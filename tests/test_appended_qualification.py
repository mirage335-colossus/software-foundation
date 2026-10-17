"""Synthetic kernel evidence and one real Python byte-integrity check.

Kernel executables and SDKs are inert fixtures, and manually authored execution
reports are synthetic. One named test supervises the actual Python byte checker.
No fixture kernel or compiler executes, and no native qualification is claimed.
"""
from contextlib import ExitStack, redirect_stdout
import builtins
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ORIGINAL_POPEN = subprocess.Popen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended_container as container
import appended_policy
import appended_project
import appended_qualification as qualification
import appended_release
import artifact
import dependency_archive
import dependency_store
import release
import source_identity
from test_appended_container import elf_fixture
from test_appended_wasm import module as wasm_fixture
from test_sdk import fixture as sdk_fixture

_spec = importlib.util.spec_from_file_location('appended_fixture_certifier', ROOT / 'tools/certify_release.py')
certifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(certifier)


KERNEL_ASSERTIONS = ['sealed-kernel', 'loader-contract', 'module-profile', 'service-abi']
HOST = {'system': 'Linux', 'machine': 'x86_64', 'release': 'synthetic-kernel',
        'version': 'synthetic-version', 'python': '3.9.0', 'distribution': 'synthetic',
        'runner_image': None, 'runner_image_version': None}


def document(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False))


def pinned(path, base, **extra):
    return {'path': path.relative_to(base).as_posix(),
            'sha256': dependency_archive.digest(path), **extra}


