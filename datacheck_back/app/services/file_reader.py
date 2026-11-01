"""Leitura segura de CSV e XLSX.

Todo o conteúdo é lido como texto. Fórmulas do Excel nunca são calculadas: o
openpyxl é aberto com data_only=True, que devolve apenas o último valor
armazenado na célula.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from app.core.errors import DataCheckError

ALLOWED_EXTENSIONS = (".csv", ".xlsx")
MAX_UNCOMPRESSED_XLSX_BYTES = 300 * 1024 * 1024  # proteção contra "zip bomb"
MAX_ROWS = 500_000
MAX_COLUMNS = 1_000


@dataclass
class LoadedTable:
    df: pd.DataFrame  # tudo como texto, índice 0..n-1
    header_line: int  # linha (1-based) do cabeçalho no arquivo original
    sheets: list[str] = field(default_factory=list)
    sheet: Optional[str] = None
    encoding: Optional[str] = None
    delimiter: Optional[str] = None

    @property
    def first_data_line(self) -> int:
        """Número da linha original do primeiro registro."""
        return self.header_line + 1


def read_table(content: bytes, filename: str, sheet: Optional[str] = None) -> LoadedTable:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DataCheckError(
            "Formato não suportado. Envie um arquivo .csv ou .xlsx "
            "(para .xls, abra no Excel e salve como .xlsx).",
            415,
        )
    if not content:
        raise DataCheckError("O arquivo está vazio.", 422)
    if ext == ".csv":
        return _read_csv(content)
    return _read_xlsx(content, sheet)


# ---------------------------------------------------------------- CSV


def _decode(content: bytes) -> tuple[str, str]:
    if b"\x00" in content[:4096]:
        raise DataCheckError(
            "O conteúdo não parece um CSV de texto. Verifique se o arquivo não está "
            "corrompido ou em outro formato.",
            422,
        )
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1"), "latin-1"


def _detect_delimiter(text: str) -> str:
    header = next((ln for ln in text.splitlines() if ln.strip()), "")
    counts = {d: header.count(d) for d in (",", ";", "\t", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def _read_csv(content: bytes) -> LoadedTable:
    text, encoding = _decode(content)
    if not text.strip():
        raise DataCheckError("O arquivo está vazio.", 422)
    delimiter = _detect_delimiter(text)
    try:
        raw = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            header=None,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=False,
            on_bad_lines="error",
            engine="python",
        )
    except pd.errors.EmptyDataError:
        raise DataCheckError("O arquivo está vazio.", 422)
    except (pd.errors.ParserError, ValueError, csv_error()) as exc:
        raise DataCheckError(
            "Não foi possível ler o CSV: há linhas com quantidade de colunas diferente "
            "do cabeçalho ou aspas mal fechadas. Revise o arquivo e tente novamente.",
            422,
        ) from exc
    rows = raw.fillna("").values.tolist()
    table = _build_table(rows)
    table.encoding = encoding
    table.delimiter = delimiter
    return table


def csv_error():
    import csv

    return csv.Error


# ---------------------------------------------------------------- XLSX


def _check_zip(content: bytes) -> None:
    if not content.startswith(b"PK"):
        raise DataCheckError(
            "O arquivo não é um .xlsx válido (pode estar corrompido ou ter outra extensão).",
            422,
        )
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if sum(i.file_size for i in zf.infolist()) > MAX_UNCOMPRESSED_XLSX_BYTES:
                raise DataCheckError("A planilha é grande demais para ser processada.", 413)
    except zipfile.BadZipFile as exc:
        raise DataCheckError("O arquivo .xlsx está corrompido e não pôde ser aberto.", 422) from exc


def _load_workbook(content: bytes):
    import openpyxl

    _check_zip(content)
    try:
        return openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except DataCheckError:
        raise
    except Exception as exc:  # openpyxl lança vários tipos de erro
        raise DataCheckError("Não foi possível abrir a planilha. O arquivo pode estar corrompido.", 422) from exc


def _cell_to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == time(0) else v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v)


def _read_xlsx(content: bytes, sheet: Optional[str]) -> LoadedTable:
    wb = _load_workbook(content)
    try:
        sheets = [ws.title for ws in wb.worksheets if ws.sheet_state == "visible"] or wb.sheetnames
        if not sheets:
            raise DataCheckError("A planilha não possui abas.", 422)
        chosen = sheet or sheets[0]
        if chosen not in wb.sheetnames:
            raise DataCheckError(f"A aba «{chosen}» não existe neste arquivo.", 422)
        rows: list[list[str]] = []
        try:
            for r in wb[chosen].iter_rows(values_only=True):
                rows.append([_cell_to_str(c) for c in r])
                if len(rows) > MAX_ROWS + 1:
                    raise DataCheckError(f"A aba possui mais de {MAX_ROWS:,} linhas.".replace(",", "."), 413)
        except DataCheckError:
            raise
        except Exception as exc:
            raise DataCheckError("Falha ao ler o conteúdo da aba. O arquivo pode estar corrompido.", 422) from exc
    finally:
        wb.close()
    table = _build_table(rows)
    table.sheets = sheets
    table.sheet = chosen
    return table


# ---------------------------------------------------------------- comum


def _build_table(rows: list[list[str]]) -> LoadedTable:
    width = max((len(r) for r in rows), default=0)
    if width > MAX_COLUMNS:
        raise DataCheckError(f"A planilha possui mais de {MAX_COLUMNS} colunas.", 413)
    rows = [r + [""] * (width - len(r)) for r in rows]
    # Cabeçalho = primeira linha com algum conteúdo; linhas finais em branco são descartadas.
    header_idx = next((i for i, r in enumerate(rows) if any(c.strip() for c in r)), None)
    if header_idx is None:
        raise DataCheckError("O arquivo está vazio.", 422)
    while rows and not any(c.strip() for c in rows[-1]):
        rows.pop()
    header = _clean_header(rows[header_idx])
    data = rows[header_idx + 1 :]
    if not data:
        raise DataCheckError("O arquivo possui apenas o cabeçalho e nenhum registro.", 422)
    df = pd.DataFrame(data, columns=header, dtype=str).reset_index(drop=True)
    return LoadedTable(df=df, header_line=header_idx + 1)


def _clean_header(raw: list[str]) -> list[str]:
    names: list[str] = []
    seen: dict[str, int] = {}
    for i, name in enumerate(raw):
        name = name.strip() or f"coluna_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        names.append(name)
    return names
