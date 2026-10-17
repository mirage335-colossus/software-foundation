"""Offline archive install lifecycle fixtures, never native qualification.

The ELF and HTML runtimes are structural byte vectors. Only physical native or
browser execution is replaced: candidate verification, extraction, installation,
state comparison, replacement and removal use the production implementation.
"""
import copy
import json
from pathlib import Path
import platform
import shutil
import stat
import struct
import sys
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_container as container
import appended_browser_check as browser
import appended_install_check as install
import appended_project as project
import appended_release as release
import appended_release_check as check
import artifact
import dependency_archive as archive
import source_identity
import test_appended_release_check as fixtures
import test_appended_browser_check as browser_fixtures


@unittest.skipUnless(sys.platform.startswith('linux') and
                     platform.machine().lower() in ('x86_64', 'amd64'),
                     'structural ELF fixture selects the actual Linux x86_64 adapter')
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CheckTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.candidate = self.fixture.candidate
        self.subject = release.verify_composition_subject(self.candidate, self.fixture.candidate_pin)
        self.entry = self.subject['composition']['artifacts'][0]
        self.prior, self.prior_pin, self.prior_entry = self.predecessor()
        self.scenario = self.root / 'install scenario.json'
        self.before_bytes = {'settings/user.txt': b'previous user preference\n'}
        self.after_bytes = {'settings/user.txt': b'upgraded user preference\n',
                            'history/latest.txt': b'upgraded application history\n'}
        self.scenario_data = {
            'schema_version': 1, 'kind': 'foundation-appended-install-scenario',
            'candidate_sha256': self.subject['candidate_sha256'], 'artifact_id': self.entry['id'],
            'target': 'linux-x86_64', 'backend': 'terminal', 'channels': ['archive'],
            'inputs': {self.prior.name: archive.digest(self.prior)},
            'predecessor': {'archive': self.prior.name, 'candidate_sha256': self.prior_pin,
                            'artifact_id': self.prior_entry['id']},
            'phases': {phase: [{'id': phase + '-state',
                                'argv': ['--phase', phase, '--state', '{state}', '--prefix', '{prefix}',
                                         'literal $(no command); path with spaces'],
                                'exit_code': 0, 'stdout': phase + ' completed\n', 'stderr': ''}]
                       for phase in ('clean', 'previous', 'upgraded')},
            'state': {'before': self.hashes(self.before_bytes), 'after': self.hashes(self.after_bytes)}}
        self.executions = []

    @staticmethod
    def hashes(values):
        return {name: container.digest(data) for name, data in values.items()}

    def predecessor(self, *, version='0.9.0', application_id=None, changed_runtime=True,
                    name='previous', top_level=False, root_only=False, extra_members=None):
        """Produce a separately verified earlier candidate using byte tools only."""
        inputs = self.root / (name + ' inputs')
        inputs.mkdir()
        source = inputs / 'source'
        (source / 'src').mkdir(parents=True)
        (source / 'src/kernel.cpp').write_bytes(b'retained native kernel source\n')
        application = dict(self.fixture.application, version=version)
        if application_id is not None:
            application['id'] = application_id
        configuration = project.default_document()
        configuration['application'] = application
        fixtures.document(source / project.CONFIG_NAME, configuration)
        source_archive = inputs / 'source.tar.gz'
        identity = source_identity.archive_source(source, source_archive)
        prefix = bytearray(self.fixture.prefix)
        if changed_runtime:
            prefix[512] ^= 1  # Different retained bytes without changing ELF structure.
        descriptor = copy.deepcopy(self.fixture.descriptor)
        descriptor['executable']['sha256'] = container.digest(prefix)
        descriptor_path = inputs / 'kernel.json'
        fixtures.document(descriptor_path, descriptor)
        runtime_member = 'retained-runtime' if top_level else 'bin/retained-runtime'
        members = {} if root_only else dict(self.fixture.members)
        if top_level:
            members.pop('bin/retained-runtime', None)
        members[runtime_member] = (bytes(prefix), 0o755)
        members.update(extra_members or {})
        archive_directories = {} if root_only else self.fixture.directories
        base = inputs / 'base.tar.gz'
        release._write_archive(base, members, archive_directories)
        inventory = inputs / 'base.inventory.json'
        described = artifact.describe(base)
        described['modes'] = release._mode_inventory(members)
        fixtures.document(inventory, described)
        recovery = inputs / 'recovery-inputs'
        recovery.write_bytes(b'explicit original recovery inputs; no reconstruction claim')
        selection = {
            'schema_version': 1, 'kind': 'foundation-appended-selection',
            'application': application,
            'source': fixtures.pin(source_archive, tree_sha256=identity['tree_sha256']), 'payload': None,
            'kernels': [{'id': self.entry['id'], 'archive': fixtures.pin(base),
                         'inventory': fixtures.pin(inventory), 'descriptor': fixtures.pin(descriptor_path),
                         'runtime_member': runtime_member, 'output': 'retained-linux.tar.gz',
                         'original_source': fixtures.pin(source_archive, tree_sha256=identity['tree_sha256']),
                         'recovery': [fixtures.pin(recovery)], 'evidence': []}]}
        selected = inputs / 'selection.json'
        fixtures.document(selected, selection)
        candidate = self.root / (name + ' candidate')
        with self.fixture.forbid_processes(), check._byte_operation():
            result = release.prepare_release(selected, candidate)
            subject = release.verify_composition_subject(candidate, result['candidate_sha256'])
        packed = self.root / (name + ' candidate.tar.gz')
        files, directories = {}, {}
        for path in candidate.rglob('*'):
            relative = path.relative_to(candidate).as_posix()
            mode = stat.S_IMODE(path.stat().st_mode)
            if path.is_dir():
                directories[relative] = mode
            else:
                files[relative] = (path.read_bytes(), mode)
        release._write_archive(packed, files, directories)
        return packed, result['candidate_sha256'], subject['composition']['artifacts'][0]

    def run_scenario(self, *, name='attempt', data=None, pin=None, execute=None, timeout=7):
        if data is not None:
            self.scenario_data = data
        fixtures.document(self.scenario, self.scenario_data)
        evidence, work = self.root / (name + ' evidence'), self.root / (name + ' work')
        evidence.mkdir()
        work.mkdir()
        self.passed = []
        self.context = {
            'directory': self.candidate, 'subject': self.subject, 'artifact': self.entry,
            'target': 'linux-x86_64', 'backend': 'terminal', 'evidence': evidence, 'work': work,
            'scenario': self.scenario, 'scenario_sha256': pin or archive.digest(self.scenario),
            'timeout': timeout, 'passed': self.passed,
            'helpers': {'extract': check._extract, 'tree': check._tree,
                        'execute': execute or self.observed_execution,
                        'environment': check._environment, 'new_json': check._new_json,
                        'junit': check._junit, 'uncertain': check._uncertain,
                        'host_target': check._host_target}}
        with self.fixture.forbid_processes(), check._byte_operation():
            return install.run(self.context)

    def observed_execution(self, argv, cwd, destination, environment, timeout):
        self.assertEqual(argv[1], '--phase')
        phase = argv[2]
        self.assertEqual(argv[3], '--state')
        state = Path(argv[4])
        self.assertEqual(argv[5], '--prefix')
        prefix = Path(argv[6])
        self.assertEqual(argv[7], 'literal $(no command); path with spaces')
        expected = self.prior_entry if phase == 'previous' else self.entry
        self.assertEqual(Path(argv[0]), prefix / expected['runtime_member'])
        self.assertNotEqual(state, prefix)
        self.assertNotIn(prefix, state.parents)
        self.assertNotIn('LD_LIBRARY_PATH', environment)
        self.assertEqual(timeout, self.context['timeout'])
        self.assertEqual(archive.digest(Path(argv[0])), expected['runtime_sha256'])
        self.assertEqual(Path(argv[0]).stat().st_mode & 0o777, 0o755)
        if phase == 'previous':
            self.write_state(state, self.before_bytes)
        elif phase == 'upgraded':
            self.assertEqual(self.state_files(state), self.before_bytes)
            self.write_state(state, self.after_bytes)
        call = self.scenario_data['phases'][phase][0]
        for filename, data in (('stdout.bin', call['stdout'].encode()),
                               ('stderr.bin', call['stderr'].encode()),
                               ('supervisor.log', b'owned structural execution capture\n')):
            (destination / filename).write_bytes(data)
        fixtures.document(destination / 'native.json', {'argv': argv, 'exit_code': call['exit_code']})
        self.executions.append({'phase': phase, 'prefix': prefix, 'state': state, 'cwd': Path(cwd),
                                'runtime_sha256': archive.digest(Path(argv[0])), 'destination': destination})
        return {'argv': argv, 'exit_code': call['exit_code'], 'stdout': call['stdout'].encode(),
                'stderr': call['stderr'].encode(), 'seconds': 0.001, 'process_tree_joined': True}

    @staticmethod
    def write_state(root, files):
        for name, data in files.items():
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)

    @staticmethod
    def state_files(root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    def test_real_archive_lifecycle_preserves_state_and_nested_foreign_file(self):
        details = self.run_scenario()
        self.assertEqual(self.passed, ['clean-install', 'upgrade', 'remove', 'preserved-application-state'])
        self.assertEqual(details['channels'], ['archive'])
        self.assertEqual(details['scenario_sha256'], archive.digest(self.scenario))
        self.assertEqual(set(details), {'channels', 'scenario_sha256', 'state_claim', 'installation'})
        self.assertEqual(details['state_claim'], 'persistent')
        installation = details['installation']
        self.assertIs(installation['state_migration'], True)
        for name, candidate, entry in (('current', self.subject['candidate_sha256'], self.entry),
                                       ('predecessor', self.prior_pin, self.prior_entry)):
            observed = installation[name]
            self.assertEqual(observed['candidate_sha256'], candidate)
            self.assertEqual(observed['artifact_id'], entry['id'])
            self.assertEqual(observed['archive_sha256'], entry['sha256'])
            self.assertEqual(observed['runtime_sha256'], entry['runtime_sha256'])
        self.assertEqual([call['phase'] for call in self.executions], ['clean', 'previous', 'upgraded'])
        clean, previous, upgraded = self.executions
        self.assertNotEqual(clean['prefix'], previous['prefix'])
        self.assertEqual(previous['prefix'], upgraded['prefix'])
        self.assertEqual(previous['state'], upgraded['state'])
        self.assertEqual(self.state_files(upgraded['state']), self.after_bytes)
        remaining = self.state_files(upgraded['prefix'])
        self.assertTrue(remaining, 'uninstall must preserve the nested foreign sentinel')
        self.assertFalse(set(remaining) & set(self.entry['files']))
        self.assertTrue(any('/' in name for name in remaining))
        evidence = self.context['evidence'] / 'install'
        self.assertEqual((evidence / 'scenario.json').read_bytes(), self.scenario.read_bytes())
        self.assertEqual(archive.digest(evidence / 'inputs' / self.prior.name), archive.digest(self.prior))
        self.assertEqual({name: item['sha256'] for name, item in installation['state_before']['files'].items()},
                         self.scenario_data['state']['before'])
        self.assertEqual({name: item['sha256'] for name, item in installation['state_after']['files'].items()},
                         self.scenario_data['state']['after'])
        self.assertEqual(json.loads((evidence / 'state-after-remove.json').read_bytes()),
                         installation['state_after'])
        for phase in ('clean', 'previous', 'upgraded'):
            calls = installation['phases'][phase]
            self.assertEqual([call['id'] for call in calls], [phase + '-state'])
            destination = next(call['destination'] for call in self.executions if call['phase'] == phase)
            self.assertEqual((destination / 'stdout.bin').read_bytes(), (phase + ' completed\n').encode())
            self.assertTrue((destination / 'before.json').is_file())
            self.assertTrue((destination / 'after.json').is_file())
            check.c.junit(evidence / phase / 'calls.junit.xml', [phase + '-state'])
        before_remove = json.loads((evidence / 'before-remove.json').read_bytes())
        after_remove = json.loads((evidence / 'after-remove.json').read_bytes())
        foreign = installation['foreign_sentinel_preserved']
        self.assertEqual(after_remove['files'], {foreign: before_remove['files'][foreign]})
        self.assertEqual(set(remaining), {foreign})
        self.assertEqual({name: item for name, item in before_remove['files'].items() if name != foreign},
                         {name: dict(item, mode=self.entry['modes'][name])
                          for name, item in self.entry['files'].items()})

    def test_wrong_scenario_binding_or_unlisted_input_never_executes(self):
        original = copy.deepcopy(self.scenario_data)
        cases = ('pin', 'candidate', 'artifact', 'target', 'backend', 'channel', 'input', 'predecessor-pin')
        for case in cases:
            data = copy.deepcopy(original)
            if case in ('candidate', 'artifact', 'target', 'backend'):
                key = {'candidate': 'candidate_sha256', 'artifact': 'artifact_id'}.get(case, case)
                data[key] = '0' * 64 if case == 'candidate' else 'unrelated'
            elif case == 'channel':
                data['channels'] = ['deb']
            elif case == 'input':
                data['inputs'][self.prior.name] = '0' * 64
            elif case == 'predecessor-pin':
                data['predecessor']['candidate_sha256'] = '0' * 64
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.run_scenario(name=case, data=data, pin='0' * 64 if case == 'pin' else None)
            self.assertEqual(self.executions, [])
            self.assertEqual(self.passed, [])

    def test_top_level_runtime_preserves_nested_foreign_data_with_or_without_owned_directories(self):
        original = copy.deepcopy(self.scenario_data)
        for root_only in (False, True):
            name = 'root-only' if root_only else 'root-with-owned-directories'
            current_name = name + '-current'
            _, pin, _ = self.predecessor(name=current_name, version='1.0.0', changed_runtime=False,
                                         top_level=True, root_only=root_only)
            self.candidate = self.root / (current_name + ' candidate')
            self.subject = release.verify_composition_subject(self.candidate, pin)
            self.entry = self.subject['composition']['artifacts'][0]
            self.prior, self.prior_pin, self.prior_entry = self.predecessor(
                name=name + '-previous', top_level=True, root_only=root_only)
            data = copy.deepcopy(original)
            data.update(candidate_sha256=pin, artifact_id=self.entry['id'])
            data['inputs'] = {self.prior.name: archive.digest(self.prior)}
            data['predecessor'] = {'archive': self.prior.name, 'candidate_sha256': self.prior_pin,
                                   'artifact_id': self.prior_entry['id']}
            self.executions.clear()
            with self.subTest(root_only=root_only):
                details = self.run_scenario(name=name, data=data)
                self.assertNotIn('/', self.entry['runtime_member'])
                self.assertEqual(bool(self.entry['directories']), not root_only)
                self.assertEqual(self.passed, ['clean-install', 'upgrade', 'remove',
                                               'preserved-application-state'])
                prefix = self.executions[-1]['prefix']
                foreign = details['installation']['foreign_sentinel_preserved']
                self.assertIn('/', foreign)
                self.assertEqual(set(self.state_files(prefix)), {foreign})
                self.assertEqual(self.state_files(self.executions[-1]['state']), self.after_bytes)
                evidence = self.context['evidence'] / 'install'
                before = json.loads((evidence / 'before-remove.json').read_bytes())
                after = json.loads((evidence / 'after-remove.json').read_bytes())
                self.assertEqual(after['files'], {foreign: before['files'][foreign]})
                self.assertEqual(after['directories'], {
                    parent.as_posix(): before['directories'][parent.as_posix()]
                    for parent in Path(foreign).parents if parent != Path('.')})
                if root_only:
                    self.assertNotIn(Path(foreign).parent.as_posix(), self.entry['directories'])
                else:
                    self.assertIn(Path(foreign).parent.as_posix(), self.entry['directories'])

    def test_predecessor_must_be_different_application_version_and_runtime(self):
        original = copy.deepcopy(self.scenario_data)
        for name, options in (('same-version', {'version': '1.0.0'}),
                              ('other-application', {'application_id': 'org.example.other'}),
                              ('self-reinstall', {'changed_runtime': False})):
            packed, pin, _ = self.predecessor(name=name, **options)
            data = copy.deepcopy(original)
            data['inputs'] = {packed.name: archive.digest(packed)}
            data['predecessor'].update(archive=packed.name, candidate_sha256=pin)
            with self.subTest(case=name), self.assertRaises(ValueError):
                self.run_scenario(name=name, data=data)
            self.assertEqual(self.executions, [])

    def test_phase_schema_rejects_commands_duplicates_and_invalid_state(self):
        original = copy.deepcopy(self.scenario_data)
        for case in ('empty', 'command', 'duplicate',
                     'one-empty-state-before', 'one-empty-state-after', 'state-traversal'):
            data = copy.deepcopy(original)
            call = data['phases']['clean'][0]
            if case == 'empty':
                data['phases']['clean'] = []
            elif case == 'command':
                call['command'] = ['/bin/true']
            elif case == 'duplicate':
                data['phases']['clean'].append(copy.deepcopy(call))
            elif case.startswith('one-empty-state-'):
                data['state'][case.removeprefix('one-empty-state-')] = {}
                self.assertTrue(data['state']['before'] or data['state']['after'])
            else:
                data['state']['before'] = {'../escaped-state': '0' * 64}
            self.executions.clear()
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    self.run_scenario(name=case, data=data)
                self.assertEqual(self.executions, [])

    def test_stateless_lifecycle_keeps_empty_state_and_preserves_foreign_identity(self):
        self.before_bytes, self.after_bytes = {}, {}
        self.scenario_data['state'] = {'before': {}, 'after': {}}
        details = self.run_scenario()
        self.assertEqual(details['state_claim'], 'stateless')
        installation = details['installation']
        self.assertIs(installation['state_migration'], False)
        self.assertEqual([call['phase'] for call in self.executions], ['clean', 'previous', 'upgraded'])
        self.assertEqual(self.passed, ['clean-install', 'upgrade', 'remove', 'preserved-application-state'])
        empty = {'files': {}, 'directories': {}}
        self.assertEqual(installation['state_before'], empty)
        self.assertEqual(installation['state_after'], empty)
        evidence = self.context['evidence'] / 'install'
        for name in ('clean-state.json', 'state-before-upgrade.json', 'state-after-upgrade.json',
                     'state-after-remove.json'):
            self.assertEqual(json.loads((evidence / name).read_bytes()), empty)
        for call in self.executions:
            self.assertEqual(check._tree(call['state']), empty)
        original = json.loads((evidence / 'foreign-before-upgrade.json').read_bytes())
        self.assertEqual(json.loads((evidence / 'foreign-after-upgrade.json').read_bytes()), original)
        prefix = self.executions[-1]['prefix']
        foreign = prefix / original['path']
        final = foreign.stat()
        self.assertGreater(final.st_size, 0)
        self.assertEqual((final.st_dev, final.st_ino, final.st_size, stat.S_IMODE(final.st_mode)),
                         (original['device'], original['inode'], original['size'], original['mode']))
        self.assertEqual(archive.digest(foreign), original['sha256'])
        self.assertEqual(set(check._tree(prefix)['files']), {original['path']})
        self.assertEqual(check._tree(prefix)['directories'], original['directories'])

    def test_stateless_runtime_cannot_create_unexpected_files_or_empty_directories(self):
        self.before_bytes, self.after_bytes = {}, {}
        original = copy.deepcopy(self.scenario_data)
        original['state'] = {'before': {}, 'after': {}}
        for phase in ('previous', 'upgraded'):
            for kind in ('file', 'empty-directory'):
                def unexpected_state(*args, phase=phase, kind=kind):
                    result = self.observed_execution(*args)
                    if args[0][2] == phase:
                        unexpected = Path(args[0][4]) / 'unexpected application state'
                        if kind == 'file':
                            unexpected.write_bytes(b'not declared by the stateless scenario')
                        else:
                            unexpected.mkdir()
                    return result
                self.executions.clear()
                with self.subTest(phase=phase, kind=kind):
                    with self.assertRaisesRegex(ValueError, 'state'):
                        self.run_scenario(name='stateless-' + phase + '-' + kind,
                                          data=copy.deepcopy(original), execute=unexpected_state)
                    expected = ['clean', 'previous'] + (['upgraded'] if phase == 'upgraded' else [])
                    self.assertEqual([call['phase'] for call in self.executions], expected)
                    self.assertEqual(self.passed, ['clean-install'])
                    evidence = self.context['evidence'] / 'install'
                    self.assertFalse((evidence / 'before-remove.json').exists())
                    self.assertFalse((evidence / 'after-remove.json').exists())
                    self.assertFalse((evidence / 'state-after-upgrade.json').exists())

    def test_other_braces_and_json_remain_literal_runtime_arguments(self):
        # Only the two documented tokens expand. Other braces are valid data,
        # including JSON and text resembling an incomplete placeholder.
        literals = ['{command}', '{state', '{"request":7,"text":"$(literal); spaces"}']
        for calls in self.scenario_data['phases'].values():
            calls[0]['argv'].extend(literals)
        def literal_arguments(*args):
            self.assertEqual(args[0][-3:], literals)
            return self.observed_execution(*args)
        details = self.run_scenario(execute=literal_arguments)
        self.assertEqual([call['phase'] for call in self.executions], ['clean', 'previous', 'upgraded'])
        for calls in details['installation']['phases'].values():
            self.assertEqual(calls[0]['argv'][-3:], literals)
        self.assertEqual(self.passed, ['clean-install', 'upgrade', 'remove', 'preserved-application-state'])

    def test_metadata_like_call_ids_preserve_separate_phase_evidence(self):
        identifiers = {'clean': 'before.json', 'previous': 'after.json', 'upgraded': 'calls.junit.xml'}
        for phase, identity in identifiers.items():
            self.scenario_data['phases'][phase][0]['id'] = identity
        details = self.run_scenario()
        evidence = self.context['evidence'] / 'install'
        for phase, identity in identifiers.items():
            phase_root = evidence / phase
            call_root = phase_root / 'calls' / identity
            self.assertTrue((phase_root / 'before.json').is_file())
            self.assertTrue((phase_root / 'after.json').is_file())
            self.assertTrue((call_root / 'before.json').is_file())
            self.assertTrue((call_root / 'after.json').is_file())
            self.assertEqual((call_root / 'stdout.bin').read_bytes(), (phase + ' completed\n').encode())
            self.assertEqual(details['installation']['phases'][phase][0]['id'], identity)
            check.c.junit(phase_root / 'calls.junit.xml', [identity])
        self.assertEqual(self.passed, ['clean-install', 'upgrade', 'remove', 'preserved-application-state'])

    def test_exact_phase_exit_output_and_argv_are_required(self):
        for field, value in (('exit_code', 3), ('stdout', b'other output'), ('stderr', b'other error'),
                             ('argv', ['/unrelated/program'])):
            def wrong(*args, field=field, value=value):
                result = self.observed_execution(*args)
                result[field] = value
                return result
            self.executions.clear()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_scenario(name=field, execute=wrong)
            self.assertEqual(len(self.executions), 1)
            self.assertEqual(self.passed, [])

    def test_unconfirmed_process_tree_preserves_work_without_later_evidence(self):
        for case in ('false', 'missing', 'non-dict'):
            def unconfirmed(*args, case=case):
                result = self.observed_execution(*args)
                if case == 'false':
                    result['process_tree_joined'] = False
                    # Uncertain process ownership takes precedence even over a
                    # changed prefix, which the supervisor must retain intact.
                    prefix = Path(args[0][6])
                    retained = prefix.with_name(prefix.name + ' retained original')
                    prefix.rename(retained)
                    prefix.symlink_to(retained, target_is_directory=True)
                elif case == 'missing':
                    result.pop('process_tree_joined')
                    (args[2] / 'stdout.bin').unlink()
                else:
                    return None
                return result
            self.executions.clear()
            with self.subTest(case=case):
                with self.assertRaises(check.ProcessTreeError) as raised:
                    self.run_scenario(name='unconfirmed-' + case, execute=unconfirmed)
                self.assertTrue(check._uncertain(raised.exception))
                self.assertEqual(len(self.executions), 1)
                self.assertEqual(self.passed, [])
                self.assertTrue(self.context['work'].is_dir())
                evidence = self.context['evidence'] / 'install'
                self.assertFalse((evidence / 'clean/calls.junit.xml').exists())
                self.assertFalse((self.executions[0]['destination'] / 'after.json').exists())
                self.assertFalse((evidence / 'previous').exists())
                self.assertFalse((evidence / 'upgraded').exists())

    def test_current_owned_filename_collision_cannot_overwrite_prior_foreign_data(self):
        foreign_name = 'bin/foreign uninstall sentinel'
        owned_bytes = b'current archive owns this exact path\n'
        name = 'foreign-collision-current'
        _, pin, _ = self.predecessor(name=name, version='1.0.0', changed_runtime=False,
                                     extra_members={foreign_name: (owned_bytes, 0o640)})
        self.candidate = self.root / (name + ' candidate')
        self.subject = release.verify_composition_subject(self.candidate, pin)
        self.entry = self.subject['composition']['artifacts'][0]
        data = copy.deepcopy(self.scenario_data)
        data.update(candidate_sha256=pin, artifact_id=self.entry['id'])
        with self.assertRaisesRegex(ValueError, 'collid|collision'):
            self.run_scenario(data=data)
        self.assertEqual([call['phase'] for call in self.executions], ['clean', 'previous'])
        self.assertEqual(self.passed, ['clean-install'])
        clean, previous = self.executions
        self.assertEqual((clean['prefix'] / foreign_name).read_bytes(), owned_bytes)
        self.assertNotEqual((previous['prefix'] / foreign_name).read_bytes(), owned_bytes)
        self.assertEqual(archive.digest(clean['prefix'] / foreign_name),
                         self.entry['files'][foreign_name]['sha256'])
        self.assertEqual(release.verify_composition_subject(self.candidate, pin), self.subject)

    def test_foreign_file_identity_and_missing_ancestor_modes_survive_upgrade_and_remove(self):
        # The new archive has no bin directory. The prior foreign file must keep
        # its original identity and parent permissions through the replacement.
        name = 'foreign-migration-current'
        _, pin, _ = self.predecessor(name=name, version='1.0.0', changed_runtime=False,
                                     top_level=True, root_only=True)
        self.candidate = self.root / (name + ' candidate')
        self.subject = release.verify_composition_subject(self.candidate, pin)
        self.entry = self.subject['composition']['artifacts'][0]
        data = copy.deepcopy(self.scenario_data)
        data.update(candidate_sha256=pin, artifact_id=self.entry['id'])
        captured = {}
        def observe_migrated_foreign(*args):
            if args[0][2] == 'upgraded':
                evidence = self.context['evidence'] / 'install'
                original = json.loads((evidence / 'foreign-before-upgrade.json').read_bytes())
                prefix = Path(args[0][6])
                foreign = prefix / original['path']
                state = foreign.stat()
                observed = {'path': original['path'], 'sha256': archive.digest(foreign),
                            'size': state.st_size, 'mode': stat.S_IMODE(state.st_mode),
                            'device': state.st_dev, 'inode': state.st_ino,
                            'directories': {parent.as_posix(): stat.S_IMODE((prefix / parent).stat().st_mode)
                                            for parent in Path(original['path']).parents if parent != Path('.')}}
                self.assertEqual(observed, original)
                self.assertEqual(json.loads((evidence / 'foreign-after-upgrade.json').read_bytes()), original)
                self.assertTrue(original['path'].startswith('bin/'))
                self.assertEqual(original['directories'], {'bin': self.prior_entry['directories']['bin']})
                self.assertNotIn('bin', self.entry['directories'])
                captured.update(original)
            return self.observed_execution(*args)
        details = self.run_scenario(data=data, execute=observe_migrated_foreign)
        self.assertTrue(captured, 'the upgraded runtime must observe the already migrated foreign file')
        prefix = self.executions[-1]['prefix']
        foreign = prefix / captured['path']
        final = foreign.stat()
        self.assertEqual((final.st_dev, final.st_ino, final.st_size, stat.S_IMODE(final.st_mode)),
                         (captured['device'], captured['inode'], captured['size'], captured['mode']))
        self.assertEqual(archive.digest(foreign), captured['sha256'])
        self.assertEqual(check._tree(prefix)['directories'], captured['directories'])
        self.assertEqual(details['installation']['foreign_sentinel_preserved'], captured['path'])
        self.assertEqual(self.state_files(self.executions[-1]['state']), self.after_bytes)
        self.assertEqual(self.passed, ['clean-install', 'upgrade', 'remove', 'preserved-application-state'])

    def test_identical_foreign_replacement_stops_before_upgrade_claim_or_owned_removal(self):
        def replace_foreign(*args):
            result = self.observed_execution(*args)
            if args[0][2] == 'upgraded':
                evidence = self.context['evidence'] / 'install'
                original = json.loads((evidence / 'foreign-before-upgrade.json').read_bytes())
                prefix = Path(args[0][6])
                foreign = prefix / original['path']
                replacement = foreign.with_name(foreign.name + ' replacement')
                replacement.write_bytes(foreign.read_bytes())
                replacement.chmod(original['mode'])
                self.assertNotEqual(replacement.stat().st_ino, original['inode'])
                replacement.replace(foreign)
                self.assertEqual(archive.digest(foreign), original['sha256'])
                self.assertEqual(stat.S_IMODE(foreign.stat().st_mode), original['mode'])
                self.assertNotEqual(foreign.stat().st_ino, original['inode'])
            return result
        with self.assertRaises(ValueError):
            self.run_scenario(execute=replace_foreign)
        self.assertEqual([call['phase'] for call in self.executions], ['clean', 'previous', 'upgraded'])
        self.assertEqual(self.passed, ['clean-install'])
        prefix = self.executions[-1]['prefix']
        observed = check._tree(prefix)
        for name, identity in self.entry['files'].items():
            self.assertEqual(observed['files'][name], dict(identity, mode=self.entry['modes'][name]))
        evidence = self.context['evidence'] / 'install'
        self.assertTrue((evidence / 'upgraded/after.json').is_file())
        self.assertFalse((evidence / 'before-remove.json').exists())
        self.assertFalse((evidence / 'after-remove.json').exists())

    def test_owned_file_mutation_and_symlink_abort_before_next_phase(self):
        for kind in ('bytes', 'link'):
            def mutate(*args, kind=kind):
                result = self.observed_execution(*args)
                runtime = Path(args[0][0])
                if kind == 'bytes':
                    runtime.write_bytes(b'modified owned runtime')
                else:
                    runtime.unlink()
                    runtime.symlink_to(self.candidate / self.entry['archive'])
                return result
            self.executions.clear()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.run_scenario(name='owned-' + kind, execute=mutate)
            self.assertEqual(len(self.executions), 1)
            self.assertEqual(self.passed, [])

    def test_root_replacement_with_identical_contents_stops_before_following_call(self):
        original = copy.deepcopy(self.scenario_data)
        following = copy.deepcopy(original['phases']['previous'][0])
        following['id'] = 'must-not-run-after-root-replacement'
        original['phases']['previous'].append(following)
        for scope in ('prefix', 'state'):
            for replacement in ('symlink', 'ordinary-copy'):
                def replace_root(*args, scope=scope, replacement=replacement):
                    self.assertFalse(any(call['phase'] == 'previous' for call in self.executions),
                                     'the following call must not execute after root replacement')
                    result = self.observed_execution(*args)
                    if args[0][2] == 'previous':
                        root = Path(args[0][6 if scope == 'prefix' else 4])
                        retained = root.with_name(root.name + ' original directory')
                        root.rename(retained)
                        if replacement == 'symlink':
                            root.symlink_to(retained, target_is_directory=True)
                        else:
                            shutil.copytree(retained, root)
                            self.assertNotEqual(root.stat().st_ino, retained.stat().st_ino)
                        self.assertEqual(self.state_files(root), self.state_files(retained))
                    return result
                self.executions.clear()
                with self.subTest(scope=scope, replacement=replacement):
                    with self.assertRaises(ValueError):
                        self.run_scenario(name=scope + '-' + replacement, data=copy.deepcopy(original),
                                          execute=replace_root)
                    self.assertEqual([call['phase'] for call in self.executions], ['clean', 'previous'])
                    self.assertEqual(self.passed, ['clean-install'])
                    self.assertFalse((self.context['evidence'] /
                                      'install/previous/calls' / following['id']).exists())

    def test_state_snapshot_is_complete_and_rejects_links(self):
        for kind in ('missing', 'unlisted', 'link'):
            def mutate(*args, kind=kind):
                result = self.observed_execution(*args)
                if args[0][2] == 'previous':
                    state = Path(args[0][4])
                    if kind == 'missing':
                        (state / 'settings/user.txt').unlink()
                    elif kind == 'unlisted':
                        (state / 'unlisted.txt').write_bytes(b'not in expected complete snapshot')
                    else:
                        (state / 'settings/user.txt').unlink()
                        (state / 'settings/user.txt').symlink_to(self.scenario)
                return result
            self.executions.clear()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.run_scenario(name='state-' + kind, execute=mutate)
            self.assertEqual([call['phase'] for call in self.executions], ['clean', 'previous'])
            self.assertEqual(self.passed, ['clean-install'])

    def test_timeout_stops_execution_and_never_records_completion(self):
        def timeout(argv, cwd, destination, environment, limit):
            self.assertEqual(limit, 0.125)
            raise ValueError('retained runtime exceeded its time/output limit')
        with self.assertRaisesRegex(ValueError, 'time/output limit'):
            self.run_scenario(execute=timeout, timeout=0.125)
        self.assertEqual(self.passed, [])

    def test_changed_frozen_scenario_is_rejected_after_calls(self):
        def change(*args):
            result = self.observed_execution(*args)
            if args[0][2] == 'upgraded':
                self.scenario.write_bytes(b'{}')
            return result
        with self.assertRaises(ValueError):
            self.run_scenario(execute=change)
        self.assertNotEqual(self.passed, ['clean-install', 'upgrade', 'remove', 'preserved-application-state'])


@unittest.skipUnless(sys.platform.startswith('linux'), 'initial browser adapter selects Linux Firefox')
class HTMLInstallTests(unittest.TestCase):
    def setUp(self):
        self.fixture = browser_fixtures.BrowserCheckTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.candidate, self.subject, self.entry = self.fixture.candidate, self.fixture.subject, self.fixture.product
        self.prior_archive, self.prior_subject = self.predecessor()
        self.prior_entry = self.prior_subject['composition']['artifacts'][0]
        self.scenario = self.root / 'HTML install scenario.json'
        self.nested = {}
        for phase in ('clean', 'previous', 'upgraded'):
            selected = self.prior_subject if phase == 'previous' else self.subject
            value = copy.deepcopy(self.fixture.scenario_data)
            value['candidate_sha256'] = selected['candidate_sha256']
            value['artifact_id'] = selected['composition']['artifacts'][0]['id']
            for step in value['steps']:
                step['id'] = phase + '-' + step['id']
            path = self.root / ('browser ' + phase + ' scenario.json')
            fixtures.document(path, value)
            self.nested[phase] = path
        self.scenario_data = {
            'schema_version': 1, 'kind': 'foundation-appended-install-scenario',
            'candidate_sha256': self.subject['candidate_sha256'], 'artifact_id': self.entry['id'],
            'target': 'web-wasm32', 'backend': 'web', 'channels': ['archive'],
            'inputs': {self.prior_archive.name: archive.digest(self.prior_archive),
                       **{path.name: archive.digest(path) for path in self.nested.values()}},
            'predecessor': {'archive': self.prior_archive.name,
                            'candidate_sha256': self.prior_subject['candidate_sha256'],
                            'artifact_id': self.prior_entry['id']},
            'phases': {phase: {'scenario': path.name} for phase, path in self.nested.items()},
            'state': {'before': {}, 'after': {}}}
        self.browser_calls = []

    def predecessor(self):
        inputs = self.root / 'previous HTML inputs'
        shutil.copytree(self.root / 'inputs', inputs)
        source = self.root / 'previous HTML source'
        shutil.copytree(self.root / 'source', source)
        configuration = json.loads((source / project.CONFIG_NAME).read_bytes())
        application = dict(configuration['application'], version='0.9.0')
        configuration['application'] = application
        fixtures.document(source / project.CONFIG_NAME, configuration)
        source_archive = inputs / 'previous-source.tar.gz'
        identity = source_identity.archive_source(source, source_archive)
        package = container.build_package({'binary/application.wasm': browser_fixtures.module()}, application,
            binary_entry='binary/application.wasm', binary_profile='foundation-guest-v1',
            requires={'abi': {'major': 1, 'minor': 0}, 'services': ['foundation.view'],
                      'capabilities': ['foundation.view.v1']},
            identities={'source_tree': identity['tree_sha256']})
        payload = inputs / 'previous.sfapp'
        payload.write_bytes(container.encode_package(package))
        selection = json.loads((inputs / 'selection.json').read_bytes())
        selection.update(application=application,
                         source=fixtures.pin(source_archive, tree_sha256=identity['tree_sha256']),
                         payload=fixtures.pin(payload))
        selected = inputs / 'previous-selection.json'
        fixtures.document(selected, selection)
        candidate = self.root / 'previous HTML candidate'
        with self.fixture.forbid_processes(), check._byte_operation():
            result = release.prepare_release(selected, candidate)
            subject = release.verify_composition_subject(candidate, result['candidate_sha256'])
        files, directories = {}, {}
        for path in candidate.rglob('*'):
            relative, mode = path.relative_to(candidate).as_posix(), stat.S_IMODE(path.stat().st_mode)
            if path.is_dir():
                directories[relative] = mode
            else:
                files[relative] = (path.read_bytes(), mode)
        packed = self.root / 'previous HTML candidate.tar.gz'
        release._write_archive(packed, files, directories)
        return packed, subject

    def run_scenario(self, *, name='HTML attempt', data=None, execute=None):
        fixtures.document(self.scenario, self.scenario_data if data is None else data)
        evidence, work = self.root / (name + ' evidence'), self.root / (name + ' work')
        evidence.mkdir()
        work.mkdir()
        self.passed = []
        self.context = {
            'directory': self.candidate, 'subject': self.subject, 'artifact': self.entry,
            'target': 'web-wasm32', 'backend': 'web', 'evidence': evidence, 'work': work,
            'scenario': self.scenario, 'scenario_sha256': archive.digest(self.scenario),
            'timeout': 20, 'passed': self.passed,
            'execution_context': copy.deepcopy(self.fixture.execution_context),
            'checker_sources': {path: archive.digest(ROOT / path) for path in browser.CHECKER_SOURCES},
            'helpers': {'extract': check._extract, 'tree': check._tree, 'execute': check._execute_runtime,
                        'environment': check._environment, 'new_json': check._new_json,
                        'junit': check._junit, 'uncertain': check._uncertain,
                        'host_target': check._host_target, 'browser': browser.run}}
        with self.fixture.forbid_processes(), check._byte_operation(), \
                patch.object(browser, '_execute_browser', side_effect=execute or self.observed_browser):
            return install.run(self.context)

    def observed_browser(self, runtime, scenario, evidence, work, timeout, environment):
        phase = scenario['steps'][0]['id'].split('-', 1)[0]
        expected_subject = self.prior_subject if phase == 'previous' else self.subject
        expected = self.prior_entry if phase == 'previous' else self.entry
        prefix = runtime.parents[1]
        self.assertTrue(prefix.is_relative_to(self.context['work'] / 'install'))
        self.assertNotIn('relocated browser archive with spaces', str(runtime))
        self.assertEqual(runtime, prefix / expected['runtime_member'])
        self.assertEqual(archive.digest(runtime), expected['runtime_sha256'])
        self.assertEqual(runtime.stat().st_mode & 0o777, 0o644)
        self.assertEqual(scenario['candidate_sha256'], expected_subject['candidate_sha256'])
        self.assertEqual(scenario['artifact_id'], expected['id'])
        parsed = container.parse_artifact(runtime.read_bytes(), self.fixture.descriptor, expected_mode='binary')
        self.assertEqual(parsed.prefix, self.fixture.prefix)
        self.assertEqual(parsed.package.file_bytes('binary/application.wasm'), browser_fixtures.module())
        self.assertEqual(parsed.package.index['application'], expected_subject['composition']['application'])
        self.assertEqual(timeout, 20)
        self.assertNotIn('LD_LIBRARY_PATH', environment)
        if phase == 'upgraded':
            original = json.loads((self.context['evidence'] / 'install/foreign-before-upgrade.json').read_bytes())
            foreign = prefix / original['path']
            state = foreign.stat()
            self.assertEqual((state.st_dev, state.st_ino, state.st_size, stat.S_IMODE(state.st_mode)),
                             (original['device'], original['inode'], original['size'], original['mode']))
            self.assertEqual(archive.digest(foreign), original['sha256'])
        def chunk(kind, value):
            return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))
        capture = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
                   chunk(b'IDAT', zlib.compress(b'\0\0\0\0')) + chunk(b'IEND', b''))
        with (evidence / 'capture.png').open('xb') as stream:
            stream.write(capture)
        self.browser_calls.append({'phase': phase, 'runtime': runtime, 'prefix': prefix,
                                   'uri': runtime.resolve().as_uri(), 'evidence': evidence})
        return {'engine': 'firefox',
            'capabilities': {'browserName': 'firefox', 'browserVersion': '153.5.0',
                             'moz:buildID': '20261006170429', 'moz:processID': 4242},
            'actual_image': {'pid': 4242, 'path': str(self.fixture.executable),
                             'sha256': archive.digest(self.fixture.executable), 'owned_ancestry': [4242, 4243]},
            'offline': {'enabled': True, 'positive_control': 'NS_ERROR_OFFLINE'},
            'quit': {'acknowledged': True, 'normal_exit': True}, 'process_tree_joined': True,
            'direct_file_uri': runtime.resolve().as_uri(), 'runtime_sha256': archive.digest(runtime),
            'executed_tests': [step['id'] for step in scenario['steps']],
            'observations': [{'id': step['id'], 'action': step['action'], 'widget': copy.deepcopy(step['widget']),
                              'passed': True} for step in scenario['steps']],
            'application_result_changed': True, 'capture_sha256': container.digest(capture),
            'frame_policy': [{'sandbox': 'allow-scripts', 'srcdoc': True}]}

    def test_html_stateless_lifecycle_uses_installed_browser_paths_and_preserves_foreign_identity(self):
        details = self.run_scenario()
        self.assertEqual(details['state_claim'], 'stateless')
        self.assertIs(details['installation']['state_migration'], False)
        self.assertEqual(self.passed, ['clean-install', 'upgrade', 'remove', 'preserved-application-state'])
        self.assertEqual([call['phase'] for call in self.browser_calls], ['clean', 'previous', 'upgraded'])
        clean, previous, upgraded = self.browser_calls
        self.assertNotEqual(clean['prefix'], previous['prefix'])
        self.assertEqual(previous['prefix'], upgraded['prefix'])
        self.assertEqual(previous['uri'], upgraded['uri'])
        self.assertNotEqual(self.entry['runtime_sha256'], self.prior_entry['runtime_sha256'])
        self.assertNotEqual(self.subject['candidate_sha256'], self.prior_subject['candidate_sha256'])
        evidence = self.context['evidence'] / 'install'
        original = json.loads((evidence / 'foreign-before-upgrade.json').read_bytes())
        self.assertEqual(json.loads((evidence / 'foreign-after-upgrade.json').read_bytes()), original)
        final = upgraded['prefix'] / original['path']
        physical = final.stat()
        self.assertEqual((physical.st_dev, physical.st_ino, physical.st_size, stat.S_IMODE(physical.st_mode)),
                         (original['device'], original['inode'], original['size'], original['mode']))
        self.assertEqual(archive.digest(final), original['sha256'])
        self.assertEqual(set(check._tree(upgraded['prefix'])['files']), {original['path']})
        self.assertFalse(set(self.entry['files']) & set(check._tree(upgraded['prefix'])['files']))
        self.assertEqual(check._tree(upgraded['prefix'])['directories'], original['directories'])
        for call in self.browser_calls:
            observed = json.loads((call['evidence'] / 'observation.json').read_bytes())
            self.assertEqual(observed['direct_file_uri'], call['uri'])
            self.assertEqual(observed['status'], 'passed')
            self.assertEqual(observed['browser_version'], observed['capabilities']['browserVersion'])
            self.assertEqual(details['installation']['phases'][call['phase']]['checker_sources'],
                             self.context['checker_sources'])
            nested = json.loads(self.nested[call['phase']].read_bytes())
            junit = call['evidence'] / 'scenario.junit.xml'
            returned_junit = details['installation']['phases'][call['phase']]['junit']
            self.assertEqual(self.context['evidence'] / returned_junit, junit)
            check.c.junit(junit, [step['id'] for step in nested['steps']])
        for path in ('clean-state.json', 'state-before-upgrade.json', 'state-after-upgrade.json',
                     'state-after-remove.json'):
            self.assertEqual(json.loads((evidence / path).read_bytes()), {'files': {}, 'directories': {}})

    def test_html_install_rejects_unbound_browser_scenarios_native_calls_and_persistent_state(self):
        original_nested = {phase: path.read_bytes() for phase, path in self.nested.items()}
        for case in ('wrong-candidate', 'wrong-previous-candidate', 'wrong-artifact', 'unlisted-scenario', 'wrong-pin',
                     'native-calls', 'native-argv', 'persistent-state'):
            for phase, content in original_nested.items():
                self.nested[phase].write_bytes(content)
            data = copy.deepcopy(self.scenario_data)
            if case in ('wrong-candidate', 'wrong-previous-candidate', 'wrong-artifact'):
                phase = 'previous' if case == 'wrong-previous-candidate' else 'clean'
                nested = json.loads(original_nested[phase])
                if case == 'wrong-artifact':
                    nested['artifact_id'] = '0' * 64
                else:
                    nested['candidate_sha256'] = (self.subject['candidate_sha256']
                                                   if phase == 'previous' else '0' * 64)
                fixtures.document(self.nested[phase], nested)
                data['inputs'][self.nested[phase].name] = archive.digest(self.nested[phase])
            elif case == 'unlisted-scenario':
                data['inputs'].pop(self.nested['clean'].name)
            elif case == 'wrong-pin':
                data['inputs'][self.nested['clean'].name] = '0' * 64
            elif case == 'native-calls':
                data['phases']['clean'] = [{'id': 'bypass-browser', 'argv': ['/bin/true'],
                                             'exit_code': 0, 'stdout': '', 'stderr': ''}]
            elif case == 'native-argv':
                data['phases']['clean']['argv'] = ['/bin/true']
            else:
                data['state'] = {'before': {'user.txt': '0' * 64}, 'after': {'user.txt': '1' * 64}}
            self.browser_calls.clear()
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    self.run_scenario(name=case, data=data)
                self.assertEqual(self.browser_calls, [])
                self.assertEqual(self.passed, [])

    def test_html_install_propagates_browser_output_offline_quit_join_and_inventory_failures(self):
        for case in ('output', 'offline', 'quit', 'join', 'inventory'):
            def failed(*args, case=case):
                result = self.observed_browser(*args)
                if case == 'output':
                    result['application_result_changed'] = False
                elif case == 'offline':
                    result['offline']['enabled'] = False
                elif case == 'quit':
                    result['quit']['normal_exit'] = False
                elif case == 'join':
                    result['process_tree_joined'] = False
                else:
                    (args[0].parents[1] / 'share/unchanged.bin').write_bytes(b'changed installed dependency')
                return result
            self.browser_calls.clear()
            with self.subTest(case=case):
                expected_error = check.ProcessTreeError if case == 'join' else ValueError
                with self.assertRaises(expected_error) as raised:
                    self.run_scenario(name='browser-' + case, execute=failed)
                if case == 'join':
                    self.assertTrue(check._uncertain(raised.exception))
                self.assertEqual([call['phase'] for call in self.browser_calls], ['clean'])
                self.assertEqual(self.passed, [])
                evidence = self.context['evidence'] / 'install'
                self.assertFalse((evidence / 'before-remove.json').exists())
                self.assertFalse((evidence / 'after-remove.json').exists())


