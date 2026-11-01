from __future__ import annotations

import pandas as pd

from app.schemas.validation import AnalysisConfig
from app.core.parsing import map_unique, missing_mask, parse_date
from app.validators.base import Rule, RuleContext, RuleOutput

_TYPE_NAMES = {"integer": "inteiro", "decimal": "decimal", "date": "data", "text": "texto"}


class TypesRule(Rule):
    code = "types"

    def is_active(self, config: AnalysisConfig) -> bool:
        return config.types.enabled and bool(config.types.expected)

    def referenced_columns(self, config: AnalysisConfig) -> list[str]:
        return list(config.types.expected)

    def run(self, df: pd.DataFrame, config: AnalysisConfig, ctx: RuleContext) -> RuleOutput:
        cfg = config.types
        formats = [cfg.date_format] if cfg.date_format else None
        out = RuleOutput()
        for col, expected in cfg.expected.items():
            series = df[col]
            present = series[~missing_mask(series, ctx.markers)]
            if present.empty:
                continue
            if expected in ("integer", "decimal"):
                parsed = map_unique(present, ctx.number)
                bad = parsed.isna()
                if expected == "integer":
                    bad = bad | (parsed.notna() & (parsed % 1 != 0))
                desc = "Valor não é um número inteiro válido." if expected == "integer" else "Valor não é um número decimal válido."
                sugg = "Remova letras/símbolos e use o separador decimal configurado (ex.: 12,5 ou 12.5)."
                severity = "critical"
            elif expected == "date":
                bad = map_unique(present, lambda v: parse_date(v, formats)).isna()
                desc = "Valor não é uma data válida."
                sugg = "Use uma data existente em formato padrão, como AAAA-MM-DD ou DD/MM/AAAA."
                severity = "critical"
            else:
                bad = map_unique(present, ctx.number).notna()
                desc = "Valor numérico em coluna esperada como texto."
                sugg = "Confira se o valor foi digitado na coluna correta."
                severity = "warning"
            for idx in present.index[bad]:
                out.issues.append(
                    ctx.issue(idx, col, series.iloc[idx], "tipo_incompativel", severity,
                              f"{desc} Esperado: {_TYPE_NAMES[expected]}.", sugg)
                )
        return out
