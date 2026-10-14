from pathlib import Path


def test_app_does_not_define_conversation_database_files():
    app_files = list(Path("app").glob("*.py"))

    assert not any(path.name in {"database.py", "storage.py"} for path in app_files)
