from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


def _truncate_str(value: str, max_chars: int) -> str:
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3] + "..."


@dataclass
class PayloadLogFormatter:
    text_field_max: int = 400
    output_max: int = 1600
    max_depth: int = 24
    browser_preview_chars: int = 800

    @staticmethod
    def text_snippet(text: str, max_chars: int) -> str:
        return _truncate_str(text, max_chars)

    def browser_extract_preview(self, text: str) -> str:
        return _truncate_str(text.strip(), self.browser_preview_chars)

    def _sanitize_value(self, value: Any, depth: int, seen: set[int]) -> Any:
        if depth > self.max_depth:
            return "<max depth>"
        if isinstance(value, str):
            return _truncate_str(value, self.text_field_max)
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, dict):
            i = id(value)
            if i in seen:
                return "<cycle>"
            seen.add(i)
            try:
                return {str(k): self._sanitize_value(v, depth + 1, seen) for k, v in value.items()}
            finally:
                seen.discard(i)
        if isinstance(value, (list, tuple)):
            i = id(value)
            if i in seen:
                return "<cycle>"
            seen.add(i)
            try:
                seq = [self._sanitize_value(item, depth + 1, seen) for item in value]
                return seq if isinstance(value, list) else tuple(seq)
            finally:
                seen.discard(i)
        if isinstance(value, (bytes, bytearray)):
            text = bytes(value).decode("utf-8", errors="replace")
            return _truncate_str(text, self.text_field_max)
        return _truncate_str(str(value), self.text_field_max)

    def sanitize(self, value: Any) -> Any:
        return self._sanitize_value(value, 0, set())

    def preview(self, value: Any) -> str:
        serialized = json.dumps(self.sanitize(value), ensure_ascii=False, default=str)
        return _truncate_str(serialized, self.output_max)


def body_preview(value: Any, *, output_max: int = 1600, text_field_max: int = 400, max_depth: int = 24) -> str:
    return PayloadLogFormatter(
        text_field_max=text_field_max,
        output_max=output_max,
        max_depth=max_depth,
    ).preview(value)


def approximate_json_bytes(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except (TypeError, ValueError, OverflowError):
        return len(str(value))
