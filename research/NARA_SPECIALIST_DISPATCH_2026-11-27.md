# Native specialist dispatch and real-catalog checks — 2026-11-27

The integration attaches the selected Legião/skill instructions to native child
context. A real parent AIAgent, real plugin discovery and deterministic HTTP provider
verify the child request, unchanged parent tool-call arguments and technical failure
without child execution. These are runtime integration tests, not real-model quality
benchmarks. The initial three contract regressions and the injected failure path
were observed failing before their fixes.

A separate read-only check used the owner's existing Legião catalog: 91 agents,
91 commands, 11 marked orchestrators. Only a temporary profile was written; no
catalog changes, new model connections or child inference occurred. Preparing a
three-task batch took 140 ms in one observation, and replay returned identical
instructions without mutating the parent arguments. This single timing is not a
latency benchmark.

The original retrieval selected `analista_dados` for backend/API/Python development
because of the word `dados`. That was insufficient relevance. Two red-first tests
cover this case and tied metadata. Selection now abstains below match score 0.4
or effective margin 0.15. A fresh real-catalog check observed:

| Task | Result | Interpretation |
| --- | --- | --- |
| Backend/API/Python with database | No automatic specialist | Weak match corrected |
| Sales spreadsheet/dashboard analysis | `analista_dados` | Relevant by catalog metadata; execution quality not evaluated |
| Sale price/profit margin calculation | `negociacao` | Lexical retrieval; semantic fitness for calculation remains unverified |

The thresholds are heuristic, not calibrated probabilities. This does not close
intent classification or general optimal-specialist selection. The stored model
recommendation also does not bind the actual model route. Full Agent Profiles and
real varied-model team acceptance remain open.

Local artifacts (under the macOS temporary directory):

- `nara-legiao-dispatch-6glorisi/report.json`, SHA-256
  `e64358b5267d1e2a13555b91ad33c19e90388c7d97ec872dc773a18f1a1a5acd`.
- `nara-legiao-selection-yhqpzplf/report.json`, SHA-256
  `22c1a398ebf54d3bb14cdd4318792f24adf790ab0117a157d1874f1b763c8f56`.

The first profile includes the frozen preparation database. Reports contain
metadata and context hashes; complete specialist prompts are not published here.
Tests and operational configuration are documented in `docs/NARA_SPECIALIST_DISPATCH.md`.

After the resolver correction, the model-benchmark CLI consumer also passed its
focused test. The existing `phase5-dynamic-team-v1` deterministic fixture completed
with three distinct specialists and verified synthesis, under temporary root
`nara-specialist-team-regression-iep7ju19`. This preserves the earlier fixture's
contract; its fake worker model and synthetic timings are not evidence of real
multi-model quality or production speedup.
