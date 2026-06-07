from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..domain import AgentSignal, MarketTick, Order, TradeDecision, TraderBehaviorSnapshot


class SQLiteMarketStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            create table if not exists ticks (
                id integer primary key autoincrement,
                timestamp text not null,
                symbol text not null,
                asset_class text not null,
                bid real not null,
                ask real not null,
                last real not null,
                volume real not null,
                source text not null,
                payload text not null
            );
            create index if not exists idx_ticks_symbol_time on ticks(symbol, timestamp);

            create table if not exists behavior (
                id integer primary key autoincrement,
                timestamp text not null,
                symbol text not null,
                payload text not null
            );

            create table if not exists signals (
                id integer primary key autoincrement,
                timestamp text not null,
                symbol text not null,
                agent text not null,
                direction text not null,
                confidence real not null,
                payload text not null
            );

            create table if not exists decisions (
                id integer primary key autoincrement,
                timestamp text not null,
                symbol text not null,
                direction text not null,
                confidence real not null,
                payload text not null
            );

            create table if not exists orders (
                id text primary key,
                timestamp text not null,
                symbol text not null,
                status text not null,
                payload text not null
            );
            """
        )
        self.connection.commit()

    def save_tick(self, tick: MarketTick) -> None:
        data = tick.to_dict()
        self.connection.execute(
            """
            insert into ticks(timestamp, symbol, asset_class, bid, ask, last, volume, source, payload)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["timestamp"],
                tick.symbol,
                tick.asset_class.value,
                tick.bid,
                tick.ask,
                tick.last,
                tick.volume,
                tick.source,
                json.dumps(data, ensure_ascii=False),
            ),
        )
        self.connection.commit()

    def save_behavior(self, snapshot: TraderBehaviorSnapshot) -> None:
        data = snapshot.to_dict()
        self.connection.execute(
            "insert into behavior(timestamp, symbol, payload) values (?, ?, ?)",
            (data["timestamp"], snapshot.symbol, json.dumps(data, ensure_ascii=False)),
        )
        self.connection.commit()

    def save_signal(self, signal: AgentSignal, timestamp: str) -> None:
        data = signal.to_dict()
        self.connection.execute(
            """
            insert into signals(timestamp, symbol, agent, direction, confidence, payload)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                signal.symbol,
                signal.agent,
                signal.direction.value,
                signal.confidence,
                json.dumps(data, ensure_ascii=False),
            ),
        )
        self.connection.commit()

    def save_decision(self, decision: TradeDecision) -> None:
        data = decision.to_dict()
        self.connection.execute(
            """
            insert into decisions(timestamp, symbol, direction, confidence, payload)
            values (?, ?, ?, ?, ?)
            """,
            (
                data["timestamp"],
                decision.symbol,
                decision.direction.value,
                decision.confidence,
                json.dumps(data, ensure_ascii=False),
            ),
        )
        self.connection.commit()

    def save_order(self, order: Order) -> None:
        data = order.to_dict()
        self.connection.execute(
            """
            insert or replace into orders(id, timestamp, symbol, status, payload)
            values (?, ?, ?, ?, ?)
            """,
            (
                order.id,
                data["timestamp"],
                order.symbol,
                order.status.value,
                json.dumps(data, ensure_ascii=False),
            ),
        )
        self.connection.commit()

    def latest(self, table: str, limit: int = 50) -> list[dict[str, Any]]:
        if table not in {"ticks", "behavior", "signals", "decisions", "orders"}:
            raise ValueError(f"Unsupported table: {table}")
        rows = self.connection.execute(
            f"select payload from {table} order by rowid desc limit ?",
            (limit,),
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def close(self) -> None:
        self.connection.close()

