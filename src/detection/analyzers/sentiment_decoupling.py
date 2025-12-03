"""
Sentiment decoupling analyzer - detects when tone doesn't match expectations.

Key signal: "The news is good but the reaction is negative (or vice versa)"
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ...models.discourse import DiscourseSnapshot
from ...models.expectation import DiscourseExpectation
from ...models.delta import Delta, SentimentDecouplingDelta


class SentimentDecouplingAnalyzer:
    """
    Detects when sentiment doesn't match what we'd expect.

    This can indicate:
    - Insiders know something the market doesn't
    - Manipulated sentiment
    - Emerging problems not yet public
    """

    def __init__(self, z_threshold: float = 2.0):
        """
        Initialize the analyzer.

        Args:
            z_threshold: Number of standard deviations for anomaly
        """
        self.z_threshold = z_threshold

    def analyze(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> list[SentimentDecouplingDelta]:
        """
        Analyze for sentiment anomalies.

        Returns deltas when sentiment significantly differs from expected.
        """
        deltas = []

        # Check overall sentiment
        overall_delta = self._check_overall_sentiment(snapshot, expectation)
        if overall_delta:
            deltas.append(overall_delta)

        # Check topic-specific sentiment
        topic_deltas = self._check_topic_sentiments(snapshot, expectation)
        deltas.extend(topic_deltas)

        return deltas

    def _check_overall_sentiment(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> Optional[SentimentDecouplingDelta]:
        """Check if overall sentiment is anomalous."""
        observed = snapshot.avg_sentiment
        expected = expectation.expected_sentiment
        stddev = expectation.baseline.sentiment_stddev

        if stddev == 0:
            return None

        z_score = (observed - expected) / stddev

        if abs(z_score) >= self.z_threshold:
            # Calculate gap and confidence
            gap = observed - expected
            confidence = min(0.95, 0.4 + (abs(z_score) - self.z_threshold) * 0.1)

            # Determine dominant tones
            observed_tones = snapshot.dominant_tones
            expected_tones = self._infer_expected_tones(expected)

            return SentimentDecouplingDelta(
                delta_id=Delta.generate_id(),
                entity=snapshot.entity,
                detected_at=datetime.utcnow(),
                window_start=snapshot.window_start,
                window_end=snapshot.window_end,
                expected_sentiment=expected,
                observed_sentiment=observed,
                sentiment_gap=gap,
                z_score=z_score,
                is_statistically_significant=True,
                observed_tones=observed_tones,
                expected_tones=expected_tones,
                confidence=confidence,
            )

        return None

    def _check_topic_sentiments(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> list[SentimentDecouplingDelta]:
        """Check sentiment for specific topics."""
        deltas = []

        for expected_topic in expectation.expected_topics:
            topic_id = expected_topic.topic_id

            # Get observed sentiment for this topic
            observed = snapshot.topic_sentiments.get(topic_id)
            if observed is None:
                continue  # Topic not present

            expected = expected_topic.expected_sentiment
            stddev = expected_topic.sentiment_stddev

            if stddev == 0:
                continue

            z_score = (observed - expected) / stddev

            if abs(z_score) >= self.z_threshold:
                gap = observed - expected
                confidence = min(0.9, 0.3 + (abs(z_score) - self.z_threshold) * 0.1)

                delta = SentimentDecouplingDelta(
                    delta_id=Delta.generate_id(),
                    entity=snapshot.entity,
                    detected_at=datetime.utcnow(),
                    window_start=snapshot.window_start,
                    window_end=snapshot.window_end,
                    expected_sentiment=expected,
                    observed_sentiment=observed,
                    sentiment_gap=gap,
                    context_trigger=f"Topic: {expected_topic.topic_name}",
                    z_score=z_score,
                    is_statistically_significant=True,
                    confidence=confidence,
                )

                deltas.append(delta)

        return deltas

    def _infer_expected_tones(self, sentiment: float) -> list[str]:
        """Infer expected tones from sentiment value."""
        if sentiment > 0.3:
            return ["positive", "optimistic"]
        elif sentiment < -0.3:
            return ["negative", "concerned"]
        else:
            return ["neutral"]


class ToneShiftAnalyzer:
    """
    Detects sudden shifts in tone markers.

    Different from sentiment - this is about HOW things are being said,
    not just positive/negative.
    """

    def __init__(self):
        # Track historical tones
        self.tone_history: dict[str, list[list[str]]] = {}

    def analyze(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> list[Delta]:
        """Detect sudden tone shifts."""
        entity = snapshot.entity
        current_tones = set(snapshot.dominant_tones)

        # Get historical tones
        history = self.tone_history.get(entity, [])

        if len(history) < 3:
            # Not enough history
            self.tone_history.setdefault(entity, []).append(list(current_tones))
            return []

        # Get recent historical tones
        recent_tones = set()
        for past_tones in history[-5:]:
            recent_tones.update(past_tones)

        # Check for new concerning tones
        concerning_new_tones = current_tones - recent_tones
        concerning_markers = {"defensive", "urgent", "uncertain", "evasive"}

        if concerning_new_tones & concerning_markers:
            # New concerning tone appeared
            # Would create a ToneShiftDelta here
            pass

        # Update history
        self.tone_history.setdefault(entity, []).append(list(current_tones))

        # Keep history bounded
        if len(self.tone_history[entity]) > 20:
            self.tone_history[entity] = self.tone_history[entity][-20:]

        return []
