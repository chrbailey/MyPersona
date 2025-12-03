"""
Delta models representing gaps between expected and observed discourse.

The core innovation: detecting what ISN'T being said that SHOULD be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import uuid


class DeltaType(Enum):
    """Types of discourse deltas (gaps) we can detect."""

    # Content-based deltas
    TOPIC_ABSENCE = "topic_absence"           # Expected topic not mentioned
    TOPIC_SUBSTITUTION = "topic_substitution" # Discussing B instead of expected A

    # Voice-based deltas
    VOICE_SILENCE = "voice_silence"           # Expected voice not participating
    UNEXPECTED_VOICE = "unexpected_voice"     # New voice that shouldn't be there

    # Sentiment-based deltas
    SENTIMENT_DECOUPLING = "sentiment_decoupling"  # Tone doesn't match expected
    TONE_SHIFT = "tone_shift"                      # Sudden tone change

    # Network-based deltas
    NETWORK_BREAK = "network_break"           # Expected responses not happening
    RESPONSE_DELAY = "response_delay"         # Slower responses than expected

    # Volume-based deltas
    VOLUME_COLLAPSE = "volume_collapse"       # Much less activity than expected
    VOLUME_SPIKE = "volume_spike"             # Much more activity than expected

    # Temporal deltas
    TEMPORAL_SHIFT = "temporal_shift"         # Activity at unusual times

    # Composite deltas
    COORDINATED_SILENCE = "coordinated_silence"  # Multiple voices go quiet together


class DeltaSeverity(Enum):
    """Severity/significance of a detected delta."""
    LOW = "low"           # Minor deviation, may be noise
    MEDIUM = "medium"     # Notable deviation, worth tracking
    HIGH = "high"         # Significant deviation, likely meaningful
    CRITICAL = "critical" # Major deviation, immediate attention


@dataclass
class Delta:
    """
    Base class for a detected discourse delta.

    Represents a gap between what IS and what SHOULD BE in discourse.
    """
    delta_id: str
    delta_type: DeltaType

    # What entity/topic this delta is about
    entity: str

    # When detected
    detected_at: datetime

    # Time window the delta covers
    window_start: datetime
    window_end: datetime

    # Severity and confidence
    severity: DeltaSeverity = DeltaSeverity.MEDIUM
    confidence: float = 0.5  # 0-1, how confident we are this is real

    # The delta itself
    expected_value: Any = None  # What we expected
    observed_value: Any = None  # What we observed
    deviation_score: float = 0.0  # Normalized measure of deviation

    # Human-readable description
    description: str = ""

    # Evidence supporting this delta
    evidence: list[str] = field(default_factory=list)  # Post IDs, metrics, etc.

    # Related deltas (often deltas co-occur)
    related_deltas: list[str] = field(default_factory=list)  # Delta IDs

    # Market validation (filled in later)
    validated: bool = False
    validation_outcome: Optional[str] = None

    @classmethod
    def generate_id(cls) -> str:
        """Generate a unique delta ID."""
        return f"delta_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "delta_id": self.delta_id,
            "delta_type": self.delta_type.value,
            "entity": self.entity,
            "detected_at": self.detected_at.isoformat(),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "severity": self.severity.value,
            "confidence": self.confidence,
            "expected_value": str(self.expected_value),
            "observed_value": str(self.observed_value),
            "deviation_score": self.deviation_score,
            "description": self.description,
        }


@dataclass
class TopicAbsenceDelta(Delta):
    """
    Delta indicating an expected topic is not being discussed.

    Key signal: When people stop talking about something they usually discuss.
    """
    delta_type: DeltaType = field(default=DeltaType.TOPIC_ABSENCE, init=False)

    # Topic details
    missing_topic_id: str = ""
    missing_topic_name: str = ""

    # Expected vs observed
    expected_mentions: float = 0.0
    observed_mentions: int = 0

    # Historical context
    baseline_mentions: float = 0.0
    last_mentioned: Optional[datetime] = None
    days_since_mention: int = 0

    # Significance factors
    topic_importance: float = 0.5  # How important is this topic normally
    is_required_topic: bool = False  # Was this a required topic for the context

    def __post_init__(self):
        self.expected_value = self.expected_mentions
        self.observed_value = self.observed_mentions
        if self.expected_mentions > 0:
            self.deviation_score = 1.0 - (self.observed_mentions / self.expected_mentions)
        self.description = (
            f"Topic '{self.missing_topic_name}' not mentioned for {self.entity}. "
            f"Expected ~{self.expected_mentions:.0f} mentions, saw {self.observed_mentions}."
        )


@dataclass
class VoiceSilenceDelta(Delta):
    """
    Delta indicating an expected voice is not participating.

    Key signal: When someone who usually talks goes quiet.
    """
    delta_type: DeltaType = field(default=DeltaType.VOICE_SILENCE, init=False)

    # Account details
    silent_account_id: str = ""
    silent_username: str = ""
    account_type: str = ""

    # Silence metrics
    silence_hours: float = 0.0
    expected_posts: float = 0.0
    observed_posts: int = 0

    # Context
    last_post_time: Optional[datetime] = None
    typical_post_frequency: float = 0.0  # Posts per day

    # Significance
    is_key_voice: bool = False
    influence_score: float = 0.0
    was_expected_to_respond: bool = False
    response_to_event: Optional[str] = None  # What event were they expected to respond to

    def __post_init__(self):
        self.expected_value = self.expected_posts
        self.observed_value = self.observed_posts
        if self.expected_posts > 0:
            self.deviation_score = 1.0 - (self.observed_posts / self.expected_posts)

        role = f" ({self.account_type})" if self.account_type else ""
        self.description = (
            f"@{self.silent_username}{role} silent for {self.silence_hours:.1f} hours. "
            f"Expected ~{self.expected_posts:.0f} posts, saw {self.observed_posts}."
        )


@dataclass
class SentimentDecouplingDelta(Delta):
    """
    Delta indicating sentiment doesn't match what context suggests.

    Key signal: Positive news but negative undertone (or vice versa).
    """
    delta_type: DeltaType = field(default=DeltaType.SENTIMENT_DECOUPLING, init=False)

    # Sentiment details
    expected_sentiment: float = 0.0
    observed_sentiment: float = 0.0
    sentiment_gap: float = 0.0

    # Context that set expectation
    context_trigger: str = ""  # What event/news set the expectation
    context_sentiment: float = 0.0  # What sentiment the context suggests

    # Statistical significance
    z_score: float = 0.0
    is_statistically_significant: bool = False

    # Tone markers
    observed_tones: list[str] = field(default_factory=list)
    expected_tones: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.expected_value = self.expected_sentiment
        self.observed_value = self.observed_sentiment
        self.sentiment_gap = self.observed_sentiment - self.expected_sentiment
        self.deviation_score = abs(self.sentiment_gap) / 2.0  # Normalize to 0-1

        direction = "positive" if self.expected_sentiment > 0 else "negative"
        actual = "negative" if self.observed_sentiment < 0 else "positive"
        self.description = (
            f"Sentiment mismatch for {self.entity}: expected {direction} "
            f"({self.expected_sentiment:.2f}), observed {actual} "
            f"({self.observed_sentiment:.2f}). Gap: {self.sentiment_gap:.2f}"
        )


@dataclass
class NetworkBreakDelta(Delta):
    """
    Delta indicating expected response patterns are broken.

    Key signal: A usually responds to B, but didn't this time.
    """
    delta_type: DeltaType = field(default=DeltaType.NETWORK_BREAK, init=False)

    # Response pattern details
    expected_responder_id: str = ""
    expected_responder_name: str = ""
    trigger_post_id: str = ""
    trigger_author: str = ""

    # Time details
    trigger_post_time: Optional[datetime] = None
    expected_response_window_hours: float = 2.0
    wait_time_hours: float = 0.0

    # Historical pattern
    historical_response_rate: float = 0.0  # What % of time do they respond
    avg_response_time_minutes: float = 0.0

    # Content context
    trigger_topic: str = ""
    trigger_sentiment: float = 0.0

    def __post_init__(self):
        self.expected_value = "response"
        self.observed_value = "no response"
        self.deviation_score = min(1.0, self.wait_time_hours / self.expected_response_window_hours)

        self.description = (
            f"@{self.expected_responder_name} did not respond to @{self.trigger_author}'s post "
            f"about {self.trigger_topic}. Usually responds {self.historical_response_rate:.0%} "
            f"of the time within {self.avg_response_time_minutes:.0f} minutes."
        )


@dataclass
class VolumeAnomalyDelta(Delta):
    """
    Delta indicating unusual volume of discourse.

    Can be either volume collapse (suspiciously quiet) or spike (unusually loud).
    """
    delta_type: DeltaType = field(default=DeltaType.VOLUME_COLLAPSE, init=False)

    # Volume details
    expected_volume: float = 0.0
    observed_volume: int = 0
    volume_ratio: float = 0.0  # observed / expected

    # Statistical context
    baseline_volume: float = 0.0
    volume_stddev: float = 0.0
    z_score: float = 0.0

    # Is this a collapse or spike?
    is_collapse: bool = True

    # Breakdown
    unique_authors: int = 0
    expected_authors: float = 0.0

    def __post_init__(self):
        self.expected_value = self.expected_volume
        self.observed_value = self.observed_volume

        if self.expected_volume > 0:
            self.volume_ratio = self.observed_volume / self.expected_volume
            self.deviation_score = abs(1.0 - self.volume_ratio)

        self.is_collapse = self.volume_ratio < 0.5
        self.delta_type = (
            DeltaType.VOLUME_COLLAPSE if self.is_collapse
            else DeltaType.VOLUME_SPIKE
        )

        direction = "below" if self.is_collapse else "above"
        self.description = (
            f"Volume {direction} expectations for {self.entity}: "
            f"expected ~{self.expected_volume:.0f}, observed {self.observed_volume} "
            f"({self.volume_ratio:.1%} of expected). Z-score: {self.z_score:.2f}"
        )


@dataclass
class CoordinatedSilenceDelta(Delta):
    """
    Delta indicating multiple expected voices went quiet together.

    Key signal: Coordinated non-discussion is as informative as coordinated messaging.
    """
    delta_type: DeltaType = field(default=DeltaType.COORDINATED_SILENCE, init=False)

    # Silent accounts
    silent_accounts: list[str] = field(default_factory=list)  # Account IDs
    silent_usernames: list[str] = field(default_factory=list)

    # Coordination metrics
    silence_start_times: list[datetime] = field(default_factory=list)
    time_spread_hours: float = 0.0  # How close together did they go quiet

    # Commonalities
    common_topics: list[str] = field(default_factory=list)  # Topics they all usually discuss
    common_relationships: list[str] = field(default_factory=list)  # Shared connections

    # Significance
    is_same_org: bool = False
    coordination_score: float = 0.0  # 0-1, how coordinated does this look

    def __post_init__(self):
        self.expected_value = f"{len(self.silent_accounts)} voices active"
        self.observed_value = "all silent"
        self.deviation_score = self.coordination_score

        names = ", ".join(self.silent_usernames[:3])
        if len(self.silent_usernames) > 3:
            names += f", and {len(self.silent_usernames) - 3} others"

        self.description = (
            f"Coordinated silence detected: {names} all went quiet "
            f"within {self.time_spread_hours:.1f} hours about {self.entity}. "
            f"Coordination score: {self.coordination_score:.2f}"
        )


@dataclass
class DeltaCluster:
    """
    A group of related deltas that together suggest something significant.

    Multiple weak signals can combine into a strong signal.
    """
    cluster_id: str
    entity: str

    # Deltas in this cluster
    deltas: list[Delta] = field(default_factory=list)
    delta_types: list[DeltaType] = field(default_factory=list)

    # Cluster timing
    first_delta_time: Optional[datetime] = None
    last_delta_time: Optional[datetime] = None

    # Combined significance
    combined_severity: DeltaSeverity = DeltaSeverity.MEDIUM
    combined_confidence: float = 0.0
    reinforcement_score: float = 0.0  # How much do deltas reinforce each other

    # Narrative
    summary: str = ""

    @classmethod
    def generate_id(cls) -> str:
        """Generate a unique cluster ID."""
        return f"cluster_{uuid.uuid4().hex[:12]}"

    def add_delta(self, delta: Delta) -> None:
        """Add a delta to this cluster."""
        self.deltas.append(delta)
        self.delta_types.append(delta.delta_type)

        if self.first_delta_time is None or delta.detected_at < self.first_delta_time:
            self.first_delta_time = delta.detected_at
        if self.last_delta_time is None or delta.detected_at > self.last_delta_time:
            self.last_delta_time = delta.detected_at

        self._recalculate_significance()

    def _recalculate_significance(self) -> None:
        """Recalculate cluster significance based on contained deltas."""
        if not self.deltas:
            return

        # Average confidence weighted by severity
        severity_weights = {
            DeltaSeverity.LOW: 1,
            DeltaSeverity.MEDIUM: 2,
            DeltaSeverity.HIGH: 3,
            DeltaSeverity.CRITICAL: 4,
        }

        total_weight = 0
        weighted_confidence = 0
        max_severity = DeltaSeverity.LOW

        for delta in self.deltas:
            weight = severity_weights[delta.severity]
            total_weight += weight
            weighted_confidence += delta.confidence * weight

            if severity_weights[delta.severity] > severity_weights[max_severity]:
                max_severity = delta.severity

        self.combined_confidence = weighted_confidence / total_weight if total_weight > 0 else 0

        # Boost severity if multiple delta types present
        unique_types = len(set(self.delta_types))
        if unique_types >= 3 and max_severity != DeltaSeverity.CRITICAL:
            max_severity = DeltaSeverity(
                list(DeltaSeverity)[min(
                    list(DeltaSeverity).index(max_severity) + 1,
                    len(list(DeltaSeverity)) - 1
                )]
            )

        self.combined_severity = max_severity
        self.reinforcement_score = min(1.0, unique_types / 4)  # Cap at 1.0
