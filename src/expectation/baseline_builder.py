"""
Baseline builder for establishing normal discourse patterns.

Analyzes historical data to build expectations for what "normal" looks like.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
import logging
import statistics

from ..models.discourse import DiscourseSnapshot, Account, Topic
from ..models.expectation import (
    BaselinePattern,
    ExpectedTopic,
    ExpectedVoice,
    TimeWindow,
)

logger = logging.getLogger(__name__)


@dataclass
class TimeSeriesPoint:
    """A point in a time series for pattern analysis."""
    timestamp: datetime
    value: float
    metadata: dict = field(default_factory=dict)


class BaselineBuilder:
    """
    Builds baseline patterns from historical discourse data.

    Analyzes:
    - Volume patterns (hourly, daily)
    - Topic patterns (what topics are typically discussed)
    - Voice patterns (who typically participates)
    - Sentiment patterns (typical sentiment range)
    - Response patterns (who responds to whom)
    """

    def __init__(
        self,
        lookback_days: int = 30,
        min_samples: int = 10,
    ):
        self.lookback_days = lookback_days
        self.min_samples = min_samples

    def build_baseline(
        self,
        entity: str,
        snapshots: list[DiscourseSnapshot],
        time_window: TimeWindow = TimeWindow.HOUR,
    ) -> BaselinePattern:
        """
        Build a baseline pattern from historical snapshots.

        Args:
            entity: Entity identifier
            snapshots: List of historical discourse snapshots
            time_window: Time window for the pattern

        Returns:
            BaselinePattern with computed expectations
        """
        if not snapshots:
            logger.warning(f"No snapshots provided for {entity}, returning empty baseline")
            return BaselinePattern(entity=entity, time_window=time_window)

        logger.info(f"Building baseline for {entity} from {len(snapshots)} snapshots")

        # Sort by time
        snapshots = sorted(snapshots, key=lambda s: s.window_start)

        # Build volume patterns
        hourly_volumes = self._compute_hourly_pattern(snapshots)
        daily_volumes = self._compute_daily_pattern(snapshots)
        avg_volume, volume_std = self._compute_volume_stats(snapshots)

        # Build topic patterns
        topic_expectations = self._compute_topic_expectations(snapshots)

        # Build voice patterns
        voice_expectations = self._compute_voice_expectations(snapshots)

        # Build sentiment patterns
        avg_sentiment, sentiment_std = self._compute_sentiment_stats(snapshots)

        # Build response patterns
        response_patterns = self._compute_response_patterns(snapshots)

        return BaselinePattern(
            entity=entity,
            time_window=time_window,
            avg_posts_per_window=avg_volume,
            post_stddev=volume_std,
            hourly_volume_pattern=hourly_volumes,
            daily_volume_pattern=daily_volumes,
            avg_sentiment=avg_sentiment,
            sentiment_stddev=sentiment_std,
            typical_topics=topic_expectations,
            typical_voices=voice_expectations,
            voice_response_patterns=response_patterns,
            sample_start=snapshots[0].window_start,
            sample_end=snapshots[-1].window_end,
            sample_size=len(snapshots),
            last_updated=datetime.utcnow(),
        )

    def _compute_hourly_pattern(self, snapshots: list[DiscourseSnapshot]) -> list[float]:
        """Compute normalized volume by hour of day."""
        hourly_counts = defaultdict(list)

        for snap in snapshots:
            hour = snap.window_start.hour
            hourly_counts[hour].append(snap.total_posts)

        # Calculate average for each hour
        hourly_avgs = []
        for hour in range(24):
            counts = hourly_counts.get(hour, [0])
            hourly_avgs.append(sum(counts) / len(counts) if counts else 0)

        # Normalize to 0-1 scale
        max_vol = max(hourly_avgs) if hourly_avgs else 1
        if max_vol > 0:
            hourly_avgs = [v / max_vol for v in hourly_avgs]

        return hourly_avgs

    def _compute_daily_pattern(self, snapshots: list[DiscourseSnapshot]) -> list[float]:
        """Compute normalized volume by day of week."""
        daily_counts = defaultdict(list)

        for snap in snapshots:
            day = snap.window_start.weekday()
            daily_counts[day].append(snap.total_posts)

        # Calculate average for each day
        daily_avgs = []
        for day in range(7):
            counts = daily_counts.get(day, [0])
            daily_avgs.append(sum(counts) / len(counts) if counts else 0)

        # Normalize
        max_vol = max(daily_avgs) if daily_avgs else 1
        if max_vol > 0:
            daily_avgs = [v / max_vol for v in daily_avgs]

        return daily_avgs

    def _compute_volume_stats(
        self,
        snapshots: list[DiscourseSnapshot],
    ) -> tuple[float, float]:
        """Compute average and standard deviation of volume."""
        volumes = [s.total_posts for s in snapshots]

        if not volumes:
            return 0.0, 0.0

        avg = statistics.mean(volumes)
        std = statistics.stdev(volumes) if len(volumes) > 1 else 0.0

        return avg, std

    def _compute_topic_expectations(
        self,
        snapshots: list[DiscourseSnapshot],
    ) -> list[ExpectedTopic]:
        """Compute expected topic patterns."""
        topic_mentions = defaultdict(list)  # topic_id -> [counts per snapshot]
        topic_sentiments = defaultdict(list)  # topic_id -> [sentiments]

        for snap in snapshots:
            for topic_id, count in snap.topic_counts.items():
                topic_mentions[topic_id].append(count)
            for topic_id, sentiment in snap.topic_sentiments.items():
                topic_sentiments[topic_id].append(sentiment)

        expectations = []
        for topic_id, counts in topic_mentions.items():
            if len(counts) < self.min_samples:
                continue

            avg_count = statistics.mean(counts)
            count_std = statistics.stdev(counts) if len(counts) > 1 else 0.0

            sentiments = topic_sentiments.get(topic_id, [0.0])
            avg_sentiment = statistics.mean(sentiments) if sentiments else 0.0
            sentiment_std = statistics.stdev(sentiments) if len(sentiments) > 1 else 0.0

            # Calculate importance based on frequency and consistency
            frequency_score = min(1.0, len(counts) / len(snapshots))
            consistency_score = 1.0 - (count_std / (avg_count + 1))
            importance = (frequency_score + consistency_score) / 2

            expectations.append(ExpectedTopic(
                topic_id=topic_id,
                topic_name=topic_id.split(":")[-1],  # Extract name from ID
                expected_mention_count=avg_count,
                mention_stddev=count_std,
                expected_sentiment=avg_sentiment,
                sentiment_stddev=sentiment_std,
                confidence=frequency_score,
                sample_size=len(counts),
                absence_severity=importance,
            ))

        # Sort by importance
        expectations.sort(key=lambda t: t.absence_severity, reverse=True)

        return expectations

    def _compute_voice_expectations(
        self,
        snapshots: list[DiscourseSnapshot],
    ) -> list[ExpectedVoice]:
        """Compute expected voice patterns."""
        voice_activity = defaultdict(list)  # account_id -> [post counts per snapshot]
        voice_info = {}  # account_id -> Account

        for snap in snapshots:
            active_ids = {a.account_id for a in snap.active_accounts}

            for account in snap.active_accounts:
                voice_info[account.account_id] = account
                # Count their posts in this snapshot
                post_count = sum(
                    1 for p in snap.posts
                    if p.author.account_id == account.account_id
                )
                voice_activity[account.account_id].append(post_count)

        expectations = []
        for account_id, activity in voice_activity.items():
            if len(activity) < self.min_samples // 2:  # Lower threshold for voices
                continue

            account = voice_info.get(account_id)
            if not account:
                continue

            avg_posts = statistics.mean(activity)
            post_std = statistics.stdev(activity) if len(activity) > 1 else 0.0

            # Calculate presence rate (how often they're active)
            presence_rate = len(activity) / len(snapshots)

            expectations.append(ExpectedVoice(
                account_id=account_id,
                username=account.username,
                expected_posts_per_day=avg_posts * (24 / 1),  # Adjust for window size
                post_stddev=post_std,
                typical_topics=[],  # Would need more analysis
                typical_sentiment=0.0,
                silence_severity=presence_rate * (0.8 if account.is_high_value() else 0.3),
                is_key_voice=account.is_high_value(),
            ))

        # Sort by significance
        expectations.sort(key=lambda v: v.silence_severity, reverse=True)

        return expectations

    def _compute_sentiment_stats(
        self,
        snapshots: list[DiscourseSnapshot],
    ) -> tuple[float, float]:
        """Compute average and standard deviation of sentiment."""
        sentiments = [s.avg_sentiment for s in snapshots if s.total_posts > 0]

        if not sentiments:
            return 0.0, 0.5  # Neutral with wide variance as default

        avg = statistics.mean(sentiments)
        std = statistics.stdev(sentiments) if len(sentiments) > 1 else 0.3

        return avg, std

    def _compute_response_patterns(
        self,
        snapshots: list[DiscourseSnapshot],
    ) -> dict[str, list[str]]:
        """
        Compute who typically responds to whom.

        Returns dict of {account_id: [responder_account_ids]}
        """
        response_counts = defaultdict(lambda: defaultdict(int))

        for snap in snapshots:
            for thread in snap.threads:
                if not thread.root_post:
                    continue

                author_id = thread.root_post.author.account_id
                for reply in thread.replies:
                    responder_id = reply.author.account_id
                    if responder_id != author_id:
                        response_counts[author_id][responder_id] += 1

        # Convert to list of typical responders (threshold: responded at least twice)
        response_patterns = {}
        for author_id, responders in response_counts.items():
            typical_responders = [
                responder_id for responder_id, count in responders.items()
                if count >= 2
            ]
            if typical_responders:
                response_patterns[author_id] = typical_responders

        return response_patterns

    def update_baseline(
        self,
        existing: BaselinePattern,
        new_snapshots: list[DiscourseSnapshot],
        decay_factor: float = 0.95,
    ) -> BaselinePattern:
        """
        Incrementally update a baseline with new data.

        Uses exponential decay to weight recent data more heavily.
        """
        if not new_snapshots:
            return existing

        # Build baseline from new data
        new_baseline = self.build_baseline(
            entity=existing.entity,
            snapshots=new_snapshots,
            time_window=existing.time_window,
        )

        # Merge with decay
        merged = BaselinePattern(
            entity=existing.entity,
            time_window=existing.time_window,
        )

        # Merge volume stats
        merged.avg_posts_per_window = (
            existing.avg_posts_per_window * decay_factor +
            new_baseline.avg_posts_per_window * (1 - decay_factor)
        )
        merged.post_stddev = (
            existing.post_stddev * decay_factor +
            new_baseline.post_stddev * (1 - decay_factor)
        )

        # Merge hourly patterns
        merged.hourly_volume_pattern = [
            existing.hourly_volume_pattern[i] * decay_factor +
            new_baseline.hourly_volume_pattern[i] * (1 - decay_factor)
            for i in range(24)
        ]

        # Merge daily patterns
        merged.daily_volume_pattern = [
            existing.daily_volume_pattern[i] * decay_factor +
            new_baseline.daily_volume_pattern[i] * (1 - decay_factor)
            for i in range(7)
        ]

        # Merge sentiment
        merged.avg_sentiment = (
            existing.avg_sentiment * decay_factor +
            new_baseline.avg_sentiment * (1 - decay_factor)
        )
        merged.sentiment_stddev = (
            existing.sentiment_stddev * decay_factor +
            new_baseline.sentiment_stddev * (1 - decay_factor)
        )

        # For topics and voices, combine lists (more complex merging in production)
        merged.typical_topics = self._merge_topics(
            existing.typical_topics,
            new_baseline.typical_topics,
            decay_factor,
        )
        merged.typical_voices = self._merge_voices(
            existing.typical_voices,
            new_baseline.typical_voices,
            decay_factor,
        )

        merged.sample_start = existing.sample_start
        merged.sample_end = new_snapshots[-1].window_end
        merged.sample_size = existing.sample_size + len(new_snapshots)
        merged.last_updated = datetime.utcnow()

        return merged

    def _merge_topics(
        self,
        existing: list[ExpectedTopic],
        new: list[ExpectedTopic],
        decay: float,
    ) -> list[ExpectedTopic]:
        """Merge topic expectations with decay."""
        existing_map = {t.topic_id: t for t in existing}
        new_map = {t.topic_id: t for t in new}

        merged = []
        all_ids = set(existing_map.keys()) | set(new_map.keys())

        for topic_id in all_ids:
            old = existing_map.get(topic_id)
            current = new_map.get(topic_id)

            if old and current:
                # Merge
                merged.append(ExpectedTopic(
                    topic_id=topic_id,
                    topic_name=current.topic_name,
                    expected_mention_count=(
                        old.expected_mention_count * decay +
                        current.expected_mention_count * (1 - decay)
                    ),
                    mention_stddev=(
                        old.mention_stddev * decay +
                        current.mention_stddev * (1 - decay)
                    ),
                    expected_sentiment=(
                        old.expected_sentiment * decay +
                        current.expected_sentiment * (1 - decay)
                    ),
                    sentiment_stddev=(
                        old.sentiment_stddev * decay +
                        current.sentiment_stddev * (1 - decay)
                    ),
                    sample_size=old.sample_size + current.sample_size,
                ))
            elif old:
                # Decay old topic
                old.expected_mention_count *= decay
                merged.append(old)
            else:
                # New topic
                merged.append(current)

        return merged

    def _merge_voices(
        self,
        existing: list[ExpectedVoice],
        new: list[ExpectedVoice],
        decay: float,
    ) -> list[ExpectedVoice]:
        """Merge voice expectations with decay."""
        # Similar logic to topics
        existing_map = {v.account_id: v for v in existing}
        new_map = {v.account_id: v for v in new}

        merged = []
        all_ids = set(existing_map.keys()) | set(new_map.keys())

        for account_id in all_ids:
            old = existing_map.get(account_id)
            current = new_map.get(account_id)

            if old and current:
                merged.append(ExpectedVoice(
                    account_id=account_id,
                    username=current.username,
                    expected_posts_per_day=(
                        old.expected_posts_per_day * decay +
                        current.expected_posts_per_day * (1 - decay)
                    ),
                    post_stddev=(
                        old.post_stddev * decay +
                        current.post_stddev * (1 - decay)
                    ),
                    is_key_voice=old.is_key_voice or current.is_key_voice,
                    silence_severity=max(old.silence_severity, current.silence_severity),
                ))
            elif old:
                merged.append(old)
            else:
                merged.append(current)

        return merged
