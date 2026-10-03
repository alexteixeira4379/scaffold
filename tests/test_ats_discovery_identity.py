from types import SimpleNamespace

import pytest

from scaffold.ats_identity import identify
from scaffold.models.ats.ats_discovery_sources import _identity_before_write


def test_shared_writer_derives_identity_from_old_style_source_url():
    source = SimpleNamespace(
        base_url="https://boards.greenhouse.io/Acme/jobs/1",
        qualification_status=None,
        canonical_identity=None,
        canonical_identity_hash=None,
    )
    _identity_before_write(None, None, source)
    assert source.canonical_identity == identify("https://job-boards.greenhouse.io/Acme").key
    assert source.canonical_identity_hash == identify(source.base_url).digest


def test_writer_rejects_silent_identity_change():
    source = SimpleNamespace(
        base_url="https://jobs.ashbyhq.com/Other",
        qualification_status=None,
        canonical_identity=identify("https://jobs.ashbyhq.com/Original").key,
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        _identity_before_write(None, None, source)


def test_ambiguous_legacy_source_stays_untouched():
    source = SimpleNamespace(
        base_url="https://jobs.ashbyhq.com/Same",
        qualification_status="legacy_ambiguous",
        canonical_identity=None,
        canonical_identity_hash=None,
    )
    _identity_before_write(None, None, source)
    assert source.canonical_identity_hash is None


@pytest.mark.parametrize("host", ["jobs.lever.co", "jobs.eu.lever.co", "api.lever.co", "api.eu.lever.co"])
def test_retired_provider_is_not_identified(host):
    assert identify(f"https://{host}/acme/123") is None
