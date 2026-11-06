import uuid

VALID_JOB = {
    "title": "Senior Backend Engineer",
    "description_md": "## Requirements\n- 5+ years Python\n- PostgreSQL",
}


def create_job(client, **overrides):
    payload = {**VALID_JOB, **overrides}
    return client.post("/api/jobs", json=payload)


def test_create_job_succeeds(client):
    response = create_job(client)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == VALID_JOB["title"]
    assert body["description_md"] == VALID_JOB["description_md"]
    assert body["rubric_version"] == 1
    assert body["requirements"] == []
    assert uuid.UUID(body["id"])


def test_create_job_rejects_blank_title(client):
    response = create_job(client, title="   ")
    assert response.status_code == 422


def test_create_job_rejects_blank_description(client):
    response = create_job(client, description_md="   ")
    assert response.status_code == 422


def test_create_job_rejects_missing_fields(client):
    response = client.post("/api/jobs", json={"title": "Only a title"})
    assert response.status_code == 422


def test_create_job_normalizes_pasted_text_artifacts(client):
    # Windows line endings, non-breaking spaces, a zero-width space, and
    # trailing whitespace per line — all invisible to someone pasting from
    # a webpage or Word doc, all capable of silently breaking line-based
    # parsing if left in.
    messy = (
        "## Requirements\r\n"
        "- 5+ years Python   \r\n"
        "- Postgre​SQL\r\n"
    )

    response = create_job(client, description_md=messy)

    assert response.status_code == 201
    stored = response.json()["description_md"]
    assert "\r" not in stored
    assert " " not in stored
    assert "​" not in stored
    assert stored == "## Requirements\n- 5+ years Python\n- PostgreSQL"


def test_infer_requirements_splits_mandatory_and_preferred_by_heading(client):
    job_id = create_job(
        client,
        description_md=(
            "## Requirements\n"
            "- 5+ years Python\n"
            "- PostgreSQL experience\n"
            "## Nice to have\n"
            "- Kubernetes knowledge"
        ),
    ).json()["id"]

    response = client.post(f"/api/jobs/{job_id}/requirements/infer")

    assert response.status_code == 200
    suggestions = response.json()
    assert len(suggestions) == 3
    by_description = {s["description"]: s for s in suggestions}
    assert by_description["5+ years Python"]["category"] == "mandatory"
    assert by_description["PostgreSQL experience"]["category"] == "mandatory"
    assert by_description["Kubernetes knowledge"]["category"] == "preferred"


def test_infer_requirements_falls_back_when_no_bullets(client):
    job_id = create_job(client, description_md="A great opportunity for a great engineer.").json()[
        "id"
    ]

    response = client.post(f"/api/jobs/{job_id}/requirements/infer")

    assert response.status_code == 200
    suggestions = response.json()
    assert len(suggestions) == 1
    assert suggestions[0]["category"] == "mandatory"


def test_infer_requirements_is_advisory_and_does_not_persist(client):
    job_id = create_job(client).json()["id"]

    client.post(f"/api/jobs/{job_id}/requirements/infer")

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["requirements"] == []


def test_infer_requirements_rejects_once_confirmed(client):
    job_id = create_job(client).json()["id"]
    client.post(
        f"/api/jobs/{job_id}/requirements",
        json={"requirements": [{"description": "Python", "category": "mandatory", "weight": 1}]},
    )

    response = client.post(f"/api/jobs/{job_id}/requirements/infer")
    assert response.status_code == 409


def test_infer_requirements_for_unknown_job_returns_404(client):
    response = client.post(f"/api/jobs/{uuid.uuid4()}/requirements/infer")
    assert response.status_code == 404


MANDATORY_PYTHON = {"description": "Python experience", "category": "mandatory", "weight": 2}
PREFERRED_KUBERNETES = {"description": "Kubernetes knowledge", "category": "preferred", "weight": 1}


def confirm_requirements(client, job_id, requirements):
    return client.post(f"/api/jobs/{job_id}/requirements", json={"requirements": requirements})


def test_delete_job_removes_it_from_the_list(client):
    job_id = create_job(client).json()["id"]

    response = client.delete(f"/api/jobs/{job_id}")

    assert response.status_code == 204
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert job_id not in [j["id"] for j in client.get("/api/jobs").json()]


