"""FastAPI authentication dependencies shared across all services.

All dependencies return a uniform ``AuthContext`` so routes never have to
care whether the caller used a JWT (end user) or a service key
(service-to-service). This replaces the per-service, subtly divergent
copies of this logic that previously lived in each API's dependencies.py.

Configuration is read from the environment so the module is self-contained
and does not couple to any single service's Settings object:

- ``JWT_SECRET``       — HMAC secret for HS256 tokens (default "change-me")
- ``SERVICE_API_KEY``  — shared internal key for service auth (default "internal-key")

A service may override these lookups by passing explicit ``secret`` /
``service_key`` values to the factory helpers below.
"""

from __future__ import annotations

import os

import jwt
from fastapi import Header, HTTPException, status

from scaffold.auth.context import AuthContext
from scaffold.auth.token_service import JWT_ALGORITHM


def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "change-me")


def get_service_api_key() -> str:
    return os.environ.get("SERVICE_API_KEY", "internal-key")


def _decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc


def _candidate_id_from_claims(claims: dict) -> int:
    sub = claims.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing 'sub' claim"
        )
    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 'sub' claim must be an integer",
        ) from exc


def _parse_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header"
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header format"
        )
    return parts[1]


def verify_jwt(authorization: str | None = Header(None, alias="Authorization")) -> AuthContext:
    """Authenticate an end user via ``Authorization: Bearer <jwt>``.

    Returns an AuthContext with ``candidate_id`` from the 'sub' claim and
    ``is_service=False``.
    """
    token = _parse_bearer(authorization)
    claims = _decode_jwt(token)
    candidate_id = _candidate_id_from_claims(claims)
    return AuthContext(candidate_id=candidate_id, is_service=False, claims=claims)


def verify_service_key(
    x_service_key: str | None = Header(None, alias="X-Service-Key"),
    x_candidate_id: str | None = Header(None, alias="X-Candidate-Id"),
) -> AuthContext:
    """Authenticate an internal service via ``X-Service-Key``.

    The optional ``X-Candidate-Id`` header names the candidate the service
    is acting on behalf of. Returns an AuthContext with ``is_service=True``.
    """
    if x_service_key is None or x_service_key != get_service_api_key():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid service key"
        )
    candidate_id = _coerce_optional_candidate_id(x_candidate_id)
    return AuthContext(candidate_id=candidate_id, is_service=True, claims={})


def verify_jwt_or_service(
    authorization: str | None = Header(None, alias="Authorization"),
    x_service_key: str | None = Header(None, alias="X-Service-Key"),
    x_candidate_id: str | None = Header(None, alias="X-Candidate-Id"),
) -> AuthContext:
    """Accept either a valid service key OR a JWT.

    Service key takes precedence: if a valid ``X-Service-Key`` is present the
    caller is treated as an internal service (candidate taken from
    ``X-Candidate-Id`` if provided). Otherwise falls back to JWT auth.
    """
    if x_service_key is not None and x_service_key == get_service_api_key():
        candidate_id = _coerce_optional_candidate_id(x_candidate_id)
        return AuthContext(candidate_id=candidate_id, is_service=True, claims={})
    return verify_jwt(authorization)


def verify_candidate_access(
    candidate_id: int,
    authorization: str | None = Header(None, alias="Authorization"),
    x_service_key: str | None = Header(None, alias="X-Service-Key"),
) -> AuthContext:
    """Guard a ``/candidates/{candidate_id}/...`` route.

    A valid service key grants access to any candidate (trusted internal
    caller). Otherwise the JWT 'sub' must match the ``candidate_id`` in the
    path, else 403.
    """
    if x_service_key is not None and x_service_key == get_service_api_key():
        return AuthContext(candidate_id=candidate_id, is_service=True, claims={})

    ctx = verify_jwt(authorization)
    if ctx.candidate_id != candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: candidate_id mismatch",
        )
    return ctx


def _coerce_optional_candidate_id(x_candidate_id: str | None) -> int | None:
    if x_candidate_id is None:
        return None
    try:
        return int(x_candidate_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Candidate-Id header",
        ) from exc
