"""Integration test: fake PR diff → rule parser → check result (real path, no mocks)."""

import pytest
from comply.checker import check_all


DIFF_WITH_CONSOLE_LOG = """\
diff --git a/src/app.js b/src/app.js
index abc1234..def5678 100644
--- a/src/app.js
+++ b/src/app.js
@@ -1,5 +1,7 @@
 function init() {
+  console.log("debug: starting app");
   return true;
 }
+console.log("top-level side effect");
"""

DIFF_CLEAN = """\
diff --git a/src/app.js b/src/app.js
index abc1234..def5678 100644
--- a/src/app.js
+++ b/src/app.js
@@ -1,3 +1,4 @@
 function init() {
+  return setup();
   return true;
 }
"""

DIFF_WITH_PRINT = """\
diff --git a/main.py b/main.py
index 0000001..0000002 100644
--- a/main.py
+++ b/main.py
@@ -1,3 +1,5 @@
 def run():
+    print("debug output")
     return 42
"""

DIFF_WITH_BARE_EXCEPT = """\
diff --git a/handler.py b/handler.py
index 0000001..0000002 100644
--- a/handler.py
+++ b/handler.py
@@ -1,5 +1,8 @@
 def handle():
+    try:
+        risky()
+    except:
+        pass
     return None
"""


# ── regex rule tests ──────────────────────────────────────────────────────────

def test_regex_no_console_log_catches_violation():
    rules = [{
        "id": "no-console-log",
        "type": "regex",
        "description": "No console.log in production code",
        "pattern": r"^\+.*\bconsole\.log\s*\(",
        "on_match": "FAIL",
        "on_no_match": "PASS",
    }]
    results = check_all(rules, DIFF_WITH_CONSOLE_LOG)
    assert len(results) == 1
    r = results[0]
    assert r["id"] == "no-console-log"
    assert r["status"] == "FAIL"
    assert "match" in r["reason"].lower()


def test_regex_no_console_log_passes_clean_diff():
    rules = [{
        "id": "no-console-log",
        "type": "regex",
        "description": "No console.log in production code",
        "pattern": r"^\+.*\bconsole\.log\s*\(",
        "on_match": "FAIL",
        "on_no_match": "PASS",
    }]
    results = check_all(rules, DIFF_CLEAN)
    assert results[0]["status"] == "PASS"


def test_regex_no_print_catches_python_print():
    rules = [{
        "id": "no-print",
        "type": "regex",
        "description": "No print() calls",
        "pattern": r"^\+.*\bprint\s*\(",
        "on_match": "WARN",
        "on_no_match": "PASS",
    }]
    results = check_all(rules, DIFF_WITH_PRINT)
    assert results[0]["status"] == "WARN"


# ── ast rule tests ────────────────────────────────────────────────────────────

def test_ast_no_bare_except_passes_clean_diff():
    rules = [{
        "id": "no-bare-except",
        "type": "ast",
        "description": "No bare except clauses",
        "check": "no-bare-except",
    }]
    # Clean diff has no Python files that exist on disk → PASS (no files to check)
    results = check_all(rules, DIFF_CLEAN)
    assert results[0]["status"] == "PASS"


# ── multiple rules + depends_on ───────────────────────────────────────────────

def test_multiple_rules_all_pass_clean_diff():
    rules = [
        {
            "id": "no-console-log",
            "type": "regex",
            "pattern": r"^\+.*\bconsole\.log\s*\(",
            "on_match": "FAIL",
            "on_no_match": "PASS",
        },
        {
            "id": "no-todo",
            "type": "regex",
            "pattern": r"^\+.*\b(TODO|FIXME)\b",
            "on_match": "WARN",
            "on_no_match": "PASS",
        },
    ]
    results = check_all(rules, DIFF_CLEAN)
    assert all(r["status"] == "PASS" for r in results)


def test_depends_on_skips_when_dependency_passes():
    rules = [
        {
            "id": "migration-exists",
            "type": "regex",
            "description": "Detect migration files",
            "pattern": r"^\+.*migrations/.*\.py",
            "on_match": "WARN",
            "on_no_match": "PASS",
        },
        {
            "id": "migration-rollback",
            "type": "regex",
            "description": "Migration must have rollback",
            "depends_on": "migration-exists",
            "pattern": r"def downgrade",
            "on_match": "PASS",
            "on_no_match": "FAIL",
        },
    ]
    # No migration files in diff → migration-exists PASS → migration-rollback SKIP
    results = check_all(rules, DIFF_CLEAN)
    by_id = {r["id"]: r for r in results}
    assert by_id["migration-exists"]["status"] == "PASS"
    assert by_id["migration-rollback"]["status"] == "SKIP"


def test_depends_on_runs_when_dependency_fails():
    rules = [
        {
            "id": "no-console-log",
            "type": "regex",
            "pattern": r"^\+.*\bconsole\.log\s*\(",
            "on_match": "FAIL",
            "on_no_match": "PASS",
        },
        {
            "id": "follow-up-rule",
            "type": "regex",
            "depends_on": "no-console-log",
            "pattern": r"^\+.*\bconsole\.warn\s*\(",
            "on_match": "WARN",
            "on_no_match": "PASS",
        },
    ]
    # console.log present → no-console-log FAIL → follow-up-rule runs (not skipped)
    results = check_all(rules, DIFF_WITH_CONSOLE_LOG)
    by_id = {r["id"]: r for r in results}
    assert by_id["no-console-log"]["status"] == "FAIL"
    assert by_id["follow-up-rule"]["status"] != "SKIP"


# ── unknown rule type ─────────────────────────────────────────────────────────

def test_unknown_rule_type_returns_warn():
    rules = [{"id": "bad-rule", "type": "magic", "description": "test"}]
    results = check_all(rules, DIFF_CLEAN)
    assert results[0]["status"] == "WARN"
    assert "Unknown rule type" in results[0]["reason"]
