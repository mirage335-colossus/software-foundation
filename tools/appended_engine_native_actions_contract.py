#!/usr/bin/env python3
"""Pure, explicitly selected native4083 facts; no retained eligibility decision.

No file, loader, provider or runtime operation occurs here. The pixel1795,
physical2003, browser editor2035 and their closed contracts stay independent.
"""
import hashlib
from types import MappingProxyType

import appended_engine_document_contract as document
import appended_engine_editor_contract as editor
import appended_engine_manifest as manifest

ContractError = document.ContractError
canonical_json = document.canonical_json
strict_json = document.strict_json
json_copy = document.json_copy
require_fields = document.require_fields
validate_sha256 = document.validate_sha256

SELECTOR = 'document-actions-v1'
PROFILE_KIND = 'foundation-native-engine-document-actions-v1'
PROFILE_NAME = 'foundation-engine-copied4083-ndv2-editor-document-actions-v1'
PROFILE_KIND_NUMBER = 4
BINDING = 'private-native'
PROOF_KIND = 'foundation-neutral-engine-provider-native-document-actions-v1-proof-v1'
BUILD_KIND = 'foundation-neutral-engine-provider-native-document-actions-v1-build-v1'
RUNTIME_KIND = 'foundation-neutral-engine-native-document-actions-v1-runtime-evidence-v1'
SCOPE = 'retained-native-document-actions-consumer-byte-and-static-contract-only'
EMBEDDED_SCOPE = 'embedded-retained-native-document-actions-consumer-byte-and-static-contract-only'
GETTER = 'bib_engine_get_provider_v1'
PROFILE_NAMES = MappingProxyType({SELECTOR: PROFILE_NAME})
CAPABILITIES = MappingProxyType({SELECTOR: '4083'})
BASE_HEADER_SHA256 = document.BASE_HEADER_SHA256
DOCUMENT_HEADER_SHA256 = document.EXTENSION_HEADER_SHA256
DOCUMENT_CONTRACT_SHA256 = document.CONTRACT_SHA256
DOCUMENT_CATALOG_SHA256 = document.DOCUMENT_CATALOG_SHA256
DOCUMENT_SCHEMA_SHA256 = document.DOCUMENT_SCHEMA_SHA256
ACTION_ACK_SCHEMA_SHA256 = document.ACTION_ACK_SCHEMA_SHA256
PHYSICAL_CATALOG_SHA256 = document.PHYSICAL_CATALOG_SHA256
EDITOR_PROFILE_NAME = editor.PROFILE_NAME
EDITOR_HEADER_SHA256 = editor.EDITOR_HEADER_SHA256
EDITOR_CONTRACT_SHA256 = editor.CONTRACT_SHA256
EDITOR_CATALOG_SHA256 = editor.EDITOR_CATALOG_SHA256
EDITOR_SCHEMA_SHA256 = editor.EDITOR_SCHEMA_SHA256
ACTIONS_HEADER_SHA256 = 'e748f399557597c510cbcf457dc96208c7bfd5ebbde3298a7cf3f49e7e05754f'
CONTRACT_SHA256 = '33e23c8972497a64956a765b24a61538fe1cfcabe6be80af8e19ceb0e401e221'
ACTIONS_CATALOG_SHA256 = 'f220358edc36eb083fd567611f5d0ebb5f607fe3fd90e1c83ccd7a85a5690be5'
ACTIONS_SCHEMA_SHA256 = 'b5603ec73b05ff2efb4b0a9405b98095789de4cc2a950e7b69813a1845cd9d64'
ACTIONS_ACK_SCHEMA_SHA256 = 'a4793ce28417ffa97b754344624c9d9d78093acba5792bde006c7b95482dfcbe'
MAX_INTERFACE_BYTES = document.MAX_INTERFACE_BYTES
MAX_INTERFACES_BYTES = 16 * MAX_INTERFACE_BYTES
MAX_DOCUMENT_BYTES = document.MAX_DOCUMENT_BYTES

PROFILE_FIELDS = ('schema_version', 'kind', 'binding', 'target', 'profile_kind', 'actions_profile',
    'provider_abi_major', 'provider_abi_minor', 'host_abi_major', 'host_abi_minor', 'lifetime',
    'maximum_starts', 'viewport_width', 'viewport_height', 'capabilities', 'base_header_sha256',
    'document_header_sha256', 'document_contract_sha256', 'document_catalog_sha256',
    'document_schema_sha256', 'action_ack_schema_sha256', 'physical_catalog_sha256', 'editor_profile',
    'editor_header_sha256', 'editor_contract_sha256', 'editor_catalog_sha256', 'editor_schema_sha256',
    'actions_header_sha256', 'contract_sha256', 'actions_catalog_sha256', 'actions_schema_sha256',
    'actions_ack_schema_sha256', 'surface_capabilities', 'surface_protocol_version', 'editor_protocol_version',
    'editor_command_max_bytes', 'editor_query_max_bytes', 'editor_reply_capacity', 'build_sha256', 'source_recipe_sha256')
