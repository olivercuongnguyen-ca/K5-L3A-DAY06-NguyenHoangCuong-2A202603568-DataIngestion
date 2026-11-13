"""TODO: evaluate retrieved evidence and preserve per-query traces."""
import re
from collections import defaultdict
from typing import Any

squash = lambda s: re.sub(r"\s+", " ", s).strip()


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]], filter_applied: bool = False) -> dict[str, Any]:
    """TODO: check source/page and enough gold evidence; keep hit@1 and hit@3 trace.

    Accept any documented alternative gold evidence. Do not infer human grounding
    or chunk coherence labels from exact string match.

    A chunk is a hit when it is on the gold page of the gold source AND contains a full evidence quote.
    The quote may be the main `evidence_quote` or any optional `alternative_evidence_quotes`.
    `filter_applied` says whether the search actually used the question's filter (only strategy C does), so
    filter compliance is reported only for searches that were filtered.
    """
    quotes = [squash(question["evidence_quote"])] + [squash(a) for a in question.get("alternative_evidence_quotes", [])]
    ranked = []
    for rank, h in enumerate(hits, start=1):
        on_gold_page = h["page"] == question["gold_page"] and h["document_id"] == question["gold_source_id"]
        text = squash(h["text"])
        has_evidence = any(quote in text for quote in quotes)
        ranked.append({
            "rank": rank, "chunk_id": h["chunk_id"], "page": h["page"], "section": h["section"],
            "score": round(h["score"], 4), "on_gold_page": on_gold_page,
            "contains_evidence": has_evidence, "hit": on_gold_page and has_evidence,
        })
    flt = question.get("filter")
    # Compliance is only defined when the filter was applied; an empty result counts as NOT compliant (conservative).
    checked = filter_applied and bool(flt)
    return {
        "question_id": question["id"], "split": question["split"], "question": question["question"],
        "filter": flt, "filter_applied": filter_applied, "gold_page": question["gold_page"],
        "top3": ranked,
        "hit_at_1": bool(ranked) and ranked[0]["hit"],
        "hit_at_3": any(r["hit"] for r in ranked),
        "filter_ok": (bool(ranked) and all(r["section"] == flt["section"] for r in ranked)) if checked else None,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """TODO: aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    groups = defaultdict(list)
    for t in traces:
        groups[(t["strategy"], t["split"])].append(t)
    out = {}
    for (strategy, split), ts in sorted(groups.items()):
        n = len(ts)
        with_filter = [t for t in ts if t["filter_ok"] is not None]
        out[f"{strategy}/{split}"] = {
            "n": n,
            "hit_at_1": f"{sum(t['hit_at_1'] for t in ts)}/{n}",
            "hit_at_3": f"{sum(t['hit_at_3'] for t in ts)}/{n}",
            "filter_ok": f"{sum(t['filter_ok'] for t in with_filter)}/{len(with_filter)}" if with_filter else "N/A",
        }
    return out
