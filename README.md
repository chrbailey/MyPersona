# MyPersona — Emotional Memory for AI Agents

> **Add emotional memory to any AI agent.** Track user mood, detect when stated values diverge from revealed behavior, and store memories that fade naturally over time — intense moments persist, mundane ones dissolve.

MyPersona is a Python library and MCP server that gives AI agents emotional intelligence: not just remembering *what* users said, but *how they felt* — and using that to predict what they'll actually do versus what they claim they'll do.

**Built with Claude Opus 4.6** | MIT License | ~3,400 LOC | 141 tests

## What Problem Does This Solve?

Current AI memory systems store facts. They don't store emotional context. This means:

- An agent can't tell if a user *wanted* to do something or *felt obligated* to
- All memories have equal weight — a crisis and a lunch order persist identically
- There's no model for *behavioral prediction* — only recall of stated intentions
- Emotionally intense memories (layoffs, breakthroughs, conflicts) get no special treatment

MyPersona solves this with a **dual-engine architecture** based on Self-Discrepancy Theory (Higgins, 1987):

| Engine | Tracks | Signals |
|--------|--------|---------|
| **Engine 1 — Persona (Should-Self)** | What authority, rules, and social pressure say you should value | Compliance language, authority references, espoused beliefs |
| **Engine 2 — Reward (Want-Self)** | What actually energizes you, revealed through behavior | Positive valence, approach behavior, elaboration, excitement |
| **Gap Layer** | Where the engines diverge — predicts action vs. intention | Theatre score: high gap = user will likely follow Want-Self at moment of decision |

## When To Use This

- You're building an AI agent that interacts with users over multiple sessions and needs to remember emotional context
- You want to detect when a user says they'll do X but their behavior signals they'll actually do Y
- You need memory that naturally prioritizes what mattered — not just what happened recently
- You want human-in-the-loop governance over emotionally intense memories before they're stored

## Quick Start

```bash
git clone https://github.com/chrbailey/MyPersona.git
cd MyPersona
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the demo (no API keys needed)
python3 -m demo.run_demo --fast
```

## MCP Server Integration

MyPersona runs as an MCP server over stdio. Any MCP-compatible client (Claude Code, Claude Desktop, custom agents) can use it.

### Register with Claude Code

```bash
claude mcp add mypersona -- python3.11 -m src.server
```

### 12 Tools

| Tool | What It Does | When To Call It |
|------|-------------|-----------------|
| `ps_process_message` | Full pipeline: mood detection → belief extraction → dual-engine analysis → gap detection → introspection | Every user message — this is the main entry point |
| `ps_get_mood` | Current emotional state (valence, arousal, quadrant, confidence, signals) | When you need the user's emotional state without running the full pipeline |
| `ps_get_gap_analysis` | Engine divergence report — where stated values ≠ revealed behavior | After processing messages to check for self-discrepancy |
| `ps_search_memories` | Semantic search with emotional decay and one-hop link expansion | When recalling relevant past interactions |
| `ps_store_memory` | Store a memory with governance gate (intense memories held for human approval) | When a significant moment should be persisted |
| `ps_get_beliefs` | Current belief network — Bayesian opinions with uncertainty | To understand the user's belief landscape |
| `ps_get_encoding_weight` | How strongly the current emotional state would encode a memory | To preview whether a memory would trigger governance |
| `ps_get_introspection` | Agent self-model: what it knows, what it's guessing, where it's blind | When the user asks "what do you know about me?" |
| `ps_hold_list` | Pending governance holds — memories waiting for human approval | For dashboard/UI integration |
| `ps_hold_approve` | Approve a held memory for storage | Human-in-the-loop decision |
| `ps_hold_reject` | Reject a held memory | Human-in-the-loop decision |
| `ps_get_audit_trail` | Full decision history — every gate decision, every hold resolution | For compliance and debugging |

### Example: Processing a Message

```python
# Via MCP tool call
result = await call_tool("ps_process_message", {
    "message": "My boss said documentation is the top priority for Q1",
    "topics": ["documentation"]
})
# Returns: mood state, engine opinions, gap analysis, introspection
```

### Example: Detecting a Gap

After several interactions where a user complies on documentation but lights up when talking about shipping:

```python
gap = await call_tool("ps_get_gap_analysis", {})
# Returns:
# {
#   "theatre_score": 0.67,
#   "topic_gaps": [{
#     "topic": "documentation",
#     "persona_opinion": 0.82,   # high — authority says it matters
#     "reward_opinion": 0.31,    # low — no genuine engagement
#     "gap_magnitude": 0.51,
#     "conflict_severity": "significant",
#     "predicted_behavior": "Will procrastinate on docs, prioritize shipping"
#   }]
# }
```

## Python Library Usage

Use the components directly without MCP:

```python
from src.engines import MoodDetector, GapAnalyzer, PersonaEngine
from src.memory import emotional_decay, GovernanceLayer
from src.belief import TruthLayer

# Detect mood from text
mood = MoodDetector().detect("I can't believe it, everyone got laid off")
# MoodState(valence=-0.95, arousal=+0.45, quadrant=STRESSED, confidence=0.9)

# Compute how fast a memory fades
retention = emotional_decay(hours=720, encoding_weight=1.5, intensity=0.9)
# 0.47 — flashbulb memory still 47% retrievable after 30 days

retention = emotional_decay(hours=720, encoding_weight=0.3, intensity=0.2)
# 0.02 — mundane memory effectively gone after 30 days
```

