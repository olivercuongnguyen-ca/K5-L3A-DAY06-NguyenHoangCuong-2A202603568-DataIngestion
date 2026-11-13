"""Build data/manifest.json from the PDF so page and character counts are measured, not typed.

Run from the repo root:  python -I starter/scripts/build_manifest.py
Rebuild whenever the PDF changes; sha256 in the manifest identifies the exact file.
"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
PDF = ROOT / "data" / "2402.06196v3.pdf"
OUT = ROOT / "data" / "manifest.json"
SOURCE_ID = "llm-survey-2024"
BIB_LINES_FOR_REFERENCE_PAGE = 10  # a page with this many "[n]" lines is a bibliography page
REFERENCES_HEADING = re.compile(r"^\s*REFERENCES\s*$", re.M)


def main() -> None:
    reader = PdfReader(PDF)
    texts = [unicodedata.normalize("NFC", p.extract_text() or "") for p in reader.pages]
    bib_counts = [len(re.findall(r"^\[\d+\]", t, re.M)) for t in texts]

    heading_page = next(i for i, t in enumerate(texts, start=1) if REFERENCES_HEADING.search(t))
    last_ref_page = max(i for i, c in enumerate(bib_counts, start=1) if c >= BIB_LINES_FOR_REFERENCE_PAGE)

    pages = []
    for number, text in enumerate(texts, start=1):
        if number < heading_page or number > last_ref_page:
            kind = "content"
        elif number == heading_page:
            kind = "mixed_content_and_references"
        else:
            kind = "references"
        pages.append({"page_id": f"{SOURCE_ID}-p{number:03d}", "page": number, "chars": len(text), "kind": kind})

    full = [p["page"] for p in pages if p["kind"] == "content"]
    mixed = [p["page"] for p in pages if p["kind"] == "mixed_content_and_references"]
    refs = [p["page"] for p in pages if p["kind"] == "references"]
    source = {
        "source_id": SOURCE_ID,
        "title": "Large Language Models: A Survey",
        "authors": "Shervin Minaee, Tomas Mikolov, Narjes Nikzad, Meysam Chenaghlu, Richard Socher, Xavier Amatriain, Jianfeng Gao",
        "source_path_or_url": str(PDF.relative_to(ROOT)),
        "origin_url": "https://arxiv.org/pdf/2402.06196v3",
        "license_or_permission": (
            "Creative Commons Attribution 4.0 International (CC BY 4.0), as shown on https://arxiv.org/abs/2402.06196 "
            "(license link https://creativecommons.org/licenses/by/4.0/). Redistribution allowed with attribution to the authors."
        ),
        "accessed_at": "2026-11-13",
        "version": "arXiv v3 (PDF stamp: 23 Mar 2025); v1 submitted 9 Feb 2024; the abstract page lists v1-v3",
        "sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
        "physical_pages": len(reader.pages),
        "counted_pages": sorted(full + mixed),
        "full_content_pages": len(full),
        "partial_content_pages": mixed,
        "excluded_pages": refs,
        "counting_method": (
            f"Body text is pages 1-{heading_page - 1}. Page {heading_page} holds the last lines of the conclusion followed by the "
            f"REFERENCES heading, so it is counted as partial, not as a full page. Pages {heading_page + 1}-{last_ref_page} are "
            f"bibliography only (>= {BIB_LINES_FOR_REFERENCE_PAGE} '[n]' lines) and are excluded. Pages {last_ref_page + 1}-"
            f"{len(reader.pages)} are appendix content placed after the references (tools and vector databases) and are counted. "
            f"Characters are counted after Unicode NFC normalization, before line-joining. Printed page numbers equal PDF page numbers."
        ),
        "known_text_noise": [
            "Page 1 contains the arXiv stamp 'arXiv:2402.06196v3 [cs.CL] 23 Mar 2025'",
            "Two-column layout: tables, figure captions and table cells can appear before or inside body text",
            "Large tables (e.g. benchmark results) extract as short space-separated lines with little prose",
        ],
        "total_chars": sum(p["chars"] for p in pages),
        "pages": pages,
    }
    OUT.write_text(json.dumps({"sources": [source]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {source['physical_pages']} physical pages, {len(full)} full + {len(mixed)} partial "
          f"content pages, references p{heading_page}-{last_ref_page}, {source['total_chars']} chars")


if __name__ == "__main__":
    main()
