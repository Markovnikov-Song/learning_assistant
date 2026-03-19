from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import models
from app.db import init_db
from app.deps import get_db
from app.schemas import (
    AskRequest,
    AskResponse,
    DocumentOut,
    SolveRequest,
    SolveResponse,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
)
from app.services.ingest import rebuild_subject_index, save_upload
from app.services.rag import answer_question, solve_problem
from app.settings import settings


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

