"""Login shells in the image keep Nara' own dirs on PATH.

Debian's ``/etc/profile`` resets PATH for every login shell, so without
``/etc/profile.d/nara.sh`` a ``bash -l`` (``docker exec <c> bash -l``, ssh, the
terminal tool's background ``bash -lic``) lost ``/opt/nara/bin`` and bare
``nara`` exited 127 (#56634).
"""
from __future__ import annotations

import subprocess


def test_login_shell_resolves_nara_to_the_image_shim(built_image: str) -> None:
    r = subprocess.run(
        ["docker", "run", "--rm", "-u", "nara", "--entrypoint", "bash", built_image,
         "-lc", 'echo "nara=$(command -v nara)"; echo "path=$PATH"'],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert r.returncode == 0, r.stderr
    lines = dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)
    assert lines["nara"] == "/opt/nara/bin/nara"
    entries = lines["path"].split(":")
    assert entries.index("/opt/nara/bin") < entries.index("/opt/nara/.venv/bin")
    assert entries.count("/opt/nara/bin") == 1
