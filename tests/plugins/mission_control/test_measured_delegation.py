"""Verified comparison results reach actual core child creation through a public backend."""

import json

import pytest

from plugins.mission_control.model_benchmarks import ModelBenchmarks
from tests.plugins.mission_control.test_model_benchmarks import benchmark as benchmark_fixture
from tests.tools.test_delegation_backends import _home, _parent, _definition, _task_props, recorded as recorded_fixture


@pytest.fixture
def benchmark(tmp_path):
    return benchmark_fixture.__wrapped__(tmp_path)


@pytest.fixture
def recorded(monkeypatch):
    return recorded_fixture.__wrapped__(monkeypatch)


def routes():
    return [{'provider': 'custom', 'model': name, 'base_url': 'http://127.0.0.1:9/v1',
             'api_key': 'fixture-route-secret', 'capabilities': {'supports_tools': True,
                'supports_vision': vision, 'supports_reasoning': reasoning, 'context_window': context}}
            for name, vision, reasoning, context in [('large-bad', True, True, 128000), ('small-good', False, False, 32000)]]


def test_measurement_changes_next_real_child_route_and_preserves_schema(benchmark, tmp_path, monkeypatch, recorded):
    from tools.delegate_tool import delegate_task

    config = {'backend': 'nara-measured', 'backends': {'nara-measured': {'routes': routes()}}}
    _, manager = _home(tmp_path, monkeypatch, config, plugins=())
    try:
        definition = _definition()
        task = {'goal': 'Count these items', 'task_category': 'structured.count'}
        first = json.loads(delegate_task(tasks=[task], parent_agent=_parent()))
        assert first['results'][0]['status'] == 'completed', first
        assert recorded[0]['model'] == 'large-bad'
        spec, llm, _ = benchmark
        spec['routes'] = [{'provider': 'custom', 'model': row['model']} for row in routes()]
        runner = ModelBenchmarks.open_default(llm)
        report = runner.run(runner.enqueue(spec)['mission_id'])
        assert report['status'] == 'completed', report
        second = json.loads(delegate_task(tasks=[task], parent_agent=_parent()))
        assert second['results'][0]['status'] == 'completed', second
        assert recorded[1]['model'] == 'small-good' and recorded[0]['model'] == 'large-bad'
        assert recorded[1]['override_base_url'] == 'http://127.0.0.1:9/v1'
        assert recorded[1]['override_api_key'] == 'fixture-route-secret'
        assert 'fixture-route-secret' not in json.dumps(second)
        assert 'task_category' in _task_props(definition)
        assert json.dumps(_definition()) == json.dumps(definition)
        # Capability requirements still win over a model's higher benchmark score.
        vision = json.loads(delegate_task(tasks=[{**task, 'requires_vision': True}], parent_agent=_parent()))
        assert vision['results'][0]['status'] == 'completed' and recorded[-1]['model'] == 'large-bad'
    finally:
        manager.unload()


def test_measured_choice_reaches_child_http_request(benchmark, tmp_path, monkeypatch):
    from nara_state import SessionDB
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task
    from tests.fakes.fake_llm_provider import FakeLLMServer
    from tests.e2e.core.history._helpers import OFFLINE_CONFIG, NO_BACKGROUND_REVIEW

    with FakeLLMServer(default_text='NARA_CHILD_OK') as server:
        pool = [{**route, 'base_url': server.base_url} for route in routes()]
        config = {'backend': 'nara-measured', 'backends': {'nara-measured': {'routes': pool}}}
        home, manager = _home(tmp_path, monkeypatch, config, plugins=())
        path = home / 'config.yaml'
        path.write_text(path.read_text(encoding='utf-8-sig') + OFFLINE_CONFIG + NO_BACKGROUND_REVIEW, encoding='utf-8')
        db = SessionDB(db_path=home / 'state.db')
        db.ensure_session('measured-parent', source='cli')
        parent = AIAgent(provider='custom', base_url=server.base_url, api_key='fixture-parent-key',
                         model='parent-model', session_db=db, session_id='measured-parent', quiet_mode=True, platform='cli')
        try:
            spec, llm, _ = benchmark
            spec['routes'] = [{'provider': 'custom', 'model': row['model']} for row in pool]
            runner = ModelBenchmarks.open_default(llm)
            assert runner.run(runner.enqueue(spec)['mission_id'])['status'] == 'completed'
            result = json.loads(delegate_task(tasks=[{'goal': 'Reply with NARA_CHILD_OK.',
                'task_category': 'structured.count'}], parent_agent=parent, max_iterations=2, background=False))
            assert result['results'][0]['status'] == 'completed', result
            assert 'NARA_CHILD_OK' in result['results'][0]['summary']
            requests = server.main_requests()
            assert requests and all(row['model'] == 'small-good' for row in requests)
            assert result['results'][0]['route']['backend'] == 'nara-measured'
        finally:
            parent.close()
            manager.unload()


def test_bad_task_does_not_spawn_or_prevent_compatible_sibling(tmp_path, monkeypatch, recorded):
    from tools.delegate_tool import delegate_task

    config = {'backend': 'nara-measured', 'backends': {'nara-measured': {'routes': routes()}}}
    _, manager = _home(tmp_path, monkeypatch, config, plugins=())
    try:
        result = json.loads(delegate_task(tasks=[
            {'goal': 'Impossible context', 'min_context': 1_000_000},
            {'goal': 'Compatible task', 'requires_vision': True},
            {'goal': 'Wrong typed requirement', 'requires_vision': 'yes'},
        ], parent_agent=_parent()))
        assert [row['status'] for row in result['results']] == ['error', 'completed', 'error']
        assert len(recorded) == 1 and recorded[0]['model'] == 'large-bad'
    finally:
        manager.unload()


def test_corrupt_measurement_stops_affected_child_without_silent_fallback(benchmark, tmp_path, monkeypatch, recorded):
    from pathlib import Path
    from tools.delegate_tool import delegate_task

    config = {'backend': 'nara-measured', 'backends': {'nara-measured': {'routes': routes()}}}
    _, manager = _home(tmp_path, monkeypatch, config, plugins=())
    try:
        spec, llm, _ = benchmark
        spec['routes'] = [{'provider': 'custom', 'model': row['model']} for row in routes()]
        runner = ModelBenchmarks.open_default(llm)
        report = runner.run(runner.enqueue(spec)['mission_id'])
        Path(report['rows'][0]['evaluation']['evidence'][0]['path']).write_bytes(b'changed')
        result = json.loads(delegate_task(tasks=[
            {'goal': 'Measured task', 'task_category': 'structured.count'},
            {'goal': 'Unmeasured task'},
        ], parent_agent=_parent()))
        assert [row['status'] for row in result['results']] == ['error', 'completed']
        assert 'evidence' in result['results'][0]['error']
        assert len(recorded) == 1 and recorded[0]['model'] == 'large-bad'
    finally:
        manager.unload()
