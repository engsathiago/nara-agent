# Video-to-primary-source verification — 2026-11-26

The source branch was exercised through Nara's real CLI parser with an isolated
`NARA_HOME`, source code from the branch, and the previously bundled Python
runtime for local faster-whisper. The media was synthetic: macOS `say` supplied
Portuguese speech, and a generated video frame showed
`github.com/ggml-org/whisper.cpp` while the speech did not say that address.

`learn-media-ingest --modality video --extract-local --language pt` returned
`transcribed_local` and the combined text:

> a Nara verifica resultados e preserva a fonte original.
> [screen @ 0.000s] github.com/ggml-org/whisper.cpp

The source ID was
`source:47511db13788aa99bec0f9bd38f4f39c09eec108a8e2ebf1570ccdf7fda77b34`.
`learn-repo-verify` cited the exact on-screen URL and called GitHub's public
[repository](https://docs.github.com/en/rest/repos/repos) and
[commit](https://docs.github.com/en/rest/commits/commits) API endpoints. It
returned a verified claim restricted to repository identity and existence at
commit `79b11911d9d38c4be2fc7dc8b4efeff3324c090f`. The official response
snapshot hash was
`2c33c2d270ca187294de85a97fff4d6894e90d0cedcda9a5a64f0002660085cc`;
the archived bytes matched it. The API reported the license identifier `MIT`.

This is a vertical proof of on-screen text → source quote → official API →
archived evidence → narrowly verified claim. It is not an accuracy benchmark
for real Reels, a check of the repository's features, or skill promotion.
Repository commit heads can change; the pinned SHA identifies only the state
observed during this run. Tests separately cover missing quotes, mismatched
identity, API failure, idempotent evidence, and tamper refusal.
