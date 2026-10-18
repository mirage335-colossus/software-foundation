#!/usr/bin/env python3
"""Bounded, passive Windows supplier projection and patch replay.

The stream kernel derives an explicitly unchecked inventory without extracting a
tree or starting a program. Source admission uses the released shared checked
projection and original-proof join, with captured inputs retained by an issued
inspection. Neither an unchecked inventory nor passive copied facts grant that
inspection's authority or lifetime.
"""
import argparse
import copy
import hashlib
import importlib.util
import lzma
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import struct
import sys
import tarfile
import time
import weakref
import zlib
import zipfile

import appended_engine_manifest as manifest
import appended_engine_native_inputs as native_inputs
import appended_engine_windows_contract as contract
import appended_engine_windows_handoff as handoff
from dependency_archive import PathInventory

MAX_DOCUMENT = 32 * 1024 * 1024
MAX_ARCHIVE = 8 * 1024 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024 * 1024
MAX_MEMBERS = 1000000
MAX_MEMBER = 256 * 1024 * 1024
MAX_DEPTH = 64
SELECTION_KIND = 'foundation-native-engine-windows-source-replay-selection-v1'
SCOPE = 'supplier-patch-overlay-replay-consistency-only'
# Set only by the supervisor after the shared owner's explicit source release.
# API presence, a caller flag or an ambient newer module never grants admission.
SOURCE_SEAM_SHA256 = '3746e0f8560460f972948f4e92ec1b42412792b5abd77ea3c4d75680bbc62d01'
NATIVE_INPUT_READER_SHA256 = '02f675a2480bbb94eafed0cac101b8afca1d2c3fe4a17dddd4cfb9693998edc0'
NATIVE_INPUT_TREE_SHA256 = '02f675a2480bbb94eafed0cac101b8afca1d2c3fe4a17dddd4cfb9693998edc0'
_NATIVE_INPUT_READER_CACHE = None
_SOURCE_INSPECTIONS = weakref.WeakKeyDictionary()
_UNCERTAIN_SOURCE_OWNERS = []
ORIGINAL_PROOF_ROLES = ('recipe', 'sources', 'archive_receipt', 'member_manifest',
                        'source_scope', 'supplier_patch_images', 'generator')
SOURCE_PROVENANCE_ROLES = native_inputs.SOURCE_PROVENANCE_ROLES
SOURCE_PROVENANCE_OPTIONAL = native_inputs.SOURCE_PROVENANCE_OPTIONAL
COMMITS = {'wrapper': '68c618544e1f8af18ebce346281a6a49766aa194',
           'engine': native_inputs.ENGINE_COMMIT}
MissingInputs = contract.MissingInputs
encoded = contract.encoded


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _native_reader_source():
    """Read only this tool's known sibling source, never an input namespace."""
    path = Path(__file__).absolute().with_name('appended_engine_windows_publication.py')
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_DOCUMENT:
        raise ValueError('Native input reader source must be one bounded ordinary file')
    identity = handoff._identity(before)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) |
        getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        if handoff._identity(os.fstat(descriptor)) != identity:
            raise ValueError('Native input reader source changed before its bounded read')
        chunks, count = [], 0
        while True:
            block = os.read(descriptor, min(65536, MAX_DOCUMENT - count + 1))
            if not block:
                break
            chunks.append(block)
            count += len(block)
            if count > MAX_DOCUMENT or count > before.st_size:
                raise ValueError('Native input reader source grew beyond its finite bound')
        if (count != before.st_size or handoff._identity(os.fstat(descriptor)) != identity or
                handoff._identity(os.lstat(path)) != identity):
            raise ValueError('Native input reader source changed during its bounded read')
        return path, b''.join(chunks)
    finally:
        os.close(descriptor)


def _native_input_reader():
    """Load only explicitly released sibling code; API presence grants nothing."""
    global _NATIVE_INPUT_READER_CACHE
    if NATIVE_INPUT_READER_SHA256 is None:
        raise MissingInputs([{'role': 'windows-native-input-reader-source',
            'path': 'tools/appended_engine_windows_publication.py',
            'reason': 'the native input reader source has not been explicitly released'}])
    contract.pin(NATIVE_INPUT_READER_SHA256, 'released native input reader source')
    cached = _NATIVE_INPUT_READER_CACHE
    path, raw = _native_reader_source()
    if digest(raw) != NATIVE_INPUT_READER_SHA256:
        raise ValueError('Native input reader source differs from its explicitly released identity')
    name = 'appended_engine_windows_publication'
    present = name in sys.modules
    existing = sys.modules.get(name)
    if present:
        if (cached is None or _NATIVE_INPUT_READER_CACHE is not cached or cached[0] is not existing or
                cached[1:] != (path, NATIVE_INPUT_READER_SHA256)):
            raise MissingInputs([{'role': 'windows-native-input-reader-loader-coordination',
                'path': 'appended_engine_windows_publication',
                'reason': 'an existing reader was not issued by this standalone source bootstrap; obtain qualification through admit_native_input_qualification'}])
        if Path(existing.__file__).absolute() != path:
            raise ValueError('Imported native input reader source path differs from the pinned sibling')
        api = existing
    else:
        if cached is not None or _NATIVE_INPUT_READER_CACHE is not cached:
            raise MissingInputs([{'role': 'windows-native-input-reader-loader-coordination',
                'path': name, 'reason': 'the released standalone reader module registration changed'}])
        specification = importlib.util.spec_from_file_location(name, path)
        api = importlib.util.module_from_spec(specification)
        if sys.modules.setdefault(name, api) is not api:
            raise MissingInputs([{'role': 'windows-native-input-reader-loader-coordination',
                'path': name, 'reason': 'another loader reserved the native reader before execution'}])
        # Failed reservations remain blockers. No check/delete or restoration
        # can safely establish that a concurrent slot is still ours to remove.
        code = compile(raw, str(path), 'exec')
        if sys.modules.get(name) is not api or _NATIVE_INPUT_READER_CACHE is not cached:
            raise MissingInputs([{'role': 'windows-native-input-reader-loader-coordination',
                'path': name, 'reason': 'native reader reservation or cache changed before execution'}])
        exec(code, api.__dict__)
    current_path, current_raw = _native_reader_source()
    if (Path(api.__file__).absolute() != path or current_path != path or
            digest(current_raw) != NATIVE_INPUT_READER_SHA256 or sys.modules.get(name) is not api):
        raise ValueError('Imported native input reader differs from the pinned source')
    if _NATIVE_INPUT_READER_CACHE is not cached:
        raise MissingInputs([{'role': 'windows-native-input-reader-loader-coordination',
            'path': name, 'reason': 'native reader cache changed before publication or reuse'}])
    published = (api, path, NATIVE_INPUT_READER_SHA256) if cached is None else cached
    if cached is None:
        _NATIVE_INPUT_READER_CACHE = published
    if sys.modules.get(name) is not api or _NATIVE_INPUT_READER_CACHE is not published:
        raise MissingInputs([{'role': 'windows-native-input-reader-loader-coordination',
            'path': name, 'reason': 'native reader slot or cache changed at publication or reuse'}])
    return api


def admit_native_input_qualification(reference):
    """Issue this phase's standalone qualification through the pinned B issuer.

    Other preloaded A issuers require a future explicit loader coordination seam.
    """
    if os.name != 'nt':
        raise ValueError('Native input qualification is only accepted on native Windows')
    contract.fields(reference, ('path', 'sha256'), 'native input qualification reference')
    contract.pin(reference['sha256'], 'native input qualification reference')
    api = _native_input_reader()
    observed = api.inspect_input_subject()
    contract.fields(observed, ('source_identity', 'runtime_identity'), 'actual native input subject')
    return api.admit_input_qualification(reference,
        source_identity=observed['source_identity'], runtime_identity=observed['runtime_identity'])


def require_original_proof_seam():
    """Never substitute a status field or the Linux file-capture inspection."""
    if SOURCE_SEAM_SHA256 is not None:
        contract.pin(SOURCE_SEAM_SHA256, 'released original source record seam')
        if digest(handoff._read(str(Path(native_inputs.__file__).absolute()))) != SOURCE_SEAM_SHA256:
            raise ValueError('Original source record seam differs from its explicitly released source')
        return native_inputs
    raise MissingInputs([{
        'role': 'native-original-source-proof-data-seam',
        'path': 'tools/appended_engine_native_inputs.py#validate_source_provenance_records',
        'reason': 'frozen source-only original-proof data extraction has not been released',
    }])


def _check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise ValueError('Source replay exceeded its original wall budget')


def _source_lifetime(started, deadline):
    if deadline is None:
        return started + 86400, False
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= started:
        raise ValueError('Source inspection requires a finite future monotonic deadline')
    if deadline - started > 86400:
        raise MissingInputs([{'role': 'windows-source-enclosing-lifetime-cap', 'path': 'inspect_for_handoff',
            'reason': 'the enclosing lifetime exceeds the existing native source owner hard cap'}])
    return deadline, True


class SourceInspection:
    """Actual issued source lifetime; passive copies never replace its owners."""
    __slots__ = ('__weakref__',)

    def __new__(cls):
        raise TypeError('Source inspections are issued only by actual checked capture')

    def as_dict(self):
        owner = _source_inspection_owner(self)
        owner.guard()
        return copy.deepcopy(owner.facts)

    def check(self):
        _source_inspection_owner(self).check()

    def revoke(self):
        _source_inspection_owner(self, allow_invalid=True).revoke()

    def close(self):
        _source_inspection_owner(self, allow_invalid=True).close()


def _source_inspection_owner(inspection, *, allow_invalid=False):
    owner = _SOURCE_INSPECTIONS.get(inspection) if type(inspection) is SourceInspection else None
    if owner is None:
        raise ValueError('An actual issued SourceInspection is required')
    if not allow_invalid:
        owner.guard()
    return owner


def _require_source_inspection(inspection, root, handoff_sha256, replay_reference):
    """Private consumer join: a live issued owner must bind this exact subject."""
    owner = _source_inspection_owner(inspection)
    if owner.subject != (os.fspath(root), handoff_sha256, replay_reference):
        raise ValueError('Source inspection belongs to another capsule/replay subject')
    owner.check()
    return copy.deepcopy(owner.facts)


class _SourceInspectionOwner:
    def __init__(self, root, handoff_sha256, replay_reference, started, deadline, explicit):
        self.subject = (os.fspath(root), handoff_sha256, copy.deepcopy(replay_reference))
        self.started, self.initial_deadline, self.deadline = started, deadline, deadline
        self.work_deadline, self.explicit = deadline, explicit
        self.phase, self.failed, self.closed = 'checking', False, False
        self.resources, self.borrowed, self.raw_records = [], [], []
        self.checked, self.facts = None, None
        self.input_bytes, self.input_members, self.charged = 0, 0, {}
        self.limits = {'seconds': deadline - started, 'maximum_archive_bytes': MAX_ARCHIVE,
            'maximum_expanded_bytes': MAX_EXPANDED, 'maximum_members': MAX_MEMBERS,
            'maximum_member_bytes': MAX_MEMBER, 'maximum_patch_bytes': MAX_DOCUMENT}

    def guard(self):
        if self.closed or self.failed:
            raise ValueError('Source inspection is closed or revoked')
        try:
            _check_deadline(self.work_deadline if self.phase == 'checking' else self.deadline)
        except BaseException:
            self.revoke()
            raise

    def set_source_limits(self, limits):
        if self.phase != 'checking':
            raise ValueError('Held source inspection cannot reopen source admission')
        self.limits = validate_limits(limits)
        self.work_deadline = min(self.started + self.limits['seconds'], self.initial_deadline)
        if not self.explicit:
            self.deadline = self.work_deadline
        self.guard()
        self._budget()
        if any(item[0] > self.limits['maximum_member_bytes'] for item in self.charged.values()):
            raise ValueError('Bootstrap source metadata exceeds the selected member bound')

    def _budget(self):
        if (self.input_bytes > self.limits['maximum_expanded_bytes'] or
                self.input_members > self.limits['maximum_members']):
            raise ValueError('Aggregate source capture exceeds the selected byte/member bounds')

    def charge(self, key, size, pin, mode):
        self.guard()
        if self.phase != 'checking':
            raise ValueError('Held source inspection permits no further body capture')
        previous = self.charged.get(key)
        value = (size, pin, mode)
        if previous is not None:
            if previous != value:
                raise ValueError('Conflicting source path/size/pin declarations')
            return
        self.charged[key] = value
        self.input_bytes += size
        self.input_members += 1
        self._budget()

    def source_limits(self):
        self.guard()
        if self.phase != 'checking':
            raise ValueError('Held source inspection cannot parse source again')
        remaining = self.work_deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('Source admission work deadline expired')
        return {**self.limits, 'seconds': min(self.limits['seconds'], remaining)}

    def initial_work(self):
        self.guard()
        if self.phase != 'checking':
            raise ValueError('Held source inspection permits no further body capture')

    def hold(self, checked, facts):
        self.guard()
        if self.phase != 'checking' or checked is None:
            raise ValueError('Actual checked source authority is required before holding')
        self.checked, self.facts = checked, copy.deepcopy(facts)
        self.check()
        self.phase = 'held'
        inspection = object.__new__(SourceInspection)
        _SOURCE_INSPECTIONS[inspection] = self
        return inspection

    def check(self):
        self.guard()
        try:
            for resource in self.resources:
                resource.check()
                self.guard()
        except BaseException:
            self.revoke()
            raise

    def revoke(self):
        self.failed = True
        if not self.closed:
            self.phase = 'revoked'

    def close(self):
        if self.closed:
            return
        errors = []
        for resource in reversed(self.resources):
            try:
                resource.close()
            except BaseException as error:
                errors.append(error)
        if errors:
            self.revoke()
            if not any(item is self for item in _UNCERTAIN_SOURCE_OWNERS):
                _UNCERTAIN_SOURCE_OWNERS.append(self)
            raise errors[0]
        self.closed, self.phase = True, 'closed'
        self.resources.clear()
        self.borrowed.clear()
        self.raw_records.clear()
        self.checked = None


