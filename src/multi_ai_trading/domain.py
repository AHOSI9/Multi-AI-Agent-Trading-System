from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


class AssetClass(str, Enum):
    CRYPTO = "crypto"
    FOREX = "forex"
    GOLD = "gold"


class Direction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FILLED = "filled"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class MarketSymbol:
    symbol: str
    asset_class: AssetClass


@dataclass(frozen=True)
class MarketTick:
    symbol: str
    asset_class: AssetClass
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume: float = 0.0
    source: str = "simulated"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def spread(self) -> float:
        return max(self.ask - self.bid, 0.0)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["asset_class"] = self.asset_class.value
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass(frozen=True)
class TraderBehaviorSnapshot:
    symbol: str
    timestamp: datetime
    volatility: float
    momentum: float
    spread_bps: float
    volume_delta: float
    crowding_score: float
    anomaly_score: float
    regime: Literal["calm", "trend", "panic", "range"]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass(frozen=True)
class AgentSignal:
    agent: str
    symbol: str
    direction: Direction
    confidence: float
    rationale: str
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["direction"] = self.direction.value
        return data


@dataclass(frozen=True)
class StrategyParameters:
    symbol: str
    confidence_threshold: float = 0.62
    risk_per_trade: float = 0.005
    stop_loss_pct: float = 0.006
    take_profit_pct: float = 0.012
    max_leverage: float = 1.0
    trend_window: int = 32
    behavior_window: int = 24

    def bounded(self) -> "StrategyParameters":
        return StrategyParameters(
            symbol=self.symbol,
            confidence_threshold=min(max(self.confidence_threshold, 0.50), 0.90),
            risk_per_trade=min(max(self.risk_per_trade, 0.001), 0.02),
            stop_loss_pct=min(max(self.stop_loss_pct, 0.001), 0.05),
            take_profit_pct=min(max(self.take_profit_pct, 0.002), 0.10),
            max_leverage=min(max(self.max_leverage, 1.0), 10.0),
            trend_window=max(int(self.trend_window), 5),
            behavior_window=max(int(self.behavior_window), 5),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TradeDecision:
    symbol: str
    asset_class: AssetClass
    direction: Direction
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy: StrategyParameters
    signals: list[AgentSignal]
    reason: str
    timestamp: datetime = field(default_factory=utc_now)
    quantity: float = 0.0

    def with_quantity(self, quantity: float) -> "TradeDecision":
        return TradeDecision(
            symbol=self.symbol,
            asset_class=self.asset_class,
            direction=self.direction,
            confidence=self.confidence,
            entry_price=self.entry_price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            strategy=self.strategy,
            signals=self.signals,
            reason=self.reason,
            timestamp=self.timestamp,
            quantity=quantity,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["asset_class"] = self.asset_class.value
        data["direction"] = self.direction.value
        data["timestamp"] = self.timestamp.isoformat()
        data["strategy"] = self.strategy.to_dict()
        data["signals"] = [signal.to_dict() for signal in self.signals]
        return data


@dataclass(frozen=True)
class Order:
    id: str
    symbol: str
    asset_class: AssetClass
    direction: Direction
    quantity: float
    price: float
    stop_loss: float
    take_profit: float
    status: OrderStatus
    reason: str
    timestamp: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["asset_class"] = self.asset_class.value
        data["direction"] = self.direction.value
        data["status"] = self.status.value
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class Position:
    symbol: str
    asset_class: AssetClass
    direction: Direction
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    opened_at: datetime = field(default_factory=utc_now)

    @property
    def notional(self) -> float:
        return abs(self.quantity * self.entry_price)

    def unrealized_pnl(self, mark_price: float) -> float:
        if self.direction == Direction.BUY:
            return (mark_price - self.entry_price) * self.quantity
        if self.direction == Direction.SELL:
            return (self.entry_price - mark_price) * self.quantity
        return 0.0


@dataclass
class AccountState:
    equity: float
    balance: float
    daily_realized_pnl: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)

    def exposure(self) -> float:
        return sum(position.notional for position in self.positions.values())

