"""Pure closed data fixtures: no subprocess, source/SDK/tool/archive body access."""

import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_dependency_proof as proof


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def reference(path):
    return {'path': path, 'sha256': digest(path)}


def program(path, version='1.2.3'):
    return {**reference(path), 'version': version}


def identity():
    roots = {name: 'C:/retained/' + name for name in proof.INVENTORIES}
    versions = {'llvm': '19.1.7', 'msvc_stl': '14.44.35207',
                'windows_sdk': '10.0.22621.0', 'host_generators': 'fixture-v1'}
    value = {'schema_version': 1, 'kind': proof.IDENTITY_KIND,
        'target': copy.deepcopy(proof.TARGET), 'policy': copy.deepcopy(proof.POLICY),
        'inventories': {name: {'root': root, 'version': versions[name],
            'subject_sha256': digest(name)} for name, root in roots.items()},
        'programs': {role: program(roots['llvm' if role in proof.LLVM_PROGRAMS else
            'host_generators'] + '/bin/' + basename,
            '19.1.7' if role in proof.LLVM_PROGRAMS else '3.13.2')
            for role, basename in proof.PROGRAM_NAMES.items()},
        'builtins': reference(roots['llvm'] + '/lib/clang_rt.builtins-x86_64.lib'),
        'crt_libraries': {name: reference(roots['windows_sdk' if name == 'libucrt' else
            'msvc_stl'] + '/lib/' + name + '.lib') for name in proof.CRT_LIBRARIES},
        'include_directories': [roots['msvc_stl'] + '/include', roots['windows_sdk'] + '/include'],
        'library_directories': [roots['msvc_stl'] + '/lib', roots['windows_sdk'] + '/lib'],
        'system_root': 'C:/Windows'}
    return value


def command(supplier, stage):
    selected = program('C:/retained/host_generators/bin/cmake.exe', '3.31.6')
    command_id = ('closure' if supplier == '__closure__' else supplier) + '-' + stage
    return {'id': command_id, 'supplier': supplier, 'stage': stage,
        'program': selected, 'argv': [selected['path'], '--build', 'C:/work/' + command_id],
        'cwd': 'C:/work/' + command_id,
        'environment': {'PATH': 'C:/retained/host_generators/bin;C:/retained/llvm/bin',
                        'SystemRoot': 'C:/Windows'},
        'initial_cache': reference('C:/work/cache/' + command_id + '.cmake'),
        'response_files': [], 'log_policy': 'stdout-stderr-combined'}


def observation(declaration):
    return {**copy.deepcopy(declaration),
        'logs': {'combined': reference('C:/work/logs/' + declaration['id'] + '.log')},
        'output_subject_sha256': digest('output-' + declaration['id']),
        'job': {'owner': 'windows-job-v1',
            'launch_intent_sha256': hashlib.sha256(proof.encoded(declaration)).hexdigest(),
            'image': {k: declaration['program'][k] for k in ('path', 'sha256')},
            'launch_suspended': True, 'assigned_before_resume': True,
            'breakaway_allowed': False, 'kill_on_close': True, 'exit_code': 0,
            'elapsed_milliseconds': 10, 'wall_limit_milliseconds': 1000,
            'process_count': 2, 'process_limit': 16,
            'peak_output_bytes': 128, 'output_limit_bytes': 4096,
            'active_processes_at_join': 0, 'streams_closed': True,
            'join_completed': True, 'owner_closed': True}}


