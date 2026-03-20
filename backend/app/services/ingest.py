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
from backend.app.services.vectorstore import load_or_create, persist
from backend.app.settings import settings


def _token_len(text: str) -> int:
    """计算文本的 token 数量"""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _truncate_to_max_tokens(text: str, max_tokens: int = 512) -> str:
    """截断文本到最大 token 数"""
    token_count = _token_len(text)
    if token_count <= max_tokens:
        return text
    
    # 截断到最大 token 数
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)[:max_tokens]
    return enc.decode(tokens)


def save_upload(
    subject_id: str,
    upload_path: Path,
    original_name: str,
    mime_type: str,
    db: Session,
    progress_callback=None,
) -> models.Document:
    """保存上传的文档并处理
    
    Args:
        progress_callback: 可选的进度回调函数，签名为 callback(current, total, message)
    """
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
        # replace content and mark for re-ingest
        existing.storage_path = str(target)
        existing.mime_type = mime_type
        existing.sha256 = h
        existing.size_bytes = size
        existing.status = "processing"
        existing.error = ""
        doc = existing
        # remove old chunks
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
    """处理文档并添加到向量存储
    
    Args:
        progress_callback: 可选的进度回调函数，签名为 callback(current, total, message)
    """
    path = Path(doc.storage_path)
    
    if progress_callback:
        progress_callback(3, 4, "提取文本并分割...")
    
    pages = extract_text_with_metadata(path)
    chunks = split_pages(pages)
    if not chunks:
        raise ValueError("未提取到可用文本（可能是扫描版/加密/损坏文件）。")

    # Persist chunks to DB first (强制元数据标注)
    if progress_callback:
        progress_callback(3, 4, f"保存 {len(chunks)} 个文本块...")
    
    for i, c in enumerate(chunks):
        db.add(
            models.Chunk(
                subject_id=doc.subject_id,
                document_id=doc.id,
                chunk_index=i,
                text=c.text,
                page_or_section=c.page_or_section,
                position_hint=c.position_hint,
            )
        )
    db.commit()

    # Then upsert into subject vectorstore
    store = load_or_create(doc.subject_id)
    
    if progress_callback:
        progress_callback(4, 4, f"生成向量索引（共 {len(chunks)} 个块）...")
    
    # 逐个添加文档，避免批量处理时的 token 超限问题
    chunks_query = db.query(models.Chunk).filter(models.Chunk.document_id == doc.id).order_by(models.Chunk.chunk_index).all()
    total_chunks = len(chunks_query)
    
    for idx, ch in enumerate(chunks_query):
        # 更新进度
        if progress_callback and idx % 10 == 0:  # 每10个chunk更新一次进度
            progress_callback(4, 4, f"生成向量索引... {idx}/{total_chunks}")
        
        # 最终检查：确保文本不超过 512 tokens
        safe_text = _truncate_to_max_tokens(ch.text, max_tokens=512)
        
        # 如果文本被截断了，更新数据库
        if safe_text != ch.text:
            ch.text = safe_text
            db.add(ch)
            db.commit()
        
        # 逐个添加到向量存储
        lc_doc = LCDocument(
            page_content=safe_text,
            metadata={
                "subject_id": doc.subject_id,
                "document_id": doc.id,
                "chunk_id": ch.id,
                "source_name": doc.source_name,
                "page_or_section": ch.page_or_section,
                "position_hint": ch.position_hint,
            },
        )
        
        try:
            store.add_documents([lc_doc])
        except Exception as e:
            # 如果还是失败，记录错误但继续处理下一个
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to add chunk {ch.id} to vector store: {e}")
            continue
    
    persist(doc.subject_id, store)


def rebuild_subject_index(subject_id: str, db: Session) -> None:
    """
    When documents are deleted, rebuild to avoid stale vectors.
    """
    from langchain_community.vectorstores import FAISS
    from backend.app.services.embeddings import get_embeddings

    chunks = db.query(models.Chunk).filter(models.Chunk.subject_id == subject_id).all()
    if not chunks:
        # reset by removing folder
        vec_dir = settings.data_dir / "subjects" / subject_id / "vectorstore"
        if vec_dir.exists():
            shutil.rmtree(vec_dir, ignore_errors=True)
        return
    
    # 逐个重建，避免批量处理时的 token 超限问题
    docs: list[LCDocument] = []
    for ch in chunks:
        doc = db.query(models.Document).filter(models.Document.id == ch.document_id).one()
        # 重建时也检查 token 数量
        safe_text = _truncate_to_max_tokens(ch.text, max_tokens=512)
        docs.append(
            LCDocument(
                page_content=safe_text,
                metadata={
                    "subject_id": subject_id,
                    "document_id": ch.document_id,
                    "chunk_id": ch.id,
                    "source_name": doc.source_name,
                    "page_or_section": ch.page_or_section,
                    "position_hint": ch.position_hint,
                },
            )
        )
    
    # 使用更小的 batch size 重建索引
    store = FAISS.from_documents(docs, get_embeddings())
    persist(subject_id, store)