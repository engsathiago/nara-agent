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
