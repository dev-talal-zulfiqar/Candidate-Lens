from app.integrations.ai_prompt import RequirementInferenceRequest
from app.integrations.ai_provider import MockAIProvider


def infer(description_md: str):
    return MockAIProvider().infer_requirements(
        RequirementInferenceRequest(job_title="Role", description_md=description_md)
    )


def test_unicode_bullets_are_recognized_as_a_real_bullet_list():
    # Pasting from a webpage/Word often turns "-"/"*" into a bullet
    # character instead, with no markdown markup at all.
    description = "Requirements:\n• 5+ years Python\n• PostgreSQL experience"

    suggestions = infer(description)

    assert len(suggestions) == 2
    assert {s.description for s in suggestions} == {"5+ years Python", "PostgreSQL experience"}
    assert all(s.category == "mandatory" for s in suggestions)


def test_bare_label_heading_without_hash_switches_category():
    description = (
        "Requirements:\n"
        "• Python experience\n"
        "Nice to have:\n"
        "• Kubernetes knowledge"
    )

    suggestions = infer(description)

    by_description = {s.description: s.category for s in suggestions}
    assert by_description["Python experience"] == "mandatory"
    assert by_description["Kubernetes knowledge"] == "preferred"


def test_plain_text_with_no_bullet_markup_at_all_does_not_only_return_the_heading():
    # This is the exact bug report: a JD pasted as plain text with a
    # heading line and un-bulleted requirement lines used to produce
    # exactly one suggestion — the heading itself.
    description = (
        "Senior ML Engineer\n"
        "\n"
        "Requirements:\n"
        "Design and train machine learning models for production use.\n"
        "5+ years of experience with Python and PyTorch.\n"
        "Strong understanding of distributed systems.\n"
    )

    suggestions = infer(description)

    descriptions = [s.description for s in suggestions]
    assert "Requirements" not in descriptions
    assert any("machine learning" in d for d in descriptions)
    assert any("PyTorch" in d for d in descriptions)
    assert any("distributed systems" in d for d in descriptions)


def test_bare_heading_phrase_with_no_colon_is_recognized_and_skipped():
    # Real job postings almost never put a colon after "Requirements" —
    # it's usually styled bold/larger in the original and, once pasted as
    # plain text, is just a bare short line indistinguishable from a real
    # requirement by punctuation alone.
    description = (
        "Senior ML Engineer\n"
        "\n"
        "About the role\n"
        "We're looking for an experienced machine learning engineer to join our team.\n"
        "\n"
        "Requirements\n"
        "Design, build, train, evaluate, and improve machine learning systems.\n"
        "5+ years of experience with Python and PyTorch.\n"
        "Strong understanding of distributed systems and MLOps.\n"
        "\n"
        "Nice to have\n"
        "Experience with LLM fine-tuning.\n"
        "Kubernetes experience.\n"
    )

    suggestions = infer(description)
    descriptions = [s.description for s in suggestions]

    assert "About the role" not in descriptions
    assert "Requirements" not in descriptions
    assert "Nice to have" not in descriptions
    assert not any(d.lower().startswith("we're looking for") for d in descriptions)
    assert any("PyTorch" in d for d in descriptions)

    by_description = {s.description: s.category for s in suggestions}
    assert by_description["Experience with LLM fine-tuning."] == "preferred"
    assert by_description["Kubernetes experience."] == "preferred"
    assert all(
        by_description[d] == "mandatory"
        for d in descriptions
        if "PyTorch" in d or "distributed systems" in d
    )


def test_single_unbroken_paragraph_splits_on_sentences_not_just_the_first_one():
    description = (
        "We need someone with five years of backend experience. "
        "Strong Python and PostgreSQL skills are required. "
        "Experience with Kubernetes is a plus."
    )

    suggestions = infer(description)

    assert len(suggestions) == 3
    assert any("Kubernetes" in s.description for s in suggestions)


def test_label_heading_with_trailing_content_is_not_treated_as_a_heading():
    # "Experience: 5 years" has real content after the colon, unlike a bare
    # "Requirements:" label line — it must be treated as a requirement, not
    # consumed as a section header.
    description = "Experience: 5 years of backend development required."

    suggestions = infer(description)

    assert any("Experience: 5 years" in s.description for s in suggestions)
