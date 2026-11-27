# Source research and background study — 2026-11-26

The registered `study-research` command now acquires source evidence through the
same web tool registry as ordinary agent work. `study-enqueue`, `study-work` and
`study-jobs` join that research to the existing reserved study cycle. Jobs, progress,
artifacts and verification live in the mission event log. The gateway's maintenance
hook wakes one bounded worker under a copied profile context, rather than blocking
maintenance or running an endless model loop.

## Live web acquisition

The probe used a fresh profile, the real CLI entry point and the existing Firecrawl
keyless web backend. Only PATH/PYTHONPATH and basic locale/system environment values
were forwarded; no API keys or authenticated browser state were supplied. No model
inference or skill activation was requested.

- Objective: Python zipapp create_archive official documentation.
- Domain: `docs.python.org`; at most one source, 120 seconds to start new work.
- Result: `sources_found`, two calls (search then extraction), no acquisition errors.
- URL: `https://docs.python.org/3/library/zipapp.html`.
- Profile basename: `nara-live-source-research-zk323q1f`.
- Mission: `source-research-9729b1c4fba242cb89d4d01f1667a82f`.
- Source SHA-256: `d26d1801d5d767ceb2574a27b0c17d265c47591ab8ee68a21e8f4f428e710776`.
- Extraction artifact: `4b9c0011ad66335b50639ea4a6615072b96c9ae86b7ceed3da68f62553ee1833`.
- Final receipt SHA-256: `2c51f6bd9ce55716349383c43f8878859685a3ce5627cefc5cc35a485fc471a6`.

An independent reopening verified all three mission artifacts, the source bytes
and the event-log projection without another web call. The source remains
explicitly unverified as a learning claim. The receipt proves
acquisition and provenance, not useful transfer or competence.

## Local verification and remaining scope

Tests first failed because the registered research/enqueue commands did not exist.
The implemented vertical test freezes original inputs, removes them, searches and
extracts through the injected host-tool seam, generates a source-cited proposal,
executes real evaluator subprocesses and records competence after reserved proof.
It also checks that reserved case content never reaches generation or web search.
Failure and restart tests cover unavailable sources, insufficient holdout scores,
changed inputs, preserved deadlines, unknown research usage, and interruptions at
cycle-result, verification-record and mission-transition boundaries. A gateway
thread test holds model execution with an Event to check nonblocking maintenance,
one active worker and profile isolation.

The fixture model/web responses in those tests are deterministic. They do not
establish successful autonomous real-model learning. The live probe above uses
real web acquisition only. Configured evaluation protocols remain required; the
system does not yet create independent curricula for arbitrary new gap categories.
Skill activation, semantic source adjudication, broad transfer and longitudinal
learning are separate pending requirements. VPS installation remains a later step.
