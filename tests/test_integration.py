"""Integration tests: multi-turn pipeline, governance, decay, edge cases."""

import math
import tempfile
from pathlib import Path

from src.models import (
    MoodState, EmotionalQuadrant, EmotionalMemory, GapAnalysis,
    TopicGap, EngineOpinion, EncodingWeight, IntrospectiveNarration,
    ComplianceProfile, RewardProfile, AuthorityTier,
)
from src.engines import (
    MoodDetector, BeliefExtractor, AuthorityGraph, ComplianceDetector,
    RewardModel, ApproachAvoidanceDetector, PersonaEngine, GapAnalyzer,
    compute_encoding_weight, IntrospectiveLayer, TOPIC_TO_REWARD_MAP,
)
from src.memory import (
    emotional_decay, GovernanceLayer, AuditTrail, TimelineManager,
)
from src.belief import TruthLayer
from src.agent import assemble_context


# =============================================================================
# MULTI-TURN PIPELINE
# =============================================================================

class TestMultiTurnPipeline:
    """Test the full signal pipeline across multiple simulated turns."""

    def _make_components(self, tmp):
        d = Path(tmp)
        return {
            "mood": MoodDetector(),
            "beliefs": BeliefExtractor(client=None),
            "authority": AuthorityGraph(d),
            "compliance": ComplianceDetector(d),
            "reward": RewardModel(d),
            "aa": ApproachAvoidanceDetector(d),
            "truth": TruthLayer(path=str(d / "truth.json")),
            "gap": GapAnalyzer(d),
            "intro": IntrospectiveLayer(),
        }

    def _process(self, components, text, topics):
        c = components
        mood = c["mood"].detect(text)
        c["beliefs"].detect_authority_refs(text)
        for delta in c["beliefs"].extract_beliefs_simple(text):
            c["truth"].add_claim(delta.belief_id, delta.text)
        persona = PersonaEngine(c["truth"], c["authority"], c["compliance"])
        p_opinions = persona.process(text, mood, topics)
        r_opinions = {}
        for topic in topics:
            aa = c["aa"].analyze(text, topic, mood)
            r_b = max(0.0, min(0.95, aa.approach_ratio * 0.7 + max(0, mood.valence) * 0.3))
            r_u = max(0.05, 0.5 / max(1, aa.observations))
            r_d = max(0.0, 1.0 - r_b - r_u)
            r_opinions[topic] = EngineOpinion(topic=topic, belief=round(r_b, 3),
                                               disbelief=round(r_d, 3), uncertainty=round(r_u, 3),
                                               source_signals=[])
        gap = c["gap"].analyze(p_opinions, r_opinions)
        return mood, p_opinions, r_opinions, gap

    def test_five_turn_divergence_buildup(self):
        """Over 5 turns, authority builds persona while reward goes elsewhere."""
        with tempfile.TemporaryDirectory() as tmp:
            c = self._make_components(tmp)
            # Turn 1: authority says documentation matters
            c["authority"].add_source("boss", "Boss", AuthorityTier.INSTITUTIONAL, 0.8, ["documentation"])
            _, p1, r1, gap1 = self._process(c, "My boss said documentation is top priority", ["documentation"])

            # Turn 2: compliance language
            self._process(c, "Yes sir, I should focus on the docs", ["documentation"])

            # Turn 3: excitement about shipping (reward engine activates)
            _, _, _, gap3 = self._process(c,
                "But honestly, I've been thinking about the new API! What if we could ship by Friday?!",
                ["shipping"])

            # Turn 4: more shipping enthusiasm
            _, _, _, gap4 = self._process(c,
                "And also the webhook endpoint! Let me try something, this is going to be amazing!!",
                ["shipping"])

            # Turn 5: back to docs obligation
            _, p5, r5, gap5 = self._process(c,
                "Oh wait, I should probably get back to the docs...", ["documentation"])

            # Persona engine should be stronger on documentation than reward
            assert p5["documentation"].expected_value > r5["documentation"].expected_value

    def test_authority_builds_persona_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._make_components(tmp)
            c["authority"].add_source("policy", "Company Policy", AuthorityTier.FORMAL, 0.95)
            _, p, _, _ = self._process(c, "The policy requires full documentation before release",
                                        ["documentation"])
            # Authority-boosted persona should have high belief
            assert p["documentation"].expected_value > 0.6

    def test_compliance_detection_across_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._make_components(tmp)
            msgs = [
                "I should finish the report first",
                "Yes sir, understood. Will do.",
                "I need to follow the process",
            ]
            for msg in msgs:
                self._process(c, msg, ["general"])
            assert c["compliance"].profile.compliance_score > 0.6

    def test_reward_model_learns_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._make_components(tmp)
            # Observe shipping-related reward signals directly
            for _ in range(6):
                c["reward"].observe("completion", 0.5)
            assert c["reward"].profile.reward_type.value == "achievement"

    def test_introspective_confidence_improves_with_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._make_components(tmp)
            # Low data
            n1 = c["intro"].analyze(None, None, {}, {}, c["truth"])
            # Add some data
            for i in range(5):
                self._process(c, f"I think documentation is important turn {i}", ["documentation"])
            mood = c["mood"].detect("Documentation matters to me!")
            _, p, r, gap = self._process(c, "I really believe in good docs", ["documentation"])
            n2 = c["intro"].analyze(mood, gap, p, r, c["truth"])
            # Confidence should be higher with more data
            assert n2.mood_confidence >= n1.mood_confidence


