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
    separators = ["\n\n", "\n", "。", ".", " ", ""]
    splitter = RecursiveCharacterTextSplitter(
        separators=separators,
        chunk_size=settings.chunk_size_tokens,
        chunk_overlap=settings.chunk_overlap_tokens,
        length_function=_token_len,
    )
    chunks: list[ChunkWithMeta] = []
    for p in pages:
        if not p.text.strip():
            continue
        for idx, c in enumerate(splitter.split_text(p.text)):
            chunks.append(
                ChunkWithMeta(
                    text=c,
                    page_or_section=p.page_or_section,
                    position_hint=f"{p.position_hint}:{idx}",
                )
            )
    return chunks

