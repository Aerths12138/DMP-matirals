import hashlib
import uuid

from app.api.v1 import files as files_api
from app.models.file import File
from app.services.file_storage_service import LocalFileStorage


async def _create_project_resources(api, name="File workbench"):
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
        json={"project_id": project["id"], "name": "File experiment"},
    )
    assert experiment_response.status_code == 201
    experiment = experiment_response.json()
    sample_response = await api.client.post(
        "/api/v1/samples",
        headers=api.headers["researcher"],
        json={"experiment_id": experiment["id"], "sample_code": "FILE-001"},
    )
    assert sample_response.status_code == 201
    return project, experiment, sample_response.json()


async def test_file_list_is_filtered_and_inherits_parent_visibility(api):
    project, experiment, sample = await _create_project_resources(api, "File list")
    async with api.session_factory() as session:
        session.add_all(
            [
                File(
                    parent_type="sample",
                    parent_id=uuid.UUID(sample["id"]),
                    original_name="sample.txt",
                    stored_path="test/sample.txt",
                    file_size_bytes=10,
                    uploaded_by=api.user_ids["researcher"],
                ),
                File(
                    parent_type="experiment",
                    parent_id=uuid.UUID(experiment["id"]),
                    original_name="experiment.txt",
                    stored_path="test/experiment.txt",
                    file_size_bytes=20,
                    uploaded_by=api.user_ids["researcher"],
                ),
            ]
        )
        await session.commit()

    hidden = await api.client.get(
        "/api/v1/files",
        params={"parent_type": "sample", "parent_id": sample["id"]},
        headers=api.headers["outsider"],
    )
    assert hidden.status_code == 403

    add_viewer = await api.client.post(
        f"/api/v1/projects/{project['id']}/members",
        headers=api.headers["researcher"],
        json={"user_id": str(api.user_ids["outsider"]), "role": "viewer"},
    )
    assert add_viewer.status_code == 201

    visible = await api.client.get(
        "/api/v1/files",
        params={"parent_type": "sample", "parent_id": sample["id"]},
        headers=api.headers["outsider"],
    )
    assert visible.status_code == 200
    assert visible.json()["total"] == 1
    assert visible.json()["items"][0]["original_name"] == "sample.txt"


async def test_upload_records_checksum_rejects_duplicate_and_can_be_deleted(
    api,
    monkeypatch,
    tmp_path,
):
    _, _, sample = await _create_project_resources(api, "File lifecycle")
    test_storage = LocalFileStorage(tmp_path)
    monkeypatch.setattr(files_api, "storage", test_storage)
    content = b"SEM image payload"

    upload = await api.client.post(
        "/api/v1/files/upload",
        params={
            "parent_type": "sample",
            "parent_id": sample["id"],
            "file_type": "sem_image",
            "description": "Raw SEM acquisition",
        },
        files={"file": ("micrograph.txt", content, "text/plain")},
        headers=api.headers["researcher"],
    )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["id"]
    assert upload.json()["file_size_bytes"] == len(content)

    listed = await api.client.get(
        "/api/v1/files",
        params={"parent_type": "sample", "parent_id": sample["id"]},
        headers=api.headers["researcher"],
    )
    assert listed.status_code == 200
    attachment = listed.json()["items"][0]
    assert attachment["checksum_sha256"] == hashlib.sha256(content).hexdigest()
    assert attachment["description"] == "Raw SEM acquisition"

    duplicate = await api.client.post(
        "/api/v1/files/upload",
        params={"parent_type": "sample", "parent_id": sample["id"]},
        files={"file": ("renamed.txt", content, "text/plain")},
        headers=api.headers["researcher"],
    )
    assert duplicate.status_code == 409

    download = await api.client.get(
        f"/api/v1/files/{file_id}/download",
        headers=api.headers["researcher"],
    )
    assert download.status_code == 200
    assert download.content == content

    deleted = await api.client.delete(
        f"/api/v1/files/{file_id}",
        headers=api.headers["researcher"],
    )
    assert deleted.status_code == 204

    empty = await api.client.get(
        "/api/v1/files",
        params={"parent_type": "sample", "parent_id": sample["id"]},
        headers=api.headers["researcher"],
    )
    assert empty.status_code == 200
    assert empty.json()["total"] == 0
