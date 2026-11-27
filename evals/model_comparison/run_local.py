"""Opt-in hosted model benchmark through the real CLI in a disposable local profile."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from evals.generated_curriculum.run_zip_study import cli, write_json


def protocol(models):
    entries = [
        [{'name': 'a.txt', 'text': 'abc'}, {'name': 'empty.txt', 'text': ''}],
        [{'name': 'folder/', 'text': ''}, {'name': 'folder/b.txt', 'text': '12345'}],
        [{'name': 'unicode.txt', 'text': 'ação🙂'}, {'name': 'second.txt', 'text': 'é'}],
    ]
    file_schema = {'type': 'object', 'properties': {'name': {'type': 'string'}, 'bytes': {'type': 'integer'}},
                   'required': ['name', 'bytes'], 'additionalProperties': False}
    return {'category': 'archive.zip-manifest.prediction',
        'instructions': 'Return the ordered manifest of regular files for a ZIP made from the supplied entries. '
                        'Names ending in / are directories; exclude them. bytes is the UTF-8 byte length of text, '
                        'not character count. total_bytes is the sum for regular files. Return only the schema JSON.',
        'json_schema': {'type': 'object', 'properties': {'files': {'type': 'array', 'items': file_schema},
            'total_bytes': {'type': 'integer'}}, 'required': ['files', 'total_bytes'], 'additionalProperties': False},
        'routes': [{'provider': 'custom', 'model': model} for model in models],
        'cases': [{'case_id': f'case-{i}', 'input': {'entries': items}, 'oracle': {'entries': items}}
                  for i, items in enumerate(entries)],
        'evaluator': str(Path(__file__).with_name('zip_manifest_grader.py').resolve()),
        'minimum_score': 1, 'max_tokens': 768, 'timeout': 120, 'max_seconds': 600}


def execute(repo, root, env, identity):
    deadline = time.monotonic() + 630
    with (root / 'run.stdout').open('w', encoding='utf-8') as stdout, (root / 'run.stderr').open('w', encoding='utf-8') as stderr:
        child = subprocess.Popen([sys.executable, '-m', 'nara_cli.main', 'mission', 'model-benchmark-run', identity],
                                 cwd=repo, env=env, stdout=stdout, stderr=stderr)
        try:
            while True:
                try:
                    return child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('comparison outer deadline exhausted')
                    print('Local model comparison still running; receipts remain in the disposable profile.', flush=True)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', action='append', help='Installed Ollama model; repeat to compare models')
    parser.add_argument('--curriculum-request', type=Path, help='Compare initial curriculum generation using one archived ZIP request')
    args = parser.parse_args()
    models = args.model or ['qwen3.5:4b']
    repo = Path(__file__).resolve().parents[2]
    with urlopen('http://127.0.0.1:11434/api/tags', timeout=10) as response:
        installed = {row['name']: row for row in json.load(response)['models']}
    inventory = [{'model': name, 'digest': installed[name]['digest']} for name in models]
    root = Path(tempfile.mkdtemp(prefix='nara-live-model-comparison-')).resolve()
    print(f'profile: {root}', flush=True)
    write_json(root / 'config.yaml', {'_setup_done': True,
        'model': {'provider': 'custom', 'default': models[0], 'base_url': 'http://127.0.0.1:11434/v1', 'api_key': 'local-eval'},
        'auxiliary': {'transient_retries': 0, 'nara_model_benchmark': {'reasoning_effort': 'none'}},
        'plugins': {'entries': {'mission_control': {'llm': {'allow_provider_override': True,
            'allow_model_override': True, 'allowed_providers': ['custom'], 'allowed_models': models}}}},
        '_benchmark_inventory': inventory})
    if args.curriculum_request:
        from evals.model_comparison.curriculum_benchmark import prepare

        spec = prepare(args.curriculum_request, models, root / 'curriculum-grader.py')
    else:
        spec = protocol(models)
    write_json(root / 'comparison.json', spec)
    env = {key: value for key, value in os.environ.items() if key in {'PATH', 'PYTHONPATH', 'SYSTEMROOT', 'WINDIR', 'TZ', 'LANG'}}
    env['NARA_HOME'] = str(root)
    job = cli(repo, root, env, 'enqueue', 'model-benchmark-enqueue', '--protocol-file', str(root / 'comparison.json'))
    write_json(root / 'frozen.json', {'mission_id': job['mission_id'], 'constraints': job['constraints'], 'models': inventory,
                                     'source_request_sha256': spec.get('source_request_sha256')})
    code = execute(repo, root, env, job['mission_id'])
    scores = cli(repo, root, env, 'performance', 'model-performance', spec['category'])
    summary = {'profile': str(root), 'mission_id': job['mission_id'], 'exit_code': code, 'performance': scores,
               'run_stdout_sha256': hashlib.sha256((root / 'run.stdout').read_bytes()).hexdigest()}
    write_json(root / 'summary.json', summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
