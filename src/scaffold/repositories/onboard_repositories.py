from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.constants.schema_enums import OnboardPhase
from scaffold.models.onboard.onboard_steps import OnboardStep
from scaffold.repositories.base import AsyncRepository


class OnboardStepRepository(AsyncRepository[OnboardStep]):
    def __init__(self) -> None:
        super().__init__(OnboardStep)

    async def get_by_step_key(self, session: AsyncSession, step_key: str) -> OnboardStep | None:
        return await self.first_where(session, OnboardStep.step_key == step_key)

    async def list_by_phase(
        self,
        session: AsyncSession,
        phase: OnboardPhase,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[OnboardStep]:
        return await self.list_where(
            session,
            OnboardStep.active.is_(True),
            OnboardStep.phase == phase,
            order_by=(OnboardStep.step_order, OnboardStep.id),
            limit=limit,
            offset=offset,
        )

    async def list_active_ordered(
        self,
        session: AsyncSession,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[OnboardStep]:
        return await self.list_where(
            session,
            OnboardStep.active.is_(True),
            order_by=(OnboardStep.step_order, OnboardStep.id),
            limit=limit,
            offset=offset,
        )


onboard_step_repository = OnboardStepRepository()
