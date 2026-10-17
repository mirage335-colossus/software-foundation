#!/usr/bin/env python3
"""Pure explicit editor2035 facts; existing document profiles stay unchanged.

This module reads no files and executes no provider. Eligible retained evidence
is admitted independently by the editor consumer, never by a profile flag.
"""
import base64
import binascii
import hashlib
import re
from types import MappingProxyType

import appended_engine_document_contract as document

ContractError = document.ContractError
canonical_json = document.canonical_json
strict_json = document.strict_json
json_copy = document.json_copy
require_fields = document.require_fields
validate_sha256 = document.validate_sha256

PROFILE_KIND = 'foundation-copied-engine-editor-v1'
PROFILE_NAME = 'foundation-engine-copied2035-ndv2-editor-v1'
BINDING = 'copied-owner-bridge/direct-worker-editor-v1'
PROOF_KIND = 'foundation-neutral-engine-provider-editor-v1-proof-v1'
BUILD_KIND = 'foundation-neutral-engine-provider-editor-v1-build-v1'
RUNTIME_KIND = 'foundation-neutral-engine-editor-v1-runtime-evidence-v1'
SCOPE = 'retained-editor-v1-consumer-byte-and-static-contract-only'
EMBEDDED_SCOPE = 'embedded-retained-editor-v1-consumer-byte-and-static-contract-only'
BASE_HEADER_SHA256 = document.BASE_HEADER_SHA256
DOCUMENT_HEADER_SHA256 = document.EXTENSION_HEADER_SHA256
DOCUMENT_CONTRACT_SHA256 = document.CONTRACT_SHA256
DOCUMENT_CATALOG_SHA256 = document.DOCUMENT_CATALOG_SHA256
DOCUMENT_SCHEMA_SHA256 = document.DOCUMENT_SCHEMA_SHA256
ACTION_ACK_SCHEMA_SHA256 = document.ACTION_ACK_SCHEMA_SHA256
PHYSICAL_CATALOG_SHA256 = document.PHYSICAL_CATALOG_SHA256
EDITOR_HEADER_SHA256 = 'bdd9bf16765513be402481ab85dd596263fd4ac66a0dfc1dcc7ba5314ec85034'
CONTRACT_SHA256 = '0d43707e404979a38e0e8d7a7bc47042be95ae54216ed118a4de3314302b8c9c'
EDITOR_CATALOG_SHA256 = '34fadacf563a00918255e4dc94b196bf0dc5c8ed57c7165e3da1e5fdd4d06bb8'
EDITOR_SCHEMA_SHA256 = 'f2a6202056bd7fb6872539ba1e8806296ae6f6409ab2a21b9b581f19a4c7d4b1'
PROFILE_NAMES = MappingProxyType({'editor': PROFILE_NAME})
CAPABILITIES = MappingProxyType({'editor': '2035'})
MAX_INTERFACE_BYTES = document.MAX_INTERFACE_BYTES
MAX_INTERFACES_BYTES = 10 * MAX_INTERFACE_BYTES
MAX_DOCUMENT_BYTES = document.MAX_DOCUMENT_BYTES
PROOF_FIELDS = document.PROOF_FIELDS
BUILD_FIELDS = document.BUILD_FIELDS
RUNTIME_FIELDS = document.RUNTIME_FIELDS
EVIDENCE_FIELDS = document.EVIDENCE_FIELDS
BOOTSTRAP_CHECKS = document.BOOTSTRAP_CHECKS
EDITOR_RUNTIME_CHECKS = (
    'editor-profile-and-surface2', 'editor-query4-owned-projection',
    'editor-command8-native-readback', 'editor-command9-native-revocation',
    'editor-full-worker-target-key', 'editor-pending-form-service-barriers',
    'editor-composition-focus-retirement', 'editor-unknown-terminal-no-replay')
