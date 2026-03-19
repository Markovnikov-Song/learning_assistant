from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument

from app.services.embeddings import get_embeddings
from app.services.storage import subject_vector_dir


INDEX_NAME = "faiss_index"


def _index_path(subject_id: str) -> Path:
    return subject_vector_dir(subject_id) / INDEX_NAME


def load_or_create(subject_id: str) -> FAISS:
    p = _index_path(subject_id)
    embeddings = get_embeddings()
    if p.exists():
        return FAISS.load_local(str(p), embeddings, allow_dangerous_deserialization=True)
    # empty index
    return FAISS.from_documents([LCDocument(page_content="__init__", metadata={"_init": True})], embeddings)


def persist(subject_id: str, store: FAISS) -> None:
    p = _index_path(subject_id)
    store.save_local(str(p))

