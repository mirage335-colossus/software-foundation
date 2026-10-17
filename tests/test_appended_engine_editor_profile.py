"""Editor compiled-facts adapter fixtures; mocked joins confer no eligibility."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_editor_contract as contract
import appended_engine_editor_consumer as consumer
import appended_engine_editor_profile as generator


class Inspection:
    def __init__(self, metadata):
        self.metadata = copy.deepcopy(metadata)

    def as_dict(self):
        return copy.deepcopy(self.metadata)


def metadata():
    pins = (contract.BASE_HEADER_SHA256, contract.DOCUMENT_HEADER_SHA256, contract.DOCUMENT_CONTRACT_SHA256,
        contract.DOCUMENT_CATALOG_SHA256, contract.ACTION_ACK_SCHEMA_SHA256, contract.PHYSICAL_CATALOG_SHA256,
        contract.EDITOR_HEADER_SHA256, contract.CONTRACT_SHA256, contract.EDITOR_CATALOG_SHA256, contract.EDITOR_SCHEMA_SHA256)
    return {'scope': contract.SCOPE, 'whole_group_verified': True, 'production_eligible': True,
        'recipe_id': 'b' * 64, 'provider_build_sha256': 'a' * 64,
        'engine_profile': contract.expected_engine_profile(editor_profile='editor',
            build_sha256='a' * 64, source_recipe_sha256='b' * 64),
        'provider_contract': contract.provider_contract(editor_profile='editor'),
        'interfaces': {role: {'path': path, 'sha256': digest}
            for (role, path), digest in zip(contract.INTERFACE_PATHS.items(), pins)}}


def cli(root):
    group, build, target = root / 'group', root / 'build', root / 'target.json'
    group.mkdir()
    build.mkdir()
    target.write_text(json.dumps({'system': 'Emscripten', 'processor': 'wasm32',
        'triple': 'wasm32-emscripten', 'pointer_bits': 32}))
    arguments = ['--editor-profile', 'editor', '--group', str(group), '--build-root', str(build),
        '--kernel-target-json', str(target), '--paired-sdk-sha256', 'e' * 64]
    for name, value in (('recipe', 'b'), ('manifest', 'c'), ('proof', 'd'), ('runtime', 'f')):
        arguments += ['--' + name + '-sha256', value * 64]
    return arguments, build / generator.HEADER_DIRECTORY / generator.HEADER_NAME


class EditorProfileTests(unittest.TestCase):
    def run_mocked(self, arguments, value=None):
        with patch.object(consumer, 'verify_kernel_consumer', return_value=Inspection(metadata() if value is None else value)) as verify, \
                patch.object(sys, 'stdout', new_callable=io.StringIO) as printed:
            result = generator.main(arguments)
        return result, verify, printed.getvalue()

    def test_private_path_and_public_renderer_require_fresh_full_verification(self):
        self.assertEqual(generator.HEADER_DIRECTORY, 'appended-engine-editor-profile')
        self.assertEqual(generator.HEADER_NAME, 'appended_engine_compiled_editor_profile.hpp')
        with patch.object(consumer, 'verify_kernel_consumer', side_effect=ValueError('fresh full verifier required')) as verify:
            with self.assertRaisesRegex(ValueError, 'fresh full verifier required'):
                generator.compiled_header('/inert/group', editor_profile='editor', expected_recipe='b' * 64)
            verify.assert_called_once_with('/inert/group', editor_profile='editor', expected_recipe='b' * 64)
        for selection in (None, 'pixel', 'physical', 3, True):
            with self.subTest(selection=selection), patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                generator.compiled_header(Inspection(metadata()), editor_profile=selection)
            verify.assert_not_called()

    def test_rendered_header_binds_exact_profile_catalog_and_all_fixed_pins(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli(Path(temporary))
            self.run_mocked(arguments)
            header = output.read_text()
            self.assertIn('namespace foundation::appended::engine_editor', header)
            self.assertIn('EngineEditorProfileFacts compiled_engine_editor_profile', header)
            self.assertIn('ProfileKind::editor', header)
            self.assertIn('kProviderCapabilities == 2035 && kSurfaceCapabilities == 8255', header)
            self.assertIn('.query_count = 2, .command_count = 7', header)
            self.assertEqual(header.count(' == OperationFacts{'), 9)
            self.assertIn('OperationFacts{4, 236, 1048576, 32,', header)
            for operation in (8, 9):
                self.assertIn('OperationFacts{' + str(operation) + ', 1048576, 1048576, 32,', header)
            self.assertIn(contract.CONTRACT_SHA256, header)
            self.assertIn(contract.EDITOR_SCHEMA_SHA256, header)
            self.assertIn('"' + 'a' * 64 + '"', header)
            self.assertIn('"' + 'b' * 64 + '"', header)
            self.assertNotIn('compiled_engine_document_profile', header)

    def test_main_verifies_once_with_every_pin_target_and_explicit_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments, output = cli(root)
            result, verify, printed = self.run_mocked(arguments)
            self.assertEqual(result, 0)
            verify.assert_called_once_with(root / 'group', expected_recipe='b' * 64,
                expected_manifest='c' * 64, expected_proof='d' * 64, expected_runtime='f' * 64,
                kernel_target={'system': 'Emscripten', 'processor': 'wasm32', 'triple': 'wasm32-emscripten', 'pointer_bits': 32},
                paired_sdk='e' * 64, editor_profile='editor')
            self.assertEqual(json.loads(printed), metadata())
            self.assertEqual([path.name for path in output.parent.iterdir()], [generator.HEADER_NAME])

    def test_embedded_old_ineligible_or_forged_boolean_inspections_cannot_generate(self):
        for key, value in (('scope', contract.EMBEDDED_SCOPE), ('scope', 'retained-document-v2-consumer-byte-and-static-contract-only'),
                ('whole_group_verified', False), ('whole_group_verified', 1), ('production_eligible', False), ('production_eligible', 1)):
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as temporary:
                arguments, output = cli(Path(temporary))
                changed = metadata()
                changed[key] = value
                with self.assertRaises(ValueError):
                    self.run_mocked(arguments, changed)
                self.assertFalse(output.parent.exists())

    def test_provider_interface_recipe_and_profile_identity_drift_cannot_generate(self):
        mutations = (lambda item: item.update(recipe_id='c' * 64),
            lambda item: item['engine_profile'].update(capabilities='2003'),
            lambda item: item['engine_profile'].update(build_sha256='";bad_cpp();//'),
            lambda item: item['provider_contract']['queries'][1].update(operation=2),
            lambda item: item['provider_contract']['commands'][-1].update(required_reply_capacity=16),
            lambda item: item['interfaces'].pop('editor_schema'),
            lambda item: item['interfaces']['editor_contract'].update(path='other.json'))
        for mutate in mutations:
            with tempfile.TemporaryDirectory() as temporary:
                arguments, output = cli(Path(temporary))
                changed = metadata()
                mutate(changed)
                with self.assertRaises(ValueError):
                    self.run_mocked(arguments, changed)
                self.assertFalse(output.parent.exists())

    def test_cli_rejects_missing_selector_and_old_flags_before_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli(Path(temporary))
            for changed in (arguments[2:], [*arguments, '--physical-input'], [*arguments, '--document-profile', 'physical']):
                with self.subTest(arguments=changed), patch.object(consumer, 'verify_kernel_consumer') as verify, \
                        patch.object(sys, 'stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as stopped:
                    generator.main(changed)
                self.assertEqual(stopped.exception.code, 2)
                verify.assert_not_called()
                self.assertFalse(output.parent.exists())

    def test_actual_empty_group_is_ineligible_and_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli(Path(temporary))
            with self.assertRaises(ValueError):
                generator.main(arguments)
            self.assertFalse(output.parent.exists())

    def test_duplicate_target_json_and_output_input_alias_fail_before_verification(self):
        for alias in (False, True):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                arguments, output = cli(root)
                if alias:
                    output.parent.mkdir()
                    output.write_bytes((root / 'target.json').read_bytes())
                    arguments[arguments.index('--kernel-target-json') + 1] = str(output)
                else:
                    (root / 'target.json').write_bytes(b'{"system":"Linux","system":"Emscripten"}')
                with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                    generator.main(arguments)
                verify.assert_not_called()

    def test_output_aliases_never_replace_foreign_bytes(self):
        for kind in ('hardlink', 'symlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                arguments, output = cli(root)
                output.parent.mkdir()
                foreign = root / 'foreign'
                foreign.write_bytes(b'preserve foreign bytes')
                if kind == 'hardlink':
                    os.link(foreign, output)
                else:
                    output.symlink_to(foreign)
                with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                    generator.main(arguments)
                verify.assert_not_called()
                self.assertEqual(foreign.read_bytes(), b'preserve foreign bytes')

    def test_malformed_existing_selection_marker_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli(Path(temporary))
            output.parent.mkdir()
            original = (generator.GENERATED_NOTICE + '\n' + generator.SELECTION_PREFIX + 'physical\n').encode()
            output.write_bytes(original)
            with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                generator.main(arguments)
            verify.assert_not_called()
            self.assertEqual(output.read_bytes(), original)

    def test_repeated_verified_header_is_unchanged_and_atomic_failure_preserves_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli(Path(temporary))
            self.run_mocked(arguments)
            before = output.read_bytes()
            os.utime(output, ns=(1000000000, 1000000000))
            self.run_mocked(arguments)
            self.assertEqual(output.stat().st_mtime_ns, 1000000000)
            changed = metadata()
            changed['provider_build_sha256'] = changed['engine_profile']['build_sha256'] = 'c' * 64
            with patch.object(generator.os, 'replace', side_effect=OSError('replace failed')), self.assertRaises(OSError):
                self.run_mocked(arguments, changed)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual([path.name for path in output.parent.iterdir()], [generator.HEADER_NAME])


if __name__ == '__main__':
    unittest.main()
