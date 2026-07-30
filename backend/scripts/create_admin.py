"""Create the first production administrator from explicit environment values."""

import asyncio
import os
import uuid

from sqlalchemy import or_, select

from app.database import async_session
from app.models.permission import Role
from app.models.user import User
from app.utils.security import hash_password


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


async def create_admin() -> None:
    username = _required("ADMIN_USERNAME")
    password = _required("ADMIN_PASSWORD")
    email = _required("ADMIN_EMAIL")
    if len(password) < 12:
        raise SystemExit("ADMIN_PASSWORD must contain at least 12 characters")

    async with async_session() as db:
        existing = await db.scalar(
            select(User).where(
                or_(User.username == username, User.email == email)
            )
        )
        if existing is not None:
            print("The username or email already exists; no changes made.")
            return

        admin_role = await db.scalar(select(Role).where(Role.name == "admin"))
        if admin_role is None:
            raise SystemExit(
                "Admin role is missing. Run python -m scripts.init_roles first."
            )

        user = User(
            id=uuid.uuid4(),
            username=username,
            email=email,
            hashed_password=hash_password(password),
            display_name=username,
            is_active=True,
            is_approved=True,
            role_id=admin_role.id,
            department="IT",
        )
        db.add(user)
        await db.commit()
        print(f"Administrator {username!r} created.")


if __name__ == "__main__":
    asyncio.run(create_admin())
