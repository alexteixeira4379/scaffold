from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.billing.billing_customers import BillingCustomer
from scaffold.models.billing.billing_events import BillingEvent
from scaffold.models.billing.billing_payments import BillingPayment
from scaffold.models.billing.billing_plans import BillingPlan
from scaffold.models.billing.billing_subscriptions import BillingSubscription

from scaffold.repositories.base import AsyncRepository


class BillingPlanRepository(AsyncRepository[BillingPlan]):
    def __init__(self) -> None:
        super().__init__(BillingPlan)

    async def get_by_code(self, session: AsyncSession, code: str) -> BillingPlan | None:
        return await self.first_where(session, BillingPlan.code == code)


class BillingCustomerRepository(AsyncRepository[BillingCustomer]):
    def __init__(self) -> None:
        super().__init__(BillingCustomer)

    async def get_by_candidate_id(self, session: AsyncSession, candidate_id: int) -> BillingCustomer | None:
        return await self.first_where(session, BillingCustomer.candidate_id == candidate_id)

    async def get_by_external_customer_id(
        self, session: AsyncSession, external_customer_id: str
    ) -> BillingCustomer | None:
        return await self.first_where(
            session, BillingCustomer.external_customer_id == external_customer_id
        )


class BillingSubscriptionRepository(AsyncRepository[BillingSubscription]):
    def __init__(self) -> None:
        super().__init__(BillingSubscription)

    async def list_by_billing_customer_id(
        self,
        session: AsyncSession,
        billing_customer_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BillingSubscription]:
        return await self.list_where(
            session,
            BillingSubscription.billing_customer_id == billing_customer_id,
            order_by=(BillingSubscription.id.desc(),),
            limit=limit,
            offset=offset,
        )


class BillingPaymentRepository(AsyncRepository[BillingPayment]):
    def __init__(self) -> None:
        super().__init__(BillingPayment)

    async def list_by_billing_customer_id(
        self,
        session: AsyncSession,
        billing_customer_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BillingPayment]:
        return await self.list_where(
            session,
            BillingPayment.billing_customer_id == billing_customer_id,
            order_by=(BillingPayment.id.desc(),),
            limit=limit,
            offset=offset,
        )


class BillingEventRepository(AsyncRepository[BillingEvent]):
    def __init__(self) -> None:
        super().__init__(BillingEvent)

    async def list_by_billing_customer_id(
        self,
        session: AsyncSession,
        billing_customer_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BillingEvent]:
        return await self.list_where(
            session,
            BillingEvent.billing_customer_id == billing_customer_id,
            order_by=(BillingEvent.id.desc(),),
            limit=limit,
            offset=offset,
        )


billing_plan_repository = BillingPlanRepository()
billing_customer_repository = BillingCustomerRepository()
billing_subscription_repository = BillingSubscriptionRepository()
billing_payment_repository = BillingPaymentRepository()
billing_event_repository = BillingEventRepository()
