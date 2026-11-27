# Same-source local 4B/27B curriculum route probe — 2026-11-27

A fresh comparison exercised two already-installed Ollama routes with the same
archived initial curriculum request and the same frozen production validators.
It did not download models, change the user's active model configuration, run a
learning promotion, or depend on a VPS.

## Reproduction and frozen inputs

- Code during execution: `adb6264705a0df142e9dd3a17f59eced6bd004c9`
  (subsequently merged as PR #76).
- Runner: `scripts/nara-python -m evals.model_comparison.run_local`, with repeated
  `--model qwen3.5:4b --model qwen38-unc-16k:latest` and `--curriculum-request`
  pointing to the archived initial request from `nara-live-zip-study-3xgzlure`.
- Source request SHA-256:
  `2460c89809d5fb701f69af390bc34253f70ef2dfa3fc56da0ef3de4def15e35e`.
- Profile:
  `/private/var/folders/c4/sn_zf7557_1gcpsyy2qtvwzr0000gn/T/nara-live-model-comparison-dzcd6ead`.
- Mission: `model-benchmark-fd28d7d46185426883104e73fe1c7367`.
- Comparison cohort:
  `6c4611f98ac888a26c72c36214d069d04dbf1a790a0e1e646329b9c1962aed95`.
- Protocol artifact:
  `sha256:06cb1be6d340c61834d4ce63b9e9e68b81f85df359a598bf10431583a051ac1d`.
- Each protocol request asked for 8,192 output tokens and reasoning `none`, with a
  120-second auxiliary timeout (the later wire probe below found no numerical token cap); frozen benchmark budget 600 seconds and outer deadline 630.
- Installed model digests: `qwen3.5:4b` =
  `7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`;
  `qwen38-unc-16k:latest` =
  `3cd491879d8edb7e1a88e1f9fd23df2bc821c9424bf1590346606a3b9dc7db32`.

## Observed outcome

| Requested route | Recorded result | Duration | Interpretation |
| --- | --- | --- | --- |
| `qwen3.5:4b` | Graded, score 0 | 29,251 ms | Repeated a case or reused a group across reserved splits |
| `qwen38-unc-16k:latest` | `route_mismatch`, ungraded | 151,652 ms total | Requested model timed out; main-model fallback returned a 4B response |

The log records the 27B request at 16:35:32 local time, its timeout after 120 s,
and fallback to `qwen3.5:4b`. The host service reported the actual fallback model.
The benchmark rejected attribution to the requested route and did not grade or
record that response as 27B quality. The 151,652 ms includes fallback generation;
it is not a measured successful-generation latency for the 27B model.

Both recorded responses have 3,491 input and 495 output tokens. These describe
the returned 4B responses, not tokens spent by the timed-out model. Call prices
are unknown. The benchmark mission is `completed` because measurement finished;
no curriculum passed, no skill was activated, and learning/transfer was not run.

One observation during the larger-model attempt showed 18 GB resident model
size, 14%/86% CPU/GPU, context 16,384, and 9% system memory free on a 24 GiB host.
This is a resource snapshot, not a hardware capacity or throughput benchmark.
The initially unloaded models were explicitly unloaded after the owned test ended.

## Evidence verification and limits

All 11 content-addressed files under Mission Control were independently rehashed,
including the grader evidence. The source-request copy matches its original hash.
The temporary profile has no installed skill.

- 4B generation receipt:
  `46188e5e5807766ffb2b325dd52a61e1473296dbe4aff70250bcbe9c7ac755d8`.
- Requested-27B/fallback receipt:
  `e552f93acbfb100387797b91bfdc383277f925dbf9bc28b4afff5a8a2e25d599`.
- Grader evidence:
  `c10302a430d2764ccf526a031e77f500f3a1b0e75c53ecf0f28637af7e7d77c3`.
- `run.stdout` SHA-256:
  `265e44fca1567db14b89f470594e644ca76f90b75178334a04550f510d6bdfa9`.

This establishes a practical failure at the tested latency budget and verifies
fallback attribution. It does not show that a 27B model is worse, cannot succeed
with a different budget/host, or that another provider will pass. A valid stronger
route result, complete source coverage, accepted curriculum and actual held-out
transfer/native-skill gain remain open. VPS remains a later separate step.

A subsequent read-only `ollama show` identifies the larger alias as qwen35,
27.3B parameters, Q4_K_M, with `num_ctx=16384` and thinking enabled by default
(boolean levels). The harness requested reasoning `none`; this probe did not
capture the HTTP request or prove how that control was interpreted by the local
server. The live server's effective behavior was not observed, so the timeout cannot be attributed solely
to parameter count or hardware. `ollama ps` was empty after cleanup.


## Offline request serialization check

The archived larger-route request was then replayed through the real PluginLlm
service and auxiliary routing, intercepting `httpx.Client.send` immediately before
network transport and returning the archived JSON as a deterministic fixture.
No model was loaded or inferred during this check. A disposable profile retained
the same model/auxiliary/trust settings, with model-catalog networking pointed at
a closed loopback port.

The serialized request targeted `qwen38-unc-16k:latest`, contained
`reasoning_effort: "none"` and `think: false`, and carried no numerical
`max_tokens` or `max_completion_tokens` value. The generic custom-provider profile
intentionally leaves output ceilings to the endpoint by default. Therefore, the
8,192 value in the frozen benchmark is a requested setting, not a demonstrated
wire-level cap for this run. Future bounded local probes should make their
endpoint-specific output cap explicit and verify its serialization.

The [official Ollama OpenAI compatibility documentation](https://docs.ollama.com/api/openai-compatibility)
lists `max_tokens` and reasoning controls, and maps `none` to disabled thinking
for boolean-control models. The [thinking documentation](https://docs.ollama.com/capabilities/thinking)
describes model-specific controls returned by `/api/show`. These documents support
the requested control's meaning; they do not prove that this installed server
applied it to the earlier live generation.

- Wire-probe profile: `nara-curriculum-wire-probe-yr1o9pn6` in the macOS temp directory.
- Serialized request SHA-256:
  `b58ebcaa3b2a77240723abd6cd023ca2120167c371f10bc14038c96f94286c50`.
- `report.json` SHA-256:
  `20ed9588ab9c47d7c38f743537c3c92a6324c7241685e123879043fe6f42594c`.

This is transport preparation evidence, not a second live model result.
