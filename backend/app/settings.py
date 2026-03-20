from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_env_value(key: str, default: str | None = None) -> str | None:
    """获取环境变量，支持 Streamlit Secrets"""
    # 尝试从 os.environ 获取
    value = os.environ.get(key)
    if value is not None:
        return value
    
    # 尝试从 Streamlit Secrets 获取（如果可用）
    try:
        import streamlit as st
        if hasattr(st, 'secrets'):
            # 使用安全的方式访问 secrets，避免抛出异常
            if hasattr(st.secrets, '_is_loaded') and st.secrets._is_loaded():
                try:
                    return st.secrets[key]
                except KeyError:
                    return default
            else:
                # Secrets还未加载，返回默认值
                return default
    except (ImportError, Exception):
        # 如果导入失败或访问失败，返回默认值
        pass
    
    return default


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local_single", "cloud_multi"] = "local_single"
    data_dir: Path = Path("data")

    # RAG defaults (must be deterministic to reduce hallucinations)
    temperature: float = 0.0
    retrieval_top_k: int = 5

    # OpenAI-compatible config (DeepSeek/硅基流动/通义等通常兼容)
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_chat_model: str = "gpt-4o-mini"
    llm_embedding_model: str = "text-embedding-3-large"

    # Chunking tuned for STEM
    chunk_size_tokens: int = 450
    chunk_overlap_tokens: int = 90

    # OCR
    ocr_enabled: bool = True
    ocr_lang: str = "ch"

    # Security (cloud mode)
    # 生产环境请务必通过环境变量设置 JWT_SECRET
    # 开发环境会自动生成一个随机值
    jwt_secret: str = secrets.token_urlsafe(32)


settings = Settings()

# 尝试从 Streamlit Secrets 覆盖 LLM 配置
_llm_api_key = _get_env_value("LLM_API_KEY")
if _llm_api_key:
    settings.llm_api_key = _llm_api_key

_llm_base_url = _get_env_value("LLM_BASE_URL")
if _llm_base_url:
    settings.llm_base_url = _llm_base_url

_llm_chat_model = _get_env_value("LLM_CHAT_MODEL")
if _llm_chat_model:
    settings.llm_chat_model = _llm_chat_model

_llm_embedding_model = _get_env_value("LLM_EMBEDDING_MODEL")
if _llm_embedding_model:
    settings.llm_embedding_model = _llm_embedding_model

_jwt_secret = _get_env_value("JWT_SECRET")
if _jwt_secret:
    settings.jwt_secret = _jwt_secret