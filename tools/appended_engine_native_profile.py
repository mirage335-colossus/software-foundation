#!/usr/bin/env python3
"""Verify one native retained group and emit its private C++20 load plan.

No provider, compiler, inspection program, SDK or build is executed here.  The
public renderer always repeats the complete eligible-group consumer admission.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile

import appended_engine_document_contract as contract
import appended_engine_manifest as manifest


HEADER_DIRECTORY = 'appended-engine-native-profile'
ACTIONS_HEADER_DIRECTORY = 'appended-engine-native-actions-profile'
HEADER_NAME = 'appended_engine_compiled_native_profile.hpp'
GENERATED_NOTICE = '// Generated from the fully verified eligible native retained-engine group.'
SYNTHETIC_NOTICE = '// Synthetic syntax fixture only; never retained-engine eligibility.'
SELECTION_PREFIX = '// Native document profile: '
ACTIONS_SELECTION_PREFIX = '// Native document actions profile: '
PAYLOAD_PREFIX = '// Native generated payload SHA256: '
METADATA_PREFIX = '// Native generated metadata: '
METADATA_CHUNK_BYTES = 4096
MAX_HEADER_BYTES = 64 * 1024 * 1024
NATIVE_SCOPE = 'retained-native-document-consumer-byte-and-static-contract-only'
PROFILE_KIND = 'foundation-native-engine-document-v2'
PROFILE_FIELDS = ('schema_version', 'kind', 'binding', 'target', 'document_profile',
    'provider_abi_major', 'provider_abi_minor', 'host_abi_major', 'host_abi_minor',
    'lifetime', 'maximum_starts', 'viewport_width', 'viewport_height', 'capabilities',
    'base_header_sha256', 'extension_header_sha256', 'contract_sha256',
    'document_catalog_sha256', 'document_schema_sha256', 'action_ack_schema_sha256',
    'build_sha256', 'source_recipe_sha256')


def _consumer():
    # Delayed only so a private syntax fixture can be rendered while the new
    # independent consumer is being prepared. Public admission has no fallback.
    return importlib.import_module('appended_engine_native_consumer')


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Invalid native compiled-profile ' + label + ' fields')


def _digest(value, label, nonzero=True):
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{64}', value) or nonzero and value == '0' * 64:
        raise ValueError('Invalid native compiled-profile SHA256: ' + label)
    return value


def _path(value):
    # The loader uses the same ASCII portable namespace, including all devices.
    if type(value) is not str or not value or len(value) > 4096 or value.startswith('/') or '\\' in value or any(ord(char) < 32 or ord(char) >= 127 or char in ':<>"|?*' for char in value):
        raise ValueError('Invalid portable native retained path')
    for part in value.split('/'):
        if not part or part in ('.', '..') or part.endswith((' ', '.')):
            raise ValueError('Invalid portable native retained path component')
        stem = part.split('.', 1)[0].rstrip(' ').lower()
        if stem in {'con', 'prn', 'aux', 'nul', 'conin$', 'conout$',
                    *('com' + str(number) for number in range(1, 10)),
                    *('lpt' + str(number) for number in range(1, 10))}:
            raise ValueError('Reserved native retained path component')
    return value


def _target(value):
    manifest.target_contract(value)
    pair = (value['system'], value['processor'])
    targets = {('Linux', 'x86_64'): ('BIB_ENGINE_TARGET_LINUX', 'BIB_ENGINE_CPU_X86_64'),
               ('Linux', 'aarch64'): ('BIB_ENGINE_TARGET_LINUX', 'BIB_ENGINE_CPU_AARCH64'),
               ('Windows', 'x86_64'): ('BIB_ENGINE_TARGET_WINDOWS', 'BIB_ENGINE_CPU_X86_64')}
    if pair not in targets or type(value['pointer_bits']) is not int or value['pointer_bits'] != 64:
        raise ValueError('Native compiled profile requires an admitted native 64-bit target')
    return targets[pair]


def _metadata(value):
    if type(value) is not dict:
        raise ValueError('Expected ordinary native consumer metadata')
    # Validate only emitted fields here. Complete retained evidence admission is
    # exclusively the public verify_kernel_consumer call, never this renderer.
    profile = value.get('engine_profile')
    _fields(profile, PROFILE_FIELDS, 'engine profile')
    if profile['document_profile'] != contract.PROFILE_NAMES['pixel']:
        raise ValueError('Native compiled document profile initially admits pixel only')
    expected = {'schema_version': 1, 'kind': PROFILE_KIND, 'binding': 'private-native',
        'provider_abi_major': 1, 'provider_abi_minor': 1, 'host_abi_major': 1, 'host_abi_minor': 0,
        'lifetime': 1, 'maximum_starts': 1, 'viewport_width': 800, 'viewport_height': 600,
        'capabilities': '1795', 'base_header_sha256': contract.BASE_HEADER_SHA256,
        'extension_header_sha256': contract.EXTENSION_HEADER_SHA256, 'contract_sha256': contract.CONTRACT_SHA256,
        'document_catalog_sha256': contract.DOCUMENT_CATALOG_SHA256,
        'document_schema_sha256': contract.DOCUMENT_SCHEMA_SHA256,
        'action_ack_schema_sha256': contract.ACTION_ACK_SCHEMA_SHA256}
    if any(type(profile[key]) is not type(item) or profile[key] != item for key, item in expected.items()):
        raise ValueError('Native compiled profile differs from exact ABI1.1 pixel1795 facts')
    target_macros = _target(profile['target'])
    pins = {key: _digest(value.get(key), key) for key in
            ('recipe_id', 'binary_manifest_sha256', 'proof_sha256', 'runtime_sha256', 'provider_build_sha256')}
    if _digest(profile['source_recipe_sha256'], 'source recipe') != pins['recipe_id'] or _digest(profile['build_sha256'], 'provider build') != pins['provider_build_sha256']:
        raise ValueError('Native compiled profile differs from independently verified pins')
    entry = _path(value.get('provider_entry'))
    if profile['target']['system'] == 'Windows':
        if not entry.endswith('.dll'):
            raise ValueError('Native Windows provider must name an exact DLL')
    elif not re.search(r'\.so(?:\.[0-9]+)*\Z', entry):
        raise ValueError('Native Linux provider must name an exact shared library')
    inventory = value.get('inventory')
    if type(inventory) is not list or not 1 <= len(inventory) <= 65536:
        raise ValueError('Complete bounded native binary inventory required')
    records, aliases, previous = {}, set(), ''
    for item in inventory:
        _fields(item, ('path', 'kind', 'mode', 'bytes', 'sha256'), 'inventory record')
        path = _path(item['path'])
        if path <= previous or path.lower() in aliases:
            raise ValueError('Native binary inventory must be sorted and case-unambiguous')
        if type(item['mode']) is not int or type(item['bytes']) is not int or not 0 <= item['bytes'] <= ((1 << 64) - 1) // 8:
            raise ValueError('Invalid native binary inventory mode/size')
        if item['kind'] == 'directory':
            if item['mode'] != 0o755 or item['bytes'] != 0 or item['sha256'] is not None:
                raise ValueError('Native directory requires mode0755, zero bytes and null digest')
        elif item['kind'] == 'file':
            if item['mode'] not in (0o644, 0o755):
                raise ValueError('Native file mode must be0644 or0755')
            _digest(item['sha256'], path)
        else:
            raise ValueError('Unknown native inventory kind')
        if '/' in path and records.get(path.rsplit('/', 1)[0], {}).get('kind') != 'directory':
            raise ValueError('Native inventory omitted a complete exact parent directory')
        previous = path; aliases.add(path.lower()); records[path] = item
    if records.get('engine-sdk.json', {}).get('kind') != 'file' or records['engine-sdk.json']['sha256'] != pins['binary_manifest_sha256']:
        raise ValueError('Complete native inventory must include the exact binary manifest itself')
    if records.get(entry, {}).get('kind') != 'file':
        raise ValueError('Native provider is not an inventoried regular file')
    notices = value.get('notices')
    if type(notices) is not dict or not notices:
        raise ValueError('Complete native notice records required')
    for name, pin in notices.items():
        _path(name)
        if name == entry or records.get(name, {}).get('kind') != 'file':
            raise ValueError('Native notice is not a separate inventoried regular file')
        # Consumer metadata uses exact notice records, never owned file bytes.
        if type(pin) is dict:
            if 'sha256' not in pin or pin['sha256'] != records[name]['sha256']:
                raise ValueError('Native notice pin differs from inventory')
        elif type(pin) is str:
            if pin != records[name]['sha256']:
                raise ValueError('Native notice pin differs from inventory')
        else:
            raise ValueError('Invalid native notice pin')
    # Copy emitted structures after checking their primitive closed shapes.
    return profile, pins, target_macros, entry, list(records.values()), sorted(notices)

def _actions_contract():
    return importlib.import_module('appended_engine_native_actions_contract')


def _actions_metadata(value):
    """Validate emitted actions facts only; this is never runtime admission."""
    if type(value) is not dict:
        raise ValueError('Expected ordinary native actions consumer metadata')
    actions = _actions_contract()
    profile = value.get('engine_profile')
    _fields(profile, actions.PROFILE_FIELDS, 'actions engine profile')
    profile = actions.validate_engine_profile(profile, kernel_target=profile['target'],
        actions_profile='document-actions-v1')
    target_macros = _target(profile['target'])
    pins = {key: _digest(value.get(key), key) for key in
            ('recipe_id', 'binary_manifest_sha256', 'proof_sha256', 'runtime_sha256', 'provider_build_sha256')}
    if _digest(profile['source_recipe_sha256'], 'source recipe') != pins['recipe_id'] or _digest(profile['build_sha256'], 'provider build') != pins['provider_build_sha256']:
        raise ValueError('Native compiled actions profile differs from independently verified pins')
    entry = _path(value.get('provider_entry'))
    if profile['target']['system'] == 'Windows':
        if not entry.endswith('.dll'):
            raise ValueError('Native Windows provider must name an exact DLL')
    elif not re.search(r'\.so(?:\.[0-9]+)*\Z', entry):
        raise ValueError('Native Linux provider must name an exact shared library')
    inventory = value.get('inventory')
    if type(inventory) is not list or not 1 <= len(inventory) <= 65536:
        raise ValueError('Complete bounded native binary inventory required')
    records, aliases, previous = {}, set(), ''
    for item in inventory:
        _fields(item, ('path', 'kind', 'mode', 'bytes', 'sha256'), 'inventory record')
        path = _path(item['path'])
        if path <= previous or path.lower() in aliases:
            raise ValueError('Native binary inventory must be sorted and case-unambiguous')
        if type(item['mode']) is not int or type(item['bytes']) is not int or not 0 <= item['bytes'] <= ((1 << 64) - 1) // 8:
            raise ValueError('Invalid native binary inventory mode/size')
        if item['kind'] == 'directory':
            if item['mode'] != 0o755 or item['bytes'] != 0 or item['sha256'] is not None:
                raise ValueError('Native directory requires mode0755, zero bytes and null digest')
        elif item['kind'] == 'file':
            if item['mode'] not in (0o644, 0o755):
                raise ValueError('Native file mode must be0644 or0755')
            _digest(item['sha256'], path)
        else:
            raise ValueError('Unknown native inventory kind')
        if '/' in path and records.get(path.rsplit('/', 1)[0], {}).get('kind') != 'directory':
            raise ValueError('Native inventory omitted a complete exact parent directory')
        previous = path; aliases.add(path.lower()); records[path] = item
    if records.get('engine-sdk.json', {}).get('kind') != 'file' or records['engine-sdk.json']['sha256'] != pins['binary_manifest_sha256']:
        raise ValueError('Complete native inventory must include the exact binary manifest itself')
    if records.get(entry, {}).get('kind') != 'file':
        raise ValueError('Native provider is not an inventoried regular file')
    notices = value.get('notices')
    if type(notices) is not dict or not notices:
        raise ValueError('Complete native notice records required')
    for name, pin in notices.items():
        _path(name)
        if name == entry or records.get(name, {}).get('kind') != 'file':
            raise ValueError('Native notice is not a separate inventoried regular file')
        # Consumer metadata uses exact notice records, never owned file bytes.
        if type(pin) is dict:
            if 'sha256' not in pin or pin['sha256'] != records[name]['sha256']:
                raise ValueError('Native notice pin differs from inventory')
        elif type(pin) is str:
            if pin != records[name]['sha256']:
                raise ValueError('Native notice pin differs from inventory')
        else:
            raise ValueError('Invalid native notice pin')
    # Copy emitted structures after checking their primitive closed shapes.
    return profile, pins, target_macros, entry, list(records.values()), sorted(notices)



def _cpp_string(value):
    return json.dumps(value, ensure_ascii=True)


def _cpp_digest(value):
    return 'engine_document::Digest{' + ','.join('0x' + value[index:index + 2] for index in range(0, 64, 2)) + '}'


def _render(metadata):
    """PRIVATE syntax-fixture renderer; its output is explicitly ineligible.

    It deliberately cannot establish eligibility from a metadata dictionary.
    Use compiled_header(group, **consumer_arguments) for every real output.
    """
    profile, pins, (system, processor), entry, inventory, notices = _metadata(metadata)
    # Keep only emitted primitive facts. This lets regeneration recognize our
    # complete output shape without retaining developer paths or trusting an
    # arbitrary C++ payload merely because its checksum was recomputed.
    inventory_pins = {item['path']: item['sha256'] for item in inventory}
    emitted = {**pins, 'engine_profile': profile, 'provider_entry': entry,
        'inventory': inventory, 'notices': {name: inventory_pins[name] for name in notices}}
    serialized = json.dumps(emitted, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    metadata_comments = ''.join(METADATA_PREFIX + serialized[index:index + METADATA_CHUNK_BYTES] + '\n'
                                for index in range(0, len(serialized), METADATA_CHUNK_BYTES))
    constants = (('kBaseHeaderSha256', contract.BASE_HEADER_SHA256),
        ('kExtensionHeaderSha256', contract.EXTENSION_HEADER_SHA256), ('kContractSha256', contract.CONTRACT_SHA256),
        ('kCatalogSha256', contract.DOCUMENT_CATALOG_SHA256), ('kSchema', contract.DOCUMENT_SCHEMA_SHA256),
        ('kAckSchema', contract.ACTION_ACK_SCHEMA_SHA256))
    assertions = '\n'.join('static_assert(engine_document::' + name + ' == ' + _cpp_digest(pin) + ');'
                           for name, pin in constants)
    rows = []
    for item in inventory:
        directory = item['kind'] == 'directory'
        rows.append('        {' + _cpp_string(item['path']) + ', NativeEngineLoadAssetKind::' + item['kind'] +
                    ', 0' + format(item['mode'], 'o') + 'u, UINT64_C(' + str(item['bytes']) + '), ' +
                    ('engine_document::Digest{}' if directory else _cpp_digest(item['sha256'])) + '}')
    asset_rows = ',\n'.join(rows)
    notice_rows = ', '.join(_cpp_string(name) for name in notices)
    payload = (metadata_comments + f'''// Private immutable native composition facts; no provider or START is invoked.
#pragma once
#include "shared/native_engine_loader.hpp"

namespace foundation::appended {{
static_assert(BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_V2_ABI_MINOR == 1);
static_assert(BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR == 0);
static_assert(BIB_ENGINE_LIFETIME_PROCESS == 1);
{assertions}
static_assert(engine_document::kPixelProfileName == "foundation-engine-copied1795-ndv2-v1");
static_assert(engine_document::kPixelCapabilities == 1795);
static_assert(engine_document::kReplyCapacity == 1048576 && engine_document::kQueryCopiedReplyCapacity == 1048672 &&
    engine_document::kFormCopiedReplyCapacity == 1048680 && engine_document::kAckCopiedReplyCapacity == 120);
static_assert(engine_document::kQueries == std::array<engine_document::OperationFacts, 1>{{{{
    {{3, 48, 1048576, 512, engine_document::kSchema}}
}}}});
static_assert(engine_document::kCommands == std::array<engine_document::OperationFacts, 2>{{{{
    {{6, 6246, 1048576, 1024, engine_document::kSchema}}, {{7, 8, 16, 1024, engine_document::kAckSchema}}
}}}});
inline const engine_document::EngineDocumentProfileFacts compiled_native_engine_document_profile{{
    .enabled = true, .kind = engine_document::ProfileKind::pixel,
    .name = std::string(engine_document::kPixelProfileName),
    .provider_abi_major = 1, .provider_abi_minor = 1, .host_abi_major = 1, .host_abi_minor = 0,
    .target_system = {system}, .target_processor = {processor}, .pointer_bits = 64,
    .lifetime = BIB_ENGINE_LIFETIME_PROCESS, .maximum_starts = 1,
    .viewport_width = 800, .viewport_height = 600, .provider_capabilities = engine_document::kPixelCapabilities,
    .base_header_sha256 = engine_document::kBaseHeaderSha256,
    .extension_header_sha256 = engine_document::kExtensionHeaderSha256,
    .contract_sha256 = engine_document::kContractSha256, .catalog_sha256 = engine_document::kCatalogSha256,
    .build_sha256 = {_cpp_digest(profile['build_sha256'])},
    .source_recipe_sha256 = {_cpp_digest(profile['source_recipe_sha256'])},
    .physical_catalog_sha256 = engine_document::Digest{{}},
    .queries = engine_document::kQueries, .commands = engine_document::kCommands, .query_count = 1, .command_count = 2
}};
inline NativeEngineLoadPlan compiled_native_engine_load_plan(const std::filesystem::path& runtime_root) {{
    NativeEngineLoadPlan plan;
    plan.schema_version = 1;
    plan.pins = {{{_cpp_digest(pins['recipe_id'])}, {_cpp_digest(pins['binary_manifest_sha256'])},
        {_cpp_digest(pins['proof_sha256'])}, {_cpp_digest(pins['runtime_sha256'])}}};
    plan.expectation = {{{system}, {processor}, 64,
        compiled_native_engine_document_profile.contract_sha256,
        compiled_native_engine_document_profile.build_sha256,
        compiled_native_engine_document_profile.source_recipe_sha256,
        compiled_native_engine_document_profile}};
    plan.root = runtime_root;
    plan.provider_entry = {_cpp_string(entry)};
    plan.assets = {{
{asset_rows}
    }};
    plan.notices = {{{notice_rows}}};
    return plan;
}}
}} // namespace foundation::appended
''')
    header = (SYNTHETIC_NOTICE + '\n' + SELECTION_PREFIX + 'pixel\n' + PAYLOAD_PREFIX +
              hashlib.sha256(payload.encode('ascii')).hexdigest() + '\n' + payload)
    if len(header.encode('ascii')) > MAX_HEADER_BYTES:
        raise ValueError('Native compiled header exceeds byte bound')
    return header


def compiled_header(group, **consumer_kwargs):
    """Reverify the complete eligible retained group before returning any C++."""
    consumer = _consumer()
    inspection = consumer.verify_kernel_consumer(group, **consumer_kwargs)
    if not isinstance(inspection, consumer.NativeConsumerInspection):
        raise ValueError('Expected a fully verified native consumer inspection')
    metadata = inspection.as_dict()
    if (type(metadata) is not dict or metadata.get('scope') != NATIVE_SCOPE or
            metadata.get('whole_group_verified') is not True or metadata.get('production_eligible') is not True):
        raise ValueError('Native compiled facts require a fully verified eligible retained group')
    if consumer_kwargs.get('document_profile') != 'pixel' or metadata.get('engine_profile', {}).get('target') != consumer_kwargs.get('kernel_target'):
        raise ValueError('Native compiled profile differs from explicit selector/target')
    for argument, key in (('expected_recipe', 'recipe_id'), ('expected_manifest', 'binary_manifest_sha256'),
                          ('expected_proof', 'proof_sha256'), ('expected_runtime', 'runtime_sha256')):
        if consumer_kwargs.get(argument) != metadata.get(key):
            raise ValueError('Native compiled facts differ from independent ' + argument + ' pin')
    header = _render(metadata)
    return header.replace(SYNTHETIC_NOTICE, GENERATED_NOTICE, 1)


def _render_actions(metadata):
    """PRIVATE actions syntax fixture; never establishes retained eligibility."""
    profile, pins, (system, processor), entry, inventory, notices = _actions_metadata(metadata)
    actions = _actions_contract()
    inventory_pins = {item['path']: item['sha256'] for item in inventory}
    emitted = {**pins, 'engine_profile': profile, 'provider_entry': entry,
        'inventory': inventory, 'notices': {name: inventory_pins[name] for name in notices}}
    serialized = json.dumps(emitted, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    metadata_comments = ''.join(METADATA_PREFIX + serialized[index:index + METADATA_CHUNK_BYTES] + '\n'
                                for index in range(0, len(serialized), METADATA_CHUNK_BYTES))
    constants = (
        ('engine_document::kBaseHeaderSha256', 'base_header_sha256'),
        ('engine_document::kExtensionHeaderSha256', 'document_header_sha256'),
        ('engine_document::kContractSha256', 'document_contract_sha256'),
        ('engine_document::kCatalogSha256', 'document_catalog_sha256'),
        ('engine_document::kSchema', 'document_schema_sha256'),
        ('engine_document::kAckSchema', 'action_ack_schema_sha256'),
        ('engine_document::kPhysicalCatalogSha256', 'physical_catalog_sha256'),
        ('engine_editor::kHeaderSha256', 'editor_header_sha256'),
        ('engine_editor::kContractSha256', 'editor_contract_sha256'),
        ('engine_editor::kCatalogSha256', 'editor_catalog_sha256'),
        ('engine_editor::kSchema', 'editor_schema_sha256'),
        ('engine_document_actions::kHeaderSha256', 'actions_header_sha256'),
        ('engine_document_actions::kContractSha256', 'contract_sha256'),
        ('engine_document_actions::kCatalogSha256', 'actions_catalog_sha256'),
        ('engine_document_actions::kSchema', 'actions_schema_sha256'),
        ('engine_document_actions::kAckSchema', 'actions_ack_schema_sha256'))
    assertions = '\n'.join('static_assert(' + name + ' == ' + _cpp_digest(profile[key]) + ');'
                           for name, key in constants)
    descriptor = actions.provider_contract(kernel_target=profile['target'], actions_profile='document-actions-v1')
    for catalog in ('queries', 'commands'):
        rows = ',\n'.join('    {' + ', '.join(str(item[key]) for key in
            ('operation', 'maximum_input_bytes', 'required_reply_capacity', 'capability')) + ', ' +
            _cpp_digest(item['schema_sha256']) + '}' for item in descriptor[catalog])
        assertions += ('\nstatic_assert(engine_document_actions::k' + catalog.title() +
            ' == std::array<engine_document::OperationFacts, ' + str(len(descriptor[catalog])) + '>{{\n' + rows + '\n}});')
    rows = []
    for item in inventory:
        directory = item['kind'] == 'directory'
        rows.append('        {' + _cpp_string(item['path']) + ', NativeEngineLoadAssetKind::' + item['kind'] +
                    ', 0' + format(item['mode'], 'o') + 'u, UINT64_C(' + str(item['bytes']) + '), ' +
                    ('engine_document::Digest{}' if directory else _cpp_digest(item['sha256'])) + '}')
    asset_rows = ',\n'.join(rows)
    notice_rows = ', '.join(_cpp_string(name) for name in notices)
    payload = (metadata_comments + f'''// Private immutable native actions facts; no provider or START is invoked.
#pragma once
#include "shared/native_engine_loader.hpp"

namespace foundation::appended {{
static_assert(BIB_ENGINE_DOCUMENT_ACTIONS_V1_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_ACTIONS_V1_ABI_MINOR == 1);
static_assert(BIB_ENGINE_DOCUMENT_ACTIONS_V1_HOST_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_ACTIONS_V1_HOST_ABI_MINOR == 0);
static_assert(BIB_ENGINE_LIFETIME_PROCESS == 1);
static_assert(static_cast<std::uint32_t>(engine_document_actions::ProfileKind::document_actions) == 4);
static_assert(engine_document_actions::kProfileName == "foundation-engine-copied4083-ndv2-editor-document-actions-v1");
static_assert(engine_document_actions::kProviderCapabilities == 4083 && engine_document_actions::kSurfaceCapabilities == 8255);
static_assert(BIB_ENGINE_EDITOR_SURFACE_PROTOCOL_VERSION == 2 && BIB_ENGINE_EDITOR_PROTOCOL_VERSION == 1);
static_assert(BIB_ENGINE_EDITOR_MAX_WIRE_BYTES == 1048576 && BIB_ENGINE_EDITOR_MAX_QUERY_BYTES == 236 && BIB_ENGINE_EDITOR_REPLY_CAPACITY == 1048576);
static_assert(engine_document_actions::kRequestBytes == 128 && engine_document_actions::kReplyCapacity == 1048576 &&
    engine_document_actions::kAckRequestBytes == 8 && engine_document_actions::kAckReplyCapacity == 16 &&
    engine_document_actions::kCopiedReplyCapacity == 1048680 && engine_document_actions::kAckCopiedReplyCapacity == 120);
{assertions}
inline const engine_document_actions::EngineDocumentActionsProfileFacts compiled_native_engine_document_actions_profile{{
    .enabled = true, .kind = engine_document_actions::ProfileKind::document_actions,
    .name = std::string(engine_document_actions::kProfileName),
    .provider_abi_major = 1, .provider_abi_minor = 1, .host_abi_major = 1, .host_abi_minor = 0,
    .target_system = {system}, .target_processor = {processor}, .pointer_bits = 64,
    .lifetime = BIB_ENGINE_LIFETIME_PROCESS, .maximum_starts = 1,
    .viewport_width = 800, .viewport_height = 600,
    .provider_capabilities = engine_document_actions::kProviderCapabilities, .surface_capabilities = engine_document_actions::kSurfaceCapabilities,
    .surface_protocol_version = 2, .editor_protocol_version = 1,
    .base_header_sha256 = engine_document::kBaseHeaderSha256,
    .document_header_sha256 = engine_document::kExtensionHeaderSha256,
    .document_contract_sha256 = engine_document::kContractSha256,
    .document_catalog_sha256 = engine_document::kCatalogSha256,
    .physical_catalog_sha256 = engine_document::kPhysicalCatalogSha256,
    .editor_header_sha256 = engine_editor::kHeaderSha256,
    .editor_contract_sha256 = engine_editor::kContractSha256,
    .editor_catalog_sha256 = engine_editor::kCatalogSha256, .editor_schema_sha256 = engine_editor::kSchema,
    .actions_header_sha256 = engine_document_actions::kHeaderSha256,
    .contract_sha256 = engine_document_actions::kContractSha256,
    .catalog_sha256 = engine_document_actions::kCatalogSha256,
    .schema_sha256 = engine_document_actions::kSchema, .ack_schema_sha256 = engine_document_actions::kAckSchema,
    .build_sha256 = {_cpp_digest(profile['build_sha256'])},
    .source_recipe_sha256 = {_cpp_digest(profile['source_recipe_sha256'])},
    .queries = engine_document_actions::kQueries, .commands = engine_document_actions::kCommands, .query_count = 2, .command_count = 9
}};
inline NativeEngineLoadPlan compiled_native_engine_load_plan(const std::filesystem::path& runtime_root) {{
    NativeEngineLoadPlan plan;
    plan.schema_version = 1;
    plan.pins = {{{_cpp_digest(pins['recipe_id'])}, {_cpp_digest(pins['binary_manifest_sha256'])},
        {_cpp_digest(pins['proof_sha256'])}, {_cpp_digest(pins['runtime_sha256'])}}};
    plan.expectation.target_system = {system};
    plan.expectation.target_processor = {processor};
    plan.expectation.pointer_bits = 64;
    plan.expectation.contract_header_sha256 = compiled_native_engine_document_actions_profile.contract_sha256;
    plan.expectation.build_identity_sha256 = compiled_native_engine_document_actions_profile.build_sha256;
    plan.expectation.source_recipe_sha256 = compiled_native_engine_document_actions_profile.source_recipe_sha256;
    plan.expectation.document_actions_profile = compiled_native_engine_document_actions_profile;
    plan.root = runtime_root;
    plan.provider_entry = {_cpp_string(entry)};
    plan.assets = {{
{asset_rows}
    }};
    plan.notices = {{{notice_rows}}};
    return plan;
}}
}} // namespace foundation::appended
''')
    header = (SYNTHETIC_NOTICE + '\n' + ACTIONS_SELECTION_PREFIX + 'document-actions-v1\n' + PAYLOAD_PREFIX +
              hashlib.sha256(payload.encode('ascii')).hexdigest() + '\n' + payload)
    if len(header.encode('ascii')) > MAX_HEADER_BYTES:
        raise ValueError('Native compiled actions header exceeds byte bound')
    return header


def compiled_actions_header(group, **consumer_kwargs):
    """Reverify the complete eligible actions group before returning any C++."""
    consumer = _consumer()
    inspection = consumer.verify_actions_kernel_consumer(group, **consumer_kwargs)
    if not isinstance(inspection, consumer.NativeConsumerInspection):
        raise ValueError('Expected a fully verified native actions consumer inspection')
    metadata = inspection.as_dict()
    if (type(metadata) is not dict or metadata.get('scope') != _actions_contract().SCOPE or
            metadata.get('whole_group_verified') is not True or metadata.get('production_eligible') is not True):
        raise ValueError('Native compiled actions facts require a fully verified eligible retained group')
    emitted_profile = metadata.get('engine_profile')
    if (consumer_kwargs.get('actions_profile') != 'document-actions-v1' or type(emitted_profile) is not dict or
            emitted_profile.get('target') != consumer_kwargs.get('kernel_target')):
        raise ValueError('Native compiled actions profile differs from explicit selector/target')
    for argument, key in (('expected_recipe', 'recipe_id'), ('expected_manifest', 'binary_manifest_sha256'),
                          ('expected_proof', 'proof_sha256'), ('expected_runtime', 'runtime_sha256')):
        if consumer_kwargs.get(argument) != metadata.get(key):
            raise ValueError('Native compiled actions facts differ from independent ' + argument + ' pin')
    return _render_actions(metadata).replace(SYNTHETIC_NOTICE, GENERATED_NOTICE, 1)


def _ordinary_path(path, directory=False):
    for parent in reversed(path.parents):
        manifest.plain_state(parent.lstat(), directory=True)
    try:
        manifest.plain_state(path.lstat(), directory=directory)
    except FileNotFoundError:
        return
    if path.resolve(strict=True) != path:
        raise ValueError('Native compiled-profile output must not alias another path')


def _read_regular(path, maximum):
    _ordinary_path(path)
    with path.open('rb') as stream:
        initial = manifest.plain_state(os.fstat(stream.fileno()), directory=False)
        if initial.st_size > maximum:
            raise ValueError('Native compiled-profile input exceeds byte bound')
        content = stream.read(maximum + 1)
        final = os.fstat(stream.fileno())
    identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size,
                              value.st_mtime_ns, value.st_ctime_ns)
    if len(content) > maximum or identity(initial) != identity(final) or identity(initial) != identity(path.lstat()):
        raise ValueError('Native compiled-profile input changed during read')
    return content


def _check_existing_selection(content, selected):
    lines = content.splitlines(keepends=True)
    if (len(lines) < 4 or lines[0] != (GENERATED_NOTICE + '\n').encode('ascii') or
            lines[1] not in {(SELECTION_PREFIX + item + '\n').encode('ascii') for item in ('pixel', 'physical')}):
        raise ValueError('Existing native compiled profile is foreign or malformed; use a fresh build directory')
    if lines[1] != (SELECTION_PREFIX + selected + '\n').encode('ascii'):
        raise ValueError('Native document profile selection changed; use a fresh build directory')
    match = re.fullmatch(re.escape(PAYLOAD_PREFIX.encode('ascii')) + rb'([0-9a-f]{64})\n', lines[2])
    if not match or hashlib.sha256(b''.join(lines[3:])).hexdigest().encode('ascii') != match[1]:
        raise ValueError('Existing native compiled profile is malformed; use a fresh build directory')
    if not lines[3].startswith(METADATA_PREFIX.encode('ascii')):
        raise ValueError('Existing native compiled profile lacks canonical metadata; use a fresh build directory')
    try:
        chunks = []
        for line in lines[3:]:
            if not line.startswith(METADATA_PREFIX.encode('ascii')):
                break
            if not line.endswith(b'\n') or len(line) > len(METADATA_PREFIX) + METADATA_CHUNK_BYTES + 1:
                raise ValueError('Invalid native metadata comment')
            chunks.append(line[len(METADATA_PREFIX):-1])
        metadata = contract.strict_json(b''.join(chunks), 'native generated metadata', maximum=MAX_HEADER_BYTES)
        canonical = _render(metadata).replace(SYNTHETIC_NOTICE, GENERATED_NOTICE, 1).encode('ascii')
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        raise ValueError('Existing native compiled profile is malformed; use a fresh build directory') from error
    if canonical != content:
        raise ValueError('Existing native compiled profile contains foreign content; use a fresh build directory')


def _check_existing_actions_selection(content, selected):
    lines = content.splitlines(keepends=True)
    if (len(lines) < 4 or lines[0] != (GENERATED_NOTICE + '\n').encode('ascii') or
            lines[1] not in {(ACTIONS_SELECTION_PREFIX + item + '\n').encode('ascii') for item in ('document-actions-v1',)}):
        raise ValueError('Existing native compiled profile is foreign or malformed; use a fresh build directory')
    if lines[1] != (ACTIONS_SELECTION_PREFIX + selected + '\n').encode('ascii'):
        raise ValueError('Native document actions profile selection changed; use a fresh build directory')
    match = re.fullmatch(re.escape(PAYLOAD_PREFIX.encode('ascii')) + rb'([0-9a-f]{64})\n', lines[2])
    if not match or hashlib.sha256(b''.join(lines[3:])).hexdigest().encode('ascii') != match[1]:
        raise ValueError('Existing native compiled profile is malformed; use a fresh build directory')
    if not lines[3].startswith(METADATA_PREFIX.encode('ascii')):
        raise ValueError('Existing native compiled profile lacks canonical metadata; use a fresh build directory')
    try:
        chunks = []
        for line in lines[3:]:
            if not line.startswith(METADATA_PREFIX.encode('ascii')):
                break
            if not line.endswith(b'\n') or len(line) > len(METADATA_PREFIX) + METADATA_CHUNK_BYTES + 1:
                raise ValueError('Invalid native metadata comment')
            chunks.append(line[len(METADATA_PREFIX):-1])
        metadata = contract.strict_json(b''.join(chunks), 'native generated metadata', maximum=MAX_HEADER_BYTES)
        canonical = _render_actions(metadata).replace(SYNTHETIC_NOTICE, GENERATED_NOTICE, 1).encode('ascii')
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        raise ValueError('Existing native compiled profile is malformed; use a fresh build directory') from error
    if canonical != content:
        raise ValueError('Existing native compiled profile contains foreign content; use a fresh build directory')


def _temporary_mode(descriptor, path, *, windows=None):
    if windows is None:
        windows = os.name == 'nt'
    if windows:
        # Windows Python3.9 lacks fchmod. This only sets the ordinary header's
        # writable attribute; the compiled loader plan owns logical asset modes.
        os.chmod(path, 0o644)
    else:
        change = getattr(os, 'fchmod', None)
        if not callable(change):
            raise ValueError('Native compiled-profile POSIX descriptor modes are unavailable')
        change(descriptor, 0o644)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', type=Path, required=True)
    for name in ('recipe', 'manifest', 'proof', 'runtime'):
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--kernel-target-json', type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--document-profile', choices=('pixel', 'physical'))
    selection.add_argument('--actions-profile', choices=('document-actions-v1',))
    parser.add_argument('--build-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    build = manifest.ordinary_root(args.build_dir)
    group = manifest.ordinary_root(args.group)
    if build == group or group in build.parents or build in group.parents:
        raise ValueError('Native compiled-profile output must be separate from retained inputs')
    actions_mode = args.actions_profile is not None
    selected = args.actions_profile if actions_mode else args.document_profile
    check_selection = _check_existing_actions_selection if actions_mode else _check_existing_selection
    directory = build / (ACTIONS_HEADER_DIRECTORY if actions_mode else HEADER_DIRECTORY)
    _ordinary_path(directory, directory=True)
    output = directory / HEADER_NAME
    if directory.exists():
        _ordinary_path(output)
        if output.exists():
            check_selection(_read_regular(output, MAX_HEADER_BYTES), selected)
    target_path = args.kernel_target_json.absolute()
    if target_path.resolve(strict=True) == output.resolve():
        raise ValueError('Native compiled-profile output must not overwrite its target input')
    target = manifest.json_bytes(_read_regular(target_path, manifest.MAX_MANIFEST))
    render = compiled_actions_header if actions_mode else compiled_header
    selector_argument = {'actions_profile' if actions_mode else 'document_profile': selected}
    header = render(group, expected_recipe=args.recipe_sha256, expected_manifest=args.manifest_sha256,
        expected_proof=args.proof_sha256, expected_runtime=args.runtime_sha256, kernel_target=target,
        **selector_argument).encode('ascii')
    directory.mkdir(mode=0o755, exist_ok=True)
    _ordinary_path(directory, directory=True)
    _ordinary_path(output)
    previous = _read_regular(output, MAX_HEADER_BYTES) if output.exists() else None
    if previous is not None:
        check_selection(previous, selected)
    if previous != header:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.compiled-native-profile-', dir=directory, delete=False) as stream:
                temporary = Path(stream.name)
                _temporary_mode(stream.fileno(), temporary)
                stream.write(header); stream.flush(); os.fsync(stream.fileno())
            _ordinary_path(output)
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print(json.dumps({'scope': 'compiled-native-retained-facts-only', 'header': str(output),
                      'sha256': hashlib.sha256(header).hexdigest(), **selector_argument}, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, tarfile.TarError) as error:
        raise SystemExit('appended engine native profile: ' + str(error))
