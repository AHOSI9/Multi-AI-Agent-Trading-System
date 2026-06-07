from __future__ import annotations

import asyncio
import math
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import AsyncIterator

from ..config import AppConfig
from ..domain import AssetClass, MarketSymbol, MarketTick


class MarketDataProvider(ABC):
    @abstractmethod
    async def stream_ticks(self, symbols: list[MarketSymbol]) -> AsyncIterator[MarketTick]:
        raise NotImplementedError

    def account_snapshot(self) -> dict[str, object] | None:
        return None


class SimulatedMarketDataProvider(MarketDataProvider):
    """Deterministic real-time-style feed for development and tests."""

    def __init__(self, interval_seconds: float = 0.25, seed: int = 42) -> None:
        self.interval_seconds = interval_seconds
        self.random = random.Random(seed)
        self.prices: dict[str, float] = {
            "BTC/USDT": 68_000.0,
            "ETH/USDT": 3_500.0,
            "EURUSD": 1.0850,
            "GBPUSD": 1.2700,
            "USDJPY": 156.0,
            "XAUUSD": 2_350.0,
        }
        self.step = 0

    async def stream_ticks(self, symbols: list[MarketSymbol]) -> AsyncIterator[MarketTick]:
        while True:
            self.step += 1
            for item in symbols:
                base = self.prices.setdefault(item.symbol, 100.0)
                drift = math.sin(self.step / 18) * 0.0018
                shock = self.random.gauss(0, 0.0012)
                if self.step % 80 == 0:
                    shock += self.random.choice([-1, 1]) * 0.012
                new_price = max(base * (1 + drift + shock), 0.0001)
                self.prices[item.symbol] = new_price
                spread_pct = 0.0004 if item.asset_class == AssetClass.CRYPTO else 0.00015
                if item.asset_class == AssetClass.GOLD:
                    spread_pct = 0.00025
                spread = new_price * spread_pct
                yield MarketTick(
                    symbol=item.symbol,
                    asset_class=item.asset_class,
                    timestamp=datetime.now(timezone.utc),
                    bid=new_price - spread / 2,
                    ask=new_price + spread / 2,
                    last=new_price,
                    volume=max(self.random.gauss(100, 25), 1.0),
                    source="simulated",
                    metadata={"step": self.step},
                )
            await asyncio.sleep(self.interval_seconds)


class CCXTMarketDataProvider(MarketDataProvider):
    def __init__(self, exchange_name: str = "binance") -> None:
        self.exchange_name = exchange_name

    async def stream_ticks(self, symbols: list[MarketSymbol]) -> AsyncIterator[MarketTick]:
        try:
            import ccxt.async_support as ccxt  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Install the crypto extra to use CCXT feeds: pip install .[crypto]") from exc

        exchange_class = getattr(ccxt, self.exchange_name)
        exchange = exchange_class()
        try:
            while True:
                for item in symbols:
                    if item.asset_class != AssetClass.CRYPTO:
                        continue
                    ticker = await exchange.fetch_ticker(item.symbol)
                    last = float(ticker.get("last") or ticker.get("close") or 0)
                    bid = float(ticker.get("bid") or last)
                    ask = float(ticker.get("ask") or last)
                    yield MarketTick(
                        symbol=item.symbol,
                        asset_class=item.asset_class,
                        timestamp=datetime.now(timezone.utc),
                        bid=bid,
                        ask=ask,
                        last=last,
                        volume=float(ticker.get("baseVolume") or 0.0),
                        source=f"ccxt:{self.exchange_name}",
                        metadata={"raw": ticker},
                    )
                await asyncio.sleep(1.0)
        finally:
            await exchange.close()


class MT5MarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        login: str = "",
        password: str = "",
        server: str = "",
        path: str = "",
        portable: bool = False,
    ) -> None:
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.portable = portable
        self._account_snapshot: dict[str, object] | None = None

    def account_snapshot(self) -> dict[str, object] | None:
        return self._account_snapshot

    def _refresh_account_snapshot(self, mt5: object) -> None:
        account = mt5.account_info()
        if account is None:
            return
        self._account_snapshot = {
            "login": getattr(account, "login", None),
            "name": getattr(account, "name", ""),
            "server": getattr(account, "server", ""),
            "company": getattr(account, "company", ""),
            "currency": getattr(account, "currency", ""),
            "balance": float(getattr(account, "balance", 0.0)),
            "equity": float(getattr(account, "equity", 0.0)),
            "profit": float(getattr(account, "profit", 0.0)),
            "margin": float(getattr(account, "margin", 0.0)),
            "margin_free": float(getattr(account, "margin_free", 0.0)),
            "trade_mode": getattr(account, "trade_mode", None),
        }

    async def stream_ticks(self, symbols: list[MarketSymbol]) -> AsyncIterator[MarketTick]:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Install the MT5 extra to use MT5 feeds: pip install .[mt5]") from exc

        init_kwargs = {"portable": self.portable}
        if self.path:
            init_kwargs["path"] = self.path
        if not mt5.initialize(**init_kwargs):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        if self.login and self.password and self.server:
            authorized = mt5.login(int(self.login), password=self.password, server=self.server)
            if not authorized:
                account = mt5.account_info()
                account_matches = (
                    account is not None
                    and int(getattr(account, "login", 0)) == int(self.login)
                    and str(getattr(account, "server", "")) == self.server
                )
                if not account_matches:
                    raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
        try:
            while True:
                self._refresh_account_snapshot(mt5)
                for item in symbols:
                    mt5.symbol_select(item.symbol, True)
                    tick = mt5.symbol_info_tick(item.symbol)
                    if tick is None:
                        continue
                    if tick.bid <= 0 or tick.ask <= 0:
                        continue
                    yield MarketTick(
                        symbol=item.symbol,
                        asset_class=item.asset_class,
                        timestamp=datetime.now(timezone.utc),
                        bid=float(tick.bid),
                        ask=float(tick.ask),
                        last=float(tick.last or (tick.bid + tick.ask) / 2),
                        volume=float(tick.volume_real or tick.volume or 0.0),
                        source="mt5",
                        metadata={"time_msc": getattr(tick, "time_msc", None)},
                    )
                await asyncio.sleep(0.5)
        finally:
            mt5.shutdown()


def build_market_data_provider(config: AppConfig) -> MarketDataProvider:
    if config.feed_mode == "ccxt":
        return CCXTMarketDataProvider(config.ccxt_exchange)
    if config.feed_mode == "mt5":
        return MT5MarketDataProvider(
            login=config.mt5_login,
            password=config.mt5_password,
            server=config.mt5_server,
            path=config.mt5_path,
            portable=config.mt5_portable,
        )
    return SimulatedMarketDataProvider()
