# Contributing

Thanks for looking.

## Before opening a PR

1. **Open an issue first** for anything larger than a typo.
2. **All changes need tests.** MyPersona has 141 tests — add yours alongside the existing suite.
3. **Match the existing code style.** Python 3.11, type hints, dataclasses where appropriate.
4. **Run the full test suite locally** before submitting: `pytest`.

## What this project will not accept

MyPersona models emotional memory with a specific dual-engine architecture grounded in Self-Discrepancy Theory (Higgins, 1987). PRs that drift from the core model will be declined.

- PRs that collapse the Engine 1 (Persona / Should-Self) and Engine 2 (Reward / Want-Self) split into a single engine. The gap between them IS the signal — flattening destroys the product.
- PRs that bypass the governance hold queue (`ps_hold_list`, `ps_hold_approve`, `ps_hold_reject`) so that emotionally intense memories get stored without human approval. Human-in-the-loop on high-intensity memories is a design invariant.
- PRs that remove or weaken the memory decay model so that mundane and intense memories persist equally.
- PRs that add a silent network call from any MCP tool. This server is local-first — any outbound request needs to be explicit, documented, and opt-in.
- PRs that store raw user messages as training data without an explicit user-facing opt-in.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not file security issues in the public tracker.

## Author

[Christopher Bailey](https://github.com/chrbailey).
