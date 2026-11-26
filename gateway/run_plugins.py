"""Gateway plugin update housekeeping, kept outside the large runner facade."""

from __future__ import annotations

import logging


def housekeeping_plugin_update_check() -> None:
    """Due-gated read-only check; opt-in apply uses the manual update pipeline."""
    from nara_cli.plugins_cadence import maybe_run_gateway_check

    maybe_run_gateway_check(log=logging.getLogger("gateway.run"))
