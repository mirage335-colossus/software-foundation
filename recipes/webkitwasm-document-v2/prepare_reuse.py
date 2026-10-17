#!/usr/bin/env python3
"""Prepare a document reuse *metadata fragment*, never a complete reuse root.

Only named, independently pinned metadata is read. Original source/object files,
SDK programs and caches are never inspected, copied or executed. Changed engine
owners require exact original argv, copied source/search/header authority and
literal unified membership. Unchanged members retain their trusted opaque
object identities; no new historical all-source assertion is inferred.
The complete maintenance driver must later admit a separately assembled root.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

ROOT = Path(__file__).absolute().parents[2]
MAX_DOCUMENT = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_COMMANDS = 8192
MAX_FILES = 100000
PREFIX = 'metadata/document-v2/'
PREDECESSOR = PREFIX + 'predecessor/reuse-proof.json'
AUTHORITY_KIND = 'foundation-document-v2-original-source-authority-v1'
ASSEMBLY_KIND = 'foundation-document-v2-reuse-metadata-assembly-v1'
TRUSTED_OPAQUE_PROOF_SHA256 = 'b3bc56608035a272943912a3663432f414a258825e6640b668e3fa0b61c8a567'
SELECTION_FIELDS = ('document_profile', 'baseline_proof', 'baseline_proof_sha256',
    'source_recipe', 'source_recipe_sha256', 'source_manifest', 'source_manifest_sha256',
    'sdk_manifest', 'sdk_manifest_sha256', 'projection', 'projection_sha256',
    'source_authority', 'source_authority_sha256')


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Invalid ' + label + ' fields')


def pin(value, label='metadata pin'):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value) or value == '0' * 64:
        raise ValueError('Invalid nonzero ' + label)
    return value


def document(raw):
    if type(raw) is not bytes or len(raw) > MAX_DOCUMENT:
        raise ValueError('Reuse metadata exceeds 64 MiB')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate reuse metadata field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite reuse metadata value: ' + value)
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
                           parse_constant=invalid)
        # Also reject invalid Unicode and overflowed floating-point literals.
        unicode_values(value)
        encoded(value)
        return value
    except (RecursionError, OverflowError, UnicodeError) as error:
        raise ValueError('Invalid or overdeep reuse metadata') from error


def ordinary(path, *, directory=False):
    if os.name != 'posix':
        raise ValueError('Reuse metadata preparation requires the qualified POSIX adapter')
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or str(path) != os.fspath(path):
        raise ValueError('Metadata paths must be explicit canonical absolute paths')
    for item in reversed((path, *path.parents)):
        state = item.lstat()
        want_directory = item != path or directory
        if (stat.S_ISLNK(state.st_mode)
                or not (stat.S_ISDIR(state.st_mode) if want_directory else stat.S_ISREG(state.st_mode))
                or not want_directory and state.st_nlink != 1):
            raise ValueError('Nonordinary metadata input: ' + str(item))
    return path


def identity(state):
    return (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns,
            state.st_ctime_ns, stat.S_IMODE(state.st_mode), state.st_nlink)


@dataclass(frozen=True)
class Owned:
    path: Path
    raw: bytes
    sha256: str
    identity: tuple


class Reader:
    """Read each named metadata input once; retain exact bytes and identities."""
    def __init__(self):
        self.inputs = {}
        self.total_bytes = 0

    def read(self, path, expected):
        expected = pin(expected)
        path = ordinary(path)
        if path in self.inputs:
            saved = self.inputs[path]
            if saved.sha256 != expected:
                raise ValueError('Conflicting independent pins for one metadata input')
            return saved
        before = identity(path.stat())
        if before[2] > MAX_DOCUMENT or self.total_bytes + before[2] > MAX_TOTAL:
            raise ValueError('Named metadata input byte budget exceeded before reading')
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, 'rb') as stream:
            if identity(os.fstat(stream.fileno())) != before:
                raise ValueError('Metadata changed before reading')
            raw = stream.read(MAX_DOCUMENT + 1)
            if identity(os.fstat(stream.fileno())) != before:
                raise ValueError('Metadata changed while reading')
        if (len(raw) != before[2] or digest(raw) != expected
                or identity(ordinary(path).stat()) != before):
            raise ValueError('Metadata differs from its exact identity/pin: ' + str(path))
        saved = Owned(path, raw, expected, before)
        self.inputs[path] = saved
        self.total_bytes += len(raw)
        return saved

    def json(self, path, expected):
        return document(self.read(path, expected).raw)

    def recheck(self):
        for saved in self.inputs.values():
            if identity(ordinary(saved.path).stat()) != saved.identity:
                raise ValueError('Named metadata input changed before publication')


def _helpers(repository):
    """Use the assembler's exact-byte helper bundle, without import-cache reuse."""
    path = ordinary(repository / 'recipes/webkitwasm-document-v2/assemble_sources.py')
    before = identity(path.stat())
    if before[2] > MAX_DOCUMENT:
        raise ValueError('Oversized source assembler helper')
    with path.open('rb') as stream:
        if identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Assembler changed before reading')
        raw = stream.read(MAX_DOCUMENT + 1)
        if identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Assembler changed while reading')
    if len(raw) != before[2] or identity(ordinary(path).stat()) != before:
        raise ValueError('Assembler helper changed')
    name = '_foundation_document_reuse_source_assembly'
    module = types.ModuleType(name)
    module.__file__ = str(path)
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    driver = module.BUNDLE.load('appended_engine_document_maintenance')
    return module, driver, Owned(path, raw, digest(raw), before)


class PrerequisiteError(ValueError):
    def __init__(self, report):
        super().__init__('Explicit selected source/context authority is required before preparing a reuse proof')
        self.report = report


def reference(root, name, files):
    if name not in files:
        raise ValueError('Metadata reference is absent from its complete inventory: ' + name)
    return {'root': root, 'path': name, 'sha256': pin(files[name], 'inventoried reference')}


def original_name(path, original_root):
    path, original_root = Path(path), Path(original_root)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected exact original absolute source path')
    try:
        return path.relative_to(original_root).as_posix()
    except ValueError:
        raise ValueError('Original primary source escapes its recorded baseline root') from None


