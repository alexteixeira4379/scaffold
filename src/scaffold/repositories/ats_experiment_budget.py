"""Finite ATS pilot budget, independent of environment and experiment-name changes."""
from datetime import timezone
from urllib.parse import urlsplit, urlunsplit
from sqlalchemy import select
from scaffold.ats_identity import identify
from scaffold.models.ats.ats_discovery_sources import AtsDiscoverySource as Source
from scaffold.models.ats.ats_providers import AtsProvider as Provider

PROVIDERS = {'inhire', 'teamtailor', 'quickin'}
MAX_SOURCES = 100


def canonical(value):
    if not isinstance(value, str):
        raise ValueError('invalid_budget_url')
    p = urlsplit(value)
    identity = identify(value)
    if p.scheme != 'https' or p.port or p.username or p.password or not identity or identity.provider not in PROVIDERS:
        raise ValueError('invalid_budget_url')
    clean = urlunsplit(('https', p.hostname.lower(), p.path.rstrip('/'), '', ''))
    if clean != value:
        raise ValueError('budget_url_must_be_canonical')
    return clean


def proof(value, provider_code, source_url):
    if (not isinstance(value, dict) or not isinstance(value.get('id'), str) or not value['id']
            or type(value.get('candidate_id')) is not int or value['candidate_id'] <= 0):
        raise ValueError('malformed_experiment_budget_proof')
    url = canonical(value.get('url'))
    if identify(url).provider != provider_code or identify(url) != identify(source_url):
        raise ValueError('experiment_budget_source_mismatch')
    return url


async def locked_budget(session):
    # Every reservation/grant takes the same existing provider rows in PK order.
    providers = (await session.scalars(select(Provider).where(Provider.code.in_(PROVIDERS))
                                       .order_by(Provider.id))).all()
    for provider in sorted(providers, key=lambda p: p.id):
        await session.scalar(select(Provider.id).where(Provider.id == provider.id).with_for_update())
    codes = {p.id: p.code for p in providers}
    # Locking read is current under MySQL REPEATABLE READ, even if a caller
    # established an older snapshot before waiting for the provider fences.
    rows = (await session.execute(select(Source.id, Source.ats_provider_id, Source.base_url,
                                         Source.discovery_metadata)
            .where(Source.ats_provider_id.in_(codes)).limit(MAX_SOURCES + 1).with_for_update())).all()
    if len(rows) > MAX_SOURCES:
        raise ValueError('experiment_budget_source_limit_exceeded_100')
    reservations, grants = {}, {}
    for source_id, provider_id, base_url, metadata in rows:
        if metadata is None:
            continue
        if not isinstance(metadata, dict):
            raise ValueError('malformed_experiment_source_metadata')
        old = metadata.get('bounded_experiment')
        if old is not None:
            url = proof(old, codes[provider_id], base_url)
            if old.get('reserved') is not True or not isinstance(old.get('reserved_at'), str) or not old['reserved_at']:
                raise ValueError('malformed_experiment_reservation')
            if url in reservations:
                raise ValueError('duplicate_experiment_reservation')
            reservations[url] = {**old, 'source_id': source_id, 'provider_code': codes[provider_id]}
        grant = metadata.get('bounded_experiment_grant')
        if grant is not None:
            url = proof(grant, codes[provider_id], base_url)
            if (codes[provider_id] != 'teamtailor' or not isinstance(grant.get('grant_id'), str)
                    or not grant['grant_id'] or not isinstance(grant.get('reason'), str) or not grant['reason']
                    or type(grant.get('consumed')) is not bool or not isinstance(grant.get('created_at'), str) or not grant['created_at']
                    or url in grants):
                raise ValueError('malformed_experiment_grant')
            previous = grant.get('previous_urls')
            if not isinstance(previous, list) or len(previous) != 2 or len(set(previous)) != 2:
                raise ValueError('malformed_experiment_grant_prior_urls')
            for prior in previous:
                canonical(prior)
            grants[url] = {**grant, 'source_id': source_id, 'provider_code': codes[provider_id]}
    if len(grants) > 1 or len(set(reservations) | set(grants)) > 3:
        raise ValueError('experiment_global_budget_exceeded')
    for url, grant in grants.items():
        if (set(grant['previous_urls']) != set(reservations) - {url}
                or {reservations[x]['provider_code'] for x in grant['previous_urls']} != {'teamtailor', 'quickin'}
                or any(reservations[x]['candidate_id'] != grant['candidate_id']
                       or reservations[x]['id'] != grant['id'] for x in grant['previous_urls'])
                or grant['consumed'] != (url in reservations)
                or (url in reservations and any(reservations[url][key] != grant[key]
                    for key in ('id', 'candidate_id', 'source_id')))):
            raise ValueError('experiment_grant_history_mismatch')
    for code in PROVIDERS:
        count = sum(r['provider_code'] == code for r in reservations.values())
        allowed = 2 if code == 'teamtailor' and any(g['consumed'] for g in grants.values()) else 1
        if count > allowed:
            raise ValueError('experiment_ungranted_provider_reservations')
    return codes, reservations, grants


