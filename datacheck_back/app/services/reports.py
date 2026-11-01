"""Geração de relatórios e exportações (CSV e XLSX).

Células de texto que começam com =, +, - (não numérico), @ recebem um apóstrofo
inicial para que o Excel não as interprete como fórmulas.
"""
from __future__ import annotations

import csv
import io
from typing import Optional

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.catalog import SEVERITY_LABELS, category_label
from app.core.parsing import parse_number
from app.validators.base import Issue

# Mesmos títulos da tabela da visão detalhada (tela de resultados).
ISSUE_HEADERS = ["Linha", "Coluna", "Valor original", "Tipo", "Severidade", "Descrição", "Sugestão de revisão"]
HEADER_FILL = PatternFill("solid", fgColor="2563EB")
SEV_FILL = {"critical": "FEE2E2", "warning": "FEF3C7", "info": "E0E7FF"}


def safe(value):
    if isinstance(value, str) and value and value[0] in "=+-@\t\r":
        if value[0] in "+-" and parse_number(value) is not None:
            return value
        return "'" + value
    return value


def issue_row(i: Issue) -> list:
    return [i.row, safe(i.column), safe(i.value), category_label(i.category),
            SEVERITY_LABELS[i.severity], i.description, i.suggestion]


def _style_header(ws, row=1):
    for cell in ws[row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _autowidth(ws, max_width=60):
    for col in ws.columns:
        longest = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(10, longest + 2), max_width)


