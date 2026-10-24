from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
from scaffold.ingestion_diagnostics import summarize

NOW = datetime(2026, 10, 24, tzinfo=UTC)


def report(**kwargs):
    defaults = dict(
        profile=NS(id=7, candidate_id=42, active=True, archived_at=None, target_country="BR"),
        now=NOW,
        days=7,
        definitions=[NS(id=1)],
        runs=[],
        eligibilities=[],
        assessments=[],
        matches=[],
    )
    defaults.update(kwargs)
    return summarize(**defaults)


def count(data, key):
    return next(x for x in data["metrics"] if x["key"] == key)


def test_empty_history_is_not_market_empty_and_unknown_is_not_zero():
    r = report()
    assert r["state"] == "search_unconfirmed"
    assert count(r, "sources_checked")["count"] is None
    assert count(r, "notifications_delivered")["count"] is None
    assert count(r, "opportunities")["count"] == 0


def test_latest_assessment_per_job_excludes_other_owners_and_old_protocol_failures():
    base = dict(candidate_id=42, target_profile_id=7, job_id=5)
    r = report(
        assessments=[
            {
                **base,
                "evaluated_at": (NOW - timedelta(hours=2)).isoformat(),
                "status": "provider_failed",
            },
            {
                **base,
                "evaluated_at": (NOW - timedelta(hours=1)).isoformat(),
                "status": "approved",
                "result": {"verdict": "compatible"},
            },
            {
                **base,
                "candidate_id": 99,
                "job_id": 6,
                "evaluated_at": NOW.isoformat(),
                "status": "provider_failed",
            },
        ]
    )
    assert count(r, "professionally_assessed")["count"] == 1
    assert count(r, "assessment_failures")["count"] == 0
    assert not r["reasons"]


def test_provider_failure_is_delayed_not_incompatible_and_does_not_refresh_collection():
    r = report(
        assessments=[
            dict(
                candidate_id=42,
                target_profile_id=7,
                job_id=5,
                evaluated_at=NOW.isoformat(),
                status="provider_failed",
            )
        ]
    )
    assert r["state"] == "processing_delayed"
    assert r["last_collection_success_at"] is None
    assert r["reasons"] == [{"code": "provider_unavailable", "count": 1}]


def test_paused_precedence_and_partial_counts():
    r = report(
        profile=NS(id=7, candidate_id=42, active=False, archived_at=None),
        incomplete=["matches", "coverage"],
    )
    assert r["state"] == "paused"
    assert not count(r, "opportunities")["complete"]
    assert not r["coverage"]["complete"]


def test_future_or_wrong_owner_demand_does_not_claim_coverage_and_activation_is_not_creation():
    r = report(
        discovery=dict(
            candidate_id=99,
            target_profile_id=7,
            checked_at=NOW.isoformat(),
            status="country_unsupported",
        ),
        matches=[NS(created_at=NOW)],
    )
    assert r["coverage"]["discovery_status"] == "unknown"
    assert r["activation"]["first_opportunity_seconds"] is None


def test_first_opportunity_latency_only_when_activation_and_complete_window_prove_it():
    activation = dict(
        candidate_id=42, target_profile_id=7, activated_at=(NOW - timedelta(minutes=5)).isoformat()
    )
    r = report(activation=activation, matches=[NS(created_at=NOW - timedelta(minutes=3))])
    assert r["activation"]["first_opportunity_seconds"] == 120
    assert (
        report(activation=activation, matches=[NS(created_at=NOW)], incomplete=["matches"])[
            "activation"
        ]["first_opportunity_seconds"]
        is None
    )


def test_rejections_count_reasons_not_private_contents():
    r = report(
        eligibilities=[
            (
                NS(
                    status="rejected",
                    updated_at=NOW,
                    routing_reason={"filters": {"country": "rejected", "remote": "pass"}},
                ),
                NOW,
            )
        ]
    )
    assert r["reasons"] == [{"code": "country", "count": 1}]
    assert count(r, "new_catalog_jobs_considered")["count"] == 1


