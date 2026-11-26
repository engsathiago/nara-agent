# Nara completion audit — 2026-11-23

This audit maps the current implementation to `NARA_DATASHEET.md` and
`NARA_BUILD_CONTRACT.md`. A green local fixture is evidence only for the environment it exercised;
it is not used to claim a remote host, production account, acoustic dataset, market period, or
public release that was not observed.

## Authoritative local run

- On production-code commit `a72116f032e40719336711e8ff10723461cbb338`,
  `scripts/run_tests.sh` exited 0: 7,466 files, 74,220 passed, 0 final failures, 2,097 skipped.
- Commit `358c7d57041f87886510210f3e6a1deba087ca1c` changes only the pytest process reaper
  and its regression test. The focused reaper and voice tests passed (39 passed, 27 skipped),
  as did the two gateway files that timed out under unrelated machine load (13 passed).
  A second full-suite attempt was stopped after an overloaded run produced a WebSocket
  handshake timeout; it is not reported as a passing run on `358c7d5704`.
- `scripts/check --commit`: 16/16 checks passed, 0 blocking and 0 advisory findings.
- `scripts/check_product_identity.py`: Nara-only active surfaces verified.
- `evals/mission_continuity/baseline.py --strict`: `ready`, zero blockers.
- All acceptance fixtures below ran in separate roots created by the operating system's temporary
  directory API.
- The authenticated Nara Office endpoint returned HTTP 200 from the live dashboard after the
  anonymous request correctly returned 401.

## Build contract gates

| Gate | Evidence observed in this audit | Verdict |
| --- | --- | --- |
| 0 — baseline | Global `nara` command, identity guard, full suite, strict scorecard | local pass |
| 1 — surviving mission | `continuity-file-effect-v1`: injected exit 86, one effect, confirmed receipt, reconstructed and independently verified mission | local pass |
| 2 — observable operation | Mission ledger/store tests and authenticated Office state projection | local pass |
| 3 — real team | `phase5-dynamic-team-v1`: three distinct Legião specialists, three leases/receipts/artifacts, verified synthesis, 2.06x fixture speedup | deterministic local pass; varied-model statistical gate remains external |
| 4 — context and memory | `phase2-learning-transfer-v1`: fresh-session recall, reversible correction, three holdouts, +0.5 mean delta and no regression | deterministic local pass; broad real-task benchmark remains external |
| 5 — full access | Capability Router, terminal/browser/desktop tests, local fleet failover and effect reconciliation | local pass; remote VPS/SSH gate remains external |
| 6 — integrated voice | Same-mission voice bridge, presence/reconnect states and hashed transcript receipts | bridge pass; PT-BR wake detector promotion remains blocked on dataset/hardware |
| 7 — automatic evolution | `phase4-evolution-fabric-v1`: source provenance, exact evaluated hash, holdout gain, canary and rollback | deterministic local pass; prolonged real-model benchmark remains external |

## Datasheet phases

| Phase | Evidence | Current status |
| --- | --- | --- |
| 0 — foundation | Nara identity guard, command/version, clean product manifest | verified locally |
| 1 — continuity | WP-00 through WP-05 fixture, receipts, artifact and independent verifier | operational locally |
| 1B — voice bridge | request/correction/barge-in/reconnect contract and persistent mission identity | verified locally |
| 2 — temporal memory | external `nara_temporal` provider plus transfer fixture and rollback-preserving corrections | verified locally |
| 3 — competence study | real failed ZIP baseline, durable gap, sourced study plan, separate dev/holdout cases, resolved proof mission | verified locally |
| 4 — Evolution Lab | provenance, candidate evaluation, exact-hash promotion, canary and rollback | verified locally |
| 5 — dynamic teams | specialist resolver, model registry, worker plans, leases, parallel artifacts and verified synthesis | verified deterministic fixture; live varied-model benchmark pending |
| 6 — fleet | host-A failure, host-B reclaim, artifact handoff and exactly-once effect | verified local processes; remote-host recovery pending |
| 7 — voice autonomy | common mission/session bridge and privacy receipts | verified bridge; acoustic promotion pending |
| 8 — Nara Office | live plugin discovery HTTP 200; protected state endpoint 401 anonymously and 200 with the official session token | operational locally |
| 9 — policy/privacy | PDP allow/confirm/deny, exact one-use confirmation, rollback, redaction and five-surface consistency tests | implemented locally in `observe_only`; production actors/rules pending owner environment |
| 10 — distribution | backup/import preservation test, product manifest, launchd gateway, rebuilt arm64 app with valid ad-hoc signature | local distribution pass; Linux/VPS, Developer ID, notarization and publication pending |

## Optional laboratories

