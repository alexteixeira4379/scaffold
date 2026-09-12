from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.billing.billing_customers import BillingCustomer
from scaffold.models.billing.billing_events import BillingEvent
from scaffold.models.billing.billing_payments import BillingPayment
from scaffold.models.billing.billing_plans import BillingPlan
from scaffold.models.billing.billing_subscriptions import BillingSubscription
from scaffold.models.billing.billing_workflow_answers import BillingWorkflowAnswer
from scaffold.models.billing.billing_workflow_sessions import BillingWorkflowSession
from scaffold.models.billing.billing_workflow_steps import BillingWorkflowStep

from scaffold.constants.schema_enums import WorkflowSessionStatus
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


class BillingWorkflowSessionRepository(AsyncRepository[BillingWorkflowSession]):
    def __init__(self) -> None:
        super().__init__(BillingWorkflowSession)

    async def get_active_by_candidate_and_workflow(
        self, session: AsyncSession, candidate_id: int, workflow_key: str
    ) -> BillingWorkflowSession | None:
        return await self.first_where(
            session,
            BillingWorkflowSession.candidate_id == candidate_id,
            BillingWorkflowSession.workflow_key == workflow_key,
            BillingWorkflowSession.status.in_(
                (WorkflowSessionStatus.STARTED, WorkflowSessionStatus.IN_PROGRESS, WorkflowSessionStatus.PAUSED)
            ),
        )

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        workflow_key: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BillingWorkflowSession]:
        criteria = [BillingWorkflowSession.candidate_id == candidate_id]
        if workflow_key is not None:
            criteria.append(BillingWorkflowSession.workflow_key == workflow_key)
        return await self.list_where(
            session,
            *criteria,
            order_by=(BillingWorkflowSession.id.desc(),),
            limit=limit,
            offset=offset,
        )


class BillingWorkflowStepRepository(AsyncRepository[BillingWorkflowStep]):
    def __init__(self) -> None:
        super().__init__(BillingWorkflowStep)

    async def get_by_workflow_and_step_key(
        self, session: AsyncSession, workflow_key: str, step_key: str
    ) -> BillingWorkflowStep | None:
        return await self.first_where(
            session,
            BillingWorkflowStep.workflow_key == workflow_key,
            BillingWorkflowStep.step_key == step_key,
        )

    async def list_active_by_workflow_key(
        self,
        session: AsyncSession,
        workflow_key: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BillingWorkflowStep]:
        return await self.list_where(
            session,
            BillingWorkflowStep.workflow_key == workflow_key,
            BillingWorkflowStep.active.is_(True),
            order_by=(BillingWorkflowStep.step_order, BillingWorkflowStep.id),
            limit=limit,
            offset=offset,
        )


class BillingWorkflowAnswerRepository(AsyncRepository[BillingWorkflowAnswer]):
    def __init__(self) -> None:
        super().__init__(BillingWorkflowAnswer)

    async def get_by_session_and_step(
        self,
        session: AsyncSession,
        session_id: int,
        step_id: int,
        repeat_index: int | None = None,
    ) -> BillingWorkflowAnswer | None:
        return await self.first_where(
            session,
            BillingWorkflowAnswer.session_id == session_id,
            BillingWorkflowAnswer.step_id == step_id,
            BillingWorkflowAnswer.repeat_index == repeat_index,
        )

    async def list_by_session_id(
        self,
        session: AsyncSession,
        session_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BillingWorkflowAnswer]:
        return await self.list_where(
            session,
            BillingWorkflowAnswer.session_id == session_id,
            order_by=(BillingWorkflowAnswer.id,),
            limit=limit,
            offset=offset,
        )


billing_workflow_session_repository = BillingWorkflowSessionRepository()
billing_workflow_step_repository = BillingWorkflowStepRepository()
billing_workflow_answer_repository = BillingWorkflowAnswerRepository()
