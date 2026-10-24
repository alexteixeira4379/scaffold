"""Shared bounds for completed ATS catalog scans (not retries or pagination)."""

DEFAULT_INTERVAL_SECONDS = 86400
MIN_INTERVAL_SECONDS = 21600
MAX_INTERVAL_SECONDS = 604800


def collection_interval(value: int | None = None) -> int:
    """Daily by default; explicit schedules may range from six hours to seven days."""
    return max(MIN_INTERVAL_SECONDS, min(int(value or DEFAULT_INTERVAL_SECONDS), MAX_INTERVAL_SECONDS))
