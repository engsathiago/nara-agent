"""Bounded, local-only Ollama embeddings for optional hybrid memory retrieval."""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


class EmbeddingUnavailable(RuntimeError):
    """The configured local embedding service cannot serve valid vectors."""


class OllamaEmbedder:
    def __init__(self, model: str, url: str = "http://127.0.0.1:11434", *, timeout: float = 10.0):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("embedding endpoint must be local loopback HTTP")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("embedding endpoint must be a bare local origin")
        if not model.strip():
            raise ValueError("embedding model is required")
        self.model = model.strip()
        self.index_key = f"{self.model}|retrieval-prompts-v1"
        self.url = url.rstrip("/") + "/api/embed"
        self.timeout = max(1.0, min(30.0, float(timeout)))

    def embed_query(self, query: str) -> list[float]:
        if self.model.split(":", 1)[0] == "embeddinggemma":
            query = f"task: search result | query: {query}"
        elif self.model.split(":", 1)[0] == "nomic-embed-text-v2-moe":
            query = f"search_query: {query}"
        return self.embed([query])[0]

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        if self.model.split(":", 1)[0] == "embeddinggemma":
            documents = [f"title: none | text: {document}" for document in documents]
        elif self.model.split(":", 1)[0] == "nomic-embed-text-v2-moe":
            documents = [f"search_document: {document}" for document in documents]
        return self.embed(documents)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or len(texts) > 64 or any(not text.strip() or len(text) > 12_000 for text in texts):
            raise ValueError("embedding batch must contain 1-64 non-empty texts under 12,000 characters")
        body = json.dumps({"model": self.model, "input": texts, "truncate": False}).encode("utf-8")
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (OSError, ValueError) as exc:
            raise EmbeddingUnavailable(type(exc).__name__) from exc
        vectors = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbeddingUnavailable("invalid_embedding_count")
        dimension = None
        normalized = []
        for vector in vectors:
            if not isinstance(vector, list) or not vector or any(
                not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector
            ):
                raise EmbeddingUnavailable("invalid_embedding_vector")
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise EmbeddingUnavailable("inconsistent_embedding_dimensions")
            magnitude = math.sqrt(sum(float(value) ** 2 for value in vector))
            if magnitude == 0:
                raise EmbeddingUnavailable("zero_embedding_vector")
            normalized.append([float(value) / magnitude for value in vector])
        return normalized


def configured_embedder(home: Path):
    """Resolve one profile's optional embedding model; no process-global config."""
    config_path = home / "config.yaml"
    if not config_path.is_file():
        return None
    from nara_yaml import safe_load

    config = safe_load(config_path.read_text(encoding="utf-8")) or {}
    memory = config.get("memory", {}) if isinstance(config, dict) else {}
    settings = memory.get("nara_temporal", {}) if isinstance(memory, dict) else {}
    if not isinstance(settings, dict):
        raise ValueError("memory.nara_temporal must be an object")
    model = settings.get("embedding_model", "")
    if not model:
        return None
    if not isinstance(model, str):
        raise ValueError("memory.nara_temporal.embedding_model must be a string")
    url = settings.get("embedding_url", "http://127.0.0.1:11434")
    if not isinstance(url, str):
        raise ValueError("memory.nara_temporal.embedding_url must be a string")
    return OllamaEmbedder(model, url)
