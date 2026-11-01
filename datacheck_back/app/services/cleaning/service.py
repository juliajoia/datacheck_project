"""Orquestra o tratamento: versões imutáveis, prévia, aplicação confirmada, histórico, desfazer e revalidação."""
from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.catalog import SEVERITY_LABELS, category_label
from app.core.config import get_settings
from app.core.errors import DataCheckError
from app.models import Analysis, AnalysisVersion, CleaningOperation, EdaReport, User, ValidationIssue
from app.schemas.cleaning import CleaningRequest
from app.schemas.validation import AnalysisConfig
from app.services import data_store
from app.services.analyzer import run_analysis
from app.services.cleaning import fixes, imputation
from app.services.cleaning.plan import Plan, TableCtx
from app.services.cleaning.variable_types import STAT_TYPES, classify_all
from app.services.file_reader import LoadedTable
from app.utils.dates import iso
from app.validators.base import Issue

ACK_TEXT = {
    "type_change": "Confirmo que o valor altera o tipo de armazenamento da coluna.",
    "domain": "Confirmo que o valor viola o domínio observado (valores não negativos).",
    "identifier_duplicates": "Confirmo que o valor repetido pode criar identificadores duplicados.",
    "partial_application": "Confirmo aplicar apenas aos registros tratáveis; os demais continuarão como estão.",
    "conflicting_groups": "Confirmo descartar registros de grupos com valores conflitantes.",
    "remove_rows": "Confirmo a remoção dos registros (a versão original permanece preservada).",
    "clip_authorization": "Autorizo a substituição de valores extremos pelos limites.",
    "swap_confirmation": "Confirmo a inversão entre latitude e longitude.",
}
OP_LABELS = {
    "impute_missing": "Imputação de valores ausentes", "keep_missing": "Manter ausente (decisão registrada)",
    "remove_duplicates": "Remoção de duplicatas", "merge_duplicates": "Mesclagem de duplicatas",
    "manual_correction": "Correção manual", "mark_missing": "Marcado como ausente", "convert_format": "Conversão de formato",
    "clip_outliers": "Substituição por limites", "swap_coordinates": "Inversão latitude/longitude", "remove_rows": "Remoção de registros",
    "accept_exception": "Exceção aceita", "undo": "Desfazer", "restore": "Restauração de versão",
}


# ------------------------------------------------------------------ estado

@dataclass
class State:
    analysis: Analysis
    version: AnalysisVersion
    df: pd.DataFrame
    rows: list[int]
    config: AnalysisConfig
    stat: dict[str, dict]
    ctx: TableCtx

    @property
    def exceptions(self) -> list[dict]:
        return list(self.version.exceptions or [])


_cache: "OrderedDict[uuid.UUID, tuple[dict, list[Issue]]]" = OrderedDict()


def _config_of(analysis: Analysis) -> AnalysisConfig:
    return AnalysisConfig.model_validate(analysis.validation_config or {})


def get_version(db: Session, analysis: Analysis, number: int) -> AnalysisVersion:
    v = db.scalar(select(AnalysisVersion).where(AnalysisVersion.analysis_id == analysis.id, AnalysisVersion.version_number == number))
    if not v:
        raise DataCheckError("Versão não encontrada.", 404)
    return v


def load_state(db: Session, analysis: Analysis, number: Optional[int] = None) -> State:
    if analysis.status != "completed":
        raise DataCheckError("A análise ainda não foi concluída.", 409)
    if analysis.current_version is None:
        raise DataCheckError("A base desta análise não está armazenada, então não é possível tratá-la. "
                             "Refaça a análise mantendo a base armazenada, ou o prazo de retenção expirou.", 409)
    version = get_version(db, analysis, analysis.current_version if number is None else number)
    if not version.storage_reference or version.status == "purged":
        raise DataCheckError("Os dados desta versão não estão mais disponíveis (retenção expirada).", 410)
    df, rows = data_store.load_version(version.storage_reference)
    cfg = _config_of(analysis)
    stat = {c["name"]: c for c in classify_all(df, cfg.missing.markers, cfg.decimal_separator, analysis.column_types)}
    return State(analysis, version, df, rows, cfg, stat, TableCtx(df, rows, cfg.missing.markers, cfg.decimal_separator, stat))


