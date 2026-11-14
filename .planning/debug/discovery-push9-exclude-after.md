---
status: awaiting_human_verify
trigger: "Discovery acceptance run 43561950802 (head 77359a8): 12/20; exclude-user-after, exclude-storage-after, exclude-after, reprove, vanish, delete-user, reattach, foreign-change red"
created: 2026-11-14
updated: 2026-11-14
---

## Current Focus

hypothesis: confirmed, exclusions set after the initial crawl were never applied before compare (harness)
test: push 10 discovery run
expecting: "SchedulerJob ran" and "clearing jobs done" in each exclude phase, intake with removed > 0, 20/20
next_action: wait for the owner to push 10 and read the discovery run; resolve this session only after it is green

owner_follow_up_14_11: search filter at query time (4b52a88 RED, ac6b053 GREEN, b858026 style): Provider::search and PageController::excerpt reload the rules first, Provider::entries asks isExcludedFile per hit; workflow logs on info. PHPUnit container avs-phpcheck-20: RED 688 tests 6 failures (exactly the new ones), HEAD 688 OK, php -l 68 files 0 fails, positive control exit 255.

## Symptoms

expected: after exclude-user-after / exclude-storage-after / exclude-after the index has no refs of the excluded user/storage/prefix
actual: ben_storage_refs 10 (exp 0), m3_refs 4 (exp 0), x_forgotten 3 (exp 0); unreadable_set excess 52 in every exclude phase; reprove unreadable 20 (exp 2)
errors: none, verdict FAILs
reproduction: CI run 43561950802 discovery leg stable33 amd64
started: first run that reached these phases with the reconcile route

## Eliminated

## Evidence

- timestamp: 2026-11-14
  checked: gh run view --log, step "Run the phases" (log lines 6108, 6129, 6154)
  found: "work stock complete after 0 s" right after "Added to the excluded ..." in all three exclude phases (05:43:34, 05:43:38, 05:43:43)
  implication: compare.sh wait (crawl.open, queue.open, dueWork) sees nothing of a changed but unapplied exclusion

- timestamp: 2026-11-14
  checked: exapp.log uvicorn access lines GET /status (SchedulerJob calls backendState -> GET /status; searches call it too, but are followed by POST /search)
  found: standalone GET /status at 05:37:39 (l.101) and 05:42:43 (l.337), 304 s apart; 05:38:46 and 05:43:46 are search-triggered (POST /search right after). Next SchedulerJob due ~05:47:4x; last exapp line 05:45:50
  implication: SchedulerJob did not run between the exclusions (05:43:34..43) and the end of the phases

- timestamp: 2026-11-14
  checked: exapp.log intake lines and occ-status-*.json
  found: no intake with removed>0 or forgotten>0 after 05:43; queue.open.exclude_storage 0 and exclude 0 in every status file; no warning "changed exclusions could not be applied" in nextcloud.log (loglevel 2, info lines invisible)
  implication: exclude_storage / exclude rows and ExclusionClearJobs were never created in the window; container had nothing to process

- timestamp: 2026-11-14
  checked: ids.env, results.txt
  found: 52 = ID_BEN_SMB_GESPERRT_WEBM (ben denied by Samba, unreadable before); 55,121-128 ben; 115-118 storage 9 (M3); 113,114,136,137 archiv-spaeter x/z of ana and cem
  implication: unreadable 52 is not a separate bug: it is a ref of ben's storage that the unapplied exclusion should have removed

- timestamp: 2026-11-14
  checked: exapp.log 05:44:00-05:44:32 and 05:45:33 "head read refused ... reason excluded status 403" for 55,113-118,121-128,136,137
  found: the reprove round (reproof_due 35, l.393) reads every still referenced excluded file, gateway answers 403 excluded, read proof maps it to read_denied -> unreadable (deferred item 02-13)
  implication: reprove/vanish/delete-user/reattach/foreign-change unreadable surplus is a follow-on error of the unapplied exclusions

## Resolution

root_cause: harness. Exclusions set after the first crawl become work only in SchedulerJob (TimedJob, 300 s, plan 02-18 by design); the workflow neither runs it nor does compare.sh wait know about an unapplied exclusion change or pending ExclusionClearJobs, so all three exclude phases are judged 0 s after the rule was written.
fix: compare.sh exclusions (force-run SchedulerJob, then every ExclusionClearJob until none left), called by the workflow right after the three exclude operations; gate rule EXCLUSIONS_AFTER in test_discovery_workflow.py
verification: gate RED 7b0d4f8 (22 failed), GREEN 3ee83c3 (52 passed); fake occ: normal run executes 7, 11, 12, successor 13; no SchedulerJob -> exit 1; stuck clearing job -> exit 1 after WAIT_LIMIT. ruff, format (76), pyright 0, vulture 0, pytest 1012 passed. CI proof waits for push 10.
files_changed: [backend/tests/test_discovery_workflow.py, ci/discovery/compare.sh, .github/workflows/discovery-e2e.yml]
open_for_owner: Search/Provider.php filters only an excluded searching user; hits of a storage or folder excluded after the fact stay findable until SchedulerJob applies it (<= 300 s plus cron delay in a real install).
