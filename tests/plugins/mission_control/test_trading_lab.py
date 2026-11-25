from __future__ import annotations

from plugins.mission_control.trading_lab import TradingLab


def _dataset(path):
    path.write_text(
        "timestamp,asset,close\n"
        "2026-01-01,BTC,100\n"
        "2026-01-02,BTC,101\n"
        "2026-01-03,BTC,99\n"
        "2026-01-04,BTC,105\n"
        "2026-01-05,BTC,110\n"
        "2026-01-06,BTC,108\n",
        encoding="utf-8",
    )
    return path


def test_backtest_is_reproducible_costed_and_compared_to_benchmark(tmp_path):
    engine = TradingLab(tmp_path / "trading.db")
    lab = engine.create_lab("Crypto", ["BTC"], benchmark="BTC", lab_id="crypto")
    source = _dataset(tmp_path / "prices.csv")

    first = engine.backtest(lab["lab_id"], source, fee_bps=10, slippage_bps=5)
    second = engine.backtest(lab["lab_id"], source, fee_bps=10, slippage_bps=5)

    assert first == second
    assert first["dataset_hash"]
    assert first["config_hash"]
    assert first["gross_equity_before_costs"] >= first["final_equity"]
    assert first["costs"] >= 0
    assert "benchmark_return" in first
    assert first["strategy"]["signal_uses_prior_rows_only"] is True


def test_paper_risk_guard_idempotency_pause_and_live_absence(tmp_path):
    engine = TradingLab(tmp_path / "trading.db")
    engine.create_lab(
        "Paper", ["BTC"], benchmark="BTC", mode="paper", lab_id="paper",
        limits={"max_order_notional": 500, "max_position_notional": 1000})

    first = engine.paper_order("paper", "BTC", "buy", 1, 100, idempotency_key="order-1")
    repeated = engine.paper_order("paper", "BTC", "buy", 1, 100, idempotency_key="order-1")
    assert first["order_id"] == repeated["order_id"]
    assert engine.status()["paper_order_count"] == 1
    assert engine.status()["live_available"] is False

    engine.set_controls("paper", paused=True)
    try:
        engine.paper_order("paper", "BTC", "buy", 1, 100, idempotency_key="order-2")
    except ValueError as exc:
        assert "unavailable" in str(exc)
    else:
        raise AssertionError("paused paper lab accepted an order")

    try:
        engine.set_mode("paper", "live")
    except ValueError as exc:
        assert "live" in str(exc)
    else:
        raise AssertionError("live mode must not be available")