def validate_df(cfg: AnalysisConfig, df: pd.DataFrame, rows: list[int]) -> tuple[dict, list[Issue]]:
    return run_analysis(LoadedTable(df=df, header_line=0), cfg, row_numbers=rows)


def validation_of(st: State, fresh: bool = False) -> tuple[dict, list[Issue]]:
    key = st.version.id
    if not fresh and key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    out = validate_df(st.config, st.df, st.rows)
    _cache[key] = out
    while len(_cache) > 12:
        _cache.popitem(last=False)
    return out


def _key(i: Issue) -> tuple[int, str, str]:
    return (i.row, i.column, i.category)


def _exception_keys(exceptions: list[dict]) -> set[tuple[int, str, str]]:
    return {(int(e["row"]), e["column"], e["category"]) for e in exceptions}


def pending_issues(issues: list[Issue], exceptions: list[dict]) -> tuple[list[Issue], list[Issue]]:
    ex = _exception_keys(exceptions)
    return [i for i in issues if _key(i) not in ex], [i for i in issues if _key(i) in ex]


def _summary_json(result: dict, issues: list[Issue], exceptions: list[dict]) -> dict:
    pend, acc = pending_issues(issues, exceptions)
    return {"total_issues": len(issues), "affected_rows": result["metrics"]["affected_rows"], "pending": len(pend),
            "accepted": len(acc), "pending_rows": len({i.row for i in pend}), "score": result["score"]["value"],
            "rows": result["metrics"]["total_rows"]}


def lineage(db: Session, analysis: Analysis, start: Optional[int] = None) -> list[AnalysisVersion]:
    """Cadeia de versões da `start` (padrão: atual) até a original, seguindo os pais."""
    versions = {v.version_number: v for v in db.scalars(select(AnalysisVersion).where(AnalysisVersion.analysis_id == analysis.id))}
    chain, cur = [], analysis.current_version if start is None else start
    while cur is not None and cur in versions:
        chain.append(versions[cur])
        cur = versions[cur].parent_version_number
    return chain


# ------------------------------------------------------------------ versão 0

def create_original_version(db: Session, analysis: Analysis, df: pd.DataFrame, rows: list[int], result: dict,
                            issues: list[Issue], user: Optional[User]) -> None:
    """Chamado ao concluir a análise (com a base armazenada): grava a versão 0, que nunca será sobrescrita."""
    ref = data_store.save_version(analysis.id, 0, df, rows)
    db.add(AnalysisVersion(
        analysis_id=analysis.id, version_number=0, label="Original", storage_reference=ref, total_rows=len(df),
        total_columns=int(df.shape[1]), quality_score=result["score"]["value"], exceptions=[],
        validation=_summary_json(result, issues, []), created_by=user.id if user else None))
    analysis.current_version = 0
    analysis.data_expires_at = datetime.now(timezone.utc) + timedelta(days=get_settings().data_retention_days)
    analysis.workflow_status = "ready_for_eda" if not issues else "analyzed"
    db.flush()


def _touch(analysis: Analysis) -> None:
    analysis.data_expires_at = datetime.now(timezone.utc) + timedelta(days=get_settings().data_retention_days)


# ------------------------------------------------------------------ resumo

def _original_keys(db: Session, analysis: Analysis) -> set[tuple[int, str, str]]:
    rows = db.execute(select(ValidationIssue.row_number, ValidationIssue.column_name, ValidationIssue.issue_type)
                      .where(ValidationIssue.analysis_id == analysis.id)).all()
    return {(r, c, t) for r, c, t in rows}


