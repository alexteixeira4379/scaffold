from __future__ import annotations

from scaffold.config import Settings
from scaffold.storage.ports import StoragePort


def create_storage_backend(settings: Settings, bucket_name: str) -> StoragePort:
    if not bucket_name.strip():
        raise ValueError("bucket_name is required to create a storage client")
    if not settings.storage_endpoint_url.strip():
        raise ValueError("storage_endpoint_url is required to create a storage client")
    if not settings.storage_access_key_id or not settings.storage_access_key_id.strip():
        raise ValueError("storage_access_key_id is required to create a storage client")
    if not settings.storage_secret_access_key or not settings.storage_secret_access_key.strip():
        raise ValueError("storage_secret_access_key is required to create a storage client")
    from scaffold.storage.s3 import S3CompatibleStorage

    return S3CompatibleStorage(
        endpoint_url=settings.storage_endpoint_url,
        region=settings.storage_region,
        access_key_id=settings.storage_access_key_id,
        secret_access_key=settings.storage_secret_access_key,
        bucket_name=bucket_name,
        public_base_url=settings.storage_public_base_url,
    )
