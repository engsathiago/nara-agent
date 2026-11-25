from __future__ import annotations

import json

from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.specialists import (
    AgentFactory,
    LegiaoCatalog,
    ModelCandidate,
    ModelCapabilityRegistry,
    SkillCatalog,
    SpecialistResolver,
    pre_llm_specialist_context,
)


def _legiao(tmp_path):
    root = tmp_path / "legiao"
    (root / "data").mkdir(parents=True)
    agents = {"schemaVersion": 1, "agents": [
        {
            "id": "analista_dados", "nome": "Analista de Dados", "categoria": "Dados",
            "resumo": "Analisa planilha, dashboard e métricas para tomar decisão",
            "pedido": "quero entender minha planilha", "orquestrador": False, "encadeia": [],
        },
        {
            "id": "precificacao", "nome": "Engenheiro de Preço", "categoria": "Oferta",
            "resumo": "Calcula preço e margem", "pedido": "quanto devo cobrar",
            "orquestrador": False, "encadeia": [],
        },
    ]}
    commands = {"schemaVersion": 1, "commands": [
        {"name": "analista_dados", "description": "dados", "instructions": "SECRET-DATA-PROMPT"},
        {"name": "precificacao", "description": "preço", "instructions": "SECRET-PRICE-PROMPT"},
    ]}
    (root / "data" / "agents.json").write_text(json.dumps(agents), encoding="utf-8")
    (root / "data" / "commands.json").write_text(json.dumps(commands), encoding="utf-8")
    return LegiaoCatalog(root)


def _models():
    return ModelCapabilityRegistry([
        ModelCandidate("local", "text-small", True, False, False, 32000, 0.8),
        ModelCandidate("cloud", "vision-reasoning", True, True, True, 200000, 0.9),
    ])


def test_resolver_uses_metadata_then_loads_only_selected_prompt(tmp_path):
    resolver = SpecialistResolver(
        legiao=_legiao(tmp_path), skills=SkillCatalog(tmp_path / "skills"),
        competence=CompetenceRegistry(tmp_path / "competence.db"), models=_models())

    decision = resolver.resolve("analise minha planilha e o dashboard de vendas")
    serialized = json.dumps(decision)

    assert decision["decision"] == "specialist"
    assert decision["selected"]["specialist_id"] == "analista_dados"
    assert "SECRET-DATA-PROMPT" not in serialized
    loaded = resolver.load_selected("legiao", "analista_dados")
    assert loaded["instructions"] == "SECRET-DATA-PROMPT"
    assert loaded["prompt_hash"] == decision["selected"]["prompt_hash"]


def test_model_registry_respects_required_modalities(tmp_path):
    registry = _models()

    text = registry.select(requires_tools=True, requires_vision=False, min_context=1000)
    vision = registry.select(requires_tools=True, requires_vision=True, min_context=100000)

    assert text.model == "vision-reasoning"  # higher observed competence wins
    assert vision.model == "vision-reasoning"
    assert registry.select(requires_tools=True, requires_vision=True, min_context=300000) is None


def test_observed_specialist_competence_is_included_in_receipt(tmp_path):
    competence = CompetenceRegistry(tmp_path / "competence.db")
    competence.record_observation(
        "dados.planilha", {"skill": "analista_dados", "model": "vision-reasoning"}, 0.95,
        verified=True, evidence_artifact_ids=["sha256:proof"])
    resolver = SpecialistResolver(
        legiao=_legiao(tmp_path), skills=SkillCatalog(tmp_path / "skills"),
        competence=competence, models=_models())

    decision = resolver.resolve("analise dados da planilha")

    assert decision["observed_competence"][0]["state"] == "demonstrated"
    assert len(decision["decision_id"]) == 24


def test_agent_factory_emits_reproducible_bounded_worker_plan(tmp_path):
    resolver = SpecialistResolver(
        legiao=_legiao(tmp_path), skills=SkillCatalog(tmp_path / "skills"),
        competence=CompetenceRegistry(tmp_path / "competence.db"), models=_models())
    factory = AgentFactory(resolver)

    first = factory.plan(
        mission_id="mission-a", task_id="task-data", task="analise a planilha de vendas",
        tools=["read_file"], budget_usd=0.25)
    second = factory.plan(
        mission_id="mission-a", task_id="task-data", task="analise a planilha de vendas",
        tools=["read_file"], budget_usd=0.25)

    assert first == second
    assert first.specialist_id == "analista_dados"
    assert first.model == "vision-reasoning"
    assert first.budget_usd == 0.25


def test_pre_llm_hook_stays_out_of_simple_leader_turns(monkeypatch):
    class LeaderOnly:
        def resolve(self, *_args, **_kwargs):
            return {"decision": "leader", "candidates": []}

    monkeypatch.setattr(
        SpecialistResolver, "open_default", classmethod(lambda cls: LeaderOnly()))

    assert pre_llm_specialist_context(
        user_message="Responda somente: NARA_OK") is None
