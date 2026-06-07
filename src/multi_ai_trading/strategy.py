from __future__ import annotations

from dataclasses import dataclass

from .domain import AgentSignal, Direction, MarketTick, StrategyParameters, TradeDecision


@dataclass(frozen=True)
class CommitteeConfig:
    weights: dict[str, float]
    min_score_gap: float = 0.08


class AgentCommittee:
    def __init__(self, config: CommitteeConfig | None = None) -> None:
        self.config = config or CommitteeConfig(
            weights={
                "trend_agent": 0.50,
                "trader_behavior_agent": 0.30,
                "sentiment_agent": 0.20,
            }
        )

    def build_decision(
        self,
        tick: MarketTick,
        signals: list[AgentSignal],
        strategy: StrategyParameters,
    ) -> TradeDecision | None:
        buy_score = 0.0
        sell_score = 0.0
        reasons: list[str] = []

        for signal in signals:
            weight = self.config.weights.get(signal.agent, 0.10)
            if signal.direction == Direction.BUY:
                buy_score += signal.confidence * weight
            elif signal.direction == Direction.SELL:
                sell_score += signal.confidence * weight
            reasons.append(f"{signal.agent}:{signal.direction.value}:{signal.confidence:.2f}:{signal.rationale}")

        gap = abs(buy_score - sell_score)
        if gap < self.config.min_score_gap:
            return None

        if buy_score > sell_score:
            direction = Direction.BUY
            confidence = min(0.99, 0.50 + buy_score - sell_score)
            stop_loss = tick.last * (1 - strategy.stop_loss_pct)
            take_profit = tick.last * (1 + strategy.take_profit_pct)
        else:
            direction = Direction.SELL
            confidence = min(0.99, 0.50 + sell_score - buy_score)
            stop_loss = tick.last * (1 + strategy.stop_loss_pct)
            take_profit = tick.last * (1 - strategy.take_profit_pct)

        if confidence < strategy.confidence_threshold:
            return None

        return TradeDecision(
            symbol=tick.symbol,
            asset_class=tick.asset_class,
            direction=direction,
            confidence=round(confidence, 4),
            entry_price=tick.last,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
            signals=signals,
            reason="; ".join(reasons),
        )

