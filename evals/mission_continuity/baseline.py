"""Executable WP-00 inventory and continuity-fixture readiness scorecard.

This module deliberately does not simulate Mission Control. It probes the real checkout,
distinguishes the inherited substrate from the mission layer wired on top of it, and reports
exactly why the Phase 1 continuity fixture can or cannot run.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
DEFAULT_FIXTURE = Path(__file__).with_name("fixture_v1.json")
MATURITY_ORDER = {name: rank for rank, name in enumerate((
    "discovered", "wired", "verified", "operational", "promoted"))}


@dataclass(frozen=True)
class Capability:
    capability_id: str
    availability: str
    maturity: str
    evidence: str
    limitation: str | None = None


@dataclass(frozen=True)
class ModuleProbe:
    capability_id: str
    module: str
    maturity: str = "wired"
    limitation: str | None = None


MODULE_PROBES = (
    ModuleProbe("substrate.session_db", "nara_state",
                limitation="Session storage remains separate from the authoritative mission event log."),
    ModuleProbe("substrate.goals", "nara_cli.goals"),
    ModuleProbe("substrate.kanban", "nara_cli.kanban_db"),
    ModuleProbe("substrate.turn_receipts", "agent.persisted_turn_receipt",
                limitation="Turn receipts remain distinct from mission external-effect receipts."),
    ModuleProbe("substrate.tool_result_storage", "tools.tool_result_storage",
                limitation="Large tool-result storage remains distinct from the mission Artifact Store."),
    ModuleProbe("mission.verifier", "plugins.mission_control.verification"),
    ModuleProbe("substrate.delegation", "tools.delegate_tool"),
    ModuleProbe("tools.file", "tools.file_operations"),
    ModuleProbe("tools.terminal", "tools.terminal_tool"),
    ModuleProbe("tools.browser", "tools.browser_tool"),
    ModuleProbe("mission.control", "plugins.mission_control"),
    ModuleProbe("mission.event_log", "plugins.mission_control.store"),
    ModuleProbe("mission.receipt_store", "plugins.mission_control.receipts"),
    ModuleProbe("mission.artifact_store", "plugins.mission_control.artifacts"),
)


def _module_capability(probe: ModuleProbe, find_spec: Callable[[str], object | None]) -> Capability:
    try:
        spec = find_spec(probe.module)
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        return Capability(probe.capability_id, "unavailable", "discovered", f"module probe failed: {exc}")
    if spec is None:
        return Capability(probe.capability_id, "unavailable", "discovered",
                          f"module {probe.module} is not present", probe.limitation)
    return Capability(probe.capability_id, "available", probe.maturity,
                      f"module {probe.module} resolves", probe.limitation)


def _runtime_capability(
    which: Callable[[str], str | None],
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> Capability:
    executable = which("nara")
    if not executable:
        return Capability("runtime.command", "unavailable", "discovered", "nara is not on PATH")
    try:
        result = run([executable, "--version"], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return Capability("runtime.command", "degraded", "wired", f"version probe failed: {exc}")
    version = (result.stdout or result.stderr).strip().splitlines()
    if result.returncode != 0:
        return Capability("runtime.command", "degraded", "wired",
                          f"{executable} --version exited {result.returncode}")
    return Capability("runtime.command", "available", "verified",
                      f"{executable}: {version[0] if version else 'version probe passed'}")


def collect_inventory(
    *,
    find_spec: Callable[[str], object | None] = importlib.util.find_spec,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[Capability]:
    capabilities = [_runtime_capability(which, run)]
    capabilities.extend(_module_capability(probe, find_spec) for probe in MODULE_PROBES)
    return sorted(capabilities, key=lambda item: item.capability_id)


def load_fixture(path: Path = DEFAULT_FIXTURE) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    required = ("schema_version", "fixture_id", "objective", "required_capabilities", "steps", "acceptance")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"fixture is missing required fields: {', '.join(missing)}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported fixture schema: {payload['schema_version']}")
    if not payload["steps"] or not payload["acceptance"]:
        raise ValueError("fixture steps and acceptance must be non-empty")
    step_ids = [str(step.get("id") or "") for step in payload["steps"]]
    if any(not step_id for step_id in step_ids) or len(step_ids) != len(set(step_ids)):
        raise ValueError("fixture step IDs must be non-empty and unique")
    return payload


def build_scorecard(
    fixture: Mapping,
    capabilities: Iterable[Capability],
    *,
    generated_at: str | None = None,
) -> dict:
    inventory = {item.capability_id: item for item in capabilities}
    blockers: list[dict[str, str]] = []
    for capability_id in fixture["required_capabilities"]:
        capability = inventory.get(capability_id)
        if capability is None:
            blockers.append({"capability_id": capability_id, "reason": "not inventoried"})
        elif capability.availability != "available":
            blockers.append({
                "capability_id": capability_id,
                "reason": capability.limitation or capability.evidence,
            })
        elif MATURITY_ORDER[capability.maturity] < MATURITY_ORDER["wired"]:
            blockers.append({
                "capability_id": capability_id,
                "reason": f"maturity is {capability.maturity}; fixture requires wired or higher",
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "nara.phase1.baseline",
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "fixture": {
            "fixture_id": fixture["fixture_id"],
            "objective": fixture["objective"],
            "step_count": len(fixture["steps"]),
            "acceptance_count": len(fixture["acceptance"]),
        },
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "capabilities": [asdict(item) for item in sorted(inventory.values(), key=lambda item: item.capability_id)],
    }


def write_scorecard(path: Path, scorecard: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(scorecard, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe Nara Phase 1 readiness without simulating missing capabilities.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, help="Atomically write the JSON scorecard to this path.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 while the continuity fixture is blocked.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    scorecard = build_scorecard(load_fixture(args.fixture), collect_inventory())
    if args.output:
        write_scorecard(args.output, scorecard)
    print(json.dumps(scorecard, indent=2, sort_keys=True))
    return int(args.strict and scorecard["status"] != "ready")


if __name__ == "__main__":
    sys.exit(main())

