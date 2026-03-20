from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="理工科")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("subject_id", "source_name", name="uq_subject_source_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)

    source_name: Mapped[str] = mapped_column(String(260), nullable=False)  # original filename or imported title
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)  # on-disk path under data/
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/octet-stream")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ready")  # ready|processing|failed
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)

    subject: Mapped["Subject"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_doc_chunk_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Strong metadata required by spec
    page_or_section: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    position_hint: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class ConversationSession(Base):
    """对话会话表"""
    __tablename__ = "conversation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False, default="新对话")
    
    # 软删除标记
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)

    # 关系
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    subject: Mapped["Subject"] = relationship(foreign_keys=[subject_id])
    histories: Mapped[list["ConversationHistory"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ConversationHistory(Base):
    """对话历史记录表"""
    __tablename__ = "conversation_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=True)

    # 问题类型：ask（问答）或 solve（解题）
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)  # ask | solve
    
    # 问题内容
    question: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 回答内容
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 引用来源（JSON 格式存储）
    citations: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON string
    
    # 是否找到相关内容
    found: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # 软删除标记
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)

    # 关系
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    subject: Mapped["Subject"] = relationship(foreign_keys=[subject_id])
    session: Mapped["ConversationSession"] = relationship(foreign_keys=[session_id])