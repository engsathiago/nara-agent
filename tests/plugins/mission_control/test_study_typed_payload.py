"""Typed exercises survive durable execution without weakening domain validation."""

import json
from pathlib import Path

import pytest

from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control import test_study_curriculum as legacy
from tests.plugins.mission_control.test_study_jobs import command

job_profile = legacy.job_profile
admission_job = legacy.admission_job
curriculum_job = legacy.curriculum_job


@pytest.fixture
def typed_job(curriculum_job):
    fixture, package = curriculum_job
    brief_path = Path(fixture[4]['curriculum']['brief_file'])
    brief = json.loads(brief_path.read_text(encoding='utf-8-sig'))
    brief['payload_schema'] = {'type': 'object', 'additionalProperties': False,
        'properties': {key: {'type': 'string', 'minLength': 1, 'maxLength': 120}
                       for key in ('requires', 'private')}, 'required': ['requires', 'private']}
    brief_path.write_text(json.dumps(brief), encoding='utf-8')
    for row in package['cases']:
        row['payload'] = json.loads(row.pop('payload_json'))
    return fixture, package, brief_path


def test_typed_exercises_resume_with_frozen_contract(typed_job, capsys, monkeypatch):
    from plugins.mission_control.study_curriculum import StudyCurriculum

    fixture, _, brief_path = typed_job
    home, parser, registry, plan, _, _, ctx, calls, _ = fixture
    job = legacy.enqueue(fixture, capsys)
    save = StudyCurriculum._save
    class Interrupted(BaseException):
        pass
    def checkpoint(self, stage, **updates):
        save(self, stage, **updates)
        if stage == 'curriculum_generated':
            raise Interrupted()
    with monkeypatch.context() as patch:
        patch.setattr(StudyCurriculum, '_save', checkpoint)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, 'study-work')
    capsys.readouterr()
    brief_path.write_text('{}', encoding='utf-8')
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    assert [row['task'] for row in calls] == ['nara_curriculum', 'nara_media_study']
    schema = calls[0]['json_schema']['properties']['cases']['items']
    assert schema['properties']['payload']['type'] == 'object'
    assert 'payload_json' not in schema['required']
    learner = json.loads(calls[1]['input'][0]['text'])
    assert 'transfer_ONLY' not in json.dumps(learner) and 'canary_ONLY' not in json.dumps(learner)
    assert registry.gap(plan.gap_id)['state'] == 'resolved'
    assert list((home / 'skills').glob('nara-learned-*/SKILL.md'))
    assert MissionStore.open_default().verify_projection(job['mission_id'])


@pytest.mark.parametrize('fault', ['wrong_type', 'extra_field', 'missing_field', 'too_long', 'false_fact'])
def test_typed_exercise_failure_never_reaches_learner(typed_job, capsys, fault):
    fixture, package, _ = typed_job
    home, parser, registry, plan, _, _, ctx, calls, _ = fixture
    payload = package['cases'][0]['payload']
    mutations = {
        'wrong_type': lambda value: {**value, 'requires': True},
        'extra_field': lambda value: {**value, 'unexpected': 'extra'},
        'missing_field': lambda value: {key: item for key, item in value.items() if key != 'requires'},
        'too_long': lambda value: {**value, 'requires': 'x' * 121},
        'false_fact': lambda value: {**value, 'requires': 'trust an unpinned branch'},
    }
    package['cases'][0]['payload'] = mutations[fault](payload)
    legacy.enqueue(fixture, capsys)
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed', result
    assert ('curriculum validator' if fault == 'false_fact' else 'payload') in result['reason']
    assert [row['task'] for row in calls] == ['nara_curriculum']
    assert registry.gap(plan.gap_id)['state'] == 'unresolved'
    assert not list((home / 'skills').glob('nara-learned-*/SKILL.md'))


def test_unsupported_payload_schema_is_rejected_before_research(typed_job, capsys):
    fixture, _, brief_path = typed_job
    _, parser, _, plan, _, path, ctx, calls, web_calls = fixture
    brief = json.loads(brief_path.read_text(encoding='utf-8-sig'))
    brief['payload_schema']['properties']['requires'] = {'$ref': 'https://example.org/schema'}
    brief_path.write_text(json.dumps(brief), encoding='utf-8')
    code, result = command(ctx, parser, capsys, 'study-enqueue', plan.gap_id, '--protocol-file', str(path))
    assert code == 1 and 'payload schema' in result['message'], result
    assert calls == [] and web_calls == []


def test_gateway_studies_typed_exercises_without_supplied_cases(typed_job):
    from tests.waiting import wait_until

    fixture, _, _ = typed_job
    home, _, _, _, spec, _, ctx, calls, _ = fixture
    ctx.get_config = lambda key, default=None: {'enabled': True, 'protocols': {'repositories': spec}, 'interval_seconds': 600}
    hook = ctx.hooks['on_gateway_housekeeping']
    assert hook()['study']['state'] == 'started'
    try:
        wait_until(lambda: any(job.status == 'completed' and job.constraints.get('study_job')
                               for job in MissionStore.open_default().list()), timeout=30, what='typed background study')
        assert list((home / 'skills').glob('nara-learned-*/SKILL.md'))
        assert [row['task'] for row in calls] == ['nara_curriculum', 'nara_media_study']
    finally:
        wait_until(lambda: hook()['study']['state'] == 'not_due', timeout=30, what='typed worker exit')


def test_zip_export_drives_nested_typed_payload_and_retains_domain_oracle(tmp_path, capsys):
    from plugins.mission_control.study_curriculum_schema import curriculum_schema, resolve_curriculum
    from plugins.mission_control.study_payload_schema import payload_schema
    from plugins.mission_control.learning_runner import ProcessEvaluator
    from tests.plugins.mission_control.test_study_oracles import invoke, zip_curriculum

    _, prepared = invoke(capsys, 'study-oracle-prepare', 'zip-manifest', str(tmp_path / 'oracle'), '--model', 'fixture')
    protocol = json.loads(Path(prepared['protocol_file']).read_text(encoding='utf-8-sig'))
    brief = json.loads(Path(protocol['curriculum']['brief_file']).read_text(encoding='utf-8-sig'))
    contract = payload_schema(brief)
    case = zip_curriculum()
    spans = case['source']['spans']
    package = case['curriculum']
    parsed = {'explanation': package['teaching_material']['explanation'], 'decline_reason': '',
              'questions': [{'question': row['question'], 'answer': row['answer'],
                             'source_span_ids': [span['id'] for span in row['citations']]}
                            for row in package['teaching_material']['questions']], 'cases': package['cases']}
    schema = curriculum_schema(spans, contract)
    assert schema['properties']['cases']['items']['properties']['payload'] == contract
    resolved = resolve_curriculum(parsed, spans, contract)
    evaluator = ProcessEvaluator(protocol['curriculum']['validator'], tmp_path / 'evidence')
    assert evaluator(None, {**case, 'curriculum': resolved})['score'] == 1.0
    parsed['cases'][0]['payload']['members'][0]['text'] = 12
    with pytest.raises(ValueError, match='payload'):
        resolve_curriculum(parsed, spans, contract)
    parsed['cases'][0]['payload']['members'] = [{}] * 9
    with pytest.raises(ValueError, match='array bounds'):
        resolve_curriculum(parsed, spans, contract)
    parsed['cases'][0]['payload'] = '{members: []}'
    with pytest.raises(ValueError, match='payload'):
        resolve_curriculum(parsed, spans, contract)
