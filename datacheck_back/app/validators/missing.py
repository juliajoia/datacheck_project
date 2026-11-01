from __future__ import annotations

import pandas as pd

from app.core.config import CRITICAL_MISSING_PCT
from app.schemas.validation import AnalysisConfig
from app.core.parsing import missing_mask
from app.validators.base import Rule, RuleContext, RuleOutput

SUGGESTION = "Confira o dado na fonte original e preencha, ou documente por que está ausente."


class MissingRule(Rule):
    code = "missing"

    def is_active(self, config: AnalysisConfig) -> bool:
        return config.missing.enabled

    def referenced_columns(self, config: AnalysisConfig) -> list[str]:
        return (config.missing.columns or []) + config.missing.required_columns

    def run(self, df: pd.DataFrame, config: AnalysisConfig, ctx: RuleContext) -> RuleOutput:
        cfg = config.missing
        out = RuleOutput()
        by_column = []
        total = len(df)
        required = set(cfg.required_columns)
        columns = list(cfg.columns) if cfg.columns else list(df.columns)
        columns += [c for c in cfg.required_columns if c not in columns]
        for col in columns:
            series = df[col]
            mask = missing_mask(series, cfg.markers, cfg.treat_blank)
            count = int(mask.sum())
            pct = round(100 * count / total, 2) if total else 0.0
            by_column.append({"column": col, "count": count, "pct": pct})
            if not count:
                continue
            severity = "critical" if col in required or pct >= CRITICAL_MISSING_PCT else "warning"
            prefix = "Campo obrigatório não preenchido. " if col in required else ""
            for idx in series.index[mask]:
                raw = series.iloc[idx]
                if raw == "":
                    desc = prefix + "Célula vazia."
                elif raw.strip() == "":
                    desc = prefix + "Célula contém apenas espaços em branco."
                else:
                    desc = prefix + f"Marcador de ausência «{raw.strip()}»."
                out.issues.append(
                    ctx.issue(idx, col, raw, "valores_ausentes", severity, desc, SUGGESTION)
                )
        out.stats["by_column"] = by_column
        return out
