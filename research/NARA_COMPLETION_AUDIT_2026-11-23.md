# Nara completion audit — 2026-11-23

This audit maps the current implementation to `NARA_DATASHEET.md` and
`NARA_BUILD_CONTRACT.md`. A green local fixture is evidence only for the environment it exercised;
it is not used to claim a remote host, production account, acoustic dataset, market period, or
public release that was not observed.

## Completion scope correction

The passing regression suite and published package do not establish 100% of
the datasheet or build contract, including the locally implementable scope.
The multimodal contract still has these concrete implementation gaps:

- `LearningFabric.ingest_file` stores the original bytes permanently in the
  content-addressed archive. The downloader's temporary directory is removed,
  but that does not implement the contract's temporary-original default.
  Retention must preserve source hashes and necessary derived evidence, and
  keep procedure evaluation possible after intentional original expiry.
- The faster-whisper path now preserves native speech segment timestamps in a
  hashed archive, exposed by the existing media-show source metadata. Local
  command backends that return only plain text explicitly report timing as
  unavailable; their timestamp adapters remain incomplete.
- Real Reel-to-new-task transfer remains unproved as described in
  `NARA_MEDIA_PROCEDURE_TRANSFER_2026-11-26.md`.

Reingestion also previously accepted an existing archive without checking its
bytes. The ingestion path now verifies its SHA-256 before reuse and reports
corruption without silently replacing the evidence. The original and supplied
transcript regression cases both failed on the prior code. This correction
does not close retention or real-transfer requirements above.

The subsequent timestamp change passed 104 focused tests. The two new
provider/persistence regressions failed on the previous production code. A real
Portuguese synthesized audio file was transcribed locally using the current
checkout with the existing Desktop package's faster-whisper dependencies:
source hash `5330e1b2d2eefa1991839d97a8ac6b432294a286d75e11c54286a3df40be8690`,
one segment from 0.00 to 6.24 seconds, timing artifact SHA-256
`8d866604d355220d84b7c44cbf36b09a43fe04edf6e8e05d9b56ddbb31b8b969`.
Reopening the temporary store preserved the timing. The tests also demonstrate
that changed timing evidence blocks both cached extraction and source citation.
This is segment-level timing, not word alignment or a varied acoustic benchmark.
The existing Desktop archive has not been rebuilt with this change.

## Authoritative local run

- On the corrected production tree at `21ce2dfced0d0ea67d601021c802c9132af659ad`,
  `scripts/run_tests.sh -j 8` exited 0 in a clean code worktree at
  `450e6debd060256ccdc3cbbcb06b0ab694effeb5` (identical Git tree):
  7,480 files, 74,302 passed, 0 failed, 2,102 skipped, 2,814.5 seconds.
  Platform-specific skips are reported by the runner; this macOS run is not
  evidence of a Windows or Linux host execution.
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

The Learning Fabric has since gained local media extraction, frame OCR,
source-quoted GitHub verification, public URL acquisition and an inactive
procedure candidate path through the existing executable transfer evaluator.
The clean macOS bundle on `0231f909ff3ff5186d84c3f128e4fe7d7a5e93ba`
processed one real public Instagram post through the bundled CLI with a
minimal PATH: local speech and 20 OCR frames, without extraction errors.
The repository verification and candidate transfer fixtures are separate;
the build-contract proof of useful transfer from a real Reel to a new task
still needs a reserved real-task evaluation. See
`research/NARA_PUBLICATION_2026-11-25.md` and
`research/NARA_MEDIA_PROCEDURE_TRANSFER_2026-11-26.md`. The owner has deferred
VPS installation and remote failover validation to a separate later stage.

The learned-skill activation path was also retested against the runtime skill
catalog. Before the fix, a failed temporal-memory promotion left a discoverable
`SKILL.md`, and rollback's `.disabled` suffix still allowed the scanner to load
the skill. The local fix publishes `SKILL.md` only after memory promotion and
moves rolled-back skills under the scanner-excluded `skills/.archive/` directory.
Focused tests first reproduced both failures on the prior `main`, then passed
against the production Learning Lab and real skill discovery. This closes those
local lifecycle faults; it does not substitute for varied real-task transfer.

A fresh local macOS package from clean `main` `bacf1a9d33127c17ae463658cd4ad8461f7bcbdb`
includes both fixes. Its own bundled Python reproduced the correction,
promotion and rollback behavior in a temporary profile; the DMG and ZIP passed
integrity checks. Exact artifact hashes and the ad-hoc signature boundary are
recorded in `research/NARA_PUBLICATION_2026-11-25.md`. The earlier real public
Instagram extraction remains evidence for that URL; this package was not used
to repeat the download or to claim transfer from a real Reel.

Exact cross-experience recall now groups byte-identical active memories in the
same layer and scope, keeps the source memory IDs and originals, and withholds
copies of a fact that was explicitly corrected to different text. The
temporal-store tests and authenticated Memory Gateway API exercise duplicate
recall, correction, history, scope isolation and an explicit reversal. This is
an exact-content rule; semantic equivalence and conflict adjudication remain
unproven and are not promoted by embedding similarity alone.

The clean public `main` package at `6ae29a3283ac48048da2f078f0eb405107c4dc71`
also reproduced exact grouping, correction suppression and full history with
its own bundled Python in a fresh temporary profile. The bundled CLI reported
the same commit, and the DMG/ZIP integrity checks passed. The exact hashes and
the extracted app's ad-hoc signature boundary are recorded in
`research/NARA_PUBLICATION_2026-11-25.md`. This local smoke does not establish
semantic consolidation or real-task learning transfer.

The local media-procedure path now accepts an exact-quoted source even when no
GitHub repository appears in it. Its candidate remains inactive until the
existing frozen evaluator passes reserved cases, and source tampering blocks
evaluation. The three additional public Instagram posts checked with the
`6ae29a3` bundle had no extractable `github.com/owner/repo` URL. None yielded a
promoted procedure or a real Reel-to-new-task transfer proof; details are in
`research/NARA_MEDIA_PROCEDURE_TRANSFER_2026-11-26.md`.

The subsequent clean local `be13a3d` bundle confirmed the no-repository CLI
path on the archived public memory post: inactive candidate created, promotion
refused without a reserved evaluation, and no active skill file. The DMG/ZIP
passed integrity checks. This satisfies the local media-to-candidate seam only;
the full real-media-to-new-task transfer gate remains open.

An integral run on
`dac95d6` completed with 74,277 passing tests, 27 failures and 2,100 skips;
PR #49 repaired the observed categories, and PR #50 repaired one additional
Desktop test expectation found during the next run. The latter run was stopped
after the correction had merged, so it is not counted as a full pass. The
subsequent corrected-tree run passed in full as recorded above. The current
local product code is packaged and its CLI and archives were checked as
described in the publication report.
