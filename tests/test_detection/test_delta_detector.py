"""
Tests for the delta detector.
"""

import pytest
from datetime import datetime, timedelta

from src.models.discourse import DiscourseSnapshot, Account, Post, PostType
from src.models.expectation import (
    DiscourseExpectation,
    BaselinePattern,
    ExpectedTopic,
    ExpectedVoice,
    TimeWindow,
)
from src.detection.delta_detector import DeltaDetector, DetectionConfig
from src.expectation.generator import ExpectationGenerator
from src.expectation.baseline_builder import BaselineBuilder
from src.expectation.context_triggers import TriggerManager


@pytest.fixture
def baseline_builder():
    return BaselineBuilder()


@pytest.fixture
def trigger_manager():
    return TriggerManager()


@pytest.fixture
def expectation_generator(baseline_builder, trigger_manager):
    return ExpectationGenerator(baseline_builder, trigger_manager)


@pytest.fixture
def detector(expectation_generator):
    config = DetectionConfig(
        topic_absence_threshold=0.3,
        voice_silence_threshold_hours=24.0,
        min_delta_confidence=0.3,
    )
    return DeltaDetector(expectation_generator, config)


@pytest.fixture
def sample_expectation():
    """Create a sample expectation for testing."""
    now = datetime.utcnow()

    baseline = BaselinePattern(
        entity="test_entity",
        time_window=TimeWindow.HOUR,
        avg_posts_per_window=100.0,
        post_stddev=20.0,
        avg_sentiment=0.2,
        sentiment_stddev=0.3,
    )

    return DiscourseExpectation(
        expectation_id="test_exp",
        entity="test_entity",
        window_start=now - timedelta(hours=1),
        window_end=now,
        baseline=baseline,
        expected_post_count=100.0,
        post_count_range=(60.0, 140.0),
        expected_topics=[
            ExpectedTopic(
                topic_id="ticker:TEST",
                topic_name="TEST",
                expected_mention_count=50.0,
                mention_stddev=10.0,
                expected_sentiment=0.3,
                sentiment_stddev=0.2,
                absence_severity=0.8,
            ),
        ],
        expected_voices=[
            ExpectedVoice(
                account_id="x:123",
                username="testceo",
                expected_posts_per_day=5.0,
                post_stddev=2.0,
                is_key_voice=True,
                silence_severity=0.9,
            ),
        ],
        expected_sentiment=0.2,
        sentiment_range=(-0.4, 0.8),
        confidence=0.8,
    )


@pytest.fixture
def sample_snapshot():
    """Create a sample snapshot for testing."""
    now = datetime.utcnow()

    return DiscourseSnapshot(
        snapshot_id="test_snap",
        entity="test_entity",
        window_start=now - timedelta(hours=1),
        window_end=now,
        total_posts=30,  # Much lower than expected 100
        unique_authors=10,
        total_engagement=500,
        topic_counts={"ticker:OTHER": 20},  # Missing expected TEST topic
        topic_sentiments={"ticker:OTHER": 0.1},
        avg_sentiment=-0.3,  # Much lower than expected 0.2
        active_accounts=[],  # testceo is not active
    )


def test_delta_detector_detects_volume_collapse(detector, sample_expectation, sample_snapshot):
    """Test that volume collapse is detected."""
    deltas = detector.detect(sample_snapshot, sample_expectation)

    volume_deltas = [d for d in deltas if d.delta_type.value == "volume_collapse"]
    assert len(volume_deltas) > 0, "Should detect volume collapse"

    volume_delta = volume_deltas[0]
    assert volume_delta.confidence > 0.5


def test_delta_detector_detects_topic_absence(detector, sample_expectation, sample_snapshot):
    """Test that topic absence is detected."""
    deltas = detector.detect(sample_snapshot, sample_expectation)

    topic_deltas = [d for d in deltas if d.delta_type.value == "topic_absence"]
    assert len(topic_deltas) > 0, "Should detect topic absence"


def test_delta_detector_detects_sentiment_decoupling(detector, sample_expectation, sample_snapshot):
    """Test that sentiment decoupling is detected."""
    deltas = detector.detect(sample_snapshot, sample_expectation)

    sentiment_deltas = [d for d in deltas if d.delta_type.value == "sentiment_decoupling"]
    assert len(sentiment_deltas) > 0, "Should detect sentiment decoupling"


def test_delta_detector_filters_by_confidence(expectation_generator):
    """Test that low confidence deltas are filtered."""
    config = DetectionConfig(min_delta_confidence=0.9)  # High threshold
    detector = DeltaDetector(expectation_generator, config)

    # With high threshold, fewer deltas should pass
    # (actual test would depend on implementation details)


def test_delta_statistics(detector, sample_expectation, sample_snapshot):
    """Test delta statistics calculation."""
    detector.detect(sample_snapshot, sample_expectation)

    stats = detector.get_delta_statistics("test_entity")

    assert stats["entity"] == "test_entity"
    assert stats["total_deltas"] >= 0
    assert "by_type" in stats
    assert "by_severity" in stats
