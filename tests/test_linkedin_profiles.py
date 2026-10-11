"""Profile ownership survives processes, blocks stale writes and preserves disconnect tombstones."""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text, update
from datetime import timedelta
from scaffold.models.linkedin_profiles import LinkedInProfile
from scaffold.linkedin_profiles import (
    LinkedInProfileStore,
    ProfileBusyError,
    ProfileLeaseLostError,
    ProfileBlockedError,
    now,
)


@pytest.fixture
async def store(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/profiles.db")
    async with engine.begin() as c:
        await c.execute(text("CREATE TABLE candidates (id BIGINT PRIMARY KEY)"))
        await c.execute(text("INSERT INTO candidates VALUES (1), (2)"))
        await c.run_sync(LinkedInProfile.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield LinkedInProfileStore(factory)
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_login_and_apply_are_fenced(store):
    lease = await store.acquire(1, operation="login", ttl_s=120)
    with pytest.raises(ProfileBusyError):
        await store.acquire(1, operation="login", ttl_s=120)
    await store.mark_state(lease, "available", authenticated=True)
    await store.release(lease)
    new = await store.acquire(1, operation="apply", ttl_s=120)
    assert (
        new.profile_id == lease.profile_id
        and new.generation == lease.generation
        and new.fence > lease.fence
    )
    with pytest.raises(ProfileLeaseLostError):
        await store.mark_state(lease, "login_required")
    assert await store.release(lease) is False
    await store.assert_lease(new)


@pytest.mark.asyncio
async def test_crash_reclaim_changes_fence_but_preserves_profile(store):
    lease = await store.acquire(1, operation="login", ttl_s=120)
    await store.mark_state(lease, "available", authenticated=True)
    async with store.factory() as s:
        await s.execute(
            update(LinkedInProfile)
            .where(LinkedInProfile.candidate_id == 1)
            .values(lease_expires_at=now() - timedelta(seconds=1))
        )
        await s.commit()
    restarted = LinkedInProfileStore(store.factory)
    recovered = await restarted.acquire(1, operation="apply", ttl_s=120)
    assert recovered.profile_id == lease.profile_id and recovered.fence > lease.fence
    with pytest.raises(ProfileLeaseLostError):
        await restarted.assert_lease(lease)


@pytest.mark.asyncio
async def test_disconnect_tombstone_and_isolation(store):
    await store.disconnect(1)
    with pytest.raises(ProfileBlockedError):
        await store.acquire(1, operation="apply", ttl_s=120)
    one = await store.acquire(1, operation="login", ttl_s=120)
    two = await store.acquire(2, operation="login", ttl_s=120)
    assert one.profile_id != two.profile_id
    with pytest.raises(ProfileBusyError):
        await store.disconnect(1)
    await store.release(one)
    await store.disconnect(1)
    relogin = await store.acquire(1, operation="login", ttl_s=120)
    assert relogin.generation > one.generation
    with pytest.raises(ProfileLeaseLostError):
        await store.mark_state(one, "available", authenticated=True)


@pytest.mark.asyncio
async def test_infra_unavailable_recoverable_but_challenge_blocks(store):
    lease = await store.acquire(1, operation="login", ttl_s=120)
    await store.mark_state(lease, "available", authenticated=True)
    await store.mark_state(lease, "unavailable", reason="network")
    await store.release(lease)
    recovered = await store.acquire(1, operation="apply", ttl_s=120)
    await store.mark_state(recovered, "verification_required", reason="captcha")
    await store.release(recovered)
    with pytest.raises(ProfileBlockedError):
        await store.acquire(1, operation="receipt", ttl_s=120)


@pytest.mark.asyncio
async def test_cleanup_failure_preserves_provider_intervention(store):
    lease = await store.acquire(1, operation="login", ttl_s=120)
    await store.mark_state(lease, "verification_required", reason="provider_checkpoint")
    await store.mark_unavailable(lease, "profile_flush_unconfirmed")
    row = await store.get(1)
    assert row.state == "verification_required" and row.reason == "provider_checkpoint"


@pytest.mark.asyncio
async def test_login_event_requires_authentication_in_current_fence(store, monkeypatch):
    import scaffold.messaging.domain as domain

    emitted = []

    async def emit(*args, **kwargs):
        emitted.append((args, kwargs))

    monkeypatch.setattr(domain, "emit", emit)
    initial = await store.acquire(1, operation="login", ttl_s=120)
    await store.mark_state(initial, "available", authenticated=True)
    await store.release(initial, emit_available=True)
    assert len(emitted) == 1
    cancelled = await store.acquire(1, operation="login", ttl_s=120)
    await store.release(cancelled, emit_available=True)
    assert len(emitted) == 1, "cancelled login emitted a stale availability event"


@pytest.mark.asyncio
async def test_outbox_failure_rolls_back_login_lease_release(store, monkeypatch):
    import scaffold.messaging.domain as domain

    async def emit(*args, **kwargs):
        raise RuntimeError("synthetic outbox failure")

    monkeypatch.setattr(domain, "emit", emit)
    lease = await store.acquire(1, operation="login", ttl_s=120)
    await store.mark_state(lease, "available", authenticated=True)
    with pytest.raises(RuntimeError, match="outbox"):
        await store.release(lease, emit_available=True)
    row = await store.get(1)
    assert row.lease_owner == lease.owner
