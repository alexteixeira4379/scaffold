from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from scaffold.storage.contracts import StoredObject, StoredObjectBody


def build_public_url(base_url: str, bucket_name: str, key: str) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_bucket = bucket_name.strip().strip("/")
    normalized_key = quote(key.lstrip("/"), safe="/")
    return f"{normalized_base}/{normalized_bucket}/{normalized_key}"


class S3CompatibleStorage:
    def __init__(
        self,
        *,
        endpoint_url: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_base_url: str | None = None,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._bucket_name = bucket_name
        self._public_base_url = public_base_url or endpoint_url
        import boto3
        from botocore.exceptions import ClientError

        self._client_error = ClientError
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            await asyncio.to_thread(close)

    async def upload(
        self,
        key: str,
        content: bytes | str,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        body = content.encode("utf-8") if isinstance(content, str) else content

        def _upload() -> dict[str, object]:
            extra_args: dict[str, object] = {}
            if content_type is not None:
                extra_args["ContentType"] = content_type
            if metadata is not None:
                extra_args["Metadata"] = dict(metadata)
            return self._client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=body,
                **extra_args,
            )

        response = await asyncio.to_thread(_upload)
        return StoredObject(
            bucket=self._bucket_name,
            key=key,
            url=build_public_url(self._public_base_url, self._bucket_name, key),
            etag=_coerce_optional_str(response.get("ETag")),
            content_type=content_type,
        )

    async def get(self, key: str) -> StoredObjectBody | None:
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket_name,
                Key=key,
            )
        except self._client_error as exc:
            if _is_not_found_error(exc):
                return None
            raise

        stream = response["Body"]
        body = await asyncio.to_thread(stream.read)
        await asyncio.to_thread(stream.close)
        return StoredObjectBody(
            bucket=self._bucket_name,
            key=key,
            url=build_public_url(self._public_base_url, self._bucket_name, key),
            etag=_coerce_optional_str(response.get("ETag")),
            content_type=_coerce_optional_str(response.get("ContentType")),
            body=body,
            metadata=_normalize_metadata(response.get("Metadata")),
        )

    async def delete(self, key: str) -> bool:
        try:
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._bucket_name,
                Key=key,
            )
        except self._client_error as exc:
            if _is_not_found_error(exc):
                return True
            raise
        return True


def _normalize_metadata(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def _coerce_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _is_not_found_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return False
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return False
    code = error.get("Code")
    return code in {"404", "NoSuchKey", "NotFound"}