def primary_sources(commands, original_root):
    result = {}
    for command_sha, record in commands.items():
        fields(record, ('argv', 'cwd'), 'original argv/cwd record')
        argv, cwd = record['argv'], record['cwd']
        if (type(argv) is not list or not argv or any(type(arg) is not str or not arg
                or any(c in arg for c in ('\0', '\n', '\r')) for arg in argv)
                or type(cwd) is not str or not Path(cwd).is_absolute()
                or '..' in Path(cwd).parts or digest(encoded(record)) != pin(command_sha, 'original command')):
            raise ValueError('Original command hash does not bind exact argv/cwd')
        if argv.count('-c') != 1 or argv.count('-o') != 1:
            raise ValueError('Original command requires one primary source and object output')
        try:
            source = argv[argv.index('-c') + 1]
            output = argv[argv.index('-o') + 1]
        except IndexError:
            raise ValueError('Truncated original source/output operand') from None
        normalized = os.path.normpath(str(Path(source) if Path(source).is_absolute() else Path(cwd) / source))
        original_name(normalized, original_root)
        result[command_sha] = normalized
        output = os.path.normpath(str(Path(output) if Path(output).is_absolute() else Path(cwd) / output))
        original_name(output, original_root)
    return result


def missing_report(commands, receipt, original_root, authority=None):
    sources = primary_sources(commands, original_root)
    missing = []
    unified = []
    observed = {} if authority is None else authority.get('unified_sources', {})
    for command_sha, source in sorted(sources.items()):
        name = original_name(source, original_root)
        if name not in receipt['files']:
            missing.append({'original_command_sha256': command_sha,
                            'original_path': source, 'retained_path': name})
        if Path(name).name.startswith('UnifiedSource-') and name not in observed:
            unified.append({'original_command_sha256': command_sha,
                            'original_path': source, 'retained_path': name})
    return {'schema_version': 1, 'kind': 'foundation-document-v2-reuse-prerequisites-v1',
        'ready': False, 'production_eligible': False,
        'scope': 'named-metadata-only-no-original-source-object-or-SDK-reads',
        'original_root': str(original_root), 'original_commands': len(commands),
        'missing_primary_inputs': missing, 'missing_unified_membership_authority': unified,
        'remaining_namespace_gaps': 'unknown until the selected literal unified membership is supplied'}


def selected_commands(config, commands, original_root):
    by_name = {}
    for command_sha, source in primary_sources(commands, original_root).items():
        by_name.setdefault(Path(source).name, []).append(command_sha)
    selected = {}
    for object_id in config['engine_objects']:
        rule = config['derived_commands'].get(object_id)
        name = object_id if rule is None else rule['donor_source']
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise ValueError('Engine owner requires one exact original argv donor: ' + object_id)
        selected[matches[0]] = commands[matches[0]]
    return selected


def opaque_baseline(old, commands, config, original_root, old_sha256, driver):
    """Retain the exact trusted opaque object tuples, with no body inference."""
    if old_sha256 != TRUSTED_OPAQUE_PROOF_SHA256:
        raise ValueError('Opaque member reuse requires the explicitly admitted original baseline proof')
    if [a['name'] for a in old['archives']] != list(config['archive_members']):
        raise ValueError('Original archive boundaries differ from the closed document profile')
    replacements, seen_owners, opaque = [], set(), []
    for archive in old['archives']:
        fields(archive, ('name', 'input', 'members'), 'original opaque archive')
        ref = archive['input']
        if ref != reference('reuse', ref['path'], old['inventory']['files']):
            raise ValueError('Original opaque archive differs from its complete retained inventory')
        if len(archive['members']) != config['archive_members'][archive['name']]:
            raise ValueError('Original archive member count differs')
        names, basenames = set(), set()
        for ordinal, member in enumerate(archive['members']):
            fields(member, ('ordinal', 'name', 'input', 'bytes', 'compile_command_sha256'), 'original opaque member')
            ref, command_sha = member['input'], member['compile_command_sha256']
            if (type(member['ordinal']) is not int or member['ordinal'] != ordinal
                    or type(member['name']) is not str or not member['name'] or '\0' in member['name']
                    or member['name'] in names or Path(ref['path']).name in basenames
                    or ref != reference('reuse', ref['path'], old['inventory']['files'])
                    or type(member['bytes']) is not int or member['bytes'] < 0
                    or command_sha not in commands):
                raise ValueError('Original opaque member tuple/order/identity differs')
            names.add(member['name']); basenames.add(Path(ref['path']).name)
            relocated_output, source_name = driver._original_output(commands[command_sha],
                Path(original_root), Path('/metadata-only-unmaterialized-root'))
            if relocated_output != Path('/metadata-only-unmaterialized-root') / ref['path']:
                raise ValueError('Original object output differs from its exact archive member reference')
            if source_name in config['engine_objects']:
                expected_archive = 'WTF' if source_name == 'RunLoopGeneric.cpp' else 'WebCore'
                if (source_name in seen_owners or archive['name'] != expected_archive
                        or Path(ref['path']).name != source_name + '.o'):
                    raise ValueError('Engine replacement differs from its actual original ordinal owner')
                seen_owners.add(source_name)
                replacements.append({'archive': archive['name'], 'ordinal': ordinal,
                    'object_id': source_name, 'old_sha256': ref['sha256']})
            else:
                opaque.append({'archive': archive['name'], **member})
    if seen_owners != set(config['engine_objects']):
        raise ValueError('Original archives omit a selected engine replacement')
    return {'kind': 'foundation-engine-trusted-opaque-baseline-v1',
        'predecessor_proof': {'root': 'reuse', 'path': PREDECESSOR,
                              'sha256': old_sha256},
        'original_receipt': old['baseline']['original_receipt'], 'target': old['target'],
        'paired_sdk_sha256': old['paired_sdk_sha256'], 'members': opaque}, replacements


