from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

SECTIONS = ["overview", "descriptive", "frequencies", "distributions", "correlation", "outliers", "temporal", "missing", "charts", "treatment"]
SECTION_LABELS = {
    "overview": "Resumo geral da base", "descriptive": "Estatísticas descritivas", "frequencies": "Análise de frequências",
    "distributions": "Distribuição das variáveis", "correlation": "Análise de correlação", "outliers": "Análise de valores extremos",
    "temporal": "Análise temporal", "missing": "Dados ausentes remanescentes", "charts": "Visualizações gráficas",
    "treatment": "Resumo do tratamento realizado",
}


class TemporalConfig(BaseModel):
    date_column: Optional[str] = None
    frequency: Literal["D", "M", "Y"] = "M"
    value_columns: list[str] = []


class EdaConfig(BaseModel):
    report_name: str = Field(default="Análise exploratória", min_length=1, max_length=255)
    version_number: Optional[int] = None  # None = versão atual
    sections: list[str] = Field(default_factory=lambda: list(SECTIONS))
    columns: list[str] = []  # vazio = todas as colunas aplicáveis
    correlation_method: Literal["pearson", "spearman"] = "pearson"
    percentiles: list[float] = [5, 25, 50, 75, 95]
    temporal: TemporalConfig = Field(default_factory=TemporalConfig)

    @field_validator("sections")
    @classmethod
    def _sections(cls, v: list[str]) -> list[str]:
        bad = [s for s in v if s not in SECTIONS]
        if bad:
            raise ValueError(f"seções inválidas: {', '.join(bad)}")
        if not v:
            raise ValueError("escolha ao menos uma seção")
        return list(dict.fromkeys(v))

    @field_validator("percentiles")
    @classmethod
    def _pct(cls, v: list[float]) -> list[float]:
        if any(p <= 0 or p >= 100 for p in v) or len(v) > 12:
            raise ValueError("percentis devem estar entre 0 e 100 (até 12)")
        return sorted(set(v))
