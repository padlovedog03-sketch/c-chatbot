from app.contracts import SourceChunk
from app.retrieval import LexicalRetriever, tokenize


def test_tokenizer_keeps_c_identifiers_and_thai_bigrams():
    tokens = tokenize("ตัวแปร int printf")

    assert "int" in tokens
    assert "printf" in tokens
    assert "ตัวแปร" in tokens


def test_retriever_returns_relevant_page_with_metadata():
    chunks = (
        SourceChunk("p1", 1, "ตัวแปร", "การประกาศตัวแปร int count;"),
        SourceChunk("p2", 2, "เงื่อนไข", "คำสั่ง if และ else"),
    )

    result = LexicalRetriever(chunks).search("ประกาศตัวแปร int")

    assert [chunk.page_number for chunk in result] == [1]


def test_retriever_prioritizes_matching_section_heading():
    chunks = (
        SourceChunk("mention", 1, "ฟังก์ชัน", "ฟังก์ชันใช้ตัวแปรหลายชนิด"),
        SourceChunk("heading", 2, "ตัวแปร", "ตัวแปรใช้เก็บข้อมูล"),
    )

    result = LexicalRetriever(chunks).search("ตัวแปรคืออะไร")

    assert result[0].chunk_id == "heading"


def test_retriever_returns_no_evidence_for_unknown_question():
    chunks = (SourceChunk("p1", 1, "ตัวแปร", "การประกาศตัวแปร"),)

    assert LexicalRetriever(chunks).search("เครือข่ายคอมพิวเตอร์") == ()
