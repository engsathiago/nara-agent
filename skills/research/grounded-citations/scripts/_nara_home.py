"""Resolve NARA_HOME for standalone skill scripts.

Skill scripts may run outside the Nara process (system Python, nix env,
CI) where ``nara_constants`` is not importable.  This module provides the
same ``get_nara_home()`` contract without requiring it on ``sys.path``.

When ``nara_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from nara_constants import get_nara_home
except (ModuleNotFoundError, ImportError):

    def get_nara_home() -> Path:
        """Return the Nara home directory (default: ``~/.nara``)."""
        val = os.environ.get("NARA_HOME", "").strip()
        return Path(val) if val else Path.home() / ".nara"
