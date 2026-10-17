#!/usr/bin/env python3
"""Native SDK admission fixtures; no compiler, engine or external tool is run."""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_engine_kernel_sdk as admission
import dependency_archive
import dependency_store
import sdk_manifest
import windows_compiler
import windows_toolchain


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class NativeKernelSdkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native kernel sdk fixture ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve(strict=True)
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        # Fail immediately if an admission path attempts tool discovery by execution.
        for name in ('run', 'check_call', 'check_output', 'Popen'):
            self.patches.enter_context(mock.patch.object(subprocess, name,
                side_effect=AssertionError('SDK admission must not launch a subprocess')))
        self.patches.enter_context(mock.patch.dict(os.environ, {}, clear=True))
        self.sdk = self.root / 'linux sdk'
        self.cxx = self.file(self.sdk / 'bin/c++', b'inert CXX compiler fixture')
        self.cc = self.file(self.sdk / 'bin/cc', b'inert C compiler fixture')
        self.sysroot = self.sdk / 'sysroot'
        self.file(self.sysroot / 'usr/include/fixture.h', b'inert target header')
        self.linux_target = {'system': 'Linux', 'processor': 'x86_64',
            'triple': 'x86_64-linux-gnu', 'pointer_bits': 64}
        self.linux_metadata = {'schema_version': 1, 'kind': 'source-build',
            'recipe_id': 'a' * 64, 'target': {
                'system': 'Linux', 'processor': 'x86_64', 'triple': 'x86_64-linux-gnu',
                'cxx_compiler': 'bin/c++', 'c_compiler': 'bin/cc', 'sysroot': 'sysroot'},
            'files': self.inventory(self.sdk)}
        self.write_metadata(self.sdk, self.linux_metadata)
        self.toolchain = ROOT / 'cmake/toolchains/sdk.cmake'

        self.dependencies = self.root / 'windows dependencies'
        self.file(self.dependencies / 'prefix/NOTICE', b'inert Windows dependency notice')
        self.file(self.dependencies / 'prefix/lib/fixture.lib', b'inert static library')
        self.windows_target = {'system': 'Windows', 'processor': 'x86_64',
            'triple': 'x64-windows-static', 'pointer_bits': 64}
        self.windows_metadata = {'schema_version': 1, 'kind': 'windows-dependencies',
            'recipe_id': 'b' * 64,
            'target': {'system': 'Windows', 'processor': 'x86_64',
                'triple': 'x64-windows-static', 'sysroot': 'prefix'},
            'sources_sha256': 'c' * 64, 'licenses': ['prefix/NOTICE'],
            'provenance': {'toolset': 'v143', 'crt_linkage': 'static',
                'library_linkage': 'static', 'lto': False},
            'external_toolchain': {'toolset': 'v143', 'minimum_linker': '14.44.35207',
                'windows_sdk': '10.0.22621.0'},
            'files': self.inventory(self.dependencies)}
        self.write_metadata(self.dependencies, self.windows_metadata)
        self.group = self.root / 'retained group'
        self.group.mkdir()
        self.group_names = dependency_store.names(self.windows_metadata['recipe_id'])
        for name in self.group_names:
            self.file(self.group / name, ('inert group member: ' + name).encode())
        self.selected = {
            'cl.exe': self.file(self.root / 'toolkit/bin/Hostx64/x64/cl.exe', b'inert selected compiler'),
            'link.exe': self.file(self.root / 'toolkit/bin/Hostx64/x64/link.exe', b'inert selected linker')}
        self.linker_info = {'path': str(self.selected['link.exe']),
            'sha256': sha(self.selected['link.exe']), 'version': '14.44.35207.0',
            'architecture': 'x86_64'}

    @staticmethod
    def file(path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    @staticmethod
    def inventory(root):
        return {path.relative_to(root).as_posix(): sha(path)
            for path in root.rglob('*') if path.is_file() and path.name != 'sdk.json'}

    @staticmethod
    def write_metadata(root, metadata):
        (root / 'sdk.json').write_text(json.dumps(metadata, sort_keys=True) + '\n', encoding='utf-8')

    def linux(self, **overrides):
        options = dict(sdk=self.sdk, expected_sdk=sha(self.sdk / 'sdk.json'),
            kernel_target=copy.deepcopy(self.linux_target), cxx_compiler=self.cxx,
            c_compiler=self.cc, sysroot=self.sysroot, toolchain=self.toolchain)
        options.update(overrides)
        return admission.verify_native_kernel_sdk(**options)

    @contextlib.contextmanager
    def windows_inputs(self, *, native=True):
        """Mock retained archive and native API admission, keeping file checks real."""
        complete_verifier = dependency_store.verify_group
        binary_verifier = dependency_store.verify_binary_group
        def group_inventory(verifier, group, recipe):
            if Path(group) != self.group:
                return verifier(group, recipe)
            return self.inventory(self.group)
        with contextlib.ExitStack() as patches:
            mocks = {}
            mocks['native'] = patches.enter_context(mock.patch.object(admission, '_native_windows', return_value=native))
            mocks['complete'] = patches.enter_context(mock.patch.object(dependency_store, 'verify_group',
                side_effect=lambda group, recipe: group_inventory(complete_verifier, group, recipe)))
            mocks['binary'] = patches.enter_context(mock.patch.object(dependency_store, 'verify_binary_group',
                side_effect=lambda group, recipe: group_inventory(binary_verifier, group, recipe)))
            mocks['archive'] = patches.enter_context(mock.patch.object(dependency_archive, 'inspect_manifest_archive',
                side_effect=lambda *args, **kwargs: (copy.deepcopy(self.windows_metadata),
                    sha(self.dependencies / 'sdk.json'))))
            mocks['toolkit'] = patches.enter_context(mock.patch.object(windows_compiler, '_select_toolkit',
                return_value=self.selected))
            mocks['linker'] = patches.enter_context(mock.patch.object(windows_toolchain, 'inspect_selected_linker',
                return_value=self.linker_info))
            yield mocks

    def windows(self, **overrides):
        options = dict(windows_dependencies=self.dependencies,
            expected_sdk=sha(self.dependencies / 'sdk.json'),
            kernel_target=copy.deepcopy(self.windows_target),
            cxx_compiler=self.selected['cl.exe'], c_compiler=self.selected['cl.exe'],
            linker=self.selected['link.exe'], dependency_group=self.group)
        options.update(overrides)
        return admission.verify_native_kernel_sdk(**options)

    def assert_metadata(self, result, root, target, kind):
        self.assertEqual(result['scope'], 'verified-native-kernel-sdk')
        self.assertEqual(result['sdk_sha256'], sha(root / 'sdk.json'))
        self.assertEqual(result['target'], target)
        self.assertEqual(Path(result['root']), root)
        self.assertEqual(result['kind'], kind)

    def test_linux_selection_returns_verified_exact_target_without_native_tool_inspection(self):
        with mock.patch.object(windows_compiler, '_select_toolkit') as toolkit, \
                mock.patch.object(windows_toolchain, 'inspect_selected_linker') as linker:
            result = self.linux()
        self.assert_metadata(result, self.sdk, self.linux_target, 'linux-sdk')
        toolkit.assert_not_called()
        linker.assert_not_called()

    def test_linux_aarch64_uses_its_declared_triple(self):
        self.linux_metadata['target'].update(processor='aarch64', triple='aarch64-linux-gnu')
        self.write_metadata(self.sdk, self.linux_metadata)
        target = dict(self.linux_target, processor='aarch64', triple='aarch64-linux-gnu')
        self.assert_metadata(self.linux(kernel_target=target), self.sdk, target, 'linux-sdk')

    def test_exactly_one_sdk_selector_is_required(self):
        base = dict(expected_sdk='a' * 64, kernel_target=self.linux_target, cxx_compiler=self.cxx)
        for selectors in ({}, {'sdk': self.sdk, 'windows_dependencies': self.dependencies}):
            with self.subTest(selectors=selectors), self.assertRaises(ValueError):
                admission.verify_native_kernel_sdk(**base, **selectors)

    def test_manifest_pin_is_required_exactly_and_checked_before_native_inspection(self):
        for value in ('a' * 63, 'A' * 64, 'a' * 64 + '\n', '0' * 64):
            with self.subTest(pin=value), self.windows_inputs() as checks, self.assertRaises(ValueError):
                self.windows(expected_sdk=value)
            checks['toolkit'].assert_not_called()
            checks['linker'].assert_not_called()

    def test_branch_specific_inputs_cannot_be_silently_ignored(self):
        for extra in ({'linker': self.selected['link.exe']}, {'dependency_group': self.group}):
            with self.subTest(branch='linux', extra=extra), self.assertRaises(ValueError):
                self.linux(**extra)
        for extra in ({'sysroot': self.sysroot}, {'toolchain': self.toolchain}):
            with self.subTest(branch='windows', extra=extra), self.windows_inputs(), self.assertRaises(ValueError):
                self.windows(**extra)

    def test_native_target_rejects_browser_unsupported_architecture_and_pointer_width(self):
        targets = [dict(self.linux_target, pointer_bits=value) for value in (32, True, '64')]
        targets += [dict(self.linux_target, system='Emscripten', processor='wasm32', triple='wasm32-emscripten'),
            dict(self.linux_target, processor='riscv64'), dict(self.linux_target, system='Darwin')]
        for target in targets:
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.linux(kernel_target=target)

    def test_same_platform_and_cpu_cannot_hide_a_different_target_triple(self):
        with self.assertRaises(ValueError):
            self.linux(kernel_target=dict(self.linux_target, triple='x86_64-unknown-linux-gnu'))
        with self.windows_inputs(), self.assertRaises(ValueError):
            self.windows(kernel_target=dict(self.windows_target, triple='x86_64-pc-windows-msvc'))

    def test_linux_configured_compiler_must_be_the_declared_file(self):
        foreign = self.file(self.root / 'foreign/bin/c++', self.cxx.read_bytes())
        with self.assertRaises(ValueError):
            self.linux(cxx_compiler=foreign)

    def test_linux_configured_sysroot_must_be_the_declared_directory(self):
        foreign = self.root / 'foreign sysroot'
        self.file(foreign / 'usr/include/fixture.h', b'inert target header')
        for selected in (foreign, None):
            with self.subTest(sysroot=selected), self.assertRaises(ValueError):
                self.linux(sysroot=selected)

    def test_linux_requires_this_repositories_sdk_toolchain(self):
        foreign = self.file(self.root / 'foreign/sdk.cmake', self.toolchain.read_bytes())
        for selected in (foreign, None):
            with self.subTest(toolchain=selected), self.assertRaises(ValueError):
                self.linux(toolchain=selected)

    def test_linux_optional_c_compiler_must_be_declared_and_match(self):
        self.assert_metadata(self.linux(c_compiler=None), self.sdk, self.linux_target, 'linux-sdk')
        foreign = self.file(self.root / 'foreign/bin/cc', self.cc.read_bytes())
        with self.assertRaises(ValueError):
            self.linux(c_compiler=foreign)
        del self.linux_metadata['target']['c_compiler']
        self.write_metadata(self.sdk, self.linux_metadata)
        with self.assertRaises(ValueError):
            self.linux()

    def test_linux_rejects_ambient_compiler_and_loader_overrides(self):
        for name in ('CC', 'CXX', 'CPATH', 'LIBRARY_PATH', 'LD_PRELOAD'):
            with self.subTest(variable=name), mock.patch.dict(os.environ, {name: 'foreign'}), \
                    self.assertRaises(ValueError):
                self.linux()

    def test_linux_does_not_accept_missing_or_uninventoried_sdk_inputs(self):
        self.cxx.unlink()
        with self.assertRaises(ValueError):
            self.linux()
        self.file(self.cxx, b'inert CXX compiler fixture')
        self.file(self.sdk / 'bin/unrecorded-tool', b'uninventoried')
        with self.assertRaises(ValueError):
            self.linux()

    def test_linux_rejects_manifest_change_during_verification(self):
        original = sdk_manifest.verify_sdk
        def verify(root, **kwargs):
            result = original(root, **kwargs)
            self.linux_metadata['fixture_changed'] = True
            self.write_metadata(self.sdk, self.linux_metadata)
            return result
        with mock.patch.object(sdk_manifest, 'verify_sdk', side_effect=verify), self.assertRaises(ValueError):
            self.linux()

    def test_linux_rechecks_file_inventory_after_compiler_binding(self):
        original = sdk_manifest.verify_sdk
        calls = []
        def verify(root, **kwargs):
            result = original(root, **kwargs)
            calls.append(root)
            if len(calls) == 1:
                self.cxx.write_bytes(b'changed after initial admission')
            return result
        with mock.patch.object(sdk_manifest, 'verify_sdk', side_effect=verify), self.assertRaises(ValueError):
            self.linux()

    def test_windows_complete_group_binds_export_and_configured_native_tools(self):
        with self.windows_inputs() as checks, mock.patch.object(sdk_manifest, 'verify_sdk',
                wraps=sdk_manifest.verify_sdk) as verify:
            result = self.windows()
        self.assert_metadata(result, self.dependencies, self.windows_target, 'windows-dependencies')
        checks['complete'].assert_called()
        checks['binary'].assert_not_called()
        checks['archive'].assert_called_once()
        self.assertTrue(any(call.kwargs.get('release') is True for call in verify.call_args_list))
        checks['toolkit'].assert_called()
        checks['linker'].assert_called()

    def test_windows_binary_group_retains_its_explicit_binary_verifier(self):
        (self.group / self.group_names[1]).unlink()
        with self.windows_inputs() as checks:
            self.assert_metadata(self.windows(), self.dependencies, self.windows_target, 'windows-dependencies')
        checks['binary'].assert_called()
        checks['complete'].assert_not_called()

    def test_windows_requires_native_host_before_inspecting_native_tools(self):
        with self.windows_inputs(native=False) as checks, self.assertRaises(ValueError):
            self.windows()
        checks['toolkit'].assert_not_called()
        checks['linker'].assert_not_called()

    def test_windows_requires_matching_retained_group_and_propagates_verifier_failure(self):
        with self.windows_inputs() as checks:
            for group in (None, self.root / 'absent group'):
                with self.subTest(group=group), self.assertRaises((ValueError, OSError)):
                    self.windows(dependency_group=group)
            checks['complete'].side_effect = ValueError('retained pair checksum mismatch')
            with self.assertRaisesRegex(ValueError, 'retained pair checksum mismatch'):
                self.windows()
        checks['toolkit'].assert_not_called()
        checks['linker'].assert_not_called()

    def test_windows_restored_metadata_must_equal_the_pinned_archive_metadata(self):
        archived = copy.deepcopy(self.windows_metadata)
        archived['external_toolchain']['windows_sdk'] = '10.0.99999.0'
        with self.windows_inputs() as checks:
            checks['archive'].side_effect = None
            checks['archive'].return_value = (archived, sha(self.dependencies / 'sdk.json'))
            with self.assertRaises(ValueError):
                self.windows()
        checks['toolkit'].assert_not_called()

    def test_windows_unknown_and_corrupt_group_identity_cannot_reach_native_tools(self):
        complete_verifier = dependency_store.verify_group
        binary_verifier = dependency_store.verify_binary_group
        for corruption in ('checksum', 'unknown-member', 'foreign-recipe'):
            group = self.root / ('corrupt ' + corruption)
            group.mkdir()
            recipe = 'd' * 64 if corruption == 'foreign-recipe' else self.windows_metadata['recipe_id']
            for name in dependency_store.names(recipe):
                self.file(group / name, b'not a valid retained checksum or archive')
            if corruption == 'unknown-member':
                self.file(group / 'unrecorded', b'unknown group member')
            with self.subTest(corruption=corruption), self.windows_inputs() as checks:
                checks['complete'].side_effect = complete_verifier
                checks['binary'].side_effect = binary_verifier
                with self.assertRaises(ValueError):
                    self.windows(dependency_group=group)
            checks['toolkit'].assert_not_called()
            checks['linker'].assert_not_called()
            checks['archive'].assert_not_called()

    def test_windows_archive_manifest_digest_cannot_be_replaced_by_equal_parsed_json(self):
        with self.windows_inputs() as checks:
            checks['archive'].side_effect = None
            checks['archive'].return_value = (copy.deepcopy(self.windows_metadata), 'f' * 64)
            with self.assertRaises(ValueError):
                self.windows()
        checks['toolkit'].assert_not_called()

    def test_windows_static_v143_abi_contract_is_not_relaxed(self):
        for field, value in (('toolset', 'v144'), ('crt_linkage', 'dynamic'),
                ('library_linkage', 'dynamic'), ('lto', True), ('lto', 0)):
            original = copy.deepcopy(self.windows_metadata)
            self.windows_metadata['provenance'][field] = value
            self.write_metadata(self.dependencies, self.windows_metadata)
            with self.subTest(field=field, value=value), self.windows_inputs(), self.assertRaises(ValueError):
                self.windows()
            self.windows_metadata = original
            self.write_metadata(self.dependencies, original)

    def test_windows_configured_compilers_and_linker_must_identify_selected_toolkit_files(self):
        foreign_compiler = self.file(self.root / 'foreign/cl.exe', self.selected['cl.exe'].read_bytes())
        foreign_linker = self.file(self.root / 'foreign/link.exe', self.selected['link.exe'].read_bytes())
        for extra in ({'cxx_compiler': foreign_compiler}, {'c_compiler': foreign_compiler},
                {'linker': foreign_linker}, {'linker': None}):
            with self.subTest(extra=extra), self.windows_inputs(), self.assertRaises(ValueError):
                self.windows(**extra)
        with self.windows_inputs():
            self.assert_metadata(self.windows(c_compiler=None), self.dependencies,
                self.windows_target, 'windows-dependencies')

    def test_windows_linker_native_inspection_failure_and_old_version_fail_closed(self):
        for version in ('14.44.35206.9', '14.43.99999.0'):
            self.linker_info['version'] = version
            with self.subTest(version=version), self.windows_inputs(), self.assertRaises(ValueError):
                self.windows()
        with self.windows_inputs() as checks:
            checks['linker'].side_effect = ValueError('unverified native version resource')
            with self.assertRaisesRegex(ValueError, 'unverified native version resource'):
                self.windows()

    def test_windows_linker_inspection_must_describe_the_selected_linker_file(self):
        foreign = self.file(self.root / 'foreign/link.exe', self.selected['link.exe'].read_bytes())
        self.linker_info['path'] = str(foreign)
        with self.windows_inputs(), self.assertRaises(ValueError):
            self.windows()

    def test_windows_rejects_toolkit_mutation_during_native_linker_inspection(self):
        def inspect():
            self.selected['cl.exe'].write_bytes(b'changed during native inspection')
            return self.linker_info
        with self.windows_inputs() as checks:
            checks['linker'].side_effect = inspect
            with self.assertRaises(ValueError):
                self.windows()

    def test_windows_rejects_group_mutation_after_retained_verification(self):
        original = copy.deepcopy(self.windows_metadata)
        def inspect(*args, **kwargs):
            (self.group / self.group_names[0]).write_bytes(b'changed retained archive')
            return original, sha(self.dependencies / 'sdk.json')
        with self.windows_inputs() as checks:
            checks['archive'].side_effect = inspect
            with self.assertRaises(ValueError):
                self.windows()

    def test_windows_rechecks_export_inventory_and_manifest_after_tool_binding(self):
        for mutation in ('library', 'manifest'):
            library = self.dependencies / 'prefix/lib/fixture.lib'
            original = library.read_bytes()
            def inspect():
                if mutation == 'library':
                    library.write_bytes(b'changed after export admission')
                else:
                    changed = copy.deepcopy(self.windows_metadata)
                    changed['fixture_changed'] = True
                    self.write_metadata(self.dependencies, changed)
                return self.linker_info
            with self.subTest(mutation=mutation), self.windows_inputs() as checks:
                checks['linker'].side_effect = inspect
                with self.assertRaises(ValueError):
                    self.windows()
            library.write_bytes(original)
            self.write_metadata(self.dependencies, self.windows_metadata)


if __name__ == '__main__':
    unittest.main()
