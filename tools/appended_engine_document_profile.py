#!/usr/bin/env python3
"""Verify an explicitly selected document engine and emit private compiled facts.

This configure-time adapter inspects retained bytes only. It does not load a
factory, execute evidence, discover a toolchain or build an engine or kernel.
"""
import argparse
import json
import os
from pathlib import Path
import tarfile
import tempfile

import appended_engine_document_consumer as consumer
import appended_engine_document_contract as contract
import appended_engine_manifest as manifest


HEADER_DIRECTORY = 'appended-engine-document-profile'
HEADER_NAME = 'appended_engine_compiled_document_profile.hpp'
GENERATED_NOTICE = '// Generated from the fully verified document retained-engine consumer.'
SELECTION_PREFIX = '// Document profile: '
MAX_HEADER_BYTES = 64 * 1024


def _validated_metadata(inspection, document_profile):
    selected = contract.document_selector(document_profile)
    if not callable(getattr(inspection, 'as_dict', None)):
        raise ValueError('Expected a fully verified document consumer inspection')
    metadata = contract.json_copy(inspection.as_dict(), 'document consumer inspection')
    if (type(metadata) is not dict or metadata.get('scope') != contract.SCOPE
            or metadata.get('whole_group_verified') is not True
            or metadata.get('production_eligible') is not True):
        raise ValueError('Compiled document facts require a fully verified eligible retained group')
    profile = contract.validate_engine_profile(metadata.get('engine_profile'), document_profile=selected)
    contract.validate_provider_contract(metadata.get('provider_contract'), document_profile=selected)
    contract.validate_interface_references(metadata.get('interfaces'), document_profile=selected)
    if (profile['source_recipe_sha256'] != metadata.get('recipe_id')
            or profile['build_sha256'] != metadata.get('provider_build_sha256')):
        raise ValueError('Compiled document facts differ from verified retained pins')
    return metadata, profile, selected


def _render(profile, selected):
    # Only these two validated lowercase SHA256 strings are untrusted literals.
    build = profile['build_sha256']
    recipe = profile['source_recipe_sha256']
    kind, name, capabilities, physical = {
        'pixel': ('pixel', 'kPixelProfileName', 'kPixelCapabilities', 'Digest{}'),
        'physical': ('physical', 'kPhysicalProfileName', 'kPhysicalCapabilities', 'kPhysicalCatalogSha256'),
    }[selected]
    return f'''{GENERATED_NOTICE}
{SELECTION_PREFIX}{selected}
// Private immutable composition facts; never an installed public header.
#pragma once
#include "shared/engine_document_profile.hpp"

namespace foundation::appended::engine_document {{
static_assert(BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_V2_ABI_MINOR == 1);
static_assert(BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR == 0);
static_assert(kBaseHeaderSha256 == detail::digest("a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d"));
static_assert(kExtensionHeaderSha256 == detail::digest("7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626"));
static_assert(kContractSha256 == detail::digest("aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298"));
static_assert(kCatalogSha256 == detail::digest("6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5"));
static_assert(kSchema == detail::digest("f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d"));
static_assert(kAckSchema == detail::digest("1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5"));
static_assert(kPhysicalCatalogSha256 == detail::digest("d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b"));
static_assert(kPixelProfileName == "foundation-engine-copied1795-ndv2-v1" && kPixelCapabilities == 1795);
static_assert(kPhysicalProfileName == "foundation-engine-copied2003-ndv2-v1" && kPhysicalCapabilities == 2003);
static_assert(kReplyCapacity == 1048576 && kQueryCopiedReplyCapacity == 1048672 &&
    kFormCopiedReplyCapacity == 1048680 && kAckCopiedReplyCapacity == 120);
static_assert(kQueries == std::array<OperationFacts, 1>{{{{
    {{3, 48, 1048576, 512, kSchema}}
}}}});
static_assert(kCommands == std::array<OperationFacts, 2>{{{{
    {{6, 6246, 1048576, 1024, kSchema}}, {{7, 8, 16, 1024, kAckSchema}}
}}}});
inline constexpr ProfileKind compiled_engine_document_kind = ProfileKind::{kind};
inline const EngineDocumentProfileFacts compiled_engine_document_profile{{
    .enabled = true,
    .kind = compiled_engine_document_kind,
    .name = std::string({name}),
    .provider_abi_major = 1, .provider_abi_minor = 1,
    .host_abi_major = 1, .host_abi_minor = 0,
    .target_system = BIB_ENGINE_TARGET_BROWSER_WASM,
    .target_processor = BIB_ENGINE_CPU_WASM32,
    .pointer_bits = 32, .lifetime = BIB_ENGINE_LIFETIME_PROCESS, .maximum_starts = 1,
    .viewport_width = 800, .viewport_height = 600,
    .provider_capabilities = {capabilities},
    .base_header_sha256 = kBaseHeaderSha256,
    .extension_header_sha256 = kExtensionHeaderSha256,
    .contract_sha256 = kContractSha256, .catalog_sha256 = kCatalogSha256,
    .build_sha256 = detail::digest("{build}"),
    .source_recipe_sha256 = detail::digest("{recipe}"),
    .physical_catalog_sha256 = {physical},
    .queries = kQueries, .commands = kCommands, .query_count = 1, .command_count = 2
}};
}} // namespace foundation::appended::engine_document
'''


