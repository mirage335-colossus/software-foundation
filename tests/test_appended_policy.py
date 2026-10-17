from copy import deepcopy
import hashlib
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import appended_policy as policy
from appended_project import default_document
from dependency_archive import encoded


class KernelProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / 'project'
        self.root.mkdir()
        self.write('src/main.cpp', 'int main() { return 0; }\n')
        self.write('build.sh', '#!/bin/sh\nexit 0\n')
        (self.root / 'build.sh').chmod(0o755)

    def tearDown(self): self.temporary.cleanup()

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')
        return path

    def config(self, document=None):
        self.write('foundation-project.json', json.dumps(document or default_document()))

    def test_full_projection_keeps_unknown_sdk_glue_and_abi_inputs(self):
        for name in ('mystery.input', 'sdk/appended/runtime.c', 'gui/host/bridge.mjs',
                     'abi/appended/v1/services.json', 'tools/appended_wasm.py'):
            self.write(name, 'kernel input')
        manifest = policy.kernel_source_tree(self.root)
        self.assertTrue({'mystery.input', 'sdk/appended/runtime.c', 'gui/host/bridge.mjs',
                         'abi/appended/v1/services.json', 'tools/appended_wasm.py'} <= manifest['files'].keys())
        self.assertEqual(manifest, policy.validate_kernel_inputs(manifest))

    def test_narrative_qualification_and_test_additions_preserve_kernel_inputs(self):
        from source_identity import source_tree
        expected = policy.kernel_source_tree(self.root)
        original_complete = source_tree(self.root)
        for name in ('README.md', 'LICENSE', 'AGENTS.md', 'docs/new-feature.md',
                     'docs/installed.md', '.agent-pending/new-qualification.md',
                     'tests/new_contract.cpp', 'tests/test_new_policy.py',
                     'gui/tests/new_interaction_test.mjs'):
            self.write(name, 'application metadata, narrative or qualification-only source\n')
        self.assertEqual(expected, policy.kernel_source_tree(self.root))
        self.assertTrue(policy.retained_eligibility(self.root, expected)['eligible'])
        self.assertNotEqual(original_complete['tree_sha256'], source_tree(self.root)['tree_sha256'])
        self.assertIn('LICENSE', source_tree(self.root)['files'])

    def test_unknown_document_data_resources_and_native_headers_remain_inputs(self):
        expected = policy.kernel_source_tree(self.root)
        for name in ('docs/new-policy.json', 'docs/appended-release-policy-extra.json',
                     'tools/appended_qualification_extra.py', 'tools/appended_delivery_extra.py',
                     'docs/new-resource.bin', 'unknown-resource.dat',
                     'include/foundation/new_api.hpp', 'src/new_runtime.cpp',
                     'third_party/README.md', 'third_party/LICENSE', 'sdk/README.md',
                     'sdk/appended/extra/README.md', 'sdk/appended/LICENSE'):
            with self.subTest(path=name):
                path = self.write(name, 'new unknown or runtime/dependency input')
                result = policy.retained_eligibility(self.root, expected)
                self.assertFalse(result['eligible'])
                self.assertIn({'path': name, 'changes': ['added']}, result['differences'])
                path.unlink()

    def test_document_named_directories_do_not_hide_unknown_kernel_inputs(self):
        expected = policy.kernel_source_tree(self.root)
        for name in ('LICENSE/runtime.cpp', 'README.md/runtime.cpp', 'AGENTS.md/schema.json',
                     'docs/notes.md/runtime.cpp', '.agent-pending/qualification.md/runtime.bin',
                     'sdk/appended/README.md/runtime.cpp', 'sdk/appended/guest.c/runtime.cpp'):
            with self.subTest(path=name):
                path = self.write(name, 'unknown nested input must remain visible')
                result = policy.retained_eligibility(self.root, expected)
                self.assertFalse(result['eligible'])
                self.assertIn({'path': name, 'changes': ['added']}, result['differences'])
                path.unlink()

    def test_exact_guest_inputs_preserve_kernel_but_change_complete_source_and_sdk_identities(self):
        from source_identity import source_tree
        for name in policy.GUEST_INPUT_FILES | policy.GUEST_DOCUMENT_FILES:
            self.write(name, 'original guest-only input\n')
        expected = policy.kernel_source_tree(self.root)
        complete = source_tree(self.root)
        sdk_complete = source_tree(self.root / 'sdk/appended')
        for name in sorted(policy.GUEST_INPUT_FILES | policy.GUEST_DOCUMENT_FILES):
            with self.subTest(path=name):
                original = (self.root / name).read_bytes()
                self.write(name, 'changed guest-only input\n')
                self.assertEqual(expected, policy.kernel_source_tree(self.root))
                self.assertTrue(policy.retained_eligibility(self.root, expected)['eligible'])
                self.assertNotEqual(complete['tree_sha256'], source_tree(self.root)['tree_sha256'])
                if name.startswith('sdk/appended/'):
                    self.assertNotEqual(sdk_complete['tree_sha256'], source_tree(self.root / 'sdk/appended')['tree_sha256'])
                (self.root / name).write_bytes(original)

    def test_shared_abi_validator_kernel_producers_and_unknown_sdk_paths_remain_protected(self):
        expected = policy.kernel_source_tree(self.root)
        for name in ('include/foundation/appended/abi.h', 'include/foundation/appended/provider_abi.h',
                     'abi/appended/providers/v1.json', 'abi/appended/v1/bootstrap.json',
                     'abi/appended/view/v1.json', 'tools/appended_wasm.py', 'tools/appended_wasm3.py',
                     'tools/appended_kernel.py', 'tools/package_appended_wasm.py',
                     'src/appended/module_wasm3.cpp', 'cmake/Appended.cmake',
                     'tools/build.py', 'CMakeLists.txt', 'tools/ci_changes_extra.py',
                     'sdk/appended/new_guest.c', 'sdk/appended/include/new_header.h',
                     'sdk/appended/rust/src/new_codec.rs', 'tools/appended_compile_extra.py'):
            with self.subTest(path=name):
                path = self.write(name, 'new kernel/shared or unclassified input')
                result = policy.retained_eligibility(self.root, expected)
                self.assertFalse(result['eligible'])
                self.assertIn({'path': name, 'changes': ['added']}, result['differences'])
                path.unlink()

    def test_composition_tools_preserve_kernel_while_complete_source_identity_changes(self):
        from source_identity import source_tree
        expected = policy.kernel_source_tree(self.root)
        complete = source_tree(self.root)
        for name in sorted(policy.COMPOSITION_FILES):
            with self.subTest(path=name):
                path = self.write(name, '# reviewed composition tool/metadata change\n')
                self.assertEqual(expected, policy.kernel_source_tree(self.root))
                self.assertTrue(policy.retained_eligibility(self.root, expected)['eligible'])
                self.assertNotEqual(complete['tree_sha256'], source_tree(self.root)['tree_sha256'])
                self.assertIn(name, source_tree(self.root)['files'])
                self.assertTrue(policy.classify_paths([name])['known_changes'])
                path.unlink()

    def test_projection_v1_requires_an_independently_issued_descriptor_without_migration(self):
        expected = policy.kernel_source_tree(self.root)
        self.assertEqual('foundation-appended-kernel-v2', expected['projection'])
        old = deepcopy(expected)
        old['projection'] = 'foundation-appended-kernel-v1'
        result = policy.retained_eligibility(self.root, old)
        self.assertFalse(result['eligible'])
        self.assertIsNone(result['actual_sha256'])
        self.assertIn('independently issue a v2 descriptor', result['reason'])
        self.assertIn('no automatic rebuild or descriptor migration', result['reason'])
        self.assertEqual('foundation-appended-kernel-v1', old['projection'])

    @unittest.skipUnless(os.name == 'posix' and shutil.which('git'), 'fork.sh fixture needs POSIX and Git')
    def test_actual_customized_fork_attribution_preserves_pinned_kernel_and_original_notices(self):
        from source_identity import source_tree
        repository = Path(__file__).resolve().parents[1]
        self.write('README.md', '# Foundation\n\nAuthor: mirage335. The code and documentation authored in this repository are\n')
        self.write('LICENSE', (repository / 'LICENSE').read_text(encoding='utf-8'))
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(('GIT_', 'PROJECT_')) and key != 'DEFAULT_SOURCE_URLS'}
        environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_CONFIG_SYSTEM=os.devnull, GIT_TERMINAL_PROMPT='0',
                           PROJECT_AUTHOR='Downstream Author')
        command = ['git', '-C', str(self.root), '-c', 'core.hooksPath=' + os.devnull,
                   '-c', 'user.name=Policy fixture', '-c', 'user.email=policy@example.invalid']
        for args in (['init', '--quiet', '--template=', '-b', 'main'], ['add', '--all'],
                     ['commit', '--quiet', '-m', 'Original kernel source']):
            subprocess.run([*command, *args], env=environment, check=True, capture_output=True)
        expected = policy.kernel_source_tree(self.root)
        original_complete = source_tree(self.root)
        original_revision = subprocess.check_output([*command, 'rev-parse', 'HEAD'], env=environment).strip()
        downstream = self.root.parent / 'customized-fork'
        subprocess.run(['sh', str(repository / 'fork.sh'), str(downstream), str(self.root)],
                       cwd=self.root.parent, env=environment, check=True, capture_output=True, timeout=30)
        self.assertIn('Author: Downstream Author.', (downstream / 'README.md').read_text())
        self.assertRegex((downstream / 'LICENSE').read_text(), r'Copyright \(c\) [0-9]+ Downstream Author')
        absent = subprocess.run(['git', '-C', str(downstream), 'cat-file', '-e', original_revision.decode()],
                                env=environment, capture_output=True)
        self.assertNotEqual(0, absent.returncode)
        self.assertEqual(expected, policy.kernel_source_tree(downstream))
        self.assertTrue(policy.retained_eligibility(downstream, expected)['eligible'])
        downstream_complete = source_tree(downstream)
        self.assertNotEqual(original_complete['files']['LICENSE'], downstream_complete['files']['LICENSE'])
        self.assertEqual(original_complete, source_tree(self.root), 'original kernel source/notices changed')

    def test_mixed_payload_product_and_composition_tooling_keep_exact_kernel_identity(self):
        expected = policy.kernel_source_tree(self.root)
        self.write('src-web-appended/index.html', '<h1>hello</h1>')
        self.write('src-bin-appended/main.rs', 'fn update() {}')
        self.write('src-bin-appended/schemas/product.json', '{"operation": 1}')
        self.write('tools/appended_container.py', '# revised composition packaging')
        self.write('tests/test_appended_container.py', '# new packaging regression')
        document = default_document()
        document['application'].update(id='org.example.product', name='A product', version='2.0.0')
        document['appended']['web'].update(enabled=True, entry='index.html')
        document['appended']['binary']['enabled'] = True
        document['startup']['primary'] = 'web'
        self.config(document)
        self.assertEqual(expected, policy.kernel_source_tree(self.root))
        with patch.object(policy.subprocess, 'run', side_effect=AssertionError('no process launch')):
            self.assertTrue(policy.retained_eligibility(self.root, expected)['eligible'])

    def test_kernel_profile_remains_a_strict_kernel_input(self):
        self.config()
        expected = policy.kernel_source_tree(self.root)
        document = default_document()
        document['kernel']['profile'] = 'both'
        self.config(document)
        result = policy.retained_eligibility(self.root, expected)
        self.assertFalse(result['eligible'])
        self.assertNotIn('comparison_policy', result)
        self.assertEqual([{'path': 'foundation-project.json', 'changes': ['content']}], result['differences'])

    def test_selection_comparison_preserves_both_raw_v2_identities_and_visible_difference(self):
        for previous, current in (('project', 'foundation'), ('foundation', 'project')):
            with self.subTest(previous=previous, current=current):
                document = default_document()
                document['kernel']['selection'] = previous
                self.config(document)
                expected = policy.kernel_source_tree(self.root)
                retained_original = deepcopy(expected)
                document['kernel']['selection'] = current
                self.config(document)
                actual = policy.kernel_source_tree(self.root)
                with patch.object(policy.subprocess, 'run', side_effect=AssertionError('no process launch')):
                    result = policy.retained_eligibility(self.root, expected)
                self.assertTrue(result['eligible'])
                self.assertEqual(retained_original, expected, 'old descriptor inputs must remain unchanged')
                self.assertEqual('foundation-appended-kernel-v2', actual['projection'])
                self.assertEqual(expected['tree_sha256'], result['expected_sha256'])
                self.assertEqual(actual['tree_sha256'], result['actual_sha256'])
                self.assertNotEqual(result['expected_sha256'], result['actual_sha256'])
                self.assertEqual(policy.SELECTION_COMPARISON, result['comparison_policy'])
                self.assertEqual(expected['tree_sha256'], result['comparison_sha256'])
                self.assertEqual([{'path': policy.CONFIGURATION, 'changes': ['content']}], result['differences'])
                self.assertEqual({'path': policy.CONFIGURATION,
                                  'expected_selection': previous, 'actual_selection': current,
                                  'expected_configuration_sha256': expected['files'][policy.CONFIGURATION],
                                  'actual_configuration_sha256': actual['files'][policy.CONFIGURATION]},
                                 result['selection_metadata_difference'])
                unchanged = policy.retained_eligibility(self.root, actual)
                self.assertTrue(unchanged['eligible'])
                self.assertEqual([], unchanged['differences'])
                self.assertNotIn('comparison_policy', unchanged)

    def test_selection_allowance_does_not_hide_profile_source_unknown_or_mode_changes(self):
        for mutation in ('profile', 'native', 'added', 'deleted', 'mode', 'configuration_mode'):
            if os.name == 'nt' and mutation in ('mode', 'configuration_mode'):
                continue
            with self.subTest(mutation=mutation):
                document = default_document()
                self.config(document)
                self.write('src/main.cpp', 'int main() { return 0; }\n')
                self.write('build.sh', '#!/bin/sh\nexit 0\n').chmod(0o755)
                expected = policy.kernel_source_tree(self.root)
                document['kernel']['selection'] = 'foundation'
                if mutation == 'profile': document['kernel']['profile'] = 'both'
                self.config(document)
                if mutation == 'native': self.write('src/main.cpp', 'int changed;\n')
                elif mutation == 'added': self.write('unknown.new', 'new native input')
                elif mutation == 'deleted': (self.root / 'src/main.cpp').unlink()
                elif mutation == 'mode': (self.root / 'build.sh').chmod(0o644)
                elif mutation == 'configuration_mode': (self.root / policy.CONFIGURATION).chmod(0o755)
                result = policy.retained_eligibility(self.root, expected)
                self.assertFalse(result['eligible'])
                self.assertNotIn('comparison_policy', result)
                if mutation == 'added': (self.root / 'unknown.new').unlink()
                (self.root / policy.CONFIGURATION).chmod(0o644)

    def test_selection_allowance_rejects_other_canonical_and_forged_configuration_hashes(self):
        self.config()
        expected = policy.kernel_source_tree(self.root)
        document = default_document()
        document['kernel']['selection'] = 'foundation'
        self.config(document)
        for wrong_hash in ('0' * 64, hashlib.sha256(encoded({})).hexdigest()):
            with self.subTest(configuration_hash=wrong_hash):
                forged = deepcopy(expected)
                forged['files'][policy.CONFIGURATION] = wrong_hash
                forged['tree_sha256'] = hashlib.sha256(encoded(
                    {'files': forged['files'], 'executables': forged['executables']})).hexdigest()
                result = policy.retained_eligibility(self.root, forged)
                self.assertFalse(result['eligible'])
                self.assertNotIn('comparison_policy', result)
        document['kernel']['selection'] = 'other'
        self.config(document)
        invalid = policy.retained_eligibility(self.root, expected)
        self.assertFalse(invalid['eligible'])
        self.assertIsNone(invalid['actual_sha256'])

    def test_selection_raw_and_counterfactual_use_one_validated_configuration_observation(self):
        self.config()
        expected = policy.kernel_source_tree(self.root)
        document = default_document()
        document['kernel']['selection'] = 'foundation'
        self.config(document)
        observed = policy.configuration_projection(self.root)
        with patch.object(policy, 'configuration_projection', side_effect=[observed]) as capture:
            result = policy.retained_eligibility(self.root, expected)
        self.assertTrue(result['eligible'])
        self.assertEqual(1, capture.call_count)

    def test_source_addition_deletion_and_edit_are_concrete_differences(self):
        expected = policy.kernel_source_tree(self.root)
        self.write('src/main.cpp', 'int main() { return 1; }\n')
        (self.root / 'build.sh').unlink()
        self.write('new-unknown.input', 'unknown must not disappear')
        result = policy.retained_eligibility(self.root, expected)
        self.assertFalse(result['eligible'])
        self.assertEqual([{'path': 'build.sh', 'changes': ['deleted']},
                          {'path': 'new-unknown.input', 'changes': ['added']},
                          {'path': 'src/main.cpp', 'changes': ['content']}], result['differences'])

    @unittest.skipIf(os.name == 'nt', 'POSIX executable mode')
    def test_supplement_files_and_modes_follow_complete_source_rules(self):
        supplement = self.root.parent / 'gui-supplement'
        supplement.mkdir()
        script = supplement / 'generate.sh'
        script.write_text('#!/bin/sh\nexit 0\n')
        script.chmod(0o755)
        nested = supplement / 'src-web-appended/kernel-helper.js'
        nested.parent.mkdir()
        nested.write_text('export const kernelHelper = 1;')
        expected = policy.kernel_source_tree(self.root, supplement)
        name = 'third_party/retained/gui/generate.sh'
        self.assertIn(name, expected['files'])
        self.assertIn(name, expected['executables'])
        self.assertIn('third_party/retained/gui/src-web-appended/kernel-helper.js', expected['files'])
        script.chmod(0o644)
        result = policy.retained_eligibility(self.root, expected, supplement)
        self.assertFalse(result['eligible'])
        self.assertEqual([{'path': name, 'changes': ['executable']}], result['differences'])

    @unittest.skipIf(os.name == 'nt', 'POSIX symbolic-link fixture')
    def test_payloads_are_pruned_before_link_inspection_in_plain_and_restored_sources(self):
        from source_identity import source_tree
        expected = policy.kernel_source_tree(self.root)
        self.write('src-web-appended/old.html', '<h1>old app</h1>')
        complete = source_tree(self.root)
        self.write('source.json', json.dumps(complete))
        (self.root / 'src-web-appended/old.html').unlink()
        (self.root / 'src-web-appended/dangling.js').symlink_to(self.root.parent / 'missing-script')
        (self.root / 'src-bin-appended').symlink_to(self.root.parent / 'missing-module', target_is_directory=True)
        scan = os.scandir
        def no_payload_scan(path):
            self.assertNotEqual(self.root / 'src-web-appended', Path(path))
            return scan(path)
        for restored in (True, False):
            with self.subTest(restored=restored):
                if not restored: (self.root / 'source.json').unlink()
                with patch.object(os, 'scandir', side_effect=no_payload_scan):
                    self.assertEqual(expected, policy.kernel_source_tree(self.root))
                    self.assertTrue(policy.retained_eligibility(self.root, expected)['eligible'])
                with self.assertRaises(ValueError): source_tree(self.root)
        self.write('unknown-native.cpp', 'native input')
        self.assertFalse(policy.retained_eligibility(self.root, expected)['eligible'])

    @unittest.skipIf(os.name == 'nt', 'POSIX symbolic-link fixture')
    def test_restored_projection_keeps_supplement_bytes_and_portable_modes(self):
        from dependency_archive import extract
        import source_identity
        supplement = self.root.parent / 'supplement'
        supplement.mkdir()
        script = supplement / 'generate.sh'
        script.write_text('#!/bin/sh\nexit 0\n')
        script.chmod(0o755)
        self.write('src-web-appended/index.html', '<p>replaceable</p>')
        expected = policy.kernel_source_tree(self.root, supplement)
        archive = self.root.parent / 'complete-source.tar.gz'
        source_identity.archive_source(self.root, archive, supplement)
        restored = self.root.parent / 'restored'
        extract(archive, restored)
        (restored / 'src-web-appended/index.html').unlink()
        (restored / 'src-web-appended/dangling').symlink_to(self.root.parent / 'missing')
        retained = restored / 'third_party/retained/gui'
        self.assertEqual(expected, policy.kernel_source_tree(restored, retained))
        (retained / 'generate.sh').chmod(0o644)
        (restored / 'build.sh').chmod(0o644)
        with patch.object(source_identity, 'WINDOWS', True):
            self.assertEqual(expected, policy.kernel_source_tree(restored, retained))

    @unittest.skipIf(os.name == 'nt', 'POSIX executable mode')
    def test_actual_executable_mode_changes_deny_reuse(self):
        expected = policy.kernel_source_tree(self.root)
        (self.root / 'build.sh').chmod(0o644)
        result = policy.retained_eligibility(self.root, expected)
        self.assertEqual([{'path': 'build.sh', 'changes': ['executable']}], result['differences'])
        self.assertFalse(result['eligible'])

    def test_missing_or_tampered_pinned_inventory_never_selects_rebuild(self):
        self.assertFalse(policy.retained_eligibility(self.root, None)['eligible'])
        expected = policy.kernel_source_tree(self.root)
        for mutation in ('digest', 'mode', 'projection', 'payload'):
            with self.subTest(mutation=mutation):
                tampered = deepcopy(expected)
                if mutation == 'digest': tampered['files']['src/main.cpp'] = '0' * 64
                elif mutation == 'mode': tampered['executables'] = ['missing']
                elif mutation == 'projection': tampered['projection'] = 'unknown'
                else: tampered['files']['src-bin-appended/hidden.c'] = '0' * 64
                result = policy.retained_eligibility(self.root, tampered)
                self.assertFalse(result['eligible'])
                self.assertIsNone(result['actual_sha256'])

    def test_alternate_payload_roots_and_duplicate_config_keys_fail_closed(self):
        expected = policy.kernel_source_tree(self.root)
        document = default_document()
        document['appended']['binary']['source'] = 'src'
        self.config(document)
        self.assertIn('standard appended source roots', policy.retained_eligibility(self.root, expected)['reason'])
        raw = json.dumps(default_document())
        self.write('foundation-project.json', raw[:-1] + ',"schema_version":1}')
        self.assertIn('duplicate', policy.retained_eligibility(self.root, expected)['reason'])

    @unittest.skipUnless(shutil.which('git'), 'Git fixture')
    def test_independent_git_roots_do_not_need_common_ancestry(self):
        expected = policy.kernel_source_tree(self.root)
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_CONFIG_SYSTEM=os.devnull)
        command = ['git', '-C', str(self.root), '-c', 'core.hooksPath=' + os.devnull,
                   '-c', 'user.name=Policy fixture', '-c', 'user.email=policy@example.invalid']
        for args in (['init', '--quiet', '--template='], ['add', '--all'],
                     ['commit', '--quiet', '-m', 'Independent root without upstream history']):
            subprocess.run([*command, *args], env=environment, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        original = subprocess.run
        def inventory_only(arguments, **kwargs):
            self.assertEqual(['git', '-C', str(self.root), 'ls-files'], arguments[:4])
            return original(arguments, **kwargs)
        with patch.object(policy.subprocess, 'run', side_effect=inventory_only):
            # source_identity legitimately uses Git only to inventory current
            # source files/modes; it never asks for commit ancestry or a diff.
            self.assertTrue(policy.retained_eligibility(self.root, expected)['eligible'])

    def test_classification_aggregates_known_changes_and_keeps_unknown_conservative(self):
        result = policy.classify_paths(['src-web-appended/index.html', 'src-bin-appended/main.c',
                                        'foundation-project.json', 'tools/appended_container.py'])
        self.assertTrue(result['known_changes'])
        self.assertTrue({'web-check', 'guest-compile', 'composition-tooling', 'compose'} <= set(result['actions']))
        for name in ('unknown.ext', '../src-web-appended/x', '/src-web-appended/x',
                     'src/main.cpp', 'sdk/appended/runtime.c', 'tools/appended_wasm.py'):
            with self.subTest(path=name): self.assertFalse(policy.classify_paths([name])['known_changes'])
        self.assertFalse(policy.classify_paths([])['known_changes'])
        metadata = policy.classify_paths(['README.md', 'LICENSE', 'docs/new-guide.md',
                                          '.agent-pending/new-check.md', 'tests/new_test.cpp'])
        self.assertTrue(metadata['known_changes'])
        self.assertTrue({'documentation-check', 'test-tooling', 'prebuilt-runtime-check'} <= set(metadata['actions']))
        guest = policy.classify_paths(sorted(policy.GUEST_INPUT_FILES))
        self.assertTrue(guest['known_changes'])
        self.assertTrue({'guest-tooling-check', 'sdk-insulation', 'binding-conformance',
                         'module-source-identity-check', 'module-check'} <= set(guest['actions']))
        self.assertNotIn('guest-compile', guest['actions'])


class InsulationTests(unittest.TestCase):
    def test_binary_tree_and_sdk_reject_javascript_and_web_dependencies(self):
        cases = [('main.js', ''), ('package.json', '{}'), ('module.cpp', 'EM_JS(int, f, (), {return 1;});'),
                 ('Cargo.toml', '[dependencies]\nwasm-bindgen="1"'),
                 ('bindings.rs', 'use web_sys::Window;'), ('build.txt', 'npm ci'),
                 ('CMakeLists.txt', 'COMMAND node -e "const f = () => 42"'),
                 ('build.txt', 'emcc main.c -o output.wasm'),
                 ('build.txt', 'em++ main.cpp -o output.wasm'),
                 ('main.c', '#include <emscripten/emscripten.h>'),
                 ('README.md', '```javascript\nalert(1);\n```'),
                 ('data.txt', 'function update() { return 1; }'),
                 ('main.cpp', 'load("./bridge.mjs");')]
        for name, source in cases:
            with self.subTest(path=name, source=source): self.assertTrue(policy.binary_violations(source, name))

    def test_binary_c_cpp_rust_and_ordinary_words_are_allowed(self):
        for source in ('int javascript_count = 1;', 'const auto value = 3;',
                       'let window = 4;', '// No JavaScript runtime is needed.\nfn update() {}',
                       'const char *message = "Browser and terminal status";'):
            with self.subTest(source=source): self.assertFalse(policy.binary_violations(source, 'main.cpp'))

    def test_web_rejects_concrete_imports_branches_runtime_and_device_code(self):
        cases = ['import { draw } from "../../gui/backends/sdl.js";',
                 'const driver = require("serialport");',
                 'if (host.backend === "terminal") drawText();',
                 'switch (backend) { case "sdl": draw(); break; }',
                 'const draw = backend === "sdl" ? nativeDraw : normalDraw;',
                 'if (navigator.userAgent.includes("Firefox")) useFirefox();',
                 'WebAssembly.instantiate(bytes, imports);', 'navigator.serial.requestPort();',
                 'WebAssembly.instantiateStreaming(fetch("module.wasm"), imports);',
                 'WebAssembly.compileStreaming(fetch("module.wasm"));',
                 'new WebAssembly.Module(bytes);', 'new WebAssembly.Instance(module, imports);',
                 'navigator?.serial.requestPort();', 'navigator["serial"].requestPort();',
                 'const value = `${JSON.stringify({value: navigator.serial})}`;',
                 'const text = `label ${backend === "sdl" ? 1 : 2}`;',
                 'Module.ccall("private", null, [], []);']
        for source in cases:
            with self.subTest(source=source): self.assertTrue(policy.web_violations(source, 'main.js'))
        self.assertTrue(policy.web_violations(r'const url = /https?:\/\//; navigator.serial.requestPort();', 'main.js'))
        self.assertTrue(policy.web_violations('const number = count / navigator.serial / total;', 'main.js'))

    def test_web_legitimate_app_strings_fields_and_generic_capabilities_are_allowed(self):
        sources = ['const status = "terminal"; const label = "SDL_Example";',
                   'const label = "navigator.serial";', 'if (record.backend) show(record.backend);',
                   'if (backend === "http") loadRecords();',
                   'if (backend === "http" && label === "terminal") loadRecords();',
                   'switch (record.backend) { case "http": show("terminal"); break; }',
                   'if (capabilities.textPresentation) renderText();',
                   'import { record } from "./hosts/data.js";',
                   'import { form } from "./gui/forms.js";',
                   '// if (backend === "sdl") useNative();\nrender();']
        for source in sources:
            with self.subTest(source=source): self.assertFalse(policy.web_violations(source, 'main.js'))
        self.assertFalse(policy.web_violations('const pattern = /SDL_Example/;', 'main.js'))
        self.assertFalse(policy.web_violations('<p>if (backend === "sdl") is documentation</p>', 'index.html'))
        self.assertFalse(policy.web_violations('<text>TerminalAdapter</text>', 'illustration.svg'))
        self.assertFalse(policy.web_violations('--SDL_palette: blue;', 'style.css'))
        self.assertFalse(policy.web_violations('TerminalAdapter usage', 'README.md'))

    def test_html_inline_events_and_quoted_or_unquoted_imports_are_checked(self):
        for source in ('<script src="./gui/backends/sdl.js"></script>',
                       '<script src=./backends/sdl.js></script>',
                       '<script>navigator.usb.requestDevice({});</script>',
                       '<button onclick="navigator&#46;serial.requestPort()">Connect</button>'):
            with self.subTest(source=source): self.assertTrue(policy.web_violations(source, 'index.html'))
        self.assertTrue(policy.web_violations('<svg><script>navigator.usb.requestDevice({})</script></svg>', 'figure.svg'))

    def test_dependency_manifest_duplicates_cannot_hide_prohibited_packages(self):
        self.assertTrue(policy.web_violations('{"dependencies":{"sdl":"1"}}', 'package.json'))
        self.assertTrue(policy.web_violations('{"dependencies":{"sdl":"1"},"dependencies":{}}', 'package.json'))
        self.assertFalse(policy.web_violations('{"description":"SDL terminal viewer","dependencies":{}}', 'package.json'))

    def test_audit_covers_binary_source_sdk_and_web_with_deterministic_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, source in (('src-bin-appended/main.c', 'int main() {}'),
                                 ('sdk/appended/include/bridge.hpp', '#include "bridge.js"'),
                                 ('src-web-appended/app.js', 'import "sdl2";')):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            result = policy.audit(root)
            self.assertFalse(result['ok'])
            self.assertEqual(3, result['files_scanned'])
            self.assertEqual(['sdk/appended/include/bridge.hpp', 'src-web-appended/app.js'],
                             sorted({item['path'] for item in result['violations']}))
            self.assertEqual(result, policy.audit(root))

    @unittest.skipIf(os.name == 'nt', 'POSIX symbolic-link fixture')
    def test_audit_rejects_direct_and_ancestor_links(self):
        for link_type in ('file', 'scope', 'ancestor'):
            with self.subTest(link=link_type), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'project'
                outside = Path(temporary) / 'outside'
                root.mkdir(); outside.mkdir()
                (outside / 'appended').mkdir()
                if link_type == 'ancestor': (root / 'sdk').symlink_to(outside, target_is_directory=True)
                elif link_type == 'scope': (root / 'src-bin-appended').symlink_to(outside, target_is_directory=True)
                else:
                    (root / 'src-bin-appended').mkdir()
                    (outside / 'source.c').write_text('int x;')
                    (root / 'src-bin-appended/source.c').symlink_to(outside / 'source.c')
                with self.assertRaisesRegex(ValueError, 'linked'): policy.audit(root)


if __name__ == '__main__': unittest.main()
