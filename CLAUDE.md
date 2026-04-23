# Comply

Comply enforces team conventions by checking PR diffs against plain-English YAML rules, posting pass/fail results back to GitHub as a Check Run.

## Architecture

```
GitHub PR opened/updated
        │
        ▼
  GitHub App webhook
        │  POST /webhook
        ▼
  FastAPI (webhook.py)
        │  verify signature → fetch diff from GitHub API
        ▼
  Rule engine (checker.py)
        │  check_all(rules, diff)
        ▼
  Rule runners
  ├── regex_check.py  — instant pattern match, no LLM
  ├── ast_check.py    — Python AST static analysis
  └── llm.py          — OpenRouter LLM call
        │
        ▼
  Post Check Run to GitHub API
  (conclusion: success / failure)
```

## What works

- `comply check` CLI — reads `.comply.yml`, gets local git diff, prints PASS/WARN/FAIL table
- `comply init` — writes default `.comply.yml` from template
- Rule types: `llm`, `regex`, `ast` with `depends_on` chaining
- MCP server (`comply-mcp`) — exposes `comply_check` tool for Claude Desktop / Cursor
- FastAPI webhook (`comply/webhook.py`) — receives GitHub PR events, runs rules, posts Check Run

## What is broken or missing

- No GitHub App created yet (need App ID, private key, webhook secret) — see DEMO.md
- `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET` env vars required
- Railway deploy not configured (not blocking demo — run locally with ngrok)
- LLM rules require `OPENROUTER_API_KEY`

## Demo needs to show

1. Open a PR with a `console.log` (or `print()`) in the diff
2. Comply webhook fires automatically
3. GitHub PR shows a failing Check Run: "no-console-log — 1 match found"
4. Fix the PR → Comply shows green check

## Key files

| File | Purpose |
|------|---------|
| `comply/webhook.py` | FastAPI app — receives GitHub webhooks, orchestrates checks |
| `comply/checker.py` | Routes rules to runners, handles depends_on |
| `comply/rules/regex_check.py` | Regex rule runner |
| `comply/rules/ast_check.py` | AST rule runner |
| `comply/rules/llm.py` | LLM rule runner via OpenRouter |
| `comply/cli.py` | `comply check` / `comply init` CLI commands |
| `comply/mcp_server.py` | MCP server entrypoint |
| `templates/default.yml` | Default rules written by `comply init` |

## Running locally for demo

```bash
# 1. Install
pip install -e ".[webhook]"

# 2. Set env vars
export GITHUB_APP_ID=12345
export GITHUB_PRIVATE_KEY="$(cat comply-app.pem)"
export GITHUB_WEBHOOK_SECRET=your_secret
export OPENROUTER_API_KEY=sk-or-...

# 3. Start webhook server
uvicorn comply.webhook:app --port 8000

# 4. Expose via ngrok
ngrok http 8000
# copy the https URL → set as webhook URL in GitHub App settings
```
