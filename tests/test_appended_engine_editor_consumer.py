"""Independent inert editor2035 admission tests, never runtime qualification.

All original reports retain parser-fixture-only scope. Tiny Wasm, ESM and
retained archives are inspected as bytes and never executed or extracted.
"""
import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_engine_editor_consumer as consumer
import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
from appended_engine_consumer import scan_wasm
from appended_engine_document_fixture import DocumentEngineFixture, tiny_wasm as document_wasm
from appended_engine_editor_fixture import (
    ACK_SHA, BASE_SHA, BOOTSTRAP_CHECKS, BUILD_PATH, CONTRACT_SHA, DATA_PATH,
    DOCUMENT_CONTRACT_SHA, EDITOR_CATALOG_SHA, EDITOR_CHECKS, EDITOR_HEADER_SHA,
    EDITOR_SCHEMA_SHA, FACTORY, FACTORY_PATH, HEADER, INTERFACE_PATHS, NOTICE_PATH,
    PHYSICAL_CATALOG, PHYSICAL_SHA, PROFILE_NAME, PROOF_PATH, REPORT_PATH,
    RUNTIME_CHECKS, RUNTIME_PATH, TARGET, WASM_PATH, EditorEngineFixture,
    bootstrap, encoded, provider_contract, sha, tiny_wasm, write,
)


class EditorConsumerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-editor-consumer-fixture-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.fixture = EditorEngineFixture(self.base / 'fixture')
        self.evidence = self.fixture.evidence()

    def pins(self, evidence=None):
        evidence = self.evidence if evidence is None else evidence
        return {key: sha(evidence[label]) for key, label in
                (('recipe', 'recipe'), ('manifest', 'binary_manifest'), ('proof', 'proof'), ('runtime', 'runtime'))}

    def inspect(self, *, fixture=None, evidence=None, assets=None, notices=None, **kwargs):
        fixture = self.fixture if fixture is None else fixture
        evidence = fixture.evidence() if evidence is None else evidence
        selection = {'editor_profile': fixture.editor_profile, **kwargs}
        result = consumer.inspect_embedded_consumer(evidence=evidence,
            assets=fixture.assets if assets is None else assets, notices=fixture.notices if notices is None else notices,
            pins=self.pins(evidence), kernel_target=copy.deepcopy(TARGET),
            paired_sdk=fixture.toolchain['paired_sdk_sha256'], **selection)
        self.assertEqual(result.as_dict()['runtime_evidence']['scope'], 'parser-fixture-only')
        self.assertFalse(result.metadata['production_eligible'])
        return result

    def changed(self, key, change, *, evidence=None, raw=None):
        """Rebind outer hashes so the intended changed inner guard is reached."""
        evidence = copy.deepcopy(self.evidence if evidence is None else evidence)
        value = json.loads(evidence[key]); change(value)
        evidence[key] = encoded(value) if raw is None else raw
        binary, proof = json.loads(evidence['binary_manifest']), json.loads(evidence['proof'])
        if key == 'provider_build':
            build_hash = sha(evidence[key]); proof['provider_build']['sha256'] = build_hash
            proof['engine_profile']['build_sha256'] = build_hash
            runtime = json.loads(evidence['runtime'])
            runtime['provider_build_sha256'] = build_hash
            runtime['engine_profile']['build_sha256'] = build_hash
            runtime['bootstrap'] = bootstrap(runtime['engine_profile'])
            evidence['runtime'] = encoded(runtime); binary['files'][BUILD_PATH] = build_hash
        if key in ('provider_build', 'runtime'):
            proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
            binary['files'][RUNTIME_PATH] = sha(evidence['runtime'])
        if key != 'proof':
            evidence['proof'] = encoded(proof)
        binary['files'][PROOF_PATH] = sha(evidence['proof'])
        if key != 'binary_manifest':
            evidence['binary_manifest'] = encoded(binary)
        return evidence

    def rebind_source(self, recipe, source, *, evidence=None):
        evidence = copy.deepcopy(self.evidence if evidence is None else evidence)
        evidence['recipe'] = encoded(recipe); recipe_hash = sha(evidence['recipe'])
        source['recipe_id'] = recipe_hash; source['files']['recipe.json'] = recipe_hash
        evidence['source_manifest'] = encoded(source)
        build = json.loads(evidence['provider_build'])
        build.update(source_recipe_sha256=recipe_hash, source_inputs_sha256=sha(encoded(recipe['inputs'])))
        evidence = self.changed('provider_build', lambda value: value.update(build), evidence=evidence)
        proof = json.loads(evidence['proof'])
        proof.update(recipe_id=recipe_hash, sources_sha256=sha(evidence['source_manifest']))
        proof['engine_profile']['source_recipe_sha256'] = recipe_hash
        runtime = json.loads(evidence['runtime'])
        runtime.update(recipe_id=recipe_hash, engine_profile=copy.deepcopy(proof['engine_profile']))
        runtime['bootstrap'] = bootstrap(runtime['engine_profile'])
        evidence['runtime'] = encoded(runtime); proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
        evidence['proof'] = encoded(proof)
        binary = json.loads(evidence['binary_manifest'])
        binary.update(recipe_id=recipe_hash, sources_sha256=sha(evidence['source_manifest']), provider={
            **recipe['provider'], 'entry': FACTORY_PATH, 'assets': sorted(self.fixture.assets)})
        for path, label in ((BUILD_PATH, 'provider_build'), (PROOF_PATH, 'proof'), (RUNTIME_PATH, 'runtime')):
            binary['files'][path] = sha(evidence[label])
        evidence['binary_manifest'] = encoded(binary)
        return evidence

    def with_assets(self, assets, records, *, evidence=None):
        evidence = copy.deepcopy(self.evidence if evidence is None else evidence)
        proof = json.loads(evidence['proof']); proof['assets'] = records
        proof['wasm_facts'] = scan_wasm(assets[WASM_PATH])
        runtime = json.loads(evidence['runtime']); runtime['assets_sha256'] = sha(encoded(records))
        evidence['runtime'] = encoded(runtime); proof['runtime_evidence']['sha256'] = sha(evidence['runtime'])
        evidence['proof'] = encoded(proof)
        binary = json.loads(evidence['binary_manifest']); binary['provider']['assets'] = sorted(assets)
        for path, raw in assets.items():
            binary['files'][path] = sha(raw); binary['modes'][path] = records[path]['mode']
        binary['files'][RUNTIME_PATH] = sha(evidence['runtime']); binary['files'][PROOF_PATH] = sha(evidence['proof'])
        evidence['binary_manifest'] = encoded(binary)
        return evidence

    def group(self, fixture=None, name='group'):
        fixture = self.fixture if fixture is None else fixture
        group = self.base / name
        fixture.export_group(group)
        return group

    def test_embedded_editor_has_exact_profile_interfaces_catalog_and_original_bytes(self):
        result = self.inspect(); metadata = result.as_dict()
        self.assertEqual(metadata['scope'], 'embedded-retained-editor-v1-consumer-byte-and-static-contract-only')
        self.assertFalse(metadata['whole_group_verified']); self.assertIsNone(metadata['group_files'])
        self.assertEqual(len(metadata['engine_profile']), 38)
        self.assertEqual(metadata['engine_profile']['capabilities'], '2035')
        self.assertEqual(metadata['engine_profile']['surface_protocol_version'], 2)
        self.assertEqual(metadata['engine_profile']['surface_capabilities'], '8255')
        self.assertEqual(metadata['engine_profile']['display_scale'], 1)
        self.assertIs(type(metadata['engine_profile']['display_scale']), int)
        self.assertEqual(set(metadata['interfaces']), set(INTERFACE_PATHS))
        self.assertEqual(metadata['interfaces']['base_header']['path'], HEADER)
        self.assertEqual(metadata['provider_contract'], provider_contract())
        self.assertEqual([item['operation'] for item in metadata['provider_contract']['queries']], [3, 4])
        self.assertEqual([item['operation'] for item in metadata['provider_contract']['commands']], [1, 3, 5, 6, 7, 8, 9])
        self.assertEqual(set(metadata['runtime_evidence']['checks']), set(RUNTIME_CHECKS))
        self.assertEqual(len(RUNTIME_CHECKS), 28)
        for role, pin in (('editor_header', EDITOR_HEADER_SHA), ('editor_contract', CONTRACT_SHA),
                          ('editor_catalog', EDITOR_CATALOG_SHA), ('editor_schema', EDITOR_SCHEMA_SHA)):
            self.assertEqual(sha(self.fixture.interfaces[INTERFACE_PATHS[role]]), pin)
        self.assertEqual(sha(PHYSICAL_CATALOG), PHYSICAL_SHA)
        self.assertEqual(dict(result.evidence['interfaces']), self.fixture.interfaces)
        for label in ('binary_manifest', 'source_manifest', 'recipe', 'proof', 'provider_build', 'runtime'):
            self.assertEqual(result.evidence[label], self.evidence[label])

    def test_complete_group_is_verified_and_fixture_verify_always_refuses(self):
        for data in (False, True):
            fixture = self.fixture if not data else EditorEngineFixture(self.base / 'data', data=True)
            group = self.group(fixture, 'group-' + str(data)); args = fixture.group_arguments()
            result = consumer.inspect_kernel_consumer(group, **args)
            with self.subTest(data=data):
                self.assertEqual(result.metadata['scope'], 'retained-editor-v1-consumer-byte-and-static-contract-only')
                self.assertTrue(result.metadata['whole_group_verified'])
                self.assertEqual(set(result.metadata['group_files']), set(sdk.group_names(fixture.pins()['recipe'])))
                self.assertEqual(result.as_dict()['runtime_evidence']['scope'], 'parser-fixture-only')
                self.assertFalse(result.metadata['production_eligible'])
                with self.assertRaisesRegex(ValueError, 'ineligible'):
                    consumer.verify_kernel_consumer(group, **args)

    def test_explicit_selector_is_required_closed_and_never_upgrades_document_profiles(self):
        for selected in (None, '', True, 'pixel', 'physical', '2035', PROFILE_NAME, 'EDITOR', 'editor '):
            with self.subTest(selected=selected), self.assertRaises((ValueError, TypeError)):
                self.inspect(editor_profile=selected)
        with self.assertRaises(TypeError):
            consumer.validate_engine_profile(self.fixture.profile)
        for mode in ('pixel', 'physical'):
            fixture = DocumentEngineFixture(self.base / mode, document_profile=mode)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                consumer.inspect_embedded_consumer(evidence=fixture.evidence(), assets=fixture.assets,
                    notices=fixture.notices, pins=fixture.pins(), kernel_target=TARGET,
                    paired_sdk=fixture.toolchain['paired_sdk_sha256'], editor_profile='editor')

    def test_owned_results_are_frozen_and_detached_from_caller_mutation(self):
        evidence = copy.deepcopy(self.evidence); assets = dict(self.fixture.assets)
        result = self.inspect(evidence=evidence, assets=assets)
        for path in self.fixture.interfaces:
            evidence['interfaces'][path] = b'changed'
            self.assertEqual(result.evidence['interfaces'][path], self.fixture.interfaces[path])
        evidence['reports'][REPORT_PATH] = b'changed'; assets[WASM_PATH] = b'changed'
        self.assertEqual(result.evidence['reports'][REPORT_PATH], self.fixture.reports[REPORT_PATH])
        self.assertEqual(result.assets[WASM_PATH], self.fixture.assets[WASM_PATH])
        for mapping in (result.metadata, result.evidence, result.evidence['interfaces'], result.evidence['reports']):
            with self.assertRaises(TypeError):
                mapping['injected'] = b'changed'
        exported = result.as_dict(); exported['provider_contract']['queries'][1]['operation'] = 99
        self.assertEqual(result.as_dict()['provider_contract']['queries'][1]['operation'], 4)

    def test_report_and_all_ten_interface_mappings_are_snapshotted_once(self):
        from collections.abc import Mapping

        class Changing(Mapping):
            def __init__(self, original):
                self.original, self.reads = original, {}
            def __iter__(self):
                return iter(self.original)
            def __len__(self):
                return len(self.original)
            def __getitem__(self, key):
                self.reads[key] = self.reads.get(key, 0) + 1
                return self.original[key] if self.reads[key] == 1 else b'changed after first read'

        evidence = copy.deepcopy(self.evidence)
        evidence['reports'] = Changing(self.fixture.reports)
        evidence['interfaces'] = Changing(self.fixture.interfaces)
        result = self.inspect(evidence=evidence)
        self.assertEqual(dict(result.evidence['reports']), self.fixture.reports)
        self.assertEqual(dict(result.evidence['interfaces']), self.fixture.interfaces)

    def test_four_independent_pins_and_exact_original_bytes_are_required(self):
        for key in self.pins():
            for pin in ('0' * 64, self.pins()[key].upper(), None):
                pins = self.pins(); pins[key] = pin
                with self.subTest(key=key, pin=pin), self.assertRaises((ValueError, TypeError)):
                    consumer.inspect_embedded_consumer(evidence=self.evidence, assets=self.fixture.assets,
                        notices=self.fixture.notices, pins=pins, kernel_target=TARGET,
                        paired_sdk=self.fixture.toolchain['paired_sdk_sha256'], editor_profile='editor')
        evidence = copy.deepcopy(self.evidence); evidence['proof'] += b'\n'
        with self.assertRaisesRegex(ValueError, 'pin'):
            consumer.inspect_embedded_consumer(evidence=evidence, assets=self.fixture.assets,
                notices=self.fixture.notices, pins=self.pins(), kernel_target=TARGET,
                paired_sdk=self.fixture.toolchain['paired_sdk_sha256'], editor_profile='editor')

    def test_legacy_kinds_cannot_upgrade_after_complete_outer_rehashing(self):
        legacy = {
            'proof': ('foundation-neutral-engine-provider-proof-v1',
                      'foundation-neutral-engine-provider-physical-proof-v1',
                      'foundation-neutral-engine-provider-document-v2-proof-v1'),
            'provider_build': ('foundation-neutral-engine-provider-build-v1',
                               'foundation-neutral-engine-provider-physical-build-v1',
                               'foundation-neutral-engine-provider-document-v2-build-v1'),
            'runtime': ('foundation-neutral-engine-runtime-evidence-v1',
                        'foundation-neutral-engine-physical-runtime-evidence-v1',
                        'foundation-neutral-engine-document-v2-runtime-evidence-v1'),
        }
        for key, kinds in legacy.items():
            for kind in kinds:
                with self.subTest(key=key, kind=kind), self.assertRaises(ValueError):
                    self.inspect(evidence=self.changed(key, lambda value: value.update(kind=kind)))

    def test_evidence_and_editor_metadata_fields_are_closed(self):
        for key in ('proof', 'provider_build', 'runtime'):
            for mutation in (lambda value: value.pop('kind'), lambda value: value.update(extra=True),
                             lambda value: value.update(schema_version=True)):
                with self.subTest(key=key, mutation=mutation), self.assertRaises(ValueError):
                    self.inspect(evidence=self.changed(key, mutation))
        for key in self.evidence:
            evidence = copy.deepcopy(self.evidence); evidence.pop(key)
            with self.subTest(missing=key), self.assertRaises(ValueError):
                consumer.inspect_embedded_consumer(evidence=evidence, assets=self.fixture.assets,
                    notices=self.fixture.notices, pins=self.pins(), kernel_target=TARGET,
                    paired_sdk=self.fixture.toolchain['paired_sdk_sha256'], editor_profile='editor')
        evidence = copy.deepcopy(self.evidence); evidence['extra'] = b''
        with self.assertRaises(ValueError):
            self.inspect(evidence=evidence)

    def test_strict_json_rejects_duplicate_nonfinite_bom_and_invalid_unicode(self):
        original = self.evidence['runtime']
        for raw in (b'{"kind":"duplicate",' + original[1:],
                    original.replace(b'"schema_version": 1', b'"schema_version": NaN'),
                    b'\xef\xbb\xbf' + original,
                    original.replace(b'fixture-not-a-browser', b'\\ud800')):
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                self.assertNotEqual(raw, original)
                self.inspect(evidence=self.changed('runtime', lambda value: None, raw=raw))

    def test_source_build_profile_target_sdk_and_provider_abi_joins_are_exact(self):
        for mutation in (lambda value: value.update(contract_header_sha256=DOCUMENT_CONTRACT_SHA),
                         lambda value: value.update(source_inputs_sha256='f' * 64),
                         lambda value: value['configuration'].update(editor_profile='physical'),
                         lambda value: value['configuration'].update(fixed_viewport_width=True),
                         lambda value: value.update(capabilities='2003'),
                         lambda value: value.update(binding='copied-owner-bridge/direct-worker-document-v2')):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('provider_build', mutation))
        for key, changed in (('abi_minor', 0), ('abi_minor', True), ('binding', 'linked-owner')):
            recipe, source = copy.deepcopy(self.fixture.recipe), copy.deepcopy(self.fixture.source)
            recipe['provider'][key] = changed
            with self.subTest(key=key, value=changed), self.assertRaises(ValueError):
                self.inspect(evidence=self.rebind_source(recipe, source))
        for target, paired in (({**TARGET, 'processor': 'x86_64'}, self.fixture.toolchain['paired_sdk_sha256']),
                               (TARGET, 'f' * 64)):
            with self.subTest(target=target, sdk=paired), self.assertRaises(ValueError):
                consumer.inspect_embedded_consumer(evidence=self.evidence, assets=self.fixture.assets,
                    notices=self.fixture.notices, pins=self.pins(), kernel_target=target,
                    paired_sdk=paired, editor_profile='editor')

    def test_fixed_query4_and_command8_9_contracts_are_exact_and_typed(self):
        for collection, index in (('queries', 1), ('commands', 5), ('commands', 6)):
            for field, changed in (('operation', 3), ('maximum_input_bytes', 235),
                                   ('required_reply_capacity', 1048575), ('capability', '1024'),
                                   ('schema_sha256', ACK_SHA), ('maximum_input_bytes', True)):
                def mutation(value):
                    value['provider_contract'][collection][index][field] = changed
                with self.subTest(collection=collection, index=index, field=field), self.assertRaises(ValueError):
                    self.inspect(evidence=self.changed('provider_build', mutation))
        for mutation in (lambda value: value['queries'].reverse(),
                         lambda value: value['commands'].pop(),
                         lambda value: value['commands'].append(copy.deepcopy(value['commands'][-1])),
                         lambda value: value.update(getter_maximum_minor=True)):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('provider_build', lambda value: mutation(value['provider_contract'])))
        for collection, index in (('queries', 1), ('commands', 5), ('commands', 6)):
            wrong = provider_contract(); wrong[collection][index]['maximum_input_bytes'] -= 1
            evidence = self.changed('provider_build', lambda value: value.update(provider_contract=copy.deepcopy(wrong)))
            evidence = self.changed('runtime', lambda value: value['provider_observation'].update(contract=copy.deepcopy(wrong)), evidence=evidence)
            with self.subTest(self_consistent_wrong=(collection, index)), self.assertRaisesRegex(ValueError, 'operation contract'):
                self.inspect(evidence=evidence)

    def test_observed_provider_minor_and_operations_must_match_original_build(self):
        for mutation in (lambda value: value.update(getter_maximum_minor=0),
                         lambda value: value.update(getter_maximum_minor=True),
                         lambda value: value['contract']['queries'][1].update(operation=3),
                         lambda value: value['contract']['commands'][-1].update(schema_sha256=ACK_SHA),
                         lambda value: value.update(extra=True)):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', lambda value: mutation(value['provider_observation'])))

    def test_every_interface_role_path_pin_and_owned_byte_closure_is_exact(self):
        for role, path in INTERFACE_PATHS.items():
            for mutation in (lambda value: value['interfaces'].pop(role),
                             lambda value: value['interfaces'][role].update(sha256='f' * 64),
                             lambda value: value['interfaces'][role].update(path=path.upper()),
                             lambda value: value['interfaces'][role].update(extra=True)):
                with self.subTest(role=role, mutation=mutation), self.assertRaises(ValueError):
                    self.inspect(evidence=self.changed('proof', mutation))
            evidence = copy.deepcopy(self.evidence); evidence['interfaces'][path] += b'\n'
            with self.subTest(role=role, changed_bytes=True), self.assertRaises(ValueError):
                self.inspect(evidence=evidence)
        evidence = copy.deepcopy(self.evidence); evidence['interfaces']['extra.json'] = b'{}'
        with self.assertRaises(ValueError):
            self.inspect(evidence=evidence)

    def test_each_interface_joins_same_binary_source_and_recipe_inventory(self):
        for role, path in INTERFACE_PATHS.items():
            with self.subTest(role=role, binary=True), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('binary_manifest', lambda value: value['files'].update({path: 'f' * 64})))
            for wrong in ('missing', 'bytes', 'role'):
                recipe, source = copy.deepcopy(self.fixture.recipe), copy.deepcopy(self.fixture.source)
                if wrong == 'missing':
                    recipe['inputs'].pop(path); source['files'].pop(path); source['modes'].pop(path)
                elif wrong == 'bytes':
                    recipe['inputs'][path]['sha256'] = 'f' * 64; source['files'][path] = 'f' * 64
                else:
                    recipe['inputs'][path]['role'] = 'source'
                with self.subTest(role=role, wrong=wrong), self.assertRaises(ValueError):
                    self.inspect(evidence=self.rebind_source(recipe, source))

    def test_exact_source_helper_closure_is_required(self):
        expected = {'tools/appended_engine_manifest.py', 'tools/appended_engine_sdk.py', 'tools/dependency_archive.py'}
        self.assertEqual(set(manifest.HELPERS), expected)
        for path in expected:
            self.assertEqual(self.fixture.recipe['inputs'][path]['role'], 'helper')
            self.assertEqual(self.fixture.source['files'][path], sha((ROOT / path).read_bytes()))
            recipe, source = copy.deepcopy(self.fixture.recipe), copy.deepcopy(self.fixture.source)
            recipe['inputs'].pop(path); source['files'].pop(path); source['modes'].pop(path)
            with self.subTest(helper=path), self.assertRaises(ValueError):
                self.inspect(evidence=self.rebind_source(recipe, source))

    def test_interface_metadata_asset_notice_and_report_roles_cannot_alias(self):
        for path in (RUNTIME_PATH, PROOF_PATH):
            with self.subTest(metadata_alias=path), self.assertRaisesRegex(ValueError, 'Conflicting'):
                self.inspect(evidence=self.changed('proof', lambda value: value['provider_build'].update(path=path)))
        for path in (HEADER, PROOF_PATH, BUILD_PATH, RUNTIME_PATH, FACTORY_PATH, WASM_PATH, NOTICE_PATH,
                     INTERFACE_PATHS['document_header'], INTERFACE_PATHS['editor_schema']):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('proof', lambda value: value['interfaces']['editor_catalog'].update(path=path)))
        for path in INTERFACE_PATHS.values():
            evidence = self.changed('runtime', lambda value: [check.update(evidence=[{'path': path, 'sha256': sha(self.fixture.interfaces[path])}])
                                                            for check in value['checks'].values()])
            evidence['reports'] = {path: self.fixture.interfaces[path]}
            with self.subTest(report_alias=path), self.assertRaises(ValueError):
                self.inspect(evidence=evidence)

    def test_bootstrap_full_worker64_editor_exports_signature_markers_and_order_are_exact(self):
        mutations = (lambda value: value.update(worker_epoch='18446744073709551616'),
                     lambda value: value.update(worker_epoch='018446744073709551614'),
                     lambda value: value.update(first_start_worker_epoch='4294967294'),
                     lambda value: value['engine_configure'].update(worker_hi=0),
                     lambda value: value['engine_configure'].update(worker_lo=True),
                     lambda value: value['engine_configure'].update(observed_result=True),
                     lambda value: value['engine_configure'].update(export='bib_engine_wasm_document_configure_v1'),
                     lambda value: value['engine_facts'].update(export='bib_engine_wasm_document_facts_v1'),
                     lambda value: value['engine_facts']['signature'].update(params=['i32']),
                     lambda value: value.update(marker_before=65536),
                     lambda value: value.update(marker_after=True),
                     lambda value: value['checks'].update(configure_before_describe=True),
                     lambda value: value['checks'].update(extra='passed'))
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', lambda value: mutation(value['bootstrap'])))
        self.assertGreater(int(self.fixture.runtime['bootstrap']['worker_epoch']), 2**53)

    def test_each_failed_or_unexecuted_bootstrap_check_is_preserved_and_ineligible(self):
        for name in BOOTSTRAP_CHECKS:
            for status in ('failed', 'not-run'):
                evidence = self.changed('runtime', lambda value: value['bootstrap']['checks'].update({name: status}))
                with self.subTest(name=name, status=status):
                    result = self.inspect(evidence=evidence)
                    self.assertEqual(result.as_dict()['runtime_evidence']['bootstrap']['checks'][name], status)

    def test_facts_preserve_original_whitespace_and_key_order_bytes(self):
        raw = json.dumps(self.fixture.profile, indent=1).encode('utf-8')
        def observed(value):
            value['bootstrap']['engine_facts'].update(observed_output=base64.b64encode(raw).decode('ascii'), observed_bytes=len(raw))
        result = self.inspect(evidence=self.changed('runtime', observed))
        retained = result.as_dict()['runtime_evidence']['bootstrap']['engine_facts']
        self.assertEqual(base64.b64decode(retained['observed_output']), raw)
        self.assertEqual(retained['observed_bytes'], len(raw))

    def test_bootstrap_facts_require_strict_measured_raw_bytes_and_same_profile(self):
        for raw in (b'\xef\xbb\xbf' + encoded(self.fixture.profile), encoded(self.fixture.profile) + b'\0',
                    b'\xff', b'{"schema_version":1,"schema_version":1}', b'x' * 4096):
            def mutate(value):
                value['bootstrap']['engine_facts'].update(observed_output=base64.b64encode(raw).decode('ascii'), observed_bytes=len(raw))
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', mutate))
        for mutation in (lambda value: value['engine_facts'].update(observed_bytes=True),
                         lambda value: value['engine_facts'].update(observed_bytes=1),
                         lambda value: value['engine_facts'].update(observed_result=0),
                         lambda value: value['engine_facts'].update(observed_output='!!!!'),
                         lambda value: value['describe_profile'].update(surface_protocol_version=1)):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', lambda value: mutation(value['bootstrap'])))

    def test_all_28_original_checks_are_required_with_original_report_references(self):
        for name in RUNTIME_CHECKS:
            with self.subTest(missing=name), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', lambda value: value['checks'].pop(name)))
            with self.subTest(no_evidence=name), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', lambda value: value['checks'][name].update(evidence=[])))

    def test_each_editor_failed_or_unexecuted_check_is_retained_without_qualification(self):
        for name in EDITOR_CHECKS:
            for status in ('failed', 'not-run'):
                changed = self.changed('runtime', lambda value: value['checks'][name].update(status=status, evidence=[]))
                with self.subTest(name=name, status=status):
                    result = self.inspect(evidence=changed)
                    self.assertEqual(result.as_dict()['runtime_evidence']['checks'][name], {'status': status, 'evidence': []})

    def test_report_notice_status_and_original_browser_closure_are_strict(self):
        for mutation in (lambda value: value.update(checks={'passed': True}),
                         lambda value: value['checks'][EDITOR_CHECKS[0]].update(extra=True),
                         lambda value: value['checks'][EDITOR_CHECKS[0]]['evidence'][0].update(sha256='f' * 64),
                         lambda value: value['checks'][EDITOR_CHECKS[0]]['evidence'].append(copy.deepcopy(value['checks'][EDITOR_CHECKS[0]]['evidence'][0])),
                         lambda value: value.update(scope='qualification'),
                         lambda value: value['browser'].update(extra=True)):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.changed('runtime', mutation))
        for key in ('reports', 'interfaces'):
            evidence = copy.deepcopy(self.evidence); evidence[key] = {}
            with self.subTest(empty=key), self.assertRaises(ValueError):
                self.inspect(evidence=evidence)
        for notices in ({}, {NOTICE_PATH: b'changed'}):
            with self.subTest(notices=notices), self.assertRaises(ValueError):
                self.inspect(notices=notices)
        evidence = copy.deepcopy(self.evidence); evidence['reports']['extra.txt'] = b'unreferenced'
        with self.assertRaises(ValueError):
            self.inspect(evidence=evidence)
        for status in ('failed', 'incomplete'):
            self.inspect(evidence=self.changed('runtime', lambda value: value.update(status=status)))

    def test_actual_editor_wasm_exports_are_required_even_after_scan_and_hash_rebinding(self):
        variants = (document_wasm(), tiny_wasm(facts_type=0), tiny_wasm(configure_type=1),
                    tiny_wasm(omit=('bib_engine_wasm_editor_facts_v1',)),
                    tiny_wasm(omit=('bib_engine_wasm_editor_configure_v1',)),
                    tiny_wasm(start=0), tiny_wasm(memory=b'\x03\x01\x02'),
                    tiny_wasm(extra=(('main', 0, 0),)), tiny_wasm(extra=(('bib_eval', 0, 0),)))
        for wasm in variants:
            assets = {**self.fixture.assets, WASM_PATH: wasm}; records = copy.deepcopy(self.fixture.asset_records)
            records[WASM_PATH].update(sha256=sha(wasm), bytes=len(wasm))
            with self.subTest(wasm=sha(wasm)), self.assertRaises(ValueError):
                self.inspect(evidence=self.with_assets(assets, records), assets=assets)

    def test_finite_private_imported_memory_preserves_origin_and_fixture_scope(self):
        wasm = tiny_wasm(imported_memory=True); assets = {**self.fixture.assets, WASM_PATH: wasm}
        records = copy.deepcopy(self.fixture.asset_records); records[WASM_PATH].update(sha256=sha(wasm), bytes=len(wasm))
        result = self.inspect(evidence=self.with_assets(assets, records), assets=assets)
        memory = result.as_dict()['wasm_facts']['memories']
        self.assertEqual(len(memory), 1); self.assertTrue(memory[0]['imported'])
        self.assertFalse(memory[0]['shared']); self.assertFalse(memory[0]['memory64'])
        self.assertEqual(memory[0]['maximum'], 2)

    def test_factory_dependencies_and_bootstrap_execution_are_rejected(self):
        for raw in (b'import "side-effect.mjs";\n' + FACTORY,
                    FACTORY + b'\ncallMain([]);\n', FACTORY + b'\nawait import("remote.mjs");\n'):
            assets = {**self.fixture.assets, FACTORY_PATH: raw}; records = copy.deepcopy(self.fixture.asset_records)
            records[FACTORY_PATH].update(sha256=sha(raw), bytes=len(raw))
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                self.inspect(evidence=self.with_assets(assets, records), assets=assets)

    def test_asset_roles_lookup_names_mode_and_measured_bounds_are_enforced(self):
        for mutation in (lambda value: value[WASM_PATH].update(bytes=True),
                         lambda value: value[WASM_PATH].update(lookup_name='../engine.wasm'),
                         lambda value: value[FACTORY_PATH].update(role='wasm'),
                         lambda value: value[WASM_PATH].update(mode=True)):
            records = copy.deepcopy(self.fixture.asset_records); mutation(records)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.inspect(evidence=self.with_assets(self.fixture.assets, records))
        for limits in (consumer.ConsumerLimits(max_factory_bytes=len(FACTORY)-1),
                       consumer.ConsumerLimits(max_wasm_bytes=len(self.fixture.assets[WASM_PATH])-1),
                       consumer.ConsumerLimits(max_reports_total_bytes=len(self.fixture.reports[REPORT_PATH])-1),
                       consumer.ConsumerLimits(max_notices_total_bytes=len(self.fixture.notices[NOTICE_PATH])-1)):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                self.inspect(limits=limits)
        self.inspect(limits=consumer.ConsumerLimits(max_factory_bytes=len(FACTORY),
                     max_wasm_bytes=len(self.fixture.assets[WASM_PATH]),
                     max_reports_total_bytes=len(self.fixture.reports[REPORT_PATH]),
                     max_notices_total_bytes=len(self.fixture.notices[NOTICE_PATH])))

    def test_full_group_data_and_interface_bounds_reject(self):
        fixture = EditorEngineFixture(self.base / 'data', data=True); group = self.group(fixture, 'data-group')
        with self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, **fixture.group_arguments(),
                limits=consumer.ConsumerLimits(max_data_total_bytes=len(fixture.assets[DATA_PATH])-1))
        path = INTERFACE_PATHS['editor_header']
        write(self.fixture.binary, path, b'x' * (65536 + 1))
        self.fixture.binary_manifest.update(manifest.tree_inventory(self.fixture.binary, 'engine-sdk.json'))
        write(self.fixture.binary, 'engine-sdk.json', encoded(self.fixture.binary_manifest))
        group = self.group(name='oversized-interface')
        with self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, **self.fixture.group_arguments())

    def test_full_group_postflight_snapshot_and_complete_stage_a_inventory_are_required(self):
        group = self.group(); original = sdk.group_snapshot; verify = sdk.verify_group; calls = []
        verified = False
        def complete(*args, **kwargs):
            nonlocal verified
            result = verify(*args, **kwargs); verified = True
            return result
        def changed(*args, **kwargs):
            value = original(*args, **kwargs); calls.append(value)
            return {**value, 'injected': 'f' * 64} if verified else value
        with mock.patch.object(sdk, 'group_snapshot', side_effect=changed), mock.patch.object(sdk, 'verify_group', side_effect=complete), self.assertRaisesRegex(ValueError, 'changed'):
            consumer.inspect_kernel_consumer(group, **self.fixture.group_arguments())
        self.assertGreaterEqual(len(calls), 3)
        (group / 'unlisted-file').write_bytes(b'not in closed group')
        with self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, **self.fixture.group_arguments())

    def test_invalid_stage_a_checksum_fails_before_wasm_or_factory_inspection(self):
        group = self.group(); checksum = sdk.group_names(self.fixture.pins()['recipe'])[2]
        (group / checksum).write_bytes(b'invalid checksum file\n')
        with mock.patch.object(consumer, 'scan_wasm', side_effect=AssertionError('Wasm scan before Stage A')), mock.patch.object(consumer, 'scan_factory', side_effect=AssertionError('factory scan before Stage A')), self.assertRaises(ValueError):
            consumer.inspect_kernel_consumer(group, **self.fixture.group_arguments())

    def test_consumer_never_executes_or_extracts_retained_inputs(self):
        group = self.group()
        with mock.patch('subprocess.run', side_effect=AssertionError('no subprocess')), mock.patch('subprocess.Popen', side_effect=AssertionError('no subprocess')), mock.patch('tarfile.TarFile.extractall', side_effect=AssertionError('no extraction')), mock.patch('tarfile.TarFile.extract', side_effect=AssertionError('no extraction')):
            result = consumer.inspect_kernel_consumer(group, **self.fixture.group_arguments())
        self.assertFalse(result.metadata['production_eligible'])


if __name__ == '__main__':
    unittest.main()
