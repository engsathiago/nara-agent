"""Conservative recall consolidation for exact, current, same-scope facts."""

from __future__ import annotations

import sqlite3
from typing import Iterable


ContentKey = tuple[str, str, str]


def current_rows(
    rows: Iterable[sqlite3.Row], stale_keys: set[ContentKey],
) -> tuple[list[sqlite3.Row], dict[str, list[str]], int]:
    """Keep one exact fact, retain its source IDs, and hide corrected copies."""
    selected: list[sqlite3.Row] = []
    first_by_key: dict[ContentKey, str] = {}
    supporting: dict[str, list[str]] = {}
    suppressed = 0
    for row in rows:
        key = (row["scope"], row["layer"], row["content_hash"])
        if key in stale_keys:
            suppressed += 1
            continue
        canonical_id = first_by_key.get(key)
        if canonical_id is None:
            first_by_key[key] = row["memory_id"]
            selected.append(row)
            supporting[row["memory_id"]] = []
        else:
            supporting[canonical_id].append(row["memory_id"])
    return selected, supporting, suppressed
