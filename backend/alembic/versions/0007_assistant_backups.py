"""add temporary AI mutation backups

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_entity_backups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action_execution_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("entity_name", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("post_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("restored_at", sa.DateTime(), nullable=True),
        sa.Column("restored_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["action_execution_id"],
            ["assistant_action_executions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["restored_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_execution_id"),
    )
    op.create_index(
        "ix_assistant_entity_backups_action_execution_id",
        "assistant_entity_backups",
        ["action_execution_id"],
    )
    op.create_index(
        "ix_assistant_entity_backups_user_id",
        "assistant_entity_backups",
        ["user_id"],
    )
    op.create_index(
        "ix_assistant_entity_backups_entity_type",
        "assistant_entity_backups",
        ["entity_type"],
    )
    op.create_index(
        "ix_assistant_entity_backups_entity_id",
        "assistant_entity_backups",
        ["entity_id"],
    )
    op.create_index(
        "ix_assistant_entity_backups_created_at",
        "assistant_entity_backups",
        ["created_at"],
    )
    op.create_index(
        "ix_assistant_entity_backups_expires_at",
        "assistant_entity_backups",
        ["expires_at"],
    )
    op.create_index(
        "ix_assistant_entity_backups_restored_at",
        "assistant_entity_backups",
        ["restored_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_entity_backups_restored_at", table_name="assistant_entity_backups")
    op.drop_index("ix_assistant_entity_backups_expires_at", table_name="assistant_entity_backups")
    op.drop_index("ix_assistant_entity_backups_created_at", table_name="assistant_entity_backups")
    op.drop_index("ix_assistant_entity_backups_entity_id", table_name="assistant_entity_backups")
    op.drop_index("ix_assistant_entity_backups_entity_type", table_name="assistant_entity_backups")
    op.drop_index("ix_assistant_entity_backups_user_id", table_name="assistant_entity_backups")
    op.drop_index(
        "ix_assistant_entity_backups_action_execution_id",
        table_name="assistant_entity_backups",
    )
    op.drop_table("assistant_entity_backups")
