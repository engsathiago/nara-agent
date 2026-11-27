# Frozen-source curriculum comparison — 2026-11-27

## Implemented and verified

The local benchmark harness now accepts an archived initial curriculum request.
It freezes the identical public source, brief, instructions and JSON schema for
all compared routes, and bundles the existing production curriculum validators
into the hashed independent evaluator. Evaluation imports only the frozen bundle,
not modules from the live checkout. Source-request bytes and their hash are also
retained. Prior correction requests are refused: this measures initial generation.

The oracle accepts a valid curriculum and rejects duplicate exercises, renamed
identical topology, incorrect factual answers and invented citations. The bundle
runs the existing ZIP oracle calibration before grading. A separate regression
exposed Python accepting boolean byte counts through `False == 0` in the example
manifest-prediction grader. That test failed before the strict integer check and
passed after it; the production learning oracle already rejected boolean counts.

Validation: 22 tests across five suites (frozen curriculum comparator 5,
prediction oracle 2, producer 2, CLI 1, recovery 12); all 16 mandatory checks passed.
This is not a rerun of the entire repository suite.

## Actual inference

Clean code commit: `81cd31df89c6fc81b4174077e9bdb2db5d6c1939`.
The real enqueue/run/performance CLI path called the host model service twice,
using already installed local Ollama models. No model downloads, user-profile
changes, skill activation or VPS access occurred.

- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-model-comparison-arvyxdx8`
- Mission: `model-benchmark-fbad651c616b42e3a07ecd36cc1d3cc7`
- Category: `curriculum.zip-manifest`
- Source request: `d42bd7cac54978be7c0bfe57de856512de4dbd8072fbc8ccc655e932802ef633`
- Cohort: `855e91444e10ea47845ff5d749fee4e8a69c317c270d591b1fb98cf2b58293a1`
- Protocol artifact: `sha256:fdd3f7f4dbac66de7de4b3408916953b80752b3e7ec180c83fa20158e2ff2dcf`
- Evaluator: `aaa21e324ad60ca325626e4646d31f061b2ded7dc673e0bbe6a0bb84c7e820ee`
- Configuration fingerprint: `a21272b2e25e967f8cde2542761c522e49b7dfebfa491063208cae3aafb25537`
- Result stdout: `bae5fac9b6e70da4d104b66afec65aea7493523a15001ccf0e68c8f1b60cc3d4`

| Model | Verified score | Model-call duration | Input/output tokens |
| --- | --- | --- | --- |
| qwen3.5:4b | 0 | 40,963 ms | 3,388 / 778 |
| llama3.2:3b | 0 | 24,166 ms | 3,227 / 418 |

Recorded installed weight digests:

- qwen3.5:4b: `7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`
- llama3.2:3b: `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`

Both responses passed structural normalization but failed the first domain check:
the explanation did not quote a relevant supplied source span exactly, as the
brief requires. Qwen summarized the task; Llama returned a generic placeholder.
Inspection also showed repeated member topologies across splits in both outputs;
Llama assigned incorrect API answers. These additional observations do not change
the recorded first-rejection reason. Neither package was taught to a learner.

All 13 content-addressed artifact/evaluator blobs and both grader evidence
references were independently rehashed. Source, instructions, schema, generation
route attribution and grader receipts matched their frozen inputs. The profile
contains `verification.json` with this independent check. Unknown call prices
remain null. Exit 0 means the comparison completed, not that learning succeeded.

## Interpretation and next work

This is one initial-generation observation per route on one source. It establishes
neither statistical superiority nor a general category success rate. Loading time
and runtime conditions are included in call durations. Both calls used the same
benchmark auxiliary slot with requested reasoning `none`; task/schema names differ
from the original study call (`nara_model_benchmark`/`model_benchmark` rather than
`nara_curriculum`/`study_curriculum`). Therefore this is a controlled comparison
between these two benchmark calls, not an exact replay of the old study run.

Switching from the 4B to the installed 3B model did not yield a valid curriculum.
Next work must improve compliance with the explicit teaching and exercise
contracts or evaluate a stronger suitable route, preserving the same acceptance
criteria. Domain-approved generation, positive real transfer and native skill gain
remain unproved. Broad model inventory, automatic categories, specialist profiles
and the other datasheet requirements remain open. VPS stays a later separate step.
