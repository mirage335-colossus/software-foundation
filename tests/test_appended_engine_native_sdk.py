#!/usr/bin/env python3
"""Passive SDK consistency fixtures; no real SDK/program/engine is exercised."""

from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import builtins
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_native_sdk as sdk

_spec = importlib.util.spec_from_file_location('native_sdk_synthetic_fixture',
    ROOT / 'tests/fixtures/appended_engine_native_sdk/fixture.py')
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)
EVIDENCE = ROOT / '.agent-work/appended-implementation-20261016/native-prototype-decision-v1/toolchain-admission/adapter-tests-v1'

INSPECTION_FIELDS = {'schema_version', 'kind', 'scope', 'request', 'target', 'sdk',
    'retained_group', 'restoration', 'observations', 'host_tools', 'policy', 'limits',
    'sdk_inventory', 'sdk_directory_facts', 'tools', 'compiler', 'inputs', 'controls', 'production_eligible',
    'native_engine_execution', 'kernel_rebuild'}
PLAN_FIELDS = {'schema_version', 'kind', 'scope', 'request', 'inspection',
    'production_eligible', 'native_engine_execution', 'kernel_rebuild'}
RECEIPT_FIELDS = {'schema_version', 'kind', 'scope', 'plan', 'request', 'target',
    'toolchain', 'sdk_admission', 'identity', 'outputs', 'production_eligible',
    'native_engine_execution', 'kernel_rebuild'}
BINDING_FIELDS = {'schema_version', 'kind', 'target', 'sdk', 'retained_group',
    'restoration', 'observations', 'producer', 'inventory', 'tool_paths', 'sysroot',
    'host_tools', 'policy'}
FLAGS = ('production_eligible', 'native_engine_execution', 'kernel_rebuild')


@contextmanager
def no_execution():
    """An accidental process/SDK installer invocation is a test failure."""
    with ExitStack() as stack:
        original_import = builtins.__import__
        forbidden = {'sdk', 'sdk_environment', 'sdk_linux', 'sdk_windows'}
        def passive_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in forbidden or name == 'tools' and forbidden.intersection(fromlist or ()):
                raise AssertionError('passive adapter attempted an SDK installer import: ' + name)
            return original_import(name, globals, locals, fromlist, level)
        stack.enter_context(mock.patch.object(builtins, '__import__', side_effect=passive_import))
        for name in ('Popen', 'run', 'call', 'check_call', 'check_output'):
            stack.enter_context(mock.patch.object(subprocess, name,
                side_effect=AssertionError('passive adapter attempted subprocess.' + name)))
        for name in ('system', 'execl', 'execle', 'execlp', 'execlpe', 'execv', 'execve',
                     'execvp', 'execvpe', 'posix_spawn', 'posix_spawnp'):
            if hasattr(os, name):
                stack.enter_context(mock.patch.object(os, name,
                    side_effect=AssertionError('passive adapter attempted os.' + name)))
        yield


@contextmanager
def no_archive_reads(fx):
    """Original restoration facts do not authorize fresh archive body reads."""
    forbidden = {str(fx.group / name) for name in (fx.binary_name, fx.source_name)}
    with ExitStack() as stack:
        for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open')):
            original = getattr(owner, name)
            def guarded(path, *args, _original=original, **kwargs):
                if isinstance(path, (str, bytes, os.PathLike)) and os.fsdecode(path) in forbidden:
                    raise AssertionError('passive adapter reread an archive body')
                return _original(path, *args, **kwargs)
            stack.enter_context(mock.patch.object(owner, name, side_effect=guarded))
        yield


