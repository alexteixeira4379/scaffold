"""Allowlisted numeric rate-limit telemetry; never retain arbitrary HTTP headers."""
import math
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def duration_seconds(value):
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        number = float(value)
    except ValueError:
        parts = re.findall(r"(\d+(?:\.\d+)?)(ms|d|h|m|s)", value)
        if not parts or "".join(n + unit for n, unit in parts) != value:
            return None
        units = {"d": 86400, "h": 3600, "m": 60, "s": 1, "ms": .001}
        number = sum(float(n) * units[unit] for n, unit in parts)
    return min(604800, math.ceil(number)) if math.isfinite(number) and number >= 0 else None


def safe_rate_limits(headers, *, now=None):
    """Groq requests headers describe RPD; tokens headers describe TPM.

    No account quota is inferred from a plan name or an error message.
    """
    result = {}
    for kind in ("requests", "tokens"):
        for field in ("limit", "remaining"):
            value = headers.get(f"x-ratelimit-{field}-{kind}")
            if isinstance(value, str) and re.fullmatch(r"\d{1,12}", value):
                result[f"{field}_{kind}"] = int(value)
        value = duration_seconds(headers.get(f"x-ratelimit-reset-{kind}"))
        if value is not None:
            result[f"reset_{kind}_seconds"] = value
    retry = headers.get("retry-after")
    seconds = duration_seconds(retry)
    if seconds is None and isinstance(retry, str) and len(retry) <= 80:
        try:
            date = parsedate_to_datetime(retry)
            if date.tzinfo is not None:
                seconds = max(0, min(604800, math.ceil((date - (now or datetime.now(UTC))).total_seconds())))
        except (ValueError, TypeError, OverflowError):
            pass
    if seconds is not None:
        result["retry_after_seconds"] = seconds
    return result
