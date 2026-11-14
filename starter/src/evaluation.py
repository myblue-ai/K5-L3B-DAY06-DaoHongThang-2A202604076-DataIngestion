"""Chấm truy xuất: evidence có nằm trong chunk ở đúng trang gold không."""
import re
import unicodedata
from collections import defaultdict
from typing import Any


def norm(text: str) -> str:
    """Chuẩn hóa để so khớp: NFC, chữ thường, thống nhất dấu nháy, gộp khoảng trắng."""
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub("[\u2018\u2019]", "'", text)
    text = re.sub("[\u201c\u201d]", '"', text)
    return re.sub(r"\s+", " ", text).strip()


def gold_options(q: dict[str, Any]) -> list[tuple[str, set[int], str]]:
    """Gold chính + các nguồn thay thế hợp lệ (trường 'alternatives', nếu có)."""
    opts = [q] + q.get("alternatives", [])
    out = []
    for o in opts:
        pages = o["gold_page"] if isinstance(o["gold_page"], list) else [o["gold_page"]]
        out.append((o["gold_source_id"], set(pages), norm(o["evidence_quote"])))
    return out


def evaluate_query(question, hits):
    raise NotImplementedError("Bước 7")


def summarize(traces):
    raise NotImplementedError("Bước 7")
