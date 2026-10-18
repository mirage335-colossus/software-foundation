"""Tiny native-producer admission fixtures; no SDK/compiler/engine is run.

All byte images and inventories produced here are synthetic unit inputs. A
successful low-level parser check establishes a format property only. It never
establishes native provenance, PIC, a linkable SDK or runtime qualification.
"""

import ast
import copy
from contextlib import ExitStack, contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import time
import types
import unittest
import zipfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/appended_engine_native_inputs.py'
TARGET = {'system': 'Linux', 'processor': 'x86_64',
          'triple': 'x86_64-buildroot-linux-gnu', 'pointer_bits': 64}
SOURCE_PROVENANCE_ROLES = ('engine-body-verification', 'engine-member-inventory',
                           'git-controls', 'git-selected-tree', 'git-top-tree',
                           'git-tree-receipt')
SYNTHETIC_LINK_LITERALS = {
    'Source/ThirdParty/skia/src/ports/fontations/Cargo.toml':
        ('../../../bazel/external/fontations/Cargo.toml',
         'Source/ThirdParty/skia/bazel/external/fontations/Cargo.toml'),
    'Tools/Scripts/libraries/reporelaypy/reporelaypy/static/css/webkit.css':
        ('../../../../resultsdbpy/resultsdbpy/view/static/library/css/webkit.css',
         'Tools/Scripts/libraries/resultsdbpy/resultsdbpy/view/static/library/css/webkit.css'),
    'Tools/Scripts/webkitpy/benchmark_runner/data/plans/jetstream2.plan':
        ('jetstream2.2.plan', 'Tools/Scripts/webkitpy/benchmark_runner/data/plans/jetstream2.2.plan'),
    'Tools/Scripts/webkitpy/benchmark_runner/data/plans/motionmark.plan':
        ('motionmark1.3.1.plan', 'Tools/Scripts/webkitpy/benchmark_runner/data/plans/motionmark1.3.1.plan'),
    'Tools/Scripts/webkitpy/benchmark_runner/data/plans/speedometer.plan':
        ('speedometer2.1.plan', 'Tools/Scripts/webkitpy/benchmark_runner/data/plans/speedometer2.1.plan'),
    'Tools/Scripts/webkitpy/benchmark_runner/data/plans/speedometer2.plan':
        ('speedometer2.1.plan', 'Tools/Scripts/webkitpy/benchmark_runner/data/plans/speedometer2.1.plan'),
    'Tools/Scripts/webkitpy/benchmark_runner/data/plans/speedometer3.plan':
        ('speedometer3.1.plan', 'Tools/Scripts/webkitpy/benchmark_runner/data/plans/speedometer3.1.plan'),
    'Tools/Tracing/SystemTracePoints.plist':
        ('../../Source/WebKit/Resources/Signposts/SystemTracePoints.plist',
         'Source/WebKit/Resources/Signposts/SystemTracePoints.plist')}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def load_helper():
    """Read the new repository helper without creating bytecode side effects."""
    module = types.ModuleType('_native_inputs_unit_helper')
    module.__file__ = str(HELPER)
    old_bytecode = sys.dont_write_bytecode
    old_module = sys.modules.get(module.__name__)
    old_path = list(sys.path)
    sys.modules[module.__name__] = module
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        exec(compile(HELPER.read_bytes(), str(HELPER), 'exec'), module.__dict__)
    finally:
        sys.dont_write_bytecode = old_bytecode
        sys.path[:] = old_path
        if old_module is None:
            sys.modules.pop(module.__name__, None)
        else:
            sys.modules[module.__name__] = old_module
    return module


@contextmanager
def no_programs():
    """A passive input operation must not execute even a version command."""
    with mock.patch('subprocess.run', side_effect=AssertionError('program launch')), \
            mock.patch('subprocess.Popen', side_effect=AssertionError('program launch')), \
            mock.patch('subprocess.check_output', side_effect=AssertionError('program launch')), \
            mock.patch('os.system', side_effect=AssertionError('program launch')):
        yield