class PureSDKUtilities(unittest.TestCase):
    def test_canonical_json_is_stable_and_nonfinite_rejects(self):
        self.assertEqual(sdk.encoded({'b': 2, 'a': 1}), fixture.encoded({'a': 1, 'b': 2}))
        with self.assertRaises((ValueError, TypeError)):
            sdk.encoded({'value': float('nan')})

    def test_renderer_accepts_only_exact_literal_tokens(self):
        template = b'set(A "@A@")\n'
        self.assertEqual(sdk.render_toolchain(template, {'A': '/owned/sdk'}),
                         b'set(A "/owned/sdk")\n')
        for values in ({}, {'A': '/owned/sdk', 'EXTRA': 'bad'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                sdk.render_toolchain(template, values)
        for value in ('', 'x;y', 'x"y', "x'y", 'x\\y', '${HOME}', '@A@', 'x\ny', 'x\ry', 'x\0y'):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                sdk.render_toolchain(template, {'A': value})


@unittest.skipUnless(os.name == 'posix' and sys.platform.startswith('linux'),
                     'Linux SDK inventory/publication semantics are not qualified on this host')
class NativeSDKAdmission(unittest.TestCase):
    def setUp(self):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self.case_root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=EVIDENCE))
        self.fx = fixture.Fixture(self.case_root, ROOT)
        self.pin = fixture.sha(self.fx.request_path.read_bytes())

    def tearDown(self):
        result = getattr(self._outcome, 'result', None)
        failed = bool(result and any(test is self for test, _ in result.errors + result.failures))
        if failed:
            print('Preserved synthetic native SDK failure fixture: ' + str(self.case_root), file=sys.stderr)
        else:
            shutil.rmtree(self.case_root)

    def inspect(self):
        with no_execution():
            return sdk.inspect_request(self.fx.request_path,
                fixture.sha(self.fx.request_path.read_bytes()), repository_root=self.fx.repository)

    def plan(self, name='plan'):
        output = self.fx.output(name)
        with no_execution():
            value = sdk.create_plan(self.fx.request_path,
                fixture.sha(self.fx.request_path.read_bytes()), output, repository_root=self.fx.repository)
        return value, output / 'plan.json'

    def prepare(self, plan_path=None, name='admission'):
        if plan_path is None:
            _, plan_path = self.plan()
        output = self.fx.output(name)
        with no_execution():
            value = sdk.prepare(plan_path, fixture.sha(plan_path.read_bytes()), output,
                                repository_root=self.fx.repository)
        return value, output

    def assert_candidate(self, value):
        self.assertEqual(value['schema_version'], 1)
        self.assertEqual(value['scope'], 'native-sdk-admission-candidate-only')
        for name in FLAGS:
            self.assertIs(value[name], False)

    def assert_invalid(self, operation=None):
        with self.assertRaises(ValueError) as caught:
            (self.inspect if operation is None else operation)()
        self.assertNotIsInstance(caught.exception, sdk.MissingInputs)
        return caught.exception

    def assert_missing(self):
        output = self.fx.output('missing-plan')
        before = fixture.snapshot(self.fx.sdk)
        with self.assertRaises(sdk.MissingInputs) as caught:
            with no_execution():
                sdk.create_plan(self.fx.request_path, fixture.sha(self.fx.request_path.read_bytes()),
                                output, repository_root=self.fx.repository)
        error = caught.exception
        self.assertTrue(error.missing)
        self.assertTrue(error.roles)
        value = error.as_dict()
        self.assertEqual(set(value), {'schema_version', 'kind', 'scope', 'missing', *FLAGS})
        self.assertEqual(value['kind'], 'foundation-native-sdk-admission-missing-inputs-v1')
        self.assert_candidate(value)
        for record in value['missing']:
            self.assertEqual(set(record), {'role', 'path', 'reason'})
        self.assertFalse(output.exists())
        self.assertEqual(fixture.snapshot(self.fx.sdk), before)
        return error

    def test_complete_fake_sdk_is_passive_candidate_and_unchanged(self):
        before = fixture.snapshot(self.fx.sdk)
        inspection = self.inspect()
        facts = inspection.as_dict()
        self.assertEqual(set(facts), INSPECTION_FIELDS)
        self.assertEqual(facts['kind'], 'foundation-native-sdk-admission-inspection-v1')
        self.assert_candidate(facts)
        self.assertEqual(facts['target'], fixture.TARGET)
        self.assertEqual(facts['compiler'], {'family': 'gcc', 'frontend': 'gcc',
            'version': '15.2.0', 'triple': fixture.TARGET['triple']})
        self.assertEqual(facts['sdk_inventory'], fixture.inventory(self.fx.sdk))
        self.assertEqual(facts['sdk']['manifest_sha256'], self.fx.manifest_pin)
        self.assertIn(self.fx.sdk, {Path(path) for path in inspection.protected_paths})
        with no_execution():
            inspection.recheck()
        self.assertEqual(fixture.snapshot(self.fx.sdk), before)

    def test_archive_bodies_are_not_reverified_or_extracted_implicitly(self):
        with no_archive_reads(self.fx):
            self.inspect()
            self.prepare()

    def test_plan_and_prepare_have_closed_candidate_schemas(self):
        before = fixture.snapshot(self.fx.sdk)
        plan, path = self.plan()
        self.assertEqual(set(plan), PLAN_FIELDS)
        self.assertEqual(plan['kind'], 'foundation-native-sdk-admission-plan-v1')
        self.assert_candidate(plan)
        self.assertEqual(path.read_bytes(), sdk.encoded(plan))
        receipt, output = self.prepare(path)
        self.assertEqual(set(receipt), RECEIPT_FIELDS)
        self.assertEqual(receipt['kind'], 'foundation-native-sdk-admission-prepare-v1')
        self.assert_candidate(receipt)
        self.assertEqual((output / 'prepare-receipt.json').read_bytes(), sdk.encoded(receipt))
        self.assertEqual(fixture.snapshot(self.fx.sdk), before)
        self.assertFalse((self.fx.sdk / 'interpreter-runtime.json').exists())
        self.assertFalse((self.fx.sdk / 'identity.json').exists())

    def test_output_hashes_and_inventory_edges_are_acyclic(self):
        receipt, output = self.prepare()
        actual = fixture.inventory(output)
        files = actual['files']
        expected_names = set(files) - {'prepare-receipt.json'}
        self.assertEqual(set(receipt['outputs']), expected_names)
        for name, record in receipt['outputs'].items():
            body = (output / name).read_bytes()
            self.assertEqual(record, {'sha256': fixture.sha(body), 'bytes': len(body),
                'mode': stat.S_IMODE((output / name).stat().st_mode)})
            self.assertEqual((output / name).stat().st_nlink, 1)
            self.assertNotIn(record['sha256'], set(self.fx.manifest['files'].values()),
                             'SDK program/library/module bodies must not be copied into admission output')
        for key in ('toolchain', 'sdk_admission', 'identity'):
            ref = receipt[key]
            self.assertEqual(set(ref), {'path', 'sha256'})
            self.assertEqual(fixture.sha((output / ref['path']).read_bytes()), ref['sha256'])
        binding = json.loads((output / receipt['sdk_admission']['path']).read_text())
        self.assertEqual(set(binding), BINDING_FIELDS)
        self.assertEqual(binding['kind'], 'foundation-native-sdk-admission-binding-v1')
        self.assertEqual(binding['sdk'], self.fx.request['sdk'])
        self.assertEqual(binding['inventory']['root'], str(self.fx.sdk))
        toolchain = json.loads((output / receipt['toolchain']['path']).read_text())
        self.assertEqual(toolchain['kind'], 'foundation-native-engine-prototype-sdk-toolchain-v1')
        self.assertEqual(toolchain['runtime']['sysroot_inventory'], 'sdk')
        self.assertEqual(toolchain['identity']['identity_sha256'], receipt['identity']['sha256'])
        identity = json.loads((output / receipt['identity']['path']).read_text())
        self.assertEqual(set(identity), {'schema_version', 'kind', 'target', 'compiler', 'runtime', 'cpu'})
        self.assertEqual(identity['runtime'], fixture.RUNTIME)
        self.assertEqual(identity['cpu'], fixture.CPU)
        metadata = toolchain['inventories']['toolchain']
        metadata_inventory = json.loads((output / metadata['inventory']['path']).read_text())
        self.assertEqual(set(metadata_inventory['files']), {'identity.json', 'native-toolchain.cmake'})
        self.assertNotIn('prepare-receipt.json', receipt['outputs'])

    def test_template_has_exact_native_paths_without_execution_or_external_include(self):
        _, output = self.prepare()
        text = (output / 'metadata/native-toolchain.cmake').read_text()
        for role in ('c', 'cxx', 'linker', 'archiver', 'ranlib'):
            self.assertIn(str(self.fx.sdk / self.fx.program_paths[role]), text)
        self.assertIn(str(self.fx.sdk / self.fx.sysroot), text)
        self.assertIn(self.fx.manifest_pin, text)
        for forbidden in ('execute_process(', 'find_program(', 'find_library(', 'include(',
                          'ExternalProject', 'FetchContent', '@', 'cmake/toolchains/sdk.cmake'):
            self.assertNotIn(forbidden.lower(), text.lower())
        self.assertIn('CMAKE_FIND_ROOT_PATH_MODE_PROGRAM', text)
        self.assertIn('CMAKE_FIND_ROOT_PATH_MODE_LIBRARY', text)
        self.assertIn('CMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH', text)

    def test_pkg_config_search_uses_only_actual_inventory_pc_parents(self):
        _, output = self.prepare()
        text = (output / 'metadata/native-toolchain.cmake').read_text()
        expected = ':'.join(sorted(str(self.fx.sdk / 'sysroot' / path)
            for path in ('usr/lib/pkgconfig', 'usr/lib64/pkgconfig')))
        self.assertIn(expected, text)
        self.assertNotIn('usr/share/pkgconfig', text)
        self.assertNotIn('usr/lib/' + fixture.TARGET['triple'] + '/pkgconfig', text)

    def test_empty_inventory_pkg_config_search_never_invents_a_directory(self):
        for relative in ('usr/lib/pkgconfig', 'usr/lib64/pkgconfig'):
            path = self.fx.sdk / 'sysroot' / relative
            for child in path.iterdir():
                child.unlink()
            path.rmdir()
        (self.fx.sdk / 'sysroot/usr/lib64').rmdir()
        self.fx.manifest['files'] = {name: pin for name, pin in fixture.inventory(self.fx.sdk)['files'].items()
                                    if name != 'sdk.json'}
        self.fx.rebind_manifest()
        _, output = self.prepare()
        text = (output / 'metadata/native-toolchain.cmake').read_text()
        self.assertIn('set(ENV{PKG_CONFIG_LIBDIR} "")', text)

    def test_output_subdirectory_modes_are_normalized_under_private_umask(self):
        previous = os.umask(0o077)
        try:
            _, output = self.prepare()
        finally:
            os.umask(previous)
        for name in fixture.inventory(output)['directories']:
            self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o755, name)

    def test_case_distinct_headers_are_preserved_only_for_original_linux_sdk(self):
        facts = self.inspect().as_dict()['sdk_inventory']['files']
        upper = 'sysroot/usr/include/X11/Core.h'
        lower = 'sysroot/usr/include/X11/core.h'
        self.assertIn(upper, facts)
        self.assertIn(lower, facts)
        self.assertNotEqual(facts[upper], facts[lower])
        self.fx.manifest['path_policy'] = 'portable'
        self.fx.rebind_manifest()
        self.assert_invalid()

    def test_arbitrary_request_path_policy_waiver_rejects(self):
        self.fx.request['path_policy'] = 'linux-case-sensitive-v1'
        self.fx.flush()
        self.assert_invalid()

    def test_non_linux_original_host_cannot_acquire_sdk_case_policy(self):
        self.fx.manifest['host']['system'] = 'Windows'
        self.fx.rebind_manifest()
        self.assert_invalid()

    def test_unknown_restoration_kind_is_missing_original_input(self):
        self.fx.restoration['kind'] = 'invented-install-receipt-v1'
        self.fx.flush()
        self.assert_missing()

    def test_unknown_tool_observation_kind_is_missing_original_input(self):
        self.fx.observations['kind'] = 'invented-tool-receipt-v1'
        self.fx.flush()
        self.assert_missing()

    def test_diagnostic_restore_cannot_emit_ready_candidate(self):
        self.fx.restoration['mode'] = 'diagnostic'
        self.fx.flush()
        self.assert_missing()

    def test_missing_raw_target_observation_is_not_implicitly_run(self):
        record = self.fx.observations['tools']['c']['commands']['dumpmachine']['stdout']
        (self.fx.inputs / record['path']).unlink()
        self.assert_missing()

    def test_missing_selected_tool_observation_is_missing_input(self):
        del self.fx.observations['tools']['ranlib']
        self.fx.flush()
        self.assert_missing()

    def test_known_raw_target_contradiction_rejects(self):
        self.fx.rewrite_raw('cxx', 'dumpmachine', 'wasm32-unknown-emscripten\n')
        self.assert_invalid()

    def test_raw_sysroot_must_be_exact_sdk_sysroot(self):
        self.fx.rewrite_raw('c', 'sysroot', '/usr\n')
        self.assert_invalid()

    def test_raw_subordinate_tool_outside_inventory_rejects(self):
        self.fx.rewrite_raw('cxx', 'assembler', '/usr/bin/as\n')
        self.assert_invalid()

    def test_raw_linker_must_equal_selected_linker(self):
        self.fx.rewrite_raw('c', 'linker', str(self.fx.sdk / self.fx.program_paths['ranlib']) + '\n')
        self.assert_invalid()

    def test_raw_search_dirs_cannot_add_ambient_library_search(self):
        self.fx.rewrite_raw('c', 'search_dirs', 'install: ' + str(self.fx.sdk / 'libexec') +
            '\nprograms: =' + str(self.fx.sdk / 'bin') + '\nlibraries: =/usr/lib\n')
        self.assert_invalid()

    def test_raw_version_cannot_disagree_with_original_record(self):
        self.fx.rewrite_raw('cmake', 'version', 'SYNTHETIC cmake 3.10.0\n')
        self.assert_invalid()

    def test_two_component_gcc_and_cmake_minima_are_valid_candidate_versions(self):
        for role, version in (('c', '12.2'), ('cxx', '12.2'), ('cmake', '3.24')):
            self.fx.observations['tools'][role]['version'] = version
            if role == 'cmake':
                self.fx.host_tools['programs']['cmake']['version'] = version
            self.fx.rewrite_raw(role, 'version', 'SYNTHETIC ' + role + ' ' + version + '\n')
        self.assert_candidate(self.inspect().as_dict())

    def test_declared_actual_cmake_below_minimum_rejects(self):
        self.fx.observations['tools']['cmake']['version'] = '3.23'
        self.fx.host_tools['programs']['cmake']['version'] = '3.23'
        self.fx.rewrite_raw('cmake', 'version', 'SYNTHETIC cmake 3.23\n')
        self.assert_invalid()

    def test_tool_bytes_pin_cannot_be_replaced_by_record_assertion(self):
        self.fx.observations['tools']['c']['sha256'] = '1' * 64
        self.fx.flush()
        self.assert_invalid()

    def test_original_command_requires_closed_output_ownership(self):
        self.fx.observations['tools']['c']['commands']['version']['ownership']['logs_closed'] = False
        self.fx.flush()
        self.assert_invalid()

    def test_original_restoration_group_cannot_disagree_with_selected_group(self):
        self.fx.restoration['group_files'] = json.loads(json.dumps(self.fx.restoration['group_files']))
        self.fx.restoration['group_files'][self.fx.source_name]['sha256'] = '6' * 64
        self.fx.flush()
        self.assert_invalid()

    def test_original_restoration_recipe_cannot_be_substituted(self):
        self.fx.restoration['recipe'] = '7' * 64
        self.fx.flush()
        self.assert_invalid()

    def test_known_receipt_extra_verified_bit_cannot_grant_admission(self):
        self.fx.restoration['verified'] = True
        self.fx.flush()
        self.assert_invalid()

    def test_original_observation_cannot_claim_engine_eligibility(self):
        self.fx.observations['production_eligible'] = True
        self.fx.flush()
        self.assert_invalid()

    def test_boolean_returncode_cannot_stand_for_zero(self):
        self.fx.restoration['command']['returncode'] = False
        self.fx.flush()
        self.assert_invalid()

    def test_release_target_runtime_cohort_cannot_be_weakened(self):
        self.fx.manifest['audits']['target']['sdk_runtime']['recipe_id'] = '2' * 64
        self.fx.rebind_manifest()
        self.assert_invalid()

    def test_release_host_audit_is_required(self):
        self.fx.manifest['audits']['host']['status'] = 'unexecuted'
        self.fx.rebind_manifest()
        self.assert_invalid()

    def test_release_runtime_file_join_must_match_original_file_hash(self):
        self.fx.manifest['audits']['target']['sdk_runtime']['files']['lib/libc.so.6'] = '3' * 64
        self.fx.rebind_manifest()
        self.assert_invalid()

    def test_unknown_original_sdk_extension_is_preserved_without_root_writes(self):
        before = (self.fx.sdk / 'sdk.json').read_bytes()
        self.prepare()
        self.assertEqual((self.fx.sdk / 'sdk.json').read_bytes(), before)
        self.assertEqual(json.loads(before)['synthetic_extension_preserved'], {'fixture': True})

    def test_full_sdk_body_mutation_is_detected_without_manifest_change(self):
        path = self.fx.sdk / self.fx.program_paths['archiver']
        original = path.stat()
        raw = path.read_bytes()
        fixture.write(path, b'X' + raw[1:], 0o755)
        os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
        self.assert_invalid()

    def test_recheck_catches_added_file_and_unknown_empty_directory(self):
        inspection = self.inspect()
        (self.fx.sdk / 'unknown-empty').mkdir()
        with no_execution(), self.assertRaises(ValueError):
            inspection.recheck()

    def test_initial_unknown_empty_directory_lacks_original_inventory_authority(self):
        (self.fx.sdk / 'unrecorded-empty').mkdir()
        self.assert_invalid()

    def test_recheck_preserves_case_policy_and_catches_case_rename(self):
        inspection = self.inspect()
        path = self.fx.sdk / 'sysroot/usr/include/X11/Core.h'
        lower = path.with_name('core.h')
        lower_bytes = lower.read_bytes()
        renamed = path.with_name('CORE.h')
        path.rename(renamed)
        self.assertTrue(renamed.is_file())
        self.assertFalse(path.exists())
        self.assertEqual(lower.read_bytes(), lower_bytes)
        with no_execution(), self.assertRaises((ValueError, FileNotFoundError)) as caught:
            inspection.recheck()
        if isinstance(caught.exception, FileNotFoundError):
            self.assertEqual(caught.exception.filename, str(path))
        self.assertTrue(renamed.is_file())
        self.assertFalse(path.exists())
        self.assertEqual(lower.read_bytes(), lower_bytes)

    def test_prepare_rejects_changed_sdk_after_passive_plan(self):
        _, path = self.plan()
        fixture.write(self.fx.sdk / 'lib/python3.12/hashlib.py', b'# CHANGED SYNTHETIC MODULE\n')
        self.assert_invalid(lambda: self.prepare(path))
        self.assertFalse(self.fx.output('admission').exists())

    def test_prepare_rejects_changed_source_control_in_replica(self):
        _, path = self.plan()
        source = self.fx.repository / fixture.CONTROL_PATHS[1]
        fixture.write(source, source.read_bytes() + b'# changed fixture control\n',
                      stat.S_IMODE(source.stat().st_mode))
        self.assert_invalid(lambda: self.prepare(path))
        self.assertFalse(self.fx.output('admission').exists())

    def test_symlink_sdk_entry_is_rejected_without_following(self):
        path = self.fx.sdk / self.fx.program_paths['ranlib']
        path.unlink()
        path.symlink_to(self.fx.sdk / self.fx.program_paths['archiver'])
        self.assert_invalid()

    def test_hardlinked_sdk_file_is_rejected(self):
        source = self.fx.sdk / self.fx.program_paths['ranlib']
        os.link(source, self.fx.inputs / 'foreign-hardlink')
        self.assert_invalid()

    def test_privileged_mode_is_rejected(self):
        (self.fx.sdk / self.fx.program_paths['c']).chmod(0o4755)
        self.assert_invalid()

    def test_special_sdk_entry_is_rejected_before_content_read(self):
        os.mkfifo(self.fx.sdk / 'unknown-pipe', 0o600)
        self.assert_invalid()

    def test_inventory_file_limit_is_not_truncation(self):
        self.fx.request['limits']['maximum_files'] = 1
        self.fx.flush()
        self.assert_invalid()

    def test_input_byte_limit_is_enforced(self):
        self.fx.request['limits']['maximum_input_bytes'] = 1
        self.fx.flush()
        self.assert_invalid()

    def test_document_limit_is_enforced(self):
        self.fx.request['limits']['maximum_document_bytes'] = 1
        self.fx.flush()
        self.assert_invalid()

    def test_boolean_limit_is_invalid(self):
        self.fx.request['limits']['maximum_files'] = True
        self.fx.flush()
        self.assert_invalid()

    def test_declared_free_space_reserve_prevents_output(self):
        empty = mock.Mock(f_bavail=0, f_frsize=4096)
        with mock.patch.object(os, 'statvfs', return_value=empty):
            error = self.assert_invalid(lambda: self.plan('reserve-plan'))
        self.assertTrue(any(word in str(error).lower() for word in ('free', 'reserve', 'space')))
        self.assertFalse(self.fx.output('reserve-plan').exists())

    def test_free_space_reserve_includes_known_publication_bytes(self):
        exact_reserve_only = mock.Mock(f_bavail=self.fx.request['limits']['minimum_free_bytes'], f_frsize=1)
        with mock.patch.object(os, 'statvfs', return_value=exact_reserve_only):
            error = self.assert_invalid(lambda: self.plan('publication-reserve-plan'))
        self.assertTrue(any(word in str(error).lower() for word in ('free', 'reserve', 'space')))
        self.assertFalse(self.fx.output('publication-reserve-plan').exists())

    def test_output_byte_limit_fails_without_sdk_mutation(self):
        self.fx.request['limits']['maximum_output_bytes'] = 1
        self.fx.flush()
        before = fixture.snapshot(self.fx.sdk)
        self.assert_invalid(lambda: self.prepare())
        self.assertEqual(fixture.snapshot(self.fx.sdk), before)

    def test_deadline_failure_is_deterministic_without_sleep(self):
        clock = itertools.count(0, self.fx.request['limits']['prepare_seconds'] + 1)
        with mock.patch.object(time, 'monotonic', side_effect=lambda: next(clock)):
            self.assert_invalid()

    def test_zero_sdk_manifest_pin_is_invalid(self):
        self.fx.request['sdk']['manifest_sha256'] = '0' * 64
        self.fx.flush()
        self.assert_invalid()

    def test_duplicate_nonfinite_and_surrogate_json_reject(self):
        for raw in (b'{"schema_version":1,"schema_version":1}',
                    b'{"value":NaN}', b'{"value":"\\ud800"}'):
            path = fixture.write(self.fx.inputs / 'malformed.json', raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                sdk.read_document(path, fixture.sha(raw))

    def test_output_inside_sdk_is_refused_without_sdk_mutation(self):
        before = fixture.snapshot(self.fx.sdk)
        with no_execution(), self.assertRaises(ValueError):
            sdk.create_plan(self.fx.request_path, self.pin, self.fx.sdk / 'admission',
                            repository_root=self.fx.repository)
        self.assertEqual(fixture.snapshot(self.fx.sdk), before)

    def test_preexisting_output_is_not_replaced(self):
        output = self.fx.output('occupied')
        output.mkdir()
        sentinel = fixture.write(output / 'sentinel', b'FOREIGN PRIOR OUTPUT\n')
        with no_execution(), self.assertRaises(ValueError):
            sdk.create_plan(self.fx.request_path, self.pin, output, repository_root=self.fx.repository)
        self.assertEqual(sentinel.read_bytes(), b'FOREIGN PRIOR OUTPUT\n')
        self.assertEqual({path.name for path in output.iterdir()}, {'sentinel'})

    def test_prepare_preserves_preexisting_output(self):
        _, plan = self.plan()
        output = self.fx.output('occupied-admission')
        output.mkdir()
        sentinel = fixture.write(output / 'sentinel', b'PRIOR ADMISSION EVIDENCE\n')
        self.assert_invalid(lambda: self.prepare(plan, name='occupied-admission'))
        self.assertEqual(sentinel.read_bytes(), b'PRIOR ADMISSION EVIDENCE\n')
        self.assertEqual({path.name for path in output.iterdir()}, {'sentinel'})

    def test_plan_pin_and_canonical_bytes_are_required(self):
        _, path = self.plan()
        with no_execution(), self.assertRaises(ValueError):
            sdk.prepare(path, '4' * 64, self.fx.output('wrong-pin'), repository_root=self.fx.repository)
        value = json.loads(path.read_text())
        fixture.write(path, json.dumps(value).encode())
        with no_execution(), self.assertRaises(ValueError):
            sdk.prepare(path, fixture.sha(path.read_bytes()), self.fx.output('noncanonical'),
                        repository_root=self.fx.repository)

    def test_external_interpreter_facts_do_not_require_sdk_mutation(self):
        inspection = self.inspect()
        self.assert_candidate(inspection.as_dict())
        self.assertFalse((self.fx.sdk / 'interpreter-runtime.json').exists())
        self.assertFalse((self.fx.sdk / 'lib/python3.12/interpreter-runtime.json').exists())
        for role in ('python', 'perl', 'ruby'):
            ref = self.fx.host_tools['interpreter_bindings'][role]
            self.assertTrue((self.fx.inputs / ref['path']).is_file())

    def test_missing_external_interpreter_fact_is_missing_input(self):
        ref = self.fx.host_tools['interpreter_bindings']['python']
        (self.fx.inputs / ref['path']).unlink()
        self.assert_missing()

    def test_external_fact_cannot_bind_foreign_program(self):
        ref = self.fx.host_tools['interpreter_bindings']['ruby']
        path = self.fx.inputs / ref['path']
        value = json.loads(path.read_text())
        value['program_sha256'] = '5' * 64
        fixture.document(path, value)
        self.fx.host_tools['interpreter_bindings']['ruby'] = self.fx.ref(path)
        self.fx.flush()
        self.assert_invalid()

    def test_external_fact_requires_program_owning_named_inventory(self):
        ref = self.fx.host_tools['interpreter_bindings']['python']
        path = self.fx.inputs / ref['path']
        value = json.loads(path.read_text())
        value['runtime_inventories'] = ['host-extension']
        fixture.document(path, value)
        self.fx.host_tools['interpreter_bindings']['python'] = self.fx.ref(path)
        self.fx.flush()
        self.assert_invalid()

    def test_cli_plan_and_prepare_use_only_passive_adapter_actions(self):
        output = self.fx.output('cli-plan')
        stdout, stderr = io.StringIO(), io.StringIO()
        with no_execution(), redirect_stdout(stdout), redirect_stderr(stderr):
            code = sdk.cli(['plan', '--request', str(self.fx.request_path),
                '--request-sha256', self.pin, '--output', str(output)])
        self.assertEqual(code, 0, stderr.getvalue())
        plan = json.loads(stdout.getvalue())
        self.assertEqual(set(plan), PLAN_FIELDS)
        self.assert_candidate(plan)
        path = output / 'plan.json'
        stdout, stderr = io.StringIO(), io.StringIO()
        with no_execution(), redirect_stdout(stdout), redirect_stderr(stderr):
            code = sdk.cli(['prepare', '--plan', str(path), '--plan-sha256', fixture.sha(path.read_bytes()),
                '--output', str(self.fx.output('cli-admission'))])
        self.assertEqual(code, 0, stderr.getvalue())
        self.assert_candidate(json.loads(stdout.getvalue()))

    def test_cli_missing_original_returns_structured_two_without_output(self):
        self.fx.observations['kind'] = 'unknown-original-tool-receipt'
        self.fx.flush()
        output = self.fx.output('cli-missing')
        stdout = io.StringIO()
        with no_execution(), redirect_stdout(stdout):
            code = sdk.cli(['plan', '--request', str(self.fx.request_path),
                '--request-sha256', fixture.sha(self.fx.request_path.read_bytes()), '--output', str(output)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())['kind'],
                         'foundation-native-sdk-admission-missing-inputs-v1')
        self.assertFalse(output.exists())


_private_spec = importlib.util.spec_from_file_location('native_sdk_private_runtime_fixture',
    ROOT / 'tests/fixtures/appended_engine_native_sdk/private_runtime_fixture.py')
private_fixture = importlib.util.module_from_spec(_private_spec)
_private_spec.loader.exec_module(private_fixture)


@contextmanager
def no_file_opens():
    """Metadata-only runtime helpers must not open any SDK or host file."""
    with ExitStack() as stack:
        for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open')):
            stack.enter_context(mock.patch.object(owner, name,
                side_effect=AssertionError('pure runtime helper attempted a file open')))
        yield


@unittest.skipUnless(os.name == 'posix' and sys.platform.startswith('linux'),
                     'Linux synthetic runtime capture requires POSIX file semantics')
class NativeSDKPrivateRuntime(unittest.TestCase):
    """Inert consistency fixtures; no real archive or compiler query is used.

    Only these positive synthetic unit paths replace the policy trust-anchor
    digest. All production parsing, complete inventory and body/mode checks run.
    The unmocked production anchor is tested separately below.
    """

    def setUp(self):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self.case_root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=EVIDENCE))
        self.fx = private_fixture.Fixture(self.case_root, ROOT)

    tearDown = NativeSDKAdmission.tearDown

    def fresh(self, name):
        parent = self.case_root / name
        parent.mkdir()
        return private_fixture.Fixture(parent, ROOT)

    def capture(self):
        import appended_engine_native_inputs as native
        value = native.InputSet()
        value.deadline = time.monotonic() + 30
        return value

    def cohort(self, fx=None, *, binding=None):
        fx = self.fx if fx is None else fx
        with no_execution(), no_archive_reads(fx), mock.patch.object(
                sdk, 'PRIVATE_RUNTIME_POLICY_SHA256', fx.synthetic_policy_sha256):
            return sdk.private_runtime_cohort(
                fx.synthetic_binding() if binding is None else binding, fx.synthetic_policy_raw)

    def selection(self, fx=None, *, binding=None, environment=None):
        fx = self.fx if fx is None else fx
        with no_execution(), no_archive_reads(fx), mock.patch.object(
                sdk, 'PRIVATE_RUNTIME_POLICY_SHA256', fx.synthetic_policy_sha256):
            capture = self.capture()
            result = sdk.validate_private_runtime_selection(
                fx.private_runtime_selection_ref, fx.inputs, capture,
                binding=fx.synthetic_binding() if binding is None else binding,
                policy_raw=fx.synthetic_policy_raw,
                expected_environment=fx.query_environment if environment is None else environment)
        return result, capture

    def invalid_selection(self, fx=None, **kwargs):
        with self.assertRaises(ValueError) as caught:
            self.selection(fx, **kwargs)
        self.assertFalse(hasattr(caught.exception, 'missing'), str(caught.exception))
        return caught.exception

    def test_production_anchor_is_unmodified_and_rejects_synthetic_policy(self):
        raw = (ROOT / private_fixture.SOURCE_POLICY_PATH).read_bytes()
        self.assertEqual(fixture.sha(raw), private_fixture.SOURCE_POLICY_SHA256)
        self.assertEqual(sdk.PRIVATE_RUNTIME_POLICY_SHA256, private_fixture.SOURCE_POLICY_SHA256)
        self.assertNotEqual(self.fx.synthetic_policy_sha256, private_fixture.SOURCE_POLICY_SHA256)
        with no_execution(), self.assertRaises(ValueError):
            sdk.private_runtime_cohort(self.fx.synthetic_binding(), self.fx.synthetic_policy_raw)
        with no_execution(), self.assertRaises(ValueError):
            sdk.private_runtime_cohort(self.fx.synthetic_binding(), raw)

    def test_cohort_is_pure_and_query_environment_excludes_host_extension(self):
        before = fixture.snapshot(self.fx.sdk)
        binding = self.fx.synthetic_binding()
        with no_file_opens():
            result = self.cohort(binding=binding)
        self.assertEqual(set(result), {'policy', 'policy_sha256', 'root', 'sysroot', 'compiler', 'candidates'})
        self.assertEqual(set(result['candidates']), set(private_fixture.RUNTIME_ROLES))
        with no_execution(), no_file_opens():
            environment = sdk.private_runtime_query_environment(binding)
        self.assertEqual(environment, self.fx.query_environment)
        self.assertEqual(set(environment), {'PATH', 'LANG', 'LC_ALL', 'TZ', 'SOURCE_DATE_EPOCH'})
        self.assertNotIn(str(self.fx.extension), environment['PATH'])
        self.assertNotIn('/usr/bin', environment['PATH'].split(':'))
        self.assertEqual(fixture.snapshot(self.fx.sdk), before)

    def test_cohort_rejects_original_recipe_hash_mode_and_inventory_changes(self):
        import copy
        for name in ('recipe', 'metadata-hash', 'complete-hash', 'candidate-hash', 'mode', 'extra-file', 'compiler'):
            with self.subTest(name=name):
                binding = copy.deepcopy(self.fx.synthetic_binding())
                leaf = self.fx.private_runtime_relative_paths['libgcc']
                if name == 'recipe': binding['metadata']['recipe_id'] = '1' * 64
                elif name == 'metadata-hash': binding['metadata']['files'][leaf] = '2' * 64
                elif name == 'complete-hash': binding['files'][leaf] = '3' * 64
                elif name == 'candidate-hash':
                    binding['metadata']['files'][leaf] = '3' * 64
                    binding['files'][leaf] = '3' * 64
                elif name == 'mode': binding['modes'][leaf] = 0o755
                elif name == 'extra-file': binding['files']['unowned.txt'] = '4' * 64
                else: binding['compiler']['triple'] = 'x86_64-linux-gnu'
                with self.assertRaises(ValueError): self.cohort(binding=binding)

    def test_complete_selection_captures_real_fixture_bodies_without_execution(self):
        before = fixture.snapshot(self.fx.sdk)
        result, capture = self.selection()
        self.assertEqual(set(result), {'policy', 'policy_sha256', 'candidates', 'selected', 'record',
            'query_environment', 'search_directories', 'compiler_triple', 'cmake'})
        self.assertEqual(result['selected'], self.fx.private_runtime_selection['selected'])
        self.assertEqual(result['compiler_triple'], fixture.TARGET['triple'])
        self.assertEqual(result['query_environment'], self.fx.query_environment)
        self.assertEqual(result['cmake']['BIB_NATIVE_RUNTIME_POLICY_SHA256'], self.fx.synthetic_policy_sha256)
        for role in private_fixture.RUNTIME_ROLES:
            self.assertTrue(any('sdk-runtime-file-' + role in item['roles'] for item in capture.records))
        with no_execution(), no_archive_reads(self.fx):
            capture.recheck()
        self.assertEqual(fixture.snapshot(self.fx.sdk), before)
        self.assertFalse(any(name.startswith('production_') for name in result))

    def test_selection_binding_and_closed_role_sets_are_required(self):
        for name in ('policy', 'sdk', 'compiler', 'scope', 'extra-top', 'missing-role', 'extra-role', 'query'):
            with self.subTest(name=name):
                fx = self.fresh(name)
                record = fx.private_runtime_selection
                if name in ('policy', 'sdk', 'compiler'):
                    key = {'policy': 'policy_sha256', 'sdk': 'sdk_manifest_sha256', 'compiler': 'compiler_sha256'}[name]
                    record[key] = '5' * 64
                elif name == 'scope': record['scope'] = 'native-engine-execution'
                elif name == 'extra-top': record['production_eligible'] = True
                elif name == 'missing-role': record['selected'].pop('libgcc_eh')
                elif name == 'extra-role': record['selected']['libsupcxx'] = dict(record['selected']['libgcc'])
                else: record['commands'].pop('search_dirs')
                fx.flush_private_runtime()
                self.invalid_selection(fx)

    def test_selected_file_hash_size_and_type_are_checked(self):
        for name in ('hash', 'size', 'bool-size', 'relative', 'foreign', 'shared'):
            with self.subTest(name=name):
                fx = self.fresh(name)
                selected = fx.private_runtime_selection['selected']['libstdcxx']
                if name == 'hash': selected['sha256'] = '6' * 64
                elif name == 'size': selected['bytes'] += 1
                elif name == 'bool-size': selected['bytes'] = True
                elif name == 'relative': selected['path'] = 'libstdc++.a'
                elif name == 'foreign': selected['path'] = '/usr/lib/libstdc++.a'
                else: selected['path'] = selected['path'].replace('.a', '.so.6')
                fx.flush_private_runtime()
                self.invalid_selection(fx)

    def test_query_environment_rejects_every_ambient_search_override(self):
        for name in ('CPATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'COMPILER_PATH',
                     'GCC_EXEC_PREFIX', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT', 'CXXFLAGS', 'LDFLAGS'):
            with self.subTest(name=name):
                fx = self.fresh(name)
                fx.private_runtime_selection['commands']['libgcc']['environment'][name] = '/ambient'
                fx.flush_private_runtime()
                self.invalid_selection(fx)
        polluted = dict(self.fx.query_environment, PATH=self.fx.query_environment['PATH'] + ':' + str(self.fx.extension / 'bin'))
        self.invalid_selection(environment=polluted)

    def test_query_argv_is_exact_and_uses_the_admitted_compiler(self):
        for index, extra in enumerate(('-B/usr/bin', '-L/usr/lib', '--sysroot=/usr', '-specs=foreign', '-march=native')):
            with self.subTest(extra=extra):
                fx = self.fresh('extra-' + str(index))
                fx.private_runtime_selection['commands']['libgcc']['argv'].insert(1, extra)
                fx.flush_private_runtime()
                self.invalid_selection(fx)
        fx = self.fresh('foreign-compiler')
        fx.private_runtime_selection['commands']['libgcc']['argv'][0] = '/usr/bin/g++'
        fx.flush_private_runtime()
        self.invalid_selection(fx)

    def test_raw_runtime_paths_reject_foreign_relative_multiline_and_whitespace(self):
        for index, raw in enumerate(('/usr/lib/libgcc.a\n', 'relative/libgcc.a\n',
                                     '\n', ' /owned/libgcc.a\n', '/owned/libgcc.a\r\n',
                                     self.fx.private_runtime_files['libgcc']['path'] + '\nextra\n')):
            with self.subTest(index=index):
                fx = self.fresh('raw-' + str(index))
                fx.rewrite_private_raw('libgcc', raw)
                self.invalid_selection(fx)

    def test_unresolved_basename_is_missing_not_workstation_discovery(self):
        self.fx.rewrite_private_raw('libgcc', 'libgcc.a\n')
        with self.assertRaises(sdk.MissingInputs): self.selection()

    def test_target_sysroot_and_search_output_cannot_import_host_directories(self):
        for name in ('triple', 'sysroot', 'install', 'programs', 'libraries', 'empty-programs', 'empty-libraries', 'extra-line'):
            with self.subTest(name=name):
                fx = self.fresh('search-' + name)
                if name == 'triple': role, raw = 'dumpmachine', 'x86_64-linux-gnu\n'
                elif name == 'sysroot': role, raw = 'sysroot', '/usr\n'
                else:
                    role = 'search_dirs'
                    original = fx.private_runtime_selection['commands'][role]['stdout']
                    lines = (fx.inputs / original['path']).read_text().splitlines()
                    if name == 'install': lines[0] = 'install: /usr/lib'
                    elif name == 'programs': lines[1] = 'programs: =/usr/bin'
                    elif name == 'libraries': lines[2] = 'libraries: =/usr/lib'
                    elif name == 'empty-programs': lines[1] = 'programs: ='
                    elif name == 'empty-libraries': lines[2] = 'libraries: ='
                    else: lines.append('extra')
                    raw = '\n'.join(lines) + '\n'
                fx.rewrite_private_raw(role, raw)
                self.invalid_selection(fx)

    def test_gcc_dotdot_paths_normalize_without_discovering_ambient_files(self):
        path = Path(self.fx.private_runtime_files['libgcc']['path'])
        self.fx.rewrite_private_raw('libgcc', str(path.parent / 'unused' / '..' / path.name) + '\n')
        result, _ = self.selection()
        self.assertEqual(result['selected']['libgcc']['path'], str(path))
        self.assertFalse((path.parent / 'unused').exists())

    def test_queries_require_closed_successful_consistent_working_directories(self):
        for name in ('returncode', 'bool-returncode', 'cwd', 'aggregate', 'command', 'stderr', 'stdout-limit', 'stderr-limit'):
            with self.subTest(name=name):
                fx = self.fresh(name)
                command = fx.private_runtime_selection['commands']['crtbeginS']
                if name == 'returncode': command['returncode'] = 1
                elif name == 'bool-returncode': command['returncode'] = False
                elif name == 'cwd': command['cwd'] = str(fx.sdk)
                elif name == 'aggregate': fx.private_runtime_selection['ownership']['closed'] = False
                elif name == 'command': command['ownership']['logs_closed'] = False
                elif name.endswith('-limit'):
                    fx.rewrite_private_raw('crtbeginS', b'L' * (1024 * 1024 + 1), stream=name.split('-')[0])
                else: fx.rewrite_private_raw('crtbeginS', b'warning\n', stream='stderr')
                fx.flush_private_runtime()
                self.invalid_selection(fx)

    def test_selected_bodies_must_remain_ordinary0644_sdk_files(self):
        for name in ('mode', 'body', 'hardlink', 'symlink'):
            with self.subTest(name=name):
                fx = self.fresh(name)
                path = Path(fx.private_runtime_files['libgcc']['path'])
                binding = fx.synthetic_binding()
                if name == 'mode': path.chmod(0o755)
                elif name == 'body': path.write_bytes(b'CHANGED INERT RUNTIME BODY\n')
                elif name == 'hardlink': os.link(path, fx.root / 'foreign-link')
                else:
                    original = fx.root / 'moved-runtime'
                    path.rename(original)
                    path.symlink_to(original)
                self.invalid_selection(fx, binding=binding)

    def test_missing_selected_body_requires_new_retained_input(self):
        binding = self.fx.synthetic_binding()
        Path(self.fx.private_runtime_files['libgcc']['path']).unlink()
        with self.assertRaises(sdk.MissingInputs):
            self.selection(binding=binding)

    def test_unknown_selection_kind_and_missing_raw_inputs_are_missing(self):
        for name in ('kind', 'selection', 'stdout', 'stderr'):
            with self.subTest(name=name):
                fx = self.fresh(name)
                ref = dict(fx.private_runtime_selection_ref)
                if name == 'kind':
                    fx.private_runtime_selection['kind'] = 'unsupported-original-selection'
                    fx.flush_private_runtime()
                elif name == 'selection': fx.private_runtime_selection_path.unlink()
                else:
                    stream = fx.private_runtime_selection['commands']['libgcc'][name]
                    (fx.inputs / stream['path']).unlink()
                with no_execution(), no_archive_reads(fx), mock.patch.object(sdk, 'PRIVATE_RUNTIME_POLICY_SHA256', fx.synthetic_policy_sha256):
                    with self.assertRaises(ValueError) as caught:
                        sdk.validate_private_runtime_selection(
                            ref if name == 'selection' else fx.private_runtime_selection_ref,
                            fx.inputs, self.capture(), binding=fx.synthetic_binding(),
                            policy_raw=fx.synthetic_policy_raw, expected_environment=fx.query_environment)
                self.assertTrue(hasattr(caught.exception, 'missing'), str(caught.exception))

    def test_capture_recheck_rejects_runtime_and_original_query_mutation(self):
        for name in ('body', 'query'):
            with self.subTest(name=name):
                fx = self.fresh(name)
                _, capture = self.selection(fx)
                if name == 'body': Path(fx.private_runtime_files['libgcc']['path']).write_bytes(b'CHANGED\n')
                else:
                    raw = fx.private_runtime_selection['commands']['libgcc']['stdout']
                    (fx.inputs / raw['path']).write_bytes(b'CHANGED\n')
                with no_execution(), no_archive_reads(fx), self.assertRaises(ValueError):
                    capture.recheck()


@unittest.skipUnless(os.name == 'posix' and sys.platform.startswith('linux'),
                     'Linux restoration capture requires POSIX file semantics')
class NativeSDKRestorationRawLimits(unittest.TestCase):
    """Large inert original logs exercise capture bounds without an SDK run."""

    setUp = NativeSDKAdmission.setUp
    tearDown = NativeSDKAdmission.tearDown
    inspect = NativeSDKAdmission.inspect
    assert_candidate = NativeSDKAdmission.assert_candidate
    assert_invalid = NativeSDKAdmission.assert_invalid

    def rewrite_restoration_stream(self, stream, raw, *, refresh=True):
        record = self.fx.restoration['command']
        path = self.fx.inputs / record[stream]['path']
        fixture.write(path, raw)
        if refresh:
            record[stream] = self.fx.ref(path)
            self.fx.flush()
        return path

    def test_large_original_restoration_streams_are_captured_in_full(self):
        self.fx.request['limits']['maximum_document_bytes'] = 8 * 1024 * 1024
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                raw = b'SYNTHETIC original restoration log; no installer ran\n' + b'L' * (4 * 1024 * 1024 + 17)
                path = self.rewrite_restoration_stream(stream, raw)
                with no_archive_reads(self.fx):
                    inspection = self.inspect()
                facts = inspection.as_dict()
                self.assert_candidate(facts)
                records = [item for item in facts['inputs'] if item['path'] == str(path)]
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['bytes'], len(raw))
                self.assertEqual(records[0]['sha256'], fixture.sha(raw))
                self.assertEqual(path.read_bytes(), raw)
                with no_execution(), no_archive_reads(self.fx):
                    inspection.recheck()
                self.rewrite_restoration_stream(stream, b'SYNTHETIC reset original log\n')

    def test_original_restoration_streams_above_eight_mib_reject(self):
        self.fx.request['limits']['maximum_document_bytes'] = 16 * 1024 * 1024
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.rewrite_restoration_stream(stream, b'L' * (8 * 1024 * 1024 + 1))
                with no_archive_reads(self.fx):
                    self.assert_invalid()
                self.rewrite_restoration_stream(stream, b'SYNTHETIC reset original log\n')

    def test_lower_caller_document_limit_still_bounds_restoration_streams(self):
        self.assertEqual(self.fx.request['limits']['maximum_document_bytes'], 1024 * 1024)
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.rewrite_restoration_stream(stream, b'L' * (1024 * 1024 + 1))
                with no_archive_reads(self.fx):
                    self.assert_invalid()
                self.rewrite_restoration_stream(stream, b'SYNTHETIC reset original log\n')

    def test_ordinary_tool_observations_retain_one_mib_limit(self):
        self.fx.request['limits']['maximum_document_bytes'] = 8 * 1024 * 1024
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                record = self.fx.observations['tools']['c']['commands']['version']
                path = self.fx.inputs / record[stream]['path']
                original = path.read_bytes()
                fixture.write(path, original + b'L' * (1024 * 1024 + 1 - len(original)))
                record[stream] = self.fx.ref(path)
                self.fx.flush()
                with no_archive_reads(self.fx):
                    self.assert_invalid()
                fixture.write(path, original)
                record[stream] = self.fx.ref(path)
                self.fx.flush()

    def test_large_restoration_stream_pin_and_recheck_use_all_bytes(self):
        self.fx.request['limits']['maximum_document_bytes'] = 8 * 1024 * 1024
        raw = b'SYNTHETIC original log\n' + b'L' * (1024 * 1024 + 17)
        path = self.rewrite_restoration_stream('stdout', raw)
        fixture.write(path, raw[:-1] + b'X')
        with no_archive_reads(self.fx):
            self.assert_invalid()
        fixture.write(path, raw)
        with no_archive_reads(self.fx):
            inspection = self.inspect()
        fixture.write(path, raw[:-1] + b'X')
        with no_execution(), no_archive_reads(self.fx), self.assertRaises(ValueError):
            inspection.recheck()


