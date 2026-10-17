#!/usr/bin/env python3
"""Explicit document-v2 incremental producer; never a cold build or eligible group.

The pinned reuse proof is an input contract, not original runtime evidence.
Its strict JSON fields and reference vocabulary are implemented below. CMake
owns all compile/archive/link edges. No engine-sdk or payload route calls this.
"""
import argparse
import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import stat
import sys
import time

import appended_engine_manifest as manifest
import appended_engine_sdk as engine_sdk
import appended_engine_document_contract as document_contract
from dependency_archive import digest, encoded, object_pairs
import process_tree
from sdk_environment import require_clean
from sdk_manifest import verify_sdk

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATHS = {name: 'recipes/webkitwasm-document-v2/maintenance-profile-' + name + '.json'
                 for name in ('pixel', 'physical', 'editor')}
GRAPH_PATH = 'cmake/AppendedEngineMaintenance/CMakeLists.txt'
SELF_PATH = 'tools/appended_engine_document_maintenance.py'
COMMON_HELPERS = (SELF_PATH, GRAPH_PATH, 'tools/appended_engine_document_contract.py',
    'recipes/webkitwasm-document-v2/prepare_reuse.py',
    'recipes/webkitwasm-document-v2/runtime/generate_document_metadata.py',
    'recipes/webkitwasm-document-v2/runtime/engine-document-copied-metadata.h.in',
    'tools/appended_engine_manifest.py', 'tools/appended_engine_sdk.py',
    'tools/dependency_archive.py', 'tools/process_tree.py', 'tools/sdk_environment.py',
    'tools/sdk_manifest.py', 'tools/appended_engine_consumer.py', 'tools/browser_bundle.py')
PLAN_KIND = 'foundation-document-v2-maintenance-plan-v1'
BUILD_KIND = 'foundation-document-v2-maintenance-build-v1'
REUSE_KIND = 'foundation-document-v2-baseline-reuse-v1'
SELECTED_CONTEXT_KIND = 'foundation-engine-selected-and-opaque-compile-contexts-v1'
OPAQUE_BASELINE_KIND = 'foundation-engine-trusted-opaque-baseline-v1'
OPAQUE_BASELINE_PROOF_SHA256 = 'b3bc56608035a272943912a3663432f414a258825e6640b668e3fa0b61c8a567'
OPAQUE_BASELINE_METADATA_NAMES = frozenset('provenance/' + name for name in (
    'argument-derivation.json', 'ctrl-key-api-repair.json', 'ctrl-key-api-repair.patch',
    'engine-input-reconciliation.json', 'host-prerequisite-facts.json',
    'main-syntax-001.json', 'main-syntax-002.json', 'object-argv-before-relocation.json',
    'original-empty-search-facts.json', 'original-engine-build.json',
    'probe-code-inputs-001.json', 'reconstruction-provenance.json', 'wrapper-inputs-launch.json'))
SCOPE = 'incremental-neutral-engine-candidate'
_MAINTENANCE_RETAINED_STATE = None
# Both explicit Emscripten wasm32 spellings occur in retained inputs. They are
# admitted vocabulary, never interchangeable identities: source and SDK must
# preserve and match the exact independently pinned declaration.
EMSCRIPTEN_TRIPLES = ('wasm32-emscripten', 'wasm32-unknown-emscripten')
REFERENCE_FIELDS = ('root', 'path', 'sha256')
SELECTION_FIELDS = ('document_profile', 'profile', 'sources', 'recipe_sha256', 'sources_sha256',
                    'projection', 'projection_sha256', 'sdk', 'sdk_manifest_sha256',
                    'reuse_root', 'reuse_proof', 'reuse_proof_sha256')
MAX_DOCUMENT = 64 * 1024 * 1024


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Invalid ' + label + ' fields')


def document(raw):
    if len(raw) > MAX_DOCUMENT:
        raise ValueError('Maintenance document exceeds 64 MiB')
    # Command ledgers can exceed the separate retained-manifest 32 MiB limit.
    return document_contract.strict_json(raw, 'maintenance document', maximum=MAX_DOCUMENT)


def sha(value, label):
    manifest.sha256(value, label)
    if value == '0' * 64:
        raise ValueError('Zero ' + label + ' is not an input identity')
    return value


def ordinary(path, directory=False, *, sdk=False):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Maintenance paths must be explicit absolute paths')
    for entry in reversed((path, *path.parents)):
        state = entry.lstat()
        want_dir = directory if entry == path else True
        if (stat.S_ISLNK(state.st_mode) or getattr(state, 'st_file_attributes', 0) & 0x400
                or not (stat.S_ISDIR(state.st_mode) if want_dir else stat.S_ISREG(state.st_mode))
                or not want_dir and state.st_nlink != 1 and not sdk):
            raise ValueError('Nonordinary maintenance input: ' + str(entry))
    if path.resolve(strict=True) != path:
        raise ValueError('Aliased maintenance input: ' + str(path))
    return path


def checked_read(path, expected=None, *, sdk=False):
    path = ordinary(path, sdk=sdk)
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('Input changed while reading: ' + str(path))
    value = hashlib.sha256(raw).hexdigest()
    if expected is not None and value != sha(expected, 'input pin'):
        raise ValueError('Input hash mismatch: ' + str(path))
    return raw


def checked_document(path, expected=None, *, sdk=False):
    return document(checked_read(path, expected, sdk=sdk))


def ref_path(reference, roots, inventories):
    fields(reference, REFERENCE_FIELDS, 'input reference')
    root = reference['root']
    if root not in roots:
        raise ValueError('Unknown input reference root')
    name = manifest.path_name(reference['path'])
    wanted = sha(reference['sha256'], 'input reference')
    if inventories[root].get(name) != wanted:
        raise ValueError('Reference not bound by complete inventory: ' + name)
    path = roots[root] / name
    if digest(ordinary(path, sdk=root == 'sdk')) != wanted:
        raise ValueError('Referenced bytes changed: ' + name)
    return path


def inventory(root, declared, excluded):
    fields(declared, ('files', 'directories', 'modes'), 'reuse inventory')
    manifest.inventory_contract(dict(declared, schema_version=1), excluded)
    actual = manifest.tree_inventory(root, excluded)
    if actual != declared:
        raise ValueError('Complete baseline reuse inventory differs')


def profile_selector(value):
    if type(value) is not str or value not in ('pixel', 'physical', 'editor'):
        raise ValueError('Maintenance profile must be explicitly pixel, physical or editor')
    return value


def profile_contract(value):
    if profile_selector(value) == 'editor':
        import appended_engine_editor_contract
        return appended_engine_editor_contract
    return document_contract


def profile_call(selected, method, **kwargs):
    module = profile_contract(selected)
    key = 'editor_profile' if selected == 'editor' else 'document_profile'
    return getattr(module, method)(**{key: selected}, **kwargs)


def profile_path(document_profile):
    return PROFILE_PATHS[profile_selector(document_profile)]


def required_helpers(document_profile):
    selected = profile_selector(document_profile)
    return COMMON_HELPERS + (profile_path(selected),) + (
        ('tools/appended_engine_editor_contract.py',) if selected == 'editor' else ())


def metadata_interface_paths(selected):
    selected = profile_selector(selected)
    paths = {'contract_header': ('include/foundation/appended/engine_provider.h', document_contract.BASE_HEADER_SHA256),
        'document_header': ('include/foundation/appended/engine_provider_document_v2.h', document_contract.EXTENSION_HEADER_SHA256),
        'document_contract': ('abi/engine/document-v2/contract.json', document_contract.CONTRACT_SHA256),
        'document_catalog': ('abi/engine/document-v2/catalog.json', document_contract.DOCUMENT_CATALOG_SHA256),
        'document_schema': ('abi/engine/document-v2/schema-definition.json', document_contract.DOCUMENT_SCHEMA_SHA256),
        'action_ack': ('abi/engine/document-v2/action-ack.json', document_contract.ACTION_ACK_SCHEMA_SHA256)}
    if selected in ('physical', 'editor'):
        paths['physical_catalog'] = ('abi/engine/physical-input-catalog.json', document_contract.PHYSICAL_CATALOG_SHA256)
    if selected == 'editor':
        editor = profile_contract(selected)
        paths.update({
            'editor_header': ('abi/appended/engine_editor_protocol.h', editor.EDITOR_HEADER_SHA256),
            'editor_contract': ('abi/appended/editor-v1/contract.json', editor.CONTRACT_SHA256),
            'editor_catalog': ('abi/appended/editor-v1/catalog.json', editor.EDITOR_CATALOG_SHA256),
            'editor_schema': ('abi/appended/editor-v1/binary-schema.json', editor.EDITOR_SCHEMA_SHA256)})
    return paths


def _validate_metadata_interfaces(recipe, selected):
    inputs = recipe.get('inputs') if type(recipe) is dict else None
    if type(inputs) is not dict:
        raise ValueError('Metadata interface inputs must be declared in the source recipe')
    for name, pin in metadata_interface_paths(selected).values():
        item = inputs.get(name)
        if type(item) is not dict or item.get('role') != 'interface' or item.get('sha256') != pin:
            raise ValueError('Metadata input must retain the exact interface role/hash: ' + name)


def profile(document_profile):
    selected = profile_selector(document_profile)
    selected_contract = profile_contract(selected)
    value = checked_document(ROOT / profile_path(selected))
    fields(value, ('schema_version', 'kind', 'name', 'document_profile', 'scope',
        'capabilities', 'bridge_abi', 'physical_input_capabilities', 'direct_objects',
        'engine_objects', 'exceptions', 'archive_members', 'link_archive_names',
        'link_literals', 'link_settings', 'compile_literals', 'metadata_generator',
        'python_entrypoints', 'source_map_sha256', 'owner_postimages',
        'derived_commands', 'source_bindings', 'declared_source_aliases'), 'document maintenance profile')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-document-v2-maintenance-profile-v1'
            or value['name'] != 'webkitwasm-copied' + selected_contract.CAPABILITIES[selected] + '-ndv2-v1'
            or value['document_profile'] != selected or value['scope'] != SCOPE
            or value['capabilities'] != selected_contract.CAPABILITIES[selected]
            or type(value['bridge_abi']) is not int or value['bridge_abi'] != 65536
            or type(value['physical_input_capabilities']) is not int
            or value['physical_input_capabilities'] != (208 if selected in ('physical', 'editor') else 0)):
        raise ValueError('Unknown maintained document-v2 profile')
    ids = value['direct_objects'] + value['engine_objects']
    if (any(type(items) is not list or not items for items in
            (value['direct_objects'], value['engine_objects']))
            or len(ids) != len(set(ids)) or set(value['source_bindings']) != set(ids)
            or set(value['owner_postimages']) != set(value['engine_objects'])
            or type(value['exceptions']) is not list
            or len(value['exceptions']) != len(set(value['exceptions']))
            or not set(value['exceptions']) <= set(value['direct_objects'])
            or not set(value['derived_commands']) <= set(ids)):
        raise ValueError('Invalid closed document object/owner profile')
    for name in ids:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name):
            raise ValueError('Invalid document object identity')
        manifest.path_name(value['source_bindings'][name])
    for paths in value['owner_postimages'].values():
        manifest.paths(paths, 'owner postimages', nonempty=True)
    sha(value['source_map_sha256'], 'source map')
    exports = ('_bib_engine_get_provider_v1,_bib_engine_wasm_bridge_v1,'
        '_bib_engine_wasm_dispatch_v1,_bib_engine_wasm_document_facts_v1,'
        '_bib_engine_wasm_document_configure_v1,_malloc,_free')
    if selected == 'editor':
        exports = exports.replace('wasm_document_', 'wasm_editor_')
    if (value['link_settings'].get('EXPORTED_FUNCTIONS') != exports
            or '-DBIB_ENGINE_PROVIDER_DOCUMENT_V2=1' not in value['compile_literals']
            or (selected == 'editor' and '-DBIB_ENGINE_PROVIDER_EDITOR_V1=1' not in value['compile_literals'])
            or value['link_literals'].count('-lexports.js') != 1
            or '-lexports.js' in value['compile_literals']
            or value['metadata_generator'] != 'source/document-provider/runtime/generate_document_metadata.py'):
        raise ValueError('Document metadata/exports/definition policy differs')
    return value


@dataclass(frozen=True)
class Inspection:
    selection: dict
    recipe: dict
    projection: dict
    proof: dict
    roots: dict
    inventories: dict
    profile: dict


def _tool(tool, *, sdk_root=None, sdk_files=None):
    if sdk_root is None:
        fields(tool, ('path', 'sha256', 'version', 'provenance', 'recovery_limit'), 'host tool')
        for key in ('version', 'provenance', 'recovery_limit'):
            manifest.text(tool[key], 'external host tool ' + key)
        path = ordinary(tool['path'])
    else:
        fields(tool, ('path', 'sha256'), 'SDK tool')
        name = manifest.path_name(tool['path'])
        if sdk_files.get(name) != tool['sha256']:
            raise ValueError('SDK tool absent from paired inventory')
        path = ordinary(sdk_root / name, sdk=True)
    if digest(path) != sha(tool['sha256'], 'tool'):
        raise ValueError('Tool bytes changed: ' + str(path))
    if not os.access(path, os.X_OK):
        raise ValueError('Selected tool is not executable: ' + str(path))
    return path


def _validate_projection(value, sources, source_files, config):
    fields(value, ('schema_version', 'kind', 'document_profile', 'source_map',
                   'files', 'physical_alias_groups', 'declared_source_aliases'), 'document source projection')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-document-v2-source-projection-v1'
            or value['document_profile'] != config['document_profile']
            or type(value['files']) is not dict or not value['files']):
        raise ValueError('Projection must select exact retained final source files')
    fields(value['source_map'], ('path', 'sha256'), 'frozen source map')
    source_map = manifest.path_name(value['source_map']['path'])
    if (value['source_map']['sha256'] != config['source_map_sha256']
            or source_files.get(source_map) != config['source_map_sha256']):
        raise ValueError('Projection must bind the selected frozen source map')
    for name, item in value['files'].items():
        manifest.path_name(name)
        fields(item, ('preimage_sha256', 'sha256'), 'projected source pre/postimage')
        if item['preimage_sha256'] is not None:
            sha(item['preimage_sha256'], 'projected preimage')
        if source_files.get(name) != sha(item['sha256'], 'projected postimage'):
            raise ValueError('Selected projection differs from retained sources: ' + name)
        if digest(ordinary(sources / name)) != item['sha256']:
            raise ValueError('Selected projection source changed: ' + name)
    required = set(config['source_bindings'].values())
    required.update(path for paths in config['owner_postimages'].values() for path in paths)
    if not required <= set(value['files']):
        raise ValueError('Projection omits an exact direct source or engine owner postimage')
    _validate_alias_groups(value['physical_alias_groups'], value['files'])
    _validate_alias_groups(value['declared_source_aliases'], value['files'])
    if document_contract.canonical_json(value['declared_source_aliases']) != document_contract.canonical_json(config['declared_source_aliases']):
        raise ValueError('Declared source aliases differ from the explicit maintained layout')
    physical = {path for group in value['physical_alias_groups'] for path in group['paths']}
    declared = {path for group in value['declared_source_aliases'] for path in group['paths']}
    if physical.intersection(declared):
        raise ValueError('Historical physical aliases and declared new layout aliases overlap')


def _validate_alias_groups(groups, files):
    """Aliases are reviewed per physical path, never inferred from equal bytes."""
    if type(groups) is not list:
        raise ValueError('Expected explicit physical alias groups')
    seen = set()
    for group in groups:
        fields(group, ('canonical', 'paths', 'preimages', 'postimages'), 'physical alias group')
        paths = manifest.paths(group['paths'], 'physical aliases', nonempty=True)
        if (len(paths) < 2 or group['canonical'] not in paths
                or seen.intersection(paths) or set(group['preimages']) != set(paths)
                or set(group['postimages']) != set(paths)):
            raise ValueError('Overlapping or incomplete physical alias group')
        for path in paths:
            if (path not in files or group['preimages'][path] != files[path]['preimage_sha256']
                    or group['postimages'][path] != files[path]['sha256']):
                raise ValueError('Alias pre/postimage does not identify its exact physical path')
        if len(set(group['postimages'].values())) != 1:
            raise ValueError('Physical aliases require identical selected postimages')
        seen.update(paths)


