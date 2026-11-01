"""Medidas e utilitários numéricos compartilhados por tratamento e EDA."""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from app.core.parsing import map_unique, missing_mask, parse_number


def infer_decimal_mode(series: pd.Series, configured: str) -> str:
    """'comma' ou 'dot'. Em modo automático, usa o separador predominante nos valores."""
    if configured in ("comma", "dot"):
        return configured
    comma = int(series.str.contains(r"^\s*[+-]?\d+,\d+\s*$", regex=True).sum())
    dot = int(series.str.contains(r"^\s*[+-]?\d+\.\d+\s*$", regex=True).sum())
    return "comma" if comma > dot else "dot"


def numeric_values(series: pd.Series, markers: list[str], decimal: str) -> pd.Series:
    """Valores numéricos válidos (índice preservado); ausentes e não numéricos são descartados."""
    present = series[~missing_mask(series, markers)]
    return map_unique(present, lambda v: parse_number(v, decimal)).dropna().astype(float)


def decimals_of(series: pd.Series, cap: int = 6) -> int:
    best = 0
    for v in series.dropna().unique():
        s = str(v).strip().replace(",", ".")
        if "." in s and "e" not in s.lower():
            best = max(best, len(s.split(".")[1]))
    return min(best, cap)


def format_number(value: float, decimals: int, mode: str) -> str:
    text = f"{value:.{decimals}f}" if decimals > 0 else str(int(round(value)))
    return text.replace(".", ",") if mode == "comma" else text


def safe_skew(x: pd.Series) -> Optional[float]:
    if len(x) < 3 or x.nunique() < 2:
        return None
    v = float(x.skew())
    return v if math.isfinite(v) else None


def iqr_bounds(x: pd.Series, factor: float = 1.5) -> Optional[tuple[float, float]]:
    if len(x) < 4:
        return None
    q1, q3 = float(x.quantile(0.25)), float(x.quantile(0.75))
    iqr = q3 - q1
    if iqr == 0:
        return None
    return q1 - factor * iqr, q3 + factor * iqr


def mode_of(values: pd.Series, order: Optional[list[str]] = None) -> Optional[object]:
    """Valor mais frequente. Empates: menor valor (ou primeiro na ordem, se ordinal)."""
    if values.empty:
        return None
    counts = values.value_counts()
    top = counts[counts == counts.max()].index.tolist()
    if order:
        top.sort(key=lambda v: order.index(v) if v in order else len(order))
        return top[0]
    return sorted(top)[0]


def finite(x: float) -> Optional[float]:
    return float(x) if x is not None and math.isfinite(float(x)) else None


def clean_array(x: pd.Series) -> np.ndarray:
    a = x.to_numpy(dtype=float)
    return a[np.isfinite(a)]
