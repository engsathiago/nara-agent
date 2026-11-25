from __future__ import annotations

import pytest

from plugins.mission_control.contracts import EffectStatus, Mission, Receipt
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore, MissionStoreError


def _stores(tmp_path):
    missions = MissionStore(tmp_path / "missions.db")
    missions.create(Mission(
        mission_id="mission-1", objective="Write report", completion_criteria=["report exists"],
    ))
    return missions, ReceiptStore(missions)


def _receipt():
    return Receipt(
        receipt_id="receipt-1", mission_id="mission-1", task_id="task-1",
        intention="Write report once", agent_id="worker-1", tool="file.write",
        target="report.txt", idempotency_key="mission-1:report-v1",
    )


def test_intent_is_durable_before_effect_and_replay_is_idempotent(tmp_path):
    missions, receipts = _stores(tmp_path)
    first = _receipt()

    prepared = receipts.prepare(first)
    replayed = receipts.prepare(_receipt())

    assert prepared == first
    assert replayed == first
    assert len(missions.events("mission-1")) == 2
    assert receipts.get("mission-1", "receipt-1").effect_status is EffectStatus.PENDING


def test_settlement_replay_is_idempotent(tmp_path):
    missions, receipts = _stores(tmp_path)
    receipts.prepare(_receipt())

    first = receipts.settle(
        "mission-1", "receipt-1", "confirmed", observed_result={"sha256": "abc"},
        idempotency_key="confirmed",
    )
    replayed = receipts.settle(
        "mission-1", "receipt-1", "confirmed", observed_result={"sha256": "abc"},
        idempotency_key="confirmed",
    )

    assert replayed == first
    assert len(missions.events("mission-1")) == 3


def test_unknown_effect_can_be_reconciled_to_confirmed(tmp_path):
    _, receipts = _stores(tmp_path)
    receipts.prepare(_receipt())

    unknown = receipts.settle(
        "mission-1", "receipt-1", "unknown", observed_result={"reason": "confirmation lost"},
        idempotency_key="settle-unknown",
    )
    confirmed = receipts.settle(
        "mission-1", "receipt-1", "confirmed", observed_result={"sha256": "abc"},
        idempotency_key="reconcile-confirmed",
    )

    assert unknown.effect_status is EffectStatus.UNKNOWN
    assert confirmed.effect_status is EffectStatus.CONFIRMED


def test_confirmed_effect_is_terminal(tmp_path):
    _, receipts = _stores(tmp_path)
    receipts.prepare(_receipt())
    receipts.settle("mission-1", "receipt-1", "confirmed", idempotency_key="confirmed")

    with pytest.raises(MissionStoreError, match="confirmed -> failed"):
        receipts.settle("mission-1", "receipt-1", "failed", idempotency_key="late-failure")

