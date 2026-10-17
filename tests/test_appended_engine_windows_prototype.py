"""Synthetic bytes, mocked Jobs and isolated Python CLI; no build tools or provider run."""
import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended_engine_windows_prototype as prototype
import appended_engine_windows_contract as contract
from appended_engine_native_binary_test import pe_fixture
from test_appended_engine_windows_contract import inputs as native_inputs_fixture


def reference(path):
    return {'path': path, 'sha256': hashlib.sha256(path.encode()).hexdigest()}


def limits():
    return {'configure_seconds': 30, 'build_seconds': 60, 'cleanup_seconds': 2,
        'maximum_jobs': 2, 'maximum_processes': 16, 'maximum_output_bytes': 1024 * 1024,
        'maximum_log_bytes': 4096}


def selection():
    return {'schema_version': 1, 'kind': prototype.SELECTION_KIND,
        'handoff': {'root': 'C:/retained/handoff', 'sha256': '1' * 64},
        'admission': reference('C:/records/admission.json'),
        'output_root': 'C:/work/candidate', 'phase_limits': limits()}


def object_bytes(directives=b'/DEFAULTLIB:libcmt /FAILIFMISMATCH:"RuntimeLibrary=MT_StaticRelease"', *, big=False):
    header_size = 56 if big else 20
    raw = bytearray(header_size + 40 + len(directives))
    if big:
        struct.pack_into('<HHHHI', raw, 0, 0, 0xffff, 2, 0x8664, 0)
        raw[12:28] = bytes.fromhex('c7a1bad1eebaa94baf20faf66aa4dcb8')
        struct.pack_into('<III', raw, 44, 1, 0, 0)
    else:
        struct.pack_into('<HHIIIHH', raw, 0, 0x8664, 1, 0, 0, 0, 0, 0)
    raw[header_size:header_size + 8] = b'.drectve'
    struct.pack_into('<II', raw, header_size + 16, len(directives), header_size + 40)
    raw[header_size + 40:] = directives
    return bytes(raw)


def archive(members):
    raw = bytearray(b'!<arch>\n')
    for name, body in members:
        raw += (name.ljust(16) + '0'.ljust(12) + '0'.ljust(6) + '0'.ljust(6) +
                '644'.ljust(8) + str(len(body)).ljust(10) + '`\n').encode('ascii')
        raw += body
        if len(body) & 1: raw += b'\n'
    return bytes(raw)


def relocation_object(*, big=False, symbol_index=0, auxiliary_value=0, auxiliary_records=0):
    raw = bytearray(object_bytes(bytes(4), big=big)); header = 56 if big else 20
    raw[header:header + 8] = b'.text\0\0\0'
    relocations = len(raw); raw += struct.pack('<IIH', 0, symbol_index, 0x0004)
    symbols = len(raw)
    raw += struct.pack('<8sIiHBB' if big else '<8sIhHBB', b'target\0\0', 0, 1, 0, 2, auxiliary_value)
    raw += bytes((20 if big else 18) * auxiliary_records)
    raw += struct.pack('<I', 4)
    struct.pack_into('<II', raw, 48 if big else 8, symbols, 1 + auxiliary_records)
    struct.pack_into('<I', raw, header + 24, relocations)
    struct.pack_into('<H', raw, header + 32, 1)
    return bytes(raw)


def admission_fixture():
    """A virtual complete inventory of tiny synthetic images, never real tools."""
    native = native_inputs_fixture()
    pe = bytearray(pe_fixture()); struct.pack_into('<H', pe, 150, 0x22); pe = bytes(pe)
    lib = archive([('x.obj/', object_bytes())])
    raw = {}
    inventory_refs = {role: reference('C:/records/' + role + '.json') for role in prototype.INVENTORY_ROLES}
    inventory_refs['msvc_stl'] = copy.deepcopy(native['toolchain']['msvc_stl']['inventory'])
    inventory_refs['windows_sdk'] = copy.deepcopy(native['toolchain']['windows_sdk']['inventory'])
    inventory_refs['native_dependencies'] = copy.deepcopy(native['dependency_inventory'])
    roots = {'llvm': 'C:/retained/llvm', 'msvc_stl': 'C:/retained/msvc',
        'windows_sdk': 'C:/retained/windows-sdk', 'native_dependencies': native['dependency_prefix'],
        'host_generators': 'C:/retained/generators', 'product_assets': 'C:/retained/assets'}
    versions = {'llvm': '19.1.7', 'msvc_stl': '14.40.33807', 'windows_sdk': '10.0.26100.0'}
    inventories = {role: {'reference': inventory_refs[role], 'root': root,
        'version': versions.get(role, '1'), 'files': {}, 'directories': ['bin', 'include', 'lib'],
        'protected_paths': [root, inventory_refs[role]['path'],
            'C:/provenance-authority/' + role + '.json', 'C:/source-authority/' + role + '.source',
            'C:/notice-authority/' + role + '.notice', 'C:/report-authority/' + role + '.report']}
        for role, root in roots.items()}
    def add(role, path, body):
        name = path[len(roots[role]) + 1:]; raw[path] = body
        item = {'sha256': prototype.digest(body), 'bytes': len(body)}
        inventories[role]['files'][name] = item
        return {'path': path, 'sha256': item['sha256']}
    programs = {}
    for role, names in prototype.PROGRAM_NAMES.items():
        owner = 'llvm' if role in ('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool') else 'host_generators'
        programs[role] = add(owner, roots[owner] + '/bin/' + names[0], pe)
    builtins = add('llvm', native['toolchain']['builtins']['path'], lib)
    native['toolchain'].update({role: copy.deepcopy(programs[role]) for role in ('compiler', 'linker')})
    native['toolchain']['builtins'] = copy.deepcopy(builtins)
    crt = {}
    for role in ('libcmt', 'libcpmt', 'libvcruntime', 'libucrt', 'oldnames'):
        owner = 'windows_sdk' if role == 'libucrt' else 'msvc_stl'
        crt[role] = add(owner, roots[owner] + '/lib/' + role + '.lib', lib)
    for target, item in native['libraries'].items():
        selected = add('native_dependencies', item['path'], lib); item['sha256'] = selected['sha256']
    handoff = {'native_inputs': native, **{name: '1' * 64 for name in ('handoff_sha256', 'recipe_sha256',
        'sources_sha256', 'provider_build_sha256', 'metadata_header_sha256', 'toolchain_identity_sha256')}}
    value = {'schema_version': 1, 'kind': 'foundation-native-engine-windows-admission-v1',
        'target': dict(contract.TARGET), **{name: item for name, item in handoff.items() if name.endswith('_sha256')},
        'inventories': inventory_refs, 'programs': programs, 'builtins': builtins, 'crt_libraries': crt,
        'program_versions': {role: {'cmake': '3.31.0', 'ninja': '1.12.1', 'python': '3.13.0',
            'perl': '5.40.0', 'ruby': '3.3.0', 'gperf': '3.1'}.get(role, '19.1.7') for role in programs},
        'include_directories': [roots['msvc_stl'] + '/include'],
        'library_directories': [roots['msvc_stl'] + '/lib', roots['windows_sdk'] + '/lib'],
        'system_root': 'C:/Windows'}
    return value, handoff, inventories, raw


