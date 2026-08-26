"""Profile classification service.

Loads professional entities and aliases, matches them against candidate
target profile name + keywords, and persists candidate_target_profile_entities
associations.

Follows the same n-gram matching logic as the job-taxonomy-worker's
taxonomy_classifier.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from scaffold.constants.schema_enums import ProfessionalEntityType
from scaffold.models.candidate.candidate_target_profile_entities import (
    CandidateTargetProfileEntity,
)
from scaffold.models.candidate.candidate_target_profile_keywords import (
    CandidateTargetProfileKeyword,
)
from scaffold.professional.normalization import normalize_text
from scaffold.repositories import (
    candidate_target_profile_entity_repository,
    professional_entity_alias_repository,
    professional_entity_repository,
)

logger = logging.getLogger(__name__)

# Entity types we classify against
_CLASSIFIABLE_TYPES: tuple[ProfessionalEntityType, ...] = (
    ProfessionalEntityType.OCCUPATION,
    ProfessionalEntityType.SKILL,
    ProfessionalEntityType.TECHNOLOGY,
    ProfessionalEntityType.TOOL,
    ProfessionalEntityType.JOB_TITLE,
    ProfessionalEntityType.DOMAIN,
)

# Module-level cache for entity lookup
_entity_lookup_cache: dict[str, list[int]] | None = None


@dataclass
class ProfileClassificationResult:
    """Result of classification for a candidate target profile."""

    target_profile_id: int
    entities_created: list[CandidateTargetProfileEntity] = field(default_factory=list)
    total_keywords_processed: int = 0
    match_rate: float = 0.0


def invalidate_cache() -> None:
    """Clear the entity lookup cache. Useful for tests."""
    global _entity_lookup_cache  # noqa: PLW0603
    _entity_lookup_cache = None


async def _get_entity_lookup(session: AsyncSession) -> dict[str, list[int]]:
    """Return the cached entity lookup, populating it on first call."""
    global _entity_lookup_cache  # noqa: PLW0603
    if _entity_lookup_cache is not None:
        return _entity_lookup_cache
    _entity_lookup_cache = await _load_entity_lookup(session)
    return _entity_lookup_cache


async def _load_entity_lookup(session: AsyncSession) -> dict[str, list[int]]:
    """Build a normalized_name -> [entity_id] lookup from active entities and aliases."""
    lookup: dict[str, list[int]] = {}

    for entity_type in _CLASSIFIABLE_TYPES:
        entities = await professional_entity_repository.list_active_by_entity_type(
            session, entity_type.value
        )
        for entity in entities:
            # Index by canonical_name
            key = normalize_text(entity.canonical_name)
            if key:
                lookup.setdefault(key, []).append(entity.id)
            # Also index by normalized_name if different
            if entity.normalized_name and entity.normalized_name != key:
                norm = normalize_text(entity.normalized_name)
                if norm:
                    lookup.setdefault(norm, []).append(entity.id)
            # Load aliases for this entity
            aliases = await professional_entity_alias_repository.list_by_entity_id(
                session, entity.id
            )
            for alias in aliases:
                alias_key = normalize_text(alias.normalized_alias)
                if alias_key:
                    lookup.setdefault(alias_key, []).append(entity.id)

    return lookup


def _match_text_against_lookup(
    text: str,
    lookup: dict[str, list[int]],
) -> list[tuple[int, str, float]]:
    """Match text against the entity lookup using n-grams of 1 to 4 tokens.

    Returns list of (entity_id, matched_text, confidence).
    """
    if not text or not text.strip():
        return []

    normalized = normalize_text(text)
    tokens = normalized.split()
    matches: list[tuple[int, str, float]] = []
    seen_entities: set[int] = set()

    max_ngram = min(4, len(tokens))
    for n in range(max_ngram, 0, -1):
        for i in range(len(tokens) - n + 1):
            ngram = " ".join(tokens[i : i + n])
            if ngram in lookup:
                for entity_id in lookup[ngram]:
                    if entity_id not in seen_entities:
                        seen_entities.add(entity_id)
                        confidence = n / max_ngram if max_ngram > 0 else 1.0
                        matches.append((entity_id, ngram, min(confidence, 1.0)))

    return matches


async def classify_candidate_profile(
    session: AsyncSession,
    candidate_target_profile_id: int,
    keywords: list[CandidateTargetProfileKeyword],
    profile_name: str,
) -> ProfileClassificationResult:
    """Classify a candidate target profile against professional entities.

    Matches the profile name and active include-keywords against the entity
    lookup. Persists results idempotently (deletes existing, inserts new).
    """
    lookup = await _get_entity_lookup(session)

    all_entities: list[CandidateTargetProfileEntity] = []
    seen_entity_ids: set[int] = set()

    # 1. Match against profile name (weight 2.0, relevance='primary')
    profile_name_matches = _match_text_against_lookup(profile_name, lookup)
    for entity_id, matched_text, confidence in profile_name_matches:
        if entity_id not in seen_entity_ids:
            seen_entity_ids.add(entity_id)
            all_entities.append(
                CandidateTargetProfileEntity(
                    candidate_target_profile_id=candidate_target_profile_id,
                    professional_entity_id=entity_id,
                    relevance="primary",
                    confidence=Decimal(str(round(confidence, 4))),
                    source="keyword_match",
                    matched_text=matched_text[:512],
                )
            )

    # 2. Match against include keywords (weight 1.5, relevance='secondary')
    active_include_keywords = [
        kw
        for kw in keywords
        if kw.match_policy == "include" and kw.active is True
    ]

    for kw in active_include_keywords:
        kw_matches = _match_text_against_lookup(kw.keyword, lookup)
        for entity_id, matched_text, confidence in kw_matches:
            if entity_id not in seen_entity_ids:
                seen_entity_ids.add(entity_id)
                all_entities.append(
                    CandidateTargetProfileEntity(
                        candidate_target_profile_id=candidate_target_profile_id,
                        professional_entity_id=entity_id,
                        relevance="secondary",
                        confidence=Decimal(str(round(confidence, 4))),
                        source="keyword_match",
                        matched_text=matched_text[:512],
                    )
                )

    # 3. Persist idempotently: delete existing, insert new
    await candidate_target_profile_entity_repository.delete_by_target_profile_id(
        session, candidate_target_profile_id
    )

    if all_entities:
        await candidate_target_profile_entity_repository.add_all(session, all_entities)

    # 4. Calculate match rate
    total_processed = len(active_include_keywords)
    match_rate = len(all_entities) / max(1, total_processed)

    return ProfileClassificationResult(
        target_profile_id=candidate_target_profile_id,
        entities_created=all_entities,
        total_keywords_processed=total_processed,
        match_rate=match_rate,
    )
