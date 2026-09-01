from scaffold.candidate.profile_completeness import (
    completion_score,
    missing_base_fields,
    summary,
)


def test_missing_base_fields_empty_candidate():
    assert missing_base_fields({}) == ["full_name", "contact"]


def test_missing_base_fields_placeholder_name_counts_as_missing():
    candidate = {"full_name": "WhatsApp User", "email": "a@b.com"}
    assert missing_base_fields(candidate) == ["full_name"]


def test_missing_base_fields_email_satisfies_contact():
    candidate = {"full_name": "Maria Silva", "email": "maria@test.com"}
    assert missing_base_fields(candidate) == []


def test_missing_base_fields_linkedin_satisfies_contact():
    candidate = {"full_name": "Maria Silva", "linkedin_url": "https://linkedin.com/in/maria"}
    assert missing_base_fields(candidate) == []


def test_missing_base_fields_no_contact():
    candidate = {"full_name": "Maria Silva"}
    assert missing_base_fields(candidate) == ["contact"]


def test_completion_score_full():
    candidate = {"full_name": "Maria Silva", "email": "maria@test.com"}
    assert completion_score(candidate) == 100


def test_completion_score_empty():
    assert completion_score({}) == 0


def test_completion_score_partial():
    candidate = {"full_name": "Maria Silva"}
    assert completion_score(candidate) == 50


def test_summary_complete():
    candidate = {"full_name": "Maria Silva", "email": "maria@test.com"}
    result = summary(candidate)
    assert result == {"missing_fields": [], "score": 100, "is_complete": True}


def test_summary_incomplete():
    result = summary({})
    assert result["is_complete"] is False
    assert result["score"] == 0
