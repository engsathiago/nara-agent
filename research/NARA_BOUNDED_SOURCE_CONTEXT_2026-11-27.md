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