def inspect_inputs(selection):
    """Pure complete source/SDK/reuse verification; no tool execution/discovery."""
    if hasattr(selection, '__dict__'):
        selection = vars(selection)
    selection = dict(selection)
    fields(selection, SELECTION_FIELDS, 'maintenance selection')
    selected_profile = profile(selection['document_profile'])
    if selection['profile'] != selected_profile['name']:
        raise ValueError('Select the matching explicit document-v2 maintenance profile')
    for key in SELECTION_FIELDS:
        if key.endswith('sha256'):
            sha(selection[key], key)
    sources = ordinary(selection['sources'], True)
    sdk_root = ordinary(selection['sdk'], True)
    reuse = ordinary(selection['reuse_root'], True)
    roots = {'sources': sources, 'sdk': sdk_root, 'reuse': reuse}
    for a in roots.values():
        for b in roots.values():
            if a != b and (a in b.parents or b in a.parents):
                raise ValueError('Retained source, SDK and baseline roots must be disjoint')
    if len(set(roots.values())) != 3:
        raise ValueError('Retained input roots must be distinct')
    recipe_input = checked_document(sources / 'recipe.json', selection['recipe_sha256'])
    _validate_metadata_interfaces(recipe_input, selection['document_profile'])
    checked_read(sources / 'sources.json', selection['sources_sha256'])
    source_manifest, source_hash, recipe = manifest.verify_sources(sources)
    if source_hash != selection['sources_sha256'] or digest(sources / 'recipe.json') != selection['recipe_sha256']:
        raise ValueError('Explicit retained source pins differ')
    if ((recipe['target']['system'], recipe['target']['processor'], recipe['target']['pointer_bits'])
            != ('Emscripten', 'wasm32', 32)
            or recipe['target']['triple'] not in EMSCRIPTEN_TRIPLES
            or recipe['options'] != {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'}
            or recipe['provider']['binding'] != 'copied-owner-bridge'
            or (recipe['provider']['abi_major'], recipe['provider']['abi_minor']) != (1, 1)
            or recipe['provider']['header'] != 'include/foundation/appended/engine_provider.h'
            or recipe['provider']['header_sha256'] != document_contract.BASE_HEADER_SHA256):
        raise ValueError('Source recipe is not the exact document-v2 browser profile')
    for name in required_helpers(selection['document_profile']):
        raw = checked_read(ROOT / name)
        if source_manifest['files'].get(name) != hashlib.sha256(raw).hexdigest():
            raise ValueError('Retain exact maintained producer input in a new recipe: ' + name)
    projection_path = ordinary(selection['projection'])
    if sources not in projection_path.parents:
        raise ValueError('Selected projection must be an inventoried source recipe input')
    projection_name = projection_path.relative_to(sources).as_posix()
    if source_manifest['files'].get(projection_name) != selection['projection_sha256']:
        raise ValueError('Selected projection is not bound by the source recipe')
    projection = checked_document(projection_path, selection['projection_sha256'])
    _validate_projection(projection, sources, source_manifest['files'], selected_profile)
    checked_read(sdk_root / 'sdk.json', selection['sdk_manifest_sha256'], sdk=True)
    if verify_sdk(sdk_root) != selection['sdk_manifest_sha256']:
        raise ValueError('Explicit paired SDK manifest pin differs')
    sdk_data = checked_document(sdk_root / 'sdk.json', selection['sdk_manifest_sha256'], sdk=True)
    sdk_target = sdk_data['target']
    sdk_pointer_bits = sdk_target.get('pointer_bits', 32)
    if ((sdk_target['system'], sdk_target['processor']) != ('Emscripten', 'wasm32')
            or sdk_target['triple'] not in EMSCRIPTEN_TRIPLES
            or type(sdk_pointer_bits) is not int or sdk_pointer_bits != 32):
        raise ValueError('Maintenance needs the paired browser SDK')
    if recipe['target']['triple'] != sdk_target['triple']:
        raise ValueError('Source target triple differs from the exact paired SDK declaration')
    if recipe['toolchain']['paired_sdk_sha256'] != selection['sdk_manifest_sha256']:
        raise ValueError('Source recipe paired SDK differs')
    proof_path = ordinary(selection['reuse_proof'])
    if proof_path.parent != reuse or proof_path.name != 'reuse-proof.json':
        raise ValueError('Reuse proof must be the explicit baseline root reuse-proof.json')
    proof = checked_document(proof_path, selection['reuse_proof_sha256'])
    fields(proof, ('schema_version', 'kind', 'profile', 'document_profile', 'target', 'paired_sdk_sha256',
        'baseline', 'inventory', 'host_tools', 'sdk_tools', 'python_launch',
        'objects', 'archives', 'replacements', 'link', 'metadata', 'private_cache',
        'emscripten_config', 'recovery_limits', 'header_identity'), 'baseline reuse proof')
    if (type(proof['schema_version']) is not int or proof['schema_version'] != 1 or proof['kind'] != REUSE_KIND
            or proof['profile'] != selection['profile'] or proof['document_profile'] != selection['document_profile']
            or proof['target'] != recipe['target']
            or proof['paired_sdk_sha256'] != selection['sdk_manifest_sha256']):
        raise ValueError('Baseline reuse proof identity/profile differs')
    inventory(reuse, proof['inventory'], 'reuse-proof.json')
    inventories = {'sources': source_manifest['files'], 'sdk': sdk_data['files'],
                   'reuse': proof['inventory']['files']}
    result = Inspection({key: str(value) if isinstance(value, Path) else value
                         for key, value in selection.items()}, recipe, projection, proof,
                        roots, inventories, selected_profile)
    _validate_proof(result)
    return result


def _argument_directory(operand, inspection):
    """Bind an observed include-search operand to its complete admitted closure.

    Only the reviewed joined -I and separate -isystem forms are supported. Other
    filename options are outside this profile, even if a caller pins a file for
    them. The sole future generated directory is the real metadata node.
    """
    if operand == '{generated}':
        return []  # Both exact generated metadata outputs are explicit graph edges.
    match = re.fullmatch(r'\{(sources|sdk|reuse)\}(?:/(.+))?', operand)
    if match is None or inspection is None:
        raise ValueError('Include input must name an admitted canonical root binding')
    root, suffix = match.groups()
    suffix = manifest.path_name(suffix) if suffix is not None else ''
    directory = inspection.roots[root] / suffix
    ordinary(directory, directory=True, sdk=root == 'sdk')
    prefix = suffix + '/' if suffix else ''
    names = [name for name in inspection.inventories[root] if name.startswith(prefix)]
    # Complete manifests were verified before this function. Retain directory
    # identity as well as every inventoried descendant as actual graph inputs,
    # including an explicitly inventoried empty include-search directory.
    return [str(directory), *(str(inspection.roots[root] / name) for name in sorted(names))]


def _setting(value, selected_profile):
    name, separator, setting = value.partition('=')
    if not separator or not re.fullmatch('[A-Z][A-Z0-9_]*', name):
        raise ValueError('Use explicit reviewed Emscripten settings')
    # Emscripten normalizes official NO_ aliases before applying values. Keep
    # exactly one positive spelling in this closed profile rather than trying
    # to infer boolean aliases, response files or settings that name commands.
    if name.startswith('NO_'):
        raise ValueError('Negative Emscripten setting aliases are outside this profile')
    if selected_profile['link_settings'].get(name) != setting:
        raise ValueError('Emscripten setting differs from the fixed neutral profile: ' + name)
    return name, setting


def _arguments(arguments, *, link=False, inspection=None):
    """Parse the closed document grammar and return explicit directory inputs.

    Compiler/linker positional inputs, outputs, response/config files, plugins,
    arbitrary setting names, transforms and other auxiliary commands have no
    grammar production. Structured source/objects/archives/pre-JS/host-library/
    data records remain the only other filename-bearing command inputs.
    """
    if type(arguments) is not list or any(type(arg) is not str or not arg or '\x00' in arg
                                          or '\n' in arg or '\r' in arg for arg in arguments):
        raise ValueError('Expected exact nonempty argument arrays')
    if inspection is None:
        raise ValueError('Argument validation requires an explicit inspected document profile')
    if link:
        if arguments.count('-lexports.js') != 1:
            raise ValueError('Final link requires exactly one literal -lexports.js')
    elif '-lexports.js' in arguments:
        raise ValueError('-lexports.js is a link-only argument')
    selected = inspection.profile
    literals = set(selected['link_literals' if link else 'compile_literals'])
    dependencies, settings, index = [], {}, 0
    while index < len(arguments):
        arg = arguments[index]
        if arg in literals:
            pass
        elif not link and arg.startswith('-I') and len(arg) > 2:
            dependencies.extend(_argument_directory(arg[2:], inspection))
        elif not link and arg == '-isystem':
            index += 1
            if index >= len(arguments):
                raise ValueError('Missing explicit system include directory')
            dependencies.extend(_argument_directory(arguments[index], inspection))
        elif link and arg.startswith('-s'):
            if arg == '-s':
                index += 1
                if index >= len(arguments):
                    raise ValueError('Missing Emscripten setting')
                value = arguments[index]
            else:
                value = arg[2:]
            name, setting = _setting(value, selected)
            settings[name] = setting
        else:
            raise ValueError('Argument is outside the reviewed document-v2 grammar: ' + arg)
        index += 1
    if link and (settings != selected['link_settings'] or '--no-entry' not in arguments):
        raise ValueError('Final link must declare the complete fixed neutral factory policy')
    return list(dict.fromkeys(dependencies))


def _exception_policy(arguments):
    values = [arg == '-fexceptions' for arg in arguments if arg in ('-fexceptions', '-fno-exceptions')]
    return values[-1] if values else None


def _settings(arguments, selected):
    settings, index = {}, 0
    while index < len(arguments):
        arg = arguments[index]
        if arg == '-s':
            index += 1
            if index >= len(arguments):
                raise ValueError('Missing Emscripten setting')
            setting = arguments[index]
        elif arg.startswith('-s') and not arg.startswith(('-std=', '-stdlib=', '-stack-')):
            setting = arg[2:]
        else:
            index += 1
            continue
        name, value = _setting(setting, selected)
        if name in settings and settings[name] != value:
            raise ValueError('Conflicting Emscripten setting: ' + name)
        settings[name] = value
        index += 1
    return settings


def _original_output(record, original_root, reuse_root):
    argv = record['argv']
    if argv.count('-o') != 1 or argv.count('-c') != 1:
        raise ValueError('Original compile record requires exact source and output')
    try:
        output = Path(argv[argv.index('-o') + 1])
        source = Path(argv[argv.index('-c') + 1])
    except IndexError:
        raise ValueError('Truncated original compile record') from None
    output = Path(os.path.normpath(str(output if output.is_absolute() else Path(record['cwd']) / output)))
    try:
        relative = output.relative_to(original_root)
    except ValueError:
        raise ValueError('Original object output escapes its recorded baseline root') from None
    return reuse_root / relative, source.name


def _relocate_original(value, cwd, bindings):
    path = Path(value)
    path = Path(os.path.normpath(str(path if path.is_absolute() else Path(cwd) / path)))
    matches = [(root, Path(prefix)) for root, prefix in bindings.items()
               if path == Path(prefix) or Path(prefix) in path.parents]
    if len(matches) != 1:
        raise ValueError('Original filename lacks one exact admitted root binding')
    root, prefix = matches[0]
    suffix = path.relative_to(prefix).as_posix()
    return '{' + root + '}' + ('/' + manifest.path_name(suffix) if suffix != '.' else '')


def _original_arguments(record, bindings):
    """Relocate only known directory operands; no generic filename guessing."""
    argv, result, index = record['argv'], [], 1
    if argv.count('-c') != 1 or argv.count('-o') != 1:
        raise ValueError('Original compile requires one source and output')
    while index < len(argv):
        arg = argv[index]
        if arg in ('-c', '-o', '-MT', '-MF', '-MQ'):
            index += 1
            if index >= len(argv):
                raise ValueError('Truncated original compile operand')
        elif arg in ('-MD', '-MMD', '-MP'):
            pass
        elif arg.startswith('-I') and len(arg) > 2:
            result.append('-I' + _relocate_original(arg[2:], record['cwd'], bindings))
        elif arg == '-isystem':
            index += 1
            if index >= len(argv):
                raise ValueError('Truncated original system include')
            result.extend(('-isystem', _relocate_original(argv[index], record['cwd'], bindings)))
        else:
            result.append(arg)
        index += 1
    return result


def _depfile_inputs(raw, *, target=None):
    """Read one compiler make dependency rule, rejecting expansion and ambiguity."""
    try:
        text = raw.decode('utf-8').replace('\\\r\n', '').replace('\\\n', '')
    except UnicodeError:
        raise ValueError('Invalid original dependency record encoding') from None
    tokens, token, separator, index = [], '', None, 0
    while index < len(text):
        char = text[index]
        if char == '\\':
            index += 1
            if index >= len(text) or text[index] not in ' \\#:$\t':
                raise ValueError('Unsupported original dependency escape')
            token += text[index]
        elif char == '$':
            index += 1
            if index >= len(text) or text[index] != '$':
                raise ValueError('Dependency variable expansion is not admitted')
            token += '$'
        elif char == ':':
            if separator is not None:
                raise ValueError('Multiple original dependency rules are not admitted')
            if token:
                tokens.append(token); token = ''
            separator = len(tokens)
        elif char.isspace():
            if token:
                tokens.append(token); token = ''
        elif char in '#\x00':
            raise ValueError('Ambiguous original dependency record')
        else:
            token += char
        index += 1
    if token:
        tokens.append(token)
    if separator != 1 or len(tokens) < 2:
        raise ValueError('One complete original dependency target is required')
    if target is not None and tokens[0] != target:
        raise ValueError('Original dependency target differs from its compile command')
    return tokens[1:]


def _macros(arguments):
    return [arg for arg in arguments if arg.startswith(('-D', '-U'))]


def _include_directories(arguments):
    directories, index = [], 0
    while index < len(arguments):
        arg = arguments[index]
        if arg.startswith('-I') and len(arg) > 2:
            directories.append(arg[2:])
        elif arg == '-isystem':
            index += 1
            if index >= len(arguments):
                raise ValueError('Missing original include-search operand')
            directories.append(arguments[index])
        index += 1
    return directories


def _search_closure(identity, arguments, inspection, header_view, closures, validated):
    """Conservative complete original search namespace, shared across objects.

    This mode does not invent dependency files. Every original copied filename
    and byte in the original search roots is unchanged. Core header/config
    postimages fail closed; only the exact profile's known C++ owner postimages
    may differ, and per-object source/unified membership is checked separately.
    """
    sha(identity, 'shared original include-search closure')
    if identity not in closures:
        raise ValueError('Original include-search closure is absent')
    value = closures[identity]
    fields(value, ('schema_version', 'kind', 'directories', 'original_inventory_sha256',
        'sdk_manifest_sha256', 'namespace_sha256', 'headers_sha256'), 'original include-search closure')
    directories = _include_directories(arguments)
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-engine-original-include-search-v1'
            or value['directories'] != directories
            or hashlib.sha256(encoded(value)).hexdigest() != identity):
        raise ValueError('Shared include-search identity/original operands differ')
    if identity in validated:
        return
    original = header_view['original_files']
    if (value['original_inventory_sha256'] != hashlib.sha256(encoded(original)).hexdigest()
            or value['sdk_manifest_sha256'] != inspection.selection['sdk_manifest_sha256']):
        raise ValueError('Shared search closure differs from complete original copy/SDK authority')
    namespace, headers, prefixes = {}, {}, []
    translation_units = {'.c', '.cc', '.cpp', '.cxx', '.m', '.mm', '.s'}
    # Every original physical input directory also participates in possible
    # quoted-header lookup, including transitive headers outside explicit -I.
    # The copier-generated command ledger is metadata, with no original input
    # identity; new proof metadata may remain outside these compiler roots.
    quote_prefixes = []
    for prefix in sorted({str(Path(name).parent) + '/'
            if str(Path(name).parent) != '.' else ''
            for name, item in original.items()
            if item.get('source_identity', [1]) is not None and Path(name).suffix.lower() not in ('.o', '.a')}):
        if not any(prefix.startswith(parent) for parent in quote_prefixes):
            quote_prefixes.append(prefix)
    for name, item in original.items():
        if inspection.inventories['reuse'].get(name) != item['sha256']:
            raise ValueError('Original copied source/header/config bytes changed outside include roots')
    for name in inspection.inventories['reuse']:
        if name not in original and any(name.startswith(prefix) for prefix in quote_prefixes):
            # The explicit opaque mode inherits the admitted artifact root's
            # existing provenance metadata. It does not introduce those names.
            old_metadata = header_view.get('opaque_baseline_metadata', {})
            if old_metadata.get(name) != inspection.inventories['reuse'][name]:
                raise ValueError('New filename shadows the original quoted-include namespace')
    for root, files in (('reuse', original), ('sdk', inspection.inventories['sdk'])):
        for name, item in files.items():
            pin = item['sha256'] if root == 'reuse' else item
            key = '{' + root + '}/' + name
            namespace[key] = pin
            if Path(name).suffix.lower() not in translation_units | {'.o', '.a'}:
                headers[key] = pin
    for operand in directories:
        match = re.fullmatch(r'\{(reuse|sdk)\}(?:/(.+))?', operand)
        if match is None:
            raise ValueError('Original search roots must name copied baseline or paired SDK')
        root, suffix = match.groups()
        suffix = manifest.path_name(suffix) if suffix is not None else ''
        prefix = suffix + '/' if suffix else ''
        prefixes.append((root, prefix))
        files = original if root == 'reuse' else inspection.inventories['sdk']
        selected = {name: item['sha256'] if root == 'reuse' else item
                    for name, item in files.items() if name.startswith(prefix)}
        actual = {name: pin for name, pin in inspection.inventories[root].items() if name.startswith(prefix)}
        if actual != selected:
            raise ValueError('Original include-search namespace or any copied/config input changed')
    expected_posts = {name for names in inspection.profile['owner_postimages'].values() for name in names}
    for (root, path), selected in header_view['postimages'].items():
        if root == 'reuse':
            if (Path(path).suffix.lower() not in translation_units
                    or selected['path'] not in expected_posts):
                raise ValueError('Include-search reuse forbids changed core headers/config or unaccounted C++ owners')
    if (value['namespace_sha256'] != hashlib.sha256(encoded(namespace)).hexdigest()
            or value['headers_sha256'] != hashlib.sha256(encoded(headers)).hexdigest()):
        raise ValueError('Shared complete header/config namespace digest differs')
    validated.add(identity)


def _original_unified_members(value, command, inspection, resolve, original_files):
    members = value['unified_members']
    if type(members) is not list:
        raise ValueError('Original unified members must be an exact ordered list')
    source_name = Path(value['source']['original_path']).name
    if not source_name.startswith('UnifiedSource-'):
        if members:
            raise ValueError('Only a recorded unified source may declare unified siblings')
        return
    raw = checked_read(resolve(value['source']['input']))
    includes = re.findall(rb'^\s*#\s*include\s+"([^"\r\n]+)"\s*$', raw, re.MULTILINE)
    directives = re.findall(rb'^\s*#\s*include\b[^\r\n]*', raw, re.MULTILINE)
    if not includes or len(includes) != len(directives) or len(includes) != len(members):
        raise ValueError('Original unified include list must be complete and literal')
    search = [str(Path(value['source']['original_path']).parent)]
    bindings = inspection.proof['baseline']['original_bindings']
    for operand in _include_directories(value['arguments']):
        match = re.fullmatch(r'\{(reuse|sdk)\}(?:/(.+))?', operand)
        if match is None:
            raise ValueError('Original unified search requires an admitted original root')
        root, suffix = match.groups()
        search.append(str(Path(bindings[root]) / (suffix or '')))
    for include, member in zip(includes, members):
        try:
            spelling = include.decode('ascii')
        except UnicodeError:
            raise ValueError('Unsupported original unified include spelling') from None
        if Path(spelling).suffix.lower() not in ('.cpp', '.cc', '.cxx') or Path(spelling).is_absolute():
            raise ValueError('Original unified include must name an exact relative C++ sibling')
        candidates = []
        for directory in search:
            path = os.path.normpath(str(Path(directory) / spelling))
            relocated = _relocate_original(path, command['cwd'], bindings)
            match = re.fullmatch(r'\{reuse\}/(.+)', relocated)
            if match is not None and match[1] in original_files:
                candidates.append(path)
        if not candidates or member['original_path'] != candidates[0]:
            raise ValueError('Original unified member differs from exact original include-search selection')


def _context_record(value, command, inspection, resolve, header_view, closures, validated):
    """Bind every retained object to original argv and complete dependency bytes."""
    common = ('source', 'headers', 'macros', 'generated_metadata', 'sdk_manifest_sha256',
              'arguments', 'closure_mode', 'unified_members')
    mode = value.get('closure_mode')
    if mode not in ('depfile-v1', 'include-search-v1'):
        raise ValueError('Select an explicit original compile closure mode')
    fields(value, common + (('depfile',) if mode == 'depfile-v1' else ('search_closure_sha256',)),
           'original compile context')
    if mode == 'depfile-v1' and (command['argv'].count('-MD') != 1 or '-MMD' in command['argv'] or command['argv'].count('-MF') != 1):
        raise ValueError('Complete original header closure requires one -MD/-MF record including system headers')
    if (value['arguments'] != _original_arguments(command, inspection.proof['baseline']['original_bindings'])
            or value['sdk_manifest_sha256'] != inspection.selection['sdk_manifest_sha256']
            or value['macros'] != _macros(value['arguments'])
            or _relocate_original(command['argv'][0], command['cwd'],
                inspection.proof['baseline']['original_bindings']) != '{sdk}/upstream/emscripten/em++'):
        raise ValueError('Original compile argument/macro/SDK context differs')
    if type(value['headers']) is not list or type(value['generated_metadata']) is not list:
        raise ValueError('Expected complete header and generated metadata closures')
    original_files = header_view['original_files']
    inputs = [value['source'], *value['headers'], *value['generated_metadata'], *value['unified_members']]
    original_paths = []
    for item in inputs:
        fields(item, ('original_path', 'input'), 'original compile input')
        path = Path(item['original_path'])
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('Original compile inputs require exact absolute paths')
        original_paths.append(str(path))
        resolve(item['input'])
        relocated = _relocate_original(str(path), command['cwd'],
            inspection.proof['baseline']['original_bindings'])
        match = re.fullmatch(r'\{(reuse|sdk)\}/(.+)', relocated)
        if match is None:
            raise ValueError('Original compile input must identify the exact copied baseline or paired SDK path')
        root, name = match.groups()
        pin = (original_files.get(name, {}).get('sha256') if root == 'reuse'
               else inspection.inventories['sdk'].get(name))
        if pin != item['input']['sha256']:
            raise ValueError('Original compile preimage differs from its complete original copy/SDK authority')
    if len(original_paths) != len(set(original_paths)):
        raise ValueError('Duplicate original compile input role')
    normalize = lambda path: os.path.normpath(str(Path(path) if Path(path).is_absolute() else Path(command['cwd']) / path))
    source = normalize(command['argv'][command['argv'].index('-c') + 1])
    if source != original_paths[0]:
        raise ValueError('Original context source differs from its exact compile command')
    _original_unified_members(value, command, inspection, resolve, original_files)
    if mode == 'include-search-v1':
        if value['headers']:
            raise ValueError('Shared include-search mode binds headers through its complete namespace')
        _search_closure(value['search_closure_sha256'], value['arguments'], inspection,
            header_view, closures, validated)
        return
    argv = command['argv']
    target = argv[argv.index('-MT') + 1] if '-MT' in argv else argv[argv.index('-o') + 1]
    observed = [normalize(path) for path in _depfile_inputs(checked_read(resolve(value['depfile'])), target=target)]
    if (source != original_paths[0] or len(observed) != len(set(observed))
            or set(observed) != set(original_paths)):
        raise ValueError('Original depfile does not establish the complete retained input closure')


