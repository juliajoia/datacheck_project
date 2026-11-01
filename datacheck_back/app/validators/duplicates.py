from __future__ import annotations

import pandas as pd

from app.schemas.validation import AnalysisConfig
from app.validators.base import Rule, RuleContext, RuleOutput

MAX_LINES_IN_TEXT = 6


class DuplicatesRule(Rule):
    """Sinaliza TODOS os registros de cada grupo duplicado (inclusive a primeira ocorrência)."""

    code = "duplicates"

    def is_active(self, config: AnalysisConfig) -> bool:
        return config.duplicates.enabled

    def referenced_columns(self, config: AnalysisConfig) -> list[str]:
        return config.duplicates.key_columns or []

    def run(self, df: pd.DataFrame, config: AnalysisConfig, ctx: RuleContext) -> RuleOutput:
        keys = config.duplicates.key_columns or list(df.columns)
        full_row = not config.duplicates.key_columns
        norm = df[keys].apply(lambda c: c.str.strip())
        in_group = norm.duplicated(keep=False)
        out = RuleOutput(stats={"groups": 0, "rows_in_groups": int(in_group.sum())})
        if not in_group.any():
            return out

        group_id = norm[in_group].groupby(keys, sort=False).ngroup()
        lines_by_group = {
            g: [ctx.line_of(i) for i in idxs] for g, idxs in group_id.groupby(group_id).groups.items()
        }
        out.stats["groups"] = len(lines_by_group)

        column_label = "(linha completa)" if full_row else ", ".join(keys)
        for idx in df.index[in_group]:
            lines = lines_by_group[group_id[idx]]
            shown = ", ".join(map(str, lines[:MAX_LINES_IN_TEXT])) + ("…" if len(lines) > MAX_LINES_IN_TEXT else "")
            values = " | ".join(df.iloc[idx][keys].tolist()[:4])
            if full_row:
                desc = f"Registro repetido: conteúdo idêntico nas linhas {shown}."
                sugg = "Verifique se é uma importação repetida (mantenha uma cópia) ou ocorrências legítimas."
            else:
                desc = f"Chave ({column_label}) repetida nas linhas {shown}."
                sugg = "Confirme se o identificador deveria ser único; se sim, corrija ou consolide os registros."
            out.issues.append(ctx.issue(idx, column_label, values, "duplicados",
                                        "warning" if full_row else "critical", desc, sugg))
        return out
