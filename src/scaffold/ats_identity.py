"""Shared identity contract for every writer of the ATS source registry."""

import hashlib
import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlsplit

PROVIDERS = {
    "greenhouse": "job-boards.greenhouse.io",
    "ashby": "jobs.ashbyhq.com",
    "gupy": "gupy.io",
    "inhire": "inhire.app",
    "teamtailor": "teamtailor.com",
    "quickin": "jobs.quickin.io",
    "recruitee": "recruitee.com",
    "smartrecruiters": "careers.smartrecruiters.com",
}


@dataclass(frozen=True)
class Identity:
    provider: str
    tenant: str
    region: str = ""

    @property
    def key(self):
        return json.dumps(
            [self.provider, self.tenant, self.region], separators=(",", ":"), ensure_ascii=False
        )

    @property
    def digest(self):
        return hashlib.sha256(self.key.encode()).hexdigest()

    @property
    def url(self):
        if self.provider in {"gupy", "inhire", "recruitee", "teamtailor"}:
            return f"https://{self.tenant}.{PROVIDERS[self.provider]}/" + (
                "vagas" if self.provider == "inhire" else ""
            )
        host = PROVIDERS[self.provider]
        return f"https://{host}/{quote(self.tenant, safe='')}"


def identify(url):
    u = urlsplit(url)
    if (
        u.scheme not in {"https", "http"}
        or not u.hostname
        or u.username
        or u.password
        or u.port not in {None, 80, 443}
    ):
        raise ValueError("invalid_url")
    host, parts = u.hostname.lower(), [unquote(p) for p in u.path.split("/") if p]
    provider, tenant, region = "", "", ""
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io", "boards-api.greenhouse.io"}:
        provider = "greenhouse"
        tenant = (
            parts[2]
            if len(parts) >= 3 and parts[:2] == ["v1", "boards"]
            else parse_qs(u.query).get("for", [""])[0]
            if parts[:1] == ["embed"]
            else parts[0]
            if parts
            else ""
        )
    elif (
        host == "api.ashbyhq.com" and parts[:2] == ["posting-api", "job-board"] and len(parts) >= 3
    ):
        provider, tenant = "ashby", parts[2]
    elif host == "api.smartrecruiters.com" and parts[:2] == ["v1", "companies"] and len(parts) >= 3:
        provider, tenant = "smartrecruiters", parts[2]
    elif host == "jobs.quickin.io":
        provider, tenant = "quickin", parts[0] if parts else ""
    elif host == "jobs.ashbyhq.com":
        provider, tenant = "ashby", parts[0] if parts else ""
    elif host in {"careers.smartrecruiters.com", "jobs.smartrecruiters.com"}:
        provider, tenant = "smartrecruiters", parts[0] if parts else ""
    else:
        for code in ("gupy", "inhire", "recruitee", "teamtailor"):
            suffix = "." + PROVIDERS[code]
            if host.endswith(suffix) and "." not in host[: -len(suffix)]:
                provider, tenant = code, host[: -len(suffix)]
    if not provider:
        return None
    if provider in {"gupy", "inhire", "recruitee", "teamtailor"} and not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,62}", tenant
    ):
        raise ValueError("invalid_tenant")
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._&+@()' -]{0,127}", tenant)
        or tenant.lower() in {"www", "api", "portal", "employability-portal", "embed"}
        or tenant.lower().endswith((".json", ".js", ".css", ".xml"))
    ):
        raise ValueError("invalid_tenant")
    return Identity(provider, tenant, region)
