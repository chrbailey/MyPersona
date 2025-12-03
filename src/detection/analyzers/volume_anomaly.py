"""
Volume anomaly analyzer - detects unusual activity levels.

Key signals:
- Volume collapse: Suspiciously quiet (coordinated non-discussion)
- Volume spike: Unusually loud (coordinated campaign or breaking news)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ...models.discourse import DiscourseSnapshot
from ...models.expectation import DiscourseExpectation
from ...models.delta import Delta, DeltaType, VolumeAnomalyDelta


class VolumeAnomalyAnalyzer:
    """
    Detects unusual volume levels.

    Both collapses and spikes can be significant:
    - Collapse: coordinated silence, holiday, or pre-announcement quiet
    - Spike: breaking news, coordinated campaign, or crisis
    """

    def __init__(
        self,
        collapse_threshold: float = 0.5,
        spike_threshold: float = 2.0,
        z_threshold: float = 2.0,
    ):
        """
        Initialize the analyzer.

        Args:
            collapse_threshold: Volume ratio below which = collapse
            spike_threshold: Volume ratio above which = spike
            z_threshold: Z-score threshold for statistical significance
        """
        self.collapse_threshold = collapse_threshold
        self.spike_threshold = spike_threshold
        self.z_threshold = z_threshold

    def analyze(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> list[VolumeAnomalyDelta]:
        """
        Analyze for volume anomalies.

        Returns deltas for significant volume deviations.
        """
        deltas = []

        expected_volume = expectation.expected_post_count
        observed_volume = snapshot.total_posts

        if expected_volume <= 0:
            return deltas

        # Calculate ratio and z-score
        ratio = observed_volume / expected_volume
        stddev = expectation.baseline.post_stddev

        if stddev > 0:
            z_score = (observed_volume - expected_volume) / stddev
        else:
            z_score = 0

        # Check for collapse
        if ratio < self.collapse_threshold:
            delta = self._create_volume_delta(
                snapshot=snapshot,
                expectation=expectation,
                is_collapse=True,
                ratio=ratio,
                z_score=z_score,
            )
            deltas.append(delta)

        # Check for spike
        elif ratio > self.spike_threshold and abs(z_score) >= self.z_threshold:
            delta = self._create_volume_delta(
                snapshot=snapshot,
                expectation=expectation,
                is_collapse=False,
                ratio=ratio,
                z_score=z_score,
            )
            deltas.append(delta)

        return deltas

    def _create_volume_delta(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
        is_collapse: bool,
        ratio: float,
        z_score: float,
    ) -> VolumeAnomalyDelta:
        """Create a volume anomaly delta."""
        # Calculate confidence
        # Higher confidence for more extreme deviations
        if is_collapse:
            confidence = min(0.95, 0.5 + (self.collapse_threshold - ratio) * 0.5)
        else:
            confidence = min(0.95, 0.4 + (ratio - self.spike_threshold) * 0.1)

        # Calculate expected authors
        unique_author_ratio = (
            snapshot.unique_authors / snapshot.total_posts
            if snapshot.total_posts > 0 else 0
        )
        expected_authors = expectation.expected_post_count * unique_author_ratio

        return VolumeAnomalyDelta(
            delta_id=Delta.generate_id(),
            entity=snapshot.entity,
            detected_at=datetime.utcnow(),
            window_start=snapshot.window_start,
            window_end=snapshot.window_end,
            expected_volume=expectation.expected_post_count,
            observed_volume=snapshot.total_posts,
            volume_ratio=ratio,
            baseline_volume=expectation.baseline.avg_posts_per_window,
            volume_stddev=expectation.baseline.post_stddev,
            z_score=z_score,
            is_collapse=is_collapse,
            unique_authors=snapshot.unique_authors,
            expected_authors=expected_authors,
            confidence=confidence,
        )


class AuthorConcentrationAnalyzer:
    """
    Analyzes the concentration of posts among authors.

    Detects when discourse is dominated by few accounts (potential coordination)
    or when normal frequent posters are absent.
    """

    def __init__(
        self,
        concentration_threshold: float = 0.5,
    ):
        """
        Args:
            concentration_threshold: If top N% of authors make > threshold% of posts
        """
        self.concentration_threshold = concentration_threshold

    def analyze(
        self,
        snapshot: DiscourseSnapshot,
    ) -> dict:
        """Analyze author concentration."""
        if not snapshot.posts:
            return {"concentration": 0, "dominant_authors": []}

        # Count posts per author
        author_counts = {}
        for post in snapshot.posts:
            author_id = post.author.account_id
            author_counts[author_id] = author_counts.get(author_id, 0) + 1

        total_posts = len(snapshot.posts)
        total_authors = len(author_counts)

        # Sort by post count
        sorted_authors = sorted(
            author_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Calculate concentration (Gini-like)
        # How much do top 10% of authors contribute
        top_10_pct = max(1, total_authors // 10)
        top_authors = sorted_authors[:top_10_pct]
        top_posts = sum(count for _, count in top_authors)
        concentration = top_posts / total_posts if total_posts > 0 else 0

        return {
            "concentration": concentration,
            "total_authors": total_authors,
            "total_posts": total_posts,
            "dominant_authors": [
                {
                    "account_id": author_id,
                    "post_count": count,
                    "percentage": count / total_posts * 100,
                }
                for author_id, count in sorted_authors[:5]
            ],
            "is_concentrated": concentration > self.concentration_threshold,
        }
