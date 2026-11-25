"""Versioned data contracts and invariants for Nara Mission Control."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar, Mapping, TypeVar


SCHEMA_VERSION = 1


class ContractError(ValueError):
    """A persisted Mission Control contract is invalid or unsupported."""


class MissionStatus(StrEnum):
    DRAFT = "draft"
    PLANNED = "planned"
    RUNNING = "running"
    WAITING = "waiting"
    VERIFYING = "verifying"
    NEEDS_INPUT = "needs_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EffectStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class VerificationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class LeaseStatus(StrEnum):
    CLAIMED = "claimed"
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


TERMINAL_MISSION_STATUSES = frozenset({
    MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED,
})

MISSION_TRANSITIONS: dict[MissionStatus, frozenset[MissionStatus]] = {
    MissionStatus.DRAFT: frozenset({MissionStatus.PLANNED, MissionStatus.CANCELLED}),
    MissionStatus.PLANNED: frozenset({MissionStatus.RUNNING, MissionStatus.NEEDS_INPUT, MissionStatus.CANCELLED}),
    MissionStatus.RUNNING: frozenset({
        MissionStatus.WAITING, MissionStatus.VERIFYING, MissionStatus.NEEDS_INPUT,
        MissionStatus.FAILED, MissionStatus.CANCELLED,
    }),
    MissionStatus.WAITING: frozenset({
        MissionStatus.RUNNING, MissionStatus.NEEDS_INPUT, MissionStatus.FAILED, MissionStatus.CANCELLED,
    }),
    MissionStatus.NEEDS_INPUT: frozenset({MissionStatus.PLANNED, MissionStatus.RUNNING, MissionStatus.CANCELLED}),
    MissionStatus.VERIFYING: frozenset({MissionStatus.RUNNING, MissionStatus.COMPLETED, MissionStatus.FAILED}),
    MissionStatus.COMPLETED: frozenset(),
    MissionStatus.FAILED: frozenset(),
    MissionStatus.CANCELLED: frozenset(),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContractError(f"{field_name} must be non-empty")
    return text


def _string_list(value: Any, field_name: str, *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ContractError(f"{field_name} must be a list")
    items = [_required_text(item, field_name) for item in value]
    if non_empty and not items:
        raise ContractError(f"{field_name} must be non-empty")
    return items


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractError(f"{field_name} must be an object")
    return dict(value)


def _schema_version(value: Any) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractError("schema_version must be an integer") from exc
    if version != SCHEMA_VERSION:
        raise ContractError(f"unsupported schema_version {version}; expected {SCHEMA_VERSION}")
    return version


def _enum(enum_type, value: Any, field_name: str):
    try:
        return enum_type(value)
    except ValueError as exc:
        choices = ", ".join(item.value for item in enum_type)
        raise ContractError(f"{field_name} must be one of: {choices}") from exc


@dataclass(frozen=True)
class VersionedContract:
    schema_version: int = SCHEMA_VERSION
    kind: ClassVar[str]

    def __post_init__(self) -> None:
        _schema_version(self.schema_version)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind
        return payload


@dataclass(frozen=True)
class Mission(VersionedContract):
    kind: ClassVar[str] = "mission"
    mission_id: str = ""
    objective: str = ""
    completion_criteria: list[str] = field(default_factory=list)
    status: MissionStatus = MissionStatus.DRAFT
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    version: int = 1
    constraints: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    deadline: str | None = None
    session_id: str | None = None
    runtime_version: str | None = None
    task_requests: dict[str, Any] = field(default_factory=dict)
    task_states: dict[str, Any] = field(default_factory=dict)
    receipts: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    verifications: dict[str, Any] = field(default_factory=dict)
    goal_ref: dict[str, Any] = field(default_factory=dict)
    schedules: dict[str, Any] = field(default_factory=dict)
    leases: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    voice_events: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "mission_id", _required_text(self.mission_id, "mission_id"))
        object.__setattr__(self, "objective", _required_text(self.objective, "objective"))
        object.__setattr__(self, "completion_criteria",
                           _string_list(self.completion_criteria, "completion_criteria", non_empty=True))
        object.__setattr__(self, "status", _enum(MissionStatus, self.status, "status"))
        object.__setattr__(self, "constraints", _mapping(self.constraints, "constraints"))
        object.__setattr__(self, "budget", _mapping(self.budget, "budget"))
        object.__setattr__(self, "task_requests", _mapping(self.task_requests, "task_requests"))
        object.__setattr__(self, "task_states", _mapping(self.task_states, "task_states"))
        object.__setattr__(self, "receipts", _mapping(self.receipts, "receipts"))
        object.__setattr__(self, "artifacts", _mapping(self.artifacts, "artifacts"))
        object.__setattr__(self, "verifications", _mapping(self.verifications, "verifications"))
        object.__setattr__(self, "goal_ref", _mapping(self.goal_ref, "goal_ref"))
        object.__setattr__(self, "schedules", _mapping(self.schedules, "schedules"))
        object.__setattr__(self, "leases", _mapping(self.leases, "leases"))
        object.__setattr__(self, "diagnostics", _mapping(self.diagnostics, "diagnostics"))
        object.__setattr__(self, "voice_events", _mapping(self.voice_events, "voice_events"))
        if self.version < 1:
            raise ContractError("version must be at least 1")


@dataclass(frozen=True)
class MissionEvent(VersionedContract):
    kind: ClassVar[str] = "mission_event"
    event_id: str = ""
    mission_id: str = ""
    sequence: int = 0
    event_type: str = ""
    occurred_at: str = field(default_factory=utc_now)
    actor_id: str = "system"
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("event_id", "mission_id", "event_type", "occurred_at", "actor_id"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))
        object.__setattr__(self, "payload", _mapping(self.payload, "payload"))
        if self.sequence < 1:
            raise ContractError("sequence must be at least 1")
        if self.idempotency_key is not None:
            object.__setattr__(self, "idempotency_key",
                               _required_text(self.idempotency_key, "idempotency_key"))


@dataclass(frozen=True)
class Receipt(VersionedContract):
    kind: ClassVar[str] = "receipt"
    receipt_id: str = ""
    mission_id: str = ""
    task_id: str = ""
    intention: str = ""
    agent_id: str = ""
    tool: str = ""
    target: str = ""
    idempotency_key: str = ""
    attempted_at: str = field(default_factory=utc_now)
    effect_status: EffectStatus = EffectStatus.PENDING
    observed_result: dict[str, Any] = field(default_factory=dict)
    artifact_ids: list[str] = field(default_factory=list)
    error: str | None = None
    verification_method: str | None = None
    verification_status: VerificationStatus | None = None
    destination_operation_id: str | None = None
    attempt: int = 1
    adapter_version: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("receipt_id", "mission_id", "task_id", "intention", "agent_id", "tool",
                     "target", "idempotency_key", "attempted_at"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))
        object.__setattr__(self, "effect_status", _enum(EffectStatus, self.effect_status, "effect_status"))
        object.__setattr__(self, "observed_result", _mapping(self.observed_result, "observed_result"))
        object.__setattr__(self, "artifact_ids", _string_list(self.artifact_ids, "artifact_ids"))
        if self.verification_status is not None:
            object.__setattr__(self, "verification_status",
                               _enum(VerificationStatus, self.verification_status, "verification_status"))
        if self.attempt < 1:
            raise ContractError("attempt must be at least 1")


@dataclass(frozen=True)
class Artifact(VersionedContract):
    kind: ClassVar[str] = "artifact"
    artifact_id: str = ""
    sha256: str = ""
    media_type: str = "application/octet-stream"
    size_bytes: int = 0
    producer_id: str = ""
    mission_id: str = ""
    location: str = ""
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    retention: str = "mission"

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("artifact_id", "media_type", "producer_id", "mission_id", "location", "retention"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))
        digest = _required_text(self.sha256, "sha256").lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ContractError("sha256 must be a 64-character lowercase hexadecimal digest")
        object.__setattr__(self, "sha256", digest)
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))
        if self.size_bytes < 0:
            raise ContractError("size_bytes must be non-negative")
        if self.version < 1:
            raise ContractError("version must be at least 1")


@dataclass(frozen=True)
class Verification(VersionedContract):
    kind: ClassVar[str] = "verification"
    verification_id: str = ""
    mission_id: str = ""
    criterion: str = ""
    verifier_id: str = ""
    executor_id: str = ""
    status: VerificationStatus = VerificationStatus.INCONCLUSIVE
    evidence_artifact_ids: list[str] = field(default_factory=list)
    method: str = ""
    observed_at: str = field(default_factory=utc_now)
    explanation: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("verification_id", "mission_id", "criterion", "verifier_id", "executor_id",
                     "method", "observed_at"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))
        if self.verifier_id == self.executor_id:
            raise ContractError("verifier_id must differ from executor_id")
        object.__setattr__(self, "status", _enum(VerificationStatus, self.status, "status"))
        object.__setattr__(self, "evidence_artifact_ids",
                           _string_list(self.evidence_artifact_ids, "evidence_artifact_ids"))
        if self.status is VerificationStatus.PASS and not self.evidence_artifact_ids:
            raise ContractError("pass verification requires at least one evidence artifact")


@dataclass(frozen=True)
class WorkerLease(VersionedContract):
    kind: ClassVar[str] = "worker_lease"
    lease_id: str = ""
    mission_id: str = ""
    task_id: str = ""
    worker_id: str = ""
    status: LeaseStatus = LeaseStatus.CLAIMED
    claimed_at: str = field(default_factory=utc_now)
    heartbeat_at: str = field(default_factory=utc_now)
    expires_at: str = ""
    attempt: int = 1
    model: str | None = None
    provider: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("lease_id", "mission_id", "task_id", "worker_id", "claimed_at", "heartbeat_at", "expires_at"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))
        object.__setattr__(self, "status", _enum(LeaseStatus, self.status, "status"))
        if self.attempt < 1:
            raise ContractError("attempt must be at least 1")


ContractType = TypeVar("ContractType", bound=VersionedContract)
CONTRACT_TYPES: dict[str, type[VersionedContract]] = {
    contract.kind: contract for contract in (Mission, MissionEvent, Receipt, Artifact, Verification, WorkerLease)
}


def _migrate_v0(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    aliases = {
        "mission": {"id": "mission_id", "goal": "objective", "criteria": "completion_criteria"},
        "mission_event": {"id": "event_id", "type": "event_type", "data": "payload"},
        "receipt": {"id": "receipt_id", "intent": "intention", "status": "effect_status"},
        "artifact": {"id": "artifact_id", "hash": "sha256", "uri": "location", "type": "media_type"},
        "verification": {"id": "verification_id", "evidence": "evidence_artifact_ids"},
        "worker_lease": {"id": "lease_id"},
    }.get(kind, {})
    for old, new in aliases.items():
        if old in migrated and new not in migrated:
            migrated[new] = migrated.pop(old)
    migrated["schema_version"] = SCHEMA_VERSION
    migrated["kind"] = kind
    return migrated


def load_contract(payload: Mapping[str, Any]) -> VersionedContract:
    """Migrate a persisted mapping to the current schema and validate every invariant."""
    if not isinstance(payload, Mapping):
        raise ContractError("contract must be an object")
    kind = _required_text(payload.get("kind"), "kind")
    contract_type = CONTRACT_TYPES.get(kind)
    if contract_type is None:
        raise ContractError(f"unknown contract kind: {kind}")
    raw_version = payload.get("schema_version", 0)
    try:
        version = int(raw_version)
    except (TypeError, ValueError) as exc:
        raise ContractError("schema_version must be an integer") from exc
    data = _migrate_v0(kind, payload) if version == 0 else dict(payload)
    data.pop("kind", None)
    return contract_type(**data)


def assert_mission_transition(current: MissionStatus | str, target: MissionStatus | str) -> None:
    source = _enum(MissionStatus, current, "current status")
    destination = _enum(MissionStatus, target, "target status")
    if destination not in MISSION_TRANSITIONS[source]:
        raise ContractError(f"invalid mission transition: {source.value} -> {destination.value}")

