"""Armazenamento privado das bases (versões) e dos relatórios.

Diretório 0700, arquivos 0600, nomes derivados de UUID (nunca do nome enviado pelo usuário).
O PostgreSQL guarda apenas as referências. A versão 0 (original) nunca é sobrescrita: cada
tratamento grava um novo arquivo.
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.core.errors import DataCheckError

ROW_COL = "__datacheck_row__"  # número da linha original, preservado entre versões


def root() -> Path:
    path = Path(get_settings().data_dir)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _resolve(reference: str) -> Path:
    base = root().resolve()
    path = (base / reference).resolve()
    if not path.is_relative_to(base):  # defesa contra referências adulteradas
        raise DataCheckError("Referência de arquivo inválida.", 400)
    return path


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def save_version(analysis_id: uuid.UUID, number: int, df: pd.DataFrame, row_numbers: list[int]) -> str:
    ref = f"versions/{analysis_id}/v{number}.csv"
    out = df.copy()
    out.insert(0, ROW_COL, [int(r) for r in row_numbers])
    _write(_resolve(ref), out.to_csv(index=False).encode("utf-8"))
    return ref


def load_version(reference: str) -> tuple[pd.DataFrame, list[int]]:
    path = _resolve(reference)
    if not path.exists():
        raise DataCheckError("Os dados desta versão não estão mais disponíveis (retenção expirada ou arquivo removido).", 410)
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, encoding="utf-8")
    rows = [int(x) for x in df.pop(ROW_COL)]
    return df.reset_index(drop=True), rows


def save_report_file(report_id: uuid.UUID, ext: str, data: bytes) -> str:
    ref = f"reports/{report_id}.{ext}"
    _write(_resolve(ref), data)
    return ref


def read_file(reference: str) -> bytes:
    path = _resolve(reference)
    if not path.exists():
        raise DataCheckError("O arquivo do relatório não está mais disponível.", 410)
    return path.read_bytes()


def delete_reference(reference: str | None) -> None:
    if reference:
        _resolve(reference).unlink(missing_ok=True)


def delete_analysis_versions(analysis_id: uuid.UUID) -> None:
    shutil.rmtree(_resolve(f"versions/{analysis_id}"), ignore_errors=True)
