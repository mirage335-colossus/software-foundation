#!/usr/bin/env python3
"""Verify an explicitly selected editor engine and emit private compiled facts.

This configure-time adapter inspects retained bytes only. It does not load a
factory, execute evidence, discover a toolchain or build an engine or kernel.
"""
import argparse
import json
import os
from pathlib import Path
import tarfile
import tempfile

import appended_engine_editor_consumer as consumer
import appended_engine_editor_contract as contract
import appended_engine_manifest as manifest


HEADER_DIRECTORY = 'appended-engine-editor-profile'
HEADER_NAME = 'appended_engine_compiled_editor_profile.hpp'
GENERATED_NOTICE = '// Generated from the fully verified editor retained-engine consumer.'
SELECTION_PREFIX = '// Editor profile: '
MAX_HEADER_BYTES = 64 * 1024


def _validated_metadata(inspection, editor_profile):
    selected = contract.editor_selector(editor_profile)
    if not callable(getattr(inspection, 'as_dict', None)):
        raise ValueError('Expected a fully verified editor consumer inspection')
    metadata = contract.json_copy(inspection.as_dict(), 'editor consumer inspection')
    if (type(metadata) is not dict or metadata.get('scope') != contract.SCOPE
            or metadata.get('whole_group_verified') is not True
            or metadata.get('production_eligible') is not True):
        raise ValueError('Compiled editor facts require a fully verified eligible retained group')
    profile = contract.validate_engine_profile(metadata.get('engine_profile'), editor_profile=selected)
    contract.validate_provider_contract(metadata.get('provider_contract'), editor_profile=selected)
    contract.validate_interface_references(metadata.get('interfaces'), editor_profile=selected)
    if (profile['source_recipe_sha256'] != metadata.get('recipe_id')
            or profile['build_sha256'] != metadata.get('provider_build_sha256')):
        raise ValueError('Compiled editor facts differ from verified retained pins')
    return metadata, profile, selected


def _render(profile, selected):
    build, recipe = profile['build_sha256'], profile['source_recipe_sha256']
    provider = contract.provider_contract(editor_profile=selected)
    operation_assertions = '\n'.join(
        'static_assert(k' + table.capitalize() + '[' + str(index) + '] == OperationFacts{' +
        ', '.join(str(item[key]) for key in ('operation', 'maximum_input_bytes', 'required_reply_capacity', 'capability')) +
        ', engine_document::detail::digest("' + item['schema_sha256'] + '")});'
        for table in ('queries', 'commands') for index, item in enumerate(provider[table]))
    return f'''{GENERATED_NOTICE}
{SELECTION_PREFIX}{selected}
// Private immutable composition facts; never an installed public header.
#pragma once
#include "shared/engine_editor_profile.hpp"

namespace foundation::appended::engine_editor {{
static_assert(BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_V2_ABI_MINOR == 1);
static_assert(BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR == 0);
static_assert(kProfileName == "foundation-engine-copied2035-ndv2-editor-v1");
static_assert(kProviderCapabilities == 2035 && kSurfaceCapabilities == 8255);
static_assert(kReplyCapacity == 1048576 && kQueryRequestMaximum == 236);
static_assert(BIB_ENGINE_EDITOR_MAX_WIRE_BYTES == 1048576 && BIB_ENGINE_EDITOR_PROTOCOL_VERSION == 1);
static_assert(kHeaderSha256 == engine_document::detail::digest("{contract.EDITOR_HEADER_SHA256}"));
static_assert(kContractSha256 == engine_document::detail::digest("{contract.CONTRACT_SHA256}"));
static_assert(kCatalogSha256 == engine_document::detail::digest("{contract.EDITOR_CATALOG_SHA256}"));
static_assert(kSchema == engine_document::detail::digest("{contract.EDITOR_SCHEMA_SHA256}"));
static_assert(engine_document::kBaseHeaderSha256 == engine_document::detail::digest("{contract.BASE_HEADER_SHA256}"));
static_assert(engine_document::kExtensionHeaderSha256 == engine_document::detail::digest("{contract.DOCUMENT_HEADER_SHA256}"));
static_assert(engine_document::kContractSha256 == engine_document::detail::digest("{contract.DOCUMENT_CONTRACT_SHA256}"));
static_assert(engine_document::kCatalogSha256 == engine_document::detail::digest("{contract.DOCUMENT_CATALOG_SHA256}"));
static_assert(engine_document::kPhysicalCatalogSha256 == engine_document::detail::digest("{contract.PHYSICAL_CATALOG_SHA256}"));
static_assert(engine_document::kSchema == engine_document::detail::digest("{contract.DOCUMENT_SCHEMA_SHA256}"));
static_assert(engine_document::kAckSchema == engine_document::detail::digest("{contract.ACTION_ACK_SCHEMA_SHA256}"));
static_assert(kQueries.size() == 2 && kCommands.size() == 7);
{operation_assertions}
inline const EngineEditorProfileFacts compiled_engine_editor_profile{{
    .enabled = true, .kind = ProfileKind::editor, .name = std::string(kProfileName),
    .provider_abi_major = 1, .provider_abi_minor = 1,
    .host_abi_major = 1, .host_abi_minor = 0,
    .target_system = BIB_ENGINE_TARGET_BROWSER_WASM, .target_processor = BIB_ENGINE_CPU_WASM32,
    .pointer_bits = 32, .lifetime = BIB_ENGINE_LIFETIME_PROCESS, .maximum_starts = 1,
    .viewport_width = 800, .viewport_height = 600,
    .provider_capabilities = kProviderCapabilities, .surface_capabilities = kSurfaceCapabilities,
    .surface_protocol_version = 2, .editor_protocol_version = 1,
    .base_header_sha256 = engine_document::kBaseHeaderSha256,
    .document_header_sha256 = engine_document::kExtensionHeaderSha256,
    .document_contract_sha256 = engine_document::kContractSha256,
    .document_catalog_sha256 = engine_document::kCatalogSha256,
    .physical_catalog_sha256 = engine_document::kPhysicalCatalogSha256,
    .editor_header_sha256 = kHeaderSha256, .contract_sha256 = kContractSha256,
    .catalog_sha256 = kCatalogSha256, .schema_sha256 = kSchema,
    .build_sha256 = engine_document::detail::digest("{build}"),
    .source_recipe_sha256 = engine_document::detail::digest("{recipe}"),
    .queries = kQueries, .commands = kCommands, .query_count = 2, .command_count = 7
}};
}} // namespace foundation::appended::engine_editor
'''


