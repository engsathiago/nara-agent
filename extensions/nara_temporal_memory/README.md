# Nara Temporal Memory

External, local-first memory provider for Nara. It keeps five explicit layers
(`working`, `episodic`, `semantic`, `procedural`, and `reflective`), source
provenance, temporal validity, correction chains, inactive candidates, and
retrieval receipts in a profile-scoped SQLite database.

The provider intentionally does not live under Nara's closed
`plugins/memory/` tree. Install it as a package/entry point or copy the
`nara_temporal/` directory to `$NARA_HOME/plugins/nara_temporal`, select
`memory.provider: nara_temporal`, and run `nara memory setup`.

Recall is a deterministic lexical baseline in this release. A semantic search
stage must pass a reserved retrieval benchmark before the provider may claim
hybrid retrieval.

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
provenance. This gateway currently uses lexical retrieval, so it does not yet
claim the datasheet's hybrid search or per-mission context budget.
