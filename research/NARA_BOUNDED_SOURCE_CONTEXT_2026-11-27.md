# Bounded source context for automatic study — 2026-11-27

PR67's final real-model source comparison reached its 120-second deadline. This
did not identify whether prefill, generation, transport or model loading caused
the delay. This increment adds a bounded relevant-source view as an efficiency
improvement to measure, without loosening the task verifier or raising deadlines.

## Implementation

Protocol v5 freezes an optional `source_context` policy before research. The
`lexical-spans-v1` algorithm ranks complete original spans using public objective
words and optional public topic terms. It retains original IDs, Unicode text and
character offsets, and returns selected spans in document order. Metadata and an
explicit model instruction disclose partial coverage. Archived sources and raw
web-tool receipts are unchanged. Versions without the option retain their full
span input and no new view metadata.

The policy is wired through source comparison and its replay, curriculum
generation/validation, effective-protocol freezing, procedure study and study-cycle
resume. The ZIP export supplies a 6,000-character per-source policy with its three
API topics. This is a source-text limit, not a total prompt/token budget. Lexical
selection can omit relevant context and contradictions; it does not prove truth.

Five initial regression cases failed before implementation: missing projection,
an unbounded learner after curriculum restart, and three invalid budgets being
silently accepted. The first integrated run passed 42 tests across context,
source selection, media study and study resume. Expanded tests also exercise
multi-source comparison and a failed practice attempt revised after restart.

Real-model outcomes and final validation are recorded below after execution.

## First bounded real-model comparison

Code frozen at `8a647836e1ed685948155a57c809e01db770ece2`.
The real run used a fresh profile at
`/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-zip-study-pp38yt76`.
Its actual comparison request contained three acquired sources: ZIP (35,270 source
characters, 6,000 selected), TAR (3,127 source characters, 3,111 selected), and
shutil (19,763 source characters, 5,363 selected). The serialized model input,
including offsets, IDs and metadata, measured 19,557 characters. Original byte
archives remained intact. The local Ollama residency endpoint reported only
`qwen3.5:4b`, with its weights resident in VRAM, during the observation.

The comparison still hit its 120-second API timeout. Failure receipt:
`010e29d71547954cc671bc0f556ef410e70ed4957ee8930d483ead15ba687546`.
No curriculum, practice or reserved cases were generated. This demonstrates the
input bound, not a successful latency fix or learning improvement.

Review found that the harness explicitly disabled reasoning for curriculum and
procedure generation but left source selection at the provider default. A separate
trial now aligns all three auxiliary slots to `reasoning_effort: none` and records
the study-profile configuration hash before execution. This changes the disposable
evaluation configuration, not users' defaults, grading criteria or deadlines.
It is a separate trial; outcomes cannot isolate context selection as the sole
cause of any timing difference.
