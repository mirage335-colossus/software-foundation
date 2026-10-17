"""Small offline regressions for pure Windows dependency support contracts.

Only maintained Python helper source and inert, caller-supplied declarations are
read. These cases establish no native admission, original execution, toolchain
qualification, or eligible retained dependency result.
"""

import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
SUPPORT = TOOLS / 'appended_engine_windows_dependency_support'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def load_source(path):
    """Execute the exact bytes read, without importing a cached bytecode file."""
    module = types.ModuleType('_windows_dependency_support_test_' + path.stem)
    module.__file__ = str(path)
    raw = path.read_bytes()
    exec(compile(raw, str(path), 'exec', dont_inherit=True), vars(module))
    return module


def reference(path, label=None):
    return {'path': path, 'sha256': digest((label or path).encode('ascii'))}


def inventory_documents(role, *, change_inventory=None, change_provenance=None):
    inventory = {'schema_version': 1,
        'kind': 'foundation-windows-retained-inventory-v1', 'role': role,
        'target': {'system': 'Windows', 'processor': 'x86_64',
                   'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64},
        'root': 'C:/retained/' + role, 'version': 'declared-label',
        'files': {'bin/tool.exe': {'sha256': digest(b'inert file declaration'), 'bytes': 7}},
        'directories': ['bin']}
    if change_inventory:
        change_inventory(inventory)
    provenance = {'schema_version': 1,
        'kind': 'foundation-windows-retained-provenance-v1', 'role': role,
        'target': copy.deepcopy(inventory['target']),
        'inventory_subject_sha256': digest(encoded(inventory)),
        'sources': [reference('C:/original/source.json')],
        'notices': [reference('C:/original/notice.txt')],
        'original_reports': [reference('C:/original/report.json')]}
    if change_provenance:
        change_provenance(provenance)
    provenance_raw = encoded(provenance)
    provenance_pin = digest(provenance_raw)
    inventory['provenance'] = {'path': 'C:/original/provenance.json',
                               'sha256': provenance_pin}
    raw = encoded(inventory)
    return raw, digest(raw), provenance_raw, provenance_pin


def identity(version):
    """Independent inert H1/H2 fixture; the Windows paths are never opened."""
    inventories = {
        'llvm': ('C:/llvm', '19.1.7'),
        'msvc_stl': ('C:/msvc', '14.40.33807'),
        'windows_sdk': ('C:/sdk', '10.0.22621.0'),
        'host_generators': ('C:/host', 'retained-tools')}
    programs = {
        'compiler': ('clang-cl.exe', '19.1.7'), 'linker': ('lld-link.exe', '19.1.7'),
        'archiver': ('llvm-lib.exe', '19.1.7'), 'resource_compiler': ('llvm-rc.exe', '19.1.7'),
        'manifest_tool': ('llvm-mt.exe', '19.1.7'), 'cmake': ('cmake.exe', '3.31.6'),
        'ninja': ('ninja.exe', '1.12.1'), 'python': ('python.exe', '3.12.9'),
        'perl': ('perl.exe', '5.40.0'), 'ruby': ('ruby.exe', '3.3.7'),
        'gperf': ('gperf.exe', '3.1')}
    if version == 2:
        programs.update(nmake=('nmake.exe', '14.40.33807'),
                        msbuild=('MSBuild.exe', '17.10.0'))
    llvm_roles = {'compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool'}
    return {'schema_version': version,
        'kind': 'foundation-native-engine-windows-toolchain-identity-v' + str(version),
        'target': {'system': 'Windows', 'processor': 'x86_64',
                   'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64},
        'policy': {'build_type': 'Release', 'crt': 'static-mt',
                   'cpu_baseline': 'x86_64-sse2',
                   'os_floor_declaration': 'windows-10-1809-unqualified',
                   'engine_cxx_standard': 23, 'lto': False},
        'inventories': {role: {'root': root, 'version': release,
                               'subject_sha256': digest(role.encode('ascii'))}
                        for role, (root, release) in inventories.items()},
        'programs': {role: {**reference(('C:/llvm' if role in llvm_roles else 'C:/host')
                                      + '/bin/' + basename), 'version': release}
                     for role, (basename, release) in programs.items()},
        'builtins': reference('C:/llvm/lib/clang_rt.builtins-x86_64.lib'),
        'crt_libraries': {role: reference(('C:/sdk' if role == 'libucrt' else 'C:/msvc')
                                          + '/lib/' + role + '.lib')
                          for role in ('libcmt', 'libcpmt', 'libvcruntime', 'libucrt', 'oldnames')},
        'include_directories': ['C:/llvm/include', 'C:/msvc/include', 'C:/sdk/include'],
        'library_directories': ['C:/llvm/lib', 'C:/msvc/lib', 'C:/sdk/lib'],
        'system_root': 'C:/Windows'}


def capabilities():
    return {'version': {'string': '3.31.6', 'major': 3, 'minor': 31, 'patch': 6,
                        'suffix': '', 'isDirty': False},
            'generators': [{'name': 'Ninja'}], 'fileApi': {},
            'serverMode': False, 'tls': True, 'debugger': True}


class WindowsDependencySupportTests(unittest.TestCase):
    def setUp(self):
        self.h1 = load_source(TOOLS / 'appended_engine_windows_dependency_proof.py')
        self.h2 = load_source(SUPPORT / 'proof_h2.py')
        self.d3 = load_source(SUPPORT / 'proof_d3.py')
        self.inventory = load_source(SUPPORT / 'inventory.py')

    def declaration(self, documents, role='native_dependencies'):
        raw, pin, provenance_raw, provenance_pin = documents
        return self.inventory.inventory_declaration(raw, pin, role,
            provenance_raw=provenance_raw, provenance_pin=provenance_pin)

    def test_six_inventory_roles_join_original_provenance_and_return_owned_data(self):
        roles = ('llvm', 'msvc_stl', 'windows_sdk', 'host_generators',
                 'native_dependencies', 'product_assets')
        self.assertEqual(self.inventory.ROLES, frozenset(roles))
        for role in roles:
            with self.subTest(role=role):
                documents = inventory_documents(role)
                value = self.declaration(documents, role)
                subject = json.loads(documents[0])
                del subject['provenance']
                self.assertEqual(value['subject_sha256'], digest(encoded(subject)))
                self.assertEqual(value['original_refs'], [
                    {'path': 'C:/original/provenance.json', 'sha256': documents[3]},
                    reference('C:/original/source.json'), reference('C:/original/notice.txt'),
                    reference('C:/original/report.json')])
                value['files']['bin/tool.exe']['bytes'] = 100
                value['original_refs'].clear()
                fresh = self.declaration(documents, role)
                self.assertEqual(fresh['files']['bin/tool.exe']['bytes'], 7)
                self.assertEqual(len(fresh['original_refs']), 4)

    def test_inventory_requires_original_pins_and_matching_provenance_subject(self):
        original = inventory_documents('native_dependencies')
        changed = json.loads(original[0])
        changed['files']['bin/tool.exe']['bytes'] += 1
        altered = encoded(changed)
        for documents in ((original[0], digest(b'wrong inventory'), *original[2:]),
                          (original[0], original[1], original[2] + b' ', original[3]),
                          (altered, digest(altered), *original[2:])):
            with self.subTest(pin=documents[1], provenance_bytes=len(documents[2])):
                with self.assertRaises(ValueError):
                    self.declaration(documents)

    def test_inventory_rejects_incomplete_parent_maps_and_case_aliases(self):
        def missing_parent(value):
            value['directories'] = []

        def missing_empty_parent(value):
            value['directories'] = ['bin', 'empty/child']

        def case_alias(value):
            value['files']['BIN/other.exe'] = copy.deepcopy(value['files']['bin/tool.exe'])

        for change in (missing_parent, missing_empty_parent, case_alias):
            with self.subTest(change=change.__name__):
                with self.assertRaises(ValueError):
                    self.declaration(inventory_documents('native_dependencies', change_inventory=change))

    def test_inventory_rejects_duplicate_json_and_forged_provenance(self):
        original = inventory_documents('native_dependencies')
        duplicate = original[0].replace(b'"schema_version": 1',
                                        b'"schema_version": 1, "schema_version": 1')
        with self.assertRaisesRegex(ValueError, 'Duplicate inventory JSON'):
            self.declaration((duplicate, digest(duplicate), *original[2:]))
        changes = (
            {'change_inventory': lambda value: value.update(schema_version=True)},
            {'change_provenance': lambda value: value.update(notices=[])},
            {'change_provenance': lambda value: value['notices'].append(
                reference('C:/original/source.json', 'contradictory pin'))},
            {'change_inventory': lambda value: value.update(native_authority=True)})
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.declaration(inventory_documents('native_dependencies', **change))

    def test_h1_and_h2_validate_canonical_declared_identities_and_owned_results(self):
        for version, module in ((1, self.h1), (2, self.h2)):
            with self.subTest(version=version):
                declared = identity(version)
                raw = encoded(declared)
                result = module.validate_toolchain_identity(raw, digest(raw), declared)
                self.assertEqual(result, declared)
                result['programs']['compiler']['version'] = '999.0.0'
                self.assertEqual(declared['programs']['compiler']['version'], '19.1.7')
                with self.assertRaises(ValueError):
                    module.validate_toolchain_identity(raw, digest(b'unrelated bytes'), declared)
                noncanonical = json.dumps(declared).encode('ascii')
                with self.assertRaises(ValueError):
                    module.validate_toolchain_identity(noncanonical, digest(noncanonical), declared)

    def test_h1_and_h2_keep_schema_tags_types_and_authority_fields_closed(self):
        for version, module in ((1, self.h1), (2, self.h2)):
            for updates in ({'schema_version': True}, {'schema_version': 3 - version},
                            {'kind': 'foundation-native-engine-windows-toolchain-identity-v' + str(3 - version)},
                            {'native_authority': {'admitted': True}}):
                with self.subTest(version=version, updates=updates):
                    declared = identity(version)
                    declared.update(updates)
                    with self.assertRaises(ValueError):
                        module.toolchain_identity(declared)

    def test_h2_requires_both_additional_frontends_in_the_host_inventory(self):
        for role in ('nmake', 'msbuild'):
            for mode in ('missing', 'outside', 'basename'):
                with self.subTest(role=role, mode=mode):
                    declared = identity(2)
                    if mode == 'missing':
                        del declared['programs'][role]
                    else:
                        declared['programs'][role]['path'] = (
                            'C:/unretained/' + declared['programs'][role]['path'].rsplit('/', 1)[1]
                            if mode == 'outside' else 'C:/host/bin/other.exe')
                    with self.assertRaises(ValueError):
                        self.h2.toolchain_identity(declared)

    def test_probe_plans_use_h2_compiler_and_reject_protected_output_overlap(self):
        declared = identity(2)
        raw = encoded(declared)
        limits = {'wall_milliseconds': 1000, 'maximum_processes': 4,
                  'maximum_output_bytes': 1024, 'maximum_log_bytes': 1024}
        plans = []
        for filename in ('probe_w2.py', 'probe_d3.py'):
            module = load_source(SUPPORT / filename)
            plan = module.plan(raw, digest(raw), 'C:/maintained/probe.cpp', 'C:/work', limits)
            plans.append(plan)
            self.assertEqual(plan['schema_version'], 2)
            self.assertEqual(plan['command']['program'], declared['programs']['compiler'])
            self.assertEqual(plan['command']['argv'][0], 'C:/llvm/bin/clang-cl.exe')
            self.assertIn('/MT', plan['command']['argv'])
            self.assertEqual(plan['command']['environment']['SystemRoot'], 'C:/Windows')
            self.assertEqual(plan['object_path'], 'C:/work/probe/static-closure-probe.obj')
            plan['limits']['maximum_processes'] = 8
            self.assertEqual(limits['maximum_processes'], 4)
            for workspace in ('C:/LLVM/work', 'C:/Windows/work', 'C:/maintained/probe.cpp'):
                with self.subTest(module=filename, workspace=workspace):
                    with self.assertRaises(ValueError):
                        module.plan(raw, digest(raw), 'C:/maintained/probe.cpp', workspace, limits)
        self.assertEqual(plans[0], plans[1])

    def test_lazy_loader_dag_is_exact_and_module_relative(self):
        h1_path = TOOLS / 'appended_engine_windows_dependency_proof.py'
        cases = (
            ('proof_h2.py', lambda module: module.encoded({}), [h1_path]),
            ('proof_d3.py', lambda module: module.encoded({}),
             [SUPPORT / 'proof_h2.py', h1_path]),
            ('probe_w2.py', lambda module: (module._h2().encoded({}), module.encoded({})),
             [SUPPORT / 'proof_h2.py', h1_path, SUPPORT / 'probe_core.py']),
            ('probe_d3.py', lambda module: (module._w2()._h2().legacy().encoded({}), module.encoded({})),
             [SUPPORT / 'probe_w2.py', SUPPORT / 'proof_d3.py',
              SUPPORT / 'proof_h2.py', h1_path, SUPPORT / 'probe_core.py']))
        original_open = Path.open
        for filename, operation, expected in cases:
            module = load_source(SUPPORT / filename)
            opened = []

            def record_open(path, *args, **kwargs):
                opened.append(path.resolve())
                return original_open(path, *args, **kwargs)

            with self.subTest(module=filename), mock.patch.object(Path, 'open', record_open):
                operation(module)
                self.assertEqual(opened, [path.resolve() for path in expected])
                operation(module)
                self.assertEqual(opened, [path.resolve() for path in expected])

    def test_lazy_loaders_reject_changed_dependency_bytes_before_execution(self):
        cases = (
            ('inventory.py', '_parser', SUPPORT / 'inventory_contract.py'),
            ('proof_h2.py', 'legacy', TOOLS / 'appended_engine_windows_dependency_proof.py'),
            ('proof_d3.py', '_d2', SUPPORT / 'proof_h2.py'),
            ('probe_w2.py', '_h2', SUPPORT / 'proof_h2.py'),
            ('probe_w2.py', '_w1', SUPPORT / 'probe_core.py'),
            ('probe_d3.py', '_d3', SUPPORT / 'proof_d3.py'),
            ('probe_d3.py', '_w2', SUPPORT / 'probe_w2.py'))
        original_open = Path.open
        for filename, loader, dependency in cases:
            original = dependency.read_bytes()
            for changed in (original + b'\n', b'#' + original[1:]):
                module = load_source(SUPPORT / filename)

                def substitute(path, *args, **kwargs):
                    if path.resolve() == dependency.resolve():
                        return io.BytesIO(changed)
                    return original_open(path, *args, **kwargs)

                with self.subTest(module=filename, loader=loader, bytes=len(changed)):
                    with mock.patch.object(Path, 'open', substitute):
                        with mock.patch('builtins.compile', side_effect=AssertionError('Tampered source compiled')):
                            with self.assertRaisesRegex(ValueError, 'Frozen .*source differs'):
                                getattr(module, loader)()

    def test_d2_d3_dispatch_preserves_original_bytes_and_rejects_mixed_tags(self):
        module = load_source(SUPPORT / 'probe_d3.py')
        d3 = module._d3()
        d2 = d3._d2()
        expected, declared = {'untrusted': 'expectation declaration'}, identity(2)
        for version, kind, selected in ((2, d2.RECEIPT_KIND, d2), (3, d3.RECEIPT_KIND, d3)):
            raw = encoded({'schema_version': version, 'kind': kind})
            marker = object()
            with self.subTest(version=version):
                with mock.patch.object(selected, 'validate_dependency_receipt', return_value=marker) as validate:
                    self.assertIs(module._dependency(raw, digest(raw), expected, declared), marker)
                    validate.assert_called_once_with(raw, digest(raw), expected, declared)
        for version, kind in ((1, self.h1.RECEIPT_KIND), (2, d3.RECEIPT_KIND),
                              (3, d2.RECEIPT_KIND), (True, d2.RECEIPT_KIND)):
            raw = encoded({'schema_version': version, 'kind': kind})
            with self.subTest(version=version, kind=kind):
                with self.assertRaisesRegex(ValueError, 'schema/kind'):
                    module._dependency(raw, digest(raw), expected, declared)

    def test_d3_public_validator_rejects_schema_mixing_and_forged_authority(self):
        expected = {name: None for name in self.d3.EXPECTED_FIELDS}
        receipt = {name: None for name in ('schema_version', 'kind', 'target', 'scope',
            'bindings', 'commands', 'prefix', 'libraries', 'postflight', 'probe', 'facts')}
        receipt.update(schema_version=3, kind=self.d3.RECEIPT_KIND,
                       target=identity(2)['target'], scope='unqualified-dependency-candidate')
        for updates in ({'schema_version': 2}, {'schema_version': True},
                        {'kind': 'foundation-native-engine-windows-dependencies-build-v2'},
                        {'native_authority': {'admitted': True}}):
            supplied = {**receipt, **updates}
            raw = encoded(supplied)
            with self.subTest(updates=updates):
                with self.assertRaisesRegex(ValueError, 'D3 schema_version|D3 kind|D3 receipt fields'):
                    self.d3.validate_dependency_receipt(raw, digest(raw), expected, identity(2))

    def test_pure_probe_helpers_keep_original_native_constructor_unavailable(self):
        for filename in ('probe_w2.py', 'probe_d3.py'):
            module = load_source(SUPPORT / filename)
            with self.subTest(module=filename):
                with self.assertRaises(module.MissingSource) as raised:
                    module.require_native_constructor()
                self.assertEqual(str(raised.exception), module.MISSING_CONSTRUCTOR)

    def cmake(self):
        with mock.patch.dict(sys.modules, {'appended_engine_windows_dependency_proof': self.h1}):
            return load_source(SUPPORT / 'cmake_version.py')

    def test_cmake_version_is_derived_from_complete_capabilities_bytes(self):
        module = self.cmake()
        self.assertEqual(module.extract_observed_version('cmake', module.METHOD,
                                                        encoded(capabilities())), '3.31.6')
        without_optional = capabilities()
        del without_optional['fileApi']
        self.assertEqual(module.extract_observed_version('cmake', module.METHOD,
                                                        encoded(without_optional)), '3.31.6')
        with self.assertRaises(module.MissingMethod):
            module.extract_observed_version('ninja', module.METHOD, encoded(capabilities()))

    def test_cmake_version_rejects_partial_ambiguous_and_unreviewed_output(self):
        module = self.cmake()
        valid = encoded(capabilities())
        candidates = [b'log prefix\n' + valid, valid + b'log suffix\n', b'\xef\xbb\xbf' + valid,
                      valid.replace(b'"patch": 6', b'"patch": 6, "patch": 6')]
        for updates in ({'minor': 32}, {'patch': True}, {'patch': 6.0},
                        {'string': '3.31.7'}, {'suffix': '-rc1'}, {'isDirty': True}):
            value = capabilities()
            value['version'].update(updates)
            candidates.append(encoded(value))
        for index, raw in enumerate(candidates):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    module.extract_observed_version('cmake', module.METHOD, raw)


if __name__ == '__main__':
    unittest.main()