def _reusable_context(value, command, inspection, postimages=None):
    """Equal source alone never authorizes an untouched archive member."""
    for item in [value['source'], *value['headers'], *value['generated_metadata'], *value['unified_members']]:
        relocated = _relocate_original(item['original_path'], command['cwd'],
            inspection.proof['baseline']['original_bindings'])
        match = re.fullmatch(r'\{(sources|sdk|reuse)\}/(.+)', relocated)
        if match is None:
            raise ValueError('Retained object input lacks an exact current physical path')
        root, path = match.groups()
        selected = ({} if postimages is None else postimages).get((root, path))
        current = selected['sha256'] if selected else inspection.inventories[root].get(path)
        if current != item['input']['sha256']:
            raise ValueError('Untouched member source/header/generated-metadata context changed; rebuild its owner')
    _arguments(value['arguments'], inspection=inspection)


def _object_provenance(obj, commands, inspection):
    provenance = obj['provenance']
    config = inspection.profile
    donor_key = 'command_sha256' if provenance.get('kind') == 'original-command-v1' else 'donor_command_sha256'
    identity = sha(provenance.get(donor_key), 'compile provenance command')
    if identity not in commands:
        raise ValueError('Compile provenance donor is absent from original commands')
    original = commands[identity]
    source = original['argv'][original['argv'].index('-c') + 1]
    arguments = _original_arguments(original, inspection.proof['baseline']['original_bindings'])
    if provenance.get('kind') == 'original-command-v1':
        fields(provenance, ('kind', 'command_sha256'), 'original command provenance')
        if obj['id'] in config['derived_commands'] or Path(source).name != obj['id']:
            raise ValueError('New source requires explicit derived command provenance')
    else:
        fields(provenance, ('kind', 'donor_command_sha256', 'profile_sha256',
                           'source_replacement', 'remove', 'append'), 'derived command provenance')
        rule = config['derived_commands'].get(obj['id'])
        if (provenance['kind'] != 'derived-command-v1' or rule is None
                or provenance['profile_sha256'] != digest(ROOT / profile_path(config['document_profile']))):
            raise ValueError('Derived command is not bound to its closed document profile')
        fields(rule, ('donor_source', 'remove', 'append'), 'profile derived command rule')
        fields(provenance['source_replacement'], ('before', 'after'), 'derived source replacement')
        if (Path(source).name != rule['donor_source']
                or provenance['source_replacement'] != {'before': source, 'after': obj['source']}
                or provenance['remove'] != rule['remove'] or provenance['append'] != rule['append']):
            raise ValueError('Derived command donor/source/local deltas differ from profile')
        for token in provenance['remove']:
            if arguments.count(token) != 1:
                raise ValueError('Derived removal must identify one exact donor argument')
            arguments.remove(token)
        arguments.extend(provenance['append'])
    if arguments != obj['arguments']:
        raise ValueError('Selected compile argv differs from its original or bounded derived provenance')
    return identity


def _current_context(obj, inspection):
    context = obj['compile_context']
    fields(context, ('source', 'headers', 'macros', 'generated_metadata',
                     'sdk_manifest_sha256', 'arguments'), 'selected compile context')
    metadata = inspection.proof['metadata']
    if (context['source'] != obj['source'] or context['headers'] != obj['dependencies'] + obj['unified_members']
            or context['arguments'] != obj['arguments'] or context['macros'] != _macros(obj['arguments'])
            or context['sdk_manifest_sha256'] != inspection.selection['sdk_manifest_sha256']
            or context['generated_metadata'] != [metadata[key] for key in sorted(metadata)]):
        raise ValueError('Selected source/header/macro/generated metadata/SDK/argv closure differs')


def _physical_postimage(before, after, originals, projected):
    """Join original physical bytes independently of a logical recipe predecessor."""
    old = originals.get(before['path'], {})
    selected = projected.get(after['path'], {})
    if (before.get('root') != 'reuse' or after.get('root') != 'sources'
            or old.get('sha256') != before['sha256']
            or selected.get('sha256') != after['sha256']):
        raise ValueError('Postimage does not bind its original physical input and selected successor')


def _header_identity(inspection):
    """A document successor of original physical identity, with explicit postimages.

    The copy receipt proves all original identity classes. COPY-SET supplies the
    chosen canonical path. Every changed canonical and alias path has its own
    exact preimage -> inventoried projected postimage record.
    """
    reference = inspection.proof['header_identity']
    if reference is None:
        raise ValueError('Document maintenance requires complete original physical identity authority')
    if reference.get('root') not in ('sources', 'reuse'):
        raise ValueError('Header identity sidecar must be a retained source/reuse input')
    resolve = lambda ref: ref_path(ref, inspection.roots, inspection.inventories)
    sidecar_path = resolve(reference)
    record = checked_document(sidecar_path, reference['sha256'])
    fields(record, ('schema_version', 'kind', 'projection_sha256', 'evidence', 'classes',
                    'postimages'), 'document header identity')
    if (type(record['schema_version']) is not int or record['schema_version'] != 1
            or record['kind'] != 'foundation-document-v2-header-identity-v1'
            or record['projection_sha256'] != inspection.selection['projection_sha256']):
        raise ValueError('Unknown document header identity contract')
    fields(record['evidence'], ('discovery', 'copy_set', 'copy_receipt'), 'original physical identity authority')
    authority_paths = {key: resolve(ref) for key, ref in record['evidence'].items()}
    receipt = checked_document(authority_paths['copy_receipt'], record['evidence']['copy_receipt']['sha256'])
    copy_set = checked_document(authority_paths['copy_set'], record['evidence']['copy_set']['sha256'])
    if (type(receipt) is not dict or type(receipt.get('schema_version')) is not int
            or receipt['schema_version'] != 1 or receipt.get('kind') != 'closed-unpublished-baseline-copy-v1'
            or receipt.get('status') != 'closed-exact-readback-passed-unpublished'
            or type(receipt.get('files')) is not dict or not receipt['files']
            or type(copy_set) is not dict or copy_set.get('kind') != 'foundation-original-baseline-prospective-copy-set-v1'
            or type(copy_set.get('entries')) is not list):
        raise ValueError('Invalid original copy receipt or canonical-path authority')
    entries = {}
    for entry in copy_set['entries']:
        name = manifest.path_name(entry['destination'])
        if name in entries:
            raise ValueError('Duplicate original copy destination')
        entries[name] = entry
    originals = {}
    for name, item in receipt['files'].items():
        manifest.path_name(name)
        identity = item.get('source_identity') if type(item) is dict else None
        if (type(item) is dict and 'source_identity' in item and identity is None
                and name == 'provenance/original-command-ledger.json'):
            sha(item.get('sha256'), 'generated original command ledger')
            if type(item.get('bytes')) is not int or item['bytes'] < 1:
                raise ValueError('Invalid generated original command ledger byte count')
            continue  # Generated metadata has no original physical identity.
        if (type(identity) is not list or len(identity) != 7
                or any(type(part) is not int or part < 0 for part in identity)
                or not stat.S_ISREG(identity[2]) or identity[3] < 1
                or type(item.get('bytes')) is not int or item['bytes'] != identity[4]):
            raise ValueError('Invalid original copied-file physical identity')
        sha(item.get('sha256'), 'copied preimage')
        originals.setdefault(tuple(identity), set()).add(name)
    multiple = {identity: names for identity, names in originals.items() if len(names) > 1}
    if type(record['postimages']) is not list or type(record['classes']) is not list:
        raise ValueError('Expected explicit document physical classes and postimages')
    postimages, dependencies = {}, [sidecar_path, *authority_paths.values()]
    for item in record['postimages']:
        fields(item, ('input', 'output'), 'physical path postimage')
        before, after = item['input'], item['output']
        if before.get('root') != 'reuse' or after.get('root') != 'sources':
            raise ValueError('Postimages require an original copied path and selected source path')
        dependencies.extend((resolve(before), resolve(after)))
        _physical_postimage(before, after, receipt['files'], inspection.projection['files'])
        if ('reuse', before['path']) in postimages:
            raise ValueError('Duplicate original physical postimage path')
        postimages['reuse', before['path']] = after
    mappings, identities, seen, changed_groups = {}, set(), set(), []
    for group in record['classes']:
        fields(group, ('original_identity', 'canonical', 'aliases'), 'document physical class')
        identity = tuple(group['original_identity'])
        if identity in identities or identity not in multiple:
            raise ValueError('Duplicate or unproven original physical class')
        identities.add(identity)
        canonical = group['canonical']
        if type(group['aliases']) is not list or not group['aliases']:
            raise ValueError('Original physical class requires explicit aliases')
        refs = [canonical, *group['aliases']]
        if len({ref.get('sha256') for ref in refs}) != 1:
            raise ValueError('Original physical aliases must retain identical preimage bytes')
        names = set()
        for ref in refs:
            path = resolve(ref); dependencies.append(path)
            old = receipt['files'].get(ref['path'], {})
            entry = entries.get(ref['path'], {})
            if (ref['root'] != 'reuse' or ref['path'] in seen
                    or old.get('source_identity') != list(identity) or old.get('sha256') != ref['sha256']
                    or old.get('bytes') != path.stat().st_size
                    or entry.get('expected_resolved_path') != canonical['path']
                    or entry.get('sha256') != ref['sha256']):
                raise ValueError('Physical class differs from exact original receipt/canonical authority')
            seen.add(ref['path']); names.add(ref['path'])
        if names != multiple[identity]:
            raise ValueError('Physical class omits an original alias path')
        selected = [postimages.get(('reuse', ref['path'])) for ref in refs]
        if any(selected):
            if not all(selected) or len({ref['sha256'] for ref in selected}) != 1:
                raise ValueError('A changed physical class requires every canonical/alias postimage')
            target = resolve(selected[0])
            selected_paths = sorted({ref['path'] for ref in selected})
            if len(selected_paths) > 1:
                changed_groups.append({'canonical': selected[0]['path'], 'paths': selected_paths,
                    'preimages': {ref['path']: inspection.projection['files'][ref['path']]['preimage_sha256']
                                  for ref in selected},
                    'postimages': {ref['path']: ref['sha256'] for ref in selected}})
            for ref in refs:
                mappings[str(resolve(ref))] = str(target)
            for ref in selected[1:]:
                alias_path = resolve(ref)
                if alias_path != target:
                    mappings[str(alias_path)] = str(target)
        else:
            target = resolve(canonical)
            for ref in group['aliases']:
                mappings[str(resolve(ref))] = str(target)
    if identities != set(multiple):
        raise ValueError('Physical identity record omits original alias classes')
    if sorted(changed_groups, key=lambda item: item['canonical']) != sorted(
            inspection.projection['physical_alias_groups'], key=lambda item: item['canonical']):
        raise ValueError('Projected physical alias groups differ from original proven classes')
    for key, ref in postimages.items():
        if key[1] not in seen:
            mappings[str(inspection.roots['reuse'] / key[1])] = str(resolve(ref))
    source_aliases = _source_aliases(inspection)
    for name, target in source_aliases['mappings'].items():
        if name in mappings and mappings[name] != target:
            raise ValueError('Declared source aliases conflict with historical physical identity')
        mappings[name] = target
    dependencies.extend(source_aliases['dependencies'])
    overlay = {'version': 0, 'case-sensitive': True, 'use-external-names': False,
        'overlay-relative': False, 'fallthrough': True,
        'roots': [{'type': 'file', 'name': name, 'external-contents': target}
                  for name, target in sorted(mappings.items())]}
    return {'overlay': overlay, 'dependencies': dependencies, 'record_ref': reference,
            'mapping_count': len(mappings), 'postimages': postimages,
            'original_files': receipt['files']}


def _source_aliases(inspection):
    """Intentional new layout aliases, with no historical inode claim."""
    groups = inspection.projection['declared_source_aliases']
    if document_contract.canonical_json(groups) != document_contract.canonical_json(inspection.profile['declared_source_aliases']):
        raise ValueError('Declared source aliases differ from the explicit maintained layout')
    _validate_alias_groups(groups, inspection.projection['files'])
    mappings, dependencies = {}, []
    for group in groups:
        canonical = inspection.roots['sources'] / group['canonical']
        for name in group['paths']:
            path = inspection.roots['sources'] / name
            checked_read(path, group['postimages'][name])
            dependencies.append(path)
            if path != canonical:
                mappings[str(path)] = str(canonical)
    return {'mappings': mappings, 'dependencies': dependencies}


def _owner_postimages(obj, inspection, header_view):
    for name in inspection.profile['owner_postimages'][obj['id']]:
        expected = {'root': 'sources', 'path': name,
            'sha256': inspection.projection['files'][name]['sha256']}
        if expected not in [obj['source'], *obj['unified_members']]:
            raise ValueError('Engine owner omits an exact projected source postimage')
        if expected != obj['source'] and expected not in header_view['postimages'].values():
            raise ValueError('Unified owner postimage lacks an explicit original physical path mapping')


def _opaque_baseline(value, inspection, resolve):
    """Retain trusted compiled artifacts without inventing historical source data."""
    fields(value, ('kind', 'predecessor_proof', 'original_receipt', 'target',
        'paired_sdk_sha256', 'members'), 'opaque baseline authority')
    reference = value['predecessor_proof']
    fields(reference, REFERENCE_FIELDS, 'opaque predecessor proof')
    if (value['kind'] != OPAQUE_BASELINE_KIND or reference['root'] != 'reuse'
            or reference['sha256'] != OPAQUE_BASELINE_PROOF_SHA256):
        raise ValueError('Opaque reuse requires the explicitly admitted predecessor proof')
    predecessor = checked_document(resolve(reference), reference['sha256'])
    proof = inspection.proof
    if (predecessor.get('schema_version') != 1
            or predecessor.get('kind') != 'foundation-copied259-baseline-reuse-v1'
            or value['target'] != predecessor.get('target')
            or value['target'] != inspection.recipe['target']
            or value['paired_sdk_sha256'] != predecessor.get('paired_sdk_sha256')
            or value['paired_sdk_sha256'] != inspection.selection['sdk_manifest_sha256']
            or value['original_receipt'] != predecessor.get('baseline', {}).get('original_receipt')
            or value['original_receipt'] != proof['baseline']['original_receipt']
            or proof['archives'] != predecessor.get('archives')):
        raise ValueError('Opaque archive authority differs from the original target/SDK/receipt/layout')
    # The old receipt's limitations remain intact. This is a source-only reuse
    # decision, never new neutral-provider runtime or eligibility evidence.
    for key, old in predecessor['baseline'].items():
        if proof['baseline'].get(key) != old:
            raise ValueError('Opaque reuse cannot relabel the original baseline scope')
    resolve(value['original_receipt'])
    replaced = {(item['archive'], item['ordinal']) for item in proof['replacements']}
    expected = [{'archive': archive['name'], **member}
                for archive in proof['archives'] for member in archive['members']
                if (archive['name'], member['ordinal']) not in replaced]
    if type(value['members']) is not list or value['members'] != expected:
        raise ValueError('Opaque members differ from exact ordered original nonreplacement tuples')
    return {name: predecessor['inventory']['files'][name]
            for name in OPAQUE_BASELINE_METADATA_NAMES}


def _compile_contexts(value, commands, inspection, resolve, header_view):
    if type(value) is not dict:
        raise ValueError('Expected an explicit compile-context authority object')
    selected = value.get('kind') == SELECTED_CONTEXT_KIND
    fields(value, ('schema_version', 'kind', 'contexts', 'search_closures')
        + (('opaque_baseline',) if selected else ()), 'original compile contexts')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] not in (SELECTED_CONTEXT_KIND, 'foundation-engine-original-compile-contexts-v1')
            or type(value['contexts']) is not dict or type(value['search_closures']) is not dict):
        raise ValueError('Select an explicit complete or selected-and-opaque context authority')
    required = set(commands)
    if selected:
        engine = inspection.profile['engine_objects']
        owners = [obj for obj in inspection.proof['objects'] if obj.get('id') in engine]
        if [obj['id'] for obj in owners] != engine:
            raise ValueError('Selected context authority requires every exact engine owner')
        required = {_object_provenance(obj, commands, inspection) for obj in owners}
        if len(required) != len(engine):
            raise ValueError('Selected engine owners require distinct original command identities')
        metadata = _opaque_baseline(value['opaque_baseline'], inspection, resolve)
        header_view = dict(header_view or {}, opaque_baseline_metadata=metadata)
    if set(value['contexts']) != required:
        raise ValueError('Explicit context authority omits or adds required original commands')
    validated = set()
    for identity, context in value['contexts'].items():
        _context_record(context, commands[identity], inspection, resolve,
            header_view, value['search_closures'], validated)
    if set(value['search_closures']) != validated:
        raise ValueError('Shared include-search table contains unused or unverified closures')
    return selected


