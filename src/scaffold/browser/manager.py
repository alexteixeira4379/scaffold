"""One private Browserless connection and context per application execution."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from scaffold.messaging.processing import InfrastructureUnavailable
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class BrowserlessLogFilter(logging.Filter):
    """Management URLs must never write the Browserless token to logs."""

    def filter(self, record):
        record.msg = re.sub(r"(?i)(token=)[^&\s\"']+", r"\1<redacted>", record.getMessage())
        record.args = ()
        return True


logging.getLogger("httpx").addFilter(BrowserlessLogFilter())

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrowserConfiguration:
    endpoint: str
    token: str = field(repr=False)
    protocol: Literal["cdp", "playwright"] = "cdp"
    connect_timeout_ms: int = 30000
    session_timeout_s: int = 300
    cleanup_timeout_s: int = 10
    verify_remote: bool = False

    def __post_init__(self) -> None:
        parsed = urlsplit(self.endpoint)
        if (
            parsed.scheme not in {"ws", "wss"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
        ):
            raise ValueError("BROWSERLESS_ENDPOINT must be a ws(s) URL without credentials")
        if any(key.casefold() in {"token", "timeout", "ttl"} for key, _ in parse_qsl(parsed.query)):
            raise ValueError("Browserless token and session timeout must be configured separately")
        if (
            not self.token
            or self.connect_timeout_ms <= 0
            or self.session_timeout_s <= 0
            or self.cleanup_timeout_s <= 0
        ):
            raise ValueError("Browserless token and positive timeout are required")
        if self.protocol not in {"cdp", "playwright"}:
            raise ValueError("unsupported Browserless protocol")

    @classmethod
    def from_env(cls) -> BrowserConfiguration:
        return cls(
            endpoint=os.environ["BROWSERLESS_ENDPOINT"],
            token=os.environ["BROWSERLESS_TOKEN"],
            protocol=os.getenv("BROWSER_BACKEND", "cdp"),
            connect_timeout_ms=int(os.getenv("BROWSER_CONNECT_TIMEOUT_MS", "30000")),
            session_timeout_s=int(os.getenv("BROWSERLESS_SESSION_TIMEOUT_S", "300")),
            cleanup_timeout_s=int(os.getenv("BROWSER_CLEANUP_TIMEOUT_S", "10")),
            verify_remote=True,
        )

    @classmethod
    def from_profile_env(cls) -> BrowserConfiguration:
        return cls(
            endpoint=os.environ["LINKEDIN_BROWSERLESS_ENDPOINT"],
            token=os.environ["LINKEDIN_BROWSERLESS_TOKEN"],
            protocol="cdp",
            session_timeout_s=int(os.getenv("LINKEDIN_PROFILE_SESSION_TIMEOUT_S", "300")),
            cleanup_timeout_s=30,
            verify_remote=False,
        )

    def connection_url(self) -> str:
        parts = urlsplit(self.endpoint)
        query = urlencode(
            [
                *parse_qsl(parts.query),
                ("token", self.token),
                ("timeout", str(self.session_timeout_s * 1000)),
            ]
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    def management_url(self, path: str) -> str:
        parts = urlsplit(self.endpoint)
        scheme = "https" if parts.scheme == "wss" else "http"
        return urlunsplit((scheme, parts.netloc, path, urlencode({"token": self.token}), ""))


def validate_operational_deadlines(
    config: BrowserConfiguration,
    *,
    message_timeout_s: float,
    drain_timeout_s: float,
    lease_seconds: float,
    heartbeat_s: float = 30,
) -> None:
    """Validate the deadlines used by both queue executors before consuming work."""
    if (
        message_timeout_s <= 0
        or drain_timeout_s < message_timeout_s + config.cleanup_timeout_s
        or config.session_timeout_s < message_timeout_s + config.cleanup_timeout_s
        or lease_seconds < message_timeout_s + config.cleanup_timeout_s
        or heartbeat_s <= 0
        or heartbeat_s * 2 >= lease_seconds
    ):
        raise ValueError("inconsistent_application_browser_lease_or_drain_deadlines")


@dataclass
class BrowserSession:
    browser: object
    context: object
    page: object
    profile_lease: object | None = None
    profile_deadline: float | None = None
    remote_closed: bool = False

    @property
    def deadline_monotonic(self):
        return self.profile_deadline


class BrowserManager:
    def __init__(self, config: BrowserConfiguration, *, admission=None):
        if admission is not None and admission.max_browser_session_s is not None:
            if admission.max_browser_session_s != config.session_timeout_s:
                raise ValueError("admission_and_remote_session_timeout_disagree")
            if admission.ttl_s < config.session_timeout_s + config.cleanup_timeout_s + 20:
                raise ValueError("slot_ttl_must_cover_session_cleanup_and_margin")
        self.config = config
        self.admission = admission
        self._driver = None

    async def start(self):
        from playwright.async_api import async_playwright

        if self._driver is None:
            self._driver = await async_playwright().start()

    async def close(self):
        driver, self._driver = self._driver, None
        if driver is not None:
            await asyncio.wait_for(driver.stop(), self.config.cleanup_timeout_s)

    @asynccontextmanager
    async def acquire(
        self, *, cookies: list[dict] | None = None, context_options: dict | None = None
    ) -> AsyncIterator[BrowserSession]:
        if self.config.verify_remote:
            await self.verify_remote_configuration()
        if self.admission is not None:
            async with self.admission.lease() as slot:  # noqa: SIM117 - lease must wrap the browser connection
                async with self._connect(
                    cookies=cookies, context_options=context_options, slot=slot
                ) as session:
                    yield session
        else:
            async with self._connect(cookies=cookies, context_options=context_options) as session:
                yield session

    async def verify_remote_configuration(self) -> None:
        """Fail closed when the actual server can exceed the shared Redis budget."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.config.connect_timeout_ms / 1000) as client:
                response = await client.get(self.config.management_url("/config"))
                response.raise_for_status()
                remote = response.json()
        except (httpx.HTTPError, ValueError):
            raise InfrastructureUnavailable("browserless_config_unverifiable") from None
        if not isinstance(remote, dict) or not isinstance(remote.get("timeout"), int):
            raise InfrastructureUnavailable("browserless_config_unverifiable")
        if remote["timeout"] == -1:
            raise ValueError("browserless_server_timeout_unbounded")
        if self.admission is not None and (
            remote.get("concurrent") != self.admission.limit or remote.get("queued") != 0
        ):
            raise InfrastructureUnavailable(
                "browserless_capacity_must_match_admission_with_zero_queue"
            )

    @asynccontextmanager
    async def _connect(
        self, *, cookies=None, context_options=None, slot=None
    ) -> AsyncIterator[BrowserSession]:
        from playwright.async_api import async_playwright

        driver = self._driver or await async_playwright().start()
        browser = context = None
        remote_id = None
        try:
            # A failed handshake can still have created a remote Chromium.
            if slot is not None:
                slot.remote_opened = True
            if self.config.protocol == "cdp":
                browser = await driver.chromium.connect_over_cdp(
                    self.config.connection_url(), timeout=self.config.connect_timeout_ms
                )
            elif self.config.protocol == "playwright":
                browser = await driver.chromium.connect(
                    self.config.connection_url(), timeout=self.config.connect_timeout_ms
                )
            else:
                raise ValueError("unsupported Browserless protocol")
            context = await browser.new_context(**(context_options or {}))
            if cookies:
                await context.add_cookies(cookies)
            page = await context.new_page()
            if self.config.verify_remote:
                cdp = await context.new_cdp_session(page)
                target = (await cdp.send("Target.getTargetInfo"))["targetInfo"]["targetId"]
                await cdp.detach()
                import httpx

                async with httpx.AsyncClient(
                    timeout=self.config.connect_timeout_ms / 1000
                ) as client:
                    response = await client.get(self.config.management_url("/sessions"))
                    response.raise_for_status()
                    remote_id = next(
                        (
                            item.get("browserId")
                            for item in response.json()
                            if item.get("id") == target
                        ),
                        None,
                    )
                if not remote_id:
                    raise InfrastructureUnavailable("browserless_session_unverifiable")
            yield BrowserSession(browser, context, page)
        finally:
            # One total cleanup budget, including cancellation and driver shutdown.
            async def cleanup():
                try:
                    if context is not None:
                        try:
                            await context.close()
                        except Exception:
                            logger.warning("Browserless context cleanup failed")
                    if browser is not None:
                        await browser.close()
                        if self.config.verify_remote:
                            if not remote_id:
                                raise InfrastructureUnavailable("browserless_close_unverifiable")
                            import httpx

                            async with httpx.AsyncClient(
                                timeout=self.config.cleanup_timeout_s
                            ) as client:
                                while True:
                                    response = await client.get(
                                        self.config.management_url("/sessions")
                                    )
                                    response.raise_for_status()
                                    if not any(
                                        item.get("browserId") == remote_id
                                        or item.get("id") == remote_id
                                        for item in response.json()
                                    ):
                                        break
                                    await asyncio.sleep(0.1)
                        if slot is not None:
                            slot.remote_closed = True
                finally:
                    if self._driver is None:
                        await driver.stop()

            task = asyncio.create_task(cleanup())
            try:
                await asyncio.wait_for(asyncio.shield(task), self.config.cleanup_timeout_s)
            except asyncio.CancelledError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise
            except Exception:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                logger.warning("Browserless cleanup unverified; retaining admission until expiry")
