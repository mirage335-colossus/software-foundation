"""Pure source-contract checks; no provider, SDK, engine or kernel is run."""

import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'include/foundation/appended/engine_provider.h'
EXTENSION = ROOT / 'include/foundation/appended/engine_provider_document_v2.h'
PROFILE = ROOT / 'gui/shared/engine_document_profile.hpp'
CONTRACT_DIR = ROOT / 'abi/engine/document-v2'
BASE_SHA256 = 'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d'
NDV2_SHA256 = 'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d'
PHYSICAL_CATALOG_SHA256 = 'd244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('ascii')


class EngineDocumentContractTests(unittest.TestCase):
    def setUp(self):
        self.extension = EXTENSION.read_text(encoding='ascii')
        self.profile = PROFILE.read_text(encoding='ascii')
        self.ack = json.loads((CONTRACT_DIR / 'action-ack.json').read_bytes())
        self.catalog = json.loads((CONTRACT_DIR / 'catalog.json').read_bytes())
        self.contract = json.loads((CONTRACT_DIR / 'contract.json').read_bytes())

    def macro_digest(self, name):
        matches = re.findall(r'^#define ' + re.escape(name) + r' "([0-9a-f]{64})"$',
                             self.extension, re.MULTILINE)
        self.assertEqual(len(matches), 1, name)
        return matches[0]

    def profile_digest(self, name):
        matches = re.findall(r'\b' + re.escape(name) + r' = detail::digest\("([0-9a-f]{64})"\);',
                             self.profile)
        self.assertEqual(len(matches), 1, name)
        return matches[0]

    def test_canonical_json_has_one_exact_encoding(self):
        for name in ('action-ack.json', 'catalog.json', 'contract.json'):
            with self.subTest(name=name):
                path = CONTRACT_DIR / name
                self.assertEqual(path.read_bytes(), canonical(json.loads(path.read_bytes())))

    def test_legacy_base_header_and_composite_binding(self):
        self.assertEqual(sha256(BASE), BASE_SHA256)
        self.assertEqual(self.macro_digest('BIB_ENGINE_DOCUMENT_V2_BASE_HEADER_SHA256_HEX'), BASE_SHA256)
        self.assertEqual(self.contract['base'], {
            'path': 'include/foundation/appended/engine_provider.h', 'sha256': BASE_SHA256})
        self.assertEqual(self.contract['extension'], {
            'path': 'include/foundation/appended/engine_provider_document_v2.h', 'sha256': sha256(EXTENSION)})
        self.assertEqual(set(self.contract), {'base', 'extension', 'canonical', 'kind', 'schema_version'})
        self.assertEqual(self.profile_digest('kExtensionHeaderSha256'), sha256(EXTENSION))
        self.assertEqual(self.profile_digest('kContractSha256'), sha256(CONTRACT_DIR / 'contract.json'))
        self.assertNotEqual(sha256(EXTENSION), sha256(CONTRACT_DIR / 'contract.json'))

    def test_hash_bindings_form_an_acyclic_contract(self):
        ack_hash = sha256(CONTRACT_DIR / 'action-ack.json')
        catalog_hash = sha256(CONTRACT_DIR / 'catalog.json')
        contract_hash = sha256(CONTRACT_DIR / 'contract.json')
        self.assertEqual(self.macro_digest('BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX'), ack_hash)
        self.assertEqual(self.macro_digest('BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX'), NDV2_SHA256)
        self.assertEqual(self.profile_digest('kCatalogSha256'), catalog_hash)
        self.assertEqual(self.profile_digest('kPhysicalCatalogSha256'), PHYSICAL_CATALOG_SHA256)
        for digest in (sha256(EXTENSION), catalog_hash, contract_hash):
            self.assertNotIn(digest, self.extension)
        self.assertNotIn(catalog_hash, (CONTRACT_DIR / 'catalog.json').read_text())
        self.assertNotIn(contract_hash, (CONTRACT_DIR / 'contract.json').read_text())
        self.assertNotIn(contract_hash, (CONTRACT_DIR / 'catalog.json').read_text())

    def test_provider_minor_one_host_minor_zero_and_exact_catalog(self):
        self.assertEqual(self.catalog['status'], 'source-contract-only-no-runtime-advertisement')
        provider = self.catalog['provider_abi']
        self.assertEqual((provider['major'], provider['minor'], provider['minimum_getter_maximum_minor']), (1, 1, 1))
        self.assertEqual(self.catalog['host_abi'], {'major': 1, 'minor': 0, 'table_layout': 'BibEngineHostV1-unchanged'})
        query, = self.catalog['queries']
        form, ack = self.catalog['commands']
        self.assertEqual((query['operation'], query['capability'], query['maximum_input_bytes'], query['required_reply_capacity']), (3, 512, 48, 1048576))
        self.assertEqual((form['operation'], form['capability'], form['maximum_input_bytes'], form['required_reply_capacity']), (6, 1024, 6246, 1048576))
        self.assertEqual((ack['operation'], ack['capability'], ack['maximum_input_bytes'], ack['required_reply_capacity'], ack['result_bytes']), (7, 1024, 8, 16, 16))
        self.assertEqual(query['schema_sha256'], NDV2_SHA256)
        self.assertEqual(form['schema_sha256'], NDV2_SHA256)
        self.assertEqual(ack['schema_sha256'], sha256(CONTRACT_DIR / 'action-ack.json'))
        pixel, physical = self.catalog['profiles']
        self.assertEqual((pixel['name'], pixel['base_capabilities'], pixel['provider_capabilities'], pixel['physical_input_catalog_sha256']),
                         ('foundation-engine-copied1795-ndv2-v1', 259, 259 | 512 | 1024, None))
        self.assertEqual((physical['name'], physical['base_capabilities'], physical['provider_capabilities'], physical['physical_input_catalog_sha256']),
                         ('foundation-engine-copied2003-ndv2-v1', 467, 467 | 512 | 1024, PHYSICAL_CATALOG_SHA256))

    def test_copied_capacities_include_metadata_and_actual_ack_payload(self):
        limits = self.catalog['limits']
        self.assertEqual(limits['fkb1_receipt_bytes'], 80)
        self.assertEqual(limits['query_copied_result_prefix_bytes'], 16)
        self.assertEqual(limits['command_copied_result_prefix_bytes'], 24)
        self.assertEqual(limits['query_complete_reply_capacity'], 80 + 16 + 1048576)
        self.assertEqual(limits['form_complete_reply_capacity'], 80 + 24 + 1048576)
        self.assertEqual(limits['ack_complete_reply_capacity'], 80 + 24 + 16)
        self.assertEqual(limits['service_maximum_bytes_unchanged'], 1048576)
        self.assertTrue(limits['guest_abi_unchanged'])

    def test_ack_is_explicit_bounded_metadata_with_distinct_status_domains(self):
        self.assertEqual(self.ack['request']['payload_bytes'], 8)
        self.assertEqual(self.ack['reply']['bytes'], 16)
        self.assertEqual({key: self.ack['reply'][key] for key in ('provider_status', 'disposition', 'handled', 'bytes_written')},
                         {'provider_status': 0, 'disposition': 1, 'handled': 0, 'bytes_written': 16})
        self.assertEqual(self.ack['reply']['fields'], [
            {'name': 'original_action_sequence', 'offset': 0, 'type': 'u64le', 'minimum': 1, 'maximum': 2**64 - 2},
            {'name': 'code', 'offset': 8, 'type': 'u32le', 'values': {'retired': 0, 'already_retired': 1, 'stale': 2}},
            {'name': 'reserved', 'offset': 12, 'type': 'u32le', 'value': 0}])
        lifetime = self.ack['lifetime']
        self.assertEqual((lifetime['retained_action_slots'], lifetime['successful_ack_tombstones'], lifetime['latest_ack_reply_slots']), (1, 1, 1))
        self.assertFalse(lifetime['ack_of_ack'])
        self.assertEqual(lifetime['exact_request_retry'], 'while-original-success-tombstone-or-latest-ack-reply-key-is-retained-return-identical-cached-bytes-without-native-entry-or-high-water-change')
        self.assertEqual(lifetime['fresh_latest_success_duplicate'], 'already_retired-without-clearing-another-action')
        self.assertEqual(lifetime['stale_owner_policy'], 'retain-original-owned-result-and-do-not-assume-native-retirement')
        self.assertEqual(lifetime['effects'], 'metadata-retirement-only-no-dom-registry-or-host-callbacks')
        order = self.ack['admission']['order']
        self.assertLess(order.index('reserve-complete-sixteen-byte-reply'), order.index('admit-fresh-global-sequence'))
        replay = 'match-retained-exact-ack-receipt-before-current-document-high-water-or-exhaustion-checks'
        self.assertLess(order.index(replay), order.index('admit-fresh-global-sequence'))
        self.assertEqual(self.ack['admission']['full_action_slot'], 'does-not-block-ack')
        self.assertEqual(self.ack['admission']['uncached_old_sequence'], {
            'provider_status': -5, 'disposition': 0, 'bytes_written': 0,
            'effects': 'none', 'high_water': 'unchanged'})
        self.assertEqual(lifetime['successful_ack_tombstone_contents'], [
            'exact-original-action-native-identity-and-sequence',
            'original-retirement-ack-full-request-key',
            'original-retirement-ack-code-zero-result-bytes'])
        self.assertEqual(lifetime['successful_ack_tombstone_replacement'],
                         'only-new-retirement-code-zero-replaces;fresh-duplicate-code-one-never-rewrites-original-success')
        self.assertEqual(self.ack['admission']['old_document'],
                         'full-original-native-identity-must-match-retained-action-or-latest-retirement-proof-for-code-zero-or-one;fresh-well-formed-unmatched-identity-returns-stale-code-two')

    def test_new_sequence_headroom_does_not_change_legacy_policy(self):
        policy = self.catalog['sequence_policy']
        self.assertEqual((policy['maximum_ordinary'], policy['maximum_ack']), (2**64 - 2, 2**64 - 1))
        self.assertTrue(policy['legacy_high_water_unchanged'])
        self.assertTrue(policy['one_application_source'])
        self.assertTrue(policy['preserve_exact_outer_sequence'])
        self.assertTrue(self.catalog['replay']['new_profile_only'])
        self.assertFalse(self.catalog['replay']['ack_of_ack'])
        self.assertEqual(self.ack['lifetime']['maximum_ordinary_sequence'], policy['maximum_ordinary'])
        self.assertEqual(self.ack['lifetime']['maximum_ack_sequence'], policy['maximum_ack'])
        self.assertEqual(self.ack['request']['fields'][0]['maximum'], policy['maximum_ordinary'])


if __name__ == '__main__':
    unittest.main()
