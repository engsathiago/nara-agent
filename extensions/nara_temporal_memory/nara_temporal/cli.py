"""CLI entry point discovered without loading the memory provider at parse time."""

from pathlib import Path


def register_cli(parser) -> None:
    parser.add_argument("action", choices=["serve"])
    parser.add_argument("--clients-file", type=Path, required=True, help="owner-only JSON with hashed client tokens")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)


def nara_temporal_command(args) -> None:
    from plugins.memory import load_memory_provider

    if load_memory_provider("nara_temporal", register_skills=False) is None:
        raise RuntimeError("nara_temporal provider is unavailable")
    from .gateway import serve_cli
    serve_cli(args)
