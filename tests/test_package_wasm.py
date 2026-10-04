import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('package_wasm', ROOT / 'tools/package_wasm.py')
package_wasm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_wasm)


class PackageWasmTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        for name in package_wasm.ASSETS:
            (self.assets / name).write_text('// local fixture\n')
        (self.assets / 'gui_web_wasm.wasm').write_bytes(b'\0asm\x01\0\0\0')
        (self.assets / 'boot.mjs').write_text("import './renderer.mjs';import './browser_lifecycle.mjs';import './wasm_transport.mjs';")
        (self.assets / 'index.html').write_text('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/style.css"><div id="status"></div><script type="module" src="/boot.mjs"></script>')
        self.notice = self.root / 'LICENSE'
        self.notice.write_text('Example notice <safe> </script>')
        self.output = self.root / 'output'

    def make(self):
        return package_wasm.package(self.assets, self.output, [self.notice])

    def test_offline_inventory_notice_and_deterministic_output(self):
        expected = self.make()
        html = (self.output / package_wasm.HTML_NAME).read_text()
        self.assertIn("connect-src &#x27;none&#x27;", html)
        self.assertNotIn('src="/boot.mjs"', html)
        self.assertIn('Example notice &lt;safe&gt; &lt;/script&gt;', html)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.assertEqual(self.make(), expected)
        self.assertEqual({p.name: p.read_bytes() for p in self.output.iterdir()}, before)
        self.assertEqual(package_wasm.verify(self.output), expected)

    def test_tampering_and_extra_files_fail(self):
        self.make()
        html = self.output / package_wasm.HTML_NAME
        html.write_bytes(html.read_bytes() + b'bad')
        with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
            package_wasm.verify(self.output)
        self.make()
        (self.output / 'external.js').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            package_wasm.verify(self.output)
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            self.make()

    def test_missing_notice_or_asset_rejected(self):
        with self.assertRaisesRegex(ValueError, 'notice'):
            package_wasm.package(self.assets, self.output, [])
        (self.assets / 'wasm_worker.mjs').unlink()
        with self.assertRaisesRegex(ValueError, 'ordinary asset'):
            self.make()

    def test_module_and_html_contract_drift_rejected(self):
        (self.assets / 'boot.mjs').write_text("import './other.mjs'")
        with self.assertRaisesRegex(ValueError, 'dependency changed'):
            self.make()

    def test_unsafe_css_and_bad_wasm_rejected(self):
        (self.assets / 'style.css').write_text('</style><script>bad()</script>')
        with self.assertRaisesRegex(ValueError, 'style terminator'):
            self.make()
        (self.assets / 'style.css').write_text('')
        (self.assets / 'gui_web_wasm.wasm').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'Wasm module header'):
            self.make()

    def test_notices_and_embedded_inputs_bound_even_with_updated_outer_checksums(self):
        for key in ('notices', 'inputs'):
            with self.subTest(key=key):
                self.make()
                path = self.output / 'web-manifest.json'
                manifest = json.loads(path.read_text())
                name = 'LICENSE' if key == 'notices' else 'wasm_worker.mjs'
                manifest[key][name] = '0' * 64
                path.write_text(json.dumps(manifest))
                (self.output / 'manifest.sha256').write_text(''.join(package_wasm.digest((self.output / name).read_bytes()) + '  ' + name + '\n'
                    for name in sorted((package_wasm.HTML_NAME, 'web-manifest.json'))))
                with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                    package_wasm.verify(self.output)

    def test_separate_module_directory_and_labeled_notices(self):
        modules = self.root / 'modules'; modules.mkdir()
        for name in ('gui_web_wasm.js', 'gui_web_wasm.wasm'):
            (self.assets / name).rename(modules / name)
        second = self.root / 'second'; second.mkdir(); (second / 'LICENSE').write_text('Second notice')
        manifest = package_wasm.package(self.assets, self.output,
            ['core=' + str(self.notice), 'toolchain=' + str(second / 'LICENSE')], modules)
        self.assertEqual(set(manifest['notices']), {'core', 'toolchain'})
        self.assertIn('Second notice', (self.output / package_wasm.HTML_NAME).read_text())
        with self.assertRaisesRegex(ValueError, 'Duplicate notice'):
            package_wasm.package(self.assets, self.output, [self.notice, second / 'LICENSE'], modules)

    def test_sdk_runtime_notices_require_exact_retained_hashes(self):
        sdk = self.root / 'sdk'; sdk.mkdir()
        names = ['LICENSE'] + list(package_wasm.WASM_RUNTIME_NOTICES)
        files = {}
        for name in names:
            path = sdk / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('notice ' + name)
            files[name] = package_wasm.digest(path.read_bytes())
        metadata = dict(target=dict(system='Emscripten'), licenses=['LICENSE'], files=files, recipe_id='a' * 64)
        (sdk / 'sdk.json').write_text(json.dumps(metadata))
        with patch.object(package_wasm, 'verify_sdk') as verify:
            manifest = package_wasm.package(self.assets, self.output, [self.notice], sdk=sdk)
            verify.assert_called_once_with(sdk.resolve(), release=True)
            self.assertEqual(len(manifest['notices']), 1 + len(names))
            self.assertEqual(manifest['sdk']['recipe_id'], 'a' * 64)
            (sdk / names[-1]).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'runtime notice differs'):
                package_wasm.package(self.assets, self.output, [self.notice], sdk=sdk)

    def test_asset_budget_and_checksums_enforced(self):
        original = package_wasm.MAX_TOTAL
        try:
            package_wasm.MAX_TOTAL = 1
            with self.assertRaisesRegex(ValueError, 'size'):
                self.make()
        finally:
            package_wasm.MAX_TOTAL = original
        self.make()
        (self.output / 'manifest.sha256').write_text('')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            package_wasm.verify(self.output)


if __name__ == '__main__':
    unittest.main()
