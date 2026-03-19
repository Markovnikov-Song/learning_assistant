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
    """计算文本的 token 数量"""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _truncate_to_max_tokens(text: str, max_tokens: int = 512) -> str:
    """截断文本到最大 token 数"""
    token_count = _token_len(text)
    if token_count <= max_tokens:
        return text
    
    # 截断到最大 token 数
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)[:max_tokens]
    return enc.decode(tokens)


def split_pages(pages: list[ExtractedPage]) -> list[ChunkWithMeta]:
    """
    分割页面文本为多个块
    确保每个块都不超过 512 tokens
    """
    # 使用保守的 chunk_size，确保分割后的块不会太大
    # 考虑到中文可能占用更多 tokens，使用 350 作为 chunk_size
    safe_chunk_size = 350
    safe_overlap = 50
    
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
        
        # 分割文本
        split_texts = splitter.split_text(p.text)
        
        for idx, c in enumerate(split_texts):
            # 强制截断到 512 tokens 以内
            truncated_text = _truncate_to_max_tokens(c, max_tokens=512)
            
            # 验证截断后的文本
            final_token_count = _token_len(truncated_text)
            if final_token_count > 512:
                # 如果还是太大（理论上不应该发生），再次截断
                truncated_text = _truncate_to_max_tokens(truncated_text, max_tokens=480)
                final_token_count = _token_len(truncated_text)
                
                if final_token_count > 512:
                    # 极端情况：直接取前 300 个字符
                    truncated_text = truncated_text[:300]
                    final_token_count = _token_len(truncated_text)
            
            chunks.append(
                ChunkWithMeta(
                    text=truncated_text,
                    page_or_section=p.page_or_section,
                    position_hint=f"{p.position_hint}:{idx}",
                )
            )
    
    return chunks