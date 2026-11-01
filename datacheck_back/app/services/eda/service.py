"""Relatórios EDA: validação de prontidão, geração em segundo plano, armazenamento e consulta."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DataCheckError
from app.database import get_engine
from app.models import Analysis, AnalysisVersion, CleaningOperation, EdaReport, User
from app.schemas.eda import SECTION_LABELS, SECTIONS, EdaConfig
from app.services import data_store
from app.services.cleaning import service as cleaning
from app.services.eda import engine, report_pdf, report_xlsx
from app.utils.dates import iso

logger = logging.getLogger("datacheck")

METHOD_LABELS = {"mean": "Média", "median": "Mediana", "mode": "Moda", "constant": "Valor personalizado", "group": "Por grupo", "interpolate": "Interpolação linear",
                 "not_informed": "Não informado", "keep_missing": "Manter ausente", "nao_informado_nulo": "Não informado (mantido nulo)", "valor_manual": "Valor manual",
                 "marcar_ausente": "Marcado como ausente", "converter_numero": "Formato numérico", "converter_data": "Formato de data", "limites_de_substituicao": "Limites de substituição",
                 "inverter_lat_lon": "Inversão lat/lon", "remover_registros": "Remoção de registros", "manter_com_justificativa": "Exceção justificada", "merge": "Mesclagem",
                 "manual": "Escolha manual", "first": "Manter o primeiro", "last": "Manter o último", "latest": "Manter o mais recente", "most_complete": "Manter o mais completo"}


def _version_number(analysis: Analysis, requested: Optional[int]) -> int:
    n = analysis.current_version if requested is None else requested
    if n is None:
        raise DataCheckError("A base desta análise não está armazenada, então não é possível gerar a EDA.", 409)
    return n


def readiness(db: Session, analysis: Analysis, number: Optional[int]) -> tuple["cleaning.State", dict[str, Any]]:
    """Recalcula as pendências da versão (não confia só no status salvo)."""
    st = cleaning.load_state(db, analysis, _version_number(analysis, number))
    result, issues = cleaning.validation_of(st, fresh=True)
    pend, acc = cleaning.pending_issues(issues, st.exceptions)
    return st, {"pending": len(pend), "accepted": len(acc), "score": result["score"]["value"], "ready": len(pend) == 0}


def options(db: Session, analysis: Analysis, number: Optional[int]) -> dict[str, Any]:
    st, ready = readiness(db, analysis, number)
    app = engine.applicability(st.stat, len(st.df))
    return {"version": {"number": st.version.version_number, "label": st.version.label, "created_at": iso(st.version.created_at), "rows": len(st.df),
                        "columns": int(st.df.shape[1]), "quality_score": ready["score"]}, "readiness": ready,
            "message": None if ready["ready"] else "Conclua o tratamento dos dados antes de gerar a análise exploratória.",
            "sections": [{"key": k, "label": SECTION_LABELS[k], **app["sections"][k]} for k in SECTIONS], "columns": app["columns"],
            "temporal_columns": [c for c, i in st.stat.items() if i["stat_type"] == "temporal"],
            "numeric_columns": [c for c, i in st.stat.items() if i["stat_type"] in ("quant_discrete", "quant_continuous")]}


def _validate_config(st: "cleaning.State", cfg: EdaConfig) -> None:
    for c in cfg.columns + cfg.temporal.value_columns:
        if c not in st.df.columns:
            raise DataCheckError(f"A coluna «{c}» não existe.", 422)
    if cfg.temporal.date_column and st.stat.get(cfg.temporal.date_column, {}).get("stat_type") != "temporal":
        raise DataCheckError(f"«{cfg.temporal.date_column}» não é uma coluna de datas.", 422)
    if "correlation" in cfg.sections and engine.applicability(st.stat, len(st.df))["sections"]["correlation"]["ok"] is False and len(cfg.sections) == 1:
        raise DataCheckError("A correlação exige ao menos 2 variáveis quantitativas.", 422)


def create(db: Session, analysis: Analysis, user: User, cfg: EdaConfig) -> EdaReport:
    st, ready = readiness(db, analysis, cfg.version_number)
    if not ready["ready"]:
        raise DataCheckError("Conclua o tratamento dos dados antes de gerar a análise exploratória "
                             f"({ready['pending']} inconsistência(s) pendente(s)).", 409)
    _validate_config(st, cfg)
    report = EdaReport(analysis_id=analysis.id, analysis_version_id=st.version.id, version_number=st.version.version_number, user_id=user.id,
                       report_name=cfg.report_name.strip(), configuration={**cfg.model_dump(mode="json"), "version_number": st.version.version_number},
                       status="queued", total_rows=len(st.df), total_columns=int(st.df.shape[1]))
    db.add(report)
    db.commit()
    return report


def _treatment_info(db: Session, analysis: Analysis, st: "cleaning.State", v0: AnalysisVersion) -> dict[str, Any]:
    chain = cleaning.lineage(db, analysis, st.version.version_number)
    ids = {v.id for v in chain}
    ops = [o for o in db.scalars(select(CleaningOperation).where(CleaningOperation.analysis_id == analysis.id).order_by(CleaningOperation.created_at))
           if o.version_id in ids and o.operation_type not in ("undo", "restore")]
    stats = cleaning._op_stats(db, analysis, chain)
    return {"version_label": st.version.label, "version_number": st.version.version_number, "score_before": v0.quality_score, "score_after": st.version.quality_score,
            "rows_before": v0.total_rows, "rows_after": len(st.df), "imputed_values": stats["imputed_values"], "removed_rows": stats["removed_rows"],
            "duplicates_resolved": stats["duplicates_resolved"], "manual_corrections": stats["manual_corrections"], "exceptions_accepted": len(st.exceptions),
            "operations": [{"label": cleaning.OP_LABELS.get(o.operation_type, o.operation_type), "column": o.column_name, "method": METHOD_LABELS.get(o.method or "", o.method),
                            "affected_rows": o.affected_rows, "justification": o.justification, "at": iso(o.created_at)} for o in ops]}


def run_job(report_id: uuid.UUID) -> None:
    """Executa em segundo plano (BackgroundTasks) com sessão própria. Falhas ficam no status, sem expor dados."""
    with Session(get_engine(), expire_on_commit=False) as db:
        report = db.get(EdaReport, report_id)
        if not report:
            return
        report.status, report.error_message = "processing", None
        db.commit()
        try:
            analysis = db.get(Analysis, report.analysis_id)
            cfg = EdaConfig.model_validate(report.configuration)
            st = cleaning.load_state(db, analysis, report.version_number)
            v0 = cleaning.get_version(db, analysis, 0)
            treatment = _treatment_info(db, analysis, st, v0)
            stats = engine.build(st.df, st.stat, cfg, st.config.missing.markers, st.config.decimal_separator, treatment)
            meta = {"analysis_name": analysis.filename, "analysis_id": str(analysis.id), "version_label": st.version.label, "version_number": st.version.version_number,
                    "generated_at": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")}
            cfg_dict = cfg.model_dump(mode="json")
            data_store.save_report_file(report.id, "pdf", report_pdf.build_pdf(report.report_name, meta, stats, cfg_dict))
            data_store.save_report_file(report.id, "xlsx", report_xlsx.build_xlsx(report.report_name, meta, stats, cfg_dict))
            report.summary_statistics, report.file_reference = stats, f"reports/{report.id}"
            report.status, report.completed_at = "completed", datetime.now(timezone.utc)
            if analysis.current_version == report.version_number:
                analysis.workflow_status = "eda_generated"
            db.commit()
        except Exception as exc:  # noqa: BLE001 — o motivo detalhado vai só para o log técnico, sem dados
            logger.error("Falha na EDA %s: %s", report_id, type(exc).__name__)
            db.rollback()
            report = db.get(EdaReport, report_id)
            report.status = "failed"
            report.error_message = exc.message if isinstance(exc, DataCheckError) else "Não foi possível gerar o relatório. Tente novamente."
            db.commit()


# ------------------------------------------------------------------ consulta

def owned(db: Session, user: User, report_id: uuid.UUID) -> EdaReport:
    r = db.scalar(select(EdaReport).where(EdaReport.id == report_id, EdaReport.user_id == user.id))
    if not r:
        raise DataCheckError("Relatório não encontrado.", 404)
    return r


def _item(db: Session, r: EdaReport, names: dict[uuid.UUID, str], labels: dict[uuid.UUID, str]) -> dict[str, Any]:
    cfg = r.configuration or {}
    return {"id": str(r.id), "analysis_id": str(r.analysis_id), "analysis_name": names.get(r.analysis_id, "—"), "report_name": r.report_name,
            "version_number": r.version_number, "version_label": labels.get(r.analysis_version_id, f"Versão {r.version_number}"),
            "total_rows": r.total_rows, "total_columns": r.total_columns, "sections": cfg.get("sections", []),
            "sections_labels": [SECTION_LABELS.get(s, s) for s in cfg.get("sections", [])], "status": r.status, "error_message": r.error_message,
            "created_at": iso(r.created_at), "completed_at": iso(r.completed_at), "has_files": bool(r.file_reference), "configuration": cfg}


def list_reports(db: Session, user: User, analysis_id: Optional[uuid.UUID] = None) -> list[dict[str, Any]]:
    q = select(EdaReport).where(EdaReport.user_id == user.id)
    if analysis_id:
        q = q.where(EdaReport.analysis_id == analysis_id)
    rows = db.scalars(q.order_by(EdaReport.created_at.desc())).all()
    names = {a.id: a.filename for a in db.scalars(select(Analysis).where(Analysis.user_id == user.id))}
    labels = {v.id: v.label for v in db.scalars(select(AnalysisVersion).where(AnalysisVersion.id.in_([r.analysis_version_id for r in rows])))} if rows else {}
    return [_item(db, r, names, labels) for r in rows]


def detail(db: Session, user: User, report_id: uuid.UUID) -> dict[str, Any]:
    r = owned(db, user, report_id)
    names = {r.analysis_id: db.scalar(select(Analysis.filename).where(Analysis.id == r.analysis_id)) or "—"}
    labels = {r.analysis_version_id: db.scalar(select(AnalysisVersion.label).where(AnalysisVersion.id == r.analysis_version_id)) or ""}
    return {**_item(db, r, names, labels), "summary_statistics": r.summary_statistics if r.status == "completed" else None}


def download(db: Session, user: User, report_id: uuid.UUID, fmt: str) -> tuple[bytes, str, str]:
    if fmt not in ("pdf", "xlsx"):
        raise DataCheckError("Formato inválido. Use pdf ou xlsx.", 422)
    r = owned(db, user, report_id)
    if r.status != "completed" or not r.file_reference:
        raise DataCheckError("O relatório ainda não está pronto.", 409)
    media = "application/pdf" if fmt == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return data_store.read_file(f"{r.file_reference}.{fmt}"), media, f"datacheck_eda_{r.report_name}_v{r.version_number}.{fmt}"


def delete(db: Session, user: User, report_id: uuid.UUID) -> None:
    r = owned(db, user, report_id)
    for ext in ("pdf", "xlsx"):
        data_store.delete_reference(f"{r.file_reference}.{ext}" if r.file_reference else None)
    analysis = db.get(Analysis, r.analysis_id)
    version_id = r.analysis_version_id
    db.delete(r)
    db.flush()
    if analysis and analysis.workflow_status == "eda_generated":
        left = db.scalar(select(func.count()).select_from(EdaReport).where(EdaReport.analysis_version_id == version_id, EdaReport.status == "completed")) or 0
        if not left:
            analysis.workflow_status = "ready_for_eda"
    db.commit()


def regenerate(db: Session, user: User, report_id: uuid.UUID) -> EdaReport:
    """Reprocessa o MESMO relatório (mesma versão e configuração). Para outra versão, gere uma nova EDA."""
    r = owned(db, user, report_id)
    if r.status in ("queued", "processing"):
        raise DataCheckError("Este relatório já está sendo gerado.", 409)
    analysis = db.get(Analysis, r.analysis_id)
    version = db.get(AnalysisVersion, r.analysis_version_id)
    if not version or not version.storage_reference or version.status == "purged":
        raise DataCheckError("Os dados desta versão não estão mais disponíveis; gere uma nova EDA a partir da versão atual.", 410)
    st = cleaning.load_state(db, analysis, r.version_number)
    result, issues = cleaning.validation_of(st, fresh=True)
    if cleaning.pending_issues(issues, st.exceptions)[0]:
        raise DataCheckError("Esta versão possui inconsistências pendentes; conclua o tratamento antes.", 409)
    r.status, r.error_message = "queued", None
    db.commit()
    return r
