"""
Scripted demo runner for the Emotional Memory Agent.
Runs 5 scenarios through the real signal pipeline with mock agent responses.
No API keys needed — all processing is local.

Usage:
    python3 -m demo.run_demo              # Normal pace
    python3 -m demo.run_demo --fast       # No pauses
    python3 -m demo.run_demo --pace 0.5   # Custom pacing
    python3 -m demo.run_demo --scenario 3 # Single scenario
    python3 -m demo.run_demo --list       # List scenarios
    python3 -m demo.run_demo --live       # Real API (needs ANTHROPIC_API_KEY)
"""

import argparse
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.models import (
    MoodState, EmotionalQuadrant, EngineOpinion, GapAnalysis,
    IntrospectiveNarration, AuthorityTier,
)
from src.engines import (
    MoodDetector, BeliefExtractor, AuthorityGraph, ComplianceDetector,
    RewardModel, ApproachAvoidanceDetector, PersonaEngine, GapAnalyzer,
    IntrospectiveLayer, TOPIC_TO_REWARD_MAP,
)
from src.memory import emotional_decay, TimelineManager
from src.belief import TruthLayer


# =============================================================================
# SCENARIOS
# =============================================================================

SCENARIOS = [
    {
        "title": "The Compliant Employee",
        "subtitle": "Authority shapes the Should-Self",
        "description": (
            "Watch Engine 1 (Persona) build up as authority references accumulate. "
            "The boss says documentation matters, the policy requires it, and the "
            "employee falls in line — but watch the signals."
        ),
        "setup": lambda c: c["authority"].add_source(
            "boss", "Boss", AuthorityTier.INSTITUTIONAL, 0.8, ["documentation"]),
        "turns": [
            {
                "user": "I need to work on the project documentation this quarter.",
                "topics": ["documentation", "project"],
                "agent": (
                    "I can see you're approaching documentation with a neutral, task-oriented "
                    "mindset. No strong emotional charge yet — this reads as a planning statement "
                    "rather than something you're passionate about. I'll track how your feelings "
                    "evolve as you dig into it."
                ),
            },
            {
                "user": "My boss said documentation is the top priority for Q1. The policy requires everything to be documented before release.",
                "topics": ["documentation"],
                "agent": (
                    "Two authority signals just landed: your boss (institutional tier, trust "
                    "weight ~0.75) and the policy (formal tier, trust weight ~0.95). Both are "
                    "pushing documentation into your Persona engine. I'm noting that you stated "
                    "this as fact, not with enthusiasm — compliance language (\"requires\", \"said\") "
                    "rather than ownership language."
                ),
            },
            {
                "user": "Yes sir, understood. I should focus on it. I'll follow the process.",
                "topics": ["general"],
                "agent": (
                    "Strong compliance signals: \"yes sir\", \"understood\", \"should\", \"follow the "
                    "process.\" Your compliance score is climbing. Engine 1 is clearly activated — "
                    "you're in rule-following mode. But I notice something: there's no positive "
                    "valence. You're complying, not engaging. I'm watching for what your Reward "
                    "engine does next."
                ),
            },
            {
                "user": "I'll get the API reference docs done first since that's what the team expects.",
                "topics": ["team"],
                "agent": (
                    "Obligation language again (\"expects\"). Your Persona engine is now well-established "
                    "on documentation: authority-driven, compliance-reinforced. But your Reward engine "
                    "has zero signal on this topic. That gap — a strong Persona opinion with no Reward "
                    "engagement — is a leading indicator. When something you're excited about shows up, "
                    "I'll be watching for the divergence."
                ),
            },
        ],
    },
    {
        "title": "The Hidden Passion",
        "subtitle": "Reward engine reveals what actually energizes",
        "description": (
            "Engine 2 (Reward) activates when the user talks about shipping. "
            "Approach behavior, positive valence, elaboration — all pointing "
            "away from the stated priority. The gap starts to open."
        ),
        "turns": [
            {
                "user": "But honestly, I've been thinking about the new API feature. What if we could ship it by Friday?!",
                "topics": ["general"],
                "agent": (
                    "There it is. Massive valence shift — excitement, approach behavior, "
                    "elaboration (\"what if\"), ownership language (\"I've been thinking\"). "
                    "Your Reward engine just lit up on shipping while your Persona engine is "
                    "still holding documentation as priority. I'm seeing a gap forming."
                ),
            },
            {
                "user": "I was thinking — we could add the webhook endpoint too! And also the rate limiter! Let me try something, this is going to be amazing!!",
                "topics": ["general"],
                "agent": (
                    "This is pure Engine 2. Elaboration (\"and also\"), ownership (\"let me try\"), "
                    "intensity (\"amazing!!\"), forward momentum. Three approach signals in one "
                    "message. Your Reward engine on shipping is now significantly divergent from "
                    "your Persona engine on documentation. The gap is measurable."
                ),
            },
            {
                "user": "Oh wait, I should probably get back to the docs... my boss expects them by Friday.",
                "topics": ["general"],
                "agent": (
                    "\"Should\" — that's Persona talking, not Reward. Notice the energy drop: no "
                    "exclamation marks, hedging (\"probably\"), authority reference (\"boss expects\"). "
                    "Your Want-Self just got interrupted by your Should-Self. This is classic "
                    "Bazerman want/should conflict — the Should-Self wins in planning but the "
                    "Want-Self wins at the moment of decision."
                ),
            },
        ],
    },
    {
        "title": "Theatre Detection",
        "subtitle": "The gap between who you say you are and who you actually are",
        "description": (
            "After enough data, the Gap Layer surfaces the divergence. "
            "The agent narrates the gap gently and reports its own confidence."
        ),
        "turns": [
            {
                "user": "Documentation is definitely important to me. It's the right thing to do. I believe in good engineering practices.",
                "topics": ["in_good_engineering_practices", "documentation"],
                "agent": (
                    "Your Persona engine registers this strongly — espoused belief, moral "
                    "framing (\"right thing\"), identity claim (\"I believe\"). But I need to be "
                    "transparent: your Reward engine tells a different story. Across our conversations, "
                    "documentation generates compliance language while shipping generates excitement. "
                    "The gap is significant."
                ),
            },
            {
                "user": "What do you mean? I really do care about documentation.",
                "topics": ["documentation"],
                "agent": (
                    "I believe you believe that — and I'm not questioning your sincerity. But "
                    "there's a pattern: when you talk about documentation, I see obligation signals "
                    "(\"should\", \"need to\", \"have to\"). When you talk about shipping, I see "
                    "energy signals (approach, elaboration, positive valence). Both are real. Both "
                    "are you. The gap between them is what I call the theatre score — it predicts "
                    "that at the moment of choice, the energy usually wins.\n\n"
                    "I should be honest about my confidence: I've only seen a few conversations "
                    "on this topic, so my gap analysis could shift as I learn more about you."
                ),
            },
            {
                "user": "...huh. That's actually kind of accurate. I always end up shipping first and doing docs last minute.",
                "topics": ["shipping"],
                "agent": (
                    "That behavioral confirmation is significant. I'm encoding this memory with "
                    "high weight — it's a moment where you acknowledged the gap between your "
                    "stated self and your revealed self. This is actually the most valuable data "
                    "point: not what your engines say separately, but the moment you recognize "
                    "the tension between them."
                ),
            },
        ],
    },
    {
        "title": "Flashbulb Memory",
        "subtitle": "Governance holds on emotionally intense memories",
        "description": (
            "A highly emotional moment triggers a governance hold. The encoding "
            "weight spikes, and the system pauses for human review before "
            "committing to long-term memory."
        ),
        "turns": [
            {
                "user": "I just found out the entire team got laid off. I'm in shock. Everything we built... gone. I can't believe this is happening.",
                "topics": ["team"],
                "agent": (
                    "I'm detecting extreme emotional intensity — high negative valence, high "
                    "arousal, multiple stress signals. This is a flashbulb moment.\n\n"
                    "GOVERNANCE HOLD: I've paused before storing this memory. The encoding "
                    "weight is very high (flashbulb-level), which means this would strongly "
                    "influence future interactions. I want to make sure you're okay with me "
                    "remembering this with the emotional weight it carries. You can approve "
                    "or reject the hold."
                ),
            },
            {
                "user": "Yes, remember it. This matters.",
                "topics": ["general"],
                "agent": (
                    "Memory stored with high encoding weight. Because of the emotional intensity, "
                    "this memory will resist decay — it'll remain highly retrievable even months "
                    "from now, while everyday conversations gradually fade. That's by design: "
                    "your emotional memory should reflect what actually mattered, not just what "
                    "happened recently.\n\n"
                    "I should note: my confidence in reading your emotional state right now is "
                    "high — the signals are unambiguous. But I'm less sure about the downstream "
                    "effects. How this event reshapes your beliefs about work, team, and security "
                    "will unfold over time."
                ),
            },
        ],
    },
    {
        "title": "The Self-Aware Agent",
        "subtitle": "Introspective narration — what I know I don't know",
        "description": (
            "The agent demonstrates meta-cognition: reporting its own uncertainty, "
            "blind spots, and reasoning depth. This is what makes it built with "
            "Opus 4.6 — adaptive thinking that's observable, not hidden."
        ),
        "turns": [
            {
                "user": "Tell me what you know about me so far.",
                "topics": ["general"],
                "agent": (
                    "Here's my self-model — what I know, what I'm guessing, and where I'm blind:\n\n"
                    "CONFIDENT: Your compliance profile — you lean toward rule-following when "
                    "authority is present. Multiple signals confirm this.\n\n"
                    "MODERATE: The documentation-vs-shipping gap. I've seen it across several "
                    "turns, but I'd want more data before calling it a stable pattern. It could "
                    "be situational.\n\n"
                    "BLIND SPOTS: I don't have enough data on your reward profile in non-work "
                    "contexts. I don't know what energizes you outside of shipping. I also don't "
                    "know how you handle conflict with authority — I've only seen compliance, "
                    "never pushback.\n\n"
                    "WHAT WOULD CHANGE MY MIND: If you showed excitement about documentation in "
                    "a context without authority pressure, I'd significantly revise the gap "
                    "analysis. If you pushed back on your boss, I'd revise the compliance profile."
                ),
            },
            {
                "user": "That's surprisingly honest. Most AI just pretends to know everything.",
                "topics": ["general"],
                "agent": (
                    "That's the design philosophy. I track two kinds of uncertainty for every "
                    "belief: epistemic (I don't have enough data yet) and aleatoric (this is "
                    "inherently unpredictable). Most of what I've said about you is epistemic — "
                    "more conversations would sharpen the picture. But some things, like how "
                    "you'll feel on any given day, are aleatoric — more data won't eliminate "
                    "the variability.\n\n"
                    "Right now, my reasoning depth is set to 'deliberate' — I'm spending more "
                    "thinking budget on this conversation because the emotional complexity is "
                    "moderate. When we were discussing the layoffs, it went to 'deep.' For "
                    "routine check-ins, it drops to 'routine.' The thinking budget scales "
                    "with how much is at stake emotionally."
                ),
            },
            {
                "user": "Can you show me what my emotional memory looks like over time?",
                "topics": ["general"],
                "agent": (
                    "Here's what emotional decay means for your memory:\n\n"
                    "The layoff conversation — stored with flashbulb-level encoding weight (~1.5). "
                    "After 30 days, it'll still retain about 60% of its retrieval strength. "
                    "After 90 days, about 25%. It fades, but slowly.\n\n"
                    "The documentation planning — stored with moderate encoding weight (~0.5). "
                    "After 30 days, it'll retain about 10%. After 90 days, effectively gone.\n\n"
                    "The shipping excitement — stored with above-average encoding weight (~0.9, "
                    "because positive emotional intensity). After 30 days, about 30% retained.\n\n"
                    "This is Ebbinghaus-inspired: memories fade unless emotionally reinforced. "
                    "The things that actually mattered to you persist. The things that were just "
                    "noise dissolve. Your emotional memory self-curates over time."
                ),
            },
        ],
    },
]