def _native_tree_reader(api):
    if NATIVE_INPUT_TREE_SHA256 is None:
        raise MissingInputs([{'role': 'windows-native-input-tree-source',
            'path': 'tools/appended_engine_windows_publication.py#AnchoredInputs.capture_tree',
            'reason': 'the complete native held-tree input reader has not been explicitly released'}])
    contract.pin(NATIVE_INPUT_TREE_SHA256, 'released native held-tree source')
    if NATIVE_INPUT_TREE_SHA256 != NATIVE_INPUT_READER_SHA256:
        raise ValueError('Native selected-file and held-tree readers require the same released issuer')
    return api


class _SourceInputs:
    """Private accounting/cache around one actual selected-input owner."""
    def __init__(self, owner, inputs):
        self.owner, self.inputs = owner, inputs
        self.raw, self.archives, self.expectations = {}, {}, {}

    def _expected(self, name, expected):
        _path(name)
        if type(expected) is not dict or set(expected) not in ({'sha256', 'mode'}, {'sha256', 'bytes', 'mode'}):
            raise ValueError('Closed independently declared source expectations required')
        contract.pin(expected['sha256'], 'selected source expectation')
        if type(expected['mode']) is not int or expected['mode'] not in (0o644, 0o755):
            raise ValueError('Selected source logical mode must be ordinary')
        if 'bytes' in expected:
            _integer(expected['bytes'], 'selected source expected bytes', MAX_ARCHIVE, 0)
        old = self.expectations.get(name)
        if old is not None and (any(old[key] != expected[key] for key in ('sha256', 'mode')) or
                ('bytes' in old and 'bytes' in expected and old['bytes'] != expected['bytes'])):
            raise ValueError('Conflicting independent expectations for one source leaf')
        self.expectations[name] = {**(old or {}), **expected}
        return copy.deepcopy(self.expectations[name])

    def read(self, name, expected, maximum=MAX_DOCUMENT):
        self.owner.initial_work()
        maximum = min(maximum, self.owner.limits['maximum_member_bytes'])
        expected = self._expected(name, expected)
        if name in self.archives:
            raise ValueError('Archive source cannot be recaptured as metadata')
        if name not in self.raw:
            if self.owner.input_members >= self.owner.limits['maximum_members']:
                raise ValueError('Selected source metadata exceeds the aggregate member bound')
            maximum = min(maximum, self.owner.limits['maximum_expanded_bytes'] - self.owner.input_bytes)
            if maximum <= 0:
                raise ValueError('Selected source metadata exceeds the aggregate byte bound')
            raw = self.inputs.read(name, expected=expected, maximum=maximum)
            if type(raw) is not bytes or len(raw) > maximum:
                raise ValueError('Actual source input reader returned an unbounded body')
            self.raw[name] = raw
        raw = self.raw[name]
        if len(raw) > maximum or ('bytes' in expected and len(raw) != expected['bytes']):
            raise ValueError('Actual source metadata length differs from independent expectation')
        self.owner.charge((id(self.inputs), name), len(raw), expected['sha256'], expected['mode'])
        self.owner.guard()
        return raw

    def archive(self, name, expected):
        self.owner.initial_work()
        if set(expected) != {'sha256', 'bytes', 'mode'}:
            raise ValueError('Archives require independently declared hash, bytes and mode')
        expected = self._expected(name, expected)
        if name in self.raw:
            raise ValueError('Metadata source cannot be recaptured as an archive')
        if expected['bytes'] > self.owner.limits['maximum_archive_bytes']:
            raise ValueError('Source archive exceeds selected archive bound')
        self.owner.charge((id(self.inputs), name), expected['bytes'], expected['sha256'], expected['mode'])
        if name not in self.archives:
            self.archives[name] = self.inputs.open_archive(name, expected=expected)
            self.owner.borrowed.append(self.archives[name])
        self.owner.guard()
        return self.archives[name]

    def capture_tree(self, files, directories):
        self.owner.initial_work()
        new_keys = ({(id(self.inputs), name) for name in files} |
                    {(id(self.inputs), name, 'directory') for name in directories}) - set(self.owner.charged)
        if self.owner.input_members + len(new_keys) > self.owner.limits['maximum_members']:
            raise ValueError('Complete source tree exceeds the selected aggregate member bound')
        tree = self.inputs.capture_tree('', files=files, directories=directories)
        self.owner.borrowed.append(tree)
        observed = tree.as_dict()
        contract.fields(observed, ('root', 'files', 'directories', 'observed'), 'held source tree view')
        if observed['root'] != '' or observed['files'] != files or observed['directories'] != sorted(directories):
            raise ValueError('Actual held source tree differs from independent declarations')
        state = contract.fields(observed['observed'], ('files', 'directories'), 'held source observations')
        if (type(state['files']) is not dict or set(state['files']) != set(files) or
                type(state['directories']) is not dict or set(state['directories']) != {'', *directories}):
            raise ValueError('Actual held source tree observations are incomplete')
        for name in directories:
            self.owner.charge((id(self.inputs), name, 'directory'), 0, None, 0o755)
        for name, expected in files.items():
            self.owner.guard()
            item = state['files'][name]
            if type(item) is not dict or 'bytes' not in item:
                raise ValueError('Actual held source leaf EOF observation is absent')
            size = _integer(item['bytes'], 'actual held source leaf bytes', MAX_ARCHIVE, 0)
            if 'bytes' in expected and size != expected['bytes']:
                raise ValueError('Actual held source leaf differs from independent length')
            maximum = (self.owner.limits['maximum_archive_bytes'] if name in self.archives
                       else self.owner.limits['maximum_member_bytes'])
            if size > maximum:
                raise ValueError('Actual held source leaf exceeds its selected finite bound')
            self.owner.charge((id(self.inputs), name), size, expected['sha256'], expected['mode'])
            if name in self.raw or name in self.archives:
                continue
            stream = tree.open_file(name)
            self.owner.borrowed.append(stream)
            total, hasher = 0, hashlib.sha256()
            while True:
                self.owner.guard()
                block = stream.read(min(65536, size - total + 1))
                if type(block) is not bytes:
                    raise ValueError('Held source view must return immutable bytes')
                if not block:
                    break
                total += len(block)
                if total > size:
                    raise ValueError('Held source leaf exceeded its actual captured EOF')
                hasher.update(block)
            if total != size or hasher.hexdigest() != expected['sha256']:
                raise ValueError('Held source leaf differs from its independent hash/length')
        self.owner.check()
        return tree


class _PosixHeldTree:
    """Hold structural source identities; body pins belong to initial admission."""

    def __init__(self, root, files, directories, *, deadline):
        self._resources, self._directories, self._files = [], {}, {}
        self._closed, self._closing, self._failed = False, False, False
        self._close_error, self._root_anchor = None, None
        self._deadline = deadline
        try:
            handoff._qualified_posix()
            if (type(deadline) not in (int, float) or not math.isfinite(deadline)):
                raise ValueError('Held source tree requires its original finite deadline')
            self._live()
            self.expectations = copy.deepcopy(files)
            self.inventory = {'files': {name: item['sha256'] for name, item in files.items()},
                'directories': sorted(directories),
                'modes': {**{name: item['mode'] for name, item in files.items()},
                          **{name: 0o755 for name in directories}}}
            manifest.inventory_contract(self.inventory, '__source_replay_excluded_manifest__.json')
            directories = list(self.inventory['directories'])
            files = sorted(self.inventory['files'])
            if len(directories) + len(files) > MAX_MEMBERS:
                raise ValueError('Held source tree exceeds its hard member bound')
            registry = PathInventory()
            for relative in files:
                registry.add(_path(relative), False)
            for relative in directories:
                registry.add(_path(relative), True)
            self._expected_names = {relative: [] for relative in ('', *directories)}
            for relative in (*directories, *files):
                parent, _, name = relative.rpartition('/')
                if parent not in self._expected_names:
                    raise ValueError('Held source inventory omits a parent directory')
                self._expected_names[parent].append(name)
            self._expected_names = {name: tuple(sorted(children))
                                    for name, children in self._expected_names.items()}
            self.root = Path(_posix(os.fspath(root)))
            anchor = handoff._Anchor(self.root)
            self._resources.append({'anchor': anchor, 'attempted': False, 'closed': False})
            self._root_anchor = anchor
            state = manifest.plain_state(os.fstat(anchor.fd), True)
            self._directories[''] = {'fd': anchor.fd, 'state': state}
            self._live()
            for relative in sorted(directories, key=lambda name: (name.count('/'), name)):
                self._capture(relative, True)
            total = 0
            for relative in files:
                self._capture(relative, False)
                total += self._files[relative]['state'].st_size
                if total > MAX_EXPANDED:
                    raise ValueError('Held source tree exceeds its hard byte bound')
            self.check()
        except BaseException:
            self._failed = True
            try:
                self.close()
            except BaseException:
                # Constructor failure must not discard an uncertain actual owner.
                if not any(item is self for item in _UNCERTAIN_SOURCE_OWNERS):
                    _UNCERTAIN_SOURCE_OWNERS.append(self)
            raise

    @staticmethod
    def _facts(state):
        return (handoff._identity(state), stat.S_IMODE(state.st_mode), state.st_nlink,
                state.st_size, state.st_mtime_ns, state.st_ctime_ns)

    def _live(self):
        if self._closed or self._closing or self._failed:
            raise ValueError('Held source tree is failed or closed')
        try:
            _check_deadline(self._deadline)
        except BaseException:
            self._failed = True
            raise

    def _state(self, state, directory, *, expected_mode=None):
        state = manifest.plain_state(state, directory)
        if expected_mode is not None and stat.S_IMODE(state.st_mode) != expected_mode:
            raise ValueError('Held source entry mode differs from its inventory')
        if not directory and not 0 <= state.st_size <= MAX_ARCHIVE:
            raise ValueError('Held source file exceeds its hard byte bound')
        return state

    def _capture(self, relative, directory):
        self._live()
        parent, _, name = relative.rpartition('/')
        parent_fd = self._directories[parent]['fd']
        mode = 0o755 if directory else self.inventory['modes'][relative]
        before = self._state(os.stat(name, dir_fd=parent_fd, follow_symlinks=False),
                             directory, expected_mode=mode)
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        descriptor = os.open(name, flags, dir_fd=parent_fd)
        self._resources.append({'fd': descriptor, 'attempted': False, 'closed': False})
        held = self._state(os.fstat(descriptor), directory, expected_mode=mode)
        after = self._state(os.stat(name, dir_fd=parent_fd, follow_symlinks=False),
                            directory, expected_mode=mode)
        if self._facts(held) != self._facts(before) or self._facts(after) != self._facts(before):
            raise ValueError('Held source entry changed during structural capture')
        record = {'fd': descriptor, 'state': held}
        (self._directories if directory else self._files)[relative] = record
        self._live()

    def _check_directory(self, relative):
        self._live()
        record = self._directories[relative]
        expected = self._facts(record['state'])
        mode = None if not relative else 0o755
        held = self._state(os.fstat(record['fd']), True, expected_mode=mode)
        if self._facts(held) != expected:
            raise ValueError('Held source directory identity changed')
        if relative:
            parent, _, name = relative.rpartition('/')
            visible = self._state(os.stat(name, dir_fd=self._directories[parent]['fd'],
                                         follow_symlinks=False), True, expected_mode=mode)
            if self._facts(visible) != expected:
                raise ValueError('Held source directory path changed')
        else:
            self._root_anchor.check()
        self._live()

    def _check_leaf(self, relative, *, parents=True):
        self._live()
        if parents:
            self._check_directory('')
            pieces = relative.split('/')[:-1]
            for count in range(1, len(pieces) + 1):
                self._check_directory('/'.join(pieces[:count]))
        record = self._files[relative]
        parent, _, name = relative.rpartition('/')
        mode = self.inventory['modes'][relative]
        held = self._state(os.fstat(record['fd']), False, expected_mode=mode)
        visible = self._state(os.stat(name, dir_fd=self._directories[parent]['fd'],
                                     follow_symlinks=False), False, expected_mode=mode)
        if (self._facts(held) != self._facts(record['state']) or
                self._facts(visible) != self._facts(record['state'])):
            raise ValueError('Held source file identity changed')
        self._live()
        return record

    def _leaf_for_read(self, relative):
        try:
            return self._check_leaf(relative)
        except BaseException:
            self._failed = True
            raise

    def check(self):
        """Check physical facts and complete names, including originally empty dirs."""
        try:
            self._live()
            directories = sorted(self._directories, key=lambda name: (name.count('/'), name))
            for relative in directories:
                self._check_directory(relative)
                names = []
                with os.scandir(self._directories[relative]['fd']) as entries:
                    for entry in entries:
                        self._live()
                        if len(names) >= MAX_MEMBERS:
                            raise ValueError('Held source directory exceeds its hard member bound')
                        _path(relative + '/' + entry.name if relative else entry.name)
                        names.append(entry.name)
                if tuple(sorted(names)) != self._expected_names[relative]:
                    raise ValueError('Held source directory membership changed')
                self._check_directory(relative)
            for relative in sorted(self._files):
                self._check_leaf(relative, parents=False)
            # Recheck the retained path graph after the complete file pass.
            for relative in directories:
                self._check_directory(relative)
            self._live()
        except BaseException:
            self._failed = True
            raise

    def as_dict(self):
        self.check()
        return {'root': '', 'files': copy.deepcopy(self.expectations),
            'directories': list(self.inventory['directories']), 'observed': {
                'files': {name: {'bytes': item['state'].st_size,
                                'identity': self._facts(item['state'])}
                          for name, item in self._files.items()},
                'directories': {name: {'identity': self._facts(item['state'])}
                                for name, item in self._directories.items()}}}

    def open_file(self, relative):
        """Borrow one retained file; this grants no additional source admission."""
        self._live()
        relative = _path(relative)
        if relative not in self._files:
            raise ValueError('Held source read requires an inventoried ordinary file')
        record = self._leaf_for_read(relative)
        return _PosixHeldFile(self, relative, record['state'].st_size)

    def close(self):
        if self._close_error is not None:
            # Never retry an uncertain numeric descriptor; it could have been reused.
            raise self._close_error
        if self._closed:
            return
        self._closing = True
        errors = []
        for resource in reversed(self._resources):
            if resource['attempted']:
                continue
            resource['attempted'] = True
            try:
                if 'anchor' in resource:
                    resource['anchor'].close()
                else:
                    os.close(resource['fd'])
                resource['closed'] = True
            except BaseException as error:
                errors.append(error)
        if errors:
            self._failed = True
            self._close_error = errors[0]
            raise self._close_error
        self._closed = True
        self._resources.clear()


