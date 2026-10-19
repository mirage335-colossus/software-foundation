#!/usr/bin/env python3
"""Passive, explicit native prototype input admission and source preparation.

This module never starts programs, discovers SDKs, downloads inputs or qualifies
a native engine. Original retained observations remain observations; byte and
schema checks cannot replace an actual compile, shared link or runtime check.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tarfile
import time
import zipfile

import appended_engine_manifest as manifest
import appended_engine_native_actions_contract as actions
from dependency_archive import PathInventory, encoded, relative, require_linux_case_host, sdk_path_policy

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'recipes/webkitwasm-native-rich4083-v1'
PROFILE = RECIPE + '/native-prototype-profile.json'
PRIVATE_TOOLCHAIN_KIND = 'foundation-native-engine-prototype-private-sdk-toolchain-v1'
PRIVATE_RUNTIME_POLICY = RECIPE + '/producer/private-cpp-runtime-policy-v1.json'
DIAGNOSTIC_HOST_POLICY = RECIPE + '/producer/diagnostic-host-policy-v1.json'
TARGET = {'system': 'Linux', 'processor': 'x86_64', 'triple': 'x86_64-buildroot-linux-gnu', 'pointer_bits': 64}
SCOPE = 'native-prototype-static-input-contract-only'
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024 * 1024
MAX_BYTES = 32 * 1024 * 1024 * 1024
MAX_FILES = 65536
MAX_MEMBERS = 1000000
MAX_MEMBER = 256 * 1024 * 1024
TOOL_NAMES = ('c', 'cxx', 'linker', 'archiver', 'ranlib', 'inspect', 'cmake', 'ninja', 'pkg_config')
HOST_REQUIRED = frozenset(('python', 'perl', 'ruby', 'gperf', 'cmake', 'ninja', 'sh'))
HOST_ALLOWED = HOST_REQUIRED | frozenset(('make', 'bash', 'sed', 'awk', 'grep', 'find', 'sort', 'cat',
    'cp', 'mkdir', 'rm', 'ln', 'touch', 'uname', 'tar', 'patch', 'autoconf', 'automake', 'libtool',
    'install', 'mv', 'chmod', 'rmdir', 'expr', 'tr', 'cut', 'head', 'tail', 'wc', 'basename',
    'dirname', 'env', 'date'))
LIBRARIES = frozenset(('ICU::data', 'ICU::i18n', 'ICU::uc', 'HarfBuzz::HarfBuzz', 'HarfBuzz::ICU',
    'Freetype::Freetype', 'Fontconfig::Fontconfig', 'JPEG::JPEG', 'LibXml2::LibXml2', 'PNG::PNG',
    'SQLite3::SQLite3', 'WebP::libwebp', 'WebP::demux', 'WebP::sharpyuv', 'ZLIB::ZLIB',
    'CURL::libcurl', 'OpenSSL::SSL', 'OpenSSL::Crypto', 'LibPSL::LibPSL',
    'FoundationNative::nghttp2', 'Brotli::dec', 'Brotli::common'))
SYSTEM_LINKS = frozenset(('Threads::Threads', 'm', 'dl', 'rt', 'atomic'))
ROLE7_PRODUCERS = ('tools/appended_engine_native_role7.py',) + tuple(
    'tools/role7/' + name for name in ('__init__.py', 'common.py', 'observer.py', 'capture.py', 'os_origins.py'))
PRODUCERS = tuple(sorted((PROFILE, RECIPE + '/producer/native-initial-cache.cmake',
    RECIPE + '/producer/verify-provider.cmake', RECIPE + '/producer/native-sdk-toolchain.cmake.in',
    'tools/appended_engine_native_inputs.py', 'tools/appended_engine_native_sdk.py',
    'tools/appended_engine_native_original_proof.py',
    'tools/appended_engine_native_prototype.py', 'tools/process_tree.py', PRIVATE_RUNTIME_POLICY,
    DIAGNOSTIC_HOST_POLICY, RECIPE + '/producer/native-private-runtime.cmake',
    RECIPE + '/producer/runtime-probe/CMakeLists.txt', RECIPE + '/producer/runtime-probe/runtime_probe.cpp') + ROLE7_PRODUCERS))
SOURCE_PROVENANCE_ROLES = frozenset(('git-controls', 'git-top-tree', 'git-selected-tree',
    'git-tree-receipt', 'engine-member-inventory', 'engine-body-verification'))
SOURCE_PROVENANCE_OPTIONAL = frozenset(('git-runner', 'git-parser-failure'))
ENGINE_COMMIT = 'aec9d2ad958e716ab4bca4bf03007e6edac7323f'
SUPPLIER_PATCH = 'f25940d21c8ba37d62a6d48ea6da25053af1559bde323d0bfc9ba25cad2bca84'


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value, label='input'):
    manifest.sha256(value, label)
    if value == '0' * 64:
        raise ValueError('A nonzero independent SHA256 is required: ' + label)
    return value


def strict_json(raw, label='native input'):
    if type(raw) is not bytes or len(raw) > MAX_DOCUMENT:
        raise ValueError(label + ' exceeds its JSON byte bound')
    try:
        value = manifest.json_bytes(raw.decode('utf-8'))
        encoded(value).decode('ascii')
        # ensure_ascii alone accepts lone surrogates; require real UTF-8 too.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (UnicodeError, OverflowError, RecursionError, TypeError) as error:
        raise ValueError('Invalid finite UTF-8 JSON: ' + label) from error
    return value


def _fields(value, names, label):
    return manifest.fields(value, names, label)


def _schema(value, names, kind):
    _fields(value, names, kind)
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != kind:
        raise ValueError('Unsupported ' + kind)
    return value


def _text(value, label):
    manifest.text(value, label)
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ValueError('Invalid Unicode: ' + label) from error
    return value


def _name(value):
    return manifest.path_name(value)


def _names(value, label, nonempty=False):
    return manifest.paths(value, label, nonempty)


def _absolute(value):
    if not isinstance(value, (str, Path)):
        raise ValueError('An explicit normalized absolute path is required')
    path = Path(value)
    if not path.is_absolute() or str(path) != str(value) or '..' in path.parts or any(
            child in str(path) for child in (';', ':', '\n', '\r', '\x00')):
        raise ValueError('An explicit normalized absolute path is required: ' + str(value))
    return path


def _identity(state):
    return (state.st_dev, state.st_ino, state.st_mode, state.st_nlink,
            state.st_size, state.st_mtime_ns, state.st_ctime_ns)


def _ordinary(path, directory=False):
    path = _absolute(path)
    for parent in reversed((path, *path.parents)):
        manifest.plain_state(parent.lstat(), directory=directory if parent == path else True)
    if path.resolve(strict=True) != path:
        raise ValueError('Native input path is not ordinary: ' + str(path))
    return path


def _ref(ref, base):
    _fields(ref, ('path', 'sha256'), 'independent file reference')
    return _absolute(base) / _name(ref['path']), pin(ref['sha256'], ref['path'])


class MissingInputs(ValueError):
    """Explicit missing prerequisites, never a request for a fallback build."""
    def __init__(self, missing):
        self.missing = tuple(dict(item) for item in missing)
        self.roles = tuple(item['role'] for item in self.missing)
        super().__init__('Missing retained native inputs: ' + '; '.join(
            item['role'] + ': ' + item['path'] + ' (' + item['reason'] + ')' for item in self.missing))

    def as_dict(self):
        return {'schema_version': 1, 'kind': 'foundation-native-engine-prototype-missing-inputs-v1',
                'scope': SCOPE, 'missing': [dict(item) for item in self.missing],
                'executable_plan': False, 'production_eligible': False}


class InputSet:
    """Bounded explicit files and explicitly selected complete roots only."""
    def __init__(self):
        self._records = {}
        self._identities = {}
        self._roots = {}
        self._sdk_roots = {}
        self._total = 0
        self.deadline = None
        self._repository_sources = {}
        self._sdk_manifests = {}
        self._sdk_directory_authorities = {}
        self._sdk_directories = {}

    def check_deadline(self):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise ValueError('Native input preparation deadline expired')

    @property
    def records(self):
        return tuple(dict(self._records[name], roles=list(self._records[name]['roles']))
                     for name in sorted(self._records))

    @property
    def sdk_directory_records(self):
        """Physical SDK directory facts, never retained file DATA aliases."""
        return tuple(dict(self._sdk_directories[name], identity=list(self._sdk_directories[name]['identity']))
                     for name in sorted(self._sdk_directories))

    @property
    def protected_paths(self):
        return tuple(Path(name) for name in sorted(set(self._records) | set(self._roots) |
                     set(self._sdk_roots) | set(self._sdk_directories)))

    def file(self, path, sha, role, maximum=MAX_FILE):
        return self._file(path, sha, role, maximum=maximum, repository_source=False)

    def _file(self, path, sha, role, *, maximum, repository_source, sdk_manifest=False):
        self.check_deadline()
        path = _absolute(path)
        pin(sha, role)
        _text(role, 'input role')
        try:
            _ordinary(path)
        except FileNotFoundError as error:
            raise MissingInputs([{'role': role, 'path': str(path), 'reason': 'ordinary retained file absent'}]) from error
        before = path.lstat()
        physical_mode = stat.S_IMODE(before.st_mode)
        source = self._repository_sources.get(str(path)) if repository_source else None
        generated = self._sdk_manifests.get(str(path)) if sdk_manifest else None
        allowed_modes = ((0o600, 0o644, 0o755) if generated is not None else
                         (0o644, 0o664, 0o755, 0o775) if source is not None else (0o644, 0o755))
        if physical_mode not in allowed_modes:
            raise ValueError('Native retained file mode must be 0644/0755: ' + str(path))
        mode = (0o644 if generated is not None and physical_mode == 0o600 else
                (0o755 if physical_mode & 0o111 else 0o644) if source is not None else physical_mode)
        key = str(path)
        old = self._records.get(key)
        if old is not None:
            if old['bytes'] > maximum or old['sha256'] != sha or _identity(before) != self._identities[key]:
                raise ValueError('Conflicting or changed explicit input: ' + key)
            if role not in old['roles']:
                old['roles'] = sorted(old['roles'] + [role])
            return dict(old, roles=list(old['roles']))
        if (len(self._records) >= MAX_FILES or before.st_size > maximum
                or before.st_size > MAX_FILE or before.st_size > MAX_BYTES - self._total):
            raise ValueError('Native input exceeds declared file/count/total byte bound: ' + key)
        digest = hashlib.sha256()
        count = 0
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            if _identity(os.fstat(stream.fileno())) != _identity(before):
                raise ValueError('Native input changed before read: ' + key)
            while True:
                self.check_deadline()
                block = stream.read(min(1024 * 1024, maximum - count + 1))
                if not block:
                    break
                count += len(block)
                if count > maximum or count > before.st_size:
                    raise ValueError('Native input grew beyond bound: ' + key)
                digest.update(block)
            after = os.fstat(stream.fileno())
        if (_identity(before) != _identity(after) or _identity(path.lstat()) != _identity(before)
                or count != before.st_size or digest.hexdigest() != sha):
            raise ValueError('Native input differs from independent bytes/identity: ' + key)
        record = {'path': key, 'sha256': sha, 'bytes': count, 'mode': mode, 'roles': [role]}
        if source is not None:
            record.update(physical_mode=physical_mode, mode_policy='repository-producer-logical-v1')
        if generated is not None and physical_mode == 0o600:
            record.update(physical_mode=physical_mode, mode_policy='generated-sdk-root-manifest-v1')
        self._records[key] = record
        self._identities[key] = _identity(before)
        self._total += count
        return dict(record, roles=[role])

    def repository_file(self, path, sha, role, *, repository_root, source_paths, maximum=MAX_DOCUMENT):
        """Normalize only an explicit producer-source allowlist, never SDK data."""
        path = _absolute(path)
        root = _ordinary(_absolute(repository_root), True)
        if type(source_paths) not in (tuple, list) or not 1 <= len(source_paths) <= 256:
            raise ValueError('Explicit finite repository producer source path authority required')
        names = tuple(_name(name) for name in source_paths)
        if len(names) != len(set(names)) or root not in path.parents or path.relative_to(root).as_posix() not in names:
            raise ValueError('Path is outside the explicit repository producer source allowlist')
        authority = (root, names)
        previous = self._repository_sources.get(str(path))
        if previous is not None and previous != authority:
            raise ValueError('Repository producer source mode authority changed')
        if str(path) in self._sdk_manifests:
            raise ValueError('SDK manifest authority cannot become repository source authority')
        if str(path) in self._records and previous is None:
            raise ValueError('An already retained input cannot acquire a source mode waiver')
        self._repository_sources[str(path)] = authority
        return self._file(path, sha, role, maximum=maximum, repository_source=True)

    def sdk_manifest_file(self, path, sha, role, *, sdk_root, manifest_sha256, maximum=MAX_DOCUMENT):
        """Capture only declared root/sdk.json; this does not admit an SDK.

        The supported installer atomically creates this generated JSON as0600.
        Preserve that physical fact while retaining ordinary logical0644 data.
        SDK schema, original restoration and full inventory validation remain
        the caller's separate mandatory gates. Public file() stays strict.
        """
        path = _absolute(path)
        root = _ordinary(_absolute(sdk_root), True)
        manifest_sha256 = pin(manifest_sha256, 'declared SDK root manifest')
        if path != root / 'sdk.json' or sha != manifest_sha256:
            raise ValueError('Generated SDK manifest requires its exact declared root/path/pin')
        authority = (root, manifest_sha256)
        previous = self._sdk_manifests.get(str(path))
        if previous is not None and previous != authority:
            raise ValueError('Generated SDK manifest authority changed')
        if str(path) in self._repository_sources:
            raise ValueError('Repository source authority cannot become SDK manifest authority')
        self._sdk_manifests[str(path)] = authority
        return self._file(path, sha, role, maximum=min(maximum, MAX_DOCUMENT),
                          repository_source=False, sdk_manifest=True)

    def sdk_directory(self, path, *, sdk_root, manifest_sha256, maximum_directories=MAX_FILES):
        """Capture only parents of files in an already captured SDK manifest.

        This typed lane preserves installer/umask physical0755 or0775 facts;
        its logical0755 is never a waiver for generic inventories or files.
        SDK schema/restoration/full inventory admission remains separate.
        """
        self.check_deadline()
        path, root = _absolute(path), _absolute(sdk_root)
        digest = pin(manifest_sha256, 'SDK directory manifest authority')
        manifest.integer(maximum_directories, 'SDK directory capture bound', 1, MAX_FILES)
        manifest_path = root / 'sdk.json'
        record = self._records.get(str(manifest_path))
        if (self._sdk_manifests.get(str(manifest_path)) != (root, digest)
                or record is None or record['sha256'] != digest):
            raise ValueError('SDK directories require the already captured independent root manifest')
        self.sdk_manifest_file(manifest_path, digest, record['roles'][0], sdk_root=root,
                               manifest_sha256=digest)
        authority = self._sdk_directory_authorities.get(str(root))
        if authority is None:
            metadata = strict_json(self.bytes(manifest_path), 'SDK directory authority')
            # Historical lower-level typed-inventory fixtures with exact{}
            # authorize only their root, never an invented nested parent.
            if metadata == {}:
                files = {}
            elif (type(metadata) is not dict or type(metadata.get('files')) is not dict
                    or not metadata['files'] or len(metadata['files']) > MAX_FILES):
                raise ValueError('SDK directory authority requires its captured finite file map')
            else:
                files = metadata['files']
            policy = sdk_path_policy(metadata)
            if policy == 'linux-case-sensitive-v1':
                require_linux_case_host()
            registry = PathInventory(policy)
            registry.add('sdk.json', False)
            allowed = {str(root)}
            for name, file_pin in files.items():
                self.check_deadline()
                registry.add(name, False)
                pin(file_pin, 'SDK directory-authorizing file')
                for parent in relative(name).parents:
                    self.check_deadline()
                    if parent.as_posix() != '.':
                        allowed.add(str(root / parent))
                        if len(allowed) > MAX_FILES:
                            raise ValueError('SDK manifest directory authority exceeds its count bound')
            authority = (digest, frozenset(allowed))
            self._sdk_directory_authorities[str(root)] = authority
        if authority[0] != digest or str(path) not in authority[1]:
            raise ValueError('SDK directory is outside the captured manifest parent authority')
        key = str(path)
        old = self._sdk_directories.get(key)
        if len(self._sdk_directories) > maximum_directories or (
                old is None and len(self._sdk_directories) >= maximum_directories):
            raise ValueError('SDK directory capture count bound exceeded')
        try:
            state = _ordinary(path, True).lstat()
        except FileNotFoundError as error:
            raise MissingInputs([{'role': 'sdk-directory', 'path': key,
                                  'reason': 'manifest-derived ordinary SDK directory absent'}]) from error
        physical_mode = stat.S_IMODE(state.st_mode)
        if physical_mode not in (0o755, 0o775):
            raise ValueError('Typed SDK directory physical mode must be0755/0775: ' + key)
        fact = {'path': key, 'sdk_root': str(root), 'manifest_sha256': digest,
                'physical_mode': physical_mode, 'mode': 0o755,
                'mode_policy': 'generated-sdk-manifest-parent-directories-v1',
                'identity': list(_identity(state))}
        if old is not None and fact != old:
            raise ValueError('SDK directory physical identity or authority changed: ' + key)
        self.check_deadline()
        if _identity(path.lstat()) != _identity(state):
            raise ValueError('SDK directory changed during capture: ' + key)
        self._sdk_directories[key] = fact
        return dict(fact, identity=list(fact['identity']))

    def document(self, ref, base, role):
        path, sha = _ref(ref, base)
        self.file(path, sha, role, maximum=MAX_DOCUMENT)
        return strict_json(self.bytes(path), role)

    def bytes(self, path, maximum=MAX_DOCUMENT):
        path = _absolute(path)
        record = self._records.get(str(path))
        if record is None or record['bytes'] > maximum:
            raise ValueError('Read requires a captured bounded explicit file: ' + str(path))
        authority = self._repository_sources.get(str(path))
        generated = self._sdk_manifests.get(str(path))
        if generated is not None:
            self.sdk_manifest_file(path, record['sha256'], record['roles'][0],
                                   sdk_root=generated[0], manifest_sha256=generated[1], maximum=maximum)
        elif authority is None:
            self.file(path, record['sha256'], record['roles'][0], maximum=maximum)
        else:
            root, names = authority
            self.repository_file(path, record['sha256'], record['roles'][0], repository_root=root,
                source_paths=names, maximum=maximum)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            if _identity(os.fstat(stream.fileno())) != self._identities[str(path)]:
                raise ValueError('Captured input changed before bounded read: ' + str(path))
            raw = stream.read(maximum + 1)
            after = _identity(os.fstat(stream.fileno()))
        if (len(raw) != record['bytes'] or sha256(raw) != record['sha256']
                or after != self._identities[str(path)] or _identity(path.lstat()) != after):
            raise ValueError('Captured input changed while reading: ' + str(path))
        return raw

    def inventory(self, record, base, role):
        return self._inventory(record, base, role, sdk_binding=None)

    def sdk_inventory(self, record, base, role, *, binding):
        """Use only the inventory bound to original SDK metadata admission."""
        _fields(record, ('root', 'inventory'), role + ' SDK inventory record')
        if type(binding) is not dict or not {'root', 'inventory', 'inventory_base', 'inventory_path',
                'files', 'directories', 'modes', 'path_policy', 'sdk_manifest_sha256', 'metadata'} <= set(binding):
            raise ValueError('Original SDK admission binding is required for its inventory')
        _fields(binding['inventory'], ('path', 'sha256'), 'original SDK inventory reference')
        if type(binding['metadata']) is not dict:
            raise ValueError('Original parsed SDK metadata is required')
        _sdk_inventory_contract({name: binding[name] for name in ('files', 'directories', 'modes')}, binding['path_policy'])
        path, _ = _ref(record['inventory'], base)
        if (record['root'] != binding['root'] or record['inventory']['sha256'] != binding['inventory']['sha256']
                or path != _absolute(binding['inventory_path'])
                or _absolute(binding['inventory_base']) / _name(binding['inventory']['path']) != path
                or sdk_path_policy(binding['metadata']) != binding['path_policy']):
            raise ValueError('SDK inventory differs from original admitted root/reference/path policy')
        if binding['path_policy'] == 'linux-case-sensitive-v1':
            require_linux_case_host()
        if binding['files'].get('sdk.json') != pin(binding['sdk_manifest_sha256'], 'original SDK manifest'):
            raise ValueError('SDK complete inventory must bind the original sdk.json bytes')
        sdk_manifest = _absolute(binding['root']) / 'sdk.json'
        self.sdk_manifest_file(sdk_manifest, binding['sdk_manifest_sha256'],
                               'sdk-provenance-sdk-manifest', sdk_root=binding['root'],
                               manifest_sha256=binding['sdk_manifest_sha256'], maximum=MAX_DOCUMENT)
        if strict_json(self.bytes(sdk_manifest), 'original SDK metadata') != binding['metadata']:
            raise ValueError('SDK inventory policy metadata differs from captured sdk.json')
        return self._inventory(record, base, role, sdk_binding=binding)

    def _inventory(self, record, base, role, *, sdk_binding):
        _fields(record, ('root', 'inventory'), role + ' inventory record')
        root = _absolute(record['root'])
        try:
            _ordinary(root, True)
        except FileNotFoundError as error:
            raise MissingInputs([{'role': role, 'path': str(root), 'reason': 'complete ordinary retained root absent'}]) from error
        path, _ = _ref(record['inventory'], base)
        if root == path or root in path.parents:
            raise ValueError('Inventory document must be outside its inventoried root')
        value = self.document(record['inventory'], base, role + '-inventory')
        _fields(value, ('files', 'directories', 'modes'), role + ' complete inventory')
        if sdk_binding is None:
            manifest.inventory_contract(value, '__native_inventory_manifest__.json')
            name_check = _name
        else:
            if value != {name: sdk_binding[name] for name in ('files', 'directories', 'modes')}:
                raise ValueError('SDK inventory document differs from original admission')
            _sdk_inventory_contract(value, sdk_binding['path_policy'])
            name_check = lambda name: str(relative(name))
        if len(value['files']) + len(value['directories']) > MAX_FILES:
            raise ValueError('Complete native inventory exceeds entry bound')
        found_files, found_dirs = set(), set()
        entries = 0
        def walk(directory):
            nonlocal entries
            before = directory.lstat()
            _ordinary(directory, True)
            if sdk_binding is not None:
                self.sdk_directory(directory, sdk_root=root,
                                   manifest_sha256=sdk_binding['sdk_manifest_sha256'])
            children = []
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    self.check_deadline()
                    entries += 1
                    if entries > MAX_FILES:
                        raise ValueError('Actual native inventory exceeds entry bound')
                    children.append(directory / entry.name)
            if sdk_binding is not None and sdk_binding['path_policy'] == 'linux-case-sensitive-v1':
                names = {child.name for child in children}
                for child in children:
                    self.check_deadline()
                    alternative = child.name.swapcase()
                    candidate = directory / alternative
                    if alternative != child.name and alternative not in names and (candidate.exists() or candidate.is_symlink()):
                        raise ValueError('SDK root filesystem folds case-distinct names')
            for child in sorted(children):
                self.check_deadline()
                state = manifest.plain_state(child.lstat())
                name = name_check(child.relative_to(root).as_posix())
                if stat.S_ISDIR(state.st_mode):
                    found_dirs.add(name)
                    mode = 0o755 if sdk_binding is not None else stat.S_IMODE(state.st_mode)
                    if name not in value['directories'] or mode != value['modes'].get(name):
                        raise ValueError('Unknown or wrong-mode native inventory directory: ' + name)
                    walk(child)
                else:
                    found_files.add(name)
                    if sdk_binding is not None and name == 'sdk.json':
                        captured = self.sdk_manifest_file(child, sdk_binding['sdk_manifest_sha256'], role,
                            sdk_root=root, manifest_sha256=sdk_binding['sdk_manifest_sha256'])
                        actual_mode = captured['mode']
                    else:
                        actual_mode = stat.S_IMODE(state.st_mode)
                    if name not in value['files'] or actual_mode != value['modes'].get(name):
                        raise ValueError('Unknown or wrong-mode native inventory file: ' + name)
                    if not (sdk_binding is not None and name == 'sdk.json'):
                        self.file(child, pin(value['files'][name], name), role)
            if _identity(directory.lstat()) != _identity(before):
                raise ValueError('Native inventory directory changed during scan')
        walk(root)
        if found_files != set(value['files']) or found_dirs != set(value['directories']):
            raise ValueError('Native inventory omits or adds actual files/directories')
        if sdk_binding is None:
            self._roots[str(root)] = (record, Path(base), role, value)
        else:
            self._sdk_roots[str(root)] = (_json_copy(record), Path(base), role, _json_copy(sdk_binding))
        return {'root': str(root), 'inventory': dict(record['inventory']),
                'files': dict(value['files']), 'directories': list(value['directories']), 'modes': dict(value['modes'])}

    def recheck(self):
        for fact in self.sdk_directory_records:
            self.sdk_directory(Path(fact['path']), sdk_root=fact['sdk_root'],
                               manifest_sha256=fact['manifest_sha256'])
        for key in sorted(self._records):
            self.check_deadline()
            item = self._records[key]
            if _identity(_ordinary(Path(key)).lstat()) != self._identities[key]:
                raise ValueError('Native input physical identity changed: ' + key)
            # A fresh InputSet rehashes instead of the identity-only reuse path.
            probe = InputSet()
            probe.deadline = self.deadline
            if key in self._sdk_manifests:
                root, digest = self._sdk_manifests[key]
                probe.sdk_manifest_file(Path(key), item['sha256'], item['roles'][0],
                                        sdk_root=root, manifest_sha256=digest)
            elif key in self._repository_sources:
                root, names = self._repository_sources[key]
                probe.repository_file(Path(key), item['sha256'], item['roles'][0], repository_root=root, source_paths=names)
            else:
                probe.file(Path(key), item['sha256'], item['roles'][0])
        for root, (record, base, role, _) in sorted(self._roots.items()):
            probe = InputSet()
            probe.deadline = self.deadline
            probe.inventory(record, base, role)
        for root, (record, base, role, binding) in sorted(self._sdk_roots.items()):
            self.check_deadline()
            probe = InputSet()
            probe.deadline = self.deadline
            probe.sdk_inventory(record, base, role, binding=binding)
        self.check_deadline()


def _sdk_inventory_contract(value, path_policy):
    """Validate the original Linux SDK namespace without changing generic R."""
    files, directories, modes = (value[name] for name in ('files', 'directories', 'modes'))
    if (type(files) is not dict or not files or type(directories) is not list
            or any(type(name) is not str for name in directories)
            or directories != sorted(set(directories)) or type(modes) is not dict
            or set(modes) != set(files) | set(directories)):
        raise ValueError('Invalid complete original SDK inventory')
    if len(files) + len(directories) > MAX_FILES:
        raise ValueError('Complete original SDK inventory exceeds entry bound')
    registry = PathInventory(path_policy)
    for name in directories:
        registry.add(name, True)
        if type(modes[name]) is not int or modes[name] != 0o755:
            raise ValueError('Original SDK directory mode must be 0755')
    for name, digest in files.items():
        registry.add(name, False)
        pin(digest, 'SDK inventory file')
        if type(modes[name]) is not int or modes[name] not in (0o644, 0o755):
            raise ValueError('Original SDK file mode must be 0644/0755')
    parents = {str(Path(name).parent).replace('\\', '/') for name in (*files, *directories) if '/' in name}
    if not parents <= set(directories):
        raise ValueError('Original SDK inventory omits a parent directory')


def validate_target(value):
    manifest.target_contract(value)
    if value != TARGET:
        if value['system'] == 'Windows':
            raise ValueError('Windows native producer needs the unfinished two-host metadata/publication join or qualified native adapter')
        raise ValueError('First native prototype supports only Linux/x86_64/x86_64-buildroot-linux-gnu/64')
    return dict(value)


def validate_phase_limits(value):
    names = ('prepare_seconds', 'configure_seconds', 'build_seconds', 'cleanup_seconds',
             'maximum_jobs', 'maximum_output_bytes', 'minimum_free_bytes', 'maximum_process_tree_bytes')
    _fields(value, names, 'native phase limits')
    for name in names:
        maximum = 2 if name == 'maximum_jobs' else (86400 if name.endswith('_seconds') else 2**50)
        manifest.integer(value[name], name, 1, maximum)
    return dict(value)


def _version(value, minimum, label):
    _text(value, label)
    match = re.fullmatch(r'(\d+)\.(\d+)(?:\.(\d+))?(?:[-+][A-Za-z0-9._-]+)?', value)
    if not match or tuple(int(n or 0) for n in match.groups()) < tuple(minimum):
        raise ValueError('Unsupported retained version: ' + label)
    return value


def _program(value, inventories, inputs, role):
    _fields(value, ('path', 'sha256', 'version'), role + ' program')
    path = _absolute(value['path'])
    _text(value['version'], role + ' original version')
    matches = []
    for inventory in inventories.values():
        root = Path(inventory['root'])
        if root in path.parents:
            name = path.relative_to(root).as_posix()
            if inventory['files'].get(name) == value['sha256'] and inventory['modes'].get(name) == 0o755:
                matches.append(inventory)
    if not matches:
        raise ValueError('Program must be exact executable in an admitted inventory: ' + role)
    inputs.file(path, pin(value['sha256'], role), role)
    return dict(value)


def parse_toolchain(value, base, inputs, target, *, repository_root=ROOT):
    private_kind = type(value) is dict and value.get('kind') == PRIVATE_TOOLCHAIN_KIND
    sdk_kind = private_kind or type(value) is dict and value.get('kind') == 'foundation-native-engine-prototype-sdk-toolchain-v1'
    fields = ('schema_version', 'kind', 'target', 'engine_cxx_standard', 'identity', 'tools',
        'inventories', 'compiler', 'runtime', 'cpu', 'environment')
    _schema(value, fields + (('sdk_admission',) if sdk_kind else ()) +
        (('private_runtime_selection',) if private_kind else ()), PRIVATE_TOOLCHAIN_KIND if private_kind else
        'foundation-native-engine-prototype-sdk-toolchain-v1' if sdk_kind else 'foundation-native-engine-prototype-toolchain-v1')
    if value['target'] != validate_target(target) or type(value['engine_cxx_standard']) is not int or value['engine_cxx_standard'] != 23:
        raise ValueError('Native toolchain target/C++23 mismatch')
    binding = None
    if sdk_kind:
        try:
            import appended_engine_native_sdk as native_sdk
        except ModuleNotFoundError as error:
            if error.name != 'appended_engine_native_sdk':
                raise
            raise MissingInputs([{'role': 'sdk-admission-helper', 'path': str(ROOT / 'tools/appended_engine_native_sdk.py'),
                'reason': 'explicit native SDK admission source absent'}]) from error
        admission = inputs.document(value['sdk_admission'], base, 'sdk-provenance-admission')
        admission_path, _ = _ref(value['sdk_admission'], base)
        try:
            binding = native_sdk.validate_sdk_binding(admission, admission_path.parent, inputs,
                target=target, repository_root=repository_root)
        except native_sdk.MissingInputs as error:
            raise MissingInputs(error.missing) from error
    identity = manifest.toolchain_contract(value['identity'], target)
    pin(identity['identity_sha256'], 'toolchain identity')
    _fields(value['tools'], TOOL_NAMES, 'explicit native tools')
    if type(value['inventories']) is not dict or not 1 <= len(value['inventories']) <= 32 or 'toolchain' not in value['inventories']:
        raise ValueError('Named complete toolchain inventory is required')
    if sdk_kind and 'sdk' not in value['inventories']:
        raise ValueError('SDK-backed toolchain requires the original complete SDK inventory')
    inventories = {}
    for name, record in sorted(value['inventories'].items()):
        if '/' in _name(name):
            raise ValueError('Inventory name must be one component')
        if sdk_kind and name == 'sdk':
            inventories[name] = inputs.sdk_inventory(record, base, 'toolchain-sdk', binding=binding)
        else:
            inventories[name] = inputs.inventory(record, base, 'toolchain-' + name)
    compiler = _fields(value['compiler'], ('family', 'version', 'frontend', 'triple'), 'native compiler')
    if compiler['family'] != 'gcc' or compiler['frontend'] != 'gcc' or compiler['triple'] != target['triple']:
        raise ValueError('First native compiler policy requires explicit GCC frontend/target')
    _version(compiler['version'], (12, 2, 0), 'native GCC')
    runtime = _fields(value['runtime'], ('c_library', 'c_library_baseline', 'cxx_library',
        'cxx_library_baseline', 'linkage', 'sysroot_inventory', 'needed_libraries'), 'native runtime')
    if runtime['c_library'] != 'glibc' or runtime['cxx_library'] != 'libstdc++' or runtime['linkage'] != 'private-native':
        raise ValueError('Explicit glibc/libstdc++ private-native runtime required')
    for name in ('c_library_baseline', 'cxx_library_baseline'):
        if type(runtime[name]) is not str or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', runtime[name]):
            raise ValueError('Explicit dotted native runtime floor required')
    if runtime['sysroot_inventory'] not in inventories:
        raise ValueError('Native sysroot inventory is missing')
    needed = runtime['needed_libraries']
    if type(needed) is not list or not needed or any(type(name) is not str for name in needed) or needed != sorted(set(needed)) or any(
            not re.fullmatch(r'lib[A-Za-z0-9_+.-]+\.so(?:\.[0-9]+)*', name) for name in needed):
        raise ValueError('Explicit sorted native DT_NEEDED allowlist required')
    if value['cpu'] != {'baseline': 'sse2', 'source_dispatch': 'supplier-per-source-reviewed'}:
        raise ValueError('First native CPU baseline is explicit SSE2 with reviewed per-source dispatch')
    environment = _fields(value['environment'], ('PATH', 'LANG', 'LC_ALL', 'TZ', 'SOURCE_DATE_EPOCH'), 'native environment')
    if (environment['LANG'] != 'C.UTF-8' or environment['LC_ALL'] != 'C.UTF-8' or environment['TZ'] != 'UTC'
            or type(environment['SOURCE_DATE_EPOCH']) is not str or not re.fullmatch('[0-9]{1,12}', environment['SOURCE_DATE_EPOCH'])):
        raise ValueError('Native build environment must be explicit deterministic allowlist')
    _text(environment['PATH'], 'explicit native PATH')
    programs = {name: _program(record, inventories, inputs, 'native-tool-' + name) for name, record in value['tools'].items()}
    if sdk_kind and (programs != binding['tool_paths'] or runtime['sysroot_inventory'] != 'sdk'
            or runtime != binding['policy']['runtime'] or value['cpu'] != binding['policy']['cpu']
            or environment['SOURCE_DATE_EPOCH'] != binding['policy']['source_date_epoch']
            or compiler != {'family': 'gcc', 'frontend': 'gcc', 'version': binding['tool_paths']['c']['version'],
                            'triple': target['triple']}):
        raise ValueError('SDK-backed toolchain tools/compiler/runtime/CPU/environment differ from original admission')
    _version(programs['cmake']['version'], (3, 24, 0), 'CMake')
    primary = inventories['toolchain']
    for name in ('identity.json', 'native-toolchain.cmake'):
        if name not in primary['files']:
            raise ValueError('Toolchain inventory must retain identity.json and native-toolchain.cmake')
    if sdk_kind and primary['files']['native-toolchain.cmake'] != binding['toolchain_sha256']:
        raise ValueError('SDK-backed CMake toolchain differs from the exact admitted template and SDK values')
    identity_path = Path(primary['root']) / 'identity.json'
    if primary['files']['identity.json'] != identity['identity_sha256']:
        raise ValueError('Original toolchain identity bytes differ from identity_sha256')
    original = strict_json(inputs.bytes(identity_path), 'original toolchain identity')
    _schema(original, ('schema_version', 'kind', 'target', 'compiler', 'runtime', 'cpu'), 'foundation-native-toolchain-identity-v1')
    expected = {'schema_version': 1, 'kind': 'foundation-native-toolchain-identity-v1', 'target': target,
                'compiler': compiler, 'runtime': runtime, 'cpu': value['cpu']}
    if original != expected:
        raise ValueError('Original native toolchain identity differs from selected facts')
    result = dict(value)
    result['inventories'] = inventories
    result['tools'] = programs
    result['toolchain_file'] = str(Path(primary['root']) / 'native-toolchain.cmake')
    if sdk_kind:
        result['sdk_binding'] = binding
    if private_kind:
        policy_path = _absolute(repository_root) / PRIVATE_RUNTIME_POLICY
        try:
            policy_raw = _producer_bytes(inputs, policy_path,
                                         'native-producer-private-runtime-policy', _absolute(repository_root))
        except FileNotFoundError as error:
            raise MissingInputs([{'role': 'private-runtime-policy', 'path': str(policy_path),
                'reason': 'exact private runtime producer policy absent'}]) from error
        try:
            query_environment = native_sdk.private_runtime_query_environment(binding)
            result['private_runtime'] = native_sdk.validate_private_runtime_selection(
                value['private_runtime_selection'], base, inputs, binding=binding, policy_raw=policy_raw,
                expected_environment=query_environment)
        except native_sdk.MissingInputs as error:
            raise MissingInputs(error.missing) from error
    return result


def render_environment(toolchain, host_tools):
    programs = list(toolchain['tools'].values()) + list(host_tools['programs'].values())
    paths = sorted({str(Path(item['path']).parent) for item in programs})
    expected = ':'.join(paths)
    if toolchain['environment']['PATH'] != expected:
        raise ValueError('Native PATH must exactly name sorted admitted program directories')
    environment = dict(toolchain['environment'])
    for role, name in (('python', 'PYTHONPATH'), ('perl', 'PERL5LIB'), ('ruby', 'RUBYLIB')):
        facts = (host_tools['interpreter_runtimes'][role] if 'interpreter_runtimes' in host_tools
                 else host_tools['module_inventories'][role]['runtime'])
        environment[name] = ':'.join(facts['search_paths'])
    return environment


def inspect_static_archive(path, *, deadline=None):
    """Check actual ar/ELF object structure, without claiming a PIC link pass."""
    path = _ordinary(_absolute(path))
    before = _identity(path.lstat())
    if before[4] > MAX_FILE:
        raise ValueError('Native archive exceeds input byte bound')
    digest = hashlib.sha256()
    members = 0
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        if _identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Native archive changed before inspection')
        magic = stream.read(8)
        digest.update(magic)
        if magic != b'!<arch>\n':
            raise ValueError('Native dependency must be an ordinary ar, never thin/Wasm/bitcode')
        names = b''
        while stream.tell() < before[4]:
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError('Native archive inspection deadline expired')
            header = stream.read(60)
            digest.update(header)
            if len(header) != 60 or header[58:] != b'`\n':
                raise ValueError('Malformed native ar member header')
            try:
                size = int(header[48:58].decode('ascii').strip())
                name = header[:16].decode('ascii').strip()
            except (UnicodeError, ValueError) as error:
                raise ValueError('Malformed native ar scalar') from error
            if size < 0 or size > MAX_MEMBER or size > before[4] - stream.tell():
                raise ValueError('Native ar member size exceeds actual archive')
            body = stream.read(size)
            digest.update(body)
            if len(body) != size:
                raise ValueError('Truncated native ar member')
            if size % 2:
                padding = stream.read(1)
                digest.update(padding)
                if padding != b'\n':
                    raise ValueError('Invalid native ar padding')
            if name == '//':
                names = body
                continue
            if name in ('/', '/SYM64/'):
                continue
            if name.startswith('#1/'):
                try:
                    length = int(name[3:])
                except ValueError as error:
                    raise ValueError('Invalid BSD ar filename') from error
                if not 0 < length <= len(body):
                    raise ValueError('Invalid BSD ar filename length')
                body = body[length:]
            elif name.startswith('/'):
                try:
                    offset = int(name[1:])
                except ValueError as error:
                    raise ValueError('Invalid GNU ar filename') from error
                if not 0 <= offset < len(names) or b'/\n' not in names[offset:]:
                    raise ValueError('GNU ar filename offset is not retained')
            if (len(body) < 64 or body[:6] != b'\x7fELF\x02\x01' or body[6] != 1
                    or struct.unpack_from('<HHI', body, 16) != (1, 62, 1)):
                raise ValueError('Native archive member must be actual ELF64 little-endian x86_64 ET_REL')
            ehsize = struct.unpack_from('<H', body, 52)[0]
            shoff = struct.unpack_from('<Q', body, 40)[0]
            shentsize, shnum = struct.unpack_from('<HH', body, 58)
            if ehsize != 64 or (shnum and (shentsize != 64 or shoff < 64 or shoff + shnum * 64 > len(body))):
                raise ValueError('Malformed native ELF section table')
            for index in range(shnum):
                section = shoff + index * 64
                section_type = struct.unpack_from('<I', body, section + 4)[0]
                offset, length = struct.unpack_from('<QQ', body, section + 24)
                if section_type != 8 and (offset > len(body) or length > len(body) - offset):
                    raise ValueError('Native ELF section extends outside its member')
            members += 1
            if members > MAX_FILES:
                raise ValueError('Native archive member count exceeds bound')
        if stream.tell() != before[4] or _identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Native archive changed during inspection')
    if members == 0 or _identity(path.lstat()) != before:
        raise ValueError('Native archive has no actual native object members or changed')
    return {'format': 'elf64-x86_64-ar', 'members': members, 'sha256': digest.hexdigest(), 'bytes': before[4]}


def apply_unified_patch(originals, raw, preimages, postimages):
    """Apply the closed ordinary-text unified-diff vocabulary, with no fuzz."""
    if type(originals) is not dict or type(raw) is not bytes or len(raw) > MAX_DOCUMENT:
        raise ValueError('Invalid bounded exact patch input')
    if type(preimages) is not dict or not preimages or type(postimages) is not dict or set(preimages) != set(postimages):
        raise ValueError('Exact patch pre/post image sets must match')
    for name in preimages:
        _name(name)
        for image in (preimages[name], postimages[name]):
            if image is not None:
                pin(image, 'patch image')
        if preimages[name] is None and postimages[name] is None:
            raise ValueError('Patch cannot have two absent images')
        actual = originals.get(name)
        if (actual is None) != (preimages[name] is None) or actual is not None and sha256(actual) != preimages[name]:
            raise ValueError('Exact patch preimage mismatch: ' + name)
    lines = raw.splitlines(keepends=True)
    output = dict(originals)
    touched = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith((b'diff --git ', b'index ', b'new file mode 100644', b'deleted file mode 100644')) or line.strip() == b'':
            index += 1
            continue
        if not line.startswith(b'--- ') or index + 1 >= len(lines) or not lines[index + 1].startswith(b'+++ '):
            raise ValueError('Unsupported exact patch header/mode/rename/binary record')
        old, new = line[4:].rstrip(b'\r\n'), lines[index + 1][4:].rstrip(b'\r\n')
        try:
            old_name = None if old == b'/dev/null' else _name(old.removeprefix(b'a/').decode('utf-8'))
            new_name = None if new == b'/dev/null' else _name(new.removeprefix(b'b/').decode('utf-8'))
        except UnicodeError as error:
            raise ValueError('Invalid patch path Unicode') from error
        if (old_name is not None and not old.startswith(b'a/')) or (new_name is not None and not new.startswith(b'b/')):
            raise ValueError('Patch requires a/ and b/ paths')
        name = new_name or old_name
        if name is None or old_name is not None and new_name is not None and old_name != new_name or name in touched or name not in preimages:
            raise ValueError('Duplicate, renamed or undeclared exact patch path')
        if (old_name is None) != (preimages[name] is None) or (new_name is None) != (postimages[name] is None):
            raise ValueError('Patch add/delete headers disagree with image inventory')
        touched.add(name)
        source = originals.get(name, b'').splitlines(keepends=True)
        result, cursor = [], 0
        index += 2
        hunks = 0
        while index < len(lines) and lines[index].startswith(b'@@ '):
            match = re.fullmatch(rb'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\r\n]*\r?\n?', lines[index])
            if not match:
                raise ValueError('Invalid exact unified hunk')
            old_start, old_count, new_start, new_count = (int(child) if child is not None else 1 for child in match.groups())
            old_offset = old_start - 1 if old_count else old_start
            new_offset = new_start - 1 if new_count else new_start
            if old_offset < cursor or old_offset > len(source):
                raise ValueError('Patch hunk coordinate outside exact preimage')
            result.extend(source[cursor:old_offset])
            cursor = old_offset
            if len(result) != new_offset:
                raise ValueError('Patch new hunk coordinate mismatch')
            index += 1
            removed = added = 0
            while index < len(lines) and lines[index][:1] in (b' ', b'-', b'+') and not lines[index].startswith(b'--- '):
                operation, content = lines[index][:1], lines[index][1:]
                index += 1
                if index < len(lines) and lines[index].startswith(b'\\ No newline at end of file'):
                    content = content.rstrip(b'\n')
                    index += 1
                if operation in (b' ', b'-'):
                    if cursor >= len(source) or source[cursor] != content:
                        raise ValueError('Patch context differs; no fuzzy fallback')
                    cursor += 1
                    removed += 1
                if operation in (b' ', b'+'):
                    result.append(content)
                    added += 1
            if removed != old_count or added != new_count:
                raise ValueError('Patch exact hunk line counts mismatch')
            hunks += 1
        if hunks == 0:
            raise ValueError('Patch file has no exact hunks')
        result.extend(source[cursor:])
        body = b''.join(result)
        if postimages[name] is None:
            if body:
                raise ValueError('Deleted patch postimage must be empty')
            output.pop(name, None)
        else:
            if sha256(body) != postimages[name]:
                raise ValueError('Exact patch postimage mismatch: ' + name)
            output[name] = body
    if touched != set(preimages):
        raise ValueError('Patch touched-image inventory differs from actual diff')
    return output


def _archive_entries(path, archive_format):
    """Yield bounded raw members; no extraction and no broad link resolution."""
    before = _identity(_ordinary(path).lstat())
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as source:
        if _identity(os.fstat(source.fileno())) != before:
            raise ValueError('Source archive changed before bounded read')
        yield from _open_archive_entries(source, archive_format)
        if _identity(os.fstat(source.fileno())) != before or _identity(path.lstat()) != before:
            raise ValueError('Source archive changed during bounded read')


def _open_archive_entries(source, archive_format, *, maximum_members=MAX_MEMBERS, maximum_document=MAX_DOCUMENT):
    if archive_format == 'zip':
        # Bound the central-directory allocation before ZipFile loads it.
        source.seek(0, 2)
        size = source.tell()
        source.seek(max(0, size - 65557))
        tail = source.read(65557)
        offset = tail.rfind(b'PK\x05\x06')
        if offset < 0 or len(tail) - offset < 22:
            raise ValueError('Source ZIP lacks a bounded end-of-directory record')
        disk, central_disk, count_disk, count, central_bytes = struct.unpack_from('<HHHHI', tail, offset + 4)
        if disk or central_disk or count_disk != count or count == 65535 or count > maximum_members or central_bytes > maximum_document:
            raise ValueError('Source ZIP central directory exceeds ordinary non-ZIP64 bounds')
        source.seek(0)
        with zipfile.ZipFile(source) as archive:
            for item in archive.infolist():
                mode = item.external_attr >> 16
                kind = 'directory' if item.is_dir() else ('symlink' if stat.S_ISLNK(mode) else 'file')
                if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK):
                    kind = 'special'
                if kind == 'file' and item.flag_bits & 1:
                    raise ValueError('Encrypted source ZIP members are unsupported')
                with archive.open(item) as stream:
                    link = None
                    if kind == 'symlink':
                        if item.file_size > 4096:
                            raise ValueError('Source link target exceeds bound')
                        try:
                            link = stream.read(4097).decode('utf-8')
                        except UnicodeError as error:
                            raise ValueError('Invalid source ZIP link target') from error
                    yield item.filename, kind, mode, item.file_size, link, stream
    else:
        wanted = {'tar-gzip': 'r|gz', 'tar-xz': 'r|xz'}.get(archive_format)
        if wanted is None:
            raise ValueError('Unsupported ordinary source archive format')
        with tarfile.open(fileobj=source, mode=wanted) as archive:
            for item in archive:
                kind = ('directory' if item.isdir() else 'file' if item.isfile()
                        else 'symlink' if item.issym() else 'hardlink' if item.islnk() else 'special')
                stream = archive.extractfile(item) if kind == 'file' else None
                try:
                    yield item.name, kind, item.mode, item.size, item.linkname if kind in ('symlink', 'hardlink') else None, stream
                finally:
                    if stream is not None:
                        stream.close()


def _member_name(raw, prefix):
    if type(raw) is not str:
        raise ValueError('Invalid source archive member name')
    name = _name(raw.rstrip('/'))
    if name == prefix:
        return None
    if prefix:
        if not name.startswith(prefix + '/'):
            raise ValueError('Source archive member is outside exact strip_prefix')
        name = name[len(prefix) + 1:]
    return _name(name)


def _resolved_link(member, target, raw_kind, prefix):
    if type(target) is not str or not target or target.startswith('/') or '\\' in target or ':' in target:
        raise ValueError('Escaping/invalid source link target')
    if raw_kind == 'hardlink':
        return [_member_name(target, prefix)]
    # A symlink target is relative to the actual containing archive directory.
    options = []
    for start in (member.split('/')[:-1],):
        parts = list(start)
        for part in target.split('/'):
            if part in ('', '.'):
                continue
            if part == '..':
                if not parts:
                    parts = None
                    break
                parts.pop()
            else:
                parts.append(part)
        if parts:
            options.append(_name('/'.join(parts)))
    return options


_CHECKED_SOURCE_TOKEN = object()
_SOURCE_RECORD_ROOT = PurePosixPath('/__foundation_checked_supplier_records__')
_SOURCE_LIMITS = {'maximum_archive_bytes': MAX_FILE, 'maximum_expanded_bytes': MAX_BYTES,
    'maximum_members': MAX_MEMBERS, 'maximum_member_bytes': MAX_MEMBER,
    'maximum_patch_bytes': MAX_DOCUMENT}


def _source_limits(value):
    _fields(value, ('seconds', *_SOURCE_LIMITS), 'checked source bounds')
    seconds = value['seconds']
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 86400:
        raise ValueError('Finite positive checked source deadline required')
    result = {'seconds': seconds}
    for name, maximum in _SOURCE_LIMITS.items():
        manifest.integer(value[name], 'checked source ' + name, 1, maximum)
        result[name] = min(value[name], maximum)
    return result


def _historical_source_absolute(value):
    """Validate original POSIX identity text without host filesystem operations."""
    if (type(value) is not str or not value.startswith('/')
            or str(PurePosixPath(value)) != value or '..' in PurePosixPath(value).parts
            or any(child in value for child in (';', ':', '\n', '\r', '\x00'))):
        raise ValueError('Explicit normalized historical POSIX source path required')
    return PurePosixPath(value)


def _source_view(value):
    """Remove only the parser's virtual prefix; preserve historical raw records."""
    result = json.loads(json.dumps(value, allow_nan=False))
    for item in result['archives'].values():
        item['path'] = str(PurePosixPath(item['path']).relative_to(_SOURCE_RECORD_ROOT))
    for name in ('provenance', 'patches', 'notices'):
        for item in result[name]:
            item['path'] = str(PurePosixPath(item['path']).relative_to(_SOURCE_RECORD_ROOT))
    for item in result['_files'].values():
        item['archive_path'] = str(PurePosixPath(item['archive_path']).relative_to(_SOURCE_RECORD_ROOT))
    return result


