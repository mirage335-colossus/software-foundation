#!/usr/bin/env python3
"""Verify existing native Foundation SDK inputs without building or repairing them.

The retained native engine has its own independent consumer contract. This helper
binds the Foundation kernel's configured tools and target to its existing Linux
SDK or native Windows dependency export; it never pairs that SDK to the engine.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import appended_engine_manifest as engine_manifest
import dependency_archive
import dependency_store
import sdk_environment
import sdk_manifest
import windows_compiler
import windows_toolchain


ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'verified-native-kernel-sdk'


def _native_windows():
    return os.name == 'nt'


def _pin(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('native kernel SDK requires an independent lowercase SHA256 pin')
    return value


def _same_path(actual, expected, label):
    if actual is None or not str(actual):
        raise ValueError('native kernel SDK requires its configured ' + label)
    actual, expected = Path(actual).resolve(strict=True), Path(expected).resolve(strict=True)
    if actual != expected and not actual.samefile(expected):
        raise ValueError('configured ' + label + ' differs from the verified native kernel SDK')
    return actual


def _sdk_metadata(root, expected_sdk, *, release):
    if sdk_manifest.verify_sdk(root, release=release) != expected_sdk:
        raise ValueError('native kernel SDK manifest differs from its independent pin')
    # Parse the same frozen bytes whose digest was pinned, rather than reading
    # JSON and its digest separately across a possible input replacement.
    raw = (root / 'sdk.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sdk:
        raise ValueError('native kernel SDK changed during admission')
    metadata = json.loads(raw, object_pairs_hook=dependency_archive.object_pairs)
    if not isinstance(metadata, dict) or not isinstance(metadata.get('target'), dict):
        raise ValueError('native kernel SDK metadata requires an explicit target')
    return metadata


def _target(metadata, kernel_target, system):
    engine_manifest.target_contract(kernel_target)
    pair = (kernel_target['system'], kernel_target['processor'])
    if (pair not in {('Linux', 'x86_64'), ('Linux', 'aarch64'), ('Windows', 'x86_64')}
            or kernel_target['system'] != system or kernel_target['pointer_bits'] != 64):
        raise ValueError('native kernel SDK requires its admitted Linux or Windows 64-bit target')
    sdk_target = metadata['target']
    expected = {name: sdk_target.get(name) for name in ('system', 'processor', 'triple')}
    expected['pointer_bits'] = 64
    if expected != kernel_target:
        raise ValueError('native kernel target differs from the exact SDK target and triple')


def _group_snapshot(group, expected_names):
    if group.is_symlink() or not group.is_dir() or {item.name for item in group.iterdir()} != expected_names:
        raise ValueError('native Windows retained dependency group changed during admission')
    result = {}
    for name in sorted(expected_names):
        path = group / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('native Windows retained dependency group requires ordinary files')
        result[name] = dependency_archive.digest(path)
    return result


def _windows_inputs(root, metadata, expected_sdk, dependency_group, cxx_compiler, c_compiler, linker):
    if not _native_windows():
        raise ValueError('native Windows kernel SDK admission requires a native Windows host')
    if metadata.get('kind') != 'windows-dependencies' or not dependency_group:
        raise ValueError('native Windows dependency export requires its matching retained group')
    recipe = metadata.get('recipe_id')
    binary, source, checksum = dependency_store.names(recipe)
    # Keep the nominated path for the group's own ordinary-directory checks.
    group = Path(dependency_group).absolute()
    complete = (group / source).exists()
    verify = dependency_store.verify_group if complete else dependency_store.verify_binary_group
    files = verify(group, recipe)
    expected_names = {binary, checksum} | ({source} if complete else set())
    before = {name: files[name] for name in expected_names}
    archived, archived_sha256 = dependency_archive.inspect_manifest_archive(
        group / binary, 'sdk.json', sdk_archive=True)
    if archived != metadata or archived_sha256 != expected_sdk:
        raise ValueError('restored Windows metadata differs from its exact retained producer metadata')
    provenance = metadata.get('provenance', {})
    external = metadata.get('external_toolchain', {})
    if (metadata['target'].get('system') != 'Windows' or metadata['target'].get('processor') != 'x86_64'
            or provenance.get('toolset') != 'v143' or provenance.get('crt_linkage') != 'static'
            or provenance.get('library_linkage') != 'static' or provenance.get('lto') is not False
            or external.get('toolset') != 'v143'):
        raise ValueError('incompatible native Windows dependency ABI contract')
    if not linker:
        raise ValueError('native Windows kernel SDK requires the configured linker')
    # The shared adapter checks ordinary, singly-linked, native x64 toolkit
    # files selected by both VCToolsInstallDir and PATH. No executable is run.
    selected = windows_compiler._select_toolkit(os.environ)
    snapshots = {name: windows_compiler._snapshot(path) for name, path in selected.items()}
    _same_path(cxx_compiler, selected['cl.exe'], 'CXX compiler')
    if c_compiler:
        _same_path(c_compiler, selected['cl.exe'], 'C compiler')
    _same_path(linker, selected['link.exe'], 'linker')
    actual = windows_toolchain.inspect_selected_linker()
    _same_path(actual['path'], selected['link.exe'], 'selected Microsoft linker')
    from sdk_windows import linker_version
    if linker_version(actual['version']) < linker_version(external.get('minimum_linker')):
        raise ValueError('actual consuming linker is older than the dependency producer')
    if any(windows_compiler._snapshot(selected[name]) != snapshot for name, snapshot in snapshots.items()):
        raise ValueError('selected Microsoft toolkit changed during native kernel admission')
    if _group_snapshot(group, expected_names) != before:
        raise ValueError('native Windows retained dependency group changed during admission')
    return {'dependency_group': str(group), 'dependency_recipe': recipe,
            'selected_tools': {name: snapshot[1] for name, snapshot in snapshots.items()},
            'linker_version': actual['version']}


def verify_native_kernel_sdk(*, sdk=None, windows_dependencies=None, expected_sdk, kernel_target,
                             cxx_compiler, c_compiler=None, sysroot=None, toolchain=None,
                             linker=None, dependency_group=None):
    """Read and bind native kernel inputs; this does not qualify an engine."""
    expected_sdk = _pin(expected_sdk)
    if bool(sdk) == bool(windows_dependencies):
        raise ValueError('select exactly one native Linux SDK or Windows dependency export')
    root = Path(sdk or windows_dependencies).resolve(strict=True)
    release = bool(windows_dependencies)
    metadata = _sdk_metadata(root, expected_sdk, release=release)
    result = {'scope': SCOPE, 'root': str(root), 'sdk_sha256': expected_sdk,
              'kind': 'windows-dependencies' if release else 'linux-sdk'}
    if sdk:
        if linker or dependency_group:
            raise ValueError('Linux kernel SDK admission does not accept Windows dependency inputs')
        if metadata.get('kind') == 'windows-dependencies':
            raise ValueError('native Linux kernel requires its existing Linux SDK')
        _target(metadata, kernel_target, 'Linux')
        sdk_environment.require_clean()
        _same_path(toolchain, ROOT / 'cmake/toolchains/sdk.cmake', 'SDK toolchain')
        target = metadata['target']
        _same_path(cxx_compiler, sdk_manifest.contained(root, target['cxx_compiler']), 'CXX compiler')
        _same_path(sysroot, sdk_manifest.contained(root, target['sysroot']), 'sysroot')
        if c_compiler:
            if not target.get('c_compiler'):
                raise ValueError('native Linux kernel SDK does not declare the configured C compiler')
            _same_path(c_compiler, sdk_manifest.contained(root, target['c_compiler']), 'C compiler')
    else:
        if sysroot or toolchain:
            raise ValueError('Windows kernel SDK admission uses the native Microsoft toolchain')
        _target(metadata, kernel_target, 'Windows')
        result.update(_windows_inputs(root, metadata, expected_sdk, dependency_group,
                                      cxx_compiler, c_compiler, linker))
    if _sdk_metadata(root, expected_sdk, release=release) != metadata:
        raise ValueError('native kernel SDK metadata changed during admission')
    result['target'] = dict(kernel_target)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--sdk', type=Path)
    selection.add_argument('--windows-dependencies', type=Path)
    parser.add_argument('--sdk-sha256', required=True)
    parser.add_argument('--kernel-target-json', type=Path, required=True)
    parser.add_argument('--cxx-compiler', type=Path, required=True)
    for name in ('c-compiler', 'sysroot', 'toolchain', 'linker', 'dependency-group'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args(argv)
    target = dependency_archive.read_json(args.kernel_target_json)
    result = verify_native_kernel_sdk(sdk=args.sdk, windows_dependencies=args.windows_dependencies,
        expected_sdk=args.sdk_sha256, kernel_target=target, cxx_compiler=args.cxx_compiler,
        c_compiler=args.c_compiler, sysroot=args.sysroot, toolchain=args.toolchain,
        linker=args.linker, dependency_group=args.dependency_group)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error))
