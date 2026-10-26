"""Disposable Browserless/Redis integration. No AI and no public destinations."""

import asyncio
import os
import multiprocessing
import pytest
from scaffold.browser.ingestion import IngestionBudget, NavigationPacer, IngestionBrowser
from scaffold.browser import BrowserConfiguration, BrowserManager, SlotAdmission

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_BROWSERLESS") != "1", reason="disposable services required"
)
URL = "redis://localhost:36379/15"


def try_slot(q, owner):
    async def run():
        c = IngestionBudget(URL, flow="linkedin", flow_limit=2)
        await c.connect()
        q.put(await c.acquire_pool_slot("", owner, 12, 90))
        await c.close()

    asyncio.run(run())


async def test_atomic_limits_across_processes_and_application_reserve():
    c = IngestionBudget(URL, flow="linkedin", flow_limit=2)
    await c.connect()
    await c._redis.flushdb()
    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    ps = [ctx.Process(target=try_slot, args=(q, str(i))) for i in range(7)]
    for p in ps:
        p.start()
    for p in ps:
        await asyncio.to_thread(p.join, 10)
    assert sum(q.get(timeout=2) for _ in ps) == 2
    assert await c._redis.zcard(c.keys[0]) == 2
    await c._redis.flushdb()
    common = IngestionBudget(URL, flow="common", flow_limit=2)
    await common.connect()
    li = IngestionBudget(URL, flow="linkedin", flow_limit=6)
    await li.connect()
    assert all([await li.acquire_pool_slot("", str(i), 12, 90) for i in range(6)])
    assert all([await common.acquire_pool_slot("", "c" + str(i), 12, 90) for i in range(2)])
    assert not await common.acquire_pool_slot("", "excess", 12, 90)
    from scaffold.cache.redis import RedisCache

    app = RedisCache(URL)
    await app.connect()
    assert all([await app.acquire_pool_slot(c.keys[0], "a" + str(i), 12, 90) for i in range(4)])
    assert not await app.acquire_pool_slot(c.keys[0], "over", 12, 90)
    assert await common.renew_pool_slot("", "c0", 90)
    await common.release_pool_slot("", "c0")
    assert await common.acquire_pool_slot("", "replacement", 12, 90)
    await c._redis.flushdb()
    for x in (common, li, app, c):
        await x.close()


async def test_distributed_pacer_cooldown():
    c = IngestionBudget(URL, flow="linkedin")
    await c.connect()
    await c._redis.flushdb()
    a = NavigationPacer(c, interval_s=0.1, cooldown_s=0.2)
    b = NavigationPacer(c, interval_s=0.1, cooldown_s=0.2)
    starts = []

    async def start(p):
        await p.acquire()
        starts.append(asyncio.get_running_loop().time())

    await asyncio.gather(*(start(p) for p in [a, b, a, b]))
    assert all(y - x >= 0.08 for x, y in zip(starts, starts[1:]))
    await a.cooldown()
    before = asyncio.get_running_loop().time()
    await b.acquire()
    assert asyncio.get_running_loop().time() - before >= 0.18
    await c._redis.flushdb()
    await c.close()


async def test_javascript_isolation_cancellation_cleanup():
    import httpx
    from urllib.parse import quote

    c = IngestionBudget(URL, flow="common", flow_limit=2)
    await c.connect()
    await c._redis.flushdb()
    config = BrowserConfiguration(
        "ws://localhost:33003", "synthetic", session_timeout_s=60, verify_remote=True
    )
    manager = BrowserManager(
        config,
        admission=SlotAdmission(c, key=c.keys[0], limit=12, ttl_s=90, max_browser_session_s=60),
    )
    await manager.start()
    try:
        browser = IngestionBrowser(manager)
        html = (
            '<body><script>setTimeout(()=>document.body.innerHTML="<article>'
            + ("Rendered description " * 30)
            + '</article>",100)</script>'
        )
        results = await asyncio.gather(
            *(browser.render("data:text/html," + quote(html)) for _ in range(2))
        )
        assert all("Rendered description" in x.html for x in results)
        assert await c._redis.zcard(c.keys[0]) == 0
        entered = asyncio.Event()

        async def cancelled():
            async with manager.acquire():
                entered.set()
                await asyncio.sleep(100)

        task = asyncio.create_task(cancelled())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with httpx.AsyncClient() as client:
            assert (await client.get(config.management_url("/sessions"))).json() == []
        assert await c._redis.zcard(c.keys[0]) == 0
    finally:
        await manager.close()
        await c.close()