def receipts():
    h = identity()
    bindings = {'selection': reference('C:/records/selection.json'),
        'plan': reference('C:/records/plan.json'),
        'producer': {'controller': reference('C:/source/tools/controller.py'),
            'recipe': reference('C:/source/recipe/profile.json'),
            'source_review': reference('C:/source/recipe/source-review.json'),
            'helpers': [reference('C:/source/tools/proof.py')],
            'templates': [reference('C:/source/recipe/cache.in')]},
        'toolchain_identity_sha256': hashlib.sha256(proof.encoded(h)).hexdigest(),
        'sources': {name: {'version': '1.2.3',
            'archive': {**reference('C:/archives/' + name + '.tar.gz'),
                'bytes': 1234, 'format': 'tar-gzip', 'strip_prefix': name + '-1.2.3'},
            'replay': reference('C:/records/' + name + '-replay.json'),
            'source_subject_sha256': digest('source-' + name),
            'notice_subject_sha256': digest('notice-' + name)} for name in proof.SOURCES},
        'controller': {'program': copy.deepcopy(h['programs']['python']),
            'runtime_subject_sha256': digest('python-runtime'), 'machine': 'AMD64',
            'pointer_bits': 64}}
    commands = [command(name, stage) for name in proof.SOURCES
                for stage in ('configure', 'build', 'install')]
    commands.append(command('__closure__', 'probe'))
    prefix = {'root': 'C:/output/prefix', 'inventory_subject_sha256': digest('prefix'),
              'header_data_subject_sha256': digest('header-data'),
              'notice_subject_sha256': digest('prefix-notices')}
    libraries = {}
    for target, supplier in proof.LIBRARY_SUPPLIERS.items():
        links = ['WebP::sharpyuv'] if target == 'WebP::libwebp' else (
                ['WebP::libwebp'] if target == 'WebP::demux' else ['ws2_32'])
        libraries[target] = {**reference(prefix['root'] + '/lib/' + target.replace('::', '_') + '.lib'),
            'includes': [prefix['root'] + '/include'], 'definitions': ['STATIC_BUILD=1'],
            'links': links, 'supplier': supplier,
            'source_subject_sha256': bindings['sources'][supplier]['source_subject_sha256'],
            'build_instance': supplier + '-build-v1'}
    probe_value = {'command_id': commands[-1]['id'],
        'library_targets': sorted(proof.LIBRARY_SUPPLIERS),
        'link_inputs': [{k: libraries[target][k] for k in ('path', 'sha256')}
                       for target in sorted(libraries)],
        'output': reference('C:/work/probe/static-closure.exe')}
    expected = {'bindings': bindings, 'commands': commands, 'prefix': prefix,
                'libraries': libraries, 'probe': probe_value}
    value = {'schema_version': 1, 'kind': proof.RECEIPT_KIND,
        'target': copy.deepcopy(proof.TARGET), 'scope': proof.SCOPE,
        'bindings': copy.deepcopy(bindings), 'commands': [observation(item) for item in commands],
        'prefix': copy.deepcopy(prefix), 'libraries': copy.deepcopy(libraries),
        'postflight': {'toolchain_identity_sha256': bindings['toolchain_identity_sha256'],
            'sources': {name: bindings['sources'][name]['source_subject_sha256'] for name in proof.SOURCES}},
        'probe': copy.deepcopy(probe_value), 'facts': {name: False for name in proof.FALSE_FACTS}}
    for item in value['libraries'].values():
        item['inspection'] = {'archive_sha256': item['sha256'], 'format': 'coff-static',
            'machine': 'AMD64', 'member_count': 5, 'import_objects': 0, 'foreign_objects': 0,
            'dynamic_crt_directives': 0, 'debug_crt_directives': 0, 'lto_objects': 0}
    return value, expected