def _validate_proof(inspection):
    p, config = inspection.proof, inspection.profile
    roots, inventories = inspection.roots, inspection.inventories
    resolve = lambda ref: ref_path(ref, roots, inventories)
    header_view = _header_identity(inspection)
    fields(p['baseline'], ('origin', 'original_receipt', 'source_identity',
           'configuration_identity', 'recorded_scopes', 'command_records', 'original_root',
           'original_bindings', 'compile_contexts'), 'original baseline')
    for name in ('origin', 'source_identity', 'configuration_identity'):
        manifest.text(p['baseline'][name], 'baseline ' + name)
    if not p['baseline']['recorded_scopes'] or type(p['recovery_limits']) is not list:
        raise ValueError('State original baseline scopes and recovery limits')
    resolve(p['baseline']['original_receipt'])
    original_root = Path(p['baseline']['original_root'])
    if not original_root.is_absolute() or '..' in original_root.parts:
        raise ValueError('Original baseline root must be an explicit lexical absolute path')
    fields(p['baseline']['original_bindings'], ('sources', 'sdk', 'reuse'), 'original root bindings')
    prefixes = [Path(value) for value in p['baseline']['original_bindings'].values()]
    if (any(not path.is_absolute() or '..' in path.parts for path in prefixes)
            or len(set(prefixes)) != 3
            or any(a != b and (a in b.parents or b in a.parents) for a in prefixes for b in prefixes)
            or p['baseline']['original_bindings']['reuse'] != str(original_root)):
        raise ValueError('Original root bindings must be explicit disjoint original source/SDK/build roots')
    commands = checked_document(resolve(p['baseline']['command_records']))
    fields(commands, ('schema_version', 'kind', 'commands'), 'original command records')
    if (commands['schema_version'] != 1 or commands['kind'] != 'foundation-engine-original-commands-v1'
            or type(commands['commands']) is not dict or not commands['commands']):
        raise ValueError('Retain original compile argv/cwd records')
    for identity, record in commands['commands'].items():
        fields(record, ('argv', 'cwd'), 'original compile command')
        if (type(record['argv']) is not list or not record['argv']
                or any(type(arg) is not str for arg in record['argv'])
                or type(record['cwd']) is not str or not Path(record['cwd']).is_absolute()
                or hashlib.sha256(encoded(record)).hexdigest() != identity):
            raise ValueError('Original command hash does not bind retained exact argv/cwd bytes')
    contexts = checked_document(resolve(p['baseline']['compile_contexts']))
    selected_contexts = _compile_contexts(contexts, commands['commands'], inspection, resolve, header_view)
    fields(p['host_tools'], ('cmake', 'ninja', 'python'), 'host tools')
    for tool in p['host_tools'].values():
        _tool(tool)
    if re.search(r'\s', p['host_tools']['python']['path']):
        raise ValueError('Pinned Python path cannot contain whitespace in launcher shebang')
    fields(p['sdk_tools'], ('emxx', 'emar', 'emranlib'), 'SDK tools')
    required_paths = {'emxx': 'upstream/emscripten/em++',
                      'emar': 'upstream/emscripten/emar',
                      'emranlib': 'upstream/emscripten/emranlib'}
    for name, tool in p['sdk_tools'].items():
        if tool['path'] != required_paths[name]:
            raise ValueError('Use the direct paired SDK driver, not a cache-resetting wrapper')
        _tool(tool, sdk_root=roots['sdk'], sdk_files=inventories['sdk'])
    validate_python_contract(p['python_launch'], roots['sdk'], inventories['sdk'])
    objects = p['objects']
    expected = config['direct_objects'] + config['engine_objects']
    if type(objects) is not list or [o.get('id') for o in objects] != expected:
        raise ValueError('Expected the exact ordered direct and archive-owner document recipes')
    for obj in objects:
        fields(obj, ('id', 'source', 'arguments', 'dependencies', 'provenance',
                    'unified_members', 'exceptions', 'compile_context'), 'object recipe')
        source = resolve(obj['source'])
        if (obj['source']['root'] != 'sources'
                or inspection.projection['files'].get(obj['source']['path'], {}).get('sha256') != obj['source']['sha256']):
            raise ValueError('Every selected owner TU must belong to the explicit final-source projection')
        if (obj['source']['path'] != config['source_bindings'][obj['id']]
                or '/spike/' in source.as_posix() or source.name == 'BibEngineProviderBinding.cpp'):
            raise ValueError('Unselected or mismatched object source')
        _object_provenance(obj, commands['commands'], inspection)
        _current_context(obj, inspection)
        _arguments(obj['arguments'], inspection=inspection)
        if type(obj['exceptions']) is not bool or _exception_policy(obj['arguments']) != obj['exceptions']:
            raise ValueError('Object exception policy differs from exact argv')
        if obj['id'] in config['engine_objects'] and (obj['exceptions'] or '-fno-exceptions' not in obj['arguments']):
            raise ValueError('Engine owner must retain original no-exceptions policy')
        if type(obj['dependencies']) is not list or not obj['dependencies']:
            raise ValueError('Every object requires its complete pinned header/config/source closure')
        for ref in obj['dependencies'] + obj['unified_members']:
            resolve(ref)
        if obj['id'].startswith('UnifiedSource-') and not obj['unified_members']:
            raise ValueError('Engine unified owners require the exact ordered sibling closure')
        if obj['id'] in config['engine_objects']:
            _owner_postimages(obj, inspection, header_view)
    if [obj['id'] for obj in objects if obj['exceptions']] != config['exceptions']:
        raise ValueError('Document exception policy differs from the closed ordered profile')
    archives = p['archives']
    if type(archives) is not list or [a.get('name') for a in archives] != list(config['archive_members']):
        raise ValueError('Expected the five fixed baseline archive boundaries')
    for archive in archives:
        fields(archive, ('name', 'input', 'members'), 'baseline archive')
        path = resolve(archive['input'])
        if checked_read(path)[:8] != b'!<thin>\n':
            raise ValueError('Original baseline archive must be the declared thin format')
        observed_members = read_thin_archive(path)
        members = archive['members']
        if len(members) != config['archive_members'][archive['name']]:
            raise ValueError('Original archive member count differs')
        names = set()
        for ordinal, member in enumerate(members):
            fields(member, ('ordinal', 'name', 'input', 'bytes', 'compile_command_sha256'), 'archive member')
            if type(member['name']) is not str or not member['name'] or '\x00' in member['name']:
                raise ValueError('Invalid thin archive member name')
            if type(member['ordinal']) is not int or member['ordinal'] != ordinal or member['name'] in names:
                raise ValueError('Duplicate/reordered archive member')
            names.add(member['name'])
            source = resolve(member['input'])
            observed = observed_members[ordinal] if ordinal < len(observed_members) else None
            if observed != {'name': member['name'], 'bytes': member['bytes']}:
                raise ValueError('Actual thin archive table order/name/size differs')
            referenced = (path.parent / member['name']).resolve(strict=True)
            if referenced != source or roots['reuse'] not in referenced.parents:
                raise ValueError('Actual thin member reference does not resolve to its retained object')
            if type(member['bytes']) is not int or source.stat().st_size != member['bytes']:
                raise ValueError('Retained member size differs')
            sha(member['compile_command_sha256'], 'member compile command')
            if member['compile_command_sha256'] not in commands['commands']:
                raise ValueError('Member original command is absent from retained records')
            original_output, original_source = _original_output(commands['commands'][member['compile_command_sha256']],
                original_root, roots['reuse'])
            if original_output != source:
                raise ValueError('Original compile output does not identify the claimed retained member')
        if len(observed_members) != len(members) or len({Path(m['input']['path']).name for m in members}) != len(members):
            raise ValueError('Actual baseline membership/basename closure differs')
    replacements = p['replacements']
    if type(replacements) is not list or len(replacements) != len(config['engine_objects']):
        raise ValueError('Every selected engine owner requires exactly one ordinal substitution')
    expected_owners = set(config['engine_objects'])
    seen = set()
    by_name = {a['name']: a for a in archives}
    for item in replacements:
        fields(item, ('archive', 'ordinal', 'object_id', 'old_sha256'), 'member replacement')
        key = (item['archive'], item['ordinal'])
        if key in seen or item['object_id'] not in expected_owners:
            raise ValueError('Duplicate or unexpected owner substitution')
        seen.add(key); expected_owners.remove(item['object_id'])
        if item['archive'] not in ('WebCore', 'WTF') or type(item['ordinal']) is not int:
            raise ValueError('Invalid owner archive/ordinal')
        try:
            old = by_name[item['archive']]['members'][item['ordinal']]
        except (IndexError, KeyError):
            raise ValueError('Replacement ordinal is absent') from None
        if item['ordinal'] < 0 or old['input']['sha256'] != item['old_sha256']:
            raise ValueError('Replacement preimage differs')
        expected_archive = 'WTF' if item['object_id'] == 'RunLoopGeneric.cpp' else 'WebCore'
        replacement_obj = next(obj for obj in objects if obj['id'] == item['object_id'])
        old_record = commands['commands'][old['compile_command_sha256']]
        _, old_source = _original_output(old_record, original_root, roots['reuse'])
        if (item['archive'] != expected_archive or Path(old['input']['path']).name != item['object_id'] + '.o'
                or old_source != item['object_id']
                or _object_provenance(replacement_obj, commands['commands'], inspection) != old['compile_command_sha256']):
            raise ValueError('Replacement does not remove its actual original owner member')
    replaced = {(item['archive'], item['ordinal']) for item in replacements}
    for archive in archives:
        for member in archive['members']:
            if not selected_contexts and (archive['name'], member['ordinal']) not in replaced:
                identity = member['compile_command_sha256']
                _reusable_context(contexts['contexts'][identity], commands['commands'][identity], inspection,
                    header_view['postimages'] if header_view else {})
    link = p['link']
    fields(link, ('flags', 'archives', 'dependencies', 'pre_js', 'host_library', 'data'), 'final link')
    _arguments(link['flags'], link=True, inspection=inspection)
    if _exception_policy(link['flags']) is not True:
        raise ValueError('Final link must retain effective exceptions after inherited baseline flags')
    if link['archives'] != config['link_archive_names']:
        raise ValueError('Literal 27-occurrence archive order differs')
    dependencies = link['dependencies']
    if len(dependencies) != 21 or len({ref['path'] for ref in dependencies}) != 21:
        raise ValueError('Exactly 21 unique dependency archives are required')
    if {Path(ref['path']).name for ref in dependencies} != set(link['archives']) - set(config['archive_members']):
        raise ValueError('Dependency archive names differ')
    for ref in dependencies + [link['pre_js'], link['host_library']]:
        resolve(ref)
    if len(link['data']) != 32:
        raise ValueError('The complete selected 32-file ICU/font/config closure is required')
    for item in link['data']:
        fields(item, ('input', 'virtual_path'), 'embedded engine data')
        resolve(item['input'])
        if type(item['virtual_path']) is not str or not item['virtual_path'].startswith('/') or '@' in item['virtual_path']:
            raise ValueError('Engine data requires an exact original virtual filename')
    metadata_names = ('generator', 'template', 'prelink_plan', 'contract_header',
        'document_header', 'document_contract', 'document_catalog', 'document_schema', 'action_ack')
    if config['document_profile'] in ('physical', 'editor'):
        metadata_names += ('physical_catalog',)
    if config['document_profile'] == 'editor':
        metadata_names += ('editor_header', 'editor_contract', 'editor_catalog', 'editor_schema')
    fields(p['metadata'], metadata_names, 'document metadata inputs')
    if p['metadata']['generator']['path'] != config['metadata_generator']:
        raise ValueError('Use the retained real document metadata generator')
    if p['metadata']['template']['path'] != 'source/document-provider/runtime/engine-document-copied-metadata.h.in':
        raise ValueError('Use the exact retained adjacent document metadata template')
    for key, local in (('generator', 'generate_document_metadata.py'),
                       ('template', 'engine-document-copied-metadata.h.in')):
        if p['metadata'][key]['sha256'] != digest(ROOT / 'recipes/webkitwasm-document-v2/runtime' / local):
            raise ValueError('Document metadata producer differs from the maintained successor: ' + key)
    interface_paths = metadata_interface_paths(config['document_profile'])
    for key, (path, pin) in interface_paths.items():
        if p['metadata'][key] != {'root': 'sources', 'path': path, 'sha256': pin}:
            raise ValueError('Document metadata interface path/identity differs: ' + key)
    for ref in p['metadata'].values():
        resolve(ref)
    fields(p['private_cache'], ('root', 'files'), 'private cache seed')
    cache_prefix = manifest.path_name(p['private_cache']['root']) + '/'
    if not p['private_cache']['files']:
        raise ValueError('Frozen prepopulated private cache is required')
    for name in p['private_cache']['files']:
        manifest.path_name(name)
        if name not in inventories['sdk'] or not name.startswith(cache_prefix):
            raise ValueError('Private cache seed is not an inventoried SDK cache member')
    fields(p['emscripten_config'], ('LLVM_ROOT', 'BINARYEN_ROOT', 'NODE_JS'), 'private SDK configuration')
    for key, name in p['emscripten_config'].items():
        path = roots['sdk'] / manifest.path_name(name)
        ordinary(path, directory=key != 'NODE_JS', sdk=True)
        if key == 'NODE_JS' and name not in inventories['sdk']:
            raise ValueError('Node must be an exact paired SDK input')


def validate_python_contract(value, sdk_root, files):
    fields(value, ('config', 'shared', 'file_packager', 'emxx'), 'Python launcher contract')
    expected = {'config': ('upstream/emscripten/tools/config.py', b"os.environ['EMSDK_PYTHON'] = sys.executable"),
        'shared': ('upstream/emscripten/tools/shared.py', b"FILE_PACKAGER = exe_path_from_root('tools/file_packager')"),
        'file_packager': ('upstream/emscripten/tools/file_packager', b'exec "$_EM_PY" -E "$0.py" "$@"'),
        'emxx': ('upstream/emscripten/em++', b'exec "$_EM_PY" -B -E "$0.py" "$@"')}
    for key, (name, marker) in expected.items():
        fields(value[key], ('path', 'sha256'), 'pinned SDK launcher source')
        if value[key]['path'] != name or files.get(name) != value[key]['sha256']:
            raise ValueError('Unsupported SDK launcher source binding')
        if marker not in checked_read(sdk_root / name, value[key]['sha256'], sdk=True):
            raise ValueError('SDK launcher semantics need explicit maintenance: ' + name)


RESUME_PLAN_KIND = 'foundation-document-v2-maintenance-resume-plan-v1'
RESUME_BUILD_KIND = 'foundation-document-v2-maintenance-resume-build-v1'
COMPLETED_KIND = 'foundation-document-v2-completed-work-v1'
COMPLETED_DEPS_KIND = 'foundation-document-v2-completed-dependencies-v1'
SUCCESSFUL_PLAN_KIND = 'foundation-document-v2-maintenance-successful-donor-plan-v1'
SUCCESSFUL_BUILD_KIND = 'foundation-document-v2-maintenance-successful-donor-build-v1'
SUCCESSFUL_HELPER = 'tools/appended_engine_successful_donor.py'


def _successful_module():
    import appended_engine_successful_donor
    return appended_engine_successful_donor


def _work(plan):
    return plan.get('completed_work') or plan.get('successful_donor')
COMPLETED_DIRECT = frozenset(('AppResourceQueue.cpp', 'BibAppResourceProfile.cpp',
    'BibAppResources.cpp', 'BibClipboardStore.cpp', 'BibCopiedDocumentBinding.cpp',
    'BibEngineCopiedDocumentDispatch.cpp', 'BibEngineCopiedHost.cpp',
    'BibEngineCopiedRecord.cpp', 'BibEngineProviderPreflight.cpp'))


def _identity7(state):
    return [state.st_dev, state.st_ino, state.st_mode, state.st_nlink,
            state.st_size, state.st_mtime_ns, state.st_ctime_ns]


def _completed_fact(value, *, sdk=False):
    fields(value, ('path', 'sha256', 'bytes', 'mode', 'identity'), 'completed-work file fact')
    path = ordinary(value['path'], sdk=sdk)
    before = path.stat()
    if (type(value['bytes']) is not int or value['bytes'] < 0
            or type(value['mode']) is not int or not 0 <= value['mode'] <= 0o777
            or type(value['identity']) is not list or len(value['identity']) != 7
            or any(type(item) is not int for item in value['identity'])
            or _identity7(before) != value['identity'] or before.st_size != value['bytes']
            or stat.S_IMODE(before.st_mode) != value['mode']):
        raise ValueError('Completed-work physical identity/mode/length differs')
    raw = checked_read(path, value['sha256'], sdk=sdk)
    if _identity7(path.stat()) != value['identity']:
        raise ValueError('Completed-work identity changed while hashing')
    return raw


def _completed_reference(value):
    fields(value, ('path', 'sha256'), 'completed-work metadata reference')
    return checked_document(ordinary(value['path']), sha(value['sha256'], 'completed-work metadata'))


def _completed_binding(value):
    fields(value, ('sources', 'sdk', 'reuse', 'build'), 'completed-work original bindings')
    paths = {key: Path(name) for key, name in value.items()}
    if (any(not item.is_absolute() or '..' in item.parts for item in paths.values())
            or len(set(paths.values())) != 4
            or any(a != b and (a in b.parents or b in a.parents)
                   for a in paths.values() for b in paths.values())):
        raise ValueError('Completed-work roots must be exact disjoint absolute paths')
    return paths


def _completed_arguments(argv, cwd, bindings):
    if (type(argv) is not list or any(type(arg) is not str for arg in argv)
            or any(argv.count(flag) != 1 for flag in ('-c', '-o', '-MT', '-MF', '-MD'))
            or any(flag in argv for flag in ('-MMD', '-MP', '-MQ')) or argv.count('-ivfsoverlay') != 1):
        raise ValueError('Completed command must retain exact compiler/dependency/VFS operands')
    roots = {key: str(value) for key, value in bindings.items() if key != 'build'}
    roots['generated'] = str(bindings['build'] / 'document-generated')
    if _relocate_original(argv[0], cwd, roots) != '{sdk}/upstream/emscripten/em++':
        raise ValueError('Completed work used another compiler')
    overlay = argv.index('-ivfsoverlay')
    if overlay + 1 >= len(argv) or argv[overlay + 1] != str(bindings['build'] / 'private/header-identity-vfs.json'):
        raise ValueError('Completed command used another header VFS')
    current = list(argv)
    del current[overlay:overlay + 2]
    return _original_arguments({'argv': current, 'cwd': cwd}, roots)


def _completed_header_context(inspection, dependency_refs, objects):
    """Complete search names/non-TU bytes, original physical headers and VFS."""
    view = _header_identity(inspection)
    if view is None:
        raise ValueError('Completed work needs actual original header identity authority')
    translation_units = {'.c', '.cc', '.cpp', '.cxx', '.m', '.mm', '.s'}
    physical = {name: item for name, item in view['original_files'].items()
                if Path(name).suffix.lower() not in translation_units | {'.o', '.a'}}
    directories = set()
    for obj in objects:
        directories.update(_include_directories(obj['arguments']))
    for reference in dependency_refs:
        directories.add('{' + reference['root'] + '}/' + str(Path(reference['path']).parent))
    # The paired driver defaults are inputs as well as the explicit -I operands.
    directories.update(('{sdk}/upstream/lib/clang/24/include',
        '{sdk}/' + inspection.proof['private_cache']['root'] + '/sysroot/include'))
    directories.discard('{generated}')  # Generated-dependent objects are explicitly ineligible.
    namespace = {}
    for operand in sorted(directories):
        match = re.fullmatch(r'\{(sources|sdk|reuse)\}(?:/(.+))?', operand)
        if match is None:
            raise ValueError('Completed search context has an unbound directory')
        root, suffix = match.groups()
        suffix = '' if suffix in (None, '.') else manifest.path_name(suffix)
        ordinary(inspection.roots[root] / suffix, directory=True, sdk=root == 'sdk')
        prefix = suffix + '/' if suffix else ''
        for name, pin in inspection.inventories[root].items():
            if name.startswith(prefix):
                namespace['{' + root + '}/' + name] = pin
    return {'directories': sorted(directories), 'namespace': namespace,
        'physical_headers_sha256': hashlib.sha256(encoded(physical)).hexdigest(),
        'vfs': _completed_normalize_vfs(view['overlay'], inspection.roots)}


def _completed_context_matches(old, current):
    fields(old, ('directories', 'namespace', 'physical_headers_sha256', 'vfs'), 'completed header context')
    if (old['directories'] != current['directories'] or set(old['namespace']) != set(current['namespace'])
            or old['physical_headers_sha256'] != current['physical_headers_sha256'] or old['vfs'] != current['vfs']):
        raise ValueError('Completed include namespace/physical-header/VFS context differs')
    units = {'.c', '.cc', '.cpp', '.cxx', '.m', '.mm', '.s'}
    for name, pin in old['namespace'].items():
        sha(pin, 'completed namespace input')
        # Changed unimported TUs are allowed; every imported actual dependency
        # (including unified .cpp siblings) is independently required unchanged.
        if Path(name).suffix.lower() not in units and current['namespace'][name] != pin:
            raise ValueError('Completed header/config input bytes differ')


def _successful_context_delta(inspection, old, previous, current):
    """The successful successor admits only the declared Publisher TU delta.

    The caller has already applied the complete legacy namespace/header/VFS
    guard. Every imported actual dependency remains independently byte exact;
    generated dependencies are never admitted for import.
    """
    prior = {row['id']: row for row in old['reuse']['objects']}
    successor = {row['id']: row for row in inspection.proof['objects']}
    publisher, shim = _successful_module().COMPILED_IDS
    before, after = prior[publisher], successor[publisher]
    source, replacement = before['source'], after['source']
    fields(source, REFERENCE_FIELDS, 'original Publisher source')
    fields(replacement, REFERENCE_FIELDS, 'successor Publisher source')
    if (source['root'] != 'sources' or replacement['root'] != source['root']
            or replacement['path'] != source['path']):
        raise ValueError('Successful donor changed Publisher logical source coordinates')
    for key in ('source', 'arguments', 'dependencies', 'unified_members', 'exceptions'):
        if prior[shim][key] != successor[shim][key]:
            raise ValueError('Successful donor changed Shim source/compiler/header inputs')
    if before['arguments'] != after['arguments'] or before['exceptions'] != after['exceptions']:
        raise ValueError('Successful donor changed Publisher compiler options')
    for key in ('dependencies', 'unified_members'):
        expected = [replacement if reference == source else reference for reference in before[key]]
        if after[key] != expected:
            raise ValueError('Successful donor changed Publisher included input context')
    operand = '{sources}/' + source['path']
    if (previous['namespace'].get(operand) != source['sha256']
            or current['namespace'].get(operand) != replacement['sha256']):
        raise ValueError('Successful donor Publisher lacks its exact namespace hash join')
    changed = {name for name, pin in previous['namespace'].items()
               if current['namespace'].get(name) != pin}
    if changed - {operand}:
        raise ValueError('Successful donor changed an undeclared namespace body')


