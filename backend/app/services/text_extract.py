from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.settings import settings
from backend.app.services.ocr_optional import ocr_image_maybe


@dataclass
class ExtractedPage:
    text: str
    page_or_section: str = ""
    position_hint: str = ""


def _ocr_image(path: Path) -> str:
    return ocr_image_maybe(path)


def extract_text_with_metadata(path: Path) -> list[ExtractedPage]:
    """
    Return a list of pages/sections with best-effort metadata.
    Must be robust for STEM documents; if text is not extractable, fall back to OCR for images.
    """
    suffix = path.suffix.lower()

    if suffix in {".png", ".jpg", ".jpeg"}:
        return [ExtractedPage(text=_ocr_image(path), page_or_section="image", position_hint="full")]

    if suffix in {".txt", ".md"}:
        return [ExtractedPage(text=path.read_text(encoding="utf-8", errors="ignore"), page_or_section="text", position_hint="full")]

    # PDFs: try text first (pypdf); scanned PDFs will yield empty -> user can re-upload as images or we extend later.
    if suffix == ".pdf":
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        pages: list[ExtractedPage] = []
        for i, p in enumerate(reader.pages):
            t = (p.extract_text() or "").strip()
            pages.append(ExtractedPage(text=t, page_or_section=f"p.{i+1}", position_hint="full"))
        return pages

    # Office formats: use unstructured as a generic fallback.
    try:
        from unstructured.partition.auto import partition  # type: ignore

        elements = partition(filename=str(path))
        text = "\n".join([str(e) for e in elements if str(e).strip()])
        return [ExtractedPage(text=text, page_or_section="doc", position_hint="full")]
    except Exception:
        return [ExtractedPage(text="", page_or_section="unknown", position_hint="full")]