async def test_database_report_scopes_all_stages_and_marks_bounded_samples(monkeypatch):
    import scaffold.ingestion_diagnostics as diagnostics
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from scaffold.base import CoreBase
    from scaffold.models import Job, JobMatch, JobCandidateEligibility, JobCandidatePreference
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.dialects.mysql import ENUM

    @compiles(ENUM, "sqlite")
    def enum_sqlite(type_, compiler, **kw):
        return "VARCHAR(255)"

    from scaffold.models.domain_delivery import DomainProjection
    from scaffold.models.search.job_collection_definitions import JobCollectionDefinition
    from scaffold.models.search.job_collection_runs import JobCollectionRun

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        x.__table__
        for x in (
            Job,
            JobMatch,
            JobCandidateEligibility,
            JobCandidatePreference,
            DomainProjection,
            JobCollectionDefinition,
            JobCollectionRun,
        )
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: CoreBase.metadata.create_all(sync, tables=tables))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        session.add_all(
            [Job(id=1, title="PHP", created_at=NOW), Job(id=2, title="PHP", created_at=NOW)]
        )
        session.add(
            JobMatch(
                id=2,
                candidate_id=42,
                candidate_target_profile_id=7,
                job_id=1,
                score=90,
                created_at=NOW,
            )
        )
        session.add(JobCandidatePreference(candidate_id=99, job_id=1, dismissed=True))
        session.add_all(
            [
                JobCandidateEligibility(
                    id=1,
                    candidate_id=42,
                    candidate_target_profile_id=7,
                    job_id=1,
                    status="eligible",
                    updated_at=NOW,
                ),
                JobCandidateEligibility(
                    id=2,
                    candidate_id=99,
                    candidate_target_profile_id=8,
                    job_id=2,
                    status="eligible",
                    updated_at=NOW,
                ),
            ]
        )
        for index in (1, 2):
            session.add(
                DomainProjection(
                    consumer="matching.professional",
                    aggregate=f"42:7:{index}:key",
                    data=dict(
                        candidate_id=42,
                        target_profile_id=7,
                        job_id=index,
                        evaluated_at=NOW.isoformat(),
                        status="approved",
                        result={"verdict": "compatible"},
                    ),
                )
            )
        session.add(
            DomainProjection(
                consumer="matching.professional",
                aggregate="99:8:1:key",
                data=dict(
                    candidate_id=99,
                    target_profile_id=8,
                    job_id=1,
                    evaluated_at=NOW.isoformat(),
                    status="provider_failed",
                ),
            )
        )
        session.add(
            JobMatch(
                id=1,
                candidate_id=99,
                candidate_target_profile_id=8,
                job_id=2,
                score=90,
                created_at=NOW,
            )
        )
    monkeypatch.setattr(diagnostics, "MAX_ROWS", 1)
    async with factory() as session:
        result = await diagnostics.objective_report(
            session, NS(id=7, candidate_id=42, active=True, archived_at=None, target_country="BR"), now=NOW
        )
    assert count(result, "jobs_considered")["count"] == 1
    assert count(result, "opportunities")["count"] == 1
    assert count(result, "available_opportunities")["count"] == 1
    assert count(result, "assessment_failures")["count"] == 0
    assert not count(result, "professionally_assessed")["complete"]
    assert "assessments" in result["limits"]["partial_stages"]
    async with factory() as session, session.begin():
        session.add(JobCandidatePreference(candidate_id=42, job_id=1, dismissed=True))
    async with factory() as session:
        dismissed_result = await diagnostics.objective_report(
            session, NS(id=7, candidate_id=42, active=True, archived_at=None, target_country="BR"), now=NOW
        )
    assert count(dismissed_result, "opportunities")["count"] == 1
    assert count(dismissed_result, "available_opportunities")["count"] == 0
    await engine.dispose()


def test_historical_opportunities_do_not_claim_current_availability():
    r = report(matches=[NS(created_at=NOW)])
    assert r["state"] == "no_current_opportunities"
    assert count(r, "opportunities")["count"] == 1
    assert count(r, "available_opportunities")["count"] == 0
    assert (
        report(matches=[NS(created_at=NOW)], available_matches=[NS(created_at=NOW)])["state"]
        == "opportunities_available"
    )


def test_fresh_capacity_schedule_is_not_incompatibility():
    r = report(
        capacity=dict(
            candidate_id=42,
            target_profile_id=7,
            updated_at=NOW.timestamp(),
            pending=True,
            next_attempt_at=(NOW + timedelta(minutes=15)).timestamp(),
            deferred_reason="provider_cooldown",
        )
    )
    assert r["state"] == "waiting_capacity"
    assert r["evaluation_schedule"]["next_attempt_at"] == (NOW + timedelta(minutes=15)).isoformat()


def test_country_unspecified_is_explicit_without_fabricating_brazil_and_pause_wins():
    profile = NS(id=7, candidate_id=42, active=True, archived_at=None, target_country=None)
    r = report(profile=profile)
    assert r["state"] == "coverage_limited"
    assert "country_unspecified" in r["reason_codes"]
    assert profile.target_country is None
    profile.active = False
    assert report(profile=profile)["state"] == "paused"
