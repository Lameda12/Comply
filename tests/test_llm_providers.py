"""Tests for multi-provider LLM dispatch and error handling in checker."""

import os
from unittest.mock import MagicMock, patch

import pytest

from comply.checker import check_all
from comply.rules import llm


DIFF = "+print('hello')\n"

LLM_RULE = {
    "id": "test-llm",
    "type": "llm",
    "description": "Test rule",
    "prompt": "Check it.",
}


def _mock_resp(text: str) -> MagicMock:
    m = MagicMock()
    m.raise_for_status = lambda: None
    m.json.return_value = text
    return m


# ── provider dispatch ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("provider,key,response_body", [
    (
        "openrouter",
        "OPENROUTER_API_KEY",
        {"choices": [{"message": {"content": '{"status":"PASS","reason":"ok"}'}}]},
    ),
    (
        "anthropic",
        "ANTHROPIC_API_KEY",
        {"content": [{"text": '{"status":"PASS","reason":"ok"}'}]},
    ),
    (
        "openai",
        "OPENAI_API_KEY",
        {"choices": [{"message": {"content": '{"status":"PASS","reason":"ok"}'}}]},
    ),
    (
        "google",
        "GOOGLE_API_KEY",
        {"candidates": [{"content": {"parts": [{"text": '{"status":"PASS","reason":"ok"}'}]}}]},
    ),
])
def test_provider_dispatches_correctly(provider, key, response_body, monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", provider)
    monkeypatch.setenv(key, "test-key")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json.return_value = response_body

    with patch("httpx.post", return_value=mock_resp):
        result = llm.run(LLM_RULE, DIFF)

    assert result["status"] == "PASS"
    assert result["reason"] == "ok"


# ── missing API key ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("provider,key", [
    ("openrouter", "OPENROUTER_API_KEY"),
    ("anthropic", "ANTHROPIC_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("google", "GOOGLE_API_KEY"),
])
def test_missing_api_key_raises(provider, key, monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", provider)
    monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match=f"{key} is not set"):
        llm.call_llm("sys", "user")


# ── unknown provider ──────────────────────────────────────────────────────────

def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", "cohere")
    with pytest.raises(RuntimeError, match="Unknown COMPLY_PROVIDER"):
        llm.call_llm("sys", "user")


# ── default models ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("provider,expected_model", [
    ("openrouter", "qwen/qwen-2.5-72b-instruct"),
    ("anthropic", "claude-sonnet-4-6"),
    ("openai", "gpt-4o"),
    ("google", "gemini-2.0-flash"),
])
def test_default_model_per_provider(provider, expected_model, monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", provider)
    monkeypatch.delenv("COMPLY_MODEL", raising=False)
    assert llm._DEFAULT_MODELS[provider] == expected_model


# ── COMPLY_MODEL override ─────────────────────────────────────────────────────

def test_comply_model_overrides_default(monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("COMPLY_MODEL", "claude-opus-4-7")

    captured = {}

    def fake_post(url, **kwargs):
        captured["model"] = kwargs["json"]["model"]
        m = MagicMock()
        m.raise_for_status = lambda: None
        m.json.return_value = {"content": [{"text": '{"status":"PASS","reason":"ok"}'}]}
        return m

    with patch("httpx.post", fake_post):
        llm.call_llm("sys", "user")

    assert captured["model"] == "claude-opus-4-7"


# ── checker catches runner exceptions ─────────────────────────────────────────

def test_checker_wraps_llm_http_error(monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-bad")

    import httpx
    with patch("httpx.post", side_effect=httpx.HTTPStatusError(
        "401", request=MagicMock(), response=MagicMock()
    )):
        results = check_all([LLM_RULE], DIFF)

    assert results[0]["status"] == "WARN"
    assert "Rule runner error" in results[0]["reason"]


def test_checker_wraps_network_error(monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import httpx
    with patch("httpx.post", side_effect=httpx.ConnectError("timeout")):
        results = check_all([LLM_RULE], DIFF)

    assert results[0]["status"] == "WARN"
    assert "Rule runner error" in results[0]["reason"]


# ── markdown fence stripping ──────────────────────────────────────────────────

def test_llm_strips_markdown_fences(monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    fenced = '```json\n{"status":"FAIL","reason":"bad code"}\n```'
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": fenced}}]
    }

    with patch("httpx.post", return_value=mock_resp):
        result = llm.run(LLM_RULE, DIFF)

    assert result["status"] == "FAIL"
    assert result["reason"] == "bad code"


def test_llm_invalid_json_returns_warn(monkeypatch):
    monkeypatch.setenv("COMPLY_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "not json at all"}}]
    }

    with patch("httpx.post", return_value=mock_resp):
        result = llm.run(LLM_RULE, DIFF)

    assert result["status"] == "WARN"
    assert "invalid JSON" in result["reason"]
