import uuid
from datetime import datetime, timedelta

from app.models.property import Property


async def _create_project(api, name: str):
    response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()


async def _create_material(api, project_id: str, name: str):
    response = await api.client.post(
        "/api/v1/materials",
        headers=api.headers["researcher"],
        json={
            "name": name,
            "material_type": "ceramic",
            "project_id": project_id,
        },
    )
    assert response.status_code == 201
    return response.json()


async def _create_experiment(api, project_id: str, name: str):
    response = await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["researcher"],
        json={"project_id": project_id, "name": name},
    )
    assert response.status_code == 201
    return response.json()


async def _create_sample(
    api,
    experiment_id: str,
    material_id: str,
    sample_code: str,
):
    response = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={
            "experiment_id": experiment_id,
            "material_id": material_id,
            "sample_code": sample_code,
            "form": "pellet",
        },
    )
    assert response.status_code == 201
    return response.json()


def _compare_params(*material_ids: str):
    return [("material_ids", material_id) for material_id in material_ids]


def _sample_compare_params(*sample_ids: str):
    return [("sample_ids", sample_id) for sample_id in sample_ids]


async def test_property_comparison_returns_latest_numeric_values_and_counts(api):
    project = await _create_project(api, "Visualization project")
    material_a = await _create_material(api, project["id"], "Ceramic A")
    material_b = await _create_material(api, project["id"], "Ceramic B")
    older = datetime(2026, 1, 1, 8, 0, 0)
    newer = older + timedelta(days=1)

    async with api.session_factory() as session:
        session.add_all(
            [
                Property(
                    material_id=uuid.UUID(material_a["id"]),
                    property_type="thermal",
                    property_name="thermal_conductivity",
                    value_number=1.2,
                    unit="W/mK",
                    conditions={"temperature": 25},
                    created_at=older,
                ),
                Property(
                    material_id=uuid.UUID(material_a["id"]),
                    property_type="thermal",
                    property_name="thermal_conductivity",
                    value_number=1.8,
                    uncertainty=0.1,
                    unit="W/mK",
                    conditions={"temperature": 50},
                    created_at=newer,
                ),
                Property(
                    material_id=uuid.UUID(material_b["id"]),
                    property_type="thermal",
                    property_name="thermal_conductivity",
                    value_number=2.2,
                    unit="W/mK",
                    created_at=newer,
                ),
                Property(
                    material_id=uuid.UUID(material_a["id"]),
                    property_type="physical",
                    property_name="density",
                    value_number=3.4,
                    created_at=newer,
                ),
                Property(
                    material_id=uuid.UUID(material_b["id"]),
                    property_type="other",
                    property_name="appearance",
                    value_text="white",
                    created_at=newer,
                ),
            ]
        )
        await session.commit()

    response = await api.client.get(
        "/api/v1/properties/compare",
        params=_compare_params(material_a["id"], material_b["id"]),
        headers=api.headers["researcher"],
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["id"] for item in payload["materials"]] == [
        material_a["id"],
        material_b["id"],
    ]

    measurements = {
        (item["material_id"], item["property_name"], item["unit"]): item
        for item in payload["measurements"]
    }
    latest_a = measurements[
        (material_a["id"], "thermal_conductivity", "W/mK")
    ]
    assert latest_a["value_number"] == 1.8
    assert latest_a["uncertainty"] == 0.1
    assert latest_a["conditions"] == {"temperature": 50}
    assert latest_a["measurement_count"] == 2
    assert measurements[
        (material_b["id"], "thermal_conductivity", "W/mK")
    ]["measurement_count"] == 1
    assert measurements[(material_a["id"], "density", None)]["value_number"] == 3.4
    assert all(item["property_name"] != "appearance" for item in payload["measurements"])


