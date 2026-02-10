"""Evaluation metrics — stdlib math only, no numpy/sklearn.

Every metric function takes simple lists and returns a float or dict.
This is the measurement layer that answers "how good is this, really?"
"""

import math
from typing import Dict, List, Optional, Tuple


# =============================================================================
# CLASSIFICATION METRICS
# =============================================================================

def confusion_matrix(y_true: List[str], y_pred: List[str],
                     labels: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
    """Build a confusion matrix as nested dict: matrix[true_label][pred_label] = count."""
    if labels is None:
        labels = sorted(set(y_true) | set(y_pred))
    matrix = {t: {p: 0 for p in labels} for t in labels}
    for true, pred in zip(y_true, y_pred):
        if true in matrix and pred in matrix[true]:
            matrix[true][pred] += 1
    return matrix


def accuracy(y_true: List[str], y_pred: List[str]) -> float:
    """Simple accuracy: fraction of correct predictions."""
    if not y_true:
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true)


def precision_recall_f1(y_true: List[str], y_pred: List[str],
                        positive_label: str) -> Tuple[float, float, float]:
    """Precision, recall, F1 for a specific label."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == positive_label and p == positive_label)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != positive_label and p == positive_label)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == positive_label and p != positive_label)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def macro_f1(y_true: List[str], y_pred: List[str]) -> float:
    """Macro-averaged F1 across all labels."""
    labels = sorted(set(y_true) | set(y_pred))
    if not labels:
        return 0.0
    f1_scores = []
    for label in labels:
        _, _, f1 = precision_recall_f1(y_true, y_pred, label)
        f1_scores.append(f1)
    return sum(f1_scores) / len(f1_scores)


# =============================================================================
# REGRESSION METRICS
# =============================================================================

def mean_absolute_error(y_true: List[float], y_pred: List[float]) -> float:
    """Mean Absolute Error."""
    if not y_true:
        return 0.0
    return sum(abs(t - p) for t, p in zip(y_true, y_pred)) / len(y_true)


def root_mean_squared_error(y_true: List[float], y_pred: List[float]) -> float:
    """Root Mean Squared Error."""
    if not y_true:
        return 0.0
    mse = sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / len(y_true)
    return math.sqrt(mse)


# =============================================================================
# CALIBRATION METRICS
# =============================================================================

def expected_calibration_error(confidences: List[float], correct: List[bool],
                               n_bins: int = 10) -> float:
    """Expected Calibration Error (ECE).

    Bins predictions by confidence, measures gap between stated confidence
    and actual accuracy per bin. Lower is better. < 0.15 is well-calibrated.
    """
    if not confidences:
        return 0.0

    bins = [[] for _ in range(n_bins)]
    for conf, corr in zip(confidences, correct):
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append((conf, corr))

    ece = 0.0
    total = len(confidences)
    for bin_items in bins:
        if not bin_items:
            continue
        avg_conf = sum(c for c, _ in bin_items) / len(bin_items)
        avg_acc = sum(1 for _, c in bin_items if c) / len(bin_items)
        ece += len(bin_items) / total * abs(avg_conf - avg_acc)
    return ece


def max_calibration_error(confidences: List[float], correct: List[bool],
                          n_bins: int = 10) -> float:
    """Maximum Calibration Error (MCE) — worst-case bin."""
    if not confidences:
        return 0.0

    bins = [[] for _ in range(n_bins)]
    for conf, corr in zip(confidences, correct):
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append((conf, corr))

    mce = 0.0
    for bin_items in bins:
        if not bin_items:
            continue
        avg_conf = sum(c for c, _ in bin_items) / len(bin_items)
        avg_acc = sum(1 for _, c in bin_items if c) / len(bin_items)
        mce = max(mce, abs(avg_conf - avg_acc))
    return mce


def calibration_bins(confidences: List[float], correct: List[bool],
                     n_bins: int = 10) -> List[dict]:
    """Per-bin reliability data for calibration plots."""
    bins = [[] for _ in range(n_bins)]
    for conf, corr in zip(confidences, correct):
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append((conf, corr))

    result = []
    for i, bin_items in enumerate(bins):
        low = i / n_bins
        high = (i + 1) / n_bins
        if bin_items:
            avg_conf = sum(c for c, _ in bin_items) / len(bin_items)
            avg_acc = sum(1 for _, c in bin_items if c) / len(bin_items)
        else:
            avg_conf = (low + high) / 2
            avg_acc = 0.0
        result.append({
            "bin_range": f"{low:.1f}-{high:.1f}",
            "count": len(bin_items),
            "avg_confidence": round(avg_conf, 3),
            "avg_accuracy": round(avg_acc, 3),
            "gap": round(abs(avg_conf - avg_acc), 3),
        })
    return result


def brier_score(probabilities: List[float], outcomes: List[bool]) -> float:
    """Brier score: mean squared error of probability estimates. Lower is better."""
    if not probabilities:
        return 0.0
    return sum((p - (1.0 if o else 0.0)) ** 2
               for p, o in zip(probabilities, outcomes)) / len(probabilities)


# =============================================================================
# RANKING METRICS
# =============================================================================

def dcg_at_k(relevances: List[float], k: int) -> float:
    """Discounted Cumulative Gain at k."""
    score = 0.0
    for i, rel in enumerate(relevances[:k]):
        score += rel / math.log2(i + 2)  # i+2 because log2(1)=0
    return score


def ndcg_at_k(relevances: List[float], k: int) -> float:
    """Normalized DCG at k. Compares actual ranking against ideal."""
    actual_dcg = dcg_at_k(relevances, k)
    ideal_relevances = sorted(relevances, reverse=True)
    ideal_dcg = dcg_at_k(ideal_relevances, k)
    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


# =============================================================================
# CORRELATION METRICS
# =============================================================================

def spearman_rho(x: List[float], y: List[float]) -> float:
    """Spearman rank correlation coefficient.

    Measures monotonic relationship between two rankings.
    Range: -1 (perfect inverse) to +1 (perfect agreement).
    """
    if len(x) != len(y) or len(x) < 2:
        return 0.0

    def _rank(values: List[float]) -> List[float]:
        indexed = sorted(enumerate(values), key=lambda iv: iv[1])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(indexed):
            j = i
            while j < len(indexed) and indexed[j][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j - 1) / 2 + 1  # 1-based
            for k in range(i, j):
                ranks[indexed[k][0]] = avg_rank
            i = j
        return ranks

    rx = _rank(x)
    ry = _rank(y)
    n = len(x)
    d_squared = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1.0 - (6 * d_squared) / (n * (n * n - 1))


# =============================================================================
# SUMMARY HELPERS
# =============================================================================

def eval_summary(component: str, metrics: Dict[str, float],
                 targets: Dict[str, float]) -> dict:
    """Compare metrics against targets, return pass/fail summary."""
    results = {}
    for metric_name, value in metrics.items():
        target = targets.get(metric_name)
        if target is None:
            results[metric_name] = {"value": round(value, 4), "target": None, "pass": None}
            continue
        # For error metrics (lower is better), pass if value <= target
        lower_is_better = any(kw in metric_name.lower()
                              for kw in ("error", "ece", "mce", "mae", "rmse", "brier"))
        if lower_is_better:
            passed = value <= target
        else:
            passed = value >= target
        results[metric_name] = {
            "value": round(value, 4),
            "target": target,
            "pass": passed,
        }
    passed = sum(1 for r in results.values() if r.get("pass") is True)
    total = sum(1 for r in results.values() if r.get("pass") is not None)
    return {
        "component": component,
        "metrics": results,
        "passed": passed,
        "total": total,
        "all_pass": passed == total if total > 0 else False,
    }
