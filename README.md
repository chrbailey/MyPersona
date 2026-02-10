# MyPersona — Emotional Memory Agent

**Built with Claude Opus 4.6** | Anthropic Hackathon Feb 2026

An AI agent that tracks the gap between who you say you are and who you actually are.

Most AI remembers *what* you said. MyPersona remembers *how you felt* — and uses that to predict what you'll actually do, not just what you claim you'll do.

## The Core Idea

Psychologist E. Tory Higgins' **Self-Discrepancy Theory** (1987) says humans have multiple selves that frequently conflict:

- **The Should-Self**: what authority, rules, and social expectations tell you to value
- **The Want-Self**: what actually energizes you, revealed through behavior

MyPersona implements this as a **dual-engine architecture**:

```
                    ┌─────────────────┐
    User Message ──▶│  Mood Detector   │──▶ valence + arousal + signals
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │  Authority  │  │ Compliance │  │  Belief    │
     │   Graph     │  │  Detector  │  │ Extractor  │
     └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
           │               │               │
           ▼               ▼               ▼
     ┌─────────────────────────────────────────┐
     │         Engine 1 — Persona (Should)      │
     │   authority weight × trust + compliance  │
     └────────────────────┬────────────────────┘
                          │
                          ▼
     ┌─────────────────────────────────────────┐
     │             Gap Layer (Theatre)          │◀── "Where do the
     │      | persona_opinion - reward_opinion | │    engines diverge?"
     └────────────────────┬────────────────────┘
                          │
     ┌────────────────────┴────────────────────┐
     │         Engine 2 — Reward (Want)         │
     │   valence × approach/avoidance + reward  │
     └────────────────────┬────────────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
     ┌──────────┐  ┌───────────┐  ┌──────────────┐
     │ Encoding │  │ Governance│  │ Introspective│
     │  Weight  │  │   Gate    │  │   Narration  │
     └─────┬────┘  └─────┬────┘  └──────┬───────┘
           │             │              │
           ▼             ▼              ▼
     ┌─────────────────────────────────────────┐
     │        Emotional Memory (Pinecone)       │
     │  decay = e^(-t/S), S ~ encoding weight   │
     └─────────────────────────────────────────┘
```

## Why Opus 4.6?

MyPersona uses Opus 4.6's **extended thinking** with adaptive budget allocation:

```python
thinking_budget = 5000                              # baseline
    + theatre_score * 6000    # gap = more thinking
    + intensity * 2000        # emotion = more thinking
# capped at 16,000 tokens
```

When engines diverge (high theatre score) or emotions run hot, the agent automatically allocates more reasoning depth. Routine check-ins get minimal thinking. Crisis moments get deep deliberation. The agent reports this via its **introspective narration layer** — it tells you what it knows, what it's guessing, and where it's blind.

## Features

### Dual-Engine Signal Processing
- **Mood Detector**: 20+ regex patterns for valence + arousal on the circumplex model
- **Authority Graph**: tracks institutional, formal, personal, peer, and ambient authority sources with trust-weighted opinions (subjective logic)
- **Compliance Detector**: "yes sir", "should", "have to" → Should-Self activation
- **Reward Model**: approach/avoidance tracking → Want-Self activation
- **Gap Analyzer**: measures divergence between engines, classifies severity, explains predicted behavior

### Emotional Memory
- **FadeMem Decay**: Ebbinghaus forgetting curve modulated by encoding weight — flashbulb memories persist for months, mundane ones fade in days
- **A-Mem Linking**: Zettelkasten-inspired memory graph — new memories search for related memories and store bidirectional links
- **Governance Gate**: memories with extreme encoding weight (flashbulb) or high conflict are held for human approval before storage

### Introspective Narration
The agent builds a self-model and reports:
- **Mood confidence**: how sure it is about your emotional state
- **Gap confidence**: how much data backs the divergence analysis
- **Belief coverage**: fraction of topics with stable opinions
- **Blind spots**: topics where uncertainty is high
- **What would change its mind**: specific observations that would revise its model

### Belief System
- Bayesian belief network with subjective logic (belief, disbelief, uncertainty triples)
- Trust discounting through authority chains
- Evidence accumulation via cumulative fusion
- Beliefs persist to disk and reload across sessions

## Demo

### Quick Start (no API keys needed)
```bash
# Clone and set up
git clone https://github.com/yourusername/mypersona.git
cd mypersona
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the scripted demo
python3 -m demo.run_demo --fast
```