class CheckedSourceProjection:
    """Synchronous source checks; a serialized dictionary is never authority."""
    __slots__ = ('_token', '_view', '_core', '_provenance', '_patch_facts', '_deadline', '_limits')

    def __new__(cls, *args, **kwargs):
        raise TypeError('CheckedSourceProjection is created only by the checked parser')

    def __setattr__(self, name, value):
        raise AttributeError('Checked source facts are immutable')

    def as_dict(self):
        if self._token is not _CHECKED_SOURCE_TOKEN:
            raise ValueError('Invalid checked source authority')
        if time.monotonic() >= self._deadline:
            raise ValueError('Checked supplier source deadline expired')
        result = json.loads(self._view)
        if time.monotonic() >= self._deadline:
            raise ValueError('Checked supplier source deadline expired')
        return result


def _checked_projection(core, provenance, patch_facts, deadline, limits):
    result = object.__new__(CheckedSourceProjection)
    object.__setattr__(result, '_token', _CHECKED_SOURCE_TOKEN)
    object.__setattr__(result, '_core', json.dumps(core, sort_keys=True, allow_nan=False))
    object.__setattr__(result, '_view', json.dumps(_source_view(core), sort_keys=True, allow_nan=False))
    object.__setattr__(result, '_provenance', tuple((role, tuple(sorted(item.items())))
        for role, item in sorted(provenance.items())))
    object.__setattr__(result, '_patch_facts', tuple((name, tuple(sorted(item.items())))
        for name, item in sorted(patch_facts.items())))
    object.__setattr__(result, '_deadline', deadline)
    object.__setattr__(result, '_limits', tuple(sorted(limits.items())))
    return result


