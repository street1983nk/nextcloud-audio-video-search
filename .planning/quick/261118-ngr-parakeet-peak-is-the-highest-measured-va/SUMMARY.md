---
quick_id: 261118-ngr
status: complete
date: 2026-11-18
---

# Summary

- `PARAKEET_PEAK_BYTES`: amd64 1 147 076 608 (1093,94 MiB, run 44297803266),
  arm64 1 232 142 336 (1175,06 MiB, run 44297803266).
- `MEASURED_RUN` became `MEASURED_RUNS` (both run URLs, in record order).
- Test `test_the_constants_are_the_highest_value_on_record`; negative control:
  constant changed by 1 byte, test red, restored.
- Gates: ruff, ruff format, pyright, vulture green; 2590 passed.
- Effect on plan 05-12: max 1175,06 MiB x 1,15 = 1352 MiB, plus 512 MiB reserve
  = 1864 MiB, 184 MiB left to 2048 MiB.
