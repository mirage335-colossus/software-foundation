"""Native source/input and inert CMake policy tests; no engine is compiled."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HISTORY_SPEC = importlib.util.spec_from_file_location('native_popup_source_history', ROOT / 'tests/native_popup_source_history.py')
HISTORY = importlib.util.module_from_spec(HISTORY_SPEC)
HISTORY_SPEC.loader.exec_module(HISTORY)
native_popup_predecessor_bytes = HISTORY.native_popup_predecessor_bytes
native_popup_history = HISTORY.native_popup_history
RECIPE = ROOT / 'recipes/webkitwasm-native-v1'
SPEC = importlib.util.spec_from_file_location('native_source_inspection', RECIPE / 'inspect_sources.py')
INSPECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECT)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class NativeSourceInputs(unittest.TestCase):
    def fixture(self, root):
        recipe = root / INSPECT.RECIPE
        source = recipe / 'source/example.cpp'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'// Native source fixture; never compiled.\n')
        source.chmod(0o644)
        raw = source.read_bytes()
        return {'schema_version': 1, 'kind': 'foundation-native-engine-source-inputs',
                'scope': 'native-source-candidate-only', 'profile': 'pixel',
                'suppliers': {'wrapper': '68c618544e1f8af18ebce346281a6a49766aa194',
                              'engine': 'aec9d2ad958e716ab4bca4bf03007e6edac7323f'},
                'provenance': {}, 'requirements': INSPECT.REQUIREMENTS,
                'limits': INSPECT.LIMITS,
                'inputs': {'source/example.cpp': {
                    'tracked_path': source.relative_to(root).as_posix(), 'sha256': digest(raw),
                    'bytes': len(raw), 'mode': 0o644, 'role': 'source',
                    'origin': {'kind': 'inert-test-fixture'}}}}

    def inspect_fixture(self, root, manifest):
        raw = (json.dumps(manifest, sort_keys=True) + '\n').encode()
        (root / INSPECT.RECIPE / 'source-imports.json').write_bytes(raw)
        return INSPECT.inspect(root, digest(raw))

    def test_tracked_source_inventory_is_incomplete_native_candidate(self):
        raw = (RECIPE / 'source-imports.json').read_bytes()
        result = INSPECT.inspect(ROOT, digest(raw))
        self.assertEqual(result['scope'], 'native-source-input-integrity-only')
        self.assertFalse(result['production_eligible'])
        self.assertFalse(result['native_build_performed'])
        self.assertFalse(result['native_runtime_checks_passed'])
        self.assertFalse(result['kernel_rebuild_performed'])
        self.assertEqual(result['requirements'], INSPECT.REQUIREMENTS)

    def test_native_popup_types_successor_preserves_exact_pixel_catalogue_history(self):
        value=json.loads((RECIPE/'source-imports.json').read_bytes())
        historical=json.loads((ROOT/'recipes/webkitwasm-native-rich4083-v1/provenance/inputs/pixel-native-source-imports.json').read_bytes())
        self.assertEqual(value['kind'],INSPECT.NATIVE_POPUP_SOURCE_KIND)
        self.assertEqual(len(INSPECT.NATIVE_POPUP_SOURCE_FACTS),1)
        self.assertEqual(INSPECT.native_popup_catalogue_counts(value),{'files':len(historical['inputs'])})
        previous=INSPECT.native_popup_catalogue_predecessor(value)
        self.assertEqual({name:row for name,row in previous['inputs'].items() if name!='inspect_sources.py'},
            {name:row for name,row in historical['inputs'].items() if name!='inspect_sources.py'})
        leaf=next(iter(INSPECT.NATIVE_POPUP_SOURCE_FACTS))
        for mutation in ('source','prior','unrelated','narrow-budget','wide-budget'):
            changed=copy.deepcopy(value)
            if mutation=='source':changed['inputs'][leaf]['sha256']='f'*64
            elif mutation=='prior':changed['inputs'][leaf]['origin']['supersedes']['origin']['kind']='restamped'
            elif mutation=='unrelated':changed['inputs']['README.md']['sha256']='e'*64
            elif mutation=='narrow-budget':changed['limits']['maximum_entries']-=1
            else:changed['limits']['maximum_entries']+=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):INSPECT.native_popup_catalogue_counts(changed)

    def test_prior_platform_and_shared_pixel_identities_are_preserved(self):
        provenance = json.loads((RECIPE / 'provenance.json').read_text())
        self.assertEqual(len(provenance['native_platform_files']), 29)
        self.assertEqual(provenance['linux_selected_engine_files'], 20)
        self.assertEqual(provenance['windows_selected_engine_files'], 9)
        for record in provenance['native_platform_files']:
            self.assertEqual(digest((RECIPE / record['tracked_source']).read_bytes()),
                             record['after_sha256'])
        for logical, record in provenance['shared_pixel_files'].items():
            body = (ROOT / record['tracked_path']).read_bytes()
            self.assertEqual(digest(native_popup_predecessor_bytes(body)), record['sha256'])
            if record['origin'].get('selection') == 'unchanged':
                self.assertEqual(record['sha256'], record['origin']['sha256'])
        self.assertEqual(provenance['selected_notice_count'], 11)

    def test_native_runtime_uses_actual_shared_page_and_native_leaves(self):
        embedder = RECIPE / 'source/wrapper/src/embedder'
        runtime = (embedder / 'main.cpp').read_text()
        for required in ('BIB_ENGINE_PROVIDER_NATIVE', 'sizeof(void*) == 8',
                         'bibProviderCreatePage', 'appResourcesStartApplicationLoad',
                         'setScriptEnabled(true)', 'bib_engine_provider_set_timer_scheduler_v1'):
            self.assertIn(required, runtime)
        for forbidden in ('EM_ASM(', 'EM_JS(', '#include <emscripten',
                          'Original diagnostic embedder', 'int main('):
            self.assertNotIn(forbidden, runtime)
        idb = (embedder / 'BibIDBServer.cpp').read_text()
        self.assertIn('BIB_ENGINE_PROVIDER_NATIVE', idb)
        self.assertIn('BinarySemaphore semaphore;', idb)
        self.assertIn('semaphore.signal();', idb)
        self.assertIn('semaphore.wait();', idb)
        self.assertIn('bool g_mediaEnabled = false;', (embedder / 'BibNativeMediaDisabled.cpp').read_text())
        self.assertFalse((embedder / 'BibMediaPlayer.cpp').exists())
        self.assertFalse((embedder / 'BibNativeHost.h').exists())
        self.assertFalse((RECIPE / 'source/engine/Source/WTF/wtf/RunLoop.h').exists())
        self.assertFalse(list((RECIPE / 'source').rglob('*.js')))
        self.assertFalse(list((RECIPE / 'source').rglob('*.wasm')))

    def test_native_bootstrap_has_actual_one_shot_binding_and_windows_is_not_enabled(self):
        header = (RECIPE / 'source/native/BibNativeProviderBootstrap.hpp').read_text()
        self.assertIn('ensureNativeDocumentProviderBound() noexcept;', header)
        self.assertNotIn('return BIB_ENGINE_OK', header)
        binding = (RECIPE / 'source/document-provider/runtime/BibNativeDocumentBinding.cpp').read_text()
        once = (RECIPE / 'source/native/BibNativeProviderOnce.hpp').read_text()
        for text in ('ensureNativeDocumentProviderBound() noexcept', 'bindingOnce.ensure(',
                     'bind_engine_document_private(', 'M::build', 'M::retention',
                     'if (!owner(*static_cast<const State*>(raw))) return BIB_ENGINE_WRONG_THREAD;'):
            self.assertIn(text, binding)
        self.assertIn('compare_exchange_strong', once)
        self.assertIn('std::memory_order_release', once)
        self.assertIn('BIB_ENGINE_PROCESS_EXIT_REQUIRED', once)
        port = (RECIPE / 'source/engine/Source/cmake/OptionsFoundation.cmake').read_text()
        self.assertIn('NOT CMAKE_SYSTEM_NAME STREQUAL "Linux"', port)
        self.assertIn('Windows clang-cl and browser builds need their own qualified port', port)
        exports = (RECIPE / 'cmake/native-provider.exports').read_text()
        self.assertEqual(exports.count('bib_engine_get_provider_v1;'), 1)
        self.assertIn('local:', exports)
        self.assertTrue(exports.lstrip().startswith('{'))

    def test_fixture_reports_only_source_integrity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.inspect_fixture(root, self.fixture(root))
            self.assertEqual(result['files'], 1)
            self.assertFalse(result['production_eligible'])

    def test_changed_declared_source_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            (root / INSPECT.RECIPE / 'source/example.cpp').write_bytes(b'changed\n')
            with self.assertRaisesRegex(ValueError, 'differs from its inventory'):
                self.inspect_fixture(root, manifest)

    def test_unknown_source_leaf_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            (root / INSPECT.RECIPE / 'source/unreviewed.cpp').write_bytes(b'new\n')
            with self.assertRaisesRegex(ValueError, 'complete input inventory'):
                self.inspect_fixture(root, manifest)

    def test_source_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            source = root / INSPECT.RECIPE / 'source/example.cpp'
            target = root / 'target.cpp'
            source.rename(target)
            source.symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'not a regular file'):
                self.inspect_fixture(root, manifest)

    def test_empty_directory_chain_has_cumulative_namespace_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            directory = root / INSPECT.RECIPE / 'source'
            for _ in range(INSPECT.LIMITS['maximum_entries'] + 1):
                directory = directory / 'd'
                directory.mkdir()
            with self.assertRaisesRegex(ValueError, 'namespace exceeds its budget'):
                self.inspect_fixture(root, manifest)

    def test_path_escape_and_foreign_recipe_rejected(self):
        for path in ('../outside.cpp', '/absolute.cpp',
                     'recipes/another-recipe/source.cpp',
                     'recipes/webkitwasm-native-v1/source/con.cpp'):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = self.fixture(root)
                manifest['inputs']['source/example.cpp']['tracked_path'] = path
                with self.assertRaises(ValueError):
                    self.inspect_fixture(root, manifest)

    def test_unknown_fields_and_invalid_scalar_types_rejected(self):
        mutations = [lambda item: item.update(extra=True),
                     lambda item: item.update(schema_version=True),
                     lambda item: item.update(profile='editor'),
                     lambda item: item['inputs']['source/example.cpp'].update(mode=True),
                     lambda item: item['inputs']['source/example.cpp'].update(bytes=True),
                     lambda item: item['inputs']['source/example.cpp'].update(extra=True),
                     lambda item: item.update(requirements=[])]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = self.fixture(root)
                mutate(manifest)
                with self.assertRaises(ValueError):
                    self.inspect_fixture(root, manifest)

    def test_duplicate_json_and_wrong_independent_pin_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.fixture(root)
            self.inspect_fixture(root, manifest)
            with self.assertRaisesRegex(ValueError, 'independent pin'):
                INSPECT.inspect(root, '1' * 64)
            path = root / INSPECT.RECIPE / 'source-imports.json'
            raw = b'{"schema_version":1,"schema_version":1}\n'
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
                INSPECT.inspect(root, digest(raw))


class NativeProviderCMakePolicy(unittest.TestCase):
    def test_native_dso_policy_and_failures_without_compilers(self):
        graph_path = RECIPE / 'cmake/native-provider.cmake'
        graph = graph_path.read_text()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / 'inputs'
            prefix = directory / 'prefix'
            prefix.mkdir()
            mapping = {name: source / target for name, target in (
                ('_embedder', 'source/wrapper/src/embedder'),
                ('_document', 'source/document-provider'),
                ('_foundation', 'source/foundation'),
                ('_binding', 'source/provider-binding'), ('_engine', 'source/engine'))}
            for variable, suffix in re.findall(r'"\$\{(_embedder|_document|_foundation|_binding|_engine)\}([^"\n]*)"', graph):
                path = Path(str(mapping[variable]) + suffix)
                if suffix and path.suffix:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('// Inert source-selection input; never compiled.\n')
            binding = source / 'source/document-provider/runtime/BibNativeDocumentBinding.cpp'
            header = source / 'source/native/BibNativeProviderBootstrap.hpp'
            for path in (binding, header, source / 'source/native/BibNativeProviderOnce.hpp'):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('// Inert source-selection input; never compiled.\n')
            pin = digest(binding.read_bytes())
            expected = {'accept': None, 'windows': 'Windows native dependencies',
                        'binding-missing': 'native binding source',
                        'binding-pin': 'differs from its reviewed SHA256',
                        'dependency-target': 'same verified linux-x86_64',
                        'jit': 'ENABLE_JIT=OFF', 'non-pic': 'requires PIC WebCore'}
            for case, failure in expected.items():
                with self.subTest(case=case):
                    project, output = directory / case, directory / (case + '-output')
                    project.mkdir()
                    output.mkdir()
                    metadata = output / 'generated/NativeMetadata.h'
                    metadata.parent.mkdir()
                    metadata.write_bytes(binding.read_bytes())
                    log = output / 'target-calls.txt'
                    log.write_text('')
                    lines = ['cmake_minimum_required(VERSION 3.24)',
                             'project(NativeSourcePolicy LANGUAGES NONE)',
                             'set(PORT Foundation)', 'set(CMAKE_SYSTEM_NAME Linux)',
                             'set(CMAKE_SIZEOF_VOID_P 8)', 'set(WTF_CPU_X86_64 ON)',
                             'set(WTF_CPU_ARM64 OFF)']
                    for flag in ('ENABLE_STATIC_JSC', 'ENABLE_C_LOOP', 'USE_SYSTEM_MALLOC',
                                 'USE_SKIA', 'USE_SKIA_CPU_ONLY', 'USE_GENERIC_EVENT_LOOP'):
                        lines.append('set(' + flag + ' ON)')
                    for flag in ('ENABLE_JIT', 'ENABLE_DFG_JIT', 'ENABLE_FTL_JIT',
                                 'ENABLE_WEBASSEMBLY', 'ENABLE_REMOTE_INSPECTOR',
                                 'ENABLE_WEBGL', 'ENABLE_WEBGPU'):
                        lines.append('set(' + flag + ' OFF)')
                    settings = {'BIB_NATIVE_PROVIDER_SOURCE_ROOT': source,
                                'BIB_NATIVE_PROVIDER_DEPENDENCY_PREFIX': prefix,
                                'FOUNDATION_NATIVE_DEPENDENCY_PREFIX': prefix,
                                'BIB_NATIVE_PROVIDER_DEPENDENCY_TARGET': 'linux-x86_64',
                                'FOUNDATION_NATIVE_DEPENDENCY_TARGET': 'linux-x86_64',
                                'BIB_NATIVE_PROVIDER_BINDING_SOURCE': binding,
                                'BIB_NATIVE_PROVIDER_BINDING_SOURCE_SHA256': pin,
                                'BIB_NATIVE_PROVIDER_BINDING_HEADER': header,
                                'BIB_NATIVE_PROVIDER_BINDING_HEADER_SHA256': pin,
                                'BIB_NATIVE_PROVIDER_METADATA_HEADER': metadata,
                                'BIB_NATIVE_PROVIDER_METADATA_HEADER_SHA256': pin}
                    lines += [f'set({name} "{value.as_posix() if isinstance(value, Path) else value}")'
                              for name, value in settings.items()]
                    lines += ['add_library(WebCore INTERFACE)',
                              'add_library(JavaScriptCore INTERFACE)', 'add_library(WTF INTERFACE)',
                              'add_library(PAL INTERFACE)', 'add_library(FixtureSkia INTERFACE)',
                              'add_library(Skia::Skia ALIAS FixtureSkia)',
                              'add_library(Threads::Threads INTERFACE IMPORTED)',
                              f'set(WebCore_INCLUDE_DIRECTORIES "{source.as_posix()}/forwarding")',
                              f'set(WebCore_PRIVATE_INCLUDE_DIRECTORIES "{source.as_posix()}/private")']
                    if case == 'windows':
                        lines.append('set(CMAKE_SYSTEM_NAME Windows)')
                    elif case == 'binding-missing':
                        lines.append('set(BIB_NATIVE_PROVIDER_BINDING_SOURCE "")')
                    elif case == 'binding-pin':
                        lines.append('set(BIB_NATIVE_PROVIDER_BINDING_SOURCE_SHA256 "' + '1' * 64 + '")')
                    elif case == 'dependency-target':
                        lines.append('set(BIB_NATIVE_PROVIDER_DEPENDENCY_TARGET linux-aarch64)')
                    elif case == 'jit':
                        lines.append('set(ENABLE_JIT ON)')
                    elif case == 'non-pic':
                        lines = [line.replace('add_library(WebCore INTERFACE)',
                                              'add_library(WebCore STATIC "' + binding.as_posix() + '")')
                                 for line in lines]
                    # Only prerequisite INTERFACE libraries exist. Intercept the
                    # provider target and its toolchain-facing calls; nothing can
                    # compile or link and no C/C++ language is enabled.
                    lines += ['function(add_library)', 'add_custom_target(${ARGV0})',
                              f'file(APPEND "{log.as_posix()}" "add_library ${{ARGV}}\\n")', 'endfunction()']
                    for name in ('target_compile_features', 'target_compile_definitions',
                                 'target_include_directories', 'target_link_libraries', 'target_link_options'):
                        lines += [f'function({name})',
                                  f'file(APPEND "{log.as_posix()}" "{name} ${{ARGV}}\\n")', 'endfunction()']
                    lines += [f'include("{graph_path.as_posix()}")',
                              'get_property(_deps DIRECTORY PROPERTY CMAKE_CONFIGURE_DEPENDS)',
                              f'file(APPEND "{log.as_posix()}" "configure-depends ${{_deps}}\\n")']
                    (project / 'CMakeLists.txt').write_text('\n'.join(lines) + '\n')
                    run = subprocess.run(['cmake', '-S', str(project), '-B', str(output)],
                                         capture_output=True, text=True, timeout=30)
                    if failure:
                        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
                        self.assertIn(failure, ' '.join(run.stderr.split()))
                        self.assertEqual(log.read_text(), '')
                    else:
                        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                        calls = log.read_text()
                        self.assertIn('add_library BibNativeProvider;SHARED;EXCLUDE_FROM_ALL;', calls)
                        self.assertIn('BibNativeDocumentBinding.cpp', calls)
                        self.assertIn('BIB_ENGINE_PROVIDER_NATIVE=1', calls)
                        self.assertIn('configure-depends ', calls)
                        for excluded in ('BibMediaPlayer.cpp', 'BibEngineCopiedHost.cpp',
                                         'BibEngineDocumentWasmShim.cpp', 'BibNativeHost.cpp', '.js;'):
                            self.assertNotIn(excluded, calls)
                    cache = (output / 'CMakeCache.txt').read_text()
                    self.assertNotIn('CMAKE_CXX_COMPILER:', cache)
                    self.assertFalse(list(output.rglob('*.o')))
                    self.assertFalse(list(output.rglob('*.obj')))


if __name__ == '__main__':
    unittest.main()
