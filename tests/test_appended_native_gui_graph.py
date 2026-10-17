#!/usr/bin/env python3
"""Compiler-free checks of the real native bitmap composition CMake fragment.

The fixture uses LANGUAGES NONE and records target/discovery calls. Its private
profile and prerequisite targets are deliberately ineligible test values. No
compiler, toolkit, SDK, engine, installed application or native window is run.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from process_tree import launch

FIXTURE = ROOT / 'tests/fixtures/appended_native_gui_graph/CMakeLists.txt'
GRAPH = ROOT / 'cmake/AppendedNativeGui.cmake'
BACKENDS = ROOT / 'cmake/GuiNativeBackends.cmake'
ADMISSION_ERROR = 'Native bitmap hosts require the admitted native rich application graph'
CASES = (
    ('none', None, 1), ('binary', None, 1), ('wasm', None, 1),
    ('linux-web-pixel', None, 47), ('linux-both-pixel', None, 47),
    ('linux-web-actions', None, 47), ('linux-both-actions', None, 47),
    ('framebuffer-only', None, 14), ('no-install', None, 47),
    ('windows-web-actions', None, 47), ('windows-both-actions', None, 47),
    ('no-maintenance', ADMISSION_ERROR, 0),
    ('no-verification', ADMISSION_ERROR, 0),
    ('missing-header', ADMISSION_ERROR, 0),
    ('missing-facade', ADMISSION_ERROR, 0),
    ('missing-sdl', 'Native SDL bitmap host is missing its generic Surface peer target', 0),
    ('missing-rev', 'Native Rev bitmap host is missing its generic Surface peer target', 0),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def stable_bytes(path):
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError('Inert fixture input is not an ordinary file: ' + str(path))
    data = path.read_bytes()
    if identity(before) != identity(path.stat(follow_symlinks=False)):
        raise RuntimeError('Inert fixture input changed while copying: ' + str(path))
    return data, identity(before)


class NativeBitmapGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected = os.environ.get('CMAKE_COMMAND') or shutil.which('cmake')
        if not selected:
            raise unittest.SkipTest('CMake 3.24+ host prerequisite unavailable; no graph assertions executed')
        if os.name != 'nt' and not sys.platform.startswith('linux'):
            raise unittest.SkipTest('Inert graph process supervision is qualified only for Linux/Windows')
        cls.cmake = Path(selected).resolve(strict=True)
        retained = os.environ.get('FOUNDATION_NATIVE_GUI_GRAPH_TEST_ROOT')
        parent = Path(retained).resolve(strict=True) if retained else None
        cls.directory = Path(tempfile.mkdtemp(prefix='native-gui-graph-', dir=parent))
        cls.retain = bool(retained)
        cls.writers_closed = True
        cls.results = []
        cls.inputs = []
        cls.copies = cls.directory / 'inputs'
        cls.copies.mkdir()
        for source, relative in (
                (GRAPH, Path('AppendedNativeGui.cmake')),
                (BACKENDS, Path('GuiNativeBackends.cmake')),
                (FIXTURE, Path('fixture/CMakeLists.txt'))):
            data, observed = stable_bytes(source)
            copy = cls.copies / relative
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(data)
            cls.inputs.append({'source': str(source), 'source_identity': observed,
                               'copy': str(copy), 'sha256': hashlib.sha256(data).hexdigest()})
        cls.tool_pins = {str(path): digest(path) for path in (
            Path(__file__), ROOT / 'tools/process_tree.py', cls.cmake)}
        cls.deadline = time.monotonic() + 25
        # Preserve only OS loader/temporary-directory basics. In particular a
        # caller's CMAKE_TOOLCHAIN_FILE environment cannot load an SDK here.
        cls.environment = {key: value for key, value in os.environ.items()
                           if key.upper() in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC')}
        cls.environment.update({'LANG': 'C', 'LC_ALL': 'C'})

    @classmethod
    def tearDownClass(cls):
        # Unknown writers retain the directory; no dependent evidence reads or
        # cleanup follow an unconfirmed process-tree result.
        if not cls.writers_closed:
            raise AssertionError('Inert graph output ownership remains unresolved: ' + str(cls.directory))
        copies_same = all(digest(Path(row['copy'])) == row['sha256'] for row in cls.inputs)
        tools_same = all(digest(Path(path)) == pin for path, pin in cls.tool_pins.items())
        summary = {
            'kind': 'ineligible-LANGUAGES-NONE-native-bitmap-graph',
            'cases': cls.results, 'case_count': len(cls.results),
            'positive_graph_assertions': sum(row['graph_assertions'] for row in cls.results),
            'source_inputs': cls.inputs, 'source_copies_unchanged': copies_same,
            'tool_inputs': cls.tool_pins, 'tool_inputs_unchanged': tools_same,
            'writers_closed': cls.writers_closed,
            'compiler_toolkit_SDK_engine_or_native_runtime_executed': False,
            'production_eligible': False, 'activity_budget_seconds': 25,
            'cleanup_budget_seconds': 5,
        }
        (cls.directory / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        if not cls.retain:
            shutil.rmtree(cls.directory)
        if not copies_same or not tools_same:
            raise AssertionError('Frozen inert graph input or tool bytes changed during the run')

    def configure(self, name, expected_error, expected_assertions):
        self.assertTrue(self.writers_closed, 'Previous inert graph process ownership is unresolved')
        remaining = self.deadline - time.monotonic()
        self.assertGreater(remaining, 0, '25-second inert graph activity budget exhausted')
        build = self.directory / name
        command = [str(self.cmake), '-G', 'Unix Makefiles', '-S', str(self.copies / 'fixture'),
                   '-B', str(build), '-DCMAKE_MAKE_PROGRAM=' + str(self.cmake),
                   '-DCMAKE_TOOLCHAIN_FILE:FILEPATH=', '-DREVIEW_CASE=' + name,
                   '-DREVIEW_FRAGMENT=' + str(self.copies / 'AppendedNativeGui.cmake'),
                   '-DREVIEW_BACKENDS=' + str(self.copies / 'GuiNativeBackends.cmake')]
        log = self.directory / (name + '.log')
        started = time.monotonic()
        type(self).writers_closed = False
        with log.open('xb') as stream:
            owner = launch(command, self.copies / 'fixture', stream, env=self.environment)
            try:
                status = owner.wait(timeout=max(.01, min(3, remaining)))
                owner.finish()
            finally:
                owner.close()
            type(self).writers_closed = True
        diagnostic_bytes = log.read_bytes()
        self.assertLessEqual(len(diagnostic_bytes), 2 * 1024 * 1024, 'Inert CMake output exceeded its bound')
        diagnostic = diagnostic_bytes.decode('utf-8', errors='replace')
        marker = build / 'ASSERTIONS.txt'
        assertions = int(marker.read_text(encoding='ascii')) if marker.is_file() else 0
        self.results.append({'case': name, 'argv': command, 'exit_code': status,
                             'expected_failure': expected_error is not None,
                             'graph_assertions': assertions,
                             'elapsed_seconds': time.monotonic() - started,
                             'process_tree_joined': True, 'output_stream_closed': True,
                             'log_sha256': hashlib.sha256(diagnostic_bytes).hexdigest()})
        if expected_error:
            self.assertNotEqual(status, 0, diagnostic)
            self.assertIn(expected_error, ' '.join(diagnostic.split()))
        else:
            self.assertEqual(status, 0, diagnostic)
        self.assertEqual(assertions, expected_assertions, diagnostic)
        cache = (build / 'CMakeCache.txt').read_text(encoding='utf-8')
        self.assertNotIn('CMAKE_CXX_COMPILER:', cache)
        self.assertNotIn('CMAKE_C_COMPILER:', cache)
        for suffix in ('*.o', '*.obj', '*.so', '*.dll', '*.a', '*.lib', '*.wasm'):
            self.assertEqual(list(build.rglob(suffix)), [], 'Unexpected compiled product in inert graph')

    def test_native_bitmap_profile_graphs(self):
        for name, expected_error, expected_assertions in CASES:
            with self.subTest(case=name):
                self.configure(name, expected_error, expected_assertions)
        self.assertEqual(len(self.results), 17)
        self.assertEqual(sum(row['graph_assertions'] for row in self.results), 346)


if __name__ == '__main__':
    unittest.main()
