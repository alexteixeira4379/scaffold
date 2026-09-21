from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, patch

import pytest

from scaffold.matching.eligibility_engine import (
    EntityMatchResult,
    ProfileWithKeywords,
    evaluate_profile,
)


def inputs(keywords=None, job_keywords=None):
    return (
        AsyncMock(),
        Obj(
            id=1,
            country="BR",
            remote_type="unknown",
            employment_type="unknown",
            experience_level="unknown",
        ),
        job_keywords or [],
        ProfileWithKeywords(
            Obj(
                id=2,
                target_country="BR",
                remote_preference="unknown",
                employment_preference="unknown",
                experience_level="unknown",
            ),
            keywords or [],
        ),
    )


async def test_missing_classification_requires_opt_in_and_is_not_approval():
    with patch(
        "scaffold.matching.eligibility_engine.evaluate_entity_overlap", new_callable=AsyncMock
    ) as overlap:
        overlap.return_value = EntityMatchResult(False, 0, [], [], 0, 0)
        strict = await evaluate_profile(*inputs())
        fallback = await evaluate_profile(*inputs(), allow_professional_evaluation=True)
        assert not strict.approved and not strict.needs_professional_evaluation
        assert not fallback.approved and fallback.needs_professional_evaluation
        assert fallback.filters["professional"] == "needs_evaluation"


@pytest.mark.parametrize("policy", ["required", "exclude"])
async def test_fallback_never_bypasses_keyword_restrictions(policy):
    with patch(
        "scaffold.matching.eligibility_engine.evaluate_entity_overlap", new_callable=AsyncMock
    ) as overlap:
        overlap.return_value = EntityMatchResult(False, 0, [], [], 0, 0)
        result = await evaluate_profile(
            *inputs(
                [Obj(keyword="java", match_policy=policy, active=True)],
                [Obj(keyword="java")] if policy == "exclude" else [],
            ),
            allow_professional_evaluation=True,
        )
        assert not result.approved and not result.needs_professional_evaluation


async def test_classified_mismatch_is_rejected():
    with patch(
        "scaffold.matching.eligibility_engine.evaluate_entity_overlap", new_callable=AsyncMock
    ) as overlap:
        overlap.return_value = EntityMatchResult(False, 0, [], [], 3, 2)
        result = await evaluate_profile(*inputs(), allow_professional_evaluation=True)
        assert not result.approved and not result.needs_professional_evaluation


async def test_country_mismatch_is_rejected_before_fallback():
    args = inputs()
    args[1].country = "US"
    result = await evaluate_profile(*args, allow_professional_evaluation=True)
    assert not result.approved and not result.needs_professional_evaluation
