from datetime import datetime, UTC, timedelta
import pytest
from sqlalchemy import select
from scaffold.models import (
    Candidate,
    CandidateTargetProfile,
    ResumeBuildSession,
    BillingCustomer,
    BillingSubscription,
)
from scaffold.models.domain_delivery import DomainOutbox


def event(name, version=1, **data):
    return {
        "event_id": str(version),
        "event_name": name,
        "candidate_id": 1,
        "aggregate_version": version,
        "data": data,
    }


async def seed_candidate(db):
    async with db() as session, session.begin():
        session.add(Candidate(id=1, full_name="Candidate", email="candidate@example.test"))
        session.add(CandidateTargetProfile(id=1, candidate_id=1, name="Developer", active=False))


async def test_activation_cancellation_and_stale_activation(db, load_service):
    module = load_service("candidate-api", "src.services.lifecycle_service")
    await seed_candidate(db)
    for e in (
        event("subscription.activated", 10, access_active=True),
        event("subscription.cancelled", 20, access_active=False),
        event("subscription.activated", 10, access_active=True),
    ):
        async with db() as session, session.begin():
            await module.handle_subscription(session, e)
    async with db() as session:
        profile = await session.get(CandidateTargetProfile, 1)
        assert profile.active is False and profile.automation_authorized is False
        assert len((await session.scalars(select(DomainOutbox))).all()) == 2


async def test_search_goal_created_after_payment_inherits_access(db, load_service):
    module = load_service("candidate-api", "src.services.lifecycle_service")
    async with db() as session, session.begin():
        session.add(Candidate(id=1, full_name="Candidate"))
    async with db() as session, session.begin():
        await module.handle_subscription(
            session, event("subscription.activated", 1, access_active=True)
        )
    async with db() as session, session.begin():
        profile = CandidateTargetProfile(id=1, candidate_id=1, name="Developer", active=False)
        session.add(profile)
        await module.sync_profile(session, profile)
        assert profile.active is True and profile.automation_authorized is True


async def test_reconciliation_is_dry_run_by_default_and_does_not_emit_purchase_pixels(
    db, load_service
):
    module = load_service("billing-worker", "src.services.reconciliation")
    await seed_candidate(db)
    async with db() as session, session.begin():
        session.add(BillingCustomer(id=1, candidate_id=1))
        session.add(
            BillingSubscription(id=1, billing_customer_id=1, billing_plan_id=1, status="active")
        )
    result = await module.reconcile(db, 1)
    assert result["access_active"] is True and result["payment_confirmed"] is False
    async with db() as session:
        assert not (await session.scalars(select(DomainOutbox))).all()
    await module.reconcile(db, 1, apply=True, operation_key="test")
    await module.reconcile(db, 1, apply=True, operation_key="test")
    async with db() as session:
        events = (await session.scalars(select(DomainOutbox))).all()
        assert {e.destination for e in events} == {
            "subscription.state_changed",
            "billing.access.reconciled",
        }
        assert len(events) == 2


@pytest.mark.parametrize("paid_first", [True, False])
async def test_resume_requires_both_events_in_either_order_and_deduplicates(
    db, load_service, paid_first
):
    module = load_service("resume-api", "src.services.lifecycle_service")
    await seed_candidate(db)
    paid, complete = event("payment.confirmed"), event("resume.builder.completed", 2)

    async def finish_builder():
        async with db() as session, session.begin():
            session.add(
                ResumeBuildSession(
                    id=5,
                    candidate_id=1,
                    session_type="builder",
                    status="completed",
                    completed_at=datetime.now(UTC),
                    session_metadata={"workflow_key": "builder"},
                )
            )

    if not paid_first:
        await finish_builder()
    async with db() as session, session.begin():
        await module.handle_lifecycle(session, paid if paid_first else complete)
        assert (await session.scalars(select(DomainOutbox))).all() == []
    if paid_first:
        await finish_builder()
    async with db() as session, session.begin():
        await module.handle_lifecycle(session, complete if paid_first else paid)
        await module.handle_lifecycle(session, paid)
        await module.handle_lifecycle(session, complete)
    async with db() as session:
        requests = (await session.scalars(select(DomainOutbox))).all()
        assert len(requests) == 1
        assert requests[0].destination == "resume.generate"


async def test_payment_persists_events_and_duplicate_or_old_webhook_cannot_reactivate(
    db, load_service
):
    module = load_service("billing-worker", "src.handlers.billing_event_handler")
    from src.models.billing_checkout_operations import operations

    async with db().bind.begin() as connection:
        await connection.run_sync(operations.create)
    await seed_candidate(db)
    async with db() as session, session.begin():
        session.add(BillingCustomer(id=1, candidate_id=1))
        session.add(
            BillingSubscription(
                id=1,
                billing_customer_id=1,
                billing_plan_id=1,
                status="incomplete",
                external_subscription_id="sub1",
            )
        )
    deps = module.HandlerDeps(session_factory=db, output_queues={}, max_retries=3)
    now = datetime.now(UTC)

    def msg(name, key, when):
        return module.PaymentEventMessage(
            event_type=name,
            gateway_event_id=key,
            candidate_id=1,
            subscription_id="sub1",
            amount=10,
            currency="BRL",
            occurred_at=when,
        )

    await module._process_event(deps, msg("payment.confirmed", "p1", now))
    await module._process_event(deps, msg("payment.confirmed", "p1", now))
    await module._process_event(
        deps, msg("subscription.cancelled", "c1", now + timedelta(seconds=2))
    )
    await module._process_event(deps, msg("payment.confirmed", "p2", now + timedelta(seconds=1)))
    async with db() as session:
        assert str((await session.get(BillingSubscription, 1)).status) == "canceled"
        events = (await session.scalars(select(DomainOutbox))).all()
        assert sum(e.destination == "subscription.activated" for e in events) == 1
        assert sum(e.destination == "subscription.cancelled" for e in events) == 1
