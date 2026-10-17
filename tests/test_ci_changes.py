"""Changed-path decisions must preserve feedback when evidence is incomplete."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ci_changes', ROOT / 'tools/ci_changes.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class ClassificationTests(unittest.TestCase):
    def test_only_reviewed_narrative_documents_omit_expensive_work(self):
        result = ci.classify(['README.md', 'docs/ci.md', 'docs/agent-coordination.md'])
        self.assertEqual(result['scope'], 'documents')
        self.assertFalse(any(result[field] for field in ('build', 'gui', 'workflow_lint')))

    def test_isolated_editor_sources_build_entry_and_local_tests_omit_application_work(self):
        paths = ['editor/CMakeLists.txt', 'editor/ui/main.cpp', 'editor/tests/test_model.py',
                 'editor/self/generated/layout.cpp', 'editor/PLAN.md', 'COMPILE-editor']
        for selected in ([path] for path in paths):
            with self.subTest(paths=selected):
                result = ci.classify(selected)
                self.assertEqual(result['scope'], 'editor')
                self.assertFalse(any(result[field] for field in ('build', 'gui', 'workflow_lint')))
                self.assertEqual(result['tool_suites'], [])
        self.assertEqual(ci.infrastructure_suites(paths), [])

    def test_editor_and_reviewed_narrative_documents_keep_the_editor_scope(self):
        for paths in (['editor/ui/main.cpp', 'README.md', 'docs/ci.md'],
                      ['docs/README.md', 'COMPILE-editor']):
            with self.subTest(paths=paths):
                result = ci.classify(paths)
                self.assertEqual(result['scope'], 'editor')
                self.assertEqual(result['changed_paths'], paths)
                self.assertFalse(any(result[field] for field in ('build', 'gui', 'workflow_lint')))
                self.assertEqual(result['tool_suites'], [])

    def test_editor_changes_cannot_waive_application_runtime_shared_or_policy_checks(self):
        for path in ('src/main.cpp', 'include/foundation/store.hpp', 'runtime/graph.cpp',
                     'visual/flow_runtime.cpp', 'gui/shared/application.cpp', 'tools/build.py',
                     'tests/test_build.py', 'cmake/Dependencies.cmake', 'CMakeLists.txt',
                     '.github/workflows/ci.yml', 'docs/release-policy.json', 'docs/new-editor.md'):
            with self.subTest(path=path):
                result = ci.classify(['editor/ui/main.cpp', path])
                self.assertEqual(result['scope'], 'full')
                self.assertTrue(all(result[field] for field in ('build', 'gui', 'workflow_lint')))
                self.assertEqual(result['tool_suites'], ci.infrastructure_suites([path]))

    def test_editor_exclusion_requires_canonical_case_sensitive_relative_paths(self):
        all_suites = ci.infrastructure_suites([])
        for path in ('', 'editor', 'editor/', 'editor//main.cpp', 'editor/./main.cpp',
                     './editor/main.cpp', 'editor/../src/main.cpp', '../editor/main.cpp',
                     'editor/ui/../../src/main.cpp', 'src/../editor/main.cpp', 'tests/./fixture.cpp',
                     'editor\\main.cpp', '/editor/main.cpp',
                     '//editor/main.cpp', 'C:/editor/main.cpp', 'C:\\editor\\main.cpp',
                     'editor/main.cpp\nREADME.md', 'editor/main\t.cpp', 'editor/main\0.cpp',
                     'editor/main\x7f.cpp', 'editor/main\u0085.cpp', 'Editor/main.cpp',
                     'editors/main.cpp', 'COMPILE-editor/child', 'COMPILE-editor.bak',
                     './COMPILE-editor', None, 1, []):
            with self.subTest(path=path):
                result = ci.classify(['editor/ui/main.cpp', path])
                self.assertEqual(result['scope'], 'full')
                self.assertTrue(all(result[field] for field in ('build', 'gui', 'workflow_lint')))
                self.assertEqual(result['tool_suites'], all_suites)
                self.assertEqual(ci.infrastructure_suites([path]), all_suites)

    def test_policy_manual_installed_config_unknown_and_source_paths_remain_full(self):
        for path in ('docs/release-policy.json', 'docs/installed.md', 'docs/man/foundation-cli.1',
                     'docs/templates/session.json', 'docs/new-feature.md', 'docs/ci.md/new',
                     '../docs/ci.md', 'docs\\ci.md', 'docs/CI.md', 'src/main.cpp',
                     '.github/workflows/ci.yml', 'tools/ci_changes.py', 'CMakeLists.txt',
                     'LICENSE', 'docs/ci.md\nREADME.md'):
            with self.subTest(path=path):
                result = ci.classify(['docs/ci.md', path])
                self.assertEqual(result['scope'], 'full')
                self.assertTrue(all(result[field] for field in ('build', 'gui', 'workflow_lint')))
        self.assertEqual(ci.classify([])['scope'], 'full')

    def test_malformed_or_unknown_event_falls_back_without_exposing_payload(self):
        for event_name, event in [('schedule', {}), ('push', None), ('pull_request', []),
                                  ('push', {'before': 'secret-command', 'after': 'a' * 40})]:
            with self.subTest(event=event), patch.object(ci, 'git', return_value=b'a' * 40 + b'\n'):
                result = ci.select(ROOT, event_name, event, 'a' * 40)
                self.assertEqual(result['scope'], 'full')
                self.assertNotIn('secret-command', result['reason'])

    def test_git_timeout_and_invalid_bytes_fall_back_to_full(self):
        event = {'before': 'b' * 40, 'after': 'a' * 40}
        for failure in (subprocess.TimeoutExpired('git', 20), OSError('unavailable')):
            with self.subTest(failure=failure), patch.object(ci, 'git', side_effect=failure):
                self.assertEqual(ci.select(ROOT, 'push', event, 'a' * 40)['scope'], 'full')
        with patch.object(ci, 'git', side_effect=[b'a' * 40 + b'\n', b'docs/ci.md']):
            self.assertEqual(ci.select(ROOT, 'push', event, 'a' * 40)['scope'], 'full')
        with patch.object(ci, 'git', side_effect=[b'a' * 40 + b'\n', b'\xff\0']):
            self.assertEqual(ci.select(ROOT, 'push', event, 'a' * 40)['scope'], 'full')
        for raw in (b'editor/main.cpp\0\0', b'\0editor/main.cpp\0'):
            with self.subTest(raw=raw), patch.object(ci, 'git', side_effect=[b'a' * 40 + b'\n', raw]):
                self.assertEqual(ci.select(ROOT, 'push', event, 'a' * 40)['scope'], 'full')


    def test_changed_domains_run_whole_affected_suites(self):
        for tool, required in {
            'agent_edit': {'agent_edit', 'agent_record', 'agent_session', 'agent_stress'},
            'apt_repo': {'apt_repo', 'distro_channel', 'distribution_release'},
            'sdk': {'sdk', 'sdk_paths', 'sdk_retention'},
            'gui_source_group': {'gui_source_group', 'gui_boundary', 'gui_visual'},
        }.items():
            with self.subTest(tool=tool):
                self.assertLessEqual(required, set(ci.infrastructure_suites(['tools/' + tool + '.py'])))
        self.assertNotIn('apt_repo', ci.infrastructure_suites(['tools/agent_edit.py']))
        self.assertIn('gui_boundary', ci.infrastructure_suites(['gui/host/boot.mjs']))
        self.assertIn('distro_channel', ci.infrastructure_suites(['tests/test_distro_channel.py']))

    def test_rust_sources_locks_and_recipes_keep_provider_evidence_suites(self):
        for path in ('rust/validation/src/lib.rs', 'rust/Cargo.lock', 'third_party/rust/linux-x86_64.json'):
            with self.subTest(path=path):
                selected = set(ci.infrastructure_suites([path]))
                self.assertLessEqual({'ci_plan', 'source_identity', 'test_plan', 'release', 'release_check'}, selected)
                self.assertEqual(ci.classify([path])['scope'], 'full')

    def test_unknown_deleted_and_missing_inventory_are_conservative(self):
        all_suites = ci.infrastructure_suites([])
        for path in ('tools/new_helper.py', 'tools/deleted_helper.py', 'tests/test_deleted.py',
                     '.github/workflows/ci.yml', 'cmake/new.cmake', 'docs/release-policy.json', 'src/new_helper.py'):
            self.assertEqual(ci.infrastructure_suites([path]), all_suites)
        self.assertEqual(ci.infrastructure_suites(['README.md']), [])
        self.assertEqual(ci.infrastructure_suites(['src/main.cpp']), [])
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
            ci.infrastructure_suites(['tools/sdk.py'], Path(temporary))

    def test_reference_closure_includes_dynamic_literal_consumers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'tools').mkdir(); (root / 'tests').mkdir()
            (root / 'tools/sdk.py').write_text('')
            (root / 'tools/consumer.py').write_text("module('sdk')")
            (root / 'tests/test_consumer.py').write_text("subprocess.run(['consumer.py'])")
            self.assertEqual(ci.infrastructure_suites(['tools/sdk.py'], root), ['consumer'])

    def test_reviewed_policy_path_metadata_does_not_hide_real_script_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'tools').mkdir(); (root / 'tests').mkdir()
            (root / 'tools/agent_edit.py').write_text('')
            metadata = 'COMPOSITION_FILES = frozenset({"tools/agent_edit.py"})\n'
            (root / 'tools/appended_policy.py').write_text(metadata)
            (root / 'tools/consumer.py').write_text('module("agent_edit")\n')
            (root / 'tests/test_appended_policy.py').write_text('import appended_policy\n')
            (root / 'tests/test_consumer.py').write_text('import consumer\n')
            self.assertEqual(['consumer'], ci.infrastructure_suites(['tools/agent_edit.py'], root))
            (root / 'tools/appended_policy.py').write_text(
                metadata + 'subprocess.run(["tools/agent_edit.py"])\n')
            self.assertEqual(['appended_policy', 'consumer'],
                             ci.infrastructure_suites(['tools/agent_edit.py'], root))
            (root / 'tools/appended_policy.py').write_text(
                'COMPOSITION_FILES = frozenset(load("tools/agent_edit.py"))\n')
            self.assertEqual(['appended_policy', 'consumer'],
                             ci.infrastructure_suites(['tools/agent_edit.py'], root))


    def test_shared_test_fixtures_select_transitive_whole_suite_consumers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'tools').mkdir(); (root/'tests').mkdir()
            (root/'tools/example.py').write_text('')
            (root/'tests/test_fixture.py').write_text('')
            (root/'tests/test_first.py').write_text('from . import test_fixture')
            (root/'tests/test_second.py').write_text('import test_first')
            self.assertEqual(ci.infrastructure_suites(['tests/test_fixture.py'], root), ['first', 'fixture', 'second'])

    def test_selected_suite_cannot_impersonate_its_unchanged_production_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'tools').mkdir(); (root / 'tests').mkdir()
            (root / 'tools/agent_edit.py').write_text('')
            (root / 'tools/ci_changes.py').write_text('')
            (root / 'tools/consumer.py').write_text('import ci_changes\n')
            (root / 'tests/test_ci_changes.py').write_text('import agent_edit\n')
            (root / 'tests/test_consumer.py').write_text('import consumer\n')
            (root / 'tests/test_fixture_consumer.py').write_text('import test_ci_changes\n')
            self.assertEqual(['ci_changes', 'fixture_consumer'],
                             ci.infrastructure_suites(['tools/agent_edit.py'], root))
            # A real production import preserves the ordinary transitive edge.
            (root / 'tools/ci_changes.py').write_text('import agent_edit\n')
            self.assertEqual(['ci_changes', 'consumer', 'fixture_consumer'],
                             ci.infrastructure_suites(['tools/agent_edit.py'], root))

    def test_production_consumers_of_actual_test_fixtures_remain_in_reference_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'tools').mkdir(); (root / 'tests').mkdir()
            (root / 'tools/agent_edit.py').write_text('')
            (root / 'tools/consumer.py').write_text('import test_fixture\n')
            (root / 'tests/test_fixture.py').write_text('import agent_edit\n')
            (root / 'tests/test_consumer.py').write_text('import consumer\n')
            (root / 'tests/test_transitive.py').write_text('import test_consumer\n')
            self.assertEqual(['consumer', 'fixture', 'transitive'],
                             ci.infrastructure_suites(['tools/agent_edit.py'], root))

    def test_actual_whole_suite_runner_rejects_skipped_and_expected_failure_cases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'tools').mkdir(); (root/'tests').mkdir()
            shutil.copyfile(ROOT/'tools/run_tests.py', root/'tools/run_tests.py')
            (root/'tests/test_fixture.py').write_text(
                "import unittest\nclass Cases(unittest.TestCase):\n"
                " @unittest.skip('fixture incomplete')\n def test_skip(self): pass\n"
                " @unittest.expectedFailure\n def test_expected(self): self.fail('fixture incomplete')\n")
            result = ci.run_tool_suites(['fixture'], root/'output', root=root)
            self.assertEqual(result['status'], 'failed')
            receipt = json.loads((root/'output/fixture.json').read_text())
            self.assertEqual(len(receipt['inventory']), 2)
            self.assertEqual({v['status'] for v in receipt['results'].values()}, {'incomplete'})


    def test_successful_suite_with_surviving_child_is_rejected_and_joined(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'tools').mkdir(); (root/'tests').mkdir()
            shutil.copyfile(ROOT/'tools/run_tests.py', root/'tools/run_tests.py')
            (root/'tests/test_fixture.py').write_text(
                "import unittest, subprocess, sys\nclass Cases(unittest.TestCase):\n"
                " def test_orphan(self): subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])\n")
            result = ci.run_tool_suites(['fixture'], root/'output', root=root)
            self.assertEqual(json.loads((root/'output/fixture.json').read_text())['status'], 'passed')
            self.assertEqual(result['status'], 'failed')
            self.assertIn('descendants outlived', (root/'output/fixture.log').read_text())

    def test_strict_runner_failure_and_missing_receipt_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'tests').mkdir(); (root / 'tools').mkdir()
            (root / 'tests/test_fixture.py').write_text('')
            for name, code in [('failed', 1), ('missing', 0)]:
                owner = Mock(); owner.finish.return_value = code
                launch = Mock(return_value=owner)
                supervisor = SimpleNamespace(launch=launch, ProcessTreeError=RuntimeError)
                with patch.object(ci, 'load_supervisor', return_value=supervisor):
                    result = ci.run_tool_suites(['fixture'], root/name, root=root)
                    self.assertEqual(result['status'], 'failed')
                    self.assertIn(str(root/'tools/run_tests.py'), launch.call_args.args[0])
                    owner.wait.assert_called_once_with(timeout=900)
                    owner.close.assert_called_once_with()
            with self.assertRaises(ValueError):
                ci.run_tool_suites([], root/'empty', root=root)

    def test_tool_workers_use_capacity_and_subdivide_nested_allowance(self):
        cases = [(None, {}, 6, 2), (4, {}, 4, 1), (1, {}, 1, 1),
                 (None, {'CTEST_PARALLEL_LEVEL': '6'}, 6, 1),
                 (3, {'CTEST_PARALLEL_LEVEL': '6'}, 3, 1),
                 ('auto', {'CTEST_PARALLEL_LEVEL': '4'}, 6, 2)]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'tools').mkdir(); (root/'tests').mkdir()
            suites = ['fixture' + str(index) for index in range(6)]
            for name in suites:
                (root/'tests'/('test_' + name + '.py')).write_text('')
            for index, (jobs, inherited, workers, budget) in enumerate(cases):
                owners, environments = [], []
                def launch(argv, cwd, log, *, env):
                    self.assertEqual(cwd, root)
                    receipt = Path(argv[argv.index('--output') + 1])
                    receipt.write_text(json.dumps({'status': 'passed'}))
                    owner = Mock(); owner.finish.return_value = 0
                    owners.append(owner); environments.append(env)
                    return owner
                supervisor = SimpleNamespace(launch=launch, ProcessTreeError=RuntimeError)
                environment = {'PATH': 'selected-toolkit', **inherited}
                with self.subTest(jobs=jobs, inherited=inherited), \
                        patch.dict(os.environ, environment, clear=True), \
                        patch.object(ci.build_capacity, 'default_jobs', return_value=12), \
                        patch.object(ci, 'load_supervisor', return_value=supervisor), \
                        patch.object(ci, 'ThreadPoolExecutor', wraps=ci.ThreadPoolExecutor) as pool:
                    result = ci.run_tool_suites(suites, root/('output' + str(index)), jobs, root=root)
                    pool.assert_called_once_with(max_workers=workers)
                    self.assertEqual(dict(os.environ), environment)
                self.assertEqual(result['status'], 'passed')
                self.assertEqual([row['suite'] for row in result['suites']], suites)
                self.assertEqual(len(owners), len(suites))
                for child, owner in zip(environments, owners):
                    self.assertEqual(child['PATH'], environment['PATH'])
                    self.assertEqual(child['FOUNDATION_WORKER_BUDGET'], str(budget))
                    self.assertEqual(child['CMAKE_BUILD_PARALLEL_LEVEL'], str(budget))
                    self.assertEqual(child['CTEST_PARALLEL_LEVEL'], str(budget))
                    owner.wait.assert_called_once_with(timeout=900)
                    owner.close.assert_called_once_with()

    def test_invalid_concurrency_and_suite_inventory_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'tests').mkdir()
            (root/'tests/test_fixture.py').write_text('')
            output = root/'output'
            for jobs in (0, -1, True, 'unknown'):
                with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                    ci.run_tool_suites(['fixture'], output, jobs, root=root)
                self.assertFalse(output.exists())
            for suites in ([], ['fixture', 'fixture'], ['missing']):
                with self.subTest(suites=suites), self.assertRaises(ValueError):
                    ci.run_tool_suites(suites, output, root=root)
                self.assertFalse(output.exists())
        self.assertEqual(ci.tool_jobs('auto'), 'auto')
        self.assertEqual(ci.tool_jobs('7'), 7)
        import argparse
        for value in ('', '0', '-1', 'unknown'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                ci.tool_jobs(value)


class GitSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.area = Path(temporary.name)
        self.root = self.area / 'source'
        self.root.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Fixture Author')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.write('docs/ci.md', 'initial documentation\n')
        self.write('src/main.cpp', 'initial source\n')
        self.base = self.save()

    def git(self, *args, root=None):
        result = subprocess.run(['git', '-C', str(root or self.root), *args], check=True,
                                capture_output=True, text=True, timeout=20)
        return result.stdout.strip()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def save(self):
        self.git('add', '--all')
        self.git('commit', '-q', '-m', 'fixture change')
        return self.git('rev-parse', 'HEAD')

    def push(self, before, after, root=None):
        return ci.select(root or self.root, 'push', {'before': before, 'after': after}, after)

    def test_push_documentation_and_source_changes_select_different_scopes(self):
        self.write('docs/ci.md', 'revised documentation\n')
        first = self.save()
        self.assertEqual(self.push(self.base, first)['scope'], 'documents')
        self.write('src/main.cpp', 'revised source\n')
        second = self.save()
        self.assertEqual(self.push(first, second)['scope'], 'full')

    def test_renamed_source_cannot_hide_behind_documentation_destination(self):
        self.git('mv', 'src/main.cpp', 'README.md')
        head = self.save()
        result = self.push(self.base, head)
        self.assertEqual(result['scope'], 'full')
        self.assertEqual(set(result['changed_paths']), {'README.md', 'src/main.cpp'})

    def test_renamed_shared_source_cannot_hide_behind_editor_destination(self):
        (self.root / 'editor').mkdir()
        self.git('mv', 'src/main.cpp', 'editor/main.cpp')
        head = self.save()
        result = self.push(self.base, head)
        self.assertEqual(result['scope'], 'full')
        self.assertTrue(all(result[field] for field in ('build', 'gui', 'workflow_lint')))
        self.assertEqual(set(result['changed_paths']), {'editor/main.cpp', 'src/main.cpp'})

    def test_editor_addition_deletion_and_editor_rename_remain_isolated(self):
        self.write('editor/main.cpp', 'editor source\n')
        first = self.save()
        result = self.push(self.base, first)
        self.assertEqual(result['scope'], 'editor')
        self.assertEqual(result['tool_suites'], [])
        self.git('mv', 'editor/main.cpp', 'editor/window.cpp')
        second = self.save()
        renamed = self.push(first, second)
        self.assertEqual(renamed['scope'], 'editor')
        self.assertEqual(set(renamed['changed_paths']), {'editor/main.cpp', 'editor/window.cpp'})
        (self.root / 'editor/window.cpp').unlink()
        third = self.save()
        self.assertEqual(self.push(second, third)['scope'], 'editor')

    def test_deleted_runtime_source_requires_full_feedback(self):
        (self.root / 'src/main.cpp').unlink()
        head = self.save()
        self.assertEqual(self.push(self.base, head)['scope'], 'full')

    def test_deleted_document_remains_subject_to_document_checks(self):
        (self.root / 'docs/ci.md').unlink()
        head = self.save()
        result = self.push(self.base, head)
        self.assertEqual(result['scope'], 'documents')
        self.assertEqual(result['changed_paths'], ['docs/ci.md'])

    def test_pr_uses_tested_merge_and_checks_both_event_parents(self):
        self.git('checkout', '-q', '-b', 'topic')
        self.write('docs/ci.md', 'topic documentation\n')
        topic = self.save()
        self.git('checkout', '-q', 'main')
        self.write('src/main.cpp', 'base change independent of topic\n')
        base = self.save()
        self.git('merge', '--no-ff', '-q', '-m', 'merge fixture', 'topic')
        head = self.git('rev-parse', 'HEAD')
        event = {'pull_request': {'base': {'sha': base}, 'head': {'sha': topic}}}
        shallow = self.area / 'shallow'
        self.git('clone', '-q', '--depth=2', self.root.as_uri(), str(shallow))
        result = ci.select(shallow, 'pull_request', event, head)
        self.assertEqual(result['scope'], 'documents')
        self.assertEqual(result['changed_paths'], ['docs/ci.md'])
        event['pull_request']['head']['sha'] = self.base
        self.assertEqual(ci.select(shallow, 'pull_request', event, head)['scope'], 'full')
        event['pull_request']['head']['sha'] = topic
        event['pull_request']['base']['sha'] = self.base
        self.assertEqual(ci.select(shallow, 'pull_request', event, head)['scope'], 'full')

    def test_push_missing_history_or_invalid_identity_falls_back_without_fetch(self):
        self.write('docs/ci.md', 'second\n')
        self.save()
        self.write('docs/ci.md', 'third\n')
        head = self.save()
        shallow = self.area / 'shallow'
        self.git('clone', '-q', '--depth=2', self.root.as_uri(), str(shallow))
        self.assertEqual(self.push(self.base, head, shallow)['scope'], 'full')
        self.assertEqual(self.push('0' * 40, head)['scope'], 'full')
        self.assertEqual(self.push(self.base, 'f' * 40)['scope'], 'full')
        self.assertEqual(ci.select(self.root, 'push', {'before': self.base, 'after': head, 'deleted': True}, head)['scope'], 'full')

    def test_cli_emits_conclusive_outputs_and_explicit_qualification_limit(self):
        self.write('docs/ci.md', 'updated documentation\n')
        head = self.save()
        event = self.area / 'event.json'
        event.write_text(json.dumps({'before': self.base, 'after': head}))
        output = self.area / 'output'
        summary = self.area / 'summary'
        subprocess.run([sys.executable, '-B', str(ROOT / 'tools/ci_changes.py'),
                        '--root', str(self.root), '--event', str(event), '--event-name', 'push',
                        '--head', head, '--github-output', str(output), '--summary', str(summary)],
                       check=True, capture_output=True, text=True, timeout=20)
        self.assertEqual(output.read_text().splitlines(),
                         ['build=false', 'gui=false', 'workflow_lint=false', 'tools=false', 'scope=documents'])
        self.assertIn('does not qualify', summary.read_text())
        event.write_text('{invalid')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/ci_changes.py'),
                                 '--root', str(self.root), '--event', str(event), '--event-name', 'push',
                                 '--head', head], check=True, capture_output=True, text=True, timeout=20)
        self.assertEqual(json.loads(result.stdout)['scope'], 'full')

    def test_cli_editor_selection_omits_tooling_and_explains_local_checks(self):
        self.write('editor/tests/test_model.py', 'editor local check\n')
        self.write('COMPILE-editor', 'explicit editor command\n')
        self.write('docs/ci.md', 'updated editor documentation\n')
        head = self.save()
        event = self.area / 'event.json'
        event.write_text(json.dumps({'before': self.base, 'after': head}))
        output = self.area / 'output'
        summary = self.area / 'summary'
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/ci_changes.py'),
                                 '--root', str(self.root), '--event', str(event), '--event-name', 'push',
                                 '--head', head, '--github-output', str(output), '--summary', str(summary),
                                 '--run-tool-suites', '--tool-output', str(self.area / 'tool-output')],
                                check=True, capture_output=True, text=True, timeout=20)
        self.assertEqual(json.loads(result.stdout)['scope'], 'editor')
        self.assertEqual(output.read_text().splitlines(),
                         ['build=false', 'gui=false', 'workflow_lint=false', 'tools=false', 'scope=editor'])
        self.assertFalse((self.area / 'tool-output').exists())
        self.assertIn('Editor checks remain explicit and local.', summary.read_text())
        self.assertIn('does not qualify', summary.read_text())


class AppendedSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'source'
        self.root.mkdir()
        self.write('src/main.cpp', 'kernel implementation')
        self.write('src-web-appended/index.html', '<h1>Product</h1>')
        self.write('src-bin-appended/main.c', 'int app_step(void) { return 0; }')
        from appended_project import default_document
        self.document = default_document()
        self.document['appended']['web'].update(enabled=True, entry='index.html')
        self.document['appended']['binary']['enabled'] = True
        self.document['startup']['primary'] = 'web'
        self.configure()
        from appended_policy import kernel_source_tree
        self.inputs = kernel_source_tree(self.root)
        self.descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'html',
                           'profile': 'both', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
                           'capabilities': [], 'services': [], 'boundary_offset': None,
                           'executable': {'length': 1, 'sha256': '0' * 64},
                           'provenance': {'scope': 'selector-fixture-only'}, 'kernel_inputs': self.inputs}

    def write(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
        return path

    def configure(self): self.write('foundation-project.json', json.dumps(self.document))

    def selection(self, paths, **kwargs):
        with patch.object(ci, 'changed_paths', return_value=paths):
            return ci.select(self.root, 'push', {}, '', **kwargs)

    def test_source_inventory_alone_cannot_claim_retained_capability_compatibility(self):
        result = self.selection(['src-web-appended/index.html'], kernel_inputs=self.inputs)
        self.assertEqual('appended-maintenance', result['scope'])
        self.assertTrue(result['kernel_inputs']['eligible'])
        self.assertTrue(result['maintenance_required'])
        self.assertFalse(any(result[field] for field in ('build', 'gui', 'retained_eligible')))
        self.assertEqual('unverified', result['requirement_checks'])
        self.assertFalse(result['package_requirements_checked'])
        self.assertIn('capabilities are unverified', result['reason'])
        self.assertIn('web-check', result['actions'])

    def test_acquisition_selection_allowance_keeps_raw_identity_and_descriptor_contract_checks(self):
        self.document['kernel']['selection'] = 'foundation'
        self.configure()
        result = self.selection(['foundation-project.json'], kernel_descriptor=self.descriptor)
        self.assertEqual('appended', result['scope'])
        self.assertTrue(result['retained_eligible'])
        self.assertFalse(result['build'])
        self.assertFalse(result['gui'])
        self.assertEqual('foundation-appended-kernel-v2-acquisition-selection-v1',
                         result['kernel_inputs']['comparison_policy'])
        self.assertNotEqual(result['kernel_inputs']['expected_sha256'], result['kernel_inputs']['actual_sha256'])
        incompatible = self.selection(['foundation-project.json'],
                                      kernel_descriptor=dict(self.descriptor, profile='binary'))
        self.assertTrue(incompatible['kernel_inputs']['eligible'])
        self.assertFalse(incompatible['retained_eligible'])
        self.assertTrue(incompatible['maintenance_required'])
        self.assertIn('incompatible', incompatible['reason'])

    def test_new_pure_checkout_and_acquisition_helpers_have_reviewed_feedback_suites(self):
        paths = ['tools/appended_checkout.py', 'tools/appended_ci.py', '.github/appended-retained.json']
        result = self.selection(paths, kernel_descriptor=self.descriptor)
        self.assertEqual('appended', result['scope'])
        self.assertFalse(result['build'])
        self.assertFalse(result['gui'])
        self.assertTrue({'appended_checkout', 'appended_ci'} <= set(result['tool_suites']))
        self.assertIn('appended_checkout', ci.infrastructure_suites(['tools/appended_checkout.py']))
        self.assertIn('appended_ci', ci.infrastructure_suites(['tools/appended_ci.py']))
        self.assertNotIn('apt_repo', result['tool_suites'])
        self.assertTrue({'build', 'artifact', 'apt_repo'} <=
                        set(ci.infrastructure_suites(['tools/appended_checkout.py'])))

    def test_selected_profiles_and_components_require_a_compatible_retained_descriptor(self):
        from appended_policy import kernel_source_tree
        cases = [('both', 'auto', 'binary', False),
                 ('binary', 'both', 'binary', False),
                 ('neither', 'both', 'binary', False),
                 ('neither', 'minimal', 'binary', False),
                 ('binary', 'auto', 'both', True),
                 ('neither', 'auto', 'binary', True),
                 ('neither', 'both', 'both', True)]
        for mode, selected_profile, retained_profile, eligible in cases:
            with self.subTest(mode=mode, selected=selected_profile, retained=retained_profile):
                for name in ('web', 'binary'):
                    self.document['appended'][name]['enabled'] = mode in (name, 'both')
                self.document['startup']['primary'] = 'compiled'
                self.document['kernel']['profile'] = selected_profile
                self.configure()
                descriptor = dict(self.descriptor, profile=retained_profile,
                                  kernel_inputs=kernel_source_tree(self.root))
                with patch.object(ci.subprocess, 'run', side_effect=AssertionError('no build fallback')):
                    result = self.selection(['foundation-project.json'], kernel_descriptor=descriptor)
                self.assertTrue(result['kernel_inputs']['eligible'])
                self.assertEqual(eligible, result['retained_eligible'])
                self.assertEqual(not eligible, result['maintenance_required'])
                self.assertFalse(result['build'])
                self.assertFalse(result['gui'])
                if not eligible:
                    self.assertIn('retained kernel contract is incompatible', result['reason'])

    def test_nonminimal_selected_profile_without_payload_stays_on_retained_only_route(self):
        for name in ('web', 'binary'):
            self.document['appended'][name]['enabled'] = False
        self.document['startup']['primary'] = 'compiled'
        self.document['kernel']['profile'] = 'both'
        self.configure()
        result = self.selection(['src/main.cpp'])
        self.assertEqual('appended-maintenance', result['scope'])
        self.assertTrue(result['maintenance_required'])
        self.assertFalse(result['build'])
        self.assertFalse(result['gui'])

    def test_descriptor_inventory_cannot_be_overridden_by_an_unrelated_source_projection(self):
        unrelated = dict(self.inputs, tree_sha256='f' * 64)
        result = self.selection(['src-web-appended/index.html'], kernel_inputs=unrelated,
                                kernel_descriptor=self.descriptor)
        self.assertTrue(result['maintenance_required'])
        self.assertFalse(any(result[field] for field in ('build', 'gui', 'retained_eligible')))
        self.assertIn('inventory differs from the authenticated kernel descriptor', result['reason'])

    def test_malformed_full_descriptor_never_grants_retained_eligibility(self):
        for changed in ({'profile': 'unrecognized'}, {'abi': {'major': 0, 'minor': 0}},
                        {'services': ['duplicate', 'duplicate']}, {'carrier': 'unknown'}):
            with self.subTest(changed=changed):
                result = self.selection(['src-web-appended/index.html'],
                                        kernel_descriptor=dict(self.descriptor, **changed))
                self.assertTrue(result['maintenance_required'])
                self.assertFalse(any(result[field] for field in ('build', 'gui', 'retained_eligible')))
                self.assertIn('retained kernel contract unavailable', result['reason'])

    def test_baseline_abi_is_required_even_when_supplied_package_requirements_match_a_different_major(self):
        descriptor = dict(self.descriptor, abi={'major': 2, 'minor': 0})
        for requirements in (None, {'abi': {'major': 2, 'minor': 0}, 'services': [], 'capabilities': []}):
            with self.subTest(requirements=requirements):
                result = self.selection(['src-web-appended/index.html'], kernel_descriptor=descriptor,
                                        payload_requirements=requirements)
                self.assertTrue(result['maintenance_required'])
                self.assertFalse(result['retained_eligible'])
                self.assertFalse(result['build'])
                self.assertIn('Kernel ABI is incompatible', result['reason'])

    def test_explicit_package_abi_service_and_capability_requirements_use_shared_compatibility_checks(self):
        requirements = {'abi': {'major': 1, 'minor': 1},
                        'services': ['org.example.counter'], 'capabilities': ['org.example.counter.v1']}
        descriptor = dict(self.descriptor, abi={'major': 1, 'minor': 1},
                          services=requirements['services'], capabilities=requirements['capabilities'])
        accepted = self.selection(['src-web-appended/index.html'], kernel_descriptor=descriptor,
                                  payload_requirements=requirements)
        self.assertTrue(accepted['retained_eligible'])
        self.assertEqual('project-profile-and-explicit-package-requirements', accepted['requirement_checks'])
        self.assertTrue(accepted['package_requirements_checked'])
        for changed, reason in (({'abi': {'major': 1, 'minor': 0}}, 'Kernel ABI is incompatible'),
                                ({'services': []}, 'missing required services'),
                                ({'capabilities': []}, 'missing required capabilities')):
            with self.subTest(changed=changed):
                rejected = self.selection(['src-web-appended/index.html'],
                                          kernel_descriptor=dict(descriptor, **changed),
                                          payload_requirements=requirements)
                self.assertTrue(rejected['maintenance_required'])
                self.assertFalse(any(rejected[field] for field in ('build', 'gui', 'retained_eligible')))
                self.assertFalse(rejected['package_requirements_checked'])
                self.assertIn(reason, rejected['reason'])

    def test_malformed_explicit_package_requirements_are_rejected_without_native_work(self):
        for requirements in ({}, {'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': [], 'unknown': 1},
                             {'abi': {'major': 1, 'minor': 0}, 'services': ['same', 'same'], 'capabilities': []}):
            with self.subTest(requirements=requirements):
                result = self.selection(['src-web-appended/index.html'], kernel_descriptor=self.descriptor,
                                        payload_requirements=requirements)
                self.assertTrue(result['maintenance_required'])
                self.assertFalse(any(result[field] for field in ('build', 'gui', 'retained_eligible')))
                self.assertIn('retained kernel contract is incompatible', result['reason'])

    def test_known_mixed_payload_and_product_changes_use_retained_feedback(self):
        self.write('src-web-appended/index.html', '<h1>Updated product</h1>')
        self.write('src-bin-appended/main.c', 'int app_step(void) { return 1; }')
        self.document['application']['name'] = 'Renamed product'
        self.configure()
        result = self.selection(['src-web-appended/index.html', 'src-bin-appended/main.c',
                                 'foundation-project.json'], kernel_descriptor=self.descriptor)
        self.assertEqual('appended', result['scope'])
        self.assertFalse(any(result[field] for field in ('build', 'gui', 'maintenance_required')))
        self.assertTrue(result['retained_eligible'])
        self.assertEqual('project-profile-and-baseline-abi-only', result['requirement_checks'])
        self.assertFalse(result['package_requirements_checked'])
        self.assertEqual('not-run', result['payload_execution'])
        self.assertEqual('development-feedback-only', result['qualification'])
        self.assertIn('appended_policy', result['tool_suites'])
        self.assertTrue({'web-check', 'guest-compile', 'compose'} <= set(result['actions']))

    def test_metadata_narrative_and_tests_select_tooling_without_kernel_work(self):
        self.write('README.md', 'Downstream project author')
        self.write('LICENSE', 'New application license; original kernel notices stay pinned')
        self.write('docs/new-guide.md', 'New application guide')
        self.write('.agent-pending/new-phase.md', 'Further qualification remains pending')
        self.write('tests/test_source_identity.py', '# changed pure tooling regression')
        self.write('tests/new_runtime_test.cpp', '// separate test harness')
        paths = ['README.md', 'LICENSE', 'docs/new-guide.md', '.agent-pending/new-phase.md',
                 'tests/test_source_identity.py', 'tests/new_runtime_test.cpp']
        result = self.selection(paths, kernel_descriptor=self.descriptor)
        self.assertEqual('appended', result['scope'])
        self.assertFalse(result['build'])
        self.assertFalse(result['gui'])
        self.assertIn('source_identity', result['tool_suites'])
        self.assertEqual(['tests/new_runtime_test.cpp'], result['test_tooling_required'])
        self.assertIn('documentation-check', result['actions'])
        self.assertNotIn('guest-compile', result['actions'])

    def test_missing_or_changed_kernel_inputs_never_fall_back_to_native_builds(self):
        for name in ('src/main.cpp', 'unknown.input'):
            with self.subTest(path=name):
                path = self.write(name, 'changed kernel or unknown input')
                result = self.selection([name], kernel_descriptor=self.descriptor)
                self.assertEqual('appended-maintenance', result['scope'])
                self.assertFalse(any(result[field] for field in ('build', 'gui', 'retained_eligible')))
                self.assertTrue(result['maintenance_required'])
                self.assertIn(name, [item['path'] for item in result['kernel_inputs']['differences']])
                if name == 'src/main.cpp': self.write(name, 'kernel implementation')
                else: path.unlink()
        missing = self.selection(['src-web-appended/index.html'])
        self.assertTrue(missing['maintenance_required'])
        self.assertFalse(missing['build'])
        self.assertIn('pinned', missing['reason'])

    def test_unavailable_history_uses_actual_inventory_without_subprocess_builds(self):
        with patch.object(ci, 'changed_paths', side_effect=ValueError('upstream object absent')), \
                patch.object(ci.subprocess, 'run', side_effect=AssertionError('no subprocess fallback')):
            result = ci.select(self.root, 'push', {}, '', kernel_descriptor=self.descriptor)
        self.assertEqual('appended', result['scope'])
        self.assertIn('complete pinned', result['comparison_history'])
        self.assertFalse(result['build'])

    def test_dirty_kernel_edit_is_seen_even_when_git_reports_only_payload(self):
        self.write('src/main.cpp', 'uncommitted kernel implementation edit')
        result = self.selection(['src-web-appended/index.html'], kernel_descriptor=self.descriptor)
        self.assertTrue(result['maintenance_required'])
        self.assertEqual([{'path': 'src/main.cpp', 'changes': ['content']}],
                         result['kernel_inputs']['differences'])

    def test_selected_component_source_and_insulation_failures_are_conclusive(self):
        (self.root / 'src-web-appended/index.html').unlink()
        missing = self.selection(['src-web-appended/index.html'], kernel_descriptor=self.descriptor)
        self.assertTrue(missing['maintenance_required'])
        self.assertIn('source checks unavailable', missing['reason'])
        self.write('src-web-appended/index.html', '<script>navigator.serial.requestPort()</script>')
        violation = self.selection(['src-web-appended/index.html'], kernel_descriptor=self.descriptor)
        self.assertTrue(violation['maintenance_required'])
        self.assertFalse(violation['insulation']['ok'])
        self.assertFalse(violation['build'])

    def test_disabled_payload_tree_does_not_become_a_source_prerequisite(self):
        self.document['appended']['web']['enabled'] = False
        self.document['startup']['primary'] = 'binary'
        self.configure()
        shutil.rmtree(self.root / 'src-web-appended')
        result = self.selection(['foundation-project.json'], kernel_descriptor=self.descriptor)
        self.assertEqual('appended', result['scope'])
        self.assertEqual('binary', result['mode'])

    def test_disabled_binary_changes_do_not_schedule_guest_compilation(self):
        self.document['appended']['binary']['enabled'] = False
        self.configure()
        result = self.selection(['src-bin-appended/main.c'], kernel_descriptor=self.descriptor)
        self.assertEqual('appended', result['scope'])
        self.assertEqual('web', result['mode'])
        self.assertEqual([], result['actions'])

    def test_guest_tool_and_sdk_changes_select_separate_checks_without_implicit_compilation(self):
        changed = ['tools/appended_compile.py', 'sdk/appended/guest.c', 'sdk/appended/README.md']
        for name in changed: self.write(name, 'changed guest-only code or instructions')
        for mode in ('both', 'web'):
            with self.subTest(mode=mode):
                self.document['appended']['binary']['enabled'] = mode == 'both'
                self.configure()
                result = self.selection(changed, kernel_descriptor=self.descriptor)
                self.assertEqual('appended', result['scope'])
                self.assertFalse(result['build'])
                self.assertFalse(result['gui'])
                self.assertNotIn('guest-compile', result['actions'])
                self.assertTrue({'guest-tooling-check', 'sdk-insulation', 'binding-conformance'} <= set(result['actions']))
                self.assertIn('appended_compile', result['tool_suites'])
                if mode == 'both':
                    self.assertIn('module-source-identity-check', result['actions'])
                    self.assertIn('module-check', result['actions'])
                else:
                    self.assertNotIn('module-source-identity-check', result['actions'])
                    self.assertNotIn('module-check', result['actions'])
        (self.root / 'foundation-project.json').unlink()
        inactive = self.selection(changed)
        self.assertEqual('appended-inactive', inactive['scope'])
        self.assertFalse(inactive['retained_eligible'])
        self.assertFalse(inactive['build'])
        self.assertNotIn('guest-compile', inactive['actions'])
        self.assertNotIn('module-check', inactive['actions'])

    def test_inactive_sdk_audit_rejects_script_glue_without_inspecting_disabled_payloads(self):
        (self.root / 'foundation-project.json').unlink()
        self.write('sdk/appended/guest.c', 'int guest_runtime(void) { return 0; }')
        self.write('src-bin-appended/disabled.js', 'forbidden inactive source is not a prerequisite')
        self.write('src-web-appended/disabled.js', 'navigator.serial.requestPort()')
        changed = ['sdk/appended/guest.c', 'tools/ci_changes.py']
        with patch.object(ci.subprocess, 'run', side_effect=AssertionError('no compiler or child process')):
            valid = self.selection(changed)
        self.assertEqual('appended-inactive', valid['scope'])
        self.assertTrue(valid['insulation']['ok'])
        self.assertEqual(1, valid['insulation']['files_scanned'])
        self.assertNotIn('compose', valid['actions'])
        self.assertNotIn('guest-compile', valid['actions'])
        self.write('sdk/appended/guest.c', 'EM_JS(int, application, (), { return 1; });')
        with patch.object(ci.subprocess, 'run', side_effect=AssertionError('no compiler or child process')):
            invalid = self.selection(changed)
        self.assertEqual('appended-maintenance', invalid['scope'])
        self.assertFalse(invalid['insulation']['ok'])
        self.assertFalse(invalid['build'])
        self.assertFalse(invalid['retained_eligible'])
        self.assertEqual('sdk/appended/guest.c', invalid['insulation']['violations'][0]['path'])

    def test_web_edits_do_not_compile_binary_while_real_binary_edits_can(self):
        web = self.selection(['src-web-appended/index.html'], kernel_descriptor=self.descriptor)
        self.assertEqual('appended', web['scope'])
        self.assertNotIn('guest-compile', web['actions'])
        binary = self.selection(['src-bin-appended/main.c'], kernel_descriptor=self.descriptor)
        self.assertIn('guest-compile', binary['actions'])
        self.assertFalse(binary['build'])
        with patch.object(ci, 'changed_paths', side_effect=ValueError('history absent')):
            uncertain = ci.select(self.root, 'push', {}, '', kernel_descriptor=self.descriptor)
        self.assertEqual('appended', uncertain['scope'])
        self.assertIn('module-source-identity-check', uncertain['actions'])
        self.assertNotIn('guest-compile', uncertain['actions'])

    def test_unknown_sdk_or_shared_abi_changes_still_require_maintenance(self):
        for name in ('sdk/appended/new_runtime.c', 'sdk/appended/extra/README.md',
                     'include/foundation/appended/abi.h', 'abi/appended/v1/bootstrap.json',
                     'tools/appended_wasm.py'):
            with self.subTest(path=name):
                path = self.write(name, 'unclassified or shared kernel input')
                result = self.selection([name], kernel_descriptor=self.descriptor)
                self.assertEqual('appended-maintenance', result['scope'])
                self.assertFalse(result['build'])
                self.assertFalse(result['retained_eligible'])
                path.unlink()

    def test_neither_mode_native_edit_preserves_conventional_feedback(self):
        self.document['appended']['web']['enabled'] = False
        self.document['appended']['binary']['enabled'] = False
        self.document['startup']['primary'] = 'compiled'
        self.configure()
        result = self.selection(['src/main.cpp'])
        self.assertEqual('full', result['scope'])
        self.assertTrue(result['build'])

    def test_inactive_payload_only_changes_omit_builds_without_claiming_reuse(self):
        for configured in (True, False):
            with self.subTest(configured=configured):
                self.document['appended']['web']['enabled'] = False
                self.document['appended']['binary']['enabled'] = False
                self.document['startup']['primary'] = 'compiled'
                self.configure()
                if not configured: (self.root / 'foundation-project.json').unlink()
                with patch.object(ci, 'run_tool_suites', side_effect=AssertionError('selector cannot launch tools')):
                    result = self.selection(['src-web-appended/index.html', 'src-bin-appended/main.c'])
                self.assertEqual('appended-inactive', result['scope'])
                self.assertFalse(any(result[field] for field in ('build', 'gui', 'retained_eligible',
                                                                 'composition_requested', 'maintenance_required')))
                self.assertNotIn('guest-compile', result['actions'])
                self.assertNotIn('compose', result['actions'])
                self.assertIn('appended_policy', result['tool_suites'])
                mixed = self.selection(['src-web-appended/index.html', 'src/main.cpp'])
                self.assertEqual('full', mixed['scope'])
                self.assertTrue(mixed['build'])

    def test_inactive_payload_and_known_metadata_test_changes_keep_tooling_scope(self):
        (self.root / 'foundation-project.json').unlink()
        result = self.selection(['src-bin-appended/main.c', 'README.md', 'docs/new-guide.md',
                                 'tests/test_ci_changes.py', 'gui/tests/new_event_test.cpp'])
        self.assertEqual('appended-inactive', result['scope'])
        self.assertFalse(result['build'])
        self.assertFalse(result['retained_eligible'])
        self.assertIn('ci_changes', result['tool_suites'])
        self.assertEqual(['gui/tests/new_event_test.cpp'], result['test_tooling_required'])
        self.assertNotIn('guest-compile', result['actions'])
        self.assertEqual('full', self.selection(['src-bin-appended/main.c', 'docs/unknown-policy.json'])['scope'])

    def test_inactive_missing_tool_inventory_fails_without_native_fallback(self):
        (self.root / 'foundation-project.json').unlink()
        with patch.object(ci, 'appended_suites', side_effect=ValueError('tool inventory unavailable')):
            result = self.selection(['src-bin-appended/main.c'])
        self.assertEqual('appended-maintenance', result['scope'])
        self.assertTrue(result['maintenance_required'])
        self.assertFalse(result['build'])

    def test_invalid_project_or_bad_pin_is_maintenance_without_kernel_fallback(self):
        self.write('foundation-project.json', '{invalid')
        result = self.selection(['foundation-project.json'], kernel_descriptor=self.descriptor)
        self.assertEqual('appended-maintenance', result['scope'])
        self.assertFalse(result['build'])
        self.assertIn('invalid appended project', result['reason'])
        self.configure()
        result = self.selection([], appended=True, appended_error='kernel descriptor pin mismatch')
        self.assertTrue(result['maintenance_required'])
        self.assertEqual('kernel descriptor pin mismatch', result['reason'])

    def test_cli_maintenance_emits_false_build_outputs_then_fails(self):
        output = self.root.parent / 'outputs'
        summary = self.root.parent / 'summary'
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/ci_changes.py'),
                                 '--root', str(self.root), '--github-output', str(output),
                                 '--summary', str(summary)], capture_output=True, text=True, timeout=20)
        self.assertEqual(1, result.returncode)
        self.assertEqual('appended-maintenance', json.loads(result.stdout)['scope'])
        self.assertIn('build=false', output.read_text().splitlines())
        self.assertIn('gui=false', output.read_text().splitlines())
        self.assertIn('maintenance_required=true', output.read_text().splitlines())
        self.assertIn('no native or shared-GUI fallback build', summary.read_text())
        self.assertIn('does not qualify', summary.read_text())

    def test_cli_authenticates_descriptor_before_retained_feedback(self):
        import appended_container as container
        manifest = self.root.parent / 'kernel.json'
        manifest.write_bytes(container.canonical_json(self.descriptor))
        pin = container.digest(manifest.read_bytes())
        command = [sys.executable, '-B', str(ROOT / 'tools/ci_changes.py'), '--root', str(self.root),
                   '--kernel-descriptor', str(manifest), '--kernel-descriptor-sha256']
        accepted = subprocess.run([*command, pin], capture_output=True, text=True, timeout=20)
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertEqual('appended', json.loads(accepted.stdout)['scope'])
        rejected = subprocess.run([*command, 'f' * 64], capture_output=True, text=True, timeout=20)
        self.assertEqual(1, rejected.returncode)
        result = json.loads(rejected.stdout)
        self.assertEqual('appended-maintenance', result['scope'])
        self.assertFalse(result['build'])
        self.assertIn('independently pinned', result['reason'])


class FeedbackWorkflowTests(unittest.TestCase):
    def test_feedback_has_conclusive_gate_and_no_workflow_path_filter(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertNotIn('paths-ignore:', workflow)
        self.assertNotIn('paths:', workflow.split('permissions:', 1)[0])
        for name, end in (('focused', 'workflow-syntax'), ('workflow-syntax', 'shared-gui')):
            block = workflow.split('  ' + name + ':\n', 1)[1].split('  ' + end + ':\n', 1)[0]
            self.assertIn('    needs: [retained-selection]', block)
            self.assertIn('    if: ${{ always() }}', block)
            self.assertIn('run: test "$SELECTION_RESULT" = success', block)
            self.assertIn('id: changes', block)
            self.assertIn('test "$SELECTED" = true || test "$SELECTED" = false', block)
            self.assertIn('fetch-depth: 2', block)
        self.assertIn('Focused checks (not release qualification)', workflow)
        tooling = workflow.split('  changed-tools:\n')[1]
        self.assertIn('    needs: [retained-selection]', tooling)
        self.assertIn('    if: ${{ always() }}', tooling)
        self.assertIn('run: test "$SELECTION_RESULT" = success', tooling)
        self.assertIn('--run-tool-suites --tool-jobs auto', tooling)
        self.assertIn("steps.changes.outputs.tools == 'true'", tooling)
        self.assertIn('uses: ./.github/actions/ci-evidence-publish', tooling)
        self.assertEqual(workflow.count("if: steps.changes.outputs.gui == 'true'"), 2)
        self.assertIn('Prepare distribution Rust host tools', workflow)
        gui = workflow.split("  shared-gui:\n", 1)[1]
        self.assertIn("--gui --gui-backends", gui)
        self.assertNotIn("FOUNDATION_GUI_GROUP", gui)
        self.assertNotIn("lifecycle.py gui-input", gui)
        self.assertNotIn("GH_TOKEN", gui)
        self.assertIn('python3 -B tools/check_docs.py', workflow)

    def test_retained_feedback_acquires_once_and_reuses_one_pin_in_all_conclusive_jobs(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        acquisition = workflow.split('  retained-selection:\n', 1)[1].split('  focused:\n', 1)[0]
        self.assertEqual(1, workflow.count('python3 -B tools/appended_ci.py'))
        self.assertIn('GH_TOKEN: ${{ github.token }}', acquisition)
        self.assertNotIn('secrets.', acquisition)
        self.assertIn('path: build/appended-feedback/descriptor.json', acquisition)
        self.assertNotIn('tools/build.py', acquisition)
        for name, end in (('focused', 'workflow-syntax'), ('workflow-syntax', 'shared-gui'),
                          ('shared-gui', 'changed-tools'), ('changed-tools', None)):
            with self.subTest(job=name):
                block = workflow.split('  ' + name + ':\n', 1)[1]
                if end: block = block.split('  ' + end + ':\n', 1)[0]
                self.assertIn('    needs: [retained-selection]', block)
                self.assertIn('    if: ${{ always() }}', block)
                self.assertLess(block.index('run: test "$SELECTION_RESULT" = success'),
                                block.index('actions/checkout@'))
                self.assertIn("if: needs.retained-selection.outputs.retained == 'true'", block)
                self.assertIn('actions/download-artifact@', block)
                self.assertIn('DESCRIPTOR_SHA256: ${{ needs.retained-selection.outputs.descriptor_sha256 }}', block)
                self.assertIn('FOUNDATION_APPENDED_KERNEL_DESCRIPTOR=$GITHUB_WORKSPACE/build/appended-feedback/descriptor.json', block)
                self.assertIn('FOUNDATION_APPENDED_KERNEL_DESCRIPTOR_SHA256=$DESCRIPTOR_SHA256', block)
                self.assertIn('>> "$GITHUB_ENV"', block)
                self.assertNotIn('GH_TOKEN', block)

    def test_package_consumers_are_isolated_and_depend_only_on_own_producer(self):
        workflow = (ROOT / '.github/workflows/candidate.yml').read_text()
        caller = workflow.split('  package:\n', 1)[1].split('  sanitizer:\n', 1)[0]
        self.assertIn('matrix: ${{ fromJSON(needs.plan.outputs.packages) }}', caller)
        self.assertIn('uses: ./.github/workflows/candidate-package.yml', caller)
        self.assertIn('fail-fast: false', caller)
        self.assertNotIn('  copied:\n', workflow)
        verdict = workflow.split('  verdict:\n', 1)[1]
        self.assertIn('    - package\n', verdict)
        pair = (ROOT / '.github/workflows/candidate-package.yml').read_text()
        producer, consumer = pair.split('  copied:\n', 1)
        self.assertIn('    needs: package\n', consumer)
        self.assertNotIn('matrix:', pair)
        self.assertIn('runs-on: ${{ inputs.runner }}', producer)
        self.assertIn('runs-on: ${{ inputs.runner }}', consumer)
        self.assertIn('actions/checkout@', consumer)
        self.assertIn('--runtime-only', consumer)
        self.assertIn('uses: ./.github/actions/ci-evidence-publish', producer)
        self.assertIn('name: package-${{ inputs.target }}-${{ github.run_attempt }}', producer)
        self.assertIn('uses: ./.github/actions/ci-evidence-download', consumer)
        self.assertIn('pattern: package-${{ inputs.target }}', consumer)
        self.assertIn('BUNDLE_NAME: package-${{ inputs.target }}-${{ github.run_attempt }}', consumer)


if __name__ == '__main__':
    unittest.main()
