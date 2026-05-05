from __future__ import annotations

from scaffold.config import Settings
from scaffold.storage.contracts import StoredObject, StoredObjectBody
from scaffold.storage.factory import create_storage_backend
from scaffold.storage.ports import StoragePort


class StorageClient:
    def __init__(self, backend: StoragePort) -> None:
        self._backend = backend

    @classmethod
    def from_settings(cls, settings: Settings, bucket_name: str) -> StorageClient:
        return cls(create_storage_backend(settings, bucket_name))

    async def connect(self) -> None:
        await self._backend.connect()

    async def close(self) -> None:
        await self._backend.close()

    async def upload(
        self,
        key: str,
        content: bytes | str,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        return await self._backend.upload(
            key,
            content,
            content_type=content_type,
            metadata=metadata,
        )

    async def get(self, key: str) -> StoredObjectBody | None:
        return await self._backend.get(key)

    async def delete(self, key: str) -> bool:
        return await self._backend.delete(key)