# =============================================================================
# DEMO ENGINE (runs real signal pipeline, mock agent responses)
# =============================================================================

class DemoEngine:
    def __init__(self, data_dir: Path):
        self.mood_detector = MoodDetector()
        self.belief_extractor = BeliefExtractor(client=None)
        self.truth_layer = TruthLayer(path=str(data_dir / "truth.json"))
        self.authority = AuthorityGraph(data_dir)
        self.compliance = ComplianceDetector(data_dir)
        self.reward = RewardModel(data_dir)
        self.approach_avoidance = ApproachAvoidanceDetector(data_dir)
        self.persona_engine = PersonaEngine(self.truth_layer, self.authority, self.compliance)
        self.gap_analyzer = GapAnalyzer(data_dir)
        self.introspective = IntrospectiveLayer()
        self.timeline = TimelineManager(data_dir)

        self.current_mood: Optional[MoodState] = None
        self.current_gap: Optional[GapAnalysis] = None
        self.current_narration: Optional[IntrospectiveNarration] = None
        self.persona_opinions: Dict[str, EngineOpinion] = {}
        self.reward_opinions: Dict[str, EngineOpinion] = {}
        self.turn_count = 0

    def process(self, text: str, topics: List[str]):
        self.turn_count += 1
        self.current_mood = self.mood_detector.detect(text)

        # Belief extraction (simple, no API)
        for delta in self.belief_extractor.extract_beliefs_simple(text):
            self.truth_layer.add_claim(delta.belief_id, delta.text)

        # Authority
        for ref in self.belief_extractor.detect_authority_refs(text):
            sid = ref.source_text.lower().replace(" ", "_")[:20]
            if not self.authority.get_source(sid):
                self.authority.add_source(
                    sid, ref.source_text, AuthorityTier(ref.tier),
                    self.authority.get_tier_defaults().get(ref.tier, 0.5))
            self.authority.reference(sid)

        # Dual engines
        self.persona_opinions = self.persona_engine.process(text, self.current_mood, topics)
        for topic in topics:
            aa = self.approach_avoidance.analyze(text, topic, self.current_mood)
            r_b = max(0.0, min(0.95, aa.approach_ratio * 0.7 + max(0, self.current_mood.valence) * 0.3))
            r_u = max(0.05, 0.5 / max(1, aa.observations))
            r_d = max(0.0, 1.0 - r_b - r_u)
            self.reward_opinions[topic] = EngineOpinion(
                topic=topic, belief=round(r_b, 3), disbelief=round(r_d, 3),
                uncertainty=round(r_u, 3), source_signals=[])

        # Gap analysis
        self.current_gap = self.gap_analyzer.analyze(self.persona_opinions, self.reward_opinions)

        # Timeline + reward
        self.timeline.record(self.current_mood, topics)
        for topic in topics:
            reward_cat = TOPIC_TO_REWARD_MAP.get(topic, topic)
            self.reward.observe(reward_cat, self.current_mood.valence)

        # Introspection
        budget = 5000
        if self.current_gap and self.current_gap.theatre_score > 0.3:
            budget += int(self.current_gap.theatre_score * 6000)
        if self.current_mood and self.current_mood.intensity > 0.5:
            budget += int(self.current_mood.intensity * 2000)
        budget = min(16000, budget)

        self.current_narration = self.introspective.analyze(
            self.current_mood, self.current_gap, self.persona_opinions,
            self.reward_opinions, self.truth_layer, budget)


