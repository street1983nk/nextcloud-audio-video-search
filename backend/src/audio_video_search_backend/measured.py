"""The measured Linux memory peak of the Parakeet child (plan 05-01, wave 0, D-05-09).

Taken in CI by the probe under ci/measure inside the pushed image, on amd64 and
arm64, on one chunk of 10 min speech plus lookahead, without a memory limit.
Two runs are on record. Each value is the highest max(ru_maxrss, VmHWM) of
both runs in KiB times 1024: for a memory limit the careful figure is the
right one, and arm64 differed by 4.5 % between the runs (owner, 2026-11-18).
The raw records with the runs and the commits live in
docs/measurements/parakeet-peak-2026-11.json; tests/test_peak_measurement.py
holds both equal. Values only, no logic.
"""

from typing import Final

PARAKEET_PEAK_BYTES: Final[dict[str, int]] = {
    "amd64": 1_147_076_608,
    "arm64": 1_232_142_336,
}

MEASURED_RUNS: Final[tuple[str, str]] = (
    "https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44304526791",
    "https://github.com/street1983nk/nextcloud-audio-video-search/actions/runs/44297803266",
)
