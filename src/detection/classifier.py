"""
Event classifier - classifies detected deltas into event types.

Takes delta clusters and produces market-relevant event classifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import logging

from ..models.delta import Delta, DeltaType, DeltaCluster, DeltaSeverity
from ..models.event import (
    DetectedEvent,
    EventType,
    EventSeverity,
    EventClassification,
)

logger = logging.getLogger(__name__)


# Mapping from delta patterns to event types
DELTA_EVENT_MAPPINGS = {
    # Single delta type mappings
    (DeltaType.TOPIC_ABSENCE,): [
        (EventType.INFORMATION_SUPPRESSION, 0.6),
        (EventType.PRE_ANNOUNCEMENT, 0.3),
    ],
    (DeltaType.VOICE_SILENCE,): [
        (EventType.INSIDER_ACTIVITY, 0.5),
        (EventType.DEPARTURE_SIGNAL, 0.3),
    ],
    (DeltaType.SENTIMENT_DECOUPLING,): [
        (EventType.CONFIDENCE_LOSS, 0.5),
        (EventType.SENTIMENT_SHIFT, 0.4),
    ],
    (DeltaType.VOLUME_COLLAPSE,): [
        (EventType.INFORMATION_SUPPRESSION, 0.4),
        (EventType.PRE_ANNOUNCEMENT, 0.4),
    ],
    (DeltaType.COORDINATED_SILENCE,): [
        (EventType.COORDINATION_DETECTED, 0.8),
        (EventType.INFORMATION_SUPPRESSION, 0.6),
    ],

    # Multi-delta patterns (more specific)
    (DeltaType.TOPIC_ABSENCE, DeltaType.VOICE_SILENCE): [
        (EventType.INFORMATION_SUPPRESSION, 0.8),
        (EventType.CRISIS_EMERGING, 0.5),
    ],
    (DeltaType.SENTIMENT_DECOUPLING, DeltaType.VOLUME_SPIKE): [
        (EventType.CRISIS_EMERGING, 0.7),
        (EventType.SENTIMENT_SHIFT, 0.5),
    ],
    (DeltaType.VOICE_SILENCE, DeltaType.SENTIMENT_DECOUPLING): [
        (EventType.INSIDER_ACTIVITY, 0.7),
        (EventType.CONFIDENCE_LOSS, 0.6),
    ],
}


class EventClassifier:
    """
    Classifies deltas and delta clusters into events.

    Uses pattern matching and optional LLM reasoning for classification.
    """

    def __init__(self, llm_client=None):
        """
        Initialize the classifier.

        Args:
            llm_client: Optional LLM client for enhanced reasoning
        """
        self.llm_client = llm_client

    def classify_delta(self, delta: Delta) -> EventClassification:
        """
        Classify a single delta.

        Returns event classification with probabilities.
        """
        delta_types = (delta.delta_type,)
        return self._classify_from_pattern(delta_types, [delta])

    def classify_cluster(self, cluster: DeltaCluster) -> EventClassification:
        """
        Classify a cluster of deltas.

        Clusters often produce higher confidence classifications.
        """
        # Get unique delta types in cluster
        delta_types = tuple(sorted(set(cluster.delta_types), key=lambda x: x.value))

        return self._classify_from_pattern(delta_types, cluster.deltas)

    def _classify_from_pattern(
        self,
        delta_types: tuple[DeltaType, ...],
        deltas: list[Delta],
    ) -> EventClassification:
        """Classify based on delta type pattern."""
        # Look for exact match first
        mappings = DELTA_EVENT_MAPPINGS.get(delta_types)

        if mappings is None:
            # Try subset matches
            for pattern, pattern_mappings in DELTA_EVENT_MAPPINGS.items():
                if all(dt in delta_types for dt in pattern):
                    mappings = pattern_mappings
                    break

        if mappings is None:
            # Default to anomaly
            return EventClassification(
                primary_type=EventType.ANOMALY_DETECTED,
                primary_confidence=0.3,
                type_probabilities={EventType.ANOMALY_DETECTED: 0.3},
                severity=EventSeverity.MINOR,
                severity_confidence=0.3,
                reasoning="Unrecognized delta pattern",
            )

        # Convert mappings to classification
        type_probs = {event_type: prob for event_type, prob in mappings}
        primary_type, primary_conf = mappings[0]

        # Boost confidence based on delta properties
        avg_confidence = sum(d.confidence for d in deltas) / len(deltas)
        primary_conf = min(0.95, primary_conf * (0.5 + avg_confidence * 0.5))

        # Determine severity
        severity = self._determine_severity(deltas)

        # Predict market direction based on event type
        predicted_direction, direction_conf = self._predict_direction(primary_type, deltas)

        return EventClassification(
            primary_type=primary_type,
            primary_confidence=primary_conf,
            type_probabilities=type_probs,
            severity=severity,
            severity_confidence=avg_confidence,
            predicted_direction=predicted_direction,
            direction_confidence=direction_conf,
            predicted_magnitude=self._predict_magnitude(severity),
            magnitude_confidence=0.5,
            reasoning=self._generate_reasoning(primary_type, deltas),
        )

    def _determine_severity(self, deltas: list[Delta]) -> EventSeverity:
        """Determine event severity from deltas."""
        # Get max severity from deltas
        severity_order = [
            DeltaSeverity.LOW,
            DeltaSeverity.MEDIUM,
            DeltaSeverity.HIGH,
            DeltaSeverity.CRITICAL,
        ]

        max_delta_severity = max(
            deltas,
            key=lambda d: severity_order.index(d.severity)
        ).severity

        # Map delta severity to event severity
        mapping = {
            DeltaSeverity.LOW: EventSeverity.MINOR,
            DeltaSeverity.MEDIUM: EventSeverity.NOTABLE,
            DeltaSeverity.HIGH: EventSeverity.SIGNIFICANT,
            DeltaSeverity.CRITICAL: EventSeverity.MAJOR,
        }

        # Boost if multiple deltas
        base_severity = mapping[max_delta_severity]

        if len(deltas) >= 3:
            # Multiple deltas = potentially more serious
            severity_order = list(EventSeverity)
            idx = severity_order.index(base_severity)
            if idx < len(severity_order) - 1:
                return severity_order[idx + 1]

        return base_severity

    def _predict_direction(
        self,
        event_type: EventType,
        deltas: list[Delta],
    ) -> tuple[Optional[str], float]:
        """Predict market direction based on event type."""
        # Default predictions by event type
        direction_map = {
            EventType.INFORMATION_SUPPRESSION: ("down", 0.6),
            EventType.CONFIDENCE_LOSS: ("down", 0.7),
            EventType.CRISIS_EMERGING: ("down", 0.8),
            EventType.DEPARTURE_SIGNAL: ("down", 0.5),
            EventType.INSIDER_ACTIVITY: ("volatile", 0.6),
            EventType.COORDINATION_DETECTED: ("volatile", 0.5),
            EventType.SENTIMENT_SHIFT: ("volatile", 0.5),
            EventType.PRE_ANNOUNCEMENT: ("volatile", 0.6),
            EventType.ANOMALY_DETECTED: (None, 0.3),
        }

        return direction_map.get(event_type, (None, 0.3))

    def _predict_magnitude(self, severity: EventSeverity) -> str:
        """Predict magnitude from severity."""
        mapping = {
            EventSeverity.NOISE: "negligible",
            EventSeverity.MINOR: "minor",
            EventSeverity.NOTABLE: "minor",
            EventSeverity.SIGNIFICANT: "moderate",
            EventSeverity.MAJOR: "major",
        }
        return mapping.get(severity, "minor")

    def _generate_reasoning(
        self,
        event_type: EventType,
        deltas: list[Delta],
    ) -> str:
        """Generate reasoning explanation for classification."""
        delta_descriptions = [d.description for d in deltas[:3]]
        delta_summary = "; ".join(delta_descriptions)

        reasoning_templates = {
            EventType.INFORMATION_SUPPRESSION: (
                f"Detected potential information suppression: {delta_summary}. "
                "This pattern often precedes negative news announcements."
            ),
            EventType.CONFIDENCE_LOSS: (
                f"Detected signals of confidence loss: {delta_summary}. "
                "Sentiment and/or voice patterns suggest insiders may be concerned."
            ),
            EventType.INSIDER_ACTIVITY: (
                f"Detected unusual insider behavior: {delta_summary}. "
                "Key voices are behaving differently than expected."
            ),
            EventType.CRISIS_EMERGING: (
                f"Detected early crisis signals: {delta_summary}. "
                "Multiple anomalies suggest a developing situation."
            ),
            EventType.PRE_ANNOUNCEMENT: (
                f"Detected pre-announcement quiet: {delta_summary}. "
                "Volume and topic patterns suggest announcement may be imminent."
            ),
        }

        return reasoning_templates.get(
            event_type,
            f"Anomaly detected: {delta_summary}"
        )

    def create_event(
        self,
        entity: str,
        deltas: list[Delta],
        cluster: Optional[DeltaCluster] = None,
    ) -> DetectedEvent:
        """
        Create a DetectedEvent from deltas.

        Args:
            entity: Entity the event is about
            deltas: Source deltas
            cluster: Optional cluster if deltas came from clustering

        Returns:
            DetectedEvent ready for market validation
        """
        if cluster:
            classification = self.classify_cluster(cluster)
            event = DetectedEvent.from_cluster(cluster, classification)
        elif len(deltas) == 1:
            classification = self.classify_delta(deltas[0])
            event = DetectedEvent.from_delta(deltas[0], classification, entity)
        else:
            # Multiple deltas but no cluster - create synthetic cluster
            synthetic_cluster = DeltaCluster(
                cluster_id=DeltaCluster.generate_id(),
                entity=entity,
            )
            for delta in deltas:
                synthetic_cluster.add_delta(delta)

            classification = self.classify_cluster(synthetic_cluster)
            event = DetectedEvent.from_cluster(synthetic_cluster, classification)

        # Set title based on event type
        event.title = self._generate_title(event.event_type, entity)

        # Extract related tickers (would come from entity config)
        # event.related_tickers = ...

        return event

    def _generate_title(self, event_type: EventType, entity: str) -> str:
        """Generate event title."""
        titles = {
            EventType.INFORMATION_SUPPRESSION: f"Potential information suppression for {entity}",
            EventType.CONFIDENCE_LOSS: f"Confidence signals weakening for {entity}",
            EventType.INSIDER_ACTIVITY: f"Unusual insider behavior detected for {entity}",
            EventType.CRISIS_EMERGING: f"Early crisis signals for {entity}",
            EventType.PRE_ANNOUNCEMENT: f"Pre-announcement quiet detected for {entity}",
            EventType.SENTIMENT_SHIFT: f"Sentiment shift detected for {entity}",
            EventType.COORDINATION_DETECTED: f"Coordinated activity detected for {entity}",
            EventType.DEPARTURE_SIGNAL: f"Potential departure signal for {entity}",
            EventType.ANOMALY_DETECTED: f"Anomaly detected for {entity}",
        }
        return titles.get(event_type, f"Event detected for {entity}")