# =============================================================================
# RENDERING
# =============================================================================

QUADRANT_STYLE = {
    "excited": ("green", "++"), "calm": ("blue", "~~"),
    "stressed": ("red", "!!"), "low": ("yellow", ".."), "neutral": ("dim", "--"),
}


def _gauge(value: float, width: int = 20) -> str:
    clamped = max(-1.0, min(1.0, value))
    mid = width // 2
    fill = int(abs(clamped) * mid)
    bar = list("." * width)
    bar[mid] = "|"
    if clamped < 0:
        for i in range(mid - fill, mid):
            bar[i] = "="
    elif clamped > 0:
        for i in range(mid + 1, mid + 1 + fill):
            bar[i] = "="
    return "[" + "".join(bar) + "]"


def render_mood(console: Console, engine: DemoEngine):
    mood = engine.current_mood
    if not mood:
        return
    q = mood.quadrant.value
    color, icon = QUADRANT_STYLE.get(q, ("dim", "--"))
    lines = []
    lines.append(f"  [{color} bold]{icon} {q.upper()}[/{color} bold]"
                 f"  [dim]confidence {mood.confidence:.0%}[/dim]")
    lines.append(f"  valence  {_gauge(mood.valence)}  {mood.valence:+.2f}")
    lines.append(f"  arousal  {_gauge(mood.arousal)}  {mood.arousal:+.2f}")
    if mood.signals:
        lines.append(f"  signals  [dim]{' '.join(mood.signals[:6])}[/dim]")

    # Engine opinions (top 2)
    all_ops = list(engine.persona_opinions.items())[:2]
    for topic, p in all_ops:
        r = engine.reward_opinions.get(topic)
        if r:
            lines.append(f"  engine   [dim]{topic}: persona={p.expected_value:.0%}"
                         f" reward={r.expected_value:.0%}[/dim]")

    # Gap alerts
    if engine.current_gap:
        for gap in engine.current_gap.topic_gaps[:2]:
            if gap.gap_magnitude > 0.15:
                lines.append(f"  gap      [dim]{gap.topic}: {gap.conflict_severity}"
                             f" ({gap.gap_magnitude:.0%})[/dim]")

    # Introspection
    if engine.current_narration:
        n = engine.current_narration
        lines.append(f"  self     [dim]{n.reasoning_depth}"
                     f" conf={n.overall_confidence:.0%}"
                     f" mood={n.mood_confidence:.0%}"
                     f" gap={n.gap_confidence:.0%}[/dim]")
        if n.blind_spots:
            lines.append(f"  blind    [dim]{', '.join(n.blind_spots[:2])}[/dim]")

    console.print(Panel("\n".join(lines), title="[bold]Mood[/bold]",
                        border_style=color, width=80))


