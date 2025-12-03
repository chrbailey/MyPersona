"""
Delta-market correlator - finds patterns between discourse deltas and market movements.

The core validation engine: do our detected deltas actually predict price moves?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging
from collections import defaultdict

from ..models.delta import Delta, DeltaType
from ..models.market import (
    PriceMovement,
    PredictionOutcome,
    ValidationResult,
    MarketCorrelation,
    MarketDirection,
)
from ..models.event import DetectedEvent
from .market_tracker import MarketTracker

logger = logging.getLogger(__name__)


@dataclass
class CorrelationConfig:
    """Configuration for correlation analysis."""
    # Time horizons to check (in hours)
    time_horizons: list[float] = field(default_factory=lambda: [1, 4, 24, 168])

    # Minimum sample size for significance
    min_samples: int = 30

    # Significance threshold
    significance_threshold: float = 0.4  # 40% better than random


class DeltaMarketCorrelator:
    """
    Correlates discourse deltas with market movements.

    This is the proof mechanism: track whether detected deltas
    actually precede market movements.
    """

    def __init__(
        self,
        market_tracker: MarketTracker,
        config: Optional[CorrelationConfig] = None,
    ):
        self.market_tracker = market_tracker
        self.config = config or CorrelationConfig()

        # Pending validations (events waiting to be validated)
        self.pending_validations: list[tuple[DetectedEvent, datetime]] = []

        # Completed validations
        self.validations: list[ValidationResult] = []

        # Correlation statistics by delta type
        self.correlations: dict[DeltaType, MarketCorrelation] = {}

    async def track_event(self, event: DetectedEvent) -> None:
        """
        Start tracking an event for validation.

        Records the event and schedules validation at multiple time horizons.
        """
        logger.info(f"Tracking event {event.event_id} for validation")

        # Record prediction time
        self.pending_validations.append((event, datetime.utcnow()))

        # Ensure tickers are being tracked
        for ticker in event.related_tickers:
            self.market_tracker.track_ticker(ticker)

    async def validate_pending(self) -> list[ValidationResult]:
        """
        Validate events that have passed their time horizons.

        Returns newly completed validations.
        """
        now = datetime.utcnow()
        completed = []
        still_pending = []

        for event, tracked_at in self.pending_validations:
            # Check if enough time has passed for validation
            hours_elapsed = (now - tracked_at).total_seconds() / 3600

            if hours_elapsed >= max(self.config.time_horizons):
                # Full validation possible
                result = await self._validate_event(event, tracked_at)
                self.validations.append(result)
                completed.append(result)

                # Update correlation statistics
                self._update_correlations(event, result)
            else:
                still_pending.append((event, tracked_at))

        self.pending_validations = still_pending

        return completed

    async def _validate_event(
        self,
        event: DetectedEvent,
        tracked_at: datetime,
    ) -> ValidationResult:
        """Validate an event against actual market movements."""
        result = ValidationResult(
            validation_id=ValidationResult.generate_id(),
            event_id=event.event_id,
            entity=event.entity,
            tickers=event.related_tickers,
            event_type=event.event_type.value,
            event_severity=event.severity.value,
            event_confidence=event.confidence,
            detected_at=event.detected_at,
        )

        for ticker in event.related_tickers:
            outcome = await self._create_outcome(
                event=event,
                ticker=ticker,
                tracked_at=tracked_at,
            )
            if outcome:
                result.outcomes[ticker] = outcome

        result.calculate_aggregate_results()

        # Calculate lead time
        if result.validated and result.outcomes:
            # Find earliest significant move
            earliest_move = None
            for outcome in result.outcomes.values():
                if outcome.best_horizon:
                    move_time = self._horizon_to_hours(outcome.best_horizon)
                    if earliest_move is None or move_time < earliest_move:
                        earliest_move = move_time

            if earliest_move:
                result.lead_time_minutes = earliest_move * 60

        return result

    async def _create_outcome(
        self,
        event: DetectedEvent,
        ticker: str,
        tracked_at: datetime,
    ) -> Optional[PredictionOutcome]:
        """Create prediction outcome for a ticker."""
        classification = event.classification

        outcome = PredictionOutcome(
            prediction_id=PredictionOutcome.generate_id(),
            event_id=event.event_id,
            ticker=ticker,
            predicted_at=tracked_at,
            predicted_direction=self._string_to_direction(
                classification.predicted_direction
            ),
            predicted_magnitude=classification.predicted_magnitude or "minor",
            predicted_timing="1d",  # Default
            prediction_confidence=classification.direction_confidence,
        )

        # Get actual movements at each horizon
        for hours in self.config.time_horizons:
            end_time = tracked_at + timedelta(hours=hours)

            if end_time > datetime.utcnow():
                continue  # Not yet available

            movement = await self.market_tracker.calculate_movement(
                ticker=ticker,
                start_time=tracked_at,
                end_time=end_time,
            )

            if movement:
                horizon_name = self._hours_to_horizon(hours)
                setattr(outcome, f"outcome_{horizon_name}", movement)

                # Check direction correctness
                predicted_dir = outcome.predicted_direction
                actual_dir = movement.direction

                direction_correct = (
                    predicted_dir == actual_dir or
                    (predicted_dir == MarketDirection.VOLATILE and
                     actual_dir in [MarketDirection.UP, MarketDirection.DOWN])
                )
                setattr(outcome, f"direction_correct_{horizon_name}", direction_correct)

                # Check magnitude correctness
                predicted_mag = outcome.predicted_magnitude
                actual_mag = movement.magnitude.value

                magnitude_correct = predicted_mag == actual_mag
                setattr(outcome, f"magnitude_correct_{horizon_name}", magnitude_correct)

        outcome.calculate_scores()
        return outcome

    def _update_correlations(
        self,
        event: DetectedEvent,
        result: ValidationResult,
    ) -> None:
        """Update correlation statistics with new validation."""
        # Get delta types from the event
        for delta_id in event.source_deltas:
            # Would look up delta type from storage
            # For now, use event type as proxy
            pass

        # Update overall outcome tracking
        for outcome in result.outcomes.values():
            # This would update running statistics
            pass

    def _string_to_direction(self, direction: Optional[str]) -> MarketDirection:
        """Convert string direction to enum."""
        if direction == "up":
            return MarketDirection.UP
        elif direction == "down":
            return MarketDirection.DOWN
        elif direction == "volatile":
            return MarketDirection.VOLATILE
        return MarketDirection.FLAT

    def _hours_to_horizon(self, hours: float) -> str:
        """Convert hours to horizon string."""
        if hours <= 1:
            return "1h"
        elif hours <= 4:
            return "4h"
        elif hours <= 24:
            return "1d"
        else:
            return "1w"

    def _horizon_to_hours(self, horizon: str) -> float:
        """Convert horizon string to hours."""
        mapping = {"1h": 1, "4h": 4, "1d": 24, "1w": 168}
        return mapping.get(horizon, 24)

    def get_correlation_summary(self) -> dict:
        """Get summary of correlation statistics."""
        total_validations = len(self.validations)
        validated_correct = sum(1 for v in self.validations if v.validated)

        if total_validations == 0:
            accuracy = 0
        else:
            accuracy = validated_correct / total_validations

        return {
            "total_validations": total_validations,
            "validated_correct": validated_correct,
            "accuracy": accuracy,
            "pending_validations": len(self.pending_validations),
            "is_significant": (
                total_validations >= self.config.min_samples and
                accuracy > self.config.significance_threshold
            ),
        }

    def get_delta_type_performance(self) -> dict[str, dict]:
        """Get performance breakdown by delta type."""
        # Would aggregate from validation results
        # Returning placeholder structure
        return {}

    def get_entity_performance(self, entity: str) -> dict:
        """Get validation performance for a specific entity."""
        entity_validations = [
            v for v in self.validations
            if v.entity == entity
        ]

        if not entity_validations:
            return {"entity": entity, "validations": 0, "accuracy": 0}

        correct = sum(1 for v in entity_validations if v.validated)

        return {
            "entity": entity,
            "validations": len(entity_validations),
            "correct": correct,
            "accuracy": correct / len(entity_validations),
            "avg_lead_time_minutes": sum(
                v.lead_time_minutes or 0 for v in entity_validations
            ) / len(entity_validations),
        }
