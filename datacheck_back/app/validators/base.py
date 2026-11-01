from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

import pandas as pd

from app.schemas.validation import AnalysisConfig
from app.core.parsing import display_value, parse_number


@dataclass
class Issue:
    row: int  # número da linha no arquivo original (cabeçalho incluído na contagem)
    column: str
    value: str
    category: str
    severity: str  # critical | warning | info
    description: str
    suggestion: str


@dataclass
class RuleContext:
    first_data_line: int
    markers: list[str]
    today: date
    decimal: str = "auto"
    row_numbers: Optional[Sequence[int]] = None  # linha original de cada registro (versões tratadas)

    def line_of(self, idx: int) -> int:
        return int(self.row_numbers[idx]) if self.row_numbers is not None else self.first_data_line + int(idx)

    def number(self, text: str) -> Optional[float]:
        return parse_number(text, self.decimal)

    def issue(self, idx: int, column: str, raw: str, category: str, severity: str,
              description: str, suggestion: str) -> Issue:
        return Issue(
            row=self.line_of(idx),
            column=column,
            value=display_value(raw),
            category=category,
            severity=severity,
            description=description,
            suggestion=suggestion,
        )


@dataclass
class RuleOutput:
    issues: list[Issue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class Rule(ABC):
    """Uma verificação independente. Nunca altera o DataFrame recebido."""

    code: str

    @abstractmethod
    def is_active(self, config: AnalysisConfig) -> bool: ...

    def referenced_columns(self, config: AnalysisConfig) -> list[str]:
        return []

    def validate(self, config: AnalysisConfig) -> None:
        """Valida a configuração (além da existência das colunas)."""

    @abstractmethod
    def run(self, df: pd.DataFrame, config: AnalysisConfig, ctx: RuleContext) -> RuleOutput: ...
