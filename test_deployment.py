# 测试部署环境的导入
import os
import sys

# 模拟Streamlit Cloud的部署环境
print("当前目录:", os.getcwd())
print("sys.path:", sys.path)

# 尝试导入根目录的app.py
try:
    import app
    print("✅ 成功导入根目录的app.py!")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()