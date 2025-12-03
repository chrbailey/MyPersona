"""
X/Twitter API client for data ingestion.

Handles authentication, streaming, and search endpoints.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import AsyncIterator, Optional, Callable, Any
import logging
import json

import aiohttp

from ..config.settings import XAPISettings
from ..models.discourse import Post, Account, PostType, AccountType

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """Simple rate limiter for API calls."""
    max_requests: int
    window_seconds: int
    requests: list[datetime] = None

    def __post_init__(self):
        self.requests = []

    async def acquire(self) -> None:
        """Wait until a request can be made."""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)

        # Remove old requests
        self.requests = [r for r in self.requests if r > window_start]

        if len(self.requests) >= self.max_requests:
            # Wait until oldest request expires
            wait_time = (self.requests[0] - window_start).total_seconds()
            logger.debug(f"Rate limited, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

        self.requests.append(now)


class XClient:
    """
    Client for X/Twitter API v2.

    Provides methods for:
    - Streaming filtered tweets
    - Searching recent tweets
    - Getting user information
    - Getting tweet details
    """

    BASE_URL = "https://api.twitter.com/2"

    def __init__(self, settings: XAPISettings):
        self.settings = settings
        self.rate_limiter = RateLimiter(
            max_requests=settings.max_requests_per_15min,
            window_seconds=900,  # 15 minutes
        )
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> XClient:
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session exists."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._get_headers()
            )

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {self.settings.bearer_token}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> dict:
        """Make an authenticated API request."""
        await self._ensure_session()
        await self.rate_limiter.acquire()

        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json_data,
            ) as response:
                if response.status == 429:
                    # Rate limited
                    reset_time = int(response.headers.get("x-rate-limit-reset", 60))
                    logger.warning(f"Rate limited, waiting {reset_time}s")
                    await asyncio.sleep(reset_time)
                    return await self._make_request(method, endpoint, params, json_data)

                response.raise_for_status()
                return await response.json()

        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            raise

    async def search_recent(
        self,
        query: str,
        max_results: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[Post]:
        """
        Search recent tweets (last 7 days).

        Args:
            query: Search query (supports X search operators)
            max_results: Maximum number of results (10-100)
            start_time: Start of time range (UTC)
            end_time: End of time range (UTC)

        Returns:
            List of Post objects
        """
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,author_id,public_metrics,entities,lang,conversation_id,in_reply_to_user_id",
            "user.fields": "id,name,username,verified,public_metrics,description",
            "expansions": "author_id,referenced_tweets.id,in_reply_to_user_id",
        }

        if start_time:
            params["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if end_time:
            params["end_time"] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        data = await self._make_request("GET", "/tweets/search/recent", params=params)
        return self._parse_tweets(data)

    async def stream_filtered(
        self,
        rules: list[dict[str, str]],
        on_tweet: Callable[[Post], Any],
        on_error: Optional[Callable[[Exception], Any]] = None,
    ) -> None:
        """
        Stream filtered tweets in real-time.

        Args:
            rules: List of filter rules [{"value": "tesla OR $TSLA", "tag": "tesla"}]
            on_tweet: Callback for each tweet
            on_error: Error callback
        """
        # First, set up the filter rules
        await self._setup_stream_rules(rules)

        # Then stream
        await self._ensure_session()

        url = f"{self.BASE_URL}/tweets/search/stream"
        params = {
            "tweet.fields": "created_at,author_id,public_metrics,entities,lang,conversation_id",
            "user.fields": "id,name,username,verified,public_metrics",
            "expansions": "author_id,referenced_tweets.id",
        }

        while True:
            try:
                async with self._session.get(url, params=params) as response:
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line)
                                if "data" in data:
                                    posts = self._parse_tweets(data)
                                    for post in posts:
                                        await on_tweet(post)
                            except json.JSONDecodeError:
                                continue

            except aiohttp.ClientError as e:
                logger.error(f"Stream error: {e}")
                if on_error:
                    await on_error(e)
                await asyncio.sleep(self.settings.stream_reconnect_delay_seconds)

    async def _setup_stream_rules(self, rules: list[dict[str, str]]) -> None:
        """Set up streaming filter rules."""
        # Get existing rules
        existing = await self._make_request("GET", "/tweets/search/stream/rules")
        existing_rules = existing.get("data", [])

        # Delete existing rules
        if existing_rules:
            ids = [r["id"] for r in existing_rules]
            await self._make_request(
                "POST",
                "/tweets/search/stream/rules",
                json_data={"delete": {"ids": ids}},
            )

        # Add new rules
        if rules:
            await self._make_request(
                "POST",
                "/tweets/search/stream/rules",
                json_data={"add": rules},
            )

    async def get_user(self, username: str) -> Optional[Account]:
        """Get user information by username."""
        params = {
            "user.fields": "id,name,username,verified,public_metrics,description,created_at",
        }

        try:
            data = await self._make_request(
                "GET",
                f"/users/by/username/{username}",
                params=params,
            )
            return self._parse_user(data.get("data", {}))
        except Exception as e:
            logger.error(f"Failed to get user {username}: {e}")
            return None

    async def get_user_tweets(
        self,
        user_id: str,
        max_results: int = 100,
        start_time: Optional[datetime] = None,
    ) -> list[Post]:
        """Get tweets from a specific user."""
        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,entities,lang,conversation_id",
            "exclude": "retweets,replies",
        }

        if start_time:
            params["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        data = await self._make_request(
            "GET",
            f"/users/{user_id}/tweets",
            params=params,
        )
        return self._parse_tweets(data)

    async def get_conversation(
        self,
        conversation_id: str,
        max_results: int = 100,
    ) -> list[Post]:
        """Get all tweets in a conversation thread."""
        query = f"conversation_id:{conversation_id}"
        return await self.search_recent(query, max_results=max_results)

    def _parse_tweets(self, data: dict) -> list[Post]:
        """Parse API response into Post objects."""
        tweets = data.get("data", [])
        if not isinstance(tweets, list):
            tweets = [tweets]

        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
        posts = []

        for tweet in tweets:
            author_data = users.get(tweet.get("author_id"), {})
            author = self._parse_user(author_data)

            # Determine post type
            post_type = PostType.ORIGINAL
            reply_to_id = None
            quote_of_id = None

            refs = tweet.get("referenced_tweets", [])
            for ref in refs:
                if ref["type"] == "replied_to":
                    post_type = PostType.REPLY
                    reply_to_id = ref["id"]
                elif ref["type"] == "quoted":
                    post_type = PostType.QUOTE
                    quote_of_id = ref["id"]
                elif ref["type"] == "retweeted":
                    post_type = PostType.REPOST

            metrics = tweet.get("public_metrics", {})

            posts.append(Post(
                post_id=tweet["id"],
                platform="x",
                text=tweet.get("text", ""),
                created_at=datetime.fromisoformat(
                    tweet.get("created_at", "").replace("Z", "+00:00")
                ),
                author=author,
                post_type=post_type,
                reply_to_id=reply_to_id,
                quote_of_id=quote_of_id,
                likes=metrics.get("like_count", 0),
                reposts=metrics.get("retweet_count", 0),
                replies=metrics.get("reply_count", 0),
                views=metrics.get("impression_count", 0),
                language=tweet.get("lang", "en"),
            ))

        return posts

    def _parse_user(self, data: dict) -> Account:
        """Parse user data into Account object."""
        if not data:
            return Account(
                platform_id="unknown",
                username="unknown",
                display_name="Unknown",
            )

        metrics = data.get("public_metrics", {})

        return Account(
            platform_id=data.get("id", ""),
            username=data.get("username", ""),
            display_name=data.get("name", ""),
            verified=data.get("verified", False),
            follower_count=metrics.get("followers_count", 0),
        )


class MockXClient(XClient):
    """
    Mock X client for testing and development.

    Generates synthetic data that mimics real patterns.
    """

    def __init__(self, settings: XAPISettings):
        super().__init__(settings)
        self._mock_data: list[Post] = []

    def add_mock_posts(self, posts: list[Post]) -> None:
        """Add mock posts for testing."""
        self._mock_data.extend(posts)

    async def search_recent(
        self,
        query: str,
        max_results: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[Post]:
        """Return mock data matching query."""
        # Filter mock data by query terms
        query_terms = query.lower().split()
        results = []

        for post in self._mock_data:
            if any(term in post.text.lower() for term in query_terms):
                if start_time and post.created_at < start_time:
                    continue
                if end_time and post.created_at > end_time:
                    continue
                results.append(post)

        return results[:max_results]

    async def stream_filtered(
        self,
        rules: list[dict[str, str]],
        on_tweet: Callable[[Post], Any],
        on_error: Optional[Callable[[Exception], Any]] = None,
    ) -> None:
        """Emit mock posts with delay."""
        for post in self._mock_data:
            await on_tweet(post)
            await asyncio.sleep(0.1)
