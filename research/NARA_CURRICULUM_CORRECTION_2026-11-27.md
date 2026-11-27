# Durable curriculum correction — 2026-11-27

PR69's real model produced valid typed exercise objects but reused the same group
across development, transfer and canary. The package was rejected before learning.
This change implements the missing correction consumer instead of relaxing the
split or domain checks.

## Implemented behavior

An optional `curriculum.max_generations` integer (1–3) is frozen before research.
New ZIP protocols use 3 and protocol v7; generation requests use schema v3.
Legacy protocols remain single-generation, including their failure type and lack
of a correction journal. The original source/context policy, brief, evaluator,
admission floors and wall-clock deadline remain frozen across attempts.

Confirmed host structure errors and verified domain rejections receive correction
feedback. Rejection receipts link previous generation and domain validation proofs.
Replay verifies their input chain, failure meaning, evaluator identity, result,
feedback and evidence hashes. Confirmed calls are reused, while unconfirmed
execution, altered evidence, source abstention and transport errors stop work.

The generator gets at most 4,000 feedback characters and the previous proposal
only when it fits 16,000 characters; larger originals remain archived. The domain
validator sees only the current proposal/source/brief. Correction history and
reserved exercise inputs never become learner teaching material. Exhausting the
limit leaves the gap unresolved without activating a rejected proposal.

## Deterministic validation

Four scenarios failed on base `e065a86446f8fbf968a0848b5cbf5112dddfbeee` before the
implementation: the rejected curriculum could not be corrected, and boolean,
zero and four-generation bounds were accepted. The completed integration passed
78 distinct tests across eight suites: correction (6), correction recovery (10),
legacy curriculum (9), typed payload (9), source context (7), study jobs (11),
ZIP oracle (10), and native admission (16). All 16 mandatory checks passed on the
final staged code before the live trial.

The new tests exercise a group rejection, then a false answer rejected by the
independent validator, then a correct curriculum through study and native
admission. They also cover gateway maintenance dispatch, six injected checkpoint
interruptions, no repeat after unknown execution, unchanged original deadlines,
frozen attempt exhaustion, corrupted rejected-domain evidence, source abstention,
and oversized previous-proposal omission. These are fixture/control-flow proofs;
they do not establish real-model improvement.

## Fresh real-model trial

