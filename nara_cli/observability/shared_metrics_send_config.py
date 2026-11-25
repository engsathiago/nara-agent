"""Configuration for shared-metrics transmission."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

#: No telemetry service is operated by this project. Sending requires an explicit
#: endpoint in the profile config; an inherited environment variable cannot set it.
DEFAULT_ENDPOINT = ""
_LEGACY_UPSTREAM_HOST = "telemetry.nousresearch.com"

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})

# Module-level latch: the enabled/send mismatch is a static misconfiguration,
# so it is reported once per process instead of on every hook fire.
_warned_send_without_collection = False


@dataclass(frozen=True)
class SendConfig:
    """Resolved transmission settings."""

    #: Collection is on. Nothing is packaged or sent without it.
    enabled: bool
    #: Transmission is on AND permitted (that is, collection is also on).
    send: bool
    #: Where packages are POSTed.
    endpoint: str


def _endpoint_is_safe(endpoint: str) -> bool:
    """Reject plaintext destinations unless they are loopback (so tests can use local HTTP)."""
    try:
        parsed = urlparse(endpoint)
    except ValueError:
        return False
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return parsed.scheme == "http" and (parsed.hostname or "") in _LOCAL_HOSTS


def resolve_send_config(config: dict | None) -> SendConfig:
    """Resolve transmission settings from explicit profile configuration.

    ``send`` is False whenever transmission cannot legitimately happen, so callers never
    have to re-check the combination.
    """
    global _warned_send_without_collection

    raw = config if isinstance(config, dict) else {}
    telemetry = raw.get("telemetry")
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    shared = telemetry.get("shared_metrics")
    shared = shared if isinstance(shared, dict) else {}

    enabled = shared.get("enabled") is True
    send_requested = shared.get("send") is True

    if send_requested and not enabled:
        # Loud, not silent: the user believes telemetry is being sent, and it never will be.
        if not _warned_send_without_collection:
            _warned_send_without_collection = True
            logger.error(
                "telemetry.shared_metrics.send is true but "
                "telemetry.shared_metrics.enabled is false — nothing is "
                "collected, so nothing can be sent. Enable collection or "
                "turn sending off."
            )
        return SendConfig(enabled=False, send=False, endpoint=DEFAULT_ENDPOINT)

    endpoint = shared.get("endpoint")
    endpoint = endpoint.strip() if isinstance(endpoint, str) else DEFAULT_ENDPOINT

    if send_requested and not endpoint:
        logger.error("Shared metrics sending requires telemetry.shared_metrics.endpoint in config.yaml.")
        return SendConfig(enabled=enabled, send=False, endpoint=endpoint)

    try:
        endpoint_host = urlparse(endpoint).hostname
    except ValueError:
        endpoint_host = None
    if send_requested and endpoint_host == _LEGACY_UPSTREAM_HOST:
        logger.error("The legacy upstream shared-metrics endpoint is no longer supported.")
        return SendConfig(enabled=enabled, send=False, endpoint=endpoint)

    if send_requested and not _endpoint_is_safe(endpoint):
        logger.error(
            "Refusing to send shared metrics to %r: telemetry must use https "
            "(or a localhost http endpoint for testing).",
            endpoint,
        )
        return SendConfig(enabled=enabled, send=False, endpoint=endpoint)

    return SendConfig(enabled=enabled, send=send_requested, endpoint=endpoint)
