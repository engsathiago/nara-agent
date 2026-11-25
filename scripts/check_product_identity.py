#!/usr/bin/env python3
"""Reject legacy product identity outside explicit external provenance.

The allowlist is intentionally structural, not a growing list of files: research may name the
projects it studied, the provenance document may name the fork source, and catalog source URL
fields may preserve real third-party repository names. Runtime code, operational documentation,
commands, examples and catalog prose must use Nara only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LEGACY = re.compile(r"(?i)(?:\bathena\b|athena2|hermes)")
CATALOG_SOURCE = re.compile(
    r"^\s*(?:repo|docs_url|image):\s*[\"']?https?://[^\s]+\s*$",
    re.IGNORECASE,
)
LOCK_DEPENDENCY = re.compile(r"hermes-(?:parser|estree)", re.IGNORECASE)


def tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        sys.stderr.write(proc.stderr.decode(errors="replace"))
        raise SystemExit(proc.returncode)
    return [ROOT / item.decode() for item in proc.stdout.split(b"\0") if item]


def allowed(path: Path, line: str) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if rel == "scripts/check_product_identity.py":
        return True
    if rel == "UPSTREAM_PROVENANCE.md" or rel.startswith("research/"):
        return True
    if rel == "pnpm-lock.yaml" and LOCK_DEPENDENCY.search(line):
        return True
    return rel.startswith("plugin-catalog/") and CATALOG_SOURCE.match(line) is not None


def main() -> int:
    failures: list[str] = []
    for path in tracked_files():
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(content.splitlines(), 1):
            if LEGACY.search(line) and not allowed(path, line):
                failures.append(f"{path.relative_to(ROOT)}:{number}:{line.strip()}")

    if failures:
        print("Legacy identity found outside external provenance:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("product identity: Nara-only active surfaces verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
