from __future__ import annotations

from ..domain import AgentSignal, Direction, MarketTick
from .base import AgentContext, BaseAgent


class SentimentAgent(BaseAgent):
    """Uses optional feed metadata, external sentiment connectors can replace this."""

    name = "sentiment_agent"

    async def analyze(self, tick: MarketTick, context: AgentContext) -> AgentSignal:
        score = float(tick.metadata.get("sentiment_score", 0.0))
        if score > 0.25:
            direction = Direction.BUY
            confidence = min(0.55 + score * 0.25, 0.80)
            rationale = "positive_external_sentiment"
        elif score < -0.25:
            direction = Direction.SELL
            confidence = min(0.55 + abs(score) * 0.25, 0.80)
            rationale = "negative_external_sentiment"
        else:
            direction = Direction.HOLD
            confidence = 0.50
            rationale = "neutral_or_missing_sentiment"

        return AgentSignal(
            agent=self.name,
            symbol=tick.symbol,
            direction=direction,
            confidence=round(confidence, 4),
            rationale=rationale,
            features={"sentiment_score": score},
        )

