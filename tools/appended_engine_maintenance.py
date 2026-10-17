#!/usr/bin/env python3
"""Explicit copied259 incremental producer; never a cold build or eligible group.

The pinned reuse proof is an input contract, not original runtime evidence.
Its strict JSON fields and reference vocabulary are implemented below. CMake
owns all compile/archive/link edges. No engine-sdk or payload route calls this.
"""
import argparse
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import time

import appended_engine_manifest as manifest
import appended_engine_sdk as engine_sdk
import appended_engine_donor as engine_donor
from dependency_archive import digest, encoded, object_pairs
import process_tree
from sdk_environment import require_clean
from sdk_manifest import verify_sdk

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = 'recipes/webkitwasm-copied259-v1/maintenance-profile.json'
GRAPH_PATH = 'cmake/AppendedEngineMaintenance/CMakeLists.txt'
SELF_PATH = 'tools/appended_engine_maintenance.py'
REQUIRED_HELPERS = (SELF_PATH, GRAPH_PATH, PROFILE_PATH,
    'tools/appended_engine_manifest.py', 'tools/appended_engine_sdk.py',
    'tools/dependency_archive.py', 'tools/process_tree.py', 'tools/sdk_environment.py',
    'tools/sdk_manifest.py', 'tools/appended_engine_consumer.py', 'tools/browser_bundle.py')
REQUIRED_HELPERS += ('tools/appended_engine_donor.py',)
PLAN_KIND = 'foundation-copied259-maintenance-plan-v1'
BUILD_KIND = 'foundation-copied259-maintenance-build-v1'
REUSE_KIND = 'foundation-copied259-baseline-reuse-v1'
SCOPE = 'incremental-neutral-engine-candidate'
# Both explicit Emscripten wasm32 spellings occur in retained inputs. They are
# admitted vocabulary, never interchangeable identities: source and SDK must
# preserve and match the exact independently pinned declaration.
EMSCRIPTEN_TRIPLES = ('wasm32-emscripten', 'wasm32-unknown-emscripten')
REFERENCE_FIELDS = ('root', 'path', 'sha256')
SELECTION_FIELDS = ('profile', 'sources', 'recipe_sha256', 'sources_sha256',
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
    # Preserve that parser's strict grammar without inheriting its size policy.
    def invalid(value):
        raise ValueError('invalid JSON constant: ' + value)
    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=invalid)


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


def profile():
    value = checked_document(ROOT / PROFILE_PATH)
    if (value.get('schema_version') != 1 or value.get('kind') != 'foundation-copied259-maintenance-profile-v1'
            or value.get('name') != 'webkitwasm-copied259-v1'):
        raise ValueError('Unknown maintained copied259 profile')
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
    completed_objects: object = None


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


def _validate_projection(value, sources, source_files):
    if type(value) is not dict or type(value.get('files')) is not dict or not value['files']:
        raise ValueError('Projection must select exact retained final source files')
    for name, item in value['files'].items():
        manifest.path_name(name)
        if type(item) is not dict or source_files.get(name) != item.get('sha256'):
            raise ValueError('Selected projection differs from retained sources: ' + name)
        if digest(ordinary(sources / name)) != item['sha256']:
            raise ValueError('Selected projection source changed: ' + name)
    # The semantic profile accepts repaired explicit successor bytes, not only
    # the original frozen promotion's hashes. Its recovery layout remains fixed.
    needed = ('source/wrapper/src/embedder/main.cpp',
              'source/wrapper/src/embedder/embedder.cmake',
              'source/copied-provider/runtime/embedder.cmake')
    if needed[0] not in value['files']:
        raise ValueError('Projection must select the neutral wrapper main.cpp')
    if any(name not in value['files'] for name in needed[1:2]):
        # Historical projection keys the copied CMake at its copied-provider path;
        # require its recovered sibling to be present in complete sources below.
        if needed[2] not in value['files']:
            raise ValueError('Projection lacks the copied CMake recovery input')
    sibling, copied = sources / needed[1], sources / needed[2]
    if not sibling.is_file() or not copied.is_file() or checked_read(sibling) != checked_read(copied):
        raise ValueError('Recover exact embedder.cmake beside wrapper/src/embedder')


