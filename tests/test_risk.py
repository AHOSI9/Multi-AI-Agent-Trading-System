import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_ai_trading.config import RiskConfig
from multi_ai_trading.domain import AccountState, AgentSignal, AssetClass, Direction, StrategyParameters, TradeDecision
from multi_ai_trading.risk import RiskManager


def make_decision(confidence: float = 0.80) -> TradeDecision:
    return TradeDecision(
        symbol="XAUUSD",
        asset_class=AssetClass.GOLD,
        direction=Direction.BUY,
        confidence=confidence,
        entry_price=2350.0,
        stop_loss=2335.0,
        take_profit=2380.0,
        strategy=StrategyParameters(symbol="XAUUSD", risk_per_trade=0.01),
        signals=[AgentSignal("trend_agent", "XAUUSD", Direction.BUY, confidence, "test")],
        reason="test",
    )


class RiskManagerTest(unittest.TestCase):
    def test_risk_manager_sizes_trade_from_stop_distance(self) -> None:
        risk = RiskManager(RiskConfig(account_equity=10_000, risk_per_trade=0.01, min_confidence=0.60))
        result = risk.evaluate(make_decision(), AccountState(equity=10_000, balance=10_000))

        self.assertTrue(result.approved)
        self.assertIsNotNone(result.decision)
        assert result.decision is not None
        self.assertGreater(result.decision.quantity, 0)
        self.assertLessEqual(result.decision.quantity, (10_000 * 0.20) / 2350.0)

    def test_risk_manager_rejects_low_confidence(self) -> None:
        risk = RiskManager(RiskConfig(account_equity=10_000, min_confidence=0.70))
        result = risk.evaluate(make_decision(confidence=0.65), AccountState(equity=10_000, balance=10_000))

        self.assertFalse(result.approved)
        self.assertEqual(result.reason, "below_min_confidence")


if __name__ == "__main__":
    unittest.main()
