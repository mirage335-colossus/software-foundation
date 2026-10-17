"""Pure rich carrier fixtures, never a compiled Foundation/WebCore qualification.

All retained runtime reports explicitly say parser-fixture-only. These tests
exercise deterministic bytes, typed contract checks and fail-closed publication.
"""
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_container as container
import appended_engine_consumer as consumer
import browser_bundle
import browser_surface_bundle as surface
import package_appended_engine_wasm as producer
import package_appended_wasm as binary_producer
from dependency_archive import encoded
from appended_policy import kernel_source_tree
from source_identity import source_tree
from test_appended_engine_consumer import create_fixture, name, section, vector, uleb, MAGIC
from test_appended_wasm import module as guest_module


def host_blobs(*, physical_input=False):
    """Small declaration-only graphs; none of this fixture JavaScript runs."""
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
    if physical_input:
        # Distinct inert parser bytes, not an executable mouse implementation or
        # original runtime observation. Receipts bind this complete inventory.
        blobs['renderer_surface_frame.mjs'] += b'// physical mouse_v1 parser fixture; never executed\n'
    blobs[browser_bundle.BUNDLE_NAME] = browser_bundle.module_bytes(browser_bundle.assemble(
        {key: blobs[key] for key in browser_bundle.CHILD_MODULES + ('style.css',)}))
    blobs[surface.BUNDLE_NAME] = surface.module_bytes(surface.build(
        {key: blobs[key] for key in surface.CHILD_MODULES + ('style.css',)}))
    for filename, dependencies in producer.IMPORTS.items():
        if filename in blobs:
            continue
        blobs[filename] = (''.join("import {fixture as dep" + str(index) + "} from './" + dep + "';\n"
                                  for index, dep in enumerate(dependencies)) + 'export const fixture=0;\n').encode()
    return blobs


def foundation_wasm(*, missing=(), dispatch_type=1, memory=b'\x01\x01\x04', start=None,
                    input_describe=False, input_describe_type=5,
                    composition=False, composition_type=0):
    """Typed, inert sections for the separate Foundation export surface."""
    types = [b'\x60\x00\x01\x7f', b'\x60\x05' + b'\x7f' * 5 + b'\x01\x7f',
             b'\x60\x01\x7f\x01\x7f', b'\x60\x01\x7f\x00', b'\x60\x00\x00']
    signatures = [0, 0, dispatch_type, 2, 2, 4, 2, 3]
    names = ['gui_web_engine_bridge_v1', 'gui_web_engine_profile_v1', 'gui_web_engine_dispatch_v1',
             'gui_web_create', 'gui_web_receive', 'gui_web_destroy', 'malloc', 'free']
    if input_describe:
        types.append(b'\x60\x02\x7f\x7f\x01\x7f')
        signatures.append(input_describe_type)
        names.append('gui_web_engine_input_describe_v1')
    if composition:
        signatures.append(composition_type)
        names.append('gui_web_application_composition_v1')
    wasm = MAGIC + section(1, vector(types)) + section(3, vector([uleb(item) for item in signatures]))
    wasm += section(5, vector([memory]))
    exports = [name(item) + b'\x00' + uleb(index) for index, item in enumerate(names) if item not in missing]
    exports.append(name('memory') + b'\x02\x00')
    wasm += section(7, vector(exports))
    if start is not None:
        wasm += section(8, uleb(start))
    bodies = [b'\x00\x0b' if item in (3, 4) else b'\x00\x41\x00\x0b' for item in signatures]
    return wasm + section(10, vector([uleb(len(body)) + body for body in bodies]))


class RichBrowserProducerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-rich-producer-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / 'source'; self.source.mkdir()
        (self.source / 'main.cpp').write_text('// inert source projection fixture\n')
        self.inputs = kernel_source_tree(self.source)
        self.full = source_tree(self.source)
        self.engine = create_fixture(self.base / 'engine')
        self.blobs = host_blobs()
        self.factory = b'export default async function createFoundation(options={}) { return options; }\n'
        self.wasm = foundation_wasm()
        self.notices = {'foundation': b'Foundation fixture notice; no runtime distribution.\n'}
        self.receipt = self.kernel_receipt()

    def kernel_receipt(self, profile='web', wasm=None, factory=None, *, physical_input=False):
        wasm = self.wasm if wasm is None else wasm
        factory = self.factory if factory is None else factory
        result = {'schema_version': 1, 'kind': 'foundation-rich-browser-kernel-proof-v1',
                'scope': 'parser-fixture-only', 'status': 'passed', 'profile': profile,
                'source': {'tree_sha256': self.full['tree_sha256'], 'kernel_inputs_sha256': self.inputs['tree_sha256']},
                'toolchain': {'sdk_sha256': self.engine['sdk'], 'target': self.engine['target']},
                'artifacts': {'factory': {'sha256': container.digest(factory), 'bytes': len(factory)},
                              'wasm': {'sha256': container.digest(wasm), 'bytes': len(wasm), 'lookup_name': producer.WASM_NAME}},
                'wasm_facts': consumer.scan_wasm(wasm),
                'compiled_profile': {'export': 'gui_web_engine_profile_v1',
                    'signature': {'params': [], 'results': ['i32']}, 'observed_result': 1 if profile == 'web' else 2,
                    'before_configure': True},
                'engine_profile': self.engine['inspection'].as_dict()['engine_profile'],
                'checks': {'inert_factory': 'passed', 'compiled_profile_query': 'passed', 'engine_describe_match': 'passed'},
                'build_origin': 'synthetic parser fixture; no compilation/runtime execution'}
        if physical_input:
            result['kind'] = producer.PHYSICAL_RECEIPT_KIND
            output = container.canonical_json(result['engine_profile'])
            result['compiled_input_profile'] = {
                'export': 'gui_web_engine_input_describe_v1',
                'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
                'observed_result': copy.deepcopy(result['engine_profile']),
                'observed_output': producer._encoded(output), 'observed_bytes': len(output),
                'before_engine_factory': True, 'before_configure': True}
            result['host_assets'] = producer._asset_hashes(self.blobs)
            result['checks'].update({key: 'passed' for key in
                ('input_profile_query', 'host_assets_match') + consumer.PHYSICAL_INPUT_CHECKS})
        return result

    def assemble(self, *, profile='web', receipt=None, blobs=None, wasm=None, factory=None, notices=None, engine=None,
                 physical_input=False):
        receipt = self.kernel_receipt(profile, physical_input=physical_input) if receipt is None else receipt
        raw = encoded(receipt)
        return producer.make_prefix(self.blobs if blobs is None else blobs,
            self.factory if factory is None else factory, self.wasm if wasm is None else wasm,
            self.engine['inspection'] if engine is None else engine, raw, container.digest(raw),
            self.notices if notices is None else notices, self.full['tree_sha256'], self.inputs['tree_sha256'], profile,
            physical_input=physical_input)

    def receipt_check(self, value, *, wasm=None, factory=None, profile='web', pin=None, physical_input=False):
        raw = encoded(value)
        return producer.inspect_kernel_receipt(raw, container.digest(raw) if pin is None else pin,
            self.factory if factory is None else factory, self.wasm if wasm is None else wasm,
            profile, self.engine['inspection'].as_dict()['engine_profile'], expected_kernel_inputs=self.inputs['tree_sha256'],
            physical_input=physical_input, host_assets=producer._asset_hashes(self.blobs) if physical_input else None)

    def composition_fixture(self, profile='web', *, physical_input=False, **wasm_options):
        """Typed parser bytes and a synthetic observation, never an executed getter."""
        wasm = foundation_wasm(composition=True, input_describe=physical_input, **wasm_options)
        value = self.kernel_receipt(profile, wasm=wasm, physical_input=physical_input)
        value['kind'] = producer.COMPOSITION_RECEIPT_KINDS[value['kind']]
        value['compiled_composition'] = {
            'export': 'gui_web_application_composition_v1',
            'signature': {'params': [], 'results': ['i32']},
            'observed_result': 5 if profile == 'web' else 7,
            'before_engine_factory': True, 'before_configure': True}
        value['checks']['application_composition_query'] = 'passed'
        return wasm, value

    def test_composition_typed_web5_and_both7_receipts_remain_parser_ineligible(self):
        for profile in ('web', 'both'):
            with self.subTest(profile=profile):
                wasm, value = self.composition_fixture(profile)
                checked, eligible = self.receipt_check(value, wasm=wasm, profile=profile)
                self.assertFalse(eligible)
                self.assertEqual(checked['kind'], producer.COMPOSITION_RECEIPT_KIND)
                self.assertEqual(checked['compiled_composition']['observed_result'], 5 if profile == 'web' else 7)
                self.assertEqual(producer.composition_descriptor_policy(profile, checked, eligible=eligible),
                                 producer.POLICIES[profile])

    def test_composition_receipt_requires_actual_typed_getter(self):
        for options in ({'missing': ('gui_web_application_composition_v1',)}, {'composition_type': 2}):
            with self.subTest(options=options):
                wasm, value = self.composition_fixture(**options)
                with self.assertRaisesRegex(ValueError, 'required typed export'):
                    self.receipt_check(value, wasm=wasm)

    def test_composition_scalar_is_strict_and_profile_specific(self):
        for profile in ('web', 'both'):
            for result in (True, False, None, 1, 2, 7 if profile == 'web' else 5, 5.0 if profile == 'web' else 7.0):
                with self.subTest(profile=profile, result=result):
                    wasm, value = self.composition_fixture(profile)
                    value['compiled_composition']['observed_result'] = result
                    with self.assertRaises(ValueError):
                        self.receipt_check(value, wasm=wasm, profile=profile)

    def test_composition_query_order_and_signature_are_bound(self):
        changes = ({'before_engine_factory': False}, {'before_configure': False},
                   {'export': 'metadata_only'}, {'signature': {'params': ['i32'], 'results': ['i32']}})
        for change in changes:
            with self.subTest(change=change):
                wasm, value = self.composition_fixture()
                value['compiled_composition'].update(change)
                with self.assertRaises(ValueError):
                    self.receipt_check(value, wasm=wasm)

    def test_composition_new_check_is_required_and_incomplete_cannot_upgrade_policy(self):
        wasm, value = self.composition_fixture()
        value['checks'].pop('application_composition_query')
        with self.assertRaises(ValueError):
            self.receipt_check(value, wasm=wasm)
        # In-memory predicate counterfactual only: no eligible engine, retained
        # runtime receipt or carrier is manufactured from these parser fixtures.
        wasm, baseline = self.composition_fixture()
        baseline['scope'] = 'foundation-rich-kernel-runtime'
        checked, eligible = self.receipt_check(baseline, wasm=wasm)
        self.assertTrue(eligible)
        self.assertTrue(all(status == 'passed' for status in checked['checks'].values()))
        self.assertIn('foundation.gui-composition.v1',
            producer.composition_descriptor_policy('web', checked, eligible=eligible)['capabilities'])
        for status in ('failed', 'unfinished'):
            value = copy.deepcopy(baseline)
            value['checks']['application_composition_query'] = status
            checked, eligible = self.receipt_check(value, wasm=wasm)
            self.assertFalse(eligible)
            checked['scope'] = 'foundation-rich-kernel-runtime'
            self.assertEqual(producer.composition_descriptor_policy('web', checked, eligible=True), producer.POLICIES['web'])
        self.assertEqual(self.receipt['scope'], 'parser-fixture-only')

    def test_composition_receipt_keeps_artifact_source_and_independent_pin_guards(self):
        for field in ('factory', 'wasm', 'source', 'pin'):
            with self.subTest(field=field):
                wasm, value = self.composition_fixture()
                options = {'wasm': wasm}
                if field in ('factory', 'wasm'):
                    value['artifacts'][field]['sha256'] = 'd' * 64
                elif field == 'source':
                    value['source']['kernel_inputs_sha256'] = 'd' * 64
                else:
                    options['pin'] = 'd' * 64
                with self.assertRaises(ValueError):
                    self.receipt_check(value, **options)

    def test_composition_receipt_kinds_cannot_cross_or_attach_to_legacy_kind(self):
        for kind in ('foundation-rich-browser-kernel-proof-v1',
                     'foundation-rich-browser-editor-composition-kernel-proof-v1'):
            with self.subTest(kind=kind):
                wasm, value = self.composition_fixture()
                value['kind'] = kind
                with self.assertRaises(ValueError):
                    self.receipt_check(value, wasm=wasm)

    def test_legacy_receipt_with_new_typed_export_does_not_gain_composition_policy(self):
        wasm = foundation_wasm(composition=True)
        value = self.kernel_receipt(wasm=wasm)
        checked, eligible = self.receipt_check(value, wasm=wasm)
        self.assertFalse(eligible)
        self.assertEqual(producer.composition_descriptor_policy('web', checked, eligible=True), producer.POLICIES['web'])
        # Pure policy counterfactual, never actual legacy receipt admission:
        # changing only the kind must disable an otherwise eligible extension.
        composition_wasm, composition = self.composition_fixture()
        composition['scope'] = 'foundation-rich-kernel-runtime'
        baseline, eligible = self.receipt_check(composition, wasm=composition_wasm)
        self.assertTrue(eligible)
        self.assertIn('foundation.gui-composition.v1',
            producer.composition_descriptor_policy('web', baseline, eligible=eligible)['capabilities'])
        legacy = copy.deepcopy(baseline)
        legacy['kind'] = checked['kind']
        self.assertEqual(producer.composition_descriptor_policy('web', legacy, eligible=eligible), producer.POLICIES['web'])
        self.assertEqual(value['scope'], 'parser-fixture-only')

    def test_old_descriptor_refuses_valid_new_compiled_startup(self):
        prefix, envelope, facts = self.assemble()
        descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
        startup = container.canonical_json({'kind': 'foundation-appended-startup', 'primary': 'compiled', 'schema_version': 2})
        package = container.build_package({'web/index.html': b'<p>inert</p>', container.COMPOSITION_STARTUP_PATH: startup},
            {'id': 'org.example.composition', 'name': 'Composition fixture', 'version': '1.0.0'},
            web_entry='web/index.html', requires=container._rich_requirements(None, 'compiled'))
        self.assertEqual(container.validate_rich_startup(package)['primary'], 'compiled')
        with self.assertRaisesRegex(ValueError, 'missing required capabilities'):
            container.compose_bytes(prefix, descriptor, package, expected_mode='web')

    def write_output(self, prefix, envelope, facts, name='retained'):
        output = self.base / name; output.mkdir()
        descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
        contents = {producer.HTML_NAME: prefix, producer.DESCRIPTOR_NAME: container.canonical_json(descriptor)}
        for filename, data in contents.items():
            (output / filename).write_bytes(data)
        (output / 'manifest.sha256').write_text(''.join(container.digest(data) + '  ' + filename + '\n'
                                                   for filename, data in sorted(contents.items())))
        return output, descriptor

    def publish_arguments(self, **changes):
        assets = self.base / 'host-assets'; assets.mkdir(exist_ok=True)
        for filename, data in self.blobs.items():
            (assets / filename).write_bytes(data)
        (assets / producer.FACTORY_NAME).write_bytes(self.factory)
        (assets / producer.WASM_NAME).write_bytes(self.wasm)
        receipt = self.base / 'kernel-receipt.json'; receipt.write_bytes(encoded(self.receipt))
        notice = self.base / 'NOTICE'; notice.write_bytes(self.notices['foundation'])
        pins = self.engine['pins']
        options = {'profile': 'web', 'source_root': self.source, 'engine_group': self.engine['group'],
            'engine_recipe_sha256': pins['recipe'], 'engine_manifest_sha256': pins['manifest'],
            'engine_proof_sha256': pins['proof'], 'engine_runtime_sha256': pins['runtime'],
            'kernel_receipt': receipt, 'kernel_receipt_sha256': container.digest(receipt.read_bytes()),
            'developer_unqualified': True}
        options.update(changes)
        return assets, ['foundation=' + str(notice)], options

    def test_fixture_prefix_is_deterministic_canonical_and_explicitly_ineligible(self):
        first = self.assemble()
        self.assertEqual(first, self.assemble())
        prefix, envelope, facts = first
        self.assertTrue(prefix.endswith(container.HTML_MARKER))
        self.assertFalse(facts['production_eligible'])
        self.assertFalse(facts['engine']['production_eligible'])
        self.assertEqual(envelope['kernel']['kernel_profile'], 'web')
        self.assertEqual(envelope['kernel']['kernel_wasm_lookup'], producer.WASM_NAME)
        self.assertEqual(envelope['kernel']['engine_wasm_lookup'], 'engine.wasm')
        checked, observed = producer.inspect_prefix(prefix)
        self.assertEqual(checked, envelope)
        self.assertFalse(observed['production_eligible'])
        self.assertFalse(observed['engine']['whole_group_verified'])
        self.assertEqual(observed['engine']['scope'], 'embedded-retained-consumer-byte-and-static-contract-only')

    def test_both_has_distinct_compiled_profile_and_fixed_provider_policy(self):
        prefix, envelope, facts = self.assemble(profile='both')
        self.assertEqual(envelope['kernel']['kernel_profile'], 'both')
        descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
        self.assertEqual(descriptor['services'], ['foundation.kernel', 'foundation.providers'])
        self.assertEqual(descriptor['capabilities'], ['foundation.providers.v1', 'foundation.startup.v1'])
        self.assertNotIn('foundation.view', descriptor['services'])
        self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)

    def test_descriptor_mutation_cannot_change_the_producer_fixed_policy(self):
        prefix, envelope, facts = self.assemble()
        descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
        descriptor['capabilities'].append('invented')
        self.assertEqual(producer.POLICIES['web']['capabilities'], ['foundation.startup.v1'])

    def test_explicit_developer_origin_never_overrides_fixture_runtime_ineligibility(self):
        assets, notices, options = self.publish_arguments()
        for developer in (False, True):
            with self.subTest(developer=developer), patch.object(subprocess, 'run', side_effect=AssertionError('no compiler/network')), \
                    patch.object(subprocess, 'check_output', side_effect=AssertionError('no SDK/build lookup')), \
                    patch.object(subprocess, 'Popen', side_effect=AssertionError('no child process')):
                with self.assertRaisesRegex(ValueError, 'developer-unqualified|production-ineligible|fixtures'):
                    producer.package(assets, self.base / ('output-' + str(developer)), notices,
                                     **{**options, 'developer_unqualified': developer})
                self.assertFalse((self.base / ('output-' + str(developer))).exists())

    def test_every_independent_pin_failure_stops_before_output_or_tool_launch(self):
        assets, notices, options = self.publish_arguments()
        for field in ('engine_recipe_sha256', 'engine_manifest_sha256', 'engine_proof_sha256',
                      'engine_runtime_sha256', 'kernel_receipt_sha256'):
            with self.subTest(field=field), patch.object(subprocess, 'Popen', side_effect=AssertionError('no producer fallback')):
                with self.assertRaises(ValueError):
                    producer.package(assets, self.base / 'absent', notices, **{**options, field: 'f' * 64})
                self.assertFalse((self.base / 'absent').exists())

    def test_preexisting_output_is_preserved_before_engine_inspection(self):
        assets, notices, options = self.publish_arguments()
        output = self.base / 'existing'; output.mkdir(); (output / 'foreign').write_bytes(b'preserve')
        with patch.object(consumer, 'verify_kernel_consumer', side_effect=AssertionError('no input work')):
            with self.assertRaisesRegex(ValueError, 'destination must be new'):
                producer.package(assets, output, notices, **options)
        self.assertEqual((output / 'foreign').read_bytes(), b'preserve')

    def test_public_verify_cannot_upgrade_a_canonical_fixture_carrier(self):
        prefix, envelope, facts = self.assemble()
        output, descriptor = self.write_output(prefix, envelope, facts)
        with self.assertRaisesRegex(ValueError, 'real runtime observations'):
            producer.verify(output, container.digest(container.canonical_json(descriptor)))

    def test_complete_output_inspection_checks_integrity_without_upgrading_fixture_scope(self):
        prefix, envelope, facts = self.assemble()
        output, descriptor = self.write_output(prefix, envelope, facts)
        checked, observed = producer.inspect_output(output)
        self.assertEqual(checked, descriptor)
        self.assertFalse(observed['production_eligible'])
        self.assertFalse(observed['independently_pinned_descriptor'])
        _, pinned = producer.inspect_output(output, container.digest(container.canonical_json(descriptor)))
        self.assertTrue(pinned['independently_pinned_descriptor'])
        self.assertFalse(pinned['production_eligible'])
        (output / 'manifest.sha256').write_bytes(b'false checksum\n')
        with self.assertRaisesRegex(ValueError, 'checksum inventory differs'):
            producer.inspect_output(output)

    def test_complete_output_inspection_rejects_metadata_only_capability_upgrades(self):
        prefix, envelope, facts = self.assemble()
        output, descriptor = self.write_output(prefix, envelope, facts)
        descriptor['capabilities'].append('foundation.view.v1')
        (output / producer.DESCRIPTOR_NAME).write_bytes(container.canonical_json(descriptor))
        with self.assertRaisesRegex(ValueError, 'canonical policy/inputs'):
            producer.inspect_output(output)

    def test_public_verify_rejects_bad_pins_extra_files_and_tampered_prefix(self):
        prefix, envelope, facts = self.assemble()
        output, _ = self.write_output(prefix, envelope, facts)
        with self.assertRaisesRegex(ValueError, 'independent pin'):
            producer.verify(output, 'f' * 64)
        (output / 'extra').write_text('foreign')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            producer.verify(output)
        (output / 'extra').unlink()
        (output / producer.HTML_NAME).write_bytes(prefix.replace(b'Rich application kernel', b'Wrong application label'))
        with self.assertRaisesRegex(ValueError, 'prefix differs'):
            producer.verify(output)

    def test_actual_typed_exports_are_required_before_any_profile_claim(self):
        for missing in ('gui_web_engine_profile_v1', 'gui_web_engine_dispatch_v1', 'malloc'):
            with self.subTest(missing=missing):
                wasm = foundation_wasm(missing=(missing,))
                receipt = self.kernel_receipt(wasm=wasm)
                with self.assertRaisesRegex(ValueError, 'required typed export'):
                    self.receipt_check(receipt, wasm=wasm)
        wrong = foundation_wasm(dispatch_type=0)
        with self.assertRaisesRegex(ValueError, 'required typed export'):
            self.receipt_check(self.kernel_receipt(wasm=wrong), wasm=wrong)

    def test_profile_query_must_be_actual_expected_signature_result_and_order(self):
        changes = ({'observed_result': 2}, {'observed_result': True}, {'before_configure': False},
                   {'signature': {'params': ['i32'], 'results': ['i32']}}, {'export': 'metadata_only'})
        for changed in changes:
            with self.subTest(changed=changed):
                value = copy.deepcopy(self.receipt); value['compiled_profile'].update(changed)
                with self.assertRaisesRegex(ValueError, 'profile query'):
                    self.receipt_check(value)

    def test_kernel_receipt_cannot_guess_engine_describe_or_source_identity(self):
        value = copy.deepcopy(self.receipt); value['engine_profile']['build_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'DESCRIBE identity'):
            self.receipt_check(value)
        value = copy.deepcopy(self.receipt); value['source']['kernel_inputs_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'source projection'):
            self.receipt_check(value)
        value = copy.deepcopy(self.receipt); value['wasm_facts']['exports'] = []
        with self.assertRaisesRegex(ValueError, 'Wasm facts differ'):
            self.receipt_check(value)

    def test_nested_receipt_facts_preserve_json_boolean_integer_types(self):
        value = copy.deepcopy(self.receipt)
        value['engine_profile']['schema_version'] = True
        with self.assertRaisesRegex(ValueError, 'DESCRIBE identity'):
            self.receipt_check(value)
        value = copy.deepcopy(self.receipt)
        value['wasm_facts']['memories'][0]['imported'] = 0
        with self.assertRaisesRegex(ValueError, 'Wasm facts differ'):
            self.receipt_check(value)

    def test_kernel_factory_and_wasm_bytes_must_match_the_pinned_receipt(self):
        with self.assertRaisesRegex(ValueError, 'factory differs'):
            self.receipt_check(self.receipt, factory=self.factory + b'// changed\n')
        with self.assertRaisesRegex(ValueError, 'wasm differs'):
            self.receipt_check(self.receipt, wasm=self.wasm + b'changed')
        with self.assertRaisesRegex(ValueError, 'independent pin'):
            self.receipt_check(self.receipt, pin='f' * 64)

    def test_wasm_lookup_names_are_explicit_and_cannot_be_inferred_or_rewritten(self):
        value = copy.deepcopy(self.receipt)
        value['artifacts']['wasm']['lookup_name'] = 'another.wasm'
        with self.assertRaisesRegex(ValueError, 'exact compiled output name'):
            self.receipt_check(value)
        prefix, envelope, _ = self.assemble()
        for key in ('kernel_wasm_lookup', 'engine_wasm_lookup'):
            changed = copy.deepcopy(envelope); changed['kernel'][key] = 'wrong.wasm'
            raw = producer._encoded(container.canonical_json(envelope)).encode('ascii')
            modified = prefix.replace(raw, producer._encoded(container.canonical_json(changed)).encode('ascii'))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Wasm lookup names differ'):
                producer.inspect_prefix(modified)

    def test_commonjs_diagnostic_and_nonmodule_factories_cannot_claim_startup(self):
        for factory in (b'module.exports=()=>({});', b'export default function create(){main();}',
                        b'const Module={};', b'import make from "./external.mjs"; export default make;'):
            with self.subTest(factory=factory):
                with self.assertRaises(ValueError):
                    self.receipt_check(self.kernel_receipt(factory=factory), factory=factory)

    def test_shared_unbounded_or_starting_foundation_wasm_is_ineligible(self):
        for wasm in (foundation_wasm(memory=b'\x03\x01\x04'), foundation_wasm(memory=b'\x00\x01'),
                     foundation_wasm(start=0)):
            with self.subTest(wasm=container.digest(wasm)):
                with self.assertRaisesRegex(ValueError, 'private finite wasm32 memory'):
                    self.receipt_check(self.kernel_receipt(wasm=wasm), wasm=wasm)

    def test_unknown_fields_and_nonstandard_receipt_json_fail_closed(self):
        value = dict(self.receipt, unknown='not a contract')
        with self.assertRaisesRegex(ValueError, 'receipt fields'):
            self.receipt_check(value)
        raw = encoded(self.receipt).rstrip()[:-1] + b',"schema_version":1}'
        with self.assertRaises(ValueError):
            producer.inspect_kernel_receipt(raw, container.digest(raw), self.factory, self.wasm, 'web',
                                            self.receipt['engine_profile'])

    def test_fixture_and_incomplete_statuses_remain_original_observations(self):
        for status in ('passed', 'unfinished', 'failed'):
            value = copy.deepcopy(self.receipt); value['status'] = status
            _, eligible = self.receipt_check(value)
            self.assertFalse(eligible)
        value = copy.deepcopy(self.receipt); value['scope'] = 'foundation-rich-kernel-runtime'
        value['checks']['engine_describe_match'] = 'unfinished'
        self.assertFalse(self.receipt_check(value)[1])

    def test_role_and_encoded_prefix_limits_fail_with_concrete_maintenance_needs(self):
        with patch.object(container, 'MAX_KERNEL', 1024):
            with self.assertRaisesRegex(ValueError, 'encoded rich prefix exceeds carrier limit'):
                self.assemble()
        with patch.object(producer, 'MAX_NOTICES', 4):
            with self.assertRaisesRegex(ValueError, 'notices exceed'):
                self.assemble()
        with patch.object(producer, 'MAX_MODULES', 4):
            with self.assertRaisesRegex(ValueError, 'host assets exceed'):
                self.assemble()

    def test_original_evidence_count_and_byte_budgets_are_symmetric_before_encoding(self):
        evidence = producer._plain(self.engine['inspection'].evidence)
        evidence['reports'] = {'reports/' + str(index) + '.txt': b'x' for index in range(1025)}
        with self.assertRaisesRegex(ValueError, 'evidence inventory'):
            producer._encode_evidence(evidence)
        evidence = producer._plain(self.engine['inspection'].evidence)
        with patch.object(producer, 'MAX_EVIDENCE', 4):
            with self.assertRaisesRegex(ValueError, 'evidence exceeds retained budget'):
                producer._encode_evidence(evidence)
        encoded_evidence = producer._encode_evidence(evidence)
        self.assertEqual(producer._decode_evidence(encoded_evidence), evidence)

    def test_missing_or_changed_host_graph_and_generated_bundle_reject(self):
        removed = dict(self.blobs); removed.pop('engine_kernel_bridge.mjs')
        with self.assertRaisesRegex(ValueError, 'asset inventory'):
            self.assemble(blobs=removed)
        changed = dict(self.blobs); changed['appended_engine_wasm_worker.mjs'] += b'import "./unretained.mjs";\n'
        with self.assertRaisesRegex(ValueError, 'dependency changed'):
            self.assemble(blobs=changed)
        for filename in (browser_bundle.BUNDLE_NAME, surface.BUNDLE_NAME):
            changed = dict(self.blobs); changed[filename] += b'// changed\n'
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                self.assemble(blobs=changed)

    def test_notice_utf8_complete_engine_closure_and_labels_are_preserved(self):
        _, envelope, _ = self.assemble()
        labels = set(envelope['kernel']['notices'])
        self.assertEqual(labels, {'foundation'} | {'engine/' + item for item in self.engine['inspection'].notices})
        with self.assertRaises(ValueError):
            self.assemble(notices={})
        with self.assertRaises(ValueError):
            self.assemble(notices={'unsafe/label': b'wrong'})
        with self.assertRaises(UnicodeError):
            self.assemble(notices={'foundation': b'\xff'})

    def test_prefix_tampering_and_extra_html_never_reconstruct_as_canonical(self):
        prefix, _, _ = self.assemble()
        for modified in (prefix.replace(b'Rich application kernel', b'Invented kernel label'),
                         prefix.replace(b'body{', b'html{', 1), prefix + b'foreign', prefix[:-1]):
            with self.subTest(identity=container.digest(modified)), self.assertRaises(ValueError):
                producer.inspect_prefix(modified)

    def test_native_and_binary_legacy_policies_and_graphs_remain_unchanged(self):
        self.assertEqual(binary_producer.KIND, 'foundation-binary-browser-kernel-v1')
        self.assertNotIn('appended_engine_wasm_worker.mjs', binary_producer.ASSETS)
        self.assertNotIn(surface.BUNDLE_NAME, binary_producer.ASSETS)
        self.assertNotIn('browser_surface.mjs', browser_bundle.CHILD_GRAPH)
        self.assemble()
        self.assertNotIn(surface.BUNDLE_NAME, binary_producer.ASSETS)

    def test_bootstrap_syntax_is_valid_and_graph_is_embedded_without_execution(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for this focused generated-source syntax check')
        script = self.base / 'bootstrap.mjs'; script.write_text(producer.bootstrap_source())
        result = subprocess.run([node, '--check', str(script)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("import(moduleURL('appended_engine_browser_bootstrap.mjs'))", script.read_text())
        self.assertNotIn('installAppendedWasmWorker', script.read_text())

    def test_strip_reappend_replaces_only_owned_suffix_for_web_and_both_profiles(self):
        app = {'id': 'org.example.fixture', 'name': 'Fixture', 'version': '1.0.0'}
        for profile in ('web', 'both'):
            with self.subTest(profile=profile):
                prefix, envelope, facts = self.assemble(profile=profile)
                descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
                files = {'web/index.html': b'<h1>First</h1>'}
                options = {'web_entry': 'web/index.html'}
                if profile == 'both':
                    files['binary/application.wasm'] = guest_module()
                    options.update(binary_entry='binary/application.wasm', binary_profile=container.BINARY_PROFILE)
                first = container.build_package(files, app, **options)
                composed = container.compose_bytes(prefix, descriptor, first, expected_mode=profile)
                self.assertEqual(container.parse_artifact(composed, descriptor).prefix, prefix)
                files['web/index.html'] = b'<h1>Replacement</h1>'
                second = container.build_package(files, app, **options)
                replaced = container.compose_bytes(composed, descriptor, second, expected_mode=profile)
                self.assertEqual(replaced, container.compose_bytes(prefix, descriptor, second))
                self.assertEqual(container.compose_bytes(replaced, descriptor), prefix)
                self.assertEqual(container.parse_artifact(replaced, descriptor).prefix, prefix)

    def test_cli_has_no_implicit_inputs_or_verification_capability_upgrade(self):
        for arguments in (['--output', str(self.base / 'absent')],
                          ['--verify', '--profile', 'both', '--output', str(self.base / 'absent')]):
            with self.subTest(arguments=arguments), patch('sys.stdout', new_callable=io.StringIO), \
                    patch('sys.stderr', new_callable=io.StringIO) as error:
                self.assertEqual(producer.main(arguments), 1)
                self.assertIn('rich browser kernel:', error.getvalue())
                self.assertFalse((self.base / 'absent').exists())


class PhysicalRichBrowserProducerTests(unittest.TestCase):
    """Explicit physical parser fixtures, never a maintained input runtime."""
    kernel_receipt = RichBrowserProducerTests.kernel_receipt
    write_output = RichBrowserProducerTests.write_output
    composition_fixture = RichBrowserProducerTests.composition_fixture

    def setUp(self):
        RichBrowserProducerTests.setUp(self)
        self.engine = create_fixture(self.base / 'physical-engine', physical_input=True)
        self.blobs = host_blobs(physical_input=True)
        self.wasm = foundation_wasm(input_describe=True)
        self.receipt = self.kernel_receipt(physical_input=True)

    def assemble(self, **kwargs):
        return RichBrowserProducerTests.assemble(self, physical_input=True, **kwargs)

    def receipt_check(self, value, **kwargs):
        return RichBrowserProducerTests.receipt_check(self, value, physical_input=True, **kwargs)

    def test_physical_composition_receipt_preserves_old_profile_checks_and_inventory(self):
        for profile in ('web', 'both'):
            wasm, value = self.composition_fixture(profile, physical_input=True)
            checked, eligible = self.receipt_check(value, wasm=wasm, profile=profile)
            self.assertFalse(eligible)
            self.assertEqual(checked['kind'], producer.PHYSICAL_COMPOSITION_RECEIPT_KIND)
            self.assertEqual(checked['host_assets'], producer._asset_hashes(self.blobs))
            self.assertEqual(set(checked['checks']), set(self.receipt['checks']) | {'application_composition_query'})
            self.assertEqual(producer.composition_descriptor_policy(profile, checked, eligible=eligible), producer.POLICIES[profile])

    def replace_envelope(self, prefix, original, changed):
        return prefix.replace(producer._encoded(container.canonical_json(original)).encode(),
                              producer._encoded(container.canonical_json(changed)).encode())

    def test_physical_mode_is_distinct_canonical_and_fixture_ineligible(self):
        for profile in ('web', 'both'):
            with self.subTest(profile=profile):
                prefix, envelope, facts = self.assemble(profile=profile)
                self.assertEqual(envelope['kind'], producer.PHYSICAL_KIND)
                self.assertEqual(envelope['kernel']['kind'], producer.PHYSICAL_KERNEL_KIND)
                self.assertEqual(envelope['kernel']['engine_profile']['surface_capabilities'], '8225')
                self.assertFalse(facts['production_eligible'])
                self.assertEqual(producer.inspect_prefix(prefix)[0], envelope)
                descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
                self.assertEqual(descriptor['provenance']['kind'], producer.PHYSICAL_KIND)
                self.assertEqual(descriptor['capabilities'], producer.POLICIES[profile]['capabilities'])

    def test_no_metadata_inference_can_upgrade_legacy_or_physical_mode(self):
        raw = encoded(self.receipt)
        with self.assertRaises(ValueError):
            producer.make_prefix(self.blobs, self.factory, self.wasm, self.engine['inspection'], raw,
                container.digest(raw), self.notices, self.full['tree_sha256'], self.inputs['tree_sha256'], 'web')
        legacy = create_fixture(self.base / 'legacy-cross-mode')
        with self.assertRaises(ValueError):
            self.assemble(engine=legacy['inspection'])
        for value in (1, 'true', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'explicit boolean'):
                producer.bootstrap_source(value)

    def test_exact_typed_input_descriptor_export_is_required(self):
        for wasm in (foundation_wasm(), foundation_wasm(input_describe=True, input_describe_type=0)):
            receipt = self.kernel_receipt(wasm=wasm, physical_input=True)
            with self.subTest(identity=container.digest(wasm)), self.assertRaisesRegex(ValueError, 'required typed export'):
                self.receipt_check(receipt, wasm=wasm)

    def test_query_raw_bytes_order_count_utf8_and_nul_are_bound(self):
        for changed in ({'before_engine_factory': False}, {'before_configure': False},
                        {'before_engine_factory': 1}, {'observed_bytes': True}, {'observed_bytes': 0},
                        {'signature': {'params': ['i32'], 'results': ['i32']}},
                        {'export': 'metadata-only'}, {'observed_output': ''},
                        {'observed_output': producer._encoded(b'\xff'), 'observed_bytes': 1},
                        {'observed_output': producer._encoded(b'{}\0'), 'observed_bytes': 3},
                        {'observed_output': producer._encoded(b' ' * 4096), 'observed_bytes': 4096}):
            receipt = copy.deepcopy(self.receipt); receipt['compiled_input_profile'].update(changed)
            with self.subTest(changed=changed), self.assertRaises((ValueError, UnicodeError)):
                self.receipt_check(receipt)
        # A real emission need not use the producer's canonical JSON spacing.
        receipt = copy.deepcopy(self.receipt)
        raw = json.dumps(receipt['engine_profile'], indent=1).encode()
        receipt['compiled_input_profile'].update(observed_output=producer._encoded(raw), observed_bytes=len(raw))
        self.assertFalse(self.receipt_check(receipt)[1])
        canonical = container.canonical_json(self.receipt['engine_profile'])
        for raw in (b'\xef\xbb\xbf' + canonical, b'{"schema_version":1,' + canonical[1:]):
            receipt = copy.deepcopy(self.receipt)
            receipt['compiled_input_profile'].update(observed_output=producer._encoded(raw), observed_bytes=len(raw))
            with self.subTest(raw=raw[:32]), self.assertRaises(ValueError):
                self.receipt_check(receipt)

    def test_query_output_and_observed_profile_cannot_disagree(self):
        receipt = copy.deepcopy(self.receipt)
        receipt['compiled_input_profile']['observed_result']['capabilities'] = '259'
        with self.assertRaisesRegex(ValueError, 'query differs'):
            self.receipt_check(receipt)
        receipt = copy.deepcopy(self.receipt)
        observed = copy.deepcopy(receipt['engine_profile']); observed['mouse_input_version'] = 2
        raw = container.canonical_json(observed)
        receipt['compiled_input_profile'].update(observed_output=producer._encoded(raw), observed_bytes=len(raw))
        with self.assertRaisesRegex(ValueError, 'query differs'):
            self.receipt_check(receipt)

    def test_each_physical_profile_field_remains_bound_to_engine_describe(self):
        profile = self.receipt['engine_profile']
        self.assertEqual(len(profile), 20)
        for key, original in profile.items():
            changed = False if type(original) is bool else original + 1 if type(original) is int else 'changed'
            if changed == original:
                changed = True
            receipt = copy.deepcopy(self.receipt); receipt['compiled_input_profile']['observed_result'][key] = changed
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'query differs'):
                self.receipt_check(receipt)

    def test_full_host_inventory_binds_same_directory_renderer_bytes(self):
        self.assertEqual(set(self.receipt['host_assets']), set(producer.asset_names()))
        for filename in ('renderer_surface_frame.mjs', surface.BUNDLE_NAME, 'engine_kernel_bridge.mjs'):
            receipt = copy.deepcopy(self.receipt); receipt['host_assets'][filename] = 'f' * 64
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, 'host asset inventory'):
                self.receipt_check(receipt)
        # Canonical but differently selected legacy renderer bytes are not the
        # graph observed by this physical runtime receipt.
        with self.assertRaisesRegex(ValueError, 'host asset inventory'):
            self.assemble(blobs=host_blobs())
        receipt = copy.deepcopy(self.receipt); receipt['host_assets'].pop(surface.BUNDLE_NAME)
        with self.assertRaisesRegex(ValueError, 'host asset inventory'):
            self.receipt_check(receipt)

    def test_new_receipt_checks_cannot_omit_the_physical_runtime(self):
        self.assertEqual(set(self.receipt['checks']), {'inert_factory', 'compiled_profile_query',
            'engine_describe_match', 'input_profile_query', 'host_assets_match', *consumer.PHYSICAL_INPUT_CHECKS})
        for key in ('input_profile_query', 'host_assets_match') + consumer.PHYSICAL_INPUT_CHECKS:
            receipt = copy.deepcopy(self.receipt); receipt['checks'].pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'runtime checks'):
                self.receipt_check(receipt)
            receipt = copy.deepcopy(self.receipt); receipt['scope'] = 'foundation-rich-kernel-runtime'
            receipt['checks'][key] = 'unfinished'
            self.assertFalse(self.receipt_check(receipt)[1])

    def test_prefix_cannot_change_outer_kind_or_drop_catalog_evidence(self):
        prefix, envelope, _ = self.assemble()
        for mutate in (lambda value: value.update(kind=producer.KIND),
                       lambda value: value['kernel'].update(kind='foundation-copied-engine-browser'),
                       lambda value: value['evidence']['engine'].pop('command_catalog')):
            changed = copy.deepcopy(envelope); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                producer.inspect_prefix(self.replace_envelope(prefix, envelope, changed))

    def test_physical_projection_is_six_owned_fields_and_legacy_bootstrap_unchanged(self):
        source = producer.bootstrap_source(True)
        self.assertIn("const physical=await import(moduleURL('renderer_surface_child_bundle.mjs'))", source)
        for field in surface.CHILD_FIELDS:
            self.assertIn(field + ':physical.' + field, source)
        self.assertIn('const physicalRendererBundle=Object.freeze({', source)
        self.assertIn(',physicalRendererBundle});', source)
        self.assertNotIn('physicalRendererBundle', producer.bootstrap_source())
        self.assertEqual(producer.bootstrap_source(), producer.bootstrap_source(False))

    def test_physical_bootstrap_is_syntax_checked_without_importing_its_assets(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for the generated-source syntax check')
        script = self.base/'physical-bootstrap.mjs'; script.write_text(producer.bootstrap_source(True))
        result = subprocess.run([node, '--check', str(script)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_catalog_transport_has_symmetric_bounded_raw_and_encoded_evidence(self):
        evidence = producer._plain(self.engine['inspection'].evidence)
        retained = producer._encode_evidence(evidence, True)
        self.assertEqual(producer._decode_evidence(retained, True), evidence)
        with patch.object(producer, 'MAX_COMMAND_CATALOG', 4):
            with self.assertRaisesRegex(ValueError, 'catalog exceeds'):
                producer._encode_evidence(evidence, True)
            with self.assertRaisesRegex(ValueError, 'command_catalog'):
                producer._decode_evidence(retained, True)

    def test_physical_fixture_cannot_publish_or_publicly_verify(self):
        prefix, envelope, facts = self.assemble()
        output, _ = self.write_output(prefix, envelope, facts, 'physical-output')
        self.assertFalse(producer.inspect_output(output)[1]['production_eligible'])
        with self.assertRaisesRegex(ValueError, 'real runtime observations'):
            producer.verify(output)
        assets, notices, options = RichBrowserProducerTests.publish_arguments(self, physical_input=True)
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('no build/download/child fallback')):
            with self.assertRaisesRegex(ValueError, 'production-ineligible|fixtures'):
                producer.package(assets, self.base / 'must-not-publish', notices, **options)
        self.assertFalse((self.base / 'must-not-publish').exists())

    def test_physical_strip_and_reappend_preserve_retained_prefix(self):
        app = {'id': 'org.example.physical.fixture', 'name': 'Fixture', 'version': '1.0.0'}
        for profile in ('web', 'both'):
            prefix, envelope, facts = self.assemble(profile=profile)
            descriptor = producer._descriptor(prefix, envelope, facts, self.inputs)
            files = {'web/index.html': b'<h1>One</h1>'}; options = {'web_entry': 'web/index.html'}
            if profile == 'both':
                files['binary/application.wasm'] = guest_module()
                options.update(binary_entry='binary/application.wasm', binary_profile=container.BINARY_PROFILE)
            first = container.build_package(files, app, **options)
            composed = container.compose_bytes(prefix, descriptor, first, expected_mode=profile)
            files['web/index.html'] = b'<h1>Two</h1>'
            second = container.build_package(files, app, **options)
            replaced = container.compose_bytes(composed, descriptor, second, expected_mode=profile)
            self.assertEqual(container.parse_artifact(replaced, descriptor).prefix, prefix)
            self.assertEqual(container.compose_bytes(replaced, descriptor), prefix)

    def test_cli_verify_cannot_select_or_upgrade_physical_mode(self):
        with patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO) as error:
            self.assertEqual(producer.main(['--verify', '--physical-input', '--output', str(self.base/'missing')]), 1)
        self.assertIn('production flags cannot upgrade', error.getvalue())

    def test_cli_threads_only_the_explicit_physical_selection(self):
        common = ['--output', str(self.base/'not-created'), '--assets', str(self.base/'assets'),
                  '--source-root', str(self.source), '--profile', 'web', '--engine-group', str(self.engine['group']),
                  '--kernel-receipt', str(self.base/'receipt'), '--developer-unqualified']
        for name in ('engine-recipe', 'engine-manifest', 'engine-proof', 'engine-runtime', 'kernel-receipt'):
            common += ['--' + name + '-sha256', 'f' * 64]
        for selected in (False, True):
            fake = {'profile': 'web', 'provenance': {'kind': producer.PHYSICAL_KIND if selected else producer.KIND,
                                                    'qualification': producer.QUALIFICATION}}
            with self.subTest(selected=selected), patch.object(producer, 'package', return_value=fake) as package, \
                    patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(producer.main(common + (['--physical-input'] if selected else [])), 0)
                self.assertIs(package.call_args.kwargs['physical_input'], selected)
        self.assertFalse((self.base/'not-created').exists())


if __name__ == '__main__':
    unittest.main()