INTERFACE_PATHS = MappingProxyType({
    'base_header': document.INTERFACE_PATHS['base_header'],
    'document_header': document.INTERFACE_PATHS['extension_header'],
    'document_contract': document.INTERFACE_PATHS['contract'],
    'document_catalog': document.INTERFACE_PATHS['document_catalog'],
    'action_ack_schema': document.INTERFACE_PATHS['action_ack_schema'],
    'physical_catalog': 'abi/engine/physical-input-catalog.json',
    'editor_header': 'abi/appended/engine_editor_protocol.h',
    'editor_contract': 'abi/appended/editor-v1/contract.json',
    'editor_catalog': 'abi/appended/editor-v1/catalog.json',
    'editor_schema': 'abi/appended/editor-v1/binary-schema.json',
})


def _pins():
    pins = {'base_header': BASE_HEADER_SHA256, 'document_header': DOCUMENT_HEADER_SHA256,
        'document_contract': DOCUMENT_CONTRACT_SHA256, 'document_catalog': DOCUMENT_CATALOG_SHA256,
        'action_ack_schema': ACTION_ACK_SCHEMA_SHA256, 'physical_catalog': PHYSICAL_CATALOG_SHA256,
        'editor_header': EDITOR_HEADER_SHA256, 'editor_contract': CONTRACT_SHA256,
        'editor_catalog': EDITOR_CATALOG_SHA256, 'editor_schema': EDITOR_SCHEMA_SHA256}
    for name, value in pins.items():
        validate_sha256(value, 'frozen editor interface ' + name, nonzero=True)
    return pins


def editor_selector(value):
    if type(value) is not str or value != 'editor':
        raise ContractError('Editor profile must be explicitly editor')
    return value


def expected_engine_profile(*, editor_profile, build_sha256, source_recipe_sha256):
    editor_selector(editor_profile)
    _pins()
    return {'schema_version': 1, 'kind': PROFILE_KIND, 'target': 'browser-wasm32', 'binding': BINDING,
        'pointer_bits': 32, 'pthread': False, 'shared_memory': False, 'bridge_abi': 65536,
        'capabilities': '2035', 'contract_sha256': CONTRACT_SHA256,
        'build_sha256': validate_sha256(build_sha256, 'provider build', nonzero=True),
        'source_recipe_sha256': validate_sha256(source_recipe_sha256, 'source recipe', nonzero=True),
        'provider_abi_major': 1, 'provider_abi_minor': 1, 'host_abi_major': 1, 'host_abi_minor': 0,
        'editor_profile': PROFILE_NAME, 'base_header_sha256': BASE_HEADER_SHA256,
        'document_header_sha256': DOCUMENT_HEADER_SHA256, 'document_contract_sha256': DOCUMENT_CONTRACT_SHA256,
        'document_catalog_sha256': DOCUMENT_CATALOG_SHA256, 'physical_catalog_sha256': PHYSICAL_CATALOG_SHA256,
        'editor_header_sha256': EDITOR_HEADER_SHA256, 'editor_catalog_sha256': EDITOR_CATALOG_SHA256,
        'editor_schema_sha256': EDITOR_SCHEMA_SHA256, 'document_schema_sha256': DOCUMENT_SCHEMA_SHA256,
        'action_ack_schema_sha256': ACTION_ACK_SCHEMA_SHA256, 'viewport_width': 800, 'viewport_height': 600,
        'surface_protocol_version': 2, 'surface_capabilities': '8255', 'mouse_input_version': 1,
        'key_mapping_version': 1, 'editor_protocol_version': 1, 'display_scale': 1,
        'editor_query_max_bytes': 236, 'editor_reply_capacity': 1048576, 'editor_command_max_bytes': 1048576}


def validate_engine_profile(value, *, editor_profile):
    editor_selector(editor_profile)
    value = json_copy(value, 'editor engine profile')
    if type(value) is not dict:
        raise ContractError('Expected editor engine profile object')
    expected = expected_engine_profile(editor_profile=editor_profile,
        build_sha256=value.get('build_sha256'), source_recipe_sha256=value.get('source_recipe_sha256'))
    if canonical_json(value) != canonical_json(expected):
        raise ContractError('Editor engine profile differs from the explicit editor2035 contract')
    return value


