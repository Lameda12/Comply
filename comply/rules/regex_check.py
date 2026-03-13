"""Regex-based rule evaluation — no LLM call, instant."""

import re


def run(rule: dict, diff: str) -> dict:
    """
    Match a regex pattern against the diff.

    Rule fields:
      pattern    - regex to match against diff lines
      on_match   - status when pattern matches (default: FAIL)
      on_no_match - status when pattern does not match (default: PASS)
    """
    pattern = rule.get("pattern")
    if not pattern:
        return {"status": "WARN", "reason": "No pattern defined in regex rule."}

    on_match = rule.get("on_match", "FAIL").upper()
    on_no_match = rule.get("on_no_match", "PASS").upper()

    matches = re.findall(pattern, diff, re.MULTILINE)
    if matches:
        # Show up to 3 matched snippets in the reason
        snippets = [m.strip() if isinstance(m, str) else m[0].strip() for m in matches[:3]]
        preview = " | ".join(snippets)
        return {
            "status": on_match,
            "reason": f"{len(matches)} match(es) found: {preview[:120]}",
        }
    return {
        "status": on_no_match,
        "reason": "No matches found — rule satisfied.",
    }
