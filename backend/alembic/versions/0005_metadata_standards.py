"""add project metadata standards

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metadata_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "entity_type",
            "name",
            name="uq_metadata_templates_project_entity_name",
        ),
    )
    op.create_index("ix_metadata_templates_project_id", "metadata_templates", ["project_id"])
    op.create_index("ix_metadata_templates_entity_type", "metadata_templates", ["entity_type"])

    op.create_table(
        "unit_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("quantity_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "symbol", name="uq_unit_definitions_project_symbol"),
    )
    op.create_index("ix_unit_definitions_project_id", "unit_definitions", ["project_id"])

    with op.batch_alter_table("samples") as batch_op:
        batch_op.add_column(sa.Column("metadata_template_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_samples_metadata_template_id",
            "metadata_templates",
            ["metadata_template_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_samples_metadata_template_id", ["metadata_template_id"])

    with op.batch_alter_table("characterizations") as batch_op:
        batch_op.add_column(sa.Column("metadata_template_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_characterizations_metadata_template_id",
            "metadata_templates",
            ["metadata_template_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_characterizations_metadata_template_id",
            ["metadata_template_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("characterizations") as batch_op:
        batch_op.drop_index("ix_characterizations_metadata_template_id")
        batch_op.drop_constraint("fk_characterizations_metadata_template_id", type_="foreignkey")
        batch_op.drop_column("metadata_template_id")
    with op.batch_alter_table("samples") as batch_op:
        batch_op.drop_index("ix_samples_metadata_template_id")
        batch_op.drop_constraint("fk_samples_metadata_template_id", type_="foreignkey")
        batch_op.drop_column("metadata_template_id")
    op.drop_index("ix_unit_definitions_project_id", table_name="unit_definitions")
    op.drop_table("unit_definitions")
    op.drop_index("ix_metadata_templates_entity_type", table_name="metadata_templates")
    op.drop_index("ix_metadata_templates_project_id", table_name="metadata_templates")
    op.drop_table("metadata_templates")
