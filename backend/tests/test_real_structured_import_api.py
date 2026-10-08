"""End-to-end API regression using the structure extracted from the real GBK CSV fixture."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.permission import Permission, Role
from app.models.user import User


async def _grant_import_permission(api):
    async with api.session_factory() as session:
        user = await session.scalar(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == api.user_ids["researcher"])
        )
        permission = await session.scalar(select(Permission).where(Permission.codename == "import:create"))
        if permission is None:
            permission = Permission(codename="import:create")
            session.add(permission)
            await session.flush()
        if permission not in user.role.permissions:
            user.role.permissions.append(permission)
        await session.commit()


@pytest.mark.asyncio
async def test_real_tensile_preview_payload_can_be_confirmed_and_read_back(api):
    await _grant_import_permission(api)
    project = (await api.client.post(
        "/api/v1/projects", headers=api.headers["researcher"], json={"name": "燕山数据导入"}
    )).json()
    experiment = (await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["researcher"],
        json={"project_id": project["id"], "name": "拉伸数据"},
    )).json()
    sample = (await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={"experiment_id": experiment["id"], "sample_code": "XLPE-燕山-1-1"},
    )).json()

    payload = {
        "sample_id": sample["id"],
        "name": "1-1_1",
        "x_name": "测量序号",
        "series_schema": [
            {"key": "series_2", "name": "拉伸位移在抗拉强度", "unit": "mm"},
            {"key": "series_3", "name": "拉伸应变 (位移)在抗拉强度", "unit": "%"},
            {"key": "series_4", "name": "拉伸应力在抗拉强度", "unit": "MPa"},
            {"key": "series_5", "name": "力在抗拉强度", "unit": "N"},
            {"key": "series_6", "name": "时间在抗拉强度", "unit": "s"},
            {"key": "series_7", "name": "位移在抗拉强度", "unit": "mm"},
        ],
        "points": [
            {"sequence": 1, "x_value": 1, "values": {
                "series_2": 171.31, "series_3": 570.90, "series_4": 15.05,
                "series_5": 56.22, "series_6": 51.43, "series_7": 171.32,
            }},
            {"sequence": 2, "x_value": 2, "values": {
                "series_2": 169.51, "series_3": 564.99, "series_4": 15.27,
                "series_5": 57.04, "series_6": 50.89, "series_7": 169.51,
            }},
        ],
        "provenance": {
            "source_filename": "1-1_1.csv",
            "parser": "structure-driven-v1",
            "source_rows": [4, 5],
            "excluded_derived_rows": [
                {"sourceRow": 6, "label": "变异系数"},
                {"sourceRow": 7, "label": "标准方差"},
                {"sourceRow": 8, "label": "最大值"},
                {"sourceRow": 9, "label": "最小值"},
                {"sourceRow": 10, "label": "平均值"},
            ],
        },
    }
    created = await api.client.post(
        "/api/v1/measurement-datasets", headers=api.headers["researcher"], json=payload
    )
    assert created.status_code == 201
    dataset = created.json()
    assert dataset["row_count"] == 2
    assert len(dataset["series_schema"]) == 6
    assert dataset["provenance"]["source_rows"] == [4, 5]
    assert len(dataset["provenance"]["excluded_derived_rows"]) == 5

    read_back = await api.client.get(
        f"/api/v1/measurement-datasets/{dataset['id']}", headers=api.headers["researcher"]
    )
    assert read_back.status_code == 200
    assert read_back.json()["points"][0]["values"]["series_4"] == 15.05
