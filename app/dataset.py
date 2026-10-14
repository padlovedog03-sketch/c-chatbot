"""PDF loading and page-preserving chunk construction."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from .contracts import SourceChunk


class DatasetError(RuntimeError):
    """Raised when the approved Dataset cannot be loaded safely."""


_HEADING_PATTERN = re.compile(
    r"^(?:บทที่\s*\d+(?:\s+.*)?|\d+(?:\.\d+)+\s*.*|[A-Z][A-Za-z ]{2,80})$"
)


def _normalise_text(text: str) -> str:
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _section_heading(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = [
        (position, line)
        for position, line in enumerate(lines[:24])
        if _HEADING_PATTERN.match(line) and len(line) <= 120
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            0 if item[1].startswith("บทที่") else item[1].split()[0].count("."),
            item[0],
        ),
        reverse=True,
    )
    heading = candidates[0][1]
    for marker in (" คือตัว", " ซึ่ง", " โดย"):
        if marker in heading:
            heading = heading.split(marker, 1)[0].strip()
    return heading


def build_chunks_from_pages(
    pages: Sequence[str], max_chars: int = 1800, overlap_chars: int = 200
) -> tuple[SourceChunk, ...]:
    if max_chars <= 0 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("chunk size must be positive and overlap must be smaller")

    chunks: list[SourceChunk] = []
    current_heading: str | None = None
    for page_number, raw_text in enumerate(pages, start=1):
        text = _normalise_text(raw_text)
        if not text:
            continue
        current_heading = _section_heading(raw_text) or current_heading
        heading = current_heading
        start = 0
        part = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    SourceChunk(
                        chunk_id=f"page-{page_number}-part-{part}",
                        page_number=page_number,
                        section_heading=heading,
                        text=chunk_text,
                    )
                )
            if end >= len(text):
                break
            start = end - overlap_chars
            part += 1
    if not chunks:
        raise DatasetError("Dataset contains no extractable text")
    return tuple(chunks)


class DatasetLoader:
    def load(self, path: Path) -> tuple[SourceChunk, ...]:
        if not path.is_file():
            raise DatasetError(f"Dataset PDF not found: {path}")
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise DatasetError("pypdf is required to load the Dataset PDF") from exc

        try:
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:
            raise DatasetError(f"Dataset PDF could not be read: {path}") from exc
        return build_chunks_from_pages(pages)
