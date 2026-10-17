#!/usr/bin/env python3
"""Pure source-contract checks; no engine, SDK, browser or kernel operations."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'abi/engine/document-actions-v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(name):
    return json.loads((DIRECTORY / name).read_bytes())


class DocumentActionContract(unittest.TestCase):
    def test_canonical_and_digest_closure(self):
        for name in ('binary-schema.json', 'action-ack.json', 'contract.json', 'catalog.json'):
            path = DIRECTORY / name
            value = json.loads(path.read_bytes())
            self.assertEqual(path.read_bytes(), (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode())
        contract, catalog = record('contract.json'), record('catalog.json')
        for key in ('base', 'document', 'editor', 'extension'):
            self.assertEqual(contract[key]['sha256'], digest(ROOT / contract[key]['path']))
        self.assertEqual(contract['schema_sha256'], digest(DIRECTORY / 'binary-schema.json'))
        self.assertEqual(contract['ack_schema_sha256'], digest(DIRECTORY / 'action-ack.json'))
        self.assertEqual(catalog['contract_sha256'], digest(DIRECTORY / 'contract.json'))
        self.assertEqual(catalog['extension_header_sha256'], contract['extension']['sha256'])
        header = (ROOT / contract['extension']['path']).read_text()
        for field, filename in (('SCHEMA', 'binary-schema.json'), ('ACK_SCHEMA', 'action-ack.json')):
            self.assertIn(f'#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_{field}_SHA256_HEX "{digest(DIRECTORY / filename)}"', header)
        self.assertNotIn(contract['extension']['sha256'], header)
        self.assertNotIn(catalog['contract_sha256'], header)

    def test_old_contract_bytes_stay_frozen(self):
        expected = {
            'include/foundation/appended/engine_provider.h': 'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d',
            'include/foundation/appended/engine_provider_document_v2.h': '7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626',
            'abi/engine/document-v2/contract.json': 'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298',
            'abi/engine/document-v2/catalog.json': '6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5',
            'abi/engine/document-v2/action-ack.json': '1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5',
            'abi/appended/editor-v1/contract.json': '0d43707e404979a38e0e8d7a7bc47042be95ae54216ed118a4de3314302b8c9c',
            'abi/appended/editor-v1/binary-schema.json': 'f2a6202056bd7fb6872539ba1e8806296ae6f6409ab2a21b9b581f19a4c7d4b1',
            'abi/appended/engine_editor_protocol.h': 'bdd9bf16765513be402481ab85dd596263fd4ac66a0dfc1dcc7ba5314ec85034',
        }
        for relative, wanted in expected.items():
            self.assertEqual(digest(ROOT / relative), wanted, relative)
        catalog = record('catalog.json')
        self.assertEqual(catalog['inherited_catalogs']['editor_v1'], digest(ROOT / 'abi/appended/editor-v1/catalog.json'))
        self.assertEqual(catalog['inherited_catalogs']['document_v2'], expected['abi/engine/document-v2/catalog.json'])

    def test_explicit_profile_and_inherited_operations(self):
        catalog = record('catalog.json')
        self.assertEqual(catalog['profile']['kind'], 4)
        self.assertEqual(catalog['profile']['provider_capabilities'], 2035 + 2048)
        self.assertEqual(catalog['profile'], record('contract.json')['profile'])
        self.assertEqual(catalog['profile']['name'], 'foundation-engine-copied4083-ndv2-editor-document-actions-v1')
        inherited = json.loads((ROOT / 'abi/appended/editor-v1/catalog.json').read_bytes())
        self.assertEqual(catalog['queries'], inherited['queries'])
        self.assertEqual(catalog['commands'][:-2], inherited['commands'])
        body, ack = catalog['commands'][-2:]
        self.assertEqual((body['operation'], body['capability'], body['maximum_input_bytes'], body['packet_kind'], body['reply_packet_kind']), (10, 2048, 128, 1, 2))
        self.assertEqual(body['schema_sha256'], digest(DIRECTORY / 'binary-schema.json'))
        self.assertEqual((ack['operation'], ack['original_action_operation'], ack['capability'], ack['maximum_input_bytes'], ack['result_bytes']), (11, 10, 2048, 8, 16))
        self.assertEqual(ack['schema_sha256'], digest(DIRECTORY / 'action-ack.json'))
        for old in (inherited, json.loads((ROOT / 'abi/engine/document-v2/catalog.json').read_bytes())):
            self.assertTrue(all(command['operation'] not in (10, 11) for command in old['commands']))
        header = (ROOT / record('contract.json')['extension']['path']).read_text()
        self.assertRegex(header, r'BIB_ENGINE_CAP_DOCUMENT_ACTIONS_V1 \(UINT64_C\(1\) << 11\)')
        self.assertIn('#define BIB_ENGINE_DOCUMENT_ACTIONS_V1_PROFILE_KIND 4u', header)

    def test_wire_offsets_and_publication_bound(self):
        schema = record('binary-schema.json')
        self.assertEqual(schema['header']['bytes'], 16)
        self.assertEqual(schema['request']['bytes'], 128)
        self.assertEqual([item['offset'] for item in schema['key']['fields']], [16, 24, 32, 40, 48, 56])
        self.assertEqual([item['offset'] for item in schema['request']['expected_version']], [64, 72, 80])
        self.assertEqual(schema['request']['action']['offset'], 88)
        self.assertEqual(schema['request']['union']['offset'], 96)
        self.assertEqual(schema['completion']['prefix_bytes'], 72)
        self.assertEqual([item['offset'] for item in schema['completion']['fields']], [64, 65, 66, 67, 68])
        self.assertEqual(schema['completion']['publication']['body_request_id'], 0)
        proof = schema['publication_size_proof']
        self.assertEqual(proof['ndv2_publication_payload_bytes'] + proof['completion_prefix_bytes'], proof['maximum_completion_bytes'])
        self.assertEqual(proof['maximum_completion_bytes'], 911577)
        self.assertLessEqual(proof['maximum_completion_bytes'], proof['provider_reply_capacity'])
        frozen = json.loads((ROOT / 'recipes/webkitwasm-document-v2/source/foundation/abi/engine/document-v2/schema-definition.json').read_bytes())
        publication = schema['completion']['publication']
        self.assertEqual(publication['records'], frozen['records'])
        self.assertEqual(publication['bounds'], frozen['bounds'])
        self.assertEqual(publication['primitives'], frozen['primitives'])
        self.assertEqual(publication['schema_sha256'], proof['source_schema_sha256'])

    def test_ack_family_and_metadata_only(self):
        ack = record('action-ack.json')
        self.assertEqual((ack['provider']['command'], ack['provider']['original_action_command'], ack['provider']['capability']), (11, 10, 2048))
        self.assertEqual((ack['request']['bytes'], ack['reply']['bytes']), (8, 16))
        self.assertEqual(ack['retention']['global_action_slots_across_form6_and_body10'], 1)
        self.assertFalse(ack['retention']['ack_of_ack'])
        self.assertEqual(ack['reply']['fields'][1]['values'], {'retired': 0, 'already_retired': 1, 'stale': 2})
        self.assertEqual(ack['sequence']['maximum_ordinary'] + 1, ack['sequence']['maximum_ack'])
        self.assertEqual(record('catalog.json')['retention']['ack11_action_family'], 10)
        self.assertEqual(record('catalog.json')['retention']['ack7_action_family'], 6)
        self.assertIn('no DOM getter', ack['effects'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
