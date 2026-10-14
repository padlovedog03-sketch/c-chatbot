from app.contracts import SourceChunk
from app.retrieval import LexicalRetriever
from app.service import AnswerService


class FakeGemini:
    def generate(self, question, context, history=(), full_document=False):
        if not context:
            return "ไม่พบข้อมูลใน Dataset ภาษา C"
        return "คำตอบจาก Dataset ภาษา C"


IN_SCOPE = (
    "ตัวแปรคืออะไร",
    "ชนิดข้อมูล int คืออะไร",
    "คำสั่ง printf ใช้ทำอะไร",
    "ฟังก์ชัน main คืออะไร",
    "อาร์เรย์คืออะไร",
)
OUT_OF_SCOPE = ("วิธีทำฐานข้อมูล SQL", "วิธีสร้างเว็บไซต์ด้วย React")


def service():
    chunks = (
        SourceChunk("p1", 1, "ตัวแปร", "ตัวแปรใช้เก็บข้อมูล"),
        SourceChunk("p2", 2, "ชนิดข้อมูล", "int เป็นชนิดข้อมูลจำนวนเต็ม"),
        SourceChunk("p3", 3, "การแสดงผล", "printf ใช้แสดงผล"),
        SourceChunk("p4", 4, "ฟังก์ชันหลัก", "main เป็นฟังก์ชันหลัก"),
        SourceChunk("p5", 5, "อาร์เรย์", "อาร์เรย์เก็บข้อมูลหลายค่า"),
    )
    return AnswerService(LexicalRetriever(chunks), FakeGemini())


def test_five_in_scope_questions_return_answers_with_sources():
    chatbot = service()

    results = [chatbot.ask(question) for question in IN_SCOPE]

    assert all(result.status == "answered" for result in results)
    assert all(result.citations for result in results)


def test_two_out_of_scope_questions_are_refused():
    chatbot = service()

    results = [chatbot.ask(question) for question in OUT_OF_SCOPE]

    assert all(result.status == "refused" for result in results)
