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
    # 使用非常保守的 chunk_size，进一步降低到 250，避免超过 512 限制
    safe_chunk_size = 250
    safe_overlap = 20  # 减少overlap，避免合并后超过限制
    
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
            # 强制截断到 480 tokens（留出安全边际）
            truncated_text = _truncate_to_max_tokens(c, max_tokens=480)
            
            # 验证截断后的文本
            final_token_count = _token_len(truncated_text)
            
            # 如果还是超过 480，继续截断到更小的值
            if final_token_count > 480:
                truncated_text = _truncate_to_max_tokens(truncated_text, max_tokens=450)
                final_token_count = _token_len(truncated_text)
                
                if final_token_count > 450:
                    truncated_text = _truncate_to_max_tokens(truncated_text, max_tokens=400)
                    final_token_count = _token_len(truncated_text)
                    
                    if final_token_count > 400:
                        # 极端情况：按字符数截断，大约 200 个字符对应约 400 tokens（中文情况）
                        truncated_text = truncated_text[:200]
                        final_token_count = _token_len(truncated_text)
            
            # 最后验证一次，确保绝对不会超过 512
            if final_token_count > 512:
                # 如果还是超过，取更少字符
                truncated_text = truncated_text[:150]
                final_token_count = _token_len(truncated_text)
            
            chunks.append(
                ChunkWithMeta(
                    text=truncated_text,
                    page_or_section=p.page_or_section,
                    position_hint=f"{p.position_hint}:{idx}",
                )
            )
    
    return chunks