---
quick_id: 261118-ngr
date: 2026-11-18
---

# Parakeet peak is the highest measured value of both runs

Owner decision 2026-11-18 (open question of plan 05-01): the need of the Parakeet
child is the highest value ever measured, not the value of the last run. arm64
differed by 4.5 % between the two runs on record (1124 vs 1175 MiB); for a memory
limit the careful figure is the right one.

Task: `measured.py` carries per architecture the maximum over both runs of the
record, names both runs, and `test_peak_measurement.py` holds that rule.
The record file is unchanged.
