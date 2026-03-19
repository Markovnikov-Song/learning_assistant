# 1. 未来特性导入（必须第一行）
from __future__ import annotations

# 2. 调整 sys.path（优先导入 backend）
import sys
import os

# 获取当前文件的上级目录（learning_assistant/），作为根路径
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
sys.path.insert(0, ROOT_DIR)  # 插入到 sys.path 最前面，优先加载 backend

# 3. 其他基础导入
import tempfile
from pathlib import Path

import streamlit as st

# 4. 导入 backend 模块（此时 sys.path 已正确，且无循环）
from backend.app.db import SessionLocal, init_db
from backend.app.settings import settings
from backend.app import models
from backend.app.services.ingest import save_upload
from backend.app.services.rag import answer_question, solve_problem


def _ensure_data_dir() -> None:
    # Streamlit Cloud: prefer writable local folder
    if "DATA_DIR" not in os.environ:
        os.environ["DATA_DIR"] = str(Path("data").absolute())


_ensure_data_dir()
init_db()


st.set_page_config(page_title="学习助手", layout="wide")
st.title("学科专属学习助手")
st.caption("基于上传资料的智能问答与解题系统")


@st.cache_data(show_spinner=False)
def list_subjects() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(models.Subject).filter(models.Subject.archived == False).order_by(models.Subject.created_at.desc()).all()  # noqa: E712
        return [{"id": r.id, "name": r.name, "category": r.category, "description": r.description} for r in rows]


def refresh_subjects() -> None:
    st.cache_data.clear()


with st.sidebar:
    st.subheader("学科")
    if st.button("刷新学科"):
        refresh_subjects()
    subjects = list_subjects()
    subj_options = {f"{s['name']}（{s['category']}）": s["id"] for s in subjects}
    subj_label = st.selectbox("选择学科", options=["（新建/选择）"] + list(subj_options.keys()))

    st.divider()
    st.markdown("**新建学科**")
    new_name = st.text_input("名称", placeholder="如：高等数学")
    new_cat = st.selectbox("分类", ["理工科", "文科", "专业课", "公共课"], index=0)
    new_desc = st.text_input("描述（可选）")
    if st.button("创建学科", disabled=not new_name.strip()):
        with SessionLocal() as db:
            s = models.Subject(name=new_name.strip(), category=new_cat, description=new_desc.strip())
            db.add(s)
            db.commit()
        refresh_subjects()
        st.success("已创建")
        st.rerun()


subject_id = None if subj_label == "（新建/选择）" else subj_options[subj_label]

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("上传资料入库")
    if not subject_id:
        st.info("请先在左侧选择或创建一个学科。")
    else:
        up = st.file_uploader(
            "支持 PDF/Word/PPT/Excel/TXT/Markdown/图片（图片OCR在Cloud默认关闭）",
            type=None,
            accept_multiple_files=False,
        )
        if up is not None:
            with st.spinner("上传并解析入库中…"):
                with tempfile.TemporaryDirectory() as td:
                    tmp_path = Path(td) / up.name
                    tmp_path.write_bytes(up.getbuffer())
                    with SessionLocal() as db:
                        doc = save_upload(
                            subject_id=subject_id,
                            upload_path=tmp_path,
                            original_name=up.name,
                            mime_type=up.type or "application/octet-stream",
                            db=db,
                        )
            if doc.status == "ready":
                st.success(f"入库完成：{doc.source_name}")
            else:
                st.error(f"入库失败：{doc.error or '未知错误'}")

        st.divider()
        st.markdown("**已上传资料**")
        with SessionLocal() as db:
            docs = (
                db.query(models.Document)
                .filter(models.Document.subject_id == subject_id)
                .order_by(models.Document.created_at.desc())
                .all()
            )
        if not docs:
            st.caption("暂无资料。")
        else:
            for d in docs:
                st.write(f"- `{d.source_name}` · {d.status}")
                if d.error:
                    st.caption(f"错误：{d.error}")


with col2:
    st.subheader("学科内问答 / 解题")
    if not subject_id:
        st.info("先选择学科并上传资料。")
    else:
        tab1, tab2 = st.tabs(["问答", "解题"])

        with tab1:
            q = st.text_area("输入问题", placeholder="例如：请给出某定理的表述与推导（必须来自你上传的资料）", height=120)
            if st.button("提问", key="ask_btn", disabled=not q.strip()):
                with st.spinner("检索并生成回答…"):
                    with SessionLocal() as db:
                        found, ans, cites = answer_question(subject_id, q.strip(), db)
                st.markdown("### 输出")
                st.code(ans, language="markdown")
                if cites:
                    st.markdown("### 来源")
                    for c in cites:
                        st.write(f"- `{c.source_name}` · {c.page_or_section} · {c.position_hint}")

        with tab2:
            p = st.text_area("输入题目文本", placeholder="粘贴题干（图片OCR版后续可开启）", height=120)
            if st.button("解题", key="solve_btn", disabled=not p.strip()):
                with st.spinner("检索并生成解题…"):
                    with SessionLocal() as db:
                        found, out_md, cites = solve_problem(subject_id, p.strip(), db)
                st.markdown("### 输出")
                st.code(out_md, language="markdown")
                if cites:
                    st.markdown("### 来源")
                    for c in cites:
                        st.write(f"- `{c.source_name}` · {c.page_or_section} · {c.position_hint}")