PROOF_FIELDS = ('schema_version', 'kind', 'recipe_id', 'sources_sha256', 'provider_build',
    'engine_profile', 'assets', 'native_facts', 'runtime_evidence', 'interfaces')
BUILD_FIELDS = ('schema_version', 'kind', 'target', 'toolchain', 'options', 'source_recipe_sha256',
    'source_inputs_sha256', 'contract_header_sha256', 'binding', 'configuration', 'capabilities',
    'provider_contract', 'provider_limits')
RUNTIME_FIELDS = ('schema_version', 'kind', 'scope', 'status', 'recipe_id', 'provider_build_sha256',
    'assets_sha256', 'target', 'toolchain_identity_sha256', 'engine_profile', 'environment', 'checks',
    'provider_observation', 'bootstrap', 'native_facts_sha256')
EVIDENCE_FIELDS = document.EVIDENCE_FIELDS
BOOTSTRAP_CHECKS = ('getter_before_start', 'table_checked_before_start', 'no_host_callbacks_during_getter',
    'one_process_start', 'outside_engine_owner_pump', 'process_lifetime_no_unload')
NATIVE_RUNTIME_CHECKS = ('native-getter-inert-and-table', 'native-import-export-dependency-closure',
    'native-runtime-floor-and-private-runtime', 'native-offline-entry-resource-load',
    'native-service-result-and-ack', 'native-outside-engine-owner-pump', 'native-opaque-raster-frame',
    'native-failure-close-process-lifetime', 'document-provider-minor-and-catalog',
    'document-query3-owned-snapshot', 'document-form6-native-readback', 'document-action-replay-and-ack7',
    'document-navigation-and-stale-lease', 'document-outer-unknown-terminal-no-replay')
ACTIONS_RUNTIME_CHECKS = ('actions-profile-and-contract', 'actions-query3-owned-body-targets',
    'actions-command10-native-dispatch-readback', 'actions-command11-retained-family-ack',
    'actions-two-unwinds-passive-publication', 'actions-stale-identity-denial',
    'actions-context-replacement-no-replay', 'actions-outer-unknown-terminal-no-replay')
RUNTIME_CHECKS = (NATIVE_RUNTIME_CHECKS + document.PHYSICAL_RUNTIME_CHECKS +
    editor.EDITOR_RUNTIME_CHECKS + ACTIONS_RUNTIME_CHECKS)
INTERFACE_PATHS = MappingProxyType({**editor.INTERFACE_PATHS,
    'physical_catalog': 'abi/engine/physical-v1/catalog.json',
    'document_schema': 'abi/engine/document-v2/schema-definition.json',
    'actions_header': 'include/foundation/appended/engine_provider_document_actions_v1.h',
    'actions_contract': 'abi/engine/document-actions-v1/contract.json',
    'actions_catalog': 'abi/engine/document-actions-v1/catalog.json',
    'actions_schema': 'abi/engine/document-actions-v1/binary-schema.json',
    'actions_ack_schema': 'abi/engine/document-actions-v1/action-ack.json'})
INTERFACE_PINS = MappingProxyType({**editor._pins(), 'document_schema': DOCUMENT_SCHEMA_SHA256,
    'actions_header': ACTIONS_HEADER_SHA256, 'actions_contract': CONTRACT_SHA256,
    'actions_catalog': ACTIONS_CATALOG_SHA256, 'actions_schema': ACTIONS_SCHEMA_SHA256,
    'actions_ack_schema': ACTIONS_ACK_SCHEMA_SHA256})
LIMIT_FIELDS = ('size', 'maximum_command_bytes', 'maximum_query_bytes', 'maximum_reply_bytes',
    'maximum_service_message_bytes', 'maximum_retired_documents', 'maximum_inflight_resources',
    'reserved', 'maximum_resource_response_bytes', 'maximum_retained_resource_bytes')
PROVIDER_LIMITS = MappingProxyType({'size': 48, 'maximum_command_bytes': 1048576,
    'maximum_query_bytes': 236, 'maximum_reply_bytes': 1048576, 'maximum_service_message_bytes': 1048576,
    'maximum_retired_documents': 8, 'maximum_inflight_resources': 64, 'reserved': 0,
    'maximum_resource_response_bytes': 67108864, 'maximum_retained_resource_bytes': 134217728})
