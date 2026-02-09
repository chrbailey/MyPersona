"""Tests for decomposition functions."""

from src.belief import Uncertainty, DecomposedUncertainty, decompose_from_beta, decompose_from_opinion


def test_decompose_from_beta():
    du = decompose_from_beta(alpha=10.0, beta=3.0)
    assert 0.0 <= du.mean <= 1.0
    assert du.epistemic_variance >= 0
    assert du.aleatoric_variance >= 0
    assert du.n_observations > 0


def test_decompose_from_beta_uniform():
    du = decompose_from_beta(alpha=1.0, beta=1.0)
    assert abs(du.mean - 0.5) < 0.01
    assert du.epistemic_variance > 0


def test_decompose_from_opinion():
    o = Uncertainty(belief=0.6, disbelief=0.1, uncertainty=0.3)
    du = decompose_from_opinion(o)
    assert 0.0 <= du.mean <= 1.0
    assert du.epistemic_variance > 0
