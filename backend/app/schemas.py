from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    is_admin: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: str = "理工科"


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: str | None = None
    archived: bool | None = None


class SubjectOut(BaseModel):
    id: str
    name: str
    description: str
    category: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class DocumentOut(BaseModel):
    id: str
    subject_id: str
    source_name: str
    mime_type: str
    sha256: str
    size_bytes: int
    status: Literal["ready", "processing", "failed"]
    error: str
    created_at: datetime
    updated_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str | None = None


class Citation(BaseModel):
    source_name: str
    page_or_section: str = ""
    position_hint: str = ""
    chunk_id: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    found: bool
    conversation_id: str | None = None


class SolveRequest(BaseModel):
    problem_text: str = Field(min_length=1)


class SolveResponse(BaseModel):
    found: bool
    output_markdown: str
    citations: list[Citation]


# 对话历史相关模型
class ConversationHistoryOut(BaseModel):
    id: str
    user_id: str
    subject_id: str
    question_type: Literal["ask", "solve"]
    question: str
    answer: str
    citations: list[Citation]
    found: bool
    created_at: datetime


class ConversationHistoryCreate(BaseModel):
    subject_id: str
    question_type: Literal["ask", "solve"]
    question: str
    answer: str
    citations: list[Citation]
    found: bool = True