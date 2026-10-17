#!/usr/bin/env python3
"""Generate source-only document copied-provider metadata, without build tools.

The retained root's exact recipe and complete inputs bind this generator, its
template and its prelink plan. provider-build.json never hashes itself: only
the generated header carries that output's actual byte hash. Source and output
roots must already exist, be ordinary directories and be disjoint. Invocation
does not establish an actual engine producer, SDK, link or runtime result.

The unchanged retained recipe schema keeps its six provider fields, with ABI
1.1 and the base header's *file* hash. Document pins live in the retained prelink
plan, not extra recipe fields. A retained helper rejecting this exact profile
is a prerequisite failure; this generator never patches or widens that helper.
Select --profile explicitly: pixel and physical are distinct retained profiles,
never inferred from capabilities. Only physical requires --physical-catalog.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import types

sys.dont_write_bytecode = True
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_FACTS = 4096
BINDING = 'copied-owner-bridge/direct-worker-document-v2'
PROFILE = 'foundation-engine-copied1795-ndv2-v1'
PROFILES = {
    'pixel': {'profile': PROFILE, 'capabilities': '1795'},
    'physical': {'profile': 'foundation-engine-copied2003-ndv2-v1', 'capabilities': '2003'},
}
PHYSICAL_CATALOG_SHA256 = 'd244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b'
PHYSICAL_FACTS = {
    'command_catalog_sha256': PHYSICAL_CATALOG_SHA256,
    'surface_protocol_version': 1, 'surface_capabilities': '8225',
    'mouse_input_version': 1, 'key_mapping_version': 1, 'display_scale': 1,
}
CONFIGURATION = {
    'profile': 'browser-wasm32-cpu-direct-owner-v1', 'modularized': True,
    'esm': True, 'auto_main': False, 'pthread': False, 'shared_memory': False,
    'fixed_viewport_width': 800, 'fixed_viewport_height': 600,
}
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
HELPERS = ('tools/dependency_archive.py', 'tools/appended_engine_manifest.py',
           'tools/appended_engine_sdk.py')
CIRCULAR_FIELDS = frozenset((
    'recipe_id', 'source_recipe_sha256', 'build_sha256', 'build_identity_sha256',
    'provider_build_sha256', 'source_inputs_sha256', 'generated_header_sha256', 'final_factory_sha256',
    'final_wasm_sha256', 'final_output_sha256',
))


def encoded(value):
    """The retained manifest/provider-build spelling, including final LF."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode('ascii')


