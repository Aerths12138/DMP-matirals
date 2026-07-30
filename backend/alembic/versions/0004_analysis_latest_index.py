"""enforce one latest analysis result per type

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY characterization_id, analysis_type
                           ORDER BY created_at DESC, id DESC
                       ) AS version_rank
                FROM analysis_results
                WHERE is_latest
            )
            UPDATE analysis_results
            SET is_latest = false
            WHERE id IN (
                SELECT id FROM ranked WHERE version_rank > 1
            )
            """
        )
    )
    op.create_index(
        "uq_analysis_latest_per_type",
        "analysis_results",
        ["characterization_id", "analysis_type"],
        unique=True,
        sqlite_where=sa.text("is_latest = 1"),
        postgresql_where=sa.text("is_latest"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_analysis_latest_per_type",
        table_name="analysis_results",
    )
