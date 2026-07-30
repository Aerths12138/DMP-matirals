async def _create_project(api, name):
    response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()


async def _create_material(api, project_id, name="Private material"):
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


async def test_private_project_material_is_hidden_until_membership(api):
    project = await _create_project(api, "Private materials")
    material = await _create_material(api, project["id"], "Secret ceramic")

    list_response = await api.client.get(
        "/api/v1/materials",
        headers=api.headers["outsider"],
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0

    get_response = await api.client.get(
        f"/api/v1/materials/{material['id']}",
        headers=api.headers["outsider"],
    )
    assert get_response.status_code == 403

    create_response = await api.client.post(
        "/api/v1/materials",
        headers=api.headers["outsider"],
        json={
            "name": "Unauthorized material",
            "material_type": "ceramic",
            "project_id": project["id"],
        },
    )
    assert create_response.status_code == 403

    search_response = await api.client.get(
        "/api/v1/search",
        params={"q": "Secret"},
        headers=api.headers["outsider"],
    )
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 0

    dashboard_response = await api.client.get(
        "/api/v1/dashboard/stats",
        headers=api.headers["outsider"],
    )
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["materials_total"] == 0
    assert dashboard_response.json()["recent_materials"] == []

    add_member = await api.client.post(
        f"/api/v1/projects/{project['id']}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": "viewer"},
    )
    assert add_member.status_code == 201

    visible_response = await api.client.get(
        f"/api/v1/materials/{material['id']}",
        headers=api.headers["outsider"],
    )
    assert visible_response.status_code == 200

    denied_update = await api.client.put(
        f"/api/v1/materials/{material['id']}",
        headers=api.headers["outsider"],
        json={"name": "Viewer rename"},
    )
    assert denied_update.status_code == 403


async def test_editor_cannot_move_material_to_inaccessible_project(api):
    source_project = await _create_project(api, "Source project")
    target_project = await _create_project(api, "Target project")
    material = await _create_material(api, source_project["id"], "Movable material")

    add_member = await api.client.post(
        f"/api/v1/projects/{source_project['id']}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": "editor"},
    )
    assert add_member.status_code == 201

    rename_response = await api.client.put(
        f"/api/v1/materials/{material['id']}",
        headers=api.headers["outsider"],
        json={"name": "Editor rename"},
    )
    assert rename_response.status_code == 200

    move_response = await api.client.put(
        f"/api/v1/materials/{material['id']}",
        headers=api.headers["outsider"],
        json={"project_id": target_project["id"]},
    )
    assert move_response.status_code == 403

    unchanged = await api.client.get(
        f"/api/v1/materials/{material['id']}",
        headers=api.headers["researcher"],
    )
    assert unchanged.json()["project_id"] == source_project["id"]


async def test_material_properties_follow_material_visibility(api):
    project = await _create_project(api, "Property isolation")
    material = await _create_material(api, project["id"], "Property secret")
    property_response = await api.client.post(
        "/api/v1/properties",
        headers=api.headers["researcher"],
        json={
            "material_id": material["id"],
            "property_type": "thermal",
            "property_name": "thermal_conductivity",
            "value_number": 1.5,
            "unit": "W/mK",
        },
    )
    assert property_response.status_code == 201

    hidden_list = await api.client.get(
        "/api/v1/properties",
        params={"material_id": material["id"]},
        headers=api.headers["outsider"],
    )
    assert hidden_list.status_code == 403

    hidden_detail = await api.client.get(
        f"/api/v1/properties/{property_response.json()['id']}",
        headers=api.headers["outsider"],
    )
    assert hidden_detail.status_code == 403
