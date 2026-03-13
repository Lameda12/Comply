"""Comply MCP server — exposes comply_check as an MCP tool."""

import subprocess
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

from comply.checker import check_all

mcp = FastMCP("comply")


def _get_diff(repo_path: str) -> str:
    kwargs = dict(capture_output=True, text=True, cwd=repo_path)
    staged = subprocess.run(["git", "diff", "--cached"], **kwargs)
    if staged.stdout.strip():
        return staged.stdout
    last = subprocess.run(["git", "diff", "HEAD~1", "HEAD"], **kwargs)
    if last.stdout.strip():
        return last.stdout
    unstaged = subprocess.run(["git", "diff"], **kwargs)
    return unstaged.stdout


def _load_rules(config_path: str) -> list[dict]:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("rules", [])


@mcp.tool()
def comply_check(
    repo_path: str = ".",
    config_path: str = ".comply.yml",
) -> dict:
    """
    Check the current git diff in a repository against rules in .comply.yml.

    Returns a structured report with PASS / WARN / FAIL per rule.

    Args:
        repo_path: Absolute or relative path to the git repository. Defaults to current directory.
        config_path: Path to the .comply.yml rules file. Defaults to .comply.yml in repo_path.
    """
    repo = Path(repo_path).resolve()
    config = Path(config_path) if Path(config_path).is_absolute() else repo / config_path

    if not config.exists():
        return {
            "error": f"No rules file found at {config}. Run 'comply init' first.",
            "results": [],
        }

    rules = _load_rules(str(config))
    if not rules:
        return {"error": "No rules defined in .comply.yml", "results": []}

    diff = _get_diff(str(repo))
    if not diff.strip():
        return {"error": None, "results": [], "summary": "No diff found — nothing to check."}

    results = check_all(rules, diff)

    failures = sum(1 for r in results if r["status"] == "FAIL")
    warnings = sum(1 for r in results if r["status"] == "WARN")
    passed = sum(1 for r in results if r["status"] == "PASS")

    return {
        "error": None,
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "warnings": warnings,
            "failures": failures,
            "verdict": "FAIL" if failures else ("WARN" if warnings else "PASS"),
        },
    }


def serve():
    mcp.run()