def inspect_inputs(selection):
    """Pure complete source/SDK/reuse verification; no tool execution/discovery."""
    if hasattr(selection, '__dict__'):
        selection = vars(selection)
    selection = dict(selection)
    fields(selection, SELECTION_FIELDS, 'maintenance selection')
    selected_profile = profile()
    if selection['profile'] != selected_profile['name']:
        raise ValueError('Only the explicit copied259 incremental profile is implemented')
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
    checked_read(sources / 'recipe.json', selection['recipe_sha256'])
    checked_read(sources / 'sources.json', selection['sources_sha256'])
    source_manifest, source_hash, recipe = manifest.verify_sources(sources)
    if source_hash != selection['sources_sha256'] or digest(sources / 'recipe.json') != selection['recipe_sha256']:
        raise ValueError('Explicit retained source pins differ')
    if ((recipe['target']['system'], recipe['target']['processor'], recipe['target']['pointer_bits'])
            != ('Emscripten', 'wasm32', 32)
            or recipe['target']['triple'] not in EMSCRIPTEN_TRIPLES
            or recipe['options'] != {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'}
            or recipe['provider']['binding'] != 'copied-owner-bridge'
            or (recipe['provider']['abi_major'], recipe['provider']['abi_minor']) != (1, 0)):
        raise ValueError('Source recipe is not the exact copied259 browser profile')
    for name in REQUIRED_HELPERS:
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
    _validate_projection(projection, sources, source_manifest['files'])
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
    proof_fields = ('schema_version', 'kind', 'profile', 'target', 'paired_sdk_sha256',
        'baseline', 'inventory', 'host_tools', 'sdk_tools', 'python_launch',
        'objects', 'archives', 'replacements', 'link', 'metadata', 'private_cache',
        'emscripten_config', 'recovery_limits')
    if type(proof) is dict and 'header_identity' in proof:
        proof_fields += ('header_identity',)
    if type(proof) is dict and 'completed_objects' in proof:
        proof_fields += ('completed_objects',)
    fields(proof, proof_fields, 'baseline reuse proof')
    if (proof['schema_version'] != 1 or proof['kind'] != REUSE_KIND
            or proof['profile'] != selection['profile'] or proof['target'] != recipe['target']
            or proof['paired_sdk_sha256'] != selection['sdk_manifest_sha256']):
        raise ValueError('Baseline reuse proof identity/profile differs')
    inventory(reuse, proof['inventory'], 'reuse-proof.json')
    inventories = {'sources': source_manifest['files'], 'sdk': sdk_data['files'],
                   'reuse': proof['inventory']['files']}
    result = Inspection({key: str(value) if isinstance(value, Path) else value
                         for key, value in selection.items()}, recipe, projection, proof,
                        roots, inventories, selected_profile)
    imports = _validate_proof(result)
    return replace(result, completed_objects=imports)


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
    """Parse the closed copied259 grammar and return explicit directory inputs.

    Compiler/linker positional inputs, outputs, response/config files, plugins,
    arbitrary setting names, transforms and other auxiliary commands have no
    grammar production. Structured source/objects/archives/pre-JS/host-library/
    data records remain the only other filename-bearing command inputs.
    """
    if type(arguments) is not list or any(type(arg) is not str or not arg or '\x00' in arg
                                          or '\n' in arg or '\r' in arg for arg in arguments):
        raise ValueError('Expected exact nonempty argument arrays')
    selected = inspection.profile if inspection is not None else profile()
    literals = set(selected['link_literals' if link else 'compile_literals'])
    dependencies, settings, index = [], {}, 0
    while index < len(arguments):
        arg = arguments[index]
        if arg == '-lexports.js' and not link:
            raise ValueError('Raw export preservation is a link-only policy')
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
            raise ValueError('Argument is outside the reviewed copied259 grammar: ' + arg)
        index += 1
    if link and (settings != selected['link_settings'] or '--no-entry' not in arguments
                 or arguments.count('-lexports.js') != 1):
        raise ValueError('Final link must declare the complete fixed neutral factory policy')
    return list(dict.fromkeys(dependencies))


def _exception_policy(arguments):
    values = [arg == '-fexceptions' for arg in arguments if arg in ('-fexceptions', '-fno-exceptions')]
    return values[-1] if values else None


def _settings(arguments):
    selected = profile()
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


def _header_identity(inspection):
    """Restore only physically proven original aliases, never equal-byte guesses.

    The complete copied-input receipt is retained as an inventoried authority.
    Its original seven-field identities distinguish unrelated identical headers;
    ordinary relocated files intentionally have different current identities.
    Header postimages require a separate explicit successor contract.
    """
    if 'header_identity' not in inspection.proof:
        return None
    reference = inspection.proof['header_identity']
    fields(reference, REFERENCE_FIELDS, 'header identity reference')
    if reference['root'] not in ('sources', 'reuse'):
        raise ValueError('Header identity record must be a retained source/reuse input')
    resolve = lambda ref: ref_path(ref, inspection.roots, inspection.inventories)
    record_path = resolve(reference)
    record = checked_document(record_path, reference['sha256'])
    fields(record, ('schema_version', 'kind', 'projection_sha256', 'evidence_sha256',
                    'classes', 'postimages'), 'header identity record')
    if (type(record['schema_version']) is not int or record['schema_version'] != 1
            or record['kind'] != 'foundation-copied259-header-identity-v1'
            or record['projection_sha256'] != inspection.selection['projection_sha256']
            or record['postimages'] != []):
        raise ValueError('Unsupported header identity/postimage contract')
    if any(name.startswith('source/engine/') and Path(name).suffix.lower() in
           ('.h', '.hpp', '.hh', '.hxx', '.inc', '.inl')
           for name in inspection.projection['files']):
        raise ValueError('Projected engine header postimages require an explicit successor contract')
    evidence = record['evidence_sha256']
    fields(evidence, ('discovery', 'copy_set', 'copy_receipt'), 'header identity evidence')
    for key, value in evidence.items():
        sha(value, 'header identity ' + key)
    receipts = [dict(root=root, path=name, sha256=value)
                for root in ('sources', 'reuse')
                for name, value in inspection.inventories[root].items()
                if value == evidence['copy_receipt']]
    if len(receipts) != 1:
        raise ValueError('Retain exactly one inventoried original header copy receipt')
    receipt_path = resolve(receipts[0])
    receipt = checked_document(receipt_path, evidence['copy_receipt'])
    if (type(receipt) is not dict or type(receipt.get('schema_version')) is not int
            or receipt['schema_version'] != 1
            or receipt.get('kind') != 'closed-unpublished-baseline-copy-v1'
            or receipt.get('status') != 'closed-exact-readback-passed-unpublished'
            or type(receipt.get('files')) is not dict or not receipt['files']):
        raise ValueError('Invalid original header copy receipt')
    original_classes = {}
    for name, item in receipt['files'].items():
        manifest.path_name(name)
        if type(item) is not dict or 'source_identity' not in item:
            raise ValueError('Missing original copied-file physical identity')
        identity = item.get('source_identity') if type(item) is dict else None
        sha(item.get('sha256'), 'original copied file')
        if type(item.get('bytes')) is not int or item['bytes'] < 0:
            raise ValueError('Invalid original copied-file byte count')
        # The copier also retained metadata that it generated itself. It has no
        # original physical identity and can never authorize an alias mapping.
        if identity is None:
            continue
        if (type(identity) is not list or len(identity) != 7
                or any(type(part) is not int or part < 0 for part in identity)
                or not stat.S_ISREG(identity[2]) or identity[3] < 1
                or type(item.get('bytes')) is not int or item['bytes'] != identity[4]):
            raise ValueError('Invalid original copied-file physical identity')
        original_classes.setdefault(tuple(identity), set()).add(name)
    multiple = {identity: names for identity, names in original_classes.items() if len(names) > 1}
    if type(record['classes']) is not list or not record['classes']:
        raise ValueError('Header identity classes must be explicit and nonempty')
    paths, identities, roots = set(), set(), []
    dependencies = [record_path, receipt_path]
    for group in record['classes']:
        fields(group, ('original_identity', 'canonical', 'aliases'), 'header identity class')
        identity = group['original_identity']
        if (type(identity) is not list or len(identity) != 7
                or any(type(part) is not int or part < 0 for part in identity)
                or not stat.S_ISREG(identity[2]) or identity[3] < 1):
            raise ValueError('Invalid original header physical identity')
        identity = tuple(identity)
        if identity in identities or identity not in multiple:
            raise ValueError('Duplicate/unproven original header identity class')
        identities.add(identity)
        if type(group['aliases']) is not list or not group['aliases']:
            raise ValueError('Header identity class requires explicit aliases')
        names, canonical, wanted = set(), None, None
        for ref in [group['canonical'], *group['aliases']]:
            fields(ref, REFERENCE_FIELDS, 'header identity member')
            if ref['root'] != 'reuse':
                raise ValueError('Header identity members must be copied baseline inputs')
            path = resolve(ref)
            name = ref['path']
            original = receipt['files'].get(name, {})
            if (path in paths or original.get('source_identity') != list(identity)
                    or original.get('sha256') != ref['sha256']
                    or original.get('bytes') != identity[4] or path.stat().st_size != identity[4]):
                raise ValueError('Header identity member differs from its original copied-file provenance')
            paths.add(path); names.add(name); dependencies.append(path)
            if canonical is None:
                canonical, wanted = path, ref['sha256']
            elif ref['sha256'] != wanted:
                raise ValueError('Original header aliases must retain identical bytes')
            else:
                roots.append({'type': 'file', 'name': str(path), 'external-contents': str(canonical)})
        if names != multiple[identity]:
            raise ValueError('Header identity class omits/relabels an original copied alias')
    if identities != set(multiple):
        raise ValueError('Header identity record omits original copied alias classes')
    overlay = {'version': 0, 'case-sensitive': True, 'use-external-names': False,
               'overlay-relative': False, 'fallthrough': True,
               'roots': sorted(roots, key=lambda item: item['name'])}
    return {'overlay': overlay, 'dependencies': dependencies, 'mapping_count': len(roots),
            'record_ref': reference}


def _write_header_identity(inspection, output):
    view = _header_identity(inspection)
    if view is None:
        return None
    path = output / 'private/header-identity-vfs.json'
    _save(path, view['overlay'])
    return dict(view, path=path, sha256=digest(path))


def _check_header_identity(view):
    if view is not None:
        checked_read(view['path'], view['sha256'])


def _validate_proof(inspection):
    p, config = inspection.proof, inspection.profile
    roots, inventories = inspection.roots, inspection.inventories
    resolve = lambda ref: ref_path(ref, roots, inventories)
    fields(p['baseline'], ('origin', 'original_receipt', 'source_identity',
           'configuration_identity', 'recorded_scopes', 'command_records', 'original_root'), 'original baseline')
    for name in ('origin', 'source_identity', 'configuration_identity'):
        manifest.text(p['baseline'][name], 'baseline ' + name)
    if not p['baseline']['recorded_scopes'] or type(p['recovery_limits']) is not list:
        raise ValueError('State original baseline scopes and recovery limits')
    resolve(p['baseline']['original_receipt'])
    original_root = Path(p['baseline']['original_root'])
    if not original_root.is_absolute() or '..' in original_root.parts:
        raise ValueError('Original baseline root must be an explicit lexical absolute path')
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
    expected = config['wrapper_objects'] + config['engine_objects']
    if type(objects) is not list or len(objects) != 24 or [o.get('id') for o in objects] != expected:
        raise ValueError('Expected the exact ordered 18 wrapper and six engine object recipes')
    for obj in objects:
        fields(obj, ('id', 'source', 'arguments', 'dependencies', 'original_command_sha256',
                    'unified_members', 'exceptions'), 'object recipe')
        source = resolve(obj['source'])
        if (obj['source']['root'] != 'sources'
                or inspection.projection['files'].get(obj['source']['path'], {}).get('sha256') != obj['source']['sha256']):
            raise ValueError('Every selected owner TU must belong to the explicit final-source projection')
        if source.name != obj['id'] or '/spike/' in source.as_posix() or source.name == 'BibEngineProviderBinding.cpp':
            raise ValueError('Unselected or mismatched object source')
        sha(obj['original_command_sha256'], 'original compile command')
        if obj['original_command_sha256'] not in commands['commands']:
            raise ValueError('Object original command is absent from retained records')
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
    if sum(o['exceptions'] for o in objects) != 12:
        raise ValueError('Exactly twelve declared wrapper/helper objects enable exceptions')
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
            if member['ordinal'] != ordinal or member['name'] in names:
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
    if type(replacements) is not list or len(replacements) != 6:
        raise ValueError('Exactly six ordinal substitutions are required')
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
                or replacement_obj['original_command_sha256'] != old['compile_command_sha256']):
            raise ValueError('Replacement does not remove its actual original owner member')
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
    fields(p['metadata'], ('generator', 'prelink_plan', 'contract_header'), 'metadata inputs')
    if p['metadata']['generator']['path'] != config['metadata_generator']:
        raise ValueError('Use the retained real copied metadata generator')
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
    _header_identity(inspection)
    return engine_donor.validate(inspection, sys.modules[__name__])


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


