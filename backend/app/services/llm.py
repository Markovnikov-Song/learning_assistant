from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.settings import settings


@lru_cache(maxsize=1)
def get_chat_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_chat_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.temperature,
    )

