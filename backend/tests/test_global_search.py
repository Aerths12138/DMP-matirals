import uuid

from app.models.file import File


async def _create_project_graph(api, project_name: str, keyword: str):
    project_response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": project_name, "description": f"{keyword} project"},
    )
    assert project_response.status_code == 201
    project = project_response.json()

    material_response = await api.client.post(
        "/api/v1/materials",
        headers=api.headers["researcher"],
        json={
            "project_id": project["id"],
            "name": f"{keyword} alloy",
            "material_type": "metal",
            "composition": [],
            "aliases": [],
            "metadata": {},
        },
    )
    assert material_response.status_code == 201
    material = material_response.json()

    experiment_response = await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["researcher"],
        json={"project_id": project["id"], "name": f"{keyword} experiment"},
    )
    assert experiment_response.status_code == 201
    experiment = experiment_response.json()

    sample_response = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={"experiment_id": experiment["id"], "sample_code": f"{keyword}-001"},
    )
    assert sample_response.status_code == 201
    sample = sample_response.json()

    characterization_response = await api.client.post(
        "/api/v1/characterizations",
        headers=api.headers["researcher"],
        json={
            "sample_id": sample["id"],
            "technique": "SEM",
            "title": f"{keyword} micrograph",
        },
    )
    assert characterization_response.status_code == 201
    characterization = characterization_response.json()

    async with api.session_factory() as session:
        attachment = File(
            parent_type="characterization",
            parent_id=uuid.UUID(characterization["id"]),
            original_name=f"{keyword}-raw.png",
            stored_path=f"search/{keyword}.png",
            file_type="sem_image",
            uploaded_by=api.user_ids["researcher"],
        )
        session.add(attachment)
        await session.commit()

    return project, material, experiment, sample, characterization


async def test_global_search_covers_core_entities_with_permission_filtering(api):
    project, _, _, _, _ = await _create_project_graph(api, "Visible project", "needle")
    hidden_project_response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": "needle hidden project"},
    )
    assert hidden_project_response.status_code == 201
    hidden_project = hidden_project_response.json()

    before_membership = await api.client.get(
        "/api/v1/search",
        params={"q": "needle"},
        headers=api.headers["outsider"],
    )
    assert before_membership.status_code == 200
    assert before_membership.json()["total"] == 0

    add_viewer = await api.client.post(
        f"/api/v1/projects/{project['id']}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": "viewer"},
    )
    assert add_viewer.status_code == 201

    visible = await api.client.get(
        "/api/v1/search",
        params={"q": "needle", "size": 100},
        headers=api.headers["outsider"],
    )
    assert visible.status_code == 200, visible.text
    payload = visible.json()
    assert payload["total"] == 6
    assert {item["entity_type"] for item in payload["items"]} == {
        "project",
        "material",
        "experiment",
        "sample",
        "characterization",
        "file",
    }
    assert {item["project_id"] for item in payload["items"]} == {project["id"]}

    files_only = await api.client.get(
        "/api/v1/search",
        params={"q": "needle", "entity_type": "file"},
        headers=api.headers["outsider"],
    )
    assert files_only.status_code == 200
    assert files_only.json()["total"] == 1
    file_result = files_only.json()["items"][0]
    assert file_result["parent_type"] == "characterization"

    forbidden_project_filter = await api.client.get(
        "/api/v1/search",
        params={"q": "needle", "project_id": hidden_project["id"]},
        headers=api.headers["outsider"],
    )
    assert forbidden_project_filter.status_code == 403


async def test_global_search_paginates_the_unified_result_set(api):
    project, _, _, _, _ = await _create_project_graph(api, "Pagination project", "paginate")
    first_page = await api.client.get(
        "/api/v1/search",
        params={"q": "paginate", "project_id": project["id"], "page": 1, "size": 2},
        headers=api.headers["researcher"],
    )
    assert first_page.status_code == 200, first_page.text
    assert first_page.json()["total"] == 6
    assert first_page.json()["pages"] == 3
    assert len(first_page.json()["items"]) == 2

    third_page = await api.client.get(
        "/api/v1/search",
        params={"q": "paginate", "project_id": project["id"], "page": 3, "size": 2},
        headers=api.headers["researcher"],
    )
    assert third_page.status_code == 200
    assert len(third_page.json()["items"]) == 2
    assert {
        item["id"] for item in first_page.json()["items"]
    }.isdisjoint({item["id"] for item in third_page.json()["items"]})
