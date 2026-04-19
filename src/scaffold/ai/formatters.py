import json
import re
from collections.abc import Sequence

from scaffold.ai.contracts import ChatMessage, ResponseMode


def with_json_instruction(messages: list[ChatMessage]) -> list[ChatMessage]:
    out = list(messages)
    extra = (
        "You must respond with a single valid JSON object only. "
        "Do not wrap the JSON in markdown code fences."
    )
    if out and out[0].role == "system":
        merged = out[0].content + "\n\n" + extra
        out[0] = ChatMessage(role="system", content=merged)
    else:
        out.insert(0, ChatMessage(role="system", content=extra))
    return out


def prepare_messages(output: ResponseMode, messages: Sequence[ChatMessage]) -> list[ChatMessage]:
    base = list(messages)
    if output == ResponseMode.JSON:
        return with_json_instruction(base)
    return base


def parse_json_content(raw: str) -> dict[str, object]:
    s = raw.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", s, re.DOTALL | re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()
    parsed: object = json.loads(s)
    if not isinstance(parsed, dict):
        raise ValueError("json root must be an object")
    return {str(k): v for k, v in parsed.items()}
