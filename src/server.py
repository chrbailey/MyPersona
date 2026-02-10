"""
MCP server for MyPersona emotional memory agent.
Exposes all 12 tools over stdio for Claude Code integration.

Usage:
    python3.11 -m src.server          # Direct run
    claude mcp add mypersona ...      # Register with Claude Code
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .models import (
    MoodState, GapAnalysis, EngineOpinion, EmotionalQuadrant,
    EmotionalMemory, AuthorityTier,
)
from .belief import TruthLayer, decompose_from_beta
from .engines import (
    MoodDetector, BeliefExtractor,
    AuthorityGraph, ComplianceDetector, RewardModel,
    ApproachAvoidanceDetector, PersonaEngine, GapAnalyzer,
    compute_encoding_weight, TOPIC_TO_REWARD_MAP,
)
from .memory import MemoryStore, TimelineManager, GovernanceLayer, AuditTrail

# Logging to stderr only — stdout is reserved for MCP JSON-RPC
logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mypersona")

load_dotenv()

# =============================================================================
# DATA DIRECTORY
# =============================================================================

DATA_DIR = Path.home() / ".mypersona"
DATA_DIR.mkdir(exist_ok=True)
log.info(f"Data directory: {DATA_DIR}")

# =============================================================================
# ENGINE INITIALIZATION
# =============================================================================

mood_detector = MoodDetector()
belief_extractor = BeliefExtractor()
truth_layer = TruthLayer(path=str(DATA_DIR / "truth_layer.json"))
authority_graph = AuthorityGraph(DATA_DIR)
compliance_detector = ComplianceDetector(DATA_DIR)
reward_model = RewardModel(DATA_DIR)
approach_avoidance = ApproachAvoidanceDetector(DATA_DIR)
persona_engine = PersonaEngine(truth_layer, authority_graph, compliance_detector)
gap_analyzer = GapAnalyzer(DATA_DIR)
memory_store = MemoryStore()
timeline_manager = TimelineManager(DATA_DIR)
governance = GovernanceLayer(DATA_DIR)

# Mutable state
_current_mood: Optional[MoodState] = None
_current_gap: Optional[GapAnalysis] = None
_persona_opinions: dict = {}
_reward_opinions: dict = {}
_session_id = "mcp_session"

# =============================================================================
# MCP SERVER
# =============================================================================

mcp = FastMCP(
    "mypersona",
    instructions=(
        "Emotional memory tools for tracking how users feel across conversations. "
        "Two engines: Engine 1 (Persona/Should-Self) tracks authority, compliance, "
        "espoused beliefs. Engine 2 (Reward/Want-Self) tracks what actually energizes "
        "them. The gap between engines predicts behavior better than either alone. "
        "Use detect_mood on each user message, then query tools as needed."
    ),
)


@mcp.tool()
def detect_mood(message: str) -> str:
    """Analyze emotional signals in a user message.

    Returns valence (-1 to +1), arousal (-1 to +1), quadrant
    (excited/calm/stressed/low/neutral), and confidence.
    Also runs belief extraction, authority detection, compliance analysis,
    approach/avoidance tracking, and dual-engine gap analysis.
    Call this on every user message to keep the emotional state current.

    Args:
        message: The user's message text to analyze
    """
    global _current_mood, _current_gap, _persona_opinions, _reward_opinions

    # 1. Mood detection
    _current_mood = mood_detector.detect(message)

    # 2. Belief extraction (simple regex, no API call)
    belief_deltas = belief_extractor.extract_beliefs_simple(message)
    authority_refs = belief_extractor.detect_authority_refs(message)

    # 3. Update belief network
    for delta in belief_deltas:
        truth_layer.add_claim(delta.belief_id, delta.text, delta.category)
        if delta.action in ("confirm", "reject"):
            truth_layer.validate(delta.belief_id, delta.action)

    # 4. Process authority references
    for ref in authority_refs:
        source_id = ref.source_text.lower().replace(" ", "_")[:20]
        if not authority_graph.get_source(source_id):
            authority_graph.add_source(
                source_id=source_id, name=ref.source_text,
                tier=AuthorityTier(ref.tier),
                trust_weight=authority_graph.get_tier_defaults().get(ref.tier, 0.5),
            )
        authority_graph.reference(source_id)

    # 5. Extract topics
    topics = _extract_topics(message, belief_deltas)

    # 6. Dual-engine processing
    _persona_opinions = persona_engine.process(message, _current_mood, topics)

    for topic in topics:
        aa = approach_avoidance.analyze(message, topic, _current_mood)
        r_belief = max(0.0, min(0.95,
            aa.approach_ratio * 0.7 + max(0, _current_mood.valence) * 0.3))
        r_uncertainty = max(0.05, 0.5 / max(1, aa.observations))
        r_disbelief = max(0.0, 1.0 - r_belief - r_uncertainty)
        _reward_opinions[topic] = EngineOpinion(
            topic=topic, belief=round(r_belief, 3),
            disbelief=round(r_disbelief, 3), uncertainty=round(r_uncertainty, 3),
            source_signals=[f"approach_ratio:{aa.approach_ratio:.2f}",
                            f"valence:{_current_mood.valence:.2f}"],
        )

    # 7. Gap analysis
    _current_gap = gap_analyzer.analyze(_persona_opinions, _reward_opinions)

    # 8. Update timeline and reward model
    timeline_manager.record(_current_mood, topics, _session_id)
    for topic in topics:
        reward_cat = TOPIC_TO_REWARD_MAP.get(topic, topic)
        reward_model.observe(reward_cat, _current_mood.valence)

    # 9. Build result
    result = _current_mood.to_dict()
    result["topics_detected"] = topics
    result["beliefs_extracted"] = len(belief_deltas)
    result["authority_refs"] = len(authority_refs)
    if _current_gap and _current_gap.topic_gaps:
        result["gaps"] = [
            {"topic": g.topic, "magnitude": round(g.gap_magnitude, 3),
             "severity": g.conflict_severity, "direction": g.gap_direction}
            for g in _current_gap.topic_gaps if g.gap_magnitude > 0.1
        ]
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_emotional_timeline(topic: str = "", days_back: int = 30) -> str:
    """Get the user's mood history for a topic over time.

    Shows emotional trajectory and trends. Useful for spotting shifts
    in how they feel about recurring subjects.

    Args:
        topic: Topic to filter by (empty for global timeline)
        days_back: How many days of history to return
    """
    entries = timeline_manager.get_timeline(topic or None, days_back)
    return json.dumps({
        "topic": topic or "global",
        "entries": entries[-10:],
        "total_entries": len(entries),
        "trend": timeline_manager.get_trend(topic or None),
    }, indent=2, default=str)


@mcp.tool()
def query_beliefs(category: str = "", min_probability: float = 0.0) -> str:
    """Query the user's current beliefs with Bayesian confidence levels.

    Includes epistemic vs aleatoric uncertainty decomposition.

    Args:
        category: Filter by category (project/personal/team/technical)
        min_probability: Minimum probability threshold
    """
    beliefs = {}
    for cid, b in truth_layer.net.beliefs.items():
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
        }
    return json.dumps({"beliefs": beliefs, "total": len(beliefs)}, indent=2)


@mcp.tool()
def update_belief(belief_id: str, action: str, strength: float = 5.0) -> str:
    """Update a belief's strength.

    Confirm reinforces it, reject weakens it, weaken reduces confidence
    without full rejection.

    Args:
        belief_id: ID of the belief to update
        action: One of: confirm, reject, weaken
        strength: How strongly to apply the update (default 5.0)
    """
    if belief_id not in truth_layer.net.beliefs:
        return json.dumps({"error": f"Belief '{belief_id}' not found"})
    if action == "weaken":
        truth_layer.net.update_belief(belief_id, False, strength=strength * 0.5)
    else:
        truth_layer.validate(belief_id, action)
    b = truth_layer.net.beliefs[belief_id]
    return json.dumps({
        "belief_id": belief_id,
        "new_probability": round(b.probability, 3),
        "action": action,
    })


@mcp.tool()
def search_memories(query: str, include_mood: bool = True, limit: int = 5) -> str:
    """Search emotional memories by semantic similarity.

    Returns memories with their mood state at time of encoding,
    trust zone, and encoding weight.

    Args:
        query: Text to search for
        include_mood: Whether to include mood data in results
        limit: Maximum number of results
    """
    try:
        results = memory_store.search(query, limit=limit)
        memories = []
        for hit in results:
            fields = hit.get("fields", {})
            entry = {
                "id": hit.get("_id", ""),
                "content": fields.get("content", ""),
                "trust_zone": fields.get("trust_zone", "unverified"),
                "encoding_weight": fields.get("encoding_weight", 0.5),
            }
            if include_mood:
                entry.update({
                    "valence": fields.get("valence", 0.0),
                    "arousal": fields.get("arousal", 0.0),
                    "quadrant": fields.get("quadrant", "neutral"),
                })
            memories.append(entry)
        return json.dumps({"memories": memories, "total": len(memories)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "memories": []})


@mcp.tool()
def store_emotional_memory(content: str, topic_tags: list[str] | None = None) -> str:
    """Store an emotional memory with the current mood state attached.

    Subject to governance — may be held for review if encoding weight
    is high or content is sensitive.

    Args:
        content: The memory content to store
        topic_tags: Optional tags for categorization
    """
    memory = EmotionalMemory(
        content=content, mood=_current_mood,
        topic_tags=topic_tags or [], session_id=_session_id,
    )
    gate_result = governance.gate_memory_write(memory)
    if gate_result == "held":
        return json.dumps({
            "status": "held", "memory_id": memory.memory_id,
            "reason": "Memory held for governance review",
        })
    try:
        memory_store.store(memory)
        return json.dumps({
            "status": "stored", "memory_id": memory.memory_id,
            "encoding_weight": memory.encoding_weight,
        })
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
def manage_authority(source_id: str, name: str, tier: str,
                     trust_weight: float = -1.0,
                     influence_topics: list[str] | None = None) -> str:
    """Add or update an authority source in the trust hierarchy.

    Authority sources feed Engine 1 (Persona). Their influence is
    trust-discounted, not taken at face value.

    Args:
        source_id: Unique identifier for this source
        name: Display name
        tier: One of: formal, institutional, personal, peer, ambient
        trust_weight: Trust level 0-1 (negative = use tier default)
        influence_topics: Topics this source has authority over
    """
    tier_enum = AuthorityTier(tier)
    if trust_weight < 0:
        trust_weight = authority_graph.get_tier_defaults().get(tier, 0.5)
    source = authority_graph.add_source(
        source_id=source_id, name=name, tier=tier_enum,
        trust_weight=trust_weight, influence_topics=influence_topics or [],
    )
    return json.dumps({
        "source_id": source.source_id, "name": source.name,
        "tier": source.tier.value, "trust_weight": source.trust_weight,
        "influence_topics": source.influence_topics,
    })


@mcp.tool()
def get_influence_analysis(topic: str = "", include_conflicts: bool = True) -> str:
    """Analyze all influence sources, compliance tendency, and reward profile.

    Shows who shapes Engine 1 (Persona) and what reward patterns drive Engine 2.

    Args:
        topic: Optional topic to focus analysis on
        include_conflicts: Whether to include conflict details
    """
    analysis = {
        "authority_sources": authority_graph.to_dict(),
        "compliance_score": round(compliance_detector.profile.compliance_score, 3),
        "compliance_tendency": (
            "rule_follower" if compliance_detector.profile.compliance_score > 0.6
            else "rule_bender" if compliance_detector.profile.compliance_score < 0.4
            else "balanced"),
        "reward_profile": reward_model.get_scores(),
    }
    if topic and include_conflicts:
        relevant = authority_graph.get_relevant_sources(topic)
        if relevant:
            analysis["topic_authorities"] = [
                {"source": s.source_id, "trust": s.trust_weight} for s in relevant]
    return json.dumps(analysis, indent=2, default=str)


@mcp.tool()
def get_gap_analysis(topic: str = "", include_trend: bool = True) -> str:
    """Get dual-engine gap analysis.

    Surfaces 'theatre' — where stated priorities (Engine 1: Persona) and
    actual engagement (Engine 2: Reward) diverge. The gap predicts behavior
    better than either engine alone.

    Args:
        topic: Optional topic to focus on
        include_trend: Whether to include trend data
    """
    analysis = _current_gap or GapAnalysis()
    result = analysis.to_dict()
    if topic:
        result["topic_gaps"] = [g for g in result.get("topic_gaps", [])
                                if g.get("topic") == topic]
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def explain_behavior(behavior: str, context: str = "") -> str:
    """Explain seemingly irrational behavior using the gap between engines.

    Uses the divergence pattern between Persona and Reward to generate
    an explanation for why the user acts against their stated values.

    Args:
        behavior: Description of the behavior to explain
        context: Optional additional context
    """
    analysis = _current_gap or GapAnalysis()
    explanation = gap_analyzer.explain_behavior(behavior, analysis)
    return json.dumps({
        "behavior": behavior, "explanation": explanation,
        "theatre_score": analysis.theatre_score,
        "dominant_engine": analysis.dominant_engine,
    }, indent=2)


@mcp.tool()
def list_holds(include_resolved: bool = False) -> str:
    """List governance holds — actions paused for human review.

    Args:
        include_resolved: Whether to include already-resolved holds
    """
    holds = governance.all_holds(include_resolved)
    return json.dumps({
        "holds": [{"hold_id": h.hold_id, "action": h.action,
                    "target_id": h.target_id, "reason": h.reason,
                    "status": h.status} for h in holds],
        "pending_count": len(governance.pending_holds()),
    }, indent=2)


@mcp.tool()
def resolve_hold(hold_id: str, decision: str, reason: str = "") -> str:
    """Resolve a governance hold by approving or rejecting the paused action.

    Args:
        hold_id: ID of the hold to resolve
        decision: Either 'approve' or 'reject'
        reason: Optional explanation for the decision
    """
    hold = governance.resolve_hold(hold_id, decision, reason)
    if hold:
        return json.dumps({
            "hold_id": hold.hold_id, "decision": hold.status,
            "target_id": hold.target_id,
        })
    return json.dumps({"error": f"Hold '{hold_id}' not found or already resolved"})


# =============================================================================
# HELPERS
# =============================================================================

def _extract_topics(message: str, belief_deltas: list) -> list[str]:
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
# ENTRY POINT
# =============================================================================

def main():
    log.info("Starting MyPersona MCP server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
