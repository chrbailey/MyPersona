"""
Agent loop, tool dispatch, context assembly, system prompt, CLI.
All bug fixes applied:
- Duplicate compliance.analyze() call removed
- Memory search wired up (was always empty list)
- Encoding weight computed and stored on memories
- Opinion normalization fixed in PersonaEngine (in engines.py)
"""

import json
import os
import sys
import uuid
import yaml
from pathlib import Path
from typing import Dict, List, Optional

import anthropic

from .models import (
    MoodState, GapAnalysis, EngineOpinion, EmotionalQuadrant,
    EmotionalMemory, AuthorityTier, TopicGap,
)
from .belief import TruthLayer, decompose_from_beta
from .engines import (
    MoodDetector, BeliefExtractor,
    AuthorityGraph, ComplianceDetector, RewardModel,
    ApproachAvoidanceDetector, PersonaEngine, GapAnalyzer,
    compute_encoding_weight, TOPIC_TO_REWARD_MAP,
)
from .memory import (
    MemoryStore, TimelineManager,
    GovernanceLayer, AuditTrail,
)


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are an emotionally intelligent assistant that remembers not just what
users discuss, but how they felt during those discussions.

You have access to:
1. The user's current emotional state (valence/arousal circumplex model)
2. Their emotional history across conversations (timeline with trends)
3. Their beliefs with Bayesian confidence levels and uncertainty decomposition
4. ENGINE 1 — Their Persona ("Should Self"): authority hierarchy, compliance
   profile, espoused beliefs. What they say they value.
5. ENGINE 2 — Their Reward Center ("Want Self"): reward profile, approach/avoidance
   patterns, revealed preferences. What actually drives their energy and behavior.
6. THE GAP — Where Engine 1 and Engine 2 diverge. This gap explains seemingly
   irrational behavior, procrastination, office politics, and hidden motivations.
7. Governance controls — some operations require human approval

