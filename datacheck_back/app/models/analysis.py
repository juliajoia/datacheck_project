from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (JSON, BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer,
                        SmallInteger, String, Text, Uuid, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now,
                                                 server_default=func.now())


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    file_size: Mapped[int] = mapped_column(BigInteger)
    sheet_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    total_columns: Mapped[int] = mapped_column(Integer, default=0)
    total_issues: Mapped[int] = mapped_column(Integer, default=0)
    affected_rows: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    validation_config: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    summary: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)  # métricas, insights, regras
    status: Mapped[str] = mapped_column(String(20), default="uploaded", index=True)
    # Tratamento: analyzed | in_treatment | pending | ready_for_eda | eda_generated
    workflow_status: Mapped[str] = mapped_column(String(20), default="analyzed", server_default="analyzed")
    current_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = base não armazenada
    column_types: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)  # classificação manual das variáveis
    data_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    issues: Mapped[list["ValidationIssue"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", passive_deletes=True)


class ValidationIssue(Base):
    __tablename__ = "validation_issues"
    __table_args__ = (
        Index("ix_issues_analysis_row", "analysis_id", "row_number"),
        Index("ix_issues_analysis_type", "analysis_id", "issue_type"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    row_number: Mapped[int] = mapped_column(Integer)
    column_name: Mapped[str] = mapped_column(String(255))
    original_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # None = não armazenado
    issue_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    analysis: Mapped[Analysis] = relationship(back_populates="issues")


class AnalysisFeedback(Base):
    """Feedback sobrevive à exclusão da análise (analysis_id vira NULL); some se o usuário for removido."""

    __tablename__ = "analysis_feedback"
    __table_args__ = (
        CheckConstraint("usability_rating BETWEEN 1 AND 5", name="ck_feedback_usability"),
        CheckConstraint("usefulness_rating BETWEEN 1 AND 5", name="ck_feedback_usefulness"),
        CheckConstraint("would_use_again IN ('sim','talvez','nao')", name="ck_feedback_reuse"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    usability_rating: Mapped[int] = mapped_column(SmallInteger)
    usefulness_rating: Mapped[int] = mapped_column(SmallInteger)
    would_use_again: Mapped[str] = mapped_column(String(10))
    difficulties: Mapped[str] = mapped_column(Text, default="")
    suggestions: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
