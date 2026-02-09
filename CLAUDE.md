# MyPersona — Emotional Memory Agent

## What This Is
Dual-engine emotional memory agent for the "Built with Opus 4.6" hackathon (Feb 10-16, 2026).
Tracks what humans *should* want (Engine 1: Persona) vs what they *actually* want (Engine 2: Reward),
and surfaces the gap between them as the primary insight.

## Full Specification
**READ FIRST:** `/Volumes/OWC drive/Dev/EMOTIONAL-MEMORY-AGENT-SPEC.md`
This is the complete spec (2,189 lines). It contains architecture, data models, code appendices,
file structure, and implementation details. Follow it precisely.

## Build Sequence (follow this order)

### Phase 1: Port Belief Stack (~2,400 LOC)
Port these files, fixing import paths to use the project's package structure:

1. `src/belief/types.py` ← Port from `/Volumes/OWC drive/Dev/belief-math/belief_math/types.py`
2. `src/belief/truth_layer.py` ← Port from `/Volumes/OWC drive/Dev/unified-belief-system/truth_layer.py`
3. `src/belief/decomposition.py` ← Port from `/Volumes/OWC drive/Dev/belief-math/belief_math/decomposition.py`
4. `src/belief/fusion.py` ← Port from `/Volumes/OWC drive/Dev/belief-math/belief_math/subjective_logic.py`
   - Only port: `cumulative_fuse`, `averaging_fuse`, `trust_discount`, `trust_chain`,
     `probability_to_opinion`, `opinion_to_probability`, `blend_uncertainty`, and helpers they need
5. `src/belief/calibration.py` ← Port from `/Volumes/OWC drive/Dev/belief-math/belief_math/calibration.py`

**Import fix pattern:** Change `from .types import ...` to use `src.belief.types` relative imports.
**Test after each port:** Write `tests/test_<module>.py` and run `python -m pytest tests/ -v`.

### Phase 2: Build Perception Layer
6. `src/perception/mood_detector.py` — See Appendix A in spec. Build from scratch.
7. `src/perception/belief_extractor.py` — Opus micro-call wrapper for belief extraction.

### Phase 3: Build Dual-Engine Layer
8. `src/engines/authority.py` — Authority graph with trust weighting (feeds Engine 1)
9. `src/engines/compliance.py` — See Appendix C in spec. Rule-following detector.
10. `src/engines/reward.py` — Reward model with valence-topic correlation tracking
11. `src/engines/approach_avoidance.py` — See Appendix G in spec. Revealed preference tracker.
12. `src/engines/persona.py` — Engine 1: Should-self (combines authority + compliance + espoused beliefs)
13. `src/engines/gap.py` — See Appendix F in spec. Gap Layer / Theatre Detector.
14. `src/engines/encoding.py` — See Appendix D in spec. Encoding weight calculator.

### Phase 4: Build Memory + Governance
15. `src/memory/store.py` — Pinecone wrapper (CRUD for emotional memories)
16. `src/memory/timeline.py` — Emotional time-series tracking per topic
17. `src/governance/trust_zones.py` — unverified → promoted lifecycle
18. `src/governance/holds.py` — See Appendix B in spec. Hold queue.
19. `src/governance/audit.py` — Append-only JSONL audit trail.

### Phase 5: Build Tools + Context + Agent Loop
20. `src/tools/registry.py` — Tool registration and dispatch
21. `src/tools/mood_tools.py` — detect_mood, get_emotional_timeline
22. `src/tools/belief_tools.py` — query_beliefs, update_belief
23. `src/tools/memory_tools.py` — search_memories, store_emotional_memory
24. `src/tools/influence_tools.py` — manage_authority, get_influence_analysis
25. `src/tools/gap_tools.py` — get_gap_analysis, explain_behavior
26. `src/tools/governance_tools.py` — list_holds, resolve_hold
27. `src/context/assembler.py` — Emotional + dual-engine context → YAML
28. `src/prompts/system.py` — System prompt (see Section 6.2 in spec)
29. `src/prompts/extraction.py` — Belief extraction prompt
30. `src/agent.py` — Agent loop (Opus 4.6 + adaptive thinking + tool dispatch)
31. `src/main.py` — CLI entry point

### Phase 6: Tests + Integration
32. Write tests for each module (especially dual-engine gap analysis)
33. Run full test suite: `python -m pytest tests/ -v`
34. Test agent loop with mock conversations

## Pinecone Configuration
- **Index:** `marine-agent-ahgen` (existing, multilingual-e5-large, content fieldMap)
- **Namespace:** `memories`
- **DO NOT** create a new index — reuse this one
- **DO NOT** touch namespaces `agent-memory` or `agent-audit`

## Environment
- `.env` must contain `ANTHROPIC_API_KEY` and `PINECONE_API_KEY`
- Model: `claude-opus-4-6` for agent, `claude-haiku-4-5-20251001` for micro-calls
- Python 3.11+

## Code Style
- Type hints everywhere
- Dataclasses (not Pydantic) for data models — keep dependencies minimal
- f-strings, pathlib over os.path
- No over-engineering — this is a 7-day hackathon build
- Comments only where logic isn't self-evident
- Every file should be independently testable

## Key Design Decisions
- **Dual-engine is the core innovation.** Engine 1 and Engine 2 MUST run as separate tracks.
  The gap between them is a first-class entity, not a derived afterthought.
- **Encoding weight uses BOTH engines:** `flashbulb × max(E1, E2) + gap_bonus`
- **Memory records store both opinions:** `persona_opinion` and `reward_opinion` fields
- **Authority only feeds Engine 1.** Engine 2 is purely observational (valence, approach/avoidance).
- **The gap itself gets encoded strongly** — conflict creates flashbulb-like effects.
- **blend_uncertainty()** from ported fusion.py is used when a merged single opinion is needed.
- **ConflictResult** from ported types.py classifies gap severity.

## What NOT to Do
- Don't add REST API, web UI, or database beyond Pinecone + JSON files
- Don't add multi-user support
- Don't add transformer-based sentiment analysis
- Don't add features not in the spec
- Don't create new Pinecone indexes
- Don't modify `claude-knowledge-base`