@unittest.skipUnless(os.name == 'posix' and sys.platform.startswith('linux'),
                     'Repository source modes require Linux POSIX file identities')
class NativeSDKOriginalHelperSourceModes(unittest.TestCase):
    """Only the exact original repository helper receives source normalization."""

    setUp = NativeSDKAdmission.setUp
    tearDown = NativeSDKAdmission.tearDown
    inspect = NativeSDKAdmission.inspect
    plan = NativeSDKAdmission.plan
    prepare = NativeSDKAdmission.prepare

    def helper(self, mode=0o664):
        # Preserve the real helper source bytes without importing or executing it.
        path = fixture.write(self.fx.repository / 'tools/sdk.py',
                             (ROOT / 'tools/sdk.py').read_bytes(), mode)
        item = {'path': str(path), 'sha256': fixture.sha(path.read_bytes())}
        self.fx.restoration['helper'] = item
        self.fx.restoration['command']['argv'][2] = str(path)
        self.fx.flush()
        return path, item

    def test_exact_repository_helper_0664_keeps_physical_facts_and_strict_cached_roles(self):
        import appended_engine_native_inputs as native
        path, item = self.helper()
        before = path.stat()
        inputs = native.InputSet()
        with no_execution():
            record = sdk._original_helper(inputs, item, repository_root=self.fx.repository)
            inputs.recheck()
            with self.assertRaises(ValueError):
                sdk._file(inputs, path, item['sha256'], 'sdk-asset')
        self.assertEqual(record['mode'], 0o644)
        self.assertEqual(record['physical_mode'], 0o664)
        self.assertEqual(record['mode_policy'], 'repository-producer-logical-v1')
        self.assertIn('sdk-provenance-original-helper', record['roles'])
        self.assertEqual(path.stat(), before)

    def test_original_helper_survives_passive_admission_prepare_and_explicit_fork_binding(self):
        import appended_engine_native_inputs as native
        path, item = self.helper()
        original_argv = list(self.fx.restoration['command']['argv'])
        with no_archive_reads(self.fx):
            inspection = self.inspect()
            _, output = self.prepare()
        records = {row['path']: row for row in inspection.as_dict()['inputs']}
        self.assertEqual(records[str(path)]['physical_mode'], 0o664)
        binding = json.loads((output / 'sdk-admission.json').read_bytes())
        with no_execution(), no_archive_reads(self.fx):
            sdk.validate_sdk_binding(binding, output, native.InputSet(),
                                     target=self.fx.request['target'], repository_root=self.fx.repository)
            with self.assertRaises(ValueError):
                sdk.validate_sdk_binding(binding, output, native.InputSet(),
                                         target=self.fx.request['target'], repository_root=ROOT)
        self.assertEqual(self.fx.restoration['helper'], item)
        self.assertEqual(self.fx.restoration['command']['argv'], original_argv)
        self.assertEqual(path.stat().st_mode & 0o777, 0o664)

    def test_noncanonical_helper_controller_and_sdk_program_modes_remain_strict(self):
        paths = (self.fx.helper, Path(self.fx.restoration['controller']['path']),
                 Path(self.fx.observations['tools']['cxx']['path']))
        for path in paths:
            with self.subTest(path=path):
                mode = path.stat().st_mode & 0o777
                path.chmod(0o664)
                try:
                    with no_archive_reads(self.fx), self.assertRaises(ValueError):
                        self.inspect()
                finally:
                    path.chmod(mode)

    def test_source_authority_does_not_transfer_to_another_repository_or_unsupported_mode(self):
        import appended_engine_native_inputs as native
        path, item = self.helper()
        other = self.fx.repository / 'other'
        other.mkdir(mode=0o755)
        with no_execution():
            with self.assertRaises(ValueError):
                sdk._original_helper(native.InputSet(), item, repository_root=other)
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                sdk._original_helper(native.InputSet(), item, repository_root=self.fx.repository)

    def test_helper_capture_preserves_lower_read_limit_and_physical_postflight(self):
        import appended_engine_native_inputs as native
        path, item = self.helper()
        limits = dict(self.fx.request['limits'], maximum_document_bytes=8)
        with no_execution():
            with self.assertRaises(ValueError):
                sdk._original_helper(sdk._Capture(native.InputSet(), limits), item,
                                     repository_root=self.fx.repository)
            inputs = native.InputSet()
            sdk._original_helper(inputs, item, repository_root=self.fx.repository)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                inputs.recheck()