class _PosixHeldFile:
    """Bounded borrowing view with an independent logical cursor and no fileno."""

    def __init__(self, tree, relative, size):
        self._tree, self.name, self._size = tree, relative, size
        self._position, self.closed = 0, False

    def _live(self):
        if self.closed:
            raise ValueError('Held source file view is closed')
        self._tree._live()

    def read(self, size=-1):
        self._live()
        if type(size) is not int or size < -1:
            raise ValueError('Held source read requires a finite integer request or -1')
        remaining = self._size - self._position
        wanted = remaining if size == -1 else min(size, remaining)
        chunks = []
        try:
            record = self._tree._leaf_for_read(self.name)
            while wanted:
                self._live()
                block = os.pread(record['fd'], min(wanted, 65536), self._position)
                if not block:
                    raise ValueError('Held source file became shorter during its initial read')
                chunks.append(block)
                self._position += len(block)
                wanted -= len(block)
                self._tree._leaf_for_read(self.name)
            self._tree._leaf_for_read(self.name)
            return b''.join(chunks)
        except BaseException:
            self._tree._failed = True
            raise

    def readinto(self, buffer):
        target = memoryview(buffer).cast('B')
        if target.readonly:
            raise TypeError('Held source readinto requires a writable buffer')
        raw = self.read(len(target))
        target[:len(raw)] = raw
        return len(raw)

    def seek(self, offset, whence=0):
        self._live()
        if type(offset) is not int or type(whence) is not int or whence not in (0, 1, 2):
            raise ValueError('Held source seek requires an integer offset and standard origin')
        base = (0, self._position, self._size)[whence]
        position = base + offset
        if not 0 <= position <= self._size:
            raise ValueError('Held source seek exceeds its original file length')
        self._position = position
        return position

    def tell(self):
        self._live()
        return self._position

    def readable(self):
        self._live()
        return True

    def seekable(self):
        self._live()
        return True

    def close(self):
        self.closed = True

    def __enter__(self):
        self._live()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class _PosixSourceInputs:
    """Selected POSIX leaves remain held through the later complete tree join."""
    def __init__(self, root, *, deadline):
        handoff._qualified_posix()
        self.root, self.deadline = handoff._absolute(os.fspath(root)), deadline
        self.leaves, self.trees, self.closed, self.close_error = {}, [], False, None
        self.resources, self.failed = [], False

    def _open(self, name, expected):
        self.check()
        name = _path(name)
        if name in self.leaves:
            item = self.leaves[name]
            if (item['pin'] != expected['sha256'] or item['mode'] != expected['mode'] or
                    ('bytes' in expected and item['state'].st_size != expected['bytes'])):
                raise ValueError('Conflicting POSIX source leaf expectations')
            return item
        path = self.root / name
        anchor = handoff._Anchor(path.parent)
        self.resources.append({'resource': anchor, 'attempted': False})
        try:
            state = manifest.plain_state(os.stat(path.name, dir_fd=anchor.fd, follow_symlinks=False), False)
            if (stat.S_IMODE(state.st_mode) != expected['mode'] or state.st_size > MAX_ARCHIVE or
                    ('bytes' in expected and state.st_size != expected['bytes'])):
                raise ValueError('POSIX source leaf differs from independent mode/length')
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=anchor.fd)
            held = {'descriptor': descriptor, 'attempted': False}
            self.resources.append(held)
            if handoff._identity(os.fstat(descriptor)) != handoff._identity(state):
                raise ValueError('POSIX source leaf changed before capture')
            stream = os.fdopen(descriptor, 'rb')
            del held['descriptor']
            held['resource'] = stream
            item = {'anchor': anchor, 'stream': stream, 'state': state,
                'path': path, 'pin': expected['sha256'], 'mode': expected['mode']}
            self.leaves[name] = item
            return item
        except BaseException:
            self.failed = True
            try:
                self.close()
            except BaseException:
                if not any(item is self for item in _UNCERTAIN_SOURCE_OWNERS):
                    _UNCERTAIN_SOURCE_OWNERS.append(self)
            raise

    def read(self, name, *, expected, maximum):
        item = self._open(name, expected)
        if item['state'].st_size > maximum:
            raise ValueError('POSIX source metadata exceeds finite bound')
        item['stream'].seek(0)
        raw = item['stream'].read(maximum + 1)
        self.check()
        if len(raw) != item['state'].st_size or digest(raw) != expected['sha256']:
            raise ValueError('POSIX source metadata differs from independent pin/length')
        return raw

    def open_archive(self, name, *, expected):
        item = self._open(name, expected)
        item['stream'].seek(0)
        return item['stream']

    def capture_tree(self, relative, *, files, directories):
        if relative != '':
            raise ValueError('Source tree must capture the exact selected owner root')
        tree = _PosixHeldTree(self.root, files, directories, deadline=self.deadline)
        self.trees.append(tree)
        self.check()
        return tree

    def check(self):
        if self.closed or self.failed:
            raise ValueError('POSIX selected source owner is failed or closed')
        _check_deadline(self.deadline)
        for item in self.leaves.values():
            item['anchor'].check()
            if (item['stream'].closed or
                    handoff._identity(os.fstat(item['stream'].fileno())) != handoff._identity(item['state']) or
                    handoff._identity(os.stat(item['path'].name, dir_fd=item['anchor'].fd,
                        follow_symlinks=False)) != handoff._identity(item['state'])):
                raise ValueError('Held POSIX source leaf physical identity changed')
        for tree in self.trees:
            tree.check()
        _check_deadline(self.deadline)

    def close(self):
        if self.close_error is not None:
            raise self.close_error
        if self.closed:
            return
        errors = []
        for tree in reversed(self.trees):
            try:
                tree.close()
            except BaseException as error:
                errors.append(error)
        for resource in reversed(self.resources):
            if resource['attempted']:
                continue
            resource['attempted'] = True
            try:
                if 'descriptor' in resource:
                    os.close(resource['descriptor'])
                else:
                    resource['resource'].close()
            except BaseException as error:
                errors.append(error)
        if errors:
            self.close_error = errors[0]
            raise self.close_error
        self.closed = True


def check_records(projection, captured_records, archive_streams, original_proof_records, limits, *, deadline=None):
    """Join actual shared checked authority; plain views never supply proof."""
    api = require_original_proof_seam()
    limits = validate_limits(limits)
    _check_deadline(deadline)
    if deadline is not None:
        limits['seconds'] = min(limits['seconds'], deadline - time.monotonic())
        if limits['seconds'] <= 0:
            raise ValueError('Source replay exceeded its original wall budget')
    checked = api.parse_source_projection_records(projection, captured_records,
                                                   archive_streams, limits)
    facts = api.validate_source_provenance_records(checked, captured_records['provenance'],
                                                   original_proof_records)
    _check_deadline(deadline)
    return checked, facts


class _CapturedSource:
    """One bounded POSIX capture; original paths remain inert record identities."""
    def __init__(self, projection, bindings, limits, *, resolve, deadline=None, relative=True):
        handoff._qualified_posix()
        self.projection = validate_projection_metadata(projection)
        self.bindings = validate_bindings(bindings, relative=relative)
        self.limits = validate_limits(limits)
        self.deadline = min(time.monotonic() + self.limits['seconds'],
                            math.inf if deadline is None else deadline)
        self.records = {'archives': {}, 'provenance': {}, 'patches': [], 'notices': []}
        self.original_proof, self.streams, self._inputs = {}, {}, {}
        self.closed, self.failed, self._resolve = False, False, resolve
        self._captured_bytes = 0
        try:
            _binding_projection(self.projection, self.bindings)
            for key, item in self.projection['archives'].items():
                bound = self.bindings['archives'][key]
                stream, state = self._open(bound)
                self.streams[key] = stream
                self.records['archives'][key] = self._record(item['path'], bound)
            for item in self.projection['provenance']:
                self.records['provenance'][item['role']] = self._metadata_record(
                    item['path'], self.bindings['provenance'][item['role']])
            for key in ('patches', 'notices'):
                for original, bound in zip(self.projection[key], self.bindings[key]):
                    self.records[key].append(self._metadata_record(original['path'], bound))
            self._capture_original_proof()
            self.check()
        except BaseException:
            self.failed = True
            self.close()
            raise

    def remaining_limits(self):
        self._live()
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('Source capture exceeded its original wall budget')
        return {**self.limits, 'seconds': min(self.limits['seconds'], remaining)}

    def _live(self):
        if self.closed or self.failed:
            raise ValueError('Source capture is failed or closed')
        if time.monotonic() >= self.deadline:
            raise ValueError('Source capture exceeded its original wall budget')

    @staticmethod
    def _record(original_path, bound, raw=None):
        result = {'path': original_path, **{name: bound[name] for name in ('sha256', 'bytes', 'mode')}}
        if raw is not None:
            result['raw'] = raw
        return result

    def _open(self, bound, *, allow_executable=False, active_path=None):
        self._live()
        path = handoff._absolute(os.fspath(self._resolve(bound['path']) if active_path is None else active_path))
        allowed = (0o644, 0o755) if allow_executable else (0o644,)
        if type(bound['mode']) is not int or bound['mode'] not in allowed:
            raise ValueError('Windows captured source inputs require original mode0644')
        previous = self._inputs.get(str(path))
        if previous is not None:
            if any(previous['binding'][key] != bound[key] for key in ('sha256', 'bytes', 'mode')):
                raise ValueError('Conflicting capture facts for one selected source path')
            previous['stream'].seek(0)
            return previous['stream'], previous['state']
        anchor, stream = handoff._Anchor(path.parent), None
        try:
            state = manifest.plain_state(os.stat(path.name, dir_fd=anchor.fd, follow_symlinks=False), False)
            if (stat.S_IMODE(state.st_mode) != bound['mode'] or state.st_size != bound['bytes'] or
                    not 0 <= state.st_size <= MAX_ARCHIVE):
                raise ValueError('Selected source mode/length differs from its binding')
            if (len(self._inputs) >= self.limits['maximum_members'] or
                    self._captured_bytes + state.st_size > self.limits['maximum_expanded_bytes']):
                raise ValueError('Complete captured source exceeds its byte/member budget')
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=anchor.fd)
            try:
                if handoff._identity(os.fstat(descriptor)) != handoff._identity(state):
                    raise ValueError('Selected source changed before capture')
                stream = os.fdopen(descriptor, 'rb')
            except BaseException:
                os.close(descriptor)
                raise
            self._inputs[str(path)] = {'path': path, 'anchor': anchor, 'stream': stream,
                'state': state, 'binding': copy.deepcopy(bound), 'descriptor': stream.fileno()}
            self._captured_bytes += state.st_size
            return stream, state
        except BaseException:
            if stream is not None:
                stream.close()
            anchor.close()
            raise

    def _metadata_record(self, original_path, bound):
        stream, state = self._open(bound)
        if state.st_size > MAX_DOCUMENT:
            raise ValueError('Captured source metadata exceeds its finite bound')
        self._live()
        stream.seek(0)
        raw = stream.read(MAX_DOCUMENT + 1)
        if len(raw) != bound['bytes'] or digest(raw) != bound['sha256']:
            raise ValueError('Captured original metadata hash/length differs')
        self.check()
        return self._record(original_path, bound, raw)

    def capture_extra(self, path, sha256, size, mode, *, maximum=MAX_MEMBER):
        """Capture a current pinned common input, retaining the same owner."""
        contract.pin(sha256, 'current source input')
        _integer(size, 'current source input bytes', maximum, 0)
        bound = {'path': os.fspath(path), 'sha256': sha256, 'bytes': size, 'mode': mode}
        stream, state = self._open(bound, allow_executable=True, active_path=path)
        self._live()
        stream.seek(0)
        raw = stream.read(maximum + 1)
        if len(raw) != size or digest(raw) != sha256:
            raise ValueError('Current source input differs from independent hash/length')
        self.check()
        return raw

    def _capture_original_proof(self):
        body = handoff._document(self.records['provenance']['engine-body-verification']['raw'])
        if type(body) is not dict or body.get('kind') != 'foundation-native-engine-retained-body-evidence-v1':
            raise ValueError('Windows source capture requires original retained-body references')
        references = contract.fields(body.get('original_proof'), ORIGINAL_PROOF_ROLES,
                                      'unchecked original proof reference discovery')
        for role, item in references.items():
            contract.fields(item, ('path', 'sha256', 'bytes'), 'unchecked original proof reference')
            if type(item['path']) is not str or not item['path']:
                raise ValueError('Original proof reference spelling is absent')
            contract.pin(item['sha256'], 'original proof reference')
            _integer(item['bytes'], 'original proof reference bytes', MAX_DOCUMENT)
            bound = self.bindings['original_proof'][role]
            if any(bound[key] != item[key] for key in ('sha256', 'bytes')):
                raise ValueError('Relocated original proof hash/length differs from original reference')
            self.original_proof[role] = self._metadata_record(item['path'], bound)

    def check(self):
        self._live()
        for item in self._inputs.values():
            item['anchor'].check()
            stream = item['stream']
            if (stream.closed or stream.fileno() != item['descriptor'] or
                    handoff._identity(os.fstat(stream.fileno())) != handoff._identity(item['state']) or
                    handoff._identity(os.stat(item['path'].name, dir_fd=item['anchor'].fd,
                        follow_symlinks=False)) != handoff._identity(item['state'])):
                raise ValueError('Captured source identity changed')
        self._live()

    def checked(self):
        self.check()
        result = check_records(self.projection, self.records, self.streams,
                               self.original_proof, self.remaining_limits(), deadline=self.deadline)
        self.check()
        return result

    @property
    def patch_bytes(self):
        return [item['raw'] for item in self.records['patches']]

    def close(self):
        if not self.closed:
            errors = []
            for item in self._inputs.values():
                for resource in (item['stream'], item['anchor']):
                    try:
                        resource.close()
                    except BaseException as error:
                        errors.append(error)
            self.closed = True
            if errors:
                raise errors[0]


