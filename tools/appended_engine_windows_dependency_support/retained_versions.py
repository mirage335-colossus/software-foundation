"""Reconstruct retained tool observations through fixed original/native readers.

Only the actual native factory may populate a production closed context. Pure
schema checks and fixture-owned flows cannot issue an observed-version token.
Native dependencies are deliberately lazy; importing this source performs no
selected input read, Workspace creation, process launch or native operation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import platform
import re
import struct
import time
import unicodedata


REQUEST_KIND = 'private-windows-retained-tool-observations-v2'
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
ENGINE_ROLES = ('compiler', 'linker', 'archiver', 'resource_compiler',
                'manifest_tool', 'cmake', 'ninja', 'python', 'perl', 'ruby', 'gperf')
H2_ROLES = ENGINE_ROLES + ('nmake', 'msbuild')
RESOURCE_ROLES = ('archiver', 'resource_compiler', 'manifest_tool')
_RESOURCE_NAMES = {'parser': 'resource/llvm_version.py',
    'codec': 'nmake_version.py',
    'emitter': 'resource/llvm_version_emitter.py'}
INVENTORY_ROLES = ('llvm', 'msvc_stl', 'windows_sdk', 'host_generators')
PROGRAM_NAMES = {'compiler': 'clang-cl.exe', 'linker': 'lld-link.exe',
    'archiver': 'llvm-lib.exe', 'resource_compiler': 'llvm-rc.exe',
    'manifest_tool': 'llvm-mt.exe', 'cmake': 'cmake.exe', 'ninja': 'ninja.exe',
    'python': 'python.exe', 'perl': 'perl.exe', 'ruby': 'ruby.exe', 'gperf': 'gperf.exe',
    'nmake': 'nmake.exe', 'msbuild': 'MSBuild.exe'}
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_CACHED_BYTES = 256 * 1024 * 1024
_LIMIT_BOUNDS = {'seconds': 86400, 'maximum_archive_bytes': 8 * 1024 ** 3,
    'maximum_expanded_bytes': 32 * 1024 ** 3, 'maximum_members': 1000000,
    'maximum_member_bytes': 256 * 1024 ** 2, 'maximum_patch_bytes': 32 * 1024 ** 2}
_CLOSED = {}
_LIVE = set()
_UNCERTAIN = []


class RetainedDataError(ValueError):
    code = 'DATA'


class RetainedSourceError(ValueError):
    code = 'SOURCE'


class RetainedOwnershipUncertain(ValueError):
    code = 'OWNERSHIP_UNCERTAIN'


def _fields(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise RetainedSourceError('Unsupported ' + label + ' fields')
    return value


def _pin(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None or value == '0' * 64:
        raise RetainedDataError('An exact nonzero SHA256 is required')
    return value


def _absolute(value):
    if type(value) is not str or not 4 <= len(value) <= 4096:
        raise RetainedSourceError('An absolute canonical Windows path is required')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise RetainedSourceError('A well-formed Unicode Windows path is required') from error
    path = PureWindowsPath(value)
    if (not re.match('^[A-Z]:/', value) or not path.is_absolute() or
            path.as_posix() != value or unicodedata.normalize('NFC', value) != value or
            any(c in value for c in ('\\', ';', '"', '$', '@'))):
        raise RetainedSourceError('An absolute canonical Windows path is required')
    for part in path.parts[1:]:
        if (part in ('.', '..') or part.endswith((' ', '.')) or
                any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in ':<>|?*' for c in part) or
                re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', part)):
            raise RetainedSourceError('Aliased/unsupported Windows input path')
    return value


def _ref(value, *, body=False):
    _fields(value, ('path', 'sha256', 'bytes', 'mode') if body else ('path', 'sha256'), 'retained reference')
    _absolute(value['path']); _pin(value['sha256'])
    if body and (type(value['bytes']) is not int or not 0 <= value['bytes'] <= _LIMIT_BOUNDS['maximum_member_bytes'] or
                 type(value['mode']) is not int or value['mode'] != 0o644):
        raise RetainedDataError('Bounded exact body bytes and logical 0644 are required')
    return copy.deepcopy(value)


def _encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('utf-8')


def _owned_equal(left, right):
    """Exact owned-data equality; bytes stay bytes and numeric aliases reject."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        if (any(type(key) is not str for key in left) or
                any(type(key) is not str for key in right) or set(left) != set(right)):
            return False
        return all(_owned_equal(left[key], right[key]) for key in left)
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(_owned_equal(a, b) for a, b in zip(left, right))
    if type(left) in (str, bytes, int, bool, type(None)):
        return left == right
    return False


def _document(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_DOCUMENT:
        raise RetainedDataError('A bounded original JSON document is required')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise RetainedDataError('Duplicate retained JSON field')
            result[key] = value
        return result
    def bad(_): raise RetainedDataError('Nonfinite retained JSON')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)
        _encoded(result)
        return result
    except RetainedDataError:
        raise
    except (UnicodeError, RecursionError, OverflowError, json.JSONDecodeError, ValueError) as error:
        raise RetainedDataError('Invalid retained JSON encoding/nesting') from error


def _target(value):
    _fields(value, TARGET, 'retained target')
    if any(type(value[name]) is not type(expected) or value[name] != expected for name, expected in TARGET.items()):
        raise RetainedDataError('Retained input target differs from Windows x64')


def _request(value):
    _fields(value, ('schema_version', 'kind', 'target', 'selection', 'batch', 'originals'), 'retained version request')
    if type(value['schema_version']) is not int or value['schema_version'] != 2 or value['kind'] != REQUEST_KIND:
        raise RetainedSourceError('Only exact retained observation request schema 2 is implemented')
    _target(value['target'])
    _ref(value['selection'], body=True); _ref(value['batch'], body=True); _ref(value['originals'])
    if value['selection']['path'].casefold() == value['batch']['path'].casefold():
        raise RetainedDataError('Selection and batch need distinct original paths')
    return copy.deepcopy(value)


def _selection(value):
    if type(value) is not dict:
        raise RetainedSourceError('Original retained selection object required')
    fields = ('schema_version', 'kind', 'target', 'programs', 'inventories',
              'source_root', 'sources', 'publication', 'input')
    _fields(value, fields + (('runtime_profiles',) if value.get('schema_version') == 2 else ()),
            'retained tool selection')
    schema = value['schema_version']
    if type(schema) is not int or schema not in (1, 2) or value['kind'] != 'private-windows-tool-version-selection-v' + str(schema):
        raise RetainedSourceError('Mixed/unsupported retained tool selection schema/kind')
    _target(value['target'])
    roles = ENGINE_ROLES if schema == 1 else H2_ROLES
    _fields(value['programs'], roles, 'retained program role map')
    aliases = {}
    def unique(reference, label):
        reference = _ref(reference, body=True)
        key = reference['path'].casefold()
        if key in aliases and aliases[key] != reference:
            raise RetainedDataError('Conflicting retained path/reference: ' + label)
        aliases[key] = reference
    for role in roles:
        unique(value['programs'][role], role)
        if value['programs'][role]['path'].rsplit('/', 1)[-1] != PROGRAM_NAMES[role]:
            raise RetainedDataError('Original program basename differs from exact role: ' + role)
    _fields(value['inventories'], INVENTORY_ROLES, 'retained inventory role map')
    for role in INVENTORY_ROLES:
        row = _fields(value['inventories'][role], ('reference', 'root', 'subject_sha256'), 'retained inventory selection')
        unique(row['reference'], role + ' inventory')
        _absolute(row['root']); _pin(row['subject_sha256'])
    _absolute(value['source_root'])
    if type(value['sources']) is not list or not 1 <= len(value['sources']) <= 128:
        raise RetainedDataError('A finite nonempty original collector/method source set is required')
    source_names = set()
    for row in value['sources']:
        unique(row, 'source')
        if row['path'].casefold() in source_names:
            raise RetainedDataError('Repeated retained source reference')
        source_names.add(row['path'].casefold())
        if not row['path'].startswith(value['source_root'] + '/'):
            raise RetainedDataError('Original collector source escapes its selected root')
    # Publication and historical input admission stay historical. Their exact
    # collector/source/runtime shape belongs to the fixed observation checker.
    for name in ('publication', 'input'):
        subject = _fields(value[name], ('qualification', 'source_identity', 'runtime_identity'),
                          'historical ' + name + ' subject')
        _ref(subject['qualification'])
        if type(subject['source_identity']) is not dict or not subject['source_identity']:
            raise RetainedSourceError('Complete historical A source identity is required')
        for digest in subject['source_identity'].values(): _pin(digest)
        if type(subject['runtime_identity']) is not dict:
            raise RetainedSourceError('Historical A runtime identity object required')
    if schema == 2:
        _fields(value['runtime_profiles'], ('nmake', 'msbuild'), 'selected original runtime profiles')
        host_root = value['inventories']['host_generators']['root'].casefold()
        seen_profiles = set()
        for role in ('nmake', 'msbuild'):
            profile = _ref(value['runtime_profiles'][role], body=True)
            if not 1 <= profile['bytes'] <= 2 * 1024 * 1024:
                raise RetainedDataError('Original runtime profile must have 1..2 MiB bytes')
            name = profile['path'].casefold()
            if name == host_root or name.startswith(host_root + '/'):
                raise RetainedDataError('Runtime profile must be outside its host inventory to avoid a self-hash')
            if name in seen_profiles:
                raise RetainedDataError('Original NMake/MSBuild profiles must have distinct paths')
            seen_profiles.add(name)
    return copy.deepcopy(value)