def compiled_header(group, **consumer_arguments):
    """Render only after fresh complete eligible retained-group verification."""
    selected = contract.editor_selector(consumer_arguments.get('editor_profile'))
    inspection = consumer.verify_kernel_consumer(group, **consumer_arguments)
    _, profile, selected = _validated_metadata(inspection, selected)
    return _render(profile, selected)


def _ordinary_path(path, directory=False):
    for ancestor in reversed(path.parents):
        manifest.plain_state(ancestor.lstat(), directory=True)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    try:
        manifest.plain_state(info, directory=directory)
    except ValueError as error:
        raise ValueError('Editor compiled-profile output must be ordinary without aliases') from error


def _read_regular(path, maximum):
    manifest.plain_state(path.lstat(), directory=False)
    with path.open('rb') as stream:
        state = manifest.plain_state(os.fstat(stream.fileno()), directory=False)
        if state.st_size > maximum:
            raise ValueError('Editor compiled-profile input exceeds its byte limit')
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError('Editor compiled-profile input exceeds its byte limit')
    return content


def _check_existing_selection(content, selected):
    prefix = SELECTION_PREFIX.encode('ascii')
    marker_lines = [line for line in content.splitlines() if line.lstrip().startswith(prefix.rstrip())]
    identifiable = (content.startswith(GENERATED_NOTICE.encode('ascii')) or marker_lines
                    or b'compiled_engine_editor_profile' in content)
    if not identifiable:
        return
    allowed = {prefix + name.encode('ascii'): name for name in ('editor',)}
    if len(marker_lines) != 1 or marker_lines[0] not in allowed:
        raise ValueError('Existing generated editor profile has a malformed selection marker')
    if allowed[marker_lines[0]] != selected:
        raise ValueError('Editor profile selection changed; use a fresh build directory')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor-profile', choices=('editor',), required=True)
    parser.add_argument('--group', type=Path, required=True)
    for name in ('recipe', 'manifest', 'proof', 'runtime'):
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--kernel-target-json', type=Path, required=True)
    parser.add_argument('--paired-sdk-sha256', required=True)
    parser.add_argument('--build-root', type=Path, required=True)
    args = parser.parse_args(argv)
    selected = contract.editor_selector(args.editor_profile)
    build_root = manifest.ordinary_root(args.build_root)
    output_directory = build_root / HEADER_DIRECTORY
    _ordinary_path(output_directory, directory=True)
    output = output_directory / HEADER_NAME
    if output_directory.exists():
        _ordinary_path(output)
        if output.exists():
            _check_existing_selection(_read_regular(output, MAX_HEADER_BYTES), selected)
    target_json = args.kernel_target_json.absolute()
    if target_json.resolve(strict=True) == output.resolve():
        raise ValueError('Editor compiled-profile output must not overwrite its target input')
    group = manifest.ordinary_root(args.group)
    if build_root == group or group in build_root.parents or build_root in group.parents:
        raise ValueError('Editor compiled-profile output must be separate from retained inputs')
    _ordinary_path(target_json)
    target = contract.strict_json(_read_regular(target_json, manifest.MAX_MANIFEST), 'kernel target')
    inspection = consumer.verify_kernel_consumer(group,
        expected_recipe=args.recipe_sha256, expected_manifest=args.manifest_sha256,
        expected_proof=args.proof_sha256, expected_runtime=args.runtime_sha256,
        kernel_target=target, paired_sdk=args.paired_sdk_sha256, editor_profile=selected)
    metadata, profile, selected = _validated_metadata(inspection, selected)
    header = _render(profile, selected).encode('utf-8')
    description = json.dumps(metadata, sort_keys=True)
    output_directory.mkdir(exist_ok=True)
    _ordinary_path(output_directory, directory=True)
    _ordinary_path(output)
    previous = _read_regular(output, MAX_HEADER_BYTES) if output.exists() else None
    if previous is not None:
        _check_existing_selection(previous, selected)
    if previous != header:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.compiled-editor-profile-', dir=output_directory, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(header)
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print(description)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, tarfile.TarError) as error:
        raise SystemExit('appended engine editor profile: ' + str(error))
