"""Frozen, local-model evaluator for a real video's office display convention.

No orders or market access. Expected answers stay outside the model prompt.
"""

import json
import urllib.request
from pathlib import Path

MODEL = "qwen3.5:4b"
ENDPOINT = "http://127.0.0.1:11434"


def evaluate(request):
    case = request["case"]
    candidate = request["candidate"]
    instructions = (
        "Produza os dados de exibição de um escritório virtual de robôs. "
        "Use os saldos fornecidos, mantendo IDs e valores numéricos. "
        "Escolha intervalo de atualização e posição do rótulo conforme seu conhecimento. "
        'Responda somente JSON com refresh_seconds (número) e labels '
        '(lista de objetos com id, balance e anchor: "above_character" ou "panel").'
    )
    if candidate is not None:
        instructions += "\nProcedimento estudado:\n" + "\n".join(candidate["steps"])
    body = {"model": MODEL, "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0, "seed": 42, "num_predict": 512},
            "messages": [{"role": "system", "content": instructions},
                         {"role": "user", "content": json.dumps(case["robots"], ensure_ascii=False)}]}
    with urllib.request.urlopen(ENDPOINT + "/api/tags", timeout=10) as response:
        models = json.load(response)["models"]
    model = next(row for row in models if row["name"] == MODEL)
    call = urllib.request.Request(ENDPOINT + "/api/chat", data=json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(call, timeout=100) as response:
        raw = json.load(response)
    content = raw.get("message", {}).get("content", "")
    try:
        answer = json.loads(content)
    except json.JSONDecodeError:
        answer = {}
    expected = [{"id": row["id"], "balance": row["balance"], "anchor": "above_character"}
                for row in case["robots"]]
    checks = {
        "refresh": isinstance(answer, dict) and answer.get("refresh_seconds") == 20,
        "labels": isinstance(answer, dict) and answer.get("labels") == expected,
    }
    evidence = {"case_id": case["case_id"], "model": MODEL, "model_digest": model["digest"],
                "request": body, "raw_response": raw, "checks": checks,
                "expected": {"refresh_seconds": 20, "labels": expected}}
    Path("evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"score": sum(checks.values()) / len(checks), "artifact_paths": ["evidence.json"]}


if __name__ == "__main__":
    import sys

    print(json.dumps(evaluate(json.load(sys.stdin))))
