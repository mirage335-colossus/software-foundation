#!/usr/bin/env python3
"""Pure native4083 value/interface tests; no provider, SDK or runtime is run."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_document_contract as document
import appended_engine_editor_contract as editor
import appended_engine_native_actions_contract as actions

TARGETS = (
    {'system': 'Linux', 'processor': 'x86_64', 'pointer_bits': 64, 'triple': 'x86_64-linux-gnu'},
    {'system': 'Linux', 'processor': 'aarch64', 'pointer_bits': 64, 'triple': 'aarch64-linux-gnu'},
    {'system': 'Windows', 'processor': 'x86_64', 'pointer_bits': 64, 'triple': 'x86_64-w64-mingw32'})


def profile(target=None):
    return actions.expected_engine_profile(kernel_target=TARGETS[0] if target is None else target,
        actions_profile='document-actions-v1', build_sha256='1' * 64, source_recipe_sha256='2' * 64)


def validate(value, target=None):
    return actions.validate_engine_profile(value, kernel_target=TARGETS[0] if target is None else target,
        actions_profile='document-actions-v1')


def descriptor(target=None):
    return actions.provider_contract(kernel_target=TARGETS[0] if target is None else target,
        actions_profile='document-actions-v1')


def interface_fixture():
    # These two original interfaces have retained logical destinations distinct
    # from their unchanged source-capsule locations in the checkout. Read only
    # these named original files, with no retained group/SDK discovery or scan.
    originals = {
        'document_schema': 'recipes/webkitwasm-document-v2/source/foundation/abi/engine/document-v2/schema-definition.json',
        'physical_catalog': 'recipes/webkitwasm-document-v2/overlays/physical/foundation/abi/engine/physical-v1/catalog.json'}
    interfaces = {path: (ROOT / originals.get(role, path)).read_bytes()
        for role, path in actions.INTERFACE_PATHS.items()}
    references = {role: {'path': path, 'sha256': actions._pins()[role]}
        for role, path in actions.INTERFACE_PATHS.items()}
    return references, interfaces


class NativeActionsContractTests(unittest.TestCase):
    def test_exact_native40_fields_supported_targets_and_independent_pins(self):
        self.assertEqual(len(actions.PROFILE_FIELDS), 40)
        self.assertEqual(len(set(actions.PROFILE_FIELDS)), 40)
        for target in TARGETS:
            with self.subTest(target=target):
                value = profile(target)
                self.assertEqual(set(value), set(actions.PROFILE_FIELDS))
                self.assertEqual(validate(value, target), value)
                self.assertEqual(value['kind'], 'foundation-native-engine-document-actions-v1')
                self.assertEqual(value['binding'], 'private-native')
                self.assertEqual(value['profile_kind'], 4)
                self.assertEqual(value['capabilities'], '4083')
                self.assertEqual(value['surface_capabilities'], '8255')
                self.assertEqual(value['editor_profile'], 'foundation-engine-copied2035-ndv2-editor-v1')
                self.assertEqual(value['build_sha256'], '1' * 64)
                self.assertEqual(value['source_recipe_sha256'], '2' * 64)
                self.assertNotIn('document_profile', value)
                self.assertNotIn('production_eligible', value)
                self.assertNotEqual(value['document_contract_sha256'], value['editor_contract_sha256'])
                self.assertNotEqual(value['editor_contract_sha256'], value['contract_sha256'])

    def test_every_fixed_profile_field_is_closed_and_cannot_be_retyped(self):
        value = profile()
        for field, original in value.items():
            with self.subTest(missing=field), self.assertRaises(actions.ContractError):
                validate({key: item for key, item in value.items() if key != field})
            if field in ('build_sha256', 'source_recipe_sha256'):
                # A different valid identity is a consumer cross-pin obligation,
                # not evidence which this pure expected-value leaf can reject.
                changed = dict(value); changed[field] = '3' * 64
                self.assertEqual(validate(changed)[field], '3' * 64)
                continue
            mutations = (True, float(original), str(original)) if type(original) is int else (None,)
            for replacement in mutations:
                changed = copy.deepcopy(value); changed[field] = replacement
                with self.subTest(field=field, replacement=replacement), self.assertRaises(actions.ContractError):
                    validate(changed)
        for field in ('browser', 'pthread', 'shared_memory', 'bridge_abi', 'document_profile', 'production_eligible'):
            with self.subTest(extra=field), self.assertRaises(actions.ContractError):
                validate({**value, field: False})

    def test_new_selectors_masks_and_old_contract_crossfeeds_never_enable_actions(self):
        for selector in ('pixel', 'physical', 'editor', '4083', '', True, None):
            with self.subTest(selector=selector), self.assertRaises(actions.ContractError):
                actions.expected_engine_profile(kernel_target=TARGETS[0], actions_profile=selector,
                    build_sha256='1' * 64, source_recipe_sha256='2' * 64)
        for original in (
            document.expected_engine_profile(document_profile='pixel', build_sha256='1' * 64, source_recipe_sha256='2' * 64),
            editor.expected_engine_profile(editor_profile='editor', build_sha256='1' * 64, source_recipe_sha256='2' * 64)):
            for changed in (original, {**original, 'capabilities': '4083'}, {**original, 'actions_profile': actions.PROFILE_NAME}):
                with self.subTest(kind=changed['kind']), self.assertRaises(actions.ContractError):
                    validate(changed)
        with self.assertRaises(document.ContractError):
            document.validate_engine_profile(profile(), document_profile='pixel')
        with self.assertRaises(editor.ContractError):
            editor.validate_engine_profile(profile(), editor_profile='editor')
        self.assertEqual(document.provider_contract(document_profile='pixel')['commands'][1]['operation'], 7)
        self.assertEqual(len(document.provider_contract(document_profile='pixel')['commands']), 2)
        self.assertEqual(len(editor.provider_contract(editor_profile='editor')['commands']), 7)

    def test_full_native_target_schema_and_independent_triple_join(self):
        for value in (None, 'Linux', {**TARGETS[0], 'extra': 1}, {**TARGETS[0], 'pointer_bits': True},
            {**TARGETS[0], 'pointer_bits': 32}, {**TARGETS[0], 'system': 'Darwin'},
            {**TARGETS[2], 'processor': 'aarch64'},
            {'system': 'Emscripten', 'processor': 'wasm32', 'pointer_bits': 32, 'triple': 'wasm32-emscripten'}):
            with self.subTest(target=value), self.assertRaises(actions.ContractError):
                actions.native_target(value)
        alternate = {**TARGETS[0], 'triple': 'x86_64-pc-linux-gnu'}
        self.assertEqual(actions.native_target(alternate), alternate)
        with self.assertRaises(actions.ContractError):
            validate(profile(alternate), TARGETS[0])

    def test_build_and_recipe_digests_are_nonzero_lowercase_exact64(self):
        for invalid in ('', 'a' * 63, 'a' * 65, 'A' * 64, '0' * 64, 'a' * 64 + '\n', 1, None):
            for field in ('build_sha256', 'source_recipe_sha256'):
                changed = profile(); changed[field] = invalid
                with self.subTest(field=field, value=invalid), self.assertRaises(actions.ContractError):
                    validate(changed)

    def test_independent_exact_operation_matrix_and_native_c_table_fields(self):
        query_expected = [(3, 48, 1048576, '512', document.DOCUMENT_SCHEMA_SHA256),
            (4, 236, 1048576, '32', editor.EDITOR_SCHEMA_SHA256)]
        command_expected = [
            (1, 160, 16, '16', '86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9'),
            (3, 32, 16, '64', 'eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9'),
            (5, 80, 16, '128', '6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3'),
            (6, 6246, 1048576, '1024', document.DOCUMENT_SCHEMA_SHA256),
            (7, 8, 16, '1024', document.ACTION_ACK_SCHEMA_SHA256),
            (8, 1048576, 1048576, '32', editor.EDITOR_SCHEMA_SHA256),
            (9, 1048576, 1048576, '32', editor.EDITOR_SCHEMA_SHA256),
            (10, 128, 1048576, '2048', actions.ACTIONS_SCHEMA_SHA256),
            (11, 8, 16, '2048', actions.ACTIONS_ACK_SCHEMA_SHA256)]
        fields = ('operation', 'maximum_input_bytes', 'required_reply_capacity', 'capability', 'schema_sha256')
        for target, numeric in zip(TARGETS, ((1, 1), (1, 2), (2, 1))):
            value = descriptor(target)
            self.assertEqual(value['target'], {'system': numeric[0], 'processor': numeric[1], 'pointer_bits': 64})
            self.assertEqual(value['provider_abi'], {'major': 1, 'minor': 1})
            self.assertEqual(value['host_abi'], {'major': 1, 'minor': 0})
            self.assertEqual(value['getter_maximum_minor'], 1)
            self.assertEqual(value['lifetime'], 1); self.assertEqual(value['maximum_starts'], 1)
            for name, expected in (('queries', query_expected), ('commands', command_expected)):
                self.assertEqual([tuple(row[key] for key in fields) for row in value[name]], expected)
                self.assertTrue(all(set(row) == set(fields) for row in value[name]))
            self.assertEqual(actions.validate_provider_contract(value, kernel_target=target,
                actions_profile='document-actions-v1'), value)

    def test_every_operation_field_order_and_schema_domain_is_closed(self):
        value = descriptor()
        for collection in ('queries', 'commands'):
            for index, row in enumerate(value[collection]):
                for field, original in row.items():
                    changed = copy.deepcopy(value)
                    changed[collection][index][field] = True if type(original) is int else '0' * 64
                    with self.subTest(collection=collection, index=index, field=field), self.assertRaises(actions.ContractError):
                        actions.validate_provider_contract(changed, kernel_target=TARGETS[0], actions_profile='document-actions-v1')
            for mutation in ('reverse', 'drop', 'duplicate'):
                changed = copy.deepcopy(value)
                if mutation == 'reverse': changed[collection].reverse()
                if mutation == 'drop': changed[collection].pop()
                if mutation == 'duplicate': changed[collection].append(copy.deepcopy(changed[collection][-1]))
                with self.subTest(mutation=mutation), self.assertRaises(actions.ContractError):
                    actions.validate_provider_contract(changed, kernel_target=TARGETS[0], actions_profile='document-actions-v1')
        changed = copy.deepcopy(value)
        changed['commands'][4]['schema_sha256'], changed['commands'][8]['schema_sha256'] = (
            changed['commands'][8]['schema_sha256'], changed['commands'][4]['schema_sha256'])
        with self.assertRaises(actions.ContractError):
            actions.validate_provider_contract(changed, kernel_target=TARGETS[0], actions_profile='document-actions-v1')

    def test_fixed_native_configuration_limits_and_distinct_evidence_kinds(self):
        self.assertEqual(actions.expected_actions_configuration(), {
            'kind': 'native-dso-private-document-actions-runtime-v1', 'actions_profile': actions.PROFILE_NAME,
            'profile_kind': 4, 'getter': 'bib_engine_get_provider_v1', 'getter_maximum_minor': 1,
            'inert_registration': True, 'public_exports': ['bib_engine_get_provider_v1'],
            'rendering': 'cpu', 'script_enabled': True, 'thread_model': 'native'})
        limits = dict(actions.PROVIDER_LIMITS)
        self.assertEqual(actions.validate_actions_provider_limits(limits), limits)
        self.assertEqual((limits['maximum_command_bytes'], limits['maximum_query_bytes'], limits['maximum_reply_bytes']),
            (1048576, 236, 1048576))
        for field, original in limits.items():
            for value in (True, float(original), original + 1, original - 1):
                with self.subTest(field=field, value=value), self.assertRaises(actions.ContractError):
                    actions.validate_actions_provider_limits({**limits, field: value})
        for fields in (dict(limits, unknown=1), {k: v for k, v in limits.items() if k != 'reserved'}):
            with self.assertRaises(actions.ContractError): actions.validate_provider_limits(fields)
        self.assertEqual(len(actions.BUILD_FIELDS), 13)
        self.assertEqual(actions.BUILD_KIND, 'foundation-neutral-engine-provider-native-document-actions-v1-build-v1')
        self.assertEqual(actions.PROOF_KIND, 'foundation-neutral-engine-provider-native-document-actions-v1-proof-v1')
        self.assertEqual(actions.RUNTIME_KIND, 'foundation-neutral-engine-native-document-actions-v1-runtime-evidence-v1')
        for field in ('pthread', 'bridge_abi', 'browser', 'wasm_facts', 'factory_policy'):
            self.assertNotIn(field, actions.BUILD_FIELDS + actions.PROOF_FIELDS + actions.RUNTIME_FIELDS)

    def test_runtime_checks_are_explicit_unique_native35_and_never_execution(self):
        checks = actions.runtime_checks(actions_profile='document-actions-v1')
        self.assertEqual(len(checks), 35); self.assertEqual(len(set(checks)), 35)
        self.assertEqual(checks[:14], actions.NATIVE_RUNTIME_CHECKS)
        self.assertEqual(checks[14:19], document.PHYSICAL_RUNTIME_CHECKS)
        self.assertEqual(checks[19:27], editor.EDITOR_RUNTIME_CHECKS)
        self.assertEqual(checks[27:], ('actions-profile-and-contract', 'actions-query3-owned-body-targets',
            'actions-command10-native-dispatch-readback', 'actions-command11-retained-family-ack',
            'actions-two-unwinds-passive-publication', 'actions-stale-identity-denial',
            'actions-context-replacement-no-replay', 'actions-outer-unknown-terminal-no-replay'))
        self.assertNotIn('factory-inert', checks)
        self.assertNotIn('document-bootstrap-worker64', checks)
        with self.assertRaises(actions.ContractError): actions.runtime_checks(actions_profile='pixel')

    def test_original_sixteen_interface_roles_paths_and_bytes_are_bound(self):
        references, interfaces = interface_fixture()
        self.assertEqual(len(references), 16)
        self.assertEqual(set(references), set(actions._pins()))
        self.assertEqual(references['physical_catalog']['path'], 'abi/engine/physical-v1/catalog.json')
        self.assertEqual(references['document_schema']['path'], 'abi/engine/document-v2/schema-definition.json')
        self.assertEqual(actions.validate_interface_bytes(references, interfaces, actions_profile='document-actions-v1'), interfaces)
        for role, reference in references.items():
            self.assertEqual(hashlib.sha256(interfaces[reference['path']]).hexdigest(), actions._pins()[role])
            for field, replacement in (('path', 'aliases/' + Path(reference['path']).name), ('sha256', 'f' * 64)):
                changed = copy.deepcopy(references); changed[role][field] = replacement
                with self.subTest(role=role, field=field), self.assertRaises(actions.ContractError):
                    actions.validate_interface_references(changed, actions_profile='document-actions-v1')
            changed = dict(interfaces); changed[reference['path']] += b'\n'
            with self.subTest(role=role), self.assertRaises(actions.ContractError):
                actions.validate_interface_bytes(references, changed, actions_profile='document-actions-v1')

    def test_interface_closure_requires_owned_bytes_and_exact_roles(self):
        references, interfaces = interface_fixture()
        path = next(iter(interfaces))
        for changed in (dict(interfaces, extra=b'x'), {k: v for k, v in interfaces.items() if k != path},
            {**interfaces, path: bytearray(interfaces[path])}, {**interfaces, path: memoryview(interfaces[path])},
            {**interfaces, path: b''}, {**interfaces, path: b'x' * (actions.MAX_INTERFACE_BYTES + 1)}):
            with self.subTest(paths=tuple(changed)), self.assertRaises(actions.ContractError):
                actions.validate_interface_bytes(references, changed, actions_profile='document-actions-v1')
        with self.assertRaises(actions.ContractError):
            actions.validate_interface_references({k: v for k, v in references.items() if k != 'document_schema'},
                actions_profile='document-actions-v1')

    def test_explicit_aliases_and_detached_value_results_perform_no_io(self):
        target = copy.deepcopy(TARGETS[0]); original = copy.deepcopy(target)
        with mock.patch('builtins.open', side_effect=AssertionError('Pure contract performed file IO')):
            result = actions.expected_actions_engine_profile(kernel_target=target,
                build_sha256='1' * 64, source_recipe_sha256='2' * 64)
            self.assertEqual(result, profile(target))
            self.assertEqual(actions.native_actions_target(target), original)
            self.assertEqual(actions.actions_provider_contract(kernel_target=target), descriptor(target))
            self.assertEqual(actions.expected_actions_configuration(), actions.expected_configuration(actions_profile='document-actions-v1'))
            self.assertEqual(actions.validate_actions_provider_limits(dict(actions.PROVIDER_LIMITS)), dict(actions.PROVIDER_LIMITS))
        target['triple'] = 'changed-after-selection'; result['target']['system'] = 'caller'
        self.assertEqual(profile()['target'], original)
        value = descriptor(); value['queries'][0]['operation'] = 99; value['commands'].clear()
        self.assertEqual(len(descriptor()['commands']), 9); self.assertEqual(descriptor()['queries'][0]['operation'], 3)
        config = actions.expected_actions_configuration(); config['public_exports'].clear()
        self.assertEqual(actions.expected_actions_configuration()['public_exports'], ['bib_engine_get_provider_v1'])
        pins = actions._pins(); pins.clear(); self.assertEqual(len(actions._pins()), 16)
        references, interfaces = interface_fixture()
        selected = actions.validate_interface_bytes(references, interfaces, actions_profile='document-actions-v1')
        selected.clear(); self.assertEqual(len(interfaces), 16)


if __name__ == '__main__':
    unittest.main()
