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

Rules live in `.comply.yml`. Each rule has three fields:

```yaml
rules:
  - id: tests-required
    description: Every new Python file needs a test file
    prompt: |
      Look at the diff. If any new .py source files are added
      (not in tests/ or test_*.py), check whether a corresponding
      test file also appears in the diff.
      Return PASS if all new files have tests, WARN if some are missing.
```

| Field | What it does |
|---|---|
| `id` | Short name shown in the output |
| `description` | Human-readable summary |
| `prompt` | Plain-English instruction sent to the LLM |

The LLM must return `PASS`, `WARN`, or `FAIL` with a reason. If it returns garbage, Comply falls back to `WARN` and shows the raw response.

---

## Starter rules (from `comply init`)

| Rule | What it checks |
|---|---|
| `tests-required` | New source files have matching test files |
| `auth-security-review` | Changes to auth/login paths get flagged |
| `migration-docs` | New DB migrations include a rollback/downgrade |
| `env-vars-documented` | New env vars appear in `.env.example` |

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
- [ ] Phase 3 — Rule types: regex, AST, LLM chaining

---

## License

MIT
