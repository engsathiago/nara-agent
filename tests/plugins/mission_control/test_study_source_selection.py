"""Source choice must be evidenced, durable and separate from transfer proof."""

import json
from types import SimpleNamespace

import pytest

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control.test_learning_study import _model
from tests.plugins.mission_control import test_study_jobs as job_tests
from tests.plugins.mission_control.test_study_jobs import command, proposal

job_profile = job_tests.job_profile


@pytest.fixture
def comparison_job(job_profile):
    _, _, _, _, spec, path, ctx, calls, web_calls = job_profile
    spec["max_sources"] = 2
    path.write_text(json.dumps(spec), encoding="utf-8")
    urls = ["https://docs.example.org/colors", "https://docs.example.org/repository"]

    def dispatch(name, args):
        web_calls.append((name, args))
        if name == "web_search":
            return json.dumps({"success": True, "data": {"web": [{"url": url} for url in urls]}})
        url = args["urls"][0]
        content = ("Choose a pleasing color for the interface." if url == urls[0] else
                   "Inspect the pinned commit in the repository before running unfamiliar code.")
        return json.dumps({"results": [{"url": url, "content": content}]})

    def compare(**kwargs):
        if kwargs["task"] != "nara_source_selection":
            return _model(proposal(), calls).complete_structured(**kwargs)
        sources = json.loads(kwargs["input"][0]["text"])["sources"]
        payload = {"selected_source_id": sources[1]["source_id"], "decline_reason": "", "assessments": [
            {"source_id": source["source_id"], "fit": "usable" if index else "irrelevant",
             "reason": "Explains commit inspection" if index else "Only discusses colors",
             "limitations": "No execution observed", "source_span_ids": [source["spans"][0]["id"]]}
            for index, source in enumerate(sources)]}
        return _model(payload, calls).complete_structured(**kwargs)

    ctx.dispatch_tool = dispatch
    ctx.llm = SimpleNamespace(complete_structured=compare)
    return job_profile


def enqueue(profile, capsys):
    _, parser, _, plan, _, path, ctx, _, _ = profile
    _, queued = command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    return queued


def test_job_compares_sources_and_studies_second_with_exact_citations(comparison_job, capsys):
    _, parser, registry, plan, _, _, ctx, calls, web_calls = comparison_job
    queued = enqueue(comparison_job, capsys)
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "completed", result
    assert [call["task"] for call in calls] == ["nara_source_selection", "nara_media_study"]
    assert calls[0]["task"] in ctx.auxiliary_tasks
    assert "HOLDOUT_PRIVATE_EXPECTATION" not in json.dumps(calls + web_calls)
    store = MissionStore.open_default()
    state = store.get(queued["mission_id"]).diagnostics["study_state"]
    receipt = json.loads(ArtifactStore.open_default().read_bytes(queued["mission_id"], state["selection_artifact_id"]))
    assert receipt["method"] == "model_comparison" and receipt["usage"]["total_tokens"] == 50
    selected = state["research"]["sources"][1]
    assert receipt["selection"]["selected_source_id"] == selected["source_id"]
    assert registry.study_plan(queued["mission_id"]).sources[0]["uri"] == selected["source_id"]
    source = LearningFabric.open_default().source(selected["source_id"])
    assert receipt["selection"]["assessments"][1]["citations"][0]["text"] == source["extracted_text"]
    assert registry.gap(plan.gap_id)["state"] == "resolved"


@pytest.mark.parametrize("failure", ["foreign_id", "missing_review", "bad_span", "declined"])
def test_invalid_or_declined_comparison_never_falls_back_to_first_source(comparison_job, capsys, failure):
    _, parser, registry, plan, _, _, ctx, calls, _ = comparison_job
    original = ctx.llm.complete_structured

    def altered(**kwargs):
        response = original(**kwargs)
        if kwargs["task"] == "nara_source_selection":
            payload = response.parsed
            if failure == "foreign_id":
                payload["selected_source_id"] = "not-acquired"
            elif failure == "missing_review":
                payload["assessments"].pop(0)
            elif failure == "bad_span":
                payload["assessments"][1]["source_span_ids"] = ["invented"]
            else:
                payload.update(selected_source_id="", decline_reason="Insufficient evidence")
            return _model(payload, []).complete_structured(**kwargs)
        return response

    ctx.llm = SimpleNamespace(complete_structured=altered)
    queued = enqueue(comparison_job, capsys)
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "failed", result
    assert len(calls) == 1 and calls[0]["task"] == "nara_source_selection"
    assert registry.gap(plan.gap_id)["state"] == "unresolved" and registry.current() == []
    with pytest.raises(KeyError):
        registry.study_plan(queued["mission_id"])