def provider_contract(*, editor_profile):
    editor_selector(editor_profile)
    _pins()
    descriptor = document.provider_contract(document_profile='physical')
    descriptor['queries'].append({'operation': 4, 'maximum_input_bytes': 236,
        'required_reply_capacity': 1048576, 'capability': '32', 'schema_sha256': EDITOR_SCHEMA_SHA256})
    descriptor['commands'] = [
        {'operation': operation, 'maximum_input_bytes': maximum, 'required_reply_capacity': 16,
         'capability': capability, 'schema_sha256': schema}
        for operation, maximum, capability, schema in (
            (1, 160, '16', '86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9'),
            (3, 32, '64', 'eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9'),
            (5, 80, '128', '6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3'))
    ] + descriptor['commands'] + [
        {'operation': operation, 'maximum_input_bytes': 1048576, 'required_reply_capacity': 1048576,
         'capability': '32', 'schema_sha256': EDITOR_SCHEMA_SHA256} for operation in (8, 9)]
    return descriptor


def validate_provider_contract(value, *, editor_profile):
    value = json_copy(value, 'editor provider contract')
    if canonical_json(value) != canonical_json(provider_contract(editor_profile=editor_profile)):
        raise ContractError('Editor provider ABI/target/lifetime/operation contract differs')
    return value


def expected_configuration(*, editor_profile):
    editor_selector(editor_profile)
    return {'profile': 'browser-wasm32-cpu-direct-owner-editor-v1',
        'modularized': True, 'esm': True, 'auto_main': False, 'pthread': False, 'shared_memory': False,
        'fixed_viewport_width': 800, 'fixed_viewport_height': 600, 'editor_profile': PROFILE_NAME}


def runtime_checks(*, editor_profile):
    editor_selector(editor_profile)
    return document.runtime_checks(document_profile='physical') + EDITOR_RUNTIME_CHECKS


def validate_interface_references(value, *, editor_profile):
    editor_selector(editor_profile)
    value = json_copy(value, 'editor interface references')
    require_fields(value, tuple(INTERFACE_PATHS), 'editor interface reference roles')
    pins, seen = _pins(), set()
    for role, reference in value.items():
        require_fields(reference, ('path', 'sha256'), 'editor interface reference')
        if reference['path'] != INTERFACE_PATHS[role] or reference['path'].casefold() in seen:
            raise ContractError('Aliased or noncanonical editor interface path')
        seen.add(reference['path'].casefold())
        if reference['sha256'] != pins[role]:
            raise ContractError('Editor interface pin differs: ' + role)
    return value


def validate_interface_bytes(references, interfaces, *, editor_profile):
    references = validate_interface_references(references, editor_profile=editor_profile)
    if not hasattr(interfaces, 'items'):
        raise ContractError('Expected owned editor interface byte mapping')
    interfaces = dict(interfaces.items())
    if set(interfaces) != {item['path'] for item in references.values()}:
        raise ContractError('Editor interface byte closure differs')
    total = 0
    for raw in interfaces.values():
        if type(raw) is not bytes or not 1 <= len(raw) <= MAX_INTERFACE_BYTES:
            raise ContractError('Invalid/oversized editor interface bytes')
        total += len(raw)
        if total > MAX_INTERFACES_BYTES:
            raise ContractError('Editor interfaces exceed aggregate bound')
    for role, reference in references.items():
        raw = interfaces[reference['path']]
        if hashlib.sha256(raw).hexdigest() != reference['sha256']:
            raise ContractError('Editor interface bytes differ: ' + role)
        if reference['path'].endswith('.json'):
            value = strict_json(raw, 'editor interface', maximum=MAX_INTERFACE_BYTES)
            expected = canonical_json(value)
            if role in ('editor_contract', 'editor_catalog'):
                # These independently pinned new documents use compact JSON
                # without a final LF; the older document interfaces keep theirs.
                expected = expected[:-1]
            # The separately frozen binary schema is human-readable JSON. Its
            # exact original bytes are still pinned above; never reconstruct it.
            if type(value) is not dict or role not in ('physical_catalog', 'editor_schema') and expected != raw:
                raise ContractError('Editor interface JSON is not a canonical object')
    return interfaces


