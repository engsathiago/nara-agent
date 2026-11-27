# Source comparison through the host model router

New queued protocols compare the acquired set before constructing a study plan.
The implementation lives in `plugins/mission_control/study_source_selection.py`
and is consumed by `StudyJobs`, including the existing gateway background worker.
There is no second agent loop or model client.

## Contracts exercised

- Compare every distinct acquired source with bounded reasons, limitations and
  exact span IDs. Study the selected source even when it is not the first result.
- Reject missing assessments, unknown sources and nonexistent citations. An
  abstention leaves the gap unresolved and does not fall back to search rank.
- Persist intent before inference; stop on unconfirmed interrupted usage. Reuse
  confirmed choice after restart without repeating web or comparison calls.
- Reopen source bytes and selection artifacts before study; changed evidence
  cannot resolve competence. Reserved case content stays out of both search and
  selection prompts. Protocol-v1 jobs preserve their original source choice.
- Treat identical source bytes at different URLs as one item, preserving aliases
  and explicitly reporting when no comparison was possible.

Seven contract cases failed on the preceding implementation. The mirrored-page
case also failed before content deduplication was added. A six-file focused run
passed 50 tests. The final selection and queue runs cover 10 and 11 tests,
respectively: 53 distinct focused tests across these runs. These are deterministic
process/CLI tests, not a varied-model benchmark.

## Frozen local-model probe

The isolated profile is `/private/tmp/nara-live-source-comparison-ly77gb19`.
It contains the original text, protocol, request/response and evidence receipts;
source text and personal profile data are not republished here.

The objective was to choose material for creating an executable Python ZIP
application from a directory with a main entry point. The acquired inputs were,
in order:

1. `https://docs.python.org/3/library/colorsys.html`, retrieved through the real
   registered `study-research` command using host search/extraction. Source hash:
   `9ad3a1f60fb3ad1ea26d048f45ff606d8e0982e3f7e2b9da32d6f6c2dc4f275a`.
2. `https://docs.python.org/3/library/zipapp.html`, reusing the exact archive from
   the earlier live source-research probe. Source hash:
   `d26d1801d5d767ceb2574a27b0c17d265c47591ab8ee68a21e8f4f428e710776`.

Before inference, the protocol fixed the expected choice, source hashes, objective,
model, one-call limit and 120-second timeout. Protocol SHA-256:
`c4b319fae6a20e6a0f4bf7e1c365f0badf07c74684bc22f6651b0e4adb7c0da3`.
A preparation error (missing mission ID) was corrected before any model request;
the frozen protocol and source bytes were unchanged.

The production selector used the registered plugin's host LLM facade with local
Ollama `qwen3.5:4b`, configured through the `custom` provider. The unedited model
response assessed both sources and chose zipapp, matching the declared choice.
Reported usage: 11,309 input tokens and 442 output tokens; cost unavailable.
Result artifact:
`sha256:dca51b3feb7dd7109c0e956f8adc4d829dedf7380d976bda1b89dfd16291089c`.
The evidence was reopened using the final selector with no model client, checking
both mission artifacts, source archives and mission projection.

This probe exercises real model selection on real acquired text. It does not
exercise an entire unattended job, reserved practice, skill activation, factual
conflict resolution or successful autonomous learning transfer. Those claims
require their own acceptance evidence.
