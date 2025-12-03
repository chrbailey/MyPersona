"""
Delta detector - the core engine for finding discourse gaps.

Compares expected discourse to observed discourse and identifies deltas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Callable
import logging

from ..models.discourse import DiscourseSnapshot
from ..models.expectation import DiscourseExpectation
from ..models.delta import (
    Delta,
    DeltaType,
    DeltaSeverity,
    DeltaCluster,
    TopicAbsenceDelta,
    VoiceSilenceDelta,
    SentimentDecouplingDelta,
    NetworkBreakDelta,
    VolumeAnomalyDelta,
    CoordinatedSilenceDelta,
)
from ..expectation.generator import ExpectationGenerator
from .analyzers.topic_absence import TopicAbsenceAnalyzer
from .analyzers.voice_silence import VoiceSilenceAnalyzer
from .analyzers.sentiment_decoupling import SentimentDecouplingAnalyzer
from .analyzers.volume_anomaly import VolumeAnomalyAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class DetectionConfig:
    """Configuration for delta detection."""
    # Thresholds
    topic_absence_threshold: float = 0.3  # Below 30% of expected = absent
    voice_silence_threshold_hours: float = 24.0
    sentiment_deviation_threshold: float = 2.0  # Z-score
    volume_collapse_threshold: float = 0.5  # Below 50% of expected

    # Confidence filters
    min_delta_confidence: float = 0.5

    # Clustering
    cluster_window_minutes: int = 60
    min_cluster_size: int = 2


class DeltaDetector:
    """
    Detects deltas between expected and observed discourse.

    The core innovation: finding what ISN'T there that SHOULD be.
    """

    def __init__(
        self,
        expectation_generator: ExpectationGenerator,
        config: Optional[DetectionConfig] = None,
    ):
        self.expectation_generator = expectation_generator
        self.config = config or DetectionConfig()

        # Specialized analyzers
        self.analyzers = [
            TopicAbsenceAnalyzer(threshold=self.config.topic_absence_threshold),
            VoiceSilenceAnalyzer(threshold_hours=self.config.voice_silence_threshold_hours),
            SentimentDecouplingAnalyzer(z_threshold=self.config.sentiment_deviation_threshold),
            VolumeAnomalyAnalyzer(collapse_threshold=self.config.volume_collapse_threshold),
        ]

        # Recent deltas for clustering
        self.recent_deltas: list[Delta] = []
        self.delta_history: list[Delta] = []

        # Callbacks
        self.on_delta_detected: Optional[Callable[[Delta], None]] = None
        self.on_cluster_detected: Optional[Callable[[DeltaCluster], None]] = None

    def detect(
        self,
        snapshot: DiscourseSnapshot,
        expectation: Optional[DiscourseExpectation] = None,
    ) -> list[Delta]:
        """
        Detect deltas in a discourse snapshot.

        Args:
            snapshot: The observed discourse
            expectation: Expected discourse (generated if not provided)

        Returns:
            List of detected deltas
        """
        # Generate expectation if not provided
        if expectation is None:
            expectation = self.expectation_generator.generate_expectation(
                entity=snapshot.entity,
                window_start=snapshot.window_start,
                window_end=snapshot.window_end,
            )

        logger.debug(f"Detecting deltas for {snapshot.entity}")

        # Run all analyzers
        deltas = []
        for analyzer in self.analyzers:
            analyzer_deltas = analyzer.analyze(snapshot, expectation)
            deltas.extend(analyzer_deltas)

        # Filter by confidence
        deltas = [
            d for d in deltas
            if d.confidence >= self.config.min_delta_confidence
        ]

        # Assign severity
        for delta in deltas:
            delta.severity = self._calculate_severity(delta)

        # Store for clustering
        self.recent_deltas.extend(deltas)
        self.delta_history.extend(deltas)

        # Check for clusters
        clusters = self._detect_clusters(snapshot.entity)

        # Trigger callbacks
        for delta in deltas:
            if self.on_delta_detected:
                self.on_delta_detected(delta)

        for cluster in clusters:
            if self.on_cluster_detected:
                self.on_cluster_detected(cluster)

        logger.info(f"Detected {len(deltas)} deltas for {snapshot.entity}")

        return deltas

    def detect_coordinated_silence(
        self,
        snapshot: DiscourseSnapshot,
        expectation: DiscourseExpectation,
    ) -> Optional[CoordinatedSilenceDelta]:
        """
        Detect if multiple expected voices went quiet together.

        This is a special delta type that looks for coordination.
        """
        # Get silent voices
        silent_deltas = [
            d for d in self.recent_deltas
            if d.delta_type == DeltaType.VOICE_SILENCE
            and d.entity == snapshot.entity
            and isinstance(d, VoiceSilenceDelta)
        ]

        if len(silent_deltas) < 2:
            return None

        # Check if they went silent around the same time
        silence_times = []
        for delta in silent_deltas:
            if isinstance(delta, VoiceSilenceDelta) and delta.last_post_time:
                silence_times.append(delta.last_post_time)

        if not silence_times:
            return None

        # Calculate time spread
        min_time = min(silence_times)
        max_time = max(silence_times)
        spread_hours = (max_time - min_time).total_seconds() / 3600

        # If they went quiet within a few hours of each other, it's suspicious
        if spread_hours < 6:  # Went quiet within 6 hours
            coordination_score = 1.0 - (spread_hours / 6)

            return CoordinatedSilenceDelta(
                delta_id=Delta.generate_id(),
                entity=snapshot.entity,
                detected_at=datetime.utcnow(),
                window_start=snapshot.window_start,
                window_end=snapshot.window_end,
                silent_accounts=[d.silent_account_id for d in silent_deltas if isinstance(d, VoiceSilenceDelta)],
                silent_usernames=[d.silent_username for d in silent_deltas if isinstance(d, VoiceSilenceDelta)],
                silence_start_times=silence_times,
                time_spread_hours=spread_hours,
                coordination_score=coordination_score,
                confidence=coordination_score * 0.8,
            )

        return None

    def _calculate_severity(self, delta: Delta) -> DeltaSeverity:
        """Calculate the severity of a delta."""
        # Base on deviation score and confidence
        score = delta.deviation_score * delta.confidence

        if score >= 0.8:
            return DeltaSeverity.CRITICAL
        elif score >= 0.6:
            return DeltaSeverity.HIGH
        elif score >= 0.4:
            return DeltaSeverity.MEDIUM
        else:
            return DeltaSeverity.LOW

    def _detect_clusters(self, entity: str) -> list[DeltaCluster]:
        """Detect clusters of related deltas."""
        clusters = []

        # Filter recent deltas for this entity
        entity_deltas = [
            d for d in self.recent_deltas
            if d.entity == entity
        ]

        if len(entity_deltas) < self.config.min_cluster_size:
            return clusters

        # Group by time window
        window = timedelta(minutes=self.config.cluster_window_minutes)
        current_cluster: Optional[DeltaCluster] = None

        for delta in sorted(entity_deltas, key=lambda d: d.detected_at):
            if current_cluster is None:
                current_cluster = DeltaCluster(
                    cluster_id=DeltaCluster.generate_id(),
                    entity=entity,
                )
                current_cluster.add_delta(delta)
            elif (
                current_cluster.last_delta_time and
                delta.detected_at - current_cluster.last_delta_time <= window
            ):
                current_cluster.add_delta(delta)
            else:
                # Finalize current cluster if big enough
                if len(current_cluster.deltas) >= self.config.min_cluster_size:
                    current_cluster.summary = self._summarize_cluster(current_cluster)
                    clusters.append(current_cluster)

                # Start new cluster
                current_cluster = DeltaCluster(
                    cluster_id=DeltaCluster.generate_id(),
                    entity=entity,
                )
                current_cluster.add_delta(delta)

        # Handle final cluster
        if current_cluster and len(current_cluster.deltas) >= self.config.min_cluster_size:
            current_cluster.summary = self._summarize_cluster(current_cluster)
            clusters.append(current_cluster)

        return clusters

    def _summarize_cluster(self, cluster: DeltaCluster) -> str:
        """Generate a summary for a delta cluster."""
        type_counts = {}
        for delta in cluster.deltas:
            type_name = delta.delta_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        type_summary = ", ".join(
            f"{count} {type_name}" for type_name, count in type_counts.items()
        )

        return (
            f"Cluster of {len(cluster.deltas)} deltas for {cluster.entity}: "
            f"{type_summary}. Combined severity: {cluster.combined_severity.value}"
        )

    def cleanup_old_deltas(self, max_age_hours: int = 24) -> None:
        """Remove old deltas from recent tracking."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        self.recent_deltas = [
            d for d in self.recent_deltas
            if d.detected_at >= cutoff
        ]

    def get_recent_deltas(
        self,
        entity: Optional[str] = None,
        delta_type: Optional[DeltaType] = None,
        min_severity: Optional[DeltaSeverity] = None,
    ) -> list[Delta]:
        """Get recent deltas with optional filtering."""
        deltas = self.recent_deltas

        if entity:
            deltas = [d for d in deltas if d.entity == entity]

        if delta_type:
            deltas = [d for d in deltas if d.delta_type == delta_type]

        if min_severity:
            severity_order = list(DeltaSeverity)
            min_index = severity_order.index(min_severity)
            deltas = [
                d for d in deltas
                if severity_order.index(d.severity) >= min_index
            ]

        return deltas

    def get_delta_statistics(self, entity: str) -> dict:
        """Get statistics about detected deltas for an entity."""
        deltas = self.get_recent_deltas(entity=entity)

        type_counts = {}
        severity_counts = {}

        for delta in deltas:
            type_name = delta.delta_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

            sev_name = delta.severity.value
            severity_counts[sev_name] = severity_counts.get(sev_name, 0) + 1

        return {
            "entity": entity,
            "total_deltas": len(deltas),
            "by_type": type_counts,
            "by_severity": severity_counts,
            "avg_confidence": (
                sum(d.confidence for d in deltas) / len(deltas)
                if deltas else 0
            ),
        }