def _completed_authority(value, bindings, old):
    """Join the actual named launch chain; failure records have no freeze field."""
    freeze = _completed_reference(value['original_input_freeze'])
    packet = _completed_reference(value['original_build_packet'])
    launch = _completed_reference(value['root_launch'])
    handle = _completed_reference(value['root_handle'])
    fields(old, ('schema_version', 'kind', 'scope', 'selection', 'profile_sha256',
        'producer_inputs', 'reuse', 'projection', 'production_eligible'), 'original default plan')
    fields(old['selection'], SELECTION_FIELDS, 'original default selection')
    plan_ref, freeze_ref = value['original_plan'], value['original_input_freeze']
    if (type(old['schema_version']) is not int or old['schema_version'] != 1
            or old['kind'] != PLAN_KIND or old['scope'] != SCOPE or old['production_eligible'] is not False
            or old['profile_sha256'] != digest(ROOT / profile_path('editor'))
            or packet.get('schema_version') != 1 or packet.get('kind') != 'editor-rich-ui-build-launch-v1'
            or packet.get('authorization_status') != 'root-reviewed-concrete-launch'
            or packet.get('freeze') != freeze_ref['path'] or packet.get('freeze_sha256') != freeze_ref['sha256']
            or packet.get('plan') != plan_ref['path'] or packet.get('plan_sha256') != plan_ref['sha256']
            or packet.get('selection') != old['selection'] or packet.get('producer_inputs') != old['producer_inputs']
            or packet.get('profile_sha256') != old['profile_sha256']
            or packet.get('output') != str(bindings['build'])
            or packet.get('review') != str(Path(value['candidate_result']['path']).parent)
            or packet.get('policy') != {'cold_fallback': False, 'header_odr_waiver': False,
                'production_eligible': False, 'runtime': False, 'timestamp_seeding': False}):
        raise ValueError('Completed original build packet/plan/freeze authority differs')
    argv = packet.get('argv', [])
    if (len(argv) != 13 or argv[:3] != ['./build.sh', 'engine-maintenance', 'document-build']
            or argv[3:9] != ['--plan', plan_ref['path'], '--plan-sha256', plan_ref['sha256'],
                             '--output', str(bindings['build'])]
            or argv[9] != '--jobs' or argv[11] != '--timeout-seconds'
            or not argv[10].isdecimal() or not argv[12].isdecimal()
            or int(argv[10]) < 1 or int(argv[12]) < 1):
        raise ValueError('Completed original packet command differs')
    if (launch.get('kind') != 'root-editor-incremental-build-launch-intent-v1'
            or launch.get('Root_owns_single_launch') is not True
            or launch.get('packet_sha256') != value['original_build_packet']['sha256']
            or launch.get('freeze_sha256') != freeze_ref['sha256']
            or launch.get('cold_fallback') is not False or launch.get('runtime') is not False
            or launch.get('cwd') != packet.get('cwd')
            or launch.get('environment_identity') != packet.get('environment_identity')
            or launch.get('jobs') != int(argv[10]) or launch.get('inner_seconds') != int(argv[12])
            or launch.get('argv', [])[-2:] != ['--packet-sha256', value['original_build_packet']['sha256']]
            or handle.get('kind') != 'root-observed-editor-incremental-build-handle-v1'
            or handle.get('Root_owns_handle_and_output_claim') is not True
            or handle.get('launch_intent_sha256') != value['root_launch']['sha256']
            or handle.get('packet_sha256') != value['original_build_packet']['sha256']
            or type(handle.get('actual_session')) is not int or handle['actual_session'] <= 0
            or Path(value['root_launch']['path']).parent != Path(value['root_failure']['path']).parent
            or Path(value['root_handle']['path']).parent != Path(value['root_failure']['path']).parent):
        raise ValueError('Completed original Root launch/handle authority differs')
    if (type(freeze.get('schema_version')) is not int or freeze['schema_version'] != 1
            or freeze.get('kind') != 'editor-rich-ui-input-freeze-v1'
            or freeze.get('actual_plan_or_build') is not False
            or freeze.get('roots') != {key: str(path) for key, path in bindings.items() if key != 'build'}
            or type(freeze.get('files')) is not dict or type(freeze.get('directories')) is not dict
            or freeze['files'].get(plan_ref['path'], {}).get('sha256') != plan_ref['sha256']):
        raise ValueError('Completed original full input freeze differs')
    for key, field in (('recipe_sha256', 'recipe.json'), ('sources_sha256', 'sources.json')):
        if freeze['files'].get(str(bindings['sources'] / field), {}).get('sha256') != old['selection'][key]:
            raise ValueError('Original plan source identity lacks frozen authority')
    if freeze['files'].get(str(bindings['sdk'] / 'sdk.json'), {}).get('sha256') != old['selection']['sdk_manifest_sha256']:
        raise ValueError('Original plan SDK identity lacks frozen authority')
    for name, pin in old['producer_inputs'].items():
        if freeze['files'].get(str(bindings['sources'] / manifest.path_name(name)), {}).get('sha256') != pin:
            raise ValueError('Original plan producer lacks full frozen authority')
    expected = _completed_reference({'path': packet['expected_commands'], 'sha256': packet['expected_commands_sha256']})
    return freeze, packet, handle, expected


def _completed_ninja_hash(command):
    # Ninja 1.12.1 log-v6 HashCommand: MurmurHash64A, little-endian host.
    # https://github.com/ninja-build/ninja/blob/v1.12.1/src/build_log.cc
    raw = command.encode('utf-8'); mask = (1 << 64) - 1
    multiplier = 0xc6a4a7935bd1e995
    value = (0xDECAFBADDECAFBAD ^ (len(raw) * multiplier)) & mask
    index = 0
    while index + 8 <= len(raw):
        block = (int.from_bytes(raw[index:index + 8], 'little') * multiplier) & mask
        block ^= block >> 47
        block = (block * multiplier) & mask
        value = ((value ^ block) * multiplier) & mask
        index += 8
    if index != len(raw):
        value ^= int.from_bytes(raw[index:], 'little')
        value = (value * multiplier) & mask
    value ^= value >> 47
    value = (value * multiplier) & mask
    return format(value ^ (value >> 47), 'x')


def _completed_ninja_command(row, argv, bindings, tools):
    """Parse bounded raw text; no guessed quoting or large Ninja graph read.

    CMake v3.31.6 cmLocalNinjaGenerator.cxx supplies cd/command/transform
    lines, script name and content SHA suffix. cmCustomCommandGenerator.cxx
    supplies the fixed transform operands and SHA256-named internal depfile.
    """
    if tools['ninja']['version'] != '1.12.1' or tools['cmake']['version'] != 'cmake version 3.31.6':
        raise ValueError('Completed Ninja/CMake hash grammar needs explicit version qualification')
    build = bindings['build']; cwd = str(build / 'cmake/build')
    source = str(bindings['sources'] / Path(GRAPH_PATH).parent)
    target = argv[argv.index('-o') + 1]; depfile = argv[argv.index('-MF') + 1]
    transformed = str(build / ('cmake/build/CMakeFiles/d/' + hashlib.sha256(depfile.encode()).hexdigest() + '.d'))
    transform = [tools['cmake']['path'], '-E', 'cmake_transform_depfile', 'Ninja', 'gccdepfile',
                 source, source, cwd, cwd, depfile, transformed]
    def tokens(command):
        if (type(command) is not str or not 0 < len(command.encode('utf-8')) <= 256 * 1024
                or any(char in command for char in ('$', '`', '\x00', '\n', '\r', ';'))):
            raise ValueError('Unsupported completed shell command grammar')
        return shlex.split(command, posix=True)
    command = row['ninja_command']; script = row['command_script']
    if script is None:
        if tokens(command) != ['cd', cwd, '&&', *argv, '&&', *transform]:
            raise ValueError('Completed raw Ninja compiler command differs')
    else:
        script_path = build / ('cmake/build/CMakeFiles/' + Path(target).name + '-'
                               + hashlib.sha256(target.encode()).hexdigest()[:7] + '.sh')
        if script.get('path') != str(script_path) or script.get('bytes', 0) > 256 * 1024:
            raise ValueError('Completed command script path/limit differs')
        body = _completed_fact(script).decode('utf-8')
        lines = body.splitlines()
        if (not body.endswith('\n') or len(lines) != 5 or lines[:2] != ['set -e', '']
                or tokens(lines[2]) != ['cd', cwd] or tokens(lines[3]) != argv
                or tokens(lines[4]) != transform):
            raise ValueError('Completed CMake script compiler command differs')
        actual = tokens(command)
        if (len(actual) != 3 or actual[0] != '/bin/sh'
                or actual[1] not in (str(script_path), script_path.relative_to(build / 'cmake/build').as_posix())
                or actual[2] != script['sha256'][:16]):
            raise ValueError('Completed raw Ninja script command differs')
    return _completed_ninja_hash(command)


def _completed_normalize_vfs(value, bindings):
    fields(value, ('version', 'case-sensitive', 'use-external-names', 'overlay-relative',
                   'fallthrough', 'roots'), 'completed original VFS')
    if (type(value['version']) is not int or value['version'] != 0
            or value['case-sensitive'] is not True or value['use-external-names'] is not False
            or value['overlay-relative'] is not False or value['fallthrough'] is not True
            or type(value['roots']) is not list):
        raise ValueError('Completed VFS policy differs')
    roots = {key: str(path) for key, path in bindings.items() if key != 'build'}
    mappings = []
    for row in value['roots']:
        fields(row, ('type', 'name', 'external-contents'), 'completed VFS mapping')
        if row['type'] != 'file':
            raise ValueError('Completed VFS mapping must remain an exact file')
        mappings.append({'type': 'file', 'name': _relocate_original(row['name'], '/', roots),
            'external-contents': _relocate_original(row['external-contents'], '/', roots)})
    if len({row['name'] for row in mappings}) != len(mappings):
        raise ValueError('Duplicate completed VFS mapping')
    return dict(value, roots=sorted(mappings, key=lambda row: row['name']))


def _completed_frozen_namespace(freeze, bindings, directories):
    names = {}
    for operand in directories:
        match = re.fullmatch(r'\{(sources|sdk|reuse)\}(?:/(.+))?', operand)
        if match is None:
            raise ValueError('Unbound original include directory')
        key, suffix = match.groups(); path = bindings[key] / (suffix or '')
        if str(path) not in freeze['directories']:
            raise ValueError('Original include directory lacks frozen namespace authority')
        prefix = str(path) + '/'
        for name, fact in freeze['files'].items():
            if name.startswith(prefix):
                names['{' + key + '}/' + Path(name).relative_to(bindings[key]).as_posix()] = fact['sha256']
    return names


def _completed_private_context(value, bindings, old, freeze):
    fields(value, ('vfs', 'configuration', 'launcher'), 'completed private configuration facts')
    build = bindings['build']; proof = old['reuse']
    expected = {'vfs': build / 'private/header-identity-vfs.json',
                'configuration': build / 'private/emscripten-config.py', 'launcher': build / 'private/sdk-python'}
    if any(value[key]['path'] != str(path) for key, path in expected.items()):
        raise ValueError('Completed private configuration paths differ')
    config = ''.join(key + ' = ' + repr(str(bindings['sdk'] / name)) + '\n'
                    for key, name in proof['emscripten_config'].items())
    config += 'CACHE = ' + repr(str(build / 'private/cache')) + '\nFROZEN_CACHE = True\n'
    if _completed_fact(value['configuration']) != config.encode('utf-8'):
        raise ValueError('Completed original private compiler configuration differs')
    class Capture:
        def __str__(self): return str(expected['launcher'])
        def write_text(self, text, encoding): self.raw = text.encode(encoding)
        def chmod(self, mode): self.mode = mode
    capture = Capture()
    python_launcher(proof['host_tools']['python']['path'],
        [bindings['sdk'] / name for name in profile('editor')['python_entrypoints']], capture)
    if _completed_fact(value['launcher']) != capture.raw or value['launcher']['mode'] != capture.mode:
        raise ValueError('Completed original recursive Python launcher differs')
    helper = freeze['files'].get(str(bindings['sources'] / SELF_PATH))
    if helper is None or helper.get('sha256') != old['producer_inputs'][SELF_PATH]:
        raise ValueError('Original sanitized construction lacks frozen helper authority')
    original = ast.parse(_completed_fact(helper))
    current = ast.parse(checked_read(ROOT / SELF_PATH))
    names = {'child_environment', 'python_launcher', '_expand', '_header_identity'}
    def functions(tree):
        return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in names}
    if set(functions(original)) != names or functions(original) != functions(current):
        raise ValueError('Original sanitizer/launcher/relocation/VFS construction differs')
    return _completed_normalize_vfs(document(_completed_fact(value['vfs'])), bindings)


def _completed_shape(inspection, old, rows, *, successful=False):
    p, config = inspection.proof, inspection.profile
    selected = config['direct_objects'] + config['engine_objects']
    expected_archives = {'WebCore': 924, 'JavaScriptCore': 185, 'PAL': 24, 'WTF': 168, 'Skia': 775}
    if (len(selected) != 51 or len(set(selected)) != 51 or len(config['engine_objects']) != 16
            or len(config['direct_objects']) != 35 or 'BibEngineDocumentWasmShim.cpp' not in config['direct_objects']
            or [row['id'] for row in p['objects']] != selected
            or {row['name']: len(row['members']) for row in p['archives']} != expected_archives
            or len(p['archives']) != 5 or len(p['replacements']) != 16
            or len({(row['archive'], row['ordinal']) for row in p['replacements']}) != 16
            or {row['object_id'] for row in p['replacements']} != set(config['engine_objects'])
            or old['reuse']['archives'] != p['archives'] or old['reuse']['replacements'] != p['replacements']
            or sum(len(row['members']) for row in p['archives']) - len(p['replacements']) != 2060):
        raise ValueError('Resume must preserve exact51/five archives/16 replacements/2060 opaque order')
    if successful:
        compiled = set(_successful_module().COMPILED_IDS)
        wanted = [name for name in selected if name not in compiled]
        if (len(wanted) != 49 or len(compiled) != 2 or not compiled <= set(selected)
                or type(rows) is not list or any(type(row) is not dict for row in rows)
                or [row.get('id') for row in rows] != wanted):
            raise ValueError('Successful donor must import exact ordered49 and compile Publisher plus Shim')
        return selected
    allowed = COMPLETED_DIRECT | set(config['engine_objects'])
    if (type(rows) is not list or not 0 < len(rows) <= 25 or any(type(row) is not dict for row in rows)
            or len({row.get('id') for row in rows}) != len(rows)
            or any(row.get('id') not in allowed for row in rows)
            or [row.get('id') for row in rows] != [name for name in selected if name in {r.get('id') for r in rows}]):
        raise ValueError('Completed objects exceed or reorder the explicit25 eligible identities')
    return selected


def _completed_build_receipt(result, plan, output, commands):
    selected = [row['id'] for row in plan['reuse']['objects']]
    rows = result.get('objects')
    if (type(rows) is not list or any(type(row) is not dict for row in rows)
            or [row.get('id') for row in rows] != selected):
        raise ValueError('Resume receipt must contain the exact ordered selected object union')
    imported = {row['id']: row for row in plan['completed_work']['objects']}
    imported_ids = [name for name in selected if name in imported]
    compiled_ids = [name for name in selected if name not in imported]
    if (set(commands['objects']) != set(compiled_ids) or set(commands['imports']) != set(imported_ids)
            or set(compiled_ids) & set(imported_ids) or len(selected) != 51):
        raise ValueError('Resume accounting does not preserve the exact disjoint selected union')
    result['kind'] = RESUME_BUILD_KIND
    result['completed_work'] = plan['completed_work']['reference']
    result['accounting'] = {'selected': 51, 'imported': len(imported_ids), 'compiled': len(compiled_ids),
                            'imported_ids': imported_ids, 'compiled_ids': compiled_ids}
    for obj in result['objects']:
        obj['origin'] = 'imported' if obj['id'] in imported else 'compiled'
        if obj['id'] in imported:
            receipt = output / ('evidence/import-' + obj['id'] + '.json')
            value = checked_document(receipt)
            original = imported[obj['id']]
            if (value.get('kind') != 'foundation-document-v2-object-import-v1'
                    or value.get('production_eligible') is not False
                    or value.get('id') != obj['id'] or value.get('origin') != 'imported'
                    or value.get('compiler_invoked') is not False or value.get('hardlinked') is not False
                    or value.get('sha256') != obj['sha256'] or value.get('bytes') != obj['bytes']
                    or value.get('object') != original['object'] or value.get('original_depfile') != original['depfile']
                    or value.get('original_command_sha256') != original['command_sha256']
                    or value.get('original_argv') != original['original_argv']
                    or value.get('original_cwd') != original['original_cwd']
                    or value.get('ninja_record') != original['ninja_record']
                    or value.get('ninja_command') != original['ninja_command']
                    or value.get('command_script') != original['command_script']):
                raise ValueError('Resume imported receipt/readback differs')
            obj['import_receipt'] = {'path': str(receipt.relative_to(output)), 'sha256': digest(receipt)}