class _PinnedSourceArchive:
    """Bind every parser byte to a bounded compressed-chunk snapshot."""
    CHUNK = 1024 * 1024

    def __init__(self, source, size, hashes, owner):
        self._source, self._size, self._hashes, self._owner = source, size, tuple(hashes), owner
        self._position, self._cached_offset, self._cached = 0, -1, b''
        self._read_bytes = size  # The one completed preliminary compressed hash.
        self._maximum_reads = 2 * size + 2 * MAX_DOCUMENT + 2 * self.CHUNK

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self._position

    def seek(self, offset, whence=0):
        self._owner.check_deadline()
        if type(offset) is not int or type(whence) is not int or whence not in (0, 1, 2):
            raise ValueError('Ordinary source archive seek required')
        position = offset + (0 if whence == 0 else self._position if whence == 1 else self._size)
        if not 0 <= position <= self._size:
            raise ValueError('Source archive seek exceeds captured extent')
        self._position = position
        return position

    def _chunk(self, offset):
        self._owner.check_deadline()
        if offset == self._cached_offset:
            return self._cached  # Immutable bytes already verified for this snapshot.
        self._source.seek(offset)
        wanted = min(self.CHUNK, self._size - offset)
        blocks, count = [], 0
        while count < wanted:
            self._owner.check_deadline()
            remaining = self._maximum_reads - self._read_bytes
            if remaining <= 0:
                raise ValueError('Source archive repeated-read budget exceeded')
            requested = min(wanted - count, remaining)
            block = self._source.read(requested)
            if type(block) is not bytes or not block or len(block) > requested:
                raise ValueError('Source archive changed or truncated after capture')
            self._read_bytes += len(block)
            if self._read_bytes > self._maximum_reads:
                raise ValueError('Source archive repeated-read budget exceeded')
            blocks.append(block); count += len(block)
        raw = b''.join(blocks)
        if hashlib.sha256(raw).digest() != self._hashes[offset // self.CHUNK]:
            raise ValueError('Source archive bytes changed between capture and member parsing')
        self._owner.check_deadline()
        self._cached_offset, self._cached = offset, raw
        return raw

    def read(self, size=-1):
        self._owner.check_deadline()
        if type(size) is not int:
            raise ValueError('Bounded source archive read required')
        remaining = self._size - self._position
        count = remaining if size < 0 else min(size, remaining)
        if count > MAX_DOCUMENT:
            raise ValueError('Single compressed source archive read exceeds bounded allocation')
        blocks = []
        while count:
            offset = self._position // self.CHUNK * self.CHUNK
            raw = self._chunk(offset)
            start = self._position - offset
            wanted = min(count, len(raw) - start)
            if wanted <= 0:
                raise ValueError('Source archive read made no progress')
            blocks.append(raw[start:start + wanted]); self._position += wanted; count -= wanted
        self._owner.check_deadline()
        return b''.join(blocks)


class _SourceRecordInputs:
    """Closed captured bytes and caller-owned streams; no path is opened."""
    def __init__(self, limits, *, deadline=None):
        self.source_limits = _source_limits(limits)
        now = time.monotonic()
        own = now + self.source_limits['seconds']
        self.deadline = own if deadline is None else min(deadline, own)
        self._records, self._raw, self._archives = {}, {}, {}
        self._capture_bytes = 0
        self.check_deadline()

    def check_deadline(self):
        if time.monotonic() >= self.deadline:
            raise ValueError('Checked supplier source deadline expired')

    def capture(self, item, path, *, archive_stream=None, original=False, maximum=MAX_DOCUMENT):
        self.check_deadline()
        names = ('path', 'sha256', 'bytes', 'mode') + (() if archive_stream is not None else ('raw',))
        _fields(item, names, 'captured source record')
        _name(item['path'])
        pin(item['sha256'], 'captured source record')
        manifest.integer(item['bytes'], 'captured source bytes', 1 if archive_stream is not None or original else 0,
            self.source_limits['maximum_archive_bytes'] if archive_stream is not None else maximum)
        if type(item['mode']) is not int or item['mode'] not in ((0o644,) if original else (0o644, 0o755)):
            raise ValueError('Captured source mode differs from ordinary record policy')
        key = str(path)
        record = {name: item[name] for name in ('sha256', 'bytes', 'mode')}
        if key in self._records and self._records[key] != record:
            raise ValueError('Conflicting captured source path aliases')
        if key not in self._records:
            if len(self._records) >= MAX_FILES or item['bytes'] > MAX_BYTES - self._capture_bytes:
                raise ValueError('Captured source record count/aggregate bytes exceed shared bounds')
            self._capture_bytes += item['bytes']
        if archive_stream is None:
            raw = item['raw']
            if type(raw) is not bytes or len(raw) != item['bytes'] or sha256(raw) != item['sha256']:
                raise ValueError('Captured source raw bytes/hash/length mismatch')
            if key in self._archives or key in self._raw and self._raw[key] != raw:
                raise ValueError('Conflicting captured metadata/archive roles')
            self._raw[key] = raw
        else:
            if key in self._raw or key in self._archives:
                raise ValueError('Duplicate captured source archive stream')
            # This is a synchronous caller-owned input. It is not retained or closed.
            try:
                archive_stream.seek(0)
                digest, count, hashes = hashlib.sha256(), 0, []
                while count < item['bytes']:
                    wanted = min(_PinnedSourceArchive.CHUNK, item['bytes'] - count)
                    pieces, chunk_bytes = [], 0
                    while chunk_bytes < wanted:
                        self.check_deadline()
                        block = archive_stream.read(wanted - chunk_bytes)
                        if type(block) is not bytes or not block or len(block) > wanted - chunk_bytes:
                            raise ValueError('Captured source stream truncated or violates bounded binary reads')
                        pieces.append(block); chunk_bytes += len(block)
                    raw = b''.join(pieces); count += len(raw); digest.update(raw)
                    hashes.append(hashlib.sha256(raw).digest())
                if archive_stream.read(1) != b'':
                    raise ValueError('Captured source stream exceeds declared archive size')
                if count != item['bytes'] or digest.hexdigest() != item['sha256']:
                    raise ValueError('Captured archive stream hash/length mismatch')
            except (AttributeError, OSError, TypeError) as error:
                raise ValueError('Ordinary bounded seekable binary archive stream required') from error
            self._archives[key] = _PinnedSourceArchive(archive_stream, item['bytes'], hashes, self)
        self._records[key] = record
        self.check_deadline()

    def file(self, path, digest, role, *, maximum=MAX_FILE):
        self.check_deadline()
        item = self._records.get(str(path))
        if item is None or item['sha256'] != digest or item['bytes'] > maximum:
            raise ValueError('Source parser requested uncaptured or contradictory bytes: ' + role)
        return dict(item, path=str(path))

    def bytes(self, path):
        self.check_deadline()
        try:
            return self._raw[str(path)]
        except KeyError as error:
            raise ValueError('Source parser requested uncaptured metadata bytes') from error

    def source_path(self, path):
        return PurePosixPath(path)

    def archive_entries(self, path, archive_format):
        self.check_deadline()
        try:
            source = self._archives[str(path)]
            source.seek(0)
        except (KeyError, AttributeError, OSError) as error:
            raise ValueError('Checked source parser lacks its captured archive stream') from error
        yield from _open_archive_entries(source, archive_format,
            maximum_members=self.source_limits['maximum_members'], maximum_document=MAX_DOCUMENT)
        self.check_deadline()


def _captured_source_records(value, records, streams, limits):
    _fields(records, ('archives', 'provenance', 'patches', 'notices'), 'captured supplier sources')
    if (type(value) is not dict or type(value.get('archives')) is not dict
            or not 2 <= len(value['archives']) <= 16):
        raise ValueError('Explicit source projection archives required')
    if (type(streams) is not dict or type(records['archives']) is not dict
            or set(streams) != set(value['archives']) or set(records['archives']) != set(streams)):
        raise ValueError('Captured archive stream/record keys must exactly match projection')
    inputs = _SourceRecordInputs(limits)
    for name, item in value['archives'].items():
        record = records['archives'][name]
        if type(item) is not dict or type(record) is not dict or any(record.get(field) != item.get(field) for field in ('path', 'sha256', 'bytes')):
            raise ValueError('Captured archive references differ from source projection')
        inputs.capture(record, _SOURCE_RECORD_ROOT / _name(item['path']), archive_stream=streams[name])
    provenance = value.get('provenance')
    if type(provenance) is not list or type(records['provenance']) is not dict:
        raise ValueError('Captured provenance role table required')
    roles = [item.get('role') for item in provenance if type(item) is dict]
    if (len(roles) != len(provenance) or roles != sorted(set(roles))
            or set(roles) != set(records['provenance'])):
        raise ValueError('Captured provenance roles must match exact ordered projection')
    for item in provenance:
        record = records['provenance'][item['role']]
        if type(record) is not dict or any(record.get(field) != item.get(field) for field in ('path', 'sha256', 'bytes')):
            raise ValueError('Captured provenance reference differs from source projection')
        inputs.capture(record, _SOURCE_RECORD_ROOT / _name(item['path']))
    for name in ('patches', 'notices'):
        expected, actual = value.get(name), records[name]
        if type(expected) is not list or type(actual) is not list or len(expected) != len(actual):
            raise ValueError('Captured source ' + name + ' order/count mismatch')
        for ref, record in zip(expected, actual):
            if (type(ref) is not dict or type(record) is not dict
                    or any(record.get(field) != ref.get(field) for field in ('path', 'sha256'))):
                raise ValueError('Captured source ' + name + ' reference/order mismatch')
            inputs.capture(record, _SOURCE_RECORD_ROOT / _name(ref['path']), maximum=(
                inputs.source_limits['maximum_patch_bytes'] if name == 'patches' else MAX_DOCUMENT))
    return inputs


def parse_source_projection_records(value, captured_records, archive_streams, limits):
    _schema(value, ('schema_version', 'kind', 'suppliers', 'archives', 'projection', 'patches', 'notices', 'provenance'),
        'foundation-native-engine-prototype-sources-v1')
    inputs = _captured_source_records(value, captured_records, archive_streams, limits)
    # One shared semantic implementation, including actual archive member derivation.
    core = _parse_source_projection_core(value, _SOURCE_RECORD_ROOT, inputs,
        archive_entries=inputs.archive_entries, source_path=PurePosixPath)
    inputs.check_deadline()
    checked = _checked_projection(core, captured_records['provenance'],
        {item['path']: inputs._records[item['path']] for item in core['patches']},
        inputs.deadline, inputs.source_limits)
    inputs.check_deadline()
    return checked


def validate_source_provenance_records(checked_projection, provenance_records, original_proof_records):
    if (type(checked_projection) is not CheckedSourceProjection
            or getattr(checked_projection, '_token', None) is not _CHECKED_SOURCE_TOKEN):
        raise ValueError('Actual shared checked source projection required')
    checked = checked_projection
    if (type(provenance_records) is not dict or any(type(item) is not dict for item in provenance_records.values())
            or tuple((role, tuple(sorted(item.items())))
            for role, item in sorted(provenance_records.items())) != checked._provenance):
        raise ValueError('Original provenance bytes differ from checked source capture')
    limits = dict(checked._limits)
    inputs = _SourceRecordInputs(limits, deadline=checked._deadline)
    core = json.loads(checked._core)
    for item in core['provenance']:
        inputs.capture(provenance_records[item['role']], PurePosixPath(item['path']))
    body_record = provenance_records['engine-body-verification']
    body = strict_json(body_record['raw'], 'original retained source body')
    retained = type(body) is dict and body.get('kind') == 'foundation-native-engine-retained-body-evidence-v1'
    names = ('recipe', 'sources', 'archive_receipt', 'member_manifest', 'source_scope',
        'supplier_patch_images', 'generator')
    if type(original_proof_records) is not dict or set(original_proof_records) != (set(names) if retained else set()):
        raise ValueError('Exact original seven-role source proof table required')
    if retained:
        _fields(body['original_proof'], names, 'retained original source proof')
        base = (_SOURCE_RECORD_ROOT / _name(body_record['path'])).parent
        for name in names:
            ref, record = body['original_proof'][name], original_proof_records[name]
            if (type(ref) is not dict or type(record) is not dict
                    or any(record.get(field) != ref.get(field) for field in ('path', 'sha256', 'bytes'))):
                raise ValueError('Original proof reference spelling/hash/bytes differs from body')
            inputs.capture(record, base / _name(ref['path']), original=True)
    # Patch metadata was already captured by the parser; retain just its exact count.
    for item in core['patches']:
        name = str(PurePosixPath(item['path']))
        record = {key: dict(item) for key, item in checked._patch_facts}.get(name)
        if record is None:
            raise ValueError('Checked source patch facts missing')
        inputs._records[name] = dict(record)
    result = _validate_source_provenance_core(core, inputs)
    inputs.check_deadline()
    if 'original_proof' in result:
        for ref in result['original_proof'].values():
            ref['path'] = str(PurePosixPath(ref['path']).relative_to(_SOURCE_RECORD_ROOT))
    return result


def parse_source_projection(value, base, inputs, target):
    validate_target(target)
    return parse_supplier_source_projection(value, base, inputs)


def parse_supplier_source_projection(value, base, inputs):
    """Qualified POSIX capture; the portable semantic core never opens paths."""
    base = _absolute(base)
    inputs.check_deadline()
    core = _parse_source_projection_core(value, base, inputs)
    virtual = json.loads(json.dumps(core, allow_nan=False))
    def retarget(text):
        return str(_SOURCE_RECORD_ROOT / Path(text).relative_to(base).as_posix())
    for item in virtual['archives'].values():
        item['path'] = retarget(item['path'])
    for name in ('provenance', 'patches', 'notices'):
        for item in virtual[name]:
            item['path'] = retarget(item['path'])
    for item in virtual['_files'].values():
        item['archive_path'] = retarget(item['archive_path'])
    provenance = {}
    for ref in value['provenance']:
        path = base / _name(ref['path'])
        record = inputs._records[str(path)]
        provenance[ref['role']] = {'path': ref['path'], 'sha256': ref['sha256'],
            'bytes': ref['bytes'], 'mode': record['mode'], 'raw': inputs.bytes(path)}
    patch_facts = {retarget(item['path']): {key: inputs._records[item['path']][key]
        for key in ('sha256', 'bytes', 'mode')} for item in core['patches']}
    deadline = inputs.deadline
    remaining = 86400 if deadline is None else min(86400, deadline - time.monotonic())
    limits = _source_limits(dict(_SOURCE_LIMITS, seconds=remaining))
    checked = _checked_projection(virtual, provenance, patch_facts,
        time.monotonic() + remaining if deadline is None else deadline, limits)
    if time.monotonic() >= checked._deadline:
        raise ValueError('Checked supplier source deadline expired')
    cache = getattr(inputs, '_checked_source_projections', None)
    if cache is None:
        cache = {}
        inputs._checked_source_projections = cache
    cache[id(core)] = (core, sha256(encoded(core)), checked)
    inputs.check_deadline()
    return core


def validate_source_provenance(projection, inputs):
    saved = getattr(inputs, '_checked_source_projections', {}).get(id(projection))
    if (saved is None or saved[0] is not projection or saved[1] != sha256(encoded(projection))
            or type(saved[2]) is not CheckedSourceProjection
            or saved[2]._token is not _CHECKED_SOURCE_TOKEN):
        raise ValueError('Source provenance requires the capture owner\'s unchanged checked projection')
    inputs.check_deadline()
    result = _validate_source_provenance_core(projection, inputs)
    inputs.check_deadline()
    return result


def _parse_source_projection_core(value, base, inputs, *, archive_entries=_archive_entries, source_path=Path):
    source_limits = getattr(inputs, 'source_limits', _SOURCE_LIMITS)
    MAX_FILE = source_limits['maximum_archive_bytes']
    MAX_BYTES = source_limits['maximum_expanded_bytes']
    MAX_MEMBERS = source_limits['maximum_members']
    MAX_MEMBER = source_limits['maximum_member_bytes']
    _schema(value, ('schema_version', 'kind', 'suppliers', 'archives', 'projection', 'patches', 'notices', 'provenance'),
            'foundation-native-engine-prototype-sources-v1')
    provenance = value['provenance']
    if type(provenance) is not list or not len(SOURCE_PROVENANCE_ROLES) <= len(provenance) <= 8:
        raise ValueError('Explicit original source provenance role records required')
    normalized_provenance, roles = [], []
    for item in provenance:
        _fields(item, ('role', 'path', 'sha256', 'bytes'), 'source provenance reference')
        role = item['role']
        if type(role) is not str or role not in SOURCE_PROVENANCE_ROLES | SOURCE_PROVENANCE_OPTIONAL:
            raise ValueError('Unknown source provenance role')
        roles.append(role)
        manifest.integer(item['bytes'], 'source provenance bytes', 1, MAX_DOCUMENT)
        path = source_path(base) / _name(item['path'])
        record = inputs.file(path, pin(item['sha256'], role), 'supplier-provenance-' + role, maximum=MAX_DOCUMENT)
        if record['bytes'] != item['bytes']:
            raise ValueError('Source provenance differs from explicit original byte count')
        normalized_provenance.append(dict(item, path=str(path)))
    if roles != sorted(set(roles)) or not SOURCE_PROVENANCE_ROLES <= set(roles):
        raise ValueError('Source provenance roles must be sorted, unique and complete')
    _fields(value['suppliers'], ('wrapper', 'engine'), 'complete source suppliers')
    expected = {'wrapper': '68c618544e1f8af18ebce346281a6a49766aa194',
                'engine': 'aec9d2ad958e716ab4bca4bf03007e6edac7323f'}
    archives = value['archives']
    if type(archives) is not dict or not 2 <= len(archives) <= 16:
        raise ValueError('Both complete ordinary supplier archives are required')
    for supplier, item in value['suppliers'].items():
        _fields(item, ('repository', 'commit', 'archive'), 'source supplier')
        if not _text(item['repository'], 'supplier repository').startswith('https://') or item['commit'] != expected[supplier] or item['archive'] not in archives:
            raise ValueError('Pinned complete supplier archive/commit mismatch')
    if len({item['archive'] for item in value['suppliers'].values()}) != 2:
        raise ValueError('Wrapper and engine need distinct supplier archives')
    projection = _fields(value['projection'], ('files', 'directories', 'exclusions', 'normalizations'), 'complete source projection')
    files = projection['files']
    if type(files) is not dict or not files or len(files) > MAX_MEMBERS:
        raise ValueError('Complete bounded source projection required')
    _names(projection['directories'], 'source projection directories')
    for key in ('exclusions', 'normalizations'):
        if type(projection[key]) is not dict or set(projection[key]) != set(archives):
            raise ValueError('Every archive needs explicit projection ' + key)
    registry = PathInventory()
    selected = {}
    for destination, item in sorted(files.items()):
        registry.add(_name(destination), False)
        _fields(item, ('archive', 'member', 'sha256', 'bytes', 'mode'), 'projected source file')
        if not destination.startswith(('source/wrapper/', 'source/engine/')):
            raise ValueError('Source projection destination must be a declared supplier root')
        supplier = destination.split('/')[1]
        if item['archive'] != value['suppliers'][supplier]['archive']:
            raise ValueError('Source projection crosses its declared supplier archive')
        _name(item['member'])
        if destination != 'source/' + supplier + '/' + item['member']:
            raise ValueError('Supplier projection must preserve exact member paths after strip_prefix')
        pin(item['sha256'], destination)
        manifest.integer(item['bytes'], 'projected source bytes', 0, MAX_MEMBER)
        if type(item['mode']) is not int or item['mode'] not in (0o644, 0o755):
            raise ValueError('Projected source mode must be 0644/0755')
        key = (item['archive'], item['member'])
        if key in selected:
            raise ValueError('Source archive member has duplicate projection owners')
        selected[key] = destination
    parents = set()
    for name in files:
        parents.update(parent.as_posix() for parent in source_path(name).parents if parent.as_posix() != '.')
    if sorted(parents) != projection['directories']:
        raise ValueError('Source projection directories must exactly cover all parents')
    required = ('source/wrapper/README.md', 'source/wrapper/src/embedder/main.cpp',
        'source/engine/CMakeLists.txt', 'source/engine/Source/cmake/WebKitCommon.cmake')
    if not set(required) <= set(files) or not any(name.startswith('source/engine/Tools/') for name in files):
        raise ValueError('Complete supplier Source/Tools/root generator inputs are required; overlays are insufficient')
    normalized_archives, actual, actual_links = {}, {}, {}
    total = entries = 0
    for key, item in sorted(archives.items()):
        if '/' in _name(key):
            raise ValueError('Source archive logical name must be one component')
        _fields(item, ('path', 'sha256', 'bytes', 'format', 'strip_prefix'), 'source archive')
        prefix = item['strip_prefix']
        if prefix:
            _name(prefix)
        elif type(prefix) is not str:
            raise ValueError('Explicit source strip_prefix required')
        manifest.integer(item['bytes'], 'source archive byte count', 1, MAX_FILE)
        path = source_path(base) / _name(item['path'])
        record = inputs.file(path, pin(item['sha256'], key), 'source-archive-' + key)
        if record['bytes'] != item['bytes']:
            raise ValueError('Source archive differs from declared byte count')
        exclusions = _names(projection['exclusions'][key], 'source exclusions')
        normalizations = projection['normalizations'][key]
        if type(normalizations) is not dict or len(normalizations) > MAX_FILES:
            raise ValueError('Explicit bounded direct-link normalizations required')
        for member, other in normalizations.items():
            _name(member)
            _name(other)
        # Generator/core source trees may not be silently excluded wholesale.
        if key == value['suppliers']['engine']['archive'] and any(
                name in ('Source', 'Tools', 'CMakeLists.txt') or name.startswith(('Source/', 'Tools/')) for name in exclusions):
            raise ValueError('Engine Source/Tools generator closure cannot be excluded')
        member_registry = PathInventory()
        seen, links, literals, used_exclusions = {}, {}, {}, set()
        for raw_name, kind, mode, size, link, stream in archive_entries(path, item['format']):
            inputs.check_deadline()
            entries += 1
            if entries > MAX_MEMBERS or type(size) is not int or not 0 <= size <= MAX_MEMBER or size > MAX_BYTES - total:
                raise ValueError('Expanded source archive exceeds member/byte bound')
            total += size
            name = _member_name(raw_name, prefix)
            if name is None:
                if kind != 'directory':
                    raise ValueError('strip_prefix root must be a directory')
                continue
            member_registry.add(name, kind == 'directory')
            if mode & 0o7000 or kind == 'special':
                raise ValueError('Privileged/special source archive member')
            if kind == 'directory':
                continue
            excluded = [root for root in exclusions if name == root or name.startswith(root + '/')]
            used_exclusions.update(excluded)
            if excluded and (key, name) in selected:
                raise ValueError('Source member is both projected and excluded')
            if not excluded and (key, name) not in selected:
                raise ValueError('Undeclared source archive member: ' + name)
            normalized_mode = 0o755 if mode & 0o111 else 0o644
            if kind in ('symlink', 'hardlink'):
                if name not in normalizations or normalizations[name] not in _resolved_link(name, link, kind, prefix):
                    raise ValueError('Source link lacks exact direct ordinary-file normalization: ' + name)
                links[name] = normalizations[name]
                literals[name] = link
                seen[name] = {'link': normalizations[name], 'mode': normalized_mode}
                continue
            digest = hashlib.sha256()
            count = 0
            while True:
                inputs.check_deadline()
                block = stream.read(min(1024 * 1024, size - count + 1))
                if not block:
                    break
                count += len(block)
                if count > size:
                    raise ValueError('Expanded source member exceeds declared bytes')
                digest.update(block)
            if count != size:
                raise ValueError('Truncated source archive member')
            seen[name] = {'sha256': digest.hexdigest(), 'bytes': count, 'mode': normalized_mode}
        if set(normalizations) != set(links) or used_exclusions != set(exclusions):
            raise ValueError('Unused or missing source normalization/exclusion')
        for name, other in links.items():
            if other not in seen or 'link' in seen[other]:
                raise ValueError('Source normalization target must be an exact same-archive regular file')
            seen[name] = dict(seen[other])
        for (archive, name), destination in selected.items():
            if archive != key:
                continue
            expected_item = files[destination]
            facts = seen.get(name)
            if facts != {field: expected_item[field] for field in ('sha256', 'bytes', 'mode')}:
                raise ValueError('Source projection hash/bytes/mode differs from actual archive: ' + destination)
            actual[destination] = dict(expected_item, archive_path=str(path),
                regular_member=links.get(name, name), format=item['format'], strip_prefix=prefix)
        normalized_archives[key] = dict(item, path=str(path))
        actual_links[key] = literals
    if set(actual) != set(files):
        raise ValueError('Complete source projection references missing archive members')
    normalized_bytes = 0
    for item in actual.values():
        inputs.check_deadline()
        if item['bytes'] > MAX_BYTES - normalized_bytes:
            raise ValueError('Normalized source projection exceeds expanded logical byte bound')
        normalized_bytes += item['bytes']
    patches = value['patches']
    if type(patches) is not list or len(patches) > 256:
        raise ValueError('Explicit ordered native source patches required')
    normalized_patches, seen = [], set()
    for item in patches:
        _fields(item, ('path', 'sha256', 'tree', 'preimages', 'postimages'), 'native exact patch')
        name = _name(item['path'])
        if name in seen or item['tree'] not in ('wrapper', 'engine'):
            raise ValueError('Duplicate/invalid native source patch')
        seen.add(name)
        path = source_path(base) / name
        inputs.file(path, pin(item['sha256'], name), 'source-patch', maximum=MAX_DOCUMENT)
        # The exact parser validates all image keys now and executes hunks in assembly.
        if type(item['preimages']) is not dict or not item['preimages'] or type(item['postimages']) is not dict or set(item['preimages']) != set(item['postimages']):
            raise ValueError('Native patch needs exact matching before/after inventories')
        for source, before in item['preimages'].items():
            _name(source)
            after = item['postimages'][source]
            if before is None and after is None:
                raise ValueError('Native patch has two absent images')
            for image in (before, after):
                if image is not None:
                    pin(image, 'patch image')
        normalized_patches.append(dict(item, path=str(path)))
    if type(value['notices']) is not list or not value['notices']:
        raise ValueError('Supplier source notices must be explicitly retained')
    notices = []
    for item in value['notices']:
        _fields(item, ('path', 'sha256'), 'independent file reference')
        path, digest = source_path(base) / _name(item['path']), pin(item['sha256'], item['path'])
        inputs.file(path, digest, 'supplier-notice', maximum=MAX_DOCUMENT)
        notices.append({'path': str(path), 'sha256': digest})
    return dict(value, archives=normalized_archives, patches=normalized_patches, notices=notices,
        provenance=normalized_provenance, _files=actual, _links=actual_links)


def _git_tree(raw, *, top=False, deadline=None):
    if not raw or not raw.endswith(b'\0') or len(raw) > MAX_DOCUMENT:
        raise ValueError('Original Git tree must be bounded complete NUL records')
    result = {}
    registry = PathInventory()
    for record in raw[:-1].split(b'\0'):
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError('Native source provenance parsing deadline expired')
        try:
            header, name_raw = record.split(b'\t', 1)
            mode, kind, oid = header.decode('ascii').split(' ')
            name = _name(name_raw.decode('utf-8'))
        except (ValueError, UnicodeError) as error:
            raise ValueError('Malformed original Git tree record') from error
        if not re.fullmatch('[0-9a-f]{40}', oid) or oid == '0' * 40:
            raise ValueError('Original Git tree requires full nonzero blob/tree OIDs')
        if mode in ('100644', '100755', '120000') and kind == 'blob':
            directory = False
        elif top and mode == '040000' and kind == 'tree':
            directory = True
        else:
            raise ValueError('Unsupported original Git tree mode/submodule/type')
        if top and '/' in name:
            raise ValueError('Top Git tree record must have one path component')
        registry.add(name, directory)
        if name in result or len(result) >= MAX_MEMBERS:
            raise ValueError('Duplicate/overbound original Git tree')
        result[name] = {'mode': mode, 'type': kind, 'oid': oid}
    return result


def _validate_source_provenance_core(projection, inputs):
    """Join original retained records; never infer a new Git/body/build pass."""
    records = {item['role']: item for item in projection['provenance']}
    if not SOURCE_PROVENANCE_ROLES <= set(records) or len(records) != len(projection['provenance']):
        raise ValueError('Original source provenance roles incomplete/duplicated')
    def raw(role):
        return inputs.bytes(getattr(inputs, 'source_path', Path)(records[role]['path']))
    def document(role):
        return strict_json(raw(role), role)
    controls, receipt = document('git-controls'), document('git-tree-receipt')
    if type(controls) is not dict or type(receipt) is not dict:
        raise ValueError('Original Git control/metadata receipt must be JSON records')
    if type(receipt.get('root')) is not str:
        raise ValueError('Original Git metadata needs its explicit original source root')
    _historical_source_absolute(receipt['root'])
    if (type(receipt.get('schema_version')) is not int or receipt['schema_version'] != 1
            or receipt.get('scope') != 'offline-original-Git-tree-metadata-only' or receipt.get('commit') != ENGINE_COMMIT
            or controls.get('commit') != ENGINE_COMMIT or controls.get('source') != receipt.get('root')
            or receipt.get('passed') is not True or receipt.get('native_build') is not False
            or receipt.get('source_archive_created') is not False or receipt.get('regular_body_hashes_verified') is not False):
        raise ValueError('Original Git metadata receipt is not the retained metadata-only operation')
    for name, role in (('top_sha256', 'git-top-tree'), ('selected_sha256', 'git-selected-tree')):
        if receipt.get(name) != records[role]['sha256']:
            raise ValueError('Original Git metadata raw-tree digest mismatch')
    if receipt.get('git_captured_output_bytes') != records['git-top-tree']['bytes'] + records['git-selected-tree']['bytes']:
        raise ValueError('Original Git metadata total raw-tree bytes mismatch')
    top = _git_tree(raw('git-top-tree'), top=True, deadline=inputs.deadline)
    selected = _git_tree(raw('git-selected-tree'), deadline=inputs.deadline)
    root_blobs = {name: item for name, item in top.items() if item['type'] == 'blob'}
    recorded_roots = receipt.get('root_blobs')
    if receipt.get('top_tree') != top or type(recorded_roots) is not dict or set(recorded_roots) != set(root_blobs):
        raise ValueError('Original Git top/root-blob inventory mismatch')
    if receipt.get('original_entries') != len(selected) or receipt.get('source_tools_original') != len(selected) - len(root_blobs):
        raise ValueError('Original Git selected member counts mismatch')
    for name, item in root_blobs.items():
        if selected.get(name) != item or type(recorded_roots[name]) is not dict or recorded_roots[name].get('original') != item:
            raise ValueError('Original root Git blob was dropped or replaced')
    if any(not name.startswith(('Source/', 'Tools/')) and name not in root_blobs for name in selected):
        raise ValueError('Original selected source tree includes an undeclared root')
    inventory = document('engine-member-inventory')
    _schema(inventory, ('schema_version', 'kind', 'commit', 'archive_sha256', 'files', 'normalizations'),
            'foundation-native-engine-clean-members-v1')
    body = document('engine-body-verification')
    retained = type(body) is dict and body.get('kind') == 'foundation-native-engine-retained-body-evidence-v1'
    _schema(body, ('schema_version', 'kind', 'scope', 'commit', 'baseline', 'archive_sha256',
        'member_inventory_sha256', 'git_inputs', 'supplier_patch_sha256', 'normalizations') +
        (('original_proof',) if retained else ('regular_blobs_verified', 'link_blobs_verified', 'source_bytes')) +
        ('production_eligible', 'native_build'), 'foundation-native-engine-retained-body-evidence-v1'
        if retained else 'foundation-native-engine-clean-source-body-v1')
    engine_key = projection['suppliers']['engine']['archive']
    archive = projection['archives'][engine_key]
    if (inventory['commit'] != ENGINE_COMMIT or body['commit'] != ENGINE_COMMIT
            or body['scope'] != ('retained-original-git-body-proof-and-source-archive-consistency-only'
                if retained else 'original-git-blob-and-clean-archive-source-consistency-only')
            or body['baseline'] != 'clean-original-commit' or body['archive_sha256'] != archive['sha256']
            or inventory['archive_sha256'] != archive['sha256']
            or body['member_inventory_sha256'] != records['engine-member-inventory']['sha256']
            or body['supplier_patch_sha256'] != SUPPLIER_PATCH or body['production_eligible'] is not False or body['native_build'] is not False):
        raise ValueError('Original clean body receipt does not bind the admitted archive/member inventory/profile')
    expected_git = {role: records[role]['sha256'] for role in ('git-controls', 'git-top-tree', 'git-selected-tree', 'git-tree-receipt')}
    if body['git_inputs'] != expected_git:
        raise ValueError('Original clean body receipt binds different Git metadata bytes')
    files, normalizations = inventory['files'], inventory['normalizations']
    if type(files) is not dict or set(files) != set(selected) or type(normalizations) is not dict or len(normalizations) != 8:
        raise ValueError('Clean source inventory must exactly cover original Git members and eight links')
    if body['normalizations'] != normalizations or set(normalizations) != {name for name, item in selected.items() if item['mode'] == '120000'}:
        raise ValueError('Clean source normalization inventory differs from original link members')
    for normalization in normalizations.values():
        _fields(normalization, ('literal', 'git_blob_sha1', 'target', 'target_git_blob_sha1', 'target_sha256'), 'original source normalization')
    if projection['projection']['normalizations'][engine_key] != {name: item.get('target') for name, item in normalizations.items()}:
        raise ValueError('Clean source projection normalizes different original links')
    actual_links = projection['_links'][engine_key]
    if set(actual_links) != set(normalizations):
        raise ValueError('Clean source archive does not preserve exactly the eight original link members')
    metadata_links = receipt.get('links_before_normalization')
    if type(metadata_links) is not dict or set(metadata_links) != set(normalizations):
        raise ValueError('Original metadata link set differs from clean source inventory')
    projected_engine = {name[len('source/engine/'):]: item for name, item in projection['_files'].items() if name.startswith('source/engine/')}
    if set(projected_engine) != set(files):
        raise ValueError('Clean engine projection omits original members or adds patched bodies')
    total = 0
    for name, item in files.items():
        inputs.check_deadline()
        _fields(item, ('sha256', 'bytes', 'mode', 'git_blob_sha1'), 'clean source member')
        pin(item['sha256'], name)
        manifest.integer(item['bytes'], 'clean normalized source bytes', 0, MAX_MEMBER)
        if type(item['mode']) is not int or item['mode'] not in (0o644, 0o755) or item['git_blob_sha1'] != selected[name]['oid']:
            raise ValueError('Clean member mode/original Git OID mismatch')
        if any(projected_engine[name][key] != item[key] for key in ('sha256', 'bytes', 'mode')):
            raise ValueError('Actual archive/projection bytes differ from clean member inventory')
        total += item['bytes']
        if name not in normalizations:
            if item['mode'] != (0o755 if selected[name]['mode'] == '100755' else 0o644):
                raise ValueError('Original Git executable semantics changed in clean archive')
            continue
        normalization = _fields(normalizations[name], ('literal', 'git_blob_sha1', 'target', 'target_git_blob_sha1', 'target_sha256'), 'original source normalization')
        metadata = metadata_links[name]
        if type(metadata) is not dict:
            raise ValueError('Original metadata link facts invalid')
        target = _name(normalization['target'])
        literal = _text(normalization['literal'], 'original link literal')
        literal_oid = hashlib.sha1(b'blob ' + str(len(literal.encode('utf-8'))).encode('ascii') + b'\0' + literal.encode('utf-8')).hexdigest()
        if (target not in files or target in normalizations or selected[target]['mode'] not in ('100644', '100755')
                or normalization['git_blob_sha1'] != selected[name]['oid'] or literal_oid != selected[name]['oid']
                or actual_links[name] != literal or normalization['target_git_blob_sha1'] != selected[target]['oid']
                or normalization['target_sha256'] != files[target]['sha256']
                or any(item[key] != files[target][key] for key in ('sha256', 'bytes', 'mode'))
                or metadata.get('literal') != literal or metadata.get('oid') != literal_oid
                or metadata.get('mode') != '120000' or metadata.get('type') != 'blob' or metadata.get('literal_git_blob_verified') is not True):
            raise ValueError('Original literal-link/OID/direct-regular-body normalization join mismatch')
    if not retained:
        for field, expected in (('regular_blobs_verified', len(files) - 8), ('link_blobs_verified', 8), ('source_bytes', total)):
            if type(body[field]) is not int or body[field] != expected:
                raise ValueError('Original clean body verification count/bytes mismatch')
    result = {'scope': 'retained-source-provenance-record-consistency-only', 'commit': ENGINE_COMMIT,
        'archive_sha256': archive['sha256'], 'member_inventory_sha256': records['engine-member-inventory']['sha256'],
        'regular_blobs': len(files) - 8, 'normalized_links': 8, 'source_bytes': total,
        'production_eligible': False, 'native_build': False}
    if retained:
        proof = _retained_source_proof(body, projection, inputs, files, normalizations, selected,
            archive, getattr(inputs, 'source_path', Path)(records['engine-body-verification']['path']).parent)
        result.update(evidence_kind=body['kind'], original_proof=proof, source_body_execution=False)
    return result


def _retained_source_proof(body, projection, inputs, files, normalizations, selected, archive, base):
    """Join historical R/S and original receipts without following old commands."""
    names = ('recipe', 'sources', 'archive_receipt', 'member_manifest', 'source_scope',
             'supplier_patch_images', 'generator')
    _fields(body['original_proof'], names, 'retained original source proof')
    proof, raw = {}, {}
    for role in names:
        inputs.check_deadline()
        ref = body['original_proof'][role]
        _fields(ref, ('path', 'sha256', 'bytes'), 'original proof reference')
        manifest.integer(ref['bytes'], 'original proof bytes', 1, MAX_DOCUMENT)
        path = base / _name(ref['path'])
        record = inputs.file(path, pin(ref['sha256'], role), 'supplier-provenance-original-' + role, maximum=MAX_DOCUMENT)
        if record['bytes'] != ref['bytes'] or record['mode'] != 0o644:
            raise ValueError('Original proof differs from declared bytes/0644 mode')
        raw[role] = inputs.bytes(path)
        proof[role] = {'path': str(path), 'sha256': ref['sha256'], 'bytes': ref['bytes']}
    docs = {name: strict_json(raw[name], 'original ' + name) for name in names if name != 'generator'}
    recipe, sources = docs['recipe'], docs['sources']
    manifest.recipe_contract(recipe)
    manifest.source_contract(sources, recipe, proof['recipe']['sha256'])
    logical = {'archive_receipt': ('archive-receipt.json', 'config'),
        'member_manifest': ('pristine-member-manifest.json', 'config'),
        'source_scope': ('source-scope.json', 'config'),
        'supplier_patch_images': ('supplier-patch-images.json', 'config'),
        'generator': ('create_archive.py', 'helper')}
    for role, (leaf, expected_role) in logical.items():
        name = 'provenance/source-archive/' + leaf
        if recipe['inputs'].get(name) != {'sha256': proof[role]['sha256'], 'mode': 0o644, 'role': expected_role}:
            raise ValueError('Original proof bytes/role/mode differ from original R/S input: ' + role)
    supplier = recipe['suppliers']['engine']
    archive_input = recipe['inputs'][supplier['archive']]
    if supplier['commit'] != ENGINE_COMMIT or archive_input != {'sha256': archive['sha256'], 'mode': 0o644, 'role': 'source'}:
        raise ValueError('Original R/S engine archive differs from admitted clean original archive')
    members = docs['member_manifest']
    _fields(members, ('schema_version', 'commit', 'scope', 'entries', 'implicit_directories',
        'safe_scoped_extractor_directory_mode'), 'original pristine member manifest')
    if (type(members['schema_version']) is not int or members['schema_version'] != 1
            or members['commit'] != ENGINE_COMMIT or type(members['safe_scoped_extractor_directory_mode']) is not int
            or members['safe_scoped_extractor_directory_mode'] != 0o755):
        raise ValueError('Original pristine member manifest identity mismatch')
    _text(members['scope'], 'original source member scope')
    entries = members['entries']
    if type(entries) is not list or len(entries) != len(files):
        raise ValueError('Original source member count mismatch')
    original, raw_bytes = {}, 0
    for entry in entries:
        inputs.check_deadline()
        if type(entry) is not dict:
            raise ValueError('Invalid original pristine member')
        link = entry.get('type') == 'symlink'
        _fields(entry, ('path', 'type', 'mode', 'target', 'git_mode', 'git_oid', 'target_sha256')
            if link else ('path', 'type', 'mode', 'bytes', 'sha256', 'git_mode', 'git_oid'), 'original pristine member')
        name = _name(entry['path'])
        if name not in files or name in original or {'mode': entry['git_mode'], 'type': 'blob', 'oid': entry['git_oid']} != selected[name]:
            raise ValueError('Original member paths/Git modes/OIDs differ from current raw tree')
        original[name] = entry
        if link:
            if name not in normalizations or type(entry['mode']) is not int or entry['mode'] != 0o777:
                raise ValueError('Original raw link mode/type differs from Git')
            literal = entry['target']
            if (literal != normalizations[name]['literal'] or entry['target_sha256'] != sha256(literal.encode('utf-8'))
                    or entry['git_oid'] != hashlib.sha1(b'blob ' + str(len(literal.encode('utf-8'))).encode('ascii') + b'\0' + literal.encode('utf-8')).hexdigest()):
                raise ValueError('Original link SHA256 must hash its raw literal, not its materialized target')
        else:
            if (entry['type'] != 'file' or name in normalizations or type(entry['bytes']) is not int
                    or type(entry['mode']) is not int or any(entry[field] != files[name][field] for field in ('sha256', 'bytes', 'mode'))):
                raise ValueError('Original regular member bytes differ from clean normalized members')
            raw_bytes += entry['bytes']
    if [item['path'] for item in entries] != sorted(original):
        raise ValueError('Original pristine members must retain their exact sorted path order')
    directories = sorted({parent.as_posix() for name in original for parent in PurePosixPath(name).parents if parent.as_posix() != '.'})
    if members['implicit_directories'] != directories:
        raise ValueError('Original pristine member directory closure mismatch')
    receipt = docs['archive_receipt']
    _fields(receipt, ('all68postimage_hashes_unchanged', 'all71104worktree_physical_identities_unchanged',
        'all_archive_members_content_type_mode_and_order_verified', 'all_network_protocols_forbidden',
        'all_selected_parent_identities_unchanged', 'archive', 'archive_bytes', 'archive_sha256', 'cap_seconds',
        'creation_seconds', 'first_failure_receipt', 'first_failure_receipt_sha256', 'generator_sha256', 'git_command',
        'git_returncode', 'git_stderr_bytes', 'members', 'no_lazy_fetch', 'no_sdk_engine_compiler_network_operation',
        'normalized_metadata', 'raw_pristine_regular_bytes', 'regular_files', 'schema_version', 'source_authority',
        'status', 'supplier_added_paths_omitted', 'supplier_modified_preimages', 'symlink_policy', 'symlinks',
        'total_seconds', 'upstream_commit'), 'original source archive receipt')
    flags = ('all68postimage_hashes_unchanged', 'all71104worktree_physical_identities_unchanged',
        'all_archive_members_content_type_mode_and_order_verified', 'all_network_protocols_forbidden',
        'all_selected_parent_identities_unchanged', 'no_lazy_fetch', 'no_sdk_engine_compiler_network_operation')
    if any(receipt[name] is not True for name in flags):
        raise ValueError('Original source archive operation prerequisites did not pass')
    if (type(receipt['schema_version']) is not int or receipt['schema_version'] != 1
            or receipt['status'] != 'passed-selected-pristine-source-archive-preparation'
            or receipt['upstream_commit'] != ENGINE_COMMIT or receipt['archive_sha256'] != archive['sha256']
            or receipt['generator_sha256'] != proof['generator']['sha256']):
        raise ValueError('Original source archive receipt identity mismatch')
    for name, expected in (('archive_bytes', archive['bytes']), ('members', len(files)), ('regular_files', len(files) - 8),
            ('symlinks', 8), ('raw_pristine_regular_bytes', raw_bytes), ('supplier_modified_preimages', 45),
            ('supplier_added_paths_omitted', 23), ('git_returncode', 0), ('git_stderr_bytes', 0)):
        if type(receipt[name]) is not int or receipt[name] != expected:
            raise ValueError('Original source archive receipt count/bytes mismatch: ' + name)
    manifest.integer(receipt['cap_seconds'], 'original archive time budget', 1, 86400)
    for name in ('creation_seconds', 'total_seconds'):
        if type(receipt[name]) not in (int, float) or not 0 <= receipt[name] <= receipt['cap_seconds']:
            raise ValueError('Invalid original archive elapsed time')
    if receipt['creation_seconds'] > receipt['total_seconds']:
        raise ValueError('Original archive elapsed ordering mismatch')
    for name in ('archive', 'first_failure_receipt', 'source_authority', 'symlink_policy'):
        _text(receipt[name], 'historical archive ' + name)
    pin(receipt['first_failure_receipt_sha256'], 'original first failure')
    expected_command = ['git', '-c', 'protocol.allow=never', '-c', 'protocol.file.allow=never',
        '-c', 'protocol.https.allow=never', '-c', 'protocol.http.allow=never', '-C']
    command = receipt['git_command']
    if type(command) is not list or len(command) != 13 or command[:10] != expected_command or command[11:] != ['cat-file', '--batch']:
        raise ValueError('Original archive Git command does not preserve offline blob-only operation')
    _historical_source_absolute(command[10])  # Historical identity only; never follow or execute it.
    if receipt['normalized_metadata'] != {'compression_level': 1, 'file_modes': 'Git100644/100755 to0644/0755',
            'gid': 0, 'gname': '', 'gzip_filename': '', 'gzip_mtime': 0, 'mtime': 0, 'symlink_mode': 0o777,
            'tar_format': 'PAX', 'uid': 0, 'uname': ''}:
        raise ValueError('Original archive normalization policy mismatch')
    if any(type(receipt['normalized_metadata'][name]) is not int for name in
            ('compression_level', 'gid', 'gzip_mtime', 'mtime', 'symlink_mode', 'uid')):
        raise ValueError('Original archive normalization integer cannot be boolean')
    scope = docs['source_scope']
    _schema(scope, ('schema_version', 'kind', 'archive_sha256', 'commit', 'members', 'omitted_scope',
        'qualification', 'raw_regular_bytes', 'regular_files', 'source_bytes', 'symlink_policy', 'symlinks'),
        'selected-upstream-source-scope-v1')
    if (scope['archive_sha256'] != archive['sha256'] or scope['commit'] != ENGINE_COMMIT
            or type(scope['members']) is not int or scope['members'] != len(files)
            or type(scope['regular_files']) is not int or scope['regular_files'] != len(files) - 8
            or type(scope['raw_regular_bytes']) is not int or scope['raw_regular_bytes'] != raw_bytes):
        raise ValueError('Original source scope/archive/member counts mismatch')
    for name in ('qualification', 'source_bytes', 'symlink_policy'):
        _text(scope[name], 'original source scope ' + name)
    if type(scope['omitted_scope']) is not list or not scope['omitted_scope']:
        raise ValueError('Original omitted source scope required')
    for name in scope['omitted_scope']:
        _text(name, 'original omitted source scope')
    if type(scope['symlinks']) is not list or len(scope['symlinks']) != 8:
        raise ValueError('Original source scope needs exactly eight raw links')
    seen = set()
    for item in scope['symlinks']:
        _fields(item, ('canonical_contained', 'canonical_target', 'canonical_target_regular', 'canonical_target_selected',
            'logical_target', 'logical_target_git_mode', 'logical_target_selected', 'path', 'raw_target',
            'raw_target_matches_local_upstream_blob', 'target_exists', 'target_is_relative'), 'original source scope link')
        name = item['path']
        if name not in normalizations or name in seen:
            raise ValueError('Original source scope has unknown or duplicate link')
        seen.add(name)
        expected = normalizations[name]
        if (any(item[key] is not True for key in ('canonical_contained', 'canonical_target_regular',
                'canonical_target_selected', 'logical_target_selected', 'raw_target_matches_local_upstream_blob',
                'target_exists', 'target_is_relative')) or item['canonical_target'] != expected['target']
                or item['logical_target'] != expected['target'] or item['raw_target'] != expected['literal']
                or item['logical_target_git_mode'] != selected[expected['target']]['mode']):
            raise ValueError('Original source scope literal/contained-target mismatch')
    images = docs['supplier_patch_images']
    _fields(images, ('added_paths', 'existing_modified_paths', 'files', 'git_read', 'patch_paths', 'recipe_patch',
        'schema_version', 'status', 'supplier_patch', 'upstream_commit'), 'original supplier patch images')
    if (type(images['schema_version']) is not int or images['schema_version'] != 1
            or images['upstream_commit'] != ENGINE_COMMIT or images['status'] != 'actual-local-preimages-and-current-postimages-verified'
            or type(images['added_paths']) is not int or images['added_paths'] != 23
            or type(images['existing_modified_paths']) is not int or images['existing_modified_paths'] != 45
            or type(images['patch_paths']) is not int or images['patch_paths'] != 68):
        raise ValueError('Original supplier patch identity/count mismatch')
    supplier_patch = _fields(images['supplier_patch'], ('bytes', 'path', 'sha256'), 'original supplier patch')
    _text(supplier_patch['path'], 'historical supplier patch path')
    patches = [item for item in projection['patches'] if item['sha256'] == SUPPLIER_PATCH and item['tree'] == 'engine']
    if (supplier_patch['sha256'] != SUPPLIER_PATCH or len(patches) != 1 or type(supplier_patch['bytes']) is not int
            or supplier_patch['bytes'] != inputs._records[patches[0]['path']]['bytes']):
        raise ValueError('Original supplier patch differs from exactly one current ordered patch')
    patch = images['recipe_patch']
    _fields(patch, ('path', 'tree', 'preimages', 'postimages'), 'original recipe supplier patch')
    if (patch not in recipe['patches'] or patch['tree'] != 'engine'
            or recipe['inputs'][patch['path']]['sha256'] != SUPPLIER_PATCH
            or any(patch[key] != patches[0][key] for key in ('tree', 'preimages', 'postimages'))
            or len(patch['preimages']) != 68):
        raise ValueError('Original R/S supplier patch images differ from current ordered patch')
    git_read = _fields(images['git_read'], ('command', 'elapsed_seconds', 'network_protocols', 'no_lazy_fetch',
        'optional_locks', 'returncode', 'stderr'), 'original supplier Git image read')
    if (git_read['command'] != command or git_read['network_protocols'] != 'all forbidden'
            or git_read['no_lazy_fetch'] is not True or git_read['optional_locks'] is not False
            or type(git_read['returncode']) is not int or git_read['returncode'] != 0 or git_read['stderr'] != ''
            or type(git_read['elapsed_seconds']) not in (int, float) or not 0 <= git_read['elapsed_seconds'] <= receipt['cap_seconds']):
        raise ValueError('Original supplier Git image observation mismatch')
    entries = images['files']
    if type(entries) is not list or len(entries) != 68:
        raise ValueError('Original supplier file image count mismatch')
    seen, added = set(), 0
    for item in entries:
        inputs.check_deadline()
        _fields(item, ('current_ctime_ns', 'current_device', 'current_inode', 'current_mode', 'current_mtime_ns',
            'path', 'postimage_bytes', 'postimage_sha256', 'preimage_bytes', 'preimage_sha256'), 'original supplier file image')
        name = _name(item['path'])
        pin(item['postimage_sha256'], 'original supplier postimage')
        if name in seen or name not in patch['preimages'] or item['preimage_sha256'] != patch['preimages'][name] or item['postimage_sha256'] != patch['postimages'][name]:
            raise ValueError('Original supplier file/pre/postimage sets mismatch')
        seen.add(name)
        for key in ('current_ctime_ns', 'current_device', 'current_inode', 'current_mode', 'current_mtime_ns', 'postimage_bytes'):
            manifest.integer(item[key], 'original supplier physical/byte fact', 0, 2**63 - 1)
        if not stat.S_ISREG(item['current_mode']):
            raise ValueError('Original supplier postimage physical fact is not regular')
        if item['preimage_sha256'] is None:
            added += 1
            if name in original or item['preimage_bytes'] is not None:
                raise ValueError('Supplier-added file was preapplied to original clean archive')
        elif (name not in original or original[name]['type'] != 'file'
                or type(item['preimage_bytes']) is not int or item['preimage_bytes'] != original[name]['bytes']
                or item['preimage_sha256'] != original[name]['sha256']):
            raise ValueError('Original supplier modified preimage differs from original Git member')
    if added != 23 or seen != set(patch['preimages']):
        raise ValueError('Original supplier 45 modified/23 added path split mismatch')
    if [item['path'] for item in entries] != sorted(seen):
        raise ValueError('Original supplier image path order mismatch')
    return proof


# Private, unexecuted insertion body for appended_engine_native_inputs.py.
# Insert immediately before parse_host_tools; retain that module's imports.
DIAGNOSTIC_HOST_KIND = 'foundation-native-engine-prototype-diagnostic-sdk-host-tools-v1'
DIAGNOSTIC_HOST_SCOPE = 'native-engine-diagnostic-build-host-only'
DIAGNOSTIC_HOST_POLICY_SHA256 = '44d932ed765689c906d1ad87ec02b109d080c6b78f713ab8a1d94784669df999'
_DIAGNOSTIC_AUTHORITY_VERSION = 'fixed-trixie-original-proof-v1'
_DIAGNOSTIC_SOURCE_AUTHORITY_VERSION = 'diagnostic-host-authored-source-v1'
_DIAGNOSTIC_ORIGINAL_HELPER_SOURCE = 'tools/appended_engine_native_original_proof.py'
_DIAGNOSTIC_ORIGINAL_HELPER_SHA256 = '73ab3f22855e7d647e6259004288fe3fc0754b38aa19d7abfd513fff705e8fd8'


@dataclass(frozen=True)
class _DiagnosticOriginalAuthority:
    version: str
    source_closure_sha256: str
    launch_policy_sha256: str


@dataclass(frozen=True)
class _DiagnosticHostPreflight:
    _owner: object
    _base: str
    _repository_root: str
    _host_sha256: str
    _toolchain_sha256: str
    _authority: _DiagnosticOriginalAuthority
    _payload: bytes


# Only reviewed source/callsite changes may install these private authorities.
# No input document, request field or successful producer result can fill them.
@dataclass(frozen=True)
class _DiagnosticRole7Authority:
    source_closure_sha256: str
    launch_policy_sha256: str
    os_manifest_sha256: str
    os_original_record_sha256: str


# Same existing ROLE7/OS approvals grouped for the passive retained-v2 path.
# JSON, CLI and successful observations never install reviewed caller authority.
_DIAGNOSTIC_ROLE7_AUTHORITY = None
_DIAGNOSTIC_ROLE7_KIND = 'foundation-retained-diagnostic-host-original-proof-provenance-v2'
_DIAGNOSTIC_ROLE7_HELPER_SHA256 = '5c85913737f511d9e6b2ec70739cae7885188d9c73c447c3d7fccc8160ca8ee6'


_DIAGNOSTIC_ORIGINAL_AUTHORITY = None
_DIAGNOSTIC_AUTHORED_SOURCES = ()  # (version, derived ID, independently approved SHA256)
# Exact released73ab generated inventory metadata categories. An arbitrary
# opaque *-inventory role is not a metadata exception.
_DIAGNOSTIC_GENERATED_INVENTORY_ROLES = frozenset(
    ['diagnostic-body-packages-inventory']
    + ['diagnostic-body-runtime-' + role + '-inventory' for role in ('controller', 'gpgv', 'dpkg_deb')]
    + ['diagnostic-body-' + kind + '-' + role + '-inventory'
       for kind in ('deb', 'member-tar') for role in ('gperf', 'ruby3.3', 'libruby3.3')])


def _diagnostic_authority():
    authority = _DIAGNOSTIC_ORIGINAL_AUTHORITY
    absent = []
    for role, name in (('diagnostic-original-source-authority', 'source_closure_sha256'),
                       ('diagnostic-original-launch-authority', 'launch_policy_sha256')):
        value = getattr(authority, name, None) if type(authority) is _DiagnosticOriginalAuthority else None
        try:
            pin(value, role)
        except ValueError:
            absent.append({'role': role, 'path': '',
                           'reason': 'independently approved original authority is absent'})
    if absent:
        raise MissingInputs(absent)
    if authority.version != _DIAGNOSTIC_AUTHORITY_VERSION:
        raise ValueError('Unsupported internal diagnostic original authority version')
    return authority


def _diagnostic_role7_authority():
    authority = _DIAGNOSTIC_ROLE7_AUTHORITY
    fields = ('source_closure_sha256', 'launch_policy_sha256',
              'os_manifest_sha256', 'os_original_record_sha256')
    if type(authority) is not _DiagnosticRole7Authority:
        raise MissingInputs([{'role': 'diagnostic-role7-original-authority', 'path': '',
            'reason': 'existing independently approved ROLE7 source/launch and original OS pins absent'}])
    missing = []
    for name in fields:
        if getattr(authority, name) is None:
            missing.append({'role': 'diagnostic-role7-' + name, 'path': '',
                'reason': 'existing independently approved ROLE7/OS pin absent'})
        else:
            pin(getattr(authority, name), 'diagnostic-role7-' + name)
    if missing:
        raise MissingInputs(missing)
    return authority


def _diagnostic_role7_api():
    from types import SimpleNamespace
    return SimpleNamespace(**globals())


def _diagnostic_role7_helper(inputs, repository_root):
    import appended_engine_native_role7 as role7
    root = _diagnostic_absolute(repository_root)
    path = root / 'tools/appended_engine_native_role7.py'
    if getattr(role7, '__file__', None) != str(path):
        raise ValueError('ROLE7 consumer must use its exact maintained source path')
    raw = _producer_bytes(inputs, path, 'diagnostic-provenance-role7-producer-helper', root)
    if sha256(raw) != _DIAGNOSTIC_ROLE7_HELPER_SHA256:
        raise ValueError('ROLE7 consumer source differs from independent fixed source')
    return role7


def _diagnostic_authored_source(name, digest, path):
    approved = []
    for item in _DIAGNOSTIC_AUTHORED_SOURCES:
        if type(item) is not tuple or len(item) != 3:
            raise ValueError('Malformed internal diagnostic authored-source authority')
        version, identifier, expected = item
        pin(expected, 'diagnostic authored-source authority')
        if version == _DIAGNOSTIC_SOURCE_AUTHORITY_VERSION and identifier == name:
            approved.append(expected)
    if len(approved) > 1:
        raise ValueError('Ambiguous internal diagnostic authored-source authority')
    if not approved:
        raise MissingInputs([{'role': 'diagnostic-authored-source-authority', 'path': str(path),
                              'reason': 'independent authored source authority is absent: ' + name}])
    if digest != approved[0]:
        raise ValueError('Diagnostic authored source differs from independent source authority')


def _diagnostic_helper_sources(original, inputs, repository_root):
    imported = _diagnostic_absolute(getattr(original, '__file__', None))
    if imported.name != 'appended_engine_native_original_proof.py' or imported.parent.name != 'tools':
        raise ValueError('Imported diagnostic helper must have its ordinary repository tools source path')
    imported_root = imported.parent.parent
    repository_root = _diagnostic_absolute(repository_root)
    selected = repository_root / _DIAGNOSTIC_ORIGINAL_HELPER_SOURCE
    bodies = []
    for label, path, root in (('imported', imported, imported_root),
                              ('retained', selected, repository_root)):
        try:
            raw = _producer_bytes(inputs, path, 'native-producer-diagnostic-original-proof-' + label, root)
        except FileNotFoundError as error:
            raise MissingInputs([{'role': 'diagnostic-original-proof-helper', 'path': str(path),
                'reason': 'exact released passive proof-consumer source absent'}]) from error
        if sha256(raw) != _DIAGNOSTIC_ORIGINAL_HELPER_SHA256:
            raise ValueError('Diagnostic ' + label + ' helper source differs from independently fixed73ab')
        bodies.append(raw)
    if bodies[0] != bodies[1]:
        raise ValueError('Imported and retained diagnostic helper source bytes differ')


def _diagnostic_original(launch_ref, base, inputs, authority, *, repository_root=ROOT):
    try:
        import appended_engine_native_original_proof as original
    except ModuleNotFoundError as error:
        if error.name != 'appended_engine_native_original_proof':
            raise
        raise MissingInputs([{'role': 'diagnostic-original-proof-helper',
            'path': str(_diagnostic_absolute(repository_root) / _DIAGNOSTIC_ORIGINAL_HELPER_SOURCE),
            'reason': 'released passive original-proof consumer source absent'}]) from error
    _diagnostic_helper_sources(original, inputs, repository_root)
    try:
        return original._diagnostic_original_proof(launch_ref, base, inputs,
            approved_source_closure_sha256=authority.source_closure_sha256,
            approved_launch_policy_sha256=authority.launch_policy_sha256)
    except original.MissingInputs as error:
        raise MissingInputs(error.missing) from error


def _diagnostic_capture(inputs, path, digest, role, maximum=MAX_FILE):
    record = inputs.file(path, digest, role, maximum=maximum)
    opaque = role.startswith('diagnostic-body-')
    if opaque and any(any(marker in old for marker in ('provenance', 'inventory', 'inspection'))
            or old in ('font', 'font_config', 'icu_data', 'ca_bundle', 'host-runtime-facts')
            for old in record.get('roles', ())):
        raise ValueError('An opaque diagnostic body already has a metadata capture role')
    if not opaque and any(old.startswith('diagnostic-body-')
            and old not in _DIAGNOSTIC_GENERATED_INVENTORY_ROLES for old in record.get('roles', ())):
        raise ValueError('Diagnostic original metadata already has an opaque body capture role')
    return record


def _diagnostic_raw(ref, base, inputs, role, maximum=1024 * 1024):
    path, digest = _ref(ref, _diagnostic_absolute(base))
    path = _diagnostic_absolute(path)
    record = _diagnostic_capture(inputs, path, digest, role, maximum=maximum)
    if record['mode'] != 0o644:
        raise ValueError('Diagnostic original metadata must be ordinary0644')
    raw = inputs.bytes(path, maximum=maximum)
    if type(raw) is not bytes or len(raw) != record['bytes'] or sha256(raw) != digest:
        raise ValueError('Diagnostic original metadata changed during bounded capture')
    return {'path': str(path), 'sha256': digest}, raw


def _diagnostic_document(ref, base, inputs, role):
    normalized, raw = _diagnostic_raw(ref, base, inputs, role)
    return normalized, strict_json(raw, role)


def _diagnostic_absolute(value):
    path = _absolute(value)
    try:
        str(path).encode('utf-8')
    except UnicodeError as error:
        raise ValueError('Diagnostic absolute path must be valid UTF-8') from error
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in str(path)):
        raise ValueError('Diagnostic absolute path contains a control character')
    return path


