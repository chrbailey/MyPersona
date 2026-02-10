"""Multi-turn agent-based evaluation orchestrator.

Flow: conversation_agent generates persona messages → pipeline processes them →
judge_agent evaluates system performance → aggregate scores.

Requires ANTHROPIC_API_KEY. Behind --agents flag.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, List

from eval.agents.conversation_agent import PERSONAS, generate_persona_messages
from eval.agents.judge_agent import judge_conversation
from eval.metrics import eval_summary
from src.models import EngineOpinion
from src.engines import (
    MoodDetector, BeliefExtractor, AuthorityGraph, ComplianceDetector,
    RewardModel, ApproachAvoidanceDetector, PersonaEngine, GapAnalyzer,
    IntrospectiveLayer,
)
from src.belief import TruthLayer


TARGETS = {
    "avg_mood_accuracy": 6.0,
    "avg_gap_detection": 5.0,
    "avg_confidence_honesty": 6.0,
    "avg_overall": 6.0,
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


def _process(components: dict, text: str, topics: List[str]) -> dict:
    """Run a single turn through the pipeline, return analysis dict."""
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
    narration = c["intro"].analyze(mood, gap, p_opinions, r_opinions, c["truth"])

    return {
        "quadrant": mood.quadrant.value,
        "valence": round(mood.valence, 3),
        "arousal": round(mood.arousal, 3),
        "confidence": round(mood.confidence, 3),
        "signals": mood.signals[:5],
        "gap_magnitude": round(gap.overall_divergence, 3) if gap else 0.0,
        "theatre_score": round(gap.theatre_score, 3) if gap else 0.0,
        "blind_spots": narration.blind_spots[:3],
        "mood_confidence": round(narration.mood_confidence, 3),
        "reasoning_depth": narration.reasoning_depth,
    }


def run(verbose: bool = False) -> dict:
    """Run agent-based evaluation across all personas."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return eval_summary("AgentEval", {}, TARGETS)

    import anthropic
    client = anthropic.Anthropic()

    all_scores = {
        "mood_accuracy": [], "gap_detection": [],
        "confidence_honesty": [], "blind_spot_awareness": [],
        "overall": [],
    }
    persona_results = {}

    for persona in PERSONAS:
        if verbose:
            print(f"  Evaluating persona: {persona['name']}...")

        try:
            # Generate messages
            messages = generate_persona_messages(persona["id"], client)

            # Process through pipeline
            with tempfile.TemporaryDirectory() as tmp:
                components = _make_components(tmp)
                analyses = []
                for msg in messages:
                    if "error" in msg:
                        continue
                    analysis = _process(components, msg["text"], msg["topics"])
                    analyses.append(analysis)

            # Judge the performance
            scores = judge_conversation(
                persona_description=persona["system_prompt"],
                conversation=messages,
                analyses=analyses,
                client=client,
            )

            persona_results[persona["id"]] = {
                "name": persona["name"],
                "turns": len(messages),
                "scores": scores,
            }

            for key in all_scores:
                if key in scores and isinstance(scores[key], (int, float)):
                    all_scores[key].append(scores[key])

        except Exception as e:
            persona_results[persona["id"]] = {
                "name": persona["name"],
                "error": str(e),
            }

    # Aggregate
    metrics = {}
    for key, values in all_scores.items():
        if values:
            metrics[f"avg_{key}"] = sum(values) / len(values)

    summary = eval_summary("AgentEval", metrics, TARGETS)
    summary["persona_results"] = persona_results
    summary["personas_evaluated"] = len([r for r in persona_results.values() if "error" not in r])
    return summary
