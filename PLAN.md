# Comply — Project Plan

## Phases

### Phase 1 — Core CLI (TODAY: 2026-03-13) ✅ TARGET
- `comply init` — writes `.comply.yml` to current directory from template
- `comply check` — reads `.comply.yml`, gets git diff, calls LLM, prints results
- Output: colored PASS / WARN / FAIL checklist via Rich
- No MCP, no web UI, no database

### Phase 2 — MCP Server (not started)
- Expose `comply_check` as an MCP tool
- Allow Claude/Cursor to call it mid-session
- Return structured JSON results

### Phase 3 — Advanced Rules (not started)
- Rule types: regex, ast, llm
- Rule chaining / dependencies
- Custom prompts per rule

---

## Today's Target
Complete Phase 1: working `comply check` against a real diff.

## Checkpoint — Phase 1 complete (2026-03-13)

- `comply init` writes `.comply.yml` from `templates/default.yml`
- `comply check` reads config → gets staged/last-commit diff → calls OpenRouter LLM per rule → prints Rich table
- `checker.py` is 59 lines (under 100 limit)
- JSON parse errors handled gracefully (falls back to WARN with raw response)
- Missing API key raises a clean error message (no traceback)
- Committed: `feat: phase 1 core CLI working` (63ac2b9)

**To test with a real LLM:** `export OPENROUTER_API_KEY=sk-or-... && comply check`

**Phase 2 requires explicit instruction to begin.**