_TARGETS = MappingProxyType({('Linux', 'x86_64'): (1, 1), ('Linux', 'aarch64'): (1, 2), ('Windows', 'x86_64'): (2, 1)})


def _pins():
    result = dict(INTERFACE_PINS)
    for role, pin in result.items():
        validate_sha256(pin, 'frozen native actions interface ' + role, nonzero=True)
    return result


def actions_selector(value):
    if type(value) is not str or value != SELECTOR:
        raise ContractError('Native actions profile must be explicitly document-actions-v1')
    return value


def native_target(value):
    target = json_copy(value, 'native actions target')
    try:
        manifest.target_contract(target)
    except ValueError as error:
        raise ContractError(str(error)) from error
    if (target['system'], target['processor']) not in _TARGETS or target['pointer_bits'] != 64:
        raise ContractError('Only explicit Linux x86_64/aarch64 or Windows x86_64 native targets are supported')
    return target


def expected_engine_profile(*, kernel_target, actions_profile, build_sha256, source_recipe_sha256):
    actions_selector(actions_profile)
    _pins()
    return {'schema_version': 1, 'kind': PROFILE_KIND, 'binding': BINDING, 'target': native_target(kernel_target),
        'profile_kind': 4, 'actions_profile': PROFILE_NAME, 'provider_abi_major': 1, 'provider_abi_minor': 1,
        'host_abi_major': 1, 'host_abi_minor': 0, 'lifetime': 1, 'maximum_starts': 1,
        'viewport_width': 800, 'viewport_height': 600, 'capabilities': '4083',
        'base_header_sha256': BASE_HEADER_SHA256, 'document_header_sha256': DOCUMENT_HEADER_SHA256,
        'document_contract_sha256': DOCUMENT_CONTRACT_SHA256, 'document_catalog_sha256': DOCUMENT_CATALOG_SHA256,
        'document_schema_sha256': DOCUMENT_SCHEMA_SHA256, 'action_ack_schema_sha256': ACTION_ACK_SCHEMA_SHA256,
        'physical_catalog_sha256': PHYSICAL_CATALOG_SHA256, 'editor_profile': EDITOR_PROFILE_NAME,
        'editor_header_sha256': EDITOR_HEADER_SHA256, 'editor_contract_sha256': EDITOR_CONTRACT_SHA256,
        'editor_catalog_sha256': EDITOR_CATALOG_SHA256, 'editor_schema_sha256': EDITOR_SCHEMA_SHA256,
        'actions_header_sha256': ACTIONS_HEADER_SHA256, 'contract_sha256': CONTRACT_SHA256,
        'actions_catalog_sha256': ACTIONS_CATALOG_SHA256, 'actions_schema_sha256': ACTIONS_SCHEMA_SHA256,
        'actions_ack_schema_sha256': ACTIONS_ACK_SCHEMA_SHA256, 'surface_capabilities': '8255',
        'surface_protocol_version': 2, 'editor_protocol_version': 1,
        'editor_command_max_bytes': 1048576, 'editor_query_max_bytes': 236, 'editor_reply_capacity': 1048576,
        'build_sha256': validate_sha256(build_sha256, 'native actions provider build', nonzero=True),
        'source_recipe_sha256': validate_sha256(source_recipe_sha256, 'native actions recipe', nonzero=True)}


def validate_engine_profile(value, *, kernel_target, actions_profile):
    value = json_copy(value, 'native actions engine profile')
    require_fields(value, PROFILE_FIELDS, 'native actions engine profile')
    expected = expected_engine_profile(kernel_target=kernel_target, actions_profile=actions_profile,
        build_sha256=value['build_sha256'], source_recipe_sha256=value['source_recipe_sha256'])
    if canonical_json(value) != canonical_json(expected):
        raise ContractError('Native engine profile differs from the explicit kind4 actions4083 contract')
    return value


def provider_contract(*, kernel_target, actions_profile):
    actions_selector(actions_profile)
    target = native_target(kernel_target)
    system, processor = _TARGETS[(target['system'], target['processor'])]
    inherited = editor.provider_contract(editor_profile='editor')
    commands = inherited['commands'] + [
        {'operation': 10, 'maximum_input_bytes': 128, 'required_reply_capacity': 1048576,
         'capability': '2048', 'schema_sha256': ACTIONS_SCHEMA_SHA256},
        {'operation': 11, 'maximum_input_bytes': 8, 'required_reply_capacity': 16,
         'capability': '2048', 'schema_sha256': ACTIONS_ACK_SCHEMA_SHA256}]
    return {'provider_abi': {'major': 1, 'minor': 1}, 'host_abi': {'major': 1, 'minor': 0},
        'getter_maximum_minor': 1, 'target': {'system': system, 'processor': processor, 'pointer_bits': 64},
        'lifetime': 1, 'maximum_starts': 1, 'queries': inherited['queries'], 'commands': commands}


