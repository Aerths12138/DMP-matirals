"""Seed default roles and permissions — uses engine-level connection for reliability."""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic import command
from alembic.config import Config

from sqlalchemy import inspect, text

from app.database import engine, Base
from app.models import *  # noqa — register all models
from app.models.permission import Permission, Role

DEFAULT_PERMISSIONS = [
    "material:create", "material:read", "material:update", "material:delete",
    "property:create", "property:read", "property:update", "property:delete",
    "crystal_structure:create", "crystal_structure:read", "crystal_structure:update", "crystal_structure:delete",
    "experiment:create", "experiment:read", "experiment:update", "experiment:delete",
    "sample:create", "sample:read", "sample:update", "sample:delete",
    "characterization:create", "characterization:read", "characterization:update", "characterization:delete",
    "analysis:run", "analysis:read",
    "file:upload", "file:read", "file:delete",
    "import:create", "export:create",
    "user:create", "user:read", "user:update", "user:delete",
    "admin",
]

ROLES_CONFIG = {
    "admin": {"description": "Full system access", "permissions": "ALL"},
    "researcher": {
        "description": "Can create and manage own data",
        "permissions": [
            "material:create", "material:read", "material:update",
            "property:create", "property:read", "property:update",
            "crystal_structure:create", "crystal_structure:read", "crystal_structure:update",
            "experiment:create", "experiment:read", "experiment:update",
            "sample:create", "sample:read", "sample:update",
            "characterization:create", "characterization:read", "characterization:update",
            "analysis:run", "analysis:read",
            "file:upload", "file:read",
            "import:create", "export:create",
            "user:read",
        ],
    },
    "viewer": {
        "description": "Read-only access",
        "permissions": [
            "material:read", "property:read", "crystal_structure:read",
            "experiment:read", "sample:read", "characterization:read",
            "analysis:read", "file:read", "user:read",
        ],
    },
}




async def needs_legacy_stamp() -> bool:
    """Detect a complete pre-Alembic database that can be stamped safely."""
    try:
        async with engine.connect() as conn:
            table_names = set(
                await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
            )
            current_version = None
            if "alembic_version" in table_names:
                current_version = (
                    await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                ).scalar_one_or_none()
                table_names.remove("alembic_version")

        if current_version or not table_names:
            return False

        # A legacy database predates Alembic and later migrations. Only the
        # baseline tables must exist before it can be stamped at revision 0001.
        migration_created_tables = {
            "project_members",
            "metadata_templates",
            "unit_definitions",
            "assistant_action_executions",
            "assistant_entity_backups",
        }
        expected_tables = set(Base.metadata.tables) - migration_created_tables
        missing_tables = expected_tables - table_names
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise RuntimeError(
                "Database has no Alembic version and is missing expected tables: "
                f"{missing}"
            )
        return True
    finally:
        await engine.dispose()


def migrate_database(stamp_legacy: bool) -> None:
    """Upgrade a fresh, legacy, or already-versioned database to head."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if stamp_legacy:
        command.stamp(config, "0001")
    command.upgrade(config, "head")


async def init():
    async with engine.begin() as conn:
        # Check existing
        count = (await conn.execute(text("SELECT COUNT(*) FROM permissions"))).scalar()
        if count > 0:
            print("Roles already initialized — skipping.")
            return

        # Bulk insert permissions
        for codename in DEFAULT_PERMISSIONS:
            await conn.execute(
                text("INSERT INTO permissions (codename, description) VALUES (:code, :desc)"),
                {"code": codename, "desc": f"Can {codename.replace(':', ' ')}"},
            )

        # Get permission IDs
        perm_rows = (await conn.execute(text("SELECT id, codename FROM permissions"))).all()
        perm_map = {row[1]: row[0] for row in perm_rows}

        # Create roles
        for role_name, config in ROLES_CONFIG.items():
            result = await conn.execute(
                text("INSERT INTO roles (name, description) VALUES (:name, :desc) RETURNING id"),
                {"name": role_name, "desc": config["description"]},
            )
            role_id = result.scalar()

            perm_codes = DEFAULT_PERMISSIONS if config["permissions"] == "ALL" else config["permissions"]
            for code in perm_codes:
                await conn.execute(
                    text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"),
                    {"rid": role_id, "pid": perm_map[code]},
                )

    print("Roles and permissions initialized successfully.")


if __name__ == "__main__":
    legacy_database = asyncio.run(needs_legacy_stamp())
    migrate_database(legacy_database)
    asyncio.run(init())
