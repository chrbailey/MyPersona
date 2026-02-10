"""IntrospectiveLayer evaluation harness.

Tests whether the introspective layer correctly identifies:
- Blind spots (topics with high uncertainty)
- Confidence tracking (does confidence improve with more data?)
- Reasoning depth assignment (does budget scale with complexity?)
"""

import tempfile
from pathlib import Path
from typing import Dict, List

from eval.datasets.schemas import AnnotatedConversation
from eval.datasets.generate import load_dataset
from eval.metrics import eval_summary
from src.models import EngineOpinion, GapAnalysis, TopicGap
from src.engines import (
    MoodDetector, BeliefExtractor, AuthorityGraph, ComplianceDetector,
    RewardModel, ApproachAvoidanceDetector, PersonaEngine, GapAnalyzer,
    IntrospectiveLayer,
)
from src.belief import TruthLayer


TARGETS = {
    "blind_spot_detection_rate": 0.60,
    "confidence_increases_with_data": 1.0,  # binary: does it always increase?
    "reasoning_depth_scales": 1.0,          # binary: does budget affect depth?
}


def _make_components(tmp: str) -> dict:
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
    c = components
    mood = c["mood"].detect(text)
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
    """Run introspective layer evaluation."""
    intro = IntrospectiveLayer()

    # Test 1: Blind spot detection
    # Topics with high uncertainty in one engine should be flagged
    blind_spot_tests = 0
    blind_spot_detected = 0

    # Create scenarios with known blind spots
    high_unc_p = {"unknown_topic": EngineOpinion("unknown_topic", 0.2, 0.2, 0.6, [])}
    high_unc_r = {"other_topic": EngineOpinion("other_topic", 0.1, 0.3, 0.6, [])}
    low_unc = {"clear_topic": EngineOpinion("clear_topic", 0.8, 0.1, 0.1, [])}

    # Scenario: single-engine topic should be blind spot
    truth_stub = type("TL", (), {"get_belief": lambda self, x: None})()

    narration = intro.analyze(None, None, high_unc_p, high_unc_r, truth_stub)
    blind_spot_tests += 2  # both topics should be blind spots
    for spot in narration.blind_spots:
        if "unknown_topic" in spot or "other_topic" in spot:
            blind_spot_detected += 1

    # Scenario: well-known topic should NOT be blind spot
    narration2 = intro.analyze(None, None, low_unc, low_unc, truth_stub)
    blind_spot_tests += 1
    if not any("clear_topic" in spot for spot in narration2.blind_spots):
        blind_spot_detected += 1  # correctly not flagged

    # Test 2: Confidence increases with data
    confidence_increases = 0
    confidence_tests = 0

    conversations = [AnnotatedConversation.from_dict(d) for d in load_dataset("conversations")]
    # Use authority_buildup conversations — they have multiple turns
    authority_convs = [c for c in conversations if c.scenario_type == "authority_buildup"][:5]

    for conv in authority_convs:
        if len(conv.turns) < 2:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            components = _make_components(tmp)
            confidences = []
            for turn in conv.turns:
                mood, p, r, gap = _process(components, turn.text, turn.topics)
                narration = components["intro"].analyze(
                    mood, gap, p, r, components["truth"])
                confidences.append(narration.overall_confidence)

            confidence_tests += 1
            # Confidence should generally increase (or stay same) with more data
            if confidences[-1] >= confidences[0]:
                confidence_increases += 1

    # Test 3: Reasoning depth scales with budget
    depth_tests = 3
    depth_correct = 0

    n_low = intro.analyze(None, None, {}, {}, truth_stub, thinking_budget=3000)
    if n_low.reasoning_depth == "routine":
        depth_correct += 1

    n_mid = intro.analyze(None, None, {}, {}, truth_stub, thinking_budget=8000)
    if n_mid.reasoning_depth == "deliberate":
        depth_correct += 1

    n_high = intro.analyze(None, None, {}, {}, truth_stub, thinking_budget=15000)
    if n_high.reasoning_depth == "deep":
        depth_correct += 1

    metrics = {
        "blind_spot_detection_rate": blind_spot_detected / max(1, blind_spot_tests),
        "confidence_increases_with_data": confidence_increases / max(1, confidence_tests),
        "reasoning_depth_scales": depth_correct / depth_tests,
    }

    summary = eval_summary("IntrospectiveLayer", metrics, TARGETS)
    summary["blind_spot_tests"] = blind_spot_tests
    summary["blind_spot_detected"] = blind_spot_detected
    summary["confidence_tests"] = confidence_tests
    summary["confidence_increases"] = confidence_increases
    summary["depth_correct"] = depth_correct
    return summary
