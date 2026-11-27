"""Specialist, skill, competence, and model resolution for dynamic worker plans."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from nara_cli.config import load_config
from nara_constants import get_nara_home
from plugins.mission_control.competence import CompetenceRegistry


TOKEN_RE = re.compile(r"[\wÀ-ÿ-]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    stop = {"para", "com", "uma", "que", "por", "dos", "das", "the", "and", "from", "como"}
    return {token.casefold() for token in TOKEN_RE.findall(text) if len(token) > 2 and token.casefold() not in stop}


def configured_legiao_path() -> Path | None:
    explicit = os.environ.get("NARA_LEGIAO_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    try:
        config = load_config() or {}
        block = ((config.get("plugins") or {}).get("mission_control") or {})
        value = str(block.get("legiao_path") or "").strip()
        return Path(value).expanduser() if value else None
    except Exception:
        return None


@dataclass(frozen=True)
class SpecialistCandidate:
    specialist_id: str
    name: str
    source: str
    summary: str
    category: str
    score: float
    prompt_hash: str
    orchestrator: bool = False
    chains: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelCandidate:
    provider: str
    model: str
    supports_tools: bool
    supports_vision: bool | None
    supports_reasoning: bool | None
    context_window: int
    observed_score: float | None = None
    performance: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LegiaoCatalog:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.agents_path = self.root / "data" / "agents.json"
        self.commands_path = self.root / "data" / "commands.json"

    def available(self) -> bool:
        return self.agents_path.is_file() and self.commands_path.is_file()

    def _data(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        agents_payload = json.loads(self.agents_path.read_text(encoding="utf-8-sig"))
        commands_payload = json.loads(self.commands_path.read_text(encoding="utf-8-sig"))
        agents = list(agents_payload.get("agents") or [])
        commands = {str(item["name"]): item for item in commands_payload.get("commands") or []}
        return agents, commands

    def search(self, task: str, *, limit: int = 5) -> list[SpecialistCandidate]:
        if not self.available():
            return []
        query = _tokens(task)
        agents, commands = self._data()
        candidates = []
        for agent in agents:
            command = commands.get(str(agent.get("id")))
            if command is None:
                continue
            haystack = " ".join(str(agent.get(key) or "") for key in (
                "nome", "categoria", "especialista", "resumo", "pedido"))
            terms = _tokens(haystack)
            overlap = len(query & terms)
            phrase_bonus = sum(token in haystack.casefold() for token in query) * 0.15
            score = overlap / max(1, len(query)) + phrase_bonus
            if score <= 0:
                continue
            instructions = str(command.get("instructions") or "")
            candidates.append(SpecialistCandidate(
                specialist_id=str(agent["id"]), name=str(agent.get("nome") or agent["id"]),
                source="legiao", summary=str(agent.get("resumo") or command.get("description") or ""),
                category=str(agent.get("categoria") or ""), score=round(score, 6),
                prompt_hash=hashlib.sha256(instructions.encode()).hexdigest(),
                orchestrator=bool(agent.get("orquestrador")),
                chains=tuple(str(item) for item in agent.get("encadeia") or ()),
            ))
        return sorted(candidates, key=lambda item: (-item.score, item.specialist_id))[:limit]

    def get(self, specialist_id: str) -> dict[str, Any]:
        agents, commands = self._data()
        agent = next((item for item in agents if str(item.get("id")) == specialist_id), None)
        command = commands.get(specialist_id)
        if agent is None or command is None:
            raise KeyError(specialist_id)
        instructions = str(command.get("instructions") or "")
        return {
            "specialist_id": specialist_id, "metadata": agent,
            "description": command.get("description"), "instructions": instructions,
            "prompt_hash": hashlib.sha256(instructions.encode()).hexdigest(),
        }

    def stats(self) -> dict[str, Any]:
        if not self.available():
            return {"available": False, "root": str(self.root), "agents": 0, "commands": 0}
        agents, commands = self._data()
        return {
            "available": True, "root": str(self.root), "agents": len(agents),
            "commands": len(commands),
            "orchestrators": sum(bool(item.get("orquestrador")) for item in agents),
        }


class SkillCatalog:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def search(self, task: str, *, limit: int = 5) -> list[SpecialistCandidate]:
        query = _tokens(task)
        result = []
        for path in sorted(self.root.glob("*/SKILL.md")) if self.root.is_dir() else ():
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            head = text[:4000]
            overlap = len(query & _tokens(head))
            if overlap == 0:
                continue
            skill_id = path.parent.name
            result.append(SpecialistCandidate(
                specialist_id=skill_id, name=skill_id, source="skill",
                summary=" ".join(head.splitlines()[:8])[:800], category="skill",
                score=overlap / max(1, len(query)),
                prompt_hash=hashlib.sha256(text.encode()).hexdigest(),
            ))
        return sorted(result, key=lambda item: (-item.score, item.specialist_id))[:limit]

    def get(self, specialist_id: str) -> dict[str, Any]:
        path = self.root / specialist_id / "SKILL.md"
        text = path.read_text(encoding="utf-8-sig")
        return {
            "specialist_id": specialist_id, "instructions": text,
            "prompt_hash": hashlib.sha256(text.encode()).hexdigest(), "path": str(path),
        }


class ModelCapabilityRegistry:
    def __init__(self, candidates: Iterable[ModelCandidate] | None = None):
        self._candidates = list(candidates) if candidates is not None else self._configured()

    def _configured(self) -> list[ModelCandidate]:
        config = load_config() or {}
        model_cfg = config.get("model") or {}
        delegation = config.get("delegation") or {}
        if str(delegation.get("backend") or "").strip().casefold() == "nara-measured":
            from plugins.mission_control.measured_delegation import measured_candidates

            return measured_candidates(delegation)
        routes = {
            (str(model_cfg.get("provider") or ""), str(model_cfg.get("default") or "")),
            (str(delegation.get("provider") or ""), str(delegation.get("model") or "")),
        }
        result = []
        for provider, model in sorted(routes):
            if not model:
                continue
            try:
                from agent.models_dev import get_model_capabilities
                capabilities = get_model_capabilities(provider, model, allow_network=False)
            except Exception:
                capabilities = None
            result.append(ModelCandidate(
                provider=provider or "configured", model=model,
                supports_tools=bool(getattr(capabilities, "supports_tools", True)),
                supports_vision=getattr(capabilities, "supports_vision", None),
                supports_reasoning=getattr(capabilities, "supports_reasoning", None),
                context_window=int(getattr(capabilities, "context_window", 0) or 0),
            ))
        return result

    def select(
        self, *, requires_tools: bool, requires_vision: bool, min_context: int = 0,
        category: str | None = None, benchmark_scope: str | None = None,
    ) -> ModelCandidate | None:
        eligible = [item for item in self._candidates if (
            (not requires_tools or item.supports_tools)
            and (not requires_vision or item.supports_vision is True)
            and item.context_window >= min_context
        )]
        if category is not None:
            from plugins.mission_control.model_performance import ModelPerformance

            measured = {(row['provider'], row['model']): row for row in
                        ModelPerformance.open_default().summaries(category, benchmark_scope)}
            eligible = [replace(item, observed_score=measured[(item.provider, item.model)]['success_rate'],
                                performance=measured[(item.provider, item.model)])
                        if (item.provider, item.model) in measured else item for item in eligible]
        return max(eligible, key=_model_rank, default=None)

    def inventory(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._candidates]


def _model_rank(item):
    performance = item.performance or {}
    cost = performance.get('mean_cost_usd')
    duration = performance.get('mean_duration_ms')
    return (item.observed_score if item.observed_score is not None else -1,
            performance.get('mean_score') if performance.get('mean_score') is not None else -1,
            -cost if cost is not None else float('-inf'),
            -duration if duration is not None else float('-inf'),
            item.supports_reasoning is True, item.context_window)


@dataclass(frozen=True)
class WorkerPlan:
    worker_id: str
    mission_id: str
    task_id: str
    role: str
    specialist_source: str | None
    specialist_id: str | None
    prompt_hash: str | None
    provider: str | None
    model: str | None
    tools: tuple[str, ...]
    budget_usd: float
    decision_id: str
    category: str | None = None
    model_evidence_json: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentFactory:
    def __init__(self, resolver: SpecialistResolver):
        self.resolver = resolver

    def plan(
        self, *, mission_id: str, task_id: str, task: str, tools: Iterable[str] = (),
        budget_usd: float = 0.0, requires_vision: bool = False,
        category: str | None = None, benchmark_scope: str | None = None,
    ) -> WorkerPlan:
        tools = tuple(tools)
        decision = self.resolver.resolve(
            task, requires_tools=bool(tools), requires_vision=requires_vision,
            category=category, benchmark_scope=benchmark_scope)
        selected = decision["selected"] or {}
        model = decision["model"] or {}
        identity = hashlib.sha256(
            f"{mission_id}\0{task_id}\0{decision['decision_id']}".encode()).hexdigest()[:16]
        return WorkerPlan(
            worker_id=f"worker:{identity}", mission_id=mission_id, task_id=task_id,
            role=(selected.get("name") or "Nara leader"),
            specialist_source=selected.get("source"), specialist_id=selected.get("specialist_id"),
            prompt_hash=selected.get("prompt_hash"), provider=model.get("provider"),
            model=model.get("model"), tools=tuple(tools), budget_usd=max(0.0, float(budget_usd)),
            decision_id=decision["decision_id"], category=category,
            model_evidence_json=json.dumps(model["performance"], sort_keys=True) if model.get("performance") else None,
        )


class SpecialistResolver:
    def __init__(
        self,
        *,
        legiao: LegiaoCatalog | None,
        skills: SkillCatalog,
        competence: CompetenceRegistry,
        models: ModelCapabilityRegistry,
    ):
        self.legiao = legiao
        self.skills = skills
        self.competence = competence
        self.models = models

    @classmethod
    def open_default(cls) -> SpecialistResolver:
        path = configured_legiao_path()
        return cls(
            legiao=LegiaoCatalog(path) if path else None,
            skills=SkillCatalog(get_nara_home() / "skills"),
            competence=CompetenceRegistry.open_default(), models=ModelCapabilityRegistry())

    def resolve(
        self, task: str, *, requires_tools: bool = True, requires_vision: bool = False,
        min_context: int = 0, max_candidates: int = 5,
        category: str | None = None, benchmark_scope: str | None = None,
    ) -> dict[str, Any]:
        candidates = self.skills.search(task, limit=max_candidates)
        if self.legiao is not None:
            candidates.extend(self.legiao.search(task, limit=max_candidates))
        task_tokens = _tokens(task)
        observed_competence = [item for item in self.competence.current() if (
            task_tokens & _tokens(item["category"] + " " + json.dumps(item["system"], ensure_ascii=False))
        )]

        def _effective(item: SpecialistCandidate) -> float:
            bonus = max((
                float(observed["best_score"]) * 0.2
                for observed in observed_competence
                if item.specialist_id.casefold() in json.dumps(observed["system"]).casefold()
            ), default=0.0)
            return item.score + bonus

        candidates = sorted(
            candidates, key=lambda item: (-_effective(item), item.source, item.specialist_id))
        unique: dict[tuple[str, str], SpecialistCandidate] = {}
        for item in candidates:
            unique.setdefault((item.source, item.specialist_id), item)
        selected_candidates = list(unique.values())[:max_candidates]
        model = self.models.select(
            requires_tools=requires_tools, requires_vision=requires_vision, min_context=min_context,
            category=category, benchmark_scope=benchmark_scope)
        selected = selected_candidates[0] if selected_candidates and selected_candidates[0].score >= 0.2 else None
        decision = "specialist" if selected else "leader"
        receipt = hashlib.sha256(json.dumps({
            "task": task, "category": category, "benchmark_scope": benchmark_scope, "candidates": [item.to_dict() for item in selected_candidates],
            "model": model.to_dict() if model else None, "decision": decision,
        }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
        return {
            "decision_id": receipt, "decision": decision, "category": category,
            "model_basis": "verified_category_benchmark" if model and model.performance else "capability_fallback",
            "selected": selected.to_dict() if selected else None,
            "model": model.to_dict() if model else None,
            "candidates": [item.to_dict() for item in selected_candidates],
            "observed_competence": observed_competence,
            "legiao": self.legiao.stats() if self.legiao else {"available": False},
            "reason": (
                "best matching specialist exceeded the routing threshold"
                if selected else "no specialist demonstrated enough relevance; keep the task with the leader"),
        }

    def load_selected(self, source: str, specialist_id: str) -> dict[str, Any]:
        if source == "legiao" and self.legiao is not None:
            return self.legiao.get(specialist_id)
        if source == "skill":
            return self.skills.get(specialist_id)
        raise KeyError(f"unknown specialist source: {source}")


def pre_llm_specialist_context(user_message: Any = "", **_: Any) -> dict[str, str] | None:
    task = str(user_message or "").strip()
    if len(task) < 12:
        return None
    decision = SpecialistResolver.open_default().resolve(task, max_candidates=3)
    if decision["decision"] == "leader" and not decision["candidates"]:
        return None
    rows = [{
        "id": item["specialist_id"], "name": item["name"], "source": item["source"],
        "category": item["category"], "score": item["score"],
    } for item in decision["candidates"]]
    return {"context": (
        "[Nara Specialist Resolver — metadata only]\n"
        f"decision_id={decision['decision_id']} decision={decision['decision']}\n"
        f"candidates={json.dumps(rows, ensure_ascii=False)}\n"
        "For a simple task, continue as leader. If specialization improves the mission, call "
        "nara_specialist_get for exactly one chosen candidate before delegating."
    )}


SPECIALIST_RESOLVE_SCHEMA = {
    "name": "nara_specialist_resolve",
    "description": "Resolve a task across Legiao, installed skills, observed competence, and configured models before creating workers.",
    "parameters": {"type": "object", "properties": {
        "task": {"type": "string"}, "requires_tools": {"type": "boolean"},
        "requires_vision": {"type": "boolean"}, "min_context": {"type": "integer"},
        "category": {"type": "string", "description": "Exact measured task category, if known"},
        "benchmark_scope": {"type": "string", "description": "Optional frozen comparison cohort hash"},
    }, "required": ["task"]},
}

SPECIALIST_GET_SCHEMA = {
    "name": "nara_specialist_get",
    "description": "Load the full instructions only for the specialist selected by the resolver.",
    "parameters": {"type": "object", "properties": {
        "source": {"type": "string", "enum": ["legiao", "skill"]},
        "specialist_id": {"type": "string"},
    }, "required": ["source", "specialist_id"]},
}


def specialist_resolve_tool(
    task: str, requires_tools: bool = True, requires_vision: bool = False,
    min_context: int = 0, category: str | None = None, benchmark_scope: str | None = None, **_: Any,
) -> dict[str, Any]:
    return SpecialistResolver.open_default().resolve(
        task, requires_tools=requires_tools, requires_vision=requires_vision,
        min_context=min_context, category=category, benchmark_scope=benchmark_scope)


def specialist_get_tool(source: str, specialist_id: str, **_: Any) -> dict[str, Any]:
    return SpecialistResolver.open_default().load_selected(source, specialist_id)
