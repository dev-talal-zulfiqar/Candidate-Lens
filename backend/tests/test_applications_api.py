import uuid

from tests.resume_fixtures import make_pdf_bytes


def create_job(client, **overrides):
    payload = {"title": "Backend Engineer", "description_md": "test", **overrides}
    return client.post("/api/jobs", json=payload).json()["id"]


def confirm_requirements(client, job_id, requirements):
    response = client.post(f"/api/jobs/{job_id}/requirements", json={"requirements": requirements})
    assert response.status_code == 201
    return response.json()


def upload(client, job_id, filename, content):
    response = client.post(
        f"/api/jobs/{job_id}/resumes", files=[("files", (filename, content, "application/pdf"))]
    )
    assert response.status_code == 202
    batch_id = response.json()["id"]
    # Processing runs as a background task; the test client runs it to
    # completion before .post() above returns, so this follow-up GET
    # already reflects the finished batch.
    batch = client.get(f"/api/jobs/{job_id}/batches/{batch_id}").json()
    return batch["results"][0]["application_id"]


MANDATORY_PYTHON = {"description": "Python experience", "category": "mandatory", "weight": 2}
PREFERRED_KUBERNETES = {"description": "Kubernetes knowledge", "category": "preferred", "weight": 1}


def test_create_evaluation_returns_completed_result(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON, PREFERRED_KUBERNETES])
    app_id = upload(
        client,
        job_id,
        "good.pdf",
        make_pdf_bytes("Senior engineer, 7 years of Python and Kubernetes experience"),
    )

    response = client.post(f"/api/applications/{app_id}/evaluations")

    assert response.status_code == 201
    body = response.json()
    assert body["stage"] == "ai"
    assert body["status"] == "completed"
    assert body["model_version"] == "mock-deterministic-v1"
    assert body["score"] == "100.00"
    assert len(body["requirement_results"]) == 2
    assert all(r["status"] == "met" for r in body["requirement_results"])


def test_create_evaluation_is_cached_on_repeat_call(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(client, job_id, "good.pdf", make_pdf_bytes("Python developer, 6 years"))

    first = client.post(f"/api/applications/{app_id}/evaluations").json()
    second = client.post(f"/api/applications/{app_id}/evaluations").json()

    assert first["id"] == second["id"]
    assert first["created_at"] == second["created_at"]


def test_create_evaluation_for_unknown_application_returns_404(client):
    response = client.post(f"/api/applications/{uuid.uuid4()}/evaluations")
    assert response.status_code == 404


def test_create_evaluation_without_confirmed_requirements_returns_409(client):
    job_id = create_job(client)
    app_id = upload(client, job_id, "good.pdf", make_pdf_bytes("Python developer, 6 years"))

    response = client.post(f"/api/applications/{app_id}/evaluations")
    assert response.status_code == 409


def test_create_evaluation_with_failed_extraction_returns_409(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(client, job_id, "corrupted.pdf", b"%PDF-1.4\n" + b"garbage" * 5)

    response = client.post(f"/api/applications/{app_id}/evaluations")
    assert response.status_code == 409


def test_list_evaluations_returns_both_stages_ordered_newest_first(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(client, job_id, "good.pdf", make_pdf_bytes("Python developer, 6 years"))

    client.post(f"/api/applications/{app_id}/evaluations")

    response = client.get(f"/api/applications/{app_id}/evaluations")
    assert response.status_code == 200
    evaluations = response.json()
    assert {e["stage"] for e in evaluations} == {"ai", "preliminary"}
    # "Newest first" only guarantees non-increasing timestamps — two
    # evaluations created in the same request burst can share a
    # microsecond-resolution timestamp, so don't assert a strict order.
    timestamps = [e["created_at"] for e in evaluations]
    assert timestamps == sorted(timestamps, reverse=True)


def test_list_evaluations_for_unknown_application_returns_404(client):
    response = client.get(f"/api/applications/{uuid.uuid4()}/evaluations")
    assert response.status_code == 404


def test_ai_evaluation_includes_verified_evidence_in_requirement_results(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(
        client, job_id, "good.pdf", make_pdf_bytes("Experienced engineer, 6 years of Python")
    )

    body = client.post(f"/api/applications/{app_id}/evaluations").json()
    result = body["requirement_results"][0]
    assert result["status"] == "met"
    assert len(result["evidence_json"]) >= 1
    assert "python" in result["evidence_json"][0]["quote"].lower()


def test_update_decision_sets_and_clears_value(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(client, job_id, "good.pdf", make_pdf_bytes("Python developer, 6 years"))

    response = client.patch(f"/api/applications/{app_id}/decision", json={"decision": "advance"})
    assert response.status_code == 200
    assert response.json()["decision"] == "advance"

    cleared = client.patch(f"/api/applications/{app_id}/decision", json={"decision": None})
    assert cleared.status_code == 200
    assert cleared.json()["decision"] is None


def test_update_decision_rejects_invalid_value(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(client, job_id, "good.pdf", make_pdf_bytes("Python developer, 6 years"))

    response = client.patch(f"/api/applications/{app_id}/decision", json={"decision": "maybe"})
    assert response.status_code == 422


def test_update_decision_for_unknown_application_returns_404(client):
    response = client.patch(
        f"/api/applications/{uuid.uuid4()}/decision", json={"decision": "hold"}
    )
    assert response.status_code == 404


def test_delete_application_removes_it_from_the_candidate_pool(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(client, job_id, "good.pdf", make_pdf_bytes("Python developer, 6 years"))
    client.post(f"/api/applications/{app_id}/evaluations")

    response = client.delete(f"/api/applications/{app_id}")

    assert response.status_code == 204
    items = client.get(f"/api/jobs/{job_id}/candidates").json()["items"]
    assert app_id not in [i["application_id"] for i in items]
    assert client.get(f"/api/applications/{app_id}/evaluations").status_code == 404


def test_delete_application_does_not_affect_the_same_resume_on_another_job(client):
    job_a = create_job(client, title="Job A")
    job_b = create_job(client, title="Job B")
    confirm_requirements(client, job_a, [MANDATORY_PYTHON])
    confirm_requirements(client, job_b, [MANDATORY_PYTHON])
    resume_bytes = make_pdf_bytes("Python developer, 6 years")
    app_a = upload(client, job_a, "shared.pdf", resume_bytes)
    app_b = upload(client, job_b, "shared.pdf", resume_bytes)

    response = client.delete(f"/api/applications/{app_a}")

    assert response.status_code == 204
    items_b = client.get(f"/api/jobs/{job_b}/candidates").json()["items"]
    assert app_b in [i["application_id"] for i in items_b]


def test_delete_application_for_unknown_application_returns_404(client):
    response = client.delete(f"/api/applications/{uuid.uuid4()}")
    assert response.status_code == 404


def test_ai_evaluation_appears_in_candidate_pool_after_triggering(client):
    job_id = create_job(client)
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    app_id = upload(client, job_id, "good.pdf", make_pdf_bytes("Python developer, 6 years"))

    before = client.get(f"/api/jobs/{job_id}/candidates").json()["items"][0]
    assert before["ai_evaluation"] is None

    client.post(f"/api/applications/{app_id}/evaluations")

    after = client.get(f"/api/jobs/{job_id}/candidates").json()["items"][0]
    assert after["ai_evaluation"] is not None
    assert after["ai_evaluation"]["status"] == "completed"
    assert after["preliminary_evaluation"] is not None  # untouched by the AI run
