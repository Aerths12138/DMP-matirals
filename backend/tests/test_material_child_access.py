import uuid

from app.models.file import File

async def _create_project(api, name):
    response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()


async def _create_material(api, project_id, name):
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


async def test_material_children_and_collection_follow_project_visibility(api):
    project = await _create_project(api, "Child resource isolation")
    material = await _create_material(api, project["id"], "Child resource secret")

    scoped_hidden = await api.client.get(
        "/api/v1/materials",
        params={"project_id": project["id"]},
        headers=api.headers["outsider"],
    )
    assert scoped_hidden.status_code == 403

    scoped_visible = await api.client.get(
        "/api/v1/materials",
        params={"project_id": project["id"]},
        headers=api.headers["researcher"],
    )
    assert scoped_visible.status_code == 200
    assert [item["id"] for item in scoped_visible.json()["items"]] == [material["id"]]

    test_response = await api.client.post(
        "/api/v1/tests",
        headers=api.headers["researcher"],
        json={"material_id": material["id"], "test_name": "Private test"},
    )
    assert test_response.status_code == 201
    test_id = test_response.json()["id"]

    hidden_tests = await api.client.get(
        "/api/v1/tests",
        headers=api.headers["outsider"],
    )
    assert hidden_tests.status_code == 200
    assert hidden_tests.json()["total"] == 0
    hidden_test = await api.client.get(
        f"/api/v1/tests/{test_id}",
        headers=api.headers["outsider"],
    )
    assert hidden_test.status_code == 403

    crystal_response = await api.client.post(
        "/api/v1/crystal-structures",
        headers=api.headers["researcher"],
        json={"material_id": material["id"], "crystal_system": "cubic"},
    )
    assert crystal_response.status_code == 201
    crystal_id = crystal_response.json()["id"]

    hidden_structures = await api.client.get(
        "/api/v1/crystal-structures",
        headers=api.headers["outsider"],
    )
    assert hidden_structures.status_code == 200
    assert hidden_structures.json()["total"] == 0
    hidden_structure = await api.client.get(
        f"/api/v1/crystal-structures/{crystal_id}",
        headers=api.headers["outsider"],
    )
    assert hidden_structure.status_code == 403

    async with api.session_factory() as session:
        db_file = File(
            parent_type="material",
            parent_id=uuid.UUID(material["id"]),
            original_name="private-result.txt",
            stored_path="not-read-by-metadata-endpoint",
            uploaded_by=api.user_ids["researcher"],
        )
        session.add(db_file)
        await session.commit()
        file_id = str(db_file.id)

    hidden_file = await api.client.get(
        f"/api/v1/files/{file_id}",
        headers=api.headers["outsider"],
    )
    assert hidden_file.status_code == 403
    visible_file = await api.client.get(
        f"/api/v1/files/{file_id}",
        headers=api.headers["researcher"],
    )
    assert visible_file.status_code == 200

    collection_response = await api.client.post(
        "/api/v1/collections",
        headers=api.headers["researcher"],
        json={
            "name": "Public shell around private material",
            "visibility": "public",
            "material_ids": [material["id"]],
        },
    )
    assert collection_response.status_code == 201
    collection_id = collection_response.json()["id"]

    outsider_collections = await api.client.get(
        "/api/v1/collections",
        headers=api.headers["outsider"],
    )
    assert outsider_collections.status_code == 200
    assert outsider_collections.json()["items"][0]["material_count"] == 0

    outsider_collection = await api.client.get(
        f"/api/v1/collections/{collection_id}",
        headers=api.headers["outsider"],
    )
    assert outsider_collection.status_code == 200
    assert outsider_collection.json()["material_ids"] == []