def validate_authority(authority, *, core_receipt, receipt, copy_set, discovery,
                       commands, old_proof_sha256, ledger_sha256, core_receipt_sha256,
                       driver, original_inventory):
    fields(authority, ('schema_version', 'kind', 'baseline_proof_sha256',
        'command_records_sha256', 'core_copy_receipt_sha256', 'original_root',
        'original_bindings', 'evidence', 'context_scope', 'unified_sources',
        'postimages', 'configuration', 'posthoc_observations'), 'original source authority')
    if (type(authority['schema_version']) is not int or authority['schema_version'] != 1
            or authority['kind'] != AUTHORITY_KIND
            or authority['baseline_proof_sha256'] != old_proof_sha256
            or authority['command_records_sha256'] != ledger_sha256
            or authority['core_copy_receipt_sha256'] != core_receipt_sha256):
        raise ValueError('Source authority differs from independently pinned original provenance')
    fields(authority['context_scope'], ('mode', 'observation', 'limits'), 'selected context scope')
    scope = authority['context_scope']
    if (scope['mode'] != 'selected-engine-owners-with-opaque-unchanged-members-v1'
            or type(scope['observation']) is not str or not scope['observation']
            or type(scope['limits']) is not list):
        raise ValueError('State the selected compatibility and opaque-object evidence scope explicitly')
    if (receipt.get('kind') != 'closed-unpublished-baseline-copy-v1'
            or receipt.get('status') != 'closed-exact-readback-passed-unpublished'
            or type(receipt.get('schema_version')) is not int or receipt['schema_version'] != 1
            or type(receipt.get('files')) is not dict or not receipt['files']
            or len(receipt['files']) > MAX_FILES
            or copy_set.get('kind') != 'foundation-original-baseline-prospective-copy-set-v1'
            or type(copy_set.get('entries')) is not list
            or discovery.get('kind') != 'bounded-original-baseline-input-discovery-v1'):
        raise ValueError('Qualified complete copy/identity authority is required')
    for name, item in core_receipt['files'].items():
        current = receipt['files'].get(name, {})
        if any(current.get(key) != item.get(key) for key in ('sha256', 'bytes', 'mode', 'source_identity')):
            raise ValueError('Copy receipt changes original core source authority: ' + name)
    for name, item in receipt['files'].items():
        driver.manifest.path_name(name)
        if type(item) is not dict:
            raise ValueError('Invalid original copied-file record')
        pin(item.get('sha256'), 'original copied-file hash')
        if type(item.get('bytes')) is not int or item['bytes'] < 0 or item.get('mode') not in (0o644, 0o755):
            raise ValueError('Invalid copied-file size or normalized mode')
        source_identity = item.get('source_identity')
        if name == 'provenance/original-command-ledger.json' and source_identity is None:
            continue
        if (type(source_identity) is not list or len(source_identity) != 7
                or any(type(part) is not int or part < 0 for part in source_identity)
                or not stat.S_ISREG(source_identity[2]) or source_identity[3] < 1
                or source_identity[4] != item['bytes']):
            raise ValueError('Missing exact original copied-file identity: ' + name)
        if name in original_inventory and original_inventory[name] != item['sha256']:
            raise ValueError('Supplementary authority changes retained core bytes: ' + name)
    original_root = Path(authority['original_root'])
    fields(authority['original_bindings'], ('sources', 'sdk', 'reuse'), 'original root bindings')
    roots = [Path(value) for value in authority['original_bindings'].values()]
    if (str(original_root) != authority['original_bindings']['reuse']
            or any(not p.is_absolute() or '..' in p.parts for p in roots)
            or len(set(roots)) != 3
            or any(a != b and (a in b.parents or b in a.parents) for a in roots for b in roots)):
        raise ValueError('Original bindings require three exact disjoint historical roots')
    if type(authority['posthoc_observations']) is not list:
        raise ValueError('Post-hoc observation metadata must be an explicit separate list')
    report = missing_report(commands, receipt, original_root, authority)
    if report['missing_primary_inputs'] or report['missing_unified_membership_authority']:
        raise PrerequisiteError(report)
    return original_root


