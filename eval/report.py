"""Rich terminal + JSON reporting for evaluation results."""

import json
from typing import Dict, List, Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def _pass_icon(passed: Optional[bool]) -> str:
    if passed is True:
        return "[green]PASS[/green]"
    elif passed is False:
        return "[red]FAIL[/red]"
    return "[dim]---[/dim]"


def render_component(console, result: dict):
    """Render a single component's evaluation results."""
    component = result.get("component", "Unknown")
    passed = result.get("passed", 0)
    total = result.get("total", 0)
    all_pass = result.get("all_pass", False)

    header_color = "green" if all_pass else "red" if passed < total else "yellow"
    console.print(f"\n  [{header_color} bold]{component}[/{header_color} bold]"
                  f"  {passed}/{total} metrics passed"
                  f"  ({result.get('total_samples', result.get('total_conversations', '?'))} samples)")

    table = Table(show_header=True, header_style="bold", width=72, padding=(0, 1))
    table.add_column("Metric", width=28)
    table.add_column("Value", justify="right", width=10)
    table.add_column("Target", justify="right", width=10)
    table.add_column("Result", justify="center", width=8)

    for name, data in result.get("metrics", {}).items():
        value = data.get("value", 0)
        target = data.get("target")
        passed_flag = data.get("pass")
        target_str = f"{target}" if target is not None else "---"
        table.add_row(name, f"{value:.4f}", target_str, _pass_icon(passed_flag))

    console.print(table)

    # Per-difficulty breakdown for mood
    if "by_difficulty" in result:
        diff_table = Table(title="By Difficulty", show_header=True, width=72, padding=(0, 1))
        diff_table.add_column("Difficulty", width=14)
        diff_table.add_column("Count", justify="right", width=8)
        diff_table.add_column("Accuracy", justify="right", width=10)
        diff_table.add_column("Val MAE", justify="right", width=10)
        diff_table.add_column("Aro MAE", justify="right", width=10)
        for diff, data in result["by_difficulty"].items():
            acc = data.get("quadrant_accuracy", 0)
            acc_color = "green" if acc >= 0.65 else "yellow" if acc >= 0.4 else "red"
            diff_table.add_row(
                diff, str(data["count"]),
                f"[{acc_color}]{acc:.3f}[/{acc_color}]",
                f"{data.get('valence_mae', 0):.3f}",
                f"{data.get('arousal_mae', 0):.3f}",
            )
        console.print(diff_table)

    # Governance failures
    if "failures" in result and result["failures"]:
        console.print(f"  [red]Failures ({len(result['failures'])}):[/red]")
        for f in result["failures"][:5]:
            console.print(f"    expected={f['expected']} got={f['got']} "
                         f"ew={f['encoding_weight']} cs={f['conflict_score']}")


def render_baselines(console, baselines: dict):
    """Render baseline comparison."""
    console.print("\n  [bold]Baselines (naive)[/bold]")
    table = Table(show_header=True, width=72, padding=(0, 1))
    table.add_column("Baseline", width=24)
    table.add_column("Metric", width=20)
    table.add_column("Value", justify="right", width=10)

    for name, data in baselines.items():
        desc = data.get("description", name)
        for key, value in data.items():
            if key in ("name", "description", "majority_label"):
                continue
            table.add_row(desc, key, f"{value:.4f}" if isinstance(value, float) else str(value))
            desc = ""  # only show description on first row

    console.print(table)


def render_full_report(results: Dict[str, dict], baselines: Optional[dict] = None):
    """Render the full evaluation report to terminal."""
    if not HAS_RICH:
        print(json.dumps(results, indent=2, default=str))
        return

    console = Console(width=80)

    # Banner
    total_pass = sum(r.get("passed", 0) for r in results.values())
    total_metrics = sum(r.get("total", 0) for r in results.values())
    all_pass = all(r.get("all_pass", False) for r in results.values())
    banner_color = "green" if all_pass else "red"

    console.print(Panel(
        f"[bold]MyPersona Evaluation Report[/bold]\n\n"
        f"[{banner_color}]{total_pass}/{total_metrics} metrics passed[/{banner_color}]",
        width=76,
    ))

    # Component results
    for name, result in results.items():
        render_component(console, result)

    # Baselines
    if baselines:
        render_baselines(console, baselines)

    # Summary table
    console.print()
    summary_table = Table(title="Summary", show_header=True, width=72, padding=(0, 1))
    summary_table.add_column("Component", width=28)
    summary_table.add_column("Passed", justify="center", width=12)
    summary_table.add_column("Status", justify="center", width=12)

    for name, result in results.items():
        p = result.get("passed", 0)
        t = result.get("total", 0)
        status = "[green]ALL PASS[/green]" if result.get("all_pass") else f"[red]{p}/{t}[/red]"
        summary_table.add_row(result.get("component", name), f"{p}/{t}", status)

    console.print(summary_table)


def to_json(results: Dict[str, dict], baselines: Optional[dict] = None) -> str:
    """Export results as JSON string."""
    output = {"results": results}
    if baselines:
        output["baselines"] = baselines
    return json.dumps(output, indent=2, default=str)
