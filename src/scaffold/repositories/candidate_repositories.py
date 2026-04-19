from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.candidate.candidate_events import CandidateEvent
from scaffold.models.candidate.candidate_preferences import CandidatePreference
from scaffold.models.candidate.candidate_search_presets import CandidateSearchPreset
from scaffold.models.candidate.candidate_search_subscriptions import CandidateSearchSubscription
from scaffold.models.candidate.candidates import Candidate

from scaffold.repositories.base import AsyncRepository


class CandidateRepository(AsyncRepository[Candidate]):
    def __init__(self) -> None:
        super().__init__(Candidate)

    async def get_by_generated_token(self, session: AsyncSession, token: str) -> Candidate | None:
        return await self.first_where(session, Candidate.generated_token == token)

    async def get_by_email_lower(self, session: AsyncSession, email: str) -> Candidate | None:
        stmt = select(Candidate).where(func.lower(Candidate.email) == email.lower()).limit(1)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_by_phone(self, session: AsyncSession, phone: str) -> Candidate | None:
        return await self.first_where(session, Candidate.phone == phone)

    async def list_by_status(
        self,
        session: AsyncSession,
        status: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Candidate]:
        return await self.list_where(
            session,
            Candidate.status == status,
            order_by=(Candidate.id,),
            limit=limit,
            offset=offset,
        )


class CandidateEventRepository(AsyncRepository[CandidateEvent]):
    def __init__(self) -> None:
        super().__init__(CandidateEvent)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CandidateEvent]:
        return await self.list_where(
            session,
            CandidateEvent.candidate_id == candidate_id,
            order_by=(CandidateEvent.id.desc(),),
            limit=limit,
            offset=offset,
        )


class CandidatePreferenceRepository(AsyncRepository[CandidatePreference]):
    def __init__(self) -> None:
        super().__init__(CandidatePreference)

    async def get_by_candidate_id(
        self, session: AsyncSession, candidate_id: int
    ) -> CandidatePreference | None:
        return await self.first_where(session, CandidatePreference.candidate_id == candidate_id)


class CandidateSearchPresetRepository(AsyncRepository[CandidateSearchPreset]):
    def __init__(self) -> None:
        super().__init__(CandidateSearchPreset)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CandidateSearchPreset]:
        return await self.list_where(
            session,
            CandidateSearchPreset.candidate_id == candidate_id,
            order_by=(CandidateSearchPreset.id,),
            limit=limit,
            offset=offset,
        )


class CandidateSearchSubscriptionRepository(AsyncRepository[CandidateSearchSubscription]):
    def __init__(self) -> None:
        super().__init__(CandidateSearchSubscription)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CandidateSearchSubscription]:
        return await self.list_where(
            session,
            CandidateSearchSubscription.candidate_id == candidate_id,
            order_by=(CandidateSearchSubscription.id,),
            limit=limit,
            offset=offset,
        )


candidate_repository = CandidateRepository()
candidate_event_repository = CandidateEventRepository()
candidate_preference_repository = CandidatePreferenceRepository()
candidate_search_preset_repository = CandidateSearchPresetRepository()
candidate_search_subscription_repository = CandidateSearchSubscriptionRepository()
