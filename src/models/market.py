"""
Market models for validation of discourse-based predictions.

These models track market data and correlate with detected events
to validate whether our discourse analysis actually predicts movements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Any
import uuid


class MarketDirection(Enum):
    """Direction of market movement."""
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    VOLATILE = "volatile"  # Large swings both directions


class MovementMagnitude(Enum):
    """Magnitude of price movement."""
    NEGLIGIBLE = "negligible"   # < 0.5%
    MINOR = "minor"             # 0.5% - 2%
    MODERATE = "moderate"       # 2% - 5%
    SIGNIFICANT = "significant" # 5% - 10%
    MAJOR = "major"            # > 10%


@dataclass
class MarketDataPoint:
    """
    A single market data observation.

    Captures price and volume at a point in time.
    """
    ticker: str
    timestamp: datetime

    # Price data
    price: float
    open_price: float = 0.0
    high: float = 0.0
    low: float = 0.0

    # Volume data
    volume: int = 0
    avg_volume: int = 0  # Average volume for comparison

    # Computed metrics
    price_change: float = 0.0  # Change from previous close
    price_change_pct: float = 0.0
    volume_ratio: float = 1.0  # volume / avg_volume

    # Volatility
    intraday_range: float = 0.0  # (high - low) / open

    # Market context
    market_open: bool = True
    pre_market: bool = False
    after_hours: bool = False

    @property
    def is_high_volume(self) -> bool:
        """Check if volume is significantly above average."""
        return self.volume_ratio > 1.5

    @property
    def movement_direction(self) -> MarketDirection:
        """Determine direction of movement."""
        if abs(self.price_change_pct) < 0.5:
            return MarketDirection.FLAT
        if self.intraday_range > 5.0:  # High volatility
            return MarketDirection.VOLATILE
        return MarketDirection.UP if self.price_change_pct > 0 else MarketDirection.DOWN

    @property
    def movement_magnitude(self) -> MovementMagnitude:
        """Determine magnitude of movement."""
        pct = abs(self.price_change_pct)
        if pct < 0.5:
            return MovementMagnitude.NEGLIGIBLE
        if pct < 2.0:
            return MovementMagnitude.MINOR
        if pct < 5.0:
            return MovementMagnitude.MODERATE
        if pct < 10.0:
            return MovementMagnitude.SIGNIFICANT
        return MovementMagnitude.MAJOR


@dataclass
class PriceMovement:
    """
    Price movement over a time window.

    Used to validate predictions against actual market behavior.
    """
    ticker: str

    # Time window
    start_time: datetime
    end_time: datetime

    # Starting point
    start_price: float
    start_volume: int = 0

    # Ending point
    end_price: float
    end_volume: int = 0

    # Movement metrics
    price_change: float = 0.0
    price_change_pct: float = 0.0
    total_volume: int = 0

    # Extremes during window
    high_price: float = 0.0
    low_price: float = 0.0
    high_time: Optional[datetime] = None
    low_time: Optional[datetime] = None

    # Volatility
    avg_volatility: float = 0.0  # Average intraday range
    max_drawdown: float = 0.0   # Largest peak-to-trough
    max_runup: float = 0.0      # Largest trough-to-peak

    # Direction and magnitude
    direction: MarketDirection = MarketDirection.FLAT
    magnitude: MovementMagnitude = MovementMagnitude.NEGLIGIBLE

    def __post_init__(self):
        """Calculate derived metrics."""
        if self.start_price > 0:
            self.price_change = self.end_price - self.start_price
            self.price_change_pct = (self.price_change / self.start_price) * 100

            # Determine direction
            if abs(self.price_change_pct) < 0.5:
                self.direction = MarketDirection.FLAT
            elif self.max_drawdown > 3 and self.max_runup > 3:
                self.direction = MarketDirection.VOLATILE
            elif self.price_change > 0:
                self.direction = MarketDirection.UP
            else:
                self.direction = MarketDirection.DOWN

            # Determine magnitude
            pct = abs(self.price_change_pct)
            if pct < 0.5:
                self.magnitude = MovementMagnitude.NEGLIGIBLE
            elif pct < 2.0:
                self.magnitude = MovementMagnitude.MINOR
            elif pct < 5.0:
                self.magnitude = MovementMagnitude.MODERATE
            elif pct < 10.0:
                self.magnitude = MovementMagnitude.SIGNIFICANT
            else:
                self.magnitude = MovementMagnitude.MAJOR


@dataclass
class PredictionOutcome:
    """
    Outcome of a prediction for validation.

    Tracks what we predicted vs what actually happened.
    """
    prediction_id: str
    event_id: str
    ticker: str

    # Prediction (made at detection time)
    predicted_at: datetime
    predicted_direction: MarketDirection
    predicted_magnitude: MovementMagnitude
    predicted_timing: str  # "1h", "4h", "1d", "1w"
    prediction_confidence: float

    # Actual outcomes at different time horizons
    outcome_1h: Optional[PriceMovement] = None
    outcome_4h: Optional[PriceMovement] = None
    outcome_1d: Optional[PriceMovement] = None
    outcome_1w: Optional[PriceMovement] = None

    # Scoring
    direction_correct_1h: Optional[bool] = None
    direction_correct_4h: Optional[bool] = None
    direction_correct_1d: Optional[bool] = None
    direction_correct_1w: Optional[bool] = None

    magnitude_correct_1h: Optional[bool] = None
    magnitude_correct_4h: Optional[bool] = None
    magnitude_correct_1d: Optional[bool] = None
    magnitude_correct_1w: Optional[bool] = None

    # Best match (which time horizon best matched prediction)
    best_horizon: Optional[str] = None
    best_horizon_score: float = 0.0

    # Overall score
    overall_score: float = 0.0  # 0-1, how accurate was the prediction

    @classmethod
    def generate_id(cls) -> str:
        """Generate a unique prediction ID."""
        return f"pred_{uuid.uuid4().hex[:12]}"

    def calculate_scores(self) -> None:
        """Calculate all scoring metrics."""
        horizons = [
            ("1h", self.outcome_1h, self.direction_correct_1h, self.magnitude_correct_1h),
            ("4h", self.outcome_4h, self.direction_correct_4h, self.magnitude_correct_4h),
            ("1d", self.outcome_1d, self.direction_correct_1d, self.magnitude_correct_1d),
            ("1w", self.outcome_1w, self.direction_correct_1w, self.magnitude_correct_1w),
        ]

        best_score = 0.0
        best_hz = None

        for horizon, outcome, dir_correct, mag_correct in horizons:
            if outcome is None:
                continue

            # Score this horizon
            score = 0.0

            # Direction correctness (weighted heavily)
            if self.predicted_direction == outcome.direction:
                score += 0.6
            elif (
                self.predicted_direction in [MarketDirection.UP, MarketDirection.DOWN]
                and outcome.direction == MarketDirection.VOLATILE
            ):
                # Partial credit if we predicted direction but it was volatile
                score += 0.3

            # Magnitude correctness (weighted less)
            if self.predicted_magnitude == outcome.magnitude:
                score += 0.4
            elif abs(
                list(MovementMagnitude).index(self.predicted_magnitude) -
                list(MovementMagnitude).index(outcome.magnitude)
            ) == 1:
                # Partial credit if off by one level
                score += 0.2

            if score > best_score:
                best_score = score
                best_hz = horizon

        self.best_horizon = best_hz
        self.best_horizon_score = best_score
        self.overall_score = best_score


@dataclass
class ValidationResult:
    """
    Complete validation result for an event.

    Used to track whether our detection was validated by market movement.
    """
    validation_id: str
    event_id: str
    entity: str
    tickers: list[str] = field(default_factory=list)

    # Event details
    event_type: str = ""
    event_severity: str = ""
    event_confidence: float = 0.0
    detected_at: Optional[datetime] = None

    # Validation timing
    validated_at: datetime = field(default_factory=datetime.utcnow)

    # Prediction outcomes per ticker
    outcomes: dict[str, PredictionOutcome] = field(default_factory=dict)

    # Aggregate results
    any_ticker_correct: bool = False
    all_tickers_correct: bool = False
    avg_direction_accuracy: float = 0.0
    avg_magnitude_accuracy: float = 0.0
    avg_overall_score: float = 0.0

    # Lead time (how much before market move did we detect)
    lead_time_minutes: Optional[float] = None

    # Verdict
    validated: bool = False
    validation_strength: str = "none"  # "none", "weak", "moderate", "strong"

    @classmethod
    def generate_id(cls) -> str:
        """Generate a unique validation ID."""
        return f"val_{uuid.uuid4().hex[:12]}"

    def calculate_aggregate_results(self) -> None:
        """Calculate aggregate validation metrics."""
        if not self.outcomes:
            return

        direction_correct_count = 0
        magnitude_correct_count = 0
        total_score = 0.0
        ticker_count = 0

        for ticker, outcome in self.outcomes.items():
            outcome.calculate_scores()
            ticker_count += 1
            total_score += outcome.overall_score

            # Check if any horizon was direction-correct
            if any([
                outcome.direction_correct_1h,
                outcome.direction_correct_4h,
                outcome.direction_correct_1d,
                outcome.direction_correct_1w,
            ]):
                direction_correct_count += 1

            # Check if any horizon was magnitude-correct
            if any([
                outcome.magnitude_correct_1h,
                outcome.magnitude_correct_4h,
                outcome.magnitude_correct_1d,
                outcome.magnitude_correct_1w,
            ]):
                magnitude_correct_count += 1

        self.avg_direction_accuracy = direction_correct_count / ticker_count
        self.avg_magnitude_accuracy = magnitude_correct_count / ticker_count
        self.avg_overall_score = total_score / ticker_count

        self.any_ticker_correct = direction_correct_count > 0
        self.all_tickers_correct = direction_correct_count == ticker_count

        # Determine validation strength
        if self.avg_overall_score >= 0.8:
            self.validation_strength = "strong"
            self.validated = True
        elif self.avg_overall_score >= 0.6:
            self.validation_strength = "moderate"
            self.validated = True
        elif self.avg_overall_score >= 0.4:
            self.validation_strength = "weak"
            self.validated = True
        else:
            self.validation_strength = "none"
            self.validated = False


@dataclass
class MarketCorrelation:
    """
    Statistical correlation between delta types and market movements.

    Used to learn which deltas are most predictive.
    """
    delta_type: str
    entity: Optional[str] = None  # None = across all entities

    # Sample size
    sample_count: int = 0

    # Direction correlation
    direction_accuracy: float = 0.0  # % of time direction was correct
    direction_confidence_interval: tuple[float, float] = (0.0, 0.0)

    # Magnitude correlation
    magnitude_accuracy: float = 0.0
    magnitude_confidence_interval: tuple[float, float] = (0.0, 0.0)

    # Timing
    avg_lead_time_minutes: float = 0.0
    lead_time_stddev: float = 0.0

    # Best time horizon
    best_horizon: str = "1d"
    best_horizon_accuracy: float = 0.0

    # Statistical significance
    p_value: float = 1.0
    is_significant: bool = False  # p < 0.05

    # Overall usefulness
    predictive_power: float = 0.0  # Combined score

    def update_with_outcome(self, outcome: PredictionOutcome) -> None:
        """Update correlation statistics with new outcome."""
        # Running average update
        self.sample_count += 1
        n = self.sample_count

        # Update direction accuracy
        dir_correct = 1.0 if outcome.best_horizon_score >= 0.5 else 0.0
        self.direction_accuracy = (
            (self.direction_accuracy * (n - 1) + dir_correct) / n
        )

        # Update magnitude accuracy
        mag_correct = 1.0 if outcome.best_horizon_score >= 0.8 else 0.0
        self.magnitude_accuracy = (
            (self.magnitude_accuracy * (n - 1) + mag_correct) / n
        )

        # Recalculate significance (simplified)
        if self.sample_count >= 30:
            # Binomial test approximation
            expected = 0.33  # Random chance for 3-way direction
            observed = self.direction_accuracy
            if observed > expected + 0.15:  # Meaningful improvement
                self.is_significant = True
                self.p_value = 0.05  # Placeholder

        # Calculate predictive power
        self.predictive_power = (
            self.direction_accuracy * 0.6 +
            self.magnitude_accuracy * 0.4
        ) * (1.0 if self.is_significant else 0.5)
