from __future__ import annotations

import hashlib
from pathlib import Path

from backend.app.settings import settings


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def subject_dir(subject_id: str) -> Path:
    root = settings.data_dir / "subjects" / subject_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def subject_docs_dir(subject_id: str) -> Path:
    d = subject_dir(subject_id) / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def subject_vector_dir(subject_id: str) -> Path:
    d = subject_dir(subject_id) / "vectorstore"
    d.mkdir(parents=True, exist_ok=True)
    return d

