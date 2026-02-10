"""
Signal detection engines: mood, beliefs, authority, compliance, reward,
approach/avoidance, persona (Engine 1), gap analysis, encoding weight.
"""

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    MoodState, EmotionalQuadrant, AuthoritySource, AuthorityTier,
    ComplianceProfile, RewardProfile, RewardType, EncodingWeight,
    EngineOpinion, TopicGap, GapAnalysis, ApproachAvoidanceData,
    IntrospectiveNarration,
)
from .belief import (
    Uncertainty, TruthLayer, trust_discount, probability_to_opinion,
)


TOPIC_TO_REWARD_MAP = {
    # achievement
    "shipping": "completion", "goals": "goals", "delivery": "delivery",
    "project": "completion", "deadline": "completion", "performance": "achievement",
    # social
    "team": "recognition", "meeting": "feedback", "review": "feedback",
    # security
    "budget": "planning", "documentation": "planning",
}


# =============================================================================
# MOOD DETECTOR
# =============================================================================

class MoodDetector:
    VALENCE_PATTERNS = {
        "v_gratitude":    (r'\b(thanks?|thank you|grateful|appreciate)\b', +0.3),
        "v_excitement":   (r'\b(awesome|amazing|fantastic|incredible|love it)\b', +0.4),
        "v_satisfaction": (r'\b(great|good|nice|pleased|happy|glad)\b', +0.25),
        "v_relief":       (r'\b(finally|at last|relieved|phew)\b', +0.3),
        "v_humor":        (r'(😂|😄|lol|haha|lmao)', +0.2),
        "v_frustration":  (r'\b(frustrat|annoy|irritat|infuriat)\w*', -0.4),
        "v_worry":        (r'\b(worr|anxious|nervous|concern|afraid|scared|terrified|terrif)\w*', -0.35),
        "v_anger":        (r'\b(angry|furious|pissed|hate|rage)\b', -0.5),
        "v_sadness":      (r'\b(sad|depress|disappoint|heartbreak|miserable)\w*', -0.4),
        "v_profanity":    (r'\b(damn|crap|shit|wtf|fuck|ugh|ffs)\b', -0.3),
        "v_defeat":       (r"\b(give up|hopeless|pointless|impossible|can't win)\b", -0.5),
        "v_stress":       (r'\b(stress|overwhelm|burnout|burned out|burnt out)\w*', -0.35),
        "v_dread":        (r'\b(dread|doom|foreboding)\w*', -0.4),
        "v_shock":        (r"\b(shock|stunned|numb|disbelief|can't believe)\b", -0.45),
        "v_loss":         (r'\b(lost|laid off|fired|terminated|let go|gutted|devastat)\w*', -0.5),
        "v_grief":        (r'\b(grief|griev|mourning|crushed|shattered|broken)\w*', -0.45),
        "v_eager":        (r'\b(excited|thrilled|passionate|energized|pumped)\b', +0.35),
        "v_love":         (r'\b(love|adore)\b', +0.3),
        "v_hope":         (r'\b(hopeful|optimistic|looking forward)\b', +0.25),
        "v_disaster":     (r'\b(disaster|catastrophe|nightmare|terrible|horrible|awful)\b', -0.4),
        "v_tired":        (r'\b(tired|exhausted|drained|fatigued)\b', -0.25),
        "v_apathy":       (r"\b(don't care|doesn't matter|who cares|meh|blah)\b", -0.2),
        "v_stuck":        (r'\b(stuck|stalled|blocked|no progress)\b', -0.2),
        "v_content":      (r'\b(content|peaceful|serene|tranquil|at ease|enjoying)\b', +0.15),
        "v_smooth":       (r'\b(smoothly|steady|stable|on track|under control)\b', +0.15),
        "v_mild_neg":     (r'\b(behind|complicated|not ideal|tight|piling up|keeps? changing|scope creep|challenging)\b', -0.15),
        "v_resigned":     (r'\b(whatever|suppose|I guess|if you say so)\b', -0.1),
        "v_struggling":   (r"\b(can't deal|can't keep up|hard to focus|interruptions?|dropped .* on me|insane)\b", -0.2),
        "v_workplace_neg":(r'\b(failed|dropped|post-?mortem|technical debt|accumulating|velocity .* dropped|escalate)\w*', -0.2),
        "v_subtle_pos":   (r'\b(not bad|trending up|right direction|clever|worth exploring|might .* work|could .* well|better than .* expected)\b', +0.2),
        "v_idiom_pos":    (r"\b(can't complain|no complaints?|all good)\b", +0.15),
        "v_pos_emoji":    (r'(👍|🙂|☺️|🌊|😌|🧘|💪|🚀|🎉|🔥)', +0.15),
        "v_neg_emoji":    (r'(😐|😞|😕|😔|💀|😤|😡|😰|😫|🤷)', -0.15),
    }

    AROUSAL_PATTERNS = {
        "a_caps":         (r'[A-Z]{4,}', +0.3),
        "a_exclaim":      (r'!{2,}', +0.25),
        "a_urgency":      (r'\b(URGENT|ASAP|emergency)\b', +0.4),
        "a_intensity":    (r'\b(extremely|absolutely|totally|completely)\b', +0.2),
        "a_repetition":   (r'(.)\1{3,}', +0.15),
        "a_ellipsis":     (r'\.{3,}', -0.2),
        "a_hedging":      (r'\b(maybe|perhaps|possibly|might|not sure)\b', -0.15),
        "a_resignation":  (r'\b(whatever|fine|okay I guess|suppose)\b', -0.25),
        "a_brevity":      (r'^.{1,10}$', -0.1),
        "a_pressure":     (r'\b(deadline|pressure|crunch|rush|time.?sensitive)\b', +0.25),
        "a_overwhelm":    (r"\b(overwhelm|too much|can't keep up|drowning)\w*", +0.2),
        "a_shock":        (r"\b(shock|can't believe|what the|oh my god|omg)\b", +0.35),
        "a_crisis":       (r'\b(crisis|emergency|catastroph|disaster|laid off|fired)\w*', +0.3),
        "a_disengaged":   (r"\b(don't care|doesn't matter|who cares|meh|blah)\b", -0.2),
        "a_fatigue":      (r'\b(tired|exhausted|drained|worn out|burned? out)\b', -0.15),
        "a_monotone":     (r'\b(same old|another day|going through the motions)\b', -0.2),
        "a_calm":         (r"\b(content|peaceful|serene|tranquil|at ease|smoothly|steady|stable|on track|under control|no complaints|no issues|quiet|slower pace|maintaining|can't complain)\b", -0.2),
        "a_mild_tension": (r'\b(behind|complicated|escalat|running out|piling up|tight timeline|growing scope|keeps? changing|failed|post-?mortem|dropped|accumulating|need to handle|should .* escalate)\b', +0.15),
        "a_calm_emoji":   (r'(👍|🙂|☺️|😌|🧘|🌊)', -0.15),
        "a_tense_emoji":  (r'(😤|😡|😰|😫|💀|🔥)', +0.15),
    }

    NEGATORS = re.compile(r"\b(not|no|never|neither|nor)\b|n't\b", re.IGNORECASE)

    SARCASM_MARKERS = re.compile(
        r'\b(oh great|just what I needed|how (?:delightful|wonderful|lovely)|yeah right|sure thing)\b'
        r'|(?:great|wonderful|fantastic|amazing|shocking|brilliant|lovely)\s*[.,!]\s*(?:the|another|my|this|production|nothing|nobody)'
        r'|(?:thanks?\s+so\s+much|really\s+appreciate)\s+(?:for\s+the\s+extra|for\s+(?:another|this|the\s+additional))'
        r'|\blove it when (?:things |stuff |it )?(?:break|fail|crash|go wrong)'
        r'|\bsure,?\s+let\'?s\b'
        r'|\bthat\'ll work out\b',
        re.IGNORECASE
    )

    HYPOTHETICAL = re.compile(
        r'\b(?:if\s+(?:this|that|it)|I\s+(?:would|wouldn\'t|\'d)\s+be|'
        r'(?:could|might|would)\s+be\s+\w+\s+if|'
        r'I\s+might\s+be)\b',
        re.IGNORECASE
    )

    def _is_negated(self, text: str, match_start: int) -> bool:
        prefix = text[:match_start]
        words = prefix.split()
        window = ' '.join(words[-3:]) if len(words) >= 3 else ' '.join(words)
        return bool(self.NEGATORS.search(window))

    def detect(self, text: str) -> MoodState:
        valence = 0.0
        arousal = 0.0
        signals = []

        # Strip quoted speech so we don't detect someone else's emotions
        # Double quotes
        text_clean = re.sub(r'"([^"]*)"', " ", text)
        # Smart/curly quotes
        text_clean = re.sub(r"[\u201c].*?[\u201d]", " ", text_clean)
        text_clean = re.sub(r"[\u2018].*?[\u2019]", " ", text_clean)
        # Speech-verb + single-quoted clause (handles contractions inside quotes)
        text_clean = re.sub(
            r"""(?:said|wrote|told\s+\w+|says|tell\s+\w+|asked)\s+'(?:[^']*(?:\w'\w)[^']*)*[^']*'""",
            " ", text_clean, flags=re.IGNORECASE)
        # Standalone single-quoted without contractions
        text_clean = re.sub(r"(?:^|\s)'([^']*)'(?:\s|[.,!?]|$)", " ", text_clean)

        for name, (pattern, value) in self.VALENCE_PATTERNS.items():
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                if self._is_negated(text_clean, match.start()):
                    signals.append(f"{name}_neg")
                    # Asymmetric flip: negating positive → strongly negative,
                    # negating negative → weakly positive (litotes)
                    flip = -0.8 if value > 0 else -0.3
                    valence += value * flip
                else:
                    signals.append(name)
                    valence += value

        for name, (pattern, value) in self.AROUSAL_PATTERNS.items():
            flags = 0 if name == "a_caps" else re.IGNORECASE
            if re.search(pattern, text_clean, flags):
                signals.append(name)
                arousal += value

        # Use original text for word-count check (quotes are real content)
        if len(text.split()) > 50:
            arousal += 0.1
            signals.append("a_long_message")

        # Hypothetical dampening: "If this works, I'd be excited" → mostly neutral
        if self.HYPOTHETICAL.search(text_clean):
            valence *= 0.3
            arousal *= 0.3
            signals.append("hypothetical_dampen")

        # Sarcasm flip: surface-positive + complaint structure
        if self.SARCASM_MARKERS.search(text_clean) and valence >= 0:
            if valence > 0:
                valence = valence * -0.7
            else:
                valence = -0.2  # push neutral sarcasm negative
            arousal = max(arousal, 0.1)
            signals.append("sarcasm_flip")

        # High-arousal stress inference: crisis/pressure/urgency signals with
        # near-zero valence implies negative situation, not excitement
        stress_signals = {"a_urgency", "a_pressure", "a_overwhelm", "a_crisis", "a_shock"}
        if arousal > 0.2 and abs(valence) < 0.1 and stress_signals & set(signals):
            valence = -0.15
            signals.append("stress_inferred")

        valence = max(-1.0, min(1.0, valence))
        arousal = max(-1.0, min(1.0, arousal))

        if abs(valence) < 0.15 and abs(arousal) < 0.15:
            quadrant = EmotionalQuadrant.NEUTRAL
        elif valence >= 0 and arousal >= 0:
            quadrant = EmotionalQuadrant.EXCITED
        elif valence >= 0:
            quadrant = EmotionalQuadrant.CALM
        elif arousal >= 0:
            quadrant = EmotionalQuadrant.STRESSED
        else:
            quadrant = EmotionalQuadrant.LOW

        return MoodState(
            valence=valence, arousal=arousal,
            confidence=min(0.80, 0.55 + len(signals) * 0.06),
            quadrant=quadrant, signals=signals,
        )


