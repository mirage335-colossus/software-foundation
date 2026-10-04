"""Optional hosted lane policy and fail-closed execution contracts."""
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rust_qualification', ROOT / '.github/scripts/rust_qualification.py')
qualification = importlib.util.module_from_spec(spec); spec.loader.exec_module(qualification)


class RustWorkflowTests(unittest.TestCase):
    def test_explicit_lane_uses_four_native_hosts_and_exact_paired_recipes(self):
        ci = qualification.ci_plan
        recipes = {target: 'a' * 64 for target in ci.RUST_RECIPES}
        result = ci.rust_qualification_matrix(recipes)['include']
        self.assertEqual({row['target'] for row in result}, set(ci.RUST_RECIPES))
        self.assertEqual(next(row['runner'] for row in result if row['target'] == 'linux-aarch64'), 'ubuntu-24.04-arm')
        self.assertTrue(all(row['core_provider'] == 'rust' and len(row['rust_recipe']) == 64 for row in result))
        for broken in ({}, {'linux-x86_64': 'a' * 64}, dict(recipes, unknown='b' * 64)):
            with self.subTest(selection=broken), self.assertRaises(ValueError): ci.rust_qualification_matrix(broken)

    def test_network_acquisition_occurs_only_in_explicit_preparation(self):
        source = ast.parse(Path(qualification.__file__).read_text())
        callers = []
        for function in (item for item in source.body if isinstance(item, ast.FunctionDef)):
            for node in ast.walk(function):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == 'rust_sdk'
                        and node.func.attr == 'fetch'):
                    callers.append(function.name)
                    self.assertTrue(any(item.arg == 'network' and isinstance(item.value, ast.Constant)
                                        and item.value.value is True for item in node.keywords))
        self.assertEqual(callers, ['prepare'])

    def test_boundary_probe_rejects_any_successful_external_connection(self):
        connection = Mock(); connection.__enter__ = Mock(return_value=connection); connection.__exit__ = Mock(return_value=False)
        with patch.object(qualification.socket, 'create_connection', return_value=connection):
            with self.assertRaisesRegex(ValueError, 'allowed an external TCP'): qualification.denial_probe()

    def test_boundary_probe_requires_external_denials_and_working_loopback(self):
        listener = Mock(); listener.__enter__ = Mock(return_value=listener); listener.__exit__ = Mock(return_value=False)
        listener.getsockname.return_value = ('127.0.0.1', 12345)
        accepted = Mock(); listener.accept.return_value = (accepted, ('127.0.0.1', 12346))
        local = Mock(); local.__enter__ = Mock(return_value=local); local.__exit__ = Mock(return_value=False)
        def connect(address, **options):
            if address[0] in ('1.1.1.1', '8.8.8.8'): raise OSError('fixture outbound denial')
            self.assertEqual(address, ('127.0.0.1', 12345))
            return local
        with patch.object(qualification.socket, 'create_connection', side_effect=connect), \
                patch.object(qualification.socket, 'socket', return_value=listener):
            result = qualification.denial_probe()
        self.assertEqual(result['loopback'], 'passed')
        self.assertEqual(len(result['external_tcp_denied']), 2)
        accepted.close.assert_called_once()

    def test_native_windows_boundary_refuses_ordinary_hosts_before_work(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(qualification.platform, 'system', return_value='Windows'), \
                patch.object(qualification, 'selection') as selection:
            with self.assertRaisesRegex(ValueError, 'active disposable hosted firewall'): qualification.windows_offline()
            selection.assert_not_called()

    def test_bounded_windows_owner_joins_all_descendants_after_timeout(self):
        import process_tree
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'build').mkdir()
            owner = Mock(); owner.wait.side_effect = subprocess.TimeoutExpired('fixture', 600)
            with patch.object(qualification, 'ROOT', root), patch.object(process_tree, 'launch', return_value=owner):
                with self.assertRaises(subprocess.TimeoutExpired): qualification.supervise_windows_offline()
            owner.wait.assert_called_once_with(timeout=600)
            owner.close.assert_called_once()
            owner.finish.assert_not_called()

    def test_workflow_retains_authenticated_groups_and_has_no_application_publication(self):
        workflow = (ROOT / '.github/workflows/rust-qualification.yml').read_text()
        self.assertIn("branches: ['codex/rust-*']", workflow)
        self.assertIn('fail-fast: false', workflow)
        self.assertIn('.github/scripts/lifecycle.py bundle-store', workflow)
        self.assertIn('build/rust-recovery/', workflow)
        self.assertNotIn('publish-candidate', workflow)
        self.assertNotIn('promote', workflow)
        self.assertNotIn('ci-evidence-publish', workflow)
        self.assertIn('if: always()', workflow)

    def test_windows_firewall_cleanup_restores_original_profiles(self):
        script = (ROOT / 'tools/rust_windows_offline.ps1').read_text()
        self.assertIn("$env:RUNNER_ENVIRONMENT -ne 'github-hosted'", script)
        self.assertIn('finally {', script)
        cleanup = script.split('} finally {', 1)[1]
        self.assertIn('Remove-NetFirewallRule -Name $taskRuleName', cleanup)
        self.assertIn('Set-NetFirewallProfile -Profile $taskProfile.Name -Enabled $taskProfile.Enabled', cleanup)
        self.assertIn('Compare-Object $taskProfiles $taskAfter -Property Name, Enabled', cleanup)
        self.assertNotIn('Set-NetFirewallProfile -Profile Domain, Private, Public -Enabled False', script)


if __name__ == '__main__': unittest.main()
