"""Public kernel dependency policy fixtures; no JavaScript runtime executes."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import package_appended_engine_wasm as producer
import appended_engine_consumer as engine
import browser_bundle
import test_package_appended_engine_wasm as rendering_fixture
import test_package_appended_engine_document_wasm as document_fixture


def generated_factory(name='Kernel', wasm='one.wasm'):
    return ('async function '+name+'(options={}){'+producer._KERNEL_NODE_DETECTION+
            producer._KERNEL_NODE_LOADER+'var _scriptName=import.meta.url;'+producer._KERNEL_NODE_IO+
            'else if(ENVIRONMENT_IS_SHELL){};const selected='+repr(wasm)+';return options;}export default '+name+';').encode()


class KernelFactoryPolicyTests(unittest.TestCase):
    def test_generated_shape_accepts_different_factories_without_hash_allowlist(self):
        for name, wasm in [('Kernel','one.wasm'),('DifferentKernel','other.wasm')]:
            result=producer.inspect_kernel_factory(generated_factory(name,wasm))
            self.assertEqual(result['guarded_node_module_dependencies'],['node:module'])
            self.assertEqual(result['guarded_node_builtin_requires'],['node:fs','node:path','node:url'])
            self.assertFalse(result['product_bytes_modified'])
            self.assertFalse(result['runtime_inertness_proven'])

    def test_rendering_and_document_receipts_use_kernel_role_policy(self):
        for cls in (rendering_fixture.RichBrowserProducerTests,document_fixture.DocumentBrowserProducerTests):
            case=cls();case.setUp();self.addCleanup(case.doCleanups)
            factory=generated_factory();receipt=case.kernel_receipt('both',factory=factory)
            _,eligible=case.receipt_check(receipt,profile='both',factory=factory)
            self.assertFalse(eligible)

    def test_engine_and_child_module_policies_remain_strict(self):
        factory=generated_factory()
        with self.assertRaises(ValueError):engine.scan_factory(factory)
        with self.assertRaises(ValueError):browser_bundle._keywords(factory.decode())

    def test_changed_guard_builtin_and_extra_dependencies_reject(self):
        body=generated_factory()
        variants=(body.replace(b'if(ENVIRONMENT_IS_NODE)',b'if(true)',1),
                  body.replace(b'node:fs',b'node:child_process'),
                  body.replace(b'return options;',b'await import("external.mjs");return options;'),
                  body.replace(b'return options;',b'require("node:fs");return options;'),
                  body.replace(b'return options;',b'main();return options;'),
                  body+b'export const extra=1;')
        for candidate in variants:
            with self.subTest(candidate=candidate[-90:]),self.assertRaises(ValueError):
                producer.inspect_kernel_factory(candidate)

    def test_adapter_lookalikes_in_comments_cannot_mask_real_dependencies(self):
        comments='/*'+producer._KERNEL_NODE_DETECTION+producer._KERNEL_NODE_LOADER+producer._KERNEL_NODE_IO+'else if(ENVIRONMENT_IS_SHELL){}*/'
        factory=('async function Kernel(){'+comments+'await import("node:module");}export default Kernel;').encode()
        with self.assertRaises(ValueError):producer.inspect_kernel_factory(factory)

    def test_unguarded_loader_and_unsupported_shapes_reject(self):
        body=generated_factory()
        for candidate in (body.replace(producer._KERNEL_NODE_LOADER.encode(),b'const{createRequire}=await import("node:module");'),
                          body.replace(b'globalThis.process?.type!="renderer"',b'true'),
                          body.replace(b'async function Kernel',b'async function $foundation_kernel_node_marker$')):
            with self.subTest(candidate=candidate[:80]),self.assertRaises(ValueError):
                producer.inspect_kernel_factory(candidate)

    def test_guard_writes_aliases_and_shadow_bindings_reject(self):
        body=generated_factory()
        for statement in ('ENVIRONMENT_IS_NODE=true;', '(ENVIRONMENT_IS_NODE)=true;',
                          '[ENVIRONMENT_IS_NODE]=[true];', '({x:ENVIRONMENT_IS_NODE}={x:true});',
                          'ENVIRONMENT_IS_NODE++;', 'const alias=ENVIRONMENT_IS_NODE;',
                          'function shadow(ENVIRONMENT_IS_NODE){}',
                          'const shadow=({ENVIRONMENT_IS_NODE})=>0;',
                          'const object={ENVIRONMENT_IS_NODE:true};'):
            changed=body.replace(producer._KERNEL_NODE_LOADER.encode(),
                                 statement.encode()+producer._KERNEL_NODE_LOADER.encode())
            with self.subTest(statement=statement),self.assertRaises(ValueError):
                producer.inspect_kernel_factory(changed)


if __name__=='__main__':unittest.main()
