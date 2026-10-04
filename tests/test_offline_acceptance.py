"""Contract/preflight tests; these do not claim an actual offline application run."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import offline_acceptance as acceptance
from dependency_archive import read_json, write_json
from dependency_store import names
import sdk
from test_sdk import fixture


@unittest.skipUnless(sys.platform.startswith('linux'), 'Bookworm acceptance contract requires Linux')
class OfflineAcceptance(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        host = patch.object(acceptance.platform, 'machine', return_value='x86_64')
        host.start(); self.addCleanup(host.stop)
        self.group = self.root / 'group with spaces'; self.group.mkdir()
        self.plan = {'schema_version': 1, 'isolation': {'kind': 'docker', 'image': 'sha256:' + 'f' * 64},
                     'cases': [{'target': 'linux-x86_64', 'group': str(self.group), 'recipe': 'a' * 64},
                               {'target': 'browser-wasm32', 'group': str(self.group), 'recipe': 'b' * 64}]}

    def test_inventory_preserves_supported_hosts_backends_and_distro_route(self):
        contract = acceptance.inventory()
        self.assertEqual(acceptance.validate_plan(self.plan, system='Linux', machine='x86_64'),
                         ['linux-x86_64', 'browser-wasm32'])
        native = contract['native_backends']
        self.assertEqual(len(native), 6)
        for target in contract['targets']:
            self.assertEqual(target['backends'], ['wasm'] if target['target'] == 'browser-wasm32' else native)
            self.assertTrue(target['core_cli'])
        self.assertFalse(contract['ordinary_distribution_route']['retained_sdk_required'])
        self.assertIn('readelf', contract['distribution_host_tools']['native_sdk'])
        self.assertIn('complete Microsoft offline compiler/Windows SDK installer layout and component configuration',
                      next(item for item in contract['targets'] if item['target'] == 'windows-x86_64')['separate_prerequisites'])
        arm = copy.deepcopy(self.plan)
        arm['cases'] = [{'target': 'linux-aarch64', 'group': str(self.group), 'recipe': 'c' * 64}]
        self.assertEqual(acceptance.validate_plan(arm, system='Linux', machine='aarch64'), ['linux-aarch64'])

    def test_plans_reject_tags_shell_fields_duplicates_and_foreign_hosts(self):
        invalid = []
        value = copy.deepcopy(self.plan); value['isolation']['image'] = 'debian:bookworm'; invalid.append(value)
        value = copy.deepcopy(self.plan); value['isolation']['command'] = 'curl supplier'; invalid.append(value)
        value = copy.deepcopy(self.plan); value['cases'][0]['arguments'] = '--online'; invalid.append(value)
        value = copy.deepcopy(self.plan); value['cases'].append(value['cases'][0].copy()); invalid.append(value)
        value = copy.deepcopy(self.plan); value['cases'][0]['recipe'] = 'short'; invalid.append(value)
        value = copy.deepcopy(self.plan); value['cases'][0]['target'] = 'linux-aarch64'; invalid.append(value)
        value = copy.deepcopy(self.plan); value['isolation'] = {'kind': 'none'}; invalid.append(value)
        value = copy.deepcopy(self.plan); value['cases'][0]['group'] = 'relative'; invalid.append(value)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                acceptance.validate_plan(value, system='Linux', machine='x86_64')

    def test_default_requires_wasm_inputs_and_narrow_selection_never_implies_full_inventory(self):
        plan = copy.deepcopy(self.plan); plan['cases'].pop()
        path = self.root / 'plan.json'; write_json(path, plan)
        output = self.root / 'new output'
        with self.assertRaisesRegex(ValueError, 'missing retained inputs'), patch.object(acceptance.subprocess, 'run') as launch:
            acceptance.run(path, output)
        launch.assert_not_called()
        self.assertFalse(output.exists())

    def prepared_fixture(self, *, capabilities=None, processor='x86_64', host_processor='x86_64'):
        recipe, tree, sources, group = fixture(self.root / 'sdk fixture')
        metadata = read_json(tree / 'sdk.json')
        metadata['target']['processor'] = processor
        metadata['capabilities'] = capabilities or acceptance.inventory()['native_backends']
        if host_processor is None:
            metadata['host'].pop('processor')
        else:
            metadata['host']['processor'] = host_processor
        write_json(tree / 'sdk.json', metadata)
        shutil.rmtree(group)
        sdk.export_group(tree, sources, group)
        return {'target': 'linux-x86_64', 'group': str(group), 'recipe': recipe}

    def test_complete_group_integrity_and_capabilities_are_verified_without_repair(self):
        case = self.prepared_fixture()
        result = acceptance.verify_case(case)
        self.assertEqual(set(result['files']), set(names(case['recipe'])))
        (Path(case['group']) / names(case['recipe'])[1]).write_bytes(b'corrupt retained sources')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            acceptance.verify_case(case)
        with self.assertRaisesRegex(ValueError, 'missing|directory'):
            acceptance.verify_case({**case, 'group': str(self.root / 'absent')})

    def test_wrong_native_architecture_and_incomplete_gui_sdk_fail(self):
        for capabilities, machine, message in ((['core', 'terminal'], 'x86_64', 'capabilities'),
                                                (None, 'aarch64', 'architecture')):
            with self.subTest(machine=machine, capabilities=capabilities), tempfile.TemporaryDirectory() as name:
                original = self.root
                self.root = Path(name).resolve()
                try:
                    with self.assertRaisesRegex(ValueError, message):
                        acceptance.verify_case(self.prepared_fixture(capabilities=capabilities, processor=machine))
                finally:
                    self.root = original

    def test_one_tree_per_target_and_existing_build_entrypoint(self):
        output = self.root / 'output'; retained = self.root / 'installed sdk'
        for target in ('linux-x86_64', 'linux-aarch64', 'browser-wasm32'):
            commands = [acceptance.build_arguments(target, retained, output, 3, action) for action in ('build', 'test', 'package')]
            for command in commands:
                self.assertEqual(command[2], str(acceptance.ROOT / 'tools/build.py'))
                self.assertEqual(command[command.index('--build-dir') + 1], str(output / 'build'))
                self.assertEqual(command[command.index('--sdk') + 1], str(retained))
                self.assertIn('--gui', command)
                backends = command[command.index('--gui-backends') + 1].split(',')
                self.assertEqual(backends, ['wasm'] if target == 'browser-wasm32' else acceptance.inventory()['native_backends'])
                self.assertNotIn('--full', command)
            self.assertIn('--label', commands[1])

    def test_missing_sdk_host_architecture_never_defaults_to_the_current_host(self):
        with self.assertRaisesRegex(ValueError, 'different native host'):
            acceptance.verify_case(self.prepared_fixture(host_processor=None))

    def test_output_overlap_is_rejected_before_input_verification_or_writes(self):
        rootfs = self.root / 'prepared rootfs'; rootfs.mkdir()
        manifest = self.root / 'rootfs.json'; manifest.write_text('{}')
        value = copy.deepcopy(self.plan)
        value['isolation'] = {'kind': 'namespace', 'rootfs': str(rootfs), 'manifest': str(manifest), 'manifest_sha256': 'a' * 64}
        path = self.root / 'overlap-plan.json'; write_json(path, value)
        output = rootfs / 'new output'
        with patch.object(acceptance, 'verify_case') as verify, self.assertRaisesRegex(ValueError, 'rootfs must be disjoint'):
            acceptance.run(path, output)
        verify.assert_not_called(); self.assertFalse(output.exists())
        source = self.root / 'application source'; source.mkdir()
        write_json(path, self.plan)
        with patch.object(acceptance, 'verify_case') as verify, self.assertRaisesRegex(ValueError, 'nonignored application source'):
            acceptance.run(path, source / 'new output', root=source)
        verify.assert_not_called(); self.assertFalse((source / 'new output').exists())

    def test_junit_requires_both_core_tests_with_no_skips_failures_or_disabled_cases(self):
        path = self.root / 'core.junit.xml'
        valid = '<testsuite tests="2" failures="0" skipped="0"><testcase name="core.store" status="run"/><testcase name="core.cli" status="run"/></testsuite>'
        path.write_text(valid)
        result = acceptance.verify_core_junit(path)
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['tests'], ['core.cli', 'core.store'])
        invalid = [valid.replace('name="core.cli"', 'name="typo"'),
                   valid.replace('name="core.cli" status="run"/>', 'name="core.cli" status="run"><skipped/></testcase>'),
                   valid.replace('name="core.cli" status="run"/>', 'name="core.cli" status="run"><failure/></testcase>'),
                   valid.replace('status="run"', 'status="notrun"'), valid.replace('skipped="0"', 'skipped="1"')]
        for document in invalid:
            with self.subTest(document=document):
                path.write_text(document)
                with self.assertRaises(ValueError): acceptance.verify_core_junit(path)

    def test_snapshot_contains_only_application_inputs_and_complete_source_identity(self):
        source = self.root / 'checkout'; source.mkdir()
        (source / 'app.py').write_text('retained application\n')
        for name in ('build', '.agent-work', '__pycache__'):
            (source / name).mkdir(); (source / name / 'ambient').write_text('must not mount\n')
        frozen = self.root / 'frozen source'
        identity = acceptance.snapshot(source, frozen)
        self.assertEqual(set(identity['files']), {'app.py'})
        self.assertEqual(set(path.name for path in frozen.iterdir()), {'app.py', 'source.json'})
        (source / 'linked').symlink_to(self.root / 'outside')
        with self.assertRaisesRegex(ValueError, 'linked|escaping'):
            acceptance.snapshot(source, self.root / 'rejected source')

    def test_missing_declared_tool_fails_with_an_actionable_error(self):
        with self.assertRaisesRegex(ValueError, 'required-builder'):
            acceptance.tool_identity('required-builder', str(self.root / 'absent-tool'))

    def test_usrmerge_package_lookup_uses_only_verified_same_file_aliases(self):
        physical = Path('/usr/bin/sh').resolve(strict=True)
        lexical = Path('/bin/sh')
        calls = []
        def lookup(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0 if command[-1] == str(lexical) else 1,
                                               'dash: /bin/sh\n' if command[-1] == str(lexical) else '', '')
        with patch.object(acceptance.subprocess, 'run', side_effect=lookup):
            completed = acceptance.distribution_owner(physical, lexical)
        self.assertEqual(completed.args[-1], str(lexical))
        self.assertTrue(all(Path(command[-1]).samefile(physical) for command in calls))
        unrelated = self.root / 'different tool'; unrelated.write_text('unrelated')
        with patch.object(acceptance.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', '')) as run:
            with self.assertRaisesRegex(ValueError, 'lacks distribution package ownership'):
                acceptance.distribution_owner(physical, unrelated)
        self.assertNotIn(str(unrelated), [call.args[0][-1] for call in run.call_args_list])


if __name__ == '__main__':
    unittest.main()
