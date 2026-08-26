"""Unit tests for the profile_classifier module.

Tests classification of candidate target profiles against professional entities
using mocked repositories and entity lookup.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scaffold.professional.profile_classifier import (
    ProfileClassificationResult,
    _match_text_against_lookup,
    classify_candidate_profile,
    invalidate_cache,
)


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure cache is clear before and after each test."""
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_lookup() -> dict[str, list[int]]:
    """Simulated entity lookup with known entities."""
    return {
        "python": [1],
        "backend developer": [2],
        "data scientist": [3],
        "machine learning": [4],
        "react": [5],
        "frontend developer": [6],
        "devops": [7],
        "aws": [8],
        "engenheiro de software": [9],
        "desenvolvedor backend": [10],
    }


def _keyword(keyword: str, match_policy: str = "include", active: bool = True) -> MagicMock:
    """Create a mock CandidateTargetProfileKeyword."""
    kw = MagicMock()
    kw.keyword = keyword
    kw.match_policy = match_policy
    kw.active = active
    return kw


# --- Tests: _match_text_against_lookup (pure function) ---


class TestMatchTextAgainstLookup:
    """Tests for the n-gram matching function."""

    def test_single_token_match(self, mock_lookup: dict[str, list[int]]) -> None:
        """Single token 'python' should match entity 1."""
        results = _match_text_against_lookup("python", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 1 in entity_ids

    def test_multi_token_match(self, mock_lookup: dict[str, list[int]]) -> None:
        """Multi-token 'backend developer' should match entity 2."""
        results = _match_text_against_lookup("backend developer", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 2 in entity_ids

    def test_no_match(self, mock_lookup: dict[str, list[int]]) -> None:
        """Text that doesn't match any lookup key returns empty."""
        results = _match_text_against_lookup("nonexistent technology", mock_lookup)
        assert results == []

    def test_empty_text_returns_empty(self, mock_lookup: dict[str, list[int]]) -> None:
        """Empty text returns no matches."""
        results = _match_text_against_lookup("", mock_lookup)
        assert results == []

    def test_whitespace_only_returns_empty(self, mock_lookup: dict[str, list[int]]) -> None:
        """Whitespace-only text returns no matches."""
        results = _match_text_against_lookup("   ", mock_lookup)
        assert results == []

    def test_case_insensitive_matching(self, mock_lookup: dict[str, list[int]]) -> None:
        """Matching should be case-insensitive (via normalize_text)."""
        results = _match_text_against_lookup("Python", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 1 in entity_ids

    def test_extra_whitespace_normalized(self, mock_lookup: dict[str, list[int]]) -> None:
        """Extra whitespace should be collapsed before matching."""
        results = _match_text_against_lookup("  backend   developer  ", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 2 in entity_ids

    def test_confidence_higher_for_longer_ngrams(self, mock_lookup: dict[str, list[int]]) -> None:
        """Longer n-gram matches should have higher confidence."""
        results = _match_text_against_lookup("machine learning engineer", mock_lookup)
        # "machine learning" is 2 tokens out of max 3 → confidence = 2/3
        ml_results = [r for r in results if r[0] == 4]
        assert len(ml_results) == 1
        assert ml_results[0][2] == pytest.approx(2 / 3, abs=0.01)

    def test_deduplicates_entity_ids(self, mock_lookup: dict[str, list[int]]) -> None:
        """Same entity_id should appear only once even if matched by multiple ngrams."""
        # "python" appears in lookup. If text has multiple ways to match, only one result.
        results = _match_text_against_lookup("python python", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert entity_ids.count(1) == 1

    def test_accented_text_matching(self, mock_lookup: dict[str, list[int]]) -> None:
        """Accented characters are preserved in v1 normalization."""
        # "engenheiro de software" is in the lookup
        results = _match_text_against_lookup("Engenheiro de Software", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 9 in entity_ids


# --- Tests: classify_candidate_profile ---


class TestClassifyCandidateProfile:
    """Tests for the main classification function."""

    @pytest.mark.asyncio
    async def test_keywords_matching_entities(self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]) -> None:
        """Keywords that match known entities should produce CandidateTargetProfileEntity records."""
        keywords = [_keyword("python"), _keyword("react")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Backend BR"
            )

        assert isinstance(result, ProfileClassificationResult)
        assert result.target_profile_id == 100
        assert len(result.entities_created) > 0
        # python(1) and react(5) from keywords, plus potential matches from profile_name
        entity_ids = [e.professional_entity_id for e in result.entities_created]
        assert 1 in entity_ids  # python
        assert 5 in entity_ids  # react

    @pytest.mark.asyncio
    async def test_keywords_not_matching_anything(self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]) -> None:
        """Keywords that don't match any entity produce no associations."""
        keywords = [_keyword("cobol"), _keyword("fortran")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Unknown Profile"
            )

        assert result.entities_created == []
        # add_all should NOT be called when there are no entities
        mock_repo.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_keywords(self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]) -> None:
        """Profile with 0 keywords should still try to match against profile_name."""
        keywords: list[MagicMock] = []

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="DevOps Engineer"
            )

        assert result.total_keywords_processed == 0
        # "devops" from profile_name should still match entity 7
        entity_ids = [e.professional_entity_id for e in result.entities_created]
        assert 7 in entity_ids

    @pytest.mark.asyncio
    async def test_empty_keywords_and_no_profile_name_match(
        self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]
    ) -> None:
        """Profile with 0 keywords and no matching profile name results in no entities."""
        keywords: list[MagicMock] = []

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Unknown"
            )

        assert result.entities_created == []

    @pytest.mark.asyncio
    async def test_idempotency_deletes_existing(self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]) -> None:
        """classify_candidate_profile must call delete_by_target_profile_id before inserting."""
        keywords = [_keyword("python")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=3)
            mock_repo.add_all = AsyncMock()

            await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Test"
            )

        mock_repo.delete_by_target_profile_id.assert_awaited_once_with(mock_session, 100)

    @pytest.mark.asyncio
    async def test_relevance_primary_from_profile_name(
        self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]
    ) -> None:
        """Entity matched from profile_name should have relevance='primary'."""
        # "devops" appears in lookup as entity 7
        keywords: list[MagicMock] = []

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="DevOps"
            )

        primary_entities = [e for e in result.entities_created if e.relevance == "primary"]
        assert len(primary_entities) > 0
        assert 7 in [e.professional_entity_id for e in primary_entities]

    @pytest.mark.asyncio
    async def test_relevance_secondary_from_keyword(
        self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]
    ) -> None:
        """Entity matched from keywords should have relevance='secondary'."""
        # Profile name doesn't match anything; keyword "aws" matches entity 8
        keywords = [_keyword("aws")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Unknown"
            )

        secondary_entities = [e for e in result.entities_created if e.relevance == "secondary"]
        assert len(secondary_entities) > 0
        assert 8 in [e.professional_entity_id for e in secondary_entities]

    @pytest.mark.asyncio
    async def test_primary_takes_precedence_over_secondary(
        self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]
    ) -> None:
        """If same entity matches both profile_name and keyword, it should be 'primary' (first match wins)."""
        # "python" in both profile_name and keywords
        keywords = [_keyword("python")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Python Developer"
            )

        # Entity 1 (python) should appear only once, with relevance='primary'
        python_entities = [e for e in result.entities_created if e.professional_entity_id == 1]
        assert len(python_entities) == 1
        assert python_entities[0].relevance == "primary"

    @pytest.mark.asyncio
    async def test_exclude_keywords_ignored(self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]) -> None:
        """Keywords with match_policy='exclude' should not be classified."""
        keywords = [_keyword("python", match_policy="exclude")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Unknown"
            )

        # python should NOT be matched because it's exclude
        entity_ids = [e.professional_entity_id for e in result.entities_created]
        assert 1 not in entity_ids

    @pytest.mark.asyncio
    async def test_inactive_keywords_ignored(self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]) -> None:
        """Inactive keywords should not be classified."""
        keywords = [_keyword("python", active=False)]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Unknown"
            )

        entity_ids = [e.professional_entity_id for e in result.entities_created]
        assert 1 not in entity_ids


