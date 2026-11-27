"""Only confirmed curriculum rejection may trigger bounded, replayable correction."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control import test_study_typed_payload as typed
from tests.plugins.mission_control.test_learning_study import _model
from tests.plugins.mission_control.test_study_jobs import command, proposal

job_profile = typed.job_profile
admission_job = typed.admission_job
curriculum_job = typed.curriculum_job
typed_job = typed.typed_job


@pytest.fixture
def correction_job(typed_job):
    fixture, package, _ = typed_job
    _, _, _, _, spec, path, ctx, calls, _ = fixture
    validator = Path(spec['curriculum']['validator'])
    validator.write_text(validator.read_text(encoding='utf-8-sig').replace(
        "'cost_usd':0", "'cost_usd':0,'feedback':'Answers must name the pinned commit.'"
    ).replace("Path('validation.json')", "ok=ok and 'correction' not in request['case']\nPath('validation.json')"), encoding='utf-8')
    spec['curriculum']['max_generations'] = 3
    path.write_text(json.dumps(spec), encoding='utf-8')
    group, fact, good = [deepcopy(package) for _ in range(3)]
    group['cases'][1]['group_id'] = group['cases'][0]['group_id']
    fact['questions'][0]['answer'] = 'Use an unpinned branch.'
    responses = [group, fact, good]
    def generate(**kwargs):
        index = sum(row['task'] == 'nara_curriculum' for row in calls)
        answer = responses[index] if kwargs['task'] == 'nara_curriculum' else proposal()
        return _model(answer, calls).complete_structured(**kwargs)
    ctx.llm = SimpleNamespace(complete_structured=generate)
    return fixture, responses


def test_rejected_curriculum_is_corrected_before_learning(correction_job, capsys):
    fixture, _ = correction_job
    home, parser, registry, plan, _, _, ctx, calls, _ = fixture
    job = typed.legacy.enqueue(fixture, capsys)
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    assert [row['task'] for row in calls] == ['nara_curriculum'] * 3 + ['nara_media_study']
    inputs = [json.loads(row['input'][0]['text']) for row in calls]
    assert 'correction' not in inputs[0]
    assert inputs[1]['correction']['stage'] == 'structure'
    assert 'group' in inputs[1]['correction']['feedback']
    assert inputs[2]['correction']['stage'] == 'domain'
    assert inputs[2]['correction']['feedback'] == 'Answers must name the pinned commit.'
    assert inputs[2]['correction']['previous_proposal']['questions'][0]['answer'] == 'Use an unpinned branch.'
    assert 'correction' not in inputs[3] and 'canary_ONLY' not in json.dumps(inputs[3])
    assert inputs[3]['study_material']['questions'][0]['answer'] == 'The pinned commit.'
    assert registry.gap(plan.gap_id)['state'] == 'resolved'
    assert list((home / 'skills').glob('nara-learned-*/SKILL.md'))
    state = MissionStore.open_default().get(job['mission_id']).diagnostics['study_state']
    assert len(state['curriculum_revisions']) == 2
    assert MissionStore.open_default().verify_projection(job['mission_id'])


@pytest.mark.parametrize('limit', [True, 0, 4])
def test_invalid_correction_bound_stops_before_research(correction_job, capsys, limit):
    fixture, _ = correction_job
    _, parser, _, plan, spec, path, ctx, calls, web_calls = fixture
    spec['curriculum']['max_generations'] = limit
    path.write_text(json.dumps(spec), encoding='utf-8')
    code, result = command(ctx, parser, capsys, 'study-enqueue', plan.gap_id, '--protocol-file', str(path))
    assert code == 1 and 'max_generations' in result['message'], result
    assert calls == [] and web_calls == []


def test_background_worker_corrects_then_admits_curriculum(correction_job):
    from tests.waiting import wait_until

    fixture, _ = correction_job
    home, _, _, _, spec, _, ctx, calls, _ = fixture
    ctx.get_config = lambda key, default=None: {'enabled': True, 'protocols': {'repositories': spec}, 'interval_seconds': 600}
    hook = ctx.hooks['on_gateway_housekeeping']
    assert hook()['study']['state'] == 'started'
    try:
        wait_until(lambda: any(job.status == 'completed' and job.constraints.get('study_job')
                               for job in MissionStore.open_default().list()), timeout=30, what='corrected background curriculum')
        assert list((home / 'skills').glob('nara-learned-*/SKILL.md'))
        assert [row['task'] for row in calls] == ['nara_curriculum'] * 3 + ['nara_media_study']
    finally:
        wait_until(lambda: hook()['study']['state'] == 'not_due', timeout=30, what='correction worker exit')


def test_oversized_previous_proposal_is_archived_but_not_replayed_to_model(correction_job, capsys):
    fixture, responses = correction_job
    _, parser, _, _, _, _, ctx, calls, _ = fixture
    responses[0]['explanation'] = 'x' * 16001
    correction = typed.legacy.enqueue(fixture, capsys)
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    retry = json.loads(calls[1]['input'][0]['text'])['correction']
    assert retry['previous_proposal_omitted'] is True and 'previous_proposal' not in retry
    assert '4000 characters' in retry['feedback']
    assert MissionStore.open_default().verify_projection(correction['mission_id'])
