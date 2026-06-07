from __future__ import annotations

from collections import defaultdict, deque
from statistics import pstdev

from ..domain import AgentSignal, Direction, MarketTick
from .base import AgentContext, BaseAgent


class TrendAgent(BaseAgent):
    name = "trend_agent"

    def __init__(self) -> None:
        self.prices: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=256))

    async def analyze(self, tick: MarketTick, context: AgentContext) -> AgentSignal:
        window = max(context.strategy.trend_window, 5)
        series = self.prices[tick.symbol]
        series.append(tick.last)
        if len(series) < window:
            return AgentSignal(
                agent=self.name,
                symbol=tick.symbol,
                direction=Direction.HOLD,
                confidence=0.50,
                rationale="waiting_for_trend_window",
                features={"window": window, "samples": len(series)},
            )

        recent = list(series)[-window:]
        returns = [(recent[i] - recent[i - 1]) / recent[i - 1] for i in range(1, len(recent))]
        momentum = (recent[-1] - recent[0]) / recent[0]
        volatility = pstdev(returns) if len(returns) > 1 else 0.0
        strength = abs(momentum) / max(volatility, 0.00001)

        if strength < 1.2:
            direction = Direction.HOLD
            rationale = "trend_strength_too_low"
        elif momentum > 0:
            direction = Direction.BUY
            rationale = "positive_momentum"
        else:
            direction = Direction.SELL
            rationale = "negative_momentum"

        confidence = min(0.50 + strength * 0.06, 0.88)
        if direction == Direction.HOLD:
            confidence = min(confidence, 0.58)

        return AgentSignal(
            agent=self.name,
            symbol=tick.symbol,
            direction=direction,
            confidence=round(confidence, 4),
            rationale=rationale,
            features={"momentum": momentum, "volatility": volatility, "strength": strength},
        )

