import hashlib
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.config import Settings
from app.services.file_storage_service import VercelBlobStorage


def test_external_database_url_overrides_local_sqlite():
    configured = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:pass@db.example.com/materials?sslmode=require",
    )

    assert configured.database_url.startswith("postgresql+psycopg://")
    assert configured.database_url.endswith("?sslmode=require")
    assert configured.is_sqlite is False


def test_vercel_requires_external_database(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    configured = Settings(_env_file=None, DATABASE_URL=None)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        _ = configured.database_url


class FakeBlobClient:
    def __init__(self):
        self.content = b""
        self.deleted_path = None

    async def put(self, pathname, body, **kwargs):
        self.content = b"".join([chunk async for chunk in body])
        assert kwargs["access"] == "private"
        return SimpleNamespace(pathname=pathname)

    async def get(self, pathname, **kwargs):
        async def stream():
            yield self.content

        return SimpleNamespace(status_code=200, stream=stream())

    async def delete(self, pathname):
        self.deleted_path = pathname


@pytest.mark.asyncio
async def test_vercel_blob_backend_uploads_downloads_and_deletes():
    payload = b"private material attachment"
    client = FakeBlobClient()
    storage = VercelBlobStorage(client)
    upload = UploadFile(
        BytesIO(payload),
        filename="result.txt",
        headers=Headers({"content-type": "text/plain"}),
    )

    stored = await storage.upload(upload, "sample/result.txt")

    assert stored.path == "sample/result.txt"
    assert stored.size_bytes == len(payload)
    assert stored.checksum_sha256 == hashlib.sha256(payload).hexdigest()
    assert await storage.download(stored.path) == payload
    assert await storage.delete(stored.path) is True
    assert client.deleted_path == stored.path
