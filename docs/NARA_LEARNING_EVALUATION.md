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

## Run a bounded study and practice cycle

`study-run` joins the configured study model, development practice and reserved
evaluation. It operates on an archived source explicitly named and versioned in
the plan (source ID or original URI; version or SHA-256). For a new, unevaluated
plan:

```sh
nara mission study-run PLAN_ID SOURCE_ID \
  --cases-file /absolute/path/cases.json \
  --evaluator /absolute/path/evaluator.py \
  --system-file /absolute/path/system.json \
  --max-attempts 3 --max-seconds 600 --timeout 30
```

The cycle archives the complete case set and evaluator before generation. The
model receives the objective and source spans. A candidate is tried on the
development cases; only their inputs, scores and optional evaluator `feedback`
(text up to 4,000 characters) reach the next generation. The previous procedure
is included for revision. All revised steps still require source citations.
Changing the original case/evaluator files during the cycle does not change
the frozen experiment. The source archive is rechecked around generation.

Once every development case meets the plan's floor, the candidate is frozen
and the existing `study-evaluate` implementation executes the reserved baseline
and candidate. Holdout feedback never returns to generation. There is no retry
or revision after this evaluation, even when it fails. Identical repeated steps,
an explicit model decline, exhausted attempts and execution failures terminate
the cycle with a retained result. No skill is automatically activated.

The competence database journals the cycle and partial attempts. One cycle may
claim a plan; simultaneous or repeated commands cannot start another cycle with
that plan. `study-show` exposes its request, progress and result. A killed process
can leave nonterminal progress: that record alone is not proof that a process is
still running or has stopped. `study-run`, `study-resume` and `study-evaluate`
share a per-plan SQLite process lock; the OS releases it when its owner exits.
New experiments
need a new plan with genuinely unused reserved cases. Case IDs are operator
declarations, not a global guarantee that content was never seen elsewhere.

### Resume an interrupted cycle

```sh
nara mission study-resume PLAN_ID
```

Resume uses the original archived source, cases, evaluator bytes and dispatch
mode, and system description. It verifies candidate, generation and evaluator
evidence before starting new work. The original generation/evaluator counters,
reported cost and absolute deadline persist; restart does not grant another
budget. Confirmed practice and reserved observations are reused without running
their processes again. Once holdout evaluation starts, the candidate stays
frozen and no new model generation is allowed. An already completed proof can
be recorded after the deadline without new inference. Repeating a terminal
resume returns the same verified final receipt.

An interrupted generation with no confirmed response consumes its reserved
attempt and leaves its cost unknown. A monetary limit therefore stops it as
`budget_unverifiable`; without one, remaining attempts may continue. An evaluator
intent without a confirmed outcome instead stops as `reconciliation_required`:
its subprocess or external effects may survive its parent, so Nara does not
automatically repeat it. Inspect and reconcile those effects before a new study.
This state does not claim that every child process has stopped. Legacy cycles
without a call journal cannot be resumed safely; completed legacy receipts are
still inspectable. Resumption is explicit through this command; background
restart scheduling is separate.

Resource bounds are explicit: 1–5 generation calls (default 3), at most 10
development and 20 reserved cases, 2,048 output tokens per generation request,
and a 1–3,600 second deadline (default 600). The deadline prevents new work after
expiry; an in-flight host request/retry can finish later. The configured host
router still owns transport retries, so generation-call count is not a physical
HTTP-request count. Each evaluator subprocess has its own bounded timeout.

If the gap has a monetary budget, Nara checks reported cost after each generation
and evaluator call and stops when exhausted or unverifiable. Evaluators may
return a finite nonnegative `cost_usd`; missing cost is recorded as unknown,
never as verified zero. This is post-call cost accounting, not a prepaid spending
cap: the last call may exceed the budget, and provider estimates may be incomplete.
Without a monetary limit, unknown costs remain explicit in the result.

The foreground pipeline supplies the executable study/practice consumer.
The source-research and background-queue consumers below extend it. Broad
longitudinal learning remains a separate completion gate.


## Discover sources and run background study

`study-research` uses the configured host `web_search` and `web_extract` tools.
It searches an explicit public learning objective, filters result URLs by optional
domains, deduplicates them and acquires up to five pages. It does not send a gap's
private diagnosis to a search engine. The complete search/extraction responses,
source hashes and observed failures are artifacts of an ordinary durable mission.
The archived source is the provider's extracted text, which may be truncated;
it is not a claim of full-page preservation. A source is an unverified quotation
source, not a demonstrated capability.

```sh
nara mission study-research GAP_ID \
  --objective "Python ZIP application creation documentation" \
  --domain docs.python.org --max-sources 3 --max-seconds 120
```

A study job freezes an evaluation protocol **before** research or generation.
The owner/evaluation author supplies separate development and reserved cases and
an executable evaluator with the contract described above. Source content cannot
replace these files. This example is a protocol file; paths must be absolute:

```json
{
  "objective": "Inspect a repository's pinned commit before using its code",
  "domains": ["docs.github.com"],
  "cases_file": "/absolute/path/cases.json",
  "evaluator": "/absolute/path/evaluator.py",
  "system_file": "/absolute/path/system.json",
  "development_case_ids": ["practice-1"],
  "minimum_candidate_score": 1.0,
  "max_sources": 3,
  "research_seconds": 120,
  "max_attempts": 3,
  "max_seconds": 600,
  "timeout": 30
}
```

