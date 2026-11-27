"""Correction resumes confirmed work and stops at unknown effects or invalid proof."""

import json
from pathlib import Path

import pytest

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.study_curriculum import StudyCurriculum
from tests.plugins.mission_control import test_curriculum_correction as correction
from tests.plugins.mission_control.test_study_jobs import command

job_profile = correction.job_profile
admission_job = correction.admission_job
curriculum_job = correction.curriculum_job
typed_job = correction.typed_job
correction_job = correction.correction_job


class Interrupted(BaseException):
    pass


def interrupt_at(monkeypatch, stage, revision):
    save = StudyCurriculum._save
    def checkpoint(self, phase, **updates):
        save(self, phase, **updates)
        if phase == stage and len(self.state.get('curriculum_revisions', [])) == revision:
            raise Interrupted()
    monkeypatch.setattr(StudyCurriculum, '_save', checkpoint)


@pytest.mark.parametrize('stage,revision,confirmed,calls_before', [
    ('curriculum_rejected', 0, True, 1),
    ('curriculum_revision_ready', 1, True, 1),
    ('curriculum_generating', 1, False, 1),
    ('curriculum_generated', 1, True, 2),
    ('curriculum_validating', 1, False, 2),
    ('curriculum_validated', 1, True, 2),
])
def test_correction_restart_never_repeats_unknown_calls(correction_job, capsys, monkeypatch,
                                                       stage, revision, confirmed, calls_before):
    fixture, _ = correction_job
    _, parser, _, _, _, _, ctx, calls, web_calls = fixture
    job = correction.typed.legacy.enqueue(fixture, capsys)
    with monkeypatch.context() as patch:
        interrupt_at(patch, stage, revision)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, 'study-work')
    capsys.readouterr()
    assert len(calls) == calls_before
    deadline = MissionStore.open_default().get(job['mission_id']).diagnostics['study_state']['deadline_at']
    _, resumed = command(ctx, parser, capsys, 'study-work')
    assert resumed['status'] == ('completed' if confirmed else 'failed'), resumed
    assert len(calls) == (4 if confirmed else calls_before)
    if not confirmed:
        assert 'unconfirmed' in resumed['reason']
    state = MissionStore.open_default().get(job['mission_id']).diagnostics['study_state']
    assert state['deadline_at'] == deadline
    assert len(web_calls) == 2
    assert MissionStore.open_default().verify_projection(job['mission_id'])


def test_generation_limit_is_frozen_and_exhaustion_does_not_teach(correction_job, capsys):
    fixture, _ = correction_job
    home, parser, registry, plan, spec, path, ctx, calls, _ = fixture
    spec['curriculum']['max_generations'] = 2
    path.write_text(json.dumps(spec), encoding='utf-8')
    correction.typed.legacy.enqueue(fixture, capsys)
    spec['curriculum']['max_generations'] = 3
    path.write_text(json.dumps(spec), encoding='utf-8')
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed' and 'exhausted 2 generations' in result['reason'], result
    assert [row['task'] for row in calls] == ['nara_curriculum'] * 2
    assert registry.gap(plan.gap_id)['state'] == 'unresolved'
    assert not list((home / 'skills').glob('nara-learned-*/SKILL.md'))


def test_old_rejected_validator_evidence_must_survive_correction(correction_job, capsys, monkeypatch):
    fixture, _ = correction_job
    _, parser, _, _, _, _, ctx, calls, _ = fixture
    job = correction.typed.legacy.enqueue(fixture, capsys)
    with monkeypatch.context() as patch:
        interrupt_at(patch, 'curriculum_revision_ready', 2)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, 'study-work')
    capsys.readouterr()
    store = MissionStore.open_default()
    state = store.get(job['mission_id']).diagnostics['study_state']
    artifacts = ArtifactStore(store, store.path.parent / 'artifacts')
    def read(identity):
        return json.loads(artifacts.read_bytes(job['mission_id'], identity))
    rejection = read(state['curriculum_revisions'][-1])
    receipt = read(rejection['validation_artifact_id'])
    Path(receipt['result']['evidence'][0]['path']).write_bytes(b'corrupt')
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed' and 'evidence' in result['reason'], result
    assert len(calls) == 2


def test_correction_cannot_renew_the_original_deadline(correction_job, capsys, monkeypatch):
    fixture, _ = correction_job
    _, parser, _, _, _, _, ctx, calls, _ = fixture
    job = correction.typed.legacy.enqueue(fixture, capsys)
    with monkeypatch.context() as patch:
        interrupt_at(patch, 'curriculum_revision_ready', 1)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, 'study-work')
    capsys.readouterr()
    deadline = MissionStore.open_default().get(job['mission_id']).diagnostics['study_state']['deadline_at']
    with monkeypatch.context() as patch:
        patch.setattr('plugins.mission_control.study_curriculum.time.time', lambda: deadline + 1)
        _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed' and 'deadline' in result['reason'], result
    assert len(calls) == 1


def test_source_abstention_does_not_trigger_correction(correction_job, capsys):
    fixture, responses = correction_job
    _, parser, _, _, _, _, ctx, calls, _ = fixture
    responses[0]['decline_reason'] = 'No source supports this task.'
    correction.typed.legacy.enqueue(fixture, capsys)
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed' and 'declined' in result['reason'], result
    assert len(calls) == 1
