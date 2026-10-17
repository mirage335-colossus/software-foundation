#!/usr/bin/env python3
"""Pure explicit document-v2 contract facts; no provider is enabled here.

This module reads no files, executes no factory and makes no runtime-eligibility
decision. The legacy copied259/467 schemas and canonical base header stay exact.
"""
import base64
import binascii
import hashlib
import json
import math
import re
from types import MappingProxyType


class ContractError(ValueError):
    """A value is outside the explicitly selected document-v2 contract."""


PROFILE_KIND = 'foundation-copied-engine-document-v2'
BINDING = 'copied-owner-bridge/direct-worker-document-v2'
PROOF_KIND = 'foundation-neutral-engine-provider-document-v2-proof-v1'
BUILD_KIND = 'foundation-neutral-engine-provider-document-v2-build-v1'
RUNTIME_KIND = 'foundation-neutral-engine-document-v2-runtime-evidence-v1'
SCOPE = 'retained-document-v2-consumer-byte-and-static-contract-only'
EMBEDDED_SCOPE = 'embedded-retained-document-v2-consumer-byte-and-static-contract-only'
BASE_HEADER_SHA256 = 'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d'
EXTENSION_HEADER_SHA256 = '7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626'
CONTRACT_SHA256 = 'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298'
DOCUMENT_CATALOG_SHA256 = '6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5'
DOCUMENT_SCHEMA_SHA256 = 'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d'
ACTION_ACK_SCHEMA_SHA256 = '1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5'
PHYSICAL_CATALOG_SHA256 = 'd244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b'
PROFILE_NAMES = MappingProxyType({
    'pixel': 'foundation-engine-copied1795-ndv2-v1',
    'physical': 'foundation-engine-copied2003-ndv2-v1',
})
CAPABILITIES = MappingProxyType({'pixel': '1795', 'physical': '2003'})
PHYSICAL_FACTS = MappingProxyType({
    'command_catalog_sha256': PHYSICAL_CATALOG_SHA256,
    'surface_protocol_version': 1, 'surface_capabilities': '8225',
    'mouse_input_version': 1, 'key_mapping_version': 1, 'display_scale': 1,
})
INTERFACE_PATHS = MappingProxyType({
    'base_header': 'include/foundation/appended/engine_provider.h',
    'extension_header': 'include/foundation/appended/engine_provider_document_v2.h',
    'contract': 'abi/engine/document-v2/contract.json',
    'document_catalog': 'abi/engine/document-v2/catalog.json',
    'action_ack_schema': 'abi/engine/document-v2/action-ack.json',
})
INTERFACE_PINS = MappingProxyType({
    'base_header': BASE_HEADER_SHA256, 'extension_header': EXTENSION_HEADER_SHA256,
    'contract': CONTRACT_SHA256, 'document_catalog': DOCUMENT_CATALOG_SHA256,
    'action_ack_schema': ACTION_ACK_SCHEMA_SHA256,
    'physical_catalog': PHYSICAL_CATALOG_SHA256,
})
MAX_INTERFACE_BYTES = 64 * 1024
MAX_INTERFACES_BYTES = 6 * MAX_INTERFACE_BYTES
MAX_DOCUMENT_BYTES = 32 * 1024 * 1024
PROOF_FIELDS = ('schema_version', 'kind', 'recipe_id', 'sources_sha256',
                'provider_build', 'engine_profile', 'assets', 'wasm_facts',
                'factory_policy', 'runtime_evidence', 'interfaces')
BUILD_FIELDS = ('schema_version', 'kind', 'target', 'toolchain', 'options',
                'source_recipe_sha256', 'source_inputs_sha256',
                'contract_header_sha256', 'binding', 'configuration',
                'capabilities', 'bridge_abi', 'provider_contract')
RUNTIME_FIELDS = ('schema_version', 'kind', 'scope', 'status', 'recipe_id',
                  'provider_build_sha256', 'assets_sha256', 'target',
                  'paired_sdk_sha256', 'engine_profile', 'browser', 'checks',
                  'provider_observation', 'bootstrap')
EVIDENCE_FIELDS = ('binary_manifest', 'source_manifest', 'recipe', 'proof',
                   'provider_build', 'runtime', 'reports', 'interfaces')
BOOTSTRAP_CHECKS = ('facts_before_configure', 'configure_once',
                    'configure_before_describe', 'describe_before_start',
                    'no_host_callbacks_during_facts_or_configure', 'one_process_start')
BASE_RUNTIME_CHECKS = ('factory-inert', 'copied-describe',
    'offline-entry-resource-load', 'native-service-result-and-ack',
    'outside-engine-owner-pump', 'opaque-raster-frame', 'worker-failure-close',
    'separate-heaps-copied-bridge')
