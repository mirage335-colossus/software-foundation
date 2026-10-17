"""Supported first-native dispatch, with no compiler, SDK or native program.

These tests require the two explicit build.py namespace routes. They do not
install those routes, synthesize eligible inputs or run either cold producer.
"""
import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build
import process_tree


ROUTES = (
    ('native-engine-prototype', 'appended_engine_native_prototype', 'create_plan'),
    ('native-engine-dependencies', 'appended_engine_native_dependencies', 'make_plan'),
)
PIN = 'a' * 64


@contextlib.contextmanager
def forbid_other_work():
    """A namespace may only reach its selected producer's passive/mocked CLI."""
    with contextlib.ExitStack() as stack:
        for name in ('execute', 'run', 'require_clean', 'default_jobs', 'job_limits',
                     'native_rust_identity', 'rust_sdk_identity', 'host_programs',
                     'sdk_identity', 'engine_consumer_identity', 'cache_identity'):
            stack.enter_context(mock.patch.object(build, name, side_effect=AssertionError(
                'Native namespace entered ordinary selection/build: ' + name)))
        for name in ('run', 'check_call', 'check_output', 'Popen'):
            stack.enter_context(mock.patch.object(subprocess, name, side_effect=AssertionError(
                'Native dispatch fixture launched a subprocess: ' + name)))
        for owner, name in ((process_tree, 'launch'), (shutil, 'which'),
                            (os, 'system'), (os, 'execv'), (os, 'execve')):
            stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError(
                'Native dispatch fixture selected a program: ' + name)))
        alternates = {}
        for name in ('appended_engine_maintenance', 'appended_engine_document_maintenance',
                     'appended_engine_sdk', 'appended', 'appended_project'):
            module = ModuleType(name)
            module.main = mock.Mock(side_effect=AssertionError(
                'Native namespace fell through into another producer: ' + name))
            alternates[name] = module
        stack.enter_context(mock.patch.dict(sys.modules, alternates))
        yield


def options(action):
    if action == 'plan':
        return ['plan', '--selection', '/unexecuted inputs/é selection.json',
                '--selection-sha256', PIN, '--output=/unexecuted output/plan']
    return ['build', '--plan', '/unexecuted inputs/é plan.json',
            '--plan-sha256', PIN, '--output=/unexecuted output/build']


class NativeDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Repository-owned Python only; no retained SDK module is imported.
        cls.modules = {namespace: importlib.import_module(name)
                       for namespace, name, _ in ROUTES}

    def capture(self, function):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                status = function()
                exited = False
            except SystemExit as error:
                status, exited = error.code, True
        self.assertIs(type(status), int)
        return status, output.getvalue(), errors.getvalue(), exited

    def test_exact_remaining_arguments_and_status_zero_one_two_are_forwarded(self):
        for namespace, name, _ in ROUTES:
            for action in ('plan', 'build'):
                for status in (0, 1, 2):
                    with self.subTest(namespace=namespace, action=action, status=status):
                        selected = ModuleType(name)
                        selected.cli = mock.Mock(return_value=status)
                        arguments = [namespace, *options(action)]
                        original = list(arguments)
                        with forbid_other_work(), mock.patch.dict(sys.modules, {name: selected}):
                            actual = build.main(arguments)
                        self.assertIs(type(actual), int)
                        self.assertEqual(actual, status)
                        selected.cli.assert_called_once_with(original[1:])
                        self.assertEqual(arguments, original)

    def test_default_sys_argv_uses_the_same_explicit_routes(self):
        for namespace, name, _ in ROUTES:
            with self.subTest(namespace=namespace):
                selected = ModuleType(name)
                selected.cli = mock.Mock(return_value=2)
                arguments = [namespace, *options('plan')]
                with forbid_other_work(), mock.patch.dict(sys.modules, {name: selected}), \
                        mock.patch.object(sys, 'argv', ['build.py', *arguments]):
                    self.assertEqual(build.main(), 2)
                selected.cli.assert_called_once_with(arguments[1:])

    def test_unexpected_cli_exception_never_enters_an_alternate_builder(self):
        for namespace, name, _ in ROUTES:
            with self.subTest(namespace=namespace):
                selected = ModuleType(name)
                failure = RuntimeError('Fixture unexpected CLI failure')
                selected.cli = mock.Mock(side_effect=failure)
                with forbid_other_work(), mock.patch.dict(sys.modules, {name: selected}):
                    with self.assertRaises(RuntimeError) as raised:
                        build.main([namespace, *options('build')])
                self.assertIs(raised.exception, failure)
                selected.cli.assert_called_once()

    def test_namespace_matching_does_not_accept_nearby_names(self):
        for namespace, name, _ in ROUTES:
            selected = ModuleType(name)
            selected.cli = mock.Mock(side_effect=AssertionError('Nonexact namespace accepted'))
            for altered in (namespace + 's', namespace + '-extra', namespace.replace('-', '_')):
                with self.subTest(namespace=altered), forbid_other_work(), \
                        mock.patch.dict(sys.modules, {name: selected}):
                    status, output, error, exited = self.capture(
                        lambda: build.main([altered]))
                    self.assertEqual(status, 2)
                    self.assertTrue(exited)
                    self.assertEqual(output, '')
                    self.assertIn('invalid choice', error)
            selected.cli.assert_not_called()

    def test_real_cli_help_exits_zero_before_any_input_or_program_selection(self):
        for namespace, _, planner in ROUTES:
            module = self.modules[namespace]
            for arguments, expected in ((['--help'], 'plan'),
                                        (['plan', '--help'], '--selection-sha256'),
                                        (['build', '--help'], '--plan-sha256')):
                with self.subTest(namespace=namespace, arguments=arguments), forbid_other_work(), \
                        mock.patch.object(module, planner, side_effect=AssertionError('Help planned inputs')), \
                        mock.patch.object(module, 'build', side_effect=AssertionError('Help entered build')):
                    status, output, error, exited = self.capture(
                        lambda: build.main([namespace, *arguments]))
                    self.assertEqual(status, 0)
                    self.assertTrue(exited)
                    self.assertIn(expected, output)
                    self.assertEqual(error, '')

    def test_malformed_actions_missing_arguments_and_foreign_flags_exit_two(self):
        bad = ([], ['unknown'], ['plan'], ['build'],
               [*options('plan'), '--kernel-maintenance'],
               [*options('plan'), '--sdk', '/foreign/sdk'],
               [*options('build'), '--appended-profile', 'both'],
               [*options('build'), '--allow-missing'],
               [*options('build'), '--cold-fallback'])
        for namespace, _, planner in ROUTES:
            module = self.modules[namespace]
            for arguments in bad:
                with self.subTest(namespace=namespace, arguments=arguments), forbid_other_work(), \
                        mock.patch.object(module, planner, side_effect=AssertionError('Invalid CLI planned inputs')), \
                        mock.patch.object(module, 'build', side_effect=AssertionError('Invalid CLI built engine')):
                    status, output, error, exited = self.capture(
                        lambda: build.main([namespace, *arguments]))
                    self.assertEqual(status, 2)
                    self.assertTrue(exited)
                    self.assertEqual(output, '')
                    self.assertIn('error:', error)

    def missing_selection(self, root, namespace):
        """An ordinary tiny selection whose explicit input manifests are absent."""
        limits = {'prepare_seconds': 5, 'configure_seconds': 5, 'build_seconds': 5,
                  'cleanup_seconds': 1, 'maximum_jobs': 2,
                  'maximum_output_bytes': 1048576, 'minimum_free_bytes': 1,
                  'maximum_process_tree_bytes': 1048576}
        target = {'system': 'Linux', 'processor': 'x86_64',
                  'triple': 'x86_64-buildroot-linux-gnu', 'pointer_bits': 64}
        reference = lambda role: {'path': role + '-absent.json', 'sha256': PIN}
        if namespace == 'native-engine-prototype':
            selection = {'schema_version': 1,
                         'kind': 'foundation-native-engine-prototype-selection-v1',
                         'target': target, 'profile': 'document-actions-v1',
                         'phase_limits': limits}
            selection.update({role: reference(role) for role in
                              ('source_map', 'source_projection', 'toolchain',
                               'dependencies', 'host_tools', 'assets')})
            roles = {role + '-manifest' for role in
                     ('source_map', 'source_projection', 'toolchain',
                      'dependencies', 'host_tools', 'assets')}
        else:
            limits['maximum_jobs'] = 4
            selection = {'schema_version': 1,
                         'kind': 'foundation-native-engine-dependencies-selection-v1',
                         'target': target, 'phase_limits': limits,
                         **{role: reference(role) for role in
                            ('archives', 'toolchain', 'host_tools', 'assets')}}
            roles = {'native dependency source manifest'}
        raw = (json.dumps(selection, sort_keys=True, indent=2) + '\n').encode()
        path = root / 'selection.json'
        path.write_bytes(raw)
        path.chmod(0o644)
        return path, hashlib.sha256(raw).hexdigest(), roles

    def test_actual_absent_plan_inputs_match_direct_structured_two_without_outputs(self):
        for namespace, _, _ in ROUTES:
            module = self.modules[namespace]
            with self.subTest(namespace=namespace), tempfile.TemporaryDirectory(
                    prefix='native-dispatch-absent-') as temporary:
                root = Path(temporary).resolve()
                selection, pin, roles = self.missing_selection(root, namespace)
                output = root / 'never-created-output'
                arguments = ['plan', '--selection', str(selection),
                             '--selection-sha256', pin, '--output', str(output)]
                with forbid_other_work():
                    direct = self.capture(lambda: module.cli(arguments))
                    routed = self.capture(lambda: build.main([namespace, *arguments]))
                self.assertEqual(routed, direct)
                self.assertEqual(routed[0], 2)
                self.assertFalse(routed[3])
                self.assertEqual(routed[1], '')
                missing = json.loads(routed[2])
                self.assertEqual(missing['kind'], 'foundation-native-engine-prototype-missing-inputs-v1')
                self.assertEqual(missing['schema_version'], 1)
                self.assertIs(missing['executable_plan'], False)
                self.assertIs(missing['production_eligible'], False)
                self.assertEqual({item['role'] for item in missing['missing']}, roles)
                self.assertTrue(all(Path(item['path']).parent == root for item in missing['missing']))
                self.assertFalse(output.exists())
                self.assertEqual({path.name for path in root.iterdir()}, {'selection.json'})

    def test_missing_engine_prefix_never_selects_dependency_production(self):
        prototype = self.modules['native-engine-prototype']
        dependencies = self.modules['native-engine-dependencies']
        error = prototype.native_inputs.MissingInputs([{
            'role': 'native-prefix', 'path': '/explicit/missing/native-prefix',
            'reason': 'Complete retained native prefix absent; explicit maintenance required'}])
        with forbid_other_work(), \
                mock.patch.object(prototype.native_inputs, 'inspect_selection', side_effect=error) as inspected, \
                mock.patch.object(dependencies, 'cli', side_effect=AssertionError('Implicit dependency build')):
            status, output, diagnostics, exited = self.capture(
                lambda: build.main(['native-engine-prototype', *options('plan')]))
        self.assertEqual(status, 2)
        self.assertFalse(exited)
        self.assertEqual(output, '')
        self.assertEqual(json.loads(diagnostics), error.as_dict())
        inspected.assert_called_once()

    def test_real_missing_build_plan_matches_direct_one_without_sdk_or_output(self):
        for namespace, _, _ in ROUTES:
            module = self.modules[namespace]
            with self.subTest(namespace=namespace), tempfile.TemporaryDirectory(
                    prefix='native-dispatch-plan-') as temporary:
                root = Path(temporary).resolve()
                output = root / 'never-created-output'
                arguments = ['build', '--plan', str(root / 'absent-plan.json'),
                             '--plan-sha256', PIN, '--output', str(output)]
                with forbid_other_work():
                    direct = self.capture(lambda: module.cli(arguments))
                    routed = self.capture(lambda: build.main([namespace, *arguments]))
                self.assertEqual(routed, direct)
                self.assertEqual(routed[0], 1)
                self.assertFalse(routed[3])
                self.assertEqual(routed[1], '')
                self.assertIn('absent-plan.json', routed[2])
                self.assertFalse(output.exists())
                self.assertEqual(list(root.iterdir()), [])

    def test_build_os_value_and_process_tree_errors_preserve_one_and_diagnostic(self):
        for namespace, _, _ in ROUTES:
            module = self.modules[namespace]
            for failure in (ValueError('Fixture independent plan pin mismatch'),
                            OSError('Fixture retained file read failed'),
                            process_tree.ProcessTreeError('Fixture writers remain unconfirmed')):
                with self.subTest(namespace=namespace, failure=type(failure).__name__), \
                        forbid_other_work(), mock.patch.object(module, 'build', side_effect=failure) as attempted:
                    arguments = options('build')
                    direct = self.capture(lambda: module.cli(arguments))
                    routed = self.capture(lambda: build.main([namespace, *arguments]))
                    self.assertEqual(routed, direct)
                    self.assertEqual(routed[0], 1)
                    self.assertFalse(routed[3])
                    self.assertEqual(routed[1], '')
                    self.assertIn(str(failure), routed[2])
                    self.assertEqual(attempted.call_count, 2)  # One direct and one supported call; no retry.


if __name__ == '__main__':
    unittest.main(verbosity=2)
