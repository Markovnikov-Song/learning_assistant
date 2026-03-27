# 1. 未来特性导入（必须第一行）
from __future__ import annotations

# 2. 调整 sys.path（优先导入 backend）
import sys
import os

# 获取当前文件的目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录（learning_assistant/）
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../"))

# 确保根目录在sys.path中
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# 确保backend目录在sys.path中
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 3. 其他基础导入
import json
import shutil
import tempfile
import time
import datetime as dt
from pathlib import Path

import streamlit as st

# 4. 导入 backend 模块（此时 sys.path 已正确，且无循环）
# 使用绝对导入
try:
    from backend.app.db import SessionLocal, init_db
    from backend.app.settings import settings
    from backend.app import models
    from backend.app.services.ingest import save_upload
    from backend.app.services.rag import answer_question, solve_problem
    from backend.app.services.auth import authenticate_user, get_password_hash
except ImportError as e:
    st.error(f"导入模块失败: {e}")
    st.error("请确保在项目根目录运行，或者 backend 目录在 Python 路径中")
    st.stop()


# 从 Streamlit Secrets 更新 settings
# 这必须在导入 streamlit 后执行
if hasattr(st, 'secrets'):
    if 'LLM_API_KEY' in st.secrets:
        settings.llm_api_key = st.secrets['LLM_API_KEY']
    if 'LLM_BASE_URL' in st.secrets:
        settings.llm_base_url = st.secrets['LLM_BASE_URL']
    if 'LLM_CHAT_MODEL' in st.secrets:
        settings.llm_chat_model = st.secrets['LLM_CHAT_MODEL']
    if 'LLM_EMBEDDING_MODEL' in st.secrets:
        settings.llm_embedding_model = st.secrets['LLM_EMBEDDING_MODEL']
    if 'JWT_SECRET' in st.secrets:
        settings.jwt_secret = st.secrets['JWT_SECRET']
    if 'DATABASE_URL' in st.secrets:
        db_url = st.secrets['DATABASE_URL']
        os.environ["DATABASE_URL"] = db_url
        settings.database_url = db_url
    if 'DATA_DIR' in st.secrets:
        os.environ["DATA_DIR"] = st.secrets['DATA_DIR']
        settings.data_dir = Path(st.secrets['DATA_DIR'])


def _ensure_data_dir() -> None:
    if "DATA_DIR" not in os.environ:
        # Streamlit Cloud 上 /mount/data 没有写权限，用 /tmp 代替
        # /tmp 在 Streamlit Cloud 上可写，但重启会清空（文件用 DB 持久化）
        candidates = [
            Path("/tmp/learning_assistant_data"),
            Path(ROOT_DIR) / "data",
        ]
        for p in candidates:
            try:
                p.mkdir(parents=True, exist_ok=True)
                # 测试写权限
                test_file = p / ".write_test"
                test_file.touch()
                test_file.unlink()
                os.environ["DATA_DIR"] = str(p)
                break
            except (PermissionError, OSError):
                continue
    settings.data_dir = Path(os.environ["DATA_DIR"])


_ensure_data_dir()
init_db()


# 导入认证相关模块
from backend.app.services.auth import authenticate_user, get_password_hash, create_user
from fastapi import HTTPException


st.set_page_config(page_title="学习助手", layout="wide")


# 初始化会话状态
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "register_mode" not in st.session_state:
    st.session_state.register_mode = False


