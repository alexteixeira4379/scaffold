from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class StoredObject:
    bucket: str
    key: str
    url: str
    etag: str | None = None
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class StoredObjectBody(StoredObject):
    body: bytes = b""
    metadata: dict[str, str] = field(default_factory=dict)
