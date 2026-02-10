"""Cross-component calibration evaluation.

Collects confidence scores from every confidence-producing component
and measures ECE across the board. This answers: "when MyPersona says
it's 80% confident, is it actually right 80% of the time?"
"""

from typing import List

from eval.datasets.schemas import MoodSample, CalibrationSample
from eval.datasets.generate import load_dataset
from eval.metrics import expected_calibration_error, calibration_bins, brier_score, eval_summary
from src.engines import MoodDetector


TARGETS = {
    "overall_ece": 0.15,
    "mood_ece": 0.15,
    "brier_score": 0.25,
}


def run(verbose: bool = False) -> dict:
    """Run cross-component calibration evaluation."""
    # Collect calibration data from mood detector (main confidence producer)
    mood_samples = [MoodSample.from_dict(d) for d in load_dataset("mood")]
    detector = MoodDetector()

    all_confidences = []
    all_correct = []
    mood_confidences = []
    mood_correct = []

    for sample in mood_samples:
        mood = detector.detect(sample.text)
        conf = mood.confidence
        correct = mood.quadrant.value == sample.expected_quadrant

        mood_confidences.append(conf)
        mood_correct.append(correct)
        all_confidences.append(conf)
        all_correct.append(correct)

    # Compute calibration metrics
    mood_ece = expected_calibration_error(mood_confidences, mood_correct)
    overall_ece = expected_calibration_error(all_confidences, all_correct)

    # Brier score: treat confidence as probability of being correct
    brier = brier_score(all_confidences, all_correct)

    metrics = {
        "overall_ece": overall_ece,
        "mood_ece": mood_ece,
        "brier_score": brier,
    }

    # Calibration bins for visualization
    cal_bins = calibration_bins(all_confidences, all_correct)

    summary = eval_summary("Calibration", metrics, TARGETS)
    summary["calibration_bins"] = cal_bins
    summary["total_predictions"] = len(all_confidences)

    # Confidence distribution stats
    if all_confidences:
        summary["confidence_stats"] = {
            "min": round(min(all_confidences), 3),
            "max": round(max(all_confidences), 3),
            "mean": round(sum(all_confidences) / len(all_confidences), 3),
        }

    return summary
