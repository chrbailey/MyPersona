"""MyPersona Evaluation Runner.

Entry point for all evaluation. Runs cached datasets by default (no API needed).

Usage:
    python -m eval.run                  # Full eval with cached data
    python -m eval.run --generate       # Regenerate datasets first
    python -m eval.run --component mood # Single component
    python -m eval.run --baseline       # Include baseline comparison
    python -m eval.run --agents         # Agent-based eval (needs API key)
    python -m eval.run --json           # JSON output
"""

import argparse
import json
import sys
import time
from typing import Dict


def main():
    parser = argparse.ArgumentParser(description="MyPersona Evaluation Framework")
    parser.add_argument("--generate", action="store_true",
                        help="Regenerate datasets before running")
    parser.add_argument("--regenerate", action="store_true",
                        help="Force regenerate all datasets")
    parser.add_argument("--component", type=str, default="",
                        help="Run only this component (mood, governance, approach, gap, decay, calibration, introspective)")
    parser.add_argument("--baseline", action="store_true",
                        help="Include baseline comparison")
    parser.add_argument("--agents", action="store_true",
                        help="Run agent-based evaluation (needs ANTHROPIC_API_KEY)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--verbose", action="store_true",
                        help="Verbose output")
    args = parser.parse_args()

    # Generate datasets if needed
    if args.generate or args.regenerate:
        from eval.datasets.generate import generate_all
        print("Generating evaluation datasets...")
        generate_all(regenerate=args.regenerate)
        print()

    # Define available components
    components = {
        "mood": ("eval.harness.mood_eval", "MoodDetector"),
        "governance": ("eval.harness.governance_eval", "GovernanceLayer"),
        "approach": ("eval.harness.approach_eval", "ApproachAvoidance"),
        "gap": ("eval.harness.gap_eval", "GapAnalyzer"),
        "decay": ("eval.harness.decay_eval", "EmotionalDecay"),
        "calibration": ("eval.harness.calibration_eval", "Calibration"),
        "introspective": ("eval.harness.introspective_eval", "IntrospectiveLayer"),
    }

    # Filter to single component if specified
    if args.component:
        if args.component not in components:
            print(f"Unknown component: {args.component}")
            print(f"Available: {', '.join(components.keys())}")
            sys.exit(1)
        components = {args.component: components[args.component]}

    # Run evaluations
    results: Dict[str, dict] = {}
    start = time.time()

    for name, (module_path, display_name) in components.items():
        if not args.json:
            print(f"Running {display_name}...", end=" ", flush=True)
        try:
            import importlib
            mod = importlib.import_module(module_path)
            result = mod.run(verbose=args.verbose)
            results[name] = result
            if not args.json:
                passed = result.get("passed", 0)
                total = result.get("total", 0)
                status = "ALL PASS" if result.get("all_pass") else f"{passed}/{total}"
                print(status)
        except FileNotFoundError as e:
            if not args.json:
                print(f"SKIP (no data: {e})")
        except Exception as e:
            if not args.json:
                print(f"ERROR: {e}")
            results[name] = {"component": display_name, "error": str(e)}

    elapsed = time.time() - start

    # Baselines
    baselines = None
    if args.baseline:
        if not args.json:
            print("\nRunning baselines...", end=" ", flush=True)
        from eval.baselines import run_all_baselines
        baselines = run_all_baselines()
        if not args.json:
            print("done")

    # Agent-based eval
    if args.agents:
        if not args.json:
            print("\nRunning agent-based evaluation...", end=" ", flush=True)
        try:
            from eval.agents.multi_turn_eval import run as run_agents
            agent_results = run_agents(verbose=args.verbose)
            results["agents"] = agent_results
            if not args.json:
                print("done")
        except ImportError:
            if not args.json:
                print("SKIP (agents not yet implemented)")
        except Exception as e:
            if not args.json:
                print(f"ERROR: {e}")

    # Output
    if args.json:
        from eval.report import to_json
        print(to_json(results, baselines))
    else:
        print(f"\nCompleted in {elapsed:.1f}s")
        from eval.report import render_full_report
        render_full_report(results, baselines)


if __name__ == "__main__":
    main()
