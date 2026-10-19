"""Inert stream/metadata fixtures; no supplier archive, source tree or program runs."""
import copy
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import hashlib
import gzip
import io
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_source_replay as replay
import appended_engine_guard_transition as GUARD_TRANSITION


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def ref(name, raw):
    return {'path': name, 'sha256': digest(raw)}


def binding(name, raw):
    return {**ref(name, raw), 'bytes': len(raw), 'mode': 0o644}


def parents(names):
    return sorted({parent.as_posix() for name in names for parent in PurePosixPath(name).parents
                   if parent.as_posix() != '.'})


def inventory(files):
    directories = parents(files)
    return {'files': {name: digest(raw) for name, raw in files.items()},
            'directories': directories,
            'modes': {**{name: 0o644 for name in files}, **{name: 0o755 for name in directories}}}


@contextmanager
def no_programs():
    with ExitStack() as stack:
        for target in ('subprocess.Popen', 'subprocess.run', 'os.system', 'os.execv', 'os.spawnv'):
            stack.enter_context(mock.patch(target, side_effect=AssertionError('program launch forbidden')))
        for name in ('inspect_selection', 'parse_source_projection', 'validate_source_provenance', 'assemble'):
            stack.enter_context(mock.patch.object(replay.native_inputs, name,
                side_effect=AssertionError('Linux producer cannot admit Windows source')))
        yield


class Fixture:
    def __init__(self, archive_format='tar-gzip'):
        self.format = archive_format
        self.members = {'engine': [], 'wrapper': []}
        self.projection = {'schema_version': 1,
            'kind': 'foundation-native-engine-prototype-sources-v1',
            'suppliers': {key: {'repository': 'https://example.invalid/' + key,
                               'commit': commit, 'archive': key} for key, commit in replay.COMMITS.items()},
            'archives': {}, 'projection': {'files': {}, 'directories': [],
                'exclusions': {'engine': [], 'wrapper': []},
                'normalizations': {'engine': {}, 'wrapper': {}}},
            'patches': [], 'notices': [ref('notices/inert.txt', b'inert source notice\n')],
            'provenance': [{'role': role, **ref('proof/' + role + '.json', b'inert ' + role.encode()),
                            'bytes': len(b'inert ' + role.encode())}
                           for role in sorted(replay.SOURCE_PROVENANCE_ROLES)]}
        self.add('engine', 'CMakeLists.txt', b'# inert root\n')
        self.add('engine', 'Source/cmake/WebKitCommon.cmake', b'# inert source\n')
        self.add('engine', 'Tools/fixture.txt', b'inert generator input\n')
        self.add('engine', 'Source/a.txt', b'before\n')
        self.add('wrapper', 'README.md', b'inert wrapper\n')
        self.add('wrapper', 'src/embedder/main.cpp', b'// inert\n')
        self.limits = {'seconds': 10, 'maximum_archive_bytes': 1024 * 1024,
            'maximum_expanded_bytes': 1024 * 1024, 'maximum_members': 1000,
            'maximum_member_bytes': 128 * 1024, 'maximum_patch_bytes': 128 * 1024}
        self.patches, self.overlays, self.overlay_facts = [], {}, {}

    def add(self, key, name, raw=b'', *, mode=0o644, kind='file', link=None,
            selected=True, expected=None, target_mode=None):
        self.members[key].append({'name': name, 'raw': raw, 'mode': mode, 'kind': kind, 'link': link})
        if selected and kind != 'directory':
            expected = raw if expected is None else expected
            self.projection['projection']['files']['source/' + key + '/' + name] = {
                'archive': key, 'member': name, 'sha256': digest(expected), 'bytes': len(expected),
                'mode': target_mode if target_mode is not None else 0o755 if mode & 0o111 else 0o644}

    def seal(self):
        streams = {}
        for key, members in self.members.items():
            output = io.BytesIO()
            if self.format == 'zip':
                with zipfile.ZipFile(output, 'w') as archive:
                    for item in [{'name': '', 'kind': 'directory', 'mode': 0o755, 'raw': b''}, *members]:
                        name = key + ('/' + item['name'] if item['name'] else '')
                        if item['kind'] == 'directory':
                            name += '/'
                        entry = zipfile.ZipInfo(name)
                        entry.create_system = 3
                        mode = item['mode'] | {'directory': stat.S_IFDIR, 'symlink': stat.S_IFLNK,
                            'file': stat.S_IFREG, 'special': stat.S_IFIFO}.get(item['kind'], stat.S_IFREG)
                        entry.external_attr = mode << 16
                        body = item['link'].encode() if item['kind'] == 'symlink' else item['raw']
                        archive.writestr(entry, body)
            else:
                with tarfile.open(fileobj=output, mode={'tar-gzip': 'w:gz', 'tar-xz': 'w:xz'}[self.format]) as archive:
                    for item in [{'name': '', 'kind': 'directory', 'mode': 0o755, 'raw': b''}, *members]:
                        entry = tarfile.TarInfo(key + ('/' + item['name'] if item['name'] else ''))
                        entry.mode = item['mode']
                        entry.type = {'directory': tarfile.DIRTYPE, 'symlink': tarfile.SYMTYPE,
                            'hardlink': tarfile.LNKTYPE, 'file': tarfile.REGTYPE,
                            'special': tarfile.FIFOTYPE}[item['kind']]
                        entry.size = len(item['raw']) if item['kind'] == 'file' else 0
                        entry.linkname = item.get('link') or ''
                        archive.addfile(entry, io.BytesIO(item['raw']) if item['kind'] == 'file' else None)
            raw = output.getvalue()
            streams[key] = io.BytesIO(raw)
            self.projection['archives'][key] = {**binding('archives/' + key + '.bin', raw),
                'format': self.format, 'strip_prefix': key}
            self.projection['archives'][key].pop('mode')
        self.projection['projection']['directories'] = parents(self.projection['projection']['files'])
        self.streams = streams
        return self

    def patch(self, before=b'before\n', after=b'after\n'):
        raw = b'--- a/Source/a.txt\n+++ b/Source/a.txt\n@@ -1 +1 @@\n-' + before + b'+' + after
        self.patches.append(raw)
        self.projection['patches'].append({**ref('patches/one.patch', raw), 'tree': 'engine',
            'preimages': {'Source/a.txt': digest(before)}, 'postimages': {'Source/a.txt': digest(after)}})
        return raw

    def overlay(self, name='source/engine/Source/a.txt', body=b'final overlay\n', mode=0o644):
        self.overlays[name] = body
        self.overlay_facts[name] = {'sha256': digest(body), 'bytes': len(body), 'mode': mode}

    def run(self):
        return replay.replay_projection(self.projection, self.streams, self.patches,
                                        self.overlays, self.overlay_facts, self.limits)

    def bindings(self):
        return {'archives': {key: {field: item[field] for field in ('path', 'sha256', 'bytes')}
                                     | {'mode': 0o644} for key, item in self.projection['archives'].items()},
            'provenance': {item['role']: {field: item[field] for field in ('path', 'sha256', 'bytes')}
                          | {'mode': 0o644} for item in self.projection['provenance']},
            'original_proof': {role: binding('original/' + role + '.bin', b'inert original ' + role.encode())
                               for role in replay.ORIGINAL_PROOF_ROLES},
            'patches': [binding(item['path'], raw) for item, raw in zip(self.projection['patches'], self.patches)],
            'notices': [binding('notices/inert.txt', b'inert source notice\n')]}


def _wiring_only_record_tables(fixture):
    """Tiny record-shaped bytes for mocked seam wiring, never source authority."""
    def record(path, raw):
        return {**binding(path, raw), 'raw': raw}

    original = {role: record('original/' + role + '.bin',
        b'# inert generator source\n' if role == 'generator' else replay.encoded({'inert_role': role}))
        for role in replay.ORIGINAL_PROOF_ROLES}
    provenance = {}
    for item in fixture.projection['provenance']:
        role = item['role']
        raw = (replay.encoded({'kind': 'foundation-native-engine-retained-body-evidence-v1',
            'original_proof': {name: {key: value[key] for key in ('path', 'sha256', 'bytes')}
                               for name, value in original.items()}})
            if role == 'engine-body-verification' else replay.encoded({'inert_role': role}))
        captured = record(item['path'], raw)
        item.update({key: captured[key] for key in ('sha256', 'bytes')})
        provenance[role] = captured
    records = {'archives': {key: {field: item[field] for field in ('path', 'sha256', 'bytes')}
                                  | {'mode': 0o644} for key, item in fixture.projection['archives'].items()},
        'provenance': provenance,
        'patches': [record(item['path'], raw) for item, raw in zip(fixture.projection['patches'], fixture.patches)],
        'notices': [record(item['path'], b'inert source notice\n') for item in fixture.projection['notices']]}
    return records, original


def _wiring_only_capture_fixture(root, *, absolute=False):
    """Write owned synthetic inputs; their source-proof semantics stay mocked."""
    fixture = Fixture().seal()
    records, original = _wiring_only_record_tables(fixture)
    bindings = {}
    for table, items in {**records, 'original_proof': original}.items():
        bound = {} if isinstance(items, dict) else []
        entries = items.items() if isinstance(items, dict) else enumerate(items)
        for key, item in entries:
            relative = 'relocated/' + item['path']
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = fixture.streams[key].getvalue() if table == 'archives' else item['raw']
            path.write_bytes(raw)
            path.chmod(0o644)
            value = {field: item[field] for field in ('path', 'sha256', 'bytes', 'mode')}
            value['path'] = str(path) if absolute else relative
            if isinstance(bound, dict):
                bound[key] = value
            else:
                bound.append(value)
        bindings[table] = bound
    return fixture, records, original, bindings


