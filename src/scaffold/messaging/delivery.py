def read_count_from_amqp(redelivered: bool, headers: object) -> int:
    if not isinstance(headers, dict):
        return 2 if redelivered else 1
    raw = headers.get("x-delivery-count")
    if isinstance(raw, int) and raw >= 1:
        return raw
    if isinstance(raw, str) and raw.isdigit():
        n = int(raw)
        return n if n >= 1 else 1
    return 2 if redelivered else 1
