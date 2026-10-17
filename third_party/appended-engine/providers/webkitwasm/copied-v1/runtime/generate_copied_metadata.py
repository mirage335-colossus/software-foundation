#!/usr/bin/env python3
"""Generate copied-provider build identities without invoking any build tool.

The retained recipe binds this script, its adjacent template, the complete
prelink plan and all semantic inputs. Exact recipe bytes determine recipe_id.
The provider-build output has the consumer's exact field set and contains no
hash of itself; only the generated header embeds its output-byte hash. Both
outputs must live in an existing, disjoint, owned build root. The later link
receipt must inventory their exact bytes and this invocation separately.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

sys.dont_write_bytecode = True
MAX_DOCUMENT = 32 * 1024 * 1024
BINDING = 'copied-owner-bridge/direct-worker-v1'
CONFIGURATION = {
    'profile': 'browser-wasm32-cpu-direct-owner-v1', 'modularized': True,
    'esm': True, 'auto_main': False, 'pthread': False, 'shared_memory': False,
    'fixed_viewport_width': 800, 'fixed_viewport_height': 600,
}
CIRCULAR_FIELDS = frozenset((
    'recipe_id', 'source_recipe_sha256', 'build_sha256',
    'build_identity_sha256', 'provider_build_sha256', 'generated_header_sha256',
    'final_factory_sha256', 'final_wasm_sha256', 'final_output_sha256',
))


def encoded(value):
    # Exactly tools/dependency_archive.py:encoded, also used by the consumer.
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode()


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


def ordinary(path, directory):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('all generator paths must be absolute')
    # Do not normalize links or parent traversals into apparently safe paths.
    if '..' in path.parts or '.' in path.parts:
        raise ValueError('generator paths must be canonical')
    for item in reversed((path, *path.parents)):
        state = item.lstat()
        wanted = directory if item == path else True
        if (stat.S_ISLNK(state.st_mode)
                or (stat.S_ISDIR(state.st_mode) if wanted else stat.S_ISREG(state.st_mode)) is False
                or getattr(state, 'st_file_attributes', 0) & 0x400
                or not wanted and state.st_nlink != 1):
            raise ValueError('generator paths must be ordinary unlinked entries: ' + str(item))
    if path.resolve(strict=True) != path:
        raise ValueError('generator paths must be canonical')
    return path


def read_file(path):
    path = ordinary(path, False)
    state = path.stat()
    if state.st_size > MAX_DOCUMENT:
        raise ValueError('metadata input exceeds 32 MiB: ' + str(path))
    raw = path.read_bytes()
    after = path.stat()
    if (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('metadata input changed while reading: ' + str(path))
    return raw


def within(path, root):
    try:
        return path.relative_to(root)
    except ValueError:
        raise ValueError('path is outside its declared root: ' + str(path)) from None


def retained(path, root, inputs, raw=None, role=None):
    path = ordinary(path, False)
    name = within(path, root).as_posix()
    item = inputs.get(name)
    if not isinstance(item, dict) or role is not None and item.get('role') != role:
        raise ValueError('required generator input is absent from recipe: ' + name)
    raw = path.read_bytes() if raw is None else raw
    if digest(raw) != item.get('sha256'):
        raise ValueError('retained generator input hash mismatch: ' + name)
    return raw


def output_path(path, build_root, source_root):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('output path must be absolute and canonical')
    within(path, build_root)
    if path == build_root or source_root == path or source_root in path.parents:
        raise ValueError('generated outputs must be outside retained sources')
    ordinary(path.parent, True)
    if path.exists() or path.is_symlink():
        ordinary(path, False)
    return path


def reject_circular(value):
    if isinstance(value, dict):
        if CIRCULAR_FIELDS.intersection(value):
            raise ValueError('prelink plan contains a circular generated identity')
        for child in value.values():
            reject_circular(child)
    elif isinstance(value, list):
        for child in value:
            reject_circular(child)


def output_snapshot(path):
    if not path.exists() and not path.is_symlink():
        return None
    raw = read_file(path)
    state = path.stat()
    return (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, raw)


def write_output(path, raw, before):
    # The caller explicitly designates this owned build root. Recheck the exact
    # old entry and bytes before atomically replacing a named generated output;
    # a changed or newly introduced foreign entry fails closed. All temporary
    # files stay in that same owned directory, outside retained sources.
    if output_snapshot(path) != before:
        raise ValueError('generated output changed before save: ' + str(path))
    if before is not None and before[-1] == raw:
        return
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    temporary = Path(temporary)
    temporary_state = temporary.stat()
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if output_snapshot(path) != before:
            raise ValueError('generated output changed during save: ' + str(path))
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            state = temporary.lstat()
            if (state.st_dev, state.st_ino) != (temporary_state.st_dev, temporary_state.st_ino):
                raise ValueError('temporary metadata output changed; preserving it: ' + str(temporary))
            temporary.unlink()


def generate(args):
    source_root = ordinary(args.source_root, True)
    build_root = ordinary(args.build_root, True)
    if (source_root == build_root or source_root in build_root.parents
            or build_root in source_root.parents):
        raise ValueError('source and build roots must be disjoint')
    recipe_path = ordinary(args.recipe, False)
    if recipe_path != source_root / 'recipe.json':
        raise ValueError('recipe must be the retained root recipe.json')
    raw_recipe = read_file(recipe_path)
    recipe = document(raw_recipe)
    inputs = recipe.get('inputs') if isinstance(recipe, dict) else None
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError('recipe must retain complete producer inputs')
    # Verify producing helpers before importing any retained Python. No bytecode
    # cache is permitted in the immutable source tree.
    for name in ('tools/appended_engine_manifest.py', 'tools/dependency_archive.py',
                 'tools/appended_engine_sdk.py'):
        retained(source_root / name, source_root, inputs, role='helper')
    generator_path = ordinary(Path(__file__).absolute(), False)
    template_path = generator_path.with_name('engine-copied-metadata.h.in')
    retained(generator_path, source_root, inputs)
    raw_template = retained(template_path, source_root, inputs)
    sys.path.insert(0, str(source_root / 'tools'))
    try:
        spec = importlib.util.spec_from_file_location(
            '_foundation_copied_retained_manifest', source_root / 'tools/appended_engine_manifest.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        checked_recipe, recipe_id, input_inventory = module.verify_inputs(source_root)
    finally:
        sys.path.pop(0)
    if encoded(recipe) != encoded(checked_recipe) or recipe_id != digest(raw_recipe):
        raise ValueError('recipe changed during complete source verification')
    # Nonzero identities are mandatory, including the toolchain/paired SDK.
    def nonzero_hashes(value):
        if isinstance(value, dict):
            for name, child in value.items():
                if ('sha256' in name and isinstance(child, str)
                        and re.fullmatch('0{64}', child)):
                    raise ValueError('zero identity is forbidden: ' + name)
                nonzero_hashes(child)
        elif isinstance(value, list):
            for child in value:
                nonzero_hashes(child)
    nonzero_hashes(recipe)
    if recipe['target']['system'] != 'Emscripten' or recipe['target']['processor'] != 'wasm32':
        raise ValueError('metadata is only for the browser-wasm32 copied profile')
    if recipe['provider']['binding'] != 'copied-owner-bridge':
        raise ValueError('metadata requires copied-owner provider binding')
    if recipe['provider']['abi_major'] != 1 or recipe['provider']['abi_minor'] != 0:
        raise ValueError('metadata requires exact copied provider ABI 1.0')
    contract_path = ordinary(args.contract_header, False)
    if contract_path != source_root / recipe['provider']['header']:
        raise ValueError('contract header differs from retained provider interface')
    contract_hash = digest(retained(contract_path, source_root, inputs, role='interface'))
    if contract_hash != recipe['provider']['header_sha256']:
        raise ValueError('contract header identity differs from recipe')
    plan_path = ordinary(args.build_plan, False)
    raw_plan = retained(plan_path, source_root, inputs)
    plan = document(raw_plan)
    if (not isinstance(plan, dict) or type(plan.get('schema_version')) is not int
            or plan['schema_version'] != 1
            or plan.get('kind') != 'foundation-copied-engine-prelink-plan-v1'):
        raise ValueError('invalid retained copied-engine prelink plan')
    reject_circular(plan)
    for name in ('target', 'toolchain', 'options'):
        if name not in plan or encoded(plan[name]) != encoded(recipe[name]):
            raise ValueError('prelink plan differs from recipe ' + name)
    for name, expected in (('binding', BINDING), ('configuration', CONFIGURATION),
                           ('capabilities', '259'), ('bridge_abi', 65536)):
        if name in plan and encoded(plan[name]) != encoded(expected):
            raise ValueError('prelink plan differs from fixed copied profile ' + name)
    build = {
        'schema_version': 1, 'kind': 'foundation-neutral-engine-provider-build-v1',
        'target': recipe['target'], 'toolchain': recipe['toolchain'], 'options': recipe['options'],
        'source_recipe_sha256': recipe_id, 'source_inputs_sha256': digest(encoded(inputs)),
        'contract_header_sha256': contract_hash, 'binding': BINDING,
        'configuration': CONFIGURATION, 'capabilities': '259', 'bridge_abi': 65536,
    }
    raw_build = encoded(build)
    build_hash = digest(raw_build)
    profile = {
        'schema_version': 1, 'kind': 'foundation-copied-engine-v1',
        'target': 'browser-wasm32', 'binding': BINDING, 'pointer_bits': 32,
        'pthread': False, 'shared_memory': False, 'bridge_abi': 65536,
        'capabilities': '259', 'contract_sha256': contract_hash,
        'build_sha256': build_hash, 'source_recipe_sha256': recipe_id,
    }
    # The wire profile is compact deterministic JSON, <=1024 UTF-8 bytes.
    profile_json = json.dumps(profile, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    if len(profile_json.encode()) > 1024:
        raise ValueError('copied profile exceeds DESCRIBE bound')
    replacements = {
        '@CONTRACT_BYTES@': ', '.join('0x' + contract_hash[i:i + 2] for i in range(0, 64, 2)),
        '@BUILD_BYTES@': ', '.join('0x' + build_hash[i:i + 2] for i in range(0, 64, 2)),
        '@RECIPE_BYTES@': ', '.join('0x' + recipe_id[i:i + 2] for i in range(0, 64, 2)),
        '@PROFILE_JSON@': json.dumps(profile_json, ensure_ascii=True),
    }
    header = raw_template.decode('utf-8')
    for key, value in replacements.items():
        if key not in header:
            raise ValueError('metadata template is missing placeholder: ' + key)
        header = header.replace(key, value)
    if re.search(r'@[A-Z_]+@', header):
        raise ValueError('unresolved metadata template placeholder')
    raw_header = header.encode('utf-8')
    output_header = output_path(args.output_header, build_root, source_root)
    output_build = output_path(args.output_build, build_root, source_root)
    if output_header == output_build:
        raise ValueError('metadata output roles must be distinct')
    # Finish complete validation before writing either result. Reverify all
    # retained bytes after the calculations, rather than trusting old digests.
    before_header, before_build = output_snapshot(output_header), output_snapshot(output_build)
    final_recipe, final_id, final_inventory = module.verify_inputs(source_root)
    if (encoded(final_recipe) != encoded(recipe) or final_id != recipe_id
            or encoded(final_inventory) != encoded(input_inventory)):
        raise ValueError('retained metadata inputs changed before output')
    if read_file(recipe_path) != raw_recipe or retained(plan_path, source_root, inputs) != raw_plan:
        raise ValueError('metadata inputs changed before output')
    write_output(output_build, raw_build, before_build)
    write_output(output_header, raw_header, before_header)
    return {'recipe_id': recipe_id, 'provider_build_sha256': build_hash,
            'contract_header_sha256': contract_hash, 'generated_header_sha256': digest(raw_header),
            'prelink_plan_sha256': digest(raw_plan), 'scope': 'source-metadata-only-no-runtime-evidence'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-root', 'build-root', 'recipe', 'build-plan', 'contract-header',
                 'output-header', 'output-build'):
        parser.add_argument('--' + name, required=True, type=Path)
    try:
        result = generate(parser.parse_args())
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as error:
        parser.exit(1, 'copied metadata: ' + str(error) + '\n')
    sys.stdout.buffer.write(encoded(result))


if __name__ == '__main__':
    main()
