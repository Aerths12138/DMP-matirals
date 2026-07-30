async def _create_project_and_experiment(api, name: str):
    project_response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": name},
    )
    assert project_response.status_code == 201
    project = project_response.json()
    experiment_response = await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["researcher"],
        json={"project_id": project["id"], "name": f"{name} experiment"},
    )
    assert experiment_response.status_code == 201
    return project, experiment_response.json()


async def _create_template(api, project_id: str, entity_type: str, fields: list[dict]):
    response = await api.client.post(
        "/api/v1/data-standards/templates",
        headers=api.headers["researcher"],
        json={
            "project_id": project_id,
            "name": f"{entity_type} standard",
            "entity_type": entity_type,
            "fields": fields,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_sample_metadata_template_enforces_required_type_and_vocabulary(api):
    project, experiment = await _create_project_and_experiment(api, "Metadata validation")
    template = await _create_template(
        api,
        project["id"],
        "sample",
        [
            {
                "key": "supplier",
                "label": "供应商",
                "value_type": "string",
                "required": True,
                "options": ["A厂", "B厂"],
            },
            {
                "key": "drying_temperature",
                "label": "干燥温度",
                "value_type": "number",
                "required": True,
                "unit": "°C",
            },
        ],
    )

    missing = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={
            "experiment_id": experiment["id"],
            "sample_code": "STD-001",
            "metadata_template_id": template["id"],
            "metadata": {"supplier": "A厂"},
        },
    )
    assert missing.status_code == 422
    assert "drying_temperature" in missing.json()["detail"]

    invalid_option = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={
            "experiment_id": experiment["id"],
            "sample_code": "STD-002",
            "metadata_template_id": template["id"],
            "metadata": {"supplier": "其他", "drying_temperature": 80},
        },
    )
    assert invalid_option.status_code == 422
    assert "controlled options" in invalid_option.json()["detail"]

    valid = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={
            "experiment_id": experiment["id"],
            "sample_code": "STD-003",
            "metadata_template_id": template["id"],
            "metadata": {"supplier": "B厂", "drying_temperature": 80.5},
        },
    )
    assert valid.status_code == 201, valid.text
    sample = valid.json()
    assert sample["metadata_template_id"] == template["id"]
    assert sample["metadata"] == {"supplier": "B厂", "drying_temperature": 80.5}

    invalid_update = await api.client.put(
        f"/api/v1/samples/{sample['id']}",
        headers=api.headers["researcher"],
        json={"metadata": {"supplier": "A厂", "drying_temperature": "80"}},
    )
    assert invalid_update.status_code == 422
    assert "Invalid value type" in invalid_update.json()["detail"]


async def test_data_standards_are_project_scoped_and_support_custom_units(api):
    project_a, experiment_a = await _create_project_and_experiment(api, "Standards A")
    project_b, _ = await _create_project_and_experiment(api, "Standards B")

    custom_unit = await api.client.post(
        "/api/v1/data-standards/units",
        headers=api.headers["researcher"],
        json={
            "project_id": project_a["id"],
            "symbol": "rpm",
            "name": "转每分钟",
            "quantity_type": "转速",
        },
    )
    assert custom_unit.status_code == 201, custom_unit.text
    assert custom_unit.json()["is_builtin"] is False

    units = await api.client.get(
        "/api/v1/data-standards/units",
        params={"project_id": project_a["id"]},
        headers=api.headers["researcher"],
    )
    assert units.status_code == 200
    symbols = {unit["symbol"] for unit in units.json()}
    assert {"rpm", "°C", "μm"}.issubset(symbols)

    template_a = await _create_template(
        api,
        project_a["id"],
        "sample",
        [
            {
                "key": "rotation_speed",
                "label": "转速",
                "value_type": "integer",
                "unit": "rpm",
            }
        ],
    )
    template_b = await _create_template(
        api,
        project_b["id"],
        "sample",
        [{"key": "source", "label": "来源", "value_type": "string"}],
    )

    cross_project = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={
            "experiment_id": experiment_a["id"],
            "sample_code": "CROSS-001",
            "metadata_template_id": template_b["id"],
            "metadata": {},
        },
    )
    assert cross_project.status_code == 400

    add_viewer = await api.client.post(
        f"/api/v1/projects/{project_a['id']}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": "viewer"},
    )
    assert add_viewer.status_code == 201

    visible = await api.client.get(
        "/api/v1/data-standards/templates",
        params={"project_id": project_a["id"]},
        headers=api.headers["outsider"],
    )
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()] == [template_a["id"]]

    denied_create = await api.client.post(
        "/api/v1/data-standards/templates",
        headers=api.headers["outsider"],
        json={
            "project_id": project_a["id"],
            "name": "Viewer template",
            "entity_type": "sample",
            "fields": [],
        },
    )
    assert denied_create.status_code == 403

    hidden_project = await api.client.get(
        "/api/v1/data-standards/templates",
        params={"project_id": project_b["id"]},
        headers=api.headers["outsider"],
    )
    assert hidden_project.status_code == 403
