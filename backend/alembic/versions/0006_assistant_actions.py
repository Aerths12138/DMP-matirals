"""add AI assistant action execution receipts

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_action_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assistant_action_executions_user_id",
        "assistant_action_executions",
        ["user_id"],
    )
    op.create_index(
        "ix_assistant_action_executions_entity_id",
        "assistant_action_executions",
        ["entity_id"],
    )
    op.create_index(
        "ix_assistant_action_executions_created_at",
        "assistant_action_executions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistant_action_executions_created_at",
        table_name="assistant_action_executions",
    )
    op.drop_index(
        "ix_assistant_action_executions_entity_id",
        table_name="assistant_action_executions",
    )
    op.drop_index(
        "ix_assistant_action_executions_user_id",
        table_name="assistant_action_executions",
    )
    op.drop_table("assistant_action_executions")
