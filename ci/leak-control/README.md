# Leak control of the read proof

`read-proof-off.patch` exists for one purpose: the control leg `leak-control`
of the workflow `Discovery acceptance` (`.github/workflows/discovery-e2e.yml`).

## Why it exists

A further copy of a file may hang at a content only after its own read proof
(D-02-01a): the first 64 KiB through its own file id and its own reader. The
acceptance test checks that a user whom the SMB server denies a file gets no
hit for it. A test like that can pass for the wrong reason, so it needs a
positive control: the same case has to show the leak as soon as the read proof
is gone. Only then the test is known to see what it guards against.

The product has no way to turn the read proof off (D-02-10): no environment
variable, no setting, no marker file, no development switch.
`backend/tests/test_read_proof_gate.py` fails when one appears. The control
therefore runs an image of its own, built in CI out of a patched copy.

## What the patch does

It changes one file, `backend/src/audio_video_search_backend/worker/read_proof.py`:
`prove_read` answers ok at once, without a request. Nothing else is touched.

## Rules

- The patch is applied to a copy of `backend/` under `RUNNER_TEMP`, never to
  the checkout. The checkout has to be clean afterwards.
- The image built out of that copy lives only in the registry of the runner,
  `localhost:5000`. It is never pushed to ghcr.io or any other registry, never
  written to a file with `docker save`, never uploaded as an artifact and never
  exported to a build cache.
- No other workflow names the patch. `docker.yml` and `release.yml` build the
  product out of `backend/`, and `ci/` is outside that build context.
- The patch lives here and nowhere else in the repository.

`backend/tests/test_read_proof_gate.py` (rule e) and
`backend/tests/test_discovery_workflow.py` hold these rules.

## After a change to read_proof.py

The patch has to apply cleanly, the gate applies it to a copy on every run
(`git apply --check`). After a change to `read_proof.py` create it again:

1. Copy `backend/src/audio_video_search_backend/worker/read_proof.py` into two
   trees `a/` and `b/` outside the repository, each under the same path
   `backend/src/audio_video_search_backend/worker/`.
2. In `b/`, put `return ProofOutcome.OK` as the first statement of
   `prove_read`, after its docstring. The original stays unchanged.
3. Run `git diff --no-index a b`, replace the path prefixes `a/a/` and `b/b/`
   in the header lines by `a/` and `b/`, and store the result as
   `ci/leak-control/read-proof-off.patch` with LF line endings.
4. Run `uv run pytest tests/test_read_proof_gate.py` in `backend/`.
