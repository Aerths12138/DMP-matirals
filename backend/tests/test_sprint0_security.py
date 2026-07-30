import uuid

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog


async def test_material_export_uses_static_route(api):
    response = await api.client.get(
        "/api/v1/materials/export/csv",
        headers=api.headers["researcher"],
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


async def test_pending_user_cannot_list_materials(api):
    response = await api.client.get(
        "/api/v1/materials",
        headers=api.headers["pending"],
    )

    assert response.status_code == 403


async def test_viewer_cannot_create_material(api):
    response = await api.client.post(
        "/api/v1/materials",
        headers=api.headers["viewer"],
        json={"name": "Test alloy", "material_type": "metal"},
    )

    assert response.status_code == 403


async def test_user_cannot_read_or_update_another_user(api):
    target_id = api.user_ids["researcher"]

    get_response = await api.client.get(
        f"/api/v1/users/{target_id}",
        headers=api.headers["viewer"],
    )
    update_response = await api.client.put(
        f"/api/v1/users/{target_id}",
        headers=api.headers["viewer"],
        json={"display_name": "Unauthorized"},
    )

    assert get_response.status_code == 403
    assert update_response.status_code == 403


async def test_material_create_audit_records_actor(api):
    response = await api.client.post(
        "/api/v1/materials",
        headers=api.headers["researcher"],
        json={"name": "Audited alloy", "material_type": "metal"},
    )

    assert response.status_code == 201

    async with api.session_factory() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.entity_type == "materials")
        )
        audit_log = result.scalar_one()

    assert audit_log.action == "CREATE"
    assert audit_log.user_id == api.user_ids["researcher"]


async def test_material_update_eager_loads_tests(api):
    create_response = await api.client.post(
        "/api/v1/materials",
        headers=api.headers["researcher"],
        json={"name": "Before update", "material_type": "metal"},
    )

    material_id = create_response.json()["id"]
    response = await api.client.put(
        f"/api/v1/materials/{material_id}",
        headers=api.headers["researcher"],
        json={"name": "After update"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After update"


@pytest.mark.parametrize(
    ("path", "kwargs"),
    [
        (
            "/api/v1/properties",
            {"json": {"material_id": str(uuid.uuid4()), "property_name": "density"}},
        ),
        (
            "/api/v1/tests",
            {"json": {"material_id": str(uuid.uuid4()), "test_name": "Tensile"}},
        ),
        (
            "/api/v1/crystal-structures",
            {"json": {"material_id": str(uuid.uuid4())}},
        ),
        (
            "/api/v1/files/upload",
            {
                "params": {"parent_id": str(uuid.uuid4())},
                "files": {"file": ("test.txt", b"test", "text/plain")},
            },
        ),
        ("/api/v1/collections", {"json": {"name": "Private collection"}}),
    ],
)
async def test_viewer_cannot_write_business_data(api, path, kwargs):
    response = await api.client.post(path, headers=api.headers["viewer"], **kwargs)

    assert response.status_code == 403
