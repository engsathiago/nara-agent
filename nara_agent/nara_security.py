"""Single authorization policy owned by Nara.

Phase 1 defaults to ``unrestricted``: application-level refusals and execution
approval gates authorize the operation and the selected LLM/provider remains
responsible for its own model-level policy.  Transport authentication and
state-integrity checks are deliberately outside this policy seam.

Phase 2 can add owner rules to ``security.yaml`` without scattering policy
decisions through the vendored agent core.
"""

from __future__ import annotations

import fnmatch
import io
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


VALID_MODES = ("unrestricted", "controlled", "nara")
_LOCK = threading.RLock()
_CACHE: tuple[str, int, dict[str, Any]] | None = None


@dataclass(frozen=True)
class SecurityDecision:
    """Nara's tri-state decision; ``None`` delegates to the vendored core."""

    allowed: Optional[bool]
    capability: str
    target: str
    mode: str
    reason: str
    rule_id: Optional[str] = None


def get_nara_home() -> Path:
    configured = os.environ.get("NARA_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".nara").resolve()


def get_policy_path() -> Path:
    override = os.environ.get("NARA_SECURITY_POLICY", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return get_nara_home() / "security.yaml"


def _default_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "mode": "unrestricted",
        "default": "allow",
        "rules": [],
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        from ruamel.yaml import YAML

        loaded = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:  # health: allow BLE001 -- malformed owner policy must delegate safely
        # A malformed future owner policy delegates to the upstream core.  It
        # must never silently become an unrestricted policy by parse failure.
        return {"mode": "nara", "_load_error": True}


def load_policy(*, refresh: bool = False) -> dict[str, Any]:
    """Load the one Nara policy, cached by resolved path and mtime."""

    global _CACHE
    env_mode = os.environ.get("NARA_SECURITY_MODE", "").strip().lower()
    # These modes do not consume owner-authored rules. Avoid touching a policy
    # path at all: it keeps delegated legacy/test execution hermetic and makes
    # the unrestricted phase independent from the presence of security.yaml.
    if env_mode in {"unrestricted", "nara"}:
        policy = _default_policy()
        policy["mode"] = env_mode
        return policy
    path = get_policy_path()
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        stamp = -1
    key = str(path)
    with _LOCK:
        if not refresh and _CACHE and _CACHE[0] == key and _CACHE[1] == stamp:
            return dict(_CACHE[2])
        policy = _default_policy()
        policy.update(_load_yaml(path))
        mode = env_mode or str(policy.get("mode", "unrestricted")).strip().lower()
        if mode not in VALID_MODES:
            mode = "nara"
            policy["_load_error"] = True
        policy["mode"] = mode
        default = str(policy.get("default", "deny")).strip().lower()
        policy["default"] = default if default in {"allow", "deny", "nara"} else "deny"
        if not isinstance(policy.get("rules"), list):
            policy["rules"] = []
        _CACHE = (key, stamp, dict(policy))
        return policy


def _matches(pattern: Any, value: str) -> bool:
    patterns = [pattern] if isinstance(pattern, str) else pattern if isinstance(pattern, list) else []
    return any(isinstance(item, str) and fnmatch.fnmatchcase(value, item) for item in patterns)


def _rule_matches(rule: Mapping[str, Any], capability: str, target: str,
                  context: Mapping[str, Any]) -> bool:
    if not _matches(rule.get("capability", "*"), capability):
        return False
    if not _matches(rule.get("target", "*"), target):
        return False
    expected = rule.get("context")
    if isinstance(expected, Mapping):
        return all(_matches(pattern, str(context.get(str(key), "")))
                   for key, pattern in expected.items())
    return True


def authorize(capability: str, target: Any = "", **context: Any) -> SecurityDecision:
    """Return Nara's authoritative allow/deny/delegate decision."""

    capability_text = str(capability or "unknown")
    target_text = str(target or "")
    policy = load_policy()
    mode = str(policy.get("mode", "nara"))

    # Uncensored tool authority is not remote-user authority.  An open bot
    # would turn the agent into a public shell, so sender authentication stays
    # with the gateway even in unrestricted mode.
    if capability_text == "gateway.receive":
        return SecurityDecision(None, capability_text, target_text, mode,
                                "Messaging identity remains owned by the gateway")
    if mode == "unrestricted":
        return SecurityDecision(True, capability_text, target_text, mode,
                                "Nara unrestricted owner policy")
    if mode == "nara":
        return SecurityDecision(None, capability_text, target_text, mode,
                                "Delegated to the vendored Nara policy")

    for index, candidate in enumerate(policy.get("rules", [])):
        if not isinstance(candidate, Mapping) or not _rule_matches(
                candidate, capability_text, target_text, context):
            continue
        effect = str(candidate.get("effect", "deny")).strip().lower()
        allowed: Optional[bool] = None if effect == "nara" else effect == "allow"
        rule_id = str(candidate.get("id") or f"rule-{index + 1}")
        return SecurityDecision(
            allowed, capability_text, target_text, mode,
            str(candidate.get("reason") or f"Nara rule {rule_id}: {effect}"),
            rule_id,
        )

    default = str(policy.get("default", "deny"))
    allowed = None if default == "nara" else default == "allow"
    return SecurityDecision(allowed, capability_text, target_text, mode,
                            f"Nara controlled policy default: {default}")


def set_mode(mode: str) -> Path:
    """Persist a mode while retaining future owner rules."""

    normalized = str(mode).strip().lower()
    if normalized not in VALID_MODES:
        raise ValueError(f"invalid mode {mode!r}; choose: {', '.join(VALID_MODES)}")
    path = get_policy_path()
    policy = load_policy(refresh=True)
    policy.pop("_load_error", None)
    policy["mode"] = normalized
    try:
        from ruamel.yaml import YAML

        stream = io.StringIO()
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.allow_unicode = True
        yaml.dump(policy, stream)
        rendered = stream.getvalue()
    except Exception as exc:
        raise RuntimeError("ruamel.yaml is required to update Nara policy") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(rendered, encoding="utf-8")
    os.replace(temp, path)
    with _LOCK:
        global _CACHE
        _CACHE = None
    return path
