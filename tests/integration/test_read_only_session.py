from __future__ import annotations

import os

import pytest
from sqlalchemy.exc import DBAPIError, OperationalError

from scaffold.constants.schema_enums import ResumeProfileSource
from scaffold.models.candidate.candidates import Candidate
from scaffold.models.resume.resume_profiles import ResumeProfile

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="Requer DATABASE_URL configurada",
)


@pytest.fixture
async def candidate_with_profile():
    from scaffold.db.session import close_engine, get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        candidate = Candidate(
            full_name="Read Only Session Test",
            email="read-only-session-test@example.com",
        )
        session.add(candidate)
        await session.flush()

        profile = ResumeProfile(
            candidate_id=candidate.id,
            source=ResumeProfileSource.DIRECT_API,
        )
        session.add(profile)
        await session.commit()
        candidate_id = candidate.id

    yield candidate_id

    async with session_factory() as session:
        await session.execute(
            ResumeProfile.__table__.delete().where(ResumeProfile.candidate_id == candidate_id)
        )
        await session.execute(Candidate.__table__.delete().where(Candidate.id == candidate_id))
        await session.commit()

    await close_engine()


async def test_get_read_only_session_allows_reads(candidate_with_profile):
    from scaffold.db.session import get_read_only_session
    from scaffold.repositories.resume_repositories import resume_profile_repository

    async with get_read_only_session() as session:
        profile = await resume_profile_repository.get_by_candidate_id(
            session, candidate_with_profile
        )

    assert profile is not None
    assert profile.candidate_id == candidate_with_profile


async def test_get_read_only_session_rejects_writes(candidate_with_profile):
    from scaffold.db.session import get_read_only_session

    with pytest.raises((OperationalError, DBAPIError)):
        async with get_read_only_session() as session:
            session.add(
                ResumeProfile(
                    candidate_id=candidate_with_profile,
                    source=ResumeProfileSource.DIRECT_API,
                )
            )
            await session.flush()
