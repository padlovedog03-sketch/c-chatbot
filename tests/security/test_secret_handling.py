from pathlib import Path


def test_source_has_no_common_hardcoded_secret_assignments():
    forbidden = ("AIzaSy", "sk-", "secret-key-value")
    source_files = [path for path in Path("app").rglob("*.py") if path.is_file()]

    text = "\n".join(path.read_text(encoding="utf-8") for path in source_files)

    assert not any(marker in text for marker in forbidden)
