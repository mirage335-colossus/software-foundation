"""Offline retained-engine integrity fixtures, never engine qualification.

The supplier archives, JavaScript and minimal valid Wasm below are test markers,
not engines. No input is compiled, linked, imported or executed by these tests.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
from dependency_archive import digest, encoded


def checksum(content):
    return hashlib.sha256(content).hexdigest()


def write(root, name, content, mode=0o644):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    for parent in path.parents:
        if parent == root:
            break
        parent.chmod(0o755)
    path.write_bytes(content)
    path.chmod(mode)
    return path


def document(root, name, value):
    return write(root, name, encoded(value))


class EngineIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='foundation-engine-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.fixture = self.make_fixture('original')
        self.binary = self.fixture['binary']
        self.sources = self.fixture['sources']
        self.recipe = self.fixture['recipe']
        self.recipe_id = self.fixture['recipe_id']
        self.repack_number = 0

    def make_fixture(self, name, variant=b'original'):
        binary, sources = self.base / (name + '-binary'), self.base / (name + '-sources')
        binary.mkdir(mode=0o755)
        sources.mkdir(mode=0o755)
        inputs = {}

        def retain(path, content, role, mode=0o644):
            write(sources, path, content, mode)
            inputs[path] = {'sha256': checksum(content), 'role': role, 'mode': mode}

        retain('archives/wrapper.tar.xz', b'fixture wrapper archive, not an engine\n' + variant, 'source')
        retain('archives/engine.tar.xz', b'fixture engine archive, not an engine\n', 'source')
        retain('patches/0001-fixture.patch', b'fixture patch; do not apply\n', 'patch')
        retain('licenses/NOTICE.txt', b'Unit-test fixture notice; no engine distribution.\n', 'license')
        header = b'/* Unit-test provider interface, not an engine API. */\n'
        retain('include/fixture_provider.h', header, 'interface')
        retain('bootstrap/never-run.py',
               b'raise RuntimeError("retained fixture inputs must never execute")\n', 'bootstrap', 0o755)
        retain('tools/never-run.py', b'raise RuntimeError("fixture tool must never execute")\n', 'tool', 0o755)
        retain('config/profile.json', b'{"fixture": true}\n', 'config')
        retain('data/fixture.dat', b'fixture data\n', 'data')
        # Retain the actual producing helper bytes, rather than stale copied
        # fixture implementations or claimed identities unrelated to the inputs.
        for helper in manifest.HELPERS:
            retain(helper, (ROOT / helper).read_bytes(), 'helper')
        (sources / 'empty-source-directory').mkdir(mode=0o755)
        target = {'system': 'Emscripten', 'processor': 'wasm32',
                  'triple': 'wasm32-unknown-emscripten', 'pointer_bits': 32}
        toolchain = {'cxx_standard': 23, 'identity_sha256': checksum(b'fixture toolchain'),
                     'runtime_policy': 'paired-emscripten',
                     'paired_sdk_sha256': checksum(b'fixture paired SDK'),
                     'target_baseline': 'fixture-only; no runtime qualified'}
        provider = {'format': 'browser-module', 'binding': 'copied-owner-bridge',
                    'abi_major': 1, 'abi_minor': 0, 'header': 'include/fixture_provider.h',
                    'header_sha256': checksum(header)}
        recipe = {'schema_version': 1, 'kind': 'foundation-appended-engine-recipe',
                  'producer_version': 1, 'target': target, 'toolchain': toolchain,
                  'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'single'},
                  'provider': provider,
                  'suppliers': {
                      'wrapper': {'repository': 'https://example.invalid/fixture-wrapper',
                                  'commit': '1' * 40, 'archive': 'archives/wrapper.tar.xz'},
                      'engine': {'repository': 'https://example.invalid/fixture-engine',
                                 'commit': '2' * 40, 'archive': 'archives/engine.tar.xz'}},
                  'inputs': inputs,
                  'patches': [{'path': 'patches/0001-fixture.patch', 'tree': 'wrapper',
                               'preimages': {'src/fixture.cpp': checksum(b'fixture before\n')},
                               'postimages': {'src/fixture.cpp': checksum(b'fixture after\n')}}],
                  'licenses': ['licenses/NOTICE.txt']}
        document(sources, 'recipe.json', recipe)
        recipe_id = digest(sources / 'recipe.json')
        source_manifest = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
                           'producer_version': 1, 'recipe_id': recipe_id,
                           **manifest.tree_inventory(sources, 'sources.json')}
        document(sources, 'sources.json', source_manifest)
        write(binary, 'include/fixture_provider.h', header)
        write(binary, 'licenses/NOTICE.txt', (sources / 'licenses/NOTICE.txt').read_bytes())
        write(binary, 'provider/fixture.mjs',
              b'throw new Error("integrity fixture, never import or execute");\n')
        write(binary, 'provider/fixture.wasm', b'\0asm\x01\0\0\0')
        document(binary, 'receipts/link.json', {'fixture': True, 'qualification': 'none'})
        (binary / 'empty-binary-directory').mkdir(mode=0o755)
        binary_manifest = {'schema_version': 1, 'kind': 'foundation-appended-engine',
                           'producer_version': 1, 'recipe_id': recipe_id,
                           'sources_sha256': digest(sources / 'sources.json'),
                           'target': copy.deepcopy(target), 'toolchain': copy.deepcopy(toolchain),
                           'options': copy.deepcopy(recipe['options']),
                           'provider': {**copy.deepcopy(provider), 'entry': 'provider/fixture.mjs',
                                        'assets': ['provider/fixture.mjs', 'provider/fixture.wasm']},
                           'licenses': list(recipe['licenses']),
                           'build': {'origin': 'unit-test-fixture-no-engine', 'link_receipt': 'receipts/link.json'},
                           **manifest.tree_inventory(binary, 'engine-sdk.json')}
        document(binary, 'engine-sdk.json', binary_manifest)
        return {'binary': binary, 'sources': sources, 'recipe': recipe, 'recipe_id': recipe_id}

    def export(self, name='group'):
        group = self.base / name
        result = sdk.export_group(self.binary, self.sources, group)
        self.assertEqual(result['scope'], 'retained-byte-integrity-only')
        return group

    def load(self, root, name):
        return json.loads((root / name).read_bytes())

    def refresh_binary(self):
        value = self.load(self.binary, 'engine-sdk.json')
        value.update(manifest.tree_inventory(self.binary, 'engine-sdk.json'))
        document(self.binary, 'engine-sdk.json', value)
        return value

    def add_windows_mode_fixtures(self):
        """Suffixes deliberately disagree with retained logical permissions."""
        for name, content, role, mode in (
                ('bootstrap/executable.data', b'inert executable-mode fixture\n', 'tool', 0o755),
                ('data/not-a-tool.exe', b'inert data-mode fixture\n', 'data', 0o644)):
            write(self.sources, name, content, mode)
            self.recipe['inputs'][name] = {'sha256': checksum(content), 'role': role, 'mode': mode}
        document(self.sources, 'recipe.json', self.recipe)
        self.recipe_id = digest(self.sources / 'recipe.json')
        source = self.load(self.sources, 'sources.json')
        source.update(recipe_id=self.recipe_id, **manifest.tree_inventory(self.sources, 'sources.json'))
        document(self.sources, 'sources.json', source)
        write(self.binary, 'provider/executable.data', b'inert executable-mode binary fixture\n', 0o755)
        write(self.binary, 'provider/not-a-tool.exe', b'inert data-mode binary fixture\n', 0o644)
        binary = self.refresh_binary()
        binary.update(recipe_id=self.recipe_id, sources_sha256=digest(self.sources / 'sources.json'))
        document(self.binary, 'engine-sdk.json', binary)
        return binary, source

    @contextlib.contextmanager
    def simulated_windows_metadata(self, attributes=None, state_overrides=None):
        """Linux-only mocks; this does not exercise Windows filesystem APIs."""
        attributes = {} if attributes is None else attributes
        state_overrides = {} if state_overrides is None else state_overrides
        lstat = Path.lstat
        rename = os.rename

        def windows_lstat(path, *args, **kwargs):
            state = lstat(path, *args, **kwargs)
            values = {name: getattr(state, name) for name in dir(state) if name.startswith('st_')}
            values['st_file_attributes'] = attributes.get(path, 0)
            # Model suffix-derived Windows stat permissions, not chmod. Neither
            # this inference nor physical POSIX modes may supply archive modes.
            permissions = 0o777 if stat.S_ISDIR(state.st_mode) else (0o755 if path.suffix == '.exe' else 0o644)
            values['st_mode'] = stat.S_IFMT(state.st_mode) | permissions
            values.update(state_overrides.get(path, {}))
            return SimpleNamespace(**values)

        def windows_rename(source, destination, *args, **kwargs):
            destination = Path(destination)
            if destination.exists() or destination.is_symlink():
                raise FileExistsError('simulated Windows destination collision')
            return rename(source, destination, *args, **kwargs)

        with mock.patch.object(manifest, 'WINDOWS', True), \
                mock.patch.object(Path, 'lstat', windows_lstat), \
                mock.patch.object(os, 'rename', windows_rename):
            yield

    def rechecksum(self, group):
        names = sdk.group_names(self.recipe_id)
        write(group, names[2], ''.join(digest(group / name) + '  ' + name + '\n'
                                      for name in names[:2]).encode('ascii'))

    def rewrite_archive(self, group, kind, change):
        name = sdk.group_names(self.recipe_id)[0 if kind == 'binary' else 1]
        path = group / name
        entries = {}
        with tarfile.open(path, 'r:*') as archive:
            for member in archive:
                content = archive.extractfile(member).read() if member.isfile() else None
                entries[member.name.rstrip('/')] = (copy.copy(member), content)
        change(entries)
        self.repack_number += 1
        temporary = self.base / ('repacked-' + str(self.repack_number) + '.tar.gz')
        with tarfile.open(temporary, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
            for member, content in entries.values():
                archive.addfile(member, None if content is None else io.BytesIO(content))
        temporary.chmod(0o644)
        temporary.replace(path)
        self.rechecksum(group)

    @staticmethod
    def replace_entry(entries, name, content):
        member, _ = entries[name]
        member.size = len(content)
        entries[name] = (member, content)

    def reject_group_without_output(self, group):
        with self.assertRaises(ValueError):
            sdk.verify_group(group, self.recipe_id)
        for sources in (False, True):
            output = self.base / ('rejected-sources' if sources else 'rejected-binary')
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                sdk.restore(group, self.recipe_id, output, sources=sources)
            self.assertFalse(output.exists())
        self.assertFalse(list(self.base.glob('.engine-restore-*')))

    def test_exact_recipe_and_source_helpers_bind_every_input(self):
        self.assertEqual(manifest.recipe_identity(self.sources), self.recipe_id)
        recipe, identity, inventory = manifest.verify_inputs(self.sources)
        self.assertEqual(identity, self.recipe_id)
        self.assertEqual(recipe, self.recipe)
        self.assertEqual(inventory['files']['recipe.json'], self.recipe_id)
        for helper in manifest.HELPERS:
            self.assertEqual(recipe['inputs'][helper]['role'], 'helper')
            self.assertEqual(inventory['files'][helper], digest(ROOT / helper))
        sources, source_hash, retained_recipe = manifest.verify_sources(self.sources)
        binary, _ = manifest.verify_engine(self.binary)
        manifest.verify_binding(binary, sources, source_hash, retained_recipe)

    def test_recipe_identity_is_exact_json_bytes(self):
        path = self.sources / 'recipe.json'
        path.write_bytes(path.read_bytes() + b'\n')
        self.assertNotEqual(manifest.recipe_identity(self.sources), self.recipe_id)
        with self.assertRaises(ValueError):
            manifest.verify_sources(self.sources)

    def test_group_export_and_restore_preserve_complete_bytes_modes_and_empty_directories(self):
        group = self.export()
        result = sdk.verify_group(group, self.recipe_id)
        self.assertEqual(result['recipe_id'], self.recipe_id)
        self.assertEqual(set(result['files']), set(sdk.group_names(self.recipe_id)))
        for sources, original, manifest_name in ((False, self.binary, 'engine-sdk.json'),
                                                   (True, self.sources, 'sources.json')):
            output = self.base / ('restored-sources' if sources else 'restored-binary')
            with self.subTest(sources=sources):
                previous_umask = os.umask(0o077)
                try:
                    restored = sdk.restore(group, self.recipe_id, output, sources=sources)
                finally:
                    os.umask(previous_umask)
                self.assertEqual(restored['scope'], 'retained-byte-integrity-only')
                self.assertEqual(restored['manifest_sha256'], digest(original / manifest_name))
                self.assertEqual(manifest.tree_inventory(output, manifest_name),
                                 manifest.tree_inventory(original, manifest_name))
                self.assertEqual((output / manifest_name).read_bytes(), (original / manifest_name).read_bytes())

    def test_export_is_deterministic_for_identical_inputs(self):
        first, second = self.export('first-group'), self.export('second-group')
        for name in sdk.group_names(self.recipe_id):
            with self.subTest(name=name):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_binary_recipe_named_asset_is_opaque_payload(self):
        write(self.binary, 'recipe.json', b'opaque binary fixture asset, not JSON\n')
        self.refresh_binary()
        manifest.verify_engine(self.binary)
        group = self.export()
        output = self.base / 'opaque-asset-restored'
        sdk.restore(group, self.recipe_id, output)
        self.assertEqual((output / 'recipe.json').read_bytes(), b'opaque binary fixture asset, not JSON\n')

    def test_asset_corruption_is_rejected_after_recomputing_group_checksums(self):
        group = self.export()
        self.rewrite_archive(group, 'binary', lambda entries:
                             self.replace_entry(entries, 'provider/fixture.wasm', b'\0asm\x01\0\0\0changed'))
        self.reject_group_without_output(group)

    def test_patch_corruption_is_rejected_after_recomputing_source_inventory_and_group_checksums(self):
        group = self.export()

        def corrupt(entries):
            content = b'changed fixture patch\n'
            self.replace_entry(entries, 'patches/0001-fixture.patch', content)
            source = json.loads(entries['sources.json'][1])
            source['files']['patches/0001-fixture.patch'] = checksum(content)
            self.replace_entry(entries, 'sources.json', encoded(source))

        self.rewrite_archive(group, 'sources', corrupt)
        self.reject_group_without_output(group)

    def test_binary_notice_binding_survives_recomputed_binary_inventory_and_checksums(self):
        group = self.export()

        def corrupt(entries):
            content = b'different notice\n'
            self.replace_entry(entries, 'licenses/NOTICE.txt', content)
            binary = json.loads(entries['engine-sdk.json'][1])
            binary['files']['licenses/NOTICE.txt'] = checksum(content)
            self.replace_entry(entries, 'engine-sdk.json', encoded(binary))

        self.rewrite_archive(group, 'binary', corrupt)
        self.reject_group_without_output(group)

    def test_binary_header_binding_survives_recomputed_provider_hash_inventory_and_checksums(self):
        group = self.export()

        def corrupt(entries):
            content = b'/* replaced interface */\n'
            self.replace_entry(entries, 'include/fixture_provider.h', content)
            binary = json.loads(entries['engine-sdk.json'][1])
            binary['files']['include/fixture_provider.h'] = checksum(content)
            binary['provider']['header_sha256'] = checksum(content)
            self.replace_entry(entries, 'engine-sdk.json', encoded(binary))

        self.rewrite_archive(group, 'binary', corrupt)
        self.reject_group_without_output(group)

    def test_swapped_self_consistent_source_archive_is_rejected(self):
        group = self.export()
        alternate = self.make_fixture('alternate', b'different retained source')
        source_name = sdk.group_names(self.recipe_id)[1]
        replacement = self.base / 'alternate-sources.tar.gz'
        sdk.archive_tree(alternate['sources'], replacement, 'sources.json')
        replacement.replace(group / source_name)
        self.rechecksum(group)
        self.reject_group_without_output(group)

    def test_source_manifest_hash_binds_empty_directories(self):
        (self.sources / 'another-empty-directory').mkdir(mode=0o755)
        source = self.load(self.sources, 'sources.json')
        source.update(manifest.tree_inventory(self.sources, 'sources.json'))
        document(self.sources, 'sources.json', source)
        manifest.verify_sources(self.sources)
        output = self.base / 'rejected-export'
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            sdk.export_group(self.binary, self.sources, output)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.base.glob('.engine-export-*')))

    def test_unlisted_empty_directory_is_rejected(self):
        for root, verify in ((self.binary, manifest.verify_engine), (self.sources, manifest.verify_sources)):
            with self.subTest(root=root.name):
                extra = root / 'unlisted-empty-directory'
                extra.mkdir(mode=0o755)
                with self.assertRaises(ValueError):
                    verify(root)
                extra.rmdir()

    def test_changed_file_or_directory_mode_is_rejected(self):
        for root, name, mode, verify in (
                (self.binary, 'provider/fixture.mjs', 0o755, manifest.verify_engine),
                (self.sources, 'bootstrap/never-run.py', 0o644, manifest.verify_sources),
                (self.binary, 'empty-binary-directory', 0o700, manifest.verify_engine),
                (self.sources, 'empty-source-directory', 0o700, manifest.verify_sources)):
            path = root / name
            previous = stat.S_IMODE(path.stat().st_mode)
            with self.subTest(root=root.name, name=name):
                path.chmod(mode)
                try:
                    with self.assertRaises(ValueError):
                        verify(root)
                finally:
                    path.chmod(previous)

    def test_archive_extra_empty_directory_and_mode_changes_are_rejected(self):
        group = self.export()
        original = (group / sdk.group_names(self.recipe_id)[0]).read_bytes()
        for alteration in ('extra-directory', 'changed-mode'):
            with self.subTest(alteration=alteration):
                write(group, sdk.group_names(self.recipe_id)[0], original)

                def corrupt(entries):
                    if alteration == 'extra-directory':
                        member = tarfile.TarInfo('unlisted-empty-directory')
                        member.type, member.mode = tarfile.DIRTYPE, 0o755
                        entries[member.name] = (member, None)
                    else:
                        entries['provider/fixture.mjs'][0].mode = 0o755

                self.rewrite_archive(group, 'binary', corrupt)
                self.reject_group_without_output(group)

    def test_unsafe_special_or_privileged_archive_members_are_rejected(self):
        group = self.export()
        original = (group / sdk.group_names(self.recipe_id)[0]).read_bytes()
        cases = ('traversal', 'symlink', 'hardlink', 'fifo', 'setuid', 'case-alias')
        for alteration in cases:
            with self.subTest(alteration=alteration):
                write(group, sdk.group_names(self.recipe_id)[0], original)

                def corrupt(entries):
                    member = tarfile.TarInfo('../outside-fixture' if alteration == 'traversal' else 'extra-fixture')
                    member.mode = 0o644
                    content = b''
                    if alteration in ('symlink', 'hardlink', 'fifo'):
                        member.type = {'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE,
                                       'fifo': tarfile.FIFOTYPE}[alteration]
                        member.linkname = 'provider/fixture.mjs'
                        content = None
                    elif alteration == 'setuid':
                        member.mode = 0o4644
                    elif alteration == 'case-alias':
                        member.name = 'Provider/fixture.mjs'
                    entries[member.name] = (member, content)

                self.rewrite_archive(group, 'binary', corrupt)
                self.reject_group_without_output(group)
                self.assertFalse((self.base / 'outside-fixture').exists())

    def test_source_recipe_requires_exact_helper_supplier_patch_interface_and_license_roles(self):
        changes = [
            ('missing helper', lambda value: value['inputs'].pop(manifest.HELPERS[0])),
            ('wrong helper role', lambda value: value['inputs'][manifest.HELPERS[0]].update(role='tool')),
            ('supplier role', lambda value: value['inputs']['archives/wrapper.tar.xz'].update(role='data')),
            ('interface role', lambda value: value['inputs']['include/fixture_provider.h'].update(role='source')),
            ('header identity', lambda value: value['provider'].update(header_sha256='0' * 64)),
            ('license role', lambda value: value['inputs']['licenses/NOTICE.txt'].update(role='data')),
            ('omitted notice', lambda value: value['inputs'].update({
                'licenses/OMITTED.txt': {'sha256': '3' * 64, 'role': 'license', 'mode': 0o644}})),
            ('patch role', lambda value: value['inputs']['patches/0001-fixture.patch'].update(role='data')),
            ('unordered patch', lambda value: value.update(patches=[])),
            ('duplicate patch', lambda value: value['patches'].append(copy.deepcopy(value['patches'][0]))),
            ('missing image', lambda value: value['patches'][0].update(postimages={})),
            ('absent images', lambda value: value['patches'][0].update(
                preimages={'src/fixture.cpp': None}, postimages={'src/fixture.cpp': None})),
            ('unsafe patch image', lambda value: value['patches'][0].update(
                preimages={'../outside.cpp': '3' * 64}, postimages={'../outside.cpp': '4' * 64})),
        ]
        for name, change in changes:
            value = copy.deepcopy(self.recipe)
            change(value)
            with self.subTest(name=name), self.assertRaises(ValueError):
                manifest.recipe_contract(value)

    def test_changed_retained_helper_bytes_fail_exact_recipe_input_validation(self):
        helper = self.sources / manifest.HELPERS[0]
        helper.write_bytes(helper.read_bytes() + b'\n# changed helper fixture\n')
        with self.assertRaises(ValueError):
            manifest.verify_inputs(self.sources)
        with self.assertRaises(ValueError):
            manifest.verify_sources(self.sources)

    def test_schemas_reject_boolean_numbers_unknown_fields_and_wrong_options(self):
        checks = (
            (manifest.recipe_contract, self.recipe),
            (manifest.binary_contract, self.load(self.binary, 'engine-sdk.json')),
        )
        changes = [
            ('boolean schema', lambda value: value.update(schema_version=True)),
            ('boolean producer', lambda value: value.update(producer_version=True)),
            ('unknown top field', lambda value: value.update(unrecognized=True)),
            ('unknown target field', lambda value: value['target'].update(unrecognized=True)),
            ('boolean pointer width', lambda value: value['target'].update(pointer_bits=True)),
            ('boolean C++ standard', lambda value: value['toolchain'].update(cxx_standard=True)),
            ('boolean ABI major', lambda value: value['provider'].update(abi_major=True)),
            ('boolean ABI minor', lambda value: value['provider'].update(abi_minor=False)),
            ('integer script flag', lambda value: value['options'].update(script_enabled=1)),
            ('unknown provider field', lambda value: value['provider'].update(unrecognized=True)),
            ('wrong rendering', lambda value: value['options'].update(rendering='gpu')),
            ('wrong thread model', lambda value: value['options'].update(thread_model='native')),
        ]
        for check, original in checks:
            for name, change in changes:
                value = copy.deepcopy(original)
                change(value)
                with self.subTest(contract=check.__name__, name=name), self.assertRaises(ValueError):
                    check(value)
        source = self.load(self.sources, 'sources.json')
        for field, value in (('schema_version', True), ('producer_version', True), ('unknown', True)):
            invalid = copy.deepcopy(source)
            invalid[field] = value
            with self.subTest(source_field=field), self.assertRaises(ValueError):
                manifest.source_contract(invalid, self.recipe, self.recipe_id)

    def test_json_rejects_duplicate_fields_and_nonfinite_constants(self):
        for content in (b'{"schema_version":1,"schema_version":1}', b'{"value":NaN}', b'{"value":Infinity}'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                manifest.json_bytes(content)

    def test_windows_simulated_file_mode_authority_ignores_suffix_and_physical_permissions(self):
        binary, source = self.add_windows_mode_fixtures()
        expected_binary = manifest.tree_inventory(self.binary, 'engine-sdk.json')
        expected_source = manifest.tree_inventory(self.sources, 'sources.json')
        with self.simulated_windows_metadata():
            self.assertEqual(manifest.tree_inventory(self.binary, 'engine-sdk.json', logical_modes=binary['modes']),
                             expected_binary)
            self.assertEqual(manifest.tree_inventory(self.sources, 'sources.json', logical_modes=source['modes']),
                             expected_source)
            manifest.verify_engine(self.binary)
            manifest.verify_inputs(self.sources)
            manifest.verify_sources(self.sources)
            self.assertEqual(binary['modes']['provider/executable.data'], 0o755)
            self.assertEqual(binary['modes']['provider/not-a-tool.exe'], 0o644)
            self.assertEqual(source['modes']['bootstrap/executable.data'], 0o755)
            self.assertEqual(source['modes']['data/not-a-tool.exe'], 0o644)

    def test_windows_simulated_export_and_private_restore_preserve_logical_mode_closure(self):
        binary, source = self.add_windows_mode_fixtures()
        expected = {False: manifest.tree_inventory(self.binary, 'engine-sdk.json'),
                    True: manifest.tree_inventory(self.sources, 'sources.json')}
        with self.simulated_windows_metadata():
            group = self.export('simulated-windows-group')
            sdk.verify_group(group, self.recipe_id)
            for sources, metadata, manifest_name in ((False, binary, 'engine-sdk.json'),
                                                      (True, source, 'sources.json')):
                with self.subTest(sources=sources):
                    output = self.base / ('simulated-windows-source' if sources else 'simulated-windows-binary')
                    result = sdk.restore(group, self.recipe_id, output, sources=sources)
                    self.assertEqual(result['scope'], 'retained-byte-integrity-only')
                    self.assertEqual(manifest.tree_inventory(output, manifest_name, logical_modes=metadata['modes']),
                                     expected[sources])
                    self.assertEqual((output / manifest_name).read_bytes(), encoded(metadata))

    def test_windows_simulated_inventory_requires_explicit_file_mode_authority(self):
        with self.simulated_windows_metadata(), \
                mock.patch.object(manifest, 'digest', side_effect=AssertionError('cannot read without authority')), \
                self.assertRaises(ValueError):
            manifest.tree_inventory(self.binary, 'engine-sdk.json')
        binary = self.load(self.binary, 'engine-sdk.json')
        write(self.binary, 'provider/unlisted.exe', b'undeclared fixture\n', 0o755)
        with self.simulated_windows_metadata(), self.assertRaises(ValueError):
            manifest.tree_inventory(self.binary, 'engine-sdk.json', logical_modes=binary['modes'])

    def test_windows_simulated_missing_file_attributes_fail_closed_before_read(self):
        # Linux lstat deliberately lacks Windows attributes in this probe.
        with mock.patch.object(manifest, 'WINDOWS', True), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('must reject metadata first')), \
                self.assertRaises(ValueError):
            manifest.read_document(self.binary, 'engine-sdk.json')
        leaf = self.binary / 'engine-sdk.json'
        with self.simulated_windows_metadata(state_overrides={leaf: {'st_file_attributes': None}}), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('must reject leaf metadata first')), \
                self.assertRaises(ValueError):
            manifest.read_document(self.binary, 'engine-sdk.json')

    def test_windows_simulated_reparse_ancestor_is_rejected_before_read_or_walk(self):
        with self.simulated_windows_metadata({self.base: 0x400}), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('must reject ancestor first')), \
                mock.patch.object(Path, 'iterdir', side_effect=AssertionError('must reject ancestor first')), \
                mock.patch.object(Path, 'resolve', side_effect=AssertionError('must reject ancestor before resolution')), \
                self.assertRaises(ValueError):
            manifest.verify_engine(self.binary)

    def test_windows_simulated_reparse_descendant_is_rejected_before_recursing(self):
        binary = self.load(self.binary, 'engine-sdk.json')
        linked = self.binary / 'provider'
        iterdir, scandir = Path.iterdir, os.scandir

        def checked_iterdir(path):
            if path == linked:
                raise AssertionError('must reject reparse directory before iterating it')
            return iterdir(path)

        def checked_scandir(path):
            if not isinstance(path, int) and Path(path) == linked:
                raise AssertionError('must reject reparse directory before scanning it')
            return scandir(path)

        with self.simulated_windows_metadata({linked: 0x400}), \
                mock.patch.object(Path, 'iterdir', checked_iterdir), \
                mock.patch.object(os, 'scandir', checked_scandir), self.assertRaises(ValueError):
            manifest.tree_inventory(self.binary, 'engine-sdk.json', logical_modes=binary['modes'])

    def test_windows_simulated_reparse_manifest_file_is_rejected_before_read(self):
        path = self.binary / 'engine-sdk.json'
        with self.simulated_windows_metadata({path: 0x400}), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('must reject reparse file first')), \
                self.assertRaises(ValueError):
            manifest.read_document(self.binary, 'engine-sdk.json')

    def test_windows_simulated_rename_failure_preserves_stage_without_fallback(self):
        staged, output = self.base / 'rename-stage', self.base / 'rename-output'
        staged.mkdir(mode=0o755)
        write(staged, 'sentinel.txt', b'owned stage fixture\n')
        with self.simulated_windows_metadata(), \
                mock.patch.object(os, 'rename', side_effect=PermissionError('simulated Windows rename error')) as rename, \
                mock.patch.object(sdk.ctypes, 'CDLL', side_effect=AssertionError('must not fall back')), \
                self.assertRaises(PermissionError):
            sdk.publish_fresh(staged, output)
        self.assertEqual(rename.call_count, 1)
        self.assertEqual((staged / 'sentinel.txt').read_bytes(), b'owned stage fixture\n')
        self.assertFalse(output.exists())

    def test_windows_simulated_rename_collision_preserves_destination(self):
        for empty in (False, True):
            with self.subTest(empty_destination=empty):
                staged, output = self.base / ('collision-stage-' + str(empty)), self.base / ('collision-output-' + str(empty))
                staged.mkdir(mode=0o755)
                write(staged, 'staged.txt', b'owned stage fixture\n')
                collided_identity = []

                def collision(source, destination):
                    destination = Path(destination)
                    destination.mkdir(mode=0o755)
                    collided_identity.append((destination.lstat().st_dev, destination.lstat().st_ino))
                    if not empty:
                        write(destination, 'owner.txt', b'competing writer fixture\n')
                    raise FileExistsError('simulated Windows destination collision')

                with self.simulated_windows_metadata(), mock.patch.object(os, 'rename', side_effect=collision) as rename, \
                        mock.patch.object(sdk.ctypes, 'CDLL', side_effect=AssertionError('must not fall back')), \
                        self.assertRaises(FileExistsError):
                    sdk.publish_fresh(staged, output)
                self.assertEqual(rename.call_count, 1)
                self.assertEqual((output.lstat().st_dev, output.lstat().st_ino), collided_identity[0])
                if empty:
                    self.assertEqual(list(output.iterdir()), [])
                else:
                    self.assertEqual((output / 'owner.txt').read_bytes(), b'competing writer fixture\n')
                self.assertEqual((staged / 'staged.txt').read_bytes(), b'owned stage fixture\n')

    def test_windows_simulated_publication_requires_direct_sibling_stage(self):
        staged, output = self.base / 'nested' / 'stage', self.base / 'nested-stage-output'
        staged.mkdir(parents=True, mode=0o755)
        write(staged, 'sentinel.txt', b'owned stage fixture\n')
        with self.simulated_windows_metadata(), mock.patch.object(os, 'rename') as rename, \
                self.assertRaisesRegex(ValueError, 'staging parent'):
            sdk.publish_fresh(staged, output)
        rename.assert_not_called()
        self.assertEqual((staged / 'sentinel.txt').read_bytes(), b'owned stage fixture\n')
        self.assertFalse(output.exists())

    def test_windows_simulated_changed_parent_identity_blocks_publication(self):
        staged, output = self.base / 'identity-stage', self.base / 'identity-output'
        staged.mkdir(mode=0o755)
        write(staged, 'sentinel.txt', b'owned stage fixture\n')
        parent_inode = self.base.lstat().st_ino
        overrides = {}
        ordinary_root = sdk.ordinary_root
        parent_checks = 0

        def changed_after_parent_recheck(root):
            nonlocal parent_checks
            result = ordinary_root(root)
            if Path(root) == self.base:
                parent_checks += 1
                # Initial destination validation, identity snapshot, then its
                # immediate recheck. Alter only the recheck result's identity.
                if parent_checks == 3:
                    overrides[self.base] = {'st_ino': parent_inode + 1}
            return result

        with self.simulated_windows_metadata(state_overrides=overrides), \
                mock.patch.object(sdk, 'ordinary_root', side_effect=changed_after_parent_recheck), \
                mock.patch.object(os, 'rename') as rename, \
                self.assertRaisesRegex(ValueError, 'parent changed'):
            sdk.publish_fresh(staged, output)
        rename.assert_not_called()
        self.assertEqual((staged / 'sentinel.txt').read_bytes(), b'owned stage fixture\n')
        self.assertFalse(output.exists())

    def test_windows_simulated_unknown_parent_identity_blocks_publication(self):
        staged, output = self.base / 'unknown-identity-stage', self.base / 'unknown-identity-output'
        staged.mkdir(mode=0o755)
        write(staged, 'sentinel.txt', b'owned stage fixture\n')
        for field in ('st_dev', 'st_ino'):
            with self.subTest(field=field), \
                    self.simulated_windows_metadata(state_overrides={self.base: {field: 0}}), \
                    mock.patch.object(os, 'rename') as rename, self.assertRaisesRegex(ValueError, 'staging parent'):
                sdk.publish_fresh(staged, output)
            rename.assert_not_called()
            self.assertFalse(output.exists())
        self.assertEqual((staged / 'sentinel.txt').read_bytes(), b'owned stage fixture\n')

    def test_reparse_attributes_are_rejected_even_on_posix_hosts(self):
        state = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_nlink=1, st_file_attributes=0x400)
        with mock.patch.object(manifest, 'WINDOWS', False), self.assertRaisesRegex(ValueError, 'reparse'):
            manifest.plain_state(state, directory=False)

    def test_hardlinked_retained_files_fail_before_reading_bytes(self):
        original = self.binary / 'provider/fixture.mjs'
        linked = self.base / 'outside-hardlink'
        os.link(original, linked)
        with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('hardlink bytes must not be read')), \
                self.assertRaisesRegex(ValueError, 'singly linked'):
            manifest.read_document(self.binary, 'provider/fixture.mjs')

    def test_inventory_paths_and_modes_are_strict(self):
        binary = self.load(self.binary, 'engine-sdk.json')
        for name in ('../escape', '/absolute', 'a\\b', 'a//b', 'NUL.txt', 'bad?.txt', 'trailing.',
                     'CON .txt', 'LPT1 .log', 'CONIN$', 'CONOUT$'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                manifest.path_name(name)
        changes = [
            ('boolean file mode', lambda value: value['modes'].update({'provider/fixture.mjs': True})),
            ('boolean directory mode', lambda value: value['modes'].update({'provider': True})),
            ('privileged mode', lambda value: value['modes'].update({'provider/fixture.mjs': 0o4644})),
            ('missing mode', lambda value: value['modes'].pop('provider/fixture.mjs')),
            ('extra mode', lambda value: value['modes'].update({'unlisted': 0o644})),
            ('missing parent directory', lambda value: (value['directories'].remove('provider'), value['modes'].pop('provider'))),
            ('case alias', lambda value: (value['files'].update({'Provider/other': '0' * 64}),
                                         value['modes'].update({'Provider/other': 0o644}))),
        ]
        for name, change in changes:
            value = copy.deepcopy(binary)
            change(value)
            with self.subTest(name=name), self.assertRaises(ValueError):
                manifest.inventory_contract(value, 'engine-sdk.json')

    def test_root_manifest_modes_and_retained_symlinks_are_rejected(self):
        for root, name, verify in ((self.binary, 'engine-sdk.json', manifest.verify_engine),
                                   (self.sources, 'sources.json', manifest.verify_sources)):
            path = root / name
            with self.subTest(root=root.name, alteration='root manifest executable'):
                path.chmod(0o755)
                try:
                    with self.assertRaises(ValueError):
                        verify(root)
                finally:
                    path.chmod(0o644)
            with self.subTest(root=root.name, alteration='retained symlink'):
                link = root / 'extra-link'
                link.symlink_to(path.name)
                try:
                    with self.assertRaises(ValueError):
                        verify(root)
                finally:
                    link.unlink()

    def test_expected_recipe_manifest_target_and_toolchain_pins(self):
        binary, identity = manifest.verify_engine(self.binary)
        pinned = {'expected_recipe': self.recipe_id, 'expected_manifest': identity,
                  'target': binary['target'], 'toolchain': binary['toolchain']['identity_sha256']}
        self.assertEqual(manifest.verify_engine(self.binary, **pinned), (binary, identity))
        for key in pinned:
            invalid = copy.deepcopy(pinned)
            invalid[key] = ({**binary['target'], 'triple': 'different-fixture-triple'}
                            if key == 'target' else '0' * 64)
            with self.subTest(pin=key), self.assertRaisesRegex(ValueError, 'pin mismatch'):
                manifest.verify_engine(self.binary, **invalid)

    def test_export_and_restore_refuse_existing_empty_directory(self):
        group = self.export()
        for operation in ('export', 'restore', 'restore-sources'):
            output = self.base / ('occupied-' + operation)
            output.mkdir(mode=0o755)
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'already exists'):
                if operation == 'export':
                    sdk.export_group(self.binary, self.sources, output)
                else:
                    sdk.restore(group, self.recipe_id, output, sources=operation == 'restore-sources')
            self.assertEqual(list(output.iterdir()), [])

    def test_export_and_restore_refuse_dangling_output_symlink(self):
        group = self.export()
        for operation in ('export', 'restore', 'restore-sources'):
            output = self.base / ('linked-' + operation)
            target = self.base / ('missing-' + operation)
            output.symlink_to(target, target_is_directory=True)
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'already exists'):
                if operation == 'export':
                    sdk.export_group(self.binary, self.sources, output)
                else:
                    sdk.restore(group, self.recipe_id, output, sources=operation == 'restore-sources')
            self.assertTrue(output.is_symlink())
            self.assertFalse(target.exists())

    def test_failed_export_publishes_no_output(self):
        write(self.binary, 'provider/fixture.mjs', b'changed fixture\n')
        output = self.base / 'failed-export'
        with self.assertRaises(ValueError):
            sdk.export_group(self.binary, self.sources, output)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.base.glob('.engine-export-*')))

    def test_failed_archive_creation_cleans_staging_and_publishes_no_output(self):
        output = self.base / 'failed-archive-export'
        archive_tree = sdk.archive_tree

        def fail_after_archive(root, path, manifest_name):
            archive_tree(root, path, manifest_name)
            raise ValueError('injected failure after archive creation')

        with mock.patch.object(sdk, 'archive_tree', side_effect=fail_after_archive), \
                self.assertRaisesRegex(ValueError, 'injected failure'):
            sdk.export_group(self.binary, self.sources, output)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.base.glob('.engine-export-*')))

    def test_destination_created_before_atomic_publication_is_preserved(self):
        group = self.export()
        publish = sdk.publish_fresh

        def competing_destination(staged, output):
            output.mkdir(mode=0o755)
            write(output, 'owner.txt', b'competing writer fixture\n')
            return publish(staged, output)

        for operation in ('export', 'restore'):
            output = self.base / ('raced-' + operation)
            with self.subTest(operation=operation):
                with mock.patch.object(sdk, 'publish_fresh', side_effect=competing_destination), \
                        self.assertRaisesRegex(ValueError, 'already exists'):
                    if operation == 'export':
                        sdk.export_group(self.binary, self.sources, output)
                    else:
                        sdk.restore(group, self.recipe_id, output)
                self.assertEqual((output / 'owner.txt').read_bytes(), b'competing writer fixture\n')
                self.assertEqual([path.name for path in output.iterdir()], ['owner.txt'])
        self.assertFalse(list(self.base.glob('.engine-export-*')))
        self.assertFalse(list(self.base.glob('.engine-restore-*')))

    def test_successful_publication_preserves_foreign_recreation_of_old_stage_name(self):
        group = self.export()
        publish = sdk.publish_fresh
        recreated = []

        def recreate_old_stage(staged, output):
            result = publish(staged, output)
            staged.mkdir(mode=0o755)
            write(staged, 'foreign.txt', b'foreign recreation fixture\n')
            recreated.append(staged)
            return result

        for operation in ('export', 'restore'):
            with self.subTest(operation=operation):
                output = self.base / ('published-with-recreated-stage-' + operation)
                with mock.patch.object(sdk, 'publish_fresh', side_effect=recreate_old_stage):
                    if operation == 'export':
                        sdk.export_group(self.binary, self.sources, output)
                        sdk.verify_group(output, self.recipe_id)
                    else:
                        sdk.restore(group, self.recipe_id, output)
                        manifest.verify_engine(output)
                self.assertEqual((recreated[-1] / 'foreign.txt').read_bytes(), b'foreign recreation fixture\n')
                self.assertTrue(output.is_dir())

    def test_failed_staging_preserves_foreign_replacement_of_owned_root(self):
        group = self.export()
        archive_tree, extract_owned = sdk.archive_tree, sdk.extract_owned
        replacements = []

        def replace_owned_root(staged, operation):
            retained = self.base / ('relocated-owned-stage-' + operation)
            staged.rename(retained)
            staged.mkdir(mode=0o755)
            write(staged, 'foreign.txt', b'foreign replacement fixture\n')
            replacements.append(staged)
            raise ValueError('injected failure after root replacement')

        def archive_then_replace(root, path, manifest_name):
            archive_tree(root, path, manifest_name)
            replace_owned_root(path.parent, 'export')

        def extract_then_replace(archive, destination):
            extract_owned(archive, destination)
            replace_owned_root(destination, 'restore')

        for operation in ('export', 'restore'):
            with self.subTest(operation=operation):
                output = self.base / ('failed-with-replaced-stage-' + operation)
                target, replacement = (('archive_tree', archive_then_replace) if operation == 'export'
                                       else ('extract_owned', extract_then_replace))
                with mock.patch.object(sdk, target, side_effect=replacement), self.assertRaises(ValueError):
                    if operation == 'export':
                        sdk.export_group(self.binary, self.sources, output)
                    else:
                        sdk.restore(group, self.recipe_id, output)
                self.assertFalse(output.exists())
                self.assertEqual((replacements[-1] / 'foreign.txt').read_bytes(), b'foreign replacement fixture\n')

    def test_windows_simulated_unknown_owned_stage_identity_preserves_created_tree(self):
        mkdtemp = tempfile.mkdtemp
        for field in ('st_dev', 'st_ino'):
            created, overrides = [], {}

            def unidentified_tree(*args, **kwargs):
                path = Path(mkdtemp(*args, **kwargs))
                write(path, 'preserve.txt', b'unidentified stage fixture\n')
                overrides[path] = {field: 0}
                created.append(path)
                return str(path)

            with self.subTest(field=field), self.simulated_windows_metadata(state_overrides=overrides), \
                    mock.patch.object(sdk.tempfile, 'mkdtemp', side_effect=unidentified_tree), \
                    self.assertRaisesRegex(ValueError, 'identity unavailable; preserve tree'):
                sdk._OwnedTree(self.base, '.unknown-owned-stage-')
            self.assertEqual(len(created), 1)
            self.assertEqual((created[0] / 'preserve.txt').read_bytes(), b'unidentified stage fixture\n')

    def test_owned_stage_chmod_failure_cleans_identified_root(self):
        tree = sdk._OwnedTree(self.base, '.owned-chmod-failure-')
        with mock.patch.object(Path, 'chmod', side_effect=PermissionError('injected owned-stage chmod failure')), \
                self.assertRaisesRegex(PermissionError, 'injected owned-stage chmod failure'):
            with tree:
                self.fail('failed stage initialization must not enter the body')
        self.assertFalse(tree.path.exists())

    def test_export_rejects_nested_inputs_and_output_inside_inputs(self):
        for binary, sources, output in (
                (self.binary, self.binary, self.base / 'same-root-output'),
                (self.binary, self.sources, self.binary / 'inside-output'),
                (self.binary, self.sources, self.sources / 'inside-output')):
            with self.subTest(output=output), self.assertRaises(ValueError):
                sdk.export_group(binary, sources, output)
            self.assertFalse(output.exists())

    def test_group_requires_exact_pair_and_checksum_inventory(self):
        group = self.export()
        checksums = group / sdk.group_names(self.recipe_id)[2]
        original = checksums.read_bytes()
        for content in (original.splitlines(keepends=True)[0], original[::-1], original + b'\n'):
            checksums.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                sdk.verify_group(group, self.recipe_id)
        checksums.write_bytes(original)
        write(group, 'unrelated', b'extra\n')
        with self.assertRaises(ValueError):
            sdk.verify_group(group, self.recipe_id)

    def test_verification_export_and_restore_never_launch_retained_inputs(self):
        # Any subprocess use in these operations is a regression. The command
        # line itself is tested separately with the real Python interpreter.
        with mock.patch('subprocess.Popen', side_effect=AssertionError('input execution forbidden')), \
                mock.patch('os.system', side_effect=AssertionError('input execution forbidden')):
            manifest.verify_inputs(self.sources)
            manifest.verify_sources(self.sources)
            manifest.verify_engine(self.binary)
            group = self.export()
            sdk.verify_group(group, self.recipe_id)
            sdk.restore(group, self.recipe_id, self.base / 'passive-restore')

    def test_cli_emits_integrity_scope_and_rejects_fetch_and_build(self):
        command = [sys.executable, str(ROOT / 'tools/appended_engine_sdk.py')]
        verified = subprocess.run([*command, 'verify', '--root', str(self.binary),
                                   '--recipe', self.recipe_id], cwd=ROOT,
                                  capture_output=True, text=True, timeout=20)
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertEqual(json.loads(verified.stdout)['scope'], 'retained-byte-integrity-only')
        for action in ('fetch', 'build'):
            with self.subTest(action=action):
                rejected = subprocess.run([*command, action], cwd=ROOT,
                                          capture_output=True, text=True, timeout=20)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertEqual(rejected.stdout, '')
                self.assertIn('invalid choice', rejected.stderr)

    def test_cli_source_pins_and_irrelevant_flags_fail_without_output(self):
        source_hash = digest(self.sources / 'sources.json')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(sdk.main(['verify-sources', '--root', str(self.sources),
                                       '--recipe', self.recipe_id, '--manifest-sha256', source_hash]), 0)
        self.assertEqual(json.loads(output.getvalue())['manifest_sha256'], source_hash)
        for flag in ('--recipe', '--manifest-sha256'):
            output = io.StringIO()
            with self.subTest(pin=flag), contextlib.redirect_stdout(output), \
                    self.assertRaisesRegex(ValueError, 'pin mismatch'):
                sdk.main(['verify-sources', '--root', str(self.sources), flag, '0' * 64])
            self.assertEqual(output.getvalue(), '')
        for arguments in (
                ['recipe-id', '--root', str(self.sources), '--recipe', self.recipe_id],
                ['verify', '--root', str(self.binary), '--output', str(self.base / 'unexpected')],
                ['restore', '--group', str(self.base / 'missing-group'), '--recipe', self.recipe_id,
                 '--output', str(self.base / 'unexpected'), '--binary', str(self.binary)]):
            output = io.StringIO()
            with self.subTest(arguments=arguments), contextlib.redirect_stdout(output), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as rejected:
                sdk.main(arguments)
            self.assertEqual(rejected.exception.code, 2)
            self.assertEqual(output.getvalue(), '')
            self.assertFalse((self.base / 'unexpected').exists())


if __name__ == '__main__':
    unittest.main()
