#!/usr/bin/env python3
"""Passive admission of an already restored native SDK; never install or probe it."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

from dependency_archive import PathInventory, relative, sdk_path_policy, LINUX_SDK_PATHS
from appended_engine_manifest import path_name

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = 'recipes/webkitwasm-native-rich4083-v1/producer/native-sdk-toolchain.cmake.in'
CONTROL_PATHS = ('tools/appended_engine_native_sdk.py', TEMPLATE)
TARGET = {'system': 'Linux', 'processor': 'x86_64', 'triple': 'x86_64-buildroot-linux-gnu', 'pointer_bits': 64}
SCOPE = 'native-sdk-admission-candidate-only'
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_RAW = 1024 * 1024
MAX_RESTORATION_RAW = 8 * 1024 * 1024
MAX_FILES = 65536
MAX_BYTES = 32 * 1024 * 1024 * 1024
TOOL_NAMES = ('c', 'cxx', 'linker', 'archiver', 'ranlib', 'inspect', 'cmake', 'ninja', 'pkg_config')
FLAGS = {'production_eligible': False, 'native_engine_execution': False, 'kernel_rebuild': False}
PRIVATE_RUNTIME_POLICY_SHA256 = '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc'
PRIVATE_RUNTIME_ROLES = ('libstdcxx', 'libgcc', 'libgcc_eh', 'crtbeginS', 'crtendS')
PRIVATE_RUNTIME_QUERIES = PRIVATE_RUNTIME_ROLES + ('dumpmachine', 'sysroot', 'search_dirs')


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def _fields(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(label + ' has missing or unknown fields')
    return value


def _pin(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value) or value == '0' * 64:
        raise ValueError('Independent nonzero lowercase SHA256 required')
    return value


def _integer(value, label, minimum=0, maximum=MAX_BYTES):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid bounded integer: ' + label)
    return value


def _absolute(value):
    if not isinstance(value, (str, Path)):
        raise ValueError('Explicit ordinary absolute path required')
    path = Path(value)
    if not path.is_absolute() or str(path) != str(value) or '..' in path.parts or any(c in str(path) for c in (';', ':', '\n', '\r', '\x00')):
        raise ValueError('Explicit normalized absolute path required')
    return path


def _name(value):
    return path_name(value)


def _identity(state):
    return (state.st_dev, state.st_ino, state.st_mode, state.st_nlink, state.st_size, state.st_mtime_ns, state.st_ctime_ns)


def _ordinary(path, directory=False):
    path = _absolute(path)
    for item in reversed((path, *path.parents)):
        state = item.lstat()
        want_directory = directory if item == path else True
        if not (stat.S_ISDIR(state.st_mode) if want_directory else stat.S_ISREG(state.st_mode)) or stat.S_ISLNK(state.st_mode) or not want_directory and state.st_nlink != 1:
            raise ValueError('Linked or special native SDK input refused: ' + str(item))
    return path


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate SDK JSON field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite SDK JSON: ' + value)
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
        # Escaped lone surrogates parse as Python strings but are not UTF8 text.
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
        encoded(result)
        return result
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid SDK JSON encoding/nesting') from error


def read_document(path, pin=None):
    path = _ordinary(path)
    before = path.lstat()
    if before.st_size > MAX_DOCUMENT:
        raise ValueError('SDK document exceeds32MiB')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0)), 'rb') as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(before):
            raise ValueError('SDK document changed before read')
        raw = stream.read(MAX_DOCUMENT + 1)
        after = os.fstat(stream.fileno())
    if len(raw) > MAX_DOCUMENT or _identity(before) != _identity(after) or _identity(path.lstat()) != _identity(before):
        raise ValueError('SDK document changed during read')
    if pin is not None and hashlib.sha256(raw).hexdigest() != _pin(pin):
        raise ValueError('SDK document independent pin mismatch')
    return _json(raw)


def _control_raw(path):
    """Read one fixed current producer control, with no source-mode waiver for data."""
    path = _ordinary(path)
    before = path.lstat()
    if before.st_size > MAX_DOCUMENT:
        raise ValueError('SDK producer control exceeds document bound')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(before):
            raise ValueError('SDK producer source changed before read')
        raw = stream.read(MAX_DOCUMENT + 1)
        after = os.fstat(stream.fileno())
    if len(raw) > MAX_DOCUMENT or _identity(before) != _identity(after) or _identity(path.lstat()) != _identity(before):
        raise ValueError('SDK producer source changed during read')
    return raw


class MissingInputs(ValueError):
    def __init__(self, missing):
        unique = {(item['role'], item['path'], item['reason']) for item in missing}
        self.missing = [{'role': role, 'path': path, 'reason': reason} for role, path, reason in sorted(unique)]
        self.roles = tuple(sorted({item['role'] for item in self.missing}))
        super().__init__('Missing original native SDK inputs: ' + ', '.join(self.roles))

    def as_dict(self):
        return dict(schema_version=1, kind='foundation-native-sdk-admission-missing-inputs-v1', scope=SCOPE, missing=self.missing, **FLAGS)


def _missing(role, path, reason):
    raise MissingInputs([{'role': role, 'path': str(path), 'reason': reason}])


def _file(capture, path, pin, role, maximum=MAX_DOCUMENT, *, manifest_root=None):
    # These original metadata records must keep a DATA alias in native R.
    if (role not in ('sdk-original-controller', 'sdk-original-compiler-support', 'sdk-complete-root')
            and not role.startswith(('sdk-program-', 'sdk-runtime-file-'))):
        role = 'sdk-provenance-' + role
    try:
        if manifest_root is not None:
            return capture.sdk_manifest_file(_absolute(path), _pin(pin), role, sdk_root=manifest_root,
                                              manifest_sha256=pin, maximum=maximum)
        return capture.file(_absolute(path), _pin(pin), role, maximum=maximum)
    except (FileNotFoundError, MissingInputs) as error:
        _missing(role, path, 'Original ordinary retained input absent')
    except ValueError as error:
        if hasattr(error, 'missing'):
            raise MissingInputs(error.missing) from error
        raise


def _ref(value, base):
    _fields(value, ('path', 'sha256'), 'SDK original file reference')
    return _absolute(base) / _name(value['path']), _pin(value['sha256'])


def _document(value, base, capture, role):
    path, pin = _ref(value, base)
    _file(capture, path, pin, role)
    return _json(capture.bytes(path)), {'path': str(path), 'sha256': pin}


def _record(value, kind, fields, role, path):
    if type(value) is not dict or value.get('kind') != kind:
        _missing(role, path, 'Compatible original ' + kind + ' observation required')
    _fields(value, ('schema_version', 'kind', *fields), role)
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported original SDK observation schema')


def _target(value):
    if value != TARGET:
        raise ValueError('Native SDK actual Buildroot target mismatch')
    return dict(value)


def _version(value):
    if type(value) is not str or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,4}', value):
        raise ValueError('Actual dotted SDK program version required')
    parts = tuple(map(int, value.split('.')))
    return parts + (0,) * max(0, 3 - len(parts))


def _group(value):
    _fields(value, ('root', 'recipe', 'files'), 'Original native SDK retained group')
    _absolute(value['root'])
    recipe = _pin(value['recipe'])
    names = {'sdk-' + recipe + suffix for suffix in ('-binary.tar.gz', '-sources.tar.gz', '-SHA256SUMS')}
    if type(value['files']) is not dict or set(value['files']) != names:
        raise ValueError('Original SDK complete binary/source/checksum binding required')
    for item in value['files'].values():
        _fields(item, ('sha256', 'bytes'), 'Original group member')
        _pin(item['sha256'])
        _integer(item['bytes'], 'group bytes', 1)
    return value


def _policy(value):
    _fields(value, ('runtime', 'cpu', 'source_date_epoch'), 'SDK candidate policy')
    runtime = _fields(value['runtime'], ('c_library', 'c_library_baseline', 'cxx_library', 'cxx_library_baseline', 'linkage', 'sysroot_inventory', 'needed_libraries'), 'Native runtime policy')
    if runtime['c_library'] != 'glibc' or runtime['cxx_library'] != 'libstdc++' or runtime['linkage'] != 'private-native' or runtime['sysroot_inventory'] != 'sdk':
        raise ValueError('Explicit private native SDK runtime required')
    _version(runtime['c_library_baseline']); _version(runtime['cxx_library_baseline'])
    if runtime['c_library_baseline'] != '2.36':
        raise ValueError('Native SDK libc baseline differs from Bookworm2.36')
    needed = runtime['needed_libraries']
    if type(needed) is not list or not needed or any(type(item) is not str or not re.fullmatch(r'lib[A-Za-z0-9_+.-]+\.so(?:\.[0-9]+)*', item) for item in needed) or needed != sorted(set(needed)):
        raise ValueError('Explicit sorted native runtime library allowlist required')
    if value['cpu'] != {'baseline': 'sse2', 'source_dispatch': 'supplier-per-source-reviewed'}:
        raise ValueError('Explicit native SSE2/source dispatch policy required')
    if type(value['source_date_epoch']) is not str or not re.fullmatch('[0-9]{1,12}', value['source_date_epoch']):
        raise ValueError('Explicit decimal source epoch required')
    return value


def _sdk_metadata(sdk, group, capture, target):
    _fields(sdk, ('root', 'manifest_sha256'), 'Original installed SDK')
    root = _absolute(sdk['root'])
    path = root / 'sdk.json'
    _file(capture, path, sdk['manifest_sha256'], 'sdk-original-manifest', manifest_root=root)
    data = _json(capture.bytes(path))
    required = {'schema_version', 'kind', 'recipe_id', 'target', 'host', 'baseline', 'host_tools', 'files', 'sources_sha256', 'licenses', 'relocation', 'audits', 'installed_root', 'archive_sha256'}
    if type(data) is not dict or not required <= set(data) or type(data['schema_version']) is not int or data['schema_version'] != 1 or data['kind'] != 'source-build':
        raise ValueError('Original source-built native SDK manifest required')
    if data['recipe_id'] != group['recipe'] or data['installed_root'] != str(root) or data['archive_sha256'] != group['files']['sdk-' + group['recipe'] + '-binary.tar.gz']['sha256'] or data['relocation'] not in ('buildroot', 'relative-paths'):
        raise ValueError('Original SDK recipe/archive/final installed root mismatch')
    _pin(data['sources_sha256'])
    target_data, host = data['target'], data['host']
    if type(target_data) is not dict or any(target_data.get(key) != target[key] for key in ('system', 'processor', 'triple')) or type(host) is not dict or host.get('system') != 'Linux' or host.get('processor') != 'x86_64' or host.get('glibc') != '2.36' or data['baseline'] != {'distribution': 'debian-12', 'glibc': '2.36'}:
        raise ValueError('Original SDK host/target/runtime baseline mismatch')
    policy = sdk_path_policy(data)
    if policy == LINUX_SDK_PATHS and not sys.platform.startswith('linux'):
        raise ValueError('Linux SDK names require an actual Linux host')
    files = data['files']
    if type(files) is not dict or not files or len(files) > MAX_FILES or 'sdk.json' in files:
        raise ValueError('Original SDK complete bounded file map required')
    registry = PathInventory(policy)
    registry.add('sdk.json', False)
    for name, pin in files.items():
        registry.add(str(relative(name)), False)
        _pin(pin)
    for key in ('sysroot', 'c_compiler', 'cxx_compiler'):
        if key not in target_data:
            raise ValueError('Original SDK must declare C/C++ and sysroot')
        name = str(relative(target_data[key]))
        if key == 'sysroot':
            if not any(member.startswith(name + '/') for member in files):
                raise ValueError('Original SDK sysroot has no retained files')
        elif name not in files:
            raise ValueError('Original SDK compiler omitted from complete file map')
    if type(data['licenses']) is not list or not data['licenses'] or any(type(name) is not str or not any(member == str(relative(name)) or member.startswith(str(relative(name)) + '/') for member in files) for name in data['licenses']):
        raise ValueError('Original SDK source licenses absent from complete inventory')
    if type(data['host_tools']) is not dict or any(type(name) is not str or str(relative(name)) not in files for name in data['host_tools'].values()):
        raise ValueError('Original SDK host tools omitted from inventory')
    audits = data['audits']
    if type(audits) is not dict or type(audits.get('host')) is not dict or audits['host'].get('status') != 'passed' or type(audits.get('target')) is not dict:
        raise ValueError('Original SDK host/target audits missing')
    audit = audits['target']; runtime = audit.get('sdk_runtime')
    if audit.get('status') != 'passed' or audit.get('scope') != 'sdk-sysroot' or type(runtime) is not dict or runtime.get('recipe_id') != data['recipe_id'] or runtime.get('processor') != target['processor'] or runtime.get('glibc') != '2.36' or type(runtime.get('files')) is not dict or not runtime['files']:
        raise ValueError('Original SDK target runtime audit binding invalid')
    _pin(runtime.get('source_sha256'))
    for name, pin in runtime['files'].items():
        if files.get(target_data['sysroot'] + '/' + str(relative(name))) != _pin(pin):
            raise ValueError('Original SDK runtime cohort differs from actual SDK file map')
    return data, policy


def _command(value, argv, base, capture, *, maximum=MAX_RAW):
    _fields(value, ('argv', 'returncode', 'stdout', 'stderr', 'ownership'), 'Original SDK command')
    _fields(value['ownership'], ('closed', 'descendants_closed', 'logs_closed'), 'Original SDK process closure')
    if value['argv'] != argv or type(value['returncode']) is not int or value['returncode'] != 0 or any(item is not True for item in value['ownership'].values()):
        raise ValueError('Original SDK command/closed ownership mismatch')
    raw = []
    for stream in ('stdout', 'stderr'):
        path, pin = _ref(value[stream], base)
        _file(capture, path, pin, 'sdk-original-' + stream, maximum)
        try:
            raw.append(capture.bytes(path, maximum=maximum).decode('utf-8'))
        except UnicodeError as error:
            raise ValueError('Original SDK tool output must be UTF8') from error
    return raw[0]


def _original_helper(capture, item, *, repository_root):
    """Keep the exact original SDK helper as source, never relax retained data."""
    _fields(item, ('path', 'sha256'), 'Original SDK install helper')
    path = _absolute(item['path'])
    root = _ordinary(repository_root, True)
    if path != root / 'tools/sdk.py':
        return _file(capture, path, item['sha256'], 'sdk-original-helper')
    maximum = MAX_DOCUMENT
    if isinstance(capture, _Capture):
        maximum = min(maximum, capture.limits['maximum_document_bytes'])
    try:
        return capture.repository_file(path, _pin(item['sha256']),
            'sdk-provenance-original-helper', repository_root=root,
            source_paths=('tools/sdk.py',), maximum=maximum)
    except (FileNotFoundError, MissingInputs) as error:
        _missing('sdk-original-helper', path, 'Original canonical SDK helper source absent')
    except ValueError as error:
        if hasattr(error, 'missing'):
            raise MissingInputs(error.missing) from error
        raise


def _observations(value, base, capture, sdk, group, metadata, *, repository_root=ROOT):
    restore, restore_ref = _document(value['restoration'], base, capture, 'sdk-restoration')
    _record(restore, 'foundation-native-sdk-restoration-observations-v1', ('scope', 'mode', 'sdk_root', 'sdk_manifest_sha256', 'recipe', 'group_files', 'sources_sha256', 'helper', 'controller', 'command', 'production_eligible', 'native_build'), 'sdk-restoration', restore_ref['path'])
    if restore['mode'] == 'diagnostic':
        _missing('sdk-restoration', restore_ref['path'], 'Original production restoration observations required; diagnostic restore is not promoted')
    if restore['scope'] != 'original-supported-sdk-install-observation-only' or restore['mode'] != 'production' or restore['sdk_root'] != sdk['root'] or restore['sdk_manifest_sha256'] != sdk['manifest_sha256'] or restore['recipe'] != group['recipe'] or restore['group_files'] != group['files'] or restore['sources_sha256'] != metadata['sources_sha256'] or restore['production_eligible'] is not False or restore['native_build'] is not False:
        raise ValueError('Original SDK restoration observations contradict selected SDK')
    _fields(restore['helper'], ('path', 'sha256'), 'Original SDK install helper')
    _fields(restore['controller'], ('path', 'sha256', 'version'), 'Original SDK restore controller')
    _original_helper(capture, restore['helper'], repository_root=repository_root)
    record = _file(capture, restore['controller']['path'], restore['controller']['sha256'],
                   'sdk-original-controller', MAX_BYTES)
    if record['mode'] != 0o755:
        raise ValueError('Original restore controller must be0755')
    _version(restore['controller']['version'])
    argv = [restore['controller']['path'], '-B', restore['helper']['path'], 'install', '--group', group['root'], '--recipe', group['recipe'], '--output', sdk['root']]
    _command(restore['command'], argv, Path(restore_ref['path']).parent, capture, maximum=MAX_RESTORATION_RAW)
    observed, observed_ref = _document(value['observations'], base, capture, 'sdk-tool-observations')
    _record(observed, 'foundation-native-sdk-tool-observations-v1', ('scope', 'sdk_root', 'sdk_manifest_sha256', 'tools', 'production_eligible', 'native_build'), 'sdk-tool-observations', observed_ref['path'])
    if observed['scope'] != 'original-retained-sdk-tool-observation-only' or observed['sdk_root'] != sdk['root'] or observed['sdk_manifest_sha256'] != sdk['manifest_sha256'] or observed['production_eligible'] is not False or observed['native_build'] is not False:
        raise ValueError('Original tool observation SDK binding mismatch')
    if type(observed['tools']) is not dict or set(observed['tools']) - set(TOOL_NAMES):
        raise ValueError('Unknown or malformed original SDK tool roles')
    missing = sorted(set(TOOL_NAMES) - set(observed['tools']))
    if missing:
        raise MissingInputs([{'role': 'sdk-tool-' + name, 'path': observed_ref['path'], 'reason': 'Original retained SDK tool observations absent'} for name in missing])
    tools = {}
    root = _absolute(sdk['root'])
    def support(text, regular=True):
        text = text.strip()
        if not text or '\n' in text or '\r' in text or not text.startswith('/'):
            raise ValueError('Original compiler support path must be explicit absolute')
        path = _absolute(os.path.normpath(text))
        if root not in path.parents:
            raise ValueError('Compiler search/support path escapes actual SDK')
        if regular:
            name = path.relative_to(root).as_posix()
            if name not in metadata['files']:
                raise ValueError('Compiler subordinate tool missing from complete SDK')
            _file(capture, path, metadata['files'][name], 'sdk-original-compiler-support', MAX_BYTES)
        return path
    for role, item in observed['tools'].items():
        _fields(item, ('path', 'sha256', 'version', 'commands'), 'Original SDK program')
        path = _absolute(item['path'])
        if root not in path.parents or metadata['files'].get(path.relative_to(root).as_posix()) != _pin(item['sha256']):
            raise ValueError('Original selected program is outside exact SDK file inventory')
        record = _file(capture, path, item['sha256'], 'sdk-program-' + role, MAX_BYTES)
        if record['mode'] != 0o755:
            raise ValueError('Original SDK selected program must be0755')
        commands = item['commands']
        expected = ('version', 'dumpmachine', 'sysroot', 'frontend', 'assembler', 'linker', 'search_dirs') if role in ('c', 'cxx') else ('version',)
        _fields(commands, expected, 'Original SDK program commands')
        output = _command(commands['version'], [str(path), '--version'], Path(observed_ref['path']).parent, capture)
        first = output.splitlines()[0] if output.splitlines() else ''
        match = re.search(r'([0-9]+(?:\.[0-9]+){1,4})\s*$', first)
        if match is None or match.group(1) != item['version']:
            raise ValueError('Original raw tool version differs from declared version')
        _version(item['version'])
        tools[role] = {key: item[key] for key in ('path', 'sha256', 'version')}
        if role in ('c', 'cxx'):
            if _version(item['version']) < (12, 2, 0):
                raise ValueError('Original native GCC below12.2')
            expected_path = root / metadata['target']['c_compiler' if role == 'c' else 'cxx_compiler']
            if path != expected_path:
                raise ValueError('Selected compiler differs from original SDK target metadata')
            suffixes = {'dumpmachine': '-dumpmachine', 'sysroot': '-print-sysroot', 'frontend': '-print-prog-name=' + ('cc1' if role == 'c' else 'cc1plus'), 'assembler': '-print-prog-name=as', 'linker': '-print-prog-name=ld', 'search_dirs': '-print-search-dirs'}
            outputs = {name: _command(commands[name], [str(path), argument], Path(observed_ref['path']).parent, capture) for name, argument in suffixes.items()}
            if outputs['dumpmachine'].strip() != TARGET['triple'] or support(outputs['sysroot'], False) != root / metadata['target']['sysroot']:
                raise ValueError('Original actual compiler target/sysroot mismatch')
            support(outputs['frontend']); support(outputs['assembler'])
            if support(outputs['linker']) != _absolute(observed['tools']['linker']['path']):
                raise ValueError('Original compiler selected a different linker')
            lines = outputs['search_dirs'].splitlines()
            if len(lines) != 3:
                raise ValueError('Original GCC complete search directory output required')
            for line, prefix in zip(lines, ('install: ', 'programs: ', 'libraries: ')):
                if not line.startswith(prefix):
                    raise ValueError('Original GCC search directory shape mismatch')
                for candidate in line[len(prefix):].removeprefix('=').split(':'):
                    support(candidate, False)
    if tools['c']['version'] != tools['cxx']['version'] or _version(tools['cmake']['version']) < (3, 24, 0):
        raise ValueError('Original compiler versions/CMake policy mismatch')
    for role, key in (('cmake', 'cmake'), ('ninja', 'ninja'), ('pkg_config', 'pkg-config')):
        if key in metadata['host_tools'] and tools[role]['path'] != str(root / metadata['host_tools'][key]):
            raise ValueError('Original host tool differs from SDK manifest')
    compiler = {'family': 'gcc', 'version': tools['cxx']['version'], 'frontend': 'gcc', 'triple': TARGET['triple']}
    return tools, compiler, restore_ref, observed_ref


def _inventory(value, metadata, sdk, policy):
    _fields(value, ('files', 'directories', 'modes'), 'Complete SDK admission inventory')
    if type(value['files']) is not dict or type(value['directories']) is not list or any(type(item) is not str for item in value['directories']) or value['directories'] != sorted(set(value['directories'])) or type(value['modes']) is not dict:
        raise ValueError('Complete SDK inventory structure mismatch')
    if len(value['files']) + len(value['directories']) > MAX_FILES or set(value['modes']) != set(value['files']) | set(value['directories']):
        raise ValueError('Complete SDK inventory bound/mode coverage mismatch')
    if value['files'] != dict(metadata['files'], **{'sdk.json': sdk['manifest_sha256']}):
        raise ValueError('SDK inventory omits or replaces original SDK manifest/files')
    registry = PathInventory(policy)
    for name in value['directories']:
        registry.add(str(relative(name)), True)
        if type(value['modes'][name]) is not int or value['modes'][name] != 0o755:
            raise ValueError('SDK inventory directory mode must be0755')
    for name, pin in value['files'].items():
        registry.add(str(relative(name)), False); _pin(pin)
        if type(value['modes'][name]) is not int or value['modes'][name] not in (0o644, 0o755):
            raise ValueError('SDK inventory file mode must be0644/0755')
    parents = {parent.as_posix() for name in value['files'] for parent in Path(name).parents if parent.as_posix() != '.'}
    if set(value['directories']) != parents:
        raise ValueError('SDK inventory must contain exactly original file parent directories; unknown empty directories refused')
    return value


def validate_sdk_binding(value, base, capture, *, target, repository_root=ROOT):
    _record(value, 'foundation-native-sdk-admission-binding-v1', ('target', 'sdk', 'retained_group', 'restoration', 'observations', 'producer', 'inventory', 'tool_paths', 'sysroot', 'host_tools', 'policy'), 'sdk-admission', base)
    _target(target)
    if value['target'] != target:
        raise ValueError('SDK admission target differs from requested target')
    group = _group(value['retained_group']); policy_record = _policy(value['policy'])
    metadata, path_policy = _sdk_metadata(value['sdk'], group, capture, target)
    tools, compiler, _, _ = _observations(value, base, capture, value['sdk'], group, metadata,
                                         repository_root=repository_root)
    if value['tool_paths'] != tools or value['sysroot'] != metadata['target']['sysroot']:
        raise ValueError('SDK binding selected tool/sysroot observations differ')
    _fields(value['producer'], ('adapter', 'template'), 'SDK adapter producer source refs')
    producer_raw = {}
    for role, ref in value['producer'].items():
        path, pin = _ref(ref, base); _file(capture, path, pin, 'sdk-adapter-original-' + role)
        producer_raw[role] = capture.bytes(path)
    if producer_raw['template'] != _control_raw(ROOT / TEMPLATE) or producer_raw['adapter'] != _control_raw(Path(__file__).absolute()):
        raise ValueError('SDK admission producer/template differs from this exact supported source')
    _fields(value['inventory'], ('root', 'inventory'), 'SDK complete inventory reference')
    if value['inventory']['root'] != value['sdk']['root']:
        raise ValueError('SDK inventory authority cannot select another root')
    inventory, inventory_ref = _document(value['inventory']['inventory'], base, capture, 'sdk-admission-inventory')
    _inventory(inventory, metadata, value['sdk'], path_policy)
    host_document, host_ref = _document(value['host_tools'], base, capture, 'sdk-host-tools')
    expected_toolchain = render_toolchain(producer_raw['template'], _toolchain_values(value['sdk'], metadata, tools))
    return dict(root=value['sdk']['root'], inventory=dict(value['inventory']['inventory']), inventory_base=str(_absolute(base)), inventory_path=inventory_ref['path'], files=dict(inventory['files']), directories=list(inventory['directories']), modes=dict(inventory['modes']), path_policy=path_policy, sdk_manifest_sha256=value['sdk']['manifest_sha256'], tool_paths=tools, sysroot=value['sysroot'], host_tools=host_ref, host_document=host_document, policy=policy_record, metadata=metadata, compiler=compiler, toolchain_sha256=hashlib.sha256(expected_toolchain).hexdigest())


def _private_runtime_binding(binding):
    """Pure joins on an already admitted SDK; never discover a replacement."""
    required = {'root', 'metadata', 'files', 'modes', 'tool_paths', 'compiler',
                'sysroot', 'sdk_manifest_sha256', 'policy'}
    if type(binding) is not dict or not required <= set(binding):
        raise ValueError('Admitted SDK binding required for private runtime')
    root = _absolute(binding['root']); metadata = binding['metadata']
    if type(metadata) is not dict or type(metadata.get('target')) is not dict or type(metadata.get('files')) is not dict:
        raise ValueError('Original complete SDK metadata required for private runtime')
    target = metadata['target']
    if any(target.get(key) != TARGET[key] for key in ('system', 'processor', 'triple')):
        raise ValueError('Private runtime SDK target mismatch')
    manifest = _pin(binding['sdk_manifest_sha256'])
    if ('sdk.json' in metadata['files'] or type(binding['files']) is not dict
            or binding['files'] != dict(metadata['files'], **{'sdk.json': manifest})
            or type(binding['modes']) is not dict):
        raise ValueError('Private runtime requires the complete original installed SDK inventory')
    sysroot_name = str(relative(target.get('sysroot')))
    if binding['sysroot'] != sysroot_name:
        raise ValueError('Private runtime sysroot differs from original SDK')
    tools = _fields(binding['tool_paths'], TOOL_NAMES, 'Private runtime admitted tools')
    for role, tool in tools.items():
        _fields(tool, ('path', 'sha256', 'version'), 'Private runtime admitted tool')
        path = _absolute(tool['path'])
        if (root not in path.parents
                or metadata['files'].get(path.relative_to(root).as_posix()) != _pin(tool['sha256'])
                or binding['modes'].get(path.relative_to(root).as_posix()) != 0o755):
            raise ValueError('Private runtime tool is outside the complete admitted SDK: ' + role)
        _version(tool['version'])
    if tools['cxx']['path'] != str(root / str(relative(target.get('cxx_compiler')))):
        raise ValueError('Private runtime C++ compiler differs from original SDK')
    compiler = _fields(binding['compiler'], ('family', 'version', 'frontend', 'triple'), 'Private runtime compiler')
    if (compiler['family'] != 'gcc' or compiler['frontend'] != 'gcc'
            or compiler['triple'] != TARGET['triple'] or compiler['version'] != tools['cxx']['version']):
        raise ValueError('Private runtime requires the admitted GCC C++ compiler')
    _policy(binding['policy'])
    return root, metadata, tools, root / sysroot_name


def _private_runtime_policy(policy_raw):
    if (type(policy_raw) is not bytes or len(policy_raw) > MAX_DOCUMENT
            or hashlib.sha256(policy_raw).hexdigest() != PRIVATE_RUNTIME_POLICY_SHA256):
        raise ValueError('Exact supported private runtime policy bytes required')
    policy = _json(policy_raw)
    _fields(policy, ('schema_version', 'kind', 'policy_id', 'scope', 'target', 'sdk_recipe_id',
        'original_manifest_sha256', 'selection_kind', 'selection_scope', 'c_library',
        'maximum_glibc_version', 'query_driver_options', 'link_driver_options', 'linker_options',
        'roles', 'forbidden_needed', 'forbidden_undefined_prefixes', 'libc_abi_exceptions',
        'required_link_evidence'), 'Private runtime source policy')
    if (type(policy['schema_version']) is not int or policy['schema_version'] != 1
            or policy['kind'] != 'foundation-native-provider-private-runtime-policy-v1'
            or policy['policy_id'] != 'private-static-gcc-sdk-v1' or policy['target'] != TARGET):
        raise ValueError('Unsupported private runtime source policy')
    _pin(policy['sdk_recipe_id']); _pin(policy['original_manifest_sha256'])
    _fields(policy['roles'], PRIVATE_RUNTIME_ROLES, 'Private runtime policy roles')
    return policy


def private_runtime_cohort(binding, policy_raw):
    """Pure original-policy/inventory join; no fresh body or execution claim."""
    policy = _private_runtime_policy(policy_raw)
    root, metadata, tools, sysroot = _private_runtime_binding(binding)
    if metadata.get('recipe_id') != policy['sdk_recipe_id']:
        raise ValueError('Private runtime policy selects a different original SDK recipe')
    candidates = {}
    for role in PRIVATE_RUNTIME_ROLES:
        item = _fields(policy['roles'][role], ('basename', 'sha256', 'paths'), 'Private runtime policy candidate')
        expected = _pin(item['sha256']); paths = item['paths']
        if type(paths) is not list or not paths or len(paths) > 16 or len(set(paths)) != len(paths):
            raise ValueError('Bounded distinct original private runtime candidate paths required')
        candidates[role] = []
        for logical in paths:
            logical = str(relative(logical))
            if (Path(logical).name != item['basename'] or metadata['files'].get(logical) != expected
                    or binding['files'].get(logical) != expected or binding['modes'].get(logical) != 0o644):
                raise ValueError('Private runtime candidate differs from original SDK inventory: ' + role)
            candidates[role].append({'path': str(root / logical), 'sha256': expected})
    return dict(policy=policy, policy_sha256=hashlib.sha256(policy_raw).hexdigest(),
                root=str(root), sysroot=str(sysroot), compiler=dict(tools['cxx']), candidates=candidates)


def private_runtime_query_environment(binding):
    """Exact SDK-only compiler-query environment, independent of host generators."""
    _, _, tools, _ = _private_runtime_binding(binding)
    return {'PATH': ':'.join(sorted({str(Path(tool['path']).parent) for tool in tools.values()})),
            'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
            'SOURCE_DATE_EPOCH': binding['policy']['source_date_epoch']}


def _runtime_closed(value):
    _fields(value, ('closed', 'descendants_closed', 'logs_closed'), 'Original private runtime ownership')
    if any(item is not True for item in value.values()):
        raise ValueError('Original private runtime process and streams must be closed')


def _runtime_line(text):
    if text.endswith('\n'):
        text = text[:-1]
    if not text or '\n' in text or '\r' in text or text != text.strip():
        raise ValueError('One exact original compiler query line required')
    return text


def _runtime_path(text, root):
    text = _runtime_line(text)
    if not text.startswith('/'):
        raise ValueError('Absolute original compiler runtime path required')
    path = _absolute(os.path.normpath(text))
    if path != root and root not in path.parents:
        raise ValueError('Original compiler runtime path escapes admitted SDK')
    return path


def validate_private_runtime_selection(ref, base, capture, *, binding, policy_raw, expected_environment):
    """Validate original query facts; never execute queries or infer link success."""
    cohort = private_runtime_cohort(binding, policy_raw); policy = cohort['policy']
    environment = private_runtime_query_environment(binding)
    if type(expected_environment) is not dict or expected_environment != environment:
        raise ValueError('Private runtime query environment differs from admitted SDK')
    value, record = _document(ref, base, capture, 'sdk-private-runtime-selection')
    _record(value, policy['selection_kind'], ('scope', 'policy_sha256', 'sdk_manifest_sha256',
        'compiler_sha256', 'selected', 'commands', 'ownership'), 'sdk-private-runtime-selection', record['path'])
    if (value['scope'] != policy['selection_scope'] or value['policy_sha256'] != cohort['policy_sha256']
            or value['sdk_manifest_sha256'] != binding['sdk_manifest_sha256']
            or value['compiler_sha256'] != cohort['compiler']['sha256']):
        raise ValueError('Original private runtime selection policy/SDK/compiler binding mismatch')
    _runtime_closed(value['ownership'])
    _fields(value['selected'], PRIVATE_RUNTIME_ROLES, 'Original selected private runtime roles')
    _fields(value['commands'], PRIVATE_RUNTIME_QUERIES, 'Original private runtime queries')
    selected = {}
    for role in PRIVATE_RUNTIME_ROLES:
        capture.check_deadline()
        item = _fields(value['selected'][role], ('path', 'sha256', 'bytes'), 'Original selected private runtime file')
        _absolute(item['path']); _pin(item['sha256']); _integer(item['bytes'], 'selected runtime bytes', 1)
        if {key: item[key] for key in ('path', 'sha256')} not in cohort['candidates'][role]:
            raise ValueError('Original compiler chose a runtime outside the fixed SDK cohort: ' + role)
        selected[role] = dict(item)
    support_directories = {str(Path(selected[role]['path']).parent) for role in PRIVATE_RUNTIME_ROLES if role != 'libstdcxx'}
    if len(support_directories) != 1:
        raise ValueError('Original GCC runtime/startup files use inconsistent support directories')
    support_directory = next(iter(support_directories)); root = Path(cohort['root'])
    common = [cohort['compiler']['path'], '--sysroot=' + cohort['sysroot'], *policy['query_driver_options']]
    queries = {role: '-print-file-name=' + policy['roles'][role]['basename'] for role in PRIVATE_RUNTIME_ROLES}
    queries.update(dumpmachine='-dumpmachine', sysroot='-print-sysroot', search_dirs='-print-search-dirs')
    outputs, cwd = {}, None
    for role in PRIVATE_RUNTIME_QUERIES:
        capture.check_deadline()
        command = _fields(value['commands'][role], ('argv', 'environment', 'cwd', 'returncode',
            'stdout', 'stderr', 'ownership'), 'Original private runtime query')
        if (command['argv'] != common + [queries[role]] or command['environment'] != environment
                or type(command['returncode']) is not int or command['returncode'] != 0):
            raise ValueError('Original private runtime query argv/environment/result mismatch: ' + role)
        working = str(_absolute(command['cwd']))
        if cwd is not None and working != cwd:
            raise ValueError('Original private runtime queries use different working directories')
        cwd = working; _runtime_closed(command['ownership']); streams = {}
        for stream in ('stdout', 'stderr'):
            path, digest = _ref(command[stream], Path(record['path']).parent)
            _file(capture, path, digest, 'sdk-private-runtime-' + role + '-' + stream, MAX_RAW)
            try:
                streams[stream] = capture.bytes(path, maximum=MAX_RAW).decode('utf-8')
            except UnicodeError as error:
                raise ValueError('Original private runtime query streams must be UTF8') from error
        if streams['stderr']:
            raise ValueError('Unexpected original compiler runtime-query stderr: ' + role)
        outputs[role] = streams['stdout']
    for role in PRIVATE_RUNTIME_ROLES:
        line = _runtime_line(outputs[role])
        if line == policy['roles'][role]['basename']:
            _missing('sdk-private-runtime-' + role, record['path'], 'Original compiler did not resolve the runtime file')
        if str(_runtime_path(line, root)) != selected[role]['path']:
            raise ValueError('Original raw runtime query differs from selected file: ' + role)
    if (_runtime_line(outputs['dumpmachine']) != TARGET['triple']
            or str(_runtime_path(outputs['sysroot'], root)) != cohort['sysroot']):
        raise ValueError('Original private runtime compiler target/sysroot mismatch')
    search_raw = outputs['search_dirs']
    if search_raw.endswith('\n'):
        search_raw = search_raw[:-1]
    lines = search_raw.split('\n')
    if len(lines) != 3 or '\r' in search_raw:
        raise ValueError('Original private runtime GCC search output must have exactly3lines')
    search = {}
    for line, name in zip(lines, ('install', 'programs', 'libraries')):
        prefix = name + ': '
        if not line.startswith(prefix):
            raise ValueError('Original private runtime GCC search prefix mismatch')
        payload = line[len(prefix):]
        if payload.startswith('='):
            payload = payload[1:]
        search[name] = [str(_runtime_path(item, root)) for item in payload.split(':')]
    if search['install'] != [support_directory]:
        raise ValueError('Original GCC install directory differs from selected runtime support')
    compiler = _file(capture, cohort['compiler']['path'], cohort['compiler']['sha256'], 'sdk-program-cxx', MAX_BYTES)
    if compiler['mode'] != 0o755:
        raise ValueError('Original runtime-query compiler must remain0755')
    for role, item in selected.items():
        capture.check_deadline()
        actual = _file(capture, item['path'], item['sha256'], 'sdk-runtime-file-' + role, MAX_BYTES)
        if actual['mode'] != 0o644 or actual['bytes'] != item['bytes']:
            raise ValueError('Original selected runtime body/size/mode changed: ' + role)
    cmake = {'BIB_NATIVE_RUNTIME_COMPILER_TRIPLE': TARGET['triple'],
             'BIB_NATIVE_RUNTIME_SELECTION_PATH': record['path'],
             'BIB_NATIVE_RUNTIME_SELECTION_SHA256': record['sha256'],
             'BIB_NATIVE_RUNTIME_POLICY_SHA256': cohort['policy_sha256']}
    for role, label in (('libstdcxx', 'LIBSTDCXX'), ('libgcc', 'LIBGCC'), ('libgcc_eh', 'LIBGCC_EH'),
                        ('crtbeginS', 'CRTBEGINS'), ('crtendS', 'CRTENDS')):
        cmake['BIB_NATIVE_RUNTIME_' + label + '_PATH'] = selected[role]['path']
        cmake['BIB_NATIVE_RUNTIME_' + label + '_SHA256'] = selected[role]['sha256']
    return dict(record=record, selected=selected, query_environment=environment, search_directories=search,
                policy=policy, policy_sha256=cohort['policy_sha256'], compiler_triple=TARGET['triple'],
                candidates=cohort['candidates'], cmake=cmake)


def _limits(value):
    caps = {'prepare_seconds': 3600, 'maximum_files': MAX_FILES, 'maximum_input_bytes': MAX_BYTES, 'maximum_document_bytes': MAX_DOCUMENT, 'maximum_output_bytes': MAX_DOCUMENT, 'minimum_free_bytes': MAX_BYTES}
    _fields(value, caps, 'SDK admission limits')
    for name, maximum in caps.items():
        _integer(value[name], name, 1, maximum)
    return dict(value)


def _walk_sdk(capture, root, metadata, manifest_pin, policy):
    root = _ordinary(root, True)
    result = {'files': {}, 'directories': [], 'modes': {}}
    registry = PathInventory(policy)
    parent_names = {parent.as_posix() for name in (*metadata['files'], 'sdk.json') for parent in Path(name).parents if parent.as_posix() != '.'}
    count = 0
    def walk(directory):
        nonlocal count
        capture.check_deadline()
        capture.sdk_directory(directory, sdk_root=root, manifest_sha256=manifest_pin,
                              maximum_directories=capture.limits['maximum_files'])
        before = directory.lstat(); children = []
        with os.scandir(directory) as stream:
            for item in stream:
                capture.check_deadline(); count += 1
                if count > capture.limits['maximum_files']:
                    raise ValueError('SDK complete root exceeds file/directory bound')
                children.append(directory / item.name)
        names = {item.name for item in children}
        if policy == LINUX_SDK_PATHS:
            for child in children:
                alternative = child.name.swapcase()
                if alternative != child.name and alternative not in names and ((directory / alternative).exists() or (directory / alternative).is_symlink()):
                    raise ValueError('SDK root filesystem folds case-distinct names')
        for child in sorted(children):
            state = child.lstat(); is_directory = stat.S_ISDIR(state.st_mode)
            _ordinary(child, is_directory)
            name = child.relative_to(root).as_posix(); registry.add(name, is_directory)
            mode = stat.S_IMODE(state.st_mode)
            generated = not is_directory and name == 'sdk.json'
            if not is_directory and mode not in ((0o600, 0o644, 0o755) if generated else (0o644, 0o755)):
                raise ValueError('SDK root has non-normalized physical mode')
            result['modes'][name] = 0o755 if is_directory else 0o644 if generated and mode == 0o600 else mode
            if is_directory:
                if name not in parent_names:
                    raise ValueError('Unknown empty SDK directory absent from original file parent closure')
                result['directories'].append(name); walk(child)
            else:
                pin = manifest_pin if name == 'sdk.json' else metadata['files'].get(name)
                if pin is None:
                    raise ValueError('Unknown actual SDK file: ' + name)
                if generated:
                    _file(capture, child, pin, 'sdk-complete-root', manifest_root=root)
                else:
                    _file(capture, child, pin, 'sdk-complete-root', MAX_BYTES)
                result['files'][name] = pin
        if _identity(directory.lstat()) != _identity(before):
            raise ValueError('SDK directory changed during admission')
    walk(root)
    result['directories'].sort()
    return _inventory(result, metadata, {'manifest_sha256': manifest_pin}, policy)


class _Capture:
    """Apply caller's lower limits before the native reader consumes a file."""
    def __init__(self, native, limits):
        self._native = native; self.limits = limits; self._paths = set(); self._bytes = 0
        self._directory_paths = set()

    def __getattr__(self, name):
        return getattr(self._native, name)

    @property
    def deadline(self):
        return self._native.deadline

    def file(self, path, pin, role, maximum=MAX_BYTES):
        return self._file(path, pin, role, maximum=maximum)

    def sdk_manifest_file(self, path, pin, role, *, sdk_root, manifest_sha256, maximum=MAX_DOCUMENT):
        return self._file(path, pin, role, maximum=maximum,
                          manifest_authority=(sdk_root, manifest_sha256))

    def sdk_directory(self, path, *, sdk_root, manifest_sha256, maximum_directories=MAX_FILES):
        path = _absolute(path); self.check_deadline()
        bound = min(_integer(maximum_directories, 'SDK directory bound', 1, MAX_FILES),
                    self.limits['maximum_files'])
        if str(path) not in self._directory_paths and len(self._directory_paths) >= bound:
            raise ValueError('SDK admission declared directory count bound exceeded')
        result = self._native.sdk_directory(path, sdk_root=sdk_root,
            manifest_sha256=manifest_sha256, maximum_directories=bound)
        self._directory_paths.add(str(path))
        return result

    def _file(self, path, pin, role, *, maximum, manifest_authority=None):
        path = _absolute(path); self.check_deadline()
        state = path.lstat()
        if str(path) not in self._paths and (len(self._paths) >= self.limits['maximum_files'] or state.st_size > self.limits['maximum_input_bytes'] - self._bytes):
            raise ValueError('SDK admission declared aggregate read bound exceeded')
        maximum = min(maximum, self.limits['maximum_document_bytes']) if maximum <= MAX_DOCUMENT else maximum
        if manifest_authority is None:
            result = self._native.file(path, pin, role, maximum=maximum)
        else:
            result = self._native.sdk_manifest_file(path, pin, role, sdk_root=manifest_authority[0],
                manifest_sha256=manifest_authority[1], maximum=maximum)
        if str(path) not in self._paths:
            self._paths.add(str(path)); self._bytes += result['bytes']
        return result

    def bytes(self, path, maximum=MAX_DOCUMENT):
        return self._native.bytes(path, maximum=min(maximum, self.limits['maximum_document_bytes']))

    def document(self, ref, base, role):
        return _document(ref, base, self, role)[0]

    def inventory(self, record, base, role):
        # The unbound method calls this wrapper's file/document for lower limits.
        import appended_engine_native_inputs as native
        return native.InputSet.inventory(self, record, base, role)

    def _inventory(self, *args, **kwargs):
        import appended_engine_native_inputs as native
        return native.InputSet._inventory(self, *args, **kwargs)

    def repository_file(self, *args, **kwargs):
        path = _absolute(args[0]); state = path.lstat()
        if str(path) not in self._paths and (len(self._paths) >= self.limits['maximum_files'] or state.st_size > self.limits['maximum_input_bytes'] - self._bytes):
            raise ValueError('SDK control aggregate read bound exceeded')
        result = self._native.repository_file(*args, **kwargs)
        if result['path'] not in self._paths:
            if len(self._paths) >= self.limits['maximum_files'] or result['bytes'] > self.limits['maximum_input_bytes'] - self._bytes:
                raise ValueError('SDK control aggregate read bound exceeded')
            self._paths.add(result['path']); self._bytes += result['bytes']
        return result


