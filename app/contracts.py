"""Small immutable contracts shared by the chatbot components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    page_number: int
    section_heading: str | None
    text: str


@dataclass(frozen=True)
class RetrievedContext:
    chunks: tuple[SourceChunk, ...]
    query: str


@dataclass(frozen=True)
class AnswerResult:
    status: Literal["answered", "refused", "unavailable", "blocked"]
    answer_text: str | None
    citations: tuple[SourceChunk, ...]
    user_message: str


@dataclass(frozen=True)
class SessionState:
    authenticated: bool
    history: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str | None = None
