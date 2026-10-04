"""Changed-path decisions must preserve feedback when evidence is incomplete."""
import importlib.util
import json
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


    def test_shared_test_fixtures_select_transitive_whole_suite_consumers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'tools').mkdir(); (root/'tests').mkdir()
            (root/'tools/example.py').write_text('')
            (root/'tests/test_fixture.py').write_text('')
            (root/'tests/test_first.py').write_text('from . import test_fixture')
            (root/'tests/test_second.py').write_text('import test_first')
            self.assertEqual(ci.infrastructure_suites(['tests/test_fixture.py'], root), ['first', 'fixture', 'second'])

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


class FeedbackWorkflowTests(unittest.TestCase):
    def test_feedback_has_conclusive_gate_and_no_workflow_path_filter(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertNotIn('paths-ignore:', workflow)
        self.assertNotIn('paths:', workflow.split('permissions:', 1)[0])
        for name, end in (('focused', 'workflow-syntax'), ('workflow-syntax', 'shared-gui')):
            block = workflow.split('  ' + name + ':\n', 1)[1].split('  ' + end + ':\n', 1)[0]
            self.assertNotIn('    needs:', block)
            self.assertIn('id: changes', block)
            self.assertIn('test "$SELECTED" = true || test "$SELECTED" = false', block)
            self.assertIn('fetch-depth: 2', block)
        self.assertIn('Focused checks (not release qualification)', workflow)
        tooling = workflow.split('  changed-tools:\n')[1]
        self.assertNotIn('    needs:', tooling)
        self.assertIn('--run-tool-suites --tool-jobs 2', tooling)
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
