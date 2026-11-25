"""Small regex callbacks split out to keep the redaction facade maintainable."""

from __future__ import annotations

from typing import Match


def mask_network_path_userinfo(match: Match[str]) -> str:
    """Mask ``//user:pass@host`` while preserving documented placeholders."""

    from agent.redact import _is_userinfo_placeholder

    if _is_userinfo_placeholder(match.group(3)):
        return match.group(0)
    return f"{match.group(1)}{match.group(2)}:***@"


def redact_phone(match: Match[str]) -> str:
    """Keep enough digits to identify a phone without exposing it in full."""

    phone = match.group(1)
    keep = 2 if len(phone) <= 8 else 4
    return phone[:keep] + "****" + phone[-keep:]
