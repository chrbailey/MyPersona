"""
Event models representing detected significant occurrences.

Events are the output of the system - derived from deltas and validated against markets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import uuid


class EventType(Enum):
    """Types of events we can detect from discourse deltas."""

    # Information-related events
    INFORMATION_LEAK = "information_leak"         # Someone knows something
    INFORMATION_SUPPRESSION = "information_suppression"  # Coordinated non-disclosure

    # Sentiment-related events
    SENTIMENT_SHIFT = "sentiment_shift"           # Major change in how entity is perceived
    CONFIDENCE_LOSS = "confidence_loss"           # Insiders losing confidence

    # Actor-related events
    INSIDER_ACTIVITY = "insider_activity"         # Unusual insider behavior
    COORDINATION_DETECTED = "coordination_detected"  # Coordinated action

    # Market-related events
    PRE_ANNOUNCEMENT = "pre_announcement"         # Something about to be announced
    CRISIS_EMERGING = "crisis_emerging"           # Problem developing

    # Relationship events
    RELATIONSHIP_CHANGE = "relationship_change"   # Key relationship shifting
    DEPARTURE_SIGNAL = "departure_signal"         # Someone about to leave

    # Unknown/exploratory
    ANOMALY_DETECTED = "anomaly_detected"         # Something unusual, unclear what


class EventSeverity(Enum):
    """Severity/importance of a detected event."""
    NOISE = "noise"         # Probably nothing
    MINOR = "minor"         # Small blip
    NOTABLE = "notable"     # Worth watching
    SIGNIFICANT = "significant"  # Likely market-moving
    MAJOR = "major"         # High confidence market event


@dataclass
class EventClassification:
    """
    Classification output from the event classifier.

    Provides probabilities across event types.
    """
    primary_type: EventType
    primary_confidence: float

    # Alternative classifications with probabilities
    type_probabilities: dict[EventType, float] = field(default_factory=dict)

    # Severity assessment
    severity: EventSeverity = EventSeverity.NOTABLE
    severity_confidence: float = 0.5

    # Market impact prediction
    predicted_direction: Optional[str] = None  # "up", "down", "volatile", "neutral"
    direction_confidence: float = 0.0
    predicted_magnitude: Optional[str] = None  # "minor", "moderate", "major"
    magnitude_confidence: float = 0.0

    # Timing prediction
    predicted_timing: Optional[str] = None  # "immediate", "hours", "days"
    timing_confidence: float = 0.0

    # Explanation
    reasoning: str = ""

    @property
    def is_tradeable(self) -> bool:
        """Whether this classification suggests tradeable signal."""
        return (
            self.severity in [EventSeverity.SIGNIFICANT, EventSeverity.MAJOR]
            and self.primary_confidence > 0.7
            and self.direction_confidence > 0.6
        )


@dataclass
class DetectedEvent:
    """
    A detected event derived from discourse analysis.

    This is the main output of the system - something we believe is happening
    based on the deltas we've observed.
    """
    event_id: str
    entity: str

    # Classification
    event_type: EventType
    classification: EventClassification

    # Timing
    detected_at: datetime
    event_window_start: datetime
    event_window_end: datetime

    # Source deltas
    source_deltas: list[str] = field(default_factory=list)  # Delta IDs
    source_cluster: Optional[str] = None  # Cluster ID if from cluster

    # Event description
    title: str = ""
    description: str = ""

    # Severity and confidence
    severity: EventSeverity = EventSeverity.NOTABLE
    confidence: float = 0.5

    # Evidence summary
    evidence_summary: list[str] = field(default_factory=list)
    key_signals: list[str] = field(default_factory=list)

    # Predictions
    market_prediction: dict[str, Any] = field(default_factory=dict)

    # Related entities
    related_entities: list[str] = field(default_factory=list)
    related_tickers: list[str] = field(default_factory=list)

    # Status
    status: str = "detected"  # "detected", "tracking", "validated", "invalidated"

    # Validation (filled in by market tracker)
    validated_at: Optional[datetime] = None
    validation_result: Optional[dict] = None
    prediction_correct: Optional[bool] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def generate_id(cls) -> str:
        """Generate a unique event ID."""
        return f"event_{uuid.uuid4().hex[:12]}"

    @classmethod
    def from_delta(
        cls,
        delta: Any,  # Delta type
        classification: EventClassification,
        entity: str,
    ) -> DetectedEvent:
        """Create an event from a single delta."""
        return cls(
            event_id=cls.generate_id(),
            entity=entity,
            event_type=classification.primary_type,
            classification=classification,
            detected_at=datetime.utcnow(),
            event_window_start=delta.window_start,
            event_window_end=delta.window_end,
            source_deltas=[delta.delta_id],
            severity=classification.severity,
            confidence=classification.primary_confidence,
            description=delta.description,
        )

    @classmethod
    def from_cluster(
        cls,
        cluster: Any,  # DeltaCluster type
        classification: EventClassification,
    ) -> DetectedEvent:
        """Create an event from a delta cluster."""
        return cls(
            event_id=cls.generate_id(),
            entity=cluster.entity,
            event_type=classification.primary_type,
            classification=classification,
            detected_at=datetime.utcnow(),
            event_window_start=cluster.first_delta_time or datetime.utcnow(),
            event_window_end=cluster.last_delta_time or datetime.utcnow(),
            source_deltas=[d.delta_id for d in cluster.deltas],
            source_cluster=cluster.cluster_id,
            severity=classification.severity,
            confidence=classification.primary_confidence * cluster.reinforcement_score,
            description=cluster.summary,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "entity": self.entity,
            "event_type": self.event_type.value,
            "detected_at": self.detected_at.isoformat(),
            "severity": self.severity.value,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "market_prediction": self.market_prediction,
            "status": self.status,
            "prediction_correct": self.prediction_correct,
        }

    def to_alert(self) -> dict:
        """Format as an alert for notification."""
        return {
            "event_id": self.event_id,
            "entity": self.entity,
            "type": self.event_type.value,
            "severity": self.severity.value,
            "confidence": f"{self.confidence:.0%}",
            "title": self.title,
            "summary": self.description[:200],
            "tickers": self.related_tickers,
            "prediction": self.market_prediction,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class EventTimeline:
    """
    Timeline of events for an entity.

    Tracks the evolution of events over time for pattern analysis.
    """
    entity: str
    events: list[DetectedEvent] = field(default_factory=list)

    # Timeline bounds
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Summary statistics
    total_events: int = 0
    events_by_type: dict[EventType, int] = field(default_factory=dict)
    events_by_severity: dict[EventSeverity, int] = field(default_factory=dict)

    # Validation statistics
    validated_events: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0

    def add_event(self, event: DetectedEvent) -> None:
        """Add an event to the timeline."""
        self.events.append(event)
        self.total_events += 1

        # Update type counts
        self.events_by_type[event.event_type] = (
            self.events_by_type.get(event.event_type, 0) + 1
        )

        # Update severity counts
        self.events_by_severity[event.severity] = (
            self.events_by_severity.get(event.severity, 0) + 1
        )

        # Update bounds
        if self.start_time is None or event.detected_at < self.start_time:
            self.start_time = event.detected_at
        if self.end_time is None or event.detected_at > self.end_time:
            self.end_time = event.detected_at

        # Update validation stats
        if event.prediction_correct is not None:
            self.validated_events += 1
            if event.prediction_correct:
                self.correct_predictions += 1
            self.accuracy = self.correct_predictions / self.validated_events

    def get_recent(self, hours: int = 24) -> list[DetectedEvent]:
        """Get events from the last N hours."""
        cutoff = datetime.utcnow().replace(
            hour=datetime.utcnow().hour - hours
        )
        return [e for e in self.events if e.detected_at >= cutoff]

    def get_by_type(self, event_type: EventType) -> list[DetectedEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_high_confidence(self, threshold: float = 0.8) -> list[DetectedEvent]:
        """Get high-confidence events."""
        return [e for e in self.events if e.confidence >= threshold]
