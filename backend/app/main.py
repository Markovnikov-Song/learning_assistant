from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.db import init_db
from backend.app.deps import get_db
from backend.app.schemas import (
    AskRequest,
    AskResponse,
    DocumentOut,
    SolveRequest,
    SolveResponse,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
)
from backend.app.services.ingest import rebuild_subject_index, save_upload
from backend.app.services.rag import answer_question, solve_problem
from backend.app.settings import settings


init_db()

app = FastAPI(title="学科专属RAG智能学习助手 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _subject_or_404(subject_id: str, db: Session) -> models.Subject:
    s = db.query(models.Subject).filter(models.Subject.id == subject_id).one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="学科不存在")
    return s


@app.get("/health")
def health() -> dict:
    return {"ok": True, "time": datetime.utcnow().isoformat()}


# ==================== 认证相关端点 ====================

from backend.app.services.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_admin,
    get_current_user,
)


@app.post("/auth/register", response_model=TokenResponse)
async def register(payload: UserRegister, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin)) -> TokenResponse:
    """注册新用户（仅管理员可用）"""
    user = create_user(db, payload.username, payload.password, is_admin=False)
    access_token = create_access_token(data={"sub": user.id})
    return TokenResponse(
        access_token=access_token,
        user=UserOut(
            id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            created_at=user.created_at,
        )
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """用户登录"""
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.id})
    return TokenResponse(
        access_token=access_token,
        user=UserOut(
            id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            created_at=user.created_at,
        )
    )


@app.get("/auth/me", response_model=UserOut)
async def get_me(current_user: models.User = Depends(get_current_user)) -> UserOut:
    """获取当前用户信息"""
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
    )


# ==================== 学科管理端点 ====================

@app.post("/subjects", response_model=SubjectOut)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db)) -> models.Subject:
    s = models.Subject(name=payload.name, description=payload.description, category=payload.category)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.get("/subjects", response_model=list[SubjectOut])
def list_subjects(include_archived: bool = False, db: Session = Depends(get_db)) -> list[models.Subject]:
    q = db.query(models.Subject)
    if not include_archived:
        q = q.filter(models.Subject.archived == False)  # noqa: E712
    return q.order_by(models.Subject.created_at.desc()).all()


@app.patch("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: str, payload: SubjectUpdate, db: Session = Depends(get_db)) -> models.Subject:
    s = _subject_or_404(subject_id, db)
    if payload.name is not None:
        s.name = payload.name
    if payload.description is not None:
        s.description = payload.description
    if payload.category is not None:
        s.category = payload.category
    if payload.archived is not None:
        s.archived = payload.archived
    s.updated_at = datetime.utcnow()
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.delete("/subjects/{subject_id}")
def delete_subject(subject_id: str, db: Session = Depends(get_db)) -> dict:
    s = _subject_or_404(subject_id, db)
    db.delete(s)
    db.commit()
    # remove on-disk subject folder
    subject_folder = settings.data_dir / "subjects" / subject_id
    if subject_folder.exists():
        shutil.rmtree(subject_folder, ignore_errors=True)
    return {"deleted": True}


@app.get("/subjects/{subject_id}/documents", response_model=list[DocumentOut])
def list_documents(subject_id: str, db: Session = Depends(get_db)) -> list[models.Document]:
    _subject_or_404(subject_id, db)
    return (
        db.query(models.Document)
        .filter(models.Document.subject_id == subject_id)
        .order_by(models.Document.created_at.desc())
        .all()
    )


@app.post("/subjects/{subject_id}/documents/upload", response_model=DocumentOut)
async def upload_document(
    subject_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> models.Document:
    _subject_or_404(subject_id, db)
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    # stream to temp file to avoid memory blow
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / file.filename
        with tmp.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        mime = file.content_type or "application/octet-stream"
        doc = save_upload(subject_id, tmp, file.filename, mime, db)
        return doc


@app.delete("/subjects/{subject_id}/documents/{document_id}")
def delete_document(subject_id: str, document_id: str, db: Session = Depends(get_db)) -> dict:
    _subject_or_404(subject_id, db)
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.subject_id == subject_id)
        .one_or_none()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="文件不存在")
    # remove file on disk
    try:
        Path(doc.storage_path).unlink(missing_ok=True)
    except Exception:
        pass
    db.delete(doc)
    db.commit()
    rebuild_subject_index(subject_id, db)
    return {"deleted": True}


@app.post("/subjects/{subject_id}/ask", response_model=AskResponse)
def ask(subject_id: str, payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    _subject_or_404(subject_id, db)
    found, answer, citations = answer_question(subject_id, payload.question, db)
    return AskResponse(answer=answer, citations=citations, found=found, conversation_id=payload.conversation_id)


@app.post("/subjects/{subject_id}/solve", response_model=SolveResponse)
def solve(subject_id: str, payload: SolveRequest, db: Session = Depends(get_db)) -> SolveResponse:
    _subject_or_404(subject_id, db)
    found, out_md, citations = solve_problem(subject_id, payload.problem_text, db)
    return SolveResponse(found=found, output_markdown=out_md, citations=citations)

