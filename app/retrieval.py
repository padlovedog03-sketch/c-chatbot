"""Deterministic local lexical retrieval for Thai text and C code tokens."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from .contracts import SourceChunk

_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[\u0E00-\u0E7F]+")
_QUERY_STOP_TERMS = frozenset({"คือ", "ใช้", "ทำ", "อะไร", "อย่างไร", "หมายถึง"})


def tokenize(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for segment in _TOKEN_PATTERN.findall(text.lower()):
        if all("\u0e00" <= char <= "\u0e7f" for char in segment):
            tokens.append(segment)
            tokens.extend(
                segment[index : index + 2] for index in range(len(segment) - 1)
            )
        else:
            tokens.append(segment)
    return tuple(tokens)


class LexicalRetriever:
    def __init__(self, chunks: Sequence[SourceChunk]) -> None:
        if not chunks:
            raise ValueError("retriever requires at least one SourceChunk")
        self._chunks = tuple(chunks)
        self._tokens = tuple(
            Counter(
                tokenize(" ".join(filter(None, (chunk.section_heading, chunk.text))))
            )
            for chunk in self._chunks
        )
        self._document_frequency: Counter[str] = Counter()
        for counts in self._tokens:
            self._document_frequency.update(counts.keys())
        self._average_length = sum(
            sum(counts.values()) for counts in self._tokens
        ) / len(self._tokens)
        self._domain_terms = self._build_domain_terms()

    def _build_domain_terms(self) -> frozenset[str]:
        terms = set()
        for chunk in self._chunks:
            for source in (chunk.section_heading or "", chunk.text):
                for segment in _TOKEN_PATTERN.findall(source.lower()):
                    if all("\u0e00" <= char <= "\u0e7f" for char in segment):
                        if len(segment) >= 3:
                            terms.add(segment)
                            terms.update(
                                segment[index : index + length]
                                for length in range(3, min(10, len(segment)) + 1)
                                for index in range(len(segment) - length + 1)
                            )
                    else:
                        terms.add(segment)
        return frozenset(terms)

    def _query_domain_terms(self, query: str) -> tuple[str, ...]:
        normalized = " ".join(query.lower().split())
        for suffix in (
            "หมายถึงอะไร",
            "คืออะไร",
            "ทำอะไร",
            "ใช้อย่างไร",
            "อย่างไร",
            "คือ",
        ):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)].strip()
                break
        query_segments = _TOKEN_PATTERN.findall(normalized)
        return tuple(
            segment
            for segment in query_segments
            if segment not in _QUERY_STOP_TERMS and segment in self._domain_terms
        )

    def _has_domain_anchor(self, query: str) -> bool:
        return bool(self._query_domain_terms(query))

    def search(self, query: str, top_k: int = 4) -> tuple[SourceChunk, ...]:
        if not query.strip() or top_k <= 0:
            return ()
        # Thai character bigrams are useful for matching unsegmented text but
        # common bigrams alone are not evidence that a question belongs to the
        # Dataset. A heading/code vocabulary anchor is required before scoring.
        if not self._has_domain_anchor(query):
            return ()
        query_tokens = tokenize(query)
        anchor_terms = self._query_domain_terms(query)
        if not query_tokens:
            return ()
        query_counts = Counter(query_tokens)
        document_count = len(self._chunks)
        scored: list[tuple[float, int]] = []
        for index, counts in enumerate(self._tokens):
            document_length = sum(counts.values()) or 1
            score = 0.0
            for token, query_frequency in query_counts.items():
                term_frequency = counts.get(token, 0)
                if not term_frequency:
                    continue
                document_frequency = self._document_frequency[token]
                inverse_frequency = math.log(
                    1
                    + (document_count - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
                normalised_frequency = (
                    term_frequency
                    * 2.0
                    / (
                        term_frequency
                        + 1.2
                        * (
                            0.75
                            + 0.25 * document_length / max(self._average_length, 1.0)
                        )
                    )
                )
                score += inverse_frequency * normalised_frequency * query_frequency
            heading = (self._chunks[index].section_heading or "").lower()
            if any(term in heading for term in anchor_terms):
                score += 50.0
            if score > 0:
                scored.append((score, index))
        scored.sort(key=lambda item: (-item[0], self._chunks[item[1]].chunk_id))
        selected: list[SourceChunk] = []
        selected_pages: set[int] = set()
        for _, index in scored:
            chunk = self._chunks[index]
            if chunk.page_number in selected_pages:
                continue
            selected.append(chunk)
            selected_pages.add(chunk.page_number)
            if len(selected) >= top_k:
                break
        return tuple(selected)

    def pages(self, page_numbers: Sequence[int]) -> tuple[SourceChunk, ...]:
        wanted = set(page_numbers)
        selected: list[SourceChunk] = []
        seen: set[int] = set()
        for chunk in self._chunks:
            if chunk.page_number in wanted and chunk.page_number not in seen:
                selected.append(chunk)
                seen.add(chunk.page_number)
        return tuple(selected)
