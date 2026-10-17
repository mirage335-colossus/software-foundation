"""Focused carrier, portable-byte transport and private Worker lifecycle checks.

Node exercises production JavaScript without a real browser. These checks do
not qualify browser CSP enforcement, rendering or direct-file engine behavior.
"""
import base64
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended_container as container
import package_appended_wasm as package
from test_appended_wasm import module, name as wasm_name, section, uint
from test_browser_bundle import fixture_blobs

APP = {'id': 'org.example.browser', 'name': 'Browser fixture', 'version': '1.0.0'}


def provider_kernel(*, marker=package.PROVIDERS_EXPORT, kind=0):
    # A complete tiny host module with one () -> i32 marker returning ABI1.0.
    export = wasm_name(marker) + bytes([kind]) + b'\0'
    body = b'\0\x41\x80\x80\x04\x0b'
    return (b'\0asm\1\0\0\0' + section(1, b'\1\x60\0\1\x7f') + section(3, b'\1\0') +
            section(7, b'\1' + export) + section(10, b'\1' + uint(len(body)) + body))


class AppendedBrowserTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assets, self.source, self.output = (self.root / name for name in ('assets', 'source', 'output'))
        self.assets.mkdir()
        self.source.mkdir()
        (self.source / 'main.cpp').write_bytes(b'int main() {}\n')
        for name in package.ASSETS:
            if name in ('gui_appended_web_wasm.js', 'gui_appended_web_wasm.wasm'):
                continue
            original = ROOT / 'gui' / 'host' / name
            if original.is_file():
                (self.assets / name).write_bytes(original.read_bytes())
        for name, data in fixture_blobs().items():
            (self.assets / name).write_bytes(data)
        package.browser_bundle.generate(self.assets, self.assets / package.browser_bundle.BUNDLE_NAME)
        (self.assets / 'gui_appended_web_wasm.js').write_bytes(b'export default async function(){throw Error("fixture only");}\n')
        (self.assets / 'gui_appended_web_wasm.wasm').write_bytes(b'\0asm\1\0\0\0')
        self.notice = self.root / 'LICENSE'
        self.notice.write_text('Fixture notice </script> <safe>\n', encoding='utf-8')

    def produce(self, *, providers=False):
        return package.package(self.assets, self.output, ['fixture=' + str(self.notice)], source_root=self.source, providers=providers)

    def rewrite_checksums(self):
        (self.output / 'manifest.sha256').write_bytes(''.join(container.digest((self.output / name).read_bytes()) + '  ' + name + '\n'
            for name in sorted((package.HTML_NAME, package.DESCRIPTOR_NAME))).encode('ascii'))

    def binary(self, data=None):
        return container.build_package({'binary/application.wasm': data or module()}, APP,
                                       binary_entry='binary/application.wasm', binary_profile='foundation-guest-v1',
                                       requires={'abi': {'major': 1, 'minor': 0}, 'services': ['foundation.view'],
                                                 'capabilities': ['foundation.view.v1']})

    def test_pristine_deterministic_strict_prefix_and_separate_descriptor_kind(self):
        descriptor = self.produce()
        self.assertEqual(descriptor['carrier'], 'html')
        self.assertEqual(descriptor['profile'], 'binary')
        self.assertEqual(descriptor['provenance']['kind'], package.KIND)
        self.assertEqual(descriptor['provenance']['renderer_modes'], ['isolated'])
        self.assertEqual(package.verify(self.output, container.digest((self.output / package.DESCRIPTOR_NAME).read_bytes())), descriptor)
        prefix = (self.output / package.HTML_NAME).read_bytes()
        self.assertTrue(prefix.endswith(container.HTML_MARKER))
        self.assertNotIn(container.HTML_OPEN, prefix)
        self.assertNotIn(b'Fixture notice </script>', prefix)
        self.assertEqual(container.parse_artifact(prefix, descriptor).mode, 'neither')
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        with self.assertRaises(FileExistsError):
            self.produce()
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.output.iterdir()})
        other = self.root / 'second-output'
        self.assertEqual(package.package(self.assets, other, ['fixture=' + str(self.notice)], source_root=self.source), descriptor)
        self.assertEqual(before, {path.name: path.read_bytes() for path in other.iterdir()})
        self.assertFalse((self.output / 'web-manifest.json').exists())

    def test_replace_remove_retain_exact_prefix_and_same_portable_module(self):
        descriptor = self.produce()
        prefix = (self.output / package.HTML_NAME).read_bytes()
        first = container.compose_bytes(prefix, descriptor, self.binary(), expected_mode='binary')
        second_module = module(import_call=True)
        second = container.compose_bytes(first, descriptor, self.binary(second_module), expected_mode='binary')
        parsed = container.parse_artifact(second, descriptor, expected_mode='binary')
        self.assertEqual(parsed.prefix, prefix)
        self.assertEqual(parsed.package.file_bytes('binary/application.wasm'), second_module)
        self.assertEqual(second.count(container.HTML_OPEN), 1)
        self.assertEqual(container.compose_bytes(second, descriptor, expected_mode='neither'), prefix)
        with self.assertRaises(container.ContainerError):
            container.compose_bytes(prefix, descriptor, container.build_package({'web/index.html': b'<script>throw 1</script>'}, APP, web_entry='web/index.html'))

    def test_provider_policy_requires_compiled_function_marker_without_output(self):
        kernel = self.assets / 'gui_appended_web_wasm.wasm'
        candidates = [b'\0asm\1\0\0\0',
                      b'\0asm\1\0\0\0' + section(0, wasm_name(package.PROVIDERS_EXPORT)),
                      provider_kernel(marker='minified_export'), provider_kernel(kind=3)]
        # A named JS facade does not prove the raw compiled Wasm marker exists.
        (self.assets / 'gui_appended_web_wasm.js').write_bytes(b'export default async()=>({_gui_web_providers_v1(){return 65536;}});')
        for candidate in candidates:
            kernel.write_bytes(candidate)
            with self.assertRaisesRegex(ValueError, 'function export'):
                self.produce(providers=True)
            self.assertFalse(self.output.exists())

    def test_provider_policy_is_explicit_and_verifies_without_flag(self):
        (self.assets / 'gui_appended_web_wasm.wasm').write_bytes(provider_kernel())
        base = self.produce()
        self.assertEqual(base['services'], package.POLICY['services'])
        self.assertEqual(base['capabilities'], package.POLICY['capabilities'])
        base_prefix = (self.output / package.HTML_NAME).read_bytes()
        self.output = self.root / 'provider-output'
        result = self.produce(providers=True)
        self.assertEqual(result['services'], package.PROVIDERS_POLICY['services'])
        self.assertEqual(result['capabilities'], package.PROVIDERS_POLICY['capabilities'])
        self.assertEqual(package.verify(self.output), result)
        self.assertIsNone(package.main(['--verify', '--output', str(self.output)]))
        self.assertEqual(container.parse_artifact(base_prefix, base).prefix, base_prefix)
        index = self.binary().index
        requiring = container.build_package({'binary/application.wasm': module()}, APP,
            binary_entry='binary/application.wasm', binary_profile='foundation-guest-v1',
            requires={'abi': index['requires']['abi'], 'services': ['foundation.providers'],
                      'capabilities': ['foundation.providers.v1']})
        with self.assertRaisesRegex(ValueError, 'missing required'):
            container.compose_bytes(base_prefix, base, requiring)
        prefix = (self.output / package.HTML_NAME).read_bytes()
        composed = container.compose_bytes(prefix, result, requiring)
        parsed = container.parse_artifact(composed, result)
        self.assertEqual(parsed.package.file_bytes('binary/application.wasm'), module())
        self.assertEqual(container.compose_bytes(composed, result), prefix)

    def test_provider_export_scanner_bounds_and_exact_entries(self):
        good = provider_kernel()
        self.assertTrue(package._provider_export(good))
        padded_export = b'\x81\0' + wasm_name(package.PROVIDERS_EXPORT) + b'\0\x80\0'
        self.assertTrue(package._provider_export(b'\0asm\1\0\0\0' + section(7, padded_export)))
        export = b'\1' + wasm_name(package.PROVIDERS_EXPORT) + b'\0\0'
        bad = [good + b'\0\x80', good + section(7, export),
               b'\0asm\1\0\0\0' + section(7, export + b'\0'),
               b'\0asm\1\0\0\0' + section(7, b'\2' + export[1:] * 2),
               b'\0asm\1\0\0\0\7\x80\x80\x80\x80\x10',
               b'\0asm\1\0\0\0' + section(7, b'\1\1\xff\0\0')]
        for data in bad:
            with self.assertRaises(ValueError):
                package._provider_export(data)

    def test_rehashed_provider_metadata_cannot_upgrade_old_compiled_kernel(self):
        descriptor = self.produce()
        prefix = (self.output / package.HTML_NAME).read_bytes()
        old = re.search(rb'<script type="application/octet-stream" id="foundation-appended-kernel">([^<]*)</script>', prefix)[1]
        metadata = container.parse_json(base64.b64decode(old))
        metadata['policy'] = package.PROVIDERS_POLICY
        forged = prefix.replace(old, base64.b64encode(container.canonical_json(metadata)), 1)
        descriptor.update(package.PROVIDERS_POLICY)
        descriptor['executable'] = {'length': len(forged), 'sha256': container.digest(forged)}
        (self.output / package.HTML_NAME).write_bytes(forged)
        (self.output / package.DESCRIPTOR_NAME).write_bytes(container.canonical_json(descriptor))
        self.rewrite_checksums()
        with self.assertRaisesRegex(ValueError, 'requires compiled kernel function export'):
            package.verify(self.output)

    def test_immutable_historical_v1_inventory_verifies_without_current_eligibility(self):
        from appended_policy import validate_kernel_inputs
        descriptor = self.produce()
        original = (self.output / package.HTML_NAME).read_bytes()
        descriptor['kernel_inputs']['projection'] = 'foundation-appended-kernel-v1'
        (self.output / package.DESCRIPTOR_NAME).write_bytes(container.canonical_json(descriptor))
        self.rewrite_checksums()
        retained = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.assertEqual(package.verify(self.output), descriptor)
        self.assertEqual({path.name: path.read_bytes() for path in self.output.iterdir()}, retained)
        self.assertEqual((self.output / package.HTML_NAME).read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'v1 is unsupported'):
            validate_kernel_inputs(descriptor['kernel_inputs'])
        from dependency_archive import encoded
        historical = json.loads(container.canonical_json(descriptor['kernel_inputs']))
        historical['files'].update({'README.md': '1' * 64, 'tests/historical.py': '2' * 64})
        historical['tree_sha256'] = container.digest(encoded({'files': historical['files'], 'executables': historical['executables']}))
        self.assertTrue(package._verify_retained_inputs(historical))
        composed = container.compose_bytes(original, descriptor, self.binary())
        self.assertEqual(container.parse_artifact(composed, descriptor).prefix, original)
        for change in (lambda value: value.pop('files'),
                       lambda value: value['files'].update({'../escape': '0' * 64}),
                       lambda value: value.update(executables=['missing']),
                       lambda value: value.update(tree_sha256='0' * 64)):
            invalid = json.loads(container.canonical_json(descriptor['kernel_inputs']))
            change(invalid)
            with self.assertRaises(ValueError):
                package._verify_retained_inputs(invalid)

    def test_new_provider_policy_cannot_be_retagged_as_historical_v1(self):
        (self.assets / 'gui_appended_web_wasm.wasm').write_bytes(provider_kernel())
        descriptor = self.produce(providers=True)
        descriptor['kernel_inputs']['projection'] = 'foundation-appended-kernel-v1'
        (self.output / package.DESCRIPTOR_NAME).write_bytes(container.canonical_json(descriptor))
        self.rewrite_checksums()
        retained = {path.name: path.read_bytes() for path in self.output.iterdir()}
        with self.assertRaisesRegex(ValueError, 'Historical browser inventory cannot advertise'):
            package.verify(self.output)
        self.assertEqual({path.name: path.read_bytes() for path in self.output.iterdir()}, retained)

    def test_source_and_asset_mutations_change_identity_and_tampering_fails(self):
        descriptor = self.produce()
        (self.source / 'main.cpp').write_bytes(b'int main() { return 1; }\n')
        self.output = self.root / 'changed-output'
        changed = self.produce()
        self.assertNotEqual(descriptor['executable'], changed['executable'])
        prefix = self.output / package.HTML_NAME
        prefix.write_bytes(prefix.read_bytes() + b'\n')
        with self.assertRaises(container.ContainerError):
            package.verify(self.output)
        self.output = self.root / 'third-output'
        self.produce()
        (self.assets / 'browser_embedding.mjs').write_bytes((self.assets / 'browser_embedding.mjs').read_bytes() + b"\nimport './unreviewed.mjs';\n")
        with self.assertRaisesRegex(ValueError, 'dependency changed'):
            self.produce()

    def test_missing_notice_source_or_kernel_rejected_without_building(self):
        with self.assertRaisesRegex(ValueError, 'source root'):
            package.package(self.assets, self.output, [str(self.notice)])
        with self.assertRaisesRegex(ValueError, 'notices'):
            package.package(self.assets, self.output, [], source_root=self.source)
        (self.assets / 'gui_appended_web_wasm.wasm').unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.produce()
        self.assertFalse(self.output.exists())

    def test_prefix_rehashed_outer_source_still_requires_canonical_generation(self):
        descriptor = self.produce()
        changed = (self.output / package.HTML_NAME).read_bytes().replace(b'<title>Binary application kernel</title>', b'<title>Changed title</title>')
        descriptor['executable'] = {'length': len(changed), 'sha256': container.digest(changed)}
        (self.output / package.HTML_NAME).write_bytes(changed)
        (self.output / package.DESCRIPTOR_NAME).write_bytes(container.canonical_json(descriptor))
        with self.assertRaisesRegex(ValueError, 'canonical retained inputs'):
            package.verify(self.output)

    def test_incomplete_input_inventory_or_forged_qualification_rejected(self):
        descriptor = self.produce()
        original = container.canonical_json(descriptor)
        mutations = [lambda value: value.update(kernel_inputs={'tree_sha256': value['kernel_inputs']['tree_sha256']}),
                     lambda value: value['provenance'].update(runtime='main-thread'),
                     lambda value: value['provenance'].update(qualification='qualified-release'),
                     lambda value: value['provenance'].pop('source_binding')]
        for change in mutations:
            altered = json.loads(original)
            change(altered)
            (self.output / package.DESCRIPTOR_NAME).write_bytes(container.canonical_json(altered))
            with self.assertRaises(ValueError):
                package.verify(self.output)

    def test_external_asset_change_before_publication_and_destination_race_fail_closed(self):
        original = package.make_prefix
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            path = self.assets / 'gui_appended_web_wasm.js'
            path.write_bytes(path.read_bytes() + b'// raced external input\n')
            return result
        with mock.patch.object(package, 'make_prefix', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'Input changed|bounded ordinary input'):
                self.produce()
        self.assertFalse(self.output.exists())
        write = container._write_new
        def race(path, content, **kwargs):
            if path.name == package.HTML_NAME:
                path.write_bytes(b'other writer')
            return write(path, content, **kwargs)
        with mock.patch.object(container, '_write_new', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'must be new'):
                self.produce()
        self.assertEqual((self.output / package.HTML_NAME).read_bytes(), b'other writer')
        self.assertFalse((self.output / package.DESCRIPTOR_NAME).exists())

    def node(self, source, *args):
        node = shutil.which('node') or shutil.which('nodejs')
        if not node:
            self.skipTest('Node is unavailable; browser model checks unexecuted')
        completed = subprocess.run([node, '--input-type=module', '-e', source, *map(str, args)], check=False,
                                   capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return completed.stdout

    def test_runtime_decodes_same_bytes_and_rejects_digest_trailer_and_web(self):
        descriptor = self.produce()
        prefix = (self.output / package.HTML_NAME).read_bytes()
        binary = self.binary()
        artifact = container.compose_bytes(prefix, descriptor, binary)
        encoded = artifact[len(prefix) + len(container.HTML_OPEN):-len(container.HTML_CLOSE)].decode('ascii')
        vector = self.root / 'vector.json'
        web = container.build_package({'web/index.html': b'<script>throw Error("must not run")</script>'}, APP, web_entry='web/index.html')
        web_encoded = base64.b64encode(web.data + container.trailer_bytes(prefix, web, 'html')).decode('ascii')
        bom_data = binary.data[:binary.index_offset] + b'\xef\xbb\xbf' + binary.data[binary.index_offset:]
        bom = container.Package(bom_data, binary.index, binary.index_offset, binary.index_length + 3)
        bom_encoded = base64.b64encode(bom.data + container.trailer_bytes(prefix, bom, 'html')).decode('ascii')
        vector.write_text(json.dumps({'encoded': encoded, 'prefix': base64.b64encode(prefix).decode(),
                                     'module': base64.b64encode(module()).decode(), 'policy': package.POLICY,
                                     'web': web_encoded, 'bom': bom_encoded}))
        self.node('''
import assert from 'node:assert/strict';import fs from 'node:fs';import {pathToFileURL} from 'node:url';import {webcrypto} from 'node:crypto';
if(!globalThis.crypto)Object.defineProperty(globalThis,'crypto',{value:webcrypto});
const {verifyAppendedBinary}=await import(pathToFileURL(process.argv[1]));
const v=JSON.parse(fs.readFileSync(process.argv[2])),prefix=new Uint8Array(Buffer.from(v.prefix,'base64'));
assert.equal(await verifyAppendedBinary(null,prefix,v.policy),null);
const decoded=await verifyAppendedBinary(v.encoded,prefix,v.policy);
assert.deepEqual(Buffer.from(decoded.module),Buffer.from(v.module,'base64'));
assert.equal(decoded.application.name,'Browser fixture');
let bad=Buffer.from(v.encoded,'base64');bad[0]^=1;await assert.rejects(verifyAppendedBinary(bad.toString('base64'),prefix,v.policy),/digest/);
bad=Buffer.from(v.encoded,'base64');bad[bad.length-1]=1;await assert.rejects(verifyAppendedBinary(bad.toString('base64'),prefix,v.policy),/trailer/);
await assert.rejects(verifyAppendedBinary(v.encoded,prefix,{...v.policy,services:[]}),/services/);
await assert.rejects(verifyAppendedBinary(v.encoded+'\\n',prefix,v.policy),/base64/);
await assert.rejects(verifyAppendedBinary(v.web,prefix,v.policy),/web applications are unavailable/);
await assert.rejects(verifyAppendedBinary(v.bom,prefix,v.policy));
''', self.assets / 'appended_browser_bootstrap.mjs', vector)

    def test_large_kernel_base64_and_canonical_padding(self):
        self.node('''
import assert from 'node:assert/strict';import {pathToFileURL} from 'node:url';
const {decodeAppendedBase64}=await import(pathToFileURL(process.argv[1]));
const bytes=Buffer.alloc(6*1024*1024+2,0x9a),encoded=bytes.toString('base64');
assert.deepEqual(Buffer.from(decodeAppendedBase64(encoded,bytes.length)),bytes);
assert.throws(()=>decodeAppendedBase64(encoded,bytes.length-1));
for(const invalid of ['AA=A','AAAA====','AB==','AAB=','AA==\\n','AA =','____','A'])
  assert.throws(()=>decodeAppendedBase64(invalid,64),invalid);
for(const valid of ['', 'AA==', 'AAA=', 'AAAA'])
  assert.equal(Buffer.from(decodeAppendedBase64(valid,64)).toString('base64'),valid);
''', self.assets / 'appended_browser_bootstrap.mjs')

    def test_generated_inline_bootstrap_reconstructs_prefix_and_handles_absence(self):
        self.produce()
        prefix = (self.output / package.HTML_NAME).read_bytes()
        own = re.search(rb'<script type="module" id="foundation-appended-bootstrap">([\s\S]*?)</script>', prefix)[1].decode('utf-8')
        raw = re.search(rb'<script type="application/octet-stream" id="foundation-appended-kernel">([^<]*)</script>', prefix)[1].decode('ascii')
        vector = self.root / 'inline.json'
        vector.write_text(json.dumps({'own': own, 'raw': raw, 'style': package.OUTER_STYLE, 'prefix': base64.b64encode(prefix).decode('ascii')}))
        self.node('''
import assert from 'node:assert/strict';import fs from 'node:fs';
const v=JSON.parse(fs.readFileSync(process.argv[1])),status={textContent:''},listeners=new Map(),notices=[];
globalThis.document={querySelector:name=>({'#foundation-appended-kernel':{textContent:v.raw},'#foundation-appended-bootstrap':{textContent:v.own},style:{textContent:v.style},'#status':status,'#application':{}}[name]),
  querySelectorAll:()=>[],createElement:()=>({append(){},textContent:''}),body:{append:value=>notices.push(value)}};
globalThis.addEventListener=(name,callback)=>listeners.set(name,callback);globalThis.removeEventListener=name=>listeners.delete(name);
globalThis.Blob=class{constructor(parts){this.source=parts.join('');}};
URL.createObjectURL=blob=>'data:text/javascript;base64,'+Buffer.from(blob.source).toString('base64');URL.revokeObjectURL=()=>{};
const probe=v.own.replace('const kernel=','globalThis.capturedPrefix=prefix;const kernel=');
await import('data:text/javascript;base64,'+Buffer.from(probe).toString('base64'));
assert.deepEqual(Buffer.from(globalThis.capturedPrefix),Buffer.from(v.prefix,'base64'));
assert.equal(status.textContent,'No binary application payload is attached.');assert.equal(notices.length,1);assert.equal(listeners.size,0);
''', vector)

    def test_private_worker_prepares_bytes_after_memory_growth_and_frees_on_failure(self):
        self.node('''
import assert from 'node:assert/strict';import {pathToFileURL} from 'node:url';
const {installAppendedWasmWorker}=await import(pathToFileURL(process.argv[1]));
const bytes=new Uint8Array([0,97,115,109,1,0,0,0]);
async function run(preparationError=''){
  const posted=[],calls=[];let closed=0,freed=0;
  const module={HEAPU8:new Uint8Array(1),_malloc:n=>{module.HEAPU8=new Uint8Array(64);return 16;},_free:p=>{assert.equal(p,16);freed++;},
    ccall:(name,result,types,args)=>{calls.push(name);if(name==='gui_web_prepare'){assert.deepEqual(module.HEAPU8.slice(16,24),bytes);return preparationError;}if(name==='gui_web_create')return '{}';}};
  const scope={postMessage:message=>posted.push(message),close:()=>closed++};
  installAppendedWasmWorker(scope,async()=>({default:async()=>module}));
  await scope.onmessage({data:{type:'init',epoch:'fixture',moduleURL:'fixture',appendedModule:bytes}});
  assert.equal(freed,1);
  if(preparationError){assert.equal(posted[0].type,'error');assert.equal(closed,1);assert.deepEqual(calls,['gui_web_prepare','gui_web_destroy']);}
  else{assert.equal(posted[0].type,'ready');assert.deepEqual(calls,['gui_web_prepare','gui_web_create']);await scope.onmessage({data:{type:'close'}});assert.equal(posted.at(-1).type,'closed');assert.equal(closed,1);assert.equal(calls.at(-1),'gui_web_destroy');}
}
await run();await run('invalid guest');
const posted=[];let loaded=0,closed=0;const scope={postMessage:m=>posted.push(m),close:()=>closed++};
installAppendedWasmWorker(scope,async()=>{loaded++;});await scope.onmessage({data:{type:'init',epoch:'fixture',moduleURL:'fixture'}});
assert.equal(loaded,0);assert.equal(closed,1);assert.equal(posted[0].type,'error');
const oversized=new Uint8Array(4*1024*1024+1);oversized.slice=()=>{throw Error('must not copy oversized input');};
const rejected=[];const big={postMessage:m=>rejected.push(m),close:()=>{}};
installAppendedWasmWorker(big,async()=>{throw Error('must not load oversized input');});
await big.onmessage({data:{type:'init',epoch:'fixture',moduleURL:'fixture',appendedModule:oversized}});
assert.match(rejected[0].message,/oversized/);
''', self.assets / 'appended_wasm_worker.mjs')


if __name__ == '__main__':
    unittest.main()
