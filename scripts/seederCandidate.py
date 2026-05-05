from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

importlib.import_module("scaffold.models")

from scaffold.constants.schema_enums import (
    ApplyMode,
    BillingPaymentStatus,
    BillingSubscriptionStatus,
    CandidateStatus,
    EmploymentType,
    ExperienceLevel,
    JobApplicationStatus,
    JobMatchStatus,
    JobStatus,
    LanguagePreference,
    RemoteType,
    ResumeDocumentFormat,
)
from scaffold.db.session import close_engine, get_session_factory
from scaffold.models.billing.billing_customers import BillingCustomer
from scaffold.models.billing.billing_payments import BillingPayment
from scaffold.models.billing.billing_plans import BillingPlan
from scaffold.models.billing.billing_subscriptions import BillingSubscription
from scaffold.models.candidate.candidate_preferences import CandidatePreference
from scaffold.models.candidate.candidate_target_profile_keywords import CandidateTargetProfileKeyword
from scaffold.models.candidate.candidate_target_profiles import CandidateTargetProfile
from scaffold.models.candidate.candidates import Candidate
from scaffold.models.job.job_applications import JobApplication
from scaffold.models.job.job_candidate_eligibilities import JobCandidateEligibility
from scaffold.models.job.job_matches import JobMatch
from scaffold.models.job.jobs import Job
from scaffold.models.resume.resume_versions import ResumeVersion

DEFAULT_SEED_EMAIL = "candidate.seed@example.test"
DEFAULT_BILLING_PLAN_CODE = "candidate_seed_monthly"
SEED_PROFILE_NAME = "Backend BR Seed"
SEED_JOB_CANONICAL_URL = "https://example.test/jobs/seed-backend-br-engineer"


def seed_url_hash() -> str:
    return hashlib.sha256(SEED_JOB_CANONICAL_URL.encode()).hexdigest()


async def get_or_create_billing_plan(session, code: str) -> BillingPlan:
    row = (
        await session.execute(select(BillingPlan).where(BillingPlan.code == code).limit(1))
    ).scalars().first()
    if row is not None:
        return row
    plan = BillingPlan(
        code=code,
        name="Seed Monthly",
        description="Plano mensal fixture candidato seed",
        price=99.0,
        currency="BRL",
        interval="month",
        interval_count=1,
        features={},
        active=True,
    )
    session.add(plan)
    await session.flush()
    return plan


async def get_or_create_candidate(session, email: str) -> Candidate:
    result = (
        await session.execute(
            select(Candidate)
            .where(func.lower(Candidate.email) == email.lower())
            .limit(1)
        )
    ).scalars().first()
    if result is not None:
        return result
    c = Candidate(
        full_name="Candidato Seed Dev",
        email=email.lower(),
        phone="+5511999998888",
        country="BR",
        location="São Paulo, SP",
        linkedin_url="https://linkedin.com/in/candidate-seed-dev",
        language_preference=LanguagePreference.PT_BR,
        status=CandidateStatus.ACTIVE,
        generated_token="seed-candidate-token-dev",
        track_code="seed-track",
    )
    session.add(c)
    await session.flush()
    return c


async def ensure_candidate_preference(session, candidate_id: int) -> None:
    row = (
        await session.execute(
            select(CandidatePreference).where(
                CandidatePreference.candidate_id == candidate_id
            ).limit(1)
        )
    ).scalars().first()
    if row is not None:
        return
    session.add(
        CandidatePreference(
            candidate_id=candidate_id,
            target_country="BR",
            target_location="Brasil, remoto",
            remote_preference=RemoteType.REMOTE,
            employment_preference=EmploymentType.FULL_TIME,
            experience_level=ExperienceLevel.MID_SENIOR,
            min_salary=12000.0,
            currency="BRL",
            notes=None,
        )
    )


async def get_or_create_target_profile(session, candidate_id: int) -> CandidateTargetProfile:
    row = (
        await session.execute(
            select(CandidateTargetProfile).where(
                CandidateTargetProfile.candidate_id == candidate_id,
                CandidateTargetProfile.name == SEED_PROFILE_NAME,
            ).limit(1)
        )
    ).scalars().first()
    if row is not None:
        return row
    tp = CandidateTargetProfile(
        candidate_id=candidate_id,
        name=SEED_PROFILE_NAME,
        target_country="BR",
        target_location="Brasil, remoto",
        remote_preference=RemoteType.REMOTE,
        employment_preference=EmploymentType.FULL_TIME,
        experience_level=ExperienceLevel.MID_SENIOR,
        min_salary=12000.0,
        currency="BRL",
        is_default=True,
        active=True,
    )
    session.add(tp)
    await session.flush()
    return tp


