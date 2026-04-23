# Comply Demo Guide

## What this demo shows

Open a PR with a `console.log` in the diff. Comply automatically checks it and posts a failing GitHub Check. Fix the PR — Comply goes green. No configuration by the reviewer.

**One-liner for Laura:** "Comply reads your team's rules from a YAML file, checks every PR diff automatically, and posts pass/fail results right in the GitHub review UI — no CI setup required."

---

## Setup (one-time, ~15 min)

### 1. Create the GitHub App

1. Go to **github.com → Settings → Developer settings → GitHub Apps → New GitHub App**
2. Fill in:
   - **Name:** `Comply Demo` (must be unique)
   - **Homepage URL:** `http://localhost:8000`
   - **Webhook URL:** (leave blank for now, fill in after step 4)
   - **Webhook secret:** pick any string, e.g. `comply-demo-secret`
3. Under **Permissions → Repository permissions:**
   - `Checks`: Read & Write
   - `Pull requests`: Read-only
   - `Contents`: Read-only
4. Under **Subscribe to events:** check `Pull request`
5. **Create GitHub App** → note the **App ID** shown at top

### 2. Generate a private key

On the App settings page → **Generate a private key** → downloads a `.pem` file.

```bash
mv ~/Downloads/comply-demo.*.private-key.pem comply-app.pem
```

### 3. Install the App on a test repo

- On the App settings page → **Install App** → choose your test repo

### 4. Set environment variables

```bash
export GITHUB_APP_ID=<your app ID>
export GITHUB_PRIVATE_KEY="$(cat comply-app.pem)"
export GITHUB_WEBHOOK_SECRET=comply-demo-secret
export OPENROUTER_API_KEY=sk-or-...   # only needed for llm-type rules
```

### 5. Install dependencies

```bash
pip install -e ".[webhook]"
```

### 6. Start the server

```bash
uvicorn comply.webhook:app --port 8000 --reload
```

### 7. Expose via ngrok

```bash
ngrok http 8000
```

Copy the `https://....ngrok-free.app` URL.

Go back to **GitHub App settings → Webhook URL** → paste the ngrok URL + `/webhook`:
```
https://xxxx.ngrok-free.app/webhook
```

---

## Triggering the demo

### Add a `.comply.yml` to the test repo

```yaml
rules:
  - id: no-console-log
    type: regex
    description: No console.log in production code
    pattern: '^\+.*\bconsole\.log\s*\('
    on_match: FAIL
    on_no_match: PASS

  - id: no-todo
    type: regex
    description: No TODO comments in new code
    pattern: '^\+.*\bTODO\b'
    on_match: WARN
    on_no_match: PASS
```

Commit and push this to the default branch.

### Open a failing PR

Create a branch with a `console.log`:

```bash
git checkout -b demo/failing
echo 'console.log("oops");' >> app.js
git add app.js && git commit -m "add debug log"
git push origin demo/failing
```

Open a PR on GitHub. Within seconds, the **Comply** check appears:

```
❌ Comply — 1 rule failed
❌ no-console-log — 1 match(es) found: +console.log("oops");
✅ no-todo — No matches found — rule satisfied.
```

### Fix the PR → green check

```bash
# remove the console.log
git commit -m "remove debug log" app.js
git push
```

Comply re-runs automatically:

```
✅ Comply — All rules passed
✅ no-console-log — No matches found — rule satisfied.
✅ no-todo — No matches found — rule satisfied.
```

---

## What Laura sees

1. PR opened → **Comply** check status immediately appears (pending → completed)
2. Failing PR shows red `❌` with the exact line that violated the rule
3. Fixed PR shows green `✅` — no reviewer action required

---

## Server logs during demo

```
2026-04-23 14:00:01 INFO webhook_received event=pull_request size=4821 bytes
2026-04-23 14:00:01 INFO webhook_processing repo=yourname/demo-repo pr=#1 sha=abc12345
2026-04-23 14:00:02 INFO rules_loaded repo=yourname/demo-repo count=2
2026-04-23 14:00:02 INFO   rule id=no-console-log type=regex
2026-04-23 14:00:02 INFO   rule id=no-todo type=regex
2026-04-23 14:00:02 INFO diff_fetched repo=yourname/demo-repo pr=#1 diff_bytes=312
2026-04-23 14:00:02 INFO rule_result id=no-console-log status=FAIL reason=1 match(es) found
2026-04-23 14:00:02 INFO rule_result id=no-todo status=PASS reason=No matches found
2026-04-23 14:00:02 INFO check_run_posted repo=yourname/demo-repo sha=abc12345 conclusion=failure
```

---

## Talking points

- **"Why not just a GitHub Action?"** Actions require YAML in every repo and CI minutes. Comply is a central service — one install, works across all repos.
- **"Why YAML rules?"** Non-engineers can write them. PM can add "no TODO in new code" without touching CI config.
- **"What about LLM rules?"** Point to `.comply.yml` — show the `llm` type with a plain-English prompt. "This rule would need an API key; for the demo we use regex rules which are instant and free."
