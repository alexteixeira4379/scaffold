from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import select
from scaffold.models import (
    Candidate,
    CandidateTargetProfile,
    ProfessionalEntity,
    CandidateTargetProfileEntity,
    JobProfessionalEntity,
    Job,
    ResumeVersion,
    JobApplication,
)
from scaffold.models.domain_delivery import ApplicationAuthorization, DomainOutbox


async def seed(db):
    async with db() as session, session.begin():
        session.add(Candidate(id=1, full_name="Candidate", email="c@example.test"))
        session.add(CandidateTargetProfile(id=1, candidate_id=1, name="Developer", active=False))
        session.add(
            ProfessionalEntity(
                id=1,
                entity_type="occupation",
                canonical_name="Developer",
                normalized_name="developer",
                language="pt",
            )
        )
        session.add(
            CandidateTargetProfileEntity(
                candidate_target_profile_id=1,
                professional_entity_id=1,
                relevance="primary",
                confidence=1,
                source="test",
            )
        )
        session.add(
            Job(
                id=1,
                title="Developer",
                country="BR",
                source_label="linkedin",
                canonical_url="https://www.linkedin.com/jobs/view/1",
            )
        )
        session.add(
            JobProfessionalEntity(
                job_id=1,
                entity_id=1,
                source_field="title",
                matched_text="Developer",
                confidence=1,
                weight=1,
                extraction_method="exact",
            )
        )


async def test_no_keywords_match_waits_for_resume_then_dispatches_once_even_after_cancellation(
    db, load_service
):
    await seed(db)
    lifecycle = load_service("candidate-api", "src.services.lifecycle_service")
    async with db() as session, session.begin():
        await lifecycle.handle_subscription(
            session, {"candidate_id": 1, "aggregate_version": 1, "data": {"access_active": True}}
        )
    eligibility = load_service("job-eligibility-worker", "src.handlers.eligibility_handler")
    now = datetime.now(UTC).isoformat()
    event = eligibility.InboundMessage.model_validate(
        {
            "event_id": str(uuid4()),
            "event_name": "job.classified",
            "schema_version": "1.0",
            "occurred_at": now,
            "correlation_id": str(uuid4()),
            "job": {"id": 1, "title": "Developer"},
            "classification": {"version": "1", "classified_at": now},
        }
    )
    await eligibility._process_eligibility(
        eligibility.HandlerDeps(db, SimpleNamespace(queue_name="job.eligible"), 3), event
    )
    async with db() as session:
        eligible = await session.scalar(
            select(DomainOutbox).where(DomainOutbox.destination == "job.eligible")
        )
        payload = eligible.payload
    matching = load_service("job-match-worker", "src.handlers.match_handler")
    await matching._score_and_persist(
        matching.HandlerDeps(db, SimpleNamespace(queue_name="job.matched"), 3, 60),
        matching.InboundMessage.model_validate(payload),
    )
    async with db() as session:
        intent = await session.get(ApplicationAuthorization, (1, 1))
        assert intent.status == "waiting"
        assert intent.payload["match"]["score"] == 100
    async with db() as session, session.begin():
        session.add(
            ResumeVersion(id=1, candidate_id=1, is_current=True, storage_url="resumes/1.pdf")
        )
    from src.services.authorization_service import handle_lifecycle

    cache = AsyncMock()
    cache.get_json.return_value = [{"name": "li_at", "value": "candidate-cookie"}]
    with (
        patch("src.services.authorization_service.CacheClient.from_settings", return_value=cache),
        patch("src.services.authorization_service.get_settings"),
    ):
        async with db() as session, session.begin():
            await handle_lifecycle(session, {"candidate_id": 1, "event_name": "resume.available"})
    async with db() as session:
        outbound = await session.scalar(
            select(DomainOutbox).where(DomainOutbox.destination == "job.matched")
        )
        payload = outbound.payload
    lifecycle = load_service("candidate-api", "src.services.lifecycle_service")
    async with db() as session, session.begin():
        await lifecycle.handle_subscription(
            session, {"candidate_id": 1, "aggregate_version": 100, "data": {"access_active": False}}
        )
    application = load_service("application-worker", "src.handlers.matched_handler")
    deps = application.MatchedHandlerDeps(
        db,
        SimpleNamespace(queue_name="application.linkedin.submit"),
        SimpleNamespace(queue_name="application.ats.submit"),
        SimpleNamespace(queue_name="tracking.event"),
        None,
    )
    message = SimpleNamespace(body=payload, delete=AsyncMock(), release=AsyncMock())
    await application.handle_matched(deps, message)
    await application.handle_matched(deps, message)
    async with db() as session:
        assert len((await session.scalars(select(JobApplication))).all()) == 1
        commands = (
            await session.scalars(
                select(DomainOutbox).where(
                    DomainOutbox.destination == "application.linkedin.submit"
                )
            )
        ).all()
        assert len(commands) == 1
        assert commands[0].payload["resume_url"] == "resumes/1.pdf"
    message.release.assert_not_called()


async def test_global_coverage_is_shared_by_candidates(db, load_service):
    await seed(db)
    async with db() as session, session.begin():
        profile = await session.get(CandidateTargetProfile, 1)
        profile.active = True
        session.add(Candidate(id=2, full_name="Second"))
        session.add(CandidateTargetProfile(id=2, candidate_id=2, name="Developer", active=True))
        session.add(
            CandidateTargetProfileEntity(
                candidate_target_profile_id=2,
                professional_entity_id=1,
                relevance="primary",
                confidence=1,
                source="test",
            )
        )
    coverage = load_service("ingestion-controller-worker", "src.services.coverage_service")
    for cid in (1, 2, 1):
        async with db() as session, session.begin():
            await coverage.handle_lifecycle(session, {"candidate_id": cid})
    from scaffold.models import JobCollectionDefinition

    async with db() as session:
        assert len((await session.scalars(select(JobCollectionDefinition))).all()) == 1


async def test_inactive_search_cannot_authorize_and_missing_preferences_do_not_match_another_profession(
    db, load_service
):
    await seed(db)
    module = load_service("job-match-worker", "src.services.authorization_service")
    payload = {"candidate": {"id": 1, "target_profile_id": 1}, "job": {"id": 1}, "match": {"id": 1}}
    async with db() as session, session.begin():
        await module.authorize(session, payload)
    async with db() as session, session.begin():
        profile = await session.get(CandidateTargetProfile, 1)
        profile.active, profile.automation_authorized = True, True
        session.add(
            ProfessionalEntity(
                id=2,
                entity_type="occupation",
                canonical_name="Nurse",
                normalized_name="nurse",
                language="pt",
            )
        )
        link = await session.scalar(select(JobProfessionalEntity))
        link.entity_id = 2
    async with db() as session, session.begin():
        await module.handle_lifecycle(
            session, {"candidate_id": 1, "event_name": "resume.available"}
        )
    async with db() as session:
        assert (await session.get(ApplicationAuthorization, (1, 1))).status == "waiting"
        assert not (await session.scalars(select(DomainOutbox))).all()
