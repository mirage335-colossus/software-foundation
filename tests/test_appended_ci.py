"""Retained feedback acquisition is explicit, pinned and never a build route."""
from contextlib import ExitStack
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_ci as ci
import appended_container as container
import appended_policy as policy
import appended_project as project


def document(path, value):
    path.write_bytes(container.canonical_json(value))


class FeedbackInputsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'checkout'
        (self.root / '.github').mkdir(parents=True)
        (self.root / 'build').mkdir()
        (self.root / 'src-web-appended').mkdir()
        (self.root / 'src-web-appended/index.html').write_text('<p>app</p>')
        self.config = project.default_document()
        self.config['appended']['web'].update(enabled=True, entry='index.html')
        self.config['startup']['primary'] = 'web'
        self.save_config()
        self.group = self.base / 'original-group'
        self.group.mkdir()
        prefix = b'<!doctype html>' + container.HTML_MARKER
        self.descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'html',
            'profile': 'web', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
            'capabilities': [], 'services': [],
            'executable': {'length': len(prefix), 'sha256': container.digest(prefix)},
            'boundary_offset': None, 'provenance': {'producer': 'original',
            'qualification': 'unqualified-development'},
            'kernel_inputs': policy.kernel_source_tree(self.root)}
        document(self.group / 'kernel.json', self.descriptor)
        self.selection = {'schema_version': 1, 'kind': 'foundation-appended-selection',
            'application': self.config['application'], 'source': self.reference('source.tar.gz', source=True),
            'payload': None, 'kernels': [self.kernel('other'), self.kernel('chosen')]}
        self.selection['kernels'][0]['descriptor'] = self.reference('other.json')
        self.request = {'schema_version': 1, 'kind': ci.REQUEST_KIND,
            'source_repository': 'upstream/source', 'source_tag': 'base-v1',
            'source_release_id': 77, 'source_commit': 'a' * 40, 'asset': 'retained.tar.gz',
            'asset_sha256': 'b' * 64, 'selection_sha256': '', 'kernel_id': 'chosen'}
        self.save_selection()
        self.save_request()
        self.output = self.root / 'build/feedback'
        self.calls = []
        self.after_fetch = None
        # Even an accidental new subprocess path must fail these pure fixtures.
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name in ('Popen', 'run', 'check_call', 'check_output', 'call'):
            stack.enter_context(patch.object(subprocess, name, side_effect=AssertionError('process forbidden')))
        stack.enter_context(patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden')))

    def reference(self, name, *, source=False):
        value = {'path': name, 'sha256': 'c' * 64}
        if source:
            value['tree_sha256'] = 'd' * 64
        return value

    def kernel(self, name):
        return {'id': name, 'archive': self.reference('base.tar.gz'),
            'inventory': self.reference('inventory.json'),
            'descriptor': {'path': 'kernel.json', 'sha256': container.digest((self.group / 'kernel.json').read_bytes())},
            'runtime_member': 'bin/application.html', 'output': name + '.tar.gz',
            'original_source': self.reference('source.tar.gz', source=True),
            'recovery': [self.reference('recovery.tar.gz')], 'evidence': []}

    def save_config(self):
        document(self.root / project.CONFIG_NAME, self.config)

    def save_selection(self):
        document(self.group / 'selection.json', self.selection)
        if hasattr(self, 'request'):
            self.request['selection_sha256'] = container.digest((self.group / 'selection.json').read_bytes())

    def save_request(self):
        document(self.root / ci.REQUEST_PATH, self.request)

    def fetch(self, *args):
        self.calls.append(args)
        shutil.copytree(self.group, args[-1])
        if self.after_fetch:
            self.after_fetch(Path(args[-1]))
        return {'schema_version': 1, 'kind': 'mock-authenticated-acquisition', 'original': True}

    def prepare(self):
        return ci.prepare_feedback(self.root, self.output, fetch=self.fetch)

    def test_selected_second_kernel_exports_exact_original_bytes_once(self):
        original = (self.group / 'kernel.json').read_bytes()
        result = self.prepare()
        self.assertTrue(result['retained'])
        self.assertEqual(result['kernel_id'], 'chosen')
        self.assertEqual(result['descriptor'], str(self.output / 'descriptor.json'))
        self.assertEqual(result['descriptor_sha256'], container.digest(original))
        self.assertEqual((self.output / 'descriptor.json').read_bytes(), original)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][:-1], ('upstream/source', 'base-v1', 77, 'a' * 40,
                         'retained.tar.gz', 'b' * 64, self.request['selection_sha256']))
        self.assertEqual((self.group / 'kernel.json').read_bytes(), original)
        self.assertEqual(result['qualification'], 'development-feedback-only')

    def test_default_fetch_is_existing_authenticated_read_only_route(self):
        with patch.object(ci.release, 'fetch_inputs', side_effect=self.fetch) as fetch:
            result = ci.prepare_feedback(self.root, self.output)
        self.assertTrue(result['retained'])
        fetch.assert_called_once()

    def test_ordinary_or_explicit_minimal_never_reads_request_or_fetches(self):
        self.config['appended']['web']['enabled'] = False
        self.config['appended']['web'].pop('entry')
        self.config['startup']['primary'] = 'compiled'
        for configured in (False, True):
            with self.subTest(configured=configured):
                self.save_config()
                if not configured:
                    (self.root / project.CONFIG_NAME).unlink()
                (self.root / ci.REQUEST_PATH).write_bytes(b'invalid request deliberately ignored')
                with patch.object(ci.release, 'fetch_inputs', side_effect=AssertionError('fetch forbidden')):
                    result = ci.prepare_feedback(self.root, self.output)
                self.assertFalse(result['retained'])
                self.assertIsNone(result['descriptor'])
                self.assertFalse(self.output.exists())

    def test_active_and_nonminimal_without_request_fail_before_acquisition(self):
        (self.root / ci.REQUEST_PATH).unlink()
        for mode in ('web', 'neither-web-kernel'):
            with self.subTest(mode=mode):
                if mode.startswith('neither'):
                    self.config['appended']['web']['enabled'] = False
                    self.config['appended']['web'].pop('entry')
                    self.config['startup']['primary'] = 'compiled'
                    self.config['kernel']['profile'] = 'web'
                    self.save_config()
                with self.assertRaisesRegex(ValueError, 'no kernel build fallback'):
                    self.prepare()
                self.assertEqual(self.calls, [])
                self.assertFalse(self.output.exists())

    def test_malformed_request_never_acquires(self):
        for raw in (b'{', b'[]', b'\xef\xbb\xbf{}', b'{"schema_version":1,"schema_version":1}'):
            with self.subTest(raw=raw):
                (self.root / ci.REQUEST_PATH).write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.prepare()
        self.assertEqual(self.calls, [])

    def test_request_rejects_unknown_missing_and_typed_coordinate_errors(self):
        original = copy.deepcopy(self.request)
        mutations = [('schema_version', True), ('schema_version', 2), ('kind', 'selection'),
            ('source_repository', 'https://github.com/a/b'), ('source_repository', 'a/../b'),
            ('source_tag', '../tag'), ('source_release_id', True), ('source_release_id', 0),
            ('source_release_id', '77'), ('source_commit', 'A' * 40), ('source_commit', '0' * 40),
            ('asset', '../group.tar.gz'), ('asset', 'CON'), ('asset_sha256', 'B' * 64),
            ('selection_sha256', '0' * 64), ('kernel_id', 'a/b')]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                bad = dict(original, **{key: value})
                with self.assertRaises(ValueError):
                    ci.validate_request(bad)
        for key in original:
            with self.subTest(missing=key), self.assertRaises(ValueError):
                ci.validate_request({k: v for k, v in original.items() if k != key})
        with self.assertRaises(ValueError):
            ci.validate_request(dict(original, token='forbidden credential field'))
        self.assertEqual(self.calls, [])

    def test_oversized_request_fails_before_acquisition(self):
        (self.root / ci.REQUEST_PATH).write_bytes(b' ' * (ci.REQUEST_LIMIT + 1))
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(self.calls, [])

    def test_linked_and_dangling_request_are_not_absence(self):
        path = self.root / ci.REQUEST_PATH
        path.unlink()
        for target in (self.group / 'selection.json', self.base / 'absent'):
            with self.subTest(target=target):
                path.symlink_to(target)
                try:
                    with self.assertRaisesRegex(ValueError, 'Linked'):
                        self.prepare()
                finally:
                    path.unlink()
        self.assertEqual(self.calls, [])

    def test_changed_selection_pin_fails_without_descriptor_export(self):
        self.request['selection_sha256'] = 'e' * 64
        self.save_request()
        with self.assertRaisesRegex(ValueError, 'selection differs'):
            self.prepare()
        self.assertFalse((self.output / 'descriptor.json').exists())

    def test_missing_requested_or_duplicate_kernel_ids_rejected(self):
        original = copy.deepcopy(self.selection)
        for mutation in ('absent', 'duplicate'):
            with self.subTest(mutation=mutation):
                selected = copy.deepcopy(original)
                selected['kernels'][1]['id'] = 'absent' if mutation == 'absent' else 'other'
                with self.assertRaisesRegex(ValueError, 'absent|duplicate'):
                    ci.select_kernel(selected, 'chosen')

    def test_all_unselected_entry_and_reference_shapes_are_validated(self):
        for mutation in ('unknown', 'path', 'pin', 'recovery', 'source', 'output'):
            with self.subTest(mutation=mutation):
                selected = copy.deepcopy(self.selection)
                row = selected['kernels'][0]
                if mutation == 'unknown': row['unexpected'] = 1
                elif mutation == 'path': row['archive']['path'] = '../base'
                elif mutation == 'pin': row['inventory']['sha256'] = 'bad'
                elif mutation == 'recovery': row['recovery'] = []
                elif mutation == 'source': row['original_source'].pop('tree_sha256')
                elif mutation == 'output': row['output'] = 'bad.zip'
                with self.assertRaises(ValueError):
                    ci.select_kernel(selected, 'chosen')

    def test_strict_selection_top_level_and_reference_shapes(self):
        for change in ('kind', 'bool-version', 'unknown', 'application', 'source', 'payload', 'empty', 'too-many'):
            with self.subTest(change=change):
                value = copy.deepcopy(self.selection)
                if change == 'kind': value['kind'] = ci.REQUEST_KIND
                elif change == 'bool-version': value['schema_version'] = True
                elif change == 'unknown': value['kernel_id'] = 'chosen'
                elif change == 'application': value['application'] = {}
                elif change == 'source': value['source']['path'] = '/absolute'
                elif change == 'payload': value['payload'] = {'path': 'p'}
                elif change == 'empty': value['kernels'] = []
                elif change == 'too-many': value['kernels'] *= 17
                with self.assertRaises(ValueError):
                    ci.select_kernel(value, 'chosen')

    def test_descriptor_mismatch_does_not_export(self):
        (self.group / 'kernel.json').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'descriptor differs'):
            self.prepare()
        self.assertFalse((self.output / 'descriptor.json').exists())

    def test_descriptor_symlink_and_oversize_are_rejected(self):
        original = (self.group / 'kernel.json').read_bytes()
        for variant in ('link', 'oversized'):
            with self.subTest(variant=variant):
                if self.output.exists(): shutil.rmtree(self.output)
                path = self.group / 'kernel.json'
                path.unlink()
                if variant == 'link':
                    (self.base / 'real.json').write_bytes(original)
                    path.symlink_to(self.base / 'real.json')
                    def linked_copy(*args):
                        shutil.copytree(self.group, args[-1], symlinks=True)
                        return {}
                    fetch = linked_copy
                else:
                    path.write_bytes(b'x' * (container.MAX_INDEX + 1))
                    fetch = self.fetch
                with self.assertRaises(ValueError):
                    ci.prepare_feedback(self.root, self.output, fetch=fetch)
                self.assertFalse((self.output / 'descriptor.json').exists())

    def test_descriptor_requires_valid_complete_kernel_input_inventory(self):
        for inputs in (None, {}, {'schema_version': 999}):
            with self.subTest(inputs=inputs):
                if self.output.exists(): shutil.rmtree(self.output)
                self.descriptor['kernel_inputs'] = inputs
                document(self.group / 'kernel.json', self.descriptor)
                self.selection['kernels'][1]['descriptor']['sha256'] = container.digest((self.group / 'kernel.json').read_bytes())
                self.save_selection(); self.save_request()
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse((self.output / 'descriptor.json').exists())

    def test_acquisition_failure_has_no_export_or_retry(self):
        fetch = Mock(side_effect=ValueError('authenticated input unavailable'))
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            ci.prepare_feedback(self.root, self.output, fetch=fetch)
        fetch.assert_called_once()
        self.assertFalse((self.output / 'descriptor.json').exists())

    def test_request_or_project_changed_during_acquisition_blocks_handoff(self):
        for changed in ('request', 'project'):
            with self.subTest(changed=changed):
                if self.output.exists(): shutil.rmtree(self.output)
                self.save_request(); self.save_config()
                def mutate(_):
                    path = self.root / (ci.REQUEST_PATH if changed == 'request' else project.CONFIG_NAME)
                    before = path.read_bytes()
                    after = before.replace(b'chosen', b'CHOSEN', 1) if changed == 'request' else before.replace(b'Foundation', b'FoundatioN', 1)
                    self.assertEqual(len(after), len(before))
                    self.assertNotEqual(after, before)
                    path.write_bytes(after)
                self.after_fetch = mutate
                with self.assertRaisesRegex(ValueError, 'changed'):
                    self.prepare()
                self.assertFalse((self.output / 'descriptor.json').exists())

    def test_existing_output_is_not_reused_or_replaced(self):
        self.output.mkdir()
        (self.output / 'foreign').write_text('preserve')
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual((self.output / 'foreign').read_text(), 'preserve')
        self.assertEqual(self.calls, [])

    def test_cli_ordinary_outputs_explicit_false_without_descriptor_path(self):
        (self.root / project.CONFIG_NAME).unlink()
        outputs, summary = self.base / 'outputs', self.base / 'summary'
        with patch('sys.stdout', new_callable=io.StringIO) as text:
            code = ci.main(['--root', str(self.root), '--output', str(self.output),
                            '--github-output', str(outputs), '--summary', str(summary)])
        self.assertEqual(code, 0)
        self.assertEqual(outputs.read_text(), 'retained=false\ndescriptor_sha256=\n')
        self.assertFalse(json.loads(text.getvalue())['retained'])
        self.assertIn('No kernel build', summary.read_text())

    def test_cli_failure_does_not_emit_success_outputs(self):
        (self.root / ci.REQUEST_PATH).unlink()
        outputs = self.base / 'outputs'
        with patch('sys.stderr', new_callable=io.StringIO) as error:
            code = ci.main(['--root', str(self.root), '--github-output', str(outputs)])
        self.assertEqual(code, 1)
        self.assertIn('no kernel build fallback', error.getvalue())
        self.assertFalse(outputs.exists())


