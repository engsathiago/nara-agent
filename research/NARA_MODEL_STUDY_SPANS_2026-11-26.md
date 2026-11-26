# Model study with source IDs and explicit acceptance floors

The previous live proposal was rejected because the model returned different
numbers of steps and quotes and modified one quotation. The study protocol now
asks for paired instruction/source-ID objects. Nara presents bounded numbered
excerpts with character offsets and attaches the exact selected source text
itself. Unknown IDs, malformed instructions and model-supplied quotations are
rejected. This avoids a citation-copying task; it does not establish semantic
support or useful behavior by itself. Study receipts are version 2; previous
receipts and existing candidates are unchanged.

## Frozen live experiment

Code, model prompt, cases, scoring and promotion condition were committed at
`9c93fdf532` before the single new generation. The source and objective are the
same as the earlier negative study; no manual repair of that output was used.
The previously unused cases in `evals/media_transfer/model_study_protocol.json`
remained reserved. The unchanged evaluator scored refresh timing and exact
robot-label mapping separately. Temporary promotion required full scores on
every case, positive gain and no regression, declared before the live call.

The registered CLI used local `qwen3.5:4b`, reasoning disabled, no transient
retries, in a temporary profile. Generation consumed 842 input and 251 output
tokens. It created candidate `e4738a0d8037861b9612` with seven instructions,
each linked to an existing source excerpt. No human edited those instructions.

| Reserved case | Baseline | Model-authored procedure | Result |
| --- | --- | --- | --- |
| new_pair | 0.0 | 0.5 | Timing correct; one label in the wrong location |
| new_single | 0.0 | 0.5 | Timing correct; an extra invented label/balance |
| new_team | 0.0 | 0.5 | Timing correct; two labels in the wrong location |

Mean gain was +0.5, with zero regressions, but none of the cases reached 1.0.
**The candidate was not promoted.** Exact citations do not imply that a model
will apply a procedure correctly. Some generated instructions also preserve
source-specific details and transcription noise; this experiment does not
establish that all seven instructions are useful or correct.

## Evidence

An independent offline verifier checked the archived request/response hashes,
source offsets and exact citation mapping, unchanged generated steps, all six
model-response artifacts, paired-request equivalence and recomputed scores.
The full source and response artifacts stay local; the public report does not
republish the transcript or quotations.

- Source: `46bafd75c32053dcac9115f5eca0164bfcd4ac281efd86cf2cd870ba7882f171`.
- Study request: `0156a26d26c60cee226994606119402f289b1cdd45fa4e729481e5d2900ef53f`.
- Study response: `f7d09f373af9ce37deaba8ee631239746b166351318985240ceb39787d13af3d`.
- Model digest: `7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`.

The generic evaluator subsequently gained a predeclared minimum candidate score
and promotion recheck. The observed scores were replayed through that production
gate with minimum 1.0, without new inference or modified scores. All three cases
were reported below minimum, the result failed acceptance and `promote` raised
`candidate did not pass reserved transfer evaluation`. Replay record SHA-256:
`cf9d11b45e99e5dcfa19ed410c295fc466853c6bfa6248edfdfd7c21c7e9f795`.
The original pre-floor evaluation and result remain archived separately.

The updated source-ID lifecycle regression failed on the preceding production
format; the minimum-score CLI regression initially failed because that option
did not exist. After implementation, 84 focused tests across 14 learning/plugin
files passed, including source corruption, unknown IDs, Unicode/long-source
coverage, partial-score rejection, full-score promotion and existing rollback.
All 16 `scripts/check --staged` checks passed. The offline verifier also checked
that the floor replay preserved the original six observations and evaluator.

Final review reproduced a stale-result bug: after a passing evaluation, a new
stricter evaluation whose executable failed could still promote using the old
pass. The new regression failed with an unexpected successful promotion in its
temporary profile. Evaluation requests are now persisted before executing cases,
and promotion binds to the latest request ID, candidate/evaluator hashes,
threshold and reserved case IDs. An interrupted request is visible as pending
in `learn-show`; the prior pass remains explicitly historical.

This proves model-authored source-linked candidate creation and partial transfer
on one small UI task family. It does not close broad autonomous learning, source
discovery, independent evaluator construction, longitudinal improvement, or
the real-Reel OCR-only repository requirement. The Desktop package has not been
rebuilt with these changes; VPS validation remains a later separate stage.
