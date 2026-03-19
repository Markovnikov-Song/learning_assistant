## learning_assistant（学科专属 RAG 智能学习助手）

本仓库是「学科专属RAG智能学习助手」的可上线全栈实现，核心原则：

- **严格资料内生成**：所有回答/解题/预测/图谱，只允许基于「当前学科」用户上传/导入资料检索到的证据生成；无证据必须明确告知“未找到相关内容”，**禁止编造**。
- **学科隔离**：每个学科独立存储与独立向量库，检索严格按 `subject_id` 过滤，禁止跨学科召回。
- **理工科优先**：公式/推导/计算题/证明题优先保证可用性；前端支持 LaTeX 渲染。

## 目录结构

- `backend/` FastAPI 后端：学科/资料管理、解析入库、RAG 问答与解题
- `frontend/` React 前端（Vite）：三步核心流程 + 简洁管理界面
- `streamlit_app/` Streamlit Cloud 入口（复用后端核心逻辑）
- `docker/` 云端 Docker 部署文件

## 快速开始（本地开发）

### 后端

```bash
cd backend
conda env create -f environment.yml
conda activate rag-assistant
pip install -r requirements-core.txt
# 如需OCR（图片/扫描版PDF识别）再安装：
# pip install -r requirements-ocr.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认访问 `http://localhost:8000`。

## 部署

- **本地一键**：见 `scripts/`（后续补齐打包与一键启动）
- **Streamlit Cloud**：见 `streamlit_app/`

