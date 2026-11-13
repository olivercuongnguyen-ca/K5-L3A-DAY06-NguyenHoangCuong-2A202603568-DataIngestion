"""Implement fixed-size and structure-aware chunking."""
import re

from .models import Chunk, DocumentPage

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _make_chunk(page: DocumentPage, strategy: str, index: int, text: str) -> Chunk:
    """Single place that builds a Chunk so IDs and metadata are identical across strategies."""
    return Chunk(
        chunk_id=f"{page.document_id}-p{page.page:03d}-{strategy}-{index:03d}",
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata=dict(page.metadata),
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """TODO: split text into overlapping windows and retain page metadata.

    Implemented as strategy A: overlapping character windows; cuts words and sentences wherever the window ends.
    """
    if not 0 <= overlap < size:
        raise ValueError("overlap must be >= 0 and < size")
    step = size - overlap
    chunks = []
    for i, start in enumerate(range(0, len(page.text), step)):
        piece = page.text[start:start + size]
        if not piece.strip():
            continue
        chunks.append(_make_chunk(page, "fixed", i, piece))
        if start + size >= len(page.text):
            break
    return chunks


def _pack(units: list[str], max_size: int, sep: str) -> list[str]:
    """Greedily join consecutive units with sep without exceeding max_size (one oversized unit stays alone)."""
    out, cur = [], ""
    for u in units:
        if cur and len(cur) + len(sep) + len(u) > max_size:
            out.append(cur)
            cur = u
        else:
            cur = f"{cur}{sep}{u}" if cur else u
    if cur:
        out.append(cur)
    return out


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """TODO: group paragraphs, split oversized paragraphs and retain metadata.

    Implemented as strategy B: pack whole paragraphs; an oversized paragraph is packed by sentences instead.
    """
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    units: list[str] = []
    for line in page.text.split("\n"):
        p = line.strip()
        if not p:
            continue
        units += [p] if len(p) <= max_size else _pack(SENTENCE_END.split(p), max_size, " ")
    return [_make_chunk(page, "para", i, t) for i, t in enumerate(_pack(units, max_size, "\n"))]
