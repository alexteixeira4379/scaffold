from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.constants.schema_enums import OrchestratorStepStatus
from scaffold.models.onboard.onboard_flow_steps import OnboardFlowStep
from scaffold.models.onboard.onboard_flows import OnboardFlow
from scaffold.models.onboard.profile_onboard_flows import ProfileOnboardFlow
from scaffold.models.onboard.profile_onboard_step_states import ProfileOnboardStepState
from scaffold.repositories.base import AsyncRepository


class OnboardFlowRepository(AsyncRepository[OnboardFlow]):
    def __init__(self) -> None:
        super().__init__(OnboardFlow)

    async def get_active_by_flow_key(self, session: AsyncSession, flow_key: str) -> OnboardFlow | None:
        return await self.first_where(
            session,
            OnboardFlow.flow_key == flow_key,
            OnboardFlow.active.is_(True),
        )


class OnboardFlowStepRepository(AsyncRepository[OnboardFlowStep]):
    def __init__(self) -> None:
        super().__init__(OnboardFlowStep)

    async def list_active_by_flow_id(
        self,
        session: AsyncSession,
        flow_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[OnboardFlowStep]:
        return await self.list_where(
            session,
            OnboardFlowStep.flow_id == flow_id,
            OnboardFlowStep.active.is_(True),
            order_by=(OnboardFlowStep.step_order, OnboardFlowStep.id),
            limit=limit,
            offset=offset,
        )

    async def get_by_flow_and_step_key(
        self, session: AsyncSession, flow_id: int, step_key: str
    ) -> OnboardFlowStep | None:
        return await self.first_where(
            session,
            OnboardFlowStep.flow_id == flow_id,
            OnboardFlowStep.step_key == step_key,
        )


class ProfileOnboardFlowRepository(AsyncRepository[ProfileOnboardFlow]):
    def __init__(self) -> None:
        super().__init__(ProfileOnboardFlow)

    async def get_by_profile_id(self, session: AsyncSession, profile_id: str) -> ProfileOnboardFlow | None:
        return await self.first_where(
            session,
            ProfileOnboardFlow.profile_id == profile_id,
        )

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfileOnboardFlow]:
        return await self.list_where(
            session,
            ProfileOnboardFlow.candidate_id == candidate_id,
            order_by=(ProfileOnboardFlow.id.desc(),),
            limit=limit,
            offset=offset,
        )


class ProfileOnboardStepStateRepository(AsyncRepository[ProfileOnboardStepState]):
    def __init__(self) -> None:
        super().__init__(ProfileOnboardStepState)

    async def get_by_profile_flow_and_step_key(
        self, session: AsyncSession, profile_flow_id: int, step_key: str
    ) -> ProfileOnboardStepState | None:
        return await self.first_where(
            session,
            ProfileOnboardStepState.profile_flow_id == profile_flow_id,
            ProfileOnboardStepState.step_key == step_key,
        )

    async def list_by_profile_flow_id(
        self,
        session: AsyncSession,
        profile_flow_id: int,
        *,
        status: OrchestratorStepStatus | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProfileOnboardStepState]:
        criteria = [ProfileOnboardStepState.profile_flow_id == profile_flow_id]
        if status is not None:
            criteria.append(ProfileOnboardStepState.status == status)
        return await self.list_where(
            session,
            *criteria,
            order_by=(ProfileOnboardStepState.id,),
            limit=limit,
            offset=offset,
        )


onboard_flow_repository = OnboardFlowRepository()
onboard_flow_step_repository = OnboardFlowStepRepository()
profile_onboard_flow_repository = ProfileOnboardFlowRepository()
profile_onboard_step_state_repository = ProfileOnboardStepStateRepository()
