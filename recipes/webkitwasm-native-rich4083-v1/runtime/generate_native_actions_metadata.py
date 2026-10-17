#!/usr/bin/env python3
"""Generate native document-actions provider metadata from a pinned complete native source group.

Run the exact recipe-retained copy, not this source-candidate checkout. Generation
reads and hashes every declared source input twice (including possibly large
supplier archives), bounded to 32 GiB per pass and 8 GiB per file, without
extracting them or finding/running any SDK/build program. It
never creates a recipe, provider-build, SDK, runtime proof or eligible group.

The output root must already be an empty private POSIX directory, disjoint from
the source group and the original provider-build input. One fresh header is
published atomically without replacing anything. Keep all inputs quiescent and
the output privately owned; hashes are consistency checks, not writer exclusion.
"""
import argparse
import builtins
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import types

sys.dont_write_bytecode = True
GENERATOR = 'source/native/runtime/generate_native_actions_metadata.py'
TEMPLATE = 'source/native/runtime/native-provider-actions-metadata.h.in'
CONFIG = 'source/native/prelink-actions-config.json'
HEADER = 'BibNativeProviderActionsMetadata.generated.h'
SCOPE = 'native-document-actions-provider-metadata-source-integrity-only'
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_INPUTS = 65536
MAX_SOURCE_BYTES = 32 * 1024 * 1024 * 1024
MAX_SOURCE_FILE = 8 * 1024 * 1024 * 1024
HELPERS = ('tools/dependency_archive.py', 'tools/appended_engine_manifest.py',
           'tools/appended_engine_document_contract.py', 'tools/appended_engine_editor_contract.py',
           'tools/appended_engine_native_actions_contract.py')
STDLIB = frozenset(('base64', 'binascii', 'contextlib', 'gzip', 'hashlib', 'json',
    'math', 'os', 'pathlib', 're', 'shutil', 'stat', 'tarfile', 'tempfile', 'types'))
PINS = {
    'base': ('include/foundation/appended/engine_provider.h', 'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d'),
    'extension': ('include/foundation/appended/engine_provider_document_v2.h', '7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626'),
    'document_contract': ('abi/engine/document-v2/contract.json', 'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298'),
    'document_catalog': ('abi/engine/document-v2/catalog.json', '6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5'),
    'schema': ('abi/engine/document-v2/schema-definition.json', 'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d'),
    'ack': ('abi/engine/document-v2/action-ack.json', '1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5'),
    'physical_catalog': ('abi/engine/physical-v1/catalog.json', 'd244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b'),
    'editor_header': ('abi/appended/engine_editor_protocol.h', 'bdd9bf16765513be402481ab85dd596263fd4ac66a0dfc1dcc7ba5314ec85034'),
    'editor_contract': ('abi/appended/editor-v1/contract.json', '0d43707e404979a38e0e8d7a7bc47042be95ae54216ed118a4de3314302b8c9c'),
    'editor_catalog': ('abi/appended/editor-v1/catalog.json', '34fadacf563a00918255e4dc94b196bf0dc5c8ed57c7165e3da1e5fdd4d06bb8'),
    'editor_schema': ('abi/appended/editor-v1/binary-schema.json', 'f2a6202056bd7fb6872539ba1e8806296ae6f6409ab2a21b9b581f19a4c7d4b1'),
    'actions_header': ('include/foundation/appended/engine_provider_document_actions_v1.h', 'e748f399557597c510cbcf457dc96208c7bfd5ebbde3298a7cf3f49e7e05754f'),
    'contract': ('abi/engine/document-actions-v1/contract.json', '33e23c8972497a64956a765b24a61538fe1cfcabe6be80af8e19ceb0e401e221'),
    'catalog': ('abi/engine/document-actions-v1/catalog.json', 'f220358edc36eb083fd567611f5d0ebb5f607fe3fd90e1c83ccd7a85a5690be5'),
    'actions_schema': ('abi/engine/document-actions-v1/binary-schema.json', 'b5603ec73b05ff2efb4b0a9405b98095789de4cc2a950e7b69813a1845cd9d64'),
    'actions_ack': ('abi/engine/document-actions-v1/action-ack.json', 'a4793ce28417ffa97b754344624c9d9d78093acba5792bde006c7b95482dfcbe'),
}
LIMITS = {'size': 48, 'maximum_command_bytes': 1048576, 'maximum_query_bytes': 236,
    'maximum_reply_bytes': 1048576, 'maximum_service_message_bytes': 1048576,
    'maximum_retired_documents': 8, 'maximum_inflight_resources': 64, 'reserved': 0,
    'maximum_resource_response_bytes': 67108864, 'maximum_retained_resource_bytes': 134217728}