def compiled_header(inspection, *, document_profile):
    """Render fixed C++ syntax only after validating the explicit inspection."""
    _, profile, selected = _validated_metadata(inspection, document_profile)
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
        raise ValueError('Document compiled-profile output must be ordinary without aliases') from error


def _read_regular(path, maximum):
    manifest.plain_state(path.lstat(), directory=False)
    with path.open('rb') as stream:
        state = manifest.plain_state(os.fstat(stream.fileno()), directory=False)
        if state.st_size > maximum:
            raise ValueError('Document compiled-profile input exceeds its byte limit')
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError('Document compiled-profile input exceeds its byte limit')
    return content


def _check_existing_selection(content, selected):
    prefix = SELECTION_PREFIX.encode('ascii')
    marker_lines = [line for line in content.splitlines() if line.lstrip().startswith(prefix.rstrip())]
    identifiable = (content.startswith(GENERATED_NOTICE.encode('ascii')) or marker_lines
                    or b'compiled_engine_document_profile' in content)
    if not identifiable:
        return
    allowed = {prefix + name.encode('ascii'): name for name in ('pixel', 'physical')}
    if len(marker_lines) != 1 or marker_lines[0] not in allowed:
        raise ValueError('Existing generated document profile has a malformed selection marker')
    if allowed[marker_lines[0]] != selected:
        raise ValueError('Document profile selection changed; use a fresh build directory')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--document-profile', choices=('pixel', 'physical'), required=True)
    parser.add_argument('--group', type=Path, required=True)
    for name in ('recipe', 'manifest', 'proof', 'runtime'):
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--kernel-target-json', type=Path, required=True)
    parser.add_argument('--paired-sdk-sha256', required=True)
    parser.add_argument('--build-root', type=Path, required=True)
    args = parser.parse_args(argv)
    selected = contract.document_selector(args.document_profile)
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
        raise ValueError('Document compiled-profile output must not overwrite its target input')
    group = manifest.ordinary_root(args.group)
    if build_root == group or group in build_root.parents or build_root in group.parents:
        raise ValueError('Document compiled-profile output must be separate from retained inputs')
    _ordinary_path(target_json)
    target = contract.strict_json(_read_regular(target_json, manifest.MAX_MANIFEST), 'kernel target')
    inspection = consumer.verify_kernel_consumer(group,
        expected_recipe=args.recipe_sha256, expected_manifest=args.manifest_sha256,
        expected_proof=args.proof_sha256, expected_runtime=args.runtime_sha256,
        kernel_target=target, paired_sdk=args.paired_sdk_sha256, document_profile=selected)
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
            with tempfile.NamedTemporaryFile(prefix='.compiled-document-profile-', dir=output_directory, delete=False) as stream:
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
        raise SystemExit('appended engine document profile: ' + str(error))
