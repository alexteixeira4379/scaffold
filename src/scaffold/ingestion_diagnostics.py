"""Read-only objective funnel. Counts describe persisted evidence, never market supply.

Version 1 deliberately leaves collection/source attribution and notification delivery
unknown when no per-objective evidence exists. Bounded samples are labelled partial.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
import json

from sqlalchemy import String, case, exists, literal, select
from scaffold.models import JobCandidateEligibility, JobMatch, Job, JobCandidatePreference
from scaffold.models.domain_delivery import DomainProjection
from scaffold.models.search.job_collection_definitions import JobCollectionDefinition
from scaffold.models.search.job_collection_runs import JobCollectionRun

MAX_ROWS = 2000


def utc(value):
    if not value:
        return None
    if isinstance(value, (float, int)):
        try:
            value = datetime.fromtimestamp(value, UTC)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def stamp(value):
    value = utc(value)
    return value.isoformat() if value else None


def mapping(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def metric(key, count, complete=True, scope="objective", reason=None):
    return {
        "key": key,
        "count": count,
        "complete": complete,
        "scope": scope,
        "unavailable_reason": reason,
    }


def summarize(
    profile,
    *,
    now,
    days,
    definitions,
    runs,
    eligibilities,
    assessments,
    matches,
    available_matches=(),
    discovery=None,
    activation=None,
    capacity=None,
    incomplete=(),
):
    cutoff = now - timedelta(days=days)
    latest = {}
    for row in assessments:
        if (
            row.get("candidate_id") != profile.candidate_id
            or row.get("target_profile_id") != profile.id
        ):
            continue
        when = utc(row.get("evaluated_at"))
        if not when or not cutoff <= when <= now:
            continue
        job = row.get("job_id")
        if job is not None and (job not in latest or when > utc(latest[job]["evaluated_at"])):
            latest[job] = row
    failures = sum(
        x.get("status") in {"provider_failed", "rejected_protocol"} for x in latest.values()
    )
    assessed = sum(bool(x.get("result")) for x in latest.values())
    reasons = Counter()
    for row, _ in eligibilities:
        if row.status == "rejected":
            filters = mapping(mapping(row.routing_reason).get("filters"))
            reasons.update(k for k, v in filters.items() if v in {"rejected", "invalid"})
    reasons.update(
        "professional_incompatible"
        for x in latest.values()
        if mapping(x.get("result")).get("verdict") == "incompatible"
    )
    reasons.update(
        "insufficient_evidence"
        for x in latest.values()
        if mapping(x.get("result")).get("verdict") == "insufficient_evidence"
    )
    reasons.update(
        "provider_unavailable" for x in latest.values() if x.get("status") == "provider_failed"
    )
    reasons.update(
        "assessment_format_error" for x in latest.values() if x.get("status") == "rejected_protocol"
    )
    successful = [utc(r.finished_at or r.started_at) for r in runs if str(r.status) == "completed"]
    last_search = max((x for x in successful if x), default=None)
    last_attempt = max((utc(r.started_at) for r in runs if r.started_at), default=None)
    last_match = max((utc(m.created_at) for m in matches), default=None)
    last_eligibility = max((utc(e.updated_at) for e, _ in eligibilities), default=None)
    discovery = mapping(discovery)
    if (
        discovery.get("candidate_id") != profile.candidate_id
        or discovery.get("target_profile_id") != profile.id
    ):
        discovery = {}
    discovery_checked = utc(discovery.get("checked_at"))
    discovery_fresh = bool(
        discovery_checked and now - timedelta(hours=24) <= discovery_checked <= now
    )
    activation = mapping(activation)
    if (
        activation.get("candidate_id") != profile.candidate_id
        or activation.get("target_profile_id") != profile.id
    ):
        activation = {}
    activated_at = utc(activation.get("activated_at"))
    first_match = min(
        (utc(m.created_at) for m in matches if activated_at and utc(m.created_at) >= activated_at),
        default=None,
    )
    # A bounded window cannot prove the first ever result after an older activation.
    latency = (
        (first_match - activated_at).total_seconds()
        if (activated_at and activated_at >= cutoff and first_match and "matches" not in incomplete)
        else None
    )
    capacity = mapping(capacity)
    capacity_updated = utc(capacity.get("updated_at"))
    if (
        capacity.get("candidate_id") != profile.candidate_id
        or capacity.get("target_profile_id") != profile.id
        or not capacity_updated
        or not now - timedelta(hours=24) <= capacity_updated <= now
    ):
        capacity = {}
    next_evaluation = utc(capacity.get("next_attempt_at"))
    codes = []
    if getattr(profile, "archived_at", None):
        state = "archived"
    elif not profile.active:
        state = "paused"
    elif not (getattr(profile, "target_country", None) or "").strip():
        state = "coverage_limited"
        codes.append("country_unspecified")
    elif discovery_fresh and discovery.get("status") in {
        "country_unsupported",
        "country_unspecified",
        "definition_scope_mismatch",
    }:
        state = "coverage_limited"
        codes.append(discovery["status"])
    elif capacity.get("pending") and next_evaluation and next_evaluation > now:
        state = "waiting_capacity"
        codes.append("evaluation_scheduled")
    elif failures:
        state = "processing_delayed"
        codes.append("assessment_failures")
    elif not definitions and "coverage" not in incomplete:
        state = "awaiting_coverage"
        codes.append("missing_collection_coverage")
    elif available_matches:
        state = "opportunities_available"
    elif matches:
        state = "no_current_opportunities"
    elif eligibilities:
        state = (
            "evaluating"
            if any(e.status == "eligible" for e, _ in eligibilities) and not assessed
            else "no_matches_in_window"
        )
    elif last_search is None or last_search < now - timedelta(hours=24):
        state = "search_unconfirmed"
    else:
        state = "awaiting_candidates"
    if last_search is None or last_search < now - timedelta(hours=24):
        codes.append("no_recent_associated_collection_success")
    if incomplete:
        codes.append("partial_metrics")
    return {
        "version": 1,
        "target_profile_id": profile.id,
        "candidate_id": profile.candidate_id,
        "checked_at": stamp(now),
        "window_start": stamp(cutoff),
        "window_days": days,
        "state": state,
        "reason_codes": codes,
        "last_collection_success_at": stamp(last_search),
        "last_collection_attempt_at": stamp(last_attempt),
        "last_eligibility_at": stamp(last_eligibility),
        "last_match_at": stamp(last_match),
        "evaluation_schedule": {
            "next_attempt_at": stamp(next_evaluation),
            "reason": capacity.get("deferred_reason"),
            "observed_at": stamp(capacity_updated) if capacity else None,
        },
        "activation": {
            "activated_at": stamp(activated_at),
            "catalog_completed_at": activation.get("catalog_completed_at"),
            "first_opportunity_seconds": latency,
        },
        "coverage": {
            "definition_ids": [d.id for d in definitions],
            "complete": "coverage" not in incomplete,
            "discovery_status": discovery.get("status") if discovery_fresh else "unknown",
            "discovery_checked_at": stamp(discovery_checked),
            "last_source_search_success_at": stamp(discovery.get("last_search_success_at"))
            if discovery_fresh
            else None,
        },
        "metrics": [
            metric(
                "sources_checked", None, False, reason="source_to_objective_attribution_unavailable"
            ),
            metric(
                "publications_found",
                sum(r.jobs_found_count or 0 for r in runs),
                "collection_runs" not in incomplete and "coverage" not in incomplete,
                "associated_shared_collections",
            ),
            metric(
                "new_catalog_jobs_considered",
                sum(utc(created) >= cutoff for _, created in eligibilities if created),
                "eligibilities" not in incomplete,
            ),
            metric("jobs_considered", len(eligibilities), "eligibilities" not in incomplete),
            metric(
                "eligible_jobs",
                sum(e.status == "eligible" for e, _ in eligibilities),
                "eligibilities" not in incomplete,
            ),
            metric("professionally_assessed", assessed, "assessments" not in incomplete),
            metric("assessment_failures", failures, "assessments" not in incomplete),
            metric("opportunities", len(matches), "matches" not in incomplete),
            metric(
                "available_opportunities",
                len(available_matches),
                "available_matches" not in incomplete,
            ),
            metric(
                "notifications_delivered", None, False, reason="notification_receipt_not_measured"
            ),
        ],
        "reasons": [{"code": k, "count": v} for k, v in sorted(reasons.items())],
        "limits": {
            "rows_per_stage": MAX_ROWS,
            "partial_stages": sorted(incomplete),
            "counts_basis": "latest_persisted_state_in_window",
            "publications_are_unique_jobs": False,
        },
    }


async def objective_report(session, profile, days=7, now=None):
    if not 1 <= days <= 30:
        raise ValueError("days must be between 1 and 30")
    now = utc(now or datetime.now(UTC))
    cutoff = (now - timedelta(days=days)).replace(tzinfo=None)
    incomplete = []

    async def bounded(statement, name, scalars=True):
        result = await session.execute(statement.limit(MAX_ROWS + 1))
        rows = list(result.scalars().all() if scalars else result.all())
        if len(rows) > MAX_ROWS:
            incomplete.append(name)
        return rows[:MAX_ROWS]

    definitions = await bounded(
        select(JobCollectionDefinition)
        .where(JobCollectionDefinition.active.is_(True))
        .order_by(JobCollectionDefinition.id),
        "coverage",
    )
    definitions = [
        d
        for d in definitions
        if profile.id in mapping(d.search_filters).get("demand_profile_ids", [])
    ]
    runs = (
        await bounded(
            select(JobCollectionRun)
            .where(
                JobCollectionRun.job_collection_definition_id.in_([d.id for d in definitions]),
                JobCollectionRun.started_at >= cutoff,
            )
            .order_by(JobCollectionRun.started_at.desc()),
            "collection_runs",
        )
        if definitions
        else []
    )
    eligibility = await bounded(
        select(JobCandidateEligibility, Job.created_at)
        .join(Job, Job.id == JobCandidateEligibility.job_id)
        .where(
            JobCandidateEligibility.candidate_id == profile.candidate_id,
            JobCandidateEligibility.candidate_target_profile_id == profile.id,
            JobCandidateEligibility.updated_at >= cutoff,
        )
        .order_by(JobCandidateEligibility.updated_at.desc()),
        "eligibilities",
        False,
    )
    assessments = await bounded(
        select(DomainProjection)
        .where(
            DomainProjection.consumer == "matching.professional",
            DomainProjection.aggregate.like(f"{profile.candidate_id}:{profile.id}:%"),
            DomainProjection.data["evaluated_at"].as_string() >= cutoff.isoformat(),
        )
        .order_by(DomainProjection.aggregate),
        "assessments",
    )
    matches = await bounded(
        select(JobMatch)
        .where(
            JobMatch.candidate_id == profile.candidate_id,
            JobMatch.candidate_target_profile_id == profile.id,
            JobMatch.created_at >= cutoff,
        )
        .order_by(JobMatch.created_at.desc()),
        "matches",
    )
    channel = case((Job.source_label == "linkedin", "linkedin"), else_="ats")
    restricted = exists(
        select(DomainProjection.aggregate)
        .where(
            DomainProjection.consumer == "job.availability",
            DomainProjection.aggregate.in_(
                [
                    literal("job:") + Job.id.cast(String) + literal(":all"),
                    literal("job:") + Job.id.cast(String) + literal(":") + channel,
                ]
            ),
        )
        .correlate(Job)
    )
    dismissed = exists(
        select(JobCandidatePreference.job_id)
        .where(
            JobCandidatePreference.candidate_id == profile.candidate_id,
            JobCandidatePreference.job_id == Job.id,
            JobCandidatePreference.dismissed.is_(True),
        )
        .correlate(Job)
    )
    available = await bounded(
        select(JobMatch)
        .join(Job, Job.id == JobMatch.job_id)
        .where(
            JobMatch.candidate_id == profile.candidate_id,
            JobMatch.candidate_target_profile_id == profile.id,
            JobMatch.created_at >= cutoff,
            JobMatch.status.not_in(["dismissed", "expired", "converted", "stale"]),
            Job.status == "active",
            ~restricted,
            ~dismissed,
        )
        .order_by(JobMatch.created_at.desc()),
        "available_matches",
    )
    discovery = await session.get(
        DomainProjection, ("ats.discovery.demand", f"target:{profile.id}")
    )
    activation = await session.get(
        DomainProjection, ("ingestion.activation", f"target:{profile.id}")
    )
    capacity = await session.get(
        DomainProjection, ("matching.professional.capacity.target", f"target:{profile.id}")
    )
    return summarize(
        profile,
        now=now,
        days=days,
        definitions=definitions,
        runs=runs,
        eligibilities=eligibility,
        assessments=[r.data for r in assessments],
        matches=matches,
        discovery=discovery.data if discovery else None,
        activation=activation.data if activation else None,
        capacity=capacity.data if capacity else None,
        available_matches=available,
        incomplete=incomplete,
    )
