"""Estruturas comuns aos planos de tratamento (prévia → confirmação → aplicação)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


@dataclass
class Change:
    row: int  # linha original no arquivo enviado
    column: str
    old: str
    new: str
    note: str = ""


@dataclass
class Plan:
    action: str
    op_type: str
    method: str
    column: Optional[str] = None
    changes: list[Change] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)       # [{row, values:{coluna: valor}}]
    exceptions: list[dict] = field(default_factory=list)     # decisões "manter" registradas
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)        # confirmações explícitas exigidas ao aplicar
    unresolved: list[int] = field(default_factory=list)      # linhas que o método não conseguiu tratar
    notes: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_justification: bool = False

    @property
    def n_rows(self) -> int:
        return len({c.row for c in self.changes} | {r["row"] for r in self.removed} | {e["row"] for e in self.exceptions})


@dataclass
class TableCtx:
    df: pd.DataFrame
    rows: list[int]                 # linha original de cada registro
    markers: list[str]
    decimal: str                    # auto | comma | dot (configuração da análise)
    stat: dict[str, dict]           # classificação estatística por coluna

    def __post_init__(self) -> None:
        self.pos = {r: i for i, r in enumerate(self.rows)}

    def positions(self, rows: list[int]) -> tuple[list[int], list[int]]:
        """(posições encontradas, linhas inexistentes)."""
        found, missing = [], []
        for r in rows:
            (found if r in self.pos else missing).append(self.pos[r] if r in self.pos else r)
        return found, missing
