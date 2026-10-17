"""Opt-in actual Windows retained-input scenarios; source preparation only.

Run only after explicit native qualification authorization and Root registration.
FOUNDATION_WINDOWS_SOURCE_READER_ROOT must name a fresh, owned, canonical local
NTFS directory. All data inputs are generated fixture bytes beneath that root;
this module does not discover a source archive, SDK, tool, or application. The
archive scenario observes reader interfaces and byte pins, not B's replay core.
"""
import hashlib
import io
import mmap
import os
from pathlib import Path
import sys
import tarfile
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_publication as publication

_BASE = None
_SOURCES = None
_CASES = {}
_INPUTS = []
_WORKSPACES = []
_CONTROLS = []
_STREAMS = []
_MAPPINGS = []
_CASE_NAMES = (
    'test_pinned_metadata_read',
    'test_anchor_rename_delete_conflict',
    'test_write_handle_conflicts',
    'test_writable_mapping_conflict',
    'test_leaf_rename_delete_conflict',
    'test_reparse_hardlink_alias_rejected',
    'test_seekable_zip_tar_capture',
    'test_bounds_deadline_and_state_changes',
    'test_reader_close_releases_handles',
)


def _limits(**changes):
    value = {'seconds': 30, 'maximum_archive_bytes': 1024 * 1024,
        'maximum_expanded_bytes': 4 * 1024 * 1024, 'maximum_members': 64,
        'maximum_member_bytes': 1024 * 1024, 'maximum_patch_bytes': 1024 * 1024}
    value.update(changes)
    return value


def _pin(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'mode': 0o644}


def _error_fact(error):
    return {'type': type(error).__name__, 'errno': getattr(error, 'errno', None),
        'winerror': getattr(error, 'winerror', None), 'message': str(error)}


def _source_identity():
    required = {'tools/appended_engine_windows_publication.py',
        'tests/diagnostics/windows_engine_source_reader.py', 'tools/process_tree.py',
        'tools/appended_engine_windows_contract.py'}
    if set(publication.INPUT_SOURCE_FILES) != required:
        raise ValueError('Reader diagnostic subject must contain exactly its four admitted sources')
    value = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in publication.INPUT_SOURCE_FILES}
    if value['tools/appended_engine_windows_contract.py'] != publication.INPUT_CONTRACT_SHA256:
        raise ValueError('Reader diagnostic contract source differs')
    return value


def _control_open(path, access, *, directory=False):
    """Diagnostic-owned fixture handle; never borrowed from the input owner."""
    native = _BASE.native
    text, _us = publication._utf16(path.replace('/', '\\'))
    flags = 0x00200000 | (0x02000000 if directory else 0)
    handle = native.k.CreateFileW(text, access, 7, None, 3, flags, None)
    if handle == publication.ct.c_void_p(-1).value:
        native._win(False, 'CreateFileW source-reader fixture control')
    record = {'handle': handle, 'closed': False, 'path': path, 'access': access}
    _CONTROLS.append(record)
    return record


def _control_close(record):
    if not record['closed']:
        _BASE.native.close(record['handle'])
        record['closed'] = True


def _fixture_stream(path, mode, **options):
    stream = open(path, mode, **options)
    _STREAMS.append(stream)
    return stream


def _state(path, *, directory=False):
    record = _control_open(path, 0x80000000, directory=directory)
    try:
        return _BASE.native.state(record['handle'])
    finally:
        _control_close(record)


def _close_inputs(owner):
    if owner.uncertain:
        raise AssertionError('Uncertain input owner must remain retained; no successful closure claim')
    if not owner.closed:
        owner.close()
    if not owner.closed or owner.uncertain:
        raise AssertionError('Input owner did not confirm terminal known closure')


def setUpModule():
    global _BASE, _SOURCES
    publication._native_host()
    if not sys.dont_write_bytecode:
        raise ValueError('Native source-reader diagnostic must start with -B')
    if tuple(publication.INPUT_CASE_NAMES) != _CASE_NAMES:
        raise ValueError('Reader native case inventory differs from its admitted helper')
    selected = os.environ.get('FOUNDATION_WINDOWS_SOURCE_READER_ROOT')
    if not selected:
        raise ValueError('Select a fresh owned FOUNDATION_WINDOWS_SOURCE_READER_ROOT')
    publication.contract.windows_path(selected, 'native source-reader diagnostic root')
    _SOURCES = _source_identity()
    _BASE = publication._diagnostic_workspace(selected,
        limits={'maximum_output_bytes': 4 * 1024 * 1024})