class ToolchainIdentityTests(unittest.TestCase):
    def setUp(self):
        self.value = identity()

    def reject(self, value=None):
        with self.assertRaises(ValueError):
            proof.toolchain_identity(self.value if value is None else value)

    def test_complete_identity_is_owned_canonical_and_source_only(self):
        checked = proof.toolchain_identity(self.value)
        self.assertEqual(checked, self.value)
        self.assertIsNot(checked, self.value)
        checked['programs']['compiler']['version'] = '20.1.7'
        self.assertEqual(self.value['programs']['compiler']['version'], '19.1.7')
        raw = proof.encoded(self.value)
        pin = hashlib.sha256(raw).hexdigest()
        self.assertEqual(proof.validate_toolchain_identity(raw, pin), self.value)
        self.assertEqual(proof.validate_toolchain_identity(raw, pin, identity()), self.value)
        self.assertEqual(raw, (json.dumps(self.value, indent=2, sort_keys=True,
                                        ensure_ascii=True) + '\n').encode('ascii'))
        self.assertNotIn('production_eligible', checked)

    def test_identity_reconstruction_and_original_independent_pin(self):
        raw = proof.encoded(self.value)
        for pin in ('0' * 64, 'A' * 64, '1' * 64, None, True):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                proof.validate_toolchain_identity(raw, pin)
        changed = identity(); changed['system_root'] = 'C:/OtherWindows'
        with self.assertRaisesRegex(ValueError, 'reconstruction'):
            proof.validate_toolchain_identity(raw, hashlib.sha256(raw).hexdigest(), changed)

    def test_exact_fields_reject_cycles_and_self_digest(self):
        for path in ((), ('policy',), ('inventories',), ('inventories', 'llvm'),
                     ('programs',), ('programs', 'compiler'), ('builtins',), ('crt_libraries',)):
            value = identity(); selected = value
            for key in path:
                selected = selected[key]
            selected['unexpected'] = 'back-reference'
            with self.subTest(path=path):
                self.reject(value)
        for name in ('provenance', 'native_inputs', 'dependency_subject', 'sha256', 'receipt'):
            value = identity(); value[name] = digest(name); self.reject(value)

    def test_schema_target_and_policy_use_exact_scalar_types(self):
        changes = [(('schema_version',), True), (('target', 'pointer_bits'), 64.0),
            (('target', 'system'), 'Linux'), (('policy', 'engine_cxx_standard'), True),
            (('policy', 'lto'), 0), (('policy', 'crt'), 'dynamic-md'),
            (('policy', 'build_type'), 'Debug'), (('policy', 'cpu_baseline'), 'avx2'),
            (('policy', 'os_floor_declaration'), 'windows-10-1809-qualified')]
        for path, replacement in changes:
            value = identity(); selected = value
            for key in path[:-1]: selected = selected[key]
            selected[path[-1]] = replacement
            with self.subTest(path=path): self.reject(value)

    def test_llvm_versions_are_exact_common_and_meet_floor(self):
        for release in ('19.1.6', '18.1.8', '19.1', '19.1.7-dev', '019.1.7'):
            value = identity(); value['inventories']['llvm']['version'] = release
            for role in proof.LLVM_PROGRAMS: value['programs'][role]['version'] = release
            with self.subTest(release=release): self.reject(value)
        self.value['programs']['linker']['version'] = '19.1.8'; self.reject()
        value = identity(); value['inventories']['llvm']['version'] = '20.1.0'
        for role in proof.LLVM_PROGRAMS: value['programs'][role]['version'] = '20.1.0'
        self.assertEqual(proof.toolchain_identity(value), value)

    def test_msvc_sdk_patch_versions_and_generator_versions_are_declared_exactly(self):
        for role, versions in (('msvc_stl', ('v143', '14.44', '15.44.1')),
                               ('windows_sdk', ('10.0', '10.0.22621', '11.0.22621.0'))):
            for version in versions:
                value = identity(); value['inventories'][role]['version'] = version
                with self.subTest(role=role, version=version): self.reject(value)
        self.value['programs']['python']['version'] = 'unknown'; self.reject()

    def test_program_builtin_crt_roles_are_owned_by_exact_inventory(self):
        for role, path in (('compiler', 'C:/retained/llvm/bin/cl.exe'),
                           ('linker', 'C:/retained/host_generators/bin/lld-link.exe'),
                           ('python', 'C:/retained/llvm/bin/python.exe')):
            value = identity(); value['programs'][role]['path'] = path
            with self.subTest(role=role): self.reject(value)
        self.value['builtins']['path'] = 'C:/retained/llvm/lib/builtins.a'; self.reject()
        value = identity(); value['crt_libraries']['libcmt']['path'] = 'C:/retained/windows_sdk/lib/libcmt.lib'
        self.reject(value)

    def test_inventory_roots_are_disjoint_and_systemroot_is_native_os(self):
        for root in ('C:/retained/llvm', 'C:/retained/llvm/subroot', 'C:/retained/LLVM'):
            value = identity(); value['inventories']['msvc_stl']['root'] = root
            with self.subTest(root=root): self.reject(value)
        self.assertEqual(proof.toolchain_identity(self.value)['system_root'], 'C:/Windows')
        self.value['system_root'] = 'C:/retained/windows_sdk'; self.reject()

    def test_paths_reject_windows_aliases_and_unicode_decomposition(self):
        paths = ('c:/retained/llvm', 'C:/', 'C:relative', '/tmp/path', '//server/share',
            'C:/retained//llvm', 'C:/retained/../llvm', 'C:/retained/./llvm',
            'C:/retained/llvm/', 'C:\\retained\\llvm', 'C:/NUL.lib',
            'C:/COM¹/file', 'C:/NUL .lib', 'C:/COM1 .log',
            'C:/retained/file:ads', 'C:/retained/trailing.',
            'C:/retained/trailing ', 'C:/retained/a;b', 'C:/retained/$<CONFIG>',
            'C:/retained/@token@', 'C:/PROGRA~1/tools', 'C:/retained/e\u0301', 'C:/retained/\ud800',
            'C:/retained/München', 'C:/retained/ı.lib')
        for path in paths:
            with self.subTest(path=repr(path)), self.assertRaises(ValueError):
                proof.windows_path(path)
        self.assertEqual(proof.parse_document(proof.encoded({'notice': 'München'})),
                         {'notice': 'München'})

    def test_implicit_case_spelling_and_file_directory_conflicts(self):
        self.value['library_directories'][0] = 'C:/Retained/msvc_stl/lib'; self.reject()
        value = identity(); value['include_directories'][0] = value['programs']['compiler']['path']
        self.reject(value)
        value = identity(); value['include_directories'][0] = 'C:/retained/host_generators/include'
        self.reject(value)
        value = identity(); value['library_directories'].append(value['library_directories'][0])
        self.reject(value)

    def test_original_json_rejects_duplicates_nonfinite_noncanonical_and_bounds(self):
        raw = proof.encoded(self.value)
        variants = [raw[:-1], raw + b' ', b'{"a":1,"a":2}\n', b'{"a":NaN}\n',
                    b'{"a":Infinity}\n', b'{"a":"\\ud800"}\n',
                    b'\xef\xbb\xbf' + raw, b'[]' * (proof.MAX_DOCUMENT // 2 + 1)]
        for raw_value in variants:
            with self.subTest(prefix=raw_value[:30]), self.assertRaises(ValueError):
                proof.validate_toolchain_identity(raw_value, digest('pin'))
        for value in (float('nan'), float('inf'), {'x': 'a' * 4097}, {'x': 2**64}):
            with self.assertRaises(ValueError): proof.encoded(value)
        nested = []
        for _ in range(34): nested = [nested]
        with self.assertRaises(ValueError): proof.encoded(nested)

    def test_encoded_bound_is_enforced_before_full_json_allocation(self):
        oversized = {'notice': ['😀' * 4096] * 100}
        with mock.patch.object(proof.json, 'dumps', side_effect=AssertionError('premature JSON allocation')):
            with self.assertRaisesRegex(ValueError, 'pre-serialization'):
                proof.encoded(oversized)


class DependencyReceiptTests(unittest.TestCase):
    def setUp(self):
        self.value, self.expected = receipts()

    def reject(self, value=None, expected=None):
        with self.assertRaises(ValueError):
            proof.validate_receipt(self.value if value is None else value,
                                   self.expected if expected is None else expected)

    def test_complete_receipt_is_owned_and_only_unqualified_source_consistency(self):
        checked = proof.validate_receipt(self.value, self.expected)
        self.assertEqual(checked, self.value)
        self.assertIsNot(checked, self.value)
        checked['prefix']['root'] = 'C:/changed'
        self.assertEqual(self.value['prefix']['root'], 'C:/output/prefix')
        self.assertEqual(self.value['facts'], {name: False for name in proof.FALSE_FACTS})
        self.assertEqual(proof.parse_document(proof.encoded(self.value)), self.value)

    def test_original_arbitrary_report_and_passed_flags_do_not_match_closed_receipt(self):
        for value in ({'passed': True}, {'original_reports': ['arbitrary']}, 'passed', True):
            self.reject(value)
        self.value['passed'] = True; self.reject()

    def test_receipt_schema_target_scope_and_false_facts_are_exact(self):
        for name, replacement in (('schema_version', True), ('kind', 'other'),
                                  ('scope', 'qualified-candidate')):
            value = copy.deepcopy(self.value); value[name] = replacement; self.reject(value)
        for name in proof.FALSE_FACTS:
            for replacement in (True, 0, 'false'):
                value = copy.deepcopy(self.value); value['facts'][name] = replacement
                with self.subTest(name=name, replacement=replacement): self.reject(value)

    def test_expectations_cannot_omit_closed_fields_or_copy_observation_shapes(self):
        for name in self.expected:
            expected = copy.deepcopy(self.expected); del expected[name]; self.reject(expected=expected)
        self.expected['commands'][0]['job'] = self.value['commands'][0]['job']; self.reject()

    def test_original_bindings_and_sources_match_independent_expected_declarations(self):
        for field in ('selection', 'plan'):
            value = copy.deepcopy(self.value); value['bindings'][field]['sha256'] = digest('changed')
            self.reject(value)
        for name, replacement in (('version', '2.0.0'), ('source_subject_sha256', digest('changed'))):
            value = copy.deepcopy(self.value); value['bindings']['sources']['icu'][name] = replacement
            self.reject(value)
        for name in ('sha256', 'bytes', 'format', 'strip_prefix'):
            value = copy.deepcopy(self.value)
            value['bindings']['sources']['icu']['archive'][name] = {
                'sha256': digest('other'), 'bytes': 1235, 'format': 'zip', 'strip_prefix': 'other'}[name]
            with self.subTest(name=name): self.reject(value)

    def test_thirteen_source_set_rejects_unknown_alias_and_invalid_format_prefix(self):
        for mutation in ('missing', 'extra', 'same-archive', 'bad-prefix', 'raw-format'):
            expected = copy.deepcopy(self.expected); sources = expected['bindings']['sources']
            if mutation == 'missing': del sources['icu']
            elif mutation == 'extra': sources['woff2'] = copy.deepcopy(sources['icu'])
            elif mutation == 'same-archive': sources['zlib']['archive'] = copy.deepcopy(sources['icu']['archive'])
            elif mutation == 'bad-prefix': sources['icu']['archive']['strip_prefix'] = '../icu'
            else: sources['icu']['archive']['format'] = 'raw'
            with self.subTest(mutation=mutation): self.reject(expected=expected)

    def test_controller_python_runtime_architecture_are_bound(self):
        for name, replacement in (('pointer_bits', True), ('machine', 'ARM64'),
                                  ('runtime_subject_sha256', '0' * 64)):
            expected = copy.deepcopy(self.expected); expected['bindings']['controller'][name] = replacement
            self.reject(expected=expected)
        self.expected['bindings']['controller']['program']['path'] = 'C:/other/pypy.exe'; self.reject()

    def test_every_literal_command_field_binds_original_semantics(self):
        replacements = {'id': 'changed-id', 'supplier': 'zlib', 'stage': 'build',
            'program': program('C:/other/cmake.exe'), 'argv': ['C:/other/cmake.exe'],
            'cwd': 'C:/other/work', 'environment': {'PATH': 'C:/other', 'SystemRoot': 'C:/Windows'},
            'initial_cache': reference('C:/changed/cache.cmake'), 'response_files': [],
            'log_policy': 'separate'}
        for name, replacement in replacements.items():
            value = copy.deepcopy(self.value); value['commands'][0][name] = replacement
            if name == 'response_files': value['commands'][0][name] = [reference('C:/changed/flags.rsp')]
            with self.subTest(name=name): self.reject(value)

    def test_stages_are_complete_ordered_and_final_probe_is_unique(self):
        for mutation in ('missing', 'reordered', 'duplicate-id', 'probe-first', 'extra-stage'):
            expected = copy.deepcopy(self.expected); commands = expected['commands']
            if mutation == 'missing': commands.pop(0)
            elif mutation == 'reordered': commands[0], commands[1] = commands[1], commands[0]
            elif mutation == 'duplicate-id': commands[1]['id'] = commands[0]['id']
            elif mutation == 'probe-first': commands.insert(0, commands.pop())
            else: commands[0]['stage'] = 'fetch'
            with self.subTest(mutation=mutation): self.reject(expected=expected)

    def test_ambient_environment_dynamic_debug_crt_cpu_and_lto_are_rejected(self):
        for name in ('CL', '_CL_', 'LINK', '_LINK_', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS'):
            expected = copy.deepcopy(self.expected); expected['commands'][0]['environment'][name] = '/MT'
            self.reject(expected=expected)
        for argument in ('/MD', '/MDd', '/MTd', '/GL', '/LTCG', '/arch:AVX2',
                         '-flto', '-mavx2', '-march=native', '/clang:-flto', '/clang:-mavx',
                         '-mcpu=native', '/clang:-msse4.2', '-mfma',
                         '-DCMAKE_CXX_FLAGS="/MD"',
                         '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL',
                         '-DCMAKE_INTERPROCEDURAL_OPTIMIZATION:BOOL=ON'):
            expected = copy.deepcopy(self.expected); expected['commands'][0]['argv'].append(argument)
            with self.subTest(argument=argument): self.reject(expected=expected)
        expected = copy.deepcopy(self.expected)
        expected['commands'][0]['environment']['Path'] = 'C:/other'; self.reject(expected=expected)

    def test_response_files_must_match_exact_ordered_literal_argv(self):
        expected = copy.deepcopy(self.expected)
        response = reference('C:/work/response/compile.rsp')
        expected['commands'][0]['response_files'] = [response]
        self.reject(expected=expected)
        expected['commands'][0]['argv'].append('@' + response['path'])
        value = copy.deepcopy(self.value); value['commands'][0] = observation(expected['commands'][0])
        self.assertEqual(proof.validate_receipt(value, expected), value)
        value['commands'][0]['response_files'][0]['sha256'] = digest('changed'); self.reject(value, expected)

    def test_global_and_config_specific_cmake_ipo_accept_only_explicit_false_values(self):
        variables = ('CMAKE_INTERPROCEDURAL_OPTIMIZATION',
                     'CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE',
                     'CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE_ASAN:BOOL',
                     'CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE:STRING',
                     'CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE.ASAN:BOOL',
                     'CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE+ASAN',
                     'CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE?CUSTOM:UNKNOWN.TYPE')
        for variable in variables:
            for enabled in ('ON', 'YES', 'Y', 'TRUE', '1', '2', '-1', 'UNKNOWN', '', 'OFF;ON', 'OFF extra'):
                with self.subTest(variable=variable, enabled=enabled), self.assertRaisesRegex(ValueError, 'IPO'):
                    proof._safe_argument('-D' + variable + '=' + enabled)
            for disabled in ('OFF', 'NO', 'FALSE', '0', 'IGNORE', 'NOTFOUND'):
                with self.subTest(variable=variable, disabled=disabled):
                    proof._safe_argument('-D' + variable.lower() + '=' + disabled.lower())
        expected = copy.deepcopy(self.expected)
        expected['commands'][0]['argv'].append('-DCMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE:BOOL=2')
        self.reject(expected=expected)

    def test_cpu_feature_and_architecture_routes_require_explicit_baseline_safe_flags(self):
        for argument in ('-mrdrnd', '-mrdseed', '-madx', '/clang:-mrdrnd',
                         '-munknown', '-mtune=native', '-mno-unknown',
                         '-target-cpu', '-target-cpu=skylake', '-target-feature=+rdrnd',
                         '/clang:-target-feature', '-DCMAKE_CXX_FLAGS=-target-cpu skylake',
                         '-DCMAKE_C_FLAGS="-madx"', '/arch:UNKNOWN', '/arch:AVX512'):
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                proof._safe_argument(argument)
        for argument in ('-msse2', '-m64', '/arch:SSE2', '/clang:-msse2',
                         '-mno-avx', '-mno-rdrnd', '-mno-rdseed', '-mno-adx',
                         '-DCMAKE_CXX_FLAGS="-msse2 -mno-avx2"'):
            with self.subTest(argument=argument): proof._safe_argument(argument)

    def test_job_requires_structured_image_intent_and_descendant_closure(self):
        replacements = {'owner': 'passed', 'launch_intent_sha256': digest('other'),
            'image': reference('C:/other/cmake.exe'), 'launch_suspended': False,
            'assigned_before_resume': False, 'breakaway_allowed': True, 'kill_on_close': False,
            'exit_code': 1, 'active_processes_at_join': 1, 'streams_closed': False,
            'join_completed': False, 'owner_closed': False}
        for name, replacement in replacements.items():
            value = copy.deepcopy(self.value); value['commands'][0]['job'][name] = replacement
            with self.subTest(name=name): self.reject(value)
        value = copy.deepcopy(self.value); value['commands'][0]['job'] = {'process_tree_closed': True}
        self.reject(value)

    def test_sampled_job_resource_observations_are_bounded_exact_integers(self):
        for name, replacement in (('elapsed_milliseconds', 1001), ('process_count', 17),
                                  ('peak_output_bytes', 4097), ('exit_code', False),
                                  ('active_processes_at_join', False), ('process_limit', True),
                                  ('wall_limit_milliseconds', 0)):
            value = copy.deepcopy(self.value); value['commands'][0]['job'][name] = replacement
            with self.subTest(name=name): self.reject(value)

    def test_wall_deadline_is_strict_but_process_and_output_limits_are_inclusive(self):
        value = copy.deepcopy(self.value); job = value['commands'][0]['job']
        job['elapsed_milliseconds'] = job['wall_limit_milliseconds']; self.reject(value)
        job['elapsed_milliseconds'] -= 1
        job['process_count'] = job['process_limit']
        job['peak_output_bytes'] = job['output_limit_bytes']
        self.assertEqual(proof.validate_receipt(value, self.expected), value)

    def test_logs_require_closed_pinned_unique_combined_originals(self):
        for logs in ({'combined': {'path': 'C:/log/file', 'sha256': '0' * 64}},
                     {'stdout': reference('C:/logs/out'), 'stderr': reference('C:/logs/err')},
                     {'passed': True}):
            value = copy.deepcopy(self.value); value['commands'][0]['logs'] = logs; self.reject(value)
        value = copy.deepcopy(self.value); value['commands'][1]['logs'] = copy.deepcopy(value['commands'][0]['logs'])
        self.reject(value)
        self.value['commands'][0]['logs']['combined'] = copy.deepcopy(self.value['bindings']['selection']); self.reject()

    def test_prefix_subjects_avoid_provenance_full_inventory_cycles(self):
        for name in ('provenance', 'full_inventory_sha256', 'native_inputs_sha256', 'receipt_sha256'):
            value = copy.deepcopy(self.value); value['prefix'][name] = digest(name); self.reject(value)
        self.value['prefix']['inventory_subject_sha256'] = digest('moved'); self.reject()

    def test_library_map_source_build_instance_and_output_pins_bind(self):
        for name, replacement in (('supplier', 'icu'), ('source_subject_sha256', digest('other')),
                                  ('build_instance', 'other-build'), ('sha256', digest('other')),
                                  ('links', []), ('definitions', ['DIFFERENT=1'])):
            value = copy.deepcopy(self.value); value['libraries']['WebP::libwebp'][name] = replacement
            with self.subTest(name=name): self.reject(value)
        for target in ('WOFF2::dec', 'Fontconfig::Fontconfig'):
            value = copy.deepcopy(self.value); value['libraries'][target] = copy.deepcopy(value['libraries']['PNG::PNG'])
            self.reject(value)
        value = copy.deepcopy(self.value); del value['libraries']['ICU::data']; self.reject(value)

    def test_library_archive_inspections_reject_foreign_import_dynamic_debug_lto(self):
        for name, replacement in (('archive_sha256', digest('other')), ('format', 'elf'),
                                  ('machine', 'ARM64'), ('member_count', 0),
                                  ('import_objects', 1), ('foreign_objects', 1),
                                  ('dynamic_crt_directives', 1), ('debug_crt_directives', 1),
                                  ('lto_objects', 1)):
            value = copy.deepcopy(self.value); value['libraries']['ICU::data']['inspection'][name] = replacement
            with self.subTest(name=name): self.reject(value)
        value = copy.deepcopy(self.value); value['libraries']['ICU::data']['inspection'] = {'passed': True}
        self.reject(value)

    def test_library_path_definition_link_and_kind_aliases_are_rejected(self):
        for name, replacement in (('path', 'C:/other/icu.lib'), ('path', 'C:/output/prefix/lib/icu.a'),
            ('includes', ['C:/outside/include']), ('definitions', ['X=$<CONFIG>']),
            ('links', ['Fontconfig::Fontconfig'])):
            expected = copy.deepcopy(self.expected); expected['libraries']['ICU::data'][name] = replacement
            with self.subTest(name=name, replacement=replacement): self.reject(expected=expected)
        expected = copy.deepcopy(self.expected)
        expected['libraries']['ICU::uc'].update({k: expected['libraries']['ICU::data'][k] for k in ('path', 'sha256')})
        self.reject(expected=expected)

    def test_probe_binds_final_command_all_twenty_ordered_inputs_and_output(self):
        for name, replacement in (('command_id', 'icu-build'), ('library_targets', ['ICU::data']),
                                  ('link_inputs', []), ('output', reference('C:/probe/out.dll'))):
            expected = copy.deepcopy(self.expected); expected['probe'][name] = replacement
            with self.subTest(name=name): self.reject(expected=expected)
        expected = copy.deepcopy(self.expected); expected['probe']['link_inputs'].reverse()
        self.reject(expected=expected)
        self.value['probe']['output']['sha256'] = digest('other'); self.reject()

    def test_malformed_nested_observations_fail_with_value_error(self):
        for replacement in (None, True, 'passed', [], {'passed': True}):
            value = copy.deepcopy(self.value); value['commands'][0]['logs']['combined'] = replacement
            with self.subTest(replacement=replacement): self.reject(value)
        expected = copy.deepcopy(self.expected); expected['probe']['command_id'] = []
        self.reject(expected=expected)

    def test_frozen_source_and_tool_postflight_are_required(self):
        value = copy.deepcopy(self.value); value['postflight']['toolchain_identity_sha256'] = digest('changed')
        self.reject(value)
        value = copy.deepcopy(self.value); value['postflight']['sources']['webp'] = digest('changed')
        self.reject(value)
        self.value['postflight']['sources']['extra'] = digest('other'); self.reject()


class PureBoundaryTests(unittest.TestCase):
    def test_module_load_and_pure_checks_do_not_import_native_or_read_bodies(self):
        # Read the one new source before forbidding reads, then execute its module
        # code in isolation. No retained or existing project module is consulted.
        source = (ROOT / 'tools/appended_engine_windows_dependency_proof.py').read_bytes()
        imports = []
        original_import = __import__
        def guarded_import(name, *args, **kwargs):
            imports.append(name)
            if name.startswith(('appended_engine_', 'process_tree', 'subprocess', 'ctypes')):
                raise AssertionError('unexpected native/body import: ' + name)
            return original_import(name, *args, **kwargs)
        h = identity(); value, expected = receipts()
        namespace = {'__name__': 'isolated_pure_proof'}
        with mock.patch('builtins.open', side_effect=AssertionError('body read')), \
                mock.patch('pathlib.Path.open', side_effect=AssertionError('body read')), \
                mock.patch('builtins.__import__', side_effect=guarded_import):
            exec(compile(source, '<pure-proof>', 'exec'), namespace)
            checked = namespace['toolchain_identity'](h)
            raw = namespace['encoded'](checked)
            namespace['validate_toolchain_identity'](raw, hashlib.sha256(raw).hexdigest(), h)
            namespace['validate_receipt'](value, expected)
        self.assertNotIn('appended_engine_windows_prototype', imports)

    def test_explicit_lazy_entry_points_delegate_only_on_request(self):
        controller = types.ModuleType('appended_engine_windows_dependencies')
        controller.admit_dependency_producer = mock.Mock(return_value={'native': 'controller-only'})
        controller.validate_source_declarations = mock.Mock(return_value={'source': 'controller-only'})
        with mock.patch.dict(sys.modules, {'appended_engine_windows_dependencies': controller}):
            self.assertEqual(proof.admit_dependency_producer('ref', 'inputs', 'inventories', 'H'),
                             {'native': 'controller-only'})
            controller.admit_dependency_producer.assert_called_once_with('ref', 'inputs', 'inventories', 'H')
            self.assertEqual(proof.validate_source_declarations(b'H', 'Hpin', b'D', 'Dpin', 'inputs'),
                             {'source': 'controller-only'})
            controller.validate_source_declarations.assert_called_once_with(b'H', 'Hpin', b'D', 'Dpin', 'inputs')


if __name__ == '__main__':
    unittest.main()
