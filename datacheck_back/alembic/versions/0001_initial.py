"""Tabelas iniciais: users, analyses, validation_issues, analysis_feedback

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
NOW = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("sheet_name", sa.String(255)),
        sa.Column("total_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_columns", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_issues", sa.Integer, nullable=False, server_default="0"),
        sa.Column("affected_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Double),
        sa.Column("validation_config", JSONType),
        sa.Column("summary", JSONType),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])
    op.create_index("ix_analyses_status", "analyses", ["status"])
    op.create_index("ix_analyses_user_created", "analyses", ["user_id", "created_at"])

    op.create_table(
        "validation_issues",
        sa.Column("id", BigIntPK, primary_key=True, autoincrement=True),
        sa.Column("analysis_id", sa.Uuid, sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("column_name", sa.String(255), nullable=False),
        sa.Column("original_value", sa.Text),
        sa.Column("issue_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("suggestion", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
    )
    op.create_index("ix_issues_analysis_row", "validation_issues", ["analysis_id", "row_number"])
    op.create_index("ix_issues_analysis_type", "validation_issues", ["analysis_id", "issue_type"])

    op.create_table(
        "analysis_feedback",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("analysis_id", sa.Uuid, sa.ForeignKey("analyses.id", ondelete="SET NULL")),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usability_rating", sa.SmallInteger, nullable=False),
        sa.Column("usefulness_rating", sa.SmallInteger, nullable=False),
        sa.Column("would_use_again", sa.String(10), nullable=False),
        sa.Column("difficulties", sa.Text, nullable=False, server_default=""),
        sa.Column("suggestions", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint("usability_rating BETWEEN 1 AND 5", name="ck_feedback_usability"),
        sa.CheckConstraint("usefulness_rating BETWEEN 1 AND 5", name="ck_feedback_usefulness"),
        sa.CheckConstraint("would_use_again IN ('sim','talvez','nao')", name="ck_feedback_reuse"),
    )
    op.create_index("ix_analysis_feedback_analysis_id", "analysis_feedback", ["analysis_id"])
    op.create_index("ix_analysis_feedback_user_id", "analysis_feedback", ["user_id"])


def downgrade() -> None:
    op.drop_table("analysis_feedback")
    op.drop_table("validation_issues")
    op.drop_table("analyses")
    op.drop_table("users")