```sh
nara mission study-enqueue GAP_ID --protocol-file /absolute/path/protocol.json
nara mission study-work
nara mission study-jobs
```

Jobs are missions, not a second mission database. `study-work` selects one pending
job by gap impact and age. The worker acquires a process-owned lock, archives web
sources, compares their usefulness for the objective, creates a reserved plan and runs the
existing study/practice/transfer cycle. Missing sources, changed protocol bytes,
unresolved execution and insufficient transfer leave the gap unresolved. Original
protocol files can disappear after enqueue; their frozen copies remain the inputs.
A completed study does not activate a skill automatically. Discovery is ranked by
the configured search provider; the acquired set is then assessed by the host's
`nara_source_selection` auxiliary model task. Each source needs a bounded reason,
limitations and 1-3 exact source-span citations; the selected source must be one
of those assessed as usable. Invented source IDs, missing assessments, invalid
citations or abstention stop the job without falling back to the first result.

The comparison input contains only the objective and archived source spans, never
reserved cases, solutions or the private gap diagnosis. Requests, raw responses,
provider/model, reported usage and resolved quotations are content-addressed
mission artifacts. The persisted choice is checked against those artifacts and
source bytes before study or resumption. A single acquired source is explicitly
recorded as `single_source_not_compared` and incurs no comparison model call.
Pages with identical archived bytes share one evidence source; acquired URL aliases
are retained rather than counted as independent corroboration.
Existing protocol-v1 jobs retain their original first-source choice; new jobs
freeze protocol v2. This avoids changing an already-declared experiment on replay.

The model's assessment is a relevance judgment, not independent verification of
source truth, authority or citation entailment. Contradictions and version limits
can be reported in its limitations, but are not automatically resolved through
additional external evidence. At most five extracted sources (48,000 characters
each) are compared in one call capped at 4,096 output tokens and 120 seconds or
the remaining job deadline. Reported comparison cost is archived separately from
the subsequent study-cycle usage; unknown usage is not treated as free.

To wake this worker from gateway maintenance, configure the plugin's settings:

```yaml
plugins:
  entries:
    mission_control:
      settings:
        study_background:
          enabled: true
          interval_seconds: 600
          protocols:
            repositories:
              objective: "Inspect a repository's pinned commit before using its code"
              domains: [docs.github.com]
              cases_file: /absolute/path/cases.json
              evaluator: /absolute/path/evaluator.py
              system_file: /absolute/path/system.json
              development_case_ids: [practice-1]
              minimum_candidate_score: 1.0
              max_seconds: 600
```

When due, a worker first resumes pending jobs, otherwise queues one open gap whose
category has a configured protocol. It runs one job and exits; there is no permanent
LLM loop. Gateway maintenance returns immediately while the worker runs in a copied
profile context. A second wake cannot duplicate the active worker, and a separate
process cannot acquire its queue-worker lock. Without a matching protocol a gap
stays open, visible through `gap-list`; no evaluator or reserved solution is invented.
Background work is disabled until configured. The same commands remain available
for explicit operation and inspection.

The job deadline includes research and source comparison and is not renewed on restart. Confirmed study
work resumes through `study-resume`; an interrupted research or comparison call with unconfirmed
usage stops for reconciliation instead of repeating potentially billed requests.
The profile's web providers own transport timeouts: the job deadline blocks new
calls, but does not claim to interrupt an already-running host request. Web tools
currently expose no priced-usage contract, so research records unknown cost. For a
gap with a monetary limit, it stops after the first unpriced request; this is not a
prepaid spending cap. Neither web research nor deterministic queue tests establish
that a real model learns successfully or generalizes to arbitrary domains.

## Recover skill publication and rollback

`learn-promote` and `learn-rollback` serialize changes to a candidate with an
OS-owned deployment lock. If the owner exits, another process can resume; a
persisted flag is not considered proof that a worker is alive. The transfer
request records the candidate's lifecycle status as observed during evaluation.
Verification reconstructs that exact hash while still checking every procedure
field, evaluator and evidence artifact. Promotion or rollback alone therefore
cannot invalidate the proof. Legacy reports recover only their original lifecycle
status from the recorded hash; altered descriptions, steps, versions and evidence
remain invalid.

Repeating promotion keeps the exact matching native skill and the memory's
version. An existing edited skill is reported instead of overwritten. Memory
promotion precedes atomic skill publication, so an unavailable memory provider
cannot expose a newly loadable skill. If the process exits after memory promotion
or publication but before candidate metadata is saved, repeating `learn-promote`
finishes the same operation.

Rollback moves the exact skill directory out of runtime discovery before rejecting
its procedural memory. Repeating it reuses the archive and does not increment an
already-rejected memory. A partially removed skill cannot be republished while
rollback is incomplete. Existing archives with the older suffix format remain
recoverable; ambiguous multiple archives or simultaneous active/archived copies
require reconciliation rather than an arbitrary choice. A rolled-back candidate
is not automatically reactivated.

Process-kill tests exercise memory promotion, native skill publication and removal
before memory rejection; concurrent attempts cannot acquire the same lock. These
prove local recovery, not an unattended canary or automatic skill admission.
The background study worker still leaves newly evaluated candidates inactive;
the Evolution Lab admission/activation consumer remains a separate pending step.
