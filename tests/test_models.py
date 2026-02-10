"""Tests for core data models."""

from src.models import (
    MoodState, EmotionalQuadrant, EmotionalMemory,
    AuthoritySource, AuthorityTier, ComplianceProfile,
    RewardProfile, RewardType, EncodingWeight,
    EngineOpinion, TopicGap, GapAnalysis, ApproachAvoidanceData,
    HoldRequest,
)


def test_mood_state():
    mood = MoodState(valence=0.5, arousal=0.3, confidence=0.8,
                     quadrant=EmotionalQuadrant.EXCITED, signals=["v_excitement"])
    assert mood.intensity > 0
    assert mood.flashbulb_weight >= 0.5
    d = mood.to_dict()
    assert "valence" in d
    assert "quadrant" in d


def test_authority_source_opinion():
    src = AuthoritySource(source_id="boss", name="Boss", tier=AuthorityTier.INSTITUTIONAL,
                          trust_weight=0.8)
    o = src.to_opinion()
    assert abs(o["belief"] + o["disbelief"] + o["uncertainty"] - 1.0) < 0.01


def test_compliance_profile():
    cp = ComplianceProfile()
    initial = cp.compliance_score
    cp.observe_compliance("should_do")
    assert cp.compliance_score > initial
    cp.observe_defiance("resistance")
    assert len(cp.signals_observed) == 2


def test_reward_profile():
    rp = RewardProfile()
    for _ in range(6):
        rp.observe("shipping", 0.5)
    assert rp.reward_type == RewardType.ACHIEVEMENT


def test_encoding_weight():
    ew = EncodingWeight(flashbulb=0.8, authority_relevance=0.7,
                        reward_alignment=0.3, conflict_score=0.4)
    assert ew.total_weight > 0
    assert "high emotional intensity" in ew.explain() or "conflict" in ew.explain()


def test_engine_opinion():
    eo = EngineOpinion(topic="docs", belief=0.7, disbelief=0.1,
                       uncertainty=0.2, source_signals=["espoused"])
    assert eo.expected_value > 0.5
    d = eo.to_dict()
    assert d["topic"] == "docs"


def test_topic_gap():
    gap = TopicGap(topic="docs", persona_opinion=0.8, reward_opinion=0.3,
                   gap_magnitude=0.5, gap_direction="persona_leads",
                   conflict_severity="high", explanation="test",
                   observations=5)
    assert gap.is_significant
    d = gap.to_dict()
    assert d["gap"] == 0.5


def test_gap_analysis():
    ga = GapAnalysis(
        topic_gaps=[
            TopicGap(topic="docs", persona_opinion=0.8, reward_opinion=0.3,
                     gap_magnitude=0.5, gap_direction="persona_leads",
                     conflict_severity="high", explanation="test", observations=5),
        ],
        overall_divergence=0.5,
    )
    assert ga.theatre_score > 0
    assert len(ga.significant_gaps) == 1


def test_approach_avoidance():
    aa = ApproachAvoidanceData(topic="shipping", approach_count=8, avoidance_count=2,
                               observations=10, total_valence=3.0, total_arousal=2.0)
    assert aa.approach_ratio == 0.8
    assert aa.avg_valence == 0.3


def test_emotional_memory():
    mood = MoodState(valence=-0.5, arousal=0.7, confidence=0.8,
                     quadrant=EmotionalQuadrant.STRESSED, signals=["v_worry"])
    mem = EmotionalMemory(content="test memory", mood=mood, topic_tags=["test"])
    record = mem.to_pinecone_record()
    assert record["content"] == "test memory"
    assert record["valence"] == -0.5
    assert record["related_ids"] == []


def test_emotional_memory_with_links():
    mem = EmotionalMemory(content="linked memory", related_ids=["mem_a", "mem_b"])
    record = mem.to_pinecone_record()
    assert record["related_ids"] == ["mem_a", "mem_b"]


def test_introspective_narration():
    from src.models import IntrospectiveNarration
    n = IntrospectiveNarration(
        mood_confidence=0.8, gap_confidence=0.6, belief_coverage=0.5,
        blind_spots=[], strongest_signal="v_excitement",
        reasoning_depth="deliberate", thinking_budget_used=8000,
    )
    assert n.overall_confidence > 0.6
    assert "confident" in n.narrative()
    d = n.to_dict()
    assert d["reasoning_depth"] == "deliberate"


def test_hold_request():
    h = HoldRequest(action="delete_memory", target_id="mem_123",
                    reason="promoted memory")
    assert h.status == "pending"
    assert h.hold_id.startswith("hold_")
