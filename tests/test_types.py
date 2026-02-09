"""Tests for belief types."""

from src.belief import Uncertainty, DecomposedUncertainty


def test_uncertainty_creation():
    u = Uncertainty(belief=0.6, disbelief=0.1, uncertainty=0.3)
    assert abs(u.belief + u.disbelief + u.uncertainty - 1.0) < 1e-6
    assert u.confidence == 0.7


def test_uncertainty_expected_value():
    u = Uncertainty(belief=0.8, disbelief=0.1, uncertainty=0.1)
    ev = u.expected_value
    assert 0.0 <= ev <= 1.0
    assert ev > 0.5


def test_uncertainty_uniform():
    u = Uncertainty.uniform()
    assert abs(u.belief - 1/3) < 1e-6
    assert abs(u.expected_value - 0.5) < 0.01


def test_uncertainty_from_confidence():
    u = Uncertainty.from_confidence(0.8)
    assert abs(u.belief - 0.8) < 1e-6
    assert abs(u.disbelief) < 1e-6
    assert abs(u.uncertainty - 0.2) < 1e-6


def test_uncertainty_from_beta():
    u = Uncertainty.from_beta(alpha=5.0, beta=2.0)
    assert u.belief > u.disbelief
    assert u.expected_value > 0.5


def test_uncertainty_credible_interval():
    u = Uncertainty(belief=0.6, disbelief=0.1, uncertainty=0.3)
    lo, hi = u.credible_interval(0.9)
    assert lo < hi
    assert 0.0 <= lo <= 1.0
    assert 0.0 <= hi <= 1.0


def test_decomposed_uncertainty():
    du = DecomposedUncertainty(mean=0.7, epistemic_variance=0.1, aleatoric_variance=0.02)
    assert abs(du.total_variance - 0.12) < 1e-10
    assert du.epistemic_fraction > 0.5
    assert du.should_gather_more_evidence()


def test_decomposed_uniform_prior():
    du = DecomposedUncertainty.uniform_prior()
    assert du.mean == 0.5
    assert du.epistemic_variance == 0.25
