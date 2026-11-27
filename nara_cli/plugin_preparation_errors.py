"""Operational hook failures are not authorization requests."""

from typing import Any


def preparation_error(results: list[Any]) -> str | None:
    """Return the first valid technical failure, before policy directive precedence."""
    for result in results:
        if not isinstance(result, dict) or result.get("action") != "error":
            continue
        message = result.get("message")
        if isinstance(message, str) and message.strip():
            return f"Tool preparation failed: {message}"
    return None
