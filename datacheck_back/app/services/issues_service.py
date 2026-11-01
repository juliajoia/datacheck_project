"""Consulta paginada, filtrada e ordenada das ocorrências de uma análise."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.catalog import SEVERITY_RANK, category_label, SEVERITY_LABELS
from app.models import ValidationIssue as V
from app.schemas.analysis import IssueFilters
from app.validators.base import Issue

NOT_STORED = "(não armazenado)"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build(analysis_id: uuid.UUID, f: IssueFilters) -> Select:
    stmt = select(V).where(V.analysis_id == analysis_id)
    if f.columns:
        stmt = stmt.where(V.column_name.in_(f.columns))
    if f.categories:
        stmt = stmt.where(V.issue_type.in_(f.categories))
    if f.severities:
        stmt = stmt.where(V.severity.in_(f.severities))
    if f.q and f.q.strip():
        like = f"%{_escape(f.q.strip())}%"
        conds = [V.original_value.ilike(like, escape="\\"), V.column_name.ilike(like, escape="\\"),
                 V.description.ilike(like, escape="\\"), V.suggestion.ilike(like, escape="\\")]
        if f.q.strip().isdigit():
            conds.append(V.row_number == int(f.q.strip()))
        stmt = stmt.where(or_(*conds))
    severity_rank = case(SEVERITY_RANK, value=V.severity)
    sort_col = {"row": V.row_number, "column": V.column_name, "value": V.original_value,
                "category": V.issue_type, "severity": severity_rank}.get(f.sort_by, V.row_number)
    order = sort_col.desc() if f.descending else sort_col.asc()
    return stmt.order_by(order, V.row_number, V.id)


def serialize(row: V) -> dict:
    return {"id": row.id, "row": row.row_number, "column": row.column_name,
            "value": row.original_value if row.original_value is not None else NOT_STORED,
            "category": row.issue_type, "category_label": category_label(row.issue_type),
            "severity": row.severity, "severity_label": SEVERITY_LABELS[row.severity],
            "description": row.description, "suggestion": row.suggestion}


def page(db: Session, analysis_id: uuid.UUID, f: IssueFilters, page: int, page_size: int) -> dict:
    stmt = _build(analysis_id, f)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [serialize(r) for r in rows]}


def all_issues(db: Session, analysis_id: uuid.UUID, f: Optional[IssueFilters] = None) -> list[Issue]:
    rows = db.scalars(_build(analysis_id, f or IssueFilters())).yield_per(5000)
    return [Issue(r.row_number, r.column_name, r.original_value if r.original_value is not None else NOT_STORED,
                  r.issue_type, r.severity, r.description, r.suggestion) for r in rows]
