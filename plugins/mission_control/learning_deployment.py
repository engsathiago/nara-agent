"""Serialized publication and removal of the exact evaluated native skill."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from plugins.mission_control.learning_acceptance import check_minimum_score
from plugins.mission_control.study_checkpoint import study_lock


def skill_artifact(lab, candidate):
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in candidate.name)
    slug = "-".join(part for part in normalized.split("-") if part)[:60] or "learned-procedure"
    name = f"nara-learned-{slug}-{candidate.candidate_id[:8]}"
    procedure = "\n".join(f"{index}. {step}" for index, step in enumerate(candidate.steps, start=1))
    body = (
        "---\n"
        f"name: {name}\n"
        f"description: {json.dumps(candidate.description, ensure_ascii=False)}\n"
        "version: 1.0.0\n"
        "author: Nara Evolution Lab\n"
        "metadata:\n"
        f"  {'source_media' if candidate.mission_id.startswith('media:') else 'source_mission'}: {candidate.mission_id}\n"
        f"  candidate_id: {candidate.candidate_id}\n"
        "---\n\n"
        f"# {candidate.name}\n\n"
        "## Procedure\n\n"
        f"{procedure}\n\n"
        "## Verification\n\n"
        "Re-run the target task's independent completion criteria and preserve evidence.\n"
    )
    return lab.skill_root / name, body.encode("utf-8")


def _publish(destination, content):
    path = destination / "SKILL.md"
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("published skill differs from the evaluated procedure; refusing to overwrite")
        return
    destination.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("wb", dir=destination, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _archive_target(lab, candidate, active):
    archive = lab.skill_root / ".archive"
    default = archive / (active.name + ".disabled")
    payload = json.loads(lab._candidate_path(candidate.candidate_id).read_text(encoding="utf-8-sig"))
    saved = Path(payload["skill_path"]) if payload.get("skill_path") else None
    if (saved is not None and saved.is_dir() and saved.parent.resolve() == archive.resolve()
            and (saved.name == default.name or saved.name.startswith(default.name + "-"))):
        return saved
    matches = [path for path in archive.glob(default.name + "*") if path.is_dir()]
    if len(matches) > 1:
        raise ValueError("multiple archived skill versions exist; reconcile before deployment")
    return matches[0] if matches else default


def promote(lab, candidate_id, *, require_evidence):
    with study_lock(lab.candidate_root, "deployment:" + candidate_id):
        report = lab.verified_evaluation(candidate_id, require_evidence=require_evidence)
        if not report.get("passed"):
            raise ValueError("candidate did not pass reserved transfer evaluation")
        check_minimum_score(report)
        candidate = lab.load(candidate_id)
        destination, body = skill_artifact(lab, candidate)
        disabled = _archive_target(lab, candidate, destination)
        if candidate.status == "rolled_back" or disabled.exists():
            raise ValueError("skill was rolled back or rollback is incomplete; it cannot be republished")
        if (destination / "SKILL.md").exists() and (destination / "SKILL.md").read_bytes() != body:
            raise ValueError("published skill differs from the evaluated procedure; refusing to overwrite")
        # Memory first: a failed evidence promotion must never leave a loadable skill.
        # The provider's promotion is idempotent; publication preserves matching bytes.
        lab.memory.promote("procedure:" + candidate_id)
        _publish(destination, body)
        lab._write_json(lab._candidate_path(candidate_id), {
            **candidate.to_dict(), "status": "promoted", "skill_path": str(destination)})
        return destination


def rollback(lab, candidate_id):
    with study_lock(lab.candidate_root, "deployment:" + candidate_id):
        candidate = lab.load(candidate_id)
        active, _ = skill_artifact(lab, candidate)
        archive = lab.skill_root / ".archive"
        disabled = _archive_target(lab, candidate, active)
        if active.exists():
            if disabled.exists():
                raise ValueError("both active and archived skill exist; reconcile before rollback")
            archive.mkdir(parents=True, exist_ok=True)
            active.replace(disabled)
        elif not disabled.exists():
            raise ValueError("promoted skill not found")
        memory = lab.memory.get("procedure:" + candidate_id)
        if memory["status"] != "rejected":
            lab.memory.reject("procedure:" + candidate_id)
        lab._write_json(lab._candidate_path(candidate_id), {
            **candidate.to_dict(), "status": "rolled_back", "skill_path": str(disabled)})
        return disabled
