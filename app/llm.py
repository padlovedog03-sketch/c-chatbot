"""LangChain Gemini adapter for local RAG and full-document fallback."""

from __future__ import annotations

import io
import re
from collections.abc import Sequence

from .config import Settings
from .contracts import SourceChunk


class ProviderUnavailable(RuntimeError):
    """Raised when Gemini cannot safely produce an answer."""


def build_prompt(
    question: str,
    context: Sequence[SourceChunk],
    history: Sequence[tuple[str, str]] = (),
    full_document: bool = True,
) -> str:
    citation_hints = ", ".join(
        f"หน้า {chunk.page_number} ({chunk.section_heading or 'ไม่ระบุหัวข้อ'})"
        for chunk in context
    )
    history_text = "\n".join(f"ผู้เรียน: {q}\nผู้ช่วย: {a}" for q, a in history[-4:])
    context_text = "\n\n".join(
        f"[หน้า {chunk.page_number} | {chunk.section_heading or 'ไม่ระบุหัวข้อ'}]\n"
        f"{chunk.text}"
        for chunk in context
    )
    source_instructions = (
        "ไฟล์ PDF ฉบับเต็มถูกแนบมากับข้อความนี้แล้ว\n"
        "ให้ใช้เนื้อหาใน PDF ฉบับเต็มเป็นแหล่งความรู้หลัก ไม่ใช่เฉพาะ citation hints\n"
        f"citation hints จาก local index (อาจว่างและไม่ใช่ขอบเขตข้อมูล): "
        f"{citation_hints or '(ไม่มี)'}"
        if full_document
        else (
            "ให้ใช้เฉพาะบริบทที่ค้นได้จาก Dataset ด้านล่างเป็นแหล่งความรู้\n"
            "ถ้าบริบทไม่รองรับคำตอบ ให้ตอบว่าไม่พบข้อมูลใน Dataset ภาษา C\n"
            f"บริบทจาก local retriever:\n{context_text or '(ไม่พบบริบท)'}"
        )
    )
    return (
        "คุณเป็นผู้ช่วยสอนภาษา C ที่ตอบได้จาก Dataset ภาษา C เท่านั้น\n"
        "ห้ามใช้ความรู้ภายนอก ห้ามแก้ไขหรือรับรองความถูกต้องของ PDF และห้ามเดา\n"
        "ถ้าคำถามไม่มีคำตอบอยู่ใน PDF ให้ตอบว่าไม่พบข้อมูลใน Dataset ภาษา C\n"
        "อธิบายเป็นภาษาไทย และคงคำสั่ง/identifier/code ภาษา C เป็นภาษาอังกฤษ\n\n"
        f"ประวัติ session:\n{history_text or '(ไม่มี)'}\n\n"
        f"{source_instructions}\n\n"
        f"คำถาม:\n{question}\n\n"
        "ตอบอย่างกระชับ โดยอ้างหน้า/หัวข้อที่ปรากฏใน PDF เมื่อพบข้อมูล "
        "และห้ามสร้าง citation ที่ไม่มีอยู่จริง"
    )


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts).strip()
    return str(content).strip()


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._document_file_id: str | None = None

    def _upload_document(self, api_key: str) -> str:
        if self._document_file_id:
            return self._document_file_id
        try:
            from google import genai

            document_bytes = self._settings.dataset_pdf_path.read_bytes()
            client = genai.Client(api_key=api_key)
            uploaded = client.files.upload(
                file=io.BytesIO(document_bytes),
                config={
                    "mime_type": "application/pdf",
                    "display_name": "dataset-c-language.pdf",
                },
            )
            file_id = getattr(uploaded, "uri", None) or getattr(uploaded, "name", None)
            if not file_id:
                raise RuntimeError("Gemini Files API returned no file reference")
            self._document_file_id = str(file_id)
            return self._document_file_id
        except Exception as exc:
            raise ProviderUnavailable(
                "Gemini document upload unavailable — กรุณาลองใหม่ภายหลัง"
            ) from exc

    def generate(
        self,
        question: str,
        context: Sequence[SourceChunk],
        history: Sequence[tuple[str, str]] = (),
        full_document: bool = False,
    ) -> str:
        api_key = self._settings.require_gemini_api_key()
        prompt = build_prompt(question, context, history, full_document=full_document)
        try:
            from langchain_core.messages import HumanMessage
            from langchain_google_genai import ChatGoogleGenerativeAI

            model = ChatGoogleGenerativeAI(
                model=self._settings.gemini_model,
                google_api_key=api_key,
                temperature=0,
                max_retries=0,
                timeout=self._settings.provider_timeout_seconds,
            )
            content = [{"type": "text", "text": prompt}]
            if full_document:
                content.append(
                    {
                        "type": "file",
                        "file_id": self._upload_document(api_key),
                        "mime_type": "application/pdf",
                    }
                )
            response = model.invoke([HumanMessage(content=content)])
        except Exception as exc:
            raise ProviderUnavailable("Gemini unavailable — กรุณาลองใหม่ภายหลัง") from exc

        text = _content_to_text(getattr(response, "content", response))
        if not text:
            raise ProviderUnavailable("Gemini returned an empty answer")
        return text


def cited_page_numbers(answer: str) -> tuple[int, ...]:
    """Extract page references emitted by Gemini without trusting them as facts."""

    pages = {
        int(value)
        for value in re.findall(r"(?:หน้า|page)\s*([0-9]{1,3})", answer.lower())
    }
    return tuple(sorted(pages))