def _completed_work(reference, inspection, *, _successful=False):
    """No cache discovery or fallback: admit every explicit record or reject all."""
    selected_reference = dict(reference)
    value = _completed_reference(reference)
    extra = ('root_acceptance', 'passive_worker', 'passive_result', 'maintenance_build', 'archives') if _successful else ()
    fields(value, ('schema_version', 'kind', 'document_profile', 'original_bindings',
        'original_plan', 'original_commands', 'root_failure', 'candidate_result',
        'original_input_freeze', 'original_build_packet', 'root_launch', 'root_handle',
        'original_private', 'ninja_log', 'dependency_sidecar', 'objects') + extra, 'completed-work selection')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != (_successful_module().DONOR_KIND if _successful else COMPLETED_KIND) or value['document_profile'] != 'editor'
            or inspection.selection['document_profile'] != 'editor'):
        raise ValueError('Completed-work resume initially requires explicit editor profile')
    bindings = _completed_binding(value['original_bindings'])
    old = _completed_reference(value['original_plan'])
    if (old.get('kind') != PLAN_KIND or old.get('production_eligible') is not False
            or old['selection']['document_profile'] != 'editor'
            or old['selection']['sdk_manifest_sha256'] != inspection.selection['sdk_manifest_sha256']):
        raise ValueError('Completed work lacks the original pinned default editor plan/SDK')
    for key, selection in (('sources', 'sources'), ('sdk', 'sdk'), ('reuse', 'reuse_root')):
        if str(bindings[key]) != old['selection'][selection]:
            raise ValueError('Completed original root does not join its plan')
    if _successful:
        freeze, packet, handle, expected_commands = _successful_module().authority(value, bindings, old, sys.modules[__name__])
    else:
        freeze, packet, handle, expected_commands = _completed_authority(value, bindings, old)
        wrapper = _completed_reference(value['root_failure'])
        result = _completed_reference(value['candidate_result'])
        report = result.get('supervisor_report', {})
        if (wrapper.get('kind') != 'root-observed-closed-incremental-document-candidate-failure-v1'
                or wrapper.get('status') != 'failed' or wrapper.get('actual_session') != handle['actual_session']
                or type(wrapper.get('actual_caller_exit_code')) is not int
                or wrapper['actual_caller_exit_code'] != 1 or wrapper.get('writers_joined') is not True
                or wrapper.get('all_frozen_input_postflight') != 'passed'
                or any(wrapper.get('result', {}).get(key) != value['candidate_result'][key] for key in ('path', 'sha256'))
                or result.get('closed') is not True or result.get('writers_joined') is not True
                or result.get('input_identity_namespace_postflight') != 'passed'
                or type(result.get('returncode')) is not int or result['returncode'] != 1
                or wrapper.get('supervisor_report') != report or type(report.get('primary_returncode')) is not int
                or report['primary_returncode'] != 1 or report.get('descendants_outlived') is not False
                or report.get('terminated') is not False or report.get('error') is not None
                or type(report.get('reaped')) is not int or report['reaped'] < 1):
            raise ValueError('Completed original failure is not qualified closed work')
    commands = _completed_reference(value['original_commands'])
    fields(commands, ('objects', 'metadata', 'link'), 'completed original command ledger')
    if (commands != expected_commands or value['original_commands']['path'] != str(bindings['build'] / 'evidence/commands.json')
            or value['ninja_log']['path'] != str(bindings['build'] / 'cmake/build/.ninja_log')):
        raise ValueError('Completed original command/Ninja ledger authority differs')
    sidecar = _completed_reference(value['dependency_sidecar'])
    fields(sidecar, ('schema_version', 'kind', 'original_bindings', 'tool_context',
        'header_context', 'dependencies'), 'completed shared dependency sidecar')
    tool_context = {key: inspection.proof[key] for key in ('host_tools', 'sdk_tools',
        'python_launch', 'emscripten_config', 'private_cache')}
    tool_context['sdk_manifest_sha256'] = inspection.selection['sdk_manifest_sha256']
    original_context = {key: old['reuse'][key] for key in tool_context if key != 'sdk_manifest_sha256'}
    original_context['sdk_manifest_sha256'] = old['selection']['sdk_manifest_sha256']
    if (type(sidecar['schema_version']) is not int or sidecar['schema_version'] != 1
            or sidecar['kind'] != COMPLETED_DEPS_KIND or sidecar['original_bindings'] != value['original_bindings']
            or sidecar['tool_context'] != tool_context or tool_context != original_context
            or type(sidecar['dependencies']) is not dict
            or not 0 < len(sidecar['dependencies']) <= 16384):
        raise ValueError('Completed SDK/tool/config/cache/shared dependency context differs')
    rows = value['objects']
    selected = _completed_shape(inspection, old, rows, successful=_successful)
    if (any(type(row.get(key, {}).get('bytes')) is not int or row[key]['bytes'] < 1
            for row in rows for key in ('object', 'depfile'))
            or sum(row['object']['bytes'] + row['depfile']['bytes']
                + (row['command_script']['bytes'] if row.get('command_script') else 0) for row in rows) > 256 * 1024 * 1024):
        raise ValueError('Completed object/depfile/script selection exceeds bounded read budget')
    if set(commands['objects']) != set(selected):
        raise ValueError('Completed command ledger must preserve the exact51 union')
    context = sidecar['header_context']
    if context['namespace'] != _completed_frozen_namespace(freeze, bindings, context['directories']):
        raise ValueError('Completed header namespace lacks original full freeze authority')
    if context['vfs'] != _completed_private_context(value['original_private'], bindings, old, freeze):
        raise ValueError('Completed original compiled VFS differs from successor')
    ninja = checked_read(ordinary(value['ninja_log']['path']), value['ninja_log']['sha256']).decode('utf-8')
    if not ninja.startswith('# ninja log v6\n'):
        raise ValueError('Completed work needs its actual Ninja success ledger')
    ninja_rows = [line.split('\t') for line in ninja.splitlines()[1:]]
    admitted, refs, dependency_cache = [], [], {}
    old_objects = {obj['id']: obj for obj in old['reuse']['objects']}
    current_objects = {obj['id']: obj for obj in inspection.proof['objects']}
    for row in rows:
        fields(row, ('id', 'object', 'depfile', 'command_sha256', 'ninja_record', 'ninja_command', 'command_script', 'dependency_keys'), 'completed object')
        name = row['id']; obj = current_objects[name]; prior = old_objects[name]
        for key in ('source', 'arguments', 'dependencies', 'unified_members', 'exceptions'):
            if prior[key] != obj[key]:
                raise ValueError('Completed selected source/command/context changed: ' + name)
        argv = commands['objects'][name]
        if (type(obj['exceptions']) is not bool or _exception_policy(obj['arguments']) != obj['exceptions']
                or '-fno-rtti' not in obj['arguments'] or '-frtti' in obj['arguments']
                or name in inspection.profile['engine_objects'] and obj['exceptions']):
            raise ValueError('Completed EH/noRTTI policy differs: ' + name)
        cwd = str(bindings['build'] / 'cmake/build')
        if (hashlib.sha256(encoded({'argv': argv, 'cwd': cwd})).hexdigest() != row['command_sha256']
                or _completed_arguments(argv, cwd, bindings) != obj['arguments']):
            raise ValueError('Completed actual compiler command differs: ' + name)
        target = str(bindings['build'] / ('objects/' + name + '.o'))
        if (row['object']['path'] != target or row['depfile']['path'] != target + '.d'
                or argv[argv.index('-o') + 1] != target or argv[argv.index('-MT') + 1] != target
                or argv[argv.index('-MF') + 1] != target + '.d'):
            raise ValueError('Completed object/depfile/command target differs')
        matching = [item for item in ninja_rows if len(item) == 5 and item[3] == target]
        recorded = row['ninja_record']
        if (len(matching) != 1 or recorded != matching[0]
                or any(not item.isdecimal() for item in recorded[:3])
                or int(recorded[1]) < int(recorded[0]) or int(recorded[2]) != row['object']['identity'][5]
                or re.fullmatch('[0-9a-f]{1,16}', recorded[4]) is None
                or recorded[4] != _completed_ninja_command(row, argv, bindings, old['reuse']['host_tools'])):
            raise ValueError('Completed object lacks its exact successful Ninja record')
        _completed_fact(row['object'])
        normalize = lambda path: os.path.normpath(str(Path(path) if Path(path).is_absolute() else Path(cwd) / path))
        observed = [normalize(path) for path in _depfile_inputs(_completed_fact(row['depfile']), target=target)]
        keys = row['dependency_keys']
        if (type(keys) is not list or len(keys) != len(set(keys)) or keys != sorted(set(observed))
                or any(key not in sidecar['dependencies'] for key in keys)):
            raise ValueError('Completed actual depfile differs from the shared table')
        source = normalize(argv[argv.index('-c') + 1])
        if source not in keys:
            raise ValueError('Completed depfile omits its exact source')
        for key in keys:
            item = sidecar['dependencies'][key]
            fields(item, ('fact', 'input', 'origin'), 'completed normalized dependency')
            if item['origin'] not in ('retained', 'private-cache') or item['fact']['path'] != key:
                raise ValueError('Generated/unknown completed dependencies require recompilation')
            reference = item['input']
            fields(reference, REFERENCE_FIELDS, 'completed dependency input')
            if key not in dependency_cache:
                if item['origin'] == 'retained' and freeze['files'].get(key) != item['fact']:
                    raise ValueError('Completed dependency lacks original frozen physical authority')
                _completed_fact(item['fact'], sdk=Path(bindings['sdk']) in Path(key).parents)
                ref_path(reference, inspection.roots, inspection.inventories)
                if item['fact']['sha256'] != reference['sha256']:
                    raise ValueError('Completed dependency bytes changed in successor')
                if item['origin'] == 'private-cache':
                    seed = inspection.proof['private_cache']
                    relative = Path(key).relative_to(bindings['build'] / 'private/cache').as_posix()
                    if (reference['root'] != 'sdk' or reference['path'] != seed['root'] + '/' + relative
                            or reference['path'] not in seed['files']
                            or freeze['files'].get(str(bindings['sdk'] / reference['path']), {}).get('sha256') != item['fact']['sha256']):
                        raise ValueError('Completed private cache input lacks its exact SDK seed')
                else:
                    logical = _relocate_original(key, cwd, {k: str(v) for k, v in bindings.items() if k != 'build'})
                    if logical != '{' + reference['root'] + '}/' + reference['path']:
                        raise ValueError('Completed dependency root relocation differs')
                dependency_cache[key] = reference
            if key == source and reference != obj['source']:
                raise ValueError('Completed source does not match its selected logical reference')
            refs.append(reference)
        admitted.append(dict(row, original_argv=argv, original_cwd=cwd))
    current_context = _completed_header_context(inspection, refs, [current_objects[row['id']] for row in admitted])
    _completed_context_matches(sidecar['header_context'], current_context)
    if _successful:
        _successful_context_delta(inspection, old, sidecar['header_context'], current_context)
    metadata = [selected_reference, *(value[key] for key in ('original_plan', 'original_commands',
        'root_failure', 'candidate_result', 'original_input_freeze', 'original_build_packet',
        'root_launch', 'root_handle', 'ninja_log', 'dependency_sidecar'))]
    if _successful:
        metadata.extend(value[key] for key in ('root_acceptance', 'passive_worker', 'passive_result', 'maintenance_build'))
    result = {'reference': selected_reference, 'objects': admitted,
        'dependency_sidecar': value['dependency_sidecar'], 'original_bindings': value['original_bindings'],
        'metadata_directories': sorted({str(Path(ref['path']).parent) for ref in metadata})}
    if _successful:
        result['archives'] = _successful_module().archive_rows(value, inspection, old, bindings, sys.modules[__name__])
    return result


def _completed_input_directories(completed):
    if completed is None:
        return ()
    return (*_completed_binding(completed['original_bindings']).values(),
            *(ordinary(path, directory=True) for path in completed['metadata_directories']))


def _copy_completed_object(plan, object_id, output):
    """Copy admitted bytes independently; never call a compiler on any failure."""
    if plan.get('kind') not in (RESUME_PLAN_KIND, SUCCESSFUL_PLAN_KIND):
        raise ValueError('Object import requires a distinct admitted continuation plan')
    for root in _completed_input_directories(_work(plan)):
        if output == root or root in output.parents or output in root.parents:
            raise ValueError('Imported output overlaps original retained input or metadata')
    rows = _work(plan)['objects']
    matches = [row for row in rows if row['id'] == object_id]
    if len(matches) != 1:
        raise ValueError('Object was not explicitly admitted for import')
    row = matches[0]
    raw = _completed_fact(row['object'])
    depfile = _completed_fact(row['depfile'])
    target = output / ('objects/' + object_id + '.o')
    report = output / ('evidence/import-' + object_id + '.json')
    provenance = output / ('evidence/import-' + object_id + '.original.d')
    ordinary(output, directory=True)
    ordinary(target.parent, directory=True)
    ordinary(provenance.parent, directory=True)
    for destination, content, mode, original in ((target, raw, row['object']['mode'], row['object']),
            (provenance, depfile, 0o644, row['depfile'])):
        if destination.exists() or destination.is_symlink():
            ordinary(destination)
            if (digest(destination) != hashlib.sha256(content).hexdigest()
                    or stat.S_IMODE(destination.stat().st_mode) != mode):
                raise ValueError('Existing imported destination differs')
        else:
            with destination.open('xb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            destination.chmod(mode)
        if (_identity7(destination.stat())[:2] == original['identity'][:2]
                or ordinary(destination).stat().st_nlink != 1
                or checked_read(destination) != content or stat.S_IMODE(destination.stat().st_mode) != mode):
            raise ValueError('Imported destination/provenance is not an independent exact copy')
    _completed_fact(row['object'])
    _completed_fact(row['depfile'])
    if (ordinary(target).stat().st_nlink != 1 or digest(target) != row['object']['sha256']
            or target.stat().st_size != len(raw) or stat.S_IMODE(target.stat().st_mode) != row['object']['mode']):
        raise ValueError('Independent imported destination differs')
    record = {'kind': 'foundation-document-v2-object-import-v1', 'id': object_id,
        'origin': 'imported', 'object': row['object'], 'original_depfile': row['depfile'],
        'original_command_sha256': row['command_sha256'], 'original_argv': row['original_argv'],
        'original_cwd': row['original_cwd'], 'ninja_record': row['ninja_record'], 'ninja_command': row['ninja_command'],
        'command_script': row['command_script'], 'destination': str(target), 'sha256': digest(target), 'bytes': len(raw),
        'depfile_sha256': hashlib.sha256(depfile).hexdigest(),
        'retained_depfile': str(provenance), 'hardlinked': False,
        'compiler_invoked': False, 'production_eligible': False}
    if report.exists() or report.is_symlink():
        if checked_document(report) != record:
            raise ValueError('Existing import receipt differs')
    else:
        _save(report, record)
    return record


def _copy_successful_archive(plan, name, output):
    """Import one admitted regular archive without invoking ar or a fallback."""
    if plan.get('kind') != SUCCESSFUL_PLAN_KIND:
        raise ValueError('Archive import requires an explicit successful-donor plan')
    work = plan['successful_donor']
    for root in _completed_input_directories(work):
        if output == root or root in output.parents or output in root.parents:
            raise ValueError('Imported archive output overlaps donor authority')
    rows = [row for row in work['archives'] if row['name'] == name]
    if len(rows) != 1:
        raise ValueError('Archive was not explicitly admitted for import')
    row = rows[0]
    archive_raw = _completed_fact(row['archive'])
    report_raw = _completed_fact(row['report'])
    original_report = document(report_raw)
    if (original_report.get('name') != name
            or original_report.get('sha256') != row['archive']['sha256']):
        raise ValueError('Admitted archive/report identity changed')
    target = output / ('archives/lib' + name + '.a')
    report = output / ('evidence/archive-' + name + '.json')
    origin = output / ('evidence/import-archive-' + name + '.json')
    ordinary(output, directory=True)
    for destination, raw, fact in ((target, archive_raw, row['archive']),
                                   (report, report_raw, row['report'])):
        ordinary(destination.parent, directory=True)
        if destination.exists() or destination.is_symlink():
            ordinary(destination)
            if (checked_read(destination) != raw
                    or stat.S_IMODE(destination.stat().st_mode) != fact['mode']):
                raise ValueError('Existing imported archive/report differs')
        else:
            with destination.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            destination.chmod(fact['mode'])
        state = ordinary(destination).stat()
        if (_identity7(state)[:2] == fact['identity'][:2] or state.st_nlink != 1
                or checked_read(destination) != raw
                or stat.S_IMODE(state.st_mode) != fact['mode']):
            raise ValueError('Imported archive/report is not an independent exact copy')
    _completed_fact(row['archive'])
    _completed_fact(row['report'])
    if read_regular_archive(target) != original_report['members']:
        raise ValueError('Imported regular archive member order/bytes differ')
    record = {'kind': 'foundation-document-v2-archive-import-v1', 'name': name,
        'origin': 'imported', 'archive': row['archive'], 'original_report': row['report'],
        'destination': str(target), 'sha256': digest(target), 'bytes': len(archive_raw),
        'hardlinked': False, 'archive_program_invoked': False, 'production_eligible': False}
    if origin.exists() or origin.is_symlink():
        if checked_document(origin) != record:
            raise ValueError('Existing archive import receipt differs')
    else:
        _save(origin, record)
    return record


def _successful_build_receipt(result, plan, output, commands):
    # Reuse the exact existing object/readback checks; keep its public legacy
    # receipt shape unchanged and relabel only this explicit successor result.
    donor = plan['successful_donor']
    _completed_build_receipt(result, dict(plan, completed_work=donor), output, commands)
    compiled = set(_successful_module().COMPILED_IDS)
    names = [row['name'] for row in plan['reuse']['archives']]
    if (set(result['accounting']['compiled_ids']) != compiled
            or result['accounting']['compiled'] != 2 or result['accounting']['imported'] != 49
            or len(names) != 5 or set(commands.get('archive_imports', {})) != set(names)
            or [row['name'] for row in donor['archives']] != names):
        raise ValueError('Successful donor accounting differs from exact49/2/five archives')
    imports = []
    for row in donor['archives']:
        path = output / ('evidence/import-archive-' + row['name'] + '.json')
        record = checked_document(path)
        target = ordinary(output / ('archives/lib' + row['name'] + '.a'))
        if (record.get('kind') != 'foundation-document-v2-archive-import-v1'
                or record.get('name') != row['name'] or record.get('origin') != 'imported'
                or record.get('archive') != row['archive'] or record.get('original_report') != row['report']
                or record.get('destination') != str(target) or record.get('hardlinked') is not False
                or record.get('archive_program_invoked') is not False or record.get('production_eligible') is not False
                or record.get('sha256') != digest(target) or record['sha256'] != row['archive']['sha256']
                or type(record.get('bytes')) is not int or record['bytes'] != target.stat().st_size
                or record['bytes'] != row['archive']['bytes'] or target.stat().st_nlink != 1
                or _identity7(target.stat())[:2] == row['archive']['identity'][:2]):
            raise ValueError('Successful donor archive receipt/readback differs')
        imports.append({'name': row['name'], 'receipt': str(path.relative_to(output)), 'sha256': digest(path)})
    result['kind'] = SUCCESSFUL_BUILD_KIND
    result.pop('completed_work')
    result['successful_donor'] = donor['reference']
    result['accounting'].update(archive_imported=5, archive_repacked=0,
                                imported_archive_names=names)
    result['archive_imports'] = imports


def make_plan(selection, output, *, completed_work=None, successful_donor=None):
    if completed_work is not None and successful_donor is not None:
        raise ValueError('Failed partial work and successful donor are mutually exclusive')
    if (completed_work is not None or successful_donor is not None) and selection.get('document_profile') != 'editor':
        raise ValueError('Completed-work resume initially requires explicit editor profile')
    inspected = inspect_inputs(selection)
    completed = (_completed_work(completed_work, inspected) if completed_work is not None else
                 _completed_work(successful_donor, inspected, _successful=True) if successful_donor is not None else None)
    if successful_donor is not None:
        ref_path({'root': 'sources', 'path': SUCCESSFUL_HELPER, 'sha256': digest(ROOT / SUCCESSFUL_HELPER)}, inspected.roots, inspected.inventories)
    output = engine_sdk.new_destination(output, (*inspected.roots.values(),
        *_completed_input_directories(completed)))
    selected = inspected.selection['document_profile']
    plan = {'schema_version': 1, 'kind': PLAN_KIND, 'scope': SCOPE,
            'selection': inspected.selection, 'profile_sha256': digest(ROOT / profile_path(selected)),
            'producer_inputs': {name: digest(ROOT / name) for name in required_helpers(selected) + ((SUCCESSFUL_HELPER,) if successful_donor is not None else ())},
            'reuse': inspected.proof, 'projection': inspected.projection,
            'production_eligible': False}
    if completed is not None:
        plan['kind'] = SUCCESSFUL_PLAN_KIND if successful_donor is not None else RESUME_PLAN_KIND
        plan['successful_donor' if successful_donor is not None else 'completed_work'] = completed
    with engine_sdk._OwnedTree(output.parent, '.engine-plan-') as staged:
        (staged.path / 'plan.json').write_bytes(encoded(plan))
        staged.publish(output)
    return {'scope': SCOPE, 'plan': str(output / 'plan.json'),
            'plan_sha256': digest(output / 'plan.json'), 'production_eligible': False}


def verify_plan(path, expected_sha256):
    value = checked_document(path, expected_sha256)
    resume = value.get('kind') == RESUME_PLAN_KIND
    successful = value.get('kind') == SUCCESSFUL_PLAN_KIND
    names = ('schema_version', 'kind', 'scope', 'selection', 'profile_sha256',
             'producer_inputs', 'reuse', 'projection', 'production_eligible')
    fields(value, names + (('completed_work',) if resume else ('successful_donor',) if successful else ()), 'maintenance plan')
    selected = value['selection']['document_profile']
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] not in (PLAN_KIND, RESUME_PLAN_KIND, SUCCESSFUL_PLAN_KIND) or value['scope'] != SCOPE
            or value['production_eligible'] is not False
            or value['profile_sha256'] != digest(ROOT / profile_path(selected))
            or value['producer_inputs'] != {name: digest(ROOT / name) for name in required_helpers(selected) + ((SUCCESSFUL_HELPER,) if successful else ())}):
        raise ValueError('Plan producer/profile identity changed; create a fresh plan')
    inspected = inspect_inputs(value['selection'])
    if inspected.proof != value['reuse'] or inspected.projection != value['projection']:
        raise ValueError('Plan selected inputs changed')
    if resume and _completed_work(value['completed_work']['reference'], inspected) != value['completed_work']:
        raise ValueError('Plan completed-work input or admission changed')
    if successful and _completed_work(value['successful_donor']['reference'], inspected, _successful=True) != value['successful_donor']:
        raise ValueError('Plan successful donor input or admission changed')
    return value, inspected


