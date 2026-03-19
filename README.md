# learning_assistant（学科专属 RAG 智能学习助手）

## 🌐 在线体验

**[https://your-learning-assistants.streamlit.app/](https://your-learning-assistants.streamlit.app/)**

本仓库是「学科专属RAG智能学习助手」的可上线全栈实现，核心原则：

- **严格资料内生成**：所有回答/解题/预测/图谱，只允许基于「当前学科」用户上传/导入资料检索到的证据生成；无证据必须明确告知"未找到相关内容"，**禁止编造**。
- **学科隔离**：每个学科独立存储与独立向量库，检索严格按 `subject_id` 过滤，禁止跨学科召回。
- **理工科优先**：公式/推导/计算题/证明题优先保证可用性；前端支持 LaTeX 渲染。

## ✨ 新功能

- **用户认证系统**：完整的用户登录/注册功能
- **权限管理**：管理员和普通用户角色分离
- **会话管理**：JWT token 认证机制

## 默认账户

管理员账户：`admin` / `123456`

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

前端默认访问 `http://localhost:5173`。

### Streamlit 应用

```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

## 部署

- **本地一键**：见 `scripts/`（后续补齐打包与一键启动）
- **Streamlit Cloud**：见 `streamlit_app/`

## 环境变量配置

### 后端必需配置

```bash
# JWT 密钥（用于 token 认证）
JWT_SECRET=your-secret-key-here-change-this-in-production

# LLM API 配置
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1  # 或其他兼容的 API
LLM_CHAT_MODEL=gpt-4o-mini
LLM_EMBEDDING_MODEL=text-embedding-3-large
```

### Streamlit Cloud 配置

**⚠️ 重要**：必须配置 LLM_API_KEY 才能使用问答和解题功能。

在 Streamlit Cloud 的 Secrets 中添加：

```toml
JWT_SECRET = "your-secret-key-here"

# 必需：LLM API 配置
LLM_API_KEY = "your-api-key-here"
LLM_BASE_URL = "https://api.openai.com/v1"  # 可选，使用 DeepSeek/通义等请修改
LLM_CHAT_MODEL = "gpt-4o-mini"
LLM_EMBEDDING_MODEL = "text-embedding-3-large"

# 可选：OCR 配置（默认关闭以减少依赖）
# OCR_ENABLED = false
```

**API Key 获取**：
- OpenAI: https://platform.openai.com/api-keys
- DeepSeek: https://platform.deepseek.com/api_keys
- 通义千问: https://dashscope.console.aliyun.com/apiKey

## 技术栈

**后端**：
- FastAPI + SQLAlchemy + SQLite
- LangChain + FAISS（RAG 框架）
- JWT 认证（python-jose + passlib）
- OpenAI 兼容 API（支持 DeepSeek、通义等）

**前端**：
- React 19 + TypeScript + Vite
- KaTeX（LaTeX 公式渲染）
- Fetch API + JWT 认证

**Streamlit 应用**：
- Streamlit 1.36+
- 云端快速部署
- 复用后端核心逻辑

## 许可证

MIT License