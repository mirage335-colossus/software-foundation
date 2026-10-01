"""Complete SDK byte retention does not grant consumer or publication approval."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import dependency_archive as archive
import dependency_store as store
import sdk_windows

spec = importlib.util.spec_from_file_location('retention_lifecycle', ROOT / '.github/scripts/lifecycle.py')
lifecycle = importlib.util.module_from_spec(spec); spec.loader.exec_module(lifecycle)


class SdkRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / 'owned checkout'; self.root.mkdir()
        shutil.copytree(ROOT / 'third_party/sdk', self.root / 'third_party/sdk')
        self.recipe_file = self.root / 'third_party/sdk/windows-base.json'
        self.recipe = sdk_windows.recipe_identity(self.recipe_file)
        self.group = self.root / 'build/sdk-group'
        provenance = json.loads(self.recipe_file.read_text())
        policy = json.loads((self.recipe_file.parent / 'windows-toolchain.json').read_text())
        provenance.update(linker_version='14.44.35207', windows_sdk=policy['windows_sdk'])
        provenance_path = self.root / 'provenance.json'; archive.write_json(provenance_path, provenance)
        sdk_windows.empty_base(self.recipe_file, provenance_path, self.group)
        self.files = store.verify_group(self.group, self.recipe)
        archive.write_json(self.root / 'build/sdk-origin.json', {'origin': 'base', 'recipe': self.recipe})
        self.environment = {'TARGET': 'windows-x86_64', 'SDK_PROFILE': 'core', 'JOBS': '2',
            'GITHUB_SHA': 'a' * 40, 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2',
            'GITHUB_OUTPUT': str(self.root / 'step-output')}
        self.addCleanup(patch.stopall)
        patch.object(lifecycle, 'ROOT', self.root).start()
        previous = Path.cwd(); lifecycle.os.chdir(self.root)
        self.addCleanup(lifecycle.os.chdir, previous)
        patch.dict(lifecycle.os.environ, self.environment).start()
        self.publisher = patch.object(lifecycle.delivery, 'publish_base', side_effect=AssertionError('unexpected publication')).start()

    def receipt(self): return json.loads((self.root / 'build/sdk-retention.json').read_text())

    def test_failed_consumer_keeps_failure_and_complete_group_can_be_retained(self):
        with patch.object(lifecycle.ci, 'assert_host'), \
             patch.object(lifecycle.ci, 'prepared_check', side_effect=RuntimeError('consumer assertion failed')):
            with self.assertRaisesRegex(RuntimeError, 'consumer assertion failed'):
                lifecycle.main('sdk-produce')
        self.assertFalse((self.root / 'build/sdk-publication-plan.json').exists())
        lifecycle.main('sdk-retain')
        receipt = self.receipt()
        self.assertEqual(receipt['files'], self.files)
        self.assertEqual((receipt['status'], receipt['qualification'], receipt['publication_approved']),
                         ('verified', 'unqualified', False))
        self.assertEqual((receipt['target'], receipt['profile'], receipt['recipe_id']),
                         ('windows-x86_64', 'core', self.recipe))
        self.assertEqual((receipt['source_commit'], receipt['run_id'], receipt['attempt']), ('a' * 40, '123', 2))
        self.assertEqual((self.root / 'step-output').read_text(), 'retained=true\n')
        self.assertEqual(store.verify_group(self.group, self.recipe), self.files)
        self.publisher.assert_not_called()

    def test_retained_group_stays_compatible_with_existing_offline_install(self):
        lifecycle.main('sdk-retain')
        copied = self.root / 'relocated group'
        self.assertEqual(store.copy_group(self.group, copied, self.recipe), self.files)
        installed = sdk_windows.install(copied, self.recipe, self.root / 'relocated dependencies', '14.44.35207')
        self.assertEqual(installed['recipe_id'], self.recipe)
        self.assertEqual(installed['target']['system'], 'Windows')
        self.assertEqual(self.receipt()['qualification'], 'unqualified')
        self.publisher.assert_not_called()

    def test_current_recipe_profile_and_origin_are_revalidated(self):
        origin = self.root / 'build/sdk-origin.json'
        for target, profile in [('windows-x86_64', 'all-gui'), ('linux-x86_64', 'core'), ('browser-wasm32', 'core')]:
            with self.subTest(target=target, profile=profile), patch.dict(lifecycle.os.environ, {'TARGET': target, 'SDK_PROFILE': profile}):
                with self.assertRaisesRegex(ValueError, 'selected current recipe'): lifecycle.main('sdk-retain')
        archive.write_json(origin, {'origin': 'base', 'recipe': 'b' * 64})
        with self.assertRaisesRegex(ValueError, 'selected current recipe'): lifecycle.main('sdk-retain')
        archive.write_json(origin, {'origin': 'base', 'recipe': self.recipe})
        self.recipe_file.write_text(self.recipe_file.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'selected current recipe'): lifecycle.main('sdk-retain')
        self.assertFalse((self.root / 'build/sdk-retention.json').exists())
        self.assertFalse((self.root / 'step-output').exists())

    def test_incomplete_or_unexpected_group_files_never_emit_retention_success(self):
        name = store.names(self.recipe)[1]; data = (self.group / name).read_bytes()
        (self.group / name).unlink()
        with self.assertRaisesRegex(ValueError, 'exactly'): lifecycle.main('sdk-retain')
        (self.group / name).write_bytes(data)
        (self.group / 'foreign.txt').write_text('must remain visible')
        with self.assertRaisesRegex(ValueError, 'exactly'): lifecycle.main('sdk-retain')
        self.assertEqual((self.group / 'foreign.txt').read_text(), 'must remain visible')
        self.assertFalse((self.root / 'build/sdk-retention.json').exists())
        self.assertFalse((self.root / 'step-output').exists())

    def test_changed_inner_content_is_rejected_even_with_rewritten_outer_checksums(self):
        binary, source, sums = store.names(self.recipe)
        extracted = self.root / 'changed binary'; archive.extract(self.group / binary, extracted)
        (extracted / 'prefix/README.txt').write_text('changed after sealing')
        (self.group / binary).unlink(); archive.archive_tree(extracted, self.group / binary)
        (self.group / sums).write_text(''.join(archive.digest(self.group / name) + '  ' + name + '\n'
                                             for name in (binary, source)))
        with self.assertRaisesRegex(ValueError, 'manifest'): lifecycle.main('sdk-retain')
        self.assertFalse((self.root / 'build/sdk-retention.json').exists())
        self.assertFalse((self.root / 'step-output').exists())

    def test_refuses_to_replace_existing_receipt(self):
        receipt = self.root / 'build/sdk-retention.json'; receipt.write_text('foreign receipt')
        with self.assertRaises(FileExistsError): lifecycle.main('sdk-retain')
        self.assertEqual(receipt.read_text(), 'foreign receipt')
        self.assertFalse((self.root / 'step-output').exists())

    def test_unknown_target_or_profile_cannot_select_a_fallback_recipe(self):
        for target, profile in [('unknown', 'core'), ('windows-x86_64', 'unknown')]:
            with self.subTest(target=target, profile=profile), self.assertRaisesRegex(ValueError, 'unknown SDK'):
                lifecycle.sdk_identity(target, profile)

    def test_workflow_retains_only_verified_group_without_masking_failure(self):
        text = (ROOT / '.github/workflows/sdk-maintenance.yml').read_text()
        retention = text.split('    - name: Verify complete SDK bytes', 1)[1].split('    - uses:', 1)[0]
        self.assertIn('id: retain', retention); self.assertIn('if: always()', retention)
        self.assertIn('lifecycle.py sdk-retain', retention)
        group = text.split('name: sdk-group-', 1)[0].rsplit('    - uses:', 1)[1]
        self.assertIn("if: always() && steps.retain.outcome == 'success' && steps.retain.outputs.retained == 'true'", group)
        self.assertNotIn('continue-on-error', text)
        publication = text.split('  publish:', 1)[1]
        self.assertIn('    if: inputs.execute\n    needs: produce\n', publication)
        self.assertNotIn('always()', publication.split('    steps:', 1)[0])
        self.assertIn('          build/sdk-retention.json\n', text)
        self.assertIn('sdk_retention', (ROOT / 'CMakeLists.txt').read_text())


if __name__ == '__main__': unittest.main()
