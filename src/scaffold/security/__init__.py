"""Transport bounds and secret validation shared by public HTTP services."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping

from starlette.responses import JSONResponse

_EXAMPLE_SECRETS = {
    "change-me", "changeme", "change-me-256-bit-secret", "internal-key",
    "local-development-only-change-before-deploy", "your-secret-key",
}


def validate_secret(value: str | None, name: str, *, production: bool | None = None) -> str:
    """Never accept missing/example values; production keys need at least 32 bytes.

    Local fixtures may use short, explicit test keys. No environment gets a
    fallback key. Values are deliberately excluded from errors and logs.
    """
    if production is None:
        production = bool(os.getenv("RAILWAY_ENVIRONMENT_ID")) or os.getenv("APP_ENV", "").lower() == "production"
    if not value or not value.strip() or value.strip().lower() in _EXAMPLE_SECRETS:
        raise RuntimeError(f"{name} must be configured with a private secret")
    if production and len(value.encode()) < 32:
        raise RuntimeError(f"{name} must contain at least 32 bytes in production")
    return value


def validate_auth_configuration() -> None:
    """Call before starting an API that accepts JWT and/or service credentials."""
    for name in ("JWT_SECRET", "SERVICE_API_KEY"):
        validate_secret(os.getenv(name), name)


class BodyLimitMiddleware:
    """Bound actual bytes *before* JSON/multipart parsing, including chunked input.

    A bounded buffer is replayed to the app only after admission. This avoids
    framework exception handlers accidentally translating a receive exception
    into a successful response. Path overrides are exact URL paths.
    """

    def __init__(self, app, *, max_bytes: int = 1024 * 1024,
                 path_limits: Mapping[str, int] | None = None,
                 read_timeout_seconds: float = 30):
        if max_bytes <= 0 or read_timeout_seconds <= 0 or any(v <= 0 for v in (path_limits or {}).values()):
            raise ValueError("Body limits and read timeout must be positive")
        self.app = app
        self.max_bytes = max_bytes
        self.path_limits = dict(path_limits or {})
        self.read_timeout_seconds = read_timeout_seconds

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        maximum = self.path_limits.get(scope.get("path", ""), self.max_bytes)
        lengths = [v for k, v in scope.get("headers", []) if k.lower() == b"content-length"]
        if lengths:
            try:
                if len(lengths) != 1 or not lengths[0].isdigit():
                    raise ValueError()
                declared = int(lengths[0])
            except ValueError:
                return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
            if declared > maximum:
                return await self._too_large(scope, receive, send)
        chunks, total = [], 0
        try:
            async with asyncio.timeout(self.read_timeout_seconds):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    total += len(chunk)
                    if total > maximum:
                        return await self._too_large(scope, receive, send)
                    chunks.append(message)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await JSONResponse({"detail": "Request body read timed out"}, status_code=408)(scope, receive, send)
        iterator = iter(chunks)

        async def bounded_receive():
            try:
                return next(iterator)
            except StopIteration:
                return await receive()

        return await self.app(scope, bounded_receive, send)

    @staticmethod
    async def _too_large(scope, receive, send):
        return await JSONResponse({"detail": "Request body exceeds the allowed size"}, status_code=413)(scope, receive, send)
