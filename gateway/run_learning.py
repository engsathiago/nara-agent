"""Dispatch profile-scoped gateway housekeeping to registered plugins."""

from __future__ import annotations

def housekeeping_plugin_maintenance() -> None:
    from nara_cli.plugins import has_hook, invoke_hook

    if has_hook("on_gateway_housekeeping"):
        invoke_hook("on_gateway_housekeeping")
