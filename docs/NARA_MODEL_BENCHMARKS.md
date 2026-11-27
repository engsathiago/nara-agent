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
independent oracle, schedule model exploration, discover every installed/cloud model, or assemble complete specialist profiles.
The opt-in `nara-measured` backend below applies the verified choice at core
child creation; other delegation surfaces remain separate work. A benchmark completion proves
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


## Apply measurements when creating subagents

With `nara-measured` selected, the specialist resolver and Agent Factory read
the same validated route pool as the executor.

The bundled `delegation/nara-measured` backend implements the host's public
`DelegationProvider` contract. It returns a model route before the existing core
creates each child; core still owns execution, prompts, tool restrictions,
concurrency, session state, cancellation and results. No second agent loop is
introduced. This backend does not assemble the specialist's full prompt or
silently substitute a model during an active child run.

Configure an explicit trusted route pool and select this backend for a new
session. Example (replace model IDs and verify the declared capabilities):

```yaml
delegation:
  backend: nara-measured
  backends:
    nara-measured:
      routes:
        - provider: custom
          model: YOUR_INSTALLED_MODEL
          base_url: http://127.0.0.1:11434/v1
          api_key: local
          reasoning_effort: none
          capabilities:
            supports_tools: true
            supports_vision: false
            supports_reasoning: false
            context_window: 32768
```

There may be 1–32 routes, each with a distinct provider/model identity. They
carry ordinary host route fields, including endpoint/credential configuration,
plus declared capabilities. Unknown tool support is not eligible; vision tasks
need explicit vision support. Context capacity must meet the task requirement.
Profile routes are excluded because they would override the measured model
identity. These declarations describe the operator's configuration, not a live
capability/availability probe. Credentials remain host-owned and are not copied
into selection labels or benchmark statistics.

The ordinary `delegate_task` tool gains stable per-task fields:

```json
{"tasks":[{"goal":"Produce the manifest for these ZIP entries...",
           "task_category":"archive.zip-manifest.prediction",
           "requires_vision":false,"min_context":16000}]}
```

`benchmark_scope` optionally pins a particular comparison cohort. The leader
must supply a known category; omitting it uses capability fallback. The returned
child route label explains the basis and, for measured choices, includes success
rate, sample count and full cohort hash. Changing measurement history does not
change the tool schema, preserving the session's cached prompt. Changing the
backend itself follows the host's existing next-session or explicit `--now`
semantics.

An incompatible task, invalid requirement or damaged measurement prevents that
child from starting; compatible siblings still execute. The backend uses the
same current-configuration comparison filter as the resolver. Configure the
route pool **before** measuring it; changing the configuration requires a new
cohort. A single provider/model may not represent multiple differently configured
routes in this pool. Actual quality under the child agent's system prompt and
toolset still requires child-task evaluation; a structured auxiliary benchmark
is a routing signal, not proof of tool-using competence.

Behavior tests use real plugin discovery, credential resolution and delegation.
They verify the model reaches child construction, and a full `AIAgent` child run
with a recording localhost model server verifies the selected model reaches the
HTTP request and produces a result. Those server responses are fixtures, not
real-model quality evidence. The separate Ollama trial above verifies real
benchmark inference; it does not establish a three-model live team mission.


## Compare initial curriculum generation on a frozen source

The same live harness accepts `--curriculum-request PATH`, pointing to an archived
initial ZIP `curriculum_request` artifact. With repeated `--model` arguments, each
installed local model receives identical public source spans, brief, instructions
and output schema. Prior correction proposals are excluded. This measures the
initial generation's validity under category `curriculum.zip-manifest`, not its
ability to learn or operate tools.

The comparator snapshots the existing structural, typed-payload and ZIP domain
validators, together with their small standard-library-only dependencies, into a
single archived evaluator. Its subprocess imports this frozen package, not the
live checkout. It calibrates the ZIP oracle, then checks source citations, factual
answers and distinct task topologies using the same validators as study jobs.
The output includes hashes of the bundled modules. Correct examples and negative
controls for repeated cases, renamed topologies, incorrect facts and invented
citations are exercised before live comparisons.

The original request bytes and SHA-256 are preserved beside `frozen.json` in the
disposable profile. The benchmark's own frozen protocol also retains the exact
public input, schema and instructions. The host task/schema names are those of
the benchmark service; source and prompt content are controlled across the
compared models. This does not replay a study's correction history or activate
any skill. A one-source result is a diagnostic observation, not a statistically
validated model ranking for all curricula.
