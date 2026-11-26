"""End-to-end contract for two authenticated clients sharing one Nara memory store."""

import asyncio
import hashlib
import json
import os
import shutil
import socket
import sys
import threading
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from extensions.nara_temporal_memory.nara_temporal import TemporalMemoryStore
from extensions.nara_temporal_memory.nara_temporal.gateway import (
    MemoryGateway, create_app, load_clients,
)
from tests.waiting import wait_until


def _clients_file(tmp_path):
    path = tmp_path / "clients.json"
    path.write_text(json.dumps({"clients": [
        {"id": "codex", "token_sha256": hashlib.sha256(b"codex-secret").hexdigest(),
         "scope": "project:nara", "permissions": ["read", "propose"]},
        {"id": "claude", "token_sha256": hashlib.sha256(b"claude-secret").hexdigest(),
         "scope": "project:nara", "permissions": ["read"]},
        {"id": "other-project", "token_sha256": hashlib.sha256(b"other-secret").hexdigest(),
         "scope": "project:private", "permissions": ["read"]},
    ]}), encoding="utf-8")
    if os.name == "posix":
        path.chmod(0o600)
    return path


def test_gateway_api_shares_canonical_store_and_enforces_scopes(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memories" / "nara-temporal.db")
    original = store.add("Nara speaks Portuguese", layer="semantic", source_type="user",
                         source_ref="session:1", scope="project:nara", status="active")
    app = create_app(MemoryGateway(store, load_clients(_clients_file(tmp_path))))
    with TestClient(app) as client:
        assert client.post("/v1/memory/search", json={"query": "Portuguese"}).status_code == 401
        codex = {"Authorization": "Bearer codex-secret"}
        claude = {"Authorization": "Bearer claude-secret"}
        other = {"Authorization": "Bearer other-secret"}
        found = client.post("/v1/memory/search", headers=codex, json={"query": "Portuguese"})
        assert found.status_code == 200
        assert [item["memory_id"] for item in found.json()["items"]] == [original["memory_id"]]
        assert client.post("/v1/memory/search", headers=codex, json={
            "query": "Portuguese", "max_chars": 256,
        }).status_code == 400
        receipt_id = found.json()["receipt_id"]
        receipt = client.get(f"/v1/memory/receipt/{receipt_id}", headers=codex)
        assert receipt.json()["memory_ids"] == [original["memory_id"]]
        assert client.get(f"/v1/memory/receipt/{receipt_id}", headers=claude).status_code == 404
        assert client.get(f"/v1/memory/get/{original['memory_id']}", headers=other).status_code == 404

        proposed = client.post("/v1/memory/propose", headers=codex, json={
            "content": "Nara likes green", "layer": "semantic", "source_ref": "document:1",
        })
        assert proposed.status_code == 200
        candidate = proposed.json()
        assert candidate["status"] == "candidate"
        assert candidate["metadata"]["external_source_ref"] == "document:1"
        assert client.get(f"/v1/memory/get/{candidate['memory_id']}", headers=claude).status_code == 404
        assert client.post("/v1/memory/propose", headers=claude, json={
            "content": "no", "layer": "semantic", "source_ref": "x",
        }).status_code == 403

        corrected = client.post("/v1/memory/correct", headers=codex, json={
            "memory_id": original["memory_id"], "content": "Nara speaks Brazilian Portuguese",
            "source_ref": "document:2",
        })
        assert corrected.status_code == 200
        assert corrected.json()["supersedes_id"] == original["memory_id"]
        assert corrected.json()["status"] == "candidate"
        assert store.get(original["memory_id"])["valid_to"] is None
        assert corrected.json()["memory_id"] not in client.get(
            f"/v1/memory/get/{original['memory_id']}", headers=claude,
        ).json()["superseded_by"]
        assert client.post("/v1/memory/search", headers=claude, json={"query": "Portuguese"}).json()["items"][0]["memory_id"] == original["memory_id"]
        store.promote(corrected.json()["memory_id"])
        assert client.post("/v1/memory/search", headers=claude, json={"query": "Portuguese"}).json()["items"][0]["memory_id"] == corrected.json()["memory_id"]


def test_gateway_mcp_protocol_uses_same_store_and_requires_bearer(tmp_path):
    import httpx2
    import uvicorn
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    store = TemporalMemoryStore(tmp_path / "canonical.db")
    store.add("mission archive record", layer="semantic", source_type="user",
              source_ref="session:1", scope="project:nara", status="active")
    app = create_app(MemoryGateway(store, load_clients(_clients_file(tmp_path))))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                            log_level="error", lifespan="on"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        assert wait_until(lambda: server.started, timeout=10)

        async def exercise():
            url = f"http://127.0.0.1:{port}/mcp"
            async with httpx2.AsyncClient(headers={"Authorization": "Bearer codex-secret"}) as http:
                async with streamable_http_client(url, http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        assert {tool.name for tool in tools.tools} >= {
                            "memory_search", "memory_get", "memory_propose", "memory_correct", "memory_receipt",
                        }
                        result = await session.call_tool("memory_search", {"query": "archive", "max_chars": 512})
                        assert not result.is_error
                        assert result.structured_content["items"][0]["content"] == "mission archive record"
                        memory_id = result.structured_content["items"][0]["memory_id"]
            async with httpx2.AsyncClient(headers={"Authorization": "Bearer claude-secret"}) as http:
                async with streamable_http_client(url, http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        result = await session.call_tool("memory_get", {"memory_id": memory_id})
                        assert not result.is_error
                        assert result.structured_content["memory_id"] == memory_id
            async with httpx2.AsyncClient() as http:
                response = await http.post(url, json={"jsonrpc": "2.0", "id": 1,
                                                     "method": "initialize", "params": {}})
                assert response.status_code == 401

        asyncio.run(exercise())
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive()


def test_gateway_refuses_world_readable_token_configuration(tmp_path):
    path = _clients_file(tmp_path)
    if os.name != "posix":
        pytest.skip("POSIX file mode requirement")
    path.chmod(0o644)
    with pytest.raises(ValueError, match="chmod 600"):
        load_clients(path)


def test_installed_provider_registers_real_cli_command(tmp_path, monkeypatch, capsys):
    import extensions.nara_temporal_memory.nara_temporal as provider_source

    target = tmp_path / "plugins" / "nara_temporal"
    target.parent.mkdir()
    shutil.copytree(Path(provider_source.__file__).parent, target)
    (tmp_path / "config.yaml").write_text("memory:\n  provider: nara_temporal\n", encoding="utf-8")
    monkeypatch.setenv("NARA_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["nara", "nara_temporal", "serve"])
    from nara_cli.main import _build_cli_parser

    parser, _ = _build_cli_parser()
    args = parser.parse_args(["nara_temporal", "serve", "--clients-file", str(_clients_file(tmp_path))])
    assert callable(args.func)
    assert args.clients_file.name == "clients.json"
    import uvicorn

    served = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: served.append((app, kwargs)))
    args.func(args)
    assert len(served) == 1
    assert served[0][1]["host"] == "127.0.0.1"
    status_args = parser.parse_args(["nara_temporal", "status"])
    status_args.func(status_args)
    assert json.loads(capsys.readouterr().out)["health"] == "available"
