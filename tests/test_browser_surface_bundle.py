"""Focused pure-data surface bundle graph, policy and filesystem fixtures.

These checks do not execute a browser, an engine or the production renderer.
The optional Node case imports only generated fixture data, then runs its inert
counter script in a separate VM context to distinguish parent and child scopes.
"""
import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import browser_bundle as legacy
import browser_surface_bundle as bundle

MODULES = ('browser_limits.mjs', 'browser_presenter.mjs', 'browser_surface_protocol.mjs',
           'browser_surface.mjs', 'renderer_channel.mjs', 'renderer_surface_dom.mjs',
           'renderer_surface_frame.mjs')
GRAPH = {
    'browser_limits.mjs': (),
    'browser_presenter.mjs': (),
    'browser_surface_protocol.mjs': (),
    'browser_surface.mjs': ('browser_surface_protocol.mjs',),
    'renderer_channel.mjs': ('browser_limits.mjs',),
    'renderer_surface_dom.mjs': ('browser_limits.mjs', 'browser_surface.mjs'),
    'renderer_surface_frame.mjs': ('renderer_surface_dom.mjs', 'browser_surface_protocol.mjs',
                                   'browser_presenter.mjs', 'renderer_channel.mjs', 'browser_limits.mjs'),
}
EXPORTS = {
    'browser_limits.mjs': legacy.CHILD_EXPORTS['browser_limits.mjs'],
    'browser_presenter.mjs': legacy.CHILD_EXPORTS['browser_presenter.mjs'],
    'browser_surface_protocol.mjs': ('validateSurfaceState', 'validateSurfaceOperation'),
    'browser_surface.mjs': ('BASIC_SURFACE_FEATURES', 'captureSurfaceKey',
                            'surfaceScalarMap', 'createBrowserSurface'),
    'renderer_channel.mjs': legacy.CHILD_EXPORTS['renderer_channel.mjs'],
    'renderer_surface_dom.mjs': legacy.CHILD_EXPORTS['renderer_dom.mjs'],
    'renderer_surface_frame.mjs': legacy.CHILD_EXPORTS['renderer_frame.mjs'],
}
FIELDS = ('CHILD_SCRIPT', 'CHILD_SCRIPT_SHA256', 'CHILD_CSP', 'CHILD_SANDBOX',
          'CHILD_PROTOCOL', 'CHILD_STYLE')
BUNDLE_NAME = 'renderer_surface_child_bundle.mjs'


def fixture_blobs():
    blobs = {}
    for name in MODULES:
        imports = ''.join("import {" + EXPORTS[dependency][0] + ' as input' + str(index) +
                          "} from './" + dependency + "';\n"
                          for index, dependency in enumerate(GRAPH[name]))
        exports = ''.join('export const ' + exported + '=' + str(index) + ';\n'
                          for index, exported in enumerate(EXPORTS[name]))
        marker = ('const fixtureLocal=1;\n'
                  'globalThis.__surfaceFixtureRuns=(globalThis.__surfaceFixtureRuns||0)+1;\n')
        blobs[name] = (imports + marker + exports).encode('utf-8')
    blobs['style.css'] = b'body{color:black}\n'
    return blobs


class BrowserSurfaceBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-surface-bundle-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.assets = self.base / 'assets'
        self.assets.mkdir()
        self.blobs = fixture_blobs()
        for name, data in self.blobs.items():
            (self.assets / name).write_bytes(data)

    def with_generated(self, blobs=None):
        blobs = dict(self.blobs if blobs is None else blobs)
        blobs[BUNDLE_NAME] = bundle.module_bytes(bundle.build(blobs))
        return blobs

    def test_exact_surface_graph_exports_and_legacy_consumer_fields(self):
        self.assertEqual(bundle.BUNDLE_NAME, BUNDLE_NAME)
        self.assertEqual(bundle.CHILD_MODULES, MODULES)
        self.assertEqual(bundle.CHILD_GRAPH, GRAPH)
        self.assertEqual(bundle.CHILD_EXPORTS, EXPORTS)
        metadata = bundle.build(self.blobs)
        self.assertEqual(tuple(metadata), FIELDS)
        self.assertTrue(all(type(metadata[name]) is str for name in FIELDS))
        self.assertNotIn('CHILD_INPUTS', metadata)
        self.assertEqual(metadata['CHILD_SANDBOX'], 'allow-scripts')
        self.assertEqual(metadata['CHILD_PROTOCOL'], 'foundation-renderer-v1')
        self.assertEqual(metadata['CHILD_STYLE'], self.blobs['style.css'].decode('utf-8'))

    def test_deterministic_build_respects_dependency_order_and_lexical_scopes(self):
        expected = bundle.build(self.blobs)
        self.assertEqual(bundle.build(self.blobs), expected)
        self.assertEqual(bundle.build(dict(reversed(tuple(self.blobs.items())))), expected)
        script = expected['CHILD_SCRIPT']
        for consumer, dependencies in GRAPH.items():
            for dependency in dependencies:
                with self.subTest(consumer=consumer, dependency=dependency):
                    self.assertLess(script.index('__modules[' + json.dumps(dependency) + ']=(() => {'),
                                    script.index('__modules[' + json.dumps(consumer) + ']=(() => {'))
        self.assertEqual(script.count('const fixtureLocal=1;'), len(MODULES))
        self.assertEqual(script.count('return Object.freeze({'), len(MODULES))
        self.assertNotIn("from './", script)

    def test_exact_script_hash_csp_and_canonical_pure_data_roundtrip(self):
        metadata = bundle.build(self.blobs)
        script = metadata['CHILD_SCRIPT']
        expected_hash = base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii')
        self.assertEqual(metadata['CHILD_SCRIPT_SHA256'], expected_hash)
        self.assertEqual(metadata['CHILD_CSP'], legacy.child_csp(script))
        self.assertIn("script-src 'sha256-" + expected_hash + "'", metadata['CHILD_CSP'])
        self.assertNotIn('blob:', metadata['CHILD_CSP'])
        self.assertNotIn('allow-same-origin', metadata['CHILD_SANDBOX'])
        encoded = bundle.module_bytes(metadata)
        self.assertEqual(bundle.parse_module(encoded), metadata)
        self.assertEqual(len(encoded.splitlines()), len(FIELDS) + 1)
        for name, line in zip(FIELDS, encoded.decode('utf-8').splitlines()[1:]):
            self.assertTrue(line.startswith('export const ' + name + '='))
            self.assertEqual(json.loads(line.split('=', 1)[1][:-1]), metadata[name])

    def test_generated_parent_import_is_inert_and_child_counter_has_private_scope(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node is required to execute the separate inert-module fixture')
        path = self.base / BUNDLE_NAME
        path.write_bytes(bundle.module_bytes(bundle.build(self.blobs)))
        probe = '''
import vm from 'node:vm';
globalThis.__surfaceFixtureRuns=0;
const data=await import(process.argv[1]);
if(globalThis.__surfaceFixtureRuns!==0)throw Error('Child ran in the parent');
if(Object.keys(data).length!==6)throw Error('Consumer exports changed');
const child={};
vm.runInNewContext(data.CHILD_SCRIPT,child,{timeout:1000});
if(child.__surfaceFixtureRuns!==7)throw Error('Incomplete child graph');
if('fixtureLocal' in child)throw Error('Module local escaped');
if(globalThis.__surfaceFixtureRuns!==0)throw Error('Child escaped VM');
'''
        completed = subprocess.run([node, '--input-type=module', '-e', probe, path.as_uri()],
                                   cwd=self.base, capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_build_rejects_missing_extra_and_legacy_renderer_modules(self):
        for name in MODULES + ('style.css',):
            blobs = dict(self.blobs)
            del blobs[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                bundle.build(blobs)
        for name in ('unexpected.mjs', 'renderer_dom.mjs', 'renderer_frame.mjs', BUNDLE_NAME):
            blobs = {**self.blobs, name: b'export const unexpected=1;\n'}
            with self.subTest(extra=name), self.assertRaises(ValueError):
                bundle.build(blobs)

    def test_surface_specific_import_export_and_dynamic_import_drift_fail(self):
        cases = [
            ('browser_surface.mjs', lambda data: data.replace(b"'./browser_surface_protocol.mjs'", b"'./browser_limits.mjs'")),
            ('renderer_surface_dom.mjs', lambda data: data.replace(b"'./browser_surface.mjs'", b"'./browser_presenter.mjs'")),
            ('renderer_surface_frame.mjs', lambda data: data.replace(b"'./renderer_surface_dom.mjs'", b"'./renderer_dom.mjs'")),
            ('browser_surface_protocol.mjs', lambda data: data.replace(b'export const validateSurfaceOperation=1;', b'')),
            ('browser_surface.mjs', lambda data: data + b'export const unsupportedSurfaceFeature=1;\n'),
            ('renderer_surface_frame.mjs', lambda data: data + b"import('./browser_surface.mjs');\n"),
        ]
        for name, alter in cases:
            blobs = dict(self.blobs)
            blobs[name] = alter(blobs[name])
            with self.subTest(name=name, altered=blobs[name]), self.assertRaises(ValueError):
                bundle.build(blobs)

    def test_utf8_and_html_terminators_are_rejected_in_surface_inputs(self):
        for name, addition in (
                ('browser_surface_protocol.mjs', b'\xff'),
                ('browser_surface.mjs', b'// </ScRiPt>'),
                ('renderer_surface_dom.mjs', b'// <!--'),
                ('renderer_surface_frame.mjs', b'// -->'),
                ('renderer_surface_frame.mjs', b'\0'),
                ('style.css', b'</StYlE>'),
                ('style.css', b'</script>'),
                ('style.css', b'\0'),
                ('style.css', b'\xff')):
            blobs = dict(self.blobs)
            blobs[name] += addition
            with self.subTest(name=name, addition=addition), self.assertRaises((ValueError, UnicodeError)):
                bundle.build(blobs)

    def test_source_newline_normalization_preserves_browser_script_hash(self):
        expected = bundle.build(self.blobs)
        for newline in (b'\r\n', b'\r'):
            windows = {name: value.replace(b'\n', newline) if name != 'style.css' else value
                       for name, value in self.blobs.items()}
            with self.subTest(newline=newline):
                actual = bundle.build(windows)
                self.assertEqual(actual, expected)
                self.assertNotIn('\r', actual['CHILD_SCRIPT'])
                self.assertEqual(bundle.verify_assets({**windows, BUNDLE_NAME: bundle.module_bytes(expected)}), expected)
        styled = dict(self.blobs)
        styled['style.css'] = styled['style.css'].replace(b'\n', b'\r\n')
        actual = bundle.build(styled)
        self.assertEqual(actual['CHILD_SCRIPT_SHA256'], expected['CHILD_SCRIPT_SHA256'])
        self.assertEqual(actual['CHILD_STYLE'], 'body{color:black}\r\n')

    def test_parse_rejects_noncanonical_modules_extra_execution_and_wrong_types(self):
        metadata = bundle.build(self.blobs)
        encoded = bundle.module_bytes(metadata)
        lines = encoded.splitlines(keepends=True)
        malformed = [b'\n' + encoded, encoded + b'\n', encoded.replace(b'export const ', b'export  const ', 1),
                     b''.join([lines[0], lines[2], lines[1], *lines[3:]]),
                     b'// Edited fixture data\n' + b''.join(lines[1:]),
                     encoded + b'globalThis.__surfaceFixtureRuns=100;\n', b'\xff' + encoded]
        for data in malformed:
            with self.subTest(data=data[:90]), self.assertRaises((ValueError, UnicodeError)):
                bundle.parse_module(data)
        for name, value in (('CHILD_STYLE', None), ('CHILD_CSP', True), ('CHILD_SCRIPT_SHA256', 7)):
            invalid = {**metadata, name: value}
            with self.subTest(field=name), self.assertRaises(ValueError):
                bundle.parse_module(bundle.module_bytes(invalid))
        for invalid in ({**metadata, 'CHILD_INPUTS': {}}, {name: metadata[name] for name in FIELDS[:-1]}):
            with self.subTest(fields=tuple(invalid)), self.assertRaises(ValueError):
                bundle.parse_module(bundle.module_bytes(invalid))

    def test_parse_rejects_script_hash_csp_sandbox_protocol_and_terminator_tampering(self):
        metadata = bundle.build(self.blobs)
        changes = [('CHILD_SCRIPT', metadata['CHILD_SCRIPT'] + '// changed script\n'),
                   ('CHILD_SCRIPT_SHA256', base64.b64encode(b'\0' * 32).decode('ascii')),
                   ('CHILD_CSP', metadata['CHILD_CSP'] + "; connect-src https:"),
                   ('CHILD_SANDBOX', 'allow-scripts allow-same-origin'),
                   ('CHILD_PROTOCOL', 'foundation-renderer-v2'),
                   ('CHILD_STYLE', '</style><script>'),
                   ('CHILD_STYLE', 'a\0b')]
        for name, value in changes:
            invalid = {**metadata, name: value}
            with self.subTest(field=name, value=value[:50]), self.assertRaises(ValueError):
                bundle.parse_module(bundle.module_bytes(invalid))
        for ending in ('</script>', '<!--', '-->', '\0', '\r\n'):
            invalid = copy.deepcopy(metadata)
            invalid['CHILD_SCRIPT'] += ending
            invalid['CHILD_SCRIPT_SHA256'] = base64.b64encode(hashlib.sha256(invalid['CHILD_SCRIPT'].encode()).digest()).decode('ascii')
            invalid['CHILD_CSP'] = legacy.child_csp(invalid['CHILD_SCRIPT'])
            with self.subTest(coherent_unsafe_ending=ending), self.assertRaises(ValueError):
                bundle.parse_module(bundle.module_bytes(invalid))

    def test_asset_verification_rebuilds_exact_generated_bytes_and_inventory(self):
        metadata = bundle.build(self.blobs)
        self.assertEqual(bundle.verify_assets(self.with_generated()), metadata)
        for name in MODULES + ('style.css', BUNDLE_NAME):
            blobs = self.with_generated()
            del blobs[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                bundle.verify_assets(blobs)
        for name in ('extra.mjs', 'renderer_child_bundle.mjs'):
            with self.subTest(extra=name), self.assertRaises(ValueError):
                bundle.verify_assets({**self.with_generated(), name: b''})

    def test_asset_verification_rejects_source_style_and_coherent_generated_drift(self):
        for name in ('browser_surface.mjs', 'style.css'):
            blobs = self.with_generated()
            blobs[name] += b'/* changed fixture source */\n'
            with self.subTest(changed_source=name), self.assertRaises(ValueError):
                bundle.verify_assets(blobs)
        metadata = bundle.build(self.blobs)
        metadata['CHILD_SCRIPT'] += '// coherent generated-only drift\n'
        metadata['CHILD_SCRIPT_SHA256'] = base64.b64encode(hashlib.sha256(metadata['CHILD_SCRIPT'].encode()).digest()).decode('ascii')
        metadata['CHILD_CSP'] = legacy.child_csp(metadata['CHILD_SCRIPT'])
        generated = bundle.module_bytes(metadata)
        self.assertEqual(bundle.parse_module(generated), metadata)
        with self.assertRaises(ValueError):
            bundle.verify_assets({**self.blobs, BUNDLE_NAME: generated})

    def test_generate_default_explicit_output_and_unchanged_mtime(self):
        expected = bundle.module_bytes(bundle.build(self.blobs))
        default = self.assets / BUNDLE_NAME
        self.assertEqual(bundle.generate(self.assets), expected)
        self.assertEqual(default.read_bytes(), expected)
        before = default.stat().st_mtime_ns
        self.assertEqual(bundle.generate(self.assets), expected)
        self.assertEqual(default.stat().st_mtime_ns, before)
        output = self.base / 'separate' / 'surface-data.mjs'
        self.assertEqual(bundle.generate(self.assets, output), expected)
        self.assertEqual(output.read_bytes(), expected)
        self.assertEqual(bundle.verify_assets({**self.blobs, BUNDLE_NAME: output.read_bytes()}), bundle.build(self.blobs))

    def test_generate_rejects_each_source_output_collision_without_changing_inputs(self):
        for name in MODULES + ('style.css',):
            with self.subTest(output=name), self.assertRaises(ValueError):
                bundle.generate(self.assets, self.assets / name)
            self.assertEqual((self.assets / name).read_bytes(), self.blobs[name])
        alias = self.base / 'source-alias.mjs'
        alias.hardlink_to(self.assets / MODULES[0])
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, alias)
        self.assertEqual(alias.read_bytes(), self.blobs[MODULES[0]])
        self.assertEqual((self.assets / MODULES[0]).read_bytes(), self.blobs[MODULES[0]])

    def test_generate_rejects_symlink_inputs_output_and_ancestor_paths(self):
        source = self.assets / MODULES[0]
        original = source.read_bytes()
        target = self.base / 'retained-source.mjs'
        source.rename(target)
        source.symlink_to(target)
        output = self.base / 'rejected-data.mjs'
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, output)
        self.assertFalse(output.exists())
        source.unlink()
        source.write_bytes(original)
        output.symlink_to(self.base / 'missing-destination')
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, output)
        self.assertTrue(output.is_symlink())
        self.assertFalse((self.base / 'missing-destination').exists())
        assets_alias = self.base / 'assets-alias'
        assets_alias.symlink_to(self.assets, target_is_directory=True)
        with self.assertRaises(ValueError):
            bundle.generate(assets_alias)
        parent_alias = self.base / 'parent-alias'
        parent_alias.symlink_to(self.assets, target_is_directory=True)
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, parent_alias / 'new-output.mjs')
        self.assertFalse((self.assets / 'new-output.mjs').exists())

    def test_generate_requires_ordinary_bounded_inputs_and_outputs(self):
        source = self.assets / MODULES[0]
        saved = source.read_bytes()
        source.unlink()
        source.mkdir()
        output = self.base / 'ordinary-output.mjs'
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, output)
        self.assertFalse(output.exists())
        source.rmdir()
        source.write_bytes(saved)
        output.mkdir()
        with self.assertRaises(ValueError):
            bundle.generate(self.assets, output)
        self.assertEqual(list(output.iterdir()), [])
        output.rmdir()
        output.write_bytes(b'unchanged prior output\n')
        stat = Path.stat

        for oversized in (source, output):
            def huge_stat(path, *args, **kwargs):
                state = stat(path, *args, **kwargs)
                if path != oversized:
                    return state
                values = {name: getattr(state, name) for name in dir(state) if name.startswith('st_')}
                values['st_size'] = 1 << 40
                return SimpleNamespace(**values)

            with self.subTest(oversized=oversized.name), mock.patch.object(Path, 'stat', huge_stat), \
                    self.assertRaises(ValueError):
                bundle.generate(self.assets, output)
            self.assertEqual(source.read_bytes(), saved)
            self.assertEqual(output.read_bytes(), b'unchanged prior output\n')

    def test_generate_bounds_reads_when_input_or_existing_output_grows_after_stat(self):
        output = self.base / 'growing-output.mjs'
        prior = b'unchanged output fixture\n'
        output.write_bytes(prior)
        path_open = Path.open
        for growing, field, limit in (
                (self.assets / MODULES[0], 'MAX_INPUT_BYTES', max(map(len, self.blobs.values())) + 8),
                (output, 'MAX_BUNDLE_BYTES', len(bundle.module_bytes(bundle.build(self.blobs))) + 8)):
            reads = []
            content = growing.read_bytes()
            grown = content + b' ' * (limit + 1 - len(content))

            class GrowingFile(io.BytesIO):
                def read(self, size=-1):
                    if size < 0 or size > limit + 1:
                        raise AssertionError('surface file read must remain bounded')
                    reads.append(size)
                    return super().read(size)

            def growing_open(path, *args, **kwargs):
                if path == growing and (args[0] if args else kwargs.get('mode')) == 'rb':
                    return GrowingFile(grown)
                return path_open(path, *args, **kwargs)

            with self.subTest(growing=growing.name), mock.patch.object(bundle, field, limit), \
                    mock.patch.object(Path, 'open', growing_open), self.assertRaises(ValueError):
                bundle.generate(self.assets, output)
            self.assertEqual(reads, [limit + 1])
            self.assertEqual(output.read_bytes(), prior)

    def test_actual_retained_renderer_patch_graph_and_separate_legacy_bundle(self):
        # Read two exact retained members in memory. No source extraction,
        # configure, build, ignored evidence or original Git checkout is needed.
        group = ROOT / 'third_party/gui-inputs'
        manifest_data = (group / 'manifest.json').read_bytes()
        retained = json.loads(manifest_data)
        sums = dict(line.split('  ')[::-1] for line in (group / 'SHA256SUMS').read_text().splitlines())
        self.assertEqual(hashlib.sha256(manifest_data).hexdigest(), sums['manifest.json'])
        archive_path = group / 'gui-inputs.tar.gz'
        archive_hash = hashlib.sha256()
        with archive_path.open('rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                archive_hash.update(block)
        self.assertEqual(archive_hash.hexdigest(), retained['archive_sha256'])
        self.assertEqual(archive_hash.hexdigest(), sums['gui-inputs.tar.gz'])
        lock = json.loads((ROOT / 'third_party/gui-boundary.lock.json').read_bytes())
        members = {}
        with tarfile.open(archive_path, 'r:gz') as archive:
            for name in ('backends/web/renderer.mjs', 'backends/web/style.css'):
                member = archive.getmember('upstream/' + name)
                expected = retained['files'][member.name]
                self.assertTrue(member.isfile())
                self.assertEqual(member.size, expected['size'])
                self.assertLess(member.size, bundle.MAX_INPUT_BYTES)
                with archive.extractfile(member) as source:
                    content = source.read(bundle.MAX_INPUT_BYTES + 1)
                self.assertEqual(len(content), expected['size'])
                self.assertEqual(hashlib.sha256(content).hexdigest(), expected['sha256'])
                self.assertEqual(expected['sha256'], lock['files'][name])
                members[name] = content
        spec = importlib.util.spec_from_file_location('surface_fixture_exact_patch', ROOT / 'gui/patches/apply.py')
        patcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patcher)
        generated = {'backends/web/renderer.mjs': members['backends/web/renderer.mjs'].decode('utf-8'),
                     'patch-inputs/renderer-surface-frame.mjs': (ROOT / 'gui/host/renderer_frame.mjs').read_text(encoding='utf-8')}
        cmake = (ROOT / 'gui/CMakeLists.txt').read_text()
        calls = re.findall(r'^foundation_gui_(?:patch|repatch)\((\S+) (\S+) (\S+)\)\s*$', cmake, re.M)
        applied = []
        for source, patch, destination in calls:
            if source in generated:
                patch_data = (ROOT / 'gui/patches' / patch).read_text(encoding='utf-8')
                generated[destination] = patcher.apply(generated[source], patch_data)
                applied.append(patch)
        self.assertEqual(applied, ['web-ordering.patch', 'web-responsiveness.patch', 'web-file-services.patch',
                                   'web-split.patch', 'web-context-renderer.patch', 'web-shortcuts-renderer.patch',
                                   'web-masked-text-renderer.patch', 'nonvisual-command-renderer.patch',
                                   'wheel-chaining-renderer.patch', 'wheel-accumulation-renderer.patch',
                                   'text-frame-renderer.patch', 'web-context-routing-renderer.patch',
                                   'surface-renderer.patch', 'surface-frame.patch'])
        actual = {name: (ROOT / 'gui/host' / name).read_bytes() for name in MODULES
                  if name not in ('renderer_surface_dom.mjs', 'renderer_surface_frame.mjs')}
        actual.update({'renderer_surface_dom.mjs': generated['web/renderer_surface_dom.mjs'].encode('utf-8'),
                       'renderer_surface_frame.mjs': generated['web/renderer_surface_frame.mjs'].encode('utf-8'),
                       'style.css': members['backends/web/style.css']})
        metadata = bundle.build(actual)
        encoded = bundle.module_bytes(metadata)
        self.assertEqual(bundle.parse_module(encoded), metadata)
        self.assertEqual(bundle.verify_assets({**actual, BUNDLE_NAME: encoded}), metadata)
        ordinary = {name: (ROOT / 'gui/host' / name).read_bytes() for name in legacy.CHILD_MODULES
                    if name != 'renderer_dom.mjs'}
        ordinary.update({'renderer_dom.mjs': generated['web/renderer_dom.mjs'].encode('utf-8'),
                         'style.css': actual['style.css']})
        binary = legacy.assemble(ordinary)
        self.assertEqual(legacy.parse_module(legacy.module_bytes(binary)), binary)
        self.assertEqual(set(binary['CHILD_INPUTS']), set(legacy.CHILD_MODULES) | {'style.css'})
        self.assertNotIn('__modules["browser_surface.mjs"]', binary['CHILD_SCRIPT'])
        self.assertNotIn('__modules["browser_surface_protocol.mjs"]', binary['CHILD_SCRIPT'])
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node is required for actual generated graph syntax checks')
        for name, data in ((BUNDLE_NAME, encoded), ('surface-child-script.cjs', metadata['CHILD_SCRIPT'].encode('utf-8'))):
            destination = self.base / name
            destination.write_bytes(data)
            checked = subprocess.run([node, '--check', str(destination)], cwd=self.base,
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

    def test_cli_default_and_explicit_outputs_match_canonical_fixture(self):
        command = [sys.executable, str(ROOT / 'tools/browser_surface_bundle.py'), '--assets', str(self.assets)]
        for output in (None, self.base / 'cli-explicit.mjs'):
            arguments = command if output is None else [*command, '--output', str(output)]
            completed = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, timeout=10)
            with self.subTest(output=output):
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                destination = self.assets / BUNDLE_NAME if output is None else output
                self.assertEqual(destination.read_bytes(), bundle.module_bytes(bundle.build(self.blobs)))


if __name__ == '__main__':
    unittest.main()
