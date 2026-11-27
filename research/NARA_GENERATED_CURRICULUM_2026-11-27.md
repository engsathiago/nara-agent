# Source-grounded exercise generation

## Implemented path

Protocol v4 removes the need to supply a new case file for every study in a
configured task family. The existing queue freezes the family's brief, transfer
evaluator, domain validator and native canary evaluator before research. After
source selection, the host `nara_curriculum` task generates an explanation,
source-cited questions and three sets of exercises. The domain validator checks
the proposed material before the effective case protocol is frozen and any
procedure is generated. No generated evaluator code is executed.

The learner receives only the teaching material and, during revision, development
feedback. Reserved task payloads stay in the evaluation path. Case IDs, canonical
JSON duplicates and declared groups are checked by the host; independence beyond
those checks belongs to the domain oracle. The source citation check establishes
provenance, not truth. A permissive or defective oracle remains a defective oracle;
this implementation does not turn self-reported confidence into an independent
answer key.

Both generation and validation use mission artifacts and persisted intents.
Confirmed results survive restart; an unknown call is not silently repeated.
The job retains its original deadline. Changed source, brief, proof or effective
protocol bytes stop replay. Existing v1/v2/v3 protocols retain their behavior.
Native skill admission and rollback continue through the already merged consumer.

## Evidence and limits

The first three vertical cases failed before implementation because the queue
required a supplied case file. They now cover generated study through native
activation, a false answer rejected before learner execution, and a group shared
between practice and transfer rejected before validation.

Additional cases exercise four interruption boundaries, gateway housekeeping with
no supplied cases, and changed validation evidence. The tests use real CLI routing,
subprocess domain validation, native skill discovery and durable mission stores,
with deterministic model/web fixtures. They establish integration and recovery,
not useful learning by a live LLM or broad semantic validity of generated tasks.

The first broader run also reproduced a fresh-database race between the background
worker and its status reader. A deterministic regression confirmed the same
transient WAL-activation error. Mission Store now opts into the existing bounded
SQLite retry mechanism, without adding another storage path or swallowing errors.

Final integrated validation passed **76 tests across seven files**: generated
curriculum, Mission Store, source study, practice cycles, native admission, queued
jobs and resume. All 16 mandatory checks passed. No full-suite, live-model,
Desktop-binary or VPS validation is claimed for this increment.

## Research informing the next oracle work

- [OpenMAIC curriculum planner at the inspected commit](https://github.com/THU-MAIC/OpenMAIC/blob/3313cc4648e4cbe774ee899954e71ea6d1200ef2/skills/agent-runtime/curriculum-planner/SKILL.md):
  orders lessons by prerequisites and revisits actual prior outputs. This is a
  reference for teaching progression; it does not independently prove an agent's
  skill gain.
- [Self-Challenging Language Model Agents](https://proceedings.neurips.cc/paper_files/paper/2025/file/a5a305fac88fb4ae40969cfec5eef48d-Paper-Conference.pdf):
  proposes tasks together with verification and successful/failing test cases.
  Its reinforcement-learning results are not evidence for Nara. The applicable
  next step is a calibrated oracle catalog that rejects known wrong solutions
  and accepts known correct ones before admitting generated tasks.
- [Self-improving-agent curator](https://github.com/ygmrs/self-improving-agent/blob/182a9fe54ccd4399f7fff94b28077c458086140a/src/sia/curator.py)
  and [synthetic corpus](https://github.com/ygmrs/self-improving-agent/blob/182a9fe54ccd4399f7fff94b28077c458086140a/src/sia/corpus.py):
  the curator uses training/validation for rule selection while held-out data stays
  outside that decision. The synthetic transaction domain is narrow; neither its
  code nor its reported performance was imported into Nara.

The remaining requirements include calibrated executable oracles for useful task
families, live-model exercise quality and transfer, semantic source-conflict
adjudication and longitudinal evidence. VPS deployment remains a separate phase.
