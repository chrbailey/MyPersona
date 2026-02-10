"""Tests for dual-engine components."""

import tempfile
from pathlib import Path

from src.models import (
    MoodState, EmotionalQuadrant, ComplianceProfile,
    AuthorityTier, RewardProfile, RewardType, EngineOpinion,
)
from src.engines import (
    AuthorityGraph, ComplianceDetector, RewardModel,
    ApproachAvoidanceDetector, GapAnalyzer, classify_severity,
    compute_encoding_weight,
)


def _tmp_dir():
    return Path(tempfile.mkdtemp())


def test_authority_graph():
    ag = AuthorityGraph(_tmp_dir())
    src = ag.add_source("boss_sarah", "Sarah", AuthorityTier.INSTITUTIONAL,
                        trust_weight=0.82, influence_topics=["docs"])
    assert src.trust_weight == 0.82

    discounted = ag.discount_opinion("boss_sarah", 0.9)
    assert discounted is not None
    assert discounted.expected_value < 0.9  # Trust-discounted


def test_authority_reference_tracking():
    ag = AuthorityGraph(_tmp_dir())
    ag.add_source("boss", "Boss", AuthorityTier.INSTITUTIONAL)
    ag.reference("boss")
    assert ag.sources["boss"].reference_count == 1


def test_compliance_detector():
    cd = ComplianceDetector(_tmp_dir())
    cd.analyze("I should follow the policy and do what's required")
    assert cd.profile.compliance_score > 0.6


def test_compliance_defiance():
    cd = ComplianceDetector(_tmp_dir())
    cd.analyze("Whatever, I prefer my way. This is pointless bureaucracy")
    assert cd.profile.compliance_score < 0.6


def test_reward_model():
    rm = RewardModel(_tmp_dir())
    for _ in range(6):
        rm.observe("shipping", 0.6)
    assert rm.reward_type == RewardType.ACHIEVEMENT


def test_approach_avoidance():
    aad = ApproachAvoidanceDetector(_tmp_dir())
    mood = MoodState(valence=0.5, arousal=0.3, confidence=0.7,
                     quadrant=EmotionalQuadrant.EXCITED, signals=[])
    result = aad.analyze(
        "I want to ship this! Let me add another feature! What if we also...",
        "shipping", mood
    )
    assert result.approach_count >= 1


def test_gap_analyzer():
    ga = GapAnalyzer(_tmp_dir())

    persona = {"docs": EngineOpinion(topic="docs", belief=0.7, disbelief=0.1,
                                      uncertainty=0.2, source_signals=["authority"])}
    reward = {"docs": EngineOpinion(topic="docs", belief=0.2, disbelief=0.5,
                                     uncertainty=0.3, source_signals=["avoidance"])}

    analysis = ga.analyze(persona, reward)
    assert len(analysis.topic_gaps) == 1
    assert analysis.topic_gaps[0].gap_magnitude > 0.2


def test_classify_severity():
    assert classify_severity(0.05) == "none"
    assert classify_severity(0.15) == "low"
    assert classify_severity(0.35) == "moderate"
    assert classify_severity(0.55) == "high"
    assert classify_severity(0.75) == "critical"


def test_explain_behavior():
    ga = GapAnalyzer(_tmp_dir())
    from src.models import GapAnalysis, TopicGap
    analysis = GapAnalysis(
        topic_gaps=[TopicGap(
            topic="docs", persona_opinion=0.8, reward_opinion=0.3,
            gap_magnitude=0.5, gap_direction="persona_leads",
            conflict_severity="high", explanation="test", observations=5
        )],
        overall_divergence=0.5,
    )
    explanation = ga.explain_behavior("procrastination on docs", analysis)
    assert "Persona Engine" in explanation


def test_reward_model_with_topic_mapping():
    from src.engines import TOPIC_TO_REWARD_MAP
    rm = RewardModel(_tmp_dir())
    for _ in range(6):
        cat = TOPIC_TO_REWARD_MAP.get("shipping", "shipping")
        rm.observe(cat, 0.6)
    assert rm.reward_type == RewardType.ACHIEVEMENT