## How It Works

```
User Message ──▶ Mood Detector ──▶ valence + arousal + signals
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
  Authority      Compliance      Belief
    Graph         Detector       Extractor
       │              │              │
       ▼              ▼              ▼
  ┌─────────────────────────────────────┐
  │     Engine 1 — Persona (Should)     │
  │  authority weight × trust + comply  │
  └──────────────┬──────────────────────┘
                 ▼
  ┌─────────────────────────────────────┐
  │        Gap Layer (Theatre)          │ ◀── divergence score
  │   | persona - reward | per topic   │
  └──────────────┬──────────────────────┘
                 ▼
  ┌─────────────────────────────────────┐
  │     Engine 2 — Reward (Want)        │
  │  valence × approach/avoid + reward  │
  └──────────────┬──────────────────────┘
                 │
      ┌──────────┼──────────┐
      ▼          ▼          ▼
  Encoding   Governance  Introspective
   Weight      Gate       Narration
      │          │          │
      ▼          ▼          ▼
  ┌─────────────────────────────────────┐
  │     Emotional Memory (Pinecone)     │
  │  R = e^(-t/S), S ~ encoding weight │
  └─────────────────────────────────────┘
```

### Key Concepts

**Emotional Decay (FadeMem)**: Memories fade on an Ebbinghaus forgetting curve, modulated by emotional intensity. Flashbulb memories (encoding weight ~1.5) retain ~47% after 30 days. Mundane memories (encoding weight ~0.3) drop to ~2%. This means the agent's memory naturally self-curates over time — what mattered persists, what didn't dissolves.

**Governance Gate**: Memories with extreme encoding weight (flashbulb events) or high engine conflict are held for human approval before storage. This prevents the agent from permanently encoding crisis moments or conflicted states without oversight.

**Introspective Narration**: The agent builds a self-model and reports what it knows (confident), what it's guessing (moderate), and where it's blind (no data). Uses Opus 4.6 extended thinking with adaptive budget: more emotional complexity → more thinking tokens (5,000–16,000 range).

**Subjective Logic**: Beliefs are represented as (belief, disbelief, uncertainty) triples, not simple probabilities. This means the agent distinguishes between "I believe X" and "I have no data about X" — both might show 50% probability, but uncertainty tells them apart.

## Research Foundations

| Concept | Source | How It's Used |
|---------|--------|---------------|
| Self-Discrepancy Theory | Higgins (1987) | Dual-engine: Should-Self vs Want-Self |
| Ebbinghaus Forgetting Curve | FadeMem (2025) | `emotional_decay()` — memories fade unless emotionally reinforced |
| Zettelkasten Memory Links | A-Mem (2024) | Bidirectional memory graph with one-hop expansion on search |
| Subjective Logic | Josang (2016) | Belief triples, trust discounting through authority chains |
| Circumplex Model of Affect | Russell (1980) | 4-quadrant mood detection (excited/calm/stressed/low) |
| Want/Should Conflict | Bazerman et al. (1998) | Gap layer predicts action vs. stated intention |

## File Structure

```
src/
├── models.py    (379 lines)   Data models — MoodState, EngineOpinion, GapAnalysis, etc.
├── engines.py   (825 lines)   Signal processing — mood, authority, compliance, reward, gap
├── memory.py    (388 lines)   Storage + governance — Pinecone, decay, audit trail
├── belief.py    (533 lines)   Bayesian belief system — subjective logic, trust, fusion
├── agent.py     (835 lines)   Agent loop — context assembly, Opus 4.6 adaptive thinking
└── server.py    (466 lines)   MCP server — 12 tools over stdio

tests/                         141 tests across 13 files (0.4s)
demo/run_demo.py               5 scripted scenarios with Rich CLI rendering
```

## Demo

Five scripted scenarios demonstrate the pipeline without API keys:

```bash
python3 -m demo.run_demo --fast       # All 5 scenarios, no pauses
python3 -m demo.run_demo --scenario 3 # Single scenario
python3 -m demo.run_demo --list       # List scenarios
python3 -m demo.run_demo --live       # Real Opus 4.6 API (needs ANTHROPIC_API_KEY)
```

| # | Scenario | Demonstrates |
|---|----------|-------------|
| 1 | The Compliant Employee | Authority builds Engine 1 — boss + policy shape the Should-Self |
| 2 | The Hidden Passion | Engine 2 activates — approach signals, positive valence, elaboration |
| 3 | Theatre Detection | Gap Layer surfaces divergence: comply on docs, light up on shipping |
| 4 | Flashbulb Memory | Crisis triggers governance hold — intense memory needs human approval |
| 5 | The Self-Aware Agent | Introspective narration — agent reports uncertainty and blind spots |

## Tests

```bash
python3 -m pytest tests/ -v    # 141 tests, ~0.4s
```

## Requirements

- Python 3.11+
- Dependencies: `anthropic`, `pinecone`, `rich`, `mcp`, `httpx`, `pyyaml`, `python-dotenv`
- Optional: `ANTHROPIC_API_KEY` for live mode, `PINECONE_API_KEY` for persistent memory

## License

MIT
