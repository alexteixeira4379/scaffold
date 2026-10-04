"""Bounded structural diagnostics; never retain generated values or unknown keys."""

import json


SAFE_FIELDS = frozenset({"verdict", "score", "candidate_evidence_ids", "job_evidence_ids",
                         "gaps", "rationale", "candidate_evidence", "job_evidence",
                         "id1", "id2", "id3", "gap1", "gap2", "gap3", "gap4", "gap5"})


def _kind(value):
    return {dict: "object", list: "array", str: "string", bool: "boolean", int: "integer",
            float: "number", type(None): "null"}.get(type(value), "unknown")


def generation_shape(generation, schema):
    """Describe failed JSON against simple supplied schema; not an acceptance validator."""
    if not isinstance(generation, str):
        return {"json_parsed": False, "reason": "generation_not_text"}
    if len(generation) > 65536:
        return {"json_parsed": False, "reason": "diagnostic_size_limit"}
    try:
        value = json.loads(generation)
    except RecursionError:
        return {"json_parsed": False, "reason": "diagnostic_depth_limit"}
    except json.JSONDecodeError as exc:
        return {"json_parsed": False, "reason": "json_decode_error", "line": exc.lineno,
                "column": exc.colno, "position": exc.pos,
                "markdown_fence": generation.lstrip().startswith("```")}
    result = {"json_parsed": True, "root_type": _kind(value), "issues": [],
              "inspected_nodes": 0, "truncated": False}

    def issue(path, reason, **details):
        if len(result["issues"]) >= 24:
            result["truncated"] = True
            return
        result["issues"].append({"path": path, "reason": reason, **details})

    def visit(item, node, path, depth):
        if result["inspected_nodes"] >= 128 or depth > 8:
            result["truncated"] = True
            return
        result["inspected_nodes"] += 1
        if not isinstance(node, dict):
            return
        actual, expected = _kind(item), node.get("type")
        allowed = expected if isinstance(expected, list) else [expected]
        if expected and actual not in allowed and not (actual == "integer" and "number" in allowed):
            issue(path, "type_mismatch", actual_type=actual)
            return
        if "enum" in node and not any(type(item) is type(option) and item == option for option in node["enum"]):
            issue(path, "enum_mismatch", actual_type=actual)
        if isinstance(item, dict):
            props = node.get("properties") or {}
            extra = len(item.keys() - props.keys())
            if extra and node.get("additionalProperties") is False:
                issue(path, "unknown_fields", count=extra)
            for key in node.get("required", []):
                if key not in item:
                    issue(path + "." + (key if key in SAFE_FIELDS else "<field>"), "required_missing")
            for key, child in props.items():
                if key in item:
                    visit(item[key], child, path + "." + (key if key in SAFE_FIELDS else "<field>"), depth + 1)
        elif isinstance(item, list):
            if "maxItems" in node and len(item) > node["maxItems"]:
                issue(path, "max_items", count=len(item))
            for index, child in enumerate(item[:32]):
                visit(child, node.get("items", {}), f"{path}[{index}]", depth + 1)
            if len(item) > 32:
                result["truncated"] = True

    visit(value, schema, "$", 0)
    return result
