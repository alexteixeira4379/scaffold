from __future__ import annotations

from typing import Protocol

from scaffold.storage.contracts import StoredObject, StoredObjectBody


class StoragePort(Protocol):
    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def upload(
        self,
        key: str,
        content: bytes | str,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject: ...

    async def get(self, key: str) -> StoredObjectBody | None: ...

    async def delete(self, key: str) -> bool: ...
