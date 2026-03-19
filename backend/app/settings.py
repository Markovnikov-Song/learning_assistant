from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    jwt_secret: str = "CHANGE_ME"


settings = Settings()

