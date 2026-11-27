# Typed exercise payloads — 2026-11-27

The PR68 real local-model run completed source comparison but returned three
invalid `payload_json` strings. Nested JSON encoding was therefore a reproduced
integration failure, not evidence of a successful study.

## Implementation and deterministic evidence

The frozen task-family brief can now supply a bounded `payload_schema`. The
curriculum request asks for native object `payload` fields. The host validates
the declared closed-object/array/string subset independently of optional provider
validation. Unsupported schema keywords fail before research. New typed jobs use
protocol v6 and generation request v2; legacy briefs retain their exact old mode.

The independent domain evaluator, exact transfer scoring, native canary gain
requirements and admission machinery remain unchanged. ZIP exports use the typed
contract, while UTF-8 byte limits and archive semantics remain domain checks.

Two new tests failed on main `b11f62294e97a107b490c8da5d9bcd07f4e48ccc` before the
implementation: a typed generated exercise could not resume into study, and an
unsupported schema was accepted at enqueue. Focused integration then passed 62
distinct tests across six suites: typed payload (9), legacy curriculum (9),
source context (7), ZIP oracle (10), study jobs (11), native admission (16).
All 16 mandatory gates passed. The final typed suite passed again after its
test dispatch was adjusted to the repository's table-dispatch rule.

Coverage includes a confirmed curriculum generation interrupted and resumed
without another model call, removal of the editable original brief, real gateway
maintenance dispatch, reserved-case isolation from the learner, nested ZIP input
through the exported independent validator, and rejection of wrong types,
missing/extra fields, oversize strings, excessive array members and false facts.
These are deterministic fixture proofs, not real-model competence measurements.

## Fresh real-model trial

Code frozen before execution: `ab539b218d27b159dc7d9f37196e8a4cbc8ebcf2`, clean tree,
Python 3.14.9. Disposable profile:

`/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-j46lefo5`

- Job: `study-job-6a3251706708fc27d9368258`.
- Frozen protocol: `8e8c9db5c29f5b876c8e9e38f64fe8cae4f8d174337594d3d572878bcc04fd6e`.
- Local model: `qwen3.5:4b`.
- Model digest: `7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`.
- Study config: `3af63fb97e0b094043d93318e361fb2c1997e0aab8e1b176181aa36a8e611df1`.
- Source-selection request: `4de1ffc3e83933118fdce36f07ac042a177ebaf2abe54b221e82328498544907`.

Research and model calls use the actual Nara CLI and disposable profile. No VPS,
personal-profile writes or learner-visible reserved answers are involved. The
original comparison and curriculum timeouts and all evaluator floors remain in
force. The owned worker exited normally; the study outcome was a recorded failure.


### Observed outcome

The three sources were acquired successfully. The source comparison completed,
selecting the ZIP documentation; its input request hash matches the previous
PR68 comparison. Selection receipt:
`1c83b81431df8fdc34a8c89ad1799091af2f16819210f0e34cb2e02d81496004`.
Reported comparison usage: 7,330 input, 590 output, 7,920 total tokens; cost unknown.

Curriculum request: `6c524e4e472d92b97bf382c9be62f9b3bb8022d9ca0f00d9b7192a7a1a8967d4`.
Generation receipt: `2dda3bd7445d3a60c47a52e6d6f6817b16ada22c8c9f6cfff87ffd35278e61a5`.
The real model produced three questions and three native object payloads, all
passing the frozen typed payload contract. Reported usage: 3,322 input, 633
output, 3,955 total tokens; cost unknown.

However, all three cases used the same normalized group across development,
transfer and canary. Their payloads were distinct. The host rejected the package
with `curriculum repeats a case or leaks a group across splits`, before the domain
validator, learner, practice, transfer or native canary. No skill was activated.
This demonstrates real-model typed generation, not a valid curriculum or learning
gain. No reserved case contents were inspected to change the trial or its scores.

Offline verification checked all ten content-addressed artifact blobs, the frozen
protocol hash, study config and worker stdout hash, plus the typed contract for
each generated payload. Cross-case checks recorded only equality flags and split
names; no reserved payloads were printed. Worker stdout SHA-256:
`8453106f7fb1c094e0eeac15963ed147c03e4f4ad0d8958f1b50c3c192c9bcdd`.
The profile contains `summary.json` and `verification.json`; zero native skills remain.

### Remaining work

Typed generation closes the reproduced nested-JSON defect. The next concrete
consumer is a bounded curriculum correction loop with explicit validation
feedback, durable confirmed-call receipts and original deadlines. It must not
simply rename groups, weaken split separation or treat formatting success as
factual correctness. Validated real-model teaching, useful held-out transfer,
native skill gain and broader longitudinal learning remain unproved. VPS is a
later deployment stage, not a dependency of this implementation.
