"""Tests for emotional timeline."""

import tempfile
from pathlib import Path

from src.models import MoodState, EmotionalQuadrant
from src.memory import TimelineManager


def _tmp_dir():
    return Path(tempfile.mkdtemp())


def test_record_and_retrieve():
    tm = TimelineManager(_tmp_dir())
    mood = MoodState(valence=0.5, arousal=0.3, confidence=0.8,
                     quadrant=EmotionalQuadrant.EXCITED, signals=["v_excitement"])
    tm.record(mood, ["project_q3"], "sess_1")

    entries = tm.get_timeline("project_q3")
    assert len(entries) == 1
    assert entries[0]["valence"] == 0.5


def test_global_timeline():
    tm = TimelineManager(_tmp_dir())
    mood = MoodState(valence=-0.3, arousal=0.5, confidence=0.7,
                     quadrant=EmotionalQuadrant.STRESSED, signals=[])
    tm.record(mood, ["topic_a"], "sess_1")

    global_entries = tm.get_timeline()
    assert len(global_entries) == 1


def test_trend_improving():
    tm = TimelineManager(_tmp_dir())
    # Record declining then improving
    for v in [-0.5, -0.3, -0.1, 0.2, 0.5]:
        mood = MoodState(valence=v, arousal=0.3, confidence=0.7,
                         quadrant=EmotionalQuadrant.EXCITED if v > 0 else EmotionalQuadrant.STRESSED,
                         signals=[])
        tm.record(mood, ["project"])

    trend = tm.get_trend("project")
    assert trend["trend"] == "improving"


def test_get_all_topics():
    tm = TimelineManager(_tmp_dir())
    mood = MoodState(valence=0.0, arousal=0.0, confidence=0.5,
                     quadrant=EmotionalQuadrant.NEUTRAL, signals=[])
    tm.record(mood, ["topic_a", "topic_b"])

    topics = tm.get_all_topics()
    assert "topic_a" in topics
    assert "topic_b" in topics
