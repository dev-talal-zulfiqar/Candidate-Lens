import uuid

from tests.resume_fixtures import make_pdf_bytes


def create_job(client, **overrides):
    payload = {"title": "Backend Engineer", "description_md": "test", **overrides}
    return client.post("/api/jobs", json=payload).json()["id"]


def upload(client, job_id, filename, content):
    response = client.post(
        f"/api/jobs/{job_id}/resumes", files=[("files", (filename, content, "application/pdf"))]
    )
    assert response.status_code == 202
    batch_id = response.json()["id"]
    batch = client.get(f"/api/jobs/{job_id}/batches/{batch_id}").json()
    return batch["results"][0]


def test_get_resume_file_returns_original_bytes(client):
    job_id = create_job(client)
    pdf_bytes = make_pdf_bytes("Python developer")
    result = upload(client, job_id, "resume.pdf", pdf_bytes)

    response = client.get(f"/api/resumes/{result['resume_id']}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert response.content == pdf_bytes


def test_get_resume_file_for_unknown_resume_returns_404(client):
    response = client.get(f"/api/resumes/{uuid.uuid4()}/file")
    assert response.status_code == 404