def _batch(value, selection):
    schema = selection['schema_version']
    fields = ('schema_version', 'kind', 'target', 'collector', 'inventory_subjects',
              'observations', 'inventories', 'inventory_release_evidence')
    _fields(value, fields + (('runtime_profiles',) if schema == 2 else ()), 'retained observation batch')
    if type(value['schema_version']) is not int or value['schema_version'] != schema or value['kind'] != 'foundation-native-engine-windows-tool-version-batch-v' + str(schema):
        raise RetainedSourceError('Batch/selection schema must preserve exact v1 eleven or v2 thirteen roles')
    _target(value['target'])
    roles = ENGINE_ROLES if schema == 1 else H2_ROLES
    _fields(value['observations'], roles, 'retained observation map')
    _fields(value['inventory_subjects'], INVENTORY_ROLES, 'retained inventory subjects')
    for role in INVENTORY_ROLES:
        _pin(value['inventory_subjects'][role])
        if value['inventory_subjects'][role] != selection['inventories'][role]['subject_sha256']:
            raise RetainedDataError('Batch/selection inventory subject differs: ' + role)
    for role in roles: _ref(value['observations'][role])
    if schema == 2: _runtime_binding(value['runtime_profiles'], selection)
    return copy.deepcopy(value)


def _runtime_binding(value, selection):
    _fields(value, ('nmake', 'msbuild'), 'original runtime profile binding')
    for role in ('nmake', 'msbuild'):
        row = _fields(value[role], ('reference', 'subject_sha256'), 'original runtime profile subject')
        _ref(row['reference'], body=True); _pin(row['subject_sha256'])
        if row['reference'] != selection['runtime_profiles'][role]:
            raise RetainedDataError('Original runtime profile reference differs from selection: ' + role)
    return copy.deepcopy(value)


def _arguments(request_ref, deadline, limits):
    _ref(request_ref)
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or time.monotonic() >= deadline:
        raise RetainedDataError('An unexpired finite absolute monotonic deadline is required')
    _fields(limits, _LIMIT_BOUNDS, 'retained input limits')
    if any(type(limits[key]) is not int or not 1 <= limits[key] <= maximum for key, maximum in _LIMIT_BOUNDS.items()):
        raise RetainedDataError('Retained input limits exceed the fixed finite domain')
    return copy.deepcopy(limits)


def _native_guard():
    if (os.name != 'nt' or platform.system() != 'Windows' or
            platform.machine().casefold() not in ('amd64', 'x86_64') or struct.calcsize('P') != 8):
        raise RetainedSourceError('Actual native Windows x64 retained input semantics are required')


_PURE_RELEASES = {
    'runtime_host': ('runtime.py', 13990,
        '557801ca12c660cc81f78d79e77bfcfbfa41d84fae5284815636c8e45427c5ec'),
    'observation_runtime': ('observation_runtime.py', 6100,
        '061a0535dda535c31ecf340d645af773bdc52ccc9b8aa88fc9a190eddfc6e756'),
    'historical_publication': ('historical_publication.py', 13382,
        '966061803c511ffd6380621829e79f2108f89a6425530ef802f9112f8bec7cf1'),
    'native_inspection': ('native_inspection.py', 1914,
        '9b91a9a47598e37650c1d6f54ab64402b028452baf58ddfe9a321cad88c071e6'),
    'inventory': ('inventory.py', 1979,
        'b4480452a0a25821203f6ef9448eb9612d969bfd9d5540b92b26463e1a286d07'),
    'observation': ('observations.py', 10155,
        '1015d81599bf7823ea5c9df7c5477b12fd325e4b878e5189975b90dca13881c8'),
    'methods': ('methods.py', 9983,
        'ab6fad7a14c7d08e5980c8c4a61eda3a3e76a2e85d5ff7006a36fd296e54eefc'),
}
_PURE_MODULES = {}