def make_contexts(commands, receipt, authority, sdk_files, sdk_sha256, driver):
    """Generate include-search contexts from explicit original metadata only."""
    original = receipt['files']
    original_files = {name: value['sha256'] for name, value in original.items()}
    bindings = authority['original_bindings']
    primary = primary_sources(commands, authority['original_root'])
    namespace, headers = {}, {}
    translation_units = {'.c', '.cc', '.cpp', '.cxx', '.m', '.mm', '.s'}
    for root, files in (('reuse', original), ('sdk', sdk_files)):
        for name, value in sorted(files.items()):
            value = value['sha256'] if root == 'reuse' else value
            name = driver.manifest.path_name(name)
            pin(value, 'complete original namespace')
            key = '{' + root + '}/' + name
            namespace[key] = value
            if Path(name).suffix.lower() not in translation_units | {'.o', '.a'}:
                headers[key] = value
    inventory_sha = digest(encoded(original))
    namespace_sha, headers_sha = digest(encoded(namespace)), digest(encoded(headers))
    contexts, closures = {}, {}
    used_unified = set()
    for command_sha, command in sorted(commands.items()):
        arguments = driver._original_arguments(command, bindings)
        if driver._relocate_original(command['argv'][0], command['cwd'], bindings) != '{sdk}/upstream/emscripten/em++':
            raise ValueError('Original compiler is not the exact paired direct SDK driver')
        source = primary[command_sha]
        name = original_name(source, authority['original_root'])
        members = []
        if Path(name).name.startswith('UnifiedSource-'):
            observation = authority['unified_sources'][name]
            fields(observation, ('sha256', 'literal_includes', 'members'), 'observed original unified source')
            if observation['sha256'] != original[name]['sha256']:
                raise ValueError('Unified observation differs from its copied original primary source')
            includes, observed_members = observation['literal_includes'], observation['members']
            if (type(includes) is not list or not includes or type(observed_members) is not list
                    or len(includes) != len(observed_members)):
                raise ValueError('Original unified source requires complete ordered literal membership')
            search = [str(Path(source).parent)]
            for operand in driver._include_directories(arguments):
                match = re.fullmatch(r'\{(reuse|sdk)\}(?:/(.+))?', operand)
                if match is None:
                    raise ValueError('Original unified include lookup lacks an admitted original root')
                search.append(str(Path(bindings[match[1]]) / (match[2] or '')))
            for spelling, member in zip(includes, observed_members):
                if (type(spelling) is not str or Path(spelling).is_absolute()
                        or Path(spelling).suffix.lower() not in ('.cpp', '.cc', '.cxx')
                        or any(c in spelling for c in ('\0', '\r', '\n', '"'))):
                    raise ValueError('Unified observation requires exact relative C++ literal includes')
                if member not in original_files:
                    raise PrerequisiteError({'schema_version': 1,
                        'kind': 'foundation-document-v2-reuse-prerequisites-v1', 'ready': False,
                        'production_eligible': False, 'missing_selected_unified_member': {
                            'source': name, 'literal_include': spelling, 'retained_path': member}})
                candidates = []
                for directory in search:
                    absolute = os.path.normpath(str(Path(directory) / spelling))
                    relocated = driver._relocate_original(absolute, command['cwd'], bindings)
                    match = re.fullmatch(r'\{reuse\}/(.+)', relocated)
                    if match and match[1] in original:
                        candidates.append((absolute, match[1]))
                if not candidates or member != candidates[0][1]:
                    raise ValueError('Observed unified member differs from original first include-search match')
                members.append({'original_path': candidates[0][0],
                    'input': reference('reuse', member, original_files)})
            if len({item['original_path'] for item in members}) != len(members):
                raise ValueError('Duplicate original unified member')
            used_unified.add(name)
        closure = {'schema_version': 1, 'kind': 'foundation-engine-original-include-search-v1',
            'directories': driver._include_directories(arguments),
            'original_inventory_sha256': inventory_sha, 'sdk_manifest_sha256': sdk_sha256,
            'namespace_sha256': namespace_sha, 'headers_sha256': headers_sha}
        closure_sha = digest(encoded(closure))
        closures[closure_sha] = closure
        contexts[command_sha] = {'source': {'original_path': source,
                'input': reference('reuse', name, original_files)},
            'headers': [], 'macros': driver._macros(arguments), 'generated_metadata': [],
            'sdk_manifest_sha256': sdk_sha256, 'arguments': arguments,
            'closure_mode': 'include-search-v1', 'unified_members': members,
            'search_closure_sha256': closure_sha}
    if set(authority['unified_sources']) != used_unified:
        raise ValueError('Unified source authority contains unused or unbound observations')
    return {'schema_version': 1, 'kind': 'foundation-engine-original-compile-contexts-v1',
            'contexts': contexts, 'search_closures': closures}


def make_header_identity(receipt, copy_set, authority, projection, projection_sha256,
                         source_files, reuse_files, evidence):
    entries = {}
    for entry in copy_set['entries']:
        name = entry['destination']
        if name in entries:
            raise ValueError('Duplicate copy-set destination')
        entries[name] = entry
    classes = {}
    for name, item in receipt['files'].items():
        if item.get('source_identity') is not None:
            classes.setdefault(tuple(item['source_identity']), []).append(name)
    groups = []
    for physical, names in sorted(classes.items()):
        if len(names) < 2:
            continue
        canonical_names = {entries.get(name, {}).get('expected_resolved_path') for name in names}
        if len(canonical_names) != 1:
            raise ValueError('Original physical aliases lack one exact copy-set canonical path')
        canonical = canonical_names.pop()
        if canonical not in names or len({receipt['files'][n]['sha256'] for n in names}) != 1:
            raise ValueError('Original canonical/alias identity class is incomplete')
        for name in names:
            if entries[name].get('sha256') != receipt['files'][name]['sha256']:
                raise ValueError('Original alias copy-set hash differs from receipt')
        groups.append({'original_identity': list(physical),
            'canonical': reference('reuse', canonical, reuse_files),
            'aliases': [reference('reuse', name, reuse_files) for name in sorted(names) if name != canonical]})
    postimages, seen = [], set()
    for mapping in authority['postimages']:
        fields(mapping, ('original_path', 'source_path'), 'explicit selected source mapping')
        original, selected = mapping['original_path'], mapping['source_path']
        if original in seen:
            raise ValueError('Duplicate original physical postimage mapping')
        seen.add(original)
        before = reference('reuse', original, reuse_files)
        after = reference('sources', selected, source_files)
        if (receipt['files'].get(original, {}).get('sha256') != before['sha256']
                or projection['files'].get(selected, {}).get('sha256') != after['sha256']):
            raise ValueError('Explicit postimage differs from complete original and selected projection')
        postimages.append({'input': before, 'output': after})
    return {'schema_version': 1, 'kind': 'foundation-document-v2-header-identity-v1',
        'projection_sha256': projection_sha256, 'evidence': evidence,
        'classes': groups, 'postimages': sorted(postimages, key=lambda item: item['input']['path'])}


def validate_header_mappings(header, projection, config, contract):
    postimages = {item['input']['path']: item['output'] for item in header['postimages']}
    allowed = {name for names in config['owner_postimages'].values() for name in names}
    if any(ref['path'] not in allowed for ref in postimages.values()):
        raise ValueError('Physical postimages must name explicitly selected engine C++ owner changes')
    changed = []
    for group in header['classes']:
        refs = [group['canonical'], *group['aliases']]
        selected = [postimages.get(ref['path']) for ref in refs]
        if not any(selected):
            continue
        if not all(selected) or len({ref['sha256'] for ref in selected}) != 1:
            raise ValueError('Changed original physical class requires every canonical and alias postimage')
        paths = sorted({ref['path'] for ref in selected})
        if len(paths) > 1:
            changed.append({'canonical': selected[0]['path'], 'paths': paths,
                'preimages': {ref['path']: projection['files'][ref['path']]['preimage_sha256'] for ref in selected},
                'postimages': {ref['path']: ref['sha256'] for ref in selected}})
    if contract.canonical_json(sorted(changed, key=lambda item: item['canonical'])) != contract.canonical_json(
            sorted(projection['physical_alias_groups'], key=lambda item: item['canonical'])):
        raise ValueError('Selected physical alias projection differs from the original proven classes')


