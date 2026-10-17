"""Finite CMake control/asset fixtures, never retained-engine qualification.

Real source fragments execute with LANGUAGES NONE and interface target adapters.
No compiler, SDK, engine, browser, supplier configure or installed graph runs.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import browser_editor_bundle as editor_bundle
import browser_surface_bundle as surface_bundle


CONTROL_PREAMBLE = r'''
cmake_minimum_required(VERSION 3.24)
project(EditorControl LANGUAGES NONE)
# Keep real target properties while adapting target creation to LANGUAGES NONE.
# These adapters contain no profile selection or admission logic.
function(add_executable name)
    add_library(${name} INTERFACE)
endfunction()
function(target_link_libraries name scope)
    _target_link_libraries(${name} INTERFACE ${ARGN})
endfunction()
function(target_compile_definitions name scope)
    _target_compile_definitions(${name} INTERFACE ${ARGN})
endfunction()
function(target_include_directories name scope)
    _target_include_directories(${name} INTERFACE ${ARGN})
endfunction()
function(target_link_options name scope)
    _target_link_options(${name} INTERFACE ${ARGN})
endfunction()
function(foundation_options name)
endfunction()
set(FOUNDATION_BUILD_GUI TRUE)
set(FOUNDATION_APPENDED_KERNEL_MAINTENANCE TRUE)
set(FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED TRUE)
set(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE "")
set(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT FALSE)
set(FOUNDATION_GUI_DISTRIBUTABLE FALSE)
set(EMSCRIPTEN TRUE)
set(CMAKE_SIZEOF_VOID_P 4)
'''


def between(source, start, end):
    if source.count(start) != 1 or source.count(end) != 1:
        raise AssertionError('Reviewed CMake fragment boundary changed')
    return source.split(start, 1)[1].split(end, 1)[0]


def fragments():
    engine = (ROOT / 'cmake/AppendedEngine.cmake').read_text()
    guard = engine.split('include("${CMAKE_CURRENT_LIST_DIR}/AppendedCommon.cmake")', 1)
    if len(guard) != 2:
        raise AssertionError('Reviewed rich graph guard boundary changed')
    gui = (ROOT / 'cmake/AppendedGui.cmake').read_text()
    browser = between(gui, '    if(EMSCRIPTEN)\n        add_executable(foundation-gui-appended-engine-wasm',
        '    else()\n        if(NOT FOUNDATION_APPENDED_KERNEL_MAINTENANCE OR')
    browser = '        add_executable(foundation-gui-appended-engine-wasm' + browser
    assets = between((ROOT / 'gui/CMakeLists.txt').read_text(), 'set(foundation_web_modules ',
                     'if(FOUNDATION_GUI_DISTRIBUTABLE)\n    foreach(notice ')
    assets = 'set(foundation_web_modules ' + assets
    inputs = (ROOT / 'cmake/GuiInputs.cmake').read_text()
    repatch = between(inputs, 'function(foundation_gui_repatch source patch output)\n',
                      '\nendfunction()\n\nmacro(foundation_gui_headers)')
    repatch = 'function(foundation_gui_repatch source patch output)\n' + repatch + '\nendfunction()\n'
    return guard[0], browser, assets, repatch


class EditorCMakeTests(unittest.TestCase):
    def configure(self, root, flags=()):
        result = subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build'), *flags],
                                capture_output=True, text=True, timeout=20)
        self.assertFalse((root / 'build/compile_commands.json').exists())
        self.assertFalse((root / 'build/CMakeFiles/CompilerIdCXX').exists())
        return result

    def control(self, root, *, selected='editor', profile='web', editor=True, document=False,
                header=True, directory=True, shared=True):
        guard, browser, _, _ = fragments()
        for name in ('appended_browser_bootstrap', 'appended_engine_browser_bootstrap',
                     'appended_engine_wasm_worker', 'engine_kernel_bridge'):
            path = root / 'host' / (name + '.mjs')
            path.parent.mkdir(exist_ok=True)
            path.write_text('// inert unexecuted configure-file fixture\n')
        if header:
            name = header if isinstance(header, str) else ('editor' if selected == 'editor' else 'document')
            path = root / 'build' / ('appended-engine-' + name + '-profile') / ('appended_engine_compiled_' + name + '_profile.hpp')
            path.parent.mkdir(parents=True)
            path.write_text('// inert header path; no C++ parser is executed\n')
        settings = '\n'.join([
            'set(FOUNDATION_APPENDED_PROFILE ' + profile + ')',
            'set(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE ' + selected + ')',
            'set(FOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED ' + ('TRUE' if editor else 'FALSE') + ')',
            'set(FOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED ' + ('TRUE' if document else 'FALSE') + ')',
            'set(FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED ' + ('TRUE' if shared else 'FALSE') + ')',
            'set(FOUNDATION_APPENDED_ENGINE_EDITOR_DIRECTORY "${PROJECT_BINARY_DIR}/' +
                ('appended-engine-editor-profile' if directory else 'wrong-editor-directory') + '")'])
        properties = '''
foreach(property INTERFACE_COMPILE_DEFINITIONS INTERFACE_INCLUDE_DIRECTORIES INTERFACE_LINK_OPTIONS INTERFACE_LINK_LIBRARIES OUTPUT_NAME SUFFIX)
    get_target_property(value foundation-gui-appended-engine-wasm ${property})
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/${property}.txt" "${value}")
endforeach()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/configured" "fragment completed")
'''
        (root / 'CMakeLists.txt').write_text(CONTROL_PREAMBLE + settings + '\n' + guard + '\n' + browser + properties)
        return self.configure(root)

    def test_editor_real_graph_requires_separate_admission_and_shared_admission(self):
        for options, message in [({'editor': False, 'document': True}, 'separately verified editor'),
                                 ({'shared': False}, 'pinned retained-engine consumer')]:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result = self.control(root, **options)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(message, result.stdout + result.stderr)
                self.assertFalse((root / 'build/configured').exists())

    def test_editor_real_gui_requires_its_exact_private_directory_and_header(self):
        for options in ({'directory': False}, {'header': False}, {'header': 'document'}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result = self.control(root, **options)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('missing its separately verified private editor profile', result.stdout + result.stderr)
                self.assertFalse((root / 'build/configured').exists())

    def test_editor_real_gui_emits_macro3_exact_getter_and_binary_capability(self):
        old_exports = ['_gui_web_engine_bridge_v1', '_gui_web_engine_profile_v1', '_gui_web_engine_input_describe_v1',
                       '_gui_web_engine_document_describe_v1', '_gui_web_engine_dispatch_v1', '_gui_web_create',
                       '_gui_web_receive', '_gui_web_destroy', '_malloc', '_free']
        for profile in ('web', 'both'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result = self.control(root, profile=profile)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                tree = root / 'build'
                self.assertEqual(set((tree / 'INTERFACE_COMPILE_DEFINITIONS.txt').read_text().split(';')),
                    {'FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=3',
                     'FOUNDATION_APPENDED_BINARY_CAPABILITY=' + ('1' if profile == 'both' else '0')})
                self.assertEqual((tree / 'INTERFACE_INCLUDE_DIRECTORIES.txt').read_text(),
                                 (tree / 'appended-engine-editor-profile').as_posix())
                options = (tree / 'INTERFACE_LINK_OPTIONS.txt').read_text().split(';')
                exports = next(value for value in options if value.startswith('-sEXPORTED_FUNCTIONS='))
                self.assertEqual(json.loads(exports.split('=', 1)[1].replace("'", '"')),
                    old_exports[:4] + ['_gui_web_engine_editor_describe_v1'] + old_exports[4:])
                self.assertEqual((tree / 'OUTPUT_NAME.txt').read_text(), 'gui_appended_engine_wasm')
                self.assertEqual((tree / 'SUFFIX.txt').read_text(), '.js')
                for name in ('appended_browser_bootstrap', 'appended_engine_browser_bootstrap',
                             'appended_engine_wasm_worker', 'engine_kernel_bridge'):
                    self.assertEqual((tree / 'web-editor' / (name + '.mjs')).read_bytes(),
                                     (root / 'host' / (name + '.mjs')).read_bytes())

    def test_legacy_pixel1_and_physical2_keep_original_exports_and_directory(self):
        for selected, value in (('pixel', '1'), ('physical', '2')):
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result = self.control(root, selected=selected, editor=False, document=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                tree = root / 'build'
                definitions = (tree / 'INTERFACE_COMPILE_DEFINITIONS.txt').read_text().split(';')
                self.assertIn('FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=' + value, definitions)
                self.assertNotIn('FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=3', definitions)
                self.assertEqual((tree / 'INTERFACE_INCLUDE_DIRECTORIES.txt').read_text(),
                                 (tree / 'appended-engine-document-profile').as_posix())
                exports = (tree / 'INTERFACE_LINK_OPTIONS.txt').read_text()
                self.assertNotIn('_gui_web_engine_editor_describe_v1', exports)
                self.assertIn("'_gui_web_engine_document_describe_v1'", exports)
                export_option = next(value for value in exports.split(';') if value.startswith('-sEXPORTED_FUNCTIONS='))
                self.assertEqual(json.loads(export_option.split('=', 1)[1].replace("'", '"')), [
                    '_gui_web_engine_bridge_v1', '_gui_web_engine_profile_v1', '_gui_web_engine_input_describe_v1',
                    '_gui_web_engine_document_describe_v1', '_gui_web_engine_dispatch_v1', '_gui_web_create',
                    '_gui_web_receive', '_gui_web_destroy', '_malloc', '_free'])
                self.assertFalse((tree / 'web-editor').exists())

    def retained_renderer_inputs(self):
        group = ROOT / 'third_party/gui-inputs'
        manifest_bytes = (group / 'manifest.json').read_bytes()
        manifest = json.loads(manifest_bytes)
        sums = dict(line.split('  ')[::-1] for line in (group / 'SHA256SUMS').read_text().splitlines())
        self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), sums['manifest.json'])
        archive = group / 'gui-inputs.tar.gz'
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(digest, manifest['archive_sha256'])
        self.assertEqual(digest, sums['gui-inputs.tar.gz'])
        lock = json.loads((ROOT / 'third_party/gui-boundary.lock.json').read_bytes())
        members = {}
        with tarfile.open(archive, 'r:gz') as source:
            for name in ('renderer.mjs', 'boot.mjs', 'style.css', 'index.html'):
                relative = 'backends/web/' + name
                member = source.getmember('upstream/' + relative)
                expected = manifest['files'][member.name]
                self.assertTrue(member.isfile())
                self.assertEqual(member.size, expected['size'])
                self.assertLess(member.size, 4 * 1048576)
                with source.extractfile(member) as stream:
                    raw = stream.read(4 * 1048576 + 1)
                self.assertEqual(len(raw), expected['size'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected['sha256'])
                self.assertEqual(expected['sha256'], lock['files'][relative])
                members[relative] = raw
        return members

    def assets(self, root, selected):
        _, _, asset_source, repatch = fragments()
        members = self.retained_renderer_inputs()
        spec = importlib.util.spec_from_file_location('editor_cmake_exact_patch', ROOT / 'gui/patches/apply.py')
        patcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patcher)
        generated = {name: data.decode('utf-8') for name, data in members.items()}
        generated['patch-inputs/renderer-surface-frame.mjs'] = (ROOT / 'gui/host/renderer_frame.mjs').read_text()
        calls = re.findall(r'^foundation_gui_(?:patch|repatch)\((\S+)\s+(\S+)\s+(\S+)\)\s*$',
                           (ROOT / 'gui/CMakeLists.txt').read_text(), re.M)
        applied = []
        for source, patch, output in calls:
            if source in generated:
                generated[output] = patcher.apply(generated[source], (ROOT / 'gui/patches' / patch).read_text())
                applied.append(patch)
        self.assertIn('mouse-surface-renderer.patch', applied)
        self.assertIn('mouse-surface-frame.patch', applied)
        gui = root / 'gui'
        (gui / 'host').mkdir(parents=True)
        (gui / 'hosts').mkdir()
        (gui / 'patches').mkdir()
        modules = re.search(r'set\(foundation_web_modules ([^)]*)\)', asset_source).group(1).split()
        host_names = set(modules) | {'browser_surface', 'browser_surface_protocol', 'renderer_compat',
            'browser_surface_editor_text', 'browser_surface_editor_controller', 'browser_surface_editor',
            'browser_surface_editor_integration', 'browser_editor_endpoint'}
        for name in sorted(host_names):
            (gui / 'host' / (name + '.mjs')).write_bytes((ROOT / 'gui/host' / (name + '.mjs')).read_bytes())
        (gui / 'hosts/web_host.py').write_bytes((ROOT / 'gui/hosts/web_host.py').read_bytes())
        for name in ('apply.py', 'surface-frame.patch', 'mouse-surface-renderer.patch', 'mouse-surface-frame.patch',
                     'editor-surface-renderer.patch', 'editor-surface-frame.patch'):
            (gui / 'patches' / name).write_bytes((ROOT / 'gui/patches' / name).read_bytes())
        tools = root / 'tools'
        tools.mkdir()
        for name in ('browser_bundle.py', 'browser_surface_bundle.py', 'browser_editor_bundle.py'):
            (tools / name).write_bytes((ROOT / 'tools' / name).read_bytes())
        vendor = root / 'retained/backends/web'
        vendor.mkdir(parents=True)
        for name in ('style.css', 'index.html'):
            (vendor / name).write_bytes(members['backends/web/' + name])
        tree = root / 'build/gui'
        (tree / 'web').mkdir(parents=True)
        for name in ('boot.mjs', 'renderer_dom.mjs', 'renderer_surface_dom.mjs'):
            (tree / 'web' / name).write_text(generated['web/' + name])
        (tree / 'web/renderer.mjs').write_bytes((ROOT / 'gui/host/renderer_compat.mjs').read_bytes())
        (tree / 'web-physical').mkdir()
        (tree / 'web-physical/unlisted.txt').write_text('not part of any declared inventory')
        project = 'cmake_minimum_required(VERSION 3.24)\nproject(EditorAssets LANGUAGES NONE)\n'
        project += 'set(Python3_EXECUTABLE "' + Path(sys.executable).as_posix() + '")\n'
        project += 'set(foundation_gui_module_root "${CMAKE_CURRENT_SOURCE_DIR}/gui")\n'
        project += 'set(FOUNDATION_GUI_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/retained")\n'
        project += 'set(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE ' + selected + ')\n'
        project += 'set(BUILD_TESTING FALSE)\nadd_subdirectory(gui)\n'
        (root / 'CMakeLists.txt').write_text(project)
        (gui / 'CMakeLists.txt').write_text(repatch + asset_source +
            '\nfile(WRITE "${CMAKE_CURRENT_BINARY_DIR}/physical-assets" "${foundation_physical_web_assets}")\n'
            'file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/editor-assets" "${foundation_editor_web_assets}")\n')
        return self.configure(root), generated

    def test_actual_editor_asset_block_extends_retained_physical_postimages_and_copies_closed_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result, generated = self.assets(root, 'editor')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            tree = root / 'build/gui'
            physical = {Path(path).name: Path(path) for path in (tree / 'physical-assets').read_text().split(';')}
            actual = {path.name: path.read_bytes() for path in (tree / 'web-editor').iterdir()}
            added = {'renderer_editor_dom.mjs', 'renderer_editor_frame.mjs', 'browser_surface_editor_text.mjs',
                     'browser_surface_editor_controller.mjs', 'browser_surface_editor.mjs',
                     'browser_surface_editor_integration.mjs', 'browser_editor_endpoint.mjs', editor_bundle.BUNDLE_NAME}
            self.assertEqual(set(actual), set(physical) | added)
            recorded = {Path(path).name for path in (tree / 'editor-assets').read_text().split(';')}
            self.assertEqual(recorded, set(actual))
            for name, source in physical.items():
                self.assertEqual(actual[name], source.read_bytes(), name)
            for name in ('renderer_surface_dom.mjs', 'renderer_surface_frame.mjs'):
                self.assertEqual(physical[name].read_text(), generated['web-physical/' + name])
            self.assertNotIn('unlisted.txt', actual)
            blobs = {name: actual[name] for name in editor_bundle.SOURCE_NAMES + (editor_bundle.BUNDLE_NAME,)}
            metadata = editor_bundle.verify_assets(blobs)
            self.assertEqual(metadata['CHILD_SANDBOX'], 'allow-scripts')
            self.assertIn('__modules["browser_editor_endpoint.mjs"]', metadata['CHILD_SCRIPT'])
            self.assertNotEqual(actual[editor_bundle.BUNDLE_NAME], actual[surface_bundle.BUNDLE_NAME])

    def test_legacy_asset_selection_does_not_emit_editor_graph_or_change_physical_postimages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result, generated = self.assets(root, 'pixel')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            tree = root / 'build/gui'
            self.assertEqual((tree / 'editor-assets').read_text(), '')
            self.assertFalse((tree / 'web-editor').exists())
            for name in ('renderer_surface_dom.mjs', 'renderer_surface_frame.mjs'):
                self.assertEqual((tree / 'web-physical' / name).read_text(), generated['web-physical/' + name])


if __name__ == '__main__':
    unittest.main()
