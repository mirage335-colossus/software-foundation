#!/usr/bin/env python3
"""Inert rich-native graph fixtures; no compiler, SDK or engine is configured.

CMake evaluates real target existence, aliases, paths and pins under LANGUAGES
NONE. Only INTERFACE prerequisites and an empty recording provider target exist.
A narrow recorder supplies explicitly ineligible WebCore TYPE/IMPORTED/PIC
properties to exercise the unchanged production gate without configuring an
engine or enabling a compiler. Source, metadata and admission data are ineligible.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from process_tree import launch

RECIPE = ROOT / 'recipes/webkitwasm-native-rich4083-v1'
GRAPH = RECIPE / 'cmake/native-provider.cmake'
RICH = (
    'physical/BibDocumentPhysicalProvider.cpp', 'key/NativeRawKeyDispatch.cpp',
    'key/NativeRawKeyMapping.cpp', 'portable/appended_engine_input_codec.cpp',
    'editor/BibNativeEditorBackend.cpp', 'editor/BibNativeEditorWireAdapter.cpp',
    'portable/native_editor_codec.cpp', 'portable/native_editor_projection.cpp',
    'portable/NativeDocumentActionsV1Codec.cpp',
)
UI_SOURCES = (
    'ui/BibEngineUiOwner.cpp', 'popup/BibNativePopupOwner.cpp',
    'popup/NativePopupController.cpp', 'clipboard/BibClipboardStore.cpp',
)
UI_HEADERS = (
    'ui/BibEngineUiOwner.hpp', 'popup/BibNativePopupOwner.hpp',
    'popup/BibNativePopupHooks.hpp', 'popup/NativePopupController.hpp',
    'clipboard/BibClipboardStore.hpp', 'clipboard/BibInternalClipboard.hpp',
)
ENABLED = ('ENABLE_STATIC_JSC', 'ENABLE_C_LOOP', 'USE_SYSTEM_MALLOC', 'USE_SKIA',
           'USE_SKIA_CPU_ONLY', 'USE_GENERIC_EVENT_LOOP')
DISABLED = ('ENABLE_JIT', 'ENABLE_DFG_JIT', 'ENABLE_FTL_JIT', 'ENABLE_WEBASSEMBLY',
            'ENABLE_REMOTE_INSPECTOR', 'ENABLE_WEBGL', 'ENABLE_WEBGPU')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quote(value):
    value = str(value)
    delimiter = '='
    while ']' + delimiter + ']' in value:
        delimiter += '='
    return '[' + delimiter + '[' + value + ']' + delimiter + ']'


RECORDER = r'''
function(record operation)
  file(APPEND "${FIXTURE_LOG}" "${operation}\t${ARGN}\n")
endfunction()
function(get_target_property output target property)
  if("${target}" STREQUAL "${INELIGIBLE_WEB_CORE_TARGET}" AND
      property MATCHES "^(TYPE|IMPORTED|POSITION_INDEPENDENT_CODE)$")
    if(property STREQUAL "TYPE")
      set(_value "${INELIGIBLE_WEB_CORE_TYPE}")
    elseif(property STREQUAL "IMPORTED")
      set(_value "${INELIGIBLE_WEB_CORE_IMPORTED}")
    else()
      set(_value "${INELIGIBLE_WEB_CORE_PIC}")
    endif()
    record(INELIGIBLE_WEB_CORE_SHAPE "${target}" "${property}" "${_value}")
  else()
    _get_target_property(_value "${target}" "${property}")
  endif()
  set(${output} "${_value}" PARENT_SCOPE)
endfunction()
function(add_library)
  if(NOT ARGV0 STREQUAL "BibNativeProvider")
    message(FATAL_ERROR "Unexpected target creation in inert fixture")
  endif()
  add_custom_target(BibNativeProvider)
  record(TARGET ${ARGV})
endfunction()
function(set_target_properties)
  record(PROPERTY ${ARGV})
endfunction()
function(set_property)
  if(ARGV0 STREQUAL "SOURCE")
    record(SOURCE_PROPERTY ${ARGV})
  else()
    _set_property(${ARGV})
  endif()
endfunction()
function(target_compile_features)
  record(FEATURE ${ARGV})
endfunction()
function(target_compile_definitions)
  record(DEFINITION ${ARGV})
endfunction()
function(target_include_directories)
  record(INCLUDE ${ARGV})
endfunction()
function(target_link_libraries)
  record(LINK ${ARGV})
endfunction()
function(target_link_options)
  record(LINK_OPTION ${ARGV})
endfunction()
function(find_package)
  message(FATAL_ERROR "Package discovery forbidden in inert fixture")
endfunction()
function(find_program)
  message(FATAL_ERROR "Program discovery forbidden in inert fixture")
endfunction()
function(execute_process)
  message(FATAL_ERROR "Subprocess execution forbidden in inert fixture")
endfunction()
function(enable_language)
  message(FATAL_ERROR "Compiler language forbidden in inert fixture")
endfunction()
'''


class NativeActionsGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected = os.environ.get('CMAKE_COMMAND') or shutil.which('cmake')
        if not selected:
            raise RuntimeError('CMake is required for the inert native graph fixtures')
        cls.cmake = Path(selected).resolve(strict=True)
        retained = os.environ.get('FOUNDATION_NATIVE_ACTIONS_CMAKE_TEST_ROOT')
        if retained:
            parent = Path(retained).resolve(strict=True)
            cls.directory = Path(tempfile.mkdtemp(prefix='fixtures-', dir=parent))
            cls.temporary = None
        else:
            cls.temporary = tempfile.TemporaryDirectory(prefix='native-actions-cmake-')
            cls.directory = Path(cls.temporary.name)
        cls.inputs = [GRAPH, RECIPE / 'cmake/native-provider.exports',
                      RECIPE / 'cmake/native-provider.def', Path(__file__),
                      ROOT / 'tools/process_tree.py']
        cls.pins = {str(path): digest(path) for path in cls.inputs}
        cls.cmake_pin = digest(cls.cmake)
        cls.deadline = time.monotonic() + 30
        cls.results = []

    @classmethod
    def tearDownClass(cls):
        same = all(digest(Path(path)) == pin for path, pin in cls.pins.items())
        same = same and digest(cls.cmake) == cls.cmake_pin
        summary = {
            'kind': 'ineligible-LANGUAGES-NONE-native-actions-graph-fixtures',
            'cases': cls.results, 'case_count': len(cls.results),
            'source_inputs': cls.pins, 'source_inputs_unchanged': same,
            'cmake': str(cls.cmake), 'cmake_sha256': cls.cmake_pin,
            'compiler_SDK_engine_or_native_runtime_executed': False,
            'target_property_representation': 'ineligible-recorded-WebCore-shapes',
            'production_eligible': False, 'whole_budget_seconds': 30,
        }
        (cls.directory / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
        if cls.temporary:
            cls.temporary.cleanup()
        if not same:
            raise AssertionError('Inert fixture source or CMake bytes changed during the run')

    def fixture(self, name, system='Linux', arm=False, alias=False, failure=None,
                webcore_type='STATIC_LIBRARY', webcore_imported=False):
        remaining = self.deadline - time.monotonic()
        self.assertGreater(remaining, 0, '30-second inert-fixture batch budget exhausted')
        directory = self.directory / name
        directory.mkdir()
        source, prefix = directory / 'inputs', directory / 'prefix'
        prefix.mkdir()
        mapping = {key: source / value for key, value in (
            ('_embedder', 'source/wrapper/src/embedder'),
            ('_document', 'source/document-provider'), ('_foundation', 'source/foundation'),
            ('_binding', 'source/provider-binding'), ('_engine', 'source/engine'), ('_root', ''))}
        for variable, suffix in re.findall(
                r'"\$\{(_embedder|_document|_foundation|_binding|_engine|_root)\}([^"\n]*)"',
                GRAPH.read_text()):
            path = Path(str(mapping[variable]) + suffix)
            if suffix and path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('// INELIGIBLE source-selection fixture; never compiled.\n')
        binding = source / 'source/document-provider/runtime/BibNativeDocumentActionsBinding.cpp'
        header = source / 'source/native/BibNativeProviderBootstrap.hpp'
        output = directory / 'output'
        output.mkdir()
        metadata = output / 'generated/NativeActionsMetadata.h'
        for path in (binding, header, metadata):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('// INELIGIBLE pinned fixture; no native metadata or implementation.\n')
        log = directory / 'calls.txt'
        log.write_text('')
        actual_webcore = 'FixtureWebCore' if alias else 'WebCore'
        target = 'windows-x86_64' if system == 'Windows' else 'linux-aarch64' if arm else 'linux-x86_64'
        settings = {
            'PORT': 'Foundation', 'CMAKE_SYSTEM_NAME': system, 'WIN32': system == 'Windows',
            'EMSCRIPTEN': False, 'CMAKE_SIZEOF_VOID_P': 8, 'WTF_CPU_X86_64': not arm,
            'WTF_CPU_ARM64': arm, 'CMAKE_CXX_STANDARD': 23,
            'CMAKE_MSVC_RUNTIME_LIBRARY': 'MultiThreaded', 'COMPILER_IS_CLANG_CL': True,
            'FOUNDATION_NATIVE_WINDOWS_INPUTS_ADMITTED': True,
            'BIB_NATIVE_PROVIDER_SOURCE_ROOT': source,
            'BIB_NATIVE_PROVIDER_DEPENDENCY_PREFIX': prefix,
            'FOUNDATION_NATIVE_DEPENDENCY_PREFIX': prefix,
            'BIB_NATIVE_PROVIDER_DEPENDENCY_TARGET': target,
            'FOUNDATION_NATIVE_DEPENDENCY_TARGET': target,
            'BIB_NATIVE_PROVIDER_BINDING_SOURCE': binding,
            'BIB_NATIVE_PROVIDER_BINDING_SOURCE_SHA256': digest(binding),
            'BIB_NATIVE_PROVIDER_BINDING_HEADER': header,
            'BIB_NATIVE_PROVIDER_BINDING_HEADER_SHA256': digest(header),
            'BIB_NATIVE_PROVIDER_METADATA_HEADER': metadata,
            'BIB_NATIVE_PROVIDER_METADATA_HEADER_SHA256': digest(metadata),
            'WebCore_INCLUDE_DIRECTORIES': source / 'forwarding',
            'WebCore_PRIVATE_INCLUDE_DIRECTORIES': source / 'private', 'FIXTURE_LOG': log,
            'INELIGIBLE_WEB_CORE_TARGET': actual_webcore,
            'INELIGIBLE_WEB_CORE_TYPE': webcore_type,
            'INELIGIBLE_WEB_CORE_IMPORTED': webcore_imported,
            'INELIGIBLE_WEB_CORE_PIC': name != 'non-pic',
            **{key: True for key in ENABLED}, **{key: False for key in DISABLED},
        }
        if name == 'wrong-pin':
            settings['BIB_NATIVE_PROVIDER_BINDING_SOURCE_SHA256'] = '1' * 64
        elif name == 'pixel-binding':
            wrong = binding.with_name('BibNativeDocumentBinding.cpp')
            wrong.write_bytes(binding.read_bytes())
            settings['BIB_NATIVE_PROVIDER_BINDING_SOURCE'] = wrong
        elif name == 'source-metadata':
            wrong = source / 'source/native/Generated.h'
            wrong.write_bytes(metadata.read_bytes())
            settings['BIB_NATIVE_PROVIDER_METADATA_HEADER'] = wrong
        elif name == 'missing-rich-source':
            (source / 'source/document-provider/editor/BibNativeEditorBackend.cpp').unlink()
        elif name == 'jit':
            settings['ENABLE_JIT'] = True
        elif name == 'windows-unadmitted':
            settings['FOUNDATION_NATIVE_WINDOWS_INPUTS_ADMITTED'] = False
        elif name == 'windows-dynamic-crt':
            settings['CMAKE_MSVC_RUNTIME_LIBRARY'] = 'MultiThreadedDLL'
        elif name == 'wasm':
            settings['EMSCRIPTEN'] = True
        elif name == 'dependency-target':
            settings['BIB_NATIVE_PROVIDER_DEPENDENCY_TARGET'] = 'linux-aarch64'
        elif name == 'hidden-loop':
            settings['USE_WINDOWS_EVENT_LOOP'] = True
        lines = ['cmake_minimum_required(VERSION 3.24)',
                 'project(IneligibleNativeActionsGraph LANGUAGES NONE)']
        for key, value in settings.items():
            lines.append('set(' + key + ' ' + quote(('ON' if value else 'OFF') if isinstance(value, bool) else value) + ')')
        lines.append('add_library(' + actual_webcore + ' INTERFACE)')
        if alias:
            lines.append('add_library(WebCore ALIAS FixtureWebCore)')
        for item in ('WTF', 'JavaScriptCore', 'PAL', 'Skia', 'LLIntSettingsExtractor',
                     'LLIntOffsetsExtractor', 'LowLevelInterpreterLib'):
            if name != 'missing-LLInt' or item != 'LowLevelInterpreterLib':
                lines.append('add_library(' + item + ' INTERFACE)')
        lines += ['add_library(Skia::Skia ALIAS Skia)',
                  'add_library(Threads::Threads INTERFACE IMPORTED)']
        if name == 'existing-provider':
            lines.append('add_custom_target(BibNativeProvider)')
        lines += [RECORDER, 'include(' + quote(GRAPH) + ')',
                  'get_directory_property(_watched CMAKE_CONFIGURE_DEPENDS)',
                  'record(WATCH ${_watched})']
        (directory / 'CMakeLists.txt').write_text('\n'.join(lines) + '\n')
        started = time.monotonic()
        with (directory / 'cmake.log').open('x') as stream:
            owner = launch([str(self.cmake), '-G', 'Unix Makefiles', '-S', str(directory),
                            '-B', str(output), '-DCMAKE_MAKE_PROGRAM=' + str(self.cmake)],
                           directory, stream, env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
            try:
                code = owner.wait(timeout=max(.01, min(3, self.deadline - time.monotonic())))
                owner.finish()
            finally:
                owner.close()
        diagnostic = (directory / 'cmake.log').read_text()
        calls = log.read_text()
        self.results.append({'id': name, 'exit_code': code, 'expected_failure': failure,
                             'ineligible_webcore_shape': {'type': webcore_type,
                                 'imported': webcore_imported, 'pic': name != 'non-pic'},
                             'elapsed_seconds': time.monotonic() - started})
        if failure:
            self.assertNotEqual(code, 0, diagnostic)
            self.assertIn(failure, ' '.join(diagnostic.split()))
            self.assertNotIn('TARGET\tBibNativeProvider;', calls)
        else:
            self.assertEqual(code, 0, diagnostic)
            document = source / 'source/document-provider'
            self.assertIn('INCLUDE\t' + actual_webcore + ';PRIVATE;' + str(document)
                          + ';' + ';'.join(str(document / folder)
                                          for folder in ('key', 'ui', 'popup', 'clipboard')) + '\n', calls)
            for property_name, value in (('TYPE', 'STATIC_LIBRARY'), ('IMPORTED', 'OFF'),
                                         ('POSITION_INDEPENDENT_CODE', 'ON')):
                self.assertIn('INELIGIBLE_WEB_CORE_SHAPE\t' + actual_webcore
                              + ';' + property_name + ';' + value + '\n', calls)
            self.assertIn('FEATURE\tBibNativeProvider;PRIVATE;cxx_std_20', calls)
            selected = next(line for line in calls.splitlines() if line.startswith('TARGET\t')).split(';')[3:]
            sources = [path for path in selected if path.endswith('.cpp')]
            self.assertEqual(len(sources), 32)
            self.assertEqual(len(set(sources)), 32)
            for path in (*RICH, *UI_SOURCES):
                self.assertEqual(sources.count(str(source / 'source/document-provider' / path)), 1)
            for path in UI_HEADERS:
                self.assertEqual(selected.count(str(document / path)), 1)
            self.assertIn(str(binding), sources)
            for flag in ('NEUTRAL', 'NATIVE', 'DOCUMENT_V2', 'EDITOR_V1', 'DOCUMENT_ACTIONS_V1'):
                self.assertIn('BIB_ENGINE_PROVIDER_' + flag + '=1', calls)
            for target_name in (actual_webcore, 'BibNativeProvider'):
                definitions = [line.split(';')[2:] for line in calls.splitlines()
                               if line.startswith('DEFINITION\t' + target_name + ';PRIVATE;')]
                for flag in ('BIB_ENGINE_HTML_POPUP_V1=1', 'BIB_INTERNAL_RICH_CLIPBOARD=1'):
                    self.assertTrue(any(flag in values for values in definitions),
                                    target_name + ' misses ' + flag)
            for folder in ('runtime', 'native', 'portable', 'editor', 'key', 'physical',
                           'ui', 'popup', 'clipboard'):
                self.assertIn(str(source / 'source/document-provider' / folder), calls)
            eh = next(line for line in calls.splitlines() if line.startswith('SOURCE_PROPERTY\t'))
            self.assertEqual(eh.count('.cpp'), 23)
            for path in RICH:
                self.assertIn(str(source / 'source/document-provider' / path), eh)
            for path in UI_SOURCES:
                if path == 'popup/BibNativePopupOwner.cpp':
                    self.assertIn(str(document / path), eh)
                else:
                    self.assertNotIn(str(document / path), eh)
            self.assertIn('LINK\tBibNativeProvider;PRIVATE;WebCore;Skia::Skia;Threads::Threads\n', calls)
            self.assertFalse(any('/source/engine/' in path for path in sources))
            if system == 'Windows':
                self.assertIn('/EHsc;/U_HAS_EXCEPTIONS;/D_HAS_EXCEPTIONS=1', eh)
                self.assertIn('LINKER:/DEF:', calls)
                self.assertNotIn('--version-script', calls)
                for item in ('WTF', 'JavaScriptCore', 'PAL', 'WebCore', 'Skia',
                             'LLIntSettingsExtractor', 'LLIntOffsetsExtractor', 'LowLevelInterpreterLib'):
                    actual = actual_webcore if item == 'WebCore' else item
                    self.assertIn('DEFINITION\t' + actual + ';PRIVATE;BIB_ENGINE_PRIVATE_STATIC_COMPONENT=1;JS_NO_EXPORT=1;BIB_FOUNDATION_SYSTEM_DWRITE_ONLY=1', calls)
                self.assertIn('WINDOWS_EXPORT_ALL_SYMBOLS;OFF;MSVC_RUNTIME_LIBRARY;MultiThreaded', calls)
            else:
                self.assertIn('COMPILE_OPTIONS;-fexceptions', eh)
                self.assertIn('--version-script', calls)
                self.assertNotIn('BIB_ENGINE_PRIVATE_STATIC_COMPONENT', calls)
            watched = next(line for line in calls.splitlines() if line.startswith('WATCH\t'))
            for path in (binding, header, metadata):
                self.assertIn(str(path), watched)
            self.assertFalse(any(Path(path).name == 'Controller.cpp' for path in sources))
            for excluded in ('BibMediaPlayer.cpp', 'CopiedHost', 'WasmShim',
                             'BibNativeHost.cpp', 'RunLoopGeneric.cpp', '.js'):
                self.assertFalse(any(excluded in path for path in sources), excluded)
            self.assertNotIn('-std=', calls)
        cache = output / 'CMakeCache.txt'
        if cache.exists():
            self.assertNotIn('CMAKE_CXX_COMPILER:', cache.read_text())
            self.assertNotIn('CMAKE_C_COMPILER:', cache.read_text())
        for pattern in ('*.o', '*.obj', '*.so', '*.dll', '*.a', '*.lib'):
            self.assertEqual(list(output.rglob(pattern)), [])
        return calls

    def test_linux_and_alias_source_selection(self):
        self.fixture('linux-x64')
        self.fixture('linux-arm64', arm=True)
        self.fixture('linux-WebCore-alias', alias=True)

    def test_windows_private_component_policy(self):
        self.fixture('windows-x64', system='Windows')
        self.fixture('windows-WebCore-alias', system='Windows', alias=True)

    def test_missing_or_mismatched_source_inputs(self):
        for name, message in (
            ('wrong-pin', 'differs from its reviewed SHA256'),
            ('pixel-binding', 'exact recipe-owned actions binding'),
            ('source-metadata', 'outside reviewed sources'),
            ('missing-rich-source', 'selected native source/header'),
        ):
            with self.subTest(name=name):
                self.fixture(name, failure=message)

    def test_incompatible_engine_graph(self):
        for name, message in (
            ('jit', 'ENABLE_JIT=OFF'), ('non-pic', 'requires PIC WebCore'),
            ('dependency-target', 'same verified linux-x86_64'),
            ('hidden-loop', 'hidden GUI event loop'),
            ('existing-provider', 'already owns BibNativeProvider'),
            ('wasm', 'explicit Linux or admitted native Windows CPU port'),
        ):
            with self.subTest(name=name):
                self.fixture(name, failure=message)

    def test_private_callbacks_require_one_static_webcore_link_owner(self):
        self.assertNotIn('INELIGIBLE_WEB_CORE_', GRAPH.read_text())
        message = 'requires one in-tree static WebCore link owner'
        for name, target_type, imported, alias in (
            ('shared-WebCore', 'SHARED_LIBRARY', False, False),
            ('shared-WebCore-alias', 'SHARED_LIBRARY', False, True),
            ('module-WebCore', 'MODULE_LIBRARY', False, False),
            ('interface-WebCore', 'INTERFACE_LIBRARY', False, False),
            ('imported-WebCore', 'STATIC_LIBRARY', True, False),
            ('imported-WebCore-alias', 'STATIC_LIBRARY', True, True),
        ):
            with self.subTest(name=name):
                calls = self.fixture(name, alias=alias, webcore_type=target_type,
                                     webcore_imported=imported, failure=message)
                actual = 'FixtureWebCore' if alias else 'WebCore'
                for property_name, value in (('TYPE', target_type),
                                             ('IMPORTED', 'ON' if imported else 'OFF')):
                    self.assertIn('INELIGIBLE_WEB_CORE_SHAPE\t' + actual + ';'
                                  + property_name + ';' + value + '\n', calls)

    def test_windows_admission_prerequisites(self):
        for name, arm, message in (
            ('windows-unadmitted', False, 'separately admitted x64 clang-cl'),
            ('windows-dynamic-crt', False, 'separately admitted x64 clang-cl'),
            ('windows-arm64', True, 'separately admitted x64 clang-cl'),
            ('missing-LLInt', False, 'Missing private Windows engine component'),
        ):
            with self.subTest(name=name):
                self.fixture(name, system='Windows', arm=arm, failure=message)

    def test_getter_only_export_declarations(self):
        self.assertEqual((RECIPE / 'cmake/native-provider.def').read_text(),
                         'EXPORTS\n    bib_engine_get_provider_v1\n')
        exports = (RECIPE / 'cmake/native-provider.exports').read_text()
        self.assertEqual(re.findall(r'\b(bib_[A-Za-z0-9_]+)\s*;', exports),
                         ['bib_engine_get_provider_v1'])
        self.assertIn('local:\n        *;', exports)


if __name__ == '__main__':
    unittest.main()