class ProjectionReplay(unittest.TestCase):
    def test_three_archive_formats_derive_complete_unchecked_inventory(self):
        for archive_format in ('tar-gzip', 'tar-xz', 'zip'):
            with self.subTest(archive_format=archive_format), no_programs():
                fixture = Fixture(archive_format).seal()
                result = fixture.run()
                self.assertEqual(result['files'], {name: item['sha256'] for name, item in
                    fixture.projection['projection']['files'].items()})
                self.assertEqual(result['directories'], fixture.projection['projection']['directories'])
                self.assertIs(result['original_proof_admitted'], False)
                self.assertIs(result['raw_member_manifest_admitted'], False)
                self.assertTrue(all(result[key] is False for key in replay.handoff.FALSE_FACTS))
                self.assertFalse(hasattr(replay, 'SourceReplayInspection'))

    def test_resealed_modified_nonoverlay_member_rejects(self):
        fixture = Fixture()
        fixture.members['wrapper'][0]['raw'] = b'modified archive member\n'
        fixture.seal()
        with no_programs(), self.assertRaisesRegex(ValueError, 'hash/bytes/mode'):
            fixture.run()

    def test_extra_and_missing_nonoverlay_members_reject(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                fixture = Fixture()
                if missing:
                    fixture.members['wrapper'].pop(0)
                else:
                    fixture.add('wrapper', 'extra.txt', b'extra\n', selected=False)
                fixture.seal()
                with self.assertRaises(ValueError):
                    fixture.run()

    def test_exact_archive_stream_pin_is_checked(self):
        fixture = Fixture().seal()
        raw = fixture.streams['engine'].getvalue()
        fixture.streams['engine'] = io.BytesIO(raw[:-1] + bytes((raw[-1] ^ 1,)))
        with self.assertRaisesRegex(ValueError, 'independent pin/bytes'):
            fixture.run()

    def test_mutation_after_initial_archive_hash_rejects(self):
        fixture = Fixture().seal()
        class Mutating(io.BytesIO):
            rewinds = 0
            def seek(self, offset, whence=0):
                if offset == 0 and whence == 0:
                    self.rewinds += 1
                    if self.rewinds == 2:
                        body = self.getvalue()
                        self.seek(0, 2)
                        self.write(b'x')
                        super().seek(0)
                return super().seek(offset, whence)
        fixture.streams['engine'] = Mutating(fixture.streams['engine'].getvalue())
        with self.assertRaisesRegex(ValueError, 'declared byte bound'):
            fixture.run()

    def test_case_alias_and_file_directory_conflict_reject(self):
        for name in ('Source/A.txt', 'Source/a.txt/child'):
            fixture = Fixture()
            fixture.add('engine', name, b'collision\n', selected=False)
            fixture.seal()
            with self.subTest(name=name), self.assertRaises(ValueError):
                fixture.run()

    def test_privileged_and_special_archive_members_reject(self):
        for kind, mode in (('file', 0o4644), ('special', 0o644)):
            fixture = Fixture()
            fixture.add('wrapper', 'unsafe', b'', selected=False, kind=kind, mode=mode)
            fixture.seal()
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Privileged or special'):
                fixture.run()

    def test_safe_mode_normalization_and_mode_mismatch(self):
        fixture = Fixture()
        fixture.members['wrapper'][0]['mode'] = 0o600
        with no_programs():
            self.assertEqual(fixture.seal().run()['modes']['source/wrapper/README.md'], 0o644)
        fixture = Fixture()
        fixture.members['wrapper'][0]['mode'] = 0o755
        with self.assertRaisesRegex(ValueError, 'hash/bytes/mode'):
            fixture.seal().run()

    def test_direct_symlink_and_hardlink_materialize_target_mode(self):
        for kind, archive_format, literal in (('symlink', 'tar-gzip', 'a.txt'),
                ('hardlink', 'tar-xz', 'engine/Source/a.txt'), ('symlink', 'zip', 'a.txt')):
            with self.subTest(kind=kind, format=archive_format):
                fixture = Fixture(archive_format)
                fixture.add('engine', 'Source/alias.txt', kind=kind, link=literal,
                            expected=b'before\n', mode=0o755, target_mode=0o644)
                fixture.projection['projection']['normalizations']['engine']['Source/alias.txt'] = 'Source/a.txt'
                result = fixture.seal().run()
                self.assertEqual(result['files']['source/engine/Source/alias.txt'], digest(b'before\n'))
                self.assertEqual(result['modes']['source/engine/Source/alias.txt'], 0o644)

    def test_link_chain_or_escape_or_changed_literal_reject(self):
        for literal, target in (('../../outside', 'outside'), ('missing', 'Source/a.txt'), ('alias2', 'Source/alias2')):
            fixture = Fixture()
            fixture.add('engine', 'Source/alias', kind='symlink', link=literal, expected=b'before\n')
            fixture.projection['projection']['normalizations']['engine']['Source/alias'] = target
            if literal == 'alias2':
                fixture.add('engine', 'Source/alias2', kind='symlink', link='a.txt', expected=b'before\n')
                fixture.projection['projection']['normalizations']['engine']['Source/alias2'] = 'Source/a.txt'
            with self.subTest(literal=literal), self.assertRaises(ValueError):
                fixture.seal().run()

    def test_complete_exclusion_and_unused_exclusion(self):
        fixture = Fixture()
        fixture.add('wrapper', 'packaging/unselected.txt', b'excluded\n', selected=False)
        fixture.projection['projection']['exclusions']['wrapper'] = ['packaging']
        self.assertNotIn('source/wrapper/packaging/unselected.txt', fixture.seal().run()['files'])
        fixture.projection['projection']['exclusions']['wrapper'].append('unused')
        with self.assertRaisesRegex(ValueError, 'Unused or missing'):
            fixture.run()

    def test_engine_source_and_tools_cannot_be_excluded(self):
        for name in ('Source/a.txt', 'Tools', 'CMakeLists.txt'):
            fixture = Fixture().seal()
            fixture.projection['projection']['exclusions']['engine'] = [name]
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'cannot be excluded'):
                fixture.run()

    def test_supplier_patch_precedes_final_overlay_and_preserves_existing_mode(self):
        fixture = Fixture()
        fixture.members['engine'][-1]['mode'] = 0o755
        fixture.projection['projection']['files']['source/engine/Source/a.txt']['mode'] = 0o755
        fixture.patch()
        fixture.overlay(mode=0o644)
        result = fixture.seal().run()
        self.assertEqual(result['files']['source/engine/Source/a.txt'], digest(b'final overlay\n'))
        self.assertEqual(result['modes']['source/engine/Source/a.txt'], 0o644)
        fixture.overlays, fixture.overlay_facts = {}, {}
        self.assertEqual(fixture.run()['modes']['source/engine/Source/a.txt'], 0o755)

    def test_later_overlay_cannot_hide_bad_intermediate_patch_context(self):
        fixture = Fixture()
        raw = fixture.patch()
        fixture.patches[0] = raw.replace(b'-before', b'-wrong!')
        fixture.projection['patches'][0]['sha256'] = digest(fixture.patches[0])
        fixture.overlay()
        with self.assertRaisesRegex(ValueError, 'context differs'):
            fixture.seal().run()

    def test_patch_add_delete_and_empty_directory_preservation(self):
        fixture = Fixture()
        raw = (b'--- a/Tools/fixture.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-inert generator input\n'
               b'--- /dev/null\n+++ b/new/added.txt\n@@ -0,0 +1 @@\n+added\n')
        fixture.patches = [raw]
        fixture.projection['patches'] = [{**ref('patches/add-delete.patch', raw), 'tree': 'engine',
            'preimages': {'Tools/fixture.txt': digest(b'inert generator input\n'), 'new/added.txt': None},
            'postimages': {'Tools/fixture.txt': None, 'new/added.txt': digest(b'added\n')}}]
        result = fixture.seal().run()
        self.assertNotIn('source/engine/Tools/fixture.txt', result['files'])
        self.assertIn('source/engine/Tools', result['directories'])
        self.assertEqual(result['modes']['source/engine/new/added.txt'], 0o644)

    def test_preapplied_patch_baseline_and_duplicate_patch_reject(self):
        fixture = Fixture()
        fixture.members['engine'][-1]['raw'] = b'after\n'
        fixture.projection['projection']['files']['source/engine/Source/a.txt']['sha256'] = digest(b'after\n')
        fixture.projection['projection']['files']['source/engine/Source/a.txt']['bytes'] = len(b'after\n')
        fixture.patch()
        with self.assertRaisesRegex(ValueError, 'clean original preimage'):
            fixture.seal().run()
        fixture = Fixture()
        fixture.patch()
        fixture.projection['patches'].append(copy.deepcopy(fixture.projection['patches'][0]))
        fixture.patches *= 2
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            fixture.seal().run()

    def test_each_explicit_finite_budget_has_a_discriminator(self):
        for key, value in (('maximum_archive_bytes', 1), ('maximum_expanded_bytes', 1),
                ('maximum_members', 1), ('maximum_member_bytes', 1), ('maximum_patch_bytes', 1)):
            fixture = Fixture()
            fixture.patch()
            fixture.seal()
            fixture.limits[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                fixture.run()
        fixture = Fixture().seal()
        with mock.patch.object(replay.time, 'monotonic', side_effect=[0, 11]), self.assertRaisesRegex(ValueError, 'wall budget'):
            fixture.run()

    def test_invalid_finite_limits_and_scalar_types_reject(self):
        for key, value in (('seconds', float('inf')), ('seconds', float('nan')), ('seconds', True),
                ('maximum_members', True), ('maximum_member_bytes', replay.MAX_MEMBER + 1),
                ('maximum_archive_bytes', 0)):
            fixture = Fixture().seal()
            fixture.limits[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                fixture.run()

    def test_overlay_missing_extra_pin_mode_and_case_reject(self):
        for mutation in ('missing', 'extra', 'pin', 'mode', 'case'):
            fixture = Fixture().seal()
            fixture.overlay()
            if mutation == 'missing': fixture.overlays.clear()
            if mutation == 'extra': fixture.overlays['source/extra'] = b'extra'
            if mutation == 'pin': fixture.overlay_facts['source/engine/Source/a.txt']['sha256'] = '1' * 64
            if mutation == 'mode': fixture.overlay_facts['source/engine/Source/a.txt']['mode'] = True
            if mutation == 'case': fixture.overlay('source/engine/source/A.txt')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                fixture.run()

    def test_projection_closed_fields_missing_roots_and_unsafe_paths_reject(self):
        for mutate in (lambda d: d.update(extra=True),
                lambda d: d['suppliers']['engine'].update(commit='1' * 40),
                lambda d: d['projection']['files'].pop('source/engine/CMakeLists.txt'),
                lambda d: d['archives']['engine'].update(bytes=True),
                lambda d: d['archives']['engine'].update(path='../outside'),
                lambda d: d['projection']['files']['source/wrapper/README.md'].update(mode=True),
                lambda d: d['provenance'].reverse()):
            fixture = Fixture().seal()
            mutate(fixture.projection)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                fixture.run()

    def test_bindings_exact_roles_modes_pins_and_relative_or_posix_paths(self):
        fixture = Fixture().seal()
        value = fixture.bindings()
        checked = replay.validate_bindings(value)
        checked['original_proof']['generator']['mode'] = 0o755
        self.assertEqual(value['original_proof']['generator']['mode'], 0o644)
        for mutate in (lambda d: d['original_proof'].pop('generator'),
                lambda d: d['original_proof']['generator'].update(extra=True),
                lambda d: d['original_proof']['generator'].update(mode=0o755),
                lambda d: d['original_proof']['recipe'].update(sha256='0' * 64),
                lambda d: d['archives']['engine'].update(path='C:/archive'),
                lambda d: d['notices'][0].update(bytes=True)):
            changed = copy.deepcopy(value)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                replay.validate_bindings(changed)
        absolute = copy.deepcopy(value)
        for table in ('archives', 'provenance', 'original_proof'):
            for item in absolute[table].values(): item['path'] = '/inert/' + item['path']
        for table in ('patches', 'notices'):
            for item in absolute[table]: item['path'] = '/inert/' + item['path']
        self.assertEqual(replay.validate_bindings(absolute, relative=False), absolute)


class MetadataFixture:
    """Entirely generated metadata, including fake catalogue pins for parser tests."""
    def __init__(self):
        inputs = {}
        for index in range(157):
            name = ('source/engine/unit' if index < 48 else 'source/document-provider/unit') + str(index) + '.txt'
            inputs[name] = self.entry(name, b'inert overlay ' + str(index).encode(), 'source')
        self.mapping, self.interfaces = {}, {}
        names = list(inputs)
        for index in range(16):
            alias = 'interfaces/inert' + str(index) + '.json'
            source = names[index + 48]
            self.mapping[alias] = {'role': 'interface', 'sha256': inputs[source]['sha256'], 'tracked_source': source}
            self.interfaces['pin' + str(index)] = {'retained_logical_path': alias, **self.mapping[alias]}
        aliases = {replay.handoff.GENERATOR: 'helper', replay.handoff.TEMPLATE: 'config', replay.handoff.CONFIG: 'config'}
        aliases.update({'tools/helper' + str(index) + '.py': 'helper' for index in range(6)})
        for alias, role in aliases.items():
            source = 'metadata/' + alias.replace('/', '_')
            inputs[source] = self.entry(source, b'inert metadata ' + alias.encode(), role)
            self.mapping[alias] = {'role': role, 'sha256': inputs[source]['sha256'], 'tracked_source': source}
        while len(inputs) < 197:
            name = 'metadata/filler' + str(len(inputs)) + '.json'
            inputs[name] = self.entry(name, b'inert filler\n', 'data')
        self.source_map = {'inputs': inputs}
        self.provenance = {'source_graph': {'source_files': 157, 'engine_files': 48, 'direct_translation_units': 32},
                           'retained_input_mapping': self.mapping, 'interface_pins': self.interfaces}
        self.graph = b'set(_sources\n' + b'\n'.join(('"inert' + str(i) + '.cpp"').encode() for i in range(32)) + b'\n)\n# document_forms\n'
        self.seal()

    @staticmethod
    def entry(name, body, role):
        return {'sha256': digest(body), 'mode': 0o644, 'role': role, 'bytes': len(body),
                'tracked_path': 'inert/' + name, 'origin': {'kind': 'inert-metadata-fixture'}}

    def seal(self):
        self.raw = {'source_map': replay.encoded(self.source_map),
                    'provenance': replay.encoded(self.provenance), 'graph': self.graph}
        self.catalogue = {role: {'path': replay.contract.CATALOGUE[role]['path'], 'sha256': digest(body)}
                          for role, body in self.raw.items()}
        return self

    def check(self):
        with mock.patch.object(replay.contract, 'CATALOGUE', self.catalogue):
            return replay.catalogue_metadata(*(self.raw[key] for key in ('source_map', 'provenance', 'graph')))


def catalogue_bodies(kind):
    """Read current metadata once and reconstruct exact retained catalogue versions."""
    root = ROOT / replay.native_inputs.RECIPE
    value = replay.handoff._document((root / 'source-imports.json').read_bytes())
    provenance = replay.handoff._document((root / 'provenance.json').read_bytes())
    api = replay.native_inputs
    while value.get('kind') != kind:
        current = value.get('kind')
        if current == api.NATIVE_FORM_PREFLIGHT_SOURCE_KIND:
            provenance = GUARD_TRANSITION.provenance_predecessor(provenance)
            value = api.native_form_preflight_catalogue_predecessor(value)
        elif current == api.NATIVE_INPUT_METHOD_SOURCE_KIND:
            provenance.pop('native_input_method_lifecycle_successor')
            value = api.native_input_method_catalogue_predecessor(value)
        elif current == api.NATIVE_SELECT_EVENTS_SOURCE_KIND:
            value = api.native_select_events_catalogue_predecessor(value)
            logical = 'source/engine/Source/WebCore/html/HTMLSelectElement.cpp'
            matches = [index for index, row in enumerate(provenance['native_engine_files']) if row['tracked_source'] == logical]
            if len(matches) != 1:
                raise AssertionError('Exact one historical native engine row required')
            provenance['native_engine_files'][matches[0]] = value['inputs'][logical]['origin']['record']
        else:
            raise AssertionError('Unsupported older fixture catalogue transition')
    raw = {'source_map': replay.contract.encoded(value), 'provenance': replay.contract.encoded(provenance),
           'graph': (root / 'cmake/native-provider.cmake').read_bytes()}
    catalogue = replay.contract.catalogue_for_map_digest(digest(raw['source_map']))
    for role, body in raw.items():
        if digest(body) != catalogue[role]['sha256']:
            raise AssertionError('Exact historical catalogue body differs: ' + role)
    return raw


def before_showpicker(raw):
    value = replay.handoff._document(raw)
    if value.get('kind') == replay.native_inputs.NATIVE_SHOWPICKER_SOURCE_KIND:
        return replay.encoded(replay.native_inputs.native_showpicker_catalogue_predecessor(value))
    return raw


class NewSourceCatalogueVersionTests(unittest.TestCase):
    def test_form_input_method_and_select_events_use_exact_real_data_guards(self):
        versions = (
            (replay.native_inputs.NATIVE_FORM_PREFLIGHT_SOURCE_KIND, 'NATIVE_FORM_PREFLIGHT_CATALOGUE', 'native_form_preflight_catalogue_counts'),
            (replay.native_inputs.NATIVE_INPUT_METHOD_SOURCE_KIND, 'NATIVE_INPUT_METHOD_CATALOGUE', 'native_input_method_catalogue_counts'),
            (replay.native_inputs.NATIVE_SELECT_EVENTS_SOURCE_KIND, 'NATIVE_SELECT_EVENTS_CATALOGUE', 'native_select_events_catalogue_counts'),
        )
        for kind, catalogue_name, gate_name in versions:
            with self.subTest(kind=kind), no_programs():
                raw = catalogue_bodies(kind)
                checked = replay.catalogue_metadata(*(raw[key] for key in ('source_map', 'provenance', 'graph')))
                self.assertEqual(checked['counts'], {'source_files': 158, 'engine_files': 48, 'direct_translation_units': 32})
                self.assertEqual(len(checked['source_map']['inputs']), 198)
                fixture = MetadataFixture()
                fixture.source_map['kind'] = kind
                fixture.seal()
                with mock.patch.object(replay.contract, catalogue_name, fixture.catalogue), mock.patch.object(
                        replay.native_inputs, gate_name, side_effect=ValueError('EXACT-SOURCE-GATE')) as gate:
                    with self.assertRaisesRegex(ValueError, 'EXACT-SOURCE-GATE'):
                        replay.catalogue_metadata(*(fixture.raw[key] for key in ('source_map', 'provenance', 'graph')))
                gate.assert_called_once_with(fixture.source_map)


class NativeShowpickerCatalogueVersionTests(unittest.TestCase):
    def test_current_showpicker_catalogue_uses_its_exact_source_guard(self):
        catalogue = replay.contract.NATIVE_SHOWPICKER_CATALOGUE
        raw = catalogue_bodies(replay.native_inputs.NATIVE_SHOWPICKER_SOURCE_KIND)
        checked = replay.catalogue_metadata(*(raw[key] for key in ('source_map', 'provenance', 'graph')))
        self.assertEqual(len(checked['overlays']), 158)
        self.assertEqual(digest(before_showpicker(raw['source_map'])),
                         replay.contract.NATIVE_CONTROL_INCLUDES_CATALOGUE['source_map']['sha256'])
        fixture = MetadataFixture()
        fixture.source_map['kind'] = replay.native_inputs.NATIVE_SHOWPICKER_SOURCE_KIND
        fixture.seal()
        with mock.patch.object(replay.contract, 'NATIVE_SHOWPICKER_CATALOGUE', fixture.catalogue), mock.patch.object(
                replay.native_inputs, 'native_showpicker_catalogue_counts', side_effect=ValueError('SHOWPICKER-EXACT-SOURCE-GATE')) as gate:
            with self.assertRaisesRegex(ValueError, 'SHOWPICKER-EXACT-SOURCE-GATE'):
                replay.catalogue_metadata(*(fixture.raw[key] for key in ('source_map', 'provenance', 'graph')))
        gate.assert_called_once_with(fixture.source_map)


class NativeControlIncludesCatalogueVersionTests(unittest.TestCase):
    def test_current_include_catalogue_and_exact_guard_are_selected(self):
        catalogue = replay.contract.NATIVE_CONTROL_INCLUDES_CATALOGUE
        raw = catalogue_bodies(replay.native_inputs.NATIVE_SHOWPICKER_SOURCE_KIND)
        raw['source_map'] = before_showpicker(raw['source_map'])
        checked = replay.catalogue_metadata(*(raw[key] for key in ('source_map', 'provenance', 'graph')))
        self.assertEqual(len(checked['overlays']), 158)
        self.assertNotEqual(catalogue, replay.contract.NATIVE_CONTROL_KEYPRESS_CATALOGUE)
        self.assertEqual(catalogue['provenance'], replay.contract.NATIVE_CONTROL_KEYPRESS_CATALOGUE['provenance'])
        fixture = MetadataFixture()
        fixture.source_map['kind'] = replay.native_inputs.NATIVE_CONTROL_INCLUDES_SOURCE_KIND
        fixture.seal()
        with mock.patch.object(replay.contract, 'NATIVE_CONTROL_INCLUDES_CATALOGUE', fixture.catalogue), mock.patch.object(
                replay.native_inputs, 'native_control_includes_catalogue_counts', side_effect=ValueError('INCLUDES-EXACT-SOURCE-GATE')) as gate:
            with self.assertRaisesRegex(ValueError, 'INCLUDES-EXACT-SOURCE-GATE'):
                replay.catalogue_metadata(*(fixture.raw[key] for key in ('source_map', 'provenance', 'graph')))
        gate.assert_called_once()


class NativeControlKeypressCatalogueVersionTests(unittest.TestCase):
    def test_current_catalogue_has_exact_keypress_guard_and_joins(self):
        catalogue = replay.contract.NATIVE_CONTROL_KEYPRESS_CATALOGUE
        raw = catalogue_bodies(replay.native_inputs.NATIVE_SHOWPICKER_SOURCE_KIND)
        raw['source_map'] = replay.encoded(replay.native_inputs.native_control_includes_catalogue_predecessor(replay.handoff._document(before_showpicker(raw['source_map']))))
        self.assertEqual(digest(raw['source_map']), catalogue['source_map']['sha256'])
        checked = replay.catalogue_metadata(*(raw[key] for key in ('source_map', 'provenance', 'graph')))
        self.assertEqual(len(checked['overlays']), 158)
        self.assertNotEqual(catalogue, replay.contract.NATIVE_POPUP_CATALOGUE)
        self.assertEqual(catalogue['provenance'], replay.contract.NATIVE_POPUP_CATALOGUE['provenance'])
        fixture = MetadataFixture()
        fixture.source_map['kind'] = replay.native_inputs.NATIVE_CONTROL_KEYPRESS_SOURCE_KIND
        fixture.seal()
        with mock.patch.object(replay.contract, 'NATIVE_CONTROL_KEYPRESS_CATALOGUE', fixture.catalogue), mock.patch.object(
                replay.native_inputs, 'native_control_keypress_catalogue_counts', side_effect=ValueError('KEYPRESS-EXACT-SOURCE-GATE')) as gate:
            with self.assertRaisesRegex(ValueError, 'KEYPRESS-EXACT-SOURCE-GATE'):
                replay.catalogue_metadata(*(fixture.raw[key] for key in ('source_map', 'provenance', 'graph')))
        gate.assert_called_once()


class NativePopupCatalogueVersionTests(unittest.TestCase):
    def test_current_native_source_catalogue_uses_exact_new_reader_lane(self):
        catalogue=replay.contract.NATIVE_POPUP_CATALOGUE
        raw=catalogue_bodies(replay.native_inputs.NATIVE_SHOWPICKER_SOURCE_KIND)
        current=replay.handoff._document(before_showpicker(raw['source_map']))
        current=replay.native_inputs.native_control_includes_catalogue_predecessor(current)
        previous=replay.native_inputs.native_control_keypress_catalogue_predecessor(current)
        raw['source_map']=replay.contract.encoded(previous)
        self.assertEqual(digest(raw['source_map']),catalogue['source_map']['sha256'])
        checked=replay.catalogue_metadata(*(raw[key] for key in ('source_map','provenance','graph')))
        self.assertEqual(len(checked['overlays']),158)
        self.assertNotEqual(catalogue,replay.contract.COMPOSITION_CATALOGUE)
        self.assertEqual(catalogue['provenance'],replay.contract.COMPOSITION_CATALOGUE['provenance'])

    def test_native_kind_cannot_bypass_its_exact_source_guard(self):
        fixture=MetadataFixture();fixture.source_map['kind']=replay.native_inputs.NATIVE_POPUP_SOURCE_KIND;fixture.seal()
        with mock.patch.object(replay.contract,'NATIVE_POPUP_CATALOGUE',fixture.catalogue),mock.patch.object(
                replay.native_inputs,'native_popup_catalogue_counts',side_effect=ValueError('NATIVE-EXACT-SOURCE-GATE')) as gate:
            with self.assertRaisesRegex(ValueError,'NATIVE-EXACT-SOURCE-GATE'):
                replay.catalogue_metadata(*(fixture.raw[key] for key in ('source_map','provenance','graph')))
            gate.assert_called_once_with(fixture.source_map)


class CompositionCatalogueVersionTests(unittest.TestCase):
    def test_successor_tag_cannot_use_legacy_count_or_unbound_body_pins(self):
        fixture = MetadataFixture()
        fixture.source_map['kind'] = replay.native_inputs.COMPOSITION_SOURCE_KIND
        fixture.seal()
        with mock.patch.object(replay.contract, 'COMPOSITION_CATALOGUE', fixture.catalogue), \
                mock.patch.object(replay.native_inputs, 'COMPOSITION_SOURCE_FACTS', None):
            with self.assertRaisesRegex(ValueError, 'unbound'):
                replay.catalogue_metadata(*(fixture.raw[key] for key in ('source_map', 'provenance', 'graph')))
        fixture.source_map.pop('kind')
        fixture.seal()
        with mock.patch.object(replay.contract, 'COMPOSITION_CATALOGUE', None):
            checked = fixture.check()
        self.assertEqual(len(checked['overlays']), 157)

    def test_capture_reads_and_reports_the_same_selected_catalogue(self):
        legacy = copy.deepcopy(replay.contract.CATALOGUE)
        successor = {role: {**item, 'sha256': str(index + 1) * 64}
                     for index, (role, item) in enumerate(legacy.items())}
        entries, bodies = {}, {}
        for version, catalogue in (('old', legacy), ('new', successor)):
            for role, item in catalogue.items():
                name = version + '/' + role + '.json'
                entries[name] = {'sha256': item['sha256'], 'mode': 420}
                bodies[name] = (version + ':' + role).encode()
        reads = []
        retained = SimpleNamespace(expectations={})
        retained.read = lambda name, expected: (reads.append(name), bodies[name])[1]
        retained.capture_tree = mock.Mock()
        assembled = SimpleNamespace(expectations={}, capture_tree=mock.Mock())
        owner = SimpleNamespace(limits={'maximum_member_bytes': 1024},
            source_limits=lambda: {}, work_deadline=123, check=mock.Mock())
        inventory = {'files': {}, 'directories': [], 'modes': {}}
        selection = {'source_catalogue': successor, 'bindings': {},
            'retained': {'recipe_sha256': 'a' * 64, 'sources_sha256': 'b' * 64}}
        with mock.patch.object(replay.contract, 'COMPOSITION_CATALOGUE', successor), \
                mock.patch.object(replay, '_capture_source_records', return_value=({'patches': []}, {}, {})), \
                mock.patch.object(replay, 'catalogue_metadata', return_value={'overlays': {}}) as catalogue_check, \
                mock.patch.object(replay, '_replay_checked_records', return_value=(object(), inventory)), \
                mock.patch.object(replay.handoff, '_retained_inventory', return_value=inventory):
            result = replay._run_selection_capture(selection, owner, retained, assembled,
                {'inputs': entries}, {}, {}, inventory)
        self.assertEqual(reads, ['new/source_map.json', 'new/provenance.json', 'new/graph.json'])
        catalogue_check.assert_called_once_with(b'new:source_map', b'new:provenance', b'new:graph')
        self.assertEqual(result['source_catalogue'], successor)
        owner.check.assert_called_once_with()
        retained.capture_tree.assert_called_once_with({}, [])
        assembled.capture_tree.assert_called_once_with({}, [])


class CatalogueTests(unittest.TestCase):
    @staticmethod
    def current_candidate():
        fixture, catalogue = Fixture(), MetadataFixture()
        sections, before, after = [], {}, {}
        for index in range(45):
            name = 'Source/original' + str(index) + '.txt'
            old, new = ('before' + str(index) + '\n').encode(), ('after' + str(index) + '\n').encode()
            fixture.add('engine', name, old)
            before[name], after[name] = digest(old), digest(new)
            sections.append(b'--- a/' + name.encode() + b'\n+++ b/' + name.encode() + b'\n@@ -1 +1 @@\n-' + old + b'+' + new)
        for index in range(23):
            name = 'Source/added' + str(index) + '.txt'
            new = ('added' + str(index) + '\n').encode()
            before[name], after[name] = None, digest(new)
            sections.append(b'--- /dev/null\n+++ b/' + name.encode() + b'\n@@ -0,0 +1 @@\n+' + new)
        raw = b''.join(sections)
        fixture.patches = [raw]
        fixture.projection['patches'] = [{**ref('patches/original45-added23.patch', raw), 'tree': 'engine',
                                          'preimages': before, 'postimages': after}]
        fixture.seal()
        mapped = [item for name, item in catalogue.source_map['inputs'].items() if name.startswith('metadata/filler')]
        for index, item in enumerate(mapped[:5]):
            item.update(role='patch', sha256=digest(raw) if index == 0 else digest(b'inert patch ' + str(index).encode()))
        catalogue.seal()
        documents = {'source_projection': fixture.projection, 'limits': fixture.limits,
                     'bindings': fixture.bindings(), **catalogue.raw}
        overlays = {('source/engine/unit' if index < 48 else 'source/document-provider/unit') + str(index) + '.txt':
                    b'inert overlay ' + str(index).encode() for index in range(157)}
        return fixture, catalogue, documents, overlays

    def test_inert_current_count_alias_interface_joins(self):
        fixture = MetadataFixture()
        with no_programs():
            result = fixture.check()
        self.assertEqual(result['counts'], {'source_files': 157, 'engine_files': 48, 'direct_translation_units': 32})
        self.assertEqual(len(result['overlays']), 157)
        self.assertNotIn('original_proof_admitted', result)

    def test_catalogue_pin_and_stale157_48_32_counts_reject(self):
        fixture = MetadataFixture()
        fixture.raw['graph'] += b'# changed metadata\n'
        with self.assertRaisesRegex(ValueError, 'catalogue pin'):
            fixture.check()
        for key in ('source_files', 'engine_files', 'direct_translation_units'):
            fixture = MetadataFixture()
            fixture.provenance['source_graph'][key] -= 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, '157/engine48/32TU'):
                fixture.seal().check()

    def test25alias_and16interface_closure_rejects_resealed_metadata(self):
        for table in ('retained_input_mapping', 'interface_pins'):
            fixture = MetadataFixture()
            fixture.provenance[table].pop(next(iter(fixture.provenance[table])))
            with self.subTest(table=table), self.assertRaises(ValueError):
                fixture.seal().check()
        fixture = MetadataFixture()
        fixture.interfaces['pin0']['sha256'] = '1' * 64
        with self.assertRaisesRegex(ValueError, 'interface alias'):
            fixture.seal().check()

    def test_forward_policy_rejects_tiny_projection_as_full_admission(self):
        fixture, catalogue = Fixture().seal(), MetadataFixture()
        documents = {'source_projection': fixture.projection, 'limits': fixture.limits,
                     'bindings': fixture.bindings(), **catalogue.raw}
        with mock.patch.object(replay.contract, 'CATALOGUE', catalogue.catalogue), no_programs(), self.assertRaisesRegex(ValueError, 'exactly one engine supplier patch'):
            replay.derive_inventory(documents, fixture.streams, [], {})

    def test_current45_modified23_added_then157_overlay_candidate(self):
        fixture, catalogue, documents, overlays = self.current_candidate()
        with mock.patch.object(replay.contract, 'CATALOGUE', catalogue.catalogue), \
                mock.patch.object(replay.native_inputs, 'SUPPLIER_PATCH', digest(fixture.patches[0])), no_programs():
            result = replay.derive_inventory(documents, fixture.streams, fixture.patches, overlays)
        self.assertEqual(len(result['files']), 231)
        self.assertEqual(result['files']['source/engine/Source/original44.txt'], digest(b'after44\n'))
        self.assertEqual(result['files']['source/engine/Source/added22.txt'], digest(b'added22\n'))
        self.assertEqual(result['overlays'], 157)
        self.assertIs(result['original_proof_admitted'], False)

    def test_full_records_stops_at_missing_original_data_seam_without_stream_access(self):
        fixture, catalogue, documents, overlays = self.current_candidate()
        with mock.patch.object(replay.contract, 'CATALOGUE', catalogue.catalogue), \
                mock.patch.object(replay, 'SOURCE_SEAM_SHA256', None), \
                mock.patch.object(replay.native_inputs, 'SUPPLIER_PATCH', digest(fixture.patches[0])), no_programs(), \
                mock.patch.object(replay, 'replay_projection', side_effect=AssertionError('no source stream access')), \
                self.assertRaises(replay.MissingInputs) as caught:
            replay.replay_records(documents, object(), object(), object())
        self.assertEqual(caught.exception.missing[0]['role'], 'native-original-source-proof-data-seam')

    def test_current_forward_policy_rejects_wrong_added_count_and_patch_order(self):
        for mutation in ('added', 'order'):
            fixture, catalogue, documents, overlays = self.current_candidate()
            if mutation == 'added':
                documents['source_projection']['patches'][0]['preimages']['Source/added0.txt'] = digest(b'preapplied\n')
            else:
                documents['source_projection']['patches'] *= 2
                documents['bindings']['patches'] *= 2
            with self.subTest(mutation=mutation), mock.patch.object(replay.contract, 'CATALOGUE', catalogue.catalogue), \
                    mock.patch.object(replay.native_inputs, 'SUPPLIER_PATCH', digest(fixture.patches[0])), self.assertRaises(ValueError):
                replay.derive_inventory(documents, object(), object(), object())

    def test_full_records_rejects_proof_receipt_flag_and_unknown_original_roles(self):
        for mutation in ('flag', 'role', 'mode'):
            fixture, catalogue, documents, overlays = self.current_candidate()
            if mutation == 'flag': documents['original_proof_passed'] = True
            if mutation == 'role': documents['bindings']['original_proof']['receipt'] = documents['bindings']['original_proof']['recipe']
            if mutation == 'mode': documents['bindings']['original_proof']['generator']['mode'] = 0o755
            with self.subTest(mutation=mutation), no_programs(), self.assertRaises(ValueError):
                replay.replay_records(documents, object(), object(), object())

    def test_tar_metadata_and_xz_dictionary_are_bounded_before_parser_allocation(self):
        fixture = Fixture().seal()
        header = tarfile.TarInfo('engine/oversized-pax')
        header.type, header.size = tarfile.XHDTYPE, fixture.limits['maximum_member_bytes'] + 1
        raw = gzip.compress(header.tobuf() + b'\0' * 1024)
        fixture.streams['engine'] = io.BytesIO(raw)
        fixture.projection['archives']['engine'].update(sha256=digest(raw), bytes=len(raw))
        with self.assertRaisesRegex(ValueError, 'raw tar member bytes'):
            fixture.run()
        fixture = Fixture('tar-xz').seal()
        # Supply a synthetic dictionary failure directly at the standard-library
        # decompressor boundary; no large allocation or production archive exists.
        with mock.patch.object(replay.lzma, 'LZMADecompressor', side_effect=replay.lzma.LZMAError('dictionary limit')) as constructor, self.assertRaisesRegex(ValueError, 'bounded ordinary source tar'):
            fixture.run()
        self.assertEqual(constructor.call_args.kwargs['memlimit'], replay.MAX_MEMBER)

    def test_zip_malformed_central_directory_has_a_closed_value_error(self):
        fixture = Fixture('zip').seal()
        raw = fixture.streams['engine'].getvalue().replace(b'PK\x01\x02', b'FAIL', 1)
        fixture.streams['engine'] = io.BytesIO(raw)
        fixture.projection['archives']['engine'].update(sha256=digest(raw), bytes=len(raw))
        with self.assertRaisesRegex(ValueError, 'central directory'):
            fixture.run()

    def test_zip_unbounded_dictionary_method_rejects_before_member_body_reader(self):
        fixture = Fixture('zip').seal()
        raw = bytearray(fixture.streams['engine'].getvalue())
        first_central = raw.index(b'PK\x01\x02')
        struct.pack_into('<H', raw, first_central + 10, zipfile.ZIP_LZMA)
        raw = bytes(raw)
        fixture.streams['engine'] = io.BytesIO(raw)
        fixture.projection['archives']['engine'].update(sha256=digest(raw), bytes=len(raw))
        with mock.patch.object(replay.zipfile, 'ZipFile', side_effect=AssertionError('no ZIP constructor before raw decoder bounds')), self.assertRaisesRegex(ValueError, 'bounded decoder admission'):
            fixture.run()

    def test_zip_forged_small_end_count_rejects_before_zipfile_allocation(self):
        for selected_budget, message in ((2, 'raw central count exceeds'), (1000, 'raw central count differs')):
            fixture = Fixture('zip').seal()
            raw = bytearray(fixture.streams['engine'].getvalue())
            end = raw.rindex(b'PK\x05\x06')
            struct.pack_into('<HH', raw, end + 8, 1, 1)
            raw = bytes(raw)
            fixture.streams['engine'] = io.BytesIO(raw)
            fixture.projection['archives']['engine'].update(sha256=digest(raw), bytes=len(raw))
            fixture.limits['maximum_members'] = selected_budget
            with self.subTest(selected_budget=selected_budget), no_programs(), \
                    mock.patch.object(replay.zipfile, 'ZipFile', side_effect=AssertionError('unbounded central index allocated')), \
                    self.assertRaisesRegex(ValueError, message):
                fixture.run()

    def test_zip_raw_offsets_lengths_and_end_comment_are_checked_before_constructor(self):
        for mutation in ('offset', 'record', 'comment', 'zip64'):
            fixture = Fixture('zip').seal()
            raw = bytearray(fixture.streams['engine'].getvalue())
            end, central = raw.rindex(b'PK\x05\x06'), raw.index(b'PK\x01\x02')
            if mutation == 'offset': struct.pack_into('<I', raw, end + 16, len(raw))
            if mutation == 'record': struct.pack_into('<H', raw, central + 28, 65535)
            if mutation == 'comment': struct.pack_into('<H', raw, end + 20, 1)
            if mutation == 'zip64': raw[end - 20:end - 16] = b'PK\x06\x07'
            raw = bytes(raw)
            fixture.streams['engine'] = io.BytesIO(raw)
            fixture.projection['archives']['engine'].update(sha256=digest(raw), bytes=len(raw))
            with self.subTest(mutation=mutation), no_programs(), \
                    mock.patch.object(replay.zipfile, 'ZipFile', side_effect=AssertionError('invalid raw central span allocated')), \
                    self.assertRaises(ValueError):
                fixture.run()

    def test_zip_actual_decoder_uses_one_frozen_bounded_central_instance(self):
        fixture = Fixture('zip').seal()
        stream = fixture.streams['engine']
        original = stream.getvalue()
        changed = bytearray(original)
        central = changed.index(b'PK\x01\x02')
        struct.pack_into('<H', changed, central + 10, zipfile.ZIP_LZMA)
        struct.pack_into('<I', changed, central + 24, replay.MAX_MEMBER + 1)
        real_constructor, parsed_methods = zipfile.ZipFile, []
        def changed_during_construction(source, *args, **kwargs):
            # The data source changes after raw preflight. The actual ZipFile
            # must receive the frozen bounded metadata rather than these bytes.
            stream.seek(0)
            stream.write(changed)
            stream.seek(0)
            try:
                archive = real_constructor(source, *args, **kwargs)
                parsed_methods.extend(item.compress_type for item in archive.infolist())
                return archive
            finally:
                position = stream.tell()
                stream.seek(0)
                stream.write(original)
                stream.seek(position)
        budget = replay._Budget(fixture.limits)
        source = replay._BoundedStream(stream, len(original), budget)
        files = {}
        with no_programs(), mock.patch.object(replay.zipfile, 'ZipFile', side_effect=changed_during_construction) as constructor, \
                mock.patch.object(replay.native_inputs, '_open_archive_entries', side_effect=AssertionError('second ZIP parser forbidden')):
            replay._stream_pin(source, fixture.projection['archives']['engine'], budget)
            for name, kind, mode, size, link, body in replay._archive_entries(source, 'zip', budget):
                budget.member(size)
                if kind == 'file':
                    files[name] = replay._read_member(body, size, True, budget)[1]
            replay._stream_pin(source, fixture.projection['archives']['engine'], budget)
        self.assertEqual(constructor.call_count, 1)
        self.assertTrue(parsed_methods)
        self.assertEqual(set(parsed_methods), {zipfile.ZIP_STORED})
        self.assertEqual(files['engine/Source/a.txt'], b'before\n')


class PublicMetadataFixture:
    def __init__(self, root):
        self.fixture = Fixture().seal()
        self.root, self.retained = root, root / 'retained'
        self.retained.mkdir()
        self.projection_raw = replay.encoded(self.fixture.projection)
        self.bindings = self.fixture.bindings()
        self.files = {'native-inputs/source_projection.json': self.projection_raw}
        self.identity = binding('native-inputs/toolchain-identity.json', b'inert typed declaration\n')
        entries = {self.identity['path']: {key: self.identity[key] for key in ('sha256', 'mode')} | {'role': 'config'}}
        for name in replay.manifest.HELPERS:
            entries[name] = {'sha256': digest(b'inert helper ' + name.encode()), 'mode': 0o644, 'role': 'helper'}
        entries['include/inert.h'] = {'sha256': digest(b'inert interface\n'), 'mode': 0o644, 'role': 'interface'}
        entries['native-inputs/source_projection.json'] = {'sha256': digest(self.projection_raw), 'mode': 0o644, 'role': 'config'}
        for table, role in (('archives', 'source'), ('provenance', 'data'), ('original_proof', 'data')):
            for item in self.bindings[table].values():
                entries[item['path']] = {key: item[key] for key in ('sha256', 'mode')} | {'role': role}
        for item in self.bindings['notices']:
            entries[item['path']] = {key: item[key] for key in ('sha256', 'mode')} | {'role': 'license'}
        recipe = {'schema_version': 1, 'kind': 'foundation-appended-engine-recipe', 'producer_version': 1,
            'target': copy.deepcopy(replay.contract.TARGET), 'toolchain': {'cxx_standard': 23,
                'identity_sha256': self.identity['sha256'], 'runtime_policy': 'private-native',
                'paired_sdk_sha256': None, 'target_baseline': 'windows-10-1809-unqualified'},
            'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'native'},
            'provider': {'format': 'native-shared', 'binding': 'c-abi', 'abi_major': 1,
                'abi_minor': 1, 'header': 'include/inert.h', 'header_sha256': entries['include/inert.h']['sha256']},
            'suppliers': {key: dict(item, archive=self.bindings['archives'][item['archive']]['path'])
                          for key, item in self.fixture.projection['suppliers'].items()}, 'inputs': entries,
            'patches': [], 'licenses': ['notices/inert.txt']}
        self.recipe_raw = replay.encoded(recipe)
        source_files = {name: item['sha256'] for name, item in entries.items()} | {'recipe.json': digest(self.recipe_raw)}
        dirs = parents(source_files)
        sources = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources', 'producer_version': 1,
            'recipe_id': digest(self.recipe_raw), 'files': source_files, 'directories': dirs,
            'modes': {**{name: item['mode'] for name, item in entries.items()}, 'recipe.json': 0o644,
                      **{name: 0o755 for name in dirs}}}
        self.sources_raw = replay.encoded(sources)
        self.inventory_raw = replay.encoded(inventory({'source/engine/CMakeLists.txt': b'inert assembled fact\n'}))
        self.selection = {'schema_version': 1, 'kind': replay.SELECTION_KIND,
            'target': copy.deepcopy(replay.contract.TARGET), 'source_catalogue': copy.deepcopy(replay.contract.CATALOGUE),
            'retained': {'root': str(self.retained), 'recipe_sha256': digest(self.recipe_raw),
                         'sources_sha256': digest(self.sources_raw)},
            'assembled': {'root': str(root / 'assembled-never-created'),
                          'inventory': ref(str(root / 'inventory.json'), self.inventory_raw)},
            'source_projection': ref('native-inputs/source_projection.json', self.projection_raw),
            'typed_toolchain_identity': {key: self.identity[key] for key in ('path', 'sha256')},
            'bindings': self.bindings, 'limits': self.fixture.limits}
        self.files.update({'recipe.json': self.recipe_raw, 'sources.json': self.sources_raw})
        for name, raw in self.files.items():
            path = self.retained / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o644)
        (root / 'inventory.json').write_bytes(self.inventory_raw)
        (root / 'inventory.json').chmod(0o644)
        self.save_selection()

    def save_selection(self):
        self.selection_raw = replay.encoded(self.selection)
        self.selection_path = self.root / 'selection.json'
        self.selection_path.write_bytes(self.selection_raw)
        self.selection_path.chmod(0o644)


