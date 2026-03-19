from __future__ import annotations

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from app.settings import settings


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """
    OpenAI-compatible embeddings; base_url allows DeepSeek/硅基流动等网关。
    """
    return OpenAIEmbeddings(
        model=settings.llm_embedding_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

