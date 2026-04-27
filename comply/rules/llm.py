"""LLM-based rule evaluation — supports OpenRouter, Anthropic, OpenAI, and Google."""

import json
import os
import re

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

_DEFAULT_MODELS = {
    "openrouter": "qwen/qwen-2.5-72b-instruct",
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
}


def _call_openrouter(system: str, user: str, model: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")
    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_anthropic(system: str, user: str, model: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": model,
            "max_tokens": 256,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _call_openai(system: str, user: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_google(system: str, user: str, model: str) -> str:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set.")
    prompt = f"{system}\n\n{user}"
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


_PROVIDERS = {
    "openrouter": _call_openrouter,
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "google": _call_google,
}


def call_llm(system: str, user: str) -> str:
    """Dispatch to the configured LLM provider and return raw response text."""
    provider = os.environ.get("COMPLY_PROVIDER", "openrouter").lower()
    if provider not in _PROVIDERS:
        raise RuntimeError(
            f"Unknown COMPLY_PROVIDER '{provider}'. "
            f"Choose one of: {', '.join(_PROVIDERS)}"
        )
    default_model = _DEFAULT_MODELS[provider]
    model = os.environ.get("COMPLY_MODEL", default_model)
    return _PROVIDERS[provider](system, user, model)


def run(rule: dict, diff: str) -> dict:
    """Evaluate a rule against a diff using the LLM. Returns {status, reason}."""
    user_prompt = (
        f"Rule: {rule.get('description', rule.get('id', 'no description'))}\n\n"
        f"Instructions:\n{rule.get('prompt', rule.get('message', '')).strip()}\n\n"
        f"Git diff:\n```\n{diff}\n```"
    )
    raw = call_llm(SYSTEM_PROMPT, user_prompt)
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
    try:
        result = json.loads(cleaned)
        return {
            "status": result.get("status", "WARN").upper(),
            "reason": result.get("reason", "No reason provided."),
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "status": "WARN",
            "reason": f"LLM returned invalid JSON — raw: {raw[:200]}",
        }
