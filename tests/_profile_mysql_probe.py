import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.engine import make_url
from scaffold.models.linkedin_profiles import LinkedInProfile
from scaffold.linkedin_profiles import LinkedInProfileStore, ProfileBusyError, ProfileLeaseLostError


async def main():
    assert make_url(os.environ["PROFILE_TEST_DATABASE_URL"]).database == "linkedin_profile_test", (
        "disposable database required"
    )
    e = create_async_engine(os.environ["PROFILE_TEST_DATABASE_URL"])
    async with e.begin() as c:
        await c.execute(text("CREATE TABLE IF NOT EXISTS candidates(id BIGINT PRIMARY KEY)"))
        await c.execute(text("INSERT IGNORE INTO candidates VALUES (1)"))
        await c.run_sync(LinkedInProfile.__table__.create, checkfirst=True)
    store = LinkedInProfileStore(async_sessionmaker(e, expire_on_commit=False))
    results = await asyncio.gather(
        *(store.acquire(1, operation="login", ttl_s=60) for _ in range(8)), return_exceptions=True
    )
    leases = [r for r in results if not isinstance(r, Exception)]
    assert len(leases) == 1 and sum(isinstance(r, ProfileBusyError) for r in results) == 7, results
    lease = leases[0]
    await store.mark_state(lease, "available", authenticated=True)
    await store.release(lease)
    new = await store.acquire(1, operation="apply", ttl_s=60)
    assert new.fence > lease.fence
    try:
        await store.mark_state(lease, "login_required")
    except ProfileLeaseLostError:
        pass
    else:
        raise AssertionError("stale writer accepted")
    assert await store.release(lease) is False
    await store.release(new)
    print("PASS MySQL 8 concurrent acquisition 8 actors, fencing, stale release")
    await e.dispose()


asyncio.run(main())
