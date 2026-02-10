"""MyPersona Evaluation Framework.

Measures whether each component actually predicts what it claims to.
141 unit tests prove the code works. This framework proves (or disproves)
that the predictions work.

Usage:
    python -m eval.run              # Full eval with cached data
    python -m eval.run --generate   # Regenerate datasets (needs API key)
    python -m eval.run --component mood  # Single component
    python -m eval.run --agents     # Agent-based eval (needs API key)
    python -m eval.run --json       # JSON output
"""
