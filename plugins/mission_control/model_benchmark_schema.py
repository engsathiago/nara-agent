"""Freeze comparable model probes without exposing private grading inputs."""

import hashlib
import json
from pathlib import Path
import re

from nara_cli.config import load_config_readonly

from plugins.mission_control.learning_acceptance import validate_minimum_score


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()


def _text(value, limit, name):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'model benchmark {name} must contain 1-{limit} characters')
    return value


def _bounded(value, lower, upper, name):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f'model benchmark {name} must be an integer from {lower} to {upper}')
    return value


def _routes(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 5:
        raise ValueError('model benchmark requires 1-5 routes')
    seen, result = set(), []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'provider', 'model'}:
            raise ValueError('model benchmark route requires provider and model')
        route = {key: _text(item[key], 200, key) for key in ('provider', 'model')}
        identity = (route['provider'], route['model'])
        if identity in seen:
            raise ValueError('model benchmark routes must be distinct')
        seen.add(identity)
        result.append(route)
    return result


def _cases(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 10:
        raise ValueError('model benchmark requires 1-10 cases')
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {'case_id', 'input', 'oracle'}:
            raise ValueError('model benchmark case requires case_id, public input and private oracle')
        identity = _text(item['case_id'], 120, 'case_id')
        if identity in seen or len(canonical(item['input'])) > 24000 or len(canonical(item['oracle'])) > 16000:
            raise ValueError('model benchmark case is duplicated or exceeds input bounds')
        seen.add(identity)
    return items


def execution_fingerprint():
    """Partition observations when the profile configuration changes; store no config values."""
    return hashlib.sha256(canonical(load_config_readonly() or {})).hexdigest()


def prepare(spec):
    category = _text(spec['category'], 120, 'category')
    if not re.fullmatch(r'[a-z][a-z0-9_.-]*', category):
        raise ValueError('model benchmark category must be a stable lowercase identifier')
    schema = spec['json_schema']
    if not isinstance(schema, dict) or not schema or len(canonical(schema)) > 16000:
        raise ValueError('model benchmark schema must be a nonempty object up to 16000 bytes')
    path = Path(spec['evaluator']).expanduser().resolve()
    source = path.read_bytes()
    if path.suffix != '.py' or not source or len(source) > 1_000_000:
        raise ValueError('model benchmark evaluator must be a Python file up to 1 MB')
    score = validate_minimum_score(spec.get('minimum_score', 1))
    if score <= 0:
        raise ValueError('model benchmark minimum score must be positive')
    protocol = {'version': 1, 'category': category,
                'instructions': _text(spec['instructions'], 16000, 'instructions'),
                'json_schema': schema, 'cases': _cases(spec['cases']), 'minimum_score': score,
                'max_tokens': _bounded(spec.get('max_tokens', 2048), 16, 8192, 'max_tokens'),
                'timeout': _bounded(spec.get('timeout', 120), 1, 120, 'timeout'),
                'evaluator_sha256': hashlib.sha256(source).hexdigest(),
                'execution_fingerprint': execution_fingerprint()}
    scope = hashlib.sha256(canonical(protocol)).hexdigest()
    protocol.update(routes=_routes(spec['routes']), benchmark_scope=scope,
                    max_seconds=_bounded(spec.get('max_seconds', 600), 1, 3600, 'max_seconds'))
    return json.loads(canonical(protocol)), source


def model_request(protocol, route, case, timeout):
    return {'instructions': protocol['instructions'],
            'input': [{'type': 'text', 'text': json.dumps(case['input'], ensure_ascii=False)}],
            'json_schema': protocol['json_schema'], 'schema_name': 'model_benchmark',
            'provider': route['provider'], 'model': route['model'], 'temperature': 0.0,
            'max_tokens': protocol['max_tokens'], 'timeout': timeout,
            'purpose': 'mission-control.model-benchmark', 'task': 'nara_model_benchmark'}
