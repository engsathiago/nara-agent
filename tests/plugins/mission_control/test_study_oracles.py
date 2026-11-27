"""A study oracle must distinguish actual correct and incorrect file results."""

import json
from pathlib import Path

import pytest

from plugins.mission_control.cli import register_cli, mission_command


def invoke(capsys, *argv):
    import argparse

    parser = argparse.ArgumentParser()
    register_cli(parser)
    code = mission_command(parser.parse_args(list(argv)))
    return code, json.loads(capsys.readouterr().out)


def test_exported_zip_protocol_is_calibrated_before_it_can_be_queued(tmp_path, capsys):
    destination = tmp_path / 'zip-oracle'
    code, result = invoke(capsys, 'study-oracle-prepare', 'zip-manifest', str(destination),
                          '--model', 'fixture-local')
    assert code == 0 and result['calibration']['passed'], result
    protocol = json.loads(Path(result['protocol_file']).read_text(encoding='utf-8-sig'))
    assert 'cases_file' not in protocol and protocol['curriculum']['validator']
    assert all(row['observed'] == row['expected'] for row in result['calibration']['probes'])
    assert any(row['expected'] == 0 for row in result['calibration']['probes'])
    assert any(row['expected'] == 1 for row in result['calibration']['probes'])
    assert Path(protocol['curriculum']['brief_file']).is_file()


def test_oracle_grading_requires_exact_inventory_and_real_byte_counts(tmp_path):
    from plugins.mission_control.study_oracle_zip import build_archive, grade_manifest, reference_manifest

    path = tmp_path / 'source.zip'
    build_archive(path, [{'name':'nested/', 'text':''}, {'name':'nested/item.txt', 'text':'ação'},
                         {'name':'root.txt', 'text':'z'}])
    expected = reference_manifest(path)
    assert expected == {'files':['nested/item.txt','root.txt'], 'total_file_bytes':7, 'directory_count':1}
    assert grade_manifest(expected, expected) == 1.0
    assert grade_manifest({**expected, 'files':['root.txt']}, expected) == 0
    assert grade_manifest({**expected, 'total_file_bytes':5}, expected) == 0
    assert grade_manifest({**expected, 'directory_count':True}, expected) == 0


def test_bad_oracle_cannot_publish_a_protocol(tmp_path, capsys, monkeypatch):
    from plugins.mission_control import study_oracle_zip

    monkeypatch.setattr(study_oracle_zip, 'grade_manifest', lambda *args: 1.0)
    destination = tmp_path / 'bad-oracle'
    code, report = invoke(capsys, 'study-oracle-prepare', 'zip-manifest', str(destination), '--model', 'fixture-local')
    assert code == 1 and 'calibration' in report['message'], report
    assert not destination.exists()


def zip_curriculum():
    span = {'id':'s0000', 'start':0, 'end':66, 'text':'ZipFile.infolist() returns a ZipInfo record for each archive member.'}
    return {'case_id':'validate', 'source':{'spans':[span]}, 'curriculum':{
        'teaching_material':{'explanation':span['text'], 'questions':[
            {'question':'Which ZipFile method returns member metadata records?', 'answer':'ZipFile.infolist()',
             'citations':[span]}]},
        'cases':[
            {'case_id':'dev', 'split':'development', 'group_id':'flat', 'payload':{'members':[{'name':'root.txt','text':'a'}]}},
            {'case_id':'hold', 'split':'transfer', 'group_id':'nested', 'payload':{'members':[
                {'name':'folder/','text':''}, {'name':'folder/item.txt','text':'b'}]}},
            {'case_id':'canary', 'split':'canary', 'group_id':'empty', 'payload':{'members':[]}},
        ]}}


@pytest.mark.parametrize('mutation,passed', [('none', True), ('false_answer', False), ('renamed_topology', False)])
def test_exported_validator_checks_facts_and_structural_independence(tmp_path, capsys, mutation, passed):
    from plugins.mission_control.learning_runner import ProcessEvaluator

    _, prepared = invoke(capsys, 'study-oracle-prepare', 'zip-manifest', str(tmp_path / 'protocol'), '--model', 'fixture-local')
    protocol = json.loads(Path(prepared['protocol_file']).read_text(encoding='utf-8-sig'))
    case = zip_curriculum()
    if mutation == 'false_answer':
        case['curriculum']['teaching_material']['questions'][0]['answer'] = 'ZipFile.extractall()'
    elif mutation == 'renamed_topology':
        case['curriculum']['cases'][1]['payload'] = {'members':[{'name':'different.txt','text':'new'}]}
    evaluator = ProcessEvaluator(protocol['curriculum']['validator'], tmp_path / 'evidence')
    result = evaluator(None, case)
    assert result['score'] == float(passed), result
    receipt = json.loads(Path(result['evidence'][0]['path']).read_text(encoding='utf-8-sig'))
    assert receipt['passed'] is passed and receipt['calibration']['passed']


@pytest.mark.parametrize('status,cost', [('unknown', None), (None, None), ('estimated', 0.25)])
def test_terminal_oracle_keeps_unpriced_usage_unknown(tmp_path, monkeypatch, status, cost):
    from plugins.mission_control import study_oracle_zip as oracle

    monkeypatch.chdir(tmp_path)
    def run_agent(*args):
        Path('manifest.json').write_text(json.dumps(oracle.reference_manifest(Path('source.zip'))))
        Path('usage.json').write_text('{}')
        Path('agent.stdout').write_text('complete')
        Path('agent.stderr').write_text('')
        return {'cost_status': status, 'total_including_auxiliary': {'estimated_cost_usd': 0.25}}
    monkeypatch.setattr(oracle, '_run_agent', run_agent)
    result = oracle.execute_case({'candidate': None, 'case': {'case_id': 'cost', 'members': []}},
                                 {'model': 'fixture', 'runtime_identity': {}})
    assert result['score'] == 1
    if cost is None:
        assert 'cost_usd' not in result
    else:
        assert result['cost_usd'] == cost


def test_owned_gateway_is_reaped_when_case_execution_raises(tmp_path):
    import os
    import sys
    from plugins.mission_control.study_oracle_zip import owned_gateway

    program = tmp_path / 'gateway.py'
    program.write_text('import os,json,threading\nfrom pathlib import Path\n'
                       'Path("gateway_state.json").write_text(json.dumps({"pid":os.getpid(),"gateway_state":"running"}))\n'
                       'threading.Event().wait(60)\n', encoding='utf-8')
    with pytest.raises(ValueError, match='case failed'):
        with owned_gateway([sys.executable, str(program)], dict(os.environ), tmp_path) as child:
            assert child.poll() is None
            raise ValueError('case failed')
    assert child.poll() is not None
