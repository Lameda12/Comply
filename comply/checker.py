"""LLM-based rule checker for comply."""

import json
import os
import httpx

SYSTEM_PROMPT = """\
You are a code review assistant enforcing team conventions.
You will be given a git diff and a single rule to evaluate.

Respond ONLY with valid JSON in this exact format:
{
  "status": "PASS" | "WARN" | "FAIL",
  "reason": "<one concise sentence>"
}

Do not include any explanation outside the JSON object.
"""


def call_llm(system: str, user: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Export it with: export OPENROUTER_API_KEY=your_key_here"
        )
    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": os.environ.get("COMPLY_MODEL", "qwen/qwen-2.5-72b-instruct"),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def check_rule(rule: dict, diff: str) -> dict:
    """Run a single rule against a diff. Returns {id, status, reason}."""
    user_prompt = (
        f"Rule: {rule['description']}\n\n"
        f"Instructions:\n{rule['prompt'].strip()}\n\n"
        f"Git diff:\n```\n{diff}\n```"
    )
    raw = call_llm(SYSTEM_PROMPT, user_prompt)
    try:
        result = json.loads(raw)
        status = result.get("status", "WARN").upper()
        reason = result.get("reason", "No reason provided.")
    except (json.JSONDecodeError, KeyError):
        status = "WARN"
        reason = f"LLM returned invalid JSON — raw response: {raw[:200]}"
    return {"id": rule["id"], "status": status, "reason": reason}
