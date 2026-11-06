import uuid

from tests.resume_fixtures import make_pdf_bytes


def create_job(client, **overrides):
    payload = {"title": "Backend Engineer", "description_md": "test", **overrides}
    return client.post("/api/jobs", json=payload).json()["id"]


def confirm_requirements(client, job_id, requirements):
    response = client.post(f"/api/jobs/{job_id}/requirements", json={"requirements": requirements})
    assert response.status_code == 201


def upload(client, job_id, filename, content):
    response = client.post(
        f"/api/jobs/{job_id}/resumes", files=[("files", (filename, content, "application/pdf"))]
    )
    assert response.status_code == 202
    batch_id = response.json()["id"]
    batch = client.get(f"/api/jobs/{job_id}/batches/{batch_id}").json()
    result = batch["results"][0]
    return result["candidate_id"], result["application_id"]


MANDATORY_PYTHON = {"description": "Python experience", "category": "mandatory", "weight": 1}


def test_get_candidate_includes_identity_and_applications(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    candidate_id, application_id = upload(
        client, job_id, "resume.pdf", make_pdf_bytes("Python developer, 6 years")
    )

    response = client.get(f"/api/candidates/{candidate_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == candidate_id
    assert len(body["applications"]) == 1
    application = body["applications"][0]
    assert application["application_id"] == application_id
    assert application["job_title"] == "Backend Engineer"
    assert application["resume_filename"] == "resume.pdf"


def test_get_candidate_includes_both_evaluation_stages_with_requirement_details(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    candidate_id, application_id = upload(
        client, job_id, "resume.pdf", make_pdf_bytes("Python developer, 6 years")
    )
    client.post(f"/api/applications/{application_id}/evaluations")

    body = client.get(f"/api/candidates/{candidate_id}").json()
    evaluations = body["applications"][0]["evaluations"]
    assert {e["stage"] for e in evaluations} == {"preliminary", "ai"}

    for evaluation in evaluations:
        result = evaluation["requirement_results"][0]
        assert result["requirement_description"] == "Python experience"
        assert result["requirement_category"] == "mandatory"


def test_get_candidate_across_multiple_jobs_shows_separate_applications(client):
    job_a = create_job(client, title="Job A")
    job_b = create_job(client, title="Job B")
    confirm_requirements(client, job_a, [MANDATORY_PYTHON])
    confirm_requirements(client, job_b, [MANDATORY_PYTHON])

    pdf_bytes = make_pdf_bytes("Python developer, shared resume")
    candidate_id, _ = upload(client, job_a, "resume.pdf", pdf_bytes)
    upload(client, job_b, "resume.pdf", pdf_bytes)

    body = client.get(f"/api/candidates/{candidate_id}").json()
    assert len(body["applications"]) == 2
    assert {a["job_title"] for a in body["applications"]} == {"Job A", "Job B"}


def test_get_unknown_candidate_returns_404(client):
    response = client.get(f"/api/candidates/{uuid.uuid4()}")
    assert response.status_code == 404


def test_update_review_status_succeeds(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    _, application_id = upload(
        client, job_id, "resume.pdf", make_pdf_bytes("Python developer, 6 years")
    )

    response = client.patch(
        f"/api/applications/{application_id}/review-status",
        json={"review_status": "reviewed"},
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == "reviewed"


def test_update_review_status_is_independent_of_ai_evaluation(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    _, application_id = upload(
        client, job_id, "resume.pdf", make_pdf_bytes("Python developer, 6 years")
    )

    client.patch(
        f"/api/applications/{application_id}/review-status",
        json={"review_status": "in_review"},
    )
    client.post(f"/api/applications/{application_id}/evaluations")

    response = client.get(f"/api/jobs/{job_id}/candidates")
    item = response.json()["items"][0]
    assert item["review_status"] == "in_review"  # untouched by the AI run
    assert item["ai_evaluation"] is not None


def test_update_review_status_rejects_invalid_value(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    _, application_id = upload(
        client, job_id, "resume.pdf", make_pdf_bytes("Python developer, 6 years")
    )

    response = client.patch(
        f"/api/applications/{application_id}/review-status",
        json={"review_status": "bogus"},
    )
    assert response.status_code == 422


def test_update_review_status_for_unknown_application_returns_404(client):
    response = client.patch(
        f"/api/applications/{uuid.uuid4()}/review-status",
        json={"review_status": "reviewed"},
    )
    assert response.status_code == 404
