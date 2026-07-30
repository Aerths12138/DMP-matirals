from types import SimpleNamespace

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register every model on Base.metadata
from app.api.deps import get_db
from app.database import Base
from app.main import create_app
from app.models.permission import Permission, Role
from app.models.user import User
from app.utils.security import create_access_token


@pytest_asyncio.fixture
async def api():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        read_permission = Permission(codename="material:read")
        create_permission = Permission(codename="material:create")
        update_permission = Permission(codename="material:update")
        export_permission = Permission(codename="export:create")
        experiment_read = Permission(codename="experiment:read")
        experiment_create = Permission(codename="experiment:create")
        experiment_update = Permission(codename="experiment:update")
        sample_read = Permission(codename="sample:read")
        sample_create = Permission(codename="sample:create")
        sample_update = Permission(codename="sample:update")
        property_read = Permission(codename="property:read")
        property_create = Permission(codename="property:create")
        property_update = Permission(codename="property:update")
        crystal_read = Permission(codename="crystal_structure:read")
        crystal_create = Permission(codename="crystal_structure:create")
        crystal_update = Permission(codename="crystal_structure:update")
        file_read = Permission(codename="file:read")
        file_upload = Permission(codename="file:upload")
        characterization_read = Permission(codename="characterization:read")
        characterization_create = Permission(codename="characterization:create")
        characterization_update = Permission(codename="characterization:update")
        analysis_read = Permission(codename="analysis:read")
        analysis_run = Permission(codename="analysis:run")
        user_read = Permission(codename="user:read")
        viewer_role = Role(
            name="viewer",
            permissions=[
                read_permission,
                experiment_read,
                sample_read,
                property_read,
                crystal_read,
                file_read,
                characterization_read,
                analysis_read,
                user_read,
            ],
        )
        researcher_role = Role(
            name="researcher",
            permissions=[
                read_permission,
                create_permission,
                update_permission,
                export_permission,
                experiment_read,
                experiment_create,
                experiment_update,
                sample_read,
                sample_create,
                property_read,
                property_create,
                property_update,
                crystal_read,
                crystal_create,
                crystal_update,
                file_read,
                file_upload,
                characterization_read,
                characterization_create,
                characterization_update,
                analysis_read,
                analysis_run,
                sample_update,
                user_read,
            ],
        )
        viewer = User(
            username="viewer",
            email="viewer@example.com",
            hashed_password="unused",
            is_approved=True,
            role=viewer_role,
        )
        researcher = User(
            username="researcher",
            email="researcher@example.com",
            hashed_password="unused",
            is_approved=True,
            role=researcher_role,
        )
        outsider = User(
            username="outsider",
            email="outsider@example.com",
            hashed_password="unused",
            is_approved=True,
            role=researcher_role,
        )
        pending = User(
            username="pending",
            email="pending@example.com",
            hashed_password="unused",
            is_approved=False,
        )
        session.add_all([viewer, researcher, outsider, pending])
        await session.commit()

        user_ids = {
            "viewer": viewer.id,
            "researcher": researcher.id,
            "pending": pending.id,
            "outsider": outsider.id,
        }

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.state.audit_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield SimpleNamespace(
            client=client,
            session_factory=session_factory,
            user_ids=user_ids,
            headers={
                name: {"Authorization": f"Bearer {create_access_token(user_id)}"}
                for name, user_id in user_ids.items()
            },
        )

    app.dependency_overrides.clear()
    await engine.dispose()
