import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from multi_ai_trading.domain import StrategyParameters
from multi_ai_trading.optimizer import ContinuousStrategyOptimizer


class OptimizerTest(unittest.TestCase):
    def test_optimizer_reduces_risk_after_losses(self) -> None:
        optimizer = ContinuousStrategyOptimizer({"BTC/USDT": StrategyParameters(symbol="BTC/USDT")})
        for pnl in [-10, -4, -7, -2, -5]:
            snapshot = optimizer.observe_trade_result("BTC/USDT", pnl)

        self.assertGreater(snapshot.params.confidence_threshold, 0.62)
        self.assertLess(snapshot.params.risk_per_trade, 0.005)

    def test_optimizer_all_snapshots_contains_symbol(self) -> None:
        optimizer = ContinuousStrategyOptimizer({"XAUUSD": StrategyParameters(symbol="XAUUSD")})
        snapshots = optimizer.all_snapshots()

        self.assertEqual(snapshots[0]["symbol"], "XAUUSD")
        self.assertIn("params", snapshots[0])


if __name__ == "__main__":
    unittest.main()