def validate_arguments(arguments, config, driver, *, link=False):
    """The driver's closed token grammar, without filesystem/tool discovery."""
    if type(arguments) is not list or any(type(arg) is not str or not arg for arg in arguments):
        raise ValueError('Expected exact nonempty selected argument array')
    if link:
        if arguments.count('-lexports.js') != 1:
            raise ValueError('Selected link requires exactly one literal -lexports.js')
    elif '-lexports.js' in arguments:
        raise ValueError('-lexports.js is a link-only selected argument')
    literals = set(config['link_literals' if link else 'compile_literals'])
    index = 0
    while index < len(arguments):
        arg = arguments[index]
        if arg in literals:
            pass
        elif not link and (arg.startswith('-I') and len(arg) > 2 or arg == '-isystem'):
            if arg == '-isystem':
                index += 1
                if index >= len(arguments):
                    raise ValueError('Missing explicit selected system include')
                operand = arguments[index]
            else:
                operand = arg[2:]
            if operand != '{generated}':
                match = re.fullmatch(r'\{(sources|sdk|reuse)\}(?:/(.+))?', operand)
                if match is None:
                    raise ValueError('Selected include directory lacks an admitted canonical root binding')
                if match[2] is not None:
                    driver.manifest.path_name(match[2])
        elif link and arg.startswith('-s'):
            if arg == '-s':
                index += 1
                if index >= len(arguments):
                    raise ValueError('Missing selected Emscripten setting')
        else:
            raise ValueError('Selected token is outside the closed document grammar: ' + arg)
        index += 1
    if link and (driver._settings(arguments, config) != config['link_settings'] or '--no-entry' not in arguments):
        raise ValueError('Selected link does not retain the complete closed neutral policy')


def make_objects(config, config_sha256, commands, contexts, source_files, projection,
                 header_identity, authority, metadata, driver):
    by_source = {}
    for command_sha, source in primary_sources(commands, authority['original_root']).items():
        by_source.setdefault(Path(source).name, []).append(command_sha)
    postimages = {item['input']['path']: item['output'] for item in header_identity['postimages']}
    configuration = authority['configuration']
    fields(configuration, ('root', 'path', 'sha256'), 'explicit copied configuration')
    if (configuration['root'] != 'reuse'
            or configuration['sha256'] != authority['_reuse_files'].get(configuration['path'])):
        raise ValueError('Selected configuration is absent from copied original authority')
    objects = []
    for object_id in config['direct_objects'] + config['engine_objects']:
        rule = config['derived_commands'].get(object_id)
        donor_name = object_id if rule is None else rule['donor_source']
        donors = by_source.get(donor_name, [])
        if len(donors) != 1:
            raise ValueError('Selected object lacks one exact original donor command: ' + object_id)
        donor = donors[0]
        command = commands[donor]
        arguments = driver._original_arguments(command, authority['original_bindings'])
        source = reference('sources', config['source_bindings'][object_id], source_files)
        if projection['files'].get(source['path'], {}).get('sha256') != source['sha256']:
            raise ValueError('Selected source is absent from exact document projection')
        if rule is None:
            provenance = {'kind': 'original-command-v1', 'command_sha256': donor}
        else:
            for token in rule['remove']:
                if arguments.count(token) != 1:
                    raise ValueError('Derived removal does not name one exact donor token')
                arguments.remove(token)
            arguments.extend(rule['append'])
            provenance = {'kind': 'derived-command-v1', 'donor_command_sha256': donor,
                'profile_sha256': config_sha256, 'source_replacement': {
                    'before': command['argv'][command['argv'].index('-c') + 1], 'after': source},
                'remove': rule['remove'], 'append': rule['append']}
        original_members = contexts['contexts'][donor]['unified_members'] if object_id in config['engine_objects'] else []
        members = [postimages.get(item['input']['path'], item['input']) for item in original_members]
        exceptions = driver._exception_policy(arguments)
        if type(exceptions) is not bool or exceptions != (object_id in config['exceptions']):
            raise ValueError('Exact donor/derived exception policy differs from selected profile')
        validate_arguments(arguments, config, driver)
        required = set(config['owner_postimages'].get(object_id, ()))
        if not required <= {ref['path'] for ref in [source, *members] if ref['root'] == 'sources'}:
            raise ValueError('Selected engine owner omits an exact projected C++ postimage')
        dependencies = [configuration]
        objects.append({'id': object_id, 'source': source, 'arguments': arguments,
            'dependencies': dependencies, 'provenance': provenance, 'unified_members': members,
            'exceptions': exceptions, 'compile_context': {'source': source,
                'headers': dependencies + members, 'macros': driver._macros(arguments),
                'generated_metadata': [metadata[key] for key in sorted(metadata)],
                'sdk_manifest_sha256': authority['_sdk_sha256'], 'arguments': arguments}})
    return objects


def _metadata(config, source_files):
    names = {'generator': config['metadata_generator'],
        'template': 'source/document-provider/runtime/engine-document-copied-metadata.h.in',
        'prelink_plan': 'prelink-plan.json',
        'contract_header': 'include/foundation/appended/engine_provider.h',
        'document_header': 'include/foundation/appended/engine_provider_document_v2.h',
        'document_contract': 'abi/engine/document-v2/contract.json',
        'document_catalog': 'abi/engine/document-v2/catalog.json',
        'document_schema': 'abi/engine/document-v2/schema-definition.json',
        'action_ack': 'abi/engine/document-v2/action-ack.json'}
    if config['document_profile'] in ('physical', 'editor'):
        names['physical_catalog'] = 'abi/engine/physical-input-catalog.json'
    if config['document_profile'] == 'editor':
        names.update({'editor_header': 'abi/appended/engine_editor_protocol.h',
            'editor_contract': 'abi/appended/editor-v1/contract.json',
            'editor_catalog': 'abi/appended/editor-v1/catalog.json',
            'editor_schema': 'abi/appended/editor-v1/binary-schema.json'})
    return {key: reference('sources', name, source_files) for key, name in names.items()}