def canonical(value):
    """The bounded facts spelling: sorted compact ASCII JSON, no final LF."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


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
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


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
        os.link(temporary, path)
    finally:
        if temporary.exists() or temporary.is_symlink():
            if identity(temporary.lstat())[:2] != temporary_identity:
                raise ValueError('temporary metadata output changed; preserving it: ' + str(temporary))
            temporary.unlink()


def selected_profile(profile):
    if type(profile) is not str or profile not in PROFILES:
        raise ValueError('explicit document profile must be pixel or physical')
    return PROFILES[profile]


def physical_plan_fields(profile, physical_catalog_path):
    selected_profile(profile)
    if profile == 'pixel':
        if physical_catalog_path is not None:
            raise ValueError('pixel profile rejects physical catalog path')
        return {}
    if (type(physical_catalog_path) is not str or not physical_catalog_path
            or '\\' in physical_catalog_path or ':' in physical_catalog_path
            or physical_catalog_path.startswith('/')
            or any(part in ('', '.', '..') for part in physical_catalog_path.split('/'))):
        raise ValueError('physical profile requires retained source-relative catalog path')
    return {**PHYSICAL_FACTS, 'physical_catalog_path': physical_catalog_path}


def fixed_plan(recipe, profile, physical_catalog_path=None):
    selected = selected_profile(profile)
    return {
        'schema_version': 1, 'kind': 'foundation-copied-engine-document-prelink-plan-v1',
        'target': recipe['target'], 'toolchain': recipe['toolchain'], 'options': recipe['options'],
        'binding': BINDING, 'configuration': CONFIGURATION, 'capabilities': selected['capabilities'],
        'bridge_abi': 65536, 'profile': selected['profile'], 'abi_major': 1, 'abi_minor': 1,
        **PINS, 'limits': LIMITS, 'retention': RETENTION,
        **physical_plan_fields(profile, physical_catalog_path),
    }


def profile_facts(profile, build_hash, recipe_id):
    selected = selected_profile(profile)
    return {
        'schema_version': 1, 'kind': 'foundation-copied-engine-document-v2',
        'target': 'browser-wasm32', 'binding': BINDING, 'pointer_bits': 32,
        'pthread': False, 'shared_memory': False, 'bridge_abi': 65536,
        'capabilities': selected['capabilities'], 'build_sha256': build_hash, 'source_recipe_sha256': recipe_id,
        'document_profile': selected['profile'], 'provider_abi_major': 1, 'provider_abi_minor': 1,
        'host_abi_major': 1, 'host_abi_minor': 0, 'viewport_width': 800, 'viewport_height': 600,
        'contract_sha256': PINS['contract_sha256'],
        'base_header_sha256': PINS['base_header_sha256'],
        'extension_header_sha256': PINS['document_header_sha256'],
        'document_catalog_sha256': PINS['document_catalog_sha256'],
        'document_schema_sha256': PINS['semantic_snapshot_schema_sha256'],
        'action_ack_schema_sha256': PINS['ack_schema_sha256'],
        **(PHYSICAL_FACTS if profile == 'physical' else {}),
    }


def generate(args):
    selected = selected_profile(args.profile)
    if args.profile == 'physical' and args.physical_catalog is None:
        raise ValueError('physical profile requires --physical-catalog')
    if args.profile == 'pixel' and args.physical_catalog is not None:
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
    physical_catalog_path = None
    if args.profile == 'physical':
        # The exact CLI path must designate bytes in the retained input closure;
        # another profile or a caller-supplied claimed digest cannot substitute.
        path = ordinary(args.physical_catalog, False)
        raw = retained(path, source_root, inputs, role='interface')
        if digest(raw) != PHYSICAL_CATALOG_SHA256:
            raise ValueError('physical catalog differs from approved profile')
        retained_pins[path] = raw
        physical_catalog_path = within(path, source_root).as_posix()
    plan_path = ordinary(args.build_plan, False)
    raw_plan = retained(plan_path, source_root, inputs)
    plan = document(raw_plan)
    reject_circular(plan)
    if encoded(plan) != encoded(fixed_plan(recipe, args.profile, physical_catalog_path)):
        raise ValueError('prelink plan differs from exact document copied profile')
    # Output identities are noncircular. Source recipe/inputs and prelink-plan
    # bytes determine provider-build bytes; only the header hashes that output.
    build = {
        'schema_version': 1, 'kind': 'foundation-neutral-engine-provider-build-v1',
        'target': target, 'toolchain': recipe['toolchain'], 'options': recipe['options'],
        'source_recipe_sha256': recipe_id, 'source_inputs_sha256': digest(encoded(inputs)),
        'contract_header_sha256': PINS['contract_sha256'], 'binding': BINDING,
        'configuration': CONFIGURATION, 'capabilities': selected['capabilities'], 'bridge_abi': 65536,
        'profile': selected['profile'], 'abi_major': 1, 'abi_minor': 1,
        **{key: value for key, value in PINS.items() if key != 'contract_sha256'},
        'limits': LIMITS, 'retention': RETENTION,
        **physical_plan_fields(args.profile, physical_catalog_path),
    }
    raw_build = encoded(build)
    build_hash = digest(raw_build)
    profile = profile_facts(args.profile, build_hash, recipe_id)
    profile_json = canonical(profile)
    if len(profile_json.encode('ascii')) > MAX_FACTS:
        raise ValueError('document copied facts exceed 4096-byte bound')
    hashes = {**PINS, 'build_identity_sha256': build_hash, 'source_recipe_sha256': recipe_id}
    replacements = {
        '@' + key.upper() + '_BYTES@': ', '.join('0x' + value[i:i + 2] for i in range(0, 64, 2))
        for key, value in hashes.items()
    }
    replacements['@PROFILE_JSON@'] = json.dumps(profile_json, ensure_ascii=True)
    replacements['@COMPILED_PROFILE@'] = args.profile
    replacements['@CAPABILITIES@'] = selected['capabilities']
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
        'contract_header_sha256': PINS['contract_sha256'],
        'generated_header_sha256': digest(raw_header), 'prelink_plan_sha256': digest(raw_plan),
        'scope': 'source-metadata-only-no-runtime-evidence',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, choices=tuple(PROFILES))
    parser.add_argument('--physical-catalog')
    for name in ('source-root', 'build-root', 'recipe', 'build-plan', 'contract-header',
                 'document-header', 'document-contract', 'document-catalog', 'document-schema',
                 'action-ack', 'output-header', 'output-build'):
        parser.add_argument('--' + name, required=True)
    try:
        result = generate(parser.parse_args())
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, ImportError) as error:
        parser.exit(1, 'document copied metadata: ' + str(error) + '\n')
    sys.stdout.buffer.write(encoded(result))


if __name__ == '__main__':
    main()
