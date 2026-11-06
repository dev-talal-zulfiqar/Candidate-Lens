from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from environment variables.

    Values are read from the process environment or a local .env file.
    Nothing here is hardcoded so deployments can override behavior without
    code changes.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://candidatelens:candidatelens@localhost:5432/candidatelens"
    )
    cors_origins: str = "http://localhost:5173"

    # The synchronous batch endpoints (resume upload, requirement edit/
    # re-run) each hold one connection for the whole operation, not just a
    # single query — a handful of those running concurrently alongside
    # normal traffic can exhaust a small pool (QA-010). Sized generously
    # for a single-instance deployment; revisit if this ever runs with
    # multiple app processes sharing the same database.
    db_pool_size: int = 20
    db_max_overflow: int = 20
    db_pool_timeout_seconds: float = 30.0

    # Resume upload limits. Deliberately conservative defaults for an MVP —
    # see section 11 of the product spec (file size, page count, upload
    # count, and decompressed-size bounds all guard against pathological or
    # malicious uploads, not just honest mistakes).
    resume_storage_dir: str = "storage/resumes"
    max_upload_size_mb: int = 5
    # Upload processing (validation, storage, extraction) runs as a
    # background task after the request returns (see
    # resume_upload.run_upload_batch_in_background), not inline with the
    # request — so this bounds per-request memory (all file bodies are
    # still read into memory up front) rather than request duration.
    # Reaching ~1000 resumes means a few uploads of this size.
    max_files_per_upload: int = 500
    max_pdf_pages: int = 25
    max_extracted_chars: int = 200_000
    max_docx_decompressed_mb: int = 50

    # AI evaluation provider. Defaults to the deterministic mock so nothing
    # ever makes a real, billable API call unless explicitly configured to.
    ai_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ai_prompt_version: str = "v1"
    ai_request_timeout_seconds: float = 30.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def max_docx_decompressed_bytes(self) -> int:
        return self.max_docx_decompressed_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