async def ensure_keywords(session, profile_id: int) -> None:
    specs: list[tuple[str, str]] = [
        ("python", "include"),
        ("backend", "include"),
        ("java", "exclude"),
    ]
    for keyword, policy in specs:
        exists = (
            await session.execute(
                select(CandidateTargetProfileKeyword.id).where(
                    CandidateTargetProfileKeyword.candidate_target_profile_id == profile_id,
                    CandidateTargetProfileKeyword.keyword == keyword,
                    CandidateTargetProfileKeyword.match_policy == policy,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        session.add(
            CandidateTargetProfileKeyword(
                candidate_target_profile_id=profile_id,
                keyword=keyword,
                match_policy=policy,
                weight=1.0,
                active=True,
            )
        )


async def get_or_create_job(session, url_hash: str) -> Job:
    row = (
        await session.execute(select(Job).where(Job.url_hash == url_hash).limit(1))
    ).scalars().first()
    if row is not None:
        return row
    now = datetime.now(timezone.utc)
    job = Job(
        company_id=None,
        ats_provider_id=None,
        external_job_id=None,
        canonical_url=SEED_JOB_CANONICAL_URL,
        url_hash=url_hash,
        source_label="seed",
        title="Engenheiro de Software Backend (Seed)",
        description="Vaga fixture para testes de aplicação.",
        location="Brasil",
        country="BR",
        state=None,
        city=None,
        remote_type=RemoteType.REMOTE,
        employment_type=EmploymentType.FULL_TIME,
        experience_level=ExperienceLevel.MID_SENIOR,
        salary_min=10000.0,
        salary_max=18000.0,
        currency="BRL",
        posted_at=now,
        status=JobStatus.ACTIVE,
        first_seen_at=now,
        last_seen_at=now,
        company_name_snapshot="Example Corp Seed",
        company_domain_snapshot="example.test",
    )
    session.add(job)
    await session.flush()
    return job


async def get_or_create_billing_customer(session, candidate: Candidate) -> BillingCustomer:
    row = (
        await session.execute(
            select(BillingCustomer).where(
                BillingCustomer.candidate_id == candidate.id
            ).limit(1)
        )
    ).scalars().first()
    if row is not None:
        return row
    bc = BillingCustomer(
        candidate_id=candidate.id,
        external_customer_id=f"cus_seed_{candidate.id}",
        email=candidate.email,
        name=candidate.full_name,
        active=True,
    )
    session.add(bc)
    await session.flush()
    return bc


async def get_or_create_subscription(
    session,
    billing_customer_id: int,
    billing_plan_id: int,
) -> BillingSubscription:
    row = (
        await session.execute(
            select(BillingSubscription).where(
                BillingSubscription.billing_customer_id == billing_customer_id,
                BillingSubscription.billing_plan_id == billing_plan_id,
            ).limit(1)
        )
    ).scalars().first()
    if row is not None:
        return row
    now = datetime.now(timezone.utc)
    sub = BillingSubscription(
        billing_customer_id=billing_customer_id,
        billing_plan_id=billing_plan_id,
        external_subscription_id="sub_seed_fixture",
        status=BillingSubscriptionStatus.ACTIVE,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        cancel_at=None,
        canceled_at=None,
    )
    session.add(sub)
    await session.flush()
    return sub


async def ensure_succeeded_payment(
    session,
    billing_customer_id: int,
    billing_subscription_id: int,
) -> None:
    pay = (
        await session.execute(
            select(BillingPayment)
            .where(
                BillingPayment.billing_subscription_id == billing_subscription_id,
                BillingPayment.status == BillingPaymentStatus.SUCCEEDED,
            )
            .limit(1)
        )
    ).scalars().first()
    if pay is not None:
        return
    now = datetime.now(timezone.utc)
    session.add(
        BillingPayment(
            billing_customer_id=billing_customer_id,
            billing_subscription_id=billing_subscription_id,
            external_payment_id="pay_seed_fixture",
            amount=99.0,
            currency="BRL",
            status=BillingPaymentStatus.SUCCEEDED,
            paid_at=now,
            failure_reason=None,
            payment_metadata={},
        )
    )


async def ensure_eligibility(
    session,
    job_id: int,
    candidate_id: int,
    profile_id: int,
) -> None:
    row = (
        await session.execute(
            select(JobCandidateEligibility).where(
                JobCandidateEligibility.job_id == job_id,
                JobCandidateEligibility.candidate_id == candidate_id,
                JobCandidateEligibility.candidate_target_profile_id == profile_id,
            ).limit(1)
        )
    ).scalars().first()
    if row is not None:
        return
    session.add(
        JobCandidateEligibility(
            job_id=job_id,
            candidate_id=candidate_id,
            candidate_target_profile_id=profile_id,
            status="eligible",
            routing_score=87.50,
            routing_reason={"source": "seed"},
        )
    )


async def get_or_create_job_match(
    session,
    candidate_id: int,
    job_id: int,
    profile_id: int,
) -> JobMatch:
    row = (
        await session.execute(
            select(JobMatch).where(
                JobMatch.candidate_id == candidate_id,
                JobMatch.job_id == job_id,
                JobMatch.candidate_target_profile_id == profile_id,
            ).limit(1)
        )
    ).scalars().first()
    if row is not None:
        return row
    now = datetime.now(timezone.utc)
    jm = JobMatch(
        candidate_id=candidate_id,
        job_id=job_id,
        candidate_target_profile_id=profile_id,
        score=89.75,
        status=JobMatchStatus.RECOMMENDED,
        matched_at=now,
    )
    session.add(jm)
    await session.flush()
    return jm


async def ensure_job_application(session, job_match_id: int) -> None:
    row = (
        await session.execute(
            select(JobApplication).where(
                JobApplication.job_match_id == job_match_id
            ).limit(1)
        )
    ).scalars().first()
    if row is not None:
        return
    session.add(
        JobApplication(
            job_match_id=job_match_id,
            status=JobApplicationStatus.READY,
            apply_mode=ApplyMode.AUTO,
            easy_apply=False,
            prepared=True,
            submitted_at=None,
            application_url_snapshot=SEED_JOB_CANONICAL_URL,
            job_title_snapshot="Engenheiro de Software Backend (Seed)",
            company_name_snapshot="Example Corp Seed",
        )
    )


async def ensure_current_resume(session, candidate_id: int) -> None:
    row = (
        await session.execute(
            select(ResumeVersion).where(
                ResumeVersion.candidate_id == candidate_id,
                ResumeVersion.is_current.is_(True),
            ).limit(1)
        )
    ).scalars().first()
    if row is not None:
        return
    session.add(
        ResumeVersion(
            candidate_id=candidate_id,
            session_id=None,
            version_number=1,
            format=ResumeDocumentFormat.PDF,
            content="Candidato Seed Dev — experiência backend Python.",
            storage_url=None,
            is_current=True,
        )
    )


async def run_seed(email: str, billing_plan_code: str) -> None:
    url_hash_value = seed_url_hash()
    try:
        factory = get_session_factory()
        async with factory() as session:
            plan = await get_or_create_billing_plan(session, billing_plan_code)
            candidate = await get_or_create_candidate(session, email)
            await ensure_candidate_preference(session, candidate.id)
            profile = await get_or_create_target_profile(session, candidate.id)
            await ensure_keywords(session, profile.id)
            job = await get_or_create_job(session, url_hash_value)
            customer = await get_or_create_billing_customer(session, candidate)
            sub = await get_or_create_subscription(session, customer.id, plan.id)
            await ensure_succeeded_payment(session, customer.id, sub.id)
            await ensure_eligibility(session, job.id, candidate.id, profile.id)
            match = await get_or_create_job_match(session, candidate.id, job.id, profile.id)
            await ensure_job_application(session, match.id)
            await ensure_current_resume(session, candidate.id)
            await session.commit()
    finally:
        await close_engine()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--email",
        default=DEFAULT_SEED_EMAIL,
        help="Email fixo do candidato seed para idempotência",
    )
    p.add_argument(
        "--billing-plan-code",
        default=DEFAULT_BILLING_PLAN_CODE,
        dest="billing_plan_code",
    )
    args = p.parse_args()
    asyncio.run(run_seed(args.email, args.billing_plan_code))


if __name__ == "__main__":
    main()