@unittest.skipUnless(os.name == 'posix' and sys.platform.startswith('linux'),
                     'Generated SDK metadata requires Linux POSIX file identities')
class NativeSDKGeneratedManifestModes(unittest.TestCase):
    setUp = NativeSDKAdmission.setUp
    tearDown = NativeSDKAdmission.tearDown
    inspect = NativeSDKAdmission.inspect
    plan = NativeSDKAdmission.plan
    prepare = NativeSDKAdmission.prepare

    def manifest(self):
        path = self.fx.sdk / 'sdk.json'
        path.chmod(0o600)
        return path

    def test_supported_generated0600_manifest_keeps_physical_facts_and_logical0644(self):
        path = self.manifest()
        before = path.read_bytes()
        with no_archive_reads(self.fx):
            inspection = self.inspect()
            inspection.recheck()
        data = inspection.as_dict()
        record = next(row for row in data['inputs'] if row['path'] == str(path))
        self.assertEqual(record['mode'], 0o644)
        self.assertEqual(record['physical_mode'], 0o600)
        self.assertEqual(record['mode_policy'], 'generated-sdk-root-manifest-v1')
        self.assertEqual(data['sdk_inventory']['modes']['sdk.json'], 0o644)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_generated_manifest_survives_prepared_binding_and_typed_inventory_recheck(self):
        import appended_engine_native_inputs as native
        path = self.manifest()
        with no_archive_reads(self.fx):
            _, output = self.prepare()
            capture = native.InputSet()
            binding = sdk.validate_sdk_binding(json.loads((output / 'sdk-admission.json').read_bytes()),
                output, capture, target=sdk.TARGET, repository_root=self.fx.repository)
            capture.sdk_inventory({'root': binding['root'], 'inventory': binding['inventory']},
                output, 'typed-original-sdk', binding=binding)
            capture.recheck()
        self.assertEqual(binding['modes']['sdk.json'], 0o644)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_every_other_sdk_leaf_and_cached_strict_role_keeps_original_mode_rule(self):
        import appended_engine_native_inputs as native
        path = self.manifest()
        capture = native.InputSet()
        capture.sdk_manifest_file(path, fixture.sha(path.read_bytes()), 'typed-manifest',
            sdk_root=self.fx.sdk, manifest_sha256=fixture.sha(path.read_bytes()))
        with self.assertRaises(ValueError):
            sdk._file(capture, path, fixture.sha(path.read_bytes()), 'arbitrary-original-data')
        ordinary = self.fx.sdk / self.fx.manifest['target']['c_compiler']
        ordinary.chmod(0o600)
        with no_archive_reads(self.fx), self.assertRaises(ValueError):
            self.inspect()

    def test_typed_manifest_applies_callers_lower_document_limit_before_capture(self):
        import appended_engine_native_inputs as native
        path = self.manifest()
        capture = native.InputSet()
        limited = sdk._Capture(capture, dict(maximum_files=10, maximum_input_bytes=2**20,
                                           maximum_document_bytes=1))
        with self.assertRaises(ValueError):
            limited.sdk_manifest_file(path, fixture.sha(path.read_bytes()), 'typed-manifest',
                sdk_root=self.fx.sdk, manifest_sha256=fixture.sha(path.read_bytes()))
        self.assertEqual(capture.records, ())

    def test_generated_mode_does_not_admit_unknown_manifest_schema_or_restore_claim(self):
        import appended_engine_native_inputs as native
        path = self.manifest()
        fixture.write(path, b'{}\n', 0o600)
        with no_execution(), self.assertRaisesRegex(ValueError, 'source-built native SDK manifest'):
            sdk._sdk_metadata({'root': str(self.fx.sdk), 'manifest_sha256': fixture.sha(path.read_bytes())},
                self.fx.request['retained_group'], native.InputSet(), sdk.TARGET)


