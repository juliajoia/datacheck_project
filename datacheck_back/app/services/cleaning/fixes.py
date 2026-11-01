"""Duplicidades, correções pontuais, valores extremos e coordenadas.

Toda função devolve um Plan (prévia). Nada é gravado aqui: a aplicação acontece no serviço,
somente após confirmação, criando uma nova versão.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.core.parsing import display_value, missing_mask, parse_date, parse_number
from app.services.cleaning.imputation import detect_date_format
from app.services.cleaning.plan import Change, Plan, TableCtx
from app.services.cleaning.stats import decimals_of, format_number, infer_decimal_mode, iqr_bounds, numeric_values

MAX_LISTED_GROUPS = 500


# ------------------------------------------------------------------ duplicidades

def duplicate_groups(t: TableCtx, key_columns: Optional[list[str]]) -> list[dict[str, Any]]:
    """Grupos de registros repetidos. Em modo chave, grupos com demais colunas diferentes são 'conflitos'."""
    keys = list(key_columns) if key_columns else list(t.df.columns)
    norm = t.df.apply(lambda c: c.str.strip())
    dup = norm[keys].duplicated(keep=False)
    if not dup.any():
        return []
    sub = norm[dup]
    gid = sub.groupby(keys, sort=False).ngroup()
    groups = []
    for g, idxs in gid.groupby(gid).groups.items():
        idxs = sorted(int(i) for i in idxs)
        others = [c for c in t.df.columns if c not in keys]
        conflicts = [c for c in others if norm.loc[idxs, c].nunique() > 1]
        records = [{"row": t.rows[i], "values": {c: t.df.iloc[i][c] for c in t.df.columns},
                    "filled": int((~missing_mask(t.df.iloc[i], t.markers)).sum())} for i in idxs]
        merge_vals, merge_conflicts = {}, []
        for c in t.df.columns:
            vals = [r["values"][c].strip() for r in records if r["values"][c].strip() and r["values"][c].strip().lower() not in {m.lower() for m in t.markers}]
            distinct = list(dict.fromkeys(vals))
            if len(distinct) > 1:
                merge_conflicts.append(c)
                merge_vals[c] = None
            else:
                merge_vals[c] = distinct[0] if distinct else ""
        groups.append({"id": records[0]["row"], "rows": [r["row"] for r in records], "exact": not conflicts,
                       "conflicts": conflicts, "records": records, "merge": {"values": merge_vals, "conflicts": merge_conflicts}})
    groups.sort(key=lambda x: x["id"])
    return groups


def _pick(group: dict, strategy: str, t: TableCtx, date_column: Optional[str]) -> Optional[list[int]]:
    rows = group["rows"]
    if strategy == "first":
        return [rows[0]]
    if strategy == "last":
        return [rows[-1]]
    if strategy == "most_complete":
        best = max(group["records"], key=lambda r: (r["filled"], -r["row"]))
        return [best["row"]]
    if strategy == "latest":
        dated = [(parse_date(r["values"][date_column].strip()), r["row"]) for r in group["records"]]
        dated = [(d, row) for d, row in dated if d]
        return [max(dated)[1]] if dated else None
    return None


def plan_remove_duplicates(t: TableCtx, key_columns: Optional[list[str]], params: dict[str, Any]) -> Plan:
    plan = Plan(action="remove_duplicates", op_type="remove_duplicates", method=params.get("strategy") or "manual",
                parameters=dict(params), requires_justification=False)
    groups = {g["id"]: g for g in duplicate_groups(t, key_columns)}
    if not groups:
        plan.errors.append("Não há registros duplicados nesta versão.")
        return plan
    strategy, date_col = params.get("strategy"), params.get("date_column")
    if strategy == "latest" and (not date_col or date_col not in t.df.columns or t.stat[date_col]["stat_type"] != "temporal"):
        plan.errors.append("Para manter o registro mais recente, escolha uma coluna temporal válida.")
        return plan
    decisions = {int(d["group"]): [int(r) for r in d["keep"]] for d in params.get("decisions") or []}
    selected = [int(g) for g in params["groups"]] if params.get("groups") else list(groups)
    conflicting = 0
    for gid in dict.fromkeys(list(decisions) + selected if decisions else selected):
        g = groups.get(gid)
        if not g:
            plan.errors.append(f"Grupo de duplicatas {gid} inexistente (a base pode ter mudado).")
            continue
        if gid in decisions:
            keep = decisions[gid]
            if not keep or not set(keep) <= set(g["rows"]):
                plan.errors.append(f"Grupo {gid}: escolha ao menos um registro do próprio grupo para manter.")
                continue
        elif strategy:
            keep = _pick(g, strategy, t, date_col)
            if keep is None:
                plan.errors.append(f"Grupo {gid}: nenhuma data válida na coluna «{date_col}» para decidir o mais recente.")
                continue
        else:
            plan.errors.append(f"Grupo {gid}: escolha qual registro manter ou uma estratégia.")
            continue
        if not g["exact"] and gid not in decisions:
            conflicting += 1
        for r in g["records"]:
            if r["row"] not in keep:
                plan.removed.append({"row": r["row"], "values": r["values"], "group": gid})
        if len(keep) == len(g["rows"]):
            plan.notes.append(f"Grupo {gid}: todos os registros mantidos (nenhuma remoção).")
    if conflicting:
        plan.warnings.append(f"{conflicting} grupo(s) têm a mesma chave, mas valores diferentes nas demais colunas: não são duplicatas exatas. Confirme que deseja descartar esses registros.")
        plan.requires.append("conflicting_groups")
    if not plan.removed and not plan.errors:
        plan.errors.append("Nenhum registro seria removido com essa escolha.")
    plan.requires.append("remove_rows")
    plan.notes.append("Os critérios automáticos são sugestões: nada é removido até você confirmar.")
    return plan


def plan_merge_duplicates(t: TableCtx, key_columns: Optional[list[str]], params: dict[str, Any]) -> Plan:
    plan = Plan(action="merge_duplicates", op_type="merge_duplicates", method="merge", parameters=dict(params), requires_justification=False)
    groups = {g["id"]: g for g in duplicate_groups(t, key_columns)}
    merges = params.get("merges") or []
    if not merges:
        plan.errors.append("Informe ao menos um grupo para mesclar.")
        return plan
    for m in merges:
        g = groups.get(int(m["group"]))
        if not g:
            plan.errors.append(f"Grupo de duplicatas {m['group']} inexistente (a base pode ter mudado).")
            continue
        chosen = dict(m.get("values") or {})
        keep_row = int(m.get("keep_row") or g["rows"][0])
        if keep_row not in g["rows"]:
            plan.errors.append(f"Grupo {g['id']}: a linha a manter não pertence ao grupo.")
            continue
        suggestion = g["merge"]["values"]
        for col in g["merge"]["conflicts"]:
            if col not in chosen or str(chosen[col]).strip() == "":
                plan.errors.append(f"Grupo {g['id']}: há valores conflitantes em «{col}»; escolha o valor final (a mesclagem nunca é automática com conflito).")
        final = {c: (chosen[c] if c in chosen and str(chosen[c]).strip() != "" else suggestion[c]) for c in t.df.columns}
        base = next(r for r in g["records"] if r["row"] == keep_row)
        for c in t.df.columns:
            if final[c] is not None and str(final[c]) != base["values"][c]:
                plan.changes.append(Change(keep_row, c, base["values"][c], str(final[c]), "mesclado"))
        for r in g["records"]:
            if r["row"] != keep_row:
                plan.removed.append({"row": r["row"], "values": r["values"], "group": g["id"]})
    plan.requires.append("remove_rows")
    plan.notes.append("A linha mantida recebe os valores mesclados; as demais do grupo são removidas.")
    return plan


# ------------------------------------------------------------------ correções pontuais

def _cells(t: TableCtx, plan: Plan, cells: list[dict], default_col: Optional[str]) -> list[tuple[int, str, dict]]:
    out = []
    for c in cells:
        col = c.get("column") or default_col
        if col not in t.df.columns:
            plan.errors.append(f"A coluna «{col}» não existe.")
            continue
        r = int(c["row"])
        if r not in t.pos:
            plan.errors.append(f"A linha {r} não existe nesta versão.")
            continue
        out.append((t.pos[r], col, c))
    return out


def plan_cell_fix(t: TableCtx, action: str, cells: list[dict], column: Optional[str], params: dict[str, Any]) -> Plan:
    plan = Plan(action=action, op_type=action, method=action, column=column, parameters=dict(params))
    if action == "swap_latlon":
        return _plan_swap(t, plan, sorted({int(c["row"]) for c in cells}), params)
    targets = _cells(t, plan, cells, column)
    if not targets and not plan.errors:
        plan.errors.append("Selecione ao menos um registro.")
    if plan.errors:
        return plan

    if action == "set_value":
        plan.op_type, plan.method = "manual_correction", "valor_manual"
        for i, col, c in targets:
            value = str(c.get("value", params.get("value", ""))).strip()
            if value == "":
                plan.errors.append(f"Informe o novo valor para a linha {t.rows[i]}.")
                continue
            st = t.stat[col]["stat_type"]
            if st in ("quant_discrete", "quant_continuous") and parse_number(value, "auto") is None and "type_change" not in plan.requires:
                plan.requires.append("type_change")
                plan.warnings.append("Há valor(es) não numérico(s) em coluna numérica: isso altera o tipo de armazenamento e pode prejudicar cálculos.")
            if st == "temporal" and parse_date(value) is None:
                plan.errors.append(f"«{value}» não é uma data válida (linha {t.rows[i]}).")
                continue
            plan.changes.append(Change(t.rows[i], col, t.df.iloc[i][col], value))
    elif action == "mark_missing":
        plan.op_type, plan.method = "mark_missing", "marcar_ausente"
        for i, col, _ in targets:
            if t.df.iloc[i][col] != "":
                plan.changes.append(Change(t.rows[i], col, t.df.iloc[i][col], ""))
        plan.notes.append("Os valores ficarão vazios (ausentes) e poderão ser tratados depois pela imputação.")
    elif action == "convert_number":
        _convert_numbers(t, plan, targets, params)
    elif action == "convert_date":
        _convert_dates(t, plan, targets, params)
    elif action == "clip":
        plan.op_type, plan.method = "clip_outliers", "limites_de_substituicao"
        lo, hi = params.get("lower"), params.get("upper")
        if lo is None and hi is None:
            plan.errors.append("Informe o limite inferior e/ou superior de substituição.")
            return plan
        for i, col, _ in targets:
            raw = t.df.iloc[i][col]
            mode = infer_decimal_mode(t.df[col], t.decimal)
            n = parse_number(raw, mode)
            if n is None:
                continue
            new = min(max(n, float(lo) if lo is not None else n), float(hi) if hi is not None else n)
            if new != n:
                dec = max(decimals_of(t.df[col]), 0)
                plan.changes.append(Change(t.rows[i], col, raw, format_number(new, dec, mode), "limitado"))
        plan.requires.append("clip_authorization")
        plan.warnings.append("Valores atípicos não são necessariamente erros: substituí-los pelos limites altera a distribuição dos dados. Aplique somente com autorização explícita.")
    else:
        plan.errors.append("Ação desconhecida.")
    if not plan.changes and not plan.errors and not plan.unresolved:
        plan.errors.append("A ação não alteraria nenhum valor.")
    if plan.unresolved:
        plan.warnings.append(f"{len(plan.unresolved)} valor(es) não puderam ser convertidos e ficarão como estão: linhas {', '.join(map(str, plan.unresolved[:10]))}{'…' if len(plan.unresolved) > 10 else ''}.")
        plan.requires.append("partial_application")
    return plan


def _plan_swap(t: TableCtx, plan: Plan, rows: list[int], params: dict[str, Any]) -> Plan:
    lat, lon = params.get("lat_column"), params.get("lon_column")
    if lat not in t.df.columns or lon not in t.df.columns or lat == lon:
        plan.errors.append("Informe as colunas de latitude e longitude.")
        return plan
    if not rows:
        plan.errors.append("Selecione ao menos um registro.")
        return plan
    plan.op_type, plan.method = "swap_coordinates", "inverter_lat_lon"
    for r in rows:
        if r not in t.pos:
            plan.errors.append(f"A linha {r} não existe nesta versão.")
            continue
        i = t.pos[r]
        a, b = t.df.iloc[i][lat], t.df.iloc[i][lon]
        plan.changes += [Change(r, lat, a, b, "latitude ↔ longitude"), Change(r, lon, b, a, "latitude ↔ longitude")]
    plan.requires.append("swap_confirmation")
    plan.warnings.append("A inversão é apenas uma sugestão baseada nos intervalos válidos. Confirme que ela corresponde ao dado real.")
    return plan


def _decimals_in(raw: str, source: str) -> int:
    """Casas decimais do texto de origem, conforme o separador decimal declarado."""
    if "e" in raw.lower():
        return 0
    sep = {"comma": ",", "dot": "."}.get(source)
    if sep is None:  # automático: o último separador presente é o decimal quando só há um tipo
        has_c, has_d = "," in raw, "." in raw
        sep = "," if has_c and (not has_d or raw.rfind(",") > raw.rfind(".")) else "."
    return len(raw.rsplit(sep, 1)[1]) if sep in raw else 0


def _convert_numbers(t, plan, targets, params) -> None:
    plan.op_type, plan.method = "convert_format", "converter_numero"
    source, target = params.get("source_decimal", "auto"), params.get("target_decimal", "dot")
    if target not in ("comma", "dot") or source not in ("auto", "comma", "dot"):
        plan.errors.append("Escolha o separador decimal de origem e de destino.")
        return
    for i, col, _ in targets:
        raw = t.df.iloc[i][col]
        n = parse_number(raw, source)
        if n is None:
            plan.unresolved.append(t.rows[i])
            continue
        dec = _decimals_in(raw.strip(), source)
        new = format_number(n, dec, target)
        if new != raw:
            plan.changes.append(Change(t.rows[i], col, raw, new, "formato numérico"))


def _convert_dates(t, plan, targets, params) -> None:
    plan.op_type, plan.method = "convert_format", "converter_data"
    src = params.get("source_format") or None
    fmt_out = params.get("target_format") or "%Y-%m-%d"
    for i, col, _ in targets:
        raw = t.df.iloc[i][col]
        d = parse_date(raw, [src] if src else None)
        if d is None:
            plan.unresolved.append(t.rows[i])
            continue
        new = d.strftime(fmt_out)
        if new != raw:
            plan.changes.append(Change(t.rows[i], col, raw, new, "formato de data"))
    plan.notes.append("Datas desconhecidas nunca são inventadas: valores não interpretáveis permanecem como estão.")


def plan_remove_rows(t: TableCtx, rows: list[int]) -> Plan:
    plan = Plan(action="remove_rows", op_type="remove_rows", method="remover_registros")
    pos, unknown = t.positions([int(r) for r in rows])
    if unknown:
        plan.errors.append(f"Linha(s) inexistente(s): {', '.join(map(str, unknown[:5]))}.")
    if not pos and not plan.errors:
        plan.errors.append("Selecione ao menos um registro.")
    for i in pos:
        plan.removed.append({"row": t.rows[i], "values": {c: t.df.iloc[i][c] for c in t.df.columns}})
    plan.requires.append("remove_rows")
    plan.warnings.append("Os registros removidos deixam de existir na versão tratada (a versão original permanece intacta e pode ser restaurada).")
    return plan


def plan_exceptions(t: TableCtx, items: list[dict]) -> Plan:
    plan = Plan(action="accept_exception", op_type="accept_exception", method="manter_com_justificativa", requires_justification=True)
    for it in items:
        r = int(it["row"])
        if r not in t.pos:
            plan.errors.append(f"A linha {r} não existe nesta versão.")
            continue
        plan.exceptions.append({"row": r, "column": it["column"], "category": it["category"]})
    if not plan.exceptions and not plan.errors:
        plan.errors.append("Nenhuma ocorrência selecionada.")
    plan.notes.append("As ocorrências serão mantidas como estão e registradas como exceção aceita (a justificativa é obrigatória).")
    return plan


# ------------------------------------------------------------------ valores extremos e coordenadas

def detect_outliers(t: TableCtx, column: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
    series = t.df[column]
    mode = infer_decimal_mode(series[~missing_mask(series, t.markers)].str.strip(), t.decimal)
    x = numeric_values(series, t.markers, mode)
    out: dict[str, Any] = {"column": column, "method": method, "n_numeric": int(len(x)), "candidates": [],
                           "note": "Valores atípicos não são necessariamente erros: podem ser observações legítimas e raras."}
    if len(x) < 4:
        out["error"] = "Há poucas observações numéricas para detectar valores extremos."
        return out
    lo = hi = None
    if method == "iqr":
        factor = float(params.get("factor") or 1.5)
        b = iqr_bounds(x, factor)
        if b is None:
            out["error"] = "Intervalo interquartil nulo: não é possível aplicar o critério."
            return out
        lo, hi = b
        out["justification"] = (f"Critério do intervalo interquartil: valores abaixo de Q1 − {factor:g}×IQR ({lo:.4g}) ou acima de Q3 + {factor:g}×IQR ({hi:.4g}) "
                                f"são marcados como possíveis valores extremos (Q1={x.quantile(.25):.4g}, Q3={x.quantile(.75):.4g}).")
    elif method == "zscore":
        thr = float(params.get("threshold") or 3.0)
        sd = float(x.std())
        if not sd or math.isnan(sd):
            out["error"] = "Desvio padrão nulo: o z-score não se aplica (coluna sem variação)."
            return out
        mu = float(x.mean())
        lo, hi = mu - thr * sd, mu + thr * sd
        out["justification"] = (f"Z-score: valores a mais de {thr:g} desvios padrão da média ({mu:.4g}; desvio {sd:.4g}) estão fora de [{lo:.4g}; {hi:.4g}]. "
                                "O critério é adequado a distribuições aproximadamente simétricas; a média e o desvio são sensíveis aos próprios extremos.")
    elif method == "limits":
        lo = float(params["min"]) if params.get("min") is not None else None
        hi = float(params["max"]) if params.get("max") is not None else None
        if lo is None and hi is None:
            out["error"] = "Informe ao menos um limite."
            return out
        out["justification"] = f"Limites definidos por você: mínimo {lo if lo is not None else '—'} e máximo {hi if hi is not None else '—'}."
    else:
        out["error"] = "Método desconhecido (use iqr, zscore ou limits)."
        return out
    out["lower"], out["upper"] = lo, hi
    mask = pd.Series(False, index=x.index)
    if lo is not None:
        mask |= x < lo
    if hi is not None:
        mask |= x > hi
    out["candidates"] = [{"row": t.rows[int(i)], "value": series.iloc[int(i)], "number": float(x.loc[i]),
                          "reason": "abaixo do limite inferior" if (lo is not None and x.loc[i] < lo) else "acima do limite superior"}
                         for i in x.index[mask]][:1000]
    out["n_candidates"] = int(mask.sum())
    return out


def suggest_coordinate_swaps(t: TableCtx, lat_col: str, lon_col: str) -> list[dict[str, Any]]:
    """Linhas em que inverter latitude/longitude produziria coordenadas válidas (sugestão, não correção)."""
    out = []
    mode = infer_decimal_mode(pd.concat([t.df[lat_col], t.df[lon_col]]), t.decimal)
    for i in range(len(t.df)):
        a, b = parse_number(t.df.iloc[i][lat_col], mode), parse_number(t.df.iloc[i][lon_col], mode)
        if a is None or b is None:
            continue
        invalid_now = abs(a) > 90 or abs(b) > 180
        valid_swapped = abs(b) <= 90 and abs(a) <= 180
        if invalid_now and valid_swapped:
            out.append({"row": t.rows[i], "latitude": t.df.iloc[i][lat_col], "longitude": t.df.iloc[i][lon_col],
                        "reason": "Latitude fora de -90..90 e, trocando as colunas, ambos os valores ficam válidos."})
    return out