DOCUMENT_RUNTIME_CHECKS = ('document-bootstrap-worker64',
    'document-provider-minor-and-catalog', 'document-query3-owned-snapshot',
    'document-form6-native-readback', 'document-action-replay-and-ack7',
    'document-navigation-and-stale-lease', 'document-outer-unknown-terminal-no-replay')
PHYSICAL_RUNTIME_CHECKS = ('raw-key-location-altgraph', 'mouse-five-buttons-context-cancel',
    'input-context-navigation-retirement', 'native-effect-input-admission',
    'document-current-physical-provider')


def document_selector(value):
    if type(value) is not str or value not in PROFILE_NAMES:
        raise ContractError('Document profile must be explicitly pixel or physical')
    return value


def _json_value(value):
    if value is None or type(value) is bool or type(value) is int:
        return
    if type(value) is str:
        try:
            value.encode('utf-8')
        except UnicodeError as error:
            raise ContractError('Invalid Unicode in document JSON') from error
        return
    if type(value) is float:
        if math.isfinite(value):
            return
        raise ContractError('Nonfinite document JSON number')
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ContractError('Document JSON keys must be strings')
            _json_value(key)
            _json_value(item)
        return
    raise ContractError('Expected ordinary document JSON values')


def canonical_json(value):
    """The canonical contract encoding, retaining integer/bool distinctions."""
    try:
        _json_value(value)
        return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                           separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
    except (RecursionError, OverflowError, TypeError) as error:
        raise ContractError('Invalid/overdeep document JSON') from error


def strict_json(raw, label='document', *, maximum=MAX_DOCUMENT_BYTES):
    """Parse owned UTF-8 without BOM removal, duplicate keys or nonfinite data."""
    if type(maximum) is not int or maximum < 0:
        raise ContractError('Invalid document JSON byte bound')
    try:
        if type(raw) is bytes:
            if len(raw) > maximum:
                raise ContractError(label + ' exceeds byte bound')
            source = raw.decode('utf-8')
        elif type(raw) is str:
            if len(raw.encode('utf-8')) > maximum:
                raise ContractError(label + ' exceeds byte bound')
            source = raw
        else:
            raise ContractError('Expected owned ' + label + ' JSON bytes or text')

        def pairs(items):
            result = {}
            for key, item in items:
                if key in result:
                    raise ContractError('Duplicate ' + label + ' JSON key: ' + key)
                result[key] = item
            return result

        def constant(value):
            raise ContractError('Invalid ' + label + ' JSON constant: ' + value)

        value = json.loads(source, object_pairs_hook=pairs, parse_constant=constant)
        _json_value(value)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as error:
        raise ContractError('Invalid ' + label + ' JSON') from error


def json_copy(value, label='document'):
    return strict_json(canonical_json(value), label)


def require_fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ContractError('Invalid ' + label + ' fields')


def validate_sha256(value, label='SHA256', *, nonzero=False):
    if (type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None
            or nonzero and value == '0' * 64):
        raise ContractError('Invalid ' + label + ' SHA256')
    return value


def expected_engine_profile(*, document_profile, build_sha256, source_recipe_sha256):
    selected = document_selector(document_profile)
    result = {
        'schema_version': 1, 'kind': PROFILE_KIND, 'target': 'browser-wasm32',
        'binding': BINDING, 'pointer_bits': 32, 'pthread': False,
        'shared_memory': False, 'bridge_abi': 65536,
        'capabilities': CAPABILITIES[selected], 'contract_sha256': CONTRACT_SHA256,
        'build_sha256': validate_sha256(build_sha256, 'provider build', nonzero=True),
        'source_recipe_sha256': validate_sha256(source_recipe_sha256, 'source recipe', nonzero=True),
        'provider_abi_major': 1, 'provider_abi_minor': 1,
        'host_abi_major': 1, 'host_abi_minor': 0, 'document_profile': PROFILE_NAMES[selected],
        'base_header_sha256': BASE_HEADER_SHA256, 'extension_header_sha256': EXTENSION_HEADER_SHA256,
        'document_catalog_sha256': DOCUMENT_CATALOG_SHA256,
        'document_schema_sha256': DOCUMENT_SCHEMA_SHA256,
        'action_ack_schema_sha256': ACTION_ACK_SCHEMA_SHA256,
        'viewport_width': 800, 'viewport_height': 600,
    }
    if selected == 'physical':
        result.update(PHYSICAL_FACTS)
    return result


def validate_engine_profile(value, *, document_profile):
    selected = document_selector(document_profile)
    value = json_copy(value, 'document engine profile')
    if type(value) is not dict:
        raise ContractError('Expected document engine profile object')
    expected = expected_engine_profile(document_profile=selected,
        build_sha256=value.get('build_sha256'),
        source_recipe_sha256=value.get('source_recipe_sha256'))
    if canonical_json(value) != canonical_json(expected):
        raise ContractError('Document engine profile differs from explicit ' + selected + ' contract')
    return value


