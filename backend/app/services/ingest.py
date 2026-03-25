from __future__ import annotations

import shutil
from pathlib import Path

import tiktoken
from langchain_core.documents import Document as LCDocument
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.services.chunking import split_pages
from backend.app.services.storage import sha256_file, subject_docs_dir
from backend.app.services.text_extract import extract_text_with_metadata
from backend.app.services.vectorstore import add_documents, rebuild_subject_index


def _token_len(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _truncate_to_max_tokens(text: str, max_tokens: int = 512) -> str:
    if _token_len(text) <= max_tokens:
        return text
    enc = tiktoken.get_encoding("cl100k_base")
    return enc.decode(enc.encode(text)[:max_tokens])


def save_upload(
    subject_id: str,
    upload_path: Path,
    original_name: str,
    mime_type: str,
    db: Session,
    progress_callback=None,
) -> models.Document:
    docs_dir = subject_docs_dir(subject_id)
    target = docs_dir / original_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(upload_path, target)
    h = sha256_file(target)
    size = target.stat().st_size

    if progress_callback:
        progress_callback(1, 4, f"检查文档: {original_name}")

    existing = (
        db.query(models.Document)
        .filter(models.Document.subject_id == subject_id, models.Document.source_name == original_name)
        .one_or_none()
    )
    if existing and existing.sha256 == h and existing.status == "ready":
        return existing

    if existing:
        existing.storage_path = str(target)
        existing.mime_type = mime_type
        existing.sha256 = h
        existing.size_bytes = size
        existing.status = "processing"
        existing.error = ""
        doc = existing
        db.query(models.Chunk).filter(models.Chunk.document_id == existing.id).delete()
    else:
        doc = models.Document(
            subject_id=subject_id,
            source_name=original_name,
            storage_path=str(target),
            mime_type=mime_type,
            sha256=h,
            size_bytes=size,
            status="processing",
        )
        db.add(doc)
        db.flush()

    db.commit()

    try:
        if progress_callback:
            progress_callback(2, 4, "提取文本内容...")
        _ingest_document(doc, db, progress_callback)
        doc.status = "ready"
        doc.error = ""
    except Exception as e:  # noqa: BLE001
        doc.status = "failed"
        doc.error = str(e)
    finally:
        db.add(doc)
        db.commit()
    return doc


def _ingest_document(doc: models.Document, db: Session, progress_callback=None) -> None:
    import logging
    logger = logging.getLogger(__name__)

    path = Path(doc.storage_path)

    if progress_callback:
        progress_callback(3, 4, "提取文本并分割...")

    pages = extract_text_with_metadata(path)
    chunks = split_pages(pages)
    if not chunks:
        raise ValueError("未提取到可用文本（可能是扫描版/加密/损坏文件）。")

    if progress_callback:
        progress_callback(3, 4, f"保存 {len(chunks)} 个文本块...")

    for i, c in enumerate(chunks):
        db.add(models.Chunk(
            subject_id=doc.subject_id,
            document_id=doc.id,
            chunk_index=i,
            text=c.text,
            page_or_section=c.page_or_section,
            position_hint=c.position_hint,
        ))
    db.commit()

    if progress_callback:
        progress_callback(4, 4, f"生成向量索引（共 {len(chunks)} 个块）...")

    chunks_query = (
        db.query(models.Chunk)
        .filter(models.Chunk.document_id == doc.id)
        .order_by(models.Chunk.chunk_index)
        .all()
    )

    lc_docs: list[LCDocument] = []
    for idx, ch in enumerate(chunks_query):
        if progress_callback and idx % 20 == 0:
            progress_callback(4, 4, f"生成向量索引... {idx}/{len(chunks_query)}")

        safe_text = _truncate_to_max_tokens(ch.text, max_tokens=512)
        if safe_text != ch.text:
            ch.text = safe_text
            db.add(ch)

        lc_docs.append(LCDocument(
            page_content=safe_text,
            metadata={
                "subject_id": doc.subject_id,
                "document_id": doc.id,
                "chunk_id": ch.id,
                "source_name": doc.source_name,
                "page_or_section": ch.page_or_section,
                "position_hint": ch.position_hint,
            },
        ))

    db.commit()

    # 批量写入向量存储（pgvector 一次搞定；FAISS 也支持批量）
    try:
        add_documents(doc.subject_id, lc_docs)
    except Exception as e:
        logger.error(f"Vector store write failed for doc {doc.id}: {e}")
        raise
