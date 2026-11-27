"""Real plugin discovery and agent tool dispatch deliver instructions to child HTTP."""

import json
from pathlib import Path

import nara_yaml as yaml
import pytest

from tests.plugins.mission_control.test_specialists import _legiao
from tests.e2e.core.history._helpers import OFFLINE_CONFIG, NO_BACKGROUND_REVIEW
from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall
from tests.waiting import wait_until


def _runtime_home(tmp_path, monkeypatch, base_url):
    from nara_cli import plugins as plugins_mod
    from nara_cli.plugins import PluginManager

    home = tmp_path / 'home'
    home.mkdir()
    catalog = _legiao(tmp_path)
    config = {'plugins': {'enabled': ['mission_control'], 'entries': {'mission_control': {
        'settings': {'legiao_path': str(catalog.root)}}}},
        'delegation': {'model': 'child-model', 'provider': 'custom', 'base_url': base_url,
                       'api_key': 'fixture-key'}}
    (home / 'config.yaml').write_text(yaml.safe_dump(config) + OFFLINE_CONFIG + NO_BACKGROUND_REVIEW,
                                    encoding='utf-8')
    bundled = tmp_path / 'bundled'
    bundled.mkdir()
    source = Path(__file__).resolve().parents[3] / 'plugins'
    for name in ('mission_control', 'delegation'):
        (bundled / name).symlink_to(source / name, target_is_directory=True)
    monkeypatch.setenv('NARA_HOME', str(home))
    monkeypatch.setenv('HOME', str(tmp_path / 'os-home'))
    monkeypatch.delenv('NARA_LEGIAO_HOME', raising=False)
    monkeypatch.setattr(plugins_mod, 'get_bundled_plugins_dir', lambda: bundled)
    manager = PluginManager()
    monkeypatch.setattr(plugins_mod, '_plugin_manager', manager)
    manager.discover_and_load()
    return home, manager


@pytest.mark.parametrize("broken_snapshot", [False, True])
def test_parent_tool_call_automatically_prepares_child_context(tmp_path, monkeypatch, broken_snapshot):
    from nara_state import SessionDB
    from run_agent import AIAgent

    args = {'tasks': [{'goal': 'analise planilha e dashboard', 'context': 'INPUT-ONLY'}]}
    issued = False

    def respond(request):
        nonlocal issued
        body = request.get('body', request)
        if body.get('model') == 'child-model':
            return Text('CHILD-FINISHED')
        if not issued:
            issued = True
            return ToolCall('delegate_task', args)
        return Text('PARENT-FINISHED')

    with FakeLLMServer(respond) as server:
        home, manager = _runtime_home(tmp_path, monkeypatch, server.base_url)
        monkeypatch.setenv('NARA_SECURITY_MODE', 'unrestricted')
        if broken_snapshot:
            def fail_snapshot(*_args, **_kwargs):
                raise ValueError('fixture snapshot hash mismatch')
            monkeypatch.setattr('plugins.mission_control.specialist_dispatch.freeze_call', fail_snapshot)
        db = SessionDB(db_path=home / 'state.db')
        db.ensure_session('specialist-parent', source='cli')
        parent = AIAgent(provider='custom', base_url=server.base_url, api_key='fixture-key',
                         model='parent-model', max_iterations=4, session_db=db,
                         session_id='specialist-parent', quiet_mode=True, platform='cli',
                         skip_background_review=True)
        try:
            parent.run_conversation('Delegate the spreadsheet analysis.')
            if broken_snapshot:
                requests = server.main_requests()
                assert requests and all(row['model'] == 'parent-model' for row in requests)
                assert 'fixture snapshot hash mismatch' in json.dumps(requests[-1]['messages'])
                return
            children = wait_until(lambda: [row for row in server.main_requests()
                if row['model'] == 'child-model'], timeout=20, what='actual child model HTTP request')
            wire = json.dumps(children[0]['messages'], ensure_ascii=False)
            assert 'SECRET-DATA-PROMPT' in wire and 'INPUT-ONLY' in wire
            assert 'SECRET-PRICE-PROMPT' not in wire
            assert args['tasks'][0]['context'] == 'INPUT-ONLY'
            parent_requests = [row for row in server.main_requests() if row['model'] == 'parent-model']
            calls = [call for row in parent_requests for msg in row['messages']
                     for call in msg.get('tool_calls', [])]
            assert calls and all('SECRET-DATA-PROMPT' not in call['function']['arguments'] for call in calls)
        finally:
            parent.close()
            manager.unload()
