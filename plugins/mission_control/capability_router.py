"""Deterministic capability inventory and least-fragile route selection."""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from plugins.mission_control.contracts import EffectStatus, Receipt
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore, MissionStoreError


@dataclass(frozen=True)
class Capability:
    capability_id: str
    module: str
    rank: int
    modalities: tuple[str, ...]
    cost: str
    latency: str
    cancellable: bool
    idempotency: str
    verification: str


@dataclass(frozen=True)
class RouteDecision:
    capability_id: str
    required_modalities: tuple[str, ...]
    reason: str
    alternatives: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_CAPABILITIES = (
    Capability("mcp", "tools.mcp_tool", 10, ("api", "structured"), "low", "low", True,
               "destination-dependent", "read-after-write or destination query"),
    Capability("file", "tools.file_operations", 20, ("file", "structured"), "low", "low", True,
               "hash-and-path", "reopen and hash"),
    Capability("terminal", "tools.terminal_tool", 30, ("terminal", "process"), "low", "medium", True,
               "adapter-dependent", "exit status plus target observation"),
    Capability("browser_dom", "tools.browser_tool", 40, ("browser", "dom"), "medium", "medium", True,
               "destination-dependent", "DOM query after action"),
    Capability("browser_accessibility", "tools.browser_use_cli", 50,
               ("browser", "accessibility"), "medium", "medium", True,
               "destination-dependent", "accessibility tree observation"),
    Capability("computer_vision", "tools.computer_use_tool", 60,
               ("desktop", "vision", "coordinates"), "high", "high", True,
               "weak", "independent screenshot or target query"),
)


class CapabilityRouter:
    def __init__(
        self,
        capabilities: Iterable[Capability] = DEFAULT_CAPABILITIES,
        *,
        find_spec: Callable[[str], object | None] = importlib.util.find_spec,
    ):
        self.capabilities = tuple(capabilities)
        self.find_spec = find_spec

    def inventory(self) -> list[dict]:
        rows = []
        for capability in sorted(self.capabilities, key=lambda item: item.rank):
            try:
                available = self.find_spec(capability.module) is not None
            except (ImportError, ModuleNotFoundError, ValueError):
                available = False
            rows.append({**asdict(capability), "available": available})
        return rows

    def select(self, required_modalities: Iterable[str]) -> RouteDecision:
        required = tuple(dict.fromkeys(str(item).strip() for item in required_modalities if str(item).strip()))
        if not required:
            raise MissionStoreError("at least one required modality is needed")
        candidates = [
            row for row in self.inventory()
            if row["available"] and set(required).issubset(row["modalities"])
        ]
        if not candidates:
            raise MissionStoreError(f"no available capability satisfies: {', '.join(required)}")
        chosen = candidates[0]
        return RouteDecision(
            capability_id=chosen["capability_id"],
            required_modalities=required,
            reason=(f"selected lowest-rank available route ({chosen['rank']}); "
                    f"verification: {chosen['verification']}"),
            alternatives=tuple(row["capability_id"] for row in candidates[1:]),
        )

    def select_for_mission(
        self,
        store: MissionStore,
        mission_id: str,
        task_id: str,
        required_modalities: Iterable[str],
        *,
        idempotency_key: str,
    ) -> RouteDecision:
        decision = self.select(required_modalities)
        receipts = ReceiptStore(store)
        receipt = receipts.prepare(Receipt(
            receipt_id=f"route:{idempotency_key}",
            mission_id=mission_id,
            task_id=task_id,
            intention="select least-fragile execution capability",
            agent_id="capability-router",
            tool="capability.select",
            target=",".join(decision.required_modalities),
            idempotency_key=idempotency_key,
        ))
        receipts.settle(
            mission_id,
            receipt.receipt_id,
            EffectStatus.CONFIRMED,
            observed_result=decision.to_dict(),
            idempotency_key=f"{idempotency_key}:settled",
        )
        return decision