class SDKInspection:
    def __init__(self, data, capture, sdk_metadata, policy):
        self._data, self._capture, self._metadata, self._policy = data, capture, sdk_metadata, policy

    def as_dict(self):
        return _json(encoded(self._data))

    @property
    def protected_paths(self):
        return tuple(sorted(set(self._capture.protected_paths) | {Path(self._data['sdk']['root'])}))

    def recheck(self):
        self._capture.recheck()
        fresh = _walk_sdk(self._capture, self._data['sdk']['root'], self._metadata, self._data['sdk']['manifest_sha256'], self._policy)
        if fresh != self._data['sdk_inventory']:
            raise ValueError('SDK inventory changed after inspection')
        if list(self._capture.sdk_directory_records) != self._data['sdk_directory_facts']:
            raise ValueError('SDK physical directory facts changed after inspection')


def inspect_request(path, pin, *, repository_root=ROOT):
    started = time.monotonic()
    path = _absolute(path)
    try:
        request = read_document(path, pin)
    except FileNotFoundError:
        _missing('sdk-admission-request', path, 'Original SDK admission request absent')
    _record(request, 'foundation-native-sdk-admission-request-v1', ('target', 'sdk', 'retained_group', 'restoration', 'observations', 'host_tools', 'policy', 'limits'), 'sdk-admission-request', path)
    target = _target(request['target']); group = _group(request['retained_group']); policy = _policy(request['policy']); limits = _limits(request['limits'])
    import appended_engine_native_inputs as native
    inputs = native.InputSet(); inputs.deadline = started + limits['prepare_seconds']
    capture = _Capture(inputs, limits)
    _file(capture, path, pin, 'sdk-admission-request')
    controls = []
    root = _ordinary(repository_root, True)
    for name in CONTROL_PATHS:
        source = root / name
        if not source.exists():
            _missing('sdk-adapter-control', source, 'Exact producer source/template absent')
        if source.lstat().st_size > min(MAX_DOCUMENT, limits['maximum_document_bytes']):
            raise ValueError('SDK adapter control exceeds document bound')
        raw = _control_raw(source)
        sha = hashlib.sha256(raw).hexdigest()
        item = capture.repository_file(source, sha, 'sdk-adapter-control', repository_root=root, source_paths=CONTROL_PATHS)
        controls.append({'path': name, 'sha256': sha, 'bytes': item['bytes'], 'mode': item['mode']})
    metadata, path_policy = _sdk_metadata(request['sdk'], group, capture, target)
    tools, compiler, restoration, observations = _observations(request, path.parent, capture,
        request['sdk'], group, metadata, repository_root=root)
    inventory = _walk_sdk(capture, request['sdk']['root'], metadata, request['sdk']['manifest_sha256'], path_policy)
    host_document, host_ref = _document(request['host_tools'], path.parent, capture, 'sdk-host-tools')
    toolchain = {'kind': 'foundation-native-engine-prototype-sdk-toolchain-v1', 'sdk_binding': {'root': request['sdk']['root'], 'metadata': metadata, 'host_document': host_document, 'policy': policy, 'sdk_manifest_sha256': request['sdk']['manifest_sha256']}, 'inventories': {'sdk': dict(root=request['sdk']['root'], files=inventory['files'], directories=inventory['directories'], modes=inventory['modes'])}, 'tools': tools}
    try:
        host = native.parse_host_tools(host_document, Path(host_ref['path']).parent, capture, toolchain, repository_root=root)
    except ValueError as error:
        if hasattr(error, 'missing'):
            raise MissingInputs(error.missing) from error
        raise
    expected_path = ':'.join(sorted({str(Path(item['path']).parent) for item in list(tools.values()) + list(host['programs'].values())}))
    environment = {'PATH': expected_path, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC', 'SOURCE_DATE_EPOCH': policy['source_date_epoch']}
    native.render_environment(dict(toolchain, environment=environment), host)
    data = dict(schema_version=1, kind='foundation-native-sdk-admission-inspection-v1', scope=SCOPE, request={'path': str(path), 'sha256': pin}, target=target, sdk=dict(request['sdk']), retained_group=group, restoration=restoration, observations=observations, host_tools=host_ref, policy=policy, limits=limits, sdk_inventory=inventory, sdk_directory_facts=list(inputs.sdk_directory_records), tools=tools, compiler=compiler, inputs=list(inputs.records), controls=sorted(controls, key=lambda item: item['path']), **FLAGS)
    inspection = SDKInspection(data, capture, metadata, path_policy)
    inspection.recheck()
    return inspection


def _fresh(output, protected):
    output = _absolute(output); _ordinary(output.parent, True)
    for item in protected:
        if output == item or output in item.parents or item in output.parents:
            raise ValueError('SDK output overlaps an admitted input')
    if output.exists() or output.is_symlink():
        raise ValueError('SDK admission output must be fresh')
    output.mkdir(mode=0o700)
    return output


def _save(root, name, raw, *, maximum=MAX_DOCUMENT):
    if len(raw) > maximum:
        raise ValueError('SDK generated metadata exceeds output bound')
    destination = root / _name(name)
    current = root
    for part in destination.relative_to(root).parts[:-1]:
        current = current / part
        try:
            current.mkdir(mode=0o755)
        except FileExistsError:
            _ordinary(current, True)
            if stat.S_IMODE(current.lstat().st_mode) != 0o755:
                raise ValueError('Unexpected publication directory mode')
        else:
            # Normalize only this invocation's newly created private children.
            descriptor = os.open(current, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fchmod(descriptor, 0o755)
            finally:
                os.close(descriptor)
    with destination.open('xb') as stream:
        stream.write(raw)
        os.fchmod(stream.fileno(), 0o644)
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'mode': 0o644}


def _plan(inspection):
    return dict(schema_version=1, kind='foundation-native-sdk-admission-plan-v1', scope=SCOPE, request=inspection.as_dict()['request'], inspection=inspection.as_dict(), **FLAGS)


def _reserve(parent, limits, publication):
    filesystem = os.statvfs(parent)
    block = max(4096, filesystem.f_frsize)
    directories = {item.as_posix() for name in publication for item in Path(name).parents}
    # One complete allocation block per file/owned directory is a conservative
    # margin in addition to exact known file bytes and the requested reserve.
    needed = sum(len(raw) for raw in publication.values()) + block * (len(publication) + len(directories))
    if filesystem.f_bavail * filesystem.f_frsize < limits['minimum_free_bytes'] + needed:
        raise ValueError('SDK admission free-space reserve plus complete publication unavailable')


def create_plan(request, pin, output, *, repository_root=ROOT):
    inspection = inspect_request(request, pin, repository_root=repository_root)
    inspection.recheck()
    result = _plan(inspection)
    raw = encoded(result)
    if len(raw) > inspection._data['limits']['maximum_output_bytes']:
        raise ValueError('SDK plan exceeds declared complete output bound')
    _reserve(_absolute(output).parent, inspection._data['limits'], {'plan.json': raw})
    output = _fresh(output, inspection.protected_paths)
    _save(output, 'plan.json', raw, maximum=inspection._data['limits']['maximum_output_bytes'])
    return result


def render_toolchain(template, values):
    if type(template) is not bytes or type(values) is not dict:
        raise ValueError('SDK template and literal values required')
    try:
        text = template.decode('ascii')
    except UnicodeError as error:
        raise ValueError('SDK toolchain template must be ASCII') from error
    tokens = set(re.findall('@([A-Z][A-Z0-9_]*)@', text))
    if set(values) != tokens:
        raise ValueError('SDK template literal token set mismatch')
    for key, value in values.items():
        if type(value) is not str or not value and key != 'PKG_CONFIG_LIBDIR' or any(c in value for c in ';\"\'\\$@\n\r\x00'):
            raise ValueError('SDK CMake literal injection refused')
        text = text.replace('@' + key + '@', value)
    if '@' in text:
        raise ValueError('SDK template has unresolved token marker')
    return text.encode('ascii')


def _toolchain_values(sdk, metadata, tools):
    values = {'SDK_ROOT': sdk['root'], 'SDK_MANIFEST_SHA256': sdk['manifest_sha256'], 'SDK_SYSROOT': str(Path(sdk['root']) / metadata['target']['sysroot'])}
    values.update({role.upper(): item['path'] for role, item in tools.items()})
    values.update({role.upper() + '_SHA256': item['sha256'] for role, item in tools.items()})
    prefix = metadata['target']['sysroot'] + '/'
    values['PKG_CONFIG_LIBDIR'] = ':'.join(sorted({str(Path(sdk['root']) / Path(name).parent) for name in metadata['files'] if name.startswith(prefix) and name.endswith('.pc')}))
    return values


def prepare(plan, pin, output, *, repository_root=ROOT):
    plan = _absolute(plan); original = read_document(plan, pin)
    if _control_raw(plan) != encoded(original):
        raise ValueError('SDK plan must contain the exact original canonical bytes')
    _record(original, 'foundation-native-sdk-admission-plan-v1', ('scope', 'request', 'inspection', *FLAGS), 'sdk-admission-plan', plan)
    request = original['request']
    _fields(request, ('path', 'sha256'), 'Original SDK request')
    inspection = inspect_request(request['path'], request['sha256'], repository_root=repository_root)
    if encoded(original) != encoded(_plan(inspection)):
        raise ValueError('SDK admission plan/source/control bytes changed')
    inspection.recheck()
    data = inspection.as_dict(); capture = inspection._capture
    output = _absolute(output)
    root = _ordinary(repository_root, True)
    # Derive all bytes and the complete publication size before creating output.
    generated = {}
    def stage(name, raw):
        name = _name(name)
        if name in generated and generated[name] != raw:
            raise ValueError('SDK metadata aliases conflict')
        generated[name] = raw
    request_base = Path(request['path']).parent
    def retained_ref(ref):
        source = Path(ref['path'])
        if request_base not in source.parents:
            raise ValueError('Original metadata must be confined below request directory for exact retained relative refs')
        return {'path': 'observations/original/' + source.relative_to(request_base).as_posix(), 'sha256': ref['sha256']}
    for item in capture.records:
        source = Path(item['path'])
        retain_metadata = any('provenance' in role or 'inventory' in role or role == 'host-runtime-facts' for role in item['roles'])
        if retain_metadata and request_base in source.parents and not (Path(data['sdk']['root']) == source or Path(data['sdk']['root']) in source.parents):
            if item['bytes'] > MAX_DOCUMENT:
                raise ValueError('Original retained observation is not bounded metadata')
            stage('observations/original/' + source.relative_to(request_base).as_posix(), capture.bytes(source))
    for name, destination in ((CONTROL_PATHS[0], 'producer/adapter.py'), (TEMPLATE, 'producer/template.cmake.in')):
        stage(destination, capture.bytes(root / name))
    identity = dict(schema_version=1, kind='foundation-native-toolchain-identity-v1', target=data['target'], compiler=data['compiler'], runtime=data['policy']['runtime'], cpu=data['policy']['cpu'])
    stage('metadata/identity.json', encoded(identity))
    values = _toolchain_values(data['sdk'], inspection._metadata, data['tools'])
    stage('metadata/native-toolchain.cmake', render_toolchain(generated['producer/template.cmake.in'], values))
    meta_files = {name[len('metadata/'):]: hashlib.sha256(raw).hexdigest() for name, raw in generated.items() if name.startswith('metadata/')}
    stage('inventories/toolchain.json', encoded({'files': meta_files, 'directories': [], 'modes': {name: 0o644 for name in meta_files}}))
    stage('inventories/sdk.json', encoded(data['sdk_inventory']))
    producer = {key: {'path': name, 'sha256': hashlib.sha256(generated[name]).hexdigest()} for key, name in (('adapter', 'producer/adapter.py'), ('template', 'producer/template.cmake.in'))}
    binding = dict(schema_version=1, kind='foundation-native-sdk-admission-binding-v1', target=data['target'], sdk=data['sdk'], retained_group=data['retained_group'], restoration=retained_ref(data['restoration']), observations=retained_ref(data['observations']), producer=producer, inventory={'root': data['sdk']['root'], 'inventory': {'path': 'inventories/sdk.json', 'sha256': hashlib.sha256(generated['inventories/sdk.json']).hexdigest()}}, tool_paths=data['tools'], sysroot=inspection._metadata['target']['sysroot'], host_tools=retained_ref(data['host_tools']), policy=data['policy'])
    stage('sdk-admission.json', encoded(binding))
    environment = {'PATH': ':'.join(sorted({str(Path(item['path']).parent) for item in data['tools'].values()})), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC', 'SOURCE_DATE_EPOCH': data['policy']['source_date_epoch']}
    # Include all admitted generator paths, not just SDK tool directories.
    host_original = read_document(data['host_tools']['path'], data['host_tools']['sha256'])
    environment['PATH'] = ':'.join(sorted({str(Path(item['path']).parent) for item in list(data['tools'].values()) + list(host_original['programs'].values())}))
    toolchain = dict(schema_version=1, kind='foundation-native-engine-prototype-sdk-toolchain-v1', target=data['target'], engine_cxx_standard=23, identity={'cxx_standard': 23, 'identity_sha256': hashlib.sha256(generated['metadata/identity.json']).hexdigest(), 'runtime_policy': 'private-native', 'paired_sdk_sha256': None, 'target_baseline': 'glibc2.36'}, tools=data['tools'], inventories={'toolchain': {'root': str(output / 'metadata'), 'inventory': {'path': 'inventories/toolchain.json', 'sha256': hashlib.sha256(generated['inventories/toolchain.json']).hexdigest()}}, 'sdk': binding['inventory']}, compiler=data['compiler'], runtime=data['policy']['runtime'], cpu=data['policy']['cpu'], environment=environment, sdk_admission={'path': 'sdk-admission.json', 'sha256': hashlib.sha256(generated['sdk-admission.json']).hexdigest()})
    stage('toolchain.json', encoded(toolchain))
    outputs = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'mode': 0o644} for name, raw in generated.items()}
    result = dict(schema_version=1, kind='foundation-native-sdk-admission-prepare-v1', scope=SCOPE, plan={'path': str(plan), 'sha256': pin}, request=request, target=data['target'], toolchain={'path': 'toolchain.json', 'sha256': outputs['toolchain.json']['sha256']}, sdk_admission={'path': 'sdk-admission.json', 'sha256': outputs['sdk-admission.json']['sha256']}, identity={'path': 'metadata/identity.json', 'sha256': outputs['metadata/identity.json']['sha256']}, outputs=outputs, **FLAGS)
    stage('prepare-receipt.json', encoded(result))
    if sum(len(raw) for raw in generated.values()) > data['limits']['maximum_output_bytes'] or len(generated) > data['limits']['maximum_files']:
        raise ValueError('SDK complete publication aggregate exceeds declared bound')
    _reserve(output.parent, data['limits'], generated)
    inspection.recheck()
    output = _fresh(output, (*inspection.protected_paths, plan))
    remaining = dict(generated)
    for name, raw in sorted(generated.items()):
        if name == 'prepare-receipt.json':
            continue
        _reserve(output.parent, data['limits'], remaining)
        capture.check_deadline(); _save(output, name, raw, maximum=data['limits']['maximum_output_bytes'])
        remaining.pop(name)
    inspection.recheck()
    _reserve(output.parent, data['limits'], remaining)
    _save(output, 'prepare-receipt.json', generated['prepare-receipt.json'], maximum=data['limits']['maximum_output_bytes'])
    return result


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    for name, source in (('plan', 'request'), ('prepare', 'plan')):
        action = actions.add_parser(name)
        action.add_argument('--' + source, type=Path, required=True)
        action.add_argument('--' + source + '-sha256', required=True)
        action.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = create_plan(args.request, args.request_sha256, args.output) if args.action == 'plan' else prepare(args.plan, args.plan_sha256, args.output)
        print(encoded(result).decode('ascii'), end='')
        return 0
    except MissingInputs as error:
        print(encoded(error.as_dict()).decode('ascii'), end='')
        return 2
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
