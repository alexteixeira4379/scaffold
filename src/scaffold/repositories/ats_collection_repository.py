"""Short transactions for ATS collection; token and expiry fence every write."""
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, update, or_, func
from scaffold.models.ats.ats_discovery_sources import AtsDiscoverySource as Source
from scaffold.models.ats.ats_providers import AtsProvider as Provider
from scaffold.models.ats.ats_provider_schedules import AtsProviderSchedule as Schedule
from scaffold.models.ats.ats_collection_runs import AtsCollectionRun as Run


class LeaseLostError(RuntimeError):
    pass


class AtsCollectionRepository:
    async def claim(self, session, *, provider_codes, now, lease_seconds, exclude_ids=()):
        eligibility = (
            Source.active.is_(True),
            Source.qualification_status == "qualified",
            Source.collection_state != "blocked",
            or_(Source.next_collection_at.is_(None), Source.next_collection_at <= now),
            or_(Source.collection_lease_until.is_(None), Source.collection_lease_until <= now),
        )
        # Do not lock the provider JOIN: MySQL would lock the shared provider row
        # and serialize unrelated sources. Lock each candidate by primary key.
        stmt = (select(Source.id, Provider.code)
                .join(Provider, Provider.id == Source.ats_provider_id)
                .where(*eligibility, Provider.active.is_(True), Provider.code.in_(provider_codes))
                .order_by(Source.last_attempt_at.asc(), Source.id.asc()).limit(100))
        if exclude_ids:
            stmt = stmt.where(Source.id.not_in(exclude_ids))
        candidates = (await session.execute(stmt)).all()
        source = None
        code = None
        for candidate_id, candidate_code in candidates:
            source = (await session.execute(select(Source).where(Source.id == candidate_id, *eligibility)
                                             .with_for_update(skip_locked=True))).scalar_one_or_none()
            if source is not None:
                code = candidate_code
                break
        if source is None:
            return None
        token = str(uuid4())
        if not source.collection_cycle_id or source.collection_state in ("idle", "completed"):
            if source.collection_state in ("idle", "completed"):
                source.collection_restarts = 0
            source.collection_cycle_id = str(uuid4())
            source.checkpoint_value = {}
            source.collection_failures = 0
            session.add(Run(id=source.collection_cycle_id, source_id=source.id,
                            provider_code=code, started_at=now, status="running",
                            attempts=0, batches=0, observed=0, published=0, errors=0))
            await session.flush()
        source.collection_lease_token = token
        source.collection_lease_until = now + timedelta(seconds=lease_seconds)
        source.last_attempt_at = now
        source.collection_state = "running"
        await session.execute(update(Run).where(Run.id == source.collection_cycle_id)
                              .values(attempts=Run.attempts + 1, status="running"))
        await session.flush()
        return source, code, token

    async def _fence(self, session, source_id, token, now, values):
        result = await session.execute(update(Source).where(
            Source.id == source_id, Source.collection_lease_token == token,
            Source.collection_lease_until > now,
        ).values(**values).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise LeaseLostError("ATS collection lease lost")

    async def heartbeat(self, session, *, source_id, token, now, lease_seconds):
        await self._fence(session, source_id, token, now,
                          {"collection_lease_until": now + timedelta(seconds=lease_seconds)})

    async def initialize(self, session, *, source_id, cycle_id, token, checkpoint, now):
        await self._fence(session, source_id, token, now, {
            "checkpoint_key": "ats-provider-v1", "checkpoint_value": checkpoint,
            "checkpoint_updated_at": now,
        })

    async def save_batch(self, session, *, source_id, cycle_id, token, checkpoint, observed, published, now, discarded=0):
        await self._fence(session, source_id, token, now, {
            "checkpoint_key": "ats-provider-v1", "checkpoint_value": checkpoint,
            "checkpoint_updated_at": now, "collection_failures": 0,
        })
        await session.execute(update(Run).where(Run.id == cycle_id).values(
            batches=Run.batches + 1, observed=Run.observed + observed,
            published=Run.published + published, discarded=Run.discarded + discarded))

    async def release(self, session, *, source_id, cycle_id, token, now, status,
                      next_at, failures=0, error_category=None, observed=0, published=0, discarded=0, error_detail=None):
        values = {"collection_state": status, "next_collection_at": next_at,
                  "collection_lease_token": None, "collection_lease_until": None,
                  "collection_failures": failures}
        if status == "completed":
            values.update(last_collected_at=now, checkpoint_value={}, checkpoint_key=None, collection_restarts=0)
        if status == "restarted":
            values.update(collection_cycle_id=None, checkpoint_value={}, checkpoint_key=None,
                          collection_restarts=Source.collection_restarts + 1)
        await self._fence(session, source_id, token, now, values)
        updates = dict(status=status, next_execution_at=next_at,
                       observed=Run.observed + observed, published=Run.published + published,
                       discarded=Run.discarded + discarded)
        if error_category:
            updates.update(errors=Run.errors + 1, last_error_category=error_category, last_error_detail=error_detail)
        if status in ("completed", "restarted", "blocked"):
            updates["finished_at"] = now
        await session.execute(update(Run).where(Run.id == cycle_id).values(**updates))

    async def interval(self, session, *, provider_id):
        value = (await session.execute(select(Schedule.interval_seconds).where(
            Schedule.ats_provider_id == provider_id, Schedule.active.is_(True)))).scalar_one_or_none()
        return max(345600, min(int(value or 345600), 432000))


ats_collection_repository = AtsCollectionRepository()
