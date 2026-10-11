"""SQL fenced access shared by login, applications and receipt reconciliation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from scaffold.models.linkedin_profiles import LinkedInProfile


class ProfileBusyError(RuntimeError):
    pass


class ProfileLeaseLostError(RuntimeError):
    pass


class ProfileBlockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProfileLease:
    candidate_id: int
    profile_id: str
    generation: int
    fence: int
    owner: str
    expires_at: datetime
    operation: str


def now():
    return datetime.now(UTC).replace(tzinfo=None)


class LinkedInProfileStore:
    def __init__(self, session_factory=None):
        if session_factory is None:
            from scaffold.db.session import get_session_factory

            session_factory = get_session_factory()
        self.factory = session_factory

    async def get(self, candidate_id):
        async with self.factory() as s:
            return await s.get(LinkedInProfile, candidate_id)

    async def acquire(self, candidate_id, *, operation, ttl_s):
        if operation not in {"login", "apply", "receipt"} or candidate_id <= 0 or ttl_s <= 0:
            raise ValueError("invalid_profile_lease")
        async with self.factory() as s:
            if await s.get(LinkedInProfile, candidate_id) is None:
                s.add(LinkedInProfile(candidate_id=candidate_id, profile_id=str(uuid4())))
                try:
                    await s.commit()
                except IntegrityError:
                    await s.rollback()
            owner = str(uuid4())
            expires = now() + timedelta(seconds=ttl_s)
            result = await s.execute(
                update(LinkedInProfile)
                .where(
                    LinkedInProfile.candidate_id == candidate_id,
                    or_(
                        LinkedInProfile.lease_owner.is_(None),
                        LinkedInProfile.lease_expires_at <= now(),
                    ),
                )
                .values(
                    lease_owner=owner,
                    lease_operation=operation,
                    lease_expires_at=expires,
                    fence=LinkedInProfile.fence + 1,
                )
            )
            if result.rowcount != 1:
                await s.rollback()
                raise ProfileBusyError("linkedin_profile_busy")
            await s.commit()
            row = (
                await s.execute(
                    select(LinkedInProfile)
                    .where(LinkedInProfile.candidate_id == candidate_id)
                    .execution_options(populate_existing=True)
                )
            ).scalar_one()
            lease = ProfileLease(
                candidate_id, row.profile_id, row.generation, row.fence, owner, expires, operation
            )
            if operation != "login" and row.state not in {"available", "unavailable"}:
                await self.release(lease)
                raise ProfileBlockedError(row.state)
            return lease

    def _conditions(self, lease):
        return (
            LinkedInProfile.candidate_id == lease.candidate_id,
            LinkedInProfile.profile_id == lease.profile_id,
            LinkedInProfile.generation == lease.generation,
            LinkedInProfile.fence == lease.fence,
            LinkedInProfile.lease_owner == lease.owner,
            LinkedInProfile.lease_expires_at > now(),
        )

    async def assert_lease(self, lease, *, require_available=True):
        async with self.factory() as s:
            row = (
                await s.execute(select(LinkedInProfile).where(*self._conditions(lease)))
            ).scalar_one_or_none()
            if row is None:
                raise ProfileLeaseLostError("linkedin_profile_lease_lost")
            if require_available and row.state != "available":
                raise ProfileBlockedError(row.state)
            return row

    async def mark_state(self, lease, state, reason=None, *, authenticated=False):
        if state not in {
            "available",
            "login_required",
            "verification_required",
            "unavailable",
            "disconnected",
        }:
            raise ValueError("invalid_linkedin_profile_state")
        if authenticated and state != "available":
            raise ValueError("authentication_requires_available")
        values = {"state": state, "reason": reason}
        if authenticated:
            values.update(
                last_authenticated_at=now(), last_used_at=now(), authenticated_fence=lease.fence
            )
        async with self.factory() as s:
            result = await s.execute(
                update(LinkedInProfile).where(*self._conditions(lease)).values(**values)
            )
            if result.rowcount != 1:
                raise ProfileLeaseLostError("linkedin_profile_lease_lost")
            await s.commit()

    async def mark_unavailable(self, lease, reason):
        """Infrastructure failures cannot erase a provider intervention requirement."""
        async with self.factory() as s:
            await s.execute(
                update(LinkedInProfile)
                .where(
                    *self._conditions(lease),
                    LinkedInProfile.state.in_(["available", "unavailable"]),
                )
                .values(state="unavailable", reason=reason)
            )
            await s.commit()

    async def release(self, lease, *, emit_available=False):
        async with self.factory() as s:
            result = await s.execute(
                update(LinkedInProfile)
                .where(*self._conditions(lease))
                .values(lease_owner=None, lease_operation=None, lease_expires_at=None)
            )
            if result.rowcount == 1 and emit_available and lease.operation == "login":
                row = await s.get(LinkedInProfile, lease.candidate_id)
                if row.state == "available" and row.authenticated_fence == lease.fence:
                    from scaffold.messaging.domain import emit

                    await emit(
                        s,
                        "login-bridge",
                        "linkedin.session.available",
                        lease.candidate_id,
                        {},
                        key=f"linkedin-profile:{lease.profile_id}:{lease.generation}:{lease.fence}",
                    )
            await s.commit()
            return result.rowcount == 1

    async def disconnect(self, candidate_id, *, session=None):
        if session is None:
            async with self.factory() as s:
                await self.disconnect(candidate_id, session=s)
                await s.commit()
            return
        row = await session.get(LinkedInProfile, candidate_id)
        if row is None:
            session.add(
                LinkedInProfile(
                    candidate_id=candidate_id,
                    profile_id=str(uuid4()),
                    state="disconnected",
                    reason="candidate_disconnected",
                )
            )
            await session.flush()
            return
        result = await session.execute(
            update(LinkedInProfile)
            .where(
                LinkedInProfile.candidate_id == candidate_id,
                or_(
                    LinkedInProfile.lease_owner.is_(None), LinkedInProfile.lease_expires_at <= now()
                ),
            )
            .values(
                state="disconnected",
                reason="candidate_disconnected",
                generation=LinkedInProfile.generation + 1,
                fence=LinkedInProfile.fence + 1,
                lease_owner=None,
                lease_operation=None,
                lease_expires_at=None,
            )
        )
        if result.rowcount != 1:
            raise ProfileBusyError("linkedin_profile_busy")