async def grant_additional(session, *, source_id, experiment_id, candidate_id, job_url,
                           grant_id, reason, previous_urls, now, apply=False):
    """Allocate the final slot. No publication; plan is default and changes nothing."""
    if (not isinstance(grant_id, str) or not grant_id.strip() or len(grant_id) > 128
            or not isinstance(reason, str) or not reason.strip() or len(reason) > 500
            or not isinstance(previous_urls, list) or len(previous_urls) != 2
            or any(not isinstance(u, str) for u in previous_urls)):
        raise ValueError('invalid_experiment_grant_request')
    url = canonical(job_url)
    prior = {canonical(x) for x in previous_urls}
    codes, reservations, grants = await locked_budget(session)
    source = await session.scalar(select(Source).where(Source.id == source_id).with_for_update())
    if source is None or codes.get(source.ats_provider_id) != 'teamtailor':
        raise ValueError('grant_requires_existing_teamtailor_source')
    proof({'id':experiment_id, 'candidate_id':candidate_id, 'url':url}, 'teamtailor', source.base_url)
    if not source.active or source.qualification_status != 'qualified' or source.collection_state == 'blocked':
        raise ValueError('experiment_grant_source_not_qualified')
    existing = grants.get(url)
    expected = {'grant_id':grant_id, 'id':experiment_id, 'candidate_id':candidate_id,
                'url':url, 'reason':reason, 'previous_urls':sorted(prior)}
    if existing:
        if existing['source_id'] != source.id or any(existing[k] != v for k,v in expected.items()):
            raise ValueError('experiment_grant_changed')
        return {'status':'already_allocated', 'source_id':source.id, 'url':url,
                'allocated_slots':len(set(reservations)|set(grants)), 'consumed':existing['consumed']}
    if (grants or len(prior) != 2 or prior != set(reservations) or url in prior
            or {r['provider_code'] for r in reservations.values()} != {'teamtailor','quickin'}
            or any(r['id'] != experiment_id or r['candidate_id'] != candidate_id for r in reservations.values())):
        raise ValueError('experiment_grant_expected_history_mismatch')
    if source.collection_lease_until and source.collection_lease_until.replace(tzinfo=timezone.utc) > now.replace(tzinfo=timezone.utc):
        raise ValueError('experiment_grant_source_leased')
    if (source.discovery_metadata or {}).get('bounded_experiment'):
        raise ValueError('experiment_grant_requires_unused_source')
    if apply:
        metadata = dict(source.discovery_metadata or {})
        metadata['bounded_experiment_grant'] = {**expected, 'created_at':now.isoformat(), 'consumed':False}
        source.discovery_metadata = metadata
        await session.flush()
    return {'status':'allocated' if apply else 'planned', 'source_id':source.id, 'url':url,
            'allocated_slots':3 if apply else 2, 'consumed':False}
