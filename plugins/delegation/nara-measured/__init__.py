"""Register measured model routing through the public delegation-provider interface."""

from plugins.mission_control.measured_delegation import MeasuredDelegationProvider


def register(ctx):
    ctx.register_delegation_provider(MeasuredDelegationProvider())
