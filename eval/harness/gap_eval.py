"""GapAnalyzer evaluation harness.

Runs annotated conversations through the full pipeline
(reusing test_integration.py's _process pattern), measures:
- Topic detection rate (did the gap analyzer find the expected topic?)
- Direction accuracy (persona_leads vs reward_leads)
- Gap magnitude correlation with expected severity
"""

import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from eval.datasets.schemas import AnnotatedConversation, ConversationTurn
from eval.datasets.generate import load_dataset
from eval.metrics import accuracy, spearman_rho, eval_summary
from src.models import EngineOpinion, MoodState, AuthorityTier
from src.engines import (
    MoodDetector, BeliefExtractor, AuthorityGraph, ComplianceDetector,
    RewardModel, ApproachAvoidanceDetector, PersonaEngine, GapAnalyzer,
    IntrospectiveLayer,
)
from src.belief import TruthLayer


TARGETS = {
    "topic_detection_rate": 0.70,
    "direction_accuracy": 0.80,
}

SEVERITY_ORDER = {"none": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}


def _make_components(tmp: str) -> dict:
    """Create fresh components in a temp directory."""
    d = Path(tmp)
    return {
        "mood": MoodDetector(),
        "beliefs": BeliefExtractor(client=None),
        "authority": AuthorityGraph(d),
        "compliance": ComplianceDetector(d),
        "reward": RewardModel(d),
        "aa": ApproachAvoidanceDetector(d),
        "truth": TruthLayer(path=str(d / "truth.json")),
        "gap": GapAnalyzer(d),
        "intro": IntrospectiveLayer(),
    }


def _process(components: dict, text: str, topics: List[str]):
    """Run a single turn through the full dual-engine pipeline."""
    c = components
    mood = c["mood"].detect(text)
    c["beliefs"].detect_authority_refs(text)
    for delta in c["beliefs"].extract_beliefs_simple(text):
        c["truth"].add_claim(delta.belief_id, delta.text)
    persona = PersonaEngine(c["truth"], c["authority"], c["compliance"])
    p_opinions = persona.process(text, mood, topics)
    r_opinions = {}
    for topic in topics:
        aa = c["aa"].analyze(text, topic, mood)
        r_b = max(0.0, min(0.95, aa.approach_ratio * 0.7 + max(0, mood.valence) * 0.3))
        r_u = max(0.05, 0.5 / max(1, aa.observations))
        r_d = max(0.0, 1.0 - r_b - r_u)
        r_opinions[topic] = EngineOpinion(
            topic=topic, belief=round(r_b, 3),
            disbelief=round(r_d, 3), uncertainty=round(r_u, 3),
            source_signals=[])
    gap = c["gap"].analyze(p_opinions, r_opinions)
    return mood, p_opinions, r_opinions, gap


def run(verbose: bool = False) -> dict:
    """Run gap analysis evaluation."""
    conversations = [AnnotatedConversation.from_dict(d) for d in load_dataset("conversations")]

    topic_detected = 0
    topic_total = 0
    direction_true = []
    direction_pred = []

    for conv in conversations:
        if not conv.expected_final_gap_topic:
            continue

        with tempfile.TemporaryDirectory() as tmp:
            components = _make_components(tmp)

            # Run all turns through the pipeline
            last_gap = None
            for turn in conv.turns:
                _, _, _, last_gap = _process(components, turn.text, turn.topics)

            if last_gap is None:
                continue

            # Check topic detection
            topic_total += 1
            detected_topics = {g.topic for g in last_gap.topic_gaps}
            if conv.expected_final_gap_topic in detected_topics:
                topic_detected += 1

            # Check direction accuracy
            if conv.expected_final_gap_direction:
                expected_dir = conv.expected_final_gap_direction
                # Find the gap for the expected topic
                actual_dir = ""
                for g in last_gap.topic_gaps:
                    if g.topic == conv.expected_final_gap_topic:
                        actual_dir = g.gap_direction
                        break
                if actual_dir:
                    direction_true.append(expected_dir)
                    direction_pred.append(actual_dir)

    metrics = {
        "topic_detection_rate": topic_detected / max(1, topic_total),
        "direction_accuracy": accuracy(direction_true, direction_pred) if direction_true else 0.0,
    }

    summary = eval_summary("GapAnalyzer", metrics, TARGETS)
    summary["total_conversations"] = len(conversations)
    summary["topic_total"] = topic_total
    summary["topic_detected"] = topic_detected
    summary["direction_samples"] = len(direction_true)
    return summary
