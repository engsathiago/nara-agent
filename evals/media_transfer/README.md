# Real-media convention transfer protocol

Frozen before the first model run. Source: the user-selected public post
https://www.instagram.com/p/DdFLWjqAfMC/, already archived and locally extracted
with source SHA-256 `46bafd75c32053dcac9115f5eca0164bfcd4ac281efd86cf2cd870ba7882f171`.

The study candidate describes the video's display convention: each robot's
balance above its character and a 20-second refresh. The reserved tasks supply
new positive, negative, zero and fractional balances. The model must produce
display data, without market access or orders. It sees the input records and
output schema; expected answers are kept in the independent evaluator.

Each case runs twice through the production ProcessEvaluator: baseline without
the procedure, candidate with the procedure. Both use local `qwen3.5:4b`, seed
42, temperature 0, JSON output and the same token limit. The evidence records
model digest, complete request/response and two independently computed checks:
refresh interval and exact label mapping (IDs, balances and position).

The development example is excluded from scoring. The three reserved cases
and evaluator are fixed before any model response is observed. No tuning or
retries based on holdout scores. A transport error is an inconclusive run,
not a score. Positive mean delta with no regression passes this narrow test;
otherwise the candidate must remain inactive. A pass alone does not authorize
promotion into the user's live profile; this experiment uses a temporary home.

This measures transfer of a UI convention from real media into new structured
inputs. It is not a benchmark of broad procedural learning, coding, profitability
or autonomous improvement. This post has no extracted repository URL, so the
separate contract requirement of a real Reel with an OCR-only repository is
not established by this experiment.

## Observed result — 2026-11-26

Protocol commit: `4ad327d24ce248d4b1e88ce11c96de7cf8055c08`. All three reserved
cases scored 0.0 baseline and 1.0 with the candidate; mean delta +1.0, no
regressions. The same local model digest was observed for all six calls.
Requests, raw responses and scores are in `result_2026_11_26/`. Run
`python3 evals/media_transfer/verify_result.py` to independently recompute scores,
check artifact/protocol hashes and verify that only the procedure changed in
the paired requests. This verifier makes no model calls.

The production LearningLab accepted the frozen executable evaluation, promoted
the skill in a temporary profile, and rolled it back into `skills/.archive`.
No skill was activated in the owner's live profile. The first wrapper failed
to JSON-serialize the rollback's Path after those operations; the public export
was recovered from the already persisted artifacts without repeating the model
calls. Public report paths are normalized; its original evaluation hash is
recorded separately.

The coding assistant authored the candidate by paraphrasing an exact source
quote. This tests use of a sourced procedure supplied in context, not autonomous
candidate discovery, model weight changes or persistence of improved behavior
without retrieving the procedure. It measures one convention with one model and
three inputs; larger real-task and regression datasets are still required.

## Model-authored follow-up protocol

`run_model_study.py --source-root LOCAL_FABRIC_ROOT` exercises the registered
`nara mission learn-media-study` CLI in a new temporary profile with local
Ollama `qwen3.5:4b`. The model receives the archived transcript and the objective
in `model_study_protocol.json`; it is not given the prior hand-authored
candidate, evaluator, reserved cases or expected answers. Its first valid
candidate is evaluated unchanged on three newly frozen inputs using the same
office-convention scoring rubric. A declined or invalid response is reported;
there is no manual repair or selection among multiple candidate attempts.

The evaluator/rubric was developed for the earlier experiment, so this is a
follow-up on the same known task family, not an independent broad benchmark.
Cases, study prompt and code are committed before the live call. Successful
evaluation permits only temporary-profile promotion followed by rollback.
Full source text and study input receipts remain local. This measures model
authorship of a proposal from a selected source; automatic source discovery,
independent evaluator design and unattended self-improvement remain unproved.

The first launch failed before inference because the probe removed the managed
Python dependency path. After restoring that path, the default model route
timed out without a candidate or evaluation: its reasoning was enabled and the
host retried the request. The follow-up uses the newly registered study slot,
sets `reasoning_effort: none`, and disables transient retries in the temporary
profile. Prompt, source, cases and scoring stay unchanged; no holdout result was
seen before this configuration correction. The outer 180-second timeout now
also retains partial output for diagnosis.

The follow-up at `d914e4051c` generated an invalid proposal: ten steps, eight
quotes, including one nonliteral quote. The CLI rejected it and archived the
failure; no candidate or transfer scores were created. See
`research/NARA_MODEL_MEDIA_STUDY_2026-11-26.md` for the negative result and
evidence hashes. The model output was not manually repaired or regenerated.

## Source-ID proposal protocol (version 2)

The negative result exposed two structural problems: independently generated
step/quote lists and model-copied citations. The production study format now
pairs each instruction with an ID from numbered source excerpts. The host
resolves that ID to exact archived text. Original version 1 receipts remain
untouched; this is a new protocol, not a repair of the rejected proposal.

Before the version 2 call, freeze the code and prompt in Git. Use the same
archived source, objective, local model, reasoning-off configuration and the
still-unused cases in `model_study_protocol.json`. Generate once, with no manual
repair or holdout-guided retries. The scoring evaluator is unchanged. Temporary
promotion additionally requires every candidate score to be 1.0; partial gain
alone leaves the candidate inactive. This is a more stringent local experiment
condition, not a change to the generic LearningLab gate. Full source, generation
and evaluation receipts stay local; the public report records hashes and counts.

The version 2 live call at `9c93fdf532` produced seven source-ID-linked steps.
All three reserved cases improved from 0.0 to 0.5: refresh timing was correct,
but label mapping was not. The predeclared full-score condition prevented
temporary promotion. The candidate remains inactive; this is partial transfer,
not full mastery of the convention. The separate offline verifier checks the
original source offsets, selected citations, unedited candidate, six model
responses and scores: `scripts/nara-python evals/media_transfer/verify_study_result.py PROFILE`.

The generic LearningLab/CLI subsequently gained `--minimum-candidate-score`,
so ordinary evaluations can enforce the same declared acceptance floor.
Replaying the already archived observations with minimum 1.0 (no new model
calls) marked every case below minimum and blocked the production promotion
path. Original generation, evaluation and source artifacts were preserved.
Future probe runs pass this floor into LearningLab directly.