class WorkflowTests(unittest.TestCase):
    def test_one_acquisition_and_descriptor_only_same_run_artifact(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertEqual(text.count('tools/appended_ci.py'), 1)
        self.assertEqual(text.count('actions/download-artifact@'), 4)
        self.assertEqual(text.count('path: build/appended-feedback/descriptor.json'), 1)
        self.assertNotIn('APPENDED_SOURCE_READ_TOKEN', text)
        self.assertIn('GH_TOKEN: ${{ github.token }}', text)
        self.assertEqual(text.count('name: ${{ needs.retained-selection.outputs.artifact_name }}'), 4)
        self.assertIn('artifact_name: ${{ steps.retained.outputs.retained', text)

    def test_all_four_jobs_fail_conclusively_before_selector_on_selection_failure(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        names = ('focused', 'workflow-syntax', 'shared-gui', 'changed-tools')
        for index, name in enumerate(names):
            with self.subTest(job=name):
                start = text.index('\n  ' + name + ':')
                end = text.index('\n  ' + names[index + 1] + ':', start) if index < 3 else len(text)
                block = text[start:end]
                self.assertIn('needs: [retained-selection]', block)
                self.assertIn('if: ${{ always() }}', block)
                self.assertLess(block.index('test "$SELECTION_RESULT" = success'), block.index('tools/ci_changes.py'))
                self.assertIn('if: needs.retained-selection.outputs.retained == \'true\'', block)
                self.assertIn('FOUNDATION_APPENDED_KERNEL_DESCRIPTOR=$GITHUB_WORKSPACE/', block)
                self.assertIn('FOUNDATION_APPENDED_KERNEL_DESCRIPTOR_SHA256=$DESCRIPTOR_SHA256', block)
                self.assertIn('>> "$GITHUB_ENV"', block)
        self.assertEqual(text.count('tools/ci_changes.py'), 5)
        self.assertIn('--run-tool-suites --tool-jobs auto', text)
        self.assertIn('Preserve complete tooling outcome receipts', text)


if __name__ == '__main__':
    unittest.main()
