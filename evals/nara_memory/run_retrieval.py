"""Compare lexical and local Ollama hybrid retrieval on a fixed PT-BR holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from extensions.nara_temporal_memory.nara_temporal import TemporalMemoryStore
from extensions.nara_temporal_memory.nara_temporal.embedding import OllamaEmbedder


def run(dataset: Path, model: str, url: str) -> dict:
    source = json.loads(dataset.read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="nara-memory-eval-") as temp:
        store = TemporalMemoryStore(Path(temp) / "memory.db")
        targets = {}
        for case in source["cases"]:
            item = store.add(case["content"], layer="semantic", source_type="evaluation",
                             source_ref=case["id"], status="active")
            targets[case["id"]] = item["memory_id"]
        embedder = OllamaEmbedder(model, url)
        store.index_embeddings(embedder)
        observations = []
        for case in source["cases"]:
            for query in case["queries"]:
                lexical = store.search(query, limit=1)
                hybrid = store.search(query, limit=1, embedder=embedder)
                expected = targets[case["id"]]
                observations.append({
                    "query": query, "expected": case["id"],
                    "lexical_hit": bool(lexical["items"] and lexical["items"][0]["memory_id"] == expected),
                    "hybrid_hit": bool(hybrid["items"] and hybrid["items"][0]["memory_id"] == expected),
                    "hybrid_mode": hybrid["mode"], "receipt_id": hybrid["receipt_id"],
                })
        negatives = []
        for query in source["negative_queries"]:
            hybrid = store.search(query, limit=1, embedder=embedder)
            negatives.append({"query": query, "false_positive": bool(hybrid["items"]),
                              "receipt_id": hybrid["receipt_id"]})
        return {
            "model": model, "cases": len(observations),
            "lexical_top1": sum(item["lexical_hit"] for item in observations),
            "hybrid_top1": sum(item["hybrid_hit"] for item in observations),
            "negative_cases": len(negatives),
            "hybrid_false_positives": sum(item["false_positive"] for item in negatives),
            "observations": observations, "negatives": negatives,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("retrieval_cases.json"))
    parser.add_argument("--model", default="embeddinggemma")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.dataset, args.model, args.url)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
