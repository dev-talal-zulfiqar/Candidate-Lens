import uuid

from tests.resume_fixtures import (
    make_corrupted_pdf_bytes,
    make_docx_bytes,
    make_pdf_bytes,
)


def create_job(client, **overrides):
    payload = {
        "title": "Backend Engineer",
        "description_md": "## Requirements\n- Python",
        **overrides,
    }
    return client.post("/api/jobs", json=payload).json()["id"]


def upload(client, job_id, files):
    """files: list of (filename, content, content_type).

    Upload processing runs as a background task (see
    resume_upload.run_upload_batch_in_background) — the initial POST
    response only confirms the batch was accepted, with empty results.
    The test client runs background tasks to completion before `.post()`
    returns control here, so a follow-up GET immediately after already
    reflects the finished batch; no polling/sleep needed.
    """
    multipart = [("files", (name, content, content_type)) for name, content, content_type in files]
    response = client.post(f"/api/jobs/{job_id}/resumes", files=multipart)
    if response.status_code != 202:
        return response
    batch_id = response.json()["id"]
    return client.get(f"/api/jobs/{job_id}/batches/{batch_id}")


def test_upload_valid_pdf_and_docx_are_processed(client):
    job_id = create_job(client)

    response = upload(
        client,
        job_id,
        [
            ("resume.pdf", make_pdf_bytes("Python developer, 6 years"), "application/pdf"),
            (
                "resume.docx",
                make_docx_bytes("QA engineer, automation"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["total_count"] == 2
    assert body["processed_count"] == 2
    assert body["failed_count"] == 0
    assert {r["status"] for r in body["results"]} == {"processed"}
    assert all(
        r["candidate_id"] and r["resume_id"] and r["application_id"] for r in body["results"]
    )


def test_upload_corrupted_pdf_is_marked_failed_but_still_tracked(client):
    job_id = create_job(client)

    response = upload(client, job_id, [("bad.pdf", make_corrupted_pdf_bytes(), "application/pdf")])

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["failed_count"] == 1
    result = body["results"][0]
    assert result["status"] == "failed"
    # A corrupted-but-valid-looking PDF still gets stored, so there's a
    # resume record a manager can see failed, not silence.
    assert result["resume_id"] is not None
    assert "corrupted" in result["error"].lower()


def test_upload_rejects_wrong_extension_without_persisting_anything(client):
    job_id = create_job(client)
    docx_bytes_named_pdf = make_docx_bytes()

    response = upload(client, job_id, [("sneaky.pdf", docx_bytes_named_pdf, "application/pdf")])

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["candidate_id"] is None
    assert result["resume_id"] is None


def test_upload_mixed_batch_reports_partial_status(client):
    job_id = create_job(client)

    response = upload(
        client,
        job_id,
        [
            ("good.pdf", make_pdf_bytes(), "application/pdf"),
            ("empty.pdf", b"", "application/pdf"),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["processed_count"] == 1
    assert body["failed_count"] == 1


def test_duplicate_file_hash_is_idempotent_within_a_job(client):
    job_id = create_job(client)
    pdf_bytes = make_pdf_bytes("Same file uploaded twice")

    first = upload(client, job_id, [("resume.pdf", pdf_bytes, "application/pdf")])
    second = upload(client, job_id, [("resume.pdf", pdf_bytes, "application/pdf")])

    first_result = first.json()["results"][0]
    second_result = second.json()["results"][0]

    assert first_result["status"] == "processed"
    assert second_result["status"] == "duplicate"
    assert second_result["resume_id"] == first_result["resume_id"]
    assert second_result["application_id"] == first_result["application_id"]
    # The duplicate didn't fail, so it still counts as processed for batch purposes.
    assert second.json()["status"] == "completed"


def test_same_file_across_two_jobs_creates_separate_applications(client):
    job_a = create_job(client, title="Job A")
    job_b = create_job(client, title="Job B")
    pdf_bytes = make_pdf_bytes("Shared resume content")

    result_a = upload(client, job_a, [("resume.pdf", pdf_bytes, "application/pdf")]).json()[
        "results"
    ][0]
    result_b = upload(client, job_b, [("resume.pdf", pdf_bytes, "application/pdf")]).json()[
        "results"
    ][0]

    assert result_a["status"] == "processed"
    assert result_b["status"] == "processed"
    assert result_a["resume_id"] == result_b["resume_id"]
    assert result_a["application_id"] != result_b["application_id"]


def test_upload_with_no_files_returns_422(client):
    job_id = create_job(client)
    response = client.post(f"/api/jobs/{job_id}/resumes", files=[])
    assert response.status_code == 422


def test_upload_for_unknown_job_returns_404(client):
    response = upload(client, uuid.uuid4(), [("r.pdf", make_pdf_bytes(), "application/pdf")])
    assert response.status_code == 404


def test_get_batch_returns_batch_state(client):
    job_id = create_job(client)
    batch_id = upload(client, job_id, [("r.pdf", make_pdf_bytes(), "application/pdf")]).json()[
        "id"
    ]

    response = client.get(f"/api/jobs/{job_id}/batches/{batch_id}")
    assert response.status_code == 200
    assert response.json()["id"] == batch_id


def test_get_batch_unknown_id_returns_404(client):
    job_id = create_job(client)
    response = client.get(f"/api/jobs/{job_id}/batches/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_batch_wrong_job_id_returns_404(client):
    job_a = create_job(client, title="Job A")
    job_b = create_job(client, title="Job B")
    batch_id = upload(client, job_a, [("r.pdf", make_pdf_bytes(), "application/pdf")]).json()[
        "id"
    ]

    response = client.get(f"/api/jobs/{job_b}/batches/{batch_id}")
    assert response.status_code == 404


def test_upload_exceeding_max_files_returns_422(client):
    job_id = create_job(client)
    # One shared pdf body reused across every entry — the cap is checked
    # before any per-file work happens, so there's no need for distinct
    # (and expensively-generated) content per file here.
    pdf_bytes = make_pdf_bytes()
    many_files = [(f"r{i}.pdf", pdf_bytes, "application/pdf") for i in range(501)]

    response = client.post(
        f"/api/jobs/{job_id}/resumes",
        files=[
            ("files", (name, content, content_type))
            for name, content, content_type in many_files
        ],
    )
    assert response.status_code == 422
