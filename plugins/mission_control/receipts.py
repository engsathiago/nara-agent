"""External-effect receipts persisted through the Mission Control event log."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from plugins.mission_control.contracts import EffectStatus, Receipt, VerificationStatus, load_contract
from plugins.mission_control.store import MissionNotFoundError, MissionStore, MissionStoreError


_SETTLEMENTS = {
    EffectStatus.PENDING: {EffectStatus.CONFIRMED, EffectStatus.FAILED, EffectStatus.UNKNOWN},
    EffectStatus.UNKNOWN: {EffectStatus.CONFIRMED, EffectStatus.FAILED, EffectStatus.UNKNOWN},
    EffectStatus.CONFIRMED: set(),
    EffectStatus.FAILED: set(),
}


def _intent_signature(receipt: Receipt) -> tuple[Any, ...]:
    """Return the stable identity of an effect intent.

    ``attempted_at`` is deliberately excluded: a caller reconstructing the same
    request after a crash will naturally obtain a new local timestamp.  The
    durable copy remains authoritative once the idempotency key is bound.
    """
    return (
        receipt.receipt_id,
        receipt.mission_id,
        receipt.task_id,
        receipt.intention,
        receipt.agent_id,
        receipt.tool,
        receipt.target,
        receipt.idempotency_key,
        receipt.attempt,
        receipt.adapter_version,
    )


class ReceiptStore:
    def __init__(self, missions: MissionStore):
        self.missions = missions

    @classmethod
    def open_default(cls) -> ReceiptStore:
        return cls(MissionStore.open_default())

    def prepare(self, receipt: Receipt) -> Receipt:
        if receipt.effect_status is not EffectStatus.PENDING:
            raise MissionStoreError("a receipt must be pending when its intent is prepared")
        mission = self.missions.get(receipt.mission_id)
        if mission is None:
            raise MissionNotFoundError(receipt.mission_id)
        for payload in mission.receipts.values():
            existing = load_contract(payload)
            if isinstance(existing, Receipt) and existing.idempotency_key == receipt.idempotency_key:
                if _intent_signature(existing) != _intent_signature(receipt):
                    raise MissionStoreError("receipt idempotency key is already bound to another intent")
                return existing
        self.missions.prepare_receipt(receipt)
        return receipt

    def get(self, mission_id: str, receipt_id: str) -> Receipt | None:
        mission = self.missions.get(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        payload = mission.receipts.get(receipt_id)
        contract = load_contract(payload) if payload else None
        return contract if isinstance(contract, Receipt) else None

    def settle(
        self,
        mission_id: str,
        receipt_id: str,
        status: EffectStatus | str,
        *,
        observed_result: dict[str, Any] | None = None,
        artifact_ids: list[str] | None = None,
        error: str | None = None,
        verification_method: str | None = None,
        verification_status: VerificationStatus | str | None = None,
        destination_operation_id: str | None = None,
        idempotency_key: str,
    ) -> Receipt:
        current = self.get(mission_id, receipt_id)
        if current is None:
            raise MissionStoreError(f"unknown receipt: {receipt_id}")
        target = EffectStatus(status)
        requested_result = observed_result or {}
        requested_artifacts = artifact_ids or []
        requested_verification = VerificationStatus(verification_status) if verification_status else None
        if (
            current.effect_status is target
            and current.observed_result == requested_result
            and current.artifact_ids == requested_artifacts
            and current.error == error
            and current.verification_method == verification_method
            and current.verification_status == requested_verification
            and current.destination_operation_id == destination_operation_id
        ):
            return current
        if target not in _SETTLEMENTS[current.effect_status]:
            raise MissionStoreError(
                f"invalid receipt settlement: {current.effect_status.value} -> {target.value}")
        settled = replace(
            current,
            effect_status=target,
            observed_result=requested_result,
            artifact_ids=requested_artifacts,
            error=error,
            verification_method=verification_method,
            verification_status=requested_verification,
            destination_operation_id=destination_operation_id,
        )
        self.missions.settle_receipt(settled, idempotency_key=idempotency_key)
        return settled

