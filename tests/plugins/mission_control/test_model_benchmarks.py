"""Measured model routing consumes verified executions, not caller-supplied scores."""

from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from plugins.mission_control.specialists import ModelCandidate, ModelCapabilityRegistry
from tests.plugins.mission_control.test_learning_study import _model


@pytest.fixture
def benchmark(tmp_path):
    evaluator = tmp_path / 'grade.py'
    evaluator.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "case=json.load(sys.stdin)['case']\n"
        "score=float(case['response']=={'count':case['oracle']['expected']})\n"
        "Path('grade.json').write_text(json.dumps({'score':score,'case_id':case['case_id']}))\n"
        "print(json.dumps({'score':score,'artifact_paths':['grade.json'],'cost_usd':0}))\n", encoding='utf-8')
    spec = {'category': 'structured.count', 'instructions': 'Count the items.',
            'json_schema': {'type': 'object', 'properties': {'count': {'type': 'integer'}},
                            'required': ['count'], 'additionalProperties': False},
            'evaluator': str(evaluator), 'max_tokens': 128, 'timeout': 10, 'max_seconds': 120,
            'routes': [{'provider': 'fixture', 'model': model} for model in ('large-bad', 'small-good')],
            'cases': [{'case_id': str(n), 'input': {'items': list(range(n))},
                       'oracle': {'expected': n, 'private_marker': 'PRIVATE_ORACLE'}} for n in (2, 3)]}
    calls = []
    def generate(**kwargs):
        items = json.loads(kwargs['input'][0]['text'])['items']
        answer = {'count': len(items) if kwargs['model'] == 'small-good' else 0}
        result = _model(answer, calls).complete_structured(**kwargs)
        return replace(result, provider=kwargs['provider'], model=kwargs['model'])
    return spec, SimpleNamespace(complete_structured=generate), calls


def test_verified_benchmark_changes_next_model_choice_and_survives_reopen(benchmark):
    from plugins.mission_control.model_benchmarks import ModelBenchmarks
    from plugins.mission_control.model_performance import ModelPerformance

    spec, llm, calls = benchmark
    models = [ModelCandidate('fixture', 'large-bad', True, False, True, 128000),
              ModelCandidate('fixture', 'small-good', True, False, False, 32000)]
    registry = ModelCapabilityRegistry(models)
    assert registry.select(requires_tools=True, requires_vision=False).model == 'large-bad'
    runner = ModelBenchmarks.open_default(llm)
    job = runner.enqueue(spec)
    # Evaluation is frozen before any model sees a case.
    from pathlib import Path
    Path(spec['evaluator']).unlink()
    result = runner.run(job['mission_id'])
    assert result['status'] == 'completed', result
    assert len(calls) == 4 and 'PRIVATE_ORACLE' not in json.dumps(calls)
    scores = ModelPerformance.open_default().summaries('structured.count', result['benchmark_scope'])
    assert {row['model']: row['success_rate'] for row in scores} == {'large-bad': 0.0, 'small-good': 1.0}
    assert all(row['sample_count'] == 2 and row['mean_cost_usd'] is None for row in scores)
    selected = ModelCapabilityRegistry(models).select(requires_tools=True, requires_vision=False,
        category='structured.count', benchmark_scope=result['benchmark_scope'])
    assert selected.model == 'small-good' and selected.performance['evidence_missions'] == [job['mission_id']]
    assert ModelCapabilityRegistry(models).select(requires_tools=True, requires_vision=False,
        category='unrelated').model == 'large-bad'
    assert runner.run(job['mission_id']) == result and len(calls) == 4


def test_corrupt_grading_evidence_cannot_influence_routing(benchmark):
    from pathlib import Path
    from plugins.mission_control.model_benchmarks import ModelBenchmarks
    from plugins.mission_control.model_performance import ModelPerformance

    spec, llm, _ = benchmark
    runner = ModelBenchmarks.open_default(llm)
    job = runner.enqueue(spec)
    result = runner.run(job['mission_id'])
    Path(result['rows'][0]['evaluation']['evidence'][0]['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='evidence'):
        ModelPerformance.open_default().summaries('structured.count', result['benchmark_scope'])
