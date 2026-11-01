"""Perfil da planilha: tipos inferidos e pré-visualização."""
from __future__ import annotations

from app.core.config import DEFAULT_MARKERS
from app.core.parsing import missing_mask, parse_date, parse_number
from app.services.cleaning.variable_types import classify_column
from app.services.file_reader import LoadedTable

_DTYPE_LABELS = {"integer": "inteiro", "decimal": "decimal", "date": "data", "text": "texto", "empty": "vazio"}
import re

_LAT = re.compile(r"^lat(itude)?$", re.I)
_LON = re.compile(r"^(lon|lng|long|longitude)$", re.I)
THRESHOLD = 0.9


def infer_column(series) -> dict:
    present = series[~missing_mask(series, DEFAULT_MARKERS)]
    total = len(present)
    if total == 0:
        dtype = "empty"
    else:
        counts = present.value_counts()
        nums = {v: parse_number(v) for v in counts.index}
        n_num = sum(c for v, c in counts.items() if nums[v] is not None)
        n_date = sum(c for v, c in counts.items() if parse_date(v) is not None)
        if n_num / total >= THRESHOLD:
            all_int = all(
                nums[v] is None or (nums[v].is_integer() and not any(ch in v for ch in ".,eE"))
                for v in counts.index
            )
            dtype = "integer" if all_int else "decimal"
        elif n_date / total >= THRESHOLD:
            dtype = "date"
        else:
            dtype = "text"
    return {
        "name": series.name,
        "dtype": dtype,
        "dtype_label": _DTYPE_LABELS[dtype],
        "non_missing": int(total),
    }


def suggest_config(columns: list[dict]) -> dict:
    """Sugestão inicial para o usuário revisar: nada é aplicado sem ele confirmar."""
    lat = next((c["name"] for c in columns if _LAT.match(c["name"].strip())), None)
    lon = next((c["name"] for c in columns if _LON.match(c["name"].strip())), None)
    geo = {c for c in (lat, lon) if c}
    return {
        "types": {c["name"]: c["dtype"] for c in columns if c["dtype"] in ("integer", "decimal") and c["name"] not in geo},
        "dates": [c["name"] for c in columns if c["dtype"] == "date"],
        "lat_column": lat,
        "lon_column": lon,
    }


def build_profile(table: LoadedTable, filename: str, size_bytes: int, preview_rows: int = 10) -> dict:
    df = table.df
    head = df.head(preview_rows)
    columns = []
    for c in df.columns:
        col = infer_column(df[c])
        stat = classify_column(df[c], c, DEFAULT_MARKERS)   # tipo estatístico provável (editável no tratamento)
        columns.append({**col, "stat_type": stat["stat_type"], "stat_label": stat["label"], "stat_reasons": stat["reasons"]})
    return {
        "filename": filename,
        "size_bytes": size_bytes,
        "sheets": table.sheets,
        "selected_sheet": table.sheet,
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
        "encoding": table.encoding,
        "delimiter": table.delimiter,
        "columns": columns,
        "suggested_config": suggest_config(columns),
        "preview": {
            "columns": list(df.columns),
            "lines": [table.first_data_line + i for i in head.index],
            "rows": head.values.tolist(),
        },
    }
