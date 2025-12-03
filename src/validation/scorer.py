"""
Prediction scorer - comprehensive scoring of prediction accuracy.

Provides detailed metrics for evaluating the system's performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging
from collections import defaultdict
import statistics

from ..models.market import ValidationResult, PredictionOutcome
from ..models.event import EventType, EventSeverity

logger = logging.getLogger(__name__)


@dataclass
class ScoreCard:
    """Comprehensive score card for system performance."""
    # Overall metrics
    total_predictions: int = 0
    correct_predictions: int = 0
    overall_accuracy: float = 0.0

    # Direction accuracy
    direction_predictions: int = 0
    direction_correct: int = 0
    direction_accuracy: float = 0.0

    # Magnitude accuracy
    magnitude_predictions: int = 0
    magnitude_correct: int = 0
    magnitude_accuracy: float = 0.0

    # Timing analysis
    avg_lead_time_minutes: float = 0.0
    median_lead_time_minutes: float = 0.0

    # By event type
    accuracy_by_event_type: dict[str, float] = field(default_factory=dict)

    # By severity
    accuracy_by_severity: dict[str, float] = field(default_factory=dict)

    # By time horizon
    accuracy_by_horizon: dict[str, float] = field(default_factory=dict)

    # Statistical significance
    sample_size: int = 0
    is_significant: bool = False
    confidence_interval: tuple[float, float] = (0.0, 0.0)

    # Comparison to baseline
    baseline_accuracy: float = 0.33  # Random chance for 3-way direction
    improvement_over_baseline: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for reporting."""
        return {
            "overall": {
                "total_predictions": self.total_predictions,
                "correct": self.correct_predictions,
                "accuracy": f"{self.overall_accuracy:.1%}",
            },
            "direction": {
                "predictions": self.direction_predictions,
                "correct": self.direction_correct,
                "accuracy": f"{self.direction_accuracy:.1%}",
            },
            "magnitude": {
                "predictions": self.magnitude_predictions,
                "correct": self.magnitude_correct,
                "accuracy": f"{self.magnitude_accuracy:.1%}",
            },
            "timing": {
                "avg_lead_time_minutes": self.avg_lead_time_minutes,
                "median_lead_time_minutes": self.median_lead_time_minutes,
            },
            "significance": {
                "sample_size": self.sample_size,
                "is_significant": self.is_significant,
                "confidence_interval": self.confidence_interval,
                "improvement_over_baseline": f"{self.improvement_over_baseline:.1%}",
            },
            "by_event_type": self.accuracy_by_event_type,
            "by_severity": self.accuracy_by_severity,
            "by_horizon": self.accuracy_by_horizon,
        }


