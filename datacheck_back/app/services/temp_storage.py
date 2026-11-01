"""Arquivos temporários de upload.

Cada upload é gravado em um diretório privado (0700) com nome aleatório (o nome original
nunca vira caminho). O arquivo é apagado ao fim da análise, ao excluir a análise ou quando
expira (limpeza a cada upload e na inicialização).
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from app.core.config import get_settings


def _dir() -> Path:
    path = Path(get_settings().temp_dir)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _path(analysis_id: uuid.UUID) -> Path:
    return _dir() / f"{analysis_id}.upload"


def save(analysis_id: uuid.UUID, content: bytes) -> None:
    fd = os.open(_path(analysis_id), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(content)


def load(analysis_id: uuid.UUID) -> bytes | None:
    try:
        return _path(analysis_id).read_bytes()
    except FileNotFoundError:
        return None


def delete(analysis_id: uuid.UUID) -> None:
    _path(analysis_id).unlink(missing_ok=True)


def purge_expired() -> int:
    ttl = get_settings().upload_ttl_minutes * 60
    removed = 0
    for f in _dir().glob("*.upload"):
        if time.time() - f.stat().st_mtime > ttl:
            f.unlink(missing_ok=True)
            removed += 1
    return removed
