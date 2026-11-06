import hashlib
import uuid
from pathlib import Path


def compute_file_hash(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def save_resume_file(contents: bytes, extension: str, storage_dir: str) -> str:
    """Persist an uploaded resume under a generated name and return its path.

    Never uses the user-supplied filename as part of the path — only a
    freshly generated UUID — so there is no path-traversal surface and no
    risk of filename collisions between candidates.
    """
    directory = Path(storage_dir)
    directory.mkdir(parents=True, exist_ok=True)

    generated_name = f"{uuid.uuid4()}{extension.lower()}"
    destination = directory / generated_name
    destination.write_bytes(contents)
    return str(destination)
