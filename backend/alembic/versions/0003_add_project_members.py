"""add project members

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-17

"""
import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _legacy_project_members(connection) -> list[dict]:
    """Convert project owners and legacy JSON members to relationship rows."""
    user_rows = connection.execute(sa.text("SELECT id FROM users")).all()

    def uuid_key(value) -> str:
        try:
            return uuid.UUID(str(value)).hex
        except (TypeError, ValueError, AttributeError):
            return str(value)

    users_by_key = {uuid_key(row[0]): row[0] for row in user_rows}
    projects = connection.execute(
        sa.text("SELECT id, owner_id, members FROM projects")
    ).mappings()
    use_hex_ids = connection.dialect.name == "sqlite"
    rows: list[dict] = []

    for project in projects:
        seen: set[str] = set()

        def add_member(user_id, role: str) -> None:
            key = uuid_key(user_id)
            if key in seen or key not in users_by_key:
                return
            seen.add(key)
            member_id = uuid.uuid4()
            rows.append(
                {
                    "id": member_id.hex if use_hex_ids else member_id,
                    "project_id": project["id"],
                    "user_id": users_by_key[key],
                    "role": role,
                }
            )

        if project["owner_id"] is not None:
            add_member(project["owner_id"], "owner")

        legacy_members = project["members"] or []
        if isinstance(legacy_members, str):
            try:
                legacy_members = json.loads(legacy_members)
            except json.JSONDecodeError:
                legacy_members = []

        if isinstance(legacy_members, list):
            for member in legacy_members:
                if not isinstance(member, dict) or not member.get("user_id"):
                    continue
                role = "viewer" if member.get("role") == "viewer" else "editor"
                add_member(member["user_id"], role)

    return rows


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_project_members_project_user",
        ),
    )
    op.create_index(
        op.f("ix_project_members_project_id"),
        "project_members",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_members_user_id"),
        "project_members",
        ["user_id"],
        unique=False,
    )

    rows = _legacy_project_members(op.get_bind())
    if rows:
        op.get_bind().execute(
            sa.text(
                "INSERT INTO project_members "
                "(id, project_id, user_id, role, created_at, updated_at) "
                "VALUES (:id, :project_id, :user_id, :role, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            rows,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_members_user_id"), table_name="project_members")
    op.drop_index(op.f("ix_project_members_project_id"), table_name="project_members")
    op.drop_table("project_members")
