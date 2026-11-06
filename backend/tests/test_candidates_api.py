import uuid

from tests.resume_fixtures import make_docx_bytes, make_pdf_bytes


def create_job(client, **overrides):
    payload = {"title": "Backend Engineer", "description_md": "test", **overrides}
    return client.post("/api/jobs", json=payload).json()["id"]


def confirm_requirements(client, job_id, requirements):
    response = client.post(f"/api/jobs/{job_id}/requirements", json={"requirements": requirements})
    assert response.status_code == 201
    return response.json()


def upload(client, job_id, filename, content, content_type="application/pdf"):
    response = client.post(
        f"/api/jobs/{job_id}/resumes", files=[("files", (filename, content, content_type))]
    )
    assert response.status_code == 202
    batch_id = response.json()["id"]
    return client.get(f"/api/jobs/{job_id}/batches/{batch_id}").json()


MANDATORY_PYTHON = {"description": "Python experience", "category": "mandatory", "weight": 1}
PREFERRED_KUBERNETES = {"description": "Kubernetes knowledge", "category": "preferred", "weight": 1}


def test_upload_after_requirements_triggers_preliminary_evaluation(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON, PREFERRED_KUBERNETES])

    upload(client, job_id, "good.pdf", make_pdf_bytes("6 years of Python and Kubernetes work"))

    response = client.get(f"/api/jobs/{job_id}/candidates")
    items = response.json()["items"]
    assert len(items) == 1
    evaluation = items[0]["preliminary_evaluation"]
    assert evaluation is not None
    assert evaluation["status"] == "completed"
    assert evaluation["score"] == "90.00"
    assert evaluation["coverage_score"] == "100.00"


def test_upload_before_requirements_is_backfilled_on_confirm(client):
    job_id = create_job(client)
    upload(client, job_id, "good.pdf", make_pdf_bytes("Experienced Python engineer"))

    before = client.get(f"/api/jobs/{job_id}/candidates").json()["items"][0]
    assert before["preliminary_evaluation"] is None

    confirm_requirements(client, job_id, [MANDATORY_PYTHON])

    after = client.get(f"/api/jobs/{job_id}/candidates").json()["items"][0]
    assert after["preliminary_evaluation"] is not None
    assert after["preliminary_evaluation"]["score"] == "70.00"


