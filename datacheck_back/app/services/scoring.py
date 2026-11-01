"""DataCheck Score (0–100).

    Score = 100 × (1 − linhas distintas afetadas ÷ total de linhas)

As linhas afetadas são a união das linhas com ao menos uma ocorrência em qualquer regra
ativa; uma linha com vários problemas conta uma única vez.
"""
from __future__ import annotations

from typing import Optional

FORMULA = "Score = 100 × (1 − linhas distintas afetadas ÷ total de linhas)."
DISCLAIMER = (
    "O score representa apenas a cobertura das regras executadas. Ele não garante que os dados "
    "estejam completamente corretos: problemas que nenhuma regra cobre não são considerados."
)


def label_for(score: Optional[float]) -> str:
    if score is None:
        return "Indisponível"
    if score >= 90:
        return "Excelente"
    if score >= 75:
        return "Boa"
    if score >= 50:
        return "Requer atenção"
    return "Crítica"


def compute_score(total_rows: int, affected_rows: int) -> dict:
    # Base vazia: sem divisão por zero e sem nota.
    value: Optional[float] = None
    if total_rows > 0:
        value = round(max(0.0, 100 * (1 - affected_rows / total_rows)), 1)
    return {"value": value, "label": label_for(value), "formula": FORMULA, "disclaimer": DISCLAIMER,
            "affected_rows": affected_rows, "rows": total_rows}
