"""MoodDetector evaluation harness.

Runs all mood samples through MoodDetector, computes:
- 5×5 confusion matrix (quadrant classification)
- Valence MAE, Arousal MAE
- Confidence ECE
- Per-difficulty breakdown
"""

from typing import Dict, List

from eval.datasets.schemas import MoodSample
from eval.datasets.generate import load_dataset
from eval.metrics import (
    confusion_matrix, accuracy, macro_f1, mean_absolute_error,
    expected_calibration_error, calibration_bins, eval_summary,
)
from src.engines import MoodDetector


QUADRANT_LABELS = ["excited", "calm", "stressed", "low", "neutral"]

TARGETS = {
    "quadrant_accuracy": 0.65,
    "valence_mae": 0.25,
    "arousal_mae": 0.25,
    "confidence_ece": 0.15,
    "macro_f1": 0.50,
}


def run(verbose: bool = False) -> dict:
    """Run mood evaluation, return results dict."""
    samples = [MoodSample.from_dict(d) for d in load_dataset("mood")]
    detector = MoodDetector()

    y_true_quad = []
    y_pred_quad = []
    true_valence = []
    pred_valence = []
    true_arousal = []
    pred_arousal = []
    confidences = []
    correct_flags = []

    # Per-difficulty tracking
    by_difficulty: Dict[str, Dict[str, list]] = {}

    for sample in samples:
        mood = detector.detect(sample.text)

        y_true_quad.append(sample.expected_quadrant)
        y_pred_quad.append(mood.quadrant.value)
        true_valence.append(sample.expected_valence)
        pred_valence.append(mood.valence)
        true_arousal.append(sample.expected_arousal)
        pred_arousal.append(mood.arousal)
        confidences.append(mood.confidence)
        correct_flags.append(mood.quadrant.value == sample.expected_quadrant)

        # Track by difficulty
        diff = sample.difficulty
        if diff not in by_difficulty:
            by_difficulty[diff] = {
                "true_quad": [], "pred_quad": [],
                "true_val": [], "pred_val": [],
                "true_aro": [], "pred_aro": [],
                "conf": [], "correct": [],
            }
        by_difficulty[diff]["true_quad"].append(sample.expected_quadrant)
        by_difficulty[diff]["pred_quad"].append(mood.quadrant.value)
        by_difficulty[diff]["true_val"].append(sample.expected_valence)
        by_difficulty[diff]["pred_val"].append(mood.valence)
        by_difficulty[diff]["true_aro"].append(sample.expected_arousal)
        by_difficulty[diff]["pred_aro"].append(mood.arousal)
        by_difficulty[diff]["conf"].append(mood.confidence)
        by_difficulty[diff]["correct"].append(mood.quadrant.value == sample.expected_quadrant)

    # Overall metrics
    metrics = {
        "quadrant_accuracy": accuracy(y_true_quad, y_pred_quad),
        "macro_f1": macro_f1(y_true_quad, y_pred_quad),
        "valence_mae": mean_absolute_error(true_valence, pred_valence),
        "arousal_mae": mean_absolute_error(true_arousal, pred_arousal),
        "confidence_ece": expected_calibration_error(confidences, correct_flags),
    }

    # Confusion matrix
    cm = confusion_matrix(y_true_quad, y_pred_quad, QUADRANT_LABELS)

    # Calibration bins
    cal_bins = calibration_bins(confidences, correct_flags)

    # Per-difficulty breakdown
    difficulty_results = {}
    for diff, data in sorted(by_difficulty.items()):
        difficulty_results[diff] = {
            "count": len(data["true_quad"]),
            "quadrant_accuracy": accuracy(data["true_quad"], data["pred_quad"]),
            "valence_mae": mean_absolute_error(data["true_val"], data["pred_val"]),
            "arousal_mae": mean_absolute_error(data["true_aro"], data["pred_aro"]),
            "confidence_ece": expected_calibration_error(data["conf"], data["correct"]),
        }

    summary = eval_summary("MoodDetector", metrics, TARGETS)
    summary["confusion_matrix"] = cm
    summary["calibration_bins"] = cal_bins
    summary["by_difficulty"] = difficulty_results
    summary["total_samples"] = len(samples)
    return summary