def python_launcher(python, allowed_scripts, output):
    """One owned real -BE interpreter entry, including recursive SDK shell calls.

    SDK config normalizes EMSDK_PYTHON to sys.executable. Keep that value on this
    launcher before SDK imports. The shell file_packager's -E cannot undo -B.
    """
    python = str(python)
    if re.search(r'\s', python) or '\n' in str(output):
        raise ValueError('Pinned Python launcher paths cannot contain whitespace')
    source = '''#!{python} -BE
import sys
sys.dont_write_bytecode = True
import os
import runpy
allowed = {allowed!r}
launcher = {launcher!r}
args = sys.argv[1:]
while args and args[0] in ('-B', '-E', '-BE'):
    args.pop(0)
if not args or args[0].startswith('-') or args[0] not in allowed:
    raise SystemExit('unsupported retained SDK Python invocation')
script = args[0]
sys.executable = launcher
os.environ['EMSDK_PYTHON'] = launcher
sys.argv = args
sys.path[0] = os.path.dirname(script)
runpy.run_path(script, run_name='__main__')
'''.format(python=python, allowed=sorted(str(p) for p in allowed_scripts), launcher=str(output))
    output.write_text(source, encoding='utf-8')
    output.chmod(0o755)
    return output


def child_environment(build_root, sdk_root, launcher, config, cache, host_tools):
    require_clean()
    keep = ('LANG', 'LC_ALL', 'TZ', 'SYSTEMROOT', 'WINDIR')
    result = {name: os.environ[name] for name in keep if name in os.environ}
    result.update(EMSDK_PYTHON=str(launcher), EM_CONFIG=str(config), EM_CACHE=str(cache),
        EM_FROZEN_CACHE='1', CCACHE_DISABLE='1', PYTHONDONTWRITEBYTECODE='1',
        HOME=str(build_root / 'private/home'), TMPDIR=str(build_root / 'private/tmp'),
        XDG_CACHE_HOME=str(build_root / 'private/user-cache'),
        PATH=os.pathsep.join(sorted({str(Path(tool['path']).parent) for tool in host_tools.values()})))
    return result


def _expand(argument, roots, build_root):
    bindings = dict(roots, build=build_root, generated=build_root / 'document-generated')
    match = re.search(r'\{([^{}]+)\}', argument)
    if match is None:
        return argument
    key, suffix = match[1], argument[match.end():]
    if key not in bindings or re.search(r'[{}]', argument[:match.start()] + suffix):
        raise ValueError('Unresolved retained command root')
    if suffix:
        if not suffix.startswith('/'):
            raise ValueError('Retained root must precede a canonical relative path')
        manifest.path_name(suffix[1:])
    return argument[:match.start()] + str(bindings[key]) + suffix


def _cmake_value(value):
    value = str(value)
    # Semicolons are list separators even inside bracket arguments. Reject them
    # rather than silently changing exact compiler/data argument boundaries.
    if ';' in value or '\x00' in value or '\n' in value or '\r' in value:
        raise ValueError('Unsupported CMake argument character')
    delimiter = '='
    while ']' + delimiter + ']' in value:
        delimiter += '='
    return '[' + delimiter + '[' + value + ']' + delimiter + ']'


def _save(path, value):
    with path.open('xb') as stream:
        stream.write(encoded(value))


def _supervision_report(report, code, *, cleanup=False):
    return (type(code) is int and type(report) is dict
        and set(report) == {'schema_version', 'primary_returncode', 'descendants_outlived',
            'terminated', 'error', 'reaped'}
        and type(report['schema_version']) is int and report['schema_version'] == 1
        and type(report['primary_returncode']) is int and report['primary_returncode'] == code
        and report['descendants_outlived'] is False and report['error'] is None
        and type(report['terminated']) is bool and (cleanup or report['terminated'] is False)
        and type(report['reaped']) is int and report['reaped'] >= 1)


def _supervision_park(log, owner, stream, failure):
    """Retain actual objects before fallible notification; Root must recover explicitly."""
    global _MAINTENANCE_RETAINED_STATE
    _MAINTENANCE_RETAINED_STATE = (owner, stream, failure)
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(signum, lambda *_: None)
        except BaseException:
            pass
    try:
        # Failure-only metadata, never a completion receipt or permission to inspect products.
        control = Path(log).parent.parent / 'evidence/ownership-uncertain.json'
        value = {'kind': 'foundation-engine-maintenance-uncertain-owner-v1',
            'schema_version': 1, 'controller_pid': os.getpid(),
            'owner_process_id': owner.process.pid if owner is not None else None,
            'strong_owner_retained': owner is not None, 'strong_log_retained': stream is not None,
            'phase': Path(log).name[:128], 'first_failure': str(failure)[:2048],
            'output_claim_released': False, 'recovery': 'separate-explicit-Root-recovery-only'}
        if len(encoded(value)) > 8192:
            raise ValueError('Uncertainty control exceeds fixed bound')
        _save(control, value)
    except BaseException:
        pass
    while True:
        try:
            time.sleep(30)
        except BaseException:
            pass


def _supervise(argv, cwd, log, environment, timeout):
    stream = log.open('xb')
    owner, code, process_id = None, None, None
    settlement_started, failure = False, None
    try:
        owner = process_tree.launch([str(arg) for arg in argv], str(cwd), stream, env=environment)
        process_id = getattr(getattr(owner, 'process', None), 'pid', None)
        _save(log.with_suffix('.process.json'), {'owner_process_id': process_id,
            'argv': list(map(str, argv)), 'cwd': str(cwd), 'completed': False})
        code = owner.wait(timeout=timeout)
        settlement_started = True
        finished = owner.finish()
        if type(finished) is not int or finished != code or not _supervision_report(getattr(owner.process, 'report', None), code):
            raise ValueError('Maintenance natural settlement report is unqualified')
        owner.close()
        if owner.closed is not True:
            raise ValueError('Maintenance natural owner closure is unconfirmed')
    except BaseException as error:
        failure = error
        if owner is None or settlement_started:
            _supervision_park(log, owner, stream, error)
        # Exactly one bounded cleanup is allowed before settlement has started.
        settlement_started = True
        try:
            owner.terminate(timeout=30)
            finished = owner.finish()
            if not _supervision_report(getattr(owner.process, 'report', None), finished, cleanup=True):
                raise ValueError('Maintenance cleanup settlement report is unqualified')
            owner.close()
            if owner.closed is not True:
                raise ValueError('Maintenance cleanup owner closure is unconfirmed')
        except BaseException as cleanup_error:
            _supervision_park(log, owner, stream, cleanup_error)
    try:
        stream.close()
        if stream.closed is not True:
            raise ValueError('Maintenance log closure is unconfirmed')
    except BaseException as close_error:
        _supervision_park(log, owner, stream, close_error)
    if failure is not None:
        raise failure
    if code != 0:
        raise ValueError('Maintenance phase failed; inspect ' + str(log))
    result = {'argv': [str(arg) for arg in argv], 'cwd': str(cwd), 'returncode': code,
              'owner_process_id': process_id, 'writers_finished': True,
              'log': str(log), 'log_sha256': digest(log)}
    _save(log.with_suffix('.complete.json'), result)
    return result


def _graph(inspected, plan, plan_path, plan_hash, output):
    p, roots = inspected.proof, inspected.roots
    header_view = _header_identity(inspected)
    overlay_arguments = []
    if header_view is not None:
        overlay = output / 'private/header-identity-vfs.json'
        checked_read(overlay, hashlib.sha256(encoded(header_view['overlay'])).hexdigest())
        overlay_arguments = ['-ivfsoverlay', str(overlay)]
    resolve = lambda ref: str(ref_path(ref, roots, inspected.inventories))
    tools = {key: str(_tool(value)) for key, value in p['host_tools'].items()}
    sdk_tools = {key: str(roots['sdk'] / value['path']) for key, value in p['sdk_tools'].items()}
    values = {'FOUNDATION_ENGINE_GRAPH_VERSION': ['1']}
    def put(name, *arguments):
        values[name] = [str(arg) for arg in arguments]
    helper = roots['sources'] / SELF_PATH
    internal = [tools['python'], '-BE', str(helper), '_step', '--plan', str(plan_path),
                '--plan-sha256', plan_hash, '--build-root', str(output)]
    header, provider = output / 'document-generated/BibCopiedDocumentMetadata.generated.h', output / 'document-generated/provider-build.json'
    put('ENGINE_HEADER', header); put('ENGINE_PROVIDER_BUILD', provider)
    metadata = p['metadata']
    metadata_command = [tools['python'], '-BE', resolve(metadata['generator']),
        '--source-root', roots['sources'], '--build-root', output,
        '--recipe', roots['sources'] / 'recipe.json', '--build-plan', resolve(metadata['prelink_plan']),
        '--contract-header', resolve(metadata['contract_header']),
        '--document-profile', inspected.selection['document_profile'],
        '--document-header', resolve(metadata['document_header']),
        '--document-contract', resolve(metadata['document_contract']),
        '--document-catalog', resolve(metadata['document_catalog']),
        '--document-schema', resolve(metadata['document_schema']),
        '--action-ack', resolve(metadata['action_ack']),
        '--output-header', header, '--output-build', provider]
    if inspected.selection['document_profile'] in ('physical', 'editor'):
        metadata_command.extend(('--physical-catalog', resolve(metadata['physical_catalog'])))
    if inspected.selection['document_profile'] == 'editor':
        for key in ('editor_header', 'editor_contract', 'editor_catalog', 'editor_schema'):
            metadata_command.extend(('--' + key.replace('_', '-'), resolve(metadata[key])))
    put('ENGINE_METADATA_COMMAND', *metadata_command)
    put('ENGINE_METADATA_DEPENDS', *(resolve(ref) for ref in metadata.values()),
        *(roots['sources'] / name for name in required_helpers(inspected.selection['document_profile']) + ((SUCCESSFUL_HELPER,) if plan['kind'] == SUCCESSFUL_PLAN_KIND else ())),
        roots['sources'] / 'recipe.json')
    object_outputs = {}
    imported = {row['id']: row for row in (_work(plan) or {}).get('objects', [])}
    ids = []
    for index, obj in enumerate(p['objects']):
        key = 'o' + str(index)
        ids.append(key)
        target = output / ('objects/' + obj['id'] + '.o')
        depfile = Path(str(target) + '.d')
        object_outputs[obj['id']] = target
        put('ENGINE_OBJECT_' + key + '_OUTPUT', target)
        put('ENGINE_OBJECT_' + key + '_DEPFILE', depfile)
        put('ENGINE_OBJECT_' + key + '_COMMAND', sdk_tools['emxx'],
            *overlay_arguments,
            *(_expand(arg, roots, output) for arg in obj['arguments']),
            '-MD', '-MT', target, '-MF', depfile, '-o', target, '-c', resolve(obj['source']))
        put('ENGINE_OBJECT_' + key + '_DEPENDS', resolve(obj['source']),
            *(resolve(ref) for ref in obj['dependencies'] + obj['unified_members']),
            *(header_view['dependencies'] if header_view else []),
            *(overlay_arguments[1:] if overlay_arguments else []),
            *_arguments(obj['arguments'], inspection=inspected))
        if obj['id'] in imported:
            row = imported[obj['id']]
            put('ENGINE_OBJECT_' + key + '_IMPORTED', 'TRUE')
            put('ENGINE_OBJECT_' + key + '_REPORT', output / ('evidence/import-' + obj['id'] + '.json'))
            put('ENGINE_OBJECT_' + key + '_PROVENANCE', output / ('evidence/import-' + obj['id'] + '.original.d'))
            put('ENGINE_OBJECT_' + key + '_COMMAND', *internal, '--action', 'import', '--object', obj['id'])
            put('ENGINE_OBJECT_' + key + '_DEPENDS', row['object']['path'], row['depfile']['path'], helper, plan_path)
    put('ENGINE_OBJECT_IDS', *ids)
    replacements = {(r['archive'], r['ordinal']): r['object_id'] for r in p['replacements']}
    archive_outputs = {}
    imported_archives = {row['name']: row for row in plan.get('successful_donor', {}).get('archives', [])}
    for archive in p['archives']:
        name = archive['name']
        target = output / ('archives/lib' + name + '.a')
        archive_outputs[name] = target
        members = [str(object_outputs[replacements[(name, i)]]) if (name, i) in replacements
                   else resolve(member['input']) for i, member in enumerate(archive['members'])]
        put('ENGINE_ARCHIVE_' + name + '_OUTPUT', target)
        put('ENGINE_ARCHIVE_' + name + '_REPORT', output / ('evidence/archive-' + name + '.json'))
        # Remove only our previous owned output before rebuilding: plain `ar cr`
        # against a stale archive can retain members absent from the new recipe.
        put('ENGINE_ARCHIVE_' + name + '_COMMAND', *internal,
            '--action', 'repack', '--archive', name)
        put('ENGINE_ARCHIVE_' + name + '_INDEX', sdk_tools['emranlib'], target)
        put('ENGINE_ARCHIVE_' + name + '_READBACK', *internal, '--action', 'archive', '--archive', name)
        put('ENGINE_ARCHIVE_' + name + '_DEPENDS', *members, str(helper), str(plan_path))
        if name in imported_archives:
            row = imported_archives[name]
            put('ENGINE_ARCHIVE_' + name + '_IMPORTED', 'TRUE')
            put('ENGINE_ARCHIVE_' + name + '_IMPORT_REPORT', output / ('evidence/import-archive-' + name + '.json'))
            put('ENGINE_ARCHIVE_' + name + '_COMMAND', *internal, '--action', 'import-archive', '--archive', name)
            put('ENGINE_ARCHIVE_' + name + '_DEPENDS', row['archive']['path'], row['report']['path'], helper, plan_path)
    put('ENGINE_ARCHIVE_NAMES', *(a['name'] for a in p['archives']))
    deps = {Path(ref['path']).name: resolve(ref) for ref in p['link']['dependencies']}
    ordered = [str(archive_outputs[name]) if name in archive_outputs else deps[name]
               for name in p['link']['archives']]
    factory, wasm, linkmap = (output / 'artifacts/foundation-retained-engine.mjs',
                             output / 'artifacts/foundation-retained-engine.wasm',
                             output / 'evidence/engine-link.map')
    put('ENGINE_FACTORY', factory); put('ENGINE_WASM', wasm); put('ENGINE_MAP', linkmap)
    wrapper_outputs = [object_outputs[name] for name in inspected.profile['direct_objects']]
    link_args = [_expand(arg, roots, output) for arg in p['link']['flags']]
    link_args += ['--pre-js', resolve(p['link']['pre_js']), '--js-library', resolve(p['link']['host_library'])]
    for data in p['link']['data']:
        link_args += ['--embed-file', resolve(data['input']) + '@' + data['virtual_path']]
    link_command = [sdk_tools['emxx'], *link_args, '-Wl,-Map=' + str(linkmap),
                    *map(str, wrapper_outputs), '-o', str(factory), *ordered]
    put('ENGINE_LINK_COMMAND', *link_command)
    put('ENGINE_LINK_DEPENDS', *(resolve(ref) for ref in p['link']['dependencies']),
        resolve(p['link']['pre_js']), resolve(p['link']['host_library']),
        *(resolve(item['input']) for item in p['link']['data']), header, provider)
    put('ENGINE_INSPECTION', output / 'evidence/artifact-inspection.json')
    put('ENGINE_INSPECT_COMMAND', *internal, '--action', 'artifacts')
    put('ENGINE_INSPECT_DEPENDS', helper, plan_path)
    fragment = output / 'cmake/verified-plan.cmake'
    fragment.write_text(''.join('set(' + name + ''.join('\n  ' + _cmake_value(arg) for arg in args)
                                + ')\n' for name, args in values.items()), encoding='utf-8')
    commands = {'metadata': list(map(str, metadata_command)),
        'objects': {obj['id']: values['ENGINE_OBJECT_o' + str(i) + '_COMMAND']
                    for i, obj in enumerate(p['objects']) if obj['id'] not in imported}, 'link': link_command}
    if plan.get('kind') in (RESUME_PLAN_KIND, SUCCESSFUL_PLAN_KIND):
        commands['imports'] = {obj['id']: values['ENGINE_OBJECT_o' + str(i) + '_COMMAND']
                              for i, obj in enumerate(p['objects']) if obj['id'] in imported}
    if plan.get('kind') == SUCCESSFUL_PLAN_KIND:
        commands['archive_imports'] = {name: values['ENGINE_ARCHIVE_' + name + '_COMMAND'] for name in imported_archives}
    return tools, fragment, commands


