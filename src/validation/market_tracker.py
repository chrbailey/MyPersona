"""
Market tracker - fetches and tracks market data for validation.

The key to proving our system works: correlating discourse deltas with price movements.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Callable
import logging
import asyncio

import aiohttp

from ..models.market import MarketDataPoint, PriceMovement

logger = logging.getLogger(__name__)


@dataclass
class MarketDataConfig:
    """Configuration for market data."""
    provider: str = "polygon"
    api_key: str = ""
    poll_interval_seconds: int = 60


class MarketTracker:
    """
    Tracks market data for validation of predictions.

    Fetches price and volume data, calculates movements,
    and provides data for correlation analysis.
    """

    def __init__(self, config: MarketDataConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

        # Cache of recent data points
        self.data_cache: dict[str, list[MarketDataPoint]] = {}

        # Tracked tickers
        self.tracked_tickers: set[str] = set()

        # Callbacks
        self.on_significant_move: Optional[Callable[[str, PriceMovement], None]] = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def track_ticker(self, ticker: str) -> None:
        """Add a ticker to tracking."""
        self.tracked_tickers.add(ticker.upper())
        if ticker.upper() not in self.data_cache:
            self.data_cache[ticker.upper()] = []

    async def get_current_price(self, ticker: str) -> Optional[MarketDataPoint]:
        """Get current price for a ticker."""
        await self._ensure_session()

        if self.config.provider == "polygon":
            return await self._get_price_polygon(ticker)
        elif self.config.provider == "yahoo":
            return await self._get_price_yahoo(ticker)
        else:
            logger.error(f"Unknown provider: {self.config.provider}")
            return None

    async def _get_price_polygon(self, ticker: str) -> Optional[MarketDataPoint]:
        """Fetch price from Polygon.io."""
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev"
        params = {"apiKey": self.config.api_key}

        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Polygon API error: {response.status}")
                    return None

                data = await response.json()
                if data.get("status") != "OK" or not data.get("results"):
                    return None

                result = data["results"][0]
                return MarketDataPoint(
                    ticker=ticker,
                    timestamp=datetime.utcnow(),
                    price=result["c"],  # Close price
                    open_price=result["o"],
                    high=result["h"],
                    low=result["l"],
                    volume=result["v"],
                )

        except Exception as e:
            logger.error(f"Error fetching from Polygon: {e}")
            return None

    async def _get_price_yahoo(self, ticker: str) -> Optional[MarketDataPoint]:
        """Fetch price from Yahoo Finance (unofficial)."""
        # Simplified implementation - would use yfinance or similar in production
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {"interval": "1m", "range": "1d"}

        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                result = data.get("chart", {}).get("result", [{}])[0]
                meta = result.get("meta", {})

                return MarketDataPoint(
                    ticker=ticker,
                    timestamp=datetime.utcnow(),
                    price=meta.get("regularMarketPrice", 0),
                    open_price=meta.get("regularMarketOpen", 0),
                    high=meta.get("regularMarketDayHigh", 0),
                    low=meta.get("regularMarketDayLow", 0),
                    volume=meta.get("regularMarketVolume", 0),
                )

        except Exception as e:
            logger.error(f"Error fetching from Yahoo: {e}")
            return None

    async def get_price_at_time(
        self,
        ticker: str,
        timestamp: datetime,
    ) -> Optional[MarketDataPoint]:
        """Get price at a specific time (for backtesting)."""
        # Would query historical data API
        # For now, return from cache if available
        if ticker in self.data_cache:
            for point in reversed(self.data_cache[ticker]):
                if point.timestamp <= timestamp:
                    return point
        return None

    async def calculate_movement(
        self,
        ticker: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[PriceMovement]:
        """Calculate price movement over a time window."""
        start_price_point = await self.get_price_at_time(ticker, start_time)
        end_price_point = await self.get_price_at_time(ticker, end_time)

        if not start_price_point or not end_price_point:
            # Try to fetch current if end_time is recent
            if datetime.utcnow() - end_time < timedelta(minutes=5):
                end_price_point = await self.get_current_price(ticker)

        if not start_price_point or not end_price_point:
            return None

        return PriceMovement(
            ticker=ticker,
            start_time=start_time,
            end_time=end_time,
            start_price=start_price_point.price,
            end_price=end_price_point.price,
            start_volume=start_price_point.volume,
            end_volume=end_price_point.volume,
            high_price=max(start_price_point.high, end_price_point.high),
            low_price=min(start_price_point.low, end_price_point.low),
        )

    async def start_tracking(self) -> None:
        """Start continuous price tracking."""
        logger.info(f"Starting market tracking for {len(self.tracked_tickers)} tickers")

        while True:
            for ticker in self.tracked_tickers:
                try:
                    point = await self.get_current_price(ticker)
                    if point:
                        self._store_data_point(ticker, point)
                        await self._check_for_significant_move(ticker)
                except Exception as e:
                    logger.error(f"Error tracking {ticker}: {e}")

            await asyncio.sleep(self.config.poll_interval_seconds)

    def _store_data_point(self, ticker: str, point: MarketDataPoint) -> None:
        """Store a data point in cache."""
        if ticker not in self.data_cache:
            self.data_cache[ticker] = []

        self.data_cache[ticker].append(point)

        # Keep last 1000 points
        if len(self.data_cache[ticker]) > 1000:
            self.data_cache[ticker] = self.data_cache[ticker][-1000:]

    async def _check_for_significant_move(self, ticker: str) -> None:
        """Check if there's been a significant price move."""
        if ticker not in self.data_cache or len(self.data_cache[ticker]) < 2:
            return

        recent = self.data_cache[ticker][-1]
        hour_ago_idx = max(0, len(self.data_cache[ticker]) - 60)
        hour_ago = self.data_cache[ticker][hour_ago_idx]

        if hour_ago.price > 0:
            change_pct = (recent.price - hour_ago.price) / hour_ago.price * 100

            if abs(change_pct) > 2.0:  # 2% move in an hour
                movement = PriceMovement(
                    ticker=ticker,
                    start_time=hour_ago.timestamp,
                    end_time=recent.timestamp,
                    start_price=hour_ago.price,
                    end_price=recent.price,
                )

                if self.on_significant_move:
                    await self.on_significant_move(ticker, movement)

    def get_recent_data(
        self,
        ticker: str,
        hours: int = 24,
    ) -> list[MarketDataPoint]:
        """Get recent data points for a ticker."""
        if ticker not in self.data_cache:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            p for p in self.data_cache[ticker]
            if p.timestamp >= cutoff
        ]


class MockMarketTracker(MarketTracker):
    """Mock market tracker for testing."""

    def __init__(self, config: MarketDataConfig):
        super().__init__(config)
        self.mock_prices: dict[str, float] = {}

    def set_mock_price(self, ticker: str, price: float) -> None:
        """Set a mock price for testing."""
        self.mock_prices[ticker] = price

    async def get_current_price(self, ticker: str) -> Optional[MarketDataPoint]:
        """Return mock price."""
        if ticker in self.mock_prices:
            return MarketDataPoint(
                ticker=ticker,
                timestamp=datetime.utcnow(),
                price=self.mock_prices[ticker],
                volume=1000000,
            )
        return None