def posthoc_metadata(reader, references, document_profile):
    """Copy pinned supplementary observations, never original compile authority.

    Editor owner/header derivations have their own closed types. They remain
    separate observations; validate_authority, make_contexts and header mapping
    checks still require the original retained command/source/copy identities.
    """
    editor_states = {
        'editor-cpp-exact-original-owner-proof-v1':
            'derived-named-original-metadata-and-closed-copy-unified-body-evidence-only',
        'editor-unchanged-original-header-identity-join-v1':
            'original-metadata-identity-proof-only-no-header-body-read'}
    outputs = {}
    for ordinal, ref in enumerate(references):
        fields(ref, ('path', 'sha256'), 'separate post-hoc observation metadata')
        saved = reader.read(ref['path'], ref['sha256'])
        value = document(saved.raw)
        generic = (value.get('kind') == 'foundation-document-v2-posthoc-source-observation-v1'
            and value.get('status') == 'copied-readback-passed-posthoc-only')
        editor = (document_profile == 'editor' and value.get('kind') in editor_states
            and type(value.get('schema_version')) is int and value['schema_version'] == 1
            and value.get('state') == editor_states[value['kind']])
        if not generic and not editor:
            raise ValueError('Post-hoc observations cannot masquerade as original copy/build authority')
        outputs[PREFIX + 'posthoc-observations-' + str(ordinal) + '.json'] = saved.raw
    return outputs


def _inventory(original, generated, supplementary, manifest):
    files = dict(original['files'])
    modes = dict(original['modes'])
    directories = set(original['directories'])
    for name, item in supplementary.items():
        if name in files and (files[name] != item['sha256'] or modes[name] != item['mode']):
            raise ValueError('Supplementary inventory changes original retained bytes')
        files[name], modes[name] = item['sha256'], item['mode']
    for name, raw in generated.items():
        if name in files:
            raise ValueError('New metadata collides with immutable original retained input')
        files[name], modes[name] = digest(raw), 0o644
    for name in files:
        for parent in Path(name).parents:
            if str(parent) != '.':
                directories.add(parent.as_posix())
    for name in directories:
        modes[name] = 0o755
    result = {'files': dict(sorted(files.items())), 'directories': sorted(directories),
              'modes': dict(sorted(modes.items()))}
    manifest.inventory_contract(dict(result, schema_version=1), 'reuse-proof.json')
    return result


