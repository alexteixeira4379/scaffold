"""Browserless-only public collection, with distributed capacity and navigation pacing."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

from scaffold.browser.admission import AdmissionUnavailable, SlotAdmission
from scaffold.browser.manager import BrowserConfiguration, BrowserManager
from scaffold.cache.redis import RedisCache
from scaffold.messaging.processing import (
    DeferredMessage,
    InfrastructureUnavailable,
    RetryableMessageError,
)


class CollectionError(RetryableMessageError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = self.failure_class = code
        self.retryable = True


@dataclass(frozen=True)
class RenderedPage:
    html: str
    url: str
    status: int


class IngestionBudget(RedisCache):
    """Acquire every budget atomically, using the applications' existing global key."""

    def __init__(self, url, *, flow, global_limit=12, ingestion_limit=8, flow_limit=6):
        super().__init__(url)
        if (
            min(global_limit, ingestion_limit, flow_limit) <= 0
            or ingestion_limit > global_limit - 4
            or flow_limit > ingestion_limit
        ):
            raise ValueError("ingestion budgets must preserve four application slots")
        self.keys = [
            "application:browserless:global",
            "ingestion:browserless:all",
            f"ingestion:browserless:{flow}",
        ]
        self.limits = [global_limit, ingestion_limit, flow_limit]

    async def acquire_pool_slot(self, key, owner, limit, ttl_s):
        script = """
        local t = redis.call('TIME'); local now = tonumber(t[1]) + tonumber(t[2])/1000000
        for i,k in ipairs(KEYS) do
          redis.call('ZREMRANGEBYSCORE',k,'-inf',now)
          if redis.call('ZCARD',k) >= tonumber(ARGV[i+2]) then return 0 end
        end
        for _,k in ipairs(KEYS) do
          redis.call('ZADD',k,now+tonumber(ARGV[2]),ARGV[1])
          local last=redis.call('ZREVRANGE',k,0,0,'WITHSCORES')
          redis.call('EXPIRE',k,math.max(tonumber(ARGV[2])*2,math.ceil(tonumber(last[2])-now)+1))
        end
        return 1
        """
        return bool(
            await self._redis.eval(script, len(self.keys), *self.keys, owner, ttl_s, *self.limits)
        )

    async def renew_pool_slot(self, key, owner, ttl_s):
        script = """
        local t = redis.call('TIME'); local now = tonumber(t[1]) + tonumber(t[2])/1000000
        for _,k in ipairs(KEYS) do
          local expiry = redis.call('ZSCORE',k,ARGV[1])
          if not expiry or tonumber(expiry) <= now then return 0 end
        end
        for _,k in ipairs(KEYS) do
          redis.call('ZADD',k,now+tonumber(ARGV[2]),ARGV[1]); local last=redis.call('ZREVRANGE',k,0,0,'WITHSCORES')
          redis.call('EXPIRE',k,math.max(tonumber(ARGV[2])*2,math.ceil(tonumber(last[2])-now)+1))
        end
        return 1
        """
        return bool(await self._redis.eval(script, len(self.keys), *self.keys, owner, ttl_s))

    async def release_pool_slot(self, key, owner):
        return bool(
            await self._redis.eval(
                "for _,k in ipairs(KEYS) do redis.call('ZREM',k,ARGV[1]) end return 1",
                len(self.keys),
                *self.keys,
                owner,
            )
        )


class NavigationPacer:
    def __init__(self, cache, *, interval_s=1.0, cooldown_s=60.0):
        if interval_s <= 0 or cooldown_s <= 0:
            raise ValueError("positive navigation pacing required")
        self.cache, self.interval_s, self.cooldown_s = cache, interval_s, cooldown_s
        self.key = "ingestion:linkedin:navigation"

    async def acquire(self):
        # Redis TIME avoids clock skew. Never pre-reserve an unbounded queue of starts.
        script = """
        local t=redis.call('TIME'); local now=tonumber(t[1])+tonumber(t[2])/1000000
        local next=tonumber(redis.call('GET',KEYS[1]) or '0')
        if next > now then return tostring(next-now) end
        redis.call('SET',KEYS[1],now+tonumber(ARGV[1]),'PX',math.ceil(tonumber(ARGV[1])*1000)+1000)
        return 0
        """
        while True:
            try:
                delay = float(await self.cache._redis.eval(script, 1, self.key, self.interval_s))
            except Exception as exc:
                raise InfrastructureUnavailable("navigation_redis_unavailable") from exc
            if delay <= 0:
                return
            if delay > max(2.0, self.interval_s * 2):
                raise DeferredMessage(
                    delay + 1, "linkedin_navigation_cooldown", pause_consumer=True
                )
            await asyncio.sleep(min(delay, 1.0))

    async def cooldown(self, seconds=None):
        seconds = max(self.cooldown_s, seconds or 0)
        script = """
        local t=redis.call('TIME'); local now=tonumber(t[1])+tonumber(t[2])/1000000
        local next=math.max(tonumber(redis.call('GET',KEYS[1]) or '0'),now+tonumber(ARGV[1]))
        redis.call('SET',KEYS[1],next,'PX',math.ceil((next-now)*1000)+1000)
        return 1
        """
        try:
            await self.cache._redis.eval(script, 1, self.key, seconds)
        except Exception as exc:
            raise InfrastructureUnavailable("navigation_redis_unavailable") from exc


