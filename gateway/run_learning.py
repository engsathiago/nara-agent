"""Gateway housekeeping for Nara's verified mission learning."""

from __future__ import annotations

import logging


def housekeeping_mission_learning() -> None:
    from plugins.mission_control.consolidation import maybe_run_gateway_consolidation

    maybe_run_gateway_consolidation(log=logging.getLogger("gateway.run"))