def _path(value):
    name = manifest.path_name(value)
    if len(name) > 4096 or len(name.split('/')) > MAX_DEPTH:
        raise ValueError('Source replay path exceeds finite length/depth bound')
    return name


def _posix(value):
    if (type(value) is not str or not value.startswith('/') or value.startswith('//')
            or PurePosixPath(value).as_posix() != value
            or '..' in PurePosixPath(value).parts
            or any(char in value for char in ('\\', ':', ';', '\x00', '\n', '\r'))):
        raise ValueError('Explicit normalized lexical POSIX absolute path required')
    contract.text(value, 'POSIX source metadata path')
    return value


def _ref(value, *, relative=True):
    contract.fields(value, ('path', 'sha256'), 'source replay reference')
    (_path if relative else _posix)(value['path'])
    contract.pin(value['sha256'], 'source replay reference')
    return copy.deepcopy(value)


def _integer(value, label, maximum, minimum=1):
    return manifest.integer(value, label, minimum, maximum)


def validate_limits(value):
    """All budgets are explicit, finite, positive and no wider than the source caps."""
    maximums = {'maximum_archive_bytes': MAX_ARCHIVE,
                'maximum_expanded_bytes': MAX_EXPANDED,
                'maximum_members': MAX_MEMBERS,
                'maximum_member_bytes': MAX_MEMBER,
                'maximum_patch_bytes': MAX_DOCUMENT}
    contract.fields(value, ('seconds', *maximums), 'source replay limits')
    seconds = value['seconds']
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 86400:
        raise ValueError('Source replay seconds must be finite, positive and bounded')
    for key, maximum in maximums.items():
        _integer(value[key], key, maximum)
    return copy.deepcopy(value)


def validate_bindings(value, relative=True):
    """Validate relocation declarations, without reading their referenced bodies."""
    contract.fields(value, ('archives', 'provenance', 'original_proof', 'patches', 'notices'),
                    'source replay bindings')
    registry = PathInventory()
    registered = {}
    def binding(item, maximum):
        contract.fields(item, ('path', 'sha256', 'bytes', 'mode'), 'source replay binding')
        (_path if relative else _posix)(item['path'])
        contract.pin(item['sha256'], 'bound source input')
        _integer(item['bytes'], 'bound source bytes', maximum)
        if type(item['mode']) is not int or item['mode'] != 0o644:
            raise ValueError('Original source bindings require ordinary mode0644')
        previous = registered.get(item['path'])
        if previous is not None and previous != item:
            raise ValueError('Conflicting relocation of an original input')
        if previous is None and relative:
            registry.add(item['path'], False)
        registered[item['path']] = dict(item)
    archives = value['archives']
    if type(archives) is not dict or not 2 <= len(archives) <= 16:
        raise ValueError('Complete bounded original archive bindings required')
    for key, item in archives.items():
        if '/' in _path(key):
            raise ValueError('Archive logical keys require one portable component')
        binding(item, MAX_ARCHIVE)
    provenance = value['provenance']
    if (type(provenance) is not dict or not SOURCE_PROVENANCE_ROLES <= set(provenance)
            or not set(provenance) <= SOURCE_PROVENANCE_ROLES | SOURCE_PROVENANCE_OPTIONAL):
        raise ValueError('Complete original provenance binding roles required')
    for item in provenance.values():
        binding(item, MAX_DOCUMENT)
    contract.fields(value['original_proof'], ORIGINAL_PROOF_ROLES, 'seven original proof bindings')
    for item in value['original_proof'].values():
        binding(item, MAX_DOCUMENT)
    for key, minimum in (('patches', 0), ('notices', 1)):
        items = value[key]
        if type(items) is not list or not minimum <= len(items) <= 256:
            raise ValueError('Bounded ordered original ' + key + ' bindings required')
        seen = set()
        for item in items:
            binding(item, MAX_DOCUMENT)
            if item['path'] in seen:
                raise ValueError('Duplicate ordered original ' + key + ' binding')
            seen.add(item['path'])
    return copy.deepcopy(value)


def validate_projection_metadata(value):
    """Check the source-only projection shape; preserve the Linux parser's guard."""
    contract.fields(value, ('schema_version', 'kind', 'suppliers', 'archives', 'projection',
                            'patches', 'notices', 'provenance'), 'source projection')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-native-engine-prototype-sources-v1'):
        raise ValueError('Unsupported original source projection')
    archives = value['archives']
    if type(archives) is not dict or not 2 <= len(archives) <= 16:
        raise ValueError('Both original ordinary supplier archives required')
    contract.fields(value['suppliers'], ('wrapper', 'engine'), 'complete suppliers')
    for supplier, item in value['suppliers'].items():
        contract.fields(item, ('repository', 'commit', 'archive'), 'source supplier')
        if (not contract.text(item['repository'], 'supplier repository').startswith('https://')
                or item['commit'] != COMMITS[supplier] or item['archive'] not in archives):
            raise ValueError('Original pinned supplier commit/archive differs')
    if len({item['archive'] for item in value['suppliers'].values()}) != 2:
        raise ValueError('Supplier archives must be distinct')
    projection = contract.fields(value['projection'], ('files', 'directories', 'exclusions',
                                                     'normalizations'), 'source projection members')
    files = projection['files']
    if type(files) is not dict or not files or len(files) > MAX_MEMBERS:
        raise ValueError('Complete bounded source projection files required')
    registry = PathInventory()
    for name, item in files.items():
        registry.add(_path(name), False)
        contract.fields(item, ('archive', 'member', 'sha256', 'bytes', 'mode'), 'projected file')
        if not name.startswith(('source/wrapper/', 'source/engine/')):
            raise ValueError('Projected source must belong to a declared supplier')
        supplier = name.split('/')[1]
        if (item['archive'] != value['suppliers'][supplier]['archive']
                or name != 'source/' + supplier + '/' + _path(item['member'])):
            raise ValueError('Supplier projection must preserve exact member paths')
        contract.pin(item['sha256'], 'projected source')
        _integer(item['bytes'], 'projected source bytes', MAX_MEMBER, 0)
        if type(item['mode']) is not int or item['mode'] not in (0o644, 0o755):
            raise ValueError('Projected file mode requires0644/0755')
    if projection['directories'] != _parents(files):
        raise ValueError('Projection directories must exactly cover source parents')
    for name in projection['directories']:
        registry.add(_path(name), True)
    required = {'source/wrapper/README.md', 'source/wrapper/src/embedder/main.cpp',
                'source/engine/CMakeLists.txt', 'source/engine/Source/cmake/WebKitCommon.cmake'}
    if not required <= set(files) or not any(name.startswith('source/engine/Tools/') for name in files):
        raise ValueError('Complete supplier root, Source and Tools inputs required')
    for key in ('exclusions', 'normalizations'):
        contract.fields(projection[key], archives, 'per-archive ' + key)
    for key, archive in archives.items():
        if '/' in _path(key):
            raise ValueError('Archive logical key requires one component')
        contract.fields(archive, ('path', 'sha256', 'bytes', 'format', 'strip_prefix'), 'source archive')
        _path(archive['path'])
        contract.pin(archive['sha256'], 'source archive')
        _integer(archive['bytes'], 'source archive bytes', MAX_ARCHIVE)
        if archive['format'] not in ('tar-gzip', 'tar-xz', 'zip'):
            raise ValueError('Unsupported bounded ordinary source archive format')
        if archive['strip_prefix'] != '':
            _path(archive['strip_prefix'])
        exclusions = projection['exclusions'][key]
        manifest.paths(exclusions, 'source exclusions')
        for name in exclusions:
            _path(name)
        if key == value['suppliers']['engine']['archive'] and any(
                name in ('Source', 'Tools', 'CMakeLists.txt') or name.startswith(('Source/', 'Tools/'))
                for name in exclusions):
            raise ValueError('Engine Source/Tools generator closure cannot be excluded')
        normalizations = projection['normalizations'][key]
        if type(normalizations) is not dict or len(normalizations) > 65536:
            raise ValueError('Bounded explicit direct link normalizations required')
        for member, target in normalizations.items():
            _path(member)
            _path(target)
    provenance = value['provenance']
    if type(provenance) is not list or not 6 <= len(provenance) <= 8:
        raise ValueError('Complete original provenance references required')
    roles = []
    for item in provenance:
        contract.fields(item, ('role', 'path', 'sha256', 'bytes'), 'source provenance reference')
        role = item['role']
        if type(role) is not str or role not in SOURCE_PROVENANCE_ROLES | SOURCE_PROVENANCE_OPTIONAL:
            raise ValueError('Unknown source provenance role')
        roles.append(role)
        _ref({key: item[key] for key in ('path', 'sha256')})
        _integer(item['bytes'], 'provenance reference bytes', MAX_DOCUMENT)
    if roles != sorted(set(roles)) or not SOURCE_PROVENANCE_ROLES <= set(roles):
        raise ValueError('Source provenance roles must be sorted, unique and complete')
    patches = value['patches']
    if type(patches) is not list or len(patches) > 256:
        raise ValueError('Bounded ordered exact patches required')
    seen = set()
    for item in patches:
        contract.fields(item, ('path', 'sha256', 'tree', 'preimages', 'postimages'), 'source patch')
        _ref({key: item[key] for key in ('path', 'sha256')})
        if item['path'] in seen or item['tree'] not in ('wrapper', 'engine'):
            raise ValueError('Duplicate or invalid ordered source patch')
        seen.add(item['path'])
        before, after = item['preimages'], item['postimages']
        if (type(before) is not dict or not before or len(before) > MAX_MEMBERS
                or type(after) is not dict or set(before) != set(after)):
            raise ValueError('Patch requires exact before/after images')
        for name, image in before.items():
            _path(name)
            if image is None and after[name] is None:
                raise ValueError('Patch cannot have two absent images')
            for pin in (image, after[name]):
                if pin is not None:
                    contract.pin(pin, 'patch image')
    if type(value['notices']) is not list or not 1 <= len(value['notices']) <= 256:
        raise ValueError('Explicit bounded source notices required')
    notice_paths = []
    for item in value['notices']:
        _ref(item)
        notice_paths.append(item['path'])
    if len(set(notice_paths)) != len(notice_paths):
        raise ValueError('Duplicate source notice reference')
    return copy.deepcopy(value)


def _parents(names):
    return sorted({parent.as_posix() for name in names for parent in PurePosixPath(name).parents
                   if parent.as_posix() != '.'})


