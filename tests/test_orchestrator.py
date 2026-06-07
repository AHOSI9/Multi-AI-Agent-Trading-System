import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_ai_trading.agents import AgentContext, BaseAgent
from multi_ai_trading.config import AppConfig, RiskConfig
from multi_ai_trading.data import SimulatedMarketDataProvider, SQLiteMarketStore
from multi_ai_trading.domain import AgentSignal, AssetClass, Direction, MarketSymbol, MarketTick
from multi_ai_trading.orchestrator import MultiAgentTradingSystem


class StaticBuyAgent(BaseAgent):
    name = "trend_agent"

    async def analyze(self, tick: MarketTick, context: AgentContext) -> AgentSignal:
        return AgentSignal(self.name, tick.symbol, Direction.BUY, 0.95, "unit_test_buy")


class OrchestratorTest(unittest.TestCase):
    def test_orchestrator_executes_approved_paper_order(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "state.sqlite"
            config = AppConfig(
                execution_mode="paper",
                state_db_path=db_path,
                symbols=[MarketSymbol("BTC/USDT", AssetClass.CRYPTO)],
                risk=RiskConfig(account_equity=10_000, min_confidence=0.60),
            )
            system = MultiAgentTradingSystem(
                config=config,
                provider=SimulatedMarketDataProvider(interval_seconds=0.0),
                store=SQLiteMarketStore(config.state_db_path),
                agents=[StaticBuyAgent()],
            )
            tick = MarketTick(
                symbol="BTC/USDT",
                asset_class=AssetClass.CRYPTO,
                timestamp=datetime.now(timezone.utc),
                bid=99.9,
                ask=100.1,
                last=100.0,
                volume=100,
            )

            import asyncio

            event = asyncio.run(system.handle_tick(tick))

            self.assertIsNotNone(event["order"])
            self.assertEqual(event["order"]["status"], "filled")
            self.assertEqual(system.snapshot()["account"]["positions"]["BTC/USDT"]["direction"], "buy")
            system.store.close()


if __name__ == "__main__":
    unittest.main()
