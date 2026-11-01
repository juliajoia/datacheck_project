"""Armazenamento: uploads temporários (memória), resultados em cache e histórico (SQLite).

Arquivos enviados ficam apenas em memória, com prazo de expiração. O histórico guarda
indicadores; os valores das células só são gravados se o usuário optar (save_details).
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional

from app.core.config import get_settings
from app.core.errors import DataCheckError
from app.validators.base import Issue
from app.services.file_reader import LoadedTable, read_table

_lock = threading.Lock()


# ---------------------------------------------------------------- uploads


class UploadStore:
    MAX_ITEMS = 8

    def __init__(self):
        self._items: OrderedDict[str, dict] = OrderedDict()

    def _purge(self):
        ttl = get_settings().upload_ttl_seconds
        now = time.time()
        for key in [k for k, v in self._items.items() if now - v["ts"] > ttl]:
            del self._items[key]
        while len(self._items) > self.MAX_ITEMS:
            self._items.popitem(last=False)

    def add(self, content: bytes, filename: str) -> str:
        with _lock:
            self._purge()
            file_id = uuid.uuid4().hex
            self._items[file_id] = {"content": content, "filename": filename, "tables": {}, "ts": time.time()}
            self._purge()
            return file_id

    def _get(self, file_id: str) -> dict:
        self._purge()
        item = self._items.get(file_id)
        if not item:
            raise DataCheckError("Arquivo não encontrado ou expirado. Envie-o novamente.", 404)
        return item

    def table(self, file_id: str, sheet: Optional[str] = None) -> tuple[LoadedTable, str, int]:
        with _lock:
            item = self._get(file_id)
            key = sheet or ""
            if key not in item["tables"]:
                item["tables"][key] = read_table(item["content"], item["filename"], sheet)
            return item["tables"][key], item["filename"], len(item["content"])

    def delete(self, file_id: str) -> None:
        with _lock:
            self._items.pop(file_id, None)


class ResultStore:
    MAX_ITEMS = 30

    def __init__(self):
        self._items: OrderedDict[str, tuple[float, dict, list[Issue]]] = OrderedDict()

    def put(self, result: dict, issues: list[Issue]) -> None:
        with _lock:
            self._items[result["id"]] = (time.time(), result, issues)
            while len(self._items) > self.MAX_ITEMS:
                self._items.popitem(last=False)

    def get(self, analysis_id: str) -> Optional[tuple[dict, list[Issue]]]:
        with _lock:
            entry = self._items.get(analysis_id)
            if not entry:
                return None
            if time.time() - entry[0] > get_settings().result_ttl_seconds:
                del self._items[analysis_id]
                return None
            return entry[1], entry[2]

    def delete(self, analysis_id: str) -> None:
        with _lock:
            self._items.pop(analysis_id, None)


upload_store = UploadStore()
result_store = ResultStore()


# ---------------------------------------------------------------- SQLite


def _conn() -> sqlite3.Connection:
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY, created_at TEXT, filename TEXT, sheet TEXT,
            n_rows INTEGER, n_cols INTEGER, occurrences INTEGER, affected_rows INTEGER,
            score REAL, score_label TEXT, result_json TEXT, issues_json TEXT);
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY, created_at TEXT, ease INTEGER, usefulness INTEGER,
            would_reuse TEXT, difficulties TEXT, suggestions TEXT, analysis_id TEXT);
        """
    )
    return conn


def save_analysis(result: dict, issues: list[Issue], save_details: bool) -> None:
    from dataclasses import asdict

    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO analyses VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (result["id"], result["created_at"], result["filename"], result["sheet"],
             result["metrics"]["total_rows"], result["metrics"]["total_columns"],
             result["metrics"]["total_occurrences"], result["metrics"]["affected_rows"],
             result["score"]["value"], result["score"]["label"], json.dumps(result),
             json.dumps([asdict(i) for i in issues]) if save_details else None),
        )


def list_analyses() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, created_at, filename, sheet, n_rows, n_cols, occurrences, affected_rows, "
            "score, score_label, issues_json IS NOT NULL AS has_details "
            "FROM analyses ORDER BY created_at DESC").fetchall()
    return [dict(r) | {"has_details": bool(r["has_details"])} for r in rows]


def load_analysis(analysis_id: str) -> Optional[tuple[dict, Optional[list[Issue]]]]:
    cached = result_store.get(analysis_id)
    if cached:
        return cached
    with _conn() as c:
        row = c.execute("SELECT result_json, issues_json FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        return None
    issues = [Issue(**d) for d in json.loads(row["issues_json"])] if row["issues_json"] else None
    return json.loads(row["result_json"]), issues


def delete_analysis(analysis_id: str) -> None:
    result_store.delete(analysis_id)
    with _conn() as c:
        c.execute("DELETE FROM analyses WHERE id=?", (analysis_id,))


def save_feedback(data: dict) -> str:
    fid = uuid.uuid4().hex
    with _conn() as c:
        c.execute(
            "INSERT INTO feedback VALUES (?,?,?,?,?,?,?,?)",
            (fid, datetime.now(timezone.utc).isoformat(timespec="seconds"), data["ease"],
             data["usefulness"], data["would_reuse"], data["difficulties"],
             data["suggestions"], data.get("analysis_id")),
        )
    return fid


def list_feedback() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM feedback ORDER BY created_at DESC")]
