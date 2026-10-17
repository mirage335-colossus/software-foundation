#!/usr/bin/env python3
"""Isolated document-facts generator checks; mocked eligibility is no runtime proof."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import appended_engine_document_contract as contract
import appended_engine_document_consumer as consumer
import appended_engine_document_profile as generator


class Inspection:
    def __init__(self, metadata):
        self.metadata = copy.deepcopy(metadata)

    def as_dict(self):
        return copy.deepcopy(self.metadata)


def fixture_metadata(selection='pixel'):
    references = {role: {'path': path, 'sha256': contract.INTERFACE_PINS[role]}
                  for role, path in contract.INTERFACE_PATHS.items()}
    if selection == 'physical':
        references['physical_catalog'] = {
            'path': 'provider/catalog/current-physical.json',
            'sha256': contract.PHYSICAL_CATALOG_SHA256,
        }
    return {
        'scope': 'retained-document-v2-consumer-byte-and-static-contract-only',
        'whole_group_verified': True,
        'production_eligible': True,
        'recipe_id': 'b' * 64,
        'provider_build_sha256': 'a' * 64,
        'engine_profile': contract.expected_engine_profile(
            document_profile=selection, build_sha256='a' * 64,
            source_recipe_sha256='b' * 64),
        'provider_contract': contract.provider_contract(document_profile=selection),
        'interfaces': references,
    }


def cli_fixture(root, selection='pixel'):
    group, build_root, target = root / 'group', root / 'build', root / 'target.json'
    group.mkdir()
    build_root.mkdir()
    target.write_text(json.dumps({'system': 'Emscripten', 'processor': 'wasm32',
                                  'triple': 'wasm32-emscripten', 'pointer_bits': 32}),
                      encoding='utf-8')
    arguments = ['--group', str(group), '--build-root', str(build_root),
                 '--kernel-target-json', str(target), '--paired-sdk-sha256', 'e' * 64,
                 '--document-profile', selection]
    for name, pin in (('recipe', 'b'), ('manifest', 'c'), ('proof', 'd'), ('runtime', 'f')):
        arguments.extend(('--' + name + '-sha256', pin * 64))
    output = build_root / generator.HEADER_DIRECTORY / generator.HEADER_NAME
    return arguments, output


def replace_argument(arguments, name, value):
    result = list(arguments)
    result[result.index(name) + 1] = str(value)
    return result


class DocumentCompiledProfileTests(unittest.TestCase):
    def run_main(self, arguments, metadata=None):
        selected = arguments[arguments.index('--document-profile') + 1]
        inspection = Inspection(metadata if metadata is not None else fixture_metadata(selected))
        with patch.object(consumer, 'verify_kernel_consumer', return_value=inspection) as verify, \
                patch.object(sys, 'stdout', new_callable=io.StringIO) as printed:
            result = generator.main(arguments)
        return result, verify, printed.getvalue()

    def test_required_explicit_python_selector_and_exact_private_path(self):
        self.assertEqual(generator.HEADER_DIRECTORY, 'appended-engine-document-profile')
        self.assertEqual(generator.HEADER_NAME, 'appended_engine_compiled_document_profile.hpp')
        with self.assertRaises(TypeError):
            generator.compiled_header(Inspection(fixture_metadata()))
        for selected in (None, True, 1, '', 'PIXEL', '467', 'pixel '):
            with self.subTest(selection=selected), self.assertRaises(ValueError):
                generator.compiled_header(Inspection(fixture_metadata()), document_profile=selected)

    def test_header_preserves_fixed_public_contract_and_actual_identity(self):
        for selected, capabilities in (('pixel', 1795), ('physical', 2003)):
            capability_name = {'pixel': 'kPixelCapabilities', 'physical': 'kPhysicalCapabilities'}[selected]
            metadata = fixture_metadata(selected)
            original = copy.deepcopy(metadata)
            header = generator.compiled_header(Inspection(metadata), document_profile=selected)
            with self.subTest(selection=selected):
                self.assertIn(generator.GENERATED_NOTICE, header)
                self.assertIn(generator.SELECTION_PREFIX + selected + '\n', header)
                self.assertIn('#include "shared/engine_document_profile.hpp"', header)
                self.assertIn('ProfileKind::' + selected, header)
                self.assertIn('EngineDocumentProfileFacts compiled_engine_document_profile', header)
                self.assertIn('"' + 'a' * 64 + '"', header)
                self.assertIn('"' + 'b' * 64 + '"', header)
                self.assertRegex(header, r'\.provider_capabilities\s*=\s*' + capability_name + r'\b')
                self.assertIn(capability_name + ' == ' + str(capabilities), header)
                for name in ('kBaseHeaderSha256', 'kExtensionHeaderSha256', 'kContractSha256',
                             'kCatalogSha256', 'kSchema', 'kAckSchema', 'kQueries', 'kCommands'):
                    self.assertIn(name, header)
                self.assertIn('static_assert', header)
                self.assertRegex(header, r'\.query_count\s*=')
                self.assertRegex(header, r'\.command_count\s*=')
                self.assertNotIn('EngineSurfaceProfileFacts', header)
                self.assertNotIn('compiled_engine_surface_profile', header)
                self.assertEqual(metadata, original)

    def test_legacy_embedded_ineligible_or_nonboolean_authority_is_rejected(self):
        for field, value in (
                ('scope', 'retained-consumer-byte-and-static-contract-only'),
                ('scope', 'embedded-retained-document-v2-consumer-byte-and-static-contract-only'),
                ('whole_group_verified', False), ('whole_group_verified', 1),
                ('production_eligible', False), ('production_eligible', 1)):
            metadata = fixture_metadata()
            metadata[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                generator.compiled_header(Inspection(metadata), document_profile='pixel')

    def test_profile_changes_and_cpp_injection_never_render(self):
        for field, value in (
                ('kind', 'foundation-copied-engine-v1'),
                ('binding', 'copied-owner-bridge/direct-worker-v1'),
                ('capabilities', '259'), ('provider_abi_minor', 0), ('host_abi_minor', 1),
                ('pointer_bits', True), ('pthread', 0), ('viewport_width', 801),
                ('contract_sha256', contract.BASE_HEADER_SHA256),
                ('base_header_sha256', contract.CONTRACT_SHA256),
                ('extension_header_sha256', contract.CONTRACT_SHA256),
                ('document_catalog_sha256', '0' * 64),
                ('document_schema_sha256', contract.ACTION_ACK_SCHEMA_SHA256),
                ('action_ack_schema_sha256', contract.DOCUMENT_SCHEMA_SHA256),
                ('build_sha256', '0' * 64), ('source_recipe_sha256', '0' * 64),
                ('build_sha256', '\"; injected_cpp(); //')):
            metadata = fixture_metadata()
            metadata['engine_profile'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                generator.compiled_header(Inspection(metadata), document_profile='pixel')

    def test_profile_cross_selection_and_added_physical_fields_reject(self):
        for selected, supplied in (('pixel', 'physical'), ('physical', 'pixel')):
            with self.subTest(selection=selected), self.assertRaises(ValueError):
                generator.compiled_header(Inspection(fixture_metadata(supplied)), document_profile=selected)
        metadata = fixture_metadata()
        metadata['engine_profile']['display_scale'] = 1
        with self.assertRaises(ValueError):
            generator.compiled_header(Inspection(metadata), document_profile='pixel')

    def test_build_recipe_provider_and_interface_joins_are_required(self):
        mutations = (
            lambda value: value.update(recipe_id='c' * 64),
            lambda value: value.update(provider_build_sha256='c' * 64),
            lambda value: value['provider_contract']['provider_abi'].update(minor=0),
            lambda value: value['provider_contract']['host_abi'].update(minor=1),
            lambda value: value['provider_contract']['commands'][1].update(required_reply_capacity=104),
            lambda value: value['provider_contract']['queries'][0].update(operation=1),
            lambda value: value['interfaces'].pop('extension_header'),
            lambda value: value['interfaces']['contract'].update(sha256=contract.EXTENSION_HEADER_SHA256),
            lambda value: value['interfaces']['action_ack_schema'].update(path='abi/other-ack.json'),
            lambda value: value['interfaces'].update(unrelated={'path': 'extra', 'sha256': 'a' * 64}),
        )
        for index, mutate in enumerate(mutations):
            metadata = fixture_metadata()
            mutate(metadata)
            with self.subTest(case=index), self.assertRaises(ValueError):
                generator.compiled_header(Inspection(metadata), document_profile='pixel')

    def test_cli_requires_selector_and_rejects_legacy_flag_before_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli_fixture(Path(temporary))
            omitted = list(arguments)
            position = omitted.index('--document-profile')
            del omitted[position:position + 2]
            cases = (omitted,
                     replace_argument(arguments, '--document-profile', '467'),
                     [*arguments, '--physical-input'],
                     [*arguments, '--engine-physical-input'])
            for selected in cases:
                with self.subTest(arguments=selected), \
                        patch.object(consumer, 'verify_kernel_consumer') as verify, \
                        patch.object(sys, 'stderr', new_callable=io.StringIO), \
                        self.assertRaises(SystemExit) as error:
                    generator.main(selected)
                self.assertEqual(error.exception.code, 2)
                verify.assert_not_called()
                self.assertFalse(output.parent.exists())

    def test_fresh_full_verification_receives_every_pin_and_explicit_selection(self):
        for selected in ('pixel', 'physical'):
            with self.subTest(selection=selected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                arguments, output = cli_fixture(root, selected)
                result, verify, printed = self.run_main(arguments)
                self.assertEqual(result, 0)
                verify.assert_called_once_with(root / 'group', expected_recipe='b' * 64,
                    expected_manifest='c' * 64, expected_proof='d' * 64,
                    expected_runtime='f' * 64, paired_sdk='e' * 64,
                    document_profile=selected,
                    kernel_target={'system': 'Emscripten', 'processor': 'wasm32',
                                   'triple': 'wasm32-emscripten', 'pointer_bits': 32})
                self.assertEqual(json.loads(printed), fixture_metadata(selected))
                self.assertEqual(output.read_text(encoding='utf-8'), generator.compiled_header(
                    Inspection(fixture_metadata(selected)), document_profile=selected))
                self.assertEqual(sorted(path.name for path in output.parent.iterdir()), [generator.HEADER_NAME])

    def test_repeated_invocation_reverifies_but_does_not_replace_identical_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli_fixture(Path(temporary))
            self.run_main(arguments)
            os.utime(output, ns=(1_000_000_000, 1_000_000_000))
            result, verify, _ = self.run_main(arguments)
            self.assertEqual(result, 0)
            verify.assert_called_once()
            self.assertEqual(output.stat().st_mtime_ns, 1_000_000_000)

    def test_changed_verified_build_replaces_only_owned_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli_fixture(Path(temporary))
            self.run_main(arguments)
            previous = output.read_bytes()
            metadata = fixture_metadata()
            metadata['provider_build_sha256'] = 'c' * 64
            metadata['engine_profile']['build_sha256'] = 'c' * 64
            self.run_main(arguments, metadata)
            self.assertNotEqual(output.read_bytes(), previous)
            self.assertIn('"' + 'c' * 64 + '"', output.read_text(encoding='utf-8'))
            self.assertEqual(sorted(path.name for path in output.parent.iterdir()), [generator.HEADER_NAME])

    def test_invalid_verified_inspection_leaves_no_output(self):
        for field, value in (('production_eligible', False),
                             ('scope', 'embedded-retained-document-v2-consumer-byte-and-static-contract-only')):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                arguments, output = cli_fixture(Path(temporary))
                metadata = fixture_metadata()
                metadata[field] = value
                with patch.object(consumer, 'verify_kernel_consumer', return_value=Inspection(metadata)), \
                        self.assertRaises(ValueError):
                    generator.main(arguments)
                self.assertFalse(output.parent.exists())

    def test_verification_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli_fixture(Path(temporary))
            self.run_main(arguments)
            previous = output.read_bytes()
            with patch.object(consumer, 'verify_kernel_consumer', side_effect=ValueError('group changed')), \
                    self.assertRaisesRegex(ValueError, 'group changed'):
                generator.main(arguments)
            self.assertEqual(output.read_bytes(), previous)
            self.assertEqual(sorted(path.name for path in output.parent.iterdir()), [generator.HEADER_NAME])

    def test_opposite_known_selection_rejects_before_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli_fixture(Path(temporary))
            output.parent.mkdir()
            previous = generator.compiled_header(Inspection(fixture_metadata('physical')),
                                                 document_profile='physical').encode('utf-8')
            output.write_bytes(previous)
            with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                generator.main(arguments)
            verify.assert_not_called()
            self.assertEqual(output.read_bytes(), previous)

    def test_identifiable_generated_header_with_bad_marker_rejects_before_verification(self):
        notice, prefix = generator.GENERATED_NOTICE, generator.SELECTION_PREFIX
        cases = (notice + '\n', notice + '\n' + prefix + 'unknown\n',
                 notice + '\n' + prefix + 'pixel\n' + prefix + 'pixel\n',
                 notice + '\n' + prefix + 'pixel\n' + prefix + 'physical\n',
                 notice + '\n// Document profile:pixel\n',
                 'compiled_engine_document_profile\n',
                 prefix + 'unknown\n')
        for previous in cases:
            with self.subTest(content=previous), tempfile.TemporaryDirectory() as temporary:
                arguments, output = cli_fixture(Path(temporary))
                output.parent.mkdir()
                output.write_text(previous, encoding='utf-8')
                with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                    generator.main(arguments)
                verify.assert_not_called()
                self.assertEqual(output.read_text(encoding='utf-8'), previous)

    def test_unrelated_placeholder_requires_successful_verification_before_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli_fixture(Path(temporary))
            output.parent.mkdir()
            previous = b'ordinary unrelated placeholder\n'
            output.write_bytes(previous)
            with patch.object(consumer, 'verify_kernel_consumer', side_effect=ValueError('not verified')), \
                    self.assertRaisesRegex(ValueError, 'not verified'):
                generator.main(arguments)
            self.assertEqual(output.read_bytes(), previous)
            self.run_main(arguments)
            self.assertNotEqual(output.read_bytes(), previous)

    def test_output_hardlink_or_symlink_is_never_replaced(self):
        for alias in ('hardlink', 'symlink'):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                arguments, output = cli_fixture(root)
                output.parent.mkdir()
                foreign = root / 'foreign-header'
                foreign.write_bytes(b'preserve foreign bytes')
                if alias == 'hardlink':
                    os.link(foreign, output)
                else:
                    output.symlink_to(foreign)
                with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                    generator.main(arguments)
                verify.assert_not_called()
                self.assertEqual(foreign.read_bytes(), b'preserve foreign bytes')
                self.assertEqual(output.read_bytes(), foreign.read_bytes())

    def test_linked_output_directory_is_rejected_before_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments, output = cli_fixture(root)
            foreign = root / 'foreign-directory'
            foreign.mkdir()
            output.parent.symlink_to(foreign, target_is_directory=True)
            with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                generator.main(arguments)
            verify.assert_not_called()
            self.assertEqual(list(foreign.iterdir()), [])

    def test_retained_group_and_build_root_cannot_contain_each_other(self):
        for case in ('same', 'build-in-group', 'group-in-build'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                arguments, output = cli_fixture(root)
                if case == 'same':
                    arguments = replace_argument(arguments, '--build-root', root / 'group')
                elif case == 'build-in-group':
                    build_root = root / 'group' / 'nested-build'
                    build_root.mkdir()
                    arguments = replace_argument(arguments, '--build-root', build_root)
                else:
                    group = root / 'build' / 'nested-group'
                    group.mkdir()
                    arguments = replace_argument(arguments, '--group', group)
                with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                    generator.main(arguments)
                verify.assert_not_called()
                self.assertFalse(output.parent.exists())

    def test_target_input_cannot_be_output_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments, output = cli_fixture(root)
            output.parent.mkdir()
            previous = (root / 'target.json').read_bytes()
            output.write_bytes(previous)
            arguments = replace_argument(arguments, '--kernel-target-json', output)
            with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                generator.main(arguments)
            verify.assert_not_called()
            self.assertEqual(output.read_bytes(), previous)

    def test_invalid_target_json_rejects_before_verification_or_output(self):
        for raw in (b'{"system":"Linux","system":"Emscripten"}',
                    b'\xef\xbb\xbf{}', b'{"scale":NaN}', b'{}\xff'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                arguments, output = cli_fixture(root)
                (root / 'target.json').write_bytes(raw)
                with patch.object(consumer, 'verify_kernel_consumer') as verify, self.assertRaises(ValueError):
                    generator.main(arguments)
                verify.assert_not_called()
                self.assertFalse(output.parent.exists())

    def test_atomic_replace_failure_preserves_header_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as temporary:
            arguments, output = cli_fixture(Path(temporary))
            self.run_main(arguments)
            previous = output.read_bytes()
            metadata = fixture_metadata()
            metadata['provider_build_sha256'] = 'c' * 64
            metadata['engine_profile']['build_sha256'] = 'c' * 64
            with patch.object(consumer, 'verify_kernel_consumer', return_value=Inspection(metadata)), \
                    patch.object(generator.os, 'replace', side_effect=OSError('replace failed')), \
                    self.assertRaisesRegex(OSError, 'replace failed'):
                generator.main(arguments)
            self.assertEqual(output.read_bytes(), previous)
            self.assertEqual(sorted(path.name for path in output.parent.iterdir()), [generator.HEADER_NAME])


if __name__ == '__main__':
    unittest.main()
