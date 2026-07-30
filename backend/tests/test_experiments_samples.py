async def _create_project(api, name="Project"):
    response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": name},
    )
    assert response.status_code == 201
    project = response.json()
    assert project["created_at"]
    assert project["updated_at"]
    return project


async def _create_experiment(api, project_id, name="Experiment"):
    response = await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["researcher"],
        json={
            "project_id": project_id,
            "name": name,
            "hypothesis": "Higher temperature improves conductivity",
            "metadata": {"temperature_c": 25},
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_experiments_inherit_project_membership(api):
    project = await _create_project(api)
    project_id = project["id"]

    denied_list = await api.client.get(
        "/api/v1/experiments",
        params={"project_id": project_id},
        headers=api.headers["viewer"],
    )
    assert denied_list.status_code == 403

    experiment = await _create_experiment(api, project_id)
    assert experiment["project_id"] == project_id
    assert experiment["metadata"] == {"temperature_c": 25}

    update_experiment = await api.client.put(
        f"/api/v1/experiments/{experiment['id']}",
        headers=api.headers["researcher"],
        json={"status": "running"},
    )
    assert update_experiment.status_code == 200
    assert update_experiment.json()["status"] == "running"

    add_member = await api.client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["viewer"]), "role": "viewer"},
    )
    assert add_member.status_code == 201

    visible_list = await api.client.get(
        "/api/v1/experiments",
        params={"project_id": project_id},
        headers=api.headers["viewer"],
    )
    assert visible_list.status_code == 200
    assert visible_list.json()["total"] == 1

    denied_create = await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["viewer"],
        json={"project_id": project_id, "name": "Unauthorized experiment"},
    )
    assert denied_create.status_code == 403


async def test_samples_inherit_their_experiment_project(api):
    project = await _create_project(api, "Sample project")
    project_id = project["id"]
    experiment = await _create_experiment(api, project_id, "Sample experiment")

    create_sample = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={
            "experiment_id": experiment["id"],
            "sample_code": "S-001",
            "form": "pellet",
            "mass_g": 1.25,
            "metadata": {"source": "batch-a"},
        },
    )
    assert create_sample.status_code == 201
    sample = create_sample.json()
    assert sample["experiment_id"] == experiment["id"]
    assert sample["metadata"] == {"source": "batch-a"}

    update_sample = await api.client.put(
        f"/api/v1/samples/{sample['id']}",
        headers=api.headers["researcher"],
        json={"status": "processing"},
    )
    assert update_sample.status_code == 200
    assert update_sample.json()["status"] == "processing"

    denied_get = await api.client.get(
        f"/api/v1/samples/{sample['id']}",
        headers=api.headers["viewer"],
    )
    assert denied_get.status_code == 403

    add_member = await api.client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["viewer"]), "role": "viewer"},
    )
    assert add_member.status_code == 201

    visible_list = await api.client.get(
        "/api/v1/samples",
        params={"project_id": project_id},
        headers=api.headers["viewer"],
    )
    assert visible_list.status_code == 200
    assert visible_list.json()["total"] == 1

    denied_update = await api.client.put(
        f"/api/v1/samples/{sample['id']}",
        headers=api.headers["viewer"],
        json={"status": "processing"},
    )
    assert denied_update.status_code == 403


async def test_sample_rejects_material_from_another_project(api):
    sample_project = await _create_project(api, "Sample owner project")
    other_project = await _create_project(api, "Other material project")
    experiment = await _create_experiment(
        api,
        sample_project["id"],
        "Cross-project validation",
    )

    material_response = await api.client.post(
        "/api/v1/materials",
        headers=api.headers["researcher"],
        json={
            "name": "Foreign material",
            "material_type": "ceramic",
            "project_id": other_project["id"],
        },
    )
    assert material_response.status_code == 201

    sample_response = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={
            "experiment_id": experiment["id"],
            "material_id": material_response.json()["id"],
            "sample_code": "CROSS-001",
        },
    )
    assert sample_response.status_code == 400
    assert sample_response.json()["detail"] == "Material belongs to a different project"
