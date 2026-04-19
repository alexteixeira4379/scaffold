from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.candidate.candidate_events import CandidateEvent
from scaffold.models.candidate.candidate_preferences import CandidatePreference
from scaffold.models.candidate.candidate_target_profile_keywords import CandidateTargetProfileKeyword
from scaffold.models.candidate.candidate_target_profiles import CandidateTargetProfile
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


class CandidateTargetProfileRepository(AsyncRepository[CandidateTargetProfile]):
    def __init__(self) -> None:
        super().__init__(CandidateTargetProfile)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CandidateTargetProfile]:
        return await self.list_where(
            session,
            CandidateTargetProfile.candidate_id == candidate_id,
            order_by=(CandidateTargetProfile.id,),
            limit=limit,
            offset=offset,
        )


class CandidateTargetProfileKeywordRepository(AsyncRepository[CandidateTargetProfileKeyword]):
    def __init__(self) -> None:
        super().__init__(CandidateTargetProfileKeyword)

    async def list_by_candidate_target_profile_id(
        self,
        session: AsyncSession,
        candidate_target_profile_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CandidateTargetProfileKeyword]:
        return await self.list_where(
            session,
            CandidateTargetProfileKeyword.candidate_target_profile_id == candidate_target_profile_id,
            order_by=(CandidateTargetProfileKeyword.id,),
            limit=limit,
            offset=offset,
        )


candidate_repository = CandidateRepository()
candidate_event_repository = CandidateEventRepository()
candidate_preference_repository = CandidatePreferenceRepository()
candidate_target_profile_repository = CandidateTargetProfileRepository()
candidate_target_profile_keyword_repository = CandidateTargetProfileKeywordRepository()
