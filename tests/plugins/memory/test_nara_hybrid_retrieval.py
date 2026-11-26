"""Hybrid retrieval, correction invalidation, visible fallback, and context budget."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from extensions.nara_temporal_memory.nara_temporal import NaraTemporalMemoryProvider, TemporalMemoryStore
from extensions.nara_temporal_memory.nara_temporal.embedding import EmbeddingUnavailable, OllamaEmbedder


class SemanticFixture:
    model = "semantic-fixture-v1"

    def embed(self, texts):
        vectors = []
        for text in texts:
            lower = text.lower()
            if any(term in lower for term in ("credentials", "secrets", "keychain", "credential")):
                vectors.append([1.0, 0.0])
            elif any(term in lower for term in ("atomic", "fsync", "package")):
                vectors.append([0.0, 1.0])
            else:
                vectors.append([-1.0, 0.0])
        return vectors


def test_paraphrase_retrieval_and_correction_use_canonical_index(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memory.db")
    original = store.add("Store credentials in keychain", layer="procedural", source_type="verified_mission",
                         source_ref="mission:1", status="active")
    store.add("Use atomic rename after fsync", layer="procedural", source_type="verified_mission",
              source_ref="mission:2", status="active")
    assert store.search("Where do secrets live?")["items"] == []

    result = store.search("Where do secrets live?", embedder=SemanticFixture())
    assert result["mode"] == "hybrid"
    assert result["items"][0]["memory_id"] == original["memory_id"]
    assert store.embedding_status(SemanticFixture.model)["pending_embeddings"] == 0
    receipt = store.get_receipt(result["receipt_id"])
    assert receipt["filters"]["embedding_model"] == "semantic-fixture-v1"
    assert receipt["reasons"][original["memory_id"]]["semantic_rank"] == 1

    corrected = store.add("Keep credentials in the encrypted keychain", layer="procedural",
                          source_type="operator", source_ref="correction:1", status="candidate",
                          supersedes_id=original["memory_id"])
    store.promote(corrected["memory_id"])
    assert store.embedding_status(SemanticFixture.model)["pending_embeddings"] == 1
    assert store.index_embeddings(SemanticFixture())["pending_embeddings"] == 0
    result = store.search("Where do secrets live?", embedder=SemanticFixture())
    assert result["items"][0]["memory_id"] == corrected["memory_id"]
    assert original["memory_id"] not in [item["memory_id"] for item in result["items"]]


def test_embedding_failure_is_visible_and_lexical_retrieval_survives(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memory.db")
    memory = store.add("Use atomic rename after fsync", layer="procedural", source_type="mission",
                       source_ref="mission:1", status="active")

    class Offline:
        model = "offline"

        def embed(self, texts):
            raise EmbeddingUnavailable("offline")

    result = store.search("atomic rename", embedder=Offline())
    assert result["mode"] == "lexical_degraded"
    assert result["degraded_reason"] == "EmbeddingUnavailable"
    assert result["items"][0]["memory_id"] == memory["memory_id"]
    assert store.get_receipt(result["receipt_id"])["filters"]["mode"] == "lexical_degraded"


def test_context_budget_preserves_original_and_profile_configuration(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("memory:\n  nara_temporal:\n    embedding_model: embeddinggemma\n", encoding="utf-8")
    provider = NaraTemporalMemoryProvider()
    provider.initialize("session:1", nara_home=str(tmp_path))
    assert provider.embedder.model == "embeddinggemma"
    assert provider.embedder.url == "http://127.0.0.1:11434/api/embed"

    store = provider.store
    memory = store.add("Important decision: " + "archive " * 1200, layer="semantic",
                       source_type="user", source_ref="session:1", status="active")
    result = store.search("important decision archive", max_chars=512)
    assert result["items"][0]["truncated"] is True
    assert len(result["items"][0]["content"]) == 512
    assert len(store.get(memory["memory_id"])["content"]) > 512
    assert store.get_receipt(result["receipt_id"])["reasons"][memory["memory_id"]]["truncated"] is True


def test_provider_setup_persists_embedding_model_in_selected_profile(tmp_path):
    provider = NaraTemporalMemoryProvider()
    provider.save_config({"embedding_model": "embeddinggemma",
                          "embedding_url": "http://127.0.0.1:11434"}, str(tmp_path))
    provider.initialize("session:1", nara_home=str(tmp_path))
    assert provider.embedder.model == "embeddinggemma"
    assert "embedding_model: embeddinggemma" in (tmp_path / "config.yaml").read_text()


def test_ollama_embed_contract_uses_retrieval_prompts_on_loopback():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append((self.path, body))
            payload = json.dumps({"embeddings": [[3.0, 4.0] for _ in body["input"]]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        embedder = OllamaEmbedder("embeddinggemma", f"http://127.0.0.1:{server.server_port}")
        assert embedder.embed_query("Onde está a fonte?") == [0.6, 0.8]
        assert embedder.embed_documents(["Fonte original"])[0] == [0.6, 0.8]
        assert received[0][0] == "/api/embed"
        assert received[0][1]["input"] == ["task: search result | query: Onde está a fonte?"]
        assert received[1][1]["input"] == ["title: none | text: Fonte original"]
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