# =============================================================================
# GOVERNANCE INTEGRATION
# =============================================================================

class TestGovernanceIntegration:
    def test_flashbulb_memory_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            gov = GovernanceLayer(Path(tmp))
            mem = EmotionalMemory(content="Team got laid off", encoding_weight=1.5, conflict_score=0.2)
            result = gov.gate_memory_write(mem)
            assert result == "held"
            assert len(gov.pending_holds()) == 1

    def test_mundane_memory_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            gov = GovernanceLayer(Path(tmp))
            mem = EmotionalMemory(content="Had lunch", encoding_weight=0.3, conflict_score=0.1)
            result = gov.gate_memory_write(mem)
            assert result == "allowed"

    def test_high_conflict_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            gov = GovernanceLayer(Path(tmp))
            mem = EmotionalMemory(content="Boss vs passion", encoding_weight=0.8, conflict_score=0.7)
            result = gov.gate_memory_write(mem)
            assert result == "held"

    def test_hold_resolve_approve(self):
        with tempfile.TemporaryDirectory() as tmp:
            gov = GovernanceLayer(Path(tmp))
            mem = EmotionalMemory(content="test", encoding_weight=1.5)
            gov.gate_memory_write(mem)
            hold = gov.pending_holds()[0]
            resolved = gov.resolve_hold(hold.hold_id, "approve", "Human reviewed")
            assert resolved.status == "approved"
            assert len(gov.pending_holds()) == 0

    def test_hold_resolve_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            gov = GovernanceLayer(Path(tmp))
            mem = EmotionalMemory(content="test", encoding_weight=1.5)
            gov.gate_memory_write(mem)
            hold = gov.pending_holds()[0]
            resolved = gov.resolve_hold(hold.hold_id, "reject", "Too emotional")
            assert resolved.status == "rejected"

    def test_multiple_holds_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            gov = GovernanceLayer(Path(tmp))
            for i in range(3):
                mem = EmotionalMemory(content=f"intense {i}", encoding_weight=1.5 + i * 0.1)
                gov.gate_memory_write(mem)
            assert len(gov.pending_holds()) == 3

    def test_audit_trail_captures_all_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            gov = GovernanceLayer(d)
            audit = AuditTrail(d)
            # Create and resolve a hold
            mem = EmotionalMemory(content="audit test", encoding_weight=1.5)
            gov.gate_memory_write(mem)
            hold = gov.pending_holds()[0]
            gov.resolve_hold(hold.hold_id, "approve", "tested")
            # Audit should have entries
            entries = audit.read()
            assert len(entries) >= 2  # hold_created + hold_resolved


