"""Tratamento de valores ausentes: perfil da coluna, recomendação explicável e planos de imputação.

As recomendações são HEURÍSTICAS documentadas (METHODOLOGY), não verdades estatísticas:
a distribuição observada não revela o mecanismo de ausência. Nada é aplicado sem confirmação.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.core.parsing import DEFAULT_DATE_FORMATS, missing_mask, parse_date, parse_number
from app.services.cleaning.plan import Change, Plan, TableCtx
from app.services.cleaning.stats import (decimals_of, format_number, infer_decimal_mode, iqr_bounds, mode_of,
                                         numeric_values, safe_skew)
from app.services.cleaning.variable_types import QUALITATIVE, QUANT

MIN_VALID = 3              # mínimo de observações válidas para calcular média/mediana/moda
MIN_VALID_RECOMMEND = 5    # abaixo disso não se recomenda imputar
MIN_GROUP = 3              # observações mínimas por grupo (padrão)
SKEW_LIMIT = 0.5           # |assimetria| abaixo disso = aproximadamente simétrica
OUTLIER_FRAC_LIMIT = 0.02  # fração de pontos fora de 1,5×IQR considerada relevante
ETA2_MIN = 0.25            # variância explicada pelo grupo para recomendar imputação por grupo
COVERAGE_MIN = 0.8         # fração de ausências cobertas por grupos com observações suficientes
HIGH_MISSING_PCT = 20.0
VERY_HIGH_MISSING_PCT = 40.0
NOT_INFORMED = "Não Informado"

METHODOLOGY = [
    f"Variável quantitativa: com |assimetria| < {SKEW_LIMIT} e menos de {OUTLIER_FRAC_LIMIT:.0%} de valores além de 1,5×IQR, recomenda-se a média; caso contrário, a mediana.",
    f"Se uma coluna de agrupamento explica ao menos {ETA2_MIN:.0%} da variância (η²) e cobre ao menos {COVERAGE_MIN:.0%} das ausências com grupos de ≥ {MIN_GROUP} observações, recomenda-se a estatística por grupo.",
    "Variável discreta: o resultado é arredondado para inteiro e não fica negativo quando todos os valores observados são não negativos.",
    "Variável qualitativa nominal: recomenda-se 'Não Informado', pois preencher com a categoria mais frequente pode produzir uma classificação incorreta.",
    "Datas: não se inventam datas desconhecidas; recomenda-se manter ausente.",
    "Identificadores: nunca se usam medidas estatísticas; a revisão é manual.",
    f"Com menos de {MIN_VALID_RECOMMEND} observações válidas não se recomenda imputar. Ausência ≥ {HIGH_MISSING_PCT:g}% gera alerta de viés.",
    "A distribuição observada não permite determinar o mecanismo de ausência dos dados; nenhum método é universalmente correto.",
]


def pct_text(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "%"


def num_text(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


# ------------------------------------------------------------------ perfil

def column_profile(t: TableCtx, column: str) -> dict[str, Any]:
    series, info = t.df[column], t.stat[column]
    mask = missing_mask(series, t.markers)
    valid_raw = series[~mask].str.strip()
    n, n_missing, n_valid = len(series), int(mask.sum()), int((~mask).sum())
    prof: dict[str, Any] = {
        "column": column, "stat_type": info["stat_type"], "stat_label": info["label"],
        "n_total": n, "n_missing": n_missing, "pct_missing": round(100 * n_missing / n, 2) if n else 0.0,
        "n_valid": n_valid, "n_unique": int(valid_raw.nunique()),
    }
    st = info["stat_type"]
    if st in QUANT and n_valid:
        x = numeric_values(series, t.markers, infer_decimal_mode(valid_raw, t.decimal))
        if len(x):
            bounds = iqr_bounds(x)
            out = int(((x < bounds[0]) | (x > bounds[1])).sum()) if bounds else 0
            prof.update(n_numeric=int(len(x)), mean=float(x.mean()), median=float(x.median()),
                        std=float(x.std()) if len(x) > 1 else None, min=float(x.min()), max=float(x.max()),
                        skew=safe_skew(x), outlier_count=out, outlier_frac=out / len(x), non_negative=bool(x.min() >= 0))
            counts = x.value_counts()
            prof["mode"] = float(counts[counts == counts.max()].index.min())
            prof["mode_count"] = int(counts.max())
            prof["mode_share"] = float(counts.max() / len(x))
    elif st in QUALITATIVE and n_valid:
        counts = valid_raw.value_counts()
        prof["top_categories"] = [{"value": str(k), "count": int(v)} for k, v in counts.head(5).items()]
        prof["mode"] = str(mode_of(valid_raw, info.get("order")))
        prof["mode_share"] = float(counts.max() / n_valid)
    elif st == "temporal" and n_valid:
        dates = [d for d in (parse_date(v) for v in valid_raw.unique()) if d]
        if dates:
            prof["min_date"], prof["max_date"] = min(dates).isoformat(), max(dates).isoformat()
    return prof


def group_candidates(t: TableCtx, column: str, limit: int = 5) -> list[dict[str, Any]]:
    """Colunas qualitativas que explicam parte da variação da coluna quantitativa (η²)."""
    if t.stat[column]["stat_type"] not in QUANT:
        return []
    series = t.df[column]
    x = numeric_values(series, t.markers, infer_decimal_mode(series[~missing_mask(series, t.markers)], t.decimal))
    if len(x) < MIN_VALID_RECOMMEND:
        return []
    target_missing = missing_mask(series, t.markers)
    out = []
    for other, info in t.stat.items():
        if other == column or info["stat_type"] not in QUALITATIVE or info["n_unique"] < 2 or info["n_unique"] > 50:
            continue
        keys = t.df[other].str.strip()
        key_ok = ~missing_mask(t.df[other], t.markers)
        both = x.index.intersection(keys.index[key_ok])
        if len(both) < MIN_VALID_RECOMMEND:
            continue
        g = pd.DataFrame({"x": x.loc[both], "k": keys.loc[both]})
        sizes = g.groupby("k")["x"].size()
        sst = float(((g["x"] - g["x"].mean()) ** 2).sum())
        if sst == 0 or len(sizes) < 2:
            continue
        ssb = float((g.groupby("k")["x"].agg(lambda s: len(s) * (s.mean() - g["x"].mean()) ** 2)).sum())
        miss_idx = target_missing.index[target_missing & key_ok]
        covered = sum(1 for i in miss_idx if sizes.get(keys.loc[i], 0) >= MIN_GROUP)
        out.append({"column": other, "eta_squared": round(ssb / sst, 4), "n_groups": int(len(sizes)),
                    "coverage": round(covered / len(miss_idx), 4) if len(miss_idx) else 0.0})
    return sorted(out, key=lambda r: -r["eta_squared"])[:limit]


def order_columns(t: TableCtx, column: str) -> list[str]:
    return [c for c, i in t.stat.items() if c != column and i["stat_type"] in ("temporal",) + QUANT]


# ------------------------------------------------------------------ catálogo e recomendação

def method_catalog(prof: dict[str, Any], order_cols: list[str]) -> list[dict[str, Any]]:
    st, n_valid = prof["stat_type"], prof["n_valid"]
    quant, qual = st in QUANT, st in QUALITATIVE

    def m(key: str, label: str, desc: str, ok: bool, why: str = "") -> dict[str, Any]:
        return {"key": key, "label": label, "description": desc, "available": ok, "reason": None if ok else why}

    enough = n_valid >= MIN_VALID
    few = f"Há apenas {n_valid} valor(es) válido(s); mínimo de {MIN_VALID}."
    wrong_q = "Disponível apenas para variáveis quantitativas."
    wrong_stat = "Não se aplica a este tipo de variável."
    ident = st == "identifier"
    mode_ok = enough and (qual or (quant and prof.get("mode_count", 1) > 1))
    mode_why = few if not enough else ("Nenhum valor se repete; a moda não é informativa." if quant else wrong_stat)
    return [
        m("mean", "Média", "Preenche com a média dos valores válidos. Adequada a distribuições aproximadamente simétricas, sem extremos relevantes.",
          quant and enough, wrong_q if not quant else few),
        m("median", "Mediana", "Preenche com a mediana dos valores válidos. Menos sensível a assimetria e valores extremos.",
          quant and enough, wrong_q if not quant else few),
        m("mode", "Moda", "Preenche com o valor/categoria mais frequente, quando isso faz sentido para a variável.",
          mode_ok and not ident, mode_why if not ident else "Identificadores não devem ser preenchidos por medidas estatísticas."),
        m("constant", "Valor personalizado", "Você informa o valor de preenchimento (para identificadores, um valor por registro).",
          True),
        m("group", "Imputação por grupo", "Usa a estatística dos registros do mesmo grupo (uma ou mais colunas de agrupamento).",
          (quant or qual) and enough, wrong_stat if not (quant or qual) else few),
        m("interpolate", "Interpolação linear", "Estima valores entre observações vizinhas de uma série ordenada. Exige coluna de ordenação (data ou número).",
          quant and n_valid >= 2 and bool(order_cols),
          wrong_q if not quant else (f"Há apenas {n_valid} valor(es) válido(s); a interpolação exige ao menos 2." if n_valid < 2 else "Não há coluna de data ou numérica para ordenar a série.")),
        m("not_informed", "Não informado", f"Qualitativas: preenche com «{NOT_INFORMED}». Quantitativas: mantém o valor nulo e registra a decisão (o texto alteraria o tipo da coluna).",
          quant or qual, "Para datas e identificadores, prefira manter ausente ou revisar manualmente."),
        m("keep_missing", "Manter ausente", "Mantém os valores ausentes e registra a sua decisão (aceita como exceção).", True),
    ]


def recommend(prof: dict[str, Any], groups: list[dict[str, Any]], order_cols: list[str]) -> dict[str, Any]:
    st, n_valid, pct = prof["stat_type"], prof["n_valid"], prof["pct_missing"]
    warnings: list[str] = []
    if pct >= VERY_HIGH_MISSING_PCT:
        warnings.append(f"{pct_text(pct)} dos valores estão ausentes: qualquer imputação pode introduzir viés considerável. Considere investigar a origem da ausência.")
    elif pct >= HIGH_MISSING_PCT:
        warnings.append(f"{pct_text(pct)} dos valores estão ausentes: a imputação pode introduzir viés.")
    warnings.append("A distribuição observada não permite determinar por que os dados estão ausentes; o método sugerido é uma heurística, não uma garantia.")

    def rec(method: str, label: str, why: str, **extra: Any) -> dict[str, Any]:
        return {"method": method, "label": label, "justification": why, "warnings": warnings, **extra}

    if prof["n_missing"] == 0:
        return rec("none", "Nenhum valor ausente", "Esta coluna não possui valores ausentes.")
    if st == "identifier":
        return rec("manual_review", "Revisão manual obrigatória",
                   "Não é recomendado preencher identificadores utilizando medidas estatísticas como média ou mediana.")
    if st == "temporal":
        return rec("keep_missing", "Manter ausente", "Datas desconhecidas não devem ser inventadas; preencher com uma data estimada criaria uma informação que não existe nos dados.")
    if n_valid < MIN_VALID_RECOMMEND:
        return rec("keep_missing", "Manter ausente",
                   f"Há apenas {n_valid} observação(ões) válida(s); com menos de {MIN_VALID_RECOMMEND} não é possível sustentar uma imputação estatística.")
    if st in QUALITATIVE:
        why = ("Como a ausência pode representar uma informação desconhecida, preencher automaticamente com a categoria mais frequente poderia produzir uma classificação incorreta.")
        if st == "ordinal":
            why += " Como a variável é ordinal, a categoria «Não Informado» ficará fora da escala ordenada."
        return rec("not_informed", f"Manter como {NOT_INFORMED}", why)

    # quantitativas
    skew, out_frac = prof.get("skew"), prof.get("outlier_frac", 0.0)
    symmetric = skew is not None and abs(skew) < SKEW_LIMIT and out_frac <= OUTLIER_FRAC_LIMIT
    stat = "mean" if symmetric else "median"
    label = "Média" if symmetric else "Mediana"
    skew_txt = "indeterminada (poucos valores distintos)" if skew is None else num_text(skew)
    if symmetric:
        why = (f"A distribuição dos valores observados é aproximadamente simétrica (assimetria {skew_txt}) e sem valores extremos relevantes "
               f"({prof.get('outlier_count', 0)} além de 1,5×IQR); a média representa adequadamente a tendência central.")
    else:
        why = (f"A distribuição observada apresenta assimetria {skew_txt} e {prof.get('outlier_count', 0)} valor(es) extremo(s) pelo critério de 1,5×IQR; "
               "a mediana é menos sensível a valores extremos e pode representar melhor a tendência central.")
    if prof["stat_type"] == "quant_discrete":
        why += " O resultado será arredondado para inteiro (variável discreta)."
        if prof.get("n_unique", 99) <= 5 and prof.get("mode_share", 0) >= 0.5:
            return rec("mode", "Moda", f"A variável discreta tem poucos valores distintos ({prof['n_unique']}) e um valor predominante ({pct_text(100 * prof['mode_share'])} das observações).")
    best = next((g for g in groups if g["eta_squared"] >= ETA2_MIN and g["coverage"] >= COVERAGE_MIN), None)
    if best:
        return rec("group", f"{label} por grupo ({best['column']})",
                   f"A coluna «{best['column']}» explica {pct_text(100 * best['eta_squared'])} da variação (η²) e {pct_text(100 * best['coverage'])} das ausências "
                   f"pertencem a grupos com ao menos {MIN_GROUP} observações. {why}",
                   statistic=stat, group_by=[best["column"]])
    return rec(stat, label, why)


# ------------------------------------------------------------------ planos

def detect_date_format(series: pd.Series, markers: list[str]) -> str:
    valid = series[~missing_mask(series, markers)].str.strip().unique()
    best, score = DEFAULT_DATE_FORMATS[0], -1
    for fmt in DEFAULT_DATE_FORMATS:
        s = sum(1 for v in valid if parse_date(v, [fmt]) is not None)
        if s > score:
            best, score = fmt, s
    return best


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


class _Fmt:
    """Formata o valor calculado respeitando tipo estatístico, separador decimal e domínio."""

    def __init__(self, t: TableCtx, column: str, prof: dict[str, Any], plan: Plan):
        series = t.df[column]
        valid_raw = series[~missing_mask(series, t.markers)].str.strip()
        self.discrete = t.stat[column]["stat_type"] == "quant_discrete"
        self.dec = 0 if self.discrete else max(decimals_of(valid_raw), 1)
        self.mode = infer_decimal_mode(valid_raw, t.decimal)
        self.nonneg = bool(prof.get("non_negative"))
        self.plan = plan
        if self.discrete:
            plan.notes.append("Variável discreta: valores calculados são arredondados para inteiros.")

    def __call__(self, v: float) -> str:
        if self.discrete:
            v = float(_round_half_up(v))
        if self.nonneg and v < 0:
            v = 0.0
            if "Domínio" not in " ".join(self.plan.notes):
                self.plan.notes.append("Domínio preservado: valor negativo ajustado para 0 (todos os valores observados são não negativos).")
        return format_number(v, self.dec, self.mode)


def plan_impute(t: TableCtx, column: str, scope: str, rows: list[int], params: dict[str, Any]) -> Plan:
    method = params.get("method", "")
    plan = Plan(action="impute", op_type="impute_missing", method=method, column=column, parameters=dict(params))
    if column not in t.df.columns:
        plan.errors.append(f"A coluna «{column}» não existe.")
        return plan
    prof = column_profile(t, column)
    st = prof["stat_type"]
    series = t.df[column]
    mask = missing_mask(series, t.markers)

    if scope == "column_all":
        targets = [int(i) for i in series.index[mask]]
    else:
        pos, unknown = t.positions(rows)
        if unknown:
            plan.errors.append(f"Linha(s) inexistente(s) nesta versão: {', '.join(map(str, unknown[:5]))}.")
        not_missing = [t.rows[i] for i in pos if not mask.iloc[i]]
        if not_missing:
            plan.errors.append(f"A(s) linha(s) {', '.join(map(str, not_missing[:5]))} não possui(em) valor ausente em «{column}».")
        targets = [i for i in pos if mask.iloc[i]]
    if not targets and not plan.errors:
        plan.errors.append("Não há valores ausentes selecionados para tratar.")
    if plan.errors:
        return plan

    catalog = {m["key"]: m for m in method_catalog(prof, order_columns(t, column))}
    if method not in catalog:
        plan.errors.append("Método de imputação desconhecido.")
        return plan
    if not catalog[method]["available"]:
        plan.errors.append(f"«{catalog[method]['label']}» indisponível: {catalog[method]['reason']}")
        return plan

    quant, qual = st in QUANT, st in QUALITATIVE
    old = {i: series.iloc[i] for i in targets}
    fmt = _Fmt(t, column, prof, plan) if quant else None
    valid_raw = series[~mask].str.strip()
    nums = numeric_values(series, t.markers, infer_decimal_mode(valid_raw, t.decimal)) if quant else None
    order = t.stat[column].get("order")

    def put(i: int, new: str, note: str = "") -> None:
        plan.changes.append(Change(t.rows[i], column, old[i], new, note))

    if method in ("mean", "median", "mode"):
        if quant:
            value = {"mean": nums.mean(), "median": nums.median(), "mode": prof.get("mode")}[method]
            text = fmt(float(value))
        else:
            text = str(mode_of(valid_raw, order))
        for i in targets:
            put(i, text)
        plan.notes.append(f"Valor calculado a partir de {len(nums) if quant else len(valid_raw)} observações válidas: {text}.")
        if method == "mean" and quant and (prof.get("outlier_frac", 0) > OUTLIER_FRAC_LIMIT or abs(prof.get("skew") or 0) >= SKEW_LIMIT):
            plan.warnings.append("A média é sensível à assimetria/valores extremos observados nesta coluna; considere a mediana.")
        if method == "mode" and qual and st == "nominal":
            plan.warnings.append("Preencher com a categoria mais frequente pode produzir classificações incorretas se a ausência for informativa.")

    elif method == "constant":
        _plan_constant(t, plan, column, st, prof, targets, old, params, fmt, order)

    elif method == "group":
        _plan_group(t, plan, column, st, targets, old, params, fmt, nums, valid_raw, order)

    elif method == "interpolate":
        _plan_interpolate(t, plan, column, targets, old, params, fmt, nums)

    elif method == "not_informed":
        if qual:
            text = str(params.get("text") or NOT_INFORMED)
            for i in targets:
                put(i, text)
            if st == "ordinal":
                plan.warnings.append(f"«{text}» não pertence à ordem definida para esta variável ordinal.")
        else:
            plan.op_type, plan.method = "keep_missing", "nao_informado_nulo"
            plan.notes.append("O valor continua nulo: escrever texto em uma coluna numérica alteraria o tipo de armazenamento e poderia prejudicar cálculos posteriores. A decisão será registrada.")
            _keep(t, plan, column, targets, old)

    elif method == "keep_missing":
        plan.op_type = "keep_missing"
        plan.requires_justification = not quant
        _keep(t, plan, column, targets, old)

    _post_checks(plan, prof)
    return plan


def _keep(t: TableCtx, plan: Plan, column: str, targets: list[int], old: dict[int, str]) -> None:
    plan.exceptions = [{"row": t.rows[i], "column": column, "category": "valores_ausentes"} for i in targets]


def _post_checks(plan: Plan, prof: dict[str, Any]) -> None:
    if prof["pct_missing"] >= HIGH_MISSING_PCT and plan.changes:
        plan.warnings.append(f"Ausência elevada ({pct_text(prof['pct_missing'])}): a imputação pode introduzir viés.")
    if plan.unresolved:
        plan.warnings.append(f"{len(plan.unresolved)} registro(s) não puderam ser tratados por este método e permanecerão ausentes: linhas {', '.join(map(str, plan.unresolved[:10]))}{'…' if len(plan.unresolved) > 10 else ''}.")
        plan.requires.append("partial_application")


def _plan_constant(t, plan, column, st, prof, targets, old, params, fmt, order) -> None:
    per_row = {int(k): str(v) for k, v in (params.get("values") or {}).items()}
    value = str(params.get("value", "")).strip()
    if not per_row and not value:
        plan.errors.append("Informe o valor de preenchimento.")
        return
    if st == "identifier" and len(targets) > 1 and not per_row:
        plan.warnings.append("Usar o mesmo valor em vários registros criará identificadores repetidos.")
        plan.requires.append("identifier_duplicates")
    date_fmt = detect_date_format(t.df[column], t.markers) if st == "temporal" else None
    for i in targets:
        raw = per_row.get(t.rows[i], value).strip()
        if not raw:
            plan.errors.append(f"Informe um valor para a linha {t.rows[i]}.")
            continue
        new = raw
        if st in QUANT:
            n = parse_number(raw, "auto")
            if n is None:
                if "type_change" not in plan.requires:
                    plan.requires.append("type_change")
                    plan.warnings.append("O valor informado não é numérico. Inserir texto em uma coluna numérica altera o tipo de armazenamento e pode prejudicar cálculos e a análise exploratória.")
            elif st == "quant_discrete" and not float(n).is_integer():
                plan.errors.append("Esta variável é discreta: informe um número inteiro.")
            else:
                if prof.get("non_negative") and n < 0 and "domain" not in plan.requires:
                    plan.requires.append("domain")
                    plan.warnings.append("O valor é negativo, mas todos os valores observados são não negativos.")
        elif st == "temporal":
            d = parse_date(raw)
            if d is None:
                plan.errors.append(f"«{raw}» não é uma data válida.")
                continue
            new = d.strftime(date_fmt)
        elif st == "ordinal" and order and raw not in order:
            plan.warnings.append(f"«{raw}» não pertence à ordem definida para esta variável ordinal.")
        plan.changes.append(Change(t.rows[i], column, old[i], new))


def _group_stat(values, statistic: str, discrete_fmt, qual: bool, order):
    if qual:
        return str(mode_of(values, order))
    x = values.astype(float)
    v = {"mean": x.mean, "median": x.median}.get(statistic)
    if v is not None:
        return discrete_fmt(float(v()))
    counts = x.value_counts()
    return discrete_fmt(float(counts[counts == counts.max()].index.min()))


def _plan_group(t, plan, column, st, targets, old, params, fmt, nums, valid_raw, order) -> None:
    group_by = [g for g in (params.get("group_by") or []) if g]
    if not group_by:
        plan.errors.append("Escolha ao menos uma coluna de agrupamento.")
        return
    bad = [g for g in group_by if g not in t.df.columns or g == column]
    if bad:
        plan.errors.append(f"Coluna(s) de agrupamento inválida(s): {', '.join(bad)}.")
        return
    qual = st in QUALITATIVE
    statistic = "mode" if qual else params.get("statistic", "median")
    if statistic not in ("mean", "median", "mode"):
        plan.errors.append("Estatística de grupo inválida (use média, mediana ou moda).")
        return
    min_size = max(1, int(params.get("min_group_size") or MIN_GROUP))
    keys = pd.concat([t.df[g].str.strip() for g in group_by], axis=1)
    key_ok = pd.concat([~missing_mask(t.df[g], t.markers) for g in group_by], axis=1).all(axis=1)
    valid_vals = nums if not qual else valid_raw
    frame = pd.DataFrame({"v": valid_vals}).join(keys[key_ok].apply(tuple, axis=1).rename("k"), how="inner")
    groups = {k: g["v"] for k, g in frame.groupby("k")}
    cache: dict[tuple, Optional[str]] = {}
    plan.parameters.update(statistic=statistic, group_by=group_by, min_group_size=min_size)
    fb_text = None
    fallback = params.get("fallback")
    if fallback:
        if fallback in ("mean", "median", "mode"):
            fb_text = _group_stat(valid_vals, "mode" if qual else fallback, fmt if not qual else None, qual, order)
        elif fallback == "constant":
            fb_text = str(params.get("fallback_value", "")).strip() or None
        if fb_text is None:
            plan.errors.append("Informe um valor para a alternativa (fallback).")
            return
    for i in targets:
        if not key_ok.iloc[i]:
            plan.unresolved.append(t.rows[i])
            continue
        k = tuple(keys.iloc[i])
        if k not in cache:
            vals = groups.get(k)
            cache[k] = _group_stat(vals, statistic, fmt, qual, order) if vals is not None and len(vals) >= min_size else None
        if cache[k] is None:
            plan.unresolved.append(t.rows[i])
        else:
            plan.changes.append(Change(t.rows[i], column, old[i], cache[k], "grupo: " + " / ".join(map(str, k))))
    if plan.unresolved and fb_text is not None:
        pos = {r: i for i, r in enumerate(t.rows)}
        for r in plan.unresolved:
            plan.changes.append(Change(r, column, old[pos[r]], fb_text, f"alternativa ({fallback}): grupo com poucas observações"))
        plan.notes.append(f"{len(plan.unresolved)} registro(s) em grupos com menos de {min_size} observações receberam a alternativa escolhida ({fallback}).")
        plan.unresolved = []
    elif plan.unresolved:
        plan.warnings.append(f"Grupos com menos de {min_size} observações válidas (ou sem valor de agrupamento): escolha uma alternativa (média/mediana/moda globais ou valor fixo) para esses registros, ou aplique apenas aos demais.")


def _order_key(series: pd.Series, info: dict, markers: list[str], decimal: str) -> pd.Series:
    if info["stat_type"] == "temporal":
        return series.map(lambda v: (parse_date(v).toordinal() if parse_date(v) else np.nan))
    mode = infer_decimal_mode(series, decimal)
    return series.map(lambda v: parse_number(v, mode) if parse_number(v, mode) is not None else np.nan)


def _plan_interpolate(t, plan, column, targets, old, params, fmt, nums) -> None:
    order_by = params.get("order_by")
    if not order_by or order_by not in t.df.columns or order_by == column:
        plan.errors.append("Interpolação exige uma coluna de ordenação válida (data ou número).")
        return
    info = t.stat[order_by]
    if info["stat_type"] not in ("temporal",) + QUANT:
        plan.errors.append("A coluna de ordenação deve ser uma data ou uma variável numérica.")
        return
    key = _order_key(t.df[order_by].str.strip(), info, t.markers, t.decimal)
    if key.notna().sum() < 2:
        plan.errors.append("A coluna de ordenação não possui valores válidos suficientes.")
        return
    group_by = [g for g in (params.get("group_by") or []) if g and g in t.df.columns]
    gkey = t.df[group_by].apply(lambda r: tuple(v.strip() for v in r), axis=1) if group_by else pd.Series([()] * len(t.df), index=t.df.index)
    plan.parameters.update(order_by=order_by, group_by=group_by)
    plan.warnings.append("A interpolação linear supõe que os registros formam uma sequência ordenada de um mesmo fenômeno. Valores nas pontas da série não são extrapolados.")
    ys_all = pd.Series(nums)
    for g, idx in gkey.groupby(gkey).groups.items():
        idx = list(idx)
        known = [i for i in idx if i in ys_all.index and not np.isnan(key.loc[i])]
        want = [i for i in targets if i in set(idx)]
        if not want:
            continue
        if len(known) < 2:
            plan.unresolved.extend(t.rows[i] for i in want)
            continue
        known.sort(key=lambda i: key.loc[i])
        xs = np.array([key.loc[i] for i in known], dtype=float)
        ys = np.array([ys_all.loc[i] for i in known], dtype=float)
        for i in want:
            x = key.loc[i]
            if np.isnan(x) or x < xs[0] or x > xs[-1]:
                plan.unresolved.append(t.rows[i])
            else:
                plan.changes.append(Change(t.rows[i], column, old[i], fmt(float(np.interp(x, xs, ys))), f"interpolado por {order_by}"))
    plan.changes.sort(key=lambda c: c.row)
    plan.unresolved.sort()
