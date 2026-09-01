"""Eligibility engine: structural filter + entity matching + keyword scoring.

Implements the CLOSED policy for evaluating candidate target profiles against a job.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from scaffold.constants.schema_enums import EmploymentType, ExperienceLevel, RemoteType
from scaffold.models import (
    CandidateTargetProfile,
    CandidateTargetProfileKeyword,
    Job,
    JobRoutingKeyword,
)
from scaffold.repositories import (
    candidate_target_profile_entity_repository,
    job_professional_entity_repository,
    professional_entity_hierarchy_relation_repository,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EligibilityScore:
    """Result of evaluating a single profile against a job."""

    approved: bool
    routing_score: float
    matched_include_keywords: list[str]
    matched_exclude_keywords: list[str]
    filters: dict[str, str]
    score_components: dict[str, float]


@dataclass(frozen=True)
class EntityMatchResult:
    """Result of entity-based overlap evaluation."""

    approved: bool
    entity_score: float
    direct_overlap_ids: list[int]
    hierarchy_overlap_ids: list[int]
    total_job_entities: int
    total_candidate_entities: int


@dataclass
class ProfileWithKeywords:
    """A target profile bundled with its keywords."""

    profile: CandidateTargetProfile
    keywords: list[CandidateTargetProfileKeyword] = field(default_factory=list)


def _rejected(filters: dict[str, str]) -> EligibilityScore:
    return EligibilityScore(
        approved=False,
        routing_score=0.0,
        matched_include_keywords=[],
        matched_exclude_keywords=[],
        filters=filters,
        score_components={},
    )


async def evaluate_entity_overlap(
    session: AsyncSession,
    job_id: int,
    candidate_target_profile_id: int,
) -> EntityMatchResult:
    """Calcula overlap de entidades profissionais entre vaga e perfil do candidato.

    - Overlap direto (mesma entity_id): +40 pts por entidade (cap 100)
    - Overlap hierárquico (vaga entity é child de candidate entity, depth=1): +20 pts (cap 100)
    - Score final = min(100, direct_score + hierarchy_score)
    """
    # 1. Carregar entity_ids da vaga
    job_entities = await job_professional_entity_repository.list_by_job_id(session, job_id)
    job_entity_ids = {je.entity_id for je in job_entities}

    if not job_entity_ids:
        return EntityMatchResult(
            approved=False,
            entity_score=0.0,
            direct_overlap_ids=[],
            hierarchy_overlap_ids=[],
            total_job_entities=0,
            total_candidate_entities=0,
        )

    # 2. Carregar entity_ids do candidato
    candidate_entity_ids_list = (
        await candidate_target_profile_entity_repository.get_entity_ids_by_target_profile_id(
            session, candidate_target_profile_id
        )
    )
    candidate_entity_ids = set(candidate_entity_ids_list)

    if not candidate_entity_ids:
        return EntityMatchResult(
            approved=False,
            entity_score=0.0,
            direct_overlap_ids=[],
            hierarchy_overlap_ids=[],
            total_job_entities=len(job_entity_ids),
            total_candidate_entities=0,
        )

    # 3. Overlap direto
    direct_overlap = job_entity_ids & candidate_entity_ids
    direct_score = min(len(direct_overlap) * 40.0, 100.0)

    # 4. Overlap hierárquico (se vaga entity é child de candidate entity)
    hierarchy_overlap: set[int] = set()
    if direct_score < 100.0:
        for job_eid in job_entity_ids - direct_overlap:
            parents = await professional_entity_hierarchy_relation_repository.list_parents_of_child(
                session, job_eid, relation_type=None
            )
            parent_ids = {p.parent_entity_id for p in parents if p.depth == 1}
            matched_parents = parent_ids & candidate_entity_ids
            if matched_parents:
                hierarchy_overlap.add(job_eid)

    hierarchy_score = min(len(hierarchy_overlap) * 20.0, 100.0 - direct_score)
    total_score = min(direct_score + hierarchy_score, 100.0)

    approved = total_score >= 40.0

    return EntityMatchResult(
        approved=approved,
        entity_score=total_score,
        direct_overlap_ids=list(direct_overlap),
        hierarchy_overlap_ids=list(hierarchy_overlap),
        total_job_entities=len(job_entity_ids),
        total_candidate_entities=len(candidate_entity_ids),
    )


async def evaluate_profile(
    session: AsyncSession,
    job: Job,
    job_keywords: list[JobRoutingKeyword],
    profile_with_keywords: ProfileWithKeywords,
) -> EligibilityScore:
    """Evaluate a single candidate target profile against a job.

    Returns EligibilityScore with approval status and routing_score.
    """
    profile = profile_with_keywords.profile
    profile_keywords = profile_with_keywords.keywords
    filters: dict[str, str] = {}
    score_components: dict[str, float] = {}

    # --- Structural filters (ALL must pass) ---

    # Country filter
    if (
        profile.target_country is not None
        and profile.target_country != ""
        and job.country is not None
        and job.country != ""
        and profile.target_country.lower() != job.country.lower()
    ):
        filters["country"] = "rejected"
        return _rejected(filters)
    filters["country"] = "pass"

    # Remote preference filter
    if (
        profile.remote_preference != RemoteType.UNKNOWN
        and job.remote_type != RemoteType.UNKNOWN
        and profile.remote_preference != job.remote_type
    ):
        filters["remote"] = "rejected"
        return _rejected(filters)
    filters["remote"] = "pass"

    # Employment preference filter
    if (
        profile.employment_preference != EmploymentType.UNKNOWN
        and job.employment_type != EmploymentType.UNKNOWN
        and profile.employment_preference != job.employment_type
    ):
        filters["employment"] = "rejected"
        return _rejected(filters)
    filters["employment"] = "pass"

    # Experience level filter
    if (
        profile.experience_level != ExperienceLevel.UNKNOWN
        and job.experience_level != ExperienceLevel.UNKNOWN
        and profile.experience_level != job.experience_level
    ):
        filters["experience"] = "rejected"
        return _rejected(filters)
    filters["experience"] = "pass"

    # Salary filter: if job.salary_max exists, require job.salary_max >= profile.min_salary
    if (
        job.salary_max is not None
        and profile.min_salary is not None
        and float(job.salary_max) < float(profile.min_salary)
    ):
        filters["salary"] = "rejected"
        return _rejected(filters)
    filters["salary"] = "pass"

    # --- Entity-based matching ---
    entity_result = await evaluate_entity_overlap(session, job.id, profile.id)

    # --- Keyword scoring ---
    job_keyword_set = {kw.keyword.lower() for kw in job_keywords}

    include_keywords: list[str] = []
    exclude_keywords: list[str] = []

    for pk in profile_keywords:
        if not pk.active:
            continue
        policy = pk.match_policy.lower() if pk.match_policy else ""
        if policy == "include":
            include_keywords.append(pk.keyword.lower())
        elif policy == "exclude":
            exclude_keywords.append(pk.keyword.lower())
        else:
            logger.warning(
                "unknown match_policy=%r for keyword=%r profile_id=%s; ignoring",
                pk.match_policy,
                pk.keyword,
                profile.id,
            )

    # Check for exclude keyword matches → immediate rejection (even with entity match)
    matched_exclude = [kw for kw in exclude_keywords if kw in job_keyword_set]
    if matched_exclude:
        return EligibilityScore(
            approved=False,
            routing_score=0.0,
            matched_include_keywords=[],
            matched_exclude_keywords=matched_exclude,
            filters=filters,
            score_components=score_components,
        )

    # Calculate include keyword matches
    matched_include = [kw for kw in include_keywords if kw in job_keyword_set]

    # Calculate keyword score
    keyword_score = 0.0

    if matched_include:
        # +30 for at least 1 include keyword in common
        keyword_score += 30.0
        score_components["first_include_match"] = 30.0

        # +10 per additional include keyword, capped at +40
        additional = len(matched_include) - 1
        additional_bonus = min(additional * 10.0, 40.0)
        keyword_score += additional_bonus
        score_components["additional_include_matches"] = additional_bonus

        # +10 if remote_preference matches exactly
        if (
            profile.remote_preference != RemoteType.UNKNOWN
            and job.remote_type != RemoteType.UNKNOWN
            and profile.remote_preference == job.remote_type
        ):
            keyword_score += 10.0
            score_components["remote_match"] = 10.0

        # +10 if employment_preference matches exactly
        if (
            profile.employment_preference != EmploymentType.UNKNOWN
            and job.employment_type != EmploymentType.UNKNOWN
            and profile.employment_preference == job.employment_type
        ):
            keyword_score += 10.0
            score_components["employment_match"] = 10.0

        # +10 if experience_level matches exactly
        if (
            profile.experience_level != ExperienceLevel.UNKNOWN
            and job.experience_level != ExperienceLevel.UNKNOWN
            and profile.experience_level == job.experience_level
        ):
            keyword_score += 10.0
            score_components["experience_match"] = 10.0

        # +10 if target_country matches exactly
        if (
            profile.target_country is not None
            and profile.target_country != ""
            and job.country is not None
            and job.country != ""
            and profile.target_country.lower() == job.country.lower()
        ):
            keyword_score += 10.0
            score_components["country_match"] = 10.0

        # Cap keyword score at 100
        keyword_score = min(keyword_score, 100.0)

    # --- Combine scores ---
    keyword_approved = keyword_score >= 40.0

    if entity_result.approved or keyword_approved:
        final_score = max(entity_result.entity_score, keyword_score)

        # Adicionar entity info nos score_components
        if entity_result.entity_score > 0:
            score_components["entity_direct_overlap"] = len(entity_result.direct_overlap_ids) * 40.0
            score_components["entity_hierarchy_overlap"] = (
                len(entity_result.hierarchy_overlap_ids) * 20.0
            )
            score_components["entity_score"] = entity_result.entity_score

        approved = final_score >= 40.0

        return EligibilityScore(
            approved=approved,
            routing_score=min(final_score, 100.0),
            matched_include_keywords=matched_include,
            matched_exclude_keywords=[],
            filters=filters,
            score_components=score_components,
        )
    else:
        # Nem entity nem keyword aprovaram
        return EligibilityScore(
            approved=False,
            routing_score=max(entity_result.entity_score, keyword_score),
            matched_include_keywords=matched_include,
            matched_exclude_keywords=matched_exclude,
            filters=filters,
            score_components=score_components,
        )
