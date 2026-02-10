"""Emotional decay evaluation harness.

Tests whether emotionally-weighted retrieval ranks memories better
than pure recency. Measures nDCG@5 for decay-weighted vs recency-only baseline.
"""

from typing import List

from eval.datasets.schemas import MemoryImportanceSample
from eval.datasets.generate import load_dataset
from eval.metrics import ndcg_at_k, eval_summary
from src.memory import emotional_decay


TARGETS = {
    "decay_ndcg5": 0.70,
    "ndcg5_improvement": 0.10,  # improvement over recency baseline
}


def run(verbose: bool = False) -> dict:
    """Run decay evaluation: compare decay-weighted vs recency ranking."""
    samples = [MemoryImportanceSample.from_dict(d) for d in load_dataset("memories")]

    # Group samples by query
    by_query = {}
    for s in samples:
        if s.query not in by_query:
            by_query[s.query] = []
        by_query[s.query].append(s)

    decay_ndcg_scores = []
    recency_ndcg_scores = []

    for query, memories in by_query.items():
        if len(memories) < 2:
            continue

        n = len(memories)
        # Ground truth relevance: invert rank so rank=1 gets highest relevance
        max_rank = max(m.expected_importance_rank for m in memories)
        gt_relevance = {m.memory_id: max_rank + 1 - m.expected_importance_rank
                        for m in memories}

        # Decay-weighted scoring
        decay_scores = []
        for m in memories:
            # Simulate: raw similarity score of 1.0 (all equally relevant to query)
            # then modulated by decay
            retention = emotional_decay(m.age_hours, m.encoding_weight, m.intensity)
            decay_scores.append((m.memory_id, retention))
        decay_ranked = sorted(decay_scores, key=lambda x: x[1], reverse=True)
        decay_relevances = [gt_relevance[mid] for mid, _ in decay_ranked]

        # Recency-only baseline: sort by age ascending (newer first)
        recency_ranked = sorted(memories, key=lambda m: m.age_hours)
        recency_relevances = [gt_relevance[m.memory_id] for m in recency_ranked]

        k = min(5, n)
        decay_ndcg_scores.append(ndcg_at_k(decay_relevances, k))
        recency_ndcg_scores.append(ndcg_at_k(recency_relevances, k))

    if not decay_ndcg_scores:
        return eval_summary("EmotionalDecay", {}, TARGETS)

    avg_decay_ndcg = sum(decay_ndcg_scores) / len(decay_ndcg_scores)
    avg_recency_ndcg = sum(recency_ndcg_scores) / len(recency_ndcg_scores)
    improvement = avg_decay_ndcg - avg_recency_ndcg

    metrics = {
        "decay_ndcg5": avg_decay_ndcg,
        "recency_ndcg5": avg_recency_ndcg,
        "ndcg5_improvement": improvement,
    }

    summary = eval_summary("EmotionalDecay", metrics, TARGETS)
    summary["query_groups"] = len(decay_ndcg_scores)
    summary["per_query"] = {
        query: {
            "decay_ndcg5": round(d, 3),
            "recency_ndcg5": round(r, 3),
        }
        for query, d, r in zip(by_query.keys(), decay_ndcg_scores, recency_ndcg_scores)
    }
    return summary
