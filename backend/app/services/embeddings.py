from __future__ import annotations

from functools import lru_cache
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

from backend.app.settings import settings


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    """
    获取OpenAI兼容的嵌入模型实例
    base_url允许使用DeepSeek/硅基流动等网关
    """
    try:
        return OpenAIEmbeddings(
            model=settings.llm_embedding_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=30,  # 添加超时设置
            max_retries=3,  # 添加重试机制
        )
    except Exception as e:
        raise ValueError(f"Failed to initialize embeddings: {str(e)}")


def get_embeddings_with_options(
    model: Optional[str] = None,
    batch_size: Optional[int] = None,
) -> Embeddings:
    """
    获取带有自定义选项的嵌入模型实例
    """
    try:
        return OpenAIEmbeddings(
            model=model or settings.llm_embedding_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            batch_size=batch_size,
            timeout=30,
            max_retries=3,
        )
    except Exception as e:
        raise ValueError(f"Failed to initialize embeddings with options: {str(e)}")