# =============================================================================
# DECAY SIMULATION
# =============================================================================

class TestDecaySimulation:
    def test_one_hour_all_retained(self):
        assert emotional_decay(1.0, 0.3, 0.2) > 0.95
        assert emotional_decay(1.0, 1.5, 0.9) > 0.99

    def test_one_day_gradient(self):
        mundane = emotional_decay(24.0, 0.3, 0.2)
        flashbulb = emotional_decay(24.0, 1.5, 0.9)
        assert flashbulb > mundane
        assert mundane > 0.5  # should still be mostly retained at 1 day

    def test_one_week_separation(self):
        mundane = emotional_decay(168.0, 0.3, 0.2)
        flashbulb = emotional_decay(168.0, 1.5, 0.9)
        assert flashbulb > 0.7  # flashbulb persists
        assert mundane < flashbulb

    def test_one_month_extreme_separation(self):
        mundane = emotional_decay(720.0, 0.3, 0.2)
        flashbulb = emotional_decay(720.0, 1.5, 0.9)
        assert flashbulb > 0.4  # flashbulb still meaningful
        assert mundane < 0.1   # mundane mostly gone

    def test_three_months(self):
        mundane = emotional_decay(2160.0, 0.3, 0.2)
        flashbulb = emotional_decay(2160.0, 1.5, 0.9)
        assert flashbulb > mundane
        assert mundane <= 0.01  # floor

    def test_zero_age_full_retention(self):
        assert emotional_decay(0.0, 0.5, 0.5) == 1.0

    def test_negative_age_full_retention(self):
        assert emotional_decay(-10.0, 0.5, 0.5) == 1.0

    def test_decay_never_hits_zero(self):
        # Even after a very long time, floor is 0.01
        assert emotional_decay(100000.0, 0.1, 0.1) >= 0.01


# =============================================================================
# CONTEXT ASSEMBLY
# =============================================================================

class TestContextAssembly:
    def test_full_context_with_narration(self):
        mood = MoodState(valence=0.5, arousal=0.3, confidence=0.7,
                         quadrant=EmotionalQuadrant.EXCITED, signals=["v_excitement"])
        narration = IntrospectiveNarration(
            mood_confidence=0.7, gap_confidence=0.3, belief_coverage=0.5,
            blind_spots=["shipping"], reasoning_depth="deliberate",
        )
        ctx = assemble_context(mood=mood, beliefs_summary={}, gap_analysis=None,
                               recent_memories=[], authority_info={}, mood_trend={},
                               narration=narration)
        assert "self_model" in ctx
        assert "deliberate" in ctx

    def test_context_without_narration(self):
        mood = MoodState(valence=0.0, arousal=0.0, confidence=0.3,
                         quadrant=EmotionalQuadrant.NEUTRAL, signals=[])
        ctx = assemble_context(mood=mood, beliefs_summary={}, gap_analysis=None,
                               recent_memories=[], authority_info={}, mood_trend={})
        assert "self_model" not in ctx

    def test_context_with_memories(self):
        ctx = assemble_context(mood=None, beliefs_summary={}, gap_analysis=None,
                               recent_memories=[{"content": "remember this"}],
                               authority_info={}, mood_trend={})
        assert "relevant_memories" in ctx


# =============================================================================
# GAP ANALYSIS EDGE CASES
# =============================================================================

