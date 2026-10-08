"""add generic characterization measurement datasets

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "measurement_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("characterization_id", sa.Uuid(), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("x_name", sa.String(length=100), nullable=False),
        sa.Column("x_unit", sa.String(length=50), nullable=True),
        sa.Column("series_schema", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["characterization_id"], ["characterizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_file_id"], ["files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_measurement_datasets_characterization_id",
        "measurement_datasets",
        ["characterization_id"],
    )
    op.create_index(
        "ix_measurement_datasets_source_file_id",
        "measurement_datasets",
        ["source_file_id"],
    )
    op.create_table(
        "measurement_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("x_value", sa.Float(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["measurement_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "sequence", name="uq_measurement_points_dataset_sequence"),
    )
    op.create_index(
        "ix_measurement_points_dataset_id",
        "measurement_points",
        ["dataset_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_measurement_points_dataset_id", table_name="measurement_points")
    op.drop_table("measurement_points")
    op.drop_index("ix_measurement_datasets_source_file_id", table_name="measurement_datasets")
    op.drop_index("ix_measurement_datasets_characterization_id", table_name="measurement_datasets")
    op.drop_table("measurement_datasets")