def catalogue_metadata(map_raw, provenance_raw, graph_raw):
    """Validate the current pinned catalogue and157/48/32,25-alias,16-interface joins."""
    raw = {'source_map': map_raw, 'provenance': provenance_raw, 'graph': graph_raw}
    catalogue = contract.catalogue_for_map_digest(digest(map_raw))
    for role, body in raw.items():
        if type(body) is not bytes or len(body) > MAX_DOCUMENT or digest(body) != catalogue[role]['sha256']:
            raise ValueError('Current Windows source catalogue pin differs: ' + role)
    source_map, provenance = (handoff._document(raw[role]) for role in ('source_map', 'provenance'))
    inputs = source_map.get('inputs') if type(source_map) is dict else None
    composition = source_map.get('kind') == native_inputs.COMPOSITION_SOURCE_KIND
    expected_counts = (native_inputs.composition_catalogue_counts(source_map) if composition else
        {'source_files': 157, 'engine_files': 48, 'direct_translation_units': 32})
    if type(inputs) is not dict or len(inputs) != (198 if composition else 197):
        raise ValueError('Composition source catalogue requires198 complete inputs' if composition else 'Current source catalogue requires197 complete inputs')
    registry = PathInventory()
    for name, item in inputs.items():
        registry.add(_path(name), False)
        contract.fields(item, ('sha256', 'mode', 'role', 'bytes', 'tracked_path', 'origin'), 'catalogue source input')
        contract.pin(item['sha256'], 'catalogue source input')
        _integer(item['bytes'], 'catalogue input bytes', MAX_MEMBER, 0)
        if type(item['mode']) is not int or item['mode'] not in (0o644, 0o755):
            raise ValueError('Catalogue file mode requires0644/0755')
        if type(item['role']) is not str or item['role'] not in manifest.ROLES | {'provenance'}:
            raise ValueError('Unknown catalogue source role')
        _path(item['tracked_path'])
        if type(item['origin']) is not dict:
            raise ValueError('Explicit catalogue source origin required')
    overlays = {name: item for name, item in inputs.items()
                if name.startswith('source/') and item['role'] == 'source'}
    try:
        graph = graph_raw.decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Invalid finite UTF-8 source graph') from error
    blocks = re.findall(r'set\(_sources\s+(.*?)\)\s*# document_forms', graph, re.S)
    units = re.findall(r'"([^"\n]+)"', blocks[0]) if len(blocks) == 1 else []
    if len(units) != len(set(units)):
        raise ValueError('Source graph has duplicate translation units')
    counts = {'source_files': len(overlays),
              'engine_files': sum(name.startswith('source/engine/') for name in overlays),
              'direct_translation_units': len(units)}
    if (counts != expected_counts
            or type(provenance) is not dict or any(
                type(provenance.get('source_graph', {}).get(key)) is not int
                or provenance['source_graph'][key] != count for key, count in counts.items())):
        raise ValueError('Current native157/engine48/32TU source graph differs')
    mapping = provenance.get('retained_input_mapping')
    if type(mapping) is not dict or len(mapping) != 25:
        raise ValueError('Current retained source alias closure requires25 entries')
    alias_registry = PathInventory()
    for name, item in mapping.items():
        alias_registry.add(_path(name), False)
        contract.fields(item, ('role', 'sha256', 'tracked_source'), 'retained catalogue alias')
        original = inputs.get(_path(item['tracked_source']))
        if (original is None or item['sha256'] != original['sha256']
                or type(item['role']) is not str or item['role'] not in manifest.ROLES):
            raise ValueError('Current retained alias differs from source catalogue')
    pins = provenance.get('interface_pins')
    if type(pins) is not dict or len(pins) != 16:
        raise ValueError('Current rich4083 interface closure requires16 entries')
    for key, item in pins.items():
        contract.text(key, 'interface pin key')
        contract.fields(item, ('retained_logical_path', 'role', 'sha256', 'tracked_source'), 'interface catalogue pin')
        alias = mapping.get(_path(item['retained_logical_path']))
        if (alias is None or item['role'] != 'interface' or alias['role'] != 'interface'
                or item['sha256'] != alias['sha256'] or item['tracked_source'] != alias['tracked_source']):
            raise ValueError('Current rich4083 interface alias differs')
    for required in (handoff.GENERATOR, handoff.TEMPLATE, handoff.CONFIG):
        if required not in mapping:
            raise ValueError('Current native metadata source alias missing')
    return {'source_map': copy.deepcopy(source_map), 'provenance': copy.deepcopy(provenance),
            'overlays': copy.deepcopy(overlays), 'counts': counts}


class _Budget:
    def __init__(self, limits):
        self.limits = validate_limits(limits)
        self.deadline = time.monotonic() + self.limits['seconds']
        self.members = self.expanded = 0

    def check(self):
        if time.monotonic() > self.deadline:
            raise ValueError('Source replay exceeded its explicit wall budget')

    def member(self, size):
        self.check()
        _integer(size, 'expanded member bytes', self.limits['maximum_member_bytes'], 0)
        self.members += 1
        self.expanded += size
        if (self.members > self.limits['maximum_members']
                or self.expanded > self.limits['maximum_expanded_bytes']):
            raise ValueError('Source replay exceeds member/expanded byte budget')


class _BoundedStream:
    """Bound an already supplied seekable stream without owning or closing it."""
    def __init__(self, stream, size, budget):
        self.stream, self.size, self.budget = stream, size, budget
        if not all(callable(getattr(stream, name, None)) for name in ('read', 'seek', 'tell')):
            raise ValueError('Source replay requires an explicit seekable binary stream')

    def read(self, size=-1):
        self.budget.check()
        position = self.tell()
        if position < 0 or position > self.size:
            raise ValueError('Source archive stream position exceeds declared bound')
        amount = self.size - position + 1 if size is None or size < 0 else min(size, self.size - position + 1)
        result = self.stream.read(amount)
        if type(result) is not bytes or len(result) > amount or position + len(result) > self.size:
            raise ValueError('Source archive stream exceeds declared byte bound')
        self.budget.check()
        return result

    def seek(self, offset, whence=0):
        self.budget.check()
        result = self.stream.seek(offset, whence)
        position = self.stream.tell()
        if type(position) is not int or not 0 <= position <= self.size:
            raise ValueError('Source archive seek exceeds declared byte bound')
        return result

    def tell(self):
        self.budget.check()
        return self.stream.tell()

    def seekable(self):
        return True


class _ExpandedTarStream:
    """Bound decompressor output and XZ dictionary memory before tar parsing."""
    def __init__(self, source, archive_format, budget):
        self.source, self.budget = source, budget
        self.xz = archive_format == 'tar-xz'
        self.decoder = (lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=MAX_MEMBER)
                        if self.xz else zlib.decompressobj(16 + zlib.MAX_WBITS))
        self.pending, self.compressed, self.total = b'', b'', 0
        # Include finite tar headers/padding and bounded extended metadata. Member
        # payload bytes have their separate, stricter cumulative budget below.
        self.maximum = (budget.limits['maximum_expanded_bytes']
                        + budget.limits['maximum_members'] * 1024 + 10240)

    def read(self, size):
        if type(size) is not int or not 0 <= size <= MAX_MEMBER + 10240:
            raise ValueError('Unbounded tar parser read is unsupported')
        chunks, count = [], 0
        while count < size:
            self.budget.check()
            if self.pending:
                block, self.pending = self.pending[:size - count], self.pending[size - count:]
                chunks.append(block)
                count += len(block)
                continue
            if self.decoder.eof:
                break
            needs_input = self.decoder.needs_input if self.xz else not self.compressed
            if needs_input:
                self.compressed = self.source.read(65536)
                if not self.compressed:
                    raise ValueError('Truncated compressed source archive')
            if self.xz:
                self.pending = self.decoder.decompress(self.compressed, max_length=65536)
                self.compressed = b''
            else:
                self.pending = self.decoder.decompress(self.compressed, 65536)
                self.compressed = self.decoder.unconsumed_tail
            self.total += len(self.pending)
            if self.total > self.maximum:
                raise ValueError('Expanded tar headers/payload exceed finite stream budget')
        return b''.join(chunks)


def _zip_record(central, position):
    """Decode one fixed ordinary central record without constructing a ZipInfo."""
    if len(central) - position < 46 or central[position:position + 4] != b'PK\x01\x02':
        raise ValueError('Source ZIP central directory has an invalid raw record')
    flags, method = struct.unpack_from('<HH', central, position + 8)
    crc, compressed, expanded = struct.unpack_from('<III', central, position + 16)
    name_bytes, extra_bytes, comment_bytes, disk = struct.unpack_from('<HHHH', central, position + 28)
    external, local = struct.unpack_from('<II', central, position + 38)
    end = position + 46 + name_bytes + extra_bytes + comment_bytes
    if not name_bytes or end > len(central) or disk or 0xffffffff in (compressed, expanded, local):
        raise ValueError('Source ZIP central directory record exceeds ordinary finite bounds')
    raw_name = central[position + 46:position + 46 + name_bytes]
    try:
        name = raw_name.decode('utf-8' if flags & 0x800 else 'cp437')
    except UnicodeError as error:
        raise ValueError('Invalid source ZIP central path encoding') from error
    return {'name': name, 'flags': flags, 'method': method, 'crc': crc,
            'compressed': compressed, 'expanded': expanded, 'external': external,
            'local': local}, end


def _zip_directory(source, budget):
    """Count the actual bounded raw central span before ZipFile allocates an index."""
    source.seek(0, 2)
    size = source.tell()
    tail_start = max(0, size - 65557)
    source.seek(tail_start)
    tail = source.read(65557)
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError('Source ZIP lacks a bounded end-of-directory record')
    disk, central_disk, count_disk, count, central_bytes, central_start, comment_bytes = struct.unpack_from(
        '<HHHHIIH', tail, offset + 4)
    end_position = tail_start + offset
    remaining = budget.limits['maximum_members'] - budget.members
    if (disk or central_disk or count_disk != count or count == 65535 or count > remaining
            or central_bytes > MAX_DOCUMENT or central_start == 0xffffffff
            or central_start + central_bytes != end_position
            or offset + 22 + comment_bytes != len(tail)):
        raise ValueError('Source ZIP central directory exceeds explicit ordinary bounds')
    # Include the20-byte ZIP64 probe preceding the central span. ZipFile always
    # probes immediately before EOCD, even when its ordinary fields are small.
    freeze_start = max(0, central_start - 20)
    prefix_bytes = central_start - freeze_start
    source.seek(freeze_start)
    raw_central = source.read(prefix_bytes + central_bytes)
    if len(raw_central) != prefix_bytes + central_bytes:
        raise ValueError('Truncated source ZIP central directory')
    central = raw_central[prefix_bytes:]
    frozen_metadata = raw_central + tail[offset:]
    locator_offset = end_position - 20 - freeze_start
    if end_position >= 20 and frozen_metadata[locator_offset:locator_offset + 4] == b'PK\x06\x07':
        raise ValueError('Source ZIP64 locator is outside the ordinary bounded contract')
    position = actual_count = 0
    expanded = budget.expanded
    while position < len(central):
        budget.check()
        actual_count += 1
        if actual_count > remaining:
            raise ValueError('Source ZIP raw central count exceeds explicit member budget')
        record, position = _zip_record(central, position)
        _integer(record['expanded'], 'ZIP member bytes', budget.limits['maximum_member_bytes'], 0)
        expanded += record['expanded']
        if expanded > budget.limits['maximum_expanded_bytes']:
            raise ValueError('Source ZIP exceeds explicit expanded byte budget')
        if (record['local'] + 30 > central_start
                or record['compressed'] > central_start - record['local'] - 30):
            raise ValueError('Source ZIP member crosses its bounded local-data span')
        if record['flags'] & (1 | 0x40 | 0x2000):
            raise ValueError('Encrypted source ZIP members are unsupported')
        # These methods have bounded decoder dictionaries. Other ZIP methods
        # need a separately implemented dictionary admission before construction.
        if record['method'] not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2):
            raise ValueError('Source ZIP compression lacks a bounded decoder admission')
    if actual_count != count:
        raise ValueError('Source ZIP raw central count differs from its end record')
    return central_start, central, freeze_start, frozen_metadata, size, count


class _FrozenZipMetadata:
    """One ZIP reader sees the immutable central/EOCD bytes just bounded above."""
    def __init__(self, source, start, metadata, size):
        self.source, self.start, self.metadata, self.size = source, start, metadata, size

    def read(self, size=-1):
        position = self.tell()
        amount = self.size - position if size is None or size < 0 else min(size, self.size - position)
        if amount < 0 or amount > MAX_MEMBER:
            raise ValueError('ZIP reader requested an unbounded raw buffer')
        chunks = []
        if position < self.start:
            prefix = self.source.read(min(amount, self.start - position))
            chunks.append(prefix)
            position += len(prefix)
            amount -= len(prefix)
            if position < self.start:
                return b''.join(chunks)
        if amount:
            block = self.metadata[position - self.start:position - self.start + amount]
            chunks.append(block)
            self.source.seek(position + len(block))
        return b''.join(chunks)

    def seek(self, offset, whence=0):
        return self.source.seek(offset, whence)

    def tell(self):
        return self.source.tell()

    def seekable(self):
        return True


def _zip_entries(source, budget):
    start, central, freeze_start, frozen_metadata, size, count = _zip_directory(source, budget)
    # Freeze the metadata span, not supplier member bodies. A same-size stream
    # change cannot switch the actual decoder or inflate ZipInfo allocation.
    frozen = _FrozenZipMetadata(source, freeze_start, frozen_metadata, size)
    try:
        with zipfile.ZipFile(frozen) as archive:
            if len(archive.infolist()) != count:
                raise ValueError('Source ZIP parsed count differs from its frozen raw central span')
            position = 0
            expanded = budget.expanded
            for item in archive.infolist():
                budget.check()
                record, position = _zip_record(central, position)
                if (item.orig_filename != record['name'] or item.flag_bits != record['flags']
                        or item.compress_type != record['method'] or item.CRC != record['crc']
                        or item.compress_size != record['compressed'] or item.file_size != record['expanded']
                        or item.external_attr != record['external'] or item.header_offset != record['local']):
                    raise ValueError('Source ZIP decoding metadata differs from its bounded raw record')
                _integer(item.file_size, 'actual ZIP member bytes', budget.limits['maximum_member_bytes'], 0)
                expanded += item.file_size
                if expanded > budget.limits['maximum_expanded_bytes']:
                    raise ValueError('Actual source ZIP decoding exceeds explicit expanded byte budget')
                if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2):
                    raise ValueError('Actual source ZIP decoder lacks bounded admission')
                mode = item.external_attr >> 16
                kind = 'directory' if item.is_dir() else 'symlink' if stat.S_ISLNK(mode) else 'file'
                if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK):
                    kind = 'special'
                with archive.open(item) as stream:
                    link = None
                    if kind == 'symlink':
                        if item.file_size > 4096:
                            raise ValueError('Source ZIP link target exceeds bound')
                        try:
                            link = stream.read(4097).decode('utf-8')
                        except UnicodeError as error:
                            raise ValueError('Invalid source ZIP link target') from error
                    yield item.filename, kind, mode, item.file_size, link, stream
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, NotImplementedError, RuntimeError) as error:
        raise ValueError('Invalid bounded ordinary source ZIP stream') from error


