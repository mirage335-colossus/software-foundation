import copy
import importlib.util
from pathlib import Path
import platform
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_check', Path(__file__).resolve().parents[1] / 'tools/release_check.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ReleaseCheckTests(unittest.TestCase):
    def fixture(self, root):
        machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine().lower(), platform.machine().lower())
        target = platform.system().lower() + '-' + machine
        (root / 'release.json').write_text('{}')
        entry = {'target': target, 'backends': [], 'archive': 'app.tar.gz', 'manifest': 'app.json', 'sha256': 'b' * 64}
        return {'source': {'sha256': 'a' * 64}, 'artifacts': [entry]}, target

    def test_core_empty_gui_inventory_is_an_exact_scope(self):
        value = {'artifacts': [{'target': 'linux-x86_64', 'backends': []}]}
        self.assertIs(check.select(value, 'linux-x86_64', 'core'), value['artifacts'][0])
        for target, backend in [('linux-aarch64', 'core'), ('linux-x86_64', 'fltk')]:
            with self.assertRaises(ValueError):
                check.select(value, target, backend)
        value['artifacts'] *= 2
        with self.assertRaises(ValueError):
            check.select(value, 'linux-x86_64', 'core')

    def test_exact_archive_receipt_and_immutable_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, target = self.fixture(root)
            with patch.object(check.release, 'verify_release', return_value=manifest) as verify, patch.object(check.artifact, 'verify') as runtime:
                result = check.check(root, target, 'core', 'archive', root / 'evidence')
                self.assertEqual(verify.call_count, 2)
                self.assertEqual(runtime.call_args.kwargs['backend'], 'core')
                self.assertTrue(runtime.call_args.kwargs['runtime_only'])
                self.assertEqual(result['source_sha256'], manifest['source']['sha256'])
                self.assertEqual(result['inventory_sha256'], check.digest(root / 'release.json'))
                self.assertEqual(result['host'], check.c.host_identity())
                with self.assertRaisesRegex(ValueError, 'new attempt'):
                    check.check(root, target, 'core', 'archive', root / 'evidence')

    def test_candidate_mutation_or_runtime_failure_never_leaves_pass_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, target = self.fixture(root)
            def mutate(*args, **kwargs):
                (root / 'release.json').write_text('{"changed":true}')
            with patch.object(check.release, 'verify_release', return_value=manifest), patch.object(check.artifact, 'verify', side_effect=mutate):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    check.check(root, target, 'core', 'archive', root / 'evidence')
                self.assertFalse((root / 'evidence/qualification.json').exists())
            with patch.object(check.release, 'verify_release', return_value=manifest), patch.object(check.artifact, 'verify', side_effect=ValueError('runtime failed')):
                with self.assertRaisesRegex(ValueError, 'runtime failed'):
                    check.check(root, target, 'core', 'archive', root / 'failure')
                self.assertFalse((root / 'failure/qualification.json').exists())

    def test_native_scope_rejects_wrong_os_architecture_and_browser(self):
        with patch.object(check.platform, 'system', return_value='Linux'), patch.object(check.platform, 'machine', return_value='x86_64'):
            check.native_target('linux-x86_64')
            for target in ('linux-aarch64', 'windows-x86_64', 'browser-wasm32'):
                with self.assertRaises(ValueError):
                    check.native_target(target)


if __name__ == '__main__':
    unittest.main()
