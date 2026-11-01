"""Relatório EDA em XLSX: abas organizadas, com proteção contra fórmulas em textos."""
from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.services.reports import HEADER_FILL, safe


def _sheet(wb: Workbook, title: str, rows: list[list[Any]], header: bool = True, widths: dict[str, int] | None = None) -> None:
    ws = wb.create_sheet(title)
    for r in rows:
        ws.append([safe(v) if isinstance(v, str) else v for v in r])
    if header and rows:
        for c in ws[1]:
            c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), HEADER_FILL, Alignment(wrap_text=True, vertical="center")
        ws.freeze_panes = "A2"
    for col in ws.columns:
        longest = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(max(10, longest + 2), 60)


def build_xlsx(report_name: str, meta: dict[str, Any], stats: dict[str, Any], cfg: dict[str, Any]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    sec = set(cfg["sections"])
    o = stats["overview"]
    _sheet(wb, "Resumo", [["Item", "Valor"], ["Relatório", report_name], ["Análise de origem", meta["analysis_name"]], ["Versão dos dados", f"{meta['version_label']} (versão {meta['version_number']})"],
                          ["Identificador da análise", meta["analysis_id"]], ["Gerado em", meta["generated_at"]], ["Registros", o["rows"]], ["Variáveis", o["columns"]], [], ["Variável", "Tipo estatístico", "Válidos", "Ausentes", "% ausentes", "Distintos"]]
           + [[c["name"], c["label"], c["n_valid"], c["n_missing"], c["pct_missing"], c["n_unique"]] for c in o["columns_info"]], header=False)
    if "descriptive" in sec and stats.get("descriptive"):
        keys = [("Observações válidas", "n_valid"), ("Ausentes", "n_missing"), ("Média", "mean"), ("Mediana", "median"), ("Moda", "mode"), ("Mínimo", "min"), ("Máximo", "max"), ("Amplitude", "range"),
                ("Variância", "variance"), ("Desvio padrão", "std"), ("Coeficiente de variação", "cv"), ("Q1", "q1"), ("Q3", "q3"), ("Intervalo interquartil", "iqr"), ("Assimetria", "skewness"), ("Curtose", "kurtosis")]
        pk = list(stats["descriptive"][0].get("percentiles", {}))
        rows = [["Variável"] + [k[0] for k in keys] + [f"Percentil {p[1:]}" for p in pk] + ["Avisos"]]
        for d in stats["descriptive"]:
            rows.append([d["column"]] + [d.get(k[1]) for k in keys] + [d.get("percentiles", {}).get(p) for p in pk] + ["; ".join(d["warnings"])])
        _sheet(wb, "Estatísticas descritivas", rows)
    if "frequencies" in sec and stats.get("frequencies"):
        rows = [["Variável", "Categoria", "Frequência absoluta", "Frequência relativa (%)", "Distintas", "Ausentes"]]
        for f in stats["frequencies"]:
            rows += [[f["column"], x["value"], x["count"], x["pct"], f["n_unique"], f["n_missing"]] for x in f["top"]]
            if f.get("other"):
                rows.append([f["column"], f"(outras {f['other']['n_categories']} categorias)", f["other"]["count"], None, f["n_unique"], f["n_missing"]])
        _sheet(wb, "Frequências", rows)
    c = stats.get("correlation")
    if "correlation" in sec and c and c.get("columns"):
        rows = [[f"Correlação de {c['method'].capitalize()}"] + c["columns"]] + [[c["columns"][i]] + r for i, r in enumerate(c["matrix"])]
        rows += [[], ["Observações por par"] + c["columns"]] + [[c["columns"][i]] + r for i, r in enumerate(c["n_matrix"])]
        rows += [[], ["Variável A", "Variável B", "Coeficiente", "n", "Intensidade", "Direção"]] + [[p["a"], p["b"], p["r"], p["n"], p["strength"], p["direction"]] for p in c["pairs"]]
        rows += [[], [c["warning"]]]
        _sheet(wb, "Correlações", rows, header=False)
    if "outliers" in sec and stats.get("outliers"):
        _sheet(wb, "Valores extremos", [["Variável", "Critério", "Limite inferior", "Limite superior", "Quantidade", "%", "Exemplos"]] +
               [[x["column"], x["method"], x.get("lower"), x.get("upper"), x.get("count"), x.get("pct"), ", ".join(str(v) for v in x.get("examples", []))] for x in stats["outliers"]])
    tm = stats.get("temporal")
    if "temporal" in sec and tm and tm.get("available"):
        rows = [["Período", "Registros"]] + [[p["period"], p["count"]] for p in tm["count_series"]]
        for vs in tm["value_series"]:
            rows += [[], [f"Período ({vs['column']})", "Média", "n"]] + [[p["period"], p["mean"], p["n"]] for p in vs["points"]]
        _sheet(wb, "Temporal", rows, header=False)
    if "missing" in sec:
        m = stats["missing"]
        _sheet(wb, "Ausentes remanescentes", [["Variável", "Ausentes", "%"]] + [[x["column"], x["n_missing"], x["pct"]] for x in m["columns"]] + [[], ["Registros com ao menos um ausente", m["rows_with_missing"]], ["Registros completos", m["complete_rows"]]])
    t = stats.get("treatment")
    if "treatment" in sec and t:
        rows = [["Indicador", "Valor"], ["Versão", t.get("version_label")], ["Score original", t.get("score_before")], ["Score desta versão", t.get("score_after")], ["Registros (original)", t.get("rows_before")],
                ["Registros (versão)", t.get("rows_after")], ["Valores imputados", t["imputed_values"]], ["Registros removidos", t["removed_rows"]], ["Duplicidades resolvidas", t["duplicates_resolved"]],
                ["Correções manuais e de formato (registros)", t["manual_corrections"]], ["Ocorrências mantidas como exceção", t["exceptions_accepted"]], [],
                ["Operação", "Coluna", "Método", "Registros", "Justificativa", "Data"]]
        rows += [[x["label"], x["column"], x["method"], x["affected_rows"], x["justification"], x["at"]] for x in t.get("operations", [])]
        _sheet(wb, "Informações do tratamento", rows, header=False)
    _sheet(wb, "Observações", [["Principais observações"]] + [[x] for x in stats["observations"]] + [[], ["Limitações"]] + [[x] for x in stats["limitations"]], header=False)
    wb["Observações"].column_dimensions["A"].width = 120
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
