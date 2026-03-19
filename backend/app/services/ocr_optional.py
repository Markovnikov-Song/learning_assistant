from __future__ import annotations

from pathlib import Path

from app.settings import settings


def ocr_image_maybe(path: Path) -> str:
    """
    OCR is optional. If paddleocr is not installed, we fail soft and return empty text.
    """
    if not settings.ocr_enabled:
        return ""
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception:
        return ""

    ocr = PaddleOCR(use_angle_cls=True, lang=settings.ocr_lang, show_log=False)
    result = ocr.ocr(str(path), cls=True)
    lines: list[str] = []
    for block in result or []:
        for line in block or []:
            if not line:
                continue
            text = line[1][0]
            if text:
                lines.append(text)
    return "\n".join(lines)

