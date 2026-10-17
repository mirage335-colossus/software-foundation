"""Independent source roots exercise selection without a compiler or a runtime."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('appended_project', ROOT / 'tools/appended_project.py')
project = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = project
spec.loader.exec_module(project)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-project-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = self.root / 'foundation-project.json'

    def write(self, data):
        self.config.write_text(json.dumps(data), encoding='utf-8')

    def document(self, mode='neither'):
        data = project.default_document()
        data['application'] = {'id': 'org.example.instrument', 'name': 'Instrument', 'version': '2.3.4'}
        for name in ('web', 'binary'):
            data['appended'][name]['enabled'] = mode in (name, 'both')
        if mode in ('web', 'both'):
            data['appended']['web']['entry'] = 'index.html'
        return data

    def sources(self):
        web = self.root / 'src-web-appended'
        web.mkdir(exist_ok=True)
        (web / 'index.html').write_text('<!doctype html><title>Instrument</title>\n')
        binary = self.root / 'src-bin-appended'
        binary.mkdir(exist_ok=True)
        (binary / 'main.c').write_text('int instrument_value(void) { return 7; }\n')

    def cli(self, *arguments, success=True):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/appended_project.py'),
                                 *arguments, '--root', str(self.root)],
                                cwd=self.root, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_missing_config_retains_ordinary_mode_even_with_example_directories(self):
        self.sources()
        with patch.object(project, '_existing_path', side_effect=AssertionError('disabled source inspected')):
            selected = project.load_project(self.root)
        self.assertFalse(selected.configured)
        self.assertEqual(selected.mode, 'neither')
        self.assertEqual(selected.required_profile, 'minimal')
        self.assertEqual(selected.selected_profile, 'minimal')
        self.assertEqual(selected.startup_primary, 'compiled')
        self.assertFalse(self.config.exists())

    def test_all_four_modes_have_independent_minimal_profiles(self):
        self.sources()
        expected = {'neither': 'minimal', 'web': 'web', 'binary': 'binary', 'both': 'both'}
        for mode, profile in expected.items():
            with self.subTest(mode=mode):
                self.write(self.document(mode))
                with patch.object(subprocess, 'run', side_effect=AssertionError('toolchain invoked')):
                    selected = project.load_project(self.root)
                self.assertTrue(selected.configured)
                self.assertEqual(selected.mode, mode)
                self.assertEqual(selected.required_profile, profile)
                self.assertEqual(selected.selected_profile, profile)

    def test_disabled_sources_may_be_absent_or_dangling_and_are_not_inspected(self):
        for source in ('src-web-appended', 'src-bin-appended'):
            (self.root / source).symlink_to(self.root / 'absent')
        self.write(self.document())
        with patch.object(project, '_existing_path', side_effect=AssertionError('disabled source inspected')):
            self.assertEqual(project.load_project(self.root).mode, 'neither')

    def test_enabling_one_source_never_requires_the_other_root(self):
        for mode in ('web', 'binary'):
            with self.subTest(mode=mode):
                root = self.root / mode
                root.mkdir()
                active = root / ('src-web-appended' if mode == 'web' else 'src-bin-appended')
                active.mkdir()
                (active / ('index.html' if mode == 'web' else 'main.c')).write_text('fixture\n')
                selected = project.validate_document(self.document(mode), root)
                self.assertEqual(selected.mode, mode)
                self.assertFalse((root / ('src-bin-appended' if mode == 'web' else 'src-web-appended')).exists())

    def test_binary_source_selection_does_not_claim_a_verified_module(self):
        (self.root / 'src-bin-appended').mkdir()
        self.write(self.document('binary'))
        selected = project.load_project(self.root)
        self.assertEqual(selected.inspect()['readiness'], {'web': 'disabled', 'binary': 'unverified'})
        self.assertNotIn('module', selected.data['appended']['binary'])

    def test_enabled_missing_or_file_source_is_rejected(self):
        for mode in ('web', 'binary'):
            with self.subTest(mode=mode):
                data = self.document(mode)
                with self.assertRaisesRegex(project.ProjectError, 'unavailable'):
                    project.validate_document(data, self.root)
                source = self.root / data['appended'][mode]['source']
                source.write_text('not a directory\n')
                with self.assertRaisesRegex(project.ProjectError, 'directory'):
                    project.validate_document(data, self.root)

    def test_web_entry_must_be_explicit_existing_regular_and_unlinked(self):
        data = self.document('web')
        del data['appended']['web']['entry']
        with self.assertRaisesRegex(project.ProjectError, 'declared entry'):
            project.validate_document(data, self.root)
        data['appended']['web']['entry'] = 'index.html'
        source = self.root / 'src-web-appended'
        source.mkdir()
        with self.assertRaisesRegex(project.ProjectError, 'entry is unavailable'):
            project.validate_document(data, self.root)
        entry = source / 'index.html'
        entry.mkdir()
        with self.assertRaisesRegex(project.ProjectError, 'regular file'):
            project.validate_document(data, self.root)
        entry.rmdir()
        outside = self.root / 'outside.html'
        outside.write_text('fixture\n')
        entry.symlink_to(outside)
        with self.assertRaisesRegex(project.ProjectError, 'symbolic links'):
            project.validate_document(data, self.root)

    def test_enabled_source_rejects_links_in_any_ancestor(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'binary').mkdir()
        (self.root / 'linked').symlink_to(outside, target_is_directory=True)
        data = self.document('binary')
        data['appended']['binary']['source'] = 'linked/binary'
        with self.assertRaisesRegex(project.ProjectError, 'symbolic links'):
            project.validate_document(data, self.root)

    def test_source_presence_can_be_omitted_only_for_explicit_snapshot_validation(self):
        data = self.document('both')
        self.assertEqual(project.validate_document(data, self.root, check_sources=False).mode, 'both')
        self.write(data)
        self.assertEqual(project.load_project(self.root, check_sources=False).mode, 'both')
        with self.assertRaisesRegex(project.ProjectError, 'unavailable'):
            project.load_project(self.root)

    def test_duplicate_keys_at_each_level_fail(self):
        raw = json.dumps(self.document())
        for first, repeated in (
                ('"schema_version": 1', '"schema_version": 1, "schema_version": 1'),
                ('"name": "Instrument"', '"name": "Instrument", "name": "Other"'),
                ('"enabled": false', '"enabled": false, "enabled": false')):
            with self.subTest(repeated=repeated):
                self.config.write_text(raw.replace(first, repeated, 1))
                with self.assertRaisesRegex(project.ProjectError, 'duplicate JSON key'):
                    project.load_project(self.root)

    def test_unknown_fields_fail_at_each_object(self):
        paths = ((), ('application',), ('appended',), ('appended', 'web'),
                 ('appended', 'binary'), ('startup',), ('kernel',))
        for path in paths:
            with self.subTest(path=path):
                data = self.document()
                target = data
                for key in path:
                    target = target[key]
                target['unknown'] = True
                with self.assertRaisesRegex(project.ProjectError, 'unknown fields'):
                    project.validate_document(data, self.root)

    def test_required_objects_and_fields_fail_when_missing(self):
        for section, field in ((None, 'application'), ('application', 'id'),
                               ('appended', 'binary'), ('startup', 'primary'), ('kernel', 'profile')):
            with self.subTest(section=section, field=field):
                data = self.document()
                del (data if section is None else data[section])[field]
                with self.assertRaisesRegex(project.ProjectError, 'missing fields'):
                    project.validate_document(data, self.root)

    def test_unknown_versions_and_noninteger_schema_are_rejected(self):
        for version in (0, 2, True, 1.0, '1', None):
            with self.subTest(version=version):
                data = self.document()
                data['schema_version'] = version
                with self.assertRaisesRegex(project.ProjectError, 'schema_version'):
                    project.validate_document(data, self.root)

    def test_enablement_is_boolean_and_not_truthy(self):
        for value in (0, 1, 'false', [], None):
            with self.subTest(value=value):
                data = self.document()
                data['appended']['binary']['enabled'] = value
                with self.assertRaisesRegex(project.ProjectError, 'boolean'):
                    project.validate_document(data, self.root)

    def test_noncanonical_and_nonportable_paths_rejected_even_when_disabled(self):
        for source in ('', '.', '..', '/tmp/app', '../app', './app', 'a/../app',
                       'a//app', 'a/', 'a\\app', 'C:/app', 'app\nother', 'app\x7f',
                       '.git/app', '.AGENT-WORK/app', '.codex/app', 'nul/app',
                       'COM1.txt', 'COM¹/app', 'LPT².txt/app', 'a./b', 'a /b',
                       'a?b', 'a|b', 'a\u0085b'):
            with self.subTest(source=source):
                data = self.document()
                data['appended']['binary']['source'] = source
                with self.assertRaises(project.ProjectError):
                    project.validate_document(data, self.root)

    def test_web_entry_cannot_escape_or_name_a_url(self):
        for entry in ('../index.html', '/index.html', 'https://example.invalid/index.html',
                      'a//index.html', '.git/config', 'LPT³.html'):
            with self.subTest(entry=entry):
                data = self.document()
                data['appended']['web']['entry'] = entry
                with self.assertRaises(project.ProjectError):
                    project.validate_document(data, self.root)

    def test_web_entry_matches_the_portable_resource_path_profile(self):
        for entry in ('café.html', 'a' * 241, '/'.join(['a'] * 17)):
            with self.subTest(entry=entry):
                data = self.document()
                data['appended']['web']['entry'] = entry
                with self.assertRaisesRegex(project.ProjectError, 'portable resource path profile'):
                    project.validate_document(data, self.root)

    def test_source_roots_cannot_overlap_or_alias_on_another_platform(self):
        for web, binary in (('payload', 'payload'), ('payload', 'payload/bin'),
                            ('payload/web', 'payload'), ('Payload', 'payload/bin'),
                            ('pé', 'pe\u0301/bin')):
            with self.subTest(web=web, binary=binary):
                data = self.document()
                data['appended']['web']['source'] = web
                data['appended']['binary']['source'] = binary
                with self.assertRaisesRegex(project.ProjectError, 'overlap or alias'):
                    project.validate_document(data, self.root)

    def test_safe_custom_paths_with_spaces_are_supported(self):
        data = self.document('web')
        data['appended']['web']['source'] = 'product payloads/web app'
        data['appended']['web']['entry'] = 'pages/start page.html'
        entry = self.root / 'product payloads/web app/pages/start page.html'
        entry.parent.mkdir(parents=True)
        entry.write_text('fixture\n')
        self.assertEqual(project.validate_document(data, self.root).web.entry, 'pages/start page.html')

    def test_primary_owner_cannot_select_a_disabled_component(self):
        for primary in ('web', 'binary', 'unknown'):
            with self.subTest(primary=primary):
                data = self.document()
                data['startup']['primary'] = primary
                with self.assertRaisesRegex(project.ProjectError, 'startup.primary'):
                    project.validate_document(data, self.root)
        self.sources()
        for primary in ('compiled', 'web', 'binary'):
            data = self.document('both')
            data['startup']['primary'] = primary
            self.assertEqual(project.validate_document(data, self.root).startup_primary, primary)

    def test_profile_is_separate_from_payload_presence(self):
        self.sources()
        for mode in ('neither', 'web', 'binary', 'both'):
            data = self.document(mode)
            data['kernel']['profile'] = 'both'
            selected = project.validate_document(data, self.root)
            self.assertEqual(selected.mode, mode)
            self.assertEqual(selected.selected_profile, 'both')
        for mode, profile in (('web', 'minimal'), ('binary', 'web'), ('both', 'binary')):
            data = self.document(mode)
            data['kernel']['profile'] = profile
            with self.assertRaisesRegex(project.ProjectError, 'lacks an enabled'):
                project.validate_document(data, self.root)

    def test_invalid_kernel_selection_or_profile_is_not_inferred(self):
        for field, value in (('selection', 'https://example.invalid/private'),
                             ('selection', 'upstream'), ('profile', 'all')):
            data = self.document()
            data['kernel'][field] = value
            with self.assertRaisesRegex(project.ProjectError, 'kernel.' + field):
                project.validate_document(data, self.root)

    def test_product_metadata_is_validated_and_is_an_owning_copy(self):
        for field, value in (('id', 'Example Project'), ('id', '../../project'),
                             ('name', 'Title\nInjected'), ('version', 'latest'),
                             ('version', '1.0.0/../../')):
            data = self.document()
            data['application'][field] = value
            with self.assertRaisesRegex(project.ProjectError, 'application.' + field):
                project.validate_document(data, self.root)
        data = self.document()
        selected = project.validate_document(data, self.root)
        copied = selected.data
        copied['application']['name'] = 'Changed copy'
        data['appended']['binary']['enabled'] = True
        self.assertEqual(selected.application_name, 'Instrument')
        self.assertEqual(selected.mode, 'neither')

    def test_product_name_limit_counts_utf8_bytes(self):
        data = self.document()
        for name in ('é' * 128, '🧭' * 64):
            data['application']['name'] = name
            self.assertEqual(project.validate_document(data, self.root).application_name, name)
        for name in ('é' * 129, '🧭' * 65):
            data['application']['name'] = name
            with self.assertRaisesRegex(project.ProjectError, 'application.name'):
                project.validate_document(data, self.root)

    def test_invalid_json_encoding_constants_and_large_documents_fail(self):
        for raw in (b'{', b'\xff', b'{"schema_version": NaN}', b'[]', b'null',
                    b' ' * (project.MAX_CONFIG_BYTES + 1)):
            with self.subTest(raw=raw[:30]):
                self.config.write_bytes(raw)
                with self.assertRaises(project.ProjectError):
                    project.load_project(self.root)

    def test_config_symlinks_directories_and_alternate_authorities_are_rejected(self):
        elsewhere = self.root / 'elsewhere.json'
        elsewhere.write_text(json.dumps(self.document()))
        self.config.symlink_to(elsewhere)
        with self.assertRaisesRegex(project.ProjectError, 'regular file'):
            project.load_project(self.root)
        self.config.unlink()
        self.config.mkdir()
        with self.assertRaisesRegex(project.ProjectError, 'regular file'):
            project.load_project(self.root)
        with self.assertRaisesRegex(project.ProjectError, 'must be'):
            project.load_project(self.root, config_path=elsewhere)

    def test_configure_all_modes_preserves_product_and_source_bytes(self):
        self.sources()
        self.write(self.document())
        before = {path.relative_to(self.root).as_posix(): path.read_bytes()
                  for path in self.root.rglob('*') if path.is_file() and path != self.config}
        for mode in ('web', 'both', 'binary', 'neither'):
            with self.subTest(mode=mode):
                selected = project.set_mode(self.root, mode)
                self.assertEqual(selected.mode, mode)
                self.assertEqual(selected.application_id, 'org.example.instrument')
                self.assertEqual(selected.application_name, 'Instrument')
                self.assertEqual(project.load_project(self.root).mode, mode)
                self.assertEqual({name: (self.root / name).read_bytes() for name in before}, before)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),
                         ['foundation-project.json', 'src-bin-appended', 'src-web-appended'])

    def test_configure_missing_inputs_fails_without_writing_or_creating_sources(self):
        with self.assertRaisesRegex(project.ProjectError, 'explicitly create'):
            project.set_mode(self.root, 'neither')
        with self.assertRaisesRegex(project.ProjectError, 'unavailable'):
            project.set_mode(self.root, 'web', create=True)
        self.assertEqual(list(self.root.iterdir()), [])
        self.write(self.document())
        before = self.config.read_bytes()
        with self.assertRaisesRegex(project.ProjectError, 'unavailable'):
            project.set_mode(self.root, 'binary')
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.config])

    def test_disabling_primary_restores_compiled_startup_and_no_runtime_claim(self):
        self.sources()
        self.write(self.document('both'))
        project.set_mode(self.root, 'both', primary='web')
        selected = project.set_mode(self.root, 'binary')
        self.assertEqual(selected.startup_primary, 'compiled')
        self.assertEqual(selected.inspect()['readiness']['binary'], 'unverified')

    def test_mode_and_identity_edits_preserve_a_deliberately_broader_profile(self):
        self.sources()
        data = self.document('both')
        data['kernel']['profile'] = 'both'
        self.write(data)
        selected = project.set_mode(self.root, 'neither', application={'name': 'Renamed Product'})
        self.assertEqual(selected.mode, 'neither')
        self.assertEqual(selected.kernel_profile, 'both')
        self.assertEqual(selected.selected_profile, 'both')
        self.assertEqual(selected.application_name, 'Renamed Product')

    def test_adding_a_capability_needs_an_explicit_change_to_an_insufficient_profile(self):
        self.sources()
        data = self.document()
        data['kernel']['profile'] = 'minimal'
        self.write(data)
        before = self.config.read_bytes()
        with self.assertRaisesRegex(project.ProjectError, 'lacks an enabled'):
            project.set_mode(self.root, 'web')
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(project.set_mode(self.root, 'web', profile='auto').selected_profile, 'web')

    def test_invalid_existing_config_is_never_overwritten_by_configure(self):
        self.config.write_text('{invalid existing configuration\n')
        before = self.config.read_bytes()
        with self.assertRaises(project.ProjectError):
            project.set_mode(self.root, 'neither', create=True)
        self.assertEqual(self.config.read_bytes(), before)

    def test_first_configuration_does_not_clobber_a_concurrently_appearing_file(self):
        original_link = os.link

        def appears(source, destination):
            self.config.write_text('other owner\n')
            return original_link(source, destination)

        with patch.object(project.os, 'link', side_effect=appears):
            with self.assertRaisesRegex(project.ProjectError, 'appeared'):
                project.set_mode(self.root, 'neither', create=True)
        self.assertEqual(self.config.read_text(), 'other owner\n')
        self.assertEqual(list(self.root.iterdir()), [self.config])

    def test_reconfiguration_preserves_a_change_observed_before_replacement(self):
        self.write(self.document())
        other_document = json.dumps(self.document(), indent=4) + '\n'
        original_fsync = os.fsync

        def changes(descriptor):
            self.config.write_text(other_document)
            return original_fsync(descriptor)

        with patch.object(project.os, 'fsync', side_effect=changes):
            with self.assertRaisesRegex(project.ProjectError, 'changed during'):
                project.set_mode(self.root, 'neither', application={'name': 'My edit'})
        self.assertEqual(self.config.read_text(), other_document)
        self.assertEqual(list(self.root.iterdir()), [self.config])

    def test_reconfiguration_comparison_uses_the_bytes_that_were_parsed(self):
        self.write(self.document())
        other = self.document()
        other['application']['name'] = 'Intervening product edit'
        other_document = json.dumps(other) + '\n'
        original_load = project.load_project

        def changes(*args, **kwargs):
            selected = original_load(*args, **kwargs)
            self.config.write_text(other_document)
            return selected

        with patch.object(project, 'load_project', side_effect=changes):
            with self.assertRaisesRegex(project.ProjectError, 'changed during'):
                project.set_mode(self.root, 'neither', application={'name': 'My edit'})
        self.assertEqual(self.config.read_text(), other_document)
        self.assertEqual(list(self.root.iterdir()), [self.config])

    def test_cli_inspection_is_read_only_and_configuration_is_explicit(self):
        inspected = json.loads(self.cli('inspect', '--json').stdout)
        self.assertEqual(inspected['mode'], 'neither')
        self.assertFalse(inspected['configured'])
        self.assertFalse(self.config.exists())
        result = self.cli('configure', '--mode', 'neither', '--application-id', 'org.example.product',
                          '--name', 'Example Product', '--version', '1.2.3')
        self.assertIn('Working-tree configuration:', result.stdout)
        self.assertEqual(project.load_project(self.root).application_name, 'Example Product')
        self.cli('configure', '--mode', 'web', success=False)
        self.assertEqual(project.load_project(self.root).mode, 'neither')


@unittest.skipUnless(os.name == 'posix' and shutil.which('git'), 'offline fork fixture needs POSIX and Git')
class IndependentForkTests(unittest.TestCase):
    def test_customized_fork_retains_configuration_and_mode_edit_preserves_root_index(self):
        with tempfile.TemporaryDirectory(prefix='foundation-project-fork-') as temporary:
            root = Path(temporary).resolve()
            source = root / 'local source'
            source.mkdir()
            config = root / 'gitconfig'
            config.write_text('[user]\n name = Project fixture\n email = project@example.invalid\n'
                              '[protocol "http"]\n allow = never\n'
                              '[protocol "https"]\n allow = never\n')
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith(('GIT_', 'PROJECT_')) and key != 'EMAIL'}
            environment.update(GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM='1',
                               GIT_TERMINAL_PROMPT='0')

            def git(repository, *arguments, success=True):
                result = subprocess.run(['git', '-C', str(repository), *arguments], env=environment,
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                return result.stdout.strip()

            git(source, 'init', '-q', '-b', 'main')
            binary = source / 'src-bin-appended'
            binary.mkdir()
            (binary / 'main.c').write_text('int value(void) { return 19; }\n')
            data = project.default_document()
            data['application'] = {'id': 'org.example.independent', 'name': 'Independent', 'version': '4.5.6'}
            data['appended']['binary']['enabled'] = True
            (source / project.CONFIG_NAME).write_text(json.dumps(data))
            git(source, 'add', '.')
            git(source, 'commit', '-q', '-m', 'Customized application')
            original_commit = git(source, 'rev-parse', 'HEAD')
            original_tree = git(source, 'rev-parse', 'HEAD^{tree}')
            destination = root / 'independent project'
            fork = subprocess.run([str(ROOT / 'fork.sh'), str(destination), str(source)],
                                  cwd=root, env=environment, text=True, capture_output=True, timeout=30)
            self.assertEqual(fork.returncode, 0, fork.stdout + fork.stderr)
            self.assertEqual(project.load_project(destination).mode, 'binary')
            self.assertEqual(git(destination, 'rev-list', '--count', 'HEAD'), '1')
            self.assertEqual(git(destination, 'remote'), '')
            git(destination, 'cat-file', '-e', original_commit, success=False)
            self.assertEqual(git(destination, 'write-tree'), original_tree)
            self.assertEqual(git(destination, 'rev-parse', 'HEAD^{tree}'), original_tree)
            root_commit = git(destination, 'rev-parse', 'HEAD')
            project.set_mode(destination, 'neither')
            self.assertEqual(project.load_project(destination).mode, 'neither')
            self.assertEqual(git(destination, 'rev-parse', 'HEAD'), root_commit)
            self.assertEqual(git(destination, 'write-tree'), original_tree)
            self.assertEqual(git(destination, 'status', '--porcelain'), 'M foundation-project.json')
            self.assertEqual(project.load_project(source).mode, 'binary')


if __name__ == '__main__':
    unittest.main()
