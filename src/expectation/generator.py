"""
Expectation generator - combines baselines and triggers to produce expectations.

The core "what SHOULD be happening" engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging

from ..models.discourse import DiscourseSnapshot
from ..models.expectation import (
    DiscourseExpectation,
    BaselinePattern,
    ExpectedTopic,
    ExpectedVoice,
    TimeWindow,
)
from .baseline_builder import BaselineBuilder
from .context_triggers import TriggerManager

logger = logging.getLogger(__name__)


class ExpectationGenerator:
    """
    Generates expectations for discourse at a given point in time.

    Combines:
    - Historical baselines (what usually happens)
    - Active context triggers (events that modify expectations)
    - Time-of-day/week patterns

    Output: What we EXPECT to see in discourse right now.
    """

    def __init__(
        self,
        baseline_builder: BaselineBuilder,
        trigger_manager: TriggerManager,
    ):
        self.baseline_builder = baseline_builder
        self.trigger_manager = trigger_manager

        # Cache of baselines by entity
        self.baselines: dict[str, BaselinePattern] = {}

    def load_baseline(self, entity: str, baseline: BaselinePattern) -> None:
        """Load a pre-computed baseline for an entity."""
        self.baselines[entity] = baseline
        logger.info(f"Loaded baseline for {entity}")

    def build_baseline(
        self,
        entity: str,
        historical_snapshots: list[DiscourseSnapshot],
    ) -> None:
        """Build and store baseline from historical data."""
        baseline = self.baseline_builder.build_baseline(
            entity=entity,
            snapshots=historical_snapshots,
        )
        self.baselines[entity] = baseline
        logger.info(f"Built baseline for {entity} from {len(historical_snapshots)} snapshots")

    def generate_expectation(
        self,
        entity: str,
        window_start: datetime,
        window_end: datetime,
    ) -> DiscourseExpectation:
        """
        Generate expectations for an entity in a time window.

        Args:
            entity: Entity to generate expectations for
            window_start: Start of the time window
            window_end: End of the time window

        Returns:
            DiscourseExpectation with all expected behaviors
        """
        baseline = self.baselines.get(entity)

        if baseline is None:
            logger.warning(f"No baseline for {entity}, using empty expectation")
            return self._empty_expectation(entity, window_start, window_end)

        # Start with baseline expectations
        expectation = self._expectation_from_baseline(
            entity=entity,
            baseline=baseline,
            window_start=window_start,
            window_end=window_end,
        )

        # Apply active triggers
        active_triggers = self.trigger_manager.get_active_triggers(
            entity=entity,
            at_time=window_start,
        )

        for trigger in active_triggers:
            expectation.apply_trigger(trigger)
            logger.debug(f"Applied trigger {trigger.name} to {entity}")

        return expectation

    def _expectation_from_baseline(
        self,
        entity: str,
        baseline: BaselinePattern,
        window_start: datetime,
        window_end: datetime,
    ) -> DiscourseExpectation:
        """Create an expectation from a baseline pattern."""
        # Calculate expected volume for this specific time window
        expected_volume = baseline.expected_volume_at(window_start)

        # Volume range (2 standard deviations)
        volume_min = max(0, expected_volume - 2 * baseline.post_stddev)
        volume_max = expected_volume + 2 * baseline.post_stddev

        # Sentiment range
        sentiment_min = baseline.avg_sentiment - 2 * baseline.sentiment_stddev
        sentiment_max = baseline.avg_sentiment + 2 * baseline.sentiment_stddev

        # Filter expected topics to those relevant at this time
        # (In a more sophisticated system, topics might have their own
        # temporal patterns)
        expected_topics = [
            t for t in baseline.typical_topics
            if t.confidence > 0.5
        ]

        # Filter expected voices to those expected to be active
        expected_voices = [
            v for v in baseline.typical_voices
            if v.expected_to_be_active(window_start)
        ]

        # Identify required topics (high importance)
        required_topics = [
            t.topic_id for t in expected_topics
            if t.absence_severity > 0.7
        ]

        # Identify required voices (key voices)
        required_voices = [
            v.account_id for v in expected_voices
            if v.is_key_voice
        ]

        return DiscourseExpectation(
            expectation_id=f"exp_{entity}_{int(window_start.timestamp())}",
            entity=entity,
            window_start=window_start,
            window_end=window_end,
            baseline=baseline,
            expected_post_count=expected_volume,
            post_count_range=(volume_min, volume_max),
            expected_topics=expected_topics,
            required_topics=required_topics,
            expected_voices=expected_voices,
            required_voices=required_voices,
            expected_sentiment=baseline.avg_sentiment,
            sentiment_range=(sentiment_min, sentiment_max),
            confidence=min(0.9, baseline.sample_size / 100),  # More samples = more confidence
        )

    def _empty_expectation(
        self,
        entity: str,
        window_start: datetime,
        window_end: datetime,
    ) -> DiscourseExpectation:
        """Create an empty expectation when no baseline exists."""
        return DiscourseExpectation(
            expectation_id=f"exp_{entity}_{int(window_start.timestamp())}_empty",
            entity=entity,
            window_start=window_start,
            window_end=window_end,
            expected_post_count=0,
            post_count_range=(0, float('inf')),
            expected_sentiment=0.0,
            sentiment_range=(-1.0, 1.0),
            confidence=0.1,  # Very low confidence
        )

    def update_with_new_data(
        self,
        entity: str,
        new_snapshots: list[DiscourseSnapshot],
    ) -> None:
        """Update baseline with new observation data."""
        existing = self.baselines.get(entity)

        if existing:
            updated = self.baseline_builder.update_baseline(
                existing=existing,
                new_snapshots=new_snapshots,
            )
            self.baselines[entity] = updated
            logger.info(f"Updated baseline for {entity}")
        else:
            self.build_baseline(entity, new_snapshots)

    def get_expectation_summary(
        self,
        entity: str,
        at_time: Optional[datetime] = None,
    ) -> dict:
        """Get a human-readable summary of expectations."""
        at_time = at_time or datetime.utcnow()
        window_end = at_time + timedelta(hours=1)

        expectation = self.generate_expectation(entity, at_time, window_end)

        return {
            "entity": entity,
            "time": at_time.isoformat(),
            "confidence": expectation.confidence,
            "expected_volume": {
                "count": expectation.expected_post_count,
                "range": expectation.post_count_range,
            },
            "expected_sentiment": {
                "value": expectation.expected_sentiment,
                "range": expectation.sentiment_range,
            },
            "required_topics": expectation.required_topics,
            "expected_voices_count": len(expectation.expected_voices),
            "required_voices": expectation.required_voices,
            "active_triggers": [
                t.name for t in expectation.active_triggers
            ],
        }

    def compare_to_observation(
        self,
        expectation: DiscourseExpectation,
        observation: DiscourseSnapshot,
    ) -> dict:
        """
        Compare an expectation to an actual observation.

        Returns a summary of differences for delta detection.
        """
        # Volume comparison
        volume_expected = expectation.expected_post_count
        volume_observed = observation.total_posts
        volume_ratio = volume_observed / volume_expected if volume_expected > 0 else float('inf')

        # Sentiment comparison
        sentiment_expected = expectation.expected_sentiment
        sentiment_observed = observation.avg_sentiment
        sentiment_diff = sentiment_observed - sentiment_expected

        # Missing required topics
        observed_topics = set(observation.topic_counts.keys())
        missing_required_topics = [
            t for t in expectation.required_topics
            if t not in observed_topics or observation.topic_counts.get(t, 0) == 0
        ]

        # Missing required voices
        observed_voices = {a.account_id for a in observation.active_accounts}
        missing_required_voices = [
            v for v in expectation.required_voices
            if v not in observed_voices
        ]

        # Topic presence comparison
        topic_presence = {}
        for topic in expectation.expected_topics:
            expected_count = topic.expected_mention_count
            observed_count = observation.topic_counts.get(topic.topic_id, 0)
            is_anomalous, z_score = topic.is_anomalous_count(observed_count)
            topic_presence[topic.topic_id] = {
                "expected": expected_count,
                "observed": observed_count,
                "anomalous": is_anomalous,
                "z_score": z_score,
            }

        return {
            "volume": {
                "expected": volume_expected,
                "observed": volume_observed,
                "ratio": volume_ratio,
                "anomalous": volume_ratio < 0.5 or volume_ratio > 2.0,
            },
            "sentiment": {
                "expected": sentiment_expected,
                "observed": sentiment_observed,
                "difference": sentiment_diff,
                "anomalous": abs(sentiment_diff) > 2 * expectation.baseline.sentiment_stddev,
            },
            "missing_required_topics": missing_required_topics,
            "missing_required_voices": missing_required_voices,
            "topic_presence": topic_presence,
            "overall_deviation_score": self._calculate_deviation_score(
                volume_ratio=volume_ratio,
                sentiment_diff=sentiment_diff,
                missing_topics=len(missing_required_topics),
                missing_voices=len(missing_required_voices),
            ),
        }

    def _calculate_deviation_score(
        self,
        volume_ratio: float,
        sentiment_diff: float,
        missing_topics: int,
        missing_voices: int,
    ) -> float:
        """Calculate overall deviation score from expected."""
        score = 0.0

        # Volume deviation (0-1)
        if volume_ratio < 1:
            score += (1 - volume_ratio) * 0.3
        else:
            score += min(1.0, (volume_ratio - 1) / 3) * 0.3

        # Sentiment deviation (0-1)
        score += min(1.0, abs(sentiment_diff)) * 0.3

        # Missing topics
        score += min(1.0, missing_topics / 3) * 0.2

        # Missing voices
        score += min(1.0, missing_voices / 3) * 0.2

        return min(1.0, score)