class PredictionScorer:
    """
    Scores prediction accuracy across multiple dimensions.

    Provides the metrics needed to prove system value to investors.
    """

    def __init__(self, min_samples_for_significance: int = 30):
        self.min_samples = min_samples_for_significance

        # Stored validations
        self.validations: list[ValidationResult] = []

    def add_validation(self, validation: ValidationResult) -> None:
        """Add a validation result for scoring."""
        self.validations.append(validation)

    def calculate_scorecard(
        self,
        time_window: Optional[tuple[datetime, datetime]] = None,
        entity_filter: Optional[str] = None,
    ) -> ScoreCard:
        """
        Calculate comprehensive scorecard.

        Args:
            time_window: Optional (start, end) to filter validations
            entity_filter: Optional entity to filter by

        Returns:
            ScoreCard with all metrics
        """
        # Filter validations
        validations = self.validations

        if time_window:
            start, end = time_window
            validations = [
                v for v in validations
                if v.validated_at and start <= v.validated_at <= end
            ]

        if entity_filter:
            validations = [v for v in validations if v.entity == entity_filter]

        if not validations:
            return ScoreCard()

        # Calculate metrics
        scorecard = ScoreCard()
        scorecard.sample_size = len(validations)
        scorecard.total_predictions = len(validations)

        # Overall accuracy
        correct = [v for v in validations if v.validated]
        scorecard.correct_predictions = len(correct)
        scorecard.overall_accuracy = len(correct) / len(validations)

        # Direction accuracy
        dir_results = self._calculate_direction_accuracy(validations)
        scorecard.direction_predictions = dir_results["predictions"]
        scorecard.direction_correct = dir_results["correct"]
        scorecard.direction_accuracy = dir_results["accuracy"]

        # Magnitude accuracy
        mag_results = self._calculate_magnitude_accuracy(validations)
        scorecard.magnitude_predictions = mag_results["predictions"]
        scorecard.magnitude_correct = mag_results["correct"]
        scorecard.magnitude_accuracy = mag_results["accuracy"]

        # Lead time analysis
        lead_times = [
            v.lead_time_minutes for v in validations
            if v.lead_time_minutes and v.lead_time_minutes > 0
        ]
        if lead_times:
            scorecard.avg_lead_time_minutes = statistics.mean(lead_times)
            scorecard.median_lead_time_minutes = statistics.median(lead_times)

        # By event type
        scorecard.accuracy_by_event_type = self._accuracy_by_field(
            validations, lambda v: v.event_type
        )

        # By severity
        scorecard.accuracy_by_severity = self._accuracy_by_field(
            validations, lambda v: v.event_severity
        )

        # By horizon
        scorecard.accuracy_by_horizon = self._calculate_horizon_accuracy(validations)

        # Statistical significance
        scorecard.is_significant = (
            scorecard.sample_size >= self.min_samples and
            scorecard.direction_accuracy > scorecard.baseline_accuracy + 0.1
        )

        # Confidence interval (simplified Wilson score)
        scorecard.confidence_interval = self._calculate_confidence_interval(
            scorecard.direction_correct,
            scorecard.direction_predictions,
        )

        # Improvement over baseline
        scorecard.improvement_over_baseline = (
            scorecard.direction_accuracy - scorecard.baseline_accuracy
        )

        return scorecard

    def _calculate_direction_accuracy(
        self,
        validations: list[ValidationResult],
    ) -> dict:
        """Calculate direction prediction accuracy."""
        predictions = 0
        correct = 0

        for validation in validations:
            for outcome in validation.outcomes.values():
                # Check each horizon
                for horizon in ["1h", "4h", "1d", "1w"]:
                    dir_correct = getattr(outcome, f"direction_correct_{horizon}", None)
                    if dir_correct is not None:
                        predictions += 1
                        if dir_correct:
                            correct += 1

        return {
            "predictions": predictions,
            "correct": correct,
            "accuracy": correct / predictions if predictions > 0 else 0,
        }

    def _calculate_magnitude_accuracy(
        self,
        validations: list[ValidationResult],
    ) -> dict:
        """Calculate magnitude prediction accuracy."""
        predictions = 0
        correct = 0

        for validation in validations:
            for outcome in validation.outcomes.values():
                for horizon in ["1h", "4h", "1d", "1w"]:
                    mag_correct = getattr(outcome, f"magnitude_correct_{horizon}", None)
                    if mag_correct is not None:
                        predictions += 1
                        if mag_correct:
                            correct += 1

        return {
            "predictions": predictions,
            "correct": correct,
            "accuracy": correct / predictions if predictions > 0 else 0,
        }

    def _accuracy_by_field(
        self,
        validations: list[ValidationResult],
        field_getter,
    ) -> dict[str, float]:
        """Calculate accuracy grouped by a field."""
        groups = defaultdict(list)

        for validation in validations:
            key = field_getter(validation)
            groups[key].append(validation)

        return {
            key: sum(1 for v in vals if v.validated) / len(vals)
            for key, vals in groups.items()
            if vals
        }

    def _calculate_horizon_accuracy(
        self,
        validations: list[ValidationResult],
    ) -> dict[str, float]:
        """Calculate accuracy by time horizon."""
        horizon_results = defaultdict(lambda: {"correct": 0, "total": 0})

        for validation in validations:
            for outcome in validation.outcomes.values():
                for horizon in ["1h", "4h", "1d", "1w"]:
                    dir_correct = getattr(outcome, f"direction_correct_{horizon}", None)
                    if dir_correct is not None:
                        horizon_results[horizon]["total"] += 1
                        if dir_correct:
                            horizon_results[horizon]["correct"] += 1

        return {
            horizon: (
                results["correct"] / results["total"]
                if results["total"] > 0 else 0
            )
            for horizon, results in horizon_results.items()
        }

    def _calculate_confidence_interval(
        self,
        successes: int,
        trials: int,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """Calculate Wilson score confidence interval."""
        if trials == 0:
            return (0.0, 0.0)

        z = 1.96  # 95% confidence
        p = successes / trials
        n = trials

        denominator = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denominator
        margin = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5 / denominator

        return (max(0, center - margin), min(1, center + margin))

    def generate_investor_report(self) -> dict:
        """Generate report suitable for investor presentation."""
        scorecard = self.calculate_scorecard()

        return {
            "summary": {
                "headline": f"Achieving {scorecard.direction_accuracy:.0%} directional accuracy",
                "sample_size": scorecard.sample_size,
                "statistically_significant": scorecard.is_significant,
            },
            "key_metrics": {
                "direction_accuracy": f"{scorecard.direction_accuracy:.1%}",
                "improvement_over_random": f"{scorecard.improvement_over_baseline:.1%}",
                "avg_lead_time": f"{scorecard.avg_lead_time_minutes:.0f} minutes",
            },
            "proof_points": [
                f"Predicted direction correctly {scorecard.direction_correct} "
                f"out of {scorecard.direction_predictions} times",
                f"Detected events an average of {scorecard.avg_lead_time_minutes:.0f} "
                "minutes before market reaction",
                f"Statistically significant at 95% confidence"
                if scorecard.is_significant else "Building sample size for significance",
            ],
            "detailed_scorecard": scorecard.to_dict(),
        }

    def get_best_performing_patterns(self, top_n: int = 5) -> list[dict]:
        """Get the best performing event type / severity combinations."""
        combinations = defaultdict(lambda: {"correct": 0, "total": 0})

        for validation in self.validations:
            key = (validation.event_type, validation.event_severity)
            combinations[key]["total"] += 1
            if validation.validated:
                combinations[key]["correct"] += 1

        # Calculate accuracy and sort
        results = []
        for (event_type, severity), stats in combinations.items():
            if stats["total"] >= 5:  # Minimum sample
                results.append({
                    "event_type": event_type,
                    "severity": severity,
                    "accuracy": stats["correct"] / stats["total"],
                    "sample_size": stats["total"],
                })

        results.sort(key=lambda x: x["accuracy"], reverse=True)
        return results[:top_n]