def prepare(selection, *, repository=ROOT):
    """Read pinned metadata and return owned small outputs; execute no programs."""
    selection = dict(selection)
    fields(selection, SELECTION_FIELDS, 'reuse metadata selection')
    repository = ordinary(repository, directory=True)
    reader = Reader()
    assembly, driver, assembler_owned = _helpers(repository)
    reader.inputs[assembler_owned.path] = assembler_owned
    reader.total_bytes += len(assembler_owned.raw)
    adapter_raw, adapter_saved = assembly.read_small(Path(__file__).absolute())
    adapter_owned = Owned(adapter_saved.path, adapter_raw, digest(adapter_raw), adapter_saved.identity)
    reader.inputs[adapter_owned.path] = adapter_owned
    reader.total_bytes += len(adapter_owned.raw)
    selected = driver.profile_selector(selection['document_profile'])
    config_path = repository / driver.profile_path(selected)
    config_raw, saved_config = assembly.read_small(config_path)
    config = driver.profile(selected)
    if encoded(config) != encoded(document(config_raw)):
        raise ValueError('Maintained profile changed during selection')
    baseline_path = ordinary(selection['baseline_proof'])
    if baseline_path.name != 'reuse-proof.json':
        raise ValueError('Original baseline proof must be its root reuse-proof.json')
    reuse = baseline_path.parent
    original_raw = reader.read(baseline_path, selection['baseline_proof_sha256']).raw
    old = document(original_raw)
    if old.get('kind') != 'foundation-copied259-baseline-reuse-v1':
        raise ValueError('Select an original copied259 proof, never relabel an existing document proof')
    driver.manifest.inventory_contract(dict(old['inventory'], schema_version=1), 'reuse-proof.json')
    ledger_ref = old['baseline']['command_records']
    engine_receipt_ref = old['baseline']['original_receipt']
    def retained_metadata(ref):
        fields(ref, ('root', 'path', 'sha256'), 'original retained metadata reference')
        name = driver.manifest.path_name(ref['path'])
        if ref['root'] != 'reuse' or old['inventory']['files'].get(name) != ref['sha256']:
            raise ValueError('Original metadata reference differs from complete old inventory')
        return reader.read(reuse / name, ref['sha256'])
    ledger_owned = retained_metadata(ledger_ref)
    ledger = document(ledger_owned.raw)
    fields(ledger, ('schema_version', 'kind', 'commands'), 'original command ledger')
    if (type(ledger['schema_version']) is not int or ledger['schema_version'] != 1
            or ledger['kind'] != 'foundation-engine-original-commands-v1'
            or type(ledger['commands']) is not dict or not 1 <= len(ledger['commands']) <= MAX_COMMANDS):
        raise ValueError('Invalid bounded original command ledger')
    retained_metadata(engine_receipt_ref)
    reconstruction_ref = reference('reuse', 'provenance/reconstruction-provenance.json', old['inventory']['files'])
    reconstruction = document(retained_metadata(reconstruction_ref).raw)
    receipts = [(path, value) for path, value in reconstruction['input_records'].items()
                if Path(path).name == 'CORE-COPY-RECEIPT.json']
    if len(receipts) != 1:
        raise ValueError('Original provenance must bind one exact core copy receipt')
    core_path, core_ref = receipts[0]
    core_owned = reader.read(core_path, core_ref['sha256'])
    if len(core_owned.raw) != core_ref['bytes']:
        raise ValueError('Original core receipt byte count differs')
    core_receipt = document(core_owned.raw)
    engine_commands = selected_commands(config, ledger['commands'], old['baseline']['original_root'])
    if selection['source_authority'] is None or selection['source_authority_sha256'] is None:
        if selection['source_authority'] is not None or selection['source_authority_sha256'] is not None:
            raise ValueError('Source authority path and independent pin are required together')
        raise PrerequisiteError(missing_report(engine_commands, core_receipt, old['baseline']['original_root']))
    authority_owned = reader.read(selection['source_authority'], selection['source_authority_sha256'])
    authority = document(authority_owned.raw)
    fields(authority.get('evidence'), ('discovery', 'copy_set', 'copy_receipt'), 'qualified authority references')
    evidence_values, evidence_owned = {}, {}
    for key, ref in authority['evidence'].items():
        fields(ref, ('path', 'sha256'), 'explicit qualified metadata path/pin')
        evidence_owned[key] = reader.read(ref['path'], ref['sha256'])
        evidence_values[key] = document(evidence_owned[key].raw)
    receipt, copy_set, discovery = (evidence_values[key] for key in ('copy_receipt', 'copy_set', 'discovery'))
    if receipt.get('copy_set_sha256') != evidence_owned['copy_set'].sha256:
        raise ValueError('Qualified copy receipt does not bind the exact canonical copy set')
    if evidence_owned['copy_receipt'].sha256 != core_owned.sha256:
        raise ValueError('Opaque baseline compatibility retains the exact original core copy authority')
    source_raw = reader.read(selection['source_recipe'], selection['source_recipe_sha256']).raw
    source_recipe = document(source_raw)
    source_manifest = reader.json(selection['source_manifest'], selection['source_manifest_sha256'])
    driver.manifest.source_contract(source_manifest, source_recipe, selection['source_recipe_sha256'])
    if ((source_recipe['provider']['abi_major'], source_recipe['provider']['abi_minor']) != (1, 1)
            or source_recipe['provider']['format'] != 'browser-module'
            or source_recipe['provider']['binding'] != 'copied-owner-bridge'
            or source_recipe['provider']['header'] != 'include/foundation/appended/engine_provider.h'
            or source_recipe['provider']['header_sha256'] != driver.document_contract.BASE_HEADER_SHA256
            or source_recipe['target'] != old['target'] or source_recipe['options'] != {
                'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'}):
        raise ValueError('Selected source metadata is not the exact document browser successor')
    sdk = reader.json(selection['sdk_manifest'], selection['sdk_manifest_sha256'])
    if (old['paired_sdk_sha256'] != selection['sdk_manifest_sha256']
            or source_recipe['toolchain']['paired_sdk_sha256'] != selection['sdk_manifest_sha256']
            or sdk.get('target', {}).get('triple') != old['target']['triple']):
        raise ValueError('Document source and original proof require the exact independently pinned SDK')
    source_files = source_manifest['files']
    for name in driver.required_helpers(selected):
        reader.read(repository / name, source_files.get(name))
    reader.read(config_path, digest(config_raw))
    projection_owned = reader.read(selection['projection'], selection['projection_sha256'])
    source_root = Path(selection['source_recipe']).parent
    try:
        projection_name = Path(selection['projection']).relative_to(source_root).as_posix()
    except ValueError:
        raise ValueError('Selected projection must be retained in the selected source inventory') from None
    if source_files.get(projection_name) != projection_owned.sha256:
        raise ValueError('Selected projection is not an inventoried source input')
    projection = document(projection_owned.raw)
    assembly._validate_projection(driver, projection, config,
        {name: (types.SimpleNamespace(sha256=value), None) for name, value in source_files.items()})
    original_root = validate_authority(authority, core_receipt=core_receipt,
        receipt=receipt, copy_set=copy_set, discovery=discovery, commands=engine_commands,
        old_proof_sha256=selection['baseline_proof_sha256'], ledger_sha256=ledger_owned.sha256,
        core_receipt_sha256=core_owned.sha256, driver=driver, original_inventory=old['inventory']['files'])
    if str(original_root) != old['baseline']['original_root']:
        raise ValueError('Supplementary authority changes the exact recorded original baseline root')
    reuse_files = {**old['inventory']['files'], **{n: v['sha256'] for n, v in receipt['files'].items()}}
    contexts = make_contexts(engine_commands, receipt, authority, sdk['files'],
                             selection['sdk_manifest_sha256'], driver)
    opaque, replacements = opaque_baseline(old, ledger['commands'], config,
        original_root, selection['baseline_proof_sha256'], driver)
    contexts.update(kind='foundation-engine-selected-and-opaque-compile-contexts-v1',
                    opaque_baseline=opaque)
    outputs = {PREDECESSOR: original_raw,
               PREFIX + 'source-authority.json': authority_owned.raw,
               PREFIX + 'compile-contexts.json': encoded(contexts)}
    evidence = {}
    for key, saved in evidence_owned.items():
        name = PREFIX + 'evidence/' + key.replace('_', '-') + '.json'
        outputs[name] = saved.raw
        evidence[key] = {'root': 'reuse', 'path': name, 'sha256': saved.sha256}
    outputs.update(posthoc_metadata(reader, authority['posthoc_observations'], selected))
    header = make_header_identity(receipt, copy_set, authority, projection,
        selection['projection_sha256'], source_files, reuse_files, evidence)
    validate_header_mappings(header, projection, config, driver.document_contract)
    outputs[PREFIX + 'header-identity.json'] = encoded(header)
    metadata = _metadata(config, source_files)
    construction_authority = dict(authority, _reuse_files=reuse_files,
                                   _sdk_sha256=selection['sdk_manifest_sha256'])
    objects = make_objects(config, digest(config_raw), ledger['commands'], contexts,
        source_files, projection, header, construction_authority, metadata, driver)
    proof = document(original_raw)
    proof.update(kind=driver.REUSE_KIND, profile=config['name'], document_profile=selected,
                 objects=objects, metadata=metadata)
    proof['baseline'].update(original_bindings=authority['original_bindings'],
        compile_contexts={'root': 'reuse', 'path': PREFIX + 'compile-contexts.json',
                          'sha256': digest(outputs[PREFIX + 'compile-contexts.json'])})
    proof['header_identity'] = {'root': 'reuse', 'path': PREFIX + 'header-identity.json',
                                'sha256': digest(outputs[PREFIX + 'header-identity.json'])}
    proof['link']['flags'] = config['link_literals'] + ['-s' + key + '=' + value
        for key, value in config['link_settings'].items()]
    validate_arguments(proof['link']['flags'], config, driver, link=True)
    proof['link']['archives'] = config['link_archive_names']
    for key, name in (('pre_js', 'engine-copied-pre.js'), ('host_library', 'engine-copied-library.js')):
        proof['link'][key] = reference('sources', 'source/document-provider/runtime/' + name, source_files)
    proof['replacements'] = replacements
    proof['recovery_limits'] = list(proof['recovery_limits']) + authority['context_scope']['limits'] + [
        'This metadata fragment has not received complete source/SDK/reuse admission.',
        'Original runtime records keep their original identities and limitations; no new runtime or eligibility result.']
    proof['inventory'] = _inventory(old['inventory'], outputs, receipt['files'], driver.manifest)
    outputs['reuse-proof.json'] = encoded(proof)
    for name, raw in outputs.items():
        driver.manifest.path_name(name)
        if len(raw) > MAX_DOCUMENT:
            raise ValueError('Generated metadata exceeds the driver 64 MiB document contract: ' + name)
    total_output = sum(len(raw) for raw in outputs.values())
    reader.recheck()
    assembly._recheck({'snapshots': [saved_config, *assembly.BUNDLE.snapshots()]})
    summary = {'schema_version': 1, 'kind': ASSEMBLY_KIND, 'document_profile': selected,
            'scope': 'metadata-fragment-no-original-source-object-SDK-copy-or-execution',
            'complete_reuse_root': False, 'production_eligible': False,
            'input_metadata_bytes': reader.total_bytes, 'metadata_root_bytes': total_output,
            'output_metadata_bytes': total_output,
            'input_metadata': [{'path': str(saved.path), 'sha256': saved.sha256, 'bytes': len(saved.raw)}
                               for saved in sorted(reader.inputs.values(), key=lambda item: str(item.path))],
            'original_commands': len(ledger['commands']),
            'selected_original_contexts': len(engine_commands),
            'opaque_unchanged_members': len(opaque['members']),
            'original_archive_members': sum(len(a['members']) for a in proof['archives']),
            'selected_objects': len(objects), 'selected_archive_replacements': len(replacements),
            'reuse_proof_sha256': digest(outputs['reuse-proof.json']),
            'expected_complete_inventory_sha256': digest(encoded(proof['inventory'])),
            'next_action': 'Separately authorize and assemble the unchanged original retained files, then run complete document maintenance admission.'}
    output_refs = {name: {'sha256': digest(raw), 'bytes': len(raw)} for name, raw in sorted(outputs.items())}
    # Byte counts have a short decimal fixed point; no manifest hashes itself.
    for _ in range(4):
        actual_total = total_output + len(encoded(dict(summary, outputs=output_refs)))
        if actual_total == summary['output_metadata_bytes']:
            break
        summary['output_metadata_bytes'] = actual_total
    actual_total = total_output + len(encoded(dict(summary, outputs=output_refs)))
    if actual_total != summary['output_metadata_bytes'] or actual_total > MAX_TOTAL:
        raise ValueError('Generated metadata plus completion receipt exceeds the 256 MiB output budget')
    return {'selection': selection, 'reader': reader, 'assembly': assembly,
        'helper_snapshots': [saved_config, *assembly.BUNDLE.snapshots()],
        'outputs': outputs, 'proof': proof, 'protected_roots': (reuse, source_root, Path(selection['sdk_manifest']).parent),
        'summary': summary}


