from __future__ import annotations

from dataclasses import dataclass

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.settings import settings
from backend.app.services.text_extract import ExtractedPage


@dataclass
class ChunkWithMeta:
    text: str
    page_or_section: str
    position_hint: str


def _token_len(text: str) -> int:
    # cl100k_base covers most OpenAI-compatible tokenization needs
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def split_pages(pages: list[ExtractedPage]) -> list[ChunkWithMeta]:
    # 使用更小的 chunk_size 以确保不超过模型限制
    # 硅基流动的 BAAI/bge-large-zh-v1.5 模型限制为 512 tokens
    # 我们使用 400 tokens 作为安全值，留有余量
    safe_chunk_size = 400
    safe_overlap = 80
    
    separators = ["\n\n", "\n", "。", ".", " ", ""]
    splitter = RecursiveCharacterTextSplitter(
        separators=separators,
        chunk_size=safe_chunk_size,
        chunk_overlap=safe_overlap,
        length_function=_token_len,
    )
    
    chunks: list[ChunkWithMeta] = []
    for p in pages:
        if not p.text.strip():
            continue
        for idx, c in enumerate(splitter.split_text(p.text)):
            # 二次检查：确保不超过 512 tokens
            token_count = _token_len(c)
            if token_count > 512:
                # 如果仍然太大，强制截断
                enc = tiktoken.get_encoding("cl100k_base")
                tokens = enc.encode(c)[:512]  # 只保留前 512 个 tokens
                c = enc.decode(tokens)
            
            chunks.append(
                ChunkWithMeta(
                    text=c,
                    page_or_section=p.page_or_section,
                    position_hint=f"{p.position_hint}:{idx}",
                )
            )
    return chunks