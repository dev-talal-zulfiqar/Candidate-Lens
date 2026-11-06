from app.models.enums import RequirementResultStatus
from app.services.preliminary_matching import extract_keywords, match_requirement


def test_extract_keywords_drops_stopwords_and_filler():
    keywords = extract_keywords("5+ years of strong Python experience")
    assert "python" in keywords
    assert "years" not in keywords
    assert "experience" not in keywords
    assert "strong" not in keywords


def test_match_requirement_met_when_keyword_present():
    result = match_requirement(
        "Python experience", "Senior engineer with 6 years of Python development."
    )
    assert result.status == RequirementResultStatus.MET
    assert any(m.term == "python" for m in result.matches)
    assert "python" in result.matches[0].quote.lower()


def test_match_requirement_unverified_when_keyword_absent():
    result = match_requirement("Kubernetes knowledge", "Frontend developer using React and CSS.")
    assert result.status == RequirementResultStatus.UNVERIFIED
    assert result.matches == []
    assert "does not confirm the candidate lacks" in result.explanation


def test_match_requirement_never_returns_not_met():
    # Preliminary matching can only confirm presence, never absence — this
    # is a deliberate guardrail against over-claiming (see module docstring).
    result = match_requirement("Rust programming", "I only know JavaScript.")
    assert result.status != RequirementResultStatus.NOT_MET


def test_match_requirement_resolves_known_alias():
    result = match_requirement("JavaScript experience", "Built UIs using JS and React.")
    assert result.status == RequirementResultStatus.MET
    assert any(m.term == "js" for m in result.matches)


def test_match_requirement_is_case_insensitive():
    result = match_requirement("python experience", "Expert in PYTHON development.")
    assert result.status == RequirementResultStatus.MET


def test_match_requirement_does_not_match_substrings():
    # "go" should not match inside "going" or "algorithm".
    result = match_requirement("Go experience", "I am going to improve my algorithm skills.")
    assert result.status == RequirementResultStatus.UNVERIFIED


def test_match_requirement_matches_symbol_bearing_terms():
    result = match_requirement("C++ experience", "Wrote performance-critical code in C++.")
    assert result.status == RequirementResultStatus.MET


def test_match_requirement_unverified_when_no_keywords_extracted():
    result = match_requirement("5+ years of experience", "Some resume text.")
    assert result.status == RequirementResultStatus.UNVERIFIED


def test_match_requirement_does_not_false_positive_on_one_generic_word():
    # Regression test: a long, multi-clause requirement (the kind the AI
    # requirement-inference feature produces straight from a job posting)
    # must not be marked "met" just because one generic verb ("design")
    # incidentally appears in a completely unrelated part of the resume.
    description = (
        "Design, build, train, evaluate, and improve advanced machine "
        "learning and LLM-based systems for patient- and provider-facing "
        "products."
    )
    resume_text = (
        "Built microservices on AWS. Skilled in RESTful and GraphQL API "
        "design, JPA/Hibernate query optimization, Spring Security, and "
        "asynchronous processing with Kafka."
    )

    result = match_requirement(description, resume_text)

    assert result.status != RequirementResultStatus.MET


def test_match_requirement_met_requires_coverage_not_one_keyword():
    # Same multi-clause requirement as the false-positive test above, but
    # this resume genuinely covers 3 of its 5 distinct concepts (machine,
    # learning, llm-based) — enough real overlap to clear the 50% coverage
    # bar, unlike one incidental word.
    description = (
        "Design, build, train, evaluate, and improve advanced machine "
        "learning and LLM-based systems for patient- and provider-facing "
        "products."
    )
    resume_text = (
        "Trained machine learning models and built LLM-based pipelines for internal tools."
    )

    result = match_requirement(description, resume_text)

    assert result.status == RequirementResultStatus.MET
    assert len(result.matches) >= 3


def test_match_requirement_partial_overlap_is_unverified_with_evidence_shown():
    # Below the coverage threshold should still be unverified (never
    # not_met) but should surface whatever partial evidence it did find,
    # rather than hiding it, so a reviewer can judge for themselves.
    description = "Machine learning, LLM systems, and Kubernetes orchestration"
    resume_text = "Managed Kubernetes clusters for a backend team."

    result = match_requirement(description, resume_text)

    assert result.status == RequirementResultStatus.UNVERIFIED
    assert any(m.term == "kubernetes" for m in result.matches)
    assert "partial overlap" in result.explanation.lower()


def test_match_requirement_met_when_stated_years_meet_the_bar():
    result = match_requirement(
        "5+ years of Python experience",
        "Backend engineer with 7 years of Python development experience.",
    )
    assert result.status == RequirementResultStatus.MET


def test_match_requirement_unverified_when_years_unstated_near_keyword():
    # QA-013 regression: "5+ years" previously reduced, after stopword
    # removal, to just the bare keyword "python" — any mention satisfied
    # it regardless of how much (or how little, or unstated) experience
    # was actually claimed. A bare mention with no nearby duration must
    # now stop short of MET — but never drop to NOT_MET; the skill is
    # still genuinely evidenced, just not confirmed at the required depth.
    result = match_requirement(
        "5+ years of Python experience",
        "Built several side projects using Python and Flask.",
    )
    assert result.status == RequirementResultStatus.UNVERIFIED
    assert any(m.term == "python" for m in result.matches)
    assert "5+ years" in result.explanation


def test_match_requirement_unverified_when_stated_years_fall_short():
    result = match_requirement(
        "5+ years of Python experience",
        "Backend engineer with 2 years of Python development experience.",
    )
    assert result.status == RequirementResultStatus.UNVERIFIED


def test_match_requirement_ignores_a_years_figure_far_from_the_keyword():
    # A large years figure attached to a *different* skill, far from the
    # Python mention, must not count as confirming Python's duration.
    description = "5+ years of Python experience"
    resume_text = (
        "Led backend teams for 12 years, with deep Java and C++ expertise. "
        + ("Filler sentence about unrelated project history and delivery timelines. " * 3)
        + "Recently picked up Python for internal tooling."
    )
    result = match_requirement(description, resume_text)
    assert result.status == RequirementResultStatus.UNVERIFIED