async def test_redis_unavailable_is_infrastructure():
    from scaffold.messaging.processing import InfrastructureUnavailable

    c = IngestionBudget("redis://localhost:1/0", flow="common", flow_limit=2)
    with pytest.raises(InfrastructureUnavailable):
        async with SlotAdmission(
            c, key=c.keys[0], limit=12, ttl_s=90, max_browser_session_s=60
        ).lease():
            pass


async def test_long_shared_cooldown_defers_without_opening_browser():
    from unittest.mock import AsyncMock
    from scaffold.messaging.processing import DeferredMessage

    c = IngestionBudget(URL, flow="linkedin")
    await c.connect()
    await c._redis.flushdb()
    pacer = NavigationPacer(c)
    await pacer.cooldown(60)
    manager = AsyncMock()
    with pytest.raises(DeferredMessage):
        await IngestionBrowser(manager, pacer=pacer).render("https://www.linkedin.com/jobs/view/1")
    manager.acquire.assert_not_called()
    await c._redis.flushdb()
    await c.close()


async def test_browserless_restart_recovers_with_same_process_driver():
    import subprocess
    import httpx
    from scaffold.browser.ingestion import CollectionError
    from urllib.parse import quote

    c = IngestionBudget(URL, flow="common", flow_limit=2)
    await c.connect()
    await c._redis.flushdb()
    config = BrowserConfiguration(
        "ws://localhost:33003", "synthetic", session_timeout_s=60, verify_remote=True
    )
    manager = BrowserManager(
        config,
        admission=SlotAdmission(c, key=c.keys[0], limit=12, ttl_s=90, max_browser_session_s=60),
    )
    await manager.start()
    browser = IngestionBrowser(manager)
    try:
        pending = asyncio.create_task(
            browser.render("data:text/html,<body>waiting for content</body>")
        )
        for _ in range(100):
            if await c._redis.zcard(c.keys[0]):
                break
            await asyncio.sleep(0.02)
        # The name belongs exclusively to this disposable test environment.
        await asyncio.to_thread(
            subprocess.run,
            ["docker", "restart", "ingestion-test-browser"],
            capture_output=True,
            check=True,
        )
        with pytest.raises(CollectionError):
            await pending
        async with httpx.AsyncClient() as client:
            for _ in range(100):
                try:
                    if (await client.get(config.management_url("/config"))).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.1)
        # A retained unverified lease is bounded; other capacity can recover immediately.
        result = await browser.render(
            "data:text/html," + quote("<body>" + ("Recovered rendered text. " * 20) + "</body>")
        )
        assert "Recovered rendered text." in result.html
    finally:
        await manager.close()
        await c.close()


async def test_short_ingestion_lease_cannot_expire_long_application_reservation():
    from scaffold.cache.redis import RedisCache

    app = RedisCache(URL)
    await app.connect()
    await app._redis.flushdb()
    short = IngestionBudget(URL, flow="common", flow_limit=2)
    await short.connect()
    try:
        key = "application:browserless:global"
        assert await app.acquire_pool_slot(key, "long-application", 12, 600)
        assert await short.acquire_pool_slot("", "ingestion", 12, 90)
        assert await app._redis.ttl(key) >= 599
        assert await short.renew_pool_slot("", "ingestion", 90)
        assert await app._redis.ttl(key) >= 599
        assert await app._redis.zscore(key, "long-application") is not None
    finally:
        await app._redis.flushdb()
        await short.close()
        await app.close()
