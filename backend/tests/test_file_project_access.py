import uuid
from unittest.mock import AsyncMock

from app.api.v1 import files as files_api
from app.models.analysis import AnalysisResult
from app.models.characterization import Characterization
from app.models.file import File


async def _create_project_resources(api):
    project_response = await api.client.post(
        "/api/v1/projects",
        headers=api.headers["researcher"],
        json={"name": "Attachment isolation"},
    )
    assert project_response.status_code == 201
    project = project_response.json()

    experiment_response = await api.client.post(
        "/api/v1/experiments",
        headers=api.headers["researcher"],
        json={"project_id": project["id"], "name": "Private experiment"},
    )
    assert experiment_response.status_code == 201
    experiment = experiment_response.json()

    sample_response = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={"experiment_id": experiment["id"], "sample_code": "PRIVATE-001"},
    )
    assert sample_response.status_code == 201
    return project, experiment, sample_response.json()


async def test_project_resource_files_inherit_parent_visibility(api):
    _, experiment, sample = await _create_project_resources(api)

    async with api.session_factory() as session:
        characterization = Characterization(
            sample_id=uuid.UUID(sample["id"]),
            technique="SEM",
            title="Private micrograph",
            created_by=api.user_ids["researcher"],
        )
        session.add(characterization)
        await session.flush()
        analysis = AnalysisResult(
            characterization_id=characterization.id,
            analysis_type="particle_segmentation",
            result_data={"particle_count": 42},
            run_by=api.user_ids["researcher"],
        )
        session.add(analysis)
        await session.flush()

        parents = [
            ("experiment", uuid.UUID(experiment["id"])),
            ("sample", uuid.UUID(sample["id"])),
            ("characterization", characterization.id),
            ("analysis", analysis.id),
        ]
        db_files = [
            File(
                parent_type=parent_type,
                parent_id=parent_id,
                original_name=f"{parent_type}-private.txt",
                stored_path=f"private/{parent_type}.txt",
                uploaded_by=api.user_ids["researcher"],
            )
            for parent_type, parent_id in parents
        ]
        session.add_all(db_files)
        await session.commit()
        file_ids = [str(db_file.id) for db_file in db_files]

    for file_id in file_ids:
        hidden = await api.client.get(
            f"/api/v1/files/{file_id}",
            headers=api.headers["outsider"],
        )
        assert hidden.status_code == 403

        visible = await api.client.get(
            f"/api/v1/files/{file_id}",
            headers=api.headers["researcher"],
        )
        assert visible.status_code == 200


async def test_unauthorized_upload_is_rejected_before_storage(api, monkeypatch):
    _, experiment, _ = await _create_project_resources(api)
    upload_mock = AsyncMock(return_value="should-not-be-created.txt")
    monkeypatch.setattr(files_api.storage, "upload", upload_mock)

    denied = await api.client.post(
        "/api/v1/files/upload",
        params={"parent_type": "experiment", "parent_id": experiment["id"]},
        files={"file": ("secret.txt", b"secret", "text/plain")},
        headers=api.headers["outsider"],
    )
    assert denied.status_code == 403
    upload_mock.assert_not_awaited()


async def test_upload_requires_an_existing_parent(api, monkeypatch):
    upload_mock = AsyncMock(return_value="should-not-be-created.txt")
    monkeypatch.setattr(files_api.storage, "upload", upload_mock)

    missing_id = await api.client.post(
        "/api/v1/files/upload",
        params={"parent_type": "experiment"},
        files={"file": ("orphan.txt", b"orphan", "text/plain")},
        headers=api.headers["researcher"],
    )
    assert missing_id.status_code == 400
    upload_mock.assert_not_awaited()
