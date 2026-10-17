#!/usr/bin/env python3
"""Admit independently pinned native document-engine bytes and original evidence.

This reader never loads a DSO, runs an inspection tool, discovers an SDK or builds
an engine. Stage A supplies complete archive integrity. Native admission adds its
own closed ABI/profile/dependency/runtime contracts; browser proofs do not apply.
"""
import argparse
from dataclasses import dataclass, fields as dataclass_fields
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tarfile
from types import MappingProxyType

import appended_engine_document_contract as contract
import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
from dependency_archive import encoded

SCOPE = 'retained-native-document-consumer-byte-and-static-contract-only'
EMBEDDED_SCOPE = 'embedded-retained-native-document-consumer-byte-and-static-contract-only'
PROFILE_KIND = 'foundation-native-engine-document-v2'
PROOF_KIND = 'foundation-neutral-engine-provider-native-document-v2-proof-v1'
BUILD_KIND = 'foundation-neutral-engine-provider-native-document-v2-build-v1'
RUNTIME_KIND = 'foundation-neutral-engine-native-document-v2-runtime-evidence-v1'
BINDING = 'private-native'
GETTER = 'bib_engine_get_provider_v1'
PROFILE_FIELDS = ('schema_version', 'kind', 'binding', 'target', 'document_profile',
    'provider_abi_major', 'provider_abi_minor', 'host_abi_major', 'host_abi_minor',
    'lifetime', 'maximum_starts', 'viewport_width', 'viewport_height', 'capabilities',
    'base_header_sha256', 'extension_header_sha256', 'contract_sha256',
    'document_catalog_sha256', 'document_schema_sha256', 'action_ack_schema_sha256',
    'build_sha256', 'source_recipe_sha256')
PROOF_FIELDS = ('schema_version', 'kind', 'recipe_id', 'sources_sha256', 'provider_build',
    'engine_profile', 'assets', 'native_facts', 'runtime_evidence', 'interfaces')
BUILD_FIELDS = ('schema_version', 'kind', 'target', 'toolchain', 'options',
    'source_recipe_sha256', 'source_inputs_sha256', 'contract_header_sha256', 'binding',
    'configuration', 'capabilities', 'provider_contract', 'provider_limits')
RUNTIME_FIELDS = ('schema_version', 'kind', 'scope', 'status', 'recipe_id',
    'provider_build_sha256', 'assets_sha256', 'target', 'toolchain_identity_sha256',
    'engine_profile', 'environment', 'checks', 'provider_observation', 'bootstrap',
    'native_facts_sha256')
EVIDENCE_FIELDS = ('binary_manifest', 'source_manifest', 'recipe', 'proof',
    'provider_build', 'runtime', 'reports', 'interfaces')
BOOTSTRAP_CHECKS = ('getter_before_start', 'table_checked_before_start',
    'no_host_callbacks_during_getter', 'one_process_start',
    'outside_engine_owner_pump', 'process_lifetime_no_unload')
RUNTIME_CHECKS = ('native-getter-inert-and-table', 'native-import-export-dependency-closure',
    'native-runtime-floor-and-private-runtime', 'native-offline-entry-resource-load',
    'native-service-result-and-ack', 'native-outside-engine-owner-pump',
    'native-opaque-raster-frame', 'native-failure-close-process-lifetime',
    'document-provider-minor-and-catalog', 'document-query3-owned-snapshot',
    'document-form6-native-readback', 'document-action-replay-and-ack7',
    'document-navigation-and-stale-lease', 'document-outer-unknown-terminal-no-replay')
LIMIT_FIELDS = ('size', 'maximum_command_bytes', 'maximum_query_bytes',
    'maximum_reply_bytes', 'maximum_service_message_bytes', 'maximum_retired_documents',
    'maximum_inflight_resources', 'reserved', 'maximum_resource_response_bytes',
    'maximum_retained_resource_bytes')
BOOKWORM = {'GLIBC': '2.36', 'GLIBCXX': '3.4.30', 'CXXABI': '1.3.13', 'GCC': '12.0.0'}
STATUS = ('passed', 'failed', 'not-run')
_TARGETS = {('Linux', 'x86_64'): (1, 1), ('Linux', 'aarch64'): (1, 2), ('Windows', 'x86_64'): (2, 1)}
_SYSTEM_LINUX = {'libc.so.6', 'libm.so.6', 'libpthread.so.0', 'libdl.so.2', 'librt.so.1',
    'libresolv.so.2', 'libutil.so.1', 'ld-linux-x86-64.so.2', 'ld-linux-aarch64.so.1',
    'libgcc_s.so.1', 'libstdc++.so.6'}
_SYSTEM_WINDOWS = {'kernel32.dll', 'ntdll.dll', 'ucrtbase.dll', 'msvcrt.dll', 'advapi32.dll',
    'user32.dll', 'gdi32.dll', 'shell32.dll', 'ole32.dll', 'oleaut32.dll', 'ws2_32.dll',
    'bcrypt.dll', 'crypt32.dll', 'secur32.dll', 'version.dll', 'winmm.dll', 'dwrite.dll',
    'd2d1.dll', 'windowscodecs.dll', 'combase.dll', 'kernelbase.dll'}


class NativeConsumerError(ValueError):
    pass


def _fail(message):
    raise NativeConsumerError(message)