RETENTION = {'max_retained_calls': 64, 'max_retained_bytes': 4194304}
PROFILE = 'foundation-engine-copied4083-ndv2-editor-document-actions-v1'
CONFIGURATION = {'kind': 'native-dso-private-document-actions-runtime-v1',
    'actions_profile': PROFILE, 'profile_kind': 4, 'getter': 'bib_engine_get_provider_v1',
    'getter_maximum_minor': 1, 'inert_registration': True,
    'public_exports': ['bib_engine_get_provider_v1'], 'rendering': 'cpu',
    'script_enabled': True, 'thread_model': 'native'}
BUILD_FIELDS = ('schema_version', 'kind', 'target', 'toolchain', 'options',
    'source_recipe_sha256', 'source_inputs_sha256', 'contract_header_sha256',
    'binding', 'configuration', 'capabilities', 'provider_contract', 'provider_limits')


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(value, label):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value) or value == '0' * 64:
        raise ValueError('Required nonzero exact SHA256: ' + label)
    return value


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Invalid closed ' + label + ' fields')


def document(raw):
    if len(raw) > MAX_DOCUMENT:
        raise ValueError('Metadata document exceeds 32 MiB')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite JSON value: ' + value)
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
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
        # Also rejects escaped unpaired Unicode and overflowed numeric floats.
        unicode_values(value)
        encoded(value)
        return value
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid metadata Unicode or nesting') from error


def qualified_posix():
    if (os.name != 'posix' or not all(hasattr(os, name) for name in
            ('O_NOFOLLOW', 'O_DIRECTORY', 'fchmod', 'fsync', 'geteuid'))
            or not {os.open, os.stat, os.link, os.unlink} <= os.supports_dir_fd
            or os.listdir not in os.supports_fd):
        raise ValueError('Native metadata requires qualified POSIX descriptor publication primitives')


def identity(state):
    return (state.st_dev, state.st_ino, state.st_mode, state.st_nlink,
            state.st_size, state.st_mtime_ns, state.st_ctime_ns)


def ordinary(path, directory):
    raw = os.fspath(path)
    path = Path(raw)
    if not path.is_absolute() or str(path) != raw or '..' in path.parts:
        raise ValueError('Paths must be explicit normalized absolute paths')
    for part in reversed((path, *path.parents)):
        state = part.lstat()
        wanted = directory if part == path else True
        if (not (stat.S_ISDIR(state.st_mode) if wanted else stat.S_ISREG(state.st_mode))
                or stat.S_ISLNK(state.st_mode) or not wanted and state.st_nlink != 1):
            raise ValueError('Paths must be ordinary unlinked entries: ' + str(part))
    return path


def read_file(path, maximum=MAX_DOCUMENT):
    path = ordinary(path, False)
    before = identity(path.stat())
    if before[4] > maximum:
        raise ValueError('Metadata input exceeds its bound: ' + str(path))
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Input changed before read: ' + str(path))
        raw = stream.read(maximum + 1)
        after = identity(os.fstat(stream.fileno()))
    if len(raw) > maximum or after != before or identity(ordinary(path, False).stat()) != before:
        raise ValueError('Input changed during read: ' + str(path))
    return raw


def relative(name):
    if type(name) is not str or not name or len(name) > 4096:
        raise ValueError('Invalid retained relative path')
    for part in name.split('/'):
        stem = part.split('.')[0].rstrip(' ').lower()
        if (not part or part in ('.', '..') or part.endswith((' ', '.'))
                or stem in {'con', 'prn', 'aux', 'nul', 'conin$', 'conout$',
                    *('com' + str(n) for n in range(1, 10)), *('lpt' + str(n) for n in range(1, 10))}
                or any(ord(c) < 32 or ord(c) >= 127 or c in '\\:<>"|?*' for c in part)):
            raise ValueError('Invalid portable retained relative path')
    return name


