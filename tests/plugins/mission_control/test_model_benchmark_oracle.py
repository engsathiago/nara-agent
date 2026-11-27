"""Calibrate the live ZIP manifest oracle against correct and incorrect answers."""

from pathlib import Path

from evals.model_comparison.run_local import protocol
from evals.model_comparison import zip_manifest_grader
from plugins.mission_control.learning_runner import ProcessEvaluator


def test_zip_prediction_oracle_checks_utf8_directories_and_exact_totals(tmp_path):
    spec = protocol(['fixture'])
    evaluator = ProcessEvaluator(Path(zip_manifest_grader.__file__), tmp_path / 'evidence')
    answers = [
        {'files': [{'name': 'a.txt', 'bytes': 3}, {'name': 'empty.txt', 'bytes': 0}], 'total_bytes': 3},
        {'files': [{'name': 'folder/b.txt', 'bytes': 5}], 'total_bytes': 5},
        {'files': [{'name': 'unicode.txt', 'bytes': 10}, {'name': 'second.txt', 'bytes': 2}], 'total_bytes': 12},
    ]
    for case, answer in zip(spec['cases'], answers):
        correct = evaluator(None, {**case, 'response': answer})
        incorrect = evaluator(None, {**case, 'response': {**answer, 'total_bytes': 99}})
        assert correct['score'] == 1 and incorrect['score'] == 0
        assert correct['evidence'] and incorrect['evidence']
