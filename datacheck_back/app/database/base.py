from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engines: dict[str, Engine] = {}


def get_engine() -> Engine:
    url = get_settings().database_url
    if url not in _engines:
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(engine, "connect")
            def _fk_on(dbapi_conn, _):  # integridade referencial também no SQLite (testes)
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
        _engines[url] = engine
    return _engines[url]


def get_db() -> Iterator[Session]:
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session