def build(plan_path, expected_sha256, output, *, jobs=2, timeout_seconds=1800):
    plan_path = ordinary(plan_path)
    plan, inspected = verify_plan(plan_path, expected_sha256)
    if type(jobs) is not int or jobs < 1 or type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError('Positive jobs and timeout are required')
    if not sys.platform.startswith('linux'):
        raise ValueError('The initial document-v2 producer is Linux-host only')
    output = engine_sdk.new_destination(output, (*inspected.roots.values(), plan_path.parent,
        *_completed_input_directories(_work(plan))))
    require_clean()
    output.mkdir(mode=0o755)
    _save(output / 'maintenance-owner.json', {'schema_version': 1,
        'plan_sha256': expected_sha256, 'output': str(output),
        'producer_sha256': digest(ROOT / SELF_PATH)})
    for name in ('document-generated', 'private/home', 'private/tmp', 'private/user-cache',
                 'private/cache', 'cmake', 'objects', 'archives', 'artifacts', 'evidence', 'logs'):
        (output / name).mkdir(parents=True, exist_ok=True)
    try:
        proof, roots = inspected.proof, inspected.roots
        cache = output / 'private/cache'
        seed = Path(proof['private_cache']['root'])
        for name in proof['private_cache']['files']:
            relative = Path(name).relative_to(seed)
            destination = cache / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = roots['sdk'] / name
            shutil.copyfile(source, destination)
            if digest(destination) != inspected.inventories['sdk'][name]:
                raise ValueError('Private cache seed changed while copying')
        python = proof['host_tools']['python']['path']
        launcher = python_launcher(python, [roots['sdk'] / path for path in inspected.profile['python_entrypoints']],
                                   output / 'private/sdk-python')
        config = output / 'private/emscripten-config.py'
        setting = proof['emscripten_config']
        config.write_text(''.join(key + ' = ' + repr(str(roots['sdk'] / name)) + '\n'
                                  for key, name in setting.items())
                          + 'CACHE = ' + repr(str(cache)) + '\nFROZEN_CACHE = True\n', encoding='utf-8')
        environment = child_environment(output, roots['sdk'], launcher, config, cache, proof['host_tools'])
        header_view = _header_identity(inspected)
        if header_view is not None:
            _save(output / 'private/header-identity-vfs.json', header_view['overlay'])
        tools, fragment, commands = _graph(inspected, plan, plan_path, expected_sha256, output)
        _save(output / 'evidence/commands.json', commands)
        # Private setup creates no SDK process. Revalidate selected closures after
        # setup and before the first CMake/Ninja/Python/driver program.
        verify_plan(plan_path, expected_sha256)
        start = time.monotonic()
        receipts = []
        configure = [tools['cmake'], '-S', str(roots['sources'] / Path(GRAPH_PATH).parent),
                     '-B', str(output / 'cmake/build'), '-G', 'Ninja',
                     '-DCMAKE_MAKE_PROGRAM=' + tools['ninja'],
                     '-DFOUNDATION_ENGINE_PLAN=' + str(fragment)]
        for phase, argv in (('configure', configure), ('build', [tools['cmake'], '--build',
                str(output / 'cmake/build'), '--target', 'foundation-neutral-engine', '--parallel', str(jobs)])):
            remaining = timeout_seconds - (time.monotonic() - start)
            if remaining <= 0:
                raise ValueError('Maintenance deadline exhausted before ' + phase)
            verify_plan(plan_path, expected_sha256)
            _save(output / ('evidence/' + phase + '-intent.json'), {'argv': argv, 'cwd': str(output)})
            receipts.append(_supervise(argv, output, output / ('logs/' + phase + '.log'), environment, remaining))
        verify_plan(plan_path, expected_sha256)
        inspection = checked_document(output / 'evidence/artifact-inspection.json')
        result = {'schema_version': 1, 'kind': BUILD_KIND, 'scope': SCOPE,
            'status': 'passed', 'production_eligible': False, 'plan_sha256': expected_sha256,
            'source_recipe_sha256': inspected.selection['recipe_sha256'],
            'sources_sha256': inspected.selection['sources_sha256'],
            'paired_sdk_sha256': inspected.selection['sdk_manifest_sha256'],
            'supervision': receipts, 'inspection': inspection,
            'objects': [{'id': obj['id'], 'sha256': digest(output / ('objects/' + obj['id'] + '.o')),
                         'bytes': (output / ('objects/' + obj['id'] + '.o')).stat().st_size,
                         'command_sha256': hashlib.sha256(encoded(commands['objects'].get(obj['id'], commands.get('imports', {}).get(obj['id'])))).hexdigest()}
                        for obj in proof['objects']],
            'commands': {'path': 'evidence/commands.json', 'sha256': digest(output / 'evidence/commands.json')},
            'private_configuration': {'launcher_sha256': digest(launcher), 'config_sha256': digest(config),
                                      'bytecode_policy': 'owned-recursive-python-BE'},
            'host_prerequisites': proof['host_tools'],
            'recovery_limits': proof['recovery_limits'],
            'next_gate': 'original dedicated-Worker runtime evidence and explicit retained group sealing'}
        if plan['kind'] == RESUME_PLAN_KIND:
            _completed_build_receipt(result, plan, output, commands)
        elif plan['kind'] == SUCCESSFUL_PLAN_KIND:
            _successful_build_receipt(result, plan, output, commands)
        _save(output / 'maintenance-build.json', result)
        return result
    except BaseException as error:
        # Preserve the owned failed/incomplete work. Never clean SDK pyc after
        # execution or publish a successful receipt from partial outputs.
        _save(output / 'maintenance-failure.json', {'schema_version': 1,
            'kind': SUCCESSFUL_BUILD_KIND if plan['kind'] == SUCCESSFUL_PLAN_KIND else RESUME_BUILD_KIND if plan['kind'] == RESUME_PLAN_KIND else BUILD_KIND,
            'scope': SCOPE, 'status': 'incomplete', 'production_eligible': False,
            'error': str(error)[:4096], 'plan_sha256': expected_sha256})
        raise


def read_thin_archive(path):
    """Read the original serialized thin table, never substitute proof order."""
    data = checked_read(path)
    if data[:8] != b'!<thin>\n':
        raise ValueError('Expected the actual baseline thin archive')
    position, names, members = 8, None, []
    while position < len(data):
        header = data[position:position + 60]
        if len(header) != 60 or header[58:] != b'`\n':
            raise ValueError('Invalid thin archive header')
        try:
            name = header[:16].decode('ascii').rstrip()
            size = int(header[48:58].decode('ascii').strip())
        except (ValueError, UnicodeError):
            raise ValueError('Invalid thin archive name/size') from None
        if size < 0:
            raise ValueError('Negative thin member size')
        position += 60
        if name in ('/', '/SYM64/', '//'):
            if size > len(data) - position:
                raise ValueError('Truncated thin special member')
            content = data[position:position + size]
            position += size + (size & 1)
            if name == '//':
                if names is not None:
                    raise ValueError('Duplicate thin long-name table')
                names = content
            continue
        if name.startswith('/'):
            if names is None or not name[1:].isdigit():
                raise ValueError('Unsupported thin archive name encoding')
            offset = int(name[1:])
            end = names.find(b'/\n', offset)
            if offset >= len(names) or end < 0 or offset and names[offset - 1:offset] != b'\n':
                raise ValueError('Invalid thin member name offset')
            name = names[offset:end].decode('ascii')
        else:
            name = name.removesuffix('/')
        if not name or '\x00' in name:
            raise ValueError('Invalid thin member name')
        members.append({'name': name, 'bytes': size})
    if position != len(data) or not members:
        raise ValueError('Incomplete thin archive table')
    return members


def read_regular_archive(path):
    """Read real GNU/BSD regular member bytes/order; no extraction or ar process."""
    data = checked_read(path)
    if data[:8] != b'!<arch>\n':
        raise ValueError('Expected a self-contained regular archive')
    position, names, members, index_seen = 8, None, [], False
    symbol_offsets, member_offsets = [], set()
    while position < len(data):
        header = data[position:position + 60]
        if len(header) != 60 or header[58:] != b'`\n':
            raise ValueError('Truncated/invalid archive member header')
        try:
            name = header[:16].decode('ascii').rstrip()
            count = int(header[48:58].decode('ascii').strip())
        except (UnicodeError, ValueError):
            raise ValueError('Invalid archive name/size') from None
        if count < 0 or count > len(data) - position - 60:
            raise ValueError('Invalid archive member size')
        header_offset = position
        content = data[position + 60:position + 60 + count]
        position += 60 + count
        if count & 1:
            if data[position:position + 1] != b'\n':
                raise ValueError('Invalid archive member alignment')
            position += 1
        if name in ('/', '/SYM64/'):
            if index_seen:
                raise ValueError('Duplicate archive symbol index')
            index_seen = True
            width = 8 if name == '/SYM64/' else 4
            if len(content) < width:
                raise ValueError('Truncated archive symbol index')
            entries = int.from_bytes(content[:width], 'big')
            if entries > (len(content) - width) // width:
                raise ValueError('Invalid archive symbol index')
            symbol_offsets = [int.from_bytes(content[width + i * width:width * 2 + i * width], 'big')
                              for i in range(entries)]
            symbols = content[width * (entries + 1):]
            cursor = 0
            for _ in range(entries):
                end = symbols.find(b'\0', cursor)
                if end <= cursor:
                    raise ValueError('Invalid archive symbol names')
                cursor = end + 1
            # LLVM may include one NUL alignment byte inside the index member.
            # Its count/offset prefix is even for both index widths, so this
            # byte is valid only after an odd number of actual name bytes.
            remainder = symbols[cursor:]
            if remainder and (remainder != b'\0' or not cursor & 1):
                raise ValueError('Invalid archive symbol names')
            continue
        if name == '//':
            if names is not None:
                raise ValueError('Duplicate archive long-name table')
            names = content
            continue
        if name.startswith('#1/'):
            length = int(name[3:])
            if length < 1 or length > len(content):
                raise ValueError('Invalid BSD archive member name')
            name, content = content[:length].rstrip(b'\0').decode('ascii'), content[length:]
        elif name.startswith('/'):
            if names is None or not name[1:].isdigit():
                raise ValueError('Unknown archive name encoding')
            offset = int(name[1:])
            end = names.find(b'/\n', offset)
            if offset >= len(names) or end < 0 or offset and names[offset - 1:offset] != b'\n':
                raise ValueError('Invalid GNU archive long-name offset')
            name = names[offset:end].decode('ascii')
        else:
            name = name.removesuffix('/')
        manifest.path_name(name)
        member_offsets.add(header_offset)
        members.append({'name': name, 'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)})
    if position != len(data) or not index_seen:
        raise ValueError('Archive lacks a complete actual symbol index')
    if len({m['name'] for m in members}) != len(members):
        raise ValueError('Duplicate regular archive member name')
    if any(offset not in member_offsets for offset in symbol_offsets):
        raise ValueError('Archive symbol index references a missing member header')
    return members


def validate_artifact_facts(facts, document_profile='pixel'):
    """Check actual section-scanned signatures without executing a factory."""
    if (facts['start'] is not None or len(facts['memories']) != 1 or facts['memories'][0]['shared']
            or facts['memories'][0]['memory64'] or facts['memories'][0]['maximum'] is None
            or facts['memories'][0]['maximum'] > 65536):
        raise ValueError('Final engine memory/start facts violate document profile')
    required = {'bib_engine_get_provider_v1': (['i32'] * 4, ['i32']),
        'bib_engine_wasm_bridge_v1': ([], ['i32']),
        'bib_engine_wasm_dispatch_v1': (['i32'] * 5, ['i32']),
        'bib_engine_wasm_document_facts_v1': (['i32'] * 2, ['i32']),
        'bib_engine_wasm_document_configure_v1': (['i32'] * 2, ['i32']),
        'malloc': (['i32'], ['i32']), 'free': (['i32'], [])}
    if profile_selector(document_profile) == 'editor':
        required = {name.replace('wasm_document_', 'wasm_editor_'): shape
                    for name, shape in required.items()}
    exports = {item['name']: item for item in facts['exports']}
    for name, (parameters, results) in required.items():
        item = exports.get(name)
        if item is None or item['kind'] != 'function' or item['details'] != {'parameters': parameters, 'results': results}:
            raise ValueError('Missing or mistyped actual document export: ' + name)
    for item in facts['imports'] + facts['exports']:
        name = item['name'].lstrip('_').lower()
        if name in ('main', 'start', 'bib_eval', 'bib_pump') or name.startswith(('pthread', 'emscripten_thread')):
            raise ValueError('Actual factory exports diagnostic or pthread entry')


def validate_provider_build(value, selection, recipe):
    selected = profile_selector(selection['document_profile'])
    selected_contract = profile_contract(selected)
    fields(value, selected_contract.BUILD_FIELDS, 'document provider build')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != selected_contract.BUILD_KIND
            or value['source_recipe_sha256'] != selection['recipe_sha256']
            or value['source_inputs_sha256'] != hashlib.sha256(encoded(recipe['inputs'])).hexdigest()
            or value['contract_header_sha256'] != selected_contract.CONTRACT_SHA256
            or value['binding'] != selected_contract.BINDING
            or value['configuration'] != profile_call(selected, 'expected_configuration')
            or value['capabilities'] != selected_contract.CAPABILITIES[selected]
            or type(value['bridge_abi']) is not int or value['bridge_abi'] != 65536
            or any(value[key] != recipe[key] for key in ('target', 'toolchain', 'options'))):
        raise ValueError('Generated document provider build identity/contract differs')
    profile_call(selected, 'validate_provider_contract', value=value['provider_contract'])


def _step(args):
    # The CMake helper reads the pinned plan itself and immediate artifact inputs,
    # avoiding a complete 351MB+ source/SDK rescan for every archive node.
    plan = checked_document(args.plan, args.plan_sha256)
    if plan.get('kind') not in (PLAN_KIND, RESUME_PLAN_KIND, SUCCESSFUL_PLAN_KIND) or plan.get('production_eligible') is not False:
        raise ValueError('Invalid internal maintenance plan')
    output = ordinary(args.build_root, True)
    p = plan['reuse']
    roots = {'sources': Path(plan['selection']['sources']), 'sdk': Path(plan['selection']['sdk']),
             'reuse': Path(plan['selection']['reuse_root'])}
    for root in (*roots.values(), Path(args.plan).parent):
        if root == output or root in output.parents or output in root.parents:
            raise ValueError('Internal artifact output overlaps retained inputs/plan')
    owner = checked_document(output / 'maintenance-owner.json')
    if owner != {'schema_version': 1, 'plan_sha256': args.plan_sha256,
                 'output': str(output), 'producer_sha256': digest(ROOT / SELF_PATH)}:
        raise ValueError('Internal action lacks its exact owned build-root binding')
    if args.action == 'import':
        return _copy_completed_object(plan, args.object, output)
    if args.action == 'import-archive':
        return _copy_successful_archive(plan, args.archive, output)
    if args.action in ('archive', 'repack'):
        archive = next((a for a in p['archives'] if a['name'] == args.archive), None)
        if archive is None:
            raise ValueError('Unknown maintained archive')
        replacements = {(r['archive'], r['ordinal']): r['object_id'] for r in p['replacements']}
        expected, member_paths = [], []
        for i, member in enumerate(archive['members']):
            owner = replacements.get((archive['name'], i))
            source = (output / ('objects/' + owner + '.o') if owner else
                      roots[member['input']['root']] / member['input']['path'])
            member_paths.append(str(ordinary(source)))
            expected.append({'name': source.name, 'sha256': digest(ordinary(source)), 'bytes': source.stat().st_size})
            if not owner and expected[-1]['sha256'] != member['input']['sha256']:
                raise ValueError('Unchanged baseline member changed before readback')
        if len({item['name'] for item in expected}) != len(expected):
            raise ValueError('Repacked regular archive would have duplicate basenames')
        if args.action == 'repack':
            target = output / ('archives/lib' + archive['name'] + '.a')
            if target.exists() or target.is_symlink():
                ordinary(target)
                target.unlink()
            driver = ordinary(roots['sdk'] / p['sdk_tools']['emar']['path'], sdk=True)
            if digest(driver) != p['sdk_tools']['emar']['sha256']:
                raise ValueError('Selected archive driver changed')
            # Exec retains the existing CMake-supervised command node; this
            # helper neither schedules members nor accepts arbitrary commands.
            os.execv(str(driver), [str(driver), 'cr', str(target), *member_paths])
        actual = read_regular_archive(output / ('archives/lib' + archive['name'] + '.a'))
        if actual != expected:
            raise ValueError('Actual archive member order/bytes/substitutions differ')
        report = {'name': archive['name'], 'members': actual,
                  'sha256': digest(output / ('archives/lib' + archive['name'] + '.a'))}
        target = output / ('evidence/archive-' + archive['name'] + '.json')
    else:
        import appended_engine_consumer as consumer
        factory = checked_read(output / 'artifacts/foundation-retained-engine.mjs')
        wasm = checked_read(output / 'artifacts/foundation-retained-engine.wasm')
        facts, syntax = consumer.scan_wasm(wasm), consumer.scan_factory(factory)
        validate_artifact_facts(facts, plan['selection']['document_profile'])
        validate_provider_build(checked_document(output / 'document-generated/provider-build.json'),
            plan['selection'], checked_document(roots['sources'] / 'recipe.json', plan['selection']['recipe_sha256']))
        linkmap = checked_read(output / 'evidence/engine-link.map')
        if not linkmap:
            raise ValueError('Actual link map is empty')
        archives = [checked_document(output / ('evidence/archive-' + a['name'] + '.json')) for a in p['archives']]
        for archive in archives:
            if digest(output / ('archives/lib' + archive['name'] + '.a')) != archive['sha256']:
                raise ValueError('Closed archive changed after member readback')
        selected_members = []
        for replacement in p['replacements']:
            marker = ('lib' + replacement['archive'] + '.a(' + replacement['object_id'] + '.o)').encode()
            if marker not in linkmap:
                raise ValueError('Actual link map lacks selected replacement member: ' + marker.decode())
            selected_members.append(marker.decode())
        report = {'scope': SCOPE, 'production_eligible': False, 'wasm_facts': facts,
            'factory_syntax': syntax, 'archives': archives,
            'factory_sha256': hashlib.sha256(factory).hexdigest(),
            'wasm_sha256': hashlib.sha256(wasm).hexdigest(),
            'map_sha256': hashlib.sha256(linkmap).hexdigest(),
            'replacement_members_observed_in_map': selected_members,
            'provider_build_sha256': digest(output / 'document-generated/provider-build.json'),
            'generated_header_sha256': digest(output / 'document-generated/BibCopiedDocumentMetadata.generated.h')}
        target = output / 'evidence/artifact-inspection.json'
    # This output is a CMake-owned rebuildable evidence node, never an input or
    # published successful build receipt. Recheck old ordinary identity first.
    if target.exists():
        ordinary(target)
        target.unlink()
    _save(target, report)
    return report


def positive(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError('value must be positive')
    return result


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    planning = sub.add_parser('plan')
    for name in SELECTION_FIELDS:
        planning.add_argument('--' + name.replace('_', '-'), required=True)
    planning.add_argument('--output', type=Path, required=True)
    planning.add_argument('--completed-work', type=Path)
    planning.add_argument('--completed-work-sha256')
    planning.add_argument('--successful-donor', type=Path)
    planning.add_argument('--successful-donor-sha256')
    building = sub.add_parser('build')
    building.add_argument('--plan', type=Path, required=True)
    building.add_argument('--plan-sha256', required=True)
    building.add_argument('--output', type=Path, required=True)
    building.add_argument('--jobs', type=positive, default=2)
    building.add_argument('--timeout-seconds', type=positive, default=1800)
    step = sub.add_parser('_step', help=argparse.SUPPRESS)
    step.add_argument('--plan', type=Path, required=True)
    step.add_argument('--plan-sha256', required=True)
    step.add_argument('--build-root', type=Path, required=True)
    step.add_argument('--action', choices=('repack', 'archive', 'artifacts', 'import', 'import-archive'), required=True, dest='step_action')
    step.add_argument('--archive')
    step.add_argument('--object')
    args = parser.parse_args(arguments)
    if args.action == 'plan':
        if (args.completed_work is None) != (args.completed_work_sha256 is None):
            parser.error('--completed-work and --completed-work-sha256 are required together')
        if (args.successful_donor is None) != (args.successful_donor_sha256 is None):
            parser.error('--successful-donor and --successful-donor-sha256 are required together')
        if args.completed_work is not None and args.successful_donor is not None:
            parser.error('--completed-work and --successful-donor are mutually exclusive')
        selection = {name: getattr(args, name) for name in SELECTION_FIELDS}
        if args.successful_donor is not None:
            result = make_plan(selection, args.output, successful_donor={
                'path': str(args.successful_donor), 'sha256': sha(args.successful_donor_sha256, 'successful-donor')})
        elif args.completed_work is None:
            result = make_plan(selection, args.output)
        else:
            result = make_plan(selection, args.output, completed_work={
                'path': str(args.completed_work), 'sha256': sha(args.completed_work_sha256, 'completed-work')})
    elif args.action == 'build':
        result = build(args.plan, args.plan_sha256, args.output,
                       jobs=args.jobs, timeout_seconds=args.timeout_seconds)
        receipt = args.output / 'maintenance-build.json'
        result = {'scope': result['scope'], 'status': result['status'],
                  'production_eligible': False, 'receipt': str(receipt),
                  'receipt_sha256': digest(receipt), 'plan_sha256': args.plan_sha256}
    else:
        args.action = args.step_action
        _step(args)
        result = {'scope': SCOPE, 'action': args.step_action, 'archive': args.archive,
                  'production_eligible': False}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, process_tree.ProcessTreeError) as error:
        raise SystemExit('document engine maintenance: ' + str(error))
