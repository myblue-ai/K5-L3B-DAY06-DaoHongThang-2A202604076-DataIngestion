"""Đọc corpus theo manifest và kiểm tra benchmark. Chạy: python -m src.corpus [--validate]"""
import argparse
import csv
import json
from pathlib import Path

from .evaluation import gold_options, norm
from .ingestion import load_pdf
from .models import DocumentPage

ROOT = Path(__file__).resolve().parents[2]          # thư mục gốc repo
RESULTS = ROOT / "results"
MANIFEST = ROOT / "data" / "manifest.json"
QUESTIONS = ROOT / "benchmark" / "questions.json"
MIN_PAGES = 30


def expand(ranges: list[list[int]]) -> list[int]:
    return [p for start, end in ranges for p in range(start, end + 1)]


def chapter_lookup(source: dict):
    def lookup(page: int) -> dict:
        for ch in source.get("chapters", []):
            start, end = ch["pdf_pages"]
            if start <= page <= end:
                return {"chapter": ch["chapter"], "chapter_title": ch["title"]}
        return {}
    return lookup


def load_corpus(write: bool = True) -> tuple[list[DocumentPage], list[dict]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pages, errors = [], []
    for src in manifest["sources"]:
        excluded = {int(p) for p in src.get("excluded_pages", {})}
        wanted = set(expand(src["counted_pages"])) - excluded
        got, errs = load_pdf(ROOT / src["local_path"], src["source_id"],
                             src["source_path_or_url"], wanted, chapter_lookup(src))
        pages += got
        errors += errs
    if write:
        RESULTS.mkdir(exist_ok=True)
        with open(RESULTS / "pages.jsonl", "w", encoding="utf-8") as f:
            for p in pages:
                f.write(json.dumps({"document_id": p.document_id, "page": p.page, "metadata": p.metadata,
                                    "chars": len(p.text), "text": p.text}, ensure_ascii=False) + "\n")
        with open(RESULTS / "page_stats.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["document_id", "page", "chapter", "chars"])
            for p in pages:
                w.writerow([p.document_id, p.page, p.metadata.get("chapter"), len(p.text)])
        (RESULTS / "ingest_errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    if len(pages) < MIN_PAGES:
        raise SystemExit(f"Chỉ có {len(pages)} trang hợp lệ, cần ≥ {MIN_PAGES}. Xem results/ingest_errors.json")
    return pages, errors


def load_questions() -> list[dict]:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def validate_benchmark(questions: list[dict], pages: list[DocumentPage]) -> list[str]:
    """Trả về danh sách vấn đề; rỗng = hợp lệ."""
    text = {(p.document_id, p.page): norm(p.text) for p in pages}
    meta = {(p.document_id, p.page): p.metadata for p in pages}
    problems, seen = [], set()
    for q in questions:
        if q["id"] in seen:
            problems.append(f"{q['id']}: trùng id")
        seen.add(q["id"])
        if q["split"] not in ("dev", "test"):
            problems.append(f"{q['id']}: split phải là dev/test")
        opts = gold_options(q)
        if not any(quote in text.get((src, pg), "") for src, pgs, quote in opts for pg in pgs):
            problems.append(f"{q['id']}: evidence_quote KHÔNG tìm thấy ở trang gold (sau chuẩn hóa)")
        for key, value in (q.get("filter") or {}).items():
            if not any(meta.get((src, pg), {}).get(key) == value for src, pgs, _ in opts for pg in pgs):
                problems.append(f"{q['id']}: trang gold không có {key}={value!r}")
    dev = sum(q["split"] == "dev" for q in questions)
    test = sum(q["split"] == "test" for q in questions)
    filt = [q for q in questions if q.get("filter")]
    filt_test = sum(q["split"] == "test" for q in filt)
    print(f"Câu hỏi: {len(questions)} | dev {dev} | test {test} | có filter {len(filt)} (test {filt_test})")
    if dev < 15 or test < 5:
        problems.append("Cần ≥15 dev và ≥5 test")
    if len(filt) < 3 or filt_test < 1:
        problems.append("Cần ≥3 câu có filter, ≥1 câu filter thuộc test")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true", help="kiểm tra benchmark/questions.json")
    args = parser.parse_args()
    pages, errors = load_corpus()
    print(f"Trang hợp lệ: {len(pages)} | lỗi/bỏ qua: {len(errors)} | tổng ký tự: {sum(len(p.text) for p in pages)}")
    if args.validate:
        problems = validate_benchmark(load_questions(), pages)
        print("\n".join(problems) if problems else "Benchmark hợp lệ ✅")


if __name__ == "__main__":
    main()
