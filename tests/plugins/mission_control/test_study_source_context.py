"""Bound source context without rewriting evidence or changing frozen legacy studies."""

import json

import pytest

from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control import test_study_curriculum as curriculum_tests
from tests.plugins.mission_control.test_study_jobs import command

job_profile = curriculum_tests.job_profile
admission_job = curriculum_tests.admission_job
curriculum_job = curriculum_tests.curriculum_job


def test_relevant_tail_keeps_original_span_ids_offsets_and_unicode():
    from plugins.mission_control.learning_study_sources import source_spans
    from plugins.mission_control.study_source_context import project_source

    text = ('Unrelated navigation and links.\n' * 900) + 'ZipInfo.file_size reports uncompressed bytes: ação.\n'
    selected, view = project_source(text, 'inspect ZIP sizes', {
        'strategy': 'lexical-spans-v1', 'max_characters': 2000, 'terms': ['file_size']})
    assert sum(len(row['text']) for row in selected) <= 2000
    assert any('ação' in row['text'] for row in selected)
    originals = {row['id']: row for row in source_spans(text)}
    assert all(row == originals[row['id']] and text[row['start']:row['end']] == row['text'] for row in selected)
    assert view['omitted_spans'] > 0 and view['source_characters'] == len(text)
    legacy, metadata = project_source(text, 'inspect ZIP sizes', None)
    assert legacy == source_spans(text) and metadata is None


def test_frozen_context_budget_survives_curriculum_restart_and_reaches_learner(curriculum_job, capsys, monkeypatch):
    from plugins.mission_control.study_curriculum import StudyCurriculum

    fixture, _ = curriculum_job
    _, parser, _, _, spec, path, ctx, calls, _ = fixture
    spec['source_context'] = {'strategy': 'lexical-spans-v1', 'max_characters': 2000, 'terms': ['pinned', 'commit']}
    path.write_text(json.dumps(spec), encoding='utf-8')
    original = ctx.dispatch_tool
    source_text = 'Inspect the pinned commit in the repository before running unfamiliar code.\n' + 'Unrelated navigation.\n' * 1200
    def dispatch(name, args):
        raw = json.loads(original(name, args))
        if name == 'web_extract':
            raw['results'][0]['content'] = source_text
        return json.dumps(raw)
    ctx.dispatch_tool = dispatch
    queued = curriculum_tests.enqueue(fixture, capsys)
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
    # Changing the editable export cannot enlarge a queued study's context.
    spec['source_context']['max_characters'] = 24000
    path.write_text(json.dumps(spec), encoding='utf-8')
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    assert [row['task'] for row in calls] == ['nara_curriculum', 'nara_media_study']
    curriculum = json.loads(calls[0]['input'][0]['text'])
    learner = json.loads(calls[1]['input'][0]['text'])
    assert sum(len(row['text']) for row in curriculum['source']['spans']) <= 2000
    assert sum(len(row['text']) for row in learner['source_spans']) <= 2000
    assert learner['source_context']['max_characters'] == 2000
    assert 'transfer_ONLY' not in json.dumps(learner) and 'canary_ONLY' not in json.dumps(learner)
    state = MissionStore.open_default().get(queued['mission_id']).diagnostics['study_state']
    stored = LearningFabric.open_default().source(state['research']['sources'][0]['source_id'])
    assert stored['extracted_text'] == source_text


@pytest.mark.parametrize('budget', [True, 1999, 24001])
def test_invalid_context_budget_is_rejected_before_research(curriculum_job, capsys, budget):
    fixture, _ = curriculum_job
    _, parser, _, plan, spec, path, ctx, calls, web_calls = fixture
    spec['source_context'] = {'strategy': 'lexical-spans-v1', 'max_characters': budget}
    path.write_text(json.dumps(spec), encoding='utf-8')
    code, result = command(ctx, parser, capsys, 'study-enqueue', plan.gap_id, '--protocol-file', str(path))
    assert code == 1 and 'context' in result['message']
    assert calls == [] and web_calls == []