def _diagnostic_reference(ref, base):
    path, digest = _ref(ref, _diagnostic_absolute(base))
    path = _diagnostic_absolute(path)
    return {'path': str(path), 'sha256': digest}


def _diagnostic_name(value, label):
    if '/' in _name(value):
        raise ValueError(label + ' must be a portable single-component identifier')
    return value


def _diagnostic_map(value, label):
    if type(value) is not dict or len(value) > MAX_FILES:
        raise ValueError(label + ' must be a bounded identifier map')
    for name in value:
        _diagnostic_name(name, label)
    return value


def _diagnostic_ownership(value):
    _fields(value, ('closed', 'descendants_closed', 'logs_closed'), 'diagnostic original ownership')
    if any(flag is not True for flag in value.values()):
        raise ValueError('Diagnostic original process/descendant/log ownership is open')


def _diagnostic_time(value):
    from datetime import datetime
    if type(value) is not str or re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)', value) is None:
        raise ValueError('Diagnostic timestamp must be an explicit UTC ISO-8601 value')
    try:
        return datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value)
    except ValueError as error:
        raise ValueError('Invalid diagnostic UTC timestamp') from error


def _diagnostic_environment(toolchain, host):
    # SDK inspection calls parse_host_tools before its complete toolchain exists.
    # Its admitted binding already supplies policy and all exact program paths.
    policy = toolchain['sdk_binding']['policy']
    programs = list(toolchain['tools'].values()) + list(host['programs'].values())
    environment = {'PATH': ':'.join(sorted({str(Path(item['path']).parent) for item in programs})),
        'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
        'SOURCE_DATE_EPOCH': policy['source_date_epoch']}
    if 'environment' in toolchain and toolchain['environment'] != environment:
        raise ValueError('Diagnostic toolchain environment differs from its exact admitted SDK policy')
    return render_environment(dict(toolchain, environment=environment), host)


def _diagnostic_external_inventories(*collections):
    joined = {}
    for collection in collections:
        if type(collection) is not list or len(collection) > MAX_FILES:
            raise ValueError('Diagnostic external inventories must be a bounded list')
        for item in collection:
            _fields(item, ('root', 'inventory'), 'diagnostic external inventory')
            _fields(item['inventory'], ('path', 'sha256'), 'diagnostic external inventory metadata')
            root = str(_diagnostic_absolute(item['root']))
            path = str(_diagnostic_absolute(item['inventory']['path']))
            digest = pin(item['inventory']['sha256'], 'diagnostic external inventory')
            if root == path or Path(root) in Path(path).parents:
                raise ValueError('Diagnostic inventory metadata must remain outside its opaque root')
            joined[(root, path, digest)] = {'root': root, 'inventory': {'path': path, 'sha256': digest}}
    return [joined[key] for key in sorted(joined)]


class _DiagnosticProofCapture:
    """Keep an original proof's capture outside previously broader roots."""
    def __init__(self, inputs, roots):
        self.inputs = inputs
        self.roots = tuple(_diagnostic_absolute(root) for root in roots)

    def __getattr__(self, name):
        return getattr(self.inputs, name)

    def file(self, path, digest, role, maximum=MAX_FILE):
        path = _diagnostic_absolute(path)
        if (role.startswith('diagnostic-body-') and role not in _DIAGNOSTIC_GENERATED_INVENTORY_ROLES
                and any(path == root or root in path.parents for root in self.roots)):
            raise ValueError('Original opaque proof input overlaps an already broader admitted root')
        return self.inputs.file(path, digest, role, maximum=maximum)

    def inventory(self, record, base, role):
        _fields(record, ('root', 'inventory'), 'original proof complete inventory')
        root = _diagnostic_absolute(record['root'])
        if any(root == old or root in old.parents or old in root.parents for old in self.roots):
            raise ValueError('Original proof root overlaps an already broader admitted root')
        return self.inputs.inventory(record, base, role)


def _diagnostic_toolchain_identity(toolchain):
    binding = toolchain['sdk_binding']
    return sha256(encoded({'kind': toolchain['kind'], 'root': binding['root'],
        'sdk_manifest_sha256': binding['sdk_manifest_sha256'], 'policy': binding['policy'],
        'inventories': {name: {'root': item['root'], 'inventory': item.get('inventory')}
                        for name, item in toolchain['inventories'].items()}}))


def _diagnostic_original_result(original, wrapper, base):
    _fields(original, ('launch', 'proof', 'packages', 'external_inventories'), 'diagnostic original result')
    _fields(original['launch'], ('path', 'sha256'), 'diagnostic original normalized launch')
    if original['launch'] != _diagnostic_reference(wrapper['original_proof'], base):
        raise ValueError('Diagnostic original result does not join its exact submitted launch reference')
    _fields(original['proof'], ('path', 'sha256', 'bytes', 'kind'), 'diagnostic original normalized proof')
    _diagnostic_absolute(original['proof']['path'])
    pin(original['proof']['sha256'], 'diagnostic original normalized proof')
    manifest.integer(original['proof']['bytes'], 'diagnostic original proof bytes', 1, 1024 * 1024)
    if original['proof']['kind'] != 'foundation-native-fixed-trixie-original-proof-v1':
        raise ValueError('Diagnostic original result proof kind differs')
    return _diagnostic_external_inventories(original['external_inventories'])


def _diagnostic_host_preflight(value, base, inputs, toolchain, *, repository_root=ROOT):
    """Capture original proof once, before common host-extension root walks."""
    authority = _diagnostic_authority()
    base = _diagnostic_absolute(base)
    repository_root = _diagnostic_absolute(repository_root)
    _schema(value, ('schema_version', 'kind', 'programs', 'module_inventories',
                   'interpreter_bindings', 'diagnostic_host', 'source_provenance'), DIAGNOSTIC_HOST_KIND)
    binding = toolchain.get('sdk_binding')
    if (toolchain.get('kind') not in ('foundation-native-engine-prototype-sdk-toolchain-v1', PRIVATE_TOOLCHAIN_KIND)
            or type(binding) is not dict or binding.get('host_document') != value
            or 'sdk' not in toolchain.get('inventories', {})):
        raise ValueError('Diagnostic preflight requires its exact admitted SDK host binding')
    provenance_ref, wrapper = _diagnostic_document(value['source_provenance'], base, inputs,
                                                   'diagnostic-provenance-wrapper')
    provenance_base = Path(provenance_ref['path']).parent
    if type(wrapper) is dict and wrapper.get('kind') == _DIAGNOSTIC_ROLE7_KIND:
        _diagnostic_role7_authority()
        role7 = _diagnostic_role7_helper(inputs, repository_root)
        return role7.preflight(_diagnostic_role7_api(), value, base, inputs, toolchain, authority,
            provenance_ref, wrapper, repository_root=repository_root)
    wrapper_kind = 'foundation-retained-diagnostic-host-original-proof-provenance-v1'
    if type(wrapper) is not dict or wrapper.get('kind') != wrapper_kind:
        raise MissingInputs([{'role': 'diagnostic-host-provenance', 'path': provenance_ref['path'],
                              'reason': 'compatible original-proof diagnostic provenance absent'}])
    _schema(wrapper, ('schema_version', 'kind', 'scope', 'original_proof', 'derived_files',
                     'operating_system_providers'), wrapper_kind)
    if wrapper['scope'] != DIAGNOSTIC_HOST_SCOPE:
        raise ValueError('Diagnostic provenance scope differs')
    prior_roots = [item['root'] for item in toolchain['inventories'].values()]
    proof_capture = _DiagnosticProofCapture(inputs, prior_roots)
    original = _diagnostic_original(wrapper['original_proof'], provenance_base, proof_capture, authority,
                                    repository_root=repository_root)
    external = _diagnostic_original_result(original, wrapper, provenance_base)
    # A later common inventory may reuse an exact complete captured root/pin.
    # It cannot add a wider root or replace the root's bounded inventory contents.
    for name, item in _diagnostic_map(value['module_inventories'], 'diagnostic host extensions').items():
        _fields(item, ('root', 'inventory'), 'diagnostic host extension inventory')
        root = _diagnostic_absolute(item['root'])
        reference = _diagnostic_reference(item['inventory'], base)
        for captured in external:
            old = Path(captured['root'])
            if root == old or root in old.parents or old in root.parents:
                if root != old or reference['sha256'] != captured['inventory']['sha256']:
                    raise ValueError('Diagnostic host extension contradicts an original bounded complete root')
    payload = encoded({'provenance_ref': provenance_ref, 'wrapper': wrapper, 'original': original})
    if len(payload) > MAX_DOCUMENT:
        raise ValueError('Diagnostic immutable preflight metadata exceeds document bound')
    return _DiagnosticHostPreflight(inputs, str(base), str(repository_root), sha256(encoded(value)),
                                   _diagnostic_toolchain_identity(toolchain), authority, payload)


def _diagnostic_preflight_records(preflight, value, base, inputs, toolchain, authority, *, repository_root=ROOT):
    if (type(preflight) is not _DiagnosticHostPreflight or preflight._owner is not inputs
            or preflight._base != str(_diagnostic_absolute(base))
            or preflight._repository_root != str(_diagnostic_absolute(repository_root))
            or preflight._host_sha256 != sha256(encoded(value))
            or preflight._toolchain_sha256 != _diagnostic_toolchain_identity(toolchain)
            or preflight._authority != authority or type(preflight._payload) is not bytes):
        raise ValueError('Diagnostic preflight is not bound to this exact original capture owner and inputs')
    payload = strict_json(preflight._payload, 'diagnostic immutable preflight')
    _fields(payload, ('provenance_ref', 'wrapper', 'original'), 'diagnostic immutable preflight')
    return payload['provenance_ref'], payload['wrapper'], payload['original']


def _diagnostic_retained_file(value, combined, inputs, role):
    _fields(value, ('path', 'sha256', 'bytes', 'inventory'), 'diagnostic retained FILE')
    path = _diagnostic_absolute(value['path'])
    digest = pin(value['sha256'], 'diagnostic retained FILE')
    manifest.integer(value['bytes'], 'diagnostic retained bytes', 0, MAX_FILE)
    alias = _diagnostic_name(value['inventory'], 'diagnostic inventory alias')
    if alias not in combined:
        raise ValueError('Diagnostic retained FILE names an unadmitted inventory')
    inventory = combined[alias]
    root = Path(inventory['root'])
    if root not in path.parents:
        raise ValueError('Diagnostic retained FILE is outside its declared complete inventory')
    member = path.relative_to(root).as_posix()
    if inventory['files'].get(member) != digest:
        raise ValueError('Diagnostic retained FILE differs from its complete inventory')
    captured = _diagnostic_capture(inputs, path, digest, role)
    if captured['bytes'] != value['bytes'] or captured['mode'] != inventory['modes'].get(member):
        raise ValueError('Diagnostic retained FILE byte/mode facts differ from actual capture')
    return {'path': str(path), 'sha256': digest, 'bytes': captured['bytes'], 'mode': captured['mode'],
            'inventory': alias}


def _diagnostic_same_file(retained, origin):
    if any(retained[name] != origin[name] for name in ('sha256', 'bytes', 'mode')):
        raise ValueError('Diagnostic retained file differs from exact original hash/size/mode')


def _diagnostic_terminal_authority(origin, role, path):
    # Byte-copy equality is not an independent binary upstream authority.
    # A future reviewed OS-origin contract must extend this boundary explicitly.
    if origin['terminal'] not in ('sdk', 'package'):
        raise MissingInputs([{'role': role, 'path': str(path),
            'reason': 'separately approved original binary origin is absent; retained source-copy equality is insufficient'}])


class _DiagnosticOrigins:
    """Join already captured facts; no archive parser, root walk or path following."""
    def __init__(self, wrapper, base, inputs, combined, sdk, packages):
        self.base, self.inputs, self.combined, self.sdk = base, inputs, combined, sdk
        self.packages = packages
        self.derived = _diagnostic_map(wrapper['derived_files'], 'diagnostic derived files')
        self.cache = {}
        self.active = set()
        self.aliases = []
        self.retained = {}
        if type(packages) is not dict or set(packages) != {'gperf', 'ruby3.3', 'libruby3.3'}:
            raise ValueError('Diagnostic original proof must return exactly its fixed three package IDs')
        for package in packages.values():
            _fields(package, ('name', 'source_package', 'version', 'architecture', 'members', 'link_origins'),
                    'diagnostic original package facts')
            if type(package['members']) is not dict or type(package['link_origins']) is not dict:
                raise ValueError('Diagnostic package member/link facts must be maps')
        for name, item in self.derived.items():
            if type(item) is not dict:
                raise ValueError('Diagnostic derived record must be a tagged object')
            kind = item.get('kind')
            fields = ('kind', 'retained', 'source') if kind == 'source-copy' else (
                ('kind', 'retained', 'origin') if kind == 'byte-copy' else
                ('kind', 'logical_path', 'resolved_path', 'origin') if kind == 'logical-alias' else ())
            if not fields:
                raise ValueError('Unknown diagnostic derived file kind')
            _fields(item, fields, 'diagnostic derived file')
            if kind == 'logical-alias':
                logical, resolved = str(_diagnostic_absolute(item['logical_path'])), str(_diagnostic_absolute(item['resolved_path']))
                if logical == resolved or any(old[0] == logical for old in self.aliases):
                    raise ValueError('Diagnostic logical aliases must be explicit and unambiguous')
                self.aliases.append((logical, resolved, item['origin']))
        for name, item in self.derived.items():
            if item['kind'] != 'logical-alias':
                self.resolve(name)
        for _, _, origin in self.aliases:
            if self.origin(origin).get('alias') is not None:
                raise ValueError('A diagnostic logical alias must name its regular terminal origin')

    def _package(self, package_id, member):
        from pathlib import PurePosixPath
        import posixpath
        if package_id not in self.packages:
            raise MissingInputs([{'role': 'diagnostic-original-package-authority', 'path': package_id,
                'reason': 'compatible independently proved package is absent'}])
        package = self.packages[package_id]
        if set(package['members']) & set(package['link_origins']):
            raise ValueError('Diagnostic original regular members and alias facts overlap')
        member = _name(member)
        alias = None
        if member in package['link_origins']:
            link = package['link_origins'][member]
            _fields(link, ('type', 'target'), 'diagnostic original package alias')
            target = link['target']
            if link['type'] not in ('symlink', 'hardlink') or type(target) is not str or not target:
                raise ValueError('Diagnostic package alias needs its original type and literal target')
            if target.startswith('/') or '\\' in target or any(c in target for c in ('\x00', ':', ';')):
                raise ValueError('Diagnostic package alias target is absolute or escaping')
            regular = posixpath.normpath(posixpath.join(str(PurePosixPath(member).parent), target)
                if link['type'] == 'symlink' else target)
            regular = _name(regular)
            if regular not in package['members']:
                raise MissingInputs([{'role': 'diagnostic-original-alias-target', 'path': member,
                    'reason': 'explicit original alias does not select a proved regular target member'}])
            alias = {'package': package_id, 'member': member, 'regular_member': regular,
                     'type': link['type'], 'literal_target': target}
            member = regular
        if member not in package['members']:
            raise MissingInputs([{'role': 'diagnostic-original-package-member', 'path': member,
                'reason': 'exact original regular member was not selected by the fixed proof'}])
        fact = package['members'][member]
        _fields(fact, ('sha256', 'size', 'mode'), 'diagnostic original regular member')
        pin(fact['sha256'], 'diagnostic package member')
        manifest.integer(fact['size'], 'diagnostic original member size', 0, MAX_MEMBER)
        manifest.integer(fact['mode'], 'diagnostic original member mode', 0, 0o777)
        return {'sha256': fact['sha256'], 'bytes': fact['size'], 'mode': fact['mode'],
                'terminal': 'package', 'package': package_id, 'member': member, 'alias': alias}

    def origin(self, value):
        if type(value) is not dict:
            raise ValueError('Diagnostic origin must be a closed tagged object')
        kind = value.get('kind')
        if kind == 'sdk':
            _fields(value, ('kind', 'path'), 'diagnostic SDK origin')
            member = _name(value['path'])
            if member not in self.sdk['files']:
                raise ValueError('Diagnostic SDK origin is not an actual captured SDK manifest leaf')
            path = Path(self.sdk['root']) / member
            record = _diagnostic_capture(self.inputs, path, self.sdk['files'][member], 'diagnostic-body-sdk-origin')
            return dict(record, terminal='sdk', member=member, alias=None)
        if kind == 'package':
            _fields(value, ('kind', 'package', 'member'), 'diagnostic package origin')
            return self._package(_diagnostic_name(value['package'], 'diagnostic package ID'), value['member'])
        if kind == 'derived':
            _fields(value, ('kind', 'id'), 'diagnostic derived origin')
            return self.resolve(_diagnostic_name(value['id'], 'diagnostic derived origin ID'))
        raise ValueError('Unknown diagnostic origin kind')

    def resolve(self, name):
        if name in self.cache:
            return self.cache[name]
        if name not in self.derived:
            raise MissingInputs([{'role': 'diagnostic-original-derived-file', 'path': name,
                'reason': 'exact retained derivation record absent'}])
        if name in self.active:
            raise ValueError('Diagnostic retained derivation contains a cycle')
        item = self.derived[name]
        if item['kind'] == 'logical-alias':
            raise ValueError('Logical alias metadata cannot supply retained runtime file authority')
        self.active.add(name)
        try:
            authored = name == 'observer' and item['kind'] == 'source-copy'
            if item['kind'] == 'source-copy':
                source_path, source_pin = _ref(item['source'], _diagnostic_absolute(self.base))
                source_path = _diagnostic_absolute(source_path)
            if authored:
                _diagnostic_authored_source(name, source_pin, source_path)
            role = 'diagnostic-provenance-authored-source' if authored else 'diagnostic-body-derived'
            retained = _diagnostic_retained_file(item['retained'], self.combined, self.inputs, role)
            if retained['path'] in self.retained:
                raise ValueError('Diagnostic retained file has competing derivation records')
            if item['kind'] == 'source-copy':
                source = _diagnostic_capture(self.inputs, source_path, source_pin, role, maximum=MAX_MEMBER)
                if (source['sha256'], source['bytes']) != (retained['sha256'], retained['bytes']):
                    raise ValueError('Diagnostic retained source-copy differs from its captured original source bytes')
                if authored and (retained['mode'] != 0o644 or source['mode'] != 0o644 or not retained['bytes']):
                    raise ValueError('Diagnostic observer source must be nonempty ordinary0644')
                result = dict(retained, terminal='authored-source' if authored else 'unproved-copy', alias=None)
            else:
                origin = self.origin(item['origin'])
                _diagnostic_same_file(retained, origin)
                result = dict(origin, **retained)
            # Recursive origin resolution may have registered this same retained
            # path since the check above. It must not silently replace its owner.
            if retained['path'] in self.retained:
                raise ValueError('Diagnostic retained file has competing derivation records')
            self.retained[retained['path']] = name
            self.cache[name] = result
            return result
        finally:
            self.active.remove(name)

    def match(self, retained, origin, role, observed=None):
        fact = self.origin(origin)
        _diagnostic_same_file(retained, fact)
        _diagnostic_terminal_authority(fact, role, retained['path'])
        alias = fact.get('alias')
        if alias is not None:
            matched = False
            for logical, resolved, candidate in self.aliases:
                if observed is not None and (logical, resolved) == observed:
                    regular = self.origin(candidate)
                    if (regular['terminal'] == 'package' and regular.get('alias') is None
                            and regular.get('package') == alias['package']
                            and regular.get('member') == alias['regular_member']):
                        matched = True
            if not matched:
                raise MissingInputs([{'role': 'diagnostic-original-logical-alias', 'path': retained['path'],
                    'reason': 'original literal package alias needs its explicit observed logical/resolved regular-target derivation'}])
        return fact


def _diagnostic_provider(value, origins, role):
    _fields(value, ('logical_path', 'resolved_path', 'retained', 'origin'), 'diagnostic provider')
    logical, resolved = str(_diagnostic_absolute(value['logical_path'])), str(_diagnostic_absolute(value['resolved_path']))
    retained = _diagnostic_retained_file(value['retained'], origins.combined, origins.inputs,
        'diagnostic-body-provider' if role == 'provider' else 'diagnostic-body-module')
    fact = origins.match(retained, value['origin'], 'diagnostic-original-' + role + '-authority',
                         (logical, resolved))
    # Keep the closed PROVIDER vocabulary in the normalized result. Mode/size
    # joins stay in separately captured facts, never invented observation fields.
    return _json_copy(value), retained, fact


def _diagnostic_ids(value, label):
    if (type(value) is not list or len(value) > MAX_FILES or any(type(name) is not str for name in value)
            or value != sorted(set(value))):
        raise ValueError(label + ' must be sorted unique identifiers')
    for name in value:
        _diagnostic_name(name, label)
    return value


def _diagnostic_subjects(value, roles, path, label):
    if type(value) is not dict:
        raise ValueError(label + ' must be a program-role map')
    if set(value) - set(roles):
        raise ValueError(label + ' contains an unadmitted program role')
    missing = [{'role': 'diagnostic-host-subject-' + role, 'path': str(path),
                'reason': 'original all-role diagnostic subject evidence absent'}
               for role in sorted(set(roles) - set(value))]
    if missing:
        raise MissingInputs(missing)


def _diagnostic_os_release(raw):
    import shlex
    if type(raw) is not bytes or len(raw) > 65536:
        raise ValueError('Diagnostic os-release exceeds its raw byte bound')
    try:
        text = raw.decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Diagnostic os-release must be UTF-8 original bytes') from error
    values = {}
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Z][A-Z0-9_]*)=(.*)', line)
        if not match:
            raise ValueError('Malformed diagnostic os-release assignment')
        name, item = match.groups()
        try:
            decoded = shlex.split(item, comments=False, posix=True)
        except ValueError as error:
            raise ValueError('Malformed diagnostic os-release quoted value') from error
        if len(decoded) > 1:
            raise ValueError('Unquoted spaces in diagnostic os-release value')
        value = decoded[0] if decoded else ''
        if name in values and values[name] != value:
            raise ValueError('Contradictory duplicate diagnostic os-release key')
        values[name] = value
    if not {'ID', 'VERSION_ID', 'VERSION_CODENAME'} <= set(values):
        raise MissingInputs([{'role': 'diagnostic-host-os-release', 'path': '',
            'reason': 'original os-release lacks ID/VERSION_ID/VERSION_CODENAME'}])
    return {'id': values['ID'], 'version_id': values['VERSION_ID'], 'codename': values['VERSION_CODENAME']}


