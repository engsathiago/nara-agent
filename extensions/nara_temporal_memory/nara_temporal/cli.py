"""CLI entry point discovered without loading the memory provider at parse time."""

from pathlib import Path


def register_cli(parser) -> None:
    parser.add_argument("action", choices=["serve", "status", "index"])
    parser.add_argument("--clients-file", type=Path, help="owner-only JSON with hashed client tokens (serve)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--max-batches", type=int, default=100, help="maximum embedding batches to index")


def nara_temporal_command(args) -> None:
    from plugins.memory import load_memory_provider

    if load_memory_provider("nara_temporal", register_skills=False) is None:
        raise RuntimeError("nara_temporal provider is unavailable")
    if args.action == "serve":
        if args.clients_file is None:
            raise ValueError("--clients-file is required for serve")
        from .gateway import serve_cli
        serve_cli(args)
        return

    import json
    from nara_constants import get_nara_home
    from . import TemporalMemoryStore
    from .embedding import configured_embedder

    home = get_nara_home()
    store = TemporalMemoryStore(home / "memories" / "nara-temporal.db")
    embedder = configured_embedder(home)
    if args.action == "index":
        if embedder is None:
            raise ValueError("configure memory.nara_temporal.embedding_model before indexing")
        result = store.index_embeddings(embedder, max_batches=args.max_batches)
    else:
        result = store.embedding_status(getattr(embedder, "index_key", embedder.model) if embedder else None)
        if embedder is None:
            result["health"] = "available"
            result["reason"] = "lexical mode configured"
        else:
            try:
                embedder.embed_query("Nara memory health probe")
                result["health"] = "available" if result["pending_embeddings"] == 0 else "degraded"
                result["reason"] = "embedding index ready" if result["pending_embeddings"] == 0 else "embedding index incomplete"
            except (OSError, RuntimeError, ValueError) as exc:
                result["health"] = "unavailable"
                result["reason"] = type(exc).__name__
    print(json.dumps(result, ensure_ascii=False))
