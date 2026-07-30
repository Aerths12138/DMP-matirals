"""File storage backends for local development and Vercel deployments."""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import UploadFile

from app.config import settings


@dataclass(frozen=True)
class StoredFile:
    """Metadata calculated while an uploaded object is persisted."""

    path: str
    size_bytes: int
    checksum_sha256: str


class FileStorageBackend(ABC):
    """Abstract interface shared by persistent file storage providers."""

    name: str

    @abstractmethod
    async def upload(self, file: UploadFile, relative_path: str) -> StoredFile:
        """Upload a file and return its storage metadata."""
        ...

    @abstractmethod
    async def download(self, relative_path: str) -> bytes:
        """Download file contents."""
        ...

    @abstractmethod
    async def delete(self, relative_path: str) -> bool:
        """Delete a file. Returns True if successful."""
        ...


class LocalFileStorage(FileStorageBackend):
    """Store files on the local filesystem."""

    name = "local"

    def __init__(self, root: Path | None = None):
        self.root = root or settings.STORAGE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: UploadFile, relative_path: str) -> StoredFile:
        full_path = self.root / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size_bytes = 0

        async with aiofiles.open(full_path, "wb") as destination:
            while chunk := await file.read(1024 * 1024):
                digest.update(chunk)
                size_bytes += len(chunk)
                await destination.write(chunk)

        return StoredFile(relative_path, size_bytes, digest.hexdigest())

    async def download(self, relative_path: str) -> bytes:
        full_path = self.root / relative_path
        if not full_path.exists():
            raise FileNotFoundError(relative_path)
        async with aiofiles.open(full_path, "rb") as stored_file:
            return await stored_file.read()

    async def delete(self, relative_path: str) -> bool:
        full_path = self.root / relative_path
        if full_path.exists():
            full_path.unlink()
            return True
        return False


class VercelBlobStorage(FileStorageBackend):
    """Store protected attachments in a private Vercel Blob store."""

    name = "vercel_blob"

    def __init__(self, client: Any | None = None):
        if client is None:
            from vercel.blob import AsyncBlobClient

            client = AsyncBlobClient()
        self.client = client

    async def upload(self, file: UploadFile, relative_path: str) -> StoredFile:
        digest = hashlib.sha256()
        size_bytes = 0

        async def chunks():
            nonlocal size_bytes
            while chunk := await file.read(1024 * 1024):
                digest.update(chunk)
                size_bytes += len(chunk)
                yield chunk

        blob = await self.client.put(
            relative_path,
            chunks(),
            access="private",
            content_type=file.content_type,
        )
        return StoredFile(blob.pathname, size_bytes, digest.hexdigest())

    async def download(self, relative_path: str) -> bytes:
        result = await self.client.get(relative_path, access="private")
        if result is None or result.status_code != 200 or result.stream is None:
            raise FileNotFoundError(relative_path)
        return b"".join([chunk async for chunk in result.stream])

    async def delete(self, relative_path: str) -> bool:
        await self.client.delete(relative_path)
        return True


class MinioFileStorage(FileStorageBackend):
    """Placeholder for the planned MinIO integration."""

    name = "minio"

    def __init__(self):
        self.endpoint = settings.MINIO_ENDPOINT
        self.bucket = settings.MINIO_BUCKET

    async def upload(self, file: UploadFile, relative_path: str) -> StoredFile:
        raise NotImplementedError("MinIO storage will be implemented in Phase 3+")

    async def download(self, relative_path: str) -> bytes:
        raise NotImplementedError("MinIO storage will be implemented in Phase 3+")

    async def delete(self, relative_path: str) -> bool:
        raise NotImplementedError("MinIO storage will be implemented in Phase 3+")


def get_storage_backend() -> FileStorageBackend:
    """Return the storage provider configured for the current environment."""
    if settings.storage_backend == "vercel_blob":
        return VercelBlobStorage()
    if settings.storage_backend == "minio":
        return MinioFileStorage()
    return LocalFileStorage()