def validate_provider_observation(value, *, editor_profile):
    value = json_copy(value, 'editor provider observation')
    require_fields(value, ('getter_maximum_minor', 'contract'), 'editor provider observation')
    if type(value['getter_maximum_minor']) is not int or value['getter_maximum_minor'] != 1:
        raise ContractError('Editor getter must request exact maximum_minor1')
    validate_provider_contract(value['contract'], editor_profile=editor_profile)
    return value


def validate_facts_observation(value, *, editor_profile, engine_profile):
    profile = validate_engine_profile(engine_profile, editor_profile=editor_profile)
    value = json_copy(value, 'engine editor facts observation')
    require_fields(value, ('export', 'signature', 'observed_output', 'observed_bytes', 'observed_result'),
                   'engine editor facts observation')
    if (value['export'] != 'bib_engine_wasm_editor_facts_v1'
            or canonical_json(value['signature']) != canonical_json({'params': ['i32', 'i32'], 'results': ['i32']})):
        raise ContractError('Missing exact editor facts export/signature')
    encoded = value['observed_output']
    if type(encoded) is not str or len(encoded) > ((4095 + 2) // 3) * 4:
        raise ContractError('Invalid/oversized engine editor facts output')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ContractError('Invalid engine editor facts base64') from error
    if base64.b64encode(raw).decode('ascii') != encoded:
        raise ContractError('Noncanonical engine editor facts base64')
    if (type(value['observed_bytes']) is not int or value['observed_bytes'] != len(raw)
            or not 1 <= len(raw) <= 4095 or b'\0' in raw):
        raise ContractError('Editor facts measured length/NUL differs')
    parsed = strict_json(raw, 'engine editor facts output', maximum=4095)
    validate_engine_profile(parsed, editor_profile=editor_profile)
    if canonical_json(parsed) != canonical_json(profile) or canonical_json(parsed) != canonical_json(value['observed_result']):
        raise ContractError('Editor facts output differs from actual selected profile')
    return value


def validate_bootstrap(value, *, editor_profile, engine_profile):
    profile = validate_engine_profile(engine_profile, editor_profile=editor_profile)
    value = json_copy(value, 'engine editor bootstrap')
    require_fields(value, ('worker_epoch', 'engine_facts', 'engine_configure', 'marker_before', 'marker_after',
        'describe_profile', 'first_start_worker_epoch', 'checks'), 'engine editor bootstrap')
    worker = value['worker_epoch']
    if (type(worker) is not str or re.fullmatch(r'[1-9][0-9]{0,19}', worker) is None or int(worker) >= 1 << 64
            or value['first_start_worker_epoch'] != worker):
        raise ContractError('Editor bootstrap requires the exact nonzero full Worker epoch')
    validate_facts_observation(value['engine_facts'], editor_profile=editor_profile, engine_profile=profile)
    configure = value['engine_configure']
    require_fields(configure, ('export', 'signature', 'worker_lo', 'worker_hi', 'observed_result'),
                   'engine editor configure observation')
    if (configure['export'] != 'bib_engine_wasm_editor_configure_v1'
            or canonical_json(configure['signature']) != canonical_json({'params': ['i32', 'i32'], 'results': ['i32']})
            or type(configure['observed_result']) is not int or configure['observed_result'] != 0):
        raise ContractError('Editor configure export/signature/result differs')
    if any(type(configure[key]) is not int or not 0 <= configure[key] < 1 << 32 for key in ('worker_lo', 'worker_hi')):
        raise ContractError('Invalid editor Worker half')
    if configure['worker_lo'] | (configure['worker_hi'] << 32) != int(worker):
        raise ContractError('Editor configure lost full Worker identity')
    if (type(value['marker_before']) is not int or value['marker_before'] != 0
            or type(value['marker_after']) is not int or value['marker_after'] != 65536
            or canonical_json(value['describe_profile']) != canonical_json(profile)):
        raise ContractError('Editor bootstrap marker/configuration/DESCRIBE order differs')
    require_fields(value['checks'], BOOTSTRAP_CHECKS, 'engine editor bootstrap checks')
    if any(type(status) is not str or status not in ('passed', 'failed', 'not-run') for status in value['checks'].values()):
        raise ContractError('Invalid engine editor bootstrap check status')
    return value
