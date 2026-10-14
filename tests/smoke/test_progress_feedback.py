from pathlib import Path


def test_streamlit_ui_exposes_processing_progress():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")

    assert 'st.status("กำลังประมวลผลคำถาม...' in source
    assert "กำลังตรวจสอบคำถามกับ Dataset ภาษา C" in source
    assert "กำลังค้นหาและวิเคราะห์เนื้อหาที่เกี่ยวข้อง" in source
    assert "กำลังเตรียมคำตอบและแหล่งอ้างอิง" in source
    assert 'st.expander("ดูแหล่งอ้างอิง", expanded=False)' in source