def provider_contract(*, document_profile):
    document_selector(document_profile)
    return {
        'provider_abi': {'major': 1, 'minor': 1},
        'host_abi': {'major': 1, 'minor': 0}, 'getter_maximum_minor': 1,
        'target': {'system': 3, 'processor': 3, 'pointer_bits': 32},
        'lifetime': 1, 'maximum_starts': 1,
        'queries': [{'operation': 3, 'maximum_input_bytes': 48,
            'required_reply_capacity': 1048576, 'capability': '512',
            'schema_sha256': DOCUMENT_SCHEMA_SHA256}],
        'commands': [
            {'operation': 6, 'maximum_input_bytes': 6246,
             'required_reply_capacity': 1048576, 'capability': '1024',
             'schema_sha256': DOCUMENT_SCHEMA_SHA256},
            {'operation': 7, 'maximum_input_bytes': 8,
             'required_reply_capacity': 16, 'capability': '1024',
             'schema_sha256': ACTION_ACK_SCHEMA_SHA256}],
    }


def validate_provider_contract(value, *, document_profile):
    value = json_copy(value, 'document provider contract')
    if canonical_json(value) != canonical_json(provider_contract(document_profile=document_profile)):
        raise ContractError('Document provider ABI/target/lifetime/operation contract differs')
    return value


def expected_configuration(*, document_profile):
    selected = document_selector(document_profile)
    return {'profile': 'browser-wasm32-cpu-direct-owner-document-v2',
        'modularized': True, 'esm': True, 'auto_main': False, 'pthread': False,
        'shared_memory': False, 'fixed_viewport_width': 800, 'fixed_viewport_height': 600,
        'document_profile': PROFILE_NAMES[selected]}


def runtime_checks(*, document_profile):
    selected = document_selector(document_profile)
    return BASE_RUNTIME_CHECKS + DOCUMENT_RUNTIME_CHECKS + (PHYSICAL_RUNTIME_CHECKS if selected == 'physical' else ())


def _path(value):
    # This is pure lexical validation. The consumer also applies Stage-A's path
    # and inventory checks and validates actual member modes before reading.
    if (type(value) is not str or not value or '\\' in value or value.startswith('/')
            or any(part in ('', '.', '..') or part.endswith((' ', '.')) for part in value.split('/'))
            or any(ord(c) < 32 or ord(c) >= 127 or c in ':<>"|?*' for c in value)):
        raise ContractError('Invalid portable interface member path')
    for part in value.split('/'):
        stem = part.split('.')[0].upper()
        if stem in {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                    *('COM' + str(i) for i in range(1, 10)),
                    *('LPT' + str(i) for i in range(1, 10))}:
            raise ContractError('Reserved interface member path')
    return value


def validate_interface_references(value, *, document_profile):
    selected = document_selector(document_profile)
    value = json_copy(value, 'document interface references')
    roles = tuple(INTERFACE_PATHS) + (('physical_catalog',) if selected == 'physical' else ())
    require_fields(value, roles, 'document interface reference roles')
    seen = set()
    for role, reference in value.items():
        require_fields(reference, ('path', 'sha256'), 'document interface reference')
        path = _path(reference['path'])
        if path.casefold() in seen or role in INTERFACE_PATHS and path != INTERFACE_PATHS[role]:
            raise ContractError('Aliased or noncanonical document interface path')
        seen.add(path.casefold())
        if reference['sha256'] != INTERFACE_PINS[role]:
            raise ContractError('Document interface pin differs: ' + role)
    return value


def validate_interface_bytes(references, interfaces, *, document_profile):
    references = validate_interface_references(references, document_profile=document_profile)
    if not hasattr(interfaces, 'items'):
        raise ContractError('Expected owned interface byte mapping')
    interfaces = dict(interfaces.items())
    if set(interfaces) != {item['path'] for item in references.values()}:
        raise ContractError('Document interface byte closure differs')
    total = 0
    for raw in interfaces.values():
        if type(raw) is not bytes or not 1 <= len(raw) <= MAX_INTERFACE_BYTES:
            raise ContractError('Invalid/oversized document interface bytes')
        total += len(raw)
        if total > MAX_INTERFACES_BYTES:
            raise ContractError('Document interfaces exceed aggregate bound')
    result = {}
    for role, reference in references.items():
        raw = interfaces[reference['path']]
        if hashlib.sha256(raw).hexdigest() != reference['sha256']:
            raise ContractError('Document interface bytes differ: ' + role)
        if role in ('contract', 'document_catalog', 'action_ack_schema', 'physical_catalog'):
            value = strict_json(raw, 'document interface', maximum=MAX_INTERFACE_BYTES)
            if type(value) is not dict:
                raise ContractError('Document interface JSON must be an object')
            if role != 'physical_catalog' and canonical_json(value) != raw:
                raise ContractError('Document interface JSON is not canonical')
        result[reference['path']] = raw
    return result


