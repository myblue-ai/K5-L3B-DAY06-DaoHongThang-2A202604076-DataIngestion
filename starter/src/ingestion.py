"""Đọc PDF theo từng trang, chuẩn hóa văn bản, ghi lại trang lỗi."""
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

import pymupdf

from .models import DocumentPage

MIN_CHARS = 200  # trang ít hơn số ký tự này coi là rỗng/scan
LIGATURES = {"\ufb01": "fi", "\ufb02": "fl", "\ufb00": "ff"}


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode + khoảng trắng nhưng GIỮ ranh giới đoạn (\n\n)."""
    text = unicodedata.normalize("NFC", text)          # dấu tiếng Việt về dạng dựng sẵn
    for bad, good in LIGATURES.items():                 # ký tự ghép 'ﬁ' trong PDF -> 'fi'
        text = text.replace(bad, good)
    text = text.replace("\u00ad", "").replace("\u00a0", " ")  # soft hyphen, nbsp
    text = re.sub(r"[ \t]+", " ", text)                 # nhiều space -> 1 space
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)              # tối đa 1 dòng trống
    return text.strip()


def _block_to_paragraph(raw: str) -> str:
    """Một block của PDF = một đoạn; nối các dòng bị xuống dòng do khổ giấy."""
    raw = re.sub(r"-\n(?=[a-z])", "", raw)              # 'pro-\ngram' -> 'program'
    return re.sub(r"\s*\n\s*", " ", raw).strip()


def load_pdf(path: Path, document_id: str, source: str,
             wanted: set[int] | None = None,
             page_meta: Callable[[int], dict[str, Any]] | None = None,
             ) -> tuple[list[DocumentPage], list[dict[str, Any]]]:
    """Trả về (các trang hợp lệ, danh sách lỗi). Số trang tính từ 1 như trình xem PDF."""
    pages, errors = [], []
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc, start=1):
            if wanted is not None and number not in wanted:
                continue
            try:
                blocks = page.get_text("blocks", sort=True)  # (x0,y0,x1,y1,text,no,type)
            except Exception as exc:
                errors.append({"document_id": document_id, "page": number, "error": f"extract_failed: {exc}"})
                continue
            paragraphs = [_block_to_paragraph(b[4]) for b in blocks if b[6] == 0]  # type 0 = chữ
            paragraphs = [p for p in paragraphs if len(p) > 3]                     # bỏ số trang lẻ
            text = normalize_text("\n\n".join(paragraphs))
            if len(text) < MIN_CHARS:
                errors.append({"document_id": document_id, "page": number,
                               "error": "empty_or_too_short (scan/ảnh?)", "chars": len(text)})
                continue
            meta = page_meta(number) if page_meta else {}
            pages.append(DocumentPage(document_id, source, number, text, meta))
        if wanted:
            for missing in sorted(wanted - set(range(1, doc.page_count + 1))):
                errors.append({"document_id": document_id, "page": missing, "error": "page_not_in_pdf"})
    return pages, errors