def _op_stats(db: Session, analysis: Analysis, chain: list[AnalysisVersion]) -> dict[str, int]:
    ids = {v.id for v in chain}
    ops = [o for o in db.scalars(select(CleaningOperation).where(CleaningOperation.analysis_id == analysis.id)) if o.version_id in ids]
    s = {"imputed_values": 0, "removed_rows": 0, "duplicates_resolved": 0, "manual_corrections": 0, "exceptions_accepted": 0, "operations": 0}
    for o in ops:
        if o.operation_type in ("undo", "restore"):
            continue
        s["operations"] += 1
        p = o.parameters or {}
        if o.operation_type == "impute_missing":
            s["imputed_values"] += len(o.replacement_values or [])
        elif o.operation_type in ("remove_duplicates", "merge_duplicates"):
            s["removed_rows"] += int(p.get("removed_count", 0))
            s["duplicates_resolved"] += int(p.get("groups_resolved", 0))
        elif o.operation_type == "remove_rows":
            s["removed_rows"] += int(p.get("removed_count", 0))
        elif o.operation_type in ("keep_missing", "accept_exception"):
            s["exceptions_accepted"] += o.affected_rows
        else:
            s["manual_corrections"] += o.affected_rows
    return s


def summary(db: Session, analysis: Analysis) -> dict[str, Any]:
    base: dict[str, Any] = {"analysis_id": str(analysis.id), "workflow_status": analysis.workflow_status,
                            "current_version": analysis.current_version}
    if analysis.current_version is None:
        return {**base, "data_available": False, "message": "A base desta análise não está armazenada; o tratamento não está disponível."}
    st = load_state(db, analysis)
    result, issues = validation_of(st)
    pend, acc = pending_issues(issues, st.exceptions)
    orig = _original_keys(db, analysis)
    cur_all, pend_keys = {_key(i) for i in issues}, {_key(i) for i in pend}
    total = len(orig | cur_all)
    handled = total - len(pend_keys)
    cats: dict[str, dict[str, int]] = {}
    for k in orig | cur_all:
        c = cats.setdefault(k[2], {"initial": 0, "pending": 0, "accepted": 0, "corrected": 0})
        c["initial"] += k in orig
        c["pending"] += k in pend_keys
        c["accepted"] += (k in cur_all and k not in pend_keys)
        c["corrected"] += k not in cur_all
    v0 = get_version(db, analysis, 0)
    chain = lineage(db, analysis)
    eda_exists = db.scalar(select(func.count()).select_from(EdaReport).where(
        EdaReport.analysis_version_id == st.version.id, EdaReport.status == "completed")) or 0
    ready = len(pend) == 0
    return {
        **base, "data_available": True, "version_label": st.version.label,
        "counts": {"total": total, "corrected": len(orig - cur_all), "accepted": len(acc), "pending": len(pend),
                   "introduced": len(cur_all - orig), "affected_rows": len({i.row for i in pend}),
                   "progress_pct": round(100 * handled / total, 1) if total else 100.0},
        "by_category": [{"category": c, "label": category_label(c), **v} for c, v in sorted(cats.items(), key=lambda kv: -kv[1]["initial"])],
        "before": {**(v0.validation or {}), "score": v0.quality_score},
        "after": {**_summary_json(result, issues, st.exceptions), "score": result["score"]["value"]},
        "operations": _op_stats(db, analysis, chain),
        "can_generate_eda": ready, "eda_generated_for_version": bool(eda_exists),
        "readiness_message": ("Sem inconsistências pendentes: a base está pronta para a análise exploratória. "
                              "Isso não significa que os dados estejam livres de problemas além das regras executadas."
                              if ready else "Conclua o tratamento dos dados antes de gerar a análise exploratória."),
        "expires_at": iso(analysis.data_expires_at),
    }


def refresh_status(db: Session, analysis: Analysis, explicit_validation: bool = False) -> None:
    st = load_state(db, analysis)
    result, issues = validation_of(st, fresh=explicit_validation)
    pend, _ = pending_issues(issues, st.exceptions)
    eda = db.scalar(select(func.count()).select_from(EdaReport).where(
        EdaReport.analysis_version_id == st.version.id, EdaReport.status == "completed")) or 0
    if not pend:
        analysis.workflow_status = "eda_generated" if eda else "ready_for_eda"
    elif analysis.current_version == 0:
        analysis.workflow_status = "analyzed"
    else:
        analysis.workflow_status = "pending" if explicit_validation else "in_treatment"
    st.version.validation = _summary_json(result, issues, st.exceptions)
    st.version.quality_score = result["score"]["value"]


def validate_treated(db: Session, analysis: Analysis) -> dict[str, Any]:
    refresh_status(db, analysis, explicit_validation=True)
    db.commit()
    return summary(db, analysis)