def validate_provider_observation(value, *, document_profile):
    value = json_copy(value, 'document provider observation')
    require_fields(value, ('getter_maximum_minor', 'contract'), 'document provider observation')
    if type(value['getter_maximum_minor']) is not int or value['getter_maximum_minor'] != 1:
        raise ContractError('Document getter must request exact maximum_minor1')
    validate_provider_contract(value['contract'], document_profile=document_profile)
    return value


def _unsigned(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ContractError('Invalid ' + label)
    return value


def _worker(value):
    if (type(value) is not str or re.fullmatch(r'[1-9][0-9]{0,19}', value) is None
            or int(value) >= 1 << 64):
        raise ContractError('Invalid nonzero full Worker epoch')
    return int(value)


def validate_facts_observation(value, *, document_profile, engine_profile):
    """Pure original bounded export observation, shared with future carrier tooling."""
    profile = validate_engine_profile(engine_profile, document_profile=document_profile)
    value = json_copy(value, 'engine document facts observation')
    require_fields(value, ('export', 'signature', 'observed_output', 'observed_bytes',
                           'observed_result'), 'engine document facts observation')
    if (value['export'] != 'bib_engine_wasm_document_facts_v1'
            or canonical_json(value['signature']) != canonical_json({'params': ['i32', 'i32'], 'results': ['i32']})):
        raise ContractError('Missing exact document facts export/signature')
    encoded = value['observed_output']
    if type(encoded) is not str or len(encoded) > ((4095 + 2) // 3) * 4:
        raise ContractError('Invalid/oversized engine document facts output')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ContractError('Invalid engine document facts base64') from error
    if base64.b64encode(raw).decode('ascii') != encoded:
        raise ContractError('Noncanonical engine document facts base64')
    if (type(value['observed_bytes']) is not int or value['observed_bytes'] != len(raw)
            or not 1 <= len(raw) <= 4095 or b'\0' in raw):
        raise ContractError('Document facts measured length/NUL differs')
    parsed = strict_json(raw, 'engine document facts output', maximum=4095)
    validate_engine_profile(parsed, document_profile=document_profile)
    if (canonical_json(parsed) != canonical_json(profile)
            or canonical_json(parsed) != canonical_json(value['observed_result'])):
        raise ContractError('Document facts output differs from actual selected profile')
    return value


def validate_bootstrap(value, *, document_profile, engine_profile):
    """Validate one original engine run, without requiring a Foundation host run."""
    profile = validate_engine_profile(engine_profile, document_profile=document_profile)
    value = json_copy(value, 'engine document bootstrap')
    require_fields(value, ('worker_epoch', 'engine_facts', 'engine_configure',
                           'marker_before', 'marker_after', 'describe_profile',
                           'first_start_worker_epoch', 'checks'), 'engine document bootstrap')
    worker = _worker(value['worker_epoch'])
    if value['first_start_worker_epoch'] != value['worker_epoch']:
        raise ContractError('Document bootstrap START Worker identity differs')
    validate_facts_observation(value['engine_facts'], document_profile=document_profile,
                               engine_profile=profile)
    configure = value['engine_configure']
    require_fields(configure, ('export', 'signature', 'worker_lo', 'worker_hi',
                               'observed_result'), 'engine document configure observation')
    if (configure['export'] != 'bib_engine_wasm_document_configure_v1'
            or canonical_json(configure['signature']) != canonical_json({'params': ['i32', 'i32'], 'results': ['i32']})
            or type(configure['observed_result']) is not int or configure['observed_result'] != 0):
        raise ContractError('Document configure export/signature/result differs')
    lo = _unsigned(configure['worker_lo'], (1 << 32) - 1, 'Worker low half')
    hi = _unsigned(configure['worker_hi'], (1 << 32) - 1, 'Worker high half')
    if (lo | (hi << 32)) != worker:
        raise ContractError('Document configure lost full Worker identity')
    if (type(value['marker_before']) is not int or value['marker_before'] != 0
            or type(value['marker_after']) is not int or value['marker_after'] != 65536):
        raise ContractError('Document bootstrap marker/configuration order differs')
    if canonical_json(value['describe_profile']) != canonical_json(profile):
        raise ContractError('Document bootstrap DESCRIBE differs from actual facts')
    require_fields(value['checks'], BOOTSTRAP_CHECKS, 'engine document bootstrap checks')
    if any(type(status) is not str or status not in ('passed', 'failed', 'not-run')
           for status in value['checks'].values()):
        raise ContractError('Invalid engine document bootstrap check status')
    return value
