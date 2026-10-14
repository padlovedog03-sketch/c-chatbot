from app.contracts import SourceChunk
from app.llm import build_prompt


def test_prompt_forbids_external_knowledge_and_source_correction():
    prompt = build_prompt(
        "ตัวแปรคืออะไร",
        (SourceChunk("p1", 2, "ตัวแปร", "ตัวแปรใช้เก็บข้อมูล"),),
    )

    assert "ห้ามใช้ความรู้ภายนอก" in prompt
    assert "ห้ามแก้ไข" in prompt
    assert "หน้า 2" in prompt
