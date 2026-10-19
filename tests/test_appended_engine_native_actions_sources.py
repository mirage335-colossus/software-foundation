"""Rich native source/input tests; no engine is compiled."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
HISTORY_SPEC = importlib.util.spec_from_file_location('native_popup_source_history', ROOT / 'tests/native_popup_source_history.py')
HISTORY = importlib.util.module_from_spec(HISTORY_SPEC)
HISTORY_SPEC.loader.exec_module(HISTORY)
native_popup_predecessor_bytes = HISTORY.native_popup_predecessor_bytes
native_popup_history = HISTORY.native_popup_history
RECIPE = ROOT / 'recipes/webkitwasm-native-rich4083-v1'
SPEC = importlib.util.spec_from_file_location('native_actions_source_inspection', RECIPE / 'inspect_sources.py')
INSPECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECT)

UI_PRIVATE_FILES = (
    'ui/BibEngineUiOwner.cpp', 'ui/BibEngineUiOwner.hpp',
    'popup/BibNativePopupOwner.cpp', 'popup/BibNativePopupOwner.hpp',
    'popup/BibNativePopupHooks.hpp', 'popup/NativePopupController.cpp',
    'popup/NativePopupController.hpp', 'clipboard/BibClipboardStore.cpp',
    'clipboard/BibClipboardStore.hpp', 'clipboard/BibInternalClipboard.hpp',
)
UI_ENGINE_PREIMAGES = {
    'html/HTMLSelectElement.cpp': '72dbbadb8c01208192af65a97f913ac35a13db56a7b44057a7d1494e26e7757e',
    'loader/EmptyClients.cpp': '816baedf47261c9375aa9f4a8dd303f04e4266e47d4304b7443371c2c7cf3be4',
    'editing/Editor.cpp': 'f3c3bcbec9a2de12f69f10c1fe072ecb2de8afeb0d89a7a1d5c9e821bb1c2863',
    'dom/DataTransfer.cpp': '4e74e837716df0f8d417577208e0bb232e2c94e887e8c1e7ece665b4e3407bca',
    'platform/emscripten/PasteboardEmscripten.cpp': '41ed6a44ac90e299e927192a0fee3946b958d96fa87226594f707e3e97b37bcf',
}
# These identify the original actions capsule, before native adaptation or the
# UI successor. Current selected bytes belong in after_sha256, not these pins.
UI_RUNTIME_ORIGINS = {
    'source/document-provider/editor/BibNativeEditorBackend.cpp':
        ('98f95b8e1c4d352a60a412fb8e97730332bb15b1b8a6995d65036bab19762839',
         'source/editor/BibNativeEditorBackend.cpp'),
    'source/document-provider/key/NativeRawKeyDispatch.cpp':
        ('0efb91a52eee6b8f95526eac3461683252addae84ef5a10023c14beafc279325',
         'source/key/NativeRawKeyDispatch.cpp'),
    'source/document-provider/key/NativeRawKeyDispatch.hpp':
        ('bd9229750368d6ee63a389645c5b99b60c6a5546dd8a7d8ead3be2f85a85f244',
         'source/key/NativeRawKeyDispatch.hpp'),
    'source/document-provider/physical/BibDocumentPhysicalProvider.cpp':
        ('1ccbf5fa7d405022f139440ad2f681cadd57bea461d7a7cbd8558862e56a3e5e',
         'source/physical/BibDocumentPhysicalProvider.cpp'),
    'source/document-provider/runtime/BibNativeDocumentActionsBinding.cpp':
        ('e0e8b8059feff2db2a27882800879d17ae55a496a96b89ea85ad6f968ee73afa',
         'source/runtime/BibCopiedDocumentBinding.cpp'),
    'source/wrapper/src/embedder/BibFoundationServiceBridge.cpp':
        ('a8a9e3901158e5e5bc697b427dfcbc75d465f5b4a5068db46c792cf7b75c0be8',
         'source/wrapper/src/embedder/BibFoundationServiceBridge.cpp'),
    'source/wrapper/src/embedder/main.cpp':
        ('8c2f98835df730b17c0fb0f5bb5807c2ddaf9559797a59598173d95d02a70449',
         'source/wrapper/src/embedder/main.cpp'),
}


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
        return {'schema_version': 1, 'kind': 'foundation-native-engine-actions-source-inputs',
                'scope': 'native-actions-source-candidate-only', 'profile': 'actions',
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
        self.assertEqual(result['scope'], 'native-actions-source-input-integrity-only')
        self.assertFalse(result['production_eligible'])
        self.assertFalse(result['native_build_performed'])
        self.assertFalse(result['native_runtime_checks_passed'])
        self.assertFalse(result['kernel_rebuild_performed'])
        self.assertEqual(result['requirements'], INSPECT.REQUIREMENTS)
        self.assertEqual(result['files'], 198)
        inputs = json.loads(raw)['inputs']
        self.assertEqual(sum(path.startswith('source/') for path in inputs), 158)

    def test_closed_engine_and_runtime_source_origins_are_exact(self):
        provenance = json.loads((RECIPE / 'provenance.json').read_text())
        self.assertEqual(len(provenance['native_engine_files']), 48)
        self.assertEqual(len(provenance['runtime_files']), 110)
        self.assertEqual(provenance['source_graph']['source_files'], 158)
        self.assertEqual(provenance['source_graph']['engine_files'], 48)
        self.assertEqual(provenance['source_graph']['direct_translation_units'], 32)
        self.assertEqual(provenance['source_graph']['source_local_exception_translation_units'], 23)
        for record in provenance['native_engine_files']:
            self.assertEqual(digest((RECIPE / record['tracked_source']).read_bytes()), record['sha256'])
        for path, record in provenance['runtime_files'].items():
            self.assertEqual(digest(native_popup_predecessor_bytes((RECIPE / path).read_bytes())), record['after_sha256'])
        self.assertEqual(provenance['selected_notice_count'], 11)
        self.assertFalse((RECIPE / 'source/engine/Source/WebCore/dom/Element.h').exists())
        self.assertFalse((RECIPE / 'source/engine/Source/WebCore/page/EventHandler.h').exists())

    def test_private_ui_union_preserves_origins_and_original_engine_headers(self):
        provenance_raw = (RECIPE / 'provenance.json').read_bytes()
        provenance = json.loads(provenance_raw)
        manifest = json.loads((RECIPE / 'source-imports.json').read_bytes())
        self.assertEqual(manifest['provenance']['sha256'], digest(provenance_raw))
        self.assertEqual(manifest['inputs']['provenance.json']['sha256'], digest(provenance_raw))
        for name in UI_PRIVATE_FILES:
            path = 'source/document-provider/' + name
            self.assertIn(path, provenance['runtime_files'])
            self.assertIn(path, manifest['inputs'])
            self.assertEqual(manifest['inputs'][path]['role'], 'source')
        engine = {record['tracked_source']: record for record in provenance['native_engine_files']}
        for name, preimage in UI_ENGINE_PREIMAGES.items():
            path = 'source/engine/Source/WebCore/' + name
            self.assertIn(path, manifest['inputs'])
            self.assertEqual(engine[path]['original_supplier_cpp_sha256'], preimage)
            self.assertEqual(engine[path]['original_supplier_path'],
                             'third_party/WebKit/Source/WebCore/' + name)
            self.assertNotEqual(engine[path]['sha256'], preimage)
        capsule = '.agent-work/appended-implementation-20261016/tui-native-actions/versions/0001-document-actions-v1/'
        for path, (preimage, origin) in UI_RUNTIME_ORIGINS.items():
            record = provenance['runtime_files'][path]
            self.assertEqual(record['sha256'], preimage)
            self.assertEqual(record['preimage_sha256'], preimage)
            self.assertEqual(record['origin_path'], capsule + origin)
            self.assertNotEqual(record['after_sha256'], preimage)
            self.assertEqual(record['after_bytes'], len(native_popup_predecessor_bytes((RECIPE / path).read_bytes())))
        for name in ('html/HTMLSelectElement.h', 'loader/EmptyClients.h',
                     'editing/Editor.h', 'dom/DataTransfer.h'):
            self.assertNotIn('source/engine/Source/WebCore/' + name, manifest['inputs'])
            self.assertFalse((RECIPE / 'source/engine/Source/WebCore' / name).exists())
        pasteboard = 'source/engine/Source/WebCore/platform/Pasteboard.h'
        self.assertEqual(engine[pasteboard]['sha256'],
                         'ae5906c0e092fe20715784f4ffbce386175c86b66b9ade60e50c723b08bd86e0')
        self.assertEqual((RECIPE / pasteboard).read_bytes(),
                         (ROOT / 'recipes/webkitwasm-native-v1' / pasteboard).read_bytes())
        self.assertFalse(provenance['source_graph']['old_pixel_semantics_changed'])
        self.assertFalse(provenance['production_eligible'])
        self.assertFalse(provenance['actual_native_recipe_or_sdk_supplied'])

    def test_pixel_recipe_and_metadata_are_frozen(self):
        pixel = ROOT / 'recipes/webkitwasm-native-v1'
        self.assertEqual(digest((RECIPE / 'provenance/inputs/pixel-native-source-imports.json').read_bytes()),
            '9ffcf873dfe27b13ce8091221bfd2b5c1353d3ebbcfeaaef94b250b23c8533aa')
        pins = {'runtime/generate_native_metadata.py': '0ce275f55e82ec57ad755037ab17c23d6bebf69da29284295bf27e5998aec894',
                'runtime/native-provider-metadata.h.in': '170b25660de8f4eb7bd6ceee1093ec7a6e77cd4b374efc5309d917ed6186dbaa',
                'prelink-config.json': '80a845dab3340db41664485756dfccae992550c9765e44afacbcec79f2d8704e'}
        for path, pin in pins.items():
            self.assertEqual(digest((pixel / path).read_bytes()), pin)
        pixel_inputs = json.loads((pixel / 'source-imports.json').read_bytes())['inputs']
        for name in UI_PRIVATE_FILES:
            path = 'source/document-provider/' + name
            self.assertNotIn(path, pixel_inputs)
            self.assertFalse((pixel / path).exists())
            self.assertFalse((pixel / path).is_symlink())
        for name in UI_ENGINE_PREIMAGES:
            path = 'source/engine/Source/WebCore/' + name
            self.assertNotIn(path, pixel_inputs)
            self.assertFalse((pixel / path).exists())
            self.assertFalse((pixel / path).is_symlink())

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

    def test_fixed_actions_native_binding_and_both_target_source_gates(self):
        header = (RECIPE / 'source/native/BibNativeProviderBootstrap.hpp').read_text()
        self.assertIn('ensureNativeDocumentProviderBound() noexcept;', header)
        binding = (RECIPE / 'source/document-provider/runtime/BibNativeDocumentActionsBinding.cpp').read_text()
        for text in ('bindingOnce.ensure(', 'bind_engine_document_actions_private(',
                     'const DocumentBindingProfile profile{DocumentBindingProfile::actions}',
                     'M::targetSystem', 'M::targetProcessor', 'M::retention',
                     'limits.maximum_command_bytes != 1048576', 'limits.maximum_query_bytes != 236',
                     'if (!owner(*static_cast<const State*>(raw))) return BIB_ENGINE_WRONG_THREAD;'):
            self.assertIn(text, binding)
        self.assertNotIn('bindActualWebCoreDocumentProvider(', binding)
        self.assertFalse((RECIPE / 'source/document-provider/runtime/BibCopiedDocumentBinding.hpp').exists())
        port = (RECIPE / 'source/engine/Source/cmake/OptionsFoundation.cmake').read_text()
        self.assertIn('FoundationWindowsInputs.cmake', port)
        self.assertIn('Windows', port)
        exports = (RECIPE / 'cmake/native-provider.exports').read_text()
        self.assertEqual(exports.count('bib_engine_get_provider_v1;'), 1)
        self.assertIn('local:', exports)
        self.assertEqual((RECIPE / 'cmake/native-provider.def').read_text().strip(),
                         'EXPORTS\n    bib_engine_get_provider_v1')

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
                     'recipes/webkitwasm-native-rich4083-v1/source/con.cpp'):
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


    def test_composition_catalogue_has_one_authored_bridge_and_preserves_original109(self):
        manifest = json.loads((RECIPE / 'source-imports.json').read_bytes())
        provenance = json.loads((RECIPE / 'provenance.json').read_bytes())
        manifest = INSPECT.native_control_keypress_catalogue_predecessor(manifest)
        self.assertEqual(INSPECT.native_popup_catalogue_counts(manifest),
            {'source_files': 158, 'engine_files': 48, 'direct_translation_units': 32})
        manifest = INSPECT.native_popup_catalogue_predecessor(manifest)
        self.assertEqual(INSPECT.composition_catalogue_counts(manifest),
            {'source_files': 158, 'engine_files': 48, 'direct_translation_units': 32})
        bridge = INSPECT.COMPOSITION_BRIDGE
        record = provenance['runtime_files'][bridge]
        self.assertEqual(record['origin'], 'reviewed-source-only-composition-undo-private-bridge')
        self.assertIsNone(record['preimage_sha256'])
        self.assertEqual(record['source'], bridge)
        self.assertEqual(record['sha256'], INSPECT.COMPOSITION_SOURCE_FACTS[bridge]['sha256'])
        historical = {k: v for k, v in provenance['runtime_files'].items() if k != bridge}
        self.assertEqual(len(historical), 109)
        for name, expected in INSPECT.COMPOSITION_PREDECESSORS.items():
            current = historical[name]
            prior = current['successor']['supersedes']['origin']
            canonical = json.dumps(prior, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
            self.assertEqual(digest(canonical), expected['record_sha256'])
            self.assertEqual(prior['after_sha256'], expected['current_sha256'])
            for field in ('origin', 'origin_path', 'source', 'sha256', 'preimage_sha256', 'bytes', 'mode'):
                self.assertEqual(current[field], prior[field])
        changed = copy.deepcopy(manifest)
        changed['kind'] = 'foundation-native-engine-actions-source-inputs'
        with self.assertRaises(ValueError):
            INSPECT.composition_catalogue_counts(changed)

if __name__ == "__main__":
    unittest.main()
