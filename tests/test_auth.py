"""Tests for the centralized scaffold.auth module."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException

from scaffold.auth import (
    AuthContext,
    TokenService,
    verify_candidate_access,
    verify_jwt,
    verify_jwt_or_service,
    verify_service_key,
)
from scaffold.auth.token_service import JWT_ALGORITHM

SECRET = "test-secret"
SERVICE_KEY = "test-service-key"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("SERVICE_API_KEY", SERVICE_KEY)


def _make_token(sub, secret=SECRET, exp_offset=3600, **extra):
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + exp_offset}
    payload.update(extra)
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


# --- verify_jwt ---------------------------------------------------------


def test_verify_jwt_valid():
    ctx = verify_jwt(authorization=f"Bearer {_make_token('42')}")
    assert isinstance(ctx, AuthContext)
    assert ctx.candidate_id == 42
    assert ctx.is_service is False
    assert ctx.claims["sub"] == "42"


def test_verify_jwt_missing_header():
    with pytest.raises(HTTPException) as exc:
        verify_jwt(authorization=None)
    assert exc.value.status_code == 401


def test_verify_jwt_bad_format():
    with pytest.raises(HTTPException) as exc:
        verify_jwt(authorization="Token abc")
    assert exc.value.status_code == 401


def test_verify_jwt_invalid_signature():
    bad = _make_token("42", secret="wrong-secret")
    with pytest.raises(HTTPException) as exc:
        verify_jwt(authorization=f"Bearer {bad}")
    assert exc.value.status_code == 401


def test_verify_jwt_expired():
    expired = _make_token("42", exp_offset=-10)
    with pytest.raises(HTTPException) as exc:
        verify_jwt(authorization=f"Bearer {expired}")
    assert exc.value.status_code == 401


def test_verify_jwt_missing_sub():
    token = jwt.encode({"iat": int(time.time())}, SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        verify_jwt(authorization=f"Bearer {token}")
    assert exc.value.status_code == 401


def test_verify_jwt_non_integer_sub():
    with pytest.raises(HTTPException) as exc:
        verify_jwt(authorization=f"Bearer {_make_token('not-a-number')}")
    assert exc.value.status_code == 401


# --- verify_service_key -------------------------------------------------


def test_verify_service_key_valid_no_candidate():
    ctx = verify_service_key(x_service_key=SERVICE_KEY, x_candidate_id=None)
    assert ctx.is_service is True
    assert ctx.candidate_id is None


def test_verify_service_key_valid_with_candidate():
    ctx = verify_service_key(x_service_key=SERVICE_KEY, x_candidate_id="7")
    assert ctx.is_service is True
    assert ctx.candidate_id == 7


def test_verify_service_key_missing():
    with pytest.raises(HTTPException) as exc:
        verify_service_key(x_service_key=None)
    assert exc.value.status_code == 403


def test_verify_service_key_wrong():
    with pytest.raises(HTTPException) as exc:
        verify_service_key(x_service_key="nope")
    assert exc.value.status_code == 403


def test_verify_service_key_invalid_candidate_id():
    with pytest.raises(HTTPException) as exc:
        verify_service_key(x_service_key=SERVICE_KEY, x_candidate_id="abc")
    assert exc.value.status_code == 400


# --- verify_jwt_or_service ---------------------------------------------


def test_jwt_or_service_prefers_service_key():
    ctx = verify_jwt_or_service(
        authorization=None, x_service_key=SERVICE_KEY, x_candidate_id="9"
    )
    assert ctx.is_service is True
    assert ctx.candidate_id == 9


def test_jwt_or_service_falls_back_to_jwt():
    ctx = verify_jwt_or_service(
        authorization=f"Bearer {_make_token('5')}", x_service_key=None
    )
    assert ctx.is_service is False
    assert ctx.candidate_id == 5


def test_jwt_or_service_no_auth_at_all():
    with pytest.raises(HTTPException) as exc:
        verify_jwt_or_service(authorization=None, x_service_key=None)
    assert exc.value.status_code == 401


# --- verify_candidate_access -------------------------------------------


def test_candidate_access_service_key_any_candidate():
    ctx = verify_candidate_access(candidate_id=123, x_service_key=SERVICE_KEY)
    assert ctx.is_service is True
    assert ctx.candidate_id == 123


def test_candidate_access_jwt_match():
    ctx = verify_candidate_access(
        candidate_id=42, authorization=f"Bearer {_make_token('42')}"
    )
    assert ctx.candidate_id == 42
    assert ctx.is_service is False


def test_candidate_access_jwt_mismatch():
    with pytest.raises(HTTPException) as exc:
        verify_candidate_access(
            candidate_id=99, authorization=f"Bearer {_make_token('42')}"
        )
    assert exc.value.status_code == 403


# --- TokenService -------------------------------------------------------


def test_token_service_roundtrip():
    svc = TokenService(secret=SECRET)
    token, jti, expires_in = svc.create_access_token(candidate_id=42)
    assert expires_in == 3600
    decoded = svc.decode_token(token)
    assert decoded["sub"] == "42"
    assert decoded["jti"] == jti


def test_token_service_refresh_has_type():
    svc = TokenService(secret=SECRET)
    token, _jti, _exp = svc.create_refresh_token(candidate_id=1)
    decoded = svc.decode_token(token)
    assert decoded["type"] == "refresh"


def test_token_service_wrong_secret_fails():
    svc = TokenService(secret=SECRET)
    token, _jti, _exp = svc.create_access_token(candidate_id=1)
    other = TokenService(secret="different")
    with pytest.raises(jwt.InvalidTokenError):
        other.decode_token(token)
