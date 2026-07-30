"""SQLAlchemy async engine, session factory, and declarative base.

Supports both SQLite (dev) and PostgreSQL (prod) via config.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

# Build kwargs based on database type
_engine_kwargs: dict = {"echo": settings.DEBUG}

if settings.is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    # SQLite uses NullPool - pool_size/max_overflow are not valid.
elif settings.storage_backend == "vercel_blob":
    # Serverless instances should use the database provider's pooled URL.
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