class IngestionBrowser:
    def __init__(
        self, manager, *, acquisition_timeout_s=45, navigation_timeout_ms=30000, pacer=None
    ):
        self.manager = manager
        self.acquisition_timeout_s = acquisition_timeout_s
        self.navigation_timeout_ms = navigation_timeout_ms
        self.pacer = pacer

    @asynccontextmanager
    async def session(self):
        # Includes admission, handshake, navigation and rendering, then bounded cleanup.
        async with asyncio.timeout(self.acquisition_timeout_s):
            async with self.manager.acquire() as session:
                yield session

    async def render(self, url, *, validate_navigation=None, ready_selector=None):
        from playwright.async_api import Error as PlaywrightError

        opened = False
        try:
            if self.pacer:
                await self.pacer.acquire()
            async with self.session() as session:
                opened = True
                page = session.page
                navigation_error = None

                async def route_request(route):
                    nonlocal navigation_error
                    request = route.request
                    if (
                        request.is_navigation_request()
                        and request.frame == page.main_frame
                        and validate_navigation
                    ):
                        try:
                            validate_navigation(request.url)
                        except Exception as exc:
                            navigation_error = exc
                            await route.abort()
                            return
                    await route.fallback()

                if validate_navigation:
                    await page.route("**/*", route_request)
                try:
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms
                    )
                except PlaywrightError:
                    if navigation_error:
                        raise navigation_error
                    raise
                if navigation_error:
                    raise navigation_error
                status = response.status if response else 200
                if status == 429:
                    if self.pacer:
                        await self.pacer.cooldown()
                    raise CollectionError("destination_429")
                if status >= 500:
                    raise CollectionError("destination_unavailable")
                if status in {401, 403}:
                    if self.pacer:
                        await self.pacer.cooldown()
                    raise CollectionError("access_blocked")
                if status in {404, 410}:
                    return RenderedPage(await page.content(), page.url, status)
                initial_html = (await page.content()).lower()
                if any(
                    marker in initial_html
                    for marker in (
                        "cf-chl-",
                        "verify you are human",
                        'id="captcha',
                        'class="authwall',
                    )
                ):
                    if self.pacer:
                        await self.pacer.cooldown()
                    raise CollectionError("access_blocked")
                if ready_selector:
                    await page.locator(ready_selector).first.wait_for(
                        state="attached", timeout=10000
                    )
                else:
                    await page.wait_for_function(
                        "() => document.body && document.body.innerText.trim().length >= 200",
                        timeout=10000,
                    )
                html = await page.content()
                return RenderedPage(html, page.url, status)
        except (AdmissionUnavailable, CollectionError):
            raise
        except TimeoutError as exc:
            raise CollectionError("render_timeout") from exc
        except PlaywrightError as exc:
            # Connection-stage failures are infrastructure; destination failures are durable retries.
            if not opened:
                raise InfrastructureUnavailable("browserless_unavailable") from exc
            raise CollectionError("browser_navigation_failed") from exc


@asynccontextmanager
async def ingestion_browser(flow):
    config = BrowserConfiguration(
        endpoint=os.environ["BROWSERLESS_ENDPOINT"],
        token=os.environ["BROWSERLESS_TOKEN"],
        connect_timeout_ms=int(os.getenv("BROWSER_CONNECT_TIMEOUT_MS", "10000")),
        session_timeout_s=int(os.getenv("BROWSERLESS_SESSION_TIMEOUT_S", "60")),
        cleanup_timeout_s=int(os.getenv("BROWSER_CLEANUP_TIMEOUT_S", "10")),
        verify_remote=True,
    )
    cache = IngestionBudget(
        os.environ["CACHE_URL"],
        flow=flow,
        global_limit=int(os.getenv("BROWSER_GLOBAL_LIMIT", "12")),
        ingestion_limit=int(os.getenv("BROWSER_INGESTION_LIMIT", "8")),
        flow_limit=int(os.getenv("BROWSER_FLOW_LIMIT", "6" if flow == "linkedin" else "2")),
    )
    admission = SlotAdmission(
        cache,
        key=cache.keys[0],
        limit=cache.limits[0],
        ttl_s=90,
        acquire_timeout_s=5,
        max_browser_session_s=config.session_timeout_s,
    )
    manager = BrowserManager(config, admission=admission)
    message_s = float(os.getenv("WORKER_MESSAGE_TIMEOUT_S", "90"))
    drain_s = float(os.getenv("WORKER_SHUTDOWN_TIMEOUT_S", "110"))
    acquisition_s = float(os.getenv("BROWSER_ACQUISITION_TIMEOUT_S", "45"))
    if (
        acquisition_s <= 0
        or acquisition_s + config.cleanup_timeout_s > config.session_timeout_s
        or acquisition_s + config.cleanup_timeout_s > message_s
        or message_s + config.cleanup_timeout_s > min(drain_s, 120)
    ):
        raise ValueError("inconsistent_ingestion_deadlines")
    await cache.connect()
    try:
        # Each acquire verifies the remote capacity. Start the consumer even
        # during outages, so durable infrastructure backoff owns recovery.
        await manager.start()
        yield IngestionBrowser(
            manager,
            pacer=NavigationPacer(
                cache,
                interval_s=float(os.getenv("LINKEDIN_NAVIGATION_INTERVAL_S", "1")),
                cooldown_s=float(os.getenv("LINKEDIN_COOLDOWN_S", "60")),
            )
            if flow == "linkedin"
            else None,
            acquisition_timeout_s=float(os.getenv("BROWSER_ACQUISITION_TIMEOUT_S", "45")),
            navigation_timeout_ms=int(os.getenv("BROWSER_NAVIGATION_TIMEOUT_MS", "30000")),
        )
    finally:
        await manager.close()
        await cache.close()
