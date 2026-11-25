"""Deterministic research, backtest, and paper-trading domain module."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import utc_now
from plugins.plugin_storage import plugin_data_dir


MODES = frozenset({"research", "backtest", "paper"})


def default_trading_path() -> Path:
    return plugin_data_dir("mission-control") / "trading-lab.db"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trading_labs (
            lab_id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL,
            universe_json TEXT NOT NULL, benchmark TEXT NOT NULL, currency TEXT NOT NULL,
            starting_cash REAL NOT NULL, limits_json TEXT NOT NULL,
            paused INTEGER NOT NULL, killed INTEGER NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trading_datasets (
            dataset_hash TEXT PRIMARY KEY, source_path TEXT NOT NULL,
            rows_json TEXT NOT NULL, row_count INTEGER NOT NULL,
            first_timestamp TEXT NOT NULL, last_timestamp TEXT NOT NULL,
            imported_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trading_backtests (
            run_id TEXT PRIMARY KEY, lab_id TEXT NOT NULL, dataset_hash TEXT NOT NULL,
            strategy_json TEXT NOT NULL, config_hash TEXT NOT NULL,
            result_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trading_paper_orders (
            order_id TEXT PRIMARY KEY, lab_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
            asset TEXT NOT NULL, side TEXT NOT NULL, quantity REAL NOT NULL,
            requested_price REAL NOT NULL, fill_price REAL NOT NULL,
            fees REAL NOT NULL, notional REAL NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL, UNIQUE (lab_id, idempotency_key)
        );
        CREATE TABLE IF NOT EXISTS trading_positions (
            lab_id TEXT NOT NULL, asset TEXT NOT NULL, quantity REAL NOT NULL,
            cash REAL NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (lab_id, asset)
        );
        CREATE TABLE IF NOT EXISTS trading_accounts (
            lab_id TEXT PRIMARY KEY, cash REAL NOT NULL, updated_at TEXT NOT NULL
        );
    """)
    conn.execute("PRAGMA user_version=1")
    conn.commit()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True)
class PriceRow:
    timestamp: str
    asset: str
    close: float


