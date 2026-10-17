"""Pure and fake-process native dependency producer checks; no SDK is run.

Supplier archives, compiler images, configure/build tools and network services
are never used. Minimal generated archives contain inert text, and supervisor
tests use unittest mocks exclusively. These checks cannot qualify a native SDK.
"""
import copy
from contextlib import contextmanager, ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import tarfile
import tempfile
import types
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/appended_engine_native_dependencies.py'
FIXTURES = ROOT / 'tests/fixtures/appended_engine_native_dependencies'
TARGET = {'system': 'Linux', 'processor': 'x86_64',
          'triple': 'x86_64-buildroot-linux-gnu', 'pointer_bits': 64}
LIMITS = {'prepare_seconds': 60, 'configure_seconds': 60, 'build_seconds': 60,
          'cleanup_seconds': 5, 'maximum_jobs': 4, 'maximum_output_bytes': 1048576,
          'minimum_free_bytes': 1, 'maximum_process_tree_bytes': 1048576}
PIN = '1' * 64
SYNTHETIC_CONTROLLER = {'kind': 'SYNTHETIC-controller-double-only',
                        'scope': 'synthetic-unit-fixture-no-program-execution'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode('ascii')


def inert_native_archive():
    """Hand-encoded ELF/ar structure; no compiler-produced or executed code."""
    ident = b'\x7fELF\x02\x01\x01\x00' + bytes(8)
    body = ident + struct.pack('<HHIQQQIHHHHHH', 1, 62, 1, 0, 0, 64, 0,
                               64, 0, 0, 64, 1, 0) + bytes(64)
    header = ('inert.o/'.ljust(16) + '0'.ljust(12) + '0'.ljust(6) + '0'.ljust(6)
              + '100644'.ljust(8) + str(len(body)).ljust(10) + '`\n').encode('ascii')
    return b'!<arch>\n' + header + body


def inert_native_dso():
    """Only an ELF64 ET_DYN header, incapable of being loaded or executed."""
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HH', header, 16, 3, 62)
    return bytes(header)


def load_helper():
    module = types.ModuleType('_native_dependencies_unit_helper')
    module.__file__ = str(HELPER)
    old_bytecode, old_path = sys.dont_write_bytecode, list(sys.path)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        exec(compile(HELPER.read_bytes(), str(HELPER), 'exec'), module.__dict__)
    finally:
        sys.dont_write_bytecode, sys.path[:] = old_bytecode, old_path
    return module


@contextmanager
def no_programs():
    with ExitStack() as stack:
        for name in ('subprocess.run', 'subprocess.Popen', 'subprocess.check_output', 'os.system'):
            stack.enter_context(mock.patch(name, side_effect=AssertionError('program launch forbidden')))
        yield


class TinyFiles:
    def __init__(self, root):
        self.root = Path(root)

    def file(self, relative, raw=b'inert fixture\n', mode=0o644):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def document(self, relative, value):
        path = self.file(relative, encoded(value))
        return {'path': relative, 'sha256': digest(path.read_bytes())}

    def archive(self, relative, members, *, archive_format='tar-gzip', normalizations=None):
        """Members are (name, kind, body/target, mode), never executable code."""
        stream = io.BytesIO()
        if archive_format == 'zip':
            with zipfile.ZipFile(stream, 'w') as archive:
                for name, kind, body, mode in members:
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    entry_type = {'file': stat.S_IFREG, 'directory': stat.S_IFDIR,
                                  'link': stat.S_IFLNK, 'special': stat.S_IFIFO}[kind]
                    info.external_attr = (entry_type | mode) << 16
                    archive.writestr(info, body)
        else:
            with tarfile.open(fileobj=stream, mode='w:gz' if archive_format == 'tar-gzip' else 'w:xz') as archive:
                for name, kind, body, mode in members:
                    info = tarfile.TarInfo(name)
                    info.mode = mode
                    info.mtime = 0
                    if kind == 'file':
                        info.size = len(body)
                        archive.addfile(info, io.BytesIO(body))
                    else:
                        info.type = {'directory': tarfile.DIRTYPE, 'link': tarfile.SYMTYPE,
                                     'hard': tarfile.LNKTYPE, 'special': tarfile.FIFOTYPE}[kind]
                        if kind in ('link', 'hard'):
                            info.linkname = body
                        archive.addfile(info)
        raw = stream.getvalue()
        path = self.file(relative, raw)
        return {'path': str(path), 'sha256': digest(raw), 'bytes': len(raw),
                'format': archive_format, 'strip_prefix': 'source',
                'normalizations': normalizations or {}}


class DependencyCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='native-dependencies-unit-')
        self.addCleanup(temporary.cleanup)
        self.f = TinyFiles(temporary.name)
        self.guard = no_programs()
        self.guard.__enter__()
        self.addCleanup(self.guard.__exit__, None, None, None)


