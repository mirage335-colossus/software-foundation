#!/usr/bin/env python3
"""Generate source-only document copied-provider metadata, without build tools.

The retained root's exact recipe and complete inputs bind this generator, its
template and its prelink plan. provider-build.json never hashes itself: only
the generated header carries that output's actual byte hash. Source and output
roots must already exist, be ordinary directories and be disjoint. Invocation
does not establish an actual engine producer, SDK, link or runtime result.

The unchanged retained recipe schema keeps its six provider fields, with ABI
1.1 and the base header's *file* hash. Document pins live in the retained prelink
plan, not extra recipe fields. The exact retained pure document contract controls
Build fields, provider operations and the explicitly selected pixel/physical/editor
profile. This adapter never widens it.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import types

sys.dont_write_bytecode = True
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_FACTS = 4095
BINDING = 'copied-owner-bridge/direct-worker-document-v2'
CONTRACT_HELPER = 'tools/appended_engine_document_contract.py'
EDITOR_CONTRACT_HELPER = 'tools/appended_engine_editor_contract.py'
EDITOR_CONTRACT_HELPER_SHA256 = '198ca94d231f58fdd027cd8bd1142d6d3fcbdc1e1975d127930eb400e77238c3'
PHYSICAL_CATALOG = 'abi/engine/physical-input-catalog.json'
LIMITS = {
    'size': 48, 'maximum_command_bytes': 6246, 'maximum_query_bytes': 48,
    'maximum_reply_bytes': 1048576, 'maximum_service_message_bytes': 1048576,
    'maximum_retired_documents': 8, 'maximum_inflight_resources': 64,
    'reserved': 0, 'maximum_resource_response_bytes': 67108864,
    'maximum_retained_resource_bytes': 134217728,
}
RETENTION = {'maximum_pending_services': 64, 'maximum_pending_bytes': 4194304}
PINS = {
    'base_header_sha256': 'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d',
    'document_header_sha256': '7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626',
    'contract_sha256': 'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298',
    'document_catalog_sha256': '6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5',
    'semantic_snapshot_schema_sha256': 'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d',
    'form_action_schema_sha256': 'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d',
    'ack_schema_sha256': '1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5',
}
PIN_FILES = {
    'contract_header': ('include/foundation/appended/engine_provider.h', 'base_header_sha256'),
    'document_header': ('include/foundation/appended/engine_provider_document_v2.h', 'document_header_sha256'),
    'document_contract': ('abi/engine/document-v2/contract.json', 'contract_sha256'),
    'document_catalog': ('abi/engine/document-v2/catalog.json', 'document_catalog_sha256'),
    'document_schema': ('abi/engine/document-v2/schema-definition.json', 'semantic_snapshot_schema_sha256'),
    'action_ack': ('abi/engine/document-v2/action-ack.json', 'ack_schema_sha256'),
}
EDITOR_PINS = {
    'editor_header_sha256': 'bdd9bf16765513be402481ab85dd596263fd4ac66a0dfc1dcc7ba5314ec85034',
    'editor_contract_sha256': '0d43707e404979a38e0e8d7a7bc47042be95ae54216ed118a4de3314302b8c9c',
    'editor_catalog_sha256': '34fadacf563a00918255e4dc94b196bf0dc5c8ed57c7165e3da1e5fdd4d06bb8',
    'editor_schema_sha256': 'f2a6202056bd7fb6872539ba1e8806296ae6f6409ab2a21b9b581f19a4c7d4b1',
}
EDITOR_PIN_FILES = {
    'editor_header': ('abi/appended/engine_editor_protocol.h', 'editor_header_sha256'),
    'editor_contract': ('abi/appended/editor-v1/contract.json', 'editor_contract_sha256'),
    'editor_catalog': ('abi/appended/editor-v1/catalog.json', 'editor_catalog_sha256'),
    'editor_schema': ('abi/appended/editor-v1/binary-schema.json', 'editor_schema_sha256'),
}
EDITOR_LIMITS = {**LIMITS, 'maximum_command_bytes': 1048576, 'maximum_query_bytes': 236}
HELPERS = ('tools/dependency_archive.py', 'tools/appended_engine_manifest.py',
           'tools/appended_engine_sdk.py')
CIRCULAR_FIELDS = frozenset((
    'recipe_id', 'source_recipe_sha256', 'build_sha256', 'build_identity_sha256',
    'provider_build_sha256', 'source_inputs_sha256', 'generated_header_sha256', 'final_factory_sha256',
    'final_wasm_sha256', 'final_output_sha256',
))


def encoded(value):
    """The retained manifest/provider-build spelling, including final LF."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def canonical(value):
    """The bounded facts spelling: sorted compact ASCII JSON, no final LF."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError('duplicate JSON field: ' + name)
        result[name] = value
    return result


def document(raw):
    if len(raw) > MAX_DOCUMENT:
        raise ValueError('metadata input exceeds 32 MiB')
    def invalid(value):
        raise ValueError('invalid JSON constant: ' + value)
    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('nonfinite metadata JSON number')
        return number
    def unicode_values(value):
        if type(value) is str:
            value.encode('utf-8')
        elif type(value) is dict:
            for key, child in value.items():
                unicode_values(key)
                unicode_values(child)
        elif type(value) is list:
            for child in value:
                unicode_values(child)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=invalid, parse_float=finite)
        unicode_values(value)
        return value
    except (RecursionError, OverflowError) as error:
        raise ValueError('invalid or overdeep metadata JSON') from error


def lexical(path):
    raw = os.fspath(path)
    parsed = Path(raw)
    if not parsed.is_absolute() or str(parsed) != raw or '..' in parsed.parts:
        raise ValueError('all generator paths must be absolute and canonical')
    return parsed


def ordinary(path, directory):
    path = lexical(path)
    for item in reversed((path, *path.parents)):
        state = item.lstat()
        wanted = directory if item == path else True
        attributes = getattr(state, 'st_file_attributes', None)
        if os.name == 'nt' and type(attributes) is not int:
            raise ValueError('Windows reparse metadata unavailable: ' + str(item))
        if (stat.S_ISLNK(state.st_mode) or attributes is not None and attributes & 0x400
                or not (stat.S_ISDIR(state.st_mode) if wanted else stat.S_ISREG(state.st_mode))
                or not wanted and state.st_nlink != 1):
            raise ValueError('generator paths must be ordinary unlinked entries: ' + str(item))
    if path.resolve(strict=True) != path:
        raise ValueError('generator paths must be canonical')
    return path


def identity(state):
    return (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns,
            state.st_ctime_ns, stat.S_IMODE(state.st_mode), state.st_nlink)


def read_file(path):
    path = ordinary(path, False)
    before = path.stat()
    if before.st_size > MAX_DOCUMENT:
        raise ValueError('metadata input exceeds 32 MiB: ' + str(path))
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise ValueError('metadata input changed before reading: ' + str(path))
        raw = stream.read(MAX_DOCUMENT + 1)
        after = os.fstat(stream.fileno())
    if (len(raw) > MAX_DOCUMENT or identity(before) != identity(after)
            or identity(ordinary(path, False).stat()) != identity(before)):
        raise ValueError('metadata input changed while reading: ' + str(path))
    return raw


def within(path, root):
    try:
        return path.relative_to(root)
    except ValueError:
        raise ValueError('path is outside its declared root: ' + str(path)) from None


def retained(path, root, inputs, role=None):
    path = ordinary(path, False)
    name = within(path, root).as_posix()
    item = inputs.get(name)
    if type(item) is not dict or role is not None and item.get('role') != role:
        raise ValueError('required generator input is absent from recipe: ' + name)
    raw = read_file(path)
    if digest(raw) != item.get('sha256'):
        raise ValueError('retained generator input hash mismatch: ' + name)
    return raw


def output_path(path, build_root, source_root):
    path = lexical(path)
    within(path, build_root)
    if path == build_root or source_root == path or source_root in path.parents:
        raise ValueError('generated outputs must be outside retained sources')
    ordinary(path.parent, True)
    if path.exists() or path.is_symlink():
        ordinary(path, False)
    return path


def reject_circular(value):
    if type(value) is dict:
        if CIRCULAR_FIELDS.intersection(value):
            raise ValueError('prelink plan contains a circular generated identity')
        for child in value.values():
            reject_circular(child)
    elif type(value) is list:
        for child in value:
            reject_circular(child)


def nonzero_hashes(value):
    if type(value) is dict:
        for name, child in value.items():
            if 'sha256' in name and isinstance(child, str) and child == '0' * 64:
                raise ValueError('zero identity is forbidden: ' + name)
            nonzero_hashes(child)
    elif type(value) is list:
        for child in value:
            nonzero_hashes(child)


def load_manifest(source_root, inputs):
    """Load exact retained helper bytes, independent of cached import names."""
    helpers = {name: retained(source_root / name, source_root, inputs, role='helper')
               for name in HELPERS}
    previous = sys.modules.get('dependency_archive')
    try:
        dependency = types.ModuleType('dependency_archive')
        dependency.__file__ = str(source_root / HELPERS[0])
        sys.modules['dependency_archive'] = dependency
        exec(compile(helpers[HELPERS[0]], dependency.__file__, 'exec'), dependency.__dict__)
        module = types.ModuleType('_foundation_document_copied_retained_manifest')
        module.__file__ = str(source_root / HELPERS[1])
        exec(compile(helpers[HELPERS[1]], module.__file__, 'exec'), module.__dict__)
    finally:
        if previous is None:
            sys.modules.pop('dependency_archive', None)
        else:
            sys.modules['dependency_archive'] = previous
    return module


def output_snapshot(path):
    if not path.exists() and not path.is_symlink():
        return None
    raw = read_file(path)
    return (*identity(path.stat()), raw)


def retained_directory_identities(source_root, inventory):
    return {identity(ordinary(source_root / name, True).stat())[:2]
            for name in ('', *inventory['directories'])}


def check_output_isolation(path, build_root, source_directories):
    # Lexically disjoint output parents can still alias a retained subdirectory
    # through a bind mount. Check every parent inside the owned output root
    # against the complete, already verified retained directory inventory.
    parent = path.parent
    while True:
        if identity(ordinary(parent, True).stat())[:2] in source_directories:
            raise ValueError('metadata output must be physically disjoint from retained directories')
        if parent == build_root:
            return
        parent = parent.parent


def write_output(path, raw, before):
    # Never replace an entry. Existing exact output is idempotent; other bytes
    # require a fresh caller-owned output name. Atomic link publication cannot
    # overwrite an entry introduced between our snapshot and publication.
    if output_snapshot(path) != before:
        raise ValueError('generated output changed before save: ' + str(path))
    if before is not None:
        if before[-1] != raw:
            raise ValueError('existing metadata output differs; use a fresh output path: ' + str(path))
        return
    parent = ordinary(path.parent, True)
    parent_identity = identity(parent.stat())[:2]
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=parent)
    temporary = Path(temporary)
    temporary_identity = identity(temporary.stat())[:2]
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if (identity(ordinary(parent, True).stat())[:2] != parent_identity
                or output_snapshot(path) != before):
            raise ValueError('generated output changed during save: ' + str(path))
        if (identity(ordinary(temporary, False).stat())[:2] != temporary_identity
                or read_file(temporary) != raw):
            raise ValueError('temporary metadata output changed before publication')
        os.link(temporary, path)
    finally:
        if temporary.exists() or temporary.is_symlink():
            if identity(temporary.lstat())[:2] != temporary_identity:
                raise ValueError('temporary metadata output changed; preserving it: ' + str(temporary))
            temporary.unlink()


def load_document_contract(source_root=None, inputs=None):
    """Load pure contract bytes; generation supplies the verified input ledger.

    Planning callers may use the same helper in their ordinary checkout before
    the retained recipe is sealed. Generation always requires its helper role
    and exact retained hash, then rechecks the whole inventory before output.
    """
    root = (Path(__file__).absolute().parents[3] if source_root is None else source_root)
    path = root / CONTRACT_HELPER
    raw = (read_file(path) if inputs is None
           else retained(path, root, inputs, role='helper'))
    module = types.ModuleType('_foundation_document_metadata_contract')
    module.__file__ = str(path)
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    # These facts also bind the unchanged C metadata/template ABI. A changed
    # contract requires an explicit adapter revision, not inferred eligibility.
    expected = {
        'base_header_sha256': module.BASE_HEADER_SHA256,
        'document_header_sha256': module.EXTENSION_HEADER_SHA256,
        'contract_sha256': module.CONTRACT_SHA256,
        'document_catalog_sha256': module.DOCUMENT_CATALOG_SHA256,
        'semantic_snapshot_schema_sha256': module.DOCUMENT_SCHEMA_SHA256,
        'form_action_schema_sha256': module.DOCUMENT_SCHEMA_SHA256,
        'ack_schema_sha256': module.ACTION_ACK_SCHEMA_SHA256,
    }
    if expected != PINS or module.BINDING != BINDING:
        raise ValueError('retained document contract requires an explicit metadata adapter revision')
    return module


def load_editor_contract(source_root=None, inputs=None, *, document_contract=None):
    """Load only the isolated, retained editor helper and its exact document dependency."""
    root = Path(__file__).absolute().parents[3] if source_root is None else source_root
    dependency = (load_document_contract(root, inputs) if document_contract is None else document_contract)
    path = root / EDITOR_CONTRACT_HELPER
    raw = read_file(path) if inputs is None else retained(path, root, inputs, role='helper')
    if digest(raw) != EDITOR_CONTRACT_HELPER_SHA256:
        raise ValueError('retained editor contract requires an explicit metadata adapter revision')
    module = types.ModuleType('_foundation_editor_metadata_contract')
    module.__file__ = str(path)
    previous = sys.modules.get('appended_engine_document_contract')
    try:
        sys.modules['appended_engine_document_contract'] = dependency
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    finally:
        if previous is None:
            sys.modules.pop('appended_engine_document_contract', None)
        else:
            sys.modules['appended_engine_document_contract'] = previous
    expected = {
        'editor_header_sha256': module.EDITOR_HEADER_SHA256,
        'editor_contract_sha256': module.CONTRACT_SHA256,
        'editor_catalog_sha256': module.EDITOR_CATALOG_SHA256,
        'editor_schema_sha256': module.EDITOR_SCHEMA_SHA256,
    }
    if (expected != EDITOR_PINS or module.BASE_HEADER_SHA256 != PINS['base_header_sha256']
            or module.DOCUMENT_HEADER_SHA256 != PINS['document_header_sha256']
            or module.DOCUMENT_CONTRACT_SHA256 != PINS['contract_sha256']
            or module.DOCUMENT_CATALOG_SHA256 != PINS['document_catalog_sha256']
            or module.DOCUMENT_SCHEMA_SHA256 != PINS['semantic_snapshot_schema_sha256']
            or module.ACTION_ACK_SCHEMA_SHA256 != PINS['ack_schema_sha256']
            or module.PHYSICAL_CATALOG_SHA256 != dependency.PHYSICAL_CATALOG_SHA256
            or module.BINDING != 'copied-owner-bridge/direct-worker-editor-v1'
            or module.BUILD_KIND != 'foundation-neutral-engine-provider-editor-v1-build-v1'
            or dict(module.CAPABILITIES) != {'editor': '2035'}):
        raise ValueError('retained editor contract requires an explicit metadata adapter revision')
    return module


def fixed_plan(recipe, document_profile, *, contract=None, editor_contract=None):
    """Exact noncircular document prelink plan shared with the maintenance tool."""
    contract = load_document_contract() if contract is None else contract
    if type(document_profile) is str and document_profile == 'editor':
        editor = load_editor_contract(document_contract=contract) if editor_contract is None else editor_contract
        selected = editor.editor_selector(document_profile)
        return {
            'schema_version': 1, 'kind': 'foundation-copied-engine-document-prelink-plan-v1',
            'target': recipe['target'], 'toolchain': recipe['toolchain'], 'options': recipe['options'],
            'binding': editor.BINDING, 'configuration': editor.expected_configuration(editor_profile=selected),
            'capabilities': editor.CAPABILITIES[selected], 'bridge_abi': 65536,
            'profile': editor.PROFILE_NAMES[selected], 'abi_major': 1, 'abi_minor': 1,
            **PINS, 'contract_sha256': editor.CONTRACT_SHA256,
            'document_contract_sha256': PINS['contract_sha256'], **EDITOR_PINS,
            'physical_catalog_path': PHYSICAL_CATALOG,
            'physical_catalog_sha256': editor.PHYSICAL_CATALOG_SHA256,
            'surface_protocol_version': 2, 'surface_capabilities': '8255',
            'mouse_input_version': 1, 'key_mapping_version': 1, 'display_scale': 1,
            'editor_protocol_version': 1,
            'limits': dict(EDITOR_LIMITS), 'retention': dict(RETENTION),
            'provider_contract': editor.provider_contract(editor_profile=selected),
        }
    selected = contract.document_selector(document_profile)
    physical = ({**contract.PHYSICAL_FACTS, 'physical_catalog_path': PHYSICAL_CATALOG}
                if selected == 'physical' else {})
    return {
        'schema_version': 1, 'kind': 'foundation-copied-engine-document-prelink-plan-v1',
        'target': recipe['target'], 'toolchain': recipe['toolchain'], 'options': recipe['options'],
        'binding': BINDING,
        'configuration': contract.expected_configuration(document_profile=selected),
        'capabilities': contract.CAPABILITIES[selected], 'bridge_abi': 65536,
        'profile': contract.PROFILE_NAMES[selected], 'abi_major': 1, 'abi_minor': 1,
        **PINS, 'limits': dict(LIMITS), 'retention': dict(RETENTION),
        'provider_contract': contract.provider_contract(document_profile=selected), **physical,
    }


def generate(args):
    selected = args.document_profile
    if type(selected) is not str or selected not in ('pixel', 'physical', 'editor'):
        raise ValueError('document profile must be explicitly pixel, physical or editor')
    editor = selected == 'editor'
    editor_arguments = {name: getattr(args, name, None) for name in EDITOR_PIN_FILES}
    if editor and any(value is None for value in editor_arguments.values()):
        raise ValueError('editor profile requires --editor-header/contract/catalog/schema')
    if not editor and any(value is not None for value in editor_arguments.values()):
        raise ValueError('non-editor profile rejects editor interface arguments')
    physical_catalog = getattr(args, 'physical_catalog', None)
    if selected in ('physical', 'editor') and physical_catalog is None:
        raise ValueError('physical/editor profile requires --physical-catalog')
    if selected == 'pixel' and physical_catalog is not None:
        raise ValueError('pixel profile rejects --physical-catalog')
    source_root = ordinary(args.source_root, True)
    build_root = ordinary(args.build_root, True)
    if (source_root == build_root or source_root in build_root.parents
            or build_root in source_root.parents):
        raise ValueError('source and build roots must be disjoint')
    # Reject physical aliases of either root in the other's ancestry (including
    # root bind mounts). Caller exclusion still owns the private output tree.
    source_identity = identity(source_root.stat())[:2]
    build_identity = identity(build_root.stat())[:2]
    if (any(identity(item.stat())[:2] == source_identity for item in (build_root, *build_root.parents))
            or any(identity(item.stat())[:2] == build_identity for item in (source_root, *source_root.parents))):
        raise ValueError('source and build roots must be physically disjoint')
    recipe_path = ordinary(args.recipe, False)
    if recipe_path != source_root / 'recipe.json':
        raise ValueError('recipe must be the retained root recipe.json')
    raw_recipe = read_file(recipe_path)
    recipe = document(raw_recipe)
    inputs = recipe.get('inputs') if type(recipe) is dict else None
    if type(inputs) is not dict or not inputs:
        raise ValueError('recipe must retain complete producer inputs')
    generator_path = ordinary(str(Path(__file__).absolute()), False)
    template_path = generator_path.with_name('engine-document-copied-metadata.h.in')
    retained(generator_path, source_root, inputs)
    raw_template = retained(template_path, source_root, inputs)
    module = load_manifest(source_root, inputs)
    checked_recipe, recipe_id, inventory = module.verify_inputs(source_root)
    if encoded(checked_recipe) != encoded(recipe) or recipe_id != digest(raw_recipe):
        raise ValueError('recipe changed during complete source verification')
    nonzero_hashes(recipe)
    contract = load_document_contract(source_root, inputs)
    active = load_editor_contract(source_root, inputs, document_contract=contract) if editor else contract
    selector = {'editor_profile': selected} if editor else {'document_profile': selected}
    target, provider = recipe['target'], recipe['provider']
    if (target['system'], target['processor'], target['pointer_bits']) != ('Emscripten', 'wasm32', 32):
        raise ValueError('metadata is only for the browser-wasm32 document profile')
    if provider['binding'] != 'copied-owner-bridge':
        raise ValueError('metadata requires copied-owner provider binding')
    if type(provider['abi_major']) is not int or type(provider['abi_minor']) is not int or (
            provider['abi_major'], provider['abi_minor']) != (1, 1):
        raise ValueError('metadata requires exact document provider ABI 1.1')
    if (provider['header'] != PIN_FILES['contract_header'][0]
            or provider['header_sha256'] != PINS['base_header_sha256']):
        raise ValueError('provider base header differs from fixed document contract')
    retained_pins = {}
    for argument, (name, pin) in PIN_FILES.items():
        path = ordinary(getattr(args, argument), False)
        if path != source_root / name:
            raise ValueError('document pin path differs from canonical retained input: ' + argument)
        raw = retained(path, source_root, inputs, role='interface')
        if digest(raw) != PINS[pin]:
            raise ValueError('document pin file differs from approved profile: ' + name)
        retained_pins[path] = raw
    if selected in ('physical', 'editor'):
        path = ordinary(physical_catalog, False)
        if path != source_root / PHYSICAL_CATALOG:
            raise ValueError('physical catalog differs from canonical retained input')
        raw = retained(path, source_root, inputs, role='interface')
        if digest(raw) != contract.PHYSICAL_CATALOG_SHA256:
            raise ValueError('physical catalog differs from approved document profile')
        retained_pins[path] = raw
    if editor:
        for argument, (name, pin) in EDITOR_PIN_FILES.items():
            path = ordinary(editor_arguments[argument], False)
            if path != source_root / name:
                raise ValueError('editor pin path differs from canonical retained input: ' + argument)
            raw = retained(path, source_root, inputs, role='interface')
            if digest(raw) != EDITOR_PINS[pin]:
                raise ValueError('editor pin file differs from approved profile: ' + name)
            retained_pins[path] = raw
        references = {role: {'path': name, 'sha256': digest(retained_pins[source_root / name])}
                      for role, name in active.INTERFACE_PATHS.items()}
        interfaces = {name: retained_pins[source_root / name] for name in active.INTERFACE_PATHS.values()}
        active.validate_interface_bytes(references, interfaces, **selector)
    plan_path = ordinary(args.build_plan, False)
    raw_plan = retained(plan_path, source_root, inputs)
    plan = document(raw_plan)
    reject_circular(plan)
    if encoded(plan) != encoded(fixed_plan(recipe, selected, contract=contract,
                                        editor_contract=active if editor else None)):
        raise ValueError('prelink plan differs from exact document copied profile')
    # Output identities are noncircular. Source recipe/inputs and prelink-plan
    # bytes determine provider-build bytes; only the header hashes that output.
    build = {
        'schema_version': 1, 'kind': active.BUILD_KIND,
        'target': target, 'toolchain': recipe['toolchain'], 'options': recipe['options'],
        'source_recipe_sha256': recipe_id, 'source_inputs_sha256': digest(encoded(inputs)),
        'contract_header_sha256': active.CONTRACT_SHA256, 'binding': active.BINDING,
        'configuration': active.expected_configuration(**selector),
        'capabilities': active.CAPABILITIES[selected], 'bridge_abi': 65536,
        'provider_contract': active.provider_contract(**selector),
    }
    contract.require_fields(build, contract.BUILD_FIELDS, 'document provider build')
    active.validate_provider_contract(build['provider_contract'], **selector)
    raw_build = encoded(build)
    build_hash = digest(raw_build)
    profile = active.expected_engine_profile(**selector,
        build_sha256=build_hash, source_recipe_sha256=recipe_id)
    active.validate_engine_profile(profile, **selector)
    profile_json = canonical(profile)
    if len(profile_json.encode('ascii')) > MAX_FACTS:
        raise ValueError('document copied facts exceed 4095-byte host bound')
    hashes = {**PINS, 'contract_sha256': active.CONTRACT_SHA256,
              'build_identity_sha256': build_hash, 'source_recipe_sha256': recipe_id}
    replacements = {
        '@' + key.upper() + '_BYTES@': ', '.join('0x' + value[i:i + 2] for i in range(0, 64, 2))
        for key, value in hashes.items()
    }
    replacements['@COMPILED_PROFILE@'] = selected
    replacements['@CAPABILITIES@'] = active.CAPABILITIES[selected]
    replacements['@PROFILE_JSON@'] = json.dumps(profile_json, ensure_ascii=True)
    replacements['@PROFILE_CONTRACT_FIELDS@'] = ('38-field editor' if editor
                                                  else '24-field pixel or 30-field physical')
    replacements['@MAX_COMMAND_BYTES@'] = str(EDITOR_LIMITS['maximum_command_bytes'] if editor else LIMITS['maximum_command_bytes'])
    replacements['@MAX_QUERY_BYTES@'] = str(EDITOR_LIMITS['maximum_query_bytes'] if editor else LIMITS['maximum_query_bytes'])
    replacements['@EDITOR_PROFILE_CLAUSE@'] = ('\n            || (compiled_profile == bib::copied::DocumentCopiedProfile::editor && capabilities == UINT64_C(2035))'
                                               if editor else '')
    constants = ''
    if editor:
        constants = '// Explicit editor2035 / surface2 metadata; profile_json has exactly38 fields.\n'
        for name, value in {'document_contract_sha256': PINS['contract_sha256'],
                            'physical_catalog_sha256': active.PHYSICAL_CATALOG_SHA256, **EDITOR_PINS}.items():
            values = ', '.join('0x' + value[i:i + 2] for i in range(0, 64, 2))
            constants += 'inline constexpr std::array<std::uint8_t, 32> ' + name + ' = {{' + values + '}};\n'
        constants += ('inline constexpr std::uint32_t surface_protocol_version = 2u;\n'
                      'inline constexpr std::uint64_t surface_capabilities = UINT64_C(8255);\n'
                      'inline constexpr std::uint32_t editor_protocol_version = 1u;\n')
    replacements['@EDITOR_CONSTANTS@'] = constants
    header = raw_template.decode('utf-8')
    for key, value in replacements.items():
        if key not in header:
            raise ValueError('metadata template is missing placeholder: ' + key)
        header = header.replace(key, value)
    if re.search(r'@[A-Z_0-9]+@', header):
        raise ValueError('unresolved metadata template placeholder')
    raw_header = header.encode('utf-8')
    output_header = output_path(args.output_header, build_root, source_root)
    output_build = output_path(args.output_build, build_root, source_root)
    if output_header == output_build:
        raise ValueError('metadata output roles must be distinct')
    source_directories = retained_directory_identities(source_root, inventory)
    for path in (output_header, output_build):
        check_output_isolation(path, build_root, source_directories)
    before_header, before_build = output_snapshot(output_header), output_snapshot(output_build)
    for path, raw, before in ((output_header, raw_header, before_header),
                             (output_build, raw_build, before_build)):
        if before is not None and before[-1] != raw:
            raise ValueError('existing metadata output differs; use a fresh output path: ' + str(path))
    final_recipe, final_id, final_inventory = module.verify_inputs(source_root)
    if (encoded(final_recipe) != encoded(recipe) or final_id != recipe_id
            or encoded(final_inventory) != encoded(inventory)):
        raise ValueError('retained metadata inputs changed before output')
    if read_file(recipe_path) != raw_recipe or retained(plan_path, source_root, inputs) != raw_plan:
        raise ValueError('metadata inputs changed before output')
    if retained(template_path, source_root, inputs) != raw_template:
        raise ValueError('metadata template changed before output')
    for path, raw in retained_pins.items():
        if retained(path, source_root, inputs, role='interface') != raw:
            raise ValueError('document pin input changed before output')
    if retained_directory_identities(source_root, final_inventory) != source_directories:
        raise ValueError('retained directory identities changed before output')
    for path in (output_header, output_build):
        check_output_isolation(path, build_root, source_directories)
    write_output(output_build, raw_build, before_build)
    try:
        write_output(output_header, raw_header, before_header)
    except (OSError, ValueError) as error:
        # Separate paths cannot publish as a transaction. Keep the valid build
        # bytes for inspection and fail explicitly; never report a complete
        # generation or undo an entry after another writer may have read it.
        raise ValueError('provider-build output saved; header publication failed: ' + str(error)) from error
    return {
        'recipe_id': recipe_id, 'provider_build_sha256': build_hash,
        'contract_header_sha256': active.CONTRACT_SHA256,
        'generated_header_sha256': digest(raw_header), 'prelink_plan_sha256': digest(raw_plan),
        'scope': 'source-metadata-only-no-runtime-evidence',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-root', 'build-root', 'recipe', 'build-plan', 'contract-header',
                 'document-header', 'document-contract', 'document-catalog', 'document-schema',
                 'action-ack', 'output-header', 'output-build'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--document-profile', choices=('pixel', 'physical', 'editor'), required=True)
    parser.add_argument('--physical-catalog')
    for name in ('editor-header', 'editor-contract', 'editor-catalog', 'editor-schema'):
        parser.add_argument('--' + name)
    try:
        result = generate(parser.parse_args())
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, ImportError) as error:
        parser.exit(1, 'document copied metadata: ' + str(error) + '\n')
    sys.stdout.buffer.write(encoded(result))


if __name__ == '__main__':
    main()
