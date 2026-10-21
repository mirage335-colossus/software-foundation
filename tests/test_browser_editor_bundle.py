"""Pure Python fixtures for the separate closed editor renderer bundle.

These cases assemble source bytes and inert data; they launch no JavaScript,
browser, engine, compiler or SDK operation.
"""
import base64
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import browser_bundle as legacy
import browser_editor_bundle as bundle
import browser_surface_bundle as surface

MODULES = (
    'browser_limits.mjs', 'browser_presenter.mjs', 'browser_surface_protocol.mjs',
    'browser_surface.mjs', 'browser_surface_editor_text.mjs',
    'browser_surface_editor_controller.mjs', 'browser_surface_editor.mjs',
    'browser_surface_editor_integration.mjs', 'browser_editor_endpoint.mjs',
    'browser_document_endpoint.mjs', 'browser_rich_surface_observer.mjs', 'renderer_channel.mjs', 'renderer_editor_dom.mjs', 'renderer_editor_frame.mjs',
)
GRAPH = {
    'browser_limits.mjs': (),
    'browser_presenter.mjs': (),
    'browser_surface_protocol.mjs': (),
    'browser_surface.mjs': ('browser_surface_protocol.mjs',),
    'browser_surface_editor_text.mjs': ('browser_surface.mjs',),
    'browser_surface_editor_controller.mjs': ('browser_surface.mjs', 'browser_surface_editor_text.mjs'),
    'browser_surface_editor.mjs': ('browser_surface.mjs', 'browser_surface_editor_text.mjs',
                                 'browser_surface_editor_controller.mjs'),
    'browser_surface_editor_integration.mjs': ('browser_surface.mjs', 'browser_surface_editor.mjs',
                                             'browser_surface_editor_controller.mjs'),
    'browser_editor_endpoint.mjs': ('browser_surface_editor_controller.mjs', 'browser_surface_editor_text.mjs',
                                   'browser_surface_protocol.mjs'),
    'browser_document_endpoint.mjs': (),
    'browser_rich_surface_observer.mjs': (),
    'renderer_channel.mjs': ('browser_limits.mjs',),
    'renderer_editor_dom.mjs': ('browser_limits.mjs', 'browser_surface_editor_integration.mjs'),
    'renderer_editor_frame.mjs': ('renderer_editor_dom.mjs', 'browser_surface_protocol.mjs',
                                 'browser_presenter.mjs', 'renderer_channel.mjs', 'browser_limits.mjs',
                                 'browser_editor_endpoint.mjs', 'browser_document_endpoint.mjs', 'browser_rich_surface_observer.mjs'),
}
EXPORTS = {
    'browser_limits.mjs': legacy.CHILD_EXPORTS['browser_limits.mjs'],
    'browser_presenter.mjs': ('createBrowserPresenter',),
    'browser_surface_protocol.mjs': ('validateSurfaceState', 'validateSurfaceOperation'),
    'browser_surface.mjs': ('BASIC_SURFACE_FEATURES', 'captureSurfaceKey', 'surfaceScalarMap', 'createBrowserSurface'),
    'browser_surface_editor_text.mjs': ('captureEditorText', 'proveEditorReplacement', 'proveEditorCompositionPassage'),
    'browser_surface_editor_controller.mjs': ('copyEditorBasis', 'copyEditorRetirement', 'createEditorObservationController'),
    'browser_surface_editor.mjs': ('createBrowserEditorConduit',),
    'browser_surface_editor_integration.mjs': ('createBrowserEditorSurface',),
    'browser_editor_endpoint.mjs': ('validateEditorPublication', 'validateEditorOperation',
                                   'validateEditorReply', 'createBrowserEditorEndpoint'),
    'browser_document_endpoint.mjs': ('validateDocumentState','validateDocumentOperation','validateDocumentReply','createBrowserDocumentEndpoint'),
    'browser_rich_surface_observer.mjs': ('createRichSurfaceObserver',),
    'renderer_channel.mjs': legacy.CHILD_EXPORTS['renderer_channel.mjs'],
    'renderer_editor_dom.mjs': ('identity', 'byteOffset', 'utf16Offset', 'Renderer'),
    'renderer_editor_frame.mjs': ('startRendererFrame',),
}
FIELDS = ('CHILD_SCRIPT', 'CHILD_SCRIPT_SHA256', 'CHILD_CSP', 'CHILD_SANDBOX', 'CHILD_PROTOCOL', 'CHILD_STYLE')
BUNDLE_NAME = 'renderer_editor_child_bundle.mjs'


