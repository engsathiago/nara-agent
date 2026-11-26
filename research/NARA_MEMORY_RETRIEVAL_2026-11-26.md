# Nara temporal retrieval evaluation — 2026-11-26

## Local setup and reproducibility

- Ollama `0.40.5` on `127.0.0.1:11434`.
- `embeddinggemma:latest`, digest
  `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`.
- Development dataset SHA-256:
  `0c53597efeafabe45fbe863ea05221a72126f6b90ab4fad8b0c539c3adeab15b`.
- Reserved dataset SHA-256:
  `9278d9da3b1a7232d49aed2335c0bb7c398b48e198c0813a940454df21a61458`.
- The embedding input uses the query and document prompts in the
  [EmbeddingGemma model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card)
  and the [Ollama `/api/embed` contract](https://docs.ollama.com/api/embed).

Run from the repository root:

```sh
scripts/run-in-nara-env python -m evals.nara_memory.run_retrieval \
  --dataset evals/nara_memory/retrieval_holdout.json \
  --model embeddinggemma \
  --output /absolute/path/retrieval-result.json
```

The harness creates a temporary profile database, indexes only the fixed
passages, and compares one-result lexical and hybrid retrieval for every query.
It checks unrelated questions separately. No live user memory is used.

## Observed results

| Corpus | Lexical top-1 | Hybrid top-1 | Unrelated false positives |
| --- | ---: | ---: | ---: |
| Development, 24 positives + 4 negatives | 3/24 | 20/24 | 0/4 |
| Reserved, 20 positives + 4 negatives | 6/20 | 16/20 | 0/4 |

All 20 reserved positive queries reported `hybrid`, with no degraded fallback.
The reserved gate in `evals/nara_memory/HOLDOUT.md` was declared before running
the reserved dataset and passed: hybrid top-1 reached 16/20, improved by 10,
and returned no memory for the four unrelated questions. Four reserved misses
remain in browser, learning and mission recovery paraphrases. These are visible
errors, not hidden successes.

The local gate supports **optional** hybrid retrieval in this environment.
It does not prove that the model generalizes to varied real conversations,
large memory banks, or other languages and hardware. The model remains unset
by default; lexical mode stays available, and an embedding outage is marked
`lexical_degraded` in each retrieval receipt. The exact code can be evaluated
on a future owner-approved real-query dataset without changing the benchmark.
