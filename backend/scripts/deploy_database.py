"""Prepare the production database during a Vercel deployment build."""

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import or_, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import async_session
from app.models.permission import Role
from app.models.user import User
from app.utils.security import hash_password
from scripts.init_roles import init, migrate_database, needs_legacy_stamp

DEFAULT_SECRET_KEY = "change-me-in-production-use-a-real-secret-key"


def validate_environment() -> None:
    if settings.is_sqlite:
        raise RuntimeError("Vercel deployment requires an external DATABASE_URL")
    if settings.SECRET_KEY == DEFAULT_SECRET_KEY:
        raise RuntimeError("Set a secure SECRET_KEY before deploying")


async def bootstrap_admin() -> None:
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip()
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@materials-dmp.local").strip()

    async with async_session() as session:
        existing = (
            await session.execute(
                select(User).where(or_(User.username == username, User.email == email))
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.username != username:
                raise RuntimeError(
                    f"BOOTSTRAP_ADMIN_EMAIL is already used by {existing.username}"
                )
            print("Bootstrap admin already exists - skipping.")
            return

        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        if len(password) < 12:
            raise RuntimeError(
                "Set BOOTSTRAP_ADMIN_PASSWORD to at least 12 characters for the first deploy"
            )

        admin_role = (
            await session.execute(select(Role).where(Role.name == "admin"))
        ).scalar_one()
        session.add(
            User(
                username=username,
                email=email,
                hashed_password=hash_password(password),
                display_name="Administrator",
                is_active=True,
                is_approved=True,
                role_id=admin_role.id,
            )
        )
        await session.commit()
        print(f"Bootstrap admin created: {username}")


def main() -> None:
    validate_environment()
    legacy_database = asyncio.run(needs_legacy_stamp())
    migrate_database(legacy_database)
    asyncio.run(init())
    asyncio.run(bootstrap_admin())


if __name__ == "__main__":
    main()
