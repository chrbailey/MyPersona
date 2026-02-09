"""Tests for fusion module."""

from src.belief import (
    Uncertainty,
    cumulative_fuse,
    averaging_fuse,
    trust_discount,
    trust_chain,
    opinion_to_probability,
    probability_to_opinion,
    blend_uncertainty,
)


def test_cumulative_fuse_reduces_uncertainty():
    o1 = Uncertainty(belief=0.6, disbelief=0.1, uncertainty=0.3)
    o2 = Uncertainty(belief=0.5, disbelief=0.2, uncertainty=0.3)
    fused = cumulative_fuse([o1, o2])
    assert fused.uncertainty < o1.uncertainty


def test_cumulative_fuse_single():
    o = Uncertainty(belief=0.6, disbelief=0.1, uncertainty=0.3)
    fused = cumulative_fuse([o])
    assert fused is o


def test_averaging_fuse():
    o1 = Uncertainty(belief=0.6, disbelief=0.1, uncertainty=0.3)
    o2 = Uncertainty(belief=0.4, disbelief=0.3, uncertainty=0.3)
    avg = averaging_fuse([o1, o2])
    assert abs(avg.belief + avg.disbelief + avg.uncertainty - 1.0) < 1e-6


def test_trust_discount_reduces_belief():
    trust = Uncertainty(belief=0.8, disbelief=0.1, uncertainty=0.1)
    opinion = Uncertainty(belief=0.7, disbelief=0.1, uncertainty=0.2)
    result = trust_discount(trust, opinion)
    assert result.belief < opinion.belief


def test_trust_discount_low_trust():
    trust = Uncertainty(belief=0.1, disbelief=0.7, uncertainty=0.2)
    opinion = Uncertainty(belief=0.9, disbelief=0.05, uncertainty=0.05)
    result = trust_discount(trust, opinion)
    assert result.uncertainty > opinion.uncertainty


def test_trust_chain():
    t1 = Uncertainty(belief=0.8, disbelief=0.1, uncertainty=0.1)
    t2 = Uncertainty(belief=0.7, disbelief=0.1, uncertainty=0.2)
    opinion = Uncertainty(belief=0.9, disbelief=0.05, uncertainty=0.05)
    result = trust_chain([t1, t2, opinion])
    assert result.uncertainty > opinion.uncertainty


def test_opinion_to_probability():
    o = Uncertainty(belief=0.6, disbelief=0.1, uncertainty=0.3)
    p = opinion_to_probability(o, base_rate=0.5)
    assert 0.0 <= p <= 1.0
    assert p == 0.6 + 0.5 * 0.3  # 0.75


def test_probability_to_opinion():
    o = probability_to_opinion(0.7, uncertainty_level=0.2)
    assert abs(o.uncertainty - 0.2) < 1e-6
    assert abs(o.belief + o.disbelief + o.uncertainty - 1.0) < 1e-6


def test_probability_to_opinion_roundtrip():
    original_p = 0.75
    o = probability_to_opinion(original_p, uncertainty_level=0.3)
    recovered_p = opinion_to_probability(o, base_rate=0.5)
    assert abs(recovered_p - original_p) < 0.05


def test_blend_uncertainty():
    current = Uncertainty(belief=0.6, disbelief=0.1, uncertainty=0.3)
    source = Uncertainty(belief=0.3, disbelief=0.4, uncertainty=0.3)
    blended = blend_uncertainty(current, source, influence=0.5)
    assert abs(blended.belief + blended.disbelief + blended.uncertainty - 1.0) < 1e-6
    assert current.belief >= blended.belief >= source.belief or source.belief >= blended.belief >= current.belief
