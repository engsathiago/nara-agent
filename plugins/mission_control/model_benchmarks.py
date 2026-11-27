"""Execute frozen model comparisons through host inference and independent graders."""

from dataclasses import asdict
import json
import logging
import time
import uuid

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import Mission, Verification, VerificationStatus
from plugins.mission_control.ledger import ExperienceLedger
from plugins.mission_control.learning_runner import ProcessEvaluator
from plugins.mission_control.model_benchmark_schema import canonical, execution_fingerprint, model_request, prepare
from plugins.mission_control.store import MissionStore, MissionStoreError
from plugins.mission_control.study_checkpoint import study_lock
from plugins.mission_control.verification import VerificationService


logger = logging.getLogger(__name__)

CRITERION = 'Execute and verify the frozen model comparison matrix'


class ModelBenchmarks:
    def __init__(self, missions, ledger, llm):
        self.missions, self.ledger, self.llm = missions, ledger, llm
        self.root = missions.path.parent / 'model-benchmarks'
        self.artifacts = ArtifactStore(missions, missions.path.parent / 'artifacts')

    @classmethod
    def open_default(cls, llm):
        return cls(MissionStore.open_default(), ExperienceLedger.open_default(), llm)

    def archive(self, identity, payload):
        return self.artifacts.put_bytes(identity, canonical(payload), producer_id='model-benchmark',
                                        media_type='application/json').artifact_id

    def read(self, identity, reference):
        return json.loads(self.artifacts.read_bytes(identity, reference))

    def enqueue(self, spec):
        protocol, evaluator = prepare(spec)
        identity = 'model-benchmark-' + uuid.uuid4().hex
        mission = self.missions.create(Mission(mission_id=identity,
            objective='Measure model routes for ' + protocol['category'], completion_criteria=[CRITERION],
            constraints={'model_benchmark': True, 'category': protocol['category'],
                         'benchmark_scope': protocol['benchmark_scope'],
                         'execution_fingerprint': protocol['execution_fingerprint']},
            budget={'max_seconds': protocol['max_seconds']}), actor_id='model-benchmark')
        source = self.artifacts.put_bytes(identity, evaluator, producer_id='model-benchmark-evaluator')
        protocol['evaluator_artifact_id'] = source.artifact_id
        reference = self.archive(identity, protocol)
        self.missions.record_diagnostic(identity, {'diagnostic_id': 'model_benchmark',
            'protocol_artifact_id': reference, 'phase': 'ready', 'rows': [], 'pending': None},
            idempotency_key='model-benchmark:prepared')
        return self.missions.transition(mission.mission_id, 'planned', actor_id='model-benchmark').to_dict()

    def save(self, identity, state, phase, **updates):
        state.update(phase=phase, **updates)
        self.missions.record_diagnostic(identity, {'diagnostic_id': 'model_benchmark', **state},
                                        idempotency_key='model-benchmark:' + uuid.uuid4().hex)

    def run(self, identity):
        from plugins.mission_control.model_benchmark_proof import verify_report

        with study_lock(self.root, identity):
            job = self.missions.get(identity)
            if job is None or not job.constraints.get('model_benchmark'):
                raise ValueError('unknown model benchmark')
            state = dict(job.diagnostics['model_benchmark'])
            if job.status == 'completed':
                return verify_report(self, job, state['result_artifact_id'])
            if job.status in {'failed', 'cancelled'}:
                return state.get('result', {'status': job.status})
            if job.status == 'planned':
                self.missions.transition(identity, 'running', actor_id='model-benchmark')
            try:
                protocol = self.read(identity, state['protocol_artifact_id'])
                if 'deadline_at' not in state:
                    self.save(identity, state, 'ready', deadline_at=time.time() + protocol['max_seconds'])
                if state['pending'] is not None:
                    raise ValueError('model benchmark has unconfirmed execution; reconcile before retry')
                execution = BenchmarkExecution(self, identity, protocol, state)
                execution.run()
                return self.finish(identity, protocol, state)
            except (ValueError, OSError, KeyError, MissionStoreError) as exc:
                result = {'status': 'failed', 'reason': str(exc), 'error_type': type(exc).__name__}
                self.save(identity, state, 'failed', result=result)
                self.missions.transition(identity, 'failed', actor_id='model-benchmark', reason=str(exc))
                return result

    def finish(self, identity, protocol, state):
        from plugins.mission_control.model_benchmark_proof import verify_report

        result = {'kind': 'model_benchmark_result', 'status': 'completed', 'mission_id': identity,
                  'category': protocol['category'], 'benchmark_scope': protocol['benchmark_scope'],
                  'protocol_artifact_id': state['protocol_artifact_id'], 'rows': state['rows']}
        reference = self.archive(identity, result)
        self.save(identity, state, 'verified', result_artifact_id=reference)
        job = self.missions.get(identity)
        verified = verify_report(self, job, reference)
        if job.status == 'running':
            job = self.missions.transition(identity, 'verifying', actor_id='model-benchmark')
        if 'model-benchmark-proof' not in job.verifications:
            VerificationService(self.missions, self.artifacts).record(Verification(
                verification_id='model-benchmark-proof', mission_id=identity, criterion=CRITERION,
                verifier_id='model-benchmark-proof', executor_id='model-benchmark', status=VerificationStatus.PASS,
                method='frozen-model-matrix', evidence_artifact_ids=[reference],
                explanation='All route/case outcomes match frozen requests and independent grader evidence'))
        self.ledger.record(event_id=identity + ':verified', kind='model.benchmark.verified', mission_id=identity,
            status='completed', payload={'category': protocol['category'],
                'benchmark_scope': protocol['benchmark_scope'], 'result_artifact_id': reference})
        self.missions.transition(identity, 'completed', actor_id='model-benchmark')
        return verified


