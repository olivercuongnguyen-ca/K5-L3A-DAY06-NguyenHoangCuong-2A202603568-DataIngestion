"""Suggested pipeline entry point; TODO: implement the orchestration."""
import argparse
import json
import os
import platform
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import drop_references, load_pdf, tag_page_kinds
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent  # repo root: data/, benchmark/, results/
MANIFEST = REPO / "data" / "manifest.json"
BENCHMARK = REPO / "benchmark" / "benchmark.json"
RESULTS = REPO / "results"
TOP_K = 3
MIN_CONTENT_PAGES = 30

FIXED_SIZE, FIXED_OVERLAP = 500, 50
PARA_MAX_SIZE = 1200
CHUNKERS = {
    "fixed": lambda page: fixed_size(page, FIXED_SIZE, FIXED_OVERLAP),
    "para": lambda page: by_paragraph(page, PARA_MAX_SIZE),
}
STRATEGIES = {
    "A": ("fixed", False),
    "B": ("para", False),
    "C": ("para", True),
}


def main() -> None:
    """TODO:

    1. Load the corpus and benchmark; validate at least 30 content pages.
    2. Build strategies A (fixed), B (paragraph) and C (B + metadata filter).
    3. Embed with the same model and store vectors/metadata per strategy.
    4. Run the same dev/test questions and save full top-3 traces.
    5. Report retrieval metrics and prepare samples for manual assessment.

    Follow the five dimensions in ../../BENCHMARK.md.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits", default="dev,test", help="comma-separated splits to evaluate (default: dev,test)")
    splits = set(parser.parse_args().splits.split(","))

    load_dotenv(ROOT / ".env")

    source = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"][0]
    if len(source["counted_pages"]) < MIN_CONTENT_PAGES:
        raise SystemExit(f"manifest counts only {len(source['counted_pages'])} content pages; need >= {MIN_CONTENT_PAGES}")
    pages = load_pdf(REPO / source["source_path_or_url"], source["source_id"], source["source_path_or_url"])
    tag_page_kinds(pages, MANIFEST)
    pages = drop_references(pages)
    questions = [q for q in json.loads(BENCHMARK.read_text(encoding="utf-8"))["questions"] if q["split"] in splits]
    print(f"corpus: {len(pages)} indexed pages | questions: {len(questions)} ({', '.join(sorted(splits))})")

    embedder = MyEmbedder(os.environ["EMBEDDING_MODEL"])
    store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
    store.create_schema()

    chunked, timing = {}, {}
    for name, chunker in CHUNKERS.items():
        t0 = time.perf_counter()
        chunks = [c for p in pages for c in chunker(p)]
        t1 = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in chunks])
        t2 = time.perf_counter()
        chunked[name] = (chunks, vectors)
        timing[name] = {"chunks": len(chunks), "avg_chars": sum(len(c.text) for c in chunks) // len(chunks),
                        "chunk_seconds": round(t1 - t0, 3), "embed_seconds": round(t2 - t1, 3)}

    reingest = {}
    for strategy, (chunking, _) in STRATEGIES.items():
        chunks, vectors = chunked[chunking]
        t0 = time.perf_counter()
        store.upsert(strategy, chunks, vectors)
        timing[f"index_{strategy}_seconds"] = round(time.perf_counter() - t0, 3)
        first = store.count(strategy)
        store.upsert(strategy, chunks, vectors)
        reingest[strategy] = {"rows_after_first": first, "rows_after_second": store.count(strategy),
                              "expected": len(chunks)}
        assert first == reingest[strategy]["rows_after_second"] == len(chunks), f"re-ingest changed row count for {strategy}"

    traces, latency = [], {s: 0.0 for s in STRATEGIES}
    for q in questions:
        query_vector = embedder.embed_query(q["question"])
        for strategy, (_, use_filter) in STRATEGIES.items():
            filters = q.get("filter") if use_filter else None
            t0 = time.perf_counter()
            hits = store.search(strategy, query_vector, TOP_K, filters)
            latency[strategy] += time.perf_counter() - t0
            trace = evaluate_query(q, hits, filter_applied=bool(filters))
            trace["strategy"] = strategy
            trace["chunk_texts"] = [h["text"] for h in hits]
            traces.append(trace)

    summary = summarize(traces)
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "traces.jsonl").open("w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    run_info = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "splits": sorted(splits), "questions": len(questions), "indexed_pages": len(pages),
        "model": embedder.model_name, "dimensions": embedder.dimensions, "query_prefix": embedder.query_prefix,
        "metric": "cosine distance (pgvector <=>), exact search", "top_k": TOP_K, "cost_usd": 0.0,
        "params": {"A": {"chunking": "fixed", "size": FIXED_SIZE, "overlap": FIXED_OVERLAP},
                   "B": {"chunking": "para", "max_size": PARA_MAX_SIZE, "filter": False},
                   "C": {"chunking": "para", "max_size": PARA_MAX_SIZE, "filter": "section (only when the question gives one)"}},
        "timing": timing, "search_seconds_total": {s: round(v, 4) for s, v in latency.items()},
        "reingest_check": reingest,
        "versions": {"python": platform.python_version(), "fastembed": version("fastembed"),
                     "psycopg": version("psycopg"), "source_sha256": source["sha256"]},
        "summary": summary,
    }
    (RESULTS / "summary.json").write_text(json.dumps(run_info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nchunks: A={timing['fixed']['chunks']}  B=C={timing['para']['chunks']}   "
          f"embed seconds: fixed={timing['fixed']['embed_seconds']} para={timing['para']['embed_seconds']}")
    print(f"re-ingest check passed for {', '.join(reingest)} (row counts unchanged)")
    print(f"\n{'strategy/split':<12} {'n':>3} {'Hit@1':>7} {'Hit@3':>7} {'filter':>7}")
    for key, row in summary.items():
        print(f"{key:<12} {row['n']:>3} {row['hit_at_1']:>7} {row['hit_at_3']:>7} {row['filter_ok']:>7}")
    print(f"\nsaved: {RESULTS / 'traces.jsonl'}, {RESULTS / 'summary.json'}")


if __name__ == "__main__":
    main()