async def test_property_comparison_rejects_hidden_or_duplicate_materials(api):
    project = await _create_project(api, "Private visualization")
    material_a = await _create_material(api, project["id"], "Private A")
    material_b = await _create_material(api, project["id"], "Private B")

    hidden = await api.client.get(
        "/api/v1/properties/compare",
        params=_compare_params(material_a["id"], material_b["id"]),
        headers=api.headers["outsider"],
    )
    assert hidden.status_code == 404

    duplicate = await api.client.get(
        "/api/v1/properties/compare",
        params=_compare_params(material_a["id"], material_a["id"]),
        headers=api.headers["researcher"],
    )
    assert duplicate.status_code == 400

    add_member = await api.client.post(
        f"/api/v1/projects/{project['id']}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": "viewer"},
    )
    assert add_member.status_code == 201

    visible = await api.client.get(
        "/api/v1/properties/compare",
        params=_compare_params(material_a["id"], material_b["id"]),
        headers=api.headers["outsider"],
    )
    assert visible.status_code == 200


async def test_sample_property_comparison_is_latest_and_project_scoped(api):
    project = await _create_project(api, "Sample visualization")
    material = await _create_material(api, project["id"], "Sample ceramic")
    experiment = await _create_experiment(api, project["id"], "Sample comparison")
    sample_a = await _create_sample(
        api,
        experiment["id"],
        material["id"],
        "SAMPLE-A",
    )
    sample_b = await _create_sample(
        api,
        experiment["id"],
        material["id"],
        "SAMPLE-B",
    )
    older = datetime(2026, 2, 1, 8, 0, 0)
    newer = older + timedelta(hours=4)

    async with api.session_factory() as session:
        session.add_all(
            [
                Property(
                    material_id=uuid.UUID(material["id"]),
                    sample_id=uuid.UUID(sample_a["id"]),
                    property_type="mechanical",
                    property_name="hardness",
                    value_number=500,
                    unit="HV",
                    created_at=older,
                ),
                Property(
                    material_id=uuid.UUID(material["id"]),
                    sample_id=uuid.UUID(sample_a["id"]),
                    property_type="mechanical",
                    property_name="hardness",
                    value_number=525,
                    uncertainty=8,
                    unit="HV",
                    conditions={"load_kgf": 1},
                    created_at=newer,
                ),
                Property(
                    material_id=uuid.UUID(material["id"]),
                    sample_id=uuid.UUID(sample_b["id"]),
                    property_type="mechanical",
                    property_name="hardness",
                    value_number=480,
                    unit="HV",
                    created_at=newer,
                ),
                Property(
                    material_id=uuid.UUID(material["id"]),
                    property_type="mechanical",
                    property_name="hardness",
                    value_number=999,
                    unit="HV",
                    created_at=newer,
                ),
            ]
        )
        await session.commit()

    hidden = await api.client.get(
        "/api/v1/properties/sample-compare",
        params=_sample_compare_params(sample_a["id"], sample_b["id"]),
        headers=api.headers["outsider"],
    )
    assert hidden.status_code == 404

    response = await api.client.get(
        "/api/v1/properties/sample-compare",
        params=_sample_compare_params(sample_a["id"], sample_b["id"]),
        headers=api.headers["researcher"],
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [sample["sample_code"] for sample in payload["samples"]] == [
        "SAMPLE-A",
        "SAMPLE-B",
    ]
    assert payload["samples"][0]["project_id"] == project["id"]
    assert payload["samples"][0]["material_name"] == "Sample ceramic"
    assert len(payload["measurements"]) == 2
    by_sample = {item["sample_id"]: item for item in payload["measurements"]}
    assert by_sample[sample_a["id"]]["value_number"] == 525
    assert by_sample[sample_a["id"]]["measurement_count"] == 2
    assert by_sample[sample_a["id"]]["conditions"] == {"load_kgf": 1}

    add_member = await api.client.post(
        f"/api/v1/projects/{project['id']}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": "viewer"},
    )
    assert add_member.status_code == 201
    visible = await api.client.get(
        "/api/v1/properties/sample-compare",
        params=_sample_compare_params(sample_a["id"], sample_b["id"]),
        headers=api.headers["outsider"],
    )
    assert visible.status_code == 200
