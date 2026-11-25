"""Resolve NARA_HOME for standalone skill scripts.

Skill scripts may run outside the Nara process (e.g. system Python,
nix env, CI) where ``nara_constants`` is not importable.  This module
provides the same ``get_nara_home()`` and ``display_nara_home()``
contracts as ``nara_constants`` without requiring it on ``sys.path``.

When ``nara_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``nara_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``NARA_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from nara_constants import display_nara_home
    from nara_constants import get_nara_home
except (ModuleNotFoundError, ImportError):

    def get_nara_home() -> Path:
        """Return the Nara home directory (default: ~/.nara).

        Mirrors ``nara_constants.get_nara_home()``."""
        val = os.environ.get("NARA_HOME", "").strip()
        return Path(val) if val else Path.home() / ".nara"

    def display_nara_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``nara_constants.display_nara_home()``."""
        home = get_nara_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(home)
