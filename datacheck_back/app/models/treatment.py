"""Versões da base, operações de tratamento e relatórios EDA."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.analysis import JSONType


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisVersion(Base):
    """Snapshot imutável da base. A versão 0 é a original (nunca sobrescrita)."""

    __tablename__ = "analysis_versions"
    __table_args__ = (UniqueConstraint("analysis_id", "version_number", name="uq_version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    parent_version_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    label: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="available")  # available | purged
    storage_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    total_columns: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    validation: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)  # resumo da validação desta versão
    exceptions: Mapped[Optional[list]] = mapped_column(JSONType, nullable=True)  # ocorrências aceitas com justificativa
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())


class CleaningOperation(Base):
    __tablename__ = "cleaning_operations"
    __table_args__ = (Index("ix_cleaning_ops_analysis_created", "analysis_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    version_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("analysis_versions.id", ondelete="CASCADE"), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(40))
    column_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    affected_rows: Mapped[int] = mapped_column(Integer, default=0)
    original_values: Mapped[Optional[list]] = mapped_column(JSONType, nullable=True)
    replacement_values: Mapped[Optional[list]] = mapped_column(JSONType, nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    from_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    to_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    undone: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())


class EdaReport(Base):
    __tablename__ = "eda_reports"
    __table_args__ = (Index("ix_eda_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    analysis_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_versions.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    report_name: Mapped[str] = mapped_column(String(255))
    configuration: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    summary_statistics: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | processing | completed | failed
    file_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # prefixo dos arquivos (.pdf/.xlsx)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    total_columns: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
