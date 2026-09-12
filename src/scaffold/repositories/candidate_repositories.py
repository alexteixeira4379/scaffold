from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.candidate.candidate_application_data import CandidateApplicationData
from scaffold.models.candidate.candidate_events import CandidateEvent
from scaffold.models.candidate.candidate_preferences import CandidatePreference
from scaffold.models.candidate.candidate_target_profile_entities import CandidateTargetProfileEntity
from scaffold.models.candidate.candidate_target_profile_keywords import CandidateTargetProfileKeyword
from scaffold.models.candidate.candidate_target_profiles import CandidateTargetProfile
from scaffold.models.candidate.candidate_workflow_answers import CandidateWorkflowAnswer
from scaffold.models.candidate.candidate_workflow_sessions import CandidateWorkflowSession
from scaffold.models.candidate.candidate_workflow_steps import CandidateWorkflowStep
from scaffold.models.candidate.candidates import Candidate

from scaffold.constants.schema_enums import WorkflowSessionStatus
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


class CandidateApplicationDataRepository(AsyncRepository[CandidateApplicationData]):
    def __init__(self) -> None:
        super().__init__(CandidateApplicationData)

    async def get_by_candidate_id(
        self, session: AsyncSession, candidate_id: int
    ) -> CandidateApplicationData | None:
        return await self.first_where(
            session, CandidateApplicationData.candidate_id == candidate_id
        )


candidate_application_data_repository = CandidateApplicationDataRepository()


class CandidateTargetProfileEntityRepository(AsyncRepository[CandidateTargetProfileEntity]):
    def __init__(self) -> None:
        super().__init__(CandidateTargetProfileEntity)

    async def list_by_target_profile_id(
        self, session: AsyncSession, target_profile_id: int
    ) -> list[CandidateTargetProfileEntity]:
        return await self.list_where(
            session,
            CandidateTargetProfileEntity.candidate_target_profile_id == target_profile_id,
            order_by=(CandidateTargetProfileEntity.id,),
        )

    async def list_by_professional_entity_id(
        self, session: AsyncSession, entity_id: int
    ) -> list[CandidateTargetProfileEntity]:
        return await self.list_where(
            session,
            CandidateTargetProfileEntity.professional_entity_id == entity_id,
            order_by=(CandidateTargetProfileEntity.id,),
        )

    async def get_entity_ids_by_target_profile_id(
        self, session: AsyncSession, target_profile_id: int
    ) -> list[int]:
        results = await self.list_where(
            session,
            CandidateTargetProfileEntity.candidate_target_profile_id == target_profile_id,
        )
        return [r.professional_entity_id for r in results]

    async def delete_by_target_profile_id(
        self, session: AsyncSession, target_profile_id: int
    ) -> int:
        from sqlalchemy import delete

        stmt = delete(CandidateTargetProfileEntity).where(
            CandidateTargetProfileEntity.candidate_target_profile_id == target_profile_id
        )
        result = await session.execute(stmt)
        return result.rowcount


candidate_target_profile_entity_repository = CandidateTargetProfileEntityRepository()


class CandidateWorkflowSessionRepository(AsyncRepository[CandidateWorkflowSession]):
    def __init__(self) -> None:
        super().__init__(CandidateWorkflowSession)

    async def get_active_by_candidate_and_workflow(
        self, session: AsyncSession, candidate_id: int, workflow_key: str
    ) -> CandidateWorkflowSession | None:
        return await self.first_where(
            session,
            CandidateWorkflowSession.candidate_id == candidate_id,
            CandidateWorkflowSession.workflow_key == workflow_key,
            CandidateWorkflowSession.status.in_(
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
    ) -> list[CandidateWorkflowSession]:
        criteria = [CandidateWorkflowSession.candidate_id == candidate_id]
        if workflow_key is not None:
            criteria.append(CandidateWorkflowSession.workflow_key == workflow_key)
        return await self.list_where(
            session,
            *criteria,
            order_by=(CandidateWorkflowSession.id.desc(),),
            limit=limit,
            offset=offset,
        )


class CandidateWorkflowStepRepository(AsyncRepository[CandidateWorkflowStep]):
    def __init__(self) -> None:
        super().__init__(CandidateWorkflowStep)

    async def get_by_workflow_and_step_key(
        self, session: AsyncSession, workflow_key: str, step_key: str
    ) -> CandidateWorkflowStep | None:
        return await self.first_where(
            session,
            CandidateWorkflowStep.workflow_key == workflow_key,
            CandidateWorkflowStep.step_key == step_key,
        )

    async def list_active_by_workflow_key(
        self,
        session: AsyncSession,
        workflow_key: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CandidateWorkflowStep]:
        return await self.list_where(
            session,
            CandidateWorkflowStep.workflow_key == workflow_key,
            CandidateWorkflowStep.active.is_(True),
            order_by=(CandidateWorkflowStep.step_order, CandidateWorkflowStep.id),
            limit=limit,
            offset=offset,
        )


class CandidateWorkflowAnswerRepository(AsyncRepository[CandidateWorkflowAnswer]):
    def __init__(self) -> None:
        super().__init__(CandidateWorkflowAnswer)

    async def get_by_session_and_step(
        self,
        session: AsyncSession,
        session_id: int,
        step_id: int,
        repeat_index: int | None = None,
    ) -> CandidateWorkflowAnswer | None:
        return await self.first_where(
            session,
            CandidateWorkflowAnswer.session_id == session_id,
            CandidateWorkflowAnswer.step_id == step_id,
            CandidateWorkflowAnswer.repeat_index == repeat_index,
        )

    async def list_by_session_id(
        self,
        session: AsyncSession,
        session_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CandidateWorkflowAnswer]:
        return await self.list_where(
            session,
            CandidateWorkflowAnswer.session_id == session_id,
            order_by=(CandidateWorkflowAnswer.id,),
            limit=limit,
            offset=offset,
        )


candidate_workflow_session_repository = CandidateWorkflowSessionRepository()
candidate_workflow_step_repository = CandidateWorkflowStepRepository()
candidate_workflow_answer_repository = CandidateWorkflowAnswerRepository()
