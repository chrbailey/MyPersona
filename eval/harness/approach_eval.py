"""ApproachAvoidanceDetector evaluation harness.

Runs approach/avoidance samples through the detector, computes:
- Spearman rho between predicted approach ratio and ground truth strength
- Direction accuracy (approach/avoidance/neutral classification)
"""

import tempfile
from pathlib import Path
from typing import List

from eval.datasets.schemas import ApproachAvoidanceSample
from eval.datasets.generate import load_dataset
from eval.metrics import spearman_rho, accuracy, eval_summary
from src.engines import ApproachAvoidanceDetector
from src.models import MoodState, EmotionalQuadrant


TARGETS = {
    "spearman_rho": 0.60,
    "direction_accuracy": 0.65,
}


def _make_mood(valence: float, arousal: float) -> MoodState:
    """Construct a MoodState from valence/arousal for feeding to detector."""
    if abs(valence) < 0.1 and abs(arousal) < 0.1:
        quadrant = EmotionalQuadrant.NEUTRAL
    elif valence >= 0 and arousal >= 0:
        quadrant = EmotionalQuadrant.EXCITED
    elif valence >= 0:
        quadrant = EmotionalQuadrant.CALM
    elif arousal >= 0:
        quadrant = EmotionalQuadrant.STRESSED
    else:
        quadrant = EmotionalQuadrant.LOW

    return MoodState(
        valence=valence, arousal=arousal, confidence=0.5,
        quadrant=quadrant, signals=[],
    )


def run(verbose: bool = False) -> dict:
    """Run approach/avoidance evaluation."""
    samples = [ApproachAvoidanceSample.from_dict(d) for d in load_dataset("approach")]

    ground_truth_strengths = []
    predicted_ratios = []
    true_directions = []
    pred_directions = []

    for sample in samples:
        with tempfile.TemporaryDirectory() as tmp:
            detector = ApproachAvoidanceDetector(Path(tmp))
            mood = _make_mood(sample.valence, sample.arousal)
            result = detector.analyze(sample.text, sample.topic, mood)

            # Map ground truth direction to numeric for Spearman
            # approach = positive, avoidance = negative, neutral = 0
            if sample.expected_direction == "approach":
                gt_val = sample.expected_strength
            elif sample.expected_direction == "avoidance":
                gt_val = -sample.expected_strength
            else:
                gt_val = 0.0

            # Predicted: approach_ratio 0-1, map to -1..+1
            pred_val = (result.approach_ratio - 0.5) * 2

            ground_truth_strengths.append(gt_val)
            predicted_ratios.append(pred_val)

            # Direction classification
            true_directions.append(sample.expected_direction)
            if result.approach_count > result.avoidance_count:
                pred_dir = "approach"
            elif result.avoidance_count > result.approach_count:
                pred_dir = "avoidance"
            else:
                pred_dir = "neutral"
            pred_directions.append(pred_dir)

    rho = spearman_rho(ground_truth_strengths, predicted_ratios)
    dir_acc = accuracy(true_directions, pred_directions)

    metrics = {
        "spearman_rho": rho,
        "direction_accuracy": dir_acc,
    }

    summary = eval_summary("ApproachAvoidanceDetector", metrics, TARGETS)
    summary["total_samples"] = len(samples)
    return summary
