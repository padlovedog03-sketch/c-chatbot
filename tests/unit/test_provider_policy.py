from app.config import Settings
from app.contracts import SourceChunk
from app.llm import build_prompt


def test_model_is_configuration_driven(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "free-tier-model")

    assert Settings.from_env().gemini_model == "free-tier-model"


def test_prompt_has_no_paid_or_web_fallback_instruction():
    prompt = build_prompt("int คืออะไร", (SourceChunk("p1", 1, "ชนิดข้อมูล", "int"),))

    assert "ความรู้ภายนอก" in prompt
    assert "Google Search" not in prompt
