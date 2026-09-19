from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from scaffold.models import Candidate
from scaffold.models.domain_delivery import DomainProjection, DomainOutbox


async def test_missing_session_parks_and_reconnect_replays_once(db, load_service):
    module = load_service("linkedin-application-worker", "src.services.pending_service")
    async with db() as session, session.begin():
        session.add(Candidate(id=1, full_name="Candidate"))
    cache = AsyncMock()
    cache.get_json.return_value = None
    deps = SimpleNamespace(session_factory=db, cache=cache)
    msg = SimpleNamespace(
        candidate=SimpleNamespace(id=1),
        application_id=5,
        model_dump=lambda: {"application_id": 5, "candidate": {"id": 1}},
    )
    await module.park(deps, msg)
    await module.park(deps, msg)
    async with db() as session:
        assert len((await session.scalars(select(DomainProjection))).all()) == 1
    event = {"candidate_id": 1, "event_id": "reconnected"}
    for _ in range(2):
        async with db() as session, session.begin():
            await module.handle_session_available(session, event)
    async with db() as session:
        assert not (await session.scalars(select(DomainProjection))).all()
        commands = (
            await session.scalars(
                select(DomainOutbox).where(
                    DomainOutbox.destination == "application.linkedin.submit"
                )
            )
        ).all()
        assert len(commands) == 1


async def test_login_race_does_not_leave_work_waiting_for_an_already_consumed_event(
    db, load_service
):
    module = load_service("linkedin-application-worker", "src.services.pending_service")
    async with db() as session, session.begin():
        session.add(Candidate(id=1, full_name="Candidate"))
    cache = AsyncMock()
    current = [{"name": "li_at", "value": "new"}]
    cache.get_json.return_value = current
    deps = SimpleNamespace(session_factory=db, cache=cache)
    msg = SimpleNamespace(
        candidate=SimpleNamespace(id=1),
        application_id=5,
        model_dump=lambda: {"application_id": 5, "candidate": {"id": 1}},
    )
    await module.park(deps, msg, failed_cookies=[{"name": "li_at", "value": "old"}])
    cache.delete.assert_not_called()
    async with db() as session:
        assert not (await session.scalars(select(DomainProjection))).all()
        assert (
            await session.scalar(select(DomainOutbox))
        ).destination == "application.linkedin.submit"


async def test_candidate_cookie_never_overwrites_global_ingestion_session(db, load_service):
    module = load_service("login-bridge", "app.persistence")
    async with db() as session, session.begin():
        session.add(Candidate(id=1, full_name="Candidate"))
    from unittest.mock import MagicMock

    redis = MagicMock()
    with (
        patch.object(module, "_get_redis", return_value=redis),
        patch("scaffold.db.session.get_session_factory", return_value=db),
    ):
        await module.save_cookies("", [{"name": "li_at", "value": "individual"}], 1)
    assert redis.set.call_count == 1
    assert redis.set.call_args.args[0] == "linkedin:session:1"
    async with db() as session:
        assert (
            await session.scalar(select(DomainOutbox))
        ).destination == "linkedin.session.available"
