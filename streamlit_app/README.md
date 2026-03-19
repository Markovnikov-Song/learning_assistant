## Streamlit Cloud 部署（推荐）

本目录提供 `learning_assistant` 的 **单进程自包含** Streamlit 应用：上传资料→自动入库→学科内问答/解题。

### 1) 推送到 GitHub

- 仓库根目录需包含 `streamlit_app/`

### 2) Streamlit Cloud 新建 App

- **Main file path**：`streamlit_app/app.py`
- **Python 版本**：3.10（推荐）
- **Requirements**：默认会读取 `streamlit_app/requirements.txt`

### 3) 配置密钥（必须）

在 Streamlit Cloud 的 App settings → Secrets 添加（或在本地用环境变量）：

```toml
LLM_API_KEY="你的key"
# 如用 OpenAI-compatible 网关（DeepSeek/硅基流动/通义等），再加：
# LLM_BASE_URL="https://xxx/v1"
LLM_CHAT_MODEL="gpt-4o-mini"
LLM_EMBEDDING_MODEL="text-embedding-3-large"
TEMPERATURE="0"
RETRIEVAL_TOP_K="5"
OCR_ENABLED="false"
```

> 说明：Streamlit Cloud 默认不建议装 PaddleOCR（体积大、依赖复杂），因此这里默认 `OCR_ENABLED=false`。

