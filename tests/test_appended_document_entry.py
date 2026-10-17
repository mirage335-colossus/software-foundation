"""Supported document producer dispatch; no fixture runs an engine or toolchain."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build
from process_tree import ProcessTreeError


@contextlib.contextmanager
def forbid_native_work():
    """A producer alias must not enter the ordinary application build graph."""
    with contextlib.ExitStack() as stack:
        for name in ('execute', 'run', 'native_rust_identity', 'rust_sdk_identity',
                     'host_programs', 'job_limits', 'sdk_identity'):
            stack.enter_context(patch.object(build, name, side_effect=AssertionError(
                'document route entered native selection: ' + name)))
        for name in ('run', 'check_call', 'check_output', 'Popen'):
            stack.enter_context(patch.object(subprocess, name, side_effect=AssertionError(
                'document route launched a subprocess: ' + name)))
        yield


class DocumentEntryTests(unittest.TestCase):
    def test_document_aliases_forward_exact_arguments_and_return_status(self):
        for alias, action in (('document-plan', 'plan'), ('document-build', 'build')):
            with self.subTest(alias=alias), forbid_native_work():
                modern = Mock()
                modern.main.return_value = 17
                legacy = Mock()
                options = ['--plan', '/retained/path with spaces/plan.json',
                           '--plan-sha256', 'a' * 64, '--output=/new/output', '--jobs', '2']
                arguments = ['engine-maintenance', alias, *options]
                original = list(arguments)
                with patch.dict(sys.modules, {'appended_engine_document_maintenance': modern,
                                              'appended_engine_maintenance': legacy}):
                    self.assertEqual(build.main(arguments), 17)
                modern.main.assert_called_once_with([action, *options])
                legacy.main.assert_not_called()
                self.assertEqual(arguments, original)

    def test_default_argv_reaches_document_route(self):
        modern = Mock()
        modern.main.return_value = 0
        with forbid_native_work(), patch.object(sys, 'argv',
                ['build.py', 'engine-maintenance', 'document-plan', '--help']), \
                patch.dict(sys.modules, {'appended_engine_document_maintenance': modern}):
            self.assertEqual(build.main(), 0)
        modern.main.assert_called_once_with(['plan', '--help'])

    def test_legacy_actions_and_help_retain_the_original_dispatch(self):
        for action in ('plan', 'build', '--help', '_step'):
            with self.subTest(action=action), forbid_native_work():
                legacy, modern = Mock(), Mock()
                legacy.main.return_value = 23
                with patch.dict(sys.modules, {'appended_engine_maintenance': legacy,
                                              'appended_engine_document_maintenance': modern}):
                    self.assertEqual(build.main(['engine-maintenance', action, '--fixture']), 23)
                legacy.main.assert_called_once_with([action, '--fixture'])
                modern.main.assert_not_called()

    def test_document_alias_matching_is_exact(self):
        for action in ('document', 'document-plans', 'document-build-extra', 'document-_step'):
            with self.subTest(action=action), forbid_native_work():
                legacy, modern = Mock(), Mock()
                legacy.main.return_value = 2
                with patch.dict(sys.modules, {'appended_engine_maintenance': legacy,
                                              'appended_engine_document_maintenance': modern}):
                    self.assertEqual(build.main(['engine-maintenance', action]), 2)
                legacy.main.assert_called_once_with([action])
                modern.main.assert_not_called()

    def test_document_input_errors_propagate_without_another_producer(self):
        modern, legacy = Mock(), Mock()
        failure = ValueError('retained source pin differs; maintenance inputs required')
        modern.main.side_effect = failure
        with forbid_native_work(), patch.dict(sys.modules, {
                'appended_engine_document_maintenance': modern,
                'appended_engine_maintenance': legacy}):
            with self.assertRaises(ValueError) as raised:
                build.main(['engine-maintenance', 'document-build', '--fixture'])
        self.assertIs(raised.exception, failure)
        legacy.main.assert_not_called()

    def test_standalone_producer_failures_remain_bounded_cli_errors(self):
        for failure in (TypeError('invalid nested retained input'),
                        ProcessTreeError('producer child cleanup was not proven')):
            with self.subTest(failure=type(failure).__name__), forbid_native_work():
                modern, legacy = Mock(), Mock()
                modern.main.side_effect = failure
                with patch.dict(sys.modules, {'appended_engine_document_maintenance': modern,
                                              'appended_engine_maintenance': legacy}):
                    with self.assertRaisesRegex(ValueError, '^document engine maintenance: ') as raised:
                        build.main(['engine-maintenance', 'document-build', '--fixture'])
                self.assertIs(raised.exception.__cause__, failure)
                legacy.main.assert_not_called()

    def test_real_modern_subcommand_help_requires_no_inputs_or_tools(self):
        import appended_engine_document_maintenance as modern
        for alias, required in (('document-plan', '--reuse-proof-sha256'),
                                ('document-build', '--plan-sha256')):
            with self.subTest(alias=alias), forbid_native_work(), \
                    patch.object(modern, 'make_plan', side_effect=AssertionError('help planned inputs')), \
                    patch.object(modern, 'build', side_effect=AssertionError('help built engine')), \
                    patch.object(modern, 'verify_sdk', side_effect=AssertionError('help verified SDK')), \
                    patch.object(sys, 'stdout', new_callable=io.StringIO) as output:
                with self.assertRaises(SystemExit) as raised:
                    build.main(['engine-maintenance', alias, '--help'])
                self.assertEqual(raised.exception.code, 0)
                self.assertIn(required, output.getvalue())
                self.assertIn('--output', output.getvalue())

    def test_missing_required_modern_pins_fail_before_input_or_tool_selection(self):
        import appended_engine_document_maintenance as modern
        for alias in ('document-plan', 'document-build'):
            with self.subTest(alias=alias), forbid_native_work(), \
                    patch.object(modern, 'make_plan', side_effect=AssertionError('parsed incomplete plan')), \
                    patch.object(modern, 'build', side_effect=AssertionError('parsed incomplete build')), \
                    patch.object(modern, 'verify_sdk', side_effect=AssertionError('verified incomplete SDK')), \
                    patch.object(sys, 'stderr', new_callable=io.StringIO) as output:
                with self.assertRaises(SystemExit) as raised:
                    build.main(['engine-maintenance', alias, '--output', '/unused/new-output'])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn('required', output.getvalue())

    def test_document_build_rejects_kernel_and_native_flags_before_building(self):
        import appended_engine_document_maintenance as modern
        for extra in (['--kernel-maintenance'], ['--appended-profile', 'web'],
                      ['--core-provider', 'cpp'], ['--sdk', '/unselected/sdk']):
            with self.subTest(extra=extra), forbid_native_work(), \
                    patch.object(modern, 'build', side_effect=AssertionError('accepted native flags')), \
                    patch.object(sys, 'stderr', new_callable=io.StringIO) as output:
                with self.assertRaises(SystemExit) as raised:
                    build.main(['engine-maintenance', 'document-build', '--plan', '/unused/plan.json',
                                '--plan-sha256', 'a' * 64, '--output', '/unused/output', *extra])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn('unrecognized arguments', output.getvalue())

    def test_document_build_missing_retained_plan_fails_without_creating_outputs(self):
        import appended_engine_document_maintenance as modern
        with tempfile.TemporaryDirectory(prefix='foundation-document-entry-') as temporary:
            root = Path(temporary).resolve()
            plan, output = root / 'missing-plan.json', root / 'output'
            with forbid_native_work(), patch.object(modern, 'verify_sdk',
                    side_effect=AssertionError('missing plan selected SDK')):
                with self.assertRaises(FileNotFoundError):
                    build.main(['engine-maintenance', 'document-build', '--plan', str(plan),
                                '--plan-sha256', 'a' * 64, '--output', str(output)])
            self.assertFalse(output.exists())

    def test_top_level_help_advertises_both_document_aliases(self):
        with forbid_native_work(), patch.object(sys, 'stdout', new_callable=io.StringIO) as output:
            with self.assertRaises(SystemExit) as raised:
                build.main(['--help'])
            self.assertEqual(raised.exception.code, 0)
            self.assertIn('engine-maintenance document-plan', output.getvalue())
            self.assertIn('engine-maintenance document-build', output.getvalue())


if __name__ == '__main__':
    unittest.main()