@pytest.mark.parametrize("boundary", ["selection_running", "sources_selected"])
def test_restart_reuses_confirmed_choice_but_does_not_repeat_unknown_selection(comparison_job, capsys, monkeypatch, boundary):
    from plugins.mission_control.study_jobs import StudyJobs

    _, parser, registry, plan, _, _, ctx, calls, web_calls = comparison_job
    queued = enqueue(comparison_job, capsys)
    checkpoint = StudyJobs._checkpoint

    class Interrupted(BaseException):
        pass

    def stop(self, identity, state):
        checkpoint(self, identity, state)
        if state["phase"] == boundary:
            raise Interrupted()

    with monkeypatch.context() as patch:
        patch.setattr(StudyJobs, "_checkpoint", stop)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, "study-work")
    capsys.readouterr()
    _, result = command(ctx, parser, capsys, "study-work")
    assert len(web_calls) == 3
    if boundary == "selection_running":
        assert result["status"] == "failed" and "unconfirmed" in result["reason"]
        assert calls == [] and registry.current() == []
    else:
        assert result["status"] == "completed" and len(calls) == 2
        assert registry.gap(plan.gap_id)["state"] == "resolved"
    assert MissionStore.open_default().verify_projection(queued["mission_id"])


def test_confirmed_choice_cannot_resume_with_changed_source_bytes(comparison_job, capsys, monkeypatch):
    from pathlib import Path
    from plugins.mission_control.study_jobs import StudyJobs

    _, parser, registry, _, _, _, ctx, calls, web_calls = comparison_job
    queued = enqueue(comparison_job, capsys)
    checkpoint = StudyJobs._checkpoint

    class Interrupted(BaseException):
        pass

    def stop(self, identity, state):
        checkpoint(self, identity, state)
        if state["phase"] == "sources_selected":
            raise Interrupted()

    with monkeypatch.context() as patch:
        patch.setattr(StudyJobs, "_checkpoint", stop)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, "study-work")
    capsys.readouterr()
    state = MissionStore.open_default().get(queued["mission_id"]).diagnostics["study_state"]
    selected = state["research"]["sources"][1]
    source = LearningFabric.open_default().source(selected["source_id"])
    Path(source["stored_path"]).write_text("Changed evidence", encoding="utf-8")
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "failed" and "changed" in result["reason"]
    assert len(calls) == 1 and len(web_calls) == 3 and registry.current() == []


def test_old_protocol_job_retains_original_choice_without_extra_model_calls(comparison_job, capsys, monkeypatch):
    from plugins.mission_control import study_jobs

    _, parser, registry, _, _, _, ctx, calls, _ = comparison_job
    freeze = study_jobs.freeze_protocol

    def legacy(root, spec):
        from pathlib import Path
        ref = freeze(root, spec)
        protocol = json.loads(Path(ref["path"]).read_text(encoding="utf-8-sig"))
        protocol["schema_version"] = 1
        return study_jobs._freeze_bytes(root, json.dumps(protocol, sort_keys=True).encode(), ".json")

    with monkeypatch.context() as patch:
        patch.setattr(study_jobs, "freeze_protocol", legacy)
        queued = enqueue(comparison_job, capsys)
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "completed", result
    assert [call["task"] for call in calls] == ["nara_media_study"]
    state = MissionStore.open_default().get(queued["mission_id"]).diagnostics["study_state"]
    assert registry.study_plan(queued["mission_id"]).sources[0]["uri"] == state["research"]["sources"][0]["source_id"]


def test_identical_pages_share_one_evidence_source_without_false_comparison(comparison_job, capsys):
    _, parser, registry, plan, _, _, ctx, calls, _ = comparison_job
    original = ctx.dispatch_tool

    def mirror(name, args):
        result = json.loads(original(name, args))
        if name == "web_extract":
            result["results"][0]["content"] = "Inspect the pinned commit in the repository before running unfamiliar code."
        return json.dumps(result)

    ctx.dispatch_tool = mirror
    queued = enqueue(comparison_job, capsys)
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "completed", result
    assert [call["task"] for call in calls] == ["nara_media_study"]
    state = MissionStore.open_default().get(queued["mission_id"]).diagnostics["study_state"]
    artifacts = ArtifactStore.open_default()
    receipt = json.loads(artifacts.read_bytes(queued["mission_id"], state["selection_artifact_id"]))
    request = json.loads(artifacts.read_bytes(queued["mission_id"], receipt["request_artifact_id"]))
    assert receipt["method"] == "single_source_not_compared"
    assert len(request["input"]["sources"]) == 1
    assert len(request["input"]["sources"][0]["acquired_urls"]) == 2
    assert registry.gap(plan.gap_id)["state"] == "resolved"
