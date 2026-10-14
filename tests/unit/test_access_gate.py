from app.config import Settings
from app.guards import verify_password


def test_password_comparison_accepts_only_exact_secret():
    assert verify_password("classroom", "classroom") is True
    assert verify_password("classroom ", "classroom") is False


def test_settings_repr_does_not_expose_secrets(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "secret-key-value")
    monkeypatch.setenv("APP_ACCESS_PASSWORD", "secret-password")

    rendered = repr(Settings.from_env())

    assert "secret-key-value" not in rendered
    assert "secret-password" not in rendered
    assert "<set>" in rendered
