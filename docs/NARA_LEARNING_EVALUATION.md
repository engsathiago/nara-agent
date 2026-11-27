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
Without the optional `skill_admission` protocol described below, a completed study
leaves its candidate inactive. Discovery is ranked by
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
freeze protocol v2, v3 with native-skill admission, or v4 with generated curricula.
This avoids
changing an already-declared experiment on replay.

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
The generated-curriculum option below can supply new cases for a configured task family.
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
prove local publication recovery. The optional queue consumer below also exercises
isolated native-skill canaries and automatic admission.


## Automatically admit a native skill after study

Add this optional block to the study protocol (including a category protocol in
`study_background.protocols`) to freeze protocol v3 before research begins:

```json
"skill_admission": {
  "cases_file": "/absolute/path/native-canary-cases.json",
  "evaluator": "/absolute/path/native-canary.py",
  "minimum_score": 1.0,
  "minimum_gain": 0.01
}
```

The canary file uses the same case format as transfer evaluation. It must contain
1–5 unique case IDs, disjoint from both development and reserved transfer cases.
The author must also keep the tasks genuinely separate: distinct IDs alone do not
prove semantic independence. The positive correctness and improvement floors,
case bytes and evaluator bytes are frozen at enqueue. No canary case or solution
is sent to source selection or candidate generation. The original job deadline
also covers the canaries; restarting does not grant more time.

After reserved transfer succeeds, the worker renders a native `SKILL.md`, registers
its exact hash in Evolution Lab and runs two subprocesses per canary case. Each
has a disposable `NARA_HOME`: the baseline has no proposed skill, and the candidate
has precisely those native skill bytes. Both receive `candidate: null`; the
procedure is available only through native skill discovery. The request adds:

```json
"canary": {"skill_name": "nara-learned-example-12345678", "variant": "candidate"}
```

The trusted evaluator must exercise the task using that profile, return the normal
score/artifact contract and report `observed_skill_sha256` (the discovered skill's
SHA-256, or `null` for baseline). The host checks the staged file, returned hash,
evaluator hash and archived evidence independently. This validates file identity
and a declared evaluator contract; it cannot make a dishonest or weak grader
reliable. A temporary profile is not an operating-system filesystem sandbox.

Every candidate score must meet `minimum_score`; mean gain must meet
`minimum_gain`, with zero regressions. Unknown reported cost stays unknown in the
ledger, rather than becoming zero; an Evolution experiment with a monetary cap
cannot pass on unknown cost. Background web research already stops a budgeted gap
after an unpriced provider call, as explained above. This is not a prepaid cap.

On success the queue publishes the identical bytes, promotes procedural memory,
activates the Evolution variant and records a separate native-skill verification
before completing the job. Existing sessions keep their current prompt; new
runtime discovery can load the skill. Publication failure leaves
`publication_pending`, visible through `study-jobs`, for an idempotent retry.
Confirmed canaries are reused. An intent left without a confirmed result becomes
`reconciliation_required` and is never silently executed again. Changed evidence
after partial publication triggers withdrawal; failed withdrawal is exposed for
reconciliation instead of reported as a completed cleanup.

```sh
nara mission study-jobs
nara mission study-work
nara mission study-rollback JOB_ID --reason "Withdraw this learned procedure"
```

Rollback removes the native skill, rejects its procedural memory and restores the
previous Evolution variant. Repeating it reuses the same result; cancelling a
publication that never created a skill does not invent an archive. Withdrawal
remains available even if the original evaluation files have become unavailable.

Vertical tests exercise real native discovery, the registered CLI, gateway
housekeeping and process termination at three admission boundaries. Their grader
is deterministic and checks a prepared procedure; these results establish the
consumer and recovery behavior, not real-model task improvement. Automatic
curriculum generation for arbitrary domains, independent evaluator validation and
broad longitudinal transfer remain separate gates. The configured-family generator
below supplies new exercises without operator-authored case files. Protocols without this option retain their
existing inactive-candidate behavior.


## Generate new exercises from the researched source

A protocol can now declare `curriculum` instead of supplying `cases_file`,
`development_case_ids` and `skill_admission`. This is protocol v4. The same
`study-enqueue`, `study-work` and gateway background worker consume it:

```json
{
  "objective": "Inspect a pinned repository commit before use",
  "domains": ["docs.github.com"],
  "evaluator": "/absolute/path/transfer-evaluator.py",
  "system_file": "/absolute/path/system.json",
  "minimum_candidate_score": 1.0,
  "max_seconds": 600,
  "timeout": 30,
  "curriculum": {
    "brief_file": "/absolute/path/task-family.json",
    "validator": "/absolute/path/curriculum-validator.py",
    "canary_evaluator": "/absolute/path/native-canary.py",
    "minimum_score": 1.0,
    "minimum_gain": 0.01
  }
}
```

The brief is a nonempty JSON object, limited to 16,000 characters, defining the
supported task family, case payload contract and required independence between
problems. The transfer evaluator, native evaluator, brief and domain validator
are copied and hashed at enqueue, before source research. They remain executable
operator-configured components; the model produces exercise data, not executable
evaluator code. Existing protocol-v1/v2/v3 jobs keep their declared behavior.

After research and source selection, the host model task `nara_curriculum` receives
only the public objective, selected source spans and brief. One bounded call
(up to 8,192 output tokens and 120 seconds or the remaining deadline) proposes:

