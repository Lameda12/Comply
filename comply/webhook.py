"""FastAPI webhook — receives GitHub PR events, runs Comply rules, posts Check Run."""

import hashlib
import hmac
import logging
import os
import time
from pathlib import Path

import httpx
import jwt
import yaml
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from comply.checker import check_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("comply.webhook")

app = FastAPI(title="Comply Webhook")

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
APP_ID = os.environ.get("GITHUB_APP_ID", "")
PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY", "")
RULES_FILE = os.environ.get("COMPLY_RULES_FILE", ".comply.yml")


# ── GitHub auth ──────────────────────────────────────────────────────────────

def _make_jwt() -> str:
    """Create a signed JWT for GitHub App authentication (valid 60s)."""
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 60, "iss": APP_ID}
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


def _installation_token(installation_id: int) -> str:
    """Exchange a GitHub App JWT for an installation access token."""
    app_jwt = _make_jwt()
    resp = httpx.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["token"]


# ── GitHub API helpers ───────────────────────────────────────────────────────

def _fetch_diff(owner: str, repo: str, pull_number: int, token: str) -> str:
    """Fetch the unified diff for a pull request."""
    resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3.diff",
        },
        timeout=30,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text


def _post_check_run(
    owner: str,
    repo: str,
    head_sha: str,
    results: list[dict],
    token: str,
) -> None:
    """Post a Check Run to GitHub with PASS/FAIL conclusion."""
    failures = [r for r in results if r["status"] == "FAIL"]
    warnings = [r for r in results if r["status"] == "WARN"]

    if failures:
        conclusion = "failure"
        title = f"{len(failures)} rule(s) failed"
    elif warnings:
        conclusion = "neutral"
        title = f"{len(warnings)} warning(s)"
    else:
        conclusion = "success"
        title = "All rules passed"

    lines = []
    for r in results:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭"}.get(r["status"], "?")
        lines.append(f"{icon} **{r['id']}** — {r['reason']}")

    summary = "\n".join(lines) or "No rules evaluated."

    payload = {
        "name": "Comply",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": title,
            "summary": summary,
        },
    }

    resp = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/check-runs",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    log.info(
        "check_run_posted repo=%s/%s sha=%.8s conclusion=%s",
        owner, repo, head_sha, conclusion,
    )


def _find_pr_by_sha(owner: str, repo: str, head_sha: str, token: str) -> dict | None:
    """Return the first open PR whose head SHA matches, or None."""
    resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        params={"state": "open", "per_page": 100},
        timeout=15,
    )
    resp.raise_for_status()
    for pr in resp.json():
        if pr["head"]["sha"] == head_sha:
            return pr
    return None


def _load_rules_from_repo(owner: str, repo: str, token: str) -> list[dict]:
    """Fetch .comply.yml from the default branch and parse rules."""
    resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{RULES_FILE}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.raw+json",
        },
        timeout=15,
    )
    if resp.status_code == 404:
        log.warning("rules_file_not_found repo=%s/%s file=%s", owner, repo, RULES_FILE)
        return []
    resp.raise_for_status()
    cfg = yaml.safe_load(resp.text)
    rules = cfg.get("rules", [])
    log.info("rules_loaded repo=%s/%s count=%d", owner, repo, len(rules))
    for r in rules:
        log.info("  rule id=%s type=%s", r.get("id"), r.get("type", "llm"))
    return rules


# ── Webhook signature verification ──────────────────────────────────────────

def _verify_signature(body: bytes, signature: str) -> None:
    """Raise 401 if the HMAC-SHA256 signature does not match."""
    if not WEBHOOK_SECRET:
        log.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature check")
        return
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


# ── Webhook endpoint ─────────────────────────────────────────────────────────

@app.post("/webhook")
async def webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> JSONResponse:
    """Receive GitHub webhook events and run Comply checks on pull requests."""
    body = await request.body()

    log.info(
        "webhook_received event=%s size=%d bytes",
        x_github_event, len(body),
    )

    _verify_signature(body, x_hub_signature_256)

    if x_github_event not in ("pull_request", "check_suite"):
        log.info("webhook_ignored event=%s", x_github_event)
        return JSONResponse({"status": "ignored", "event": x_github_event})

    payload = await request.json()
    action = payload.get("action", "")

    if x_github_event == "pull_request":
        if action not in ("opened", "synchronize", "reopened"):
            log.info("webhook_ignored action=%s", action)
            return JSONResponse({"status": "ignored", "action": action})

        pr = payload["pull_request"]
        repo_info = payload["repository"]
        owner = repo_info["owner"]["login"]
        repo = repo_info["name"]
        pull_number = pr["number"]
        head_sha = pr["head"]["sha"]
        installation_id = payload["installation"]["id"]

    elif x_github_event == "check_suite":
        if action != "requested":
            log.info("webhook_ignored check_suite action=%s", action)
            return JSONResponse({"status": "ignored", "action": action})

        suite = payload["check_suite"]
        repo_info = payload["repository"]
        owner = repo_info["owner"]["login"]
        repo = repo_info["name"]
        head_sha = suite["head_sha"]
        installation_id = payload["installation"]["id"]

        log.info(
            "check_suite_requested repo=%s/%s sha=%.8s",
            owner, repo, head_sha,
        )

        token = _installation_token(installation_id)
        pr = _find_pr_by_sha(owner, repo, head_sha, token)
        if pr is None:
            log.info("check_suite_no_pr_found sha=%.8s", head_sha)
            return JSONResponse({"status": "skipped", "reason": "no open PR for this SHA"})

        pull_number = pr["number"]

    log.info(
        "webhook_processing repo=%s/%s pr=#%d sha=%.8s",
        owner, repo, pull_number, head_sha,
    )

    if x_github_event == "pull_request":
        token = _installation_token(installation_id)

    rules = _load_rules_from_repo(owner, repo, token)

    if not rules:
        return JSONResponse({"status": "skipped", "reason": "no rules file"})

    diff = _fetch_diff(owner, repo, pull_number, token)
    log.info(
        "diff_fetched repo=%s/%s pr=#%d diff_bytes=%d",
        owner, repo, pull_number, len(diff),
    )

    results = check_all(rules, diff)

    for r in results:
        log.info(
            "rule_result id=%s status=%s reason=%.80s",
            r["id"], r["status"], r["reason"],
        )

    _post_check_run(owner, repo, head_sha, results, token)

    failures = sum(1 for r in results if r["status"] == "FAIL")
    warnings = sum(1 for r in results if r["status"] == "WARN")
    return JSONResponse({
        "status": "ok",
        "repo": f"{owner}/{repo}",
        "pr": pull_number,
        "failures": failures,
        "warnings": warnings,
    })


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})
