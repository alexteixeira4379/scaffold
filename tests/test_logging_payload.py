from __future__ import annotations

from scaffold.logging.payload import PayloadLogFormatter, approximate_json_bytes


def test_payload_log_formatter_truncates_long_text() -> None:
    fmt = PayloadLogFormatter(text_field_max=5, output_max=200)
    preview = fmt.preview({"text": "abcdefgh"})
    assert "ab..." in preview


def test_approximate_json_bytes_handles_non_json_values() -> None:
    class X:
        def __str__(self) -> str:
            return "x"

    size = approximate_json_bytes({"v": X()})
    assert size > 0