class TestCacheInvalidation:
    """Tests for cache behavior."""

    @pytest.mark.asyncio
    async def test_invalidate_cache_clears_lookup(self, mock_session: AsyncMock) -> None:
        """invalidate_cache() should clear the module-level _entity_lookup_cache."""
        import scaffold.professional.profile_classifier as pc

        # Manually set cache
        pc._entity_lookup_cache = {"python": [1]}
        assert pc._entity_lookup_cache is not None

        invalidate_cache()

        assert pc._entity_lookup_cache is None

    @pytest.mark.asyncio
    async def test_cache_populated_on_first_call(self, mock_session: AsyncMock) -> None:
        """First call to _get_entity_lookup should populate cache."""
        import scaffold.professional.profile_classifier as pc

        assert pc._entity_lookup_cache is None

        fake_lookup = {"python": [1]}

        with patch(
            "scaffold.professional.profile_classifier._load_entity_lookup",
            return_value=fake_lookup,
        ) as mock_load:
            from scaffold.professional.profile_classifier import _get_entity_lookup

            result = await _get_entity_lookup(mock_session)
            assert result == fake_lookup
            mock_load.assert_awaited_once()

            # Second call should NOT reload
            result2 = await _get_entity_lookup(mock_session)
            assert result2 == fake_lookup
            assert mock_load.await_count == 1


