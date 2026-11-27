# Verified model comparisons

Mission Control can measure configured model routes on identical frozen public
inputs, grade them in a separate Python process, and use the resulting category
statistics when resolving a subsequent task. This is an explicit measurement
path, not an automatic claim that a model is generally competent.

## Commands

```sh
nara mission model-benchmark-enqueue --protocol-file comparison.json
nara mission model-benchmark-run MODEL_BENCHMARK_MISSION_ID
nara mission model-performance archive.zip-manifest.prediction
```

The first command returns a durable mission ID. The second executes or resumes
that exact matrix; a completed rerun verifies the saved report without calling
the model again. It returns a nonzero CLI exit code for a failed job. Repeating
`enqueue` creates another independent repetition rather than overwriting the
previous observations. `model-performance --benchmark-scope HASH` selects an
explicit cohort; otherwise the latest completed cohort for that category and
current configuration is used. Different cohorts are never pooled.

A protocol contains:

- `category`: stable lowercase identifier; `instructions`: public task instructions.
- `json_schema`: structured model response contract.
- `routes`: 1–5 distinct `{provider, model}` objects, using exact runtime IDs.
- `cases`: 1–10 `{case_id, input, oracle}` objects. Only `input` reaches the model.
- `evaluator`: local Python file. Its bytes are archived before inference. It reads
  one JSON stdin object with `case` and `candidate: null`. The case includes the
  private `oracle` and the model's parsed `response`.
- The evaluator prints `{score, artifact_paths, cost_usd?}`. Score is finite in
  `[0,1]`; it must create evidence files with relative paths in its working
  directory. Files are archived and their hashes rechecked before reuse.
- `minimum_score`: positive verified success threshold, default 1; `max_tokens`:
  16–8192, default 2048; `timeout`: 1–120 seconds per call/grader, default 120;
  `max_seconds`: 1–3600 overall, default 600. The original overall deadline
  survives resume. There are at most 50 route/case cells per job.

`evals/model_comparison/run_local.py` constructs a complete example. Its
`zip_manifest_grader.py` creates actual ZIP bytes and obtains the expected
manifest from the standard library. The model predicts from a public entry list;
this does **not** test its ability to use terminal tools or learn a new skill.

## Host integration

Inference uses the plugin's public `ctx.llm.complete_structured` service and the
registered auxiliary slot `nara_model_benchmark`. The host's configured provider
and model override permissions apply. The live harness enables only its exact
local routes in a disposable profile. Normal operator profiles configure their
own `plugins.entries.mission_control.llm` settings; this feature never edits
credentials or enables overrides in the user's profile.

Requests, responses, usage, actual provider/model attribution, call duration,
grader requests, scores and evidence references are retained. The normalized
host configuration is hashed, never copied into the report. Changing it starts
a separate cohort and excludes older configuration observations from current
routing. Configuration changes before another call stop that job. Model weights,
remote backend revisions and environment changes outside this configuration are
not automatically detected; the live harness also records Ollama digests before
execution, without claiming continuous digest attestation.

## Routing and limits

The existing `nara_specialist_resolve` tool accepts `category` and optional
`benchmark_scope`. After modality/context filtering it ranks eligible candidates
by verified success rate, mean graded score, known mean model-call cost and known
mean model-call latency, then existing capability tie breakers. Missing cost is
unknown, never zero. Every completed repetition and confirmed call failure in
the selected cohort counts; a provider/model mismatch receives no quality credit.
Incomplete jobs remain visible in the mission log and supply no ranking evidence.

`AgentFactory.plan` accepts the same category/scope and freezes the selected
route plus serialized measurement evidence. Later measurements do not mutate an
existing worker plan. The resolver returns its measurement basis and evidence.
Without an exact category or comparable observations, the existing capability
fallback remains. Corrupt evidence raises an error rather than influencing a
choice. Call and grading intents are durable: an interrupted execution with no
confirmed result stops for reconciliation, not automatic retry.

This increment does not classify arbitrary requests into categories, invent an
independent oracle, schedule model exploration, expand the configured model
inventory, or automatically dispatch the returned plan to every delegation
surface. Those consumers remain separate work. A benchmark completion proves
that its measurement matrix was executed and verified, even when every model
scored zero. Small fixed suites do not establish statistical superiority or
performance on unseen tasks. Grader cost is separate from reported model-call
cost and is not included in its tie breaker.

## Local live validation

```sh
scripts/nara-python -m evals.model_comparison.run_local --model qwen3.5:4b
```

Uses installed Ollama models only, no download, and a new temporary profile.
Repeat `--model` to compare compatible installed routes on the same frozen cases.
The harness saves the protocol, model digests, stdout/stderr, final measurement
summary and report checksum. It neither starts the VPS nor activates learned
skills. Run only models suitable for the available machine.