class BenchmarkExecution:
    def __init__(self, owner, identity, protocol, state):
        self.owner, self.identity, self.protocol, self.state = owner, identity, protocol, state

    def save(self, phase, **updates):
        self.owner.save(self.identity, self.state, phase, **updates)

    def archive(self, value):
        return self.owner.archive(self.identity, value)

    def timeout(self):
        remaining = self.state['deadline_at'] - time.time()
        if remaining < 1:
            raise ValueError('model benchmark deadline exhausted')
        return min(self.protocol['timeout'], remaining)

    def run(self):
        from plugins.mission_control.model_benchmark_proof import verify_row

        matrix = [(route, case) for route in self.protocol['routes'] for case in self.protocol['cases']]
        for index, (route, case) in enumerate(matrix):
            if index < len(self.state['rows']):
                verify_row(self.owner, self.identity, self.protocol, route, case, self.state['rows'][index])
                continue
            row = self.generate(index, route, case)
            verify_row(self.owner, self.identity, self.protocol, route, case, row)
            if row['status'] == 'generated':
                row = self.grade(index, route, case, row)
            self.save('cell_completed', rows=[*self.state['rows'], row], current=None)

    def generate(self, index, route, case):
        current = self.state.get('current')
        if current is not None:
            if current['index'] != index:
                raise ValueError('model benchmark cell identity changed')
            return current['row']
        if self.owner.llm is None:
            raise ValueError("host model service is unavailable")
        if execution_fingerprint() != self.protocol["execution_fingerprint"]:
            raise ValueError("model benchmark profile configuration changed")
        request = model_request(self.protocol, route, case, self.timeout())
        reference = self.archive({'kind': 'model_benchmark_request', 'index': index, 'request': request})
        self.save('generating', pending={'kind': 'generation', 'request_artifact_id': reference, 'index': index})
        started = time.monotonic()
        row = {'route': route, 'case_id': case['case_id'], 'request_artifact_id': reference}
        try:
            response = self.owner.llm.complete_structured(**request)
            if len(response.text) > 64000 or len(canonical(response.parsed)) > 64000:
                raise ValueError('model benchmark response exceeds 64000 bytes')
            receipt = {'status': 'generated', 'provider': response.provider, 'model': response.model,
                       'parsed': response.parsed, 'response': response.text, 'usage': asdict(response.usage)}
            if (response.provider, response.model) != (route['provider'], route['model']):
                receipt['status'] = 'route_mismatch'
        except Exception as exc:
            logger.exception("Model benchmark call failed for cell %s", index)
            receipt = {'status': 'call_failed', 'error_type': type(exc).__name__}
        receipt.update(request_artifact_id=reference, duration_ms=max(0, int((time.monotonic() - started) * 1000)))
        row.update(generation_artifact_id=self.archive(receipt), status=receipt['status'],
                   duration_ms=receipt['duration_ms'])
        self.save('generated', pending=None, current={'index': index, 'row': row})
        return row

    def grade(self, index, route, case, row):
        generation = self.owner.read(self.identity, row['generation_artifact_id'])
        grading_case = {**case, 'response': generation['parsed']}
        reference = self.archive({'kind': 'model_benchmark_grade_request', 'case': grading_case,
                                  'generation_artifact_id': row['generation_artifact_id']})
        source = self.owner.artifacts.get(self.identity, self.protocol['evaluator_artifact_id'])
        self.owner.artifacts.verify(self.identity, source.artifact_id)
        evaluator = ProcessEvaluator(source.location, self.owner.root / 'evidence',
                                     timeout=self.timeout(), python_script=True)
        self.save('grading', pending={'kind': 'evaluation', 'request_artifact_id': reference, 'index': index})
        evaluation = evaluator(None, grading_case)
        receipt = {'request_artifact_id': reference, 'evaluator_sha256': evaluator.sha256, 'result': evaluation}
        updated = {**row, 'status': 'graded', 'evaluation': evaluation,
                   'evaluation_artifact_id': self.archive(receipt)}
        self.save('graded', pending=None, current={'index': index, 'row': updated})
        return updated