# ------------------------------------------------------------------ listagens

def issues_page(db: Session, analysis: Analysis, *, category=None, column=None, q=None, severity=None,
                include_accepted=False, page=1, page_size=50) -> dict[str, Any]:
    st = load_state(db, analysis)
    _, issues = validation_of(st)
    ex = _exception_keys(st.exceptions)
    items = [(i, _key(i) in ex) for i in issues if include_accepted or _key(i) not in ex]
    if category:
        items = [x for x in items if x[0].category in category]
    if column:
        items = [x for x in items if x[0].column in column]
    if severity:
        items = [x for x in items if x[0].severity in severity]
    if q and q.strip():
        n = q.strip().lower()
        items = [x for x in items if n in f"{x[0].row} {x[0].column} {x[0].value} {x[0].description}".lower()]
    total = len(items)
    chunk = items[(page - 1) * page_size: page * page_size]
    return {"total": total, "page": page, "page_size": page_size, "version": st.version.version_number,
            "items": [{"row": i.row, "column": i.column, "value": i.value, "category": i.category,
                       "category_label": category_label(i.category), "severity": i.severity,
                       "severity_label": SEVERITY_LABELS[i.severity], "description": i.description,
                       "suggestion": i.suggestion, "accepted": acc} for i, acc in chunk]}


def column_options(db: Session, analysis: Analysis, column: Optional[str]) -> dict[str, Any]:
    st = load_state(db, analysis)
    cols = []
    for name, info in st.stat.items():
        mask_missing = info["n_missing"]
        cols.append({"name": name, "stat_type": info["stat_type"], "label": info["label"], "source": info["source"],
                     "reasons": info["reasons"], "n_missing": mask_missing, "n_unique": info["n_unique"],
                     "pct_missing": round(100 * mask_missing / len(st.df), 2) if len(st.df) else 0, "order": info.get("order")})
    out: dict[str, Any] = {"version": st.version.version_number, "stat_types": STAT_TYPES, "columns": cols,
                           "methodology": imputation.METHODOLOGY}
    if column:
        if column not in st.df.columns:
            raise DataCheckError(f"A coluna «{column}» não existe.", 404)
        prof = imputation.column_profile(st.ctx, column)
        groups, order_cols = imputation.group_candidates(st.ctx, column), imputation.order_columns(st.ctx, column)
        out.update(profile=prof, group_candidates=groups, order_columns=order_cols,
                   recommendation=imputation.recommend(prof, groups, order_cols),
                   methods=imputation.method_catalog(prof, order_cols), not_informed_text=imputation.NOT_INFORMED)
    return out


def set_column_types(db: Session, analysis: Analysis, types: dict[str, dict]) -> dict[str, Any]:
    df_cols = None
    if analysis.current_version is not None:
        df_cols = set(load_state(db, analysis).df.columns)
    cur = dict(analysis.column_types or {})
    for col, spec in types.items():
        if df_cols is not None and col not in df_cols:
            raise DataCheckError(f"A coluna «{col}» não existe.", 404)
        t = spec.get("type")
        if t in (None, "", "auto"):
            cur.pop(col, None)
            continue
        if t not in STAT_TYPES:
            raise DataCheckError(f"Tipo de variável inválido para «{col}».", 422)
        entry: dict[str, Any] = {"type": t}
        if t == "ordinal":
            order = [str(x) for x in (spec.get("order") or [])]
            if len(order) < 2 or len(set(order)) != len(order):
                raise DataCheckError(f"Informe a ordem das categorias de «{col}» (ao menos 2, sem repetições).", 422)
            entry["order"] = order
        cur[col] = entry
    analysis.column_types = cur
    db.commit()
    return column_options(db, analysis, None) if df_cols is not None else {"column_types": cur}


# ------------------------------------------------------------------ planos

