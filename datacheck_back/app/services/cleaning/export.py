"""Exportação da base tratada (CSV/XLSX), refletindo exatamente a versão confirmada pelo usuário."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.core.errors import DataCheckError
from app.core.parsing import missing_mask, parse_date, parse_number
from app.services.cleaning.stats import infer_decimal_mode
from app.services.cleaning.variable_types import QUANT
from app.services.reports import HEADER_FILL, safe

ENCODINGS = {"utf-8": "utf-8", "utf-8-sig": "utf-8-sig", "latin-1": "latin-1", "cp1252": "cp1252"}
DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|"}


def _reformat_number(text: str, target: str, source_mode: str) -> str:
    n = parse_number(text, source_mode)
    if n is None:
        return text
    raw = text.strip()
    sep = "," if (source_mode == "comma" or (source_mode == "auto" and "," in raw and raw.rfind(",") > raw.rfind("."))) else "."
    dec = len(raw.rsplit(sep, 1)[1]) if sep in raw and "e" not in raw.lower() else 0
    out = f"{n:.{dec}f}" if dec else str(int(n)) if float(n).is_integer() else repr(n)
    return out.replace(".", ",") if target == "comma" else out


def export_csv(df: pd.DataFrame, stat: dict[str, dict], markers: list[str], decimal_cfg: str, *,
               delimiter: str = "comma", encoding: str = "utf-8-sig", decimal: str = "keep") -> bytes:
    if delimiter not in DELIMITERS or encoding not in ENCODINGS or decimal not in ("keep", "comma", "dot"):
        raise DataCheckError("Opção de exportação CSV inválida.", 422)
    out = df.copy()
    for col in out.columns:
        info = stat.get(col)
        if info and info["stat_type"] in QUANT and decimal != "keep":
            mode = infer_decimal_mode(out[col][~missing_mask(out[col], markers)].str.strip(), decimal_cfg)
            out[col] = out[col].map(lambda v: v if v == "" else _reformat_number(v, decimal, mode))
        elif not info or info["stat_type"] not in QUANT:
            out[col] = out[col].map(safe)  # texto que parece fórmula recebe apóstrofo
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=DELIMITERS[delimiter], lineterminator="\r\n")
    w.writerow([safe(c) for c in out.columns])
    w.writerows(out.itertuples(index=False, name=None))
    try:
        return buf.getvalue().encode(ENCODINGS[encoding])
    except UnicodeEncodeError:
        raise DataCheckError(f"Há caracteres que a codificação {encoding} não suporta. Use UTF-8.", 422)


def export_xlsx(df: pd.DataFrame, stat: dict[str, dict], markers: list[str], decimal_cfg: str,
                treatment_summary: dict[str, Any] | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Base tratada"
    ws.append([safe(c) for c in df.columns])
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), HEADER_FILL
    modes = {c: infer_decimal_mode(df[c][~missing_mask(df[c], markers)].str.strip(), decimal_cfg)
             for c in df.columns if stat.get(c, {}).get("stat_type") in QUANT}
    for rec in df.itertuples(index=False, name=None):
        row: list[Any] = []
        for col, v in zip(df.columns, rec):
            st = stat.get(col, {}).get("stat_type")
            if v == "":
                row.append(None)
            elif st in QUANT and parse_number(v, modes[col]) is not None:
                n = parse_number(v, modes[col])
                row.append(int(n) if st == "quant_discrete" and float(n).is_integer() else n)
            elif st == "temporal" and parse_date(v) is not None:
                row.append(parse_date(v))
            else:
                row.append(safe(v))  # identificadores e textos permanecem texto (zeros à esquerda preservados)
        ws.append(row)
    for j, col in enumerate(df.columns, start=1):
        if stat.get(col, {}).get("stat_type") == "temporal":
            for cell in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                if isinstance(cell[0].value, (date, datetime)):
                    cell[0].number_format = "yyyy-mm-dd"
    ws.freeze_panes = "A2"
    if treatment_summary:
        sh = wb.create_sheet("Resumo do tratamento")
        for k, v in treatment_summary.items():
            sh.append([k, v if not isinstance(v, (list, dict)) else str(v)])
        for r in sh.iter_rows(max_col=1):
            r[0].font = Font(bold=True)
        sh.column_dimensions["A"].width = 38
        sh.column_dimensions["B"].width = 70
        for r in sh.iter_rows(min_col=2, max_col=2):
            r[0].alignment = Alignment(wrap_text=True, vertical="top")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