When responding:
- Acknowledge emotional states naturally, never clinically
- Reference emotional patterns when relevant ("you seemed more optimistic
  about this last week")
- Adjust your tone to match the emotional trajectory
- If asked about past feelings, use the emotional timeline tools
- When authority sources are mentioned ("my boss said...", "the policy requires..."),
  note the influence and track how it shapes Engine 1 beliefs via trust discounting
- Track what generates energy (approach behavior, positive valence, elaboration)
  separately as Engine 2 signals — the user may not articulate these
- When you detect a significant gap between Engine 1 and Engine 2 on a topic,
  surface it gently. The user may not be conscious of the tension. Frame it as
  an observation, not a diagnosis: "I notice your stated priority (documentation)
  and what energizes you (shipping) are pulling in different directions."
- NEVER be judgmental about the gap. Both engines are valid.
- When authority sources are trust-discounted, reflect that nuance. A boss with
  trust_weight=0.8 shifts Engine 1 beliefs but doesn't override them. Lower-trust
  sources (ambient media, peer gossip) get heavily discounted.
- Be honest about uncertainty. If you have limited data, say so: "I've only seen
  a few interactions on this topic — my read could shift as I learn more about you."
- If a governance hold is created, explain it simply

IMPORTANT: You track two kinds of uncertainty for every belief:
- Epistemic: "We don't know enough yet" → gathering more context helps
- Aleatoric: "This is inherently unpredictable" → more context won't help

IMPORTANT: Authority-sourced beliefs are trust-discounted, not taken at face value.

The following YAML describes the user's current emotional context:

<emotional_context>
{context_yaml}
</emotional_context>"""


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

AGENT_TOOLS = [
    {"name": "detect_mood",
     "description": "Analyze emotional signals in a user message. Returns valence, arousal, quadrant, and confidence. Use this to get a detailed read on how the user is feeling right now.",
     "input_schema": {"type": "object", "properties": {"message": {"type": "string"}},
                      "required": ["message"]}},
    {"name": "get_emotional_timeline",
     "description": "Get the user's mood history for a topic over time. Shows emotional trajectory and trends — useful for spotting shifts in how they feel about recurring subjects.",
     "input_schema": {"type": "object", "properties": {
         "topic": {"type": "string"}, "days_back": {"type": "integer", "default": 30}}}},
    {"name": "query_beliefs",
     "description": "Query the user's current beliefs with Bayesian confidence levels. Can filter by category and minimum probability. Includes epistemic vs aleatoric uncertainty decomposition.",
     "input_schema": {"type": "object", "properties": {
         "category": {"type": "string"}, "min_probability": {"type": "number", "default": 0.0}}}},
    {"name": "update_belief",
     "description": "Update a belief's strength — confirm reinforces it, reject weakens it, weaken reduces confidence without full rejection.",
     "input_schema": {"type": "object", "properties": {
         "belief_id": {"type": "string"}, "action": {"type": "string", "enum": ["confirm", "reject", "weaken"]},
         "strength": {"type": "number", "default": 5.0}}, "required": ["belief_id", "action"]}},
    {"name": "search_memories",
     "description": "Search emotional memories by semantic similarity. Returns memories with their mood state at time of encoding, trust zone, and encoding weight.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "include_mood": {"type": "boolean", "default": True},
         "limit": {"type": "integer", "default": 5}}, "required": ["query"]}},
    {"name": "store_emotional_memory",
     "description": "Store an emotional memory with the current mood state attached. Subject to governance — may be held for review if encoding weight is high or content is sensitive.",
     "input_schema": {"type": "object", "properties": {
         "content": {"type": "string"}, "topic_tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["content"]}},
    {"name": "manage_authority",
     "description": "Add or update an authority source in the trust hierarchy. Authority sources feed Engine 1 (Persona) — their influence is trust-discounted, not taken at face value.",
     "input_schema": {"type": "object", "properties": {
         "source_id": {"type": "string"}, "name": {"type": "string"},
         "tier": {"type": "string", "enum": ["formal", "institutional", "personal", "peer", "ambient"]},
         "trust_weight": {"type": "number"}, "influence_topics": {"type": "array", "items": {"type": "string"}}},
         "required": ["source_id", "name", "tier"]}},
    {"name": "get_influence_analysis",
     "description": "Analyze all influence sources, compliance tendency, and reward profile. Shows who shapes the user's Persona (Engine 1) and what reward patterns drive Engine 2.",
     "input_schema": {"type": "object", "properties": {
         "topic": {"type": "string"}, "include_conflicts": {"type": "boolean", "default": True}}}},
    {"name": "get_gap_analysis",
     "description": "Get dual-engine gap analysis. Surfaces 'theatre' — where stated priorities (Engine 1: Persona) and actual engagement (Engine 2: Reward) diverge. The gap predicts behavior better than either engine alone.",
     "input_schema": {"type": "object", "properties": {
         "topic": {"type": "string"}, "include_trend": {"type": "boolean", "default": True}}}},
    {"name": "explain_behavior",
     "description": "Explain seemingly irrational behavior using the gap between Persona and Reward engines. Uses the divergence pattern to generate an explanation for why the user acts against their stated values.",
     "input_schema": {"type": "object", "properties": {
         "behavior": {"type": "string"}, "context": {"type": "string", "default": ""}},
         "required": ["behavior"]}},
    {"name": "list_holds",
     "description": "List governance holds — actions that were paused for human review before execution.",
     "input_schema": {"type": "object", "properties": {
         "include_resolved": {"type": "boolean", "default": False}}}},
    {"name": "resolve_hold",
     "description": "Resolve a governance hold by approving or rejecting the paused action.",
     "input_schema": {"type": "object", "properties": {
         "hold_id": {"type": "string"}, "decision": {"type": "string", "enum": ["approve", "reject"]},
         "reason": {"type": "string", "default": ""}}, "required": ["hold_id", "decision"]}},
]


# =============================================================================
# CONTEXT ASSEMBLY
# =============================================================================

def assemble_context(
    mood: Optional[MoodState],
    beliefs_summary: dict,
    gap_analysis: Optional[GapAnalysis],
    recent_memories: list,
    authority_info: dict,
    mood_trend: dict,
) -> str:
    context = {}

    if mood:
        context["current_mood"] = {
            "valence": round(mood.valence, 3), "arousal": round(mood.arousal, 3),
            "quadrant": mood.quadrant.value, "intensity": round(mood.intensity, 3),
            "confidence": round(mood.confidence, 3),
        }

    if mood_trend:
        context["mood_trend"] = mood_trend

    if beliefs_summary:
        high_conf = {k: v for k, v in beliefs_summary.get("beliefs", {}).items()
                     if v.get("probability", 0) > 0.7}
        uncertain = {k: v for k, v in beliefs_summary.get("beliefs", {}).items()
                     if 0.3 <= v.get("probability", 0) <= 0.7}
        if high_conf:
            context["strong_beliefs"] = {
                k: f"{v['text']} ({v['probability']:.0%})"
                for k, v in list(high_conf.items())[:5]
            }
        if uncertain:
            context["uncertain_beliefs"] = {
                k: f"{v['text']} ({v['probability']:.0%})"
                for k, v in list(uncertain.items())[:5]
            }

    if gap_analysis and gap_analysis.topic_gaps:
        gaps_data = {}
        for g in gap_analysis.topic_gaps[:5]:
            gaps_data[g.topic] = {
                "persona_says": round(g.persona_opinion, 2),
                "reward_wants": round(g.reward_opinion, 2),
                "gap": round(g.gap_magnitude, 2),
                "severity": g.conflict_severity, "direction": g.gap_direction,
            }
        context["dual_engine_gaps"] = gaps_data
        context["theatre_score"] = round(gap_analysis.theatre_score, 3)
        context["dominant_engine"] = gap_analysis.dominant_engine

    if authority_info:
        sources = authority_info.get("authority_sources", {})
        if sources:
            context["authority_sources"] = {
                k: f"{v['name']} ({v['tier']}, trust={v['trust_weight']})"
                for k, v in list(sources.items())[:5]
            }
        context["compliance"] = authority_info.get("compliance_tendency", "balanced")

    if recent_memories:
        context["relevant_memories"] = [
            m.get("content", "")[:100] for m in recent_memories[:3]
        ]

    return yaml.dump(context, default_flow_style=False, sort_keys=False)


# =============================================================================
# AGENT
# =============================================================================

class EmotionalMemoryAgent:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.session_id = f"sess_{uuid.uuid4().hex[:8]}"

        self.client = anthropic.Anthropic()
        self.mood_detector = MoodDetector()
        self.belief_extractor = BeliefExtractor(self.client)
        self.truth_layer = TruthLayer(path=str(self.data_dir / "truth_layer.json"))
        self.authority = AuthorityGraph(self.data_dir)
        self.compliance = ComplianceDetector(self.data_dir)
        self.reward = RewardModel(self.data_dir)
        self.approach_avoidance = ApproachAvoidanceDetector(self.data_dir)
        self.persona_engine = PersonaEngine(self.truth_layer, self.authority, self.compliance)
        self.gap_analyzer = GapAnalyzer(self.data_dir)
        self.memory_store = MemoryStore()
        self.timeline = TimelineManager(self.data_dir)
        self.governance = GovernanceLayer(self.data_dir)

        self.current_mood: Optional[MoodState] = None
        self.current_gap: Optional[GapAnalysis] = None
        self.persona_opinions: Dict[str, EngineOpinion] = {}
        self.reward_opinions: Dict[str, EngineOpinion] = {}
        self.messages: List[dict] = []

    def process_message(self, user_message: str) -> str:
        # 1. Mood detection
        self.current_mood = self.mood_detector.detect(user_message)

        # 2. Belief extraction (simple, no API call)
        belief_deltas = self.belief_extractor.extract_beliefs_simple(user_message)
        authority_refs = self.belief_extractor.detect_authority_refs(user_message)

        # 3. Update belief network
        for delta in belief_deltas:
            self.truth_layer.add_claim(delta.belief_id, delta.text, delta.category)
            if delta.action in ("confirm", "reject"):
                self.truth_layer.validate(delta.belief_id, delta.action)

        # 4. Process authority references
        for ref in authority_refs:
            source_id = ref.source_text.lower().replace(" ", "_")[:20]
            if not self.authority.get_source(source_id):
                self.authority.add_source(
                    source_id=source_id, name=ref.source_text,
                    tier=AuthorityTier(ref.tier),
                    trust_weight=self.authority.get_tier_defaults().get(ref.tier, 0.5),
                )
            self.authority.reference(source_id)

        # 5. Extract topics
        topics = self._extract_topics(user_message, belief_deltas)

        # 6. Dual-engine processing
        # PersonaEngine.process() calls compliance.analyze() internally — no duplicate call
        self.persona_opinions = self.persona_engine.process(
            user_message, self.current_mood, topics)

        for topic in topics:
            aa = self.approach_avoidance.analyze(user_message, topic, self.current_mood)
            r_belief = max(0.0, min(0.95,
                aa.approach_ratio * 0.7 + max(0, self.current_mood.valence) * 0.3))
            r_uncertainty = max(0.05, 0.5 / max(1, aa.observations))
            r_disbelief = max(0.0, 1.0 - r_belief - r_uncertainty)
            self.reward_opinions[topic] = EngineOpinion(
                topic=topic, belief=round(r_belief, 3),
                disbelief=round(r_disbelief, 3), uncertainty=round(r_uncertainty, 3),
                source_signals=[f"approach_ratio:{aa.approach_ratio:.2f}",
                                f"valence:{self.current_mood.valence:.2f}"],
            )

        # 7. Gap analysis
        self.current_gap = self.gap_analyzer.analyze(self.persona_opinions, self.reward_opinions)

        # 8. Update timeline and reward model
        self.timeline.record(self.current_mood, topics, self.session_id)
        for topic in topics:
            reward_cat = TOPIC_TO_REWARD_MAP.get(topic, topic)
            self.reward.observe(reward_cat, self.current_mood.valence)

        # 9. Compute encoding weight (was missing — now wired up)
        ew = compute_encoding_weight(
            self.current_mood,
            next(iter(self.authority.sources.values()), None),
            self.reward.profile,
            self.compliance.profile,
            topics[0] if topics else "general",
        )

        # 10. Search recent memories (was always empty — now wired up)
        recent_memories = []
        try:
            hits = self.memory_store.search(user_message, limit=3)
            for hit in hits:
                fields = hit.get("fields", {})
                recent_memories.append({
                    "content": fields.get("content", ""),
                    "valence": fields.get("valence", 0.0),
                    "quadrant": fields.get("quadrant", "neutral"),
                })
        except Exception:
            pass

        # 11. Build context
        beliefs_summary = {"beliefs": {}}
        for cid, b in self.truth_layer.net.beliefs.items():
            beliefs_summary["beliefs"][cid] = {"text": b.text, "probability": b.probability}

        authority_info = {
            "authority_sources": self.authority.to_dict(),
            "compliance_tendency": (
                "rule_follower" if self.compliance.profile.compliance_score > 0.6
                else "rule_bender" if self.compliance.profile.compliance_score < 0.4
                else "balanced"
            ),
        }

        context_yaml = assemble_context(
            mood=self.current_mood, beliefs_summary=beliefs_summary,
            gap_analysis=self.current_gap, recent_memories=recent_memories,
            authority_info=authority_info, mood_trend=self.timeline.get_trend(),
        )

        # 12. Call Claude
        system_prompt = SYSTEM_PROMPT.format(context_yaml=context_yaml)
        self.messages.append({"role": "user", "content": user_message})
        return self._call_claude(system_prompt)

    def _call_claude(self, system_prompt: str) -> str:
        model = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
        max_tokens = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))

        response = self.client.messages.create(
            model=model, max_tokens=max_tokens, system=system_prompt,
            tools=AGENT_TOOLS, messages=self.messages, temperature=0.7,
        )

        for _ in range(10):
            if response.stop_reason != "tool_use":
                break
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._dispatch_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })
            self.messages.append({"role": "assistant", "content": response.content})
            self.messages.append({"role": "user", "content": tool_results})
            response = self.client.messages.create(
                model=model, max_tokens=max_tokens, system=system_prompt,
                tools=AGENT_TOOLS, messages=self.messages, temperature=0.7,
            )

        final_text = "".join(block.text for block in response.content if hasattr(block, "text"))
        self.messages.append({"role": "assistant", "content": response.content})
        return final_text

    def _dispatch_tool(self, name: str, args: dict) -> dict:
        handlers = {
            "detect_mood": self._tool_detect_mood,
            "get_emotional_timeline": self._tool_get_timeline,
            "query_beliefs": self._tool_query_beliefs,
            "update_belief": self._tool_update_belief,
            "search_memories": self._tool_search_memories,
            "store_emotional_memory": self._tool_store_memory,
            "manage_authority": self._tool_manage_authority,
            "get_influence_analysis": self._tool_get_influence,
            "get_gap_analysis": self._tool_get_gap,
            "explain_behavior": self._tool_explain_behavior,
            "list_holds": self._tool_list_holds,
            "resolve_hold": self._tool_resolve_hold,
        }
        handler = handlers.get(name)
        if handler:
            return handler(**args)
        return {"error": f"Unknown tool: {name}"}

    def _tool_detect_mood(self, message: str) -> dict:
        return self.mood_detector.detect(message).to_dict()

    def _tool_get_timeline(self, topic: str = None, days_back: int = 30) -> dict:
        entries = self.timeline.get_timeline(topic, days_back)
        return {"topic": topic or "global", "entries": entries[-10:],
                "total_entries": len(entries), "trend": self.timeline.get_trend(topic)}

    def _tool_query_beliefs(self, category: str = None, min_probability: float = 0.0) -> dict:
        beliefs = {}
        for cid, b in self.truth_layer.net.beliefs.items():
            if category and b.category != category:
                continue
            if b.probability < min_probability:
                continue
            du = decompose_from_beta(b.alpha, b.beta)
            beliefs[cid] = {
                "text": b.text, "probability": round(b.probability, 3),
                "category": b.category, "variance": round(b.variance, 4),
                "epistemic_fraction": round(du.epistemic_fraction, 3),
                "should_investigate": du.should_gather_more_evidence(),
                "anchored": self.truth_layer.net.anchored.get(cid, False),
            }
        return {"beliefs": beliefs, "total": len(beliefs)}

    def _tool_update_belief(self, belief_id: str, action: str, strength: float = 5.0) -> dict:
        if belief_id not in self.truth_layer.net.beliefs:
            return {"error": f"Belief '{belief_id}' not found"}
        if action == "weaken":
            self.truth_layer.net.update_belief(belief_id, False, strength=strength * 0.5)
        else:
            self.truth_layer.validate(belief_id, action)
        b = self.truth_layer.net.beliefs[belief_id]
        return {"belief_id": belief_id, "new_probability": round(b.probability, 3), "action": action}

    def _tool_search_memories(self, query: str, include_mood: bool = True, limit: int = 5) -> dict:
        try:
            results = self.memory_store.search(query, limit=limit)
            memories = []
            for hit in results:
                fields = hit.get("fields", {})
                entry = {"id": hit.get("_id", ""), "content": fields.get("content", ""),
                         "trust_zone": fields.get("trust_zone", "unverified"),
                         "encoding_weight": fields.get("encoding_weight", 0.5)}
                if include_mood:
                    entry.update({"valence": fields.get("valence", 0.0),
                                  "arousal": fields.get("arousal", 0.0),
                                  "quadrant": fields.get("quadrant", "neutral")})
                memories.append(entry)
            return {"memories": memories, "total": len(memories)}
        except Exception as e:
            return {"error": str(e), "memories": []}

    def _tool_store_memory(self, content: str, topic_tags: list = None) -> dict:
        memory = EmotionalMemory(
            content=content, mood=self.current_mood,
            topic_tags=topic_tags or [], session_id=self.session_id,
        )
        gate_result = self.governance.gate_memory_write(memory)
        if gate_result == "held":
            return {"status": "held", "memory_id": memory.memory_id,
                    "reason": "Memory held for governance review"}
        try:
            self.memory_store.store(memory)
            return {"status": "stored", "memory_id": memory.memory_id,
                    "encoding_weight": memory.encoding_weight}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _tool_manage_authority(self, source_id: str, name: str, tier: str,
                               trust_weight: float = None, influence_topics: list = None) -> dict:
        tier_enum = AuthorityTier(tier)
        if trust_weight is None:
            trust_weight = self.authority.get_tier_defaults().get(tier, 0.5)
        source = self.authority.add_source(
            source_id=source_id, name=name, tier=tier_enum,
            trust_weight=trust_weight, influence_topics=influence_topics or [],
        )
        return {"source_id": source.source_id, "name": source.name,
                "tier": source.tier.value, "trust_weight": source.trust_weight,
                "influence_topics": source.influence_topics}

    def _tool_get_influence(self, topic: str = None, include_conflicts: bool = True) -> dict:
        analysis = {
            "authority_sources": self.authority.to_dict(),
            "compliance_score": round(self.compliance.profile.compliance_score, 3),
            "compliance_tendency": (
                "rule_follower" if self.compliance.profile.compliance_score > 0.6
                else "rule_bender" if self.compliance.profile.compliance_score < 0.4
                else "balanced"),
            "reward_profile": self.reward.get_scores(),
        }
        if topic and include_conflicts:
            relevant = self.authority.get_relevant_sources(topic)
            if relevant:
                analysis["topic_authorities"] = [
                    {"source": s.source_id, "trust": s.trust_weight} for s in relevant]
        return analysis

    def _tool_get_gap(self, topic: str = None, include_trend: bool = True) -> dict:
        analysis = self.current_gap or GapAnalysis()
        result = analysis.to_dict()
        if topic:
            result["topic_gaps"] = [g for g in result.get("topic_gaps", [])
                                    if g.get("topic") == topic]
        return result

    def _tool_explain_behavior(self, behavior: str, context: str = "") -> dict:
        analysis = self.current_gap or GapAnalysis()
        explanation = self.gap_analyzer.explain_behavior(behavior, analysis)
        return {"behavior": behavior, "explanation": explanation,
                "theatre_score": analysis.theatre_score,
                "dominant_engine": analysis.dominant_engine}

    def _tool_list_holds(self, include_resolved: bool = False) -> dict:
        holds = self.governance.all_holds(include_resolved)
        return {
            "holds": [{"hold_id": h.hold_id, "action": h.action, "target_id": h.target_id,
                        "reason": h.reason, "status": h.status} for h in holds],
            "pending_count": len(self.governance.pending_holds()),
        }

    def _tool_resolve_hold(self, hold_id: str, decision: str, reason: str = "") -> dict:
        hold = self.governance.resolve_hold(hold_id, decision, reason)
        if hold:
            return {"hold_id": hold.hold_id, "decision": hold.status, "target_id": hold.target_id}
        return {"error": f"Hold '{hold_id}' not found or already resolved"}

    def _extract_topics(self, message: str, belief_deltas: list) -> List[str]:
        topics = set()
        for delta in belief_deltas:
            topics.add(delta.belief_id)
        topic_keywords = [
            "project", "deadline", "team", "documentation", "shipping",
            "meeting", "review", "budget", "performance", "goals",
        ]
        lower = message.lower()
        for kw in topic_keywords:
            if kw in lower:
                topics.add(kw)
        return list(topics) if topics else ["general"]


# =============================================================================
# MOOD DISPLAY
# =============================================================================

QUADRANT_STYLE = {
    "excited":  ("green",  "++"),
    "calm":     ("blue",   "~~"),
    "stressed": ("red",    "!!"),
    "low":      ("yellow", ".."),
    "neutral":  ("dim",    "--"),
}

CIRCUMPLEX = [
    # 5x5 grid: rows = arousal (high to low), cols = valence (neg to pos)
    # Each cell: (valence_range, arousal_range, label)
    ["  tense ", " nervous", "  alert ", " excited", "  elated"],
    [" annoyed", " uneasy ", " focused", "  happy ", "thrilled"],
    ["  bored ", "   meh  ", "  -YOU- ", " content", " pleased"],
    ["  tired ", "  dull  ", "  calm  ", " relaxed", " serene "],
    ["  spent ", "  numb  ", " drowsy ", " tranqul", "  bliss "],
]


def _gauge_bar(value: float, width: int = 20, neg_color: str = "red",
               pos_color: str = "green") -> str:
    """Render a -1..+1 gauge as a text bar: [====|====]"""
    clamped = max(-1.0, min(1.0, value))
    mid = width // 2
    fill = int(abs(clamped) * mid)
    bar = list("." * width)
    bar[mid] = "|"
    if clamped < 0:
        for i in range(mid - fill, mid):
            bar[i] = "="
        color = neg_color
    elif clamped > 0:
        for i in range(mid + 1, mid + 1 + fill):
            bar[i] = "="
        color = pos_color
    else:
        color = "dim"
    inner = "".join(bar)
    return f"[{color}][{inner}][/{color}]"


def _circumplex_marker(valence: float, arousal: float) -> str:
    """Render a 5x5 circumplex grid with the current position marked."""
    # Map valence/arousal (-1..+1) to grid coords (0..4)
    col = min(4, max(0, int((valence + 1) / 2 * 4.99)))
    row = min(4, max(0, int((1 - arousal) / 2 * 4.99)))  # high arousal = top
    lines = []
    for r, cells in enumerate(CIRCUMPLEX):
        parts = []
        for c, label in enumerate(cells):
            if r == row and c == col:
                parts.append(f"[bold white on blue]{label}[/]")
            else:
                parts.append(f"[dim]{label}[/]")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _render_mood_panel(mood: MoodState, agent: 'EmotionalMemoryAgent') -> str:
    """Build the full mood status display."""
    from rich.text import Text

    q = mood.quadrant.value
    color, icon = QUADRANT_STYLE.get(q, ("dim", "--"))
    lines = []

    # Header: quadrant + confidence
    lines.append(f"  [{color} bold]{icon} {q.upper()}[/{color} bold]"
                 f"  [dim]confidence {mood.confidence:.0%}[/dim]")

    # Gauges
    lines.append(f"  valence  {_gauge_bar(mood.valence, 20, 'red', 'green')}"
                 f"  {mood.valence:+.2f}")
    lines.append(f"  arousal  {_gauge_bar(mood.arousal, 20, 'blue', 'yellow')}"
                 f"  {mood.arousal:+.2f}")

    # Signals
    if mood.signals:
        sig_str = " ".join(f"[dim]{s}[/dim]" for s in mood.signals[:6])
        lines.append(f"  signals  {sig_str}")

    # Reward profile (if enough data)
    scores = agent.reward.get_scores()
    if scores["observations"] >= 3:
        dom = scores["dominant"]
        lines.append(f"  reward   [dim]ach={scores['achievement']:.1f}"
                     f" soc={scores['social_approval']:.1f}"
                     f" aut={scores['autonomy']:.1f}"
                     f" sec={scores['security']:.1f}"
                     f"  dominant=[/dim][bold]{dom}[/bold]")

    # Gap alerts
    if agent.current_gap:
        for gap in agent.current_gap.topic_gaps[:3]:
            if gap.gap_magnitude > 0.15:
                sev_color = {"low": "yellow", "moderate": "red",
                             "high": "red bold", "critical": "white on red"
                             }.get(gap.conflict_severity, "dim")
                lines.append(
                    f"  gap      [dim]{gap.topic}:[/dim] "
                    f"persona={gap.persona_opinion:.0%} "
                    f"reward={gap.reward_opinion:.0%} "
                    f"[{sev_color}]{gap.conflict_severity} "
                    f"({gap.gap_magnitude:.0%})[/{sev_color}]")

    # Trend
    trend = agent.timeline.get_trend()
    if trend.get("direction") and trend["direction"] != "stable":
        arrow = {"improving": "[green]trending up[/green]",
                 "declining": "[red]trending down[/red]"}.get(
            trend["direction"], f"[dim]{trend['direction']}[/dim]")
        lines.append(f"  trend    {arrow}")

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def main():
    from dotenv import load_dotenv
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    load_dotenv()
    console = Console()

    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY not set in .env[/red]")
        sys.exit(1)

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    agent = EmotionalMemoryAgent(data_dir=str(data_dir))

    console.print(Panel(
        Text.from_markup(
            "[bold]Emotional Memory Agent[/bold]\n"
            "Dual-engine: tracks what you [italic]should[/italic] want "
            "vs what you [italic]actually[/italic] want\n"
            "Commands: [bold]quit[/bold] | [bold]holds[/bold] | [bold]mood[/bold]"
        ),
        border_style="blue",
    ))

    while True:
        try:
            user_input = console.input("\n[bold blue]You:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break

        if user_input.lower() == "holds":
            holds = agent.governance.pending_holds()
            if holds:
                for h in holds:
                    console.print(f"  [{h.hold_id}] {h.action}: {h.reason}")
            else:
                console.print("  [dim]No pending holds.[/dim]")
            continue

        if user_input.lower() == "mood":
            if agent.current_mood:
                console.print(Panel(
                    _circumplex_marker(agent.current_mood.valence,
                                      agent.current_mood.arousal),
                    title="[bold]Circumplex Position[/bold]",
                    border_style="blue", width=60,
                ))
            else:
                console.print("  [dim]No mood data yet. Say something first.[/dim]")
            continue

        try:
            response = agent.process_message(user_input)
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            continue

        # Mood status panel
        if agent.current_mood:
            console.print(Panel(
                _render_mood_panel(agent.current_mood, agent),
                title="[bold]Mood[/bold]",
                border_style=QUADRANT_STYLE.get(
                    agent.current_mood.quadrant.value, ("dim", "--"))[0],
                width=72,
            ))

        console.print(f"\n[bold green]Agent:[/bold green] {response}")


if __name__ == "__main__":
    main()
