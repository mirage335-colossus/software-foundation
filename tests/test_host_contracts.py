"""Installed runtime selection and fail-closed repeated diagnostic evidence."""
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('host_contracts', ROOT / 'tools/host_contracts.py')
HOST = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HOST)


class HostContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='host-contract-fixture-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = 'windows-x86_64' if platform.system() == 'Windows' else (
            'linux-aarch64' if HOST.architecture(platform.machine()) == 'arm64' else 'linux-x86_64')

    def cache(self, version, arch='x64', system='Windows', complete=True):
        folder = self.root / 'Python' / version / arch
        executable = folder / ('python.exe' if system == 'Windows' else 'bin/python')
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_bytes(b'fixture Python executable')
        if complete:
            (folder.parent / (arch + '.complete')).touch()
        return executable.resolve()

    def metadata(self, executable):
        return dict(executable=str(executable), version='3.12.10 fixture', version_info=[3, 12, 10],
                    implementation='cpython', system='Windows', machine='AMD64', bits=64, optimize=0)

    def receipt(self, status='passed'):
        return {'schema_version': 1, 'system': platform.system(), 'status': status,
                'inventory': ['fixture.one', 'fixture.other_platform'],
                'excluded': {'fixture.other_platform': 'different host'},
                'results': {'fixture.one': {'status': status}}}

    def test_cache_selects_highest_complete_stable_patch_of_requested_architecture(self):
        expected = self.cache('3.12.10')
        self.cache('3.12.9'); self.cache('3.12.99', complete=False)
        self.cache('3.12.20', arch='arm64'); self.cache('3.12.11rc1'); self.cache('3.14.7')
        with mock.patch.object(HOST.platform, 'system', return_value='Windows'), \
             mock.patch.object(HOST.platform, 'machine', return_value='AMD64'):
            self.assertEqual(HOST.interpreter('3.12', 'windows-x86_64', {'RUNNER_TOOL_CACHE': str(self.root)}), expected)
            self.assertEqual(HOST.interpreter('3.14', 'windows-x86_64', {'RUNNER_TOOL_CACHE': str(self.root)}),
                             (self.root / 'Python/3.14.7/x64/python.exe').resolve())

    def test_linux_arm_cache_uses_native_bin_python(self):
        expected = self.cache('3.14.7', 'arm64', 'Linux')
        self.cache('3.14.8', 'x64', 'Linux')
        with mock.patch.object(HOST.platform, 'system', return_value='Linux'), \
             mock.patch.object(HOST.platform, 'machine', return_value='aarch64'):
            self.assertEqual(HOST.interpreter('3.14', 'linux-aarch64', {'RUNNER_TOOL_CACHE': str(self.root)}), expected)

    def test_missing_explicit_version_never_falls_back_to_default_or_download(self):
        self.cache('3.12.10')
        with mock.patch.object(HOST.platform, 'system', return_value='Windows'), \
             mock.patch.object(HOST.platform, 'machine', return_value='AMD64'), \
             mock.patch.object(HOST.subprocess, 'run') as run:
            for environment in ({}, {'RUNNER_TOOL_CACHE': str(self.root)}):
                with self.subTest(environment=environment), self.assertRaises(ValueError):
                    HOST.interpreter('3.14', 'windows-x86_64', environment)
            run.assert_not_called()

    def test_default_and_mismatched_host_are_explicit(self):
        self.assertEqual(HOST.interpreter('runner-default', self.target, {}), Path(sys.executable).resolve())
        with mock.patch.object(HOST.platform, 'system', return_value='Linux'), \
             mock.patch.object(HOST.platform, 'machine', return_value='aarch64'):
            with self.assertRaisesRegex(ValueError, 'native host'):
                HOST.interpreter('3.12', 'windows-x86_64', {})

    def test_runtime_probe_binds_actual_executable_architecture_version_and_hash(self):
        executable = self.cache('3.12.10')
        value = self.metadata(executable)
        with mock.patch.object(HOST.subprocess, 'run', return_value=mock.Mock(stdout=json.dumps(value))) as run:
            actual = HOST.inspect_runtime(executable, '3.12', 'windows-x86_64')
            self.assertEqual(actual['sha256'], HOST.digest(executable))
            self.assertEqual(actual['version_info'], [3, 12, 10])
            self.assertEqual(run.call_args.kwargs['timeout'], 15)
        for changes in ({'version_info': [3, 14, 7]}, {'bits': 32}, {'machine': 'ARM64'},
                        {'system': 'Linux'}, {'optimize': 1}, {'implementation': 'pypy'},
                        {'executable': str(self.root)}):
            with self.subTest(changes=changes), mock.patch.object(HOST.subprocess, 'run',
                    return_value=mock.Mock(stdout=json.dumps(dict(value, **changes)))), self.assertRaises(ValueError):
                HOST.inspect_runtime(executable, '3.12', 'windows-x86_64')

    def execute(self, launch, count=5):
        executable = Path(sys.executable).resolve()
        metadata = {'sha256': HOST.digest(executable), 'version': sys.version}
        with mock.patch.object(HOST, 'interpreter', return_value=executable), \
             mock.patch.object(HOST, 'inspect_runtime', return_value=metadata), \
             mock.patch.object(HOST.process_tree, 'launch', side_effect=launch):
            return HOST.execute(self.target, 'process_tree', 'runner-default', count, self.root / 'evidence', {})

    def test_failure_remains_failed_after_later_passes_and_every_inventory_is_retained(self):
        owners = []
        def launch(command, cwd, stream, env):
            status = 'failed' if not owners else 'passed'
            report = Path(command[-1]); HOST.run_tests.publish(report, self.receipt(status))
            self.assertEqual(Path(env['TMP']), report.parent / 'scratch')
            stream.write(status.encode())
            owner = mock.Mock(); owner.wait.return_value = 1 if status == 'failed' else 0
            owners.append(owner)
            return owner
        result = self.execute(launch)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual([row['status'] for row in result['repetitions']], ['failed'] + ['passed'] * 4)
        self.assertEqual(len(list((self.root / 'evidence/repetitions').glob('*/cases.json'))), 5)
        self.assertTrue(result['writers_stopped'])
        self.assertIn('*/console.log', HOST.retained_paths(self.root / 'evidence'))
        self.assertFalse(result['release_qualification'])
        self.assertEqual(result['kind'], 'host-contract-diagnostic')
        for owner in owners:
            owner.wait.assert_called_once_with(timeout=HOST.CASE_SECONDS)
            owner.finish.assert_called_once_with(); owner.close.assert_called_once_with()

    def test_timeout_stops_and_joins_before_next_repetition_and_remains_failed(self):
        owners = []
        def launch(command, cwd, stream, env):
            if owners:
                owners[-1].close.assert_called_once_with()
            owner = mock.Mock()
            if not owners:
                owner.wait.side_effect = subprocess.TimeoutExpired(command, 120)
            else:
                owner.wait.return_value = 0
                HOST.run_tests.publish(Path(command[-1]), self.receipt())
            owners.append(owner)
            return owner
        result = self.execute(launch)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(result['repetitions']), 5)
        owners[0].terminate.assert_called_once_with(); owners[0].close.assert_called_once_with()
        self.assertIn('bounded execution', result['repetitions'][0]['error'])

    def test_uncertain_cleanup_stops_later_repetitions_and_records_failure(self):
        owner = mock.Mock(); owner.wait.return_value = 0
        owner.close.side_effect = HOST.process_tree.ProcessTreeError('writer exit unconfirmed')
        launch = mock.Mock(return_value=owner)
        result = self.execute(launch)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('writer exit unconfirmed', result['error'])
        launch.assert_called_once()
        self.assertEqual(result['repetitions'], [])
        self.assertFalse(result['writers_stopped'])
        self.assertEqual(HOST.retained_paths(self.root / 'evidence'), (self.root / 'evidence/result.json').as_posix())

    def test_windows_retention_uses_portable_slashes_for_lifecycle_transport(self):
        class WindowsPath(PureWindowsPath):
            def read_text(self, **kwargs):
                return '{"writers_stopped":true}'
        with mock.patch.object(HOST, 'Path', WindowsPath):
            self.assertEqual(HOST.retained_paths('build/host-contracts'),
                'build/host-contracts/result.json\n'
                'build/host-contracts/repetitions/*/cases.json\n'
                'build/host-contracts/repetitions/*/console.log')

    def test_zero_exit_missing_inventory_or_internal_skip_cannot_pass(self):
        for receipt in (None, self.receipt('incomplete'), dict(self.receipt(), results={}),
                        dict(self.receipt(), inventory=['fixture.one', 'fixture.one'])):
            with self.subTest(receipt=receipt):
                folder = self.root / str(len(list(self.root.iterdir())))
                def launch(command, cwd, stream, env):
                    if receipt is not None:
                        HOST.run_tests.publish(Path(command[-1]), receipt)
                    owner = mock.Mock(); owner.wait.return_value = 0
                    return owner
                with mock.patch.object(HOST.process_tree, 'launch', side_effect=launch):
                    row = HOST.repetition(Path(sys.executable), 'process_tree', folder, 1, {})
                self.assertEqual(row['status'], 'failed')

    def test_setup_failure_is_retained_without_executing_any_cases(self):
        with mock.patch.object(HOST, 'interpreter', side_effect=ValueError('unavailable version')), \
             mock.patch.object(HOST, 'repetition') as run:
            result = HOST.execute(self.target, 'process_tree', '3.14', 20, self.root / 'evidence', {})
        self.assertEqual(result['status'], 'failed'); self.assertEqual(result['repetitions'], [])
        self.assertIn('unavailable version', result['error']); run.assert_not_called()
        self.assertEqual(json.loads((self.root / 'evidence/result.json').read_text()), result)

    def test_overall_deadline_preserves_completed_rows_but_fails_incomplete_run(self):
        clock = [0]
        def run(*args):
            clock[0] = 11
            return {'status': 'passed'}
        executable = Path(sys.executable).resolve()
        with mock.patch.object(HOST, 'interpreter', return_value=executable), \
             mock.patch.object(HOST, 'inspect_runtime', return_value={'sha256': HOST.digest(executable)}), \
             mock.patch.object(HOST, 'repetition', side_effect=run), \
             mock.patch.object(HOST, 'TOTAL_SECONDS', 10), \
             mock.patch.object(HOST.time, 'monotonic', side_effect=lambda: clock[0]):
            result = HOST.execute(self.target, 'process_tree', 'runner-default', 5, self.root / 'evidence', {})
        self.assertEqual(result['status'], 'failed'); self.assertEqual(len(result['repetitions']), 1)
        self.assertIn('remaining repetitions incomplete', result['error'])

    def test_arbitrary_commands_counts_and_reused_output_are_rejected(self):
        for target, suite, interpreter, count in ((self.target, '../run', '3.12', 1),
                (self.target, 'process_tree', '/tmp/python', 1), ('other', 'process_tree', '3.12', 1),
                (self.target, 'process_tree', '3.12', 2)):
            with self.subTest(suite=suite, count=count), self.assertRaises(ValueError):
                HOST.execute(target, suite, interpreter, count, self.root / 'new', {})
        with self.assertRaises(FileExistsError):
            HOST.execute(self.target, 'process_tree', 'runner-default', 1, self.root, {})


if __name__ == '__main__':
    unittest.main()
