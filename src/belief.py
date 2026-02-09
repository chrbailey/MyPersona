"""
Belief math: subjective logic, fusion, truth maintenance, decomposition.
Consolidated from belief-math and unified-belief-system ports.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# =============================================================================
# UNCERTAINTY (Subjective Logic Opinion Triple)
# =============================================================================

@dataclass(frozen=True)
class Uncertainty:
    belief: float
    disbelief: float
    uncertainty: float
    sample_size: float = 2.0

    def __post_init__(self) -> None:
        if self.belief < 0.0 or self.disbelief < 0.0 or self.uncertainty < 0.0:
            raise ValueError(
                f"All components must be >= 0: "
                f"b={self.belief}, d={self.disbelief}, u={self.uncertainty}"
            )
        total = self.belief + self.disbelief + self.uncertainty
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Components must sum to 1.0 (got {total:.10f}): "
                f"b={self.belief}, d={self.disbelief}, u={self.uncertainty}"
            )
        if self.sample_size <= 0.0:
            raise ValueError(f"sample_size must be positive (got {self.sample_size})")

    @property
    def alpha(self) -> float:
        return self.belief * self.sample_size + 1.0

    @property
    def beta_param(self) -> float:
        return self.disbelief * self.sample_size + 1.0

    @property
    def expected_value(self) -> float:
        a = self.alpha
        b = self.beta_param
        return a / (a + b)

    @property
    def confidence(self) -> float:
        return 1.0 - self.uncertainty

    @property
    def aleatoric_component(self) -> float:
        if self.sample_size <= 10.0:
            return 0.0
        a = self.alpha
        b = self.beta_param
        total = a + b
        return (a * b) / (total * total * (total + 1.0))

    @property
    def epistemic_fraction(self) -> float:
        aleatoric = self.aleatoric_component
        total_unc = self.uncertainty + aleatoric
        return self.uncertainty / max(total_unc, 1e-10)

    def credible_interval(self, width: float = 0.9) -> Tuple[float, float]:
        if not (0.0 < width < 1.0):
            raise ValueError(f"width must be in (0, 1), got {width}")
        a = self.alpha
        b = self.beta_param
        mean = a / (a + b)
        var = (a * b) / ((a + b) ** 2 * (a + b + 1.0))
        std = math.sqrt(var)
        tail = (1.0 - width) / 2.0
        z = self._approx_inv_normal(1.0 - tail)
        lower = max(0.0, mean - z * std)
        upper = min(1.0, mean + z * std)
        return (lower, upper)

    @staticmethod
    def _approx_inv_normal(p: float) -> float:
        if p <= 0.5:
            return -Uncertainty._approx_inv_normal(1.0 - p)
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        t = math.sqrt(-2.0 * math.log(1.0 - p))
        return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)

    @classmethod
    def uniform(cls) -> Uncertainty:
        return cls(belief=1.0 / 3.0, disbelief=1.0 / 3.0, uncertainty=1.0 / 3.0)

    @classmethod
    def from_confidence(cls, conf: float) -> Uncertainty:
        if not (0.0 <= conf <= 1.0):
            raise ValueError(f"conf must be in [0, 1], got {conf}")
        return cls(belief=conf, disbelief=0.0, uncertainty=1.0 - conf)

    @classmethod
    def from_beta(cls, alpha: float, beta: float) -> Uncertainty:
        if alpha < 1.0 or beta < 1.0:
            raise ValueError(f"Alpha and beta must be >= 1 (got alpha={alpha}, beta={beta})")
        w = (alpha - 1.0) + (beta - 1.0)
        if w < 1e-10:
            return cls.uniform()
        b = (alpha - 1.0) / w
        d = (beta - 1.0) / w
        u = max(0.0, 1.0 - b - d)
        return cls(belief=b, disbelief=d, uncertainty=u, sample_size=w)

    def __repr__(self) -> str:
        return (
            f"Uncertainty(b={self.belief:.3f}, d={self.disbelief:.3f}, "
            f"u={self.uncertainty:.3f}, W={self.sample_size:.1f})"
        )


# =============================================================================
# DECOMPOSED UNCERTAINTY (Epistemic/Aleatoric Split)
# =============================================================================

@dataclass
class DecomposedUncertainty:
    mean: float
    epistemic_variance: float
    aleatoric_variance: float
    n_observations: int = 0
    evidence_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0 <= self.mean <= 1:
            raise ValueError(f"Mean must be in [0,1], got {self.mean}")
        if self.epistemic_variance < 0:
            raise ValueError("Epistemic variance must be non-negative")
        if self.aleatoric_variance < 0:
            raise ValueError("Aleatoric variance must be non-negative")

    @property
    def total_variance(self) -> float:
        return self.epistemic_variance + self.aleatoric_variance

    @property
    def total_std(self) -> float:
        return self.total_variance ** 0.5

    @property
    def epistemic_fraction(self) -> float:
        if self.total_variance == 0:
            return 0.0
        return self.epistemic_variance / self.total_variance

    @property
    def confidence(self) -> float:
        return 1.0 / (1.0 + 4.0 * self.epistemic_variance)

    def should_gather_more_evidence(self, threshold: float = 0.3) -> bool:
        return self.epistemic_fraction > threshold

    def expected_information_gain(self, new_evidence_reliability: float = 0.8) -> float:
        reduction_factor = new_evidence_reliability / (1 + self.n_observations * 0.1)
        return self.epistemic_variance * reduction_factor

    @classmethod
    def uniform_prior(cls) -> DecomposedUncertainty:
        return cls(mean=0.5, epistemic_variance=0.25, aleatoric_variance=0.0, n_observations=0)

    @classmethod
    def from_beta(cls, alpha: float, beta: float) -> DecomposedUncertainty:
        mean = alpha / (alpha + beta)
        total_var = (alpha * beta) / ((alpha + beta)**2 * (alpha + beta + 1))
        n_obs = alpha + beta - 2
        epistemic_fraction = 1.0 / (1.0 + n_obs * 0.1) if n_obs > 0 else 1.0
        return cls(
            mean=mean,
            epistemic_variance=total_var * epistemic_fraction,
            aleatoric_variance=total_var * (1 - epistemic_fraction),
            n_observations=max(0, int(n_obs)),
        )


# =============================================================================
# FUSION OPERATORS (Subjective Logic)
# =============================================================================

def _normalize_opinion(b: float, d: float, u: float) -> Tuple[float, float, float]:
    b = max(0.0, b)
    d = max(0.0, d)
    u = max(0.0, u)
    total = b + d + u
    if total < 1e-12:
        third = 1.0 / 3.0
        return (third, third, third)
    return (b / total, d / total, u / total)


def cumulative_fuse(opinions: List[Uncertainty]) -> Uncertainty:
    if not opinions:
        raise ValueError("Cannot fuse an empty list of opinions")
    if len(opinions) == 1:
        return opinions[0]

    def _fuse_pair(a: Uncertainty, b: Uncertainty) -> Uncertainty:
        denom = a.uncertainty + b.uncertainty - a.uncertainty * b.uncertainty
        if abs(denom) < 1e-12:
            total_w = a.sample_size + b.sample_size
            if total_w < 1e-12:
                return Uncertainty.uniform()
            fb = (a.belief * a.sample_size + b.belief * b.sample_size) / total_w
            fd = (a.disbelief * a.sample_size + b.disbelief * b.sample_size) / total_w
            fu = 0.0
        else:
            fb = (a.belief * b.uncertainty + b.belief * a.uncertainty) / denom
            fd = (a.disbelief * b.uncertainty + b.disbelief * a.uncertainty) / denom
            fu = (a.uncertainty * b.uncertainty) / denom
        nb, nd, nu = _normalize_opinion(fb, fd, fu)
        return Uncertainty(belief=nb, disbelief=nd, uncertainty=nu,
                          sample_size=a.sample_size + b.sample_size)

    result = opinions[0]
    for opinion in opinions[1:]:
        result = _fuse_pair(result, opinion)
    return result


def averaging_fuse(opinions: List[Uncertainty]) -> Uncertainty:
    if not opinions:
        raise ValueError("Cannot fuse an empty list of opinions")
    if len(opinions) == 1:
        return opinions[0]

    total_weight = sum(o.sample_size for o in opinions)
    if total_weight < 1e-12:
        n = len(opinions)
        fb = sum(o.belief for o in opinions) / n
        fd = sum(o.disbelief for o in opinions) / n
        fu = sum(o.uncertainty for o in opinions) / n
    else:
        fb = sum(o.belief * o.sample_size for o in opinions) / total_weight
        fd = sum(o.disbelief * o.sample_size for o in opinions) / total_weight
        fu = sum(o.uncertainty * o.sample_size for o in opinions) / total_weight

    nb, nd, nu = _normalize_opinion(fb, fd, fu)
    max_sample = max(o.sample_size for o in opinions)
    return Uncertainty(belief=nb, disbelief=nd, uncertainty=nu, sample_size=max_sample)


def trust_discount(trustor_opinion: Uncertainty, trusted_opinion: Uncertainty) -> Uncertainty:
    fb = trustor_opinion.belief * trusted_opinion.belief
    fd = trustor_opinion.belief * trusted_opinion.disbelief
    fu = (trustor_opinion.disbelief + trustor_opinion.uncertainty
          + trustor_opinion.belief * trusted_opinion.uncertainty)
    nb, nd, nu = _normalize_opinion(fb, fd, fu)
    return Uncertainty(belief=nb, disbelief=nd, uncertainty=nu,
                      sample_size=trustor_opinion.sample_size)


def trust_chain(opinions: List[Uncertainty]) -> Uncertainty:
    if not opinions:
        raise ValueError("Cannot compute trust chain from an empty list")
    if len(opinions) == 1:
        return opinions[0]
    result = opinions[-1]
    for trust_opinion in reversed(opinions[:-1]):
        result = trust_discount(trust_opinion, result)
    return result


def opinion_to_probability(opinion: Uncertainty, base_rate: float = 0.5) -> float:
    if not (0.0 <= base_rate <= 1.0):
        raise ValueError(f"base_rate must be in [0, 1], got {base_rate}")
    projected = opinion.belief + base_rate * opinion.uncertainty
    return max(0.0, min(1.0, projected))


def probability_to_opinion(
    probability: float, uncertainty_level: float = 0.3, base_rate: float = 0.5,
) -> Uncertainty:
    if not (0.0 <= probability <= 1.0):
        raise ValueError(f"probability must be in [0, 1], got {probability}")
    if not (0.0 <= uncertainty_level < 1.0):
        raise ValueError(f"uncertainty_level must be in [0, 1), got {uncertainty_level}")
    if not (0.0 <= base_rate <= 1.0):
        raise ValueError(f"base_rate must be in [0, 1], got {base_rate}")

    if uncertainty_level < 1e-12:
        return Uncertainty(belief=probability, disbelief=1.0 - probability,
                          uncertainty=0.0, sample_size=2.0)

    denom = 1.0 - uncertainty_level
    fb = (probability - base_rate * uncertainty_level) / denom
    fd = ((1.0 - probability) - (1.0 - base_rate) * uncertainty_level) / denom
    fb = max(0.0, fb)
    fd = max(0.0, fd)
    bd_sum = fb + fd
    available = 1.0 - uncertainty_level

    if bd_sum < 1e-12:
        fb = available / 2.0
        fd = available / 2.0
    else:
        fb = fb / bd_sum * available
        fd = fd / bd_sum * available

    return Uncertainty(belief=fb, disbelief=fd, uncertainty=uncertainty_level, sample_size=2.0)


def blend_uncertainty(current: Uncertainty, source: Uncertainty, influence: float) -> Uncertainty:
    influence = max(0.0, min(1.0, influence))
    new_b = (1.0 - influence) * current.belief + influence * source.belief
    new_d = (1.0 - influence) * current.disbelief + influence * source.disbelief
    new_u = (1.0 - influence) * current.uncertainty + influence * source.uncertainty

    total = new_b + new_d + new_u
    if total < 1e-12:
        return Uncertainty.uniform()
    new_b /= total
    new_d /= total
    new_u /= total

    new_sample = (1.0 - influence) * current.sample_size + influence * source.sample_size
    new_sample = max(new_sample, 1e-6)
    return Uncertainty(belief=new_b, disbelief=new_d, uncertainty=new_u, sample_size=new_sample)


# =============================================================================
# DECOMPOSITION FUNCTIONS
# =============================================================================

def decompose_from_beta(alpha: float, beta: float, prior_strength: float = 2.0) -> DecomposedUncertainty:
    mean = alpha / (alpha + beta)
    total_var = (alpha * beta) / ((alpha + beta)**2 * (alpha + beta + 1))
    n_observations = alpha + beta - prior_strength

    if n_observations > 0:
        epistemic_fraction = 1.0 / (1.0 + n_observations * 0.5)
    else:
        epistemic_fraction = 1.0

    distance_from_half = abs(mean - 0.5)
    aleatoric_boost = 1.0 - distance_from_half * 2
    epistemic_var = total_var * epistemic_fraction * (1 - aleatoric_boost * 0.5)
    aleatoric_var = total_var - epistemic_var

    return DecomposedUncertainty(
        mean=mean,
        epistemic_variance=max(0, epistemic_var),
        aleatoric_variance=max(0, aleatoric_var),
        n_observations=max(0, int(n_observations)),
    )


def decompose_from_opinion(opinion: Uncertainty) -> DecomposedUncertainty:
    mean = opinion.expected_value
    epistemic_var = opinion.uncertainty * 0.25
    confidence = 1.0 - opinion.uncertainty
    aleatoric_var = opinion.aleatoric_component if confidence > 0 else 0.0
    return DecomposedUncertainty(
        mean=mean,
        epistemic_variance=epistemic_var,
        aleatoric_variance=aleatoric_var,
        n_observations=int(opinion.sample_size),
    )


# =============================================================================
# TRUTH LAYER (Bayesian Truth-Maintenance)
# =============================================================================

@dataclass
class Belief:
    alpha: float = 1.0
    beta: float = 1.0
    text: str = ""
    category: str = "general"

    @property
    def probability(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        total = self.alpha + self.beta
        return (self.alpha * self.beta) / ((total ** 2) * (total + 1))


class BayesianNetwork:
    def __init__(self):
        self.beliefs: Dict[str, Belief] = {}
        self.edges: Dict[str, List[Tuple[str, float]]] = {}
        self.anchored: Dict[str, bool] = {}

    def add_node(self, cid: str, text: str, category: str = "general"):
        if cid not in self.beliefs:
            self.beliefs[cid] = Belief(alpha=1.0, beta=1.0, text=text, category=category)
            self.edges[cid] = []

    def add_edge(self, parent: str, child: str, weight: float):
        self.edges.setdefault(child, []).append((parent, weight))

    def update_belief(self, cid: str, supports: bool, strength: float = 1.0):
        if cid not in self.beliefs:
            return
        b = self.beliefs[cid]
        if supports:
            b.alpha += strength
        else:
            b.beta += strength
        self.anchored[cid] = True

    def propagate(self, steps: int = 20, damping: float = 0.85):
        for _ in range(steps):
            updates = {}
            for child, parents in list(self.edges.items()):
                if not parents:
                    continue
                influence = 0.0
                total_weight = 0.0
                for parent_cid, w in parents:
                    if parent_cid not in self.beliefs:
                        continue
                    p = self.beliefs[parent_cid].probability
                    centered = 2.0 * p - 1.0
                    influence += w * centered
                    total_weight += abs(w)
                if total_weight > 0:
                    influence = influence / total_weight * damping
                strength = abs(influence) * 12.0
                virtual_alpha = 1.0 + strength if influence > 0 else 1.0
                virtual_beta = 1.0 + strength if influence < 0 else 1.0
                updates[child] = (virtual_alpha, virtual_beta)

            for cid, (v_alpha, v_beta) in updates.items():
                if self.anchored.get(cid):
                    continue
                b = self.beliefs[cid]
                mix = 0.6
                b.alpha = (1 - mix) * b.alpha + mix * v_alpha
                b.beta = (1 - mix) * b.beta + mix * v_beta
                b.alpha = max(b.alpha, 0.1)
                b.beta = max(b.beta, 0.1)


class TruthLayer:
    def __init__(self, path: str = "truth_layer.json"):
        self.path = Path(path)
        self.net = BayesianNetwork()
        self._load()

    def add_claim(self, cid: str, text: str, category: str = "general"):
        self.net.add_node(cid, text, category)

    def add_relationship(self, parent: str, child: str, weight: float):
        self.net.add_edge(parent, child, weight)

    def validate(self, cid: str, response: str, correction: str = ""):
        if cid not in self.net.beliefs:
            return
        if response == "confirm":
            self.net.update_belief(cid, True, strength=25.0)
        elif response == "reject":
            self.net.update_belief(cid, False, strength=25.0)
        elif response == "modify":
            self.net.update_belief(cid, True, strength=6.0)
            if correction:
                self.net.beliefs[cid].text = correction
        self.net.propagate()
        self._save()

    def get_belief(self, cid: str) -> Optional[Belief]:
        return self.net.beliefs.get(cid)

    def get_probability(self, cid: str) -> float:
        b = self.net.beliefs.get(cid)
        return b.probability if b else 0.5

    def get_truth_context(self) -> str:
        items = sorted(self.net.beliefs.items(), key=lambda x: x[1].probability, reverse=True)
        blocks = ["=== TRUTH LAYER (Bayesian Knowledge Base) ===\n", "VERIFIED TRUE (>90%):"]
        for _, b in items:
            if b.probability > 0.90:
                blocks.append(f"  {b.text}")
        blocks.append("\nLIKELY TRUE (70-90%):")
        for _, b in items:
            if 0.70 < b.probability <= 0.90:
                blocks.append(f"  {b.text} ({b.probability:.0%})")
        blocks.append("\nUNCERTAIN (30-70%):")
        for _, b in items:
            if 0.30 <= b.probability <= 0.70:
                blocks.append(f"  {b.text} ({b.probability:.0%})")
        blocks.append("\nLIKELY FALSE (<30%):")
        for _, b in items:
            if b.probability < 0.30:
                blocks.append(f"  {b.text} ({b.probability:.0%})")
        blocks.append("\n=== END TRUTH LAYER ===")
        return "\n".join(blocks)

    def stats(self) -> dict:
        beliefs = self.net.beliefs
        return {
            "total_claims": len(beliefs),
            "anchored": sum(1 for k in beliefs if self.net.anchored.get(k)),
            "high_confidence": sum(1 for b in beliefs.values() if b.probability > 0.9 or b.probability < 0.1),
            "total_edges": sum(len(e) for e in self.net.edges.values()),
        }

    def _save(self):
        data = {
            "beliefs": {k: asdict(v) for k, v in self.net.beliefs.items()},
            "edges": {k: v for k, v in self.net.edges.items()},
            "anchored": self.net.anchored,
        }
        self.path.write_text(json.dumps(data, indent=2))

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            for cid, state in data.get("beliefs", {}).items():
                self.net.beliefs[cid] = Belief(**state)
            self.net.edges = {k: v for k, v in data.get("edges", {}).items()}
            self.net.anchored = data.get("anchored", {})
        except Exception as e:
            print(f"[TruthLayer] Failed to load: {e}")