def fixture_blobs():
    blobs = {}
    for name in MODULES:
        imports = ''.join("import {" + EXPORTS[dependency][0] + ' as input' + str(index) +
                          "} from './" + dependency + "';\n"
                          for index, dependency in enumerate(GRAPH[name]))
        exports = ''.join('export const ' + exported + '=' + str(index) + ';\n'
                          for index, exported in enumerate(EXPORTS[name]))
        blobs[name] = (imports + 'const fixtureLocal=1;\n' + exports).encode()
    blobs['style.css'] = b'body{color:black}\n'
    return blobs


class BrowserEditorBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-editor-bundle-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.assets = self.base / 'assets'
        self.assets.mkdir()
        self.blobs = fixture_blobs()
        for name, data in self.blobs.items():
            (self.assets / name).write_bytes(data)

    def generated(self):
        return {**self.blobs, BUNDLE_NAME: bundle.module_bytes(bundle.build(self.blobs))}

    def test_distinct_closed_editor_graph_and_existing_consumer_api(self):
        self.assertEqual(bundle.BUNDLE_NAME, BUNDLE_NAME)
        self.assertNotIn(BUNDLE_NAME, (legacy.BUNDLE_NAME, surface.BUNDLE_NAME))
        self.assertEqual(bundle.CHILD_MODULES, MODULES)
        self.assertEqual(bundle.SOURCE_NAMES, MODULES + ('style.css',))
        self.assertEqual(bundle.CHILD_GRAPH, GRAPH)
        self.assertEqual(bundle.CHILD_EXPORTS, EXPORTS)
        self.assertEqual(bundle.CHILD_FIELDS, FIELDS)
        self.assertEqual(bundle.CHILD_PROTOCOL, legacy.CHILD_PROTOCOL)
        self.assertEqual(bundle.CHILD_SANDBOX, 'allow-scripts')
        for name in ('browser_editor_endpoint.mjs', 'browser_document_endpoint.mjs', 'renderer_editor_dom.mjs', 'renderer_editor_frame.mjs'):
            self.assertNotIn(name, legacy.CHILD_GRAPH)
            self.assertNotIn(name, surface.CHILD_GRAPH)

    def test_deterministic_dependency_order_and_private_lexical_modules(self):
        expected = bundle.build(self.blobs)
        self.assertEqual(bundle.build(dict(reversed(tuple(self.blobs.items())))), expected)
        script = expected['CHILD_SCRIPT']
        for name, dependencies in GRAPH.items():
            for dependency in dependencies:
                with self.subTest(name=name, dependency=dependency):
                    self.assertLess(script.index('__modules[' + json.dumps(dependency) + ']=(() => {'),
                                    script.index('__modules[' + json.dumps(name) + ']=(() => {'))
        self.assertEqual(script.count('const fixtureLocal=1;'), len(MODULES))
        self.assertEqual(script.count('return Object.freeze({'), len(MODULES))
        self.assertNotIn("from './", script)

    def test_six_pure_data_fields_exact_hash_policy_and_roundtrip(self):
        metadata = bundle.build(self.blobs)
        self.assertEqual(tuple(metadata), FIELDS)
        self.assertTrue(all(type(value) is str for value in metadata.values()))
        self.assertNotIn('CHILD_INPUTS', metadata)
        script = metadata['CHILD_SCRIPT']
        digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode('ascii')
        self.assertEqual(metadata['CHILD_SCRIPT_SHA256'], digest)
        self.assertEqual(metadata['CHILD_CSP'], legacy.child_csp(script))
        self.assertIn("script-src 'sha256-" + digest + "'", metadata['CHILD_CSP'])
        self.assertNotIn('allow-same-origin', metadata['CHILD_SANDBOX'])
        encoded = bundle.module_bytes(metadata)
        self.assertEqual(bundle.parse_module(encoded), metadata)
        self.assertEqual(len(encoded.splitlines()), 7)
        for name, line in zip(FIELDS, encoded.decode().splitlines()[1:]):
            self.assertTrue(line.startswith('export const ' + name + '='))
            self.assertEqual(json.loads(line.split('=', 1)[1][:-1]), metadata[name])

    def test_existing_editor_sources_fit_the_declared_closed_graph(self):
        actual = dict(self.blobs)
        synthetic = {'browser_editor_endpoint.mjs', 'renderer_editor_dom.mjs', 'renderer_editor_frame.mjs'}
        for name in set(MODULES) - synthetic:
            actual[name] = (ROOT / 'gui/host' / name).read_bytes()
        metadata = bundle.build(actual)
        self.assertEqual(bundle.verify_assets({**actual, BUNDLE_NAME: bundle.module_bytes(metadata)}), metadata)

    def test_actual_editor_frame_patch_binds_document_before_paint_in_closed_graph(self):
        spec = importlib.util.spec_from_file_location('document_child_patch', ROOT / 'gui/patches/apply.py')
        patcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patcher)
        ordinary = (ROOT / 'gui/host/renderer_frame.mjs').read_text()
        physical = patcher.apply(ordinary, (ROOT / 'gui/patches/mouse-surface-frame.patch').read_text())
        editor = patcher.apply(physical, (ROOT / 'gui/patches/editor-surface-frame.patch').read_text())
        self.assertNotIn('documentProtocol', ordinary)
        self.assertNotIn('documentProtocol', physical)
        self.assertIn('surfaceProtocol,editorProtocol,documentProtocol,', editor)
        self.assertLess(editor.index('documentEndpoint.accept(snapshot,documentState,documentReply)'),
                        editor.index('editorEndpoint.accept(snapshot,surface,editor,editorReply)'))
        self.assertLess(editor.index('documentEndpoint.accept(snapshot,documentState,documentReply)'),
                        editor.index('renderer.acceptSnapshot(snapshot,surface,'))
        self.assertIn('documentEndpoint?.close(); editorEndpoint?.close(); requests?.close();', editor)
        actual = {**self.blobs, 'renderer_editor_frame.mjs': editor.encode(),
                  'browser_document_endpoint.mjs': (ROOT / 'gui/host/browser_document_endpoint.mjs').read_bytes(),
                  'browser_rich_surface_observer.mjs': (ROOT / 'gui/host/browser_rich_surface_observer.mjs').read_bytes()}
        self.assertEqual(bundle.parse_module(bundle.module_bytes(bundle.build(actual)))['CHILD_SANDBOX'],
                         'allow-scripts')

    def test_missing_extra_and_other_renderer_assets_are_rejected(self):
        for name in MODULES + ('style.css',):
            changed = dict(self.blobs)
            del changed[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                bundle.build(changed)
        for name in ('renderer_dom.mjs', 'renderer_frame.mjs', 'renderer_surface_dom.mjs',
                     'renderer_surface_frame.mjs', legacy.BUNDLE_NAME, surface.BUNDLE_NAME, BUNDLE_NAME):
            with self.subTest(extra=name), self.assertRaises(ValueError):
                bundle.build({**self.blobs, name: b'export const foreign=1;\n'})

    def test_editor_import_export_and_dynamic_dependency_drift_fail(self):
        changes = (
            ('browser_editor_endpoint.mjs', lambda data: data.replace(b"'./browser_surface_protocol.mjs'", b"'./browser_limits.mjs'")),
            ('renderer_editor_dom.mjs', lambda data: data.replace(b"'./browser_surface_editor_integration.mjs'", b"'./browser_surface.mjs'")),
            ('renderer_editor_frame.mjs', lambda data: data.replace(b"'./renderer_editor_dom.mjs'", b"'./renderer_surface_dom.mjs'")),
            ('browser_surface_editor_text.mjs', lambda data: data.replace(b'export const proveEditorReplacement=1;', b'')),
            ('browser_editor_endpoint.mjs', lambda data: data + b'export const uncheckedEditorOperation=1;\n'),
            ('browser_document_endpoint.mjs', lambda data: data + b'export const documentPublicationAck=1;\n'),
            ('renderer_editor_frame.mjs', lambda data: data + b"import('./browser_editor_endpoint.mjs');\n"),
        )
        for name, alter in changes:
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundle.build({**self.blobs, name: alter(self.blobs[name])})

    def test_inputs_require_bounded_byte_strings(self):
        for data in ('text', bytearray(b'text'), None):
            with self.subTest(data=data), self.assertRaises(ValueError):
                bundle.build({**self.blobs, 'style.css': data})
        with mock.patch.object(bundle, 'MAX_INPUT_BYTES', 1), self.assertRaises(ValueError):
            bundle.build(self.blobs)

    def test_source_terminators_invalid_utf8_and_newline_normalization(self):
        for name, addition in (('browser_surface_editor.mjs', b'\xff'),
                               ('browser_editor_endpoint.mjs', b'// </ScRiPt>'),
                               ('renderer_editor_dom.mjs', b'// <!--'),
                               ('renderer_editor_frame.mjs', b'// -->'),
                               ('renderer_editor_frame.mjs', b'\0'),
                               ('style.css', b'</StYlE>'), ('style.css', b'</script>'), ('style.css', b'\0')):
            with self.subTest(name=name, addition=addition), self.assertRaises((ValueError, UnicodeError)):
                bundle.build({**self.blobs, name: self.blobs[name] + addition})
        expected = bundle.build(self.blobs)
        for newline in (b'\r\n', b'\r'):
            changed = {name: data.replace(b'\n', newline) if name != 'style.css' else data
                       for name, data in self.blobs.items()}
            self.assertEqual(bundle.build(changed), expected)

    def test_parse_rejects_noncanonical_executable_and_wrong_typed_data(self):
        encoded = self.generated()[BUNDLE_NAME]
        lines = encoded.splitlines(keepends=True)
        for changed in (b'\n' + encoded, encoded + b'\n', encoded + b'globalThis.editor=1;\n',
                        encoded.replace(b'export const ', b'export  const ', 1),
                        b''.join([lines[0], lines[2], lines[1], *lines[3:]]), b'\xff' + encoded):
            with self.subTest(changed=changed[:50]), self.assertRaises((ValueError, UnicodeError)):
                bundle.parse_module(changed)
        metadata = bundle.build(self.blobs)
        for field, value in (('CHILD_STYLE', None), ('CHILD_CSP', True), ('CHILD_SCRIPT_SHA256', 7)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                bundle.module_bytes({**metadata, field: value})
        with self.assertRaises(ValueError):
            bundle.module_bytes({**metadata, 'CHILD_INPUTS': {}})

    def test_policy_and_coherent_unsafe_script_tampering_fail(self):
        metadata = bundle.build(self.blobs)
        for field, value in (('CHILD_CSP', metadata['CHILD_CSP'] + '; connect-src https:'),
                             ('CHILD_SCRIPT_SHA256', 'incorrect'), ('CHILD_SANDBOX', 'allow-same-origin'),
                             ('CHILD_PROTOCOL', 'unreviewed-editor-protocol'), ('CHILD_STYLE', '</style>')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                bundle.module_bytes({**metadata, field: value})
        for suffix in ('</script>', '<!--', '-->', '\0', '\r\n'):
            changed = {**metadata, 'CHILD_SCRIPT': metadata['CHILD_SCRIPT'] + suffix}
            changed['CHILD_SCRIPT_SHA256'] = base64.b64encode(hashlib.sha256(changed['CHILD_SCRIPT'].encode()).digest()).decode()
            changed['CHILD_CSP'] = legacy.child_csp(changed['CHILD_SCRIPT'])
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                bundle.module_bytes(changed)

    def test_verify_reconstructs_sources_and_rejects_coherent_generated_drift(self):
        self.assertEqual(bundle.verify_assets(self.generated()), bundle.build(self.blobs))
        for name in ('browser_surface_editor_controller.mjs', 'browser_editor_endpoint.mjs', 'style.css'):
            changed = self.generated()
            changed[name] += b'/* source changed */\n'
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundle.verify_assets(changed)
        metadata = bundle.build(self.blobs)
        metadata['CHILD_SCRIPT'] += '// generated-only change\n'
        metadata['CHILD_SCRIPT_SHA256'] = base64.b64encode(hashlib.sha256(metadata['CHILD_SCRIPT'].encode()).digest()).decode()
        metadata['CHILD_CSP'] = legacy.child_csp(metadata['CHILD_SCRIPT'])
        encoded = bundle.module_bytes(metadata)
        self.assertEqual(bundle.parse_module(encoded), metadata)
        with self.assertRaises(ValueError):
            bundle.verify_assets({**self.blobs, BUNDLE_NAME: encoded})
        for name in bundle.SOURCE_NAMES + (BUNDLE_NAME,):
            changed = self.generated()
            del changed[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                bundle.verify_assets(changed)

    def test_module_and_existing_asset_byte_limits_are_enforced(self):
        metadata = bundle.build(self.blobs)
        encoded = bundle.module_bytes(metadata)
        with mock.patch.object(bundle, 'MAX_BUNDLE_BYTES', len(encoded) - 1):
            with self.assertRaises(ValueError):
                bundle.module_bytes(metadata)
            with self.assertRaises(ValueError):
                bundle.parse_module(encoded)
            with self.assertRaises(ValueError):
                bundle.verify_assets({**self.blobs, BUNDLE_NAME: encoded})

    def test_generate_default_explicit_cli_output_and_unchanged_mtime(self):
        expected = self.generated()[BUNDLE_NAME]
        self.assertEqual(bundle.generate(self.assets), expected)
        output = self.assets / BUNDLE_NAME
        before = output.stat().st_mtime_ns
        self.assertEqual(bundle.generate(self.assets), expected)
        self.assertEqual(output.stat().st_mtime_ns, before)
        explicit = self.base / 'separate' / 'editor-data.mjs'
        bundle.main(['--assets', str(self.assets), '--output', str(explicit)])
        self.assertEqual(explicit.read_bytes(), expected)

    def test_generate_rejects_input_collision_and_hardlink_alias(self):
        for name in bundle.SOURCE_NAMES:
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundle.generate(self.assets, self.assets / name)
            self.assertEqual((self.assets / name).read_bytes(), self.blobs[name])
        alias = self.base / 'input-alias.mjs'
        alias.hardlink_to(self.assets / MODULES[0])
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, alias)
        self.assertEqual(alias.read_bytes(), self.blobs[MODULES[0]])

    def test_generate_rejects_symlink_inputs_outputs_and_ancestors(self):
        source = self.assets / MODULES[0]
        retained = self.base / 'retained.mjs'
        source.rename(retained)
        source.symlink_to(retained)
        output = self.base / 'rejected.mjs'
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, output)
        self.assertFalse(output.exists())
        source.unlink()
        source.write_bytes(self.blobs[MODULES[0]])
        output.symlink_to(self.base / 'missing.mjs')
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, output)
        self.assertFalse((self.base / 'missing.mjs').exists())
        alias = self.base / 'assets-alias'
        alias.symlink_to(self.assets, target_is_directory=True)
        with self.assertRaises(ValueError):
            bundle.generate(alias)
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, alias / 'new-output.mjs')

    def test_generate_bounded_reads_reject_input_growth_before_output_write(self):
        growing = self.assets / MODULES[0]
        limit = max(map(len, self.blobs.values())) + 8
        output = self.base / 'previous.mjs'
        previous = b'original output\n'
        output.write_bytes(previous)
        path_open = Path.open
        reads = []

        class GrowingFile(io.BytesIO):
            def read(self, size=-1):
                self.assert_bound(size)
                reads.append(size)
                return super().read(size)

            @staticmethod
            def assert_bound(size):
                if size < 0 or size > limit + 1:
                    raise AssertionError('Editor input read must remain bounded')

        def growing_open(path, *args, **kwargs):
            if path == growing and (args[0] if args else kwargs.get('mode')) == 'rb':
                return GrowingFile(b'x' * (limit + 1))
            return path_open(path, *args, **kwargs)

        with mock.patch.object(bundle, 'MAX_INPUT_BYTES', limit), \
                mock.patch.object(Path, 'open', growing_open), self.assertRaises(ValueError):
            bundle.generate(self.assets, output)
        self.assertEqual(reads, [limit + 1])
        self.assertEqual(output.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