def save(plan, output):
    """Write one NEW incomplete metadata fragment; ASSEMBLY.json is saved last."""
    output = Path(output)
    if not output.is_absolute() or '..' in output.parts:
        raise ValueError('Metadata output must be an explicit absolute NEW directory')
    ordinary(output.parent, directory=True)
    if output.exists() or output.is_symlink():
        raise ValueError('Metadata output must be new')
    for protected in plan['protected_roots']:
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError('Metadata output must be disjoint from retained source, SDK and reuse roots')
        protected_identity = identity(ordinary(protected, directory=True).stat())[:2]
        if any(identity(ordinary(parent, directory=True).stat())[:2] == protected_identity for parent in output.parents):
            raise ValueError('Metadata output aliases a protected retained root')
    plan['reader'].recheck()
    plan['assembly']._recheck({'snapshots': plan['helper_snapshots']})
    output.mkdir(mode=0o755)
    output.chmod(0o755)
    metadata_root = output / 'metadata-root'
    metadata_root.mkdir(mode=0o755)
    metadata_root.chmod(0o755)
    saved_outputs = {}
    for name, raw in sorted(plan['outputs'].items()):
        path = metadata_root / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        for parent in path.parents:
            if parent == metadata_root:
                break
            parent.chmod(0o755)
        with path.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(raw)
        before = identity(ordinary(path).stat())
        with path.open('rb') as stream:
            if identity(os.fstat(stream.fileno())) != before:
                raise ValueError('Saved metadata changed before readback')
            actual = stream.read(len(raw) + 1)
            after = identity(os.fstat(stream.fileno()))
        if actual != raw or before != after or identity(ordinary(path).stat()) != before:
            raise ValueError('Saved metadata output differs; incomplete fragment retained')
        saved_outputs[name] = {'sha256': digest(raw), 'bytes': len(raw)}
    plan['reader'].recheck()
    plan['assembly']._recheck({'snapshots': plan['helper_snapshots']})
    result = dict(plan['summary'], outputs=saved_outputs)
    with (output / 'ASSEMBLY.json').open('xb') as stream:
        os.fchmod(stream.fileno(), 0o644)
        stream.write(encoded(result))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'prepare'))
    parser.add_argument('--document-profile', choices=('pixel', 'physical', 'editor'), required=True)
    for name in ('baseline-proof', 'source-recipe', 'source-manifest', 'sdk-manifest', 'projection'):
        parser.add_argument('--' + name, type=Path, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--source-authority', type=Path)
    parser.add_argument('--source-authority-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if (args.action == 'prepare') != (args.output is not None):
            raise ValueError('Only prepare requires an explicit NEW --output')
        selection = {key: getattr(args, key) for key in SELECTION_FIELDS}
        plan = prepare(selection)
        result = save(plan, args.output) if args.action == 'prepare' else plan['summary']
        sys.stdout.buffer.write(encoded(result))
        return 0
    except PrerequisiteError as error:
        sys.stdout.buffer.write(encoded(error.report))
        return 2
    except (OSError, ValueError, TypeError, KeyError, ImportError) as error:
        print('document reuse metadata: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
