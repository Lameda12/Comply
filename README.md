# Comply

**Enforce your team's conventions — automatically, before every merge.**

Comply reads a simple rules file, looks at your git diff, and asks an LLM to check each rule. You get a clear PASS / WARN / FAIL report in your terminal.

```
$ comply check

Comply — checking 4 rules against current diff

  ✅ PASS   tests-required        No new source files missing tests
  ⚠️  WARN   auth-security-review  auth/login.py modified — needs security review
  ❌ FAIL   migration-docs        migrations/0012.py has no rollback plan
  ⚠️  WARN   env-vars-documented   JWT_SECRET not in .env.example

1 failure, 2 warnings. Fix before merging.
```

---

## How it works

```
your git diff
     │
     ▼
.comply.yml  ──►  LLM (OpenRouter)  ──►  PASS / WARN / FAIL per rule
```

1. You write rules in plain English inside `.comply.yml`
2. `comply check` gets the current staged diff (or last commit)
3. Each rule is sent to an LLM alongside the diff
4. Results are printed as a formatted checklist

---

## Install

**Requires Python 3.10+**

```bash
git clone https://github.com/Lameda12/Comply.git
cd Comply
pip install -e .
```

Verify it works:

```bash
comply --help
```

---

## Quick start

### 1. Get an API key

Sign up at [openrouter.ai](https://openrouter.ai) → go to **Keys** → create one.

```bash
export OPENROUTER_API_KEY=sk-or-your-key-here
```

> Add this to your `~/.zshrc` or `~/.bashrc` so you don't have to set it every time.

### 2. Go to your project

```bash
cd /path/to/your/project
git init   # if not already a git repo
```

### 3. Create your rules file

```bash
comply init
```

This writes a `.comply.yml` with 4 starter rules. Open it and edit to match your team's conventions.

### 4. Make some changes and check them

```bash
# edit some files...
git add .
comply check
```

That's it.

---

## Writing rules

Rules live in `.comply.yml`. There are three rule types:

### `llm` — plain-English instructions (default)

```yaml
rules:
  - id: tests-required
    type: llm
    description: Every new Python file needs a test file
    prompt: |
      Look at the diff. If any new .py source files are added
      (not in tests/ or test_*.py), check whether a corresponding
      test file also appears in the diff.
      Return PASS if all new files have tests, WARN if some are missing.
```

| Field | What it does |
|---|---|
| `id` | Short name shown in output |
| `description` | Human-readable summary |
| `prompt` | Plain-English instruction sent to the LLM |

---

### `regex` — instant pattern matching, no LLM call

```yaml
  - id: no-print-statements
    type: regex
    description: No print() calls in production code
    pattern: '^\+.*\bprint\s*\('
    on_match: WARN       # status when pattern is found  (default: FAIL)
    on_no_match: PASS    # status when not found         (default: PASS)
```

Fast and free — runs entirely locally against the raw diff text.

---

### `ast` — Python static analysis, no LLM call

```yaml
  - id: no-bare-except
    type: ast
    description: No bare except clauses
    check: no-bare-except
```

Parses changed Python files with Python's built-in `ast` module.

| `check` value | What it enforces |
|---|---|
| `docstrings` | All new functions/classes have docstrings |
| `type-hints` | All new functions have type annotations |
| `no-bare-except` | No bare `except:` — must catch a specific exception |
| `no-globals` | No `global` statements |

---

### `depends_on` — rule chaining

```yaml
  - id: migration-exists
    type: llm
    prompt: "Return WARN if any migration files are added, else PASS."
    ...

  - id: migration-rollback
    type: llm
    depends_on: migration-exists   # ← only runs if migration-exists returned WARN/FAIL
    prompt: "Check that migrations have a downgrade() function."
    ...
```

If the dependency returned `PASS`, the dependent rule shows `SKIP` in output. This avoids false positives when there's nothing to check.

---

## Starter rules (from `comply init`)

| Rule | Type | What it checks |
|---|---|---|
| `tests-required` | llm | New source files have matching test files |
| `migration-exists` | llm | Detects new migration files |
| `migration-rollback` | llm | Checks rollback — skipped if no migrations found |
| `env-vars-documented` | llm | New env vars appear in `.env.example` |
| `no-print-statements` | regex | No `print()` calls in production code |
| `no-hardcoded-secrets` | regex | No hardcoded passwords/tokens |
| `no-todo-in-new-code` | regex | No new TODO/FIXME comments |
| `functions-need-docstrings` | ast | All new functions/classes have docstrings |
| `no-bare-except` | ast | No bare `except:` handlers |

---

## Options

```bash
# Use a different config file
comply check --config path/to/rules.yml

# Use a different LLM model
export COMPLY_MODEL=openai/gpt-4o
comply check
```

Default model: `qwen/qwen-2.5-72b-instruct` — fast and cheap.
Any model on [openrouter.ai/models](https://openrouter.ai/models) works.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All rules passed |
| `1` | One or more FAIL or WARN |

This makes it easy to use in CI:

```yaml
# .github/workflows/comply.yml
- name: Run Comply
  run: comply check
  env:
    OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

---

## Project structure

```
comply/
├── comply/
│   ├── cli.py        # comply init + comply check commands
│   └── checker.py    # LLM call + rule evaluation (< 100 lines)
├── templates/
│   └── default.yml   # starter rules written by comply init
└── pyproject.toml
```

---

---

## MCP Server (Phase 2)

Comply ships a built-in MCP server so Claude Desktop or Cursor can call `comply_check` directly during a conversation — no terminal needed.

### What the tool does

```
comply_check(repo_path=".", config_path=".comply.yml")
```

Returns structured JSON:

```json
{
  "results": [
    { "id": "tests-required",       "status": "WARN", "reason": "..." },
    { "id": "auth-security-review", "status": "PASS", "reason": "..." }
  ],
  "summary": {
    "total": 4, "passed": 3, "warnings": 1, "failures": 0,
    "verdict": "WARN"
  }
}
```

### Connect to Claude Desktop

1. Find your config file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add this block (replace the path with your actual `comply-mcp` location):

```json
{
  "mcpServers": {
    "comply": {
      "command": "/Library/Frameworks/Python.framework/Versions/3.13/bin/comply-mcp",
      "env": {
        "OPENROUTER_API_KEY": "sk-or-your-key-here"
      }
    }
  }
}
```

> Find your `comply-mcp` path with: `which comply-mcp`

3. Restart Claude Desktop. You'll see **comply** in the tools list.

4. In any conversation, ask Claude:
   > *"Check my repo at /path/to/project for convention violations"*

   Claude will call `comply_check` and show you the results inline.

### Connect to Cursor

Add to your `.cursor/mcp.json` or Cursor MCP settings:

```json
{
  "comply": {
    "command": "/Library/Frameworks/Python.framework/Versions/3.13/bin/comply-mcp",
    "env": {
      "OPENROUTER_API_KEY": "sk-or-your-key-here"
    }
  }
}
```

---

## Roadmap

- [x] Phase 1 — Core CLI (`comply init`, `comply check`)
- [x] Phase 2 — MCP server (`comply-mcp`, works in Claude Desktop + Cursor)
- [x] Phase 3 — Rule types: `llm`, `regex`, `ast` + `depends_on` chaining

---

## License

MIT
