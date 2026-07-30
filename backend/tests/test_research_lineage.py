async def _create_project_sample(api, project_name="Lineage project"):
    project_response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": project_name},
    )
    assert project_response.status_code == 201
    project = project_response.json()

    experiment_response = await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["researcher"],
        json={"project_id": project["id"], "name": "Lineage experiment"},
    )
    assert experiment_response.status_code == 201
    experiment = experiment_response.json()

    sample_response = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={"experiment_id": experiment["id"], "sample_code": "LINEAGE-001"},
    )
    assert sample_response.status_code == 201
    return project, experiment, sample_response.json()


async def _add_project_member(api, project_id, role):
    response = await api.client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": role},
    )
    assert response.status_code == 201


async def test_processing_chain_inherits_sample_project_access(api):
    project, _, sample = await _create_project_sample(api, "Processing lineage")

    first_response = await api.client.post(
        "/api/v1/processing-methods",
        headers=api.headers["researcher"],
        json={
            "sample_id": sample["id"],
            "method_type": "sintering",
            "parameters": {"temperature_c": 800, "duration_h": 2},
            "order_in_chain": 1,
        },
    )
    assert first_response.status_code == 201
    first = first_response.json()

    second_response = await api.client.post(
        "/api/v1/processing-methods",
        headers=api.headers["researcher"],
        json={
            "sample_id": sample["id"],
            "method_type": "polishing",
            "parameters": {"grit": 1200},
            "order_in_chain": 2,
            "parent_step_id": first["id"],
        },
    )
    assert second_response.status_code == 201
    assert second_response.json()["parent_step_id"] == first["id"]

    hidden = await api.client.get(
        "/api/v1/processing-methods",
        params={"sample_id": sample["id"]},
        headers=api.headers["outsider"],
    )
    assert hidden.status_code == 403

    await _add_project_member(api, project["id"], "viewer")
    visible = await api.client.get(
        "/api/v1/processing-methods",
        params={"sample_id": sample["id"]},
        headers=api.headers["outsider"],
    )
    assert visible.status_code == 200
    assert [item["method_type"] for item in visible.json()["items"]] == [
        "sintering",
        "polishing",
    ]

    denied_create = await api.client.post(
        "/api/v1/processing-methods",
        headers=api.headers["outsider"],
        json={"sample_id": sample["id"], "method_type": "annealing"},
    )
    assert denied_create.status_code == 403


async def test_characterization_and_analysis_versions_are_traceable(api):
    project, _, sample = await _create_project_sample(api, "Analysis lineage")

    characterization_response = await api.client.post(
        "/api/v1/characterizations",
        headers=api.headers["researcher"],
        json={
            "sample_id": sample["id"],
            "technique": "SEM",
            "instrument": "Zeiss GeminiSEM",
            "parameters": {"accelerating_voltage_kv": 5},
            "metadata": {"lab": "Microscopy Center"},
        },
    )
    assert characterization_response.status_code == 201
    characterization = characterization_response.json()
    assert characterization["metadata"] == {"lab": "Microscopy Center"}

    hidden_characterization = await api.client.get(
        f"/api/v1/characterizations/{characterization['id']}",
        headers=api.headers["outsider"],
    )
    assert hidden_characterization.status_code == 403

    version_one_response = await api.client.post(
        "/api/v1/analysis-results",
        headers=api.headers["researcher"],
        json={
            "characterization_id": characterization["id"],
            "analysis_type": "particle_segmentation",
            "pipeline_name": "sem-pipeline",
            "model_name": "cellpose",
            "model_version": "1.0",
            "result_data": {"particle_count": 40},
        },
    )
    assert version_one_response.status_code == 201
    version_one = version_one_response.json()
    assert version_one["previous_version_id"] is None

    version_two_response = await api.client.post(
        "/api/v1/analysis-results",
        headers=api.headers["researcher"],
        json={
            "characterization_id": characterization["id"],
            "analysis_type": "particle_segmentation",
            "pipeline_name": "sem-pipeline",
            "model_name": "cellpose",
            "model_version": "1.1",
            "result_data": {"particle_count": 42},
        },
    )
    assert version_two_response.status_code == 201
    version_two = version_two_response.json()
    assert version_two["previous_version_id"] == version_one["id"]
    assert version_two["is_latest"] is True

    versions = await api.client.get(
        "/api/v1/analysis-results",
        params={"characterization_id": characterization["id"]},
        headers=api.headers["researcher"],
    )
    assert versions.status_code == 200
    assert [item["id"] for item in versions.json()["items"]] == [
        version_two["id"],
        version_one["id"],
    ]
    assert versions.json()["items"][1]["is_latest"] is False

    hidden_analysis = await api.client.get(
        f"/api/v1/analysis-results/{version_two['id']}",
        headers=api.headers["outsider"],
    )
    assert hidden_analysis.status_code == 403

    await _add_project_member(api, project["id"], "viewer")
    visible_analysis = await api.client.get(
        f"/api/v1/analysis-results/{version_two['id']}",
        headers=api.headers["outsider"],
    )
    assert visible_analysis.status_code == 200

    denied_run = await api.client.post(
        "/api/v1/analysis-results",
        headers=api.headers["outsider"],
        json={
            "characterization_id": characterization["id"],
            "analysis_type": "particle_segmentation",
            "result_data": {"particle_count": 43},
        },
    )
    assert denied_run.status_code == 403
