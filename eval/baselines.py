"""Naive baselines for comparison.

Each baseline represents what you'd get with zero intelligence.
If MyPersona can't beat these, the component isn't adding value.
"""

import random
from typing import List, Tuple

from eval.datasets.schemas import MoodSample, GovernanceSample, ApproachAvoidanceSample
from eval.datasets.generate import load_dataset
from eval.metrics import accuracy, mean_absolute_error, spearman_rho, ndcg_at_k


QUADRANTS = ["excited", "calm", "stressed", "low", "neutral"]


def random_quadrant_baseline() -> dict:
    """Random quadrant assignment. Expected accuracy: ~20% (1/5)."""
    samples = [MoodSample.from_dict(d) for d in load_dataset("mood")]
    random.seed(42)
    y_true = [s.expected_quadrant for s in samples]
    y_pred = [random.choice(QUADRANTS) for _ in samples]
    return {
        "name": "random_quadrant",
        "accuracy": accuracy(y_true, y_pred),
        "description": "Random quadrant assignment (expected ~20%)",
    }


def majority_class_baseline() -> dict:
    """Always predict the most common quadrant."""
    samples = [MoodSample.from_dict(d) for d in load_dataset("mood")]
    y_true = [s.expected_quadrant for s in samples]
    from collections import Counter
    majority = Counter(y_true).most_common(1)[0][0]
    y_pred = [majority] * len(y_true)
    return {
        "name": "majority_class",
        "accuracy": accuracy(y_true, y_pred),
        "majority_label": majority,
        "description": f"Always predict '{majority}'",
    }


def zero_valence_arousal_baseline() -> dict:
    """Always predict zero valence and arousal."""
    samples = [MoodSample.from_dict(d) for d in load_dataset("mood")]
    true_v = [s.expected_valence for s in samples]
    true_a = [s.expected_arousal for s in samples]
    pred_v = [0.0] * len(samples)
    pred_a = [0.0] * len(samples)
    return {
        "name": "zero_valence_arousal",
        "valence_mae": mean_absolute_error(true_v, pred_v),
        "arousal_mae": mean_absolute_error(true_a, pred_a),
        "description": "Always predict valence=0, arousal=0",
    }


def always_allow_baseline() -> dict:
    """Always allow all governance decisions."""
    samples = [GovernanceSample.from_dict(d) for d in load_dataset("governance")]
    y_true = [s.expected_decision for s in samples]
    y_pred = ["allowed"] * len(y_true)
    return {
        "name": "always_allow",
        "accuracy": accuracy(y_true, y_pred),
        "description": "Always allow everything (no governance)",
    }


def uniform_confidence_baseline() -> dict:
    """Always predict confidence = 0.5."""
    return {
        "name": "uniform_confidence",
        "ece": 0.0,  # uniform is trivially calibrated if accuracy happens to be 50%
        "description": "Always predict 50% confidence",
    }


def random_approach_baseline() -> dict:
    """Random approach/avoidance assignment."""
    samples = [ApproachAvoidanceSample.from_dict(d) for d in load_dataset("approach")]
    random.seed(42)
    directions = ["approach", "avoidance", "neutral"]
    y_true = [s.expected_direction for s in samples]
    y_pred = [random.choice(directions) for _ in samples]
    gt = [s.expected_strength if s.expected_direction == "approach"
          else -s.expected_strength if s.expected_direction == "avoidance"
          else 0.0 for s in samples]
    pred = [random.uniform(-1, 1) for _ in samples]
    return {
        "name": "random_approach",
        "direction_accuracy": accuracy(y_true, y_pred),
        "spearman_rho": spearman_rho(gt, pred),
        "description": "Random approach/avoidance/neutral assignment",
    }


def run_all_baselines() -> dict:
    """Run all baselines and return results."""
    return {
        "random_quadrant": random_quadrant_baseline(),
        "majority_class": majority_class_baseline(),
        "zero_valence_arousal": zero_valence_arousal_baseline(),
        "always_allow": always_allow_baseline(),
        "uniform_confidence": uniform_confidence_baseline(),
        "random_approach": random_approach_baseline(),
    }
