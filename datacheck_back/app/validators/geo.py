from __future__ import annotations

import pandas as pd

from app.core.errors import DataCheckError
from app.schemas.validation import AnalysisConfig
from app.core.parsing import fmt_number, map_unique, missing_mask
from app.validators.base import Rule, RuleContext, RuleOutput

# Ponto de extensão: regras por região (ex.: caixa delimitadora do país/estado)
# podem ser acrescentadas aqui como uma nova categoria sem alterar as demais regras.


class GeoRule(Rule):
    code = "geo"

    def is_active(self, config: AnalysisConfig) -> bool:
        g = config.geo
        return g.enabled and bool(g.lat_column or g.lon_column)

    def referenced_columns(self, config: AnalysisConfig) -> list[str]:
        g = config.geo
        return [c for c in (g.lat_column, g.lon_column) if c]

    def validate(self, config: AnalysisConfig) -> None:
        g = config.geo
        if g.lat_column and g.lat_column == g.lon_column:
            raise DataCheckError("Latitude e longitude precisam ser colunas diferentes.", 422)

    def run(self, df: pd.DataFrame, config: AnalysisConfig, ctx: RuleContext) -> RuleOutput:
        g = config.geo
        out = RuleOutput()
        for col, label, limit in ((g.lat_column, "Latitude", 90.0), (g.lon_column, "Longitude", 180.0)):
            if not col:
                continue
            series = df[col]
            missing = missing_mask(series, ctx.markers)
            numbers = map_unique(series, ctx.number)
            for idx in series.index[missing]:
                out.issues.append(ctx.issue(
                    idx, col, series.iloc[idx], "geo_ausente", "warning",
                    f"{label} ausente: o registro não pode ser posicionado no mapa.",
                    "Preencha a coordenada a partir da fonte ou do endereço."))
            invalid = numbers.isna() & ~missing
            for idx in series.index[invalid]:
                out.issues.append(ctx.issue(
                    idx, col, series.iloc[idx], "geo_nao_numerica", "critical",
                    f"{label} não é um número válido.",
                    "Use graus decimais (ex.: -23.5505), sem letras ou símbolos."))
            outside = numbers.abs() > limit
            for idx in series.index[outside.fillna(False)]:
                out.issues.append(ctx.issue(
                    idx, col, series.iloc[idx], "geo_fora_limite", "critical",
                    f"{label} {fmt_number(numbers[idx])} fora do intervalo permitido (-{limit:g} a {limit:g}).",
                    "Verifique se há erro de digitação, ponto decimal deslocado ou colunas trocadas."))
        return out