def tearDownModule():
    if _BASE is None:
        return
    if (any(not owner.closed or owner.uncertain for owner in _INPUTS) or
            any(not work.closed or work.uncertain for work in _WORKSPACES) or
            any(not record['closed'] for record in _CONTROLS) or
            any(not stream.closed for stream in _STREAMS) or
            any(not mapping.closed for mapping in _MAPPINGS)):
        raise AssertionError('Reader fixture ownership remains open or uncertain; retain all evidence')
    if set(_CASES) != set(_CASE_NAMES):
        raise AssertionError('Incomplete native reader cases; omit success-bound observation marker')
    subjects = _source_identity()
    if subjects != _SOURCES:
        raise ValueError('Native source-reader subject changed during the diagnostic')
    value = {'schema_version': 1, 'kind': 'foundation-windows-source-reader-observations-v1',
        'scope': publication.INPUT_SCOPE, 'policy': publication.INPUT_POLICY,
        'source_identity': subjects, 'runtime_identity': _BASE.native.runtime_identity(),
        'filesystem': _BASE.filesystem, 'cases': _CASES}
    raw = publication.encoded(value)
    row = _BASE.publish_bytes_new('observations.json', raw)
    path = _BASE.output + '/observations.json'
    _BASE.close_joined()
    print('WINDOWS_SOURCE_READER_OBSERVATIONS_SHA256=' + row['sha256'], flush=True)
    print('WINDOWS_SOURCE_READER_OBSERVATIONS_PATH=' + path, flush=True)


