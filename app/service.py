"""Application service that keeps grounding and failure policy outside the UI."""

from __future__ import annotations

from collections.abc import Sequence

from .contracts import AnswerResult
from .llm import GeminiClient, ProviderUnavailable, cited_page_numbers
from .retrieval import LexicalRetriever

REFUSAL_MESSAGE = "ไม่พบข้อมูลนี้ใน Dataset ภาษา C"
UNAVAILABLE_MESSAGE = "Gemini unavailable — กรุณาลองใหม่ภายหลัง"


def _is_refusal(answer: str) -> bool:
    normalized = " ".join(answer.lower().split())
    return "ไม่พบข้อมูล" in normalized and "dataset ภาษา c" in normalized


class AnswerService:
    def __init__(self, retriever: LexicalRetriever, client: GeminiClient) -> None:
        self._retriever = retriever
        self._client = client

    def ask(
        self, question: str, history: Sequence[tuple[str, str]] = (), top_k: int = 4
    ) -> AnswerResult:
        if not question.strip():
            return AnswerResult("blocked", None, (), "กรุณาพิมพ์คำถาม")
        context = self._retriever.search(question, top_k=top_k)
        # Normal questions use retrieved chunks as RAG context. If the local
        # index has no confident match, ask against the approved PDF in full
        # so paraphrased document-wide questions still have a safe fallback.
        full_document = not context
        try:
            answer = self._client.generate(
                question, context, history, full_document=full_document
            )
        except ProviderUnavailable:
            return AnswerResult("unavailable", None, context, UNAVAILABLE_MESSAGE)
        if not answer.strip():
            return AnswerResult("unavailable", None, context, UNAVAILABLE_MESSAGE)
        answer = answer.strip()
        if _is_refusal(answer):
            return AnswerResult("refused", None, (), REFUSAL_MESSAGE)
        cited_pages = cited_page_numbers(answer)
        citations = self._retriever.pages(cited_pages) or context
        return AnswerResult("answered", answer, citations, "")