def _archive_entries(source, archive_format, budget):
    if archive_format == 'zip':
        yield from _zip_entries(source, budget)
        return
    headers = 0
    class BoundedTarInfo(tarfile.TarInfo):
        def _proc_member(self, archive):
            nonlocal headers
            budget.check()
            headers += 1
            if headers > budget.limits['maximum_members']:
                raise ValueError('Source tar header count exceeds explicit member budget')
            _integer(self.size, 'raw tar member bytes', budget.limits['maximum_member_bytes'], 0)
            if self.type in (tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.SOLARIS_XHDTYPE,
                              tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK):
                if self.size > min(MAX_DOCUMENT, budget.limits['maximum_member_bytes']):
                    raise ValueError('Source tar extended header exceeds finite metadata bound')
            if self.type == tarfile.GNUTYPE_SPARSE:
                raise ValueError('Sparse source archive members are unsupported')
            result = super()._proc_member(archive)
            if result.sparse is not None:
                raise ValueError('Sparse source archive members are unsupported')
            return result
    try:
        expanded = _ExpandedTarStream(source, archive_format, budget)
        with tarfile.open(fileobj=expanded, mode='r|', tarinfo=BoundedTarInfo) as archive:
            for item in archive:
                kind = ('directory' if item.isdir() else 'file' if item.isfile()
                        else 'symlink' if item.issym() else 'hardlink' if item.islnk() else 'special')
                stream = archive.extractfile(item) if kind == 'file' else None
                try:
                    yield item.name, kind, item.mode, item.size, item.linkname if kind in ('symlink', 'hardlink') else None, stream
                finally:
                    if stream is not None:
                        stream.close()
    except (tarfile.TarError, lzma.LZMAError, zlib.error, EOFError, RecursionError) as error:
        raise ValueError('Invalid bounded ordinary source tar stream') from error


def _stream_pin(source, expected, budget):
    source.seek(0)
    actual = hashlib.sha256()
    count = 0
    while True:
        budget.check()
        block = source.read(min(1024 * 1024, expected['bytes'] - count + 1))
        if not block:
            break
        actual.update(block)
        count += len(block)
    if count != expected['bytes'] or actual.hexdigest() != expected['sha256']:
        raise ValueError('Source archive stream differs from independent pin/bytes')
    source.seek(0)


def _read_member(stream, size, keep, budget):
    if stream is None:
        raise ValueError('Ordinary source member has no binary stream')
    chunks, count, actual = [], 0, hashlib.sha256()
    while True:
        budget.check()
        block = stream.read(min(1024 * 1024, size - count + 1))
        if type(block) is not bytes:
            raise ValueError('Source member stream must return bytes')
        if not block:
            break
        count += len(block)
        if count > size:
            raise ValueError('Expanded source member exceeds declared bytes')
        actual.update(block)
        if keep:
            chunks.append(block)
    if count != size:
        raise ValueError('Truncated source archive member')
    return actual.hexdigest(), b''.join(chunks) if keep else None


def replay_projection(projection, archive_streams, patch_bytes, overlay_bytes, overlays, limits):
    """Derive candidate inventory from streams; this function admits no original proof.

    ``overlays`` maps final paths to sha256/bytes/mode facts. Only patch preimages
    are buffered, with a256MiB aggregate bound; other members are hashed in place.
    Raw member order is deliberately not original-manifest proof.
    """
    projection = validate_projection_metadata(projection)
    budget = _Budget(limits)
    archives, selected = projection['archives'], projection['projection']['files']
    if type(archive_streams) is not dict or set(archive_streams) != set(archives):
        raise ValueError('Source replay stream keys must exactly match original archives')
    if type(patch_bytes) is not list or len(patch_bytes) != len(projection['patches']):
        raise ValueError('Source replay requires exact ordered patch bodies')
    if type(overlays) is not dict or type(overlay_bytes) is not dict or set(overlays) != set(overlay_bytes):
        raise ValueError('Source replay requires every final overlay exactly once')
    if len(overlays) > MAX_MEMBERS:
        raise ValueError('Final overlay count exceeds finite source bound')
    archive_streams = dict(archive_streams)
    patch_bytes = tuple(patch_bytes)
    overlay_bytes = dict(overlay_bytes)
    overlays = copy.deepcopy(overlays)
    wanted = {(item['tree'], name) for item in projection['patches']
              for name, image in item['preimages'].items() if image is not None}
    selected_members = {(item['archive'], item['member']): name for name, item in selected.items()}
    needed = set()
    for destination, item in selected.items():
        supplier = destination.split('/')[1]
        if (supplier, item['member']) in wanted:
            normalization = projection['projection']['normalizations'][item['archive']]
            needed.add((item['archive'], normalization.get(item['member'], item['member'])))
    bodies, facts, raw_links, buffered = {}, {}, {}, 0
    for key, archive in sorted(archives.items()):
        budget.check()
        if archive['bytes'] > budget.limits['maximum_archive_bytes']:
            raise ValueError('Source archive exceeds explicit archive byte budget')
        source = _BoundedStream(archive_streams[key], archive['bytes'], budget)
        _stream_pin(source, archive, budget)
        exclusions = projection['projection']['exclusions'][key]
        normalizations = projection['projection']['normalizations'][key]
        member_registry, seen, links, literals, used = PathInventory(), {}, {}, {}, set()
        for raw_name, kind, mode, size, link, stream in _archive_entries(source, archive['format'], budget):
            budget.member(size)
            if (type(mode) is not int or not 0 <= mode <= 0o177777 or mode & 0o7000
                    or kind not in ('file', 'directory', 'symlink', 'hardlink')):
                raise ValueError('Privileged or special source archive member')
            name = native_inputs._member_name(raw_name, archive['strip_prefix'])
            if name is None:
                if kind != 'directory':
                    raise ValueError('Source archive strip-prefix root must be a directory')
                continue
            name = _path(name)
            member_registry.add(name, kind == 'directory')
            if kind == 'directory':
                continue
            excluded = [root for root in exclusions if name == root or name.startswith(root + '/')]
            used.update(excluded)
            destination = selected_members.get((key, name))
            if excluded and destination is not None:
                raise ValueError('Source member is both projected and excluded')
            if not excluded and destination is None:
                raise ValueError('Undeclared source archive member: ' + name)
            normalized_mode = 0o755 if mode & 0o111 else 0o644
            if kind in ('symlink', 'hardlink'):
                if (name not in normalizations or normalizations[name] not in
                        native_inputs._resolved_link(name, link, kind, archive['strip_prefix'])):
                    raise ValueError('Source link lacks exact direct ordinary-file normalization')
                links[name], literals[name] = normalizations[name], link
                seen[name] = {'link': normalizations[name]}
                continue
            keep = (key, name) in needed
            if keep:
                buffered += size
                if buffered > MAX_MEMBER:
                    raise ValueError('Source patch preimages exceed aggregate buffer bound')
            pin, body = _read_member(stream, size, keep, budget)
            seen[name] = {'sha256': pin, 'bytes': size, 'mode': normalized_mode}
            if keep:
                bodies[(key, name)] = body
        _stream_pin(source, archive, budget)
        if used != set(exclusions) or set(normalizations) != set(links):
            raise ValueError('Unused or missing source exclusions/direct link normalizations')
        for name, target in links.items():
            if target not in seen or 'link' in seen[target]:
                raise ValueError('Source link target must be a same-archive direct ordinary file')
            seen[name] = dict(seen[target])
        for destination, item in selected.items():
            if item['archive'] != key:
                continue
            expected = {field: item[field] for field in ('sha256', 'bytes', 'mode')}
            if seen.get(item['member']) != expected:
                raise ValueError('Source projection hash/bytes/mode differs from archive: ' + destination)
            facts[destination] = expected
        raw_links[key] = literals
    if set(facts) != set(selected):
        raise ValueError('Source projection omitted original archive members')
    directories = set(projection['projection']['directories'])
    patched_bodies = {}
    for item, raw in zip(projection['patches'], patch_bytes):
        budget.check()
        if (type(raw) is not bytes or len(raw) > budget.limits['maximum_patch_bytes']
                or digest(raw) != item['sha256']):
            raise ValueError('Ordered source patch differs from exact pin/byte budget')
        originals, buffer_size = {}, 0
        prefix = 'source/' + item['tree'] + '/'
        for name, image in item['preimages'].items():
            destination = prefix + name
            actual = facts.get(destination)
            if image is None:
                if actual is not None:
                    raise ValueError('Source patch addition already exists in clean baseline')
                continue
            if actual is None or actual['sha256'] != image:
                raise ValueError('Source patch requires exact clean original preimage')
            if destination in patched_bodies:
                body = patched_bodies[destination]
            else:
                source_item = selected[destination]
                target = projection['projection']['normalizations'][source_item['archive']].get(source_item['member'], source_item['member'])
                body = bodies[(source_item['archive'], target)]
            originals[name] = body
            buffer_size += len(body)
        if buffer_size > MAX_MEMBER:
            raise ValueError('Source patch image buffer exceeds bound')
        patched = native_inputs.apply_unified_patch(originals, raw, item['preimages'], item['postimages'])
        if sum(len(body) for body in patched.values()) > MAX_MEMBER:
            raise ValueError('Source patch postimages exceed aggregate buffer bound')
        for name, image in item['postimages'].items():
            destination = prefix + name
            mode = facts.get(destination, {}).get('mode', 0o644)
            facts.pop(destination, None)
            patched_bodies.pop(destination, None)
            if image is not None:
                body = patched[name]
                _integer(len(body), 'patched member bytes', budget.limits['maximum_member_bytes'], 0)
                facts[destination] = {'sha256': digest(body), 'bytes': len(body), 'mode': mode}
                patched_bodies[destination] = body
                directories.update(_parents((destination,)))
    for name, item in sorted(overlays.items()):
        budget.check()
        _path(name)
        if not name.startswith('source/') or type(item) is not dict:
            raise ValueError('Final overlays must be ordinary source destinations')
        for required in ('sha256', 'bytes', 'mode'):
            if required not in item:
                raise ValueError('Final overlay lacks exact source facts')
        contract.pin(item['sha256'], 'final overlay')
        if type(item['mode']) is not int or item['mode'] not in (0o644, 0o755):
            raise ValueError('Final overlay mode requires0644/0755')
        _integer(item['bytes'], 'final overlay bytes', budget.limits['maximum_member_bytes'], 0)
        body = overlay_bytes[name]
        if type(body) is not bytes or len(body) != item['bytes'] or digest(body) != item['sha256']:
            raise ValueError('Final overlay differs from independently pinned source bytes')
        facts[name] = {key: item[key] for key in ('sha256', 'bytes', 'mode')}
        directories.update(_parents((name,)))
    if (sum(item['bytes'] for item in facts.values()) > budget.limits['maximum_expanded_bytes']
            or len(facts) + len(directories) > budget.limits['maximum_members']):
        raise ValueError('Complete derived inventory exceeds explicit final byte/member budget')
    result = {'files': {name: item['sha256'] for name, item in sorted(facts.items())},
              'directories': sorted(directories),
              'modes': {**{name: item['mode'] for name, item in sorted(facts.items())},
                        **{name: 0o755 for name in sorted(directories)}}}
    manifest.inventory_contract(result, '__source_replay_excluded_manifest__.json')
    budget.check()
    return {**result, 'original_proof_admitted': False,
            'supplier_patch': [item['sha256'] for item in projection['patches']],
            'overlays': len(overlays), 'raw_links': raw_links,
            'raw_member_manifest_admitted': False,
            'build': False, 'production_eligible': False, 'engine_execution': False,
            'kernel_rebuild': False}


def _documents(documents):
    contract.fields(documents, ('source_projection', 'limits', 'source_map', 'provenance',
                               'graph', 'bindings'), 'source replay captured documents')
    projection = validate_projection_metadata(documents['source_projection'])
    limits = validate_limits(documents['limits'])
    bindings = validate_bindings(documents['bindings'])
    _binding_projection(projection, bindings)
    catalogue = catalogue_metadata(*(documents[role] for role in ('source_map', 'provenance', 'graph')))
    native_inputs._forward_patch_contract(dict(projection, _files=projection['projection']['files']),
                                          catalogue['source_map']['inputs'])
    return projection, limits, bindings, catalogue


def _binding_projection(projection, bindings):
    if set(bindings['archives']) != set(projection['archives']):
        raise ValueError('Archive bindings differ from exact original projection keys')
    for key, item in projection['archives'].items():
        if any(bindings['archives'][key][field] != item[field] for field in ('sha256', 'bytes')):
            raise ValueError('Relocated original archive pin/bytes differs')
    originals = {item['role']: item for item in projection['provenance']}
    if set(bindings['provenance']) != set(originals):
        raise ValueError('Original provenance binding roles differ')
    for role, original in originals.items():
        if any(bindings['provenance'][role][field] != original[field] for field in ('sha256', 'bytes')):
            raise ValueError('Relocated original provenance pin/bytes differs')
    for key in ('patches', 'notices'):
        if len(bindings[key]) != len(projection[key]) or any(
                bound['sha256'] != original['sha256'] for bound, original in zip(bindings[key], projection[key])):
            raise ValueError('Relocated ordered original ' + key + ' differ')


def derive_inventory(documents, archive_streams, patch_bytes, overlay_bytes):
    """Current catalogue/forward-policy candidate derivation; never source admission."""
    projection, limits, bindings, catalogue = _documents(documents)
    return replay_projection(projection, archive_streams, patch_bytes, overlay_bytes,
                             catalogue['overlays'], limits)


