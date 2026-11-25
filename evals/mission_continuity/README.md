# Phase 1 continuity fixture

WP-00 establishes the measurement baseline before Mission Control is implemented. Run:

```bash
scripts/nara-python -m evals.mission_continuity.baseline
```

The command probes the active `nara` executable and the real modules in this checkout. It reports
inherited substrate separately from the missing mission layer. `blocked` is the correct baseline
until WP-01 through WP-04 connect the required contracts; the runner never substitutes mocks or
empty success objects for those capabilities.

Use `--output <path>` for an atomic JSON receipt and `--strict` in a gate that should fail while a
required capability is absent. The fixture intentionally starts with a local file effect: it is
deterministic, hash-reconcilable and safe to fault immediately after the write.

