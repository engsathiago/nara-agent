# Source-reference curriculum teaching — 2026-11-27

## Delivered behavior

A brief can opt into `teaching_schema` with mode `source-span-v1` and a bounded
list of allowed question strings. The generator selects `explanation_source_span_id`;
the runtime resolves the exact archived source text before independent validation
and teaching. It rejects invented IDs, free-form overrides and undeclared questions.
Answers, source relevance, exercise independence, transfer and native admission
remain subject to their existing validators. This is source extraction, not proof
that the model understood or learned the quoted fact.

The contract is frozen at enqueue, survives restart, supports confirmed bounded
correction and is bundled in the independent model comparator. Old briefs retain
their old free-form format. New ZIP exports use protocol v8/request v4. The ZIP
validator now reports the unsupported question, public API term and cited IDs,
and permits correcting its citations or omitting a question unsupported by the
supplied text. It does not disclose reserved cases or change acceptance criteria.

Two initial source-contract tests failed before implementation. A subsequent
regression demonstrated that citation feedback omitted the failing question;
that test also failed before its fix. Final focused validation: 63 distinct tests
across seven suites (source references 8, frozen comparator 10, typed payloads 9,
curriculum correction 6, legacy curricula 9, correction recovery 10, ZIP oracles 11).
All 16 mandatory checks passed. Tests include actual subprocess validators and
durable CLI/gateway paths with fixture model responses, not real learning gains.

## First real study: exact quotation, unsupported question citations

- Clean code: `e04dceadc95089a5d3472a9d592b70dacc89b8e9`
- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-f48lk813`
- Job: `study-job-670a7833823031bac1908449`
- Frozen protocol: `763ed8ee86e40056faae7d25ee4ca981c97a257b02c9338ad6d99a2119f90083`
- Validator: `f8e3cc5923eb04f1a0cc281a99e42b393b5b4937ae0189ec8641df5789bdde62`
- Source hash: `c9a3c17019643b6ea7ab72e7c100fb2d2a4a1a66e6a8b1c49ab1de499d2d4406`
- Initial request: `b0d3e93014d033fde1dbd69df965f3e7a7150fd7833df5386ff2e6c8fa2f2ef9`
- Result stdout: `ce780f38b9a46c7849b2c29ebff33e091e22ae64b93b27645a4d171305632fb2`

The real CLI researched three official Python documentation URLs, compared them
with local qwen3.5:4b and selected the current zipfile page. The host extraction
for this URL returned 3,118 characters; its acquired text contained `infolist`
but neither `is_dir` nor `file_size`. The generator selected span s0041 correctly
for its explanation and supplied typed exercises. All three proposals passed
structural normalization, then failed domain citation checks.

For `is_dir` and later `file_size`, the model cited s0040, which only describes a
class representing information about an archive member. That generic text does
not support either claimed API fact. The validator correctly rejected it. The
source-reference mechanism removed the free-form quotation problem in this run;
it did not manufacture missing evidence or certify answers from model knowledge.
Generation token counts were 4,890/534, 5,275/490 and 5,242/490 input/output. All
27 content-addressed blobs, frozen files and three evaluator receipts were
independently verified. The job exhausted three generations before teaching.

The acquired source was already short before lexical selection. Improving source
coverage therefore also needs acquisition/selection work, not just increasing
the model's context budget. Logs identify the extractor as exa for this URL; they
do not establish why its upstream result was incomplete. A full-source retrieval
fix or alternative extraction has not been validated by this increment.

## Second real study: structural rejection before domain validation

After the citation-feedback change, a fresh end-to-end run used:

- Clean code: `8ca1a28622fa7c7db166cc4b4efcac4b55a92048`
- Profile: `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-3xgzlure`
- Job: `study-job-f4b6eda5ba5fab155e7dc46f`
- Frozen protocol: `14cb8b65533e30f3fe07624b6331ed01c709ba43e7381cf2711987104646c072`
- Validator: `fe450a20f7e526150e0e44f18fb0035cffe6a5d8801b237faa8aed17cd7edff1`
- Source hash: `5f740b7afc8edfb17425266ac6547c51ae12dd06789aef4789476cd06c4ce271`
- Initial request: `2460c89809d5fb701f69af390bc34253f70ef2dfa3fc56da0ef3de4def15e35e`
- Result stdout: `f0ad9c45f633ef7c086df57bffda4087d01e20956cc62ea8d688735838430186`

The selected URL was the same, but extraction produced 17,949 characters and the
lexical view selected five original spans totaling 6,000 characters. This time
`infolist` and `file_size` were available. All three generated proposals reused
`api_inspection` as the group for development, transfer and canary. They were
rejected at structural validation, so the new citation diagnostic was not reached
in this live trial. Input/output tokens were 3,492/520, 3,874/520 and 3,874/520.
All 20 stored blobs and frozen files were independently rehashed.

Both trials used installed qwen3.5:4b, digest
`7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`,
requested auxiliary reasoning `none`, unknown call prices and isolated profiles.
Each profile retains `verification.json` and the original receipts. Neither
activated a skill, entered terminal practice or established transfer/native gain.
The worker command returned 0 while the durable study status was failed; job
status and evidence, not process exit alone, determine learning success.

## Remaining work

Sources changed between trials, so these are distinct operational observations,
not a causal prompt/feedback comparison. Exact citation handling is implemented;
reliable curriculum generation, complete relevant source acquisition, useful
practice, held-out transfer and native improvement remain open. Further model
measurement should freeze sources and avoid repeating blind full-study attempts.
All other outstanding datasheet capabilities remain open. VPS remains later and
separate; this work used no VPS and made no changes to the user's active profile.
