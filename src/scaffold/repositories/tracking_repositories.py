from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.models.tracking.tracking_attributions import TrackingAttribution
from scaffold.models.tracking.tracking_clicks import TrackingClick
from scaffold.models.tracking.tracking_events import TrackingEvent
from scaffold.models.tracking.tracking_sessions import TrackingSession
from scaffold.models.tracking.tracking_visits import TrackingVisit

from scaffold.repositories.base import AsyncRepository


class TrackingSessionRepository(AsyncRepository[TrackingSession]):
    def __init__(self) -> None:
        super().__init__(TrackingSession)

    async def get_by_session_key(self, session: AsyncSession, session_key: str) -> TrackingSession | None:
        return await self.first_where(session, TrackingSession.session_key == session_key)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackingSession]:
        return await self.list_where(
            session,
            TrackingSession.candidate_id == candidate_id,
            order_by=(TrackingSession.id.desc(),),
            limit=limit,
            offset=offset,
        )


class TrackingClickRepository(AsyncRepository[TrackingClick]):
    def __init__(self) -> None:
        super().__init__(TrackingClick)

    async def get_by_click_key(self, session: AsyncSession, click_key: str) -> TrackingClick | None:
        return await self.first_where(session, TrackingClick.click_key == click_key)

    async def list_by_track_code(
        self,
        session: AsyncSession,
        track_code: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackingClick]:
        return await self.list_where(
            session,
            TrackingClick.track_code == track_code,
            order_by=(TrackingClick.id.desc(),),
            limit=limit,
            offset=offset,
        )

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackingClick]:
        return await self.list_where(
            session,
            TrackingClick.candidate_id == candidate_id,
            order_by=(TrackingClick.id.desc(),),
            limit=limit,
            offset=offset,
        )


class TrackingVisitRepository(AsyncRepository[TrackingVisit]):
    def __init__(self) -> None:
        super().__init__(TrackingVisit)

    async def list_by_session_id(
        self,
        session: AsyncSession,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackingVisit]:
        return await self.list_where(
            session,
            TrackingVisit.session_id == session_id,
            order_by=(TrackingVisit.id.desc(),),
            limit=limit,
            offset=offset,
        )

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackingVisit]:
        return await self.list_where(
            session,
            TrackingVisit.candidate_id == candidate_id,
            order_by=(TrackingVisit.id.desc(),),
            limit=limit,
            offset=offset,
        )


class TrackingEventRepository(AsyncRepository[TrackingEvent]):
    def __init__(self) -> None:
        super().__init__(TrackingEvent)

    async def list_by_session_id(
        self,
        session: AsyncSession,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackingEvent]:
        return await self.list_where(
            session,
            TrackingEvent.session_id == session_id,
            order_by=(TrackingEvent.id.desc(),),
            limit=limit,
            offset=offset,
        )

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackingEvent]:
        return await self.list_where(
            session,
            TrackingEvent.candidate_id == candidate_id,
            order_by=(TrackingEvent.id.desc(),),
            limit=limit,
            offset=offset,
        )


class TrackingAttributionRepository(AsyncRepository[TrackingAttribution]):
    def __init__(self) -> None:
        super().__init__(TrackingAttribution)

    async def list_by_candidate_id(
        self,
        session: AsyncSession,
        candidate_id: int,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TrackingAttribution]:
        return await self.list_where(
            session,
            TrackingAttribution.candidate_id == candidate_id,
            order_by=(TrackingAttribution.id.desc(),),
            limit=limit,
            offset=offset,
        )


tracking_session_repository = TrackingSessionRepository()
tracking_click_repository = TrackingClickRepository()
tracking_visit_repository = TrackingVisitRepository()
tracking_event_repository = TrackingEventRepository()
tracking_attribution_repository = TrackingAttributionRepository()
