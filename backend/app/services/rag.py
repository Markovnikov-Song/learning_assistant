from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy.orm import Session

from app import models
from app.schemas import Citation
from app.services.llm import get_chat_llm
from app.services.vectorstore import load_or_create
from app.settings import settings


SYSTEM_GUARDRAILS = """你是「学科专属RAG智能学习助手」。
硬性规则（必须遵守）：
1) 你只能基于我提供的【资料证据片段】回答，不得使用任何通用常识/外部知识补全。
2) 若证据片段不足以回答，必须直接回复：当前学科的资料中未找到相关内容，请上传对应的学习资料后再提问。不得编造定义、公式、定理、推导、步骤。
3) 理工科回答中公式请用 LaTeX 输出，推导要连贯，不得跳步（但仍必须来自证据）。
4) 回答必须给出来源引用（文件名 + 页码/章节 + 位置），且引用必须对应证据片段。
"""


def _keyword_retrieve(subject_id: str, question: str, db: Session, limit: int) -> list[models.Chunk]:
    q = question.strip()
    if not q:
        return []
    # naive keyword: take up to 5 tokens as LIKE probes
    terms = [t for t in q.replace("\n", " ").split(" ") if t][:5]
    query = db.query(models.Chunk).filter(models.Chunk.subject_id == subject_id)
    for t in terms:
        query = query.filter(models.Chunk.text.like(f"%{t}%"))
    return query.limit(limit).all()


def _vector_retrieve(subject_id: str, question: str, limit: int) -> list[dict[str, Any]]:
    store = load_or_create(subject_id)
    docs = store.similarity_search(question, k=limit)
    out: list[dict[str, Any]] = []
    for d in docs:
        md = d.metadata or {}
        if md.get("_init"):
            continue
        out.append({"text": d.page_content, "metadata": md})
    return out


def _build_citations(chunks: list[dict[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for c in chunks:
        md = c.get("metadata") or {}
        chunk_id = str(md.get("chunk_id") or "")
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        citations.append(
            Citation(
                source_name=str(md.get("source_name") or ""),
                page_or_section=str(md.get("page_or_section") or ""),
                position_hint=str(md.get("position_hint") or ""),
                chunk_id=chunk_id,
            )
        )
    return citations


def hybrid_retrieve(subject_id: str, question: str, db: Session) -> list[dict[str, Any]]:
    vec = _vector_retrieve(subject_id, question, settings.retrieval_top_k)
    kw_chunks = _keyword_retrieve(subject_id, question, db, settings.retrieval_top_k)

    merged: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    for d in vec:
        cid = str((d.get("metadata") or {}).get("chunk_id") or "")
        if cid and cid not in seen_chunk_ids:
            seen_chunk_ids.add(cid)
            merged.append(d)

    for ch in kw_chunks:
        if ch.id in seen_chunk_ids:
            continue
        doc = db.query(models.Document).filter(models.Document.id == ch.document_id).one_or_none()
        merged.append(
            {
                "text": ch.text,
                "metadata": {
                    "subject_id": subject_id,
                    "document_id": ch.document_id,
                    "chunk_id": ch.id,
                    "source_name": doc.source_name if doc else "",
                    "page_or_section": ch.page_or_section,
                    "position_hint": ch.position_hint,
                },
            }
        )
        seen_chunk_ids.add(ch.id)

    return merged[: settings.retrieval_top_k]


def answer_question(subject_id: str, question: str, db: Session) -> tuple[bool, str, list[Citation]]:
    chunks = hybrid_retrieve(subject_id, question, db)
    if not chunks:
        return False, "当前学科的资料中未找到相关内容，请上传对应的学习资料后再提问。", []

    context = "\n\n".join(
        [
            f"[证据 {i+1}] 来源：{(c['metadata'] or {}).get('source_name','')} "
            f"{(c['metadata'] or {}).get('page_or_section','')} "
            f"{(c['metadata'] or {}).get('position_hint','')}\n{c['text']}"
            for i, c in enumerate(chunks)
        ]
    )

    llm = get_chat_llm()
    msg = [
        SystemMessage(content=SYSTEM_GUARDRAILS),
        HumanMessage(
            content=f"【资料证据片段】\n{context}\n\n【用户问题】\n{question}\n\n请基于证据作答，并在文末用列表给出你使用到的证据编号与对应来源。"
        ),
    ]
    resp = llm.invoke(msg)
    answer = getattr(resp, "content", str(resp))
    return True, answer, _build_citations(chunks)


SOLVE_GUARDRAILS = SYSTEM_GUARDRAILS + """
你正在执行「智能解题」：
- 输出固定结构：考点定位→解题思路→完整标准解题步骤→踩分点说明→易错点提醒→对应知识点来源
- 若证据不足以支撑解题，必须按规则直接拒答（同上）。
"""


def solve_problem(subject_id: str, problem_text: str, db: Session) -> tuple[bool, str, list[Citation]]:
    chunks = hybrid_retrieve(subject_id, problem_text, db)
    if not chunks:
        return False, "当前学科的资料中未找到相关内容，请上传对应的学习资料后再解题。", []

    context = "\n\n".join(
        [
            f"[证据 {i+1}] 来源：{(c['metadata'] or {}).get('source_name','')} "
            f"{(c['metadata'] or {}).get('page_or_section','')} "
            f"{(c['metadata'] or {}).get('position_hint','')}\n{c['text']}"
            for i, c in enumerate(chunks)
        ]
    )

    llm = get_chat_llm()
    msg = [
        SystemMessage(content=SOLVE_GUARDRAILS),
        HumanMessage(
            content=f"【资料证据片段】\n{context}\n\n【题目】\n{problem_text}\n\n请严格按固定结构输出，使用 LaTeX 表达公式。"
        ),
    ]
    resp = llm.invoke(msg)
    output = getattr(resp, "content", str(resp))
    return True, output, _build_citations(chunks)

