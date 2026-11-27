# Verified model performance — 2026-11-27

## Delivered behavior

Previously `ModelCandidate.observed_score` had no production measurement producer.
Mission Control now exposes enqueue/run/performance commands backed by durable
missions, immutable artifacts, a separate-process grader and verified ledger
observations. Exact task-category measurements feed the existing specialist
resolver and subsequent frozen worker plans. Unknown costs remain unknown; all
completed repetitions and confirmed call failures count in their cohort. Host
configuration changes partition measurements. Details and explicit limits:
`docs/NARA_MODEL_BENCHMARKS.md`.

The original two producer tests failed before the implementation; a registered-CLI
integration test also failed on the absent commands. Final focused validation:
37 distinct tests in seven suites (benchmarks 2, CLI 1, recovery 12, oracle 1,
specialists 5, plugin 5, background study jobs 11). All 16 mandatory checks passed.
Recovery covers confirmed generation/grading/cell/report checkpoints, interruption
before confirmation, expired original deadlines, corrupted artifacts and a crash
after the verified ledger event. No duplicate call or observation is credited.
The local grader was calibrated with three known-correct and three incorrect
responses before the real run.

## Real hosted-inference trial

Code commit: `e6cf2b2efbc47be3d6e71b09f83e833bc612506c`; clean working tree.
The committed opt-in harness ran `nara mission model-benchmark-enqueue`,
`model-benchmark-run`, and `model-performance` through the actual CLI, plugin
registration and host model service, in a disposable profile. Only the existing
local model was used; no model download or VPS operation occurred.

- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-model-comparison-xtrutt6n`
- Mission: `model-benchmark-5738e0048f754de3b4f0468b14c05710`
- Route: `custom` / `qwen3.5:4b`, local Ollama; requested auxiliary reasoning `none`.
- Model digest: `7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`
- Category: `archive.zip-manifest.prediction`
- Cohort: `c03c8e53c4da7eef768a080b0e78da5a8b68791239c4c1e96483f6988693c4b8`
- Frozen protocol artifact: `sha256:8b2105132247446e98ca29248ae734fd8adaadcb588517a578495ddc9d34da96`
- Evaluator: `79552629efeb4f725e0a11f8df426c1b5743f22289db426637388e9b9aaa0563`
- Normalized configuration fingerprint: `a44bebae87f4204c75e0050e6d9d29326c472d19e6b22d6dac0f171fb452deb4`
- Result stdout: `d173023d2270ce73a32beb5cb3cecb4f8fb8df301768e6d78f880c39763f514c`

| Frozen case | Verified score | Model-call duration | Input/output tokens |
| --- | --- | --- | --- |
| Regular and empty file | 1 | 9,282 ms | 230 / 37 |
| Directory exclusion | 1 | 3,450 ms | 234 / 25 |
| UTF-8 accents and emoji | 0 | 3,710 ms | 232 / 37 |

All three responses had the expected structured shape and exact route
attribution. The independent ZIP evaluator rejected the Unicode answer:
`ação🙂` occupies 10 UTF-8 bytes, but the model returned 6; with the second
file it returned total 8 instead of 12. The ledger-derived report retained
success rate and mean score `2/3`, mean call duration `5480.6667 ms`, zero
call failures and zero route mismatches. All three prices were absent, so
mean cost is `null`, not zero. CLI exit was 0 because the measurement matrix
completed, not because all answers were correct.

All 19 artifact/evaluator blobs and all grader-evidence references were
independently rehashed. The disposable profile contains `verification.json`,
`frozen.json`, stdout/stderr, summaries and the complete durable mission log.
No learned skill was activated by this benchmark.

## Remaining work

This establishes a working measurement producer and resolver consumer. It does
not prove learning, held-out transfer, a native skill gain, model superiority,
terminal operation or autonomous assignment of every worker. The suite predicts
manifests from entry descriptions; the grader, not the model, operates real ZIP
bytes. The small three-case trial is a recorded observation, not a performance
estimate for the entire category.

The existing factory is still a planning API. A concrete next integration is a
public delegation-provider adapter that consumes the verified choice when the
core creates a child, preserving its existing lifecycle and immutable route.
Broader model inventory, category classification and scheduled exploration also
remain. The learning path still needs domain-approved generated curricula and
positive real transfer/native admission. These and other datasheet gaps stay open;
VPS validation remains a separate later step.