def validate_provider_contract(value, *, kernel_target, actions_profile):
    value = json_copy(value, 'native actions provider contract')
    expected = provider_contract(kernel_target=kernel_target, actions_profile=actions_profile)
    if canonical_json(value) != canonical_json(expected):
        raise ContractError('Native actions provider ABI/target/lifetime/operation contract differs')
    return value


def expected_configuration(*, actions_profile):
    actions_selector(actions_profile)
    return {'kind': 'native-dso-private-document-actions-runtime-v1', 'actions_profile': PROFILE_NAME,
        'profile_kind': 4, 'getter': GETTER, 'getter_maximum_minor': 1, 'inert_registration': True,
        'public_exports': [GETTER], 'rendering': 'cpu', 'script_enabled': True, 'thread_model': 'native'}


def runtime_checks(*, actions_profile):
    actions_selector(actions_profile)
    return RUNTIME_CHECKS


def validate_provider_limits(value):
    value = json_copy(value, 'native actions provider limits')
    require_fields(value, LIMIT_FIELDS, 'native actions provider limits')
    # Original native4083 Build/config/table facts are fixed, including shared
    # resource limits. Kernel-side selected Owner options are separate inputs.
    if canonical_json(value) != canonical_json(dict(PROVIDER_LIMITS)):
        raise ContractError('Native actions provider limits differ from the exact ten-field contract')
    return value


def validate_interface_references(value, *, actions_profile):
    actions_selector(actions_profile)
    value = json_copy(value, 'native actions interface references')
    require_fields(value, tuple(INTERFACE_PATHS), 'native actions interface reference roles')
    pins, seen = _pins(), set()
    for role, reference in value.items():
        require_fields(reference, ('path', 'sha256'), 'native actions interface reference')
        if reference['path'] != INTERFACE_PATHS[role] or reference['path'].casefold() in seen:
            raise ContractError('Aliased or noncanonical native actions interface path')
        seen.add(reference['path'].casefold())
        if reference['sha256'] != pins[role]:
            raise ContractError('Native actions interface pin differs: ' + role)
    return value


def validate_interface_bytes(references, interfaces, *, actions_profile):
    references = validate_interface_references(references, actions_profile=actions_profile)
    if not hasattr(interfaces, 'items'):
        raise ContractError('Expected owned native actions interface byte mapping')
    interfaces = dict(interfaces.items())
    if set(interfaces) != {item['path'] for item in references.values()}:
        raise ContractError('Native actions interface byte closure differs')
    total = 0
    for raw in interfaces.values():
        if type(raw) is not bytes or not 1 <= len(raw) <= MAX_INTERFACE_BYTES:
            raise ContractError('Invalid/oversized native actions interface bytes')
        total += len(raw)
        if total > MAX_INTERFACES_BYTES:
            raise ContractError('Native actions interfaces exceed aggregate bound')
    for role, reference in references.items():
        raw = interfaces[reference['path']]
        if hashlib.sha256(raw).hexdigest() != reference['sha256']:
            raise ContractError('Native actions interface bytes differ: ' + role)
        if reference['path'].endswith('.json'):
            parsed = strict_json(raw, 'native actions interface', maximum=MAX_INTERFACE_BYTES)
            canonical = canonical_json(parsed)
            if role in ('editor_contract', 'editor_catalog'):
                canonical = canonical[:-1]
            if type(parsed) is not dict or role not in ('physical_catalog', 'editor_schema') and canonical != raw:
                raise ContractError('Native actions interface JSON is not a canonical object')
    return interfaces


# Explicitly named producer/consumer entry points select only this new contract.
# Generic helpers above retain a mandatory selector; none infer it from masks.
def expected_actions_engine_profile(*, kernel_target, build_sha256, source_recipe_sha256):
    return expected_engine_profile(kernel_target=kernel_target, actions_profile=SELECTOR,
        build_sha256=build_sha256, source_recipe_sha256=source_recipe_sha256)


def actions_provider_contract(*, kernel_target):
    return provider_contract(kernel_target=kernel_target, actions_profile=SELECTOR)


def expected_actions_configuration():
    return expected_configuration(actions_profile=SELECTOR)


def validate_actions_provider_limits(value):
    return validate_provider_limits(value)


def native_actions_target(value):
    return native_target(value)
