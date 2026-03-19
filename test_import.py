#!/usr/bin/env python3
"""
测试导入backend模块是否成功
"""

import sys
import os

# 模拟Streamlit Cloud的环境
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
sys.path.insert(0, ROOT_DIR)

print(f"当前目录: {os.getcwd()}")
print(f"ROOT_DIR: {ROOT_DIR}")
print(f"sys.path: {sys.path}")

try:
    from backend.app.db import SessionLocal, init_db
    from backend.app.settings import settings
    from backend.app import models
    from backend.app.services.ingest import save_upload
    from backend.app.services.rag import answer_question, solve_problem
    print("✅ 所有backend模块导入成功!")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("测试完成!")