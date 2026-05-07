from __future__ import annotations


def normalize_text(text: str) -> str:
    """Lowercase, strip, collapse internal whitespace. Preserves accents in v1."""
    return " ".join(text.lower().strip().split())


def split_alias_field(raw: str) -> list[str]:
    """Split altLabels/hiddenLabels field by pipe | and newline, ignoring empty segments."""
    parts: list[str] = []
    for segment in raw.replace("\n", "|").split("|"):
        s = segment.strip()
        if s:
            parts.append(s)
    return parts


def deduplicate_normalized(items: list[str]) -> list[str]:
    """Return items with duplicate normalized forms removed, preserving first occurrence."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = normalize_text(item)
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result
