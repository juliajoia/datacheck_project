from __future__ import annotations

import pandas as pd

from app.core.errors import DataCheckError
from app.core.parsing import fmt_number, map_unique, missing_mask
from app.schemas.validation import AnalysisConfig
from app.validators.base import Rule, RuleContext, RuleOutput

CONFIRMED_HINT = "Viola um limite que você definiu. Confirme com a fonte antes de corrigir; se o limite estiver errado, ajuste a regra."
SUSPECT_HINT = "Valor muito distante dos demais; pode ser legítimo. Confira com a fonte antes de alterar."
IQR_FACTOR = 3.0
MIN_VALUES_FOR_OUTLIERS = 8


class RangesRule(Rule):
    code = "ranges"

    def is_active(self, config: AnalysisConfig) -> bool:
        r = config.ranges
        return r.enabled and (bool(r.suspect_columns) or any(
            lim.min is not None or lim.max is not None for lim in r.limits.values()))

    def referenced_columns(self, config: AnalysisConfig) -> list[str]:
        return list(config.ranges.limits) + list(config.ranges.suspect_columns)

    def validate(self, config: AnalysisConfig) -> None:
        for col, lim in config.ranges.limits.items():
            if lim.min is not None and lim.max is not None and lim.min > lim.max:
                raise DataCheckError(f"Na coluna «{col}», o mínimo é maior que o máximo.", 422)

    def run(self, df: pd.DataFrame, config: AnalysisConfig, ctx: RuleContext) -> RuleOutput:
        out = RuleOutput()
        cfg = config.ranges
        for col, lim in cfg.limits.items():
            if lim.min is None and lim.max is None:
                continue
            series = df[col]
            present = series[~missing_mask(series, ctx.markers)]
            numbers = map_unique(present, ctx.number)  # não numéricos viram NaN (regra C)
            if lim.min is not None:
                for idx in numbers.index[numbers < lim.min]:
                    out.issues.append(ctx.issue(
                        idx, col, series.iloc[idx], "fora_limites", "critical",
                        f"Valor {fmt_number(numbers[idx])} abaixo do mínimo configurado ({fmt_number(lim.min)}).",
                        CONFIRMED_HINT))
            if lim.max is not None:
                for idx in numbers.index[numbers > lim.max]:
                    out.issues.append(ctx.issue(
                        idx, col, series.iloc[idx], "fora_limites", "critical",
                        f"Valor {fmt_number(numbers[idx])} acima do máximo configurado ({fmt_number(lim.max)}).",
                        CONFIRMED_HINT))
        flagged = {(i.row, i.column) for i in out.issues}
        for col in cfg.suspect_columns:
            series = df[col]
            present = series[~missing_mask(series, ctx.markers)]
            numbers = map_unique(present, ctx.number).dropna().astype(float)
            if len(numbers) < MIN_VALUES_FOR_OUTLIERS:
                continue
            q1, q3 = numbers.quantile(0.25), numbers.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            low, high = q1 - IQR_FACTOR * iqr, q3 + IQR_FACTOR * iqr
            for idx in numbers.index[(numbers < low) | (numbers > high)]:
                if (ctx.line_of(idx), col) in flagged:
                    continue
                out.issues.append(ctx.issue(
                    idx, col, series.iloc[idx], "valor_suspeito", "info",
                    f"Valor {fmt_number(numbers[idx])} muito distante da distribuição da coluna "
                    f"(fora de {fmt_number(round(low, 2))} a {fmt_number(round(high, 2))}). Suspeito, não confirmado como erro.",
                    SUSPECT_HINT))
        return out