def make_plan(selection, output):
    inspected = inspect_inputs(selection)
    output = engine_sdk.new_destination(output, tuple(inspected.roots.values()))
    plan = {'schema_version': 1, 'kind': PLAN_KIND, 'scope': SCOPE,
            'selection': inspected.selection, 'profile_sha256': digest(ROOT / PROFILE_PATH),
            'producer_inputs': {name: digest(ROOT / name) for name in REQUIRED_HELPERS},
            'reuse': inspected.proof, 'projection': inspected.projection,
            'production_eligible': False}
    with engine_sdk._OwnedTree(output.parent, '.engine-plan-') as staged:
        (staged.path / 'plan.json').write_bytes(encoded(plan))
        staged.publish(output)
    return {'scope': SCOPE, 'plan': str(output / 'plan.json'),
            'plan_sha256': digest(output / 'plan.json'), 'production_eligible': False}


def verify_plan(path, expected_sha256):
    value = checked_document(path, expected_sha256)
    fields(value, ('schema_version', 'kind', 'scope', 'selection', 'profile_sha256',
                  'producer_inputs', 'reuse', 'projection', 'production_eligible'), 'maintenance plan')
    if (value['schema_version'] != 1 or value['kind'] != PLAN_KIND or value['scope'] != SCOPE
            or value['production_eligible'] is not False
            or value['profile_sha256'] != digest(ROOT / PROFILE_PATH)
            or value['producer_inputs'] != {name: digest(ROOT / name) for name in REQUIRED_HELPERS}):
        raise ValueError('Plan producer/profile identity changed; create a fresh plan')
    inspected = inspect_inputs(value['selection'])
    if inspected.proof != value['reuse'] or inspected.projection != value['projection']:
        raise ValueError('Plan selected inputs changed')
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
    bindings = dict(roots, build=build_root, generated=build_root / 'copied-generated')
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


