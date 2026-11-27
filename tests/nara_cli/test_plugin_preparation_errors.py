"""Operational pre-tool failures are distinct from authorization decisions."""

import pytest

from nara_cli.plugins import _dispatch_pre_tool_call_hooks


@pytest.mark.parametrize('earlier', [[], [{'action': 'block', 'message': 'policy veto'}],
                                    [{'action': 'approve', 'message': 'confirm'}]])
def test_preparation_failure_survives_unrestricted_authorization(monkeypatch, earlier):
    monkeypatch.setenv('NARA_SECURITY_MODE', 'unrestricted')
    monkeypatch.setattr('nara_cli.plugins.invoke_hook', lambda *_a, **_kw: earlier + [
        {'action': 'error', 'message': 'cannot load the selected instruction snapshot'}])
    error, modified = _dispatch_pre_tool_call_hooks('delegate_task', {'goal': 'inspect records'})
    assert error and 'cannot load the selected instruction snapshot' in error
    assert modified is None


@pytest.mark.parametrize('message', [None, '', 42])
def test_invalid_preparation_error_does_not_invent_a_failure(monkeypatch, message):
    monkeypatch.setattr('nara_cli.plugins.invoke_hook', lambda *_a, **_kw: [
        {'action': 'error', 'message': message}])
    assert _dispatch_pre_tool_call_hooks('delegate_task', {'goal': 'inspect records'}) == (None, None)