def _checked_inventory(checked, overlays, *, deadline=None):
    """Final expected inventory from a checked view; the view itself is not proof."""
    projection = checked.as_dict()
    files, modes = {}, {}
    for name, item in projection['_files'].items():
        _check_deadline(deadline)
        files[name], modes[name] = item['sha256'], item['mode']
    directories = set(projection['projection']['directories'])
    for patch in projection['patches']:
        prefix = 'source/' + patch['tree'] + '/'
        for name, image in patch['postimages'].items():
            _check_deadline(deadline)
            destination = prefix + name
            if image is None:
                files.pop(destination, None)
                modes.pop(destination, None)
            else:
                files[destination] = image
                modes.setdefault(destination, 0o644)
                directories.update(_parents((destination,)))
    for name, item in overlays.items():
        _check_deadline(deadline)
        files[name], modes[name] = item['sha256'], item['mode']
        directories.update(_parents((name,)))
    result = {'files': dict(sorted(files.items())), 'directories': sorted(directories),
        'modes': {**dict(sorted(modes.items())), **{name: 0o755 for name in sorted(directories)}}}
    manifest.inventory_contract(result, '__source_replay_excluded_manifest__.json')
    _check_deadline(deadline)
    return result


def replay_records(documents, archive_streams, patch_bytes, overlay_bytes, *,
                   captured_records=None, original_proof_records=None, deadline=None):
    """Use the released original proof seam; no candidate can mint authority."""
    return _replay_checked_records(documents, archive_streams, patch_bytes, overlay_bytes,
        captured_records=captured_records, original_proof_records=original_proof_records,
        deadline=deadline)[1]


def _replay_checked_records(documents, archive_streams, patch_bytes, overlay_bytes, *,
                            captured_records=None, original_proof_records=None, deadline=None):
    projection, limits, bindings, catalogue = _documents(documents)
    _check_deadline(deadline)
    require_original_proof_seam()
    if captured_records is None or original_proof_records is None:
        raise MissingInputs([{'role': 'windows-source-captured-records', 'path': 'replay_records',
            'reason': 'actual bounded original records and streams are required'}])
    if ([item['raw'] for item in captured_records['patches']] != patch_bytes or
            type(overlay_bytes) is not dict or set(overlay_bytes) != set(catalogue['overlays'])):
        raise ValueError('Replay captured patch/overlay records differ')
    for name, item in catalogue['overlays'].items():
        _check_deadline(deadline)
        body = overlay_bytes[name]
        if type(body) is not bytes or len(body) != item['bytes'] or digest(body) != item['sha256']:
            raise ValueError('Replay overlay differs from the pinned common source')
    checked, facts = check_records(projection, captured_records, archive_streams,
                                  original_proof_records, limits, deadline=deadline)
    native_inputs._forward_patch_contract(checked.as_dict(), catalogue['source_map']['inputs'])
    return checked, {**_checked_inventory(checked, catalogue['overlays'], deadline=deadline),
        'scope': SCOPE, 'original_proof_admitted': True,
        'source_provenance': copy.deepcopy(facts), 'build': False,
        'production_eligible': False, 'engine_execution': False, 'kernel_rebuild': False}


def _pinned_metadata(path, pin, role):
    contract.pin(pin, role)
    try:
        raw = handoff._read(path)
    except FileNotFoundError as error:
        raise MissingInputs([{'role': role, 'path': os.fspath(path),
                              'reason': 'explicit independently pinned source metadata absent'}]) from error
    if digest(raw) != pin:
        raise ValueError('Source replay metadata differs from independent pin: ' + role)
    return raw


def _selected_source_metadata(inputs, name, pin, role, path):
    try:
        return inputs.read(name, {'sha256': pin, 'mode': 0o644})
    except FileNotFoundError as error:
        raise MissingInputs([{'role': role, 'path': os.fspath(path),
            'reason': 'explicit independently pinned source metadata absent'}]) from error


def _selection_metadata(value):
    contract.fields(value, ('schema_version', 'kind', 'target', 'source_catalogue', 'retained',
        'assembled', 'source_projection', 'typed_toolchain_identity', 'bindings', 'limits'),
        'Windows source replay selection')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != SELECTION_KIND or value['target'] != contract.TARGET
            or value['source_catalogue'] != contract.catalogue_for_reference(value['source_catalogue'])):
        raise ValueError('Source replay target/current catalogue differs')
    retained = contract.fields(value['retained'], ('root', 'recipe_sha256', 'sources_sha256'), 'retained source selection')
    root = _posix(retained['root'])
    for key in ('recipe_sha256', 'sources_sha256'):
        contract.pin(retained[key], key)
    assembled = contract.fields(value['assembled'], ('root', 'inventory'), 'assembled source selection')
    other = _posix(assembled['root'])
    if root == other or root + '/' == other[:len(root) + 1] or other + '/' == root[:len(other) + 1]:
        raise ValueError('Retained and assembled source roots must be disjoint')
    _ref(assembled['inventory'], relative=False)
    _ref(value['source_projection'])
    _ref(value['typed_toolchain_identity'])
    if value['typed_toolchain_identity']['path'] != 'native-inputs/toolchain-identity.json':
        raise ValueError('Typed Windows identity must name its exact retained config input')
    validate_bindings(value['bindings'])
    validate_limits(value['limits'])
    return copy.deepcopy(value)


def _join_retained_metadata(value, recipe_raw, sources_raw, projection_raw, inventory_raw):
    recipe, sources = handoff._document(recipe_raw), handoff._document(sources_raw)
    manifest.recipe_contract(recipe)
    manifest.source_contract(sources, recipe, digest(recipe_raw))
    if recipe['target'] != contract.TARGET:
        raise ValueError('Active source replay recipe must target exact Windows x64')
    if value['source_catalogue'] != contract.catalogue_for_recipe_inputs(recipe['inputs']):
        raise ValueError('Source replay catalogue differs from selected retained recipe version')
    projection = validate_projection_metadata(handoff._document(projection_raw))
    bindings = validate_bindings(value['bindings'])
    _binding_projection(projection, bindings)
    inventory = handoff._inventory_contract(handoff._document(inventory_raw))
    def joined(ref, role):
        item = recipe['inputs'].get(ref['path'])
        if item != {'sha256': ref['sha256'], 'mode': 0o644, 'role': role}:
            raise ValueError('Relocated source binding differs from active R/S role/mode/pin')
    joined(value['source_projection'], 'config')
    joined(value['typed_toolchain_identity'], 'config')
    if recipe['toolchain']['identity_sha256'] != value['typed_toolchain_identity']['sha256']:
        raise ValueError('Original typed Windows identity differs from active recipe declaration')
    for table, role in (('archives', 'source'), ('provenance', 'data'), ('original_proof', 'data')):
        for ref in bindings[table].values():
            joined(ref, role)
    for table, role in (('patches', 'patch'), ('notices', 'license')):
        for ref in bindings[table]:
            joined(ref, role)
    for supplier, original in projection['suppliers'].items():
        wanted = dict(original, archive=bindings['archives'][original['archive']]['path'])
        if recipe['suppliers'][supplier] != wanted:
            raise ValueError('Original supplier archive/commit differs from active Windows recipe')
    patches = [{key: item[key] for key in ('tree', 'preimages', 'postimages')}
               | {'path': ref['path']} for item, ref in zip(projection['patches'], bindings['patches'])]
    if recipe['patches'] != patches:
        raise ValueError('Active recipe differs from exact ordered source patches')
    return recipe, sources, projection, inventory


def check_selection(path, selection_sha256):
    """Check a POSIX preparation selection; native capsules use check-handoff."""
    started = time.monotonic()
    if os.name != 'posix':
        path = handoff._absolute(os.fspath(path))
        raise MissingInputs([{'role': 'windows-source-capture-adapter', 'path': str(path),
            'reason': 'native checking uses capsule-relative check-handoff; native archive capture is not implemented'}])
    path = Path(_posix(os.fspath(path)))
    lifetime = started + 86400
    owner = _SourceInspectionOwner(path.parent, selection_sha256,
        {'path': str(path), 'sha256': selection_sha256}, started, lifetime, False)
    try:
        def inputs_for(root):
            actual = _PosixSourceInputs(root, deadline=lifetime)
            owner.resources.append(actual)
            inputs = _SourceInputs(owner, actual)
            owner.borrowed.append(inputs)
            return inputs
        selection_inputs = inputs_for(path.parent)
        selection_raw = _selected_source_metadata(selection_inputs, path.name, selection_sha256,
            'source-replay-selection', path)
        value = _selection_metadata(handoff._document(selection_raw))
        owner.set_source_limits(value['limits'])
        retained_inputs = inputs_for(Path(value['retained']['root']))
        assembled_inputs = inputs_for(Path(value['assembled']['root']))
        recipe_raw = _selected_source_metadata(retained_inputs, 'recipe.json',
            value['retained']['recipe_sha256'], 'source-replay-recipe', Path(value['retained']['root']) / 'recipe.json')
        sources_raw = _selected_source_metadata(retained_inputs, 'sources.json',
            value['retained']['sources_sha256'], 'source-replay-sources', Path(value['retained']['root']) / 'sources.json')
        projection_ref, inventory_ref = value['source_projection'], value['assembled']['inventory']
        projection_raw = _selected_source_metadata(retained_inputs, projection_ref['path'],
            projection_ref['sha256'], 'source-replay-projection', Path(value['retained']['root']) / projection_ref['path'])
        inventory_path = Path(inventory_ref['path'])
        inventory_inputs = inputs_for(inventory_path.parent)
        inventory_raw = _selected_source_metadata(inventory_inputs, inventory_path.name,
            inventory_ref['sha256'], 'source-replay-assembled-inventory', inventory_path)
        joined = _join_retained_metadata(value, recipe_raw, sources_raw, projection_raw, inventory_raw)
        require_original_proof_seam()
        return _run_selection_capture(value, owner, retained_inputs, assembled_inputs, *joined)
    finally:
        owner.close()


def _check_captured_selection(value, retained, assembled, recipe, sources, projection, inventory, *, deadline=None):
    """Actual selected roots use the same hash-once capture/tree discipline."""
    if os.name != 'posix':
        raise MissingInputs([{'role': 'windows-source-capture-adapter', 'path': str(retained),
            'reason': 'qualified native bounded archive capture is not implemented'}])
    limits = validate_limits(value['limits'])
    started = time.monotonic() if deadline is None else deadline - limits['seconds']
    lifetime = started + limits['seconds'] if deadline is None else deadline
    # This private accounting owner issues no handoff/SourceInspection authority.
    owner = _SourceInspectionOwner(retained, value['retained']['recipe_sha256'],
        value['assembled']['inventory'], started, lifetime, True)
    try:
        owner.set_source_limits(limits)
        retained_actual = _PosixSourceInputs(retained, deadline=lifetime)
        owner.resources.append(retained_actual)
        assembled_actual = _PosixSourceInputs(assembled, deadline=lifetime)
        owner.resources.append(assembled_actual)
        retained_inputs, assembled_inputs = _SourceInputs(owner, retained_actual), _SourceInputs(owner, assembled_actual)
        owner.borrowed.extend((retained_inputs, assembled_inputs))
        return _run_selection_capture(value, owner, retained_inputs, assembled_inputs,
            recipe, sources, projection, inventory)
    finally:
        owner.close()


def _run_selection_capture(value, owner, retained_inputs, assembled_inputs, recipe, sources, projection, inventory):
    records, streams, original_proof = _capture_source_records(owner, retained_inputs,
        projection, value['bindings'], prefix='')
    def body_by_pin(pin):
        names = sorted(name for name, item in recipe['inputs'].items() if item['sha256'] == pin)
        if not names:
            raise ValueError('Retained recipe omits current catalogue body')
        name = names[0]
        return retained_inputs.read(name, {'sha256': pin, 'mode': recipe['inputs'][name]['mode']})
    selected_catalogue = contract.catalogue_for_reference(value['source_catalogue'])
    catalogue_raw = {role: body_by_pin(selected_catalogue[role]['sha256'])
                     for role in ('source_map', 'provenance', 'graph')}
    catalogue = catalogue_metadata(*(catalogue_raw[role] for role in ('source_map', 'provenance', 'graph')))
    overlays = {name: retained_inputs.read(name,
        {key: item[key] for key in ('sha256', 'bytes', 'mode')}, owner.limits['maximum_member_bytes'])
        for name, item in catalogue['overlays'].items()}
    documents = {'source_projection': projection, 'limits': owner.source_limits(),
        'bindings': value['bindings'], **catalogue_raw}
    checked, result = _replay_checked_records(documents, streams,
        [item['raw'] for item in records['patches']], overlays, captured_records=records,
        original_proof_records=original_proof, deadline=owner.work_deadline)
    owner.checked = checked
    expected = {key: result[key] for key in ('files', 'directories', 'modes')}
    if inventory != expected:
        raise ValueError('Selected assembled inventory differs from checked supplier/patch/overlay image')
    retained_expected = handoff._retained_inventory(sources, value['retained']['sources_sha256'])
    def capture_inventory(inputs, expected):
        files = {name: {'sha256': pin, 'mode': expected['modes'][name]}
                 for name, pin in expected['files'].items()}
        for name, item in inputs.expectations.items():
            if name not in files or any(files[name][key] != item[key] for key in ('sha256', 'mode')):
                raise ValueError('Captured source leaf differs from its complete selected inventory')
            if 'bytes' in item:
                files[name]['bytes'] = item['bytes']
        inputs.capture_tree(files, expected['directories'])
    capture_inventory(retained_inputs, retained_expected)
    capture_inventory(assembled_inputs, expected)
    owner.check()
    return {**result, 'target': copy.deepcopy(contract.TARGET),
        'source_catalogue': copy.deepcopy(selected_catalogue),
        'retained_recipe_sha256': value['retained']['recipe_sha256'],
        'retained_sources_sha256': value['retained']['sources_sha256']}


