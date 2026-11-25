"""The optional dashboard pairing flow must not call an absent vendor service."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from nara_cli.web_server_messaging import _telegram_onboarding_request_sync


def test_unconfigured_telegram_pairing_returns_manual_setup_hint(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ONBOARDING_URL", raising=False)
    with patch("httpx.Client") as client:
        with pytest.raises(HTTPException) as error:
            _telegram_onboarding_request_sync("POST", "/v1/telegram/pairings", body={"bot_name": "Nara"})
    assert error.value.status_code == 503
    assert "BotFather" in error.value.detail
    client.assert_not_called()