def test_delete_job_cascades_applications_and_evaluations(client):
    from tests.resume_fixtures import make_pdf_bytes

    job_id = create_job(client).json()["id"]
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload = client.post(
        f"/api/jobs/{job_id}/resumes",
        files=[
            (
                "files",
                (
                    "resume.pdf",
                    make_pdf_bytes("Experienced Python developer, 6 years"),
                    "application/pdf",
                ),
            )
        ],
    )
    assert upload.status_code == 202
    batch = client.get(f"/api/jobs/{job_id}/batches/{upload.json()['id']}").json()
    app_id = batch["results"][0]["application_id"]
    client.post(f"/api/applications/{app_id}/evaluations")

    response = client.delete(f"/api/jobs/{job_id}")

    assert response.status_code == 204
    assert client.get(f"/api/applications/{app_id}/evaluations").status_code == 404


def test_delete_job_for_unknown_job_returns_404(client):
    response = client.delete(f"/api/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


def test_edit_requirements_replaces_the_rubric_and_bumps_version(client):
    job_id = create_job(client).json()["id"]
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])

    response = client.put(
        f"/api/jobs/{job_id}/requirements",
        json={"requirements": [PREFERRED_KUBERNETES]},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["description"] == "Kubernetes knowledge"

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["rubric_version"] == 2
    assert [r["description"] for r in job["requirements"]] == ["Kubernetes knowledge"]


def test_edit_requirements_wipes_existing_evaluations(client):
    from tests.resume_fixtures import make_pdf_bytes

    job_id = create_job(client).json()["id"]
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload = client.post(
        f"/api/jobs/{job_id}/resumes",
        files=[
            (
                "files",
                (
                    "resume.pdf",
                    make_pdf_bytes("Experienced Python developer, 6 years"),
                    "application/pdf",
                ),
            )
        ],
    )
    assert upload.status_code == 202
    batch = client.get(f"/api/jobs/{job_id}/batches/{upload.json()['id']}").json()
    app_id = batch["results"][0]["application_id"]
    client.post(f"/api/applications/{app_id}/evaluations")
    before = client.get(f"/api/applications/{app_id}/evaluations").json()
    assert len(before) == 2
    old_ids = {e["id"] for e in before}

    response = client.put(
        f"/api/jobs/{job_id}/requirements",
        json={"requirements": [PREFERRED_KUBERNETES]},
    )
    assert response.status_code == 200

    # Both stages are fully redone against the new rubric in this same
    # request — not left for a client-side queue that only runs while the
    # browser tab stays on this page.
    evaluations = client.get(f"/api/applications/{app_id}/evaluations").json()
    assert len(evaluations) == 2
    assert {e["stage"] for e in evaluations} == {"preliminary", "ai"}
    assert all(e["status"] == "completed" for e in evaluations)
    assert all(e["rubric_version"] == 2 for e in evaluations)
    assert {e["id"] for e in evaluations}.isdisjoint(old_ids)


def test_edit_requirements_without_any_confirmed_yet_returns_404(client):
    job_id = create_job(client).json()["id"]

    response = client.put(
        f"/api/jobs/{job_id}/requirements",
        json={"requirements": [MANDATORY_PYTHON]},
    )

    assert response.status_code == 404


def test_rerun_evaluations_recomputes_preliminary_and_clears_ai(client):
    from tests.resume_fixtures import make_pdf_bytes

    job_id = create_job(client).json()["id"]
    confirm_requirements(client, job_id, [MANDATORY_PYTHON])
    upload = client.post(
        f"/api/jobs/{job_id}/resumes",
        files=[
            (
                "files",
                (
                    "resume.pdf",
                    make_pdf_bytes("Experienced Python developer, 6 years"),
                    "application/pdf",
                ),
            )
        ],
    )
    assert upload.status_code == 202
    batch = client.get(f"/api/jobs/{job_id}/batches/{upload.json()['id']}").json()
    app_id = batch["results"][0]["application_id"]
    client.post(f"/api/applications/{app_id}/evaluations")
    before = client.get(f"/api/applications/{app_id}/evaluations").json()
    assert len(before) == 2
    old_ids = {e["id"] for e in before}

    response = client.post(f"/api/jobs/{job_id}/evaluations/rerun")

    assert response.status_code == 202
    # The AI stage runs as a background task — the test client drains it
    # before .post() returns control here, so this read-back already
    # reflects the finished run; no polling/sleep needed.
    evaluations = client.get(f"/api/applications/{app_id}/evaluations").json()
    assert len(evaluations) == 2
    assert {e["stage"] for e in evaluations} == {"preliminary", "ai"}
    assert all(e["status"] == "completed" for e in evaluations)
    assert {e["id"] for e in evaluations}.isdisjoint(old_ids)


def test_rerun_evaluations_without_requirements_returns_409(client):
    job_id = create_job(client).json()["id"]

    response = client.post(f"/api/jobs/{job_id}/evaluations/rerun")

    assert response.status_code == 409


def test_rerun_evaluations_for_unknown_job_returns_404(client):
    response = client.post(f"/api/jobs/{uuid.uuid4()}/evaluations/rerun")
    assert response.status_code == 404


def test_get_job_returns_404_for_unknown_id(client):
    response = client.get(f"/api/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


def test_list_jobs_includes_requirement_count(client):
    job_id = create_job(client).json()["id"]
    client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Python", "category": "mandatory", "weight": 1},
            ]
        },
    )

    response = client.get("/api/jobs")
    assert response.status_code == 200
    jobs = {job["id"]: job for job in response.json()}
    assert jobs[job_id]["requirement_count"] == 1