@unittest.skipUnless(os.name == 'posix' and sys.platform.startswith('linux'),
                     'Generated SDK directories require Linux POSIX file identities')
class NativeSDKGeneratedDirectoryModes(unittest.TestCase):
    setUp = NativeSDKAdmission.setUp
    tearDown = NativeSDKAdmission.tearDown
    inspect = NativeSDKAdmission.inspect
    plan = NativeSDKAdmission.plan
    prepare = NativeSDKAdmission.prepare

    def directories(self):
        parents = {parent for name in self.fx.manifest['files']
                   for parent in (self.fx.sdk / name).parents
                   if parent == self.fx.sdk or self.fx.sdk in parent.parents}
        return sorted(parents)

    def generated_modes(self):
        for path in self.directories():
            path.chmod(0o775)
        (self.fx.sdk / 'sdk.json').chmod(0o600)

    def test_generated_root_and_nested0775_are_physical_facts_with_logical0755(self):
        self.generated_modes()
        before = fixture.snapshot(self.fx.sdk)
        root_before = sdk._identity(self.fx.sdk.lstat())
        with no_archive_reads(self.fx):
            inspection = self.inspect()
            inspection.recheck()
        data = inspection.as_dict()
        facts = data['sdk_directory_facts']
        self.assertEqual([row['path'] for row in facts], [str(path) for path in self.directories()])
        for row in facts:
            self.assertEqual(row['sdk_root'], str(self.fx.sdk))
            self.assertEqual(row['manifest_sha256'], self.fx.request['sdk']['manifest_sha256'])
            self.assertEqual(row['physical_mode'], 0o775)
            self.assertEqual(row['mode'], 0o755)
            self.assertEqual(row['mode_policy'], 'generated-sdk-manifest-parent-directories-v1')
            self.assertEqual(row['identity'], list(sdk._identity(Path(row['path']).lstat())))
        self.assertEqual(data['sdk_inventory']['modes']['bin'], 0o755)
        self.assertEqual(data['sdk_inventory']['modes']['sdk.json'], 0o644)
        self.assertFalse({row['path'] for row in facts} & {row['path'] for row in data['inputs']})
        self.assertEqual(fixture.snapshot(self.fx.sdk), before)
        self.assertEqual(sdk._identity(self.fx.sdk.lstat()), root_before)

    def test_prepared_plan_keeps_directory_facts_and_sdk_inventory_stays_three_fields(self):
        import appended_engine_native_inputs as native
        self.generated_modes()
        with no_archive_reads(self.fx):
            plan, plan_path = self.plan()
            receipt, output = self.prepare(plan_path)
            capture = native.InputSet()
            binding = sdk.validate_sdk_binding(json.loads((output / 'sdk-admission.json').read_bytes()),
                output, capture, target=sdk.TARGET, repository_root=self.fx.repository)
            capture.sdk_inventory({'root': binding['root'], 'inventory': binding['inventory']},
                output, 'typed-sdk', binding=binding)
            capture.recheck()
        self.assertEqual(set(json.loads((output / 'inventories/sdk.json').read_bytes())),
                         {'files', 'directories', 'modes'})
        self.assertEqual(len(plan['inspection']['sdk_directory_facts']), len(self.directories()))
        self.assertEqual({row['physical_mode'] for row in capture.sdk_directory_records}, {0o775})
        self.assertIn('sdk-admission.json', receipt['outputs'])
        self.assertEqual(stat.S_IMODE(self.fx.sdk.stat().st_mode), 0o775)

    def test_directory_normalization_never_admits_forbidden_modes(self):
        for name in ('.', 'bin'):
            path = self.fx.sdk if name == '.' else self.fx.sdk / name
            for mode in (0o700, 0o777, 0o1775, 0o2775):
                with self.subTest(name=name, mode=oct(mode)):
                    path.chmod(mode)
                    try:
                        with no_archive_reads(self.fx), self.assertRaises(ValueError):
                            self.inspect()
                    finally:
                        path.chmod(0o755)

    def test_directory_authority_rejects_empty_extras_and_symlinked_parents(self):
        unknown = self.fx.sdk / 'unknown-empty'
        unknown.mkdir(mode=0o775)
        with no_archive_reads(self.fx), self.assertRaises(ValueError):
            self.inspect()
        unknown.rmdir()
        path = self.fx.sdk / 'share'
        saved = self.case_root / 'old-share'
        path.rename(saved)
        path.symlink_to(saved, target_is_directory=True)
        with no_archive_reads(self.fx), self.assertRaises(ValueError):
            self.inspect()

    def test_recheck_does_not_hide_a_physical_directory_mode_change(self):
        self.generated_modes()
        with no_archive_reads(self.fx):
            inspection = self.inspect()
            (self.fx.sdk / 'bin').chmod(0o755)
            with self.assertRaises(ValueError):
                inspection.recheck()

    def test_sdk_directory_capture_applies_lower_bound_before_underlying_call(self):
        native = mock.Mock()
        native.sdk_directory.return_value = {'mode': 0o755}
        capture = sdk._Capture(native, dict(maximum_files=1, maximum_input_bytes=2**20,
                                            maximum_document_bytes=2**20))
        arguments = dict(sdk_root=self.fx.sdk,
                         manifest_sha256=self.fx.request['sdk']['manifest_sha256'])
        capture.sdk_directory(self.fx.sdk, **arguments)
        with self.assertRaisesRegex(ValueError, 'directory count bound'):
            capture.sdk_directory(self.fx.sdk / 'bin', **arguments)
        self.assertEqual(native.sdk_directory.call_count, 1)
        self.assertEqual(native.sdk_directory.call_args.kwargs['maximum_directories'], 1)


if __name__ == '__main__':
    unittest.main()
