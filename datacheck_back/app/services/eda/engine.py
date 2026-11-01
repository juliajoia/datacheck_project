"""Motor de estatística descritiva e exploratória (Pandas/NumPy/SciPy) sobre a versão tratada.

Só calcula o que o tipo estatístico da variável permite: nenhuma média de variável nominal e
nenhuma correlação com identificadores. Todo resultado vem dos dados; os textos descritivos
são derivados dos números calculados.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.core.parsing import missing_mask, parse_date
from app.schemas.eda import EdaConfig
from app.services.cleaning.stats import infer_decimal_mode, iqr_bounds, numeric_values
from app.services.cleaning.variable_types import QUALITATIVE, QUANT

MAX_CATEGORIES = 15
MAX_HIST_BINS = 30
MIN_KDE = 30
SCATTER_POINTS = 800
MAX_SCATTER_PAIRS = 3


def _f(x: Any, nd: int = 6) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if math.isfinite(v) else None


def pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "%"


def num(x: Optional[float], nd: int = 2) -> str:
    return "—" if x is None else f"{x:,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _quant_values(df: pd.DataFrame, col: str, markers: list[str], decimal: str) -> pd.Series:
    s = df[col]
    return numeric_values(s, markers, infer_decimal_mode(s[~missing_mask(s, markers)].str.strip(), decimal))


# ---------------------------------------------------------------- aplicabilidade

def applicability(stat: dict[str, dict], n_rows: int) -> dict[str, Any]:
    """Quais seções se aplicam a quais colunas (e por que não), para a interface."""
    cols = []
    for name, info in stat.items():
        t, nv = info["stat_type"], info["n_valid"]
        quant, qual = t in QUANT, t in QUALITATIVE
        why_not_num = None if quant else {"identifier": "Identificadores não são variáveis quantitativas.", "temporal": "Datas não possuem média/desvio nesta análise.",
                                          "nominal": "Variável qualitativa: média não se aplica.", "ordinal": "Variável qualitativa: média não se aplica."}[t]
        usable = nv >= 2
        cols.append({"name": name, "stat_type": t, "label": info["label"], "n_valid": nv,
                     "descriptive": {"ok": quant and usable, "reason": why_not_num or (None if usable else "Valores válidos insuficientes.")},
                     "frequencies": {"ok": qual and usable, "reason": None if qual and usable else "Frequências se aplicam a variáveis qualitativas."},
                     "distributions": {"ok": (quant or qual) and usable, "reason": None if (quant or qual) and usable else "Não se aplica a este tipo de variável."},
                     "correlation": {"ok": quant and nv >= 3, "reason": None if quant and nv >= 3 else ("Identificadores não entram em correlações." if t == "identifier" else "Exige variável quantitativa com ao menos 3 valores.")},
                     "outliers": {"ok": quant and nv >= 4, "reason": None if quant and nv >= 4 else "Exige variável quantitativa com ao menos 4 valores."},
                     "temporal": {"ok": t == "temporal" and usable, "reason": None if t == "temporal" else "Exige uma coluna de datas."}})
    has_q = sum(c["correlation"]["ok"] for c in cols)
    return {"columns": cols, "sections": {
        "overview": {"ok": True}, "missing": {"ok": True}, "treatment": {"ok": True}, "charts": {"ok": True},
        "descriptive": {"ok": any(c["descriptive"]["ok"] for c in cols), "reason": "Não há variáveis quantitativas." if not any(c["descriptive"]["ok"] for c in cols) else None},
        "frequencies": {"ok": any(c["frequencies"]["ok"] for c in cols), "reason": "Não há variáveis qualitativas." if not any(c["frequencies"]["ok"] for c in cols) else None},
        "distributions": {"ok": any(c["distributions"]["ok"] for c in cols), "reason": "Não há variáveis analisáveis." if not any(c["distributions"]["ok"] for c in cols) else None},
        "correlation": {"ok": has_q >= 2, "reason": None if has_q >= 2 else "São necessárias ao menos 2 variáveis quantitativas."},
        "outliers": {"ok": any(c["outliers"]["ok"] for c in cols), "reason": "Não há variáveis quantitativas." if not any(c["outliers"]["ok"] for c in cols) else None},
        "temporal": {"ok": any(c["temporal"]["ok"] for c in cols), "reason": "Não há coluna de datas válida." if not any(c["temporal"]["ok"] for c in cols) else None}}}


# ---------------------------------------------------------------- blocos

def descriptive(x: pd.Series, n_missing: int, percentiles: list[float]) -> dict[str, Any]:
    n = len(x)
    out: dict[str, Any] = {"n_valid": n, "n_missing": n_missing, "warnings": []}
    if n == 0:
        out["warnings"].append("Sem observações válidas.")
        return out
    mean = float(x.mean())
    sd = float(x.std()) if n > 1 else None
    counts = x.value_counts()
    modes = counts[counts == counts.max()].index.tolist()
    q1, q3 = float(x.quantile(0.25)), float(x.quantile(0.75))
    constant = x.nunique() == 1
    out.update(
        mean=_f(mean), median=_f(x.median()), mode=_f(min(modes)) if counts.max() > 1 else None, mode_count=int(counts.max()) if counts.max() > 1 else 0,
        n_modes=len(modes) if counts.max() > 1 else 0, min=_f(x.min()), max=_f(x.max()), range=_f(x.max() - x.min()),
        variance=_f(x.var()) if n > 1 else None, std=_f(sd), cv=_f(abs(sd / mean)) if sd is not None and mean != 0 else None,
        q1=_f(q1), q3=_f(q3), iqr=_f(q3 - q1), percentiles={f"p{p:g}": _f(x.quantile(p / 100)) for p in percentiles},
        skewness=_f(x.skew()) if n >= 3 and not constant else None, kurtosis=_f(x.kurt()) if n >= 4 and not constant else None)
    if constant:
        out["warnings"].append("Coluna constante: não há variação (desvio padrão 0; assimetria, curtose e coeficiente de variação não se aplicam).")
    if n < 10:
        out["warnings"].append(f"Amostra pequena (n={n}): as medidas são pouco estáveis.")
    if mean == 0 and not constant:
        out["warnings"].append("Média igual a zero: o coeficiente de variação não se aplica.")
    return out


def frequencies(s: pd.Series, markers: list[str], order: Optional[list[str]]) -> dict[str, Any]:
    mask = missing_mask(s, markers)
    v = s[~mask].str.strip()
    n = len(v)
    out: dict[str, Any] = {"n_valid": n, "n_missing": int(mask.sum()), "n_unique": int(v.nunique()), "ordered": bool(order), "top": []}
    if n == 0:
        return out
    counts = v.value_counts()
    if order:
        idx = [c for c in order if c in counts.index] + sorted(c for c in counts.index if c not in order)
        counts = counts.reindex(idx)
    else:
        counts = counts.sort_values(ascending=False, kind="stable")
    tied = counts[counts == counts.max()].index.tolist()
    out["mode"] = str(tied[0] if order else sorted(tied)[0])  # empate: primeiro na ordem definida (ordinal) ou menor valor
    out["mode_pct"] = _f(100 * counts.max() / n, 2)
    out["top"] = [{"value": str(k), "count": int(c), "pct": _f(100 * c / n, 2)} for k, c in counts.head(MAX_CATEGORIES).items()]
    out["other"] = {"count": int(counts.iloc[MAX_CATEGORIES:].sum()), "n_categories": int(max(0, len(counts) - MAX_CATEGORIES))} if len(counts) > MAX_CATEGORIES else None
    return out


def distribution(x: pd.Series) -> dict[str, Any]:
    n = len(x)
    out: dict[str, Any] = {"n": n, "histogram": None, "boxplot": None, "density": None}
    if n == 0:
        return out
    arr = x.to_numpy(dtype=float)
    uniq = np.unique(arr)
    if len(uniq) == 1:
        out["histogram"] = {"bins": [{"x0": float(uniq[0]), "x1": float(uniq[0]), "count": n}], "n": n, "discrete": True}
    elif len(uniq) <= 12:
        out["histogram"] = {"bins": [{"x0": float(u), "x1": float(u), "count": int((arr == u).sum())} for u in uniq], "n": n, "discrete": True}
    else:
        k = int(min(MAX_HIST_BINS, max(5, math.ceil(math.log2(n) + 1))))
        counts, edges = np.histogram(arr, bins=k)
        out["histogram"] = {"bins": [{"x0": float(edges[i]), "x1": float(edges[i + 1]), "count": int(counts[i])} for i in range(k)], "n": n, "discrete": False}
    q1, med, q3 = (float(x.quantile(q)) for q in (0.25, 0.5, 0.75))
    iqr = q3 - q1
    lo_f, hi_f = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = arr[(arr >= lo_f) & (arr <= hi_f)]
    out["boxplot"] = {"min": float(arr.min()), "q1": q1, "median": med, "q3": q3, "max": float(arr.max()),
                      "whisker_low": float(inside.min()) if len(inside) else q1, "whisker_high": float(inside.max()) if len(inside) else q3,
                      "outliers": [float(v) for v in arr[(arr < lo_f) | (arr > hi_f)][:50]], "n_outliers": int(((arr < lo_f) | (arr > hi_f)).sum())}
    if n >= MIN_KDE and len(uniq) > 12 and arr.std() > 0:
        try:
            from scipy.stats import gaussian_kde
            grid = np.linspace(arr.min(), arr.max(), 80)
            out["density"] = {"x": [float(g) for g in grid], "y": [float(v) for v in gaussian_kde(arr)(grid)]}
        except Exception:  # matriz singular etc.: a densidade é opcional
            out["density"] = None
    return out


def strength(r: float) -> str:
    a = abs(r)
    return "desprezível" if a < 0.1 else "fraca" if a < 0.3 else "moderada" if a < 0.5 else "forte" if a < 0.7 else "muito forte"


def correlation(df_num: pd.DataFrame, method: str) -> dict[str, Any]:
    excluded, cols = [], []
    for c in df_num.columns:
        s = df_num[c].dropna()
        if len(s) < 3:
            excluded.append({"column": c, "reason": "menos de 3 observações válidas"})
        elif s.nunique() < 2:
            excluded.append({"column": c, "reason": "coluna constante (sem variação)"})
        else:
            cols.append(c)
    out: dict[str, Any] = {"method": method, "columns": cols, "matrix": [], "n_matrix": [], "pairs": [], "excluded": excluded,
                           "warning": "Correlação não implica causalidade. O coeficiente descreve associação entre os valores observados."}
    if len(cols) < 2:
        return out
    d = df_num[cols]
    corr = d.corr(method=method, min_periods=3)
    valid = d.notna().astype(int)
    n = valid.T.dot(valid)
    out["matrix"] = [[_f(corr.iloc[i, j], 4) for j in range(len(cols))] for i in range(len(cols))]
    out["n_matrix"] = [[int(n.iloc[i, j]) for j in range(len(cols))] for i in range(len(cols))]
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if math.isfinite(r):
                out["pairs"].append({"a": cols[i], "b": cols[j], "r": _f(r, 4), "n": int(n.iloc[i, j]), "strength": strength(r),
                                     "direction": "positiva" if r > 0 else "negativa" if r < 0 else "nula"})
    out["pairs"].sort(key=lambda p: -abs(p["r"]))
    return out


def scatter_pairs(df_num: pd.DataFrame, pairs: list[dict]) -> list[dict[str, Any]]:
    out = []
    for p in pairs[:MAX_SCATTER_PAIRS]:
        d = df_num[[p["a"], p["b"]]].dropna()
        if len(d) > SCATTER_POINTS:
            d = d.sample(SCATTER_POINTS, random_state=0)  # amostra determinística apenas para o gráfico
        out.append({"x": p["a"], "y": p["b"], "r": p["r"], "n": p["n"], "points": [[float(a), float(b)] for a, b in d.itertuples(index=False)]})
    return out


def outliers_block(x: pd.Series) -> dict[str, Any]:
    b = iqr_bounds(x)
    if b is None:
        return {"method": "IQR 1,5", "available": False, "reason": "intervalo interquartil nulo ou poucas observações"}
    lo, hi = b
    mask = (x < lo) | (x > hi)
    return {"method": "IQR 1,5", "available": True, "lower": _f(lo), "upper": _f(hi), "count": int(mask.sum()), "pct": _f(100 * mask.mean(), 2),
            "examples": [_f(v) for v in x[mask].sort_values(key=lambda s: -abs(s - x.median())).head(10)]}


def temporal(df: pd.DataFrame, stat: dict, cfg: EdaConfig, markers: list[str], decimal: str) -> Optional[dict[str, Any]]:
    col = cfg.temporal.date_column or next((c for c, i in stat.items() if i["stat_type"] == "temporal"), None)
    if not col or col not in df.columns:
        return None
    mask = ~missing_mask(df[col], markers)
    dates = df[col][mask].map(lambda v: parse_date(v))
    ok = dates.notna()
    if ok.sum() < 2:
        return {"date_column": col, "available": False, "reason": "Há menos de 2 datas válidas."}
    d = pd.to_datetime(dates[ok].map(lambda x: x.isoformat()))
    freq = cfg.temporal.frequency
    period = d.dt.to_period(freq)
    counts = period.value_counts().sort_index()
    full = pd.period_range(counts.index.min(), counts.index.max(), freq=freq)
    series = [{"period": str(p), "count": int(counts.get(p, 0))} for p in full]
    gaps = [str(p) for p in full if counts.get(p, 0) == 0]
    out: dict[str, Any] = {"date_column": col, "available": True, "frequency": freq, "n_dates": int(ok.sum()), "n_invalid_or_missing": int(len(df) - ok.sum()),
                           "start": str(d.min().date()), "end": str(d.max().date()), "count_series": series[:2000], "gaps": gaps[:100], "n_gaps": len(gaps), "value_series": []}
    value_cols = cfg.temporal.value_columns or [c for c, i in stat.items() if i["stat_type"] in QUANT][:2]
    for vc in value_cols[:3]:
        if vc not in df.columns or stat.get(vc, {}).get("stat_type") not in QUANT:
            continue
        v = _quant_values(df, vc, markers, decimal)
        frame = pd.DataFrame({"v": v}).join(period.rename("p"), how="inner")
        if frame.empty:
            continue
        g = frame.groupby("p")["v"].agg(["mean", "count"])
        out["value_series"].append({"column": vc, "points": [{"period": str(p), "mean": _f(r["mean"]), "n": int(r["count"])} for p, r in g.iterrows()][:2000]})
    return out


# ---------------------------------------------------------------- relatório completo

def build(df: pd.DataFrame, stat: dict[str, dict], cfg: EdaConfig, markers: list[str], decimal: str,
          treatment: dict[str, Any]) -> dict[str, Any]:
    """Calcula as seções pedidas. Retorna o JSON salvo em eda_reports.summary_statistics."""
    n_rows = len(df)
    chosen = [c for c in (cfg.columns or list(df.columns)) if c in df.columns]
    quant = [c for c in chosen if stat[c]["stat_type"] in QUANT and stat[c]["n_valid"] >= 2]
    qual = [c for c in chosen if stat[c]["stat_type"] in QUALITATIVE and stat[c]["n_valid"] >= 2]
    sec = set(cfg.sections)
    qv = {c: _quant_values(df, c, markers, decimal) for c in quant}
    out: dict[str, Any] = {"n_rows": n_rows, "n_columns": int(df.shape[1]), "sections": [s for s in cfg.sections], "skipped": {}}

    counts: dict[str, int] = {}
    for c in df.columns:
        counts[stat[c]["label"]] = counts.get(stat[c]["label"], 0) + 1
    out["overview"] = {"rows": n_rows, "columns": int(df.shape[1]), "type_counts": counts,
                       "columns_info": [{"name": c, "stat_type": stat[c]["stat_type"], "label": stat[c]["label"], "n_valid": stat[c]["n_valid"],
                                         "n_missing": stat[c]["n_missing"], "pct_missing": _f(100 * stat[c]["n_missing"] / n_rows, 2) if n_rows else 0,
                                         "n_unique": stat[c]["n_unique"]} for c in df.columns]}
    if "descriptive" in sec:
        if quant:
            out["descriptive"] = [{"column": c, **descriptive(qv[c], stat[c]["n_missing"], cfg.percentiles)} for c in quant]
        else:
            out["skipped"]["descriptive"] = "Não há variáveis quantitativas selecionáveis."
    if "frequencies" in sec:
        if qual:
            out["frequencies"] = [{"column": c, **frequencies(df[c], markers, stat[c].get("order"))} for c in qual]
        else:
            out["skipped"]["frequencies"] = "Não há variáveis qualitativas selecionáveis."
    if "distributions" in sec or "charts" in sec:
        dist = [{"column": c, "kind": "quantitative", **distribution(qv[c])} for c in quant]
        dist += [{"column": c, "kind": "qualitative", "frequencies": frequencies(df[c], markers, stat[c].get("order"))} for c in qual]
        out["distributions"] = dist
    if "correlation" in sec:
        if len(quant) >= 2:
            num_df = pd.DataFrame({c: qv[c] for c in quant}).reindex(df.index)
            corr = correlation(num_df, cfg.correlation_method)
            out["correlation"] = corr
            out["scatter"] = scatter_pairs(num_df, corr["pairs"]) if "charts" in sec else []
        else:
            out["skipped"]["correlation"] = "São necessárias ao menos 2 variáveis quantitativas."
    if "outliers" in sec:
        out["outliers"] = [{"column": c, **outliers_block(qv[c])} for c in quant]
        if not quant:
            out["skipped"]["outliers"] = "Não há variáveis quantitativas selecionáveis."
    if "temporal" in sec:
        t = temporal(df, stat, cfg, markers, decimal)
        if t is None:
            out["skipped"]["temporal"] = "Não há coluna de datas válida."
        else:
            out["temporal"] = t
    miss_cols = [{"column": c, "n_missing": stat[c]["n_missing"], "pct": _f(100 * stat[c]["n_missing"] / n_rows, 2) if n_rows else 0} for c in df.columns]
    any_missing = pd.concat([missing_mask(df[c], markers) for c in df.columns], axis=1).any(axis=1)
    out["missing"] = {"columns": miss_cols, "rows_with_missing": int(any_missing.sum()), "complete_rows": int((~any_missing).sum())}
    out["treatment"] = treatment
    out["observations"] = observations(out, treatment)
    out["limitations"] = limitations(out, treatment)
    return out


def observations(r: dict[str, Any], treatment: dict[str, Any]) -> list[str]:
    obs: list[str] = []
    o = r["overview"]
    obs.append(f"A base tratada possui {o['rows']:,} registros e {o['columns']} variáveis ({', '.join(f'{v} {k.lower()}' for k, v in o['type_counts'].items())}).".replace(",", "."))
    for d in r.get("descriptive", []):
        c, sk, cv = d["column"], d.get("skewness"), d.get("cv")
        if sk is not None and abs(sk) >= 1:
            rel = "maior" if d["mean"] > d["median"] else "menor"
            obs.append(f"«{c}» tem distribuição assimétrica {'à direita' if sk > 0 else 'à esquerda'} (assimetria {num(sk)}): a média ({num(d['mean'])}) é {rel} que a mediana ({num(d['median'])}).")
        if cv is not None and cv >= 1:
            obs.append(f"«{c}» apresenta alta dispersão relativa (coeficiente de variação {pct(100 * cv)}).")
        if d.get("n_valid", 0) and d["warnings"]:
            obs.append(f"«{c}»: {d['warnings'][0]}")
    for ot in r.get("outliers", []):
        if ot.get("available") and ot["count"]:
            obs.append(f"«{ot['column']}» possui {ot['count']} valor(es) além do critério 1,5×IQR ({pct(ot['pct'])} das observações). São possíveis valores atípicos, não necessariamente erros.")
    for f in r.get("frequencies", []):
        if f.get("top") and f["mode_pct"] is not None and f["mode_pct"] >= 50:
            obs.append(f"A categoria «{f['mode']}» concentra {pct(f['mode_pct'])} dos registros válidos de «{f['column']}».")
    corr = r.get("correlation")
    if corr and corr.get("pairs"):
        p = corr["pairs"][0]
        obs.append(f"A associação {p['direction']} mais intensa entre variáveis quantitativas ocorre entre «{p['a']}» e «{p['b']}» (r = {num(p['r'])}, {p['strength']}; n = {p['n']}). Correlação não implica causalidade.")
    t = r.get("temporal")
    if t and t.get("available"):
        obs.append(f"Há {t['n_dates']} registros datados em «{t['date_column']}», de {t['start']} a {t['end']}; {t['n_gaps']} período(s) sem registros na frequência escolhida.")
    m = r["missing"]
    left = [c for c in m["columns"] if c["n_missing"]]
    if left:
        obs.append(f"Permanecem valores ausentes em {len(left)} variável(is); {m['rows_with_missing']} registro(s) têm ao menos um valor ausente.")
    if treatment.get("imputed_values"):
        obs.append(f"{treatment['imputed_values']} valor(es) foram imputados durante o tratamento; medidas de tendência central e dispersão dessas variáveis podem estar subestimando a variabilidade real.")
    return obs


def limitations(r: dict[str, Any], treatment: dict[str, Any]) -> list[str]:
    lim = ["Os resultados descrevem apenas os registros desta base; não permitem inferências sobre populações maiores.",
           "Correlação não implica causalidade.",
           "A qualidade estimada pelo DataCheck cobre somente as regras executadas, e não garante que os dados estejam totalmente corretos."]
    if treatment.get("imputed_values"):
        lim.append("Valores imputados são estimativas e foram tratados como observações; a incerteza associada não está refletida nas estatísticas.")
    if treatment.get("removed_rows"):
        lim.append(f"{treatment['removed_rows']} registro(s) foram removidos no tratamento; as estatísticas referem-se à base após essa remoção.")
    if treatment.get("exceptions_accepted"):
        lim.append(f"{treatment['exceptions_accepted']} ocorrência(s) foram mantidas como exceção por decisão do usuário.")
    return lim
