"""Task-category model statistics derived only from verified benchmark ledger events."""

import math

from plugins.mission_control.model_benchmark_schema import execution_fingerprint
from plugins.mission_control.ledger import ExperienceLedger
from plugins.mission_control.store import MissionStore


def _cost(generation):
    value = generation.get('usage', {}).get('cost_usd')
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('model benchmark reported an invalid cost')
    return float(value)


class ModelPerformance:
    def __init__(self, missions, ledger):
        self.missions, self.ledger = missions, ledger

    @classmethod
    def open_default(cls):
        return cls(MissionStore.open_default(), ExperienceLedger.open_default())

    def summaries(self, category, benchmark_scope=None):
        from plugins.mission_control.model_benchmarks import ModelBenchmarks
        from plugins.mission_control.model_benchmark_proof import verify_report

        owner = ModelBenchmarks(self.missions, self.ledger, None)
        eligible = []
        fingerprint = execution_fingerprint()
        for job in self.missions.list(status='completed'):
            if (not job.constraints.get('model_benchmark') or job.constraints.get('category') != category
                    or job.constraints.get('execution_fingerprint') != fingerprint):
                continue
            events = [row for row in self.ledger.events(job.mission_id) if row['kind'] == 'model.benchmark.verified']
            if len(events) != 1:
                raise ValueError('model benchmark lacks a unique verified ledger event')
            event = events[0]
            scope = job.constraints['benchmark_scope']
            if event['payload'].get('category') != category or event['payload'].get('benchmark_scope') != scope:
                raise ValueError('model performance ledger identity changed')
            if benchmark_scope is None or scope == benchmark_scope:
                eligible.append((event['occurred_at'], job, event))
        if not eligible:
            return []
        # A new suite is a new cohort: never pool grades from different inputs or rubrics.
        scope = benchmark_scope or max(eligible, key=lambda row: (row[0], row[1].mission_id))[1].constraints['benchmark_scope']
        groups = {}
        for _, job, event in eligible:
            if job.constraints['benchmark_scope'] != scope:
                continue
            result = verify_report(owner, job, event['payload']['result_artifact_id'])
            protocol = owner.read(job.mission_id, result['protocol_artifact_id'])
            for row in result['rows']:
                route = row['route']
                key = (route['provider'], route['model'])
                generation = owner.read(job.mission_id, row['generation_artifact_id'])
                score = row['evaluation']['score'] if row['status'] == 'graded' else None
                groups.setdefault(key, []).append({'mission_id': job.mission_id, 'score': score,
                    'success': score is not None and score >= protocol['minimum_score'],
                    'duration_ms': row['duration_ms'], 'cost_usd': _cost(generation), 'status': row['status']})
        return [_summary(category, scope, key, rows) for key, rows in sorted(groups.items())]


def _summary(category, scope, key, rows):
    scores = [row['score'] for row in rows if row['score'] is not None]
    costs = [row['cost_usd'] for row in rows if row['cost_usd'] is not None]
    return {'provider': key[0], 'model': key[1], 'category': category, 'benchmark_scope': scope,
            'sample_count': len(rows), 'graded_count': len(scores),
            'success_rate': sum(row['success'] for row in rows) / len(rows),
            'mean_score': sum(scores) / len(scores) if scores else None,
            'call_failure_count': sum(row['status'] == 'call_failed' for row in rows),
            'route_mismatch_count': sum(row['status'] == 'route_mismatch' for row in rows),
            'mean_duration_ms': sum(row['duration_ms'] for row in rows) / len(rows),
            'priced_sample_count': len(costs), 'mean_cost_usd': sum(costs) / len(costs) if len(costs) == len(rows) else None,
            'evidence_missions': sorted({row['mission_id'] for row in rows})}