| Track | Evidence | Current status |
| --- | --- | --- |
| A1 — reproducible backtest | Stable dataset/config hashes, prior-row-only evaluation and explicit costs | local pass |
| A2 — paper engine | Durable ledger, limits, idempotency, pause and kill-switch tests | engine implemented; future quote-feed period pending |
| A3 — live trading | Explicitly gated by Phase 9 and owner authorization | not promoted; no broker order path is enabled |
| B1 — static REA | Read-only routing for Electron/JavaScript and native artifacts, preserved hashes, pinned REA and Ghidra | local pass |
| B2 — device/runtime investigation | Optional future expansion requiring an authorized consumer and assisted mutable effects | not claimed by the current release |
| B3 — independent reconstruction | Optional future expansion requiring a selected reconstruction target and predeclared behavior tests | not claimed by the current release |

## External acceptance still required

The following requirements cannot be truthfully completed from the current machine alone:

1. At least 100 reserved positive PT-BR wake samples, negative samples, and the target hardware for
   the `Ei, Nara` acoustic benchmark.
2. A real VPS/SSH host pair to exercise transport, host identity, incompatibility and failover.
3. Owner-selected cloud/model and messaging accounts for their real connectivity and actor mapping.
4. A future paper quote feed and an agreed observation period; no live-capital path is authorized.
5. External authenticated Memory Gateway clients on the intended external
   services. The local gateway code and two-client API/MCP protocol test now
   exist; connectivity to those services is not claimed by this fixture.
6. A varied real-task/model dataset large enough for statistical competence, team and evolution
   claims.
7. Apple Developer credentials and explicit publication authority for Developer ID signing,
   notarization and release-feed upload.

The owner separated VPS installation and validation into a later project step, after local code,
documentation, manifest and package are finished. The VPS is not a prerequisite for completing
the local implementation. External gates remain unverified until their own evidence exists;
they must not be converted to passes by mocks, documentation, empty provider rows, or a locally
signed package.

## Subsequent publication evidence (2026-11-25)

The repository is public at `https://github.com/engsathiago/nara-agent`. Its owned skills-index
workflow completed with 106,709 entries, and the GitHub Pages workflow deployed the documentation.
The public docs, skills index and plugin catalog returned HTTP 200. The live skills index matched
the workflow artifact by SHA-256; the Desktop CORS probe passed. The active desktop and plugin
identifiers now use the project's own namespace. See `research/NARA_PUBLICATION_2026-11-25.md`
for run IDs, counts and focused validation. The attempted full Python suite on the published
snapshot was interrupted after file timeouts under load, so its current verdict is still open.
The VPS, acoustic, external-account, future paper-feed and signed-release gates above remain open.
After the product-identity update, a clean local macOS bundle was rebuilt from published commit
`3c02ec2a3765587701c8c89122e432ee534c40f8`. The DMG and ZIP passed integrity checks and
both contain the project's own bundle identifier. The unpacked app passed ad-hoc code-signature
verification after packaging; the archives themselves remain unsigned and unnotarized. The
current hashes and manifest are recorded in `research/NARA_PUBLICATION_2026-11-25.md`.

The local bundle was subsequently rebuilt from clean public `main` commit `efcc2b6f846c4b2ecaad85a6df7085b6cb911249`, including the owned metrics/reporting and runtime-guard fixes. Its DMG and ZIP passed integrity checks and both carry the owned bundle identifier. The extracted app passed deep strict verification after a local ad-hoc signature applied after packaging; the archives remain unsigned and unnotarized. The exact hashes, manifest, CI runs and partial full-suite attempts are recorded in the publication report. On this commit, `nara --version`, the product-identity guard and the strict mission-continuity baseline passed. VPS installation remains a separate later step as requested by the owner.

The final local package for this stage was rebuilt again from clean public `main` commit `81194723bc2cff253ec9f95a8547fd8fc03ed097`. This includes the temporal-memory relevance fix and corrected root persona. The DMG and ZIP passed integrity checks; their identifiers and the corrected files inside the ZIP were inspected. The extracted app passed deep strict verification after local ad-hoc signing. A real local `qwen3.5:4b` one-shot query returned `OK` with zero tool calls after the memory fix; before it, the same query retrieved unrelated old instructions and entered a tool loop, which was stopped. The full Python suite on this final commit has not completed under the current machine load; focused tests and owner CI passed. See the publication report for exact hashes, test counts, and the distinction between local and external gates.

On 2026-11-26, PR #23 added the authenticated local Memory Gateway to public
`main` at `e883a70d908f3e79a048f78f000e9f6b70123c5a`, with two-client MCP
and API tests in owner CI. Optional hybrid retrieval was subsequently merged
on `main`; its PT-BR synthetic holdout and limitations are recorded in
`research/NARA_MEMORY_RETRIEVAL_2026-11-26.md`. Neither step constitutes VPS
installation or real external-service connectivity.

The procedural learning CLI was subsequently closed end to end: `learn-evaluate`
now executes a frozen evaluator against separate baseline and candidate runs,
archives evidence hashes, and refuses promotion when candidate or evidence
changes. The local vertical test covers extraction, evaluation, promotion and
tamper refusal in a temporary profile. A later gateway housekeeping pass
creates inactive candidates from newly verified missions and retries interrupted
writes. Cross-experience semantic consolidation and varied real-task transfer
remain separate requirements; these tests do not convert them into proven
capabilities.
