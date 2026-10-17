"""Pure document-v2 carrier fixtures; no provider or Foundation is executed.

The inert retained group and Foundation observations say parser-fixture-only.
These tests prove byte closure and rejection behavior, never runtime eligibility.
"""
import base64
import copy
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_container as container
import appended_engine_document_consumer as consumer
import appended_engine_editor_consumer as editor_consumer
from appended_engine_editor_fixture import EditorEngineFixture, bootstrap as editor_bootstrap
import browser_bundle
import browser_surface_bundle as surface
import package_appended_engine_document_wasm as producer
from appended_policy import kernel_source_tree
from dependency_archive import encoded
from source_identity import source_tree
from appended_engine_document_fixture import (
    DocumentEngineFixture, TARGET, bootstrap, section, uleb, vector, wasm_name,
)


BASE_CHECKS = ('inert_factory', 'compiled_profile_query', 'engine_describe_match')
DOCUMENT_CHECKS = ('document_profile_query', 'engine_document_bootstrap', 'host_assets_match',
    'document_owner_app_native_effect_publication', 'document_work_and_action_ack',
    'document_terminal_unknown_no_replay')
PHYSICAL_CHECKS = ('raw-key-location-altgraph', 'mouse-five-buttons-context-cancel',
    'input-context-navigation-retirement', 'native-effect-input-admission',
    'document_current_physical_provider')
ORDER_CHECKS = ('kernel_document_facts_before_engine_factory',
    'engine_describe_before_kernel_configure', 'kernel_configure_before_start')
BOOTSTRAP_CHECKS = ('facts_before_configure', 'configure_once', 'configure_before_describe',
    'describe_before_start', 'no_host_callbacks_during_facts_or_configure', 'one_process_start')
KERNEL_FIELDS = {'schema_version', 'kind', 'kernel_profile', 'kernel_wasm_lookup',
    'engine_wasm_lookup', 'kernel_factory', 'kernel_wasm', 'engine_factory', 'engine_wasm',
    'engine_profile', 'engine_assets', 'notices'}
ENVELOPE_FIELDS = {'schema_version', 'kind', 'kernel', 'modules', 'evidence',
    'identities', 'group_files', 'document_profile'}
EVIDENCE_FIELDS = {'binary_manifest', 'source_manifest', 'recipe', 'proof',
    'provider_build', 'runtime', 'reports', 'interfaces'}
BLOCK = rb'(<script type="application/octet-stream" id="foundation-rich-kernel">)([A-Za-z0-9+/=]+)(</script>)'


def b64(raw):
    return base64.b64encode(raw).decode('ascii')


def asset_hashes(blobs):
    return {name: container.digest(raw) for name, raw in sorted(blobs.items())}


def host_blobs(*, physical=False):
    """Declaration-only lexical graphs, assembled without evaluating JavaScript."""
    graphs = {**browser_bundle.CHILD_GRAPH, **surface.CHILD_GRAPH}
    exports = {**browser_bundle.CHILD_EXPORTS, **surface.CHILD_EXPORTS}
    blobs = {}
    for filename, dependencies in graphs.items():
        imports = ''.join("import {" + exports[dep][0] + ' as dep' + str(index) + "} from './" + dep + "';\n"
                          for index, dep in enumerate(dependencies))
        declarations = ''.join('export const ' + item + '=' + str(index) + ';\n'
                               for index, item in enumerate(exports[filename]))
        blobs[filename] = (imports + declarations).encode()
    blobs['style.css'] = b'body{color:black}\n'
    if physical:
        blobs['renderer_surface_frame.mjs'] += b'// distinct physical parser bytes; never executed\n'
    blobs[browser_bundle.BUNDLE_NAME] = browser_bundle.module_bytes(browser_bundle.assemble(
        {key: blobs[key] for key in browser_bundle.CHILD_MODULES + ('style.css',)}))
    blobs[surface.BUNDLE_NAME] = surface.module_bytes(surface.build(
        {key: blobs[key] for key in surface.CHILD_MODULES + ('style.css',)}))
    for filename, dependencies in producer.IMPORTS.items():
        if filename not in blobs:
            imports = ''.join("import {fixture as dep" + str(index) + "} from './" + dep + "';\n"
                              for index, dep in enumerate(dependencies))
            blobs[filename] = (imports + 'export const fixture=0;\n').encode()
    return blobs


def foundation_wasm(*, missing=(), describe_type=5, dispatch_type=1,
                    memory=b'\x01\x01\x04', start=None, imported_memory=False,
                    getter='gui_web_engine_document_describe_v1',
                    composition=False, composition_type=0):
    """Independent nine-export Foundation section fixture; inert bodies never run."""
    types = [b'\x60\x00\x01\x7f', b'\x60\x05' + b'\x7f' * 5 + b'\x01\x7f',
             b'\x60\x01\x7f\x01\x7f', b'\x60\x01\x7f\x00', b'\x60\x00\x00',
             b'\x60\x02\x7f\x7f\x01\x7f']
    signatures = [0, 0, dispatch_type, 2, 2, 4, 2, 3, describe_type]
    names = ['gui_web_engine_bridge_v1', 'gui_web_engine_profile_v1', 'gui_web_engine_dispatch_v1',
             'gui_web_create', 'gui_web_receive', 'gui_web_destroy', 'malloc', 'free',
             getter]
    if composition:
        signatures.append(composition_type)
        names.append('gui_web_application_composition_v1')
    wasm = b'\0asm\x01\0\0\0' + section(1, vector(types))
    if imported_memory:
        wasm += section(2, vector([wasm_name('host') + wasm_name('memory') + b'\x02' + memory]))
    wasm += section(3, vector([uleb(item) for item in signatures]))
    if not imported_memory:
        wasm += section(5, vector([memory]))
    exports = [wasm_name(item) + b'\x00' + uleb(index) for index, item in enumerate(names) if item not in missing]
    exports.append(wasm_name('memory') + b'\x02\x00')
    wasm += section(7, vector(exports))
    if start is not None:
        wasm += section(8, uleb(start))
    bodies = [b'\x00\x0b' if item in (3, 4) else b'\x00\x41\x00\x0b' for item in signatures]
    return wasm + section(10, vector([uleb(len(body)) + body for body in bodies]))


def guest_wasm():
    """Minimal portable guest ABI bytes for suffix replacement; never instantiated."""
    types = [b'\x60\x00\x01\x7f', b'\x60\x01\x7f\x01\x7f', b'\x60\x02\x7f\x7f\x00',
             b'\x60\x02\x7f\x7f\x01\x7f', b'\x60\x01\x7f\x00']
    signatures = (0, 1, 2, 3, 3, 1, 4)
    names = ('foundation_app_abi_v1', 'foundation_app_alloc_v1', 'foundation_app_free_v1',
             'foundation_app_init_v1', 'foundation_app_dispatch_v1', 'foundation_app_step_v1',
             'foundation_app_shutdown_v1')
    bodies = [b'\x00\x41\x00\x0b', b'\x00\x20\x00\x0b', b'\x00\x0b',
              b'\x00\x41\x00\x0b', b'\x00\x41\x00\x0b', b'\x00\x20\x00\x0b', b'\x00\x0b']
    return (b'\0asm\x01\0\0\0' + section(1, vector(types))
        + section(3, vector([uleb(item) for item in signatures]))
        + section(5, b'\x01\x01\x01\x10')
        + section(7, vector([wasm_name(name) + b'\x00' + uleb(index) for index, name in enumerate(names)]
                             + [wasm_name('memory') + b'\x02\x00']))
        + section(10, vector([uleb(len(body)) + body for body in bodies])))


def replace_envelope(prefix, envelope):
    payload = base64.b64encode(container.canonical_json(envelope))
    result, count = re.subn(BLOCK, lambda match: match[1] + payload + match[3], prefix)
    if count != 1:
        raise AssertionError('fixture requires one envelope block')
    return result


class DocumentBrowserProducerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-document-carrier-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        (self.source / 'main.cpp').write_text('// inert source projection fixture\n')
        self.inputs, self.full = kernel_source_tree(self.source), source_tree(self.source)
        self.selected = 'pixel'
        self.fixture = DocumentEngineFixture(self.base / 'engine', document_profile=self.selected)
        self.group = self.base / 'group'
        self.fixture.export_group(self.group)
        self.engine = consumer.inspect_kernel_consumer(self.group, **self.fixture.group_arguments())
        self.blobs = host_blobs()
        self.factory = b'export default async function createFoundation(options={}) { return options; }\n'
        self.wasm = foundation_wasm()
        self.notices = {'foundation': b'Foundation parser fixture notice; no runtime distribution.\n'}
        self.receipt = self.kernel_receipt()

    def use_physical(self):
        self.selected = 'physical'
        self.fixture = DocumentEngineFixture(self.base / 'physical-engine', document_profile=self.selected)
        self.group = self.base / 'physical-group'
        self.fixture.export_group(self.group)
        self.engine = consumer.inspect_kernel_consumer(self.group, **self.fixture.group_arguments())
        self.blobs = host_blobs(physical=True)
        self.receipt = self.kernel_receipt()

    def kernel_receipt(self, profile='web', *, wasm=None, factory=None):
        wasm = self.wasm if wasm is None else wasm
        factory = self.factory if factory is None else factory
        engine_profile = self.engine.as_dict()['engine_profile']
        observed = container.canonical_json(engine_profile)
        combined = bootstrap(engine_profile)
        # The original engine fixture run has a different valid full-width Worker.
        combined.update(worker_epoch='4294967297', first_start_worker_epoch='4294967297')
        combined['engine_configure'].update(worker_lo=1, worker_hi=1)
        checks = BASE_CHECKS + DOCUMENT_CHECKS + (PHYSICAL_CHECKS if self.selected == 'physical' else ())
        return {'schema_version': 1, 'kind': 'foundation-rich-browser-document-kernel-proof-v1',
            'scope': 'parser-fixture-only', 'status': 'passed', 'profile': profile,
            'document_profile': self.selected,
            'source': {'tree_sha256': self.full['tree_sha256'], 'kernel_inputs_sha256': self.inputs['tree_sha256']},
            'toolchain': {'sdk_sha256': self.fixture.toolchain['paired_sdk_sha256'], 'target': copy.deepcopy(TARGET)},
            'artifacts': {'factory': {'sha256': container.digest(factory), 'bytes': len(factory)},
                'wasm': {'sha256': container.digest(wasm), 'bytes': len(wasm), 'lookup_name': 'gui_appended_engine_wasm.wasm'}},
            'wasm_facts': consumer.scan_wasm(wasm),
            'compiled_profile': {'export': 'gui_web_engine_profile_v1',
                'signature': {'params': [], 'results': ['i32']}, 'observed_result': 1 if profile == 'web' else 2,
                'before_configure': True},
            'engine_profile': copy.deepcopy(engine_profile),
            'compiled_document_profile': {'export': 'gui_web_engine_document_describe_v1',
                'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
                'observed_result': copy.deepcopy(engine_profile), 'observed_output': b64(observed),
                'observed_bytes': len(observed), 'before_engine_factory': True, 'before_configure': True},
            'engine_bootstrap': {'engine': combined, 'order': {name: 'passed' for name in ORDER_CHECKS}},
            'host_assets': asset_hashes(self.blobs), 'checks': {name: 'passed' for name in checks},
            'build_origin': 'synthetic parser fixture; no compilation/runtime execution'}

    def assemble(self, *, profile='web', receipt=None, blobs=None, wasm=None, factory=None,
                 notices=None, engine=None, document_profile=None, group_files=None):
        raw = encoded(self.kernel_receipt(profile) if receipt is None else receipt)
        return producer.make_prefix(self.blobs if blobs is None else blobs,
            self.factory if factory is None else factory, self.wasm if wasm is None else wasm,
            self.engine if engine is None else engine, raw, container.digest(raw),
            self.notices if notices is None else notices, self.full['tree_sha256'],
            self.inputs['tree_sha256'], profile,
            document_profile=self.selected if document_profile is None else document_profile,
            group_files=group_files)

    def receipt_check(self, value, *, profile='web', wasm=None, factory=None, pin=None,
                      host_assets=None, document_profile=None):
        raw = encoded(value)
        return producer.inspect_kernel_receipt(raw, container.digest(raw) if pin is None else pin,
            self.factory if factory is None else factory, self.wasm if wasm is None else wasm,
            profile, self.engine.as_dict()['engine_profile'],
            document_profile=self.selected if document_profile is None else document_profile,
            expected_kernel_inputs=self.inputs['tree_sha256'],
            host_assets=asset_hashes(self.blobs) if host_assets is None else host_assets)

    def composition_fixture(self, profile='web', **wasm_options):
        wasm = foundation_wasm(composition=True,
            getter=EDITOR_GETTER if self.selected == 'editor' else 'gui_web_engine_document_describe_v1',
            **wasm_options)
        value = self.kernel_receipt(profile, wasm=wasm)
        value['kind'] = (producer.EDITOR_COMPOSITION_RECEIPT_KIND if self.selected == 'editor'
                         else producer.COMPOSITION_RECEIPT_KIND)
        value['compiled_composition'] = {'export': 'gui_web_application_composition_v1',
            'signature': {'params': [], 'results': ['i32']},
            'observed_result': 5 if profile == 'web' else 7,
            'before_engine_factory': True, 'before_configure': True}
        value['checks']['application_composition_query'] = 'passed'
        return wasm, value

    def composition_profiles(self):
        yield self.selected
        if self.selected == 'pixel':
            self.use_physical()
            yield self.selected

    def test_composition_typed_receipts_preserve_document_selection_and_parser_scope(self):
        for selected in self.composition_profiles():
            for profile in ('web', 'both'):
                with self.subTest(selected=selected, profile=profile):
                    wasm, value = self.composition_fixture(profile)
                    checked, eligible = self.receipt_check(value, profile=profile, wasm=wasm)
                    self.assertFalse(eligible)
                    self.assertEqual(checked['document_profile'], selected)
                    self.assertEqual(checked['compiled_composition']['observed_result'], 5 if profile == 'web' else 7)
                    self.assertEqual(checked['host_assets'], asset_hashes(self.blobs))
                    self.assertEqual(checked['checks']['application_composition_query'], 'passed')
                    prefix, envelope, facts = self.assemble(profile=profile, receipt=value, wasm=wasm)
                    self.assertFalse(facts['production_eligible'])
                    self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)
                    descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
                    for key in ('capabilities', 'services'):
                        self.assertEqual(descriptor[key], producer.POLICIES[profile][key])

    def test_composition_receipt_requires_actual_typed_getter(self):
        for selected in self.composition_profiles():
            for options in ({'missing': ('gui_web_application_composition_v1',)}, {'composition_type': 2}):
                with self.subTest(selected=selected, options=options):
                    wasm, value = self.composition_fixture(**options)
                    with self.assertRaisesRegex(ValueError, 'typed document Foundation export'):
                        self.receipt_check(value, wasm=wasm)

    def test_composition_scalar_order_and_signature_are_exact(self):
        for selected in self.composition_profiles():
            for profile in ('web', 'both'):
                wasm, value = self.composition_fixture(profile)
                for scalar in (True, False, None, 1, 2, 7 if profile == 'web' else 5, 5.0 if profile == 'web' else 7.0):
                    with self.subTest(selected=selected, profile=profile, scalar=scalar):
                        changed = copy.deepcopy(value)
                        changed['compiled_composition']['observed_result'] = scalar
                        with self.assertRaisesRegex(ValueError, 'composition'):
                            self.receipt_check(changed, profile=profile, wasm=wasm)
                for key, replacement in (('before_engine_factory', False), ('before_configure', False),
                        ('export', 'gui_web_engine_profile_v1'), ('signature', {'params': ['i32'], 'results': ['i32']})):
                    with self.subTest(selected=selected, profile=profile, field=key):
                        changed = copy.deepcopy(value)
                        changed['compiled_composition'][key] = replacement
                        with self.assertRaisesRegex(ValueError, 'composition'):
                            self.receipt_check(changed, profile=profile, wasm=wasm)

    def test_composition_check_and_old_profile_checks_remain_required(self):
        for selected in self.composition_profiles():
            wasm, value = self.composition_fixture()
            for check in tuple(value['checks']):
                with self.subTest(selected=selected, missing_check=check):
                    changed = copy.deepcopy(value)
                    del changed['checks'][check]
                    with self.assertRaises(ValueError):
                        self.receipt_check(changed, wasm=wasm)
            # Counterfactual predicate inputs only; no eligible engine or output
            # is manufactured from the original parser-only observations.
            baseline = copy.deepcopy(value)
            baseline['scope'] = 'foundation-rich-kernel-runtime'
            self.assertTrue(self.receipt_check(baseline, wasm=wasm)[1])
            for status in ('failed', 'unfinished'):
                changed = copy.deepcopy(baseline)
                changed['checks']['application_composition_query'] = status
                self.assertFalse(self.receipt_check(changed, wasm=wasm)[1])
            self.assertEqual(value['scope'], 'parser-fixture-only')
            self.assertFalse(self.engine.as_dict()['production_eligible'])

    def test_composition_artifact_source_lookup_and_independent_pin_are_bound(self):
        for selected in self.composition_profiles():
            wasm, value = self.composition_fixture()
            for role in ('factory', 'wasm'):
                changed = copy.deepcopy(value)
                changed['artifacts'][role]['sha256'] = 'a' * 64
                with self.subTest(selected=selected, artifact=role), self.assertRaises(ValueError):
                    self.receipt_check(changed, wasm=wasm)
            changed = copy.deepcopy(value)
            changed['artifacts']['wasm']['lookup_name'] = 'different.wasm'
            with self.assertRaisesRegex(ValueError, 'lookup'):
                self.receipt_check(changed, wasm=wasm)
            changed = copy.deepcopy(value)
            changed['source']['kernel_inputs_sha256'] = 'b' * 64
            with self.assertRaisesRegex(ValueError, 'kernel inputs'):
                self.receipt_check(changed, wasm=wasm)
            with self.assertRaisesRegex(ValueError, 'independent pin'):
                self.receipt_check(value, wasm=wasm, pin='c' * 64)

    def test_composition_receipt_family_cannot_cross_or_attach_to_legacy_kind(self):
        for selected in self.composition_profiles():
            wasm, value = self.composition_fixture()
            wrong_kinds = (producer.RECEIPT_KIND if selected != 'editor' else producer.EDITOR_RECEIPT_KIND,
                producer.COMPOSITION_RECEIPT_KIND if selected == 'editor' else producer.EDITOR_COMPOSITION_RECEIPT_KIND,
                producer.rendering.COMPOSITION_RECEIPT_KIND)
            for kind in wrong_kinds:
                changed = copy.deepcopy(value)
                changed['kind'] = kind
                with self.subTest(selected=selected, kind=kind), self.assertRaises(ValueError):
                    self.receipt_check(changed, wasm=wasm)

    def test_composition_descriptor_dispatch_uses_the_admitted_document_receipt_family(self):
        # This is the pure policy calculation after admission, not runtime evidence.
        for selected in self.composition_profiles():
            for profile in ('web', 'both'):
                wasm, value = self.composition_fixture(profile)
                prefix, envelope, facts = self.assemble(profile=profile, receipt=value, wasm=wasm)
                facts['kernel_receipt']['scope'] = 'foundation-rich-kernel-runtime'
                facts['production_eligible'] = True
                descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
                with self.subTest(selected=selected, profile=profile):
                    self.assertIn('foundation.gui-composition.v1', descriptor['capabilities'])
                    self.assertEqual('foundation.view' in descriptor['services'], profile == 'both')
                    self.assertEqual('foundation.view.v1' in descriptor['capabilities'], profile == 'both')

    def test_legacy_receipt_with_typed_composition_export_keeps_old_policy(self):
        for selected in self.composition_profiles():
            for profile in ('web', 'both'):
                wasm, _ = self.composition_fixture(profile)
                value = self.kernel_receipt(profile, wasm=wasm)
                prefix, envelope, facts = self.assemble(profile=profile, receipt=value, wasm=wasm)
                self.assertFalse(facts['production_eligible'])
                descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
                for key in ('capabilities', 'services'):
                    self.assertEqual(descriptor[key], producer.POLICIES[profile][key])
                # An old receipt must not acquire new policy even when this
                # pure calculation receives otherwise eligible status inputs.
                facts['kernel_receipt']['scope'] = 'foundation-rich-kernel-runtime'
                facts['production_eligible'] = True
                descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
                for key in ('capabilities', 'services'):
                    self.assertEqual(descriptor[key], producer.POLICIES[profile][key])

    def test_old_descriptor_refuses_valid_new_compiled_startup(self):
        for selected in self.composition_profiles():
            prefix, envelope, facts = self.assemble()
            descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
            startup = container.canonical_json({'kind': 'foundation-appended-startup', 'primary': 'compiled', 'schema_version': 2})
            package = container.build_package({'web/index.html': b'<p>inert</p>', container.COMPOSITION_STARTUP_PATH: startup},
                {'id': 'org.example.document-composition', 'name': 'Document composition fixture', 'version': '1.0.0'},
                web_entry='web/index.html', requires=container._rich_requirements(None, 'compiled'))
            self.assertEqual(container.validate_rich_startup(package)['primary'], 'compiled')
            with self.subTest(selected=selected), self.assertRaisesRegex(ValueError, 'missing required capabilities'):
                container.compose_bytes(prefix, descriptor, package, expected_mode='web')

    def write_output(self, prefix, envelope, facts, name='retained'):
        output = self.base / name
        output.mkdir()
        descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
        contents = {producer.HTML_NAME: prefix, producer.DESCRIPTOR_NAME: container.canonical_json(descriptor)}
        for filename, raw in contents.items():
            (output / filename).write_bytes(raw)
        self.checksums(output, contents)
        return output, descriptor

    @staticmethod
    def checksums(output, contents):
        (output / 'manifest.sha256').write_text(''.join(container.digest(raw) + '  ' + name + '\n'
            for name, raw in sorted(contents.items())))

    def publish_arguments(self, **changes):
        assets = self.base / 'host-assets'
        assets.mkdir(exist_ok=True)
        for filename, raw in self.blobs.items():
            (assets / filename).write_bytes(raw)
        (assets / producer.FACTORY_NAME).write_bytes(self.factory)
        (assets / producer.WASM_NAME).write_bytes(self.wasm)
        receipt = self.base / 'kernel-receipt.json'
        receipt.write_bytes(encoded(self.receipt))
        notice = self.base / 'NOTICE'
        notice.write_bytes(self.notices['foundation'])
        options = {'profile': 'web', 'document_profile': self.selected, 'source_root': self.source,
            'engine_group': self.group,
            **{'engine_' + key + '_sha256': value for key, value in self.fixture.pins().items()},
            'kernel_receipt': receipt, 'kernel_receipt_sha256': container.digest(receipt.read_bytes()),
            'developer_unqualified': True}
        options.update(changes)
        return assets, ['foundation=' + str(notice)], options

    def test_pixel_prefix_has_exact_new_schemas_owned_interfaces_and_no_runtime_upgrade(self):
        first = self.assemble()
        self.assertEqual(first, self.assemble())
        prefix, envelope, facts = first
        self.assertTrue(prefix.endswith(container.HTML_MARKER))
        self.assertEqual(set(envelope), ENVELOPE_FIELDS)
        self.assertEqual(envelope['kind'], 'foundation-rich-browser-document-kernel-v1')
        self.assertEqual(envelope['document_profile'], 'pixel')
        self.assertEqual(set(envelope['kernel']), KERNEL_FIELDS)
        self.assertEqual(envelope['kernel']['kind'], 'foundation-copied-engine-document-browser')
        self.assertEqual(len(envelope['kernel']['engine_profile']), 24)
        self.assertEqual(envelope['kernel']['engine_profile']['capabilities'], '1795')
        self.assertEqual(set(envelope['evidence']['engine']), EVIDENCE_FIELDS)
        self.assertEqual(len(envelope['evidence']['engine']['interfaces']), 5)
        self.assertEqual({name: base64.b64decode(raw, validate=True) for name, raw
                          in envelope['evidence']['engine']['interfaces'].items()}, self.fixture.interfaces)
        checked, observed = producer.inspect_prefix(prefix)
        self.assertEqual(checked, envelope)
        self.assertFalse(facts['production_eligible'])
        self.assertFalse(observed['production_eligible'])
        self.assertFalse(observed['engine']['whole_group_verified'])
        self.assertEqual(observed['engine']['scope'], 'embedded-retained-document-v2-consumer-byte-and-static-contract-only')
        self.assertEqual(observed['kernel_receipt']['scope'], 'parser-fixture-only')

    def test_physical_prefix_keeps_thirty_facts_six_interfaces_and_full_host_inventory(self):
        self.use_physical()
        prefix, envelope, facts = self.assemble()
        self.assertEqual(envelope['document_profile'], 'physical')
        self.assertEqual(len(envelope['kernel']['engine_profile']), 30)
        self.assertEqual(envelope['kernel']['engine_profile']['capabilities'], '2003')
        self.assertEqual(len(envelope['evidence']['engine']['interfaces']), 6)
        self.assertEqual(facts['kernel_receipt']['host_assets'], asset_hashes(self.blobs))
        self.assertEqual(set(facts['kernel_receipt']['checks']), set(BASE_CHECKS + DOCUMENT_CHECKS + PHYSICAL_CHECKS))
        self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)
        self.assertFalse(facts['production_eligible'])

    def test_both_keeps_distinct_scalar_observation_and_fixed_provider_policy(self):
        prefix, envelope, facts = self.assemble(profile='both')
        self.assertEqual(envelope['kernel']['kernel_profile'], 'both')
        self.assertEqual(facts['kernel_receipt']['compiled_profile']['observed_result'], 2)
        descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
        self.assertEqual(descriptor['services'], ['foundation.kernel', 'foundation.providers'])
        self.assertEqual(descriptor['capabilities'], ['foundation.providers.v1', 'foundation.startup.v1'])
        descriptor['capabilities'].append('invented')
        self.assertEqual(producer.POLICIES['both']['capabilities'], ['foundation.providers.v1', 'foundation.startup.v1'])
        self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)

    def test_profile_is_explicit_and_cross_profile_or_legacy_relabeling_is_rejected(self):
        for selected in ('physical', 'copied259', 'physical467', '', True):
            with self.subTest(selected=selected), self.assertRaises((ValueError, TypeError)):
                self.assemble(document_profile=selected)
        args = (self.blobs, self.factory, self.wasm, self.engine, encoded(self.receipt),
                container.digest(encoded(self.receipt)), self.notices,
                self.full['tree_sha256'], self.inputs['tree_sha256'], 'web')
        with self.assertRaises(TypeError):
            producer.make_prefix(*args)
        with self.assertRaises(TypeError):
            producer.bootstrap_source()
        for kind in ('foundation-rich-browser-kernel-proof-v1', 'foundation-rich-browser-physical-kernel-proof-v1'):
            value = copy.deepcopy(self.receipt)
            value['kind'] = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.receipt_check(value)
        prefix, envelope, _ = self.assemble()
        for key, value in (('kind', 'foundation-rich-browser-kernel-v1'), ('document_profile', 'physical')):
            changed = copy.deepcopy(envelope)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                producer.inspect_prefix(replace_envelope(prefix, changed))

    def test_receipt_retains_raw_whitespace_without_confusing_count_and_typed_facts(self):
        value = copy.deepcopy(self.receipt)
        observation = value['compiled_document_profile']
        raw = json.dumps(observation['observed_result'], indent=1, sort_keys=False).encode() + b'\n'
        observation.update(observed_output=b64(raw), observed_bytes=len(raw))
        checked, eligible = self.receipt_check(value)
        self.assertEqual(checked['compiled_document_profile']['observed_output'], b64(raw))
        self.assertFalse(eligible)
        value['compiled_document_profile']['observed_result'] = len(raw)
        with self.assertRaises(ValueError):
            self.receipt_check(value)

    def test_compiled_document_observation_rejects_malformed_raw_count_and_profile(self):
        original = self.receipt['compiled_document_profile']
        malformed = [b'', b'\xef\xbb\xbf' + base64.b64decode(original['observed_output']),
                     b'\xff', b'{}\0', b' ' * 4096]
        for raw in malformed:
            value = copy.deepcopy(self.receipt)
            value['compiled_document_profile'].update(observed_output=b64(raw), observed_bytes=len(raw))
            with self.subTest(raw=raw[:8]), self.assertRaises((ValueError, UnicodeError)):
                self.receipt_check(value)
        changes = ({'observed_bytes': True}, {'observed_bytes': original['observed_bytes'] + 1},
            {'observed_output': original['observed_output'] + '\n'}, {'before_configure': False},
            {'before_engine_factory': False}, {'export': 'gui_web_engine_input_describe_v1'},
            {'signature': {'params': [], 'results': ['i32']}})
        for change in changes:
            value = copy.deepcopy(self.receipt)
            value['compiled_document_profile'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.receipt_check(value)
        value = copy.deepcopy(self.receipt)
        observed = value['compiled_document_profile']['observed_result']
        observed['capabilities'] = '259'
        raw = encoded(observed)
        value['compiled_document_profile'].update(observed_output=b64(raw), observed_bytes=len(raw))
        with self.assertRaises(ValueError):
            self.receipt_check(value)

    def test_duplicate_json_fields_are_rejected_even_when_values_match(self):
        original = container.canonical_json(self.receipt)
        key = b'"schema_version":1'
        self.assertTrue(original.startswith(b'{'))
        self.assertGreaterEqual(original.count(key), 1)
        raw = b'{"schema_version":1,' + original[1:]
        self.assertNotEqual(raw, original)
        self.assertEqual(raw.count(key), original.count(key) + 1)
        with self.assertRaises(ValueError):
            producer.inspect_kernel_receipt(raw, container.digest(raw), self.factory, self.wasm, 'web',
                self.engine.as_dict()['engine_profile'], document_profile='pixel',
                expected_kernel_inputs=self.inputs['tree_sha256'], host_assets=asset_hashes(self.blobs))
        value = copy.deepcopy(self.receipt)
        original_facts = base64.b64decode(value['compiled_document_profile']['observed_output'])
        self.assertTrue(original_facts.startswith(b'{'))
        self.assertEqual(original_facts.count(key), 1)
        facts = b'{"schema_version":1,' + original_facts[1:]
        self.assertNotEqual(facts, original_facts)
        self.assertEqual(facts.count(key), 2)
        value['compiled_document_profile'].update(observed_output=b64(facts), observed_bytes=len(facts))
        with self.assertRaises(ValueError):
            self.receipt_check(value)

    def test_combined_worker_is_full_width_and_independent_of_original_engine_run(self):
        checked, eligible = self.receipt_check(self.receipt)
        original = self.fixture.runtime['bootstrap']['worker_epoch']
        combined = checked['engine_bootstrap']['engine']
        self.assertNotEqual(combined['worker_epoch'], original)
        self.assertEqual(combined['worker_epoch'], '4294967297')
        self.assertEqual(combined['engine_configure']['worker_hi'], 1)
        self.assertFalse(eligible)
        for path, changed in ((('worker_epoch',), '1'), (('first_start_worker_epoch',), original),
                              (('engine_configure', 'worker_lo'), 2), (('marker_before',), 65536),
                              (('marker_after',), 0)):
            value = copy.deepcopy(self.receipt)
            target = value['engine_bootstrap']['engine']
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = changed
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.receipt_check(value)

    def test_partial_runtime_checks_are_retained_but_never_eligible(self):
        # Mutate only Foundation observation status; never manufacture eligible
        # engine fixture evidence or promote the fixture's declared scope.
        for status in ('unfinished', 'failed'):
            value = copy.deepcopy(self.receipt)
            value['checks']['document_work_and_action_ack'] = status
            checked, eligible = self.receipt_check(value)
            self.assertEqual(checked['checks']['document_work_and_action_ack'], status)
            self.assertFalse(eligible)
        for group, key in (('order', ORDER_CHECKS[0]), ('engine', 'facts_before_configure')):
            for status in ('failed', 'not-run'):
                value = copy.deepcopy(self.receipt)
                target = value['engine_bootstrap'][group]
                if group == 'engine':
                    target = target['checks']
                target[key] = status
                checked, eligible = self.receipt_check(value)
                self.assertFalse(eligible)
                self.assertEqual(checked['engine_bootstrap'][group]['checks'][key]
                                 if group == 'engine' else checked['engine_bootstrap'][group][key], status)

    def test_synthetic_foundation_predicate_requires_each_status_and_order_gate(self):
        # In-memory predicate inputs only: this explicit counterfactual scope is
        # never retained, sealed, executed, packaged or paired with an eligible
        # engine. Original fixture evidence remains parser-fixture-only.
        for selected in ('pixel', 'physical'):
            if selected == 'physical':
                self.use_physical()
            baseline = copy.deepcopy(self.receipt)
            baseline['scope'] = 'foundation-rich-kernel-runtime'
            self.assertTrue(self.receipt_check(baseline)[1])
            for status in ('unfinished', 'failed'):
                value = copy.deepcopy(baseline)
                value['status'] = status
                self.assertFalse(self.receipt_check(value)[1])
            groups = ((('checks',), tuple(baseline['checks']), ('unfinished', 'failed')),
                      (('engine_bootstrap', 'order'), ORDER_CHECKS, ('failed', 'not-run')),
                      (('engine_bootstrap', 'engine', 'checks'), BOOTSTRAP_CHECKS, ('failed', 'not-run')))
            for path, names, statuses in groups:
                for name in names:
                    for status in statuses:
                        value = copy.deepcopy(baseline)
                        target = value
                        for part in path:
                            target = target[part]
                        target[name] = status
                        with self.subTest(selected=selected, path=path, name=name, status=status):
                            self.assertFalse(self.receipt_check(value)[1])
            self.assertEqual(self.receipt['scope'], 'parser-fixture-only')
            self.assertFalse(self.engine.as_dict()['production_eligible'])

    def test_receipt_requires_exact_new_fields_check_names_and_status_domains(self):
        mutations = []
        for name in ('document_profile', 'compiled_document_profile', 'engine_bootstrap', 'host_assets'):
            value = copy.deepcopy(self.receipt)
            del value[name]
            mutations.append(value)
        for name in DOCUMENT_CHECKS:
            value = copy.deepcopy(self.receipt)
            del value['checks'][name]
            mutations.append(value)
        for status in ('passed ', True, 'not-run'):
            value = copy.deepcopy(self.receipt)
            value['checks']['document_profile_query'] = status
            mutations.append(value)
        for value in mutations:
            with self.subTest(keys=set(value)), self.assertRaises(ValueError):
                self.receipt_check(value)
        value = copy.deepcopy(self.receipt)
        value['engine_bootstrap']['order']['extra'] = 'passed'
        with self.assertRaises(ValueError):
            self.receipt_check(value)

    def test_actual_nine_typed_foundation_exports_are_required(self):
        variants = [foundation_wasm(missing=('gui_web_engine_document_describe_v1',)),
                    foundation_wasm(describe_type=0), foundation_wasm(dispatch_type=2),
                    foundation_wasm(missing=('malloc',)), foundation_wasm(missing=('free',))]
        for wasm in variants:
            with self.subTest(wasm=container.digest(wasm)), self.assertRaisesRegex(ValueError, 'typed.*export'):
                self.receipt_check(self.kernel_receipt(wasm=wasm), wasm=wasm)

    def test_foundation_memory_and_start_restrictions_are_not_relaxed_by_engine_policy(self):
        boundary = foundation_wasm(memory=b'\x01' + uleb(1) + uleb(65536))
        self.assertFalse(self.receipt_check(self.kernel_receipt(wasm=boundary), wasm=boundary)[1])
        variants = [foundation_wasm(imported_memory=True), foundation_wasm(memory=b'\x00\x01'),
                    foundation_wasm(memory=b'\x03\x01\x04'), foundation_wasm(start=5),
                    foundation_wasm(memory=b'\x01' + uleb(1) + uleb(65537))]
        for wasm in variants:
            with self.subTest(wasm=container.digest(wasm)), self.assertRaises(ValueError):
                self.receipt_check(self.kernel_receipt(wasm=wasm), wasm=wasm)

    def test_compiled_web_both_scalar_is_separate_and_strict(self):
        for change in ({'observed_result': True}, {'observed_result': 2}, {'before_configure': False},
                       {'export': 'gui_web_engine_document_describe_v1'}):
            value = copy.deepcopy(self.receipt)
            value['compiled_profile'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.receipt_check(value)
        with self.assertRaises(ValueError):
            self.receipt_check(self.receipt, profile='both')

    def test_receipt_artifacts_pin_lookup_and_kernel_inputs_are_actual_bytes(self):
        for field in ('factory', 'wasm'):
            value = copy.deepcopy(self.receipt)
            value['artifacts'][field]['sha256'] = 'f' * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.receipt_check(value)
        value = copy.deepcopy(self.receipt)
        value['artifacts']['wasm']['lookup_name'] = 'engine.wasm'
        with self.assertRaises(ValueError):
            self.receipt_check(value)
        value = copy.deepcopy(self.receipt)
        value['source']['kernel_inputs_sha256'] = 'e' * 64
        with self.assertRaises(ValueError):
            self.receipt_check(value)
        with self.assertRaises(ValueError):
            self.receipt_check(self.receipt, pin='f' * 64)

    def test_foundation_and_retained_engine_must_share_target_and_paired_sdk(self):
        for field, changed in (('sdk_sha256', 'f' * 64),
                               ('target', {**TARGET, 'triple': 'different-wasm32-triple'})):
            value = copy.deepcopy(self.receipt)
            value['toolchain'][field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.assemble(receipt=value)

    def test_pixel_requires_full_same_directory_host_inventory(self):
        for mode in ('missing', 'extra', 'changed'):
            value = copy.deepcopy(self.receipt)
            if mode == 'missing':
                del value['host_assets']['engine_kernel_bridge.mjs']
            elif mode == 'extra':
                value['host_assets']['unselected.mjs'] = 'a' * 64
            else:
                value['host_assets']['engine_kernel_bridge.mjs'] = 'a' * 64
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'host asset'):
                self.receipt_check(value)
        changed = dict(self.blobs)
        changed['engine_kernel_bridge.mjs'] += b'// selected host changed\n'
        with self.assertRaises(ValueError):
            self.assemble(blobs=changed)

    def test_generated_child_bundles_must_reconstruct_from_owned_sources(self):
        for filename in (browser_bundle.BUNDLE_NAME, surface.BUNDLE_NAME, 'renderer_surface_frame.mjs'):
            changed = dict(self.blobs)
            changed[filename] += b'// changed after generation\n'
            receipt = self.kernel_receipt()
            receipt['host_assets'] = asset_hashes(changed)
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                self.assemble(blobs=changed, receipt=receipt)

    def test_original_group_identity_closure_is_complete(self):
        groups = self.engine.as_dict()['group_files']
        stem = 'engine-' + self.fixture.pins()['recipe']
        self.assertEqual(set(groups), {stem + '-binary.tar.gz', stem + '-sources.tar.gz', stem + '-SHA256SUMS'})
        for changed in ({}, {**groups, 'extra': 'a' * 64}, {**groups, next(iter(groups)): 'bad'}):
            with self.subTest(groups=changed), self.assertRaises(ValueError):
                self.assemble(group_files=changed)
        _, envelope, _ = self.assemble()
        self.assertEqual(envelope['group_files'], groups)

    def test_embedded_interfaces_reject_missing_extra_hash_and_path_aliases(self):
        prefix, envelope, _ = self.assemble()
        path = next(iter(envelope['evidence']['engine']['interfaces']))
        for mode in ('missing', 'extra', 'changed', 'alias', 'noncanonical'):
            changed = copy.deepcopy(envelope)
            interfaces = changed['evidence']['engine']['interfaces']
            if mode == 'missing':
                del interfaces[path]
            elif mode == 'extra':
                interfaces['abi/engine/extra.json'] = b64(b'{}')
            elif mode == 'changed':
                interfaces[path] = b64(b'changed owned interface')
            elif mode == 'alias':
                interfaces['./' + path] = interfaces.pop(path)
            else:
                interfaces[path] += '\n'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                producer.inspect_prefix(replace_envelope(prefix, changed))

    def test_evidence_budgets_are_symmetric_and_preflight_interface_allocations(self):
        prefix, _, _ = self.assemble()
        for constant in ('MAX_INTERFACE_BYTES', 'MAX_INTERFACES_BYTES', 'MAX_EVIDENCE'):
            with self.subTest(constant=constant), patch.object(producer, constant, 1), \
                    patch.object(producer.contract, 'validate_interface_bytes',
                                 side_effect=AssertionError('budget must precede interface hashing')):
                with self.assertRaises(ValueError):
                    self.assemble()
                with self.assertRaises(ValueError):
                    producer.inspect_prefix(prefix)

    def test_report_count_is_bounded_in_raw_and_encoded_evidence(self):
        prefix, envelope, _ = self.assemble()
        changed = copy.deepcopy(envelope)
        changed['evidence']['engine']['reports'] = {'evidence/report' + str(i) + '.txt': b64(b'x') for i in range(1025)}
        with self.assertRaisesRegex(ValueError, 'count|inventory'):
            producer.inspect_prefix(replace_envelope(prefix, changed))
        evidence = self.fixture.evidence()
        evidence['reports'] = {name: b'x' for name in changed['evidence']['engine']['reports']}
        engine = consumer.ConsumerInspection(self.engine.metadata, self.engine.assets, self.engine.notices, evidence)
        with self.assertRaisesRegex(ValueError, 'count|inventory'):
            self.assemble(engine=engine)

    def test_retained_module_and_engine_bytes_are_hash_checked_not_metadata_only(self):
        prefix, envelope, _ = self.assemble()
        changes = [('module', 'engine_kernel_bridge.mjs'), ('kernel', 'engine_wasm'), ('kernel', 'kernel_factory')]
        for group, name in changes:
            changed = copy.deepcopy(envelope)
            if group == 'module':
                changed['modules'][name] = b64(b'export const tampered=1;\n')
            else:
                changed['kernel'][name]['data'] = b64(b'different bytes')
            with self.subTest(group=group, name=name), self.assertRaises(ValueError):
                producer.inspect_prefix(replace_envelope(prefix, changed))

    def test_notice_closure_and_external_data_have_no_loader_fallback(self):
        for notices in ({}, {'bad/name': b'text'}, {'foundation': b'\xff'}):
            with self.subTest(notices=notices), self.assertRaises((ValueError, UnicodeError)):
                self.assemble(notices=notices)
        data_fixture = DocumentEngineFixture(self.base / 'data-engine', document_profile='pixel', data=True)
        group = self.base / 'data-group'
        data_fixture.export_group(group)
        engine = consumer.inspect_kernel_consumer(group, **data_fixture.group_arguments())
        with self.assertRaisesRegex(ValueError, 'preloader'):
            self.assemble(engine=engine)
        _, envelope, _ = self.assemble()
        self.assertIn('foundation', envelope['kernel']['notices'])
        for path, raw in self.engine.notices.items():
            self.assertEqual(base64.b64decode(envelope['kernel']['notices']['engine/' + path]['data']), raw)

    def test_prefix_shell_and_fixed_descriptor_cannot_be_rewritten_by_metadata(self):
        prefix, envelope, _ = self.assemble()
        changed = copy.deepcopy(envelope)
        changed['kernel']['engine_profile']['capabilities'] = '467'
        with self.assertRaises(ValueError):
            producer.inspect_prefix(replace_envelope(prefix, changed))
        changed = copy.deepcopy(envelope)
        changed['kernel']['unexpected'] = True
        with self.assertRaises(ValueError):
            producer.inspect_prefix(replace_envelope(prefix, changed))
        with self.assertRaises(ValueError):
            producer.inspect_prefix(prefix.replace(b'</head>', b'<!-- modified shell --></head>', 1))

    def test_fixture_publication_is_refused_with_or_without_developer_flag_and_no_tools(self):
        assets, notices, options = self.publish_arguments()
        for developer in (False, True):
            output = self.base / ('output-' + str(developer))
            with self.subTest(developer=developer), \
                    patch.object(subprocess, 'run', side_effect=AssertionError('no compiler/network')), \
                    patch.object(subprocess, 'check_output', side_effect=AssertionError('no SDK/tool discovery')), \
                    patch.object(subprocess, 'Popen', side_effect=AssertionError('no child process')):
                with self.assertRaisesRegex(ValueError, 'developer-unqualified|production-ineligible|fixtures|runtime'):
                    producer.package(assets, output, notices, **{**options, 'developer_unqualified': developer})
                self.assertFalse(output.exists())

    def test_independent_engine_verification_precedes_final_foundation_receipt_admission(self):
        assets, notices, options = self.publish_arguments()
        with patch.object(consumer, 'verify_kernel_consumer', side_effect=ValueError('original engine refused')) as verify, \
                patch.object(producer, 'inspect_kernel_receipt', side_effect=AssertionError('no final receipt before eligible engine')):
            with self.assertRaisesRegex(ValueError, 'original engine refused'):
                producer.package(assets, self.base / 'absent', notices, **options)
        verify.assert_called_once()
        self.assertEqual(verify.call_args.kwargs['document_profile'], 'pixel')
        self.assertFalse((self.base / 'absent').exists())

    def test_preexisting_output_is_untouched_before_engine_inspection(self):
        assets, notices, options = self.publish_arguments()
        output = self.base / 'existing'
        output.mkdir()
        (output / 'foreign').write_bytes(b'preserve')
        with patch.object(consumer, 'verify_kernel_consumer', side_effect=AssertionError('no input inspection')):
            with self.assertRaisesRegex(ValueError, 'destination must be new'):
                producer.package(assets, output, notices, **options)
        self.assertEqual((output / 'foreign').read_bytes(), b'preserve')

    def test_every_independent_pin_failure_prevents_output_and_fallback(self):
        assets, notices, options = self.publish_arguments()
        for field in ('engine_recipe_sha256', 'engine_manifest_sha256', 'engine_proof_sha256',
                      'engine_runtime_sha256', 'kernel_receipt_sha256'):
            with self.subTest(field=field), patch.object(subprocess, 'Popen', side_effect=AssertionError('no fallback')), \
                    patch.object(consumer, 'verify_kernel_consumer', wraps=consumer.verify_kernel_consumer) as verify:
                with self.assertRaises(ValueError):
                    producer.package(assets, self.base / 'absent', notices, **{**options, field: 'f' * 64})
                self.assertFalse((self.base / 'absent').exists())
                if field == 'kernel_receipt_sha256':
                    verify.assert_not_called()
                else:
                    verify.assert_called_once()
                    expected = 'expected_' + field.removeprefix('engine_').removesuffix('_sha256')
                    self.assertEqual(verify.call_args.kwargs[expected], 'f' * 64)

    def test_package_preflights_all_notice_names_and_count_before_any_notice_snapshot(self):
        assets, _, options = self.publish_arguments()
        notice = self.base / 'NOTICE'
        original_snapshot = container._snapshot

        def snapshot(path, *args, **kwargs):
            self.assertNotEqual(Path(path), notice, 'notice allocated before complete inventory preflight')
            return original_snapshot(path, *args, **kwargs)

        inventories = ([name + '=' + str(notice) for name in ('same', 'same')],
                       ['valid=' + str(notice), 'invalid/name=' + str(notice)],
                       ['notice' + str(index) + '=' + str(notice) for index in range(128)])
        # The original engine contributes one retained notice, so 128 Foundation
        # labels exceed the combined 128 limit before any notice file is read.
        for inventory in inventories:
            with self.subTest(count=len(inventory)), \
                    patch.object(consumer, 'verify_kernel_consumer', return_value=self.engine), \
                    patch.object(container, '_snapshot', side_effect=snapshot), \
                    patch.object(producer, 'make_prefix', side_effect=AssertionError('invalid notice inventory reached assembly')):
                with self.assertRaisesRegex(ValueError, '[Nn]otice'):
                    producer.package(assets, self.base / 'absent', inventory, **options)
                self.assertFalse((self.base / 'absent').exists())

    def test_package_bounds_each_notice_snapshot_by_remaining_aggregate(self):
        assets, _, options = self.publish_arguments()
        first, second = self.base / 'notice-one', self.base / 'notice-two'
        first.write_bytes(b'abcd')
        second.write_bytes(b'xyz')
        engine_bytes = sum(len(raw) for raw in self.engine.notices.values())
        original_snapshot = container._snapshot
        allocations = []

        def snapshot(path, limit=container.MAX_ARTIFACT):
            path = Path(path)
            if path in (first, second):
                allocations.append((path, limit))
            return original_snapshot(path, limit)

        with patch.object(consumer, 'verify_kernel_consumer', return_value=self.engine), \
                patch.object(producer, 'MAX_NOTICES', engine_bytes + 6), \
                patch.object(container, '_snapshot', side_effect=snapshot), \
                patch.object(producer, 'make_prefix', side_effect=AssertionError('oversized notice reached assembly')):
            with self.assertRaises(ValueError):
                producer.package(assets, self.base / 'absent',
                    ['first=' + str(first), 'second=' + str(second)], **options)
        self.assertEqual(allocations, [(first, 6), (second, 2)])
        self.assertFalse((self.base / 'absent').exists())

    def test_late_publication_rechecks_group_source_and_local_snapshots_before_output(self):
        # Sequencing-only fault injection: bypass parser-fixture eligibility at
        # explicit pure seams, never produce an eligible engine proof or carrier.
        prefix, envelope, fixture_facts = self.assemble()
        synthetic_facts = {**fixture_facts, 'production_eligible': True}
        assets, notices, options = self.publish_arguments()
        selected_asset = assets / 'engine_kernel_bridge.mjs'
        source_file = self.source / 'main.cpp'
        original_asset, original_source = selected_asset.read_bytes(), source_file.read_bytes()
        for changed in ('group', 'source', 'local'):
            output = self.base / ('late-' + changed)
            calls = []

            def independent_verify(group, **selection):
                self.assertFalse(output.exists(), 'output reserved before independent final verification')
                calls.append((group, selection))
                if len(calls) == 2 and changed == 'group':
                    raise ValueError('retained group changed at final independent verification')
                return self.engine

            def synthetic_prefix_check(_prefix):
                self.assertEqual(_prefix, prefix)
                if changed == 'source':
                    source_file.write_bytes(original_source + b'// changed after snapshot\n')
                elif changed == 'local':
                    mutated = bytes((original_asset[0] ^ 1,)) + original_asset[1:]
                    self.assertEqual(len(mutated), len(original_asset))
                    self.assertNotEqual(mutated, original_asset)
                    selected_asset.write_bytes(mutated)
                return envelope, synthetic_facts

            with self.subTest(changed=changed), \
                    patch.object(consumer, 'verify_kernel_consumer', side_effect=independent_verify), \
                    patch.object(producer, 'make_prefix', return_value=(prefix, envelope, synthetic_facts)), \
                    patch.object(producer, 'inspect_prefix', side_effect=synthetic_prefix_check), \
                    patch.object(container, '_write_new', side_effect=AssertionError('no publication after changed input')), \
                    patch.object(subprocess, 'Popen', side_effect=AssertionError('no build fallback')):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    producer.package(assets, output, notices, **options)
                self.assertFalse(output.exists())
                self.assertEqual(len(calls), 2)
                self.assertEqual(calls[0], calls[1])
            source_file.write_bytes(original_source)
            selected_asset.write_bytes(original_asset)

    def test_output_inspection_preserves_fixture_scope_and_verify_rejects_it(self):
        prefix, envelope, facts = self.assemble()
        output, descriptor = self.write_output(prefix, envelope, facts)
        checked, observed = producer.inspect_output(output)
        self.assertEqual(checked, descriptor)
        self.assertFalse(observed['production_eligible'])
        self.assertFalse(observed['independently_pinned_descriptor'])
        pin = container.digest(container.canonical_json(descriptor))
        _, pinned = producer.inspect_output(output, pin)
        self.assertTrue(pinned['independently_pinned_descriptor'])
        self.assertFalse(pinned['production_eligible'])
        with self.assertRaisesRegex(ValueError, 'runtime|production-ineligible|fixtures'):
            producer.verify(output, pin)

    def test_output_checksum_inventory_descriptor_pin_and_extra_files_are_checked(self):
        prefix, envelope, facts = self.assemble()
        output, _ = self.write_output(prefix, envelope, facts)
        with self.assertRaises(ValueError):
            producer.inspect_output(output, 'f' * 64)
        (output / 'manifest.sha256').write_bytes(b'false checksum\n')
        with self.assertRaisesRegex(ValueError, 'checksum inventory'):
            producer.inspect_output(output)
        self.checksums(output, {producer.HTML_NAME: prefix,
            producer.DESCRIPTOR_NAME: (output / producer.DESCRIPTOR_NAME).read_bytes()})
        (output / 'extra').write_bytes(b'not in receipt')
        with self.assertRaises(ValueError):
            producer.inspect_output(output)

    def test_output_descriptor_metadata_cannot_upgrade_fixed_policy(self):
        prefix, envelope, facts = self.assemble()
        output, descriptor = self.write_output(prefix, envelope, facts)
        descriptor['capabilities'].append('foundation.view.v1')
        raw = container.canonical_json(descriptor)
        (output / producer.DESCRIPTOR_NAME).write_bytes(raw)
        self.checksums(output, {producer.HTML_NAME: prefix, producer.DESCRIPTOR_NAME: raw})
        with self.assertRaisesRegex(ValueError, 'canonical|policy|descriptor'):
            producer.inspect_output(output)

    def test_cli_requires_explicit_selector_and_verify_rejects_production_selection(self):
        for arguments in (['--output', str(self.base / 'absent')],
                          ['--verify', '--output', str(self.base / 'absent'), '--document-profile', 'pixel']):
            with self.subTest(arguments=arguments), patch('sys.stderr', new_callable=io.StringIO), \
                    patch.object(producer, 'package', side_effect=AssertionError('no default production')), \
                    patch.object(producer, 'verify', side_effect=AssertionError('no flags on retained verify')):
                self.assertEqual(producer.main(arguments), 1)
        prefix, envelope, facts = self.assemble()
        output, _ = self.write_output(prefix, envelope, facts)
        with patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(producer.main(['--verify', '--output', str(output)]), 1)

    def test_strip_and_reappend_preserve_exact_document_prefix_for_web_and_both(self):
        for profile in ('web', 'both'):
            with self.subTest(profile=profile):
                prefix, envelope, facts = self.assemble(profile=profile)
                descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
                files = {'web/index.html': b'<!doctype html><title>one</title>'}
                options = {'web_entry': 'web/index.html'}
                if profile == 'both':
                    files['binary/application.wasm'] = guest_wasm()
                    options.update(binary_entry='binary/application.wasm', binary_profile='foundation-guest-v1')
                app = {'id': 'org.example.document', 'name': 'Document parser fixture', 'version': '1.0.0'}
                first = container.build_package(files, app, **options)
                composed = container.compose_bytes(prefix, descriptor, first, expected_mode=profile)
                files['web/index.html'] = b'<!doctype html><title>two</title>'
                second = container.build_package(files, app, **options)
                replaced = container.compose_bytes(composed, descriptor, second, expected_mode=profile)
                self.assertTrue(replaced.startswith(prefix))
                self.assertNotEqual(composed, replaced)
                self.assertEqual(container.compose_bytes(replaced, descriptor), prefix)
                self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)


EDITOR_GETTER = 'gui_web_engine_editor_describe_v1'
EDITOR_FOUNDATION_CHECKS = ('editor_profile_query', 'editor_query4_owned_projection',
    'editor_command8_native_readback', 'editor_command9_native_revocation',
    'editor_full_worker_target_key', 'editor_pending_form_service_barriers',
    'editor_composition_focus_retirement', 'editor_unknown_terminal_no_replay',
    'engine_editor_bootstrap')
EDITOR_ORDER = ('kernel_editor_facts_before_engine_factory',
    'engine_describe_before_kernel_configure', 'kernel_configure_before_start')


def editor_host_blobs():
    """Closed declaration-only editor graph; no browser script is evaluated."""
    import browser_editor_bundle as editor
    blobs = host_blobs(physical=True)
    for filename, dependencies in editor.CHILD_GRAPH.items():
        if filename in blobs:
            continue
        imports = ''.join("import {" + editor.CHILD_EXPORTS[dep][0] + ' as dep' + str(index)
                          + "} from './" + dep + "';\n" for index, dep in enumerate(dependencies))
        declarations = ''.join('export const ' + name + '=' + str(index) + ';\n'
                               for index, name in enumerate(editor.CHILD_EXPORTS[filename]))
        blobs[filename] = (imports + declarations).encode()
    blobs[editor.BUNDLE_NAME] = editor.module_bytes(editor.build({name: blobs[name] for name in editor.SOURCE_NAMES}))
    # Declaration-only parent leaf; the validators are never invoked here.
    blobs['browser_document_endpoint.mjs'] = (
        b'export const validateDocumentState=0;\n'
        b'export const validateDocumentOperation=1;\n'
        b'export const validateDocumentReply=2;\n'
        b'export const createBrowserDocumentEndpoint=3;\n')
    return blobs


class EditorBrowserProducerTests(unittest.TestCase):
    """Separate editor receipts remain inert and can never publish a carrier."""

    assemble = DocumentBrowserProducerTests.assemble
    receipt_check = DocumentBrowserProducerTests.receipt_check
    write_output = DocumentBrowserProducerTests.write_output
    checksums = staticmethod(DocumentBrowserProducerTests.checksums)
    publish_arguments = DocumentBrowserProducerTests.publish_arguments
    composition_fixture = DocumentBrowserProducerTests.composition_fixture
    composition_profiles = DocumentBrowserProducerTests.composition_profiles
    test_composition_typed_receipts_preserve_document_selection_and_parser_scope = (
        DocumentBrowserProducerTests.test_composition_typed_receipts_preserve_document_selection_and_parser_scope)
    test_composition_receipt_requires_actual_typed_getter = (
        DocumentBrowserProducerTests.test_composition_receipt_requires_actual_typed_getter)
    test_composition_scalar_order_and_signature_are_exact = (
        DocumentBrowserProducerTests.test_composition_scalar_order_and_signature_are_exact)
    test_composition_check_and_old_profile_checks_remain_required = (
        DocumentBrowserProducerTests.test_composition_check_and_old_profile_checks_remain_required)
    test_composition_artifact_source_lookup_and_independent_pin_are_bound = (
        DocumentBrowserProducerTests.test_composition_artifact_source_lookup_and_independent_pin_are_bound)
    test_composition_receipt_family_cannot_cross_or_attach_to_legacy_kind = (
        DocumentBrowserProducerTests.test_composition_receipt_family_cannot_cross_or_attach_to_legacy_kind)
    test_composition_descriptor_dispatch_uses_the_admitted_document_receipt_family = (
        DocumentBrowserProducerTests.test_composition_descriptor_dispatch_uses_the_admitted_document_receipt_family)
    test_legacy_receipt_with_typed_composition_export_keeps_old_policy = (
        DocumentBrowserProducerTests.test_legacy_receipt_with_typed_composition_export_keeps_old_policy)
    test_old_descriptor_refuses_valid_new_compiled_startup = (
        DocumentBrowserProducerTests.test_old_descriptor_refuses_valid_new_compiled_startup)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-editor-carrier-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        (self.source / 'main.cpp').write_text('// inert editor source projection fixture\n')
        self.inputs, self.full = kernel_source_tree(self.source), source_tree(self.source)
        self.selected = 'editor'
        self.fixture = EditorEngineFixture(self.base / 'engine')
        self.group = self.base / 'group'
        self.fixture.export_group(self.group)
        self.engine = editor_consumer.inspect_kernel_consumer(self.group, **self.fixture.group_arguments())
        self.blobs = editor_host_blobs()
        self.factory = b'export default async function createFoundation(options={}) { return options; }\n'
        self.wasm = foundation_wasm(getter=EDITOR_GETTER)
        self.notices = {'foundation': b'Foundation editor parser fixture notice; no runtime distribution.\n'}
        self.receipt = self.kernel_receipt()

    def kernel_receipt(self, profile='web', *, wasm=None, factory=None):
        value = DocumentBrowserProducerTests.kernel_receipt(self, profile, wasm=wasm, factory=factory)
        value['kind'] = 'foundation-rich-browser-editor-kernel-proof-v1'
        observed = value.pop('compiled_document_profile')
        observed['export'] = EDITOR_GETTER
        value['compiled_editor_profile'] = observed
        value['engine_bootstrap'] = {'engine': editor_bootstrap(self.engine.as_dict()['engine_profile']),
            'order': {name: 'passed' for name in EDITOR_ORDER}}
        combined = value['engine_bootstrap']['engine']
        combined.update(worker_epoch='4294967297', first_start_worker_epoch='4294967297')
        combined['engine_configure'].update(worker_lo=1, worker_hi=1)
        value['checks'] = {name: 'passed' for name in
            BASE_CHECKS + DOCUMENT_CHECKS + PHYSICAL_CHECKS + EDITOR_FOUNDATION_CHECKS}
        return value

    def test_editor_prefix_has_distinct_kinds_38_facts_ten_interfaces_and_owned_bytes(self):
        prefix, envelope, facts = self.assemble()
        self.assertEqual(envelope['kind'], 'foundation-rich-browser-editor-kernel-v1')
        self.assertEqual(envelope['document_profile'], 'editor')
        self.assertEqual(envelope['kernel']['kind'], 'foundation-copied-engine-editor-browser')
        self.assertEqual(envelope['kernel']['engine_profile'], self.fixture.profile)
        self.assertEqual(len(envelope['kernel']['engine_profile']), 38)
        self.assertEqual(envelope['kernel']['engine_profile']['capabilities'], '2035')
        self.assertEqual(len(envelope['evidence']['engine']['interfaces']), 10)
        self.assertEqual(facts['kernel_receipt']['kind'], 'foundation-rich-browser-editor-kernel-proof-v1')
        self.assertNotIn('compiled_document_profile', facts['kernel_receipt'])
        self.assertEqual(facts['kernel_receipt']['compiled_editor_profile']['export'], EDITOR_GETTER)
        self.assertEqual(set(facts['kernel_receipt']['checks']),
                         set(BASE_CHECKS + DOCUMENT_CHECKS + PHYSICAL_CHECKS + EDITOR_FOUNDATION_CHECKS))
        self.assertEqual(len(facts['kernel_receipt']['checks']), 23)
        for name, raw in self.fixture.evidence().items():
            retained = envelope['evidence']['engine'][name]
            if isinstance(raw, dict):
                self.assertEqual({path: base64.b64decode(value) for path, value in retained.items()}, raw)
            else:
                self.assertEqual(base64.b64decode(retained), raw)
        self.assertFalse(facts['production_eligible'])
        self.assertEqual(facts['engine']['runtime_evidence']['scope'], 'parser-fixture-only')
        self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)

    def test_editor_both_marker_policy_and_surface_bootstrap_are_explicit(self):
        prefix, envelope, facts = self.assemble(profile='both')
        self.assertEqual(facts['kernel_receipt']['compiled_profile']['observed_result'], 2)
        self.assertEqual(envelope['kernel']['kernel_profile'], 'both')
        editor_source = producer.bootstrap_source(document_profile='editor')
        self.assertNotEqual(editor_source, producer.bootstrap_source(document_profile='physical'))
        self.assertIn("moduleURL('renderer_editor_child_bundle.mjs')", editor_source)
        self.assertIn('editorRendererBundle', editor_source)
        self.assertNotIn('physicalRendererBundle', editor_source)
        self.assertIn('editor', facts['child'])
        descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
        self.assertEqual(descriptor['provenance']['kind'], 'foundation-rich-browser-editor-kernel-v1')
        self.assertEqual(descriptor['capabilities'], ['foundation.providers.v1', 'foundation.startup.v1'])
        self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)

    def test_editor_selection_envelope_kernel_and_proof_kinds_cannot_cross_profiles(self):
        for selected in ('pixel', 'physical', 'EDITOR', '2035', True):
            with self.subTest(selected=selected), self.assertRaises((ValueError, TypeError)):
                self.assemble(document_profile=selected)
        with self.assertRaises(ValueError):
            producer.bootstrap_source(document_profile=None)
        prefix, envelope, _ = self.assemble()
        for key, changed in (('kind', 'foundation-rich-browser-document-kernel-v1'),
                             ('document_profile', 'physical')):
            value = copy.deepcopy(envelope); value[key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                producer.inspect_prefix(replace_envelope(prefix, value))
        value = copy.deepcopy(envelope); value['kernel']['kind'] = 'foundation-copied-engine-document-browser'
        with self.assertRaises(ValueError):
            producer.inspect_prefix(replace_envelope(prefix, value))
        for kind in ('foundation-rich-browser-document-kernel-proof-v1', 'foundation-rich-browser-physical-kernel-proof-v1',
                     'foundation-rich-browser-kernel-proof-v1'):
            value = copy.deepcopy(self.receipt); value['kind'] = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.receipt_check(value)

    def test_editor_receipt_requires_its_distinct_getter_field_and_order_name(self):
        for mutation in (lambda value: value.update(compiled_document_profile=value.pop('compiled_editor_profile')),
                         lambda value: value.update(compiled_document_profile=copy.deepcopy(value['compiled_editor_profile'])),
                         lambda value: value['engine_bootstrap']['order'].update(
                             kernel_document_facts_before_engine_factory=value['engine_bootstrap']['order'].pop('kernel_editor_facts_before_engine_factory')),
                         lambda value: value['compiled_editor_profile'].update(export='gui_web_engine_document_describe_v1')):
            value = copy.deepcopy(self.receipt); mutation(value)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.receipt_check(value)

    def test_actual_typed_editor_getter_is_required_despite_rehashed_receipt_facts(self):
        for wasm in (foundation_wasm(), foundation_wasm(getter=EDITOR_GETTER, describe_type=0),
                     foundation_wasm(getter=EDITOR_GETTER, missing=(EDITOR_GETTER,)),
                     foundation_wasm(getter=EDITOR_GETTER, dispatch_type=0)):
            with self.subTest(wasm=container.digest(wasm)), self.assertRaises(ValueError):
                self.receipt_check(self.kernel_receipt(wasm=wasm), wasm=wasm)

    def test_editor_getter_requires_strict_original_38_fact_bytes_and_measured_count(self):
        profile = self.engine.as_dict()['engine_profile']
        raw = json.dumps(profile, indent=1).encode('utf-8')
        value = copy.deepcopy(self.receipt)
        value['compiled_editor_profile'].update(observed_output=b64(raw), observed_bytes=len(raw))
        retained, eligible = self.receipt_check(value)
        self.assertEqual(retained['compiled_editor_profile']['observed_output'], b64(raw))
        self.assertFalse(eligible)
        for raw in (b'\xef\xbb\xbf' + encoded(profile), encoded(profile) + b'\0', b'\xff',
                    b'{"schema_version":1,"schema_version":1}', b'x' * 4096):
            value = copy.deepcopy(self.receipt)
            value['compiled_editor_profile'].update(observed_output=b64(raw), observed_bytes=len(raw))
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                self.receipt_check(value)
        for change in ({'observed_bytes': True}, {'observed_bytes': 1}, {'observed_result': len(raw)},
                       {'observed_output': '!!!!'}, {'before_engine_factory': False}, {'before_configure': False}):
            value = copy.deepcopy(self.receipt); value['compiled_editor_profile'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.receipt_check(value)

    def test_editor_combined_bootstrap_keeps_full_worker_identity_and_new_exports(self):
        self.assertEqual(self.receipt['engine_bootstrap']['engine']['worker_epoch'], '4294967297')
        self.assertNotEqual(self.receipt['engine_bootstrap']['engine']['worker_epoch'],
                            self.fixture.runtime['bootstrap']['worker_epoch'])
        for mutation in (lambda value: value['engine_configure'].update(worker_hi=0),
                         lambda value: value.update(first_start_worker_epoch='1'),
                         lambda value: value['engine_configure'].update(export='bib_engine_wasm_document_configure_v1'),
                         lambda value: value['engine_facts'].update(export='bib_engine_wasm_document_facts_v1')):
            value = copy.deepcopy(self.receipt); mutation(value['engine_bootstrap']['engine'])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.receipt_check(value)
        for name in EDITOR_ORDER:
            value = copy.deepcopy(self.receipt); value['engine_bootstrap']['order'][name] = 'not-run'
            retained, eligible = self.receipt_check(value)
            self.assertFalse(eligible); self.assertEqual(retained['engine_bootstrap']['order'][name], 'not-run')

    def test_all_23_editor_foundation_checks_are_closed_and_incomplete_checks_stay_ineligible(self):
        for name in BASE_CHECKS + DOCUMENT_CHECKS + PHYSICAL_CHECKS + EDITOR_FOUNDATION_CHECKS:
            value = copy.deepcopy(self.receipt); value['checks'].pop(name)
            with self.subTest(missing=name), self.assertRaises(ValueError):
                self.receipt_check(value)
            for status in ('unfinished', 'failed'):
                value = copy.deepcopy(self.receipt); value['checks'][name] = status
                retained, eligible = self.receipt_check(value)
                with self.subTest(name=name, status=status):
                    self.assertFalse(eligible); self.assertEqual(retained['checks'][name], status)
        value = copy.deepcopy(self.receipt); value['checks']['extra'] = 'passed'
        with self.assertRaises(ValueError):
            self.receipt_check(value)

    def test_editor_ten_interface_closure_rejects_every_missing_or_changed_member(self):
        prefix, envelope, _ = self.assemble()
        for path in self.fixture.interfaces:
            for missing in (False, True):
                value = copy.deepcopy(envelope)
                if missing:
                    value['evidence']['engine']['interfaces'].pop(path)
                else:
                    value['evidence']['engine']['interfaces'][path] = b64(self.fixture.interfaces[path] + b'\n')
                with self.subTest(path=path, missing=missing), self.assertRaises(ValueError):
                    producer.inspect_prefix(replace_envelope(prefix, value))

    def test_editor_interface_budget_is_symmetric_and_keeps_old_budget_unchanged(self):
        prefix, envelope, _ = self.assemble()
        total = sum(map(len, self.fixture.interfaces.values()))
        original = producer.MAX_INTERFACES_BYTES
        with patch.object(producer, 'EDITOR_MAX_INTERFACES_BYTES', total - 1), self.assertRaisesRegex(ValueError, 'budget|bounds'):
            self.assemble()
        with patch.object(producer, 'EDITOR_MAX_INTERFACES_BYTES', 0), self.assertRaisesRegex(ValueError, 'aggregate budget'):
            producer.inspect_prefix(prefix)
        self.assertEqual(producer.MAX_INTERFACES_BYTES, original)
        self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)

    def test_editor_same_directory_host_graph_and_target_sdk_joins_remain_mandatory(self):
        blobs = dict(self.blobs); blobs.pop(next(iter(blobs)))
        with self.assertRaises(ValueError):
            self.assemble(blobs=blobs)
        value = copy.deepcopy(self.receipt); value['host_assets'][next(iter(value['host_assets']))] = 'f' * 64
        with self.assertRaises(ValueError):
            self.receipt_check(value)
        for key, changed in (('sdk_sha256', 'f' * 64), ('target', {**TARGET, 'processor': 'x86_64'})):
            value = copy.deepcopy(self.receipt); value['toolchain'][key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.assemble(receipt=value)

    def test_editor_selected_renderer_reconstructs_exact_source_graph_without_changing_old_inventory(self):
        import browser_editor_bundle as editor
        self.assertEqual(set(self.blobs), set(producer.asset_names(document_profile='editor')))
        original = set(producer.asset_names())
        self.assertEqual(set(producer.asset_names(document_profile='physical')), original)
        self.assertTrue(original < set(self.blobs))
        self.assertNotIn(editor.BUNDLE_NAME, original)
        for name in (editor.BUNDLE_NAME, 'browser_editor_endpoint.mjs', 'renderer_editor_frame.mjs'):
            blobs = dict(self.blobs); blobs[name] += b'\n'
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.assemble(blobs=blobs)

    def test_editor_prefix_readback_selects_only_editor_consumer_with_explicit_keyword(self):
        prefix, envelope, _ = self.assemble()
        with patch.object(editor_consumer, 'inspect_embedded_consumer', wraps=editor_consumer.inspect_embedded_consumer) as inspect, \
                patch.object(consumer, 'inspect_embedded_consumer', side_effect=AssertionError('no document fallback')):
            self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)
        inspect.assert_called_once()
        self.assertEqual(inspect.call_args.kwargs['editor_profile'], 'editor')
        self.assertNotIn('document_profile', inspect.call_args.kwargs)

    def test_editor_external_data_is_rejected_without_loader_fallback(self):
        fixture = EditorEngineFixture(self.base / 'data-engine', data=True)
        group = self.base / 'data-group'; fixture.export_group(group)
        engine = editor_consumer.inspect_kernel_consumer(group, **fixture.group_arguments())
        original = self.engine
        self.engine = engine
        try:
            with patch.object(subprocess, 'Popen', side_effect=AssertionError('no fallback')), self.assertRaisesRegex(ValueError, 'External engine data'):
                self.assemble(engine=engine)
        finally:
            self.engine = original

    def test_editor_consumer_dispatch_precedes_final_receipt_and_never_calls_document_verifier(self):
        assets, notices, options = self.publish_arguments()
        with patch.object(editor_consumer, 'verify_kernel_consumer', side_effect=ValueError('editor engine refused')) as verify, \
                patch.object(consumer, 'verify_kernel_consumer', side_effect=AssertionError('no document fallback')), \
                patch.object(producer, 'inspect_kernel_receipt', side_effect=AssertionError('no final receipt yet')):
            with self.assertRaisesRegex(ValueError, 'editor engine refused'):
                producer.package(assets, self.base / 'absent', notices, **options)
        verify.assert_called_once()
        self.assertEqual(verify.call_args.kwargs['editor_profile'], 'editor')
        self.assertNotIn('document_profile', verify.call_args.kwargs)
        self.assertFalse((self.base / 'absent').exists())

    def test_editor_five_independent_pins_prevent_output_and_all_fallbacks(self):
        assets, notices, options = self.publish_arguments()
        for field in ('engine_recipe_sha256', 'engine_manifest_sha256', 'engine_proof_sha256',
                      'engine_runtime_sha256', 'kernel_receipt_sha256'):
            with self.subTest(field=field), patch.object(subprocess, 'Popen', side_effect=AssertionError('no fallback')), \
                    patch.object(consumer, 'verify_kernel_consumer', side_effect=AssertionError('no document fallback')), \
                    patch.object(editor_consumer, 'verify_kernel_consumer', wraps=editor_consumer.verify_kernel_consumer) as verify:
                with self.assertRaises(ValueError):
                    producer.package(assets, self.base / 'absent', notices, **{**options, field: 'f' * 64})
                self.assertFalse((self.base / 'absent').exists())
                if field == 'kernel_receipt_sha256':
                    verify.assert_not_called()
                else:
                    verify.assert_called_once()
                    expected = 'expected_' + field.removeprefix('engine_').removesuffix('_sha256')
                    self.assertEqual(verify.call_args.kwargs[expected], 'f' * 64)

    def test_editor_fixture_publication_and_existing_output_are_refused_without_execution(self):
        assets, notices, options = self.publish_arguments()
        for developer in (False, True):
            output = self.base / ('absent-' + str(developer))
            with self.subTest(developer=developer), patch.object(subprocess, 'run', side_effect=AssertionError('no execution')), \
                    patch.object(subprocess, 'Popen', side_effect=AssertionError('no execution')), self.assertRaisesRegex(ValueError, 'developer-unqualified|ineligible|runtime'):
                producer.package(assets, output, notices, **{**options, 'developer_unqualified': developer})
            self.assertFalse(output.exists())
        output = self.base / 'existing'; output.mkdir(); (output / 'foreign').write_bytes(b'preserve')
        with patch.object(editor_consumer, 'verify_kernel_consumer', side_effect=AssertionError('no consumption')), self.assertRaisesRegex(ValueError, 'destination must be new'):
            producer.package(assets, output, notices, **options)
        self.assertEqual((output / 'foreign').read_bytes(), b'preserve')

    def test_editor_output_integrity_retains_fixture_scope_and_verify_refuses(self):
        prefix, envelope, facts = self.assemble()
        output, descriptor = self.write_output(prefix, envelope, facts)
        pin = container.digest(container.canonical_json(descriptor))
        checked, observed = producer.inspect_output(output, pin)
        self.assertEqual(checked, descriptor)
        self.assertEqual(checked['provenance']['kind'], 'foundation-rich-browser-editor-kernel-v1')
        self.assertTrue(observed['independently_pinned_descriptor'])
        self.assertFalse(observed['production_eligible'])
        self.assertEqual(observed['engine']['runtime_evidence']['scope'], 'parser-fixture-only')
        with self.assertRaisesRegex(ValueError, 'runtime'):
            producer.verify(output, pin)
        (output / 'manifest.sha256').write_bytes(b'invalid\n')
        with self.assertRaisesRegex(ValueError, 'checksum inventory'):
            producer.inspect_output(output, pin)

    def test_editor_inspection_does_not_follow_later_caller_or_descriptor_mutation(self):
        prefix, envelope, facts = self.assemble()
        envelope['kind'] = 'invented'
        self.fixture.interfaces[next(iter(self.fixture.interfaces))] = b'changed after assembly'
        retained, checked = producer.inspect_prefix(prefix)
        self.assertEqual(retained['kind'], 'foundation-rich-browser-editor-kernel-v1')
        self.assertFalse(checked['production_eligible'])
        descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
        self.assertEqual(descriptor['provenance']['kind'], 'foundation-rich-browser-editor-kernel-v1')

    def test_editor_cli_selection_is_explicit_and_verify_cannot_accept_production_flags(self):
        with patch.object(producer, 'package', side_effect=ValueError('explicit editor selected')) as package, \
                patch('sys.stderr', new_callable=io.StringIO):
            arguments = ['--output', str(self.base / 'absent'), '--document-profile', 'editor',
                '--assets', str(self.base), '--source-root', str(self.source), '--profile', 'web',
                '--engine-group', str(self.group), '--kernel-receipt', str(self.base / 'receipt')]
            for name in ('engine-recipe', 'engine-manifest', 'engine-proof', 'engine-runtime', 'kernel-receipt'):
                arguments += ['--' + name + '-sha256', 'a' * 64]
            self.assertEqual(producer.main(arguments), 1)
        package.assert_called_once()
        self.assertEqual(package.call_args.kwargs['document_profile'], 'editor')
        with patch.object(producer, 'verify', side_effect=AssertionError('no upgrade')), patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(producer.main(['--verify', '--output', str(self.base), '--document-profile', 'editor']), 1)

    def test_editor_strip_and_reappend_keep_exact_prefix_for_web_and_both(self):
        for profile in ('web', 'both'):
            prefix, envelope, facts = self.assemble(profile=profile)
            descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
            files = {'web/index.html': b'<!doctype html><title>editor one</title>'}
            options = {'web_entry': 'web/index.html'}
            if profile == 'both':
                files['binary/application.wasm'] = guest_wasm()
                options.update(binary_entry='binary/application.wasm', binary_profile='foundation-guest-v1')
            app = {'id': 'org.example.editor', 'name': 'Editor parser fixture', 'version': '1.0.0'}
            first = container.build_package(files, app, **options)
            composed = container.compose_bytes(prefix, descriptor, first, expected_mode=profile)
            files['web/index.html'] = b'<!doctype html><title>editor two</title>'
            second = container.build_package(files, app, **options)
            replaced = container.compose_bytes(composed, descriptor, second, expected_mode=profile)
            with self.subTest(profile=profile):
                self.assertNotEqual(composed, replaced)
                self.assertTrue(replaced.startswith(prefix))
                self.assertEqual(container.compose_bytes(replaced, descriptor), prefix)
                self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)

    def test_editor_and_document_protocol_hooks_are_dynamic_closed_and_conditional(self):
        editor_source = producer.bootstrap_source(document_profile='editor')
        self.assertIn("await import(moduleURL('browser_editor_endpoint.mjs'))", editor_source)
        self.assertIn('const editorProtocol=Object.freeze({validateEditorPublication,validateEditorOperation,validateEditorReply});', editor_source)
        document_import = "const {validateDocumentState,validateDocumentOperation,validateDocumentReply}=await import(moduleURL('browser_document_endpoint.mjs'));"
        document_protocol = 'const documentProtocol=Object.freeze({validateDocumentState,validateDocumentOperation,validateDocumentReply});'
        self.assertEqual(editor_source.count(document_import), 1)
        self.assertEqual(editor_source.count(document_protocol), 1)
        self.assertEqual(editor_source.count('editorRendererBundle,editorProtocol,documentProtocol});'), 1)
        for selected in ('pixel', 'physical'):
            source = producer.bootstrap_source(document_profile=selected)
            with self.subTest(selected=selected):
                self.assertNotIn('browser_editor_endpoint.mjs', source)
                self.assertNotIn('editorProtocol', source)
                self.assertNotIn('browser_document_endpoint.mjs', source)
                self.assertNotIn('documentProtocol', source)
                self.assertNotIn('browser_document_endpoint.mjs', producer.asset_names(document_profile=selected))
                self.assertEqual(producer.asset_names(document_profile=selected), producer.rendering.asset_names())
        expected = {
            'browser_document_endpoint.mjs': (),
            'browser_editor_endpoint.mjs': ('browser_surface_editor_controller.mjs',
                'browser_surface_editor_text.mjs', 'browser_surface_protocol.mjs'),
            'browser_surface_editor_controller.mjs': ('browser_surface.mjs', 'browser_surface_editor_text.mjs'),
            'browser_surface_editor_text.mjs': ('browser_surface.mjs',),
            'browser_surface.mjs': ('browser_surface_protocol.mjs',),
        }
        for name, dependencies in expected.items():
            self.assertEqual(producer.EDITOR_IMPORTS[name], dependencies)
            self.assertIn(name, producer.asset_names(document_profile='editor'))
        self.assertEqual(set(producer.validate_assets(self.blobs, document_profile='editor')),
                         {'ordinary', 'surface', 'editor'})

    def test_editor_document_protocol_asset_has_exact_inventory_and_owned_bytes(self):
        name = 'browser_document_endpoint.mjs'
        prefix, envelope, facts = self.assemble()
        self.assertEqual(base64.b64decode(envelope['modules'][name]), self.blobs[name])
        self.assertEqual(facts['kernel_receipt']['host_assets'][name], container.digest(self.blobs[name]))
        self.assertFalse(facts['production_eligible'])
        self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)
        for mode in ('missing', 'extra'):
            blobs = dict(self.blobs)
            if mode == 'missing':
                del blobs[name]
            else:
                blobs['unselected_document_endpoint.mjs'] = blobs[name]
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'inventory'):
                producer.validate_assets(blobs, document_profile='editor')

    def test_editor_document_protocol_rejects_imports_reexports_and_export_drift(self):
        name = 'browser_document_endpoint.mjs'
        additions = (
            b"import './browser_limits.mjs';",
            b"import {fixture} from './browser_limits.mjs';",
            b"import 'unexpected-bare-module';",
            b"import 'https://example.invalid/document.mjs';",
            b"import('./browser_limits.mjs');",
            b"const hidden=`value ${import('./browser_limits.mjs')}`;",
            b"const value=/\\/\\//;import('./browser_limits.mjs');",
            b"let x=1;x++ / import('unexpected') / 2;",
            b"let x=1;x-- / import /* comment */ ('unexpected') / 2;",
            b"export {fixture} from './browser_limits.mjs';",
            b'export const unexpectedDocumentExport=4;',
        )
        for addition in additions:
            blobs = dict(self.blobs); blobs[name] += addition
            with self.subTest(addition=addition), self.assertRaises(ValueError):
                producer.validate_assets(blobs, document_profile='editor')
        for exported in ('validateDocumentState', 'validateDocumentOperation',
                         'validateDocumentReply', 'createBrowserDocumentEndpoint'):
            blobs = dict(self.blobs); blobs[name] = blobs[name].replace(exported.encode(), b'unselectedExport')
            with self.subTest(exported=exported), self.assertRaises(ValueError):
                producer.validate_assets(blobs, document_profile='editor')

    def test_actual_document_protocol_leaf_fits_closed_exports_without_execution(self):
        import browser_editor_bundle as editor
        blobs = dict(self.blobs)
        blobs['browser_document_endpoint.mjs'] = (ROOT / 'gui/host/browser_document_endpoint.mjs').read_bytes()
        self.assertIn('browser_document_endpoint.mjs', editor.SOURCE_NAMES)
        blobs[editor.BUNDLE_NAME] = editor.module_bytes(editor.build({name: blobs[name] for name in editor.SOURCE_NAMES}))
        self.assertEqual(set(producer.validate_assets(blobs, document_profile='editor')),
                         {'ordinary', 'surface', 'editor'})


if __name__ == '__main__':
    unittest.main()
