"""Generated exercises must pass an independent domain validator before study."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control import test_study_admission as admission_tests
from tests.plugins.mission_control.test_learning_study import _model
from tests.plugins.mission_control.test_study_jobs import command, proposal

job_profile = admission_tests.job_profile
admission_job = admission_tests.admission_job


@pytest.fixture
def curriculum_job(admission_job, tmp_path):
    _, _, _, _, spec, path, ctx, calls, _ = admission_job
    native = spec.pop("skill_admission")
    spec.pop("cases_file")
    spec.pop("development_case_ids")
    brief = tmp_path / "curriculum-brief.json"
    brief.write_text(json.dumps({"task_family": "pinned repository inspection",
                                 "case_contract": "requires is the procedure to be exercised"}), encoding="utf-8")
    validator = tmp_path / "case-validator.py"
    validator.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "request=json.load(sys.stdin)\npackage=request['case']['curriculum']\n"
        "ok=all(row['payload']['requires']=='inspect the pinned commit' for row in package['cases'])\n"
        "ok=ok and all('pinned commit' in q['answer'] for q in package['teaching_material']['questions'])\n"
        "Path('validation.json').write_text(json.dumps({'valid':ok,'package':package}))\n"
        "print(json.dumps({'score':float(ok),'artifact_paths':['validation.json'],'cost_usd':0}))\n",
        encoding="utf-8")
    spec['curriculum'] = {"brief_file": str(brief), "validator": str(validator),
                          "canary_evaluator": native['evaluator']}
    package = {"explanation": "Check the pinned repository version before use.",
               "questions": [{"question": "What version should be inspected?", "answer": "The pinned commit.",
                              "source_span_ids": ["s0000"]}],
               "cases": [
                   {"case_id": kind + '-new', "split": kind, "group_id": kind + '-repo',
                    "payload_json": json.dumps({"requires": "inspect the pinned commit", "private": kind + '_ONLY'})}
                   for kind in ('development', 'transfer', 'canary')], "decline_reason": ""}

    def generate(**kwargs):
        return _model(package if kwargs['task'] == 'nara_curriculum' else proposal(), calls).complete_structured(**kwargs)

    ctx.llm = SimpleNamespace(complete_structured=generate)
    path.write_text(json.dumps(spec), encoding="utf-8")
    return admission_job, package


def enqueue(fixture, capsys):
    _, parser, _, plan, _, path, ctx, _, _ = fixture
    code, queued = command(ctx, parser, capsys, 'study-enqueue', plan.gap_id, '--protocol-file', str(path))
    assert code == 0, queued
    return queued


def test_background_study_generates_and_validates_cases_before_learning(curriculum_job, capsys):
    fixture, _ = curriculum_job
    home, parser, registry, plan, spec, _, ctx, calls, _ = fixture
    job = enqueue(fixture, capsys)
    # Only the frozen inputs may be used after enqueue.
    for path in spec['curriculum'].values():
        Path(path).unlink()
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    assert [call['task'] for call in calls] == ['nara_curriculum', 'nara_media_study']
    learner = json.loads(calls[1]['input'][0]['text'])
    assert learner['study_material']['questions'][0]['answer'] == 'The pinned commit.'
    assert 'transfer_ONLY' not in json.dumps(learner) and 'canary_ONLY' not in json.dumps(learner)
    assert list((home / 'skills').glob('nara-learned-*/SKILL.md'))
    assert registry.gap(plan.gap_id)['state'] == 'resolved'
    mission = MissionStore.open_default().get(job['mission_id'])
    assert mission.diagnostics['study_state']['curriculum_validation_artifact_id']
    assert MissionStore.open_default().verify_projection(job['mission_id'])


def test_generated_false_answer_never_reaches_the_learner(curriculum_job, capsys):
    fixture, package = curriculum_job
    _, parser, registry, plan, _, _, ctx, calls, _ = fixture
    package['cases'][0]['payload_json'] = json.dumps({'requires': 'trust the latest unpinned branch'})
    enqueue(fixture, capsys)
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed' and 'curriculum validator' in result['reason'], result
    assert [call['task'] for call in calls] == ['nara_curriculum']
    assert registry.gap(plan.gap_id)['state'] == 'unresolved'


def test_generated_group_leakage_is_rejected_before_validation(curriculum_job, capsys):
    fixture, package = curriculum_job
    _, parser, _, _, _, _, ctx, calls, _ = fixture
    package['cases'][1]['group_id'] = package['cases'][0]['group_id']
    enqueue(fixture, capsys)
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed' and 'group' in result['reason'], result
    assert len(calls) == 1


@pytest.mark.parametrize('phase', ['curriculum_generating', 'curriculum_generated',
                                   'curriculum_validating', 'curriculum_validated'])
def test_curriculum_restart_never_repeats_unconfirmed_calls(curriculum_job, capsys, monkeypatch, tmp_path, phase):
    from plugins.mission_control.study_curriculum import StudyCurriculum

    fixture, _ = curriculum_job
    _, parser, _, _, spec, path, ctx, calls, web_calls = fixture
    trace = tmp_path / 'validator-calls'
    validator = Path(spec['curriculum']['validator'])
    validator.write_text(validator.read_text(encoding='utf-8-sig').replace(
        "request=json.load(sys.stdin)",
        f"with open({str(trace)!r},'a',encoding='utf-8') as log: log.write('called\\n')\nrequest=json.load(sys.stdin)"), encoding='utf-8')
    path.write_text(json.dumps(spec), encoding='utf-8')
    job = enqueue(fixture, capsys)
    save = StudyCurriculum._save

    class Interrupted(BaseException):
        pass

    def checkpoint(self, stage, **updates):
        save(self, stage, **updates)
        if stage == phase:
            raise Interrupted()

    with monkeypatch.context() as patch:
        patch.setattr(StudyCurriculum, '_save', checkpoint)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, 'study-work')
    capsys.readouterr()
    deadline = MissionStore.open_default().get(job['mission_id']).diagnostics['study_state']['deadline_at']
    _, resumed = command(ctx, parser, capsys, 'study-work')
    confirmed = phase in {'curriculum_generated', 'curriculum_validated'}
    assert resumed['status'] == ('completed' if confirmed else 'failed'), resumed
    assert len(calls) == (2 if confirmed else (0 if phase == 'curriculum_generating' else 1))
    assert (trace.read_text(encoding='utf-8-sig') if trace.exists() else '') == ('called\n' if confirmed else '')
    assert len(web_calls) == 2
    state = MissionStore.open_default().get(job['mission_id']).diagnostics['study_state']
    assert state['deadline_at'] == deadline
    assert MissionStore.open_default().verify_projection(job['mission_id'])


def test_gateway_generates_curriculum_without_operator_supplied_cases(curriculum_job):
    from tests.waiting import wait_until

    fixture, _ = curriculum_job
    home, _, _, _, spec, _, ctx, calls, _ = fixture
    ctx.get_config = lambda key, default=None: {'enabled': True, 'protocols': {'repositories': spec}, 'interval_seconds': 600}
    hook = ctx.hooks['on_gateway_housekeeping']
    assert hook()['study']['state'] == 'started'
    try:
        wait_until(lambda: any(job.status == 'completed' and job.constraints.get('study_job')
                               for job in MissionStore.open_default().list()),
                   timeout=30, what='generated curriculum background study')
        assert list((home / 'skills').glob('nara-learned-*/SKILL.md'))
        assert [call['task'] for call in calls] == ['nara_curriculum', 'nara_media_study']
    finally:
        wait_until(lambda: hook()['study']['state'] == 'not_due', timeout=30,
                   what='owned curriculum worker exit')


def test_corrupt_validation_evidence_prevents_curriculum_replay(curriculum_job, capsys, monkeypatch):
    from plugins.mission_control.artifacts import ArtifactStore
    from plugins.mission_control.study_curriculum import StudyCurriculum

    fixture, _ = curriculum_job
    _, parser, _, _, _, _, ctx, calls, _ = fixture
    job = enqueue(fixture, capsys)
    save = StudyCurriculum._save

    class Interrupted(BaseException):
        pass

    def checkpoint(self, stage, **updates):
        save(self, stage, **updates)
        if stage == 'curriculum_validated':
            raise Interrupted()

    with monkeypatch.context() as patch:
        patch.setattr(StudyCurriculum, '_save', checkpoint)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, 'study-work')
    capsys.readouterr()
    store = MissionStore.open_default()
    state = store.get(job['mission_id']).diagnostics['study_state']
    receipt = json.loads(ArtifactStore(store, store.path.parent / 'artifacts').read_bytes(
        job['mission_id'], state['curriculum_validation_artifact_id']))
    Path(receipt['result']['evidence'][0]['path']).write_bytes(b'changed')
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'failed' and 'evidence' in result['reason'], result
    assert len(calls) == 1
