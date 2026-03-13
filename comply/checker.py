"""Rule orchestrator — routes by type, handles depends_on chaining."""

from comply.rules import llm, regex_check, ast_check

RUNNERS = {
    "llm": llm.run,
    "regex": regex_check.run,
    "ast": ast_check.run,
}


def check_rule(rule: dict, diff: str) -> dict:
    """Evaluate a single rule. Returns {id, status, reason}."""
    rule_type = rule.get("type", "llm")
    runner = RUNNERS.get(rule_type)
    if not runner:
        return {
            "id": rule["id"],
            "status": "WARN",
            "reason": f"Unknown rule type '{rule_type}'. Valid: {', '.join(RUNNERS)}",
        }
    result = runner(rule, diff)
    return {"id": rule["id"], **result}


def check_all(rules: list[dict], diff: str) -> list[dict]:
    """
    Run all rules in order, respecting depends_on.

    If a rule has depends_on: <id> and that rule returned PASS,
    the dependent rule is skipped (SKIP status).
    """
    results_by_id: dict[str, dict] = {}

    for rule in rules:
        dep_id = rule.get("depends_on")
        if dep_id:
            dep = results_by_id.get(dep_id)
            if dep is None:
                result = {
                    "id": rule["id"],
                    "status": "WARN",
                    "reason": f"depends_on '{dep_id}' not found or not yet evaluated.",
                }
            elif dep["status"] == "PASS":
                result = {
                    "id": rule["id"],
                    "status": "SKIP",
                    "reason": f"Skipped — '{dep_id}' passed (nothing to check).",
                }
            else:
                result = check_rule(rule, diff)
        else:
            result = check_rule(rule, diff)

        results_by_id[rule["id"]] = result

    return list(results_by_id.values())
