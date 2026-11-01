"""Relatório EDA em PDF (ReportLab)."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from app.schemas.eda import SECTION_LABELS
from app.services.eda import charts
from app.services.eda.engine import num, pct

LOGO = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.png"
BLUE, PURPLE, SLATE = colors.HexColor("#2563EB"), colors.HexColor("#7C3AED"), colors.HexColor("#334155")
MAX_QUANT_CHARTS, MAX_QUAL_CHARTS = 12, 8
PAGE_W = A4[0] - 36 * mm


def _styles() -> dict[str, ParagraphStyle]:
    b = getSampleStyleSheet()
    return {
        "body": ParagraphStyle("body", parent=b["BodyText"], fontSize=9, leading=12.5, textColor=SLATE),
        "small": ParagraphStyle("small", parent=b["BodyText"], fontSize=7.5, leading=10, textColor=colors.HexColor("#64748B")),
        "h1": ParagraphStyle("h1", parent=b["Heading1"], fontSize=15, textColor=BLUE, spaceBefore=6, spaceAfter=6, keepWithNext=1),
        "h2": ParagraphStyle("h2", parent=b["Heading2"], fontSize=11, textColor=PURPLE, spaceBefore=8, spaceAfter=4, keepWithNext=1),
        "intro": ParagraphStyle("intro", parent=b["BodyText"], fontSize=7.5, leading=10, textColor=colors.HexColor("#64748B"), keepWithNext=1),
        "cell": ParagraphStyle("cell", parent=b["BodyText"], fontSize=7.5, leading=9.5),
        "cellb": ParagraphStyle("cellb", parent=b["BodyText"], fontSize=7.5, leading=9.5, fontName="Helvetica-Bold", textColor=colors.white),
        "title": ParagraphStyle("title", parent=b["Title"], fontSize=26, leading=30, textColor=BLUE, alignment=0),
        "subtitle": ParagraphStyle("subtitle", parent=b["BodyText"], fontSize=12, leading=16, textColor=SLATE),
    }


def _p(t: Any, st: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(t)), st)


def _table(rows: list[list[Any]], widths: list[float], st: dict[str, ParagraphStyle], header: bool = True) -> Table:
    data = [[_p(c, st["cellb"] if header and i == 0 else st["cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), BLUE)]
    t.setStyle(TableStyle(style))
    return t


def _img(png: bytes, width: float) -> Image:
    from PIL import Image as PILImage  # Pillow acompanha o Matplotlib
    w, h = PILImage.open(io.BytesIO(png)).size
    return Image(io.BytesIO(png), width=width, height=width * h / w)


def _side(a: bytes, b: bytes) -> Table:
    t = Table([[_img(a, PAGE_W * 0.62), _img(b, PAGE_W * 0.36)]], colWidths=[PAGE_W * 0.64, PAGE_W * 0.36])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def build_pdf(report_name: str, meta: dict[str, Any], stats: dict[str, Any], cfg: dict[str, Any]) -> bytes:
    st = _styles()
    sec = set(cfg["sections"])
    story: list[Any] = []

    # ------------------------------------------------------------ 1. capa
    if LOGO.exists():
        story.append(Image(str(LOGO), width=60 * mm, height=60 * mm * 507 / 1886))
    story += [Spacer(1, 40 * mm), Paragraph(escape(report_name), st["title"]), Spacer(1, 6 * mm),
              _p("Relatório de Análise Exploratória de Dados", st["subtitle"]), Spacer(1, 14 * mm)]
    story.append(_table([["Análise de origem", meta["analysis_name"]], ["Versão dos dados", f"{meta['version_label']} (versão {meta['version_number']})"],
                         ["Identificador da análise", meta["analysis_id"]], ["Registros × variáveis", f"{stats['n_rows']} × {stats['n_columns']}"],
                         ["Gerado em", meta["generated_at"]]], [48 * mm, PAGE_W - 48 * mm], st, header=False))
    story += [Spacer(1, 12 * mm), _p("Este relatório descreve os dados da versão indicada. Não apresenta conclusões causais nem inferências populacionais.", st["small"]), PageBreak()]

    n = 0

    def h1(title: str, need: float = 75) -> None:
        nonlocal n
        n += 1
        story.append(CondPageBreak(need * mm))  # evita título de seção sozinho no fim da página
        story.append(Paragraph(f"{n}. {escape(title)}", st["h1"]))

    # ------------------------------------------------------------ resumo executivo
    o = stats["overview"]
    h1("Resumo executivo")
    story.append(_p(f"A base tratada contém {o['rows']} registros e {o['columns']} variáveis: " + "; ".join(f"{v} {k.lower()}" for k, v in o["type_counts"].items()) + ".", st["body"]))
    story.append(Spacer(1, 3 * mm))
    story.append(_table([["Variável", "Tipo estatístico", "Válidos", "Ausentes", "% ausentes", "Distintos"]] +
                        [[c["name"], c["label"], c["n_valid"], c["n_missing"], pct(c["pct_missing"]), c["n_unique"]] for c in o["columns_info"]],
                        [PAGE_W * f for f in (.28, .22, .12, .12, .13, .13)], st))

    # ------------------------------------------------------------ qualidade e preparação
    t = stats.get("treatment")
    if "treatment" in sec and t:
        h1("Qualidade e preparação dos dados")
        story.append(_p(f"Versão analisada: {t.get('version_label')}. DataCheck Score: {num(t.get('score_before'), 1)} (original) → {num(t.get('score_after'), 1)} (esta versão). "
                        "O score representa apenas a cobertura das regras executadas e não garante que os dados estejam completamente corretos.", st["body"]))
        story.append(Spacer(1, 2 * mm))
        story.append(_table([["Indicador", "Valor"], ["Registros (original → versão)", f"{t.get('rows_before')} → {t.get('rows_after')}"], ["Valores imputados", t["imputed_values"]],
                             ["Registros removidos", t["removed_rows"]], ["Duplicidades resolvidas", t["duplicates_resolved"]], ["Correções manuais e de formato (registros)", t["manual_corrections"]],
                             ["Ocorrências mantidas como exceção", t["exceptions_accepted"]]], [PAGE_W * .65, PAGE_W * .35], st))
        if t.get("operations"):
            story += [CondPageBreak(45 * mm), Paragraph("Operações de tratamento aplicadas", st["h2"]),
                      _table([["Operação", "Coluna", "Método", "Registros", "Justificativa"]] +
                             [[x["label"], x["column"] or "—", x["method"] or "—", x["affected_rows"], x["justification"] or "—"] for x in t["operations"][:40]],
                             [PAGE_W * f for f in (.22, .17, .17, .1, .34)], st)]

    # ------------------------------------------------------------ estatísticas descritivas
    if "descriptive" in sec and stats.get("descriptive"):
        h1("Estatísticas descritivas", 170)
        story.append(_p("Medidas calculadas apenas com valores válidos. Variáveis qualitativas e identificadores não possuem média ou desvio.", st["intro"]))
        desc = stats["descriptive"]
        pnames = [k for k in desc[0].get("percentiles", {})]
        rows_def = [("Observações válidas", "n_valid", 0), ("Ausentes", "n_missing", 0), ("Média", "mean", 2), ("Mediana", "median", 2), ("Moda", "mode", 2), ("Mínimo", "min", 2), ("Máximo", "max", 2),
                    ("Amplitude", "range", 2), ("Variância", "variance", 2), ("Desvio padrão", "std", 2), ("Coef. de variação", "cv", 3), ("Q1", "q1", 2), ("Q3", "q3", 2), ("IIQ", "iqr", 2),
                    ("Assimetria", "skewness", 3), ("Curtose", "kurtosis", 3)]
        for i in range(0, len(desc), 4):
            grp = desc[i:i + 4]
            rows = [["Medida"] + [d["column"] for d in grp]]
            for label, key, nd in rows_def:
                rows.append([label] + [num(d.get(key), nd) if key not in ("n_valid", "n_missing") else d.get(key) for d in grp])
            for pk in pnames:
                rows.append([f"Percentil {pk[1:]}"] + [num(d.get("percentiles", {}).get(pk), 2) for d in grp])
            w = [PAGE_W * .28] + [PAGE_W * .72 / len(grp)] * len(grp)
            story += [KeepTogether([_table(rows, w, st)]), Spacer(1, 4 * mm)]
        warns = [(d["column"], w) for d in desc for w in d["warnings"]]
        for c, w in warns:
            story.append(_p(f"• {c}: {w}", st["small"]))
    if stats.get("frequencies") and ("frequencies" in sec):
        story += [CondPageBreak(45 * mm), Paragraph("Tabelas de frequência", st["h2"])]
        for f in stats["frequencies"]:
            rows = [[f"{f['column']}", "Frequência", "%"]] + [[x["value"], x["count"], pct(x["pct"])] for x in f["top"]]
            if f.get("other"):
                rows.append([f"Outras {f['other']['n_categories']} categorias", f["other"]["count"], ""])
            story += [KeepTogether([_table(rows, [PAGE_W * .5, PAGE_W * .25, PAGE_W * .25], st),
                                    _p(f"{f['n_unique']} categoria(s); {f['n_missing']} ausente(s); moda: {f.get('mode', '—')}" + (" (ordem definida pelo usuário)" if f["ordered"] else ""), st["small"])]), Spacer(1, 3 * mm)]

    # ------------------------------------------------------------ distribuições
    dist = stats.get("distributions") or []
    if ("distributions" in sec or "charts" in sec) and dist:
        h1("Análise das distribuições", 95)
        q = [d for d in dist if d["kind"] == "quantitative" and d.get("histogram")][:MAX_QUANT_CHARTS]
        for d in q:
            story.append(KeepTogether([_side(charts.histogram(d["column"], d), charts.boxplot(d["column"], d["boxplot"])), Spacer(1, 2 * mm)]))
        for d in [d for d in dist if d["kind"] == "qualitative" and d["frequencies"].get("top")][:MAX_QUAL_CHARTS]:
            story.append(KeepTogether([_img(charts.bars(d["column"], d["frequencies"]), PAGE_W * 0.7), Spacer(1, 2 * mm)]))
        if len([d for d in dist if d["kind"] == "quantitative"]) > MAX_QUANT_CHARTS:
            story.append(_p(f"Exibindo os gráficos das primeiras {MAX_QUANT_CHARTS} variáveis quantitativas; os dados completos estão no XLSX e na visualização do DataCheck.", st["small"]))

    # ------------------------------------------------------------ relações entre variáveis
    corr = stats.get("correlation")
    if "correlation" in sec and corr and corr.get("pairs"):
        h1("Relações entre variáveis", 135)
        story.append(_p(corr["warning"] + f" Método: {corr['method'].capitalize()}. Cada coeficiente usa os pares de valores válidos disponíveis (n por par abaixo).", st["body"]))
        story.append(_img(charts.heatmap(corr), PAGE_W * 0.75))
        story.append(_table([["Variável A", "Variável B", "r", "n", "Intensidade", "Direção"]] +
                            [[p["a"], p["b"], num(p["r"], 3), p["n"], p["strength"], p["direction"]] for p in corr["pairs"][:20]], [PAGE_W * f for f in (.24, .24, .1, .1, .17, .15)], st))
        if corr["excluded"]:
            story.append(_p("Excluídas da correlação: " + "; ".join(f"{e['column']} ({e['reason']})" for e in corr["excluded"]) + ".", st["small"]))
        for s in stats.get("scatter", []):
            story.append(KeepTogether([_img(charts.scatter(s), PAGE_W * 0.55), Spacer(1, 2 * mm)]))
    elif "correlation" in sec:
        h1("Relações entre variáveis")
        story.append(_p(stats.get("skipped", {}).get("correlation", "Não há pares de variáveis quantitativas com variação suficiente."), st["body"]))

    # ------------------------------------------------------------ valores extremos
    if "outliers" in sec and stats.get("outliers"):
        h1("Valores extremos", 60)
        story.append(_p("Critério: 1,5×IQR. Valores atípicos não são necessariamente erros.", st["intro"]))
        story.append(_table([["Variável", "Limite inferior", "Limite superior", "Qtde", "%", "Exemplos"]] +
                            [[x["column"], num(x.get("lower")), num(x.get("upper")), x.get("count", "—"), pct(x["pct"]) if x.get("pct") is not None else "—",
                              ", ".join(num(v) for v in x.get("examples", [])[:5]) or "—"] for x in stats["outliers"]], [PAGE_W * f for f in (.2, .14, .14, .08, .08, .36)], st))

    # ------------------------------------------------------------ temporal
    tm = stats.get("temporal")
    if "temporal" in sec and tm and tm.get("available"):
        h1("Análise temporal", 95)
        freq = {"D": "dia", "M": "mês", "Y": "ano"}[tm["frequency"]]
        story.append(_p(f"Coluna «{tm['date_column']}», agrupamento por {freq}. {tm['n_dates']} datas válidas entre {tm['start']} e {tm['end']}; {tm['n_gaps']} período(s) sem registros.", st["body"]))
        story.append(_img(charts.line("Registros por período", [(p["period"], p["count"]) for p in tm["count_series"]], "Registros", bar=True), PAGE_W))
        for vs in tm["value_series"]:
            story.append(_img(charts.line(f"Média de {vs['column']} por período", [(p["period"], p["mean"]) for p in vs["points"]], "Média"), PAGE_W))
        if tm["gaps"]:
            story.append(_p("Períodos sem registros: " + ", ".join(tm["gaps"][:30]) + ("…" if tm["n_gaps"] > 30 else ""), st["small"]))
    elif "temporal" in sec:
        h1("Análise temporal")
        story.append(_p(stats.get("skipped", {}).get("temporal") or (tm or {}).get("reason", "Não há coluna de datas válida."), st["body"]))

    # ------------------------------------------------------------ ausentes
    if "missing" in sec:
        m = stats["missing"]
        h1("Dados ausentes remanescentes")
        story.append(_p(f"{m['rows_with_missing']} registro(s) possuem ao menos um valor ausente; {m['complete_rows']} estão completos.", st["body"]))
        rem = [c for c in m["columns"] if c["n_missing"]]
        story.append(_table([["Variável", "Ausentes", "%"]] + [[c["column"], c["n_missing"], pct(c["pct"])] for c in rem], [PAGE_W * .5, PAGE_W * .25, PAGE_W * .25], st) if rem else _p("Nenhum valor ausente remanescente.", st["body"]))

    # ------------------------------------------------------------ observações e considerações
    h1("Principais observações")
    for ob in stats["observations"]:
        story.append(_p(f"• {ob}", st["body"]))
    h1("Considerações finais")
    story.append(_p("Este relatório descreve as características da base tratada com base nas estatísticas calculadas. Recomenda-se revisar as variáveis com assimetria acentuada, alta dispersão ou valores atípicos antes de análises que dependam de normalidade ou de medidas sensíveis a extremos.", st["body"]))
    story.append(Paragraph("Advertências e limitações", st["h2"]))
    for lim in stats["limitations"]:
        story.append(_p(f"• {lim}", st["body"]))
    story.append(Paragraph("Possíveis próximas análises", st["h2"]))
    for nx in ("Comparar grupos (por categoria ou período) nas variáveis de maior dispersão.", "Investigar a origem dos valores atípicos e dos dados ausentes remanescentes.",
               "Aprofundar as relações observadas com métodos apropriados ao objetivo do estudo."):
        story.append(_p(f"• {nx}", st["body"]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        if doc.page > 1:
            canvas.drawString(18 * mm, 9 * mm, f"DataCheck · {report_name}")
            canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Página {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                      title=report_name, author="DataCheck").build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
