---
quick_id: 261118-lkb
date: 2026-11-18
---

# Run the security scans on phase branches

Found on 2026-11-18: `security.yml` (CodeQL, REUSE lint, pip-audit) started on a push to main, on pull requests and on the weekly schedule only. Phase 5 lives on `phase-05` without a pull request, so the 16 packages locked in plan 05-02 were built and deployed in CI without one audit.

1. `.github/workflows/security.yml`: the push trigger names `main` and `phase-*`.
2. `backend/tests/test_workflows.py`: a gate that keeps both names in the push trigger.
