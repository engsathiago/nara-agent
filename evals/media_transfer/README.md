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
