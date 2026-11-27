"""Comparison recovery retains confirmed calls and stops uncertain execution."""

from dataclasses import replace
import time
from types import SimpleNamespace

import pytest

from plugins.mission_control.model_benchmarks import ModelBenchmarks
from plugins.mission_control.model_performance import ModelPerformance
from tests.plugins.mission_control.test_model_benchmarks import benchmark as benchmark_fixture


@pytest.fixture
def benchmark(tmp_path):
    return benchmark_fixture.__wrapped__(tmp_path)


class Interrupted(BaseException):
    pass


@pytest.mark.parametrize('phase', ['generated', 'graded', 'cell_completed', 'verified'])
def test_resume_uses_confirmed_checkpoint_without_repeating_calls(benchmark, monkeypatch, phase):
    spec, llm, calls = benchmark
    runner = ModelBenchmarks.open_default(llm)
    job = runner.enqueue(spec)
    save = runner.save
    def interrupt(identity, state, current_phase, **updates):
        save(identity, state, current_phase, **updates)
        if current_phase == phase:
            raise Interrupted()
    monkeypatch.setattr(runner, 'save', interrupt)
    with pytest.raises(Interrupted):
        runner.run(job['mission_id'])
    state = runner.missions.get(job['mission_id']).diagnostics['model_benchmark']
    deadline = state['deadline_at']
    result = ModelBenchmarks.open_default(llm).run(job['mission_id'])
    assert result['status'] == 'completed', result
    assert len(calls) == 4
    assert runner.missions.get(job['mission_id']).diagnostics['model_benchmark']['deadline_at'] == deadline
    events = [e for e in runner.ledger.events(job['mission_id']) if e['kind'] == 'model.benchmark.verified']
    assert len(events) == 1


def test_uncertain_generation_stops_without_retry_or_scores(benchmark):
    spec, _, calls = benchmark
    def generate(**kwargs):
        calls.append(kwargs)
        raise Interrupted()
    runner = ModelBenchmarks.open_default(SimpleNamespace(complete_structured=generate))
    job = runner.enqueue(spec)
    with pytest.raises(Interrupted):
        runner.run(job['mission_id'])
    result = runner.run(job['mission_id'])
    assert result['status'] == 'failed' and 'unconfirmed' in result['reason']
    assert len(calls) == 1 and ModelPerformance.open_default().summaries(spec['category']) == []


def test_deadline_expiration_does_not_start_another_call(benchmark):
    spec, llm, calls = benchmark
    runner = ModelBenchmarks.open_default(llm)
    job = runner.enqueue(spec)
    state = dict(runner.missions.get(job['mission_id']).diagnostics['model_benchmark'])
    runner.save(job['mission_id'], state, 'ready', deadline_at=time.time() - 10)
    result = runner.run(job['mission_id'])
    assert result['status'] == 'failed' and 'deadline' in result['reason'] and not calls


def test_all_repetitions_and_failures_count_and_other_suites_stay_separate(benchmark):
    spec, llm, _ = benchmark
    runner = ModelBenchmarks.open_default(llm)
    first = runner.run(runner.enqueue(spec)['mission_id'])
    def failed(**kwargs):
        if kwargs['model'] == 'large-bad':
            raise TimeoutError('confirmed timeout')
        return replace(llm.complete_structured(**kwargs), model='fallback-model')
    other = ModelBenchmarks.open_default(SimpleNamespace(complete_structured=failed))
    second = other.run(other.enqueue(spec)['mission_id'])
    assert first['benchmark_scope'] == second['benchmark_scope']
    scores = ModelPerformance.open_default().summaries(spec['category'])
    indexed = {row['model']: row for row in scores}
    assert indexed['large-bad']['sample_count'] == 4 and indexed['large-bad']['call_failure_count'] == 2
    assert indexed['small-good']['sample_count'] == 4 and indexed['small-good']['route_mismatch_count'] == 2
    assert indexed['small-good']['success_rate'] == .5
    assert indexed['small-good']['mean_cost_usd'] is None
    third = runner.run(runner.enqueue({**spec, 'instructions': 'A distinct comparison protocol.'})['mission_id'])
    assert third['benchmark_scope'] != first['benchmark_scope']
    assert all(row['sample_count'] == 2 for row in ModelPerformance.open_default().summaries(spec['category']))
    old = ModelPerformance.open_default().summaries(spec['category'], first['benchmark_scope'])
    assert all(row['sample_count'] == 4 for row in old)


@pytest.mark.parametrize('field,value', [('max_tokens', True), ('timeout', 121), ('max_seconds', 0)])
def test_invalid_bounds_rejected_before_calls(benchmark, field, value):
    spec, llm, calls = benchmark
    with pytest.raises(ValueError):
        ModelBenchmarks.open_default(llm).enqueue({**spec, field: value})
    assert not calls


def test_unknown_grade_and_corrupt_frozen_protocol_stop(benchmark, monkeypatch):
    from pathlib import Path
    from plugins.mission_control.model_benchmarks import ProcessEvaluator

    spec, llm, calls = benchmark
    runner = ModelBenchmarks.open_default(llm)
    job = runner.enqueue(spec)
    def interrupted_grade(*args, **kwargs):
        raise Interrupted()
    monkeypatch.setattr(ProcessEvaluator, '__call__', interrupted_grade)
    with pytest.raises(Interrupted):
        runner.run(job['mission_id'])
    assert runner.run(job['mission_id'])['status'] == 'failed'
    assert len(calls) == 1
    other = runner.enqueue(spec)
    reference = other['diagnostics']['model_benchmark']['protocol_artifact_id']
    Path(runner.artifacts.get(other['mission_id'], reference).location).write_bytes(b'corrupt')
    result = runner.run(other['mission_id'])
    assert result['status'] == 'failed' and 'verification' in result['reason']
    assert len(calls) == 1


def test_resume_after_verified_ledger_does_not_duplicate_observation(benchmark, monkeypatch):
    spec, llm, calls = benchmark
    runner = ModelBenchmarks.open_default(llm)
    job = runner.enqueue(spec)
    transition = runner.missions.transition
    def interrupt(identity, status, **kwargs):
        if status == 'completed':
            raise Interrupted()
        return transition(identity, status, **kwargs)
    monkeypatch.setattr(runner.missions, 'transition', interrupt)
    with pytest.raises(Interrupted):
        runner.run(job['mission_id'])
    result = ModelBenchmarks.open_default(llm).run(job['mission_id'])
    assert result['status'] == 'completed' and len(calls) == 4
    events = [e for e in runner.ledger.events(job['mission_id']) if e['kind'] == 'model.benchmark.verified']
    assert len(events) == 1
