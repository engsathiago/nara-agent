"""The registered runtime hook binds complete specialist instructions to child tasks."""

import copy
import json

import pytest

from plugins import mission_control
from tests.plugins.mission_control.test_plugin import _Context
from tests.plugins.mission_control.test_specialists import _legiao


@pytest.fixture
def dispatch_profile(tmp_path, monkeypatch):
    home = tmp_path / 'profile'
    home.mkdir()
    monkeypatch.setenv('NARA_HOME', str(home))
    monkeypatch.delenv('NARA_LEGIAO_HOME', raising=False)
    catalog = _legiao(tmp_path)
    config = {'plugins': {'entries': {'mission_control': {'settings': {'legiao_path': str(catalog.root)}}}}}
    (home / 'config.yaml').write_text(json.dumps(config), encoding='utf-8')
    ctx = _Context()
    mission_control.register(ctx)
    return home, catalog, ctx.hooks['pre_tool_call']


def invoke(hook, args, call='call-1'):
    return hook(tool_name='delegate_task', args=args, session_id='parent', tool_call_id=call)


def test_full_selected_instructions_are_frozen_per_call_without_mutating_parent(dispatch_profile):
    _, catalog, hook = dispatch_profile
    args = {'tasks': [{'goal': 'analise a planilha e dashboard', 'context': 'Keep original context'},
                      {'goal': 'calcular preço e margem'}, {'goal': 'Reply HELLO'}]}
    original = copy.deepcopy(args)
    first = invoke(hook, args)
    assert first and first['action'] == 'modify', first
    tasks = first['args']['tasks']
    assert 'SECRET-DATA-PROMPT' in tasks[0]['context'] and 'SECRET-PRICE-PROMPT' not in tasks[0]['context']
    assert 'Keep original context' in tasks[0]['context']
    assert 'SECRET-PRICE-PROMPT' in tasks[1]['context'] and 'SECRET-DATA-PROMPT' not in tasks[1]['context']
    assert tasks[2] == original['tasks'][2]
    assert args == original
    commands = json.loads(catalog.commands_path.read_text(encoding='utf-8-sig'))
    commands['commands'][0]['instructions'] = 'UPDATED-DATA-PROMPT'
    catalog.commands_path.write_text(json.dumps(commands), encoding='utf-8')
    assert invoke(hook, args) == first
    second = invoke(hook, args, 'call-2')
    assert 'UPDATED-DATA-PROMPT' in second['args']['tasks'][0]['context']
    assert 'SECRET-DATA-PROMPT' in first['args']['tasks'][0]['context']
    conflict = invoke(hook, {'tasks': [{'goal': 'different task'}]})
    assert conflict['action'] == 'error' and 'changed' in conflict['message']


def test_single_goal_and_controls_keep_native_semantics(dispatch_profile):
    _, _, hook = dispatch_profile
    args = {'goal': 'analise planilha de vendas', 'context': 'Inputs belong here', 'max_iterations': 7}
    prepared = invoke(hook, args)
    assert prepared and prepared['action'] == 'modify', prepared
    assert 'SECRET-DATA-PROMPT' in prepared['args']['context']
    assert prepared['args']['max_iterations'] == 7
    assert hook(tool_name='delegate_task', args={'action': 'stop', 'subagent_id': 'child'}) is None
    assert hook(tool_name='read_file', args={'path': 'any'}) is None


def test_changed_selected_prompt_stops_before_child_dispatch(dispatch_profile, monkeypatch):
    from plugins.mission_control.specialists import SpecialistResolver

    _, _, hook = dispatch_profile
    original = SpecialistResolver.load_selected
    def changed(self, source, specialist_id):
        loaded = original(self, source, specialist_id)
        return {**loaded, 'instructions': 'changed after metadata selection'}
    monkeypatch.setattr(SpecialistResolver, 'load_selected', changed)
    result = invoke(hook, {'goal': 'analise a planilha'})
    assert result and result['action'] == 'error' and 'hash' in result['message'], result


def test_corrupt_binding_is_not_reused_and_disabled_mode_preserves_call(dispatch_profile):
    import sqlite3

    home, _, hook = dispatch_profile
    args = {'goal': 'analise planilha'}
    assert invoke(hook, args)['action'] == 'modify'
    path = home / 'plugin-data' / 'mission-control' / 'specialist-bindings.db'
    with sqlite3.connect(path) as db:
        db.execute("UPDATE bindings SET payload='{}'")
    result = invoke(hook, args)
    assert result['action'] == 'error' and 'hash' in result['message']
    config_path = home / 'config.yaml'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    config['plugins']['entries']['mission_control']['settings']['specialist_delegation'] = False
    config_path.write_text(json.dumps(config), encoding='utf-8')
    assert invoke(hook, args) is None


def test_same_call_identity_is_isolated_by_profile(dispatch_profile, tmp_path, monkeypatch):
    _, _, hook = dispatch_profile
    args = {'goal': 'analise planilha'}
    assert 'SECRET-DATA-PROMPT' in invoke(hook, args)['args']['context']
    other = tmp_path / 'other-profile'
    other.mkdir()
    (other / 'config.yaml').write_text('{}', encoding='utf-8')
    monkeypatch.setenv('NARA_HOME', str(other))
    assert invoke(hook, args) is None


def test_native_skill_preserves_reference_location(dispatch_profile):
    home, _, hook = dispatch_profile
    skill = home / 'skills' / 'spectroscopy'
    skill.mkdir(parents=True)
    path = skill / 'SKILL.md'
    text = '---\nname: spectroscopy\ndescription: spectroscopy wavelength\n---\nRead references/calibration.md.\n'
    path.write_text(text, encoding='utf-8')
    result = invoke(hook, {'goal': 'spectroscopy wavelength'}, 'skill-call')
    assert result['action'] == 'modify'
    assert text in result['args']['context'] and str(path) in result['args']['context']
