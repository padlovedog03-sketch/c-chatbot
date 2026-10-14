"""Environment-backed runtime configuration without secret leakage in repr."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, repr=False)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    access_password: str | None
    dataset_pdf_path: Path
    request_min_interval_seconds: float = 10.0
    max_question_chars: int = 2000
    duplicate_suppression_seconds: float = 60.0
    retrieval_top_k: int = 4
    provider_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            gemini_api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest"),
            access_password=os.getenv("APP_ACCESS_PASSWORD"),
            dataset_pdf_path=Path(os.getenv("DATASET_PDF_PATH", "DatasetภาษาC.pdf")),
            request_min_interval_seconds=float(
                os.getenv("REQUEST_MIN_INTERVAL_SECONDS", "10")
            ),
            max_question_chars=int(os.getenv("MAX_QUESTION_CHARS", "2000")),
            duplicate_suppression_seconds=float(
                os.getenv("DUPLICATE_SUPPRESSION_SECONDS", "60")
            ),
            retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "4")),
            provider_timeout_seconds=float(
                os.getenv("PROVIDER_TIMEOUT_SECONDS", "30")
            ),
        )

    def __repr__(self) -> str:
        key_state = "set" if self.gemini_api_key else "missing"
        password_state = "set" if self.access_password else "missing"
        return (
            "Settings("
            f"gemini_api_key=<{key_state}>, "
            f"access_password=<{password_state}>, "
            f"gemini_model={self.gemini_model!r}, "
            f"dataset_pdf_path={str(self.dataset_pdf_path)!r})"
        )

    def require_access_password(self) -> str:
        if not self.access_password:
            raise RuntimeError("APP_ACCESS_PASSWORD is not configured")
        return self.access_password

    def require_gemini_api_key(self) -> str:
        if not self.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured")
        return self.gemini_api_key