def build_plan(st: State, req: CleaningRequest, issues: Optional[list[Issue]] = None) -> Plan:
    a, ctx = req.action, st.ctx
    cells = list(req.cells) or [{"row": r, "column": req.column} for r in req.rows]
    if a == "impute":
        if not req.column:
            raise DataCheckError("Informe a coluna a tratar.", 422)
        return imputation.plan_impute(ctx, req.column, req.scope, req.rows or [int(c["row"]) for c in req.cells], req.params)
    if a == "remove_duplicates":
        return fixes.plan_remove_duplicates(ctx, st.config.duplicates.key_columns, req.params)
    if a == "merge_duplicates":
        return fixes.plan_merge_duplicates(ctx, st.config.duplicates.key_columns, req.params)
    if a in ("set_value", "mark_missing", "convert_number", "convert_date", "clip", "swap_latlon"):
        if a == "convert_number" and req.scope == "column_all" and req.column:
            cells = [{"row": r, "column": req.column} for r in st.rows]
        return fixes.plan_cell_fix(ctx, a, cells, req.column, req.params)
    if a == "remove_rows":
        return fixes.plan_remove_rows(ctx, req.rows or [int(c["row"]) for c in req.cells])
    if a == "accept_exception":
        items = [c for c in req.cells if c.get("category") and c.get("column")]
        if not items and req.params.get("category"):
            _, issues = validation_of(st) if issues is None else (None, issues)
            pend, _ = pending_issues(issues, st.exceptions)
            items = [{"row": i.row, "column": i.column, "category": i.category} for i in pend
                     if i.category == req.params["category"] and (not req.params.get("column") or i.column == req.params["column"])]
        return fixes.plan_exceptions(ctx, items)
    raise DataCheckError("Ação desconhecida.", 422)


def _serialize_plan(plan: Plan, limit: int = 200) -> dict[str, Any]:
    return {
        "action": plan.action, "method": plan.method, "operation_type": plan.op_type, "column": plan.column,
        "n_changes": len(plan.changes), "n_rows_affected": plan.n_rows, "n_removed": len(plan.removed),
        "n_exceptions": len(plan.exceptions),
        "changes": [{"row": c.row, "column": c.column, "old": c.old, "new": c.new, "note": c.note} for c in plan.changes[:limit]],
        "changes_truncated": len(plan.changes) > limit,
        "removed": [{"row": r["row"], "group": r.get("group"), "values": r["values"]} for r in plan.removed[:limit]],
        "removed_truncated": len(plan.removed) > limit,
        "warnings": plan.warnings, "errors": plan.errors, "notes": plan.notes, "unresolved": plan.unresolved[:200],
        "requires": [{"key": k, "text": ACK_TEXT[k]} for k in dict.fromkeys(plan.requires)],
        "requires_justification": plan.requires_justification, "parameters": plan.parameters,
    }


def _materialize(st: State, plan: Plan) -> tuple[pd.DataFrame, list[int]]:
    df = st.df.copy()
    for c in plan.changes:
        df.iat[st.ctx.pos[c.row], df.columns.get_loc(c.column)] = c.new
    gone = {r["row"] for r in plan.removed}
    keep = [i for i, r in enumerate(st.rows) if r not in gone]
    if not keep:
        raise DataCheckError("Esta operação removeria todos os registros da base.", 422)
    return df.iloc[keep].reset_index(drop=True), [st.rows[i] for i in keep]


def preview(db: Session, analysis: Analysis, req: CleaningRequest) -> dict[str, Any]:
    st = load_state(db, analysis)
    if req.base_version != st.version.version_number:
        raise DataCheckError("A base foi alterada desde que você abriu esta tela. Recarregue para continuar.", 409)
    plan = build_plan(st, req)
    out = _serialize_plan(plan)
    if not plan.errors and (plan.changes or plan.removed or plan.exceptions):
        try:
            new_df, new_rows = _materialize(st, plan)
            before = _summary_json(*validation_of(st), st.exceptions)
            ex_after = _merge_exceptions(st.exceptions, plan, req.justification, new_rows)
            after = _summary_json(*validate_df(st.config, new_df, new_rows), ex_after)
            out["impact"] = {"before": before, "after": after}
        except DataCheckError as e:
            out["errors"].append(e.message)
    return out


