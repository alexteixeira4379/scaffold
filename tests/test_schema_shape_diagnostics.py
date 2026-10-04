import json

from scaffold.ai.schema_shape_diagnostics import generation_shape


def schema():
    return {"type": "object", "properties": {
        "score": {"type": "integer", "enum": [80]},
        "candidate_evidence_ids": {"type": "object", "properties": {
            "id1": {"type": "string", "enum": ["", "candidate_1"]}},
            "required": ["id1"], "additionalProperties": False},
    }, "required": ["score", "candidate_evidence_ids"], "additionalProperties": False}


def test_shape_preserves_paths_types_and_missing_fields_without_values():
    body = {"score": 80.0, "candidate_evidence_ids": {"PRIVATE_NAME": "PRIVATE_CPF"},
            "PRIVATE_FIELD": "PRIVATE_VALUE"}
    result = generation_shape(json.dumps(body), schema())
    assert result["json_parsed"] is True
    assert {"path": "$.score", "reason": "type_mismatch", "actual_type": "number"} in result["issues"]
    assert {"path": "$.candidate_evidence_ids.id1", "reason": "required_missing"} in result["issues"]
    assert {"path": "$", "reason": "unknown_fields", "count": 1} in result["issues"]
    assert "PRIVATE" not in json.dumps(result)


def test_wrong_id_only_reports_enum_mismatch():
    result = generation_shape(json.dumps({"score": 80, "candidate_evidence_ids": {"id1": "PRIVATE_CPF"}}), schema())
    assert result["issues"] == [{"path": "$.candidate_evidence_ids.id1", "reason": "enum_mismatch", "actual_type": "string"}]
    assert "PRIVATE" not in json.dumps(result)


def test_array_instead_of_fixed_slots_and_markdown_are_not_repaired():
    result = generation_shape(json.dumps({"score": 80, "candidate_evidence_ids": ["PRIVATE"]}), schema())
    assert result["issues"] == [{"path": "$.candidate_evidence_ids", "reason": "type_mismatch", "actual_type": "array"}]
    invalid = generation_shape('```json\n{"PRIVATE":"value"}\n```', schema())
    assert invalid["json_parsed"] is False and invalid["markdown_fence"] is True
    assert invalid["position"] == 0


def test_arbitrary_schema_keys_are_redacted_too():
    result = generation_shape('{}', {"type": "object", "properties": {"PRIVATE_KEY": {"type": "string"}},
                                     "required": ["PRIVATE_KEY"], "additionalProperties": False})
    assert result["issues"] == [{"path": "$.<field>", "reason": "required_missing"}]


def test_diagnostics_bound_size_and_traversal():
    assert generation_shape('x' * 65537, schema())["reason"] == "diagnostic_size_limit"
    result = generation_shape(json.dumps(["PRIVATE"] * 1000),
                              {"type": "array", "items": {"type": "integer"}, "maxItems": 10})
    assert result["truncated"] is True and len(result["issues"]) <= 24
    assert result["issues"][0] == {"path": "$", "reason": "max_items", "count": 1000}
    assert "PRIVATE" not in json.dumps(result)
