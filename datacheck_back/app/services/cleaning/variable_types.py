"""Tipo ESTATÍSTICO das variáveis (não o tipo de armazenamento).

Heurísticas transparentes: cada classificação devolve as razões usadas e pode ser
substituída manualmente pelo usuário. Códigos e documentos (CPF, CEP, IBGE…) são
identificadores mesmo quando só têm dígitos.
"""
from __future__ import annotations

import re
from typing import Any, Optional

import pandas as pd

from app.core.parsing import missing_mask, parse_date, parse_number

STAT_TYPES = {
    "quant_discrete": "Quantitativa discreta",
    "quant_continuous": "Quantitativa contínua",
    "nominal": "Qualitativa nominal",
    "ordinal": "Qualitativa ordinal",
    "temporal": "Data ou temporal",
    "identifier": "Identificador",
}
QUANT = ("quant_discrete", "quant_continuous")
QUALITATIVE = ("nominal", "ordinal")

_ID_NAME = re.compile(
    r"(^|[^a-zà-ú])(id|cod|cód|codigo|código|cpf|cnpj|cep|ibge|matricula|matrícula|protocolo|inscricao|inscrição|nis|rg)([^a-zà-ú]|$)",
    re.I)
THRESHOLD = 0.9
MIN_UNIQUE_ID = 20


def _valid(series: pd.Series, markers: list[str]) -> pd.Series:
    return series[~missing_mask(series, markers)].str.strip()


def classify_column(series: pd.Series, name: str, markers: list[str], decimal: str = "auto",
                    override: Optional[dict] = None) -> dict[str, Any]:
    valid = _valid(series, markers)
    n_valid, n_unique = len(valid), int(valid.nunique())
    base = {"name": name, "n_valid": n_valid, "n_missing": int(len(series) - n_valid), "n_unique": n_unique}

    if override and override.get("type") in STAT_TYPES:
        out = {**base, "stat_type": override["type"], "source": "manual", "reasons": ["Definido manualmente pelo usuário."]}
        if override["type"] == "ordinal":
            out["order"] = list(override.get("order") or [])
        return _finish(out)

    def done(t: str, *reasons: str) -> dict[str, Any]:
        return _finish({**base, "stat_type": t, "source": "auto", "reasons": list(reasons)})

    if n_valid == 0:
        return done("nominal", "A coluna não possui valores válidos; não há como inferir o tipo.")

    counts = valid.value_counts()
    dates = sum(c for v, c in counts.items() if parse_date(v) is not None)
    nums = {v: parse_number(v, decimal) for v in counts.index}
    n_num = sum(c for v, c in counts.items() if nums[v] is not None)
    unique_ratio = n_unique / n_valid
    name_hint = bool(_ID_NAME.search(name))

    if dates / n_valid >= THRESHOLD:
        return done("temporal", f"{dates / n_valid:.0%} dos valores são datas válidas.")

    if n_num / n_valid >= THRESHOLD:
        digits = valid.str.fullmatch(r"\d+")
        fixed_len = digits.all() and valid.str.len().nunique() == 1 and valid.str.len().iloc[0] >= 5
        if name_hint:
            return done("identifier", "O nome da coluna sugere código ou identificador.")
        if fixed_len:
            return done("identifier", "Todos os valores são sequências numéricas de mesmo tamanho (padrão de código/documento).")
        all_int = all(nums[v] is None or (nums[v].is_integer() and not any(ch in v for ch in ".,eE")) for v in counts.index)
        if all_int and unique_ratio >= 0.98 and n_valid >= MIN_UNIQUE_ID:
            return done("identifier", "Quase todos os valores são inteiros distintos (comportamento de identificador).")
        if all_int:
            return done("quant_discrete", "Valores numéricos inteiros (contagens/quantidades).")
        return done("quant_continuous", "Valores numéricos com casas decimais.")

    if name_hint:
        return done("identifier", "O nome da coluna sugere código ou identificador.")
    if unique_ratio >= THRESHOLD and n_valid >= MIN_UNIQUE_ID:
        return done("identifier", "Quase todos os textos são distintos (identificador ou texto livre).")
    return done("nominal", f"Texto com {n_unique} categoria(s) distinta(s).")


def _finish(out: dict[str, Any]) -> dict[str, Any]:
    out["label"] = STAT_TYPES[out["stat_type"]]
    return out


def classify_all(df: pd.DataFrame, markers: list[str], decimal: str, overrides: Optional[dict]) -> list[dict[str, Any]]:
    overrides = overrides or {}
    return [classify_column(df[c], c, markers, decimal, overrides.get(c)) for c in df.columns]
