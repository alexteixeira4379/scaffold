from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def ensure_mysql_utf8mb4_charset(url: str) -> str:
    raw = url.strip()
    if not raw.startswith("mysql+"):
        return raw
    parts = urlparse(raw)
    pairs = list(parse_qsl(parts.query, keep_blank_values=True))
    charset_idx: int | None = None
    for i, (key, _) in enumerate(pairs):
        if key.lower() == "charset":
            charset_idx = i
            break
    if charset_idx is not None:
        cur = pairs[charset_idx][1].lower().replace("-", "").replace("_", "")
        if cur.startswith("utf8mb4"):
            return raw
        pairs[charset_idx] = ("charset", "utf8mb4")
    else:
        pairs.append(("charset", "utf8mb4"))
    return urlunparse(parts._replace(query=urlencode(pairs)))
