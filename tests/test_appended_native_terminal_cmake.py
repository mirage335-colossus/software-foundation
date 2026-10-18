#!/usr/bin/env python3
"""Compiler-free static CMake composition fixtures, never engine admission proof.

Actual copied project fragments execute under LANGUAGES NONE. Only target/tool
execution and registration commands are recorded; no SDK, compiler, engine,
provider, VM, production build or retained runtime is executed or qualified.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE_TARGET = 'foundation-appended-engine-terminal'
NATIVE_SELECTOR = 'FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE'
FRAGMENTS = ('Appended.cmake', 'AppendedCommon.cmake', 'AppendedPortableCodecs.cmake',
             'AppendedGui.cmake', 'AppendedBinary.cmake', 'AppendedEngineProvider.cmake',
             'AppendedDemoServices.cmake', 'AppendedNativeGuiTests.cmake',
             'AppendedCompositionTests.cmake')
MAIN_CASES = {
    'help', 'cli-missing', 'cli-relative', 'cli-normalized', 'cli-flag', 'cli-extra',
    'graceful', 'start-waiting', 'runner-hooks', 'physical-profile', 'browser-profile',
    'invalid-profile', 'binary-payload', 'unconfigured-start', 'unadopted-start',
    'missing-payload', 'corrupt-payload', 'invalid-startup', 'plan-root',
    'verify-failure', 'load-failure', 'bind-failure', 'start-terminal',
    'start-blocked', 'start-bound', 'runner-terminal', 'runner-blocked',
    'close-terminal', 'close-blocked', 'unfinished-close', 'tty-failure',
    'tty-nonstd', 'tty-return-failure',
} | {'profile-' + str(number) for number in range(37)}
ACTION_MAIN_CASES = {name for name in MAIN_CASES if not name.startswith('profile-')} - {
    'cli-missing', 'physical-profile', 'browser-profile', 'invalid-profile'} | {
    'default-runtime', 'default-runtime-failure', 'actions-cli-missing', 'actions-browser',
    'actions-legacy-document', 'actions-legacy-editor', 'actions-legacy-document-dirty',
    'actions-legacy-editor-dirty', 'actions-linux-arm64', 'actions-windows'} | {
    'actions-plan-' + str(number) for number in range(97)} | {
    'actions-facts-' + str(number) for number in range(91)}


def quote(value):
    """CMake bracket arguments preserve spaces without evaluating their text."""
    value = str(value)
    delimiter = '='
    while ']' + delimiter + ']' in value:
        delimiter += '='
    return '[' + delimiter + '[' + value + ']' + delimiter + ']'


def function_source(name):
    content = (ROOT / 'gui/CMakeLists.txt').read_text(encoding='utf-8')
    match = re.search(r'^function\(' + re.escape(name) + r'\b.*?^endfunction\(\)\n',
                      content, flags=re.M | re.S)
    if not match:
        raise AssertionError('Missing actual GUI helper: ' + name)
    return match.group()


def physical_asset_install_source():
    """Copy the real balanced profile-gated install block, not its condition."""
    lines = (ROOT / 'gui/CMakeLists.txt').read_text(encoding='utf-8').splitlines(True)
    begin = next(index for index, line in enumerate(lines)
                 if 'install(FILES ${foundation_surface_web_assets}' in line) - 1
    if not lines[begin].strip().startswith('if('):
        raise AssertionError('Missing outer surface asset profile guard')
    depth = 0
    for end in range(begin, len(lines)):
        if lines[end].strip().startswith('if('):
            depth += 1
        elif lines[end].strip().startswith('endif('):
            depth -= 1
            if depth == 0:
                return ''.join(lines[begin:end + 1])
    raise AssertionError('Unbalanced surface asset install block')


# Recording adapters keep CMake's conditionals/include guards/if(TARGET) real.
# INTERFACE placeholders deliberately do not constitute an actual binary DAG.
RECORDER = r'''
function(record operation)
    file(APPEND "${GRAPH}" "${operation}\t${ARGN}\n")
endfunction()
function(add_library name)
    _add_library("${name}" INTERFACE)
    record(TARGET "${name}" LIBRARY ${ARGN})
endfunction()
function(add_executable name)
    _add_library("${name}" INTERFACE)
    record(TARGET "${name}" EXECUTABLE ${ARGN})
endfunction()
function(add_custom_target name)
    _add_library("${name}" INTERFACE)
    record(TARGET "${name}" CUSTOM ${ARGN})
endfunction()
function(target_link_libraries)
    record(LINK ${ARGV})
endfunction()
function(target_include_directories)
    record(INCLUDE ${ARGV})
endfunction()
function(target_compile_definitions)
    record(DEFINITION ${ARGV})
endfunction()
function(target_compile_features)
    record(FEATURE ${ARGV})
endfunction()
function(target_compile_options)
    record(COMPILE_OPTION ${ARGV})
endfunction()
function(target_link_options)
    record(LINK_OPTION ${ARGV})
endfunction()
function(target_sources)
    record(SOURCES ${ARGV})
endfunction()
function(set_target_properties)
    record(PROPERTY ${ARGV})
endfunction()
function(add_dependencies)
    record(DEPENDENCY ${ARGV})
endfunction()
function(add_test)
    record(TEST ${ARGV})
endfunction()
function(set_tests_properties)
    record(TEST_PROPERTY ${ARGV})
endfunction()
function(foundation_test_prerequisites)
    record(PREREQUISITES ${ARGV})
endfunction()
function(install)
    record(INSTALL ${ARGV})
endfunction()
function(configure_file input output)
    record(COPY "${input}" "${output}")
    get_filename_component(directory "${output}" DIRECTORY)
    file(MAKE_DIRECTORY "${directory}")
    file(WRITE "${output}" "// Synthetic graph fixture only\n")
endfunction()
function(foundation_options)
endfunction()
function(foundation_notice_file)
    record(NOTICE ${ARGV})
endfunction()
function(enable_language)
    record(LANGUAGE ${ARGV})
endfunction()
function(find_package name)
    if(NOT name STREQUAL "Threads")
        message(FATAL_ERROR "Unexpected package discovery in static fixture: ${name}")
    endif()
    if(NOT TARGET Threads::Threads)
        _add_library(Threads::Threads INTERFACE IMPORTED)
    endif()
    set(Threads_FOUND TRUE PARENT_SCOPE)
    record(PACKAGE ${ARGV})
endfunction()
function(execute_process)
    record(PROCESS ${ARGV})
    set(arguments ${ARGV})
    set(status 0)
    string(JOIN " " command ${arguments})
    if(command MATCHES "appended_engine_sdk.py")
        if(command MATCHES "restore-sources")
            message(FATAL_ERROR "Native terminal must never restore a source archive")
        endif()
        if(FIXTURE_RESTORE_FAILURE)
            set(status 7)
            set(answer "")
            list(FIND arguments "COMMAND_ERROR_IS_FATAL" fatal_index)
            if(NOT fatal_index EQUAL -1)
                math(EXPR fatal_index "${fatal_index}+1")
                list(GET arguments ${fatal_index} fatal_mode)
                if(fatal_mode MATCHES "^(ANY|LAST)$")
                    message(FATAL_ERROR "Synthetic retained native runtime refused")
                endif()
            endif()
        else()
            list(FIND arguments "--output" output_index)
            if(NOT output_index EQUAL -1)
                math(EXPR output_index "${output_index}+1")
                list(GET arguments ${output_index} output)
                file(MAKE_DIRECTORY "${output}/lib" "${output}/share" "${output}/notices")
                file(WRITE "${output}/lib/provider.so" "ineligible provider bytes")
                file(WRITE "${output}/share/required.dat" "complete runtime resource")
                file(WRITE "${output}/notices/LICENSE" "fixture notice")
                file(WRITE "${output}/engine-sdk.json" "${FIXTURE_MANIFEST}")
            endif()
            set(answer "{\"scope\":\"synthetic-static-graph-only\",\"recipe_id\":\"${FOUNDATION_APPENDED_ENGINE_RECIPE_SHA256}\",\"manifest_sha256\":\"${FOUNDATION_APPENDED_ENGINE_MANIFEST_SHA256}\"}")
        endif()
    elseif(command MATCHES "appended_wasm3.py")
        set(answer "synthetic static VM leaf only")
    else()
        message(FATAL_ERROR "Unexpected external execution in compiler-free fixture: ${command}")
    endif()
    foreach(keyword OUTPUT_VARIABLE ERROR_VARIABLE RESULT_VARIABLE)
        list(FIND arguments "${keyword}" index)
        if(NOT index EQUAL -1)
            math(EXPR index "${index}+1")
            list(GET arguments ${index} variable)
            if(keyword STREQUAL "OUTPUT_VARIABLE")
                set(${variable} "${answer}" PARENT_SCOPE)
            elseif(keyword STREQUAL "RESULT_VARIABLE")
                set(${variable} ${status} PARENT_SCOPE)
            else()
                set(${variable} "" PARENT_SCOPE)
            endif()
        endif()
    endforeach()
endfunction()
'''

# Generated install scripts run only this argv recorder, never the SDK verifier.
FAKE_VERIFIER = r'''import json, os, sys
from pathlib import Path
with Path(os.environ['NATIVE_STATIC_ARGV_LOG']).open('a') as output:
    output.write(json.dumps(sys.argv[1:]) + '\n')
if os.environ.get('NATIVE_STATIC_VERIFIER_REFUSE') == '1':
    sys.exit(7)
if len(sys.argv) < 2 or sys.argv[1] != 'verify':
    sys.exit(8)
'''


class Graph:
    def __init__(self, records, output, returncode, cache):
        self.records, self.output, self.returncode, self.cache = records, output, returncode, cache
        self.targets = {row[0]: row[1:] for row in self.rows('TARGET')}

    def rows(self, operation):
        return [row for kind, row in self.records if kind == operation]

    def values(self, operation, target):
        return [value for row in self.rows(operation) if row and row[0] == target for value in row[1:]]

    def closure(self, target):
        result, pending = set(), [target]
        while pending:
            item = pending.pop()
            if item in result:
                continue
            result.add(item)
            pending.extend(value for value in self.values('LINK', item)
                           if value not in ('PRIVATE', 'PUBLIC', 'INTERFACE'))
        return result

    def tests_for(self, target):
        result = {}
        for row in self.rows('TEST'):
            if row and row[0] == 'NAME' and 'COMMAND' in row:
                command = row[row.index('COMMAND') + 1:]
                if command and command[0] in (target, '$<TARGET_FILE:' + target + '>'):
                    result[row[1]] = command
        return result


class Fixture:
    def __init__(self, root):
        self.root = root
        self.source, self.build = root / 'source', root / 'build'
        (self.source / 'cmake').mkdir(parents=True)
        (self.source / 'gui').mkdir()
        for name in FRAGMENTS:
            shutil.copyfile(ROOT / 'cmake' / name, self.source / 'cmake' / name)
        runtime = self.source / 'third_party/wasm3/source'
        runtime.mkdir(parents=True)
        (runtime / 'm3_env.c').write_text('/* ineligible graph sentinel; never compiled */\n')
        self.group = self.source / 'ineligible-retained-group'
        self.group.mkdir()
        (self.source / 'tools').mkdir()
        (self.source / 'tools/appended_engine_sdk.py').write_text(FAKE_VERIFIER)

    def configure(self, *, profile='web', native='pixel', testing=False,
                  consumer_verified=True, native_verified=True,
                  generated=True, system='Linux', pointer_bits=64, maintenance=True,
                  gui=True, emscripten=False, restore_failure=False):
        self.build.mkdir(exist_ok=True)
        generated_directory = self.build / 'appended-engine-native-profile'
        generated_directory.mkdir(exist_ok=True)
        header = generated_directory / 'appended_engine_compiled_native_profile.hpp'
        if generated:
            header.write_text('// Synthetic static graph only; not eligible native profile facts.\n')
        else:
            header.unlink(missing_ok=True)
        settings = {
            'FOUNDATION_APPENDED_PROFILE': profile, NATIVE_SELECTOR: native,
            'FOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED': native_verified,
            'FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED': consumer_verified,
            'FOUNDATION_APPENDED_KERNEL_MAINTENANCE': maintenance,
            'FOUNDATION_BUILD_GUI': gui, 'FOUNDATION_GUI_SOURCE': str(self.source / 'gui'),
            'FOUNDATION_GUI_DISTRIBUTABLE': True, 'BUILD_TESTING': testing,
            'EMSCRIPTEN': emscripten, 'CMAKE_SYSTEM_NAME': system,
            'CMAKE_SIZEOF_VOID_P': pointer_bits // 8, 'WIN32': system == 'Windows',
            'Python3_EXECUTABLE': sys.executable, 'FOUNDATION_NODE_EXECUTABLE': 'not-executed-node',
            'FOUNDATION_APPENDED_ENGINE_GROUP': str(self.group),
            'FOUNDATION_APPENDED_ENGINE_RECIPE_SHA256': '1' * 64,
            'FOUNDATION_APPENDED_ENGINE_MANIFEST_SHA256': '2' * 64,
            'FOUNDATION_APPENDED_ENGINE_PROOF_SHA256': '3' * 64,
            'FOUNDATION_APPENDED_ENGINE_RUNTIME_SHA256': '4' * 64,
            'CMAKE_INSTALL_BINDIR': 'bin', 'CMAKE_INSTALL_INCLUDEDIR': 'include',
            'CMAKE_INSTALL_DATADIR': 'share', 'CMAKE_DL_LIBS': 'dl',
            'CMAKE_INSTALL_FULL_BINDIR': str(self.root / 'install/bin'),
            'CMAKE_INSTALL_FULL_DATADIR': str(self.root / 'install/share'),
            'FIXTURE_RESTORE_FAILURE': restore_failure,
            'FIXTURE_MANIFEST': '{"files":{"lib/provider.so":"ineligible","share/required.dat":"ineligible","notices/LICENSE":"ineligible"},"directories":["lib","share","notices"]}',
        }
        def spelling(value):
            return 'ON' if value is True else 'OFF' if value is False else str(value)
        project = 'cmake_minimum_required(VERSION 3.24)\nproject(NativeTerminalStaticFixture LANGUAGES NONE)\n'
        project += 'set(GRAPH "${CMAKE_CURRENT_BINARY_DIR}/graph.txt")\nfile(WRITE "${GRAPH}" "")\n'
        project += RECORDER
        for key, value in settings.items():
            project += 'set(' + key + ' ' + quote(spelling(value)) + ')\n'
        project += '_add_library(foundation_gui_boundary INTERFACE)\n_add_library(foundation_gui_application INTERFACE)\n'
        project += '_add_library(foundation_core INTERFACE)\n_add_library(foundation::core ALIAS foundation_core)\n'
        project += '_add_library(foundation_gui_contract INTERFACE)\n_add_library(foundation-gui-hosts INTERFACE)\n'
        project += function_source('foundation_gui_executable') + function_source('foundation_gui_check')
        project += 'if(FOUNDATION_APPENDED_PROFILE MATCHES "^(binary|web|both)$" OR FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE)\n'
        project += ' include(cmake/Appended.cmake)\nendif()\nadd_subdirectory(gui)\n'
        (self.source / 'CMakeLists.txt').write_text(project, encoding='utf-8')
        (self.source / 'gui/CMakeLists.txt').write_text('include("${PROJECT_SOURCE_DIR}/cmake/AppendedGui.cmake")\n')
        command = [shutil.which('cmake') or 'cmake', '-G', 'Ninja', '-S', str(self.source), '-B', str(self.build)]
        result = subprocess.run(command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=30)
        graph = self.build / 'graph.txt'
        records = []
        if graph.exists():
            for line in graph.read_text(encoding='utf-8').splitlines():
                operation, separator, value = line.partition('\t')
                if not separator:
                    raise AssertionError('Malformed static graph record: ' + line)
                records.append((operation, value.split(';') if value else []))
        cache = self.build / 'CMakeCache.txt'
        return Graph(records, result.stdout, result.returncode, cache.read_text() if cache.exists() else '')


class NativeTerminalCMakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('cmake') or not shutil.which('ninja'):
            raise RuntimeError('The compiler-free static graph fixture requires CMake3.24+ and Ninja')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native terminal static graph ')
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Fixture(Path(self.temporary.name))

    def success(self, **options):
        graph = self.fixture.configure(**options)
        self.assertEqual(0, graph.returncode, graph.output)
        self.assertNotRegex(graph.cache, r'(?m)^CMAKE_(?:C|CXX)_COMPILER:')
        return graph

    def test_none_and_binary_do_not_select_native_engine_entry(self):
        none = self.success(profile='none', native='')
        self.assertNotIn(NATIVE_TARGET, none.targets)
        # The shared pure demo-services leaf is declared for ordinary GUI builds.
        # No appended runtime, VM or engine target is enabled by that declaration.
        self.assertEqual({target for target in none.targets if 'appended' in target},
                         {'foundation_gui_appended_demo_services'})
        self.assertIn('EXCLUDE_FROM_ALL', none.values('TARGET', 'foundation_gui_appended_demo_services'))
        binary = self.success(profile='binary', native='')
        self.assertIn('foundation-appended-kernel', binary.targets)
        self.assertIn('foundation-appended-terminal', binary.targets)
        self.assertIn('foundation_appended_wasm3', binary.closure('foundation-appended-terminal'))
        self.assertNotIn(NATIVE_TARGET, binary.targets)

    def test_native_web_is_pixel_only_and_vm_free(self):
        graph = self.success()
        self.assertIn(NATIVE_TARGET, graph.targets)
        closure = graph.closure(NATIVE_TARGET)
        self.assertTrue({'foundation_gui_native_engine_document_composition',
                         'foundation_appended_native_engine_loader', 'foundation_appended_startup'} <= closure)
        self.assertTrue({'foundation_appended_wasm3', 'foundation_appended_module',
                         'foundation_appended_engine_module_binding', 'foundation_gui_application'}.isdisjoint(closure))
        self.assertNotIn('foundation-appended-kernel', graph.targets)
        self.assertIn('FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED=1', graph.values('DEFINITION', NATIVE_TARGET))
        self.assertIn('FOUNDATION_APPENDED_BINARY_CAPABILITY=0', graph.values('DEFINITION', NATIVE_TARGET))
        self.assertTrue(any(value.endswith('/appended-engine-native-profile') for value in graph.values('INCLUDE', NATIVE_TARGET)))
        self.assertTrue(any(value.endswith('hosts/appended_engine_terminal_main.cpp') for value in graph.targets[NATIVE_TARGET]))

    def test_native_both_uses_actual_module_leaf_without_binary_console(self):
        graph = self.success(profile='both')
        closure = graph.closure(NATIVE_TARGET)
        self.assertTrue({'foundation_appended_engine_module_binding', 'foundation_appended_module',
                         'foundation_appended_wasm3'} <= closure)
        self.assertIn('FOUNDATION_APPENDED_BINARY_CAPABILITY=1', graph.values('DEFINITION', NATIVE_TARGET))
        self.assertTrue(any(value.endswith('gui/shared/appended_engine_module.cpp')
                            for value in graph.targets['foundation_appended_engine_module_binding']))
        self.assertNotIn('foundation-appended-kernel', graph.targets)
        self.assertNotIn('foundation-appended-terminal', graph.targets)
        self.assertNotIn('foundation_gui_application', closure)

    def test_invalid_or_unverified_native_selection_fails_before_entry(self):
        for options in ({'native': 'physical'}, {'native': ''}, {'consumer_verified': False},
                        {'native_verified': False}, {'profile': 'binary'}, {'profile': 'none'},
                        {'system': 'Darwin'}, {'pointer_bits': 32}, {'emscripten': True},
                        {'maintenance': False}, {'gui': False}, {'generated': False}):
            with self.subTest(options=options):
                graph = self.fixture.configure(**options)
                self.assertNotEqual(0, graph.returncode, graph.output)
                self.assertNotIn(NATIVE_TARGET, graph.targets)
                self.assertFalse(graph.rows('PROCESS'), graph.rows('PROCESS'))
                self.assertRegex(graph.output.lower(), r'native|pixel|verified|maintenance|compiled profile')

    def test_runtime_restore_failure_cannot_publish_production_target(self):
        graph = self.fixture.configure(restore_failure=True)
        self.assertNotEqual(0, graph.returncode, graph.output)
        self.assertIn('Synthetic retained native runtime refused', graph.output)
        self.assertNotIn(NATIVE_TARGET, graph.targets)

    def test_native_runtime_uses_binary_restore_and_complete_install(self):
        graph = self.success()
        processes = graph.rows('PROCESS')
        restore = [row for row in processes if 'restore' in row]
        self.assertEqual(1, len(restore), processes)
        self.assertFalse(any('restore-sources' in row for row in processes))
        restore_command = restore[0]
        self.assertEqual('1' * 64, restore_command[restore_command.index('--recipe') + 1])
        restored = restore_command[restore_command.index('--output') + 1]
        self.assertTrue(Path(restored).is_relative_to(self.fixture.build))
        self.assertFalse(Path(restored).is_relative_to(self.fixture.group))
        verifiers = [row for row in processes if 'verify' in row]
        self.assertTrue(verifiers, processes)
        for verifier in verifiers:
            self.assertEqual('1' * 64, verifier[verifier.index('--recipe') + 1])
            self.assertEqual('2' * 64, verifier[verifier.index('--manifest-sha256') + 1])
        installs = graph.rows('INSTALL')
        directories = [row for row in installs if row and row[0] == 'DIRECTORY']
        matching = [row for row in directories if row[1] == restored.rstrip('/') + '/']
        self.assertEqual(1, len(matching), directories)
        self.assertIn('USE_SOURCE_PERMISSIONS', matching[0])
        self.assertFalse({'PATTERN', 'REGEX', 'EXCLUDE', 'FILES_MATCHING'} & set(matching[0]))
        scripts = [row[1] for row in installs if row and row[0] == 'SCRIPT']
        self.assertEqual(2, len(scripts), installs)
        self.assertLess(installs.index(['SCRIPT', scripts[0]]), installs.index(matching[0]))
        self.assertGreater(installs.index(['SCRIPT', scripts[1]]), installs.index(matching[0]))
        # Reconfiguration must verify an existing owned runtime, never restore
        # over it or weaken the independent manifest join.
        existing = self.success()
        self.assertFalse(any('restore' in row for row in existing.rows('PROCESS')))
        existing_verifiers = [row for row in existing.rows('PROCESS') if 'verify' in row]
        self.assertEqual(1, len(existing_verifiers))
        verifier = existing_verifiers[0]
        self.assertEqual(restored, verifier[verifier.index('--root') + 1])
        self.assertEqual('1' * 64, verifier[verifier.index('--recipe') + 1])
        self.assertEqual('2' * 64, verifier[verifier.index('--manifest-sha256') + 1])

    def test_generated_install_verifiers_preserve_prefix_destdir_and_arguments(self):
        graph = self.success()
        installs = graph.rows('INSTALL')
        scripts = [row[1] for row in installs if row and row[0] == 'SCRIPT']
        self.assertEqual(2, len(scripts), installs)
        directory = next(row for row in installs if row and row[0] == 'DIRECTORY')
        runtime = directory[1].rstrip('/')
        destination = directory[directory.index('DESTINATION') + 1]
        log = self.fixture.root / 'fake verifier argv.jsonl'
        environment = os.environ.copy()
        environment['NATIVE_STATIC_ARGV_LOG'] = str(log)
        prefix = self.fixture.root / 'alternate install prefix $value'
        staging = self.fixture.root / 'destdir stage'
        environment['DESTDIR'] = str(staging)
        def run(script, *, refuse=False):
            current = dict(environment)
            if refuse:
                current['NATIVE_STATIC_VERIFIER_REFUSE'] = '1'
            command = [shutil.which('cmake'), '-DCMAKE_INSTALL_PREFIX:PATH=' + str(prefix), '-P', script]
            return subprocess.run(command, cwd=self.fixture.root, env=current,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15)
        before = run(scripts[0])
        self.assertEqual(0, before.returncode, before.stdout)
        after = run(scripts[1])
        self.assertEqual(0, after.returncode, after.stdout)
        invocations = [json.loads(line) for line in log.read_text().splitlines()]
        installed_root = str(staging) + str(prefix / destination)
        for actual, expected_root in zip(invocations, (runtime, installed_root)):
            self.assertEqual(['verify', '--root', expected_root, '--recipe', '1' * 64,
                              '--manifest-sha256', '2' * 64], actual)
        self.assertEqual(2, len(invocations))
        failed = run(scripts[1], refuse=True)
        self.assertNotEqual(0, failed.returncode, failed.stdout)
        self.assertIn('7', failed.stdout)
        failed_before = run(scripts[0], refuse=True)
        self.assertNotEqual(0, failed_before.returncode, failed_before.stdout)
        self.assertIn('7', failed_before.stdout)

    def test_generic_runner_and_editor_value_tests_survive_none_profile(self):
        graph = self.success(profile='none', native='', testing=True)
        targets = [name for name, values in graph.targets.items()
                   if any(value.endswith('tests/terminal_runner_test.cpp') for value in values)]
        self.assertEqual(1, len(targets))
        runner_tests = graph.tests_for(targets[0])
        self.assertEqual(1, len(runner_tests))
        for name in runner_tests:
            self.assertIn([name, targets[0]], graph.rows('PREREQUISITES'))
            properties = [row for row in graph.rows('TEST_PROPERTY') if row[0] == name]
            self.assertTrue(any('LABELS' in row and 'gui' in row and 'focused' in row for row in properties))

        for source in ('browser_surface_editor_controller_test.mjs', 'browser_surface_editor_conduit_test.mjs'):
            matches = [row for row in graph.rows('TEST') if any(value.endswith('/' + source) for value in row)]
            self.assertEqual(1, len(matches), source)
            self.assertIn([matches[0][1]], graph.rows('PREREQUISITES'))
            properties = [row for row in graph.rows('TEST_PROPERTY') if row[0] == matches[0][1]]
            self.assertTrue(any('LABELS' in row and 'gui' in row and 'focused' in row for row in properties))

    def test_physical_asset_install_gate_keeps_legacy_and_document_selection(self):
        # Only selection/whole-list forwarding is modeled; assets are not built.
        for profile, document, legacy, expected in (
                ('web', '', True, True), ('web', 'physical', False, True),
                ('web', 'pixel', False, False), ('web', '', False, False),
                ('binary', 'physical', False, False)):
            with self.subTest(profile=profile, document=document, legacy=legacy):
                script = self.fixture.root / 'asset gate.cmake'
                graph_file = self.fixture.root / 'asset gate.graph'
                script.write_text('set(GRAPH ' + quote(graph_file) + ')\nfile(WRITE "${GRAPH}" "")\n' + RECORDER
                                  + 'set(FOUNDATION_APPENDED_PROFILE ' + quote(profile) + ')\n'
                                  + 'set(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE ' + quote(document) + ')\n'
                                  + 'set(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT ' + ('ON' if legacy else 'OFF') + ')\n'
                                  + 'set(CMAKE_INSTALL_DATADIR share)\n'
                                  + 'set(foundation_surface_web_assets surface-a surface-b)\n'
                                  + 'set(foundation_physical_web_assets physical-a physical-b physical-c)\n'
                                  + physical_asset_install_source())
                result = subprocess.run([shutil.which('cmake'), '-P', str(script)], cwd=self.fixture.root,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15)
                self.assertEqual(0, result.returncode, result.stdout)
                records = [line.split('\t', 1)[1].split(';') for line in graph_file.read_text().splitlines()]
                physical = [row for row in records if 'share/software-foundation/web-physical' in row]
                self.assertEqual([['FILES', 'physical-a', 'physical-b', 'physical-c', 'DESTINATION',
                                   'share/software-foundation/web-physical']] if expected else [], physical)

    def test_native_main_mocks_register_every_fresh_case_and_overlay(self):
        graph = self.success(testing=True)
        targets = [name for name, values in graph.targets.items()
                   if any(value.endswith('tests/appended_engine_terminal_main_test.cpp') for value in values)]
        self.assertEqual({'foundation_gui_native_terminal_' + variant + mode + '_test'
                          for variant in ('main_', 'actions_main_') for mode in ('web', 'both')}, set(targets))
        modes = set()
        for target in targets:
            definitions = graph.values('DEFINITION', target)
            self.assertIn('FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED=1', definitions)
            capability = [value for value in definitions if value.startswith('FOUNDATION_APPENDED_BINARY_CAPABILITY=')]
            self.assertEqual(1, len(capability))
            modes.add(capability[0].split('=')[1])
            self.assertNotIn('foundation_appended_engine_module_binding', graph.closure(target))
            includes = [row for row in graph.rows('INCLUDE') if row[0] == target]
            overlays = [row for row in includes if any('/tests/fixtures/appended_engine_terminal' in value for value in row)]
            self.assertTrue(overlays)
            self.assertIn('BEFORE', overlays[0])
            directories = [value for value in overlays[0][1:]
                           if value not in ('BEFORE', 'PRIVATE', 'PUBLIC', 'INTERFACE', 'SYSTEM')]
            self.assertTrue(directories[0].endswith('/tests/fixtures/appended_engine_terminal'))
            tests = graph.tests_for(target)
            actions = '_actions_main_' in target
            self.assertEqual(ACTION_MAIN_CASES if actions else MAIN_CASES,
                             {command[-1] for command in tests.values()})
            self.assertEqual(227 if actions else 70, len(tests))
            self.assertEqual('1' if '_both_' in target else '0', capability[0].split('=')[1])
            self.assertEqual(actions, 'FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE=1' in definitions)
            for name in tests:
                self.assertIn([name, target], graph.rows('PREREQUISITES'))
                properties = [row for row in graph.rows('TEST_PROPERTY') if row[0] == name]
                self.assertTrue(any('LABELS' in row and 'gui' in row and 'appended' in row and 'focused' in row
                                    for row in properties))
        self.assertEqual({'0', '1'}, modes)


if __name__ == '__main__':
    unittest.main()
