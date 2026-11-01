"""PDF da tabela de inconsistências (mesmas colunas da visão detalhada)."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.reports import ISSUE_HEADERS, issue_row
from app.utils.dates import fmt_local
from app.validators.base import Issue

MAX_PDF_ROWS = 3000  # PDFs muito longos ficam impraticáveis; o XLSX traz a lista completa
COL_WIDTHS = [34, 78, 100, 88, 58, 205, 195]  # pontos; soma ≈ 758 (A4 paisagem com margens de 12 mm)
SEV_BG = {"Crítica": "#FEE2E2", "Aviso": "#FEF3C7", "Informativa": "#E0E7FF"}
BLUE = colors.HexColor("#2563EB")


def _p(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def issues_pdf(result: dict, issues: list[Issue]) -> bytes:
    base = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=base["BodyText"], fontSize=7.5, leading=9.5)
    head = ParagraphStyle("head", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    title = ParagraphStyle("title", parent=base["Title"], fontSize=16, alignment=0, textColor=BLUE, spaceAfter=2)
    meta = ParagraphStyle("meta", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#334155"))

    shown = issues[:MAX_PDF_ROWS]
    score = result["score"]["value"]
    story = [
        Paragraph("DataCheck · Relatório de inconsistências", title),
        Paragraph(escape(f"Arquivo: {result['filename']}" + (f" (aba {result['sheet']})" if result.get("sheet") else "")), meta),
        Paragraph(escape(
            f"Executada em {fmt_local(result.get('completed_at'))} · {result['total_rows']} registros · "
            f"{result['total_issues']} ocorrências · {result['affected_rows']} linhas afetadas · "
            f"DataCheck Score: {score if score is not None else 'indisponível'}"), meta),
        Paragraph(escape(
            "O score representa apenas a cobertura das regras executadas e não garante que os dados estejam corretos."), meta),
    ]
    if len(issues) > len(shown):
        story.append(Paragraph(escape(
            f"Exibindo as primeiras {len(shown)} de {len(issues)} ocorrências. Use o XLSX para a lista completa."), meta))
    story.append(Spacer(1, 6 * mm))

    if not shown:
        story.append(Paragraph("Nenhuma inconsistência foi encontrada pelas regras executadas.", meta))
    else:
        rows = [[_p(h, head) for h in ISSUE_HEADERS]]
        styles = [
            ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for n, issue in enumerate(shown, start=1):
            values = issue_row(issue)
            values[1], values[2] = issue.column, issue.value  # PDF não precisa do apóstrofo anti-fórmula
            rows.append([_p(v, cell) for v in values])
            styles.append(("BACKGROUND", (4, n), (4, n), colors.HexColor(SEV_BG[values[4]])))
        table = Table(rows, colWidths=COL_WIDTHS, repeatRows=1)
        table.setStyle(TableStyle(styles))
        story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(12 * mm, 7 * mm, "DataCheck · Dados confiáveis. Decisões inteligentes.")
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 7 * mm, f"Página {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm, title="DataCheck · Inconsistências",
                            author="DataCheck")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
