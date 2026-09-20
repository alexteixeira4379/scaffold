from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scaffold.matching.eligibility_engine import ProfileWithKeywords, evaluate_profile


def profile(keywords):
    return ProfileWithKeywords(
        SimpleNamespace(
            id=1,
            target_country=None,
            remote_preference="unknown",
            employment_preference="unknown",
            experience_level="unknown",
        ),
        [SimpleNamespace(keyword=k, match_policy=p, active=True) for k, p in keywords],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "keywords, approved",
    [
        ([("Python", "required"), ("SQL", "required")], False),
        ([("  PYTHON  ", "required")], True),
        ([("Python", "forbidden")], False),
        ([("Python", "exclude")], False),
        ([("Python", "made_up")], False),
        ([("Python", "desirable")], True),
        ([("Python", "include")], True),
    ],
)
async def test_keyword_constraints_cannot_be_overridden_by_entity_match(keywords, approved):
    job = SimpleNamespace(
        id=2,
        country=None,
        remote_type="unknown",
        employment_type="unknown",
        experience_level="unknown",
    )
    result = await evaluate_profile(
        AsyncMock(),
        job,
        [SimpleNamespace(keyword="python")],
        profile(keywords),
        entity_context={"jobs": {2: {10}}, "candidate": {10}, "parents": {}},
    )
    assert result.approved is approved


@pytest.mark.asyncio
async def test_required_is_a_gate_and_desirable_adds_score():
    job = SimpleNamespace(
        id=2,
        country=None,
        remote_type="unknown",
        employment_type="unknown",
        experience_level="unknown",
    )
    args = (AsyncMock(), job, [SimpleNamespace(keyword="python")])
    context = {"jobs": {}, "candidate": set(), "parents": {}}
    required = await evaluate_profile(
        *args, profile([("python", "required")]), entity_context=context
    )
    desired = await evaluate_profile(
        *args, profile([("python", "desirable")]), entity_context=context
    )
    assert required.routing_score == 0
    assert desired.routing_score == 30