def _supervise(argv, cwd, log, environment, timeout):
    with log.open('xb') as stream:
        owner = process_tree.launch([str(arg) for arg in argv], str(cwd), stream, env=environment)
        try:
            try:
                process_id = getattr(getattr(owner, 'process', None), 'pid', None)
                _save(log.with_suffix('.process.json'), {'owner_process_id': process_id,
                    'argv': list(map(str, argv)), 'cwd': str(cwd), 'completed': False})
                code = owner.wait(timeout=timeout)
                owner.finish()
            except BaseException:
                owner.terminate()
                raise
        finally:
            owner.close()
    if code != 0:
        raise ValueError('Maintenance phase failed; inspect ' + str(log))
    result = {'argv': [str(arg) for arg in argv], 'cwd': str(cwd), 'returncode': code,
              'owner_process_id': process_id, 'writers_finished': True,
              'log': str(log), 'log_sha256': digest(log)}
    _save(log.with_suffix('.complete.json'), result)
    return result


def _graph(inspected, plan, plan_path, plan_hash, output):
    p, roots = inspected.proof, inspected.roots
    resolve = lambda ref: str(ref_path(ref, roots, inspected.inventories))
    tools = {key: str(_tool(value)) for key, value in p['host_tools'].items()}
    sdk_tools = {key: str(roots['sdk'] / value['path']) for key, value in p['sdk_tools'].items()}
    values = {'FOUNDATION_ENGINE_GRAPH_VERSION': ['1']}
    identity = _header_identity(inspected)
    view_path = output / 'private/header-identity-vfs.json'
    compiler_view = ['-ivfsoverlay', str(view_path)] if identity is not None else []
    def put(name, *arguments):
        values[name] = [str(arg) for arg in arguments]
    helper = roots['sources'] / SELF_PATH
    internal = [tools['python'], '-BE', str(helper), '_step', '--plan', str(plan_path),
                '--plan-sha256', plan_hash, '--build-root', str(output)]
    header, provider = output / 'copied-generated/BibCopiedMetadata.generated.h', output / 'copied-generated/provider-build.json'
    put('ENGINE_HEADER', header); put('ENGINE_PROVIDER_BUILD', provider)
    metadata = p['metadata']
    metadata_command = [tools['python'], '-BE', resolve(metadata['generator']),
        '--source-root', roots['sources'], '--build-root', output,
        '--recipe', roots['sources'] / 'recipe.json', '--build-plan', resolve(metadata['prelink_plan']),
        '--contract-header', resolve(metadata['contract_header']),
        '--output-header', header, '--output-build', provider]
    put('ENGINE_METADATA_COMMAND', *metadata_command)
    put('ENGINE_METADATA_DEPENDS', *(resolve(ref) for ref in metadata.values()),
        *(roots['sources'] / name for name in REQUIRED_HELPERS), roots['sources'] / 'recipe.json')
    imports = getattr(inspected, 'completed_objects', None)
    if p.get('completed_objects') is not None and imports is None:
        imports = engine_donor.validate(inspected, sys.modules[__name__])
    admission = output / 'evidence/completed-object-admission.json'
    if imports is not None:
        _save(admission, {'schema_version': 1, 'kind': engine_donor.KIND + '-admission',
            'record': imports['record'], 'objects': {
                name: item['provenance'] for name, item in imports['objects'].items()}})
        admission_sha256 = digest(admission)
    object_outputs = {}
    ids = []
    for index, obj in enumerate(p['objects']):
        key = 'o' + str(index)
        ids.append(key)
        target = output / ('objects/' + obj['id'] + '.o')
        depfile = Path(str(target) + '.d')
        object_outputs[obj['id']] = target
        put('ENGINE_OBJECT_' + key + '_OUTPUT', target)
        put('ENGINE_OBJECT_' + key + '_DEPFILE', depfile)
        imported = imports is not None and obj['id'] in imports['objects']
        if imported:
            put('ENGINE_OBJECT_' + key + '_COMMAND', *internal, '--action', 'donor',
                '--object', obj['id'], '--admission-sha256', admission_sha256)
        else:
            put('ENGINE_OBJECT_' + key + '_COMMAND', sdk_tools['emxx'],
                *compiler_view,
                *(_expand(arg, roots, output) for arg in obj['arguments']),
                '-MD', '-MT', target, '-MF', depfile, '-o', target, '-c', resolve(obj['source']))
        dependencies = [resolve(obj['source']),
            *(resolve(ref) for ref in obj['dependencies'] + obj['unified_members']),
            *_arguments(obj['arguments'], inspection=inspected)]
        if identity is not None:
            present = set(dependencies)
            dependencies.extend(str(path) for path in [view_path, *identity['dependencies']]
                                if str(path) not in present)
        if imported:
            dependencies.extend(map(str, [admission, *imports['dependencies']]))
        put('ENGINE_OBJECT_' + key + '_DEPENDS', *dependencies)
    put('ENGINE_OBJECT_IDS', *ids)
    replacements = {(r['archive'], r['ordinal']): r['object_id'] for r in p['replacements']}
    archive_outputs = {}
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
    put('ENGINE_ARCHIVE_NAMES', *(a['name'] for a in p['archives']))
    deps = {Path(ref['path']).name: resolve(ref) for ref in p['link']['dependencies']}
    ordered = [str(archive_outputs[name]) if name in archive_outputs else deps[name]
               for name in p['link']['archives']]
    factory, wasm, linkmap = (output / 'artifacts/foundation-retained-engine.mjs',
                             output / 'artifacts/foundation-retained-engine.wasm',
                             output / 'evidence/engine-link.map')
    put('ENGINE_FACTORY', factory); put('ENGINE_WASM', wasm); put('ENGINE_MAP', linkmap)
    wrapper_outputs = [object_outputs[obj['id']] for obj in p['objects'][:18]]
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
    return tools, fragment, {'metadata': list(map(str, metadata_command)),
        'objects': {obj['id']: values['ENGINE_OBJECT_o' + str(i) + '_COMMAND']
                    for i, obj in enumerate(p['objects'])}, 'link': link_command}


