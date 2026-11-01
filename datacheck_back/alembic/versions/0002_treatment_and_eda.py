"""Versões da base, operações de tratamento e relatórios EDA

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
NOW = sa.func.now()


def upgrade() -> None:
    op.add_column("analyses", sa.Column("workflow_status", sa.String(20), nullable=False, server_default="analyzed"))
    op.add_column("analyses", sa.Column("current_version", sa.Integer))
    op.add_column("analyses", sa.Column("column_types", JSONType))
    op.add_column("analyses", sa.Column("data_expires_at", sa.DateTime(timezone=True)))

    op.create_table(
        "analysis_versions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("analysis_id", sa.Uuid, sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("parent_version_number", sa.Integer),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("storage_reference", sa.String(255)),
        sa.Column("total_rows", sa.Integer, nullable=False),
        sa.Column("total_columns", sa.Integer, nullable=False),
        sa.Column("quality_score", sa.Double),
        sa.Column("validation", JSONType),
        sa.Column("exceptions", JSONType),
        sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.UniqueConstraint("analysis_id", "version_number", name="uq_version_number"),
    )
    op.create_index("ix_analysis_versions_analysis_id", "analysis_versions", ["analysis_id"])

    op.create_table(
        "cleaning_operations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("analysis_id", sa.Uuid, sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Uuid, sa.ForeignKey("analysis_versions.id", ondelete="CASCADE")),
        sa.Column("operation_type", sa.String(40), nullable=False),
        sa.Column("column_name", sa.String(255)),
        sa.Column("affected_rows", sa.Integer, nullable=False),
        sa.Column("original_values", JSONType),
        sa.Column("replacement_values", JSONType),
        sa.Column("method", sa.String(60)),
        sa.Column("parameters", JSONType),
        sa.Column("justification", sa.Text),
        sa.Column("from_version", sa.Integer),
        sa.Column("to_version", sa.Integer),
        sa.Column("undone", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_cleaning_ops_analysis_created", "cleaning_operations", ["analysis_id", "created_at"])

    op.create_table(
        "eda_reports",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("analysis_id", sa.Uuid, sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_version_id", sa.Uuid, sa.ForeignKey("analysis_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_name", sa.String(255), nullable=False),
        sa.Column("configuration", JSONType),
        sa.Column("summary_statistics", JSONType),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("file_reference", sa.String(255)),
        sa.Column("error_message", sa.Text),
        sa.Column("total_rows", sa.Integer, nullable=False),
        sa.Column("total_columns", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_eda_reports_analysis_id", "eda_reports", ["analysis_id"])
    op.create_index("ix_eda_user_created", "eda_reports", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("eda_reports")
    op.drop_table("cleaning_operations")
    op.drop_table("analysis_versions")
    for c in ("data_expires_at", "column_types", "current_version", "workflow_status"):
        op.drop_column("analyses", c)
