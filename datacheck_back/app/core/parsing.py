"""Funções puras de interpretação de texto: números, datas e valores ausentes.

Os dados são sempre tratados como texto. Nada do conteúdo é avaliado ou executado.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Callable, Iterable, Optional

import pandas as pd

DEFAULT_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"]

_NUM_RE = re.compile(r"^[+-]?(\d+([.,]\d+)?|[.,]\d+)([eE][+-]?\d+)?$")
# 1.234,56 ou 1.234.567 (milhar com ponto). "1.234" sozinho é tratado como decimal.
_PT_THOUSANDS_RE = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+,\d+$|^[+-]?\d{1,3}(\.\d{3}){2,}$")
_TIME_SUFFIX_RE = re.compile(r"[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")


_COMMA_RE = re.compile(r"^[+-]?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$")
_DOT_RE = re.compile(r"^[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")


def parse_number(text: str, mode: str = "auto") -> Optional[float]:
    """Converte texto em número. mode: auto (aceita ponto ou vírgula), comma (pt-BR) ou dot (en-US)."""
    s = text.strip()
    if not s:
        return None
    if mode == "comma":
        if not _COMMA_RE.match(s):
            return None
        s = s.replace(".", "").replace(",", ".")
    elif mode == "dot":
        if not _DOT_RE.match(s):
            return None
        s = s.replace(",", "")
    elif _PT_THOUSANDS_RE.match(s):
        s = s.replace(".", "").replace(",", ".")
    elif _NUM_RE.match(s):
        s = s.replace(",", ".")
    else:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    return None if math.isinf(value) or math.isnan(value) else value


def parse_date(text: str, formats: Optional[Iterable[str]] = None) -> Optional[date]:
    """Converte texto em data usando formatos estritos (rejeita datas inexistentes)."""
    s = text.strip()
    if not s:
        return None
    fmts = list(formats) if formats else DEFAULT_DATE_FORMATS
    candidates = [s]
    stripped = _TIME_SUFFIX_RE.sub("", s)
    if stripped != s:
        candidates.append(stripped)
    for candidate in candidates:
        for fmt in fmts:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def missing_mask(series: pd.Series, markers: Iterable[str], treat_blank: bool = True) -> pd.Series:
    """Máscara de valores ausentes: vazio/espaços e marcadores (sem diferenciar caixa)."""
    stripped = series.str.strip()
    mask = pd.Series(False, index=series.index)
    if treat_blank:
        mask |= stripped == ""
    lowered = {m.strip().lower() for m in markers if m.strip()}
    if lowered:
        mask |= stripped.str.lower().isin(lowered)
    return mask


def map_unique(series: pd.Series, fn: Callable[[str], object]) -> pd.Series:
    """Aplica fn apenas aos valores distintos e espalha o resultado (mais rápido)."""
    mapping = {v: fn(v) for v in series.unique()}
    return series.map(mapping)


def display_value(raw: str, limit: int = 200) -> str:
    if raw == "":
        return "(vazio)"
    if raw.strip() == "":
        return "(espaços em branco)"
    return raw if len(raw) <= limit else raw[: limit - 1] + "…"


def fmt_number(value: float) -> str:
    return f"{value:g}"
