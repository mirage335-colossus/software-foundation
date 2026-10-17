#!/usr/bin/env python3
"""Strict retained-engine contracts. Verification establishes byte integrity only."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from dependency_archive import PathInventory, digest, encoded, object_pairs, relative

VERSION = 1
WINDOWS = os.name == 'nt'
MAX_MANIFEST = 32 * 1024 * 1024
SCOPE = 'retained-byte-integrity-only'
HELPERS = ('tools/appended_engine_manifest.py', 'tools/appended_engine_sdk.py',
           'tools/dependency_archive.py')
ROLES = frozenset(('source', 'patch', 'tool', 'bootstrap', 'data', 'license',
                   'helper', 'config', 'interface'))


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('invalid ' + label + ' fields')
    return value


def integer(value, label, minimum=0, maximum=2**32 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('invalid ' + label)
    return value


def text(value, label):
    if (not isinstance(value, str) or not value or len(value) > 4096
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError('invalid ' + label)
    return value


def sha256(value, label):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid SHA-256: ' + label)
    return value


def path_name(value):
    name = str(relative(value))
    for part in name.split('/'):
        if (any(c in '<>"|?*' or ord(c) >= 127 for c in part)
                or part.split('.')[0].rstrip(' ').upper() in {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                    *('COM' + str(i) for i in range(1, 10)),
                    *('LPT' + str(i) for i in range(1, 10))}):
            raise ValueError('nonportable retained path: ' + name)
    return name


def paths(value, label, nonempty=False):
    if (type(value) is not list or (nonempty and not value)
            or any(not isinstance(p, str) for p in value)
            or value != sorted(set(value))):
        raise ValueError('invalid sorted unique ' + label)
    for name in value:
        path_name(name)
    return value


def json_bytes(content):
    if len(content) > MAX_MANIFEST:
        raise ValueError('engine manifest exceeds size limit')
    def invalid(value):
        raise ValueError('invalid JSON constant: ' + value)
    return json.loads(content, object_pairs_hook=object_pairs, parse_constant=invalid)


def plain_state(state, directory=None):
    attributes = getattr(state, 'st_file_attributes', None)
    if attributes is not None and type(attributes) is not int:
        raise ValueError('invalid retained reparse metadata')
    if WINDOWS and type(attributes) is not int:
        raise ValueError('Windows reparse metadata is unavailable')
    if (stat.S_ISLNK(state.st_mode) or (attributes is not None and attributes & 0x400)
            or not (stat.S_ISDIR(state.st_mode) or stat.S_ISREG(state.st_mode))):
        raise ValueError('linked, reparse or special retained entry')
    if directory is not None and bool(stat.S_ISDIR(state.st_mode)) != directory:
        raise ValueError('retained path has the wrong file/directory type')
    if stat.S_ISREG(state.st_mode) and state.st_nlink != 1:
        raise ValueError('retained file must be singly linked')
    return state


def ordinary_root(root):
    if os.name not in ('posix', 'nt'):
        raise ValueError('retained engine integrity host is unsupported')
    root = Path(root).absolute()
    # Inspect each ancestor before resolution so junctions cannot disappear into
    # a seemingly ordinary resolved path. Missing Windows attributes fail closed.
    for parent in reversed((root, *root.parents)):
        plain_state(parent.lstat(), directory=True)
    if root.resolve(strict=True) != root:
        raise ValueError('retained root must be an ordinary unlinked directory')
    return root


def read_document(root, name):
    root = ordinary_root(root)
    path = root / path_name(name)
    ordinary_root(path.parent)
    plain_state(path.lstat(), directory=False)
    if path.resolve(strict=True) != path:
        raise ValueError('manifest must be an ordinary contained file')
    if path.stat().st_size > MAX_MANIFEST:
        raise ValueError('engine manifest exceeds size limit')
    content = path.read_bytes()
    return json_bytes(content), hashlib.sha256(content).hexdigest()


def target_contract(value):
    fields(value, ('system', 'processor', 'triple', 'pointer_bits'), 'engine target')
    text(value['system'], 'target system')
    text(value['processor'], 'target processor')
    pair = (value['system'], value['processor'])
    if pair not in {('Linux', 'x86_64'), ('Linux', 'aarch64'),
                   ('Windows', 'x86_64'), ('Emscripten', 'wasm32')}:
        raise ValueError('unsupported engine target tuple')
    text(value['triple'], 'target triple')
    integer(value['pointer_bits'], 'target pointer width')
    if value['pointer_bits'] != (32 if value['system'] == 'Emscripten' else 64):
        raise ValueError('engine target pointer width mismatch')
    return value


def toolchain_contract(value, target):
    fields(value, ('cxx_standard', 'identity_sha256', 'runtime_policy',
                   'paired_sdk_sha256', 'target_baseline'), 'engine toolchain')
    if integer(value['cxx_standard'], 'engine C++ standard') != 23:
        raise ValueError('engine internals require their isolated C++23 toolchain')
    sha256(value['identity_sha256'], 'engine toolchain')
    text(value['target_baseline'], 'target runtime baseline')
    browser = target['system'] == 'Emscripten'
    if value['runtime_policy'] != ('paired-emscripten' if browser else 'private-native'):
        raise ValueError('engine runtime policy mismatch')
    if browser:
        sha256(value['paired_sdk_sha256'], 'paired Emscripten SDK')
    elif value['paired_sdk_sha256'] is not None:
        raise ValueError('native engine does not claim an Emscripten pairing')
    return value


def options_contract(value, target):
    fields(value, ('script_enabled', 'rendering', 'thread_model'), 'engine options')
    if value['script_enabled'] is not True or value['rendering'] != 'cpu':
        raise ValueError('retained profile requires scripts and CPU rendering')
    if value['thread_model'] != ('single' if target['system'] == 'Emscripten' else 'native'):
        raise ValueError('engine thread profile mismatch')


def provider_contract(value, target, binary=False):
    names = ['format', 'binding', 'abi_major', 'abi_minor', 'header', 'header_sha256']
    if binary:
        names += ['entry', 'assets']
    fields(value, names, 'engine provider')
    browser = target['system'] == 'Emscripten'
    if value['format'] != ('browser-module' if browser else 'native-shared'):
        raise ValueError('engine provider format mismatch')
    bindings = ('linked-owner', 'copied-owner-bridge') if browser else ('c-abi',)
    if value['binding'] not in bindings:
        raise ValueError('engine owner binding mismatch')
    integer(value['abi_major'], 'provider ABI major', 1)
    integer(value['abi_minor'], 'provider ABI minor')
    path_name(value['header'])
    sha256(value['header_sha256'], 'provider header')
    if binary:
        entry = path_name(value['entry'])
        assets = paths(value['assets'], 'provider assets', True)
        if entry not in assets or value['header'] in assets:
            raise ValueError('provider entry/header asset roles conflict')
        if browser:
            if not entry.endswith(('.js', '.mjs')) or not any(p.endswith('.wasm') for p in assets):
                raise ValueError('browser engine requires explicit JS and Wasm assets')
        elif target['system'] == 'Windows':
            if not entry.endswith('.dll') or not any(p.endswith('.lib') for p in assets):
                raise ValueError('Windows engine requires DLL and import library assets')
        elif not re.search(r'\.so(?:\.[0-9]+)*$', entry):
            raise ValueError('Linux engine requires an explicit shared-library entry')


def inventory_contract(data, manifest):
    files = data['files']
    if type(files) is not dict or not files or manifest in files:
        raise ValueError('invalid complete engine file inventory')
    directories = paths(data['directories'], 'retained directories')
    modes = data['modes']
    if type(modes) is not dict or set(modes) != set(files) | set(directories):
        raise ValueError('engine modes must cover every retained file and directory')
    registry = PathInventory()
    registry.add(manifest, False)
    for name in directories:
        registry.add(path_name(name), True)
        if type(modes[name]) is not int or modes[name] != 0o755:
            raise ValueError('retained directory mode must be 0755')
    for name, value in files.items():
        registry.add(path_name(name), False)
        sha256(value, 'retained file ' + name)
        if type(modes[name]) is not int or modes[name] not in (0o644, 0o755):
            raise ValueError('retained file mode must be 0644 or 0755')
    needed = {str(Path(name).parent).replace('\\', '/') for name in files if '/' in name}
    needed |= {str(Path(name).parent).replace('\\', '/') for name in directories if '/' in name}
    if not needed <= set(directories):
        raise ValueError('retained directory inventory omits a parent')


def tree_inventory(root, manifest, *, logical_modes=None):
    root = ordinary_root(root)
    if WINDOWS and type(logical_modes) is not dict:
        raise ValueError('Windows retained tree requires explicit logical mode authority')
    files, directories, modes = {}, [], {}
    registry = PathInventory()
    def walk(directory):
        # Validate a directory before enumerating it and every child before
        # descending. rglob can visit a junction before its body can reject it.
        plain_state(directory.lstat(), directory=True)
        for path in sorted(directory.iterdir()):
            state = plain_state(path.lstat())
            yield path, state
            if stat.S_ISDIR(state.st_mode):
                yield from walk(path)
    for path, state in walk(root):
        name = path_name(path.relative_to(root).as_posix())
        directory = stat.S_ISDIR(state.st_mode)
        mode = (logical_modes.get(name, 0o755 if directory else None) if WINDOWS
                else stat.S_IMODE(state.st_mode))
        registry.add(name, directory)
        if name == manifest:
            if directory or (not WINDOWS and mode != 0o644):
                raise ValueError('root manifest must be an ordinary 0644 file')
            continue
        if type(mode) is not int or mode not in ((0o755,) if directory else (0o644, 0o755)):
            raise ValueError('retained entry mode is not normalized: ' + name)
        modes[name] = mode
        if directory:
            directories.append(name)
        else:
            files[name] = digest(path)
    if WINDOWS and not set(logical_modes) <= set(modes):
        raise ValueError('logical mode authority names a missing retained entry')
    directories.sort()
    return {'files': files, 'directories': directories, 'modes': modes}


def verify_tree(root, data, manifest):
    inventory_contract(data, manifest)
    actual = tree_inventory(root, manifest, logical_modes=data['modes'])
    if actual != {key: data[key] for key in actual}:
        raise ValueError('complete retained engine inventory or mode mismatch')


def recipe_contract(data):
    fields(data, ('schema_version', 'kind', 'producer_version', 'target', 'toolchain',
                  'options', 'provider', 'suppliers', 'inputs', 'patches', 'licenses'), 'engine recipe')
    if (integer(data['schema_version'], 'recipe schema') != VERSION
            or data['kind'] != 'foundation-appended-engine-recipe'
            or integer(data['producer_version'], 'producer version') != VERSION):
        raise ValueError('unsupported engine recipe/producer version')
    target = target_contract(data['target'])
    toolchain_contract(data['toolchain'], target)
    options_contract(data['options'], target)
    provider_contract(data['provider'], target)
    inputs = data['inputs']
    if type(inputs) is not dict or not inputs:
        raise ValueError('recipe requires complete retained producer inputs')
    registry = PathInventory()
    registry.add('recipe.json', False)
    registry.add('sources.json', False)
    for name, item in inputs.items():
        registry.add(path_name(name), False)
        fields(item, ('sha256', 'role', 'mode'), 'producer input')
        sha256(item['sha256'], 'producer input')
        if (not isinstance(item['role'], str) or item['role'] not in ROLES
                or type(item['mode']) is not int or item['mode'] not in (0o644, 0o755)):
            raise ValueError('invalid producer input role/mode')
    if any(name not in inputs or inputs[name]['role'] != 'helper' for name in HELPERS):
        raise ValueError('recipe must retain its exact producing helpers')
    provider = data['provider']
    if (provider['header'] not in inputs or inputs[provider['header']]['role'] != 'interface'
            or inputs[provider['header']]['sha256'] != provider['header_sha256']):
        raise ValueError('provider header differs from source input contract')
    licenses = paths(data['licenses'], 'retained source licenses', True)
    if licenses != sorted(name for name, item in inputs.items() if item['role'] == 'license'):
        raise ValueError('licenses must name every retained license input exactly')
    fields(data['suppliers'], ('wrapper', 'engine'), 'engine suppliers')
    for supplier in data['suppliers'].values():
        fields(supplier, ('repository', 'commit', 'archive'), 'engine supplier')
        if not text(supplier['repository'], 'supplier repository').startswith('https://'):
            raise ValueError('supplier repository must use HTTPS')
        if not isinstance(supplier['commit'], str) or not re.fullmatch('[0-9a-f]{40}', supplier['commit']):
            raise ValueError('supplier requires a complete commit identity')
        if (not isinstance(supplier['archive'], str) or supplier['archive'] not in inputs
                or inputs[supplier['archive']]['role'] != 'source'):
            raise ValueError('supplier archive omitted from retained source inputs')
    if type(data['patches']) is not list:
        raise ValueError('ordered patches must be a list')
    seen = set()
    for patch in data['patches']:
        fields(patch, ('path', 'tree', 'preimages', 'postimages'), 'ordered engine patch')
        name = patch['path']
        if (not isinstance(name, str) or name in seen or name not in inputs or inputs[name]['role'] != 'patch'
                or patch['tree'] not in ('wrapper', 'engine')):
            raise ValueError('invalid duplicate/missing engine patch')
        seen.add(name)
        before, after = patch['preimages'], patch['postimages']
        if type(before) is not dict or not before or type(after) is not dict or set(before) != set(after):
            raise ValueError('patch must bind exact preimages and postimages')
        for source_name in before:
            path_name(source_name)
            if before[source_name] is None and after[source_name] is None:
                raise ValueError('patch cannot have absent preimage and postimage')
            for value in (before[source_name], after[source_name]):
                if value is not None:
                    sha256(value, 'patch image')
    if seen != {name for name, item in inputs.items() if item['role'] == 'patch'}:
        raise ValueError('recipe has an unordered retained patch')
    return data


def recipe_identity(root):
    data, recipe_hash = read_document(root, 'recipe.json')
    recipe_contract(data)
    # Exact recipe bytes bind every expected input hash, role and mode.
    return recipe_hash


def verify_inputs(root):
    root = ordinary_root(root)
    data, recipe_hash = read_document(root, 'recipe.json')
    recipe_contract(data)
    input_modes = {name: value['mode'] for name, value in data['inputs'].items()}
    input_modes['recipe.json'] = 0o644
    actual = tree_inventory(root, 'sources.json', logical_modes=input_modes)
    expected = {name: value['sha256'] for name, value in data['inputs'].items()}
    expected['recipe.json'] = recipe_hash
    if actual['files'] != expected:
        raise ValueError('retained producer inputs differ from exact recipe')
    for name, item in data['inputs'].items():
        if actual['modes'].get(name) != item['mode']:
            raise ValueError('retained producer input mode mismatch')
    if actual['modes'].get('recipe.json') != 0o644:
        raise ValueError('recipe must use mode 0644')
    return data, recipe_hash, actual


def source_contract(data, recipe, recipe_hash):
    fields(data, ('schema_version', 'kind', 'producer_version', 'recipe_id',
                  'files', 'directories', 'modes'), 'engine source manifest')
    if (integer(data['schema_version'], 'source schema') != VERSION
            or data['kind'] != 'foundation-appended-engine-sources'
            or integer(data['producer_version'], 'source producer') != VERSION):
        raise ValueError('unsupported engine source manifest')
    recipe_contract(recipe)
    if sha256(data['recipe_id'], 'source recipe') != recipe_hash:
        raise ValueError('engine source recipe identity mismatch')
    inventory_contract(data, 'sources.json')
    expected = {name: item['sha256'] for name, item in recipe['inputs'].items()}
    expected['recipe.json'] = recipe_hash
    if data['files'] != expected or data['modes'].get('recipe.json') != 0o644:
        raise ValueError('source manifest differs from exact recipe inputs')
    if any(data['modes'].get(name) != item['mode'] for name, item in recipe['inputs'].items()):
        raise ValueError('source manifest producer input mode mismatch')
    return data


def verify_sources(root):
    data, source_hash = read_document(root, 'sources.json')
    recipe, identity, _ = verify_inputs(root)
    source_contract(data, recipe, identity)
    verify_tree(root, data, 'sources.json')
    return data, source_hash, recipe


def binary_contract(data):
    fields(data, ('schema_version', 'kind', 'producer_version', 'recipe_id',
                  'sources_sha256', 'target', 'toolchain', 'options', 'provider',
                  'licenses', 'build', 'files', 'directories', 'modes'), 'engine binary manifest')
    if (integer(data['schema_version'], 'binary schema') != VERSION
            or data['kind'] != 'foundation-appended-engine'
            or integer(data['producer_version'], 'binary producer') != VERSION):
        raise ValueError('unsupported engine binary manifest')
    sha256(data['recipe_id'], 'binary recipe')
    sha256(data['sources_sha256'], 'complete source manifest')
    target = target_contract(data['target'])
    toolchain_contract(data['toolchain'], target)
    options_contract(data['options'], target)
    provider_contract(data['provider'], target, binary=True)
    inventory_contract(data, 'engine-sdk.json')
    provider, files = data['provider'], data['files']
    if files.get(provider['header']) != provider['header_sha256']:
        raise ValueError('binary provider header differs from inventory')
    licenses = paths(data['licenses'], 'binary notices', True)
    fields(data['build'], ('origin', 'link_receipt'), 'engine build provenance')
    text(data['build']['origin'], 'build origin')
    receipt = path_name(data['build']['link_receipt'])
    required = set(provider['assets']) | {provider['header'], receipt} | set(licenses)
    if (not required <= set(files) or set(provider['assets']) & (set(licenses) | {receipt})
            or provider['header'] in licenses or receipt in licenses or receipt == provider['header']):
        raise ValueError('missing/conflicting engine asset, header, notice or receipt role')
    return data


def verify_engine(root, *, expected_recipe=None, expected_manifest=None, target=None, toolchain=None):
    data, manifest_hash = read_document(root, 'engine-sdk.json')
    binary_contract(data)
    verify_tree(root, data, 'engine-sdk.json')
    for wanted, actual, label in ((expected_recipe, data['recipe_id'], 'recipe'),
            (expected_manifest, manifest_hash, 'manifest'),
            (toolchain, data['toolchain']['identity_sha256'], 'toolchain')):
        if wanted is not None and sha256(wanted, label) != actual:
            raise ValueError('retained engine ' + label + ' pin mismatch')
    if target is not None and target_contract(target) != data['target']:
        raise ValueError('retained engine target pin mismatch')
    return data, manifest_hash


def verify_binding(binary, sources, source_hash, recipe):
    if binary['recipe_id'] != sources['recipe_id'] or binary['sources_sha256'] != source_hash:
        raise ValueError('engine binary/source group identity mismatch')
    for name in ('target', 'toolchain', 'options', 'licenses'):
        if binary[name] != recipe[name]:
            raise ValueError('engine binary differs from retained recipe: ' + name)
    if {key: binary['provider'][key] for key in recipe['provider']} != recipe['provider']:
        raise ValueError('engine provider differs from retained source contract')
    for name in recipe['licenses']:
        if binary['files'][name] != sources['files'][name]:
            raise ValueError('binary notice differs from retained source notice')


def integrity_result(**values):
    return {'scope': SCOPE, **values}
