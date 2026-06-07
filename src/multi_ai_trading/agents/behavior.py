from __future__ import annotations

from collections import defaultdict, deque
from statistics import mean, pstdev

from ..domain import AgentSignal, Direction, MarketTick, TraderBehaviorSnapshot
from .base import AgentContext, BaseAgent


class TraderBehaviorAgent(BaseAgent):
    name = "trader_behavior_agent"

    def __init__(self) -> None:
        self.prices: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=256))
        self.volumes: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=256))
        self.last_snapshot: dict[str, TraderBehaviorSnapshot] = {}

    async def analyze(self, tick: MarketTick, context: AgentContext) -> AgentSignal:
        window = max(context.strategy.behavior_window, 5)
        prices = self.prices[tick.symbol]
        volumes = self.volumes[tick.symbol]
        prices.append(tick.last)
        volumes.append(tick.volume)

        if len(prices) < window:
            snapshot = TraderBehaviorSnapshot(
                symbol=tick.symbol,
                timestamp=tick.timestamp,
                volatility=0.0,
                momentum=0.0,
                spread_bps=(tick.spread / tick.mid) * 10_000 if tick.mid else 0.0,
                volume_delta=0.0,
                crowding_score=0.0,
                anomaly_score=0.0,
                regime="calm",
            )
            self.last_snapshot[tick.symbol] = snapshot
            return AgentSignal(
                agent=self.name,
                symbol=tick.symbol,
                direction=Direction.HOLD,
                confidence=0.50,
                rationale="waiting_for_behavior_window",
                features=snapshot.to_dict(),
            )

        recent_prices = list(prices)[-window:]
        recent_volumes = list(volumes)[-window:]
        returns = [(recent_prices[i] - recent_prices[i - 1]) / recent_prices[i - 1] for i in range(1, len(recent_prices))]
        volatility = pstdev(returns) if len(returns) > 1 else 0.0
        momentum = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        avg_volume = max(mean(recent_volumes[:-1]), 0.0001)
        volume_delta = (recent_volumes[-1] - avg_volume) / avg_volume
        spread_bps = (tick.spread / tick.mid) * 10_000 if tick.mid else 0.0
        crowding_score = min(max(abs(momentum) * 85 + max(volume_delta, 0) * 0.35, 0.0), 1.0)
        anomaly_score = min(max(volatility * 120 + max(spread_bps - 8, 0) / 40, 0.0), 1.0)

        if anomaly_score > 0.75:
            regime = "panic"
        elif crowding_score > 0.55 and abs(momentum) > 0.003:
            regime = "trend"
        elif volatility < 0.001:
            regime = "range"
        else:
            regime = "calm"

        snapshot = TraderBehaviorSnapshot(
            symbol=tick.symbol,
            timestamp=tick.timestamp,
            volatility=volatility,
            momentum=momentum,
            spread_bps=spread_bps,
            volume_delta=volume_delta,
            crowding_score=crowding_score,
            anomaly_score=anomaly_score,
            regime=regime,
        )
        self.last_snapshot[tick.symbol] = snapshot

        if regime == "panic":
            direction = Direction.HOLD
            confidence = 0.70
            rationale = "panic_or_spread_risk"
        elif regime == "trend" and momentum > 0:
            direction = Direction.BUY
            confidence = 0.56 + min(crowding_score * 0.24, 0.22)
            rationale = "crowd_following_uptrend"
        elif regime == "trend" and momentum < 0:
            direction = Direction.SELL
            confidence = 0.56 + min(crowding_score * 0.24, 0.22)
            rationale = "crowd_following_downtrend"
        else:
            direction = Direction.HOLD
            confidence = 0.53
            rationale = "no_behavioral_edge"

        return AgentSignal(
            agent=self.name,
            symbol=tick.symbol,
            direction=direction,
            confidence=round(confidence, 4),
            rationale=rationale,
            features=snapshot.to_dict(),
        )

