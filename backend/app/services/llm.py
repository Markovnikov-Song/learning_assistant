from __future__ import annotations

from functools import lru_cache
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from backend.app.settings import settings


@lru_cache(maxsize=1)
def get_chat_llm() -> BaseChatModel:
    """
    获取Chat LLM实例，支持OpenAI兼容的API
    处理API密钥和基础URL的配置
    """
    try:
        return ChatOpenAI(
            model=settings.llm_chat_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=settings.temperature,
            timeout=60,  # 增加超时时间到 60 秒
            max_retries=5,  # 增加重试次数到 5 次
        )
    except Exception as e:
        raise ValueError(f"Failed to initialize LLM: {str(e)}")


def get_chat_llm_with_options(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    获取带有自定义选项的Chat LLM实例
    """
    try:
        return ChatOpenAI(
            model=settings.llm_chat_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=temperature or settings.temperature,
            max_tokens=max_tokens,
            timeout=60,
            max_retries=5,
        )
    except Exception as e:
        raise ValueError(f"Failed to initialize LLM with options: {str(e)}")

