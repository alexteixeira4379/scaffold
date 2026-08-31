"""Standardized authentication context shared across all services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuthContext:
    """The result of authenticating a request.

    Every auth dependency in the platform returns this object, so routes
    have a single, uniform shape to work with regardless of whether the
    caller authenticated with a JWT (an end user) or a service key
    (an internal service-to-service call).

    Attributes:
        candidate_id: The candidate the request acts on behalf of. For JWT
            auth this comes from the token 'sub' claim; for service auth it
            comes from the X-Candidate-Id header (when provided).
        is_service: True when the request authenticated with a valid
            service key, False when it authenticated with a JWT.
        claims: The decoded JWT claims (empty for service auth).
    """

    candidate_id: int | None
    is_service: bool = False
    claims: dict[str, Any] = field(default_factory=dict)

    def require_candidate_id(self) -> int:
        """Return candidate_id, raising if it is missing.

        Useful for routes that always need a concrete candidate.
        """
        if self.candidate_id is None:
            raise ValueError("candidate_id is required but was not present in the auth context")
        return self.candidate_id
