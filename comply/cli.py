"""Comply CLI — enforce team conventions via LLM."""

import shutil
import subprocess
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich import box

from comply.checker import check_all

app = typer.Typer(help="Comply — enforce team conventions via LLM.", add_completion=False)
console = Console()

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "default.yml"
CONFIG_FILE = ".comply.yml"

STATUS_ICONS = {
    "PASS": "[green]✅ PASS[/green]",
    "WARN": "[yellow]⚠️  WARN[/yellow]",
    "FAIL": "[red]❌ FAIL[/red]",
    "SKIP": "[dim]⏭  SKIP[/dim]",
}


def get_diff() -> str:
    """Return staged diff, or last commit diff if nothing is staged."""
    staged = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True, text=True
    )
    if staged.stdout.strip():
        return staged.stdout

    last = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD"],
        capture_output=True, text=True
    )
    if last.stdout.strip():
        return last.stdout

    # Fallback: diff of all tracked changes vs HEAD
    unstaged = subprocess.run(
        ["git", "diff"],
        capture_output=True, text=True
    )
    return unstaged.stdout


@app.command()
def init():
    """Write a default .comply.yml to the current directory."""
    target = Path(CONFIG_FILE)
    if target.exists():
        console.print(f"[yellow]{CONFIG_FILE} already exists.[/yellow] Use --force to overwrite.")
        raise typer.Exit(1)

    if TEMPLATE_PATH.exists():
        shutil.copy(TEMPLATE_PATH, target)
    else:
        console.print(f"[red]Template not found at {TEMPLATE_PATH}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Created {CONFIG_FILE}[/green] — edit rules to match your team conventions.")


@app.command()
def check(
    config: Path = typer.Option(Path(CONFIG_FILE), "--config", "-c", help="Path to .comply.yml"),
):
    """Check the current git diff against rules in .comply.yml."""
    if not config.exists():
        console.print(
            f"[red]No {CONFIG_FILE} found.[/red] Run [bold]comply init[/bold] first."
        )
        raise typer.Exit(1)

    with open(config) as f:
        cfg = yaml.safe_load(f)

    rules = cfg.get("rules", [])
    if not rules:
        console.print("[yellow]No rules defined in .comply.yml[/yellow]")
        raise typer.Exit(0)

    diff = get_diff()
    if not diff.strip():
        console.print("[yellow]No diff found — nothing to check.[/yellow]")
        raise typer.Exit(0)

    console.print(f"\n[bold]Comply[/bold] — checking [bold]{len(rules)}[/bold] rules against current diff\n")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Status", min_width=14)
    table.add_column("Rule ID", style="bold cyan", min_width=28)
    table.add_column("Reason")

    results = []
    try:
        with console.status("[dim]Running checks...[/dim]"):
            results = check_all(rules, diff)
        for result in results:
            icon = STATUS_ICONS.get(result["status"], result["status"])
            table.add_row(icon, result["id"], result["reason"])
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)

    console.print(table)

    failures = sum(1 for r in results if r["status"] == "FAIL")
    warnings = sum(1 for r in results if r["status"] == "WARN")

    parts = []
    if failures:
        parts.append(f"[red]{failures} failure{'s' if failures > 1 else ''}[/red]")
    if warnings:
        parts.append(f"[yellow]{warnings} warning{'s' if warnings > 1 else ''}[/yellow]")

    if parts:
        console.print(", ".join(parts) + ". Fix before merging.\n")
        raise typer.Exit(1)
    else:
        console.print("[green]All checks passed.[/green]\n")
