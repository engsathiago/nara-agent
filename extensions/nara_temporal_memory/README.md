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
