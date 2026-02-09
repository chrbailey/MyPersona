"""Tests for truth layer."""

import tempfile
from pathlib import Path
from src.belief import Belief, BayesianNetwork, TruthLayer


def test_belief_probability():
    b = Belief(alpha=3.0, beta=1.0)
    assert b.probability == 0.75


def test_belief_variance():
    b = Belief(alpha=1.0, beta=1.0)
    assert abs(b.variance - 1/12) < 1e-6


def test_bayesian_network():
    net = BayesianNetwork()
    net.add_node("a", "claim A")
    net.add_node("b", "claim B")
    net.add_edge("a", "b", 0.8)

    net.update_belief("a", True, strength=10.0)
    net.propagate()

    assert net.beliefs["a"].probability > 0.5
    assert net.beliefs["b"].probability > 0.5


def test_truth_layer_add_and_validate():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    tl = TruthLayer(path=path)
    tl.add_claim("test_claim", "The sky is blue", "science")
    tl.validate("test_claim", "confirm")

    assert tl.get_probability("test_claim") > 0.9
    Path(path).unlink(missing_ok=True)


def test_truth_layer_reject():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    tl = TruthLayer(path=path)
    tl.add_claim("bad_claim", "Earth is flat", "science")
    tl.validate("bad_claim", "reject")

    assert tl.get_probability("bad_claim") < 0.1
    Path(path).unlink(missing_ok=True)


def test_truth_layer_context():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    tl = TruthLayer(path=path)
    tl.add_claim("c1", "Python is great", "tech")
    tl.validate("c1", "confirm")

    ctx = tl.get_truth_context()
    assert "Python is great" in ctx
    Path(path).unlink(missing_ok=True)


def test_truth_layer_stats():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    tl = TruthLayer(path=path)
    tl.add_claim("s1", "claim 1")
    tl.add_claim("s2", "claim 2")
    s = tl.stats()
    assert s["total_claims"] == 2
    Path(path).unlink(missing_ok=True)


def test_truth_layer_persistence():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    tl = TruthLayer(path=path)
    tl.add_claim("persist", "persistent claim")
    tl.validate("persist", "confirm")

    tl2 = TruthLayer(path=path)
    assert tl2.get_probability("persist") > 0.9
    Path(path).unlink(missing_ok=True)
