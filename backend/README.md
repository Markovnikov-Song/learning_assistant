## 后端（FastAPI + LangChain RAG）

### Conda 环境（推荐）

```bash
cd backend
conda env create -f environment.yml
conda activate rag-assistant
```

### 依赖说明

- `requirements-core.txt`：**P0必需**（学科/资料/入库/问答/解题）
- `requirements-ocr.txt`：**可选**（PaddleOCR，用于图片/扫描资料识别）

安装核心依赖：

```bash
pip install -r requirements-core.txt
```

需要 OCR 再安装：

```bash
pip install -r requirements-ocr.txt
```

### 启动

```bash
uvicorn app.main:app --reload --port 8000
```

### 环境变量

复制 `backend/.env.example` 为 `backend/.env`，至少配置一个 OpenAI-compatible 的 `LLM_API_KEY`（以及必要时的 `LLM_BASE_URL`）。