def test_encoding_weight():
    mood = MoodState(valence=-0.3, arousal=0.7, confidence=0.8,
                     quadrant=EmotionalQuadrant.STRESSED, signals=[])
    from src.models import AuthoritySource
    authority = AuthoritySource(
        source_id="boss", name="Boss", tier=AuthorityTier.INSTITUTIONAL,
        trust_weight=0.8
    )
    compliance = ComplianceProfile(alpha=5.0, beta=3.0)
    reward = RewardProfile(reward_type=RewardType.ACHIEVEMENT)

    ew = compute_encoding_weight(mood, authority, reward, compliance, "shipping")
    assert ew.total_weight > 0
    assert ew.flashbulb > 0.5  # High arousal = high flashbulb


def test_introspective_layer_low_data():
    """With minimal data, introspection should show low confidence and blind spots."""
    from src.engines import IntrospectiveLayer
    from src.belief import TruthLayer
    layer = IntrospectiveLayer()
    mood = MoodState(valence=0.2, arousal=0.1, confidence=0.3,
                     quadrant=EmotionalQuadrant.NEUTRAL, signals=["v_satisfaction"])
    tl = TruthLayer()

    persona = {"work": EngineOpinion(topic="work", belief=0.5, disbelief=0.1,
                                     uncertainty=0.4, source_signals=[])}
    reward = {"work": EngineOpinion(topic="work", belief=0.6, disbelief=0.1,
                                    uncertainty=0.3, source_signals=[])}
    narration = layer.analyze(mood, None, persona, reward, tl, thinking_budget=5000)

    assert narration.mood_confidence == 0.3
    assert narration.gap_confidence == 0.0  # no gap analysis
    assert len(narration.blind_spots) >= 1  # work has high uncertainty
    assert narration.reasoning_depth == "routine"
    assert "guessing" in narration.narrative()


def test_introspective_layer_high_data():
    """With solid data, introspection should show high confidence."""
    from src.engines import IntrospectiveLayer
    from src.models import GapAnalysis, TopicGap
    from src.belief import TruthLayer

    layer = IntrospectiveLayer()
    mood = MoodState(valence=0.5, arousal=0.3, confidence=0.85,
                     quadrant=EmotionalQuadrant.EXCITED,
                     signals=["v_excitement", "v_satisfaction", "a_intensity"])
    tl = TruthLayer()
    tl.add_claim("shipping", "Shipping is important", "work")
    for _ in range(10):
        tl.validate("shipping", "confirm")

    persona = {"shipping": EngineOpinion(topic="shipping", belief=0.8, disbelief=0.1,
                                         uncertainty=0.1, source_signals=["authority:boss"])}
    reward = {"shipping": EngineOpinion(topic="shipping", belief=0.7, disbelief=0.1,
                                        uncertainty=0.2, source_signals=[])}
    gap = GapAnalysis(topic_gaps=[
        TopicGap(topic="shipping", persona_opinion=0.85, reward_opinion=0.75,
                 gap_magnitude=0.1, gap_direction="persona_leads",
                 conflict_severity="none", explanation="aligned", observations=12)
    ])

    narration = layer.analyze(mood, gap, persona, reward, tl, thinking_budget=12000)

    assert narration.mood_confidence == 0.85
    assert narration.gap_confidence > 0.5
    assert narration.reasoning_depth == "deep"
    assert "confident" in narration.narrative()


def test_introspective_narration_narrative():
    """Test the human-readable narrative generation."""
    from src.models import IntrospectiveNarration
    n = IntrospectiveNarration(
        mood_confidence=0.3, gap_confidence=0.2, belief_coverage=0.1,
        blind_spots=["career (persona uncertain)", "health (single-engine only)"],
        would_change_mind=["more emotional signals"],
    )
    text = n.narrative()
    assert "guessing" in text
    assert "career" in text
    assert "change my read" in text
