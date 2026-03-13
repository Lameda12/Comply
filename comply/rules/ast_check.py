"""AST-based rule evaluation — static analysis of changed Python files."""

import ast
import re
from pathlib import Path


def _changed_py_files(diff: str) -> list[str]:
    """Extract paths of added/modified .py files from a diff."""
    return re.findall(r"^diff --git a/.+ b/(.+\.py)$", diff, re.MULTILINE)


def _check_docstrings(tree: ast.Module, path: str) -> list[str]:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                issues.append(f"{path}:{node.lineno} `{node.name}` missing docstring")
    return issues


def _check_type_hints(tree: ast.Module, path: str) -> list[str]:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            missing = [a.arg for a in node.args.args if a.annotation is None
                       and a.arg != "self"]
            if missing:
                issues.append(f"{path}:{node.lineno} `{node.name}` missing hints on: {', '.join(missing)}")
            if node.returns is None:
                issues.append(f"{path}:{node.lineno} `{node.name}` missing return type hint")
    return issues


def _check_no_bare_except(tree: ast.Module, path: str) -> list[str]:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(f"{path}:{node.lineno} bare `except:` — catch a specific exception")
    return issues


def _check_no_globals(tree: ast.Module, path: str) -> list[str]:
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            issues.append(f"{path}:{node.lineno} `global {', '.join(node.names)}` — avoid mutable globals")
    return issues


CHECKS = {
    "docstrings": _check_docstrings,
    "type-hints": _check_type_hints,
    "no-bare-except": _check_no_bare_except,
    "no-globals": _check_no_globals,
}


def run(rule: dict, diff: str) -> dict:
    """
    Parse changed Python files with ast and run a named check.

    Rule fields:
      check - one of: docstrings | type-hints | no-bare-except | no-globals
    """
    check_name = rule.get("check")
    if check_name not in CHECKS:
        return {
            "status": "WARN",
            "reason": f"Unknown ast check '{check_name}'. Valid: {', '.join(CHECKS)}",
        }

    checker_fn = CHECKS[check_name]
    py_files = _changed_py_files(diff)
    if not py_files:
        return {"status": "PASS", "reason": "No Python files changed."}

    all_issues = []
    parse_errors = []
    for path in py_files:
        if not Path(path).exists():
            continue
        try:
            tree = ast.parse(Path(path).read_text(), filename=path)
            all_issues.extend(checker_fn(tree, path))
        except SyntaxError as e:
            parse_errors.append(f"{path}: {e}")

    if parse_errors:
        return {"status": "WARN", "reason": f"Parse error(s): {'; '.join(parse_errors[:2])}"}

    if all_issues:
        summary = all_issues[0]
        extra = f" (+{len(all_issues) - 1} more)" if len(all_issues) > 1 else ""
        return {"status": "FAIL", "reason": summary + extra}

    return {"status": "PASS", "reason": f"All {len(py_files)} file(s) passed `{check_name}` check."}