def _merge_exceptions(current: list[dict], plan: Plan, justification: Optional[str], new_rows: list[int]) -> list[dict]:
    changed = {(c.row, c.column) for c in plan.changes}
    alive = set(new_rows)
    kept = [e for e in current if (int(e["row"]), e["column"]) not in changed and int(e["row"]) in alive]
    seen = _exception_keys(kept)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for e in plan.exceptions:
        k = (e["row"], e["column"], e["category"])
        if k not in seen:
            kept.append({**e, "justification": justification, "at": now})
            seen.add(k)
    return kept


# ------------------------------------------------------------------ aplicação

def apply(db: Session, analysis: Analysis, user: User, req: CleaningRequest) -> dict[str, Any]:
    st = load_state(db, analysis)
    base = st.version.version_number
    if req.base_version != base:
        raise DataCheckError("A base foi alterada por outra operação. Recarregue a página para continuar.", 409)
    if not req.confirm:
        raise DataCheckError("Confirme a operação para aplicá-la. Nenhuma correção é feita sem confirmação.", 422)
    plan = build_plan(st, req)
    if plan.errors:
        raise DataCheckError(" ".join(plan.errors), 422)
    if not (plan.changes or plan.removed or plan.exceptions):
        raise DataCheckError("A operação não alteraria nenhum registro.", 422)
    missing_ack = [k for k in dict.fromkeys(plan.requires) if k not in req.acknowledge]
    if missing_ack:
        raise DataCheckError("Confirmação necessária: " + " ".join(ACK_TEXT[k] for k in missing_ack), 422)
    just = (req.justification or "").strip()
    if plan.requires_justification and not just:
        raise DataCheckError("Informe uma justificativa para registrar esta decisão.", 422)

    new_df, new_rows = _materialize(st, plan)
    n_versions = db.scalar(select(func.count()).select_from(AnalysisVersion).where(AnalysisVersion.analysis_id == analysis.id)) or 0
    if n_versions >= get_settings().max_versions:
        raise DataCheckError(f"Limite de {get_settings().max_versions} versões atingido. Exclua a análise ou continue a partir de uma versão existente.", 409)
    number = (db.scalar(select(func.max(AnalysisVersion.version_number)).where(AnalysisVersion.analysis_id == analysis.id)) or 0) + 1
    exceptions = _merge_exceptions(st.exceptions, plan, just or None, new_rows)
    result, issues = validate_df(st.config, new_df, new_rows)

    # Transição atômica da versão corrente: falha se outra requisição alterou a base nesse intervalo.
    moved = db.execute(update(Analysis).where(Analysis.id == analysis.id, Analysis.current_version == base)
                       .values(current_version=number)).rowcount
    if not moved:
        db.rollback()
        raise DataCheckError("A base foi alterada por outra operação. Recarregue a página para continuar.", 409)
    analysis.current_version = number  # sincroniza o objeto ORM com o UPDATE atômico
    ref = data_store.save_version(analysis.id, number, new_df, new_rows)
    version = AnalysisVersion(
        analysis_id=analysis.id, version_number=number, parent_version_number=base, label=f"Tratada {number}",
        storage_reference=ref, total_rows=len(new_df), total_columns=int(new_df.shape[1]), quality_score=result["score"]["value"],
        validation=_summary_json(result, issues, exceptions), exceptions=exceptions, created_by=user.id)
    db.add(version)
    db.flush()
    removed_groups = {r.get("group") for r in plan.removed if r.get("group") is not None}
    db.add(CleaningOperation(
        analysis_id=analysis.id, version_id=version.id, operation_type=plan.op_type, column_name=plan.column,
        affected_rows=plan.n_rows,
        original_values=[{"row": c.row, "column": c.column, "value": c.old} for c in plan.changes]
        + [{"row": r["row"], "removed": r["values"]} for r in plan.removed],
        replacement_values=[{"row": c.row, "column": c.column, "value": c.new} for c in plan.changes],
        method=plan.method, parameters={**plan.parameters, "removed_count": len(plan.removed), "groups_resolved": len(removed_groups),
                                         "exceptions": len(plan.exceptions), "acknowledged": req.acknowledge},
        justification=just or None, from_version=base, to_version=number, created_by=user.id))
    _touch(analysis)
    db.flush()
    _cache[version.id] = (result, issues)
    pend, _ = pending_issues(issues, exceptions)
    analysis.workflow_status = "ready_for_eda" if not pend else "in_treatment"
    db.commit()
    return {"version": number, "label": version.label, "summary": summary(db, analysis)}


