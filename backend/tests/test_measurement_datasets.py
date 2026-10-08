import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.permission import Permission, Role
from app.models.user import User


async def _grant_permission(api, user_id, codename):
    async with api.session_factory() as session:
        user = await session.scalar(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        permission = await session.scalar(
            select(Permission).where(Permission.codename == codename)
        )
        if permission is None:
            permission = Permission(codename=codename)
            session.add(permission)
            await session.flush()
        if permission not in user.role.permissions:
            user.role.permissions.append(permission)
        await session.commit()


async def _grant_import_permission(api, user_id):
    await _grant_permission(api, user_id, "import:create")


async def _create_project_sample(api):
    project = (
        await api.client.post(
            "/api/v1/projects",
            headers=api.headers["researcher"],
            json={"name": "Dataset import project"},
        )
    ).json()
    experiment = (
        await api.client.post(
            "/api/v1/experiments",
            headers=api.headers["researcher"],
            json={"project_id": project["id"], "name": "Dataset import experiment"},
        )
    ).json()
    response = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={"experiment_id": experiment["id"], "sample_code": "XLPE-YS-1-1"},
    )
    assert response.status_code == 201
    return project, response.json()


def _dataset_body(sample_id):
    return {
        "sample_id": sample_id,
        "name": "1-1_1",
        "x_name": "测量序号",
        "series_schema": [
            {"key": "tensile_displacement", "name": "拉伸位移在抗拉强度", "unit": "mm"},
            {"key": "tensile_stress", "name": "拉伸应力在抗拉强度", "unit": "MPa"},
        ],
        "points": [
            {"sequence": 1, "x_value": 1, "values": {"tensile_displacement": 171.31, "tensile_stress": 15.05}},
            {"sequence": 2, "x_value": 2, "values": {"tensile_displacement": 169.51, "tensile_stress": 15.27}},
        ],
        "provenance": {
            "source_filename": "1-1_1.csv",
            "excluded_derived_rows": ["变异系数", "标准方差", "最大值", "最小值", "平均值"],
        },
    }


@pytest.mark.asyncio
async def test_dataset_import_creates_one_dataset_with_ordered_points(api):
    await _grant_import_permission(api, api.user_ids["researcher"])
    _, sample = await _create_project_sample(api)

    response = await api.client.post(
        "/api/v1/measurement-datasets",
        headers=api.headers["researcher"],
        json=_dataset_body(sample["id"]),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "1-1_1"
    assert data["row_count"] == 2
    assert [point["sequence"] for point in data["points"]] == [1, 2]
    assert data["points"][1]["values"]["tensile_stress"] == 15.27

    fetched = await api.client.get(
        f"/api/v1/measurement-datasets/{data['id']}",
        headers=api.headers["researcher"],
    )
    assert fetched.status_code == 200
    assert fetched.json()["series_schema"][0]["unit"] == "mm"


@pytest.mark.asyncio
async def test_dataset_import_rejects_same_name_for_same_sample(api):
    await _grant_import_permission(api, api.user_ids["researcher"])
    _, sample = await _create_project_sample(api)
    first = await api.client.post(
        "/api/v1/measurement-datasets",
        headers=api.headers["researcher"],
        json=_dataset_body(sample["id"]),
    )
    assert first.status_code == 201

    duplicate = await api.client.post(
        "/api/v1/measurement-datasets",
        headers=api.headers["researcher"],
        json=_dataset_body(sample["id"]),
    )
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_dataset_access_follows_sample_project_membership(api):
    await _grant_import_permission(api, api.user_ids["researcher"])
    project, sample = await _create_project_sample(api)
    created = await api.client.post(
        "/api/v1/measurement-datasets",
        headers=api.headers["researcher"],
        json=_dataset_body(sample["id"]),
    )
    dataset_id = created.json()["id"]

    hidden = await api.client.get(
        f"/api/v1/measurement-datasets/{dataset_id}",
        headers=api.headers["outsider"],
    )
    assert hidden.status_code == 403

    member = await api.client.post(
        f"/api/v1/projects/{project['id']}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": "viewer"},
    )
    assert member.status_code == 201
    visible = await api.client.get(
        f"/api/v1/measurement-datasets/{dataset_id}",
        headers=api.headers["outsider"],
    )
    assert visible.status_code == 200

    denied_write = await api.client.post(
        "/api/v1/measurement-datasets",
        headers=api.headers["outsider"],
        json={**_dataset_body(sample["id"]), "name": "viewer-write"},
    )
    assert denied_write.status_code == 403


@pytest.mark.asyncio
async def test_dataset_can_be_updated_and_deleted(api):
    await _grant_import_permission(api, api.user_ids["researcher"])
    await _grant_permission(api, api.user_ids["researcher"], "characterization:delete")
    _, sample = await _create_project_sample(api)
    created = await api.client.post(
        "/api/v1/measurement-datasets",
        headers=api.headers["researcher"],
        json=_dataset_body(sample["id"]),
    )
    dataset_id = created.json()["id"]

    updated = await api.client.patch(
        f"/api/v1/measurement-datasets/{dataset_id}",
        headers=api.headers["researcher"],
        json={"name": "renamed dataset"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "renamed dataset"

    deleted = await api.client.delete(
        f"/api/v1/measurement-datasets/{dataset_id}",
        headers=api.headers["researcher"],
    )
    assert deleted.status_code == 204
    missing = await api.client.get(
        f"/api/v1/measurement-datasets/{dataset_id}",
        headers=api.headers["researcher"],
    )
    assert missing.status_code == 404