def _diagnostic_command(value, argv, environment, base, inputs, role):
    _fields(value, ('argv', 'environment', 'cwd', 'returncode', 'stdout', 'stderr',
                    'started_utc', 'finished_utc', 'ownership'), 'diagnostic original COMMAND')
    if (value['argv'] != argv or value['environment'] != environment
            or type(value['returncode']) is not int or value['returncode'] != 0):
        raise ValueError('Diagnostic original argv/environment/returncode differs from its exact collector contract')
    _diagnostic_absolute(value['cwd'])  # Original observation only; never open or execute it.
    _diagnostic_ownership(value['ownership'])
    started, finished = _diagnostic_time(value['started_utc']), _diagnostic_time(value['finished_utc'])
    if finished < started:
        raise ValueError('Diagnostic original command UTC interval is reversed')
    _, raw = _diagnostic_raw(value['stdout'], base, inputs, 'diagnostic-provenance-command-' + role + '-stdout')
    _diagnostic_raw(value['stderr'], base, inputs, 'diagnostic-provenance-command-' + role + '-stderr')
    return strict_json(raw, 'diagnostic original raw ' + role), started, finished


def validate_diagnostic_host(value, base, inputs, toolchain, host, *, policy_raw, _preflight=None, repository_root=ROOT):
    """Join complete original diagnostic facts; never launch or qualify a host.

    The two original-proof authorities are checked before any submitted graph
    capture. Complete raw/retained joins below remain implemented even though no
    compatible actual authority or complete actual host observations exist.
    """
    authority = _diagnostic_authority()
    _schema(value, ('schema_version', 'kind', 'programs', 'module_inventories',
                   'interpreter_bindings', 'diagnostic_host', 'source_provenance'), DIAGNOSTIC_HOST_KIND)
    binding = toolchain.get('sdk_binding')
    if (toolchain.get('kind') not in ('foundation-native-engine-prototype-sdk-toolchain-v1', PRIVATE_TOOLCHAIN_KIND)
            or type(binding) is not dict or binding.get('host_document') != value
            or host.get('programs') != value['programs'] or 'interpreter_runtimes' not in host
            or 'sdk' not in toolchain.get('inventories', {})):
        raise ValueError('Diagnostic host must retain its exact admitted original SDK-host document and common checks')
    if type(policy_raw) is not bytes or sha256(policy_raw) != DIAGNOSTIC_HOST_POLICY_SHA256:
        raise ValueError('Diagnostic host requires the exact fixed independent producer policy')
    policy = strict_json(policy_raw, 'diagnostic host producer policy')
    _schema(policy, ('schema_version', 'kind', 'scope', 'policy_id', 'execution_host', 'sdk_original_host',
        'target', 'cpu', 'program_roles', 'production_eligible', 'native_engine_execution', 'kernel_rebuild'),
        'foundation-native-diagnostic-host-policy-v1')
    if (policy['scope'] != DIAGNOSTIC_HOST_SCOPE
            or binding['policy']['runtime']['c_library_baseline'] != policy['target']['glibc']
            or binding['policy']['cpu'] != policy['cpu']):
        raise ValueError('Diagnostic policy cannot change admitted SDK target runtime or CPU policy')
    combined = dict(toolchain['inventories'])
    combined.update({'host-' + name: item for name, item in host['module_inventories'].items()})
    preflight = (_diagnostic_host_preflight(value, base, inputs, toolchain, repository_root=repository_root)
                 if _preflight is None else _preflight)
    provenance_ref, wrapper, original = _diagnostic_preflight_records(
        preflight, value, base, inputs, toolchain, authority, repository_root=repository_root)
    provenance_base = Path(provenance_ref['path']).parent
    # Reuse only immutable owner-bound facts. The original helper already owns
    # its 1GiB preflight; do not invoke it or walk its complete roots a second time.
    _diagnostic_original_result(original, wrapper, provenance_base)
    role7 = role7_records = None
    if wrapper['kind'] == _DIAGNOSTIC_ROLE7_KIND:
        role7 = _diagnostic_role7_helper(inputs, repository_root)
        role7_records = role7.records(_diagnostic_role7_api(), wrapper, provenance_base, inputs,
            _diagnostic_role7_authority(), repository_root=repository_root)
        origins = role7.origins(_diagnostic_role7_api(), wrapper, provenance_base, inputs, combined,
            toolchain['inventories']['sdk'], original['packages'], role7_records)
    else:
        origins = _DiagnosticOrigins(wrapper, provenance_base, inputs, combined,
                                     toolchain['inventories']['sdk'], original['packages'])
    if 'observer' not in origins.derived or origins.derived['observer']['kind'] != 'source-copy':
        raise MissingInputs([{'role': 'diagnostic-host-observer-source', 'path': provenance_ref['path'],
            'reason': 'original independently approved observer source-copy record absent'}])
    observer = origins.resolve('observer')
    if observer['terminal'] != 'authored-source':
        raise ValueError('Diagnostic observer requires independent authored source authority')
    observations_ref, observed = _diagnostic_document(value['diagnostic_host'], base, inputs,
                                                      'diagnostic-provenance-observations')
    observed_base = Path(observations_ref['path']).parent
    observation_kind = 'foundation-native-diagnostic-build-host-observations-v1'
    if type(observed) is not dict or observed.get('kind') != observation_kind:
        raise MissingInputs([{'role': 'diagnostic-host-observations', 'path': observations_ref['path'],
                              'reason': 'compatible original complete diagnostic host observations absent'}])
    _schema(observed, ('schema_version', 'kind', 'scope', 'policy_id', 'observed_utc', 'subjects', 'host',
        'runtime', 'commands', 'ownership', 'production_eligible', 'native_engine_execution', 'kernel_rebuild'),
        observation_kind)
    if (observed['scope'] != DIAGNOSTIC_HOST_SCOPE or observed['policy_id'] != policy['policy_id']
            or any(observed[name] is not False for name in
                   ('production_eligible', 'native_engine_execution', 'kernel_rebuild'))):
        raise ValueError('Diagnostic original scope/policy/ineligible flags differ')
    _diagnostic_ownership(observed['ownership'])
    subjects = observed['subjects']
    _fields(subjects, ('programs', 'inventory_documents', 'interpreter_facts'), 'diagnostic original subjects')
    _diagnostic_subjects(subjects['programs'], host['programs'], observations_ref['path'], 'diagnostic subject programs')
    if subjects['programs'] != host['programs']:
        raise ValueError('Diagnostic subject program map differs from exact admitted host programs')
    _fields(subjects['inventory_documents'], ('sdk', 'extensions'), 'diagnostic subject inventories')
    _fields(subjects['inventory_documents']['sdk'], ('root', 'manifest_sha256'), 'diagnostic original SDK subject')
    if subjects['inventory_documents']['sdk'] != {
            'root': str(_diagnostic_absolute(binding['root'])), 'manifest_sha256': binding['sdk_manifest_sha256']}:
        raise ValueError('Diagnostic subject SDK root/manifest differs from original admission')
    extensions = subjects['inventory_documents']['extensions']
    if type(extensions) is not dict or set(extensions) != {'host-' + name for name in host['module_inventories']}:
        raise ValueError('Diagnostic subject extension aliases differ from complete admitted host inventories')
    for name, admitted in host['module_inventories'].items():
        item = extensions['host-' + name]
        _fields(item, ('root', 'inventory'), 'diagnostic subject extension')
        if (item['root'] != admitted['root'] or
                _diagnostic_reference(item['inventory'], observed_base) !=
                _diagnostic_reference(value['module_inventories'][name]['inventory'], base)):
            raise ValueError('Diagnostic extension root/normalized metadata reference differs from admission')
    _fields(subjects['interpreter_facts'], ('python', 'perl', 'ruby'), 'diagnostic subject interpreter facts')
    for role in ('python', 'perl', 'ruby'):
        if (_diagnostic_reference(subjects['interpreter_facts'][role], observed_base) !=
                _diagnostic_reference(value['interpreter_bindings'][role], base)):
            raise ValueError('Diagnostic original interpreter reference differs from base admitted facts')
    original_host = observed['host']
    _fields(original_host, ('system', 'processor', 'distribution', 'os_release', 'libc'), 'diagnostic execution host')
    expected_host = policy['execution_host']
    if {name: original_host[name] for name in ('system', 'processor', 'distribution', 'libc')} != expected_host:
        raise ValueError('Diagnostic observed host differs from the exact execution-host policy')
    _, os_release = _diagnostic_raw(original_host['os_release'], observed_base, inputs,
                                     'diagnostic-provenance-os-release', 65536)
    if _diagnostic_os_release(os_release) != expected_host['distribution']:
        raise ValueError('Diagnostic original os-release contradicts its declared host/policy')

    # Every non-SDK program needs one unambiguous retained derivation. Copies
    # whose only terminal evidence is source-copy equality fail with MissingInputs.
    sdk = toolchain['inventories']['sdk']
    for role, program in host['programs'].items():
        program_path = Path(program['path'])
        if Path(sdk['root']) in program_path.parents:
            member = program_path.relative_to(sdk['root']).as_posix()
            if sdk['files'].get(member) == program['sha256'] and sdk['modes'].get(member) == 0o755:
                continue
        matches = [fact for fact in origins.cache.values() if fact['path'] == program['path']]
        if not matches:
            raise MissingInputs([{'role': 'diagnostic-original-program-origin', 'path': program['path'],
                'reason': 'non-SDK program lacks its exact separately retained original derivation'}])
        if len(matches) != 1 or matches[0]['sha256'] != program['sha256'] or matches[0]['mode'] != 0o755:
            raise ValueError('Diagnostic program has contradictory or ambiguous retained origin')
        if role7 is None or matches[0]['terminal'] != 'os-original':
            _diagnostic_terminal_authority(matches[0], 'diagnostic-original-program-authority', program['path'])
        if matches[0].get('alias') is not None and (role7 is None or matches[0]['terminal'] != 'os-original'):
            raise MissingInputs([{'role': 'diagnostic-original-program-alias', 'path': program['path'],
                'reason': 'copied package executable alias lacks an explicit observed source-path mapping'}])

    runtime = observed['runtime']
    _fields(runtime, ('providers', 'modules', 'loaded_by_subject'), 'diagnostic runtime')
    providers = _diagnostic_map(runtime['providers'], 'diagnostic runtime providers')
    provider_values, provider_facts, provider_origins = {}, {}, {}
    retained_paths, resolved_paths = set(), set()
    for name, item in providers.items():
        normalized, retained, origin = _diagnostic_provider(item, origins, 'provider')
        if retained['path'] in retained_paths or normalized['resolved_path'] in resolved_paths:
            raise ValueError('Diagnostic providers have competing retained/resolved selections')
        retained_paths.add(retained['path'])
        resolved_paths.add(normalized['resolved_path'])
        provider_values[name], provider_facts[name], provider_origins[name] = normalized, retained, origin
    _fields(runtime['modules'], ('python', 'perl', 'ruby'), 'diagnostic interpreter modules')
    module_values, module_facts, all_modules, module_paths = {}, {}, {}, set()
    for role in ('python', 'perl', 'ruby'):
        module_values[role] = {}
        facts = host['interpreter_runtimes'][role]
        for name, item in _diagnostic_map(runtime['modules'][role], 'diagnostic interpreter module').items():
            if name in all_modules:
                raise ValueError('Diagnostic module IDs must be unique across all interpreters')
            normalized, retained, _ = _diagnostic_provider(item, origins, 'module')
            if retained['inventory'] not in facts['runtime_inventories']:
                raise ValueError('Diagnostic module lies outside its interpreter retained runtime closure')
            if normalized['resolved_path'] in module_paths:
                raise ValueError('Diagnostic modules have ambiguous resolved source paths')
            module_paths.add(normalized['resolved_path'])
            module_values[role][name], module_facts[name], all_modules[name] = normalized, retained, role
    loaded = runtime['loaded_by_subject']
    _diagnostic_subjects(loaded, host['programs'], observations_ref['path'], 'diagnostic loaded subject map')
    used_providers, used_modules = set(), set()
    for role, item in loaded.items():
        _fields(item, ('providers', 'modules'), 'diagnostic subject loaded selection')
        pids = _diagnostic_ids(item['providers'], 'diagnostic subject provider IDs')
        mids = _diagnostic_ids(item['modules'], 'diagnostic subject module IDs')
        if not set(pids) <= set(providers) or not set(mids) <= set(all_modules):
            raise ValueError('Diagnostic subject selects an unknown provider/module')
        if mids and (role not in ('python', 'perl', 'ruby') or any(all_modules[name] != role for name in mids)):
            raise ValueError('Diagnostic subject selects modules outside its admitted interpreter role')
        used_providers.update(pids)
        used_modules.update(mids)
    if used_providers != set(providers) or used_modules != set(all_modules):
        raise ValueError('Diagnostic runtime contains unobserved provider/module padding')
    roots = [Path(item['root']) for item in combined.values()]
    os_providers = {name: item for name, item in providers.items() if item['origin']['kind'] != 'sdk'
        and not any(Path(item['resolved_path']) == root or root in Path(item['resolved_path']).parents for root in roots)}
    if wrapper['operating_system_providers'] != os_providers:
        raise ValueError('Diagnostic OS-provider subset differs from exact observed non-SDK source-path selection')

    commands = observed['commands']
    _fields(commands, ('host', 'subjects'), 'diagnostic original command map')
    _diagnostic_subjects(commands['subjects'], host['programs'], observations_ref['path'], 'diagnostic original subject commands')
    environment = _diagnostic_environment(toolchain, host)
    prefix = [host['programs']['python']['path'], '-I', '-B', observer['path']]
    raw_host, first, last = _diagnostic_command(commands['host'], prefix + ['--observe-host'],
        environment, observed_base, inputs, 'host')
    _schema(raw_host, ('schema_version', 'kind', 'host', 'libc_provider', 'loader_provider'),
            'foundation-native-diagnostic-host-raw-v1')
    if raw_host['host'] != expected_host:
        raise ValueError('Diagnostic original host stdout contradicts host/policy')
    selected_os = [raw_host['libc_provider'], raw_host['loader_provider']]
    if (any(type(name) is not str for name in selected_os) or len(set(selected_os)) != 2
            or any(name not in os_providers for name in selected_os)):
        raise ValueError('Diagnostic original libc/loader proof must name two exact observed OS providers')
    if any(provider_origins[name]['terminal'] == 'sdk' for name in selected_os):
        raise ValueError('SDK-origin target runtime bytes cannot establish observed host libc/loader providers')
    for role, program in host['programs'].items():
        raw, started, finished = _diagnostic_command(commands['subjects'][role],
            prefix + ['--observe-subject', role, '--program', program['path']], environment,
            observed_base, inputs, 'subject-' + role)
        first, last = min(first, started), max(last, finished)
        _schema(raw, ('schema_version', 'kind', 'role', 'program', 'search_paths', 'loaded_module_paths',
                     'loaded_provider_paths'), 'foundation-native-diagnostic-subject-raw-v1')
        search = host['interpreter_runtimes'][role]['search_paths'] if role in ('python', 'perl', 'ruby') else []
        expected_modules = sorted(module_values[role][name]['resolved_path'] for name in loaded[role]['modules']) if role in module_values else []
        expected_providers = sorted(provider_values[name]['resolved_path'] for name in loaded[role]['providers'])
        if (raw['role'] != role or raw['program'] != program or raw['search_paths'] != search
                or raw['loaded_module_paths'] != expected_modules or raw['loaded_provider_paths'] != expected_providers):
            raise ValueError('Diagnostic original subject stdout contradicts exact program/search/loaded retained selections: ' + role)
    if not first <= _diagnostic_time(observed['observed_utc']) <= last:
        raise ValueError('Diagnostic observation timestamp lies outside the retained original command interval')
    if role7 is not None:
        role7.validate(_diagnostic_role7_api(), observed, observed_base, wrapper, provenance_base,
            inputs, host, toolchain, origins, role7_records)
    inputs.check_deadline()
    return {'observations': observations_ref, 'provenance': provenance_ref,
        'policy': policy, 'policy_sha256': DIAGNOSTIC_HOST_POLICY_SHA256,
        'host': _json_copy(original_host),
        'runtime': {'providers': provider_values, 'modules': module_values, 'loaded_by_subject': _json_copy(loaded)},
        'environment': environment,
        'external_inventories': _diagnostic_external_inventories(original['external_inventories'])}


def _interpreter_modules(files, module_groups, label, *, external=False):
    for options in module_groups:
        if not any(name == suffix or name.endswith('/' + suffix) for suffix in options for name in files):
            raise ValueError('Required ' + label + ' module absent from ' +
                ('named complete runtime inventories: ' if external else 'complete inventory: ') + options[0])


def _interpreter_runtime_facts(facts, program, combined_inventories, module_groups,
                               *, required_inventory=None, external=False):
    """Original captured interpreter facts, normalized data rather than authority.

    The caller captures the executable with _program and applies its role's
    version minimum before calling. This function neither captures nor executes
    programs, chooses a target, or supplies an SDK/host admission shortcut.
    """
    if type(external) is not bool or type(combined_inventories) is not dict:
        raise ValueError('Explicit captured interpreter inventory context required')
    if (type(module_groups) not in (tuple, list) or not module_groups or len(module_groups) > 64
            or any(type(group) not in (tuple, list) or not group or len(group) > 16
                or any(type(name) is not str for name in group) for group in module_groups)):
        raise ValueError('Explicit bounded interpreter module groups required')
    for group in module_groups:
        for name in group:
            _name(name)
    # Preserve the existing role-specific error labels for the unchanged groups.
    label = {'English.pm': 'perl', 'json/__init__.py': 'python', 'json.rb': 'ruby'}.get(
        module_groups[0][0], 'interpreter')
    _schema(facts, ('schema_version', 'kind', 'program_sha256', 'search_paths', 'runtime_inventories'),
            'foundation-native-host-interpreter-runtime-v1')
    _fields(program, ('path', 'sha256', 'version'), 'captured interpreter program')
    _absolute(program['path'])
    pin(program['sha256'], 'captured interpreter program')
    _text(program['version'], 'captured interpreter version')
    if facts['program_sha256'] != program['sha256']:
        raise ValueError('Original interpreter runtime facts bind another executable')
    names = facts['runtime_inventories']
    if (type(names) is not list or any(type(name) is not str for name in names)
            or names != sorted(set(names)) or not names or len(names) > 64
            or not set(names) <= set(combined_inventories)
            or not external and (type(required_inventory) is not str or required_inventory not in names)):
        raise ValueError('Original interpreter runtime must name its complete admitted inventories')
    if external:
        program_path = _absolute(program['path'])
        if not any(Path(combined_inventories[name]['root']) in program_path.parents
                and combined_inventories[name]['files'].get(program_path.relative_to(
                    combined_inventories[name]['root']).as_posix()) == program['sha256']
                and combined_inventories[name]['modes'].get(program_path.relative_to(
                    combined_inventories[name]['root']).as_posix()) == 0o755 for name in names):
            raise ValueError('External interpreter runtime omits its exact program-owning inventory')
        files = {name for key in names for name in combined_inventories[key]['files']}
    else:
        files = combined_inventories[required_inventory]['files']
    _interpreter_modules(files, module_groups, label, external=external)
    searches = facts['search_paths']
    if (type(searches) is not list or not searches or any(type(name) is not str for name in searches)
            or searches != sorted(set(searches))):
        raise ValueError('Explicit sorted original interpreter module search paths required')
    for name in searches:
        search = _ordinary(_absolute(name), True)
        if not any(search == Path(combined_inventories[key]['root'])
                or Path(combined_inventories[key]['root']) in search.parents and search.relative_to(
                    combined_inventories[key]['root']).as_posix() in combined_inventories[key]['directories']
                for key in names):
            raise ValueError('Interpreter module search path is outside its complete admitted inventories')
    return _json_copy(facts)


def parse_host_tools(value, base, inputs, toolchain, *, repository_root=ROOT):
    diagnostic_kind = type(value) is dict and value.get('kind') == DIAGNOSTIC_HOST_KIND
    sdk_kind = diagnostic_kind or type(value) is dict and value.get('kind') == 'foundation-native-engine-prototype-sdk-host-tools-v1'
    kind = (DIAGNOSTIC_HOST_KIND if diagnostic_kind else 'foundation-native-engine-prototype-sdk-host-tools-v1'
            if sdk_kind else 'foundation-native-engine-prototype-host-tools-v1')
    fields = ('schema_version', 'kind', 'programs', 'module_inventories')
    _schema(value, fields + (('interpreter_bindings',) if sdk_kind else ()) +
            (('diagnostic_host', 'source_provenance') if diagnostic_kind else ()), kind)
    if sdk_kind and (toolchain.get('kind') not in ('foundation-native-engine-prototype-sdk-toolchain-v1', PRIVATE_TOOLCHAIN_KIND)
            or 'sdk_binding' not in toolchain or 'sdk' not in toolchain['inventories']):
        raise ValueError('External SDK interpreter facts require an admitted SDK-backed toolchain')
    if sdk_kind and value != toolchain['sdk_binding'].get('host_document'):
        raise ValueError('SDK host tools differ from the original admitted host manifest')
    programs = value['programs']
    if type(programs) is not dict or not HOST_REQUIRED <= set(programs) <= HOST_ALLOWED:
        raise ValueError('Explicit native host generators/utilities required; unknown program role')
    inventories = value['module_inventories']
    if (type(inventories) is not dict or not (0 if sdk_kind else 3) <= len(inventories) <= 32
            or not sdk_kind and not {'python', 'ruby', 'perl'} <= set(inventories)):
        raise ValueError('Explicit complete Python/Ruby/Perl module inventories required')
    diagnostic_preflight = (_diagnostic_host_preflight(value, base, inputs, toolchain,
                                                     repository_root=repository_root)
                            if diagnostic_kind else None)
    admitted = {}
    for name, item in sorted(inventories.items()):
        if '/' in _name(name):
            raise ValueError('Host inventory name must be one component')
        admitted[name] = inputs.inventory(item, base, 'host-' + name)
    combined = dict(toolchain['inventories'])
    if sdk_kind and set(combined) & {'host-' + name for name in admitted}:
        raise ValueError('Host inventory names cannot replace admitted SDK/toolchain roots')
    combined.update({'host-' + name: record for name, record in admitted.items()})
    programs = {name: _program(item, combined, inputs, 'host-program-' + name) for name, item in programs.items()}
    for name in ('cmake', 'ninja'):
        if programs[name] != toolchain['tools'][name]:
            raise ValueError('Native host/toolchain tool disagreement: ' + name)
    _version(programs['python']['version'], (3, 9, 0), 'Python')
    _version(programs['perl']['version'], (5, 10, 0), 'Perl')
    _version(programs['ruby']['version'], (2, 5, 0), 'Ruby')
    _version(programs['gperf']['version'], (3, 0, 1), 'gperf')
    required = {'perl': (('English.pm',), ('FindBin.pm',), ('JSON/PP.pm',)),
        'python': (('json/__init__.py',), ('hashlib.py',), ('pathlib.py', 'pathlib/__init__.py')),
        'ruby': (('json.rb',), ('fileutils.rb',))}
    runtimes = {}
    if sdk_kind:
        _fields(value['interpreter_bindings'], ('python', 'perl', 'ruby'), 'external original interpreter facts')
    for role, groups in required.items():
        if sdk_kind:
            facts = inputs.document(value['interpreter_bindings'][role], base, 'host-runtime-facts')
        else:
            files = admitted[role]['files']
            _interpreter_modules(files, groups, role)
            if 'interpreter-runtime.json' not in files:
                raise ValueError('Original ' + role + ' interpreter search/runtime facts required')
            runtime_path = Path(admitted[role]['root']) / 'interpreter-runtime.json'
            inputs.file(runtime_path, files['interpreter-runtime.json'], 'host-runtime-facts', maximum=MAX_DOCUMENT)
            facts = strict_json(inputs.bytes(runtime_path), 'original interpreter runtime')
        facts = _interpreter_runtime_facts(facts, programs[role], combined, groups,
            required_inventory='host-' + role, external=sdk_kind)
        if sdk_kind:
            runtimes[role] = facts
        else:
            admitted[role]['runtime'] = facts
    result = dict(value, programs=programs, module_inventories=admitted)
    if sdk_kind:
        result['interpreter_runtimes'] = runtimes
    if diagnostic_kind:
        policy_path = _absolute(repository_root) / DIAGNOSTIC_HOST_POLICY
        try:
            policy_raw = _producer_bytes(inputs, policy_path, 'native-producer-diagnostic-host-policy',
                                         _absolute(repository_root))
        except FileNotFoundError as error:
            raise MissingInputs([{'role': 'diagnostic-host-policy', 'path': str(policy_path),
                'reason': 'exact diagnostic host producer policy absent'}]) from error
        result['diagnostic'] = validate_diagnostic_host(value, base, inputs, toolchain, result,
            policy_raw=policy_raw, _preflight=diagnostic_preflight, repository_root=repository_root)
    return result


def _notice(ref, base, inputs, role):
    path, sha = _ref(ref, base)
    inputs.file(path, sha, role, maximum=MAX_DOCUMENT)
    return {'path': str(path), 'sha256': sha}


def parse_assets(value, base, inputs, target):
    validate_target(target)
    _schema(value, ('schema_version', 'kind', 'fonts', 'font_config', 'icu_data', 'ca_bundle', 'notices',
        'initialization'), 'foundation-native-engine-prototype-assets-v1')
    if type(value['initialization']) is not dict or type(value['initialization'].get('network')) is not bool or value['initialization'] != {'policy': 'explicit-retained-assets-only', 'font_search': 'retained-only',
            'icu_search': 'retained-only', 'network': False}:
        raise ValueError('Native assets must have explicit retained-only initialization')
    if type(value['fonts']) is not list or not 1 <= len(value['fonts']) <= 64:
        raise ValueError('Explicit retained fonts required')
    notices = set()
    def asset(item, role):
        _fields(item, ('path', 'sha256', 'bytes', 'mode', 'origin', 'notice'), role + ' asset')
        _fields(item['origin'], ('repository', 'revision'), 'asset origin')
        for name, child in item['origin'].items():
            _text(child, 'asset origin ' + name)
        manifest.integer(item['bytes'], 'asset bytes', 1, MAX_FILE)
        if type(item['mode']) is not int or item['mode'] != 0o644:
            raise ValueError('Native assets must be ordinary 0644 files')
        path = Path(base) / _name(item['path'])
        record = inputs.file(path, pin(item['sha256'], role), role)
        if record['bytes'] != item['bytes'] or record['mode'] != item['mode']:
            raise ValueError('Native asset differs from explicit byte/mode facts')
        notice = _notice(item['notice'], base, inputs, role + '-notice')
        notices.add((notice['path'], notice['sha256']))
        return dict(item, path=str(path), notice=notice)
    result = dict(value)
    result['fonts'] = [asset(item, 'font') for item in value['fonts']]
    if len({item['path'] for item in result['fonts']}) != len(result['fonts']):
        raise ValueError('Duplicate retained font')
    for name in ('font_config', 'icu_data', 'ca_bundle'):
        result[name] = asset(value[name], name)
    if type(value['notices']) is not list or not value['notices'] or len(value['notices']) > 128:
        raise ValueError('Exact native asset notices required')
    actual = [_notice(ref, base, inputs, 'asset-notice') for ref in value['notices']]
    if len(actual) != len({(item['path'], item['sha256']) for item in actual}) or set(
            (item['path'], item['sha256']) for item in actual) != notices:
        raise ValueError('Native assets notices must exactly cover distinct asset notices')
    result['notices'] = actual
    return result


def parse_dependencies(value, base, inputs, target, toolchain, assets_ref):
    _schema(value, ('schema_version', 'kind', 'target', 'toolchain_identity_sha256', 'prefix', 'inventory',
        'build_provenance', 'libraries', 'pkg_config', 'assets', 'notices', 'windows_inputs'),
        'foundation-native-engine-prototype-dependencies-v1')
    if (value['target'] != validate_target(target) or value['toolchain_identity_sha256'] != toolchain['identity']['identity_sha256']
            or value['windows_inputs'] is not None):
        raise ValueError('Native dependencies must match selected native target/toolchain and Linux policy')
    prefix = inputs.inventory({'root': value['prefix'], 'inventory': value['inventory']}, base, 'native-prefix')
    if not isinstance(assets_ref, dict) or set(assets_ref) != {'path', 'sha256'}:
        raise ValueError('Selected independently pinned assets reference required')
    asset_path, asset_pin = _ref(value['assets'], base)
    inputs.file(asset_path, asset_pin, 'dependency-assets-manifest', maximum=MAX_DOCUMENT)
    if asset_pin != pin(assets_ref['sha256'], 'selected assets'):
        raise ValueError('Native dependency assets differ from selected retained assets bytes')
    if type(value['build_provenance']) is not list or not 1 <= len(value['build_provenance']) <= 256:
        raise ValueError('Original native dependency build/source provenance must be retained')
    provenance = [_notice(ref, base, inputs, 'native-dependency-original-provenance') for ref in value['build_provenance']]
    if type(value['libraries']) is not dict or set(value['libraries']) != LIBRARIES:
        raise ValueError('Native dependency targets must exactly cover the reviewed static closure')
    libraries = {}
    root = Path(prefix['root'])
    archive_cache = {}
    for name, item in sorted(value['libraries'].items()):
        inputs.check_deadline()
        _fields(item, ('archive', 'sha256', 'includes', 'definitions', 'links', 'inspection'), name + ' native library')
        archive_name = _name(item['archive'])
        archive = root / archive_name
        if prefix['files'].get(archive_name) != pin(item['sha256'], name):
            raise ValueError('Native archive is not an exact inventoried prefix file: ' + name)
        _names(item['includes'], name + ' include directories', True)
        for directory in item['includes']:
            if directory not in prefix['directories']:
                raise ValueError('Native include directory is not an inventoried prefix directory')
        definitions = item['definitions']
        if type(definitions) is not list or any(type(child) is not str for child in definitions) or definitions != sorted(set(definitions)) or len(definitions) > 128 or any(
                not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:=[A-Za-z0-9_.+-]{1,128})?', child) for child in definitions):
            raise ValueError('Native dependency definitions must be bounded scalar macros')
        links = item['links']
        if type(links) is not list or any(type(link) is not str for link in links) or links != sorted(set(links)) or any(link not in LIBRARIES | SYSTEM_LINKS or link == name for link in links):
            raise ValueError('Native dependency links must name explicit closed targets/system libraries')
        if name == 'WebP::libwebp' and 'WebP::sharpyuv' not in links:
            raise ValueError('Static WebP requires its explicit same-source sharpyuv closure')
        if archive_name not in archive_cache:
            facts = inspect_static_archive(archive, deadline=inputs.deadline)
            if facts['sha256'] != item['sha256']:
                raise ValueError('Native dependency archive changed during actual object inspection')
            archive_cache[archive_name] = facts
        report = inputs.document(item['inspection'], base, name + '-original-inspection')
        _schema(report, ('schema_version', 'kind', 'target', 'toolchain_identity_sha256', 'archive_sha256',
            'format', 'pic', 'runtime', 'commands'), 'foundation-native-dependency-archive-inspection-v1')
        if (report['target'] != target or report['toolchain_identity_sha256'] != value['toolchain_identity_sha256']
                or report['archive_sha256'] != item['sha256'] or report['format'] != 'elf64-x86_64-ar'
                or report['pic'] is not True or report['runtime'] != toolchain['runtime']):
            raise ValueError('Original dependency inspection facts do not bind selected bytes/target/runtime')
        commands = report['commands']
        if type(commands) is not list or not 1 <= len(commands) <= 64:
            raise ValueError('Original dependency inspection commands/logs required')
        inspection_path, _ = _ref(item['inspection'], base)
        for command in commands:
            _fields(command, ('tool_sha256', 'argv', 'exit_code', 'log'), 'original dependency inspection command')
            if command['tool_sha256'] != toolchain['tools']['inspect']['sha256']:
                raise ValueError('Original native inspection uses a different admitted inspector')
            if type(command['argv']) is not list or not 1 <= len(command['argv']) <= 256:
                raise ValueError('Original native inspection argv required')
            for argument in command['argv']:
                _text(argument, 'original inspection argument')
            if type(command['exit_code']) is not int or command['exit_code'] != 0:
                raise ValueError('Original native inspection command did not succeed')
            _notice(command['log'], inspection_path.parent, inputs, name + '-original-inspection-log')
        libraries[name] = dict(item, archive=str(archive), includes=[str(root / part) for part in item['includes']],
            inspection={'path': str(inspection_path), 'sha256': item['inspection']['sha256']},
            byte_inspection=archive_cache[archive_name])
    pkg = _fields(value['pkg_config'], ('directories', 'files'), 'native pkg-config closure')
    _names(pkg['directories'], 'native pkg-config directories', True)
    if type(pkg['files']) is not dict or not pkg['files']:
        raise ValueError('Explicit native pkg-config files required')
    for directory in pkg['directories']:
        if directory not in prefix['directories']:
            raise ValueError('pkg-config search directory is outside inventoried native prefix')
    for name, sha in pkg['files'].items():
        _name(name)
        if (not name.endswith('.pc') or prefix['files'].get(name) != pin(sha, name)
                or str(Path(name).parent).replace('\\', '/') not in pkg['directories']):
            raise ValueError('pkg-config file is not independently bound inside declared search directories')
    if {name for name in prefix['files'] if name.endswith('.pc')} != set(pkg['files']):
        raise ValueError('Native prefix has undeclared pkg-config inputs')
    if type(value['notices']) is not list or not value['notices']:
        raise ValueError('Original native dependency notices required')
    notices = [_notice(ref, base, inputs, 'native-dependency-notice') for ref in value['notices']]
    return dict(value, prefix=str(root), inventory=prefix, libraries=libraries, build_provenance=provenance,
        assets={'path': str(asset_path), 'sha256': asset_pin}, notices=notices,
        pkg_config={'directories': [str(root / name) for name in pkg['directories']], 'files': dict(pkg['files'])})


def _json_copy(value):
    return strict_json(encoded(value))


