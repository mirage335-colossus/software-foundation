"""Source-level boundary tripwires supplement executable GUI conformance."""

from pathlib import Path
import importlib.util
import ctypes
import json
import os
import re
import sys
import subprocess
import unittest
import tempfile
import time
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


_spec = importlib.util.spec_from_file_location("gui_guard", ROOT / "gui/check_boundary.py")
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)
shared_violations = _guard.shared_violations


class GuiBoundaryTests(unittest.TestCase):
    def test_shared_application_is_backend_independent(self):
        for path in _guard.sources(ROOT / "gui/shared"):
            self.assertEqual([], shared_violations(path.read_text()), str(path))

    def test_tripwire_rejects_concrete_backends(self):
        for source in ('#include <FL/Fl.H>', '#include <gui/framebuffer.hpp>',
                       'import Rev.Widget;', 'gui::WebAdapter adapter;'):
            self.assertTrue(shared_violations(source), source)
        self.assertFalse(shared_violations('#include <gui/contract.hpp>\ngui::Adapter& adapter;'))

    def test_generic_surface_companion_is_public_to_shared_and_host_code(self):
        self.assertEqual([], shared_violations('#include <foundation/gui/surface.hpp>\n'))
        for name in ('gui/surface.hpp', 'foundation/gui/private.hpp', 'foundation/gui/contract.hpp',
                     'foundation/gui/detail/surface.hpp', 'other/gui/surface.hpp'):
            self.assertTrue(shared_violations('#include <' + name + '>\n'), name)
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary); root = project / 'gui'
            for directory in ('shared', 'host'):
                (root / directory).mkdir(parents=True)
                (root / directory / 'consumer.cpp').write_text(
                    '#include <foundation/gui/surface.hpp>\n'
                    'foundation::gui_surface::Capabilities* capabilities;\n')
            header = project / 'include/foundation/gui/surface.hpp'
            header.parent.mkdir(parents=True)
            header.write_text('#include <cstdint>\nnamespace foundation::gui_surface { struct Capabilities; }\n')
            failures, dependencies = _guard.analyze(root)
            self.assertEqual([], failures)
            self.assertIn(header.resolve(), dependencies)
            private = header.with_name('private.hpp')
            private.write_text('void private_helper();\n')
            for directory in ('shared', 'host'):
                consumer = root / directory / 'consumer.cpp'
                consumer.write_text('#include <foundation/gui/private.hpp>\n')
                failures = _guard.tree_violations(root)
                self.assertTrue(any(str(consumer) in failure for failure in failures), directory)
                consumer.write_text('#include <foundation/gui/surface.hpp>\n')

    def test_generic_editor_companion_preserves_the_application_boundary(self):
        self.assertEqual([], shared_violations('#include <foundation/gui/surface_editor.hpp>\n'))
        for name in ('gui/surface_editor.hpp', 'foundation/gui/detail/surface_editor.hpp',
                     'foundation/gui/native_editor_controller.hpp'):
            self.assertTrue(shared_violations('#include <' + name + '>\n'), name)
        with tempfile.TemporaryDirectory(prefix='generic editor boundary ') as temporary:
            project = Path(temporary); root = project / 'gui'
            for directory in ('shared', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            consumer = root / 'host/editor.hpp'
            consumer.write_text('#include <foundation/gui/surface_editor.hpp>\n'
                'foundation::gui_editor::Packet* packet;\n')
            header = project / 'include/foundation/gui/surface_editor.hpp'
            header.parent.mkdir(parents=True)
            neutral = 'namespace foundation::gui_editor { struct Packet; }\n'
            header.write_text(neutral)
            failures, dependencies = _guard.analyze(root)
            self.assertEqual([], failures)
            self.assertIn(header.resolve(), dependencies)
            private = root / 'shared/native_editor_controller.hpp'
            private.write_text('namespace foundation::ui::native_editor { class Controller; }\n')
            domain = project / 'include/foundation/store.hpp'
            domain.write_text('namespace foundation { class Store; }\n')
            engine = root / 'shared/engine_editor_profile.hpp'
            engine.write_text('struct EngineEditorFacts;\n')
            for forbidden in ('#include "../../../gui/shared/native_editor_controller.hpp"\n',
                              '#include "../../../gui/shared/engine_editor_profile.hpp"\n',
                              '#include <foundation/store.hpp>\n',
                              'foundation::ui::native_editor::Controller* controller;\n',
                              '#include <SDL.h>\n'):
                header.write_text(neutral + forbidden)
                self.assertTrue(_guard.tree_violations(root), forbidden)
            header.write_text(neutral)
            for symbol in ('EngineEditorPort', 'BoundEngineEditorPort'):
                source = '#include "../shared/appended_engine_application.hpp"\n' + \
                    'foundation::ui::' + symbol + '* port;\n'
                (root / 'shared/appended_engine_application.hpp').write_text(
                    'namespace foundation::ui { struct ' + symbol + '; }\n')
                main = root / 'hosts/appended_main.cpp'; main.write_text(source)
                self.assertEqual([], _guard.tree_violations(root), symbol)
                helper = root / 'host/helper.hpp'; helper.write_text(source)
                self.assertTrue(_guard.tree_violations(root), symbol)
                helper.unlink(); main.unlink()

    def test_generic_document_values_and_endpoint_have_exact_public_names(self):
        for name in ('document_values.hpp', 'document_endpoint.hpp'):
            self.assertEqual([], shared_violations('#include <foundation/gui/' + name + '>\n'))
        for name in ('gui/document_values.hpp', 'foundation/gui/detail/document_values.hpp',
                     'foundation/gui/private_document.hpp', 'foundation/gui/document_endpoint_private.hpp'):
            self.assertTrue(shared_violations('#include <' + name + '>\n'), name)
        expected = {'DocumentVersion', 'DocumentNodeKind', 'DocumentWhiteSpace', 'DocumentNode',
            'DocumentPoint', 'DocumentSelection', 'DocumentSnapshot', 'DocumentEditorState',
            'DocumentNodeMetadata', 'DocumentNativeOffsetKind', 'DocumentNativePoint',
            'DocumentNativeSelection', 'DocumentWireSelection', 'DocumentDecodeDegradation',
            'DocumentSemanticReply', 'NativeFormsDocumentObservation'}
        self.assertEqual(expected, _guard.PUBLIC_GUI_VALUE_SYMBOLS)
        with tempfile.TemporaryDirectory(prefix='generic document boundary ') as temporary:
            project = Path(temporary); root = project / 'gui'
            for directory in ('shared', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            consumer = root / 'host/document.hpp'
            public = project / 'include/foundation/gui'; public.mkdir(parents=True)
            values = public / 'document_values.hpp'
            values.write_text('#include <foundation/appended/document_forms.hpp>\n'
                'namespace foundation::ui { struct DocumentSnapshot; }\n')
            endpoint = public / 'document_endpoint.hpp'
            endpoint.write_text('#include <foundation/gui/document_values.hpp>\n'
                'namespace foundation::gui_document { struct State; }\n')
            forms = project / 'include/foundation/appended/document_forms.hpp'
            forms.parent.mkdir(); forms.write_text('namespace foundation::appended { struct FormVersion; }\n')
            source = '#include <foundation/gui/document_endpoint.hpp>\n'
            for symbol in expected:
                consumer.write_text(source + 'foundation::ui::' + symbol + '* value;\n')
                failures, dependencies = _guard.analyze(root)
                self.assertEqual([], failures, symbol)
                for path in (values, endpoint, forms): self.assertIn(path.resolve(), dependencies)
            for symbol in ('AppendedDocument', 'AppendedDocumentForms', 'DocumentProjection',
                           'DocumentEngineRequest', 'EngineDocumentBroker', 'NativeFormsDocumentObservationPrivate'):
                consumer.write_text(source + 'foundation::ui::' + symbol + '* private_value;\n')
                self.assertTrue(_guard.tree_violations(root), symbol)
            consumer.write_text(source + 'foundation::appended::FormDraft* private_draft;\n')
            self.assertTrue(any('shared document draft behavior' in failure
                for failure in _guard.tree_violations(root)))
            consumer.write_text(source)
            rust = root / 'host/document.rs'
            rust.write_text('use foundation::appended::FormDraft;\n')
            self.assertTrue(any('shared document draft behavior in Rust' in failure
                for failure in _guard.tree_violations(root)))
            rust.unlink()
            consumer.write_text('#include <foundation/appended/document_forms.hpp>\n')
            self.assertTrue(_guard.tree_violations(root), 'direct generic form implementation include')

    def test_generic_document_leaf_checks_its_exact_form_dependency_closure(self):
        with tempfile.TemporaryDirectory(prefix='generic document dependency ') as temporary:
            project = Path(temporary); root = project / 'gui'
            (root / 'host').mkdir(parents=True); (root / 'shared').mkdir()
            (root / 'host/document.hpp').write_text('#include <foundation/gui/document_endpoint.hpp>\n')
            public = project / 'include/foundation/gui'; public.mkdir(parents=True)
            values = public / 'document_values.hpp'
            values.write_text('#include <foundation/appended/document_forms.hpp>\n')
            endpoint = public / 'document_endpoint.hpp'
            endpoint.write_text('#include <foundation/gui/document_values.hpp>\n')
            forms = project / 'include/foundation/appended/document_forms.hpp'
            forms.parent.mkdir(); forms.write_text('void form_values();\n')
            domain = project / 'include/foundation/store.hpp'; domain.write_text('class Store;\n')
            private = forms.with_name('private.hpp'); private.write_text('void private_helper();\n')
            self.assertEqual([], _guard.tree_violations(root))
            for forbidden in ('#include <foundation/store.hpp>\n', '#include "private.hpp"\n',
                              'foundation::Store* domain;\n', '#include <SDL.h>\n'):
                forms.write_text(forbidden)
                self.assertTrue(_guard.tree_violations(root), forbidden)
            forms.write_text('void form_values();\n')
            # The exception belongs to the leaf's exact edge, not every public
            # companion or an adjacent Foundation header.
            endpoint.write_text('#include <foundation/appended/document_forms.hpp>\n')
            self.assertTrue(_guard.tree_violations(root))
            endpoint.write_text('#include <foundation/gui/document_values.hpp>\n')
            values.write_text('#include <foundation/appended/private.hpp>\n')
            self.assertTrue(_guard.tree_violations(root))

    def test_generic_surface_companion_checks_nested_backend_and_domain_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary); root = project / 'gui'
            (root / 'shared').mkdir(parents=True)
            (root / 'shared/consumer.cpp').write_text('#include <foundation/gui/surface.hpp>\n')
            (root / 'shared/view.hpp').write_text('const char* id = "records.add";\n')
            header = project / 'include/foundation/gui/surface.hpp'
            header.parent.mkdir(parents=True)
            header.write_text('#include "../../../helpers/bridge.hpp"\n')
            bridge = project / 'helpers/bridge.hpp'; bridge.parent.mkdir()
            bridge.write_text('#include "nested.hpp"\n')
            nested = bridge.with_name('nested.hpp')
            nested.write_text('void generic_helper();\n')
            (project / 'include/foundation/store.hpp').write_text('namespace foundation { class Store; }\n')
            failures, dependencies = _guard.analyze(root)
            self.assertEqual([], failures)
            for path in (header, bridge, nested):
                self.assertIn(path.resolve(), dependencies)
            for source in ('#include <FL/Fl.H>\n', 'using Native = SDL_Window;\n',
                           '#include <foundation/store.hpp>\n', 'foundation::Store* domain;\n',
                           'namespace foundation { Store* domain; }\n',
                           'const char* id = "records.add";\n',
                           '#include "../gui/shared/view.hpp"\n',
                           '#define HEADER <FL/Fl.H>\n#include HEADER\n'):
                with self.subTest(source=source):
                    nested.write_text(source)
                    failures = _guard.tree_violations(root)
                    self.assertTrue(any(str(nested) in failure for failure in failures), failures)

    def test_native_bitmap_entry_header_stays_at_the_composition_root(self):
        with tempfile.TemporaryDirectory(prefix='native bitmap entry boundary ') as temporary:
            project = Path(temporary); root = project / 'gui'
            for directory in ('shared', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            (root / 'shared/native_engine_bitmap_composition.hpp').write_text(
                'namespace foundation::ui { class NativeEngineBitmapComposition; }\n')
            startup = project / 'include/foundation/appended/startup.hpp'
            startup.parent.mkdir(parents=True)
            startup.write_text('void startup_value();\n')
            entry = root / 'hosts/appended_engine_native_entry.hpp'
            source = '#include "../shared/native_engine_bitmap_composition.hpp"\n' + \
                '#include <foundation/appended/startup.hpp>\n' + \
                'foundation::ui::NativeEngineBitmapComposition* composition;\n'
            entry.write_text(source)
            main = root / 'hosts/appended_engine_sdl_main.cpp'
            main.write_text('#include "appended_engine_native_entry.hpp"\n')
            self.assertEqual([], _guard.tree_violations(root))
            helper = root / 'host/helper.hpp'
            helper.write_text('#include "../hosts/appended_engine_native_entry.hpp"\n')
            self.assertTrue(any('application composition root' in failure
                for failure in _guard.tree_violations(root)))
            helper.write_text(source)
            self.assertTrue(_guard.tree_violations(root))
            helper.unlink()
            entry.with_name('other_entry.hpp').write_text(source)
            self.assertTrue(_guard.tree_violations(root))

    def test_unused_generic_surface_implementation_is_checked_by_real_entry_point(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve(); root = project / 'gui'; root.mkdir()
            guard = root / 'check_boundary.py'
            guard.write_bytes((ROOT / 'gui/check_boundary.py').read_bytes())
            header = project / 'include/foundation/gui/surface.hpp'
            header.parent.mkdir(parents=True)
            header.write_text('namespace foundation::gui_surface { struct Capabilities; }\n')
            source = project / 'src/gui/surface.cpp'; source.parent.mkdir(parents=True)
            source.write_text('#include <foundation/gui/surface.hpp>\n')
            result = subprocess.run([sys.executable, '-B', str(guard), '--dependencies'],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)
            for path in (header, source):
                self.assertIn(str(path), result.stdout)
            helper = project / 'helpers/nested.hpp'; helper.parent.mkdir()
            source.write_text('#include "../../helpers/nested.hpp"\n')
            for content in ('using Native = SDL_Window;\n', 'foundation::Store* domain;\n'):
                helper.write_text(content)
                result = subprocess.run([sys.executable, '-B', str(guard)],
                    capture_output=True, text=True, timeout=15)
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn(str(helper), result.stderr)
            helper.write_text('void generic_helper();\n')
            result = subprocess.run([sys.executable, '-B', str(guard)],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_real_source_tree_including_generic_surface_passes_boundary(self):
        failures, dependencies = _guard.analyze(ROOT / 'gui')
        self.assertEqual([], failures)
        for relative in ('include/foundation/gui/surface.hpp', 'src/gui/surface.cpp'):
            self.assertIn((ROOT / relative).resolve(), dependencies)

    def test_incremental_build_rechecks_new_generic_surface_and_nested_helpers(self):
        cmake = (ROOT / 'gui/CMakeLists.txt').read_text()
        block = 'file(GLOB_RECURSE' + cmake.split('file(GLOB_RECURSE', 1)[1].split(
            'add_library(foundation_gui_application STATIC', 1)[0]
        with tempfile.TemporaryDirectory(prefix='incremental generic surface ') as temporary:
            project = Path(temporary) / 'source'; root = project / 'gui'; root.mkdir(parents=True)
            (root / 'check_boundary.py').write_bytes((ROOT / 'gui/check_boundary.py').read_bytes())
            (root / 'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(BoundaryGuard LANGUAGES NONE)\n' +
                'find_package(Python3 REQUIRED COMPONENTS Interpreter)\n' + block)
            build = Path(temporary) / 'build'
            subprocess.run(['cmake', '-G', 'Ninja', '-S', str(root), '-B', str(build)],
                check=True, capture_output=True, text=True, timeout=30)
            def check():
                return subprocess.run(['cmake', '--build', str(build), '--target', 'foundation_gui_contract'],
                    capture_output=True, text=True, timeout=30)
            def change(path, contents):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)
                tick = max(time.time_ns(), path.stat().st_mtime_ns + 10_000_000,
                           (build / 'boundary-checked').stat().st_mtime_ns + 10_000_000)
                os.utime(path, ns=(tick, tick))
            result = check(); self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            header = project / 'include/foundation/gui/surface.hpp'
            change(header, 'using Native = SDL_Window;\n')
            result = check(); self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn('surface.hpp', result.stdout + result.stderr)
            change(header, 'namespace foundation::gui_surface { struct Capabilities; }\n')
            result = check(); self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            source = project / 'src/gui/surface.cpp'
            change(source, 'foundation::Store* domain;\n')
            result = check(); self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn('surface.cpp', result.stdout + result.stderr)
            helper = project / 'helpers/nested.hpp'
            change(helper, 'void generic_helper();\n')
            change(source, '#include <foundation/gui/surface.hpp>\n#include "../../helpers/nested.hpp"\n')
            result = check(); self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            change(helper, '#include <FL/Fl.H>\n')
            result = check(); self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn('nested.hpp', result.stdout + result.stderr)

    def test_rust_tripwire_rejects_backend_imports_calls_and_linkage(self):
        for source in ('use sdl2::video::Window;', 'use fltk::{app, window};',
                       'extern crate rev as renderer;', 'use gui::framebuffer::Adapter;',
                       'fn draw() { sdl2::event::poll(); }',
                       'extern "C" { fn SDL_PollEvent(event: *mut u8) -> u32; }',
                       'extern "C" { fn foundation_gui_render(); }',
                       'extern "C" { fn rev_create_window(); }',
                       '#[link(name = "SDL2")] extern "C" {}',
                       '#[link(name = "SDL2main")] extern "C" {}',
                       '#[link(name = r#"fltk"#)] extern "C" {}',
                       '#[link(name = "\\x53DL2")] extern "C" {}',
                       '#[link_name = "SDL_PollEvent"] extern "C" { fn poll(); }',
                       '#[link(name = concat!("SDL", "2"))] extern "C" {}',
                       '#[path = "../../gui/host/renderer.rs"] mod renderer;'):
            self.assertTrue(_guard.rust_violations(source), source)

    def test_rust_tripwire_permits_core_and_private_callback_without_data_false_positives(self):
        source = '''use core::slice;
use std::{ffi::c_void, ptr};
extern "C" { fn foundation_rust_panic() -> !; }
#[link(name = "c")] extern "C" { fn memcpy(); }
#[link_name = "foundation_rust_panic"] extern "C" { fn fault() -> !; }
fn borrow<'a>(value: &'a [u8]) -> &'a [u8] { value }
const TEXT: &str = r###"use sdl2::video::Window; #[link(name="SDL2")]"###;
const CHAR: char = 'x';
// extern "C" { fn SDL_PollEvent(); }
/* outer /* use fltk::app; */ #[link(name="Rev")] */
'''
        self.assertEqual([], _guard.rust_violations(source))
        for path in _guard.sources(ROOT / 'rust'):
            if path.suffix == '.rs':
                self.assertEqual([], _guard.rust_violations(path.read_text()), str(path))

    def test_rust_application_modules_are_checked_by_real_entry_point(self):
        with tempfile.TemporaryDirectory(prefix='Rust GUI boundary ') as temporary:
            project = Path(temporary).resolve(); root = project / 'gui'; root.mkdir()
            guard = root / 'check_boundary.py'
            guard.write_bytes((ROOT / 'gui/check_boundary.py').read_bytes())
            path = project / 'rust/component/src/nested/codec.rs'
            path.parent.mkdir(parents=True)
            path.write_text('extern "C" { fn SDL_PollEvent(); }\n')
            result = subprocess.run([sys.executable, '-B', str(guard)],
                capture_output=True, text=True, timeout=15)
            self.assertNotEqual(0, result.returncode)
            self.assertIn(str(path), result.stderr)
            path.write_text('use core::slice;\nextern "C" { fn foundation_rust_panic() -> !; }\n')
            result = subprocess.run([sys.executable, '-B', str(guard), '--dependencies'],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(str(path), result.stdout)

    def test_rust_hosts_keep_backend_ownership_and_reject_application_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='Rust host boundary ') as temporary:
            root = Path(temporary) / 'gui'
            (root / 'host').mkdir(parents=True); (root / 'shared').mkdir()
            (root / 'shared/view.rs').write_text('const ID: &str = "records.add";\n')
            host = root / 'host/adapter.rs'
            host.write_text('extern "C" { fn SDL_PollEvent(); }\n')
            self.assertEqual([], _guard.tree_violations(root))
            for source in ('const ID: &str = "records.add";\n', 'use foundation::Store;\n',
                           'use foundation::{Record, Store};\n', 'use foundation::ui::Application;\n'):
                host.write_text(source)
                self.assertTrue(_guard.tree_violations(root), source)

    def test_incremental_build_rechecks_new_and_modified_rust_module(self):
        cmake = (ROOT / 'gui/CMakeLists.txt').read_text()
        block = 'file(GLOB_RECURSE' + cmake.split('file(GLOB_RECURSE', 1)[1].split(
            'add_library(foundation_gui_application STATIC', 1)[0]
        with tempfile.TemporaryDirectory(prefix='incremental Rust boundary ') as temporary:
            project = Path(temporary) / 'source'; root = project / 'gui'; root.mkdir(parents=True)
            (root / 'check_boundary.py').write_bytes((ROOT / 'gui/check_boundary.py').read_bytes())
            (root / 'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(BoundaryGuard LANGUAGES NONE)\n' +
                'find_package(Python3 REQUIRED COMPONENTS Interpreter)\n' + block)
            build = Path(temporary) / 'build'
            subprocess.run(['cmake', '-G', 'Ninja', '-S', str(root), '-B', str(build)],
                check=True, capture_output=True, text=True, timeout=30)
            def check():
                return subprocess.run(['cmake', '--build', str(build), '--target', 'foundation_gui_contract'],
                    capture_output=True, text=True, timeout=30)
            result = check(); self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            path = project / 'rust/component/src/nested/codec.rs'
            path.parent.mkdir(parents=True)
            for contents, accepted in [('use sdl2::event;\n', False), ('use core::slice;\n', True),
                                       ('#[link(name="SDL2")] extern "C" {}\n', False)]:
                path.write_text(contents)
                tick = max(time.time_ns(), path.stat().st_mtime_ns + 10_000_000,
                           (build / 'boundary-checked').stat().st_mtime_ns + 10_000_000)
                os.utime(path, ns=(tick, tick))
                result = check()
                self.assertEqual(accepted, result.returncode == 0, result.stdout + result.stderr)
                if not accepted:
                    self.assertIn('codec.rs', result.stdout + result.stderr)

    def test_composition_hosts_do_not_name_feature_ids(self):
        for path in _guard.sources(ROOT / "gui/hosts"):
            self.assertNotIn('"entries.', path.read_text(), str(path))

    def test_nested_shared_and_host_sources_are_checked_by_real_entry_point(self):
        with tempfile.TemporaryDirectory(prefix="nested GUI boundary ") as directory:
            root = Path(directory).resolve()
            guard = root / "check_boundary.py"
            guard.write_bytes((ROOT / "gui/check_boundary.py").read_bytes())
            paths = [root / "shared/feature/detail/control.hh",
                     root / "host/native/detail/dispatch.ipp",
                     root / "hosts/browser/detail/transport.cpp"]
            for path in paths: path.parent.mkdir(parents=True, exist_ok=True)
            paths[0].write_text('#include <FL/Fl.H>\n')
            for path in paths[1:]: path.write_text('const char* key = "entries.editor";\n')
            result = subprocess.run([sys.executable, "-B", str(guard)],
                capture_output=True, text=True, timeout=15)
            self.assertNotEqual(0, result.returncode)
            for path in paths: self.assertIn(str(path), result.stderr)
            paths[0].write_text('#include <gui/contract.hpp>\n')
            for path in paths[1:]: path.write_text('void generic_dispatch();\n')
            result = subprocess.run([sys.executable, "-B", str(guard)],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_incremental_build_rechecks_added_and_modified_nested_header(self):
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        block = "file(GLOB_RECURSE" + cmake.split("file(GLOB_RECURSE", 1)[1].split(
            "add_library(foundation_gui_application STATIC", 1)[0]
        with tempfile.TemporaryDirectory(prefix="incremental GUI boundary ") as directory:
            root = Path(directory); source = root / "source"; source.mkdir()
            (source / "check_boundary.py").write_bytes((ROOT / "gui/check_boundary.py").read_bytes())
            (source / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(BoundaryGuard LANGUAGES NONE)\n' +
                'find_package(Python3 REQUIRED COMPONENTS Interpreter)\n' + block)
            build = root / "build"
            subprocess.run(["cmake", "-G", "Ninja", "-S", str(source), "-B", str(build)],
                check=True, capture_output=True, text=True, timeout=30)
            def check():
                return subprocess.run(["cmake", "--build", str(build), "--target", "foundation_gui_contract"],
                    capture_output=True, text=True, timeout=30)
            result = check(); self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            path = source / "shared/new/detail/control.hh"; path.parent.mkdir(parents=True)
            def change(content):
                path.write_text(content)
                # Exercise dependency invalidation, independently of filesystem
                # timestamp granularity when edits follow a build immediately.
                tick = max(time.time_ns(), path.stat().st_mtime_ns + 10_000_000,
                           (build / "boundary-checked").stat().st_mtime_ns + 10_000_000)
                os.utime(path, ns=(tick, tick))
            change('#include <FL/Fl.H>\n')
            result = check(); self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("control.hh", result.stdout + result.stderr)
            change('#include <gui/contract.hpp>\n')
            result = check(); self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            change('#include <gui/framebuffer.hpp>\n')
            result = check(); self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("control.hh", result.stdout + result.stderr)
            helper = source / 'helpers/bridge.hpp'; helper.parent.mkdir()
            helper.write_text('void generic_helper();\n')
            change('#include "../../../helpers/bridge.hpp"\n')
            result = check(); self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            nested = helper.parent / 'nested.hpp'; nested.write_text('void another_helper();\n')
            helper.write_text('#include "nested.hpp"\n')
            tick = max(time.time_ns(), helper.stat().st_mtime_ns + 10_000_000,
                       (build / 'boundary-checked').stat().st_mtime_ns + 10_000_000)
            os.utime(helper,ns=(tick,tick))
            result = check(); self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            nested.write_text('#include <FL/Fl.H>\n')
            tick = max(time.time_ns(), nested.stat().st_mtime_ns + 10_000_000,
                       (build / 'boundary-checked').stat().st_mtime_ns + 10_000_000)
            os.utime(nested,ns=(tick,tick))
            result = check(); self.assertNotEqual(0,result.returncode,result.stdout+result.stderr)
            self.assertIn('nested.hpp',result.stdout+result.stderr)

    def test_direct_group_configure_dependencies_have_no_path_aliases(self):
        inputs = (ROOT/'cmake/GuiInputs.cmake').read_text()
        selection = inputs.split('macro(foundation_gui_inputs)', 1)[1].split('if(NOT IS_DIRECTORY', 1)[0]
        # The fixture relocates the reviewed helper's explicit GUI module root.
        selection = 'set(foundation_gui_module_root "${CMAKE_CURRENT_SOURCE_DIR}")\n' + selection
        with tempfile.TemporaryDirectory(prefix='direct retained inputs ') as temporary:
            source=Path(temporary)/'source';(source/'gui').mkdir(parents=True)
            group=source/'third_party/gui-inputs';group.mkdir(parents=True)
            tool=source/'tools/dependency_archive.py';tool.parent.mkdir();tool.write_text('# fixture\n')
            for name in ('manifest.json','SHA256SUMS','gui-inputs.tar.gz'):
                (group/name).write_text('fixture\n')
            # Isolate CMake dependency spelling; archive validity is covered by
            # the real source-group suite and combined direct native build.
            (source/'gui/source_group.py').write_text('print('+repr(json.dumps({'source':str(source/'upstream')}))+')\n')
            (source/'gui/CMakeLists.txt').write_text(selection)
            (source/'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(DirectInputs NONE)\n'
                'find_package(Python3 REQUIRED COMPONENTS Interpreter)\n'
                'function(foundation_register_build_directory)\nendfunction()\n'
                'set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS\n'
                ' "${CMAKE_SOURCE_DIR}/tools/dependency_archive.py"\n'
                ' "${CMAKE_SOURCE_DIR}/third_party/gui-inputs/manifest.json"\n'
                ' "${CMAKE_SOURCE_DIR}/third_party/gui-inputs/SHA256SUMS"\n'
                ' "${CMAKE_SOURCE_DIR}/third_party/gui-inputs/gui-inputs.tar.gz")\n'
                'add_subdirectory(gui)\n')
            for label,arguments in [('default',[]),('explicit-alias',[
                    '-DFOUNDATION_GUI_INPUT_GROUP='+str(source/'gui/../third_party/gui-inputs')])]:
                build=Path(temporary)/label
                for command in (['cmake','-G','Ninja','-S',str(source),'-B',str(build),*arguments],
                                ['cmake','--build',str(build)]):
                    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
                    self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_literal_include_closure_and_aliases_cannot_hide_native_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'gui'
            for directory in ('shared', 'helpers', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            (root / 'shared/app.cpp').write_text('#include "../helpers/bridge.hpp"\n')
            bridge = root / 'helpers/bridge.hpp'
            for contents in ('#include<gui/detail/framebuffer.hpp>\n',
                             '#include "../host/adapter.hpp"\n',
                             'using Native = SDL_Window;\n', '#define BACKEND <FL/Fl.H>\n#include BACKEND\n'):
                bridge.write_text(contents)
                (root / 'host/adapter.hpp').write_text('struct NativeAdapter {};\n')
                failures = _guard.tree_violations(root)
                self.assertTrue(failures, contents)
                self.assertTrue(any('bridge.hpp' in failure for failure in failures))
            bridge.write_text('#include <gui/contract.hpp>\n// SDL_Window is forbidden here.\n')
            self.assertEqual([], _guard.tree_violations(root))
            dependencies = _guard.analyze(root)[1]
            self.assertIn(bridge.resolve(), dependencies)
            bridge.write_text('#include "cycle.hpp"\n')
            (root / 'helpers/cycle.hpp').write_text('#include "bridge.hpp"\n')
            self.assertEqual([], _guard.tree_violations(root))

    def test_include_resolution_preserves_angle_and_quoted_search_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'gui'
            for directory in ('shared', 'helpers'):
                (root / directory).mkdir(parents=True)
            (root / 'shared/app.cpp').write_text('#include "../helpers/bridge.hpp"\n')
            bridge = root / 'helpers/bridge.hpp'
            (root / 'common.hpp').write_text('void public_helper();\n')
            (root / 'helpers/common.hpp').write_text('using Hidden = SDL_Window;\n')
            bridge.write_text('#include <common.hpp>\n')
            self.assertEqual([], _guard.tree_violations(root))
            bridge.write_text('#include "common.hpp"\n')
            self.assertTrue(_guard.tree_violations(root))
            (root / 'common.hpp').write_text('using Hidden = SDL_Window;\n')
            (root / 'helpers/common.hpp').write_text('void sibling_helper();\n')
            bridge.write_text('#include <common.hpp>\n')
            self.assertTrue(_guard.tree_violations(root))
            self.assertTrue(shared_violations('#include_next <hidden.hpp>\n'))

    def test_host_domain_guards_follow_helpers_and_allow_only_composition_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'gui'
            for directory in ('shared', 'helpers', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            (root / 'shared/task.hpp').write_text('class TextTask {};\n')
            (root / 'shared/application.hpp').write_text('#include "task.hpp"\nclass Application {};\n')
            (root / 'shared/view_definition.hpp').write_text('const char* id="records.add";\n')
            main = root / 'hosts/example_main.cpp'
            main.write_text('#include "shared/application.hpp"\nfoundation::ui::Application* app;\n')
            (root / 'host/task.hpp').write_text('void generic_task();\n')
            (root / 'host/service.hpp').write_text('#include "task.hpp"\n')
            self.assertEqual([], _guard.tree_violations(root))
            for source in ('const char* id="records.add";\n', 'foundation::Store entries;\n',
                           'foundation::ui::TextTask task;\n', 'foundation::ui::Application* concrete;\n',
                           '#include "shared/view_definition.hpp"\n'):
                (root / 'host/service.hpp').write_text(source)
                self.assertTrue(_guard.tree_violations(root), source)
            (root / 'host/service.hpp').write_text('#include "../helpers/bridge.hpp"\n')
            (root / 'helpers/bridge.hpp').write_text('#include "../shared/application.hpp"\n')
            self.assertTrue(any('bridge.hpp' in failure for failure in _guard.tree_violations(root)))

    def test_appended_composition_type_does_not_open_generic_host_helpers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'gui'
            for directory in ('shared', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            (root / 'shared/private_view.hpp').write_text('class PrivateView {};\n')
            main = root / 'hosts/appended_main.cpp'
            helper = root / 'host/service.hpp'
            for name, header in (("AppendedApplication", "appended_application.hpp"),
                                 ("AppendedEngineApplication", "appended_engine_application.hpp"),
                                 ("EnginePrimaryRegionApplication", "engine_primary_region_application.hpp"),
                                 ("SemanticPrimaryDocumentApplication", "semantic_primary_document_application.hpp"),
                                 ("AppendedEngineDocumentApplication", "appended_engine_document_application.hpp"),
                                 ("NativeEngineDocumentComposition", "native_engine_document_composition.hpp"),
                                 ("EngineSurfacePort", "appended_engine_application.hpp")):
                (root / 'shared' / header).write_text('class ' + name + ' {};\n')
                main.write_text('#include "shared/' + header + '"\n'
                                'foundation::ui::' + name + '* application;\n')
                self.assertEqual([], _guard.tree_violations(root))
                for source in ('foundation::ui::' + name + '* application;\n',
                               '#include "shared/' + header + '"\n'):
                    helper.write_text(source)
                    self.assertTrue(_guard.tree_violations(root), source)
                helper.unlink()
            for header in ('appended_engine_abi.h', 'appended_engine_module.hpp', 'native_engine_loader.hpp'):
                (root / 'shared' / header).write_text('#include <stdint.h>\n')
                main.write_text('#include "shared/' + header + '"\n')
                self.assertEqual([], _guard.tree_violations(root))
                helper.write_text('#include "shared/' + header + '"\n')
                self.assertTrue(_guard.tree_violations(root))
                helper.unlink()
            startup = root.parent / 'include/foundation/appended/startup.hpp'
            startup.parent.mkdir(parents=True)
            startup.write_text('void load_self();\n')
            main.write_text('#include <foundation/appended/startup.hpp>\n')
            self.assertEqual([], _guard.tree_violations(root))
            helper.write_text('#include <foundation/appended/startup.hpp>\n')
            self.assertTrue(_guard.tree_violations(root))
            helper.unlink()
            main.write_text('void entry() { foundation::ui::prepare_engine_html_package(); }\n')
            self.assertEqual([], _guard.tree_violations(root))
            helper.write_text('void dispatch() { foundation::ui::prepare_engine_html_package(); }\n')
            self.assertTrue(_guard.tree_violations(root))
            helper.unlink()
            for source in ('foundation::ui::PrivateView* state;\n',
                           '#include "shared/private_view.hpp"\n'):
                main.write_text(source)
                self.assertTrue(_guard.tree_violations(root), source)

    def test_demo_services_exact_declaration_and_factory_are_composition_root_only(self):
        with tempfile.TemporaryDirectory(prefix='demo service composition boundary ') as temporary:
            root = Path(temporary) / 'gui'
            for directory in ('shared', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            header = root / 'shared/appended_demo_services.hpp'
            implementation = root / 'shared/appended_demo_services.cpp'
            for path in (header, implementation):
                path.write_bytes((ROOT / 'gui/shared' / path.name).read_bytes())
            main = root / 'hosts/appended_demo_main.cpp'
            source = '#include "../shared/appended_demo_services.hpp"\n' + \
                'void compose() { auto registrations = foundation::ui::demo_native_services(); }\n'
            main.write_text(source)
            failures, dependencies = _guard.analyze(root)
            self.assertEqual([], failures)
            for path in (header, implementation, main):
                self.assertIn(path.resolve(), dependencies)
            extra = root / 'shared/appended_demo_services_extra.hpp'
            extra.write_text('void unrelated_service_factory();\n')
            for forbidden in ('#include "../shared/appended_demo_services_extra.hpp"\n',
                              'void compose() { foundation::ui::demo_native_services_extra(); }\n'):
                with self.subTest(contract=forbidden):
                    main.write_text(forbidden)
                    self.assertTrue(any(str(main) in failure for failure in _guard.tree_violations(root)))
            main.write_text(source)
            helper = root / 'hosts/ordinary_helper.hpp'
            helper.write_text(source)
            self.assertTrue(any(str(helper) in failure for failure in _guard.tree_violations(root)))

    def test_demo_services_factory_name_and_include_stay_out_of_generic_host_helpers(self):
        with tempfile.TemporaryDirectory(prefix='demo service direct helper boundary ') as temporary:
            root = Path(temporary) / 'gui'
            for directory in ('shared', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            for name in ('appended_demo_services.hpp', 'appended_demo_services.cpp'):
                (root / 'shared' / name).write_bytes((ROOT / 'gui/shared' / name).read_bytes())
            (root / 'hosts/appended_demo_main.cpp').write_text(
                '#include "../shared/appended_demo_services.hpp"\n'
                'void compose() { auto registrations = foundation::ui::demo_native_services(); }\n')
            self.assertEqual([], _guard.tree_violations(root))
            helper = root / 'host/service.hpp'
            for source in ('#include "../shared/appended_demo_services.hpp"\n',
                           'void dispatch() { foundation::ui::demo_native_services(); }\n'):
                with self.subTest(source=source):
                    helper.write_text(source)
                    failures = _guard.tree_violations(root)
                    self.assertTrue(any(str(helper) in failure for failure in failures), failures)
            helper.unlink()
            self.assertEqual([], _guard.tree_violations(root))

    def test_demo_services_factory_name_and_include_cannot_escape_through_transitive_helpers(self):
        with tempfile.TemporaryDirectory(prefix='demo service transitive helper boundary ') as temporary:
            root = Path(temporary) / 'gui'
            for directory in ('shared', 'helpers', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            for name in ('appended_demo_services.hpp', 'appended_demo_services.cpp'):
                (root / 'shared' / name).write_bytes((ROOT / 'gui/shared' / name).read_bytes())
            main = root / 'hosts/appended_demo_main.cpp'
            main.write_text('#include "../shared/appended_demo_services.hpp"\n'
                '#include "../helpers/bridge.hpp"\n'
                'void compose() { auto registrations = foundation::ui::demo_native_services(); }\n')
            bridge = root / 'helpers/bridge.hpp'; bridge.write_text('#include "nested.hpp"\n')
            nested = root / 'helpers/nested.hpp'; nested.write_text('void generic_helper();\n')
            failures, dependencies = _guard.analyze(root)
            self.assertEqual([], failures)
            self.assertIn(bridge.resolve(), dependencies)
            self.assertIn(nested.resolve(), dependencies)
            for source in ('#include "../shared/appended_demo_services.hpp"\n',
                           'void dispatch() { foundation::ui::demo_native_services(); }\n'):
                with self.subTest(source=source):
                    nested.write_text(source)
                    failures = _guard.tree_violations(root)
                    self.assertTrue(any(str(nested) in failure for failure in failures), failures)

    def test_demo_service_identity_stays_forbidden_in_roots_and_helpers_after_body_moves(self):
        with tempfile.TemporaryDirectory(prefix='demo service identity boundary ') as temporary:
            root = Path(temporary) / 'gui'
            for directory in ('shared', 'helpers', 'host', 'hosts'):
                (root / directory).mkdir(parents=True)
            header = root / 'shared/appended_demo_services.hpp'
            implementation = root / 'shared/appended_demo_services.cpp'
            for path in (header, implementation):
                path.write_bytes((ROOT / 'gui/shared' / path.name).read_bytes())
            self.assertNotIn('"demo.echo"', header.read_text())
            self.assertIn('"demo.echo"', implementation.read_text())
            main = root / 'hosts/appended_demo_main.cpp'
            main.write_text('#include "../shared/appended_demo_services.hpp"\n'
                '#include "../helpers/bridge.hpp"\n'
                'void compose() { auto registrations = foundation::ui::demo_native_services(); }\n')
            helper = root / 'host/service.hpp'; helper.write_text('void generic_service();\n')
            (root / 'helpers/bridge.hpp').write_text('#include "nested.hpp"\n')
            nested = root / 'helpers/nested.hpp'; nested.write_text('void generic_helper();\n')
            self.assertEqual([], _guard.tree_violations(root))
            for consumer in (main, helper, nested):
                with self.subTest(consumer=consumer.relative_to(root)):
                    source = consumer.read_text()
                    consumer.write_text(source + 'const char* service_name = "demo.echo";\n')
                    failures = _guard.tree_violations(root)
                    self.assertTrue(any(str(consumer) in failure and 'application identity' in failure
                                        for failure in failures), failures)
                    consumer.write_text(source)
            self.assertEqual([], _guard.tree_violations(root))

    def test_demo_services_pure_cmake_leaf_precedes_optional_gui_profiles(self):
        helper_include = 'include("${CMAKE_CURRENT_LIST_DIR}/AppendedDemoServices.cmake")'
        common = (ROOT / 'cmake/AppendedCommon.cmake').read_text()
        gui = (ROOT / 'cmake/AppendedGui.cmake').read_text()
        self.assertEqual(1, common.splitlines().count(helper_include))
        marker = '# Optional compositions share the generic GUI boundary.'
        self.assertEqual(1, gui.count(marker))
        prefix = gui.split(marker, 1)[0]
        self.assertTrue(prefix.startswith(helper_include + '\n'))
        leaf = 'foundation_gui_appended_demo_services'
        terminal = ['foundation_gui_native_terminal_' + kind + mode + '_test'
                    for kind in ('main_', 'actions_main_') for mode in ('web', 'both')]
        # Only declarations before the optional-profile guard are exercised.
        # The real production engine graph and Common's other targets are outside
        # this LANGUAGES NONE fixture; Common's actual helper include is replayed.
        with tempfile.TemporaryDirectory(prefix='demo services cmake declarations ') as temporary:
            root = Path(temporary); source = root / 'source'; cmake = source / 'cmake'
            cmake.mkdir(parents=True)
            (source / 'include').mkdir()
            implementation = source / 'gui/shared/appended_demo_services.cpp'
            implementation.parent.mkdir(parents=True)
            implementation.write_bytes((ROOT / 'gui/shared/appended_demo_services.cpp').read_bytes())
            (cmake / 'AppendedDemoServices.cmake').write_bytes(
                (ROOT / 'cmake/AppendedDemoServices.cmake').read_bytes())
            (cmake / 'AppendedGuiPrefix.cmake').write_text(prefix)
            (cmake / 'CommonDemoServices.cmake').write_text(helper_include + '\n')
            (source / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.20)
project(DemoServicesDeclarations LANGUAGES NONE)
# Select the declaration branch explicitly; no platform executable is built.
set(CMAKE_SYSTEM_NAME Linux)
set(EMSCRIPTEN FALSE)
set(FOUNDATION_NODE_EXECUTABLE "")
function(add_library target)
  file(APPEND "${CMAKE_BINARY_DIR}/add_library.txt" "${target}|${ARGN}\\n")
  _add_library(${target} INTERFACE)
endfunction()
function(add_executable target)
  file(APPEND "${CMAKE_BINARY_DIR}/add_executable.txt" "${target}|${ARGN}\\n")
  _add_library(${target} INTERFACE)
endfunction()
foreach(command target_link_libraries target_include_directories target_compile_features
    set_target_properties add_dependencies foundation_options)
  function(${command} target)
    file(APPEND "${CMAKE_BINARY_DIR}/${CMAKE_CURRENT_FUNCTION}.txt" "${target}|${ARGN}\\n")
  endfunction()
endforeach()
foreach(command target_compile_definitions foundation_gui_check add_test
    foundation_test_prerequisites set_tests_properties)
  function(${command})
  endfunction()
endforeach()
if(COMMON_FIRST)
  include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/CommonDemoServices.cmake")
endif()
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/AppendedGuiPrefix.cmake")
# Both includers and a repeated direct include share the real GLOBAL guard.
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/AppendedDemoServices.cmake")
''')
            for profile, testing, common_first in (('none', False, False), ('none', True, False),
                                                    ('web', True, True), ('both', True, True)):
                with self.subTest(profile=profile, testing=testing, common_first=common_first):
                    build = root / (profile + ('-tests' if testing else '-production'))
                    result = subprocess.run(['cmake', '-S', str(source), '-B', str(build),
                        '-DFOUNDATION_APPENDED_PROFILE=' + profile,
                        '-DBUILD_TESTING=' + ('ON' if testing else 'OFF'),
                        '-DCOMMON_FIRST=' + ('ON' if common_first else 'OFF')],
                        capture_output=True, text=True, timeout=15)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)

                    def records(command):
                        path = build / (command + '.txt')
                        return [line.split('|', 1) for line in path.read_text().splitlines()] \
                            if path.exists() else []

                    self.assertEqual([[leaf, 'STATIC;EXCLUDE_FROM_ALL;' + implementation.as_posix()]],
                                     records('add_library'))
                    expected_executables = ['foundation_gui_terminal_runner_test'] + terminal if testing else []
                    self.assertEqual(expected_executables, [target for target, _ in records('add_executable')])
                    self.assertEqual([[leaf, 'PUBLIC;' + (source / 'include').as_posix()]],
                        [record for record in records('target_include_directories') if record[0] == leaf])
                    self.assertEqual([[leaf, 'PUBLIC;cxx_std_20']],
                        [record for record in records('target_compile_features') if record[0] == leaf])
                    self.assertEqual([[leaf, 'PROPERTIES;CXX_EXTENSIONS;OFF']],
                        [record for record in records('set_target_properties') if record[0] == leaf])
                    self.assertEqual([[leaf, '']],
                        [record for record in records('foundation_options') if record[0] == leaf])
                    self.assertFalse([record for record in records('add_dependencies') if record[0] == leaf])
                    links = records('target_link_libraries')
                    expected_links = [['foundation_gui_terminal_runner_test', 'PRIVATE;foundation_gui_boundary']]
                    expected_links += [[target, 'PRIVATE;foundation_gui_boundary;' + leaf] for target in terminal]
                    self.assertEqual(expected_links if testing else [], links)
                    cache = (build / 'CMakeCache.txt').read_text()
                    self.assertNotIn('CMAKE_C_COMPILER:', cache)
                    self.assertNotIn('CMAKE_CXX_COMPILER:', cache)

    def test_header_mirror_uses_final_patch_bytes_and_preserves_incremental_outputs(self):
        inputs = (ROOT / 'cmake/GuiInputs.cmake').read_text()
        patcher = 'function(foundation_gui_patch' + inputs.split('function(foundation_gui_patch',1)[1].split('endfunction()',1)[0] + 'endfunction()\n'
        repatcher = 'function(foundation_gui_repatch' + inputs.split('function(foundation_gui_repatch',1)[1].split('endfunction()',1)[0] + 'endfunction()\n'
        mirror = inputs.split('macro(foundation_gui_headers)', 1)[1].split('endmacro()', 1)[0]
        with tempfile.TemporaryDirectory(prefix='patched header mirror ') as temporary:
            root = Path(temporary); source = root / 'source'; source.mkdir()
            upstream = source / 'upstream/include/gui'; upstream.mkdir(parents=True)
            patches = source / 'patches'; patches.mkdir()
            (patches / 'apply.py').write_bytes((ROOT / 'gui/patches/apply.py').read_bytes())
            names = [('contract','touch-contract'),('memory_adapter','touch-memory'),
                     ('interaction','touch-interaction'),('runtime','file-services'),
                     ('terminal','terminal-caret'),('web','web-tick'),('bitmap','bitmap-copy'),
                     ('text','masked-text-policy'),('framebuffer','masked-text-framebuffer'),
                     ('presentation','masked-text-presentation')]
            for name, patch in names:
                old = 'inline constexpr int ' + name + '_value=1;\n'
                new = old.replace('=1;', '=2;')
                (upstream / (name+'.hpp')).write_text(old)
                (patches / (patch+'.patch')).write_text('--- old\n+++ new\n@@ -1 +1 @@\n-'+old+'+'+new)
            stages = [('contract','context-contract',2),('contract','shortcut-contract',3),
                      ('contract','availability-path',4),('contract','masked-text-contract',5),
                      ('contract','nonvisual-command-contract',6),
                      ('contract','text-frame-contract',7),('framebuffer','text-frame-framebuffer',2),
                      ('interaction','context-interaction',2),
                      ('interaction','shortcut-interaction',3),('interaction','masked-text-interaction',4),
                      ('interaction','wheel-chaining-interaction',5),
                      ('memory_adapter','shortcut-memory',2),('memory_adapter','nonvisual-command-memory',3),('terminal','terminal-shortcuts',2),
                      ('terminal','masked-text-terminal',3)]
            for name, patch, value in stages:
                old = 'inline constexpr int ' + name + '_value=' + str(value) + ';\n'
                new = old.replace('='+str(value)+';', '='+str(value+1)+';')
                (patches / (patch+'.patch')).write_text('--- old\n+++ new\n@@ -1 +1 @@\n-'+old+'+'+new)
            final_values = {'contract':8,'interaction':6,'memory_adapter':4,'terminal':4,'framebuffer':3}
            (upstream / 'removed.hpp').write_text('inline constexpr int obsolete=1;\n')
            (upstream / 'other.hpp').write_text(''.join('#include "'+name+'.hpp"\n' for name,_ in names))
            (source / 'main.cpp').write_text('#include <gui/other.hpp>\n' +
                ''.join('static_assert('+name+'_value=='+str(final_values.get(name,2))+');\n' for name,_ in names)+'int main(){return 0;}\n')
            project = 'cmake_minimum_required(VERSION 3.24)\nproject(HeaderMirror LANGUAGES CXX)\nfind_package(Python3 REQUIRED COMPONENTS Interpreter)\n'
            project += 'set(FOUNDATION_GUI_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/upstream")\n'
            project += 'set(foundation_gui_module_root "${CMAKE_CURRENT_SOURCE_DIR}")\n'
            project += 'file(GLOB verified_files "${FOUNDATION_GUI_SOURCE}/include/gui/*")\n'
            project += patcher + repatcher + mirror + 'foundation_gui_patch(include/gui/web.hpp web-tick.patch include/gui/web.hpp)\n'
            project += 'add_executable(mirror main.cpp)\ntarget_compile_features(mirror PRIVATE cxx_std_20)\n'
            project += 'target_include_directories(mirror PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/include" "${FOUNDATION_GUI_SOURCE}/include")\n'
            (source / 'CMakeLists.txt').write_text(project)
            build = root / 'build'
            configure = ['cmake','-G','Ninja','-S',str(source),'-B',str(build)]
            compile = ['cmake','--build',str(build)]
            for command in (configure,compile):
                subprocess.run(command,check=True,capture_output=True,text=True,timeout=45)
            for name in ('contract', 'interaction'):
                self.assertIn(name+'_value='+str(final_values[name]), (build/'include/gui'/(name+'.hpp')).read_text())
                self.assertIn(name+'_value=2', (build/'patch-inputs'/(name+'-touch.hpp')).read_text())
            outputs = list((build/'include/gui').glob('*.hpp')) + list((build/'CMakeFiles/mirror.dir').rglob('*.o')) + list((build/'CMakeFiles/mirror.dir').rglob('*.obj'))
            self.assertGreater(len(outputs),5)
            before = {path: (path.read_bytes(),path.stat().st_mtime_ns) for path in outputs}
            for command in (configure,compile):
                subprocess.run(command,check=True,capture_output=True,text=True,timeout=45)
            self.assertEqual(before,{path:(path.read_bytes(),path.stat().st_mtime_ns) for path in outputs})
            # A reviewed supplier inventory upgrade cannot leave stale generated
            # headers visible only to incremental consumers.
            (upstream/'removed.hpp').unlink()
            remaining={path:value for path,value in before.items() if path.name!='removed.hpp'}
            for command in (configure,compile):
                subprocess.run(command,check=True,capture_output=True,text=True,timeout=45)
            self.assertFalse((build/'include/gui/removed.hpp').exists())
            self.assertEqual(remaining,{path:(path.read_bytes(),path.stat().st_mtime_ns) for path in remaining})
            self.assertIn('contract_value=1', (upstream/'contract.hpp').read_text())

    def test_shared_declaration_has_one_construction_and_layout_source(self):
        source = (ROOT / "gui/shared/application.cpp").read_text()
        definition = (ROOT / "gui/shared/view_definition.hpp").read_text()
        self.assertIn("definition : view_definition", source)
        self.assertIn("definition.height", source)
        for identity in ("entries.heading", "entries.editor", "entries.add", "entries.remove"):
            self.assertEqual(1, definition.count('"' + identity + '"'))
        for path in (ROOT / "gui/patches").glob("*.patch"):
            self.assertNotIn('"entries.', path.read_text(), str(path))
        visual = (ROOT / "gui/tests/visual_test.py").read_text()
        self.assertIn("negative_checks(images['framebuffer'], baseline)", visual)

    def test_dependency_lock_is_complete_for_consumed_inputs(self):
        lock = json.loads((ROOT / "third_party/gui-boundary.lock.json").read_text())
        self.assertRegex(lock["revision"], r"^[0-9a-f]{40}$")
        self.assertRegex(lock["source_tree"], r"^[0-9a-f]{40}$")
        for path in ("include/gui/contract.hpp", "include/gui/layout.hpp",
                     "include/gui/terminal.hpp", "include/gui/framebuffer.hpp",
                     "backends/terminal/main.cpp", "backends/fltk/adapter.hpp",
                     "backends/rev/adapter.cpp", "backends/framebuffer/main_sdl.cpp",
                     "backends/web/renderer.mjs", "backends/web/host.py",
                     "cmake/PrepareRev.cmake", "third_party/rev/SHA256SUMS"):
            self.assertIn(path, lock["files"])
        for path, digest in lock["files"].items():
            self.assertFalse(Path(path).is_absolute())
            self.assertNotIn("..", Path(path).parts)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual("CC0-1.0", lock["license"])
        self.assertIn("LICENSE", lock["redistribution"]["license_files"])
        for notice in lock["redistribution"]["license_files"]:
            self.assertIn(notice, lock["files"])


    def test_typed_host_contract_has_no_feature_dispatch(self):
        for path in (ROOT / "gui/host").glob("*.hpp"):
            self.assertNotIn('"entries.', path.read_text())
            self.assertNotIn("foundation::Store", path.read_text())
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        self.assertNotIn("using Example", cmake)
        self.assertNotIn('"entries.', cmake)
        self.assertNotIn("foundation::Store", cmake)
        selector = 'string(REPLACE "_" "-" _native_surface_selector "${_native_surface_fixture}")'
        self.assertEqual(1, cmake.count(selector))
        self.assertNotIn("string(REPLACE", cmake.replace(selector, ""))
        for name in ("FLTK", "SDL", "REV", "WEB"):
            self.assertIn("FOUNDATION_GUI_" + name, cmake)

    def windows_macro_fixture(self, *, windows, remove_guard=False):
        # Execute the real shared interface, application linkage and host factory.
        # Windows uses its actual platform header; other hosts reproduce only
        # that header's conditional min/max definitions for the same compile test.
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        inputs = (ROOT / "cmake/GuiInputs.cmake").read_text()
        boundary = "add_library(foundation_gui_boundary INTERFACE)" + inputs.split(
            "add_library(foundation_gui_boundary INTERFACE)", 1)[1].split("endmacro()", 1)[0]
        application = "add_library(foundation_gui_application STATIC" + cmake.split(
            "add_library(foundation_gui_application STATIC", 1)[1].split("function(gui_warnings", 1)[0]
        host = "function(foundation_gui_executable" + cmake.split(
            "function(foundation_gui_executable", 1)[1].split("endfunction()", 1)[0] + "endfunction()\n"
        with tempfile.TemporaryDirectory(prefix="gui Windows macros ") as directory:
            source = Path(directory) / "source"; source.mkdir()
            (source / "shared").mkdir(); (source / "include").mkdir()
            # The real application fragment declares optional generic targets.
            # Supply their actual sources; EXCLUDE_FROM_ALL keeps this build
            # focused on the direct and application-linked macro consumers.
            for original, relative in (("src/gui/surface.cpp", "src/gui/surface.cpp"),
                    ("gui/host/native_surface.cpp", "host/native_surface.cpp"),
                    ("gui/host/native_editor_capture.cpp", "host/native_editor_capture.cpp")):
                destination = source / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((ROOT / original).read_bytes())
            header = """#pragma once
#include <algorithm>
#ifdef FIXTURE_WINDOWS_HEADERS
#ifdef _WIN32
#include <windows.h>
#elif !defined(NOMINMAX)
#define min(a,b) (((a)<(b))?(a):(b))
#define max(a,b) (((a)>(b))?(a):(b))
#endif
#else
#ifdef NOMINMAX
#error Non-Windows consumers must not inherit NOMINMAX
#endif
#endif
inline int generic_extent() { return std::min(4, std::max(1, 2)); }
"""
            (source / "collision.hpp").write_text(header, encoding="utf-8")
            (source / "shared/application.cpp").write_text(
                '#include "collision.hpp"\nint shared_extent() { return generic_extent(); }\n', encoding="utf-8")
            (source / "host.cpp").write_text(
                '#include "collision.hpp"\nint shared_extent();\nint main() { return shared_extent() != generic_extent(); }\n', encoding="utf-8")
            (source / "direct.cpp").write_text(
                '#include "collision.hpp"\nint main() { return generic_extent() != 2; }\n', encoding="utf-8")
            project = """cmake_minimum_required(VERSION 3.24)
project(WindowsGuiHeaderContract LANGUAGES CXX)
set(FOUNDATION_GUI_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}")
set(EMSCRIPTEN OFF)
add_library(Threads::Threads INTERFACE IMPORTED)
add_library(fixture_core INTERFACE)
add_library(foundation::core ALIAS fixture_core)
add_custom_target(foundation_gui_contract)
add_custom_target(foundation-gui-hosts)
function(foundation_options target)
endfunction()
"""
            project += "set(WIN32 " + ("ON" if windows else "OFF") + ")\n"
            if windows:
                project += "add_compile_definitions(FIXTURE_WINDOWS_HEADERS)\n"
            project += boundary
            if remove_guard:
                project += "set_property(TARGET foundation_gui_boundary PROPERTY INTERFACE_COMPILE_DEFINITIONS \"\")\n"
            project += application + host + """
foundation_gui_executable(foundation-gui-fixture host.cpp)
add_executable(direct_boundary_consumer direct.cpp)
target_link_libraries(direct_boundary_consumer PRIVATE gui_boundary)
"""
            (source / "CMakeLists.txt").write_text(project, encoding="utf-8")
            build = Path(directory) / "build"
            configured = subprocess.run(["cmake", "-G", "Ninja", "-S", str(source), "-B", str(build)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            self.assertEqual(0, configured.returncode, configured.stdout)
            return subprocess.run(["cmake", "--build", str(build), "--config", "Debug", "--parallel", "2"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)

    def test_windows_shared_interface_prevents_native_min_max_macro_collision(self):
        guarded = self.windows_macro_fixture(windows=True)
        self.assertEqual(0, guarded.returncode, guarded.stdout)
        unguarded = self.windows_macro_fixture(windows=True, remove_guard=True)
        self.assertNotEqual(0, unguarded.returncode, "The negative control must expose the platform macro collision")
        self.assertIn("collision.hpp", unguarded.stdout)

    def test_non_windows_shared_interface_does_not_add_windows_macro_policy(self):
        result = self.windows_macro_fixture(windows=False)
        self.assertEqual(0, result.returncode, result.stdout)

    def test_sdl_host_and_deliverable_checks_select_declared_native_display(self):
        self.sdl_display_fixture()

    def test_sdl_display_discovery_selects_multiconfig_configuration(self):
        self.sdl_display_fixture("Ninja Multi-Config")

    def sdl_display_fixture(self, generator=None):
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        setup = "function(foundation_gui_sdl_display_test " + cmake.split(
            "function(foundation_gui_sdl_display_test ", 1)[1].split("endfunction()", 1)[0] + "endfunction()\n"
        installed = "foreach(backend IN LISTS smoke_backends)" + cmake.split(
            "foreach(backend IN LISTS smoke_backends)", 1)[1].split("endforeach()", 1)[0] + "endforeach()\n"
        native = "foundation_gui_executable(foundation_gui_sdl_test" + cmake.split(
            "foundation_gui_executable(foundation_gui_sdl_test", 1)[1].split("endif()", 1)[0]
        project = """cmake_minimum_required(VERSION 3.24)
project(NativeSdlDisplay LANGUAGES NONE)
enable_testing()
set(smoke_backends sdl)
set(Python3_EXECUTABLE "${CMAKE_COMMAND}")
add_executable(foundation-gui-sdl IMPORTED)
set_target_properties(foundation-gui-sdl PROPERTIES IMPORTED_LOCATION "${CMAKE_COMMAND}")
function(foundation_gui_executable)
endfunction()
function(target_link_libraries)
endfunction()
function(foundation_gui_check name target labels)
    add_test(NAME foundation.gui.${name} COMMAND "${CMAKE_COMMAND}" --version)
endfunction()
"""
        project += 'include("' + (ROOT / 'cmake/TestPrerequisites.cmake').as_posix() + '")\n'
        with tempfile.TemporaryDirectory(prefix="SDL native display ") as directory:
            root = Path(directory)
            for system, driver in (("Linux", "x11"), ("Windows", "windows"), ("Other", None)):
                with self.subTest(system=system):
                    source = root / system; source.mkdir()
                    (source / "CMakeLists.txt").write_text(project + 'set(CMAKE_SYSTEM_NAME "' + system + '")\n' +
                                                          setup + installed + native)
                    build = source / "build"
                    command = ["cmake", "-S", str(source), "-B", str(build)]
                    if generator is not None: command += ["-G", generator]
                    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                    if driver is None:
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn("Declare the native SDL video driver", result.stderr)
                        continue
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    # Multi-configuration generators guard test definitions by
                    # configuration even when this fixture builds no executable.
                    result = subprocess.run(["ctest", "--test-dir", str(build), "-C", "Debug", "--show-only=json-v1"],
                        capture_output=True, text=True, check=True, timeout=15)
                    tests = json.loads(result.stdout)["tests"]
                    self.assertEqual({"foundation.gui.installed-sdl", "foundation.gui.sdl-host"},
                                     {test["name"] for test in tests})
                    for test in tests:
                        properties = {item["name"]: item["value"] for item in test["properties"]}
                        self.assertEqual(["SDL_VIDEODRIVER=" + driver], properties["ENVIRONMENT"])
                        self.assertEqual(["foundation_native_display"], properties["RESOURCE_LOCK"])

    def sdl_link_fixture(self, *, portable, static_available=True, remove_selection=False):
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        block = (ROOT / "cmake/GuiNativeBackends.cmake").read_text() + "\nif(FOUNDATION_GUI_SDL)\n" + cmake.split("if(FOUNDATION_GUI_SDL)\n", 1)[1].split(
            "\nif(FOUNDATION_GUI_REV)", 1)[0]
        native_test = "foundation_gui_executable(foundation_gui_sdl_test" + cmake.split(
            "foundation_gui_executable(foundation_gui_sdl_test", 1)[1].split(
            "foundation_gui_check(sdl-host", 1)[0]
        if remove_selection:
            block = block.replace("INTERFACE SDL2::SDL2-static)", "INTERFACE SDL2::SDL2)")
        with tempfile.TemporaryDirectory(prefix="SDL linkage ") as temporary:
            root = Path(temporary); source = root / "source"; source.mkdir()
            peer = source / "host/native_sdl_surface_peer.cpp"
            peer.parent.mkdir()
            peer.write_bytes((ROOT / "gui/host/native_sdl_surface_peer.cpp").read_bytes())
            (source / "static.c").write_text("int fixture_value(void) { return 3; }\n")
            (source / "shared.c").write_text("int fixture_value(void) { return 7; }\n")
            (source / "entry.c").write_text("int fixture_value(void); int fixture_entry(void) { return fixture_value(); }\n")
            (source / "main.c").write_text("int fixture_entry(void); int main(void) { return fixture_entry() != " +
                                           ("3" if portable else "7") + "; }\n")
            config = """add_library(fixture_shared SHARED "${CMAKE_CURRENT_SOURCE_DIR}/shared.c")
set_target_properties(fixture_shared PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
add_library(SDL2::SDL2 ALIAS fixture_shared)
add_library(fixture_entry STATIC "${CMAKE_CURRENT_SOURCE_DIR}/entry.c")
add_library(SDL2::SDL2main ALIAS fixture_entry)
"""
            if static_available:
                config += """add_library(fixture_static STATIC "${CMAKE_CURRENT_SOURCE_DIR}/static.c")
add_library(SDL2::SDL2-static ALIAS fixture_static)
"""
            (source / "SDL2Config.cmake").write_text(config)
            project = """cmake_minimum_required(VERSION 3.24)
project(PortableSdlSelection LANGUAGES C CXX)
set(SDL2_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
set(FOUNDATION_GUI_SDL ON)
add_custom_target(foundation_gui_contract)
function(foundation_options target)
endfunction()
function(foundation_gui_patch)
endfunction()
function(foundation_gui_executable name source)
    add_executable(${name} "${CMAKE_CURRENT_SOURCE_DIR}/main.c")
endfunction()
"""
            project += "set(FOUNDATION_PORTABLE " + ("ON" if portable else "OFF") + ")\n" + block + "\n" + native_test
            (source / "CMakeLists.txt").write_text(project)
            build = root / "build"
            configured = subprocess.run(["cmake", "-G", "Ninja", "-S", str(source), "-B", str(build)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            if portable and not static_available:
                self.assertNotEqual(0, configured.returncode)
                self.assertIn("Portable SDL requires the retained SDL2::SDL2-static target", configured.stdout)
                return []
            self.assertEqual(0, configured.returncode, configured.stdout)
            built = subprocess.run(["cmake", "--build", str(build), "--config", "Debug", "--parallel", "2"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
            self.assertEqual(0, built.returncode, built.stdout)
            return [subprocess.run([str(next(p for p in build.glob(name + "*") if p.is_file() and
                p.suffix in ("", ".exe")))], cwd=build, capture_output=True, timeout=10).returncode
                for name in ("foundation-gui-sdl", "foundation_gui_sdl_test")]

    def test_portable_sdl_host_and_test_use_static_supplier_target(self):
        self.assertEqual([0, 0], self.sdl_link_fixture(portable=True))
        self.assertEqual([1, 1], self.sdl_link_fixture(portable=True, remove_selection=True),
                         "Both consumers must expose the incorrect shared linkage")

    def test_ordinary_sdl_preserves_shared_target_and_portable_requires_static(self):
        self.assertEqual([0, 0], self.sdl_link_fixture(portable=False))
        self.assertEqual([], self.sdl_link_fixture(portable=True, static_available=False))

    def rev_dependency_configuration(self, *, sdk=False, bundled=None, windows=False):
        # Execute the real composition block in CMake. The fixture replaces only
        # the toolkit build, so this stays independent of native SDK availability.
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        block = cmake.split("if(FOUNDATION_GUI_REV)\n", 1)[1].split("\nendif()", 1)[0] + "\nendif()\n"
        block = (ROOT / "cmake/GuiNativeBackends.cmake").read_text() + "\nif(FOUNDATION_GUI_REV)\n" + block
        with tempfile.TemporaryDirectory(prefix="rev dependency ") as directory:
            root = Path(directory)
            source = root / "source"; source.mkdir()
            peer = source / "host/native_rev_surface_peer.cpp"
            peer.parent.mkdir()
            peer.write_bytes((ROOT / "gui/host/native_rev_surface_peer.cpp").read_bytes())
            (source / "toolkit.cpp").write_text("void fixture_rev_toolkit() {}\n")
            project = """cmake_minimum_required(VERSION 3.24)
project(RevDependencySelection LANGUAGES CXX)
set(FOUNDATION_GUI_REV ON)
add_custom_target(foundation_gui_contract)
function(foundation_options target)
endfunction()
function(foundation_gui_repatch source patch output)
    foundation_gui_patch("${source}" "${patch}" "${output}")
endfunction()
function(foundation_gui_patch source patch output)
    if(output STREQUAL "Rev.cmake")
        file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/Rev.cmake" [=[
option(GUI_REV_BUNDLED_DEPS "Retained dependencies" ${WIN32})
if(GUI_REV_BUNDLED_DEPS)
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/selection.txt" "retained")
else()
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/selection.txt" "system")
endif()
add_library(gui_rev_toolkit STATIC EXCLUDE_FROM_ALL "${CMAKE_CURRENT_SOURCE_DIR}/toolkit.cpp")
]=])
    endif()
endfunction()
function(foundation_gui_executable)
endfunction()
function(target_link_libraries)
endfunction()
"""
            project += "set(WIN32 " + ("ON" if windows else "OFF") + ")\n"
            if sdk:
                project += 'set(FOUNDATION_SDK_ROOT "retained SDK")\n'
            (source / "CMakeLists.txt").write_text(project + block, encoding="utf-8")
            command = ["cmake", "-G", "Ninja", "-S", str(source), "-B", str(root / "build")]
            if bundled is not None:
                command.append("-DGUI_REV_BUNDLED_DEPS=" + bundled)
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=30)
            selected = root / "build/selection.txt"
            return result, selected.read_text() if selected.exists() else None

    def test_prepared_sdk_rev_selects_retained_dependencies(self):
        for setting in (None, "ON"):
            with self.subTest(setting=setting):
                result, selected = self.rev_dependency_configuration(sdk=True, bundled=setting)
                self.assertEqual(0, result.returncode, result.stdout)
                self.assertEqual("retained", selected)

    def test_prepared_sdk_rev_rejects_system_dependency_override(self):
        result, selected = self.rev_dependency_configuration(sdk=True, bundled="OFF")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Prepared SDK Rev requires GUI_REV_BUNDLED_DEPS=ON", result.stdout)
        self.assertIsNone(selected, "Reject the conflict before entering the toolkit build")

    def test_local_rev_dependency_defaults_and_overrides_remain_available(self):
        for windows, setting, expected in ((False, None, "system"), (False, "ON", "retained"),
                                            (True, None, "retained"), (True, "OFF", "system")):
            with self.subTest(windows=windows, setting=setting):
                result, selected = self.rev_dependency_configuration(windows=windows, bundled=setting)
                self.assertEqual(0, result.returncode, result.stdout)
                self.assertEqual(expected, selected)

    def fltk_static_link_fixture(self, *, sdk):
        # Model the SDK's autotools FindFLTK result: the static archive itself
        # omits its Xft closure. Every imported edge must reach the final link.
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        block = (ROOT / "cmake/GuiNativeBackends.cmake").read_text() + "\nif(FOUNDATION_GUI_FLTK)\n" + cmake.split("if(FOUNDATION_GUI_FLTK)\n", 1)[1].split(
            "\nif(FOUNDATION_GUI_SDL)", 1)[0]
        with tempfile.TemporaryDirectory(prefix="fltk dependency ") as directory:
            root = Path(directory); source = root / "source"; source.mkdir()
            units = {
                "main": "int fltk_entry(void); int main(void) { return fltk_entry(); }",
                "fltk": "int xft_entry(void); int fltk_entry(void) { return xft_entry(); }",
                "xft": "int render_entry(void); int font_entry(void); int type_entry(void); "
                       "int xft_entry(void) { return render_entry()+font_entry()+type_entry(); }",
                "render": "int render_entry(void) { return 0; }",
                "font": "int font_entry(void) { return 0; }",
                "type": "int type_entry(void) { return 0; }"}
            for name, content in units.items():
                (source / (name + ".c")).write_text(content, encoding="utf-8")
            (source / "FindFLTK.cmake").write_text(
                "set(FLTK_LIBRARIES fixture_fltk)\nset(FLTK_FOUND TRUE)\n", encoding="utf-8")
            (source / "FindX11.cmake").write_text("""
if(NOT "Xft" IN_LIST X11_FIND_COMPONENTS OR NOT "Xrender" IN_LIST X11_FIND_COMPONENTS)
    message(FATAL_ERROR "The SDK must require the static toolkit dependencies")
endif()
foreach(name xft render font type)
    add_library(fixture_${name} STATIC "${CMAKE_CURRENT_SOURCE_DIR}/${name}.c")
endforeach()
add_library(X11::Xft ALIAS fixture_xft)
add_library(X11::Xrender ALIAS fixture_render)
add_library(Fontconfig::Fontconfig ALIAS fixture_font)
add_library(Freetype::Freetype ALIAS fixture_type)
target_link_libraries(fixture_xft PUBLIC X11::Xrender Fontconfig::Fontconfig Freetype::Freetype)
""", encoding="utf-8")
            project = """cmake_minimum_required(VERSION 3.24)
project(StaticToolkitClosure LANGUAGES C)
list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}")
set(FOUNDATION_GUI_FLTK ON)
set(CMAKE_SYSTEM_NAME Linux)
add_library(fixture_fltk STATIC fltk.c)
function(foundation_gui_patch)
endfunction()
function(foundation_gui_repatch)
endfunction()
function(foundation_gui_executable name source)
    add_executable(${name} "${CMAKE_CURRENT_SOURCE_DIR}/main.c")
endfunction()
"""
            if sdk:
                project += 'set(FOUNDATION_SDK_ROOT "retained SDK")\n'
            (source / "CMakeLists.txt").write_text(project + block, encoding="utf-8")
            result = subprocess.run(["cmake", "-G", "Ninja", "-S", str(source), "-B", str(root / "build")],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stdout)
            return subprocess.run(["cmake", "--build", str(root / "build"), "--config", "Debug",
                                   "--parallel", "2", "--target", "foundation-gui-fltk"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)

    def test_prepared_sdk_fltk_carries_complete_static_link_dependencies(self):
        with_sdk = self.fltk_static_link_fixture(sdk=True)
        self.assertEqual(0, with_sdk.returncode, with_sdk.stdout)
        # Negative control proves the fixture actually needs the new closure.
        without_sdk_closure = self.fltk_static_link_fixture(sdk=False)
        self.assertNotEqual(0, without_sdk_closure.returncode)
        self.assertIn("xft_entry", without_sdk_closure.stdout)

    def test_patch_application_is_exact_and_fail_closed(self):
        spec = importlib.util.spec_from_file_location("gui_patch", ROOT / "gui/patches/apply.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        patch = "--- old\n+++ new\n@@ -1,2 +1,2 @@\n first\n-old\n+new\n"
        self.assertEqual("first\nnew\n", module.apply("first\nold\n", patch))
        for source in ("different\nold\n", "first\nchanged\n", "prefix\nfirst\nold\n"):
            with self.assertRaises(ValueError): module.apply(source, patch)
        with self.assertRaises(ValueError): module.apply("first\nold\n", patch.replace("-1,2", "-1,3"))

    def test_portability_patches_select_exact_generated_tests_and_preserve_inputs(self):
        # Execute the actual patch function and upstream target-selection block.
        # Full behavior stays in the upstream executable tests; this fixture
        # detects compiling the unchanged supplier file or losing patch inputs.
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        inputs = (ROOT / "cmake/GuiInputs.cmake").read_text()
        patch_function = "function(foundation_gui_patch" + inputs.split(
            "function(foundation_gui_patch", 1)[1].split("endfunction()", 1)[0] + "endfunction()\n"
        tests = "foreach(test_name contract " + cmake.split(
            "foreach(test_name contract ", 1)[1].split("endforeach()", 1)[0] + "endforeach()\n"
        lock = json.loads((ROOT / "third_party/gui-boundary.lock.json").read_text())
        declared = {entry.split(": ", 1)[0] for entry in lock["patches"]}
        with tempfile.TemporaryDirectory(prefix="GUI test patches ") as temporary:
            source = Path(temporary) / "source"; source.mkdir()
            upstream = source / "upstream"; (upstream / "tests").mkdir(parents=True)
            (source / "patches").mkdir()
            (source / "patches/apply.py").write_bytes((ROOT / "gui/patches/apply.py").read_bytes())
            originals = {}
            for name in ("contract", "adapter"):
                patch_name = "gui/patches/" + name + "-portability.patch"
                self.assertIn(patch_name, declared)
                patch = (ROOT / patch_name).read_text(encoding="utf-8")
                (source / "patches" / Path(patch_name).name).write_text(patch, encoding="utf-8")
                lines = patch.splitlines(keepends=True)
                start = int(re.match(r"@@ -(\d+)", lines[2]).group(1))
                original = "\n" * (start - 1) + "".join(line[1:] for line in lines[3:] if line.startswith((" ", "-")))
                path = upstream / "tests" / (name + "_test.cpp")
                path.write_text(original, encoding="utf-8"); originals[name] = path.read_bytes()
            for name in ("bitmap", "layout", "runtime", "presentation", "extension", "interaction", "framebuffer", "terminal", "web"):
                (upstream / "tests" / (name + "_test.cpp")).write_text("int main() { return 0; }\n")
            project = """cmake_minimum_required(VERSION 3.24)
project(PatchedSupplierTests LANGUAGES CXX)
set(FOUNDATION_GUI_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/upstream")
add_library(foundation_gui_boundary INTERFACE)
function(foundation_options target)
    target_compile_features(${target} PRIVATE cxx_std_20)
endfunction()
function(foundation_gui_check)
endfunction()
"""
            project += 'set(Python3_EXECUTABLE "' + Path(sys.executable).as_posix() + '")\n'
            project += 'set(foundation_gui_module_root "${CMAKE_CURRENT_SOURCE_DIR}")\n'
            project += patch_function + tests
            for name in ("contract", "adapter", "bitmap"):
                project += 'get_target_property(selected foundation_gui_upstream_' + name + ' SOURCES)\n'
                project += 'file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/' + name + '.source" "${selected}")\n'
            (source / "CMakeLists.txt").write_text(project, encoding="utf-8")
            build = Path(temporary) / "build"
            result = subprocess.run(["cmake", "-G", "Ninja", "-S", str(source), "-B", str(build)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stdout)
            for name in ("contract", "adapter"):
                generated = build / "tests" / (name + "_test.cpp")
                self.assertEqual(generated.resolve(strict=True), Path((build / (name + ".source")).read_text()).resolve(strict=True))
                self.assertIn("MemoryAdapter* active=nullptr;", generated.read_text())
                self.assertEqual(originals[name], (upstream / "tests" / (name + "_test.cpp")).read_bytes())
            self.assertEqual((upstream / "tests/bitmap_test.cpp").resolve(strict=True), Path((build / "bitmap.source").read_text()).resolve(strict=True))
            changed = upstream / "tests/contract_test.cpp"
            changed.write_text(changed.read_text().replace("const Event& event", "const Event& changed", 1))
            rejected = subprocess.run(["cmake", "-G", "Ninja", "-S", str(source), "-B", str(Path(temporary) / "rejected")],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            self.assertNotEqual(0, rejected.returncode)
            self.assertIn("Patch context differs", rejected.stdout)

    def test_browser_startup_diagnostics_survive_cleanup(self):
        spec = importlib.util.spec_from_file_location("gui_browser", ROOT / "gui/tests/browser_test.py")
        browser = importlib.util.module_from_spec(spec); spec.loader.exec_module(browser)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "startup failed"):
                with browser.browser_workspace(output) as work:
                    (work / "chromedriver.log").write_text("startup evidence")
                    raise RuntimeError("startup failed")
            self.assertEqual("startup evidence", (output / "chromedriver.log").read_text())
            self.assertFalse(any(path.name.startswith("browser-") for path in output.iterdir()))

    def test_browser_transport_has_bounded_worker_and_cleanup(self):
        source = (ROOT / "gui/hosts/web_host.py").read_text()
        self.assertIn("queue.Queue(1)", source)
        self.assertIn("self.worker.join(timeout=2)", source)
        self.assertNotIn("select.select", source)


class BrowserOwnerTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("owned_browser", ROOT / "gui/tests/browser_test.py")
        self.browser = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.browser)

    def instance(self, cls, log, owner):
        instance = cls.__new__(cls)
        instance.owner = owner; instance.log = log
        instance.closed = False; instance.cleanup_error = None
        instance.socket = None; instance.session = None
        return instance

    def test_firefox_accepts_delayed_startup_without_extending_protocol_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); elapsed = [0.0]; attempts = []; connection = mock.Mock()
            owner = mock.Mock(); owner.process.poll.return_value = None
            def connect(address, *, timeout):
                self.assertEqual(('127.0.0.1', 32100), address)
                self.assertEqual(1, timeout)
                attempts.append(elapsed[0])
                if elapsed[0] >= 21.5: return connection
                elapsed[0] += timeout
                raise OSError('Firefox has not started listening')
            def sleep(seconds): elapsed[0] += seconds
            def command(name, arguments):
                return {'capabilities': {'browserVersion': '156.0'}} if name == 'WebDriver:NewSession' else {}
            with mock.patch.object(self.browser.process_tree, 'launch', return_value=owner), \
                 mock.patch.object(self.browser.socket, 'socket') as reserve_socket, \
                 mock.patch.object(self.browser.socket, 'create_connection', side_effect=connect), \
                 mock.patch.object(self.browser.time, 'monotonic', side_effect=lambda: elapsed[0]), \
                 mock.patch.object(self.browser.time, 'sleep', side_effect=sleep), \
                 mock.patch.object(self.browser.Browser, 'receive', return_value={}), \
                 mock.patch.object(self.browser.Browser, 'command', side_effect=command):
                reserve_socket.return_value.__enter__.return_value.getsockname.return_value = ('127.0.0.1', 32100)
                with self.browser.browser_workspace(output) as work:
                    browser = self.browser.Browser('firefox', work)
                    try:
                        self.assertGreater(attempts[-1], 20)
                        self.assertLess(attempts[-1], 120)
                        self.assertEqual('156.0', browser.capabilities['browserVersion'])
                        connection.settimeout.assert_called_once_with(15)
                        owner.terminate.assert_not_called(); owner.close.assert_not_called()
                    finally: browser.close()
            owner.terminate.assert_called_once(); owner.close.assert_called_once()
            connection.close.assert_called_once()
            self.assertFalse(work.exists())

    def test_firefox_startup_expires_at_120_seconds_and_joins_before_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); elapsed = [0.0]; attempts = []; events = []; streams = []
            owner = mock.Mock(); owner.process.poll.return_value = None
            owner.terminate.side_effect = lambda: events.append('terminate')
            owner.close.side_effect = lambda: events.append('join')
            def launch(argv, cwd, stream, *, env):
                streams.append(stream); stream.write('Firefox startup remained pending'); stream.flush()
                return owner
            def connect(address, *, timeout):
                self.assertEqual(1, timeout)
                attempts.append(elapsed[0]); elapsed[0] += timeout
                raise OSError('Firefox has not started listening')
            def sleep(seconds): elapsed[0] += seconds
            real_copy = self.browser.shutil.copyfile
            def copy(source, destination):
                self.assertEqual(['terminate', 'join'], events)
                self.assertTrue(streams[0].closed)
                return real_copy(source, destination)
            with mock.patch.object(self.browser.process_tree, 'launch', side_effect=launch), \
                 mock.patch.object(self.browser.socket, 'socket') as reserve_socket, \
                 mock.patch.object(self.browser.socket, 'create_connection', side_effect=connect), \
                 mock.patch.object(self.browser.time, 'monotonic', side_effect=lambda: elapsed[0]), \
                 mock.patch.object(self.browser.time, 'sleep', side_effect=sleep), \
                 mock.patch.object(self.browser.shutil, 'copyfile', side_effect=copy):
                reserve_socket.return_value.__enter__.return_value.getsockname.return_value = ('127.0.0.1', 32100)
                with self.assertRaisesRegex(TimeoutError, 'Firefox automation startup timeout'):
                    with self.browser.browser_workspace(output) as work:
                        self.browser.Browser('firefox', work)
            self.assertLess(attempts[-1], 120)
            self.assertGreaterEqual(elapsed[0], 120)
            self.assertLess(elapsed[0], 121.1)  # At most the last bounded connection attempt plus its pause.
            owner.terminate.assert_called_once(); owner.close.assert_called_once()
            self.assertEqual('Firefox startup remained pending', (output / 'firefox.log').read_text())
            self.assertFalse(work.exists())

    def test_both_launchers_own_startup_and_join_before_log_copy(self):
        for chromium in (False, True):
            with self.subTest(chromium=chromium), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary); events = []; streams = []
                owner = mock.Mock(); owner.process.poll.return_value = 1
                owner.terminate.side_effect = lambda: events.append('terminate')
                owner.close.side_effect = lambda: events.append('join')
                def launch(argv, cwd, stream, *, env):
                    self.assertEqual(Path.cwd(), cwd)
                    streams.append(stream); stream.write('startup evidence'); stream.flush()
                    self.assertEqual('driver' if chromium else 'firefox', argv[0])
                    self.assertEqual(None if chromium else '1', None if env is None else env['MOZ_HEADLESS'])
                    return owner
                real_copy = self.browser.shutil.copyfile
                def copy(source, destination):
                    self.assertEqual(['terminate', 'join'], events)
                    self.assertTrue(streams[0].closed)
                    return real_copy(source, destination)
                with mock.patch.object(self.browser.process_tree, 'launch', side_effect=launch), \
                     mock.patch.object(self.browser.socket, 'socket') as reserve_socket, \
                     mock.patch.object(self.browser.socket, 'create_connection', side_effect=OSError('offline')), \
                     mock.patch.object(self.browser.ChromiumBrowser, 'request', side_effect=OSError('offline')), \
                     mock.patch.object(self.browser.shutil, 'copyfile', side_effect=copy):
                    reserve_socket.return_value.__enter__.return_value.getsockname.return_value = ('127.0.0.1', 32100)
                    with self.assertRaisesRegex(RuntimeError, 'exited during startup'):
                        with self.browser.browser_workspace(output) as work:
                            if chromium: self.browser.ChromiumBrowser('chrome', 'driver', work, [])
                            else: self.browser.Browser('firefox', work)
                self.assertEqual('startup evidence', (output / ('chromedriver.log' if chromium else 'firefox.log')).read_text())
                self.assertFalse(list(output.glob('browser-*')))

    def test_failed_launch_closes_log_and_uncertain_launch_preserves_workspace(self):
        for uncertain in (False, True):
            with self.subTest(uncertain=uncertain), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary); streams = []
                error = (self.browser.process_tree.ProcessTreeError('writer cleanup is uncertain') if uncertain
                         else OSError('executable missing'))
                def launch(argv, cwd, stream, *, env):
                    streams.append(stream); stream.write('launch evidence'); raise error
                expected = self.browser.BrowserCleanupError if uncertain else OSError
                with mock.patch.object(self.browser.process_tree, 'launch', side_effect=launch):
                    with self.assertRaises(expected):
                        with self.browser.browser_workspace(output) as work:
                            instance = self.browser.Browser.__new__(self.browser.Browser)
                            instance._launch(['missing'], work, 'firefox.log')
                self.assertTrue(streams[0].closed)
                self.assertEqual(uncertain, work.exists())
                self.assertEqual(not uncertain, (output / 'firefox.log').exists())
                if uncertain:
                    self.assertEqual('launch evidence', (work / 'firefox.log').read_text())
                    with self.assertRaises(self.browser.BrowserCleanupError): instance.close()
                else: instance.close()  # Failed launch has no process or socket to close.

    def test_failure_after_owner_creation_still_joins_before_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            owner=mock.Mock(spec=['terminate','close'])
            with mock.patch.object(self.browser.process_tree,'launch',return_value=owner):
                with self.assertRaises(AttributeError):
                    with self.browser.browser_workspace(Path(temporary)) as work:
                        instance=self.browser.Browser.__new__(self.browser.Browser)
                        instance._launch(['unused'],work,'firefox.log')
            owner.terminate.assert_called_once();owner.close.assert_called_once()
            self.assertTrue(instance.log.closed);self.assertFalse(work.exists())

    def test_failed_launch_with_unclosed_log_preserves_uncertain_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary); stream=mock.Mock(); stream.close.side_effect=OSError('flush failed')
            with mock.patch.object(self.browser.process_tree,'launch',side_effect=OSError('launch failed')), \
                 mock.patch.object(Path,'open',return_value=stream):
                with self.assertRaisesRegex(self.browser.BrowserCleanupError,'flush failed'):
                    with self.browser.browser_workspace(output) as work:
                        instance=self.browser.Browser.__new__(self.browser.Browser)
                        instance._launch(['missing'],work,'firefox.log')
            self.assertTrue(work.exists())
            with self.assertRaises(self.browser.BrowserCleanupError):instance.close()
            stream.close.assert_called_once()

    def test_disconnect_failure_still_joins_and_successful_close_is_idempotent(self):
        for cls in (self.browser.Browser, self.browser.ChromiumBrowser):
            with self.subTest(cls=cls.__name__):
                events = []; owner = mock.Mock(); log = mock.Mock()
                owner.terminate.side_effect = lambda: events.append('terminate')
                owner.close.side_effect = lambda: events.append('join')
                log.close.side_effect = lambda: events.append('log')
                instance = self.instance(cls, log, owner)
                if cls is self.browser.Browser:
                    instance.socket = mock.Mock(); instance.socket.close.side_effect = RuntimeError('disconnect failed')
                else:
                    instance.session = 'active'; instance.request = mock.Mock(side_effect=RuntimeError('disconnect failed'))
                with self.assertRaisesRegex(RuntimeError, 'disconnect failed'): instance.close()
                self.assertEqual(['terminate', 'join', 'log'], events)
                instance.close()
                self.assertEqual(['terminate', 'join', 'log'], events)

    def test_uncertain_join_is_sticky_and_never_copies_or_deletes_logs(self):
        for failing_action in ('terminate', 'close'):
            with self.subTest(action=failing_action), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary); owner = mock.Mock()
                getattr(owner, failing_action).side_effect = RuntimeError('unconfirmed writer')
                with self.assertRaisesRegex(self.browser.BrowserCleanupError, 'unconfirmed writer'):
                    with self.browser.browser_workspace(output) as work:
                        log = (work / 'firefox.log').open('w'); log.write('not final')
                        (work / 'profile.sqlite').write_text('owned')
                        instance = self.instance(self.browser.Browser, log, owner)
                        instance.close()
                self.assertTrue(log.closed)
                owner.terminate.assert_called_once(); owner.close.assert_called_once()
                self.assertTrue((work / 'profile.sqlite').is_file())
                self.assertEqual('not final', (work / 'firefox.log').read_text())
                self.assertFalse((output / 'firefox.log').exists())
                with self.assertRaises(self.browser.BrowserCleanupError): instance.close()
                owner.terminate.assert_called_once(); owner.close.assert_called_once()

    def test_close_joins_actual_descendant_profile_writer_before_workspace_cleanup(self):
        # The browser/driver owns a child that keeps both its profile and inherited
        # log open. A parent-only wait cannot satisfy the pinned Windows handle or
        # Linux supervisor completion checks, even when its initial process exits.
        for cls in (self.browser.Browser, self.browser.ChromiumBrowser):
            with self.subTest(cls=cls.__name__), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)
                with self.browser.browser_workspace(output) as work:
                    profile = work / 'profile.sqlite'
                    child = ('import os,time;f=open(' + repr(str(profile)) + ',"wb");'
                             'print("child-ready:"+str(os.getpid()),flush=True);time.sleep(60)')
                    parent = ('import subprocess,sys,time;subprocess.Popen([sys.executable,"-B","-c",' +
                              repr(child) + ']);print("parent-ready",flush=True);time.sleep(60)')
                    instance = cls.__new__(cls); instance.socket = None; instance.session = None
                    instance._launch([sys.executable, '-B', '-c', parent], work, 'firefox.log')
                    owner = instance.owner; handle = None
                    try:
                        deadline = time.monotonic() + 10
                        while True:
                            lines = (work / 'firefox.log').read_bytes().splitlines()
                            children = [line[len(b'child-ready:'):] for line in lines if line.startswith(b'child-ready:')]
                            if b'parent-ready' in lines and len(children) == 1 and children[0].isdigit(): break
                            if time.monotonic() >= deadline: self.fail('profile writer did not become ready')
                            time.sleep(.01)
                        if owner.job is not None:
                            job = owner.job; handle = job.api.OpenProcess(0x101000, False, int(children[0]))
                            self.assertTrue(handle, 'cannot pin descendant writer')
                            member = job.w.BOOL()
                            self.assertTrue(job.api.IsProcessInJob(handle, job.handle, ctypes.byref(member)))
                            self.assertTrue(member.value)
                        instance.close()
                        if handle is not None:
                            self.assertEqual(0, job.api.WaitForSingleObject(handle, 0), 'descendant writer is still running')
                        else:
                            self.assertFalse(owner._live(), 'descendant writer is still running')
                        self.assertTrue(owner.closed); self.assertTrue(instance.log.closed)
                        profile.rename(work / 'renamed.sqlite'); (work / 'renamed.sqlite').unlink()
                        completed = (work / 'firefox.log').read_bytes()
                        instance.close()
                    finally:
                        try: owner.terminate()
                        finally:
                            try: owner.close()
                            finally:
                                instance.log.close()
                                if handle is not None: self.assertTrue(job.api.CloseHandle(handle))
                self.assertEqual(completed, (output / 'firefox.log').read_bytes())
                self.assertFalse(work.exists())


if __name__ == "__main__":
    unittest.main()
