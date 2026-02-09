"""Core data models for the Emotional Memory Agent."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
import uuid


class EmotionalQuadrant(str, Enum):
    EXCITED = "excited"
    CALM = "calm"
    STRESSED = "stressed"
    LOW = "low"
    NEUTRAL = "neutral"


class AuthorityTier(str, Enum):
    FORMAL = "formal"
    INSTITUTIONAL = "institutional"
    PERSONAL = "personal"
    PEER = "peer"
    AMBIENT = "ambient"


class RewardType(str, Enum):
    SOCIAL_APPROVAL = "social_approval"
    ACHIEVEMENT = "achievement"
    AUTONOMY = "autonomy"
    SECURITY = "security"
    UNKNOWN = "unknown"


@dataclass
class MoodState:
    valence: float
    arousal: float
    confidence: float
    quadrant: EmotionalQuadrant
    signals: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def intensity(self) -> float:
        return (self.valence**2 + self.arousal**2) ** 0.5

    @property
    def flashbulb_weight(self) -> float:
        return 0.5 + 0.5 * min(1.0, abs(self.arousal))

    def to_dict(self) -> dict:
        return {
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "confidence": round(self.confidence, 3),
            "quadrant": self.quadrant.value,
            "intensity": round(self.intensity, 3),
            "signals": self.signals,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AuthoritySource:
    source_id: str
    name: str
    tier: AuthorityTier
    trust_weight: float = 0.5
    influence_topics: List[str] = field(default_factory=list)
    last_referenced: datetime = field(default_factory=datetime.utcnow)
    reference_count: int = 0

    def to_opinion(self) -> dict:
        u = max(0.05, 1.0 - self.trust_weight)
        b = self.trust_weight * (1.0 - u)
        d = (1.0 - self.trust_weight) * (1.0 - u)
        return {"belief": round(b, 3), "disbelief": round(d, 3), "uncertainty": round(u, 3)}


@dataclass
class ComplianceProfile:
    alpha: float = 3.0
    beta: float = 2.0
    signals_observed: List[str] = field(default_factory=list)

    @property
    def compliance_score(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    def observe_compliance(self, signal: str):
        self.alpha += 1.0
        self.signals_observed.append(f"+{signal}")

    def observe_defiance(self, signal: str):
        self.beta += 1.0
        self.signals_observed.append(f"-{signal}")


@dataclass
class RewardProfile:
    reward_type: RewardType = RewardType.UNKNOWN
    social_score: float = 0.0
    achievement_score: float = 0.0
    autonomy_score: float = 0.0
    security_score: float = 0.0
    observations: int = 0

    def observe(self, topic_category: str, valence: float):
        if valence > 0.1:
            if topic_category in ("praise", "recognition", "approval", "feedback"):
                self.social_score += valence
            elif topic_category in ("completion", "shipping", "goals", "delivery", "achievement"):
                self.achievement_score += valence
            elif topic_category in ("independence", "choice", "freedom", "own_decision"):
                self.autonomy_score += valence
            elif topic_category in ("stability", "safety", "planning", "predictability"):
                self.security_score += valence
        self.observations += 1
        self._update_type()

    def _update_type(self):
        scores = {
            RewardType.SOCIAL_APPROVAL: self.social_score,
            RewardType.ACHIEVEMENT: self.achievement_score,
            RewardType.AUTONOMY: self.autonomy_score,
            RewardType.SECURITY: self.security_score,
        }
        if self.observations >= 5:
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                self.reward_type = best

    @property
    def dominant_reward(self) -> str:
        return self.reward_type.value


@dataclass
class EncodingWeight:
    flashbulb: float = 0.5
    authority_relevance: float = 0.5
    reward_alignment: float = 0.5
    conflict_score: float = 0.0

    @property
    def total_weight(self) -> float:
        base = self.flashbulb * max(self.authority_relevance, self.reward_alignment)
        conflict_bonus = self.conflict_score * 0.5
        return min(2.0, base + conflict_bonus)

    def explain(self) -> str:
        parts = []
        if self.flashbulb > 0.7:
            parts.append("high emotional intensity")
        if self.authority_relevance > 0.7:
            parts.append("authority says this matters")
        if self.reward_alignment > 0.7:
            parts.append("aligns with your reward center")
        if self.conflict_score > 0.4:
            parts.append(f"authority-reward conflict ({self.conflict_score:.0%})")
        return " + ".join(parts) if parts else "moderate encoding"


@dataclass
class EngineOpinion:
    topic: str
    belief: float
    disbelief: float
    uncertainty: float
    source_signals: List[str]

    @property
    def expected_value(self) -> float:
        return self.belief + self.uncertainty * 0.5

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "belief": round(self.belief, 3),
            "disbelief": round(self.disbelief, 3),
            "uncertainty": round(self.uncertainty, 3),
            "expected_value": round(self.expected_value, 3),
            "signals": self.source_signals,
        }


@dataclass
class TopicGap:
    topic: str
    persona_opinion: float
    reward_opinion: float
    gap_magnitude: float
    gap_direction: str
    conflict_severity: str
    explanation: str
    first_detected: datetime = field(default_factory=datetime.utcnow)
    observations: int = 1

    @property
    def is_significant(self) -> bool:
        return self.gap_magnitude > 0.3 and self.observations >= 3

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "persona_says": round(self.persona_opinion, 3),
            "reward_wants": round(self.reward_opinion, 3),
            "gap": round(self.gap_magnitude, 3),
            "direction": self.gap_direction,
            "severity": self.conflict_severity,
            "explanation": self.explanation,
            "significant": self.is_significant,
            "observations": self.observations,
        }


@dataclass
class GapAnalysis:
    topic_gaps: List[TopicGap] = field(default_factory=list)
    overall_divergence: float = 0.0
    divergence_trend: str = "stable"
    dominant_engine: str = "balanced"

    @property
    def significant_gaps(self) -> List[TopicGap]:
        return [g for g in self.topic_gaps if g.is_significant]

    @property
    def theatre_score(self) -> float:
        if not self.topic_gaps:
            return 0.0
        return min(1.0, self.overall_divergence * 2)

    def to_dict(self) -> dict:
        return {
            "topic_gaps": [g.to_dict() for g in self.significant_gaps],
            "overall_divergence": round(self.overall_divergence, 3),
            "theatre_score": round(self.theatre_score, 3),
            "trend": self.divergence_trend,
            "dominant_engine": self.dominant_engine,
            "total_topics_tracked": len(self.topic_gaps),
            "significant_gaps": len(self.significant_gaps),
        }


@dataclass
class ApproachAvoidanceData:
    topic: str
    approach_count: int = 0
    avoidance_count: int = 0
    total_valence: float = 0.0
    total_arousal: float = 0.0
    observations: int = 0

    @property
    def approach_ratio(self) -> float:
        total = self.approach_count + self.avoidance_count
        if total == 0:
            return 0.5
        return self.approach_count / total

    @property
    def avg_valence(self) -> float:
        if self.observations == 0:
            return 0.0
        return self.total_valence / self.observations

    @property
    def avg_arousal(self) -> float:
        if self.observations == 0:
            return 0.0
        return self.total_arousal / self.observations


@dataclass
class EmotionalMemory:
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    user_id: str = "default"
    content: str = ""
    mood: Optional[MoodState] = None
    beliefs_affected: List[str] = field(default_factory=list)
    topic_tags: List[str] = field(default_factory=list)
    session_id: str = ""
    trust_zone: str = "unverified"
    corroboration_count: int = 0
    authority_source: str = ""
    encoding_weight: float = 0.5
    conflict_score: float = 0.0
    persona_opinion: float = 0.5
    reward_opinion: float = 0.5
    gap_magnitude: float = 0.0
    gap_direction: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_pinecone_record(self) -> dict:
        return {
            "_id": self.memory_id,
            "content": self.content,
            "user_id": self.user_id,
            "valence": self.mood.valence if self.mood else 0.0,
            "arousal": self.mood.arousal if self.mood else 0.0,
            "quadrant": self.mood.quadrant.value if self.mood else "neutral",
            "intensity": self.mood.intensity if self.mood else 0.0,
            "trust_zone": self.trust_zone,
            "corroboration_count": self.corroboration_count,
            "encoding_weight": self.encoding_weight,
            "conflict_score": self.conflict_score,
            "authority_source": self.authority_source,
            "persona_opinion": self.persona_opinion,
            "reward_opinion": self.reward_opinion,
            "gap_magnitude": self.gap_magnitude,
            "gap_direction": self.gap_direction,
            "topic_tags": self.topic_tags,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class HoldRequest:
    hold_id: str = field(default_factory=lambda: f"hold_{uuid.uuid4().hex[:8]}")
    action: str = ""
    target_id: str = ""
    reason: str = ""
    requested_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "pending"
    resolution_reason: str = ""
    resolved_at: Optional[datetime] = None
