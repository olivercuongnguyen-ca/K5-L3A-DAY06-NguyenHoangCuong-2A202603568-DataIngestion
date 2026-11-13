"""Check data/benchmark.json before any retrieval run.

Run from starter/:  python scripts/verify_benchmark.py
Verifies that every evidence_quote really appears on its gold_page (after normalization, whitespace
collapsed) and that the benchmark meets the lab's structural rules.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.ingestion import load_pdf  # noqa: E402

MANIFEST = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["sources"][0]
BENCH = json.loads((ROOT / "data" / "benchmark.json").read_text(encoding="utf-8"))
squash = lambda s: re.sub(r"\s+", " ", s).strip()

pages = load_pdf(ROOT / MANIFEST["source_path_or_url"], MANIFEST["source_id"], MANIFEST["source_path_or_url"])
by_page = {p.page: squash(p.text) for p in pages}
excluded = set(MANIFEST["excluded_pages"])

problems: list[str] = []
questions = BENCH["questions"]
ids = [q["id"] for q in questions]
if len(ids) != len(set(ids)):
    problems.append("duplicate question ids")

for q in questions:
    qid, page = q["id"], q["gold_page"]
    if q["gold_source_id"] != MANIFEST["source_id"]:
        problems.append(f"{qid}: unknown gold_source_id {q['gold_source_id']}")
    if page in excluded or page not in by_page:
        problems.append(f"{qid}: gold_page {page} is excluded or does not exist")
        continue
    if squash(q["evidence_quote"]) not in by_page[page]:
        problems.append(f"{qid}: evidence_quote NOT found on page {page}")

splits = Counter(q["split"] for q in questions)
filters_all = [q for q in questions if q.get("filter")]
filters_test = [q for q in filters_all if q["split"] == "test"]
print(f"questions: {len(questions)}  splits: {dict(splits)}")
print(f"types: {dict(Counter(q['type'] for q in questions))}")
print(f"filter questions: {len(filters_all)} (test: {len(filters_test)})")
print(f"pages used: {sorted({q['gold_page'] for q in questions})}")

if len(questions) < 20:
    problems.append("fewer than 20 questions")
if splits["dev"] < 15 or splits["test"] < 5:
    problems.append("need at least 15 dev and 5 test")
if len(filters_all) < 3 or not filters_test:
    problems.append("need >= 3 filter questions with >= 1 in test")

if problems:
    print("\nPROBLEMS:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("\nOK: all evidence quotes found and structural rules met")
