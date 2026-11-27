"""Source-backed teaching resolves exact text without trusting generated quotations."""

import json

import pytest

from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control import test_study_typed_payload as typed
from tests.plugins.mission_control.test_study_jobs import command

job_profile = typed.job_profile
admission_job = typed.admission_job
curriculum_job = typed.curriculum_job
typed_job = typed.typed_job


@pytest.fixture
def source_job(typed_job):
    fixture, package, brief_path = typed_job
    brief = json.loads(brief_path.read_text(encoding='utf-8-sig'))
    brief['teaching_schema'] = {'mode': 'source-span-v1',
                              'questions': [package['questions'][0]['question']]}
    brief_path.write_text(json.dumps(brief), encoding='utf-8')
    package.pop('explanation')
    package['explanation_source_span_id'] = 's0000'
    return fixture, package, brief_path


def test_source_span_teaching_survives_restart_and_reaches_learner(source_job, capsys, monkeypatch):
    from plugins.mission_control.study_curriculum import StudyCurriculum

    fixture, _, brief_path = source_job
    home, parser, registry, plan, _, _, ctx, calls, _ = fixture
    job = typed.legacy.enqueue(fixture, capsys)
    save = StudyCurriculum._save
    class Interrupted(BaseException):
        pass
    def checkpoint(self, phase, **updates):
        save(self, phase, **updates)
        if phase == 'curriculum_generated':
            raise Interrupted()
    with monkeypatch.context() as patch:
        patch.setattr(StudyCurriculum, '_save', checkpoint)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, 'study-work')
    capsys.readouterr()
    brief_path.unlink()
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    assert [call['task'] for call in calls] == ['nara_curriculum', 'nara_media_study']
    request = json.loads(calls[0]['input'][0]['text'])
    spans = request['source']['spans']
    expected = next(span['text'] for span in spans if span['id'] == 's0000')
    schema = calls[0]['json_schema']
    assert 'explanation_source_span_id' in schema['required'] and 'explanation' not in schema['properties']
    learner = json.loads(calls[1]['input'][0]['text'])
    assert learner['study_material']['explanation'] == expected
    assert 'transfer_ONLY' not in json.dumps(learner) and 'canary_ONLY' not in json.dumps(learner)
    assert registry.gap(plan.gap_id)['state'] == 'resolved'
    assert list((home / 'skills').glob('nara-learned-*/SKILL.md'))
    assert MissionStore.open_default().verify_projection(job['mission_id'])


@pytest.mark.parametrize('fault', ['unknown_span', 'freeform_override', 'unlisted_question', 'false_answer', 'repeated_group'])
def test_invalid_source_teaching_never_reaches_learner(source_job, capsys, fault):
    fixture, package, _ = source_job
    home, parser, registry, plan, _, _, ctx, calls, _ = fixture
    mutations = {
        'unknown_span': (package, 'explanation_source_span_id', 'invented'),
        'freeform_override': (package, 'explanation', 'Unverified substitute'),
        'unlisted_question': (package['questions'][0], 'question', 'Invented question'),
        'false_answer': (package['questions'][0], 'answer', 'Use an unpinned branch'),
        'repeated_group': (package['cases'][1], 'group_id', package['cases'][0]['group_id']),
    }
    target, key, value = mutations[fault]
    target[key] = value
    typed.legacy.enqueue(fixture, capsys)
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed', result
    assert [call['task'] for call in calls] == ['nara_curriculum']
    assert registry.gap(plan.gap_id)['state'] == 'unresolved'
    assert not list((home / 'skills').glob('nara-learned-*/SKILL.md'))


def test_unknown_teaching_contract_stops_before_research(source_job, capsys):
    fixture, _, brief_path = source_job
    _, parser, _, plan, _, path, ctx, calls, web_calls = fixture
    brief = json.loads(brief_path.read_text(encoding='utf-8-sig'))
    brief['teaching_schema']['mode'] = 'invented'
    brief_path.write_text(json.dumps(brief), encoding='utf-8')
    code, result = command(ctx, parser, capsys, 'study-enqueue', plan.gap_id, '--protocol-file', str(path))
    assert code == 1 and 'teaching schema' in result['message'], result
    assert calls == [] and web_calls == []


def test_source_reference_rejection_is_corrected_without_weakening_oracle(source_job, capsys):
    from copy import deepcopy
    from types import SimpleNamespace
    from tests.plugins.mission_control.test_learning_study import _model
    from tests.plugins.mission_control.test_study_jobs import proposal

    fixture, package, _ = source_job
    _, parser, _, _, spec, path, ctx, calls, _ = fixture
    spec['curriculum']['max_generations'] = 2
    path.write_text(json.dumps(spec), encoding='utf-8')
    invalid = deepcopy(package)
    invalid['explanation_source_span_id'] = 'invented'
    responses = [invalid, package]
    def generate(**kwargs):
        index = sum(call['task'] == 'nara_curriculum' for call in calls)
        answer = responses[index] if kwargs['task'] == 'nara_curriculum' else proposal()
        return _model(answer, calls).complete_structured(**kwargs)
    ctx.llm = SimpleNamespace(complete_structured=generate)
    typed.legacy.enqueue(fixture, capsys)
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    assert [call['task'] for call in calls] == ['nara_curriculum', 'nara_curriculum', 'nara_media_study']
    correction = json.loads(calls[1]['input'][0]['text'])['correction']
    assert correction['stage'] == 'structure'
    assert correction['previous_proposal']['explanation_source_span_id'] == 'invented'
    assert 'source span' in correction['feedback']
