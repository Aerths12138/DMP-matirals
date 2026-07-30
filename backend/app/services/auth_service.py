"""Authentication business logic."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


async def authenticate(db: AsyncSession, username: str, password: str) -> User | None:
    """Verify credentials and return the user, or None."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user(db: AsyncSession, username: str, email: str, password: str, **kwargs) -> User:
    """Register a new user with hashed password."""
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        **kwargs,
    )
    db.add(user)
    await db.flush()
    return user


async def create_refresh_token_record(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Create a DB-persisted refresh token and return the JWT string."""
    token_str = create_refresh_token(user_id)
    record = RefreshToken(
        token=token_str,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(record)
    await db.flush()
    return token_str


async def revoke_refresh_token(db: AsyncSession, token_str: str) -> None:
    """Mark a refresh token as revoked."""
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token_str))
    token_record = result.scalar_one_or_none()
    if token_record:
        token_record.is_revoked = True
        await db.flush()


async def refresh_access_token(db: AsyncSession, refresh_token_str: str) -> tuple[str, str] | None:
    """Validate refresh token, issue new access + refresh token pair. Returns None if invalid."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == refresh_token_str,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    token_record = result.scalar_one_or_none()
    if token_record is None:
        return None

    # Revoke old token
    token_record.is_revoked = True

    # Issue new pair
    new_access = create_access_token(token_record.user_id)
    new_refresh = await create_refresh_token_record(db, token_record.user_id)
    return new_access, new_refresh
