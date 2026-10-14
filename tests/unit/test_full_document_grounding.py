from types import SimpleNamespace

from app.config import Settings
from app.contracts import SourceChunk
from app.llm import GeminiClient, build_prompt, cited_page_numbers


def test_prompt_declares_full_pdf_as_primary_source():
    prompt = build_prompt("อธิบายบทที่ 5", ())

    assert "PDF ฉบับเต็ม" in prompt
    assert "citation hints" in prompt
    assert "ห้ามใช้ความรู้ภายนอก" in prompt


def test_model_page_references_are_mapped_as_citation_candidates():
    assert cited_page_numbers("อธิบายจากหน้า 8 และ page 10") == (8, 10)


def test_prompt_keeps_local_citation_hints_without_limiting_document_scope():
    prompt = build_prompt(
        "printf ใช้ทำอะไร",
        (SourceChunk("p9", 9, "printf", "ใช้แสดงผล"),),
    )

    assert "หน้า 9" in prompt
    assert "ไม่ใช่ขอบเขตข้อมูล" in prompt


def test_rag_prompt_contains_retrieved_chunk_and_does_not_attach_full_pdf():
    prompt = build_prompt(
        "printf ใช้ทำอะไร",
        (SourceChunk("p9", 9, "printf", "ใช้แสดงผลข้อความ"),),
        full_document=False,
    )

    assert "ใช้เฉพาะบริบทที่ค้นได้" in prompt
    assert "ใช้แสดงผลข้อความ" in prompt
    assert "ไฟล์ PDF ฉบับเต็มถูกแนบ" not in prompt


def test_pdf_upload_uses_ascii_display_name_and_is_cached(tmp_path, monkeypatch):
    from google import genai

    pdf_path = tmp_path / "DatasetภาษาC.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    calls = []

    class FakeFiles:
        def upload(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(uri="https://files.example/dataset")

    class FakeClient:
        def __init__(self, api_key):
            self.files = FakeFiles()

    monkeypatch.setattr(genai, "Client", FakeClient)
    settings = Settings("key", "model", "password", pdf_path)
    client = GeminiClient(settings)

    assert client._upload_document("key") == "https://files.example/dataset"
    assert client._upload_document("key") == "https://files.example/dataset"
    assert len(calls) == 1
    assert calls[0]["config"]["display_name"].isascii()


def test_rag_generation_does_not_upload_pdf(tmp_path, monkeypatch):
    import langchain_google_genai

    pdf_path = tmp_path / "DatasetภาษาC.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    settings = Settings("key", "model", "password", pdf_path)
    client = GeminiClient(settings)

    def fail_upload(_api_key):
        raise AssertionError("RAG path must not upload the full PDF")

    class FakeModel:
        def __init__(self, **kwargs):
            del kwargs

        def invoke(self, messages):
            assert "ใช้แสดงผลข้อความ" in messages[0].content[0]["text"]
            assert len(messages[0].content) == 1
            return SimpleNamespace(content="คำตอบจากบริบท RAG")

    monkeypatch.setattr(client, "_upload_document", fail_upload)
    monkeypatch.setattr(langchain_google_genai, "ChatGoogleGenerativeAI", FakeModel)

    assert (
        client.generate(
            "printf ใช้ทำอะไร",
            (SourceChunk("p9", 9, "printf", "ใช้แสดงผลข้อความ"),),
        )
        == "คำตอบจากบริบท RAG"
    )