class DependencyFormats(DependencyCase):
    def test_json_rejects_duplicates_nonfinite_and_bad_encoding(self):
        for index, raw in enumerate((b'{"a":1,"a":2}', b'{"a":{"x":1,"x":2}}',
                                     b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e10000}',
                                     b'{} {}', b'\xff')):
            path = self.f.file(str(index) + '.json', raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.api.document(path)

    def test_independent_pin_rejects_changed_document(self):
        path = self.f.file('input.json', b'{"a":1}\n')
        self.assertEqual(self.api.document(path, digest(path.read_bytes())), {'a': 1})
        with self.assertRaisesRegex(ValueError, 'independent pin'):
            self.api.document(path, PIN)

    def test_sha_requires_nonzero_exact_lowercase_digest(self):
        self.assertEqual(self.api.sha(PIN), PIN)
        for value in ('0' * 64, 'A' * 64, 'a' * 63, 'a' * 65, True, None, 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.api.sha(value)

    def test_limits_require_closed_positive_integers_and_exact_four_jobs(self):
        self.assertEqual(self.api._limits(copy.deepcopy(LIMITS)), LIMITS)
        for key in LIMITS:
            for value in (True, 0, -1, '4', 2**49):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.api._limits({**LIMITS, key: value})
        for values in ({**LIMITS, 'maximum_jobs': 2}, {**LIMITS, 'extra': 1},
                       {**LIMITS, 'cleanup_seconds': 61}, {**LIMITS, 'build_seconds': 86401}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.api._limits(values)

    def test_cmake_literals_reject_variable_list_control_and_unicode_injection(self):
        for value in ('x;y', '${ENV}', '$(command)', 'x|y', 'x\ny', 'x\ty', 'é', '', True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.api.cmake_literal(value)
        self.assertEqual(self.api.cmake_literal('path with spaces'), '[=[path with spaces]=]')
        self.assertEqual(self.api.cmake_literal('x]=]y'), '[==[x]=]y]==]')

    def test_cache_is_literal_closed_and_deterministic(self):
        values = {'ROOT': '/owned/a path', 'LIST': ['one', 'two'], 'EMPTY': ''}
        actual = self.api.render_cache(values, ['ROOT', 'LIST', 'EMPTY'])
        self.assertIn(b'set(ROOT [=[/owned/a path]=] CACHE INTERNAL "" FORCE)', actual)
        self.assertIn(b'set(LIST [=[one]=] [=[two]=] CACHE INTERNAL "" FORCE)', actual)
        self.assertIn(b'set(EMPTY "" CACHE INTERNAL "" FORCE)', actual)
        for invalid, names in (({'bad)\nmessage(FATAL_ERROR x)': 'x'}, ['bad)\nmessage(FATAL_ERROR x)']),
                               ({'X': []}, ['X']), ({'X': ['a;b']}, ['X']),
                               ({'X': 'value'}, ['Y'])):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.api.render_cache(invalid, names)

    def test_cache_rejects_exhausted_safe_delimiter(self):
        payload = ''.join(']' + '=' * width + ']' for width in range(1, 9))
        with self.assertRaises(ValueError):
            self.api.cmake_literal(payload)


class DependencyProfile(DependencyCase):
    def test_recipe_has_exact_independently_frozen_fifteen_source_pins_and_dag(self):
        expected = json.loads((FIXTURES / 'source-pins.json').read_bytes())
        profile = self.api.load_profile()
        actual = {name: [entry[key] for key in ('version', 'sha256', 'bytes', 'format',
                                                'strip_prefix', 'depends')]
                  for name, entry in profile['components'].items()}
        self.assertEqual(actual, expected)
        visited = set()
        while len(visited) < len(expected):
            ready = {name for name, entry in expected.items()
                     if name not in visited and set(entry[-1]) <= visited}
            self.assertTrue(ready, 'dependency graph has a cycle or unknown dependency')
            visited.update(ready)

    def test_recipe_cmake_components_select_static_targets_and_fixed_job_limit(self):
        profile = self.api.load_profile()
        self.assertEqual(profile['maximum_jobs'], 4)
        self.assertEqual(profile['source_policy'], 'exact-retained-archives-no-fetch-no-patches')
        self.assertEqual(len(profile['libraries']), 22)
        self.assertTrue(all(entry['archive'].endswith('.a') for entry in profile['libraries'].values()))
        for name, entry in profile['components'].items():
            with self.subTest(component=name):
                self.assertEqual(entry['install_policy'], 'recipe-selected-static-only')
                if entry['build_system'] in ('cmake', 'recipe-cmake'):
                    self.assertNotIn('all', entry['build_targets'])
                    self.assertTrue(entry['build_targets'])
        pic = profile['pic_check']
        self.assertEqual(set(pic['ordered_libraries']), set(profile['libraries']))
        self.assertEqual(len(pic['ordered_libraries']), 22)
        self.assertEqual(pic['output'], 'pic/libfoundation-native-dependencies-pic-check.so')
        self.assertEqual(pic['link_options'], ['-Wl,-z,defs', '-Wl,-z,text'])

    def test_profile_rejects_bool_version_unknown_fields_and_wrong_target(self):
        profile = self.api.load_profile()
        for value in ({**profile, 'schema_version': True}, {**profile, 'extra': 1},
                      {**profile, 'target': {**TARGET, 'processor': 'aarch64'}},
                      {**profile, 'maximum_jobs': 8}):
            with self.subTest(value=value), mock.patch.object(self.api, 'document', return_value=value), \
                    self.assertRaises(ValueError):
                self.api.load_profile()

    def test_recipe_projection_is_complete_and_graph_is_local_serial_with_explicit_targets(self):
        recipe = ROOT / self.api.RECIPE
        names = set(self.api.RECIPE_FILES)
        for name in self.api.RECIPE_FILES:
            source = recipe / name
            self.assertTrue(source.is_file(), name)
            if source.suffix not in ('.cmake', '.txt'):
                continue
            for include in re.findall(r'include\("\$\{CMAKE_CURRENT_LIST_DIR\}/([^"\n]+)"\)', source.read_text()):
                relative = (source.parent / include).relative_to(recipe).as_posix()
                self.assertIn(relative, names, 'copied recipe omits local include ' + relative)
        top = (recipe / 'CMakeLists.txt').read_text()
        components = (recipe / 'cmake/components.cmake').read_text()
        self.assertIn('add_custom_target(native-dependencies DEPENDS native-pic)', top)
        self.assertIn('DEPENDS native-fontconfig EXCLUDE_FROM_ALL TRUE', top)
        self.assertNotRegex(top, r'add_custom_target\(native-dependencies\s+ALL')
        self.assertEqual(components.count('DOWNLOAD_COMMAND "" UPDATE_COMMAND "" PATCH_COMMAND ""'), 2)
        self.assertEqual(components.count('DEPENDS ${_native_previous} EXCLUDE_FROM_ALL TRUE'), 2)
        self.assertIn('set(_native_previous native-${_component})', components)
        self.assertIn('--target ${_targets} --parallel 4', components)
        self.assertIn('"CMAKE_BUILD_PARALLEL_LEVEL=4"', components)
        self.assertIn('"${PROGRAM_make}" -j4', components)
        self.assertNotRegex(components, r'(?m)^\s*(?:URL|GIT_REPOSITORY|SVN_REPOSITORY)\s')
        common = (recipe / 'cmake/install-common.cmake').read_text()
        directory_helper = re.search(r'function\(native_directory relative\)(.*?)endfunction\(\)',
                                     common, re.S).group(1)
        permissions = re.search(r'file\(CHMOD "\$\{_owned\}" PERMISSIONS\s*(.*?)\)',
                                directory_helper, re.S).group(1).split()
        self.assertEqual(set(permissions), {'OWNER_READ', 'OWNER_WRITE', 'OWNER_EXECUTE',
                                          'GROUP_READ', 'GROUP_EXECUTE', 'WORLD_READ', 'WORLD_EXECUTE'})
        self.assertRegex(directory_helper, r'if\(_check STREQUAL NATIVE_PREFIX\)\s*break\(\)')
        self.assertLess(directory_helper.index('IS_SYMLINK "${_check}"'),
                        directory_helper.index('file(MAKE_DIRECTORY "${_owned}")'))
        copy_helper = re.search(r'function\(native_copy source relative\)(.*?)endfunction\(\)',
                               common, re.S).group(1)
        self.assertIn('native_directory("${_relative_parent}")', copy_helper)
        self.assertNotIn('file(MAKE_DIRECTORY', copy_helper)
        assets = (recipe / 'cmake/install-assets.cmake').read_text()
        self.assertIn('native_directory(var/cache/fontconfig)', assets)
        self.assertNotIn('file(MAKE_DIRECTORY', assets)


class DependencySourceSelection(DependencyCase):
    def source_fixture(self):
        archive = self.f.archive('retained/archive.tar.gz', [('source/a.c', 'file', b'inert\n', 0o644)])
        notice = self.f.file('retained/NOTICE', b'Original synthetic notice\n')
        component = {key: archive[key] for key in ('sha256', 'bytes', 'format', 'strip_prefix')}
        source = {'schema_version': 1, 'kind': self.api.SOURCES_KIND,
                  'archives': {'sample': {**archive, 'path': 'archive.tar.gz'}},
                  'notices': [{'path': 'NOTICE', 'sha256': digest(notice.read_bytes())}]}
        return source, {'components': {'sample': component}}

    def test_sources_verify_exact_local_archive_and_original_notice_bytes(self):
        source, profile = self.source_fixture()
        inputs = self.api.native_inputs.InputSet()
        archives, notices = self.api._sources(source, self.f.root / 'retained', inputs, profile)
        self.assertEqual(archives['sample']['path'], str(self.f.root / 'retained/archive.tar.gz'))
        self.assertEqual(notices[0]['path'], str(self.f.root / 'retained/NOTICE'))
        inputs.recheck()

    def test_sources_reject_unknown_missing_bool_and_recipe_mismatch(self):
        source, profile = self.source_fixture()
        bad_values = [{**source, 'extra': 1}, {**source, 'schema_version': True},
                      {**source, 'archives': {}}, {**source, 'notices': []}]
        for key, value in (('sha256', PIN), ('bytes', True), ('format', 'zip'),
                           ('strip_prefix', 'different'), ('extra', 1)):
            bad = copy.deepcopy(source)
            bad['archives']['sample'][key] = value
            bad_values.append(bad)
        for bad in bad_values:
            with self.subTest(value=bad), self.assertRaises(ValueError):
                self.api._sources(bad, self.f.root / 'retained', self.api.native_inputs.InputSet(), profile)

    def test_sources_reject_tampered_archive_and_notice(self):
        source, profile = self.source_fixture()
        for name in ('archive.tar.gz', 'NOTICE'):
            path = self.f.root / 'retained' / name
            original = path.read_bytes()
            path.write_bytes(b'tampered\n')
            with self.subTest(path=name), self.assertRaises(ValueError):
                self.api._sources(source, path.parent, self.api.native_inputs.InputSet(), profile)
            path.write_bytes(original)

    def test_sources_reject_self_links_chains_and_unportable_names(self):
        source, profile = self.source_fixture()
        for mapping in ({'a': 'a'}, {'a': 'b', 'b': 'c'}, {'../a': 'b'}, {'a': '../b'}, []):
            bad = copy.deepcopy(source)
            bad['archives']['sample']['normalizations'] = mapping
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                self.api._sources(bad, self.f.root / 'retained', self.api.native_inputs.InputSet(), profile)

    def test_selection_rejects_shape_bool_target_and_limit_before_input_parsers(self):
        ref = {'path': 'not-opened.json', 'sha256': PIN}
        selection = {'schema_version': 1, 'kind': self.api.SELECTION_KIND, 'target': TARGET,
                     'archives': ref, 'toolchain': ref, 'host_tools': ref, 'assets': ref,
                     'phase_limits': LIMITS}
        for index, bad in enumerate(({**selection, 'schema_version': True},
                                     {**selection, 'unexpected': 1},
                                     {**selection, 'target': {**TARGET, 'pointer_bits': True}},
                                     {**selection, 'phase_limits': {**LIMITS, 'maximum_jobs': 2}})):
            path = self.f.file(str(index) + '.json', encoded(bad))
            with self.subTest(value=bad), mock.patch.object(self.api, 'load_profile') as profile, \
                    self.assertRaises(ValueError):
                self.api.inspect_selection(path, digest(path.read_bytes()))
            profile.assert_not_called()


class DependencyProducerControls(DependencyCase):
    SDK_CONTROLS = ('tools/appended_engine_native_sdk.py',
        'recipes/webkitwasm-native-rich4083-v1/producer/native-sdk-toolchain.cmake.in')

    def source_fixture(self, prefix='repository'):
        root = self.f.root / prefix
        for name in self.api.PRODUCER_SOURCES + self.api.PRIVATE_SHARED_SOURCES:
            self.f.file(prefix + '/' + name, ('SYNTHETIC producer source ' + name + '\n').encode('ascii'))
        return root

    def test_fixed_source_authority_preserves_recipe_helpers_and_adds_only_sdk_controls(self):
        self.assertEqual(self.api.PRODUCER_CONTROL_SOURCES, self.SDK_CONTROLS)
        self.assertEqual(self.api.PRODUCER_HELPERS, (
            'appended_engine_native_dependencies.py', 'appended_engine_native_inputs.py',
            'appended_engine_native_actions_contract.py', 'appended_engine_document_contract.py',
            'appended_engine_editor_contract.py', 'appended_engine_manifest.py',
            'dependency_archive.py', 'process_tree.py'))
        self.assertEqual(len(self.api.RECIPE_FILES), 13)
        expected = tuple(self.api.RECIPE + '/' + name for name in self.api.RECIPE_FILES) + tuple(
            'tools/' + name for name in self.api.PRODUCER_HELPERS) + self.SDK_CONTROLS
        self.assertEqual(self.api.PRODUCER_SOURCES, expected)
        self.assertEqual(len(set(expected)), 23)

    def test_real_capture_retains_adapter_and_template_bytes_and_original_source_recheck(self):
        root = self.source_fixture()
        inputs = self.api.native_inputs.InputSet()
        self.api._producer_inputs(inputs, root)
        records = {item['path']: item for item in inputs.records}
        self.assertEqual(set(records), {str(root / name) for name in
                                       self.api.PRODUCER_SOURCES + self.api.PRIVATE_SHARED_SOURCES})
        for name in self.SDK_CONTROLS:
            path = root / name
            original = path.read_bytes()
            self.assertEqual(inputs.bytes(path), original)
            self.assertEqual(records[str(path)]['sha256'], digest(original))
            self.assertEqual(records[str(path)]['mode_policy'], 'repository-producer-logical-v1')
        inputs.recheck()

    def test_selection_plan_retains_sdk_controls_for_original_explicit_input_format(self):
        root = self.source_fixture()
        ref = self.f.document('synthetic-input.json', {'scope': 'SYNTHETIC-parser-double-only'})
        selection = {'schema_version': 1, 'kind': self.api.SELECTION_KIND, 'target': TARGET,
                     'archives': ref, 'toolchain': ref, 'host_tools': ref, 'assets': ref,
                     'phase_limits': LIMITS}
        path = self.f.file('selection.json', encoded(selection))
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(self.api, 'load_profile', return_value={'cmake_inputs': []}))
            stack.enter_context(mock.patch.object(self.api, '_sources', return_value=({}, [])))
            toolchain = stack.enter_context(mock.patch.object(self.api.native_inputs, 'parse_toolchain',
                return_value={'kind': 'foundation-native-engine-prototype-toolchain-v1'}))
            host = stack.enter_context(mock.patch.object(self.api.native_inputs, 'parse_host_tools',
                return_value={'programs': {'make': {'scope': 'SYNTHETIC-no-program'}}}))
            stack.enter_context(mock.patch.object(self.api.native_inputs, 'render_environment', return_value={}))
            stack.enter_context(mock.patch.object(self.api.native_inputs, 'parse_assets', return_value={}))
            stack.enter_context(mock.patch.object(self.api, 'cache_values', return_value={}))
            stack.enter_context(mock.patch.object(self.api, 'render_cache', return_value=b''))
            plan = self.api.make_plan(path, digest(path.read_bytes()), self.f.root / 'plan', repository_root=root)
        self.assertEqual(toolchain.call_args.kwargs, {'repository_root': root})
        self.assertEqual(host.call_args.kwargs, {'repository_root': root})
        records = {entry['path']: entry for entry in plan['inspection']['inputs']}
        for name in self.SDK_CONTROLS:
            source = root / name
            self.assertEqual(records[str(source)]['sha256'], digest(source.read_bytes()))
        self.assertEqual(plan, json.loads((self.f.root / 'plan/plan.json').read_bytes()))
        self.assertIs(plan['production_eligible'], False)
        self.assertIs(plan['kernel_rebuild'], False)

    def test_missing_adapter_or_template_refuses_fixed_source_capture(self):
        for number, name in enumerate(self.SDK_CONTROLS):
            root = self.source_fixture('missing-' + str(number))
            (root / name).unlink()
            with self.subTest(source=name), self.assertRaises(FileNotFoundError):
                self.api._producer_inputs(self.api.native_inputs.InputSet(), root)

    def test_adapter_and_template_changes_refuse_recheck_and_original_plan(self):
        for number, name in enumerate(self.SDK_CONTROLS):
            root = self.source_fixture('changed-' + str(number))
            inputs = self.api.native_inputs.InputSet()
            self.api._producer_inputs(inputs, root)
            original = {'inputs': list(inputs.records)}
            value = {'schema_version': 1, 'kind': self.api.PLAN_KIND,
                     'scope': 'explicit-native-dependency-candidate',
                     'selection': {'path': str(self.f.root / 'not-opened.json'), 'sha256': PIN},
                     'inspection': original, 'production_eligible': False,
                     'engine_execution': False, 'kernel_rebuild': False}
            plan = self.f.file('plan-' + str(number) + '.json', encoded(value))
            path = root / name
            path.write_bytes(path.read_bytes().replace(b'SYNTHETIC', b'ALTERED__', 1))
            with self.subTest(source=name), self.assertRaises(ValueError):
                inputs.recheck()
            def fresh_source_inspection(*args, **kwargs):
                fresh = self.api.native_inputs.InputSet()
                self.api._producer_inputs(fresh, root)
                return types.SimpleNamespace(as_dict=lambda: {'inputs': list(fresh.records)})
            with self.subTest(source=name), mock.patch.object(self.api, 'inspect_selection',
                    side_effect=fresh_source_inspection), self.assertRaisesRegex(ValueError, 'no longer matches'):
                self.api.verify_plan(plan, digest(plan.read_bytes()), repository_root=root)

    def test_source_mode_normalization_cannot_admit_sdk_or_asset_data(self):
        root = self.source_fixture()
        for name in self.SDK_CONTROLS:
            (root / name).chmod(0o664)
        inputs = self.api.native_inputs.InputSet()
        self.api._producer_inputs(inputs, root)
        for name in self.SDK_CONTROLS:
            path = root / name
            with self.subTest(source=name), self.assertRaises(ValueError):
                inputs.file(path, digest(path.read_bytes()), 'SDK or asset data')
        inputs.recheck()

    def test_shared_runtime_controls_keep_native13_authority_and_old23_unchanged(self):
        root = self.source_fixture()
        inputs = self.api.native_inputs.InputSet()
        policy = root / self.api.PRIVATE_SHARED_SOURCES[0]
        self.api.native_inputs._producer_bytes(inputs, policy, 'private policy prerequisite', root)
        self.api._producer_inputs(inputs, root)
        self.assertEqual(len(inputs.records), 34)
        self.assertEqual(len(self.api.PRODUCER_SOURCES), 23)
        self.assertTrue(set(self.api.PRIVATE_SHARED_SOURCES) <= set(self.api.native_inputs.PRODUCERS))
        with self.assertRaises(ValueError):
            inputs.repository_file(policy, digest(policy.read_bytes()), 'incorrect dependency authority',
                repository_root=root, source_paths=self.api.PRODUCER_SOURCES + (self.api.PRIVATE_SHARED_SOURCES[0],))
        inputs.recheck()

    def test_original_proof_consumer_is_retained_under_native14_and_mutation_refuses_recheck(self):
        name = 'tools/appended_engine_native_original_proof.py'
        self.assertEqual(self.api.PRIVATE_SHARED_SOURCES[-2], name)
        self.assertEqual(self.api.PRIVATE_SHARED_SOURCES[-1], 'tools/appended_engine_native_prototype.py')
        self.assertEqual(len(self.api.PRIVATE_SHARED_SOURCES), 11)
        self.assertEqual(len(self.api.native_inputs.PRODUCERS), 20)
        root = self.source_fixture()
        path = root / name
        original = path.read_bytes()
        inputs = self.api.native_inputs.InputSet()
        self.api.native_inputs._producer_bytes(inputs, path, 'original proof consumer prerequisite', root)
        self.api._producer_inputs(inputs, root)
        records = {item['path']: item for item in inputs.records}
        self.assertEqual(len(records), 34)
        self.assertEqual(records[str(path)]['sha256'], digest(original))
        self.assertEqual(records[str(path)]['bytes'], len(original))
        self.assertEqual(records[str(path)]['mode_policy'], 'repository-producer-logical-v1')
        self.assertEqual(inputs.bytes(path), original)
        inputs.recheck()
        path.write_bytes(original.replace(b'SYNTHETIC', b'ALTERED__', 1))
        with self.assertRaises(ValueError):
            inputs.recheck()


class DependencyArchive(DependencyCase):
    def extract(self, members, *, normalizations=None, archive_format='tar-gzip', **kwargs):
        number = len(list(self.f.root.glob('archive-*')))
        entry = self.f.archive('archive-' + str(number), members,
                               archive_format=archive_format, normalizations=normalizations)
        output = self.f.root / ('output-' + str(number))
        return self.api.extract_archive(entry, output, **kwargs), output

    def test_tar_gzip_tar_xz_and_zip_materialize_only_regular_bytes(self):
        for archive_format in ('tar-gzip', 'tar-xz', 'zip'):
            with self.subTest(format=archive_format):
                records, output = self.extract([('source/', 'directory', b'', 0o777),
                                                ('source/a.c', 'file', b'int inert;\n', 0o666)],
                                               archive_format=archive_format)
                self.assertEqual(records, [{'path': 'a.c', 'sha256': digest(b'int inert;\n'),
                                            'bytes': 11, 'mode': 0o644}])
                self.assertEqual((output / 'a.c').read_bytes(), b'int inert;\n')

    def test_archive_normalizes_file_modes_without_setuid_or_group_write(self):
        records, output = self.extract([('source/tool', 'file', b'inert\n', 0o6777)])
        self.assertEqual(records[0]['mode'], 0o755)
        self.assertEqual(stat.S_IMODE((output / 'tool').stat().st_mode), 0o755)

    def test_archive_rejects_traversal_absolute_outside_root_and_backslash(self):
        for name in ('source/../escape', '/source/absolute', 'other/file', 'source/a\\b',
                     'source//bad', 'source/./bad'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.extract([(name, 'file', b'inert\n', 0o644)])
        self.assertFalse((self.f.root / 'escape').exists())

    def test_archive_rejects_case_alias_duplicates_and_file_directory_conflicts(self):
        for names in (('A.c', 'a.c'), ('same', 'same'), ('parent', 'parent/child')):
            with self.subTest(names=names), self.assertRaises(ValueError):
                self.extract([('source/' + name, 'file', b'inert\n', 0o644) for name in names])

    def test_archive_rejects_special_entries_and_unadmitted_links(self):
        for kind, body in (('special', b''), ('link', 'a.c'), ('hard', 'source/a.c')):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.extract([('source/a.c', 'file', b'inert\n', 0o644),
                              ('source/other', kind, body, 0o644)])
        with self.assertRaises(ValueError):
            self.extract([('source/fifo', 'special', b'', 0o644)], archive_format='zip')

    def test_explicit_relative_symlink_is_copied_from_exact_regular_target(self):
        records, output = self.extract([('source/a.c', 'file', b'inert\n', 0o755),
                                        ('source/sub/alias.c', 'link', '../a.c', 0o777)],
                                       normalizations={'sub/alias.c': 'a.c'})
        self.assertEqual((output / 'sub/alias.c').read_bytes(), b'inert\n')
        self.assertFalse((output / 'sub/alias.c').is_symlink())
        self.assertEqual(records[1]['normalized_from'], 'a.c')
        self.assertEqual(records[1]['mode'], 0o755)

    def test_explicit_hard_link_is_copied_without_preserving_hard_link_identity(self):
        _, output = self.extract([('source/a.c', 'file', b'inert\n', 0o644),
                                  ('source/alias.c', 'hard', 'source/a.c', 0o644)],
                                 normalizations={'alias.c': 'a.c'})
        self.assertEqual((output / 'alias.c').read_bytes(), b'inert\n')
        self.assertNotEqual((output / 'alias.c').stat().st_ino, (output / 'a.c').stat().st_ino)

    def test_archive_rejects_link_escape_wrong_target_chain_and_invented_map(self):
        cases = [('a.c', '../../escape', {'alias': 'a.c'}),
                 ('a.c', 'different', {'alias': 'a.c'}),
                 ('a.c', 'a.c', {'alias': 'missing'}),
                 ('a.c', 'a.c', {'alias': 'a.c', 'invented': 'a.c'})]
        for target, actual, mapping in cases:
            with self.subTest(actual=actual, mapping=mapping), self.assertRaises(ValueError):
                self.extract([('source/' + target, 'file', b'inert\n', 0o644),
                              ('source/alias', 'link', actual, 0o644)], normalizations=mapping)
        with self.assertRaises(ValueError):
            self.extract([('source/a.c', 'file', b'inert\n', 0o644),
                          ('source/alias', 'link', 'other', 0o644),
                          ('source/other', 'link', 'a.c', 0o644)],
                         normalizations={'alias': 'other', 'other': 'a.c'})

    def test_archive_rejects_empty_source_or_non_directory_root(self):
        for members in ([], [('source/', 'directory', b'', 0o755)],
                        [('source', 'file', b'inert\n', 0o644)]):
            with self.subTest(members=members), self.assertRaises(ValueError):
                self.extract(members)

    def test_archive_enforces_member_count_member_bytes_and_expanded_byte_limits(self):
        members = [('source/a', 'file', b'1234', 0o644), ('source/b', 'file', b'56', 0o644)]
        for constant, bound in (('MAX_ARCHIVE_FILES', 1), ('MAX_MEMBER_BYTES', 3)):
            with self.subTest(constant=constant), mock.patch.object(self.api, constant, bound), \
                    self.assertRaises(ValueError):
                self.extract(members)
        with self.assertRaises(ValueError):
            self.extract(members, maximum_bytes=5)

    def test_normalized_link_bytes_count_against_expansion_limit(self):
        with self.assertRaises(ValueError):
            self.extract([('source/a', 'file', b'1234', 0o644),
                          ('source/b', 'link', 'a', 0o644)],
                         normalizations={'b': 'a'}, maximum_bytes=7)

    def test_archive_rejects_expired_deadline_and_changed_pin(self):
        with mock.patch.object(self.api.time, 'monotonic', return_value=20), self.assertRaises(ValueError):
            self.extract([('source/a', 'file', b'inert', 0o644)], deadline=20)
        entry = self.f.archive('tampered.tar.gz', [('source/a', 'file', b'inert', 0o644)])
        entry['sha256'] = PIN
        with self.assertRaises(ValueError):
            self.api.extract_archive(entry, self.f.root / 'tampered-output')

    def test_normalized_alias_copy_rechecks_deadline_and_free_reserve(self):
        members = [('source/a', 'file', b'inert', 0o644), ('source/b', 'link', 'a', 0o644)]
        # Four admission/chunk checkpoints precede normalization for this fixture.
        times = iter((0, 0, 0, 0))
        with mock.patch.object(self.api.time, 'monotonic', side_effect=lambda: next(times, 10)), \
                self.assertRaisesRegex(ValueError, 'wall deadline'):
            self.extract(members, normalizations={'b': 'a'}, deadline=10)
        free = iter((100, 100, 100, 100))
        with mock.patch.object(self.api.shutil, 'disk_usage', side_effect=lambda path:
                               types.SimpleNamespace(free=next(free, 0))), \
                self.assertRaisesRegex(ValueError, 'free disk reserve'):
            self.extract(members, normalizations={'b': 'a'}, minimum_free_bytes=1)


class DependencyOutputAndPlan(DependencyCase):
    def inspection(self):
        selection = self.f.file('selection.json', b'{}\n')
        return types.SimpleNamespace(selection_path=selection, protected_paths=(selection,),
                                     recheck=mock.Mock(), as_dict=mock.Mock(return_value={'frozen': 'inputs'}))

    def test_output_must_be_fresh_and_preserves_existing_bytes(self):
        path = self.f.file('occupied', b'preserve\n')
        for output in (path, self.f.root, Path('relative'), self.f.root / 'missing/child'):
            with self.subTest(output=output), self.assertRaises((ValueError, OSError)):
                self.api.fresh_output(output)
        self.assertEqual(path.read_bytes(), b'preserve\n')
        output = self.api.fresh_output(self.f.root / 'fresh')
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)

    def test_output_rejects_both_overlap_directions_and_symlink_ancestors(self):
        root = self.f.root / 'retained'
        root.mkdir()
        input_path = self.f.file('retained/source')
        for output, protected in ((root, [input_path]), (root / 'new', [root]),
                                  (self.f.root / 'new', [self.f.root / 'new/input'])):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.api.fresh_output(output, protected)
        (self.f.root / 'alias').symlink_to(root, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.api.fresh_output(self.f.root / 'alias/new')

    def test_output_rejects_shell_metacharacters_before_creating_any_directory(self):
        for name in ('with space', 'back`tick', 'amp&ersand', 'list|separator', '(parentheses)',
                     'semi;colon', 'dollar$sign'):
            output = self.f.root / name
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.api.fresh_output(output)
            self.assertFalse(output.exists())

    def test_save_is_immutable_and_dangling_symlink_output_is_occupied(self):
        path = self.f.file('existing', b'preserve\n')
        with self.assertRaises(FileExistsError):
            self.api.save(path, b'overwrite\n')
        link = self.f.root / 'dangling'
        link.symlink_to(self.f.root / 'absent')
        with self.assertRaises(ValueError):
            self.api.fresh_output(link)
        self.assertEqual(path.read_bytes(), b'preserve\n')

    def test_plan_is_passive_immutable_rechecked_and_marks_no_execution(self):
        inspection = self.inspection()
        output = self.f.root / 'plan'
        with mock.patch.object(self.api, 'inspect_selection', return_value=inspection):
            value = self.api.make_plan(inspection.selection_path, PIN, output)
            with self.assertRaises(ValueError):
                self.api.make_plan(inspection.selection_path, PIN, output)
        inspection.recheck.assert_called_once()
        self.assertEqual(json.loads((output / 'plan.json').read_bytes()), value)
        self.assertIs(value['production_eligible'], False)
        self.assertIs(value['engine_execution'], False)
        self.assertIs(value['kernel_rebuild'], False)

    def test_plan_recheck_failure_never_publishes_plan(self):
        inspection = self.inspection()
        inspection.recheck.side_effect = ValueError('retained bytes changed')
        output = self.f.root / 'plan'
        with mock.patch.object(self.api, 'inspect_selection', return_value=inspection), \
                self.assertRaisesRegex(ValueError, 'retained bytes changed'):
            self.api.make_plan(inspection.selection_path, PIN, output)
        self.assertFalse((output / 'plan.json').exists())

    def test_verify_plan_recomputes_inspection_and_rejects_reformatted_or_tampered_bytes(self):
        inspection = self.inspection()
        output = self.f.root / 'plan'
        with mock.patch.object(self.api, 'inspect_selection', return_value=inspection):
            value = self.api.make_plan(inspection.selection_path, PIN, output)
            path = output / 'plan.json'
            pin = digest(path.read_bytes())
            self.assertEqual(self.api.verify_plan(path, pin)[1], value)
            inspection.as_dict.return_value = {'frozen': 'changed'}
            with self.assertRaisesRegex(ValueError, 'no longer matches'):
                self.api.verify_plan(path, pin)
            path.write_bytes(encoded(value))
            with self.assertRaisesRegex(ValueError, 'independent pin'):
                self.api.verify_plan(path, pin)

    def test_verify_plan_rejects_unknown_bool_and_execution_claims(self):
        inspection = self.inspection()
        with mock.patch.object(self.api, 'inspect_selection', return_value=inspection):
            base = self.api.make_plan(inspection.selection_path, PIN, self.f.root / 'base-plan')
        for number, value in enumerate(({**base, 'schema_version': True}, {**base, 'extra': 1},
                                        {**base, 'engine_execution': True},
                                        {**base, 'production_eligible': 0})):
            path = self.f.file('bad-plan-' + str(number), encoded(value))
            with self.subTest(value=value), mock.patch.object(self.api, 'inspect_selection') as inspect, \
                    self.assertRaises(ValueError):
                self.api.verify_plan(path, digest(path.read_bytes()))
            inspect.assert_not_called()


class DependencySupervisor(DependencyCase):
    def run_fake(self, owner, *, resource_samples=None, clock=None):
        log = self.f.root / 'process.log'
        samples = resource_samples or [{'output_bytes': 0, 'free_bytes': 1000, 'process_tree_bytes': 0}]
        with ExitStack() as stack:
            launch = stack.enter_context(mock.patch.object(self.api.process_tree, 'launch', return_value=owner))
            stack.enter_context(mock.patch.object(self.api, '_resources', side_effect=lambda *args: samples.pop(0) if len(samples) > 1 else samples[0]))
            stack.enter_context(mock.patch.object(self.api.time, 'sleep'))
            if clock is not None:
                steps = iter(clock)
                stack.enter_context(mock.patch.object(self.api.time, 'monotonic',
                    side_effect=lambda: next(steps, clock[-1])))
            result = self.api.run_owned(['/inert/cmake', '--version'], self.f.root, log,
                                        {'PATH': '/inert'}, LIMITS, phase='configure', output=self.f.root)
        return result, launch.call_args

    def owner(self, *, polls=(0,), code=0):
        owner = mock.Mock()
        owner.poll.side_effect = list(polls)
        owner.finish.return_value = code
        owner.process.pid = 999999999
        return owner

    def test_supervisor_success_joins_owner_and_closes_log_before_return(self):
        owner = self.owner()
        result, call = self.run_fake(owner)
        owner.finish.assert_called_once_with()
        owner.terminate.assert_not_called()
        owner.close.assert_called_once_with()
        self.assertTrue(call.args[2].closed)
        self.assertTrue(result['process_tree_closed'])
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(call.kwargs['env'], {'PATH': '/inert'})

    def test_supervisor_nonzero_exit_terminates_and_closes_without_success(self):
        owner = self.owner(code=7)
        with self.assertRaisesRegex(ValueError, 'exited 7'):
            self.run_fake(owner)
        owner.terminate.assert_called_once_with(timeout=5)
        owner.close.assert_called_once_with()

    def test_supervisor_deadline_terminates_then_closes_without_finish(self):
        owner = self.owner(polls=(None,))
        with self.assertRaisesRegex(ValueError, 'wall deadline'):
            self.run_fake(owner, clock=[0, 61])
        owner.terminate.assert_called_once_with(timeout=5)
        owner.finish.assert_not_called()
        owner.close.assert_called_once_with()

    def test_supervisor_live_tree_resource_failure_cleans_up(self):
        owner = self.owner(polls=(None,))
        before = {'output_bytes': 0, 'free_bytes': 1000, 'process_tree_bytes': 0}
        over = {**before, 'process_tree_bytes': LIMITS['maximum_process_tree_bytes'] + 1}
        with self.assertRaisesRegex(ValueError, 'memory limit'):
            self.run_fake(owner, resource_samples=[before, over], clock=[0, 1])
        owner.terminate.assert_called_once_with(timeout=5)
        owner.close.assert_called_once_with()

    def test_supervisor_uncertain_cleanup_is_preserved_as_failure(self):
        owner = self.owner(code=8)
        owner.terminate.side_effect = RuntimeError('descendant still alive')
        retained = []
        with mock.patch.object(self.api, '_UNCERTAIN_OWNERS', retained), \
                self.assertRaisesRegex(self.api.process_tree.ProcessTreeError, 'cleanup.*uncertain'):
            self.run_fake(owner)
        owner.terminate.assert_called_once_with(timeout=5)
        owner.close.assert_not_called()
        self.assertEqual(len(retained), 1)
        self.assertIs(retained[0], owner)
        stage = json.loads((self.f.root / 'process.stage.json').read_bytes())
        self.assertEqual(stage['status'], 'incomplete')
        self.assertTrue(stage['launched'])
        self.assertIs(stage['process_tree_closed'], False)
        self.assertIn('uncertain', stage['error'])

    def test_supervisor_stage_publication_failure_preserves_original_command_failure(self):
        owner = self.owner(code=7)
        save = self.api.save
        def fail_only_stage(path, value):
            if Path(path).name == 'process.stage.json':
                raise OSError('synthetic evidence storage failure')
            return save(path, value)
        with mock.patch.object(self.api, 'save', side_effect=fail_only_stage), \
                self.assertRaises(ValueError) as failure:
            self.run_fake(owner)
        self.assertIn('synthetic evidence storage failure', str(failure.exception))
        self.assertIn('exited 7', str(failure.exception.__cause__))
        self.assertEqual(failure.exception.native_stage_receipt['status'], 'incomplete')
        owner.terminate.assert_called_once_with(timeout=5)
        owner.close.assert_called_once_with()

    def test_supervisor_completed_process_still_rejects_expired_phase_deadline(self):
        owner = self.owner()
        with self.assertRaisesRegex(ValueError, 'wall deadline'):
            self.run_fake(owner, clock=[0, 61])
        owner.finish.assert_called_once()
        owner.close.assert_called_once()

    def test_supervisor_launch_failure_leaves_log_closed(self):
        log = self.f.root / 'failed-launch.log'
        observed = []
        def fail(argv, cwd, stream, **kwargs):
            observed.append(stream)
            raise OSError('synthetic launch failure')
        with mock.patch.object(self.api.process_tree, 'launch', side_effect=fail), \
                self.assertRaisesRegex(OSError, 'synthetic launch failure'):
            self.api.run_owned(['/inert/tool'], self.f.root, log, {}, LIMITS,
                               phase='build', output=self.f.root)
        self.assertTrue(observed[0].closed)

    def test_supervisor_aggregate_deadline_rejects_before_launch(self):
        with mock.patch.object(self.api.time, 'monotonic', return_value=10), \
                mock.patch.object(self.api.process_tree, 'launch') as launch, \
                self.assertRaisesRegex(ValueError, 'aggregate'):
            self.api.run_owned(['/inert/tool'], self.f.root, self.f.root / 'not-created.log', {}, LIMITS,
                               phase='inspection', output=self.f.root, absolute_deadline=10)
        launch.assert_not_called()
        self.assertFalse((self.f.root / 'not-created.log').exists())

    def test_supervisor_rejects_invalid_phase_argv_and_prelaunch_resources(self):
        for phase, argv in (('unknown', ['x']), ('build', []), ('build', [True]), ('build', [''])):
            with self.subTest(phase=phase, argv=argv), \
                    mock.patch.object(self.api.process_tree, 'launch') as launch, self.assertRaises(ValueError):
                self.api.run_owned(argv, self.f.root, self.f.root / 'unused', {}, LIMITS,
                                   phase=phase, output=self.f.root)
            launch.assert_not_called()
        with mock.patch.object(self.api, '_resources', return_value={
                'output_bytes': 0, 'free_bytes': 0, 'process_tree_bytes': 0}), \
                mock.patch.object(self.api.process_tree, 'launch') as launch, \
                self.assertRaisesRegex(ValueError, 'reserve'):
            self.api.run_owned(['x'], self.f.root, self.f.root / 'unused', {}, LIMITS,
                               phase='build', output=self.f.root)
        launch.assert_not_called()

    def test_resource_bounds_accept_exact_boundary_and_reject_each_excess(self):
        exact = {'output_bytes': LIMITS['maximum_output_bytes'], 'free_bytes': 1,
                 'process_tree_bytes': LIMITS['maximum_process_tree_bytes']}
        self.api._check_resources(exact, LIMITS)
        for key, value in (('output_bytes', exact['output_bytes'] + 1), ('free_bytes', 0),
                           ('process_tree_bytes', exact['process_tree_bytes'] + 1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.api._check_resources({**exact, key: value}, LIMITS)


class DependencyFakeBuild(DependencyCase):
    def inspection(self):
        programs = {name: {'path': '/admitted/' + name}
                    for name in ('cmake', 'ninja', 'c', 'cxx', 'archiver', 'ranlib')}
        host = {'programs': {name: {'path': '/admitted/' + name}
                             for name in ('make', 'sh', 'perl', 'python', 'gperf', 'pkg_config')}}
        font = self.f.file('fake-inputs/font.ttf', b'Inert synthetic font bytes.\n')
        notice = self.f.file('fake-inputs/NOTICE', b'Original synthetic dependency notice.\n')
        notice_ref = {'path': str(notice), 'sha256': digest(notice.read_bytes())}
        return types.SimpleNamespace(protected_paths=(), archives={}, repository_root=ROOT,
            toolchain={'tools': programs, 'toolchain_file': '/admitted/toolchain.cmake',
                       'runtime': {'sysroot_inventory': 'runtime'},
                       'inventories': {'runtime': {'root': '/admitted/sysroot'}}}, host_tools=host,
            assets={'font_config': {'path': '/admitted/fonts.conf'},
                    'icu_data': {'path': '/admitted/icu.dat'}, 'ca_bundle': {'path': '/admitted/ca.pem'},
                    'fonts': [{'path': str(font)}], 'notices': [notice_ref]}, notices=[notice_ref],
            phase_limits=copy.deepcopy(LIMITS), profile={'cmake_inputs': []},
            inputs=self.api.native_inputs.InputSet(), recheck=mock.Mock())

    def build_fake(self, inspection, output, run, *, final_error=None):
        # Test real cache generation and build orchestration, but no recipe or program execution.
        cache = self.api.cache_values(inspection, output)
        inspection.profile['cmake_inputs'] = [name for name in cache if name not in self.api.PRIVATE_CMAKE_INPUTS]
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(self.api.sys, 'platform', 'linux'))
        stack.enter_context(mock.patch.object(self.api, 'verify_plan', return_value=(inspection, {})))
        stack.enter_context(mock.patch.object(self.api, 'admit_controller',
                                              return_value=copy.deepcopy(SYNTHETIC_CONTROLLER)))
        stack.enter_context(mock.patch.object(self.api, 'RECIPE_FILES', ()))
        stack.enter_context(mock.patch.object(self.api.native_inputs, 'render_environment', return_value={'PATH': '/admitted'}))
        stack.enter_context(mock.patch.object(self.api, 'run_owned', side_effect=run))
        final = stack.enter_context(mock.patch.object(self.api, '_prefix_manifest',
            return_value={'fixture': True}, side_effect=final_error))
        return self.api.build(self.f.root / 'plan.json', PIN, output), final

    def test_build_uses_exact_cmake_ninja_graph_target_serial_outer_jobs_and_private_environment(self):
        inspection = self.inspection()
        output, calls = self.f.root / 'build', []
        def run(argv, cwd, log, environment, limits, **kwargs):
            calls.append((argv, cwd, environment, limits, kwargs))
            return {'phase': kwargs['phase'], 'exit_code': 0}
        result, final = self.build_fake(inspection, output, run)
        self.assertEqual(result, {'fixture': True})
        self.assertEqual(calls[0][0], ['/admitted/cmake', '-S', str(output / 'recipe'), '-B',
            str(output / 'graph'), '-G', 'Ninja', '-C', str(output / 'inputs.cmake'),
            '-DCMAKE_MAKE_PROGRAM=/admitted/ninja'])
        self.assertEqual(calls[1][0], ['/admitted/cmake', '--build', str(output / 'graph'),
            '--parallel', '1', '--target', 'native-dependencies'])
        environment = calls[0][2]
        self.assertEqual(environment['HOME'], str(output / 'home'))
        self.assertEqual(environment['TMPDIR'], str(output / 'tmp'))
        self.assertEqual(environment['CMAKE_BUILD_PARALLEL_LEVEL'], '4')
        self.assertEqual(environment['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(environment['PYTHONNOUSERSITE'], '1')
        self.assertEqual(environment['PKG_CONFIG_PATH'], '')
        self.assertEqual(environment['PKG_CONFIG_LIBDIR'], str(output / 'prefix/lib/pkgconfig'))
        self.assertEqual(len(calls), 2)
        inspection.recheck.assert_called_once()
        final.assert_called_once()
        self.assertEqual(calls[1][4]['absolute_deadline'], final.call_args.kwargs['build_deadline'])
        self.assertEqual(final.call_args.kwargs['controller'], SYNTHETIC_CONTROLLER)
        self.assertNotIn('absolute_deadline', calls[0][4])
        self.assertFalse((output / 'failure.json').exists())

    def test_build_failed_configure_or_build_never_publishes_dependencies_manifest(self):
        for failed_phase in ('configure', 'build'):
            inspection = self.inspection()
            output = self.f.root / failed_phase
            calls = []
            def run(argv, cwd, log, environment, limits, **kwargs):
                calls.append(kwargs['phase'])
                if kwargs['phase'] == failed_phase:
                    raise ValueError('synthetic ' + failed_phase + ' failure')
                return {'phase': kwargs['phase'], 'exit_code': 0}
            with self.subTest(phase=failed_phase), self.assertRaisesRegex(ValueError, 'synthetic'):
                self.build_fake(inspection, output, run)
            failure = json.loads((output / 'failure.json').read_bytes())
            self.assertTrue(failure['failed'])
            self.assertIs(failure['production_eligible'], False)
            self.assertFalse((output / 'dependencies.json').exists())
            self.assertFalse((output / 'build-receipt.json').exists())
            self.assertEqual(calls, ['configure'] if failed_phase == 'configure' else ['configure', 'build'])

    def test_build_changed_inputs_fail_before_any_fake_launch_or_publication(self):
        inspection = self.inspection()
        inspection.recheck.side_effect = ValueError('changed admitted input')
        output = self.f.root / 'changed'
        run = mock.Mock()
        with self.assertRaisesRegex(ValueError, 'changed admitted input'):
            self.build_fake(inspection, output, run)
        run.assert_not_called()
        self.assertFalse((output / 'dependencies.json').exists())
        self.assertTrue((output / 'failure.json').exists())

    def test_failed_final_inspection_retains_failure_without_publishing_dependency_input(self):
        inspection = self.inspection()
        output = self.f.root / 'final-inspection-failure'
        run = mock.Mock(return_value={'exit_code': 0})
        with self.assertRaisesRegex(ValueError, 'synthetic missing static archive'):
            self.build_fake(inspection, output, run,
                            final_error=ValueError('synthetic missing static archive'))
        failure = json.loads((output / 'failure.json').read_bytes())
        self.assertEqual(len(failure['completed_commands']), 2)
        self.assertFalse((output / 'dependencies.json').exists())
        self.assertFalse((output / 'build-receipt.json').exists())
        self.assertIs(failure['production_eligible'], False)

    def test_missing_explicit_make_is_rejected_before_any_program_fallback(self):
        inspection = self.inspection()
        del inspection.host_tools['programs']['make']
        with self.assertRaisesRegex(ValueError, 'admitted program: make'):
            self.api.cache_values(inspection, self.f.root / 'output')

    def test_cache_paths_used_by_make_are_restricted_literal_shell_words(self):
        for path in ('/inert/with space', '/inert/amp&ersand', '/inert/command`x`',
                     '/inert/a|b', '/inert/(subshell)', 'relative/path'):
            for role in ('output', 'sysroot', 'program'):
                inspection = self.inspection()
                output = self.f.root / 'output'
                if role == 'output':
                    output = path
                elif role == 'sysroot':
                    inspection.toolchain['inventories']['runtime']['root'] = path
                else:
                    inspection.host_tools['programs']['make']['path'] = path
                with self.subTest(path=path, role=role), self.assertRaises(ValueError):
                    self.api.cache_values(inspection, output)
        valid = self.api.cache_values(self.inspection(), self.f.root / 'output')
        self.assertEqual(valid['NATIVE_C_FLAGS'],
                         '-fPIC -march=x86-64 -mtune=generic --sysroot=/admitted/sysroot')
        self.assertEqual(valid['NATIVE_CXX_FLAGS'], valid['NATIVE_C_FLAGS'])


class DependencyController(DependencyCase):
    def inspection(self, *, program_path=None):
        actual = str(Path(sys.executable).resolve())
        program = {'path': actual if program_path is None else program_path,
                   'sha256': '2' * 64, 'version': 'SYNTHETIC-version-only'}
        runtime = {'runtime': 'SYNTHETIC-python-runtime-only', 'root': '/SYNTHETIC/modules',
                   'inventory': {'path': '/SYNTHETIC/modules.json', 'sha256': '3' * 64}}
        return types.SimpleNamespace(host_tools={'programs': {'python': program},
                                                 'module_inventories': {'python': runtime}})

    def test_matching_actual_controller_retains_program_and_module_identity_without_launch(self):
        inspected = self.inspection()
        with mock.patch.object(self.api.sys, 'dont_write_bytecode', True), \
                mock.patch.object(self.api.process_tree, 'launch') as launch:
            record = self.api.admit_controller(inspected)
        launch.assert_not_called()
        self.assertEqual(record, {
            'kind': 'admitted-native-dependency-build-controller-v1',
            'path': str(Path(sys.executable).resolve()), 'sha256': '2' * 64,
            'declared_version': 'SYNTHETIC-version-only', 'bytecode_disabled': True,
            'runtime': 'SYNTHETIC-python-runtime-only',
            'module_inventory': {'root': '/SYNTHETIC/modules',
                'inventory': {'path': '/SYNTHETIC/modules.json', 'sha256': '3' * 64}}})

    def test_sdk_controller_retains_original_interpreter_binding_without_legacy_module_lookup(self):
        inspected = self.inspection()
        inspected.host_tools.update(kind='foundation-native-engine-prototype-sdk-host-tools-v1',
            module_inventories={}, interpreter_runtimes={'python': {'scope': 'SYNTHETIC-original-runtime'}},
            interpreter_bindings={'python': {'path': 'original-python.json', 'sha256': PIN}})
        with mock.patch.object(self.api.sys, 'dont_write_bytecode', True), \
                mock.patch.object(self.api.process_tree, 'launch') as launch:
            record = self.api.admit_controller(inspected)
        launch.assert_not_called()
        self.assertEqual(record['runtime'], {'scope': 'SYNTHETIC-original-runtime'})
        self.assertEqual(record['interpreter_binding'], inspected.host_tools['interpreter_bindings']['python'])
        self.assertNotIn('module_inventory', record)

    def test_mismatched_controller_build_fails_before_output_or_any_program(self):
        inspected = self.inspection(program_path='/SYNTHETIC/different-python')
        output = self.f.root / 'rejected-controller'
        with mock.patch.object(self.api.sys, 'platform', 'linux'), \
                mock.patch.object(self.api.sys, 'dont_write_bytecode', True), \
                mock.patch.object(self.api, 'verify_plan', return_value=(inspected, {})), \
                mock.patch.object(self.api, 'fresh_output') as fresh, \
                mock.patch.object(self.api, 'run_owned') as run, \
                mock.patch.object(self.api.process_tree, 'launch') as launch, \
                self.assertRaisesRegex(ValueError, 'controller differs.*admitted host Python') as failure:
            self.api.build(self.f.root / 'plan.json', PIN, output)
        self.assertIn('PYTHON=/SYNTHETIC/different-python', str(failure.exception))
        self.assertIn('PYTHONDONTWRITEBYTECODE=1', str(failure.exception))
        fresh.assert_not_called()
        run.assert_not_called()
        launch.assert_not_called()
        self.assertFalse(output.exists())

    def test_bytecode_enabled_controller_build_fails_before_output_or_any_program(self):
        inspected = self.inspection()
        output = self.f.root / 'rejected-bytecode'
        with mock.patch.object(self.api.sys, 'platform', 'linux'), \
                mock.patch.object(self.api.sys, 'dont_write_bytecode', False), \
                mock.patch.object(self.api, 'verify_plan', return_value=(inspected, {})), \
                mock.patch.object(self.api, 'fresh_output') as fresh, \
                mock.patch.object(self.api, 'run_owned') as run, \
                mock.patch.object(self.api.process_tree, 'launch') as launch, \
                self.assertRaisesRegex(ValueError, 'PYTHONDONTWRITEBYTECODE=1'):
            self.api.build(self.f.root / 'plan.json', PIN, output)
        fresh.assert_not_called()
        run.assert_not_called()
        launch.assert_not_called()
        self.assertFalse(output.exists())


class DependencyPrefixHandoff(DependencyCase):
    def normalize_owned_prefix_directories(self, prefix):
        """Model the retained prefix modes without depending on ambient umask."""
        prefix.relative_to(self.f.root)
        self.assertNotEqual(prefix, self.f.root)
        prefix.mkdir(parents=True, exist_ok=True, mode=0o755)
        for path in [prefix, *prefix.rglob('*')]:
            self.assertFalse(path.is_symlink())
            if path.is_dir():
                path.chmod(0o755)

    def prefix_fixture(self):
        profile = self.api.load_profile()
        output = self.f.root / 'candidate'
        output.mkdir()
        for directory in ('home', 'tmp'):
            (output / directory).mkdir()
        self.f.file('candidate/inputs.cmake', b'# Inert fake graph input.\n')
        archive_bytes = inert_native_archive()
        for declaration in profile['libraries'].values():
            self.f.file('candidate/prefix/' + declaration['archive'], archive_bytes)
            for directory in declaration['includes']:
                (output / 'prefix' / directory).mkdir(parents=True, exist_ok=True, mode=0o755)
        for name in profile['pkg_config']:
            self.f.file('candidate/prefix/' + name, b'Name: inert fixture\nVersion: 1\n')
        self.normalize_owned_prefix_directories(output / 'prefix')
        self.f.file('candidate/components/' + profile['pic_check']['output'], inert_native_dso())
        link_argv = ['/inert/cxx', '-shared', *profile['pic_check']['link_options'],
                     '-o', str(output / 'components' / profile['pic_check']['output']), '-Wl,--whole-archive']
        ordered_paths = [str(output / 'prefix' / profile['libraries'][name]['archive'])
                         for name in profile['pic_check']['ordered_libraries']]
        link_argv.extend(ordered_paths)
        link_argv.extend(['-Wl,--no-whole-archive', '-pthread', '-lm', '-ldl', '-lrt', '-latomic'])
        self.f.file('candidate/components/pic/pic-commands.log', (' '.join(link_argv) + '\n').encode('ascii'))
        self.f.file('candidate/components/pic/ordered-archives.txt', ('\n'.join(ordered_paths) + '\n').encode('ascii'))
        notice_path = self.f.file('original/NOTICE', b'Original synthetic asset notice.\n')
        source_notice = self.f.file('source/NOTICE', b'Original distinct synthetic source notice.\n')
        notice = {'path': 'NOTICE', 'sha256': digest(notice_path.read_bytes())}
        def asset(name):
            path = self.f.file('original/' + name, b'inert retained asset\n')
            return {'path': name, 'sha256': digest(path.read_bytes()), 'bytes': len(path.read_bytes()),
                    'mode': 0o644, 'origin': {'repository': 'synthetic-fixture', 'revision': 'fixture-v1'},
                    'notice': notice}
        asset_doc = {'schema_version': 1, 'kind': 'foundation-native-engine-prototype-assets-v1',
                     'fonts': [asset('font.ttf')], 'font_config': asset('fonts.conf'),
                     'icu_data': asset('icu.dat'), 'ca_bundle': asset('ca.pem'), 'notices': [notice],
                     'initialization': {'policy': 'explicit-retained-assets-only', 'font_search': 'retained-only',
                                        'icu_search': 'retained-only', 'network': False}}
        asset_ref = self.f.document('original/assets.json', asset_doc)
        parsed_assets = self.api.native_inputs.parse_assets(asset_doc, self.f.root / 'original',
                                                           self.api.native_inputs.InputSet(), TARGET)
        toolchain = {'identity': {'identity_sha256': '2' * 64},
                     'tools': {'inspect': {'path': '/inert/readelf', 'sha256': '3' * 64},
                               'cxx': {'path': '/inert/cxx', 'sha256': '4' * 64}},
                     'runtime': {'policy': 'synthetic-test-runtime', 'needed_libraries': ['libc.so.6']}}
        inspected = types.SimpleNamespace(profile=profile, toolchain=toolchain, host_tools={},
            phase_limits=LIMITS, selection={'assets': asset_ref},
            selection_path=self.f.file('selection.json', b'{}\n'), assets=parsed_assets,
            notices=[{'path': str(source_notice), 'sha256': digest(source_notice.read_bytes())}],
            inputs=self.api.native_inputs.InputSet(),
            recheck=mock.Mock(), as_dict=mock.Mock(return_value={'scope': 'synthetic-fixture-only'}))
        return profile, output, inspected, asset_ref, notice, source_notice

    def test_completed_fake_prefix_passes_actual_consumer_with_original_assets_and_inspection_logs(self):
        """Exercise the real producer/consumer contract around 22 tiny ar files."""
        profile, output, inspected, asset_ref, notice, source_notice = self.prefix_fixture()
        commands = []
        def fake_inspection(argv, cwd, log, environment, limits, **kwargs):
            self.assertEqual(argv[0], '/inert/readelf')
            self.assertEqual(environment['PYTHONDONTWRITEBYTECODE'], '1')
            self.assertEqual(environment['PYTHONNOUSERSITE'], '1')
            self.assertEqual(kwargs['phase'], 'inspection')
            self.assertEqual(kwargs['absolute_deadline'], 1000000000000)
            raw = (b'  Type: DYN (Shared object file)\n  0x0001 (NEEDED) Shared library: [libc.so.6]\n'
                   if '-d' in argv else b'Inert fake inspector completed; no program ran.\n')
            self.api.save(log, raw)
            return {'phase': 'inspection', 'exit_code': 0, 'process_tree_closed': True}
        with mock.patch.object(self.api.native_inputs, 'render_environment', return_value={'PATH': '/inert'}), \
                mock.patch.object(self.api, 'run_owned', side_effect=fake_inspection) as run:
            produced = self.api._prefix_manifest(inspected, output, commands, PIN, {},
                controller=copy.deepcopy(SYNTHETIC_CONTROLLER), build_deadline=1000000000000)
        self.assertEqual(run.call_count, 23)
        self.assertEqual(len(commands), 23)
        self.assertEqual(set(produced['libraries']), self.api.native_inputs.LIBRARIES)
        self.assertEqual(set(produced['pkg_config']['files']), set(profile['pkg_config']))
        self.assertEqual(produced['pkg_config']['directories'], ['lib/pkgconfig'])
        self.assertEqual(produced['assets']['sha256'], asset_ref['sha256'])
        self.assertEqual({entry['sha256'] for entry in produced['notices']},
                         {notice['sha256'], digest(source_notice.read_bytes())})
        self.assertEqual(json.loads((output / 'dependencies.json').read_bytes()), produced)
        copied = output / produced['assets']['path']
        self.assertEqual(copied.read_bytes(), (self.f.root / asset_ref['path']).read_bytes())
        copied_inputs = self.api.native_inputs.InputSet()
        copied_assets = self.api.native_inputs.parse_assets(
            self.api.document(copied, produced['assets']['sha256']), copied.parent, copied_inputs, TARGET)
        copied_inputs.recheck()
        self.assertEqual(Path(copied_assets['fonts'][0]['path']).read_bytes(), b'inert retained asset\n')
        self.assertEqual(Path(copied_assets['icu_data']['path']).read_bytes(), b'inert retained asset\n')
        inputs = self.api.native_inputs.InputSet()
        consumed = self.api.native_inputs.parse_dependencies(produced, output, inputs,
                                                            TARGET, inspected.toolchain, asset_ref)
        inputs.recheck()
        self.assertEqual(len(consumed['libraries']), 22)
        self.assertEqual(consumed['libraries']['WebP::libwebp']['byte_inspection']['members'], 1)
        for library in consumed['libraries'].values():
            inspection_path = Path(library['inspection']['path'])
            self.assertTrue((inspection_path.parent / 'archive.log').is_file())
            self.assertTrue((inspection_path.parent / 'pic-check.log').is_file())
        receipt = json.loads((output / 'build-receipt.json').read_bytes())
        self.assertIs(receipt['production_eligible'], False)
        self.assertIs(receipt['engine_execution'], False)
        self.assertIs(receipt['kernel_rebuild'], False)
        self.assertEqual(receipt['build_controller'], SYNTHETIC_CONTROLLER)
        self.assertIs(receipt['pic_shared_link']['dso_loaded_or_executed'], False)
        self.assertEqual(len(receipt['pic_shared_link']['ordered_archives']), 22)
        inspected.recheck.assert_called_once_with()

    def test_missing_pic_dso_blocks_dependency_manifest_before_any_inspector_launch(self):
        profile, output, inspected, *_ = self.prefix_fixture()
        (output / 'components' / profile['pic_check']['output']).unlink()
        with mock.patch.object(self.api.native_inputs, 'render_environment', return_value={}), \
                mock.patch.object(self.api, 'run_owned') as run, self.assertRaises(OSError):
            self.api._prefix_manifest(inspected, output, [], PIN, {},
                                      controller=copy.deepcopy(SYNTHETIC_CONTROLLER))
        run.assert_not_called()
        self.assertFalse((output / 'dependencies.json').exists())
        self.assertFalse((output / 'build-receipt.json').exists())

    def test_pic_inspector_output_requires_dyn_explicit_runtime_and_no_textrel(self):
        good = b'  Type: DYN (Shared object file)\n  0x0001 (NEEDED) Shared library: [libc.so.6]\n'
        self.assertEqual(self.api.verify_pic_output(good, ['libc.so.6']), ['libc.so.6'])
        for raw in (good.replace(b'DYN', b'REL'), good + b'  0x0016 (TEXTREL) 0x0\n',
                    good + b'  0x001e (FLAGS) TEXTREL\n', good.replace(b'libc.so.6', b'libunadmitted.so'),
                    b'Type: DYN\n', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.api.verify_pic_output(raw, ['libc.so.6'])

    def test_pic_command_requires_ordered_archives_inside_actual_shared_output_link(self):
        profile, output, inspected, *_ = self.prefix_fixture()
        command_log = output / 'components/pic/pic-commands.log'
        original = command_log.read_text()
        archives = [str(output / 'prefix' / profile['libraries'][name]['archive'])
                    for name in profile['pic_check']['ordered_libraries']]
        prematurely_closed = original.replace(' -Wl,--no-whole-archive', '').replace(
            '-Wl,--whole-archive', '-Wl,--whole-archive -Wl,--no-whole-archive')
        mutations = {'omitted-archive': original.replace(archives[0], ''),
                     'reordered-archive': original.replace(archives[0], '@FIRST@')
                         .replace(archives[1], archives[0]).replace('@FIRST@', archives[1]),
                     'archives-outside-whole-archive': prematurely_closed,
                     'not-shared': original.replace(' -shared ', ' '),
                     'wrong-output': original.replace(str(output / 'components' / profile['pic_check']['output']),
                                                       str(output / 'components/pic/wrong.so'))}
        for label, mutated in mutations.items():
            command_log.write_text(mutated)
            with self.subTest(mutation=label), mock.patch.object(self.api, 'run_owned') as run, \
                    self.assertRaises(ValueError):
                self.api._pic_receipt(inspected, output, {}, [], None)
            run.assert_not_called()

    def test_expired_final_publication_never_creates_admissible_dependency_manifest(self):
        output = self.f.root / 'expired-prefix'
        output.mkdir()
        self.f.file('expired-prefix/prefix/include/inert.h')
        self.normalize_owned_prefix_directories(output / 'prefix')
        self.f.file('expired-prefix/inputs.cmake', b'# inert\n')
        # The mocked asset copier normally creates this owned retained parent.
        (output / 'retained').mkdir(mode=0o755)
        inspected = types.SimpleNamespace(profile={'libraries': {}, 'pkg_config': {}},
            toolchain={'tools': {'inspect': {'path': '/inert/readelf', 'sha256': PIN}},
                       'identity': {'identity_sha256': PIN}}, host_tools={}, phase_limits=LIMITS,
            inputs=self.api.native_inputs.InputSet(),
            notices=[], assets={'notices': []}, recheck=mock.Mock(), as_dict=mock.Mock(return_value={}))
        inventory = self.api.bounded_inventory(output / 'prefix', LIMITS)
        with mock.patch.object(self.api.native_inputs, 'render_environment', return_value={}), \
                mock.patch.object(self.api, '_copy_asset_input', return_value={'path': 'not-published', 'sha256': PIN}), \
                mock.patch.object(self.api, '_pic_receipt', return_value=({}, {}, b'', [])), \
                mock.patch.object(self.api, 'bounded_inventory', return_value=inventory), \
                mock.patch.object(self.api.time, 'monotonic', return_value=10), \
                mock.patch.object(self.api, 'run_owned') as run, \
                self.assertRaisesRegex(ValueError, 'final publication wall deadline'):
            self.api._prefix_manifest(inspected, output, [], PIN, {},
                controller=copy.deepcopy(SYNTHETIC_CONTROLLER), build_deadline=10)
        run.assert_not_called()
        self.assertFalse((output / 'dependencies.json').exists())

    def test_bounded_prefix_inventory_rejects_expired_deadline_before_reading_members(self):
        prefix = self.f.root / 'bounded-prefix'
        self.f.file('bounded-prefix/include/inert.h', b'inert header\n')
        self.normalize_owned_prefix_directories(prefix)
        with mock.patch.object(self.api.time, 'monotonic', return_value=10), \
                self.assertRaisesRegex(ValueError, 'deadline'):
            self.api.bounded_inventory(prefix, LIMITS, deadline=10)


class DependencyPrivateRuntime(DependencyCase):
    def fixture(self):
        # Parsed-like synthetic selection: this does not call the SDK parser or
        # pretend these inert role bytes are compiler-produced runtime objects.
        profile, output, inspected, *_ = DependencyPrefixHandoff.prefix_fixture(self)
        inspected.repository_root = ROOT
        self.api._producer_inputs(inspected.inputs, ROOT)
        selection = self.f.file('private-selection.json', b'{"scope":"SYNTHETIC-runtime-only"}\n')
        record = inspected.inputs.file(selection, digest(selection.read_bytes()), 'synthetic private selection')
        values = {'BIB_NATIVE_RUNTIME_COMPILER_TRIPLE': TARGET['triple'],
            'BIB_NATIVE_RUNTIME_POLICY_SHA256': self.api.PRIVATE_POLICY_SHA256,
            'BIB_NATIVE_RUNTIME_SELECTION_PATH': str(selection),
            'BIB_NATIVE_RUNTIME_SELECTION_SHA256': record['sha256']}
        names = ('libstdc++.a', 'libgcc.a', 'libgcc_eh.a', 'crtbeginS.o', 'crtendS.o')
        for role, name in zip(self.api.PRIVATE_ROLE_NAMES, names):
            path = self.f.file('selected/' + name, b'SYNTHETIC-runtime-input-not-code\n')
            captured = inspected.inputs.file(path, digest(path.read_bytes()), 'synthetic selected runtime')
            values['BIB_NATIVE_RUNTIME_' + role + '_PATH'] = str(path)
            values['BIB_NATIVE_RUNTIME_' + role + '_SHA256'] = captured['sha256']
        inspected.toolchain.update(kind=self.api.PRIVATE_KIND, private_runtime={'cmake': values, 'record': record})
        inspected.toolchain['tools']['cmake'] = {'path': '/inert/cmake', 'sha256': '5' * 64}
        self.api.stage_private_sources(inspected, output)
        private = self.api.private_cache_values(inspected, output)
        paths = [private['BIB_NATIVE_RUNTIME_' + role + '_PATH'] for role in self.api.PRIVATE_ROLE_NAMES]
        trace = ('\n'.join(paths + [paths[1]]) + '\n').encode('ascii')
        self.f.file('candidate/logs/build.log', trace)
        self.f.file('candidate/components/pic/evidence/dependency-runtime-link.map', trace)
        self.f.file('candidate/components/pic/dependencies-pic.exports.map', self.api.PRIVATE_EXPORT_RAW)
        command = output / 'components/pic/pic-commands.log'
        command.write_text(command.read_text().rstrip() + ' -static-libstdc++ -static-libgcc'
            + ' -Wl,--exclude-libs,ALL -Wl,--trace -Wl,-Map,' + private['BIB_NATIVE_RUNTIME_LINK_MAP']
            + ' -Wl,--version-script,' + str(output / 'components/pic/dependencies-pic.exports.map') + '\n')
        return output, inspected, private

    normalize_owned_prefix_directories = DependencyPrefixHandoff.normalize_owned_prefix_directories

    def fake_inspector(self, *, corrupt=None):
        def run(argv, cwd, log, environment, limits, **kwargs):
            self.api.save(log, b'SYNTHETIC completed command; no program ran.\n')
            if argv[0] == '/inert/readelf':
                # Replace the fresh synthetic log, before it is consumed.
                log.unlink()
                self.api.save(log, b'Type: DYN\n(NEEDED) Shared library: [libc.so.6]\n')
            else:
                self.assertEqual(argv[0], '/inert/cmake')
                self.assertIn('-DBIB_NATIVE_PROTOTYPE_INSPECTION_KIND=dependencies-pic-v1', argv)
                folder = log.parent
                logs = [('symbols_sha256', 'provider-dynamic-symbols.txt'),
                        ('dynamic_sha256', 'provider-dynamic-section.txt'),
                        ('version_info_sha256', 'provider-version-info.txt')]
                shared = cwd / 'components/pic/libfoundation-native-dependencies-pic-check.so'
                receipt = {'schema_version': 1, 'kind': 'foundation-native-dependencies-private-pic-inspection-v1',
                    'scope': 'actual-linked-native-dependencies-private-pic-byte-inspection',
                    'artifact_sha256': digest(shared.read_bytes()), 'artifact_bytes': shared.stat().st_size,
                    'architecture': 'elf64-x86_64', 'exports': [self.api.PRIVATE_EXPORT],
                    'needed': ['libc.so.6'], 'inspect_tool_sha256': '3' * 64,
                    'private_runtime_policy_sha256': self.api.PRIVATE_POLICY_SHA256,
                    'production_eligible': False, 'engine_execution': False, 'kernel_rebuild': False}
                for field, name in logs:
                    self.api.save(folder / name, b'SYNTHETIC inspector output, not ELF evidence.\n')
                    receipt[field] = digest((folder / name).read_bytes())
                if corrupt:
                    corrupt(receipt, folder)
                self.api.save(folder / 'provider-inspection.json', receipt)
            return {'phase': kwargs['phase'], 'exit_code': 0, 'process_tree_closed': True}
        return run

    def test_private_cache_has_exact17_conditional_keys_fixed_paths_and_no_generic_fallback(self):
        output, inspected, values = self.fixture()
        self.assertEqual(set(values), set(self.api.PRIVATE_CMAKE_INPUTS))
        self.assertEqual(len(values), 17)
        self.assertEqual(values['BIB_NATIVE_RUNTIME_LINK_MAP'], str(output / 'components/pic/evidence/dependency-runtime-link.map'))
        self.assertEqual(values['NATIVE_PRIVATE_RUNTIME_HELPER'], str(output / 'private-runtime/native-private-runtime.cmake'))
        self.assertEqual(self.api.cache_names(inspected), inspected.profile['cmake_inputs'] + list(self.api.PRIVATE_CMAKE_INPUTS))
        inspected.toolchain.pop('private_runtime')
        with self.assertRaisesRegex(ValueError, 'no generic fallback'):
            self.api.private_cache_values(inspected, output)

    def test_private_cache_rejects_wrong_policy_triple_selection_and_unknown_key(self):
        output, inspected, _ = self.fixture()
        original = copy.deepcopy(inspected.toolchain['private_runtime']['cmake'])
        for name, value in (('BIB_NATIVE_RUNTIME_POLICY_SHA256', '1' * 64),
                ('BIB_NATIVE_RUNTIME_COMPILER_TRIPLE', 'x86_64-linux-gnu'),
                ('BIB_NATIVE_RUNTIME_SELECTION_SHA256', '2' * 64), ('UNKNOWN', 'value')):
            inspected.toolchain['private_runtime']['cmake'] = dict(original, **{name: value})
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.api.private_cache_values(inspected, output)

    def test_generic_kind_cannot_silently_acquire_private_semantics(self):
        _, inspected, _ = self.fixture()
        inspected.toolchain['kind'] = 'foundation-native-engine-prototype-toolchain-v1'
        with self.assertRaisesRegex(ValueError, 'cannot acquire'):
            self.api.private_runtime(inspected)

    def test_staged_runtime_sources_and_selection_match_original_captured_bytes(self):
        output, inspected, _ = self.fixture()
        for name in self.api.PRIVATE_SHARED_SOURCES:
            self.assertEqual((output / 'private-runtime' / Path(name).name).read_bytes(),
                             inspected.inputs.bytes(ROOT / name))
        runtime = inspected.toolchain['private_runtime']
        self.assertEqual((output / 'private-runtime/selection.json').read_bytes(),
                         inspected.inputs.bytes(runtime['record']['path']))

    def test_private_build_stages_bound_sources_and_conditional_cache_before_any_fake_launch(self):
        _, private, _ = self.fixture()
        inspected = DependencyFakeBuild.inspection(self)
        inspected.inputs = private.inputs
        inspected.toolchain.update(kind=self.api.PRIVATE_KIND, private_runtime=private.toolchain['private_runtime'])
        output = self.f.root / 'private-build'
        calls = []
        def run(argv, cwd, log, environment, limits, **kwargs):
            calls.append(argv)
            self.assertEqual((output / 'private-runtime/selection.json').read_bytes(),
                inspected.inputs.bytes(inspected.toolchain['private_runtime']['record']['path']))
            cache = (output / 'inputs.cmake').read_text()
            self.assertIn('set(NATIVE_PIC_RUNTIME_MODE [=[private-static-gcc-sdk-v1]=] CACHE INTERNAL "" FORCE)', cache)
            self.assertIn(str(output / 'components/pic/evidence/dependency-runtime-link.map'), cache)
            return {'phase': kwargs['phase'], 'exit_code': 0}
        result, _ = DependencyFakeBuild.build_fake(self, inspected, output, run)
        self.assertEqual(result, {'fixture': True})
        self.assertEqual(len(calls), 2)

    def test_captured_shared_checker_rejects_missing_foreign_and_shared_runtime_inputs(self):
        output, inspected, values = self.fixture()
        checker = self.api.private_link_verifier(inspected)
        trace, link_map = output / 'logs/build.log', Path(values['BIB_NATIVE_RUNTIME_LINK_MAP'])
        original = trace.read_bytes()
        joined = checker(values, trace, link_map)
        self.assertEqual(joined['selection_sha256'], values['BIB_NATIVE_RUNTIME_SELECTION_SHA256'])
        self.assertEqual(joined['evidence']['linker_input_trace']['sha256'], digest(original))
        for raw in (b'\n'.join(original.splitlines()[1:]) + b'\n',
                    original + b'/foreign/libgcc.a\n', original + b'/foreign/libstdc++.so.6\n'):
            trace.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                checker(values, trace, link_map)

    def test_captured_checker_rechecks_original_source_before_loading(self):
        output, inspected, _ = self.fixture()
        source = ROOT / self.api.PRIVATE_SHARED_SOURCES[-1]
        with mock.patch.object(inspected.inputs, 'bytes', side_effect=ValueError('original source changed')), \
                mock.patch.object(self.api, 'compile', create=True) as compile_source, \
                self.assertRaisesRegex(ValueError, 'original source changed'):
            self.api.private_link_verifier(inspected)
        compile_source.assert_not_called()

    def test_captured_checker_rechecks_source_after_loading(self):
        _, inspected, _ = self.fixture()
        source = ROOT / self.api.PRIVATE_SHARED_SOURCES[-1]
        raw = inspected.inputs.bytes(source)
        with mock.patch.object(inspected.inputs, 'bytes', side_effect=[raw, raw + b'\n']), \
                self.assertRaisesRegex(ValueError, 'changed while loading'):
            self.api.private_link_verifier(inspected)

    def test_private_link_command_rejects_each_missing_or_foreign_map_flag(self):
        output, inspected, values = self.fixture()
        raw = (output / 'components/pic/pic-commands.log').read_bytes()
        paths = [str(output / 'prefix' / inspected.profile['libraries'][name]['archive'])
                 for name in inspected.profile['pic_check']['ordered_libraries']]
        shared = output / 'components/pic/libfoundation-native-dependencies-pic-check.so'
        argv = self.api.verify_pic_commands(raw, '/inert/cxx', paths, shared, inspected.profile['pic_check']['link_options'])
        exports = output / 'components/pic/dependencies-pic.exports.map'
        self.api.verify_private_pic_command(argv, values, exports)
        for option in ('-static-libstdc++', '-static-libgcc', '-Wl,--exclude-libs,ALL', '-Wl,--trace',
                       '-Wl,-Map,' + values['BIB_NATIVE_RUNTIME_LINK_MAP'], '-Wl,--version-script,' + str(exports)):
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.api.verify_private_pic_command([item for item in argv if item != option], values, exports)
        with self.assertRaises(ValueError):
            self.api.verify_private_pic_command(argv + ['-Wl,-Map,/foreign/map'], values, exports)

    def test_private_pic_joins_all22_shared_checker_and_closed_elf_receipt_without_execution(self):
        output, inspected, _ = self.fixture()
        commands = []
        with mock.patch.object(self.api, 'run_owned', side_effect=self.fake_inspector()) as run:
            receipt, archives, _, _ = self.api._pic_receipt(inspected, output, {}, commands, 1000000000000)
        self.assertEqual(receipt['kind'], 'foundation-native-dependencies-private-pic-shared-link-v1')
        self.assertEqual(len(archives), 22)
        self.assertEqual(len(receipt['ordered_archives']), 22)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(len(commands), 2)
        self.assertIs(receipt['dso_loaded_or_executed'], False)
        private = receipt['private_runtime']
        self.assertEqual(private['export_map']['sha256'], digest(self.api.PRIVATE_EXPORT_RAW))
        self.assertEqual(private['selection_sha256'], inspected.toolchain['private_runtime']['record']['sha256'])
        self.assertEqual(json.loads((output / 'pic-check/receipt.json').read_bytes()), receipt)

    def test_private_pic_rejects_wrong_export_policy_artifact_and_inspection_log(self):
        mutations = {
            'extra-export': lambda value, folder: value['exports'].append('unexpected'),
            'provider-kind': lambda value, folder: value.update(kind='foundation-native-engine-prototype-provider-inspection-v1'),
            'wrong-policy': lambda value, folder: value.update(private_runtime_policy_sha256=PIN),
            'wrong-size': lambda value, folder: value.update(artifact_bytes=True),
            'foreign-needed': lambda value, folder: value['needed'].append('libstdc++.so.6'),
            'log-tamper': lambda value, folder: (folder / 'provider-dynamic-symbols.txt').write_bytes(b'tampered'),
            'false-claim': lambda value, folder: value.update(engine_execution=True)}
        # Separate temporary directories avoid reusing a failed evidence tree.
        for name, corrupt in mutations.items():
            with self.subTest(mutation=name), tempfile.TemporaryDirectory(prefix='native-private-negative-') as temp:
                old, self.f = self.f, TinyFiles(temp)
                try:
                    output, inspected, _ = self.fixture()
                    with mock.patch.object(self.api, 'run_owned', side_effect=self.fake_inspector(corrupt=corrupt)), \
                            self.assertRaises(ValueError):
                        self.api._pic_receipt(inspected, output, {}, [], 1000000000000)
                    self.assertFalse((output / 'pic-check/receipt.json').exists())
                    self.assertFalse((output / 'dependencies.json').exists())
                finally:
                    self.f = old

    def test_private_inspection_budget_exhaustion_fails_before_shared_checker_or_launch(self):
        output, inspected, _ = self.fixture()
        with mock.patch.object(self.api.time, 'monotonic', return_value=10), \
                mock.patch.object(self.api, 'private_link_verifier') as checker, \
                mock.patch.object(self.api, 'run_owned') as run, self.assertRaisesRegex(ValueError, '60-second'):
            self.api.private_pic_evidence(inspected, output, output / 'unused', PIN, {}, [], 69, expected_needed=[])
        checker.assert_not_called()
        run.assert_not_called()


class DependencyCommandLine(DependencyCase):
    def test_cli_dispatches_only_explicit_plan_or_build_with_independent_pins(self):
        for action, args, helper in (('plan', ['--selection', '/inert/selection.json',
                '--selection-sha256', PIN], 'make_plan'), ('build', ['--plan', '/inert/plan.json',
                '--plan-sha256', PIN], 'build')):
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(action=action), mock.patch.object(self.api, helper,
                    return_value={'scope': 'synthetic-only'}) as operation, \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                result = self.api.cli([action, *args, '--output', '/inert/output'])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue()), {'scope': 'synthetic-only'})
            self.assertEqual(stderr.getvalue(), '')
            operation.assert_called_once_with('/inert/' + ('selection.json' if action == 'plan' else 'plan.json'),
                                              PIN, '/inert/output')

    def test_cli_distinguishes_structured_missing_inputs_from_ordinary_failure(self):
        missing = self.api.native_inputs.MissingInputs([
            {'role': 'synthetic-toolchain', 'path': '/missing/fixture', 'reason': 'fixture-only'}])
        for error, code in ((missing, 2), (ValueError('synthetic invalid shape'), 1)):
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(error=error), mock.patch.object(self.api, 'main', side_effect=error), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(self.api.cli(['plan']), code)
            self.assertEqual(stdout.getvalue(), '')
            if code == 2:
                value = json.loads(stderr.getvalue())
                self.assertIs(value['executable_plan'], False)
                self.assertEqual(value['missing'][0]['role'], 'synthetic-toolchain')
            else:
                self.assertEqual(stderr.getvalue(), 'native-engine-dependencies: synthetic invalid shape\n')

    def test_cli_preserves_argparse_help_and_invalid_action_exit_status(self):
        for argv, expected in ((['--help'], 0), (['fetch'], 2), (['build'], 2)):
            with self.subTest(argv=argv), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                    mock.patch.object(self.api, 'make_plan') as plan, \
                    mock.patch.object(self.api, 'build') as build, self.assertRaises(SystemExit) as result:
                self.api.cli(argv)
            self.assertEqual(result.exception.code, expected)
            plan.assert_not_called()
            build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
