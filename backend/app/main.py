from __future__ import annotations

import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.db import init_db
from backend.app.deps import get_db
from backend.app.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    ConversationHistoryOut,
    ConversationSessionCreate,
    ConversationSessionOut,
    ConversationSessionUpdate,
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


def _sanitize_filename(filename: str) -> str:
    """
    清理文件名，防止路径遍历攻击
    只允许字母、数字、中文、下划线、短横线、点号
    """
    # 移除路径分隔符和危险字符
    sanitized = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', filename)

    # 限制文件名长度
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:250] + ('.' + ext if ext else '')

    # 确保文件名不为空
    if not sanitized:
        sanitized = "unnamed_file"

    return sanitized


def _validate_filename(filename: str) -> bool:
    """
    验证文件名是否安全
    """
    if not filename:
        return False

    # 检查路径遍历
    if '..' in filename or filename.startswith(('/', '\\')):
        return False

    # 检查文件扩展名白名单
    allowed_extensions = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.txt', '.md', '.jpg', '.jpeg', '.png', '.gif'}
    ext = Path(filename).suffix.lower()
    if ext and ext not in allowed_extensions:
        return False

    return True


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
async def register(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    """注册新用户（开放注册）"""
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

    # 验证文件名
    if not _validate_filename(file.filename):
        raise HTTPException(status_code=400, detail="文件名包含非法字符或文件类型不支持")

    # 清理文件名
    safe_filename = _sanitize_filename(file.filename)

    # stream to temp file to avoid memory blow
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / safe_filename
        with tmp.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        mime = file.content_type or "application/octet-stream"
        doc = save_upload(subject_id, tmp, safe_filename, mime, db)
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


# ==================== 问答和解题端点（带历史记录保存）====================

@app.post("/subjects/{subject_id}/ask", response_model=AskResponse)
def ask(subject_id: str, payload: AskRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> AskResponse:
    _subject_or_404(subject_id, db)
    
    # 如果提供了conversation_id，验证会话是否存在并获取历史记录
    conversation_history = None
    session_id = None
    
    if payload.conversation_id:
        session = db.query(models.ConversationSession).filter(
            models.ConversationSession.id == payload.conversation_id,
            models.ConversationSession.user_id == current_user.id,
            models.ConversationSession.subject_id == subject_id,
        ).one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在或不属于当前学科")
        
        session_id = session.id
        
        # 获取该会话的历史记录
        histories = db.query(models.ConversationHistory).filter(
            models.ConversationHistory.session_id == session_id,
            models.ConversationHistory.deleted == False,
        ).order_by(models.ConversationHistory.created_at.asc()).all()
        
        if histories:
            conversation_history = [
                {"question": h.question, "answer": h.answer}
                for h in histories
            ]
    
    # 调用answer_question，传入历史记录
    found, answer, citations = answer_question(subject_id, payload.question, db, conversation_history)
    
    # 保存对话历史
    history = models.ConversationHistory(
        user_id=current_user.id,
        subject_id=subject_id,
        session_id=session_id,
        question_type="ask",
        question=payload.question,
        answer=answer,
        citations=json.dumps([c.model_dump() for c in citations]),
        found=found,
    )
    db.add(history)
    db.commit()
    
    # 更新会话的updated_at时间
    if session_id:
        session = db.query(models.ConversationSession).filter(
            models.ConversationSession.id == session_id
        ).first()
        if session:
            session.updated_at = datetime.utcnow()
            db.add(session)
            db.commit()
    
    return AskResponse(answer=answer, citations=citations, found=found, conversation_id=payload.conversation_id)


@app.post("/subjects/{subject_id}/solve", response_model=SolveResponse)
def solve(subject_id: str, payload: SolveRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> SolveResponse:
    _subject_or_404(subject_id, db)
    
    # 如果提供了conversation_id，验证会话是否存在并获取历史记录
    conversation_history = None
    session_id = None
    
    if payload.conversation_id:
        session = db.query(models.ConversationSession).filter(
            models.ConversationSession.id == payload.conversation_id,
            models.ConversationSession.user_id == current_user.id,
            models.ConversationSession.subject_id == subject_id,
        ).one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在或不属于当前学科")
        
        session_id = session.id
        
        # 获取该会话的历史记录
        histories = db.query(models.ConversationHistory).filter(
            models.ConversationHistory.session_id == session_id,
            models.ConversationHistory.deleted == False,
        ).order_by(models.ConversationHistory.created_at.asc()).all()
        
        if histories:
            conversation_history = [
                {"question": h.question, "answer": h.answer}
                for h in histories
            ]
    
    # 调用solve_problem，传入历史记录
    found, out_md, citations = solve_problem(subject_id, payload.problem_text, db, conversation_history)
    
    # 保存对话历史
    history = models.ConversationHistory(
        user_id=current_user.id,
        subject_id=subject_id,
        session_id=session_id,
        question_type="solve",
        question=payload.problem_text,
        answer=out_md,
        citations=json.dumps([c.model_dump() for c in citations]),
        found=found,
    )
    db.add(history)
    db.commit()
    
    # 更新会话的updated_at时间
    if session_id:
        session = db.query(models.ConversationSession).filter(
            models.ConversationSession.id == session_id
        ).first()
        if session:
            session.updated_at = datetime.utcnow()
            db.add(session)
            db.commit()
    
    return SolveResponse(found=found, output_markdown=out_md, citations=citations)


# ==================== 对话会话管理端点 ====================

@app.post("/sessions", response_model=ConversationSessionOut)
def create_session(
    payload: ConversationSessionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.ConversationSession:
    """创建新的对话会话"""
    # 验证学科是否存在
    _subject_or_404(payload.subject_id, db)
    
    session = models.ConversationSession(
        user_id=current_user.id,
        subject_id=payload.subject_id,
        title=payload.title or "新对话",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.get("/sessions", response_model=list[ConversationSessionOut])
def list_sessions(
    subject_id: str | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """获取当前用户的所有对话会话"""
    query = db.query(models.ConversationSession).filter(
        models.ConversationSession.user_id == current_user.id,
        models.ConversationSession.deleted == False,
    )
    
    if subject_id:
        query = query.filter(models.ConversationSession.subject_id == subject_id)
    
    sessions = query.order_by(models.ConversationSession.updated_at.desc()).all()
    
    # 添加消息数量统计
    result = []
    for s in sessions:
        message_count = db.query(models.ConversationHistory).filter(
            models.ConversationHistory.session_id == s.id,
            models.ConversationHistory.deleted == False,
        ).count()
        
        result.append({
            "id": s.id,
            "user_id": s.user_id,
            "subject_id": s.subject_id,
            "title": s.title,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "message_count": message_count,
        })
    
    return result


@app.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """删除指定的对话会话"""
    session = db.query(models.ConversationSession).filter(
        models.ConversationSession.id == session_id,
        models.ConversationSession.user_id == current_user.id,
    ).one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 软删除会话（历史记录会被级联软删除或保持原样）
    session.deleted = True
    db.add(session)
    db.commit()
    
    return {"deleted": True}


@app.patch("/sessions/{session_id}", response_model=ConversationSessionOut)
def update_session(
    session_id: str,
    payload: ConversationSessionUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.ConversationSession:
    """更新对话会话标题"""
    session = db.query(models.ConversationSession).filter(
        models.ConversationSession.id == session_id,
        models.ConversationSession.user_id == current_user.id,
    ).one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if payload.title is not None:
        session.title = payload.title
    
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return session


@app.get("/sessions/{session_id}/histories", response_model=list[ConversationHistoryOut])
def get_session_histories(
    session_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[models.ConversationHistory]:
    """获取指定会话的所有对话历史"""
    # 验证会话是否存在且属于当前用户
    session = db.query(models.ConversationSession).filter(
        models.ConversationSession.id == session_id,
        models.ConversationSession.user_id == current_user.id,
    ).one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    histories = db.query(models.ConversationHistory).filter(
        models.ConversationHistory.session_id == session_id,
        models.ConversationHistory.deleted == False,
    ).order_by(models.ConversationHistory.created_at.asc()).all()
    
    return histories


# ==================== 对话历史管理端点 ====================

@app.get("/history", response_model=list[ConversationHistoryOut])
def get_history(
    subject_id: str | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[models.ConversationHistory]:
    """获取当前用户的对话历史"""
    query = db.query(models.ConversationHistory).filter(
        models.ConversationHistory.user_id == current_user.id,
        models.ConversationHistory.deleted == False,
    )
    
    if subject_id:
        query = query.filter(models.ConversationHistory.subject_id == subject_id)
    
    return query.order_by(models.ConversationHistory.created_at.desc()).all()


@app.delete("/history/{history_id}")
def delete_history(
    history_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """删除指定的对话历史记录"""
    history = db.query(models.ConversationHistory).filter(
        models.ConversationHistory.id == history_id,
        models.ConversationHistory.user_id == current_user.id,
    ).one_or_none()
    
    if not history:
        raise HTTPException(status_code=404, detail="对话记录不存在")
    
    # 软删除
    history.deleted = True
    db.add(history)
    db.commit()
    
    return {"deleted": True}


@app.get("/history/export/{history_id}")
def export_history(
    history_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """导出对话历史为 Markdown 文件"""
    history = db.query(models.ConversationHistory).filter(
        models.ConversationHistory.id == history_id,
        models.ConversationHistory.user_id == current_user.id,
        models.ConversationHistory.deleted == False,
    ).one_or_none()
    
    if not history:
        raise HTTPException(status_code=404, detail="对话记录不存在")
    
    # 解析引用
    citations = json.loads(history.citations)
    
    # 生成 Markdown 内容
    question_type_label = "问答" if history.question_type == "ask" else "解题"
    
    md_content = f"# {question_type_label}记录\n\n"
    md_content += f"**学科 ID**: {history.subject_id}\n"
    md_content += f"**时间**: {history.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    md_content += f"**状态**: {'✅ 找到相关内容' if history.found else '❌ 未找到相关内容'}\n\n"
    
    md_content += "## 问题\n\n"
    md_content += f"{history.question}\n\n"
    
    md_content += "## 回答\n\n"
    md_content += f"{history.answer}\n\n"
    
    if citations:
        md_content += "## 来源\n\n"
        for c in citations:
            md_content += f"- **{c['source_name']}**"
            if c.get('page_or_section'):
                md_content += f" · {c['page_or_section']}"
            if c.get('position_hint'):
                md_content += f" · {c['position_hint']}"
            md_content += "\n"
    
    # 生成文件名
    filename = f"{question_type_label}_{history.created_at.strftime('%Y%m%d_%H%M%S')}.md"
    
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )