from __future__ import annotations

from typing import Any

_PLACEHOLDER_NAME = "WhatsApp User"

# field -> weight used by completion_score(); must sum to 100.
_FIELD_WEIGHTS: dict[str, int] = {
    "full_name": 50,
    "contact": 50,  # email OR linkedin_url
}


def missing_base_fields(candidate: dict[str, Any]) -> list[str]:
    """Return the base profile fields still missing for a candidate dict.

    Mirrors the rule that used to be hardcoded in conversation-worker's
    _has_basic_data: a real full_name, plus a contact (email or linkedin_url).
    """
    missing: list[str] = []

    full_name = str(candidate.get("full_name") or "").strip()
    if not full_name or full_name == _PLACEHOLDER_NAME:
        missing.append("full_name")

    email = str(candidate.get("email") or "").strip()
    linkedin = str(candidate.get("linkedin_url") or "").strip()
    if not email and not linkedin:
        missing.append("contact")

    return missing


def completion_score(candidate: dict[str, Any]) -> int:
    """Weighted 0-100 completeness score for a candidate dict."""
    missing = set(missing_base_fields(candidate))
    score = sum(weight for field, weight in _FIELD_WEIGHTS.items() if field not in missing)
    return score


def summary(candidate: dict[str, Any]) -> dict[str, Any]:
    """Compact snapshot: missing fields + score, for logging/prompts."""
    missing = missing_base_fields(candidate)
    return {
        "missing_fields": missing,
        "score": completion_score(candidate),
        "is_complete": not missing,
    }