- Frozen clean code: `f8047cc22582b855cc0a9f6f92562f195eaffd10`.
- Python: 3.14.9.
- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-jorht0c_`.
- Job: `study-job-7cf246a86104deef769db7d8`.
- Protocol: `215dcc16d4278032d868f87fba5aa8e715306e724649645a6f5618a7c9a2f721`.
- Model: `qwen3.5:4b`, digest `7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`.
- Config: `3af63fb97e0b094043d93318e361fb2c1997e0aab8e1b176181aa36a8e611df1`.

The actual CLI performs web research and local inference in a disposable profile.
Per-call deadlines and all evaluation floors remain unchanged. No VPS or personal
profile is involved. The final observed outcome is recorded below.


### First outcome: confirmed corrections, rejected at the frozen bound

The three documented sources were acquired and source selection completed.
Selection request and receipt remained, respectively,
`4de1ffc3e83933118fdce36f07ac042a177ebaf2abe54b221e82328498544907` and
`1c83b81431df8fdc34a8c89ad1799091af2f16819210f0e34cb2e02d81496004`.

All three generated proposals had valid typed payloads but reused one normalized
group across all splits. The real worker sent two corrections containing the
preceding complete proposal and matching rejection feedback, then stopped at the
frozen three-generation limit. No domain validator, learner, transfer or native
admission was reached. No skill was activated. This confirms live correction
execution and bounded failure, not a successful repair or learning gain.

| Attempt | Generation receipt SHA-256 | Input/output/total tokens |
|---|---|---|
| 1 | `a149564382e8970d39737f042563c4c7fa8895da20cf250f0256ee94e3925a46` | 3389 / 527 / 3916 |
| 2 | `1b7bddca0a8b21ab6c0dc1b715439af1c318fe2c49ba3c46176b2aa88a2b5d31` | 3822 / 569 / 4391 |
| 3 | `97f19acbb6623fc87d15d54e682a05dd48eb0d9cafa0fb8b224bc21e0fed5209` | 3864 / 544 / 4408 |

Reported costs remain unknown. Offline verification checked all 17 artifact blobs,
the frozen protocol, configuration and worker stdout, payload shape, and exact
previous-proposal/feedback linkage on both correction requests. Reserved case
contents were not printed or used to modify the trial. Worker stdout SHA-256:
`fe52d3e62e53e0eaed658ee0e3fd2a23edb5de9d729413333e977af1a5a7f50e`.
The owned worker exited normally with a recorded failed study; zero native skills
remain. `summary.json` and `verification.json` are in the profile above.

The local model inventory includes 27B variants around 17.7 GB, but this 24 GiB
Mac already showed approximately 5.2 GB of compressed memory and a 5.18 GB resident
4B model. The larger model was not loaded for this comparison. The evaluation
harness now accepts `--curriculum-reasoning low` to test increased reasoning on
the existing model without changing source-selection settings or personal defaults;
frozen metadata records each auxiliary task's actual setting.


### Second outcome: requested low reasoning, generation timeout

A fresh profile used the same model digest with `nara_curriculum.reasoning_effort`
set to `low`; selection and procedure-study slots stayed at `none`. This records
requested configuration, not a provider-side guarantee of internal reasoning.
Code was clean at `702621cfc65a2f4ed57a1303cade90a9bf2c37c9`.

- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-tzarck5w`.
- Job: `study-job-0ca86ccf0e7f64edaf04e8ba`.
- Protocol: `84ed4c02ad97b0fedf77a7ad4fcc10e7460b9f3de008f82d69abd16c94c72419`.
- Config: `4af5d4f347ef9001b6b8f3888f688e017046917b2219c326e8047a8692d87415`.
- Selection request: `815e4ecfcbd3cae42993696c76bc1f8e055bfc5c3ce7260ba8bdc6d7ec5af3bb`.
- Selection receipt: `64ef3ef09ccb366c824797ccacbe8ebda480c9f0af89383bf02ef1c5d31f383b`.
- Curriculum request: `4dc0085a1ad455f982624bb48c142a0cadbe24136e1840187d942d2a557bc23b`.
- Failure receipt: `adf43979fe23e6b8c66225c5dc7444e69e62d9137ef4f4c420cb71482bcd7cfb`.

The live search returned current, Python 2.7 and Python 3.5 ZIP documentation;
the current source was selected, with extracted-text hash
`c9a3c17019643b6ea7ab72e7c100fb2d2a4a1a66e6a8b1c49ab1de499d2d4406`.
Thus source inputs changed as well as the reasoning setting: this is **not** a
controlled causal comparison of reasoning modes. Selection completed with 7,705
input / 700 output / 8,405 total reported tokens, cost unknown. Curriculum
generation failed with `APITimeoutError` at the unchanged 120-second timeout.
There was no confirmed proposal to repair, so no correction or learner call ran.

The owned worker exited with a recorded failed study. Offline checks verified all
ten artifact blobs, protocol, configuration and stdout; zero native skills remain.
Worker stdout SHA-256:
`451d1f69e2e16c1f247f56f916409bfe21d470a10a5fc259021ff118c63eaf5b`.
The profile retains `summary.json` and `verification.json`.

## Remaining evidence gates

The bounded correction consumer is implemented and exercised with real inference.
A successful real-model repair and valid domain-approved curriculum remain
unproved, as do useful held-out transfer and native skill gain. The next concrete
work is curriculum-route quality/latency calibration with identical frozen public
source inputs, followed by valid independent exercises and real execution. Group
checks and evaluator thresholds must stay intact. Factual source conflicts,
semantic memory consolidation, broader domains and longitudinal gains remain
separate unfinished requirements. VPS remains a later deployment stage.
