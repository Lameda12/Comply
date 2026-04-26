# Comply

Comply enforces your team's plain-English rules on every PR, automatically.

---

## How it works

1. Write rules in `.comply.yml` describing what you want to enforce
2. Open a PR — Comply's GitHub App webhook fires on every push
3. Comply flags violations inline as a Check Run on the PR

---

## Install

```bash
pipx install comply-cli
comply init
```

`comply init` writes a starter `.comply.yml` and connects the GitHub App.

---

## Usage

```bash
# check current diff against rules
comply check --file src/api.ts

# list configured rules
comply rules list

# start the MCP server
comply-mcp
```

---

## Example `.comply.yml`

```yaml
rules:
  - id: no-console-log
    type: regex
    description: No console.log in production code
    pattern: '^\+.*\bconsole\.log\s*\('
    on_match: FAIL
    on_no_match: PASS

  - id: tests-required
    type: llm
    description: Every new source file needs a corresponding test file
    prompt: |
      Look at the diff. If any new source files are added outside of
      test directories, check whether a corresponding test file also
      appears in the diff. Return PASS if all new files have tests,
      FAIL if any are missing.

  - id: no-bare-except
    type: ast
    description: No bare except clauses in Python files
    check: no-bare-except
```

Rule types: `regex` (local pattern match), `llm` (OpenRouter LLM), `ast` (Python static analysis). Chain rules with `depends_on`.

---

## GitHub App

The GitHub App posts Check Runs directly to your PRs. When a PR is opened or updated, Comply fetches the diff, runs all rules, and posts a pass/fail result with per-rule details. Run `comply init` in your repo — it walks through connecting the app and writing the webhook URL to your GitHub App settings.

Requires `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, and `GITHUB_WEBHOOK_SECRET` env vars. LLM rules additionally require `OPENROUTER_API_KEY`.

---

## MCP server

`comply-mcp` exposes a `comply_check` tool for Claude Desktop and Cursor. After running `comply-mcp`, add the server path to your MCP config. Claude can then call `comply_check(repo_path=".", config_path=".comply.yml")` directly from a conversation and return structured pass/fail results.

Find the binary path with `which comply-mcp`.

---

## Contributing

Open an issue or PR at [github.com/Lameda12/Comply](https://github.com/Lameda12/Comply).

---

## License

MIT
