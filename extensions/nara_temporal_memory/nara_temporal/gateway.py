"""Authenticated local API and MCP projection of the canonical temporal store."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import LAYERS, TemporalMemoryStore

try:
    from mcp.server.mcpserver import Context
except ImportError:  # Memory provider can run without the optional MCP transport.
    Context = Any


@dataclass(frozen=True)
class MemoryClient:
    client_id: str
    token_hash: str
    scope: str
    permissions: frozenset[str]


def load_clients(path: Path) -> list[MemoryClient]:
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise ValueError("memory gateway clients file must be readable only by its owner (chmod 600)")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("clients"), list):
        raise ValueError("clients file must contain a clients array")
    clients = []
    for entry in raw["clients"]:
        if not isinstance(entry, dict):
            raise ValueError("each client must be an object")
        client_id = entry.get("id")
        token_hash = entry.get("token_sha256")
        scope = entry.get("scope")
        permissions = entry.get("permissions")
        if not isinstance(client_id, str) or not client_id or any(c.isspace() for c in client_id):
            raise ValueError("client id must be a non-empty word")
        if not isinstance(token_hash, str) or len(token_hash) != 64 or any(c not in "0123456789abcdef" for c in token_hash):
            raise ValueError(f"client {client_id} requires a lowercase SHA-256 token hash")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError(f"client {client_id} requires a scope")
        if not isinstance(permissions, list) or not permissions or not set(permissions) <= {"read", "propose"}:
            raise ValueError(f"client {client_id} permissions must be read and/or propose")
        clients.append(MemoryClient(client_id, token_hash, scope, frozenset(permissions)))
    if len({item.client_id for item in clients}) != len(clients):
        raise ValueError("duplicate memory gateway client id")
    if len({item.token_hash for item in clients}) != len(clients):
        raise ValueError("duplicate memory gateway token")
    return clients


class MemoryGateway:
    def __init__(self, store: TemporalMemoryStore, clients: list[MemoryClient], embedder=None):
        self.store = store
        self.clients = clients
        self.embedder = embedder

    def authenticate(self, authorization: str | None) -> MemoryClient | None:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        digest = hashlib.sha256(authorization[7:].encode("utf-8")).hexdigest()
        for client in self.clients:
            if hmac.compare_digest(digest, client.token_hash):
                return client
        return None

    @staticmethod
    def require(client: MemoryClient, permission: str) -> None:
        if permission not in client.permissions:
            raise PermissionError(f"client lacks {permission} permission")

    def search(self, client: MemoryClient, query: str, *, layer: str | None = None,
               limit: int = 8, max_chars: int = 6000) -> dict[str, Any]:
        self.require(client, "read")
        if layer is not None and layer not in LAYERS:
            raise ValueError("unknown memory layer")
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        if not 512 <= max_chars <= 24_000:
            raise ValueError("max_chars must be between 512 and 24000")
        return self.store.search(query, session_id=f"memory-gateway:{client.client_id}",
                                 layer=layer, scope=client.scope, limit=limit, embedder=self.embedder,
                                 max_chars=max_chars)

    def get(self, client: MemoryClient, memory_id: str) -> dict[str, Any]:
        self.require(client, "read")
        item = self.store.get(memory_id)
        if item["scope"] != client.scope:
            raise KeyError(memory_id)
        if item["status"] != "active" and not (
            item["status"] == "candidate" and item["source_type"] == "memory_gateway"
            and item["source_ref"] == f"client:{client.client_id}"
        ):
            raise KeyError(memory_id)
        item["superseded_by"] = [
            successor_id for successor_id in item["superseded_by"]
            if (successor := self.store.get(successor_id))["scope"] == client.scope
            and (successor["status"] == "active"
                 or (successor["status"] == "candidate" and successor["source_type"] == "memory_gateway"
                     and successor["source_ref"] == f"client:{client.client_id}"))
        ]
        return item

    def propose(self, client: MemoryClient, content: str, layer: str, source_ref: str,
                *, source_type: str = "external", mission_id: str | None = None,
                confidence: float = 0.7) -> dict[str, Any]:
        self.require(client, "propose")
        if layer not in LAYERS or not source_ref.strip() or not source_type.strip():
            raise ValueError("valid layer and source provenance are required")
        return self.store.add(content, layer=layer, source_type="memory_gateway",
                              source_ref=f"client:{client.client_id}", mission_id=mission_id,
                              session_id=f"memory-gateway:{client.client_id}", scope=client.scope,
                              confidence=confidence, status="candidate",
                              metadata={"client_id": client.client_id, "external_source_type": source_type,
                                        "external_source_ref": source_ref})

    def correct(self, client: MemoryClient, memory_id: str, content: str, source_ref: str,
                *, source_type: str = "external") -> dict[str, Any]:
        self.require(client, "propose")
        self.require(client, "read")
        previous = self.get(client, memory_id)
        if not source_ref.strip() or not source_type.strip():
            raise ValueError("source provenance is required")
        return self.store.add(content, layer=previous["layer"], source_type="memory_gateway",
                              source_ref=f"client:{client.client_id}",
                              session_id=f"memory-gateway:{client.client_id}", scope=client.scope,
                              supersedes_id=memory_id, status="candidate",
                              metadata={"client_id": client.client_id, "external_source_type": source_type,
                                        "external_source_ref": source_ref})

    def receipt(self, client: MemoryClient, receipt_id: str) -> dict[str, Any]:
        self.require(client, "read")
        result = self.store.get_receipt(receipt_id)
        if result["session_id"] != f"memory-gateway:{client.client_id}" or result["filters"]["scope"] != client.scope:
            raise KeyError(receipt_id)
        return result


def create_app(gateway: MemoryGateway, *, host: str = "127.0.0.1"):
    """Create one ASGI app; the bearer gate covers MCP initialization and API routes."""
    from mcp.server.mcpserver import MCPServer
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response

    server = MCPServer("nara-memory-gateway")

    def mcp_client(ctx: Context) -> MemoryClient:
        request = ctx.request_context.request
        client = gateway.authenticate(request.headers.get("authorization"))
        if client is None:
            raise PermissionError("unauthorized memory gateway client")
        return client

    @server.tool(name="memory_search", description="Search current scoped memories and return a retrieval receipt")
    def memory_search(query: str, ctx: Context, layer: str | None = None,
                      limit: int = 8, max_chars: int = 6000) -> dict[str, Any]:
        return gateway.search(mcp_client(ctx), query, layer=layer, limit=limit, max_chars=max_chars)

    @server.tool(name="memory_get", description="Read the original memory, provenance and correction chain")
    def memory_get(memory_id: str, ctx: Context) -> dict[str, Any]:
        return gateway.get(mcp_client(ctx), memory_id)

    @server.tool(name="memory_propose", description="Submit an inactive, attributed memory candidate")
    def memory_propose(content: str, layer: str, source_ref: str, ctx: Context,
                       source_type: str = "external", mission_id: str | None = None,
                       confidence: float = 0.7) -> dict[str, Any]:
        return gateway.propose(mcp_client(ctx), content, layer, source_ref,
                               source_type=source_type, mission_id=mission_id, confidence=confidence)

    @server.tool(name="memory_correct", description="Submit an inactive correction linked to an original")
    def memory_correct(memory_id: str, content: str, source_ref: str, ctx: Context,
                       source_type: str = "external") -> dict[str, Any]:
        return gateway.correct(mcp_client(ctx), memory_id, content, source_ref, source_type=source_type)

    @server.tool(name="memory_receipt", description="Explain a retrieval made by this client")
    def memory_receipt(receipt_id: str, ctx: Context) -> dict[str, Any]:
        return gateway.receipt(mcp_client(ctx), receipt_id)

    async def api(request: Request) -> Response:
        client = gateway.authenticate(request.headers.get("authorization"))
        if client is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            operation = request.path_params["operation"]
            if request.method == "POST":
                body = await request.body()
                if len(body) > 65536:
                    return JSONResponse({"error": "request too large"}, status_code=413)
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError("request body must be an object")
                if operation == "search":
                    result = gateway.search(client, str(data["query"]), layer=data.get("layer"),
                                            limit=int(data.get("limit", 8)),
                                            max_chars=int(data.get("max_chars", 6000)))
                elif operation == "propose":
                    result = gateway.propose(client, str(data["content"]), str(data["layer"]),
                                             str(data["source_ref"]), source_type=str(data.get("source_type", "external")),
                                             mission_id=data.get("mission_id"), confidence=float(data.get("confidence", 0.7)))
                elif operation == "correct":
                    result = gateway.correct(client, str(data["memory_id"]), str(data["content"]),
                                             str(data["source_ref"]), source_type=str(data.get("source_type", "external")))
                else:
                    return JSONResponse({"error": "unknown operation"}, status_code=404)
            elif operation == "get":
                result = gateway.get(client, request.path_params["item_id"])
            elif operation == "receipt":
                result = gateway.receipt(client, request.path_params["item_id"])
            else:
                return JSONResponse({"error": "unknown operation"}, status_code=404)
            return JSONResponse(result)
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=403)
        except KeyError:
            return JSONResponse({"error": "not found"}, status_code=404)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    for path, methods in (("/v1/memory/{operation}", ["POST"]),
                          ("/v1/memory/{operation}/{item_id}", ["GET"])):
        server.custom_route(path, methods, include_in_schema=False)(api)

    app = server.streamable_http_app(streamable_http_path="/mcp", json_response=True,
                                     stateless_http=True, host=host)

    async def authenticated(scope, receive, send):
        if scope["type"] == "http":
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            authorization = headers.get(b"authorization", b"").decode("utf-8", errors="replace")
            if gateway.authenticate(authorization) is None:
                response = JSONResponse({"error": "unauthorized"}, status_code=401)
                await response(scope, receive, send)
                return
        await app(scope, receive, send)

    return authenticated


def serve_cli(args) -> None:
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("memory gateway binds to loopback only; use an SSH tunnel for remote access")
    from nara_constants import get_nara_home
    import uvicorn

    home = get_nara_home()
    store = TemporalMemoryStore(home / "memories" / "nara-temporal.db")
    from .embedding import configured_embedder
    app = create_app(MemoryGateway(store, load_clients(args.clients_file), configured_embedder(home)), host=args.host)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
