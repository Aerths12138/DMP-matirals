"""add persisted AI assistant conversations

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assistant_conversations_user_id",
        "assistant_conversations",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_assistant_conversations_updated_at",
        "assistant_conversations",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistant_conversations_updated_at",
        table_name="assistant_conversations",
    )
    op.drop_index(
        "ix_assistant_conversations_user_id",
        table_name="assistant_conversations",
    )
    op.drop_table("assistant_conversations")
