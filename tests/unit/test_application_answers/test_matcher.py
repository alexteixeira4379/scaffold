"""Tests for the CommonMatcher deterministic answer resolver."""

import pytest

from scaffold.application_answers.contracts import (
    AnswerType,
    CandidateContext,
    Question,
    QuestionOption,
)
from scaffold.application_answers.matcher import (
    CommonMatcher,
    _find_best_option,
    _match_keywords,
    normalize_text,
    similarity_score,
)


# --- Fixtures ---


@pytest.fixture
def full_context() -> CandidateContext:
    return CandidateContext(
        candidate_id=1,
        full_name="João Silva Santos",
        email="joao@example.com",
        phone="+5511999887766",
        country="BR",
        location="São Paulo, Brazil",
        linkedin_url="https://linkedin.com/in/joaosilva",
        target_country="US",
        target_location="New York, NY",
        min_salary=120000.0,
        currency="USD",
        years_of_experience=7,
        work_authorization="Yes",
        citizenship="Brazilian",
        education_level="Master's",
        languages=["Portuguese", "English"],
        availability="Immediately",
        gender="Male",
        veteran_status="No",
        disability_status="No",
        custom_answers={"favorite_framework": "Django"},
        resume_local_path="/tmp/resume_1.pdf",
        cover_letter_local_path="/tmp/cover_1.pdf",
    )


@pytest.fixture
def matcher(full_context: CandidateContext) -> CommonMatcher:
    return CommonMatcher(full_context)


# --- Utility function tests ---


class TestNormalizeText:
    def test_basic(self):
        assert normalize_text("Hello World!") == "hello world"

    def test_punctuation(self):
        assert normalize_text("What's your e-mail?") == "whats your email"

    def test_empty(self):
        assert normalize_text("") == ""

    def test_whitespace(self):
        assert normalize_text("  multiple   spaces  ") == "multiple spaces"


class TestSimilarityScore:
    def test_identical(self):
        assert similarity_score("hello", "hello") == 1.0

    def test_different(self):
        assert similarity_score("hello", "world") < 0.5

    def test_empty(self):
        assert similarity_score("", "hello") == 0.0


class TestMatchKeywords:
    def test_match(self):
        assert _match_keywords("What is your email address?", ["email"])

    def test_no_match(self):
        assert not _match_keywords("What is your name?", ["email"])

    def test_partial_word_no_match(self):
        # "email" should not match "emailing" due to word boundaries
        assert not _match_keywords("I was emailing", ["email"])

    def test_case_insensitive(self):
        assert _match_keywords("YOUR EMAIL ADDRESS", ["email"])


class TestFindBestOption:
    def test_exact_match(self):
        opts = [QuestionOption(label="Yes", value="yes"), QuestionOption(label="No", value="no")]
        result = _find_best_option("Yes", opts)
        assert result is not None
        assert result.value == "yes"

    def test_fuzzy_match(self):
        opts = [
            QuestionOption(label="Bachelor's Degree", value="bachelors"),
            QuestionOption(label="Master's Degree", value="masters"),
        ]
        result = _find_best_option("Master's", opts)
        assert result is not None
        assert result.value == "masters"

    def test_no_match_below_threshold(self):
        opts = [QuestionOption(label="Apple", value="apple")]
        result = _find_best_option("completely different xyz", opts, threshold=0.9)
        assert result is None

    def test_containment(self):
        opts = [
            QuestionOption(label="1-3 years", value="1-3"),
            QuestionOption(label="4-6 years", value="4-6"),
        ]
        result = _find_best_option("4-6", opts)
        assert result is not None
        assert result.value == "4-6"


# --- CommonMatcher tests ---


