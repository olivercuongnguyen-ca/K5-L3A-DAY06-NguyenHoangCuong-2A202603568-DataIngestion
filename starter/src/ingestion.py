"""Read and normalize source data. TODO: implement functions."""
import json
import logging
import re
import unicodedata

from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage

log = logging.getLogger(__name__)
MIN_CHARS = 50

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")   # everything except tab and newline
ARXIV_STAMP = re.compile(r"arXiv:\d{4}\.\d{4,5}v\d+\s*\[[^\]]+\]\s*\d{1,2}\s+\w+\s+\d{4}")
HYPHEN_BREAK = re.compile(r"(\w)-\n([a-z])")
HEADING = re.compile(r"^([IVX]+\.|[A-Z]\.)\s+[A-Z]")
ROMAN_HEADING = re.compile(r"^([IVX]+)\.\s+[A-Z] ?[A-Z]{2,}")

def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """TODO: extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    reader = PdfReader(path)
    pages: list[DocumentPage] = []

    for number, pdf_page in enumerate(reader.pages, start=1):
        metadata = {}
        try:
            raw = pdf_page.extract_text() or ""
        except Exception as exc:
            log.warning("page %d failed: %s", number, exc)
            raw = ""
            metadata["error"] = str(exc)

        text = normalize_text(raw)
        if len(text) < MIN_CHARS:
            metadata["empty"] = True
            log.warning("page %d has no usable text", number)

        pages.append(DocumentPage(document_id=document_id, source=source, page=number, text=text, metadata=metadata))

    assign_sections(pages)
    return pages


def assign_sections(pages: list[DocumentPage]) -> None:
    """Tag each page with the top-level section (Roman numeral) in effect at the START of the page.

    Page 1 starts before any heading, so it is tagged "front". A heading in the middle of a page only
    affects the following pages. Known limitation: pages after the references (appendix) inherit the last section.
    """
    current = "front"
    for page in pages:
        page.metadata["section"] = current
        for line in page.text.split("\n"):
            match = ROMAN_HEADING.match(line)
            if match:
                current = match.group(1)


def tag_page_kinds(pages: list[DocumentPage], manifest_path: Path) -> None:
    """Copy each page's `kind` (content / mixed_content_and_references / references) from data/manifest.json.

    The manifest is the single place that records how pages were counted, so the index follows the same rule.
    """
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["sources"]
    kinds = {}
    for source in manifest:
        for entry in source["pages"]:
            kinds[(source["source_id"], entry["page"])] = entry["kind"]
    for page in pages:
        page.metadata["kind"] = kinds[(page.document_id, page.page)]   # KeyError = pages and manifest disagree


def drop_references(pages: list[DocumentPage]) -> list[DocumentPage]:
    """Return only the pages that should be indexed: everything except bibliography-only pages."""
    return [p for p in pages if p.metadata.get("kind") != "references"]


def normalize_text(text: str) -> str:
    """TODO: normalize Unicode and whitespace without discarding useful structure."""
    text = unicodedata.normalize("NFKC", text)
    text = CONTROL_CHARS.sub(" ", text)      # math glyphs extract as \x00/\x01; PostgreSQL rejects NUL bytes
    text = ARXIV_STAMP.sub("", text)
    text = HYPHEN_BREAK.sub(r"\1\2", text)

    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]

    longest = max((len(ln) for ln in lines), default=0)
    out: list[str] = []
    for ln in lines:
        if not out:
            out.append(ln)
            continue
        prev = out[-1]
        prev_is_heading = bool(HEADING.match(prev)) and len(prev) < 80
        ends_paragraph = prev.endswith((".", ":", "?")) and len(prev) < 0.85 * longest
        if HEADING.match(ln) or ends_paragraph or prev_is_heading:
            out.append(ln)
        else:
            out[-1] = prev + " " + ln
    return "\n".join(re.sub(r"[ \t]+", " ", p) for p in out)
