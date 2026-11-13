"""Build data/manifest.json from the PDF so page and character counts are measured, not typed.

Run from starter/:  python -I scripts/build_manifest.py
The PDF itself is not committed; the manifest records origin_url + sha256 so it can be re-fetched and verified.
"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data" / "2211.14876v1.pdf"
OUT = ROOT / "data" / "manifest.json"
SOURCE_ID = "dense-retrieval-survey-2022"
BIB_ENTRIES_FOR_REFERENCE_PAGE = 15  # a page with this many "[n]" lines is a bibliography page


def main() -> None:
    reader = PdfReader(PDF)
    texts = [unicodedata.normalize("NFC", p.extract_text() or "") for p in reader.pages]
    bib_counts = [len(re.findall(r"^\[\d+\]", t, re.M)) for t in texts]
    first_ref = next(i for i, c in enumerate(bib_counts, start=1) if c >= BIB_ENTRIES_FOR_REFERENCE_PAGE)

    pages = []
    for number, text in enumerate(texts, start=1):
        kind = "content" if number < first_ref else ("mixed_content_and_references" if number == first_ref else "references")
        pages.append({"page_id": f"{SOURCE_ID}-p{number:03d}", "page": number, "chars": len(text), "kind": kind})

    full = [p["page"] for p in pages if p["kind"] == "content"]
    mixed = [p["page"] for p in pages if p["kind"] == "mixed_content_and_references"]
    source = {
        "source_id": SOURCE_ID,
        "title": "Dense Text Retrieval based on Pretrained Language Models: A Survey",
        "authors": "Wayne Xin Zhao, Jing Liu, Ruiyang Ren, Ji-Rong Wen",
        "source_path_or_url": str(PDF.relative_to(ROOT)),
        "origin_url": "https://arxiv.org/pdf/2211.14876v1",
        "license_or_permission": (
            "arXiv non-exclusive distribution license (shown on https://arxiv.org/abs/2211.14876). "
            "Not a Creative Commons license, so the PDF is NOT redistributed in this repository: "
            "obtain it from origin_url and verify it with sha256. Used locally for research and for local embedding only."
        ),
        "accessed_at": "2026-11-13",
        "version": "arXiv v1, submitted 27 Nov 2022 (the only version listed on the abstract page when accessed)",
        "sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
        "physical_pages": len(reader.pages),
        "counted_pages": full + mixed,
        "full_content_pages": len(full),
        "partial_content_pages": mixed,
        "excluded_pages": [p["page"] for p in pages if p["kind"] == "references"],
        "counting_method": (
            f"Pages 1-{first_ref - 1} are body text (title/abstract, sections 1-10). Page {first_ref} holds the end of the "
            f"conclusion followed by the start of the reference list, so it is counted as partial and not as a full page. "
            f"Pages {first_ref + 1}-{len(reader.pages)} are bibliography only (>= {BIB_ENTRIES_FOR_REFERENCE_PAGE} '[n]' lines "
            f"marks the first reference page) and are excluded. Characters are counted after Unicode NFC normalization, "
            f"before line-joining. Printed page numbers equal PDF page numbers."
        ),
        "known_text_noise": [
            "Each page starts with its printed page number on its own line",
            "Page 1 contains the arXiv stamp 'arXiv:2211.14876v1 [cs.IR] 27 Nov 2022'",
            "Two-column layout: tables and figure captions can appear before or inside body text",
        ],
        "total_chars": sum(p["chars"] for p in pages),
        "pages": pages,
    }
    OUT.write_text(json.dumps({"sources": [source]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {source['physical_pages']} physical pages, {len(full)} full + {len(mixed)} partial "
          f"content pages, first reference page {first_ref}, {source['total_chars']} chars")


if __name__ == "__main__":
    main()
