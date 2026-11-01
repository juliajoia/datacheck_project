from __future__ import annotations

import pandas as pd

from app.core.errors import DataCheckError
from app.schemas.validation import AnalysisConfig
from app.core.parsing import map_unique, missing_mask, parse_date
from app.validators.base import Rule, RuleContext, RuleOutput


class DatesRule(Rule):
    code = "dates"

    def is_active(self, config: AnalysisConfig) -> bool:
        return config.dates.enabled and bool(config.dates.columns)

    def referenced_columns(self, config: AnalysisConfig) -> list[str]:
        return list(config.dates.columns)

    def validate(self, config: AnalysisConfig) -> None:
        d = config.dates
        if d.min_date and d.max_date and d.min_date > d.max_date:
            raise DataCheckError("A data mínima é posterior à data máxima.", 422)

    def run(self, df: pd.DataFrame, config: AnalysisConfig, ctx: RuleContext) -> RuleOutput:
        cfg = config.dates
        formats = [cfg.date_format] if cfg.date_format else None
        out = RuleOutput()
        for col in cfg.columns:
            series = df[col]
            present = series[~missing_mask(series, ctx.markers)]
            parsed = map_unique(present, lambda v: parse_date(v, formats))
            for idx in present.index[parsed.isna()]:
                out.issues.append(ctx.issue(
                    idx, col, series.iloc[idx], "data_invalida", "critical",
                    "Data inexistente ou fora do formato esperado.",
                    "Corrija para uma data real (ex.: 2024-03-31 ou 31/03/2024)."))
            for idx in parsed.index[parsed.notna()]:
                d = parsed[idx]
                raw = series.iloc[idx]
                if cfg.min_date and d < cfg.min_date:
                    out.issues.append(ctx.issue(
                        idx, col, raw, "data_fora_limite", "warning",
                        f"Data anterior ao limite mínimo ({cfg.min_date.isoformat()}).",
                        "Confirme se a data está correta ou se o período configurado precisa mudar."))
                elif cfg.max_date and d > cfg.max_date:
                    out.issues.append(ctx.issue(
                        idx, col, raw, "data_fora_limite", "warning",
                        f"Data posterior ao limite máximo ({cfg.max_date.isoformat()}).",
                        "Confirme se a data está correta ou se o período configurado precisa mudar."))
                elif cfg.flag_future and d > ctx.today:
                    out.issues.append(ctx.issue(
                        idx, col, raw, "data_futura", "warning",
                        f"Data futura (hoje é {ctx.today.isoformat()}).",
                        "Verifique se é um registro previsto ou um erro de digitação (ex.: ano trocado)."))
        return out
