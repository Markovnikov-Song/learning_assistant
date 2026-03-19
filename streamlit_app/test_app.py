import streamlit as st
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

st.title("测试应用")
st.write("当前目录:", os.getcwd())
st.write("ROOT_DIR:", ROOT_DIR)
st.write("BACKEND_DIR:", BACKEND_DIR)
st.write("sys.path:", sys.path)

# 测试导入
try:
    from backend.app.settings import settings
    st.success("✅ 成功导入backend模块!")
    st.write("Settings:", settings)
except Exception as e:
    st.error(f"❌ 导入失败: {e}")
    import traceback
    st.code(traceback.format_exc())