def _pure_module(name):
    """Load only a fixed frozen pure source helper, never selected input code."""
    if name not in _PURE_RELEASES:
        raise RetainedSourceError('Unknown fixed retained data helper')
    if name not in _PURE_MODULES:
        import stat
        import types
        relative, expected_size, expected_sha = _PURE_RELEASES[name]
        source = Path(__file__).resolve().parent / relative
        try:
            with source.open('rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
                    raise RetainedSourceError('Fixed retained helper source type/size differs: ' + name)
                raw = stream.read(expected_size + 1)
                after = os.fstat(stream.fileno())
        except OSError as error:
            raise RetainedSourceError('Fixed retained helper source is absent: ' + name) from error
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode,
                                   value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if (identity(before) != identity(after) or len(raw) != expected_size or
                hashlib.sha256(raw).hexdigest() != expected_sha):
            raise RetainedSourceError('Fixed retained helper source SHA/identity differs: ' + name)
        module = types.ModuleType('_private_retained_' + name)
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _PURE_MODULES[name] = module
    return _PURE_MODULES[name]


def _core_module():
    """Resolve the one issuer instance; never execute another issuer registry."""
    import sys
    import types
    core = sys.modules.get('_foundation_windows_h2_native_issuer_v1')
    source = Path(__file__).resolve().parent / 'issuer.py'
    if (type(core) is not types.ModuleType or not getattr(core, '__file__', None) or
            Path(core.__file__).resolve() != source.resolve()):
        raise RetainedSourceError('The fixed sibling H2 issuer module is required')
    for name in ('_issue_retained_closed', '_inventory_provenance', '_data_module',
                 '_admit_runtime_profiles', '_retained_method_plan', '_retained_source_catalogue',
                 '_publication_checker', 'originals_module'):
        function = getattr(core, name, None)
        if not callable(function) or not hasattr(function, '__code__') or Path(function.__code__.co_filename).resolve() != source.resolve():
            raise RetainedSourceError('Unreviewed/replaced issuer retained seam: ' + name)
    return core


class _RetainedContext:
    """Actual fixed-factory input owner; constructing a dictionary is insufficient."""
    def __new__(cls, *args, **kwargs):
        raise RetainedSourceError('Use the actual retained-observation factory')

    def check_deadline(self):
        if time.monotonic() >= self.deadline:
            raise RetainedDataError('Shared retained observation deadline expired')

    def _reader(self, root):
        self.check_deadline()
        if self._state not in ('opening', 'open'):
            raise RetainedSourceError('Retained input context is not live')
        _absolute(root)
        if root not in self._owners:
            owner = self.native.AnchoredInputs.open_existing(root,
                qualification=self.input_q, limits=self.limits, deadline=self.deadline)
            self._owners[root] = owner  # Retain even a rejected returned owner.
            if type(owner) is not self.native.AnchoredInputs:
                raise RetainedSourceError('Actual qualified A.AnchoredInputs required')
            if root == self.origin_summary['root'] and owner.filesystem != self.origin_summary['input']['filesystem']:
                raise RetainedDataError('Current retained root volume differs from the original reader volume')
        return self._owners[root]

    def _membership(self, reference):
        reference = _ref(reference, body=set(reference) == {'path', 'sha256', 'bytes', 'mode'})
        selected = {key: reference[key] for key in ('path', 'sha256')}
        if 'bytes' in reference: selected['bytes'] = reference['bytes']
        facts = self.origin_module.require_original_membership(self.origin, [selected])
        if type(facts) is not list or len(facts) != 1 or not facts[0].get('origins'):
            raise RetainedDataError('Original source/observation member authority is absent')
        fact = facts[0]
        # The fixed lower accessor checks the member's exact original path/hash/
        # byte identity. Require actual original namespaces, never archive-only
        # evidence interpreted as a detached original body.
        names = {row['name']: row for row in self.origin_summary['origins']}
        for origin in fact['origins']:
            if origin.get('name') not in names or names[origin['name']]['kind'] != origin.get('kind'):
                raise RetainedDataError('Captured member has no selected original transport')
            member = origin.get('member')
            if type(member) is not str or not member or (origin['kind'] == 'base' and not member.startswith(('binary/', 'sources/'))):
                raise RetainedDataError('Detached original body must be a genuine payload/archive member')
        body = dict(fact['reference'], mode=0o644)
        _ref(body, body=True)
        if set(reference) == {'path', 'sha256', 'bytes', 'mode'} and body != reference:
            raise RetainedDataError('Independent original reference differs from membership')
        self._original_refs[body['path']] = {key: body[key] for key in ('path', 'sha256')}
        return body

    def _capture(self, reference, *, retain=False, root=None, use_tree=True):
        reference = _ref(reference, body=True)
        self.check_deadline()
        if self._state not in ('opening', 'open'):
            raise RetainedSourceError('Retained byte capture needs a live actual context')
        path = reference['path']
        if root is not None:
            _absolute(root)
            try: PureWindowsPath(path).relative_to(PureWindowsPath(root))
            except ValueError as error:
                raise RetainedDataError('Selected file escapes its explicit inventory root') from error
        alias = path.casefold()
        previous = self._files.get(alias)
        if previous is not None:
            if previous['reference'] != reference:
                raise RetainedDataError('Conflicting/aliased retained file selection')
            if root is None and (not retain or previous['raw'] is not None):
                return previous['raw']
        if retain and (previous is None or previous['raw'] is None) and self._retained_bytes + reference['bytes'] > MAX_CACHED_BYTES:
            raise RetainedDataError('Retained metadata/program byte cache exceeds 256-MiB bound')
        if reference['bytes'] > self.limits['maximum_member_bytes']:
            raise RetainedDataError('Selected retained body exceeds member bound')
        if previous is None:
            self._members += 1; self._bytes += reference['bytes']
            if self._members > self.limits['maximum_members'] or self._bytes > self.limits['maximum_expanded_bytes']:
                raise RetainedDataError('Retained selected file/byte aggregate exceeds limits')
        selected = PureWindowsPath(path)
        if root is None:
            original_root = self.origin_summary['root']
            try:
                relative = selected.relative_to(PureWindowsPath(original_root)).as_posix()
                root = original_root
            except ValueError:
                root, relative = selected.parent.as_posix(), selected.name
        else:
            try: relative = selected.relative_to(PureWindowsPath(root)).as_posix()
            except ValueError as error: raise RetainedDataError('Selected file escapes its complete inventory root') from error
        owner = self._reader(root)
        tree = self._trees.get(root) if use_tree else None
        stream = (tree.open_file(relative) if tree is not None else
            owner.open_archive(relative, expected={key: reference[key] for key in ('sha256', 'bytes', 'mode')}))
        self._streams.append(stream)
        digest, count, chunks = hashlib.sha256(), 0, []
        try:
            while True:
                self.check_deadline()
                block = stream.read(min(1024 * 1024, reference['bytes'] - count + 1))
                if type(block) is not bytes:
                    raise RetainedDataError('Actual native input stream returned non-bytes')
                if not block: break
                count += len(block)
                if count > reference['bytes']:
                    raise RetainedDataError('Retained file exceeds independently selected EOF')
                digest.update(block)
                if retain: chunks.append(block)
            if count != reference['bytes'] or digest.hexdigest() != reference['sha256']:
                raise RetainedDataError('Retained file bytes/SHA256 differ from the original inventory')
        finally:
            try:
                stream.close()
            except BaseException as error:
                self._state = 'uncertain'; _UNCERTAIN.append(self)
                raise RetainedOwnershipUncertain('Retain native stream/owner after unconfirmed close') from error
            else:
                self._streams.remove(stream)
        raw = b''.join(chunks) if retain else previous['raw'] if previous is not None else None
        if retain and (previous is None or previous['raw'] is None):
            self._retained_bytes += len(raw)
        self._files[alias] = {'reference': reference, 'raw': raw}
        return raw

    def read_input(self, reference):
        """Actual original document; its physical location grants no membership."""
        return self.read_original_body(reference, maximum=min(MAX_DOCUMENT, self.limits['maximum_patch_bytes']))

    def read_runtime_input(self, reference):
        """Actual selected/reached runtime body from one complete held inventory.

        Fixed runtime readers use this distinct seam only for program/runtime
        bodies. Every document uses read_input even when it is also an exact
        inventory member; no body dictionary can redirect this seam to Origin.
        """
        reference = _ref(reference, body=True)
        matches = []
        for facts in self.inventory_facts.values():
            try:
                relative = PureWindowsPath(reference['path']).relative_to(PureWindowsPath(facts['root'])).as_posix()
            except ValueError:
                continue
            if facts['files'].get(relative) == {key: reference[key] for key in ('sha256', 'bytes')}:
                matches.append(facts['root'])
        if len(matches) != 1:
            raise RetainedDataError('Runtime body must join exactly one complete held inventory subject')
        return self._capture(reference, retain=True, root=matches[0])

    def read_original_body(self, reference, *, maximum):
        """Actual bounded whole original console/log/document, never an evaluator."""
        if type(maximum) is not int or not 1 <= maximum <= 64 * 1024 * 1024:
            raise RetainedSourceError('Fixed original body reader bound must be 1..64 MiB')
        body = self._membership(reference)
        if body['bytes'] > maximum:
            raise RetainedDataError('Original metadata exceeds its finite retained document bound')
        return self._capture(body, retain=True)

    def read_system_runtime_input(self, reference):
        """Only the original profile's exact current qualified System32 shell.

        The profile is an Original document. Its current OS file is a separate
        typed sidecar, never an inventory row or a CI member assertion.
        """
        _require_live_context(self)
        reference = _ref(reference, body=True)
        if self.selection['schema_version'] != 2:
            raise RetainedSourceError('Current OS runtime sidecars require selection2')
        profile_ref = self.selection['runtime_profiles']['nmake']
        profile_raw = self.read_input(profile_ref)
        selected = _pure_module('runtime_host').system_references('nmake', profile_ref, profile_raw)
        if (type(selected) is not list or len(selected) != 1 or
                reference != dict(selected[0], mode=0o644)):
            raise RetainedDataError('Only the exact original NMake command-processor reference is admitted')
        if reference['bytes'] > 64 * 1024 * 1024:
            raise RetainedDataError('Current OS command processor exceeds 64-MiB bound')
        system = _document(profile_raw)['system']
        runtime = self.actual_subject['runtime_identity']
        root, version = runtime.get('system_root'), runtime.get('windows_version')
        _absolute(root)
        if (type(version) is not list or len(version) != 3 or
                any(type(value) is not int or not 0 <= value <= 2**31 - 1 for value in version)):
            raise RetainedSourceError('Exact actual current Windows major/minor/build identity required')
        if (system['policy'] != 'qualified-native-system-root-v1' or system['root'] != root or
                not _owned_equal(system['windows_version'], version) or
                reference['path'] != root.rstrip('/') + '/System32/cmd.exe'):
            raise RetainedDataError('Original command processor differs from the actual current OS subject')
        raw = self._capture(reference, retain=True, root=root, use_tree=False)
        self.check_inputs()
        self._system_runtime_refs[reference['path']] = copy.deepcopy(reference)
        return raw

    def emitter(self, role):
        """Fixed original source-owned emitter lookup for the core method plan."""
        if role == 'nmake':
            return _nmake_emitter(self)['path']
        if self.selection['schema_version'] == 2 and role in RESOURCE_ROLES:
            return _resource_emitter(self, role)['path']
        return _catalogue_emitter(self, role, self.checked_source_catalogue)

    def check_inputs(self):
        if self._state not in ('opening', 'open'):
            raise RetainedSourceError('Actual retained readers are not live')
        self.check_deadline()
        for owner in self._owners.values():
            if type(owner) is not self.native.AnchoredInputs or owner.closed or owner.uncertain:
                raise RetainedOwnershipUncertain('Actual retained input owner is closed or uncertain before postflight')
            owner.check()
        actual = self.native.inspect_input_subject()
        if actual != self.actual_subject:
            raise RetainedDataError('Current A input source/runtime changed during retained reconstruction')

    def _close(self):
        self.check_inputs()
        first = None
        for stream in reversed(self._streams):
            try: stream.close()
            except BaseException as error: first = first or error
        for owner in reversed(list(self._owners.values())):
            try: owner.close()
            except BaseException as error: first = first or error
        if (first is not None or any(not owner.closed or owner.uncertain for owner in self._owners.values())):
            self._state = 'uncertain'; _UNCERTAIN.append(self)
            raise RetainedOwnershipUncertain('Retain actual readers after uncertain closure; no versions issued') from first
        self._state = 'closed'
        _LIVE.discard(self)
        self.check_deadline()

    def _abort(self):
        _CLOSED.pop(self, None)
        _LIVE.discard(self)
        if self._state == 'uncertain':
            if self not in _UNCERTAIN: _UNCERTAIN.append(self)
            raise RetainedOwnershipUncertain('Retain unconfirmed stream/reader ownership; do not retry dependent closes')
        first = None
        for stream in reversed(self._streams):
            try: stream.close()
            except BaseException as error: first = first or error
        for owner in reversed(list(self._owners.values())):
            if getattr(owner, 'uncertain', True):
                first = first or RetainedOwnershipUncertain('Uncertain retained owner remains held')
                continue
            if not owner.closed:
                try: owner.close()
                except BaseException as error: first = first or error
        if first is not None or any(not getattr(owner, 'closed', False) or getattr(owner, 'uncertain', True) for owner in self._owners.values()):
            self._state = 'uncertain'; _UNCERTAIN.append(self)
            raise RetainedOwnershipUncertain('Retain uncertain native readers after failed reconstruction') from first
        self._state = 'aborted'


def _require_closed_context(context, facts, origin):
    """Core-only accessor: exact actual class + production close record + Origin."""
    if type(context) is not _RetainedContext or context not in _CLOSED:
        raise RetainedSourceError('An actual registered closed retained context is required')
    record = _CLOSED[context]
    if (context._state != 'closed' or not context._owners or
            any(type(owner) is not context.native.AnchoredInputs or not owner.closed or owner.uncertain for owner in context._owners.values()) or
            record['origin'] is not origin or
            context.origin is not origin or _encoded(facts) != record['facts'] or
            not _owned_equal(context.runtime_profile_facts, record['runtime_profile_facts']) or
            not _owned_equal(context._system_runtime_refs, record['system_runtime_refs'])):
        raise RetainedSourceError('Closed retained context/facts/origin association differs')
    current_origin = context.origin_module.require_retained_originals(origin)
    if current_origin != record['origin_summary'] or current_origin['request'] != context.originals_reference:
        raise RetainedSourceError('Genuine original request association differs')
    return _document(record['facts'])


def _require_live_context(context):
    """Fixed core runtime/provenance readers may use only this actual live context."""
    if (type(context) is not _RetainedContext or context not in _LIVE or
            context._state not in ('opening', 'open') or not context._owners):
        raise RetainedSourceError('An actual registered live retained context is required')
    if (context.origin_module.require_retained_originals(context.origin) != context.origin_summary or
            context.origin_summary['request'] != context.originals_reference):
        raise RetainedSourceError('Live retained original authority association differs')
    context.check_inputs()
    return {'selection': copy.deepcopy(context.selection),
            'inventory_subjects': copy.deepcopy(context.inventory_subjects),
            'inventory_facts': copy.deepcopy(context.inventory_facts),
            'current_input': copy.deepcopy(context.actual_subject),
            'original_request': copy.deepcopy(context.originals_reference)}


def _require_closed_original_references(context, origin):
    """Core-only original-input association outside the unchanged facts schema."""
    if type(context) is not _RetainedContext or context not in _CLOSED:
        raise RetainedSourceError('An actual registered closed retained context is required')
    record = _CLOSED[context]
    _require_closed_context(context, _document(record['facts']), origin)
    references = [copy.deepcopy(record['original_refs'][path])
                  for path in sorted(record['original_refs'], key=str.casefold)]
    if not 1 <= len(references) <= 16000:
        raise RetainedDataError('Finite exact consumed original input references required')
    for reference in references: _ref(reference)
    context.origin_module.require_original_membership(origin, references)
    return references


def _require_closed_runtime_facts(context):
    """Owned runtime facts from the actual closed association, never a new cap."""
    if type(context) is not _RetainedContext or context not in _CLOSED:
        raise RetainedSourceError('An actual registered closed retained context is required')
    record = _CLOSED[context]
    _require_closed_context(context, _document(record['facts']), record['origin'])
    return copy.deepcopy(record['runtime_profile_facts'])


def _capture_inventories(context):
    """Reconstruct original declarations, hold every actual file, enumerate all."""
    contract = _pure_module('inventory')
    context.inventory_facts, context.inventory_subjects = {}, {}
    for role in INVENTORY_ROLES:
        row = context.selection['inventories'][role]
        raw = context.read_original_body(row['reference'], maximum=min(MAX_DOCUMENT, context.limits['maximum_patch_bytes']))
        value = _document(raw)
        if type(value) is not dict or 'provenance' not in value:
            raise RetainedSourceError('Original complete inventory has no provenance reference: ' + role)
        provenance_reference = _ref(value['provenance'])
        provenance_raw = context.read_original_body(provenance_reference, maximum=min(MAX_DOCUMENT, context.limits['maximum_patch_bytes']))
        try:
            facts = contract.inventory_declaration(raw, row['reference']['sha256'], role,
                provenance_raw=provenance_raw, provenance_pin=provenance_reference['sha256'])
        except ValueError as error:
            raise RetainedDataError('Original complete inventory/provenance does not join: ' + role + ': ' + str(error)) from error
        if facts['root'] != row['root'] or facts['subject_sha256'] != row['subject_sha256']:
            raise RetainedDataError('Original selected complete inventory root/subject differs: ' + role)
        context.inventory_facts[role] = facts
        context.inventory_subjects[role] = facts['subject_sha256']
        for original in facts['original_refs']:
            # Genuine original member authority is retained for every report,
            # notice and source reference. Readers interpreting these originals
            # use read_input; large source members may remain bounded streams.
            body = context._membership(original)
            context._capture(body)
        owner = context._reader(facts['root'])
        if not hasattr(owner, 'capture_tree') or not hasattr(context.native, 'HeldInputTree'):
            raise RetainedSourceError('windows-retained-complete-tree-reader: coherent reviewed Aeedb input binding required')
        tree = owner.capture_tree('', files={name: dict(record, mode=0o644)
                    for name, record in facts['files'].items()},
                    directories=facts['directories'])
        if type(tree) is not context.native.HeldInputTree:
            raise RetainedSourceError('Actual complete A.HeldInputTree required')
        context._trees[facts['root']] = tree
        # capture_tree establishes complete held identities and names including
        # empty directories; it deliberately does not label declared SHA as an
        # observed hash. Verify every actual body through its borrowed views.
        for name, record in facts['files'].items():
            context.check_deadline()
            body = {'path': facts['root'] + '/' + name, **record, 'mode': 0o644}
            context._capture(body, root=facts['root'])
        owner.check()


def _collector(selection, inventory_subjects):
    """Independent original collector facts, never current A Python facts."""
    publication = selection['publication']
    if type(publication) is not dict or 'qualification' not in publication:
        raise RetainedSourceError('Original collector qualification selection is absent')
    return {'program': {key: selection['programs']['python'][key] for key in ('path', 'sha256')},
            'runtime_subject_sha256': inventory_subjects['host_generators'],
            'sources': [{key: row[key] for key in ('path', 'sha256')} for row in selection['sources']],
            'qualification': _ref(publication['qualification'])}


def _command(selection, batch_reference, role, *, emitter_path):
    methods = _pure_module('methods')
    roles = ENGINE_ROLES if selection['schema_version'] == 1 else H2_ROLES
    if role not in roles:
        raise RetainedSourceError('Version command role differs from original schema')
    selected = selection['programs'][role]
    cwd = PureWindowsPath(batch_reference['path']).parent.as_posix()
    runtime = selection['publication'].get('runtime_identity')
    if type(runtime) is not dict or 'system_root' not in runtime:
        raise RetainedSourceError('Original collector runtime SystemRoot is missing')
    _absolute(runtime['system_root'])
    parents = sorted({PureWindowsPath(selection['programs'][name]['path']).parent.as_posix()
                      for name in roles}, key=str.casefold)
    if len({name.casefold() for name in parents}) != len(parents):
        raise RetainedDataError('Original command PATH has aliased directories')
    try:
        argv = methods.argv(role, selected['path'], emitter_path)
    except methods.MissingMethod as error:
        raise RetainedSourceError(str(error)) from error
    return {'program': {key: selected[key] for key in ('path', 'sha256')},
            'argv': argv, 'cwd': cwd,
            'environment': {'SystemRoot': runtime['system_root'], 'PATH': ';'.join(parents),
                            'TEMP': cwd + '/temp', 'TMP': cwd + '/temp'}}


def _open_actual_context(request_ref, *, deadline, limits):
    """Bootstrap a pinned request then re-read all bytes through qualified A."""
    _native_guard()
    limits = _arguments(request_ref, deadline, limits)
    core = _core_module()
    # The core owns the one common loader instance and its lower opaque registry.
    origin_module = core.originals_module()
    # This one source-owned provider owns canonical tool imports and the actual
    # current A instance. Initialize/re-require it before any such helper loads.
    origin_module._capture_source_provider()
    try:
        # The lower fixed bootstrap checks ordinary physical identity, finite
        # bytes and the independently selected hash. It grants no A/Q facts;
        # those come from the one actual pair below and its anchored recapture.
        request_raw = origin_module._read_consistent(request_ref,
            min(MAX_DOCUMENT, limits['maximum_member_bytes']))
    except (OSError, EOFError) as error:
        raise RetainedDataError('Actual independently pinned retained request could not be read') from error
    request = _request(_document(request_raw))
    origin = origin_module.admit_retained_originals(request['originals'], deadline=deadline, limits=limits)
    summary = origin_module.require_retained_originals(origin)
    if summary['request'] != request['originals']:
        raise RetainedDataError('Lower original authority is not the selected original request')
    profile = {key: summary['input'][key] for key in ('qualification', 'source_identity', 'runtime_identity')}
    native, qualification, actual = origin_module._admit_input_subject(profile)
    context = object.__new__(_RetainedContext)
    context.native, context.input_q, context.actual_subject = native, qualification, actual
    context.origin_module, context.origin, context.origin_summary = origin_module, origin, summary
    context.originals_reference = copy.deepcopy(request['originals'])
    context.request_reference = copy.deepcopy(request_ref)
    context.batch_reference = copy.deepcopy(request['batch'])
    context.checked_source_catalogue = None
    context.runtime_profiles, context.runtime_profile_facts, context._system_runtime_refs = {}, {}, {}
    context.deadline, context.limits, context._state = deadline, limits, 'opening'
    context._owners, context._trees, context._streams, context._files, context._original_refs = {}, {}, [], {}, {}
    context._members = context._bytes = context._retained_bytes = 0
    context.inventory_facts, context.inventory_subjects = {}, {}
    _LIVE.add(context)
    try:
        context._reader(summary['root'])
        actual_request = context._capture(dict(request_ref, bytes=len(request_raw), mode=0o644), retain=True)
        if actual_request != request_raw:
            raise RetainedDataError('Retained request changed before anchored qualified capture')
        context.selection = _selection(_document(context.read_original_body(request['selection'], maximum=min(MAX_DOCUMENT, limits['maximum_patch_bytes']))))
        batch = _batch(_document(context.read_original_body(request['batch'], maximum=min(MAX_DOCUMENT, limits['maximum_patch_bytes']))), context.selection)
        context._state = 'open'
        context.check_inputs()
        return core, context, request, batch
    except BaseException as error:
        if isinstance(error, native.OwnershipUncertain):
            context._state = 'uncertain'; _LIVE.discard(context); _UNCERTAIN.append(context)
            raise RetainedOwnershipUncertain('Retain uncertain actual readers while opening retained context') from error
        context._abort()
        if isinstance(error, (native.PublicationError, OSError, EOFError)):
            raise RetainedDataError('Actual retained original inputs could not be captured') from error
        raise


def _origin_body_at(context, path):
    """Select original log metadata from the authenticated member map, not O."""
    _absolute(path)
    fact = context.origin_summary['members'].get(path)
    if fact is None:
        raise RetainedDataError('Required exact original member is absent: ' + path)
    return context._membership({key: fact['reference'][key] for key in ('path', 'sha256')})


def _nmake_emitter(context):
    """Exact source-owned original emitter and parser siblings, both held."""
    catalogue = context.checked_source_catalogue
    if type(catalogue) is not dict or set(catalogue) != {'issuer', 'files'}:
        raise RetainedSourceError('Independent checked collector source catalogue required')
    parent = PureWindowsPath(catalogue['issuer']).parent.as_posix()
    prefix = parent + '/'
    selected = None
    for basename, pin, size in (
            ('nmake_version_emitter.py', '82ae5d7e673450505435af68bd1c1aa04718dac86fe454bde267b6547d35adb0', 5294),
            ('nmake_version.py', '20645406f9402db9f70d24679508078cfa7e648d77f652e30e4355bc1df90fdc', 22934)):
        path = prefix + basename
        matches = [row for row in context.selection['sources'] if row['path'] == path]
        if (len(matches) != 1 or matches[0]['sha256'] != pin or matches[0]['bytes'] != size or
                path not in catalogue['files'] or catalogue['files'][path]['sha256'] != pin):
            raise RetainedDataError('Fixed NMake method source is absent from independent original closure: ' + basename)
        reference = _ref(matches[0], body=True)
        raw = context.read_input(reference)
        if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != pin:
            raise RetainedDataError('Actual original NMake method source differs: ' + basename)
        if basename == 'nmake_version_emitter.py': selected = reference
    return selected


def _resource_emitter(context, role):
    """Join all three fixed resource source rows to actual held originals."""
    if context.selection['schema_version'] != 2 or role not in RESOURCE_ROLES:
        raise RetainedSourceError('Resource collector is restricted to the three O2 LLVM roles')
    methods = _core_module()._data_module('methods')
    rows = methods.resource_refs(role)
    _fields(rows, tuple(_RESOURCE_NAMES), 'fixed LLVM resource source closure')
    catalogue = context.checked_source_catalogue
    if type(catalogue) is not dict or set(catalogue) != {'issuer', 'files'}:
        raise RetainedSourceError('Independent checked collector source catalogue required')
    parent = PureWindowsPath(catalogue['issuer']).parent.as_posix()
    selected = None
    for name, relative in _RESOURCE_NAMES.items():
        row = rows[name]
        _fields(row, ('path', 'sha256', 'bytes', 'mode'), 'fixed LLVM resource source')
        if row['path'] != relative:
            raise RetainedSourceError('Fixed LLVM resource relative source path differs')
        expected = _ref(dict(row, path=parent + '/' + relative), body=True)
        if not 1 <= expected['bytes'] <= 131072:
            raise RetainedSourceError('Fixed LLVM resource source exceeds its finite source bound')
        matches = [item for item in context.selection['sources'] if item['path'] == expected['path']]
        if (len(matches) != 1 or not _owned_equal(matches[0], expected) or
                expected['path'] not in catalogue['files'] or
                catalogue['files'][expected['path']]['sha256'] != expected['sha256']):
            raise RetainedDataError('Fixed LLVM resource source is absent from independent original closure: ' + name)
        raw = context.read_input(expected)
        if (type(raw) is not bytes or len(raw) != expected['bytes'] or
                hashlib.sha256(raw).hexdigest() != expected['sha256']):
            raise RetainedDataError('Actual original LLVM resource source differs: ' + name)
        if name == 'emitter': selected = expected
    return selected


def _observation_method_inputs(context, role):
    """Join one fixed actual core plan; serialized O never selects its runner."""
    _require_live_context(context)
    roles = ENGINE_ROLES if context.selection['schema_version'] == 1 else H2_ROLES
    if role not in roles:
        raise RetainedSourceError('Observation role differs from selected original schema')
    plan = _core_module()._retained_method_plan(context, role)
    _fields(plan, ('runner', 'argv', 'method_inputs'), 'actual retained method plan')
    runner = _ref(plan['runner'])
    resource = context.selection['schema_version'] == 2 and role in RESOURCE_ROLES
    expected_role = 'python' if role == 'nmake' or resource else role
    expected = {key: context.selection['programs'][expected_role][key] for key in ('path', 'sha256')}
    if runner != expected:
        raise RetainedDataError('Actual method runner differs from its fixed selected role')
    if (type(plan['argv']) is not list or not 1 <= len(plan['argv']) <= 64 or
            any(type(arg) is not str or not arg or len(arg) > 4096 or '\0' in arg for arg in plan['argv']) or
            plan['argv'][0] != runner['path']):
        raise RetainedDataError('Bounded fixed method argv must start with its actual selected runner')
    inputs = plan['method_inputs']
    if resource:
        _fields(inputs, ('program', 'runner', 'emitter', 'emitter_raw'),
                'actual retained LLVM resource-method inputs')
        _fields(inputs['program'], ('path', 'sha256', 'bytes'), 'actual held LLVM resource subject')
        program = {key: context.selection['programs'][role][key] for key in ('path', 'sha256', 'bytes')}
        if not _owned_equal(inputs['program'], program) or not _owned_equal(inputs['runner'], runner):
            raise RetainedDataError('LLVM resource subject/runner differs from independently selected inputs')
        emitter = _resource_emitter(context, role)
        if not _owned_equal(inputs['emitter'], emitter):
            raise RetainedDataError('LLVM resource emitter differs from fixed original source')
        raw = context.read_input(emitter)
        if type(inputs['emitter_raw']) is not bytes or raw != inputs['emitter_raw']:
            raise RetainedDataError('LLVM resource emitter differs from actual original held source')
    elif role not in ('nmake', 'msbuild'):
        if inputs is not None:
            raise RetainedDataError('Pre-existing observation methods accept no host-method inputs')
    elif role == 'msbuild':
        _fields(inputs, ('runtime_profile', 'project', 'project_raw'), 'actual retained MSBuild inputs')
        expected = context.runtime_profile_facts.get('msbuild', {}).get('method_inputs')
        if not _owned_equal(inputs, expected) or not _owned_equal(inputs['runtime_profile'], context.runtime_profiles['msbuild']):
            raise RetainedDataError('MSBuild method inputs differ from actual original runtime profile facts')
        project = _ref(inputs['project'], body=True)
        raw = context.read_input(project)
        if type(inputs['project_raw']) is not bytes or raw != b'<Project />\n' or raw != inputs['project_raw']:
            raise RetainedDataError('Actual held original MSBuild entry project differs from fixed empty source')
    else:
        _fields(inputs, ('runtime_profile', 'program', 'runner', 'emitter', 'emitter_raw'),
                'actual retained NMake resource-method inputs')
        _fields(inputs['program'], ('path', 'sha256', 'bytes'), 'actual held NMake subject')
        program = {key: context.selection['programs']['nmake'][key] for key in ('path', 'sha256', 'bytes')}
        if (not _owned_equal(inputs['program'], program) or not _owned_equal(inputs['runner'], runner) or
                not _owned_equal(inputs['runtime_profile'], context.runtime_profiles['nmake'])):
            raise RetainedDataError('NMake subject/runner/runtime differs from actual independent selected inputs')
        emitter = _nmake_emitter(context)
        if not _owned_equal(inputs['emitter'], emitter):
            raise RetainedDataError('NMake method emitter differs from fixed original source')
        raw = context.read_input(emitter)
        if type(inputs['emitter_raw']) is not bytes or raw != inputs['emitter_raw']:
            raise RetainedDataError('NMake emitter body differs from actual original held source')
    return copy.deepcopy(plan)


def _command_for_plan(selection, batch_reference, role, plan):
    """Rebuild the original environment/cwd independently of O and core argv."""
    roles = ENGINE_ROLES if selection['schema_version'] == 1 else H2_ROLES
    if role not in roles: raise RetainedSourceError('Method command role differs from original schema')
    _fields(plan, ('runner', 'argv', 'method_inputs'), 'actual retained method plan')
    runner = _ref(plan['runner'])
    resource = selection['schema_version'] == 2 and role in RESOURCE_ROLES
    expected_role = 'python' if role == 'nmake' or resource else role
    if runner != {key: selection['programs'][expected_role][key] for key in ('path', 'sha256')}:
        raise RetainedDataError('Only fixed NMake/LLVM3 resource methods have a distinct Python runner')
    cwd = PureWindowsPath(batch_reference['path']).parent.as_posix()
    root = selection['publication']['runtime_identity'].get('system_root')
    _absolute(root)
    parents = sorted({PureWindowsPath(selection['programs'][name]['path']).parent.as_posix()
                      for name in roles}, key=str.casefold)
    if len({name.casefold() for name in parents}) != len(parents):
        raise RetainedDataError('Original command PATH has case aliases')
    return {'program': runner, 'argv': copy.deepcopy(plan['argv']), 'cwd': cwd,
            'environment': {'SystemRoot': root, 'PATH': ';'.join(parents),
                            'TEMP': cwd + '/temp', 'TMP': cwd + '/temp'}}


def _reconstruct_observations(context, request, batch, *, catalogue, runtime_profiles=None):
    """One fixed O/Job parser consumes independently selected original bodies."""
    checker = _pure_module('observation')
    roles = ENGINE_ROLES if context.selection['schema_version'] == 1 else H2_ROLES
    collector = _collector(context.selection, context.inventory_subjects)
    if _encoded(batch['collector']) != _encoded(collector):
        raise RetainedDataError('Original batch collector differs from independently reconstructed collector')
    cwd = PureWindowsPath(request['batch']['path']).parent.as_posix()
    observations, programs = {}, {}
    for role in roles:
        context.check_deadline()
        original_o = batch['observations'][role]
        if original_o['path'] != cwd + '/observations/' + role + '.json':
            raise RetainedDataError('Original O path differs from its exact batch/role layout')
        raw = context.read_original_body(original_o, maximum=min(MAX_DOCUMENT, context.limits['maximum_patch_bytes']))
        log_reference = _origin_body_at(context, cwd + '/logs/' + role + '.log')
        if not 1 <= log_reference['bytes'] <= 65536:
            raise RetainedDataError('Whole original version log exceeds finite 64-KiB grammar')
        log_raw = context.read_original_body(log_reference, maximum=65536)
        method_inputs = None
        if context.selection['schema_version'] == 1:
            emitter = None if role == 'cmake' else _catalogue_emitter(context, role, catalogue)
            command = _command(context.selection, request['batch'], role, emitter_path=emitter)
        else:
            plan = _observation_method_inputs(context, role)
            command = _command_for_plan(context.selection, request['batch'], role, plan)
            method_inputs = plan['method_inputs']
        program = {key: context.selection['programs'][role][key] for key in ('path', 'sha256')}
        owning_role = 'llvm' if role in ENGINE_ROLES[:5] else 'host_generators'
        arguments = {'role': role, 'program': program,
            'inventory_subject_sha256': context.inventory_subjects[owning_role],
            'collector': collector, 'command': command,
            'log_raw': log_raw, 'log_reference': log_reference}
        try:
            if context.selection['schema_version'] == 1:
                result = checker.observation(raw, original_o['sha256'], **arguments)
            else:
                # Fresh and retained O2 use the same fixed core-owned wrapper;
                # original O1 still delegates its immutable historical checker.
                result = _core_module()._data_module('observation_host').observation(raw, original_o['sha256'],
                    runtime_profiles=runtime_profiles, method_inputs=method_inputs, **arguments)
        except ValueError as error:
            # The additive immutable wrapper privately loads the same fixed
            # core, so its exception class has a distinct Python identity. Both
            # fixed sources name only their explicit method gap MissingMethod;
            # this classification always rejects and grants no authority.
            if isinstance(error, checker.MissingMethod) or type(error).__name__ == 'MissingMethod':
                raise RetainedSourceError(str(error)) from error
            raise RetainedDataError('Original O/Job/log consistency failed: ' + str(error)) from error
        if result['observation']['schema_version'] != context.selection['schema_version']:
            raise RetainedDataError('Original O schema differs from its original complete batch')
        observations[role] = copy.deepcopy(original_o)
        programs[role] = dict(program, version=result['version'])
    return observations, programs


def _drop_cached_body(context, path):
    record = context._files.get(path.casefold())
    if record is not None and record['raw'] is not None:
        context._retained_bytes -= len(record['raw'])
        record['raw'] = None


def _hold_native_programs(context):
    """Strict static same-directory dependency domain over complete held trees.

    This does not infer dynamic LoadLibrary behavior. Unknown origin/search
    policy is a concrete SOURCE delta; no ambient PATH/filesystem search occurs.
    """
    inspector = _pure_module('native_inspection')
    roles = ENGINE_ROLES if context.selection['schema_version'] == 1 else H2_ROLES
    checked = set()
    context.native_runtime_images = {}
    for role in roles:
        if role == 'msbuild':
            # Its explicit managed profile is independently interpreted by the
            # core runtime-profile factory, never by relaxing native CLR reject.
            continue
        owning_role = 'llvm' if role in ENGINE_ROLES[:5] else 'host_generators'
        inventory = context.inventory_facts[owning_role]
        selected = context.selection['programs'][role]
        try:
            relative = PureWindowsPath(selected['path']).relative_to(PureWindowsPath(inventory['root'])).as_posix()
        except ValueError as error:
            raise RetainedDataError('Original program escapes its independent owning inventory: ' + role) from error
        if inventory['files'].get(relative) != {key: selected[key] for key in ('sha256', 'bytes')}:
            raise RetainedDataError('Original program bytes do not join complete owning inventory: ' + role)
        pending = [(relative, False)]
        while pending:
            member, must_be_dll = pending.pop()
            identity = (owning_role, member)
            if identity in checked: continue
            checked.add(identity)
            if len(checked) > 65536:
                raise RetainedDataError('Static original runtime graph exceeds 65536 held images')
            record = inventory['files'][member]
            path = inventory['root'] + '/' + member
            body = {'path': path, **record, 'mode': 0o644}
            raw = context._capture(body, retain=True, root=inventory['root'])
            try:
                facts = inspector.inspect_tool_image(raw)
            except ValueError as error:
                raise RetainedSourceError('windows-retained-native-image-domain:' + role + ':' + path + ':' + str(error)) from error
            finally:
                _drop_cached_body(context, path)
            if facts['dll'] != must_be_dll:
                raise RetainedDataError('Original program/runtime DLL kind differs: ' + path)
            context.native_runtime_images[path] = facts
            parent, _, _name = member.rpartition('/')
            for needed in facts['needed']:
                if needed in inspector.SYSTEM_IMPORTS:
                    continue
                matches = [name for name in inventory['files']
                    if name.rsplit('/', 1)[-1].casefold() == needed]
                if len(matches) != 1 or matches[0].rpartition('/')[0] != parent:
                    raise RetainedSourceError('windows-retained-native-runtime-origin:' + role + ':' + needed +
                        ': exact unique same-directory held import required; a different loader/runtime origin needs reviewed source/profile')
                pending.append((matches[0], True))


def _relative_source(value):
    if (type(value) is not str or not value or len(value) > 4096 or '\\' in value or
            value.startswith('/') or ':' in value or
            any(part in ('', '.', '..') for part in value.split('/'))):
        raise RetainedDataError('Canonical relative original source catalogue path required')
    _absolute('C:/catalogue/' + value)
    return value


def _source_catalogue(catalogue, selection):
    """Pure branch against fixed independent original data; no authority here."""
    schema = selection['schema_version']
    if type(schema) is not int or schema not in (1, 2):
        raise RetainedSourceError('Exact original source catalogue schema1/2 required')
    _fields(catalogue, ('issuer_relative', 'files', 'publication_source_identity',
                        'input_source_identity') + (('qualification_sources',) if schema == 2 else ()),
                        'independent original source catalogue')
    _relative_source(catalogue['issuer_relative'])
    if type(catalogue['files']) is not dict or not 1 <= len(catalogue['files']) <= 4096:
        raise RetainedDataError('Finite independent original source catalogue required')
    expected = {}
    aliases = set()
    for relative, row in catalogue['files'].items():
        _relative_source(relative)
        if type(row) is not dict or set(row) not in ({'sha256'}, {'sha256', 'bytes'}):
            raise RetainedSourceError('Original source catalogue rows have SHA and optional exact bytes')
        _pin(row['sha256'])
        if 'bytes' in row and (type(row['bytes']) is not int or not 0 <= row['bytes'] <= MAX_DOCUMENT):
            raise RetainedDataError('Bounded original source catalogue byte count required')
        if relative.casefold() in aliases:
            raise RetainedDataError('Aliased original source catalogue paths')
        aliases.add(relative.casefold()); expected[relative] = copy.deepcopy(row)
    qualification_pins = {}
    for field, subject in (('publication_source_identity', 'publication'), ('input_source_identity', 'input')):
        source_map = catalogue[field]
        if type(source_map) is not dict or not 1 <= len(source_map) <= 128:
            raise RetainedDataError('original-source-catalogue: independent historical A source map is missing: ' + subject)
        if selection[subject]['source_identity'] != source_map:
            raise RetainedDataError('Original declared A subject differs from independent catalogue: ' + subject)
        for relative, pin in source_map.items():
            _relative_source(relative); _pin(pin)
            if relative in qualification_pins and qualification_pins[relative] != pin:
                raise RetainedDataError('Independent qualification logical source maps have conflicting pins')
            qualification_pins[relative] = pin
            if schema == 1:
                if relative in expected and expected[relative]['sha256'] != pin:
                    raise RetainedDataError('Independent source catalogue/A maps have conflicting pins')
                if relative not in expected:
                    if relative.casefold() in aliases:
                        raise RetainedDataError('Independent A source map has case aliases')
                    aliases.add(relative.casefold()); expected[relative] = {'sha256': pin}
    if schema == 2:
        mapping = _fields(catalogue['qualification_sources'], qualification_pins,
                          'source-owned logical qualification to physical source map')
        logical_aliases = set()
        for logical, physical in mapping.items():
            _relative_source(logical); _relative_source(physical)
            if logical.casefold() in logical_aliases:
                raise RetainedDataError('Qualification logical source keys have case aliases')
            logical_aliases.add(logical.casefold())
            if physical not in expected or expected[physical]['sha256'] != qualification_pins[logical]:
                raise RetainedDataError('Logical qualification source does not join an exact physical catalogue file')
    if catalogue['issuer_relative'] not in expected:
        raise RetainedDataError('Original producer is absent from independent source catalogue')
    root = selection['source_root']
    files = {root + '/' + relative: row for relative, row in expected.items()}
    declared = {row['path']: row for row in selection['sources']}
    if set(declared) != set(files):
        raise RetainedDataError('Exact original producer/method/A/inspector source closure differs')
    for path, row in files.items():
        if any(declared[path][name] != value for name, value in row.items()):
            raise RetainedDataError('Original source pin/known byte count differs from independent catalogue: ' + path)
    return {'issuer': root + '/' + catalogue['issuer_relative'], 'files': files}


def _capture_sources(context, catalogue):
    checked = _source_catalogue(catalogue, context.selection)
    for reference in context.selection['sources']:
        context.read_original_body(reference, maximum=min(MAX_DOCUMENT, context.limits['maximum_patch_bytes']))
    return checked


def _catalogue_emitter(context, role, catalogue):
    methods = (_pure_module('methods') if context.selection['schema_version'] == 1
               else _core_module()._data_module('methods'))
    try:
        rows = [row for row in methods.source_refs(role)
                if row['path'].endswith(('emitter.py', 'emitter.pl', 'emitter.rb'))]
    except methods.MissingMethod as error:
        raise RetainedSourceError(str(error)) from error
    if len(rows) != 1:
        raise RetainedSourceError('One exact source-owned historical emitter is required')
    # Current method source paths are flattened. Historical source locations
    # come only from the independent finite original catalogue; an exact
    # source-owned hash and basename must select one original emitter body.
    if type(catalogue['files']) is not dict or not 1 <= len(catalogue['files']) <= 128:
        raise RetainedDataError('Finite original collector source catalogue required')
    basename = PureWindowsPath(rows[0]['path']).name
    matches = [path for path, row in catalogue['files'].items()
               if PureWindowsPath(path).name == basename and row['sha256'] == rows[0]['sha256']]
    if len(matches) != 1:
        raise RetainedDataError('Fixed original emitter hash/basename must select exactly one catalogue body')
    selected = matches[0]
    _absolute(selected)
    if (not selected.startswith(context.selection['source_root'] + '/') or
            selected not in catalogue['files'] or
            catalogue['files'][selected]['sha256'] != rows[0]['sha256']):
        raise RetainedDataError('Historical emitter does not join independent original source catalogue')
    declared = next((row for row in context.selection['sources'] if row['path'] == selected), None)
    if declared is None:
        raise RetainedDataError('Original pinned emitter body is absent')
    context.read_original_body(declared, maximum=min(MAX_DOCUMENT, context.limits['maximum_patch_bytes']))
    return selected


def _historical_qualification(context, independent_catalogue):
    """Replay original Q/run/evidence semantics without a current-runtime Q call."""
    # Report semantics are source-version-specific: schema1 retains A53/PUB726,
    # schema2 selects the core's fixed current-A pure checker. Neither branch
    # admits a historical collector by comparing it with the current reader.
    helper = _core_module()._publication_checker(context.selection['schema_version'])
    selected = context.selection['publication']
    original_runtime = selected['runtime_identity']
    python = context.selection['programs']['python']
    if (original_runtime.get('python_path') != python['path'] or
            original_runtime.get('python_sha256') != python['sha256']):
        raise RetainedDataError('Historical collector runtime Python differs from its original selected program')
    qualification_raw = context.read_original_body(selected['qualification'], maximum=1024 * 1024)
    references = helper.original_references(qualification_raw, selected['qualification']['sha256'])
    originals = {}
    for role, reference in references.items():
        maximum = 64 * 1024 * 1024 if role == 'console' else 1024 * 1024
        originals[reference['path']] = context.read_original_body(reference, maximum=maximum)
    try:
        facts = helper.publication_qualification(qualification_raw, selected['qualification']['sha256'],
            source_identity=independent_catalogue['publication_source_identity'],
            runtime_identity=original_runtime, originals=originals)
    except ValueError as error:
        category = getattr(error, 'code', 'DATA')
        exception = RetainedSourceError if category == 'SOURCE' else RetainedDataError
        raise exception('Historical collector publication originals: ' + str(error)) from error
    # Historical input Q is retained as original source evidence only. Current
    # actual input authority was independently re-admitted with the shared A
    # subject helper and is never obtained from this historical JSON object.
    context.read_original_body(context.selection['input']['qualification'], maximum=1024 * 1024)
    context.historical_publication = facts
    return facts


def admit_retained_observed_versions(request_ref, *, deadline, limits):
    """Actual native retained reconstruction; only the one core registry issues V.

    Known final-method/runtime formats remain explicit source requirements.
    A missing independently retained original catalogue/report is DATA. Genuine
    current inputs, original membership and known closed ownership remain
    necessary; inventory labels are descriptive and never observed versions.
    """
    _native_guard()
    limits = _arguments(request_ref, deadline, limits)
    context = None
    try:
        core, context, request, batch = _open_actual_context(request_ref, deadline=deadline, limits=limits)
        # Schema dispatch and each expected source literal come from fixed core
        # data, not the selected Q's expected map or current verifier identity.
        catalogue = core._retained_source_catalogue(context.selection['schema_version'])
        checked_catalogue = _capture_sources(context, catalogue)
        context.checked_source_catalogue = checked_catalogue
        _historical_qualification(context, catalogue)
        _capture_inventories(context)
        _hold_native_programs(context)
        runtime_profiles = None
        if context.selection['schema_version'] == 2:
            runtime_profiles = core._admit_runtime_profiles(context)
            _runtime_binding(runtime_profiles, context.selection)
            context.runtime_profiles = copy.deepcopy(runtime_profiles)
            if _encoded(batch['runtime_profiles']) != _encoded(runtime_profiles):
                raise RetainedDataError('Original batch runtime subjects differ from independently held profile interpretation')
        observations, programs = _reconstruct_observations(context, request, batch,
            catalogue=checked_catalogue, runtime_profiles=runtime_profiles)
        # Join the independently parsed old Python log to the historical
        # collector declaration. This never queries/compares current A Python.
        if programs['python']['version'] != context.selection['publication']['runtime_identity']['python_version']:
            raise RetainedDataError('Original Python observation and historical collector runtime version differ')
        # Inventory version strings are declared descriptive labels. This pure
        # derivation retains the complete original provenance ledger; it is no
        # separate executable observation or opaque vendor-label authority.
        declared = core._inventory_provenance(context)
        _fields(declared, ('inventories', 'inventory_release_evidence'), 'original inventory provenance descriptions')
        if (not _owned_equal(batch['inventories'], declared['inventories']) or
                not _owned_equal(batch['inventory_release_evidence'], declared['inventory_release_evidence'])):
            raise RetainedDataError('Original batch inventory labels/provenance differ from complete held declarations')
        for references in declared['inventory_release_evidence'].values():
            for reference in references:
                # A full ledger includes original source bodies as well as
                # metadata. Hash/hold them through the existing bounded stream
                # path; do not impose a whole-JSON buffer bound on source bytes.
                body = context._membership(reference)
                context._capture(body)
        facts = {'batch': {key: request['batch'][key] for key in ('path', 'sha256')},
            'observations': observations, 'programs': programs,
            'inventory_subjects': copy.deepcopy(context.inventory_subjects),
            'inventories': copy.deepcopy(declared['inventories']),
            'inventory_release_evidence': copy.deepcopy(declared['inventory_release_evidence'])}
        if runtime_profiles is not None:
            facts['runtime_profiles'] = copy.deepcopy(runtime_profiles)
        context.check_inputs()
        context._close()
        # Only this actual native path inserts a production close record. The
        # core rechecks exact class/record, all closed owners, genuine Origin and
        # complete provenance descriptions before minting into its one registry.
        context.origin_module.require_retained_originals(context.origin)
        _CLOSED[context] = {'facts': _encoded(facts),
            'origin': context.origin, 'origin_summary': copy.deepcopy(context.origin_summary),
            'original_refs': copy.deepcopy(context._original_refs),
            'runtime_profile_facts': copy.deepcopy(context.runtime_profile_facts),
            'system_runtime_refs': copy.deepcopy(context._system_runtime_refs)}
        # Origin checks and finite serialization/copies can consume the last
        # deadline interval after readers close. Never forward a late record;
        # the common exception path revokes this context's closed association.
        context.check_deadline()
        return core._issue_retained_closed(context, facts, context.origin)
    except BaseException as error:
        if context is not None:
            _CLOSED.pop(context, None)
            if isinstance(error, context.native.OwnershipUncertain):
                context._state = 'uncertain'; _LIVE.discard(context); _UNCERTAIN.append(context)
                raise RetainedOwnershipUncertain('Retain actual native input ownership; no versions issued') from error
            if context._state not in ('closed', 'aborted'):
                context._abort()
            if isinstance(error, (context.native.PublicationError, OSError, EOFError)):
                raise RetainedDataError('Actual retained input/readback could not be completed') from error
        if isinstance(error, FileNotFoundError):
            raise RetainedDataError('Selected actual retained original input is absent') from error
        code = getattr(error, 'code', None)
        if code == 'SOURCE' and not isinstance(error, RetainedSourceError):
            raise RetainedSourceError(str(error)) from error
        if code == 'DATA' and not isinstance(error, RetainedDataError):
            raise RetainedDataError(str(error)) from error
        if code == 'OWNERSHIP_UNCERTAIN' and not isinstance(error, RetainedOwnershipUncertain):
            raise RetainedOwnershipUncertain(str(error)) from error
        raise
