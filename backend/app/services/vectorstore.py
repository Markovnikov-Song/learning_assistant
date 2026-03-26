from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from langchain_core.documents import Document as LCDocument

from backend.app.services.embeddings import get_embeddings
from backend.app.settings import settings

logger = logging.getLogger(__name__)


def _use_pgvector() -> bool:
    return bool(settings.database_url)


def _pg_collection(subject_id: str) -> str:
    """每个学科对应一个 pgvector collection，用 subject_id 命名"""
    return f"subject_{subject_id}"


def _pg_connection_string() -> str:
    url = settings.database_url or ""
    # LangChain PGVector 需要 postgresql+psycopg2:// 格式
    url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


# ── pgvector 路径 ────────────────────────────────────────────────────────────

def _pgvector_store(subject_id: str):
    from langchain_community.vectorstores import PGVector
    return PGVector(
        collection_name=_pg_collection(subject_id),
        connection_string=_pg_connection_string(),
        embedding_function=get_embeddings(),
        pre_delete_collection=False,
        use_jsonb=True,
    )


def _pgvector_add(subject_id: str, documents: List[LCDocument]) -> None:
    from langchain_community.vectorstores import PGVector
    PGVector.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        collection_name=_pg_collection(subject_id),
        connection_string=_pg_connection_string(),
        pre_delete_collection=False,
        use_jsonb=True,
    )


def _pgvector_delete_collection(subject_id: str) -> None:
    from langchain_community.vectorstores import PGVector
    store = PGVector(
        collection_name=_pg_collection(subject_id),
        connection_string=_pg_connection_string(),
        embedding_function=get_embeddings(),
        pre_delete_collection=True,   # 重建时清空
    )
    store  # 触发 pre_delete


# ── FAISS 路径 ───────────────────────────────────────────────────────────────

INDEX_NAME = "faiss_index"


def _faiss_index_path(subject_id: str) -> Path:
    from backend.app.services.storage import subject_vector_dir
    return subject_vector_dir(subject_id) / INDEX_NAME


def _faiss_load_or_create(subject_id: str):
    from langchain_community.vectorstores import FAISS
    p = _faiss_index_path(subject_id)
    embeddings = get_embeddings()
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists():
        # 安全校验：必须在 data_dir 内
        try:
            p.resolve().relative_to(settings.data_dir.resolve())
        except ValueError:
            logger.error(f"FAISS index outside data_dir, recreating: {p}")
            return FAISS.from_documents(
                [LCDocument(page_content="__init__", metadata={"_init": True})], embeddings
            )
        logger.info(f"Loading FAISS index for subject {subject_id}")
        return FAISS.load_local(str(p), embeddings, allow_dangerous_deserialization=True)

    logger.info(f"Creating new FAISS index for subject {subject_id}")
    return FAISS.from_documents(
        [LCDocument(page_content="__init__", metadata={"_init": True})], embeddings
    )


def _faiss_persist(subject_id: str, store) -> None:
    p = _faiss_index_path(subject_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    store.save_local(str(p))
    logger.info(f"FAISS index persisted for subject {subject_id}")


# ── 统一公共接口 ─────────────────────────────────────────────────────────────

def load_or_create(subject_id: str):
    """加载或创建向量存储（pgvector 或 FAISS）"""
    if _use_pgvector():
        return _pgvector_store(subject_id)
    return _faiss_load_or_create(subject_id)


def persist(subject_id: str, store) -> None:
    """持久化向量存储（仅 FAISS 需要；pgvector 写入时自动持久化）"""
    if not _use_pgvector():
        _faiss_persist(subject_id, store)


def add_documents(subject_id: str, documents: List[LCDocument]) -> None:
    """向量化并写入文档"""
    if not documents:
        return
    if _use_pgvector():
        logger.info(f"Adding {len(documents)} docs to pgvector for subject {subject_id}")
        _pgvector_add(subject_id, documents)
    else:
        store = _faiss_load_or_create(subject_id)
        store.add_documents(documents)
        _faiss_persist(subject_id, store)


def delete_documents(subject_id: str, document_ids: List[str]) -> None:
    """删除文档后重建索引（pgvector 支持按 metadata 过滤删除；FAISS 需全量重建）"""
    if _use_pgvector():
        # pgvector：按 document_id metadata 过滤删除
        try:
            from langchain_community.vectorstores import PGVector
            store = PGVector(
                collection_name=_pg_collection(subject_id),
                connection_string=_pg_connection_string(),
                embedding_function=get_embeddings(),
            )
            # LangChain PGVector 支持 delete by filter
            for doc_id in document_ids:
                store.delete(filter={"document_id": doc_id})
            logger.info(f"Deleted {len(document_ids)} docs from pgvector for subject {subject_id}")
        except Exception as e:
            logger.error(f"pgvector delete failed, falling back to rebuild: {e}")
            rebuild_subject_index(subject_id, _get_db_session())
    else:
        # FAISS：重建整个索引（在 ingest.rebuild_subject_index 里处理）
        pass


def rebuild_subject_index(subject_id: str, db) -> None:
    """重建指定学科的向量索引（删除文档后调用）"""
    from backend.app import models
    from backend.app.services.ingest import _truncate_to_max_tokens

    chunks = db.query(models.Chunk).filter(models.Chunk.subject_id == subject_id).all()

    if not chunks:
        if _use_pgvector():
            _pgvector_delete_collection(subject_id)
        else:
            import shutil
            vec_dir = settings.data_dir / "subjects" / subject_id / "vectorstore"
            if vec_dir.exists():
                shutil.rmtree(vec_dir, ignore_errors=True)
        return

    docs: list[LCDocument] = []
    for ch in chunks:
        doc = db.query(models.Document).filter(models.Document.id == ch.document_id).one_or_none()
        safe_text = _truncate_to_max_tokens(ch.text, max_tokens=512)
        docs.append(LCDocument(
            page_content=safe_text,
            metadata={
                "subject_id": subject_id,
                "document_id": ch.document_id,
                "chunk_id": ch.id,
                "source_name": doc.source_name if doc else "",
                "page_or_section": ch.page_or_section,
                "position_hint": ch.position_hint,
            },
        ))

    if _use_pgvector():
        _pgvector_delete_collection(subject_id)
        _pgvector_add(subject_id, docs)
    else:
        from langchain_community.vectorstores import FAISS
        store = FAISS.from_documents(docs, get_embeddings())
        _faiss_persist(subject_id, store)

    logger.info(f"Rebuilt index for subject {subject_id}: {len(docs)} chunks")
