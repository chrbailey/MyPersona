"""Tests for context assembler."""

from src.models import MoodState, EmotionalQuadrant, GapAnalysis, TopicGap
from src.agent import assemble_context


def test_assemble_basic():
    mood = MoodState(valence=0.5, arousal=0.3, confidence=0.8,
                     quadrant=EmotionalQuadrant.EXCITED, signals=[])
    result = assemble_context(
        mood=mood,
        beliefs_summary={"beliefs": {}},
        gap_analysis=None,
        recent_memories=[],
        authority_info={},
        mood_trend={"trend": "stable"},
    )
    assert "valence" in result
    assert "excited" in result


def test_assemble_with_gaps():
    gap = GapAnalysis(
        topic_gaps=[TopicGap(
            topic="docs", persona_opinion=0.8, reward_opinion=0.3,
            gap_magnitude=0.5, gap_direction="persona_leads",
            conflict_severity="high", explanation="test", observations=5,
        )],
        overall_divergence=0.5,
    )
    result = assemble_context(
        mood=None,
        beliefs_summary={"beliefs": {}},
        gap_analysis=gap,
        recent_memories=[],
        authority_info={},
        mood_trend={},
    )
    assert "docs" in result
    assert "theatre_score" in result


def test_assemble_with_beliefs():
    beliefs = {
        "beliefs": {
            "b1": {"text": "Tests pass", "probability": 0.95},
            "b2": {"text": "Uncertain claim", "probability": 0.5},
        }
    }
    result = assemble_context(
        mood=None,
        beliefs_summary=beliefs,
        gap_analysis=None,
        recent_memories=[],
        authority_info={},
        mood_trend={},
    )
    assert "Tests pass" in result
