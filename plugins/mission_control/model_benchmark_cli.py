"""Bounded model measurement through the registered Mission Control CLI."""

import json
from pathlib import Path

from plugins.mission_control.model_benchmarks import ModelBenchmarks
from plugins.mission_control.model_performance import ModelPerformance
from plugins.mission_control.store import MissionStoreError


def register_model_cli(actions):
    enqueue = actions.add_parser('model-benchmark-enqueue', help='Freeze model comparison inputs and independent grader')
    enqueue.add_argument('--protocol-file', type=Path, required=True)
    run = actions.add_parser('model-benchmark-run', help='Execute or resume a frozen model comparison')
    run.add_argument('mission_id')
    performance = actions.add_parser('model-performance', help='Show verified per-category model results')
    performance.add_argument('category')
    performance.add_argument('--benchmark-scope')


def model_command(args, llm=None):
    try:
        actions = {
            'model-benchmark-enqueue': lambda: ModelBenchmarks.open_default(None).enqueue(
                json.loads(args.protocol_file.read_text(encoding='utf-8-sig'))),
            'model-benchmark-run': lambda: ModelBenchmarks.open_default(llm).run(args.mission_id),
            'model-performance': lambda: ModelPerformance.open_default().summaries(args.category, args.benchmark_scope),
        }
        result = actions[args.mission_action]()
        code = int(isinstance(result, dict) and result.get('status') in {'failed', 'cancelled'})
    except (ValueError, KeyError, TypeError, OSError, MissionStoreError) as exc:
        result, code = {'error': type(exc).__name__, 'message': str(exc)}, 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return code
