from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .domain import StrategyParameters


@dataclass(frozen=True)
class OptimizationSnapshot:
    symbol: str
    trades: int
    win_rate: float
    average_pnl: float
    params: StrategyParameters


class ContinuousStrategyOptimizer:
    def __init__(self, initial: dict[str, StrategyParameters], window: int = 50) -> None:
        self.params = {symbol: params.bounded() for symbol, params in initial.items()}
        self.results: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=window))

    def get(self, symbol: str) -> StrategyParameters:
        return self.params.setdefault(symbol, StrategyParameters(symbol=symbol))

    def observe_trade_result(self, symbol: str, pnl: float) -> OptimizationSnapshot:
        results = self.results[symbol]
        results.append(pnl)
        current = self.get(symbol)
        if len(results) < 5:
            return self.snapshot(symbol)

        wins = sum(1 for value in results if value > 0)
        win_rate = wins / len(results)
        avg = sum(results) / len(results)

        if win_rate < 0.42 or avg < 0:
            updated = StrategyParameters(
                symbol=symbol,
                confidence_threshold=current.confidence_threshold + 0.02,
                risk_per_trade=current.risk_per_trade * 0.85,
                stop_loss_pct=current.stop_loss_pct,
                take_profit_pct=current.take_profit_pct * 0.95,
                max_leverage=current.max_leverage,
                trend_window=current.trend_window + 2,
                behavior_window=current.behavior_window + 1,
            )
        elif win_rate > 0.58 and avg > 0:
            updated = StrategyParameters(
                symbol=symbol,
                confidence_threshold=current.confidence_threshold - 0.01,
                risk_per_trade=current.risk_per_trade * 1.05,
                stop_loss_pct=current.stop_loss_pct,
                take_profit_pct=current.take_profit_pct * 1.02,
                max_leverage=current.max_leverage,
                trend_window=max(current.trend_window - 1, 8),
                behavior_window=current.behavior_window,
            )
        else:
            updated = current
        self.params[symbol] = updated.bounded()
        return self.snapshot(symbol)

    def snapshot(self, symbol: str) -> OptimizationSnapshot:
        results = self.results[symbol]
        wins = sum(1 for value in results if value > 0)
        win_rate = wins / len(results) if results else 0.0
        avg = sum(results) / len(results) if results else 0.0
        return OptimizationSnapshot(
            symbol=symbol,
            trades=len(results),
            win_rate=round(win_rate, 4),
            average_pnl=round(avg, 6),
            params=self.get(symbol),
        )

    def all_snapshots(self) -> list[dict[str, object]]:
        return [
            {
                "symbol": symbol,
                "trades": snapshot.trades,
                "win_rate": snapshot.win_rate,
                "average_pnl": snapshot.average_pnl,
                "params": snapshot.params.to_dict(),
            }
            for symbol in sorted(self.params)
            for snapshot in [self.snapshot(symbol)]
        ]

