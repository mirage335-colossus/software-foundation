#!/usr/bin/env python3
"""Prepare/verify a source-integrity Windows capsule; never build or admit an SDK.

Preparation requires already prepared Windows R/S/B, generator receipt/header,
and a separately pinned complete assembled-source inventory. It does not create
these prerequisites, extract suppliers, establish assembly provenance, inspect
SDK/program bodies, run a generator, or claim native dependency/runtime closure.
Keep inputs quiescent and output privately owned while preparing the capsule.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
import errno
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import secrets
import stat
import sys

import appended_engine_manifest as manifest
import appended_engine_native_actions_contract as actions
import appended_engine_windows_contract as contract

MAX_DOCUMENT = 32 * 1024 * 1024
MAX_ENTRIES = 524288
MAX_FILE = 8 * 1024 * 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024 * 1024
MAX_DEPTH = 64
SCOPE = 'windows-native-handoff-source-integrity-only'
KIND = 'foundation-native-engine-windows-handoff-v1'
SELECTION_KIND = 'foundation-native-engine-windows-handoff-selection-v1'
HEADER = 'BibNativeProviderActionsMetadata.generated.h'
GENERATOR = 'source/native/runtime/generate_native_actions_metadata.py'
TEMPLATE = 'source/native/runtime/native-provider-actions-metadata.h.in'
CONFIG = 'source/native/prelink-actions-config.json'
PATHS = {'retained': 'retained', 'assembled': 'assembled',
    'provider_build': 'metadata/provider-build.json', 'metadata_header': 'metadata/' + HEADER,
    'metadata_receipt': 'metadata/metadata-receipt.json',
    'assembled_inventory': 'metadata/assembled-inventory.json',
    'native_inputs': 'metadata/native-windows-inputs.json'}
REFS = ('recipe', 'sources', 'provider_build', 'metadata_header',
        'metadata_receipt', 'assembled_inventory', 'native_inputs')
FALSE_FACTS = ('build', 'production_eligible', 'engine_execution', 'kernel_rebuild')
MissingInputs = contract.MissingInputs
encoded = contract.encoded


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _document(raw):
    if len(raw) > MAX_DOCUMENT:
        raise ValueError('Windows handoff document exceeds its finite bound')
    # This parser is strict about duplicate fields, encodings and nonfinite data.
    # Its smaller input-contract bound does not apply to full source inventories.
    try:
        value = manifest.json_bytes(raw)
        pending = [(value, 0)]
        while pending:
            child, depth = pending.pop()
            if depth > MAX_DEPTH:
                raise ValueError('Windows handoff JSON exceeds finite nesting bound')
            if type(child) is str:
                child.encode('utf-8')
            elif type(child) is dict:
                pending.extend((item, depth + 1) for pair in child.items() for item in pair)
            elif type(child) is list:
                pending.extend((item, depth + 1) for item in child)
        encoded(value)
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid Windows handoff JSON encoding/nesting') from error
    return value


def _absolute(value):
    if type(value) is not str:
        raise ValueError('Local normalized absolute host path required')
    path = Path(value)
    if os.name == 'nt':
        # Accept canonical slash-separated selectors as well as native Path
        # strings. Reject UNC/device/ADS/drive-relative/trailing aliases first.
        contract.windows_path(PureWindowsPath(value).as_posix(), 'handoff host path')
        normalized = value in (str(path), path.as_posix())
    else:
        normalized = str(path) == value and value.startswith('/') and not value.startswith('//')
    if not path.is_absolute() or not normalized or '..' in path.parts:
        raise ValueError('Local normalized absolute host path required')
    return path


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _qualified_posix():
    required = (os.open, os.stat, os.mkdir, os.unlink)
    if (os.name != 'posix' or not sys.platform.startswith('linux') or
            not all(hasattr(os, name) for name in ('O_NOFOLLOW', 'O_DIRECTORY', 'O_NONBLOCK')) or
            any(function not in os.supports_dir_fd for function in required) or
            os.scandir not in os.supports_fd or not hasattr(os, 'geteuid')):
        raise ValueError('Qualified POSIX anchored publication primitives are unavailable')


class _Anchor:
    """Keep a directory inode anchored; reopen its whole path at checkpoints."""
    def __init__(self, path):
        self.path = _absolute(os.fspath(path))
        descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in self.path.parts[1:]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
                manifest.plain_state(os.fstat(descriptor), directory=True)
            self.fd = descriptor
            self.physical = _identity(os.fstat(descriptor))[:2]
        except BaseException:
            os.close(descriptor)
            raise

    def check(self):
        other = _Anchor(self.path)
        try:
            if self.physical != other.physical or _identity(os.fstat(self.fd))[:2] != self.physical:
                raise ValueError('Windows handoff directory path identity changed')
        finally:
            other.close()

    def close(self):
        os.close(self.fd)


def _names(descriptor):
    result = []
    fresh = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
    try:
        with os.scandir(fresh) as entries:
            for entry in entries:
                if len(result) >= MAX_ENTRIES:
                    raise ValueError('Windows handoff directory exceeds entry bound')
                result.append(entry.name)
    finally:
        os.close(fresh)
    return sorted(result)


def _read_fd(directory, name, maximum=MAX_DOCUMENT, output=None, expected=None, *, snapshot=False):
    before = manifest.plain_state(os.stat(name, dir_fd=directory, follow_symlinks=False), False)
    if expected is not None and _identity(before) != _identity(expected):
        raise ValueError('Windows handoff file identity/mode changed before capture')
    if before.st_size > maximum:
        raise ValueError('Windows handoff file exceeds byte bound: ' + name)
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    chunks, hasher, count = ([] if output is None else None), hashlib.sha256(), 0
    try:
        if _identity(manifest.plain_state(os.fstat(descriptor), False)) != _identity(before):
            raise ValueError('Windows handoff input changed before read')
        while True:
            block = os.read(descriptor, min(1024 * 1024, maximum - count + 1))
            if not block:
                break
            count += len(block)
            if count > maximum:
                raise ValueError('Windows handoff file exceeds byte bound')
            hasher.update(block)
            if output is None:
                chunks.append(block)
            else:
                view = memoryview(block)
                while view:
                    written = os.write(output, view)
                    if written <= 0:
                        raise ValueError('Incomplete Windows handoff output write')
                    view = view[written:]
        if (_identity(os.fstat(descriptor)) != _identity(before) or
                _identity(os.stat(name, dir_fd=directory, follow_symlinks=False)) != _identity(before) or
                count != before.st_size):
            raise ValueError('Windows handoff input changed during read')
    finally:
        os.close(descriptor)
    result = b''.join(chunks) if output is None else hasher.hexdigest()
    return (result, _identity(before)) if snapshot else result


def _read(path, *, snapshot=False):
    path = _absolute(os.fspath(path))
    if os.name == 'nt':
        manifest.ordinary_root(path.parent)
        before = manifest.plain_state(path.lstat(), False)
        if before.st_size > MAX_DOCUMENT:
            raise ValueError('Windows handoff document exceeds bound')
        with path.open('rb') as stream:
            opened = manifest.plain_state(os.fstat(stream.fileno()), False)
            if _identity(opened) != _identity(before):
                raise ValueError('Windows handoff document changed before opening')
            raw = stream.read(MAX_DOCUMENT + 1)
            after = manifest.plain_state(os.fstat(stream.fileno()), False)
        manifest.ordinary_root(path.parent)
        if (_identity(after) != _identity(before) or _identity(path.lstat()) != _identity(before) or
                len(raw) != before.st_size or len(raw) > MAX_DOCUMENT):
            raise ValueError('Windows handoff document changed during read')
        return (raw, _identity(before)) if snapshot else raw
    anchor = _Anchor(path.parent)
    try:
        raw = _read_fd(anchor.fd, path.name, snapshot=snapshot)
        anchor.check()
        return raw
    finally:
        anchor.close()


def _inventory_contract(value):
    manifest.fields(value, ('files', 'directories', 'modes'), 'Windows handoff complete inventory')
    manifest.inventory_contract(value, '__excluded_manifest__.json')
    if len(value['files']) + len(value['directories']) > MAX_ENTRIES:
        raise ValueError('Windows handoff complete inventory exceeds entry bound')
    for name in (*value['files'], *value['directories']):
        if len(name) > 4096 or len(name.split('/')) > MAX_DEPTH:
            raise ValueError('Windows handoff path exceeds finite depth/length bound')
    return value


def _scan_windows(root, expected, omitted=()):
    """Cross-host logical modes, bounded ordinary-tree reads; no publication."""
    root = manifest.ordinary_root(root)
    files, directories, modes = {}, [], {}
    allowed_directories = set(expected['directories'])
    total, count, identities = 0, 0, set()
    def walk(directory, prefix, depth):
        nonlocal total, count
        if depth > MAX_DEPTH:
            raise ValueError('Windows handoff tree exceeds finite depth bound')
        before = manifest.plain_state(directory.lstat(), True)
        physical = _identity(before)[:2]
        if physical in identities:
            raise ValueError('Physically aliased Windows handoff directory')
        identities.add(physical)
        names = []
        with os.scandir(directory) as stream:
            for item in stream:
                if count + len(names) >= MAX_ENTRIES:
                    raise ValueError('Windows handoff tree exceeds entry bound')
                names.append(item.name)
        for base in sorted(names):
            count += 1
            name = manifest.path_name(prefix + base)
            if len(name) > 4096:
                raise ValueError('Windows handoff path exceeds length bound')
            path = directory / base
            state = manifest.plain_state(path.lstat())
            is_directory = stat.S_ISDIR(state.st_mode)
            if name in omitted:
                if is_directory:
                    raise ValueError('Windows handoff root manifest must be ordinary')
                continue
            if is_directory:
                if name not in allowed_directories:
                    raise ValueError('Unknown Windows handoff directory: ' + name)
                directories.append(name)
                modes[name] = expected['modes'][name]
                walk(path, name + '/', depth + 1)
            else:
                if name not in expected['files']:
                    raise ValueError('Unknown Windows handoff file: ' + name)
                total += state.st_size
                if state.st_size > MAX_FILE or total > MAX_BYTES:
                    raise ValueError('Windows handoff source exceeds byte bound')
                hasher, size = hashlib.sha256(), 0
                with path.open('rb') as stream:
                    if _identity(manifest.plain_state(os.fstat(stream.fileno()), False)) != _identity(state):
                        raise ValueError('Windows handoff file changed before read')
                    while True:
                        block = stream.read(min(1024 * 1024, MAX_FILE - size + 1))
                        if not block:
                            break
                        size += len(block)
                        if size > MAX_FILE or total - state.st_size + size > MAX_BYTES:
                            raise ValueError('Windows handoff file exceeds byte bound')
                        hasher.update(block)
                    if _identity(manifest.plain_state(os.fstat(stream.fileno()), False)) != _identity(state):
                        raise ValueError('Windows handoff file changed during read')
                if _identity(manifest.plain_state(path.lstat(), False)) != _identity(state) or size != state.st_size:
                    raise ValueError('Windows handoff file changed after read')
                files[name], modes[name] = hasher.hexdigest(), expected['modes'][name]
        after_names = []
        with os.scandir(directory) as stream:
            for item in stream:
                if len(after_names) >= MAX_ENTRIES:
                    raise ValueError('Windows handoff tree exceeds entry bound')
                after_names.append(item.name)
        manifest.ordinary_root(directory)
        if sorted(names) != sorted(after_names) or _identity(directory.lstat()) != _identity(before):
            raise ValueError('Windows handoff directory changed during scan')
    walk(root, '', 1)
    actual = {'files': files, 'directories': sorted(directories), 'modes': modes}
    if actual != expected:
        raise ValueError('Complete Windows handoff inventory differs')
    return actual


def _scan(root, expected, *, destination=None, omitted=()):
    """Bounded complete inventory, copying through inode anchors when requested."""
    _inventory_contract(expected)
    if os.name == 'nt':
        if destination is not None:
            raise ValueError('Windows handoff publication requires qualified POSIX')
        return _scan_windows(root, expected, omitted)
    source = _Anchor(root)
    output = _Anchor(destination) if destination is not None else None
    actual = {'files': {}, 'directories': [], 'modes': {}}
    total, entries, identities = 0, 0, set()
    allowed_directories = set(expected['directories'])
    def walk(descriptor, target, prefix, depth):
        nonlocal total, entries
        before = _identity(manifest.plain_state(os.fstat(descriptor), True))
        if before[:2] in identities:
            raise ValueError('Physically aliased Windows handoff directories')
        identities.add(before[:2])
        names = _names(descriptor)
        for base in names:
            name = prefix + base
            manifest.path_name(name)
            entries += 1
            if entries > MAX_ENTRIES or depth > MAX_DEPTH or len(name) > 4096:
                raise ValueError('Windows handoff tree exceeds finite entry/depth bound')
            state = manifest.plain_state(os.stat(base, dir_fd=descriptor, follow_symlinks=False))
            directory = stat.S_ISDIR(state.st_mode)
            mode = stat.S_IMODE(state.st_mode)
            if name in omitted:
                if directory or mode != 0o644:
                    raise ValueError('Windows handoff root manifest must be ordinary0644')
                continue
            if directory:
                if name not in allowed_directories or mode != 0o755:
                    raise ValueError('Unknown or wrong-mode Windows handoff directory: ' + name)
                actual['directories'].append(name)
                actual['modes'][name] = mode
                child = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
                copied = None
                try:
                    if _identity(os.fstat(child)) != _identity(state):
                        raise ValueError('Windows handoff directory changed before traversal')
                    if target is not None:
                        os.mkdir(base, 0o700, dir_fd=target)
                        copied = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=target)
                    walk(child, copied, name + '/', depth + 1)
                    if copied is not None:
                        os.fchmod(copied, 0o755)
                        os.fsync(copied)
                    if _identity(os.stat(base, dir_fd=descriptor, follow_symlinks=False)) != _identity(state):
                        raise ValueError('Windows handoff directory changed during traversal')
                finally:
                    if copied is not None:
                        os.close(copied)
                    os.close(child)
            else:
                if name not in expected['files'] or mode != expected['modes'].get(name):
                    raise ValueError('Unknown or wrong-mode Windows handoff file: ' + name)
                total += state.st_size
                if total > MAX_BYTES or state.st_size > MAX_FILE:
                    raise ValueError('Windows handoff tree exceeds finite byte bound')
                target_fd = None
                try:
                    if target is not None:
                        target_fd = os.open(base, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                            0o600, dir_fd=target)
                    # A disposable hash sink keeps verification memory bounded.
                    if target_fd is None:
                        with open(os.devnull, 'wb') as sink:
                            pin = _read_fd(descriptor, base, min(MAX_FILE, MAX_BYTES - total + state.st_size), sink.fileno(), state)
                    else:
                        pin = _read_fd(descriptor, base, min(MAX_FILE, MAX_BYTES - total + state.st_size), target_fd, state)
                        os.fchmod(target_fd, mode)
                        os.fsync(target_fd)
                    actual['files'][name] = pin
                    actual['modes'][name] = mode
                finally:
                    if target_fd is not None:
                        os.close(target_fd)
        if names != _names(descriptor) or before != _identity(os.fstat(descriptor)):
            raise ValueError('Windows handoff directory changed during scan')
    try:
        walk(source.fd, output.fd if output else None, '', 1)
        actual['directories'].sort()
        source.check()
        if output:
            output.check()
        if actual != expected:
            raise ValueError('Complete Windows handoff bytes/directories/modes differ')
        return actual
    finally:
        source.close()
        if output:
            output.close()


def _retained_inventory(sources, source_sha256):
    return {'files': {**sources['files'], 'sources.json': source_sha256},
            'directories': sources['directories'], 'modes': {**sources['modes'], 'sources.json': 0o644}}


def _expected_build(recipe, recipe_pin):
    return {'schema_version': 1, 'kind': actions.BUILD_KIND, 'target': recipe['target'],
        'toolchain': recipe['toolchain'], 'options': recipe['options'],
        'source_recipe_sha256': recipe_pin, 'source_inputs_sha256': digest(encoded(recipe['inputs'])),
        'contract_header_sha256': actions.CONTRACT_SHA256, 'binding': actions.BINDING,
        'configuration': actions.expected_configuration(actions_profile=actions.SELECTOR),
        'capabilities': '4083', 'provider_contract': actions.provider_contract(
            kernel_target=recipe['target'], actions_profile=actions.SELECTOR),
        'provider_limits': dict(actions.PROVIDER_LIMITS)}


def _joined(raw, retained_read):
    recipe, sources, build = (_document(raw[name]) for name in ('recipe', 'sources', 'provider_build'))
    recipe_pin, sources_pin, build_pin = (digest(raw[name]) for name in ('recipe', 'sources', 'provider_build'))
    manifest.recipe_contract(recipe)
    manifest.source_contract(sources, recipe, recipe_pin)
    if recipe['target'] != contract.TARGET:
        raise ValueError('Prepared Windows recipe target differs; Linux/Wasm reuse is forbidden')
    if recipe['provider'] != {'format': 'native-shared', 'binding': 'c-abi',
            'abi_major': 1, 'abi_minor': 1, 'header': 'include/foundation/appended/engine_provider.h',
            'header_sha256': actions.BASE_HEADER_SHA256}:
        raise ValueError('Prepared Windows recipe differs from exact ABI1.1 rich4083 provider')
    if encoded(build) != raw['provider_build'] or build != _expected_build(recipe, recipe_pin):
        raise ValueError('Prepared Windows provider build differs from exact source/target/ABI/configuration')
    assembled = _inventory_contract(_document(raw['assembled_inventory']))
    if 'source/engine/CMakeLists.txt' not in assembled['files']:
        raise MissingInputs([{'role': 'assembled-native-source', 'path': 'source/engine/CMakeLists.txt',
            'reason': 'complete prepared native supplier tree is required'}])
    def pinned_body(pin):
        candidates = sorted(name for name, item in recipe['inputs'].items() if item['sha256'] == pin)
        if not candidates:
            raise ValueError('Retained source omits current source catalogue pin')
        body = retained_read(candidates[0])
        if digest(body) != pin:
            raise ValueError('Retained source catalogue bytes differ')
        return body
    catalogue_raw = {role: pinned_body(item['sha256']) for role, item in contract.CATALOGUE.items()}
    source_map, provenance = (_document(catalogue_raw[name]) for name in ('source_map', 'provenance'))
    inputs = source_map.get('inputs')
    if type(inputs) is not dict:
        raise ValueError('Current native source map has no complete inputs')
    for name, item in inputs.items():
        expected = {key: item[key] for key in ('sha256', 'mode')}
        expected['role'] = {'provenance': 'data', 'patch': 'data'}.get(item['role'], item['role'])
        if any(recipe['inputs'].get(name, {}).get(key) != value for key, value in expected.items()):
            raise ValueError('Retained source differs from current common source map: ' + name)
    overlays = {name: item for name, item in inputs.items()
                if name.startswith('source/') and item.get('role') == 'source'}
    graph = catalogue_raw['graph'].decode('utf-8')
    block = re.search(r'set\(_sources\s+(.*?)\)\s*# document_forms', graph, re.S)
    units = re.findall(r'"[^"\n]+"', block.group(1)) if block else []
    counts = {'source_files': len(overlays),
        'engine_files': sum(name.startswith('source/engine/') for name in overlays),
        'direct_translation_units': len(units)}
    if counts != {'source_files': 157, 'engine_files': 48, 'direct_translation_units': 32} or any(
            provenance.get('source_graph', {}).get(key) != value for key, value in counts.items()):
        raise ValueError('Prepared common native157/engine48/32TU graph differs')
    for name, item in overlays.items():
        if assembled['files'].get(name) != item['sha256'] or assembled['modes'].get(name) != item['mode']:
            raise ValueError('Assembled native overlay differs: ' + name)
    mapping = provenance.get('retained_input_mapping')
    if type(mapping) is not dict or len(mapping) != 25:
        raise ValueError('Current native metadata alias closure must contain25 entries')
    for name, item in mapping.items():
        original = inputs.get(item['tracked_source'], {})
        selected = recipe['inputs'].get(name, {})
        if (item['sha256'] != original.get('sha256') or selected.get('sha256') != item['sha256'] or
                selected.get('role') != item['role'] or selected.get('mode') != original.get('mode')):
            raise ValueError('Retained native metadata provenance alias differs: ' + name)
    expected_config = {'schema_version': 1, 'kind': 'foundation-native-provider-actions-prelink-config-v1',
        'document_profile': actions.PROFILE_NAME, 'profile_kind': 4,
        'provider_limits': dict(actions.PROVIDER_LIMITS),
        'service_retention': {'max_retained_bytes': 4194304, 'max_retained_calls': 64}}
    if _document(retained_read(CONFIG)) != expected_config:
        raise ValueError('Retained fixed native prelink configuration differs')
    # Reconstruct current generator output as data, never importing/executing
    # any retained helper or generator. Provenance pins its generator/template.
    template = retained_read(TEMPLATE).decode('ascii')
    def literal(pin):
        contract.pin(pin, 'generated metadata')
        return ','.join('0x' + pin[index:index + 2] for index in range(0, 64, 2))
    def operation(item):
        return '{' + ','.join((str(item['operation']), str(item['maximum_input_bytes']),
            str(item['required_reply_capacity']), 'UINT64_C(' + item['capability'] + ')',
            '{' + literal(item['schema_sha256']) + '}')) + '}'
    values = {'TARGET_SYSTEM': '2', 'TARGET_PROCESSOR': '1',
        'SOURCE_RECIPE_SHA256_BYTES': literal(recipe_pin), 'BUILD_IDENTITY_SHA256_BYTES': literal(build_pin),
        'SOURCE_INPUTS_SHA256_BYTES': literal(build['source_inputs_sha256']),
        'TOOLCHAIN_IDENTITY_SHA256_BYTES': literal(recipe['toolchain']['identity_sha256']),
        'QUERIES': ',\n    '.join(operation(item) for item in build['provider_contract']['queries']),
        'COMMANDS': ',\n    '.join(operation(item) for item in build['provider_contract']['commands'])}
    pins = provenance.get('interface_pins')
    if type(pins) is not dict or len(pins) != 16 or GENERATOR not in mapping or TEMPLATE not in mapping:
        raise ValueError('Current rich4083 metadata source closure differs')
    for key, item in pins.items():
        if recipe['inputs'].get(item['retained_logical_path'], {}).get('sha256') != item['sha256']:
            raise ValueError('Retained rich4083 interface provenance differs')
        values[key.upper() + '_SHA256_BYTES'] = literal(item['sha256'])
    tokens = set(re.findall(r'@([A-Z0-9_]+)@', template))
    if tokens != set(values):
        raise ValueError('Retained current metadata template token closure differs')
    for key, value in values.items():
        template = template.replace('@' + key + '@', value)
    if '@' in template or '#error "DESIGN TEMPLATE' in template or template.encode('ascii') != raw['metadata_header']:
        raise ValueError('Generated metadata header differs from exact source/build/target/toolchain join')
    receipt = _document(raw['metadata_receipt'])
    profile = actions.expected_engine_profile(kernel_target=recipe['target'], actions_profile=actions.SELECTOR,
        build_sha256=build_pin, source_recipe_sha256=recipe_pin)
    manifest.fields(receipt, ('scope', 'production_eligible', 'engine_execution', 'recipe_sha256',
        'source_manifest_sha256', 'provider_build_sha256', 'source_inputs_sha256', 'target',
        'engine_profile', 'header', 'header_sha256'), 'current native metadata generator receipt')
    wanted = {'scope': 'native-document-actions-provider-metadata-source-integrity-only',
        'production_eligible': False, 'engine_execution': False, 'recipe_sha256': recipe_pin,
        'source_manifest_sha256': sources_pin, 'provider_build_sha256': build_pin,
        'source_inputs_sha256': build['source_inputs_sha256'], 'target': contract.TARGET,
        'engine_profile': profile, 'header': receipt['header'], 'header_sha256': digest(raw['metadata_header'])}
    header_path = receipt['header']
    if (type(header_path) is not str or not header_path.startswith('/') or
            PurePosixPath(header_path).as_posix() != header_path or
            '..' in PurePosixPath(header_path).parts or PurePosixPath(header_path).name != HEADER or
            encoded(receipt) != encoded(wanted)):
        raise ValueError('Original native metadata generator receipt differs from current exact shape/joins')
    native = contract.validate_inputs(_document(raw['native_inputs']))
    return {'target': copy.deepcopy(contract.TARGET), 'source_catalogue': copy.deepcopy(contract.CATALOGUE),
        'recipe_sha256': recipe_pin, 'sources_sha256': sources_pin, 'provider_build_sha256': build_pin,
        'metadata_header_sha256': digest(raw['metadata_header']),
        'toolchain_identity_sha256': recipe['toolchain']['identity_sha256'], 'native_inputs': native,
        'scope': SCOPE, 'dependency_admission': 'unimplemented-source-closure-required',
        'assembly_provenance': 'independently-pinned-inventory-not-supplier-replay-proof',
        **{name: False for name in FALSE_FACTS}}, _retained_inventory(sources, sources_pin), assembled


def _selection(path, pin):
    raw_selection = _read(path)
    if digest(raw_selection) != contract.pin(pin, 'handoff selection'):
        raise ValueError('Windows handoff selection pin differs')
    value = _document(raw_selection)
    manifest.fields(value, ('schema_version', 'kind', 'target', 'source_catalogue',
        'retained_root', 'assembled_root', *REFS), 'Windows handoff selection')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != SELECTION_KIND or
            value['target'] != contract.TARGET or value['source_catalogue'] != contract.CATALOGUE):
        raise ValueError('Windows handoff selection target/current catalogue differs')
    retained, assembled = (_absolute(value[name]) for name in ('retained_root', 'assembled_root'))
    if retained == assembled or retained in assembled.parents or assembled in retained.parents:
        raise ValueError('Retained and assembled Windows source roots must be disjoint')
    raw, paths, missing = {}, {}, []
    for role in REFS:
        manifest.fields(value[role], ('path', 'sha256'), 'Windows handoff ' + role)
        paths[role] = _absolute(value[role]['path'])
        contract.pin(value[role]['sha256'], role)
        try:
            raw[role] = _read(paths[role])
        except FileNotFoundError:
            missing.append({'role': role, 'path': str(paths[role]), 'reason': 'explicit prepared Windows input absent'})
            continue
        if digest(raw[role]) != value[role]['sha256']:
            raise ValueError('Pinned prepared Windows input differs: ' + role)
    if missing:
        raise MissingInputs(missing)
    if paths['recipe'] != retained / 'recipe.json' or paths['sources'] != retained / 'sources.json' or paths['metadata_header'].name != HEADER:
        raise ValueError('Prepared R/S/header selection must name exact original source roles')
    receipt = _document(raw['metadata_receipt'])
    if type(receipt) is not dict or receipt.get('header') != str(paths['metadata_header']):
        raise ValueError('Original metadata receipt header path differs from selected original generated header')
    facts, retained_inventory, assembled_inventory = _joined(raw,
        lambda name: _read(retained / manifest.path_name(name)))
    for root, inventory in ((retained, retained_inventory), (assembled, assembled_inventory)):
        try:
            _scan(root, inventory)
        except FileNotFoundError as error:
            raise MissingInputs([{'role': 'prepared-native-source-tree', 'path': str(root),
                'reason': 'complete explicitly prepared source tree is absent'}]) from error
    return facts, retained_inventory, assembled_inventory, raw, value


def verify_handoff(root, expected_sha256):
    root = _absolute(os.fspath(root))
    manifest_path = root / 'handoff.json'
    raw_manifest, manifest_identity = _read(manifest_path, snapshot=True)
    if digest(raw_manifest) != contract.pin(expected_sha256, 'Windows handoff manifest'):
        raise ValueError('Windows handoff manifest pin differs')
    def recheck_manifest():
        checked_raw, checked_identity = _read(manifest_path, snapshot=True)
        if (checked_raw != raw_manifest or checked_identity != manifest_identity or
                digest(checked_raw) != expected_sha256):
            raise ValueError('Windows handoff root manifest changed during verification')
    value = _document(raw_manifest)
    manifest.fields(value, ('schema_version', 'kind', 'scope', 'target', 'source_catalogue', 'paths',
        'files', 'directories', 'modes', 'build', 'production_eligible', 'engine_execution', 'kernel_rebuild'), 'Windows handoff manifest')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != KIND or
            value['scope'] != SCOPE or value['target'] != contract.TARGET or value['source_catalogue'] != contract.CATALOGUE or
            value['paths'] != PATHS or any(value[name] is not False for name in FALSE_FACTS)):
        raise ValueError('Windows handoff exact source-only contract differs')
    inventory = {name: value[name] for name in ('files', 'directories', 'modes')}
    _scan(root, inventory, omitted=('handoff.json',))
    recheck_manifest()
    raw = {role: _read(root / ('retained/' + role + '.json' if role in ('recipe', 'sources') else PATHS[role])) for role in REFS}
    facts, retained, assembled = _joined(raw, lambda name: _read(root / 'retained' / manifest.path_name(name)))
    def subinventory(prefix):
        return {'files': {name[len(prefix):]: pin for name, pin in inventory['files'].items() if name.startswith(prefix)},
            'directories': [name[len(prefix):] for name in inventory['directories'] if name.startswith(prefix)],
            'modes': {name[len(prefix):]: mode for name, mode in inventory['modes'].items() if name.startswith(prefix)}}
    if subinventory('retained/') != retained or subinventory('assembled/') != assembled:
        raise ValueError('Windows capsule payload differs from original retained/assembled closure')
    expected = _combined_inventory(retained, assembled, raw)
    if inventory != expected:
        raise ValueError('Windows capsule contains unknown payload files/directories or metadata modes')
    facts.update({'root': str(root), 'handoff_sha256': expected_sha256, 'paths': dict(PATHS),
        'files': inventory['files'], 'directories': inventory['directories'], 'modes': inventory['modes'],
        'protected_paths': [str(root)]})
    # The root manifest is excluded from its own inventory. Preserve its exact
    # opened-file identity as well as bytes across both payload and join checks;
    # a same-byte inode replacement is an observed input change, not a pass.
    recheck_manifest()
    return facts


def _combined_inventory(retained, assembled, raw):
    files, directories, modes = {}, ['assembled', 'metadata', 'retained'], {
        'assembled': 0o755, 'metadata': 0o755, 'retained': 0o755}
    for prefix, inventory in (('retained', retained), ('assembled', assembled)):
        files.update({prefix + '/' + name: pin for name, pin in inventory['files'].items()})
        directories.extend(prefix + '/' + name for name in inventory['directories'])
        modes.update({prefix + '/' + name: mode for name, mode in inventory['modes'].items()})
    for role in REFS:
        if role not in ('recipe', 'sources'):
            files[PATHS[role]], modes[PATHS[role]] = digest(raw[role]), 0o644
    return {'files': files, 'directories': sorted(directories), 'modes': modes}


def _save(directory, name, raw):
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ValueError('Incomplete Windows handoff metadata write')
            view = view[written:]
        os.fchmod(descriptor, 0o644)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(parent, staged, output):
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, 'renameat2', None)
    if rename is None:
        raise ValueError('Atomic no-replace Windows handoff publication unavailable')
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    parent.check()
    if rename(parent.fd, os.fsencode(staged), parent.fd, os.fsencode(output), 1) != 0:
        error = ctypes.get_errno()
        if error in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, errno.EXDEV):
            raise ValueError('Qualified filesystem atomic no-replace publication unavailable')
        raise OSError(error, os.strerror(error), output)
    os.fsync(parent.fd)
    parent.check()


def create_handoff(selection_path, selection_sha256, output):
    _qualified_posix()
    selection_path, output = _absolute(os.fspath(selection_path)), _absolute(os.fspath(output))
    facts, retained, assembled, raw, selection = _selection(selection_path, selection_sha256)
    protected = [selection_path, *(_absolute(selection[name]) for name in ('retained_root', 'assembled_root')),
                 *(_absolute(selection[role]['path']) for role in REFS)]
    if any(output == path or output in path.parents or path in output.parents for path in protected):
        raise ValueError('Windows handoff output overlaps a selected input')
    parent = _Anchor(output.parent)
    temporary = '.windows-handoff-' + secrets.token_hex(16)
    stage = output.parent / temporary
    try:
        try:
            os.stat(output.name, dir_fd=parent.fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError('Windows handoff output already exists; preserve it')
        os.mkdir(temporary, 0o700, dir_fd=parent.fd)
        stage_anchor = _Anchor(stage)
        try:
            state = os.fstat(stage_anchor.fd)
            if state.st_uid != os.geteuid() or stat.S_IMODE(state.st_mode) != 0o700:
                raise ValueError('Fresh Windows capsule stage must be caller-owned private0700')
            for name in ('retained', 'assembled', 'metadata'):
                os.mkdir(name, 0o755, dir_fd=stage_anchor.fd)
                descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=stage_anchor.fd)
                try:
                    os.fchmod(descriptor, 0o755)
                finally:
                    os.close(descriptor)
            _scan(selection['retained_root'], retained, destination=stage / 'retained')
            _scan(selection['assembled_root'], assembled, destination=stage / 'assembled')
            metadata = _Anchor(stage / 'metadata')
            try:
                for role in REFS:
                    if role not in ('recipe', 'sources'):
                        _save(metadata.fd, Path(PATHS[role]).name, raw[role])
            finally:
                metadata.close()
            value = {'schema_version': 1, 'kind': KIND, 'scope': SCOPE, 'target': contract.TARGET,
                'source_catalogue': contract.CATALOGUE, 'paths': PATHS,
                **_combined_inventory(retained, assembled, raw), **{name: False for name in FALSE_FACTS}}
            manifest_raw = encoded(value)
            _save(stage_anchor.fd, 'handoff.json', manifest_raw)
            verify_handoff(stage, digest(manifest_raw))
            # Recheck independent selected bytes and complete source trees after
            # capture. A pathname hash never supplies exclusion against writers.
            _selection(selection_path, selection_sha256)
            stage_anchor.check()
            os.fsync(stage_anchor.fd)
            _publish(parent, temporary, output.name)
        finally:
            stage_anchor.close()
        return verify_handoff(output, digest(manifest_raw))
    finally:
        # Preserve failed/uncertain private staging evidence; never recursively
        # delete names that may have changed identity after an interrupted copy.
        parent.close()


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    check = commands.add_parser('check')
    check.add_argument('--root', required=True)
    check.add_argument('--sha256', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--selection', required=True)
    prepare.add_argument('--selection-sha256', required=True)
    prepare.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        result = (verify_handoff(args.root, args.sha256) if args.action == 'check' else
                  create_handoff(args.selection, args.selection_sha256, args.output))
        print(encoded(result).decode('ascii'), end='')
        return 0
    except MissingInputs as error:
        print(encoded(error.as_dict()).decode('ascii'), end='')
        return 2
    except (ValueError, OSError) as error:
        print('Windows engine handoff: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(cli())
