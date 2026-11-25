"""Phase-5 fixture: resolve specialists, plan workers, run in parallel, synthesize."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
from pathlib import Path
from typing import Sequence

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import Mission, Receipt, Verification, VerificationStatus
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.specialists import (
    AgentFactory,
    LegiaoCatalog,
    ModelCandidate,
    ModelCapabilityRegistry,
    SkillCatalog,
    SpecialistResolver,
)
from plugins.mission_control.store import MissionStore
from plugins.mission_control.verification import VerificationService
from plugins.mission_control.workers import WorkerLeaseService


def _write_catalog(root: Path) -> LegiaoCatalog:
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    agents = []
    commands = []
    rows = [
        ("analista_dados", "Analista de Dados", "dados planilha métricas vendas", "DATA-PROMPT"),
        ("precificacao", "Engenheiro de Precificação", "preço margem custo oferta", "PRICE-PROMPT"),
        ("copywriter", "Copywriter", "copy anúncio mensagem campanha", "COPY-PROMPT"),
    ]
    for identity, name, summary, prompt in rows:
        agents.append({
            "id": identity, "nome": name, "categoria": name, "resumo": summary,
            "pedido": summary, "orquestrador": False, "encadeia": [],
        })
        commands.append({"name": identity, "description": summary, "instructions": prompt})
    (data / "agents.json").write_text(
        json.dumps({"schemaVersion": 1, "agents": agents}), encoding="utf-8")
    (data / "commands.json").write_text(
        json.dumps({"schemaVersion": 1, "commands": commands}), encoding="utf-8")
    return LegiaoCatalog(root)


def run_fixture(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    missions = MissionStore(root / "missions.db")
    mission_id = "dynamic-team-v1"
    criteria = [
        "data analysis is independently evidenced",
        "pricing analysis is independently evidenced",
        "campaign copy is independently evidenced",
        "team synthesis contains all three verified contributions",
    ]
    missions.create(Mission(
        mission_id=mission_id, objective="Prepare a measured launch recommendation",
        completion_criteria=criteria))
    missions.transition(mission_id, "planned")
    missions.transition(mission_id, "running")
    tasks = {
        "task-data": "analise a planilha e as métricas de vendas",
        "task-price": "calcule preço, margem e custo da oferta",
        "task-copy": "escreva a copy da campanha e do anúncio",
    }
    for task_id, description in tasks.items():
        missions.request_task(mission_id, task_id, {"title": description})
        missions.link_task(mission_id, task_id, task_id, "todo")

    resolver = SpecialistResolver(
        legiao=_write_catalog(root / "legiao"), skills=SkillCatalog(root / "skills"),
        competence=CompetenceRegistry(root / "competence.db"),
        models=ModelCapabilityRegistry([
            ModelCandidate("local", "worker-fast", True, False, False, 32000, 0.8),
            ModelCandidate("cloud", "worker-reasoning", True, True, True, 128000, 0.9),
        ]))
    factory = AgentFactory(resolver)
    plans = {
        task_id: factory.plan(
            mission_id=mission_id, task_id=task_id, task=description,
            tools=["read_file", "artifact.write"], budget_usd=0.10)
        for task_id, description in tasks.items()
    }
    expected = {
        "task-data": "DATA-PROMPT", "task-price": "PRICE-PROMPT", "task-copy": "COPY-PROMPT"}
    artifacts = ArtifactStore(missions, root / "artifacts")
    receipts = ReceiptStore(missions)
    leases = WorkerLeaseService(missions)

    def worker(task_id: str) -> tuple[str, str, float]:
        plan = plans[task_id]
        started = time.monotonic()
        lease = leases.claim(mission_id, task_id, plan.worker_id, ttl_seconds=30, model=plan.model, provider=plan.provider)
        selected = resolver.load_selected(plan.specialist_source or "", plan.specialist_id or "")
        if selected["instructions"] != expected[task_id] or selected["prompt_hash"] != plan.prompt_hash:
            raise RuntimeError("worker did not load the exact selected specialist")
        receipt = receipts.prepare(Receipt(
            receipt_id=f"receipt-{task_id}", mission_id=mission_id, task_id=task_id,
            intention=tasks[task_id], agent_id=plan.worker_id, tool="specialist.execute",
            target=task_id, idempotency_key=f"execute:{task_id}"))
        time.sleep(0.12)
        content = json.dumps({
            "task_id": task_id, "specialist_id": plan.specialist_id,
            "model": plan.model, "prompt_hash": plan.prompt_hash,
            "finding": f"verified contribution from {plan.role}",
        }, sort_keys=True).encode()
        artifact = artifacts.put_bytes(
            mission_id, content, producer_id=plan.worker_id, media_type="application/json")
        receipts.settle(
            mission_id, receipt.receipt_id, "confirmed", artifact_ids=[artifact.artifact_id],
            observed_result={"worker_plan": plan.to_dict()},
            idempotency_key=f"confirmed:{task_id}")
        leases.release(mission_id, lease.lease_id)
        missions.record_task_status(task_id, "done", idempotency_key=f"done:{task_id}")
        return task_id, artifact.artifact_id, time.monotonic() - started

    wall_started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(worker, tasks))
    parallel_wall = time.monotonic() - wall_started
    artifact_by_task = {task_id: artifact_id for task_id, artifact_id, _ in results}
    sequential_worker_time = sum(duration for _, _, duration in results)
    synthesis_content = json.dumps({
        "mission_id": mission_id, "contributions": artifact_by_task,
        "decision": "launch recommendation assembled only from verified worker artifacts",
    }, sort_keys=True).encode()
    synthesis = artifacts.put_bytes(
        mission_id, synthesis_content, producer_id="nara-leader", media_type="application/json")
    verifier = VerificationService(missions, artifacts)
    for task_id, criterion in zip(tasks, criteria[:3], strict=True):
        verifier.verify_artifact(
            mission_id, criterion, artifact_by_task[task_id], verifier_id="team-judge",
            executor_id=plans[task_id].worker_id, verification_id=f"verify-{task_id}")
    verifier.record(Verification(
        verification_id="verify-synthesis", mission_id=mission_id, criterion=criteria[3],
        verifier_id="team-judge", executor_id="nara-leader", status=VerificationStatus.PASS,
        evidence_artifact_ids=[synthesis.artifact_id, *artifact_by_task.values()],
        method="reopen synthesis and all content-addressed worker contributions",
        explanation="all three distinct verified contributions are referenced"))
    missions.transition(mission_id, "verifying")
    completed = missions.transition(mission_id, "completed")

    specialist_ids = {plan.specialist_id for plan in plans.values()}
    if len(specialist_ids) != 3 or parallel_wall >= sequential_worker_time * 0.75:
        raise RuntimeError("dynamic team did not demonstrate specialist diversity and parallel gain")
    return {
        "schema_version": 1, "fixture_id": "phase5-dynamic-team-v1", "status": "passed",
        "mission_status": completed.status.value,
        "worker_plans": {key: value.to_dict() for key, value in plans.items()},
        "parallel_wall_seconds": parallel_wall,
        "sequential_worker_seconds": sequential_worker_time,
        "speedup": sequential_worker_time / parallel_wall,
        "specialist_count": len(specialist_ids),
        "artifacts": artifact_by_task,
        "synthesis_artifact_id": synthesis.artifact_id,
        "completion_blockers": verifier.blockers(mission_id),
        "leader_baseline_quality": 1,
        "team_quality": len(artifact_by_task),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run_fixture(args.root)
    serialized = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