class FakeOwner:
    def __init__(self, *, code=0, poll=None, finish_error=None, cleanup_error=None, close_error=None, active=0):
        self.closed = False
        self.job = mock.Mock(); self.job.active.return_value = active
        self.process = mock.Mock(pid=42)
        self.code, self.poll_values = code, iter(poll or [code])
        self.finish_error, self.cleanup_error, self.close_error = finish_error, cleanup_error, close_error
        self.events = []

    def poll(self):
        self.events.append('poll')
        return next(self.poll_values, self.code)

    def finish(self):
        self.events.append('finish')
        if self.finish_error: raise self.finish_error
        return self.code

    def terminate(self, *, timeout):
        self.events.append(('terminate', timeout))
        if self.cleanup_error: raise self.cleanup_error

    def close(self):
        self.events.append('close')
        if self.close_error: raise self.close_error
        self.closed = True


class WindowsPrototypeTests(unittest.TestCase):
    def admit_fixture(self, value, handoff, inventories, raw):
        with mock.patch.object(prototype, 'inspect_inventory', side_effect=lambda _reference, role: inventories[role]), \
                mock.patch.object(prototype, '_read', side_effect=lambda path, *_args, **_kwargs: raw[str(path)]):
            return prototype._admission(value, handoff)

    def test_admission_joins_finite_inventory_tool_versions_and_static_libraries(self):
        value, handoff, inventories, raw = admission_fixture()
        result = self.admit_fixture(value, handoff, inventories, raw)
        self.assertEqual(result['programs']['compiler'], value['programs']['compiler']['path'])
        self.assertEqual(result['inventories']['windows_sdk']['version'], '10.0.26100.0')
        self.assertIn('C:/report-authority/llvm.report', result['protected_paths'])
        inventories['llvm']['protected_paths'].clear()
        self.assertIn('C:/report-authority/llvm.report', result['protected_paths'])

    def test_inventory_retains_every_original_authority_path_outside_its_root(self):
        root = 'C:/retained/synthetic-assets'; body = b'x'
        inventory_ref = reference('C:/inventory-authority/assets.json')
        provenance_ref = reference('C:/provenance-authority/assets.json')
        value = {'schema_version': 1, 'kind': 'foundation-windows-retained-inventory-v1',
            'role': 'product_assets', 'target': dict(contract.TARGET), 'root': root, 'version': '1',
            'files': {'data.txt': {'sha256': prototype.digest(body), 'bytes': len(body)}},
            'directories': [], 'provenance': provenance_ref}
        originals = {category: [reference('C:/' + category + '-authority/original.data')]
            for category in ('sources', 'notices', 'original_reports')}
        provenance = {'schema_version': 1, 'kind': 'foundation-windows-retained-provenance-v1',
            'role': 'product_assets', 'target': dict(contract.TARGET),
            'inventory_subject_sha256': prototype._inventory_subject(value), **originals}
        child = mock.Mock(path=root + '/data.txt')
        directory = mock.MagicMock(); directory.__enter__.return_value = [child]
        documents = {inventory_ref['path']: value, provenance_ref['path']: provenance}
        with mock.patch.object(prototype, '_document', side_effect=lambda path, _pin: documents[path]), \
                mock.patch.object(prototype, '_ordinary', side_effect=lambda path, **_kwargs: Path(path)), \
                mock.patch.object(prototype.os, 'scandir', return_value=directory), \
                mock.patch.object(prototype, '_read', return_value=body):
            inspected = prototype.inspect_inventory(inventory_ref, 'product_assets')
        expected = [root, inventory_ref['path'], provenance_ref['path'],
            *(originals[category][0]['path'] for category in ('sources', 'notices', 'original_reports'))]
        self.assertEqual(inspected['protected_paths'], expected)
        originals['original_reports'][0]['path'] = 'C:/changed/report'
        self.assertEqual(inspected['protected_paths'], expected)

    def mocked_create_plan(self, output, *, selected_metadata='C:/selection-authority/selection.json'):
        value = selection(); value['output_root'] = output
        admission, handoff, inventories, _raw = admission_fixture()
        handoff.update({'target': dict(contract.TARGET), 'source_catalogue': copy.deepcopy(contract.CATALOGUE),
            'protected_paths': [value['handoff']['root'].replace('/', '\\')],
            'files': {'metadata/inputs.json': '2' * 64,
                'assembled/source/document-provider/runtime/BibNativeDocumentActionsBinding.cpp': '3' * 64,
                'assembled/source/native/BibNativeProviderBootstrap.hpp': '4' * 64},
            'paths': {'retained': 'retained', 'assembled': 'assembled',
                'metadata_header': 'metadata/header.h', 'native_inputs': 'metadata/inputs.json'}})
        admitted = {'inventories': inventories,
            'programs': {name: item['path'] for name, item in admission['programs'].items()},
            'native_inputs': handoff['native_inputs'], 'include_directories': admission['include_directories'],
            'library_directories': admission['library_directories'], 'system_root': admission['system_root'],
            'protected_paths': [path for inventory in inventories.values() for path in inventory['protected_paths']]}
        documents = {selected_metadata: value, value['admission']['path']: admission}
        with mock.patch.object(prototype, '_document', side_effect=lambda path, _pin: documents[str(path)]), \
                mock.patch('appended_engine_windows_handoff.verify_handoff', return_value=handoff), \
                mock.patch.object(prototype, '_admission', return_value=admitted), \
                mock.patch.object(prototype.process_tree, 'launch') as launch:
            result = prototype.create_plan(selected_metadata, '1' * 64)
        launch.assert_not_called()
        return result

    def test_create_plan_protects_selected_metadata_path_with_native_comparison(self):
        for output in ('C:/selection-authority', 'C:/selection-authority/selection.json',
                       'C:/SELECTION-AUTHORITY'):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'overlaps'):
                self.mocked_create_plan(output)

    def test_create_plan_protects_inventory_provenance_and_all_original_paths(self):
        for output in ('C:/records/llvm.json', 'C:/provenance-authority', 'C:/source-authority',
                       'C:/notice-authority', 'C:/report-authority', 'C:/REPORT-AUTHORITY/llvm.report'):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'overlaps'):
                self.mocked_create_plan(output)

    def test_create_plan_disjoint_output_keeps_complete_owned_authority_paths(self):
        result = self.mocked_create_plan('C:/private/fresh-candidate')
        self.assertIs(result['executable_plan'], False)
        self.assertIs(result['build'], False)
        self.assertIn('C:/retained/handoff', result['protected_paths'])
        self.assertNotIn('C:\\retained\\handoff', result['protected_paths'])
        for path in ('C:/selection-authority/selection.json', 'C:/records/admission.json',
                     'C:/records/llvm.json', 'C:/provenance-authority/llvm.json',
                     'C:/source-authority/llvm.source', 'C:/notice-authority/llvm.notice',
                     'C:/report-authority/llvm.report'):
            self.assertIn(path, result['protected_paths'])

    def test_admission_compiler_and_linker_digest_cannot_change_at_same_path(self):
        for role in ('compiler', 'linker'):
            value, handoff, inventories, raw = admission_fixture()
            value['programs'][role]['sha256'] = '2' * 64
            name = value['programs'][role]['path'][len(inventories['llvm']['root']) + 1:]
            inventories['llvm']['files'][name]['sha256'] = '2' * 64
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, 'independent pins'):
                self.admit_fixture(value, handoff, inventories, raw)

    def test_admission_cannot_retarget_metadata_or_declare_old_build_tools(self):
        value, handoff, inventories, raw = admission_fixture()
        value['metadata_header_sha256'] = '2' * 64
        with self.assertRaisesRegex(ValueError, 'immutable handoff'): self.admit_fixture(value, handoff, inventories, raw)
        value, handoff, inventories, raw = admission_fixture(); value['program_versions']['cmake'] = '3.23.0'
        with self.assertRaisesRegex(ValueError, 'producer baseline'): self.admit_fixture(value, handoff, inventories, raw)

    def test_admission_missing_non_system_tool_runtime_has_named_missing_input(self):
        value, handoff, inventories, raw = admission_fixture()
        path = value['programs']['python']['path']; image = bytearray(raw[path])
        image[1024:1080] = bytes(56); image[1024:1036] = b'missing.dll\0'; raw[path] = bytes(image)
        with self.assertRaisesRegex(contract.MissingInputs, 'host-tool-runtime'):
            self.admit_fixture(value, handoff, inventories, raw)

    def test_admission_runtime_dll_outside_loader_search_directory_is_missing(self):
        value, handoff, inventories, raw = admission_fixture()
        path = value['programs']['python']['path']; image = bytearray(raw[path])
        image[1024:1080] = bytes(56); image[1024:1036] = b'private.dll\0'; raw[path] = bytes(image)
        private = 'C:/retained/generators/lib/private.dll'; raw[private] = pe_fixture()
        inventories['host_generators']['files']['lib/private.dll'] = {'sha256': prototype.digest(raw[private]), 'bytes': len(raw[private])}
        with self.assertRaisesRegex(contract.MissingInputs, 'loader search'):
            self.admit_fixture(value, handoff, inventories, raw)

    def test_admission_refuses_uninventoried_library_even_with_valid_coff_bytes(self):
        value, handoff, inventories, raw = admission_fixture()
        item = next(iter(value['crt_libraries'].values()))
        name = item['path'][len(inventories['msvc_stl']['root']) + 1:]
        del inventories['msvc_stl']['files'][name]
        with self.assertRaisesRegex(ValueError, 'complete inventory identity'):
            self.admit_fixture(value, handoff, inventories, raw)

    def test_finite_plan_renders_same_graph_and_consumes_transferred_metadata(self):
        value = selection(); base = value['handoff']['root']; source = base + '/assembled'
        files = {'metadata/native-windows-inputs.json': '2' * 64,
            'assembled/source/document-provider/runtime/BibNativeDocumentActionsBinding.cpp': '3' * 64,
            'assembled/source/native/BibNativeProviderBootstrap.hpp': '4' * 64}
        handoff = {'handoff_sha256': '1' * 64, 'files': files,
            'paths': {'retained': 'retained', 'assembled': 'assembled',
                'metadata_header': 'metadata/BibNativeProviderActionsMetadata.generated.h',
                'native_inputs': 'metadata/native-windows-inputs.json'},
            **{name: '5' * 64 for name in ('recipe_sha256', 'sources_sha256', 'provider_build_sha256',
                'metadata_header_sha256', 'toolchain_identity_sha256')}}
        admitted = {'programs': {role: 'C:/tools/' + names[0] for role, names in prototype.PROGRAM_NAMES.items()},
            'native_inputs': {'dependency_prefix': 'C:/dependencies'}, 'admission_sha256': '6' * 64,
            'include_directories': ['C:/stl/include'], 'library_directories': ['C:/stl/lib'], 'system_root': 'C:/Windows'}
        with mock.patch.object(prototype.process_tree, 'launch') as launch:
            result = prototype._candidate_plan(value, handoff, admitted)
        launch.assert_not_called()
        self.assertEqual([item['phase'] for item in result['commands']], ['configure', 'build'])
        self.assertIn(source + '/source/engine', result['commands'][0]['argv'])
        cache = result['rendered']['windows-initial-cache.cmake']
        self.assertIn(base + '/retained/cmake/native-provider.cmake', cache)
        self.assertIn(base + '/metadata/BibNativeProviderActionsMetadata.generated.h', cache)
        self.assertNotIn('generate_native_actions_metadata.py', str(result['commands']))
        self.assertIn('MultiThreaded', cache); self.assertIn('CMAKE_CXX_STANDARD 23', cache)
        self.assertNotIn('CMAKE_CXX_COMPILER_FORCED', str(result['rendered']))
        self.assertIs(result['executable_plan'], False)
        self.assertEqual({item['role'] for item in result['missing_admission']},
            {'windows-publication-adapter', 'native-source-replay', 'native-dependency-producer-proof'})
        for name in prototype.FALSE_FACTS: self.assertIs(result[name], False)

    def test_finite_plan_missing_binding_fails_before_any_write_or_launch(self):
        value = selection()
        handoff = {'paths': {'retained': 'retained', 'assembled': 'assembled',
            'metadata_header': 'metadata/header.h', 'native_inputs': 'metadata/inputs.json'},
            'files': {'metadata/inputs.json': '1' * 64}, 'metadata_header_sha256': '1' * 64}
        admitted = {'programs': {role: 'C:/tools/' + names[0] for role, names in prototype.PROGRAM_NAMES.items()},
                    'native_inputs': {'dependency_prefix': 'C:/dependencies'}}
        with mock.patch.object(prototype.process_tree, 'launch') as launch:
            with self.assertRaisesRegex(contract.MissingInputs, 'native-provider-binding'):
                prototype._candidate_plan(value, handoff, admitted)
        launch.assert_not_called()

    def test_selection_owns_values_and_explicit_limits(self):
        value = selection(); checked = prototype.validate_selection(value)
        value['phase_limits']['maximum_jobs'] = 63
        self.assertEqual(checked['phase_limits']['maximum_jobs'], 2)

    def test_selection_cannot_add_authority_or_unknown_fields(self):
        for name in ('executable_plan', 'publication_qualified', 'native_runtime_qualified'):
            value = selection(); value[name] = True
            with self.subTest(name=name), self.assertRaises(ValueError):
                prototype.validate_selection(value)

    def test_selection_rejects_bool_schema_and_path_aliases(self):
        for path in ('c:/work/out', '//server/share/out', 'C:/work/../out', 'C:/work/NUL', 'C:/work/out:stream'):
            value = selection(); value['output_root'] = path
            with self.subTest(path=path), self.assertRaises(ValueError): prototype.validate_selection(value)
        value = selection(); value['schema_version'] = True
        with self.assertRaises(ValueError): prototype.validate_selection(value)

    def test_selection_rejects_every_handoff_output_overlap(self):
        for path in ('C:/retained/handoff', 'C:/retained', 'C:/retained/handoff/output'):
            value = selection(); value['output_root'] = path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'overlaps'):
                prototype.validate_selection(value)

    def test_limits_reject_bool_missing_unknown_zero_and_unbounded(self):
        for name in limits():
            for replacement in (True, 0, 2 ** 64):
                value = limits(); value[name] = replacement
                with self.subTest(name=name, replacement=replacement), self.assertRaises(ValueError): prototype.validate_limits(value)
        value = limits(); value['memory_qualified'] = True
        with self.assertRaises(ValueError): prototype.validate_limits(value)

    def test_metadata_tamper_missing_and_duplicate_keys_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'metadata.json'
            with self.assertRaises(contract.MissingInputs): prototype._document(path, '1' * 64)
            path.write_bytes(b'{"x":1,"x":2}')
            with self.assertRaisesRegex(ValueError, 'SHA256'): prototype._document(path, '1' * 64)
            with self.assertRaisesRegex(ValueError, 'Duplicate'): prototype._document(path, prototype.digest(path.read_bytes()))

    def test_metadata_unicode_nonfinite_and_size_fail_before_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'metadata.json'
            for raw in (b'{"x":NaN}', b'{"x":"\\ud800"}', b'\xff'):
                path.write_bytes(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError): prototype._document(path, prototype.digest(raw))
            path.write_bytes(b'long')
            with self.assertRaisesRegex(ValueError, 'byte bound'): prototype._read(path, maximum=3)

    def test_metadata_hardlink_and_symbolic_aliases_do_not_admit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); path = root / 'record.json'; path.write_bytes(b'{}')
            os.link(path, root / 'alias.json')
            with self.assertRaisesRegex(ValueError, 'singly linked'): prototype._read(path)
            (root / 'alias.json').unlink()
            if os.name != 'nt':
                (root / 'symlink.json').symlink_to(path)
                with self.assertRaisesRegex(ValueError, 'ordinary'): prototype._read(root / 'symlink.json')

    def test_provider_accepts_actual_tables_and_keeps_all_runtime_facts_false(self):
        result = prototype.inspect_provider(pe_fixture())
        self.assertEqual(result['binary']['exports'], [prototype.GETTER])
        self.assertEqual(result['binary']['needed'], ['KERNEL32.dll'])
        for name in prototype.FALSE_FACTS: self.assertIs(result[name], False)

    def test_tool_pe_machine_and_runtime_imports_are_actual_bytes(self):
        raw = bytearray(pe_fixture()); struct.pack_into('<H', raw, 150, 0x22)
        result = prototype.inspect_tool_image(bytes(raw))
        self.assertEqual(result['needed'], ['kernel32.dll']); self.assertIs(result['dll'], False)
        struct.pack_into('<H', raw, 132, 0xaa64)
        with self.assertRaisesRegex(ValueError, 'x64'): prototype.inspect_tool_image(bytes(raw))
        with self.assertRaisesRegex(ValueError, 'actual PE'): prototype.inspect_tool_image(b'pretend compiler')

    def test_tool_pe_unbacked_import_and_delayed_dependency_reject(self):
        raw = bytearray(pe_fixture()); struct.pack_into('<I', raw, 768 + 12, 0xffff0000)
        with self.assertRaisesRegex(ValueError, 'unbacked'): prototype.inspect_tool_image(bytes(raw))
        raw = bytearray(pe_fixture()); struct.pack_into('<II', raw, 152 + 112 + 13 * 8, 0x1100, 40)
        with self.assertRaisesRegex(ValueError, 'delayed'): prototype.inspect_tool_image(bytes(raw))
        raw = bytearray(pe_fixture()); struct.pack_into('<I', raw, 600, 0x1080)
        with self.assertRaisesRegex(ValueError, 'forwarded'): prototype.inspect_tool_image(bytes(raw))

    def test_tool_pe_declared_image_and_section_alignment_are_enforced(self):
        for offset, value in ((152 + 56, 0), (152 + 56, 4096), (152 + 32, 2048),
                              (152 + 36, 513), (392 + 12, 0x1001)):
            raw = bytearray(pe_fixture()); struct.pack_into('<I', raw, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                prototype.inspect_tool_image(bytes(raw))

    def test_tool_pe_import_lookup_and_iat_need_complete_backed_terminators(self):
        for offset, value in ((768, 0xffff0000), (768 + 16, 0xffff0000), (768 + 16, 0x15f8)):
            raw = bytearray(pe_fixture()); struct.pack_into('<I', raw, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaisesRegex(ValueError, 'unbacked'):
                prototype.inspect_tool_image(bytes(raw))
        raw = bytearray(pe_fixture())
        for at in range(1088, len(raw), 8): struct.pack_into('<Q', raw, at, (1 << 63) | 1)
        with self.assertRaises(ValueError): prototype.inspect_tool_image(bytes(raw))

    def test_tool_pe_absent_clr_directory_does_not_read_section_header_as_metadata(self):
        raw = bytearray(pe_fixture()); section = bytes(raw[392:432])
        struct.pack_into('<H', raw, 148, 224)
        struct.pack_into('<I', raw, 152 + 108, 14)
        raw[376:416] = section
        self.assertEqual(prototype.inspect_tool_image(bytes(raw))['needed'], ['kernel32.dll'])

    def test_provider_rejects_wrong_machine_and_non_dll(self):
        for offset, value in ((132, 0xaa64), (150, 2)):
            raw = bytearray(pe_fixture()); struct.pack_into('<H', raw, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError): prototype.inspect_provider(bytes(raw))

    def test_provider_dynamic_crt_families_are_rejected(self):
        for name in ('msvcrt.dll', 'msvcp140.dll', 'vcruntime140.dll', 'ucrtbase.dll',
                     'api-ms-win-crt-runtime-l1-1-0.dll', 'concrt140.dll', 'vccorlib140.dll'):
            raw = bytearray(pe_fixture()); raw[1024:1080] = bytes(56)
            raw[1024:1024 + len(name) + 1] = name.encode() + b'\0'
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'dynamic CRT'):
                prototype.inspect_provider(bytes(raw))

    def test_provider_unknown_import_paths_and_ads_reject(self):
        for name in ('evil.dll', 'C:/x.dll', 'foo:bar.dll'):
            raw = bytearray(pe_fixture()); raw[1024:1080] = bytes(56)
            raw[1024:1024 + len(name) + 1] = name.encode() + b'\0'
            with self.subTest(name=name), self.assertRaises(ValueError): prototype.inspect_provider(bytes(raw))

    def test_provider_missing_and_forwarded_getters_reject(self):
        raw = bytearray(pe_fixture()); raw[624] = ord('x')
        with self.assertRaisesRegex(ValueError, 'sole getter'): prototype.inspect_provider(bytes(raw))
        raw = bytearray(pe_fixture()); struct.pack_into('<I', raw, 600, 0x1080)
        with self.assertRaisesRegex(ValueError, 'Forwarded'): prototype.inspect_provider(bytes(raw))

    def test_provider_ordinal_export_is_not_hidden_by_getter_name(self):
        raw = bytearray(pe_fixture()); struct.pack_into('<I', raw, 512 + 20, 2)
        struct.pack_into('<II', raw, 600, 0x1300, 0x1308)
        with self.assertRaisesRegex(ValueError, 'sole getter'): prototype.inspect_provider(bytes(raw))

    def test_provider_delay_import_and_non_executable_getter_reject(self):
        raw = bytearray(pe_fixture()); struct.pack_into('<II', raw, 152 + 112 + 13 * 8, 0x1100, 40)
        with self.assertRaisesRegex(ValueError, 'delay import'): prototype.inspect_provider(bytes(raw))
        raw = bytearray(pe_fixture()); struct.pack_into('<I', raw, 392 + 36, 0x40000040)
        with self.assertRaisesRegex(ValueError, 'executable'): prototype.inspect_provider(bytes(raw))

    def test_coff_regular_and_bigobj_static_objects_are_inspected(self):
        for big in (False, True):
            result = prototype.inspect_coff_object(object_bytes(big=big))
            self.assertEqual(result['machine'], 'x86_64')
            self.assertIn('/DEFAULTLIB:libcmt', result['directives'])

    def test_coff_relocations_join_existing_primary_symbols_in_regular_and_bigobj(self):
        for big in (False, True):
            raw = relocation_object(big=big, auxiliary_value=1, auxiliary_records=1)
            with self.subTest(big=big):
                self.assertEqual(prototype.inspect_coff_object(raw)['machine'], 'x86_64')
                self.assertEqual(len(prototype.inspect_static_archive(archive([('unit.obj/', raw)]))['members']), 1)

    def test_coff_relocation_cannot_reference_absent_or_auxiliary_symbol(self):
        for big in (False, True):
            for symbol_index in (1, 2):
                raw = relocation_object(big=big, symbol_index=symbol_index, auxiliary_value=1, auxiliary_records=1)
                with self.subTest(big=big, symbol_index=symbol_index), self.assertRaisesRegex(ValueError, 'existing primary symbol'):
                    prototype.inspect_coff_object(raw)
        raw = bytearray(object_bytes(bytes(4))); raw[20:28] = b'.text\0\0\0'
        offset = len(raw); raw += struct.pack('<IIH', 0, 1, 0x0004)
        struct.pack_into('<I', raw, 20 + 24, offset); struct.pack_into('<H', raw, 20 + 32, 1)
        with self.assertRaisesRegex(ValueError, 'existing primary symbol'):
            prototype.inspect_static_archive(archive([('unit.obj/', bytes(raw))]))

    def test_coff_primary_auxiliary_record_count_cannot_escape_symbol_table(self):
        for big in (False, True):
            with self.subTest(big=big), self.assertRaisesRegex(ValueError, 'auxiliary symbol records'):
                prototype.inspect_coff_object(relocation_object(big=big, auxiliary_value=1))

    def test_microsoft_archive_two_linker_members_are_allowed(self):
        raw = archive([('/', bytes(4)), ('/', bytes(8)), ('unit.obj/', object_bytes())])
        result = prototype.inspect_static_archive(raw)
        self.assertEqual([item['name'] for item in result['members']], ['unit.obj'])

    def test_coff_thin_empty_and_foreign_objects_never_admit(self):
        for raw in (b'!<thin>\n', b'!<arch>\n', archive([('x.obj/', b'\x7fELF' + bytes(60))]),
                    archive([('x.obj/', b'\0asm' + bytes(60))])):
            with self.subTest(raw=raw[:24]), self.assertRaises(ValueError): prototype.inspect_static_archive(raw)

    def test_coff_wrong_architecture_short_import_and_old_import_objects_reject(self):
        raw = bytearray(object_bytes()); struct.pack_into('<H', raw, 0, 0xaa64)
        with self.assertRaisesRegex(ValueError, 'x86_64'): prototype.inspect_coff_object(bytes(raw))
        raw = b'\0\0\xff\xff' + bytes(56)
        with self.assertRaisesRegex(ValueError, 'short import'): prototype.inspect_coff_object(raw)
        raw = bytearray(object_bytes()); raw[20:28] = b'.idata$2'
        with self.assertRaisesRegex(ValueError, 'import-library'): prototype.inspect_coff_object(bytes(raw))

    def test_coff_dynamic_and_debug_crt_directives_reject(self):
        for directive in (b'/DEFAULTLIB:MSVCRT', b'-defaultlib:ucrt.lib', b'/DEFAULTLIB:"vcruntime.lib"',
                b'/DEFAULTLIB:libcmtd', b'/FAILIFMISMATCH:"RuntimeLibrary=MD_DynamicRelease"',
                b'/FAILIFMISMATCH:"RuntimeLibrary=MTd_StaticDebug"'):
            with self.subTest(directive=directive), self.assertRaisesRegex(ValueError, 'CRT|runtime'):
                prototype.inspect_coff_object(object_bytes(directive))

    def test_coff_linker_directives_cannot_select_ambient_paths_or_outputs(self):
        for directive in (b'/LIBPATH:C:/ambient', b'/OUT:C:/foreign.dll', b'@C:/args.rsp', b'/NODEFAULTLIB:libcmt'):
            with self.subTest(directive=directive), self.assertRaisesRegex(ValueError, 'ambient path/output'):
                prototype.inspect_coff_object(object_bytes(directive))
        with self.assertRaisesRegex(ValueError, 'exact static dependency'):
            prototype.inspect_static_archive(archive([('unit.obj/', object_bytes(b'/DEFAULTLIB:evil'))]),
                allowed_default_libraries={'libcmt'})

    def test_coff_string_in_data_is_not_misclassified_as_a_directive(self):
        raw = bytearray(object_bytes(b'/DEFAULTLIB:MSVCRT')); raw[20:28] = b'.rdata\0\0'
        self.assertEqual(prototype.inspect_coff_object(bytes(raw))['directives'], [])

    def test_coff_directive_unterminated_quote_and_bad_archive_padding_reject(self):
        with self.assertRaisesRegex(ValueError, 'quote'):
            prototype.inspect_coff_object(object_bytes(b'/DEFAULTLIB:"libcmt'))
        raw = bytearray(archive([('x.obj/', object_bytes(b'x'))])); raw[-1] = 0
        with self.assertRaisesRegex(ValueError, 'padding'): prototype.inspect_static_archive(bytes(raw))

    def test_coff_archive_path_traversal_duplicates_and_extra_linker_tables_reject(self):
        for members in ([('../x.obj/', object_bytes())], [('x.obj/', object_bytes()), ('X.obj/', object_bytes())],
                        [('/', b'a'), ('/', b'b'), ('/', b'c'), ('x.obj/', object_bytes())]):
            with self.subTest(members=[item[0] for item in members]), self.assertRaises(ValueError): prototype.inspect_static_archive(archive(members))

    def test_coff_truncated_section_and_overlapping_symbol_table_reject(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'): prototype.inspect_coff_object(object_bytes()[:40])
        raw = bytearray(object_bytes()); struct.pack_into('<II', raw, 8, 20, 1)
        with self.assertRaises(ValueError): prototype.inspect_coff_object(bytes(raw))
        raw = bytearray(object_bytes()); struct.pack_into('<I', raw, 20 + 36, 0x01000000)
        with self.assertRaisesRegex(ValueError, 'relocation-overflow'): prototype.inspect_coff_object(bytes(raw))

    def test_coff_archive_index_offsets_and_symbols_must_be_complete(self):
        for body in (b'one', struct.pack('>II', 1, 99999) + b'name\0', bytes(4) + b'unlisted\0'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                prototype.inspect_static_archive(archive([('/', body), ('x.obj/', object_bytes())]))

    def test_coff_long_names_are_bounded_and_cannot_escape(self):
        raw = archive([('//', b'long-object.obj\0'), ('/0', object_bytes())])
        self.assertEqual(prototype.inspect_static_archive(raw)['members'][0]['name'], 'long-object.obj')
        for name in ('../evil.obj', 'C:/evil.obj'):
            with self.assertRaises(ValueError): prototype.inspect_static_archive(archive([('//', name.encode() + b'\0'), ('/0', object_bytes())]))

    def test_cache_rendering_is_closed_and_rejects_cmake_injection(self):
        self.assertEqual(prototype.render_cache(b'set(X "@X@")', {'X': 'C:/a b/tool'}), b'set(X "C:/a b/tool")')
        for value in ('C:/a;message(x)', 'C:/a$<CONFIG>', 'C:/a"x', 'C:/a\\b', 'C:/a@b'):
            with self.subTest(value=value), self.assertRaises(ValueError): prototype.render_cache(b'@X@', {'X': value})
        with self.assertRaises(ValueError): prototype.render_cache(b'@X@', {'X': 'ok', 'Y': 'extra'})

    def test_environment_does_not_inherit_flag_or_interpreter_injection(self):
        admitted = {'programs': {role: 'C:/tools/' + names[0] for role, names in prototype.PROGRAM_NAMES.items()},
            'include_directories': ['C:/stl/include'], 'library_directories': ['C:/stl/lib'], 'system_root': 'C:/Windows'}
        with mock.patch.dict(os.environ, {'CL': '/MD /arch:AVX2', 'PYTHONPATH': 'C:/evil', 'CMAKE_PREFIX_PATH': 'C:/ambient'}):
            environment = prototype.native_environment(admitted, 'C:/work/out')
        self.assertNotIn('CL', environment); self.assertNotIn('PYTHONPATH', environment)
        self.assertNotIn('CMAKE_PREFIX_PATH', environment)
        self.assertEqual(environment['INCLUDE'], 'C:/stl/include')
        self.assertEqual(environment['TEMP'], 'C:/work/out/tmp')

    def test_native_host_guard_rejects_posix_without_reads_or_writes(self):
        with mock.patch.object(prototype.os, 'name', 'posix'), mock.patch.object(prototype, 'create_plan') as plan:
            with self.assertRaisesRegex(ValueError, 'native Windows x64'): prototype.build('/no/read', '1' * 64)
        plan.assert_not_called()

    def test_build_missing_publication_cannot_create_or_replace_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'preserved'; path.write_bytes(b'foreign')
            with mock.patch.object(prototype, 'require_native_host'), \
                    mock.patch.object(prototype, '_document', return_value=selection()) as document, \
                    mock.patch.object(prototype, 'create_plan') as plan, \
                    mock.patch.object(prototype, '_capture_source_adapter') as capture, \
                    mock.patch.object(prototype.process_tree, 'launch') as launch:
                with self.assertRaises(contract.MissingInputs) as caught:
                    prototype.build('/selected', '1' * 64)
            document.assert_called_once_with('/selected', '1' * 64)
            self.assertEqual({row['role'] for row in caught.exception.as_dict()['missing']},
                {'native-source-replay', 'windows-native-input-qualification',
                 'windows-publication-qualification', 'windows-original-dependency-admission'})
            plan.assert_not_called(); capture.assert_not_called(); launch.assert_not_called()
            self.assertEqual(path.read_bytes(), b'foreign')
            self.assertEqual(list(Path(temporary).iterdir()), [path])

    def run_owner(self, owner, **changes):
        values = limits(); values.update(changes)
        with tempfile.TemporaryFile() as stream, mock.patch.object(prototype, 'require_native_host'), \
                mock.patch.object(prototype, '_output_usage', return_value=0), \
                mock.patch.object(prototype.time, 'sleep'), \
                mock.patch.object(prototype.process_tree, 'launch', return_value=owner) as launch:
            result = prototype.run_owned(['C:/tools/cmake.exe', '--build', 'C:/out/cmake'],
                'C:/out', stream, {'SystemRoot': 'C:/Windows'}, values, phase='build', resource_root='C:/out')
            self.assertEqual(launch.call_count, 1)
            return result

    def test_owned_success_requires_finish_then_close_and_zero_exit(self):
        owner = FakeOwner(poll=[None, 0]); result = self.run_owner(owner)
        self.assertEqual(owner.events[-2:], ['finish', 'close'])
        self.assertIs(result['process_tree_closed'], True)

    def test_owned_parent_zero_with_surviving_descendant_is_failure(self):
        owner = FakeOwner(finish_error=prototype.process_tree.ProcessTreeError('descendants outlived'))
        with self.assertRaisesRegex(prototype.process_tree.ProcessTreeError, 'descendants outlived'): self.run_owner(owner)
        self.assertIn(('terminate', 2), owner.events); self.assertEqual(owner.events[-1], 'close')

    def test_owned_nonzero_joins_descendants_before_close(self):
        owner = FakeOwner(code=7)
        with self.assertRaisesRegex(ValueError, 'exited 7'): self.run_owner(owner)
        self.assertEqual(owner.events[-2:], [('terminate', 2), 'close'])

    def test_owned_cleanup_failure_keeps_owner_and_stream_without_close(self):
        owner = FakeOwner(code=1, cleanup_error=RuntimeError('cannot join'))
        before = len(prototype._UNCERTAIN_OWNERS)
        with self.assertRaisesRegex(prototype.process_tree.ProcessTreeError, 'retain log/output'): self.run_owner(owner)
        self.assertEqual(len(prototype._UNCERTAIN_OWNERS), before + 1)
        self.assertNotIn('close', owner.events)
        prototype._UNCERTAIN_OWNERS.pop()

    def test_owned_close_failure_is_not_a_pass(self):
        owner = FakeOwner(close_error=RuntimeError('unconfirmed'))
        with self.assertRaisesRegex(prototype.process_tree.ProcessTreeError, 'close is uncertain'): self.run_owner(owner)
        prototype._UNCERTAIN_OWNERS.pop()

    def test_owned_job_process_count_limit_terminates(self):
        owner = FakeOwner(poll=[None, 0], active=100)
        with self.assertRaisesRegex(ValueError, 'process-count'): self.run_owner(owner)
        self.assertIn(('terminate', 2), owner.events)

    def test_owned_deadline_late_success_never_passes(self):
        owner = FakeOwner()
        with mock.patch.object(prototype.time, 'monotonic', side_effect=[0, 0, 0, 100]):
            with self.assertRaisesRegex(ValueError, 'wall deadline'): self.run_owner(owner)
        self.assertIn(('terminate', 2), owner.events)

    def test_owned_slow_preflight_cannot_launch_after_its_budget(self):
        now = [0]
        def slow(_root): now[0] = 100; return 0
        with tempfile.TemporaryFile() as stream, mock.patch.object(prototype, 'require_native_host'), \
                mock.patch.object(prototype.time, 'monotonic', side_effect=lambda: now[0]), \
                mock.patch.object(prototype, '_output_usage', side_effect=slow), \
                mock.patch.object(prototype.process_tree, 'launch') as launch:
            with self.assertRaisesRegex(ValueError, 'during resource sampling'):
                prototype.run_owned(['C:/cmake.exe'], 'C:/out', stream, {}, limits(), phase='build', resource_root='C:/out')
        launch.assert_not_called()

    def test_owned_launch_uncertainty_preserves_output_reference(self):
        before = len(prototype._UNCERTAIN_OWNERS)
        with tempfile.TemporaryFile() as stream, mock.patch.object(prototype, 'require_native_host'), \
                mock.patch.object(prototype, '_output_usage', return_value=0), \
                mock.patch.object(prototype.process_tree, 'launch', side_effect=prototype.process_tree.ProcessTreeError('launch cleanup uncertain')):
            with self.assertRaisesRegex(prototype.process_tree.ProcessTreeError, 'launch cleanup uncertain'):
                prototype.run_owned(['C:/cmake.exe'], 'C:/out', stream, {}, limits(), phase='build', resource_root='C:/out')
            self.assertEqual(prototype._UNCERTAIN_OWNERS[-1], (None, stream, 'C:/out'))
        self.assertEqual(len(prototype._UNCERTAIN_OWNERS), before + 1)
        prototype._UNCERTAIN_OWNERS.pop()

    def test_inspection_cli_reads_selected_pinned_bytes_without_any_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'provider.dll'; path.write_bytes(pe_fixture())
            with mock.patch.object(prototype.process_tree, 'launch') as launch, redirect_stdout(io.StringIO()) as output:
                code = prototype.cli(['inspect-provider', '--provider', str(path), '--provider-sha256', prototype.digest(path.read_bytes())])
            self.assertEqual(code, 0); self.assertIn('static-pe-machine', output.getvalue()); launch.assert_not_called()

    def test_missing_cli_is_explicit_incomplete_evidence(self):
        missing = contract.MissingInputs([{'role': 'windows-publication-qualification', 'path': 'C:/out', 'reason': 'original qualification is required'}])
        with mock.patch.object(prototype, 'build', side_effect=missing), redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(prototype.cli(['build', '--selection', '/metadata', '--selection-sha256', '1' * 64]), 2)
        self.assertIn('windows-publication-qualification', errors.getvalue())
        self.assertIn('"native_runtime_qualified": false', errors.getvalue())


class WindowsPrototypeEntryTests(unittest.TestCase):
    def cold_cli(self, arguments, *, code=None):
        # This interpreter executes only the maintained source/bootstrap and tiny
        # static fixture. No compiler, provider or native owner is selected.
        argv = [sys.executable, '-I', '-S', '-B']
        if code is None:
            argv += [str(ROOT / 'tools/appended_engine_windows_prototype.py'), *arguments]
        else:
            argv += ['-c', code, str(ROOT / 'tools/appended_engine_windows_prototype.py'), *arguments]
        return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                              check=False, timeout=30)

    def test_cold_isolated_inspection_cli_reads_only_pinned_synthetic_pe(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'synthetic-provider.dll'
            raw = pe_fixture(); path.write_bytes(raw)
            result = self.cold_cli(['inspect-provider', '--provider', str(path),
                '--provider-sha256', hashlib.sha256(raw).hexdigest()])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        value = json.loads(result.stdout)
        self.assertEqual(value['binary']['exports'], [prototype.GETTER])
        self.assertEqual(value['binary']['needed'], ['KERNEL32.dll'])
        for name in prototype.FALSE_FACTS: self.assertIs(value[name], False)

    def test_cold_isolated_entry_rejects_unknown_facade_without_adopting_it(self):
        code = r"""import json, runpy, sys, types
name = 'appended_engine_windows_dependencies'
core = '_foundation_windows_h2d3_controller_core_v1'
foreign = types.ModuleType(name)
def forbidden(*args):
    raise AssertionError('unknown facade was called')
foreign._module = forbidden
sys.modules[name] = foreign
try:
    runpy.run_path(sys.argv[1], run_name='inert_unknown_entry_probe')
except ValueError as error:
    print(json.dumps({'error': str(error), 'same_foreign': sys.modules.get(name) is foreign,
        'core_absent': core not in sys.modules,
        'native_modules_absent': all(key not in sys.modules for key in
            ('appended_engine_windows_source_replay', 'appended_engine_windows_publication',
             'appended_engine_native_consumer', 'process_tree'))}))
else:
    raise AssertionError('unknown facade was accepted')
"""
        result = self.cold_cli([], code=code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        value = json.loads(result.stdout)
        self.assertIn('partial dependency entry registration', value['error'])
        self.assertIs(value['same_foreign'], True)
        self.assertIs(value['core_absent'], True)
        self.assertIs(value['native_modules_absent'], True)

    def test_runtime_cli_uses_only_the_explicit_closed_request_pair(self):
        outcome = {'schema_version': 1, **{name: False for name in prototype.FALSE_FACTS}}
        request = 'C:/retained/runtime-request.json'; pin = '1' * 64
        with mock.patch.object(prototype, '_runtime_maintenance', return_value=outcome) as runtime, \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(prototype.cli(['runtime', '--request', request,
                '--request-sha256', pin]), 0)
        runtime.assert_called_once_with(Path(request), pin)
        self.assertEqual(json.loads(output.getvalue()), outcome)
        for extra in (['--selection', 'C:/selection.json'], ['--provider', 'C:/provider.dll'],
                      ['--publication-sha256', '2' * 64], ['--dependency-admission', 'C:/D.json']):
            with self.subTest(extra=extra), mock.patch.object(prototype, '_runtime_maintenance') as runtime, \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                prototype.cli(['runtime', '--request', request, '--request-sha256', pin, *extra])
            self.assertEqual(caught.exception.code, 2); runtime.assert_not_called()

    def test_actual_source_binding_and_cold_bootstrap_precede_project_imports(self):
        path = ROOT / 'tools/appended_engine_windows_prototype.py'
        self.assertEqual(Path(prototype.__file__).resolve(), path.resolve())
        self.assertEqual(prototype.ROOT, ROOT)
        tree = ast.parse(path.read_bytes())
        call = next(node.lineno for node in tree.body if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
            and node.value.func.id == '_prototype_owned_tools')
        imports = [node.lineno for node in tree.body if isinstance(node, ast.Import)
            and any(alias.name in ('appended_engine_native_consumer',
                'appended_engine_windows_contract', 'process_tree') for alias in node.names)]
        self.assertTrue(imports); self.assertLess(call, min(imports))
        facade = path.with_name('appended_engine_windows_dependencies.py').read_bytes()
        self.assertEqual(prototype._DEPENDENCY_FACADE_SHA256, hashlib.sha256(facade).hexdigest())
        self.assertEqual(prototype._DEPENDENCY_FACADE_BYTES, len(facade))
        source_root = ROOT / 'tools/appended_engine_windows_dependency_support/raw_runtime'
        self.assertEqual(Path(prototype._runtime_maintained_source_root()), source_root)
        self.assertEqual({leaf.relative_to(source_root).as_posix() for leaf in source_root.rglob('*')
                          if leaf.is_file()}, set(prototype._RAW_RUNTIME_SOURCE_PINS))
        for relative, pin in prototype._RAW_RUNTIME_SOURCE_PINS.items():
            with self.subTest(relative=relative):
                self.assertEqual(hashlib.sha256((source_root / relative).read_bytes()).hexdigest(), pin)


if __name__ == '__main__':
    unittest.main()
