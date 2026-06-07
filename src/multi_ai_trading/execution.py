from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from .domain import AccountState, Direction, Order, OrderStatus, Position, TradeDecision


class BrokerAdapter(ABC):
    @abstractmethod
    async def execute(self, decision: TradeDecision) -> Order:
        raise NotImplementedError

    @abstractmethod
    def account_state(self) -> AccountState:
        raise NotImplementedError


class PaperBroker(BrokerAdapter):
    def __init__(self, starting_equity: float) -> None:
        self.account = AccountState(equity=starting_equity, balance=starting_equity)

    async def execute(self, decision: TradeDecision) -> Order:
        existing = self.account.positions.get(decision.symbol)
        if existing and existing.direction == decision.direction:
            return Order(
                id=str(uuid.uuid4()),
                symbol=decision.symbol,
                asset_class=decision.asset_class,
                direction=decision.direction,
                quantity=0.0,
                price=decision.entry_price,
                stop_loss=decision.stop_loss,
                take_profit=decision.take_profit,
                status=OrderStatus.REJECTED,
                reason="same_direction_position_exists",
            )

        if existing and existing.direction != decision.direction:
            pnl = existing.unrealized_pnl(decision.entry_price)
            self.account.balance += pnl
            self.account.equity = self.account.balance
            self.account.daily_realized_pnl += pnl

        self.account.positions[decision.symbol] = Position(
            symbol=decision.symbol,
            asset_class=decision.asset_class,
            direction=decision.direction,
            quantity=decision.quantity,
            entry_price=decision.entry_price,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
        )

        return Order(
            id=str(uuid.uuid4()),
            symbol=decision.symbol,
            asset_class=decision.asset_class,
            direction=decision.direction,
            quantity=decision.quantity,
            price=decision.entry_price,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
            status=OrderStatus.FILLED,
            reason="paper_fill",
            metadata={"confidence": decision.confidence},
        )

    def mark_to_market(self, symbol: str, price: float) -> None:
        position = self.account.positions.get(symbol)
        if not position:
            return
        self.account.equity = self.account.balance + position.unrealized_pnl(price)

    def account_state(self) -> AccountState:
        return self.account


class LiveBrokerRouter(BrokerAdapter):
    def __init__(self, live_trading_confirm: bool) -> None:
        self.live_trading_confirm = live_trading_confirm

    async def execute(self, decision: TradeDecision) -> Order:
        if not self.live_trading_confirm:
            return Order(
                id=str(uuid.uuid4()),
                symbol=decision.symbol,
                asset_class=decision.asset_class,
                direction=decision.direction,
                quantity=0.0,
                price=decision.entry_price,
                stop_loss=decision.stop_loss,
                take_profit=decision.take_profit,
                status=OrderStatus.REJECTED,
                reason="live_trading_not_confirmed",
            )
        return Order(
            id=str(uuid.uuid4()),
            symbol=decision.symbol,
            asset_class=decision.asset_class,
            direction=decision.direction,
            quantity=0.0,
            price=decision.entry_price,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
            status=OrderStatus.REJECTED,
            reason="live_broker_adapter_not_configured",
        )

    def account_state(self) -> AccountState:
        return AccountState(equity=0.0, balance=0.0)