class TestGapAnalysisEdgeCases:
    def test_single_engine_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            gap = GapAnalyzer(Path(tmp))
            p = {"docs": EngineOpinion("docs", 0.8, 0.1, 0.1, ["espoused"])}
            r = {}
            analysis = gap.analyze(p, r)
            # No gap when only one engine has data
            assert len(analysis.topic_gaps) == 0

    def test_perfectly_aligned(self):
        with tempfile.TemporaryDirectory() as tmp:
            gap = GapAnalyzer(Path(tmp))
            p = {"docs": EngineOpinion("docs", 0.7, 0.1, 0.2, [])}
            r = {"docs": EngineOpinion("docs", 0.7, 0.1, 0.2, [])}
            analysis = gap.analyze(p, r)
            assert analysis.topic_gaps[0].gap_magnitude < 0.01

    def test_maximum_divergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            gap = GapAnalyzer(Path(tmp))
            p = {"docs": EngineOpinion("docs", 0.95, 0.0, 0.05, [])}
            r = {"docs": EngineOpinion("docs", 0.05, 0.9, 0.05, [])}
            analysis = gap.analyze(p, r)
            assert analysis.topic_gaps[0].gap_magnitude > 0.5

    def test_empty_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            gap = GapAnalyzer(Path(tmp))
            analysis = gap.analyze({}, {})
            assert len(analysis.topic_gaps) == 0
            assert analysis.theatre_score == 0.0

    def test_multi_topic_divergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            gap = GapAnalyzer(Path(tmp))
            p = {
                "docs": EngineOpinion("docs", 0.8, 0.1, 0.1, []),
                "shipping": EngineOpinion("shipping", 0.3, 0.4, 0.3, []),
            }
            r = {
                "docs": EngineOpinion("docs", 0.3, 0.4, 0.3, []),
                "shipping": EngineOpinion("shipping", 0.8, 0.1, 0.1, []),
            }
            analysis = gap.analyze(p, r)
            assert len(analysis.topic_gaps) == 2

    def test_gap_history_accumulates(self):
        with tempfile.TemporaryDirectory() as tmp:
            gap = GapAnalyzer(Path(tmp))
            p = {"docs": EngineOpinion("docs", 0.8, 0.1, 0.1, [])}
            r = {"docs": EngineOpinion("docs", 0.3, 0.4, 0.3, [])}
            for _ in range(5):
                gap.analyze(p, r)
            assert len(gap.history.get("docs", [])) == 5

    def test_explain_behavior_with_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            gap = GapAnalyzer(Path(tmp))
            p = {"docs": EngineOpinion("docs", 0.8, 0.1, 0.1, [])}
            r = {"docs": EngineOpinion("docs", 0.3, 0.4, 0.3, [])}
            # Run enough times to make significant
            for _ in range(5):
                analysis = gap.analyze(p, r)
            explanation = gap.explain_behavior("procrastinating on docs", analysis)
            assert len(explanation) > 0


# =============================================================================
# MOOD EDGE CASES
# =============================================================================

class TestMoodEdgeCases:
    def test_mixed_signals(self):
        md = MoodDetector()
        mood = md.detect("I'm happy but also worried about the deadline")
        # Both positive and negative signals should be detected
        assert any("v_" in s for s in mood.signals)
        assert mood.confidence > 0.3

    def test_very_long_message(self):
        md = MoodDetector()
        mood = md.detect("word " * 100)
        assert "a_long_message" in mood.signals

    def test_all_caps_rage(self):
        md = MoodDetector()
        mood = md.detect("THIS IS ABSOLUTELY RIDICULOUS AND I HATE IT")
        assert mood.valence < 0
        assert mood.arousal > 0

    def test_emoji_positive(self):
        md = MoodDetector()
        mood = md.detect("That's so funny 😂😄")
        assert mood.valence > 0

    def test_empty_string(self):
        md = MoodDetector()
        mood = md.detect("")
        assert mood.quadrant == EmotionalQuadrant.NEUTRAL

    def test_profanity_negative(self):
        md = MoodDetector()
        mood = md.detect("What the fuck, this is bullshit")
        assert mood.valence < 0

    def test_hedging_low_arousal(self):
        md = MoodDetector()
        mood = md.detect("Maybe we should perhaps consider it, not sure")
        assert mood.arousal < 0

    def test_shock_crisis(self):
        md = MoodDetector()
        mood = md.detect("I can't believe it, everyone got laid off. I'm in shock.")
        assert mood.valence < -0.5
        assert mood.arousal > 0
        assert mood.quadrant == EmotionalQuadrant.STRESSED

    def test_grief_loss(self):
        md = MoodDetector()
        mood = md.detect("I'm devastated, everything is gone and I feel crushed")
        assert mood.valence < -0.5
        assert any("v_loss" in s or "v_grief" in s for s in mood.signals)


