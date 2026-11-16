"""Real local SQL lifecycle, simulated Stripe notifications; no external effects."""
from datetime import UTC, datetime, timedelta
from sqlalchemy import select, text
from scaffold.models import Candidate, BillingCustomer, BillingPlan, BillingSubscription, BillingPayment
from scaffold.models.domain_delivery import DomainOutbox

async def seed(db):
    async with db() as s, s.begin():
        await s.execute(text("CREATE TABLE IF NOT EXISTS billing_checkout_operations (operation_key VARCHAR(128) PRIMARY KEY, candidate_id INTEGER NOT NULL, plan_code VARCHAR(128) NOT NULL, subscription_id INTEGER, result JSON)"))
        c = Candidate(full_name="Trial local", email="trial@example.invalid")
        s.add(c)
        await s.flush()
        customer = BillingCustomer(candidate_id=c.id, active=True)
        plan = BillingPlan(code="trial-local", name="Local", active=True)
        s.add_all([customer, plan])
        await s.flush()
        sub = BillingSubscription(billing_customer_id=customer.id, billing_plan_id=plan.id, status="incomplete", external_subscription_id="sub_local")
        s.add(sub)
        await s.flush()
        return c.id, sub.id

async def notify(w, deps, cid, when, name, event_id, **kw):
    msg = w.PaymentEventMessage(event_type=name, gateway_event_id=event_id, candidate_id=cid,
        subscription_id="sub_local", occurred_at=when, amount=kw.pop("amount", None), currency="brl", metadata=kw)
    await w._process_event(deps, msg)

async def test_trial_to_first_payment_deduplicates_invoice(db, load_service):
    w = load_service("billing-worker", "src.handlers.billing_event_handler")
    cid, sid = await seed(db)
    deps = w.HandlerDeps(session_factory=db, output_queues={}, max_retries=3)
    start = datetime.now(UTC).replace(microsecond=0)
    await notify(w, deps, cid, start, "subscription.created", "evt_trial", subscription_status="trialing", trial_start=start.isoformat(), trial_end=(start+timedelta(days=7)).isoformat(), livemode=False)
    async with db() as s:
        assert str((await s.get(BillingSubscription, sid)).status) == "trialing"
        trial = await s.scalar(select(DomainOutbox).where(DomainOutbox.destination == "subscription.trial_started"))
        assert trial.payload["data"]["access_active"] is True
    await notify(w, deps, cid, start, "payment.confirmed", "evt_zero", amount=0, financial_id="in_zero", livemode=False)
    async with db() as s:
        assert str((await s.get(BillingSubscription, sid)).status) == "trialing"
    for event_id in ("evt_paid", "evt_succeeded", "evt_paid"):
        await notify(w, deps, cid, start+timedelta(days=7), "payment.confirmed", event_id, amount=49.9, financial_id="in_first", billing_reason="subscription_cycle", livemode=False)
    async with db() as s:
        assert str((await s.get(BillingSubscription, sid)).status) == "active"
        purchases = (await s.scalars(select(DomainOutbox).where(DomainOutbox.destination == "payment.confirmed"))).all()
        assert len(purchases) == 1
        d = purchases[0].payload["data"]
        assert (d["order_id"], d["value"], d["currency"], d["classification"]) == ("in_first",49.9,"BRL","first_purchase")
        assert len((await s.scalars(select(BillingPayment).where(BillingPayment.amount>0))).all()) == 1

async def test_cancel_trial_before_payment(db, load_service):
    w = load_service("billing-worker", "src.handlers.billing_event_handler")
    cid, sid = await seed(db)
    deps = w.HandlerDeps(session_factory=db, output_queues={}, max_retries=3)
    start = datetime.now(UTC).replace(microsecond=0)
    await notify(w, deps, cid, start, "subscription.created", "evt_trial", subscription_status="trialing", livemode=False)
    await notify(w, deps, cid, start+timedelta(days=2), "subscription.cancelled", "evt_cancel", livemode=False)
    async with db() as s:
        assert str((await s.get(BillingSubscription, sid)).status) == "canceled"
        assert not await s.scalar(select(DomainOutbox).where(DomainOutbox.destination=="payment.confirmed"))
        states = (await s.scalars(select(DomainOutbox).where(DomainOutbox.destination=="subscription.state_changed").order_by(DomainOutbox.id))).all()
        assert states[-1].payload["data"]["access_active"] is False