def source_snapshot(root, recipe, raw_recipe, sources, raw_sources):
    inputs = recipe.get('inputs') if type(recipe) is dict else None
    if type(inputs) is not dict or not 1 <= len(inputs) <= MAX_INPUTS:
        raise ValueError('An actual complete retained native recipe is required; source-candidate maps are ineligible')
    expected = {'recipe.json': {'sha256': digest(raw_recipe), 'mode': 0o644},
                'sources.json': {'sha256': digest(raw_sources), 'mode': 0o644}}
    for name, item in inputs.items():
        relative(name)
        fields(item, ('sha256', 'role', 'mode'), 'recipe input')
        sha(item['sha256'], name)
        if name in expected or Path(name).name in (HEADER, 'provider-build.json', 'engine-sdk.json'):
            raise ValueError('Generated/circular output cannot be a native recipe input: ' + name)
        expected[name] = item
    directories = sources.get('directories') if type(sources) is dict else None
    if type(directories) is not list or len(directories) > MAX_INPUTS * 8:
        raise ValueError('Complete bounded source manifest is required')
    expected_directories = set(relative(name) for name in directories)
    records, directory_records, total = {}, {}, 0
    def walk(parent, prefix, depth=0):
        nonlocal total
        if depth > 128:
            raise ValueError('Retained source directory depth exceeds 128')
        directory_records[prefix] = (parent.stat().st_dev, parent.stat().st_ino, stat.S_IMODE(parent.stat().st_mode))
        for child in sorted(parent.iterdir()):
            name = prefix + '/' + child.name if prefix else child.name
            relative(name)
            state = child.lstat()
            if stat.S_ISDIR(state.st_mode):
                if name not in expected_directories or stat.S_IMODE(state.st_mode) != 0o755:
                    raise ValueError('Unlisted or invalid retained source directory: ' + name)
                walk(ordinary(child, True), name, depth + 1)
            else:
                if name not in expected:
                    raise ValueError('Unlisted retained source file: ' + name)
                ordinary(child, False)
                if stat.S_IMODE(state.st_mode) != expected[name]['mode'] or state.st_size > MAX_SOURCE_FILE:
                    raise ValueError('Retained source mode/size differs: ' + name)
                total += state.st_size
                if total > MAX_SOURCE_BYTES:
                    raise ValueError('Complete retained source input exceeds 32 GiB')
                before = identity(state)
                value = hashlib.sha256()
                count = 0
                with os.fdopen(os.open(child, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
                    if identity(os.fstat(stream.fileno())) != before:
                        raise ValueError('Retained input changed before hashing: ' + name)
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        count += len(block)
                        if count > state.st_size:
                            raise ValueError('Retained input grew during hashing: ' + name)
                        value.update(block)
                    after = identity(os.fstat(stream.fileno()))
                if after != before or identity(ordinary(child, False).stat()) != before or value.hexdigest() != expected[name]['sha256']:
                    raise ValueError('Retained input changed or hash differs: ' + name)
                records[name] = before
    walk(root, '')
    if set(records) != set(expected) or set(directory_records) != {''} | expected_directories:
        raise ValueError('Complete retained source files/directories differ')
    return records, directory_records


def retained(root, inputs, name, role):
    item = inputs.get(name)
    if type(item) is not dict or item.get('role') != role:
        raise ValueError('Required exact recipe input/role missing: ' + name)
    raw = read_file(root / name)
    if digest(raw) != item['sha256']:
        raise ValueError('Required recipe input hash differs: ' + name)
    return raw


def load_helpers(root, inputs):
    raw = {name: retained(root, inputs, name, 'helper') for name in HELPERS}
    modules = {}
    def importer(name, globals=None, locals=None, fromlist=(), level=0):
        if level:
            raise ValueError('Relative retained helper import is ineligible')
        if 'tools/' + name + '.py' in HELPERS:
            return load(name)
        if name not in STDLIB:
            raise ValueError('Unpinned retained helper import: ' + name)
        return builtins.__import__(name, globals, locals, fromlist, level)
    def load(name):
        if name not in modules:
            path = 'tools/' + name + '.py'
            module = types.ModuleType('_native_metadata_' + name)
            module.__file__ = str(root / path)
            module.__dict__['__builtins__'] = {**vars(builtins), '__import__': importer}
            modules[name] = module
            exec(compile(raw[path], module.__file__, 'exec'), module.__dict__)
        return modules[name]
    # The fixed-actions helper and its complete pure transitive closure are private.
    # No SDK/helper consumer code is executed and ambient helper modules are ignored.
    return load('appended_engine_manifest'), load('appended_engine_native_actions_contract')


def expected_config():
    return {'schema_version': 1, 'kind': 'foundation-native-provider-actions-prelink-config-v1',
        'document_profile': PROFILE, 'profile_kind': 4,
        'provider_limits': LIMITS, 'service_retention': RETENTION}


def expected_build(recipe, recipe_sha256, contract):
    return {'schema_version': 1, 'kind': 'foundation-neutral-engine-provider-native-document-actions-v1-build-v1',
        'target': recipe['target'], 'toolchain': recipe['toolchain'], 'options': recipe['options'],
        'source_recipe_sha256': recipe_sha256, 'source_inputs_sha256': digest(encoded(recipe['inputs'])),
        'contract_header_sha256': PINS['contract'][1], 'binding': 'private-native',
        'configuration': CONFIGURATION, 'capabilities': '4083',
        'provider_contract': contract.actions_provider_contract(kernel_target=recipe['target']),
        'provider_limits': LIMITS}


def checked_catalog(raw, expected):
    value = document(raw)
    for family in ('queries', 'commands'):
        records = value.get(family) if type(value) is dict else None
        if type(records) is not list:
            raise ValueError('Pinned actions catalog has no operation array: ' + family)
        selected = []
        for record in records:
            if type(record) is not dict:
                raise ValueError('Invalid pinned actions catalog operation')
            selected.append({name: str(record[name]) if name == 'capability' else record[name]
                for name in ('operation', 'maximum_input_bytes', 'required_reply_capacity', 'capability', 'schema_sha256')})
        if encoded(selected) != encoded(expected[family]):
            raise ValueError('Pinned actions catalog differs from native helper operations: ' + family)


def checked_profile(profile, target, recipe_sha256, build_sha256):
    expected = {'schema_version': 1, 'kind': 'foundation-native-engine-document-actions-v1',
        'binding': 'private-native', 'target': target, 'profile_kind': 4, 'actions_profile': PROFILE,
        'provider_abi_major': 1, 'provider_abi_minor': 1, 'host_abi_major': 1, 'host_abi_minor': 0,
        'lifetime': 1, 'maximum_starts': 1, 'viewport_width': 800, 'viewport_height': 600,
        'capabilities': '4083', 'base_header_sha256': PINS['base'][1],
        'document_header_sha256': PINS['extension'][1], 'document_contract_sha256': PINS['document_contract'][1],
        'document_catalog_sha256': PINS['document_catalog'][1], 'document_schema_sha256': PINS['schema'][1],
        'action_ack_schema_sha256': PINS['ack'][1], 'physical_catalog_sha256': PINS['physical_catalog'][1],
        'editor_profile': 'foundation-engine-copied2035-ndv2-editor-v1',
        'editor_header_sha256': PINS['editor_header'][1], 'editor_contract_sha256': PINS['editor_contract'][1],
        'editor_catalog_sha256': PINS['editor_catalog'][1], 'editor_schema_sha256': PINS['editor_schema'][1],
        'actions_header_sha256': PINS['actions_header'][1], 'contract_sha256': PINS['contract'][1],
        'actions_catalog_sha256': PINS['catalog'][1], 'actions_schema_sha256': PINS['actions_schema'][1],
        'actions_ack_schema_sha256': PINS['actions_ack'][1], 'surface_capabilities': '8255',
        'surface_protocol_version': 2, 'editor_protocol_version': 1,
        'editor_command_max_bytes': 1048576, 'editor_query_max_bytes': 236, 'editor_reply_capacity': 1048576,
        'build_sha256': build_sha256, 'source_recipe_sha256': recipe_sha256}
    if encoded(profile) != encoded(expected):
        raise ValueError('Native actions helper profile closure or source/build/target joins differ')


def checked_provider_contract(value, target):
    fields(value, ('provider_abi', 'host_abi', 'getter_maximum_minor', 'target',
        'lifetime', 'maximum_starts', 'queries', 'commands'), 'native actions provider contract')
    system, processor = {('Linux', 'x86_64'): (1, 1), ('Linux', 'aarch64'): (1, 2),
        ('Windows', 'x86_64'): (2, 1)}[(target['system'], target['processor'])]
    expected = {'provider_abi': {'major': 1, 'minor': 1}, 'host_abi': {'major': 1, 'minor': 0},
        'getter_maximum_minor': 1, 'target': {'system': system, 'processor': processor, 'pointer_bits': 64},
        'lifetime': 1, 'maximum_starts': 1}
    if encoded({name: value[name] for name in expected}) != encoded(expected):
        raise ValueError('Native actions helper ABI/target/lifetime differs')


def operation_literal(record):
    # Fields have already matched the closed typed helper and pinned catalog.
    return '{' + ','.join((str(record['operation']), str(record['maximum_input_bytes']),
        str(record['required_reply_capacity']), 'UINT64_C(' + record['capability'] + ')',
        '{' + digest_literal(record['schema_sha256']) + '}')) + '}'


def digest_literal(value):
    sha(value, 'generated digest')
    return ','.join('0x' + value[n:n + 2] for n in range(0, 64, 2))


def directory_entries(descriptor, expected_identity):
    # Some filesystems retain a stale enumeration on a reused open directory.
    # Open a fresh description through the retained inode anchor, never its path.
    fresh = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
    try:
        for state in (os.fstat(descriptor), os.fstat(fresh)):
            if not stat.S_ISDIR(state.st_mode) or (state.st_dev, state.st_ino) != expected_identity:
                raise ValueError('Output directory descriptor identity changed before listing')
        entries = os.listdir(fresh)
        for state in (os.fstat(descriptor), os.fstat(fresh)):
            if not stat.S_ISDIR(state.st_mode) or (state.st_dev, state.st_ino) != expected_identity:
                raise ValueError('Output directory descriptor identity changed during listing')
        return entries
    finally:
        os.close(fresh)


def publish(root, raw, source_directories):
    ordinary(root, True)
    state = root.stat()
    if state.st_uid != os.geteuid() or stat.S_IMODE(state.st_mode) != 0o700:
        raise ValueError('Output root must be caller-owned and private mode0700')
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.native-metadata-' + secrets.token_hex(16)
    created = False
    temporary_identity = None
    try:
        root_identity = (state.st_dev, state.st_ino)
        if (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino) != root_identity or root_identity in source_directories:
            raise ValueError('Output root identity changed or aliases retained source')
        if directory_entries(descriptor, root_identity):
            raise ValueError('Output root must be fresh and empty; never replace existing metadata')
        output_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
        created = True
        with os.fdopen(output_fd, 'wb') as stream:
            temporary_identity = (os.fstat(stream.fileno()).st_dev, os.fstat(stream.fileno()).st_ino)
            stream.write(raw)
            os.fchmod(stream.fileno(), 0o644)
            stream.flush()
            os.fsync(stream.fileno())
        current = ordinary(root, True).stat()
        saved = os.stat(temporary, dir_fd=descriptor, follow_symlinks=False)
        if ((current.st_dev, current.st_ino) != root_identity or directory_entries(descriptor, root_identity) != [temporary]
                or (saved.st_dev, saved.st_ino) != temporary_identity or saved.st_nlink != 1
                or not stat.S_ISREG(saved.st_mode) or saved.st_size != len(raw)):
            raise ValueError('Private output state changed before publication')
        with os.fdopen(os.open(temporary, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor), 'rb') as stream:
            before = identity(os.fstat(stream.fileno()))
            saved_raw = stream.read(MAX_DOCUMENT + 1)
            after = identity(os.fstat(stream.fileno()))
        if before != after or before != identity(saved) or saved_raw != raw:
            raise ValueError('Temporary output bytes changed before publication')
        # Link is atomic no-replace. There is no overwrite/rename fallback.
        os.link(temporary, HEADER, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False)
        os.unlink(temporary, dir_fd=descriptor)
        created = False
        os.fsync(descriptor)
    finally:
        try:
            if created:
                saved = os.stat(temporary, dir_fd=descriptor, follow_symlinks=False)
                if (saved.st_dev, saved.st_ino) != temporary_identity:
                    raise ValueError('Temporary output changed; preserve it and inspect before retry')
                os.unlink(temporary, dir_fd=descriptor)
        finally:
            os.close(descriptor)


def generate(args):
    qualified_posix()
    root = ordinary(args.source_root, True)
    output = ordinary(args.output_root, True)
    build_path = ordinary(args.provider_build, False)
    for name, value in (('recipe', args.recipe_sha256), ('source manifest', args.source_manifest_sha256), ('provider build', args.provider_build_sha256)):
        sha(value, name)
    if (root == output or root in output.parents or output in root.parents
            or root in build_path.parents or output in build_path.parents):
        raise ValueError('Source, original provider-build input and output must be disjoint')
    raw_recipe, raw_sources = read_file(root / 'recipe.json'), read_file(root / 'sources.json')
    if digest(raw_recipe) != args.recipe_sha256 or digest(raw_sources) != args.source_manifest_sha256:
        raise ValueError('Independent recipe/source-manifest pin differs')
    recipe, sources = document(raw_recipe), document(raw_sources)
    snapshot = source_snapshot(root, recipe, raw_recipe, sources, raw_sources)
    inputs = recipe['inputs']
    if ordinary(Path(__file__), False) != root / GENERATOR:
        raise ValueError('Execute the exact recipe-retained source/native/runtime/generate_native_actions_metadata.py copy')
    retained(root, inputs, GENERATOR, 'helper')
    template = retained(root, inputs, TEMPLATE, 'config')
    config_raw = retained(root, inputs, CONFIG, 'config')
    manifest, contract = load_helpers(root, inputs)
    manifest.source_contract(sources, recipe, args.recipe_sha256)
    target = contract.native_actions_target(recipe['target'])
    if (encoded(target) != encoded(recipe['target']) or target['pointer_bits'] != 64
            or (target['system'], target['processor']) not in
                {('Linux', 'x86_64'), ('Linux', 'aarch64'), ('Windows', 'x86_64')}):
        raise ValueError('Native actions helper target changed or is unsupported')
    if (recipe['toolchain']['runtime_policy'] != 'private-native' or recipe['toolchain']['paired_sdk_sha256'] is not None):
        raise ValueError('Native actions metadata requires private-native inputs, never browser SDKs')
    sha(recipe['toolchain']['identity_sha256'], 'native toolchain')
    if encoded(recipe['provider']) != encoded({'format': 'native-shared', 'binding': 'c-abi',
            'abi_major': 1, 'abi_minor': 1, 'header': PINS['base'][0], 'header_sha256': PINS['base'][1]}):
        raise ValueError('Native actions recipe must select the exact ABI1.1 base header and C provider')
    for name, pin in PINS.values():
        if digest(retained(root, inputs, name, 'interface')) != pin:
            raise ValueError('Source interface differs from rich4083: ' + name)
    pinned_paths = {name: pin for name, pin in PINS.values()}
    interfaces = dict(contract.INTERFACE_PATHS)
    if len(interfaces) != 16 or set(interfaces.values()) != set(pinned_paths):
        raise ValueError('Native actions helper interface path closure differs')
    if any(contract._pins()[role] != pinned_paths[path] for role, path in interfaces.items()):
        raise ValueError('Pinned helper component constants differ from native rich4083')
    if tuple(contract.BUILD_FIELDS) != BUILD_FIELDS:
        raise ValueError('Native actions helper Build field closure differs')
    if encoded(contract.expected_actions_configuration()) != encoded(CONFIGURATION):
        raise ValueError('Native actions helper fixed configuration differs')
    if encoded(document(config_raw)) != encoded(expected_config()):
        raise ValueError('Prelink config differs from exact native limits/retention; no CLI override exists')
    raw_build = read_file(build_path)
    if digest(raw_build) != args.provider_build_sha256:
        raise ValueError('Independent original provider-build pin differs')
    build = document(raw_build)
    fields(build, BUILD_FIELDS, 'native provider-build')
    if encoded(build) != raw_build or raw_build != encoded(expected_build(recipe, args.recipe_sha256, contract)):
        raise ValueError('Original canonical provider-build differs from source/target/native configuration')
    build_state = identity(build_path.stat())
    if build_state[:2] in {item[:2] for item in snapshot[0].values()}:
        raise ValueError('Original provider-build physically aliases retained input')
    source_directories = {item[:2] for item in snapshot[1].values()}
    if any((part.stat().st_dev, part.stat().st_ino) in source_directories for part in (output, *output.parents)):
        raise ValueError('Output physically aliases retained source directories')
    contract.validate_actions_provider_limits(build['provider_limits'])
    checked_provider_contract(build['provider_contract'], target)
    checked_catalog(retained(root, inputs, PINS['catalog'][0], 'interface'), build['provider_contract'])
    profile = contract.expected_actions_engine_profile(kernel_target=target,
        build_sha256=args.provider_build_sha256, source_recipe_sha256=args.recipe_sha256)
    fields(profile, contract.PROFILE_FIELDS, 'native actions engine profile')
    checked_profile(profile, target, args.recipe_sha256, args.provider_build_sha256)
    replacements = {'TARGET_SYSTEM': str(build['provider_contract']['target']['system']),
        'TARGET_PROCESSOR': str(build['provider_contract']['target']['processor']),
        'SOURCE_RECIPE_SHA256_BYTES': digest_literal(args.recipe_sha256),
        'BUILD_IDENTITY_SHA256_BYTES': digest_literal(args.provider_build_sha256),
        'SOURCE_INPUTS_SHA256_BYTES': digest_literal(build['source_inputs_sha256']),
        'TOOLCHAIN_IDENTITY_SHA256_BYTES': digest_literal(recipe['toolchain']['identity_sha256']),
        'QUERIES': ',\n    '.join(operation_literal(item) for item in build['provider_contract']['queries']),
        'COMMANDS': ',\n    '.join(operation_literal(item) for item in build['provider_contract']['commands'])}
    replacements.update({key.upper() + '_SHA256_BYTES': digest_literal(pin) for key, (_, pin) in PINS.items()})
    header = template.decode('ascii')
    for key, replacement in replacements.items():
        if '@' + key + '@' not in header:
            raise ValueError('Required template token missing: ' + key)
        header = header.replace('@' + key + '@', replacement)
    if '@' in header or '#error "DESIGN TEMPLATE' in header:
        raise ValueError('Unresolved or design-only metadata template is ineligible')
    raw_header = header.encode('ascii')
    if len(raw_header) > MAX_DOCUMENT:
        raise ValueError('Generated native header exceeds 32 MiB')
    if source_snapshot(root, recipe, raw_recipe, sources, raw_sources) != snapshot or read_file(build_path) != raw_build or identity(build_path.stat()) != build_state:
        raise ValueError('Original source/provider-build inputs changed before output')
    publish(output, raw_header, source_directories)
    return {'scope': SCOPE, 'production_eligible': False, 'engine_execution': False,
        'recipe_sha256': args.recipe_sha256, 'source_manifest_sha256': args.source_manifest_sha256,
        'provider_build_sha256': args.provider_build_sha256, 'source_inputs_sha256': build['source_inputs_sha256'],
        'target': target, 'engine_profile': profile, 'header': str(output / HEADER), 'header_sha256': digest(raw_header)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--recipe-sha256', required=True)
    parser.add_argument('--source-manifest-sha256', required=True)
    parser.add_argument('--provider-build', type=Path, required=True)
    parser.add_argument('--provider-build-sha256', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    result = generate(parser.parse_args(argv))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        raise SystemExit('native document-actions provider metadata: ' + str(error)) from error
