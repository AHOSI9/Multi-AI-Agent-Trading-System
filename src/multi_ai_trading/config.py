from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain import AssetClass, MarketSymbol, StrategyParameters


@dataclass(frozen=True)
class RiskConfig:
    account_equity: float = 10_000.0
    risk_per_trade: float = 0.005
    max_daily_loss_pct: float = 0.03
    max_symbol_exposure_pct: float = 0.20
    max_total_exposure_pct: float = 0.60
    min_confidence: float = 0.62


@dataclass(frozen=True)
class AppConfig:
    trading_env: str = "paper"
    feed_mode: str = "simulated"
    execution_mode: str = "paper"
    live_trading_confirm: bool = False
    state_db_path: Path = Path("runtime/trading_state.sqlite")
    symbols: list[MarketSymbol] = field(default_factory=list)
    risk: RiskConfig = field(default_factory=RiskConfig)
    ccxt_exchange: str = "binance"
    ccxt_api_key: str = ""
    ccxt_api_secret: str = ""
    mt5_path: str = ""
    mt5_portable: bool = False
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""

    def strategy_defaults(self) -> dict[str, StrategyParameters]:
        return {
            item.symbol: StrategyParameters(
                symbol=item.symbol,
                confidence_threshold=self.risk.min_confidence,
                risk_per_trade=self.risk.risk_per_trade,
            )
            for item in self.symbols
        }


def parse_symbols(raw: str | None) -> list[MarketSymbol]:
    if not raw:
        raw = "BTC/USDT:crypto,EURUSD:forex,XAUUSD:gold"
    symbols: list[MarketSymbol] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        if ":" in text:
            symbol, asset_class = text.rsplit(":", 1)
        else:
            symbol, asset_class = text, "crypto"
        symbols.append(MarketSymbol(symbol=symbol.strip(), asset_class=AssetClass(asset_class.strip().lower())))
    return symbols


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def load_config() -> AppConfig:
    risk = RiskConfig(
        account_equity=env_float("ACCOUNT_EQUITY", 10_000.0),
        risk_per_trade=env_float("RISK_PER_TRADE", 0.005),
        max_daily_loss_pct=env_float("MAX_DAILY_LOSS_PCT", 0.03),
        max_symbol_exposure_pct=env_float("MAX_SYMBOL_EXPOSURE_PCT", 0.20),
        max_total_exposure_pct=env_float("MAX_TOTAL_EXPOSURE_PCT", 0.60),
        min_confidence=env_float("MIN_CONFIDENCE", 0.62),
    )
    return AppConfig(
        trading_env=os.getenv("TRADING_ENV", "paper"),
        feed_mode=os.getenv("FEED_MODE", "simulated"),
        execution_mode=os.getenv("EXECUTION_MODE", "paper"),
        live_trading_confirm=env_bool("LIVE_TRADING_CONFIRM", False),
        state_db_path=Path(os.getenv("STATE_DB_PATH", "runtime/trading_state.sqlite")),
        symbols=parse_symbols(os.getenv("SYMBOLS")),
        risk=risk,
        ccxt_exchange=os.getenv("CCXT_EXCHANGE", "binance"),
        ccxt_api_key=os.getenv("CCXT_API_KEY", ""),
        ccxt_api_secret=os.getenv("CCXT_API_SECRET", ""),
        mt5_path=os.getenv("MT5_PATH", ""),
        mt5_portable=env_bool("MT5_PORTABLE", False),
        mt5_login=os.getenv("MT5_LOGIN", ""),
        mt5_password=os.getenv("MT5_PASSWORD", ""),
        mt5_server=os.getenv("MT5_SERVER", ""),
    )
