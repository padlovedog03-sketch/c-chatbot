"""Access and request-level abuse guards."""

from __future__ import annotations

import hmac
import time
from collections.abc import Callable

from .contracts import GuardDecision


def verify_password(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


class RequestGuard:
    def __init__(
        self,
        min_interval_seconds: float = 10.0,
        max_question_chars: int = 2000,
        duplicate_suppression_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_interval_seconds = min_interval_seconds
        self.max_question_chars = max_question_chars
        self.duplicate_suppression_seconds = duplicate_suppression_seconds
        self._clock = clock
        self._last_request_at: float | None = None
        self._last_question: str | None = None

    def check(self, question: str) -> GuardDecision:
        normalized = " ".join(question.split())
        if not normalized:
            return GuardDecision(False, "กรุณาพิมพ์คำถาม")
        if len(normalized) > self.max_question_chars:
            return GuardDecision(False, "คำถามยาวเกินขีดจำกัดที่กำหนด")

        now = self._clock()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < self.min_interval_seconds:
                return GuardDecision(False, "กรุณารอสักครู่ก่อนส่งคำถามถัดไป")
            if (
                normalized == self._last_question
                and elapsed < self.duplicate_suppression_seconds
            ):
                return GuardDecision(False, "คำถามซ้ำติดกัน กรุณาเปลี่ยนคำถามหรือรอสักครู่")

        self._last_request_at = now
        self._last_question = normalized
        return GuardDecision(True)
