"""Tổng hợp nhãn chấm tay trong results/audit/*.csv.  Chạy: python -m src.audit"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[2] / "results" / "audit"
sys.stdout.reconfigure(encoding="utf-8")


def read(name):
    with open(AUDIT / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    out = defaultdict(dict)

    coh = defaultdict(list)
    for r in read("coherence.csv"):
        if r["score_0_2"].strip():
            coh[r["strategy"]].append(int(r["score_0_2"]))
    for s, v in coh.items():
        out[s]["coherence"] = f"{sum(v) / len(v):.2f}/2 (n={len(v)})"

    meta = defaultdict(lambda: [0, 0])
    filt = defaultdict(dict)
    for r in read("test_metadata.csv"):
        s = r["strategy"]
        if r["metadata_ok_0_1"].strip():
            meta[s][0] += r["metadata_ok_0_1"].strip() == "1"
            meta[s][1] += 1
        if r["question_filter"]:
            filt[s][r["qid"]] = filt[s].get(r["qid"], True) and r["filter_ok"].strip() == "1"
    for s, (ok, n) in meta.items():
        out[s]["metadata_ok"] = f"{ok}/{n}"
    for s in sorted({r["strategy"] for r in read("test_metadata.csv")}):
        q = filt.get(s, {})
        out[s]["filter_compliance_test"] = f"{sum(q.values())}/{len(q)}" if q else "N/A"

    grd = defaultdict(list)
    for r in read("grounding.csv"):
        if r["grounding_0_2"].strip():
            grd[r["strategy"]].append(int(r["grounding_0_2"]))
    for s, v in grd.items():
        out[s]["grounding"] = (f"0:{v.count(0)} 1:{v.count(1)} 2:{v.count(2)} "
                               f"| TB {sum(v) / len(v):.2f}/2 (n={len(v)})")

    out = dict(sorted(out.items()))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    (AUDIT / "audit_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
