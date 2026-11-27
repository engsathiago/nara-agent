"""Calibrated frozen curriculum comparators accept valid work and reject false independence."""

import copy
import json
from pathlib import Path

import pytest

from evals.model_comparison.curriculum_benchmark import prepare
from plugins.mission_control.learning_runner import ProcessEvaluator
from plugins.mission_control.study_curriculum import INSTRUCTIONS
from plugins.mission_control.study_curriculum_schema import curriculum_schema
from plugins.mission_control.study_oracles import _brief


def examples():
    quote = 'ZipFile.infolist returns member metadata. ZipInfo.is_dir identifies directories. ZipInfo.file_size is uncompressed bytes.'
    source = {'spans': [{'id': 's0001', 'text': quote, 'start': 0, 'end': len(quote)}]}
    brief = _brief()
    request = {'kind': 'curriculum_request', 'input': {'objective': 'Inspect ZIP archives', 'source': source, 'brief': brief},
               'instructions': INSTRUCTIONS.replace('payload_json', 'payload'),
               'schema': curriculum_schema(source['spans'], brief['payload_schema']), 'max_tokens': 8192}
    payloads = [[{'name': 'a.txt', 'text': 'abc'}],
                [{'name': 'dir/', 'text': ''}, {'name': 'dir/b.txt', 'text': 'ação'}], []]
    proposal = {'explanation': quote, 'questions': [{'question': brief['questions'][0], 'answer': 'infolist',
                   'source_span_ids': ['s0001']}], 'decline_reason': '',
                'cases': [{'case_id': split, 'split': split, 'group_id': group, 'payload': {'members': rows}}
                          for split, group, rows in zip(('development', 'transfer', 'canary'), ('flat', 'nested', 'empty'), payloads)]}
    return request, proposal


def grader(tmp_path):
    request, proposal = examples()
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request), encoding='utf-8')
    spec = prepare(path, ['fixture'], tmp_path / 'grader.py')
    path.unlink()
    return ProcessEvaluator(spec['evaluator'], tmp_path / 'evidence'), spec['cases'][0], proposal


def test_frozen_validator_bundle_operates_without_live_repository_imports(tmp_path, monkeypatch):
    evaluator, case, proposal = grader(tmp_path)
    poison = tmp_path / 'poison' / 'plugins'
    poison.mkdir(parents=True)
    (poison / '__init__.py').write_text("raise RuntimeError('unfrozen dependency used')\n", encoding='utf-8')
    monkeypatch.setenv('PYTHONPATH', str(poison.parent))
    result = evaluator(None, {**case, 'response': proposal})
    assert result['score'] == 1
    report = json.loads(Path(result['evidence'][0]['path']).read_bytes())
    assert report['calibration']['passed']
    assert 'plugins/mission_control/study_oracle_zip.py' in report['validator_sources']
    assert report['validation']['accepted_cases'] == 3


@pytest.mark.parametrize('error', ['duplicate', 'renamed_topology', 'wrong_fact', 'invented_citation'])
def test_frozen_comparator_rejects_incorrect_curricula(tmp_path, error):
    evaluator, case, original = grader(tmp_path)
    proposal = copy.deepcopy(original)
    if error == 'duplicate':
        proposal['cases'][1]['payload'] = proposal['cases'][0]['payload']
    elif error == 'renamed_topology':
        proposal['cases'][1]['payload'] = {'members': [{'name': 'different.txt', 'text': 'different content'}]}
    elif error == 'wrong_fact':
        proposal['questions'][0]['answer'] = 'extractall'
    else:
        proposal['questions'][0]['source_span_ids'] = ['invented']
    result = evaluator(None, {**case, 'response': proposal})
    assert result['score'] == 0 and result['feedback']
