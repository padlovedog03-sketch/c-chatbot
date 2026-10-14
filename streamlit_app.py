"""Streamlit entrypoint for the C Language PDF Q&A chatbot."""

from __future__ import annotations


def run() -> None:
    import streamlit as st

    from app.config import Settings
    from app.dataset import DatasetError, DatasetLoader
    from app.guards import RequestGuard, verify_password
    from app.llm import GeminiClient
    from app.retrieval import LexicalRetriever
    from app.service import AnswerService

    st.set_page_config(
        page_title="C Language PDF Q&A", page_icon="C", layout="centered"
    )
    st.title("C Language PDF Q&A")
    st.caption("ตอบตาม Dataset ภาษา C เท่านั้น อาจไม่ตรงกับมาตรฐานภาษา C ปัจจุบัน")

    settings = Settings.from_env()
    if not settings.access_password:
        st.error("ระบบยังไม่ได้ตั้งค่า APP_ACCESS_PASSWORD")
        st.stop()

    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("history", [])
    st.session_state.setdefault(
        "request_guard",
        RequestGuard(
            min_interval_seconds=settings.request_min_interval_seconds,
            max_question_chars=settings.max_question_chars,
            duplicate_suppression_seconds=settings.duplicate_suppression_seconds,
        ),
    )

    if not st.session_state["authenticated"]:
        with st.form("access-form"):
            password = st.text_input("Access password", type="password")
            submitted = st.form_submit_button("เข้าใช้งาน")
        if submitted:
            if verify_password(password, settings.require_access_password()):
                st.session_state["authenticated"] = True
                st.rerun()
            st.error("รหัสผ่านไม่ถูกต้อง")
        st.stop()

    @st.cache_resource(show_spinner="กำลังอ่าน Dataset...")
    def build_service(dataset_path: str, model: str) -> AnswerService:
        del model  # model is a cache key; the client reads the full settings object.
        chunks = DatasetLoader().load(settings.dataset_pdf_path)
        return AnswerService(LexicalRetriever(chunks), GeminiClient(settings))

    try:
        service = build_service(str(settings.dataset_pdf_path), settings.gemini_model)
    except DatasetError as exc:
        st.error(str(exc))
        st.stop()

    def render_citations(citations) -> None:
        with st.expander("ดูแหล่งอ้างอิง", expanded=False):
            st.caption(
                "แหล่งอ้างอิง: "
                + "; ".join(
                    f"หน้า {chunk.page_number} ({chunk.section_heading or 'ไม่ระบุหัวข้อ'})"
                    for chunk in citations
                )
            )

    for role, content, citations in st.session_state["history"]:
        with st.chat_message(role):
            st.markdown(content)
            if role == "assistant" and citations:
                render_citations(citations)

    question = st.chat_input("ถามเกี่ยวกับภาษา C จาก Dataset...")
    if not question:
        return

    decision = st.session_state["request_guard"].check(question)
    if not decision.allowed:
        st.warning(decision.reason)
        return

    st.session_state["history"].append(("user", question, ()))
    with st.chat_message("user"):
        st.markdown(question)

    history_pairs = tuple(
        (
            st.session_state["history"][index][1],
            st.session_state["history"][index + 1][1],
        )
        for index in range(0, max(len(st.session_state["history"]) - 1, 0), 2)
        if st.session_state["history"][index][0] == "user"
        and index + 1 < len(st.session_state["history"])
        and st.session_state["history"][index + 1][0] == "assistant"
    )
    with st.chat_message("assistant"):
        with st.status("กำลังประมวลผลคำถาม...", expanded=True) as progress:
            st.write("กำลังตรวจสอบคำถามกับ Dataset ภาษา C")
            st.write("กำลังค้นหาและวิเคราะห์เนื้อหาที่เกี่ยวข้อง")
            result = service.ask(
                question, history_pairs, top_k=settings.retrieval_top_k
            )
            st.write("กำลังเตรียมคำตอบและแหล่งอ้างอิง")
            if result.status == "answered":
                progress.update(label="ตอบเสร็จแล้ว", state="complete", expanded=False)
            elif result.status == "refused":
                progress.update(
                    label="ไม่พบข้อมูลใน Dataset", state="complete", expanded=False
                )
            else:
                progress.update(
                    label="ระบบไม่สามารถตอบได้", state="error", expanded=False
                )
        answer = result.answer_text or result.user_message
        st.markdown(answer)
        if result.citations:
            render_citations(result.citations)
    st.session_state["history"].append(("assistant", answer, result.citations))


if __name__ == "__main__":
    run()
