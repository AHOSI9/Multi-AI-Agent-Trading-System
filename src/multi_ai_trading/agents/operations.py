from __future__ import annotations

from collections import defaultdict

from ..domain import AgentSignal, Direction, MarketTick
from .base import AgentContext, BaseAgent


class RecordKeeperAgent(BaseAgent):
    name = "record_keeper_agent"

    def __init__(self) -> None:
        self.tick_counts: dict[str, int] = defaultdict(int)

    async def analyze(self, tick: MarketTick, context: AgentContext) -> AgentSignal:
        self.tick_counts[tick.symbol] += 1
        count = self.tick_counts[tick.symbol]
        return AgentSignal(
            agent=self.name,
            symbol=tick.symbol,
            direction=Direction.HOLD,
            confidence=0.99,
            rationale="recording_market_tick_signal_and_decision_context",
            features={
                "role": "Data recorder",
                "status": "recording",
                "current_task": f"Logging {tick.symbol} tick #{count}",
                "workload": min(count / 120, 1.0),
                "records_for_symbol": count,
            },
        )


class TechnicalDevelopmentAgent(BaseAgent):
    name = "technical_development_agent"

    def __init__(self) -> None:
        self.cycles = 0

    async def analyze(self, tick: MarketTick, context: AgentContext) -> AgentSignal:
        self.cycles += 1
        risk = context.strategy.risk_per_trade
        threshold = context.strategy.confidence_threshold
        return AgentSignal(
            agent=self.name,
            symbol=tick.symbol,
            direction=Direction.HOLD,
            confidence=0.72,
            rationale="monitoring_strategy_health_and_optimization_backlog",
            features={
                "role": "Trading system engineer",
                "status": "developing",
                "current_task": "Reviewing risk, confidence threshold, and strategy windows",
                "workload": min(0.35 + self.cycles / 180, 1.0),
                "risk_per_trade": risk,
                "confidence_threshold": threshold,
                "trend_window": context.strategy.trend_window,
                "behavior_window": context.strategy.behavior_window,
            },
        )