def build(plan_path, expected_sha256, output, *, jobs=2, timeout_seconds=1800):
    plan_path = ordinary(plan_path)
    plan, inspected = verify_plan(plan_path, expected_sha256)
    if type(jobs) is not int or jobs < 1 or type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError('Positive jobs and timeout are required')
    if not sys.platform.startswith('linux'):
        raise ValueError('The initial copied259 producer is Linux-host only')
    output = engine_sdk.new_destination(output, (*inspected.roots.values(), plan_path.parent))
    require_clean()
    output.mkdir(mode=0o755)
    _save(output / 'maintenance-owner.json', {'schema_version': 1,
        'plan_sha256': expected_sha256, 'output': str(output),
        'producer_sha256': digest(ROOT / SELF_PATH)})
    for name in ('copied-generated', 'private/home', 'private/tmp', 'private/user-cache',
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
        identity = _write_header_identity(inspected, output)
        tools, fragment, commands = _graph(inspected, plan, plan_path, expected_sha256, output)
        _save(output / 'evidence/commands.json', commands)
        # Private setup creates no SDK process. Revalidate selected closures after
        # setup and before the first CMake/Ninja/Python/driver program.
        verify_plan(plan_path, expected_sha256)
        _check_header_identity(identity)
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
            _check_header_identity(identity)
            _save(output / ('evidence/' + phase + '-intent.json'), {'argv': argv, 'cwd': str(output)})
            receipts.append(_supervise(argv, output, output / ('logs/' + phase + '.log'), environment, remaining))
        verify_plan(plan_path, expected_sha256)
        _check_header_identity(identity)
        inspection = checked_document(output / 'evidence/artifact-inspection.json')
        result = {'schema_version': 1, 'kind': BUILD_KIND, 'scope': SCOPE,
            'status': 'passed', 'production_eligible': False, 'plan_sha256': expected_sha256,
            'source_recipe_sha256': inspected.selection['recipe_sha256'],
            'sources_sha256': inspected.selection['sources_sha256'],
            'paired_sdk_sha256': inspected.selection['sdk_manifest_sha256'],
            'supervision': receipts, 'inspection': inspection,
            'objects': [{'id': obj['id'], 'sha256': digest(output / ('objects/' + obj['id'] + '.o')),
                         'bytes': (output / ('objects/' + obj['id'] + '.o')).stat().st_size,
                         'command_sha256': hashlib.sha256(encoded(commands['objects'][obj['id']])).hexdigest()}
                        for obj in proof['objects']],
            'commands': {'path': 'evidence/commands.json', 'sha256': digest(output / 'evidence/commands.json')},
            'private_configuration': {'launcher_sha256': digest(launcher), 'config_sha256': digest(config),
                                      'bytecode_policy': 'owned-recursive-python-BE'},
            'host_prerequisites': proof['host_tools'],
            'recovery_limits': proof['recovery_limits'],
            'next_gate': 'original dedicated-Worker runtime evidence and explicit retained group sealing'}
        if identity is not None:
            result['header_identity'] = {'record': identity['record_ref'],
                'path': str(identity['path'].relative_to(output)), 'sha256': identity['sha256'],
                'mapping_count': identity['mapping_count']}
        if getattr(inspected, 'completed_objects', None) is not None:
            imports = inspected.completed_objects
            result['completed_objects'] = {'record': imports['record'],
                'policy': 'retained-original-products-not-fresh-compilation',
                'imports': {name: item['provenance'] for name, item in imports['objects'].items()},
                'compiled': [obj['id'] for obj in proof['objects'] if obj['id'] not in imports['objects']]}
        _save(output / 'maintenance-build.json', result)
        return result
    except BaseException as error:
        # Preserve the owned failed/incomplete work. Never clean SDK pyc after
        # execution or publish a successful receipt from partial outputs.
        _save(output / 'maintenance-failure.json', {'schema_version': 1, 'kind': BUILD_KIND,
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
            # LLVM aligns the index internally with one NUL when the names
            # have odd length. GNU may instead use the outer member padding.
            # Consume the declared names first: extra names, empty names and
            # padding that cannot serve alignment must still fail closed.
            tail = symbols[cursor:]
            if tail and (tail != b'\0' or not cursor & 1):
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


def _step(args):
    # The CMake helper reads the pinned plan itself and immediate artifact inputs,
    # avoiding a complete 351MB+ source/SDK rescan for every archive node.
    plan = checked_document(args.plan, args.plan_sha256)
    if plan.get('kind') != PLAN_KIND or plan.get('production_eligible') is not False:
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
    if args.action == 'donor':
        helper_pin = plan['producer_inputs']['tools/appended_engine_donor.py']
        checked_read(ROOT / 'tools/appended_engine_donor.py', helper_pin)
        reference = p.get('completed_objects')
        if reference is None or reference.get('root') != 'reuse' or args.object == engine_donor.SHIM:
            raise ValueError('Internal donor copy lacks an admitted metadata-independent input')
        inventories = {'sources': {}, 'sdk': {}, 'reuse': p['inventory']['files']}
        record = checked_document(ref_path(reference, roots, inventories))
        admission_pin = sha(args.admission_sha256, 'internal donor admission')
        admission = checked_document(output / 'evidence/completed-object-admission.json', admission_pin)
        fields(admission, ('schema_version', 'kind', 'record', 'objects'), 'internal donor admission')
        if (admission['schema_version'] != 1 or admission['kind'] != engine_donor.KIND + '-admission'
                or admission['record'] != reference or record.get('kind') != engine_donor.KIND):
            raise ValueError('Internal donor admission differs')
        selected = [item for item in record['objects'] if item['id'] == args.object]
        if len(selected) != 1 or args.object not in admission['objects']:
            raise ValueError('Unknown internal donor object')
        provenance = admission['objects'][args.object]
        if provenance['input'] != selected[0]['object'] or provenance['depfile'] != selected[0]['depfile']:
            raise ValueError('Internal donor object provenance differs')
        source = ref_path(selected[0]['object'], roots, inventories)
        ref_path(selected[0]['depfile'], roots, inventories)
        raw = checked_read(source, selected[0]['object']['sha256'])
        destination = output / ('objects/' + args.object + '.o')
        if destination.exists() or destination.is_symlink():
            ordinary(destination).unlink()
        with destination.open('xb') as stream:
            stream.write(raw)
        destination.chmod(0o644)
        if digest(destination) != selected[0]['object']['sha256']:
            raise ValueError('Copied donor object differs on readback')
        dependency_path = Path(str(destination) + '.d')
        if dependency_path.exists() or dependency_path.is_symlink():
            ordinary(dependency_path).unlink()
        def make_name(path):
            return str(path).replace('\\', '\\\\').replace('$', '$$').replace(' ', '\\ ').replace('#', '\\#').replace(':', '\\:')
        with dependency_path.open('x', encoding='utf-8') as stream:
            stream.write(make_name(destination) + ': ' + make_name(source) + '\n')
        report = {'schema_version': 1, 'kind': 'foundation-completed-object-import-v1',
            'object_id': args.object, 'sha256': digest(destination), 'bytes': len(raw),
            'provenance': provenance, 'compiler_executed': False}
        target = output / ('evidence/donor-' + args.object + '.json')
    elif args.action in ('archive', 'repack'):
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
        if (facts['start'] is not None or len(facts['memories']) != 1 or facts['memories'][0]['shared']
                or facts['memories'][0]['memory64'] or facts['memories'][0]['maximum'] is None
                or facts['memories'][0]['maximum'] > 65536):
            raise ValueError('Final engine memory/start facts violate neutral profile')
        names = {item['name'] for item in facts['exports']}
        if not {'bib_engine_wasm_bridge_v1', 'bib_engine_wasm_dispatch_v1', 'malloc', 'free'} <= names:
            raise ValueError('Actual factory lacks required copied exports')
        for item in facts['imports'] + facts['exports']:
            name = item['name'].lstrip('_').lower()
            if name in ('main', 'start', 'bib_eval', 'bib_pump') or name.startswith(('pthread', 'emscripten_thread')):
                raise ValueError('Actual factory exports diagnostic entry')
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
            'provider_build_sha256': digest(output / 'copied-generated/provider-build.json'),
            'generated_header_sha256': digest(output / 'copied-generated/BibCopiedMetadata.generated.h')}
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
    step.add_argument('--action', choices=('repack', 'archive', 'artifacts', 'donor'), required=True, dest='step_action')
    step.add_argument('--archive')
    step.add_argument('--object')
    step.add_argument('--admission-sha256')
    args = parser.parse_args(arguments)
    if args.action == 'plan':
        result = make_plan({name: getattr(args, name) for name in SELECTION_FIELDS}, args.output)
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
        raise SystemExit('engine maintenance: ' + str(error))
