from __future__ import annotations

from typing import Any, List, Dict

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSequence
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.schemas import Citation
from backend.app.services.llm import get_chat_llm
from backend.app.services.vectorstore import load_or_create
from backend.app.settings import settings


SYSTEM_GUARDRAILS = """你是「学科专属RAG智能学习助手」。
硬性规则（必须遵守）：
1) 你只能基于我提供的【资料证据片段】回答，不得使用任何通用常识/外部知识补全。
2) 若证据片段不足以回答，必须直接回复：当前学科的资料中未找到相关内容，请上传对应的学习资料后再提问。不得编造定义、公式、定理、推导、步骤。
3) 理工科回答中公式请用 LaTeX 输出，推导要连贯，不得跳步（但仍必须来自证据）。
4) 回答必须给出来源引用（文件名 + 页码/章节 + 位置），且引用必须对应证据片段。
"""


def _keyword_retrieve(subject_id: str, question: str, db: Session, limit: int) -> list[models.Chunk]:
    """
    基于关键词检索相关片段
    """
    q = question.strip()
    if not q:
        return []
    # 改进关键词提取：移除停用词，保留有意义的词
    stop_words = set(['的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'])
    terms = [t for t in q.replace("\n", " ").split(" ") if t and t not in stop_words][:8]  # 增加关键词数量
    if not terms:
        return []
    
    query = db.query(models.Chunk).filter(models.Chunk.subject_id == subject_id)
    for t in terms:
        query = query.filter(models.Chunk.text.like(f"%{t}%"))
    return query.limit(limit).all()


def _vector_retrieve(subject_id: str, question: str, limit: int) -> list[dict[str, Any]]:
    """
    基于向量相似度检索相关片段
    """
    store = load_or_create(subject_id)
    # 使用相似度分数进行排序
    docs = store.similarity_search_with_score(question, k=limit)
    out: list[dict[str, Any]] = []
    for d, score in docs:
        md = d.metadata or {}
        if md.get("_init"):
            continue
        out.append({"text": d.page_content, "metadata": md, "score": score})
    # 按相似度分数排序
    out.sort(key=lambda x: x.get("score", 0), reverse=True)
    return out


def _build_citations(chunks: list[dict[str, Any]]) -> list[Citation]:
    """
    构建引用列表
    """
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
    """
    混合检索：结合向量检索和关键词检索
    """
    # 增加检索数量，然后进行去重和排序
    vec = _vector_retrieve(subject_id, question, settings.retrieval_top_k * 2)
    kw_chunks = _keyword_retrieve(subject_id, question, db, settings.retrieval_top_k * 2)

    merged: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    # 先添加向量检索结果
    for d in vec:
        cid = str((d.get("metadata") or {}).get("chunk_id") or "")
        if cid and cid not in seen_chunk_ids:
            seen_chunk_ids.add(cid)
            merged.append(d)

    # 再添加关键词检索结果
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
                "score": 0.8,  # 给关键词检索结果一个默认分数
            }
        )
        seen_chunk_ids.add(ch.id)

    # 按分数排序并限制数量
    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    return merged[: settings.retrieval_top_k]


def answer_question(subject_id: str, question: str, db: Session) -> tuple[bool, str, list[Citation]]:
    """
    回答用户问题
    """
    try:
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
        # 使用RunnableSequence优化调用
        chain = RunnableSequence(
            lambda x: [
                SystemMessage(content=SYSTEM_GUARDRAILS),
                HumanMessage(
                    content=f"【资料证据片段】\n{x['context']}\n\n【用户问题】\n{x['question']}\n\n请基于证据作答，并在文末用列表给出你使用到的证据编号与对应来源。"
                ),
            ],
            llm,
            StrOutputParser()
        )
        answer = chain.invoke({"context": context, "question": question})
        return True, answer, _build_citations(chunks)
    except Exception as e:
        return False, f"处理问题时出错：{str(e)}", []


SOLVE_GUARDRAILS = SYSTEM_GUARDRAILS + """
你正在执行「智能解题」：
- 输出固定结构：考点定位→解题思路→完整标准解题步骤→踩分点说明→易错点提醒→对应知识点来源
- 若证据不足以支撑解题，必须按规则直接拒答（同上）。
"""


def solve_problem(subject_id: str, problem_text: str, db: Session) -> tuple[bool, str, list[Citation]]:
    """
    解决数学问题
    """
    try:
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
        # 使用RunnableSequence优化调用
        chain = RunnableSequence(
            lambda x: [
                SystemMessage(content=SOLVE_GUARDRAILS),
                HumanMessage(
                    content=f"【资料证据片段】\n{x['context']}\n\n【题目】\n{x['problem']}\n\n请严格按固定结构输出，使用 LaTeX 表达公式。"
                ),
            ],
            llm,
            StrOutputParser()
        )
        output = chain.invoke({"context": context, "problem": problem_text})
        return True, output, _build_citations(chunks)
    except Exception as e:
        return False, f"处理问题时出错：{str(e)}", []

