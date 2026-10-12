"""add source-citable research knowledge chunks

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("files") as batch_op:
        batch_op.add_column(sa.Column("knowledge_status", sa.String(length=20), nullable=False, server_default="pending"))
        batch_op.add_column(sa.Column("knowledge_chunk_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("knowledge_indexed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("knowledge_error", sa.Text(), nullable=True))
        batch_op.create_index("ix_files_knowledge_status", ["knowledge_status"])

    op.create_table(
        "research_knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="text"),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "chunk_index", name="uq_research_knowledge_file_chunk"),
    )
    op.create_index("ix_research_knowledge_chunks_file_id", "research_knowledge_chunks", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_research_knowledge_chunks_file_id", table_name="research_knowledge_chunks")
    op.drop_table("research_knowledge_chunks")
    with op.batch_alter_table("files") as batch_op:
        batch_op.drop_index("ix_files_knowledge_status")
        batch_op.drop_column("knowledge_error")
        batch_op.drop_column("knowledge_indexed_at")
        batch_op.drop_column("knowledge_chunk_count")
        batch_op.drop_column("knowledge_status")