def test_candidate_with_failed_extraction_has_no_evaluation(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload(client, job_id, "corrupted.pdf", b"%PDF-1.4\n" + b"garbage" * 5)

    items = client.get(f"/api/jobs/{job_id}/candidates").json()["items"]
    assert items[0]["extraction_status"] == "failed"
    assert items[0]["preliminary_evaluation"] is None


def test_candidate_pool_summary_counts(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload(client, job_id, "good.pdf", make_pdf_bytes("Experienced Python developer, 6 years"))
    upload(client, job_id, "corrupted.pdf", b"%PDF-1.4\n" + b"garbage" * 5)

    summary = client.get(f"/api/jobs/{job_id}/candidates").json()["summary"]
    assert summary["total_applications"] == 2
    assert summary["extraction_completed"] == 1
    assert summary["extraction_failed"] == 1


def test_candidate_pool_sort_by_score_desc(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload(client, job_id, "strong.pdf", make_pdf_bytes("Senior Python engineer"))
    upload(client, job_id, "weak.docx", make_docx_bytes("Frontend developer, React and CSS"))

    items = client.get(
        f"/api/jobs/{job_id}/candidates", params={"sort_by": "score", "sort_dir": "desc"}
    ).json()["items"]
    assert [i["resume_filename"] for i in items] == ["strong.pdf", "weak.docx"]


def test_candidate_pool_min_score_filter_excludes_low_scorers(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload(client, job_id, "strong.pdf", make_pdf_bytes("Senior Python engineer"))
    upload(client, job_id, "weak.docx", make_docx_bytes("Frontend developer, React and CSS"))

    response = client.get(f"/api/jobs/{job_id}/candidates", params={"min_score": 50})
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["resume_filename"] == "strong.pdf"


def test_candidate_pool_does_not_hide_unscored_candidates_by_default(client):
    job_id = create_job(client)
    upload(client, job_id, "unscored.pdf", make_pdf_bytes("No requirements confirmed yet"))

    items = client.get(f"/api/jobs/{job_id}/candidates").json()["items"]
    assert len(items) == 1
    assert items[0]["preliminary_evaluation"] is None


def test_candidate_pool_search_filters_by_resume_filename(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload(client, job_id, "alpha_resume.pdf", make_pdf_bytes("Python developer"))
    upload(client, job_id, "beta_resume.pdf", make_pdf_bytes("Python developer"))

    response = client.get(f"/api/jobs/{job_id}/candidates", params={"search": "alpha"})
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["resume_filename"] == "alpha_resume.pdf"


def test_candidate_pool_requirement_status_filter(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload(client, job_id, "match.pdf", make_pdf_bytes("Python developer"))
    upload(client, job_id, "nomatch.docx", make_docx_bytes("Frontend React developer"))

    response = client.get(
        f"/api/jobs/{job_id}/candidates", params={"requirement_status": "unverified"}
    )
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["resume_filename"] == "nomatch.docx"


def test_candidate_pool_pagination(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    for i in range(3):
        upload(client, job_id, f"resume_{i}.pdf", make_pdf_bytes(f"Python developer number {i}"))

    page1 = client.get(f"/api/jobs/{job_id}/candidates", params={"page": 1, "page_size": 2}).json()
    page2 = client.get(f"/api/jobs/{job_id}/candidates", params={"page": 2, "page_size": 2}).json()

    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    assert {i["application_id"] for i in page1["items"]}.isdisjoint(
        {i["application_id"] for i in page2["items"]}
    )


def test_candidate_pool_baseline_is_null_until_ai_evaluation_runs(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON, PREFERRED_KUBERNETES])
    app_id = upload(
        client, job_id, "good.pdf", make_pdf_bytes("6 years of Python and Kubernetes work")
    )["results"][0]["application_id"]

    before = client.get(f"/api/jobs/{job_id}/candidates").json()["items"][0]
    assert before["baseline"] is None

    client.post(f"/api/applications/{app_id}/evaluations")

    after = client.get(f"/api/jobs/{job_id}/candidates").json()["items"][0]
    assert after["baseline"] == {"met": 1, "total": 1}


def test_candidate_pool_surfaces_decision(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(client, job_id, "good.pdf", make_pdf_bytes("Python developer"))["results"][
        0
    ]["application_id"]

    client.patch(f"/api/applications/{app_id}/decision", json={"decision": "decline"})

    items = client.get(f"/api/jobs/{job_id}/candidates").json()["items"]
    assert items[0]["decision"] == "decline"


def test_candidate_pool_for_unknown_job_returns_404(client):
    response = client.get(f"/api/jobs/{uuid.uuid4()}/candidates")
    assert response.status_code == 404


def test_duplicate_resume_across_jobs_each_gets_own_evaluation(client):
    job_a = create_job(client, title="Job A")
    job_b = create_job(client, title="Job B")
    confirm_requirements(client, job_a, [MANDATORY_PYTHON])
    confirm_requirements(client, job_b, [PREFERRED_KUBERNETES])

    pdf_bytes = make_pdf_bytes("Python and Kubernetes expert")
    upload(client, job_a, "resume.pdf", pdf_bytes)
    upload(client, job_b, "resume.pdf", pdf_bytes)

    score_a = client.get(f"/api/jobs/{job_a}/candidates").json()["items"][0][
        "preliminary_evaluation"
    ]["score"]
    score_b = client.get(f"/api/jobs/{job_b}/candidates").json()["items"][0][
        "preliminary_evaluation"
    ]["score"]
    assert score_a == "70.00"  # mandatory-only rubric
    assert score_b == "20.00"  # preferred-only rubric
