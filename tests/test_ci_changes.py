"""Changed-path decisions must preserve feedback when evidence is incomplete."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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
                         ['build=false', 'gui=false', 'workflow_lint=false', 'scope=documents'])
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
        self.assertNotIn('paths:', workflow)
        for name, end in (('focused', 'workflow-syntax'), ('workflow-syntax', 'shared-gui')):
            block = workflow.split('  ' + name + ':\n', 1)[1].split('  ' + end + ':\n', 1)[0]
            self.assertNotIn('    needs:', block)
            self.assertIn('id: changes', block)
            self.assertIn('test "$SELECTED" = true || test "$SELECTED" = false', block)
            self.assertIn('fetch-depth: 2', block)
        self.assertIn('Focused checks (not release qualification)', workflow)
        self.assertEqual(workflow.count("if: steps.changes.outputs.gui == 'true'"), 2)
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