def _public(value):
    if type(value) is dict:
        return {key: _public(child) for key, child in value.items() if not key.startswith('_')}
    if type(value) is list:
        return [_public(child) for child in value]
    return value


def _producer_bytes(inputs, path, role, repository_root):
    """Bound current producer source before hashing its original exact bytes."""
    path = _ordinary(path)
    before = _identity(path.lstat())
    if before[4] > MAX_DOCUMENT:
        raise ValueError('Native producer source exceeds document byte bound')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        if _identity(os.fstat(stream.fileno())) != before:
            raise ValueError('Native producer source changed before bounded read')
        raw = stream.read(MAX_DOCUMENT + 1)
        after = _identity(os.fstat(stream.fileno()))
    if len(raw) != before[4] or after != before or _identity(path.lstat()) != before:
        raise ValueError('Native producer source changed during bounded read')
    inputs.repository_file(path, sha256(raw), role, repository_root=repository_root, source_paths=PRODUCERS)
    return raw


def _record_aliases(records):
    """Every original provenance record has a data alias, including notices."""
    aliases = []
    for item in records:
        roles = item['roles']
        if any('notice' in role for role in roles):
            aliases.append(('notices/retained/' + item['sha256'] + '.txt', Path(item['path']), 'license'))
        if any('inventory' in role or 'provenance' in role or 'inspection' in role for role in roles) or any(
                role in ('font', 'font_config', 'icu_data', 'ca_bundle', 'host-runtime-facts') for role in roles):
            aliases.append(('native-inputs/records/' + item['sha256'] + '.bin', Path(item['path']), 'data'))
    return aliases


def _forward_patch_contract(projection, source_entries):
    """Apply the supplier diff once; native postimages are exact final overlays."""
    mapped = [item['sha256'] for item in source_entries.values() if item['role'] == 'patch']
    patches = projection['patches']
    if (len(mapped) != 5 or len(set(mapped)) != 5 or mapped.count(SUPPLIER_PATCH) != 1
            or len(patches) != 1 or patches[0]['tree'] != 'engine' or patches[0]['sha256'] != SUPPLIER_PATCH):
        raise ValueError('Native forward patches must contain exactly one engine supplier patch; all five mapped patches remain provenance')
    before, after = patches[0]['preimages'], patches[0]['postimages']
    if (type(before) is not dict or type(after) is not dict or len(before) != 68 or set(before) != set(after)
            or sum(value is None for value in before.values()) != 23):
        raise ValueError('Supplier forward patch requires the original 45 modified and 23 added images')
    for name, digest in before.items():
        _name(name)
        pin(after[name], 'supplier forward postimage')
        member = projection['_files'].get('source/engine/' + name)
        if (digest is None and member is not None or digest is not None and
                (member is None or member['sha256'] != pin(digest, 'supplier clean preimage'))):
            raise ValueError('Supplier forward patch preimages require the clean original baseline')


@dataclass(frozen=True)
class Inspection:
    _data: dict
    _inputs: InputSet
    _retained: dict
    _projection: dict
    _overlays: dict
    _recipe_suppliers: dict
    _recipe_patches: list

    def as_dict(self):
        return _json_copy(self._data)

    def recheck(self):
        self._inputs.recheck()

    @property
    def protected_paths(self):
        return self._inputs.protected_paths

    @property
    def programs(self):
        return _json_copy(self._data['programs'])

    @property
    def environment(self):
        return dict(self._data['environment'])

    @property
    def needed_libraries(self):
        return list(self._data['needed_libraries'])

    @property
    def phase_limits(self):
        return dict(self._data['phase_limits'])

    @property
    def cmake(self):
        tools = self._data['toolchain']['tools']
        host = self._data['host_tools']['programs']
        result = {'CMAKE_TOOLCHAIN_FILE': self._data['toolchain']['toolchain_file']}
        for variable, role in (('CMAKE_C_COMPILER', 'c'), ('CMAKE_CXX_COMPILER', 'cxx'),
                ('CMAKE_LINKER', 'linker'), ('CMAKE_AR', 'archiver'), ('CMAKE_RANLIB', 'ranlib'),
                ('CMAKE_MAKE_PROGRAM', 'ninja'), ('PKG_CONFIG_EXECUTABLE', 'pkg_config')):
            result[variable] = tools[role]['path']
        for variable, role in (('PERL_EXECUTABLE', 'perl'), ('Python_EXECUTABLE', 'python'),
                ('Ruby_EXECUTABLE', 'ruby'), ('GPERF_EXECUTABLE', 'gperf')):
            result[variable] = host[role]['path']
        prefix = self._data['dependencies']['prefix']
        result.update({'FOUNDATION_NATIVE_DEPENDENCY_PREFIX': prefix,
            'FOUNDATION_NATIVE_DEPENDENCY_TARGET': 'linux-x86_64',
            'BIB_NATIVE_PROVIDER_DEPENDENCY_PREFIX': prefix, 'BIB_NATIVE_PROVIDER_DEPENDENCY_TARGET': 'linux-x86_64'})
        runtime = self._data['toolchain'].get('private_runtime')
        if runtime is not None:
            result.update(runtime['cmake'])
        return result


# Explicit source-only successor; final native source facts stay unbound until release.
COMPOSITION_SOURCE_KIND = 'foundation-native-engine-actions-composition-undo-source-inputs-v1'
COMPOSITION_PROFILE_KIND = 'foundation-native-engine-prototype-composition-undo-profile-v1'
COMPOSITION_BRIDGE = 'source/wrapper/src/embedder/BibEngineProviderCompositionUndo.h'
COMPOSITION_SOURCE_FACTS = {'source/document-provider/editor/BibNativeEditorBackend.cpp': {'sha256': 'd14dab28100d3689d9a04aa4a81290b50cf24cd3e00a34b2f8402d9eeca9da60', 'bytes': 61375, 'mode': 420}, 'source/wrapper/src/embedder/main.cpp': {'sha256': '3c2c7beb2b582ab91fb8174aa7d5f6022ce1a4b29ec66918674f9f13fadd88ac', 'bytes': 48346, 'mode': 420}, 'source/wrapper/src/embedder/BibPageClients.h': {'sha256': '6e77e9b1b47cc5e4e3d2a5dcd7600ea959c4b22eb95c763165c4ccc3c5d28a43', 'bytes': 29858, 'mode': 420}, 'source/wrapper/src/embedder/BibUndoHistory.h': {'sha256': 'f6ca9055367085abe855a19b0d047034279dff1beb7dc44c8c2ab78001d602bb', 'bytes': 9317, 'mode': 420}, 'source/wrapper/src/embedder/BibEngineProviderCompositionUndo.h': {'sha256': '1572b86481c93b9568c781ababc9f6645f505a038704f91236192e31a4208118', 'bytes': 592, 'mode': 420}}
COMPOSITION_NAMESPACE_SHA256 = '786fd3a2c417370bc0dae92bae552c5c7a80ba0adf6dfa67ef88ad5ffcf15812'
COMPOSITION_RETAINED_SHA256 = '436136c1f85dfa38608f6852bce7192cb8d89e8e03d84e85e00d6a95322d8af8'
COMPOSITION_PREDECESSORS = {'source/document-provider/editor/BibNativeEditorBackend.cpp': {'current_sha256': '5fe5f78c031cb50b83b40aed998a02a765045fdd111dba1ea7f76950f8ab1815', 'record_sha256': '936d83294fe9561a8822c1d49c7ea35768125aa5b20dc4d069c662059327181d'}, 'source/wrapper/src/embedder/BibPageClients.h': {'current_sha256': 'cd5775db97976fc01d8f457474d41cbafd3ae2895efbd0a3dff49bbfe2e8f3d2', 'record_sha256': '9b8de546a2822ac27dc540bb14eb7e931af06fde1048b1793a96611ce5c01ffe'}, 'source/wrapper/src/embedder/BibUndoHistory.h': {'current_sha256': 'eda850a3b35353dc47be20f85fe16bff55058aaf83610ee0c96a7ffda5c369f2', 'record_sha256': '72ff0df8f1a13f52d18c06483492eb305f4884750eea14af7dd26c3428e4ee2d'}, 'source/wrapper/src/embedder/main.cpp': {'current_sha256': '4cb8131b86f6bf1ede303053b7aa1752fab16dd66fe8b0271f97d256e0cd137b', 'record_sha256': '590cea1e6c33f40e7e00d2e6d8a7a7727da0436130b2537fa6fa3484a104fd74'}}


