"""Ground truth data structures for evaluation datasets.

Each schema mirrors what a component claims to predict, plus the
human-labeled ground truth to compare against.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MoodSample:
    """Ground truth for MoodDetector evaluation."""
    text: str
    expected_quadrant: str          # "excited", "calm", "stressed", "low", "neutral"
    expected_valence: float         # -1.0 to +1.0
    expected_arousal: float         # -1.0 to +1.0
    difficulty: str = "standard"    # "standard", "negation", "sarcasm", "quoted", "mixed", "edge"
    category: str = "general"       # "direct", "indirect", "figurative", "emoji", "context_dependent"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "expected_quadrant": self.expected_quadrant,
            "expected_valence": self.expected_valence,
            "expected_arousal": self.expected_arousal,
            "difficulty": self.difficulty,
            "category": self.category,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MoodSample":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class GovernanceSample:
    """Ground truth for GovernanceLayer gate decisions."""
    encoding_weight: float
    conflict_score: float
    trust_zone: str                 # "unverified", "promoted"
    corroboration_count: int
    action: str                     # "store_memory", "promote_memory", "delete_memory"
    expected_decision: str          # "allowed", "held"
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "encoding_weight": self.encoding_weight,
            "conflict_score": self.conflict_score,
            "trust_zone": self.trust_zone,
            "corroboration_count": self.corroboration_count,
            "action": self.action,
            "expected_decision": self.expected_decision,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GovernanceSample":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ApproachAvoidanceSample:
    """Ground truth for ApproachAvoidanceDetector."""
    text: str
    topic: str
    valence: float                  # mood valence to feed the detector
    arousal: float                  # mood arousal to feed the detector
    expected_direction: str         # "approach", "avoidance", "neutral"
    expected_strength: float        # 0.0 to 1.0 — how strongly approach or avoidance
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text, "topic": self.topic,
            "valence": self.valence, "arousal": self.arousal,
            "expected_direction": self.expected_direction,
            "expected_strength": self.expected_strength,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ApproachAvoidanceSample":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ConversationTurn:
    """Single turn within an annotated conversation."""
    text: str
    topics: List[str]
    expected_quadrant: str = ""
    expected_gap_direction: str = ""    # "persona_leads", "reward_leads", "aligned", ""
    expected_gap_severity: str = ""     # "none", "low", "moderate", "high", "critical", ""
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text, "topics": self.topics,
            "expected_quadrant": self.expected_quadrant,
            "expected_gap_direction": self.expected_gap_direction,
            "expected_gap_severity": self.expected_gap_severity,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationTurn":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class AnnotatedConversation:
    """Multi-turn conversation with ground truth annotations."""
    conversation_id: str
    scenario_type: str              # "authority_buildup", "reward_divergence", "crisis", "mixed", "null_signal"
    turns: List[ConversationTurn] = field(default_factory=list)
    expected_final_gap_topic: str = ""
    expected_final_gap_direction: str = ""
    expected_reward_type: str = ""  # "achievement", "social_approval", etc.
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "scenario_type": self.scenario_type,
            "turns": [t.to_dict() for t in self.turns],
            "expected_final_gap_topic": self.expected_final_gap_topic,
            "expected_final_gap_direction": self.expected_final_gap_direction,
            "expected_reward_type": self.expected_reward_type,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnnotatedConversation":
        turns = [ConversationTurn.from_dict(t) for t in d.get("turns", [])]
        return cls(
            conversation_id=d["conversation_id"],
            scenario_type=d["scenario_type"],
            turns=turns,
            expected_final_gap_topic=d.get("expected_final_gap_topic", ""),
            expected_final_gap_direction=d.get("expected_final_gap_direction", ""),
            expected_reward_type=d.get("expected_reward_type", ""),
            notes=d.get("notes", ""),
        )


@dataclass
class MemoryImportanceSample:
    """Ground truth for emotional decay retrieval ranking."""
    memory_id: str
    content: str
    encoding_weight: float          # 0.0 to 2.0
    intensity: float                # 0.0 to 1.0
    age_hours: float
    expected_importance_rank: int   # 1 = most important
    query: str = ""                 # retrieval query this is relevant to

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "encoding_weight": self.encoding_weight,
            "intensity": self.intensity,
            "age_hours": self.age_hours,
            "expected_importance_rank": self.expected_importance_rank,
            "query": self.query,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryImportanceSample":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CalibrationSample:
    """Generic sample for confidence calibration evaluation."""
    predicted_confidence: float     # model's stated confidence
    was_correct: bool               # whether the prediction was actually right
    component: str = ""             # which component produced this
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "predicted_confidence": self.predicted_confidence,
            "was_correct": self.was_correct,
            "component": self.component,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationSample":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
