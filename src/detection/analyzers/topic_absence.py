"""
Topic absence analyzer - detects when expected topics aren't being discussed.

Key signal: "Why aren't they talking about X when they usually do?"
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ...models.discourse import DiscourseSnapshot
from ...models.expectation import DiscourseExpectation, ExpectedTopic
from ...models.delta import Delta, TopicAbsenceDelta


class Analyzer(Protocol):
    """Protocol for delta analyzers."""

    def analyze(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> list[Delta]:
        """Analyze snapshot against expectation and return deltas."""
        ...


class TopicAbsenceAnalyzer:
    """
    Detects when expected topics are absent from discourse.

    This is one of the most powerful signals: when people stop
    talking about something they usually discuss.
    """

    def __init__(self, threshold: float = 0.3):
        """
        Initialize the analyzer.

        Args:
            threshold: Ratio below which topic is considered absent
                      (0.3 = less than 30% of expected mentions)
        """
        self.threshold = threshold

    def analyze(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> list[TopicAbsenceDelta]:
        """
        Analyze for absent topics.

        Returns deltas for topics that are significantly underrepresented.
        """
        deltas = []

        for expected_topic in expectation.expected_topics:
            # Get observed count
            observed_count = snapshot.topic_counts.get(expected_topic.topic_id, 0)
            expected_count = expected_topic.expected_mention_count

            # Skip if we don't expect many mentions
            if expected_count < 1:
                continue

            # Calculate ratio
            ratio = observed_count / expected_count

            # Check if below threshold
            if ratio < self.threshold:
                # This topic is significantly underrepresented
                is_required = expectation.is_topic_required(expected_topic.topic_id)

                # Calculate confidence based on how far below threshold
                confidence = min(0.95, (self.threshold - ratio) / self.threshold + 0.3)

                # Boost confidence for required topics
                if is_required:
                    confidence = min(0.99, confidence + 0.2)

                delta = TopicAbsenceDelta(
                    delta_id=Delta.generate_id(),
                    entity=snapshot.entity,
                    detected_at=datetime.utcnow(),
                    window_start=snapshot.window_start,
                    window_end=snapshot.window_end,
                    missing_topic_id=expected_topic.topic_id,
                    missing_topic_name=expected_topic.topic_name,
                    expected_mentions=expected_count,
                    observed_mentions=observed_count,
                    baseline_mentions=expected_count,
                    topic_importance=expected_topic.absence_severity,
                    is_required_topic=is_required,
                    confidence=confidence,
                )

                deltas.append(delta)

        return deltas


class TopicSubstitutionAnalyzer:
    """
    Detects when topic B is being discussed instead of expected topic A.

    Signal: Deliberate topic avoidance by discussing something else.
    """

    def __init__(
        self,
        absence_threshold: float = 0.3,
        substitution_threshold: float = 2.0,
    ):
        self.absence_threshold = absence_threshold
        self.substitution_threshold = substitution_threshold

    def analyze(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> list[Delta]:
        """Detect topic substitution patterns."""
        deltas = []

        # First find absent topics
        absent_topics = []
        for expected_topic in expectation.expected_topics:
            observed_count = snapshot.topic_counts.get(expected_topic.topic_id, 0)
            expected_count = expected_topic.expected_mention_count

            if expected_count > 0 and (observed_count / expected_count) < self.absence_threshold:
                absent_topics.append(expected_topic)

        if not absent_topics:
            return deltas

        # Then find unexpectedly popular topics
        unexpected_popular = []
        for topic_id, count in snapshot.topic_counts.items():
            expected_topic = expectation.get_expected_topic(topic_id)

            if expected_topic is None:
                # Completely unexpected topic
                if count >= 5:  # Significant presence
                    unexpected_popular.append((topic_id, count, float('inf')))
            else:
                # Expected topic but much more than usual
                ratio = count / expected_topic.expected_mention_count
                if ratio > self.substitution_threshold:
                    unexpected_popular.append((topic_id, count, ratio))

        # If we have both absent topics and unexpected popular topics,
        # this could be substitution
        # (In a full implementation, would analyze semantic relationships)

        return deltas