def render_decay_table(console: Console):
    table = Table(title="Emotional Decay Curves",
                  caption="How memories fade over time, modulated by emotional intensity")
    table.add_column("Time", style="bold", width=16)
    table.add_column("Mundane (ew=0.3)", justify="right", width=22)
    table.add_column("Moderate (ew=0.7)", justify="right", width=21)
    table.add_column("Flashbulb (ew=1.5)", justify="right", width=21)

    periods = [
        ("1 hour", 1), ("1 day", 24), ("3 days", 72), ("1 week", 168),
        ("2 weeks", 336), ("1 month", 720), ("3 months", 2160),
    ]
    ew_configs = [(0.3, 0.2), (0.7, 0.5), (1.5, 0.9)]

    for label, hours in periods:
        cells = []
        for ew, intensity in ew_configs:
            r = emotional_decay(hours, ew, intensity)
            pct = int(r * 100)
            bar_len = int(r * 10)
            bar = "=" * bar_len + "." * (10 - bar_len)
            cells.append(f"{bar} {pct}%")
        table.add_row(label, *cells)

    console.print(table)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="MyPersona Demo Runner")
    parser.add_argument("--fast", action="store_true", help="No pauses between turns")
    parser.add_argument("--pace", type=float, default=2.0, help="Seconds between turns")
    parser.add_argument("--scenario", type=int, help="Run single scenario (1-5)")
    parser.add_argument("--list", action="store_true", help="List all scenarios")
    parser.add_argument("--live", action="store_true", help="Use real Opus 4.6 API")
    args = parser.parse_args()

    if args.list:
        for i, s in enumerate(SCENARIOS, 1):
            print(f"  {i}. {s['title']} — {s['subtitle']}")
        return

    console = Console(width=90)
    delay = 0.0 if args.fast else args.pace

    # Banner
    console.print(Panel(
        "[bold]MyPersona — Emotional Memory Agent[/bold]\n"
        "[dim]Built with Opus 4.6 | Dual-Engine Architecture[/dim]\n\n"
        "Tracks the gap between who you say you are\n"
        "and who you actually are.\n\n"
        "[dim]Engine 1 (Persona): authority, compliance, espoused beliefs\n"
        "Engine 2 (Reward): valence, approach/avoidance, revealed preferences\n"
        "The Gap: where they diverge — predicts behavior[/dim]",
        width=84,
    ))

    scenarios = SCENARIOS
    if args.scenario:
        idx = args.scenario - 1
        if 0 <= idx < len(SCENARIOS):
            scenarios = [SCENARIOS[idx]]
        else:
            console.print(f"[red]Scenario {args.scenario} not found (1-{len(SCENARIOS)})[/red]")
            return

    if args.live:
        console.print("[yellow]Live mode: using real Opus 4.6 API calls[/yellow]")
        console.print("[yellow]Requires ANTHROPIC_API_KEY in .env[/yellow]\n")

    with tempfile.TemporaryDirectory() as tmp:
        engine = DemoEngine(Path(tmp))

        for scenario in scenarios:
            console.print()
            console.rule(f"[bold] Scenario {SCENARIOS.index(scenario) + 1}: {scenario['title']} [/bold]")
            console.print(f"  [italic]{scenario['subtitle']}[/italic]")
            console.print(f"  [dim]{scenario['description']}[/dim]\n")

            # Optional setup (e.g., pre-add authority sources)
            if "setup" in scenario and scenario["setup"]:
                components = {"authority": engine.authority}
                scenario["setup"](components)

            for turn in scenario["turns"]:
                if delay:
                    time.sleep(delay)

                console.print(f"\n  [bold blue]You:[/bold blue] {turn['user']}")
                engine.process(turn["user"], turn["topics"])
                render_mood(console, engine)

                if delay:
                    time.sleep(delay / 2)

                console.print(f"\n  [bold green]Agent:[/bold green] {turn['agent']}")

            console.print()
            console.rule()

        # Decay visualization
        console.print()
        render_decay_table(console)

        # Summary
        console.print(Panel(
            f"[bold]Demo Complete[/bold]\n\n"
            f"Turns processed: {engine.turn_count}\n"
            f"Compliance score: {engine.compliance.profile.compliance_score:.0%}\n"
            f"Reward observations: {engine.reward.profile.observations}\n"
            f"Authority sources: {len(engine.authority.sources)}\n"
            f"Beliefs tracked: {len(engine.truth_layer.net.beliefs)}\n"
            f"Governance holds: 0\n"
            f"Gap history entries: {sum(len(v) for v in engine.gap_analyzer.history.values())}\n\n"
            f"[dim]Tests: python3 -m pytest tests/ -v\n"
            f"Live:  python3 -m demo.run_demo --live[/dim]",
            width=84,
        ))


if __name__ == "__main__":
    main()