class TestMatcherSkip:
    def test_current_value_returns_skip(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Your email?", current_value="already@filled.com")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.type == AnswerType.SKIP
        assert ans.value == "already@filled.com"


class TestMatcherEmail:
    def test_email(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What is your email address?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.type == AnswerType.TEXT
        assert ans.value == "joao@example.com"
        assert ans.source == "database"

    def test_email_with_options(self, matcher: CommonMatcher):
        q = Question(
            id="q1",
            question="Email",
            options=[
                QuestionOption(label="joao@example.com", value="joao@example.com"),
                QuestionOption(label="other@email.com", value="other@email.com"),
            ],
        )
        ans = matcher.match(q)
        assert ans is not None
        assert ans.type == AnswerType.OPTION
        assert ans.value == "joao@example.com"


class TestMatcherName:
    def test_first_name(self, matcher: CommonMatcher):
        q = Question(id="q1", question="First name")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "João"

    def test_last_name(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Last name")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "Silva Santos"

    def test_full_name(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Full name")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "João Silva Santos"


class TestMatcherPhone:
    def test_phone(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Phone number")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "5511999887766"

    def test_mobile(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Your mobile phone")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "5511999887766"


class TestMatcherLinkedIn:
    def test_linkedin(self, matcher: CommonMatcher):
        q = Question(id="q1", question="LinkedIn profile URL")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.type == AnswerType.LINK
        assert ans.value == "https://linkedin.com/in/joaosilva"


class TestMatcherFiles:
    def test_resume(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Upload your resume")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.type == AnswerType.FILE
        assert ans.value == "/tmp/resume_1.pdf"

    def test_cover_letter(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Attach your cover letter")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.type == AnswerType.FILE
        assert ans.value == "/tmp/cover_1.pdf"

    def test_resume_not_available(self):
        ctx = CandidateContext(candidate_id=1, email="x@y.com")
        m = CommonMatcher(ctx)
        q = Question(id="q1", question="Upload your resume")
        ans = m.match(q)
        assert ans is None


class TestMatcherExperience:
    def test_years(self, matcher: CommonMatcher):
        q = Question(id="q1", question="How many years of experience do you have?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "7"

    def test_experience_with_options(self, matcher: CommonMatcher):
        q = Question(
            id="q1",
            question="Years of experience",
            options=[
                QuestionOption(label="1-3", value="1-3"),
                QuestionOption(label="4-6", value="4-6"),
                QuestionOption(label="7+", value="7+"),
            ],
        )
        ans = matcher.match(q)
        assert ans is not None
        assert ans.type == AnswerType.OPTION
        assert ans.value == "7+"

    def test_experience_in_range_middle(self):
        """5 years should match '4-6'."""
        ctx = CandidateContext(candidate_id=1, email="x@y.com", years_of_experience=5)
        m = CommonMatcher(ctx)
        q = Question(
            id="q1",
            question="Years of experience",
            options=[
                QuestionOption(label="1-3", value="1-3"),
                QuestionOption(label="4-6", value="4-6"),
                QuestionOption(label="7+", value="7+"),
            ],
        )
        ans = m.match(q)
        assert ans is not None
        assert ans.type == AnswerType.OPTION
        assert ans.value == "4-6"

    def test_experience_low_range(self):
        """2 years should match '1-3'."""
        ctx = CandidateContext(candidate_id=1, email="x@y.com", years_of_experience=2)
        m = CommonMatcher(ctx)
        q = Question(
            id="q1",
            question="Experience",
            options=[
                QuestionOption(label="1-3", value="1-3"),
                QuestionOption(label="4-6", value="4-6"),
                QuestionOption(label="7+", value="7+"),
            ],
        )
        ans = m.match(q)
        assert ans is not None
        assert ans.value == "1-3"

    def test_experience_boundary_value(self):
        """4 years should match '4-6' (inclusive lower bound)."""
        ctx = CandidateContext(candidate_id=1, email="x@y.com", years_of_experience=4)
        m = CommonMatcher(ctx)
        q = Question(
            id="q1",
            question="Experience",
            options=[
                QuestionOption(label="1-3", value="1-3"),
                QuestionOption(label="4-6", value="4-6"),
                QuestionOption(label="7+", value="7+"),
            ],
        )
        ans = m.match(q)
        assert ans is not None
        assert ans.value == "4-6"

    def test_experience_high_plus(self):
        """15 years should match '10+'."""
        ctx = CandidateContext(candidate_id=1, email="x@y.com", years_of_experience=15)
        m = CommonMatcher(ctx)
        q = Question(
            id="q1",
            question="Experience",
            options=[
                QuestionOption(label="0-2", value="0-2"),
                QuestionOption(label="3-5", value="3-5"),
                QuestionOption(label="6-9", value="6-9"),
                QuestionOption(label="10+", value="10+"),
            ],
        )
        ans = m.match(q)
        assert ans is not None
        assert ans.value == "10+"


class TestNumericRangeMatching:
    """Dedicated tests for _find_numeric_range_option."""

    def test_range_dash(self):
        from scaffold.application_answers.matcher import _find_numeric_range_option

        opts = [
            QuestionOption(label="1-3 years", value="1-3"),
            QuestionOption(label="4-6 years", value="4-6"),
        ]
        assert _find_numeric_range_option(2, opts).value == "1-3"
        assert _find_numeric_range_option(5, opts).value == "4-6"
        assert _find_numeric_range_option(7, opts) is None

    def test_plus_notation(self):
        from scaffold.application_answers.matcher import _find_numeric_range_option

        opts = [
            QuestionOption(label="1-5", value="1-5"),
            QuestionOption(label="6+", value="6+"),
        ]
        assert _find_numeric_range_option(3, opts).value == "1-5"
        assert _find_numeric_range_option(6, opts).value == "6+"
        assert _find_numeric_range_option(100, opts).value == "6+"

    def test_exact_number(self):
        from scaffold.application_answers.matcher import _find_numeric_range_option

        opts = [
            QuestionOption(label="5", value="5"),
            QuestionOption(label="10", value="10"),
        ]
        assert _find_numeric_range_option(5, opts).value == "5"
        assert _find_numeric_range_option(10, opts).value == "10"
        assert _find_numeric_range_option(7, opts) is None

    def test_no_match_returns_none(self):
        from scaffold.application_answers.matcher import _find_numeric_range_option

        opts = [
            QuestionOption(label="Yes", value="yes"),
            QuestionOption(label="No", value="no"),
        ]
        assert _find_numeric_range_option(5, opts) is None


class TestMatcherWorkAuth:
    def test_work_authorization(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Are you legally authorized to work in the US?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "Yes"


class TestMatcherEducation:
    def test_education(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What is your highest level of education?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "Master's"


class TestMatcherSalary:
    def test_salary(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What is your salary expectation?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "120000"


class TestMatcherLocation:
    def test_city(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What city do you live in?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "São Paulo, Brazil"

    def test_country(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What country are you based in?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "BR"

    def test_location_not_confused_with_work_auth(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Are you authorized to work in this location?")
        ans = matcher.match(q)
        assert ans is not None
        # Should match work_authorization because "authorized to work" is present
        assert ans.value == "Yes"
        assert ans.source == "database"


class TestMatcherDemographics:
    def test_gender(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What is your gender?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "Male"

    def test_veteran(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Are you a veteran?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "No"

    def test_disability(self, matcher: CommonMatcher):
        q = Question(id="q1", question="Do you have a disability?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "No"


class TestMatcherAvailability:
    def test_availability(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What is your availability?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "Immediately"


class TestMatcherCitizenship:
    def test_citizenship(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What is your citizenship?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "Brazilian"


class TestMatcherCustomAnswers:
    def test_custom_by_keyword(self, matcher: CommonMatcher):
        q = Question(id="q_framework", question="What is your favorite framework?")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "Django"

    def test_custom_by_id(self, matcher: CommonMatcher):
        q = Question(id="favorite_framework", question="Random text that won't match")
        ans = matcher.match(q)
        assert ans is not None
        assert ans.value == "Django"


class TestMatcherNoData:
    def test_empty_context_returns_none(self):
        ctx = CandidateContext(candidate_id=1)
        m = CommonMatcher(ctx)
        q = Question(id="q1", question="What is your email?")
        ans = m.match(q)
        assert ans is None

    def test_unknown_question_returns_none(self, matcher: CommonMatcher):
        q = Question(id="q1", question="What is your favorite color of the sky?")
        ans = matcher.match(q)
        assert ans is None
