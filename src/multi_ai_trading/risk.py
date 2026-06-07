from __future__ import annotations

import math
from dataclasses import dataclass

from .config import RiskConfig
from .domain import AccountState, Direction, TradeDecision


@dataclass(frozen=True)
class RiskResult:
    approved: bool
    reason: str
    decision: TradeDecision | None = None


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def evaluate(self, decision: TradeDecision, account: AccountState) -> RiskResult:
        if decision.direction == Direction.HOLD:
            return RiskResult(False, "hold_decision")
        if decision.confidence < self.config.min_confidence:
            return RiskResult(False, "below_min_confidence")
        if account.daily_realized_pnl <= -account.equity * self.config.max_daily_loss_pct:
            return RiskResult(False, "daily_loss_limit_reached")

        stop_distance = abs(decision.entry_price - decision.stop_loss)
        if stop_distance <= 0:
            return RiskResult(False, "invalid_stop_distance")

        current_symbol = account.positions.get(decision.symbol)
        if current_symbol and current_symbol.direction == decision.direction:
            return RiskResult(False, "same_direction_position_exists")

        risk_amount = account.equity * decision.strategy.risk_per_trade
        quantity = risk_amount / stop_distance
        max_symbol_notional = account.equity * self.config.max_symbol_exposure_pct * decision.strategy.max_leverage
        max_total_notional = account.equity * self.config.max_total_exposure_pct * decision.strategy.max_leverage
        requested_notional = quantity * decision.entry_price

        current_symbol_notional = current_symbol.notional if current_symbol else 0.0
        total_after = account.exposure() - current_symbol_notional + min(requested_notional, max_symbol_notional)

        if total_after > max_total_notional:
            return RiskResult(False, "portfolio_exposure_limit")

        if requested_notional > max_symbol_notional:
            quantity = max_symbol_notional / decision.entry_price
        if quantity <= 0:
            return RiskResult(False, "quantity_too_small")

        safe_quantity = math.floor(quantity * 100_000_000) / 100_000_000
        if safe_quantity <= 0:
            return RiskResult(False, "quantity_too_small")
        return RiskResult(True, "approved", decision.with_quantity(safe_quantity))
