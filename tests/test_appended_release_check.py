"""Focused offline byte gates and retained-runtime adapter observations.

The native container vector is structural ELF, never an executable test program.
Tests mock only the physical launch boundary when qualifying that vector. A
separate supervisor test executes an ordinary Python script without presenting it
as a native composition or invoking a compiler/build/install operation.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_container as container
import appended_policy as policy
import appended_project as project
import appended_release as release
import appended_release_check as check
import artifact
import dependency_archive as archive
import source_identity


def document(path, value):
    path.write_bytes(container.canonical_json(value))


def pin(path, **extra):
    return {'path': path.name, 'sha256': archive.digest(path), **extra}


def elf_prefix():
    content = bytearray(4096)
    content[:16] = b'\x7fELF\x02\x01\x01' + bytes(9)
    struct.pack_into('<HHIQQQIHHHHHH', content, 16, 2, 62, 1, 256, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into('<IIQQQQQQ', content, 64, 1, 5, 0, 0x400000, 0, 4096, 4096, 4096)
    content[256:272] = container.STAMP_MAGIC + struct.pack('<Q', len(content))
    return bytes(content)


@unittest.skipUnless(os.name == 'posix', 'POSIX exact-mode fixture; Windows runtime adapter is unavailable')
class CheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='appended check tests ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        source = self.root / 'source'
        (source / 'src').mkdir(parents=True)
        (source / 'src/kernel.cpp').write_text('retained native kernel source\n')
        configuration = project.default_document()
        self.application = {'id': 'org.example.retained', 'name': 'Retained fixture', 'version': '1.0.0'}
        configuration['application'] = self.application
        document(source / project.CONFIG_NAME, configuration)
        source_archive = self.inputs / 'source.tar.gz'
        identity = source_identity.archive_source(source, source_archive)
        self.prefix = elf_prefix()
        self.descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'elf',
                           'profile': 'minimal', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
                           'capabilities': [], 'services': [], 'executable': {'length': len(self.prefix),
                           'sha256': container.digest(self.prefix)}, 'boundary_offset': 256,
                           'provenance': {'producer': 'structural-test-vector'},
                           'kernel_inputs': policy.kernel_source_tree(source)}
        descriptor_path = self.inputs / 'kernel.json'
        document(descriptor_path, self.descriptor)
        base = self.inputs / 'base.tar.gz'
        self.members = {'bin/retained-runtime': (self.prefix, 0o755),
                        'share/build-info.txt': (b'original producer\n', 0o640)}
        self.directories = {'bin': 0o755, 'share': 0o750, 'empty': 0o700}
        release._write_archive(base, self.members, self.directories)
        inventory = self.inputs / 'base.inventory.json'
        described = artifact.describe(base)
        described['modes'] = release._mode_inventory(self.members)
        document(inventory, described)
        recovery = self.inputs / 'recovery-inputs'
        recovery.write_bytes(b'explicit original recovery inputs; no reconstruction claim')
        selection = {'schema_version': 1, 'kind': 'foundation-appended-selection',
                     'application': self.application, 'source': pin(source_archive, tree_sha256=identity['tree_sha256']),
                     'payload': None, 'kernels': [{'id': 'linux-x86_64-terminal', 'archive': pin(base),
                     'inventory': pin(inventory), 'descriptor': pin(descriptor_path),
                     'runtime_member': 'bin/retained-runtime', 'output': 'retained-linux.tar.gz',
                     'original_source': pin(source_archive, tree_sha256=identity['tree_sha256']),
                     'recovery': [pin(recovery)], 'evidence': []}]}
        selected = self.inputs / 'selection.json'
        document(selected, selection)
        self.candidate = self.root / 'candidate'
        with self.forbid_processes():
            self.result = release.prepare_release(selected, self.candidate)
        self.candidate_pin = self.result['candidate_sha256']
        self.composition = json.loads((self.candidate / 'composition.json').read_bytes())
        self.entry = self.composition['artifacts'][0]
        self.scenario = self.root / 'scenario.json'
        self.scenario_data = {'schema_version': 1, 'kind': 'foundation-appended-runtime-scenario',
                              'candidate_sha256': self.candidate_pin, 'artifact_id': self.entry['id'],
                              'target': 'linux-x86_64', 'backend': 'terminal',
                              'calls': [{'id': 'retained-self-check', 'argv': ['--self-check', 'path with spaces'],
                                         'exit_code': 0, 'stdout': 'retained scenario passed\n', 'stderr': ''},
                                        {'id': 'retained-rejection', 'argv': ['--invalid'], 'exit_code': 2,
                                         'stdout': '', 'stderr': 'invalid request\n'}]}
        document(self.scenario, self.scenario_data)
        self.context = {'FOUNDATION_PLAN_ID': 'a' * 64, 'FOUNDATION_CHECK_ID': 'retained-check',
                        'FOUNDATION_RUN_ID': 'unit-fixture', 'FOUNDATION_RUN_ATTEMPT': '2',
                        'FOUNDATION_COMPOSITION_POLICY_SHA256': 'b' * 64, 'FOUNDATION_COMPOSITION_PROFILE': 'binary'}
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.context).start()

    def forbid_processes(self):
        stack = ExitStack()
        for name in ('run', 'Popen', 'call', 'check_call', 'check_output'):
            stack.enter_context(patch.object(subprocess, name, side_effect=AssertionError('unexpected process: ' + name)))
        return stack

    def qualify(self, scope='composition-integrity', name='evidence', **options):
        target, backend = ('linux-x86_64', 'terminal') if scope == 'retained-runtime' else ('composition', 'none')
        return check.check(self.candidate, self.candidate_pin, target, backend, scope,
                           self.root / name, **options)

    def runtime(self, name='runtime-evidence', **options):
        return self.qualify('retained-runtime', name, artifact_id=self.entry['id'],
                            scenario=self.scenario, scenario_sha256=archive.digest(self.scenario), **options)

    def observed_execution(self, argv, cwd, destination, environment, timeout):
        runtime = Path(argv[0])
        self.assertEqual(runtime.name, 'retained-runtime')
        self.assertEqual(runtime.parent.name, 'bin')
        self.assertIn('relocated final archive with spaces', str(runtime))
        self.assertEqual(runtime.read_bytes(), self.prefix)
        self.assertEqual(archive.digest(runtime), self.entry['runtime_sha256'])
        self.assertEqual(runtime.stat().st_mode & 0o777, 0o755)
        self.assertIn(' ', str(cwd))
        self.assertNotIn('LD_LIBRARY_PATH', environment)
        call = next(value for value in self.scenario_data['calls'] if value['argv'] == argv[1:])
        for filename, data in (('stdout.bin', call['stdout'].encode()), ('stderr.bin', call['stderr'].encode()),
                               ('supervisor.log', b'owned capture fixture\n')):
            (destination / filename).write_bytes(data)
        document(destination / 'native.json', {'argv': argv, 'exit_code': call['exit_code']})
        return {'argv': argv, 'exit_code': call['exit_code'], 'stdout': call['stdout'].encode(),
                'stderr': call['stderr'].encode(), 'seconds': 0.001, 'process_tree_joined': True}

    def host(self):
        return dict(check.c.host_identity(), system='Linux', machine='x86_64')

    def test_global_integrity_checks_entire_subject_and_emits_bound_receipt(self):
        with self.forbid_processes():
            receipt = self.qualify()
        self.assertEqual(receipt['status'], 'passed')
        self.assertEqual(receipt['source_sha256'], self.composition['source']['sha256'])
        self.assertEqual(receipt['inventory_sha256'], self.candidate_pin)
        self.assertEqual(receipt['assertions'], check.ASSERTIONS['composition-integrity'])
        self.assertEqual(receipt['details']['candidate_sha256'], self.candidate_pin)
        self.assertEqual(receipt['details']['composition_sha256'], archive.digest(self.candidate / 'composition.json'))
        self.assertEqual(receipt['details']['qualification_policy_sha256'], 'b' * 64)
        self.assertEqual(receipt['details']['plan'], 'a' * 64)
        self.assertEqual(receipt['details']['check'], 'retained-check')
        self.assertEqual(receipt['details']['attempt'], 2)
        self.assertEqual(receipt['host'], check.c.host_identity())
        self.assertEqual(receipt['details']['mode'], 'neither')
        self.assertIn('qualification.junit.xml', receipt['evidence'])
        self.assertEqual(set(receipt['details']['checker_sources']), set(check.tool_source_catalog(['composition-integrity'])))
        for name, expected in receipt['details']['checker_sources'].items():
            self.assertEqual(receipt['evidence']['checker-sources/' + name], expected)
        for name, expected in receipt['evidence'].items():
            self.assertEqual(archive.digest(self.root / 'evidence' / name), expected)
        check.c.junit(self.root / 'evidence/qualification.junit.xml', check.ASSERTIONS['composition-integrity'])

    def test_offline_recompose_reproduces_candidate_without_processes(self):
        with self.forbid_processes():
            receipt = self.qualify('offline-recompose')
        self.assertEqual(receipt['assertions'], check.ASSERTIONS['offline-recompose'])
        self.assertEqual(receipt['details']['recomposition']['candidate_sha256'], self.candidate_pin)
        self.assertFalse(receipt['details']['recomposition']['network_permitted'])
        self.assertFalse(receipt['details']['recomposition']['processes_permitted'])
        self.assertFalse(receipt['details']['recomposition']['native_reconstruction'])

    def test_offline_recompose_audit_rejects_attempted_process_even_if_swallowed(self):
        recover = release.recover

        def attempted(*args):
            try:
                subprocess.run([sys.executable, '-c', 'raise SystemExit(0)'])
            except ValueError:
                pass
            return recover(*args)

        with patch.object(release, 'recover', side_effect=attempted), \
                self.assertRaisesRegex(ValueError, 'forbidden operation'):
            self.qualify('offline-recompose')
        self.assertFalse((self.root / 'evidence/qualification.json').exists())
        self.assertIn('exact-recomposition', (self.root / 'evidence/qualification.junit.xml').read_text())

    def test_native_execution_uses_exact_extracted_runtime_and_frozen_calls(self):
        host = self.host()
        with patch.object(check.c, 'host_identity', return_value=host), \
                patch.object(check, '_execute_runtime', side_effect=self.observed_execution) as execute:
            receipt = self.runtime()
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(receipt['assertions'], check.ASSERTIONS['retained-runtime'])
        self.assertEqual(receipt['details']['runtime']['scenario_sha256'], archive.digest(self.scenario))
        self.assertEqual(receipt['details']['scenario_sha256'], archive.digest(self.scenario))
        self.assertEqual(receipt['details']['runtime']['runtime_before_sha256'], self.entry['runtime_sha256'])
        self.assertEqual(receipt['details']['runtime']['runtime_after_sha256'], self.entry['runtime_sha256'])
        self.assertEqual([call['exit_code'] for call in receipt['details']['runtime']['calls']], [0, 2])
        self.assertEqual(receipt['host'], host)
        evidence = self.root / 'runtime-evidence'
        for name in ('runtime/before.json', 'runtime/after.json', 'runtime/scenario.json',
                     'runtime/retained-self-check/stdout.bin', 'runtime/retained-rejection/stderr.bin',
                     'runtime/calls.junit.xml'):
            self.assertEqual(receipt['evidence'][name], archive.digest(evidence / name))
        self.assertEqual(json.loads((evidence / 'runtime/before.json').read_bytes()),
                         json.loads((evidence / 'runtime/after.json').read_bytes()))
        check.c.junit(evidence / 'runtime/calls.junit.xml', ['retained-self-check', 'retained-rejection'])

    def test_native_wrong_exit_or_output_is_failure_without_passing_receipt(self):
        host = self.host()
        for changed in ('exit_code', 'stdout', 'stderr', 'process_tree_joined', 'argv'):
            with self.subTest(changed=changed):
                def wrong(*args):
                    result = self.observed_execution(*args)
                    result[changed] = {'exit_code': 9, 'stdout': b'wrong', 'stderr': b'wrong',
                                       'process_tree_joined': False, 'argv': ['/unrelated/command']}[changed]
                    return result
                name = 'wrong-' + changed
                expected_error = check.ProcessTreeError if changed == 'process_tree_joined' else ValueError
                with patch.object(check.c, 'host_identity', return_value=host), \
                        patch.object(check, '_execute_runtime', side_effect=wrong), self.assertRaises(expected_error):
                    self.runtime(name)
                self.assertFalse((self.root / name / 'qualification.json').exists())
                if changed == 'process_tree_joined':
                    retained = json.loads((self.root / name / 'retained-work.json').read_bytes())
                    self.addCleanup(shutil.rmtree, retained['workspace'], True)
                    self.assertFalse((self.root / name / 'failure.json').exists())
                else:
                    self.assertTrue((self.root / name / 'failure.json').is_file())

    def test_runtime_mutation_is_detected_after_execution(self):
        host = self.host()
        def mutate(*args):
            result = self.observed_execution(*args)
            if args[0][1:] == self.scenario_data['calls'][-1]['argv']:
                Path(args[0][0]).write_bytes(b'changed after execution')
            return result
        with patch.object(check.c, 'host_identity', return_value=host), \
                patch.object(check, '_execute_runtime', side_effect=mutate), \
                self.assertRaisesRegex(ValueError, 'inventory changed'):
            self.runtime()
        self.assertFalse((self.root / 'runtime-evidence/qualification.json').exists())
        self.assertTrue((self.root / 'runtime-evidence/runtime/retained-rejection/after.json').exists())

    def test_intermediate_mutation_cannot_be_hidden_by_a_later_restoring_call(self):
        host = self.host()
        def mutate_then_restore(*args):
            # A second call would restore the original bytes. It must never run
            # after the first call changes the delivered dependency inventory.
            result = self.observed_execution(*args)
            library = Path(args[0][0]).parents[1] / 'share/build-info.txt'
            library.write_bytes(b'changed between native invocations' if args[0][1:] ==
                                self.scenario_data['calls'][0]['argv'] else self.members['share/build-info.txt'][0])
            return result
        with patch.object(check.c, 'host_identity', return_value=host), \
                patch.object(check, '_execute_runtime', side_effect=mutate_then_restore) as execute, \
                self.assertRaisesRegex(ValueError, 'inventory changed during call'):
            self.runtime()
        self.assertEqual(execute.call_count, 1)
        self.assertFalse((self.root / 'runtime-evidence/qualification.json').exists())

    def test_unconfirmed_close_preserves_workspace_and_defers_completion_evidence(self):
        class UnconfirmedOwner:
            def poll(self):
                return 0
            def wait(self):
                return 0
            def finish(self):
                return 0
            def close(self):
                raise subprocess.TimeoutExpired('unconfirmed-child', 0.01)
        host = self.host()
        with patch.object(check.c, 'host_identity', return_value=host), \
                patch.object(check, 'launch', return_value=UnconfirmedOwner()), \
                self.assertRaisesRegex(check.ProcessTreeError, 'retain output ownership'):
            self.runtime()
        evidence = self.root / 'runtime-evidence'
        retained = json.loads((evidence / 'retained-work.json').read_bytes())
        work = Path(retained['workspace'])
        self.addCleanup(shutil.rmtree, work)
        self.assertTrue((work / 'relocated final archive with spaces/bin/retained-runtime').exists())
        for name in ('qualification.json', 'qualification.junit.xml', 'failure.json', 'runtime/calls.junit.xml'):
            self.assertFalse((evidence / name).exists(), name)

    def test_candidate_mutation_during_execution_is_detected(self):
        host = self.host()
        def mutate(*args):
            result = self.observed_execution(*args)
            (self.candidate / 'changed-input').write_bytes(b'changed candidate during execution')
            return result
        with patch.object(check.c, 'host_identity', return_value=host), \
                patch.object(check, '_execute_runtime', side_effect=mutate), \
                self.assertRaisesRegex(ValueError, 'inventory'):
            self.runtime()
        self.assertFalse((self.root / 'runtime-evidence/qualification.json').exists())

    def test_wrong_host_or_architecture_never_launches_structural_fixture(self):
        wrong = dict(self.host(), machine='aarch64')
        with patch.object(check.c, 'host_identity', return_value=wrong), \
                patch.object(check, '_execute_runtime') as execute, self.assertRaisesRegex(ValueError, 'actual native target'):
            self.runtime()
        execute.assert_not_called()

    def test_frozen_scenario_cannot_select_an_unrelated_command_or_candidate(self):
        cases = ('candidate', 'artifact', 'empty', 'command', 'duplicate', 'pin')
        host = self.host()
        for case in cases:
            with self.subTest(case=case):
                data = copy.deepcopy(self.scenario_data)
                if case == 'candidate':
                    data['candidate_sha256'] = '0' * 64
                elif case == 'artifact':
                    data['artifact_id'] = 'other-artifact'
                elif case == 'empty':
                    data['calls'] = []
                elif case == 'command':
                    data['calls'][0]['command'] = ['/bin/true']
                elif case == 'duplicate':
                    data['calls'].append(data['calls'][0])
                document(self.scenario, data)
                with patch.object(check.c, 'host_identity', return_value=host), \
                        patch.object(check, '_execute_runtime') as execute, self.assertRaises(ValueError):
                    self.qualify('retained-runtime', 'scenario-' + case, artifact_id=self.entry['id'],
                                 scenario=self.scenario,
                                 scenario_sha256='0' * 64 if case == 'pin' else archive.digest(self.scenario))
                execute.assert_not_called()

    def test_binary_runtime_requires_a_successful_call_that_enters_the_application(self):
        subject = release.verify_composition_subject(self.candidate, self.candidate_pin)
        subject = copy.deepcopy(subject)
        subject['composition']['payload']['mode'] = 'binary'
        original = copy.deepcopy(self.scenario_data)
        for argv, exit_code in ((['--help'], 0), (['--inspect'], 0), (['--invalid'], 2),
                                (['--self-check', 'unrecognized-extra'], 0)):
            value = copy.deepcopy(original)
            value['calls'] = [dict(value['calls'][0], argv=argv, exit_code=exit_code)]
            document(self.scenario, value)
            with self.subTest(argv=argv), self.assertRaisesRegex(ValueError, 'positive application call'):
                check._scenario(self.scenario, archive.digest(self.scenario), subject,
                                self.entry, 'linux-x86_64', 'terminal')
        for argv in (['--help', '--dispatch', 'value'], ['--dispatch', 'value', '--help'],
                     ['--inspect', '--provider', 'org.example.increment'],
                     ['--provider', 'org.example.increment', '--inspect'],
                     ['--expect-mode', '--help', '--dispatch', 'value'],
                     ['--provider', '--help'], ['--dispatch-hex', '--help'],
                     ['--dispatch', 'value', '--provider-operation', '1'],
                     ['--provider-operation', '--help', '--provider', 'org.example.increment'],
                     ['--provider-operation', '4294967296', '--provider', 'org.example.increment'],
                     ['--dispatch', 'value', '--provider', 'org.example.increment']):
            with self.subTest(rejected_core_argv=argv):
                self.assertFalse(check.positive_application_call(argv, 0, 'core'))
        for backend, argv in (('terminal', ['--self-check']), ('terminal', ['--smoke-test']),
                              ('core', ['--provider', 'org.example.increment']),
                              ('core', ['--expect-mode', 'binary', '--provider', 'org.example.increment']),
                              ('core', ['--dispatch', '--help']),
                              ('core', ['--dispatch', '--inspect']),
                              ('core', ['--provider-operation', '1', '--provider', 'org.example.increment']),
                              ('core', ['--provider-operation', '00000000000001', '--provider', 'org.example.increment']),
                              ('core', ['--dispatch-hex', '00'])):
            value = copy.deepcopy(original)
            value['backend'] = backend
            value['calls'] = [dict(value['calls'][0], argv=argv, exit_code=0)]
            document(self.scenario, value)
            with self.subTest(backend=backend, argv=argv):
                _, parsed = check._scenario(self.scenario, archive.digest(self.scenario), subject,
                                             self.entry, 'linux-x86_64', backend)
                self.assertEqual(parsed['calls'][0]['argv'], argv)

    def test_browser_instrument_requires_all_proven_gates_and_exact_code_sources(self):
        context = {'passed': [], 'checker_sources': {'tools/appended_browser_check.py': 'a' * 64}}
        def incomplete(scope, current):
            self.assertEqual(scope, 'browser')
            current['passed'].extend(check.ASSERTIONS['browser'][:-1])
            return {'checker_sources': dict(current['checker_sources'])}

        with patch.object(check, '_adapter', side_effect=incomplete), self.assertRaisesRegex(ValueError, 'assertion inventory'):
            check._browser_context(context)
        context['passed'] = []
        def wrong_sources(scope, current):
            current['passed'].extend(check.ASSERTIONS['browser'])
            return {'checker_sources': {}}
        with patch.object(check, '_adapter', side_effect=wrong_sources), self.assertRaisesRegex(ValueError, 'source closure'):
            check._browser_context(context)

    def test_candidate_tampering_and_extra_files_fail_before_qualification(self):
        (self.candidate / 'unlisted').write_text('foreign byte')
        with self.forbid_processes(), self.assertRaisesRegex(ValueError, 'inventory'):
            self.qualify()
        self.assertFalse((self.root / 'evidence').exists())

    def test_scope_prerequisites_and_global_artifact_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'no self-verifying adapter'):
            self.qualify('unknown-scope')
        for scope in ('browser', 'guest-source', 'install-upgrade'):
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, 'requires'):
                self.qualify(scope)
        with self.assertRaisesRegex(ValueError, 'global byte checks'):
            self.qualify(artifact_id=self.entry['id'])

    def test_before_run_tool_pins_reject_changed_or_incomplete_source_closure(self):
        frozen = {name: archive.digest(ROOT / name) for name in check.tool_source_catalog(['composition-integrity'])}
        for attack in ('hash', 'missing', 'unknown'):
            changed = dict(frozen)
            if attack == 'hash':
                changed['tools/appended_release_check.py'] = '0' * 64
            elif attack == 'missing':
                changed.pop('tools/process_tree.py')
            else:
                changed['tools/unreviewed.py'] = '0' * 64
            with self.subTest(attack=attack), patch.dict(os.environ, {
                    'FOUNDATION_COMPOSITION_TOOL_SOURCES': container.canonical_json(changed).decode()}):
                with self.assertRaisesRegex(ValueError, 'source|tool pin'):
                    self.qualify(name='rejected-' + attack)
                self.assertFalse((self.root / ('rejected-' + attack)).exists())

    def test_extension_cannot_overwrite_bindings_or_claim_unexecuted_assertions(self):
        def binding_override(scope, context):
            self.assertEqual(scope, 'guest-source')
            self.assertEqual(context['subject']['candidate_sha256'], self.candidate_pin)
            self.assertEqual(context['execution_context']['run_id'], 'unit-fixture')
            self.assertIn('runtime', context['helpers'])
            context['passed'].extend(check.ASSERTIONS[scope])
            return {'candidate_sha256': '0' * 64}

        for name, adapter, message in (('binding', binding_override, 'immutable execution'),
                                       ('assertions', lambda scope, context: {}, 'assertion inventory')):
            evidence = self.root / name
            with patch.object(check, '_adapter', side_effect=adapter), self.assertRaisesRegex(ValueError, message):
                check.check(self.candidate, self.candidate_pin, 'portable-wasm32', 'guest', 'guest-source', evidence,
                            scenario=self.scenario, scenario_sha256=archive.digest(self.scenario))
            self.assertFalse((evidence / 'qualification.json').exists())

    def test_returned_incomplete_join_retains_workspace_without_completion_receipt(self):
        def incomplete(*args):
            return dict(self.observed_execution(*args), process_tree_joined=False)

        with patch.object(check.c, 'host_identity', return_value=self.host()), \
                patch.object(check, '_execute_runtime', side_effect=incomplete), \
                self.assertRaises(check.ProcessTreeError):
            self.runtime()
        evidence = self.root / 'runtime-evidence'
        retained = json.loads((evidence / 'retained-work.json').read_bytes())
        workspace = Path(retained['workspace'])
        self.addCleanup(shutil.rmtree, workspace, True)
        self.assertTrue(workspace.is_dir())
        self.assertFalse((evidence / 'qualification.json').exists())
        self.assertFalse((evidence / 'qualification.junit.xml').exists())

    def test_checker_source_replacement_during_check_prevents_receipt(self):
        source = self.root / 'checker-source.py'
        source.write_bytes(b'reviewed checker source')
        saved = container._snapshot(source)
        snapshots = {'tools/appended_release_check.py': saved}
        pins = {'tools/appended_release_check.py': container.digest(saved.content)}
        original = check._subject
        calls = 0

        def replace_before_recheck(*args):
            nonlocal calls
            result = original(*args)
            calls += 1
            if calls == 2:
                alternate = self.root / 'replacement.py'
                alternate.write_bytes(source.read_bytes())
                alternate.replace(source)
            return result

        with patch.object(check, '_checker_sources', return_value=(snapshots, pins)), \
                patch.object(check, '_subject', side_effect=replace_before_recheck), \
                self.assertRaisesRegex(ValueError, 'changed'):
            self.qualify()
        self.assertFalse((self.root / 'evidence/qualification.json').exists())

    def test_incomplete_frozen_context_and_reused_evidence_are_rejected(self):
        with patch.dict(os.environ, {'FOUNDATION_COMPOSITION_PROFILE': ''}), \
                self.assertRaisesRegex(ValueError, 'complete frozen'):
            self.qualify()
        self.qualify()
        before = (self.root / 'evidence/qualification.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'new for this attempt'):
            self.qualify()
        self.assertEqual((self.root / 'evidence/qualification.json').read_bytes(), before)


class CaptureBoundaryTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux') or os.name == 'nt', 'qualified process-tree hosts only')
    def test_supervised_capture_preserves_separate_complete_outputs_and_native_exit(self):
        with tempfile.TemporaryDirectory(prefix='retained capture boundary ') as temporary:
            work = Path(temporary)
            script = work / 'ordinary offline script.py'
            script.write_text('import sys\nsys.stdout.buffer.write(b"actual stdout\\n")\nsys.stderr.buffer.write(b"actual stderr\\n")\nraise SystemExit(7)\n')
            calls = work / 'captures'
            calls.mkdir()
            environment = check._environment(work)
            argv = [sys.executable, str(script)]
            result = check._execute_runtime(argv, work, calls, environment, 5)
            self.assertEqual(result['argv'], argv)
            self.assertEqual(result['exit_code'], 7)
            self.assertEqual(result['stdout'], b'actual stdout\n')
            self.assertEqual(result['stderr'], b'actual stderr\n')
            self.assertTrue(result['process_tree_joined'])
            self.assertEqual((calls / 'stdout.bin').read_bytes(), result['stdout'])
            self.assertEqual((calls / 'stderr.bin').read_bytes(), result['stderr'])
            self.assertEqual(json.loads((calls / 'native.json').read_bytes())['exit_code'], 7)

    @unittest.skipUnless(sys.platform.startswith('linux') or os.name == 'nt', 'qualified process-tree hosts only')
    def test_capture_timeout_joins_owned_process_tree(self):
        with tempfile.TemporaryDirectory(prefix='retained capture timeout ') as temporary:
            work = Path(temporary)
            script = work / 'bounded wait.py'
            script.write_text('import time\ntime.sleep(10)\n')
            captures = work / 'captures'
            captures.mkdir()
            environment = check._environment(work)
            with self.assertRaisesRegex(ValueError, 'time/output limit'):
                check._execute_runtime([sys.executable, str(script)], work, captures, environment, 0.1)

    @unittest.skipUnless(sys.platform.startswith('linux') or os.name == 'nt', 'qualified process-tree hosts only')
    def test_surviving_child_prevents_successful_execution_observation(self):
        with tempfile.TemporaryDirectory(prefix='retained child lifetime ') as temporary:
            work = Path(temporary)
            script = work / 'starts child.py'
            script.write_text('import subprocess, sys\nsubprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])\n')
            captures = work / 'captures'
            captures.mkdir()
            environment = check._environment(work)
            with self.assertRaisesRegex(check.ProcessTreeError, 'descendants outlived'):
                check._execute_runtime([sys.executable, str(script)], work, captures, environment, 5)


if __name__ == '__main__':
    unittest.main()
