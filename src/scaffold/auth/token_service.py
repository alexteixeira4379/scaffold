"""JWT token service: issue, decode, blacklist and refresh tokens.

Moved from auth-api into the scaffold so every service shares one
implementation of token handling. The cache-backed methods (blacklist,
refresh storage) are optional helpers used by the auth service; plain
issue/decode work with no cache.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

JWT_ALGORITHM = "HS256"


class TokenService:
    def __init__(
        self,
        secret: str,
        access_expire_minutes: int = 60,
        refresh_expire_days: int = 30,
    ) -> None:
        self._secret = secret
        self._access_expire_minutes = access_expire_minutes
        self._refresh_expire_days = refresh_expire_days
        self._algorithm = JWT_ALGORITHM

    def create_access_token(self, candidate_id: int) -> tuple[str, str, int]:
        """Returns (token, jti, expires_in_seconds)."""
        now = datetime.now(UTC)
        jti = str(uuid.uuid4())
        exp = now + timedelta(minutes=self._access_expire_minutes)
        payload = {
            "sub": str(candidate_id),
            "exp": exp,
            "iat": now,
            "jti": jti,
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, jti, self._access_expire_minutes * 60

    def create_refresh_token(self, candidate_id: int) -> tuple[str, str, int]:
        """Returns (token, jti, expires_in_seconds)."""
        now = datetime.now(UTC)
        jti = str(uuid.uuid4())
        exp = now + timedelta(days=self._refresh_expire_days)
        payload = {
            "sub": str(candidate_id),
            "exp": exp,
            "iat": now,
            "jti": jti,
            "type": "refresh",
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, jti, self._refresh_expire_days * 24 * 60 * 60

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and verify a JWT. Raises jwt.InvalidTokenError on failure."""
        return jwt.decode(token, self._secret, algorithms=[self._algorithm])

    async def blacklist_token(self, cache: Any, jti: str, remaining_seconds: int) -> None:
        """Add a jti to the blacklist with TTL = remaining token expiration."""
        if remaining_seconds > 0:
            await cache.set(f"blacklist:{jti}", "1", ttl_s=remaining_seconds)

    async def is_blacklisted(self, cache: Any, jti: str) -> bool:
        """Check if a jti is blacklisted."""
        return await cache.exists(f"blacklist:{jti}")

    async def store_refresh_token(self, cache: Any, jti: str, candidate_id: int) -> None:
        """Store refresh token reference in cache."""
        ttl_s = self._refresh_expire_days * 24 * 60 * 60
        await cache.set(f"refresh:{jti}", str(candidate_id), ttl_s=ttl_s)

    async def validate_refresh_token(self, cache: Any, token: str) -> tuple[int, str] | None:
        """Validate refresh token. Returns (candidate_id, jti) or None."""
        try:
            payload = self.decode_token(token)
        except jwt.InvalidTokenError:
            return None

        if payload.get("type") != "refresh":
            return None

        jti = payload.get("jti", "")
        stored = await cache.get(f"refresh:{jti}")
        if stored is None:
            return None

        candidate_id = int(payload["sub"])
        if stored != str(candidate_id):
            return None

        return candidate_id, jti

    async def revoke_refresh_token(self, cache: Any, jti: str) -> None:
        """Remove refresh token from cache (revocation)."""
        await cache.delete(f"refresh:{jti}")
