from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .agents import (
    AgentContext,
    BaseAgent,
    RecordKeeperAgent,
    SentimentAgent,
    TechnicalDevelopmentAgent,
    TraderBehaviorAgent,
    TrendAgent,
)
from .config import AppConfig
from .data import MarketDataProvider, SQLiteMarketStore, build_market_data_provider
from .domain import AgentSignal, MarketTick, Order, TradeDecision
from .execution import BrokerAdapter, LiveBrokerRouter, PaperBroker
from .optimizer import ContinuousStrategyOptimizer
from .risk import RiskManager
from .strategy import AgentCommittee


@dataclass
class SystemState:
    latest_ticks: dict[str, dict[str, Any]] = field(default_factory=dict)
    latest_behavior: dict[str, dict[str, Any]] = field(default_factory=dict)
    latest_signals: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    agent_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    agent_journal: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    orders: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    active_symbol: str = ""


class MultiAgentTradingSystem:
    def __init__(
        self,
        config: AppConfig,
        provider: MarketDataProvider | None = None,
        broker: BrokerAdapter | None = None,
        store: SQLiteMarketStore | None = None,
        agents: list[BaseAgent] | None = None,
    ) -> None:
        self.config = config
        self.provider = provider or build_market_data_provider(config)
        self.broker = broker or self._build_broker(config)
        self.store = store or SQLiteMarketStore(config.state_db_path)
        self.agents = agents or [
            TrendAgent(),
            TraderBehaviorAgent(),
            SentimentAgent(),
            RecordKeeperAgent(),
            TechnicalDevelopmentAgent(),
        ]
        self.committee = AgentCommittee()
        self.risk = RiskManager(config.risk)
        self.optimizer = ContinuousStrategyOptimizer(config.strategy_defaults())
        self.state = SystemState()
        self.running = False

    def _build_broker(self, config: AppConfig) -> BrokerAdapter:
        if config.execution_mode == "live":
            return LiveBrokerRouter(config.live_trading_confirm)
        return PaperBroker(config.risk.account_equity)

    async def handle_tick(self, tick: MarketTick) -> dict[str, Any]:
        self.store.save_tick(tick)
        self.state.latest_ticks[tick.symbol] = tick.to_dict()
        if hasattr(self.broker, "mark_to_market"):
            self.broker.mark_to_market(tick.symbol, tick.last)  # type: ignore[attr-defined]

        if self.state.active_symbol and tick.symbol != self.state.active_symbol:
            event = {
                "type": "tick_recorded_inactive_symbol",
                "symbol": tick.symbol,
                "active_symbol": self.state.active_symbol,
                "tick": tick.to_dict(),
            }
            self._push_event(event)
            return event

        strategy = self.optimizer.get(tick.symbol)
        context = AgentContext(strategy=strategy, account_equity=self.broker.account_state().equity)
        signals: list[AgentSignal] = []
        for agent in self.agents:
            signal = await agent.analyze(tick, context)
            signals.append(signal)
            self.store.save_signal(signal, tick.timestamp.isoformat())
            self._update_agent_status(signal, tick)
            if isinstance(agent, TraderBehaviorAgent) and tick.symbol in agent.last_snapshot:
                snapshot = agent.last_snapshot[tick.symbol]
                self.state.latest_behavior[tick.symbol] = snapshot.to_dict()
                self.store.save_behavior(snapshot)

        self.state.latest_signals[tick.symbol] = [signal.to_dict() for signal in signals]
        decision = self.committee.build_decision(tick, signals, strategy)
        event: dict[str, Any] = {
            "type": "tick_processed",
            "symbol": tick.symbol,
            "tick": tick.to_dict(),
            "signals": [signal.to_dict() for signal in signals],
        }

        if decision is None:
            event["decision"] = None
            event["order"] = None
            self._push_event(event)
            return event

        risk_result = self.risk.evaluate(decision, self.broker.account_state())
        event["risk"] = {"approved": risk_result.approved, "reason": risk_result.reason}
        if not risk_result.approved or risk_result.decision is None:
            event["decision"] = decision.to_dict()
            event["order"] = None
            self.store.save_decision(decision)
            self._push_event(event)
            return event

        approved_decision = risk_result.decision
        order = await self.broker.execute(approved_decision)
        self._save_decision_and_order(approved_decision, order)
        event["decision"] = approved_decision.to_dict()
        event["order"] = order.to_dict()
        self._push_event(event)
        return event

    async def run(self, max_ticks: int | None = None) -> None:
        self.running = True
        count = 0
        async for tick in self.provider.stream_ticks(self.config.symbols):
            await self.handle_tick(tick)
            count += 1
            if max_ticks is not None and count >= max_ticks:
                break
        self.running = False

    async def run_background(self) -> None:
        try:
            await self.run(max_ticks=None)
        except asyncio.CancelledError:
            self.running = False
            raise

    def _save_decision_and_order(self, decision: TradeDecision, order: Order) -> None:
        decision_data = decision.to_dict()
        order_data = order.to_dict()
        self.store.save_decision(decision)
        self.store.save_order(order)
        self.state.decisions.insert(0, decision_data)
        self.state.orders.insert(0, order_data)
        self.state.decisions = self.state.decisions[:100]
        self.state.orders = self.state.orders[:100]

    def _push_event(self, event: dict[str, Any]) -> None:
        self.state.events.insert(0, event)
        self.state.events = self.state.events[:200]

    def set_active_symbol(self, symbol: str) -> str:
        valid_symbols = {item.symbol for item in self.config.symbols}
        if symbol and symbol not in valid_symbols:
            raise ValueError(f"Unknown symbol: {symbol}")
        self.state.active_symbol = symbol
        return self.state.active_symbol

    def _update_agent_status(self, signal: AgentSignal, tick: MarketTick) -> None:
        features = signal.features
        status = {
            "agent": signal.agent,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "confidence": signal.confidence,
            "rationale": signal.rationale,
            "role": features.get("role", self._agent_role(signal.agent)),
            "status": features.get("status", self._agent_runtime_status(signal)),
            "current_task": features.get("current_task", self._agent_task(signal, tick)),
            "workload": features.get("workload", self._agent_workload(signal)),
            "updated_at": tick.timestamp.isoformat(),
        }
        self.state.agent_status[signal.agent] = status
        if signal.agent == "record_keeper_agent":
            self.state.agent_journal.insert(
                0,
                {
                    "timestamp": tick.timestamp.isoformat(),
                    "symbol": tick.symbol,
                    "message": status["current_task"],
                },
            )
            self.state.agent_journal = self.state.agent_journal[:80]

    def _agent_role(self, agent: str) -> str:
        roles = {
            "trend_agent": "Market structure and momentum analyst",
            "trader_behavior_agent": "Trader behavior analyst",
            "sentiment_agent": "News and sentiment monitor",
            "record_keeper_agent": "Data recorder",
            "technical_development_agent": "Trading system engineer",
        }
        return roles.get(agent, "AI agent")

    def _agent_runtime_status(self, signal: AgentSignal) -> str:
        if signal.direction.value == "hold":
            return "monitoring"
        return "active"

    def _agent_task(self, signal: AgentSignal, tick: MarketTick) -> str:
        if signal.agent == "trend_agent":
            return f"Checking momentum and volatility on {tick.symbol}"
        if signal.agent == "trader_behavior_agent":
            return f"Reading crowding, spread, and regime on {tick.symbol}"
        if signal.agent == "sentiment_agent":
            return f"Watching external sentiment channel for {tick.symbol}"
        return f"Processing {tick.symbol}"

    def _agent_workload(self, signal: AgentSignal) -> float:
        if signal.direction.value == "hold":
            return min(max(signal.confidence, 0.20), 0.65)
        return min(max(signal.confidence, 0.35), 1.0)

    def snapshot(self) -> dict[str, Any]:
        account = self.broker.account_state()
        market_account = self.provider.account_snapshot()
        return {
            "running": self.running,
            "symbols": [item.symbol for item in self.config.symbols],
            "active_symbol": self.state.active_symbol,
            "market_account": market_account,
            "account": {
                "equity": account.equity,
                "balance": account.balance,
                "daily_realized_pnl": account.daily_realized_pnl,
                "exposure": account.exposure(),
                "positions": {
                    symbol: {
                        "direction": position.direction.value,
                        "quantity": position.quantity,
                        "entry_price": position.entry_price,
                        "stop_loss": position.stop_loss,
                        "take_profit": position.take_profit,
                    }
                    for symbol, position in account.positions.items()
                },
            },
            "latest_ticks": self.state.latest_ticks,
            "latest_behavior": self.state.latest_behavior,
            "latest_signals": self.state.latest_signals,
            "agent_status": list(self.state.agent_status.values()),
            "agent_journal": self.state.agent_journal[:20],
            "decisions": self.state.decisions[:20],
            "orders": self.state.orders[:20],
            "optimization": self.optimizer.all_snapshots(),
        }