# =============================================================================
# BELIEF EXTRACTOR
# =============================================================================

AUTHORITY_INDICATORS = {
    r'\b(my boss|my manager|my lead|my director|my VP|my CEO)\b': "institutional",
    r'\b(HR said|HR requires|management wants|leadership decided)\b': "institutional",
    r'\b(the contract|the policy|the regulation|the law|the agreement)\b': "formal",
    r'\b(legally required|compliance requires|audit found)\b': "formal",
    r'\b(my (mom|dad|mother|father|parent|wife|husband|partner))\b': "personal",
    r'\b(my (mentor|coach|therapist|advisor))\b': "personal",
    r'\b(my (coworker|colleague|teammate|friend) (said|thinks|suggested))\b': "peer",
    r'\b(everyone (says|thinks|believes)|the team (wants|decided))\b': "peer",
    r'\b(I (read|saw|heard) that|according to|studies show|they say)\b': "ambient",
}


@dataclass
class BeliefDelta:
    belief_id: str
    text: str
    category: str = "general"
    confidence: str = "moderate"
    action: str = "new"


@dataclass
class AuthorityRef:
    source_text: str
    tier: str
    topics: List[str] = field(default_factory=list)


class BeliefExtractor:
    EXTRACTION_PROMPT = (
        'Extract beliefs or claims from this message. For each:\n'
        '1. belief_id: short snake_case identifier\n'
        '2. text: concise statement\n'
        '3. category: project | personal | team | technical | other\n'
        '4. confidence: strong | moderate | weak | uncertain\n'
        '5. action: "new" if first mention, "confirm" if reinforcing, "reject" if contradicting\n\n'
        'Message: {user_message}\n\n'
        'Respond as JSON: {{"beliefs": [...]}}'
    )

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def detect_authority_refs(self, text: str) -> List[AuthorityRef]:
        refs = []
        for pattern, tier in AUTHORITY_INDICATORS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                refs.append(AuthorityRef(source_text=match.group(0), tier=tier))
        return refs

    def extract_beliefs(self, message: str) -> List[BeliefDelta]:
        try:
            response = self.client.messages.create(
                model=os.getenv("MICRO_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=300, temperature=0.0,
                messages=[{"role": "user",
                           "content": self.EXTRACTION_PROMPT.format(user_message=message)}],
            )
            data = json.loads(response.content[0].text)
            return [
                BeliefDelta(
                    belief_id=b.get("belief_id", "unknown"),
                    text=b.get("text", ""),
                    category=b.get("category", "general"),
                    confidence=b.get("confidence", "moderate"),
                    action=b.get("action", "new"),
                )
                for b in data.get("beliefs", [])
            ]
        except Exception:
            return []

    def extract_beliefs_simple(self, message: str) -> List[BeliefDelta]:
        beliefs = []
        patterns = [
            (r"I (think|believe|feel) (?:that )?(.+?)(?:\.|$)", "moderate"),
            (r"I'm (sure|certain|confident) (?:that )?(.+?)(?:\.|$)", "strong"),
            (r"(?:maybe|perhaps) (.+?)(?:\.|$)", "weak"),
        ]
        for pattern, confidence in patterns:
            for match in re.finditer(pattern, message, re.IGNORECASE):
                text = match.group(2) if match.lastindex >= 2 else match.group(1)
                bid = re.sub(r'\W+', '_', text[:30].lower()).strip('_')
                beliefs.append(BeliefDelta(belief_id=bid, text=text.strip(), confidence=confidence))
        return beliefs


# =============================================================================
# AUTHORITY GRAPH
# =============================================================================

class AuthorityGraph:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "authority_graph.json"
        self.sources: Dict[str, AuthoritySource] = {}
        self._load()

    def add_source(self, source_id: str, name: str, tier: AuthorityTier,
                   trust_weight: float = 0.5, influence_topics: Optional[List[str]] = None) -> AuthoritySource:
        source = AuthoritySource(
            source_id=source_id, name=name, tier=tier,
            trust_weight=max(0.0, min(1.0, trust_weight)),
            influence_topics=influence_topics or [],
        )
        self.sources[source_id] = source
        self._save()
        return source

    def get_source(self, source_id: str) -> Optional[AuthoritySource]:
        return self.sources.get(source_id)

    def reference(self, source_id: str):
        if source_id in self.sources:
            self.sources[source_id].reference_count += 1
            self.sources[source_id].last_referenced = datetime.utcnow()
            self._save()

    def discount_opinion(self, source_id: str, opinion_strength: float = 0.9) -> Optional[Uncertainty]:
        source = self.sources.get(source_id)
        if not source:
            return None
        authority_opinion = probability_to_opinion(opinion_strength, uncertainty_level=0.1)
        user_trust = probability_to_opinion(
            source.trust_weight, uncertainty_level=max(0.05, 1.0 - source.trust_weight))
        return trust_discount(user_trust, authority_opinion)

    def get_relevant_sources(self, topic: str) -> List[AuthoritySource]:
        return [s for s in self.sources.values()
                if topic in s.influence_topics or not s.influence_topics]

    def get_tier_defaults(self) -> Dict[str, float]:
        return {
            AuthorityTier.FORMAL.value: 0.95,
            AuthorityTier.INSTITUTIONAL.value: 0.75,
            AuthorityTier.PERSONAL.value: 0.70,
            AuthorityTier.PEER.value: 0.50,
            AuthorityTier.AMBIENT.value: 0.25,
        }

    def to_dict(self) -> dict:
        return {
            sid: {"name": s.name, "tier": s.tier.value, "trust_weight": s.trust_weight,
                  "influence_topics": s.influence_topics, "reference_count": s.reference_count}
            for sid, s in self.sources.items()
        }

    def _save(self):
        data = {}
        for sid, s in self.sources.items():
            data[sid] = {
                "source_id": s.source_id, "name": s.name, "tier": s.tier.value,
                "trust_weight": s.trust_weight, "influence_topics": s.influence_topics,
                "reference_count": s.reference_count, "last_referenced": s.last_referenced.isoformat(),
            }
        self.path.write_text(json.dumps(data, indent=2))

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            for sid, d in data.items():
                self.sources[sid] = AuthoritySource(
                    source_id=d["source_id"], name=d["name"],
                    tier=AuthorityTier(d["tier"]),
                    trust_weight=d.get("trust_weight", 0.5),
                    influence_topics=d.get("influence_topics", []),
                    reference_count=d.get("reference_count", 0),
                )
        except Exception:
            self.sources = {}


# =============================================================================
# COMPLIANCE DETECTOR
# =============================================================================

class ComplianceDetector:
    COMPLIANCE_PATTERNS = {
        "should_do":    r'\b(I should|I need to|I have to|I must|I ought to)\b',
        "obligation":   r'\b(required|mandatory|obligated|expected to|supposed to)\b',
        "deference":    r'\b(yes sir|understood|will do|right away|of course)\b',
        "rule_citing":  r'\b(the policy|the rule|the guidelines?|the process|per the)\b',
        "apologetic":   r"\b(sorry|apologize|my fault|my mistake|I'll fix it)\b",
    }
    DEFIANCE_PATTERNS = {
        "but_hedge":      r'\b(I know I should but|I know but|yeah but)\b',
        "dismissal":      r"\b(whatever|who cares|doesn't matter|screw that|forget that)\b",
        "workaround":     r'\b(work around|shortcut|skip|bypass|hack it)\b',
        "resistance":     r"\b(don't see why|pointless|waste of time|bureaucracy)\b",
        "autonomy_pref":  r"\b(I prefer|my way|let me decide|I'll figure it out)\b",
    }

    def __init__(self, data_dir: Path):
        self.path = data_dir / "compliance.json"
        self.profile = ComplianceProfile()
        self._load()

    def analyze(self, text: str) -> ComplianceProfile:
        for name, pattern in self.COMPLIANCE_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                self.profile.observe_compliance(name)
        for name, pattern in self.DEFIANCE_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                self.profile.observe_defiance(name)
        self._save()
        return self.profile

    def _save(self):
        data = {"alpha": self.profile.alpha, "beta": self.profile.beta,
                "signals_observed": self.profile.signals_observed[-50:]}
        self.path.write_text(json.dumps(data, indent=2))

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            self.profile = ComplianceProfile(
                alpha=data.get("alpha", 3.0), beta=data.get("beta", 2.0),
                signals_observed=data.get("signals_observed", []),
            )
        except Exception:
            pass


# =============================================================================
# REWARD MODEL
# =============================================================================

class RewardModel:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "reward_profile.json"
        self.profile = RewardProfile()
        self._load()

    def observe(self, topic_category: str, valence: float):
        self.profile.observe(topic_category, valence)
        self._save()

    @property
    def reward_type(self) -> RewardType:
        return self.profile.reward_type

    @property
    def dominant_reward(self) -> str:
        return self.profile.dominant_reward

    def get_scores(self) -> dict:
        return {
            "social_approval": self.profile.social_score,
            "achievement": self.profile.achievement_score,
            "autonomy": self.profile.autonomy_score,
            "security": self.profile.security_score,
            "dominant": self.profile.dominant_reward,
            "observations": self.profile.observations,
        }

    def _save(self):
        data = {
            "reward_type": self.profile.reward_type.value,
            "social_score": self.profile.social_score,
            "achievement_score": self.profile.achievement_score,
            "autonomy_score": self.profile.autonomy_score,
            "security_score": self.profile.security_score,
            "observations": self.profile.observations,
        }
        self.path.write_text(json.dumps(data, indent=2))

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            self.profile = RewardProfile(
                reward_type=RewardType(data.get("reward_type", "unknown")),
                social_score=data.get("social_score", 0.0),
                achievement_score=data.get("achievement_score", 0.0),
                autonomy_score=data.get("autonomy_score", 0.0),
                security_score=data.get("security_score", 0.0),
                observations=data.get("observations", 0),
            )
        except Exception:
            pass


# =============================================================================
# APPROACH/AVOIDANCE DETECTOR
# =============================================================================

class ApproachAvoidanceDetector:
    APPROACH_PATTERNS = {
        "elaboration":    r'\b(and also|furthermore|another thing|plus|let me add)\b',
        "follow_up":      r'\b(what if|how about|could we|I was thinking)\b',
        "enthusiasm":     r'!{1,}',
        "ownership":      r"\b(I want to|I'd love to|I'm excited|let me|my idea)\b",
        "detail_seeking": r'\b(tell me more|how exactly|specifically|what does)\b',
    }
    AVOIDANCE_PATTERNS = {
        "deflection":      r"\b(anyway|moving on|let's talk about|different topic)\b",
        "deferral":        r'\b(later|eventually|someday|when I get to it|at some point)\b',
        "hedge":           r"\b(I guess|I suppose|maybe|not sure if|probably should)\b",
        "minimal":         r'^.{1,20}$',
        "compliance_only": r'\b(fine|okay|sure|will do|understood)\b',
    }

    def __init__(self, data_dir: Path):
        self.path = data_dir / "approach_avoidance.json"
        self.tracker: Dict[str, ApproachAvoidanceData] = {}
        self._load()

    def analyze(self, text: str, topic: str, mood: MoodState) -> ApproachAvoidanceData:
        if topic not in self.tracker:
            self.tracker[topic] = ApproachAvoidanceData(topic=topic)
        aa = self.tracker[topic]
        aa.observations += 1
        aa.total_valence += mood.valence
        aa.total_arousal += mood.arousal

        approach_hits = sum(1 for _, p in self.APPROACH_PATTERNS.items()
                           if re.search(p, text, re.IGNORECASE))
        avoidance_hits = sum(1 for _, p in self.AVOIDANCE_PATTERNS.items()
                            if re.search(p, text, re.IGNORECASE))
        if len(text.split()) > 40:
            approach_hits += 1

        if approach_hits > avoidance_hits:
            aa.approach_count += 1
        elif avoidance_hits > approach_hits:
            aa.avoidance_count += 1

        self._save()
        return aa

    def get_tracker(self, topic: str) -> ApproachAvoidanceData:
        return self.tracker.get(topic, ApproachAvoidanceData(topic=topic))

    def _save(self):
        data = {}
        for topic, aa in self.tracker.items():
            data[topic] = {
                "topic": aa.topic, "approach_count": aa.approach_count,
                "avoidance_count": aa.avoidance_count, "total_valence": aa.total_valence,
                "total_arousal": aa.total_arousal, "observations": aa.observations,
            }
        self.path.write_text(json.dumps(data, indent=2))

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            for topic, d in data.items():
                self.tracker[topic] = ApproachAvoidanceData(**d)
        except Exception:
            self.tracker = {}


# =============================================================================
# PERSONA ENGINE (Engine 1: "Should Self")
# =============================================================================

class PersonaEngine:
    def __init__(self, truth_layer: TruthLayer, authority_graph: AuthorityGraph,
                 compliance_detector: ComplianceDetector):
        self.truth_layer = truth_layer
        self.authority = authority_graph
        self.compliance = compliance_detector

    def process(self, text: str, mood: MoodState, topics: List[str],
                authority_refs: Optional[List[dict]] = None) -> Dict[str, EngineOpinion]:
        self.compliance.analyze(text)
        opinions = {}

        for topic in topics:
            signals = []
            belief = self.truth_layer.get_belief(topic)

            if belief:
                b_val = belief.probability
                u_val = max(0.05, min(0.5, belief.variance * 10))
            else:
                b_val = 0.5
                u_val = 0.4

            relevant = self.authority.get_relevant_sources(topic)
            for source in relevant:
                discounted = self.authority.discount_opinion(source.source_id)
                if discounted:
                    b_val = min(0.95, b_val * 0.6 + discounted.expected_value * 0.4)
                    u_val = max(0.05, u_val * 0.7)
                    signals.append(f"authority:{source.source_id}")

            compliance_score = self.compliance.profile.compliance_score
            if compliance_score > 0.6:
                signals.append("compliance:rule_follower")
            elif compliance_score < 0.4:
                signals.append("compliance:rule_bender")
                u_val = min(0.5, u_val * 1.2)

            espoused_patterns = ["I should", "I need to", "I believe", "I think", "it's important"]
            for p in espoused_patterns:
                if p.lower() in text.lower():
                    b_val = min(0.95, b_val + 0.05)
                    signals.append(f"espoused:{p.replace(' ', '_')}")

            # BUG FIX: proper normalization — ensure b + d + u == 1.0
            d_val = max(0.0, 1.0 - b_val - u_val)
            total = b_val + d_val + u_val
            if abs(total - 1.0) > 1e-6:
                b_val /= total
                d_val /= total
                u_val /= total

            opinions[topic] = EngineOpinion(
                topic=topic, belief=round(b_val, 3),
                disbelief=round(d_val, 3), uncertainty=round(u_val, 3),
                source_signals=signals,
            )

        return opinions


# =============================================================================
# GAP ANALYZER ("Theatre Detector")
# =============================================================================

GAP_HISTORY_CAP = 50


def classify_severity(gap: float) -> str:
    if gap < 0.1:
        return "none"
    elif gap < 0.25:
        return "low"
    elif gap < 0.45:
        return "moderate"
    elif gap < 0.65:
        return "high"
    else:
        return "critical"


class GapAnalyzer:
    def __init__(self, data_dir: Path):
        self.history_path = data_dir / "gap_history.json"
        self.history: Dict[str, List[dict]] = {}
        self._load()

    def analyze(self, persona_opinions: Dict[str, EngineOpinion],
                reward_opinions: Dict[str, EngineOpinion]) -> GapAnalysis:
        all_topics = set(persona_opinions.keys()) | set(reward_opinions.keys())
        gaps = []

        for topic in all_topics:
            e1 = persona_opinions.get(topic)
            e2 = reward_opinions.get(topic)
            if e1 and e2:
                e1_val = e1.expected_value
                e2_val = e2.expected_value
                gap_mag = abs(e1_val - e2_val)
                direction = "persona_leads" if e1_val > e2_val else "reward_leads"
                self._record(topic, e1_val, e2_val, gap_mag)
                obs = len(self.history.get(topic, []))
                gaps.append(TopicGap(
                    topic=topic, persona_opinion=e1_val, reward_opinion=e2_val,
                    gap_magnitude=gap_mag, gap_direction=direction,
                    conflict_severity=classify_severity(gap_mag),
                    explanation=self._explain(topic, e1, e2, gap_mag, direction),
                    observations=obs,
                ))

        if gaps:
            overall = sum(g.gap_magnitude for g in gaps) / len(gaps)
            trend = self._compute_trend(gaps)
            dominant = self._compute_dominant(gaps)
        else:
            overall, trend, dominant = 0.0, "stable", "balanced"

        return GapAnalysis(topic_gaps=gaps, overall_divergence=overall,
                          divergence_trend=trend, dominant_engine=dominant)

    def explain_behavior(self, behavior: str, analysis: GapAnalysis) -> str:
        significant = analysis.significant_gaps
        if not significant:
            return ("Not enough divergence data yet to explain this behavior. "
                    "I need more conversations to separate your persona beliefs "
                    "from your reward patterns.")

        top_gap = max(significant, key=lambda g: g.gap_magnitude)
        if top_gap.gap_direction == "reward_leads":
            return (f"Your Persona Engine says '{top_gap.topic}' matters "
                    f"(confidence {top_gap.persona_opinion:.0%}), but your "
                    f"Reward Engine is pulling harder toward what energizes you "
                    f"(confidence {top_gap.reward_opinion:.0%}). "
                    f"The gap ({top_gap.gap_magnitude:.0%}) predicts that your "
                    f"actual behavior follows Engine 2 — your want-self wins "
                    f"at the moment of decision.")
        else:
            return (f"Your Persona Engine holds '{top_gap.topic}' strongly "
                    f"(confidence {top_gap.persona_opinion:.0%}), and it's "
                    f"currently overriding your reward center "
                    f"({top_gap.reward_opinion:.0%}). Watch for burnout — "
                    f"sustained persona-over-reward creates stress. "
                    f"The gap ({top_gap.gap_magnitude:.0%}) is "
                    f"{top_gap.conflict_severity}.")

    def _explain(self, topic, e1, e2, gap, direction) -> str:
        if gap < 0.15:
            return f"Aligned on '{topic}' — both engines agree."
        elif direction == "reward_leads":
            return (f"'{topic}': You say it matters ({e1.expected_value:.0%}) "
                    f"but your energy goes elsewhere ({e2.expected_value:.0%}).")
        else:
            return (f"'{topic}': Authority pushes this ({e1.expected_value:.0%}) "
                    f"harder than your reward center buys in ({e2.expected_value:.0%}).")

    def _record(self, topic: str, e1_val: float, e2_val: float, gap: float):
        if topic not in self.history:
            self.history[topic] = []
        self.history[topic].append({
            "e1": round(e1_val, 3), "e2": round(e2_val, 3),
            "gap": round(gap, 3), "ts": datetime.utcnow().isoformat(),
        })
        # Cap history per topic
        if len(self.history[topic]) > GAP_HISTORY_CAP:
            self.history[topic] = self.history[topic][-GAP_HISTORY_CAP:]
        self._save()

    def _compute_trend(self, gaps: List[TopicGap]) -> str:
        trends = []
        for gap in gaps:
            hist = self.history.get(gap.topic, [])
            if len(hist) >= 3:
                recent = [h["gap"] for h in hist[-3:]]
                if recent[-1] > recent[0] * 1.1:
                    trends.append("increasing")
                elif recent[-1] < recent[0] * 0.9:
                    trends.append("decreasing")
                else:
                    trends.append("stable")
        if not trends:
            return "stable"
        return Counter(trends).most_common(1)[0][0]

    def _compute_dominant(self, gaps: List[TopicGap]) -> str:
        persona_leads = sum(1 for g in gaps if g.gap_direction == "persona_leads")
        reward_leads = len(gaps) - persona_leads
        if abs(persona_leads - reward_leads) <= 1:
            return "balanced"
        return "persona" if persona_leads > reward_leads else "reward"

    def _save(self):
        self.history_path.write_text(json.dumps(self.history, indent=2))

    def _load(self):
        if self.history_path.exists():
            try:
                self.history = json.loads(self.history_path.read_text())
            except Exception:
                self.history = {}


# =============================================================================
# ENCODING WEIGHT
# =============================================================================

def compute_encoding_weight(
    mood: MoodState,
    authority: Optional[AuthoritySource],
    reward_profile: RewardProfile,
    compliance: ComplianceProfile,
    topic_category: str,
) -> EncodingWeight:
    flashbulb = mood.flashbulb_weight

    if authority:
        authority_opinion = probability_to_opinion(0.9, uncertainty_level=0.1)
        user_trust = probability_to_opinion(
            authority.trust_weight, uncertainty_level=max(0.05, 1.0 - authority.trust_weight))
        discounted = trust_discount(user_trust, authority_opinion)
        authority_relevance = discounted.expected_value * compliance.compliance_score
    else:
        authority_relevance = 0.3

    reward_map = {
        RewardType.SOCIAL_APPROVAL: ("praise", "recognition", "approval", "feedback"),
        RewardType.ACHIEVEMENT: ("completion", "shipping", "goals", "delivery"),
        RewardType.AUTONOMY: ("independence", "choice", "freedom", "own_decision"),
        RewardType.SECURITY: ("stability", "safety", "planning", "predictability"),
    }
    reward_alignment = 0.3
    if reward_profile.reward_type != RewardType.UNKNOWN:
        aligned_topics = reward_map.get(reward_profile.reward_type, ())
        if topic_category in aligned_topics:
            reward_alignment = 0.8 + 0.2 * max(0, mood.valence)
        elif mood.valence > 0.3:
            reward_alignment = 0.5

    conflict = abs(authority_relevance - reward_alignment)
    return EncodingWeight(flashbulb=flashbulb, authority_relevance=authority_relevance,
                         reward_alignment=reward_alignment, conflict_score=conflict)


# =============================================================================
# INTROSPECTIVE LAYER ("What I Know I Don't Know")
# =============================================================================

class IntrospectiveLayer:
    """Generates the agent's self-model — structured uncertainty about its own reads.

    This is the meta-cognitive layer: instead of just reporting "you feel X",
    it reports "I'm 60% sure you feel X, and here's what's limiting my read."
    """

    def analyze(
        self,
        mood: Optional['MoodState'],
        gap_analysis: Optional[GapAnalysis],
        persona_opinions: Dict[str, EngineOpinion],
        reward_opinions: Dict[str, EngineOpinion],
        truth_layer: 'TruthLayer',
        thinking_budget: int = 5000,
    ) -> IntrospectiveNarration:
        narration = IntrospectiveNarration()
        narration.thinking_budget_used = thinking_budget

        # Mood confidence: based on signal count and mood detector confidence
        if mood:
            narration.mood_confidence = mood.confidence
            if mood.signals:
                narration.strongest_signal = mood.signals[0]
        else:
            narration.mood_confidence = 0.0

        # Gap confidence: based on observation count across topics
        if gap_analysis and gap_analysis.topic_gaps:
            obs_counts = [g.observations for g in gap_analysis.topic_gaps]
            avg_obs = sum(obs_counts) / len(obs_counts)
            narration.gap_confidence = min(0.95, avg_obs / 10.0)
        else:
            narration.gap_confidence = 0.0

        # Belief coverage: what fraction of active topics have sufficient data
        all_topics = set(persona_opinions.keys()) | set(reward_opinions.keys())
        if all_topics:
            covered = 0
            for topic in all_topics:
                belief = truth_layer.get_belief(topic)
                if belief and belief.variance < 0.15:
                    covered += 1
            narration.belief_coverage = covered / len(all_topics)
        else:
            narration.belief_coverage = 0.0

        # Blind spots: topics with high uncertainty in either engine
        blind = []
        for topic in all_topics:
            p = persona_opinions.get(topic)
            r = reward_opinions.get(topic)
            if p and p.uncertainty > 0.35:
                blind.append(f"{topic} (persona uncertain)")
            elif r and r.uncertainty > 0.35:
                blind.append(f"{topic} (reward uncertain)")
            elif not p or not r:
                blind.append(f"{topic} (single-engine only)")
        narration.blind_spots = blind[:5]

        # What would change my mind
        changes = []
        if narration.mood_confidence < 0.5:
            changes.append("more emotional signals in the message (exclamations, explicit feelings)")
        if narration.gap_confidence < 0.3:
            changes.append("several more conversations about these topics to separate persona from reward")
        for topic in all_topics:
            p = persona_opinions.get(topic)
            r = reward_opinions.get(topic)
            if p and r and abs(p.expected_value - r.expected_value) > 0.3:
                if p.uncertainty > 0.25 or r.uncertainty > 0.25:
                    changes.append(f"clearer signal on '{topic}' — the gap could be noise or real")
                    break
        narration.would_change_mind = changes[:3]

        # Reasoning depth label
        if thinking_budget >= 12000:
            narration.reasoning_depth = "deep"
        elif thinking_budget >= 7000:
            narration.reasoning_depth = "deliberate"
        else:
            narration.reasoning_depth = "routine"

        return narration
