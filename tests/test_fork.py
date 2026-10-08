"""Offline Git fixtures verify creation of an independent foundation repository.

Set FOUNDATION_FORK_SHELL to an executable path to exercise a specific shell;
otherwise the fixtures use fork.sh's shebang.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'fork.sh'
FORK_SHELL = os.environ.get('FOUNDATION_FORK_SHELL')
SCRIPT_COMMAND = [FORK_SHELL, str(SCRIPT)] if FORK_SHELL else [str(SCRIPT)]


@unittest.skipUnless(os.name == 'posix' and shutil.which('git'),
                     'fork.sh requires POSIX shell and Git')
class ForkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation-fork-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = self.root / 'gitconfig'
        self.config.write_text('[user]\n\tname = Fork fixture\n'
                               '\temail = fork@example.invalid\n'
                               '\tuseConfigOnly = true\n'
                               '[protocol "http"]\n\tallow = never\n'
                               '[protocol "https"]\n\tallow = never\n'
                               '[protocol "ssh"]\n\tallow = never\n')
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith('GIT_') and not key.startswith('PROJECT_')
                            and key not in ('EMAIL', 'DEFAULT_SOURCE_URLS')}
        self.environment.update(GIT_CONFIG_GLOBAL=str(self.config),
                                GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0',
                                LC_ALL='C')
        self.scratch = self.root / 'scratch'
        self.scratch.mkdir()
        self.environment['TMPDIR'] = str(self.scratch)

    def git(self, repository, *arguments, check=True, environment=None, input=None):
        result = subprocess.run(['git', '-C', str(repository), *arguments],
                                env=environment or self.environment, input=input, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=15)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def source(self, name='source', rich=False, attribution=False, object_format=None):
        repository = self.root / name
        repository.mkdir()
        if object_format:
            result = self.git(repository, 'init', '-q', '-b', 'main',
                              '--object-format=' + object_format, check=False)
            if result.returncode:
                self.skipTest('Git does not support ' + object_format + ' repositories: ' + result.stderr)
        else:
            self.git(repository, 'init', '-q', '-b', 'main')
        (repository / 'tracked.txt').write_text('previous contents\n')
        self.git(repository, 'add', 'tracked.txt')
        self.git(repository, 'commit', '-q', '-m', 'Old upstream commit')
        previous = self.git(repository, 'rev-parse', 'HEAD').stdout.strip()
        (repository / 'tracked.txt').write_text(name + '\n')
        if rich:
            (repository / '.gitignore').write_text('ignored.txt\n')
            (repository / 'ignored.txt').write_text('tracked despite ignore\n')
            (repository / '.hidden').write_text('hidden file\n')
            (repository / 'with space.txt').write_text('space in tracked filename\n')
            executable = repository / 'executable.sh'
            executable.write_text('#!/bin/sh\nprintf "%s\\n" fixture\n')
            executable.chmod(0o755)
            (repository / 'relative-link').symlink_to('tracked.txt')
            (repository / '.gitattributes').write_text(
                'export-only.txt export-ignore\nsubstituted.txt export-subst\n')
            (repository / 'export-only.txt').write_text('retain exported-ignore file\n')
            (repository / 'substituted.txt').write_text('$Format:%H$\n')
        if attribution:
            (repository / 'LICENSE').write_bytes((ROOT / 'LICENSE').read_bytes())
            (repository / 'README.md').write_text(
                '# Software Foundation\n\n'
                'Author: mirage335. The code and documentation authored in this repository are\n'
                'dedicated to the public domain under [CC0 1.0 Universal](LICENSE).\n\n'
                'History mentions mirage335 independently of the author line.\n')
            (repository / 'third_party').mkdir()
            (repository / 'third_party' / 'NOTICE').write_text(
                'Copyright (c) 2024 Supplier\nSupplier author: mirage335\n')
        self.git(repository, 'add', '-f', '-A')
        self.git(repository, 'commit', '-q', '-m', 'Current upstream commit')
        self.git(repository, 'tag', 'upstream-tag', previous)
        self.git(repository, 'remote', 'add', 'origin', str(self.root / 'unused-remote'))
        return repository, previous

    def fork(self, destination=None, *sources, cwd=None, environment=None, success=True,
             separator=False):
        command = list(SCRIPT_COMMAND)
        if separator:
            command.append('--')
        if destination is not None:
            command.append(str(destination))
        command.extend(str(source) for source in sources)
        result = subprocess.run(command, cwd=cwd or self.root,
                                env=environment or self.environment, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=30)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def assert_fresh(self, destination, source, old_commit, modified=()):
        source_main = self.git(source, 'rev-parse', 'refs/heads/main').stdout.strip()
        root_commit = self.git(destination, 'rev-parse', 'HEAD').stdout.strip()
        source_tree = self.git(source, 'rev-parse', 'refs/heads/main^{tree}').stdout.strip()
        source_headers = self.git(source, 'cat-file', 'commit', source_main).stdout.split('\n\n', 1)[0]
        identity_headers = [line for line in source_headers.splitlines()
                            if line.startswith(('author ', 'committer ', 'encoding '))]
        self.assertEqual(self.git(destination, 'cat-file', 'commit', root_commit).stdout,
                         'tree ' + source_tree + '\n' + '\n'.join(identity_headers) +
                         '\n\nFoundation snapshot\n\nFoundation-commit: ' + source_main + '\n')
        self.assertEqual(self.git(destination, 'symbolic-ref', 'HEAD').stdout.strip(), 'refs/heads/main')
        self.assertNotEqual(root_commit, source_main)
        self.assertEqual(self.git(destination, 'rev-list', '--all', '--parents').stdout.strip(), root_commit)
        self.assertEqual(self.git(destination, 'rev-list', '--count', 'HEAD').stdout.strip(), '1')
        self.assert_complete_history(destination, (root_commit,))
        self.assertEqual(self.git(destination, 'for-each-ref', '--format=%(refname) %(objectname)').stdout,
                         'refs/heads/main ' + root_commit + '\n')
        self.assertEqual(self.git(destination, 'rev-parse', 'HEAD^{tree}').stdout,
                         self.git(source, 'rev-parse', 'refs/heads/main^{tree}').stdout)
        self.assertEqual(self.git(destination, 'write-tree').stdout,
                         self.git(source, 'rev-parse', 'refs/heads/main^{tree}').stdout)
        self.assertEqual(self.git(destination, 'diff', '--cached', '--name-only').stdout, '')
        self.assertEqual(self.git(destination, 'remote').stdout, '')
        self.assertEqual(self.git(destination, 'for-each-ref', 'refs/remotes').stdout, '')
        self.assertEqual(self.git(destination, 'config', '--local', '--get-regexp',
                                 r'^remote\.|^branch\.', check=False).returncode, 1)
        self.assertNotEqual(self.git(destination, 'rev-parse', '--verify', '@{upstream}',
                                     check=False).returncode, 0)
        self.assertNotEqual(self.git(destination, 'cat-file', '-e', old_commit,
                                     check=False).returncode, 0)
        self.assertNotEqual(self.git(destination, 'cat-file', '-e', source_main,
                                     check=False).returncode, 0)
        self.assertEqual(self.git(destination, 'status', '--porcelain').stdout,
                         ''.join(' M ' + filename + '\n' for filename in sorted(modified)))
        self.assertFalse((destination / '.git' / 'FETCH_HEAD').exists())
        self.assert_no_temporary_output()

    def assert_complete_history(self, repository, commits):
        metadata = Path(self.git(repository, 'rev-parse', '--absolute-git-dir').stdout.strip())
        self.assertEqual(self.git(repository, 'rev-parse', '--is-shallow-repository').stdout.strip(),
                         'false')
        for path in ('shallow', 'objects/info/alternates', 'objects/info/http-alternates',
                     'info/grafts', 'refs/replace'):
            self.assertFalse((metadata / path).exists(), path)
        self.assertEqual(self.git(repository, 'for-each-ref', 'refs/replace').stdout, '')
        stored = [line.split() for line in self.git(repository, 'cat-file', '--batch-all-objects',
                  '--batch-check=%(objectname) %(objecttype)').stdout.splitlines()]
        self.assertEqual({object_id for object_id, kind in stored if kind == 'commit'}, set(commits))
        self.assertNotIn('tag', [kind for _, kind in stored])
        reachable = set(self.git(repository, 'rev-list', '--objects', '--all',
                                '--no-object-names').stdout.splitlines())
        self.assertEqual({object_id for object_id, _ in stored}, reachable)
        result = self.git(repository, 'fsck', '--strict', '--full')
        self.assertEqual(result.stdout + result.stderr, '')

    def assert_no_temporary_output(self):
        self.assertEqual(list(self.root.rglob('.foundation-fork.*')), [])
        self.assertEqual(list(self.scratch.iterdir()), [])

    def current_date(self):
        return subprocess.run(['date', '+%Y-%m-%d'], env=self.environment, text=True,
                              stdout=subprocess.PIPE, check=True, timeout=5).stdout.strip()

    def test_exact_tracked_tree_is_preserved_in_an_independent_root_commit(self):
        source, previous = self.source('source path', rich=True)
        (source / 'tracked.txt').write_text('uncommitted modification\n')
        (source / 'untracked.txt').write_text('exclude this file\n')
        destination = self.root / 'new project'
        current_date = self.current_date()
        result = self.fork(destination, source)
        self.assert_fresh(destination, source, previous)
        self.assertEqual((destination / 'tracked.txt').read_text(), 'source path\n')
        self.assertFalse((destination / 'untracked.txt').exists())
        self.assertEqual((destination / 'ignored.txt').read_text(), 'tracked despite ignore\n')
        self.assertEqual((destination / 'export-only.txt').read_text(), 'retain exported-ignore file\n')
        self.assertEqual((destination / 'substituted.txt').read_text(), '$Format:%H$\n')
        self.assertTrue((destination / 'relative-link').is_symlink())
        self.assertEqual(os.readlink(destination / 'relative-link'), 'tracked.txt')
        self.assertTrue(os.access(destination / 'executable.sh', os.X_OK))
        self.assertEqual((destination / '.hidden').read_text(), 'hidden file\n')
        self.assertEqual((destination / 'with space.txt').read_text(), 'space in tracked filename\n')
        identity = self.git(destination, 'show', '-s', '--format=%an%n%ae').stdout.splitlines()
        self.assertEqual(identity, ['Fork fixture', 'fork@example.invalid'])
        self.assertIn('new project', result.stdout)
        self.assertIn(current_date, result.stdout)

    def test_default_https_source_uses_git_url_rewriting_without_network(self):
        source, previous = self.source()
        self.git(self.root, 'config', '--file', str(self.config),
                 'url.' + source.as_uri() + '.insteadOf',
                 'https://github.com/mirage335-colossus/software-foundation.git')
        destination = self.root / 'default-source'
        self.fork(destination)
        self.assert_fresh(destination, source, previous)

    def test_sha256_source_retains_object_format_and_complete_independent_history(self):
        source, previous = self.source('sha256-source', rich=True, object_format='sha256')
        destination = self.root / 'sha256-project'
        self.fork(destination, source)
        self.assert_fresh(destination, source, previous)
        self.assertEqual(self.git(destination, 'config', '--local', '--get',
                                 'extensions.objectFormat').stdout.strip(), 'sha256')
        self.assertEqual(len(self.git(destination, 'rev-parse', 'HEAD').stdout.strip()), 64)

    def test_omitted_destination_uses_project_name_and_ordered_configured_sources(self):
        source, previous = self.source(r"source [literal] 'quoted' \path")
        alternate, _ = self.source('alternate')
        environment = dict(self.environment, PROJECT_NAME='Default Project',
                           DEFAULT_SOURCE_URLS='\n' + str(self.root / 'missing') + '\n\n' +
                           str(source) + '\n' + str(alternate) + '\n')
        self.fork(environment=environment)
        self.assert_fresh(self.root / 'Default Project', source, previous)

    def test_positional_sources_replace_default_list_and_destination_overrides_name(self):
        default, _ = self.source('default')
        selected, previous = self.source('selected')
        environment = dict(self.environment, PROJECT_NAME='Configured Name',
                           DEFAULT_SOURCE_URLS=str(default))
        destination = self.root / 'explicit-destination'
        result = self.fork(destination, selected, environment=environment)
        self.assert_fresh(destination, selected, previous)
        self.assertFalse((self.root / 'Configured Name').exists())
        self.assertIn('Configured Name', result.stdout)

    def test_empty_configured_source_list_fails_without_output(self):
        destination = self.root / 'empty-list'
        for sources in ('', '\n\n'):
            with self.subTest(sources=sources):
                self.fork(destination, environment=dict(self.environment,
                          DEFAULT_SOURCE_URLS=sources), success=False)
                self.assertFalse(destination.exists())
                self.assert_no_temporary_output()

    def test_empty_destination_does_not_fall_back_to_configured_project_name(self):
        source, _ = self.source()
        environment = dict(self.environment, PROJECT_NAME='Configured Project')
        self.fork('', source, environment=environment, success=False)
        self.assertFalse((self.root / 'Configured Project').exists())
        self.assert_no_temporary_output()

    def test_ssh_url_forms_in_source_list_use_git_native_routing(self):
        source, previous = self.source('routed-source')
        alternate, _ = self.source('alternate-source')
        for number, url in enumerate(('ssh://git@example.invalid/software-foundation.git',
                                       'git@example.invalid:software-foundation.git')):
            with self.subTest(url=url):
                self.git(self.root, 'config', '--file', str(self.config), '--add',
                         'url.' + source.as_uri() + '.insteadOf', url)
                destination = self.root / ('ssh-source-' + str(number))
                self.fork(destination, self.root / 'missing', url, alternate)
                self.assert_fresh(destination, source, previous)

    def test_unavailable_source_falls_back_in_order_and_first_success_wins(self):
        first, previous = self.source('first')
        second, _ = self.source('second')
        destination = self.root / 'fallback'
        self.fork(destination, self.root / 'missing', first, second)
        self.assert_fresh(destination, first, previous)
        self.assertEqual((destination / 'tracked.txt').read_text(), 'first\n')

    def test_missing_main_and_tag_named_main_sources_are_rejected_before_fallback(self):
        no_main, _ = self.source('without-main')
        tag_main, _ = self.source('tag-only-main')
        selected, previous = self.source('valid-main')
        self.git(no_main, 'branch', '-m', 'other')
        self.git(tag_main, 'branch', '-m', 'other')
        self.git(tag_main, 'tag', 'main')
        destination = self.root / 'selected-main'
        self.fork(destination, no_main, tag_main, selected)
        self.assert_fresh(destination, selected, previous)
        failed_destination = self.root / 'all-without-main'
        self.fork(failed_destination, no_main, tag_main, success=False)
        self.assertFalse(failed_destination.exists())
        self.assert_no_temporary_output()

    def test_old_history_other_branches_tags_and_unique_objects_are_excluded(self):
        source, previous = self.source()
        previous_blob = self.git(source, 'rev-parse', previous + ':tracked.txt').stdout.strip()
        self.git(source, 'branch', 'old-topic', previous)
        self.git(source, 'checkout', '-q', '--orphan', 'independent-topic')
        self.git(source, 'rm', '-q', '-r', '-f', '--', '.')
        (source / 'independent.txt').write_text('independent ancestry\n')
        self.git(source, 'add', 'independent.txt')
        self.git(source, 'commit', '-q', '-m', 'Independent branch root')
        independent_commit = self.git(source, 'rev-parse', 'HEAD').stdout.strip()
        independent_blob = self.git(source, 'rev-parse', 'HEAD:independent.txt').stdout.strip()
        self.git(source, 'tag', '-a', 'independent-tag', '-m', 'Independent annotated tag')
        self.git(source, 'checkout', '-q', '--orphan', 'tag-only-topic')
        self.git(source, 'rm', '-q', '-r', '-f', '--', '.')
        (source / 'tag-only.txt').write_text('reachable only through a tag\n')
        self.git(source, 'add', 'tag-only.txt')
        self.git(source, 'commit', '-q', '-m', 'Tag-only root')
        tag_commit = self.git(source, 'rev-parse', 'HEAD').stdout.strip()
        tag_blob = self.git(source, 'rev-parse', 'HEAD:tag-only.txt').stdout.strip()
        self.git(source, 'tag', '-a', 'tag-only', '-m', 'Tag-only annotated tag')
        tag_object = self.git(source, 'rev-parse', 'refs/tags/tag-only').stdout.strip()
        self.git(source, 'checkout', '-q', 'main')
        self.git(source, 'branch', '-D', 'tag-only-topic')
        destination = self.root / 'main-only'
        self.fork(destination, source)
        self.assert_fresh(destination, source, previous)
        for object_id in (previous_blob, independent_commit, independent_blob,
                          tag_commit, tag_blob, tag_object):
            with self.subTest(object_id=object_id):
                self.assertNotEqual(self.git(destination, 'cat-file', '-e', object_id,
                                             check=False).returncode, 0)

    def test_repository_objects_are_independent_after_source_is_removed(self):
        source, previous = self.source(rich=True)
        self.git(source, 'gc', '--quiet')
        destination = self.root / 'independent-objects'
        self.fork(destination, source)
        self.assert_fresh(destination, source, previous)
        object_inodes = []
        for repository in (source, destination):
            object_inodes.append({(path.stat().st_dev, path.stat().st_ino)
                                  for path in (repository / '.git' / 'objects').rglob('*')
                                  if path.is_file()})
        self.assertTrue(object_inodes[0])
        self.assertTrue(object_inodes[1])
        self.assertFalse(object_inodes[0] & object_inodes[1])
        root_commit = self.git(destination, 'rev-parse', 'HEAD').stdout.strip()
        shutil.rmtree(source)
        self.assert_complete_history(destination, (root_commit,))
        self.assertEqual(self.git(destination, 'rev-list', '--count', 'HEAD').stdout.strip(), '1')
        self.assertEqual(self.git(destination, 'show', 'HEAD:tracked.txt').stdout, 'source\n')

    def test_initial_push_and_ordinary_clone_keep_only_the_snapshot_and_project_history(self):
        source, previous = self.source(rich=True)
        source_main = self.git(source, 'rev-parse', 'refs/heads/main').stdout.strip()
        for child_commits in (0, 2):
            with self.subTest(child_commits=child_commits):
                destination = self.root / ('push-project-' + str(child_commits))
                self.fork(destination, source)
                self.assert_fresh(destination, source, previous)
                root_commit = self.git(destination, 'rev-parse', 'HEAD').stdout.strip()
                commits = [root_commit]
                for number in range(child_commits):
                    (destination / 'project.txt').write_text('project work ' + str(number) + '\n')
                    self.git(destination, 'add', 'project.txt')
                    self.git(destination, 'commit', '-q', '-m', 'Project commit ' + str(number))
                    commits.append(self.git(destination, 'rev-parse', 'HEAD').stdout.strip())
                remote = self.root / ('empty-remote-' + str(child_commits) + '.git')
                remote.mkdir()
                self.git(remote, 'init', '-q', '--bare', '-b', 'main')
                self.assertEqual(self.git(remote, 'config', '--get', 'receive.shallowUpdate',
                                         check=False).returncode, 1)
                expected_history = self.git(destination, 'rev-list', '--parents', 'HEAD').stdout
                expected_root = self.git(destination, 'cat-file', 'commit', root_commit).stdout
                expected_tree = self.git(destination, 'rev-parse', 'HEAD^{tree}').stdout
                self.git(destination, 'push', '--', remote.as_uri(), 'main')
                shutil.rmtree(destination)
                if child_commits == 2:
                    shutil.rmtree(source)
                clone = self.root / ('ordinary-clone-' + str(child_commits))
                self.git(self.root, 'clone', '--quiet', '--', remote.as_uri(), str(clone))
                for repository in (remote, clone):
                    self.assert_complete_history(repository, commits)
                    self.assertEqual(self.git(repository, 'rev-list', '--parents', 'HEAD').stdout,
                                     expected_history)
                    self.assertEqual(self.git(repository, 'cat-file', 'commit', root_commit).stdout,
                                     expected_root)
                    for excluded in (source_main, previous):
                        self.assertNotEqual(self.git(repository, 'cat-file', '-e', excluded,
                                                     check=False).returncode, 0)
                self.assertEqual(self.git(clone, 'rev-parse', 'HEAD^{tree}').stdout, expected_tree)
                self.assertEqual(self.git(clone, 'status', '--porcelain').stdout, '')

    def test_failed_clone_does_not_leak_refs_or_objects_into_next_attempt(self):
        failed, _ = self.source('failed-source')
        selected, previous = self.source('selected-source')
        self.git(failed, 'branch', 'failed-only-branch')
        self.git(failed, 'tag', 'failed-only-tag')
        failed_head = self.git(failed, 'rev-parse', 'HEAD').stdout.strip()
        programs = self.root / 'programs'
        programs.mkdir()
        wrapper = programs / 'git'
        wrapper.write_text('#!/bin/sh\n'
            'is_clone=false\nis_failed_source=false\n'
            'for argument do\n'
            '  [ "$argument" != clone ] || is_clone=true\n'
            '  [ "$argument" != ' + shlex.quote(str(failed)) + ' ] || is_failed_source=true\n'
            'done\n' + shlex.quote(shutil.which('git')) + ' "$@"\nresult=$?\n'
            'if [ "$result" -eq 0 ] && [ "$is_clone" = true ] && [ "$is_failed_source" = true ]; then\n'
            '  exit 1\nfi\nexit "$result"\n')
        wrapper.chmod(0o755)
        environment = dict(self.environment, PATH=str(programs) + os.pathsep + self.environment['PATH'])
        destination = self.root / 'after-partial-failure'
        self.fork(destination, failed, selected, environment=environment)
        self.assert_fresh(destination, selected, previous)
        self.assertNotEqual(self.git(destination, 'cat-file', '-e', failed_head,
                                     check=False).returncode, 0)

    def test_detached_or_non_main_source_head_does_not_change_selected_main_tip(self):
        source, previous = self.source()
        for number, checkout_arguments in enumerate((('--detach', previous), ('-b', 'other-topic', previous))):
            with self.subTest(checkout_arguments=checkout_arguments):
                self.git(source, 'checkout', '-q', *checkout_arguments)
                destination = self.root / ('source-head-' + str(number))
                result = self.fork(destination, source)
                self.assert_fresh(destination, source, previous)
                self.assertNotIn('switch -c', result.stdout)

    def test_suggested_commit_and_remote_blocks_are_separate_and_shell_safe(self):
        source, previous = self.source(attribution=True)
        project_name = "Project 'name' $(touch injected) & literal"
        destination = self.root / "new 'project' $(touch injected)"
        environment = dict(self.environment, PROJECT_NAME=project_name, PROJECT_AUTHOR='Screenname')
        result = self.fork(destination, source, environment=environment)
        self.assert_fresh(destination, source, previous, modified=('LICENSE', 'README.md'))
        lines = result.stdout.splitlines()
        directory_commands = [(number, line.strip(), shlex.split(line.strip()))
                              for number, line in enumerate(lines) if line.strip().startswith('cd ')]
        commands = [(number, line.strip(), shlex.split(line.strip()))
                    for number, line in enumerate(lines) if line.strip().startswith('git ')]
        self.assertEqual(len(directory_commands), 1, result.stdout)
        directory_line, directory_command, directory_arguments = directory_commands[0]
        self.assertEqual(directory_arguments, ['cd', os.path.relpath(destination, self.root)])
        self.assertTrue(commands, result.stdout)
        self.assertLess(directory_line, commands[0][0])
        for _, _, arguments in commands:
            self.assertNotIn('-C', arguments)
            self.assertNotIn(str(destination), arguments)
        commit_commands = [item for item in commands if 'commit' in item[2]]
        remote_commands = [item for item in commands if 'remote' in item[2] and 'add' in item[2]]
        self.assertEqual(len(commit_commands), 1, result.stdout)
        self.assertEqual(len(remote_commands), 1, result.stdout)
        commit_line, _, _ = commit_commands[0]
        remote_line, _, remote_arguments = remote_commands[0]
        self.assertGreater(remote_line, commit_line)
        self.assertTrue(any(not line.strip() for line in lines[commit_line + 1:remote_line]), result.stdout)
        self.assertIn('origin', remote_arguments)
        # Execute only the suggested local staging/commit commands after checking
        # the script itself created the snapshot root. Keep cd and Git in the same shell;
        # never execute remote setup or push.
        selected_commands = [directory_command]
        for _, command, arguments in commands:
            if 'commit' in arguments or ('add' in arguments and 'remote' not in arguments):
                selected_commands.append(command)
        root_commit = self.git(destination, 'rev-parse', 'HEAD').stdout.strip()
        execution = subprocess.run('\n'.join(selected_commands), shell=True,
            executable=FORK_SHELL or '/bin/sh',
            cwd=self.root, env=self.environment, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(execution.returncode, 0, execution.stdout + execution.stderr)
        self.assertFalse((self.root / 'injected').exists())
        self.git(destination, 'merge-base', '--is-ancestor', root_commit, 'HEAD')
        self.assertNotEqual(self.git(destination, 'rev-parse', 'HEAD').stdout.strip(), root_commit)
        self.assertEqual(self.git(destination, 'status', '--porcelain').stdout, '')

    def test_source_local_configuration_is_not_copied(self):
        source, previous = self.source()
        self.git(source, 'config', 'user.name', 'Source-only name')
        self.git(source, 'config', 'user.email', 'source-only@example.invalid')
        self.git(source, 'config', 'custom.private', 'source-only metadata')
        self.git(source, 'config', 'branch.main.remote', 'origin')
        self.git(source, 'config', 'branch.main.merge', 'refs/heads/main')
        destination = self.root / 'clean-configuration'
        self.fork(destination, source)
        self.assert_fresh(destination, source, previous)
        for key in ('user.name', 'user.email', 'custom.private'):
            self.assertEqual(self.git(destination, 'config', '--local', '--get', key,
                                      check=False).returncode, 1)

    def test_snapshot_metadata_preserves_source_identity_without_private_caller_or_source_details(self):
        source, previous = self.source("private source '$(touch source-injected)'")
        source_environment = dict(self.environment,
            GIT_AUTHOR_NAME='Source author', GIT_AUTHOR_EMAIL='source-author@example.invalid',
            GIT_AUTHOR_DATE='2001-02-03T04:05:06+05:30',
            GIT_COMMITTER_NAME='Source committer', GIT_COMMITTER_EMAIL='source-committer@example.invalid',
            GIT_COMMITTER_DATE='2007-08-09T10:11:12-04:00')
        self.git(source, 'config', 'i18n.commitEncoding', 'ISO-8859-1')
        private_message = 'Private source message ' + str(source)
        self.git(source, 'commit', '-q', '--amend', '--reset-author', '-m', private_message,
                 environment=source_environment)
        raw_source = self.git(source, 'cat-file', 'commit', 'HEAD').stdout.replace('\n\n',
            '\nx-private-location ' + str(source) +
            '\ngpgsig private-source-signature\n private-signature-continuation\n\n', 1)
        source_commit = self.git(source, 'hash-object', '-t', 'commit', '-w', '--stdin',
                                 input=raw_source).stdout.strip()
        self.git(source, 'update-ref', 'refs/heads/main', source_commit)
        routed_url = 'https://private-source.example.invalid/private-repository.git'
        self.git(self.root, 'config', '--file', str(self.config),
                 'url.' + source.as_uri() + '.insteadOf', routed_url)
        self.git(self.root, 'config', '--file', str(self.config), 'user.name', 'Private machine user')
        self.git(self.root, 'config', '--file', str(self.config), 'user.email', 'private-machine@example.invalid')
        self.git(self.root, 'config', '--file', str(self.config), 'core.logAllRefUpdates', 'true')
        self.git(self.root, 'config', '--file', str(self.config), 'i18n.commitEncoding', 'UTF-8')
        environment = dict(self.environment,
            EMAIL='private-email@example.invalid',
            GIT_AUTHOR_NAME='Private environment author', GIT_AUTHOR_EMAIL='private-author@example.invalid',
            GIT_AUTHOR_DATE='1999-01-02T03:04:05+00:00',
            GIT_COMMITTER_NAME='Private environment committer',
            GIT_COMMITTER_EMAIL='private-committer@example.invalid',
            GIT_COMMITTER_DATE='1999-06-07T08:09:10+00:00',
            GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_0='user.name',
            GIT_CONFIG_VALUE_0='Private injected user', GIT_CONFIG_KEY_1='user.email',
            GIT_CONFIG_VALUE_1='private-injected@example.invalid',
            PROJECT_NAME='Private project name', PROJECT_AUTHOR='Private project screenname')
        destination = self.root / 'metadata-isolated'
        self.fork(destination, routed_url, environment=environment)
        self.assert_fresh(destination, source, previous)
        metadata_text = self.git(destination, 'cat-file', 'commit', 'HEAD').stdout
        metadata_text += (destination / '.git' / 'config').read_text()
        logs = destination / '.git' / 'logs'
        if logs.exists():
            metadata_text += ''.join(path.read_text() for path in logs.rglob('*') if path.is_file())
        for private in (str(source), routed_url, private_message, 'private-source-signature',
                        'private-signature-continuation', 'Private machine user',
                        'private-machine@example.invalid', 'Private environment author',
                        'Private environment committer', 'private-author@example.invalid',
                        'private-committer@example.invalid', 'private-email@example.invalid',
                        'Private injected user', 'private-injected@example.invalid',
                        'Private project name', 'Private project screenname'):
            self.assertNotIn(private, metadata_text)
        self.assertFalse((self.root / 'source-injected').exists())

    def test_file_url_handles_spaces(self):
        source, previous = self.source('source with spaces')
        destination = self.root / 'file-url'
        self.fork(destination, source.as_uri())
        self.assert_fresh(destination, source, previous)

    def test_relative_local_source_resolves_from_callers_directory(self):
        source, previous = self.source('relative source')
        caller = self.root / 'caller'
        caller.mkdir()
        destination = self.root / 'project'
        result = self.fork(destination, '../relative source', cwd=caller)
        self.assert_fresh(destination, source, previous)
        directory_commands = [shlex.split(line.strip()) for line in result.stdout.splitlines()
                              if line.strip().startswith('cd ')]
        self.assertEqual(directory_commands, [['cd', '../project']])

    def test_all_source_failures_leave_no_destination_or_scratch(self):
        destination = self.root / 'failed'
        self.fork(destination, self.root / 'missing-one', self.root / 'missing-two', success=False)
        self.assertFalse(destination.exists())
        self.assert_no_temporary_output()

    def test_checkout_failure_removes_own_output_and_preserves_other_files(self):
        source, _ = self.source()
        source_head = self.git(source, 'rev-parse', 'HEAD').stdout
        source_index = (source / '.git' / 'index').read_bytes()
        sentinel = self.root / 'unrelated.txt'
        sentinel.write_text('preserve unrelated content\n')
        programs = self.root / 'programs'
        programs.mkdir()
        wrapper = programs / 'git'
        wrapper.write_text('#!/bin/sh\n'
            'for argument do\n'
            '  if [ "$argument" = reset ]; then exit 7; fi\n'
            'done\nexec ' + shlex.quote(shutil.which('git')) + ' "$@"\n')
        wrapper.chmod(0o755)
        environment = dict(self.environment, PATH=str(programs) + os.pathsep + self.environment['PATH'])
        destination = self.root / 'failed-checkout'
        self.fork(destination, source, environment=environment, success=False)
        self.assertFalse(destination.exists())
        self.assertEqual(sentinel.read_text(), 'preserve unrelated content\n')
        self.assertEqual(self.git(source, 'rev-parse', 'HEAD').stdout, source_head)
        self.assertEqual((source / '.git' / 'index').read_bytes(), source_index)
        self.assertEqual(self.git(source, 'status', '--porcelain').stdout, '')
        self.assert_no_temporary_output()

    def test_missing_git_identity_is_not_required_to_create_checkout(self):
        source, previous = self.source()
        self.config.write_text('[user]\n\tuseConfigOnly = true\n')
        destination = self.root / 'identity-not-required'
        self.fork(destination, source)
        self.assert_fresh(destination, source, previous)

    def test_existing_destinations_are_preserved_including_dangling_symlink(self):
        source, _ = self.source()
        empty = self.root / 'empty'
        empty.mkdir()
        populated = self.root / 'populated'
        populated.mkdir()
        (populated / 'keep.txt').write_text('keep existing content\n')
        plain_file = self.root / 'plain-file'
        plain_file.write_text('keep file\n')
        link = self.root / 'dangling-link'
        link.symlink_to(self.root / 'absent-target')
        for destination in (empty, populated, plain_file, link):
            with self.subTest(destination=destination.name):
                self.fork(destination, source, success=False)
        self.assertEqual(list(empty.iterdir()), [])
        self.assertEqual((populated / 'keep.txt').read_text(), 'keep existing content\n')
        self.assertEqual(plain_file.read_text(), 'keep file\n')
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), str(self.root / 'absent-target'))
        self.assert_no_temporary_output()

    def test_missing_destination_parent_is_not_created(self):
        source, _ = self.source()
        parent = self.root / 'absent-parent'
        self.fork(parent / 'project', source, success=False)
        self.assertFalse(parent.exists())
        self.assert_no_temporary_output()

    def test_inherited_git_repository_environment_cannot_modify_another_repository(self):
        source, previous = self.source()
        foreign, _ = self.source('foreign')
        original_head = self.git(foreign, 'rev-parse', 'HEAD').stdout
        original_index = (foreign / '.git' / 'index').read_bytes()
        environment = dict(self.environment, GIT_DIR=str(foreign / '.git'),
                           GIT_WORK_TREE=str(foreign), GIT_COMMON_DIR=str(foreign / '.git'),
                           GIT_INDEX_FILE=str(foreign / '.git' / 'foreign-index'),
                           GIT_OBJECT_DIRECTORY=str(foreign / '.git' / 'objects'),
                           GIT_ALTERNATE_OBJECT_DIRECTORIES=str(foreign / '.git' / 'objects'),
                           GIT_NAMESPACE='foreign-namespace')
        destination = self.root / 'isolated'
        self.fork(destination, source, environment=environment)
        self.assert_fresh(destination, source, previous)
        self.assertEqual(self.git(foreign, 'rev-parse', 'HEAD').stdout, original_head)
        self.assertEqual((foreign / '.git' / 'index').read_bytes(), original_index)
        self.assertFalse((foreign / '.git' / 'foreign-index').exists())
        self.assertEqual(self.git(foreign, 'status', '--porcelain').stdout, '')

    def test_user_hooks_and_signing_cannot_mutate_or_block_checkout(self):
        source, previous = self.source()
        hooks = self.root / 'hooks'
        hooks.mkdir()
        marker = self.root / 'hook-ran'
        for name in ('pre-commit', 'commit-msg', 'post-checkout'):
            hook = hooks / name
            hook.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 1\n')
            hook.chmod(0o755)
        template = self.root / 'template'
        template.mkdir()
        (template / 'config').write_text('[remote "inherited"]\n\turl = /not/a/remote\n')
        self.git(self.root, 'config', '--file', str(self.config), 'core.hooksPath', str(hooks))
        self.git(self.root, 'config', '--file', str(self.config), 'commit.gpgSign', 'true')
        self.git(self.root, 'config', '--file', str(self.config), 'gpg.program', '/not/a/signing/program')
        self.git(self.root, 'config', '--file', str(self.config), 'init.templateDir', str(template))
        destination = self.root / 'hooks-isolated'
        self.fork(destination, source)
        self.assert_fresh(destination, source, previous)
        self.assertFalse(marker.exists())

    def test_separator_allows_destination_beginning_with_dash(self):
        source, previous = self.source()
        result = self.fork('-project', source, separator=True)
        self.assert_fresh(self.root / '-project', source, previous)
        directory_commands = [shlex.split(line.strip()) for line in result.stdout.splitlines()
                              if line.strip().startswith('cd ')]
        self.assertEqual(directory_commands, [['cd', './-project']])

    def test_project_attribution_without_documents_does_not_set_git_identity(self):
        source, previous = self.source()
        environment = dict(self.environment, PROJECT_NAME='Example Project',
                           PROJECT_AUTHOR='Screenname')
        current_date = self.current_date()
        destination = self.root / 'custom-project'
        result = self.fork(destination, source, environment=environment)
        self.assert_fresh(destination, source, previous)
        identity = self.git(destination, 'show', '-s', '--format=%an%n%ae%n%cn%n%ce').stdout.splitlines()
        self.assertEqual(identity, ['Fork fixture', 'fork@example.invalid',
                                    'Fork fixture', 'fork@example.invalid'])
        self.assertIn('Example Project', result.stdout)
        self.assertIn(current_date, result.stdout)

    def test_unconfigured_attribution_keeps_source_author_instead_of_git_name(self):
        source, previous = self.source(attribution=True)
        destination = self.root / 'source-attribution'
        self.fork(destination, source)
        self.assert_fresh(destination, source, previous)
        self.assertEqual((destination / 'LICENSE').read_bytes(), (source / 'LICENSE').read_bytes())
        self.assertEqual((destination / 'README.md').read_bytes(), (source / 'README.md').read_bytes())
        self.assertIn('Author: mirage335.', (destination / 'README.md').read_text())
        self.assertNotIn('Fork fixture', (destination / 'README.md').read_text())

    def test_screenname_updates_only_project_attribution_preserving_license_body_and_git_identity(self):
        source, previous = self.source(attribution=True)
        author = r'Screen/name & \literal $ (handle) `name`'
        environment = dict(self.environment, PROJECT_AUTHOR=author)
        destination = self.root / 'attributed-project'
        current_date = self.current_date()
        self.fork(destination, source, environment=environment)
        self.assert_fresh(destination, source, previous, modified=('LICENSE', 'README.md'))
        original_license = (source / 'LICENSE').read_text()
        original_readme = (source / 'README.md').read_text()
        expected_license = original_license.replace('Copyright (c) 2026 mirage335',
            'Copyright (c) ' + current_date[:4] + ' ' + author, 1).replace(
            'To the extent possible under law, mirage335 has waived all copyright and',
            'To the extent possible under law, ' + author + ' has waived all copyright and', 1)
        self.assertEqual((destination / 'LICENSE').read_text(), expected_license)
        self.assertEqual((destination / 'README.md').read_text(),
                         original_readme.replace('Author: mirage335.', 'Author: ' + author + '.', 1))
        self.assertEqual((destination / 'LICENSE').read_text().split('Creative Commons Legal Code', 1)[1],
                         original_license.split('Creative Commons Legal Code', 1)[1])
        self.assertEqual((destination / 'third_party' / 'NOTICE').read_bytes(),
                         (source / 'third_party' / 'NOTICE').read_bytes())
        for filename in ('LICENSE', 'README.md'):
            self.assertNotIn('fork@example.invalid', (destination / filename).read_text())
        for key in ('user.name', 'user.email'):
            self.assertEqual(self.git(destination, 'config', '--local', '--get', key,
                                      check=False).returncode, 1)
        self.assertEqual(self.git(destination, 'show', '-s', '--format=%an%n%ae%n%cn%n%ce').stdout.splitlines(),
                         ['Fork fixture', 'fork@example.invalid', 'Fork fixture', 'fork@example.invalid'])
        for filename in ('tracked.txt', 'third_party/NOTICE'):
            self.assertEqual(self.git(destination, 'rev-parse', 'HEAD:' + filename).stdout,
                             self.git(source, 'rev-parse', 'HEAD:' + filename).stdout)

    def test_screenname_attribution_does_not_require_git_identity(self):
        source, previous = self.source(attribution=True)
        self.config.write_text('[user]\n\tuseConfigOnly = true\n')
        destination = self.root / 'attribution-without-identity'
        self.fork(destination, source, environment=dict(self.environment, PROJECT_AUTHOR='Screenname'))
        self.assert_fresh(destination, source, previous, modified=('LICENSE', 'README.md'))
        self.assertIn('Author: Screenname.', (destination / 'README.md').read_text())

    def test_multiline_project_author_is_rejected_without_output(self):
        source, _ = self.source()
        destination = self.root / 'multiline-author'
        for author in ('First\nSecond', 'First\rSecond'):
            with self.subTest(author=author):
                self.fork(destination, source, environment=dict(self.environment,
                          PROJECT_AUTHOR=author), success=False)
                self.assertFalse(destination.exists())
                self.assert_no_temporary_output()

    def test_unrecognized_attribution_documents_are_preserved(self):
        source, previous = self.source()
        licenses = ('Copyright (c) 2024 Other\nDifferent project license.',
                    'MIT License\n\nCopyright (c) 2026 mirage335\n\nDifferent license terms.',
                    'CC0 1.0 Universal\n\nCopyright (c) 2026 mirage335\n\nNo foundation waiver follows.')
        for number, license_text in enumerate(licenses):
            with self.subTest(license_text=license_text):
                # Absence of the final newline is intentional: unmatched blobs
                # must retain exact bytes rather than be reformatted by awk.
                (source / 'LICENSE').write_text(license_text)
                (source / 'README.md').write_text('Author: mirage335. Different attribution format.')
                self.git(source, 'add', 'LICENSE', 'README.md')
                self.git(source, 'commit', '-q', '-m', 'Different documentation ' + str(number))
                destination = self.root / ('unrecognized-' + str(number))
                self.fork(destination, source,
                          environment=dict(self.environment, PROJECT_AUTHOR='Screenname'))
                self.assert_fresh(destination, source, previous)

    def test_attribution_does_not_follow_root_document_symlinks(self):
        source, previous = self.source(attribution=True)
        for filename in ('LICENSE', 'README.md'):
            document = source / filename
            target = source / 'third_party' / filename
            target.write_bytes(document.read_bytes())
            document.unlink()
            document.symlink_to('third_party/' + filename)
        self.git(source, 'add', '-A')
        self.git(source, 'commit', '-q', '-m', 'Use root document symlinks')
        destination = self.root / 'document-links'
        self.fork(destination, source, environment=dict(self.environment, PROJECT_AUTHOR='Screenname'))
        self.assert_fresh(destination, source, previous)
        for filename in ('LICENSE', 'README.md'):
            self.assertTrue((destination / filename).is_symlink())
            self.assertEqual(os.readlink(destination / filename), 'third_party/' + filename)
            self.assertEqual((destination / 'third_party' / filename).read_bytes(),
                             (source / 'third_party' / filename).read_bytes())

    def test_gitlinks_fail_clearly_without_creating_destination(self):
        source, _ = self.source()
        commit = self.git(source, 'rev-parse', 'HEAD').stdout.strip()
        self.git(source, 'update-index', '--add', '--cacheinfo', '160000,' + commit + ',submodule')
        self.git(source, 'commit', '-q', '-m', 'Add unsupported gitlink')
        destination = self.root / 'gitlink-rejected'
        result = self.fork(destination, source, success=False)
        self.assertRegex(result.stdout + result.stderr, r'(?i)gitlink|submodule')
        self.assertFalse(destination.exists())
        self.assert_no_temporary_output()

    def test_help_and_missing_arguments_do_not_fetch_or_write(self):
        help_result = subprocess.run([*SCRIPT_COMMAND, '--help'], cwd=self.root,
                                     env=self.environment, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn('https://github.com/mirage335-colossus/software-foundation.git',
                      help_result.stdout + help_result.stderr)
        missing = subprocess.run(SCRIPT_COMMAND, cwd=self.root, env=self.environment,
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertNotEqual(missing.returncode, 0)
        self.assert_no_temporary_output()


if __name__ == '__main__':
    unittest.main()
