---
quick_id: 261118-lkb
status: complete
---

# Summary

`security.yml` now also runs on a push to `phase-*`. `test_the_security_scans_run_on_main_and_on_the_phase_branches` holds the trigger; with the old inline `branches: [main]` it is red.

Local: tests/test_workflows.py 52 passed, ruff check and format clean, pyright 0 errors.

pip-audit was run locally the way the workflow runs it during plan 05-01 (2026-11-18): no known vulnerabilities; on Windows the export leaves out uvloop (Linux only) and httpx2-jsfetch (emscripten only).

Proof only in CI: CodeQL, the REUSE lint and pip-audit on Linux have never seen the tree of `phase-05`. Their first run after the push can be red for reasons that are older than this change.
