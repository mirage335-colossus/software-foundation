"""Source-level boundary tripwires supplement executable GUI conformance."""

from pathlib import Path
import importlib.util
import json
import re
import sys
import subprocess
import unittest
import tempfile


ROOT = Path(__file__).resolve().parents[1]


_spec = importlib.util.spec_from_file_location("gui_guard", ROOT / "gui/check_boundary.py")
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)
shared_violations = _guard.shared_violations


class GuiBoundaryTests(unittest.TestCase):
    def test_shared_application_is_backend_independent(self):
        for path in (ROOT / "gui/shared").glob("*pp"):
            self.assertEqual([], shared_violations(path.read_text()), str(path))

    def test_tripwire_rejects_concrete_backends(self):
        for source in ('#include <FL/Fl.H>', '#include <gui/framebuffer.hpp>',
                       'import Rev.Widget;', 'gui::WebAdapter adapter;'):
            self.assertTrue(shared_violations(source), source)
        self.assertFalse(shared_violations('#include <gui/contract.hpp>\ngui::Adapter& adapter;'))

    def test_composition_hosts_do_not_name_feature_ids(self):
        for path in (ROOT / "gui/hosts").glob("*.cpp"):
            self.assertNotIn('"entries.', path.read_text(), str(path))

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
        self.assertEqual("NOASSERTION", lock["license"])


    def test_typed_host_contract_has_no_feature_dispatch(self):
        for path in (ROOT / "gui/host").glob("*.hpp"):
            self.assertNotIn('"entries.', path.read_text())
            self.assertNotIn("foundation::Store", path.read_text())
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        self.assertNotIn("using Example", cmake)
        self.assertNotIn("string(REPLACE", cmake)
        for name in ("FLTK", "SDL", "REV", "WEB"):
            self.assertIn("FOUNDATION_GUI_" + name, cmake)

    def windows_macro_fixture(self, *, windows, remove_guard=False):
        # Execute the real shared interface, application linkage and host factory.
        # Windows uses its actual platform header; other hosts reproduce only
        # that header's conditional min/max definitions for the same compile test.
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        boundary = "add_library(foundation_gui_boundary INTERFACE)" + cmake.split(
            "add_library(foundation_gui_boundary INTERFACE)", 1)[1].split("file(GLOB_RECURSE", 1)[0]
        application = "add_library(foundation_gui_application STATIC" + cmake.split(
            "add_library(foundation_gui_application STATIC", 1)[1].split("function(gui_warnings", 1)[0]
        host = "function(foundation_gui_executable" + cmake.split(
            "function(foundation_gui_executable", 1)[1].split("endfunction()", 1)[0] + "endfunction()\n"
        with tempfile.TemporaryDirectory(prefix="gui Windows macros ") as directory:
            source = Path(directory) / "source"; source.mkdir()
            (source / "shared").mkdir(); (source / "include").mkdir()
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
        block = "if(FOUNDATION_GUI_SDL)\n" + cmake.split("if(FOUNDATION_GUI_SDL)\n", 1)[1].split(
            "\nif(FOUNDATION_GUI_REV)", 1)[0]
        native_test = "foundation_gui_executable(foundation_gui_sdl_test" + cmake.split(
            "foundation_gui_executable(foundation_gui_sdl_test", 1)[1].split(
            "foundation_gui_check(sdl-host", 1)[0]
        if remove_selection:
            block = block.replace("INTERFACE SDL2::SDL2-static)", "INTERFACE SDL2::SDL2)")
        with tempfile.TemporaryDirectory(prefix="SDL linkage ") as temporary:
            root = Path(temporary); source = root / "source"; source.mkdir()
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
project(PortableSdlSelection LANGUAGES C)
set(SDL2_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
set(FOUNDATION_GUI_SDL ON)
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
        block = cmake.split("if(FOUNDATION_GUI_REV)\n", 1)[1].split("\nif(BUILD_TESTING)", 1)[0]
        block = "if(FOUNDATION_GUI_REV)\n" + block
        with tempfile.TemporaryDirectory(prefix="rev dependency ") as directory:
            root = Path(directory)
            source = root / "source"; source.mkdir()
            project = """cmake_minimum_required(VERSION 3.24)
project(RevDependencySelection LANGUAGES NONE)
set(FOUNDATION_GUI_REV ON)
function(foundation_gui_patch source patch output)
    if(output STREQUAL "Rev.cmake")
        file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/Rev.cmake" [=[
option(GUI_REV_BUNDLED_DEPS "Retained dependencies" ${WIN32})
if(GUI_REV_BUNDLED_DEPS)
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/selection.txt" "retained")
else()
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/selection.txt" "system")
endif()
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
        block = "if(FOUNDATION_GUI_FLTK)\n" + cmake.split("if(FOUNDATION_GUI_FLTK)\n", 1)[1].split(
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
        patch_function = "function(foundation_gui_patch" + cmake.split(
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


if __name__ == "__main__":
    unittest.main()
