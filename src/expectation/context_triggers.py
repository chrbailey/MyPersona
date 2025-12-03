"""
Context triggers that modify discourse expectations.

Handles events like earnings releases, product launches, etc.
that change what we expect to see in discourse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable
from enum import Enum
import logging

from ..models.expectation import ContextTrigger, TriggerType

logger = logging.getLogger(__name__)


class TriggerSource(Enum):
    """Source of trigger information."""
    CALENDAR = "calendar"      # Pre-scheduled events
    NEWS = "news"              # Breaking news detection
    MARKET = "market"          # Market-derived events
    SOCIAL = "social"          # Social media-derived events
    MANUAL = "manual"          # Manually configured


@dataclass
class TriggerDefinition:
    """Definition of a trigger type and its effects."""
    trigger_type: TriggerType
    name: str

    # Default effects
    default_volume_multiplier: float = 1.0
    default_sentiment_shift: float = 0.0
    default_duration_hours: float = 24.0

    # Required responses
    typical_required_voices: list[str] = field(default_factory=list)
    typical_expected_topics: list[str] = field(default_factory=list)

    # Detection criteria
    detection_keywords: list[str] = field(default_factory=list)


# Pre-defined trigger types
TRIGGER_DEFINITIONS = {
    TriggerType.EARNINGS_RELEASE: TriggerDefinition(
        trigger_type=TriggerType.EARNINGS_RELEASE,
        name="Earnings Release",
        default_volume_multiplier=5.0,
        default_duration_hours=48.0,
        typical_expected_topics=["earnings", "revenue", "guidance", "eps"],
        detection_keywords=["earnings", "quarterly results", "Q1", "Q2", "Q3", "Q4"],
    ),
    TriggerType.PRODUCT_LAUNCH: TriggerDefinition(
        trigger_type=TriggerType.PRODUCT_LAUNCH,
        name="Product Launch",
        default_volume_multiplier=3.0,
        default_duration_hours=72.0,
        typical_expected_topics=["launch", "announcement", "new product"],
        detection_keywords=["launch", "announcing", "introducing", "unveil"],
    ),
    TriggerType.EXECUTIVE_CHANGE: TriggerDefinition(
        trigger_type=TriggerType.EXECUTIVE_CHANGE,
        name="Executive Change",
        default_volume_multiplier=4.0,
        default_sentiment_shift=-0.1,  # Usually initially negative
        default_duration_hours=168.0,  # Week-long impact
        typical_expected_topics=["ceo", "cfo", "departure", "appointment"],
        detection_keywords=["steps down", "appointed", "resignation", "new ceo"],
    ),
    TriggerType.REGULATORY_FILING: TriggerDefinition(
        trigger_type=TriggerType.REGULATORY_FILING,
        name="Regulatory Filing",
        default_volume_multiplier=2.0,
        default_duration_hours=24.0,
        typical_expected_topics=["sec", "filing", "disclosure"],
        detection_keywords=["8-K", "10-K", "10-Q", "SEC filing", "Form 4"],
    ),
    TriggerType.NEWS_BREAKING: TriggerDefinition(
        trigger_type=TriggerType.NEWS_BREAKING,
        name="Breaking News",
        default_volume_multiplier=10.0,
        default_duration_hours=12.0,
        detection_keywords=["breaking", "just in", "developing"],
    ),
    TriggerType.MARKET_OPEN: TriggerDefinition(
        trigger_type=TriggerType.MARKET_OPEN,
        name="Market Open",
        default_volume_multiplier=1.5,
        default_duration_hours=1.0,
    ),
    TriggerType.MARKET_CLOSE: TriggerDefinition(
        trigger_type=TriggerType.MARKET_CLOSE,
        name="Market Close",
        default_volume_multiplier=1.3,
        default_duration_hours=1.0,
    ),
}


class TriggerManager:
    """
    Manages context triggers that modify expectations.

    Responsibilities:
    - Store active and scheduled triggers
    - Detect triggers from news/social data
    - Query active triggers for a given entity/time
    """

    def __init__(self):
        # Active triggers by entity
        self.active_triggers: dict[str, list[ContextTrigger]] = {}

        # Scheduled triggers (future events)
        self.scheduled_triggers: list[ContextTrigger] = []

        # Detection callbacks
        self.on_trigger_detected: Optional[Callable[[ContextTrigger], None]] = None

    def add_trigger(self, trigger: ContextTrigger) -> None:
        """Add a trigger (active or scheduled)."""
        now = datetime.utcnow()

        if trigger.start_time and trigger.start_time > now:
            # Future trigger
            self.scheduled_triggers.append(trigger)
            logger.info(f"Scheduled trigger: {trigger.name} for {trigger.entity}")
        else:
            # Active trigger
            if trigger.entity not in self.active_triggers:
                self.active_triggers[trigger.entity] = []
            self.active_triggers[trigger.entity].append(trigger)
            logger.info(f"Activated trigger: {trigger.name} for {trigger.entity}")

    def get_active_triggers(
        self,
        entity: str,
        at_time: Optional[datetime] = None,
    ) -> list[ContextTrigger]:
        """Get all active triggers for an entity at a given time."""
        at_time = at_time or datetime.utcnow()

        # Check for newly activated scheduled triggers
        self._activate_scheduled_triggers(at_time)

        # Filter active triggers
        active = []
        for trigger in self.active_triggers.get(entity, []):
            if trigger.is_active(at_time):
                active.append(trigger)

        # Clean up expired triggers
        self._cleanup_expired_triggers(entity, at_time)

        return active

    def _activate_scheduled_triggers(self, now: datetime) -> None:
        """Move scheduled triggers to active when their time comes."""
        newly_active = []
        still_scheduled = []

        for trigger in self.scheduled_triggers:
            if trigger.start_time and trigger.start_time <= now:
                newly_active.append(trigger)
            else:
                still_scheduled.append(trigger)

        self.scheduled_triggers = still_scheduled

        for trigger in newly_active:
            self.add_trigger(trigger)

    def _cleanup_expired_triggers(self, entity: str, now: datetime) -> None:
        """Remove expired triggers."""
        if entity not in self.active_triggers:
            return

        self.active_triggers[entity] = [
            t for t in self.active_triggers[entity]
            if t.is_active(now)
        ]

    def detect_trigger_from_text(
        self,
        text: str,
        entity: str,
        source: TriggerSource = TriggerSource.NEWS,
    ) -> Optional[ContextTrigger]:
        """
        Detect if text indicates a trigger event.

        Returns a trigger if detected, None otherwise.
        """
        text_lower = text.lower()

        for trigger_type, definition in TRIGGER_DEFINITIONS.items():
            for keyword in definition.detection_keywords:
                if keyword.lower() in text_lower:
                    trigger = self._create_trigger_from_detection(
                        trigger_type=trigger_type,
                        definition=definition,
                        entity=entity,
                        source_text=text,
                    )

                    if self.on_trigger_detected:
                        self.on_trigger_detected(trigger)

                    return trigger

        return None

    def _create_trigger_from_detection(
        self,
        trigger_type: TriggerType,
        definition: TriggerDefinition,
        entity: str,
        source_text: str,
    ) -> ContextTrigger:
        """Create a trigger from detection."""
        now = datetime.utcnow()

        return ContextTrigger(
            trigger_id=f"trigger_{entity}_{now.timestamp():.0f}",
            trigger_type=trigger_type,
            entity=entity,
            name=definition.name,
            description=f"Detected from: {source_text[:100]}...",
            start_time=now,
            end_time=now + timedelta(hours=definition.default_duration_hours),
            volume_multiplier=definition.default_volume_multiplier,
            sentiment_shift=definition.default_sentiment_shift,
            expected_new_topics=definition.typical_expected_topics,
        )

    def create_earnings_trigger(
        self,
        entity: str,
        release_time: datetime,
        tickers: Optional[list[str]] = None,
    ) -> ContextTrigger:
        """Create a pre-scheduled earnings trigger."""
        definition = TRIGGER_DEFINITIONS[TriggerType.EARNINGS_RELEASE]

        # Earnings window: 2 hours before to 48 hours after
        start_time = release_time - timedelta(hours=2)
        end_time = release_time + timedelta(hours=48)

        return ContextTrigger(
            trigger_id=f"earnings_{entity}_{release_time.date().isoformat()}",
            trigger_type=TriggerType.EARNINGS_RELEASE,
            entity=entity,
            name=f"{entity} Earnings Release",
            description=f"Scheduled earnings release at {release_time}",
            start_time=start_time,
            end_time=end_time,
            volume_multiplier=definition.default_volume_multiplier,
            expected_new_topics=["earnings", "revenue", "eps", "guidance", "outlook"],
            required_voices=[],  # Would be populated with known IR accounts
        )

    def create_market_hours_triggers(self, entity: str) -> list[ContextTrigger]:
        """Create recurring market hours triggers."""
        # This would create daily triggers for market open/close
        # For simplicity, returning empty list - full implementation
        # would handle recurring schedules
        return []

    def get_upcoming_triggers(
        self,
        entity: str,
        hours_ahead: int = 24,
    ) -> list[ContextTrigger]:
        """Get triggers scheduled for the near future."""
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours_ahead)

        return [
            t for t in self.scheduled_triggers
            if t.entity == entity
            and t.start_time
            and t.start_time <= cutoff
        ]

    def summarize_active_triggers(self, entity: str) -> dict:
        """Get summary of active triggers for an entity."""
        triggers = self.get_active_triggers(entity)

        if not triggers:
            return {
                "entity": entity,
                "active_count": 0,
                "triggers": [],
                "combined_volume_multiplier": 1.0,
                "combined_sentiment_shift": 0.0,
            }

        # Combine effects (multiplicative for volume, additive for sentiment)
        combined_volume = 1.0
        combined_sentiment = 0.0
        trigger_summaries = []

        for trigger in triggers:
            combined_volume *= trigger.volume_multiplier
            combined_sentiment += trigger.sentiment_shift
            trigger_summaries.append({
                "type": trigger.trigger_type.value,
                "name": trigger.name,
                "ends_at": trigger.end_time.isoformat() if trigger.end_time else None,
            })

        return {
            "entity": entity,
            "active_count": len(triggers),
            "triggers": trigger_summaries,
            "combined_volume_multiplier": combined_volume,
            "combined_sentiment_shift": combined_sentiment,
        }
