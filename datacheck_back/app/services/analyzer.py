"""Orquestra as verificações e calcula os indicadores. Não altera o DataFrame."""
from __future__ import annotations

import time
from collections import Counter
from datetime import date
from typing import Optional, Sequence

from app.core.config import get_settings
from app.core.catalog import (CATEGORIES, RULE_NAMES, RULES_INFO, SEVERITY_LABELS,
                              SEVERITY_RANK, category_label)
from app.core.errors import DataCheckError
from app.schemas.validation import AnalysisConfig
from app.validators import RULES, Issue, RuleContext
from app.services.file_reader import LoadedTable
from app.services.insights import generate_insights
from app.services.profiler import infer_column
from app.services.scoring import compute_score


def _validate(table: LoadedTable, config: AnalysisConfig) -> None:
    if len(table.df) == 0:
        raise DataCheckError("A planilha não contém registros para analisar.", 422)
    columns = set(table.df.columns)
    for rule in RULES:
        rule.validate(config)
        for col in rule.referenced_columns(config):
            if col not in columns:
                raise DataCheckError(
                    f"A coluna «{col}» (verificação «{RULE_NAMES[rule.code]}») não existe na planilha.", 422)


def run_analysis(table: LoadedTable, config: AnalysisConfig, *, filename: str = "",
                 file_size: int = 0, today: Optional[date] = None,
                 row_numbers: Optional[Sequence[int]] = None) -> tuple[dict, list[Issue]]:
    """Executa as verificações. Retorna (resumo serializável, ocorrências)."""
    _validate(table, config)
    active = [r for r in RULES if r.is_active(config)]
    if not active:
        raise DataCheckError(
            "Nenhuma verificação está ativa ou configurada. Ative ao menos uma e, onde "
            "necessário, escolha as colunas.", 422)

    df = table.df
    ctx = RuleContext(table.first_data_line, config.missing.markers, today or date.today(),
                      config.decimal_separator, row_numbers)
    issues: list[Issue] = []
    rule_summaries, stats = [], {}
    info_by_code = {r["code"]: r for r in RULES_INFO}
    for rule in RULES:
        info = info_by_code[rule.code]
        if rule not in active:
            rule_summaries.append({**info, "executed": False, "issues": 0, "seconds": 0.0})
            continue
        start = time.perf_counter()
        out = rule.run(df, config, ctx)
        elapsed = round(time.perf_counter() - start, 3)
        issues.extend(out.issues)
        stats[rule.code] = out.stats
        rule_summaries.append({**info, "executed": True, "issues": len(out.issues), "seconds": elapsed})

    issues.sort(key=lambda i: (i.row, i.column, i.category))
    total_rows = len(df)
    affected = len({i.row for i in issues})

    by_cat = Counter(i.category for i in issues)
    by_sev = Counter(i.severity for i in issues)
    by_col = Counter(i.column for i in issues)
    top_cols: dict[str, list] = {}
    pair = Counter((i.category, i.column) for i in issues)
    for (cat, col), n in pair.most_common():
        top_cols.setdefault(cat, [])
        if len(top_cols[cat]) < 5:
            top_cols[cat].append({"column": col, "count": n})

    metrics = {
        "total_rows": total_rows,
        "total_columns": int(df.shape[1]),
        "total_occurrences": len(issues),
        "affected_rows": affected,
        "affected_rows_pct": round(100 * affected / total_rows, 1),
        "clean_rows": total_rows - affected,
        "clean_rows_pct": round(100 * (total_rows - affected) / total_rows, 1),
        "by_category": [
            {"category": c, "label": category_label(c), "rule": CATEGORIES[c]["rule"], "count": n}
            for c, n in by_cat.most_common()
        ],
        "by_severity": [
            {"severity": s, "label": SEVERITY_LABELS[s], "count": by_sev.get(s, 0)}
            for s in sorted(SEVERITY_LABELS, key=SEVERITY_RANK.get)
        ],
        "by_column": [{"column": c, "count": n} for c, n in by_col.most_common()],
        "top_columns_by_category": top_cols,
        "missing_by_column": stats.get("missing", {}).get("by_column", []),
        "duplicates": stats.get("duplicates", {}),
    }

    cap = get_settings().max_stored_issues
    result = {
        "dataset": {
            "rows": total_rows,
            "columns": int(df.shape[1]),
            "column_info": [infer_column(df[c]) for c in df.columns],
        },
        "config": config.model_dump(mode="json"),
        "metrics": metrics,
        "score": compute_score(total_rows, affected),
        "rules": rule_summaries,
        "issues_truncated": len(issues) > cap,
        "issues_stored": min(len(issues), cap),
    }
    result["insights"] = generate_insights(result)
    return result, issues[:cap]
