from app.contracts import SourceChunk
from app.retrieval import LexicalRetriever
from app.service import REFUSAL_MESSAGE, AnswerService


class FakeGemini:
    def __init__(self, answer="คำตอบภาษาไทย: ใช้ int สำหรับจำนวนเต็ม"):
        self.answer = answer
        self.calls = []

    def generate(self, question, context, history=(), full_document=False):
        self.calls.append((question, context, history, full_document))
        if not context:
            return "ไม่พบข้อมูลใน Dataset ภาษา C"
        return self.answer


def test_answer_contains_application_owned_citations():
    chunks = (SourceChunk("p1", 3, "ชนิดข้อมูล", "int ใช้เก็บจำนวนเต็ม"),)
    fake = FakeGemini()

    result = AnswerService(LexicalRetriever(chunks), fake).ask("int")

    assert result.status == "answered"
    assert result.citations[0].page_number == 3
    assert fake.calls[0][1][0].chunk_id == "p1"
    assert fake.calls[0][3] is False


def test_follow_up_history_reaches_full_document_provider():
    chunks = (SourceChunk("p1", 3, "ชนิดข้อมูล", "int ใช้เก็บจำนวนเต็ม"),)
    fake = FakeGemini()

    AnswerService(LexicalRetriever(chunks), fake).ask(
        "แล้ว char ล่ะ", history=(("int คืออะไร", "ชนิดข้อมูลจำนวนเต็ม"),)
    )

    assert fake.calls[0][2] == (("int คืออะไร", "ชนิดข้อมูลจำนวนเต็ม"),)
    assert fake.calls[0][3] is True


def test_out_of_scope_question_refuses_after_full_document_scope_check():
    chunks = (SourceChunk("p1", 3, "ชนิดข้อมูล", "int ใช้เก็บจำนวนเต็ม"),)
    fake = FakeGemini()

    result = AnswerService(LexicalRetriever(chunks), fake).ask("ฐานข้อมูล SQL")

    assert result.status == "refused"
    assert result.user_message == REFUSAL_MESSAGE
    assert len(fake.calls) == 1
    assert fake.calls[0][3] is True