class TestNormalization:
    """Tests for text normalization in matching."""

    def test_mixed_case_normalized(self, mock_lookup: dict[str, list[int]]) -> None:
        """Mixed case is normalized to lowercase."""
        results = _match_text_against_lookup("PYTHON", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 1 in entity_ids

    def test_extra_spaces_collapsed(self, mock_lookup: dict[str, list[int]]) -> None:
        """Multiple spaces are collapsed to single space."""
        results = _match_text_against_lookup("machine    learning", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 4 in entity_ids

    def test_leading_trailing_whitespace_stripped(self, mock_lookup: dict[str, list[int]]) -> None:
        """Leading/trailing whitespace is stripped."""
        results = _match_text_against_lookup("  aws  ", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 8 in entity_ids

    def test_portuguese_accents_preserved(self, mock_lookup: dict[str, list[int]]) -> None:
        """Accented characters should be preserved (v1 normalization keeps accents)."""
        results = _match_text_against_lookup("Desenvolvedor Backend", mock_lookup)
        entity_ids = [r[0] for r in results]
        assert 10 in entity_ids


class TestMatchRate:
    """Tests for the match_rate calculation."""

    @pytest.mark.asyncio
    async def test_match_rate_all_keywords_match(
        self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]
    ) -> None:
        """Match rate should be >1.0 when entities > keywords (profile name adds entities)."""
        keywords = [_keyword("python"), _keyword("react")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Unknown"
            )

        # 2 keywords processed, 2 entities created → match_rate = 2/2 = 1.0
        assert result.total_keywords_processed == 2
        assert result.match_rate == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_match_rate_no_keywords_match(
        self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]
    ) -> None:
        """Match rate should be 0 when no keywords match."""
        keywords = [_keyword("cobol"), _keyword("fortran")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Unknown"
            )

        assert result.total_keywords_processed == 2
        assert result.match_rate == 0.0

    @pytest.mark.asyncio
    async def test_confidence_is_decimal(self, mock_session: AsyncMock, mock_lookup: dict[str, list[int]]) -> None:
        """Confidence values stored in entities should be Decimal."""
        keywords = [_keyword("python")]

        with patch(
            "scaffold.professional.profile_classifier._get_entity_lookup",
            return_value=mock_lookup,
        ), patch(
            "scaffold.professional.profile_classifier.candidate_target_profile_entity_repository"
        ) as mock_repo:
            mock_repo.delete_by_target_profile_id = AsyncMock(return_value=0)
            mock_repo.add_all = AsyncMock()

            result = await classify_candidate_profile(
                mock_session, candidate_target_profile_id=100, keywords=keywords, profile_name="Unknown"
            )

        for entity in result.entities_created:
            assert isinstance(entity.confidence, Decimal)
