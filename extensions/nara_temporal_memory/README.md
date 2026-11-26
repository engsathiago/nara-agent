# Nara Temporal Memory

External, local-first memory provider for Nara. It keeps five explicit layers
(`working`, `episodic`, `semantic`, `procedural`, and `reflective`), source
provenance, temporal validity, correction chains, inactive candidates, and
retrieval receipts in a profile-scoped SQLite database.

The provider intentionally does not live under Nara's closed
`plugins/memory/` tree. Install it as a package/entry point or copy the
`nara_temporal/` directory to `$NARA_HOME/plugins/nara_temporal`, select
`memory.provider: nara_temporal`, and run `nara memory setup`.

Recall works in lexical mode without an embedding model. To enable local
hybrid retrieval, set `memory.nara_temporal.embedding_model: embeddinggemma` in
the selected profile's `config.yaml` (or run `nara memory setup`) and keep the
local Ollama service available at `http://127.0.0.1:11434`. Pull the model once
with `ollama pull embeddinggemma`. The model is optional. The endpoint accepts
only loopback HTTP; select a locally installed Ollama model to keep embeddings
on this machine.

```sh
nara nara_temporal status
nara nara_temporal index
```

`status` distinguishes lexical mode, an incomplete embedding index, and an
unavailable embedding service. `index` catches up to 6,300 current memories per
invocation; re-run if `pending_embeddings` remains nonzero. New current memories
are indexed on subsequent searches. Search returns `hybrid`, `hybrid_partial`,
or `lexical_degraded` with a retrieval receipt; an embedding failure falls back
visibly to lexical search. Results have a 6,000-character context budget by
default (callers may request 512–24,000), while `memory_get` keeps the
unabridged original. The SQLite schema
adds a model-specific embedding cache without changing memory IDs or sources.

The reserved local PT-BR evaluation passed its predeclared gate (16/20 hybrid
top-1 versus 6/20 lexical, 0/4 unrelated-query false positives) on
`embeddinggemma:latest`. See `evals/nara_memory/HOLDOUT.md` and the dated
retrieval report in `research/`. This small synthetic gate supports a local
opt-in; broader real-task evaluation is still needed before claiming universal
retrieval quality. EmbeddingGemma's query/document prompt formats follow the
[model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card).

## Memory Gateway

The same `memories/nara-temporal.db` can be served to authorized local clients
through JSON API and streamable HTTP MCP. With the provider installed, run:

```sh
nara nara_temporal serve --clients-file /absolute/private/path/memory-clients.json
```

The default address is `127.0.0.1:8788`. The server refuses non-loopback bind
addresses. Use a private SSH tunnel when a later deployment needs remote access.
The client file must be owner-only (`chmod 600` on POSIX) and contains hashes,
never raw bearer tokens:

```json
{
  "clients": [
    {
      "id": "codex",
      "token_sha256": "<lowercase SHA-256 hex of a long random bearer token>",
      "scope": "project:nara",
      "permissions": ["read", "propose"]
    }
  ]
}
```

Generate each token with a cryptographic random generator, save the token in
the external client's secret store, and put only its SHA-256 digest in the
client file. Every request needs `Authorization: Bearer <token>`, including
MCP initialization. The MCP endpoint is `/mcp` with tools `memory_search`,
`memory_get`, `memory_propose`, `memory_correct`, and `memory_receipt`. The API
uses `POST /v1/memory/{search,propose,correct}` and
`GET /v1/memory/{get,receipt}/{id}` with JSON bodies and responses.

Each client is pinned to one exact memory scope. Reads show active memories in
that scope, plus the client's own candidates by ID. Retrieval receipts belong
to the client that searched. Proposals and corrections stay inactive until the
Nara runtime verifies and promotes them. External clients have no promotion
endpoint. Their identity and supplied source reference are retained as
provenance. The gateway uses the same lexical or configured hybrid path as the
in-agent provider, including the context budget and retrieval receipt.
