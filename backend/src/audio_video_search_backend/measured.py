"""The measured Linux memory peak of the Parakeet child (plan 05-01, wave 0, D-05-09).

Taken in CI by the probe under ci/measure inside the pushed image, on amd64 and
arm64, on one chunk of 10 min speech plus lookahead, without a memory limit.
Each value is max(ru_maxrss, VmHWM) of that run in KiB times 1024. The raw
records with the run and the commit live in
docs/measurements/parakeet-peak-2026-11.json; tests/test_peak_measurement.py
holds both equal. Values only, no logic.
"""

from typing import Final

PARAKEET_PEAK_BYTES: Final[dict[str, int]] = {
    "amd64": 1_142_382_592,
    "arm64": 1_178_927_104,
}

MEASURED_RUN: Final[str] = "https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44304526791"
