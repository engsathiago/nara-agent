# Learning a procedure from a verified mission

Nara extracts a procedural candidate only from a completed mission with
independent verification and confirmed effect receipts. The candidate starts
inactive in the temporal memory store. To test transfer to new cases:

```sh
nara mission learn-extract MISSION_ID
nara mission learn-evaluate CANDIDATE_ID \
  --cases-file /absolute/path/cases.json \
  --evaluator /absolute/path/evaluator.py \
  --development-case dev-1 \
  --minimum-candidate-score 1
nara mission learn-show CANDIDATE_ID
nara mission learn-promote CANDIDATE_ID
```

The case file is a JSON array or `{"cases": [...]}`. Every case has a unique
`case_id`; the IDs supplied with `--development-case` must be present. At least
one separate holdout case must remain. The development cases are declared but
never run by `learn-evaluate`, so the evaluator cannot tune on them during
this command.

For each holdout, Nara executes the evaluator twice in fresh temporary
directories: once with `candidate: null` (baseline) and once with the frozen
candidate object. The evaluator receives one JSON object on stdin:

```json
{"schema_version": 1, "case": {"case_id": "holdout-1"}, "candidate": null}
```

It must print one JSON object to stdout, for example:

```json
{"score": 1.0, "artifact_paths": ["observed-result.txt"]}
```

`score` must be finite and between 0 and 1. Artifacts must be files created
under that run's working directory. Nara archives the evaluator source and
the observed artifacts by SHA-256 in the profile's Mission Control learning
directory. It records baseline/candidate scores, case IDs, hashes, artifact
paths and mean delta. The evaluator runs under a temporary `NARA_HOME` with
a bounded timeout, without inherited API credential variables. It must be a
self-contained script or executable; Python files run with Nara's Python.

Promotion requires positive mean gain, zero regressions, the exact candidate
identity, the archived evaluator, and intact evidence from both variants.
`--minimum-candidate-score` declares an additional acceptance floor before the
evaluation: every reserved candidate result must reach it. Use `1` when every
case must be fully correct, or a predeclared fractional quality threshold for
graded tasks. The report preserves the threshold and lists `below_minimum`
case IDs; promotion checks the scores against that threshold again. A positive
average improvement cannot compensate for a case below the declared floor.
The default remains `0` for existing callers and reports, which require relative
improvement only. Set the threshold before observing reserved results.
Nara persists an evaluation request before the first case, binding its ID,
candidate hash, threshold, evaluator hash and reserved case IDs. Promotion must
match that latest request. If an evaluation stops or fails, an older passing
report cannot satisfy it. `learn-show` exposes `evaluation_pending` and the
request, while any older report is shown as `previous_evaluation`. Re-run the
evaluation after resolving the failure; the previous artifacts remain available.
`nara mission learn-rollback CANDIDATE_ID` disables the promoted skill and
rejects its memory. A synthetic local fixture proves this command chain and
tamper refusal. Real-task transfer quality still needs varied missions and
independent evaluation cases.

## Evaluate a competence study

Study plans now have an executable consumer. Reserve the case IDs and quality
floor before studying; then submit the frozen candidate to the existing process
evaluator. For example, after `gap-record` and candidate creation:

```sh
nara mission study-plan GAP_ID "Complete and verify every report field" \
  --source '{"uri":"file:report-spec","version":"sha256:SPEC_HASH"}' \
  --development-case dev-1 --holdout-case holdout-1 \
  --minimum-candidate-score 1
nara mission study-evaluate PLAN_ID CANDIDATE_ID \
  --cases-file /absolute/path/cases.json \
  --evaluator /absolute/path/evaluator.py \
  --system-file /absolute/path/system.json
nara mission study-show PLAN_ID
nara mission competence
```

`system.json` is a nonempty object describing the tested model, tools and
environment. These fields are operator-supplied, not automatic hardware/model
attestation. Nara adds the exact candidate identity/hash, its inactive or active
state, and the evaluator hash to keep this observation specific to the tested
combination. A demonstrated inactive candidate does not assert that the running
agent already has that skill installed.

The case file must contain exactly the development and holdout IDs in the plan;
duplicates, replacements and omissions are rejected before execution. Only
holdouts reach the evaluator, once per variant. The plan's floor is used directly;
`study-evaluate` cannot lower it. New plans default to `0.8` per case; use `1` for
tasks requiring complete correctness. Existing schema-v1 plans retain their
original relative-improvement contract (`0` floor) during migration.

Nara archives the plan, cases, system description and evaluator identity before
running, then archives the exact evaluation result. Before recording competence,
it checks the latest evaluation request, candidate, evaluator and both variants'
artifact hashes with the same verification used by promotion. The returned
`receipt_path` and `receipt_sha256` locate the evidence linked by the competence
observation. Direct Python `evaluate_study` remains a trusted score-recording API;
the CLI consumer instead derives its scores from executed, archived evaluations.

Positive mean gain, no regressions and the declared floor are all required.
A passed study whose average remains below the registry's `0.8` demonstrated
threshold records practice and leaves the gap practicing. A failed study leaves
the gap unresolved and creates no competence observation. Evaluation, observation
and gap completion commit together in one SQLite transaction. An interrupted
process may leave a study `proving`; it must be inspected/re-run and is not
reported as passed. A handled evaluator failure marks it failed/unresolved.
Each execution has its own attempt ID; handled failures also retain a failure
receipt linked to the original request. The CLI error identifies that receipt.

This command never promotes a skill; use the separately verified `learn-promote`
operation when appropriate. It connects evaluation to competence, but does not
yet schedule research, generate practice iterations, or demonstrate autonomous
learning on varied real tasks. Each variant has a bounded timeout (default 30s,
maximum 120s); total execution also depends on the number of reserved cases.
