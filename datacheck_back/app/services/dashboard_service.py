"""Indicadores do dashboard, calculados a partir das análises reais do usuário."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.catalog import category_label
from app.models import Analysis, User, ValidationIssue
from app.utils.dates import iso

RECENT_DAYS = 7
SERIES_DAYS = 30


def summary(db: Session, user: User) -> dict:
    done = (Analysis.user_id == user.id, Analysis.status == "completed")
    total, rows, issues, avg = db.execute(
        select(func.count(), func.coalesce(func.sum(Analysis.total_rows), 0),
               func.coalesce(func.sum(Analysis.total_issues), 0), func.avg(Analysis.quality_score)).where(*done)
    ).one()
    since = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    recent = db.scalar(select(func.count()).where(*done, Analysis.completed_at >= since))
    return {"total_analyses": total, "total_rows": int(rows), "total_issues": int(issues),
            "recent_analyses": recent, "recent_days": RECENT_DAYS,
            "average_score": round(float(avg), 1) if avg is not None else None}


def charts(db: Session, user: User) -> dict:
    done = (Analysis.user_id == user.id, Analysis.status == "completed")
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=SERIES_DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    stamps = db.scalars(select(Analysis.completed_at).where(*done, Analysis.completed_at >= start)).all()
    per_day = Counter((s if s.tzinfo else s.replace(tzinfo=timezone.utc)).date() for s in stamps)
    series = [{"date": (start + timedelta(days=i)).date().isoformat(),
               "count": per_day.get((start + timedelta(days=i)).date(), 0)} for i in range(SERIES_DAYS)]

    by_cat = db.execute(
        select(ValidationIssue.issue_type, func.count())
        .join(Analysis, Analysis.id == ValidationIssue.analysis_id).where(*done)
        .group_by(ValidationIssue.issue_type).order_by(func.count().desc())).all()

    latest = db.scalars(select(Analysis).where(*done).order_by(Analysis.completed_at.desc()).limit(10)).all()
    return {
        "analyses_over_time": series,
        "issues_by_category": [{"category": c, "label": category_label(c), "count": n} for c, n in by_cat],
        "recent_quality": [{"id": str(a.id), "filename": a.filename, "score": a.quality_score,
                            "completed_at": iso(a.completed_at)} for a in reversed(latest)],
    }