def _handoff_metadata(raw):
    value = handoff._document(raw)
    contract.fields(value, ('schema_version', 'kind', 'scope', 'target', 'source_catalogue', 'paths',
        'files', 'directories', 'modes', *handoff.FALSE_FACTS), 'source replay handoff')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != handoff.KIND or value['scope'] != handoff.SCOPE
            or value['target'] != contract.TARGET or value['source_catalogue'] != contract.catalogue_for_reference(value['source_catalogue'])
            or value['paths'] != handoff.PATHS or any(value[name] is not False for name in handoff.FALSE_FACTS)):
        raise ValueError('Source replay handoff exact metadata contract differs')
    handoff._inventory_contract({key: value[key] for key in ('files', 'directories', 'modes')})
    return value


def _subtree_inventory(value, prefix):
    prefix += '/'
    return {'files': {name[len(prefix):]: pin for name, pin in value['files'].items()
                     if name.startswith(prefix)},
        'directories': sorted(name[len(prefix):] for name in value['directories'] if name.startswith(prefix)),
        'modes': {name[len(prefix):]: mode for name, mode in value['modes'].items()
                  if name.startswith(prefix)}}


def _capture_source_records(owner, inputs, projection, bindings, *, prefix='retained/'):
    records = {'archives': {}, 'provenance': {}, 'patches': [], 'notices': []}
    streams, original_proof = {}, {}
    def capture(original, bound):
        raw = inputs.read(prefix + bound['path'],
            {key: bound[key] for key in ('sha256', 'bytes', 'mode')})
        return {'path': original, **{key: bound[key] for key in ('sha256', 'bytes', 'mode')}, 'raw': raw}
    for key, item in projection['archives'].items():
        owner.guard()
        bound = bindings['archives'][key]
        streams[key] = inputs.archive(prefix + bound['path'],
            {name: bound[name] for name in ('sha256', 'bytes', 'mode')})
        records['archives'][key] = {'path': item['path'],
            **{name: bound[name] for name in ('sha256', 'bytes', 'mode')}}
    for item in projection['provenance']:
        records['provenance'][item['role']] = capture(item['path'], bindings['provenance'][item['role']])
    for key in ('patches', 'notices'):
        if key == 'patches' and sum(item['bytes'] for item in bindings[key]) > owner.limits['maximum_patch_bytes']:
            raise ValueError('Captured source patches exceed the selected patch byte bound')
        for original, bound in zip(projection[key], bindings[key]):
            records[key].append(capture(original['path'], bound))
    body = handoff._document(records['provenance']['engine-body-verification']['raw'])
    if type(body) is not dict or body.get('kind') != 'foundation-native-engine-retained-body-evidence-v1':
        raise ValueError('Source capture requires original retained-body references')
    references = contract.fields(body.get('original_proof'), ORIGINAL_PROOF_ROLES,
                                  'unchecked original proof reference discovery')
    for role, item in references.items():
        contract.fields(item, ('path', 'sha256', 'bytes'), 'unchecked original proof reference')
        if type(item['path']) is not str or not item['path']:
            raise ValueError('Original proof reference spelling is absent')
        contract.pin(item['sha256'], 'original proof reference')
        _integer(item['bytes'], 'original proof reference bytes', MAX_DOCUMENT)
        bound = bindings['original_proof'][role]
        if any(bound[key] != item[key] for key in ('sha256', 'bytes')):
            raise ValueError('Relocated original proof differs from independent original reference')
        original_proof[role] = capture(item['path'], bound)
    owner.raw_records.extend((projection, records, original_proof))
    return records, streams, original_proof


def _inspect_source_inputs(owner, capsule, replay_inputs, replay_name, handoff_sha256, replay_reference):
    """One initial source/proof join; only physical checks follow its admission."""
    contract.pin(handoff_sha256, 'source replay handoff')
    contract.pin(replay_reference['sha256'], 'external source replay reference')
    root = (PureWindowsPath if os.name == 'nt' else PurePosixPath)(owner.subject[0])
    raw = _selected_source_metadata(capsule, 'handoff.json', handoff_sha256,
        'source-replay-handoff', str(root / 'handoff.json'))
    value = _handoff_metadata(raw)
    replay_raw = _selected_source_metadata(replay_inputs, replay_name, replay_reference['sha256'],
        'source-replay-reference', replay_reference['path'])
    replay = _selection_metadata(handoff._document(replay_raw))
    if value['source_catalogue'] != replay['source_catalogue']:
        raise ValueError('Handoff and replay selected source catalogues differ')
    owner.set_source_limits(replay['limits'])
    for role, name, pin in (('recipe', 'retained/recipe.json', replay['retained']['recipe_sha256']),
            ('sources', 'retained/sources.json', replay['retained']['sources_sha256']),
            ('assembled inventory', handoff.PATHS['assembled_inventory'], replay['assembled']['inventory']['sha256']),
            ('original projection', 'retained/' + replay['source_projection']['path'], replay['source_projection']['sha256'])):
        if value['files'].get(name) != pin or value['modes'].get(name) != 0o644:
            raise ValueError('Handoff source replay subject differs: ' + role)
    def metadata(name, pin, role):
        if value['files'].get(name) != pin or value['modes'].get(name) != 0o644:
            raise ValueError('Selected source metadata differs from the independent handoff inventory')
        return _selected_source_metadata(capsule, name, pin, role, str(root / name))
    recipe, sources, projection, inventory = _join_retained_metadata(replay,
        metadata('retained/recipe.json', replay['retained']['recipe_sha256'], 'source-replay-recipe'),
        metadata('retained/sources.json', replay['retained']['sources_sha256'], 'source-replay-sources'),
        metadata('retained/' + replay['source_projection']['path'], replay['source_projection']['sha256'], 'source-replay-projection'),
        metadata(handoff.PATHS['assembled_inventory'], replay['assembled']['inventory']['sha256'], 'source-replay-assembled-inventory'))
    require_original_proof_seam()
    records, streams, original_proof = _capture_source_records(owner, capsule, projection, replay['bindings'])
    def body_by_pin(pin):
        names = sorted(name for name, item in recipe['inputs'].items() if item['sha256'] == pin)
        if not names:
            raise ValueError('Retained recipe omits current catalogue body')
        name = names[0]
        item = recipe['inputs'][name]
        return capsule.read('retained/' + name, {'sha256': pin, 'mode': item['mode']})
    selected_catalogue = contract.catalogue_for_reference(replay['source_catalogue'])
    catalogue_raw = {role: body_by_pin(selected_catalogue[role]['sha256'])
                     for role in ('source_map', 'provenance', 'graph')}
    catalogue = catalogue_metadata(*(catalogue_raw[role] for role in ('source_map', 'provenance', 'graph')))
    overlays = {name: capsule.read('retained/' + name,
        {key: item[key] for key in ('sha256', 'bytes', 'mode')}, owner.limits['maximum_member_bytes'])
        for name, item in catalogue['overlays'].items()}
    documents = {'source_projection': projection, 'limits': owner.source_limits(),
                 'bindings': replay['bindings'], **catalogue_raw}
    checked, result = _replay_checked_records(documents, streams,
        [item['raw'] for item in records['patches']], overlays,
        captured_records=records, original_proof_records=original_proof, deadline=owner.work_deadline)
    expected = {key: result[key] for key in ('files', 'directories', 'modes')}
    if inventory != expected:
        raise ValueError('Selected assembled inventory differs from checked supplier/patch/overlay image')
    retained_expected = handoff._retained_inventory(sources, replay['retained']['sources_sha256'])
    if _subtree_inventory(value, 'retained') != retained_expected or _subtree_inventory(value, 'assembled') != expected:
        raise ValueError('Complete handoff retained/assembled inventory differs from checked source facts')
    files = {name: {'sha256': pin, 'mode': value['modes'][name]} for name, pin in value['files'].items()}
    if 'handoff.json' in files:
        raise ValueError('Handoff inventory must exclude its own independently selected manifest')
    files['handoff.json'] = {'sha256': handoff_sha256, 'mode': 0o644}
    # Only independent archive/binding declarations add bytes. Observed EOF never does.
    for name, expectation in capsule.expectations.items():
        if name not in files or any(files[name][key] != expectation[key] for key in ('sha256', 'mode')):
            raise ValueError('Captured source leaf differs from the complete independent handoff inventory')
        if 'bytes' in expectation:
            files[name]['bytes'] = expectation['bytes']
    capsule.capture_tree(files, value['directories'])
    facts = {**result, 'target': copy.deepcopy(contract.TARGET),
        'source_catalogue': copy.deepcopy(selected_catalogue),
        'retained_recipe_sha256': replay['retained']['recipe_sha256'],
        'retained_sources_sha256': replay['retained']['sources_sha256'],
        'handoff_sha256': handoff_sha256, 'source_replay_sha256': replay_reference['sha256']}
    return owner.hold(checked, facts)


def inspect_for_handoff(root, handoff_sha256, replay_reference, *, input_qualification=None, deadline=None):
    """Capture one actual source inspection with an unrenewable enclosing lifetime."""
    started = time.monotonic()
    lifetime, explicit = _source_lifetime(started, deadline)
    owner = _SourceInspectionOwner(root, handoff_sha256, replay_reference, started, lifetime, explicit)
    try:
        if os.name == 'nt':
            if input_qualification is None:
                raise MissingInputs([{'role': 'windows-native-input-qualification', 'path': os.fspath(root),
                    'reason': 'an actual issued native input qualification is required before capsule access'}])
            api = _native_input_reader()
            # A's six capture ceilings require strict integer seconds. Its
            # separate original lifetime deadline still bounds both owners;
            # rounding the data ceiling never renews source parsing or checks.
            native_limits = {**owner.limits, 'seconds': min(86400, math.ceil(lifetime - started))}
            actual = api.AnchoredInputs.open_existing(root, qualification=input_qualification,
                limits=copy.deepcopy(native_limits), deadline=lifetime)
            owner.resources.append(actual)
            owner.check()
            _native_tree_reader(api)
            require_original_proof_seam()
            contract.fields(replay_reference, ('path', 'sha256'), 'external source replay reference')
            replay_path = PureWindowsPath(replay_reference['path'])
            if not replay_path.is_absolute() or replay_path.name in ('', '.', '..') or '..' in replay_path.parts:
                raise ValueError('Native external replay requires an absolute lexical Windows leaf path')
            external = api.AnchoredInputs.open_existing(str(replay_path.parent), qualification=input_qualification,
                limits=copy.deepcopy(native_limits), deadline=lifetime)
            replay_name = replay_path.name
        elif os.name == 'posix':
            if input_qualification is not None:
                raise ValueError('Native input qualification is not accepted by POSIX source replay')
            contract.fields(replay_reference, ('path', 'sha256'), 'external source replay reference')
            replay_path = handoff._absolute(replay_reference['path'])
            actual = _PosixSourceInputs(root, deadline=lifetime)
            owner.resources.append(actual)
            external = _PosixSourceInputs(replay_path.parent, deadline=lifetime)
            replay_name = replay_path.name
        else:
            raise ValueError('Source replay requires a qualified POSIX or native Windows input reader')
        owner.resources.append(external)
        capsule, replay_inputs = _SourceInputs(owner, actual), _SourceInputs(owner, external)
        owner.borrowed.extend((capsule, replay_inputs))
        return _inspect_source_inputs(owner, capsule, replay_inputs, replay_name, handoff_sha256, replay_reference)
    except BaseException:
        owner.revoke()
        owner.close()
        raise


def verify_for_handoff(root, handoff_sha256, replay_reference, *, input_qualification=None, deadline=None):
    """Compatibility wrapper returning passive facts after closing actual owners."""
    inspection = inspect_for_handoff(root, handoff_sha256, replay_reference,
                                    input_qualification=input_qualification, deadline=deadline)
    try:
        inspection.check()
        return inspection.as_dict()
    finally:
        inspection.close()


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    check = commands.add_parser('check')
    check.add_argument('--selection', required=True, type=Path)
    check.add_argument('--selection-sha256', required=True)
    native = commands.add_parser('check-handoff')
    native.add_argument('--root', required=True, type=Path)
    native.add_argument('--handoff-sha256', required=True)
    native.add_argument('--replay', required=True)
    native.add_argument('--replay-sha256', required=True)
    native.add_argument('--input-qualification')
    native.add_argument('--input-qualification-sha256')
    args = parser.parse_args(argv)
    if args.action == 'check-handoff' and ((args.input_qualification is None) !=
                                          (args.input_qualification_sha256 is None)):
        parser.error('--input-qualification and --input-qualification-sha256 must be supplied together')
    try:
        if args.action == 'check':
            result = check_selection(args.selection, args.selection_sha256)
        else:
            reference = {'path': args.replay, 'sha256': args.replay_sha256}
            if args.input_qualification is None:
                result = verify_for_handoff(args.root, args.handoff_sha256, reference)
            else:
                if os.name != 'nt':
                    raise ValueError('Native input qualification is only accepted on native Windows')
                qualification = admit_native_input_qualification({'path': args.input_qualification,
                    'sha256': args.input_qualification_sha256})
                result = verify_for_handoff(args.root, args.handoff_sha256, reference,
                                           input_qualification=qualification)
        print(encoded(result).decode('ascii'), end='')
        return 0
    except MissingInputs as error:
        print(encoded(error.as_dict()).decode('ascii'), file=sys.stderr, end='')
        return 2
    except (OSError, ValueError) as error:
        print('Windows source replay: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