# =============================================================================
# BELIEF INTEGRATION
# =============================================================================

class TestBeliefIntegration:
    def test_belief_strengthens_with_repetition(self):
        with tempfile.TemporaryDirectory() as tmp:
            tl = TruthLayer(path=str(Path(tmp) / "truth.json"))
            tl.add_claim("docs_matter", "Documentation matters")
            tl.validate("docs_matter", "confirm")
            tl.validate("docs_matter", "confirm")
            assert tl.get_probability("docs_matter") > 0.9

    def test_belief_weakens_with_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            tl = TruthLayer(path=str(Path(tmp) / "truth.json"))
            tl.add_claim("docs_matter", "Documentation matters")
            tl.validate("docs_matter", "reject")
            assert tl.get_probability("docs_matter") < 0.5

    def test_multiple_beliefs_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tl = TruthLayer(path=str(Path(tmp) / "truth.json"))
            tl.add_claim("a", "Claim A")
            tl.add_claim("b", "Claim B")
            tl.validate("a", "confirm")
            tl.validate("b", "reject")
            assert tl.get_probability("a") > 0.7
            assert tl.get_probability("b") < 0.3


# =============================================================================
# ENCODING WEIGHT EDGE CASES
# =============================================================================

class TestEncodingWeightEdgeCases:
    def test_calm_no_authority(self):
        mood = MoodState(valence=0.0, arousal=0.0, confidence=0.3,
                         quadrant=EmotionalQuadrant.NEUTRAL, signals=[])
        rp = RewardProfile()
        cp = ComplianceProfile()
        ew = compute_encoding_weight(mood, None, rp, cp, "general")
        # Should be low — no emotional intensity, no authority
        assert ew.total_weight < 0.5

    def test_high_arousal_with_authority(self):
        mood = MoodState(valence=-0.8, arousal=0.9, confidence=0.9,
                         quadrant=EmotionalQuadrant.STRESSED, signals=["v_shock", "a_crisis"])
        from src.models import AuthoritySource
        auth = AuthoritySource(source_id="boss", name="Boss",
                               tier=AuthorityTier.INSTITUTIONAL, trust_weight=0.85)
        cp = ComplianceProfile(alpha=8.0, beta=2.0)  # high compliance
        rp = RewardProfile()
        ew = compute_encoding_weight(mood, auth, rp, cp, "team")
        # Should be high — strong emotional + authority
        assert ew.total_weight > 0.5
        assert ew.flashbulb > 0.7


# =============================================================================
# INTROSPECTIVE LAYER
# =============================================================================

class TestIntrospectiveIntegration:
    def test_blind_spots_detected(self):
        intro = IntrospectiveLayer()
        truth = TruthLayer.__new__(TruthLayer)
        truth.net = type('Net', (), {'beliefs': {}})()
        truth.get_belief = lambda self, x: None
        truth.get_belief = lambda x: None
        p = {"docs": EngineOpinion("docs", 0.3, 0.2, 0.5, [])}
        r = {"shipping": EngineOpinion("shipping", 0.2, 0.3, 0.5, [])}
        narration = intro.analyze(None, None, p, r, truth)
        assert len(narration.blind_spots) > 0

    def test_deep_reasoning_on_high_budget(self):
        intro = IntrospectiveLayer()
        truth = TruthLayer.__new__(TruthLayer)
        truth.net = type('Net', (), {'beliefs': {}})()
        truth.get_belief = lambda x: None
        narration = intro.analyze(None, None, {}, {}, truth, thinking_budget=15000)
        assert narration.reasoning_depth == "deep"

    def test_narrative_output(self):
        n = IntrospectiveNarration(
            mood_confidence=0.3, blind_spots=["shipping", "docs"],
            would_change_mind=["more signals"],
        )
        text = n.narrative()
        assert "guessing" in text
        assert "shipping" in text
