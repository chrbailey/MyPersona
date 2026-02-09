"""Tests for mood detector."""

from src.engines import MoodDetector
from src.models import EmotionalQuadrant


def test_detect_neutral():
    md = MoodDetector()
    mood = md.detect("Let's discuss the project plan.")
    assert mood.quadrant == EmotionalQuadrant.NEUTRAL or abs(mood.valence) < 0.3


def test_detect_positive():
    md = MoodDetector()
    mood = md.detect("This is awesome! I'm so happy with the results!")
    assert mood.valence > 0
    assert mood.quadrant in (EmotionalQuadrant.EXCITED, EmotionalQuadrant.CALM)


def test_detect_stressed():
    md = MoodDetector()
    mood = md.detect("I'm really worried about the deadline. This is frustrating!!")
    assert mood.valence < 0
    assert mood.quadrant == EmotionalQuadrant.STRESSED


def test_detect_low():
    md = MoodDetector()
    mood = md.detect("whatever... I guess it doesn't matter...")
    # Low valence signals absent, so arousal is negative from hedging/resignation
    assert mood.arousal < 0


def test_detect_high_arousal():
    md = MoodDetector()
    mood = md.detect("THIS IS URGENT!! We need to act NOW!!!")
    assert mood.arousal > 0


def test_flashbulb_weight():
    md = MoodDetector()
    calm = md.detect("Things are okay.")
    stressed = md.detect("I'm EXTREMELY worried about EVERYTHING!!")
    assert stressed.flashbulb_weight >= calm.flashbulb_weight


def test_signals_populated():
    md = MoodDetector()
    mood = md.detect("I'm worried and frustrated about this damn project")
    assert len(mood.signals) > 0
    assert mood.confidence > 0.3


def test_confidence_increases_with_signals():
    md = MoodDetector()
    few = md.detect("ok")
    many = md.detect("This is absolutely amazing! I'm so grateful and excited!!")
    assert many.confidence >= few.confidence


def test_detect_stressed_direct():
    md = MoodDetector()
    mood = md.detect("I'm stressed about the deadline")
    assert mood.valence < 0
    assert mood.arousal > 0


def test_detect_excited_direct():
    md = MoodDetector()
    mood = md.detect("I'm excited about this project!")
    assert mood.valence > 0
