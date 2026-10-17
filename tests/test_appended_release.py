"""Retained composition/recovery is pure byte work, with conservative claims."""
from contextlib import ExitStack
import copy
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_container as container
import appended_policy as policy
import appended_project as project
import appended_release as release
import artifact
import dependency_archive as archive
import source_identity


def document(path, value):
    path.write_bytes(container.canonical_json(value))


def pinned(path, **extra):
    return {'path': path.name, 'sha256': archive.digest(path), **extra}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / 'selected'
        self.inputs.mkdir()
        self.application = {'id': 'fork.example', 'name': 'Independent fork', 'version': '2.0.0'}
        self.source = self.root / 'source'
        (self.source / 'src').mkdir(parents=True)
        (self.source / 'src/kernel.cpp').write_text('retained kernel input\n')
        (self.source / 'src-web-appended').mkdir()
        (self.source / 'src-web-appended/index.html').write_text('<p>new application</p>')
        self.configuration = project.default_document()
        self.configuration['application'] = dict(self.application)
        self.configuration['appended']['web'].update(enabled=True, entry='index.html')
        self.configuration['startup']['primary'] = 'web'
        document(self.source / project.CONFIG_NAME, self.configuration)
        self.source_archive = self.inputs / 'downstream-source.tar.gz'
        self.source_manifest = source_identity.archive_source(self.source, self.source_archive)
        self.prefix = b'<!doctype html><html><head></head><body><p>retained shell</p>' + container.HTML_MARKER
        self.descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'html',
                           'profile': 'web', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
                           'capabilities': [], 'services': [], 'executable': {'length': len(self.prefix),
                           'sha256': container.digest(self.prefix)}, 'boundary_offset': None,
                           'provenance': {'producer': 'original-producer', 'qualification': 'unqualified-development'},
                           'kernel_inputs': policy.kernel_source_tree(self.source)}
        self.descriptor_path = self.inputs / 'kernel.json'
        document(self.descriptor_path, self.descriptor)
        self.base = self.inputs / 'base.tar.gz'
        self.members = {'bin/application.html': (self.prefix, 0o755),
                        'share/build-info.txt': (b'ORIGINAL KERNEL SOURCE AND PRODUCER\n', 0o644),
                        'lib/runtime.so': (b'unchanged library\x00\xff', 0o640),
                        'include/runtime.h': (b'int existing_contract(void);\n', 0o644)}
        self.directories = {'bin': 0o755, 'share': 0o750, 'lib': 0o755, 'include': 0o755, 'empty': 0o700}
        release._write_archive(self.base, self.members, self.directories)
        self.inventory_path = self.inputs / 'base.inventory.json'
        inventory = artifact.describe(self.base)
        inventory['modes'] = release._mode_inventory(self.members)
        document(self.inventory_path, inventory)
        self.payload = container.build_package({'web/index.html': b'<p>new application</p>'}, self.application,
                                              web_entry='web/index.html',
                                              identities={'source_tree': self.source_manifest['tree_sha256']})
        self.payload_path = self.inputs / 'application.sfapp'
        self.payload_path.write_bytes(container.encode_package(self.payload))
        self.recovery = self.inputs / 'retained-kernel-inputs.tar.gz'
        self.recovery.write_bytes(b'Explicit retained dependency/source group; not reconstruction evidence')
        self.evidence = self.inputs / 'original-evidence.json'
        document(self.evidence, {'original': 'never relabelled as the new application'})
        self.selection = {'schema_version': 1, 'kind': 'foundation-appended-selection',
                          'application': self.application,
                          'source': pinned(self.source_archive, tree_sha256=self.source_manifest['tree_sha256']),
                          'payload': pinned(self.payload_path), 'kernels': [self.kernel_entry()]}
        self.selection_path = self.inputs / 'selection.json'
        self.save_selection()

    def kernel_entry(self, identity='linux-html', output='fork-linux.tar.gz'):
        return {'id': identity, 'archive': pinned(self.base), 'inventory': pinned(self.inventory_path),
                'descriptor': pinned(self.descriptor_path), 'runtime_member': 'bin/application.html',
                'output': output,
                'original_source': pinned(self.source_archive, tree_sha256=self.source_manifest['tree_sha256']),
                'recovery': [pinned(self.recovery)], 'evidence': [pinned(self.evidence)]}

    def save_selection(self):
        document(self.selection_path, self.selection)

    def forbid_processes(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name in ('run', 'Popen', 'check_output', 'check_call', 'call'):
            stack.enter_context(patch.object(subprocess, name, side_effect=AssertionError('native/process invocation: ' + name)))
        return stack

    def prepare(self, output='candidate'):
        return release.prepare_release(self.selection_path, self.root / output)

    def repin_candidate(self, candidate):
        """Model a separately supplied malicious pin, beyond simple hash damage."""
        composition = candidate / 'composition.json'
        recovery = json.loads((candidate / 'recovery.json').read_bytes())
        recovery['composition_sha256'] = archive.digest(composition)
        recovery['selection_sha256'] = archive.digest(candidate / 'selection.json')
        document(candidate / 'recovery.json', recovery)
        record = json.loads((candidate / 'candidate.json').read_bytes())
        record['files'] = release._files(candidate, ('candidate.json',))
        document(candidate / 'candidate.json', record)
        return archive.digest(candidate / 'candidate.json')

    def replace_downstream_source(self):
        original = self.inputs / 'original-source.tar.gz'
        if not original.exists():
            shutil.copyfile(self.source_archive, original)
            for entry in self.selection['kernels']:
                entry['original_source'] = pinned(original, tree_sha256=self.source_manifest['tree_sha256'])
        self.source_archive.unlink()
        identity = source_identity.archive_source(self.source, self.source_archive)
        self.selection['source'] = pinned(self.source_archive, tree_sha256=identity['tree_sha256'])
        return identity

    def test_composes_same_package_across_mappings_preserving_every_other_member(self):
        self.selection['kernels'].append(self.kernel_entry('windows-html', 'fork-windows.tar.gz'))
        self.save_selection()
        with self.forbid_processes():
            result = self.prepare()
        self.assertFalse(result['publication_eligible'])
        self.assertEqual(result['qualification'], 'incomplete')
        candidate = self.root / 'candidate'
        record = json.loads((candidate / 'composition.json').read_bytes())
        self.assertEqual(record['source']['tree_sha256'], self.source_manifest['tree_sha256'])
        self.assertEqual(record['payload']['payload_id'], self.payload.payload_id)
        self.assertEqual(len(record['artifacts']), 2)
        for entry in record['artifacts']:
            _, observed, directories = release._members(candidate / entry['archive'])
            self.assertEqual(directories, self.directories)
            for name, value in self.members.items():
                if name != 'bin/application.html':
                    self.assertEqual(observed[name], value)
            composed, mode = observed['bin/application.html']
            self.assertEqual(mode, 0o755)
            self.assertTrue(composed.startswith(self.prefix))
            self.assertEqual(container.parse_artifact(composed, self.descriptor).package.data, self.payload.data)
        self.assertEqual(self.base.read_bytes(), (candidate / 'inputs' / archive.digest(self.base)).read_bytes())
        self.assertEqual(self.descriptor_path.read_bytes(), (candidate / 'inputs' / archive.digest(self.descriptor_path)).read_bytes())
        frozen = release.verify_candidate(candidate, result['candidate_sha256'])
        self.assertNotIn('candidate.json', frozen['files'])
        self.assertNotIn('certificate', frozen)
        self.assertNotIn('candidate_sha256', record)
        self.assertEqual(record['recomposition_environment']['python_implementation'], sys.implementation.name)
        for name, pin in record['composer_sources'].items():
            self.assertEqual((candidate / 'inputs' / pin).read_bytes(), (ROOT / 'tools' / name).read_bytes())

    def test_recovery_is_byte_identical_without_native_build_or_git_history(self):
        with self.forbid_processes():
            first = self.prepare()
            replay = release.recover(self.root / 'candidate', first['candidate_sha256'], self.root / 'recovered')
        self.assertEqual(first, replay)
        self.assertEqual(release._files(self.root / 'candidate'), release._files(self.root / 'recovered'))

    def test_semantic_subject_verification_is_pure_and_preserves_every_input(self):
        result = self.prepare()
        candidate = self.root / 'candidate'
        original = release._files(candidate)
        with self.forbid_processes():
            subject = release.verify_composition_subject(candidate, result['candidate_sha256'])
        self.assertEqual(subject['candidate_sha256'], result['candidate_sha256'])
        self.assertEqual(subject['composition_sha256'], result['composition_sha256'])
        self.assertEqual(subject['selection_sha256'], archive.digest(candidate / 'selection.json'))
        self.assertEqual(subject['composition']['artifacts'][0]['kernel_prefix_sha256'], container.digest(self.prefix))
        self.assertEqual(release._files(candidate), original)

    def test_semantic_subject_cli_exposes_verified_relationships(self):
        result = self.prepare()
        captured = io.StringIO()
        with self.forbid_processes(), patch('sys.stdout', captured):
            self.assertEqual(release.main(['verify-composition', '--input', str(self.root / 'candidate'),
                                          '--candidate-sha256', result['candidate_sha256']]), 0)
        observed = json.loads(captured.getvalue())
        self.assertEqual(observed['candidate_sha256'], result['candidate_sha256'])
        self.assertEqual(observed['composition']['artifacts'][0]['runtime_member'], 'bin/application.html')

    def test_semantic_subject_rejects_rehashed_native_closure_change(self):
        self.prepare()
        candidate = self.root / 'candidate'
        composition = json.loads((candidate / 'composition.json').read_bytes())
        product = composition['artifacts'][0]
        path = candidate / product['archive']
        _, members, directories = release._members(path)
        members['lib/runtime.so'] = (b'foreign native implementation', 0o777)
        path.unlink()
        release._write_archive(path, members, directories)
        product['sha256'] = archive.digest(path)
        product['files'] = artifact.describe(path)['files']
        product['modes'] = release._mode_inventory(members)
        document(candidate / 'composition.json', composition)
        pin = self.repin_candidate(candidate)
        release.verify_candidate(candidate, pin)
        with self.assertRaisesRegex(ValueError, 'closure'):
            release.verify_composition_subject(candidate, pin)

    def test_semantic_subject_rejects_rehashed_metadata_lie_and_extra_input(self):
        for attack in ('metadata', 'extra-input'):
            with self.subTest(attack=attack):
                result = self.prepare(attack)
                candidate = self.root / attack
                if attack == 'metadata':
                    composition = json.loads((candidate / 'composition.json').read_bytes())
                    composition['artifacts'][0]['kernel_prefix_length'] += 1
                    document(candidate / 'composition.json', composition)
                else:
                    (candidate / 'inputs' / ('0' * 64)).write_bytes(b'unexplained retained evidence')
                pin = self.repin_candidate(candidate)
                self.assertNotEqual(pin, result['candidate_sha256'])
                release.verify_candidate(candidate, pin)
                with self.assertRaisesRegex(ValueError, 'metadata|unexplained'):
                    release.verify_composition_subject(candidate, pin)

    def test_semantic_subject_does_not_alias_json_booleans_and_integers(self):
        for attack in ('qualification', 'abi-major', 'abi-minor'):
            with self.subTest(attack=attack):
                self.prepare(attack)
                candidate = self.root / attack
                composition = json.loads((candidate / 'composition.json').read_bytes())
                if attack == 'qualification':
                    composition['qualification']['publication_eligible'] = 0
                else:
                    composition['artifacts'][0]['abi']['major' if attack == 'abi-major' else 'minor'] = attack == 'abi-major'
                document(candidate / 'composition.json', composition)
                pin = self.repin_candidate(candidate)
                release.verify_candidate(candidate, pin)
                with self.assertRaisesRegex(ValueError, 'qualification|metadata'):
                    release.verify_composition_subject(candidate, pin)

    def test_semantic_subject_rejects_same_byte_inode_replacement_during_read(self):
        result = self.prepare()
        candidate = self.root / 'candidate'
        original = release._source
        replaced = False

        def replacing(*args, **kwargs):
            nonlocal replaced
            value = original(*args, **kwargs)
            if not replaced:
                path = candidate / 'inputs' / archive.digest(self.evidence)
                contents = path.read_bytes()
                alternate = candidate / 'replacement'
                alternate.write_bytes(contents)
                alternate.replace(path)
                replaced = True
            return value

        with patch.object(release, '_source', side_effect=replacing):
            with self.assertRaisesRegex(ValueError, 'changed during semantic'):
                release.verify_composition_subject(candidate, result['candidate_sha256'])
        release.verify_candidate(candidate, result['candidate_sha256'])

    def test_semantic_subject_records_but_does_not_invent_current_recomposition_environment(self):
        self.prepare()
        candidate = self.root / 'candidate'
        composition = json.loads((candidate / 'composition.json').read_bytes())
        composition['recomposition_environment']['python_version'] = [3, 99, 1]
        document(candidate / 'composition.json', composition)
        pin = self.repin_candidate(candidate)
        subject = release.verify_composition_subject(candidate, pin)
        self.assertEqual(subject['composition']['recomposition_environment']['python_version'], [3, 99, 1])

    def test_excluded_empty_source_directories_cannot_trigger_git_or_native_tools(self):
        for name in ('.git', 'build', 'src/__pycache__', '.env'):
            with self.subTest(name=name):
                malicious = self.inputs / 'extra-directory.tar.gz'
                with tarfile.open(self.source_archive, 'r:*') as before:
                    with tarfile.open(malicious, 'w:gz') as after:
                        for member in before:
                            stream = before.extractfile(member) if member.isfile() else None
                            after.addfile(member, stream)
                        member = tarfile.TarInfo(name)
                        member.type, member.mode = tarfile.DIRTYPE, 0o755
                        after.addfile(member)
                self.selection['source'] = pinned(malicious, tree_sha256=self.source_manifest['tree_sha256'])
                self.save_selection()
                with self.forbid_processes(), self.assertRaisesRegex(ValueError, 'excluded/generated/private'):
                    self.prepare('rejected-directory')
                self.assertFalse((self.root / 'rejected-directory').exists())
                malicious.unlink()

    def test_neither_mode_removes_previous_suffix_and_recovers_exact_pristine_kernel(self):
        old_members = dict(self.members)
        old_members['bin/application.html'] = (container.compose_bytes(self.prefix, self.descriptor, self.payload), 0o755)
        self.base.unlink()
        release._write_archive(self.base, old_members, self.directories)
        document(self.inventory_path, artifact.describe(self.base))
        self.selection['kernels'][0].update(archive=pinned(self.base), inventory=pinned(self.inventory_path))
        self.selection['payload'] = None
        self.configuration['appended']['web']['enabled'] = False
        self.configuration['startup']['primary'] = 'compiled'
        document(self.source / project.CONFIG_NAME, self.configuration)
        self.replace_downstream_source()
        self.save_selection()
        with self.forbid_processes():
            result = self.prepare()
            replay = release.recover(self.root / 'candidate', result['candidate_sha256'], self.root / 'recovered')
        self.assertEqual(result, replay)
        _, members, _ = release._members(self.root / 'candidate/artifacts/fork-linux.tar.gz')
        self.assertEqual(members['bin/application.html'], (self.prefix, 0o755))
        record = json.loads((self.root / 'candidate/composition.json').read_bytes())
        self.assertEqual(record['payload'], {'mode': 'neither', 'transport_sha256': None,
                                             'package_sha256': None, 'payload_id': None})

    def test_recovery_with_different_environment_fails_before_exposing_output(self):
        result = self.prepare()
        with patch.object(release.zlib, 'ZLIB_RUNTIME_VERSION', 'different-unqualified-zlib'), \
                self.assertRaisesRegex(ValueError, 'did not reproduce'):
            release.recover(self.root / 'candidate', result['candidate_sha256'], self.root / 'wrong-environment')
        self.assertFalse((self.root / 'wrong-environment').exists())

    def test_application_selection_cannot_override_restored_project_identity(self):
        alternate = dict(self.application, id='other.application', version='3.0.0')
        self.selection['application'] = alternate
        package = container.build_package({'web/index.html': b'other app'}, alternate, web_entry='web/index.html')
        self.payload_path.write_bytes(container.encode_package(package))
        self.selection['payload'] = pinned(self.payload_path)
        self.save_selection()
        with self.forbid_processes(), self.assertRaisesRegex(ValueError, 'application differs from restored'):
            self.prepare('wrong-application')
        self.assertFalse((self.root / 'wrong-application').exists())

    def test_payload_presence_must_match_restored_project_mode(self):
        self.selection['payload'] = None
        self.save_selection()
        with self.forbid_processes(), self.assertRaisesRegex(ValueError, 'payload mode differs from restored'):
            self.prepare('wrong-mode')
        self.assertFalse((self.root / 'wrong-mode').exists())

    def test_retained_profile_must_match_explicit_project_profile(self):
        self.configuration['kernel']['profile'] = 'both'
        document(self.source / project.CONFIG_NAME, self.configuration)
        source = self.replace_downstream_source()
        package = container.build_package({'web/index.html': b'current app'}, self.application,
                                          web_entry='web/index.html', identities={'source_tree': source['tree_sha256']})
        self.payload_path.write_bytes(container.encode_package(package))
        self.selection['payload'] = pinned(self.payload_path)
        self.save_selection()
        with self.forbid_processes(), self.assertRaisesRegex(ValueError, 'profile differs from explicit'):
            self.prepare('wrong-profile')
        self.assertFalse((self.root / 'wrong-profile').exists())

    def test_recovery_revalidates_entire_original_before_reserving_output(self):
        result = self.prepare()
        publish = release._publish_tree

        def mutate(staged, destination, snapshots=(), **kwargs):
            (self.root / 'candidate/composition.json').write_text('changed after initial verification')
            return publish(staged, destination, snapshots, **kwargs)

        with self.forbid_processes(), patch.object(release, '_publish_tree', side_effect=mutate), \
                self.assertRaisesRegex(ValueError, 'complete inventory'):
            release.recover(self.root / 'candidate', result['candidate_sha256'], self.root / 'recovered')
        self.assertFalse((self.root / 'recovered').exists())

    def test_recovery_revalidates_original_again_before_final_marker(self):
        result = self.prepare()
        link = release.os.link
        changed = False

        def mutate(source, destination, **kwargs):
            nonlocal changed
            if not changed and self.root / 'recovered' in Path(destination).parents:
                changed = True
                (self.root / 'candidate/composition.json').write_text('changed during output linking')
            return link(source, destination, **kwargs)

        with self.forbid_processes(), patch.object(release.os, 'link', side_effect=mutate), \
                self.assertRaisesRegex(ValueError, 'publication incomplete'):
            release.recover(self.root / 'candidate', result['candidate_sha256'], self.root / 'recovered')
        self.assertTrue(changed)
        self.assertFalse((self.root / 'recovered/candidate.json').exists())

    def test_recovery_rejects_replaced_identical_original_entry(self):
        result = self.prepare()
        publish = release._publish_tree

        def replace(staged, destination, snapshots=(), **kwargs):
            path = self.root / 'candidate/composition.json'
            content = path.read_bytes()
            path.rename(path.with_suffix('.old'))
            path.write_bytes(content)
            path.with_suffix('.old').unlink()
            return publish(staged, destination, snapshots, **kwargs)

        with patch.object(release, '_publish_tree', side_effect=replace), \
                self.assertRaisesRegex(ValueError, 'original candidate changed'):
            release.recover(self.root / 'candidate', result['candidate_sha256'], self.root / 'recovered')
        self.assertFalse((self.root / 'recovered').exists())

    def test_payload_only_source_change_keeps_original_kernel_identity(self):
        original = self.inputs / 'original-source.tar.gz'
        shutil.copyfile(self.source_archive, original)
        self.selection['kernels'][0]['original_source'] = pinned(original, tree_sha256=self.source_manifest['tree_sha256'])
        (self.source / 'src-web-appended/index.html').write_text('<p>independent fork update</p>')
        self.source_archive.unlink()
        changed = source_identity.archive_source(self.source, self.source_archive)
        self.selection['source'] = pinned(self.source_archive, tree_sha256=changed['tree_sha256'])
        payload = container.build_package({'web/index.html': b'<p>independent fork update</p>'}, self.application,
                                          web_entry='web/index.html', identities={'source_tree': changed['tree_sha256']})
        self.payload_path.write_bytes(container.encode_package(payload))
        self.selection['payload'] = pinned(self.payload_path)
        self.save_selection()
        with self.forbid_processes():
            self.prepare()
        record = json.loads((self.root / 'candidate/composition.json').read_bytes())
        self.assertNotEqual(record['source']['tree_sha256'], record['artifacts'][0]['original_source_tree_sha256'])
        self.assertEqual(record['artifacts'][0]['original_source_tree_sha256'], self.source_manifest['tree_sha256'])

    def test_changed_or_unknown_kernel_source_fails_without_fallback(self):
        for change in ('content', 'mode', 'unknown'):
            with self.subTest(change=change):
                root = self.root / ('changed-' + change)
                shutil.copytree(self.source, root)
                if change == 'content':
                    (root / 'src/kernel.cpp').write_text('different kernel')
                elif change == 'mode':
                    (root / 'src/kernel.cpp').chmod(0o755)
                else:
                    (root / 'unknown-contract').write_text('must not disappear')
                source = self.inputs / ('changed-' + change + '.tar.gz')
                identity = source_identity.archive_source(root, source)
                self.selection['source'] = pinned(source, tree_sha256=identity['tree_sha256'])
                # Absence of an internal source binding is permitted because the
                # external frozen selection still binds package and full source.
                package = container.build_package({'web/index.html': b'<p>new application</p>'}, self.application,
                                                  web_entry='web/index.html')
                self.payload_path.write_bytes(container.encode_package(package))
                self.selection['payload'] = pinned(self.payload_path)
                self.save_selection()
                with self.forbid_processes(), self.assertRaisesRegex(ValueError, 'kernel maintenance required'):
                    self.prepare('rejected-' + change)
                self.assertFalse((self.root / ('rejected-' + change)).exists())

    def test_missing_base_wrong_pin_profile_and_missing_recovery_fail_closed(self):
        cases = ('missing-base', 'bad-pin', 'profile', 'recovery', 'inventory', 'payload-identity')
        original = copy.deepcopy(self.selection)
        for case in cases:
            with self.subTest(case=case):
                self.selection = copy.deepcopy(original)
                document(self.descriptor_path, self.descriptor)
                kernel = self.selection['kernels'][0]
                if case == 'missing-base':
                    kernel['archive']['path'] = 'absent.tar.gz'
                elif case == 'bad-pin':
                    kernel['descriptor']['sha256'] = '0' * 64
                elif case == 'profile':
                    changed = copy.deepcopy(self.descriptor)
                    changed['profile'] = 'minimal'
                    document(self.descriptor_path, changed)
                    kernel['descriptor'] = pinned(self.descriptor_path)
                elif case == 'recovery':
                    kernel['recovery'] = []
                elif case == 'inventory':
                    inventory = artifact.describe(self.base)
                    inventory['files'].pop('lib/runtime.so')
                    document(self.inventory_path, inventory)
                    kernel['inventory'] = pinned(self.inventory_path)
                else:
                    self.selection['application']['version'] = 'wrong-version'
                self.save_selection()
                with self.forbid_processes(), self.assertRaises(ValueError):
                    self.prepare('rejected-' + case)
                self.assertFalse((self.root / ('rejected-' + case)).exists())

    def test_old_composition_is_replaced_once_and_complete_prefix_verified(self):
        old = container.build_package({'web/index.html': b'old app'}, self.application, web_entry='web/index.html')
        old_members = dict(self.members)
        old_members['bin/application.html'] = (container.compose_bytes(self.prefix, self.descriptor, old), 0o755)
        self.base.unlink()
        release._write_archive(self.base, old_members, self.directories)
        document(self.inventory_path, artifact.describe(self.base))
        self.selection['kernels'][0].update(archive=pinned(self.base), inventory=pinned(self.inventory_path))
        self.save_selection()
        with self.forbid_processes():
            self.prepare()
        _, observed, _ = release._members(self.root / 'candidate/artifacts/fork-linux.tar.gz')
        self.assertEqual(observed['bin/application.html'][0], container.compose_bytes(self.prefix, self.descriptor, self.payload))

    def test_archive_parent_alias_and_links_are_rejected(self):
        for malformed in ('alias', 'symlink'):
            path = self.inputs / ('unsafe-' + malformed + '.tar.gz')
            with tarfile.open(path, 'w:gz') as bundle:
                member = tarfile.TarInfo('BIN/extra')
                member.size = 1
                bundle.addfile(member, io.BytesIO(b'x'))
                if malformed == 'alias':
                    member = tarfile.TarInfo('bin/application.html')
                    member.size = len(self.prefix)
                    bundle.addfile(member, io.BytesIO(self.prefix))
                else:
                    member = tarfile.TarInfo('bin/link')
                    member.type = tarfile.SYMTYPE
                    member.linkname = 'extra'
                    bundle.addfile(member)
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                release._members(path)

    def test_unix_zip_zero_modes_are_preserved_without_broadening_permissions(self):
        path = self.inputs / 'zero-permissions.zip'
        with zipfile.ZipFile(path, 'w') as bundle:
            for name, file_type in (('private/', stat.S_IFDIR), ('private/file', stat.S_IFREG)):
                member = zipfile.ZipInfo(name)
                member.create_system = 3
                member.external_attr = file_type << 16
                bundle.writestr(member, b'' if file_type == stat.S_IFDIR else b'private bytes')
        _, members, directories = release._members(path)
        self.assertEqual(members['private/file'], (b'private bytes', 0))
        self.assertEqual(directories['private'], 0)
        output = self.inputs / 'zero-permissions.tar.gz'
        release._write_archive(output, members, directories)
        self.assertEqual(release._members(output)[1:], (members, directories))

    def test_existing_or_concurrently_created_destination_is_preserved(self):
        output = self.root / 'occupied'
        output.mkdir()
        (output / 'foreign').write_text('preserve me')
        with self.assertRaises(ValueError):
            self.prepare('occupied')
        self.assertEqual((output / 'foreign').read_text(), 'preserve me')
        publish = release._publish_tree

        def competing(staged, destination, snapshots=()):
            destination.mkdir()
            (destination / 'foreign').write_text('concurrent writer')
            return publish(staged, destination, snapshots)

        with patch.object(release, '_publish_tree', side_effect=competing), self.assertRaises(FileExistsError):
            self.prepare('race')
        self.assertEqual((self.root / 'race/foreign').read_text(), 'concurrent writer')

    def test_input_changed_before_publication_never_creates_candidate(self):
        publish = release._publish_tree

        def change(staged, destination, snapshots=()):
            self.evidence.write_text('changed original evidence')
            return publish(staged, destination, snapshots)

        with patch.object(release, '_publish_tree', side_effect=change), self.assertRaisesRegex(ValueError, 'changed'):
            self.prepare()
        self.assertFalse((self.root / 'candidate').exists())

    def test_publication_failure_preserves_foreign_entries_and_omits_validity_marker(self):
        link = release.os.link
        injected = False

        def add_foreign(source, target, **kwargs):
            nonlocal injected
            result = link(source, target, **kwargs)
            if not injected:
                injected = True
                (self.root / 'candidate/foreign').write_text('preserve foreign writer')
            return result

        with patch.object(release.os, 'link', side_effect=add_foreign), \
                self.assertRaisesRegex(ValueError, 'publication incomplete'):
            self.prepare()
        self.assertEqual((self.root / 'candidate/foreign').read_text(), 'preserve foreign writer')
        self.assertFalse((self.root / 'candidate/candidate.json').exists())

    def test_nested_candidate_basename_is_an_ordinary_group_file(self):
        staged = self.root / 'group'
        (staged / 'prior').mkdir(parents=True)
        (staged / 'prior/candidate.json').write_text('prior independently pinned inventory')
        (staged / 'selection.json').write_text('group selection')
        release._publish_tree(staged, self.root / 'acquired')
        self.assertEqual(release._files(staged), release._files(self.root / 'acquired'))

    def test_candidate_tampering_and_unpinned_recovery_fail(self):
        result = self.prepare()
        with self.assertRaisesRegex(ValueError, 'independently pinned'):
            release.verify_candidate(self.root / 'candidate', '0' * 64)
        (self.root / 'candidate/extra').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'complete inventory'):
            release.recover(self.root / 'candidate', result['candidate_sha256'], self.root / 'recovered')
        self.assertFalse((self.root / 'recovered').exists())

    def test_linked_input_parent_is_rejected(self):
        alias = self.root / 'linked'
        alias.symlink_to(self.inputs, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Linked'):
            release.prepare_release(alias / 'selection.json', self.root / 'candidate')

    def test_manual_workflow_separates_read_credentials_and_never_publishes(self):
        workflow = (ROOT / '.github/workflows/appended-compose.yml').read_text()
        self.assertIn('workflow_dispatch:', workflow)
        self.assertIn('contents: read', workflow)
        self.assertIn('fetch-inputs', workflow)
        self.assertIn('appended prepare-release', workflow)
        self.assertRegex(workflow, r'uses: actions/upload-artifact@[0-9a-f]{40}')
        self.assertNotIn('contents: write', workflow)
        for prohibited in ('cmake ', 'apt-get', 'rustup', 'cargo ', 'gh release', 'workflow_dispatches', 'lifecycle.py'):
            self.assertNotIn(prohibited, workflow)
        compose = workflow.split('- name: Compose frozen', 1)[1]
        self.assertNotIn('GH_TOKEN', compose)
        self.assertNotIn('${{ inputs.', compose)


class AcquisitionTests(unittest.TestCase):
    def test_explicit_pinned_source_group_uses_read_only_helpers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            group = root / 'group'
            group.mkdir()
            document(group / 'selection.json', {'schema_version': 1})
            (group / 'extra.bin').write_bytes(b'retained dependency')
            retained = root / 'retained.tar.gz'
            # archive_tree may replace only this private, owned staging path.
            archive.archive_tree(group, retained)
            pin, selection_pin = archive.digest(retained), archive.digest(group / 'selection.json')

            class FakeRemote:
                repository = 'upstream/source'

                def __init__(self):
                    self.reads = []
                    self.on_unchanged = None

                def by_id(self, identity, tag):
                    self.reads.append(('release', identity, tag))
                    return {'id': identity, 'tag_name': tag, 'draft': False}

                def reference(self, tag):
                    return 'a' * 40

                def assets(self, info):
                    return {'group.tar.gz': {'id': 123, 'name': 'group.tar.gz', 'size': retained.stat().st_size,
                                             'digest': 'sha256:' + pin}}

                def download(self, row, path, expected):
                    self.reads.append(('download', row['id'], expected))
                    self.downloaded = path
                    shutil.copyfile(retained, path)

                def unchanged(self, tag, info, assets, expected_ref):
                    self.reads.append(('unchanged', tag, expected_ref))
                    if self.on_unchanged:
                        self.on_unchanged(self.downloaded.parent / 'group')

            remote = FakeRemote()
            result = release.fetch_inputs(remote.repository, 'source-v1', 77, 'a' * 40, 'group.tar.gz',
                                          pin, selection_pin, root / 'acquired', remote=remote)
            self.assertEqual(result['schema_version'], 1)
            self.assertEqual(result['kind'], 'foundation-appended-acquisition')
            self.assertEqual(result['source_repository'], 'upstream/source')
            self.assertEqual(result['source_tag'], 'source-v1')
            self.assertEqual(result['release_id'], 77)
            self.assertEqual(result['asset_id'], 123)
            self.assertEqual(result['asset_name'], 'group.tar.gz')
            self.assertEqual(result['asset_size'], retained.stat().st_size)
            self.assertEqual(result['group_files'], release._files(group))
            self.assertEqual(result['origin'], {'kind': 'local'})
            self.assertEqual((root / 'acquired/selection.json').read_bytes(), (group / 'selection.json').read_bytes())
            self.assertEqual(remote.reads[-1], ('unchanged', 'source-v1', 'a' * 40))
            with self.assertRaisesRegex(ValueError, 'repository differs'):
                release.fetch_inputs('downstream/other', 'source-v1', 77, 'a' * 40, 'group.tar.gz',
                                     pin, selection_pin, root / 'wrong', remote=remote)
            origin = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'downstream/application',
                      'GITHUB_WORKFLOW_REF': 'downstream/application/.github/workflows/appended-compose.yml@refs/heads/main',
                      'GITHUB_WORKFLOW_SHA': 'b' * 40, 'GITHUB_RUN_ID': '1234',
                      'GITHUB_RUN_ATTEMPT': '2', 'GITHUB_JOB': 'compose', 'RUNNER_ENVIRONMENT': 'github-hosted'}
            with patch.dict(os.environ, origin):
                observed = release.fetch_inputs(remote.repository, 'source-v1', 77, 'a' * 40, 'group.tar.gz',
                                                pin, selection_pin, root / 'actions', remote=remote)
            self.assertEqual(observed['origin'], {'kind': 'github-actions',
                'repository': 'downstream/application', 'workflow_ref': origin['GITHUB_WORKFLOW_REF'],
                'workflow_sha': 'b' * 40, 'run_id': '1234', 'run_attempt': '2', 'job': 'compose',
                'runner_environment': 'github-hosted'})
            incomplete = dict(origin, GITHUB_WORKFLOW_SHA='')
            before = list(remote.reads)
            with patch.dict(os.environ, incomplete):
                with self.assertRaisesRegex(ValueError, 'acquisition origin'):
                    release.fetch_inputs(remote.repository, 'source-v1', 77, 'a' * 40, 'group.tar.gz',
                                         pin, selection_pin, root / 'incomplete', remote=remote)
            self.assertFalse((root / 'incomplete').exists())
            self.assertEqual([row for row in remote.reads[len(before):] if row[0] == 'download'], [])
            with self.assertRaisesRegex(ValueError, 'positive release ID'):
                release.fetch_inputs(remote.repository, 'source-v1', True, 'a' * 40, 'group.tar.gz',
                                     pin, selection_pin, root / 'boolean-id', remote=remote)
            self.assertEqual(retained.stat().st_size, result['asset_size'])
            self.assertEqual(archive.digest(retained), pin)
            for attack in ('bytes', 'inode', 'extra'):
                def mutate(group_root, attack=attack):
                    path = group_root / 'extra.bin'
                    if attack == 'bytes':
                        path.write_bytes(b'changed while remote metadata was checked')
                    elif attack == 'inode':
                        replacement = group_root / 'replacement'
                        replacement.write_bytes(path.read_bytes())
                        replacement.replace(path)
                    else:
                        (group_root / 'unlisted.bin').write_bytes(b'foreign')
                remote.on_unchanged = mutate
                with self.assertRaisesRegex(ValueError, 'group changed'):
                    release.fetch_inputs(remote.repository, 'source-v1', 77, 'a' * 40, 'group.tar.gz',
                                         pin, selection_pin, root / ('mutated-' + attack), remote=remote)
                self.assertFalse((root / ('mutated-' + attack)).exists())


if __name__ == '__main__':
    unittest.main()
