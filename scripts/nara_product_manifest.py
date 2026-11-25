#!/usr/bin/env python3
"""Build a deterministic, secret-free manifest for a Nara source release."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


INCLUDED_ROOTS = (
    "plugins/mission_control",
    "extensions/nara_temporal_memory",
    "evals",
    "docs",
)
INCLUDED_FILES = (
    "NARA_DATASHEET.md",
    "NARA_BUILD_CONTRACT.md",
    "UPSTREAM_PROVENANCE.md",
    "pyproject.toml",
    "uv.lock",
    "scripts/install.sh",
    "scripts/install.ps1",
    "scripts/install.cmd",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def build_manifest(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    paths = [repo / item for item in INCLUDED_FILES]
    for root_name in INCLUDED_ROOTS:
        root = repo / root_name
        if root.is_dir():
            paths.extend(path for path in root.rglob("*") if path.is_file())
    entries = []
    for path in sorted(set(paths)):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        entries.append({
            "path": path.relative_to(repo).as_posix(), "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    payload = {
        "schema_version": 1,
        "product": "Nara",
        "command": "nara",
        "git_commit": _git(repo, "rev-parse", "HEAD"),
        "git_branch": _git(repo, "branch", "--show-current"),
        "working_tree_clean": not bool(_git(repo, "status", "--porcelain")),
        "required_components": {
            "mission_control": "bundled",
            "nara_temporal": "extensions/nara_temporal_memory",
            "rea": "catalog pin 1690b63a4790cb821fb6a319ba524815d4e09411",
        },
        "state_compatibility": {
            "mission_contract_schema": 1,
            "policy_schema": 1,
            "backup_command": "nara backup",
            "restore_command": "nara import",
        },
        "files": entries,
    }
    payload["content_set_sha256"] = hashlib.sha256(json.dumps(
        entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = build_manifest(args.repo)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        destination = args.output.expanduser().resolve()
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(encoded, encoding="utf-8")
        print(destination)
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