class AdmissionTests(unittest.TestCase):
    def assert_seam(self, error):
        self.assertEqual(error.missing, ({'role': 'native-original-source-proof-data-seam',
            'path': 'tools/appended_engine_native_inputs.py#validate_source_provenance_records',
            'reason': 'frozen source-only original-proof data extraction has not been released'},))

    def test_explicit_proof_seam_cannot_be_overridden_by_truthy_flags(self):
        with no_programs(), mock.patch.object(replay, 'SOURCE_SEAM_SHA256', None), self.assertRaises(replay.MissingInputs) as caught:
            replay.require_original_proof_seam()
        self.assert_seam(caught.exception)
        with self.assertRaises(TypeError):
            replay.require_original_proof_seam(True)

    def test_public_selection_fails_before_any_supplier_or_generator_body_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PublicMetadataFixture(Path(temporary))
            original_read, seen = replay._PosixSourceInputs.read, []
            allowed = {fixture.selection_path, fixture.retained / 'recipe.json', fixture.retained / 'sources.json',
                       fixture.retained / 'native-inputs/source_projection.json', fixture.root / 'inventory.json'}
            def read(inputs, name, **kwargs):
                path = inputs.root / name
                self.assertIn(path, allowed)
                seen.append(path)
                return original_read(inputs, name, **kwargs)
            with no_programs(), mock.patch.object(replay, 'SOURCE_SEAM_SHA256', None), \
                    mock.patch.object(replay._PosixSourceInputs, 'read', new=read), self.assertRaises(replay.MissingInputs) as caught:
                replay.check_selection(fixture.selection_path, digest(fixture.selection_raw))
            self.assert_seam(caught.exception)
            self.assertEqual(set(seen), allowed)
            self.assertFalse((fixture.root / 'assembled-never-created').exists())
            self.assertFalse((fixture.retained / 'archives').exists())

    def test_public_selection_pin_missing_metadata_and_closed_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PublicMetadataFixture(Path(temporary))
            self.assertEqual(stat.S_IMODE(fixture.selection_path.stat().st_mode), 0o644)
            fixture.selection_path.chmod(0o755)
            with self.assertRaises(ValueError):
                replay.check_selection(fixture.selection_path, digest(fixture.selection_raw))
            fixture.selection_path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'independent pin'):
                replay.check_selection(fixture.selection_path, '1' * 64)
            fixture.selection['extra'] = True
            fixture.save_selection()
            with self.assertRaisesRegex(ValueError, 'selection fields'):
                replay.check_selection(fixture.selection_path, digest(fixture.selection_raw))
            fixture.selection.pop('extra')
            fixture.save_selection()
            (fixture.retained / 'sources.json').unlink()
            with self.assertRaises(replay.MissingInputs) as caught:
                replay.check_selection(fixture.selection_path, digest(fixture.selection_raw))
            self.assertEqual(caught.exception.missing[0]['role'], 'source-replay-sources')

    def test_public_selection_rejects_stale_catalogue_target_and_identity_pin(self):
        for mutation in ('catalogue', 'target', 'identity'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                fixture = PublicMetadataFixture(Path(temporary))
                if mutation == 'catalogue': fixture.selection['source_catalogue']['source_map']['sha256'] = '1' * 64
                if mutation == 'target': fixture.selection['target'] = copy.deepcopy(replay.native_inputs.TARGET)
                if mutation == 'identity': fixture.selection['typed_toolchain_identity']['sha256'] = '1' * 64
                fixture.save_selection()
                with no_programs(), self.assertRaises(ValueError):
                    replay.check_selection(fixture.selection_path, digest(fixture.selection_raw))

    def test_public_metadata_symlink_is_rejected_without_following_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PublicMetadataFixture(Path(temporary))
            original = fixture.retained / 'sources.json'
            external = fixture.root / 'external-sources.json'
            original.rename(external)
            original.symlink_to(external)
            with no_programs(), self.assertRaises(ValueError):
                replay.check_selection(fixture.selection_path, digest(fixture.selection_raw))

    def test_original_proof_binding_mode_and_active_recipe_mismatch_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PublicMetadataFixture(Path(temporary))
            fixture.selection['bindings']['original_proof']['generator']['mode'] = 0o755
            fixture.save_selection()
            with self.assertRaisesRegex(ValueError, 'mode0644'):
                replay.check_selection(fixture.selection_path, digest(fixture.selection_raw))
            fixture.selection['bindings']['original_proof']['generator']['mode'] = 0o644
            fixture.selection['bindings']['original_proof']['recipe']['sha256'] = '1' * 64
            fixture.save_selection()
            with self.assertRaisesRegex(ValueError, 'active R/S'):
                replay.check_selection(fixture.selection_path, digest(fixture.selection_raw))

    def test_cli_missing_seam_is_exit2_and_pin_failure_exit1(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PublicMetadataFixture(Path(temporary))
            args = ['check', '--selection', str(fixture.selection_path), '--selection-sha256', digest(fixture.selection_raw)]
            output = io.StringIO()
            with no_programs(), mock.patch.object(replay, 'SOURCE_SEAM_SHA256', None), redirect_stderr(output):
                self.assertEqual(replay.cli(args), 2)
            self.assertIn('native-original-source-proof-data-seam', output.getvalue())
            args[-1] = '1' * 64
            with redirect_stderr(io.StringIO()):
                self.assertEqual(replay.cli(args), 1)

    def test_native_handoff_external_selection_preflight_has_no_body_walk(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PublicMetadataFixture(Path(temporary))
            root = fixture.root / 'capsule'
            raw_files = {'retained/recipe.json': fixture.recipe_raw, 'retained/sources.json': fixture.sources_raw,
                'retained/native-inputs/source_projection.json': fixture.projection_raw,
                replay.handoff.PATHS['assembled_inventory']: fixture.inventory_raw}
            for name, raw in raw_files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                path.chmod(0o644)
            value = {'schema_version': 1, 'kind': replay.handoff.KIND, 'scope': replay.handoff.SCOPE,
                'target': replay.contract.TARGET, 'source_catalogue': replay.contract.CATALOGUE,
                'paths': replay.handoff.PATHS, **inventory(raw_files),
                **{key: False for key in replay.handoff.FALSE_FACTS}}
            raw = replay.encoded(value)
            (root / 'handoff.json').write_bytes(raw)
            (root / 'handoff.json').chmod(0o644)
            external = ref(str(fixture.selection_path), fixture.selection_raw)
            with no_programs(), mock.patch.object(replay, 'SOURCE_SEAM_SHA256', None), \
                    mock.patch.object(replay.handoff, '_scan', side_effect=AssertionError('body scan forbidden')), self.assertRaises(replay.MissingInputs) as caught:
                replay.verify_for_handoff(root, digest(raw), external)
            self.assert_seam(caught.exception)
            with self.assertRaises(ValueError):
                replay.verify_for_handoff(root, digest(raw), {'path': 'selection.json', 'sha256': external['sha256']})
            value['files']['retained/recipe.json'] = '1' * 64
            raw = replay.encoded(value)
            (root / 'handoff.json').write_bytes(raw)
            (root / 'handoff.json').chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'subject differs'):
                replay.verify_for_handoff(root, digest(raw), external)


class ReleasedSharedRecordConsumerTests(unittest.TestCase):
    """Use the maintained tiny synthetic fixture and the actual released checker."""
    def test_real_checked_object_reaches_real_proof_join_and_passive_views_cannot_join(self):
        from test_appended_engine_native_inputs import checked_record_fixture
        self.api = replay.native_inputs
        value, records, streams, originals, original_projection, _captured_inputs = checked_record_fixture(self, retained=True)
        limits = {'seconds': 10, 'maximum_archive_bytes': 1024 * 1024,
            'maximum_expanded_bytes': 16 * 1024 * 1024, 'maximum_members': 10000,
            'maximum_member_bytes': 1024 * 1024, 'maximum_patch_bytes': 1024 * 1024}
        real_parser = self.api.parse_source_projection_records
        real_proof = self.api.validate_source_provenance_records
        actual_proof_results = []
        def observe_real_proof(*args, **kwargs):
            result = real_proof(*args, **kwargs)
            actual_proof_results.append(result)
            return result
        with no_programs(), \
                mock.patch.object(self.api, 'parse_source_projection_records', wraps=real_parser) as parser, \
                mock.patch.object(self.api, 'validate_source_provenance_records', side_effect=observe_real_proof) as proof:
            checked, facts = replay.check_records(value, records, streams, originals, limits)
        parser.assert_called_once_with(value, records, streams, limits)
        proof.assert_called_once_with(checked, records['provenance'], originals)
        self.assertIs(proof.call_args.args[0], checked)
        self.assertIs(facts, actual_proof_results[0])
        self.assertIsNot(checked, value)
        self.assertIs(type(facts), dict)
        self.assertTrue(facts)
        view = checked.as_dict()
        self.assertEqual(view, checked.as_dict())
        self.assertIsNot(view, checked.as_dict())
        view['suppliers']['engine']['commit'] = '0' * 40
        self.assertNotEqual(view, checked.as_dict())
        for candidate in (value, original_projection, checked.as_dict(), copy.deepcopy(checked.as_dict())):
            with self.subTest(candidate_keys=sorted(candidate)), no_programs(), self.assertRaises((TypeError, ValueError)):
                real_proof(candidate, records['provenance'], originals)


class CheckedRecordWiringOnlyTests(unittest.TestCase):
    """Lower APIs are mocked: these cases establish call wiring, not admission."""
    def fixture(self):
        fixture = Fixture().seal()
        records, original = _wiring_only_record_tables(fixture)
        return fixture, records, original

    def test_wiring_only_shared_parser_result_is_passed_to_proof_join_by_identity(self):
        fixture, records, original = self.fixture()
        lower_api, lower_checked = mock.Mock(), object()
        proof_facts = {'inert_wiring_fact': 'original-proof-result'}
        lower_api.parse_source_projection_records.return_value = lower_checked
        lower_api.validate_source_provenance_records.return_value = proof_facts
        with no_programs(), mock.patch.object(replay, 'require_original_proof_seam', return_value=lower_api):
            checked, facts = replay.check_records(fixture.projection, records, fixture.streams,
                                                  original, fixture.limits)
        self.assertIs(checked, lower_checked)
        self.assertEqual(facts, proof_facts)
        lower_api.parse_source_projection_records.assert_called_once_with(
            fixture.projection, records, fixture.streams, fixture.limits)
        lower_api.validate_source_provenance_records.assert_called_once_with(
            lower_checked, records['provenance'], original)

    def test_wiring_only_projection_failure_prevents_proof_join(self):
        fixture, records, original = self.fixture()
        lower_api = mock.Mock()
        lower_api.parse_source_projection_records.side_effect = ValueError('inert parser rejection')
        with no_programs(), mock.patch.object(replay, 'require_original_proof_seam', return_value=lower_api), \
                self.assertRaisesRegex(ValueError, 'parser rejection'):
            replay.check_records(fixture.projection, records, fixture.streams, original, fixture.limits)
        lower_api.validate_source_provenance_records.assert_not_called()

    def test_wiring_only_original_proof_rejection_is_not_an_admitted_result(self):
        fixture, records, original = self.fixture()
        lower_api = mock.Mock()
        lower_checked = lower_api.parse_source_projection_records.return_value = object()
        lower_api.validate_source_provenance_records.side_effect = ValueError('inert proof rejection')
        with no_programs(), mock.patch.object(replay, 'require_original_proof_seam', return_value=lower_api), \
                self.assertRaisesRegex(ValueError, 'proof rejection'):
            replay.check_records(fixture.projection, records, fixture.streams, original, fixture.limits)
        lower_api.validate_source_provenance_records.assert_called_once_with(
            lower_checked, records['provenance'], original)

    def test_wiring_only_metadata_preflight_time_cannot_extend_the_shared_parser_budget(self):
        fixture, records, original = self.fixture()
        now, lower_api = [0.0], mock.Mock()
        view = copy.deepcopy(fixture.projection)
        view['_files'] = copy.deepcopy(view['projection']['files'])
        lower_api.parse_source_projection_records.return_value.as_dict.return_value = view
        lower_api.validate_source_provenance_records.return_value = {'wiring_only': True}
        def delayed_metadata(documents):
            now[0] = 7.0
            return fixture.projection, fixture.limits, fixture.bindings(), {
                'overlays': {}, 'source_map': {'inputs': {}}}
        with no_programs(), mock.patch.object(replay.time, 'monotonic', side_effect=lambda: now[0]), \
                mock.patch.object(replay, '_documents', side_effect=delayed_metadata), \
                mock.patch.object(replay, 'require_original_proof_seam', return_value=lower_api), \
                mock.patch.object(replay.native_inputs, '_forward_patch_contract'):
            result = replay.replay_records({}, fixture.streams, [], {}, captured_records=records,
                original_proof_records=original, deadline=10.0)
        self.assertEqual(lower_api.parse_source_projection_records.call_args.args[3]['seconds'], 3.0)
        self.assertTrue(result['original_proof_admitted'])  # Mocked wiring fact only.
        self.assertTrue(all(result[name] is False for name in replay.handoff.FALSE_FACTS))
        lower_api.reset_mock()
        with no_programs(), mock.patch.object(replay.time, 'monotonic', return_value=10.0), \
                mock.patch.object(replay, 'require_original_proof_seam', return_value=lower_api), \
                self.assertRaisesRegex(ValueError, 'original wall budget'):
            replay.check_records(fixture.projection, records, fixture.streams, original,
                fixture.limits, deadline=10.0)
        lower_api.parse_source_projection_records.assert_not_called()

    def test_unreleased_gate_ignores_present_shared_record_api_symbols(self):
        with no_programs(), mock.patch.object(replay, 'SOURCE_SEAM_SHA256', None), \
                mock.patch.object(replay.native_inputs, 'parse_source_projection_records', create=True) as parser, \
                mock.patch.object(replay.native_inputs, 'validate_source_provenance_records', create=True) as proof, \
                self.assertRaises(replay.MissingInputs) as caught:
            replay.require_original_proof_seam()
        self.assertEqual(caught.exception.missing[0]['role'], 'native-original-source-proof-data-seam')
        parser.assert_not_called()
        proof.assert_not_called()


class CapturedSourceWiringOnlyTests(unittest.TestCase):
    """Exercise capsule capture; the shared semantic checker remains mocked."""
    def test_wiring_only_relative_and_absolute_relocation_preserves_original_record_paths(self):
        for absolute in (False, True):
            with self.subTest(absolute=absolute), tempfile.TemporaryDirectory(prefix='windows-capture-wiring-inert-') as temporary:
                root = Path(temporary)
                fixture, records, original, bindings = _wiring_only_capture_fixture(root, absolute=absolute)
                lower_checked, proof_facts = object(), {'inert_wiring_fact': 'source-proof'}
                with no_programs(), mock.patch.object(replay, 'check_records',
                        return_value=(lower_checked, proof_facts)) as checked_records:
                    captured = replay._CapturedSource(fixture.projection, bindings, fixture.limits,
                        resolve=lambda path: path if absolute else root / path, relative=not absolute)
                    try:
                        self.assertEqual(captured.records, records)
                        self.assertEqual(captured.original_proof, original)
                        self.assertTrue(all(not item['path'].startswith('relocated/')
                            for item in captured.records['provenance'].values()))
                        checked, facts = captured.checked()
                        self.assertIs(checked, lower_checked)
                        self.assertEqual(facts, proof_facts)
                        args = checked_records.call_args.args
                        self.assertEqual(args[0], fixture.projection)
                        self.assertEqual(args[1], records)
                        self.assertEqual(set(args[2]), set(fixture.projection['archives']))
                        self.assertTrue(all(args[2][key] is captured.streams[key] for key in args[2]))
                        self.assertEqual(args[3], original)
                        self.assertGreater(args[4]['seconds'], 0)
                        self.assertLessEqual(args[4]['seconds'], fixture.limits['seconds'])
                        self.assertEqual({key: value for key, value in args[4].items() if key != 'seconds'},
                            {key: value for key, value in fixture.limits.items() if key != 'seconds'})
                        captured.check()
                    finally:
                        captured.close()
                checked_records.assert_called_once()

    def test_capsule_metadata_mode0755_is_not_reinterpreted_as0644(self):
        with tempfile.TemporaryDirectory(prefix='windows-capture-mode-inert-') as temporary:
            root = Path(temporary)
            fixture, records, original, bindings = _wiring_only_capture_fixture(root)
            bindings['provenance'][next(iter(bindings['provenance']))]['mode'] = 0o755
            with no_programs(), self.assertRaisesRegex(ValueError, 'mode0644'):
                replay._CapturedSource(fixture.projection, bindings, fixture.limits, resolve=lambda path: root / path)

    def test_physical_capture_replacement_is_rejected_before_shared_semantic_check(self):
        with tempfile.TemporaryDirectory(prefix='windows-capture-replacement-inert-') as temporary:
            root = Path(temporary)
            fixture, records, original, bindings = _wiring_only_capture_fixture(root)
            with no_programs(), mock.patch.object(replay, 'check_records',
                    side_effect=AssertionError('shared proof after physical input replacement')):
                captured = replay._CapturedSource(fixture.projection, bindings, fixture.limits, resolve=lambda path: root / path)
                try:
                    role = next(iter(bindings['provenance']))
                    path = root / bindings['provenance'][role]['path']
                    path.rename(path.with_name(path.name + '.retained-old'))
                    path.write_bytes(records['provenance'][role]['raw'])
                    path.chmod(0o644)
                    with self.assertRaises(ValueError):
                        captured.checked()
                finally:
                    captured.close()


class SourceInspectionWiringOnlyTests(unittest.TestCase):
    """Private fake lower captures exercise ownership, never native admission."""
    def setUp(self):
        self.now = [101.0]
        self.root = r'C:\inert\capsule'
        self.handoff_pin = digest(b'inert inspection handoff')
        self.replay_reference = {'path': r'C:\inert\replay.json',
                                 'sha256': digest(b'inert inspection replay')}
        self.limits = {'seconds': 10, 'maximum_archive_bytes': 1024,
            'maximum_expanded_bytes': 1024, 'maximum_members': 10,
            'maximum_member_bytes': 1024, 'maximum_patch_bytes': 1024}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(no_programs())
        self.stack.enter_context(mock.patch.object(replay.time, 'monotonic',
                                                   side_effect=lambda: self.now[0]))

    def owner(self, *, explicit=True, resources=None, lifetime=200.0):
        deadline, supplied = replay._source_lifetime(100.0, lifetime if explicit else None)
        owner = replay._SourceInspectionOwner(self.root, self.handoff_pin,
            self.replay_reference, 100.0, deadline, supplied)
        owner.resources.extend(resources if resources is not None else
                               [mock.Mock(spec=('check', 'close'))])
        self.addCleanup(owner.close)
        owner.set_source_limits(self.limits)
        return owner

    def issue(self, *, explicit=True, resources=None, facts=None):
        owner = self.owner(explicit=explicit, resources=resources)
        checked = object()
        facts = ({'wiring_only': {'source': ['checked once']},
                  **{name: False for name in replay.handoff.FALSE_FACTS}}
                 if facts is None else facts)
        inspection = owner.hold(checked, facts)
        return owner, inspection, checked

    def test_issued_handle_retains_exact_checked_resources_records_and_subject(self):
        resources = [mock.Mock(spec=('check', 'close')) for unused in range(2)]
        owner = self.owner(resources=resources)
        borrowed, records, checked = object(), {'raw': b'inert original record'}, object()
        owner.borrowed.append(borrowed)
        owner.raw_records.append(records)
        inspection = owner.hold(checked, {'wiring_only': True})
        self.assertIs(replay._SOURCE_INSPECTIONS[inspection], owner)
        self.assertIs(owner.checked, checked)
        self.assertIs(owner.borrowed[0], borrowed)
        self.assertIs(owner.raw_records[0], records)
        self.assertTrue(all(held is actual for held, actual in zip(owner.resources, resources)))
        self.replay_reference['sha256'] = digest(b'caller mutation after issuance')
        self.assertEqual(owner.subject[2]['sha256'], digest(b'inert inspection replay'))
        for resource in resources:
            resource.check.assert_called_once_with()
            resource.close.assert_not_called()

    def test_passive_fresh_views_do_not_check_resources_or_read_or_parse_bodies(self):
        facts = {'wiring_only': {'source': ['original']},
                 **{name: False for name in replay.handoff.FALSE_FACTS}}
        owner, inspection, checked = self.issue(facts=facts)
        facts['wiring_only']['source'].append('caller changed facts')
        for resource in owner.resources:
            resource.check.side_effect = AssertionError('passive view checked a resource')
        with mock.patch.object(replay, '_pinned_metadata', side_effect=AssertionError('body read')), \
                mock.patch.object(replay, 'check_records', side_effect=AssertionError('source parse')):
            first = inspection.as_dict()
            first['wiring_only']['source'].append('first passive view mutation')
            second = inspection.as_dict()
        self.assertEqual(second['wiring_only']['source'], ['original'])
        self.assertTrue(all(second[name] is False for name in replay.handoff.FALSE_FACTS))
        self.assertIs(owner.checked, checked)

    def test_constructor_forgery_copies_and_foreign_subjects_cannot_supply_authority(self):
        owner, inspection, checked = self.issue()
        with self.assertRaises(TypeError):
            replay.SourceInspection()
        for forged in (inspection.as_dict(), object(), object.__new__(replay.SourceInspection)):
            with self.subTest(forged=type(forged).__name__), self.assertRaises(ValueError):
                replay._require_source_inspection(forged, self.root, self.handoff_pin,
                                                  self.replay_reference)
        for copier in (copy.copy, copy.deepcopy):
            try:
                copied = copier(inspection)
            except (TypeError, ValueError):
                continue
            self.assertIsNot(copied, inspection)
            with self.assertRaises(ValueError):
                replay._require_source_inspection(copied, self.root, self.handoff_pin,
                                                  self.replay_reference)
        subjects = [(r'C:\inert\other', self.handoff_pin, self.replay_reference),
                    (self.root, digest(b'other handoff'), self.replay_reference),
                    (self.root, self.handoff_pin,
                     {'path': r'C:\inert\other.json', 'sha256': self.replay_reference['sha256']})]
        for root, pin, reference in subjects:
            with self.subTest(subject=(root, pin, reference)), self.assertRaisesRegex(ValueError, 'another'):
                replay._require_source_inspection(inspection, root, pin, reference)
        self.assertIs(owner.checked, checked)
        self.assertEqual(replay._require_source_inspection(inspection, self.root,
            self.handoff_pin, self.replay_reference), inspection.as_dict())

    def test_held_checks_after_work_budget_use_original_lifetime_without_body_work(self):
        owner, inspection, checked = self.issue()
        resource = owner.resources[0]
        resource.reset_mock()
        self.now[0] = 111.0  # Original source work ended at 110; enclosing L stays 200.
        with mock.patch.object(replay, '_pinned_metadata', side_effect=AssertionError('held body read')), \
                mock.patch.object(replay, 'check_records', side_effect=AssertionError('held proof reparse')), \
                mock.patch.object(replay, '_CapturedSource', side_effect=AssertionError('new capture')):
            inspection.check()
            self.now[0] = 199.0
            inspection.check()
        self.assertEqual(resource.check.call_count, 2)
        self.assertEqual((owner.initial_deadline, owner.deadline, owner.work_deadline), (200.0, 200.0, 110.0))
        self.assertIs(owner.checked, checked)
        self.now[0] = 200.0
        with self.assertRaisesRegex(ValueError, 'wall budget'):
            inspection.check()
        self.assertEqual(resource.check.call_count, 2)
        self.assertEqual(owner.phase, 'revoked')
        resource.close.assert_not_called()

    def test_revoke_retains_owners_then_explicit_close_clears_resources_once(self):
        resources = [mock.Mock(spec=('check', 'close')) for unused in range(2)]
        owner, inspection, checked = self.issue(resources=resources)
        borrowed = mock.Mock(spec=('close',))
        owner.borrowed.append(borrowed)
        owner.raw_records.append(b'inert original bytes')
        inspection.revoke()
        self.assertIs(owner.checked, checked)
        self.assertEqual(owner.resources, resources)
        self.assertEqual(owner.borrowed, [borrowed])
        for operation in (inspection.check, inspection.as_dict,
                          lambda: replay._require_source_inspection(inspection, self.root,
                              self.handoff_pin, self.replay_reference)):
            with self.assertRaisesRegex(ValueError, 'revoked'):
                operation()
        for resource in resources:
            resource.close.assert_not_called()
        inspection.close()
        inspection.close()
        self.assertTrue(owner.closed)
        self.assertEqual(owner.phase, 'closed')
        self.assertEqual((owner.resources, owner.borrowed, owner.raw_records), ([], [], []))
        self.assertIsNone(owner.checked)
        for resource in resources:
            resource.close.assert_called_once_with()
        borrowed.close.assert_not_called()

    def test_failed_physical_check_revokes_without_closing_or_rechecking(self):
        owner, inspection, checked = self.issue()
        resource = owner.resources[0]
        resource.reset_mock()
        resource.check.side_effect = ValueError('inert retained identity changed')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            inspection.check()
        self.assertEqual(owner.phase, 'revoked')
        self.assertIs(owner.checked, checked)
        self.assertEqual(owner.resources, [resource])
        with self.assertRaisesRegex(ValueError, 'revoked'):
            inspection.check()
        resource.check.assert_called_once_with()
        resource.close.assert_not_called()
        inspection.close()
        resource.close.assert_called_once_with()

    def test_uncertain_close_retains_actual_revoked_owner_until_cleanup_is_known(self):
        owner, inspection, checked = self.issue()
        resource = owner.resources[0]
        resource.close.side_effect = ValueError('inert close remains uncertain')
        retained = []
        with mock.patch.object(replay, '_UNCERTAIN_SOURCE_OWNERS', retained):
            try:
                with self.assertRaisesRegex(ValueError, 'uncertain'):
                    inspection.close()
                self.assertEqual(retained, [owner])
                self.assertFalse(owner.closed)
                self.assertEqual(owner.phase, 'revoked')
                self.assertIs(owner.checked, checked)
                self.assertEqual(owner.resources, [resource])
                with self.assertRaisesRegex(ValueError, 'revoked'):
                    inspection.check()
            finally:
                resource.close.side_effect = None
                inspection.close()
        self.assertTrue(owner.closed)

    def test_lifetime_is_finite_future_and_cannot_exceed_existing_hard_cap(self):
        self.assertEqual(replay._source_lifetime(100.0, None), (86500.0, False))
        self.assertEqual(replay._source_lifetime(100.0, 86500.0), (86500.0, True))
        for deadline in (True, False, float('nan'), float('inf'), -float('inf'), 100.0, 99.0, '200'):
            with self.subTest(deadline=deadline), self.assertRaisesRegex(ValueError, 'finite future'):
                replay._source_lifetime(100.0, deadline)
        with self.assertRaises(replay.MissingInputs) as caught:
            replay._source_lifetime(100.0, 86501.0)
        self.assertEqual(caught.exception.missing[0]['role'], 'windows-source-enclosing-lifetime-cap')
        with mock.patch.object(replay, '_native_input_reader', side_effect=AssertionError('reader discovery')), \
                mock.patch.object(replay, '_PosixSourceInputs', side_effect=AssertionError('source open')), \
                self.assertRaises(replay.MissingInputs) as caught:
            replay.inspect_for_handoff(self.root, self.handoff_pin, self.replay_reference,
                                       deadline=self.now[0] + 86401.0)
        self.assertEqual(caught.exception.missing[0]['role'], 'windows-source-enclosing-lifetime-cap')

    def test_selected_work_budget_includes_bootstrap_and_expired_admission_never_holds(self):
        self.now[0] = 107.0
        owner = self.owner()
        self.assertEqual(owner.source_limits()['seconds'], 3.0)
        self.assertEqual(owner.work_deadline, 110.0)
        shorter = self.owner(lifetime=108.0)
        self.assertEqual(shorter.source_limits()['seconds'], 1.0)
        self.assertEqual(shorter.work_deadline, 108.0)
        self.now[0] = 110.0
        with self.assertRaisesRegex(ValueError, 'wall budget'):
            owner.hold(object(), {'wiring_only': True})
        self.assertEqual(owner.phase, 'revoked')
        self.assertIsNone(owner.checked)
        self.now[0] = 109.0
        late = self.owner()
        late.resources[0].check.side_effect = lambda: self.now.__setitem__(0, 111.0)
        with self.assertRaisesRegex(ValueError, 'wall budget'):
            late.hold(object(), {'wiring_only': True})
        self.assertEqual(late.phase, 'revoked')

    def test_held_source_cannot_reopen_work_and_default_lifetime_ends_with_work(self):
        owner, inspection, checked = self.issue(explicit=False)
        self.assertEqual((owner.initial_deadline, owner.deadline, owner.work_deadline),
                         (86500.0, 110.0, 110.0))
        for operation in (owner.source_limits,
                          lambda: owner.set_source_limits(dict(self.limits, seconds=20)),
                          lambda: owner.charge(('capsule', 'late'), 1, digest(b'x'), 0o644)):
            with self.assertRaisesRegex(ValueError, 'Held'):
                operation()
        self.assertIs(owner.checked, checked)
        self.now[0] = 111.0
        with self.assertRaisesRegex(ValueError, 'wall budget'):
            inspection.check()
        self.assertEqual(owner.deadline, 110.0)

    def test_aggregate_bootstrap_charges_both_owners_and_rejects_conflicting_reuse(self):
        for bound in ('bytes', 'members', 'member bytes'):
            with self.subTest(bound=bound):
                owner = self.owner()
                pin = digest(b'inert observed metadata')
                owner.charge(('capsule', 'metadata'), 6, pin, 0o644)
                owner.charge(('capsule', 'metadata'), 6, pin, 0o644)
                self.assertEqual((owner.input_bytes, owner.input_members), (6, 1))
                with self.assertRaisesRegex(ValueError, 'Conflicting'):
                    owner.charge(('capsule', 'metadata'), 7, pin, 0o644)
                owner.charge(('external-replay', 'metadata'), 6, pin, 0o644)
                self.assertEqual((owner.input_bytes, owner.input_members), (12, 2))
                reduced = {'bytes': {'maximum_expanded_bytes': 11},
                           'members': {'maximum_members': 1},
                           'member bytes': {'maximum_member_bytes': 5}}
                limits = dict(self.limits, **reduced[bound])
                with self.assertRaises(ValueError):
                    owner.set_source_limits(limits)

    def test_passive_wrapper_forwards_subject_and_optional_limits_and_always_closes(self):
        for failure in (None, 'check', 'view'):
            with self.subTest(failure=failure):
                events = []
                inspection = mock.Mock(spec=('check', 'as_dict', 'close'))
                def check():
                    events.append('check')
                    if failure == 'check':
                        raise ValueError('inert check failure')
                def view():
                    events.append('view')
                    if failure == 'view':
                        raise ValueError('inert passive view failure')
                    return {'wiring_only': True}
                inspection.check.side_effect = check
                inspection.as_dict.side_effect = view
                inspection.close.side_effect = lambda: events.append('close')
                qualification = object()
                with mock.patch.object(replay, 'inspect_for_handoff', return_value=inspection) as inspect:
                    if failure is None:
                        result = replay.verify_for_handoff(self.root, self.handoff_pin,
                            self.replay_reference, input_qualification=qualification, deadline=190.0)
                        self.assertEqual(result, {'wiring_only': True})
                    else:
                        with self.assertRaisesRegex(ValueError, 'inert'):
                            replay.verify_for_handoff(self.root, self.handoff_pin,
                                self.replay_reference, input_qualification=qualification, deadline=190.0)
                self.assertEqual(inspect.call_args.args,
                                 (self.root, self.handoff_pin, self.replay_reference))
                self.assertIs(inspect.call_args.kwargs['input_qualification'], qualification)
                self.assertEqual(inspect.call_args.kwargs['deadline'], 190.0)
                self.assertEqual(events, ['check', 'close'] if failure == 'check'
                                 else ['check', 'view', 'close'])
                inspection.close.assert_called_once_with()


class SourceTreeWiringOnlyTests(unittest.TestCase):
    """Tiny fake A observations test B caching and complete-inventory wiring."""
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(no_programs())
        self.stack.enter_context(mock.patch.object(replay.time, 'monotonic', return_value=101.0))

    def fixture(self):
        bodies = {'metadata.json': b'{"inert":true}\n', 'supplier.bin': b'inert archive bytes',
                  'source/header.h': b'// inert ordinary source\n'}
        files = {name: {'sha256': digest(raw), 'mode': 0o755 if name.endswith('.h') else 0o644}
                 for name, raw in bodies.items()}
        files['supplier.bin']['bytes'] = len(bodies['supplier.bin'])
        directories = ['empty', 'source']
        view = {'root': '', 'files': copy.deepcopy(files), 'directories': directories,
                'observed': {'files': {name: {'bytes': len(raw)} for name, raw in bodies.items()},
                             'directories': {name: {} for name in ('', *directories)}}}
        stream = mock.Mock(wraps=io.BytesIO(bodies['source/header.h']), spec=io.BytesIO)
        archive = mock.Mock(spec=('read', 'seek', 'close'))
        tree = SimpleNamespace(as_dict=mock.Mock(return_value=view),
                               open_file=mock.Mock(return_value=stream), close=mock.Mock())
        actual = SimpleNamespace(read=mock.Mock(return_value=bodies['metadata.json']),
            open_archive=mock.Mock(return_value=archive), capture_tree=mock.Mock(return_value=tree),
            check=mock.Mock(), close=mock.Mock())
        owner = replay._SourceInspectionOwner(r'C:\inert\capsule', digest(b'inert handoff'),
            {'path': r'C:\inert\replay.json', 'sha256': digest(b'inert replay')}, 100.0, 200.0, True)
        owner.resources.append(actual)
        self.addCleanup(owner.close)
        owner.set_source_limits({'seconds': 10, 'maximum_archive_bytes': 1024,
            'maximum_expanded_bytes': 1024, 'maximum_members': 10,
            'maximum_member_bytes': 1024, 'maximum_patch_bytes': 1024})
        return owner, replay._SourceInputs(owner, actual), actual, tree, stream, archive, bodies, files, directories

    def test_tree_reuses_metadata_and_archive_captures_and_hashes_only_remaining_leaf(self):
        owner, inputs, actual, tree, stream, archive, bodies, files, directories = self.fixture()
        self.assertEqual(inputs.read('metadata.json', files['metadata.json']), bodies['metadata.json'])
        self.assertEqual(inputs.read('metadata.json', files['metadata.json']), bodies['metadata.json'])
        self.assertIs(inputs.archive('supplier.bin', files['supplier.bin']), archive)
        self.assertIs(inputs.archive('supplier.bin', files['supplier.bin']), archive)
        self.assertIs(inputs.capture_tree(files, directories), tree)
        actual.read.assert_called_once_with('metadata.json', expected=files['metadata.json'],
                                           maximum=owner.limits['maximum_member_bytes'])
        actual.open_archive.assert_called_once_with('supplier.bin', expected=files['supplier.bin'])
        actual.capture_tree.assert_called_once_with('', files=files, directories=directories)
        tree.open_file.assert_called_once_with('source/header.h')
        self.assertEqual(stream.read.call_count, 2)  # One tiny body and its EOF.
        archive.read.assert_not_called()
        self.assertEqual((owner.input_bytes, owner.input_members),
                         (sum(map(len, bodies.values())), len(files) + len(directories)))
        self.assertNotIn('bytes', files['source/header.h'])
        self.assertEqual(tree.as_dict.return_value['observed']['files']['source/header.h'],
                         {'bytes': len(bodies['source/header.h'])})
        checked = object()
        inspection = owner.hold(checked, {'wiring_only': True})
        read_count = stream.read.call_count
        inspection.check()
        inspection.check()
        for operation in (lambda: inputs.read('metadata.json', files['metadata.json']),
                          lambda: inputs.archive('supplier.bin', files['supplier.bin']),
                          lambda: inputs.capture_tree(files, directories)):
            with self.assertRaises(ValueError):
                operation()
        self.assertIs(owner.checked, checked)
        self.assertEqual(stream.read.call_count, read_count)
        actual.read.assert_called_once()
        actual.open_archive.assert_called_once()
        actual.capture_tree.assert_called_once_with('', files=files, directories=directories)
        tree.as_dict.assert_called_once_with()
        tree.open_file.assert_called_once_with('source/header.h')
        inspection.close()
        actual.close.assert_called_once_with()
        for borrowed in (tree, stream, archive):
            borrowed.close.assert_not_called()

    def test_tree_observations_reject_missing_extra_names_lengths_and_changed_body(self):
        for mutation in ('extra leaf', 'missing leaf', 'missing empty directory', 'cached length',
                         'body pin', 'body EOF', 'member cap'):
            with self.subTest(mutation=mutation):
                owner, inputs, actual, tree, stream, archive, bodies, files, directories = self.fixture()
                inputs.read('metadata.json', files['metadata.json'])
                inputs.archive('supplier.bin', files['supplier.bin'])
                observed = tree.as_dict.return_value['observed']
                if mutation == 'extra leaf':
                    observed['files']['undeclared.h'] = {'bytes': 1}
                elif mutation == 'missing leaf':
                    observed['files'].pop('source/header.h')
                elif mutation == 'missing empty directory':
                    observed['directories'].pop('empty')
                elif mutation == 'cached length':
                    observed['files']['metadata.json']['bytes'] += 1
                elif mutation == 'body pin':
                    stream.read.side_effect = [b'x' * len(bodies['source/header.h']), b'']
                elif mutation == 'body EOF':
                    stream.read.side_effect = [b'x' * (len(bodies['source/header.h']) + 1)]
                else:
                    owner.limits['maximum_members'] = len(files) + len(directories) - 1
                with self.assertRaises(ValueError):
                    inputs.capture_tree(files, directories)
                archive.read.assert_not_called()
                if mutation == 'member cap':
                    actual.capture_tree.assert_not_called()
                if mutation in ('extra leaf', 'missing leaf', 'missing empty directory', 'cached length', 'member cap'):
                    tree.open_file.assert_not_called()

    def test_present_tree_symbols_cannot_override_the_unreleased_tree_source_gate(self):
        api = SimpleNamespace(AnchoredInputs=SimpleNamespace(capture_tree=mock.Mock()))
        with mock.patch.object(replay, 'NATIVE_INPUT_TREE_SHA256', None), \
                mock.patch.object(replay, '_native_reader_source', side_effect=AssertionError('tree source read')), \
                self.assertRaises(replay.MissingInputs) as caught:
            replay._native_tree_reader(api)
        self.assertEqual(caught.exception.missing[0]['role'], 'windows-native-input-tree-source')
        api.AnchoredInputs.capture_tree.assert_not_called()

    def test_wiring_only_posix_selection_reuses_captures_and_checks_both_complete_trees(self):
        """Mock source/proof boundaries; this private path issues no handoff handle."""
        roles = ('source_map', 'provenance', 'graph')
        catalogue_raw = {role: ('inert catalogue ' + role).encode() for role in roles}
        catalogue_pins = {role: {'sha256': digest(raw)} for role, raw in catalogue_raw.items()}
        retained_bodies = {'catalogue/' + role + '.json': raw for role, raw in catalogue_raw.items()}
        retained_bodies.update({'archives/engine.bin': b'inert archive',
            'overlays/one.h': b'// inert overlay\n', 'include/extra.h': b'// retained ordinary leaf\n'})
        assembled_bodies = {'source/engine/fixture.cpp': b'// assembled ordinary leaf\n'}
        retained_expected, assembled_expected = inventory(retained_bodies), inventory(assembled_bodies)
        recipe = {'inputs': {'catalogue/' + role + '.json':
                  {'sha256': catalogue_pins[role]['sha256'], 'mode': 0o644} for role in roles}}
        value = {'limits': Fixture().limits,
            'source_catalogue': copy.deepcopy(catalogue_pins),
            'retained': {'recipe_sha256': digest(b'inert active recipe'),
                         'sources_sha256': digest(b'inert active sources')},
            'assembled': {'inventory': ref('/inert/assembled-inventory.json', b'inert inventory')},
            'bindings': {'wiring_only': 'lower capture is explicitly mocked'}}
        projection, sources, checked = object(), object(), object()
        records, original = {'patches': [{'raw': b'inert patch'}]}, {'wiring_only': b'inert original proof'}
        archive = mock.Mock(spec=('read', 'seek', 'close'))
        retained, assembled = mock.Mock(), mock.Mock()
        retained.read.side_effect = lambda name, **unused: retained_bodies[name]
        retained.open_archive.return_value = archive
        trees, captured, events = {}, {}, []

        def capture_records(owner, inputs, selected, bindings, *, prefix):
            captured.update(owner=owner, inputs=inputs)
            self.assertIs(selected, projection)
            self.assertIs(bindings, value['bindings'])
            self.assertEqual(prefix, '')
            self.assertEqual(inputs.read('catalogue/source_map.json',
                {'sha256': catalogue_pins['source_map']['sha256'], 'mode': 0o644}), catalogue_raw['source_map'])
            stream = inputs.archive('archives/engine.bin',
                {'sha256': digest(retained_bodies['archives/engine.bin']),
                 'bytes': len(retained_bodies['archives/engine.bin']), 'mode': 0o644})
            captured['streams'] = {'engine': stream}
            return records, captured['streams'], original

        def replay_checked(documents, streams, patches, overlays, **arguments):
            self.assertIs(streams, captured['streams'])
            self.assertIs(streams['engine'], archive)
            self.assertIs(arguments['captured_records'], records)
            self.assertIs(arguments['original_proof_records'], original)
            self.assertEqual(patches, [b'inert patch'])
            self.assertEqual(overlays, {'overlays/one.h': retained_bodies['overlays/one.h']})
            self.assertTrue(all(documents[role] == catalogue_raw[role] for role in roles))
            return checked, {**assembled_expected, 'wiring_only': True,
                             **{name: False for name in replay.handoff.FALSE_FACTS}}

        def capture_tree(label, bodies, files, directories):
            self.assertIs(captured['owner'].checked, checked)
            self.assertFalse(captured['owner'].closed)
            events.append(label + '.tree')
            tree = SimpleNamespace(as_dict=mock.Mock(return_value={
                'root': '', 'files': copy.deepcopy(files), 'directories': list(directories),
                'observed': {'files': {name: {'bytes': len(bodies[name])} for name in files},
                             'directories': {name: {} for name in ('', *directories)}}}),
                open_file=mock.Mock(side_effect=lambda name: io.BytesIO(bodies[name])), close=mock.Mock())
            trees[label] = tree
            return tree

        retained.capture_tree.side_effect = lambda root, **items: capture_tree('retained', retained_bodies, **items)
        assembled.capture_tree.side_effect = lambda root, **items: capture_tree('assembled', assembled_bodies, **items)
        def close(label):
            self.assertIs(captured['owner'].checked, checked)
            events.append(label + '.close')
        retained.close.side_effect = lambda: close('retained')
        assembled.close.side_effect = lambda: close('assembled')
        overlay = {'overlays/one.h': {key: binding('unused', retained_bodies['overlays/one.h'])[key]
                                    for key in ('sha256', 'bytes', 'mode')}}
        with mock.patch.object(replay, '_PosixSourceInputs', side_effect=[retained, assembled]) as owners, \
                mock.patch.object(replay, '_capture_source_records', side_effect=capture_records) as capture, \
                mock.patch.object(replay, '_replay_checked_records', side_effect=replay_checked) as core, \
                mock.patch.object(replay, 'catalogue_metadata', return_value={'overlays': overlay}) as catalogue, \
                mock.patch.object(replay.contract, 'CATALOGUE', catalogue_pins), \
                mock.patch.object(replay.handoff, '_retained_inventory', return_value=retained_expected), \
                mock.patch.object(replay.handoff, '_scan', side_effect=AssertionError('duplicate body scan')), \
                mock.patch.object(replay, '_CapturedSource', side_effect=AssertionError('old capture path')):
            result = replay._check_captured_selection(value, Path('/inert/retained'), Path('/inert/assembled'),
                recipe, sources, projection, assembled_expected, deadline=110.0)
        self.assertTrue(result['wiring_only'])
        self.assertTrue(all(result[name] is False for name in replay.handoff.FALSE_FACTS))
        self.assertEqual(owners.call_args_list,
                         [mock.call(Path('/inert/retained'), deadline=110.0),
                          mock.call(Path('/inert/assembled'), deadline=110.0)])
        capture.assert_called_once()
        core.assert_called_once()
        catalogue.assert_called_once_with(*(catalogue_raw[role] for role in roles))
        self.assertEqual([call.args[0] for call in retained.read.call_args_list],
                         ['catalogue/source_map.json', 'catalogue/provenance.json',
                          'catalogue/graph.json', 'overlays/one.h'])
        for actual, expected in ((retained, retained_expected), (assembled, assembled_expected)):
            actual.capture_tree.assert_called_once()
            arguments = actual.capture_tree.call_args
            self.assertEqual(arguments.args, ('',))
            self.assertEqual(set(arguments.kwargs['files']), set(expected['files']))
            self.assertEqual(arguments.kwargs['directories'], expected['directories'])
            self.assertTrue(all(item['sha256'] == expected['files'][name]
                                for name, item in arguments.kwargs['files'].items()))
            actual.close.assert_called_once_with()
        trees['retained'].open_file.assert_called_once_with('include/extra.h')
        trees['assembled'].open_file.assert_called_once_with('source/engine/fixture.cpp')
        archive.read.assert_not_called()
        archive.close.assert_not_called()
        self.assertEqual(events, ['retained.tree', 'assembled.tree', 'assembled.close', 'retained.close'])
        self.assertTrue(captured['owner'].closed)
        self.assertIsNone(captured['owner'].checked)


class NativeInputQualificationWiringOnlyTests(unittest.TestCase):
    """Explicit mocked A boundaries; no actual native admission or body reads."""
    def setUp(self):
        self.native_os = mock.Mock(wraps=os)
        self.native_os.name = 'nt'
        self.posix_os = mock.Mock(wraps=os)
        self.posix_os.name = 'posix'
        self.root = r'C:\inert\capsule'
        self.replay_reference = {'path': r'C:\inert\replay.json', 'sha256': digest(b'inert replay')}
        self.handoff_pin = digest(b'inert handoff')

    def api(self, owner=None):
        return SimpleNamespace(AnchoredInputs=SimpleNamespace(open_existing=mock.Mock(return_value=owner)),
            inspect_input_subject=mock.Mock(), admit_input_qualification=mock.Mock())

    def arguments(self):
        return ['check-handoff', '--root', self.root, '--handoff-sha256', self.handoff_pin,
                '--replay', self.replay_reference['path'], '--replay-sha256', self.replay_reference['sha256']]

    def test_native_absence_stops_before_reader_discovery_or_metadata_reads(self):
        with mock.patch.object(replay, 'os', self.native_os), \
                mock.patch.object(replay, '_native_input_reader', side_effect=AssertionError('reader discovery')), \
                mock.patch.object(replay, '_pinned_metadata', side_effect=AssertionError('native metadata read')), \
                self.assertRaises(replay.MissingInputs) as caught:
            replay.verify_for_handoff(self.root, self.handoff_pin, self.replay_reference)
        self.assertEqual(caught.exception.missing[0]['role'], 'windows-native-input-qualification')

    def test_posix_supplied_object_or_false_is_rejected_before_native_discovery(self):
        for qualification in (object(), False, {}):
            with self.subTest(qualification=qualification), \
                    mock.patch.object(replay, 'os', self.posix_os), \
                    mock.patch.object(replay, '_native_input_reader', side_effect=AssertionError('native discovery')), \
                    mock.patch.object(replay, '_pinned_metadata', side_effect=AssertionError('metadata read')), \
                    self.assertRaisesRegex(ValueError, 'POSIX'):
                replay.verify_for_handoff('/inert/capsule', self.handoff_pin, self.replay_reference,
                                         input_qualification=qualification)

    def test_qualification_is_keyword_only(self):
        with self.assertRaises(TypeError):
            replay.verify_for_handoff(self.root, self.handoff_pin, self.replay_reference, object())

    def test_native_forgeries_are_forwarded_unchanged_to_actual_lower_issuer(self):
        for qualification in (object(), False, {'qualified': True}):
            api = self.api()
            api.AnchoredInputs.open_existing.side_effect = ValueError('actual issuer rejected this handle')
            with self.subTest(qualification=qualification), mock.patch.object(replay, 'os', self.native_os), \
                    mock.patch.object(replay, '_native_input_reader', return_value=api), \
                    mock.patch.object(replay.time, 'monotonic', return_value=50), \
                    mock.patch.object(replay, 'require_original_proof_seam', side_effect=AssertionError('source gate before issuer')), \
                    mock.patch.object(replay, '_pinned_metadata', side_effect=AssertionError('native body read')), \
                    self.assertRaisesRegex(ValueError, 'actual issuer rejected'):
                replay.verify_for_handoff(self.root, self.handoff_pin, self.replay_reference,
                                         input_qualification=qualification)
            args, kwargs = api.AnchoredInputs.open_existing.call_args
            self.assertEqual(args, (self.root,))
            self.assertIs(kwargs['qualification'], qualification)
            self.assertEqual(kwargs['deadline'], 86450)
            self.assertEqual(kwargs['limits'], {'seconds': 86400, 'maximum_archive_bytes': replay.MAX_ARCHIVE,
                'maximum_expanded_bytes': replay.MAX_EXPANDED, 'maximum_members': replay.MAX_MEMBERS,
                'maximum_member_bytes': replay.MAX_MEMBER, 'maximum_patch_bytes': replay.MAX_DOCUMENT})

    def test_native_owner_closes_on_check_failure_missing_source_and_unreleased_tree(self):
        for failure in ('check', 'post-source', 'source', 'tree'):
            owner, external_owner, qualification = mock.Mock(), mock.Mock(), object()
            api = self.api(owner)
            api.AnchoredInputs.open_existing.side_effect = [owner, external_owner]
            if failure == 'check':
                owner.check.side_effect = ValueError('inert native owner changed')
            elif failure == 'post-source':
                owner.check.side_effect = [None, ValueError('inert native owner changed after source gate')]
            source_error = replay.MissingInputs([{'role': 'native-original-source-proof-data-seam',
                'path': 'inert shared source', 'reason': 'not released'}])
            tree_error = replay.MissingInputs([{'role': 'windows-native-input-tree-source',
                'path': 'inert tree reader', 'reason': 'not released'}])
            def checked_capture(owner, *arguments):
                return owner.hold(object(), {'wiring_only': True})
            with self.subTest(failure=failure), mock.patch.object(replay, 'os', self.native_os), \
                    mock.patch.object(replay, '_native_input_reader', return_value=api), \
                    mock.patch.object(replay, '_native_tree_reader',
                        side_effect=tree_error if failure == 'tree' else lambda actual: actual) as tree, \
                    mock.patch.object(replay, 'require_original_proof_seam',
                        side_effect=source_error if failure == 'source' else None) as source, \
                    mock.patch.object(replay, '_inspect_source_inputs', side_effect=checked_capture) as capture, \
                    mock.patch.object(replay, '_pinned_metadata', side_effect=AssertionError('native body read')):
                with self.assertRaises(ValueError if failure in ('check', 'post-source') else replay.MissingInputs) as caught:
                    replay.verify_for_handoff(self.root, self.handoff_pin, self.replay_reference,
                                             input_qualification=qualification)
            owner.close.assert_called_once()
            if failure == 'post-source':
                external_owner.close.assert_called_once_with()
            else:
                external_owner.close.assert_not_called()
            if failure in ('check', 'tree'):
                source.assert_not_called()
            else:
                source.assert_called_once()
            self.assertEqual(owner.check.call_count, 1 if failure in ('check', 'source', 'tree') else 2)
            if failure == 'check':
                tree.assert_not_called()
            else:
                tree.assert_called_once_with(api)
            if failure in ('check', 'source', 'tree'):
                capture.assert_not_called()
            if failure in ('source', 'tree'):
                self.assertEqual(caught.exception.missing[0]['role'],
                    'native-original-source-proof-data-seam' if failure == 'source' else 'windows-native-input-tree-source')

    def test_wiring_only_native_inspection_retains_external_replay_owner_under_same_lifetime(self):
        capsule, external, qualification, checked = mock.Mock(), mock.Mock(), object(), object()
        api = self.api()
        api.AnchoredInputs.open_existing.side_effect = [capsule, external]
        captured, events = {}, []
        capsule.close.side_effect = lambda: events.append('capsule.close')
        external.close.side_effect = lambda: events.append('external.close')
        def checked_capture(owner, capsule_inputs, replay_inputs, replay_name, handoff_pin, replay_reference):
            captured.update(owner=owner, capsule=capsule_inputs, replay=replay_inputs,
                            name=replay_name, pin=handoff_pin, reference=replay_reference)
            owner.set_source_limits({'seconds': 10, 'maximum_archive_bytes': 1024,
                'maximum_expanded_bytes': 1024, 'maximum_members': 10,
                'maximum_member_bytes': 1024, 'maximum_patch_bytes': 1024})
            return owner.hold(checked, {'wiring_only': True,
                **{name: False for name in replay.handoff.FALSE_FACTS}})
        with mock.patch.object(replay, 'os', self.native_os), \
                mock.patch.object(replay.time, 'monotonic', return_value=50.0), \
                mock.patch.object(replay, '_native_input_reader', return_value=api), \
                mock.patch.object(replay, '_native_tree_reader', side_effect=lambda actual: actual), \
                mock.patch.object(replay, 'require_original_proof_seam'), \
                mock.patch.object(replay, '_inspect_source_inputs', side_effect=checked_capture) as capture, \
                mock.patch.object(replay, '_pinned_metadata', side_effect=AssertionError('generic Windows source read')):
            inspection = replay.inspect_for_handoff(self.root, self.handoff_pin,
                self.replay_reference, input_qualification=qualification, deadline=75.0)
            try:
                owner = captured['owner']
                self.assertIs(owner.checked, checked)
                self.assertEqual(owner.resources, [capsule, external])
                self.assertIs(captured['capsule'].inputs, capsule)
                self.assertIs(captured['replay'].inputs, external)
                self.assertIs(captured['capsule'].owner, owner)
                self.assertIs(captured['replay'].owner, owner)
                self.assertEqual((captured['name'], captured['pin'], captured['reference']),
                                 ('replay.json', self.handoff_pin, self.replay_reference))
                opens = api.AnchoredInputs.open_existing.call_args_list
                self.assertEqual([call.args for call in opens], [(self.root,), (r'C:\inert',)])
                self.assertEqual(len(opens), 2)
                for call in opens:
                    self.assertIs(call.kwargs['qualification'], qualification)
                    self.assertEqual(call.kwargs['deadline'], 75.0)
                    self.assertEqual(call.kwargs['limits']['seconds'], 25.0)
                self.assertEqual((owner.initial_deadline, owner.work_deadline), (75.0, 60.0))
                capsule.close.assert_not_called()
                external.close.assert_not_called()
                inspection.check()
                self.assertTrue(all(inspection.as_dict()[name] is False for name in replay.handoff.FALSE_FACTS))
                capture.assert_called_once()
            finally:
                inspection.close()
        self.assertEqual(events, ['external.close', 'capsule.close'])
        capsule.close.assert_called_once_with()
        external.close.assert_called_once_with()

    def test_admission_forwards_actual_observed_subject_objects_by_identity(self):
        source_identity, runtime_identity, qualification = object(), object(), object()
        api = self.api()
        api.inspect_input_subject.return_value = {'source_identity': source_identity, 'runtime_identity': runtime_identity}
        api.admit_input_qualification.return_value = qualification
        reference = {'path': r'C:\inert\qualification.json', 'sha256': digest(b'inert qualification')}
        with mock.patch.object(replay, 'os', self.native_os), mock.patch.object(replay, '_native_input_reader', return_value=api):
            result = replay.admit_native_input_qualification(reference)
        self.assertIs(result, qualification)
        api.inspect_input_subject.assert_called_once_with()
        args, kwargs = api.admit_input_qualification.call_args
        self.assertEqual(args, (reference,))
        self.assertIs(kwargs['source_identity'], source_identity)
        self.assertIs(kwargs['runtime_identity'], runtime_identity)

    def test_observation_failure_prevents_qualification_admission(self):
        api = self.api()
        api.inspect_input_subject.side_effect = ValueError('inert subject observation changed')
        with mock.patch.object(replay, 'os', self.native_os), \
                mock.patch.object(replay, '_native_input_reader', return_value=api), \
                self.assertRaisesRegex(ValueError, 'subject observation changed'):
            replay.admit_native_input_qualification({'path': 'inert.json', 'sha256': digest(b'inert')})
        api.admit_input_qualification.assert_not_called()

    def test_unreleased_reader_gate_precedes_source_path_or_import_work(self):
        with mock.patch.object(replay, 'NATIVE_INPUT_READER_SHA256', None), \
                mock.patch.object(replay, '_native_reader_source', side_effect=AssertionError('source read')), \
                mock.patch.object(replay.importlib.util, 'spec_from_file_location', side_effect=AssertionError('source import')), \
                self.assertRaises(replay.MissingInputs) as caught:
            replay._native_input_reader()
        self.assertEqual(caught.exception.missing[0]['role'], 'windows-native-input-reader-source')

    def test_source_pin_mismatch_prevents_exact_source_import(self):
        path = ROOT / 'inert-appended-engine-windows-publication.py'
        with mock.patch.object(replay, 'NATIVE_INPUT_READER_SHA256', digest(b'expected inert source')), \
                mock.patch.object(replay, '_native_reader_source', return_value=(path, b'foreign inert source')), \
                mock.patch.object(replay.importlib.util, 'spec_from_file_location', side_effect=AssertionError('source import')), \
                self.assertRaisesRegex(ValueError, 'released identity'):
            replay._native_input_reader()

    def test_unknown_cached_api_is_not_admitted_by_a_matching_source_path_and_hash(self):
        path, raw = ROOT / 'inert-appended-engine-windows-publication.py', b'inert_marker = 1\n'
        cached = SimpleNamespace(__file__=str(path), AnchoredInputs=self.api().AnchoredInputs)
        with mock.patch.object(replay, 'NATIVE_INPUT_READER_SHA256', digest(raw)), \
                mock.patch.object(replay, '_NATIVE_INPUT_READER_CACHE', None), \
                mock.patch.object(replay, '_native_reader_source', return_value=(path, raw)), \
                mock.patch.dict(sys.modules, {'appended_engine_windows_publication': cached}), \
                self.assertRaises(replay.MissingInputs) as caught:
            replay._native_input_reader()
        self.assertEqual(caught.exception.missing[0]['role'], 'windows-native-input-reader-loader-coordination')
        cached.AnchoredInputs.open_existing.assert_not_called()

    def test_unknown_cached_none_entry_is_preserved_as_a_loader_coordination_gap(self):
        path, raw = ROOT / 'inert-appended-engine-windows-publication.py', b'inert_marker = 1\n'
        name = 'appended_engine_windows_publication'
        with mock.patch.object(replay, 'NATIVE_INPUT_READER_SHA256', digest(raw)), \
                mock.patch.object(replay, '_NATIVE_INPUT_READER_CACHE', None), \
                mock.patch.object(replay, '_native_reader_source', return_value=(path, raw)), \
                mock.patch.dict(sys.modules, {name: None}), self.assertRaises(replay.MissingInputs) as caught:
            try:
                replay._native_input_reader()
            finally:
                self.assertIn(name, sys.modules)
                self.assertIsNone(sys.modules[name])
        self.assertEqual(caught.exception.missing[0]['role'], 'windows-native-input-reader-loader-coordination')

    def test_pinned_inert_source_bootstrap_reuses_its_exact_module_and_detects_later_source_change(self):
        path, raw = ROOT / 'inert-appended-engine-windows-publication.py', b'inert_marker = "pinned fixture"\n'
        with mock.patch.object(replay, 'NATIVE_INPUT_READER_SHA256', digest(raw)), \
                mock.patch.object(replay, '_NATIVE_INPUT_READER_CACHE', None), mock.patch.dict(sys.modules), \
                mock.patch.object(replay, '_native_reader_source', return_value=(path, raw)) as source:
            sys.modules.pop('appended_engine_windows_publication', None)
            first = replay._native_input_reader()
            self.assertEqual(first.inert_marker, 'pinned fixture')
            self.assertIs(replay._native_input_reader(), first)
            source.return_value = path, raw + b'# changed after capture\n'
            with self.assertRaisesRegex(ValueError, 'released identity'):
                replay._native_input_reader()

    def test_inert_import_time_source_change_retains_failed_bootstrap_as_a_blocker(self):
        path, raw = ROOT / 'inert-appended-engine-windows-publication.py', b'inert_marker = 1\n'
        name = 'appended_engine_windows_publication'
        with mock.patch.object(replay, 'NATIVE_INPUT_READER_SHA256', digest(raw)), \
                mock.patch.object(replay, '_NATIVE_INPUT_READER_CACHE', None), mock.patch.dict(sys.modules), \
                mock.patch.object(replay, '_native_reader_source', side_effect=[(path, raw), (path, raw + b'# change\n')]) as source:
            sys.modules.pop(name, None)
            with self.assertRaisesRegex(ValueError, 'pinned source'):
                replay._native_input_reader()
            self.assertIn(name, sys.modules)
            blocker = sys.modules[name]
            self.assertEqual(blocker.inert_marker, 1)
            self.assertIsNone(replay._NATIVE_INPUT_READER_CACHE)
            source.side_effect = None
            source.return_value = path, raw
            with mock.patch.object(replay.importlib.util, 'module_from_spec',
                    side_effect=AssertionError('failed source bootstrap retried')) as load, \
                    self.assertRaises(replay.MissingInputs) as caught:
                replay._native_input_reader()
            self.assertEqual(caught.exception.missing[0]['role'], 'windows-native-input-reader-loader-coordination')
            self.assertIs(sys.modules[name], blocker)
            self.assertIsNone(replay._NATIVE_INPUT_READER_CACHE)
            self.assertEqual(blocker.inert_marker, 1)
            load.assert_not_called()

    def test_cli_requires_both_qualification_arguments_before_admission(self):
        for tail in (['--input-qualification', 'inert.json'], ['--input-qualification-sha256', digest(b'inert')]):
            with self.subTest(tail=tail), redirect_stderr(io.StringIO()), \
                    mock.patch.object(replay, 'admit_native_input_qualification', side_effect=AssertionError('admission')), \
                    mock.patch.object(replay, 'verify_for_handoff', side_effect=AssertionError('verification')), \
                    self.assertRaises(SystemExit) as caught:
                replay.cli(self.arguments() + tail)
            self.assertEqual(caught.exception.code, 2)

    def test_cli_pair_is_rejected_on_posix_before_native_admission(self):
        with mock.patch.object(replay, 'os', self.posix_os), \
                mock.patch.object(replay, 'admit_native_input_qualification', side_effect=AssertionError('native admission')), \
                redirect_stderr(io.StringIO()):
            code = replay.cli(self.arguments() + ['--input-qualification', 'inert.json',
                             '--input-qualification-sha256', digest(b'inert')])
        self.assertEqual(code, 1)

    def test_cli_empty_supplied_qualification_pin_is_invalid_without_native_discovery(self):
        with mock.patch.object(replay, 'os', self.native_os), \
                mock.patch.object(replay, '_native_input_reader', side_effect=AssertionError('native discovery')), \
                redirect_stderr(io.StringIO()):
            code = replay.cli(self.arguments() + ['--input-qualification', 'inert.json',
                             '--input-qualification-sha256', ''])
        self.assertEqual(code, 1)

    def test_cli_pair_forwards_the_exact_issued_token_on_native_windows(self):
        qualification = object()
        reference = {'path': 'inert-qualification.json', 'sha256': digest(b'inert qualification')}
        with mock.patch.object(replay, 'os', self.native_os), redirect_stdout(io.StringIO()), \
                mock.patch.object(replay, 'admit_native_input_qualification', return_value=qualification) as admit, \
                mock.patch.object(replay, 'verify_for_handoff', return_value={'wiring_only': True}) as verify:
            code = replay.cli(self.arguments() + ['--input-qualification', reference['path'],
                             '--input-qualification-sha256', reference['sha256']])
        self.assertEqual(code, 0)
        admit.assert_called_once_with(reference)
        self.assertIs(verify.call_args.kwargs['input_qualification'], qualification)

    def test_cli_without_qualification_preserves_three_positional_argument_call(self):
        with redirect_stdout(io.StringIO()), \
                mock.patch.object(replay, 'admit_native_input_qualification', side_effect=AssertionError('admission')), \
                mock.patch.object(replay, 'verify_for_handoff', return_value={'wiring_only': True}) as verify:
            self.assertEqual(replay.cli(self.arguments()), 0)
        self.assertEqual(verify.call_args.args, (Path(self.root), self.handoff_pin, self.replay_reference))
        self.assertEqual(verify.call_args.kwargs, {})

    def test_posix_check_parser_does_not_accept_native_qualification_arguments(self):
        with redirect_stderr(io.StringIO()), \
                mock.patch.object(replay, 'check_selection', side_effect=AssertionError('selection read')), \
                self.assertRaises(SystemExit) as caught:
            replay.cli(['check', '--selection', '/inert/selection.json', '--selection-sha256', digest(b'inert'),
                        '--input-qualification', 'inert.json', '--input-qualification-sha256', digest(b'inert')])
        self.assertEqual(caught.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
