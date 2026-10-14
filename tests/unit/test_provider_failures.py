from app.contracts import SourceChunk
from app.llm import ProviderUnavailable
from app.retrieval import LexicalRetriever
from app.service import UNAVAILABLE_MESSAGE, AnswerService


class FailingGemini:
    def generate(self, question, context, history=(), full_document=False):
        raise ProviderUnavailable("private provider detail")


def test_provider_failure_becomes_safe_unavailable_result():
    chunks = (SourceChunk("p1", 1, "ชนิดข้อมูล", "int"),)

    result = AnswerService(LexicalRetriever(chunks), FailingGemini()).ask("int")

    assert result.status == "unavailable"
    assert result.user_message == UNAVAILABLE_MESSAGE
    assert "private provider" not in result.user_message
