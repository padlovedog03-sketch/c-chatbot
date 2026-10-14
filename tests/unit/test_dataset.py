import pytest

from app.dataset import DatasetError, DatasetLoader, build_chunks_from_pages


def test_build_chunks_preserves_page_and_heading_metadata():
    chunks = build_chunks_from_pages(["บทที่ 1\nตัวแปรและชนิดข้อมูล\nint count;"])

    assert chunks
    assert chunks[0].page_number == 1
    assert chunks[0].section_heading == "บทที่ 1"
    assert "int count;" in chunks[0].text


def test_loader_rejects_missing_dataset(tmp_path):
    with pytest.raises(DatasetError, match="not found"):
        DatasetLoader().load(tmp_path / "missing.pdf")


def test_empty_pages_are_not_silent_success():
    with pytest.raises(DatasetError, match="no extractable text"):
        build_chunks_from_pages(["", "   "])
