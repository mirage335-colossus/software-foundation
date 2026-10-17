#!/usr/bin/env python3
"""Admit an explicit physical retained engine and emit its private compiled facts.

This configure-time adapter runs the strict retained-byte consumer once. It does
not load a factory, execute runtime evidence, discover tools or build anything.
"""
import argparse
import json
import os
from pathlib import Path
import tarfile
import tempfile

import appended_engine_consumer as consumer
import appended_engine_manifest as manifest

HEADER_DIRECTORY = 'appended-engine-physical-input'
HEADER_NAME = 'appended_engine_compiled_input_profile.hpp'


def compiled_header(inspection):
    """Render only fixed C++ syntax and validated lowercase digest literals."""
    metadata = inspection.as_dict()
    if (metadata.get('scope') != consumer.SCOPE
            or metadata.get('whole_group_verified') is not True
            or metadata.get('production_eligible') is not True):
        raise ValueError('Compiled physical facts require a fully verified eligible retained group')
    profile = consumer.validate_engine_profile(metadata['engine_profile'],
                                               required_binding=consumer.PHYSICAL_BINDING)
    if (profile['source_recipe_sha256'] != metadata['recipe_id']
            or profile['build_sha256'] != metadata['provider_build_sha256']
            or metadata['command_catalog']['sha256'] != profile['command_catalog_sha256']
            or any(profile[name] == '0' * 64 for name in ('build_sha256', 'source_recipe_sha256'))):
        raise ValueError('Compiled physical facts differ from verified retained pins')
    return '''// Generated from the fully verified physical retained-engine consumer.
// Private immutable composition facts; never an installed public header.
#pragma once
#include "shared/appended_engine_input_profile.hpp"

namespace foundation::appended::engine_input {
static_assert(kProviderContractSha256 == detail::digest("%(contract_sha256)s"));
static_assert(kInputCatalogSha256 == detail::digest("%(command_catalog_sha256)s"));
static_assert(kInputProfileName == "foundation-engine-copied467-mouse-v1");
static_assert(kProviderCapabilities == 467 && kSurfaceCapabilities == 8225);
static_assert(kSurfaceProtocolVersion == 1 && kMouseInputVersion == 1 && kRawKeyMappingRevision == 1);
static_assert(kCommands == std::array<OperationFacts, 3>{{
    {1, 160, 16, 16, kKeySchema}, {3, 32, 16, 64, kFocusSchema}, {5, 80, 16, 128, kMouseSchema}}});
inline const EngineSurfaceProfileFacts compiled_engine_surface_profile{
    true, std::string(kInputProfileName),
    detail::digest("%(contract_sha256)s"),
    detail::digest("%(build_sha256)s"),
    detail::digest("%(source_recipe_sha256)s"),
    detail::digest("%(command_catalog_sha256)s"),
    kProviderCapabilities, kSurfaceCapabilities,
    kSurfaceProtocolVersion, kMouseInputVersion, kRawKeyMappingRevision,
    800, 600, 1.0, kCommands, 0
};
} // namespace foundation::appended::engine_input
''' % profile


def _ordinary_path(path, directory=False):
    """Reject linked/special output ancestors and an aliased existing header."""
    for ancestor in reversed(path.parents):
        manifest.plain_state(ancestor.lstat(), directory=True)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    try:
        manifest.plain_state(info, directory=directory)
    except ValueError as error:
        raise ValueError('Physical compiled-profile output must be an ordinary owned path without aliases') from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', type=Path, required=True)
    for name in ('recipe', 'manifest', 'proof', 'runtime'):
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--kernel-target-json', type=Path, required=True)
    parser.add_argument('--paired-sdk-sha256', required=True)
    parser.add_argument('--build-root', type=Path, required=True)
    args = parser.parse_args(argv)
    build_root = manifest.ordinary_root(args.build_root)
    output_directory = build_root / HEADER_DIRECTORY
    _ordinary_path(output_directory, directory=True)
    output = output_directory / HEADER_NAME
    if output_directory.exists():
        _ordinary_path(output)
    target_json = args.kernel_target_json.absolute()
    if target_json.resolve(strict=True) == output.resolve():
        raise ValueError('Physical compiled-profile output must not overwrite its target input')
    group = args.group.absolute()
    if build_root == group or group in build_root.parents or build_root in group.parents:
        raise ValueError('Physical compiled-profile output must be separate from retained inputs')
    inspection = consumer.verify_kernel_consumer(group,
        expected_recipe=args.recipe_sha256, expected_manifest=args.manifest_sha256,
        expected_proof=args.proof_sha256, expected_runtime=args.runtime_sha256,
        kernel_target=consumer._document(target_json.read_bytes(), 'kernel target'),
        paired_sdk=args.paired_sdk_sha256, required_binding=consumer.PHYSICAL_BINDING)
    header = compiled_header(inspection).encode('utf-8')
    output_directory.mkdir(exist_ok=True)
    _ordinary_path(output_directory, directory=True)
    _ordinary_path(output)
    if not output.exists() or output.read_bytes() != header:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.compiled-profile-', dir=output_directory, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(header)
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print(json.dumps(inspection.as_dict(), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, tarfile.TarError) as error:
        raise SystemExit('appended engine input profile: ' + str(error))