class TradingLab:
    """Owns isolated labs while leaving Mission Control as the agent authority."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    @classmethod
    def open_default(cls) -> TradingLab:
        return cls(default_trading_path())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.path, db_label="plugin-data/mission-control/trading-lab.db",
            synchronous_full=True, initialize=_initialize)

    def create_lab(
        self, name: str, universe: Iterable[str], *, benchmark: str,
        starting_cash: float = 10000.0, currency: str = "USD",
        mode: str = "research", limits: dict[str, float] | None = None,
        lab_id: str | None = None,
    ) -> dict[str, Any]:
        clean_universe = sorted({item.strip().upper() for item in universe if item.strip()})
        if not name.strip() or not clean_universe or benchmark.upper() not in clean_universe:
            raise ValueError("name, universe, and a benchmark inside the universe are required")
        if mode not in MODES or starting_cash <= 0:
            raise ValueError("invalid mode or starting cash")
        identity = lab_id or uuid.uuid4().hex
        now = utc_now()
        risk = {
            "max_order_notional": 1000.0,
            "max_position_notional": 3000.0,
            **(limits or {}),
        }
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT INTO trading_labs VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)",
                (identity, name.strip(), mode, json.dumps(clean_universe), benchmark.upper(),
                 currency.upper(), float(starting_cash), json.dumps(risk, sort_keys=True), now, now))
            conn.execute(
                "INSERT INTO trading_accounts VALUES (?, ?, ?)",
                (identity, float(starting_cash), now))
        return self.lab(identity)

    def lab(self, lab_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM trading_labs WHERE lab_id = ?", (lab_id,)).fetchone()
        if row is None:
            raise KeyError(lab_id)
        return {
            **dict(row), "universe": json.loads(row["universe_json"]),
            "limits": json.loads(row["limits_json"]), "paused": bool(row["paused"]),
            "killed": bool(row["killed"]),
        }

    def set_mode(self, lab_id: str, mode: str) -> dict[str, Any]:
        if mode not in MODES:
            raise ValueError("live mode is intentionally unavailable")
        with transaction(self._connect(), immediate=True) as conn:
            result = conn.execute(
                "UPDATE trading_labs SET mode = ?, updated_at = ? WHERE lab_id = ?",
                (mode, utc_now(), lab_id))
            if result.rowcount != 1:
                raise KeyError(lab_id)
        return self.lab(lab_id)

    def set_controls(
        self, lab_id: str, *, paused: bool | None = None, kill: bool | None = None,
    ) -> dict[str, Any]:
        current = self.lab(lab_id)
        paused_value = current["paused"] if paused is None else bool(paused)
        killed_value = current["killed"] if kill is None else bool(kill)
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "UPDATE trading_labs SET paused = ?, killed = ?, updated_at = ? WHERE lab_id = ?",
                (int(paused_value), int(killed_value), utc_now(), lab_id))
        return self.lab(lab_id)

    def import_csv(self, path: Path | str) -> dict[str, Any]:
        source = Path(path).expanduser().resolve()
        payload = source.read_bytes()
        dataset_hash = hashlib.sha256(payload).hexdigest()
        rows: list[PriceRow] = []
        with source.open(newline="", encoding="utf-8") as handle:
            for item in csv.DictReader(handle):
                row = PriceRow(
                    timestamp=str(item["timestamp"]).strip(),
                    asset=str(item["asset"]).strip().upper(),
                    close=float(item["close"]),
                )
                if not row.timestamp or not row.asset or row.close <= 0:
                    raise ValueError("dataset rows require timestamp, asset, and positive close")
                rows.append(row)
        if len(rows) < 2:
            raise ValueError("dataset requires at least two observations")
        ordered = sorted(rows, key=lambda item: (item.timestamp, item.asset))
        keys = [(item.timestamp, item.asset) for item in ordered]
        if keys != [(item.timestamp, item.asset) for item in rows] or len(keys) != len(set(keys)):
            raise ValueError("dataset must be sorted and contain no duplicate timestamp/asset")
        encoded = json.dumps([asdict(item) for item in rows], separators=(",", ":"))
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO trading_datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
                (dataset_hash, str(source), encoded, len(rows), rows[0].timestamp,
                 rows[-1].timestamp, utc_now()))
        return self.dataset(dataset_hash)

    def dataset(self, dataset_hash: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM trading_datasets WHERE dataset_hash = ?", (dataset_hash,)).fetchone()
        if row is None:
            raise KeyError(dataset_hash)
        return {**dict(row), "rows": json.loads(row["rows_json"])}

    def backtest(
        self, lab_id: str, dataset_path: Path | str, *, short_window: int = 2,
        long_window: int = 3, fee_bps: float = 10.0, slippage_bps: float = 5.0,
    ) -> dict[str, Any]:
        lab = self.lab(lab_id)
        if not 1 <= short_window < long_window or fee_bps < 0 or slippage_bps < 0:
            raise ValueError("windows and execution costs are invalid")
        dataset = self.import_csv(dataset_path)
        grouped: dict[str, list[PriceRow]] = {}
        for item in dataset["rows"]:
            row = PriceRow(**item)
            if row.asset in lab["universe"]:
                grouped.setdefault(row.asset, []).append(row)
        if set(grouped) != set(lab["universe"]) or any(
            len(rows) <= long_window for rows in grouped.values()
        ):
            raise ValueError("dataset does not cover the laboratory universe/window")
        strategy = {
            "name": "moving_average_cross", "short_window": short_window,
            "long_window": long_window, "signal_uses_prior_rows_only": True,
            "fee_bps": fee_bps, "slippage_bps": slippage_bps,
        }
        config_hash = _canonical_hash({
            "lab": {key: lab[key] for key in (
                "universe", "benchmark", "starting_cash", "currency")},
            "strategy": strategy,
        })
        run_id = hashlib.sha256(
            f"{lab_id}\0{dataset['dataset_hash']}\0{config_hash}".encode()).hexdigest()[:32]
        existing = self._backtest(run_id)
        if existing:
            return existing
        result = self._simulate(
            lab, grouped, short_window, long_window, fee_bps, slippage_bps)
        result.update({
            "run_id": run_id, "lab_id": lab_id, "dataset_hash": dataset["dataset_hash"],
            "config_hash": config_hash, "strategy": strategy,
            "dataset_first_timestamp": dataset["first_timestamp"],
            "dataset_last_timestamp": dataset["last_timestamp"],
            "limitations": [
                "historical performance does not predict future results",
                "close-only synthetic execution; no market impact model",
            ],
        })
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT INTO trading_backtests VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, lab_id, dataset["dataset_hash"], json.dumps(strategy, sort_keys=True),
                 config_hash, json.dumps(result, sort_keys=True), utc_now()))
        return result

    def _backtest(self, run_id: str) -> dict[str, Any] | None:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT result_json FROM trading_backtests WHERE run_id = ?", (run_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None

    @staticmethod
    def _simulate(lab, grouped, short_window, long_window, fee_bps, slippage_bps):
        sleeve = float(lab["starting_cash"]) / len(grouped)
        simulations = {
            asset: TradingLab._simulate_asset(
                rows, sleeve, short_window, long_window, fee_bps, slippage_bps)
            for asset, rows in grouped.items()
        }
        final_equity = sum(item["final_equity"] for item in simulations.values())
        costs = sum(item["costs"] for item in simulations.values())
        trade_count = sum(item["trade_count"] for item in simulations.values())
        curves = [item["equity_curve"] for item in simulations.values()]
        equity_curve = [sum(values) for values in zip(*curves, strict=False)]
        benchmark_rows = grouped[lab["benchmark"]]
        benchmark_return = benchmark_rows[-1].close / benchmark_rows[0].close - 1
        peak = equity_curve[0]
        max_drawdown = 0.0
        for equity in equity_curve:
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity / peak - 1)
        return {
            "assets": sorted(grouped), "allocation": "equal_weight_cash_sleeves",
            "per_asset": {asset: {
                key: value for key, value in result.items() if key != "equity_curve"
            } for asset, result in simulations.items()},
            "starting_cash": lab["starting_cash"], "final_equity": final_equity,
            "gross_equity_before_costs": final_equity + costs, "costs": costs,
            "net_return": final_equity / lab["starting_cash"] - 1,
            "benchmark_asset": lab["benchmark"], "benchmark_return": benchmark_return,
            "max_drawdown": max_drawdown, "trade_count": trade_count,
        }

    @staticmethod
    def _simulate_asset(rows, starting_cash, short_window, long_window, fee_bps, slippage_bps):
        cash = starting_cash
        units = 0.0
        costs = 0.0
        trade_count = 0
        equity_curve = [cash]
        for index, row in enumerate(rows):
            prior = [item.close for item in rows[:index]]
            desired = units > 0
            if len(prior) >= long_window:
                short_mean = sum(prior[-short_window:]) / short_window
                long_mean = sum(prior[-long_window:]) / long_window
                desired = short_mean > long_mean
            if desired and units == 0:
                execution = row.close * (1 + slippage_bps / 10000)
                fee_rate = fee_bps / 10000
                units = cash / (execution * (1 + fee_rate))
                fee = units * execution * fee_rate
                cash = 0.0
                costs += fee + units * (execution - row.close)
                trade_count += 1
            elif not desired and units > 0:
                execution = row.close * (1 - slippage_bps / 10000)
                fee = units * execution * fee_bps / 10000
                cash = units * execution - fee
                costs += fee + units * (row.close - execution)
                units = 0.0
                trade_count += 1
            equity_curve.append(cash + units * row.close)
        final_equity = cash + units * rows[-1].close
        gross_equity = final_equity + costs
        return {
            "starting_cash": starting_cash, "final_equity": final_equity,
            "gross_equity_before_costs": gross_equity, "costs": costs,
            "net_return": final_equity / starting_cash - 1, "trade_count": trade_count,
            "equity_curve": equity_curve,
        }

    def paper_order(
        self, lab_id: str, asset: str, side: str, quantity: float, price: float, *,
        idempotency_key: str, fee_bps: float = 10.0, slippage_bps: float = 5.0,
    ) -> dict[str, Any]:
        lab = self.lab(lab_id)
        asset = asset.upper()
        side = side.lower()
        if lab["mode"] != "paper" or lab["paused"] or lab["killed"]:
            raise ValueError("paper execution is unavailable while mode/control blocks it")
        if asset not in lab["universe"] or side not in {"buy", "sell"} or quantity <= 0 or price <= 0:
            raise ValueError("invalid paper order")
        with transaction(self._connect()) as conn:
            prior = conn.execute(
                "SELECT * FROM trading_paper_orders WHERE lab_id = ? AND idempotency_key = ?",
                (lab_id, idempotency_key)).fetchone()
        if prior:
            return dict(prior)
        direction = 1 if side == "buy" else -1
        fill = price * (1 + direction * slippage_bps / 10000)
        notional = quantity * fill
        fee = notional * fee_bps / 10000
        if notional > float(lab["limits"]["max_order_notional"]):
            raise ValueError("paper order exceeds max_order_notional")
        positions = {item["asset"]: item for item in self.positions(lab_id)}
        current = positions.get(asset, {"quantity": 0.0})
        with transaction(self._connect()) as conn:
            account = conn.execute(
                "SELECT cash FROM trading_accounts WHERE lab_id = ?", (lab_id,)).fetchone()
        if account is None:
            raise RuntimeError("paper account is missing")
        next_quantity = float(current["quantity"]) + direction * quantity
        next_cash = float(account["cash"]) - direction * notional - fee
        if next_quantity < 0 or next_cash < 0:
            raise ValueError("paper order would create negative holdings or cash")
        if next_quantity * price > float(lab["limits"]["max_position_notional"]):
            raise ValueError("paper order exceeds max_position_notional")
        identity = uuid.uuid4().hex
        now = utc_now()
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT INTO trading_paper_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'filled', ?)",
                (identity, lab_id, idempotency_key, asset, side, quantity, price, fill, fee,
                 notional, now))
            conn.execute(
                """INSERT INTO trading_positions VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(lab_id, asset) DO UPDATE SET quantity=excluded.quantity,
                   cash=excluded.cash, updated_at=excluded.updated_at""",
                (lab_id, asset, next_quantity, next_cash, now))
            conn.execute(
                "UPDATE trading_accounts SET cash = ?, updated_at = ? WHERE lab_id = ?",
                (next_cash, now, lab_id))
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM trading_paper_orders WHERE order_id = ?", (identity,)).fetchone()
        return dict(row)

    def positions(self, lab_id: str) -> list[dict[str, Any]]:
        lab = self.lab(lab_id)
        with transaction(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM trading_positions WHERE lab_id = ? ORDER BY asset", (lab_id,)).fetchall()
            account = conn.execute(
                "SELECT cash FROM trading_accounts WHERE lab_id = ?", (lab_id,)).fetchone()
        cash = float(account["cash"]) if account else lab["starting_cash"]
        if rows:
            return [{**dict(row), "cash": cash} for row in rows]
        return [{"lab_id": lab_id, "asset": lab["benchmark"], "quantity": 0.0,
                 "cash": cash, "updated_at": lab["created_at"]}]

    def status(self, lab_id: str | None = None) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            ids = [row["lab_id"] for row in conn.execute(
                "SELECT lab_id FROM trading_labs ORDER BY created_at").fetchall()]
            backtests = conn.execute("SELECT COUNT(*) AS count FROM trading_backtests").fetchone()["count"]
            orders = conn.execute("SELECT COUNT(*) AS count FROM trading_paper_orders").fetchone()["count"]
        selected = [self.lab(lab_id)] if lab_id else [self.lab(identity) for identity in ids]
        return {"labs": selected, "backtest_count": backtests, "paper_order_count": orders,
                "live_available": False}


TRADING_INIT_SCHEMA = {
    "name": "nara_trading_init", "description": "Create an isolated research/backtest/paper lab.",
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string"}, "universe": {"type": "array", "items": {"type": "string"}},
        "benchmark": {"type": "string"}, "starting_cash": {"type": "number"},
        "currency": {"type": "string"}, "mode": {"type": "string", "enum": sorted(MODES)},
    }, "required": ["name", "universe", "benchmark"]},
}
TRADING_BACKTEST_SCHEMA = {
    "name": "nara_trading_backtest", "description": "Run a reproducible no-lookahead backtest.",
    "parameters": {"type": "object", "properties": {
        "lab_id": {"type": "string"}, "dataset_path": {"type": "string"},
        "short_window": {"type": "integer"}, "long_window": {"type": "integer"},
        "fee_bps": {"type": "number"}, "slippage_bps": {"type": "number"},
    }, "required": ["lab_id", "dataset_path"]},
}
TRADING_STATUS_SCHEMA = {
    "name": "nara_trading_status", "description": "Inspect real Trading Lab state; live is disabled.",
    "parameters": {"type": "object", "properties": {"lab_id": {"type": "string"}}},
}


def trading_init_tool(**kwargs: Any) -> dict[str, Any]:
    return TradingLab.open_default().create_lab(**kwargs)


def trading_backtest_tool(**kwargs: Any) -> dict[str, Any]:
    return TradingLab.open_default().backtest(**kwargs)


def trading_status_tool(lab_id: str | None = None, **_: Any) -> dict[str, Any]:
    return TradingLab.open_default().status(lab_id)