def test_source_comparison_uses_bounded_views_with_original_citations(job_profile, capsys):
    from types import SimpleNamespace
    from tests.plugins.mission_control.test_learning_study import _model
    from tests.plugins.mission_control.test_study_jobs import proposal

    _, parser, _, plan, spec, path, ctx, calls, _ = job_profile
    spec.update(max_sources=2, source_context={'strategy': 'lexical-spans-v1', 'max_characters': 2000})
    path.write_text(json.dumps(spec), encoding='utf-8')
    urls = ['https://docs.example.org/colors', 'https://docs.example.org/repository']
    def dispatch(name, args):
        if name == 'web_search':
            return json.dumps({'data': {'web': [{'url': url} for url in urls]}})
        url = args['urls'][0]
        text = ('Choose interface colors.\n' if url == urls[0] else
                'Inspect the pinned commit in the repository before running unfamiliar code.\n')
        return json.dumps({'results': [{'url': url, 'content': text + 'Navigation link.\n' * 1400}]})
    def generate(**kwargs):
        if kwargs['task'] != 'nara_source_selection':
            return _model(proposal(), calls).complete_structured(**kwargs)
        sources = json.loads(kwargs['input'][0]['text'])['sources']
        for source in sources:
            assert source['source_context']['coverage'] == 'partial'
            assert sum(len(row['text']) for row in source['spans']) <= 2000
        package = {'selected_source_id': sources[1]['source_id'], 'decline_reason': '', 'assessments': [
            {'source_id': source['source_id'], 'fit': 'usable' if index else 'irrelevant',
             'reason': 'Relevant supplied evidence' if index else 'Only colors', 'limitations': 'Partial view',
             'source_span_ids': [source['spans'][0]['id']]}
            for index, source in enumerate(sources)]}
        return _model(package, calls).complete_structured(**kwargs)
    ctx.dispatch_tool, ctx.llm = dispatch, SimpleNamespace(complete_structured=generate)
    _, queued = command(ctx, parser, capsys, 'study-enqueue', plan.gap_id, '--protocol-file', str(path))
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    assert [row['task'] for row in calls] == ['nara_source_selection', 'nara_media_study']
    assert MissionStore.open_default().verify_projection(queued['mission_id'])


def test_resumed_practice_revision_retains_the_frozen_source_view(curriculum_job, capsys, monkeypatch):
    from plugins.mission_control.study_cycle import StudyCycle

    fixture, _ = curriculum_job
    _, parser, _, _, spec, path, ctx, calls, _ = fixture
    spec['source_context'] = {'strategy': 'lexical-spans-v1', 'max_characters': 2000}
    path.write_text(json.dumps(spec), encoding='utf-8')
    generate = ctx.llm.complete_structured
    learner_calls = 0
    def revise(**kwargs):
        nonlocal learner_calls
        result = generate(**kwargs)
        if kwargs['task'] == 'nara_media_study':
            learner_calls += 1
            if learner_calls == 1:
                result.parsed['steps'][0]['instruction'] = 'inspect a different branch'
        return result
    ctx.llm.complete_structured = revise
    queued = curriculum_tests.enqueue(fixture, capsys)
    progress = StudyCycle._progress
    class Interrupted(BaseException):
        pass
    def checkpoint(self, status):
        progress(self, status)
        if self.result['attempts'] and self.result['attempts'][0]['practice_complete']:
            raise Interrupted()
    with monkeypatch.context() as patch:
        patch.setattr(StudyCycle, '_progress', checkpoint)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, 'study-work')
    capsys.readouterr()
    before = MissionStore.open_default().get(queued['mission_id']).diagnostics['study_state']['deadline_at']
    _, result = command(ctx, parser, capsys, 'study-work')
    assert result['status'] == 'completed', result
    assert learner_calls == 2
    revision = json.loads(calls[-1]['input'][0]['text'])
    assert revision['source_context']['max_characters'] == 2000
    assert revision['development_feedback']['previous_steps'][0] == 'inspect a different branch'
    after = MissionStore.open_default().get(queued['mission_id']).diagnostics['study_state']['deadline_at']
    assert before == after
