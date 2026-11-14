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


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    opts = gold_options(question)
    filt = question.get("filter") or {}
    top3 = []
    for rank, h in enumerate(hits[:3], start=1):
        on_gold_page = any(h["document_id"] == s and h["page"] in pgs for s, pgs, _ in opts)
        is_hit = any(h["document_id"] == s and h["page"] in pgs and quote in norm(h["text"])
                     for s, pgs, quote in opts)
        top3.append({
            "rank": rank, "chunk_id": h["chunk_id"], "document_id": h["document_id"], "source": h["source"],
            "page": h["page"], "score": round(float(h["score"]), 4), "metadata": h["metadata"],
            "text": h["text"], "on_gold_page": on_gold_page, "is_hit": is_hit,
            "filter_ok": all(h["metadata"].get(k) == v for k, v in filt.items()) if filt else None,
        })
    hit3 = any(t["is_hit"] for t in top3)
    page3 = any(t["on_gold_page"] for t in top3)
    return {
        "id": question["id"], "split": question["split"], "type": question.get("type"),
        "question": question["question"], "expected_answer": question["expected_answer"],
        "gold_source_id": question["gold_source_id"], "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"], "filter": filt or None,
        "hit@1": bool(top3) and top3[0]["is_hit"], "hit@3": hit3,
        # đúng trang nhưng không chunk nào chứa ĐỦ evidence -> nghi evidence bị cắt qua nhiều chunk
        "evidence_split_suspect": page3 and not hit3,
        "top3": top3,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list] = defaultdict(list)
    for t in traces:
        groups[f"{t['strategy']}/{t['split']}"].append(t)
    out = {}
    for key, ts in sorted(groups.items()):
        n = len(ts)
        h1 = sum(t["hit@1"] for t in ts)
        h3 = sum(t["hit@3"] for t in ts)
        f = [t for t in ts if t["filter"]]
        ok = sum(all(x["filter_ok"] for x in t["top3"]) for t in f)
        out[key] = {"N": n, "hit@1": f"{h1}/{n}", "hit@3": f"{h3}/{n}",
                    "hit@1_rate": round(h1 / n, 3), "hit@3_rate": round(h3 / n, 3),
                    "evidence_split_suspect": sum(t["evidence_split_suspect"] for t in ts),
                    "filter_compliance": f"{ok}/{len(f)}" if f else "N/A"}
    return out

