# Streamlit Cloud 部署入口文件
# 直接导入并运行streamlit_app目录中的应用
import os
import sys

# 获取当前文件的目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 确保streamlit_app目录在sys.path中
STREAMLIT_DIR = os.path.join(CURRENT_DIR, "streamlit_app")
if STREAMLIT_DIR not in sys.path:
    sys.path.insert(0, STREAMLIT_DIR)

# 运行streamlit_app目录中的app.py
from streamlit_app.app import *