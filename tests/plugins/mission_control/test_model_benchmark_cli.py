"""Registered commands and resolver tools share durable category evidence."""

import argparse
import json

import pytest

from plugins.mission_control import register
from plugins.mission_control.specialists import AgentFactory, ModelCandidate, ModelCapabilityRegistry, SpecialistResolver
from tests.plugins.mission_control.test_model_benchmarks import benchmark as benchmark_fixture
from tests.plugins.mission_control.test_plugin import _Context


@pytest.fixture
def benchmark(tmp_path):
    return benchmark_fixture.__wrapped__(tmp_path)


def test_registered_benchmark_changes_next_plan_without_mutating_existing_plan(benchmark, tmp_path, monkeypatch, capsys):
    spec, llm, calls = benchmark
    ctx = _Context()
    ctx.llm = llm
    register(ctx)
    parser = argparse.ArgumentParser()
    ctx.command['setup_fn'](parser)
    registry = [ModelCandidate('fixture', 'large-bad', True, False, True, 128000),
                ModelCandidate('fixture', 'small-good', True, False, False, 32000)]
    monkeypatch.setattr(ModelCapabilityRegistry, '_configured', lambda self: registry)
    resolver = SpecialistResolver.open_default()
    factory = AgentFactory(resolver)
    old = factory.plan(mission_id='m', task_id='old', task='Count input items', category=spec['category'])
    path = tmp_path / 'comparison.json'
    path.write_text(json.dumps(spec), encoding='utf-8')
    def command(*args):
        code = ctx.command['handler_fn'](parser.parse_args(args))
        return code, json.loads(capsys.readouterr().out)
    code, job = command('model-benchmark-enqueue', '--protocol-file', str(path))
    assert code == 0
    code, result = command('model-benchmark-run', job['mission_id'])
    assert code == 0 and result['status'] == 'completed'
    assert all(call['task'] in ctx.auxiliary_tasks for call in calls)
    code, scores = command('model-performance', spec['category'])
    assert code == 0 and len(scores) == 2
    decision = json.loads(ctx.tools['nara_specialist_resolve']['handler']({
        'task': 'Count input items', 'category': spec['category']}))
    assert decision['model']['model'] == 'small-good'
    assert decision['model_basis'] == 'verified_category_benchmark'
    new = factory.plan(mission_id='m', task_id='new', task='Count input items', category=spec['category'])
    assert new.model == 'small-good' and old.model == 'large-bad'
    assert json.loads(new.model_evidence_json)['evidence_missions'] == [job['mission_id']]
    # A changed host configuration must not inherit an older environment's ranking.
    from nara_constants import get_nara_home
    (get_nara_home() / 'config.yaml').write_text('auxiliary:\n  nara_model_benchmark:\n    reasoning_effort: low\n', encoding='utf-8')
    assert resolver.resolve('Count input items', category=spec['category'])['model']['model'] == 'large-bad'
