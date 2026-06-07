from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..domain import AgentSignal, MarketTick, StrategyParameters


@dataclass(frozen=True)
class AgentContext:
    strategy: StrategyParameters
    account_equity: float


class BaseAgent(ABC):
    name: str

    @abstractmethod
    async def analyze(self, tick: MarketTick, context: AgentContext) -> AgentSignal:
        raise NotImplementedError

