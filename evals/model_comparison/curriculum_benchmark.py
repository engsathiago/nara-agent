"""Freeze the existing curriculum validators for identical-input model comparisons."""

import base64
import hashlib
import json
from pathlib import Path


MODULES = ('learning_acceptance', 'study_checkpoint', 'study_payload_schema',
           'study_curriculum_schema', 'study_oracle_zip')

GRADER = '''
import base64
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


def main():
    case = json.load(sys.stdin)['case']
    sources = json.loads(base64.b64decode(FROZEN_SOURCES))
    manifest = {name: hashlib.sha256(content.encode('utf-8')).hexdigest() for name, content in sources.items()}
    with TemporaryDirectory(prefix='nara-curriculum-oracle-') as folder:
        root = Path(folder)
        for name, content in sources.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        sys.path.insert(0, str(root))
        from plugins.mission_control.study_payload_schema import payload_schema
        from plugins.mission_control.study_curriculum_schema import resolve_curriculum
        from plugins.mission_control.study_oracle_zip import calibrate, validate_curriculum
        calibration = calibrate()
        if not calibration['passed']:
            raise ValueError('frozen ZIP oracle failed calibration')
        supplied = case['input']
        try:
            package = resolve_curriculum(case['response'], supplied['source']['spans'], payload_schema(supplied['brief']))
            validation = validate_curriculum({'curriculum': package, 'source': supplied['source']})
            result = {'score': 1, 'validation': validation}
        except (ValueError, TypeError, KeyError) as exc:
            result = {'score': 0, 'reason': str(exc)}
        result.update(calibration=calibration, validator_sources=manifest)
        Path('curriculum-grade.json').write_text(json.dumps(result, sort_keys=True), encoding='utf-8')
        print(json.dumps({'score': result['score'], 'artifact_paths': ['curriculum-grade.json'],
                          'cost_usd': 0, 'feedback': result.get('reason', 'Frozen curriculum validators passed')}))


if __name__ == '__main__':
    main()
'''


def export_grader(path):
    root = Path(__file__).resolve().parents[2] / 'plugins' / 'mission_control'
    sources = {'plugins/__init__.py': '', 'plugins/mission_control/__init__.py': ''}
    sources.update({f'plugins/mission_control/{name}.py': (root / (name + '.py')).read_text(encoding='utf-8-sig')
                    for name in MODULES})
    encoded = base64.b64encode(json.dumps(sources, sort_keys=True, ensure_ascii=False).encode()).decode()
    path.write_text('FROZEN_SOURCES = ' + repr(encoded) + '\n' + GRADER, encoding='utf-8')
    return path


def prepare(request_path, models, evaluator_path):
    original = request_path.read_bytes()
    request = json.loads(original.decode('utf-8-sig'))
    if request.get('kind') != 'curriculum_request' or request.get('input', {}).get('brief', {}).get('task_family') != 'zip-manifest':
        raise ValueError('comparison requires an archived ZIP curriculum request')
    if 'correction' in request['input']:
        raise ValueError('compare the same initial generation request, without prior proposal feedback')
    evaluator = export_grader(evaluator_path)
    (evaluator_path.parent / 'frozen-source-request.json').write_bytes(original)
    return {'source_request_sha256': hashlib.sha256(original).hexdigest(),
            'category': 'curriculum.zip-manifest', 'instructions': request['instructions'],
            'json_schema': request['schema'], 'routes': [{'provider': 'custom', 'model': model} for model in models],
            'cases': [{'case_id': 'frozen-source-curriculum', 'input': request['input'], 'oracle': {}}],
            'evaluator': str(evaluator), 'minimum_score': 1,
            'max_tokens': request['max_tokens'], 'timeout': 120, 'max_seconds': 600}
