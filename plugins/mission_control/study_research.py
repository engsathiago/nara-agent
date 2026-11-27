"""Bounded source discovery through the host web tools, with mission evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import Mission, utc_now
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_github_source import _check_cited_source
from plugins.mission_control.verification import VerificationService


CRITERION = "Archive a retrieved source and its search and extraction provenance"


def research_options(objective, domains, max_sources, max_seconds):
    if not isinstance(objective, str) or not 1 <= len(objective.strip()) <= 1500:
        raise ValueError("research objective must contain 1-1500 characters")
    if isinstance(max_sources, bool) or not isinstance(max_sources, int) or not 1 <= max_sources <= 5:
        raise ValueError("research max-sources must be from 1 to 5")
    if not isinstance(max_seconds, (float, int)) or not 1 <= max_seconds <= 600:
        raise ValueError("research max-seconds must be from 1 to 600")
    domains = list(dict.fromkeys(domain.lower() for domain in domains))
    if len(domains) > 5 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", d) for d in domains):
        raise ValueError("research domains must be at most five public host names")
    return objective.strip(), domains


def selected_url(value, domains):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None, 443)):
            return None
    except ValueError:
        return None
    if domains and not any(parsed.hostname == d or parsed.hostname.endswith("." + d) for d in domains):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


class SourceResearch:
    def __init__(self, missions, fabric, dispatch, gap, objective, *, domains=(), max_sources=3, max_seconds=120):
        if dispatch is None:
            raise ValueError("web tool dispatch is unavailable on this surface")
        self.objective, self.domains = research_options(objective, domains, max_sources, max_seconds)
        self.missions, self.fabric, self.dispatch = missions, fabric, dispatch
        self.artifacts = ArtifactStore(missions, missions.path.parent / "artifacts")
        self.max_sources, self.deadline = max_sources, time.monotonic() + max_seconds
        self.mission_id = "source-research-" + uuid.uuid4().hex
        self.result = {
            "kind": "source_research", "schema_version": 1, "mission_id": self.mission_id,
            "gap_id": gap["gap_id"], "objective": self.objective, "domains": self.domains,
            "max_sources": max_sources, "max_seconds": max_seconds, "calls_started": 0,
            "sources": [], "rejected": [], "errors": [], "cost_unknown": False,
        }
        missions.create(Mission(
            mission_id=self.mission_id, objective="Research: " + self.objective,
            completion_criteria=[CRITERION], constraints={"gap_id": gap["gap_id"], "domains": self.domains},
            budget={"max_web_calls": 1 + max_sources, "max_seconds": max_seconds},
        ), actor_id="study-research")
        missions.transition(self.mission_id, "planned", actor_id="study-research")
        missions.transition(self.mission_id, "running", actor_id="study-research")
        self.budget_usd = gap["budget_usd"]

    def _archive(self, payload):
        return self.artifacts.put_bytes(
            self.mission_id, json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(),
            producer_id="study-research", media_type="application/json")

    def _call(self, name, args):
        if time.monotonic() >= self.deadline:
            raise ValueError("research deadline exhausted")
        self.result["calls_started"] += 1
        self.result["cost_unknown"] = True
        number = self.result["calls_started"]
        self.missions.record_diagnostic(self.mission_id, {
            "diagnostic_id": f"research-call-{number}", "kind": "research_call_started",
            "tool": name, "arguments": args, "call_number": number,
        }, idempotency_key=f"research-call-{number}")
        try:
            raw = self.dispatch(name, args)
        except Exception as exc:
            raise ValueError(f"web tool failed: {type(exc).__name__}") from exc
        if not isinstance(raw, str) or len(raw) > 1_000_000:
            raise ValueError("web tool response must be JSON text of at most 1 MB")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("web tool response must be a JSON object")
        receipt = self._archive({"kind": "research_tool_result", "tool": name, "arguments": args,
                                 "call_number": number, "observed_at": utc_now(), "result": payload})
        # Web dispatch currently exposes no priced-usage contract. Never claim
        # free research or spend an entire monetary budget on unpriced calls.
        if self.budget_usd is not None:
            raise ValueError("research cost is unverifiable for a monetary-budgeted gap")
        if payload.get("success") is False or payload.get("error"):
            raise ValueError("web tool reported unavailable or unsuccessful acquisition")
        return payload, receipt

    def _discover(self):
        scope = " OR ".join("site:" + domain for domain in self.domains)
        query = self.objective + (" (" + scope + ")" if scope else "")
        payload, receipt = self._call("web_search", {"query": query, "limit": 20})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("web search returned no structured result data")
        rows = data.get("web", [])
        if not isinstance(rows, list):
            raise ValueError("web search returned invalid result entries")
        selected = []
        for item in rows:
            value = item.get("url") if isinstance(item, dict) else None
            url = selected_url(value, self.domains)
            if url and url not in selected:
                selected.append(url)
            elif value:
                self.result["rejected"].append({"url": value, "reason": "outside scope, invalid or duplicate"})
        self.result["search_artifact_id"] = receipt.artifact_id
        return selected[:self.max_sources]

    def _extract(self, url):
        payload, receipt = self._call("web_extract", {"urls": [url], "char_limit": 48000})
        rows = payload.get("results", [])
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError("web extraction must return one result")
        row = rows[0]
        if row.get("error") or selected_url(row.get("url"), self.domains) != url:
            raise ValueError("web extraction failed or changed the selected URL")
        content = row.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("extracted source must contain nonempty text")
        # The host may append paging metadata beyond char_limit. Its complete
        # response is already archived; bound only the text supplied to study.
        window = {"start": 0, "end": min(len(content), 48000), "received_characters": len(content),
                  "received_sha256": hashlib.sha256(content.encode()).hexdigest(), "truncated": len(content) > 48000}
        content = content[:48000]
        if not content.strip():
            raise ValueError("extracted source window contains no usable text")
        with TemporaryDirectory(prefix="nara-research-") as temp:
            path = Path(temp) / "source.txt"
            path.write_text(content, encoding="utf-8")
            source = self.fabric.ingest_file(
                path, modality="site", source_uri=url,
                version="sha256:" + hashlib.sha256(content.encode()).hexdigest(),
                metadata={"acquisition": "host_web_extract", "retrieved_at": utc_now(),
                          "research_mission_id": self.mission_id, "claims_status": "unverified",
                          "search_artifact_id": self.result["search_artifact_id"],
                          "extraction_artifact_id": receipt.artifact_id, "text_window": window})
        _check_cited_source(source)
        return {"source_id": source["source_id"], "source_hash": source["source_hash"], "url": url,
                "extraction_artifact_id": receipt.artifact_id, "claims_status": "unverified"}

    def run(self):
        try:
            urls = self._discover()
            for url in urls:
                try:
                    self.result["sources"].append(self._extract(url))
                except (ValueError, OSError) as exc:
                    self.result["errors"].append({"url": url, "error": str(exc)})
                    if time.monotonic() >= self.deadline:
                        break
        except (ValueError, OSError) as exc:
            self.result["errors"].append({"error": str(exc)})
        self.result["status"] = "sources_found" if self.result["sources"] else "unresolved"
        receipt = self._archive(self.result)
        self.result["receipt"] = receipt.to_dict()
        if self.result["sources"]:
            VerificationService(self.missions, self.artifacts).verify_artifact(
                self.mission_id, CRITERION, receipt.artifact_id, verifier_id="source-archive-verifier",
                executor_id="study-research", verification_id="source-archive-proof")
            self.missions.transition(self.mission_id, "verifying", actor_id="study-research")
            self.missions.transition(self.mission_id, "completed", actor_id="study-research")
        else:
            self.missions.transition(self.mission_id, "failed", actor_id="study-research", reason="No source acquired")
        return self.result


def register_research_cli(actions):
    command = actions.add_parser("study-research", help="Discover and archive sources for a competence gap")
    command.add_argument("gap_id")
    command.add_argument("--objective", required=True)
    command.add_argument("--domain", action="append", default=[])
    command.add_argument("--max-sources", type=int, default=3)
    command.add_argument("--max-seconds", type=float, default=120)


def research_command(store, args, dispatch):
    gap = CompetenceRegistry.open_default().gap(args.gap_id)
    return SourceResearch(store, LearningFabric.open_default(), dispatch, gap, args.objective,
                          domains=args.domain, max_sources=args.max_sources, max_seconds=args.max_seconds).run()
