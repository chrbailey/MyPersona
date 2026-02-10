"""GovernanceLayer evaluation harness.

Deterministic evaluation — all cases have known-correct outcomes
from threshold logic. This is a regression test with precision/recall framing.
Target: 1.0 precision, 1.0 recall (any failure is a bug).
"""

import tempfile
from pathlib import Path
from typing import List

from eval.datasets.schemas import GovernanceSample
from eval.datasets.generate import load_dataset
from eval.metrics import precision_recall_f1, accuracy, eval_summary
from src.models import EmotionalMemory
from src.memory import GovernanceLayer


TARGETS = {
    "accuracy": 1.0,
    "held_precision": 1.0,
    "held_recall": 1.0,
    "held_f1": 1.0,
    "allowed_precision": 1.0,
    "allowed_recall": 1.0,
    "allowed_f1": 1.0,
}


def run(verbose: bool = False) -> dict:
    """Run governance evaluation, return results dict."""
    samples = [GovernanceSample.from_dict(d) for d in load_dataset("governance")]

    y_true = []
    y_pred = []
    failures = []

    for sample in samples:
        with tempfile.TemporaryDirectory() as tmp:
            gov = GovernanceLayer(Path(tmp))
            memory = EmotionalMemory(
                content="eval test",
                encoding_weight=sample.encoding_weight,
                conflict_score=sample.conflict_score,
                trust_zone=sample.trust_zone,
                corroboration_count=sample.corroboration_count,
            )

            if sample.action == "delete_memory":
                decision = gov.gate_memory_delete(memory)
            else:
                decision = gov.gate_memory_write(memory)

            y_true.append(sample.expected_decision)
            y_pred.append(decision)

            if decision != sample.expected_decision:
                failures.append({
                    "expected": sample.expected_decision,
                    "got": decision,
                    "encoding_weight": sample.encoding_weight,
                    "conflict_score": sample.conflict_score,
                    "trust_zone": sample.trust_zone,
                    "corroboration_count": sample.corroboration_count,
                    "action": sample.action,
                    "reason": sample.reason,
                })

    held_p, held_r, held_f = precision_recall_f1(y_true, y_pred, "held")
    allowed_p, allowed_r, allowed_f = precision_recall_f1(y_true, y_pred, "allowed")

    metrics = {
        "accuracy": accuracy(y_true, y_pred),
        "held_precision": held_p,
        "held_recall": held_r,
        "held_f1": held_f,
        "allowed_precision": allowed_p,
        "allowed_recall": allowed_r,
        "allowed_f1": allowed_f,
    }

    summary = eval_summary("GovernanceLayer", metrics, TARGETS)
    summary["total_samples"] = len(samples)
    summary["failures"] = failures
    return summary