class NativeSourceReader(unittest.TestCase):
    def fixture(self, files, *, directories=()):
        work = publication._diagnostic_workspace(_BASE.output + '/' + self._testMethodName,
            limits={'maximum_output_bytes': 1024 * 1024})
        _WORKSPACES.append(work)
        parents = set(directories)
        for name in files:
            parts = name.split('/')
            parents.update('/'.join(parts[:index]) for index in range(1, len(parts)))
        for name in sorted(parents, key=lambda item: (item.count('/'), item)):
            work.mkdir_new(name)
        pins = {name: _pin(raw) for name, raw in files.items()}
        for name, raw in files.items():
            row = work.publish_bytes_new(name, raw)
            self.assertEqual(row['sha256'], pins[name]['sha256'])
            self.assertEqual(row['bytes'], pins[name]['bytes'])
        root = work.output
        # The fixture writer must not independently hold the locks under test.
        work.close_joined()
        self.assertTrue(work.closed)
        return root, pins

    def inputs(self, root, *, limits=None, deadline=None):
        owner = publication._diagnostic_inputs(root, limits=_limits() if limits is None else limits,
            deadline=deadline)
        _INPUTS.append(owner)
        self.addCleanup(_close_inputs, owner)
        self.assertEqual(owner.root, root)
        self.assertEqual(owner.filesystem, _BASE.filesystem)
        return owner

    def record(self, observed):
        self.assertIn(self._testMethodName, _CASE_NAMES)
        self.assertNotIn(self._testMethodName, _CASES)
        self.assertTrue(observed)
        _CASES[self._testMethodName] = {'operation': self._testMethodName, 'observed': observed}

    def sharing_error(self, operation):
        with self.assertRaises(OSError) as caught:
            operation()
        error = caught.exception
        self.assertEqual(getattr(error, 'winerror', None) or error.errno, 32,
            'Fixture must observe ERROR_SHARING_VIOLATION, not merely an unrelated open failure')
        return _error_fact(error)

    def reject_read(self, root, name, expected, *, maximum=65536, limits=None):
        owner = self.inputs(root, limits=limits)
        try:
            with self.assertRaises((ValueError, OSError)) as caught:
                owner.read(name, expected=expected, maximum=maximum)
            return _error_fact(caught.exception)
        finally:
            _close_inputs(owner)

    def test_pinned_metadata_read(self):
        raw = b'{"fixture":"retained-input"}\n'
        root, pins = self.fixture({'metadata.json': raw})
        before = _state(root + '/metadata.json')
        owner = self.inputs(root)
        actual = owner.read('metadata.json', expected=pins['metadata.json'], maximum=1024)
        self.assertIs(type(actual), bytes)
        self.assertEqual(actual, raw)
        owner.check()
        after = _state(root + '/metadata.json')
        self.assertEqual(after, before)
        _close_inputs(owner)
        sha_only_expected = {'sha256': pins['metadata.json']['sha256'], 'mode': 0o644}
        sha_only_owner = self.inputs(root)
        self.assertEqual(sha_only_owner.read('metadata.json', expected=sha_only_expected, maximum=1024), raw)
        sha_only_owner.check()
        _close_inputs(sha_only_owner)
        failures = {}
        for key, replacement in (('bytes', len(raw) + 1), ('sha256', '2' * 64), ('mode', 0o755)):
            expected = dict(pins['metadata.json'], **{key: replacement})
            failures[key] = self.reject_read(root, 'metadata.json', expected)
        self.record({'expected': pins['metadata.json'], 'actual_sha256': hashlib.sha256(actual).hexdigest(),
            'before': before, 'after': after, 'rejected_expected_values': failures,
            'sha_only_expected': sha_only_expected, 'observed_eof': after['bytes'],
            'mode_scope': 'logical manifest mode; observed NT attributes are separate facts',
            'owner_closed': owner.closed, 'sha_only_owner_closed': sha_only_owner.closed})

    def test_anchor_rename_delete_conflict(self):
        raw = b'anchored ordinary input\n'
        root, pins = self.fixture({'nested/metadata.txt': raw})
        owner = self.inputs(root)
        self.assertEqual(owner.read('nested/metadata.txt', expected=pins['nested/metadata.txt'], maximum=1024), raw)
        path = root + '/nested'
        before = _state(path, directory=True)
        conflict = self.sharing_error(lambda: _control_open(path, 0x10000, directory=True))
        with self.assertRaises(OSError) as renamed:
            os.rename(path, root + '/nested-moved')
        owner.check()
        self.assertEqual(_state(path, directory=True), before)
        _close_inputs(owner)
        control = _control_open(path, 0x10000, directory=True)
        _control_close(control)
        os.rename(path, root + '/nested-moved')
        os.rename(root + '/nested-moved', path)
        after = _state(path, directory=True)
        self.assertEqual(after['identity'], before['identity'])
        self.record({'directory_before': before, 'delete_open_conflict': conflict,
            'rename_conflict': _error_fact(renamed.exception), 'after_release': after,
            'owner_closed': owner.closed})

    def test_write_handle_conflicts(self):
        raw = b'write-sharing fixture\n'
        root, pins = self.fixture({'metadata.txt': raw})
        path = root + '/metadata.txt'
        writer = _control_open(path, 0x40000000)
        owner = self.inputs(root)
        try:
            preexisting = self.sharing_error(lambda: owner.read('metadata.txt',
                expected=pins['metadata.txt'], maximum=1024))
        finally:
            _control_close(writer)
            _close_inputs(owner)
        held = self.inputs(root)
        self.assertEqual(held.read('metadata.txt', expected=pins['metadata.txt'], maximum=1024), raw)
        subsequent = self.sharing_error(lambda: _control_open(path, 0x40000000))
        # A truncating ordinary open must also fail while the retained leaf is live.
        with self.assertRaises(OSError) as truncated:
            with _fixture_stream(path, 'wb'):
                self.fail('Truncating fixture open unexpectedly succeeded')
        held.check()
        state = _state(path)
        self.assertEqual(state['bytes'], len(raw))
        _close_inputs(held)
        with _fixture_stream(path, 'rb') as stream:
            self.assertEqual(stream.read(len(raw) + 1), raw)
        self.record({'expected': pins['metadata.txt'], 'preexisting_writer_conflict': preexisting,
            'subsequent_writer_conflict': subsequent, 'truncate_conflict': _error_fact(truncated.exception),
            'retained_state': state, 'closed_owners': [owner.closed, held.closed]})

    def test_writable_mapping_conflict(self):
        raw = b'writable mapping fixture\n'
        root, pins = self.fixture({'mapped.txt': raw})
        stream = _fixture_stream(root + '/mapped.txt', 'r+b', buffering=0)
        mapping = None
        conflicts = []
        try:
            mapping = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_WRITE)
            _MAPPINGS.append(mapping)
            owner = self.inputs(root)
            try:
                conflicts.append(self.sharing_error(lambda: owner.read('mapped.txt',
                    expected=pins['mapped.txt'], maximum=1024)))
            finally:
                _close_inputs(owner)
            stream.close()
            self.assertTrue(stream.closed)
            self.assertFalse(mapping.closed)
            owner = self.inputs(root)
            try:
                conflicts.append(self.sharing_error(lambda: owner.read('mapped.txt',
                    expected=pins['mapped.txt'], maximum=1024)))
            finally:
                _close_inputs(owner)
        finally:
            if mapping is not None and not mapping.closed:
                mapping.close()
            if not stream.closed:
                stream.close()
        owner = self.inputs(root)
        self.assertEqual(owner.read('mapped.txt', expected=pins['mapped.txt'], maximum=1024), raw)
        owner.check()
        state = _state(root + '/mapped.txt')
        _close_inputs(owner)
        self.record({'write_mapping_conflicts': conflicts, 'original_stream_closed': stream.closed,
            'mapping_closed': mapping.closed, 'after_release': state, 'expected': pins['mapped.txt'],
            'fixture_scope': 'stdlib mmap; runtime-private retained handles are not enumerated'})

    def test_leaf_rename_delete_conflict(self):
        raw = b'retained leaf\n'
        root, pins = self.fixture({'metadata.txt': raw})
        path = root + '/metadata.txt'
        before = _state(path)
        owner = self.inputs(root)
        self.assertEqual(owner.read('metadata.txt', expected=pins['metadata.txt'], maximum=1024), raw)
        conflict = self.sharing_error(lambda: _control_open(path, 0x10000))
        with self.assertRaises(OSError) as renamed:
            os.rename(path, root + '/moved.txt')
        owner.check()
        self.assertEqual(_state(path), before)
        _close_inputs(owner)
        control = _control_open(path, 0x10000)
        _control_close(control)
        os.rename(path, root + '/moved.txt')
        os.rename(root + '/moved.txt', path)
        after = _state(path)
        self.assertEqual(after['identity'], before['identity'])
        self.record({'leaf_before': before, 'delete_open_conflict': conflict,
            'rename_conflict': _error_fact(renamed.exception), 'after_release': after,
            'expected': pins['metadata.txt'], 'owner_closed': owner.closed})

    def test_reparse_hardlink_alias_rejected(self):
        raw = b'ordinary namespace fixture\n'
        root, pins = self.fixture({'original.txt': raw, 'linked.txt': raw}, directories=('directory',))
        os.symlink('original.txt', root + '/symbolic.txt')
        os.link(root + '/linked.txt', root + '/hard.txt')
        # Missing symlink privilege fails the case; no platform-internal skips.
        rejected = {}
        for name in ('symbolic.txt', 'linked.txt', 'hard.txt', 'ORIGINAL.TXT', 'directory'):
            rejected[name] = self.reject_read(root, name, pins['original.txt'])
        for name in ('/absolute', 'C:relative', 'C:/absolute', '../original.txt',
                'original.txt:ads', 'NUL', 'nested//original.txt'):
            rejected[name] = self.reject_read(root, name, pins['original.txt'])
        owner = self.inputs(root)
        self.assertEqual(owner.read('original.txt', expected=pins['original.txt'], maximum=1024), raw)
        owner.check()
        state = _state(root + '/original.txt')
        _close_inputs(owner)
        self.assertEqual(os.stat(root + '/linked.txt').st_nlink, 2)
        self.assertTrue(os.path.islink(root + '/symbolic.txt'))
        self.record({'rejected_inputs': rejected, 'ordinary_file': state,
            'hardlink_count': 2, 'symlink_created': True, 'owner_closed': owner.closed})

    def test_seekable_zip_tar_capture(self):
        member = b'generated member bytes\n'
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('member.txt', member)
        tarred = io.BytesIO()
        with tarfile.open(fileobj=tarred, mode='w') as archive:
            entry = tarfile.TarInfo('member.txt')
            entry.size, entry.mode, entry.mtime = len(member), 0o644, 0
            archive.addfile(entry, io.BytesIO(member))
        bodies = {'fixture.zip': zipped.getvalue(), 'fixture.tar': tarred.getvalue()}
        root, pins = self.fixture(bodies)
        owner = self.inputs(root)
        facts = {}
        for name, raw in bodies.items():
            view = owner.open_archive(name, expected=pins[name])
            self.assertTrue(view.readable())
            self.assertTrue(view.seekable())
            self.assertFalse(hasattr(view, 'fileno'))
            digest, count = hashlib.sha256(), 0
            while True:
                chunk = view.read(4096)
                if not chunk:
                    break
                count += len(chunk)
                self.assertLessEqual(count, pins[name]['bytes'])
                digest.update(chunk)
            self.assertEqual(count, pins[name]['bytes'])
            self.assertEqual(digest.hexdigest(), pins[name]['sha256'])
            self.assertEqual(view.seek(0, os.SEEK_END), len(raw))
            self.assertEqual(view.read(1), b'')
            self.assertEqual(view.seek(-5, os.SEEK_END), len(raw) - 5)
            self.assertEqual(view.read(-1), raw[-5:])
            self.assertEqual(view.seek(0), 0)
            self.assertEqual(view.read(0), b'')
            self.assertEqual(view.read(4), raw[:4])
            self.assertEqual(view.seek(-2, os.SEEK_CUR), 2)
            self.assertEqual(view.read(2), raw[2:4])
            self.assertEqual(view.seek(1), 1)
            second = owner.open_archive(name, expected=pins[name])
            self.assertEqual(second.tell(), 0)
            self.assertEqual(second.read(3), raw[:3])
            self.assertEqual(view.tell(), 1)
            second.close()
            self.assertTrue(second.closed)
            view.seek(0)
            if name.endswith('.zip'):
                with zipfile.ZipFile(view, 'r') as archive:
                    self.assertEqual(archive.namelist(), ['member.txt'])
                    self.assertEqual(archive.read('member.txt'), member)
            else:
                with tarfile.open(fileobj=view, mode='r:') as archive:
                    self.assertEqual(archive.getnames(), ['member.txt'])
                    extracted = archive.extractfile('member.txt')
                    self.assertIsNotNone(extracted)
                    with extracted:
                        self.assertEqual(extracted.read(), member)
            self.assertFalse(view.closed)
            view.close()
            self.assertTrue(view.closed)
            facts[name] = {'expected': pins[name], 'actual_compressed_bytes': count,
                'actual_compressed_sha256': digest.hexdigest(), 'member_bytes': len(member),
                'member_sha256': hashlib.sha256(member).hexdigest(), 'closed_views': 2}
        owner.check()
        _close_inputs(owner)
        self.record({'reader_interface_and_actual_pin_only': facts,
            'b_shared_core_integration': 'separate unqualified scope', 'owner_closed': owner.closed})

    def test_bounds_deadline_and_state_changes(self):
        first, second = b'abc', b'defgh'
        header = b'/* complete held input tree fixture */\n'
        root, pins = self.fixture({'first.txt': first, 'second.txt': second,
            'include/nested/header.h': header}, directories=('empty',))
        failures = {'metadata_maximum': self.reject_read(root, 'second.txt', pins['second.txt'], maximum=4)}
        for key, selected in (('aggregate_bytes', _limits(maximum_archive_bytes=6,
                maximum_expanded_bytes=6, maximum_member_bytes=6, maximum_patch_bytes=6)),
                ('input_count', _limits(maximum_members=1))):
            owner = self.inputs(root, limits=selected)
            try:
                self.assertEqual(owner.read('first.txt', expected=pins['first.txt'], maximum=len(first)), first)
                with self.assertRaises((ValueError, OSError)) as rejected:
                    owner.read('second.txt', expected=pins['second.txt'], maximum=len(second))
                failures[key] = _error_fact(rejected.exception)
            finally:
                _close_inputs(owner)
        owner = self.inputs(root, limits=_limits(maximum_archive_bytes=4))
        try:
            with self.assertRaises((ValueError, OSError)) as rejected:
                owner.open_archive('second.txt', expected=pins['second.txt'])
            failures['archive_eof'] = _error_fact(rejected.exception)
        finally:
            _close_inputs(owner)
        expired = time.monotonic() - 1
        try:
            expired_owner = publication._diagnostic_inputs(root, limits=_limits(), deadline=expired)
        except (ValueError, OSError) as error:
            failures['expired_enclosing_deadline'] = _error_fact(error)
        else:
            _INPUTS.append(expired_owner)
            self.addCleanup(_close_inputs, expired_owner)
            self.fail('Expired enclosing deadline unexpectedly admitted an input owner')
        owner = self.inputs(root)
        self.assertEqual(owner.read('first.txt', expected=pins['first.txt'], maximum=8), first)
        path = root + '/first.txt'
        before = _state(path)
        times = os.stat(path)
        os.utime(path, ns=(times.st_atime_ns, times.st_mtime_ns + 2000000000))
        changed = _state(path)
        self.assertNotEqual(changed['version'], before['version'])
        with self.assertRaises((ValueError, OSError)) as rejected:
            owner.check()
        failures['allowed_timestamp_change'] = _error_fact(rejected.exception)
        _close_inputs(owner)
        # A second owner observes the new fixed version. Structural capture
        # deliberately performs no archive/body hash; explicit readback follows.
        tree_owner = self.inputs(root)
        declarations = {name: {'sha256': row['sha256'], 'mode': row['mode']} for name, row in pins.items()}
        tree = tree_owner.capture_tree('', files=declarations,
            directories=['empty', 'include', 'include/nested'])
        tree_before = tree.as_dict()
        self.assertEqual(tree_before['root'], '')
        self.assertEqual(tree_before['files'], declarations)
        readback = {}
        for name, raw in (('first.txt', first), ('second.txt', second), ('include/nested/header.h', header)):
            view = tree.open_file(name)
            try:
                actual = view.read()
            finally:
                view.close()
            self.assertEqual(actual, raw)
            readback[name] = {'sha256': hashlib.sha256(actual).hexdigest(), 'bytes': len(actual)}
            self.assertEqual(tree_before['observed']['files'][name]['bytes'], len(actual))
            self.assertNotIn('bytes', tree_before['files'][name])
        tree_owner.check()
        # Directory sharing does not freeze membership. This controlled fixture
        # writer closes before the complete boundary scan detects its new name.
        with _fixture_stream(root + '/include/undeclared.h', 'xb') as stream:
            self.assertEqual(stream.write(b'/* undeclared include */\n'), 25)
        with self.assertRaises((ValueError, OSError)) as rejected:
            tree_owner.check()
        failures['late_undeclared_header'] = _error_fact(rejected.exception)
        _close_inputs(tree_owner)
        self.record({'rejections': failures, 'before_change': before, 'after_change': changed,
            'absolute_expired_deadline': expired, 'owner_closed': owner.closed,
            'complete_tree': tree_before, 'explicit_tree_body_readback': readback,
            'tree_owner_closed': tree_owner.closed,
            'tree_contract': 'held identities plus repeated full names; cooperating writer exclusion remains caller-owned',
            'deadline_semantics': 'cooperative checks, no hard synchronous-call completion bound'})

    def test_reader_close_releases_handles(self):
        raw = b'close ownership fixture\n'
        root, pins = self.fixture({'metadata.txt': raw})
        path = root + '/metadata.txt'
        owner = self.inputs(root)
        view = owner.open_archive('metadata.txt', expected=pins['metadata.txt'])
        self.assertEqual(view.read(), raw)
        view.close()
        self.assertTrue(view.closed)
        held = self.sharing_error(lambda: _control_open(path, 0x40000000))
        owner.check()
        _close_inputs(owner)
        self.assertTrue(owner.closed)
        with self.assertRaises((ValueError, OSError)):
            owner.read('metadata.txt', expected=pins['metadata.txt'], maximum=1024)
        with self.assertRaises((ValueError, OSError)):
            view.read(1)
        writer = _control_open(path, 0x40000000)
        _control_close(writer)
        os.rename(path, root + '/moved.txt')
        os.rename(root + '/moved.txt', path)
        state = _state(path)
        self.record({'view_closed_while_owner_live_conflict': held, 'view_closed': view.closed,
            'owner_closed': owner.closed, 'after_controlled_write_open_and_rename': state,
            'expected': pins['metadata.txt']})


if __name__ == '__main__':
    unittest.main()