# 登录界面
if not st.session_state.logged_in:
    st.title("学科专属学习助手")
    st.caption("基于上传资料的智能问答与解题系统")

    # 登录/注册切换
    col1, col2 = st.columns(2)
    with col1:
        if st.button("登录", use_container_width=True):
            st.session_state.register_mode = False
            st.rerun()
    with col2:
        if st.button("注册", use_container_width=True):
            st.session_state.register_mode = True
            st.rerun()

    if st.session_state.register_mode:
        # 注册表单
        with st.form("register_form"):
            st.subheader("注册新账户")
            username = st.text_input("用户名", placeholder="请输入用户名（至少3个字符）")
            password = st.text_input("密码", type="password", placeholder="请输入密码（至少6个字符）")
            confirm_password = st.text_input("确认密码", type="password", placeholder="请再次输入密码")
            submit = st.form_submit_button("注册")

            if submit:
                if len(username) < 3:
                    st.error("用户名至少需要3个字符")
                elif len(password) < 6:
                    st.error("密码至少需要6个字符")
                elif password != confirm_password:
                    st.error("两次输入的密码不一致")
                else:
                    try:
                        with SessionLocal() as db:
                            user = create_user(db, username, password, is_admin=False)
                            st.success(f"注册成功！欢迎，{user.username}")
                            # 自动登录
                            st.session_state.logged_in = True
                            st.session_state.user_id = user.id
                            st.session_state.username = user.username
                            st.session_state.is_admin = user.is_admin
                            st.rerun()
                    except HTTPException as e:
                        st.error(e.detail)
    else:
        # 登录表单
        with st.form("login_form"):
            st.subheader("登录")
            username = st.text_input("用户名", placeholder="请输入用户名")
            password = st.text_input("密码", type="password", placeholder="请输入密码")
            submit = st.form_submit_button("登录")

            if submit:
                with SessionLocal() as db:
                    user = authenticate_user(db, username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user.id
                        st.session_state.username = user.username
                        st.session_state.is_admin = user.is_admin
                        st.success(f"登录成功！欢迎，{user.username}")
                        st.rerun()
                    else:
                        st.error("用户名或密码错误")

    st.stop()


# 主应用（已登录）
st.title("学科专属学习助手")
st.caption(f"欢迎，{st.session_state.username} - 基于上传资料的智能问答与解题系统")

if st.button("退出登录"):
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.is_admin = False
    st.rerun()


@st.cache_data(show_spinner=False)
def list_subjects() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(models.Subject).filter(models.Subject.archived == False).order_by(models.Subject.created_at.desc()).all()  # noqa: E712
        return [{"id": r.id, "name": r.name, "category": r.category, "description": r.description} for r in rows]


def refresh_subjects() -> None:
    st.cache_data.clear()


@st.cache_data(show_spinner=False)
def list_history(subject_id: str | None = None, user_id: str | None = None) -> list[dict]:
    with SessionLocal() as db:
        query = db.query(models.ConversationHistory).filter(
            models.ConversationHistory.deleted == False
        )
        if user_id:
            query = query.filter(models.ConversationHistory.user_id == user_id)
        if subject_id:
            query = query.filter(models.ConversationHistory.subject_id == subject_id)
        return [
            {
                "id": h.id,
                "question_type": h.question_type,
                "question": h.question,
                "answer": h.answer,
                "citations": h.citations,
                "found": h.found,
                "created_at": h.created_at,
            }
            for h in query.order_by(models.ConversationHistory.created_at.desc()).all()
        ]


def delete_history(history_id: str, user_id: str) -> bool:
    with SessionLocal() as db:
        h = db.query(models.ConversationHistory).filter(
            models.ConversationHistory.id == history_id,
            models.ConversationHistory.user_id == user_id,
        ).first()
        if h:
            h.deleted = True
            db.commit()
            return True
        return False


# 初始化 session_state
if "subject_id" not in st.session_state:
    st.session_state.subject_id = None

with st.sidebar:
    st.subheader("学科")
    if st.button("刷新学科"):
        refresh_subjects()
    subjects = list_subjects()
    subj_options = {f"{s['name']}（{s['category']}）": s["id"] for s in subjects}
    subj_label = st.selectbox("选择学科", options=["（新建/选择）"] + list(subj_options.keys()))

    # 更新 session_state 中的 subject_id
    st.session_state.subject_id = None if subj_label == "（新建/选择）" else subj_options[subj_label]
    subject_id = st.session_state.subject_id

    # 删除学科按钮
    if subj_label != "（新建/选择）":
        if st.button("🗑️ 删除当前学科", type="secondary", use_container_width=True):
            with SessionLocal() as db:
                s = db.query(models.Subject).filter(models.Subject.id == subj_options[subj_label]).first()
                if s:
                    # 删除学科（级联删除文档和向量索引）
                    db.delete(s)
                    db.commit()
                    # 删除磁盘上的学科文件夹
                    subject_folder = settings.data_dir / "subjects" / s.id
                    if subject_folder.exists():
                        shutil.rmtree(subject_folder, ignore_errors=True)
                    st.toast(f"学科「{s.name}」已删除", icon="🗑️")
                    refresh_subjects()
                    st.rerun()

    st.divider()
    st.markdown("**新建学科**")
    new_name = st.text_input("名称", placeholder="如：高等数学")
    new_cat = st.selectbox("分类", ["文科", "理科", "工科", "农学", "医学"], index=0)
    new_desc = st.text_input("描述（可选）")
    if st.button("创建学科", disabled=not new_name.strip()):
        with SessionLocal() as db:
            s = models.Subject(name=new_name.strip(), category=new_cat, description=new_desc.strip())
            db.add(s)
            db.commit()
        refresh_subjects()
        st.toast(f"学科「{new_name.strip()}」创建成功！", icon="✅")
        st.rerun()

    st.divider()
    
    # 会话管理
    if subject_id:
        st.markdown("**💬 会话管理**")
        
        # 初始化会话相关状态
        if "show_sessions" not in st.session_state:
            st.session_state.show_sessions = False
        if "active_session_id" not in st.session_state:
            st.session_state.active_session_id = ""
        
        # 显示当前活动会话
        if st.session_state.active_session_id:
            with SessionLocal() as db:
                active_session = db.query(models.ConversationSession).filter(
                    models.ConversationSession.id == st.session_state.active_session_id,
                    models.ConversationSession.user_id == st.session_state.user_id,
                    models.ConversationSession.subject_id == subject_id,
                ).first()
                if active_session:
                    st.info(f"当前会话: {active_session.title}")
                    if st.button("退出会话", key="exit_session", use_container_width=True):
                        st.session_state.active_session_id = ""
                        st.rerun()
        
        # 切换会话管理面板
        if st.button("管理会话", use_container_width=True):
            st.session_state.show_sessions = not st.session_state.show_sessions
            st.rerun()
        
        # 会话管理面板
        if st.session_state.show_sessions:
            st.divider()
            
            # 新建会话
            with st.expander("新建会话", expanded=False):
                new_session_title = st.text_input("会话标题", placeholder="如：复习第1章")
                if st.button("创建会话", use_container_width=True, disabled=not new_session_title.strip()):
                    with SessionLocal() as db:
                        session = models.ConversationSession(
                            user_id=st.session_state.user_id,
                            subject_id=subject_id,
                            title=new_session_title.strip(),
                        )
                        db.add(session)
                        db.commit()
                        st.toast(f"会话「{new_session_title.strip()}」创建成功！", icon="✅")
                        st.rerun()
            
            # 会话列表
            st.markdown("**会话列表**")
            with SessionLocal() as db:
                sessions = db.query(models.ConversationSession).filter(
                    models.ConversationSession.user_id == st.session_state.user_id,
                    models.ConversationSession.subject_id == subject_id,
                    models.ConversationSession.deleted == False,
                ).order_by(models.ConversationSession.updated_at.desc()).all()
            
            if not sessions:
                st.info("暂无会话")
            else:
                for s in sessions:
                    # 计算消息数量
                    with SessionLocal() as db:
                        message_count = db.query(models.ConversationHistory).filter(
                            models.ConversationHistory.session_id == s.id,
                            models.ConversationHistory.deleted == False,
                        ).count()
                    
                    with st.expander(f"{s.title} ({message_count} 条消息)", expanded=(s.id == st.session_state.active_session_id)):
                        col1, col2, col3 = st.columns([1, 1, 1])
                        
                        with col1:
                            if s.id != st.session_state.active_session_id:
                                if st.button("进入", key=f"enter_{s.id}", use_container_width=True):
                                    st.session_state.active_session_id = s.id
                                    st.rerun()
                            else:
                                st.success("当前会话")
                        
                        with col2:
                            if st.button("编辑标题", key=f"edit_{s.id}", use_container_width=True):
                                new_title = st.text_input("新标题", value=s.title, key=f"title_{s.id}")
                                if st.button("保存", key=f"save_{s.id}"):
                                    with SessionLocal() as db:
                                        session = db.query(models.ConversationSession).filter(
                                            models.ConversationSession.id == s.id
                                        ).first()
                                        if session:
                                            session.title = new_title
                                            session.updated_at = dt.datetime.utcnow()
                                            db.add(session)
                                            db.commit()
                                            st.toast("标题已更新", icon="✅")
                                            st.rerun()
                        
                        with col3:
                            if st.button("删除", key=f"delete_{s.id}", use_container_width=True, type="secondary"):
                                if st.session_state.active_session_id == s.id:
                                    st.session_state.active_session_id = ""
                                with SessionLocal() as db:
                                    session = db.query(models.ConversationSession).filter(
                                        models.ConversationSession.id == s.id
                                    ).first()
                                    if session:
                                        session.deleted = True
                                        db.add(session)
                                        db.commit()
                                        st.toast("会话已删除", icon="🗑️")
                                        st.rerun()
            
            if st.button("关闭会话管理", use_container_width=True):
                st.session_state.show_sessions = False
                st.rerun()
        
        st.divider()
    
    st.markdown("**📜 历史记录**")
    if st.button("查看历史记录", use_container_width=True, disabled=not subject_id):
        history = list_history(subject_id, st.session_state.user_id)
        if history:
            for h in history:
                with st.expander(f"{'❓ 问答' if h['question_type'] == 'ask' else '✏️ 解题'} - {h['created_at'].strftime('%Y-%m-%d %H:%M')}"):
                    st.write(f"**问题**: {h['question']}")
                    st.write(f"**回答**:")
                    st.markdown(h['answer'])
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button(f"📥 导出", key=f"export_{h['id']}", use_container_width=True):
                            # 导出为 Markdown 文件
                            import json
                            citations = json.loads(h['citations'])
                            md_content = f"# {'问答' if h['question_type'] == 'ask' else '解题'}记录\n\n"
                            md_content += f"**时间**: {h['created_at'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            md_content += "## 问题\n\n"
                            md_content += f"{h['question']}\n\n"
                            md_content += "## 回答\n\n"
                            md_content += f"{h['answer']}\n\n"
                            if citations:
                                md_content += "## 来源\n\n"
                                for c in citations:
                                    md_content += f"- **{c['source_name']}**"
                                    if c.get('page_or_section'):
                                        md_content += f" · {c['page_or_section']}"
                                    if c.get('position_hint'):
                                        md_content += f" · {c['position_hint']}"
                                    md_content += "\n"
                            
                            st.download(
                                md_content,
                                f"history_{h['id']}.md",
                                mime="text/markdown",
                                key=f"download_{h['id']}"
                            )
                    with col2:
                        if st.button(f"🗑️ 删除", key=f"delete_{h['id']}", type="secondary", use_container_width=True):
                            if delete_history(h['id'], st.session_state.user_id):
                                st.toast("已删除", icon="🗑️")
                                st.rerun()
        else:
            st.info("暂无历史记录")


col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("上传资料入库")
    if not subject_id:
        st.info("请先在左侧选择或创建一个学科。")
    else:
        st.caption("💡 小贴士：500页的书籍约需20-60分钟处理，处理期间请保持页面打开")
        up = st.file_uploader(
            "支持 PDF/Word/PPT/Excel/TXT/Markdown/图片（图片OCR在Cloud默认关闭）",
            type=None,
            accept_multiple_files=False,
        )
        if up is not None:
            # 检查文件大小并给出警告
            file_size_mb = len(up.getbuffer()) / (1024 * 1024)
            if file_size_mb > 10:  # 超过10MB
                st.warning(f"⚠️ 文件较大（{file_size_mb:.1f}MB），处理可能需要较长时间，请耐心等待。建议先关闭其他标签页以提高处理速度。")
            elif file_size_mb > 5:  # 超过5MB
                st.info(f"ℹ️ 文件大小：{file_size_mb:.1f}MB，处理可能需要几分钟...")
            
            doc_status = None
            doc_source_name = None
            doc_error = None
            
            # 暂时使用简单的spinner，不使用进度回调
            try:
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
                            # 在会话关闭前获取需要的属性
                            doc_status = doc.status
                            doc_source_name = doc.source_name
                            doc_error = doc.error
                
                if doc_status == "ready":
                    st.success(f"✅ 入库完成：{doc_source_name}")
                else:
                    st.error(f"❌ 入库失败：{doc_error or '未知错误'}")
            except Exception as e:
                st.error(f"❌ 处理出错：{str(e)}")

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
                        # 获取会话历史（如果有活动会话）
                        conversation_history = None
                        if st.session_state.get("active_session_id"):
                            histories = db.query(models.ConversationHistory).filter(
                                models.ConversationHistory.session_id == st.session_state.active_session_id,
                                models.ConversationHistory.deleted == False,
                            ).order_by(models.ConversationHistory.created_at.asc()).all()
                            
                            if histories:
                                conversation_history = [
                                    {"question": h.question, "answer": h.answer}
                                    for h in histories[-5:]  # 只使用最近5条历史
                                ]
                        
                        found, ans, cites = answer_question(subject_id, q.strip(), db, conversation_history)
                        
                        # 保存对话历史
                        history = models.ConversationHistory(
                            user_id=st.session_state.user_id,
                            subject_id=subject_id,
                            session_id=st.session_state.get("active_session_id"),
                            question_type="ask",
                            question=q.strip(),
                            answer=ans,
                            citations=json.dumps([c.model_dump() for c in cites]),
                            found=found,
                        )
                        db.add(history)
                        db.commit()
                        
                        # 更新会话的updated_at时间
                        if st.session_state.get("active_session_id"):
                            session = db.query(models.ConversationSession).filter(
                                models.ConversationSession.id == st.session_state.active_session_id
                            ).first()
                            if session:
                                session.updated_at = dt.datetime.utcnow()
                                db.add(session)
                                db.commit()
                
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
                        # 获取会话历史（如果有活动会话）
                        conversation_history = None
                        if st.session_state.get("active_session_id"):
                            histories = db.query(models.ConversationHistory).filter(
                                models.ConversationHistory.session_id == st.session_state.active_session_id,
                                models.ConversationHistory.deleted == False,
                            ).order_by(models.ConversationHistory.created_at.asc()).all()
                            
                            if histories:
                                conversation_history = [
                                    {"question": h.question, "answer": h.answer}
                                    for h in histories[-5:]  # 只使用最近5条历史
                                ]
                        
                        found, out_md, cites = solve_problem(subject_id, p.strip(), db, conversation_history)
                        
                        # 保存对话历史
                        history = models.ConversationHistory(
                            user_id=st.session_state.user_id,
                            subject_id=subject_id,
                            session_id=st.session_state.get("active_session_id"),
                            question_type="solve",
                            question=p.strip(),
                            answer=out_md,
                            citations=json.dumps([c.model_dump() for c in cites]),
                            found=found,
                        )
                        db.add(history)
                        db.commit()
                        
                        # 更新会话的updated_at时间
                        if st.session_state.get("active_session_id"):
                            session = db.query(models.ConversationSession).filter(
                                models.ConversationSession.id == st.session_state.active_session_id
                            ).first()
                            if session:
                                session.updated_at = dt.datetime.utcnow()
                                db.add(session)
                                db.commit()
                
                st.markdown("### 输出")
                st.code(out_md, language="markdown")
                if cites:
                    st.markdown("### 来源")
                    for c in cites:
                        st.write(f"- `{c.source_name}` · {c.page_or_section} · {c.position_hint}")

