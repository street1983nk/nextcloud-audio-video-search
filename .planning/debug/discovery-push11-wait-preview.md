---
status: awaiting_human_verify
trigger: "Discovery acceptance push run 43633120030 (stable33 ubuntu-24.04, 97b6a08): 20/22; search-parity FAIL (wait_preview, before_*, search_* abgebrochen), play-leak P12 p12a-reference FAIL reference_changed_since_reprove, p12a-control/p12a INVALID"
created: 2026-11-15
updated: 2026-11-15
---

## Current Focus

reasoning_checkpoint:
  hypothesis: "The preview worker commits every chunk with an index_outbox row, but no running code works the outbox off (only the start-up reconcile and the sample route publish). The words of a preview therefore never reach tantivy until a restart, so the search for the clip word has no hit."
  confirming_evidence:
    - "exapp.log 19:55:35: preview job settled media 30 complete, 20 words; state.db: transcript v9 parakeet with surface Dinosaurier, current index_rev 1, index_outbox still (30, 1)"
    - "grep: index.reconcile only in main.lifespan (start), index.publish only in api/sample.py; worker/preview.py never touches services.index"
    - "03-RESEARCH line 179 and 03-13 plan/summary assume an 'Index-Worker (Phase 1/2)' that does not exist in the code"
    - "exapp.log: POST /search 200 every 15 s from 19:56:01 to 20:01:06, no hit, wait_index fails after 300 s"
  falsification_test: "With the fix, a preview test that searches the index after chunk 1 finds the media; without it the same test fails (RED first)."
  fix_rationale: "Publishing the outbox right after each committed chunk is what D-07 (findable after every chunk) needs; it is the narrow outbox loop of reconcile, not a new mechanism."
  blind_spots: "The second cause (PHP worker exhaustion by hanging SMB reads) is not fixed here and needs an owner decision; CI proof only after the next push."

## Symptoms

expected: search-parity and play-leak PASS; ana finds the speech clip within 300 s after the preview
actual: "preview of the clip done after 0 s complete 1", then "wait_index ana has no hit after 300 s"; from 20:02 every request to Nextcloud times out (curl 28, http=000)
errors: FAIL search-parity:wait_index, before_cem_finds_the_share id=150, before_ana_finds_the_trash_copy id=151, search_* abgebrochen; P12 p12a-reference FAIL reference_changed_since_reprove
reproduction: CI run 43633120030, discovery leg stable33 ubuntu-24.04
started: first run with real models and the search-parity phase (03-17)

## Eliminated

- hypothesis: models missing in the volume or download failed
  evidence: cache hit avs-models-3a78ea81..., "model files: 5", procure silero/parakeet present, "models ready" 19:41:15
  timestamp: 2026-11-15
- hypothesis: engine child does not start / RAM guard refuses
  evidence: "engine chunk code ok seconds 2.94 / 3.34" for media 29 and 30
  timestamp: 2026-11-15
- hypothesis: wrong file (tone without speech) or VAD/language rule drops the clip
  evidence: media 30 kept_words 20, drop_* 0, speech_ms 6108; word 12 surface Dinosaurier norm dinosaurier; the 28 no_speech are the phase 1 tones
  timestamp: 2026-11-15
- hypothesis: wait limit too short
  evidence: preview complete at 19:55:35, before the wait started (19:56:01); 300 s of searches afterwards without a hit
  timestamp: 2026-11-15
- hypothesis: p12a-reference reference_changed_since_reprove is a cause of its own
  evidence: "page ana 83 t=0 http=000" at 20:27:25, Nextcloud did not answer any request after 20:02:24 (php-server.log); an empty page differs from the p12b reference
  timestamp: 2026-11-15

## Evidence

- timestamp: 2026-11-15
  checked: job log search-parity
  found: the FAIL label is wait_index, not wait_preview: the preview part passed after 0 s with complete 1
  implication: the transcript exists; the gap lies between store and search
- timestamp: 2026-11-15
  checked: artifact state.db (scratchpad disc1/art), tables current, transcript, word, index_outbox
  found: media 30 current version 9 (parakeet, level 100, index_rev 1), outbox row (30, 1) unpublished
  implication: nothing published the revision into tantivy
- timestamp: 2026-11-15
  checked: code paths that publish (grep publish/reconcile/mark_indexed)
  found: SearchIndex.reconcile only at start (main.reconcile), publish only in api/sample.py, retire_forgotten in intake/capture; no index worker
  implication: root cause 1 (product, plan 03-13/03-09 assumption)
- timestamp: 2026-11-15
  checked: php-server.log last line per PHP worker pid; exapp.log read_timeout lines
  found: workers 5400 19:44:41, 5395 19:46:15, 5403 19:48:45 (file 55 head read, timeout 30 s later), 5406 19:53:00 (file 62), 5399 19:55:17, 5405 19:56:47, 5404 19:59:17 (file 156 capture read), 5402 20:01:24 and 5401 20:02:24 (truth.sh DAV reads of ana's SMB files) accept a request and never log again; after 20:02:24 the server logs nothing
  implication: root cause 2: every read of a Samba DENY READ file pins a PHP built-in server worker forever (GatewayController comment, Findling A6); 9 pinned workers = Nextcloud dead; search_* and play-leak time out
- timestamp: 2026-11-15
  checked: StorageBreaker and capture retry
  found: storage 4 paused only after the third timeout of file 156 (19:59:47); storage 6 file 55 timed out three times without a pause (other answers of the storage reset the count); read_timeout retries after 2^n*60 s
  implication: the product itself causes 7 of the 9 pinned workers; owner decision needed (retry policy vs CI server workers)

## Resolution

root_cause: "1) Preview chunks are committed with an index_outbox row, but no code works the outbox off while the container runs, so preview words are never findable until a restart. 2) Independently, reads of Samba DENY READ files pin PHP built-in server workers forever; with the third such file (search-parity, 03-17) and truth.sh's DAV reads all 9 workers hang from 20:02:24."
fix: "1) SearchIndex.publish_pending (outbox loop of reconcile, reconcile uses it) and Preview._commit calls it after every committed chunk; a failed publication is logged with error_type and keeps the outbox row. 2) open, owner decision"
verification: "Local: test_after_the_first_chunk_the_media_is_findable_as_a_preview now searches the real tantivy index before chunk 2 (word of chunk 1 found, word of chunk 2 not yet, outbox empty); new test_a_failed_publication_keeps_the_outbox_row_and_the_job_goes_on; two publish_pending tests in test_index_publish.py; load test measures publish_pending. ruff --no-cache, format (115), pyright latest 0, vulture 0, pytest 1912 passed 15 skipped. RED run skipped on purpose (owner: pytest once); RED is structural (publish_pending did not exist, the worker never touched the index). CI proof only with the next push, and only if cause 2 is handled."
files_changed: [backend/src/audio_video_search_backend/index/publish.py, backend/src/audio_video_search_backend/worker/preview.py, backend/tests/test_preview_worker.py, backend/tests/test_index_publish.py, backend/tests/test_preview_index_load.py]