def composition_catalogue_counts(value):
    """Admit only the exact released one-header successor, never a count range."""
    if type(COMPOSITION_SOURCE_FACTS) is not dict:
        raise ValueError('Composition source successor facts remain unbound')
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    if (type(value) is not dict or set(value) != fields or type(value['schema_version']) is not int
            or value['schema_version'] != 1 or value['kind'] != COMPOSITION_SOURCE_KIND
            or value['scope'] != 'native-actions-source-candidate-only' or value['profile'] != 'actions'):
        raise ValueError('Exact composition source successor version required')
    entries = value['inputs']
    known = set(COMPOSITION_PREDECESSORS) | {COMPOSITION_BRIDGE}
    if type(entries) is not dict or len(entries) != 198 or set(COMPOSITION_SOURCE_FACTS) != known:
        raise ValueError('Composition successor requires exact198 entries/five source pins')
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    if hashed(sorted(entries)) != COMPOSITION_NAMESPACE_SHA256:
        raise ValueError('Composition source successor namespace differs')
    retained = {k: v for k, v in entries.items() if k.startswith('source/') and k not in known}
    if len(retained) != 153 or hashed(retained) != COMPOSITION_RETAINED_SHA256:
        raise ValueError('Unchanged153 native source rows differ')
    for logical in known:
        item = entries[logical]
        expected = COMPOSITION_SOURCE_FACTS[logical]
        if (type(expected) is not dict or set(expected) != {'sha256', 'bytes', 'mode'}
                or type(expected['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', expected['sha256'])
                or type(expected['bytes']) is not int or not 0 < expected['bytes'] <= 8388608
                or type(expected['mode']) is not int or expected['mode'] != 420):
            raise ValueError('Final composition source pins required')
        if (type(item) is not dict or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
                or item['tracked_path'] != RECIPE + '/' + logical or item['role'] != 'source'
                or any(type(item[k]) is not type(expected[k]) or item[k] != expected[k] for k in expected)):
            raise ValueError('Released composition source fact differs')
        origin = item['origin']
        if type(origin) is not dict or set(origin) != {'kind', 'record'} or type(origin['record']) is not dict:
            raise ValueError('Explicit native source successor record required')
        record = origin['record']
        if type(record.get('after_bytes')) is not int or type(record.get('bytes')) is not int:
            raise ValueError('Native source record byte counts require strict integers')
        if logical == COMPOSITION_BRIDGE:
            wanted = {'action': 'new-private-source-header', 'selection': 'source-only-addition',
                'origin': 'reviewed-source-only-composition-undo-private-bridge', 'origin_path': item['tracked_path'],
                'source': logical, 'preimage_sha256': None, 'sha256': expected['sha256'], 'bytes': expected['bytes'],
                'after_sha256': expected['sha256'], 'after_bytes': expected['bytes'], 'mode': expected['mode']}
            if origin['kind'] != 'reviewed-source-only-composition-undo-private-bridge' or record != wanted:
                raise ValueError('Bridge cannot claim historical compiled/capsule origin')
        else:
            if origin['kind'] != 'mapped-native-actions-runtime':
                raise ValueError('Native adapted predecessor origin differs')
            successor = record.get('successor')
            if type(successor) is not dict or set(successor) != {'kind', 'correction', 'sha256', 'source_path', 'source_only', 'supersedes'}:
                raise ValueError('Exact composition successor lineage required')
            prior = successor['supersedes']
            expected_prior = COMPOSITION_PREDECESSORS[logical]
            if (type(prior) is not dict or set(prior) != {'origin', 'sha256', 'tracked_path'}
                    or prior['sha256'] != expected_prior['current_sha256'] or prior['tracked_path'] != item['tracked_path']
                    or hashed(prior['origin']) != expected_prior['record_sha256']):
                raise ValueError('Native original/adapted predecessor was restamped')
            old = prior['origin']
            allowed = {'action', 'selection', 'after_sha256', 'after_bytes', 'successor'}
            if (set(record) != set(old) | allowed
                    or any(record.get(k) != v for k, v in old.items() if k not in allowed)
                    or record['after_sha256'] != expected['sha256'] or record['after_bytes'] != expected['bytes']
                    or successor['kind'] != 'reviewed-native-composition-cancel-inverse-repair'
                    or successor['correction'] != 'transaction-owned-native-composition-inverse-and-original-selection'
                    or successor['sha256'] != expected['sha256'] or successor['source_path'] != item['tracked_path']
                    or successor['source_only'] is not True):
                raise ValueError('Native current source must preserve its full historical origin')
    return {'source_files': 158, 'engine_files': 48, 'direct_translation_units': 32}



NATIVE_POPUP_SOURCE_KIND = 'foundation-native-engine-actions-native-popup-capability-source-inputs-v1'
NATIVE_POPUP_PROFILE_KIND = 'foundation-native-engine-prototype-native-popup-capability-profile-v1'
NATIVE_POPUP_REVIEWED_SOURCE_MAP = '969ca78d0594ba0aeb0191a676319c0f030aa47ae09a613e2f154439011b13e4'
NATIVE_POPUP_SOURCE_FACTS = {'source/document-provider/native/NativeDocumentV2Publisher.cpp': {'sha256': 'f0e6119409d960390e4bca8baaa11f766dfe6827b1f3723b190f638a92864770', 'bytes': 111163, 'mode': 420}, 'source/document-provider/native/NativeFormsV2Combined.cpp': {'sha256': 'c1cae92f150d65944c723c14755cf9bc87a58c64c6c8fe0a7c3fcf06542506aa', 'bytes': 41947, 'mode': 420}, 'source/document-provider/portable/NativeDocumentV2Types.cpp': {'sha256': 'c515fab6e801e2b0139130cdc7a5828b31156645f526914fb1edae74f8aab34f', 'bytes': 18228, 'mode': 420}, 'source/document-provider/popup/BibNativePopupOwner.cpp': {'sha256': '5d9657543b68ac4be23d14c5476f53e49fe8986a61d9a2c0c708b81bed9541f5', 'bytes': 32014, 'mode': 420}}
NATIVE_POPUP_PREDECESSOR_ROWS = {'source/document-provider/native/NativeDocumentV2Publisher.cpp': 'e9e2cb26deb0a0ebc29b8c08b83d3f50ead8503550d5d4ea9ef3d8a78473aeca', 'source/document-provider/native/NativeFormsV2Combined.cpp': 'feac42e5a1874c753db68434caeb192e8017a4de8d2aa24b80fde9ee5ecbdb62', 'source/document-provider/portable/NativeDocumentV2Types.cpp': '1ed46bae43d50f7c98d8931e2afa109bff88584d893cfd0916ac1d4072c14133', 'source/document-provider/popup/BibNativePopupOwner.cpp': '1a1aadb35428416969533aca798934fdf8b25daf2c5d5585c5be3f2f916ada8a'}
NATIVE_POPUP_NAMESPACE_SHA256 = '786fd3a2c417370bc0dae92bae552c5c7a80ba0adf6dfa67ef88ad5ffcf15812'
NATIVE_POPUP_RETAINED_SHA256 = 'c61e39b0ba259dc8b3d85d69a66bcc8fd311d6df42b9a8b49349687c05e88814'
NATIVE_POPUP_HEADER_SHA256 = '443c4774b2a6994ed83b9e71a6c8b4bdcdab5f6d12670657da428a8a4c2f0c8c'
NATIVE_POPUP_ENTRY_COUNT = 198
NATIVE_POPUP_PREDECESSOR_KIND = 'foundation-native-engine-actions-composition-undo-source-inputs-v1'

def native_popup_catalogue_predecessor(value):
    """Validate the exact source-only successor, preserving complete prior rows."""
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    if (type(value) is not dict or set(value) != fields or value['kind'] != NATIVE_POPUP_SOURCE_KIND
            or hashed({key: item for key, item in value.items() if key not in ('kind', 'inputs')}) != NATIVE_POPUP_HEADER_SHA256):
        raise ValueError('Exact native popup source successor version/header/bounds required')
    entries = value['inputs']
    if (type(NATIVE_POPUP_SOURCE_FACTS) is not dict or type(entries) is not dict
            or len(entries) != NATIVE_POPUP_ENTRY_COUNT
            or set(NATIVE_POPUP_SOURCE_FACTS) != set(NATIVE_POPUP_PREDECESSOR_ROWS)
            or hashed(sorted(entries)) != NATIVE_POPUP_NAMESPACE_SHA256):
        raise ValueError('Exact native popup source namespace and bound source pins required')
    retained = {name: row for name, row in entries.items() if name not in (*NATIVE_POPUP_SOURCE_FACTS, 'inspect_sources.py')}
    if hashed(retained) != NATIVE_POPUP_RETAINED_SHA256:
        raise ValueError('Unrelated native source/catalogue row changed')
    previous = dict(value, kind=NATIVE_POPUP_PREDECESSOR_KIND, inputs=dict(entries))
    for logical, expected in NATIVE_POPUP_SOURCE_FACTS.items():
        item = entries[logical]
        if (type(expected) is not dict or set(expected) != {'sha256', 'bytes', 'mode'}
                or type(expected['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', expected['sha256'])
                or type(expected['bytes']) is not int or not 0 < expected['bytes'] <= 8388608
                or type(expected['mode']) is not int or expected['mode'] != 420
                or type(item) is not dict or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
                or item['tracked_path'] != RECIPE + '/' + logical or item['role'] != 'source'
                or any(type(item[key]) is not type(expected[key]) or item[key] != expected[key] for key in expected)):
            raise ValueError('Exact released native popup source fact differs')
        origin = item['origin']
        wanted = {'kind': 'reviewed-native-popup-capability-successor',
            'correction': 'bounded-private-label-association-and-css-opaque-single-menu-popup',
            'source_only': True, 'source_path': item['tracked_path'], 'sha256': item['sha256'],
            'reviewed_source_map_sha256': NATIVE_POPUP_REVIEWED_SOURCE_MAP}
        if (type(origin) is not dict or set(origin) != set(wanted) | {'supersedes'}
                or any(type(origin[key]) is not type(expected_value) or origin[key] != expected_value
                       for key, expected_value in wanted.items())):
            raise ValueError('Native popup source-only lineage was restamped')
        prior = origin['supersedes']
        if (type(prior) is not dict or set(prior) != {'origin', 'sha256', 'bytes', 'tracked_path'}
                or type(prior['bytes']) is not int or prior['tracked_path'] != item['tracked_path']):
            raise ValueError('Native popup complete historical predecessor required')
        old = dict(item, **prior)
        if hashed(old) != NATIVE_POPUP_PREDECESSOR_ROWS[logical]:
            raise ValueError('Native popup prior source/origin/bytes/path was restamped')
        previous['inputs'][logical] = old
    return previous


def native_popup_catalogue_counts(value):
    """New source membership is finite; historical admission remains separate."""
    previous = native_popup_catalogue_predecessor(value)
    return composition_catalogue_counts(previous)



NATIVE_CONTROL_KEYPRESS_SOURCE_KIND = 'foundation-native-engine-actions-native-control-keypress-source-inputs-v1'
NATIVE_CONTROL_KEYPRESS_PROFILE_KIND = 'foundation-native-engine-prototype-native-control-keypress-profile-v1'
NATIVE_CONTROL_KEYPRESS_REVIEWED_SOURCE_MAP = '677fba2311553bafcbfb10317ad1a871b59bbe10223935cd6681a80af8d9e663'
NATIVE_CONTROL_KEYPRESS_SOURCE_FACTS = {'source/document-provider/physical/BibDocumentPhysicalProvider.cpp': {'sha256': 'ee79f3bc8488cfd92c9b62abc2e84a9c110221cf2eba805fac4803980bae612a', 'bytes': 30151, 'mode': 420}}
NATIVE_CONTROL_KEYPRESS_PREDECESSOR_ROWS = {'source/document-provider/physical/BibDocumentPhysicalProvider.cpp': 'c5d36dc2daf8f51b4f59e026f8afe541daa031e5e4e71b0fd4e644ebff24ab78'}
NATIVE_CONTROL_KEYPRESS_NAMESPACE_SHA256 = '786fd3a2c417370bc0dae92bae552c5c7a80ba0adf6dfa67ef88ad5ffcf15812'
NATIVE_CONTROL_KEYPRESS_RETAINED_SHA256 = 'db80bb0c25b72b82da43e9bba4bc02ff9b40843524b3bee3462ec5ab531c3716'
NATIVE_CONTROL_KEYPRESS_HEADER_SHA256 = '443c4774b2a6994ed83b9e71a6c8b4bdcdab5f6d12670657da428a8a4c2f0c8c'
NATIVE_CONTROL_KEYPRESS_PREDECESSOR_INSPECTOR = {'bytes': 23355, 'mode': 420, 'origin': {'kind': 'native-actions-source-recipe-input'}, 'role': 'helper', 'sha256': 'db00773f662b258d8082c0b1a0be5987bc329ddab644c81e1361e3e5bb2dfa27', 'tracked_path': 'recipes/webkitwasm-native-rich4083-v1/inspect_sources.py'}


def native_control_keypress_catalogue_predecessor(value):
    """Admit one source-only PhysicalProvider repair and reconstruct exact history."""
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    if (type(value) is not dict or set(value) != fields or value['kind'] != NATIVE_CONTROL_KEYPRESS_SOURCE_KIND
            or hashed({key: item for key, item in value.items() if key not in ('kind', 'inputs')}) != NATIVE_CONTROL_KEYPRESS_HEADER_SHA256):
        raise ValueError('Exact native control keypress source successor version/header/bounds required')
    entries = value['inputs']
    if (type(NATIVE_CONTROL_KEYPRESS_SOURCE_FACTS) is not dict or type(entries) is not dict
            or len(entries) != 198 or len(NATIVE_CONTROL_KEYPRESS_SOURCE_FACTS) != 1
            or set(NATIVE_CONTROL_KEYPRESS_SOURCE_FACTS) != set(NATIVE_CONTROL_KEYPRESS_PREDECESSOR_ROWS)
            or hashed(sorted(entries)) != NATIVE_CONTROL_KEYPRESS_NAMESPACE_SHA256):
        raise ValueError('Exact native control keypress namespace and one source pin required')
    retained = {name: row for name, row in entries.items() if name not in (*NATIVE_CONTROL_KEYPRESS_SOURCE_FACTS, 'inspect_sources.py')}
    if hashed(retained) != NATIVE_CONTROL_KEYPRESS_RETAINED_SHA256:
        raise ValueError('Unrelated native control keypress source/catalogue row changed')
    inspector = entries['inspect_sources.py']
    old_inspector = NATIVE_CONTROL_KEYPRESS_PREDECESSOR_INSPECTOR
    if (type(inspector) is not dict or set(inspector) != set(old_inspector)
            or any(inspector[key] != old_inspector[key] or type(inspector[key]) is not type(old_inspector[key])
                   for key in old_inspector if key not in ('sha256', 'bytes'))
            or type(inspector['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', inspector['sha256'])
            or type(inspector['bytes']) is not int or not 0 < inspector['bytes'] <= 1048576):
        raise ValueError('Native control keypress inspector identity/shape differs')
    previous = dict(value, kind=NATIVE_POPUP_SOURCE_KIND, inputs=dict(entries))
    previous['inputs']['inspect_sources.py'] = dict(old_inspector)
    for logical, expected in NATIVE_CONTROL_KEYPRESS_SOURCE_FACTS.items():
        item = entries[logical]
        if (type(expected) is not dict or set(expected) != {'sha256', 'bytes', 'mode'}
                or type(expected['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', expected['sha256'])
                or type(expected['bytes']) is not int or not 0 < expected['bytes'] <= 8388608
                or type(expected['mode']) is not int or expected['mode'] != 420
                or type(item) is not dict or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
                or item['tracked_path'] != RECIPE + '/' + logical or item['role'] != 'source'
                or any(type(item[key]) is not type(expected[key]) or item[key] != expected[key] for key in expected)):
            raise ValueError('Exact released native control keypress source fact differs')
        origin = item['origin']
        wanted = {'kind': 'reviewed-native-control-keypress-successor',
            'correction': 'trusted-cancelable-select-space-keypress-before-native-control-default',
            'source_only': True, 'source_path': item['tracked_path'], 'sha256': item['sha256'],
            'reviewed_source_map_sha256': NATIVE_CONTROL_KEYPRESS_REVIEWED_SOURCE_MAP}
        if (type(origin) is not dict or set(origin) != set(wanted) | {'supersedes'}
                or any(type(origin[key]) is not type(expected_value) or origin[key] != expected_value
                       for key, expected_value in wanted.items())):
            raise ValueError('Native control keypress source-only lineage was restamped')
        prior = origin['supersedes']
        if (type(prior) is not dict or set(prior) != {'origin', 'sha256', 'bytes', 'tracked_path'}
                or type(prior['bytes']) is not int or prior['tracked_path'] != item['tracked_path']):
            raise ValueError('Native control keypress complete historical predecessor required')
        old = dict(item, **prior)
        if hashed(old) != NATIVE_CONTROL_KEYPRESS_PREDECESSOR_ROWS[logical]:
            raise ValueError('Native control keypress prior source/origin/bytes/path was restamped')
        previous['inputs'][logical] = old
    raw = (json.dumps(previous, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    if hashlib.sha256(raw).hexdigest() != NATIVE_CONTROL_KEYPRESS_REVIEWED_SOURCE_MAP:
        raise ValueError('Exact native popup predecessor map reconstruction differs')
    return previous


def native_control_keypress_catalogue_counts(value):
    """Keep all older native popup/composition admission rules unchanged."""
    previous = native_control_keypress_catalogue_predecessor(value)
    return native_popup_catalogue_counts(previous)



NATIVE_CONTROL_INCLUDES_SOURCE_KIND = 'foundation-native-engine-actions-native-control-includes-source-inputs-v1'
NATIVE_CONTROL_INCLUDES_PROFILE_KIND = 'foundation-native-engine-prototype-native-control-includes-profile-v1'
NATIVE_CONTROL_INCLUDES_REVIEWED_SOURCE_MAP = '11208c13bce5e005526199a1922deed8b17259d93d0d892e35fdc6a8969bd9d0'
NATIVE_CONTROL_INCLUDES_SOURCE_FACTS = {'source/document-provider/physical/BibDocumentPhysicalProvider.cpp': {'sha256': '9d5d434c1af6109c7a007e67fcceccb48b5549339663ada3621736bcbeefde47', 'bytes': 30284, 'mode': 420}}
NATIVE_CONTROL_INCLUDES_PREDECESSOR_ROWS = {'source/document-provider/physical/BibDocumentPhysicalProvider.cpp': '4651168a729157104243af908843a8962f259ac96ef386d209a9dd340d9979c7'}
NATIVE_CONTROL_INCLUDES_NAMESPACE_SHA256 = '786fd3a2c417370bc0dae92bae552c5c7a80ba0adf6dfa67ef88ad5ffcf15812'
NATIVE_CONTROL_INCLUDES_RETAINED_SHA256 = 'db80bb0c25b72b82da43e9bba4bc02ff9b40843524b3bee3462ec5ab531c3716'
NATIVE_CONTROL_INCLUDES_HEADER_SHA256 = '443c4774b2a6994ed83b9e71a6c8b4bdcdab5f6d12670657da428a8a4c2f0c8c'
NATIVE_CONTROL_INCLUDES_PREDECESSOR_INSPECTOR = {'bytes': 30111, 'mode': 420, 'origin': {'kind': 'native-actions-source-recipe-input'}, 'role': 'helper', 'sha256': '764da93ad163ab57112679b687532e89ee4f7a541fb323c53e0745a74ece9d3c', 'tracked_path': 'recipes/webkitwasm-native-rich4083-v1/inspect_sources.py'}


def native_control_includes_catalogue_predecessor(value):
    """Admit one source-only PhysicalProvider repair and reconstruct exact history."""
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    if (type(value) is not dict or set(value) != fields or value['kind'] != NATIVE_CONTROL_INCLUDES_SOURCE_KIND
            or hashed({key: item for key, item in value.items() if key not in ('kind', 'inputs')}) != NATIVE_CONTROL_INCLUDES_HEADER_SHA256):
        raise ValueError('Exact native control includes source successor version/header/bounds required')
    entries = value['inputs']
    if (type(NATIVE_CONTROL_INCLUDES_SOURCE_FACTS) is not dict or type(entries) is not dict
            or len(entries) != 198 or len(NATIVE_CONTROL_INCLUDES_SOURCE_FACTS) != 1
            or set(NATIVE_CONTROL_INCLUDES_SOURCE_FACTS) != set(NATIVE_CONTROL_INCLUDES_PREDECESSOR_ROWS)
            or hashed(sorted(entries)) != NATIVE_CONTROL_INCLUDES_NAMESPACE_SHA256):
        raise ValueError('Exact native control includes namespace and one source pin required')
    retained = {name: row for name, row in entries.items() if name not in (*NATIVE_CONTROL_INCLUDES_SOURCE_FACTS, 'inspect_sources.py')}
    if hashed(retained) != NATIVE_CONTROL_INCLUDES_RETAINED_SHA256:
        raise ValueError('Unrelated native control includes source/catalogue row changed')
    inspector = entries['inspect_sources.py']
    old_inspector = NATIVE_CONTROL_INCLUDES_PREDECESSOR_INSPECTOR
    if (type(inspector) is not dict or set(inspector) != set(old_inspector)
            or any(inspector[key] != old_inspector[key] or type(inspector[key]) is not type(old_inspector[key])
                   for key in old_inspector if key not in ('sha256', 'bytes'))
            or type(inspector['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', inspector['sha256'])
            or type(inspector['bytes']) is not int or not 0 < inspector['bytes'] <= 1048576):
        raise ValueError('Native control keypress inspector identity/shape differs')
    previous = dict(value, kind=NATIVE_CONTROL_KEYPRESS_SOURCE_KIND, inputs=dict(entries))
    previous['inputs']['inspect_sources.py'] = dict(old_inspector)
    for logical, expected in NATIVE_CONTROL_INCLUDES_SOURCE_FACTS.items():
        item = entries[logical]
        if (type(expected) is not dict or set(expected) != {'sha256', 'bytes', 'mode'}
                or type(expected['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', expected['sha256'])
                or type(expected['bytes']) is not int or not 0 < expected['bytes'] <= 8388608
                or type(expected['mode']) is not int or expected['mode'] != 420
                or type(item) is not dict or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
                or item['tracked_path'] != RECIPE + '/' + logical or item['role'] != 'source'
                or any(type(item[key]) is not type(expected[key]) or item[key] != expected[key] for key in expected)):
            raise ValueError('Exact released native control includes source fact differs')
        origin = item['origin']
        wanted = {'kind': 'reviewed-native-control-includes-successor',
            'correction': 'explicit-webcore-inline-definitions-for-native-control-default',
            'source_only': True, 'source_path': item['tracked_path'], 'sha256': item['sha256'],
            'reviewed_source_map_sha256': NATIVE_CONTROL_INCLUDES_REVIEWED_SOURCE_MAP}
        if (type(origin) is not dict or set(origin) != set(wanted) | {'supersedes'}
                or any(type(origin[key]) is not type(expected_value) or origin[key] != expected_value
                       for key, expected_value in wanted.items())):
            raise ValueError('Native control keypress source-only lineage was restamped')
        prior = origin['supersedes']
        if (type(prior) is not dict or set(prior) != {'origin', 'sha256', 'bytes', 'tracked_path'}
                or type(prior['bytes']) is not int or prior['tracked_path'] != item['tracked_path']):
            raise ValueError('Native control keypress complete historical predecessor required')
        old = dict(item, **prior)
        if hashed(old) != NATIVE_CONTROL_INCLUDES_PREDECESSOR_ROWS[logical]:
            raise ValueError('Native control keypress prior source/origin/bytes/path was restamped')
        previous['inputs'][logical] = old
    raw = (json.dumps(previous, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    if hashlib.sha256(raw).hexdigest() != NATIVE_CONTROL_INCLUDES_REVIEWED_SOURCE_MAP:
        raise ValueError('Exact native control keypress predecessor map reconstruction differs')
    return previous


def native_control_includes_catalogue_counts(value):
    """Keep all older native keypress/popup/composition admission rules unchanged."""
    previous = native_control_includes_catalogue_predecessor(value)
    return native_control_keypress_catalogue_counts(previous)



def _retain_current_source(retained, name, original, role, inputs):
    name = _name(name)
    item = inputs._records[str(original)]
    previous = retained.get(name)
    fact = {'path': str(original), 'sha256': item['sha256'], 'mode': item['mode'], 'role': role}
    if previous is not None and any(previous[key] != fact[key] for key in ('sha256', 'mode', 'role')):
        raise ValueError('Conflicting retained native recipe logical path: ' + name)
    if previous is None:
        retained[name] = fact


NATIVE_SHOWPICKER_SOURCE_KIND = 'foundation-native-engine-actions-showpicker-settings-source-inputs-v1'
NATIVE_SHOWPICKER_PROFILE_KIND = 'foundation-native-engine-prototype-showpicker-settings-profile-v1'
NATIVE_SHOWPICKER_PREDECESSOR_SOURCE_MAP = '20778ece9cd45fc8f4e1839cdd9da8abd820d21e9042099b9157b32c018b43d8'
NATIVE_SHOWPICKER_SOURCE_FACTS = {'source/wrapper/src/embedder/main.cpp': {'sha256': '559ee65304dcda907f8c574ce664710435740366555036113063d94946b335ad', 'bytes': 48401, 'mode': 420}}
NATIVE_SHOWPICKER_PREDECESSOR_ROWS = {'source/wrapper/src/embedder/main.cpp': '5be6358ab3ae931afdb1c7944450662ff77367c2135ec119e93c5c324bf646e3'}
NATIVE_SHOWPICKER_NAMESPACE_SHA256 = '786fd3a2c417370bc0dae92bae552c5c7a80ba0adf6dfa67ef88ad5ffcf15812'
NATIVE_SHOWPICKER_RETAINED_SHA256 = '12064c1f91f3071171ebf79beb6590cdf6cd89a87ade54b1915ac2e0e0715f9b'
NATIVE_SHOWPICKER_HEADER_SHA256 = '443c4774b2a6994ed83b9e71a6c8b4bdcdab5f6d12670657da428a8a4c2f0c8c'
NATIVE_SHOWPICKER_PREDECESSOR_INSPECTOR = {'bytes': 36902, 'mode': 420, 'origin': {'kind': 'native-actions-source-recipe-input'}, 'role': 'helper', 'sha256': '6c9ff7cfe20dc7088efad76bd983a876a02e9666f6e5f3b3e59c64711ab93f48', 'tracked_path': 'recipes/webkitwasm-native-rich4083-v1/inspect_sources.py'}


def native_showpicker_catalogue_predecessor(value):
    """Admit one source-only showPicker setting and reconstruct exact history."""
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    if (type(value) is not dict or set(value) != fields or value['kind'] != NATIVE_SHOWPICKER_SOURCE_KIND
            or hashed({key: item for key, item in value.items() if key not in ('kind', 'inputs')}) != NATIVE_SHOWPICKER_HEADER_SHA256):
        raise ValueError('Exact native showPicker source successor version/header/bounds required')
    entries = value['inputs']
    if (type(entries) is not dict or len(entries) != 198 or len(NATIVE_SHOWPICKER_SOURCE_FACTS) != 1
            or set(NATIVE_SHOWPICKER_SOURCE_FACTS) != set(NATIVE_SHOWPICKER_PREDECESSOR_ROWS)
            or hashed(sorted(entries)) != NATIVE_SHOWPICKER_NAMESPACE_SHA256):
        raise ValueError('Exact native showPicker namespace and one source pin required')
    retained = {name: row for name, row in entries.items() if name not in (*NATIVE_SHOWPICKER_SOURCE_FACTS, 'inspect_sources.py')}
    if hashed(retained) != NATIVE_SHOWPICKER_RETAINED_SHA256:
        raise ValueError('Unrelated native source/catalogue row changed')
    inspector = entries['inspect_sources.py']
    old_inspector = NATIVE_SHOWPICKER_PREDECESSOR_INSPECTOR
    if (type(inspector) is not dict or set(inspector) != set(old_inspector)
            or any(inspector[key] != old_inspector[key] or type(inspector[key]) is not type(old_inspector[key])
                   for key in old_inspector if key not in ('sha256', 'bytes'))
            or type(inspector['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', inspector['sha256'])
            or type(inspector['bytes']) is not int or not 0 < inspector['bytes'] <= 1048576):
        raise ValueError('Native showPicker inspector identity/shape differs')
    previous = dict(value, kind=NATIVE_CONTROL_INCLUDES_SOURCE_KIND, inputs=dict(entries))
    previous['inputs']['inspect_sources.py'] = dict(old_inspector)
    for logical, expected in NATIVE_SHOWPICKER_SOURCE_FACTS.items():
        item = entries[logical]
        if (set(expected) != {'sha256', 'bytes', 'mode'} or type(expected['bytes']) is not int
                or type(expected['mode']) is not int or type(item) is not dict
                or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
                or item['tracked_path'] != RECIPE + '/' + logical or item['role'] != 'source'
                or any(type(item[key]) is not type(expected[key]) or item[key] != expected[key] for key in expected)):
            raise ValueError('Exact released native showPicker source fact differs')
        origin = item['origin']
        wanted = {'kind': 'reviewed-native-select-showpicker-successor',
            'correction': 'provider-page-startup-enables-native-select-show-picker',
            'source_only': True, 'source_path': item['tracked_path'], 'sha256': item['sha256'],
            'reviewed_source_acceptance_sha256': 'a2883e614f6ff2268f0ab332d0888b4f72a671c9bf2b27da160f3249137d9f41'}
        if (type(origin) is not dict or set(origin) != set(wanted) | {'supersedes'}
                or any(type(origin[key]) is not type(expected_value) or origin[key] != expected_value
                       for key, expected_value in wanted.items())):
            raise ValueError('Native showPicker source-only lineage was restamped')
        prior = origin['supersedes']
        if (type(prior) is not dict or set(prior) != {'origin', 'sha256', 'bytes', 'tracked_path'}
                or type(prior['bytes']) is not int or prior['tracked_path'] != item['tracked_path']):
            raise ValueError('Native showPicker complete historical predecessor required')
        old = dict(item, **prior)
        if hashed(old) != NATIVE_SHOWPICKER_PREDECESSOR_ROWS[logical]:
            raise ValueError('Native showPicker prior source/origin/bytes/path was restamped')
        previous['inputs'][logical] = old
    raw = (json.dumps(previous, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    if hashlib.sha256(raw).hexdigest() != NATIVE_SHOWPICKER_PREDECESSOR_SOURCE_MAP:
        raise ValueError('Exact native control-includes predecessor map reconstruction differs')
    return previous


def native_showpicker_catalogue_counts(value):
    """Keep all older native control, popup and composition history unchanged."""
    return native_control_includes_catalogue_counts(native_showpicker_catalogue_predecessor(value))


NATIVE_SELECT_EVENTS_SOURCE_KIND = 'foundation-native-engine-actions-select-events-source-inputs-v1'
NATIVE_SELECT_EVENTS_PROFILE_KIND = 'foundation-native-engine-prototype-select-events-profile-v1'
NATIVE_SELECT_EVENTS_PREDECESSOR_SOURCE_MAP = '5033e776046234aad7b60a4adf833e589be45133786315755173933ec7146b1e'
NATIVE_SELECT_EVENTS_HEADER_SHA256 = 'c60e04a5f3d47f92cd02fd93e33fdefc743fba57935dce704bee20d9a3672995'
NATIVE_SELECT_EVENTS_RETAINED_SHA256 = 'fcc84379c800ac41678489a26df1a1d1134162d7df9327bfee313e26b4c30097'
NATIVE_SELECT_EVENTS_PREDECESSOR_PROVENANCE = {'sha256': 'f5e4a29c6e5bdd0d396c634e8f51a2cc64c43f75d8f25e251184f65c55eb86ee', 'bytes': 183217}
NATIVE_SELECT_EVENTS_SOURCE_FACTS = {'source/engine/Source/WebCore/html/HTMLSelectElement.cpp': {'sha256': 'ccabb6855aa4befe7db1f9a2225ae1ef1b942a7508cc3fdeea62783e01f73509', 'bytes': 74829, 'mode': 420}}
NATIVE_SELECT_EVENTS_PREDECESSOR_ROW = 'e5796e05832009af593242731de2882f1d7c557221ef9634b8d5894c36a94c85'
NATIVE_SELECT_EVENTS_PREDECESSOR_INSPECTOR = {'bytes': 43107, 'mode': 420, 'origin': {'kind': 'native-actions-source-recipe-input'}, 'role': 'helper', 'sha256': 'f25e7dad8018b746936c025ccdcde791e6881bf1f3a7dcfe4702251af4854f6f', 'tracked_path': 'recipes/webkitwasm-native-rich4083-v1/inspect_sources.py'}
NATIVE_SELECT_EVENTS_REVIEWED_SOURCE_ACCEPTANCE = 'aee6871efc89abbb98119bbf01eb9e71713c1a0db529e6bc1c9ba7f249e469d4'
NATIVE_SELECT_EVENTS_CORRECTION = 'compare-current-selection-before-immediate-changed-user-choice-commit'


def native_select_events_catalogue_predecessor(value):
    """Restore the exact current showPicker catalogue before the select leaf successor."""
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    logical = 'source/engine/Source/WebCore/html/HTMLSelectElement.cpp'
    if (type(value) is not dict or set(value) != fields or value['kind'] != NATIVE_SELECT_EVENTS_SOURCE_KIND
            or hashed({key: item for key, item in value.items() if key not in ('kind', 'inputs')}) != NATIVE_SELECT_EVENTS_HEADER_SHA256):
        raise ValueError('Exact native select events source successor version/header/bounds required')
    entries = value['inputs']
    if type(entries) is not dict or len(entries) != 198 or hashed(sorted(entries)) != NATIVE_SHOWPICKER_NAMESPACE_SHA256:
        raise ValueError('Exact native select events namespace required')
    retained = {name: row for name, row in entries.items() if name not in (logical, 'inspect_sources.py')}
    if hashed(retained) != NATIVE_SELECT_EVENTS_RETAINED_SHA256:
        raise ValueError('Unrelated native source/catalogue row changed')
    inspector = entries['inspect_sources.py']
    old_inspector = NATIVE_SELECT_EVENTS_PREDECESSOR_INSPECTOR
    if (type(inspector) is not dict or set(inspector) != set(old_inspector)
            or any(inspector[key] != old_inspector[key] or type(inspector[key]) is not type(old_inspector[key])
                   for key in old_inspector if key not in ('sha256', 'bytes'))
            or type(inspector['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', inspector['sha256'])
            or type(inspector['bytes']) is not int or not 0 < inspector['bytes'] <= 1048576):
        raise ValueError('Native select events inspector identity/shape differs')
    previous = dict(value, kind=NATIVE_SHOWPICKER_SOURCE_KIND, inputs=dict(entries))
    previous['inputs']['inspect_sources.py'] = dict(old_inspector)
    old_provenance = dict(value['provenance'], sha256=NATIVE_SELECT_EVENTS_PREDECESSOR_PROVENANCE['sha256'])
    previous['provenance'] = old_provenance
    old_provenance_item = dict(entries['provenance.json'])
    if (old_provenance_item.get('tracked_path') != RECIPE + '/provenance.json'
            or old_provenance_item.get('role') != 'provenance'
            or old_provenance_item.get('origin') != {'kind': 'native-actions-source-recipe-input'}
            or old_provenance_item.get('sha256') != value['provenance']['sha256']
            or old_provenance_item.get('bytes') != value['inputs']['provenance.json'].get('bytes')):
        raise ValueError('Exact native select events current provenance input required')
    old_provenance_item.update(sha256=NATIVE_SELECT_EVENTS_PREDECESSOR_PROVENANCE['sha256'],
                               bytes=NATIVE_SELECT_EVENTS_PREDECESSOR_PROVENANCE['bytes'])
    previous['inputs']['provenance.json'] = old_provenance_item
    item = entries[logical]
    expected = NATIVE_SELECT_EVENTS_SOURCE_FACTS[logical]
    path = RECIPE + '/' + logical
    if (type(expected) is not dict or set(expected) != {'sha256', 'bytes', 'mode'}
            or type(expected['bytes']) is not int or type(expected['mode']) is not int
            or type(item) is not dict or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
            or item['tracked_path'] != path or item['role'] != 'source'
            or any(type(item[key]) is not type(expected[key]) or item[key] != expected[key] for key in expected)):
        raise ValueError('Exact released native select events source fact differs')
    origin = item['origin']
    record = origin.get('record') if type(origin) is dict else None
    if type(origin) is not dict or set(origin) != {'kind', 'record'} or origin['kind'] != 'mapped-native-engine' or type(record) is not dict:
        raise ValueError('Native select events mapped source origin required')
    successor = record.get('successor')
    if type(successor) is not dict or set(successor) != {'kind', 'correction', 'source_only', 'source_path', 'sha256', 'reviewed_source_acceptance_sha256', 'supersedes'}:
        raise ValueError('Exact native select events source-only lineage required')
    wanted = {'kind': 'reviewed-native-select-events-successor', 'correction': NATIVE_SELECT_EVENTS_CORRECTION,
              'source_only': True, 'source_path': path, 'sha256': expected['sha256'],
              'reviewed_source_acceptance_sha256': NATIVE_SELECT_EVENTS_REVIEWED_SOURCE_ACCEPTANCE}
    if any(type(successor[key]) is not type(value) or successor[key] != value for key, value in wanted.items()):
        raise ValueError('Native select events source-only lineage was restamped')
    prior_record = successor['supersedes']
    if type(prior_record) is not dict:
        raise ValueError('Complete native select events historical predecessor required')
    old_record = dict(record)
    del old_record['successor']
    old_record['sha256'] = '0b4b077b36193fd5ebea0e29017c54ae2df430b6e6ef78d7a3a06f6c19cfe4b1'
    old_record['bytes'] = 74585
    old_item = dict(item, sha256=prior_record.get('sha256'), bytes=prior_record.get('bytes'),
                    origin={'kind': 'mapped-native-engine', 'record': prior_record})
    if (prior_record != old_record or hashed(old_item) != NATIVE_SELECT_EVENTS_PREDECESSOR_ROW
            or prior_record.get('sha256') != '0b4b077b36193fd5ebea0e29017c54ae2df430b6e6ef78d7a3a06f6c19cfe4b1'
            or prior_record.get('bytes') != 74585 or prior_record.get('tracked_source') != logical):
        raise ValueError('Native select events original/adapted predecessor was restamped')
    previous['inputs'][logical] = old_item
    raw = (json.dumps(previous, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    if hashlib.sha256(raw).hexdigest() != NATIVE_SELECT_EVENTS_PREDECESSOR_SOURCE_MAP:
        raise ValueError('Exact native showPicker predecessor map reconstruction differs')
    return previous


def native_select_events_catalogue_counts(value):
    """Keep all source history before the accepted select events leaf unchanged."""
    return native_showpicker_catalogue_counts(native_select_events_catalogue_predecessor(value))



NATIVE_INPUT_METHOD_SOURCE_KIND = 'foundation-native-engine-actions-input-method-source-inputs-v1'
NATIVE_INPUT_METHOD_PROFILE_KIND = 'foundation-native-engine-prototype-input-method-profile-v1'
NATIVE_INPUT_METHOD_PREDECESSOR_SOURCE_MAP = '9e6b36bcfd6efdbc834c8fb06ef2ab9ca5a7dadb91b9c0d78b7a94fddf0bcf31'
NATIVE_INPUT_METHOD_SOURCE_FACTS = {'source/wrapper/src/embedder/BibPageClients.h': {'sha256': '283876d4a85cd07b800f0c54ee96695ab5345146481f41e1a615a44fc9e5c7aa', 'bytes': 30339, 'mode': 420}}
NATIVE_INPUT_METHOD_PREDECESSOR_HEADER_ROW = 'b36c511951b829225fbafa1726103ae4803d98a37d5f6243be8ef19ec26eb201'
NATIVE_INPUT_METHOD_PREDECESSOR_INSPECTOR = {'bytes': 51246, 'mode': 420, 'origin': {'kind': 'native-actions-source-recipe-input'}, 'role': 'helper', 'sha256': '12ae1239503fab0148d7d3872322dfa87d97415ef854c47840b730d1a3b5c0fb', 'tracked_path': 'recipes/webkitwasm-native-rich4083-v1/inspect_sources.py'}
NATIVE_INPUT_METHOD_PREDECESSOR_PROVENANCE = {'sha256': 'e4b1c122b95fe2b629ad80818552bc354614223d8fadcf7de004aed5b857084c', 'bytes': 184668}
NATIVE_INPUT_METHOD_REVIEWED_ACCEPTANCE = '539a2dd0ee5992cfcf260d35f1014f1df749af371cdfead31658867e211fdda9'
NATIVE_INPUT_METHOD_CORRECTION = 'reset-native-input-method-state-on-main-document-lifecycle'
NATIVE_INPUT_METHOD_HEADER_SHA256 = '7550b7f3da2dd5b77b07cf1385024d71ee97cdfdb875f4e8fb51b58db98309fa'
NATIVE_INPUT_METHOD_RETAINED_SHA256 = '7a87e58264c3960bcead0bffba1760d07a16bfa6e41e66ad19cb0dd9d1859e7f'


def native_input_method_catalogue_predecessor(value):
    """Restore the exact accepted select-events map before this header leaf."""
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    logical = 'source/wrapper/src/embedder/BibPageClients.h'
    if (type(value) is not dict or set(value) != fields or value['kind'] != NATIVE_INPUT_METHOD_SOURCE_KIND
            or hashed({key: item for key, item in value.items() if key not in ('kind', 'inputs')}) != NATIVE_INPUT_METHOD_HEADER_SHA256):
        raise ValueError('Exact native input method source successor version/header/bounds required')
    entries = value['inputs']
    if (type(entries) is not dict or len(entries) != 198 or hashed(sorted(entries)) != NATIVE_SHOWPICKER_NAMESPACE_SHA256):
        raise ValueError('Exact native input method source namespace required')
    retained = {name: row for name, row in entries.items() if name not in (logical, 'inspect_sources.py', 'provenance.json')}
    if hashed(retained) != NATIVE_INPUT_METHOD_RETAINED_SHA256:
        raise ValueError('Unrelated native input method source/catalogue row changed')
    old_inspector = NATIVE_INPUT_METHOD_PREDECESSOR_INSPECTOR
    inspector = entries['inspect_sources.py']
    if (type(inspector) is not dict or set(inspector) != set(old_inspector)
            or inspector['mode'] != old_inspector['mode'] or type(inspector['mode']) is not int
            or inspector['tracked_path'] != old_inspector['tracked_path'] or inspector['role'] != 'helper'
            or inspector['origin'] != {'kind': 'native-actions-source-recipe-input'}
            or type(inspector['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', inspector['sha256'])
            or type(inspector['bytes']) is not int or not 0 < inspector['bytes'] <= 1048576):
        raise ValueError('Native input method inspector identity/shape differs')
    previous = dict(value, kind=NATIVE_SELECT_EVENTS_SOURCE_KIND, inputs=dict(entries))
    previous['inputs']['inspect_sources.py'] = dict(old_inspector)
    old_provenance = NATIVE_INPUT_METHOD_PREDECESSOR_PROVENANCE
    provenance = value['provenance']
    provenance_item = entries['provenance.json']
    path = RECIPE + '/provenance.json'
    if (type(provenance_item) is not dict or provenance_item.get('tracked_path') != path
            or provenance_item.get('role') != 'provenance'
            or provenance_item.get('origin') != {'kind': 'native-actions-source-recipe-input'}
            or provenance_item.get('sha256') != provenance.get('sha256')
            or provenance_item.get('sha256') != '124b5904cdf711214ea3ade9cf840f179c1f3e439b29f60cfd01e4408cf4101c'
            or provenance_item.get('bytes') != 185327
            or type(provenance_item.get('bytes')) is not int):
        raise ValueError('Exact native input method current provenance input required')
    previous['provenance'] = dict(provenance, sha256=old_provenance['sha256'])
    previous['inputs']['provenance.json'] = dict(provenance_item, sha256=old_provenance['sha256'], bytes=old_provenance['bytes'])
    item = entries[logical]
    if (type(NATIVE_INPUT_METHOD_SOURCE_FACTS) is not dict or set(NATIVE_INPUT_METHOD_SOURCE_FACTS) != {logical}
            or type(NATIVE_INPUT_METHOD_SOURCE_FACTS[logical]) is not dict
            or set(NATIVE_INPUT_METHOD_SOURCE_FACTS[logical]) != {'sha256', 'bytes', 'mode'}):
        raise ValueError('Native input method source facts remain unbound')
    expected = NATIVE_INPUT_METHOD_SOURCE_FACTS[logical]
    if (type(item) is not dict or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
            or item['tracked_path'] != RECIPE + '/' + logical or item['role'] != 'source'
            or any(type(item.get(key)) is not type(expected[key]) or item.get(key) != expected[key] for key in expected)):
        raise ValueError('Exact released native input method source fact differs')
    origin = item['origin']
    record = origin.get('record') if type(origin) is dict else None
    if (type(origin) is not dict or set(origin) != {'kind', 'record'}
            or origin['kind'] != 'mapped-native-actions-runtime' or type(record) is not dict):
        raise ValueError('Native input method mapped source origin required')
    successor = record.get('successor')
    if type(successor) is not dict or set(successor) != {'kind', 'correction', 'source_only', 'source_path', 'sha256', 'reviewed_source_acceptance_sha256', 'supersedes'}:
        raise ValueError('Exact native input method source-only lineage required')
    wanted = {'kind': 'reviewed-native-input-method-successor', 'correction': NATIVE_INPUT_METHOD_CORRECTION,
        'source_only': True, 'source_path': RECIPE + '/' + logical, 'sha256': expected['sha256'],
        'reviewed_source_acceptance_sha256': NATIVE_INPUT_METHOD_REVIEWED_ACCEPTANCE}
    if any(type(successor.get(key)) is not type(value) or successor.get(key) != value for key, value in wanted.items()):
        raise ValueError('Native input method source-only lineage was restamped')
    prior_record = successor['supersedes']
    old_row = dict(item, sha256='6e77e9b1b47cc5e4e3d2a5dcd7600ea959c4b22eb95c763165c4ccc3c5d28a43', bytes=29858,
                   origin={'kind': 'mapped-native-actions-runtime', 'record': prior_record})
    expected_record = dict(prior_record, action=NATIVE_INPUT_METHOD_CORRECTION,
        after_sha256=expected['sha256'], after_bytes=expected['bytes'], successor=successor) if type(prior_record) is dict else None
    if (type(prior_record) is not dict or canonical(record) != canonical(expected_record)
            or hashed(old_row) != NATIVE_INPUT_METHOD_PREDECESSOR_HEADER_ROW
            or prior_record.get('after_sha256') != '6e77e9b1b47cc5e4e3d2a5dcd7600ea959c4b22eb95c763165c4ccc3c5d28a43'
            or prior_record.get('after_bytes') != 29858
            or prior_record.get('source') != logical):
        raise ValueError('Native input method complete header predecessor/origin was restamped')
    previous['inputs'][logical] = old_row
    raw = (json.dumps(previous, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    if hashlib.sha256(raw).hexdigest() != NATIVE_INPUT_METHOD_PREDECESSOR_SOURCE_MAP:
        raise ValueError('Exact native select events predecessor map reconstruction differs')
    return previous


def native_input_method_catalogue_counts(value):
    """Preserve accepted select-events and all older native history layers."""
    return native_select_events_catalogue_counts(native_input_method_catalogue_predecessor(value))



NATIVE_FORM_PREFLIGHT_SOURCE_KIND = 'foundation-native-engine-actions-retired-form-preflight-source-inputs-v1'
NATIVE_FORM_PREFLIGHT_PROFILE_KIND = 'foundation-native-engine-prototype-retired-form-preflight-profile-v1'
NATIVE_FORM_PREFLIGHT_PREDECESSOR_SOURCE_MAP = '13cbe3ca607bb5cba54f1f880f9b2471b430c9be3563a7f3a623ed9ceb7cff03'
NATIVE_FORM_PREFLIGHT_SOURCE_FACTS = {'source/foundation/third_party/appended-engine/src/ProviderGuard.cpp': {'sha256': 'c0e73457c85e3b54c956cad124407ff0fd03d53b0abdfdb5003f6146990a8157', 'bytes': 75818, 'mode': 420}}
NATIVE_FORM_PREFLIGHT_PREDECESSOR_GUARD_ROW = '18404166355c937453deef1ac6a28da50125063984bf920892a18d0eb196d6fc'
NATIVE_FORM_PREFLIGHT_PREDECESSOR_INSPECTOR = {'bytes': 59714, 'mode': 420, 'origin': {'kind': 'native-actions-source-recipe-input'}, 'role': 'helper', 'sha256': 'f8f5eaddb0a6948e56c35859dded7676cc176350b000bc0135447176697646e4', 'tracked_path': 'recipes/webkitwasm-native-rich4083-v1/inspect_sources.py'}
NATIVE_FORM_PREFLIGHT_PREDECESSOR_PROVENANCE = {'sha256': '124b5904cdf711214ea3ade9cf840f179c1f3e439b29f60cfd01e4408cf4101c', 'bytes': 185327}
NATIVE_FORM_PREFLIGHT_CURRENT_PROVENANCE = {'sha256': '5312e2bb2de6754de28f0792382096d2542484af2d8cef32b9c37cc842a4ee89', 'bytes': 186852}
NATIVE_FORM_PREFLIGHT_REVIEWED_ACCEPTANCE = 'aae075f824859c9133a24bdea86ad1e7cb86d9b58165a907e13b665d4fd36757'
NATIVE_FORM_PREFLIGHT_CORRECTION = 'inert-retired-FORM_ACTION_V2-before-host-TURN-with-in-turn-revalidation'
NATIVE_FORM_PREFLIGHT_HEADER_SHA256 = '5a017cd0e8b6d1e7dcb948f149974da94f9ee2e1d211cb40084833371fa4fe96'
NATIVE_FORM_PREFLIGHT_RETAINED_SHA256 = '9d1e96eea4676e743dead33c578719c7cb8e3712fec4434dfb0f43abe4f1ee65'


def native_form_preflight_catalogue_predecessor(value):
    """Restore the exact accepted InputMethod catalogue before the form Guard."""
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    logical = 'source/foundation/third_party/appended-engine/src/ProviderGuard.cpp'
    if (type(value) is not dict or set(value) != fields or value['kind'] != NATIVE_FORM_PREFLIGHT_SOURCE_KIND
            or hashed({key: item for key, item in value.items() if key not in ('kind', 'inputs')}) != NATIVE_FORM_PREFLIGHT_HEADER_SHA256):
        raise ValueError('Exact native form preflight source successor version/header/bounds required')
    entries = value['inputs']
    if (type(entries) is not dict or len(entries) != 198 or hashed(sorted(entries)) != NATIVE_SHOWPICKER_NAMESPACE_SHA256):
        raise ValueError('Exact native form preflight source namespace required')
    retained = {name: row for name, row in entries.items() if name not in (logical, 'inspect_sources.py', 'provenance.json')}
    if hashed(retained) != NATIVE_FORM_PREFLIGHT_RETAINED_SHA256:
        raise ValueError('Unrelated native form preflight source/catalogue row changed')
    old_inspector = NATIVE_FORM_PREFLIGHT_PREDECESSOR_INSPECTOR
    inspector = entries['inspect_sources.py']
    if (type(inspector) is not dict or set(inspector) != set(old_inspector)
            or any(type(inspector[key]) is not type(old_inspector[key]) or inspector[key] != old_inspector[key]
                   for key in old_inspector if key not in ('sha256', 'bytes'))
            or type(inspector['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', inspector['sha256'])
            or type(inspector['bytes']) is not int or not 0 < inspector['bytes'] <= 1048576):
        raise ValueError('Native form preflight inspector identity/shape differs')
    provenance_item = entries['provenance.json']
    current_provenance = NATIVE_FORM_PREFLIGHT_CURRENT_PROVENANCE
    if (type(provenance_item) is not dict or set(provenance_item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
            or provenance_item['tracked_path'] != RECIPE + '/provenance.json' or provenance_item['role'] != 'provenance'
            or provenance_item['origin'] != {'kind': 'native-actions-source-recipe-input'}
            or provenance_item['mode'] != 420 or type(provenance_item['mode']) is not int
            or any(type(provenance_item.get(key)) is not type(expected) or provenance_item.get(key) != expected
                   for key, expected in current_provenance.items())
            or value['provenance']['sha256'] != current_provenance['sha256']):
        raise ValueError('Exact native form preflight current provenance required')
    if (type(NATIVE_FORM_PREFLIGHT_SOURCE_FACTS) is not dict or set(NATIVE_FORM_PREFLIGHT_SOURCE_FACTS) != {logical}
            or type(NATIVE_FORM_PREFLIGHT_SOURCE_FACTS[logical]) is not dict
            or set(NATIVE_FORM_PREFLIGHT_SOURCE_FACTS[logical]) != {'sha256', 'bytes', 'mode'}):
        raise ValueError('Native form preflight source facts remain unbound')
    expected = NATIVE_FORM_PREFLIGHT_SOURCE_FACTS[logical]
    item = entries[logical]
    if (type(item) is not dict or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
            or item['tracked_path'] != RECIPE + '/' + logical or item['role'] != 'source'
            or any(type(item.get(key)) is not type(wanted) or item.get(key) != wanted for key, wanted in expected.items())):
        raise ValueError('Exact native form preflight Guard source fact required')
    origin = item['origin']
    record = origin.get('record') if type(origin) is dict else None
    if (type(origin) is not dict or set(origin) != {'kind', 'record'}
            or origin['kind'] != 'mapped-native-actions-runtime' or type(record) is not dict):
        raise ValueError('Native form preflight mapped runtime origin required')
    successor = record.get('successor')
    wanted = {'kind': 'reviewed-native-retired-form-preflight-successor', 'correction': NATIVE_FORM_PREFLIGHT_CORRECTION,
        'source_only': True, 'source_path': RECIPE + '/' + logical, 'sha256': expected['sha256'],
        'reviewed_source_acceptance_sha256': NATIVE_FORM_PREFLIGHT_REVIEWED_ACCEPTANCE}
    if (type(successor) is not dict or set(successor) != set(wanted) | {'supersedes'}
            or any(type(successor.get(key)) is not type(value) or successor.get(key) != value for key, value in wanted.items())):
        raise ValueError('Native form preflight source-only successor was restamped')
    prior_record = successor['supersedes']
    old_item = dict(item, sha256='3aebfcc5b4e838846f23a5c9c61a62acc51fecc73541fd58deaa9c157308b0ff', bytes=74981,
        origin={'kind': 'mapped-native-actions-runtime', 'record': prior_record})
    expected_record = dict(prior_record, action=NATIVE_FORM_PREFLIGHT_CORRECTION,
        after_sha256=expected['sha256'], after_bytes=expected['bytes'], successor=successor) if type(prior_record) is dict else None
    if (type(prior_record) is not dict or canonical(record) != canonical(expected_record)
            or hashed(old_item) != NATIVE_FORM_PREFLIGHT_PREDECESSOR_GUARD_ROW):
        raise ValueError('Native form preflight complete predecessor or supplier origin was restamped')
    previous = dict(value, kind=NATIVE_INPUT_METHOD_SOURCE_KIND, inputs=dict(entries),
        provenance=dict(value['provenance'], sha256=NATIVE_FORM_PREFLIGHT_PREDECESSOR_PROVENANCE['sha256']))
    previous['inputs'][logical] = old_item
    previous['inputs']['inspect_sources.py'] = dict(old_inspector)
    previous['inputs']['provenance.json'] = dict(provenance_item, **NATIVE_FORM_PREFLIGHT_PREDECESSOR_PROVENANCE)
    raw = (json.dumps(previous, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    if hashlib.sha256(raw).hexdigest() != NATIVE_FORM_PREFLIGHT_PREDECESSOR_SOURCE_MAP:
        raise ValueError('Exact native InputMethod predecessor map reconstruction differs')
    return previous


def native_form_preflight_catalogue_counts(value):
    """Preserve every accepted InputMethod and earlier source contract."""
    return native_input_method_catalogue_counts(native_form_preflight_catalogue_predecessor(value))

def _capture_current_sources_core(profile, source_map, source_map_sha256, root, inputs):
    """One implementation of the existing finite197/157 source admission."""
    map_path, map_pin = _ref(profile['source_map'], root)
    if source_map_sha256 != map_pin:
        raise ValueError('Native selection must use the exact current canonical197 source map')
    inputs.file(map_path, map_pin, 'canonical-native-source-map', maximum=MAX_DOCUMENT)
    source_entries = source_map.get('inputs') if type(source_map) is dict else None
    native_form_preflight = type(source_map) is dict and source_map.get('kind') == NATIVE_FORM_PREFLIGHT_SOURCE_KIND
    native_input_method = type(source_map) is dict and source_map.get('kind') == NATIVE_INPUT_METHOD_SOURCE_KIND
    native_select_events = type(source_map) is dict and source_map.get('kind') == NATIVE_SELECT_EVENTS_SOURCE_KIND
    native_showpicker = type(source_map) is dict and source_map.get('kind') == NATIVE_SHOWPICKER_SOURCE_KIND
    native_control_includes = type(source_map) is dict and source_map.get('kind') == NATIVE_CONTROL_INCLUDES_SOURCE_KIND
    native_control_keypress = type(source_map) is dict and source_map.get('kind') == NATIVE_CONTROL_KEYPRESS_SOURCE_KIND
    native_popup = type(source_map) is dict and source_map.get('kind') == NATIVE_POPUP_SOURCE_KIND
    composition = type(source_map) is dict and source_map.get('kind') == COMPOSITION_SOURCE_KIND
    expected_counts = (native_form_preflight_catalogue_counts(source_map) if native_form_preflight else native_input_method_catalogue_counts(source_map) if native_input_method else native_select_events_catalogue_counts(source_map) if native_select_events else native_showpicker_catalogue_counts(source_map) if native_showpicker else native_control_includes_catalogue_counts(source_map) if native_control_includes else native_control_keypress_catalogue_counts(source_map) if native_control_keypress else native_popup_catalogue_counts(source_map) if native_popup else composition_catalogue_counts(source_map) if composition else
        {'source_files': 157, 'engine_files': 48, 'direct_translation_units': 32})
    expected_entries = 198 if native_form_preflight or native_input_method or native_select_events or native_showpicker or native_control_includes or native_control_keypress or native_popup or composition else 197
    if not (native_form_preflight or native_input_method or native_select_events or native_showpicker or native_control_includes or native_control_keypress or native_popup or composition) and type(source_entries) is dict and COMPOSITION_BRIDGE in source_entries:
        raise ValueError('Composition bridge requires its explicit successor version')
    if type(source_entries) is not dict or len(source_entries) != expected_entries:
        raise ValueError('Composition native source map requires exact198 entries' if composition else 'Native source map must be the reviewed197-entry contract')
    expected_profile_kind = NATIVE_FORM_PREFLIGHT_PROFILE_KIND if native_form_preflight else NATIVE_INPUT_METHOD_PROFILE_KIND if native_input_method else NATIVE_SELECT_EVENTS_PROFILE_KIND if native_select_events else NATIVE_SHOWPICKER_PROFILE_KIND if native_showpicker else NATIVE_CONTROL_INCLUDES_PROFILE_KIND if native_control_includes else NATIVE_CONTROL_KEYPRESS_PROFILE_KIND if native_control_keypress else NATIVE_POPUP_PROFILE_KIND if native_popup else COMPOSITION_PROFILE_KIND if composition else 'foundation-native-engine-prototype-profile-v1'
    if profile.get('kind') != expected_profile_kind:
        raise ValueError('Native source/profile successor versions differ')
    inspector = source_entries.get('inspect_sources.py')
    if type(inspector) is not dict or inspector.get('tracked_path') != RECIPE + '/inspect_sources.py':
        raise ValueError('Native map lacks its exact passive source inspector')
    inspector_path = root / inspector['tracked_path']
    inputs.file(inspector_path, pin(inspector['sha256'], 'source inspector'), 'source-inspector', maximum=MAX_DOCUMENT)
    namespace = {'__name__': '_foundation_native_source_inspection', '__file__': str(inspector_path)}
    exec(compile(inputs.bytes(inspector_path), str(inspector_path), 'exec'), namespace)
    source_facts = namespace['inspect'](root, map_pin)
    retained = {}
    overlays = {}
    def retain(name, original, role):
        _retain_current_source(retained, name, original, role, inputs)
    for name, item in sorted(source_entries.items()):
        original = root / item['tracked_path']
        record = inputs.file(original, pin(item['sha256'], name), 'native-map-' + item['role'])
        if record['bytes'] != item['bytes'] or record['mode'] != item['mode']:
            raise ValueError('Native source map byte/mode mismatch')
        # Original patch files are retained provenance. Ordered actual patches
        # receive separate aliases below so the existing recipe contract owns
        # exactly the declared patch sequence.
        role = {'provenance': 'data', 'patch': 'data'}.get(item['role'], item['role'])
        retain(name, original, role)
        if name.startswith('source/') and item['role'] == 'source':
            overlays[name] = original
    provenance_path, provenance_pin = _ref(profile['provenance'], root)
    inputs.file(provenance_path, provenance_pin, 'native-provenance', maximum=MAX_DOCUMENT)
    provenance = strict_json(inputs.bytes(provenance_path), 'native provenance')
    graph_path, graph_pin = _ref(profile['graph'], root)
    inputs.file(graph_path, graph_pin, 'native-provider-graph', maximum=MAX_DOCUMENT)
    graph = inputs.bytes(graph_path).decode('utf-8')
    source_block = re.search(r'set\(_sources\s+(.*?)\)\s*# document_forms', graph, re.S)
    translation_units = re.findall(r'"[^"\n]+"', source_block.group(1)) if source_block else []
    counts = {'source_files': len(overlays), 'engine_files': sum(name.startswith('source/engine/') for name in overlays),
              'direct_translation_units': len(translation_units)}
    if counts != expected_counts or any(
            type(profile[name]) is not int or profile[name] != count or provenance['source_graph'][name] != count
            for name, count in counts.items()):
        raise ValueError('Actual native source/provider graph differs from157/48/32 profile')
    mapping = provenance.get('retained_input_mapping')
    if type(mapping) is not dict or len(mapping) != 25:
        raise ValueError('Native metadata retained mapping must have exactly25 reviewed entries')
    for name, item in mapping.items():
        _fields(item, ('role', 'sha256', 'tracked_source'), 'native retained metadata alias')
        original_item = source_entries.get(item['tracked_source'])
        if original_item is None or original_item['sha256'] != item['sha256']:
            raise ValueError('Native retained metadata alias differs from exact source map')
        retain(name, root / original_item['tracked_path'], item['role'])
    for name in PRODUCERS:
        original = root / name
        try:
            _ordinary(original)
        except FileNotFoundError as error:
            raise MissingInputs([{'role': 'native-producer-source', 'path': str(original), 'reason': 'exact source producer input absent'}]) from error
        _producer_bytes(inputs, original, 'native-producer-source', root)
        retain(name, original, 'config' if name.endswith(('.json', '.cmake')) else 'helper')
    inputs.check_deadline()
    return dict(profile=profile, source_facts=source_facts, source_entries=source_entries,
        retained=retained, overlays=overlays, provenance=provenance,
        map_path=map_path, map_pin=map_pin, root=root)


_CHECKED_CURRENT_SOURCE_TOKEN = object()
_CHECKED_COMPOSITION_TOKEN = object()


class CheckedCurrentSources:
    """Actual finite source capture; serialized metadata cannot construct it."""
    __slots__ = ('_token', '_owner', '_view', '_entries', '_overlays', '_deadline')

    def __new__(cls, *args, **kwargs):
        raise TypeError('CheckedCurrentSources is created only by current source capture')

    def __setattr__(self, name, value):
        raise AttributeError('Checked current source facts are immutable')

    def as_dict(self):
        if (getattr(self, '_token', None) is not _CHECKED_CURRENT_SOURCE_TOKEN
                or time.monotonic() >= self._deadline):
            raise ValueError('Invalid or expired checked current source capture')
        result = json.loads(self._view)
        if time.monotonic() >= self._deadline:
            raise ValueError('Checked current source deadline expired')
        return result


def capture_current_sources(profile_sha256, source_map_sha256, *, repository_root, inputs):
    """Capture only current source leaves; no supplier archive or SDK is read.

    Pins come from the independently reviewed enclosing control. The caller
    retains the real InputSet and performs its normal physical rechecks before
    publication or assembly. No receipt, user dictionary or old process result
    is accepted as the checked object.
    """
    if os.name != 'posix' or type(inputs) is not InputSet:
        raise ValueError('Qualified POSIX source capture owner required')
    started = time.monotonic()
    if inputs.deadline is not None and (type(inputs.deadline) not in (int, float)
            or not math.isfinite(inputs.deadline)):
        raise ValueError('Finite numeric current source owner deadline required')
    inputs.deadline = min(inputs.deadline, started + 86400) if inputs.deadline is not None else started + 86400
    inputs.check_deadline()
    if inputs.records or inputs._roots or inputs._sdk_roots or inputs.sdk_directory_records:
        raise ValueError('A fresh source-only capture owner is required')
    root = _ordinary(_absolute(repository_root), True)
    profile_raw = _producer_bytes(inputs, root / PROFILE, 'producer-profile', root)
    if sha256(profile_raw) != pin(profile_sha256, 'current producer profile'):
        raise ValueError('Current source profile differs from its independent pin')
    profile = strict_json(profile_raw, 'native producer profile')
    _schema(profile, ('schema_version', 'kind', 'target', 'profile', 'scope', 'recipe_directory',
        'source_map', 'provenance', 'graph', 'source_files', 'direct_translation_units', 'engine_files',
        'producer_inputs', 'required_toolchain_kind'), NATIVE_FORM_PREFLIGHT_PROFILE_KIND if profile.get('kind') == NATIVE_FORM_PREFLIGHT_PROFILE_KIND else NATIVE_INPUT_METHOD_PROFILE_KIND if profile.get('kind') == NATIVE_INPUT_METHOD_PROFILE_KIND else NATIVE_SELECT_EVENTS_PROFILE_KIND if profile.get('kind') == NATIVE_SELECT_EVENTS_PROFILE_KIND else NATIVE_SHOWPICKER_PROFILE_KIND if profile.get('kind') == NATIVE_SHOWPICKER_PROFILE_KIND else NATIVE_CONTROL_INCLUDES_PROFILE_KIND if profile.get('kind') == NATIVE_CONTROL_INCLUDES_PROFILE_KIND else NATIVE_CONTROL_KEYPRESS_PROFILE_KIND if profile.get('kind') == NATIVE_CONTROL_KEYPRESS_PROFILE_KIND else NATIVE_POPUP_PROFILE_KIND if profile.get('kind') == NATIVE_POPUP_PROFILE_KIND else COMPOSITION_PROFILE_KIND if profile.get('kind') == COMPOSITION_PROFILE_KIND else 'foundation-native-engine-prototype-profile-v1')
    validate_target(profile['target'])
    if (profile['profile'] != actions.SELECTOR
            or profile['scope'] != 'first-native-engine-baseline-candidate'
            or profile['recipe_directory'] != RECIPE or profile['producer_inputs'] != list(PRODUCERS)
            or profile['required_toolchain_kind'] != PRIVATE_TOOLCHAIN_KIND):
        raise ValueError('Native producer source profile changed or unsupported')
    path, digest = _ref(profile['source_map'], root)
    if digest != pin(source_map_sha256, 'current source map'):
        raise ValueError('Current source map differs from independently pinned profile')
    inputs.file(path, digest, 'canonical-native-source-map', maximum=MAX_DOCUMENT)
    value = strict_json(inputs.bytes(path), 'current native source map')
    current = _capture_current_sources_core(profile, value, digest, root, inputs)
    overlay_bytes = tuple((name, inputs.bytes(original, maximum=8 * 1024 * 1024))
        for name, original in sorted(current['overlays'].items()))
    # Capture only immutable normalized facts. The live owner is kept separately
    # so wrappers can retain/close their actual physical-input obligation.
    deadline = inputs.deadline
    facts = {'schema_version': 1, 'kind': 'foundation-native-current-source-capture-v1',
        'scope': 'current198-final158-retired-form-preflight-only' if value.get('kind') == NATIVE_FORM_PREFLIGHT_SOURCE_KIND else 'current198-final158-native-input-method-only' if value.get('kind') == NATIVE_INPUT_METHOD_SOURCE_KIND else 'current198-final158-native-select-events-only' if value.get('kind') == NATIVE_SELECT_EVENTS_SOURCE_KIND else 'current198-final158-native-select-showpicker-only' if value.get('kind') == NATIVE_SHOWPICKER_SOURCE_KIND else 'current198-final158-native-control-includes-only' if value.get('kind') == NATIVE_CONTROL_INCLUDES_SOURCE_KIND else 'current198-final158-native-control-keypress-only' if value.get('kind') == NATIVE_CONTROL_KEYPRESS_SOURCE_KIND else 'current198-final158-native-popup-capability-only' if value.get('kind') == NATIVE_POPUP_SOURCE_KIND else 'current198-final158-composition-only' if value.get('kind') == COMPOSITION_SOURCE_KIND else 'current197-final157-only', 'profile': {'path': str(root / PROFILE), 'sha256': profile_sha256},
        'source_map': current['source_facts'], 'overlays': {
            name: dict(value['inputs'][name]) for name in sorted(current['overlays'])},
        'graph': dict(profile['graph']), 'provenance': dict(profile['provenance']),
        'source_files': profile['source_files'], 'engine_files': profile['engine_files'],
        'direct_translation_units': profile['direct_translation_units'],
        'inputs': list(inputs.records), 'complete_original_source_admission': False,
        'source_tree_assembled': False, 'production_eligible': False}
    result = object.__new__(CheckedCurrentSources)
    object.__setattr__(result, '_token', _CHECKED_CURRENT_SOURCE_TOKEN)
    object.__setattr__(result, '_owner', inputs)
    object.__setattr__(result, '_view', json.dumps(facts, sort_keys=True, allow_nan=False))
    object.__setattr__(result, '_entries', json.dumps(value['inputs'], sort_keys=True, allow_nan=False))
    object.__setattr__(result, '_overlays', overlay_bytes)
    object.__setattr__(result, '_deadline', deadline)
    inputs.recheck()
    inputs.check_deadline()
    if time.monotonic() >= deadline:
        raise ValueError('Checked current source deadline expired')
    return result


class CheckedNativeSourceComposition:
    """Checked original plus current source operations; never assembled output."""
    __slots__ = ('_token', '_original', '_current', '_view', '_deadline')

    def __new__(cls, *args, **kwargs):
        raise TypeError('Checked composition is created only by the source composition join')

    def __setattr__(self, name, value):
        raise AttributeError('Checked source composition is immutable')

    def as_dict(self):
        if (getattr(self, '_token', None) is not _CHECKED_COMPOSITION_TOKEN
                or time.monotonic() >= self._deadline):
            raise ValueError('Invalid or expired checked native source composition')
        result = json.loads(self._view)
        if time.monotonic() >= self._deadline:
            raise ValueError('Checked native source composition deadline expired')
        return result


def compose_native_sources(original, current, provenance_records, original_proof_records):
    """Pure join over actual checked captures; no path open or archive replay.

    Existing clean-body and retained-body provenance formats remain valid;
    only the retained-body format requires the seven captured original refs.
    """
    if (type(original) is not CheckedSourceProjection
            or getattr(original, '_token', None) is not _CHECKED_SOURCE_TOKEN
            or type(current) is not CheckedCurrentSources
            or getattr(current, '_token', None) is not _CHECKED_CURRENT_SOURCE_TOKEN):
        raise ValueError('Actual original and current source captures required')
    deadline = min(original._deadline, current._deadline)
    if time.monotonic() >= deadline:
        raise ValueError('Checked native source composition deadline expired')
    original_facts = validate_source_provenance_records(original, provenance_records, original_proof_records)
    baseline = original.as_dict()
    current_facts = current.as_dict()
    entries = json.loads(current._entries)
    _forward_patch_contract(baseline, entries)
    facts = {'schema_version': 1, 'kind': 'foundation-native-source-composition-v1',
        'scope': 'checked-original-plus-current-source-operations-only',
        'original_provenance': original_facts, 'current_sources': current_facts,
        'original_projection_files': len(baseline['_files']),
        'operations': ['clean-original-projection', 'supplier-f259-once',
            'final158-retired-form-preflight-current-overlays' if current_facts.get('scope') == 'current198-final158-retired-form-preflight-only' else 'final158-native-input-method-current-overlays' if current_facts.get('scope') == 'current198-final158-native-input-method-only' else 'final158-native-select-events-current-overlays' if current_facts.get('scope') == 'current198-final158-native-select-events-only' else 'final158-native-control-includes-current-overlays' if current_facts.get('scope') == 'current198-final158-native-control-includes-only' else 'final158-native-control-keypress-current-overlays' if current_facts.get('scope') == 'current198-final158-native-control-keypress-only' else 'final158-native-popup-capability-current-overlays' if current_facts.get('scope') == 'current198-final158-native-popup-capability-only' else 'final158-composition-current-overlays' if current_facts.get('scope') == 'current198-final158-composition-only' else 'final157-current-overlays'],
        'patches': _public(baseline['patches']), 'overlays': current_facts['overlays'],
        'source_tree_assembled': False, 'production_eligible': False,
        'compiler_or_sdk_used': False}
    result = object.__new__(CheckedNativeSourceComposition)
    object.__setattr__(result, '_token', _CHECKED_COMPOSITION_TOKEN)
    object.__setattr__(result, '_original', original)
    object.__setattr__(result, '_current', current)
    object.__setattr__(result, '_view', json.dumps(facts, sort_keys=True, allow_nan=False))
    object.__setattr__(result, '_deadline', deadline)
    if time.monotonic() >= deadline:
        raise ValueError('Checked native source composition deadline expired')
    return result


def inspect_selection(selection_path, selection_sha256, *, repository_root=ROOT):
    if os.name != 'posix':
        raise ValueError('Native input preparation requires qualified POSIX modes; Windows needs the unfinished two-host publication join')
    root = _ordinary(_absolute(repository_root), True)
    path = _absolute(selection_path)
    inputs = InputSet()
    inputs.file(path, pin(selection_sha256, 'native selection'), 'selection', maximum=MAX_DOCUMENT)
    selection = strict_json(inputs.bytes(path), 'native selection')
    _schema(selection, ('schema_version', 'kind', 'target', 'profile', 'source_map', 'source_projection',
        'toolchain', 'dependencies', 'host_tools', 'assets', 'phase_limits'), 'foundation-native-engine-prototype-selection-v1')
    target = validate_target(selection['target'])
    if selection['profile'] != actions.SELECTOR:
        raise ValueError('Native actions profile must be explicitly document-actions-v1')
    limits = validate_phase_limits(selection['phase_limits'])
    inputs.deadline = time.monotonic() + limits['prepare_seconds']
    documents, paths = {}, {}
    missing = []
    for role in ('source_map', 'source_projection', 'toolchain', 'dependencies', 'host_tools', 'assets'):
        document_path, document_pin = _ref(selection[role], path.parent)
        paths[role] = document_path
        try:
            inputs.file(document_path, document_pin, role + '-manifest', maximum=MAX_DOCUMENT)
        except MissingInputs as error:
            missing.extend(error.missing)
    if missing:
        raise MissingInputs(missing)
    for role, document_path in paths.items():
        documents[role] = strict_json(inputs.bytes(document_path), role)
    profile_path = root / PROFILE
    try:
        _ordinary(profile_path)
    except FileNotFoundError as error:
        raise MissingInputs([{'role': 'native-producer-profile', 'path': str(profile_path), 'reason': 'new exact source producer profile absent'}]) from error
    # The profile is part of the calling producer source; its bytes are retained
    # in R. Its independently pinned map/provenance bind the old source recipe.
    profile_raw = _producer_bytes(inputs, profile_path, 'producer-profile', root)
    profile = strict_json(profile_raw, 'native producer profile')
    _schema(profile, ('schema_version', 'kind', 'target', 'profile', 'scope', 'recipe_directory',
        'source_map', 'provenance', 'graph', 'source_files', 'direct_translation_units', 'engine_files',
        'producer_inputs', 'required_toolchain_kind'), NATIVE_FORM_PREFLIGHT_PROFILE_KIND if profile.get('kind') == NATIVE_FORM_PREFLIGHT_PROFILE_KIND else NATIVE_INPUT_METHOD_PROFILE_KIND if profile.get('kind') == NATIVE_INPUT_METHOD_PROFILE_KIND else NATIVE_SELECT_EVENTS_PROFILE_KIND if profile.get('kind') == NATIVE_SELECT_EVENTS_PROFILE_KIND else NATIVE_SHOWPICKER_PROFILE_KIND if profile.get('kind') == NATIVE_SHOWPICKER_PROFILE_KIND else NATIVE_CONTROL_INCLUDES_PROFILE_KIND if profile.get('kind') == NATIVE_CONTROL_INCLUDES_PROFILE_KIND else NATIVE_CONTROL_KEYPRESS_PROFILE_KIND if profile.get('kind') == NATIVE_CONTROL_KEYPRESS_PROFILE_KIND else NATIVE_POPUP_PROFILE_KIND if profile.get('kind') == NATIVE_POPUP_PROFILE_KIND else COMPOSITION_PROFILE_KIND if profile.get('kind') == COMPOSITION_PROFILE_KIND else 'foundation-native-engine-prototype-profile-v1')
    if (profile['target'] != target or profile['profile'] != actions.SELECTOR
            or profile['scope'] != 'first-native-engine-baseline-candidate' or profile['recipe_directory'] != RECIPE
            or profile['producer_inputs'] != list(PRODUCERS) or profile['required_toolchain_kind'] != PRIVATE_TOOLCHAIN_KIND):
        raise ValueError('Native producer source profile changed or unsupported')
    if type(documents['toolchain']) is not dict or documents['toolchain'].get('kind') != PRIVATE_TOOLCHAIN_KIND:
        raise MissingInputs([{'role': 'private-sdk-toolchain', 'path': str(paths['toolchain']),
            'reason': 'explicit private runtime selection required by current native producer profile'}])
    current = _capture_current_sources_core(profile, documents['source_map'],
        selection['source_map']['sha256'], root, inputs)
    source_facts, source_entries = current['source_facts'], current['source_entries']
    retained, overlays = current['retained'], current['overlays']
    map_path, map_pin = current['map_path'], current['map_pin']
    def retain(name, original, role):
        _retain_current_source(retained, name, original, role, inputs)
    toolchain = parse_toolchain(documents['toolchain'], paths['toolchain'].parent, inputs, target, repository_root=root)
    host = parse_host_tools(documents['host_tools'], paths['host_tools'].parent, inputs, toolchain, repository_root=root)
    assets = parse_assets(documents['assets'], paths['assets'].parent, inputs, target)
    dependencies = parse_dependencies(documents['dependencies'], paths['dependencies'].parent, inputs, target,
        toolchain, {'path': str(paths['assets']), 'sha256': selection['assets']['sha256']})
    projection = parse_source_projection(documents['source_projection'], paths['source_projection'].parent, inputs, target)
    projection['_provenance_join'] = validate_source_provenance(projection, inputs)
    environment = render_environment(toolchain, host)
    _forward_patch_contract(projection, source_entries)
    recipe_patches = []
    for number, item in enumerate(projection['patches']):
        name = 'ordered-patches/' + str(number).zfill(3) + '.patch'
        retain(name, Path(item['path']), 'patch')
        recipe_patches.append(dict(item, path=name))
        recipe_patches[-1].pop('sha256')
    suppliers, archive_names = {}, {}
    for name, archive in sorted(projection['archives'].items()):
        logical = 'supplier-archives/' + name + '.' + {'tar-gzip': 'tar.gz', 'tar-xz': 'tar.xz', 'zip': 'zip'}[archive['format']]
        retain(logical, Path(archive['path']), 'source')
        archive_names[name] = logical
    for name, item in projection['suppliers'].items():
        suppliers[name] = dict(item, archive=archive_names[item['archive']])
    for role, document_path in paths.items():
        retain('native-inputs/' + role + '.json', document_path, 'config')
    retain('native-inputs/canonical-source-map.json', map_path, 'config')
    retain('native-inputs/selection.json', path, 'config')
    primary = toolchain['inventories']['toolchain']
    retain('native-inputs/toolchain-identity.json', Path(primary['root']) / 'identity.json', 'config')
    for name, original, role in _record_aliases(inputs.records):
        retain(name, original, role)
    programs = dict(toolchain['tools'])
    programs.update(host['programs'])
    data = {'schema_version': 1, 'kind': 'foundation-native-engine-prototype-input-inspection-v1', 'scope': SCOPE,
        'selection': {'path': str(path), 'sha256': selection_sha256}, 'target': target, 'profile': actions.SELECTOR,
        'inputs': list(inputs.records), 'source_map': source_facts, 'source_projection': _public(projection),
        'toolchain': toolchain, 'dependencies': dependencies, 'host_tools': host, 'assets': assets,
        'phase_limits': limits, 'programs': programs, 'environment': environment,
        'needed_libraries': list(toolchain['runtime']['needed_libraries']),
        'production_eligible': False, 'engine_execution': False, 'kernel_rebuild': False}
    if inputs.sdk_directory_records:
        data['sdk_directory_facts'] = list(inputs.sdk_directory_records)
    inputs.recheck()
    return Inspection(data, inputs, retained, projection, overlays, suppliers, recipe_patches)


@dataclass(frozen=True)
class Prepared:
    _data: dict
    _cmake: dict

    def as_dict(self):
        return dict(self._data)

    @property
    def cmake(self):
        return dict(self._cmake)


def _save_new(root, name, raw, mode=0o644, *, deadline=None):
    path = root / _name(name)
    current = root
    for part in path.relative_to(root).parts[:-1]:
        current = current / part
        try:
            current.mkdir(mode=0o755)
            descriptor = os.open(current, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fchmod(descriptor, 0o755)
            finally:
                os.close(descriptor)
        except FileExistsError:
            _ordinary(current, True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(descriptor, 'wb') as stream:
        for offset in range(0, len(raw), 1024 * 1024):
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError('Native source publication deadline expired')
            stream.write(memoryview(raw)[offset:offset + 1024 * 1024])
        stream.flush()
        os.fchmod(stream.fileno(), mode)
    return path


def _copy_new(root, name, original, record, inputs):
    inputs.check_deadline()
    authority = inputs._repository_sources.get(str(original))
    if authority is None:
        inputs.file(original, record['sha256'], 'assembly-copy')
    else:
        source_root, names = authority
        inputs.repository_file(original, record['sha256'], 'assembly-copy', repository_root=source_root, source_paths=names)
    destination = root / _name(name)
    parent = destination.parent
    current = root
    for part in parent.relative_to(root).parts:
        current = current / part
        try:
            current.mkdir(mode=0o755)
            descriptor = os.open(current, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fchmod(descriptor, 0o755)
            finally:
                os.close(descriptor)
        except FileExistsError:
            _ordinary(current, True)
    before = inputs._identities[str(original)]
    source_descriptor = os.open(original, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    destination_descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, record['mode'])
    digest = hashlib.sha256()
    count = 0
    with os.fdopen(source_descriptor, 'rb') as source, os.fdopen(destination_descriptor, 'wb') as output:
        if _identity(os.fstat(source.fileno())) != before:
            raise ValueError('Native retained source changed before private copy')
        while True:
            inputs.check_deadline()
            block = source.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            if count > MAX_FILE or count > before[4]:
                raise ValueError('Native retained copy exceeds original byte bound')
            digest.update(block)
            output.write(block)
        output.flush()
        os.fchmod(output.fileno(), record['mode'])
        if _identity(os.fstat(source.fileno())) != before:
            raise ValueError('Native retained source changed during private copy')
    if count != before[4] or digest.hexdigest() != record['sha256'] or _identity(original.lstat()) != before:
        raise ValueError('Native private copy differs from admitted source bytes')


def _fresh_directory(output, protected):
    if (os.name != 'posix' or not all(hasattr(os, name) for name in ('O_NOFOLLOW', 'O_DIRECTORY', 'fchmod', 'geteuid'))):
        raise ValueError('Native source preparation needs qualified POSIX publication primitives')
    output = _absolute(output)
    _ordinary(output.parent, True)
    for path in protected:
        if path == output or path in output.parents or output in path.parents:
            raise ValueError('Native source output overlaps an admitted input: ' + str(path))
    try:
        output.mkdir(mode=0o700)
    except FileExistsError:
        _ordinary(output, True)
        if output.lstat().st_uid != os.geteuid() or stat.S_IMODE(output.lstat().st_mode) != 0o700 or any(output.iterdir()):
            raise ValueError('Native preparation requires a fresh or empty private owned0700 output directory')
    return output


def _project_sources(inspection, assembled):
    inputs = inspection._inputs
    projection = inspection._projection
    # Read only one regular member at a time. Alias destinations share its
    # immutable bytes in memory only during this iteration, never hardlinks.
    targets = {}
    for destination, item in projection['_files'].items():
        targets.setdefault((item['archive_path'], item['regular_member']), []).append((destination, item))
    for key, archive in sorted(projection['archives'].items()):
        path = Path(archive['path'])
        inputs.file(path, archive['sha256'], 'assembly-source-archive')
        for raw_name, kind, mode, size, link, stream in _archive_entries(path, archive['format']):
            inputs.check_deadline()
            name = _member_name(raw_name, archive['strip_prefix'])
            chosen = targets.get((str(path), name), ())
            if not chosen or kind != 'file':
                continue
            if size > MAX_MEMBER:
                raise ValueError('Native source member exceeds assembly buffer bound')
            chunks, count = [], 0
            while True:
                inputs.check_deadline()
                block = stream.read(min(1024 * 1024, size - count + 1))
                if not block:
                    break
                count += len(block)
                if count > size:
                    raise ValueError('Native source member grew during assembly')
                chunks.append(block)
            body = b''.join(chunks)
            for destination, item in chosen:
                if len(body) != item['bytes'] or sha256(body) != item['sha256']:
                    raise ValueError('Native source bytes changed during assembly')
                _save_new(assembled, destination, body, item['mode'], deadline=inputs.deadline)
    for destination, item in projection['_files'].items():
        if not (assembled / destination).is_file():
            raise ValueError('Native assembly omitted an admitted projected file')
    for item in projection['patches']:
        inputs.check_deadline()
        tree = assembled / 'source' / item['tree']
        originals = {}
        original_bytes = 0
        for name, image in item['preimages'].items():
            original = tree / name
            if image is not None:
                _ordinary(original)
                original_bytes += original.stat().st_size
                if original_bytes > MAX_MEMBER:
                    raise ValueError('Native patch source images exceed bounded patch buffer size')
                originals[name] = original.read_bytes()
            elif original.exists():
                raise ValueError('Native patch addition already exists')
        patched = apply_unified_patch(originals, inputs.bytes(Path(item['path'])), item['preimages'], item['postimages'])
        for name, image in item['postimages'].items():
            original = tree / name
            mode = stat.S_IMODE(original.stat().st_mode) if original.exists() else 0o644
            if original.exists():
                original.unlink()
            if image is not None:
                _save_new(tree, name, patched[name], mode, deadline=inputs.deadline)
    # All overlays are exact current source-map bytes and are copied only after
    # supplier patches. They are application source, not backend discovery.
    for name, original in sorted(inspection._overlays.items()):
        inputs.check_deadline()
        destination = assembled / name
        if destination.exists():
            _ordinary(destination)
            destination.unlink()
        _copy_new(assembled, name, original, inputs._records[str(original)], inputs)


def assemble(inspection, fresh_directory):
    if type(inspection) is not Inspection:
        raise ValueError('Native assembly requires an actual validated Inspection')
    inputs = inspection._inputs
    # A later build has its own explicit preparation allowance, independent of
    # the earlier passive inspection's completed monotonic deadline.
    inputs.deadline = time.monotonic() + inspection.phase_limits['prepare_seconds']
    inspection.recheck()
    recipe = {'schema_version': 1, 'kind': 'foundation-appended-engine-recipe', 'producer_version': 1,
        'target': inspection._data['target'], 'toolchain': inspection._data['toolchain']['identity'],
        'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'native'},
        'provider': {'format': 'native-shared', 'binding': 'c-abi', 'abi_major': 1, 'abi_minor': 1,
            'header': 'include/foundation/appended/engine_provider.h', 'header_sha256': actions.BASE_HEADER_SHA256},
        'suppliers': inspection._recipe_suppliers,
        'inputs': {name: {key: item[key] for key in ('sha256', 'role', 'mode')} for name, item in sorted(inspection._retained.items())},
        'patches': inspection._recipe_patches,
        'licenses': sorted(name for name, item in inspection._retained.items() if item['role'] == 'license')}
    manifest.recipe_contract(recipe)
    runtime = inspection._data['toolchain'].get('private_runtime')
    runtime_alias = None
    if runtime is not None:
        runtime_alias = 'native-inputs/records/' + pin(runtime['record']['sha256'], 'private runtime selection') + '.bin'
        if recipe['inputs'].get(runtime_alias) != {'sha256': runtime['record']['sha256'], 'role': 'data', 'mode': 0o644}:
            raise ValueError('Private runtime selection requires its exact ordinary retained DATA alias')
    recipe_raw = encoded(recipe)
    recipe_sha = sha256(recipe_raw)
    file_hashes = {name: item['sha256'] for name, item in recipe['inputs'].items()}
    file_hashes['recipe.json'] = recipe_sha
    directories = set()
    for name in file_hashes:
        directories.update(parent.as_posix() for parent in Path(name).parents if parent.as_posix() != '.')
    modes = {name: 0o755 for name in directories}
    modes.update({name: item['mode'] for name, item in recipe['inputs'].items()})
    modes['recipe.json'] = 0o644
    inventory = {'files': file_hashes, 'directories': sorted(directories), 'modes': modes}
    sources = dict(inventory, schema_version=1, kind='foundation-appended-engine-sources', producer_version=1, recipe_id=recipe_sha)
    manifest.source_contract(sources, recipe, recipe_sha)
    source_raw = encoded(sources)
    if (len(inspection._retained) + 3 + len(directories) > MAX_FILES or len(recipe_raw) > MAX_DOCUMENT or len(source_raw) > MAX_DOCUMENT
            or sum(inputs._records[item['path']]['bytes'] for item in inspection._retained.values())
            + len(recipe_raw) + len(source_raw) > MAX_BYTES):
        raise ValueError('Retained R/S aggregate including every copied alias exceeds declared bounds before output')
    expected_config = {'schema_version': 1, 'kind': 'foundation-native-provider-actions-prelink-config-v1',
        'document_profile': actions.PROFILE_NAME, 'profile_kind': 4, 'provider_limits': dict(actions.PROVIDER_LIMITS),
        'service_retention': {'max_retained_bytes': 4194304, 'max_retained_calls': 64}}
    config_source = Path(inspection._retained['source/native/prelink-actions-config.json']['path'])
    actual_config = strict_json(inputs.bytes(config_source))
    if encoded(actual_config) != encoded(expected_config):
        raise ValueError('Native actions retained config differs from fixed profile4/4083/allten limits')
    build = {'schema_version': 1, 'kind': actions.BUILD_KIND, 'target': recipe['target'],
        'toolchain': recipe['toolchain'], 'options': recipe['options'], 'source_recipe_sha256': recipe_sha,
        'source_inputs_sha256': sha256(encoded(recipe['inputs'])), 'contract_header_sha256': actions.CONTRACT_SHA256,
        'binding': actions.BINDING, 'configuration': actions.expected_configuration(actions_profile=actions.SELECTOR),
        'capabilities': '4083', 'provider_contract': actions.provider_contract(kernel_target=recipe['target'], actions_profile=actions.SELECTOR),
        'provider_limits': dict(actions.PROVIDER_LIMITS)}
    _fields(build, actions.BUILD_FIELDS, 'original13-field native provider build')
    build_raw = encoded(build)
    inputs.check_deadline()
    output = _fresh_directory(fresh_directory, inspection.protected_paths)
    retained, assembled, metadata = output / 'retained', output / 'assembled', output / 'metadata'
    for directory in (retained, assembled, metadata):
        directory.mkdir(mode=0o755)
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fchmod(descriptor, 0o755)
        finally:
            os.close(descriptor)
    for name, item in sorted(inspection._retained.items()):
        _copy_new(retained, name, Path(item['path']), item, inputs)
    _save_new(retained, 'recipe.json', recipe_raw, deadline=inputs.deadline)
    _save_new(retained, 'sources.json', source_raw, deadline=inputs.deadline)
    _project_sources(inspection, assembled)
    _save_new(metadata, 'provider-build.json', build_raw, deadline=inputs.deadline)
    inputs.check_deadline()
    # Reuse the complete inventory/schema contracts, with the bounded streaming
    # reader for physical verification. The ordinary helper's tree hash has no
    # mid-file deadline hook, so it is deliberately not called for large R.
    complete_inventory = {'files': dict(file_hashes, **{'sources.json': sha256(source_raw)}),
        'directories': sorted(directories), 'modes': dict(modes, **{'sources.json': 0o644})}
    inventory_raw = encoded(complete_inventory)
    _save_new(metadata, 'retained-inventory.json', inventory_raw, deadline=inputs.deadline)
    verified = InputSet()
    verified.deadline = inputs.deadline
    verified.inventory({'root': str(retained), 'inventory': {'path': 'retained-inventory.json', 'sha256': sha256(inventory_raw)}}, metadata, 'prepared-native-R-S')
    inspection.recheck()
    values = inspection.cmake
    if runtime_alias is not None:
        values['BIB_NATIVE_RUNTIME_SELECTION_PATH'] = str(retained / runtime_alias)
    binding = 'source/document-provider/runtime/BibNativeDocumentActionsBinding.cpp'
    header = 'source/native/BibNativeProviderBootstrap.hpp'
    for name in (binding, header):
        binding_check = InputSet()
        binding_check.deadline = inputs.deadline
        binding_check.file(assembled / name, inspection._retained[name]['sha256'], 'prepared-native-binding')
    values.update({'BIB_NATIVE_PROVIDER_SOURCE_ROOT': str(assembled),
        'BIB_NATIVE_PROVIDER_BINDING_SOURCE': str(assembled / binding),
        'BIB_NATIVE_PROVIDER_BINDING_SOURCE_SHA256': inspection._retained[binding]['sha256'],
        'BIB_NATIVE_PROVIDER_BINDING_HEADER': str(assembled / header),
        'BIB_NATIVE_PROVIDER_BINDING_HEADER_SHA256': inspection._retained[header]['sha256'],
        'BIB_NATIVE_EMBEDDER_CMAKE': str(retained / 'cmake/native-provider.cmake')})
    result = {'retained_root': str(retained), 'assembled_root': str(assembled),
        'provider_build_path': str(metadata / 'provider-build.json'), 'recipe_sha256': recipe_sha,
        'sources_sha256': sha256(source_raw), 'provider_build_sha256': sha256(build_raw)}
    return Prepared(result, values)