@unittest.skipUnless(sys.platform.startswith('linux'), 'Chromium physical adapter selects Linux')
class ChromiumHTMLInstallTests(HTMLInstallTests):
    """Reuse every HTML lifecycle assertion through the Chromium proof contract."""

    def setUp(self):
        super().setUp()
        self.fixture.executable = self.root / 'chromium structural executable'
        self.driver = self.root / 'chromedriver structural executable'
        for path, label in ((self.fixture.executable, b'browser'), (self.driver, b'driver')):
            path.write_bytes(b'\x7fELF\x02\x01\x01' + b'\0' * 13 + b'structural ' + label + b'; never executed\n')
            path.chmod(0o755)
        for path in self.nested.values():
            scenario = json.loads(path.read_bytes())
            scenario['browser'] = {'engine': 'chromium', 'executable': str(self.fixture.executable),
                'sha256': archive.digest(self.fixture.executable),
                'driver': {'executable': str(self.driver), 'sha256': archive.digest(self.driver)}}
            fixtures.document(path, scenario)
            self.scenario_data['inputs'][path.name] = archive.digest(path)

    def observed_browser(self, *args):
        result = super().observed_browser(*args)
        result.update(engine='chromium',
            capabilities={'browserName': 'chrome', 'browserVersion': '130.0.1.2', 'goog:processID': 4242,
                          'chrome': {'chromedriverVersion': '130.0.1.7 (fixture)'}},
            offline=browser_fixtures.chromium_offline_fixture(),
            actual_driver={'pid': 4243, 'path': str(self.driver), 'sha256': archive.digest(self.driver),
                           'start_time': '124', 'owned_ancestry': [4243, 4244]})
        result['actual_image'].update(start_time='123', owned_ancestry=[4242, 4243, 4244])
        return result

    def test_chromium_install_checks_trusted_adapter_offline_engine_and_quit_records(self):
        original = browser.run
        for case in ('unknown-engine', 'firefox-offline', 'missing-worker', 'online-after', 'listener', 'quit'):
            def incomplete(context, case=case):
                result = original(context)
                observed = result['browser']
                if case == 'unknown-engine':
                    observed['engine'] = 'unknown'
                elif case == 'firefox-offline':
                    observed['offline'] = {'enabled': True, 'positive_control': 'NS_ERROR_OFFLINE'}
                elif case == 'missing-worker':
                    observed['offline']['before']['offline'].pop('worker')
                elif case == 'online-after':
                    observed['offline']['after']['offline']['frame']['response'] = True
                elif case == 'listener':
                    observed['offline']['listener_joined'] = False
                else:
                    observed['quit']['normal_exit'] = False
                return result
            self.browser_calls.clear()
            with self.subTest(case=case), patch.object(browser, 'run', side_effect=incomplete), \
                    self.assertRaisesRegex(ValueError, 'installed browser did not complete'):
                self.run_scenario(name='chromium-trusted-' + case)
            self.assertEqual([call['phase'] for call in self.browser_calls], ['clean'])
            self.assertEqual(self.passed, [])
            self.assertFalse((self.context['evidence'] / 'install/before-remove.json').exists())

    def test_chromium_install_stops_at_each_incomplete_or_mutated_phase(self):
        for phase in ('clean', 'previous', 'upgraded'):
            for case in ('offline', 'quit', 'join', 'inventory'):
                def failed(*args, phase=phase, case=case):
                    result = self.observed_browser(*args)
                    if self.browser_calls[-1]['phase'] != phase:
                        return result
                    if case == 'offline':
                        result['offline']['after']['offline']['worker']['response'] = True
                    elif case == 'quit':
                        result['quit']['acknowledged'] = False
                    elif case == 'join':
                        result['process_tree_joined'] = False
                    else:
                        (args[0].parents[1] / 'share/unchanged.bin').write_bytes(b'changed installed dependency')
                    return result
                self.browser_calls.clear()
                with self.subTest(phase=phase, case=case):
                    expected_error = check.ProcessTreeError if case == 'join' else ValueError
                    with self.assertRaises(expected_error) as raised:
                        self.run_scenario(name='chromium-' + phase + '-' + case, execute=failed)
                    if case == 'join':
                        self.assertTrue(check._uncertain(raised.exception))
                    self.assertEqual([call['phase'] for call in self.browser_calls],
                                     list(install.PHASES[:install.PHASES.index(phase) + 1]))
                    self.assertEqual(self.passed, [] if phase == 'clean' else ['clean-install'])
                    evidence = self.context['evidence'] / 'install'
                    self.assertFalse((evidence / 'before-remove.json').exists())
                    self.assertFalse((evidence / 'after-remove.json').exists())
                    if case == 'join':
                        self.assertFalse((self.browser_calls[-1]['evidence'] / 'observation.json').exists())

    def test_chromium_install_rechecks_selected_driver_during_every_phase(self):
        original = self.driver.read_bytes()
        for phase in install.PHASES:
            def changed(*args, phase=phase):
                result = self.observed_browser(*args)
                if self.browser_calls[-1]['phase'] == phase:
                    self.driver.write_bytes(original + b'changed during installed browser execution\n')
                return result
            self.browser_calls.clear()
            with self.subTest(phase=phase):
                try:
                    with self.assertRaises(ValueError):
                        self.run_scenario(name='chromium-driver-' + phase, execute=changed)
                finally:
                    self.driver.write_bytes(original)
                self.assertEqual([call['phase'] for call in self.browser_calls],
                                 list(install.PHASES[:install.PHASES.index(phase) + 1]))
                self.assertEqual(self.passed, [] if phase == 'clean' else ['clean-install'])
                self.assertFalse((self.context['evidence'] / 'install/before-remove.json').exists())


if __name__ == '__main__':
    unittest.main()
