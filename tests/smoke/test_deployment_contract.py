import os

import pytest


@pytest.mark.skipif(
    not os.getenv("PUBLIC_APP_URL"),
    reason="PUBLIC_APP_URL is required for deployed smoke verification",
)
def test_public_app_url_is_configured():
    assert os.environ["PUBLIC_APP_URL"].startswith(("https://", "http://"))