- an explanation and 1–5 questions/answers citing supplied source spans;
- 1–10 development cases, 1–20 reserved transfer cases and 1–5 native canaries;
- a distinct case ID, split, underlying problem `group_id` and JSON object payload
  for each exercise; no code or replacement evaluator is accepted.

The host rejects duplicate identities, duplicate JSON payloads and groups shared
across splits. Group names are normalized for case and surrounding whitespace.
These checks cannot prove semantic independence when a generator invents different
group labels. The trusted domain validator must check that property, factual
answers, question relevance, reserved-answer leakage through teaching text and
fitness for the declared evaluator. Exact source
citations prove where text came from, not that a question or answer is correct.
A validator that accepts everything invalidates the experiment's meaning.

The validator uses the existing subprocess evaluator contract. It receives
`candidate: null` and a `case` object containing `case_id`, `curriculum`, `objective`,
`source` and `brief`. `curriculum.teaching_material` contains the explanation and
questions with resolved citations. Each `curriculum.cases` row contains `case_id`,
`split`, normalized `group_id` and decoded `payload`. It must return score `1.0`
with actual validation evidence to admit the package; a lower score stops the job
before candidate generation. Its input, file hash, result and evidence hashes are
archived. This is a trusted domain oracle, not another ungrounded model vote.

The admitted cases are then frozen before the learner runs. The existing study
cycle receives the explanation/questions as `study_material`, with an instruction
to use the original source for authority. Reserved case payloads and validator
inputs are not included. Development feedback remains the only task-feedback
channel into later procedure revisions. Passing transfer still leads to the
separate native canary and activation described above.

Generation and validation each have a persisted intent and confirmed receipt.
Restart reopens confirmed receipts and checks source, brief, evaluator, evidence
and effective protocol bytes without regenerating questions or re-running the
validator. An intent without a result stops for reconciliation; the original job
deadline is never renewed. `study-jobs` exposes these phases and artifact IDs in
`progress`; `mission artifact-show` can inspect their underlying evidence.
Generation usage and validator cost remain in separate receipts, including unknown
cost, rather than being reported as free. The web research monetary-limit caveat
above still applies. Temporary profiles do not create an OS sandbox.

This removes the need to write every new exercise manually for a configured task
family. It does not supply a universal oracle, automatically trust a new validator,
prove semantic independence in arbitrary subjects or establish real-model learning
gain. The deterministic tests use a deliberately narrow repository-inspection
oracle and verify both acceptance and rejection through the production CLI and
gateway. Broader domain verifiers and live-model evidence remain required.

## Calibrated ZIP task family

`nara mission study-oracles` lists shipped domain oracles and runs their local
calibration without calling a model. The first family, `zip-manifest`, exports a
protocol-v4 package:

```bash
nara mission study-oracle-prepare zip-manifest /absolute/new/zip-study --model qwen3.5:4b
nara mission study-enqueue GAP_ID --protocol-file /absolute/new/zip-study/protocol.json
nara mission study-work
```

The model must already be installed on the local HTTP endpoint (default Ollama
`http://127.0.0.1:11434/v1`). Export records the runtime revision, dirty status,
Python version and evaluator hashes. It refuses to overwrite an existing package.
This family uses public Python documentation, generates three structurally
different archives, and verifies the lesson's selected API facts against the
calibrated contract. Renaming files or group IDs cannot disguise an identical
member topology across splits. Explanation text must be an exact relevant source
span, rather than unverified generated prose. The supported API facts are
`ZipFile.infolist`, `ZipInfo.is_dir` and `ZipInfo.file_size`; see the
[Python reference](https://docs.python.org/3.14/library/zipfile.html).

Before export and again at curriculum validation, the oracle checks correct and
incorrect reports against real ZIP files: nested members, directories, UTF-8 byte
counts, boolean counts, extra fields, absent artifacts and empty archives. A
failed calibration prevents use. This is finite calibration of a narrow domain,
not proof that every possible validator defect has been excluded.

Practice and transfer launch the real `nara -z` CLI with its terminal tool in a
disposable working directory. The task must produce `manifest.json`; the oracle
compares exact file paths, uncompressed byte totals and directory count to actual
archive metadata, and verifies the archive was not changed. Native canaries use
the ordinary `-s` skill preloader and bind the exact staged skill hash. Runtime
errors do not count as task failure scores. Usage and output artifacts are kept;
unknown monetary cost remains unknown. Temporary profiles are not OS sandboxes.

`evals/generated_curriculum/run_zip_study.py` runs the research-to-study pipeline
with a local model in a fresh profile, records its installed model digest, and
withdraws any admitted skill before finishing. Invoke it with
`scripts/nara-python evals/generated_curriculum/run_zip_study.py --model MODEL`.
It performs real web/model calls; it is an opt-in evaluation, not a unit test.
Do not adjust a protocol using already-revealed reserved results. A baseline
that already solves the task yields no positive gain and must not cause promotion.

The research consumer archives the complete web-tool response (within its 1 MB
response bound) before preparing a study text window of at most 48,000 characters.
`text_window` source metadata records start/end offsets, received length and hash,
and whether the response was clipped. The web extractor may already return a
partial page; the archived response and its study window are not represented as
a complete original page. This also accommodates paging footers that exceed the
requested extractor character limit.
