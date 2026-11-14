"""Pipeline Day 06: chunk -> embed -> pgvector -> top-3 -> Hit@1/Hit@3 -> xuất bảng chấm tay.

Chạy từ thư mục starter/:  python -m src.run
"""
import csv
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .corpus import RESULTS, load_corpus, load_questions, validate_benchmark
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .store import PgVectorStore

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.stdout.reconfigure(encoding="utf-8")  # terminal Windows mặc định cp1252, không in được tiếng Việt

# Hai index thật; C dùng LẠI index B -> B và C chỉ khác đúng một yếu tố: metadata filter.
INDEXES = {
    "A": {"chunking": "fixed_size", "size": 500, "overlap": 50},
    "B": {"chunking": "by_paragraph", "max_size": 1000},
}
STRATEGIES = {
    "A": {"index": "A", "use_filter": False},
    "B": {"index": "B", "use_filter": False},
    "C": {"index": "B", "use_filter": True},
}
TOP_K = 3


def make_chunks(pages, cfg):
    if cfg["chunking"] == "fixed_size":
        return [c for p in pages for c in fixed_size(p, cfg["size"], cfg["overlap"])]
    return [c for p in pages for c in by_paragraph(p, cfg["max_size"])]


def write_jsonl(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def write_csv_once(path, rows):
    """Không ghi đè file đã chấm tay; nếu đã có thì ghi ra *.new.csv."""
    if path.exists():
        path = path.with_suffix(".new.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("  ->", path.relative_to(RESULTS.parent))


def export_audit_sheets(pages, chunks_by_index, traces):
    audit = RESULTS / "audit"
    audit.mkdir(exist_ok=True)
    # 1) Coherence: 10 vị trí CỐ ĐỊNH, chọn trước khi xem điểm = giữa văn bản của 10 trang đầu
    #    (sắp theo document_id, page). Mỗi chiến lược lấy chunk phủ vị trí đó.
    rows = []
    for p in sorted(pages, key=lambda p: (p.document_id, p.page))[:10]:
        pos = len(p.text) // 2
        for name, cfg in STRATEGIES.items():
            cands = [c for c in chunks_by_index[cfg["index"]]
                     if c.document_id == p.document_id and c.page == p.page]
            cover = [c for c in cands
                     if 0 <= c.metadata["char_start"] <= pos < c.metadata["char_start"] + len(c.text)]
            c = cover[0] if cover else min(cands, key=lambda c: abs(c.metadata["char_start"] - pos))
            rows.append({"strategy": name, "position": f"{p.document_id}:p{p.page}@char{pos}",
                         "chunk_id": c.chunk_id, "chunk_chars": len(c.text), "chunk_text": c.text,
                         "score_0_2": "", "reason": ""})
    write_csv_once(audit / "coherence.csv", rows)

    # 2) Metadata + filter: 5 câu test x top-3 x 3 chiến lược
    test = [t for t in traces if t["split"] == "test"]
    write_csv_once(audit / "test_metadata.csv", [
        {"strategy": t["strategy"], "qid": t["id"], "rank": h["rank"], "chunk_id": h["chunk_id"],
         "source": h["source"], "page": h["page"], "chapter": h["metadata"].get("chapter"),
         "chapter_title": h["metadata"].get("chapter_title"),
         "question_filter": json.dumps(t["filter"], ensure_ascii=False) if t["filter"] else "",
         "filter_ok": "" if h["filter_ok"] is None else int(h["filter_ok"]),
         "metadata_ok_0_1": "", "note": "", "chunk_text": h["text"]}
        for t in test for h in t["top3"]])

    # 3) Grounding: mỗi câu test x chiến lược chấm 1 điểm cho cả top-3
    write_csv_once(audit / "grounding.csv", [
        {"strategy": t["strategy"], "qid": t["id"], "question": t["question"],
         "expected_answer": t["expected_answer"], "evidence_quote": t["evidence_quote"],
         "hit@3_auto": int(t["hit@3"]),
         "top3": "\n---\n".join(f"[{h['chunk_id']}] {h['text']}" for h in t["top3"]),
         "grounding_0_2": "", "reason": ""} for t in test])


def lib_versions():
    names = ["sentence-transformers", "torch", "transformers", "psycopg", "pymupdf", "python-dotenv"]
    out = {"python": platform.python_version()}
    for n in names:
        try:
            out[n] = version(n)
        except Exception:
            out[n] = "unknown"
    return out


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    pages, errors = load_corpus()
    questions = load_questions()
    problems = validate_benchmark(questions, pages)
    if problems:
        raise SystemExit("Benchmark chưa hợp lệ:\n" + "\n".join(problems))

    model_name = os.getenv("EMBEDDING_MODEL") or "intfloat/multilingual-e5-small"
    t0 = time.perf_counter()
    embedder = MyEmbedder(model_name)  # lỗi tải model -> dừng, không fallback sang vector giả
    stats = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": model_name, "embedding_provider": "local sentence-transformers",
        "dimensions": embedder.dimensions, "max_seq_length": embedder.max_seq_length,
        "query_prefix": "query: " if embedder.is_e5 else "", "document_prefix": "passage: " if embedder.is_e5 else "",
        "normalize_embeddings": True, "device": str(embedder.model.device),
        "model_load_seconds": round(time.perf_counter() - t0, 2), "cost_usd": 0,
        "vector_store": "PostgreSQL 16 + pgvector 0.8 (Docker image pgvector/pgvector:0.8.7-pg16)",
        "search": "exact (không tạo ANN index), cosine distance <=>", "top_k": TOP_K,
        "versions": lib_versions(),
        "pages": len(pages), "page_errors": len(errors), "indexes": {},
    }
    store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
    store.create_schema()

    chunks_by_index = {}
    for name, cfg in INDEXES.items():
        t0 = time.perf_counter()
        chunks = make_chunks(pages, cfg)
        t_chunk = time.perf_counter() - t0
        vectors = embedder.embed_documents([c.text for c in chunks])
        t_embed = time.perf_counter() - t0 - t_chunk
        store.upsert(name, chunks, vectors)
        seconds = time.perf_counter() - t0
        first = store.count(name)
        store.upsert(name, chunks, vectors)  # nạp lại cùng phiên bản -> phải không nhân đôi
        second = store.count(name)
        lens = [len(c.text) for c in chunks]
        tokens = [embedder.count_tokens(c.text) for c in chunks]
        stats["indexes"][name] = {
            **cfg, "chunks": len(chunks), "chars_total": sum(lens), "len_min": min(lens),
            "len_median": statistics.median(lens), "len_mean": round(statistics.mean(lens), 1),
            "len_max": max(lens), "tokens_total": sum(tokens), "tokens_max": max(tokens),
            "chunks_over_token_limit": sum(t > embedder.max_seq_length for t in tokens),
            "chunk_seconds": round(t_chunk, 3), "embed_seconds": round(t_embed, 2),
            "ingest_seconds_total": round(seconds, 2),
            "rows_first_load": first, "rows_after_reload": second,
            "reload_no_duplicates": first == second == len(chunks)}
        chunks_by_index[name] = chunks
        print(f"Index {name}: {len(chunks)} chunks, {seconds:.1f}s, "
              f"nạp lại không trùng = {first == second == len(chunks)}")

    qvec = {q["id"]: embedder.embed_query(q["question"]) for q in questions}
    traces = []
    for name, cfg in STRATEGIES.items():
        for q in questions:
            filt = q.get("filter") if cfg["use_filter"] else None  # câu không có filter: C chạy không lọc
            t0 = time.perf_counter()
            hits = store.search(cfg["index"], qvec[q["id"]], top_k=TOP_K, filters=filt)
            tr = evaluate_query(q, hits)
            tr.update(strategy=name, index=cfg["index"], filter_applied=filt,
                      search_ms=round((time.perf_counter() - t0) * 1000, 1))
            traces.append(tr)
        write_jsonl(RESULTS / f"traces_{name}.jsonl", [t for t in traces if t["strategy"] == name])

    summary = summarize(traces)
    for key, s in summary.items():
        ms = [t["search_ms"] for t in traces if f"{t['strategy']}/{t['split']}" == key]
        s["search_ms_median"] = statistics.median(ms)
    (RESULTS / "ingest_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "strategies.json").write_text(
        json.dumps({"indexes": INDEXES, "strategies": STRATEGIES, "top_k": TOP_K}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print("\nStrategy/Split  Hit@1   Hit@3   Split-suspect  Filter")
    for key, s in summary.items():
        print(f"{key:<15} {s['hit@1']:<7} {s['hit@3']:<7} {s['evidence_split_suspect']:<14} {s['filter_compliance']}")
    print("\nBảng chấm tay:")
    export_audit_sheets(pages, chunks_by_index, traces)


if __name__ == "__main__":
    main()