def _save(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv_bytes(rows: list[list]) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")


# ---------------------------------------------------------------- tabela de inconsistências


def issues_csv(issues: list[Issue]) -> bytes:
    return _csv_bytes([ISSUE_HEADERS] + [issue_row(i) for i in issues])


def _write_issues_sheet(ws, issues: list[Issue]):
    ws.append(ISSUE_HEADERS)
    _style_header(ws)
    for i in issues:
        ws.append(issue_row(i))
        ws.cell(ws.max_row, 5).fill = PatternFill("solid", fgColor=SEV_FILL[i.severity])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _autowidth(ws)


def issues_xlsx(issues: list[Issue]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Inconsistências"
    _write_issues_sheet(ws, issues)
    return _save(wb)


# ---------------------------------------------------------------- relatório completo


def _sections(result: dict) -> dict[str, list[list]]:
    m, s, ds = result["metrics"], result["score"], result["dataset"]
    return {
        "1. Identificação da análise": [
            ["Identificador", result["id"]],
            ["Arquivo", result["filename"]],
            ["Aba", result["sheet"] or "-"],
            ["Tamanho (bytes)", result["file_size_bytes"]],
            ["Enviada em (UTC)", result["created_at"]],
            ["Executada em (UTC)", result.get("completed_at") or "-"],
            ["Verificações executadas", ", ".join(r["name"] for r in result["rules"] if r["executed"])],
        ],
        "2. Resumo da base de dados": [["Coluna", "Tipo identificado", "Valores preenchidos"]]
        + [[c["name"], c["dtype_label"], c["non_missing"]] for c in ds["column_info"]]
        + [[], ["Total de registros", ds["rows"]], ["Total de colunas", ds["columns"]]],
        "3. Indicadores de qualidade": [
            ["DataCheck Score (0-100)", s["value"] if s["value"] is not None else "indisponível"],
            ["Classificação", s["label"]],
            ["Ocorrências encontradas", m["total_occurrences"]],
            ["Linhas afetadas", m["affected_rows"]],
            ["Linhas sem inconsistências (%)", m["clean_rows_pct"]],
            ["Fórmula do score", s["formula"]],
            ["Aviso", s["disclaimer"]],
        ],
    }


def _recommendations(result: dict) -> list[list]:
    return [["Nível", "Tema", "Observação", "Recomendação"]] + [
        [it["level"], it["title"], it["text"], it["recommendation"]] for it in result["insights"]["items"]]


def report_csv(result: dict, issues: Optional[list[Issue]]) -> bytes:
    rows: list[list] = [["RELATÓRIO DATACHECK"], ["Gráficos: disponíveis na exportação XLSX."], []]
    for title, body in _sections(result).items():
        rows += [[title]] + body + [[]]
    rows += [["4. Gráficos (dados)"], ["Categoria", "Ocorrências"]]
    rows += [[c["label"], c["count"]] for c in result["metrics"]["by_category"]]
    rows += [[], ["Severidade", "Ocorrências"]] + [[x["label"], x["count"]] for x in result["metrics"]["by_severity"]]
    rows += [[], ["Coluna", "Ausentes", "% ausentes"]]
    rows += [[x["column"], x["count"], x["pct"]] for x in result["metrics"]["missing_by_column"]]
    rows += [[], ["5. Lista de inconsistências"]]
    rows += [ISSUE_HEADERS] + [issue_row(i) for i in issues] if issues is not None else \
        [["Detalhes não armazenados para esta análise (histórico salvo sem valores das células)."]]
    rows += [[], ["6. Recomendações de revisão"]] + _recommendations(result)
    return _csv_bytes(rows)


def report_xlsx(result: dict, issues: Optional[list[Issue]]) -> bytes:
    wb = Workbook()
    names = ["Identificação", "Resumo da base", "Indicadores"]
    for n, (title, body) in zip(names, _sections(result).items()):
        ws = wb.active if n == names[0] else wb.create_sheet()
        ws.title = n
        for r in body:
            ws.append(r)
        if n == "Resumo da base":
            _style_header(ws)
        else:
            for row in ws.iter_rows(max_col=1):
                row[0].font = Font(bold=True)
        _autowidth(ws, 90)
    _charts_sheet(wb.create_sheet("Gráficos"), result)
    ws = wb.create_sheet("Inconsistências")
    if issues is None:
        ws.append(["Detalhes não armazenados para esta análise (histórico salvo sem valores das células)."])
    else:
        _write_issues_sheet(ws, issues)
    ws = wb.create_sheet("Recomendações")
    for r in _recommendations(result):
        ws.append(r)
    _style_header(ws)
    _autowidth(ws, 80)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    return _save(wb)


def _charts_sheet(ws, result: dict):
    m = result["metrics"]
    blocks = [
        ("Categoria", "Ocorrências", [[c["label"], c["count"]] for c in m["by_category"]], "bar", "Inconsistências por categoria"),
        ("Severidade", "Ocorrências", [[x["label"], x["count"]] for x in m["by_severity"]], "pie", "Ocorrências por severidade"),
        ("Coluna", "Ausentes", [[x["column"], x["count"]] for x in m["missing_by_column"]], "bar", "Valores ausentes por coluna"),
    ]
    anchor_row = 1
    for h1, h2, data, kind, title in blocks:
        if not data:
            continue
        ws.cell(anchor_row, 1, h1)
        ws.cell(anchor_row, 2, h2)
        for k, (a, b) in enumerate(data, start=1):
            ws.cell(anchor_row + k, 1, safe(a))
            ws.cell(anchor_row + k, 2, b)
        chart = PieChart() if kind == "pie" else BarChart()
        chart.title = title
        chart.add_data(Reference(ws, min_col=2, min_row=anchor_row, max_row=anchor_row + len(data)), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=anchor_row + 1, max_row=anchor_row + len(data)))
        chart.width, chart.height = 16, 7.5
        ws.add_chart(chart, f"D{anchor_row}")
        anchor_row += max(len(data) + 3, 17)
    _style_header(ws)
    ws.column_dimensions["A"].width = 32


def feedback_csv(rows: list[dict]) -> bytes:
    cols = ["id", "created_at", "ease", "usefulness", "would_reuse", "difficulties", "suggestions", "analysis_id"]
    return _csv_bytes([cols] + [[safe(r[c]) if isinstance(r[c], str) else r[c] for c in cols] for r in rows])
