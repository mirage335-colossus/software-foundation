"""Exact editor2035 value contracts; no provider, SDK or runtime is executed."""
import base64
import copy
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_document_contract as document
import appended_engine_editor_contract as contract


def profile():
    return contract.expected_engine_profile(editor_profile='editor',
        build_sha256='a' * 64, source_recipe_sha256='b' * 64)


def bootstrap(value):
    raw = contract.canonical_json(value)
    return {'worker_epoch': '18446744073709551614',
        'engine_facts': {'export': 'bib_engine_wasm_editor_facts_v1',
            'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
            'observed_output': base64.b64encode(raw).decode('ascii'),
            'observed_bytes': len(raw), 'observed_result': copy.deepcopy(value)},
        'engine_configure': {'export': 'bib_engine_wasm_editor_configure_v1',
            'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
            'worker_lo': 4294967294, 'worker_hi': 4294967295, 'observed_result': 0},
        'marker_before': 0, 'marker_after': 65536, 'describe_profile': copy.deepcopy(value),
        'first_start_worker_epoch': '18446744073709551614',
        'checks': {name: 'passed' for name in contract.BOOTSTRAP_CHECKS}}


class EditorContractTests(unittest.TestCase):
    def test_flat_profile_has_exact_independent_38_fields_and_2035_values(self):
        value = profile()
        self.assertEqual(len(value), 38)
        self.assertTrue(all(type(item) in (str, int, bool) for item in value.values()))
        self.assertEqual(value['kind'], 'foundation-copied-engine-editor-v1')
        self.assertEqual(value['binding'], 'copied-owner-bridge/direct-worker-editor-v1')
        self.assertEqual(value['editor_profile'], 'foundation-engine-copied2035-ndv2-editor-v1')
        self.assertEqual((value['capabilities'], value['surface_capabilities']), ('2035', '8255'))
        self.assertEqual((value['surface_protocol_version'], value['editor_protocol_version']), (2, 1))
        self.assertEqual((value['editor_query_max_bytes'], value['editor_command_max_bytes'], value['editor_reply_capacity']),
                         (236, 1048576, 1048576))
        self.assertIs(type(value['display_scale']), int)
        self.assertEqual(contract.validate_engine_profile(value, editor_profile='editor'), value)

    def test_every_missing_extra_or_changed_profile_fact_rejects(self):
        value = profile()
        for key in value:
            missing = dict(value)
            del missing[key]
            changed = dict(value)
            original = changed[key]
            changed[key] = not original if type(original) is bool else original + 1 if type(original) is int else original + 'x'
            for candidate in (missing, changed):
                with self.subTest(key=key, candidate=candidate), self.assertRaises(ValueError):
                    contract.validate_engine_profile(candidate, editor_profile='editor')
        with self.assertRaises(ValueError):
            contract.validate_engine_profile(dict(value, unexpected=0), editor_profile='editor')

    def test_editor_selection_is_explicit_and_never_a_document_profile_upgrade(self):
        for selected in (None, '', 'pixel', 'physical', 3, True):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                contract.validate_engine_profile(profile(), editor_profile=selected)
        for selected in ('pixel', 'physical'):
            old = document.expected_engine_profile(document_profile=selected,
                build_sha256='a' * 64, source_recipe_sha256='b' * 64)
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                contract.validate_engine_profile(old, editor_profile='editor')
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                document.validate_engine_profile(profile(), document_profile=selected)

    def test_profile_integer_and_pin_domains_are_exact(self):
        for key, value in (('surface_protocol_version', True), ('display_scale', 1.0),
                ('provider_abi_minor', '1'), ('capabilities', 2035), ('build_sha256', '0' * 64),
                ('source_recipe_sha256', 'B' * 64)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                contract.validate_engine_profile(dict(profile(), **{key: value}), editor_profile='editor')

    def test_provider_catalog_has_two_queries_and_seven_exact_commands(self):
        value = contract.provider_contract(editor_profile='editor')
        self.assertEqual([item['operation'] for item in value['queries']], [3, 4])
        self.assertEqual([item['operation'] for item in value['commands']], [1, 3, 5, 6, 7, 8, 9])
        self.assertNotIn(2, [item['operation'] for item in value['commands']])
        self.assertEqual(value['queries'][1], {'operation': 4, 'maximum_input_bytes': 236,
            'required_reply_capacity': 1048576, 'capability': '32', 'schema_sha256': contract.EDITOR_SCHEMA_SHA256})
        for item in value['commands'][-2:]:
            self.assertEqual((item['maximum_input_bytes'], item['required_reply_capacity'], item['capability']),
                             (1048576, 1048576, '32'))
        self.assertEqual(contract.validate_provider_contract(value, editor_profile='editor'), value)

    def test_mutated_provider_limits_schema_and_operation_order_reject(self):
        original = contract.provider_contract(editor_profile='editor')
        variants = []
        for path, replacement in ((('queries', 1, 'maximum_input_bytes'), 237),
                (('commands', 5, 'maximum_input_bytes'), 1048577), (('commands', 6, 'operation'), 2),
                (('queries', 1, 'schema_sha256'), document.DOCUMENT_SCHEMA_SHA256)):
            value = copy.deepcopy(original)
            value[path[0]][path[1]][path[2]] = replacement
            variants.append(value)
        value = copy.deepcopy(original)
        value['commands'].reverse()
        variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                contract.validate_provider_contract(value, editor_profile='editor')

    def test_canonical_editor_interfaces_match_actual_frozen_source_bytes(self):
        roles = ('editor_header', 'editor_contract', 'editor_catalog', 'editor_schema')
        pins = (contract.EDITOR_HEADER_SHA256, contract.CONTRACT_SHA256,
                contract.EDITOR_CATALOG_SHA256, contract.EDITOR_SCHEMA_SHA256)
        for role, expected in zip(roles, pins):
            raw = (ROOT / contract.INTERFACE_PATHS[role]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
            if role != 'editor_header':
                parsed = contract.strict_json(raw)
                self.assertIs(type(parsed), dict)
                if role != 'editor_schema':
                    self.assertEqual(contract.canonical_json(parsed)[:-1], raw)

    def test_editor_runtime_gates_add_to_all_existing_physical_document_checks(self):
        original = document.runtime_checks(document_profile='physical')
        checks = contract.runtime_checks(editor_profile='editor')
        self.assertEqual(checks[:len(original)], original)
        self.assertEqual(len(checks), len(set(checks)))
        self.assertEqual(checks[len(original):], contract.EDITOR_RUNTIME_CHECKS)
        self.assertIn('editor-command9-native-revocation', checks)
        self.assertIn('editor-unknown-terminal-no-replay', checks)

    def test_bootstrap_joins_both_worker_halves_actual_facts_and_describe(self):
        value = profile()
        observed = bootstrap(value)
        self.assertEqual(contract.validate_bootstrap(observed, editor_profile='editor', engine_profile=value), observed)
        for mutate in (
                lambda item: item['engine_configure'].__setitem__('worker_hi', 0),
                lambda item: item.__setitem__('first_start_worker_epoch', '4294967294'),
                lambda item: item.__setitem__('marker_before', 65536),
                lambda item: item['engine_configure'].__setitem__('export', 'bib_engine_wasm_document_configure_v1'),
                lambda item: item['engine_facts'].__setitem__('export', 'bib_engine_wasm_document_facts_v1'),
                lambda item: item['describe_profile'].__setitem__('capabilities', '2003')):
            changed = copy.deepcopy(observed)
            mutate(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                contract.validate_bootstrap(changed, editor_profile='editor', engine_profile=value)

    def test_facts_are_strict_owned_utf8_json_not_inferred_observation_values(self):
        value = profile()
        observed = bootstrap(value)['engine_facts']
        raw = contract.canonical_json(value)
        malformed = [b'\xef\xbb\xbf' + raw, raw[:-2] + b',"schema_version":1}\n',
                     raw + b'\0', raw.replace(b'"schema_version":1', b'"schema_version":NaN'),
                     raw.replace(b'"target":"browser-wasm32"', b'"target":"\\ud800"')]
        for payload in malformed:
            changed = copy.deepcopy(observed)
            changed.update(observed_output=base64.b64encode(payload).decode('ascii'), observed_bytes=len(payload))
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                contract.validate_facts_observation(changed, editor_profile='editor', engine_profile=value)


if __name__ == '__main__':
    unittest.main()