def _public(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except NativeConsumerError:
            raise
        except (ValueError, TypeError, KeyError, OSError, tarfile.TarError, UnicodeError, struct.error) as error:
            raise NativeConsumerError(str(error)) from error
    return checked


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _same(left, right):
    return contract.canonical_json(left) == contract.canonical_json(right)


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if hasattr(value, 'items'):
        return {key: _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class NativeConsumerLimits:
    max_native_member_bytes: int = 512 * 1024 * 1024
    max_native_total_bytes: int = 1024 * 1024 * 1024
    max_data_member_bytes: int = 64 * 1024 * 1024
    max_data_total_bytes: int = 128 * 1024 * 1024
    max_assets: int = 256
    max_members: int = 4096
    max_notice_bytes: int = 4 * 1024 * 1024
    max_notices_total_bytes: int = 16 * 1024 * 1024
    max_notices: int = 128
    max_reports_total_bytes: int = 32 * 1024 * 1024

    def __post_init__(self):
        for field in dataclass_fields(self):
            if type(getattr(self, field.name)) is not int or getattr(self, field.name) <= 0:
                _fail('Invalid positive native consumer limit: ' + field.name)


@dataclass(frozen=True)
class NativeConsumerInspection:
    metadata: object
    assets: object
    notices: object
    evidence: object

    def as_dict(self):
        return _thaw(self.metadata)


def _selector(value):
    contract.document_selector(value)
    if value != 'pixel':
        _fail('Native physical2003 admission is unavailable; explicit target/host qualification required')
    return value


@_public
def native_target(value):
    target = contract.json_copy(value, 'native target')
    manifest.target_contract(target)
    if (target['system'], target['processor']) not in _TARGETS or target['pointer_bits'] != 64:
        _fail('Only explicit Linux x86_64/aarch64 or Windows x86_64 native targets are supported')
    return target


@_public
def expected_engine_profile(*, kernel_target, document_profile, build_sha256, source_recipe_sha256):
    _selector(document_profile)
    target = native_target(kernel_target)
    return {'schema_version': 1, 'kind': PROFILE_KIND, 'binding': BINDING, 'target': target,
        'document_profile': contract.PROFILE_NAMES[document_profile],
        'provider_abi_major': 1, 'provider_abi_minor': 1, 'host_abi_major': 1, 'host_abi_minor': 0,
        'lifetime': 1, 'maximum_starts': 1, 'viewport_width': 800, 'viewport_height': 600,
        'capabilities': '1795', 'base_header_sha256': contract.BASE_HEADER_SHA256,
        'extension_header_sha256': contract.EXTENSION_HEADER_SHA256,
        'contract_sha256': contract.CONTRACT_SHA256, 'document_catalog_sha256': contract.DOCUMENT_CATALOG_SHA256,
        'document_schema_sha256': contract.DOCUMENT_SCHEMA_SHA256,
        'action_ack_schema_sha256': contract.ACTION_ACK_SCHEMA_SHA256,
        'build_sha256': contract.validate_sha256(build_sha256, 'native provider build', nonzero=True),
        'source_recipe_sha256': contract.validate_sha256(source_recipe_sha256, 'native recipe', nonzero=True)}


@_public
def validate_engine_profile(value, *, kernel_target, document_profile):
    value = contract.json_copy(value, 'native engine profile')
    contract.require_fields(value, PROFILE_FIELDS, 'native engine profile')
    expected = expected_engine_profile(kernel_target=kernel_target, document_profile=document_profile,
        build_sha256=value['build_sha256'], source_recipe_sha256=value['source_recipe_sha256'])
    if not _same(value, expected):
        _fail('Native engine profile differs from the explicit ABI1.1 pixel1795 contract')
    return value


@_public
def provider_contract(*, kernel_target, document_profile):
    _selector(document_profile)
    target = native_target(kernel_target)
    system, processor = _TARGETS[(target['system'], target['processor'])]
    # Only the shared canonical operation arrays are reused; browser target and
    # Worker/bootstrap/profile facts are deliberately not imported here.
    operations = contract.provider_contract(document_profile='pixel')
    return {'provider_abi': {'major': 1, 'minor': 1}, 'host_abi': {'major': 1, 'minor': 0},
        'getter_maximum_minor': 1, 'target': {'system': system, 'processor': processor, 'pointer_bits': 64},
        'lifetime': 1, 'maximum_starts': 1, 'queries': operations['queries'], 'commands': operations['commands']}


@_public
def expected_configuration(*, document_profile):
    _selector(document_profile)
    return {'kind': 'native-dso-private-runtime-v1', 'document_profile': contract.PROFILE_NAMES[document_profile],
        'getter': GETTER, 'getter_maximum_minor': 1, 'inert_registration': True,
        'public_exports': [GETTER], 'rendering': 'cpu', 'script_enabled': True, 'thread_model': 'native'}


@_public
def validate_provider_limits(value):
    value = contract.json_copy(value, 'native provider limits')
    contract.require_fields(value, LIMIT_FIELDS, 'native provider limits')
    bounds = {'size': (48, 48), 'reserved': (0, 0), 'maximum_command_bytes': (6246, 16 * 1024 * 1024),
        'maximum_query_bytes': (48, 16 * 1024 * 1024), 'maximum_reply_bytes': (1048576, 16 * 1024 * 1024),
        'maximum_service_message_bytes': (384, 1048576), 'maximum_retired_documents': (1, 8),
        'maximum_inflight_resources': (1, 64), 'maximum_resource_response_bytes': (1, 64 * 1024 * 1024),
        'maximum_retained_resource_bytes': (1, 128 * 1024 * 1024)}
    for name, (minimum, maximum) in bounds.items():
        manifest.integer(value[name], 'native provider ' + name, minimum, maximum)
    if value['maximum_retained_resource_bytes'] < value['maximum_resource_response_bytes']:
        _fail('Native retained-resource maximum is smaller than one response')
    return value


def _document(raw, label):
    if type(raw) is not bytes:
        _fail('Expected owned original ' + label + ' bytes')
    return contract.strict_json(raw, label, maximum=manifest.MAX_MANIFEST)


def _mapping(value, label):
    if not hasattr(value, 'items'):
        _fail('Expected owned ' + label + ' mapping')
    return dict(value.items())


def _reference(value, label):
    contract.require_fields(value, ('path', 'sha256'), label)
    manifest.path_name(value['path']);contract.validate_sha256(value['sha256'], label, nonzero=True)
    return value['path']


def _version(value, kind, label):
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != kind:
        _fail('Unsupported native ' + label + ' kind/version')


def _pins(value):
    value = _mapping(value, 'native independent pin')
    contract.require_fields(value, ('recipe', 'manifest', 'proof', 'runtime'), 'native independent pins')
    for name, pin in value.items():
        contract.validate_sha256(pin, name + ' independent pin', nonzero=True)
    return value


def _member(mapping, path, binary, maximum, label):
    manifest.path_name(path)
    raw = mapping.get(path)
    if type(raw) is not bytes or len(raw) > maximum or binary['files'].get(path) != _hash(raw):
        _fail('Missing, oversized or changed native ' + label + ': ' + path)
    return raw


def _path_inventory(binary, limits):
    if len(binary['files']) + len(binary['directories']) + 1 > limits.max_members:
        _fail('Native complete binary inventory exceeds member bound')
    for path in [*binary['files'], *binary['directories'], 'engine-sdk.json']:
        manifest.path_name(path)
        if len(path) > 4096:
            _fail('Native retained path exceeds loader bound')


def _asset_records(proof, binary, limits):
    records = proof['assets']
    if type(records) is not dict or set(records) != set(binary['provider']['assets']) or not 1 <= len(records) <= limits.max_assets:
        _fail('Native asset closure differs from complete Stage-A assets')
    native_bytes = data_bytes = 0;providers = [];imports = 0
    for path, item in records.items():
        manifest.path_name(path)
        contract.require_fields(item, ('role', 'sha256', 'bytes', 'mode'), 'native runtime asset')
        role = item['role']
        if role not in ('provider', 'dependency', 'data', 'import-library'):
            _fail('Unsupported native asset role; browser factories/Wasm are ineligible')
        maximum = limits.max_data_member_bytes if role == 'data' else limits.max_native_member_bytes
        manifest.integer(item['bytes'], 'native asset size', 0 if role == 'data' else 1, maximum)
        if item['sha256'] != binary['files'].get(path) or type(item['mode']) is not int or item['mode'] != binary['modes'][path]:
            _fail('Native asset digest/mode differs from exact binary inventory')
        if role == 'provider':providers.append(path)
        if role == 'import-library':
            imports += 1
            if binary['target']['system'] != 'Windows' or not path.endswith('.lib'):
                _fail('Import-library role is only an explicit Windows .lib asset')
        if role == 'data':data_bytes += item['bytes']
        else:native_bytes += item['bytes']
    if providers != [binary['provider']['entry']] or native_bytes > limits.max_native_total_bytes or data_bytes > limits.max_data_total_bytes:
        _fail('Native provider count/entry or aggregate asset bound differs')
    if binary['target']['system'] == 'Windows' and imports == 0:
        _fail('Native Windows closure lacks its explicit import library')
    return records


def _native_header(raw, target):
    """Check actual format/machine/DSO shape, never execute platform tools."""
    if target['system'] == 'Linux':
        if len(raw) < 64 or raw[:7] != b'\x7fELF\x02\x01\x01':
            _fail('Native Linux asset requires an actual ELF64 little-endian header')
        kind, machine, version = struct.unpack_from('<HHI', raw, 16)
        if kind != 3 or machine != {'x86_64':62, 'aarch64':183}[target['processor']] or version != 1:
            _fail('Native ELF DSO type/machine/version differs from full target')
        return 'elf64-le'
    if len(raw) < 64 or raw[:2] != b'MZ':
        _fail('Native Windows asset requires an actual PE32+ DLL header')
    offset = struct.unpack_from('<I', raw, 60)[0]
    if offset < 64 or offset > len(raw) - 26 or raw[offset:offset+4] != b'PE\0\0':
        _fail('Invalid bounded PE header offset/signature')
    machine = struct.unpack_from('<H', raw, offset+4)[0]
    optional, flags = struct.unpack_from('<HH', raw, offset+20)
    if machine != 0x8664 or not flags & 0x2000 or optional < 2 or offset+24+optional > len(raw) or struct.unpack_from('<H',raw,offset+24)[0] != 0x20b:
        _fail('Native PE machine/DLL/64-bit optional header differs')
    return 'pe32plus'


def _actions_contract():
    # The independent source contract has no engine or eligibility side effect.
    import appended_engine_native_actions_contract
    return appended_engine_native_actions_contract


@_public
def expected_actions_engine_profile(*, kernel_target, actions_profile='document-actions-v1',
                                    build_sha256, source_recipe_sha256):
    return _actions_contract().expected_engine_profile(kernel_target=kernel_target,
        actions_profile=actions_profile, build_sha256=build_sha256, source_recipe_sha256=source_recipe_sha256)


@_public
def validate_actions_engine_profile(value, *, kernel_target, actions_profile='document-actions-v1'):
    return _actions_contract().validate_engine_profile(value, kernel_target=kernel_target, actions_profile=actions_profile)


@_public
def actions_provider_contract(*, kernel_target, actions_profile='document-actions-v1'):
    return _actions_contract().provider_contract(kernel_target=kernel_target, actions_profile=actions_profile)


@_public
def expected_actions_configuration(*, actions_profile='document-actions-v1'):
    return _actions_contract().expected_configuration(actions_profile=actions_profile)


@_public
def validate_actions_provider_limits(value):
    return _actions_contract().validate_actions_provider_limits(value)


def _selection(kernel_target, document_profile, limits, *, actions=False):
    selected = _actions_contract().actions_selector(document_profile) if actions else _selector(document_profile)
    target = native_target(kernel_target)
    limits = NativeConsumerLimits() if limits is None else limits
    if type(limits) is not NativeConsumerLimits:
        _fail('Expected explicit NativeConsumerLimits')
    return selected, target, limits


def _evidence(value):
    value = _mapping(value, 'native evidence')
    contract.require_fields(value, EVIDENCE_FIELDS, 'native evidence')
    value['reports'] = _mapping(value['reports'], 'original native report')
    value['interfaces'] = _mapping(value['interfaces'], 'native interface')
    for name in EVIDENCE_FIELDS:
        if name not in ('reports', 'interfaces') and (type(value[name]) is not bytes or len(value[name]) > manifest.MAX_MANIFEST):
            _fail('Expected bounded owned original native ' + name + ' bytes')
    return value


def _metadata_paths(binary, proof, selected, *, actions=False):
    interfaces = (_actions_contract().validate_interface_references(proof['interfaces'], actions_profile=selected) if actions else
        contract.validate_interface_references(proof['interfaces'], document_profile=selected))
    build_path = _reference(proof['provider_build'], 'native provider build')
    runtime_path = _reference(proof['runtime_evidence'], 'native runtime')
    metadata = {binary['build']['link_receipt'], build_path, runtime_path}
    interface_paths = {item['path'] for item in interfaces.values()}
    if len(metadata) != 3 or metadata & interface_paths:
        _fail('Conflicting native proof/build/runtime/interface roles')
    if binary['provider']['header'] != interfaces['base_header']['path']:
        _fail('Native provider header must name the canonical source-pinned base interface')
    reserved = metadata | interface_paths
    if reserved & (set(binary['provider']['assets']) | set(binary['licenses'])):
        _fail('Conflicting native metadata/asset/notice roles')
    return interfaces, build_path, runtime_path, reserved


def _environment(value, target):
    contract.require_fields(value, ('system', 'processor', 'os_version', 'loader', 'loader_flags'), 'native runtime environment')
    manifest.text(value['os_version'], 'native observed operating-system version')
    windows = target['system'] == 'Windows'
    flags = sorted(['LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR', 'LOAD_LIBRARY_SEARCH_SYSTEM32'] if windows else ['RTLD_NOW', 'RTLD_LOCAL'])
    if (value['system'] != target['system'] or value['processor'] != target['processor']
            or value['loader'] != ('LoadLibraryExW' if windows else 'dlopen') or not _same(value['loader_flags'], flags)):
        _fail('Native runtime environment differs from the selected private loader policy')


def _documents(evidence, pins, target, selected, *, actions=False):
    rules = _actions_contract() if actions else None
    for label, pin in (('recipe', 'recipe'), ('binary_manifest', 'manifest'), ('proof', 'proof'), ('runtime', 'runtime')):
        if _hash(evidence[label]) != pins[pin]:
            _fail('Independent native ' + pin + ' pin mismatch')
    binary = _document(evidence['binary_manifest'], 'native binary manifest')
    source = _document(evidence['source_manifest'], 'native source manifest')
    recipe = _document(evidence['recipe'], 'native recipe')
    manifest.binary_contract(binary)
    manifest.source_contract(source, recipe, pins['recipe'])
    manifest.verify_binding(binary, source, _hash(evidence['source_manifest']), recipe)
    if binary['recipe_id'] != pins['recipe'] or not _same(binary['target'], target):
        _fail('Native full target or recipe differs from consumer selection')
    provider, toolchain = binary['provider'], binary['toolchain']
    if (provider['format'] != 'native-shared' or provider['binding'] != 'c-abi'
            or type(provider['abi_major']) is not int or provider['abi_major'] != 1
            or type(provider['abi_minor']) is not int or provider['abi_minor'] != 1
            or provider['header_sha256'] != contract.BASE_HEADER_SHA256
            or toolchain['runtime_policy'] != BINDING or toolchain['paired_sdk_sha256'] is not None
            or not _same(binary['options'], {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'native'})):
        _fail('Native ABI1.1/private-native Stage-A contract is required; browser SDK/factory evidence is ineligible')
    proof = _document(evidence['proof'], 'native proof')
    contract.require_fields(proof, rules.PROOF_FIELDS if actions else PROOF_FIELDS, 'native proof')
    _version(proof, rules.PROOF_KIND if actions else PROOF_KIND, 'proof')
    references, build_path, runtime_path, reserved = _metadata_paths(binary, proof, selected, actions=actions)
    interfaces = (rules.validate_interface_bytes(references, evidence['interfaces'], actions_profile=selected) if actions else
        contract.validate_interface_bytes(references, evidence['interfaces'], document_profile=selected))
    for path, raw in interfaces.items():
        _member(interfaces, path, binary, contract.MAX_INTERFACE_BYTES, 'interface')
        item = recipe['inputs'].get(path)
        if source['files'].get(path) != _hash(raw) or type(item) is not dict or item.get('sha256') != _hash(raw) or item.get('role') != 'interface':
            _fail('Native interface is not bound to the original source recipe')
    for path, raw, pin in ((binary['build']['link_receipt'], evidence['proof'], pins['proof']),
            (build_path, evidence['provider_build'], proof['provider_build']['sha256']),
            (runtime_path, evidence['runtime'], pins['runtime'])):
        if binary['files'].get(path) != pin or _hash(raw) != pin:
            _fail('Native proof/build/runtime reference differs from inventoried original bytes')
    if (proof['runtime_evidence']['sha256'] != pins['runtime'] or proof['recipe_id'] != pins['recipe']
            or proof['sources_sha256'] != _hash(evidence['source_manifest'])):
        _fail('Native proof source/runtime pin differs')
    build = _document(evidence['provider_build'], 'native provider build')
    contract.require_fields(build, rules.BUILD_FIELDS if actions else BUILD_FIELDS, 'native provider build')
    _version(build, rules.BUILD_KIND if actions else BUILD_KIND, 'provider build')
    observed_contract = (rules.provider_contract(kernel_target=target, actions_profile=selected) if actions else
        provider_contract(kernel_target=target, document_profile=selected))
    provider_limits = (rules.validate_actions_provider_limits(build['provider_limits']) if actions else
        validate_provider_limits(build['provider_limits']))
    if (not _same(build['target'], target) or not _same(build['toolchain'], toolchain)
            or not _same(build['options'], binary['options']) or build['source_recipe_sha256'] != pins['recipe']
            or build['source_inputs_sha256'] != _hash(encoded(recipe['inputs']))
            or build['contract_header_sha256'] != (rules.CONTRACT_SHA256 if actions else contract.CONTRACT_SHA256) or build['binding'] != BINDING
            or not _same(build['configuration'], rules.expected_configuration(actions_profile=selected) if actions else
                expected_configuration(document_profile=selected))
            or build['capabilities'] != ('4083' if actions else '1795') or not _same(build['provider_contract'], observed_contract)):
        _fail('Native build configuration/identity differs from the explicit native contract')
    profile = (rules.validate_engine_profile(proof['engine_profile'], kernel_target=target, actions_profile=selected) if actions else
        validate_engine_profile(proof['engine_profile'], kernel_target=target, document_profile=selected))
    if profile['build_sha256'] != _hash(evidence['provider_build']) or profile['source_recipe_sha256'] != pins['recipe']:
        _fail('Native profile differs from exact provider-build and recipe bytes')
    runtime = _document(evidence['runtime'], 'native runtime evidence')
    contract.require_fields(runtime, rules.RUNTIME_FIELDS if actions else RUNTIME_FIELDS, 'native runtime evidence')
    _version(runtime, rules.RUNTIME_KIND if actions else RUNTIME_KIND, 'runtime evidence')
    if (runtime['scope'] not in ('parser-fixture-only', 'retained-native-provider-runtime')
            or runtime['status'] not in ('passed', 'failed', 'incomplete') or runtime['recipe_id'] != pins['recipe']
            or runtime['provider_build_sha256'] != profile['build_sha256']
            or runtime['assets_sha256'] != _hash(encoded(proof['assets']))
            or runtime['native_facts_sha256'] != _hash(encoded(proof['native_facts']))
            or not _same(runtime['target'], target) or runtime['toolchain_identity_sha256'] != toolchain['identity_sha256']
            or not _same(runtime['engine_profile'], profile)):
        _fail('Original native runtime evidence subject differs from the pinned native closure')
    _environment(runtime['environment'], target)
    observation = runtime['provider_observation']
    contract.require_fields(observation, ('getter','requested_major','maximum_minor','status','provider_contract','provider_limits'), 'native provider observation')
    if not _same(observation, {'getter':GETTER, 'requested_major':1, 'maximum_minor':1, 'status':0,
            'provider_contract':observed_contract, 'provider_limits':provider_limits}):
        _fail('Original native getter/table observation differs from build contract/limits')
    bootstrap = runtime['bootstrap']
    contract.require_fields(bootstrap, ('getter','requested_major','maximum_minor','checks'), 'native bootstrap')
    if not _same({name:bootstrap[name] for name in ('getter','requested_major','maximum_minor')},
            {'getter':GETTER,'requested_major':1,'maximum_minor':1}):
        _fail('Native bootstrap must negotiate getter ABI1.1 before one process START')
    contract.require_fields(bootstrap['checks'], rules.BOOTSTRAP_CHECKS if actions else BOOTSTRAP_CHECKS, 'native bootstrap checks')
    if any(value not in STATUS for value in bootstrap['checks'].values()):
        _fail('Invalid original native bootstrap check status')
    contract.require_fields(runtime['checks'], rules.RUNTIME_CHECKS if actions else RUNTIME_CHECKS, 'native original runtime checks')
    return binary, source, recipe, proof, build, profile, runtime, references, reserved


def _report_references(proof, runtime, reserved):
    references = {}
    checks = list(runtime['checks'].items()) + [('native facts', {'status':'not-run', 'evidence':proof['native_facts']['evidence']})]
    for name, check in checks:
        contract.require_fields(check, ('status','evidence'), 'native original check ' + name)
        if check['status'] not in STATUS or type(check['evidence']) is not list:
            _fail('Invalid original native check status/evidence')
        seen = set()
        for item in check['evidence']:
            path = _reference(item, 'native original report reference')
            if path in reserved or path in seen or path in references and references[path] != item['sha256']:
                _fail('Conflicting/duplicate native original report role/pin')
            references[path] = item['sha256']; seen.add(path)
        if check['status'] == 'passed' and not seen:
            _fail('Passed native check requires original retained evidence')
    return references


def _library_name(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,254}', value) or value in ('.','..'):
        _fail('Native dependency must have one portable bare library name')
    return value


def _system_library(value, target):
    value = _library_name(value)
    if target['system'] == 'Linux':
        return value in _SYSTEM_LINUX and not (value.startswith('ld-linux-') and value != ('ld-linux-x86-64.so.2' if target['processor'] == 'x86_64' else 'ld-linux-aarch64.so.1'))
    return value.lower() in _SYSTEM_WINDOWS or bool(re.fullmatch(r'(api-ms-win|ext-ms-win)-[a-z0-9-]+-l[0-9]+-[0-9]+-[0-9]+\.dll', value.lower()))


def _version_number(value, label):
    if type(value) is not str or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', value):
        _fail('Invalid native ' + label + ' version')
    return tuple(map(int, value.split('.')))


def _runtime_floor(value, target):
    contract.require_fields(value, ('system','minimum_os','GLIBC','GLIBCXX','CXXABI','GCC','CRT','loader_api'), 'native runtime floor')
    if value['system'] != target['system']:
        _fail('Native runtime floor target differs')
    manifest.text(value['minimum_os'], 'native minimum operating system')
    if target['system'] == 'Windows':
        if (not (6,2) <= _version_number(value['minimum_os'], 'Windows floor') <= (10,0)
                or value['CRT'] not in ('ucrt','msvcrt') or any(value[name] is not None for name in BOOKWORM)
                or value['loader_api'] != 'LoadLibraryExW-DLL_LOAD_DIR-SYSTEM32'):
            _fail('Native Windows runtime floor exceeds the supported baseline or loader policy')
    else:
        if value['minimum_os'] != 'Debian 12' or value['CRT'] is not None or value['loader_api'] != 'dlopen-RTLD_NOW-RTLD_LOCAL':
            _fail('Native Linux runtime floor is not the Debian 12 private-loader baseline')
        if value['GLIBC'] is None:
            _fail('Native Linux evidence requires an explicit GLIBC runtime floor')
        for name, maximum in BOOKWORM.items():
            if value[name] is not None and _version_number(value[name], name) > _version_number(maximum, name):
                _fail('Native runtime floor exceeds Debian 12: ' + name)


def _native_facts(proof, assets, target, *, actual, inventory_paths=None):
    facts = proof['native_facts']
    contract.require_fields(facts, ('binaries','dependencies','runtime_floor','private_runtime','evidence'), 'native binary/dependency facts')
    binaries = facts['binaries']
    native_paths = {path for path,item in proof['assets'].items() if item['role'] in ('provider','dependency')}
    if type(binaries) is not dict or set(binaries) != native_paths:
        _fail('Native binary scan facts do not cover every DSO and only DSOs')
    needed = set()
    for path, item in binaries.items():
        contract.require_fields(item, ('format','machine','pointer_bits','exports','imports','needed','soname','runpath'), 'native binary facts')
        if item['format'] != _native_header(assets[path], target) or item['machine'] != target['processor'] or type(item['pointer_bits']) is not int or item['pointer_bits'] != 64:
            _fail('Native binary format/machine differs from actual retained header')
        for field in ('exports','needed','runpath'):
            if (type(item[field]) is not list or any(type(name) is not str or not name or '\0' in name for name in item[field])
                    or len(item[field]) != len(set(item[field])) or field == 'exports' and item[field] != sorted(item[field])):
                _fail('Native binary ' + field + ' must be unique; exports must also be sorted')
        for name in item['needed']:_library_name(name)
        needed.update(item['needed'])
        if item['soname'] is not None:_library_name(item['soname'])
        if target['system'] == 'Windows' and (item['soname'] is not None or item['runpath']):
            _fail('Native Windows binary cannot declare ELF SONAME/RUNPATH')
        if type(item['imports']) is not list:
            _fail('Native imports must be a sorted unique array')
        keys = []
        for imported in item['imports']:
            contract.require_fields(imported, ('library','symbol','version'), 'native import')
            if imported['library'] is not None:_library_name(imported['library'])
            manifest.text(imported['symbol'], 'native imported symbol')
            if imported['version'] is not None:manifest.text(imported['version'], 'native import version')
            keys.append(contract.canonical_json(imported))
        if keys != sorted(set(keys)):
            _fail('Native imports must be sorted and unique')
        if proof['assets'][path]['role'] == 'provider' and item['exports'] != [GETTER]:
            _fail('Native provider exposes an unexpected public or diagnostic entry point')
        for runpath in item['runpath']:
            if runpath != '$ORIGIN':
                if not runpath.startswith('$ORIGIN/'):_fail('Ambient or absolute native RUNPATH is ineligible')
                manifest.path_name(runpath[len('$ORIGIN/'):])
        if actual:
            scanned = scan_native_binary(assets[path])
            if not _same(scanned, item):
                _fail('Declared native exports/imports/dependencies differ from actual bounded binary scan: ' + path)
    dependencies = facts['dependencies']
    if type(dependencies) is not list:
        _fail('Native dependency closure must be an array')
    library_keys = []; retained = set()
    for item in dependencies:
        contract.require_fields(item, ('library','kind','path','sha256'), 'native dependency')
        library = _library_name(item['library']); library_keys.append(library)
        if item['kind'] == 'retained':
            path = item['path']; manifest.path_name(path)
            if path not in native_paths or proof['assets'][path]['role'] != 'dependency' or item['sha256'] != proof['assets'][path]['sha256']:
                _fail('Native retained dependency lacks exact original DSO asset identity')
            if target['system'] == 'Windows' and (Path(path).name.lower() != library.lower()):
                _fail('Windows retained DLL library/path spelling differs')
            if target['system'] == 'Linux' and binaries[path]['soname'] not in (None, library):
                _fail('Retained ELF dependency SONAME differs from lookup name')
            retained.add(path)
        elif item['kind'] == 'system':
            if item['path'] is not None or item['sha256'] is not None or not _system_library(library, target):
                _fail('Unretained native dependency is outside the explicit target system policy')
        else:_fail('Native dependency kind must be retained or system')
    if (library_keys != sorted(set(library_keys)) or set(library_keys) != needed
            or target['system'] == 'Windows' and len({name.lower() for name in library_keys}) != len(library_keys)
            or retained != {path for path in native_paths if proof['assets'][path]['role'] == 'dependency'}):
        _fail('Native dependency graph has duplicate, missing or unreferenced library/DSO records')
    by_library = {item['library']:item for item in dependencies}
    for path, item in binaries.items():
        for name in item['needed']:
            dependency = by_library[name]
            if dependency['kind'] == 'retained':
                destination = dependency['path']
                parent = Path(path).parent
                search = [parent] if target['system'] == 'Windows' else [parent / suffix[len('$ORIGIN/'): ] if suffix != '$ORIGIN' else parent for suffix in item['runpath']]
                # The explicit provider directory is the only allowed private
                # fallback, useful for synthetic NOT RUN fixtures as well.
                if not search and not actual:search = [parent]
                candidates = [(directory / name).as_posix() for directory in search]
                if actual and inventory_paths is None:_fail('Actual native search requires the complete binary path inventory')
                extant = [candidate for candidate in candidates if candidate in (inventory_paths if inventory_paths is not None else assets)]
                if not extant or extant[0] != destination:
                    _fail('Retained native dependency is not reachable under the private loader policy')
        for imported in item['imports']:
            if imported['library'] is not None and imported['library'] not in by_library:
                _fail('Native import supplier lies outside the complete dependency closure')
            version = imported['version']
            if version and target['system'] == 'Linux' and (imported['library'] is None or by_library[imported['library']]['kind'] == 'system'):
                if version == 'GLIBC_ABI_DT_RELR':category, number = 'GLIBC','2.36'
                else:
                    match = re.fullmatch(r'(GLIBCXX|GLIBC|CXXABI|GCC)_([0-9]+(?:\.[0-9]+){1,3})', version)
                    if not match:_fail('Unqualified external native symbol-version namespace: ' + version)
                    category, number = match.groups()
                floor = facts['runtime_floor'].get(category)
                if floor is None or _version_number(number, category) > _version_number(floor, category):
                    _fail('Native system symbol version exceeds declared target runtime floor')
    _runtime_floor(facts['runtime_floor'], target)
    private = facts['private_runtime']
    contract.require_fields(private, ('policy','unique_dependencies','ambient_search','loader_resolution','conflicting_preload'), 'native private runtime')
    if (private['policy'] != BINDING or private['unique_dependencies'] is not True or private['ambient_search'] is not False
            or private['loader_resolution'] not in STATUS or private['conflicting_preload'] not in STATUS):
        _fail('Native runtime is not explicitly private with unique dependencies and observed loader checks')
    if type(facts['evidence']) is not list or not facts['evidence']:
        _fail('Native facts require retained original binary/dependency/runtime-floor evidence')
    return facts


def _observed_path(value, *, windows):
    if (type(value) is not str or '\0' in value or '\\' in value
            or any(part in ('.','..') for part in value.split('/')) or any(not part for part in value.split('/')[1:])):
        _fail('Unsafe original native loader-resolution path')
    if not (re.fullmatch(r'[A-Za-z]:/[^:]+', value) if windows else value.startswith('/') and not value.startswith('//')):
        _fail('Original native loader resolution must preserve its explicit absolute path')
    return value.rstrip('/')


def _audit_closure(facts, proof, runtime, reports, target):
    """Cross-check original audit observations against static retained bytes.

    A report kind/status is insufficient. The audit must preserve the precise
    loaded paths/digests, every needed edge and every symbol resolution, plus
    pinned original tool outputs. Independent caller pins remain the authority
    for these original observations; this static reader never reruns them.
    """
    candidates = []
    for reference in facts['evidence']:
        raw = reports[reference['path']]
        try:
            value = _document(raw, 'native original audit')
        except ValueError:
            continue
        if type(value) is dict and value.get('kind') == 'foundation-native-dso-audit-v1':
            candidates.append(value)
    if len(candidates) != 1:
        _fail('Actual native admission requires one original detailed native DSO audit, not an audit label')
    audit = candidates[0]
    contract.require_fields(audit, ('schema_version','kind','scope','executed','target','assets_sha256',
        'binaries_sha256','dependencies_sha256','runtime_floor_sha256','private_runtime_sha256',
        'environment','runtime_root','tools','outputs','library_resolutions','import_resolutions'), 'original native DSO audit')
    _version(audit, 'foundation-native-dso-audit-v1', 'DSO audit')
    if (audit['scope'] != 'actual-native-binary-audit' or audit['executed'] is not True
            or not _same(audit['target'], target) or audit['assets_sha256'] != _hash(encoded(proof['assets']))
            or any(audit[name + '_sha256'] != _hash(encoded(facts[name])) for name in ('binaries','dependencies','runtime_floor','private_runtime'))
            or not _same(audit['environment'], runtime['environment'])):
        _fail('Original native audit subject differs from retained native bytes and runtime environment')
    windows = target['system'] == 'Windows'
    root = _observed_path(audit['runtime_root'], windows=windows)
    if root in ('/', root[:2]):_fail('Original native audit root must be an owned runtime subtree')
    if type(audit['tools']) is not list or not audit['tools'] or len(audit['tools']) > 16:
        _fail('Original native audit requires bounded inspection-tool identities')
    names = []
    for tool in audit['tools']:
        contract.require_fields(tool, ('name','version','sha256'), 'native original audit tool')
        manifest.text(tool['name'], 'native audit tool name'); manifest.text(tool['version'], 'native audit tool version')
        contract.validate_sha256(tool['sha256'], 'native original audit tool', nonzero=True)
        names.append(tool['name'])
    if names != sorted(set(names)):_fail('Original native audit tools must be sorted and unique')
    if type(audit['outputs']) is not list or not audit['outputs']:
        _fail('Original native audit requires retained original inspection output bytes')
    output_paths = []
    for reference in audit['outputs']:
        path = _reference(reference, 'native original inspection output')
        if path not in reports or _hash(reports[path]) != reference['sha256']:
            _fail('Original native audit output is missing from pinned report closure')
        output_paths.append(path)
    if output_paths != sorted(set(output_paths)):_fail('Original native audit outputs must be sorted and unique')
    by_library = {item['library']:item for item in facts['dependencies']}
    resolved_identities = {}
    def resolution(item, dependency):
        observed = _observed_path(item['resolved_path'], windows=windows)
        contract.validate_sha256(item['resolved_sha256'], 'native actual resolved library', nonzero=True)
        if item['kind'] != dependency['kind'] or item['path'] != dependency['path'] or item['sha256'] != dependency['sha256']:
            _fail('Original loader resolution differs from declared retained/system dependency')
        if dependency['kind'] == 'retained':
            if observed != root + '/' + dependency['path'] or item['resolved_sha256'] != dependency['sha256']:
                _fail('Original loaded private DSO path/digest differs from retained asset')
        elif windows:
            if not re.fullmatch(r'[A-Za-z]:/[Ww][Ii][Nn][Dd][Oo][Ww][Ss]/[Ss][Yy][Ss][Tt][Ee][Mm]32/[^/]+', observed):
                _fail('Original system DLL did not resolve through the Windows system directory')
            name, requested = Path(observed).name.lower(), dependency['library'].lower()
            # Only these explicit API-set families have admitted host aliases.
            aliases = ({'ucrtbase.dll'} if requested.startswith('api-ms-win-crt-') else
                {'kernelbase.dll','kernel32.dll','ntdll.dll'} if requested.startswith('api-ms-win-core-') else set())
            if not _system_library(name, target) or name != requested and name not in aliases:
                _fail('Original system DLL name differs from the requested library or explicit API-set mapping')
        else:
            name, requested = Path(observed).name, dependency['library']
            if (not observed.startswith(('/lib/','/lib64/','/usr/lib/','/usr/lib64/'))
                    or not re.fullmatch(re.escape(requested) + r'(?:\.[0-9]+)*', name)):
                _fail('Original system ELF dependency resolved outside the explicit target runtime')
        key = dependency['library'].lower() if windows else dependency['library']
        identity = (observed.lower() if windows else observed, item['resolved_sha256'])
        if key in resolved_identities and resolved_identities[key] != identity:
            _fail('Original native dependency resolved to conflicting loaded paths/digests within one process')
        resolved_identities[key] = identity
    expected_edges = {(path,name) for path,item in facts['binaries'].items() for name in item['needed']}
    if type(audit['library_resolutions']) is not list:_fail('Original native needed-library resolutions must be an array')
    edges = []
    for item in audit['library_resolutions']:
        contract.require_fields(item, ('requester','library','kind','path','sha256','resolved_path','resolved_sha256'), 'native needed-library resolution')
        key = (item['requester'], item['library'])
        if key not in expected_edges:_fail('Unexpected original native needed-library resolution')
        resolution(item, by_library[item['library']]); edges.append(key)
    if edges != sorted(expected_edges):_fail('Original native needed-library resolutions are incomplete, repeated or unsorted')
    expected_imports = {(path,item['library'],item['symbol'],item['version']) : item for path,binary in facts['binaries'].items() for item in binary['imports']}
    if type(audit['import_resolutions']) is not list:_fail('Original native symbol resolutions must be an array')
    import_keys = []
    for item in audit['import_resolutions']:
        contract.require_fields(item, ('requester','symbol','version','library','kind','path','sha256','resolved_path','resolved_sha256'), 'native symbol resolution')
        matches = [key for key in expected_imports if key[0] == item['requester'] and key[2:] == (item['symbol'],item['version'])
            and key[1] in (None,item['library'])]
        if len(matches) != 1 or item['library'] not in by_library:
            _fail('Original native symbol supplier differs from the scanned import/dependency closure')
        key = matches[0]
        dependency = by_library[item['library']]
        resolution(item, dependency)
        if dependency['kind'] == 'retained':
            if windows and item['symbol'].startswith('#'):
                _fail('Retained ordinal DLL imports require an ordinal export contract not admitted by this initial schema')
            if item['symbol'] not in facts['binaries'][dependency['path']]['exports']:
                _fail('Original retained symbol supplier does not actually export the scanned imported symbol')
        import_keys.append(key)
    sort_import = lambda key: (key[0],key[1] or '',key[2],key[3] or '')
    if import_keys != sorted(expected_imports, key=sort_import):
        _fail('Original native symbol resolutions are incomplete, repeated or unsorted')
    return {'scope':'actual-native-binary-audit', 'binary_scan_verified':True,
        'needed_edges':len(edges), 'symbol_resolutions':len(import_keys), 'original_outputs':output_paths}


def _inspect(evidence, assets, notices, pins, kernel_target, document_profile, limits, group_files=None, *, actions=False):
    selected, target, limits = _selection(kernel_target, document_profile, limits, actions=actions)
    pins, evidence = _pins(pins), _evidence(evidence)
    assets, notices = _mapping(assets, 'native asset'), _mapping(notices, 'native notice')
    binary, source, recipe, proof, build, profile, runtime, interfaces, reserved = _documents(evidence, pins, target, selected, actions=actions)
    _path_inventory(binary, limits)
    records = _asset_records(proof, binary, limits)
    if set(assets) != set(records):_fail('Native owned assets differ from exact proof closure')
    for path, item in records.items():
        maximum = limits.max_data_member_bytes if item['role'] == 'data' else limits.max_native_member_bytes
        raw = _member(assets, path, binary, maximum, 'asset')
        if len(raw) != item['bytes']:_fail('Native asset size differs from declared retained bytes')
    if set(notices) != set(binary['licenses']) or not 1 <= len(notices) <= limits.max_notices:
        _fail('Native notices differ from complete original license closure')
    notice_records, total_notices = {}, 0
    for path, raw in notices.items():
        raw = _member(notices, path, binary, limits.max_notice_bytes, 'notice')
        total_notices += len(raw)
        if not raw or source['files'].get(path) != _hash(raw) or recipe['inputs'].get(path, {}).get('role') != 'license':
            _fail('Native notice lacks exact original source-license identity')
        notice_records[path] = {'sha256':_hash(raw),'bytes':len(raw),'mode':binary['modes'][path]}
    if total_notices > limits.max_notices_total_bytes:_fail('Native notice aggregate bound exceeded')
    actual = runtime['scope'] == 'retained-native-provider-runtime'
    facts = _native_facts(proof, assets, target, actual=actual, inventory_paths=set(binary['files']) | set(binary['directories']) | {'engine-sdk.json'})
    report_refs = _report_references(proof, runtime, reserved | set(assets) | set(notices))
    if set(evidence['reports']) != set(report_refs):_fail('Native original reports differ from complete referenced closure')
    total_reports = 0
    for path, pin in report_refs.items():
        raw = _member(evidence['reports'], path, binary, limits.max_reports_total_bytes, 'original report')
        total_reports += len(raw)
        if not raw or _hash(raw) != pin:_fail('Original native report differs from reference pin or is empty')
    if total_reports > limits.max_reports_total_bytes:_fail('Original native report aggregate bound exceeded')
    audit = _audit_closure(facts, proof, runtime, evidence['reports'], target) if actual else {
        'scope':'synthetic-header-only-no-binary-contract-proof','binary_scan_verified':False,
        'needed_edges':0,'symbol_resolutions':0,'original_outputs':[]}
    members = {**assets, **notices, **evidence['interfaces'], **evidence['reports'],
        binary['build']['link_receipt']:evidence['proof'], proof['provider_build']['path']:evidence['provider_build'],
        proof['runtime_evidence']['path']:evidence['runtime']}
    if set(members) != set(binary['files']):
        _fail('Native complete binary inventory contains missing, extra or unassigned runtime members')
    inventory = [{'path':path,'kind':'file','mode':binary['modes'][path], 'bytes':len(raw),'sha256':_hash(raw)} for path,raw in members.items()]
    inventory.append({'path':'engine-sdk.json','kind':'file','mode':0o644,'bytes':len(evidence['binary_manifest']),'sha256':pins['manifest']})
    inventory.extend({'path':path,'kind':'directory','mode':binary['modes'][path],'bytes':0,'sha256':None} for path in binary['directories'])
    inventory.sort(key=lambda item:item['path'])
    whole = group_files is not None
    eligible = (whole and actual and runtime['status'] == 'passed'
        and all(item['status'] == 'passed' for item in runtime['checks'].values())
        and all(value == 'passed' for value in runtime['bootstrap']['checks'].values())
        and all(facts['private_runtime'][name] == 'passed' for name in ('loader_resolution','conflicting_preload')))
    scope = ((_actions_contract().SCOPE if whole else _actions_contract().EMBEDDED_SCOPE) if actions else
        (SCOPE if whole else EMBEDDED_SCOPE))
    metadata = {'schema_version':1, 'scope':scope, 'whole_group_verified':whole,
        'production_eligible':bool(eligible), 'recipe_id':pins['recipe'], 'binary_manifest_sha256':pins['manifest'],
        'proof_sha256':pins['proof'], 'runtime_sha256':pins['runtime'], 'source_manifest_sha256':_hash(evidence['source_manifest']),
        'provider_build_sha256':profile['build_sha256'], 'group_files':group_files,
        'engine_profile':profile, 'provider_contract':build['provider_contract'], 'provider_limits':build['provider_limits'],
        'interfaces':interfaces, 'assets':records, 'notices':notice_records,
        'provider_entry':binary['provider']['entry'], 'inventory':inventory, 'native_facts':facts,
        'native_audit':audit, 'runtime_evidence':runtime}
    return NativeConsumerInspection(_freeze(metadata),_freeze(assets),_freeze(notices),_freeze(evidence))


@_public
def inspect_embedded_consumer(*, evidence, assets, notices, pins, kernel_target, document_profile, limits=None):
    return _inspect(evidence, assets, notices, pins, kernel_target, document_profile, limits)


@_public
def inspect_embedded_actions_consumer(*, evidence, assets, notices, pins, kernel_target,
                                      actions_profile='document-actions-v1', limits=None):
    return _inspect(evidence, assets, notices, pins, kernel_target, actions_profile, limits, actions=True)


def _read_members(archive_path, wanted, *, aggregate_limit=None):
    """Materialize named bounded members only after full Stage-A verification."""
    result, total = {}, 0
    with tarfile.open(archive_path, 'r:*') as archive:
        for member in archive:
            if member.name not in wanted:continue
            selected = wanted[member.name]
            maximum, expected = selected if isinstance(selected, tuple) else (selected, None)
            total += member.size
            if (member.name in result or not member.isfile() or member.size < 0 or member.size > maximum
                    or expected is not None and member.size != expected
                    or aggregate_limit is not None and total > aggregate_limit):
                _fail('Duplicate/oversized/nonordinary native consumer archive member')
            with archive.extractfile(member) as stream:raw = stream.read(member.size + 1)
            if len(raw) != member.size:_fail('Native retained archive member changed or truncated')
            result[member.name] = raw
    if set(result) != set(wanted):_fail('Missing retained native consumer archive members')
    return result


def _inspect_kernel_consumer(group, *, expected_recipe, expected_manifest, expected_proof, expected_runtime,
                             kernel_target, document_profile, limits=None, actions=False):
    selected, target, limits = _selection(kernel_target, document_profile, limits, actions=actions)
    rules = _actions_contract() if actions else None
    pins = _pins({'recipe':expected_recipe,'manifest':expected_manifest,'proof':expected_proof,'runtime':expected_runtime})
    verified = sdk.verify_group(group, expected_recipe)
    if verified['binary_manifest_sha256'] != expected_manifest:_fail('Independent native manifest pin mismatch')
    root = manifest.ordinary_root(group)
    binary_name, source_name, _ = sdk.group_names(expected_recipe)
    binary_path, source_path = root / binary_name, root / source_name
    raw_binary = _read_members(binary_path, {'engine-sdk.json':manifest.MAX_MANIFEST})['engine-sdk.json']
    if _hash(raw_binary) != expected_manifest:_fail('Independent native manifest bytes mismatch')
    binary = _document(raw_binary, 'native binary manifest'); manifest.binary_contract(binary); _path_inventory(binary, limits)
    proof_path = binary['build']['link_receipt']
    raw_proof = _read_members(binary_path, {proof_path:manifest.MAX_MANIFEST})[proof_path]
    if _hash(raw_proof) != expected_proof:_fail('Independent native proof pin mismatch')
    proof = _document(raw_proof, 'native proof')
    contract.require_fields(proof, rules.PROOF_FIELDS if actions else PROOF_FIELDS, 'native proof')
    _version(proof, rules.PROOF_KIND if actions else PROOF_KIND, 'proof')
    references, build_path, runtime_path, _ = _metadata_paths(binary, proof, selected, actions=actions)
    interfaces = _read_members(binary_path, {item['path']:contract.MAX_INTERFACE_BYTES for item in references.values()},
        aggregate_limit=rules.MAX_INTERFACES_BYTES if actions else contract.MAX_INTERFACES_BYTES)
    documents = _read_members(binary_path, {build_path:manifest.MAX_MANIFEST,runtime_path:manifest.MAX_MANIFEST})
    sources = _read_members(source_path, {'recipe.json':manifest.MAX_MANIFEST,'sources.json':manifest.MAX_MANIFEST})
    evidence = {'binary_manifest':raw_binary,'source_manifest':sources['sources.json'],'recipe':sources['recipe.json'],
        'proof':raw_proof,'provider_build':documents[build_path],'runtime':documents[runtime_path], 'interfaces':interfaces,'reports':{}}
    _, _, _, _, _, _, runtime, _, reserved = _documents(evidence, pins, target, selected, actions=actions)
    records = _asset_records(proof, binary, limits)
    # Validate the facts envelope before selecting its report references.
    contract.require_fields(proof['native_facts'], ('binaries','dependencies','runtime_floor','private_runtime','evidence'), 'native facts')
    report_refs = _report_references(proof, runtime, reserved | set(records) | set(binary['licenses']))
    assets = _read_members(binary_path, {path:((limits.max_data_member_bytes if item['role'] == 'data' else limits.max_native_member_bytes),item['bytes']) for path,item in records.items()},
        aggregate_limit=limits.max_native_total_bytes + limits.max_data_total_bytes)
    if len(binary['licenses']) > limits.max_notices:_fail('Native notice count exceeds bound')
    notices = _read_members(binary_path, {path:limits.max_notice_bytes for path in binary['licenses']}, aggregate_limit=limits.max_notices_total_bytes)
    evidence['reports'] = _read_members(binary_path, {path:limits.max_reports_total_bytes for path in report_refs}, aggregate_limit=limits.max_reports_total_bytes)
    result = _inspect(evidence, assets, notices, pins, target, selected, limits, verified['files'], actions=actions)
    if sdk.group_snapshot(root, expected_recipe) != verified['files']:_fail('Native retained group changed during inspection')
    return result


@_public
def inspect_kernel_consumer(group, *, expected_recipe, expected_manifest, expected_proof, expected_runtime,
                            kernel_target, document_profile, limits=None):
    return _inspect_kernel_consumer(group, expected_recipe=expected_recipe, expected_manifest=expected_manifest,
        expected_proof=expected_proof, expected_runtime=expected_runtime, kernel_target=kernel_target,
        document_profile=document_profile, limits=limits)


@_public
def inspect_actions_kernel_consumer(group, *, expected_recipe, expected_manifest, expected_proof, expected_runtime,
                                    kernel_target, actions_profile='document-actions-v1', limits=None):
    return _inspect_kernel_consumer(group, expected_recipe=expected_recipe, expected_manifest=expected_manifest,
        expected_proof=expected_proof, expected_runtime=expected_runtime, kernel_target=kernel_target,
        document_profile=actions_profile, limits=limits, actions=True)


@_public
def verify_actions_kernel_consumer(group, **kwargs):
    result = inspect_actions_kernel_consumer(group, **kwargs)
    if not result.metadata['production_eligible']:
        _fail('Native actions retained engine is production-ineligible: original actual binary/dependency/runtime evidence remains required; parser fixtures never qualify')
    return result


@_public
def verify_kernel_consumer(group, **kwargs):
    result = inspect_kernel_consumer(group, **kwargs)
    if not result.metadata['production_eligible']:
        _fail('Native retained engine is production-ineligible: original actual binary/dependency/runtime evidence remains required; parser fixtures never qualify')
    return result


# Bounded static parser: frozen source candidate 0e8590cd30beb57fe44f16dc051a1f6e45b68e80fa697cc116ac2167dfcb7359.
class NativeBinaryError(ValueError):
    pass


_NATIVE_MAX_RECORDS = 262144
_NATIVE_MAX_NAME = 4096


def _native_fail(message):
    raise NativeBinaryError(message)


def _native_span(raw, offset, count, label):
    if (type(offset) is not int or type(count) is not int or offset < 0 or count < 0
            or offset > len(raw) or count > len(raw)-offset):
        _native_fail('Truncated/out-of-range native '+label)
    return memoryview(raw)[offset:offset+count]


def _native_unpack(raw, layout, offset, label):
    return struct.unpack(layout,_native_span(raw,offset,struct.calcsize(layout),label))


def _native_text(raw, offset, limit, label):
    view = _native_span(raw,offset,limit,label)
    end = bytes(view[:min(limit,_NATIVE_MAX_NAME+1)]).find(b'\0')
    if end < 0 or end > _NATIVE_MAX_NAME:
        _native_fail('Unterminated/oversized native '+label)
    try:
        value = bytes(view[:end]).decode('utf-8','strict')
    except UnicodeError as error:
        raise NativeBinaryError('Invalid UTF-8 native '+label) from error
    if any(ord(character)<32 or ord(character)==127 for character in value):
        _native_fail('Control character in native '+label)
    return value


def _native_import_order(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)


def _scan_native_elf(raw):
    header = _native_span(raw,0,64,'ELF header')
    if bytes(header[:7]) != b'\x7fELF\x02\x01\x01':
        _native_fail('Only ELF64 little-endian version1 is admitted')
    kind,machine,version,entry,phoff,shoff,flags,ehsize,phentsize,phnum,shentsize,shnum,shstrndx = _native_unpack(
        raw,'<HHIQQQIHHHHHH',16,'ELF header')
    if kind!=3 or machine not in (62,183) or version!=1 or ehsize!=64:
        _native_fail('ELF must be a supported 64-bit ET_DYN image')
    if not shoff or not 1 <= shnum <= 8192 or shentsize!=64 or shstrndx==0xffff or shstrndx>=shnum:
        _native_fail('ELF needs ordinary bounded section tables; extended/absent tables are unsupported')
    _native_span(raw,shoff,shnum*64,'ELF section table')
    if not 1 <= phnum <= 8192 or phentsize!=56:
        _native_fail('ELF needs bounded actual program headers')
    _native_span(raw,phoff,phnum*56,'ELF program headers')
    loads=[]
    dynamic_segments=[]
    for index in range(phnum):
        type_,segment_flags,offset,address,physical,size,memory_size,alignment=_native_unpack(
            raw,'<IIQQQQQQ',phoff+56*index,'ELF program header')
        if size:
            _native_span(raw,offset,size,'ELF segment')
        if memory_size<size or address+memory_size>1<<64:
            _native_fail('Invalid ELF segment size/address')
        if type_==1:
            if alignment not in (0,1) and (alignment & (alignment-1) or offset%alignment!=address%alignment):
                _native_fail('Invalid ELF load alignment')
            for previous in loads:
                if address<previous['address']+previous['memory_size'] and previous['address']<address+memory_size:
                    _native_fail('Overlapping ELF load segments are unsupported')
            loads.append({'offset':offset,'address':address,'size':size,'memory_size':memory_size,'flags':segment_flags})
        elif type_==2:
            dynamic_segments.append({'offset':offset,'address':address,'size':size})
        elif type_==3:
            _native_fail('ELF interpreter-bearing images are outside the DSO subset')
    if not loads or len(dynamic_segments)!=1:
        _native_fail('ELF needs actual load and unique dynamic program segments')
    def virtual(address,size,label):
        for segment in loads:
            if segment['address']<=address and address-segment['address']<=segment['size']:
                delta=address-segment['address']
                if size<=segment['size']-delta:
                    return segment['offset']+delta
        _native_fail('ELF dynamic '+label+' is not backed by a load segment')
    sections=[]
    for index in range(shnum):
        name,type_,section_flags,address,offset,size,link,info,alignment,entsize = _native_unpack(
            raw,'<IIQQQQIIQQ',shoff+index*64,'ELF section')
        if type_!=8:
            _native_span(raw,offset,size,'ELF section content')
        sections.append({'type':type_,'address':address,'offset':offset,'size':size,
                         'link':link,'info':info,'entsize':entsize})
    if any(sections[0].values()):
        _native_fail('ELF null section must be empty')
    def only(type_,label,required=False):
        found=[(index,value) for index,value in enumerate(sections) if value['type']==type_]
        if len(found)>1 or required and not found:
            _native_fail('Missing/ambiguous ELF '+label)
        return found[0] if found else (None,None)
    sym_index,symbols=only(11,'dynamic symbol table',True)
    dynamic_index,dynamic=only(6,'dynamic table',True)
    if any(dynamic[key]!=dynamic_segments[0][key] for key in ('offset','address','size')):
        _native_fail('ELF section dynamic table differs from actual PT_DYNAMIC')
    if symbols['entsize']!=24 or symbols['size']%24 or symbols['link']>=shnum:
        _native_fail('Invalid ELF dynamic symbol shape/link')
    strings=sections[symbols['link']]
    if strings['type']!=3 or not strings['size'] or strings['size']>64*1024*1024:
        _native_fail('Invalid ELF dynamic string table')
    for selected in (symbols,dynamic,strings):
        if virtual(selected['address'],selected['size'],'table')!=selected['offset']:
            _native_fail('ELF table section differs from its actual load mapping')
    if raw[strings['offset']]!=0 or raw[strings['offset']+strings['size']-1]!=0:
        _native_fail('ELF string table is not NUL bounded')
    cache={}
    def text(index,label):
        if not 0 <= index < strings['size']:
            _native_fail('Invalid ELF string offset')
        if index not in cache:
            if len(cache)>=_NATIVE_MAX_RECORDS:
                _native_fail('ELF string count exceeds bound')
            cache[index]=_native_text(raw,strings['offset']+index,strings['size']-index,label)
        return cache[index]
    if (dynamic['link']!=symbols['link'] or dynamic['entsize']!=16
            or not dynamic['size'] or dynamic['size']%16 or dynamic['size']//16>65536):
        _native_fail('Invalid ELF dynamic shape/string link')
    tags={}
    ended=False
    for offset in range(dynamic['offset'],dynamic['offset']+dynamic['size'],16):
        tag,value=_native_unpack(raw,'<qQ',offset,'ELF dynamic entry')
        if ended:
            if tag or value:
                _native_fail('Nonempty ELF dynamic entry after DT_NULL')
            continue
        if tag==0:
            if value:
                _native_fail('Invalid ELF DT_NULL value')
            ended=True
        else:
            tags.setdefault(tag,[]).append(value)
    if not ended:
        _native_fail('ELF dynamic table lacks DT_NULL')
    def tag_one(tag,label,required=False):
        values=tags.get(tag,[])
        if len(values)>1 or required and not values:
            _native_fail('Missing/duplicate ELF '+label)
        return values[0] if values else None
    if (tag_one(5,'DT_STRTAB',True)!=strings['address']
            or tag_one(10,'DT_STRSZ',True)!=strings['size']
            or tag_one(6,'DT_SYMTAB',True)!=symbols['address']
            or tag_one(11,'DT_SYMENT',True)!=24):
        _native_fail('ELF dynamic pointers/sizes disagree with actual linked sections')
    if any(tag in tags for tag in (15,0x7fffffff,0x7ffffffd,0x6ffffefb,0x6ffffefc)):
        _native_fail('ELF RPATH/filter/auxiliary/audit loader extensions are unsupported')
    needed=[text(value,'DT_NEEDED') for value in tags.get(1,[])]
    if any(not value for value in needed) or len(needed)>4096 or len(set(needed))!=len(needed):
        _native_fail('Invalid/duplicate ELF DT_NEEDED')
    soname_index=tag_one(14,'DT_SONAME')
    soname=None if soname_index is None else text(soname_index,'DT_SONAME')
    if soname=='':
        _native_fail('Empty ELF SONAME')
    runpath_index=tag_one(29,'DT_RUNPATH')
    runpath=[] if runpath_index is None else text(runpath_index,'DT_RUNPATH').split(':')
    if len(runpath)>1024:
        _native_fail('ELF RUNPATH component count exceeds bound')
    count=symbols['size']//24
    if not 1 <= count <= _NATIVE_MAX_RECORDS:
        _native_fail('ELF dynamic symbol count exceeds bound')
    # The loader discovers symbols through these actual hash tables, not the
    # section-header count. Join both views before trusting the symbol extent.
    hash_members=set()
    sysv_checks={}
    gnu_checks={}
    gnu_bloom=[]
    gnu_bloom_shift=0
    sysv_hash=tag_one(4,'DT_HASH')
    gnu_hash=tag_one(0x6ffffef5,'DT_GNU_HASH')
    if sysv_hash is None and gnu_hash is None:
        _native_fail('ELF dynamic symbols need an actual loader hash table')
    if sysv_hash is not None:
        offset=virtual(sysv_hash,8,'SysV hash header')
        buckets,chains=_native_unpack(raw,'<II',offset,'ELF SysV hash header')
        if not 1 <= buckets <= _NATIVE_MAX_RECORDS or chains!=count:
            _native_fail('ELF SysV hash/symbol count mismatch')
        offset=virtual(sysv_hash,8+4*(buckets+chains),'SysV hash table')
        bucket_values=[_native_unpack(raw,'<I',offset+8+4*index,'ELF hash bucket')[0] for index in range(buckets)]
        chain_values=[_native_unpack(raw,'<I',offset+8+4*buckets+4*index,'ELF hash chain')[0] for index in range(chains)]
        if any(value>=count for value in bucket_values+chain_values):
            _native_fail('Invalid ELF SysV hash index')
        visited={0}
        for bucket_index,first in enumerate(bucket_values):
            chain=set()
            current=first
            while current not in visited:
                if current in chain:
                    _native_fail('Cyclic ELF SysV hash chain')
                chain.add(current)
                sysv_checks[current]=(bucket_index,buckets)
                current=chain_values[current]
            if current:
                _native_fail('Overlapping ELF SysV hash bucket chains')
            visited.update(chain)
            hash_members.update(chain)
    if gnu_hash is not None:
        offset=virtual(gnu_hash,16,'GNU hash header')
        buckets,symbol_offset,bloom_words,bloom_shift=_native_unpack(raw,'<IIII',offset,'ELF GNU hash header')
        if (not 1 <= buckets <= _NATIVE_MAX_RECORDS or not 1 <= symbol_offset <= count
                or not 1 <= bloom_words <= _NATIVE_MAX_RECORDS or bloom_words & (bloom_words-1) or bloom_shift>=64):
            _native_fail('Invalid ELF GNU hash header')
        total=16+8*bloom_words+4*buckets+4*(count-symbol_offset)
        offset=virtual(gnu_hash,total,'GNU hash table')
        bucket_at=offset+16+8*bloom_words
        chains_at=bucket_at+4*buckets
        gnu_bloom=[_native_unpack(raw,'<Q',offset+16+8*index,'ELF GNU bloom word')[0] for index in range(bloom_words)]
        gnu_bloom_shift=bloom_shift
        maximum=symbol_offset
        for index in range(buckets):
            current=_native_unpack(raw,'<I',bucket_at+4*index,'ELF GNU hash bucket')[0]
            if not current:
                continue
            if not symbol_offset<=current<count:
                _native_fail('Invalid ELF GNU hash bucket index')
            for current in range(current,count):
                if current in gnu_checks:
                    _native_fail('Overlapping ELF GNU hash bucket chains')
                hash_members.add(current)
                chain=_native_unpack(raw,'<I',chains_at+4*(current-symbol_offset),'ELF GNU hash chain')[0]
                gnu_checks[current]=(index,buckets,chain)
                maximum=max(maximum,current+1)
                if chain & 1:
                    break
            else:
                _native_fail('ELF GNU hash chain lacks a bounded terminator')
        if maximum!=count:
            _native_fail('ELF GNU hash/symbol extent mismatch')
    versym_index,versym=only(0x6fffffff,'version-symbol table')
    verneed_index,verneed=only(0x6ffffffe,'version-needs table')
    verdef_index,verdef=only(0x6ffffffd,'version-definitions table')
    def version_section(section,address_tag,count_tag,label):
        address=tag_one(address_tag,label+' address')
        declared=tag_one(count_tag,label+' count')
        if section is None:
            if address is not None or declared is not None:
                _native_fail('ELF '+label+' tags lack their section')
            return 0
        if (section['link']!=symbols['link'] or address!=section['address']
                or declared is None or not 1 <= declared <= 4096 or declared!=section['info']):
            _native_fail('ELF '+label+' section/tags disagree')
        if virtual(section['address'],section['size'],label)!=section['offset']:
            _native_fail('ELF version section differs from actual load mapping')
        return declared
    needs_count=version_section(verneed,0x6ffffffe,0x6fffffff,'version needs')
    definitions_count=version_section(verdef,0x6ffffffc,0x6ffffffd,'version definitions')
    versions={}
    definitions={}
    if versym is None:
        if tag_one(0x6ffffff0,'DT_VERSYM') is not None or verneed is not None or verdef is not None:
            _native_fail('ELF version tables lack version-symbol joins')
    elif (versym['link']!=sym_index or versym['entsize'] not in (0,2) or versym['size']!=count*2
          or tag_one(0x6ffffff0,'DT_VERSYM')!=versym['address']):
        _native_fail('ELF version-symbol table shape/tags disagree')
    elif virtual(versym['address'],versym['size'],'version symbols')!=versym['offset']:
        _native_fail('ELF version-symbol section differs from load mapping')
    def local(section,offset,size,label):
        if offset<0 or offset>section['size'] or size>section['size']-offset:
            _native_fail('Out-of-range ELF '+label)
        return section['offset']+offset
    position=0
    for ordinal in range(needs_count):
        at=local(verneed,position,16,'version need')
        version_,aux_count,file_index,aux_offset,next_offset=_native_unpack(raw,'<HHIII',at,'version need')
        library=text(file_index,'version need library')
        if version_!=1 or not 1 <= aux_count <= 4096 or aux_offset<16 or library not in needed:
            _native_fail('Unsupported ELF version-need entry')
        auxiliary=position+aux_offset
        for child in range(aux_count):
            at=local(verneed,auxiliary,16,'version need auxiliary')
            hash_,flags_,index,name_index,next_aux=_native_unpack(raw,'<IHHII',at,'version need auxiliary')
            index &= 0x7fff
            version_name=text(name_index,'import version')
            if index<2 or index in versions or not version_name or flags_ & ~3:
                _native_fail('Invalid/duplicate ELF import version')
            versions[index]=(library,version_name)
            if child+1<aux_count:
                if next_aux<16:
                    _native_fail('Invalid ELF version auxiliary chain')
                auxiliary+=next_aux
            elif next_aux:
                _native_fail('Unexpected trailing ELF version auxiliary')
        if ordinal+1<needs_count:
            if next_offset<16:
                _native_fail('Invalid ELF version needs chain')
            position+=next_offset
        elif next_offset:
            _native_fail('Unexpected trailing ELF version need')
    position=0
    for ordinal in range(definitions_count):
        at=local(verdef,position,20,'version definition')
        version_,flags_,index,aux_count,hash_,aux_offset,next_offset=_native_unpack(raw,'<HHHHIII',at,'version definition')
        index &= 0x7fff
        if version_!=1 or not index or index in definitions or index in versions or not 1 <= aux_count <= 256 or aux_offset<20 or flags_ & ~3:
            _native_fail('Invalid ELF version definition')
        auxiliary=position+aux_offset
        definition_name=None
        for child in range(aux_count):
            at=local(verdef,auxiliary,8,'version definition auxiliary')
            name_index,next_aux=_native_unpack(raw,'<II',at,'version definition auxiliary')
            value=text(name_index,'export version')
            if not value:
                _native_fail('Empty ELF export version')
            if child==0:
                definition_name=value
            if child+1<aux_count:
                if next_aux<8:
                    _native_fail('Invalid ELF version-definition auxiliary chain')
                auxiliary+=next_aux
            elif next_aux:
                _native_fail('Unexpected trailing ELF version-definition auxiliary')
        definitions[index]=definition_name
        if ordinal+1<definitions_count:
            if next_offset<20:
                _native_fail('Invalid ELF version-definitions chain')
            position+=next_offset
        elif next_offset:
            _native_fail('Unexpected trailing ELF version definition')
    exports=set()
    imports=[]
    seen_imports=set()
    for index in range(count):
        name_index,info,other,section_index,value,size=_native_unpack(raw,'<IBBHQQ',symbols['offset']+24*index,'ELF dynamic symbol')
        if index==0:
            if name_index or info or other or section_index or value or size:
                _native_fail('ELF dynamic null symbol must be empty')
            continue
        symbol=text(name_index,'dynamic symbol')
        if index in sysv_checks:
            hash_=0
            for byte in symbol.encode('utf-8'):
                hash_=(hash_<<4)+byte
                high=hash_ & 0xf0000000
                if high:hash_ ^= high>>24
                hash_ &= ~high
            bucket,buckets=sysv_checks[index]
            if hash_%buckets!=bucket:
                _native_fail('ELF SysV bucket disagrees with actual symbol hash')
        if index in gnu_checks:
            hash_=5381
            for byte in symbol.encode('utf-8'):hash_=((hash_<<5)+hash_+byte)&0xffffffff
            bucket,buckets,chain=gnu_checks[index]
            word=gnu_bloom[(hash_//64)%len(gnu_bloom)]
            mask=(1<<(hash_%64))|(1<<((hash_>>gnu_bloom_shift)%64))
            if hash_%buckets!=bucket or hash_ & ~1 != chain & ~1 or word & mask != mask:
                _native_fail('ELF GNU bucket/chain/bloom disagrees with actual symbol hash')
        version_bits=1 if versym is None else _native_unpack(raw,'<H',versym['offset']+2*index,'version symbol')[0]
        version_index=version_bits&0x7fff
        undefined=section_index==0
        if version_index>=2 and version_index not in (versions if undefined else definitions):
            _native_fail('ELF symbol references an unknown/mismatched version index')
        if info>>4 not in (1,2,10) or other & 3 not in (0,3):
            continue
        if not symbol:
            _native_fail('Visible ELF dynamic symbol has no name')
        if undefined:
            if version_index==0:
                _native_fail('Global ELF import cannot have local version index')
            library,version_name=versions.get(version_index,(None,None))
            key=(library,symbol,version_name)
            if key in seen_imports:
                _native_fail('Duplicate ELF imported symbol/version')
            seen_imports.add(key)
            imports.append({'library':library,'symbol':symbol,'version':version_name})
        elif version_index!=0:
            if symbol=='bib_engine_get_provider_v1' and version_bits&0x8000:
                _native_fail('Native ELF getter cannot be a nondefault version-only export')
            if symbol=='bib_engine_get_provider_v1' and (info & 15 != 2 or not any(
                    segment['flags'] & 1 and segment['address'] <= value < segment['address'] + segment['size']
                    and size <= segment['size'] - (value - segment['address']) for segment in loads)):
                _native_fail('Native ELF getter must be an ordinary function in file-backed executable memory, never data or IFUNC')
            if (sysv_hash is not None and index not in sysv_checks
                    or gnu_hash is not None and index not in gnu_checks):
                _native_fail('Visible ELF export is absent from actual loader hashes')
            exports.add(symbol)
    return {'format':'elf64-le','machine':'x86_64' if machine==62 else 'aarch64','pointer_bits':64,
        'exports':sorted(exports),'imports':sorted(imports,key=_native_import_order),
        'needed':needed,'soname':soname,'runpath':runpath}


def _scan_native_pe(raw):
    if bytes(_native_span(raw,0,2,'DOS signature'))!=b'MZ':
        _native_fail('Invalid DOS/PE signature')
    nt=_native_unpack(raw,'<I',60,'DOS PE offset')[0]
    if nt<64 or bytes(_native_span(raw,nt,4,'PE signature'))!=b'PE\0\0':
        _native_fail('Invalid PE signature offset')
    machine,section_count,timestamp,symbols,symbol_count,optional_size,characteristics=_native_unpack(raw,'<HHIIIHH',nt+4,'PE COFF header')
    if machine!=0x8664 or not characteristics & 0x2000 or not characteristics & 2 or not 1 <= section_count <= 96:
        _native_fail('PE must be an x86_64 DLL with ordinary bounded sections')
    optional=nt+24
    _native_span(raw,optional,optional_size,'PE optional header')
    if not 112 <= optional_size <= 4096 or _native_unpack(raw,'<H',optional,'PE optional magic')[0]!=0x20b:
        _native_fail('Only PE32+ optional headers are admitted')
    headers_size=_native_unpack(raw,'<I',optional+60,'PE SizeOfHeaders')[0]
    image_size=_native_unpack(raw,'<I',optional+56,'PE SizeOfImage')[0]
    section_alignment,file_alignment=_native_unpack(raw,'<II',optional+32,'PE alignments')
    if (not 4096<=section_alignment<=1<<20 or section_alignment&(section_alignment-1)
            or not 512<=file_alignment<=65536 or file_alignment&(file_alignment-1)
            or file_alignment>section_alignment or headers_size%file_alignment
            or image_size<=headers_size or image_size%section_alignment):
        _native_fail('Unsupported/invalid PE image or file alignment')
    directory_count=_native_unpack(raw,'<I',optional+108,'PE directory count')[0]
    if not 14 <= directory_count <= 16 or 112+directory_count*8>optional_size:
        _native_fail('Incomplete/unsupported PE data directory shape')
    section_table=optional+optional_size
    _native_span(raw,section_table,section_count*40,'PE section table')
    if not section_table+section_count*40 <= headers_size <= len(raw):
        _native_fail('Invalid PE file header bound')
    sections=[]
    for index in range(section_count):
        at=section_table+40*index
        virtual_size,address,raw_size,offset=_native_unpack(raw,'<IIII',at+8,'PE section')
        extent=max(virtual_size,raw_size)
        if (not extent or address<headers_size or address+extent>image_size
                or address%section_alignment or raw_size and (offset%file_alignment or raw_size%file_alignment)):
            _native_fail('Invalid PE virtual section range')
        if raw_size:
            if offset<headers_size:
                _native_fail('PE section overlaps headers')
            _native_span(raw,offset,raw_size,'PE raw section')
        for previous in sections:
            if address<previous['address']+previous['extent'] and previous['address']<address+extent:
                _native_fail('Overlapping PE virtual sections')
            if raw_size and previous['raw_size'] and offset<previous['offset']+previous['raw_size'] and previous['offset']<offset+raw_size:
                _native_fail('Overlapping PE raw sections')
        section_flags = _native_unpack(raw,'<I',at+36,'PE section characteristics')[0]
        sections.append({'address':address,'extent':extent,'raw_size':raw_size,'offset':offset,'flags':section_flags})
    def rva(address,size,label):
        if address<headers_size:
            if size>headers_size-address:
                _native_fail('PE RVA crosses header bound')
            _native_span(raw,address,size,label)
            return address,headers_size-address
        for section in sections:
            if section['address']<=address<section['address']+section['extent']:
                offset=address-section['address']
                if offset>section['raw_size'] or size>section['raw_size']-offset:
                    _native_fail('PE RVA references unbacked/truncated section data')
                return section['offset']+offset,section['raw_size']-offset
        _native_fail('PE RVA is outside mapped sections')
    def text(address,label):
        offset,available=rva(address,1,label)
        return _native_text(raw,offset,available,label)
    def directory(index,label):
        if index>=directory_count:
            return 0,0
        address,size=_native_unpack(raw,'<II',optional+112+index*8,'PE '+label+' directory')
        if bool(address)!=bool(size):
            _native_fail('Incomplete PE '+label+' directory')
        if address:
            rva(address,size,'PE '+label+' directory')
        return address,size
    for index,label in ((11,'bound import'),(13,'delay import'),(14,'CLR')):
        if directory(index,label)!=(0,0):
            _native_fail('PE '+label+' metadata is unsupported')
    export_address,export_size=directory(0,'export')
    exports=set()
    if export_address:
        if export_size<40:
            _native_fail('Truncated PE export directory')
        offset,available=rva(export_address,40,'PE export header')
        flags,timestamp,major,minor,dll_name,base,function_count,name_count,functions_address,names_address,ordinals_address=_native_unpack(
            raw,'<IIHHIIIIIII',offset,'PE export header')
        if (not 1 <= function_count <= 65536 or name_count>_NATIVE_MAX_RECORDS or not functions_address
                or name_count and (not names_address or not ordinals_address) or not text(dll_name,'PE export DLL name')):
            _native_fail('Invalid PE export counts/addresses')
        functions_offset,unused=rva(functions_address,function_count*4,'PE export address table')
        functions=[_native_unpack(raw,'<I',functions_offset+4*index,'PE exported RVA')[0] for index in range(function_count)]
        named=set()
        getter_ordinals=set()
        previous=None
        if name_count:
            names_offset,unused=rva(names_address,name_count*4,'PE export name table')
            ordinals_offset,unused=rva(ordinals_address,name_count*2,'PE export ordinal table')
            for index in range(name_count):
                symbol=text(_native_unpack(raw,'<I',names_offset+4*index,'PE export name RVA')[0],'PE exported symbol')
                ordinal=_native_unpack(raw,'<H',ordinals_offset+2*index,'PE export ordinal')[0]
                if not symbol or previous is not None and symbol<=previous or ordinal>=function_count or not functions[ordinal]:
                    _native_fail('Invalid/unsorted PE named export')
                previous=symbol
                named.add(ordinal)
                exports.add(symbol)
                if symbol=='bib_engine_get_provider_v1':
                    getter_ordinals.add(ordinal)
        for ordinal,address in enumerate(functions):
            if not address:
                continue
            if export_address<=address<export_address+export_size:
                _native_fail('Forwarded PE exports, including a forwarded getter, are unsupported')
            if not any(section['address']<=address<section['address']+section['extent'] for section in sections):
                _native_fail('PE export RVA is outside mapped image sections')
            if ordinal in getter_ordinals and not any(section['flags'] & 0x20000000 and section['address'] <= address < section['address'] + section['raw_size'] for section in sections):
                _native_fail('Native PE getter must point into file-backed executable section memory')
            if ordinal not in named:
                exports.add('#'+str(base+ordinal))
    imports=[]
    needed=[]
    seen=set()
    import_address,import_size=directory(1,'import')
    if import_address:
        if import_size<20:
            _native_fail('Truncated PE import directory')
        offset,unused=rva(import_address,import_size,'PE import descriptors')
        ended=False
        for cursor in range(0,import_size-19,20):
            original,timestamp,forward_chain,library_address,first_thunk=_native_unpack(raw,'<IIIII',offset+cursor,'PE import descriptor')
            if not any((original,timestamp,forward_chain,library_address,first_thunk)):
                ended=True
                break
            if len(needed)>=4096 or timestamp or forward_chain or not library_address or not first_thunk:
                _native_fail('Unsupported/bound PE import descriptor')
            library=text(library_address,'PE import library')
            if not library or library.casefold() in {name.casefold() for name in needed}:
                _native_fail('Invalid/duplicate PE import library')
            needed.append(library)
            thunk_address=original or first_thunk
            for index in range(65536):
                at,unused=rva(thunk_address+8*index,8,'PE import lookup thunk')
                value=_native_unpack(raw,'<Q',at,'PE import lookup thunk')[0]
                rva(first_thunk+8*index,8,'PE import address thunk')
                if not value:
                    break
                if value & (1<<63):
                    if value & ~((1<<63)|0xffff) or not value & 0xffff:
                        _native_fail('Invalid PE ordinal import')
                    symbol='#'+str(value & 0xffff)
                else:
                    if value>0xffffffff:
                        _native_fail('Invalid PE import-name RVA width')
                    rva(value,2,'PE import hint')
                    symbol=text(value+2,'PE imported symbol')
                    if not symbol:
                        _native_fail('Empty PE imported symbol')
                key=(library,symbol,None)
                if key in seen or len(imports)>=_NATIVE_MAX_RECORDS:
                    _native_fail('Duplicate/oversized PE import closure')
                seen.add(key)
                imports.append({'library':library,'symbol':symbol,'version':None})
            else:
                _native_fail('PE import lookup table lacks a bounded terminator')
        if not ended:
            _native_fail('PE import descriptors lack a bounded terminator')
    return {'format':'pe32plus','machine':'x86_64','pointer_bits':64,'exports':sorted(exports),
        'imports':sorted(imports,key=_native_import_order),'needed':needed,'soname':None,'runpath':[]}


def scan_native_binary(raw,*,maximum_bytes=512*1024*1024):
    """Inspect actual bounded dynamic metadata; never establish load success."""
    if type(maximum_bytes) is not int or maximum_bytes<64 or type(raw) is not bytes or not 64<=len(raw)<=maximum_bytes:
        _native_fail('Expected bounded immutable native binary bytes')
    if raw.startswith(b'\x7fELF'):
        return _scan_native_elf(raw)
    if raw.startswith(b'MZ'):
        return _scan_native_pe(raw)
    _native_fail('Unsupported native binary format')


def _read_document_file(value, label):
    path = Path(value).absolute()
    manifest.ordinary_root(path.parent)
    manifest.plain_state(path.lstat(), directory=False)
    if path.resolve(strict=True) != path:_fail('Native target document must be an ordinary exact path')
    identity = lambda state: (state.st_dev,state.st_ino,state.st_mode,state.st_nlink,state.st_size,state.st_mtime_ns,state.st_ctime_ns)
    with path.open('rb') as stream:
        before = manifest.plain_state(os.fstat(stream.fileno()), directory=False)
        if before.st_size > manifest.MAX_MANIFEST:_fail('Native target document exceeds byte bound')
        raw = stream.read(manifest.MAX_MANIFEST + 1)
        after = os.fstat(stream.fileno())
    if identity(before) != identity(after) or identity(before) != identity(path.lstat()):
        _fail('Native target document changed during bounded read')
    return _document(raw, label)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect','verify'))
    parser.add_argument('--group', type=Path, required=True)
    for name in ('recipe','manifest','proof','runtime'):parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--kernel-target-json', type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--document-profile', choices=('pixel','physical'))
    selection.add_argument('--actions-profile', choices=('document-actions-v1',))
    args = parser.parse_args(argv)
    if args.actions_profile is not None:
        operation = inspect_actions_kernel_consumer if args.action == 'inspect' else verify_actions_kernel_consumer
        selected = {'actions_profile':args.actions_profile}
    else:
        operation = inspect_kernel_consumer if args.action == 'inspect' else verify_kernel_consumer
        selected = {'document_profile':args.document_profile}
    result = operation(args.group, expected_recipe=args.recipe_sha256, expected_manifest=args.manifest_sha256,
        expected_proof=args.proof_sha256, expected_runtime=args.runtime_sha256,
        kernel_target=_read_document_file(args.kernel_target_json, 'native target'), **selected)
    print(json.dumps(result.as_dict(), sort_keys=True)); return 0


if __name__ == '__main__':
    try:raise SystemExit(main())
    except (ValueError, OSError, tarfile.TarError) as error:raise SystemExit('appended native engine consumer: ' + str(error))
