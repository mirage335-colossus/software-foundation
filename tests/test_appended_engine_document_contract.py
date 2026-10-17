"""Pure document contract checks; no provider, factory, SDK or engine is run."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_document_contract as contract


PIXEL = {
    'schema_version': 1, 'kind': 'foundation-copied-engine-document-v2',
    'target': 'browser-wasm32', 'binding': 'copied-owner-bridge/direct-worker-document-v2',
    'pointer_bits': 32, 'pthread': False, 'shared_memory': False, 'bridge_abi': 65536,
    'capabilities': '1795',
    'contract_sha256': 'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298',
    'build_sha256': 'b' * 64, 'source_recipe_sha256': 'c' * 64,
    'provider_abi_major': 1, 'provider_abi_minor': 1, 'host_abi_major': 1,
    'host_abi_minor': 0, 'document_profile': 'foundation-engine-copied1795-ndv2-v1',
    'base_header_sha256': 'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d',
    'extension_header_sha256': '7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626',
    'document_catalog_sha256': '6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5',
    'document_schema_sha256': 'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d',
    'action_ack_schema_sha256': '1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5',
    'viewport_width': 800, 'viewport_height': 600,
}
PHYSICAL = dict(PIXEL, capabilities='2003',
    document_profile='foundation-engine-copied2003-ndv2-v1',
    command_catalog_sha256='d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b',
    surface_protocol_version=1, surface_capabilities='8225', mouse_input_version=1,
    key_mapping_version=1, display_scale=1)
PROVIDER = {
    'provider_abi': {'major': 1, 'minor': 1}, 'host_abi': {'major': 1, 'minor': 0},
    'getter_maximum_minor': 1, 'target': {'system': 3, 'processor': 3, 'pointer_bits': 32},
    'lifetime': 1, 'maximum_starts': 1,
    'queries': [{'operation': 3, 'maximum_input_bytes': 48, 'required_reply_capacity': 1048576,
        'capability': '512', 'schema_sha256': PIXEL['document_schema_sha256']}],
    'commands': [
        {'operation': 6, 'maximum_input_bytes': 6246, 'required_reply_capacity': 1048576,
         'capability': '1024', 'schema_sha256': PIXEL['document_schema_sha256']},
        {'operation': 7, 'maximum_input_bytes': 8, 'required_reply_capacity': 16,
         'capability': '1024', 'schema_sha256': PIXEL['action_ack_schema_sha256']}],
}
INTERFACES = {
    'base_header': {'path': 'include/foundation/appended/engine_provider.h',
                    'sha256': PIXEL['base_header_sha256']},
    'extension_header': {'path': 'include/foundation/appended/engine_provider_document_v2.h',
                         'sha256': PIXEL['extension_header_sha256']},
    'contract': {'path': 'abi/engine/document-v2/contract.json', 'sha256': PIXEL['contract_sha256']},
    'document_catalog': {'path': 'abi/engine/document-v2/catalog.json',
                         'sha256': PIXEL['document_catalog_sha256']},
    'action_ack_schema': {'path': 'abi/engine/document-v2/action-ack.json',
                          'sha256': PIXEL['action_ack_schema_sha256']},
}


def facts(profile, raw=None):
    raw = json.dumps(profile, indent=1).encode() if raw is None else raw
    return {'export': 'bib_engine_wasm_document_facts_v1',
            'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
            'observed_output': base64.b64encode(raw).decode(),
            'observed_bytes': len(raw), 'observed_result': copy.deepcopy(profile)}


def bootstrap(profile=PIXEL, worker=0xfedcba9876543210):
    return {'worker_epoch': str(worker), 'engine_facts': facts(profile),
            'engine_configure': {'export': 'bib_engine_wasm_document_configure_v1',
                'signature': {'params': ['i32', 'i32'], 'results': ['i32']},
                'worker_lo': worker & 0xffffffff, 'worker_hi': worker >> 32,
                'observed_result': 0},
            'marker_before': 0, 'marker_after': 65536,
            'describe_profile': copy.deepcopy(profile), 'first_start_worker_epoch': str(worker),
            'checks': {name: 'passed' for name in (
                'facts_before_configure', 'configure_once', 'configure_before_describe',
                'describe_before_start', 'no_host_callbacks_during_facts_or_configure',
                'one_process_start')}}


class DocumentContractTests(unittest.TestCase):
    def test_exact_literal_profiles_have_24_and_30_fields(self):
        for selected, value, count in (('pixel', PIXEL, 24), ('physical', PHYSICAL, 30)):
            with self.subTest(profile=selected):
                self.assertEqual(len(value), count)
                self.assertEqual(contract.validate_engine_profile(value, document_profile=selected), value)
                self.assertEqual(contract.expected_engine_profile(document_profile=selected,
                    build_sha256='b' * 64, source_recipe_sha256='c' * 64), value)
                owned = contract.validate_engine_profile(value, document_profile=selected)
                self.assertIsNot(owned, value)
                owned['capabilities'] = '0'
                self.assertNotEqual(owned, value)

    def test_selection_is_explicit_despite_shared_binding(self):
        self.assertEqual(PIXEL['binding'], PHYSICAL['binding'])
        for value, requested in ((PIXEL, 'physical'), (PHYSICAL, 'pixel')):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                contract.validate_engine_profile(value, document_profile=requested)
        for selected in (None, True, 1, '', '1795', 'Pixel', 'pixel ', 'none'):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                contract.document_selector(selected)
        with self.assertRaises(TypeError):
            contract.validate_engine_profile(PIXEL)

    def test_every_profile_field_is_required_exactly_and_typed(self):
        for selected, profile in (('pixel', PIXEL), ('physical', PHYSICAL)):
            for field, value in profile.items():
                for replacement in ('missing', None, 0 if type(value) in (str, bool) else True):
                    changed = dict(profile)
                    if replacement == 'missing':
                        del changed[field]
                    else:
                        changed[field] = replacement
                    with self.subTest(profile=selected, field=field, replacement=replacement), self.assertRaises(ValueError):
                        contract.validate_engine_profile(changed, document_profile=selected)
            with self.assertRaises(ValueError):
                contract.validate_engine_profile(dict(profile, enabled=True), document_profile=selected)

    def test_profile_rejects_legacy_minors_and_each_changed_fixed_fact(self):
        for field, value in PIXEL.items():
            if field in ('build_sha256', 'source_recipe_sha256'):
                continue
            changed = dict(PIXEL)
            changed[field] = not value if type(value) is bool else value + 1 if type(value) is int else value + 'x'
            with self.subTest(field=field), self.assertRaises(ValueError):
                contract.validate_engine_profile(changed, document_profile='pixel')
        for minor in (0, 2, 1.0):
            with self.subTest(minor=minor), self.assertRaises(ValueError):
                contract.validate_engine_profile(dict(PIXEL, provider_abi_minor=minor), document_profile='pixel')

    def test_dynamic_pins_are_nonzero_exact_lowercase_hashes(self):
        for field in ('build_sha256', 'source_recipe_sha256'):
            for value in ('0' * 64, 'F' * 64, 'f' * 63, 'f' * 65, ' f' + 'f' * 62, b'f' * 64):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    contract.validate_engine_profile(dict(PIXEL, **{field: value}), document_profile='pixel')
        self.assertEqual(contract.validate_sha256('0' * 64), '0' * 64)
        with self.assertRaises(ValueError):
            contract.validate_sha256('0' * 64, nonzero=True)

    def test_strict_json_rejects_nonstandard_text_without_coercion(self):
        for raw in (b'{"x":1,"x":2}', b'NaN', b'Infinity', b'-Infinity', b'1e999',
                    b'"\xff"', b'"\\ud800"', b'\xef\xbb\xbf{}', b'{"x":true,}',
                    '\ufeff{}', '"\udfff"'):
            with self.subTest(raw=repr(raw)), self.assertRaises(ValueError):
                contract.strict_json(raw)
        self.assertEqual(contract.strict_json(b' {"n":1,"b":true} \n'), {'n': 1, 'b': True})
        with self.assertRaises(ValueError):
            contract.strict_json(b'{}', maximum=1)
        for bound in (-1, True, 1.0):
            with self.assertRaises(ValueError):
                contract.strict_json(b'{}', maximum=bound)

    def test_canonical_json_is_sorted_lf_and_owns_nested_values(self):
        self.assertEqual(contract.canonical_json({'z': '\u00e9', 'a': [True, 1, 1.0]}),
                         b'{"a":[true,1,1.0],"z":"\\u00e9"}\n')
        for value in ({1: 'number-key'}, {'x': float('nan')}, {'x': ('tuple',)}, {'x': object()}):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                contract.canonical_json(value)
        original = {'a': [{'b': 4}]}
        copied = contract.json_copy(original)
        original['a'][0]['b'] = 9
        self.assertEqual(copied, {'a': [{'b': 4}]})

    def test_provider_contract_exact_native_sizes_abi_and_lifetime(self):
        for selected in ('pixel', 'physical'):
            self.assertEqual(contract.provider_contract(document_profile=selected), PROVIDER)
            self.assertEqual(contract.validate_provider_contract(PROVIDER, document_profile=selected), PROVIDER)
        self.assertEqual(80 + 16 + PROVIDER['queries'][0]['required_reply_capacity'], 1048672)
        self.assertEqual(80 + 24 + PROVIDER['commands'][0]['required_reply_capacity'], 1048680)
        self.assertEqual(80 + 24 + PROVIDER['commands'][1]['required_reply_capacity'], 120)
        for section, key, replacement in (
                ('provider_abi', 'minor', 0), ('host_abi', 'minor', 1),
                ('target', 'pointer_bits', 64), ('target', 'system', True)):
            value = copy.deepcopy(PROVIDER); value[section][key] = replacement
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                contract.validate_provider_contract(value, document_profile='pixel')
        for field in ('lifetime', 'maximum_starts', 'getter_maximum_minor'):
            for replacement in (True, 0, 2):
                value = copy.deepcopy(PROVIDER); value[field] = replacement
                with self.subTest(field=field, replacement=replacement), self.assertRaises(ValueError):
                    contract.validate_provider_contract(value, document_profile='pixel')

    def test_operation_facts_reject_unknown_and_altered_shapes(self):
        changes = (
            lambda v: v['queries'].append(copy.deepcopy(v['queries'][0])),
            lambda v: v['commands'].reverse(),
            lambda v: v['commands'][1].update(required_reply_capacity=0),
            lambda v: v['commands'][0].update(maximum_input_bytes=6247),
            lambda v: v['queries'][0].update(capability=512),
            lambda v: v['commands'][1].update(schema_sha256=PIXEL['document_schema_sha256']),
            lambda v: v.update(enabled=True),
        )
        for change in changes:
            value = copy.deepcopy(PROVIDER); change(value)
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.validate_provider_contract(value, document_profile='pixel')

    def test_configuration_and_runtime_checks_do_not_require_foundation_host(self):
        expected = {'profile': 'browser-wasm32-cpu-direct-owner-document-v2',
            'modularized': True, 'esm': True, 'auto_main': False, 'pthread': False,
            'shared_memory': False, 'fixed_viewport_width': 800, 'fixed_viewport_height': 600,
            'document_profile': 'foundation-engine-copied1795-ndv2-v1'}
        self.assertEqual(contract.expected_configuration(document_profile='pixel'), expected)
        pixel = contract.runtime_checks(document_profile='pixel')
        physical = contract.runtime_checks(document_profile='physical')
        self.assertEqual(len(pixel), 15)
        self.assertEqual(len(physical), 20)
        self.assertEqual(physical[:15], pixel)
        self.assertIn('document-current-physical-provider', physical)
        self.assertNotIn('document-owner-publication-before-ack', pixel)
        self.assertNotIn('kernel_configure_before_start', contract.BOOTSTRAP_CHECKS)
        self.assertEqual(len(set(physical)), len(physical))

    def test_interface_identity_is_actual_bytes_with_distinct_hash_roles(self):
        raw = {item['path']: (ROOT / item['path']).read_bytes() for item in INTERFACES.values()}
        self.assertEqual(contract.validate_interface_references(INTERFACES, document_profile='pixel'), INTERFACES)
        owned = contract.validate_interface_bytes(INTERFACES, raw, document_profile='pixel')
        for role, item in INTERFACES.items():
            with self.subTest(role=role):
                self.assertEqual(hashlib.sha256(owned[item['path']]).hexdigest(), item['sha256'])
        composite = json.loads(raw[INTERFACES['contract']['path']])
        self.assertEqual(composite['base'], INTERFACES['base_header'])
        self.assertEqual(composite['extension'], INTERFACES['extension_header'])
        self.assertNotEqual(INTERFACES['base_header']['sha256'], INTERFACES['contract']['sha256'])
        raw.clear()
        self.assertEqual(len(owned), 5)

    def test_interface_roles_paths_aliases_and_pins_are_closed(self):
        for role in INTERFACES:
            value = copy.deepcopy(INTERFACES); del value[role]
            with self.subTest(missing=role), self.assertRaises(ValueError):
                contract.validate_interface_references(value, document_profile='pixel')
        physical = copy.deepcopy(INTERFACES)
        physical['physical_catalog'] = {'path': 'native/physical-catalog.json',
                                       'sha256': PHYSICAL['command_catalog_sha256']}
        self.assertEqual(contract.validate_interface_references(physical, document_profile='physical'), physical)
        with self.assertRaises(ValueError):
            contract.validate_interface_references(physical, document_profile='pixel')
        for path in ('../catalog.json', '/catalog.json', 'a//catalog.json', 'a/./catalog.json',
                     'a\\catalog.json', 'CON.json', 'a/trailing.', 'a/\u00e9.json', 'a/\x00x',
                     INTERFACES['contract']['path'], INTERFACES['contract']['path'].upper()):
            value = copy.deepcopy(physical); value['physical_catalog']['path'] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                contract.validate_interface_references(value, document_profile='physical')
        for role in INTERFACES:
            value = copy.deepcopy(INTERFACES); value[role]['sha256'] = '0' * 64
            with self.subTest(pin=role), self.assertRaises(ValueError):
                contract.validate_interface_references(value, document_profile='pixel')

    def test_interface_bytes_bound_and_owned_closure_precede_hashing(self):
        raw = {item['path']: (ROOT / item['path']).read_bytes() for item in INTERFACES.values()}
        for change in (
                lambda v: v.pop(INTERFACES['base_header']['path']),
                lambda v: v.update(extra=b'ignored'),
                lambda v: v.update({INTERFACES['base_header']['path']: bytearray(b'not-owned')}),
                lambda v: v.update({INTERFACES['contract']['path']: b'{}\n'})):
            value = dict(raw); change(value)
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.validate_interface_bytes(INTERFACES, value, document_profile='pixel')
        raw[INTERFACES['base_header']['path']] = b'x' * (65536 + 1)
        with mock.patch.object(contract.hashlib, 'sha256', side_effect=AssertionError('oversized member was hashed')):
            with self.assertRaisesRegex(ValueError, 'oversized'):
                contract.validate_interface_bytes(INTERFACES, raw, document_profile='pixel')

    def test_provider_observation_requires_exact_getter_and_no_new_json_keys(self):
        value = {'getter_maximum_minor': 1, 'contract': copy.deepcopy(PROVIDER)}
        self.assertEqual(contract.validate_provider_observation(value, document_profile='pixel'), value)
        for change in (lambda v: v.update(getter_maximum_minor=True),
                       lambda v: v.update(getter_maximum_minor=0),
                       lambda v: v.update(enabled=True),
                       lambda v: v['contract']['host_abi'].update(minor=1)):
            bad = copy.deepcopy(value); change(bad)
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.validate_provider_observation(bad, document_profile='pixel')

    def test_bootstrap_preserves_high_bit_worker_and_independent_run_identity(self):
        for selected, profile in (('pixel', PIXEL), ('physical', PHYSICAL)):
            for worker in (1, (1 << 63) + 0x12345678, (1 << 64) - 1):
                value = bootstrap(profile, worker)
                owned = contract.validate_bootstrap(value, document_profile=selected, engine_profile=profile)
                self.assertEqual(owned, value)
                self.assertIsNot(owned['engine_facts'], value['engine_facts'])
        # Independently observed runs are each joined internally, not compared
        # through a mutable global/default Worker chosen by this pure codec.
        self.assertNotEqual(bootstrap(worker=1)['worker_epoch'], bootstrap(worker=2)['worker_epoch'])

    def test_bootstrap_rejects_each_identity_order_export_and_status_mismatch(self):
        changes = (
            lambda v: v.update(worker_epoch='0'), lambda v: v.update(worker_epoch=str(1 << 64)),
            lambda v: v.update(worker_epoch='01'), lambda v: v.update(worker_epoch=True),
            lambda v: v.update(first_start_worker_epoch='2'),
            lambda v: v['engine_configure'].update(worker_lo=0),
            lambda v: v['engine_configure'].update(worker_hi=True),
            lambda v: v['engine_configure'].update(worker_hi=1 << 32),
            lambda v: v['engine_configure'].update(observed_result=-8),
            lambda v: v['engine_configure'].update(export='bib_engine_wasm_bridge_v1'),
            lambda v: v['engine_configure']['signature'].update(params=['i64']),
            lambda v: v.update(marker_before=65536), lambda v: v.update(marker_before=False),
            lambda v: v.update(marker_after=0), lambda v: v['describe_profile'].update(host_abi_minor=1),
            lambda v: v['checks'].update(configure_once=True),
            lambda v: v['checks'].update(kernel_configure_before_start='passed'),
            lambda v: v['checks'].pop('describe_before_start'),
            lambda v: v.update(owner='invented'),
        )
        for change in changes:
            value = bootstrap(); change(value)
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.validate_bootstrap(value, document_profile='pixel', engine_profile=PIXEL)
        for status in ('failed', 'not-run'):
            value = bootstrap(); value['checks']['configure_once'] = status
            self.assertEqual(contract.validate_bootstrap(value, document_profile='pixel', engine_profile=PIXEL), value)

    def test_facts_observation_preserves_actual_json_bytes_and_measured_bounds(self):
        raw = json.dumps(PIXEL).encode()
        at_limit = raw + b' ' * (4095 - len(raw))
        observed = facts(PIXEL, at_limit)
        self.assertEqual(contract.validate_facts_observation(observed,
            document_profile='pixel', engine_profile=PIXEL), observed)
        for raw in (at_limit + b' ', b'\0' + raw, b'\xef\xbb\xbf' + raw, b'\xff' + raw, b'{}'):
            with self.subTest(raw=raw[:10]), self.assertRaises(ValueError):
                contract.validate_facts_observation(facts(PIXEL, raw), document_profile='pixel', engine_profile=PIXEL)
        for change in (lambda v: v.update(observed_bytes=True),
                       lambda v: v.update(observed_bytes=v['observed_bytes'] + 1),
                       lambda v: v.update(observed_output=v['observed_output'] + '\n'),
                       lambda v: v.update(export='gui_web_engine_document_describe_v1'),
                       lambda v: v['observed_result'].update(build_sha256='d' * 64)):
            value = facts(PIXEL); change(value)
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.validate_facts_observation(value, document_profile='pixel', engine_profile=PIXEL)

    def test_noncanonical_base64_pad_bits_are_not_another_observation_identity(self):
        raw = json.dumps(PIXEL).encode()
        raw += b' ' * ((1 - len(raw)) % 3)
        value = facts(PIXEL, raw)
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        text = value['observed_output']
        self.assertTrue(text.endswith('=='))
        value['observed_output'] = text[:-3] + alphabet[alphabet.index(text[-3]) + 1] + '=='
        self.assertEqual(base64.b64decode(value['observed_output']), raw)
        with self.assertRaisesRegex(ValueError, 'Noncanonical'):
            contract.validate_facts_observation(value, document_profile='pixel', engine_profile=PIXEL)


if __name__ == '__main__':
    unittest.main()