### Demo Modes
```bash
python3 -m demo.run_demo              # Normal pace (2s between turns)
python3 -m demo.run_demo --fast       # No pauses
python3 -m demo.run_demo --pace 0.5   # Custom pacing (for recording)
python3 -m demo.run_demo --scenario 3 # Run single scenario
python3 -m demo.run_demo --list       # List all scenarios
python3 -m demo.run_demo --live       # Real Opus 4.6 API calls (needs key)
```

### Five Scenarios

| # | Scenario | What It Shows |
|---|----------|---------------|
| 1 | The Compliant Employee | Authority shapes Engine 1 — boss + policy build the Should-Self |
| 2 | The Hidden Passion | Engine 2 activates on shipping — approach signals, positive valence, elaboration |
| 3 | Theatre Detection | Gap Layer surfaces the divergence — "you comply on docs but light up on shipping" |
| 4 | Flashbulb Memory | Crisis triggers governance hold — intense memories need human approval |
| 5 | The Self-Aware Agent | Introspective narration — the agent reports its own uncertainty and blind spots |

### Live Mode (with API key)
```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
python3 -m src.agent
```

Interactive CLI with real-time mood panel, gap alerts, and governance notifications.

## Architecture

```
src/
├── models.py    (379 lines)  Data models — MoodState, EngineOpinion, GapAnalysis,
│                              EmotionalMemory, IntrospectiveNarration, HoldRequest
├── engines.py   (825 lines)  Signal processing — MoodDetector, BeliefExtractor,
│                              AuthorityGraph, ComplianceDetector, RewardModel,
│                              GapAnalyzer, IntrospectiveLayer
├── memory.py    (388 lines)  Storage + governance — MemoryStore (Pinecone),
│                              GovernanceLayer, AuditTrail, emotional_decay()
├── belief.py    (533 lines)  Bayesian belief system — TruthLayer, subjective logic,
│                              trust discounting, evidence fusion
├── agent.py     (835 lines)  Main agent loop — context assembly, tool dispatch,
│                              Opus 4.6 adaptive thinking, CLI
└── server.py    (466 lines)  MCP server — 12 tools over stdio for Claude Code

tests/                        141 tests across 13 files (0.4s)
demo/run_demo.py              5 scripted scenarios with Rich CLI rendering
```

**Total: ~3,400 LOC source + ~1,500 LOC tests + ~700 LOC demo**

## Research Foundations

| Concept | Source | Implementation |
|---------|--------|----------------|
| Self-Discrepancy Theory | Higgins (1987) | Dual-engine architecture |
| Ebbinghaus Forgetting Curve | FadeMem (2025) | `emotional_decay()` with encoding modulation |
| Zettelkasten Memory Links | A-Mem (2024) | `search_with_links()` one-hop expansion |
| Subjective Logic | Jøsang (2016) | Belief triples, trust discount, cumulative fusion |
| Circumplex Model of Affect | Russell (1980) | 4-quadrant mood detection |
| Introspective AI | Anthropic Research (2025) | Agent self-model with blind spot reporting |
| Want/Should Conflict | Bazerman et al. (1998) | Gap layer predicts action-vs-intention |

## Tests

```bash
python3 -m pytest tests/ -v       # 141 tests, ~0.4s
```

Coverage includes:
- Multi-turn pipeline integration (5-turn divergence buildup)
- Governance gate decisions (flashbulb hold, conflict hold, resolve)
- Emotional decay simulation (1hr → 3mo retention curves)
- Gap analysis edge cases (aligned, max divergence, multi-topic)
- Mood detector edge cases (mixed signals, caps rage, emoji, empty)
- Belief system (strengthening, weakening, independence)
- Encoding weight computation

## MCP Server

MyPersona exposes 12 tools over MCP for integration with Claude Code or any MCP client:

| Tool | Description |
|------|-------------|
| `ps_process_message` | Full pipeline: mood → beliefs → engines → gap → introspection |
| `ps_get_mood` | Current emotional state with circumplex position |
| `ps_get_gap_analysis` | Engine divergence report |
| `ps_search_memories` | Semantic search with decay + link expansion |
| `ps_store_memory` | Store with governance gate |
| `ps_get_beliefs` | Current belief network state |
| `ps_get_encoding_weight` | Compute encoding weight for current state |
| `ps_get_introspection` | Self-model report |
| `ps_hold_list` | Pending governance holds |
| `ps_hold_approve` | Approve held memory |
| `ps_hold_reject` | Reject held memory |
| `ps_get_audit_trail` | Full decision history |

## License

MIT
