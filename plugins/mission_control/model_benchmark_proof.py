"""Recheck model-comparison provenance before it can affect another worker."""

import hashlib
import math

from plugins.mission_control.model_benchmark_schema import canonical, model_request
from plugins.mission_control.study_checkpoint import verify_evaluator_result


SCOPE_FIELDS = ('version', 'category', 'instructions', 'json_schema', 'cases', 'minimum_score',
                'max_tokens', 'timeout', 'evaluator_sha256', 'execution_fingerprint')


def verify_row(owner, identity, protocol, route, case, row):
    if row['route'] != route or row['case_id'] != case['case_id']:
        raise ValueError('model benchmark route/case matrix changed')
    request = owner.read(identity, row['request_artifact_id'])
    index = protocol['routes'].index(route) * len(protocol['cases']) + protocol['cases'].index(case)
    timeout = request['request']['timeout']
    if (request['kind'] != 'model_benchmark_request' or request['index'] != index
            or isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= protocol['timeout']
            or request['request'] != model_request(protocol, route, case, timeout)):
        raise ValueError('model benchmark request differs from its frozen protocol')
    generation = owner.read(identity, row['generation_artifact_id'])
    if (generation['request_artifact_id'] != row['request_artifact_id']
            or type(generation['duration_ms']) is not int or generation['duration_ms'] < 0
            or row['duration_ms'] != generation['duration_ms']):
        raise ValueError('model benchmark generation proof changed')
    status = generation['status']
    if status == 'generated':
        if (generation['provider'], generation['model']) != (route['provider'], route['model']):
            raise ValueError('model benchmark response belongs to another route')
        if row['status'] == 'graded':
            _grade(owner, identity, protocol, case, row, generation)
        elif row['status'] != 'generated':
            raise ValueError('model benchmark generation status changed')
    elif status not in {'call_failed', 'route_mismatch'} or row['status'] != status:
        raise ValueError('model benchmark failure proof changed')
    return generation


def _grade(owner, identity, protocol, case, row, generation):
    receipt = owner.read(identity, row['evaluation_artifact_id'])
    request = owner.read(identity, receipt['request_artifact_id'])
    expected = {'kind': 'model_benchmark_grade_request', 'case': {**case, 'response': generation['parsed']},
                'generation_artifact_id': row['generation_artifact_id']}
    if (request != expected or receipt['evaluator_sha256'] != protocol['evaluator_sha256']
            or row['evaluation'] != receipt['result']):
        raise ValueError('model benchmark evaluator proof changed')
    result = verify_evaluator_result(receipt['result'])
    score = result['score']
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError('model benchmark has an invalid verified score')


def verify_report(owner, job, reference):
    result = owner.read(job.mission_id, reference)
    state = job.diagnostics['model_benchmark']
    protocol = owner.read(job.mission_id, state['protocol_artifact_id'])
    scope = hashlib.sha256(canonical({key: protocol[key] for key in SCOPE_FIELDS})).hexdigest()
    if (result['kind'] != 'model_benchmark_result' or result['status'] != 'completed'
            or result['mission_id'] != job.mission_id or result['protocol_artifact_id'] != state['protocol_artifact_id']
            or result['category'] != protocol['category'] or protocol['category'] != job.constraints['category']
            or result['benchmark_scope'] != scope or protocol['benchmark_scope'] != scope
            or scope != job.constraints['benchmark_scope']
            or protocol['execution_fingerprint'] != job.constraints['execution_fingerprint']):
        raise ValueError('model benchmark result differs from its frozen comparison')
    evaluator = owner.artifacts.read_bytes(job.mission_id, protocol['evaluator_artifact_id'])
    if hashlib.sha256(evaluator).hexdigest() != protocol['evaluator_sha256']:
        raise ValueError('model benchmark evaluator changed')
    matrix = [(route, case) for route in protocol['routes'] for case in protocol['cases']]
    if len(result['rows']) != len(matrix):
        raise ValueError('model benchmark does not cover the full comparison matrix')
    for (route, case), row in zip(matrix, result['rows']):
        if row['status'] == 'generated':
            raise ValueError('model benchmark response has not been independently graded')
        verify_row(owner, job.mission_id, protocol, route, case, row)
    return result
