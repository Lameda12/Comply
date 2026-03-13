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

## Checkpoint
_To be filled after Phase 1 passes._
