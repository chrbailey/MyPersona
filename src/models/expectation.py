"""
Expectation models representing what SHOULD be happening in discourse.

These models capture historical patterns and contextual triggers to predict
what normal discourse looks like, enabling detection of anomalies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional, Callable


class TriggerType(Enum):
    """Types of events that modify discourse expectations."""
    EARNINGS_RELEASE = "earnings_release"
    PRODUCT_LAUNCH = "product_launch"
    EXECUTIVE_CHANGE = "executive_change"
    REGULATORY_FILING = "regulatory_filing"
    NEWS_BREAKING = "news_breaking"
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    COMPETITOR_EVENT = "competitor_event"
    SEASONAL = "seasonal"
    CUSTOM = "custom"


class TimeWindow(Enum):
    """Standard time windows for expectation analysis."""
    HOUR = "hour"
    MARKET_SESSION = "market_session"  # 9:30 AM - 4:00 PM ET
    TRADING_DAY = "trading_day"
    WEEK = "week"
    EARNINGS_WINDOW = "earnings_window"  # Around earnings dates
    CUSTOM = "custom"


@dataclass
class ExpectedTopic:
    """
    A topic that is expected to be discussed for an entity.

    Includes baseline metrics and acceptable variance ranges.
    """
    topic_id: str
    topic_name: str

    # Expected metrics
    expected_mention_count: float  # Average mentions per time window
    mention_stddev: float  # Standard deviation for anomaly detection

    expected_sentiment: float  # Average sentiment (-1 to 1)
    sentiment_stddev: float

    # Confidence in expectation
    confidence: float = 0.8  # How confident we are in this expectation
    sample_size: int = 0  # Number of observations this is based on

    # Relationships
    usually_discussed_with: list[str] = field(default_factory=list)  # Other topic IDs

    # Absence significance
    absence_severity: float = 0.5  # 0-1, how significant is absence of this topic

    def is_anomalous_count(self, observed_count: int) -> tuple[bool, float]:
        """
        Check if observed count is anomalous.

        Returns (is_anomaly, z_score).
        """
        if self.mention_stddev == 0:
            return (False, 0.0)

        z_score = (observed_count - self.expected_mention_count) / self.mention_stddev
        # Anomaly if more than 2 standard deviations
        return (abs(z_score) > 2.0, z_score)

    def is_anomalous_sentiment(self, observed_sentiment: float) -> tuple[bool, float]:
        """
        Check if observed sentiment is anomalous.

        Returns (is_anomaly, z_score).
        """
        if self.sentiment_stddev == 0:
            return (False, 0.0)

        z_score = (observed_sentiment - self.expected_sentiment) / self.sentiment_stddev
        return (abs(z_score) > 2.0, z_score)


@dataclass
class ExpectedVoice:
    """
    An account expected to participate in discourse about an entity.

    Tracks who should be talking and what their typical patterns are.
    """
    account_id: str
    username: str

    # Expected activity
    expected_posts_per_day: float
    post_stddev: float

    # Typical behavior
    typical_topics: list[str] = field(default_factory=list)
    typical_sentiment: float = 0.0
    typical_response_time_minutes: float = 60.0  # How fast they usually respond

    # Activity windows
    active_hours_utc: list[int] = field(default_factory=list)  # Hours 0-23
    active_days: list[int] = field(default_factory=list)  # Days 0-6 (Mon-Sun)

    # Significance
    silence_severity: float = 0.5  # How significant is their silence
    is_key_voice: bool = False  # Executives, official accounts, etc.

    # Response patterns
    usually_responds_to: list[str] = field(default_factory=list)  # Account IDs
    usually_responds_about: list[str] = field(default_factory=list)  # Topic IDs

    def expected_to_be_active(self, check_time: datetime) -> bool:
        """Check if this voice is expected to be active at given time."""
        hour = check_time.hour
        day = check_time.weekday()

        hour_ok = not self.active_hours_utc or hour in self.active_hours_utc
        day_ok = not self.active_days or day in self.active_days

        return hour_ok and day_ok

    def silence_duration_hours(self, last_post: datetime, now: datetime) -> float:
        """Calculate how long this voice has been silent."""
        delta = now - last_post
        return delta.total_seconds() / 3600


@dataclass
class ContextTrigger:
    """
    An event that modifies discourse expectations.

    When these triggers fire, the baseline expectations are adjusted.
    """
    trigger_id: str
    trigger_type: TriggerType
    entity: str  # Which entity this trigger affects

    # Trigger conditions
    name: str  # Human-readable name
    description: str = ""

    # When this trigger is active
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # cron-like pattern

    # How this trigger modifies expectations
    volume_multiplier: float = 1.0  # 2.0 = expect 2x normal volume
    sentiment_shift: float = 0.0  # Expected sentiment change

    # New expected behaviors during trigger
    expected_new_topics: list[str] = field(default_factory=list)
    expected_new_voices: list[str] = field(default_factory=list)  # Account IDs
    required_voices: list[str] = field(default_factory=list)  # Must participate

    # Trigger confidence
    confidence: float = 0.8

    def is_active(self, check_time: datetime) -> bool:
        """Check if this trigger is currently active."""
        if self.start_time and check_time < self.start_time:
            return False
        if self.end_time and check_time > self.end_time:
            return False
        return True


@dataclass
class BaselinePattern:
    """
    Historical pattern for an entity's discourse.

    Built from historical data, represents what "normal" looks like.
    """
    entity: str
    time_window: TimeWindow

    # Volume patterns
    avg_posts_per_window: float = 0.0
    post_stddev: float = 0.0

    # By hour patterns (24 values, 0-23 UTC)
    hourly_volume_pattern: list[float] = field(default_factory=lambda: [0.0] * 24)

    # By day patterns (7 values, Mon-Sun)
    daily_volume_pattern: list[float] = field(default_factory=lambda: [0.0] * 7)

    # Sentiment patterns
    avg_sentiment: float = 0.0
    sentiment_stddev: float = 0.0

    # Topic patterns
    typical_topics: list[ExpectedTopic] = field(default_factory=list)
    topic_co_occurrence: dict[str, list[str]] = field(default_factory=dict)

    # Voice patterns
    typical_voices: list[ExpectedVoice] = field(default_factory=list)
    voice_response_patterns: dict[str, list[str]] = field(default_factory=dict)

    # Metadata
    sample_start: Optional[datetime] = None
    sample_end: Optional[datetime] = None
    sample_size: int = 0
    last_updated: Optional[datetime] = None

    def expected_volume_at(self, check_time: datetime) -> float:
        """Get expected volume for a specific time."""
        hour_factor = self.hourly_volume_pattern[check_time.hour]
        day_factor = self.daily_volume_pattern[check_time.weekday()]

        # Combined factor
        if hour_factor > 0 and day_factor > 0:
            avg_factor = (hour_factor + day_factor) / 2
        else:
            avg_factor = max(hour_factor, day_factor)

        return self.avg_posts_per_window * avg_factor


@dataclass
class DiscourseExpectation:
    """
    Complete expectation model for an entity at a point in time.

    Combines baseline patterns with active context triggers to produce
    what we expect discourse to look like RIGHT NOW.
    """
    expectation_id: str
    entity: str

    # Time window for this expectation
    window_start: datetime
    window_end: datetime

    # Base pattern (from historical analysis)
    baseline: BaselinePattern = field(default_factory=lambda: BaselinePattern(entity=""))

    # Active triggers modifying the baseline
    active_triggers: list[ContextTrigger] = field(default_factory=list)

    # Computed expectations (baseline + trigger modifications)

    # Volume expectations
    expected_post_count: float = 0.0
    post_count_range: tuple[float, float] = (0.0, 0.0)  # (min, max) acceptable

    # Topic expectations
    expected_topics: list[ExpectedTopic] = field(default_factory=list)
    required_topics: list[str] = field(default_factory=list)  # Must be discussed

    # Voice expectations
    expected_voices: list[ExpectedVoice] = field(default_factory=list)
    required_voices: list[str] = field(default_factory=list)  # Must participate

    # Sentiment expectations
    expected_sentiment: float = 0.0
    sentiment_range: tuple[float, float] = (-1.0, 1.0)  # (min, max) acceptable

    # Response pattern expectations
    expected_response_pairs: list[tuple[str, str]] = field(default_factory=list)

    # Confidence in overall expectation
    confidence: float = 0.8

    def get_expected_topic(self, topic_id: str) -> Optional[ExpectedTopic]:
        """Get expectation for a specific topic."""
        for topic in self.expected_topics:
            if topic.topic_id == topic_id:
                return topic
        return None

    def get_expected_voice(self, account_id: str) -> Optional[ExpectedVoice]:
        """Get expectation for a specific voice."""
        for voice in self.expected_voices:
            if voice.account_id == account_id:
                return voice
        return None

    def is_topic_required(self, topic_id: str) -> bool:
        """Check if a topic is required to be discussed."""
        return topic_id in self.required_topics

    def is_voice_required(self, account_id: str) -> bool:
        """Check if an account is required to participate."""
        return account_id in self.required_voices

    def apply_trigger(self, trigger: ContextTrigger) -> None:
        """Apply a context trigger to modify expectations."""
        self.active_triggers.append(trigger)

        # Modify volume expectation
        self.expected_post_count *= trigger.volume_multiplier
        min_posts, max_posts = self.post_count_range
        self.post_count_range = (
            min_posts * trigger.volume_multiplier,
            max_posts * trigger.volume_multiplier,
        )

        # Modify sentiment expectation
        self.expected_sentiment += trigger.sentiment_shift

        # Add required voices
        self.required_voices.extend(trigger.required_voices)

        # Add expected new topics
        for topic_id in trigger.expected_new_topics:
            if not self.get_expected_topic(topic_id):
                self.expected_topics.append(
                    ExpectedTopic(
                        topic_id=topic_id,
                        topic_name=topic_id,
                        expected_mention_count=10.0,  # Default expectation
                        mention_stddev=5.0,
                        expected_sentiment=0.0,
                        sentiment_stddev=0.3,
                        absence_severity=0.7,  # New topics are significant if missing
                    )
                )