def test_create_requirements_succeeds_and_preserves_order(client):
    job_id = create_job(client).json()["id"]

    response = client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Mandatory skill", "category": "mandatory", "weight": 2},
                {"description": "Nice to have", "category": "preferred", "weight": 1},
            ]
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert [r["description"] for r in body] == ["Mandatory skill", "Nice to have"]
    assert [r["sort_order"] for r in body] == [0, 1]
    assert body[0]["category"] == "mandatory"


def test_create_requirements_rejects_non_positive_weight(client):
    job_id = create_job(client).json()["id"]

    response = client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Bad weight", "category": "mandatory", "weight": 0},
            ]
        },
    )

    assert response.status_code == 422


def test_create_requirements_rejects_weight_over_ten(client):
    job_id = create_job(client).json()["id"]

    response = client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Fat-fingered weight", "category": "mandatory", "weight": 100_000},
            ]
        },
    )

    assert response.status_code == 422


def test_create_requirements_accepts_weight_at_the_cap(client):
    job_id = create_job(client).json()["id"]

    response = client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Max weight", "category": "mandatory", "weight": 10},
            ]
        },
    )

    assert response.status_code == 201


def test_create_requirements_rejects_invalid_category(client):
    job_id = create_job(client).json()["id"]

    response = client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Bad category", "category": "optional", "weight": 1},
            ]
        },
    )

    assert response.status_code == 422


def test_create_requirements_rejects_empty_list(client):
    job_id = create_job(client).json()["id"]

    response = client.post(f"/api/jobs/{job_id}/requirements", json={"requirements": []})

    assert response.status_code == 422


def test_create_requirements_for_unknown_job_returns_404(client):
    response = client.post(
        f"/api/jobs/{uuid.uuid4()}/requirements",
        json={
            "requirements": [
                {"description": "Python", "category": "mandatory", "weight": 1},
            ]
        },
    )
    assert response.status_code == 404


def test_create_requirements_twice_returns_409(client):
    job_id = create_job(client).json()["id"]
    first = client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Python", "category": "mandatory", "weight": 1},
            ]
        },
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Different", "category": "preferred", "weight": 1},
            ]
        },
    )
    assert second.status_code == 409


def test_list_requirements_returns_confirmed_rubric(client):
    job_id = create_job(client).json()["id"]
    client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Python", "category": "mandatory", "weight": 1},
                {"description": "Go", "category": "preferred", "weight": 1},
            ]
        },
    )

    response = client.get(f"/api/jobs/{job_id}/requirements")
    assert response.status_code == 200
    assert [r["description"] for r in response.json()] == ["Python", "Go"]


def test_get_job_embeds_requirements(client):
    job_id = create_job(client).json()["id"]
    client.post(
        f"/api/jobs/{job_id}/requirements",
        json={
            "requirements": [
                {"description": "Python", "category": "mandatory", "weight": 1},
            ]
        },
    )

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    assert len(response.json()["requirements"]) == 1

