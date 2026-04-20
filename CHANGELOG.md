# Changelog

All notable changes to MyPersona are documented here.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses semantic versioning from v0.2.0 onward.

## [Unreleased]

### Changed
- README now lists the 12 actual MCP tool names verified against `src/server.py`
  (previous README referenced `ps_*` prefixed names that never existed in the
  code). Added "What this is NOT" and "Known Limitations" sections.
- Added this CHANGELOG.

## [0.2.0] — 2026-02-10

### Added
- Evaluation framework under `eval/` with scripted scenarios and scoring harness.
- Emoji and calm-mood patterns in `MoodDetector`.
- Demo GIF embedded in README.

### Fixed
- `MoodDetector` edge cases: negation handling, sarcasm detection, quote stripping,
  additional signal patterns.
- Recalibrated confidence formula for improved accuracy.
- Agent evaluation JSON parsing.

## [0.1.0] — 2026-02-09 (initial public release)

### Added
- Dual-engine architecture: Persona (Should-Self) + Reward (Want-Self).
- Gap Layer / theatre score based on Self-Discrepancy Theory (Higgins 1987).
- Mood Detector — circumplex model (valence × arousal → 4 quadrants).
- Emotional decay following an Ebbinghaus curve, modulated by encoding weight
  (FadeMem 2025).
- Belief system with subjective logic triples (belief / disbelief / uncertainty).
- Governance layer — intense memories held for human approval before storage.
- MCP server (stdio) exposing 12 tools.
- 141 tests across 13 files (~0.4 s).
- Five scripted demo scenarios runnable without API keys.

### Notes
- Agent loop targets Claude Opus 4.6 with extended thinking.
- Persistent memory uses Pinecone; everything else is in-process or SQLite.
