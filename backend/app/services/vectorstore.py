from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument

from backend.app.services.embeddings import get_embeddings
from backend.app.services.storage import subject_vector_dir


logger = logging.getLogger(__name__)
INDEX_NAME = "faiss_index"


def _index_path(subject_id: str) -> Path:
    """
    获取向量索引的路径
    """
    return subject_vector_dir(subject_id) / INDEX_NAME


def load_or_create(subject_id: str) -> FAISS:
    """
    加载或创建FAISS向量存储
    """
    try:
        p = _index_path(subject_id)
        embeddings = get_embeddings()
        
        # 确保目录存在
        p.parent.mkdir(parents=True, exist_ok=True)
        
        if p.exists():
            logger.info(f"Loading existing vector store for subject {subject_id}")
            return FAISS.load_local(str(p), embeddings, allow_dangerous_deserialization=True)
        
        logger.info(f"Creating new vector store for subject {subject_id}")
        # 创建空索引
        return FAISS.from_documents([LCDocument(page_content="__init__", metadata={"_init": True})], embeddings)
    except Exception as e:
        logger.error(f"Error loading or creating vector store: {str(e)}")
        raise


def persist(subject_id: str, store: FAISS) -> None:
    """
    持久化向量存储
    """
    try:
        p = _index_path(subject_id)
        # 确保目录存在
        p.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Persisting vector store for subject {subject_id}")
        store.save_local(str(p))
    except Exception as e:
        logger.error(f"Error persisting vector store: {str(e)}")
        raise


def add_documents(subject_id: str, documents: List[LCDocument]) -> FAISS:
    """
    添加文档到向量存储
    """
    try:
        store = load_or_create(subject_id)
        if documents:
            logger.info(f"Adding {len(documents)} documents to vector store for subject {subject_id}")
            store.add_documents(documents)
            persist(subject_id, store)
        return store
    except Exception as e:
        logger.error(f"Error adding documents to vector store: {str(e)}")
        raise


def delete_documents(subject_id: str, document_ids: List[str]) -> FAISS:
    """
    从向量存储中删除文档
    """
    try:
        store = load_or_create(subject_id)
        # FAISS不直接支持按文档ID删除，需要重建索引
        # 这里简化处理，实际项目中可能需要更复杂的实现
        logger.info(f"Deleting documents from vector store for subject {subject_id}")
        # 重建索引的逻辑可以在这里实现
        return store
    except Exception as e:
        logger.error(f"Error deleting documents from vector store: {str(e)}")
        raise