def synthetic_reports(coverage, plan, root, *, details=None, assertions=None,
                      run_id='synthetic-run', attempt=1, direct=False):
    """Write independent coverage-format bytes without executing plan commands."""
    reports = []
    for check in plan['checks']:
        directory = root if direct else root / check['id']
        directory.mkdir(parents=True)
        names = check['expected_tests']
        junit = directory / check.get('junit', 'source.junit.xml')
        junit.write_text('<testsuite>' + ''.join('<testcase name="' + name + '"/>' for name in names) + '</testsuite>')
        observed = dict(details or {})
        observed.update(run_id=run_id, attempt=attempt)
        if check['scope'] in ('source', 'recovery', 'guest-source'):
            observed['executed_tests'] = names
        evidence = {junit.name: dependency_archive.digest(junit)}
        if check['scope'] == 'guest-source':
            guest = directory / 'guest.junit.xml'
            guest.write_bytes(junit.read_bytes())
            evidence[guest.name] = dependency_archive.digest(guest)
        receipt = {'schema_version': 1, 'source_sha256': plan['subject']['source_sha256'],
                   'inventory_sha256': plan['subject']['inventory_sha256'],
                   'target': check['target'], 'backend': check['backend'], 'scope': check['scope'],
                   'host': HOST, 'status': 'passed', 'details': observed,
                   'assertions': list(assertions if assertions is not None else names), 'evidence': evidence}
        receipt_path = directory / check['qualification']
        document(receipt_path, receipt)
        console = directory / 'console.log'
        console.write_text('Explicitly synthetic unit-test receipt; no command executed.\n')
        result = {'schema_version': 1, 'plan': plan['id'], 'subject': plan['subject'],
                  'check': check['id'], 'run_id': run_id, 'attempt': attempt,
                  'status': 'passed', 'exit_code': 0, 'created_at': '2026-10-16T00:00:00+00:00',
                  'argv': ['synthetic-not-executed'], 'host': HOST, 'warnings': [],
                  'error': None, 'seconds': 0.01,
                  'evidence': {name: dependency_archive.digest(directory / name)
                               for name in ('console.log', receipt_path.name, *receipt['evidence'])}}
        result_path = directory / 'result.json'
        document(result_path, result)
        reports.append(result_path)
    return reports


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.report_plans = {}
        # Forbid every common process entry point even during fixture creation.
        # Archive, hashing and evidence verification need no native tools.
        processes = ExitStack()
        self.addCleanup(processes.close)
        for name in ('run', 'Popen', 'check_output', 'check_call', 'call'):
            processes.enter_context(patch.object(subprocess, name,
                side_effect=AssertionError('forbidden native/process invocation: ' + name)))
        self.coverage = certifier.coverage
        self.source = self.root / 'source'
        (self.source / 'src').mkdir(parents=True)
        (self.source / 'src/kernel.cpp').write_text('synthetic retained source\n')
        self.configuration = appended_project.default_document()
        self.configuration['application'] = {'id': 'synthetic.fixture', 'name': 'Synthetic fixture', 'version': '2.0.0'}
        self.configuration['kernel']['profile'] = 'binary'
        document(self.source / appended_project.CONFIG_NAME, self.configuration)
        self.inputs = self.root / 'selected'
        self.inputs.mkdir()
        self.source_archive = self.inputs / 'source.tar.gz'
        self.source_identity = source_identity.archive_source(self.source, self.source_archive)
        self.prefix, boundary = elf_fixture()
        self.descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'elf',
            'profile': 'binary', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
            'capabilities': [], 'services': [], 'executable': {'length': len(self.prefix),
            'sha256': container.digest(self.prefix)}, 'boundary_offset': boundary,
            'provenance': {'producer': 'synthetic-unit-fixture', 'qualification': 'unqualified-development'},
            'kernel_inputs': appended_policy.kernel_source_tree(self.source)}
        self.descriptor_path = self.inputs / 'kernel.json'
        document(self.descriptor_path, self.descriptor)
        recipe, _, _, self.sdk_group = sdk_fixture(self.root / 'synthetic-sdk')
        self.recipe = recipe
        self.base = self.inputs / 'kernel.tar.gz'
        info = ('sdk_recipe_id=' + recipe + '\nsource_tree_sha256=' + self.source_identity['tree_sha256']
                + '\ntarget=linux-x86_64\ngui_backends=\ndependency_recipes=' + recipe + '\n')
        self.members = {'bin/application': (self.prefix, 0o755), 'build-info.txt': (info.encode(), 0o644),
                        'share/original.txt': (b'unchanged original bytes\n', 0o644)}
        appended_release._write_archive(self.base, self.members, {'bin': 0o755, 'share': 0o755})
        self.inventory_path = self.inputs / 'kernel.inventory.json'
        document(self.inventory_path, artifact.describe(self.base))
        self.original = self.root / 'original-release'
        store = self.root / 'sdk-store'
        dependency_store.put(store, self.sdk_group, recipe)
        spec = {'schema_version': 1, 'source': {'path': str(self.source_archive), 'sha256': dependency_archive.digest(self.source_archive)},
                'artifacts': [{'path': str(self.base), 'manifest_path': str(self.inventory_path),
                    'sha256': dependency_archive.digest(self.base), 'target': 'linux-x86_64',
                    'backends': [], 'sdk_recipe': recipe}],
                'required_scopes': ['source', 'archive', 'recovery', 'appended-kernel']}
        spec_path = self.root / 'original-spec.json'
        document(spec_path, spec)
        self.original_manifest = release.assemble(spec_path, store, self.original)
        self.proof_tree = self.root / 'proof-tree'
        shutil.copytree(self.original, self.proof_tree / 'release')
        shutil.copyfile(self.descriptor_path, self.proof_tree / 'kernel.json')
        self.old_policy, self.old_plan, self.old_reports, self.old_certificate = self.old_qualification()
        self.proof_path = self.root / 'kernel-proof.tar.gz'
        self.write_proof()
        self.selection = {'schema_version': 1, 'kind': 'foundation-appended-selection',
            'application': self.configuration['application'],
            'source': pinned(self.source_archive, self.inputs, tree_sha256=self.source_identity['tree_sha256']),
            'payload': None, 'kernels': [{'id': 'linux-elf', 'archive': pinned(self.base, self.inputs),
                'inventory': pinned(self.inventory_path, self.inputs), 'descriptor': pinned(self.descriptor_path, self.inputs),
                'runtime_member': 'bin/application', 'output': 'synthetic-linux.tar.gz',
                'original_source': pinned(self.source_archive, self.inputs, tree_sha256=self.source_identity['tree_sha256']),
                'recovery': [], 'evidence': []}]}
        for name in dependency_store.names(recipe):
            destination = self.inputs / name
            shutil.copyfile(self.sdk_group / name, destination)
            self.selection['kernels'][0]['recovery'].append(pinned(destination, self.inputs))
        self.selection_path = self.inputs / 'selection.json'
        document(self.selection_path, self.selection)
        self.candidate = self.root / 'candidate'
        self.prepared = appended_release.prepare_release(self.selection_path, self.candidate)
        self.pin = self.prepared['candidate_sha256']
        self.policy = self.new_policy()
        self.proofs = {'linux-elf': pinned(self.proof_path, self.root)}
        self.checks = self.new_checks()

    def old_qualification(self, *, omit_abi=False):
        rows = [{'target': 'linux-x86_64', 'backend': 'core', 'environment': 'synthetic', 'scope': scope}
                for scope in ('source', 'archive', 'recovery', 'abi', 'appended-kernel')
                if not (omit_abi and scope == 'abi')]
        policy = {'schema_version': 1, 'profiles': {'synthetic': {'description': 'Synthetic old evidence only',
                  'targets': {'linux-x86_64': ['core']}, 'checks': rows}}}
        checks = []
        for row in rows:
            assertions = KERNEL_ASSERTIONS if row['scope'] == 'appended-kernel' else [row['scope']]
            checks.append(dict(row, id=row['scope'], required=True, argv=['synthetic-not-executed'],
                timeout_seconds=5, warning_seconds=4, expected_tests=assertions,
                qualification='qualification.json', junit='source.junit.xml'))
        plan = self.coverage.freeze({'schema_version': 1, 'mode': 'release', 'subject': {
            'source_sha256': self.original_manifest['source']['sha256'],
            'inventory_sha256': dependency_archive.digest(self.proof_tree / 'release/release.json'),
            'configuration_sha256': self.coverage.digest({'policy': policy, 'profile': 'synthetic'})},
            'inputs': {}, 'checks': checks})
        details = {'appended_kernel': {'descriptor_sha256': dependency_archive.digest(self.descriptor_path),
            'kernel_prefix_sha256': container.digest(self.prefix), 'kernel_prefix_length': len(self.prefix),
            'profile': 'binary', 'abi': {'major': 1, 'minor': 0}, 'archive_sha256': dependency_archive.digest(self.base),
            'runtime_member': 'bin/application', 'source_tree_sha256': self.source_identity['tree_sha256']}}
        reports = synthetic_reports(self.coverage, plan, self.proof_tree / 'evidence', details=details)
        certificate = certifier.certify(self.proof_tree / 'release', self.original_manifest,
            plan, reports, policy, 'synthetic')
        document(self.proof_tree / 'policy.json', policy)
        document(self.proof_tree / 'plan.json', plan)
        document(self.proof_tree / 'certificate.json', certificate)
        return policy, plan, reports, certificate

    def write_proof(self):
        manifest = {'schema_version': 1, 'kind': 'foundation-retained-kernel-proof',
            'files': dependency_archive.file_inventory(self.proof_tree, exclude=('kernel-proof.json',)),
            'descriptor': 'kernel.json', 'release': 'release/release.json', 'certificate': 'certificate.json',
            'plan': 'plan.json', 'policy': 'policy.json', 'profile': 'synthetic',
            'reports': [path.relative_to(self.proof_tree).as_posix() for path in self.old_reports],
            'target': 'linux-x86_64', 'backend': 'core', 'archive': 'kernel.tar.gz',
            'runtime_member': 'bin/application', 'appended_check': 'appended-kernel'}
        document(self.proof_tree / 'kernel-proof.json', manifest)
        self.proof_path.unlink(missing_ok=True)
        dependency_archive.archive_tree(self.proof_tree, self.proof_path)

    def new_policy(self):
        checks = []
        for identity, scope, item, target, backend, environment in (
            ('integrity', 'composition-integrity', None, 'composition', 'none', 'portable'),
            ('recompose', 'offline-recompose', None, 'composition', 'none', 'portable'),
            ('runtime', 'retained-runtime', 'linux-elf', 'linux-x86_64', 'core', 'synthetic'),
            ('install', 'install-upgrade', 'linux-elf', 'linux-x86_64', 'core', 'synthetic')):
            checks.append({'id': identity, 'artifact': item, 'scope': scope, 'target': target,
                'backend': backend, 'environment': environment, 'assertions': [scope]})
        return {'schema_version': 1, 'kind': 'foundation-appended-qualification-policy',
            'profiles': {'synthetic': {'description': 'Synthetic fixtures, never platform qualification',
                'artifacts': {'linux-elf': {'target': 'linux-x86_64', 'backend': 'core', 'carrier': 'elf',
                                          'baseline': 'synthetic', 'channels': ['synthetic-archive-channel']}},
                'checks': checks, 'kernel_scopes': ['source', 'archive', 'recovery', 'abi'],
                'kernel_assertions': KERNEL_ASSERTIONS}}}

    def new_checks(self, policy=None):
        checks = []
        for row in (policy or self.policy)['profiles']['synthetic']['checks']:
            argv = ['{python}', '-I', '-S', str(qualification.TOOL_ROOT / 'tools/appended_release_check.py'), row['scope'],
                '--release', str(self.candidate), '--candidate-sha256', self.pin,
                '--target', row['target'], '--backend', row['backend'],
                '--evidence', '{evidence}', '--junit', 'assertions.junit.xml']
            if row['artifact'] is not None:
                argv.extend(['--artifact', row['artifact']])
            if 'scenario' in row:
                argv.extend(['--scenario', str(self.root / row['scenario']['path']),
                             '--scenario-sha256', row['scenario']['sha256']])
            checks.append({'id': row['id'], 'scope': row['scope'], 'target': row['target'],
                'backend': row['backend'], 'environment': row['environment'], 'required': True,
                'argv': argv, 'timeout_seconds': 5, 'warning_seconds': 4,
                'expected_tests': list(row['assertions']), 'junit': 'assertions.junit.xml',
                'qualification': 'qualification.json'})
        return checks

    def freeze(self, policy=None, checks=None, proofs=None):
        return qualification.freeze_plan(self.candidate, self.pin, policy or self.policy, 'synthetic',
            self.proofs if proofs is None else proofs, checks=self.checks if checks is None else checks,
            evidence_root=self.root)

    def repack_proof(self):
        self.proof_path.unlink()
        dependency_archive.archive_tree(self.proof_tree, self.proof_path)
        self.proofs['linux-elf'] = pinned(self.proof_path, self.root)

    def reports(self, plan, directory='fresh-evidence'):
        reports = synthetic_reports(self.coverage, plan['coverage_plan'], self.root / directory,
                                    details=self.fresh_details(plan))
        for path in reports:
            self.annotate_fresh_report(plan, path)
        return reports

    def fresh_details(self, plan):
        subject = plan['subject']
        return {'plan': plan['coverage_plan']['id'], 'qualification_policy_sha256': subject['policy_sha256'],
            'profile': 'synthetic', 'candidate_sha256': subject['candidate_sha256'],
            'composition_sha256': subject['composition_sha256'], 'selection_sha256': subject['selection_sha256']}

    def annotate_fresh_report(self, plan, path, *, complete=True):
        receipt = json.loads((path.parent / 'qualification.json').read_bytes())
        identity = json.loads(path.read_bytes())['check']
        receipt['details']['composition_check_id'] = identity
        receipt['details']['checker_sources'] = {
            name: reference['sha256'] for name, reference in plan['tool_sources'].items()}
        result = json.loads(path.read_bytes())
        for name, reference in plan['tool_sources'].items():
            retained = 'checker-sources/' + name
            destination = path.parent / retained
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.root / reference['path']).read_bytes())
            receipt['evidence'][retained] = reference['sha256']
            result['evidence'][retained] = reference['sha256']
        row = next(item for item in plan['policy']['profiles']['synthetic']['checks'] if item['id'] == identity)
        if row['artifact'] is not None:
            receipt['details']['artifact_id'] = row['artifact']
        if row['scope'] == 'install-upgrade':
            receipt['details']['channels'] = ['synthetic-archive-channel']
        document(path.parent / 'qualification.json', receipt)
        document(path, result)
        self.report_plans[path] = plan
        self.refresh_report(path, complete=complete)

    def local_tool_tree(self, plan, name='local-tools'):
        """Copy frozen real checker sources into an owned mutation fixture."""
        root = self.root / name
        for filename, reference in plan['tool_sources'].items():
            destination = root / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.root / reference['path']).read_bytes())
        return root

    def rehash_plan(self, plan):
        plan['coverage_plan']['id'] = self.coverage.digest({
            key: value for key, value in plan['coverage_plan'].items() if key != 'id'})
        plan['id'] = self.coverage.digest({key: value for key, value in plan.items() if key != 'id'})
        return plan

    def supervised_report(self, plan, execution_plan, check_id, root, output, run_id, attempt):
        """Materialize one raw supervisor outcome without launching its argv."""
        check = next(item for item in execution_plan['checks'] if item['id'] == check_id)
        projection = dict(execution_plan, checks=[check])
        path = synthetic_reports(self.coverage, projection, output, details=self.fresh_details(plan),
            run_id=run_id, attempt=attempt, direct=True)[0]
        self.annotate_fresh_report(plan, path, complete=False)
        report = json.loads(path.read_bytes())
        report['argv'] = [argument.replace('{python}', sys.executable).replace('{root}', str(root))
                          .replace('{evidence}', str(output)).replace('{plan_id}', execution_plan['id'])
                          .replace('{run_id}', run_id).replace('{attempt}', str(attempt))
                          for argument in check['argv']]
        document(path, report)
        return report

    def refresh_report(self, path, *, complete=True):
        report = json.loads(path.read_bytes())
        completion = report.pop('completion', None)
        if completion is not None:
            report['evidence'].pop(completion['path'], None)
        report['evidence'] = {name: dependency_archive.digest(path.parent / name) for name in report['evidence']}
        if path in self.report_plans:
            plan = self.report_plans[path]
            check = next(item for item in plan['coverage_plan']['checks'] if item['id'] == report['check'])
            receipt_path = path.parent / check['qualification']
            receipt = json.loads(receipt_path.read_bytes())
            receipt['evidence'].pop(qualification.COMPLETION_FILE, None)
            document(receipt_path, receipt)
            report['evidence'][check['qualification']] = dependency_archive.digest(receipt_path)
        if complete and path in self.report_plans:
            completion_path = path.parent / qualification.COMPLETION_FILE
            document(completion_path, qualification.completion_record(plan, report, receipt))
            completion_pin = dependency_archive.digest(completion_path)
            receipt['evidence'][qualification.COMPLETION_FILE] = completion_pin
            document(receipt_path, receipt)
            report['evidence'][check['qualification']] = dependency_archive.digest(receipt_path)
            report['completion'] = {'path': qualification.COMPLETION_FILE,
                                    'sha256': completion_pin}
            report['evidence'][qualification.COMPLETION_FILE] = report['completion']['sha256']
        document(path, report)

    def certify(self, plan, reports):
        return qualification.certify(self.candidate, self.pin, plan, reports, evidence_root=self.root)

    def test_complete_synthetic_evidence_preserves_original_identities_and_candidate(self):
        before = appended_release._files(self.candidate)
        original = {path.relative_to(self.proof_tree).as_posix(): path.read_bytes()
                    for path in self.proof_tree.rglob('*') if path.is_file()}
        plan = self.freeze()
        reports = self.reports(plan)
        certificate = self.certify(plan, reports)
        self.assertEqual(certificate['status'], 'passed')
        self.assertTrue(certificate['eligible_for_promotion'])
        self.assertEqual(certificate['subject'], plan['subject'])
        qualification.verify_certificate(self.candidate, self.pin, plan, reports, certificate, evidence_root=self.root)
        self.assertEqual(appended_release._files(self.candidate), before)
        self.assertEqual({path.relative_to(self.proof_tree).as_posix(): path.read_bytes()
                          for path in self.proof_tree.rglob('*') if path.is_file()}, original)
        self.assertEqual(plan['kernel_proofs'], self.proofs)
        self.assertEqual(appended_release.verify_candidate(self.candidate, self.pin)['qualification'], 'incomplete')

    def test_incomplete_candidate_metadata_is_not_execution_evidence(self):
        plan = self.freeze()
        with self.assertRaises((ValueError, OSError)):
            self.certify(plan, [])
        reports = self.reports(plan)
        (reports[-1].parent / 'qualification.json').unlink()
        with self.assertRaises((ValueError, OSError)):
            self.certify(plan, reports)

    def test_missing_duplicate_optional_or_noop_checks_cannot_freeze(self):
        mutations = [lambda checks: checks.pop(), lambda checks: checks.append(copy.deepcopy(checks[0])),
                     lambda checks: checks[0].update(required=False),
                     lambda checks: checks[0].pop('qualification'), lambda checks: checks[0].pop('junit'),
                     lambda checks: checks[0].update(expected_tests=[]),
                     lambda checks: checks[0].update(expected_tests=['unrelated'])]
        for mutation in mutations:
            checks = copy.deepcopy(self.checks)
            mutation(checks)
            with self.subTest(checks=checks), self.assertRaises(ValueError):
                self.freeze(checks=checks)

    def test_policy_requires_complete_artifact_and_scope_contract(self):
        mutations = [lambda value: value.update(schema_version=True),
            lambda value: value.update(kind='unknown'), lambda value: value.update(unknown=True),
            lambda value: value['profiles']['synthetic']['checks'].pop(),
            lambda value: value['profiles']['synthetic']['checks'].append(copy.deepcopy(value['profiles']['synthetic']['checks'][0])),
            lambda value: value['profiles']['synthetic']['artifacts'].clear(),
            lambda value: value['profiles']['synthetic']['artifacts']['linux-elf'].pop('channels'),
            lambda value: value['profiles']['synthetic']['artifacts']['linux-elf'].update(channels=[]),
            lambda value: value['profiles']['synthetic']['artifacts']['linux-elf'].update(channels=['archive', 'archive']),
            lambda value: value['profiles']['synthetic']['artifacts']['linux-elf'].update(channels=['second', 'first']),
            lambda value: value['profiles']['synthetic'].update(kernel_scopes=['source', 'archive']),
            lambda value: value['profiles']['synthetic'].update(kernel_scopes=['source', 'archive', 'recovery']),
            lambda value: value['profiles']['synthetic'].update(kernel_assertions=[])]
        for mutation in mutations:
            policy = copy.deepcopy(self.policy)
            mutation(policy)
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                self.freeze(policy=policy, checks=self.new_checks(policy))

    def test_proof_pin_inventory_and_original_certificate_are_required(self):
        for proofs in ({}, {'unknown': self.proofs['linux-elf']},
                       {'linux-elf': dict(self.proofs['linux-elf'], sha256='0' * 64)},
                       {'linux-elf': {'path': '../kernel-proof.tar.gz', 'sha256': '0' * 64}}):
            with self.subTest(proofs=proofs), self.assertRaises((ValueError, OSError)):
                self.freeze(proofs=proofs)
        certificate = json.loads((self.proof_tree / 'certificate.json').read_bytes())
        certificate['eligible_for_promotion'] = False
        document(self.proof_tree / 'certificate.json', certificate)
        self.write_proof()
        self.proofs['linux-elf'] = pinned(self.proof_path, self.root)
        with self.assertRaises(ValueError):
            self.freeze()

    def test_original_proof_complete_inventory_and_strict_json_are_enforced(self):
        path = self.proof_tree / 'kernel-proof.json'
        original = path.read_bytes()
        manifest = json.loads(original)
        incomplete = copy.deepcopy(manifest)
        incomplete['files'].pop('certificate.json')
        unknown = dict(manifest, unknown='must fail closed')
        boolean_schema = dict(manifest, schema_version=True)
        redirected = dict(manifest, certificate='../certificate.json')
        for value in (incomplete, unknown, boolean_schema, redirected):
            document(path, value)
            self.repack_proof()
            with self.subTest(manifest=value), self.assertRaises(ValueError):
                self.freeze()
        path.write_bytes(b'{"schema_version":1,' + original[1:])
        self.repack_proof()
        with self.assertRaises(ValueError):
            self.freeze()

    def test_kernel_proof_needs_actual_assertions_and_original_bound_descriptor(self):
        path = self.proof_tree / 'evidence/appended-kernel/qualification.json'
        original = json.loads(path.read_bytes())
        for name, mutation in (
            ('missing-abi-assertion', lambda receipt: receipt['assertions'].remove('service-abi')),
            ('wrong-prefix', lambda receipt: receipt['details']['appended_kernel'].update(kernel_prefix_sha256='0' * 64)),
            ('wrong-profile', lambda receipt: receipt['details']['appended_kernel'].update(profile='web')),
            ('boolean-abi-major', lambda receipt: receipt['details']['appended_kernel']['abi'].update(major=True)),
            ('boolean-abi-minor', lambda receipt: receipt['details']['appended_kernel']['abi'].update(minor=False)),
            ('boolean-prefix-length', lambda receipt: receipt['details']['appended_kernel'].update(kernel_prefix_length=True))):
            receipt = copy.deepcopy(original)
            mutation(receipt)
            document(path, receipt)
            self.refresh_report(path.parent / 'result.json')
            # Keep the old certificate internally consistent so the component
            # validator, rather than an outer checksum, must reject the attack.
            changed = certifier.certify(self.proof_tree / 'release', self.original_manifest,
                self.old_plan, self.old_reports, self.old_policy, 'synthetic')
            document(self.proof_tree / 'certificate.json', changed)
            self.write_proof()
            self.proofs['linux-elf'] = pinned(self.proof_path, self.root)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.freeze()

    def test_complete_legacy_certificate_without_abi_cannot_qualify_elf_kernel(self):
        # The original legacy policy can pass without ABI qualification; the
        # composition policy independently requires the selected ELF ABI scope.
        shutil.rmtree(self.proof_tree / 'evidence')
        self.old_policy, self.old_plan, self.old_reports, self.old_certificate = self.old_qualification(omit_abi=True)
        self.assertTrue(self.old_certificate['eligible_for_promotion'])
        self.write_proof()
        self.proofs['linux-elf'] = pinned(self.proof_path, self.root)
        with self.assertRaisesRegex(ValueError, 'coverage is incomplete'):
            self.freeze()

    def test_retained_baseline_and_complete_dependency_groups_cannot_be_weakened(self):
        changed = copy.deepcopy(self.policy)
        changed['profiles']['synthetic']['artifacts']['linux-elf']['baseline'] = 'different-baseline'
        for row in changed['profiles']['synthetic']['checks']:
            if row['artifact'] == 'linux-elf':
                row['environment'] = 'different-baseline'
        with self.assertRaisesRegex(ValueError, 'appended-kernel contract check'):
            self.freeze(policy=changed, checks=self.new_checks(changed))
        self.selection['kernels'][0]['recovery'].pop()
        document(self.selection_path, self.selection)
        self.candidate = self.root / 'incomplete-dependencies'
        self.pin = appended_release.prepare_release(self.selection_path, self.candidate)['candidate_sha256']
        with self.assertRaisesRegex(ValueError, 'SDK binary/source/checksum'):
            self.freeze()

    def test_fresh_receipt_identity_and_exact_assertion_inventory_are_enforced(self):
        plan = self.freeze()
        reports = self.reports(plan)
        path = reports[0].parent / 'qualification.json'
        original = json.loads(path.read_bytes())
        mutations = [lambda receipt: receipt['details'].update(candidate_sha256='0' * 64),
            lambda receipt: receipt['details'].update(composition_sha256='0' * 64),
            lambda receipt: receipt['details'].update(selection_sha256='0' * 64),
            lambda receipt: receipt['details'].update(qualification_policy_sha256='0' * 64),
            lambda receipt: receipt['details'].update(plan='0' * 64),
            lambda receipt: receipt['details'].update(composition_check_id='other'),
            lambda receipt: receipt['details'].update(profile='other'),
            lambda receipt: receipt['details'].update(run_id='other-run'),
            lambda receipt: receipt['details'].update(run_id=True),
            lambda receipt: receipt['details'].update(attempt=2),
            lambda receipt: receipt['details'].update(attempt=True),
            lambda receipt: receipt['details'].update(attempt='1'),
            lambda receipt: receipt.update(assertions=[]),
            lambda receipt: receipt.update(assertions=['unrelated']),
            lambda receipt: receipt.update(assertions=receipt['assertions'] * 2)]
        for mutation in mutations:
            receipt = copy.deepcopy(original)
            mutation(receipt)
            document(path, receipt)
            self.refresh_report(reports[0])
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                self.certify(plan, reports)

    def test_skipped_failed_changed_or_missing_assertions_never_pass(self):
        plan = self.freeze()
        reports = self.reports(plan)
        junit = reports[0].parent / 'assertions.junit.xml'
        original = junit.read_bytes()
        for body in (b'<testsuite/>', b'<testsuite><testcase name="composition-integrity"><skipped/></testcase></testsuite>',
                     b'<testsuite><testcase name="composition-integrity"><failure/></testcase></testsuite>'):
            junit.write_bytes(body)
            receipt_path = reports[0].parent / 'qualification.json'
            receipt = json.loads(receipt_path.read_bytes())
            receipt['evidence'][junit.name] = dependency_archive.digest(junit)
            document(receipt_path, receipt)
            self.refresh_report(reports[0])
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.certify(plan, reports)
        junit.write_bytes(original + b' ')
        with self.assertRaises(ValueError):
            self.certify(plan, reports)

    def test_stale_result_unknown_report_and_wrong_target_host_rejected(self):
        plan = self.freeze()
        reports = self.reports(plan)
        path = reports[-1]
        report = json.loads(path.read_bytes())
        for changed in (dict(report, plan='0' * 64), dict(report, check='unknown'),
                        dict(report, status='skipped', exit_code=None), dict(report, attempt=True),
                        dict(report, schema_version=True), dict(report, exit_code=False),
                        dict(report, seconds=True), dict(report, seconds=-1), dict(report, seconds='elapsed')):
            document(path, changed)
            with self.subTest(report=changed), self.assertRaises(ValueError):
                self.certify(plan, reports)
        document(path, report)
        receipt_path = path.parent / 'qualification.json'
        receipt = json.loads(receipt_path.read_bytes())
        receipt['host'] = dict(HOST, machine='aarch64')
        report['host'] = receipt['host']
        document(receipt_path, receipt)
        document(path, report)
        self.refresh_report(path)
        with self.assertRaises(ValueError):
            self.certify(plan, reports)

    def test_plan_certificate_and_frozen_candidate_tampering_are_rejected(self):
        plan = self.freeze()
        reports = self.reports(plan)
        certificate = self.certify(plan, reports)
        altered = copy.deepcopy(plan)
        altered['subject']['candidate_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.certify(altered, reports)
        forged = copy.deepcopy(certificate)
        forged['subject']['composition_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            qualification.verify_certificate(self.candidate, self.pin, plan, reports, forged, evidence_root=self.root)
        (self.candidate / 'composition.json').write_bytes((self.candidate / 'composition.json').read_bytes() + b' ')
        with self.assertRaises(ValueError):
            self.certify(plan, reports)

    def test_pinned_scenario_and_installation_evidence_bind_the_fresh_receipt(self):
        scenario = self.root / 'scenario.json'
        document(scenario, {'synthetic': 'install, upgrade and remove the retained application'})
        self.policy['profiles']['synthetic']['checks'][-1]['scenario'] = pinned(scenario, self.root)
        plan = self.freeze()
        reports = self.reports(plan)
        path = reports[-1].parent / 'qualification.json'
        receipt = json.loads(path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'pinned scenario'):
            self.certify(plan, reports)
        receipt['details']['scenario_sha256'] = dependency_archive.digest(scenario)
        for channels in (None, [], ['other-channel'], ['synthetic-archive-channel'] * 2):
            if channels is None:
                receipt['details'].pop('channels', None)
            else:
                receipt['details']['channels'] = channels
            document(path, receipt)
            self.refresh_report(reports[-1])
            with self.subTest(channels=channels), self.assertRaisesRegex(ValueError, 'channel evidence'):
                self.certify(plan, reports)
        receipt['details']['channels'] = ['synthetic-archive-channel']
        document(path, receipt)
        self.refresh_report(reports[-1])
        self.assertTrue(self.certify(plan, reports)['eligible_for_publication'])
        document(scenario, {'synthetic': 'changed after the plan was frozen'})
        with self.assertRaisesRegex(ValueError, 'input changed'):
            self.certify(plan, reports)

    def test_frozen_scenario_retains_complete_nested_instrument_inputs(self):
        scenarios = self.root / 'scenarios'
        scenarios.mkdir()
        instrument = scenarios / 'retained-sdk.tar.gz'
        instrument.write_bytes(b'pinned external instrument, not execution evidence')
        test = scenarios / 'browser.scenario'
        document(test, {'kind': 'foundation-appended-browser-scenario',
                        'inputs': {'retained-sdk.tar.gz': dependency_archive.digest(instrument)}})
        parent = scenarios / 'guest.json'
        document(parent, {'kind': 'foundation-appended-guest-source-scenario',
            'inputs': {'browser.scenario': dependency_archive.digest(test)},
            'test': {'scenario': 'browser.scenario'}})
        selected = {'checks': [{'scenario': pinned(parent, self.root)}]}
        frozen = qualification._frozen_inputs(selected, self.proofs, self.root)
        self.assertEqual(frozen['scenarios/retained-sdk.tar.gz'], dependency_archive.digest(instrument))
        self.assertEqual(frozen['scenarios/browser.scenario'], dependency_archive.digest(test))
        self.assertEqual(frozen['scenarios/guest.json'], dependency_archive.digest(parent))
        document(parent, {'kind': 'foundation-appended-guest-source-scenario', 'inputs': {},
                          'test': {'scenario': 'browser.scenario'}})
        selected['checks'][0]['scenario'] = pinned(parent, self.root)
        with self.assertRaisesRegex(ValueError, 'absent from declared inputs'):
            qualification._frozen_inputs(selected, self.proofs, self.root)
        document(parent, {'inputs': {'../escape': '0' * 64}})
        selected['checks'][0]['scenario'] = pinned(parent, self.root)
        with self.assertRaises(ValueError):
            qualification._frozen_inputs(selected, self.proofs, self.root)

    def test_plan_pins_scenario_instrument_bytes_before_any_check_runs(self):
        predecessor = self.root / 'previous.tar.gz'
        predecessor.write_bytes(b'previous pinned candidate group')
        scenario = self.root / 'install.json'
        document(scenario, {'inputs': {'previous.tar.gz': dependency_archive.digest(predecessor)}})
        self.policy['profiles']['synthetic']['checks'][-1]['scenario'] = pinned(scenario, self.root)
        plan = self.freeze()
        self.assertEqual(plan['coverage_plan']['inputs']['previous.tar.gz'], dependency_archive.digest(predecessor))
        predecessor.write_bytes(b'changed before qualification')
        with self.assertRaises(ValueError):
            qualification._validate_plan(self.candidate, self.pin, plan, self.root)

    def test_install_phase_scenarios_retain_nested_shared_instruments(self):
        scenarios = self.root / 'install-scenarios'
        phases = scenarios / 'phases'
        phases.mkdir(parents=True)
        instrument = phases / 'runner.py'
        instrument.write_bytes(b'Pinned synthetic instrument; never executed.\n')
        browser = phases / 'browser.json'
        runtime = phases / 'runtime.json'
        for path, kind in ((browser, 'foundation-appended-browser-scenario'),
                           (runtime, 'foundation-appended-runtime-scenario')):
            document(path, {'kind': kind, 'inputs': {'runner.py': dependency_archive.digest(instrument)}})
        parent = scenarios / 'install.json'
        document(parent, {'kind': 'foundation-appended-install-scenario',
            'inputs': {'phases/browser.json': dependency_archive.digest(browser),
                       'phases/runtime.json': dependency_archive.digest(runtime)},
            'phases': {'clean': {'scenario': 'phases/browser.json'},
                       'previous': {'scenario': 'phases/browser.json'},
                       'upgraded': {'scenario': 'phases/runtime.json'}}})
        selected = {'checks': [{'scenario': pinned(parent, self.root)}]}
        frozen = qualification._frozen_inputs(selected, self.proofs, self.root)
        for path in (parent, browser, runtime, instrument):
            self.assertEqual(frozen[path.relative_to(self.root).as_posix()], dependency_archive.digest(path))
        self.assertEqual(len(frozen), len(self.proofs) + 4)

    def test_install_phase_scenarios_require_declared_safe_typed_references(self):
        scenario = self.root / 'install.json'
        for phases, declared in (([], {}),
                ({'clean': {'scenario': 'missing.json'}}, {}),
                ({'clean': {}}, {}),
                ({'clean': {'scenario': False}}, {}),
                ({'clean': {'scenario': '../escape.json'}}, {'../escape.json': '0' * 64}),
                ({'clean': {'scenario': '/absolute.json'}}, {'/absolute.json': '0' * 64})):
            document(scenario, {'kind': 'foundation-appended-install-scenario',
                                'inputs': declared, 'phases': phases})
            selected = {'checks': [{'scenario': pinned(scenario, self.root)}]}
            with self.subTest(phases=phases), self.assertRaises(ValueError):
                qualification._frozen_inputs(selected, self.proofs, self.root)

    def test_native_install_phase_call_lists_keep_existing_input_discovery(self):
        instrument = self.root / 'state.bin'
        instrument.write_bytes(b'Synthetic native phase state; never executed.')
        scenario = self.root / 'native-install.json'
        document(scenario, {'kind': 'foundation-appended-install-scenario',
            'inputs': {'state.bin': dependency_archive.digest(instrument)},
            'phases': {name: [{'id': name, 'argv': ['ordinary-native-call']}]
                       for name in ('clean', 'previous', 'upgraded')}})
        selected = {'checks': [{'scenario': pinned(scenario, self.root)}]}
        frozen = qualification._frozen_inputs(selected, self.proofs, self.root)
        self.assertEqual(frozen['state.bin'], dependency_archive.digest(instrument))
        self.assertEqual(frozen['native-install.json'], dependency_archive.digest(scenario))
        self.assertEqual(len(frozen), len(self.proofs) + 2)

    def test_evidence_changed_during_certification_cannot_receive_certificate(self):
        plan = self.freeze()
        reports = self.reports(plan)
        original = appended_release.verify_composition_subject
        calls = 0

        def changed_at_final_subject_check(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                (reports[0].parent / 'assertions.junit.xml').write_text('<testsuite/>')
            return original(*args, **kwargs)

        with patch.object(appended_release, 'verify_composition_subject', side_effect=changed_at_final_subject_check), \
                self.assertRaisesRegex(ValueError, 'evidence|assertion'):
            self.certify(plan, reports)

    def test_cli_round_trip_handles_realistic_fractional_report_timings(self):
        plan = self.freeze()
        reports = self.reports(plan)
        plan_path = self.root / 'qualification-plan.json'
        certificate_path = self.root / 'certificate.json'
        document(plan_path, plan)
        arguments = ['--release', str(self.candidate), '--candidate-sha256', self.pin,
                     '--evidence-root', str(self.root), '--plan', str(plan_path)]
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(qualification.main(['certify', *arguments, '--output', str(certificate_path),
                                                *map(str, reports)]), 0)
        self.assertEqual(json.loads(stdout.getvalue()), json.loads(certificate_path.read_bytes()))
        self.assertEqual(json.loads(stdout.getvalue())['coverage']['checks']['integrity']['seconds'], 0.01)
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(qualification.main(['verify-certificate', *arguments,
                '--certificate', str(certificate_path), *map(str, reports)]), 0)
        self.assertEqual(json.loads(stdout.getvalue()), json.loads(certificate_path.read_bytes()))

    def test_supervised_check_uses_frozen_arguments_and_restores_scoped_environment(self):
        plan = self.freeze()
        before = appended_release._files(self.candidate)
        output = self.root / 'supervised-evidence'
        expected_environment = {'FOUNDATION_COMPOSITION_POLICY_SHA256': plan['subject']['policy_sha256'],
            'FOUNDATION_COMPOSITION_PROFILE': 'synthetic',
            'FOUNDATION_COMPOSITION_TOOL_SOURCES': container.canonical_json({
                name: reference['sha256'] for name, reference in plan['tool_sources'].items()}).decode()}
        inherited = {'FOUNDATION_COMPOSITION_POLICY_SHA256': 'prior-policy',
                     'FOUNDATION_COMPOSITION_PROFILE': 'prior-profile',
                     'FOUNDATION_COMPOSITION_TOOL_SOURCES': 'prior-tool-sources'}
        seen = []

        def supervised(*args):
            seen.append((args, {key: os.environ.get(key) for key in expected_environment}))
            return self.supervised_report(plan, *args)

        with patch.dict(os.environ, inherited), patch.object(qualification.coverage, 'run_case', side_effect=supervised):
            result = qualification.run_check(self.candidate, self.pin, plan, 'integrity', output,
                'synthetic-run', 3, evidence_root=self.root)
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result, json.loads((output / 'result.json').read_bytes()))
            self.assertIn('completion', result)
            self.assertEqual({key: os.environ[key] for key in inherited}, inherited)
        self.assertEqual(len(seen), 1)
        arguments, observed_environment = seen[0]
        self.assertEqual(arguments[:3], (plan['coverage_plan'], 'integrity', self.root))
        self.assertEqual(arguments[4:], ('synthetic-run', 3))
        self.assertNotEqual(arguments[3], output)
        self.assertTrue(arguments[3].is_relative_to(self.root))
        self.assertEqual(observed_environment, expected_environment)
        with patch.dict(os.environ, inherited), patch.object(qualification.coverage, 'run_case', side_effect=RuntimeError('synthetic supervisor error')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic supervisor error'):
                qualification.run_check(self.candidate, self.pin, plan, 'integrity', self.root / 'error-evidence',
                    'synthetic-run', 3, evidence_root=self.root)
            self.assertEqual({key: os.environ[key] for key in inherited}, inherited)
        with patch.object(qualification.coverage, 'run_case', side_effect=AssertionError('must reject before supervisor')):
            with self.assertRaisesRegex(ValueError, 'outside the immutable candidate'):
                qualification.run_check(self.candidate, self.pin, plan, 'integrity', self.candidate / 'evidence',
                    'synthetic-run', 3, evidence_root=self.root)
        self.assertEqual(appended_release._files(self.candidate), before)

    def test_run_rejects_unpinned_or_different_checker_commands_before_supervision(self):
        plan = self.freeze()
        mutations = [lambda argv: argv.__setitem__(3, str(self.root / 'unchecked-checker.py')),
                     lambda argv: argv.__setitem__(0, 'unchecked-python'),
                     lambda argv: argv.extend(['--unreviewed', 'flag']),
                     lambda argv: argv.extend(['--release', str(self.root / 'other-candidate')])]
        for mutation in mutations:
            changed = copy.deepcopy(plan)
            mutation(changed['coverage_plan']['checks'][0]['argv'])
            self.rehash_plan(changed)
            with self.subTest(argv=changed['coverage_plan']['checks'][0]['argv']), \
                    patch.object(qualification.coverage, 'run_case', side_effect=AssertionError('untrusted command reached supervisor')), \
                    self.assertRaises(ValueError):
                qualification.run_check(self.candidate, self.pin, changed, 'integrity', self.root / 'rejected-command',
                    'synthetic-run', 1, evidence_root=self.root)

    def test_fresh_reports_require_exact_successful_wrapper_completion(self):
        plan = self.freeze()
        reports = self.reports(plan)
        self.refresh_report(reports[0], complete=False)
        with self.assertRaises(ValueError):
            self.certify(plan, reports)
        self.refresh_report(reports[0])
        path = reports[0]
        wrapper_path = path.parent / qualification.COMPLETION_FILE
        wrapper = json.loads(wrapper_path.read_bytes())
        wrapper['run_id'] = 'other-run'
        document(wrapper_path, wrapper)
        wrapper_pin = dependency_archive.digest(wrapper_path)
        receipt_path = path.parent / 'qualification.json'
        receipt = json.loads(receipt_path.read_bytes())
        receipt['evidence'][qualification.COMPLETION_FILE] = wrapper_pin
        document(receipt_path, receipt)
        result = json.loads(path.read_bytes())
        result['completion']['sha256'] = wrapper_pin
        result['evidence'][qualification.COMPLETION_FILE] = wrapper_pin
        result['evidence']['qualification.json'] = dependency_archive.digest(receipt_path)
        document(path, result)
        with self.assertRaisesRegex(ValueError, 'completion'):
            self.certify(plan, reports)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'requires the qualified Linux Python process-tree supervisor')
    def test_real_python_integrity_supervision_binds_sources_and_completed_evidence(self):
        import appended_release_check
        row = self.policy['profiles']['synthetic']['checks'][0]
        row['assertions'] = list(appended_release_check.ASSERTIONS['composition-integrity'])
        self.checks = self.new_checks()
        self.checks[0].update(timeout_seconds=15, warning_seconds=12)
        plan = self.freeze()
        before = appended_release._files(self.candidate)
        output = self.root / 'real-python-integrity'
        launches = []

        def python_supervisor_only(argv, *args, **kwargs):
            self.assertEqual(argv[:4], [sys.executable, '-B', str(ROOT / 'tools/process_tree.py'), '--supervise-linux'])
            self.assertEqual(argv[7:12], [sys.executable, '-I', '-S',
                str(ROOT / 'tools/appended_release_check.py'), 'composition-integrity'])
            launches.append(list(argv))
            return ORIGINAL_POPEN(argv, *args, **kwargs)

        # Only this exact Python supervisor launch escapes the process guard.
        # Its fixed child performs byte checks and never executes the inert ELF,
        # SDK compiler fixture or any native package/build operation.
        with patch.object(subprocess, 'Popen', side_effect=python_supervisor_only):
            report = qualification.run_check(self.candidate, self.pin, plan, 'integrity', output,
                'real-byte-check', 1, evidence_root=self.root)
        self.assertEqual(len(launches), 1)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report, json.loads((output / 'result.json').read_bytes()))
        receipt = json.loads((output / 'qualification.json').read_bytes())
        self.assertEqual(receipt['assertions'], row['assertions'])
        self.assertEqual(receipt['details']['checker_sources'], {
            name: reference['sha256'] for name, reference in plan['tool_sources'].items()})
        self.assertEqual(receipt['details']['run_id'], 'real-byte-check')
        self.assertEqual(receipt['details']['attempt'], 1)
        qualification._verify_completion(plan, report, receipt, output)
        self.assertEqual(appended_release._files(self.candidate), before)

    def test_attempt_publication_rejects_parent_retargeted_to_a_link(self):
        staged = self.root / 'staged-attempt'
        staged.mkdir()
        document(staged / 'result.json', {'synthetic': 'must never reach the foreign directory'})
        parent = self.root / 'original-parent'
        parent.mkdir()
        output = parent / 'published'
        foreign = self.root / 'foreign-directory'
        foreign.mkdir()
        (foreign / 'keep.txt').write_bytes(b'preserve foreign bytes')
        parent.rename(self.root / 'moved-original-parent')
        parent.symlink_to(foreign, target_is_directory=True)
        with self.assertRaises(ValueError):
            qualification._publish_attempt(staged, output)
        self.assertEqual({path.name: path.read_bytes() for path in foreign.iterdir()},
                         {'keep.txt': b'preserve foreign bytes'})

    def test_plan_retains_exact_reviewed_tool_catalog_at_content_addresses(self):
        import appended_release_check
        self.assertEqual(qualification.tool_source_catalog(appended_release_check.ASSERTIONS),
                         appended_release_check.tool_source_catalog(appended_release_check.ASSERTIONS))
        plan = self.freeze()
        scopes = [row['scope'] for row in self.policy['profiles']['synthetic']['checks']]
        self.assertEqual(set(plan['tool_sources']), set(appended_release_check.tool_source_catalog(scopes)))
        self.assertIn('tools/appended_install_check.py', plan['tool_sources'])
        identities = {}
        for name, reference in plan['tool_sources'].items():
            self.assertEqual(set(reference), {'path', 'sha256'})
            self.assertEqual(reference['path'], 'tool-inputs/' + reference['sha256'])
            retained = self.root / reference['path']
            self.assertEqual(retained.read_bytes(), (ROOT / name).read_bytes())
            self.assertEqual(plan['coverage_plan']['inputs'][reference['path']], reference['sha256'])
            identities[reference['path']] = retained.stat().st_ino
        self.assertEqual(self.freeze(), plan)
        self.assertEqual({name: (self.root / name).stat().st_ino for name in identities}, identities)

    def test_missing_tampered_and_linked_tool_blobs_prevent_plan_validation(self):
        plan = self.freeze()
        reference = plan['tool_sources']['tools/appended_qualification.py']
        retained = self.root / reference['path']
        original = retained.read_bytes()
        retained.unlink()
        with self.assertRaises((ValueError, OSError)):
            qualification._validate_plan(self.candidate, self.pin, plan, self.root)
        retained.write_bytes(original + b'\n# tampered retained checker\n')
        with self.assertRaises(ValueError):
            qualification._validate_plan(self.candidate, self.pin, plan, self.root)
        retained.unlink()
        other = self.root / 'same-source-bytes.py'
        other.write_bytes(original)
        retained.symlink_to(other)
        with self.assertRaises(ValueError):
            qualification._validate_plan(self.candidate, self.pin, plan, self.root)

    def test_tool_blob_retention_never_overwrites_conflicting_existing_bytes(self):
        source = ROOT / 'tools/appended_qualification.py'
        destination = self.root / 'tool-inputs' / dependency_archive.digest(source)
        destination.parent.mkdir()
        destination.write_bytes(b'foreign bytes already occupy the expected content address')
        original = destination.read_bytes()
        with self.assertRaises(ValueError):
            self.freeze()
        self.assertEqual(destination.read_bytes(), original)

    def test_tool_source_map_rejects_unknown_missing_or_nonaddressed_inputs(self):
        plan = self.freeze()
        name = 'tools/appended_qualification.py'
        mutations = [lambda value: value['tool_sources'].pop(name),
            lambda value: value['tool_sources'].update({'tools/unreviewed.py': copy.deepcopy(value['tool_sources'][name])}),
            lambda value: value['tool_sources'][name].update(sha256='0' * 64),
            lambda value: value['tool_sources'][name].update(path='tool-inputs/incorrect-address'),
            lambda value: value['tool_sources'][name].update(unknown=True),
            lambda value: value.update(tool_sources=[]),
            lambda value: value['coverage_plan']['inputs'].pop(value['tool_sources'][name]['path'])]
        for mutation in mutations:
            changed = copy.deepcopy(plan)
            mutation(changed)
            self.rehash_plan(changed)
            with self.subTest(tool_sources=changed['tool_sources']), self.assertRaises(ValueError):
                qualification._validate_plan(self.candidate, self.pin, changed, self.root)

    def test_missing_real_required_checker_source_prevents_freeze(self):
        plan = self.freeze()
        current = self.local_tool_tree(plan)
        (current / 'tools/appended_install_check.py').unlink()
        with patch.object(qualification, 'TOOL_ROOT', current), self.assertRaises((ValueError, OSError)):
            self.freeze()

    def test_changed_local_tools_block_supervisor_before_and_after_execution(self):
        plan = self.freeze()
        before = appended_release._files(self.candidate)
        current = self.local_tool_tree(plan)
        for check in plan['coverage_plan']['checks']:
            check['argv'][3] = str(current / 'tools/appended_release_check.py')
        self.rehash_plan(plan)
        changed = current / 'tools/appended_qualification.py'
        original = changed.read_bytes()
        changed.write_bytes(original + b'\n# changed before execution\n')
        with patch.object(qualification, 'TOOL_ROOT', current), \
                patch.object(qualification.coverage, 'run_case', side_effect=AssertionError('stale tools reached supervisor')), \
                self.assertRaises(ValueError):
            qualification.run_check(self.candidate, self.pin, plan, 'integrity', self.root / 'before-check',
                'synthetic-run', 1, evidence_root=self.root)
        changed.write_bytes(original)
        calls = []

        def change_after_supervision(*args):
            calls.append(args)
            args[3].mkdir(parents=True)
            document(args[3] / 'result.json', {'status': 'passed'})
            changed.write_bytes(original + b'\n# changed during execution\n')
            return {'status': 'synthetic-wrapper-result'}

        with patch.object(qualification, 'TOOL_ROOT', current), \
                patch.object(qualification.coverage, 'run_case', side_effect=change_after_supervision), \
                self.assertRaises(ValueError):
            qualification.run_check(self.candidate, self.pin, plan, 'integrity', self.root / 'after-check',
                'synthetic-run', 1, evidence_root=self.root)
        self.assertEqual(len(calls), 1)
        self.assertFalse((self.root / 'after-check').exists())
        self.assertEqual(appended_release._files(self.candidate), before)

    def test_historical_tool_bytes_remain_certifiable_when_current_tools_change(self):
        plan = self.freeze()
        reports = self.reports(plan)
        certificate = self.certify(plan, reports)
        current = self.local_tool_tree(plan)
        (current / 'tools/appended_qualification.py').write_bytes(b'changed current checker; not historical evidence')
        with patch.object(qualification, 'TOOL_ROOT', current):
            self.assertEqual(self.certify(plan, reports), certificate)
            qualification.verify_certificate(self.candidate, self.pin, plan, reports, certificate, evidence_root=self.root)

    def test_freeze_and_historical_verification_never_import_current_checker_code(self):
        original = builtins.__import__

        def reject_checker_import(name, *args, **kwargs):
            if name == 'appended_release_check':
                raise AssertionError('unpinned checker import executed before source verification')
            return original(name, *args, **kwargs)

        with patch.object(builtins, '__import__', side_effect=reject_checker_import):
            plan = self.freeze()
            reports = self.reports(plan)
            self.assertTrue(self.certify(plan, reports)['eligible_for_publication'])

    def test_fresh_checker_source_map_and_retained_evidence_are_exact(self):
        plan = self.freeze()
        reports = self.reports(plan)
        path = reports[0].parent / 'qualification.json'
        original = json.loads(path.read_bytes())
        name = 'tools/appended_qualification.py'
        for mutation in (lambda value: value['details'].pop('checker_sources'),
                lambda value: value['details'].update(checker_sources={}),
                lambda value: value['details']['checker_sources'].update({name: '0' * 64}),
                lambda value: value['details']['checker_sources'].update({'tools/unreviewed.py': '0' * 64})):
            receipt = copy.deepcopy(original)
            mutation(receipt)
            document(path, receipt)
            self.refresh_report(reports[0])
            with self.subTest(details=receipt['details']), self.assertRaises(ValueError):
                self.certify(plan, reports)
        receipt = copy.deepcopy(original)
        evidence_name = 'checker-sources/' + name
        receipt['evidence'].pop(evidence_name)
        document(path, receipt)
        result = json.loads(reports[0].read_bytes())
        original_result = copy.deepcopy(result)
        result['evidence'].pop(evidence_name)
        document(reports[0], result)
        self.refresh_report(reports[0])
        with self.assertRaises(ValueError):
            self.certify(plan, reports)
        receipt = copy.deepcopy(original)
        (path.parent / evidence_name).write_bytes(b'altered retained checker source')
        receipt['evidence'][evidence_name] = dependency_archive.digest(path.parent / evidence_name)
        document(path, receipt)
        document(reports[0], original_result)
        self.refresh_report(reports[0])
        with self.assertRaises(ValueError):
            self.certify(plan, reports)

    def test_binary_payload_requires_guest_source_and_complete_fresh_evidence(self):
        # The independent Wasm vector is prepared bytes. No guest compiler or
        # native runtime executes, and all receipts remain explicitly synthetic.
        original_source = self.inputs / 'original-source.tar.gz'
        shutil.copyfile(self.source_archive, original_source)
        self.selection['kernels'][0]['original_source'] = pinned(original_source, self.inputs,
            tree_sha256=self.source_identity['tree_sha256'])
        self.configuration['appended']['binary']['enabled'] = True
        self.configuration['startup']['primary'] = 'binary'
        document(self.source / appended_project.CONFIG_NAME, self.configuration)
        (self.source / 'src-bin-appended').mkdir()
        (self.source / 'src-bin-appended/application.c').write_text('synthetic guest source\n')
        self.source_archive.unlink()
        identity = source_identity.archive_source(self.source, self.source_archive)
        self.selection['source'] = pinned(self.source_archive, self.inputs, tree_sha256=identity['tree_sha256'])
        package = container.build_package({'binary/application.wasm': wasm_fixture()}, self.configuration['application'],
            binary_entry='binary/application.wasm', binary_profile=container.BINARY_PROFILE,
            identities={'source_tree': identity['tree_sha256']})
        payload = self.inputs / 'application.sfapp'
        payload.write_bytes(container.encode_package(package))
        self.selection['payload'] = pinned(payload, self.inputs)
        document(self.selection_path, self.selection)
        self.candidate = self.root / 'binary-candidate'
        self.pin = appended_release.prepare_release(self.selection_path, self.candidate)['candidate_sha256']
        with self.assertRaisesRegex(ValueError, 'guest-source'):
            self.freeze()
        self.policy['profiles']['synthetic']['checks'].append({'id': 'guest', 'artifact': None,
            'scope': 'guest-source', 'target': 'portable-wasm32', 'backend': 'guest',
            'environment': 'sdk-host', 'assertions': ['guest-source']})
        self.checks = self.new_checks()
        plan = self.freeze()
        reports = self.reports(plan)
        self.assertTrue(self.certify(plan, reports)['eligible_for_publication'])
        guest_report = reports[-1]
        receipt_path = guest_report.parent / 'qualification.json'
        receipt = json.loads(receipt_path.read_bytes())
        original_receipt = copy.deepcopy(receipt)
        receipt['evidence'].pop('guest.junit.xml')
        document(receipt_path, receipt)
        result = json.loads(guest_report.read_bytes())
        original_result = copy.deepcopy(result)
        result['evidence'].pop('guest.junit.xml')
        document(guest_report, result)
        self.refresh_report(guest_report)
        with self.assertRaisesRegex(ValueError, 'guest'):
            self.certify(plan, reports)
        guest_junit = guest_report.parent / 'guest.junit.xml'
        guest_junit.write_text('<testsuite><testcase name="guest-source"><skipped/></testcase></testsuite>')
        original_receipt['evidence']['guest.junit.xml'] = dependency_archive.digest(guest_junit)
        document(receipt_path, original_receipt)
        document(guest_report, original_result)
        self.refresh_report(guest_report)
        with self.assertRaisesRegex(ValueError, 'skipped'):
            self.certify(plan, reports)


if __name__ == '__main__':
    unittest.main()