# ------------------------------------------------------------------ desfazer / restaurar / histórico

def _move_pointer(db: Session, analysis: Analysis, user: User, target: int, op_type: str, mark_undone: bool) -> dict[str, Any]:
    cur = analysis.current_version
    if cur is None:
        raise DataCheckError("A base desta análise não está armazenada.", 409)
    version = get_version(db, analysis, target)
    if not version.storage_reference or version.status == "purged":
        raise DataCheckError("Os dados desta versão não estão mais disponíveis.", 410)
    if target == cur:
        raise DataCheckError("Esta já é a versão atual.", 409)
    current_v = get_version(db, analysis, cur)
    moved = db.execute(update(Analysis).where(Analysis.id == analysis.id, Analysis.current_version == cur)
                       .values(current_version=target)).rowcount
    if not moved:
        db.rollback()
        raise DataCheckError("A base foi alterada por outra operação. Recarregue a página.", 409)
    if mark_undone:
        for op in db.scalars(select(CleaningOperation).where(CleaningOperation.version_id == current_v.id)):
            op.undone = True
    db.add(CleaningOperation(analysis_id=analysis.id, version_id=version.id, operation_type=op_type, affected_rows=0,
                             method=op_type, from_version=cur, to_version=target, created_by=user.id,
                             parameters={"from": current_v.label, "to": version.label}))
    _touch(analysis)
    db.flush()
    db.refresh(analysis)
    refresh_status(db, analysis)
    db.commit()
    return summary(db, analysis)


def undo(db: Session, analysis: Analysis, user: User) -> dict[str, Any]:
    cur = analysis.current_version
    if cur is None or cur == 0:
        raise DataCheckError("Não há alteração para desfazer: esta já é a base original.", 409)
    parent = get_version(db, analysis, cur).parent_version_number
    return _move_pointer(db, analysis, user, 0 if parent is None else parent, "undo", mark_undone=True)


def restore(db: Session, analysis: Analysis, user: User, number: int) -> dict[str, Any]:
    return _move_pointer(db, analysis, user, number, "restore", mark_undone=False)


def versions_list(db: Session, analysis: Analysis) -> list[dict[str, Any]]:
    chain = {v.version_number for v in lineage(db, analysis)}
    rows = db.scalars(select(AnalysisVersion).where(AnalysisVersion.analysis_id == analysis.id).order_by(AnalysisVersion.version_number)).all()
    return [{"id": str(v.id), "version_number": v.version_number, "label": v.label, "parent_version_number": v.parent_version_number,
             "is_current": v.version_number == analysis.current_version, "in_current_lineage": v.version_number in chain,
             "status": v.status, "total_rows": v.total_rows, "total_columns": v.total_columns, "quality_score": v.quality_score,
             "validation": v.validation, "created_at": iso(v.created_at), "data_available": bool(v.storage_reference) and v.status != "purged"}
            for v in rows]


def history(db: Session, analysis: Analysis) -> list[dict[str, Any]]:
    chain_ids = {v.id for v in lineage(db, analysis)}
    names = {u.id: u.name for u in db.scalars(select(User))}
    ops = db.scalars(select(CleaningOperation).where(CleaningOperation.analysis_id == analysis.id)
                     .order_by(CleaningOperation.created_at.desc())).all()
    out = []
    for o in ops:
        out.append({
            "id": str(o.id), "analysis_id": str(o.analysis_id), "operation_type": o.operation_type,
            "operation_label": OP_LABELS.get(o.operation_type, o.operation_type), "column": o.column_name,
            "affected_rows": o.affected_rows, "method": o.method, "parameters": o.parameters, "justification": o.justification,
            "from_version": o.from_version, "to_version": o.to_version, "undone": o.undone,
            "in_current_version": o.version_id in chain_ids and not o.undone and o.operation_type not in ("undo", "restore"),
            "user": names.get(o.created_by, "—"), "created_at": iso(o.created_at),
            "original_values": (o.original_values or [])[:200], "replacement_values": (o.replacement_values or [])[:200],
            "values_truncated": len(o.original_values or []) > 200})
    return out
