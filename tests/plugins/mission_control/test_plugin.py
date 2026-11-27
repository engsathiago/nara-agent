from __future__ import annotations

import json
from types import SimpleNamespace

from plugins import mission_control
from plugins.mission_control import cli
from plugins.mission_control.store import MissionStore


class _Context:
    def __init__(self):
        self.command = None
        self.hooks = {}
        self.tools = {}
        self.auxiliary_tasks = {}

    def get_config(self, key, default=None):
        return default

    def register_auxiliary_task(self, name, **kwargs):
        self.auxiliary_tasks[name] = kwargs

    def register_cli_command(self, **kwargs):
        self.command = kwargs

    def register_hook(self, name, handler):
        self.hooks[name] = handler

    def register_tool(self, name, **kwargs):
        self.tools[name] = kwargs

    def dispatch_tool(self, name, args):
        raise AssertionError("not used")


def test_plugin_registers_real_mission_cli():
    context = _Context()

    mission_control.register(context)

    assert context.command["name"] == "mission"
    assert context.command["setup_fn"] is cli.register_cli
    assert callable(context.command["handler_fn"])
    assert set(context.hooks) == {
        "kanban_task_completed", "kanban_task_blocked", "pre_tool_call", "post_tool_call",
        "kanban_task_claimed", "on_kanban_worker_exited", "on_kanban_worker_stale_claim",
        "post_llm_call",
        "voice_wake_detected", "voice_transcript", "pre_llm_call",
        "on_gateway_housekeeping",
    }
    assert callable(context.hooks["on_gateway_housekeeping"])
    assert set(context.tools) == {
        "nara_competence_status", "nara_gap_record", "nara_evolution_status",
        "nara_learning_ingest", "nara_learning_fetch", "nara_learning_claim_propose", "nara_learning_frame_extract",
        "nara_learning_repo_verify", "nara_learning_media_procedure_propose",
        "nara_learning_status",
        "nara_specialist_resolve", "nara_specialist_get",
        "nara_fleet_status",
        "nara_voice_presence",
        "nara_trading_init", "nara_trading_backtest", "nara_trading_status",
        "nara_rea_route", "nara_rea_status",
        "nara_policy_status", "nara_policy_explain", "nara_policy_confirm",
        "nara_policy_stage", "nara_policy_promote", "nara_policy_rollback",
        "nara_privacy_status", "nara_privacy_configure", "nara_privacy_export",
    }


def test_registered_tool_handler_accepts_json_object_and_returns_json(tmp_path, monkeypatch):
    monkeypatch.setenv("NARA_HOME", str(tmp_path))
    context = _Context()
    mission_control.register(context)

    raw = context.tools["nara_policy_status"]["handler"]({})
    status = json.loads(raw)

    assert status["active"]["version_id"] == "default-observe-only-v1"
    assert status["active"]["mode"] == "observe_only"


def test_tool_adapter_maps_payload_fields_and_serializes_result():
    def sample(*, value, suffix="", **context):
        return {"result": f"{value}{suffix}", "session": context["session_id"]}

    handler = mission_control._tool_handler(sample)

    assert json.loads(handler(
        {"value": "nara", "suffix": "-ok"}, session_id="session-1"
    )) == {"result": "nara-ok", "session": "session-1"}


def test_cli_create_and_show_use_durable_store(tmp_path, monkeypatch, capsys):
    store = MissionStore(tmp_path / "missions.db")
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: store))
    create = SimpleNamespace(
        mission_action="create", mission_id="mission-cli", objective="Build report",
        criteria=["file exists"], session_id="session-1", idempotency_key="create-cli",
    )

    assert cli.mission_command(create) == 0
    created = capsys.readouterr().out
    assert '"mission_id": "mission-cli"' in created

    show = SimpleNamespace(mission_action="show", mission_id="mission-cli", events=True)
    assert cli.mission_command(show) == 0
    output = capsys.readouterr().out
    assert '"event_type": "mission.created"' in output


def test_cli_receipt_and_artifact_surfaces_are_real(tmp_path, monkeypatch, capsys):
    store = MissionStore(tmp_path / "missions.db")
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: store))
    store.create(__import__("plugins.mission_control.contracts", fromlist=["Mission"]).Mission(
        mission_id="mission-cli", objective="Build report", completion_criteria=["file exists"],
    ))
    source = tmp_path / "report.txt"
    source.write_text("verified report", encoding="utf-8")

    prepare = SimpleNamespace(
        mission_action="receipt-prepare", mission_id="mission-cli", task_id="task-1",
        intention="write report", agent="worker-1", tool="file.write", target=str(source),
        idempotency_key="write-report", receipt_id="receipt-cli", adapter_version="1",
    )
    assert cli.mission_command(prepare) == 0
    assert '"effect_status": "pending"' in capsys.readouterr().out

    artifact = SimpleNamespace(
        mission_action="artifact-add", mission_id="mission-cli", path=source,
        producer="worker-1", media_type="text/plain", metadata={},
    )
    assert cli.mission_command(artifact) == 0
    output = capsys.readouterr().out
    assert '"artifact_id": "sha256:' in output
