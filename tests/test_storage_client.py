from typing import cast

import pytest

from scaffold.config import Settings
from scaffold.storage import StorageClient, create_storage_backend
from scaffold.storage.contracts import StoredObject, StoredObjectBody
from scaffold.storage.s3 import build_public_url


class InMemoryStorage:
    def __init__(self, bucket_name: str, public_base_url: str) -> None:
        self._bucket_name = bucket_name
        self._public_base_url = public_base_url
        self._objects: dict[str, tuple[bytes, str | None, dict[str, str]]] = {}

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def upload(
        self,
        key: str,
        content: bytes | str,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        body = content.encode("utf-8") if isinstance(content, str) else content
        self._objects[key] = (body, content_type, dict(metadata or {}))
        return StoredObject(
            bucket=self._bucket_name,
            key=key,
            url=build_public_url(self._public_base_url, self._bucket_name, key),
            etag="memory-etag",
            content_type=content_type,
        )

    async def get(self, key: str) -> StoredObjectBody | None:
        stored = self._objects.get(key)
        if stored is None:
            return None
        body, content_type, metadata = stored
        return StoredObjectBody(
            bucket=self._bucket_name,
            key=key,
            url=build_public_url(self._public_base_url, self._bucket_name, key),
            etag="memory-etag",
            content_type=content_type,
            body=body,
            metadata=metadata,
        )

    async def delete(self, key: str) -> bool:
        self._objects.pop(key, None)
        return True


@pytest.mark.asyncio
async def test_storage_client_upload_get_delete() -> None:
    client = StorageClient(InMemoryStorage("worker-bucket", "https://cdn.example.com"))
    await client.connect()

    uploaded = await client.upload(
        "artifacts/output.json",
        b'{"ok":true}',
        content_type="application/json",
        metadata={"scope": "worker"},
    )
    fetched = await client.get("artifacts/output.json")
    deleted = await client.delete("artifacts/output.json")

    assert uploaded.bucket == "worker-bucket"
    assert uploaded.key == "artifacts/output.json"
    assert uploaded.url == "https://cdn.example.com/worker-bucket/artifacts/output.json"
    assert fetched is not None
    assert fetched.body == b'{"ok":true}'
    assert fetched.content_type == "application/json"
    assert fetched.metadata == {"scope": "worker"}
    assert deleted is True
    assert await client.get("artifacts/output.json") is None
    assert await client.delete("artifacts/output.json") is True

    await client.close()


@pytest.mark.asyncio
async def test_storage_client_upload_converts_str_to_utf8() -> None:
    client = StorageClient(InMemoryStorage("docs", "https://cdn.example.com"))

    await client.upload("notes/resume.txt", "olá mundo")
    fetched = await client.get("notes/resume.txt")

    assert fetched is not None
    assert fetched.body == "olá mundo".encode("utf-8")


@pytest.mark.asyncio
async def test_storage_client_from_settings_uses_bucket_name() -> None:
    s3_module = pytest.importorskip("boto3")
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@localhost:3306/db",
            "storage_access_key_id": "key",
            "storage_secret_access_key": "secret",
        },
    )

    client = StorageClient.from_settings(settings, "worker-bucket")

    assert s3_module is not None
    assert client._backend.__class__.__name__ == "S3CompatibleStorage"


def test_storage_factory_requires_bucket_name() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@localhost:3306/db",
            "storage_access_key_id": "key",
            "storage_secret_access_key": "secret",
        },
    )

    with pytest.raises(ValueError, match="bucket_name is required"):
        create_storage_backend(settings, "")


def test_storage_factory_creates_s3_backend() -> None:
    pytest.importorskip("boto3")
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@localhost:3306/db",
            "storage_endpoint_url": "https://t3.storageapi.dev",
            "storage_region": "auto",
            "storage_access_key_id": "key",
            "storage_secret_access_key": "secret",
        },
    )

    backend = create_storage_backend(settings, "worker-bucket")

    assert backend.__class__.__name__ == "S3CompatibleStorage"


@pytest.mark.parametrize(
    ("field_name", "expected_message"),
    [
        ("storage_access_key_id", "storage_access_key_id is required"),
        ("storage_secret_access_key", "storage_secret_access_key is required"),
    ],
)
def test_storage_factory_requires_credentials(field_name: str, expected_message: str) -> None:
    payload = {
        "database_url": "mysql+asyncmy://u:p@localhost:3306/db",
        "storage_endpoint_url": "https://t3.storageapi.dev",
        "storage_region": "auto",
        "storage_access_key_id": "key",
        "storage_secret_access_key": "secret",
    }
    payload[field_name] = cast(object, " " if field_name == "storage_access_key_id" else None)
    settings = Settings.model_validate(payload)

    with pytest.raises(ValueError, match=expected_message):
        create_storage_backend(settings, "worker-bucket")


def test_storage_factory_requires_endpoint_url() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "mysql+asyncmy://u:p@localhost:3306/db",
            "storage_endpoint_url": " ",
            "storage_access_key_id": "key",
            "storage_secret_access_key": "secret",
        },
    )

    with pytest.raises(ValueError, match="storage_endpoint_url is required"):
        create_storage_backend(settings, "worker-bucket")


def test_build_public_url_uses_endpoint_base_when_not_overridden() -> None:
    assert (
        build_public_url("https://t3.storageapi.dev", "worker-bucket", "files/cv 2026.pdf")
        == "https://t3.storageapi.dev/worker-bucket/files/cv%202026.pdf"
    )


def test_build_public_url_uses_explicit_public_base_url() -> None:
    assert (
        build_public_url("https://public.example.com/storage", "worker-bucket", "files/cv.pdf")
        == "https://public.example.com/storage/worker-bucket/files/cv.pdf"
    )
