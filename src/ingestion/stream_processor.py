"""
Stream processor for real-time post processing.

Handles the flow from raw posts to preprocessed discourse data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
import logging
from collections import defaultdict

from ..models.discourse import Post, DiscourseSnapshot, Account, Topic
from ..config.settings import Settings, TrackedEntity
from .x_client import XClient
from .preprocessor import Preprocessor

logger = logging.getLogger(__name__)


@dataclass
class EntityBuffer:
    """Buffer for collecting posts about a specific entity."""
    entity_id: str
    posts: list[Post] = field(default_factory=list)
    last_flush: datetime = field(default_factory=datetime.utcnow)

    def add(self, post: Post) -> None:
        """Add a post to the buffer."""
        self.posts.append(post)

    def flush(self) -> list[Post]:
        """Return and clear buffered posts."""
        posts = self.posts
        self.posts = []
        self.last_flush = datetime.utcnow()
        return posts

    @property
    def count(self) -> int:
        """Number of posts in buffer."""
        return len(self.posts)


class StreamProcessor:
    """
    Processes incoming posts and creates discourse snapshots.

    Responsibilities:
    - Receive posts from X client
    - Run through preprocessor for entity extraction
    - Buffer posts by entity
    - Emit snapshots on time intervals
    """

    def __init__(
        self,
        x_client: XClient,
        preprocessor: Preprocessor,
        settings: Settings,
    ):
        self.x_client = x_client
        self.preprocessor = preprocessor
        self.settings = settings

        # Entity tracking
        self.tracked_entities: dict[str, TrackedEntity] = {
            e.entity_id: e for e in settings.tracked_entities
        }

        # Buffers per entity
        self.buffers: dict[str, EntityBuffer] = {
            entity_id: EntityBuffer(entity_id=entity_id)
            for entity_id in self.tracked_entities
        }

        # Callbacks
        self.on_snapshot: Optional[Callable[[DiscourseSnapshot], Any]] = None
        self.on_post: Optional[Callable[[Post, str], Any]] = None  # (post, entity_id)

        # Metrics
        self.posts_processed = 0
        self.snapshots_created = 0

        # Control
        self._running = False
        self._snapshot_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the stream processor."""
        if self._running:
            return

        self._running = True
        logger.info("Starting stream processor")

        # Build stream rules from tracked entities
        rules = self._build_stream_rules()

        # Start snapshot timer
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())

        # Start streaming
        await self.x_client.stream_filtered(
            rules=rules,
            on_tweet=self._handle_post,
            on_error=self._handle_error,
        )

    async def stop(self) -> None:
        """Stop the stream processor."""
        self._running = False

        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass

        logger.info(
            f"Stream processor stopped. "
            f"Processed {self.posts_processed} posts, "
            f"created {self.snapshots_created} snapshots."
        )

    async def process_historical(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
    ) -> list[DiscourseSnapshot]:
        """
        Process historical data for an entity.

        Used for building baselines and backtesting.
        """
        entity = self.tracked_entities.get(entity_id)
        if not entity:
            logger.error(f"Unknown entity: {entity_id}")
            return []

        end_time = end_time or datetime.utcnow()
        query = self._build_query_for_entity(entity)

        logger.info(f"Processing historical data for {entity_id}: {start_time} to {end_time}")

        posts = await self.x_client.search_recent(
            query=query,
            max_results=100,
            start_time=start_time,
            end_time=end_time,
        )

        # Process posts
        processed_posts = []
        for post in posts:
            processed = await self.preprocessor.process(post)
            processed_posts.append(processed)

        # Create snapshot
        snapshot = self._create_snapshot(entity_id, processed_posts, start_time, end_time)
        return [snapshot]

    async def _handle_post(self, post: Post) -> None:
        """Handle an incoming post from the stream."""
        self.posts_processed += 1

        # Preprocess the post
        processed_post = await self.preprocessor.process(post)

        # Match to entities
        matched_entities = self._match_post_to_entities(processed_post)

        for entity_id in matched_entities:
            self.buffers[entity_id].add(processed_post)

            if self.on_post:
                await self.on_post(processed_post, entity_id)

        if self.posts_processed % 100 == 0:
            logger.debug(f"Processed {self.posts_processed} posts")

    async def _handle_error(self, error: Exception) -> None:
        """Handle stream errors."""
        logger.error(f"Stream error: {error}")

    async def _snapshot_loop(self) -> None:
        """Periodically create snapshots from buffers."""
        interval = self.settings.detection.snapshot_window_minutes * 60

        while self._running:
            await asyncio.sleep(interval)

            for entity_id, buffer in self.buffers.items():
                if buffer.count > 0:
                    posts = buffer.flush()
                    now = datetime.utcnow()
                    start_time = now - timedelta(seconds=interval)

                    snapshot = self._create_snapshot(
                        entity_id, posts, start_time, now
                    )

                    self.snapshots_created += 1

                    if self.on_snapshot:
                        await self.on_snapshot(snapshot)

    def _build_stream_rules(self) -> list[dict[str, str]]:
        """Build X API filter rules from tracked entities."""
        rules = []

        for entity in self.tracked_entities.values():
            if not entity.enabled:
                continue

            query = self._build_query_for_entity(entity)
            rules.append({
                "value": query,
                "tag": entity.entity_id,
            })

        return rules

    def _build_query_for_entity(self, entity: TrackedEntity) -> str:
        """Build a search query for an entity."""
        terms = []

        # Add tickers
        for ticker in entity.tickers:
            terms.append(f"${ticker}")

        # Add usernames (from:)
        for username in entity.usernames:
            terms.append(f"from:{username}")
            terms.append(f"@{username}")

        # Add keywords
        terms.extend(entity.keywords)

        # Add hashtags
        for hashtag in entity.hashtags:
            terms.append(f"#{hashtag}")

        # Combine with OR
        query = " OR ".join(terms)

        # Add language filter
        if self.settings.x_api.languages:
            lang_filter = " OR ".join(
                f"lang:{lang}" for lang in self.settings.x_api.languages
            )
            query = f"({query}) ({lang_filter})"

        return query

    def _match_post_to_entities(self, post: Post) -> list[str]:
        """Match a post to tracked entities."""
        matched = []
        text_lower = post.text.lower()

        for entity_id, entity in self.tracked_entities.items():
            # Check tickers
            for ticker in entity.tickers:
                if f"${ticker.lower()}" in text_lower:
                    matched.append(entity_id)
                    break

            if entity_id in matched:
                continue

            # Check keywords
            for keyword in entity.keywords:
                if keyword.lower() in text_lower:
                    matched.append(entity_id)
                    break

            if entity_id in matched:
                continue

            # Check hashtags
            for hashtag in entity.hashtags:
                if f"#{hashtag.lower()}" in text_lower:
                    matched.append(entity_id)
                    break

            if entity_id in matched:
                continue

            # Check mentioned accounts
            for username in entity.usernames:
                if username.lower() in [m.lower() for m in post.mentioned_accounts]:
                    matched.append(entity_id)
                    break

        return matched

    def _create_snapshot(
        self,
        entity_id: str,
        posts: list[Post],
        window_start: datetime,
        window_end: datetime,
    ) -> DiscourseSnapshot:
        """Create a discourse snapshot from posts."""
        # Aggregate metrics
        topic_counts: dict[str, int] = defaultdict(int)
        topic_sentiments: dict[str, list[float]] = defaultdict(list)
        unique_authors: set[str] = set()
        active_accounts: list[Account] = []
        high_value_accounts: list[Account] = []
        total_engagement = 0
        sentiment_scores: list[float] = []
        tones: list[str] = []

        for post in posts:
            unique_authors.add(post.author.account_id)
            total_engagement += post.likes + post.reposts + post.replies
            sentiment_scores.append(post.sentiment_score)
            tones.extend(post.tone_markers)

            # Track active accounts
            if post.author not in active_accounts:
                active_accounts.append(post.author)
                if post.author.is_high_value():
                    high_value_accounts.append(post.author)

            # Count topics
            for topic in post.topics:
                topic_counts[topic.topic_id] += 1
                topic_sentiments[topic.topic_id].append(post.sentiment_score)

        # Calculate aggregates
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        sentiment_variance = (
            sum((s - avg_sentiment) ** 2 for s in sentiment_scores) / len(sentiment_scores)
            if sentiment_scores else 0.0
        )

        # Calculate topic average sentiments
        topic_avg_sentiments = {
            topic_id: sum(scores) / len(scores)
            for topic_id, scores in topic_sentiments.items()
        }

        # Get dominant tones
        tone_counts = defaultdict(int)
        for tone in tones:
            tone_counts[tone] += 1
        dominant_tones = sorted(tone_counts.keys(), key=lambda t: tone_counts[t], reverse=True)[:3]

        return DiscourseSnapshot(
            snapshot_id=f"snap_{entity_id}_{int(window_end.timestamp())}",
            entity=entity_id,
            window_start=window_start,
            window_end=window_end,
            posts=posts,
            total_posts=len(posts),
            unique_authors=len(unique_authors),
            total_engagement=total_engagement,
            topic_counts=dict(topic_counts),
            topic_sentiments=topic_avg_sentiments,
            active_accounts=active_accounts,
            high_value_accounts_active=high_value_accounts,
            avg_sentiment=avg_sentiment,
            sentiment_variance=sentiment_variance,
            dominant_tones=dominant_tones,
        )

    def get_metrics(self) -> dict:
        """Get processing metrics."""
        buffer_sizes = {
            entity_id: buffer.count
            for entity_id, buffer in self.buffers.items()
        }

        return {
            "posts_processed": self.posts_processed,
            "snapshots_created": self.snapshots_created,
            "buffer_sizes": buffer_sizes,
            "tracked_entities": len(self.tracked_entities),
        }