class TinyFiles:
    """Explicit files/inventories; never an actual target toolchain or SDK."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def file(self, relative, raw, mode=0o644):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in path.parents:
            if parent == self.root:
                break
            parent.chmod(0o755)
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def document(self, relative, value):
        path = self.file(relative, encoded(value))
        return {'path': relative, 'sha256': digest(path.read_bytes())}

    def inventory(self, name, root_relative, members):
        root = self.root / root_relative
        root.mkdir(parents=True, exist_ok=True)
        root.chmod(0o755)
        files = {}
        modes = {}
        directories = set()
        for relative, (raw, mode) in members.items():
            path = self.file(root_relative + '/' + relative, raw, mode)
            files[relative] = digest(raw)
            modes[relative] = mode
            for parent in Path(relative).parents:
                if parent == Path('.'):
                    continue
                directories.add(parent.as_posix())
                (root / parent).chmod(0o755)
        for relative in directories:
            modes[relative] = 0o755
        ref = self.document('inventory-' + name + '.json',
                            {'files': files, 'directories': sorted(directories),
                             'modes': modes})
        return {'root': str(root), 'inventory': ref}

    def archive(self, relative, members):
        """Regular tar members only; malicious variants are made per test."""
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for name, raw in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(raw))
        return self.file(relative, stream.getvalue())


def elf_object(machine=62, elf_class=2, endian=1, kind=1):
    """Minimal hand-encoded ELF format fixture, never compiler-produced code."""
    ident = b'\x7fELF' + bytes((elf_class, endian, 1, 0)) + bytes(8)
    header = struct.pack('<HHIQQQIHHHHHH', kind, machine, 1, 0, 0, 64, 0,
                         64, 0, 0, 64, 2, 0)
    null_section = bytes(64)
    text_section = struct.pack('<IIQQQQIIQQ', 0, 1, 6, 0, 192, 1, 0, 0, 1, 0)
    return ident + header + null_section + text_section + b'\xc3'


def static_archive(members):
    """Ordinary ar layout around inert hand-encoded member byte fixtures."""
    raw = bytearray(b'!<arch>\n')
    for name, body in members:
        header = (str(name + '/').ljust(16) + '0'.ljust(12) + '0'.ljust(6)
                  + '0'.ljust(6) + '100644'.ljust(8) + str(len(body)).ljust(10)
                  + '`\n').encode('ascii')
        if len(header) != 60:
            raise ValueError('fixture archive header length')
        raw.extend(header)
        raw.extend(body)
        if len(body) % 2:
            raw.extend(b'\n')
    return bytes(raw)


class NativeInputParsing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def test_strict_json_preserves_ordinary_utf8_values(self):
        value = {'text': 'a\u00e9\U0001f642', 'items': [0, True, None]}
        with no_programs():
            self.assertEqual(self.api.strict_json(encoded(value)), value)

    def test_duplicate_fields_reject_at_every_depth(self):
        for raw in (b'{"x":1,"x":2}', b'{"a":{"x":1,"x":1}}',
                    b'{"a":[{"x":1,"x":2}]}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.api.strict_json(raw)

    def test_json_rejects_bad_unicode_nonfinite_and_trailing_data(self):
        invalid = (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}',
                   b'{"x":1e10000}', b'{"x":"\\ud800"}',
                   b'{"x":"\\udfff"}', b'{"x":"\xff"}', b'{} {}', b'')
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.api.strict_json(raw)

    def test_exact_linux_x64_target_is_the_only_executable_source_tuple(self):
        with no_programs():
            self.assertEqual(self.api.validate_target(copy.deepcopy(TARGET)), TARGET)
        mutations = ({**TARGET, 'extra': 1}, {**TARGET, 'pointer_bits': True},
                     {**TARGET, 'pointer_bits': 32},
                     {**TARGET, 'system': 'Emscripten'},
                     {**TARGET, 'processor': 'aarch64', 'triple': 'aarch64-linux-gnu'},
                     {**TARGET, 'triple': 'x86_64-linux-musl'},
                     {**TARGET, 'system': 'Windows', 'triple': 'x86_64-pc-windows-msvc'},
                     {'system': 'Linux'}, None, [])
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.api.validate_target(value)

    def test_phase_limits_are_closed_positive_integers_with_two_job_ceiling(self):
        good = {'prepare_seconds': 60, 'configure_seconds': 120,
                'build_seconds': 600, 'cleanup_seconds': 30, 'maximum_jobs': 2,
                'maximum_output_bytes': 1048576, 'minimum_free_bytes': 1073741824,
                'maximum_process_tree_bytes': 17179869184}
        self.assertEqual(self.api.validate_phase_limits(copy.deepcopy(good)), good)
        for key in good:
            for bad in (True, 0, -1, '1', None):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    self.api.validate_phase_limits({**good, key: bad})
        for value in ({**good, 'extra': 1}, {**good, 'maximum_jobs': 3},
                      {key: val for key, val in good.items() if key != 'build_seconds'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.api.validate_phase_limits(value)


    def test_generic_host_triple_cannot_replace_the_admitted_buildroot_target(self):
        self.assertEqual(TARGET['triple'], 'x86_64-buildroot-linux-gnu')
        with no_programs(), self.assertRaises(ValueError):
            self.api.validate_target({**TARGET, 'triple': 'x86_64-linux-gnu'})


class NativeExplicitInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-input-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def test_explicit_file_and_document_use_independent_pins_without_programs(self):
        raw = b'Synthetic source input only.\n'
        path = self.f.file('retained/input.txt', raw)
        inputs = self.api.InputSet()
        with no_programs():
            record = inputs.file(path, digest(raw), 'synthetic-source')
            reference = self.f.document('retained/doc.json', {'path': 'relative'})
            value = inputs.document({'path': 'doc.json', 'sha256': reference['sha256']},
                                    path.parent, 'synthetic-document')
            inputs.recheck()
        self.assertEqual(value, {'path': 'relative'})
        self.assertEqual(record['sha256'], digest(raw))
        self.assertEqual(record['bytes'], len(raw))
        self.assertEqual(record['mode'], 0o644)
        self.assertEqual(Path(record['path']), path)
        self.assertIn('synthetic-source', record['roles'])
        self.assertEqual(len(inputs.records), 2)

    def test_provenance_keeps_data_recipe_alias_when_same_input_is_also_a_notice(self):
        raw = b'Explicit synthetic original record with a separate notice role.\n'
        path = self.f.file('records/original.txt', raw)
        for notice_role in ('supplier-notice', 'asset-notice'):
            with self.subTest(notice_role=notice_role), no_programs():
                inputs = self.api.InputSet()
                inputs.file(path, digest(raw), 'supplier-provenance-git-controls')
                inputs.file(path, digest(raw), notice_role)
                aliases = self.api._record_aliases(inputs.records)
                recipe_inputs = {name: {'role': role, 'path': original}
                                 for name, original, role in aliases}
                data = recipe_inputs['native-inputs/records/' + digest(raw) + '.bin']
                notice = recipe_inputs['notices/retained/' + digest(raw) + '.txt']
                self.assertEqual(data, {'role': 'data', 'path': path})
                self.assertEqual(notice, {'role': 'license', 'path': path})
                self.assertEqual(len(recipe_inputs), 2)
                self.assertEqual(inputs.records[0]['roles'],
                                 sorted([notice_role, 'supplier-provenance-git-controls']))

    def test_document_resolution_is_relative_to_containing_document(self):
        reference = self.f.document('group/manifest.json', {'marker': 'correct'})
        self.f.file('manifest.json', b'wrong relative base\n')
        with no_programs():
            result = self.api.InputSet().document(
                {'path': 'manifest.json', 'sha256': reference['sha256']},
                self.f.root / 'group', 'synthetic-document')
        self.assertEqual(result, {'marker': 'correct'})

    def test_missing_explicit_input_has_concrete_missing_role(self):
        inputs = self.api.InputSet()
        try:
            inputs.file(self.f.root / 'missing.a', '1' * 64, 'missing-native-library')
        except self.api.MissingInputs as error:
            self.assertIn('missing-native-library', error.roles)
            self.assertTrue(error.missing)
            diagnostic = error.as_dict()
            self.assertIsInstance(diagnostic, dict)
            self.assertIn('missing.a', json.dumps(diagnostic))
        else:
            self.fail('An absent explicitly named archive was accepted')

    def test_pin_types_zero_and_file_size_are_validated_before_admission(self):
        raw = b'inert bytes\n'
        path = self.f.file('file', raw)
        for pin in ('0' * 64, 'A' * 64, 'a' * 63, 'z' * 64, True, None,
                    '1' * 64):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                self.api.InputSet().file(path, pin, 'synthetic-source')
        with self.assertRaises(ValueError):
            with mock.patch.object(self.api.os, 'open',
                                   side_effect=AssertionError('oversized input opened')):
                self.api.InputSet().file(path, digest(raw), 'synthetic-source', maximum=4)

    def test_cumulative_file_and_byte_limits_stop_before_opening_next_input(self):
        first = self.f.file('first', b'1234')
        second = self.f.file('second', b'5678')
        for setting, limit in (('MAX_FILES', 1), ('MAX_BYTES', 6)):
            with self.subTest(setting=setting), mock.patch.object(self.api, setting, limit):
                inputs = self.api.InputSet()
                inputs.file(first, digest(b'1234'), 'first-synthetic-source')
                with mock.patch.object(self.api.os, 'open',
                                       side_effect=AssertionError('over-budget input opened')):
                    with self.assertRaises(ValueError):
                        inputs.file(second, digest(b'5678'), 'second-synthetic-source')

    def test_input_mutation_and_same_byte_replacement_are_detected(self):
        raw = b'inert bytes\n'
        path = self.f.file('retained/source', raw)
        inputs = self.api.InputSet()
        inputs.file(path, digest(raw), 'synthetic-source')
        path.write_bytes(b'mutated input\n')
        with self.assertRaises(ValueError):
            inputs.recheck()
        path.write_bytes(raw)
        inputs = self.api.InputSet()
        inputs.file(path, digest(raw), 'synthetic-source')
        replacement = self.f.file('retained/replacement', raw)
        replacement.replace(path)
        with self.assertRaises(ValueError):
            inputs.recheck()

    def test_leaf_and_ancestor_symlinks_and_hardlinks_are_rejected(self):
        raw = b'inert bytes\n'
        source = self.f.file('retained/source', raw)
        symlink = self.f.root / 'alias'
        symlink.symlink_to(source)
        with self.assertRaises(ValueError):
            self.api.InputSet().file(symlink, digest(raw), 'synthetic-source')
        hardlink = self.f.root / 'hardlink'
        os.link(source, hardlink)
        for path in (hardlink, source):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.api.InputSet().file(path, digest(raw), 'synthetic-source')
        hardlink.unlink()
        linked_directory = self.f.root / 'linked-directory'
        linked_directory.symlink_to(source.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.api.InputSet().file(linked_directory / source.name, digest(raw),
                                     'synthetic-source')


    def test_recheck_fresh_hash_probe_inherits_expiry_before_reading_its_chunk(self):
        raw = b'Synthetic bounded rehash input.\n'
        path = self.f.file('deadline/source', raw)
        inputs = self.api.InputSet()
        inputs.file(path, digest(raw), 'synthetic-deadline-source')
        inputs.deadline = 5.0
        clock = iter((0.0, 0.0, 6.0))
        original_fdopen = self.api.os.fdopen
        original_open = self.api.os.open

        @contextmanager
        def guarded_fdopen(descriptor, *args, **kwargs):
            with original_fdopen(descriptor, *args, **kwargs) as stream:
                class Guarded:
                    def fileno(self):
                        return stream.fileno()

                    def read(self, *read_args, **read_kwargs):
                        raise AssertionError('Fresh recheck probe read after its inherited deadline')
                yield Guarded()

        with mock.patch.object(self.api.time, 'monotonic',
                               side_effect=lambda: next(clock, 6.0)), \
                mock.patch.object(self.api.os, 'open', wraps=original_open) as opened, \
                mock.patch.object(self.api.os, 'fdopen', side_effect=guarded_fdopen):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                inputs.recheck()
        self.assertEqual(opened.call_count, 1)

    def test_recheck_complete_inventory_probe_stops_during_expired_scandir(self):
        inventory = self.f.inventory('deadline', 'deadline-root',
                                     {'leaf.txt': (b'Synthetic inventoried leaf.\n', 0o644)})
        inputs = self.api.InputSet()
        inputs.inventory(inventory, self.f.root, 'synthetic-deadline-inventory')
        inputs.deadline = 5.0
        root = Path(inventory['root'])
        phase = {'scanning': False, 'entries_requested': 0}
        original_scandir = self.api.os.scandir

        @contextmanager
        def guarded_scandir(path):
            with original_scandir(path) as iterator:
                if Path(path) != root:
                    yield iterator
                    return
                phase['scanning'] = True

                class Guarded:
                    def __iter__(self):
                        return self

                    def __next__(self):
                        phase['entries_requested'] += 1
                        if phase['entries_requested'] > 1:
                            raise AssertionError('Fresh inventory probe continued scanning after deadline')
                        return next(iterator)
                yield Guarded()

        with mock.patch.object(self.api.time, 'monotonic',
                               side_effect=lambda: 6.0 if phase['scanning'] else 0.0), \
                mock.patch.object(self.api.os, 'scandir', side_effect=guarded_scandir):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                inputs.recheck()
        self.assertTrue(phase['scanning'])
        self.assertEqual(phase['entries_requested'], 1)

    def test_absolute_colon_parent_is_rejected_before_file_open(self):
        raw = b'Ordinary synthetic file under a colon-bearing parent.\n'
        path = self.f.file('has:colon/input.txt', raw)
        self.assertTrue(path.is_file())
        with mock.patch.object(self.api.os, 'open',
                               side_effect=AssertionError('Colon-bearing path was opened')):
            with self.assertRaisesRegex(ValueError, 'absolute path'):
                self.api.InputSet().file(path, digest(raw), 'synthetic-colon-path')


class NativeRepositoryProducerModes(unittest.TestCase):
    """Repository producer exceptions never widen retained-input mode policy."""

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-repo-mode-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def producer_file(self, mode):
        logical = self.api.PRODUCERS[0]
        path = self.f.file('repository/' + logical,
                           b'Synthetic explicitly listed producer source.\n', mode)
        return path, self.f.root / 'repository'

    def capture(self, inputs, path, root):
        return inputs.repository_file(path, digest(path.read_bytes()),
                                      'synthetic-listed-producer', repository_root=root,
                                      source_paths=self.api.PRODUCERS)

    def test_only_allowlisted_producer_modes_get_explicit_logical_normalization(self):
        for physical, logical in ((0o644, 0o644), (0o664, 0o644),
                                  (0o755, 0o755), (0o775, 0o755)):
            with self.subTest(physical=oct(physical)):
                path, root = self.producer_file(physical)
                inputs = self.api.InputSet()
                with no_programs():
                    record = self.capture(inputs, path, root)
                    inputs.recheck()
                self.assertEqual(record['mode'], logical)
                self.assertEqual(record['physical_mode'], physical)
                self.assertEqual(record['mode_policy'], 'repository-producer-logical-v1')
                self.assertEqual(inputs.records[0]['physical_mode'], physical)
                self.assertEqual(path.stat().st_mode & 0o777, physical)

    def test_plain_retained_file_admission_stays_strict_for_group_write_modes(self):
        for physical in (0o664, 0o775):
            with self.subTest(physical=oct(physical)):
                path, root = self.producer_file(physical)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.InputSet().file(path, digest(path.read_bytes()),
                                              'strict-retained-input')

    def test_producer_exception_rejects_unreviewed_modes_paths_and_authority_changes(self):
        for physical in (0o600, 0o666, 0o700, 0o777):
            with self.subTest(physical=oct(physical)):
                path, root = self.producer_file(physical)
                with no_programs(), self.assertRaises(ValueError):
                    self.capture(self.api.InputSet(), path, root)
        path, root = self.producer_file(0o664)
        unlisted = self.f.file('repository/tools/not-an-admitted-producer.py',
                               b'Synthetic unlisted repository file.\n', 0o664)
        outsider = self.f.file('outside/' + self.api.PRODUCERS[0],
                               b'Synthetic file outside repository authority.\n', 0o664)
        for candidate in (unlisted, outsider):
            with self.subTest(candidate=candidate), no_programs(), self.assertRaises(ValueError):
                self.capture(self.api.InputSet(), candidate, root)
        inputs = self.api.InputSet()
        self.capture(inputs, path, root)
        changed = tuple(self.api.PRODUCERS) + ('tools/unreviewed-addition.py',)
        with no_programs(), self.assertRaises(ValueError):
            inputs.repository_file(path, digest(path.read_bytes()),
                                   'changed-producer-authority', repository_root=root,
                                   source_paths=changed)

    def test_recheck_retains_physical_mode_identity_even_when_logical_mode_matches(self):
        path, root = self.producer_file(0o644)
        inputs = self.api.InputSet()
        self.capture(inputs, path, root)
        path.chmod(0o664)
        with no_programs(), self.assertRaises(ValueError):
            inputs.recheck()

    def test_already_retained_input_cannot_acquire_repository_mode_waiver(self):
        path, root = self.producer_file(0o644)
        inputs = self.api.InputSet()
        inputs.file(path, digest(path.read_bytes()), 'original-strict-retained-input')
        with no_programs(), self.assertRaisesRegex(ValueError, 'already retained'):
            self.capture(inputs, path, root)
        record = inputs.records[0]
        self.assertEqual(record['mode'], 0o644)
        self.assertNotIn('physical_mode', record)
        self.assertNotIn('mode_policy', record)
        with no_programs():
            inputs.recheck()


    def test_repository_capture_does_not_relax_later_public_file_admission(self):
        path, root = self.producer_file(0o664)
        inputs = self.api.InputSet()
        with no_programs():
            accepted = self.capture(inputs, path, root)
        self.assertEqual(accepted['mode'], 0o644)
        self.assertEqual(accepted['physical_mode'], 0o664)
        with no_programs(), self.assertRaises(ValueError):
            inputs.file(path, digest(path.read_bytes()), 'strict-retained-after-source')
        self.assertNotIn('strict-retained-after-source', inputs.records[0]['roles'])
        with no_programs():
            repeated = self.capture(inputs, path, root)
            inputs.recheck()
        self.assertEqual(repeated['mode_policy'], 'repository-producer-logical-v1')

    def test_assets_cannot_reuse_repository_mode_authority_for_group_writable_font(self):
        assets = NativeExplicitAssets.fixture(self)
        original = self.f.root / assets['fonts'][0]['path']
        raw = original.read_bytes()
        relative = 'repository/' + self.api.PRODUCERS[0]
        path = self.f.file(relative, raw, 0o664)
        assets['fonts'][0]['path'] = relative
        inputs = self.api.InputSet()
        with no_programs():
            accepted = self.capture(inputs, path, self.f.root / 'repository')
        self.assertEqual(accepted['mode'], assets['fonts'][0]['mode'])
        self.assertEqual(accepted['physical_mode'], 0o664)
        with no_programs(), self.assertRaises(ValueError):
            self.api.parse_assets(assets, self.f.root, inputs, TARGET)
        record = next(item for item in inputs.records if item['path'] == str(path))
        self.assertNotIn('font', record['roles'])


class NativeArchiveFormats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-ar-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def test_low_level_elf_archive_format_is_not_provenance_or_pic_evidence(self):
        raw = static_archive([('first.o', elf_object()), ('second.o', elf_object())])
        path = self.f.file('synthetic-format-only.a', raw)
        with no_programs():
            result = self.api.inspect_static_archive(path)
        self.assertEqual(result['format'], 'elf64-x86_64-ar')
        self.assertEqual(result['members'], 2)
        self.assertEqual(result['sha256'], digest(raw))
        self.assertEqual(result['bytes'], len(raw))
        self.assertNotIn('production_eligible', result)
        self.assertNotIn('pic', result)

    def test_wasm_bitcode_thin_truncated_and_wrong_elf_members_reject(self):
        bodies = (b'\x00asm\x01\x00\x00\x00', b'BC\xc0\xde' + bytes(32),
                  elf_object(machine=183), elf_object(elf_class=1),
                  elf_object(endian=2), elf_object(kind=3), b'\x7fELF')
        invalid = [static_archive([('bad.o', body)]) for body in bodies]
        invalid.extend((b'!<thin>\n', b'!<arch>\nshort', b'arbitrary bytes',
                        static_archive([('ok.o', elf_object())])[:-1]))
        for index, raw in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.api.inspect_static_archive(self.f.file('bad-' + str(index) + '.a', raw))


class NativeExactPatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def test_patch_edit_add_delete_is_exact_and_leaves_inputs_unchanged(self):
        originals = {'Source/edit.cpp': b'first\nold\nlast\n',
                     'Source/delete.cpp': b'delete me\n',
                     'Source/untouched.cpp': b'untouched\n'}
        patch = (b'--- a/Source/edit.cpp\n+++ b/Source/edit.cpp\n'
                 b'@@ -1,3 +1,3 @@\n first\n-old\n+new\n last\n'
                 b'--- /dev/null\n+++ b/Source/add.cpp\n'
                 b'@@ -0,0 +1 @@\n+added\n'
                 b'--- a/Source/delete.cpp\n+++ /dev/null\n'
                 b'@@ -1 +0,0 @@\n-delete me\n')
        before = {'Source/edit.cpp': digest(originals['Source/edit.cpp']),
                  'Source/add.cpp': None,
                  'Source/delete.cpp': digest(originals['Source/delete.cpp'])}
        after = {'Source/edit.cpp': digest(b'first\nnew\nlast\n'),
                 'Source/add.cpp': digest(b'added\n'), 'Source/delete.cpp': None}
        snapshot = copy.deepcopy(originals)
        with no_programs():
            result = self.api.apply_unified_patch(originals, patch, before, after)
        self.assertEqual(originals, snapshot)
        self.assertEqual(result, {'Source/edit.cpp': b'first\nnew\nlast\n',
                                  'Source/add.cpp': b'added\n',
                                  'Source/untouched.cpp': b'untouched\n'})

    def test_wrong_coordinate_context_and_pins_never_get_fuzzy_recovery(self):
        originals = {'file.cpp': b'a\nb\nc\n'}
        patch = b'--- a/file.cpp\n+++ b/file.cpp\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n'
        pre = {'file.cpp': digest(originals['file.cpp'])}
        post = {'file.cpp': digest(b'a\nB\nc\n')}
        cases = ((patch.replace(b'-1,3 +1,3', b'-2,3 +2,3'), pre, post),
                 (patch.replace(b' a\n', b' x\n'), pre, post),
                 (patch, {'file.cpp': '1' * 64}, post),
                 (patch, pre, {'file.cpp': '2' * 64}),
                 (patch, {}, post),
                 (patch, pre, {**post, 'untouched.cpp': '3' * 64}))
        for raw, before, after in cases:
            with self.subTest(raw=raw, before=before, after=after), \
                    self.assertRaises(ValueError):
                self.api.apply_unified_patch(originals, raw, before, after)
        self.assertEqual(originals, {'file.cpp': b'a\nb\nc\n'})

    def test_escaping_binary_rename_and_duplicate_owners_reject(self):
        originals = {'file.cpp': b'old\n'}
        base = b'--- a/file.cpp\n+++ b/file.cpp\n@@ -1 +1 @@\n-old\n+new\n'
        pre = {'file.cpp': digest(b'old\n')}
        post = {'file.cpp': digest(b'new\n')}
        invalid = (base.replace(b'file.cpp', b'../file.cpp'),
                   base.replace(b'file.cpp', b'/absolute.cpp'),
                   b'GIT binary patch\nliteral 1\nA\n',
                   b'diff --git a/file.cpp b/renamed.cpp\nrename from file.cpp\n'
                   b'rename to renamed.cpp\n', base + base)
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.api.apply_unified_patch(originals, raw, pre, post)


class NativeExplicitAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-assets-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def fixture(self):
        notice_raw = b'Synthetic unit fixture notice; no native license claim.\n'
        self.f.file('NOTICES/fixture.txt', notice_raw)
        notice = {'path': 'NOTICES/fixture.txt', 'sha256': digest(notice_raw)}

        def asset(relative, raw):
            self.f.file(relative, raw)
            return {'path': relative, 'sha256': digest(raw), 'bytes': len(raw),
                    'mode': 0o644,
                    'origin': {'repository': 'https://example.invalid/unit-fixture',
                               'revision': 'synthetic-not-native'},
                    'notice': copy.deepcopy(notice)}

        return {'schema_version': 1,
                'kind': 'foundation-native-engine-prototype-assets-v1',
                'fonts': [asset('fonts/inert-font.bin', b'inert font bytes\n')],
                'font_config': asset('fonts/fonts.conf', b'<fixture/>\n'),
                'icu_data': asset('icu/inert-data.bin', b'inert ICU bytes\n'),
                'ca_bundle': asset('ca/inert.pem', b'inert CA bytes\n'),
                'notices': [notice],
                'initialization': {'policy': 'explicit-retained-assets-only',
                                   'font_search': 'retained-only',
                                   'icu_search': 'retained-only', 'network': False}}

    def test_assets_bind_bytes_origins_notices_and_retained_only_policy(self):
        value = self.fixture()
        inputs = self.api.InputSet()
        with no_programs():
            result = self.api.parse_assets(value, self.f.root, inputs, TARGET)
            inputs.recheck()
        self.assertEqual(result['initialization'], value['initialization'])
        self.assertEqual(len(result['fonts']), 1)
        self.assertEqual(result['fonts'][0]['sha256'], value['fonts'][0]['sha256'])
        self.assertEqual(Path(result['fonts'][0]['path']),
                         self.f.root / value['fonts'][0]['path'])

    def test_missing_asset_or_notice_reports_role_without_program_launch(self):
        for missing in ('fonts/inert-font.bin', 'NOTICES/fixture.txt'):
            with self.subTest(missing=missing):
                value = self.fixture()
                (self.f.root / missing).unlink()
                with no_programs(), self.assertRaises(self.api.MissingInputs) as caught:
                    self.api.parse_assets(value, self.f.root, self.api.InputSet(), TARGET)
                self.assertIn(Path(missing).name, str(caught.exception))

    def test_assets_reject_missing_notices_search_fallback_and_bad_scalar_types(self):
        mutations = (lambda value: value.update(extra=True),
                     lambda value: value.update(fonts=[]),
                     lambda value: value.update(notices=[]),
                     lambda value: value['initialization'].update(network=True),
                     lambda value: value['initialization'].update(network=0),
                     lambda value: value['initialization'].update(font_search='system'),
                     lambda value: value['initialization'].update(icu_search='ambient'),
                     lambda value: value['fonts'][0].update(bytes=True),
                     lambda value: value['fonts'][0].update(mode=True),
                     lambda value: value['fonts'][0].update(bytes=1),
                     lambda value: value['fonts'][0]['origin'].update(extra='unknown'),
                     lambda value: value['fonts'][0]['origin'].update(revision=''),
                     lambda value: value['fonts'][0]['notice'].update(sha256='1' * 64))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value = self.fixture()
                mutate(value)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.parse_assets(value, self.f.root, self.api.InputSet(), TARGET)


class NativeSupplierProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-projection-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def fixture(self):
        members = {
            'engine': {'engine/CMakeLists.txt': b'# Synthetic engine root; never configure.\n',
                       'engine/Source/cmake/WebKitCommon.cmake': b'# Inert fixture.\n',
                       'engine/Source/fixture.cpp': b'// Inert complete-projection member.\n',
                       'engine/Tools/fixture.txt': b'build-only source fixture\n'},
            'wrapper': {'wrapper/README.md': b'Synthetic supplier fixture only.\n',
                        'wrapper/src/embedder/main.cpp': b'// Never compiled.\n'}}
        archives = {}
        projection = {}
        directories = set()
        for name, files in members.items():
            path = self.f.archive('archives/' + name + '.tar.gz', files)
            archives[name] = {'path': path.relative_to(self.f.root).as_posix(),
                              'sha256': digest(path.read_bytes()),
                              'bytes': path.stat().st_size, 'format': 'tar-gzip',
                              'strip_prefix': name}
            for member, raw in files.items():
                stripped = member.split('/', 1)[1]
                destination = 'source/' + name + '/' + stripped
                projection[destination] = {'archive': name, 'member': stripped,
                                           'sha256': digest(raw), 'bytes': len(raw),
                                           'mode': 0o644}
                for parent in Path(destination).parents:
                    if parent != Path('.'):
                        directories.add(parent.as_posix())
        notice = self.f.file('NOTICES/source-fixture.txt',
                             b'Synthetic source fixture notice only.\n')
        value = {'schema_version': 1,
                 'kind': 'foundation-native-engine-prototype-sources-v1',
                 'suppliers': {
                     'wrapper': {'repository': 'https://github.com/theogbob/WebkitWasm',
                                 'commit': '68c618544e1f8af18ebce346281a6a49766aa194',
                                 'archive': 'wrapper'},
                     'engine': {'repository': 'https://github.com/WebKit/WebKit',
                                'commit': 'aec9d2ad958e716ab4bca4bf03007e6edac7323f',
                                'archive': 'engine'}},
                 'archives': archives,
                 'projection': {'files': projection,
                                'directories': sorted(directories),
                                'exclusions': {'engine': [], 'wrapper': []},
                                'normalizations': {'engine': {}, 'wrapper': {}}},
                 'patches': [],
                 'notices': [{'path': notice.relative_to(self.f.root).as_posix(),
                              'sha256': digest(notice.read_bytes())}]}
        provenance = []
        for role in SOURCE_PROVENANCE_ROLES:
            raw = ('SYNTHETIC lower-parser fixture only: ' + role + '\n').encode('ascii')
            path = self.f.file('provenance/' + role + '.fixture.txt', raw)
            provenance.append({'role': role, 'path': path.relative_to(self.f.root).as_posix(),
                               'sha256': digest(raw), 'bytes': len(raw)})
        value['provenance'] = provenance
        return value

    def parse(self, value):
        with no_programs():
            return self.api.parse_source_projection(value, self.f.root,
                                                    self.api.InputSet(), TARGET)

    def test_tiny_complete_projection_parses_without_promoting_fixture_provenance(self):
        value = self.fixture()
        result = self.parse(value)
        self.assertIsInstance(result, dict)
        self.assertNotIn('production_eligible', result)
        self.assertEqual(result['suppliers'], value['suppliers'])

    def test_uncovered_member_and_missing_required_supplier_roots_reject(self):
        for dropped in ('source/engine/Source/fixture.cpp',
                        'source/engine/Tools/fixture.txt',
                        'source/engine/CMakeLists.txt',
                        'source/engine/Source/cmake/WebKitCommon.cmake',
                        'source/wrapper/README.md',
                        'source/wrapper/src/embedder/main.cpp'):
            with self.subTest(dropped=dropped):
                value = self.fixture()
                del value['projection']['files'][dropped]
                with self.assertRaises(ValueError):
                    self.parse(value)

    def test_engine_source_member_cannot_be_hidden_as_exclusion(self):
        value = self.fixture()
        del value['projection']['files']['source/engine/Source/fixture.cpp']
        value['projection']['exclusions']['engine'] = ['Source/fixture.cpp']
        with self.assertRaisesRegex(ValueError, 'cannot be excluded'):
            self.parse(value)

    def test_projection_pins_modes_directory_closure_and_unknown_fields_reject(self):
        mutations = (lambda value: value.update(extra=True),
                     lambda value: value['archives']['engine'].update(bytes=True),
                     lambda value: value['archives']['engine'].update(sha256='1' * 64),
                     lambda value: value['projection'].update(extra=True),
                     lambda value: value['projection'].update(directories=[]),
                     lambda value: value['projection']['files']['source/engine/CMakeLists.txt']
                     .update(mode=True),
                     lambda value: value['projection']['files']['source/engine/CMakeLists.txt']
                     .update(bytes=1),
                     lambda value: value['projection']['files']['source/engine/CMakeLists.txt']
                     .update(sha256='2' * 64),
                     lambda value: value['projection']['normalizations']['engine']
                     .update({'missing-link': 'CMakeLists.txt'}))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value = self.fixture()
                mutate(value)
                with self.assertRaises(ValueError):
                    self.parse(value)

    def test_archive_link_traversal_and_case_aliases_reject_before_extraction(self):
        for kind in ('traversal', 'absolute', 'symlink', 'hardlink', 'case-alias'):
            with self.subTest(kind=kind):
                value = self.fixture()
                stream = io.BytesIO()
                with tarfile.open(fileobj=stream, mode='w:gz') as archive:
                    name = ('../escape' if kind == 'traversal' else
                            '/absolute' if kind == 'absolute' else 'engine/CMakeLists.txt')
                    info = tarfile.TarInfo(name)
                    info.mode = 0o644
                    if kind in ('symlink', 'hardlink'):
                        info.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
                        info.linkname = '../../outside'
                        archive.addfile(info)
                    else:
                        body = b'inert unsafe fixture\n'
                        info.size = len(body)
                        archive.addfile(info, io.BytesIO(body))
                        if kind == 'case-alias':
                            second = tarfile.TarInfo('engine/cmakelists.txt')
                            second.size = len(body)
                            second.mode = 0o644
                            archive.addfile(second, io.BytesIO(body))
                raw = stream.getvalue()
                archive = self.f.file('archives/engine.tar.gz', raw)
                value['archives']['engine'].update(sha256=digest(raw), bytes=len(raw))
                with self.assertRaises(ValueError):
                    self.parse(value)
                self.assertFalse((self.f.root / 'escape').exists())

    def test_projection_provenance_roles_are_complete_ordered_unique_and_byte_pinned(self):
        mutations = (lambda value: value.pop('provenance'),
                     lambda value: value.update(provenance=[]),
                     lambda value: value['provenance'].pop(),
                     lambda value: value['provenance'].reverse(),
                     lambda value: value['provenance'].append(copy.deepcopy(value['provenance'][0])),
                     lambda value: value['provenance'][0].update(role='unreviewed-proof'),
                     lambda value: value['provenance'][0].update(bytes=True),
                     lambda value: value['provenance'][0].update(bytes=1),
                     lambda value: value['provenance'][0].update(sha256='1' * 64),
                     lambda value: value['provenance'][0].update(path='../outside.txt'),
                     lambda value: value['provenance'][0].update(extra='not-admitted'))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value = self.fixture()
                mutate(value)
                with self.assertRaises(ValueError):
                    self.parse(value)

    def test_lower_projection_provenance_capture_does_not_claim_semantic_verification(self):
        value = self.fixture()
        inputs = self.api.InputSet()
        with no_programs():
            result = self.api.parse_source_projection(value, self.f.root, inputs, TARGET)
            inputs.recheck()
        self.assertEqual([item['role'] for item in result['provenance']],
                         list(SOURCE_PROVENANCE_ROLES))
        captured = {record['path']: record for record in inputs.records}
        for item in value['provenance']:
            record = captured[str(self.f.root / item['path'])]
            self.assertEqual(record['sha256'], item['sha256'])
            self.assertEqual(record['bytes'], item['bytes'])
        self.assertNotIn('production_eligible', result)
        self.assertNotIn('native_build', result)


class NativeSourceProvenance(unittest.TestCase):
    """SYNTHETIC eight-link records test joins, never original source proof."""

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-provenance-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    @staticmethod
    def git_blob(raw):
        return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()

    @staticmethod
    def git_z(records):
        return b''.join((item['mode'] + ' ' + item['type'] + ' ' + item['oid'] + '\t' + name)
                        .encode('utf-8') + b'\0' for name, item in sorted(records.items()))

    def fixture(self, mutate=None, extra_regulars=None):
        value = NativeSupplierProjection.fixture(self)
        engine_path = self.f.root / value['archives']['engine']['path']
        with tarfile.open(engine_path, 'r:gz') as archive:
            bodies = {member.name[len('engine/'):]: archive.extractfile(member).read()
                      for member in archive if member.isfile()}
        for literal, target in SYNTHETIC_LINK_LITERALS.values():
            bodies[target] = ('SYNTHETIC regular body: ' + target + '\n').encode('utf-8')
        bodies.update(extra_regulars or {})
        selected = {name: {'mode': '100644', 'type': 'blob', 'oid': self.git_blob(raw)}
                    for name, raw in bodies.items()}
        normalizations, metadata_links = {}, {}
        for name, (literal, target) in SYNTHETIC_LINK_LITERALS.items():
            oid = self.git_blob(literal.encode('utf-8'))
            selected[name] = {'mode': '120000', 'type': 'blob', 'oid': oid}
            normalizations[name] = {'literal': literal, 'git_blob_sha1': oid,
                                    'target': target,
                                    'target_git_blob_sha1': selected[target]['oid'],
                                    'target_sha256': digest(bodies[target])}
            metadata_links[name] = {'mode': '120000', 'type': 'blob', 'oid': oid,
                                    'literal': literal, 'literal_git_blob_verified': True}
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for name in sorted(selected):
                info = tarfile.TarInfo('engine/' + name)
                info.mode = 0o644
                info.mtime = 0
                if name in normalizations:
                    info.type = tarfile.SYMTYPE
                    info.linkname = normalizations[name]['literal']
                    archive.addfile(info)
                else:
                    info.size = len(bodies[name])
                    archive.addfile(info, io.BytesIO(bodies[name]))
        engine_raw = stream.getvalue()
        engine_path.write_bytes(engine_raw)
        archive_sha = digest(engine_raw)
        value['archives']['engine'].update(sha256=archive_sha, bytes=len(engine_raw))
        projected = {name: item for name, item in value['projection']['files'].items()
                     if not name.startswith('source/engine/')}
        files = {}
        for name, original in selected.items():
            raw = bodies[normalizations[name]['target']] if name in normalizations else bodies[name]
            facts = {'sha256': digest(raw), 'bytes': len(raw), 'mode': 0o644}
            files[name] = dict(facts, git_blob_sha1=original['oid'])
            projected['source/engine/' + name] = dict(facts, archive='engine', member=name)
        value['projection']['files'] = projected
        parents = {parent.as_posix() for name in projected for parent in Path(name).parents
                   if parent != Path('.')}
        value['projection']['directories'] = sorted(parents)
        value['projection']['normalizations']['engine'] = {
            name: item['target'] for name, item in normalizations.items()}
        top = {'CMakeLists.txt': selected['CMakeLists.txt'],
               'Source': {'mode': '040000', 'type': 'tree', 'oid': '1' * 40},
               'Tools': {'mode': '040000', 'type': 'tree', 'oid': '2' * 40}}
        selected_raw, top_raw = self.git_z(selected), self.git_z(top)
        source = str(self.f.root / 'SYNTHETIC-original-source-not-a-Git-checkout')
        controls = {'commit': self.api.ENGINE_COMMIT, 'source': source,
                    'fixture_only': 'SYNTHETIC unit records, never original provenance'}
        receipt = {'schema_version': 1, 'scope': 'offline-original-Git-tree-metadata-only',
                   'commit': self.api.ENGINE_COMMIT, 'root': source,
                   'selected_sha256': digest(selected_raw), 'top_sha256': digest(top_raw),
                   'git_captured_output_bytes': len(selected_raw) + len(top_raw),
                   'original_entries': len(selected), 'source_tools_original': len(selected) - 1,
                   'root_blobs': {'CMakeLists.txt': {'original': selected['CMakeLists.txt']}},
                   'top_tree': top, 'links_before_normalization': metadata_links,
                   'passed': True, 'native_build': False, 'source_archive_created': False,
                   'regular_body_hashes_verified': False,
                   'fixture_only': 'SYNTHETIC unit records, never original provenance'}
        inventory = {'schema_version': 1, 'kind': 'foundation-native-engine-clean-members-v1',
                     'commit': self.api.ENGINE_COMMIT, 'archive_sha256': archive_sha,
                     'files': files, 'normalizations': normalizations}
        raw_records = {'git-controls': encoded(controls), 'git-selected-tree': selected_raw,
                       'git-top-tree': top_raw, 'git-tree-receipt': encoded(receipt)}
        body = {'schema_version': 1, 'kind': 'foundation-native-engine-clean-source-body-v1',
                'scope': 'original-git-blob-and-clean-archive-source-consistency-only',
                'commit': self.api.ENGINE_COMMIT, 'baseline': 'clean-original-commit',
                'archive_sha256': archive_sha,
                'member_inventory_sha256': digest(encoded(inventory)),
                'git_inputs': {role: digest(raw) for role, raw in raw_records.items()},
                'supplier_patch_sha256': self.api.SUPPLIER_PATCH,
                'normalizations': copy.deepcopy(normalizations),
                'regular_blobs_verified': len(files) - 8, 'link_blobs_verified': 8,
                'source_bytes': sum(item['bytes'] for item in files.values()),
                'production_eligible': False, 'native_build': False}
        facts = {'controls': controls, 'receipt': receipt, 'inventory': inventory, 'body': body}
        if mutate is not None:
            mutate(facts)
        raw_records.update({'git-controls': encoded(facts['controls']),
                            'git-tree-receipt': encoded(facts['receipt']),
                            'engine-member-inventory': encoded(facts['inventory']),
                            'engine-body-verification': encoded(facts['body'])})
        value['provenance'] = []
        for role in SOURCE_PROVENANCE_ROLES:
            raw = raw_records[role]
            path = self.f.file('provenance/' + role + '.SYNTHETIC', raw)
            value['provenance'].append({'role': role,
                'path': path.relative_to(self.f.root).as_posix(), 'sha256': digest(raw), 'bytes': len(raw)})
        inputs = self.api.InputSet()
        with no_programs():
            projection = self.api.parse_source_projection(value, self.f.root, inputs, TARGET)
        return projection, inputs, facts

    def test_synthetic_eight_link_records_join_without_native_or_body_execution_claim(self):
        projection, inputs, facts = self.fixture()
        with no_programs():
            summary = self.api.validate_source_provenance(projection, inputs)
            inputs.recheck()
        self.assertEqual(summary['scope'], 'retained-source-provenance-record-consistency-only')
        self.assertEqual(summary['normalized_links'], 8)
        self.assertEqual(summary['regular_blobs'], len(facts['inventory']['files']) - 8)
        self.assertEqual(summary['source_bytes'], facts['body']['source_bytes'])
        self.assertFalse(summary['production_eligible'])
        self.assertFalse(summary['native_build'])
        self.assertFalse(facts['receipt']['regular_body_hashes_verified'])
        self.assertNotIn('final_projection_sha256', facts['body'])

    def test_metadata_only_flags_raw_hashes_counts_and_body_receipt_fields_are_not_relabelled(self):
        mutations = (lambda facts: facts['receipt'].update(regular_body_hashes_verified=True),
                     lambda facts: facts['receipt'].update(native_build=True),
                     lambda facts: facts['receipt'].update(source_archive_created=True),
                     lambda facts: facts['receipt'].update(selected_sha256='1' * 64),
                     lambda facts: facts['receipt'].update(git_captured_output_bytes=1),
                     lambda facts: facts['receipt'].update(source_tools_original=1),
                     lambda facts: facts['receipt'].pop('top_tree'),
                     lambda facts: facts['body'].update(regular_blobs_verified=True),
                     lambda facts: facts['body'].update(source_bytes=0),
                     lambda facts: facts['body'].update(production_eligible=True),
                     lambda facts: facts['body'].update(native_build=True),
                     lambda facts: facts['body'].update(supplier_patch_sha256='2' * 64),
                     lambda facts: facts['body'].update(member_inventory_sha256='3' * 64),
                     lambda facts: facts['body']['git_inputs'].update({'git-controls': '4' * 64}))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                projection, inputs, facts = self.fixture(mutate)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.validate_source_provenance(projection, inputs)

    def test_exact_member_oid_target_and_literal_joins_reject_resealed_inventories(self):
        link = sorted(SYNTHETIC_LINK_LITERALS)[0]
        target = SYNTHETIC_LINK_LITERALS[link][1]
        mutations = (lambda facts: facts['inventory']['files'][link].update(git_blob_sha1='1' * 40),
                     lambda facts: facts['inventory']['files'][target].update(sha256='2' * 64),
                     lambda facts: facts['inventory']['normalizations'][link].update(target_git_blob_sha1='3' * 40),
                     lambda facts: facts['inventory']['normalizations'][link].update(target_sha256='4' * 64),
                     lambda facts: facts['inventory']['normalizations'][link].update(literal='unreviewed-link-target'),
                     lambda facts: facts['inventory']['files'].pop(target))
        for index, mutate in enumerate(mutations):
            def resealed(facts):
                mutate(facts)
                facts['body']['normalizations'] = copy.deepcopy(facts['inventory']['normalizations'])
                facts['body']['member_inventory_sha256'] = digest(encoded(facts['inventory']))
            with self.subTest(index=index):
                projection, inputs, facts = self.fixture(resealed)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.validate_source_provenance(projection, inputs)


class NativeToolInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-tools-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def fixture(self):
        compiler = {'family': 'gcc', 'version': '14.2.0', 'frontend': 'gcc',
                    'triple': TARGET['triple']}
        runtime = {'c_library': 'glibc', 'c_library_baseline': '2.36',
                   'cxx_library': 'libstdc++', 'cxx_library_baseline': '3.4.30',
                   'linkage': 'private-native', 'sysroot_inventory': 'toolchain',
                   'needed_libraries': ['libc.so.6', 'libm.so.6']}
        cpu = {'baseline': 'sse2', 'source_dispatch': 'supplier-per-source-reviewed'}
        original = {'schema_version': 1, 'kind': 'foundation-native-toolchain-identity-v1',
                    'target': copy.deepcopy(TARGET), 'compiler': compiler,
                    'runtime': runtime, 'cpu': cpu}
        members = {'identity.json': (encoded(original), 0o644),
                   'native-toolchain.cmake': (b'# Synthetic fixture; never configure.\n', 0o644),
                   'include/fixture.h': (b'/* Inert fixture; no SDK claim. */\n', 0o644)}
        names = ('c', 'cxx', 'linker', 'archiver', 'ranlib', 'inspect', 'cmake',
                 'ninja', 'pkg_config')
        versions = {name: '14.2.0' for name in names}
        versions.update(cmake='3.31.6', ninja='1.12.1', pkg_config='1.8.1')
        for name in names:
            members['bin/' + name] = (b'#!/bin/sh\n# Inert ' + name.encode()
                                      + b' fixture; must not run.\nexit 99\n', 0o755)
        inventory = self.f.inventory('tools', 'toolchain', members)
        programs = {name: {'path': str(self.f.root / 'toolchain/bin' / name),
                           'sha256': digest(members['bin/' + name][0]),
                           'version': versions[name]} for name in names}
        value = {'schema_version': 1,
                 'kind': 'foundation-native-engine-prototype-toolchain-v1',
                 'target': copy.deepcopy(TARGET), 'engine_cxx_standard': 23,
                 'identity': {'cxx_standard': 23, 'identity_sha256': digest(encoded(original)),
                              'runtime_policy': 'private-native', 'paired_sdk_sha256': None,
                              'target_baseline': 'synthetic-unit-fixture-not-an-SDK'},
                 'tools': programs, 'inventories': {'toolchain': inventory},
                 'compiler': compiler, 'runtime': runtime, 'cpu': cpu,
                 'environment': {'PATH': str(self.f.root / 'toolchain/bin'),
                                 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
                                 'SOURCE_DATE_EPOCH': '0'}}
        return value

    def parse(self, value, inputs=None):
        with no_programs():
            return self.api.parse_toolchain(value, self.f.root,
                                            inputs or self.api.InputSet(), TARGET)

    def host_fixture(self, toolchain):
        versions = {'python': '3.11.0', 'perl': '5.36.0', 'ruby': '3.1.2',
                    'gperf': '3.1.0', 'sh': '1.0.0'}
        inert_program = b'#!/bin/sh\n# Inert host fixture.\nexit 99\n'
        modules = {
            'python': {'lib/json/__init__.py': b'# Synthetic Python runtime fixture\n',
                       'lib/hashlib.py': b'# Synthetic Python runtime fixture\n',
                       'lib/pathlib.py': b'# Synthetic Python runtime fixture\n'},
            'ruby': {'lib/fileutils.rb': b'# Synthetic Ruby runtime fixture\n',
                     'lib/json.rb': b'# Synthetic Ruby runtime fixture\n'},
            'perl': {'lib/English.pm': b'# Synthetic Perl runtime fixture\n',
                     'lib/FindBin.pm': b'# Synthetic Perl runtime fixture\n',
                     'lib/JSON/PP.pm': b'# Synthetic Perl runtime fixture\n'}}
        programs, inventories = {}, {}
        for interpreter, leaves in modules.items():
            root_relative = 'host/' + interpreter
            root = self.f.root / root_relative
            members = {name: (raw, 0o644) for name, raw in leaves.items()}
            members['bin/' + interpreter] = (inert_program, 0o755)
            runtime = {'schema_version': 1,
                       'kind': 'foundation-native-host-interpreter-runtime-v1',
                       'program_sha256': digest(inert_program),
                       'search_paths': [str(root / 'lib')],
                       'runtime_inventories': ['host-' + interpreter]}
            members['interpreter-runtime.json'] = (encoded(runtime), 0o644)
            if interpreter == 'perl':
                for name in ('gperf', 'sh'):
                    members['bin/' + name] = (inert_program, 0o755)
                    programs[name] = {'path': str(root / 'bin' / name),
                                      'sha256': digest(inert_program),
                                      'version': versions[name]}
            inventories[interpreter] = self.f.inventory('host-' + interpreter,
                                                        root_relative, members)
            programs[interpreter] = {'path': str(root / 'bin' / interpreter),
                                     'sha256': digest(inert_program),
                                     'version': versions[interpreter]}
        programs.update({name: copy.deepcopy(toolchain['tools'][name])
                         for name in ('cmake', 'ninja')})
        return {'schema_version': 1,
                'kind': 'foundation-native-engine-prototype-host-tools-v1',
                'programs': programs, 'module_inventories': inventories}

    def test_lower_toolchain_parser_binds_explicit_inventory_without_execution(self):
        value = self.fixture()
        inputs = self.api.InputSet()
        result = self.parse(value, inputs)
        with no_programs():
            inputs.recheck()
        self.assertEqual(result['compiler'], value['compiler'])
        self.assertEqual(result['cpu'], value['cpu'])
        self.assertEqual(result['runtime'], value['runtime'])
        self.assertEqual(result['tools'], value['tools'])
        self.assertEqual(Path(result['toolchain_file']),
                         self.f.root / 'toolchain/native-toolchain.cmake')
        self.assertNotIn('production_eligible', result)

    def test_toolchain_rejects_ambient_flags_target_runtime_and_missing_roles(self):
        mutations = (lambda value: value.update(extra=True),
                     lambda value: value.update(engine_cxx_standard=True),
                     lambda value: value.update(engine_cxx_standard=20),
                     lambda value: value['target'].update(system='Emscripten'),
                     lambda value: value['compiler'].update(family='clang'),
                     lambda value: value['compiler'].update(version='12.1.0'),
                     lambda value: value['identity'].update(runtime_policy='emscripten'),
                     lambda value: value['runtime'].update(sysroot_inventory='missing'),
                     lambda value: value['runtime'].update(c_library_baseline='ambient'),
                     lambda value: value['runtime'].update(linkage='shared-host-default'),
                     lambda value: value['runtime'].update(needed_libraries=['/usr/lib/libc.so.6']),
                     lambda value: value['cpu'].update(baseline='native'),
                     lambda value: value['environment'].update(CXXFLAGS='-march=native'),
                     lambda value: value['environment'].update(LANG='ambient'),
                     lambda value: value['tools'].pop('archiver'))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value = self.fixture()
                mutate(value)
                with self.assertRaises(ValueError):
                    self.parse(value)

    def test_program_pin_mode_inventory_membership_and_original_version_are_enforced(self):
        mutations = (lambda value: value['tools']['cxx'].update(sha256='1' * 64),
                     lambda value: value['tools']['cxx'].update(path='/usr/bin/unadmitted-g++'),
                     lambda value: value['tools']['cmake'].update(version='3.23.0'),
                     lambda value: value['identity'].update(identity_sha256='2' * 64))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value = self.fixture()
                mutate(value)
                with self.assertRaises(ValueError):
                    self.parse(value)
        value = self.fixture()
        (self.f.root / 'toolchain/bin/cxx').chmod(0o644)
        with self.assertRaises(ValueError):
            self.parse(value)

    def test_complete_inventory_rejects_extra_missing_changed_and_alias_entries(self):
        for mutation in ('extra', 'missing', 'changed', 'symlink'):
            with self.subTest(mutation=mutation):
                value = self.fixture()
                root = self.f.root / 'toolchain'
                if mutation == 'extra':
                    self.f.file('toolchain/unreviewed.txt', b'undeclared\n')
                elif mutation == 'missing':
                    (root / 'include/fixture.h').unlink()
                elif mutation == 'changed':
                    (root / 'include/fixture.h').write_bytes(b'changed\n')
                else:
                    (root / 'include/fixture.h').unlink()
                    (root / 'include/fixture.h').symlink_to(root / 'native-toolchain.cmake')
                with self.assertRaises(ValueError):
                    self.parse(value)
                # This test repeatedly rebuilds its own tiny fixture directory.
                if mutation == 'extra':
                    (root / 'unreviewed.txt').unlink()

    def test_lower_host_tools_bind_exact_cmake_ninja_and_required_perl_modules(self):
        inputs = self.api.InputSet()
        toolchain = self.parse(self.fixture(), inputs)
        host = self.host_fixture(toolchain)
        with no_programs():
            result = self.api.parse_host_tools(host, self.f.root, inputs, toolchain)
            inputs.recheck()
        self.assertEqual(result['programs'], host['programs'])
        self.assertIn('perl', result['module_inventories'])
        self.assertNotIn('production_eligible', result)

    def test_host_program_versions_roles_and_inventory_module_closure_are_enforced(self):
        mutations = (lambda value: value.update(extra=True),
                     lambda value: value['programs'].pop('gperf'),
                     lambda value: value['programs'].update(node=copy.deepcopy(value['programs']['python'])),
                     lambda value: value['programs']['python'].update(version='3.8.0'),
                     lambda value: value['programs']['perl'].update(version='5.8.0'),
                     lambda value: value['programs']['ruby'].update(version='2.4.0'),
                     lambda value: value['programs']['gperf'].update(version='3.0.0'),
                     lambda value: value['programs']['cmake'].update(version='3.24.0'),
                     lambda value: value['programs']['gperf'].update(path='/ambient/gperf'),
                     lambda value: value['module_inventories'].clear())
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                inputs = self.api.InputSet()
                toolchain = self.parse(self.fixture(), inputs)
                value = self.host_fixture(toolchain)
                mutate(value)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.parse_host_tools(value, self.f.root, inputs, toolchain)
        inputs = self.api.InputSet()
        toolchain = self.parse(self.fixture(), inputs)
        value = self.host_fixture(toolchain)
        (self.f.root / 'host/perl/lib/JSON/PP.pm').unlink()
        with no_programs(), self.assertRaises(ValueError):
            self.api.parse_host_tools(value, self.f.root, inputs, toolchain)


    def test_interpreter_runtime_facts_require_own_inventory_and_contained_search(self):
        mutations = (lambda value: value.update(extra=True),
                     lambda value: value.update(schema_version=True),
                     lambda value: value.update(program_sha256='1' * 64),
                     lambda value: value.update(runtime_inventories=[]),
                     lambda value: value.update(runtime_inventories=['missing-inventory']),
                     lambda value: value.update(search_paths=[str(self.f.root / 'ambient')]))
        for interpreter in ('python', 'ruby', 'perl'):
            for index, mutate in enumerate(mutations):
                with self.subTest(interpreter=interpreter, index=index):
                    inputs = self.api.InputSet()
                    toolchain = self.parse(self.fixture(), inputs)
                    host = self.host_fixture(toolchain)
                    self.f.file('ambient/unlisted.txt', b'outside admitted roots\n')
                    runtime_path = self.f.root / 'host' / interpreter / 'interpreter-runtime.json'
                    facts = json.loads(runtime_path.read_text(encoding='utf-8'))
                    mutate(facts)
                    runtime_path.write_bytes(encoded(facts))
                    inventory_ref = host['module_inventories'][interpreter]['inventory']
                    inventory_path = self.f.root / inventory_ref['path']
                    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
                    inventory['files']['interpreter-runtime.json'] = digest(runtime_path.read_bytes())
                    inventory_path.write_bytes(encoded(inventory))
                    inventory_ref['sha256'] = digest(inventory_path.read_bytes())
                    with no_programs(), self.assertRaises(ValueError):
                        self.api.parse_host_tools(host, self.f.root, inputs, toolchain)

    def test_rendered_environment_uses_only_admitted_tool_and_interpreter_paths(self):
        inputs = self.api.InputSet()
        toolchain = self.parse(self.fixture(), inputs)
        host_value = self.host_fixture(toolchain)
        host = self.api.parse_host_tools(host_value, self.f.root, inputs, toolchain)
        paths = sorted({str(Path(item['path']).parent)
                        for item in list(toolchain['tools'].values())
                        + list(host['programs'].values())})
        toolchain['environment']['PATH'] = ':'.join(paths)
        with no_programs():
            environment = self.api.render_environment(toolchain, host)
        self.assertEqual(environment['PATH'], ':'.join(paths))
        for variable, interpreter in (('PYTHONPATH', 'python'), ('RUBYLIB', 'ruby'),
                                      ('PERL5LIB', 'perl')):
            self.assertEqual(environment[variable], str(self.f.root / 'host' / interpreter / 'lib'))
        toolchain['environment']['PATH'] += ':/ambient/bin'
        with no_programs(), self.assertRaises(ValueError):
            self.api.render_environment(toolchain, host)


class NativeDependencyInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-deps-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def fixture(self):
        inputs = self.api.InputSet()
        tool_value = NativeToolInventory.fixture(self)
        toolchain = self.api.parse_toolchain(tool_value, self.f.root, inputs, TARGET)
        assets_value = NativeExplicitAssets.fixture(self)
        assets = self.f.document('assets.json', assets_value)
        selected_assets = {'path': str(self.f.root / 'assets.json'),
                           'sha256': assets['sha256']}
        notice_raw = b'Synthetic dependency notice; no real build/license claim.\n'
        notice_path = self.f.file('NOTICES/dependency-fixture.txt', notice_raw)
        notice = {'path': notice_path.relative_to(self.f.root).as_posix(),
                  'sha256': digest(notice_raw)}
        log_raw = b'Synthetic unit fixture log, not actual executed inspection.\n'
        self.f.file('inspection/logs/inspection.txt', log_raw)
        log = {'path': 'logs/inspection.txt', 'sha256': digest(log_raw)}
        provenance = self.f.document('provenance/dependency-fixture.json',
                                    {'kind': 'synthetic-unit-fixture-not-a-build',
                                     'production_eligible': False, 'engine_execution': False})
        members = {'include/fixture.h': (b'/* Synthetic static-input header. */\n', 0o644),
                   'lib/pkgconfig/fixture.pc': (b'Name: synthetic-input-fixture\n', 0o644)}
        libraries = {}
        for index, name in enumerate(sorted(self.api.LIBRARIES)):
            relative = 'lib/fixture-' + str(index) + '.a'
            raw = static_archive([('fixture.o', elf_object())])
            members[relative] = (raw, 0o644)
            inspected = {'schema_version': 1,
                         'kind': 'foundation-native-dependency-archive-inspection-v1',
                         'target': copy.deepcopy(TARGET),
                         'toolchain_identity_sha256': toolchain['identity']['identity_sha256'],
                         'archive_sha256': digest(raw), 'format': 'elf64-x86_64-ar',
                         'pic': True, 'runtime': copy.deepcopy(toolchain['runtime']),
                         'commands': [{'tool_sha256': toolchain['tools']['inspect']['sha256'],
                                       'argv': [toolchain['tools']['inspect']['path'], '-r',
                                                str(self.f.root / 'dependencies' / relative)],
                                       'exit_code': 0, 'log': copy.deepcopy(log)}]}
            inspection_ref = self.f.document('inspection/library-' + str(index) + '.json',
                                              inspected)
            libraries[name] = {'archive': relative, 'sha256': digest(raw),
                               'includes': ['include'],
                               'definitions': ['SYNTHETIC_FORMAT_FIXTURE=1'],
                               'links': ['WebP::sharpyuv'] if name == 'WebP::libwebp' else [],
                               'inspection': inspection_ref}
        inventory = self.f.inventory('dependencies', 'dependencies', members)
        value = {'schema_version': 1,
                 'kind': 'foundation-native-engine-prototype-dependencies-v1',
                 'target': copy.deepcopy(TARGET),
                 'toolchain_identity_sha256': toolchain['identity']['identity_sha256'],
                 'prefix': inventory['root'], 'inventory': inventory['inventory'],
                 'build_provenance': [provenance], 'libraries': libraries,
                 'pkg_config': {'directories': ['lib/pkgconfig'],
                                'files': {'lib/pkgconfig/fixture.pc':
                                          digest(members['lib/pkgconfig/fixture.pc'][0])}},
                 'assets': assets, 'notices': [notice], 'windows_inputs': None}
        return value, inputs, toolchain, selected_assets

    def parse(self, value, inputs, toolchain, assets):
        with no_programs():
            return self.api.parse_dependencies(value, self.f.root, inputs, TARGET,
                                               toolchain, assets)

    def test_lower_dependency_format_admission_retains_explicit_fixture_limits(self):
        value, inputs, toolchain, assets = self.fixture()
        result = self.parse(value, inputs, toolchain, assets)
        with no_programs():
            inputs.recheck()
        self.assertEqual(set(result['libraries']), set(self.api.LIBRARIES))
        first = sorted(value['libraries'])[0]
        self.assertEqual(Path(result['libraries'][first]['archive']),
                         Path(value['prefix']) / value['libraries'][first]['archive'])
        self.assertEqual(result['libraries'][first]['links'], [])
        self.assertNotIn('production_eligible', result)
        self.assertNotIn('engine_execution', result)

    def test_dependency_required_roles_transitive_links_pkg_config_and_asset_pin_reject(self):
        mutations = (lambda value: value.update(extra=True),
                     lambda value: value.update(toolchain_identity_sha256='1' * 64),
                     lambda value: value['libraries'].pop('ICU::uc'),
                     lambda value: value['libraries'].update({'Unknown::archive':
                         copy.deepcopy(value['libraries']['ICU::uc'])}),
                     lambda value: value['libraries']['ICU::uc'].update(links=['Unadmitted::library']),
                     lambda value: value['libraries']['WebP::libwebp'].update(links=[]),
                     lambda value: value['libraries']['ICU::uc'].update(includes=['../outside']),
                     lambda value: value['libraries']['ICU::uc'].update(definitions=['-march=native']),
                     lambda value: value['pkg_config'].update(directories=['/usr/lib/pkgconfig']),
                     lambda value: value['pkg_config']['files'].update({'../ambient.pc': '2' * 64}),
                     lambda value: value['assets'].update(sha256='3' * 64),
                     lambda value: value.update(notices=[]),
                     lambda value: value.update(build_provenance=[]),
                     lambda value: value.update(windows_inputs={'path': 'missing.json', 'sha256': '4' * 64}))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value, inputs, toolchain, assets = self.fixture()
                mutate(value)
                with self.assertRaises(ValueError):
                    self.parse(value, inputs, toolchain, assets)


    def test_declared_inspection_failure_wrong_target_and_boolean_substitutions_reject(self):
        mutations = (lambda value: value.update(pic=False),
                     lambda value: value.update(pic=1),
                     lambda value: value['target'].update(processor='aarch64'),
                     lambda value: value.update(archive_sha256='1' * 64),
                     lambda value: value.update(format='wasm32-ar'),
                     lambda value: value['commands'][0].update(exit_code=1),
                     lambda value: value['commands'][0].update(exit_code=False),
                     lambda value: value['commands'][0].update(tool_sha256='2' * 64),
                     lambda value: value.update(commands=[]))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value, inputs, toolchain, assets = self.fixture()
                name = sorted(value['libraries'])[0]
                ref = value['libraries'][name]['inspection']
                path = self.f.root / ref['path']
                inspected = json.loads(path.read_text(encoding='utf-8'))
                mutate(inspected)
                path.write_bytes(encoded(inspected))
                ref['sha256'] = digest(path.read_bytes())
                with self.assertRaises(ValueError):
                    self.parse(value, inputs, toolchain, assets)


class NativeSelectionFailures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-selection-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def fixture(self):
        value = {'schema_version': 1,
                 'kind': 'foundation-native-engine-prototype-selection-v1',
                 'target': copy.deepcopy(TARGET), 'profile': 'document-actions-v1',
                 'phase_limits': {'prepare_seconds': 60, 'configure_seconds': 120,
                                  'build_seconds': 600, 'cleanup_seconds': 30,
                                  'maximum_jobs': 2, 'maximum_output_bytes': 1048576,
                                  'minimum_free_bytes': 1073741824,
                                  'maximum_process_tree_bytes': 17179869184}}
        for role in ('source_map', 'source_projection', 'toolchain', 'dependencies',
                     'host_tools', 'assets'):
            value[role] = {'path': 'absent-' + role + '.json', 'sha256': '1' * 64}
        return value

    def inspect(self, raw, pin=None):
        path = self.f.file('selection.json', raw)
        with no_programs():
            return self.api.inspect_selection(path, pin or digest(raw),
                                               repository_root=self.f.root)

    def test_all_six_missing_manifests_report_before_source_profile_access(self):
        value = self.fixture()
        with self.assertRaises(self.api.MissingInputs) as caught:
            self.inspect(encoded(value))
        error = caught.exception
        roles = {role + '-manifest' for role in ('source_map', 'source_projection',
                 'toolchain', 'dependencies', 'host_tools', 'assets')}
        self.assertEqual(set(error.roles), roles)
        diagnostic = error.as_dict()
        self.assertFalse(diagnostic['executable_plan'])
        self.assertFalse(diagnostic['production_eligible'])
        self.assertEqual(len(diagnostic['missing']), 6)
        self.assertEqual(sorted(path.name for path in self.f.root.iterdir()),
                         ['selection.json'])

    def test_selection_rejects_wrong_pin_and_duplicate_json_before_any_missing_plan(self):
        raw = encoded(self.fixture())
        with self.assertRaises(ValueError) as caught:
            self.inspect(raw, pin='2' * 64)
        self.assertNotIsInstance(caught.exception, self.api.MissingInputs)
        duplicate = raw.replace(b'"schema_version":1',
                                b'"schema_version":1,"schema_version":1')
        with self.assertRaises(ValueError) as caught:
            self.inspect(duplicate)
        self.assertNotIsInstance(caught.exception, self.api.MissingInputs)

    def test_selection_unknown_boolean_bad_profile_and_path_escape_fail_closed(self):
        mutations = (lambda value: value.update(extra=True),
                     lambda value: value.update(schema_version=True),
                     lambda value: value.update(profile='pixel'),
                     lambda value: value['phase_limits'].update(maximum_jobs=True),
                     lambda value: value['source_map'].update(path='../outside.json'),
                     lambda value: value['source_map'].update(path='/outside.json'),
                     lambda value: value['source_map'].update(sha256='0' * 64))
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                value = self.fixture()
                mutate(value)
                with self.assertRaises(ValueError) as caught:
                    self.inspect(encoded(value))
                self.assertNotIsInstance(caught.exception, self.api.MissingInputs)

    def test_windows_selection_reports_specific_unfinished_host_join(self):
        value = self.fixture()
        value['target'] = {'system': 'Windows', 'processor': 'x86_64',
                           'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
        with self.assertRaisesRegex(ValueError, 'two-host|publication'):
            self.inspect(encoded(value))


class NativeExternalCopiedMap(unittest.TestCase):
    """Held real source-map checks stop before any native input admission."""

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-copied-map-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def fixture(self, raw_map=None, map_pin=None):
        profile = json.loads((ROOT / self.api.PROFILE).read_text(encoding='utf-8'))
        canonical_map = ROOT / profile['source_map']['path']
        canonical_raw = canonical_map.read_bytes()
        self.assertEqual(digest(canonical_raw), profile['source_map']['sha256'])
        value = NativeSelectionFailures.fixture(self)
        raw = canonical_raw if raw_map is None else raw_map
        copied = self.f.file('manifests/copied-source-map.json', raw)
        value['source_map'] = {'path': copied.relative_to(self.f.root).as_posix(),
                               'sha256': digest(raw) if map_pin is None else map_pin}
        for role in ('source_projection', 'toolchain', 'dependencies', 'host_tools', 'assets'):
            value[role] = self.f.document('manifests/' + role + '.json',
                {'kind': self.api.PRIVATE_TOOLCHAIN_KIND} if role == 'toolchain' else {})
        selection = self.f.file('selection.json', encoded(value))
        return selection, value, copied, canonical_map

    def test_exact_external_map_advances_only_to_next_parser_and_captures_canonical_map(self):
        selection, value, copied, canonical = self.fixture()

        class ReachedNextParser(RuntimeError):
            pass

        with mock.patch.object(self.api, 'parse_toolchain',
                               side_effect=ReachedNextParser('static source checks reached next parser')) as next_parser:
            with no_programs(), self.assertRaisesRegex(ReachedNextParser, 'static source checks'):
                self.api.inspect_selection(selection, digest(selection.read_bytes()),
                                           repository_root=ROOT)
        next_parser.assert_called_once()
        self.assertEqual(next_parser.call_args.args[0], {'kind': self.api.PRIVATE_TOOLCHAIN_KIND})
        self.assertEqual(next_parser.call_args.kwargs['repository_root'], ROOT)
        captured = {record['path']: record for record in next_parser.call_args.args[2].records}
        self.assertIn(str(copied), captured)
        self.assertIn(str(canonical), captured)
        self.assertEqual(captured[str(copied)]['sha256'], value['source_map']['sha256'])
        self.assertEqual(captured[str(canonical)]['sha256'], value['source_map']['sha256'])
        self.assertIn('canonical-native-source-map', captured[str(canonical)]['roles'])
        self.assertFalse((self.f.root / 'retained').exists())
        self.assertFalse((self.f.root / 'plan.json').exists())

    def test_different_external_map_bytes_or_wrong_pin_never_reach_next_parser(self):
        for mutation in ('different-content-with-own-pin', 'wrong-independent-pin'):
            with self.subTest(mutation=mutation):
                selection, value, copied, canonical = self.fixture()
                if mutation == 'different-content-with-own-pin':
                    changed = json.loads(copied.read_text(encoding='utf-8'))
                    changed['synthetic_changed_map'] = 'This is not the canonical source identity.'
                    copied.write_bytes(encoded(changed))
                    value['source_map']['sha256'] = digest(copied.read_bytes())
                else:
                    value['source_map']['sha256'] = '1' * 64
                selection.write_bytes(encoded(value))
                with mock.patch.object(self.api, 'parse_toolchain',
                                       side_effect=AssertionError('Noncanonical map reached next parser')) as next_parser:
                    with no_programs(), self.assertRaises(ValueError):
                        self.api.inspect_selection(selection, digest(selection.read_bytes()),
                                                   repository_root=ROOT)
                next_parser.assert_not_called()
                self.assertEqual(digest(canonical.read_bytes()),
                                 json.loads((ROOT / self.api.PROFILE).read_text(encoding='utf-8'))
                                 ['source_map']['sha256'])


class NativeSourcePreparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-prepare-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def test_real_projection_copy_patch_and_final_overlay_order(self):
        value = NativeSupplierProjection.fixture(self)
        before = b'// Inert complete-projection member.\n'
        patched = b'// Exact supplier patch fixture.\n'
        final = b'// Final recipe overlay fixture, never compiled.\n'
        patch = (b'--- a/Source/fixture.cpp\n+++ b/Source/fixture.cpp\n'
                 b'@@ -1 +1 @@\n-// Inert complete-projection member.\n'
                 b'+// Exact supplier patch fixture.\n')
        self.f.file('patches/source.patch', patch)
        value['patches'] = [{'path': 'patches/source.patch', 'sha256': digest(patch),
                             'tree': 'engine',
                             'preimages': {'Source/fixture.cpp': digest(before)},
                             'postimages': {'Source/fixture.cpp': digest(patched)}}]
        inputs = self.api.InputSet()
        with no_programs():
            projection = self.api.parse_source_projection(value, self.f.root, inputs, TARGET)
        overlay = self.f.file('overlay/fixture.cpp', final)
        inputs.file(overlay, digest(final), 'synthetic-overlay')
        inspection = types.SimpleNamespace(_inputs=inputs, _projection=projection,
                                           _overlays={'source/engine/Source/fixture.cpp': overlay})
        assembled = self.f.root / 'assembled'
        assembled.mkdir(mode=0o700)
        archive_before = {key: Path(item['path']).read_bytes()
                          for key, item in projection['archives'].items()}
        with no_programs():
            self.api._project_sources(inspection, assembled)
            inputs.recheck()
        destination = assembled / 'source/engine/Source/fixture.cpp'
        self.assertEqual(destination.read_bytes(), final)
        self.assertEqual(overlay.read_bytes(), final)
        self.assertNotEqual(destination.stat().st_ino, overlay.stat().st_ino)
        self.assertEqual(destination.stat().st_nlink, 1)
        self.assertEqual((assembled / 'source/wrapper/README.md').read_bytes(),
                         b'Synthetic supplier fixture only.\n')
        for key, item in projection['archives'].items():
            self.assertEqual(Path(item['path']).read_bytes(), archive_before[key])

    def internal_inspection(self):
        """Construct INTERNAL test data, never an inspect_selection admission.

        This deliberately omits any actual supplier/SDK and tests only assemble's
        canonical R/S/B publication joins. It cannot be used as a runnable plan.
        """
        inputs = self.api.InputSet()
        toolchain = self.api.parse_toolchain(NativeToolInventory.fixture(self),
                                             self.f.root, inputs, TARGET)
        host_value = NativeToolInventory.host_fixture(self, toolchain)
        host = self.api.parse_host_tools(host_value, self.f.root, inputs, toolchain)
        toolchain['environment']['PATH'] = ':'.join(sorted({
            str(Path(item['path']).parent)
            for item in list(toolchain['tools'].values()) + list(host['programs'].values())}))
        retained = {}

        def retain(name, raw, role):
            original = self.f.file('retained-inputs/' + name, raw)
            fact = inputs.file(original, digest(raw), 'internal-assembly-fixture')
            retained[name] = {'path': str(original), 'sha256': fact['sha256'],
                              'mode': fact['mode'], 'role': role}
            return original

        for name in self.api.manifest.HELPERS:
            retain(name, (ROOT / name).read_bytes(), 'helper')
        header = 'include/foundation/appended/engine_provider.h'
        retain(header, (ROOT / header).read_bytes(), 'interface')
        retain('licenses/UNIT-NOTICE', b'Internal synthetic unit fixture only.\n', 'license')
        retain('supplier/wrapper.tar', b'Synthetic internal wrapper, not source admission.\n', 'source')
        retain('supplier/engine.tar', b'Synthetic internal engine, not source admission.\n', 'source')
        config = {'schema_version': 1,
                  'kind': 'foundation-native-provider-actions-prelink-config-v1',
                  'document_profile': self.api.actions.PROFILE_NAME, 'profile_kind': 4,
                  'provider_limits': dict(self.api.actions.PROVIDER_LIMITS),
                  'service_retention': {'max_retained_bytes': 4194304, 'max_retained_calls': 64}}
        retain('source/native/prelink-actions-config.json', encoded(config), 'config')
        binding = 'source/document-provider/runtime/BibNativeDocumentActionsBinding.cpp'
        bootstrap = 'source/native/BibNativeProviderBootstrap.hpp'
        overlays = {binding: retain(binding, b'// Internal fixture; never compiled.\n', 'source'),
                    bootstrap: retain(bootstrap, b'// Internal fixture; never compiled.\n', 'source')}
        retain('cmake/native-provider.cmake', b'# Internal fixture; never configure.\n', 'config')
        data = {'target': copy.deepcopy(TARGET), 'toolchain': toolchain, 'host_tools': host,
                'dependencies': {'prefix': str(self.f.root / 'internal-not-a-native-prefix')},
                'programs': {}, 'environment': self.api.render_environment(toolchain, host),
                'needed_libraries': [], 'phase_limits': {'prepare_seconds': 60},
                'fixture_only': True, 'production_eligible': False, 'engine_execution': False}
        suppliers = {name: {'repository': 'https://example.invalid/internal-fixture/' + name,
                             'commit': '1' * 40, 'archive': 'supplier/' + name + '.tar'}
                     for name in ('wrapper', 'engine')}
        return self.api.Inspection(data, inputs, retained,
                                   {'archives': {}, '_files': {}, 'patches': []},
                                   overlays, suppliers, [])

    def test_internal_fixture_publishes_deterministic_real_r_s_b_formats_only(self):
        inspection = self.internal_inspection()
        with no_programs():
            first = self.api.assemble(inspection, self.f.root / 'first')
            second = self.api.assemble(inspection, self.f.root / 'second')
        one, two = first.as_dict(), second.as_dict()
        for key in ('recipe_sha256', 'sources_sha256', 'provider_build_sha256'):
            self.assertEqual(one[key], two[key])
        retained = Path(one['retained_root'])
        recipe = json.loads((retained / 'recipe.json').read_text(encoding='utf-8'))
        sources = json.loads((retained / 'sources.json').read_text(encoding='utf-8'))
        build_path = Path(one['provider_build_path'])
        build = json.loads(build_path.read_text(encoding='utf-8'))
        self.assertEqual(len(build), 13)
        self.assertEqual(set(build), set(self.api.actions.BUILD_FIELDS))
        self.assertEqual(build['capabilities'], '4083')
        self.assertEqual(build['provider_limits'], dict(self.api.actions.PROVIDER_LIMITS))
        self.assertEqual(build['source_recipe_sha256'], digest((retained / 'recipe.json').read_bytes()))
        self.assertEqual(build['source_inputs_sha256'], digest(self.api.encoded(recipe['inputs'])))
        self.assertEqual(sources['recipe_id'], build['source_recipe_sha256'])
        self.assertNotIn(retained, build_path.parents)
        self.assertNotIn('provider-build.json', recipe['inputs'])
        self.assertFalse((retained / 'engine-sdk.json').exists())
        self.assertFalse((retained / 'generated').exists())
        self.assertFalse(inspection.as_dict()['production_eligible'])
        self.assertFalse(inspection.as_dict()['engine_execution'])

    def test_assembly_refuses_overwrite_and_changed_retained_input_before_output(self):
        inspection = self.internal_inspection()
        sentinel = self.f.file('occupied/keep.txt', b'preserve existing output\n')
        with no_programs(), self.assertRaises(ValueError):
            self.api.assemble(inspection, sentinel.parent)
        self.assertEqual(sentinel.read_bytes(), b'preserve existing output\n')
        config = Path(inspection._retained['source/native/prelink-actions-config.json']['path'])
        config.write_bytes(b'changed internal input\n')
        output = self.f.root / 'must-not-exist'
        with no_programs(), self.assertRaises(ValueError):
            self.api.assemble(inspection, output)
        self.assertFalse(output.exists())

    def test_assembly_honors_monotonic_preparation_deadline(self):
        inspection = self.internal_inspection()
        clock = iter((0.0, 1000.0))
        with mock.patch.object(self.api.time, 'monotonic', side_effect=lambda: next(clock, 1000.0)):
            with no_programs(), self.assertRaisesRegex(ValueError, 'deadline'):
                self.api.assemble(inspection, self.f.root / 'timed-out')

    def test_retained_alias_aggregate_is_bounded_before_any_output_creation(self):
        inspection = self.internal_inspection()
        sizes = {record['path']: record['bytes'] for record in inspection._inputs.records}
        captured_total = sum(sizes.values())
        maximum = captured_total + 1
        retained = inspection._retained
        alias_source = max(retained.values(), key=lambda item: sizes[item['path']])
        copied_total = sum(sizes[item['path']] for item in retained.values())
        index = 0
        while copied_total <= maximum:
            retained['internal-aliases/copy-' + str(index) + '.txt'] = dict(alias_source, role='data')
            copied_total += sizes[alias_source['path']]
            index += 1
        self.assertGreater(index, 0)
        self.assertLess(captured_total, maximum)
        self.assertGreater(copied_total, maximum)
        output = self.f.root / 'must-not-create-alias-output'
        with mock.patch.object(self.api, 'MAX_BYTES', maximum), \
                mock.patch.object(self.api, '_fresh_directory',
                                  side_effect=AssertionError('Alias overflow reached output creation')):
            with no_programs(), self.assertRaises(ValueError):
                self.api.assemble(inspection, output)
        self.assertFalse(output.exists())


class NativeRetainedOriginalEvidence(unittest.TestCase):
    """Entirely SYNTHETIC historical R/S/receipts; never original body proof."""

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    git_blob = staticmethod(NativeSourceProvenance.git_blob)
    git_z = staticmethod(NativeSourceProvenance.git_z)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-retained-proof-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)
        self.modified = {'Source/Proof/modified%02d.cpp' % index: ('pristine %d\n' % index).encode()
                         for index in range(45)}
        self.before = {name: digest(raw) for name, raw in self.modified.items()}
        self.after = {name: digest(('patched %d\n' % index).encode()) for index, name in enumerate(self.modified)}
        parts = []
        for index, name in enumerate(self.modified):
            parts.append(('diff --git a/{0} b/{0}\n--- a/{0}\n+++ b/{0}\n@@ -1 +1 @@\n-pristine {1}\n+patched {1}\n'
                          .format(name, index)).encode())
        for index in range(23):
            name = 'Source/Proof/added%02d.cpp' % index
            self.before[name] = None
            self.after[name] = digest(('added %d\n' % index).encode())
            parts.append(('diff --git a/{0} b/{0}\nnew file mode 100644\n--- /dev/null\n+++ b/{0}\n@@ -0,0 +1 @@\n+added {1}\n'
                          .format(name, index)).encode())
        self.patch_raw = b''.join(parts)
        patcher = mock.patch.object(self.api, 'SUPPLIER_PATCH', digest(self.patch_raw))
        patcher.start()
        self.addCleanup(patcher.stop)

    def fixture(self, mutate=None, mutate_sources=None, mutate_body=None):
        # Reuse only the synthetic lower source fixture; no ignored real files.
        projection, _, facts = NativeSourceProvenance.fixture(self, extra_regulars=self.modified)
        files, norms = facts['inventory']['files'], facts['inventory']['normalizations']
        generator = b'# SYNTHETIC historical generator bytes. Never execute.\n'
        entries = []
        for name, item in sorted(files.items()):
            common = {'path': name, 'git_oid': item['git_blob_sha1']}
            if name in norms:
                entries.append(dict(common, type='symlink', mode=0o777, git_mode='120000',
                                    target=norms[name]['literal'], target_sha256=digest(norms[name]['literal'].encode())))
            else:
                entries.append(dict(common, type='file', git_mode='100755' if item['mode'] == 0o755 else '100644',
                                    **{key: item[key] for key in ('mode', 'bytes', 'sha256')}))
        members = {'schema_version': 1, 'commit': self.api.ENGINE_COMMIT,
                   'scope': 'SYNTHETIC original selected member evidence; never actual proof',
                   'entries': entries, 'implicit_directories': sorted({p.as_posix() for name in files
                        for p in Path(name).parents if p.as_posix() != '.'}),
                   'safe_scoped_extractor_directory_mode': 0o755}
        raw_bytes = sum(item['bytes'] for item in entries if item['type'] == 'file')
        engine = projection['archives']['engine']
        command = ['git', '-c', 'protocol.allow=never', '-c', 'protocol.file.allow=never',
                   '-c', 'protocol.https.allow=never', '-c', 'protocol.http.allow=never',
                   '-C', str(self.f.root / 'historical-never-follow'), 'cat-file', '--batch']
        receipt = {key: True for key in ('all68postimage_hashes_unchanged',
            'all71104worktree_physical_identities_unchanged', 'all_archive_members_content_type_mode_and_order_verified',
            'all_network_protocols_forbidden', 'all_selected_parent_identities_unchanged',
            'no_lazy_fetch', 'no_sdk_engine_compiler_network_operation')}
        receipt.update(schema_version=1, status='passed-selected-pristine-source-archive-preparation',
            upstream_commit=self.api.ENGINE_COMMIT, archive='historical/archive.tar.gz', archive_sha256=engine['sha256'],
            archive_bytes=engine['bytes'], cap_seconds=180, creation_seconds=1.0, total_seconds=2.0,
            first_failure_receipt='../historical-failure.json', first_failure_receipt_sha256='1' * 64,
            generator_sha256=digest(generator), git_command=command, git_returncode=0, git_stderr_bytes=0,
            members=len(files), regular_files=len(files) - 8, symlinks=8, raw_pristine_regular_bytes=raw_bytes,
            supplier_added_paths_omitted=23, supplier_modified_preimages=45,
            source_authority='SYNTHETIC byte-consistency fixture only', symlink_policy='SYNTHETIC eight direct links',
            normalized_metadata={'compression_level': 1, 'file_modes': 'Git100644/100755 to0644/0755',
                'gid': 0, 'gname': '', 'gzip_filename': '', 'gzip_mtime': 0, 'mtime': 0,
                'symlink_mode': 0o777, 'tar_format': 'PAX', 'uid': 0, 'uname': ''})
        scope_links = []
        for name, item in sorted(norms.items()):
            record = {key: True for key in ('canonical_contained', 'canonical_target_regular',
                'canonical_target_selected', 'logical_target_selected', 'raw_target_matches_local_upstream_blob',
                'target_exists', 'target_is_relative')}
            record.update(path=name, raw_target=item['literal'], logical_target=item['target'],
                          canonical_target=item['target'], logical_target_git_mode='100644')
            scope_links.append(record)
        scope = {'schema_version': 1, 'kind': 'selected-upstream-source-scope-v1', 'commit': self.api.ENGINE_COMMIT,
                 'archive_sha256': engine['sha256'], 'members': len(files), 'regular_files': len(files) - 8,
                 'raw_regular_bytes': raw_bytes, 'source_bytes': 'SYNTHETIC original raw regular byte semantics',
                 'qualification': 'SYNTHETIC; never original engine/runtime proof', 'omitted_scope': ['unselected extras'],
                 'symlink_policy': 'SYNTHETIC eight direct links', 'symlinks': scope_links}
        patch = {'path': 'patches/supplier.patch', 'tree': 'engine',
                 'preimages': copy.deepcopy(self.before), 'postimages': copy.deepcopy(self.after)}
        images = {'schema_version': 1, 'status': 'actual-local-preimages-and-current-postimages-verified',
                  'upstream_commit': self.api.ENGINE_COMMIT, 'added_paths': 23, 'existing_modified_paths': 45,
                  'patch_paths': 68, 'recipe_patch': patch,
                  'supplier_patch': {'path': 'historical/supplier.patch', 'sha256': digest(self.patch_raw), 'bytes': len(self.patch_raw)},
                  'git_read': {'command': command, 'elapsed_seconds': 0.1, 'network_protocols': 'all forbidden',
                               'no_lazy_fetch': True, 'optional_locks': False, 'returncode': 0, 'stderr': ''}, 'files': []}
        for name in sorted(self.before):
            before = self.before[name]
            images['files'].append({'path': name, 'preimage_sha256': before, 'postimage_sha256': self.after[name],
                'preimage_bytes': len(self.modified[name]) if before is not None else None,
                'postimage_bytes': len(('patched ' if before else 'added ') + str(int(name[-6:-4])) + '\n'),
                'current_device': 1, 'current_inode': 2, 'current_mode': 0o100644, 'current_mtime_ns': 3, 'current_ctime_ns': 4})
        originals = {'archive_receipt': receipt, 'member_manifest': members, 'source_scope': scope,
                     'supplier_patch_images': images, 'generator': generator}
        if mutate is not None:
            mutate(originals)
        leaves = {'archive_receipt': 'archive-receipt.json', 'member_manifest': 'pristine-member-manifest.json',
                  'source_scope': 'source-scope.json', 'supplier_patch_images': 'supplier-patch-images.json', 'generator': 'create_archive.py'}
        raw = {name: value if name == 'generator' else encoded(value) for name, value in originals.items()}
        toolchain = NativeToolInventory.fixture(self)
        recipe_inputs = {name: {'sha256': digest(b'SYNTHETIC unrelated helper bytes'), 'mode': 0o644, 'role': 'helper'}
                         for name in self.api.manifest.HELPERS}
        recipe_inputs.update({
            'include/foundation/appended/engine_provider.h': {'sha256': self.api.actions.BASE_HEADER_SHA256, 'mode': 0o644, 'role': 'interface'},
            'licenses/SYNTHETIC': {'sha256': digest(b'SYNTHETIC'), 'mode': 0o644, 'role': 'license'},
            'archives/engine.tar.gz': {'sha256': engine['sha256'], 'mode': 0o644, 'role': 'source'},
            'archives/wrapper.tar.gz': {'sha256': projection['archives']['wrapper']['sha256'], 'mode': 0o644, 'role': 'source'},
            'patches/supplier.patch': {'sha256': digest(self.patch_raw), 'mode': 0o644, 'role': 'patch'}})
        for name, value in raw.items():
            recipe_inputs['provenance/source-archive/' + leaves[name]] = {'sha256': digest(value), 'mode': 0o644,
                'role': 'helper' if name == 'generator' else 'config'}
        recipe = {'schema_version': 1, 'kind': 'foundation-appended-engine-recipe', 'producer_version': 1,
            'target': TARGET, 'toolchain': toolchain['identity'],
            'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'native'},
            'provider': {'format': 'native-shared', 'binding': 'c-abi', 'abi_major': 1, 'abi_minor': 1,
                'header': 'include/foundation/appended/engine_provider.h', 'header_sha256': self.api.actions.BASE_HEADER_SHA256},
            'suppliers': {name: dict(projection['suppliers'][name], archive='archives/' + name + '.tar.gz') for name in ('engine', 'wrapper')},
            'inputs': recipe_inputs, 'patches': [copy.deepcopy(patch)], 'licenses': ['licenses/SYNTHETIC']}
        raw['recipe'] = encoded(recipe)
        source_files = {name: item['sha256'] for name, item in recipe_inputs.items()}
        source_files['recipe.json'] = digest(raw['recipe'])
        dirs = sorted({p.as_posix() for name in source_files for p in Path(name).parents if p.as_posix() != '.'})
        modes = {name: item['mode'] for name, item in recipe_inputs.items()}
        modes.update({name: 0o755 for name in dirs}); modes['recipe.json'] = 0o644
        sources = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources', 'producer_version': 1,
                   'recipe_id': digest(raw['recipe']), 'files': source_files, 'directories': dirs, 'modes': modes}
        if mutate_sources is not None:
            mutate_sources(sources)
        raw['sources'] = encoded(sources)
        proof = {}
        for name, contents in raw.items():
            leaf = leaves.get(name, name + '.json')
            self.f.file('provenance/original-proof/' + leaf, contents)
            proof[name] = {'path': 'original-proof/' + leaf, 'sha256': digest(contents), 'bytes': len(contents)}
        body = facts['body']
        body = {key: copy.deepcopy(value) for key, value in body.items()
                if key not in ('regular_blobs_verified', 'link_blobs_verified', 'source_bytes')}
        body.update(kind='foundation-native-engine-retained-body-evidence-v1',
                    scope='retained-original-git-body-proof-and-source-archive-consistency-only', original_proof=proof)
        if mutate_body is not None:
            mutate_body(body)
        body_path = self.f.file('provenance/engine-body-verification.SYNTHETIC', encoded(body))
        value = {key: copy.deepcopy(projection[key]) for key in ('schema_version', 'kind', 'suppliers', 'archives',
            'projection', 'patches', 'notices', 'provenance')}
        for item in list(value['archives'].values()) + value['notices'] + value['provenance']:
            item['path'] = Path(item['path']).relative_to(self.f.root).as_posix()
        body_item = next(item for item in value['provenance'] if item['role'] == 'engine-body-verification')
        body_item.update(sha256=digest(encoded(body)), bytes=len(encoded(body)))
        self.f.file('patches/supplier.patch', self.patch_raw)
        value['patches'] = [dict(patch, sha256=digest(self.patch_raw))]
        inputs = self.api.InputSet()
        with no_programs():
            parsed = self.api.parse_source_projection(value, self.f.root, inputs, TARGET)
        return parsed, inputs, {'body': body, 'raw': raw, 'originals': originals, 'body_path': body_path}

    def test_retained_original_evidence_keeps_seven_originals_and_false_execution_claim(self):
        projection, inputs, facts = self.fixture()
        with no_programs():
            result = self.api.validate_source_provenance(projection, inputs)
            inputs.recheck()
        self.assertEqual(result['evidence_kind'], 'foundation-native-engine-retained-body-evidence-v1')
        self.assertFalse(result['source_body_execution'])
        self.assertFalse(result['production_eligible'])
        self.assertEqual(len(result['original_proof']), 7)
        aliases = self.api._record_aliases(inputs.records)
        for name, ref in result['original_proof'].items():
            self.assertTrue(any(str(original) == ref['path'] and role == 'data' for _, original, role in aliases), name)
        self.assertEqual(len(facts['body']), 13)
        self.assertNotIn('passed', facts['body'])

    def test_retained_evidence_rejects_resealed_original_receipt_or_generator_changes(self):
        changes = (lambda facts: facts['archive_receipt'].update(git_returncode=True),
                   lambda facts: facts['archive_receipt'].update(archive_sha256='1' * 64),
                   lambda facts: facts['archive_receipt'].update(generator_sha256='2' * 64),
                   lambda facts: facts.update(generator=b'# changed synthetic generator\n'),
                   lambda facts: facts['archive_receipt'].update(all_archive_members_content_type_mode_and_order_verified=False))
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                projection, inputs, _ = self.fixture(change)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.validate_source_provenance(projection, inputs)

    def test_retained_evidence_rejects_raw_literal_vs_target_hash_and_scope_escape(self):
        def wrong_literal_hash(facts):
            item = next(item for item in facts['member_manifest']['entries'] if item['type'] == 'symlink')
            item['target_sha256'] = digest(b'wrong normalized target body')
        changes = (wrong_literal_hash,
                   lambda facts: facts['member_manifest']['entries'].pop(),
                   lambda facts: facts['member_manifest']['entries'][0].update(git_oid='3' * 40),
                   lambda facts: facts['source_scope']['symlinks'][0].update(raw_target='../../escape'),
                   lambda facts: facts['source_scope'].update(raw_regular_bytes=1))
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                projection, inputs, _ = self.fixture(change)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.validate_source_provenance(projection, inputs)

    def test_retained_evidence_requires_all45_original_preimages_and23_absent_additions(self):
        changes = (lambda facts: facts['supplier_patch_images'].update(added_paths=22),
                   lambda facts: facts['supplier_patch_images']['files'][0].update(preimage_sha256='4' * 64),
                   lambda facts: facts['supplier_patch_images']['recipe_patch']['preimages'].update({next(iter(self.modified)): '5' * 64}),
                   lambda facts: facts['supplier_patch_images']['files'].pop(),
                   lambda facts: facts['supplier_patch_images']['git_read'].update(optional_locks=True))
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                projection, inputs, _ = self.fixture(change)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.validate_source_provenance(projection, inputs)

    def test_retained_evidence_wrong_independent_pin_or_missing_original_never_executes(self):
        for mutation in ('missing', 'wrong-pin'):
            with self.subTest(mutation=mutation):
                projection, inputs, facts = self.fixture()
                ref = facts['body']['original_proof']['generator']
                path = self.f.root / 'provenance' / ref['path']
                if mutation == 'missing':
                    path.unlink()
                else:
                    path.write_bytes(b'# different bytes\n')
                with no_programs(), self.assertRaises(ValueError):
                    self.api.validate_source_provenance(projection, inputs)

    def test_retained_evidence_recipe_identity_missing_proof_or_preapplied_baseline_rejects(self):
        changes = ((lambda value: value.update(recipe_id='9' * 64), None),
                   (None, lambda value: value['original_proof'].pop('generator')),
                   (None, lambda value: value.update(baseline='supplier-already-patched')),
                   (None, lambda value: value.update(body_executed=True)))
        for index, (source_change, body_change) in enumerate(changes):
            with self.subTest(index=index):
                projection, inputs, _ = self.fixture(mutate_sources=source_change, mutate_body=body_change)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.validate_source_provenance(projection, inputs)


class NativeForwardPatchSource(unittest.TestCase):
    """Read current tracked patch/overlay bytes; never apply or compile them."""

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()
        cls.source_map = json.loads((ROOT / 'recipes/webkitwasm-native-rich4083-v1/source-imports.json').read_bytes())

    def fixture(self):
        before = {'Source/Proof/modified%02d.cpp' % index: digest(('original %d' % index).encode()) for index in range(45)}
        before.update({'Source/Proof/added%02d.cpp' % index: None for index in range(23)})
        after = {name: digest(('after ' + name).encode()) for name in before}
        files = {'source/engine/' + name: {'sha256': sha} for name, sha in before.items() if sha is not None}
        return {'patches': [{'tree': 'engine', 'sha256': self.api.SUPPLIER_PATCH,
                             'preimages': before, 'postimages': after}], '_files': files}

    def test_actual_four_native_diffs_are_fully_replaced_by_exact_final_overlays(self):
        entries = self.source_map['inputs']
        expected = {'patches/native-platform-engine.patch': 32,
                    'patches/native-provider-actions-binding.patch': 1,
                    'patches/native-provider-getter.patch': 1,
                    'patches/native-provider-runtime.patch': 2}
        overlays = {name for name, item in entries.items() if item['role'] == 'source'}
        self.assertEqual(len(overlays), 158 if self.source_map.get('kind') == self.api.COMPOSITION_SOURCE_KIND else 157)
        for name, count in expected.items():
            item = entries[name]
            raw = (ROOT / item['tracked_path']).read_bytes()
            self.assertEqual(digest(raw), item['sha256'])
            changed = [line[6:].decode() for line in raw.splitlines() if line.startswith(b'+++ b/')]
            self.assertEqual(len(changed), count, name)
            for path in changed:
                logical = path if path.startswith('source/') else 'source/engine/' + path
                self.assertIn(logical, overlays)
                self.assertEqual(digest((ROOT / entries[logical]['tracked_path']).read_bytes()), entries[logical]['sha256'])

    def test_only_supplier_forward_patch_is_admitted_while_all_five_map_pins_remain(self):
        entries = self.source_map['inputs']
        value = self.fixture()
        with no_programs():
            self.api._forward_patch_contract(value, entries)
        native = [item for item in entries.values() if item['role'] == 'patch' and item['sha256'] != self.api.SUPPLIER_PATCH]
        self.assertEqual(len(native), 4)
        for item in native:
            extra = copy.deepcopy(value)
            extra['patches'].append(dict(extra['patches'][0], sha256=item['sha256']))
            with self.subTest(sha=item['sha256']), no_programs(), self.assertRaises(ValueError):
                self.api._forward_patch_contract(extra, entries)
        for patches in ([], value['patches'] * 2):
            with self.subTest(count=len(patches)), self.assertRaises(ValueError):
                self.api._forward_patch_contract(dict(value, patches=patches), entries)

    def test_supplier_forward_images_require_exact45_original_and23_absent_members(self):
        changes = (lambda value: value['_files'].pop('source/engine/Source/Proof/modified00.cpp'),
                   lambda value: value['_files'].update({'source/engine/Source/Proof/added00.cpp': {'sha256': '1' * 64}}),
                   lambda value: value['patches'][0]['preimages'].pop('Source/Proof/added00.cpp'),
                   lambda value: value['patches'][0]['postimages'].update({'Source/Proof/added00.cpp': None}))
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                value = self.fixture()
                change(value)
                with no_programs(), self.assertRaises(ValueError):
                    self.api._forward_patch_contract(value, self.source_map['inputs'])


class NativeSDKInputHooks(unittest.TestCase):
    """Synthetic typed-inventory hooks; adapter validation is mocked explicitly."""

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-sdk-hook-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    def fixture(self, all_in_sdk=False):
        value = NativeToolInventory.fixture(self)
        value['kind'] = 'foundation-native-engine-prototype-sdk-toolchain-v1'
        value['runtime']['sysroot_inventory'] = 'sdk'
        sdk_metadata = {'kind': 'source-build', 'host': {'system': 'Linux'},
                        'target': {'system': 'Linux'}, 'path_policy': 'linux-case-sensitive-v1',
                        'fixture_only': 'SYNTHETIC hook; adapter admission is mocked'}
        inert = b'#!/bin/sh\n# SYNTHETIC SDK hook program; never run.\nexit 99\n'
        members = {'sdk.json': (encoded(sdk_metadata), 0o644),
                   'include/Case.h': (b'upper synthetic header\n', 0o644),
                   'include/case.h': (b'lower synthetic header\n', 0o644),
                   'lib/python/json/__init__.py': (b'# synthetic module\n', 0o644),
                   'lib/python/hashlib.py': (b'# synthetic module\n', 0o644),
                   'lib/python/pathlib.py': (b'# synthetic module\n', 0o644),
                   'bin/python': (inert, 0o755)}
        for name in self.api.TOOL_NAMES:
            members['bin/' + name] = (inert + name.encode() + b'\n', 0o755)
        if all_in_sdk:
            for name in ('perl', 'ruby', 'gperf', 'sh'):
                members['bin/' + name] = (inert, 0o755)
            for name in ('perl/English.pm', 'perl/FindBin.pm', 'perl/JSON/PP.pm',
                         'ruby/json.rb', 'ruby/fileutils.rb'):
                members['lib/' + name] = (b'# synthetic module\n', 0o644)
        sdk_metadata['files'] = {name: digest(body) for name, (body, _) in members.items()
                                 if name != 'sdk.json'}
        members['sdk.json'] = (encoded(sdk_metadata), 0o644)
        sdk_record = self.f.inventory('sdk', 'sdk', members)
        inventory_path = self.f.root / sdk_record['inventory']['path']
        inventory = json.loads(inventory_path.read_bytes())
        for name, program in value['tools'].items():
            program.update(path=str(self.f.root / 'sdk/bin' / name),
                           sha256=digest(members['bin/' + name][0]))
        value['inventories']['sdk'] = sdk_record
        value['environment']['PATH'] = str(self.f.root / 'sdk/bin')
        original = {'schema_version': 1, 'kind': 'foundation-native-toolchain-identity-v1',
                    'target': TARGET, 'compiler': value['compiler'],
                    'runtime': value['runtime'], 'cpu': value['cpu']}
        identity_path = self.f.file('toolchain/identity.json', encoded(original))
        identity_pin = digest(identity_path.read_bytes())
        value['identity']['identity_sha256'] = identity_pin
        metadata_path = self.f.root / value['inventories']['toolchain']['inventory']['path']
        metadata = json.loads(metadata_path.read_bytes())
        metadata['files']['identity.json'] = identity_pin
        metadata_path.write_bytes(encoded(metadata))
        value['inventories']['toolchain']['inventory']['sha256'] = digest(metadata_path.read_bytes())
        value['sdk_admission'] = self.f.document('sdk-admission.json',
            {'fixture_only': 'SYNTHETIC hook; real adapter validator is mocked'})
        binding = dict(inventory, root=sdk_record['root'], inventory=sdk_record['inventory'],
            inventory_base=str(self.f.root), inventory_path=str(inventory_path),
            metadata=sdk_metadata, path_policy='linux-case-sensitive-v1',
            sdk_manifest_sha256=digest(encoded(sdk_metadata)),
            tool_paths=copy.deepcopy(value['tools']), sysroot='sysroot',
            toolchain_sha256=metadata['files']['native-toolchain.cmake'],
            policy={'runtime': copy.deepcopy(value['runtime']), 'cpu': copy.deepcopy(value['cpu']),
                    'source_date_epoch': '0'})
        return value, binding

    @contextmanager
    def adapter(self, binding, error=None):
        module = types.ModuleType('appended_engine_native_sdk')

        class AdapterMissing(ValueError):
            def __init__(self, missing):
                self.missing = missing

        module.MissingInputs = AdapterMissing
        module.validate_sdk_binding = mock.Mock(return_value=copy.deepcopy(binding))
        if error is not None:
            module.validate_sdk_binding.side_effect = AdapterMissing(error)
        with mock.patch.dict(sys.modules, {'appended_engine_native_sdk': module}):
            yield module

    def parse(self, value, binding, inputs=None):
        with self.adapter(binding), no_programs():
            return self.api.parse_toolchain(value, self.f.root,
                                            inputs or self.api.InputSet(), TARGET)

    def test_synthetic_sdk_hook_manifest_binds_its_actual_file_parent_authority(self):
        value, binding = self.fixture()
        raw = (self.f.root / 'sdk/sdk.json').read_bytes()
        metadata = json.loads(raw)
        self.assertEqual(metadata['files'], {name: sha for name, sha in binding['files'].items()
                                            if name != 'sdk.json'})
        self.assertEqual(digest(raw), binding['sdk_manifest_sha256'])
        inputs = self.api.InputSet()
        self.parse(value, binding, inputs)
        self.assertEqual({row['path'] for row in inputs.sdk_directory_records},
                         {str(self.f.root / 'sdk'), *(str(self.f.root / 'sdk' / name)
                             for name in binding['directories'])})

    def test_sdk_adapter_receives_explicit_fork_repository_root(self):
        value, binding = self.fixture()
        repository = self.f.root / 'fork-repository'
        repository.mkdir(mode=0o755)
        with self.adapter(binding) as adapter, no_programs():
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET,
                                     repository_root=repository)
        adapter.validate_sdk_binding.assert_called_once()
        self.assertEqual(adapter.validate_sdk_binding.call_args.kwargs['repository_root'], repository)

    def host_fixture(self, toolchain, all_in_sdk=False):
        inert = b'#!/bin/sh\n# SYNTHETIC SDK hook program; never run.\nexit 99\n'
        sdk_root = self.f.root / 'sdk'
        programs = {name: copy.deepcopy(toolchain['tools'][name]) for name in ('cmake', 'ninja')}
        programs['python'] = {'path': str(sdk_root / 'bin/python'), 'sha256': digest(inert), 'version': '3.11.0'}
        extensions = {}
        if all_in_sdk:
            root, named_root = sdk_root, 'sdk'
        else:
            members = {'bin/' + name: (inert, 0o755) for name in ('perl', 'ruby', 'gperf', 'sh')}
            for name in ('perl/English.pm', 'perl/FindBin.pm', 'perl/JSON/PP.pm', 'ruby/json.rb', 'ruby/fileutils.rb'):
                members['lib/' + name] = (b'# synthetic module\n', 0o644)
            extensions['extensions'] = self.f.inventory('host-extension', 'extensions', members)
            root, named_root = self.f.root / 'extensions', 'host-extensions'
        for name, version in (('perl', '5.36.0'), ('ruby', '3.1.2'), ('gperf', '3.1.0'), ('sh', '1.0.0')):
            programs[name] = {'path': str(root / 'bin' / name), 'sha256': digest(inert), 'version': version}
        bindings = {}
        for role in ('python', 'perl', 'ruby'):
            facts = {'schema_version': 1, 'kind': 'foundation-native-host-interpreter-runtime-v1',
                     'program_sha256': programs[role]['sha256'],
                     'search_paths': [str((sdk_root if role == 'python' else root) / 'lib' / role)],
                     'runtime_inventories': ['sdk' if role == 'python' else named_root]}
            bindings[role] = self.f.document('facts-' + role + '.json', facts)
        result = {'schema_version': 1, 'kind': 'foundation-native-engine-prototype-sdk-host-tools-v1',
                  'programs': programs, 'module_inventories': extensions, 'interpreter_bindings': bindings}
        toolchain['sdk_binding']['host_document'] = copy.deepcopy(result)
        return result

    def test_typed_sdk_inventory_keeps_case_pair_without_relaxing_generic_inventory(self):
        value, binding = self.fixture()
        inputs = self.api.InputSet()
        with no_programs():
            result = inputs.sdk_inventory(value['inventories']['sdk'], self.f.root, 'sdk-inventory', binding=binding)
            inputs.recheck()
            with self.assertRaises(ValueError):
                inputs.inventory(value['inventories']['sdk'], self.f.root, 'ordinary-inventory')
        self.assertIn('include/Case.h', result['files'])
        self.assertIn('include/case.h', result['files'])
        self.assertNotIn('production_eligible', result)

    def test_sdk_inventory_cannot_accept_foreign_reference_policy_or_manifest_pin(self):
        changes = (lambda item: item.update(root=str(self.f.root / 'toolchain')),
                   lambda item: item.update(inventory_path=str(self.f.root / 'other.json')),
                   lambda item: item.update(inventory_base=str(self.f.root / 'elsewhere')),
                   lambda item: item.update(path_policy='portable'),
                   lambda item: item['metadata'].update(fixture_only='changed parsed metadata'),
                   lambda item: item.update(sdk_manifest_sha256='1' * 64),
                   lambda item: item['modes'].update({'sdk.json': True}))
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                value, binding = self.fixture()
                change(binding)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.InputSet().sdk_inventory(value['inventories']['sdk'], self.f.root, 'sdk', binding=binding)

    def test_sdk_inventory_requires_complete_actual_entries_and_exact_modes(self):
        for mutation in ('extra', 'missing', 'changed', 'mode', 'symlink'):
            with self.subTest(mutation=mutation):
                value, binding = self.fixture()
                target = self.f.root / 'sdk/include/Case.h'
                if mutation == 'extra':
                    self.f.file('sdk/unlisted', b'unlisted\n')
                elif mutation == 'missing':
                    target.unlink()
                elif mutation == 'changed':
                    target.write_bytes(b'changed\n')
                elif mutation == 'mode':
                    target.chmod(0o755)
                else:
                    target.unlink()
                    target.symlink_to(self.f.root / 'sdk/include/case.h')
                with no_programs(), self.assertRaises(ValueError):
                    self.api.InputSet().sdk_inventory(value['inventories']['sdk'], self.f.root, 'sdk', binding=binding)
                if mutation == 'extra':
                    (self.f.root / 'sdk/unlisted').unlink()
                if mutation == 'symlink':
                    target.unlink()

    def test_sdk_inventory_recheck_keeps_binding_and_deadline(self):
        value, binding = self.fixture()
        inputs = self.api.InputSet()
        inputs.sdk_inventory(value['inventories']['sdk'], self.f.root, 'sdk', binding=binding)
        original = self.api.InputSet.sdk_inventory
        inherited = []

        def observe(probe, *args, **kwargs):
            inherited.append(probe.deadline)
            return original(probe, *args, **kwargs)

        inputs.deadline = self.api.time.monotonic() + 60
        with mock.patch.object(self.api.InputSet, 'sdk_inventory', new=observe), no_programs():
            inputs.recheck()
        self.assertEqual(inherited, [inputs.deadline])
        inputs.deadline = 5
        with mock.patch.object(self.api.time, 'monotonic', return_value=6), no_programs(), self.assertRaisesRegex(ValueError, 'deadline'):
            inputs.recheck()
        inputs.deadline = None
        self.f.file('sdk/new-after-admission', b'changed complete inventory\n')
        with no_programs(), self.assertRaises(ValueError):
            inputs.recheck()

    def test_typed_sdk_walk_rejects_read_only_case_folding_lookup(self):
        value, binding = self.fixture()
        original = Path.exists
        alias = self.f.root / 'sdk' / 'SDK.JSON'

        def folded(path):
            return True if path == alias else original(path)

        with mock.patch.object(Path, 'exists', new=folded), no_programs(), self.assertRaisesRegex(ValueError, 'folds case'):
            self.api.InputSet().sdk_inventory(value['inventories']['sdk'], self.f.root, 'sdk', binding=binding)

    def test_sdk_toolchain_joins_real_walk_to_mocked_adapter_facts_without_execution(self):
        value, binding = self.fixture()
        inputs = self.api.InputSet()
        result = self.parse(value, binding, inputs)
        with no_programs():
            inputs.recheck()
        self.assertEqual(result['tools'], binding['tool_paths'])
        self.assertEqual(result['sdk_binding'], binding)
        self.assertEqual(result['runtime']['sysroot_inventory'], 'sdk')
        self.assertNotIn('production_eligible', result)

    def test_sdk_toolchain_refuses_resealed_runtime_controls_and_foreign_template(self):
        changes = (lambda item, binding: item['runtime'].update(cxx_library_baseline='3.4.31'),
                   lambda item, binding: item['environment'].update(SOURCE_DATE_EPOCH='1'),
                   lambda item, binding: binding['policy']['cpu'].update(source_dispatch='different'),
                   lambda item, binding: binding['tool_paths']['inspect'].update(version='14.3.0'),
                   lambda item, binding: binding.update(toolchain_sha256='2' * 64))
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                value, binding = self.fixture()
                change(value, binding)
                with self.assertRaisesRegex(ValueError, 'SDK-backed'):
                    self.parse(value, binding)

    def test_missing_original_sdk_observations_remain_structured_missing_inputs(self):
        value, binding = self.fixture()
        missing = [{'role': 'sdk-tool-observations', 'path': str(self.f.root / 'absent.json'),
                    'reason': 'original closed tool observations absent'}]
        with self.adapter(binding, error=missing), no_programs(), self.assertRaises(self.api.MissingInputs) as caught:
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET)
        self.assertEqual(caught.exception.missing, tuple(missing))
        self.assertFalse(caught.exception.as_dict()['executable_plan'])

    def test_old_toolchain_kind_cannot_acquire_sdk_field_or_case_policy(self):
        value = NativeToolInventory.fixture(self)
        with mock.patch.dict(sys.modules, {'appended_engine_native_sdk': None}), no_programs():
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET)
            value['sdk_admission'] = {'path': 'unrequested.json', 'sha256': '1' * 64}
            with self.assertRaises(ValueError):
                self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET)

    def test_external_sdk_interpreter_facts_need_no_root_mutation_and_render_exact_environment(self):
        value, binding = self.fixture()
        inputs = self.api.InputSet()
        toolchain = self.parse(value, binding, inputs)
        host = self.host_fixture(toolchain)
        with no_programs():
            result = self.api.parse_host_tools(host, self.f.root, inputs, toolchain)
            toolchain['environment']['PATH'] = ':'.join(sorted({str(Path(record['path']).parent)
                for record in list(toolchain['tools'].values()) + list(result['programs'].values())}))
            environment = self.api.render_environment(toolchain, result)
            inputs.recheck()
        self.assertEqual(set(result['interpreter_runtimes']), {'python', 'perl', 'ruby'})
        self.assertEqual(environment['PYTHONPATH'], str(self.f.root / 'sdk/lib/python'))
        self.assertEqual(environment['PERL5LIB'], str(self.f.root / 'extensions/lib/perl'))
        self.assertEqual(environment['RUBYLIB'], str(self.f.root / 'extensions/lib/ruby'))
        self.assertFalse((self.f.root / 'sdk/interpreter-runtime.json').exists())
        self.assertNotIn('python', result['module_inventories'])

    def test_sdk_host_kind_accepts_zero_extensions_only_with_complete_sdk_runtime_facts(self):
        value, binding = self.fixture(all_in_sdk=True)
        inputs = self.api.InputSet()
        toolchain = self.parse(value, binding, inputs)
        host = self.host_fixture(toolchain, all_in_sdk=True)
        with no_programs():
            result = self.api.parse_host_tools(host, self.f.root, inputs, toolchain)
            inputs.recheck()
        self.assertEqual(result['module_inventories'], {})
        self.assertEqual(result['interpreter_runtimes']['perl']['runtime_inventories'], ['sdk'])

    def test_external_facts_must_name_program_owner_and_contained_modules_and_search(self):
        changes = (lambda facts: facts.update(runtime_inventories=['toolchain']),
                   lambda facts: facts.update(program_sha256='3' * 64),
                   lambda facts: facts.update(search_paths=[str(self.f.root / 'toolchain/include')]),
                   lambda facts: facts.update(extra=True),
                   lambda facts: facts.update(runtime_inventories=[]))
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                value, binding = self.fixture()
                inputs = self.api.InputSet()
                toolchain = self.parse(value, binding, inputs)
                host = self.host_fixture(toolchain)
                path = self.f.root / host['interpreter_bindings']['python']['path']
                facts = json.loads(path.read_bytes())
                change(facts)
                host['interpreter_bindings']['python'] = self.f.document(path.name, facts)
                toolchain['sdk_binding']['host_document'] = copy.deepcopy(host)
                with no_programs(), self.assertRaises(ValueError):
                    self.api.parse_host_tools(host, self.f.root, inputs, toolchain)

    def test_external_facts_require_actual_modules_in_their_named_complete_roots(self):
        value, binding = self.fixture()
        inputs = self.api.InputSet()
        toolchain = self.parse(value, binding, inputs)
        host = self.host_fixture(toolchain)
        root = self.f.root / 'extensions'
        (root / 'lib/perl/English.pm').unlink()
        inventory_ref = host['module_inventories']['extensions']['inventory']
        inventory_path = self.f.root / inventory_ref['path']
        inventory = json.loads(inventory_path.read_bytes())
        inventory['files'].pop('lib/perl/English.pm')
        inventory['modes'].pop('lib/perl/English.pm')
        inventory_path.write_bytes(encoded(inventory))
        inventory_ref['sha256'] = digest(inventory_path.read_bytes())
        toolchain['sdk_binding']['host_document'] = copy.deepcopy(host)
        with no_programs(), self.assertRaisesRegex(ValueError, 'Required perl module'):
            self.api.parse_host_tools(host, self.f.root, inputs, toolchain)

    def test_selected_sdk_host_manifest_cannot_diverge_from_admission(self):
        value, binding = self.fixture()
        toolchain = self.parse(value, binding)
        host = self.host_fixture(toolchain)
        host['programs']['gperf']['version'] = '3.2.0'
        with no_programs(), self.assertRaisesRegex(ValueError, 'original admitted host manifest'):
            self.api.parse_host_tools(host, self.f.root, self.api.InputSet(), toolchain)

    def test_sdk_host_external_facts_recheck_stale_bytes_and_reject_generic_toolchain(self):
        value, binding = self.fixture()
        inputs = self.api.InputSet()
        toolchain = self.parse(value, binding, inputs)
        host = self.host_fixture(toolchain)
        with no_programs():
            self.api.parse_host_tools(host, self.f.root, inputs, toolchain)
            path = self.f.root / host['interpreter_bindings']['python']['path']
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaises(ValueError):
                inputs.recheck()
            toolchain['kind'] = 'foundation-native-engine-prototype-toolchain-v1'
            with self.assertRaisesRegex(ValueError, 'SDK-backed'):
                self.api.parse_host_tools(host, self.f.root, self.api.InputSet(), toolchain)


class NativePrivateRuntimeHooks(unittest.TestCase):
    """Real input/retention hooks with an explicit mocked SDK runtime boundary."""

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-private-runtime-hook-')
        self.addCleanup(self.temporary.cleanup)
        self.f = TinyFiles(self.temporary.name)

    adapter = NativeSDKInputHooks.adapter

    def fixture(self):
        value, binding = NativeSDKInputHooks.fixture(self)
        value['kind'] = self.api.PRIVATE_TOOLCHAIN_KIND
        value['private_runtime_selection'] = self.f.document('private-runtime-selection.json',
            {'fixture_only': 'SDK runtime validator mocked; never compiler/link evidence'})
        return value, binding

    def runtime(self, value):
        ref = value['private_runtime_selection']
        record = {'path': str(self.f.root / ref['path']), 'sha256': ref['sha256']}
        selected = {role: {'path': str(self.f.root / 'sdk/include/Case.h'),
                           'sha256': digest(b'upper synthetic header\n'), 'bytes': len(b'upper synthetic header\n')}
                    for role in ('libstdcxx', 'libgcc', 'libgcc_eh', 'crtbeginS', 'crtendS')}
        cmake = {'BIB_NATIVE_RUNTIME_COMPILER_TRIPLE': TARGET['triple'],
                 'BIB_NATIVE_RUNTIME_SELECTION_PATH': record['path'],
                 'BIB_NATIVE_RUNTIME_SELECTION_SHA256': record['sha256'],
                 'BIB_NATIVE_RUNTIME_POLICY_SHA256': '1' * 64}
        for role, symbol in (('libstdcxx', 'LIBSTDCXX'), ('libgcc', 'LIBGCC'), ('libgcc_eh', 'LIBGCC_EH'),
                             ('crtbeginS', 'CRTBEGINS'), ('crtendS', 'CRTENDS')):
            cmake['BIB_NATIVE_RUNTIME_' + symbol + '_PATH'] = selected[role]['path']
            cmake['BIB_NATIVE_RUNTIME_' + symbol + '_SHA256'] = selected[role]['sha256']
        return {'record': record, 'selected': selected, 'query_environment': {}, 'search_directories': {},
                'policy': {'fixture_only': True}, 'policy_sha256': '1' * 64,
                'compiler_triple': TARGET['triple'], 'candidates': {}, 'cmake': cmake}

    @contextmanager
    def runtime_adapter(self, value, binding, *, missing=None):
        runtime = self.runtime(value)
        environment = {'PATH': str(self.f.root / 'sdk/bin'), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                       'TZ': 'UTC', 'SOURCE_DATE_EPOCH': '0'}
        with self.adapter(binding) as module:
            module.private_runtime_query_environment = mock.Mock(return_value=environment)

            def validate(ref, base, capture, **kwargs):
                if missing is not None:
                    raise module.MissingInputs(missing)
                capture.document(ref, base, 'sdk-provenance-private-runtime-selection')
                return copy.deepcopy(runtime)

            module.validate_private_runtime_selection = mock.Mock(side_effect=validate)
            yield module, runtime, environment

    def test_private_kind_delegates_exact_policy_and_sdk_query_environment(self):
        value, binding = self.fixture()
        inputs = self.api.InputSet()
        with self.runtime_adapter(value, binding) as (module, runtime, environment), no_programs():
            result = self.api.parse_toolchain(value, self.f.root, inputs, TARGET, repository_root=ROOT)
            inputs.recheck()
        self.assertEqual(result['private_runtime'], runtime)
        module.private_runtime_query_environment.assert_called_once_with(binding)
        call = module.validate_private_runtime_selection.call_args
        self.assertEqual(call.args[:2], (value['private_runtime_selection'], self.f.root))
        self.assertEqual(call.kwargs['binding'], binding)
        self.assertEqual(call.kwargs['expected_environment'], environment)
        self.assertEqual(digest(call.kwargs['policy_raw']),
                         '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc')
        records = {item['path']: item for item in inputs.records}
        self.assertEqual(records[str(ROOT / self.api.PRIVATE_RUNTIME_POLICY)]['mode_policy'], 'repository-producer-logical-v1')
        self.assertIn('sdk-provenance-private-runtime-selection', records[runtime['record']['path']]['roles'])

    def test_old_toolchain_kinds_reject_private_selection_without_reinterpretation(self):
        value, binding = self.fixture()
        value['kind'] = 'foundation-native-engine-prototype-sdk-toolchain-v1'
        with self.runtime_adapter(value, binding) as (module, _, _), no_programs(), self.assertRaises(ValueError):
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET)
        module.validate_private_runtime_selection.assert_not_called()
        value = NativeToolInventory.fixture(self)
        value['private_runtime_selection'] = {'path': 'not-admitted.json', 'sha256': '1' * 64}
        with no_programs(), self.assertRaises(ValueError):
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET)

    def test_missing_runtime_facts_translate_without_plan_or_tool_launch(self):
        value, binding = self.fixture()
        missing = [{'role': 'sdk-private-runtime-selection', 'path': str(self.f.root / 'absent'),
                    'reason': 'Original compiler query observations required'}]
        with self.runtime_adapter(value, binding, missing=missing), no_programs(), self.assertRaises(self.api.MissingInputs) as caught:
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET)
        self.assertEqual(caught.exception.missing, tuple(missing))
        self.assertFalse(caught.exception.as_dict()['executable_plan'])

    def test_private_policy_source_uses_explicit_repository_modes_and_missing_role(self):
        value, binding = self.fixture()
        with self.runtime_adapter(value, binding) as (module, _, _), no_programs(), self.assertRaises(self.api.MissingInputs) as caught:
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET, repository_root=self.f.root)
        self.assertEqual(caught.exception.roles, ('private-runtime-policy',))
        module.validate_private_runtime_selection.assert_not_called()
        policy = self.f.file(self.api.PRIVATE_RUNTIME_POLICY, (ROOT / self.api.PRIVATE_RUNTIME_POLICY).read_bytes(), 0o664)
        with self.runtime_adapter(value, binding), no_programs():
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET, repository_root=self.f.root)
        policy.chmod(0o600)
        with self.runtime_adapter(value, binding) as (module, _, _), no_programs(), self.assertRaises(ValueError):
            self.api.parse_toolchain(value, self.f.root, self.api.InputSet(), TARGET, repository_root=self.f.root)
        module.validate_private_runtime_selection.assert_not_called()

    def internal_runtime_inspection(self, with_alias=True):
        inspection = NativeSourcePreparation.internal_inspection(self)
        raw = encoded({'fixture_only': 'INTERNAL R/S/CMake publication; no runtime query evidence'})
        path = self.f.file('internal-selection.json', raw)
        record = inspection._inputs.file(path, digest(raw), 'sdk-provenance-private-runtime-selection')
        value = {'private_runtime_selection': {'path': path.name, 'sha256': record['sha256']}}
        runtime = self.runtime(value)
        runtime['record']['path'] = str(path)
        runtime['cmake']['BIB_NATIVE_RUNTIME_SELECTION_PATH'] = str(path)
        inspection._data['toolchain']['private_runtime'] = runtime
        alias = 'native-inputs/records/' + record['sha256'] + '.bin'
        if with_alias:
            inspection._retained[alias] = {'path': str(path), 'sha256': record['sha256'], 'mode': 0o644, 'role': 'data'}
        return inspection, alias, raw, runtime

    def test_internal_runtime_cmake_path_is_exact_retained_data_copy(self):
        inspection, alias, raw, runtime = self.internal_runtime_inspection()
        self.assertEqual(inspection.cmake['BIB_NATIVE_RUNTIME_SELECTION_PATH'], runtime['record']['path'])
        with no_programs():
            result = self.api.assemble(inspection, self.f.root / 'private-runtime-retained')
        retained_path = Path(result.as_dict()['retained_root']) / alias
        self.assertEqual(result.cmake['BIB_NATIVE_RUNTIME_SELECTION_PATH'], str(retained_path))
        self.assertEqual(retained_path.read_bytes(), raw)
        self.assertEqual(result.cmake['BIB_NATIVE_RUNTIME_SELECTION_SHA256'], digest(raw))
        self.assertEqual(result.cmake['BIB_NATIVE_RUNTIME_POLICY_SHA256'], runtime['policy_sha256'])

    def test_runtime_cmake_refuses_missing_data_alias_before_output(self):
        inspection, _, _, _ = self.internal_runtime_inspection(with_alias=False)
        output = self.f.root / 'missing-runtime-alias-output'
        with mock.patch.object(self.api, '_fresh_directory', side_effect=AssertionError('output created')), \
                no_programs(), self.assertRaisesRegex(ValueError, 'retained DATA alias'):
            self.api.assemble(inspection, output)
        self.assertFalse(output.exists())

    def test_profile_requires_private_kind_before_source_parser_or_executable_plan(self):
        selection, value, _, _ = NativeExternalCopiedMap.fixture(self)
        value['toolchain'] = self.f.document('manifests/toolchain.json',
            {'kind': 'foundation-native-engine-prototype-sdk-toolchain-v1'})
        selection.write_bytes(encoded(value))
        with mock.patch.object(self.api, 'parse_toolchain', side_effect=AssertionError('private prerequisite bypassed')), \
                no_programs(), self.assertRaises(self.api.MissingInputs) as caught:
            self.api.inspect_selection(selection, digest(selection.read_bytes()), repository_root=ROOT)
        self.assertEqual(caught.exception.roles, ('private-sdk-toolchain',))
        self.assertFalse(caught.exception.as_dict()['executable_plan'])


class NativeGeneratedSDKManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='native-generated-sdk-manifest-')
        self.addCleanup(temporary.cleanup)
        self.files = TinyFiles(temporary.name)
        self.root = self.files.root / 'sdk'
        self.path = self.files.file('sdk/sdk.json', b'{}\n', 0o600)
        self.sha = digest(self.path.read_bytes())

    def capture(self, inputs=None, **kwargs):
        inputs = self.api.InputSet() if inputs is None else inputs
        arguments = dict(sdk_root=self.root, manifest_sha256=self.sha)
        arguments.update(kwargs)
        return inputs, inputs.sdk_manifest_file(self.path, self.sha, 'sdk-provenance-root', **arguments)

    def test_exact_generated_manifest_reads_and_rechecks_without_chmod(self):
        with no_programs():
            inputs, record = self.capture()
            self.assertEqual(record['mode'], 0o644)
            self.assertEqual(record['physical_mode'], 0o600)
            self.assertEqual(record['mode_policy'], 'generated-sdk-root-manifest-v1')
            self.assertEqual(inputs.bytes(self.path), b'{}\n')
            inputs.recheck()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_exact_declared_path_root_and_independent_pin_are_mandatory(self):
        wrong = self.files.root / 'other'
        wrong.mkdir()
        for changes in ({'sdk_root': wrong}, {'manifest_sha256': digest(b'other')}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.capture(**changes)
        alternate = self.files.file('sdk/not-sdk.json', b'{}\n', 0o600)
        with self.assertRaises(ValueError):
            self.api.InputSet().sdk_manifest_file(alternate, self.sha, 'not-root',
                sdk_root=self.root, manifest_sha256=self.sha)

    def test_cached_typed_authority_never_relaxes_public_file_or_generic_inventory(self):
        inputs, _ = self.capture()
        with self.assertRaises(ValueError):
            inputs.file(self.path, self.sha, 'strict-same-cached-path')
        reference = self.files.document('ordinary-inventory.json', {'files': {'sdk.json': self.sha},
            'directories': [], 'modes': {'sdk.json': 0o644}})
        with self.assertRaises(ValueError):
            inputs.inventory({'root': str(self.root), 'inventory': reference}, self.files.root, 'strict-root')
        self.assertEqual(inputs.bytes(self.path), b'{}\n')

    def test_generated_manifest_mode_does_not_extend_to_other_private_modes(self):
        for mode in (0o640, 0o664, 0o700, 0o4600):
            self.path.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.capture()

    def test_recheck_and_cached_bytes_reject_changed_body_or_physical_mode(self):
        for change in ('body', 'mode'):
            self.path.write_bytes(b'{}\n'); self.path.chmod(0o600)
            inputs, _ = self.capture()
            if change == 'body':
                self.path.write_bytes(b'[]\n')
            else:
                self.path.chmod(0o644)
            for operation in (lambda: inputs.bytes(self.path), inputs.recheck):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    operation()

    def test_typed_sdk_inventory_keeps_logical_mode_and_rechecks_actual0600(self):
        reference = self.files.document('sdk-inventory.json', {'files': {'sdk.json': self.sha},
            'directories': [], 'modes': {'sdk.json': 0o644}})
        path = self.files.root / reference['path']
        binding = dict(root=str(self.root), inventory=reference, inventory_base=str(self.files.root),
            inventory_path=str(path), files={'sdk.json': self.sha}, directories=[],
            modes={'sdk.json': 0o644}, path_policy='portable',
            sdk_manifest_sha256=self.sha, metadata={})
        inputs = self.api.InputSet()
        with no_programs():
            result = inputs.sdk_inventory({'root': str(self.root), 'inventory': reference}, self.files.root,
                                          'typed-sdk', binding=binding)
            inputs.recheck()
        self.assertEqual(result['modes']['sdk.json'], 0o644)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_typed_manifest_bound_and_repository_authority_cannot_be_reused(self):
        with self.assertRaises(ValueError):
            self.capture(maximum=1)
        inputs, _ = self.capture()
        with self.assertRaises(ValueError):
            inputs.repository_file(self.path, self.sha, 'source', repository_root=self.root,
                                   source_paths=('sdk.json',))
        self.path.chmod(0o644)
        inputs = self.api.InputSet()
        inputs.repository_file(self.path, self.sha, 'source', repository_root=self.root,
                               source_paths=('sdk.json',))
        with self.assertRaises(ValueError):
            self.capture(inputs)


class NativeSDKDirectoryAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with no_programs():
            cls.api = load_helper()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='native-SYNTHETIC-sdk-directories-')
        self.addCleanup(temporary.cleanup)
        self.files = TinyFiles(temporary.name)
        self.root = self.files.root / 'sdk'
        executable = self.files.file('sdk/bin/nested/tool', b'SYNTHETIC tool, never executed\n', 0o755)
        notice = self.files.file('sdk/share/licenses/notice', b'SYNTHETIC notice\n')
        self.metadata = {'files': {'bin/nested/tool': digest(executable.read_bytes()),
                                   'share/licenses/notice': digest(notice.read_bytes())}}
        self.manifest = self.files.file('sdk/sdk.json', encoded(self.metadata), 0o600)
        self.sha = digest(self.manifest.read_bytes())
        self.directories = (self.root, self.root / 'bin', self.root / 'bin/nested',
                            self.root / 'share', self.root / 'share/licenses')

    def captured(self, metadata=None):
        if metadata is not None:
            self.manifest.write_bytes(encoded(metadata)); self.manifest.chmod(0o600)
            self.sha = digest(self.manifest.read_bytes())
        inputs = self.api.InputSet()
        inputs.sdk_manifest_file(self.manifest, self.sha, 'sdk-provenance-original-manifest',
                                 sdk_root=self.root, manifest_sha256=self.sha)
        return inputs

    def directory(self, inputs, path=None, **kwargs):
        arguments = dict(sdk_root=self.root, manifest_sha256=self.sha)
        arguments.update(kwargs)
        return inputs.sdk_directory(self.root if path is None else path, **arguments)

    def binding(self):
        files = dict(self.metadata['files'], **{'sdk.json': self.sha})
        directories = sorted(path.relative_to(self.root).as_posix() for path in self.directories[1:])
        modes = {name: (0o755 if name == 'bin/nested/tool' else 0o644) for name in files}
        modes.update({name: 0o755 for name in directories})
        value = dict(files=files, directories=directories, modes=modes)
        reference = self.files.document('sdk-inventory.json', value)
        return dict(root=str(self.root), inventory=reference, inventory_base=str(self.files.root),
            inventory_path=str(self.files.root / reference['path']), path_policy='portable',
            sdk_manifest_sha256=self.sha, metadata=self.metadata, **value)

    def test_root_and_nested0755_or0775_keep_physical_facts_without_file_aliases(self):
        original = self.manifest.read_bytes()
        for mode in (0o755, 0o775):
            for path in self.directories:
                path.chmod(mode)
            with self.subTest(mode=mode), no_programs():
                inputs = self.captured()
                for path in self.directories:
                    fact = self.directory(inputs, path)
                    self.assertEqual(set(fact), {'path', 'sdk_root', 'manifest_sha256',
                        'physical_mode', 'mode', 'mode_policy', 'identity'})
                    self.assertEqual(fact['physical_mode'], mode)
                    self.assertEqual(fact['mode'], 0o755)
                    self.assertEqual(fact['mode_policy'], 'generated-sdk-manifest-parent-directories-v1')
                    self.assertEqual(fact['identity'], list(self.api._identity(path.lstat())))
                    self.assertEqual(fact['sdk_root'], str(self.root))
                    self.assertEqual(fact['manifest_sha256'], self.sha)
                inputs.recheck()
                self.assertEqual(len(inputs.sdk_directory_records), len(self.directories))
                self.assertEqual([row['path'] for row in inputs.records], [str(self.manifest)])
                self.assertTrue(set(self.directories) <= set(inputs.protected_paths))
        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertEqual(self.manifest.stat().st_mode & 0o7777, 0o600)

    def test_authority_requires_the_already_captured_exact_root_manifest_and_pin(self):
        with self.assertRaises(ValueError):
            self.directory(self.api.InputSet())
        inputs = self.captured()
        foreign = self.files.root / 'foreign'; foreign.mkdir()
        for kwargs in ({'sdk_root': foreign}, {'manifest_sha256': digest(b'foreign manifest')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.directory(inputs, **kwargs)
        self.assertEqual(inputs.sdk_directory_records, ())

    def test_unknown_empty_extra_and_external_directories_are_never_derived(self):
        extra = self.root / 'unlisted'; extra.mkdir()
        foreign = self.files.root / 'foreign'; foreign.mkdir()
        inputs = self.captured()
        for path in (extra, foreign, self.root.parent):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'parent authority'):
                self.directory(inputs, path)
        self.assertEqual(inputs.sdk_directory_records, ())

    def test_empty_lower_level_metadata_authorizes_only_root(self):
        inputs = self.captured({})
        self.assertEqual(self.directory(inputs)['mode'], 0o755)
        with self.assertRaisesRegex(ValueError, 'parent authority'):
            self.directory(inputs, self.root / 'bin')
        self.assertEqual(len(inputs.sdk_directory_records), 1)

    def test_present_file_maps_require_valid_nonempty_original_namespace(self):
        cases = ([], {'files': {}}, {'files': []}, {'not-files': {}},
            {'files': {'bin/../tool': digest(b'tool')}},
            {'files': {'bin/tool': '0' * 64}},
            {'files': {'sdk.json/nested': digest(b'tool')}},
            {'files': {'Case/tool': digest(b'a'), 'case/tool': digest(b'b')}})
        for value in cases:
            with self.subTest(value=value):
                inputs = self.captured(value)
                with self.assertRaises(ValueError):
                    self.directory(inputs)
                self.assertEqual(inputs.sdk_directory_records, ())

    def test_existing_linux_case_sensitive_policy_derives_exact_case_parents(self):
        upper, lower = self.root / 'Case', self.root / 'case'
        upper.mkdir(); lower.mkdir()
        inputs = self.captured({'files': {'Case/tool': digest(b'a'), 'case/tool': digest(b'b')},
            'path_policy': 'linux-case-sensitive-v1', 'host': {'system': 'Linux'},
            'target': {'system': 'Linux'}})
        with no_programs():
            self.directory(inputs, upper); self.directory(inputs, lower)
        self.assertEqual({row['path'] for row in inputs.sdk_directory_records}, {str(upper), str(lower)})

    def test_only0755_and0775_directory_modes_are_accepted(self):
        path = self.root / 'bin'
        for mode in (0o700, 0o750, 0o770, 0o777, 0o1755, 0o2755, 0o4775):
            path.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.directory(self.captured(), path)
        path.chmod(0o755)

    def test_manifest_parent_must_be_an_actual_ordinary_directory(self):
        path = self.root / 'bin/nested'
        saved = self.files.root / 'saved-directory'
        for kind in ('symlink', 'file', 'fifo'):
            path.rename(saved)
            try:
                if kind == 'symlink':
                    path.symlink_to(saved, target_is_directory=True)
                elif kind == 'file':
                    path.write_bytes(b'SYNTHETIC non-directory')
                else:
                    os.mkfifo(path)
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    self.directory(self.captured(), path)
            finally:
                path.unlink(); saved.rename(path)

    def test_physical_mode_drift_is_not_hidden_by_equal_logical0755(self):
        inputs = self.captured()
        path = self.root / 'bin'
        self.directory(inputs, path)
        path.chmod(0o775)
        for operation in (lambda: self.directory(inputs, path), inputs.recheck):
            with self.assertRaisesRegex(ValueError, 'physical identity'):
                operation()

    def test_directory_inode_replacement_is_not_a_fresh_snapshot_during_recheck(self):
        inputs = self.captured()
        path = self.root / 'bin'
        original = self.directory(inputs, path)
        path.rename(self.files.root / 'original-bin')
        path.mkdir(mode=0o755)
        self.assertNotEqual(path.lstat().st_ino, original['identity'][1])
        with self.assertRaisesRegex(ValueError, 'physical identity'):
            inputs.recheck()

    def test_typed_inventory_normalizes_directories_but_cached_generic_stays_actual(self):
        for path in self.directories:
            path.chmod(0o775)
        inputs = self.captured()
        binding = self.binding()
        record = {'root': str(self.root), 'inventory': binding['inventory']}
        with no_programs():
            value = inputs.sdk_inventory(record, self.files.root, 'typed-sdk', binding=binding)
            inputs.recheck()
        for name in binding['directories']:
            self.assertEqual(value['modes'][name], 0o755)
        self.assertEqual(len(inputs.sdk_directory_records), len(self.directories))
        with self.assertRaisesRegex(ValueError, 'wrong-mode native inventory directory'):
            inputs.inventory(record, self.files.root, 'ordinary-root')
        self.assertEqual((self.root / 'bin').stat().st_mode & 0o7777, 0o775)
        self.assertEqual(self.manifest.stat().st_mode & 0o7777, 0o600)

    def test_count_bound_includes_root_and_precedes_next_directory_capture(self):
        inputs = self.captured()
        self.directory(inputs, maximum_directories=1)
        original = self.api._ordinary
        target = self.root / 'bin'
        def ordinary(path, directory=False):
            if path == target:
                raise AssertionError('directory count bound did not precede capture')
            return original(path, directory)
        with mock.patch.object(self.api, '_ordinary', side_effect=ordinary), \
                self.assertRaisesRegex(ValueError, 'capture count bound'):
            self.directory(inputs, target, maximum_directories=1)
        self.assertEqual(len(inputs.sdk_directory_records), 1)

    def test_derived_parent_bound_and_deadline_precede_directory_fact_publication(self):
        inputs = self.captured()
        with mock.patch.object(self.api, 'MAX_FILES', 2), \
                self.assertRaisesRegex(ValueError, 'directory authority exceeds'):
            self.directory(inputs, maximum_directories=2)
        self.assertEqual(inputs.sdk_directory_records, ())
        inputs.deadline = 1
        with mock.patch.object(self.api.time, 'monotonic', return_value=2), \
                self.assertRaisesRegex(ValueError, 'deadline expired'):
            self.directory(inputs)
        self.assertEqual(inputs.sdk_directory_records, ())

    def test_directory_facts_are_independent_copies_and_not_file_mode_authority(self):
        inputs = self.captured()
        fact = self.directory(inputs)
        fact['identity'][0] = -1
        fact['mode'] = 0o777
        copied = inputs.sdk_directory_records
        copied[0]['identity'][0] = -2
        copied[0]['physical_mode'] = 0o777
        self.assertEqual(inputs.sdk_directory_records[0]['mode'], 0o755)
        self.assertEqual(inputs.sdk_directory_records[0]['physical_mode'], 0o755)
        self.assertGreaterEqual(inputs.sdk_directory_records[0]['identity'][0], 0)
        ordinary = self.root / 'bin/nested/tool'
        ordinary.chmod(0o775)
        with self.assertRaises(ValueError):
            inputs.file(ordinary, self.metadata['files']['bin/nested/tool'], 'ordinary-asset')
        self.assertEqual([row['path'] for row in inputs.records], [str(self.manifest)])


# New diagnostic authority and portable supplier-record checks use only tiny synthetic inputs.
def diag_digest(raw):
    return hashlib.sha256(raw).hexdigest()

def diag_encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')

class DiagnosticSyntheticFixture:
    """Create tiny, ordinary, test-owned files when a later test is authorized."""
    roles = ('python', 'perl', 'ruby', 'gperf', 'cmake', 'ninja', 'sh')
    versions = {'python': '3.11.2', 'perl': '5.36.0', 'ruby': '3.3.8', 'gperf': '3.2.1', 'cmake': '3.25.1', 'ninja': '1.11.1', 'sh': '1.0'}
    tool_roles = ('c', 'cxx', 'linker', 'archiver', 'ranlib', 'inspect', 'cmake', 'ninja', 'pkg_config')
    policy_raw = b'{\n  "cpu": {\n    "baseline": "sse2",\n    "source_dispatch": "supplier-per-source-reviewed"\n  },\n  "execution_host": {\n    "distribution": {\n      "codename": "trixie",\n      "id": "debian",\n      "version_id": "13"\n    },\n    "libc": {\n      "family": "glibc",\n      "version": "2.41"\n    },\n    "processor": "x86_64",\n    "system": "Linux"\n  },\n  "kernel_rebuild": false,\n  "kind": "foundation-native-diagnostic-host-policy-v1",\n  "native_engine_execution": false,\n  "policy_id": "linux-x86_64-debian13-trixie-glibc2.41-diagnostic-v1",\n  "production_eligible": false,\n  "program_roles": [\n    "python",\n    "perl",\n    "ruby",\n    "gperf",\n    "cmake",\n    "ninja",\n    "sh"\n  ],\n  "schema_version": 1,\n  "scope": "native-engine-diagnostic-build-host-only",\n  "sdk_original_host": {\n    "glibc": "2.36",\n    "processor": "x86_64",\n    "system": "Linux"\n  },\n  "target": {\n    "glibc": "2.36",\n    "processor": "x86_64",\n    "system": "Linux",\n    "triple": "x86_64-buildroot-linux-gnu"\n  }\n}\n'

    def __init__(self, root, native, original):
        self.root, self.native, self.original = (Path(root), native, original)
        self.base = self.root / 'metadata'
        self.sdk_root, self.host_root = (self.root / 'sdk', self.root / 'host')
        self.body_root = self.root / 'opaque'
        self.helper_calls = []
        self.boundary_calls = []
        for path in (self.root, self.base, self.sdk_root, self.host_root, self.body_root):
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(493)
        helper_path = Path(original.__file__)
        with helper_path.open('rb') as stream:
            helper_raw = stream.read(1024 * 1024 + 1)
        if len(helper_raw) > 1024 * 1024 or diag_digest(helper_raw) != '73ab3f22855e7d647e6259004288fe3fc0754b38aa19d7abfd513fff705e8fd8':
            raise AssertionError('Synthetic fixture needs the exact reviewed passive helper source')
        self.put(self.root / 'tools/appended_engine_native_original_proof.py', helper_raw)
        self.put(self.sdk_root / 'sdk.json', diag_encoded({'synthetic_admission_boundary': True}))
        self.programs, self.tools = ({}, {})
        for role in self.tool_roles:
            self.tools[role] = self.program(self.sdk_root / 'bin' / role, role, '12.2.0')
        self.tools['cmake']['version'], self.tools['ninja']['version'] = ('3.25.1', '1.11.1')
        for role in self.roles:
            path = (self.host_root if role in ('gperf', 'ruby') else self.sdk_root) / 'bin' / role
            if role in ('cmake', 'ninja'):
                self.programs[role] = copy.deepcopy(self.tools[role])
            else:
                self.programs[role] = self.program(path, role, self.versions[role])
        for member in ('lib/python/json/__init__.py', 'lib/python/hashlib.py', 'lib/python/pathlib.py', 'lib/perl/English.pm', 'lib/perl/FindBin.pm', 'lib/perl/JSON/PP.pm'):
            self.put(self.sdk_root / member, ('synthetic module ' + member).encode())
        for member in ('lib/ruby/json.rb', 'lib/ruby/fileutils.rb'):
            self.put(self.host_root / member, ('synthetic module ' + member).encode())
        self.put(self.host_root / 'lib/ruby/empty.rb', b'')
        self.observer_raw = b'# Inert synthetic observer; no execution modes.\n'
        self.put(self.host_root / 'observer.py', self.observer_raw)
        self.put(self.base / 'observer-original.py', self.observer_raw)
        for name in ('libc', 'loader'):
            raw = ('synthetic original ' + name).encode()
            self.put(self.host_root / 'runtime' / name, raw)
            self.put(self.base / ('original-' + name), raw)
        self.put(self.body_root / 'Packages', b'SYNTHETIC Packages body\n')
        self.sdk_ref, self.sdk_inventory = self.inventory(self.sdk_root, 'sdk-inventory.json')
        self.host_ref, self.host_inventory = self.inventory(self.host_root, 'host-inventory.json')
        self.body_ref, self.body_inventory = self.inventory(self.body_root, 'body-inventory.json')
        self.runtime_facts, self.fact_refs = ({}, {})
        for role in ('python', 'perl', 'ruby'):
            owner = self.host_root if role == 'ruby' else self.sdk_root
            facts = {'schema_version': 1, 'kind': 'foundation-native-host-interpreter-runtime-v1', 'program_sha256': self.programs[role]['sha256'], 'search_paths': [str(owner / 'lib' / role)], 'runtime_inventories': ['host-extra' if role == 'ruby' else 'sdk']}
            self.runtime_facts[role] = facts
            self.fact_refs[role] = self.document('facts/' + role + '.json', facts)
        self.original_ref = self.document('proof-launch.json', {'synthetic': 'original launch boundary'})
        proof_raw = diag_encoded({'synthetic': 'original proof boundary'})
        self.put(self.base / 'proof.json', proof_raw)
        self.proof_ref = {'path': str(self.base / 'proof.json'), 'sha256': diag_digest(proof_raw), 'bytes': len(proof_raw), 'kind': 'foundation-native-fixed-trixie-original-proof-v1'}
        self.packages = {}
        for name in ('gperf', 'ruby3.3', 'libruby3.3'):
            self.packages[name] = {'name': name, 'source_package': 'gperf' if name == 'gperf' else 'ruby3.3', 'version': '3.2.1-1' if name == 'gperf' else '3.3.8-2', 'architecture': 'amd64', 'members': {}, 'link_origins': {}}
        self.member('gperf', 'usr/bin/gperf', self.host_root / 'bin/gperf')
        self.member('ruby3.3', 'usr/bin/ruby3.3', self.host_root / 'bin/ruby')
        self.member('libruby3.3', 'usr/lib/ruby/json.rb', self.host_root / 'lib/ruby/json.rb')
        self.member('libruby3.3', 'usr/lib/ruby/empty.rb', self.host_root / 'lib/ruby/empty.rb')
        self.wrapper = {'schema_version': 1, 'kind': 'foundation-retained-diagnostic-host-original-proof-provenance-v1', 'scope': 'native-engine-diagnostic-build-host-only', 'original_proof': self.original_ref, 'derived_files': {'observer': {'kind': 'source-copy', 'retained': self.file(self.host_root / 'observer.py'), 'source': self.ref(self.base / 'observer-original.py')}, 'gperf': {'kind': 'byte-copy', 'retained': self.file(self.host_root / 'bin/gperf'), 'origin': self.package_origin('gperf', 'usr/bin/gperf')}, 'ruby': {'kind': 'byte-copy', 'retained': self.file(self.host_root / 'bin/ruby'), 'origin': self.package_origin('ruby3.3', 'usr/bin/ruby3.3')}}, 'operating_system_providers': {}}
        providers = {}
        for name in ('libc', 'loader'):
            self.wrapper['derived_files'][name] = {'kind': 'source-copy', 'retained': self.file(self.host_root / 'runtime' / name), 'source': self.ref(self.base / ('original-' + name))}
            providers[name] = {'logical_path': '/observed-os/runtime/' + name, 'resolved_path': '/observed-os/runtime/' + name, 'retained': self.file(self.host_root / 'runtime' / name), 'origin': {'kind': 'derived', 'id': name}}
        modules = {'python': {'pyjson': self.provider(self.sdk_root / 'lib/python/json/__init__.py', {'kind': 'sdk', 'path': 'lib/python/json/__init__.py'}, '/observed/python/json.py')}, 'perl': {'perljson': self.provider(self.sdk_root / 'lib/perl/JSON/PP.pm', {'kind': 'sdk', 'path': 'lib/perl/JSON/PP.pm'}, '/observed/perl/JSON/PP.pm')}, 'ruby': {'rbjson': self.provider(self.host_root / 'lib/ruby/json.rb', self.package_origin('libruby3.3', 'usr/lib/ruby/json.rb'), '/observed/ruby/json.rb'), 'rbempty': self.provider(self.host_root / 'lib/ruby/empty.rb', self.package_origin('libruby3.3', 'usr/lib/ruby/empty.rb'), '/observed/ruby/empty.rb')}}
        loaded = {role: {'providers': ['libc', 'loader'], 'modules': sorted(modules[role]) if role in modules else []} for role in self.roles}
        self.environment = self.independent_environment()
        self.raw_subjects = {}
        commands = {'host': None, 'subjects': {}}
        expected_host = json.loads(self.policy_raw)['execution_host']
        self.raw_host = {'schema_version': 1, 'kind': 'foundation-native-diagnostic-host-raw-v1', 'host': expected_host, 'libc_provider': 'libc', 'loader_provider': 'loader'}
        commands['host'] = self.command('host', self.raw_host)
        for role in self.roles:
            raw = {'schema_version': 1, 'kind': 'foundation-native-diagnostic-subject-raw-v1', 'role': role, 'program': copy.deepcopy(self.programs[role]), 'search_paths': copy.deepcopy(self.runtime_facts[role]['search_paths']) if role in modules else [], 'loaded_module_paths': sorted((item['resolved_path'] for item in modules.get(role, {}).values())), 'loaded_provider_paths': sorted((item['resolved_path'] for item in providers.values()))}
            self.raw_subjects[role] = raw
            commands['subjects'][role] = self.command(role, raw)
        os_release = b'ID=debian\nVERSION_ID="13"\nVERSION_CODENAME=trixie\n'
        self.put(self.base / 'os-release', os_release)
        self.observed = {'schema_version': 1, 'kind': 'foundation-native-diagnostic-build-host-observations-v1', 'scope': 'native-engine-diagnostic-build-host-only', 'policy_id': json.loads(self.policy_raw)['policy_id'], 'observed_utc': '2026-10-16T01:00:00.500000Z', 'subjects': {'programs': copy.deepcopy(self.programs), 'inventory_documents': {'sdk': {'root': str(self.sdk_root), 'manifest_sha256': self.sdk_inventory['files']['sdk.json']}, 'extensions': {'host-extra': self.host_ref}}, 'interpreter_facts': self.fact_refs}, 'host': dict(expected_host, os_release=self.ref(self.base / 'os-release')), 'runtime': {'providers': providers, 'modules': modules, 'loaded_by_subject': loaded}, 'commands': commands, 'ownership': self.ownership(), 'production_eligible': False, 'native_engine_execution': False, 'kernel_rebuild': False}
        self.wrapper['operating_system_providers'] = copy.deepcopy(providers)
        self.host_document = {'schema_version': 1, 'kind': native.DIAGNOSTIC_HOST_KIND, 'programs': copy.deepcopy(self.programs), 'module_inventories': {'extra': self.host_ref}, 'interpreter_bindings': self.fact_refs, 'diagnostic_host': {}, 'source_provenance': {}}
        self.binding = {'root': str(self.sdk_root), 'sdk_manifest_sha256': self.sdk_inventory['files']['sdk.json'], 'policy': {'runtime': {'c_library_baseline': '2.36'}, 'cpu': json.loads(self.policy_raw)['cpu'], 'source_date_epoch': '1760659200'}, 'host_document': None}
        self.toolchain = {'kind': 'foundation-native-engine-prototype-sdk-toolchain-v1', 'sdk_binding': self.binding, 'inventories': {'sdk': self.sdk_inventory}, 'tools': self.tools}
        self.host = dict(self.host_document, programs=self.programs, module_inventories={'extra': self.host_inventory}, interpreter_runtimes=self.runtime_facts)
        self.seal()

    @staticmethod
    def ownership():
        return {'closed': True, 'descendants_closed': True, 'logs_closed': True}

    def put(self, path, raw, mode=420):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in path.parents:
            if parent == self.root.parent:
                break
            parent.chmod(493)
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def program(self, path, name, version):
        raw = ('INERT synthetic executable bytes ' + name + '\n').encode()
        self.put(path, raw, 493)
        return {'path': str(path), 'sha256': diag_digest(raw), 'version': version}

    def ref(self, path):
        path = Path(path)
        return {'path': path.relative_to(self.base).as_posix(), 'sha256': diag_digest(path.read_bytes())}

    def document(self, name, value):
        path = self.put(self.base / name, diag_encoded(value))
        return self.ref(path)

    def inventory(self, root, name):
        files, directories, modes = ({}, [], {})
        for path in sorted(root.rglob('*')):
            member = path.relative_to(root).as_posix()
            if path.is_dir():
                directories.append(member)
                modes[member] = 493
            else:
                files[member] = diag_digest(path.read_bytes())
                modes[member] = path.stat().st_mode & 511
        value = {'files': files, 'directories': directories, 'modes': modes}
        reference = {'root': str(root), 'inventory': self.document(name, value)}
        normalized = dict(value, root=str(root), inventory=reference['inventory'])
        return (reference, normalized)

    def file(self, path):
        path = Path(path)
        return {'path': str(path), 'sha256': diag_digest(path.read_bytes()), 'bytes': path.stat().st_size, 'inventory': 'sdk' if self.sdk_root in path.parents else 'host-extra'}

    @staticmethod
    def package_origin(package, member):
        return {'kind': 'package', 'package': package, 'member': member}

    def member(self, package, member, path):
        path = Path(path)
        self.packages[package]['members'][member] = {'sha256': diag_digest(path.read_bytes()), 'size': path.stat().st_size, 'mode': path.stat().st_mode & 511}

    def provider(self, path, origin, observed):
        return {'logical_path': observed, 'resolved_path': observed, 'retained': self.file(path), 'origin': origin}

    def independent_environment(self):
        paths = {str(Path(item['path']).parent) for item in list(self.tools.values()) + list(self.programs.values())}
        value = {'PATH': ':'.join(sorted(paths)), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC', 'SOURCE_DATE_EPOCH': '1760659200'}
        for role, variable in (('python', 'PYTHONPATH'), ('perl', 'PERL5LIB'), ('ruby', 'RUBYLIB')):
            value[variable] = ':'.join(self.runtime_facts[role]['search_paths'])
        return value

    def command(self, role, raw):
        prefix = [self.programs['python']['path'], '-I', '-B', str(self.host_root / 'observer.py')]
        argv = prefix + (['--observe-host'] if role == 'host' else ['--observe-subject', role, '--program', self.programs[role]['path']])
        return {'argv': argv, 'environment': copy.deepcopy(self.environment), 'cwd': str(self.root / 'workspace'), 'returncode': 0, 'stdout': self.document('raw/' + role + '.stdout.json', raw), 'stderr': self.document('raw/' + role + '.stderr.json', None), 'started_utc': '2026-10-16T01:00:00Z', 'finished_utc': '2026-10-16T01:00:01Z', 'ownership': self.ownership()}

    def seal(self):
        """Reseal synthetic originals before a fresh InputSet captures anything."""
        self.observed['commands']['host']['stdout'] = self.document('raw/host.stdout.json', self.raw_host)
        for role, raw in self.raw_subjects.items():
            if role in self.observed['commands']['subjects']:
                self.observed['commands']['subjects'][role]['stdout'] = self.document('raw/' + role + '.stdout.json', raw)
        self.host_document['diagnostic_host'] = self.document('observations.json', self.observed)
        self.host_document['source_provenance'] = self.document('provenance.json', self.wrapper)
        self.binding['host_document'] = copy.deepcopy(self.host_document)
        self.host.update(self.host_document)
        self.host['module_inventories'] = {'extra': self.host_inventory}
        self.host['interpreter_runtimes'] = self.runtime_facts

    def inputs(self, admit_host=True):
        native = self.native

        class TrackedInputSet(native.InputSet):

            def __init__(self):
                super().__init__()
                self.inventory_calls = []

            def inventory(self, record, base, role):
                self.inventory_calls.append((copy.deepcopy(record), str(base), role))
                return super().inventory(record, base, role)
        inputs = TrackedInputSet()
        inputs.inventory(self.sdk_ref, self.base, 'toolchain-sdk')
        if admit_host:
            inputs.inventory(self.host_ref, self.base, 'host-extra')
        inputs.inventory_calls.clear()
        return inputs

    def fake_original(self, launch_ref, base, inputs, **authority):
        self.helper_calls.append((copy.deepcopy(launch_ref), str(base), dict(authority)))
        capture = self.original._Capture(inputs)
        capture.inventory(self.body_ref, self.base, 'diagnostic-body-packages')
        inventories = capture.finish()
        return {'launch': {'path': str(self.base / launch_ref['path']), 'sha256': launch_ref['sha256']}, 'proof': copy.deepcopy(self.proof_ref), 'packages': copy.deepcopy(self.packages), 'external_inventories': inventories}

    @contextmanager
    def mocked_boundaries(self, allow_unproved=True, helper=None):
        """Mock exactly the absent authorities and fixed proof, never SDK admission."""
        n = self.native
        authority = n._DiagnosticOriginalAuthority(n._DIAGNOSTIC_AUTHORITY_VERSION, '1' * 64, '2' * 64)
        terminal = n._diagnostic_terminal_authority

        def explicit_terminal_boundary(origin, role, path):
            if allow_unproved and origin['terminal'] == 'unproved-copy':
                self.boundary_calls.append((role, str(path)))
                return None
            return terminal(origin, role, path)
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(n, '_DIAGNOSTIC_ORIGINAL_AUTHORITY', authority))
            stack.enter_context(mock.patch.object(n, '_DIAGNOSTIC_AUTHORED_SOURCES', ((n._DIAGNOSTIC_SOURCE_AUTHORITY_VERSION, 'observer', diag_digest(self.observer_raw)),)))
            stack.enter_context(mock.patch.object(self.original, '_diagnostic_original_proof', side_effect=helper or self.fake_original))
            stack.enter_context(mock.patch.object(n, '_diagnostic_terminal_authority', side_effect=explicit_terminal_boundary))
            yield

    def validate(self, inputs=None):
        return self.native.validate_diagnostic_host(self.host_document, self.base, inputs or self.inputs(), self.toolchain, self.host, policy_raw=self.policy_raw)

class NativeDiagnosticHost(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()
        name = 'appended_engine_native_original_proof'
        old = sys.modules.get(name)
        cls.original = types.ModuleType(name)
        cls.original.__file__ = str(ROOT / 'tools/appended_engine_native_original_proof.py')
        sys.modules[name] = cls.original

        def restore():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        cls.addClassCleanup(restore)
        exec(compile(Path(cls.original.__file__).read_bytes(), cls.original.__file__, 'exec'), cls.original.__dict__)

    def setUp(self):
        guards = ExitStack()
        self.addCleanup(guards.close)
        for target in ('subprocess.Popen', 'os.system', 'os.execv', 'os.execve', 'os.execvp', 'os.execvpe', 'os.execl', 'os.execlp', 'os.posix_spawn', 'os.posix_spawnp', 'socket.socket', 'socket.create_connection'):
            guards.enter_context(mock.patch(target, create=True, side_effect=AssertionError('Synthetic diagnostic admission attempted a process/network launch')))
        self.temporary = tempfile.TemporaryDirectory(prefix='diagnostic-inert-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = self.new_fixture('baseline')

    def new_fixture(self, name):
        return DiagnosticSyntheticFixture(self.root / name, self.api, self.original)

    def parse(self, fixture, inputs):
        return self.api.parse_host_tools(fixture.host_document, fixture.base, inputs, fixture.toolchain, repository_root=fixture.root)

    def test_absent_authorities_precede_extension_inventory_and_helper(self):
        f = self.fixture
        inputs = f.inputs(admit_host=False)
        with mock.patch.object(self.api, '_DIAGNOSTIC_ORIGINAL_AUTHORITY', None), mock.patch.object(self.original, '_diagnostic_original_proof') as helper:
            with self.assertRaises(self.api.MissingInputs) as raised:
                self.parse(f, inputs)
        self.assertEqual(raised.exception.roles, ('diagnostic-original-source-authority', 'diagnostic-original-launch-authority'))
        self.assertEqual(inputs.inventory_calls, [])
        helper.assert_not_called()

    def test_submitted_launch_pins_cannot_install_authority(self):
        f = self.fixture
        f.wrapper['original_proof'] = f.document('proof-launch.json', {'producer': {'source_closure_sha256': '1' * 64, 'launch_policy_sha256': '2' * 64}, 'success': True, 'production_eligible': True})
        f.seal()
        inputs = f.inputs(admit_host=False)
        with mock.patch.object(self.api, '_DIAGNOSTIC_ORIGINAL_AUTHORITY', None), mock.patch.object(self.original, '_diagnostic_original_proof') as helper:
            with self.assertRaises(self.api.MissingInputs) as raised:
                self.parse(f, inputs)
        self.assertEqual(set(raised.exception.roles), {'diagnostic-original-source-authority', 'diagnostic-original-launch-authority'})
        self.assertEqual(inputs.inventory_calls, [])
        helper.assert_not_called()

    def test_existing_host_kinds_retain_their_closed_field_sets(self):
        for sdk in (False, True):
            for extra in ('diagnostic_host', 'source_provenance'):
                with self.subTest(sdk=sdk, extra=extra):
                    f = self.fixture
                    value = {name: copy.deepcopy(f.host_document[name]) for name in ('schema_version', 'programs', 'module_inventories')}
                    value['kind'] = 'foundation-native-engine-prototype-sdk-host-tools-v1' if sdk else 'foundation-native-engine-prototype-host-tools-v1'
                    if sdk:
                        value['interpreter_bindings'] = copy.deepcopy(f.fact_refs)
                    value[extra] = copy.deepcopy(f.host_document[extra])
                    inputs = f.inputs(admit_host=False)
                    with self.assertRaises(ValueError):
                        self.api.parse_host_tools(value, f.base, inputs, f.toolchain)
                    self.assertEqual(inputs.inventory_calls, [])

    def test_complete_all_role_join_is_synthetic_and_keeps_opaque_bodies_external(self):
        f = self.fixture
        inputs = f.inputs()
        with f.mocked_boundaries():
            result = f.validate(inputs)
        self.assertEqual(set(result), {'observations', 'provenance', 'policy', 'policy_sha256', 'host', 'runtime', 'environment', 'external_inventories'})
        self.assertEqual(result['environment'], f.independent_environment())
        self.assertEqual(set(result['runtime']['loaded_by_subject']), set(f.roles))
        self.assertEqual(len(f.helper_calls), 1)
        self.assertEqual(f.helper_calls[0], (f.wrapper['original_proof'], str(f.base), {'approved_source_closure_sha256': '1' * 64, 'approved_launch_policy_sha256': '2' * 64}))
        self.assertEqual({path for _, path in f.boundary_calls}, {str(f.host_root / 'runtime/libc'), str(f.host_root / 'runtime/loader')})
        self.assertEqual(result['external_inventories'], [{'root': str(f.body_root), 'inventory': {'path': str(f.base / 'body-inventory.json'), 'sha256': f.body_ref['inventory']['sha256']}}])
        body_path = str(f.body_root / 'Packages')
        body = next((item for item in inputs.records if item['path'] == body_path))
        self.assertTrue(body['roles'])
        self.assertTrue(all((role.startswith('diagnostic-body-') for role in body['roles'])))
        self.assertNotIn(body_path, {str(path) for _, path, _ in self.api._record_aliases(inputs.records)})
        inputs.recheck()

    def test_raw_sdk_environment_and_provider_contradictions_fail(self):

        def wrong_raw(f):
            f.raw_subjects['gperf']['role'] = 'ruby'

        def wrong_sdk(f):
            f.observed['subjects']['inventory_documents']['sdk']['manifest_sha256'] = 'f' * 64

        def wrong_environment(f):
            f.observed['commands']['subjects']['perl']['environment']['PERL5LIB'] = '/outside'

        def wrong_provider(f):
            f.observed['runtime']['providers']['libc']['retained']['sha256'] = 'f' * 64
            f.wrapper['operating_system_providers'] = copy.deepcopy(f.observed['runtime']['providers'])
        for label, mutate in (('raw', wrong_raw), ('sdk', wrong_sdk), ('environment', wrong_environment), ('provider', wrong_provider)):
            with self.subTest(label=label):
                f = self.new_fixture('contradiction-' + label)
                mutate(f)
                f.seal()
                with f.mocked_boundaries(), self.assertRaises(ValueError) as raised:
                    f.validate()
                self.assertNotIsInstance(raised.exception, self.api.MissingInputs)

    def test_derivation_cycles_and_nested_duplicate_retained_paths_fail(self):
        for label in ('cycle', 'duplicate-path'):
            with self.subTest(label=label):
                f = self.new_fixture('derivation-' + label)
                records = f.wrapper['derived_files']
                if label == 'cycle':
                    records['gperf']['origin'] = {'kind': 'derived', 'id': 'gperf'}
                else:
                    records['gperf-original'] = copy.deepcopy(records['gperf'])
                    records['gperf']['origin'] = {'kind': 'derived', 'id': 'gperf-original'}
                f.seal()
                with f.mocked_boundaries(), self.assertRaises(ValueError) as raised:
                    f.validate()
                self.assertNotIsInstance(raised.exception, self.api.MissingInputs)

    def test_partial_subject_maps_are_named_missing_inputs(self):
        for label in ('programs', 'loaded', 'commands'):
            with self.subTest(label=label):
                f = self.new_fixture('partial-' + label)
                maps = {'programs': f.observed['subjects']['programs'], 'loaded': f.observed['runtime']['loaded_by_subject'], 'commands': f.observed['commands']['subjects']}
                maps[label].pop('sh')
                f.seal()
                with f.mocked_boundaries(), self.assertRaises(self.api.MissingInputs) as raised:
                    f.validate()
                self.assertIn('diagnostic-host-subject-sh', raised.exception.roles)

    def test_helper_local_missing_records_are_translated_exactly(self):
        f = self.fixture
        records = [{'role': 'diagnostic-original-alias-target', 'path': '/synthetic/member', 'reason': 'original selection absent', 'preserved_extension': 'opaque'}]

        def missing(*args, **kwargs):
            raise self.original.MissingInputs(records)
        with f.mocked_boundaries(helper=missing), self.assertRaises(self.api.MissingInputs) as raised:
            f.validate()
        self.assertIs(type(raised.exception), self.api.MissingInputs)
        self.assertEqual(raised.exception.missing, tuple(records))

    def test_zero_byte_member_and_alias_use_regular_facts_and_normalized_origin(self):
        f = self.fixture
        regular = 'usr/lib/ruby/empty.rb'
        alias = 'usr/lib/ruby/empty-alias.rb'
        package = f.packages['libruby3.3']
        package['link_origins'][alias] = {'type': 'symlink', 'target': 'empty.rb'}
        f.wrapper['derived_files']['empty-regular'] = {'kind': 'byte-copy', 'retained': f.file(f.host_root / 'lib/ruby/empty.rb'), 'origin': f.package_origin('libruby3.3', regular)}
        f.wrapper['derived_files']['empty-alias'] = {'kind': 'logical-alias', 'logical_path': '/observed/ruby/empty-alias.rb', 'resolved_path': '/observed/ruby/empty.rb', 'origin': {'kind': 'derived', 'id': 'empty-regular'}}
        provider = {'logical_path': '/observed/ruby/empty-alias.rb', 'resolved_path': '/observed/ruby/empty.rb', 'retained': f.file(f.host_root / 'lib/ruby/empty.rb'), 'origin': f.package_origin('libruby3.3', alias)}
        with f.mocked_boundaries():
            origins = self.api._DiagnosticOrigins(f.wrapper, f.base, f.inputs(), {'sdk': f.sdk_inventory, 'host-extra': f.host_inventory}, f.sdk_inventory, f.packages)
            _, retained, fact = self.api._diagnostic_provider(provider, origins, 'module')
        self.assertEqual(retained['bytes'], 0)
        self.assertEqual(retained['sha256'], diag_digest(b''))
        self.assertEqual(fact['mode'], 420)
        self.assertEqual(fact['alias']['literal_target'], 'empty.rb')
        self.assertEqual(fact['member'], regular)

    def test_unique_input_cap_fails_before_common_extension_inventory(self):
        f = self.fixture
        inputs = f.inputs(admit_host=False)
        metadata_bytes = (f.base / 'body-inventory.json').stat().st_size
        body_bytes = (f.body_root / 'Packages').stat().st_size
        with f.mocked_boundaries(), mock.patch.dict(self.original.LIMITS, {'unique_opaque_body_bytes': metadata_bytes + body_bytes - 1}):
            with self.assertRaises(ValueError):
                self.parse(f, inputs)
        self.assertEqual(len(f.helper_calls), 1)
        self.assertEqual(inputs.inventory_calls, [])

    def test_prior_sdk_and_partial_prospective_extension_overlap_fail_before_walk(self):
        for label in ('prior-sdk', 'partial-prospective-host'):
            with self.subTest(label=label):
                f = self.new_fixture('overlap-' + label)
                if label == 'prior-sdk':
                    f.body_ref = copy.deepcopy(f.sdk_ref)
                else:
                    f.host_document['module_inventories']['extra'] = {'root': str(f.body_root / 'nested'), 'inventory': f.host_ref['inventory']}
                    f.binding['host_document'] = copy.deepcopy(f.host_document)
                inputs = f.inputs(admit_host=False)
                with f.mocked_boundaries(), self.assertRaises(ValueError):
                    self.parse(f, inputs)
                self.assertEqual(len(f.helper_calls), 1)
                self.assertEqual([item for item in inputs.inventory_calls if item[2].startswith('host-')], [])
                if label == 'prior-sdk':
                    self.assertEqual(inputs.inventory_calls, [])

    def test_c1_paths_and_metadata_body_reclassification_are_rejected(self):
        for value in ('/observed/\x85bad', '/observed/\x9fbad'):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                self.api._diagnostic_absolute(value)
        f = self.fixture
        for first, second in (('diagnostic-body-derived', 'diagnostic-provenance-source'), ('diagnostic-provenance-source', 'diagnostic-body-derived')):
            with self.subTest(first=first):
                inputs = self.api.InputSet()
                path = f.base / 'observer-original.py'
                pin = diag_digest(path.read_bytes())
                self.api._diagnostic_capture(inputs, path, pin, first)
                with self.assertRaises(ValueError):
                    self.api._diagnostic_capture(inputs, path, pin, second)

    def test_wrong_selected_helper_source_fails_before_delegation(self):
        f = self.fixture
        f.put(f.root / 'tools/appended_engine_native_original_proof.py', b'# Wrong retained control source.\n')
        inputs = f.inputs(admit_host=False)
        with f.mocked_boundaries(), self.assertRaises(ValueError) as changed:
            self.parse(f, inputs)
        self.assertNotIsInstance(changed.exception, self.api.MissingInputs)
        self.assertEqual(f.helper_calls, [])
        self.assertEqual(inputs.inventory_calls, [])
        self.assertFalse(any(('diagnostic-body-packages' in item['roles'] for item in inputs.records)))

    def test_wrong_imported_helper_source_fails_before_delegation(self):
        f = self.fixture
        imported = f.root / 'imported/tools/appended_engine_native_original_proof.py'
        f.put(imported, b'# Wrong imported control source.\n')
        inputs = f.inputs(admit_host=False)
        with f.mocked_boundaries(), mock.patch.object(self.original, '__file__', str(imported)):
            with self.assertRaises(ValueError) as changed:
                self.parse(f, inputs)
        self.assertNotIsInstance(changed.exception, self.api.MissingInputs)
        self.assertEqual(f.helper_calls, [])
        self.assertEqual(inputs.inventory_calls, [])

    def test_correct_both_helper_sources_are_captured_before_exact_delegation(self):
        f = self.fixture
        inputs = f.inputs(admit_host=False)
        imported = str(Path(self.original.__file__))
        selected = str(f.root / 'tools/appended_engine_native_original_proof.py')
        expected = '73ab3f22855e7d647e6259004288fe3fc0754b38aa19d7abfd513fff705e8fd8'
        authority = self.api._DiagnosticOriginalAuthority(self.api._DIAGNOSTIC_AUTHORITY_VERSION, '1' * 64, '2' * 64)

        def closed_original_boundary(launch, base, capture, **pins):
            rows = {row['path']: row for row in inputs.records}
            for path in (imported, selected):
                self.assertIn(path, rows)
                self.assertEqual(rows[path]['sha256'], expected)
                self.assertEqual(rows[path]['mode'], 420)
            self.assertEqual(pins, {'approved_source_closure_sha256': '1' * 64, 'approved_launch_policy_sha256': '2' * 64})
            return f.fake_original(launch, base, capture, **pins)
        with mock.patch.object(self.api, '_DIAGNOSTIC_ORIGINAL_AUTHORITY', authority), mock.patch.object(self.original, '_diagnostic_original_proof', side_effect=closed_original_boundary):
            preflight = self.api._diagnostic_host_preflight(f.host_document, f.base, inputs, f.toolchain, repository_root=f.root)
        self.assertIsInstance(preflight, self.api._DiagnosticHostPreflight)
        self.assertEqual(preflight._repository_root, str(f.root))
        self.assertEqual(len(f.helper_calls), 1)
        self.assertEqual([item for item in inputs.inventory_calls if item[2].startswith('host-')], [])
        with self.assertRaises(ValueError):
            self.api._diagnostic_preflight_records(preflight, f.host_document, f.base, inputs, f.toolchain, authority, repository_root=f.root / 'different')
CHECKED_RECORD_LIMITS = dict(seconds=10, maximum_archive_bytes=8 * 1024 ** 3, maximum_expanded_bytes=32 * 1024 ** 3, maximum_members=1000000, maximum_member_bytes=256 * 1024 ** 2, maximum_patch_bytes=32 * 1024 ** 2)

def checked_record_fixture(owner, retained=True):
    """Valid tiny original Git/link/proof facts, all visibly synthetic."""
    cls = NativeRetainedOriginalEvidence if retained else NativeSourceProvenance
    case = cls()
    case.api = owner.api
    case.setUp()
    owner.addCleanup(case.doCleanups)
    projection, inputs, facts = case.fixture()
    base = case.f.root
    value = {name: copy.deepcopy(projection[name]) for name in ('schema_version', 'kind', 'suppliers', 'archives', 'projection', 'patches', 'notices', 'provenance')}
    for row in list(value['archives'].values()) + value['patches'] + value['notices'] + value['provenance']:
        row['path'] = Path(row['path']).relative_to(base).as_posix()

    def record(ref):
        path = base / ref['path']
        old = inputs._records[str(path)]
        raw = path.read_bytes()
        return {'path': ref['path'], 'sha256': old['sha256'], 'bytes': old['bytes'], 'mode': old['mode'], 'raw': raw}
    records = {'archives': {}, 'provenance': {ref['role']: record(ref) for ref in value['provenance']}, 'patches': [record(ref) for ref in value['patches']], 'notices': [record(ref) for ref in value['notices']]}
    streams = {}
    for name, ref in value['archives'].items():
        item = record(ref)
        streams[name] = io.BytesIO(item.pop('raw'))
        records['archives'][name] = item
    originals = {}
    if retained:
        body = facts['body']
        parent = (base / records['provenance']['engine-body-verification']['path']).parent
        for role, ref in body['original_proof'].items():
            raw = (parent / ref['path']).read_bytes()
            originals[role] = dict(ref, mode=420, raw=raw)
    return (value, records, streams, originals, projection, inputs)

class NativeCheckedSourceRecords(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def check(self, value, records, streams, limits=CHECKED_RECORD_LIMITS):
        with no_programs(), mock.patch('os.open', side_effect=AssertionError('path open')):
            return self.api.parse_source_projection_records(value, records, streams, limits)

    def test_real_semantic_core_derives_same_files_without_paths_or_stream_ownership(self):
        value, records, streams, originals, legacy, inputs = checked_record_fixture(self)
        for stream in streams.values():
            stream.seek(5)
        checked = self.check(value, records, streams)
        view = checked.as_dict()
        self.assertEqual(set(view['_files']), set(legacy['_files']))
        self.assertEqual(view['_links'], legacy['_links'])
        for name in view['_files']:
            self.assertEqual({key: view['_files'][name][key] for key in ('archive', 'member', 'sha256', 'bytes', 'mode', 'regular_member')}, {key: legacy['_files'][name][key] for key in ('archive', 'member', 'sha256', 'bytes', 'mode', 'regular_member')})
        self.assertTrue(all((not stream.closed for stream in streams.values())))
        view['_files'].clear()
        self.assertTrue(checked.as_dict()['_files'])

    def test_retained_seven_originals_and_eight_links_join_same_facts(self):
        value, records, streams, originals, legacy, inputs = checked_record_fixture(self)
        checked = self.check(value, records, streams)
        with no_programs(), mock.patch('os.open', side_effect=AssertionError('path open')):
            actual = self.api.validate_source_provenance_records(checked, records['provenance'], originals)
        expected = self.api.validate_source_provenance(legacy, inputs)
        for key in ('commit', 'archive_sha256', 'regular_blobs', 'normalized_links', 'source_bytes', 'evidence_kind'):
            self.assertEqual(actual[key], expected[key])
        self.assertEqual(len(actual['original_proof']), 7)
        self.assertEqual(actual['normalized_links'], 8)
        self.assertFalse(actual['source_body_execution'])

    def test_legacy_clean_body_accepts_no_originals_and_does_not_invent_retained_evidence(self):
        value, records, streams, originals, legacy, inputs = checked_record_fixture(self, retained=False)
        checked = self.check(value, records, streams)
        actual = self.api.validate_source_provenance_records(checked, records['provenance'], {})
        self.assertNotIn('evidence_kind', actual)
        with self.assertRaises(ValueError):
            self.api.validate_source_provenance_records(checked, records['provenance'], {'recipe': {}})

    def test_constructor_dictionary_and_uninitialized_type_cannot_mint_checked_state(self):
        with self.assertRaises(TypeError):
            self.api.CheckedSourceProjection()
        for value in ({}, object.__new__(self.api.CheckedSourceProjection)):
            with self.assertRaises(ValueError):
                self.api.validate_source_provenance_records(value, {}, {})

    def test_wrong_capture_hash_bytes_mode_role_and_order_are_rejected(self):
        mutations = (lambda r: r['archives']['engine'].update(sha256='1' * 64), lambda r: r['archives']['engine'].update(bytes=1), lambda r: r['archives']['engine'].update(mode=436), lambda r: r['provenance'].update(extra=dict(next(iter(r['provenance'].values())))), lambda r: r['notices'].append(copy.deepcopy(r['notices'][0])), lambda r: r['provenance']['git-controls'].update(raw=b'not the captured raw'))
        for mutate in mutations:
            with self.subTest(mutate=repr(mutate)):
                value, records, streams, *_ = checked_record_fixture(self)
                mutate(records)
                with self.assertRaises(ValueError):
                    self.check(value, records, streams)

    def test_lower_caps_and_deadline_never_expand_shared_limits(self):
        for key, number in (('maximum_archive_bytes', 1), ('maximum_expanded_bytes', 1), ('maximum_members', 1), ('maximum_member_bytes', 1)):
            with self.subTest(key=key):
                value, records, streams, *_ = checked_record_fixture(self)
                with self.assertRaises(ValueError):
                    self.check(value, records, streams, dict(CHECKED_RECORD_LIMITS, **{key: number}))
        value, records, streams, *_ = checked_record_fixture(self)
        checked = self.check(value, records, streams)
        with mock.patch.object(self.api.time, 'monotonic', return_value=checked._deadline):
            with self.assertRaises(ValueError):
                self.api.validate_source_provenance_records(checked, records['provenance'], {})

    def test_original_proof_spelling_pin_mode_and_captured_provenance_are_bound(self):
        for change in ('path', 'sha256', 'mode', 'provenance'):
            with self.subTest(change=change):
                value, records, streams, originals, *_ = checked_record_fixture(self)
                checked = self.check(value, records, streams)
                if change == 'provenance':
                    records['provenance']['git-controls']['raw'] += b'changed'
                else:
                    originals['recipe'][change] = {'path': 'other.json', 'sha256': '1' * 64, 'mode': 493}[change]
                with self.assertRaises(ValueError):
                    self.api.validate_source_provenance_records(checked, records['provenance'], originals)

    def test_old_target_refusal_and_capture_fingerprint_remain_strict(self):
        value, records, streams, originals, legacy, inputs = checked_record_fixture(self)
        with self.assertRaises(ValueError):
            self.api.parse_source_projection(value, Path('/SYNTHETIC'), inputs, dict(TARGET, system='Windows'))
        with self.assertRaises(ValueError):
            self.api.validate_source_provenance(copy.deepcopy(legacy), inputs)
        legacy['projection']['files'].clear()
        with self.assertRaises(ValueError):
            self.api.validate_source_provenance(legacy, inputs)

    def test_archive_A_pin_cannot_admit_archive_B_member_parse(self):
        value, records, streams, *_ = checked_record_fixture(self)
        original = streams['engine'].getvalue()
        changed = bytearray(original)
        changed[4] ^= 1

        class Switching:

            def __init__(self):
                self.current = io.BytesIO(original)
                self.changed = False

            def seek(self, *args):
                return self.current.seek(*args)

            def read(self, maximum=-1):
                raw = self.current.read(maximum)
                if not raw and (not self.changed):
                    self.current = io.BytesIO(bytes(changed))
                    self.current.seek(len(changed))
                    self.changed = True
                return raw
        streams['engine'] = Switching()
        with self.assertRaisesRegex(ValueError, 'changed between capture and member parsing'):
            self.check(value, records, streams)

    def test_zip_seek_reads_are_chunk_bound_and_leave_caller_streams_open(self):
        value, records, streams, *_ = checked_record_fixture(self)
        for name, stream in list(streams.items()):
            result = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='r:gz') as archive, zipfile.ZipFile(result, mode='w') as output:
                for member in archive:
                    if member.isdir():
                        continue
                    info = zipfile.ZipInfo(member.name)
                    info.external_attr = (41471 if member.issym() else 33188) << 16
                    output.writestr(info, member.linkname.encode() if member.issym() else archive.extractfile(member).read())
            raw = result.getvalue()
            ref = value['archives'][name]
            ref.update(format='zip', sha256=digest(raw), bytes=len(raw))
            records['archives'][name].update(sha256=ref['sha256'], bytes=len(raw))
            streams[name] = io.BytesIO(raw)
        checked = self.check(value, records, streams)
        self.assertEqual(checked.as_dict()['_links']['engine'], {key: item[0] for key, item in SYNTHETIC_LINK_LITERALS.items()})
        self.assertTrue(all((not stream.closed for stream in streams.values())))

    def test_normalized_link_copies_cannot_exceed_expanded_logical_cap(self):
        value, records, streams, *_ = checked_record_fixture(self)
        unique = {}
        for ref in value['projection']['files'].values():
            regular = value['projection']['normalizations'][ref['archive']].get(ref['member'], ref['member'])
            unique[ref['archive'], regular] = ref['bytes']
        raw_bytes = sum(unique.values())
        self.assertGreater(sum((ref['bytes'] for ref in value['projection']['files'].values())), raw_bytes + 1)
        with self.assertRaisesRegex(ValueError, 'expanded logical byte bound'):
            self.check(value, records, streams, dict(CHECKED_RECORD_LIMITS, maximum_expanded_bytes=raw_bytes + 1))

    def test_late_checked_serialization_cannot_return_success(self):
        value, records, streams, *_ = checked_record_fixture(self)
        original = self.api._checked_projection
        clock = [0]

        def delayed(*args):
            result = original(*args)
            clock[0] = result._deadline
            return result
        with mock.patch.object(self.api.time, 'monotonic', side_effect=lambda: clock[0]), mock.patch.object(self.api, '_checked_projection', side_effect=delayed):
            with self.assertRaisesRegex(ValueError, 'deadline expired'):
                self.check(value, records, streams)

    def test_historical_POSIX_identity_spellings_keep_old_lexical_acceptance(self):
        for name in ('/source/root', '//source/root', '/source/back\\slash'):
            self.assertEqual(str(self.api._historical_source_absolute(name)), name)
        for name in ('relative', '/source/../root', '/source//root', '/source/root\n'):
            with self.assertRaises(ValueError):
                self.api._historical_source_absolute(name)

    def test_parser_chunk_fetch_is_clamped_before_underlying_budget_overrun(self):
        raw = b'SYNTHETIC immutable compressed chunk'
        for remaining in (0, 2):
            with self.subTest(remaining=remaining):

                class Counting(io.BytesIO):

                    def read(self, requested=-1):
                        requests.append(requested)
                        return super().read(requested)
                requests = []
                owner = types.SimpleNamespace(check_deadline=lambda: None)
                pinned = self.api._PinnedSourceArchive(Counting(raw), len(raw), [hashlib.sha256(raw).digest()], owner)
                pinned._read_bytes = pinned._maximum_reads - remaining
                with self.assertRaisesRegex(ValueError, 'repeated-read budget'):
                    pinned.read(len(raw))
                self.assertEqual(requests, [] if remaining == 0 else [2])


class NativeInterpreterRuntimeData(unittest.TestCase):
    """One-interpreter normalized data never supplies source or launch authority."""

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-interpreter-data-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.files = TinyFiles(self.temporary.name)
        item = self.files.inventory('python-data', 'python', {
            'bin/python': (b'SYNTHETIC unexecuted interpreter', 0o755),
            'lib/python/json/__init__.py': (b'', 0o644),
            'lib/python/hashlib.py': (b'fixture module', 0o644),
            'lib/python/pathlib.py': (b'fixture module', 0o644)})
        inputs = self.api.InputSet()
        record = inputs.inventory(item, self.files.root, 'interpreter-data-fixture')
        self.root = Path(record['root'])
        self.inventories = {'python': record}
        self.program = {'path': str(self.root / 'bin/python'),
                        'sha256': record['files']['bin/python'], 'version': '3.9.0'}
        self.facts = {'schema_version': 1, 'kind': 'foundation-native-host-interpreter-runtime-v1',
            'program_sha256': self.program['sha256'],
            'search_paths': [str(self.root / 'lib/python')], 'runtime_inventories': ['python']}
        self.groups = (('json/__init__.py',), ('hashlib.py',), ('pathlib.py', 'pathlib/__init__.py'))

    def validate(self, facts=None, program=None, inventories=None, external=True, required_inventory=None):
        with no_programs():
            return self.api._interpreter_runtime_facts(
                self.facts if facts is None else facts, self.program if program is None else program,
                self.inventories if inventories is None else inventories, self.groups,
                external=external, required_inventory=required_inventory)

    def test_external_exact_program_and_modules_return_independent_normalized_data(self):
        result = self.validate()
        self.assertEqual(result, self.facts)
        result['search_paths'].clear()
        self.assertTrue(self.facts['search_paths'])
        self.assertEqual(set(result), {'schema_version', 'kind', 'program_sha256',
                                     'search_paths', 'runtime_inventories'})
        self.assertNotIn('production_eligible', result)
        self.assertNotIn('source_closure_sha256', result)

    def test_wrong_executable_and_unowned_program_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'another executable'):
            self.validate(dict(self.facts, program_sha256='1' * 64))
        for mutate in ('hash', 'mode', 'missing'):
            with self.subTest(mutate=mutate):
                inventories = copy.deepcopy(self.inventories)
                if mutate == 'missing': del inventories['python']['files']['bin/python']
                elif mutate == 'mode': inventories['python']['modes']['bin/python'] = 0o644
                else: inventories['python']['files']['bin/python'] = '1' * 64
                with self.assertRaisesRegex(ValueError, 'program-owning inventory'):
                    self.validate(inventories=inventories)

    def test_unknown_inventory_and_generic_required_owner_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'complete admitted inventories'):
            self.validate(dict(self.facts, runtime_inventories=['absent']))
        with self.assertRaisesRegex(ValueError, 'complete admitted inventories'):
            self.validate(external=False, required_inventory='absent')
        self.assertEqual(self.validate(external=False, required_inventory='python'), self.facts)

    def test_module_groups_are_required_with_existing_role_label(self):
        inventories = copy.deepcopy(self.inventories)
        del inventories['python']['files']['lib/python/hashlib.py']
        with self.assertRaisesRegex(ValueError, 'Required python module absent'):
            self.validate(inventories=inventories)
        with self.assertRaises(ValueError):
            self.api._interpreter_runtime_facts(self.facts, self.program, self.inventories, (), external=True)

    def test_search_paths_are_sorted_ordinary_and_contained(self):
        foreign = self.files.root / 'foreign'
        foreign.mkdir()
        for paths, error in (([str(foreign)], ValueError),
                ([str(self.root / 'lib/python')] * 2, ValueError),
                ([str(self.root / 'missing')], FileNotFoundError), (['relative'], ValueError)):
            with self.subTest(paths=paths), self.assertRaises(error):
                self.validate(dict(self.facts, search_paths=paths))

    def test_schema_and_mode_flags_do_not_change_caller_version_policy(self):
        with self.assertRaises(ValueError): self.validate(dict(self.facts, invented_authority=True))
        with self.assertRaises(ValueError): self.validate(external=1)
        # This DATA helper has no role-version policy. Both real callers retain
        # their own Python minimum before calling it, using the existing checker.
        old = dict(self.program, version='3.8.0')
        self.assertEqual(self.validate(program=old), self.facts)
        with self.assertRaisesRegex(ValueError, 'Python'):
            self.api._version(old['version'], (3, 9, 0), 'Python')



def native_current_source_fixture(owner, supplier_patch=None):
    temporary = tempfile.TemporaryDirectory(prefix='current-source-inert-')
    owner.addCleanup(temporary.cleanup)
    f = TinyFiles(temporary.name)
    recipe = owner.api.RECIPE
    records = {}

    def put(name, body, role):
        f.file(recipe + '/' + name, body)
        records[name] = dict(tracked_path=recipe + '/' + name, sha256=digest(body), bytes=len(body), mode=420, role=role, origin={'kind': 'synthetic-source-only'})
    for index in range(157):
        name = ('source/engine/Source/' if index < 48 else 'source/document-provider/') + 'inert%03d.cpp' % index
        put(name, ('SYNTHETIC source %d\n' % index).encode(), 'source')
    for index in range(25):
        put('metadata/inert%02d.bin' % index, ('inert metadata %d' % index).encode(), 'config')
    for index in range(7):
        put('metadata/extra%02d.bin' % index, ('extra %d' % index).encode(), 'config')
    for index in range(5):
        put('patches/inert%02d.patch' % index, supplier_patch if index == 0 and supplier_patch is not None else ('synthetic patch %d' % index).encode(), 'patch')
    inspector = (ROOT / recipe / 'inspect_sources.py').read_bytes()
    put('inspect_sources.py', inspector, 'helper')
    graph = ('set(_sources\n' + ''.join(('  "inert%d.cpp"\n' % i for i in range(32))) + ') # document_forms\n').encode()
    put('cmake/native-provider.cmake', graph, 'config')
    provenance = {'source_graph': {'source_files': 157, 'engine_files': 48, 'direct_translation_units': 32}, 'retained_input_mapping': {'retained/inert%02d' % i: dict(role='data', sha256=records['metadata/inert%02d.bin' % i]['sha256'], tracked_source='metadata/inert%02d.bin' % i) for i in range(25)}}
    put('provenance.json', encoded(provenance), 'provenance')
    if len(records) != 197:
        raise ValueError('Exact synthetic197 fixture required')
    value = dict(schema_version=1, kind='foundation-native-engine-actions-source-inputs', scope='native-actions-source-candidate-only', profile='actions', suppliers=dict(wrapper='68c618544e1f8af18ebce346281a6a49766aa194', engine=owner.api.ENGINE_COMMIT), provenance={'path': 'provenance.json', 'sha256': records['provenance.json']['sha256']}, requirements=['closed-retained-native-actions-source-recipe-and-provider-build', 'target-qualified-native-dependency-baseline', 'native-compile-link-runtime'], limits={'maximum_entries': 256, 'maximum_file_bytes': 8388608, 'maximum_total_bytes': 33554432}, inputs=records)
    raw_map = encoded(value)
    f.file(recipe + '/source-imports.json', raw_map)
    profile = dict(schema_version=1, kind='foundation-native-engine-prototype-profile-v1', target=dict(owner.api.TARGET), profile='document-actions-v1', scope='first-native-engine-baseline-candidate', recipe_directory=recipe, source_map={'path': recipe + '/source-imports.json', 'sha256': digest(raw_map)}, provenance={'path': recipe + '/provenance.json', 'sha256': records['provenance.json']['sha256']}, graph={'path': recipe + '/cmake/native-provider.cmake', 'sha256': records['cmake/native-provider.cmake']['sha256']}, source_files=157, engine_files=48, direct_translation_units=32, producer_inputs=list(owner.api.PRODUCERS), required_toolchain_kind=owner.api.PRIVATE_TOOLCHAIN_KIND)
    for name in owner.api.PRODUCERS:
        if name != owner.api.PROFILE:
            f.file(name, b'SYNTHETIC unexecuted producer control\n')
    raw_profile = encoded(profile)
    f.file(owner.api.PROFILE, raw_profile)
    return (f, digest(raw_profile), digest(raw_map), value)

class NativeCurrentSourceCapture(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.api = load_helper()

    def capture(self, fixture, inputs=None):
        f, profile, map_pin, _ = fixture
        return self.api.capture_current_sources(profile, map_pin, repository_root=f.root, inputs=inputs or self.api.InputSet())

    def baseline(self):
        self.api = self.api
        return checked_record_fixture(self)

    def test_complete_source_capture_keeps_only_current_facts_and_frozen_overlay_bytes(self):
        f = native_current_source_fixture(self)
        with no_programs():
            current = self.capture(f)
        facts = current.as_dict()
        self.assertEqual((facts['source_files'], facts['engine_files'], facts['direct_translation_units']), (157, 48, 32))
        self.assertEqual(len(facts['overlays']), 157)
        self.assertEqual(len(current._overlays), 157)
        self.assertEqual(sum((len(raw) for _, raw in current._overlays)), sum((x['bytes'] for x in facts['overlays'].values())))
        self.assertFalse(facts['complete_original_source_admission'])
        self.assertFalse(facts['source_tree_assembled'])
        facts['overlays'].clear()
        self.assertEqual(len(current.as_dict()['overlays']), 157)

    def test_constructor_receipt_dictionary_and_uninitialized_type_cannot_mint_authority(self):
        with self.assertRaises(TypeError):
            self.api.CheckedCurrentSources()
        with self.assertRaises(TypeError):
            self.api.CheckedNativeSourceComposition()
        for value in ({'passed': True}, object.__new__(self.api.CheckedCurrentSources)):
            with self.assertRaises(ValueError):
                self.api.compose_native_sources({}, value, {}, {})
        with self.assertRaises(ValueError):
            object.__new__(self.api.CheckedCurrentSources).as_dict()

    def test_wrong_independent_profile_map_and_actual_overlay_bytes_fail(self):
        f, pin, map_pin, value = native_current_source_fixture(self)
        for wrong_profile, wrong_map in [('1' * 64, map_pin), (pin, '1' * 64)]:
            with self.subTest(profile=wrong_profile, map=wrong_map), self.assertRaises(ValueError):
                self.api.capture_current_sources(wrong_profile, wrong_map, repository_root=f.root, inputs=self.api.InputSet())
        path = f.root / value['inputs']['source/engine/Source/inert000.cpp']['tracked_path']
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.capture((f, pin, map_pin, value))

    def test_unknown_namespace_and_prepopulated_owner_are_rejected(self):
        fixture = native_current_source_fixture(self)
        f = fixture[0]
        f.file(self.api.RECIPE + '/source/undeclared.cpp', b'unknown')
        with self.assertRaisesRegex(ValueError, 'namespace differs'):
            self.capture(fixture)
        fixture = native_current_source_fixture(self)
        f = fixture[0]
        owner = self.api.InputSet()
        extra = f.file('SDK-looking.bin', b'inert')
        owner.file(extra, digest(b'inert'), 'arbitrary-prior-input')
        with self.assertRaisesRegex(ValueError, 'fresh source-only'):
            self.capture(fixture, owner)

    def test_original_checked_projection_and_current_capture_compose_without_path_or_program(self):
        value, records, streams, originals, _, _ = self.baseline()
        original = self.api.parse_source_projection_records(value, records, streams, CHECKED_RECORD_LIMITS)
        current = self.capture(native_current_source_fixture(self, records['patches'][0]['raw']))
        with no_programs(), mock.patch('os.open', side_effect=AssertionError('pure join opened path')):
            result = self.api.compose_native_sources(original, current, records['provenance'], originals)
        facts = result.as_dict()
        self.assertEqual(facts['operations'], ['clean-original-projection', 'supplier-f259-once', 'final157-current-overlays'])
        self.assertFalse(facts['source_tree_assembled'])
        self.assertFalse(facts['compiler_or_sdk_used'])
        self.assertEqual(len(facts['overlays']), 157)

    def test_original_provenance_and_exact_single_forward_patch_remain_mandatory(self):
        value, records, streams, originals, _, _ = self.baseline()
        original = self.api.parse_source_projection_records(value, records, streams, CHECKED_RECORD_LIMITS)
        current = self.capture(native_current_source_fixture(self, records['patches'][0]['raw']))
        wrong = copy.deepcopy(records['provenance'])
        wrong['git-controls']['raw'] += b'changed'
        with self.assertRaises(ValueError):
            self.api.compose_native_sources(original, current, wrong, originals)
        fixture = native_current_source_fixture(self)
        foreign = self.capture(fixture)
        with self.assertRaisesRegex(ValueError, 'five mapped patches'):
            self.api.compose_native_sources(original, foreign, records['provenance'], originals)

    def test_current_owner_drift_is_rejected_by_wrapper_publication_recheck(self):
        fixture = native_current_source_fixture(self)
        current = self.capture(fixture)
        name, raw = current._overlays[0]
        (fixture[0].root / self.api.RECIPE / name).write_bytes(raw + b'changed')
        with self.assertRaises(ValueError):
            current._owner.recheck()
        self.assertEqual(current._overlays[0][1], raw)

    def test_original_and_current_deadlines_cannot_be_extended_by_composition(self):
        value, records, streams, originals, _, _ = self.baseline()
        original = self.api.parse_source_projection_records(value, records, streams, CHECKED_RECORD_LIMITS)
        inputs = self.api.InputSet()
        inputs.deadline = time.monotonic() + 5
        current = self.capture(native_current_source_fixture(self, records['patches'][0]['raw']), inputs)
        limit = min(original._deadline, current._deadline)
        with mock.patch.object(self.api.time, 'monotonic', return_value=limit):
            with self.assertRaisesRegex(ValueError, 'deadline expired'):
                self.api.compose_native_sources(original, current, records['provenance'], originals)

    def test_late_current_capture_serialization_cannot_return_success(self):
        fixture = native_current_source_fixture(self)
        inputs = self.api.InputSet()
        inputs.deadline = time.monotonic() + 5
        real = self.api.json.dumps
        clock = [time.monotonic()]

        def delayed(value, *args, **kwargs):
            raw = real(value, *args, **kwargs)
            if type(value) is dict and value.get('kind') == 'foundation-native-current-source-capture-v1':
                clock[0] = inputs.deadline
            return raw
        with mock.patch.object(self.api.time, 'monotonic', side_effect=lambda: clock[0]), mock.patch.object(self.api.json, 'dumps', side_effect=delayed):
            with self.assertRaisesRegex(ValueError, 'deadline expired'):
                self.capture(fixture, inputs)

    def test_late_composition_serialization_cannot_return_success(self):
        value, records, streams, originals, _, _ = self.baseline()
        original = self.api.parse_source_projection_records(value, records, streams, CHECKED_RECORD_LIMITS)
        current = self.capture(native_current_source_fixture(self, records['patches'][0]['raw']))
        limit = min(original._deadline, current._deadline)
        real = self.api.json.dumps
        clock = [time.monotonic()]

        def delayed(value, *args, **kwargs):
            raw = real(value, *args, **kwargs)
            if type(value) is dict and value.get('kind') == 'foundation-native-source-composition-v1':
                clock[0] = limit
            return raw
        with mock.patch.object(self.api.time, 'monotonic', side_effect=lambda: clock[0]), mock.patch.object(self.api.json, 'dumps', side_effect=delayed):
            with self.assertRaisesRegex(ValueError, 'deadline expired'):
                self.api.compose_native_sources(original, current, records['provenance'], originals)

    def test_current_only_capture_preserves_linux_profile_target_guard(self):
        fixture = native_current_source_fixture(self)
        f, _, map_pin, _ = fixture
        path = f.root / self.api.PROFILE
        profile = json.loads(path.read_bytes())
        profile['target']['system'] = 'Windows'
        raw = encoded(profile)
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'Linux|target|native'):
            self.api.capture_current_sources(digest(raw), map_pin, repository_root=f.root, inputs=self.api.InputSet())

    def test_current_owner_deadline_is_finite_capped_and_precedes_source_reads(self):
        fixture = native_current_source_fixture(self)
        for invalid in (float('nan'), float('inf'), True, 'later'):
            with self.subTest(invalid=invalid):
                inputs = self.api.InputSet()
                inputs.deadline = invalid
                with mock.patch.object(self.api, '_producer_bytes', side_effect=AssertionError('read before deadline validation')):
                    with self.assertRaisesRegex(ValueError, 'Finite numeric'):
                        self.capture(fixture, inputs)
        for supplied in (None, 10 ** 20):
            inputs = self.api.InputSet()
            inputs.deadline = supplied

            def boundary(*args, **kwargs):
                self.assertEqual(inputs.deadline, 86401)
                raise RuntimeError('FINITE-DEADLINE-BEFORE-READ')
            with mock.patch.object(self.api.time, 'monotonic', return_value=1), mock.patch.object(self.api, '_producer_bytes', side_effect=boundary):
                with self.assertRaisesRegex(RuntimeError, 'FINITE-DEADLINE-BEFORE-READ'):
                    self.capture(fixture, inputs)

    def test_legacy_source_capture_advances_to_same_toolchain_boundary(self):
        f, _, map_pin, _ = native_current_source_fixture(self)
        selection = {'schema_version': 1, 'kind': 'foundation-native-engine-prototype-selection-v1', 'target': dict(self.api.TARGET), 'profile': 'document-actions-v1', 'phase_limits': {'prepare_seconds': 60, 'configure_seconds': 120, 'build_seconds': 600, 'cleanup_seconds': 30, 'maximum_jobs': 2, 'maximum_output_bytes': 1048576, 'minimum_free_bytes': 1073741824, 'maximum_process_tree_bytes': 17179869184}, 'source_map': {'path': self.api.RECIPE + '/source-imports.json', 'sha256': map_pin}}
        for role in ('source_projection', 'toolchain', 'dependencies', 'host_tools', 'assets'):
            selection[role] = f.document(role + '.json', {'kind': self.api.PRIVATE_TOOLCHAIN_KIND} if role == 'toolchain' else {})
        raw = encoded(selection)
        path = f.file('selection.json', raw)
        standalone_inputs = self.api.InputSet()
        public = self.api.capture_current_sources(hashlib.sha256((f.root / self.api.PROFILE).read_bytes()).hexdigest(), map_pin, repository_root=f.root, inputs=standalone_inputs)
        results = []
        for api in (self.api,):
            observed = []

            def boundary(value, base, inputs, *args, **kwargs):
                observed.append((copy.deepcopy(value), str(base), list(inputs.records)))
                raise RuntimeError('EXACT-SYNTHETIC-TOOLCHAIN-BOUNDARY')
            with no_programs(), mock.patch.object(api, 'parse_toolchain', side_effect=boundary):
                with self.assertRaisesRegex(RuntimeError, 'EXACT-SYNTHETIC-TOOLCHAIN-BOUNDARY'):
                    api.inspect_selection(path, digest(raw), repository_root=f.root)
            self.assertEqual(len(observed), 1)
            results.append(observed[0])
        legacy_records = {row['path']: row for row in results[0][2]}
        for row in standalone_inputs.records:
            self.assertIn(row['path'], legacy_records)
            self.assertEqual({name: row[name] for name in ('sha256', 'bytes', 'mode')}, {name: legacy_records[row['path']][name] for name in ('sha256', 'bytes', 'mode')})
        self.assertEqual(public.as_dict()['source_map']['files'], 197)




def composition_catalogue_fixture(api):
    """Inert metadata rows; no mapped source, SDK or compiler body is opened."""
    value = json.loads((ROOT / api.RECIPE / 'source-imports.json').read_bytes())
    value['kind'] = api.COMPOSITION_SOURCE_KIND
    pins = {}
    for index, logical in enumerate((*api.COMPOSITION_PREDECESSORS, api.COMPOSITION_BRIDGE)):
        pins[logical] = {'sha256': format(index + 1, 'x') * 64, 'bytes': 1000 + index, 'mode': 420}
        expected = pins[logical]
        tracked = api.RECIPE + '/' + logical
        if logical == api.COMPOSITION_BRIDGE:
            record = {'action': 'new-private-source-header', 'selection': 'source-only-addition',
                'origin': 'reviewed-source-only-composition-undo-private-bridge', 'origin_path': tracked,
                'source': logical, 'preimage_sha256': None, 'sha256': expected['sha256'], 'bytes': expected['bytes'],
                'after_sha256': expected['sha256'], 'after_bytes': expected['bytes'], 'mode': 420}
            origin = {'kind': 'reviewed-source-only-composition-undo-private-bridge', 'record': record}
        else:
            previous = copy.deepcopy(value['inputs'][logical]['origin']['record'])
            if previous.get('successor', {}).get('kind') == 'reviewed-native-composition-cancel-inverse-repair':
                previous = previous['successor']['supersedes']['origin']
            successor = {'kind': 'reviewed-native-composition-cancel-inverse-repair',
                'correction': 'transaction-owned-native-composition-inverse-and-original-selection',
                'sha256': expected['sha256'], 'source_path': tracked, 'source_only': True,
                'supersedes': {'origin': previous, 'sha256': previous['after_sha256'], 'tracked_path': tracked}}
            record = {**previous, 'action': successor['correction'], 'selection': 'reviewed-source-successor',
                'after_sha256': expected['sha256'], 'after_bytes': expected['bytes'], 'successor': successor}
            origin = {'kind': 'mapped-native-actions-runtime', 'record': record}
        value['inputs'][logical] = {**expected, 'tracked_path': tracked, 'role': 'source', 'origin': origin}
    return value, pins


class NativeCompositionSourceCatalogue(unittest.TestCase):
    def setUp(self):
        self.api = load_helper()
        self.value, self.pins = composition_catalogue_fixture(self.api)

    def test_exact_successor_is_data_only_and_unbound_facts_fail_closed(self):
        with mock.patch.object(self.api, 'COMPOSITION_SOURCE_FACTS', None), no_programs():
            with self.assertRaisesRegex(ValueError, 'unbound'):
                self.api.composition_catalogue_counts(self.value)
        with mock.patch.object(self.api, 'COMPOSITION_SOURCE_FACTS', self.pins), no_programs():
            self.assertEqual(self.api.composition_catalogue_counts(self.value),
                {'source_files': 158, 'engine_files': 48, 'direct_translation_units': 32})

    def test_only_one_known_addition_and_exact_native_lineage_are_admitted(self):
        logical = next(iter(self.api.COMPOSITION_PREDECESSORS))
        bridge = self.api.COMPOSITION_BRIDGE
        guard = 'source/foundation/third_party/appended-engine/src/ProviderGuard.cpp'
        edits = (
            lambda v: v.update(kind='foundation-native-engine-actions-source-inputs'),
            lambda v: v['inputs'].update(unknown=v['inputs'].pop(bridge)),
            lambda v: v['inputs'][guard].update(sha256='d' * 64),
            lambda v: v['inputs'][logical].update(sha256='e' * 64),
            lambda v: v['inputs'][logical]['origin']['record'].update(preimage_sha256='d' * 64),
            lambda v: v['inputs'][logical]['origin']['record']['successor']['supersedes']['origin'].update(after_sha256='d' * 64),
            lambda v: v['inputs'][logical]['origin']['record']['successor'].update(source_only=1),
            lambda v: v['inputs'][bridge]['origin']['record'].update(origin='frozen-native-actions-capsule'),
            lambda v: v['inputs'][bridge].update(bytes=True),
        )
        with mock.patch.object(self.api, 'COMPOSITION_SOURCE_FACTS', self.pins), no_programs():
            for index, change in enumerate(edits):
                value = copy.deepcopy(self.value); change(value)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    self.api.composition_catalogue_counts(value)

    def test_passive_inspector_and_capture_use_identical_strict_guard(self):
        paths = (HELPER, ROOT / self.api.RECIPE / 'inspect_sources.py')
        bodies = []
        for path in paths:
            body = next(node for node in ast.parse(path.read_bytes()).body
                if isinstance(node, ast.FunctionDef) and node.name == 'composition_catalogue_counts')
            bodies.append(ast.dump(body, include_attributes=False))
        self.assertEqual(*bodies)


if __name__ == '__main__':
    unittest.main()
