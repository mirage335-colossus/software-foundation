#!/usr/bin/env python3
"""Pure generator fixtures; no compiler, provider, SDK or runtime is launched."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_native_profile as profile
import appended_engine_document_contract as contract


def syntax_metadata():
    """Explicitly ineligible invented declarations, never retained evidence."""
    recipe, build = '1' * 64, '2' * 64
    facts = {'schema_version': 1, 'kind': profile.PROFILE_KIND, 'binding': 'private-native',
        'target': {'system': 'Linux', 'processor': 'x86_64', 'pointer_bits': 64, 'triple': 'x86_64-linux-gnu'},
        'document_profile': contract.PROFILE_NAMES['pixel'], 'provider_abi_major': 1, 'provider_abi_minor': 1,
        'host_abi_major': 1, 'host_abi_minor': 0, 'lifetime': 1, 'maximum_starts': 1,
        'viewport_width': 800, 'viewport_height': 600, 'capabilities': '1795',
        'base_header_sha256': contract.BASE_HEADER_SHA256, 'extension_header_sha256': contract.EXTENSION_HEADER_SHA256,
        'contract_sha256': contract.CONTRACT_SHA256, 'document_catalog_sha256': contract.DOCUMENT_CATALOG_SHA256,
        'document_schema_sha256': contract.DOCUMENT_SCHEMA_SHA256, 'action_ack_schema_sha256': contract.ACTION_ACK_SCHEMA_SHA256,
        'build_sha256': build, 'source_recipe_sha256': recipe}
    def item(path, kind='file', sha='7' * 64, mode=0o644, size=11):
        return {'path': path, 'kind': kind, 'mode': 0o755 if kind == 'directory' else mode,
                'bytes': 0 if kind == 'directory' else size, 'sha256': None if kind == 'directory' else sha}
    inventory = [item('NOTICE'), item('abi', 'directory'), item('abi/contract.json', sha=contract.CONTRACT_SHA256),
        item('bin', 'directory'), item('bin/provider.so', mode=0o755), item('data', 'directory'), item('data/config.json'),
        item('engine-sdk.json', sha='3' * 64), item('proof.json', sha='4' * 64),
        item('reports', 'directory'), item('reports/original.json'), item('runtime.json', sha='5' * 64)]
    return {'scope': 'syntactic-ineligible-unit-fixture', 'whole_group_verified': False, 'production_eligible': False,
        'recipe_id': recipe, 'binary_manifest_sha256': '3' * 64, 'proof_sha256': '4' * 64,
        'runtime_sha256': '5' * 64, 'provider_build_sha256': build, 'engine_profile': facts,
        'provider_entry': 'bin/provider.so', 'inventory': inventory,
        'notices': {'NOTICE': {'sha256': '7' * 64, 'bytes': 11, 'mode': 0o644}},
        'assets': {}, 'provider_contract': {}, 'provider_limits': {}, 'interfaces': {}}


class FakeInspection:
    def __init__(self, metadata):
        self.metadata = copy.deepcopy(metadata)
    def as_dict(self):
        return copy.deepcopy(self.metadata)


def mock_consumer(metadata):
    """A call-wiring unit double; it proves no artifact or runtime eligibility."""
    return types.SimpleNamespace(NativeConsumerInspection=FakeInspection,
        verify_kernel_consumer=mock.Mock(return_value=FakeInspection(metadata)),
        inspect_kernel_consumer=mock.Mock(side_effect=AssertionError('Inspect is not eligible admission')))


def arguments(metadata):
    return {'expected_recipe': metadata['recipe_id'], 'expected_manifest': metadata['binary_manifest_sha256'],
        'expected_proof': metadata['proof_sha256'], 'expected_runtime': metadata['runtime_sha256'],
        'kernel_target': copy.deepcopy(metadata['engine_profile']['target']), 'document_profile': 'pixel'}


def claimed_eligible_unit_double():
    metadata = syntax_metadata()
    metadata.update(scope=profile.NATIVE_SCOPE, whole_group_verified=True, production_eligible=True)
    return metadata


class RenderSyntax(unittest.TestCase):
    def setUp(self):
        self.metadata = syntax_metadata()

    def test_private_render_is_explicitly_ineligible_and_deterministic(self):
        original = copy.deepcopy(self.metadata)
        header = profile._render(self.metadata)
        self.assertTrue(header.startswith(profile.SYNTHETIC_NOTICE))
        self.assertNotIn(profile.GENERATED_NOTICE, header)
        self.assertEqual(header, profile._render(self.metadata))
        self.assertEqual(self.metadata, original)

    def test_complete_inventory_notices_and_exact_runtime_root_are_emitted(self):
        header = profile._render(self.metadata)
        for record in self.metadata['inventory']:
            self.assertIn(json.dumps(record['path']), header)
        self.assertIn('plan.root = runtime_root;', header)
        self.assertIn('const std::filesystem::path& runtime_root', header)
        self.assertNotIn('runtime_root /', header)
        self.assertNotIn('current_path', header)
        self.assertIn('plan.notices = {"NOTICE"};', header)
        self.assertIn('NativeEngineLoadAssetKind::directory, 0755u, UINT64_C(0), engine_document::Digest{}', header)
        self.assertNotIn('plan.expectation.limits', header)
        self.assertNotIn('plan.limits', header)
        self.assertNotIn('static_assert(engine_document::document_profile_valid', header)

    def test_group_or_developer_paths_never_enter_generated_literals(self):
        self.metadata['unrelated_developer_path'] = '/private/developer/source/group'
        self.metadata['notices']['NOTICE']['unrelated_developer_path'] = '/private/developer/source/notice'
        self.assertNotIn(self.metadata['unrelated_developer_path'], profile._render(self.metadata))
        self.assertNotIn(self.metadata['notices']['NOTICE']['unrelated_developer_path'], profile._render(self.metadata))

    def test_actual_constant_and_operation_assertions_are_emitted(self):
        header = profile._render(self.metadata)
        self.assertIn('namespace foundation::appended {', header)
        self.assertIn('compiled_native_engine_document_profile', header)
        self.assertIn('compiled_native_engine_load_plan', header)
        self.assertIn('{3, 48, 1048576, 512, engine_document::kSchema}', header)
        self.assertIn('{6, 6246, 1048576, 1024, engine_document::kSchema}', header)
        self.assertIn('{7, 8, 16, 1024, engine_document::kAckSchema}', header)
        self.assertIn('inline const engine_document::EngineDocumentProfileFacts', header)

    def test_each_canonical_pin_and_actual_build_source_crosspin_is_checked(self):
        for key in ('base_header_sha256', 'extension_header_sha256', 'contract_sha256',
                    'document_catalog_sha256', 'document_schema_sha256', 'action_ack_schema_sha256',
                    'build_sha256', 'source_recipe_sha256'):
            with self.subTest(field=key):
                changed = copy.deepcopy(self.metadata)
                changed['engine_profile'][key] = 'f' * 64
                with self.assertRaises(ValueError):
                    profile._render(changed)

    def test_digest_length_case_and_injection_cannot_enter_cpp(self):
        for pin in ('a' * 63, 'a' * 65, 'A' * 64, 'a' * 64 + '\n', '"}; evil(); //', '0' * 64):
            changed = copy.deepcopy(self.metadata); changed['proof_sha256'] = pin
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                profile._render(changed)

    def test_native_targets_are_explicit_and_browser_is_rejected(self):
        for system, processor, macro in (('Linux', 'aarch64', 'BIB_ENGINE_CPU_AARCH64'),
                                          ('Windows', 'x86_64', 'BIB_ENGINE_TARGET_WINDOWS')):
            changed = copy.deepcopy(self.metadata)
            changed['engine_profile']['target'].update(system=system, processor=processor, triple=processor + '-native')
            if system == 'Windows':
                changed['provider_entry'] = 'bin/provider.dll'
                next(item for item in changed['inventory'] if item['path'] == 'bin/provider.so')['path'] = 'bin/provider.dll'
            self.assertIn(macro, profile._render(changed))
        self.metadata['engine_profile']['target'].update(system='Emscripten', processor='wasm32', pointer_bits=32)
        with self.assertRaisesRegex(ValueError, 'native 64-bit'):
            profile._render(self.metadata)

    def test_unknown_physical_minor_and_boolean_numbers_are_rejected(self):
        for key, value in (('document_profile', contract.PROFILE_NAMES['physical']), ('provider_abi_minor', 0),
                           ('schema_version', True), ('lifetime', True), ('capabilities', 1795), ('viewport_width', 801)):
            changed = copy.deepcopy(self.metadata); changed['engine_profile'][key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                profile._render(changed)

    def test_every_inventory_row_is_closed_and_has_exact_parent_kind_mode(self):
        changes = (lambda rows: rows.pop(1),
            lambda rows: rows[1].__setitem__('mode', 0o644),
            lambda rows: rows[1].__setitem__('bytes', 1),
            lambda rows: rows[1].__setitem__('sha256', '0' * 64),
            lambda rows: rows[0].__setitem__('mode', True),
            lambda rows: rows[0].__setitem__('bytes', -1),
            lambda rows: rows[0].__setitem__('extra', 'unknown'),
            lambda rows: rows.reverse())
        for change in changes:
            changed = copy.deepcopy(self.metadata); change(changed['inventory'])
            with self.subTest(change=change), self.assertRaises(ValueError):
                profile._render(changed)

    def test_manifest_self_entry_pin_and_provider_must_be_complete(self):
        for name in ('engine-sdk.json', 'bin/provider.so'):
            changed = copy.deepcopy(self.metadata)
            changed['inventory'] = [item for item in changed['inventory'] if item['path'] != name]
            with self.subTest(member=name), self.assertRaises(ValueError):
                profile._render(changed)
        next(item for item in self.metadata['inventory'] if item['path'] == 'engine-sdk.json')['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'manifest'):
            profile._render(self.metadata)

    def test_path_injection_devices_aliases_and_traversal_reject(self):
        for path in ('../provider.so', 'bin//provider.so', 'bin/./provider.so', 'bin/provider.so/',
            'bin/CON.so', 'bin/COM1.so', 'bin/name .so.', 'bin/name.so ', '/absolute.so',
            'bin/name".so', 'bin/name\\.so', 'bin/name\n.so', 'bin/name\x00.so', 'bin/é.so', 'bin/name:.so', 'bin/name?.so'):
            changed = copy.deepcopy(self.metadata); changed['provider_entry'] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                profile._render(changed)
        self.metadata['inventory'].insert(1, {'path': 'notice', 'kind': 'file', 'mode': 0o644, 'bytes': 1, 'sha256': '9' * 64})
        with self.assertRaisesRegex(ValueError, 'case-unambiguous'):
            profile._render(self.metadata)

    def test_permitted_cpp_punctuation_remains_quoted_data(self):
        name = "data/notice;{brace}#apostrophe'"
        self.metadata['inventory'].append({'path': name, 'kind': 'file', 'mode': 0o644, 'bytes': 1, 'sha256': '9' * 64})
        self.metadata['inventory'].sort(key=lambda item: item['path'])
        header = profile._render(self.metadata)
        self.assertIn(json.dumps(name) + ', NativeEngineLoadAssetKind::file', header)

    def test_large_inventory_metadata_uses_bounded_canonical_comment_lines(self):
        for index in range(100):
            self.metadata['inventory'].append({'path': 'data/large-inventory-' + str(index).zfill(4) + '-' + 'x' * 80,
                'kind': 'file', 'mode': 0o644, 'bytes': 1, 'sha256': '9' * 64})
        self.metadata['inventory'].sort(key=lambda item: item['path'])
        header = profile._render(self.metadata)
        comments = [line for line in header.splitlines() if line.startswith(profile.METADATA_PREFIX)]
        self.assertGreater(len(comments), 1)
        self.assertTrue(all(len(line) <= len(profile.METADATA_PREFIX) + profile.METADATA_CHUNK_BYTES for line in comments))
        # This verifies canonical format recognition only; the private renderer
        # still cannot supply any retained group or qualify production output.
        recognized = header.replace(profile.SYNTHETIC_NOTICE, profile.GENERATED_NOTICE, 1).encode('ascii')
        with mock.patch.object(profile.manifest, 'MAX_MANIFEST', 1):
            profile._check_existing_selection(recognized, 'pixel')


class PublicAdmission(unittest.TestCase):
    def setUp(self):
        self.metadata = claimed_eligible_unit_double()
        self.arguments = arguments(self.metadata)
        self.consumer = mock_consumer(self.metadata)

    def test_public_function_always_reverifies_exact_group_and_arguments(self):
        limits = object(); self.arguments['limits'] = limits
        with mock.patch.object(profile, '_consumer', return_value=self.consumer):
            first = profile.compiled_header(Path('/synthetic/group-one'), **self.arguments)
            second = profile.compiled_header(Path('/synthetic/group-two'), **self.arguments)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(profile.GENERATED_NOTICE))
        self.assertNotIn('/synthetic/', first)
        self.assertEqual(self.consumer.verify_kernel_consumer.call_args_list,
            [mock.call(Path('/synthetic/group-one'), **self.arguments), mock.call(Path('/synthetic/group-two'), **self.arguments)])
        self.consumer.inspect_kernel_consumer.assert_not_called()

    def test_verification_failure_never_renders_or_falls_back(self):
        self.consumer.verify_kernel_consumer.side_effect = ValueError('Actual runtime incomplete')
        with mock.patch.object(profile, '_consumer', return_value=self.consumer), mock.patch.object(profile, '_render') as render:
            with self.assertRaisesRegex(ValueError, 'runtime incomplete'):
                profile.compiled_header('/synthetic/group', **self.arguments)
            render.assert_not_called(); self.consumer.inspect_kernel_consumer.assert_not_called()

    def test_parser_fixture_or_embedded_inspection_cannot_enable_public_output(self):
        for change in ({'production_eligible': False}, {'whole_group_verified': False}, {'scope': 'embedded-native'}):
            metadata = copy.deepcopy(self.metadata); metadata.update(change)
            with mock.patch.object(profile, '_consumer', return_value=mock_consumer(metadata)):
                with self.assertRaisesRegex(ValueError, 'fully verified eligible'):
                    profile.compiled_header('/synthetic/group', **self.arguments)

    def test_explicit_target_pin_and_selector_remain_bound_after_verification(self):
        for change in ({'expected_runtime': 'f' * 64}, {'document_profile': 'physical'},
                       {'kernel_target': dict(self.arguments['kernel_target'], processor='aarch64')}):
            selected = dict(self.arguments); selected.update(change)
            with mock.patch.object(profile, '_consumer', return_value=self.consumer):
                with self.assertRaises(ValueError):
                    profile.compiled_header('/synthetic/group', **selected)


class ParserFixtureIntegration(unittest.TestCase):
    def test_real_consumer_metadata_renders_only_as_private_synthetic_fixture(self):
        # These owned Stage-A archives contain only invented parser headers and
        # NOT RUN runtime records. The actual public verifier must reject them.
        sys.path.insert(0, str(ROOT / 'tests' / 'fixtures'))
        try:
            import appended_engine_native as fixture
        finally:
            sys.path.pop(0)
        consumer = profile._consumer()
        for target in (fixture.LINUX_X86_64, fixture.LINUX_AARCH64, fixture.WINDOWS_X86_64):
            with self.subTest(target=target), tempfile.TemporaryDirectory(prefix='native-profile-parser-fixture-') as temporary:
                group = fixture.build_group(temporary, target=target, with_dependency=True)
                pins = group['pins']
                selected = {'expected_recipe': pins['recipe'], 'expected_manifest': pins['manifest'],
                    'expected_proof': pins['proof'], 'expected_runtime': pins['runtime'],
                    'kernel_target': target, 'document_profile': 'pixel'}
                inspection = consumer.inspect_kernel_consumer(group['group'], **selected)
                metadata = inspection.as_dict()
                self.assertIs(metadata['whole_group_verified'], True)
                self.assertIs(metadata['production_eligible'], False)
                self.assertFalse(metadata['native_audit']['binary_scan_verified'])
                self.assertTrue(profile._render(metadata).startswith(profile.SYNTHETIC_NOTICE))
                with mock.patch.object(profile, '_render') as render:
                    with self.assertRaisesRegex(consumer.NativeConsumerError, 'production-ineligible'):
                        profile.compiled_header(group['group'], **selected)
                    render.assert_not_called()


class OutputCli(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-profile-synthetic-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.group, self.build = self.root / 'group', self.root / 'build'
        self.group.mkdir(); self.build.mkdir()
        self.metadata = claimed_eligible_unit_double()
        self.consumer = mock_consumer(self.metadata)
        self.target = self.root / 'target.json'
        self.target.write_text(json.dumps(self.metadata['engine_profile']['target']))
        self.output = self.build / profile.HEADER_DIRECTORY / profile.HEADER_NAME
        self.argv = ['--group', str(self.group), '--build-dir', str(self.build), '--kernel-target-json', str(self.target),
            '--document-profile', 'pixel']
        for name, value in (('recipe', 'recipe_id'), ('manifest', 'binary_manifest_sha256'),
                            ('proof', 'proof_sha256'), ('runtime', 'runtime_sha256')):
            self.argv.extend(['--' + name + '-sha256', self.metadata[value]])

    def run_cli(self):
        with mock.patch.object(profile, '_consumer', return_value=self.consumer), contextlib.redirect_stdout(io.StringIO()):
            return profile.main(self.argv)

    def test_cli_writes_exact_named_header_atomically_and_idempotently(self):
        self.assertEqual(self.run_cli(), 0)
        first = self.output.read_bytes(); before = self.output.stat().st_mtime_ns
        self.assertEqual(self.run_cli(), 0)
        self.assertEqual(self.output.read_bytes(), first)
        self.assertEqual(self.output.stat().st_mtime_ns, before)
        if os.name == 'posix':
            self.assertEqual(self.output.stat().st_mode & 0o7777, 0o644)

    def test_same_pixel_selection_may_update_admitted_pins(self):
        self.run_cli(); original = self.output.read_bytes()
        updated = copy.deepcopy(self.metadata)
        updated['provider_build_sha256'] = updated['engine_profile']['build_sha256'] = 'a' * 64
        self.consumer.verify_kernel_consumer.return_value = FakeInspection(updated)
        self.run_cli()
        self.assertNotEqual(self.output.read_bytes(), original)

    def test_failed_verification_creates_no_header_and_preserves_previous(self):
        self.consumer.verify_kernel_consumer.side_effect = ValueError('Fixture cannot qualify')
        with self.assertRaisesRegex(ValueError, 'cannot qualify'):
            self.run_cli()
        self.assertFalse(self.output.exists())
        self.consumer.verify_kernel_consumer.side_effect = None
        self.run_cli(); original = self.output.read_bytes()
        self.consumer.verify_kernel_consumer.side_effect = ValueError('Fixture cannot qualify')
        with self.assertRaises(ValueError):
            self.run_cli()
        self.assertEqual(self.output.read_bytes(), original)

    def test_foreign_malformed_or_changed_selection_is_never_overwritten(self):
        self.run_cli(); original = self.output.read_bytes()
        for content in (b'foreign user source\n', original.replace(b'profile: pixel', b'profile: physical'),
                        original.replace(b'plan.root = runtime_root;', b'plan.root = "foreign";')):
            self.output.write_bytes(content)
            with self.assertRaises(ValueError):
                self.run_cli()
            self.assertEqual(self.output.read_bytes(), content)

    def test_rehashed_foreign_payload_is_never_overwritten(self):
        self.run_cli()
        lines = self.output.read_bytes().splitlines(keepends=True)
        lines[-1] += b'inline int foreign_injected_code = 1;\n'
        lines[2] = (profile.PAYLOAD_PREFIX + hashlib.sha256(b''.join(lines[3:])).hexdigest() + '\n').encode('ascii')
        foreign = b''.join(lines)
        self.output.write_bytes(foreign)
        with self.assertRaisesRegex(ValueError, 'foreign content'):
            self.run_cli()
        self.assertEqual(self.output.read_bytes(), foreign)

    def test_rehashed_noncanonical_or_unknown_metadata_is_rejected(self):
        self.run_cli(); original = self.output.read_bytes()
        for altered in ({'extra': 'foreign'}, {'engine_profile': None}):
            lines = original.splitlines(keepends=True)
            end = 3
            while lines[end].startswith(profile.METADATA_PREFIX.encode('ascii')):
                end += 1
            metadata = json.loads(b''.join(line[len(profile.METADATA_PREFIX):-1] for line in lines[3:end]))
            metadata.update(altered)
            serialized = json.dumps(metadata, sort_keys=True, separators=(',', ':'))
            comments = [(profile.METADATA_PREFIX + serialized[index:index + profile.METADATA_CHUNK_BYTES] + '\n').encode('ascii')
                        for index in range(0, len(serialized), profile.METADATA_CHUNK_BYTES)]
            lines[3:end] = comments
            lines[2] = (profile.PAYLOAD_PREFIX + hashlib.sha256(b''.join(lines[3:])).hexdigest() + '\n').encode('ascii')
            foreign = b''.join(lines)
            self.output.write_bytes(foreign)
            with self.subTest(metadata=altered), self.assertRaises(ValueError):
                self.run_cli()
            self.assertEqual(self.output.read_bytes(), foreign)

    @unittest.skipUnless(hasattr(os, 'symlink'), 'Host lacks symlink fixtures')
    def test_linked_output_directory_or_file_is_rejected(self):
        elsewhere = self.root / 'elsewhere'; elsewhere.mkdir()
        directory = self.output.parent
        directory.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.run_cli()
        directory.unlink(); directory.mkdir()
        foreign = elsewhere / 'foreign.hpp'; foreign.write_bytes(b'preserve foreign')
        self.output.symlink_to(foreign)
        with self.assertRaises(ValueError):
            self.run_cli()
        self.assertEqual(foreign.read_bytes(), b'preserve foreign')

    def test_output_cannot_overlap_retained_group(self):
        index = self.argv.index('--build-dir') + 1
        self.argv[index] = str(self.group)
        with self.assertRaisesRegex(ValueError, 'separate'):
            self.run_cli()

    def test_windows_writer_does_not_require_unavailable_python39_fchmod(self):
        with mock.patch.object(profile.os, 'fchmod', None, create=True), mock.patch.object(profile.os, 'chmod') as change:
            profile._temporary_mode(12, Path('/synthetic/temporary'), windows=True)
            change.assert_called_once_with(Path('/synthetic/temporary'), 0o644)
            with self.assertRaisesRegex(ValueError, 'POSIX descriptor modes'):
                profile._temporary_mode(12, Path('/synthetic/temporary'), windows=False)

def actions_syntax_metadata():
    """Invented native4083 syntax facts, with no artifact/runtime authority."""
    metadata = syntax_metadata()
    actions = profile._actions_contract()
    metadata['engine_profile'] = actions.expected_engine_profile(
        kernel_target=metadata['engine_profile']['target'], actions_profile='document-actions-v1',
        build_sha256=metadata['provider_build_sha256'], source_recipe_sha256=metadata['recipe_id'])
    next(item for item in metadata['inventory'] if item['path'] == 'abi/contract.json')['sha256'] = metadata['engine_profile']['contract_sha256']
    return metadata


def actions_arguments(metadata):
    result = arguments(metadata)
    result.pop('document_profile')
    result['actions_profile'] = 'document-actions-v1'
    return result


def claimed_eligible_actions_unit_double():
    metadata = actions_syntax_metadata()
    metadata.update(scope=profile._actions_contract().SCOPE, whole_group_verified=True, production_eligible=True)
    return metadata


def mock_actions_consumer(metadata):
    """Only a unit call-wiring double; it proves no eligible retained input."""
    return types.SimpleNamespace(NativeConsumerInspection=FakeInspection,
        verify_actions_kernel_consumer=mock.Mock(return_value=FakeInspection(metadata)),
        verify_kernel_consumer=mock.Mock(side_effect=AssertionError('Legacy verifier cannot admit actions')),
        inspect_actions_kernel_consumer=mock.Mock(side_effect=AssertionError('Inspect cannot admit actions')))


class ActionsRenderSyntax(unittest.TestCase):
    def setUp(self):
        self.metadata = actions_syntax_metadata()

    def test_private_actions_output_is_deterministic_and_legacy_bytes_stay_exact(self):
        original = copy.deepcopy(self.metadata)
        first = profile._render_actions(self.metadata)
        self.assertTrue(first.startswith(profile.SYNTHETIC_NOTICE + '\n' + profile.ACTIONS_SELECTION_PREFIX))
        self.assertNotIn(profile.GENERATED_NOTICE, first)
        self.assertEqual(first, profile._render_actions(self.metadata))
        self.assertEqual(self.metadata, original)
        self.assertEqual(hashlib.sha256(profile._render(syntax_metadata()).encode('ascii')).hexdigest(),
            'eee63056840ff5e8c483abde87e0433afc6e81e02ffac9053a74218b654d51b0')

    def test_only_typed_actions_facts_and_expectation_are_emitted(self):
        header = profile._render_actions(self.metadata)
        self.assertIn('inline const engine_document_actions::EngineDocumentActionsProfileFacts compiled_native_engine_document_actions_profile', header)
        self.assertIn('plan.expectation.document_actions_profile = compiled_native_engine_document_actions_profile;', header)
        for legacy in ('plan.expectation.document_profile', 'plan.expectation.editor_profile',
                       'inline const engine_document::EngineDocumentProfileFacts', 'inline const engine_editor::EngineEditorProfileFacts'):
            self.assertNotIn(legacy, header)
        self.assertIn('plan.schema_version = 1;', header)
        self.assertIn('plan.root = runtime_root;', header)
        self.assertNotIn('runtime_root /', header)
        for record in self.metadata['inventory']:
            self.assertIn(json.dumps(record['path']), header)
        self.assertIn('plan.notices = {"NOTICE"};', header)
        self.assertNotIn('plan.limits', header)

    def test_all_inherited_and_actions_pins_and_complete_catalogs_are_asserted(self):
        header = profile._render_actions(self.metadata)
        facts = self.metadata['engine_profile']
        for name, pin in facts.items():
            if name.endswith('_sha256'):
                self.assertIn(profile._cpp_digest(pin), header, name)
        self.assertIn('static_assert(engine_document_actions::kQueries == std::array<engine_document::OperationFacts, 2>', header)
        self.assertIn('static_assert(engine_document_actions::kCommands == std::array<engine_document::OperationFacts, 9>', header)
        descriptor = profile._actions_contract().provider_contract(kernel_target=facts['target'], actions_profile='document-actions-v1')
        for item in descriptor['queries'] + descriptor['commands']:
            row = '{' + ', '.join(str(item[key]) for key in ('operation', 'maximum_input_bytes', 'required_reply_capacity', 'capability'))
            self.assertIn(row + ', ' + profile._cpp_digest(item['schema_sha256']) + '}', header)
        self.assertIn('BIB_ENGINE_EDITOR_MAX_WIRE_BYTES == 1048576 && BIB_ENGINE_EDITOR_MAX_QUERY_BYTES == 236', header)
        self.assertIn('.query_count = 2, .command_count = 9', header)

    def test_all_forty_profile_fields_are_closed_exact_and_strictly_typed(self):
        self.assertEqual(len(self.metadata['engine_profile']), 40)
        for name, value in self.metadata['engine_profile'].items():
            changed = copy.deepcopy(self.metadata)
            changed['engine_profile'][name] = True if type(value) is int else ('foreign' if type(value) is str else {})
            with self.subTest(field=name), self.assertRaises(ValueError):
                profile._render_actions(changed)
            changed = copy.deepcopy(self.metadata); del changed['engine_profile'][name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                profile._render_actions(changed)
        changed = copy.deepcopy(self.metadata); changed['engine_profile']['unknown'] = 1
        with self.assertRaises(ValueError):
            profile._render_actions(changed)

    def test_legacy_and_actions_profiles_cross_feed_fail_closed(self):
        with self.assertRaises(ValueError):
            profile._render_actions(syntax_metadata())
        with self.assertRaises(ValueError):
            profile._render(self.metadata)
        for key, value in (('document_profile', contract.PROFILE_NAMES['pixel']), ('pthread', False), ('shared_memory', False)):
            changed = copy.deepcopy(self.metadata); changed['engine_profile'][key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                profile._render_actions(changed)

    def test_actions_native_targets_and_provider_extensions_are_explicit(self):
        for system, processor, macro in (('Linux', 'aarch64', 'BIB_ENGINE_CPU_AARCH64'),
                                          ('Windows', 'x86_64', 'BIB_ENGINE_TARGET_WINDOWS')):
            changed = copy.deepcopy(self.metadata)
            changed['engine_profile']['target'].update(system=system, processor=processor, triple=processor + '-native')
            if system == 'Windows':
                changed['provider_entry'] = 'bin/provider.dll'
                next(item for item in changed['inventory'] if item['path'] == 'bin/provider.so')['path'] = 'bin/provider.dll'
            self.assertIn(macro, profile._render_actions(changed))
        for changes in ({'system': 'Emscripten', 'processor': 'wasm32', 'pointer_bits': 32},
                        {'system': 'Windows', 'processor': 'aarch64'}, {'pointer_bits': True}, {'triple': ''}):
            changed = copy.deepcopy(self.metadata); changed['engine_profile']['target'].update(changes)
            with self.subTest(target=changes), self.assertRaises(ValueError):
                profile._render_actions(changed)
        changed = copy.deepcopy(self.metadata); changed['provider_entry'] = 'bin/provider.exe'
        with self.assertRaises(ValueError):
            profile._render_actions(changed)

    def test_actions_inventory_and_independent_pins_cannot_be_forged(self):
        for name in ('recipe_id', 'provider_build_sha256', 'binary_manifest_sha256'):
            changed = copy.deepcopy(self.metadata); changed[name] = 'f' * 64
            with self.subTest(pin=name), self.assertRaises(ValueError):
                profile._render_actions(changed)
        for mutation in (lambda value: value['inventory'].reverse(),
                         lambda value: value['inventory'].pop(1),
                         lambda value: value['inventory'][0].__setitem__('mode', True),
                         lambda value: value['inventory'][0].__setitem__('bytes', -1),
                         lambda value: value['inventory'][0].__setitem__('unknown', 1),
                         lambda value: value['notices']['NOTICE'].__setitem__('sha256', 'f' * 64),
                         lambda value: value.__setitem__('provider_entry', '../provider.so')):
            changed = copy.deepcopy(self.metadata); mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                profile._render_actions(changed)

    def test_nonemitted_paths_are_trimmed_and_header_metadata_is_bounded(self):
        self.metadata['unrelated_developer_path'] = '/private/developer/source/group'
        self.metadata['notices']['NOTICE']['unrelated_developer_path'] = '/private/developer/source/notice'
        for index in range(100):
            self.metadata['inventory'].append({'path': 'data/large-' + str(index).zfill(4) + '-' + 'x' * 80,
                'kind': 'file', 'mode': 0o644, 'bytes': 1, 'sha256': '9' * 64})
        self.metadata['inventory'].sort(key=lambda item: item['path'])
        header = profile._render_actions(self.metadata)
        self.assertNotIn('/private/developer/', header)
        comments = [line for line in header.splitlines() if line.startswith(profile.METADATA_PREFIX)]
        self.assertGreater(len(comments), 1)
        self.assertTrue(all(len(line) <= len(profile.METADATA_PREFIX) + profile.METADATA_CHUNK_BYTES for line in comments))
        recognized = header.replace(profile.SYNTHETIC_NOTICE, profile.GENERATED_NOTICE, 1).encode('ascii')
        profile._check_existing_actions_selection(recognized, 'document-actions-v1')
        with mock.patch.object(profile, 'MAX_HEADER_BYTES', 1), self.assertRaisesRegex(ValueError, 'byte bound'):
            profile._render_actions(self.metadata)


class ActionsPublicAdmission(unittest.TestCase):
    def setUp(self):
        self.metadata = claimed_eligible_actions_unit_double()
        self.arguments = actions_arguments(self.metadata)
        self.consumer = mock_actions_consumer(self.metadata)

    def test_public_actions_function_reverifies_every_exact_group_and_argument(self):
        self.arguments['limits'] = object()
        with mock.patch.object(profile, '_consumer', return_value=self.consumer):
            first = profile.compiled_actions_header(Path('/synthetic/group-one'), **self.arguments)
            second = profile.compiled_actions_header(Path('/synthetic/group-two'), **self.arguments)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(profile.GENERATED_NOTICE))
        self.assertNotIn('/synthetic/', first)
        self.assertEqual(self.consumer.verify_actions_kernel_consumer.call_args_list,
            [mock.call(Path('/synthetic/group-one'), **self.arguments), mock.call(Path('/synthetic/group-two'), **self.arguments)])
        self.consumer.verify_kernel_consumer.assert_not_called()
        self.consumer.inspect_actions_kernel_consumer.assert_not_called()

    def test_failed_actions_verification_never_renders_or_falls_back(self):
        self.consumer.verify_actions_kernel_consumer.side_effect = ValueError('Original actual runtime incomplete')
        with mock.patch.object(profile, '_consumer', return_value=self.consumer), mock.patch.object(profile, '_render_actions') as render:
            with self.assertRaisesRegex(ValueError, 'actual runtime incomplete'):
                profile.compiled_actions_header('/synthetic/group', **self.arguments)
            render.assert_not_called()
        self.consumer.verify_kernel_consumer.assert_not_called()
        self.consumer.inspect_actions_kernel_consumer.assert_not_called()

    def test_parser_embedded_legacy_and_nonboolean_eligibility_are_rejected(self):
        for change in ({'production_eligible': False}, {'whole_group_verified': False}, {'production_eligible': 1},
                       {'scope': profile.NATIVE_SCOPE}, {'scope': profile._actions_contract().EMBEDDED_SCOPE}):
            metadata = copy.deepcopy(self.metadata); metadata.update(change)
            with mock.patch.object(profile, '_consumer', return_value=mock_actions_consumer(metadata)), self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, 'fully verified eligible'):
                    profile.compiled_actions_header('/synthetic/group', **self.arguments)
        self.consumer.verify_actions_kernel_consumer.return_value = self.metadata
        with mock.patch.object(profile, '_consumer', return_value=self.consumer), self.assertRaisesRegex(ValueError, 'inspection'):
            profile.compiled_actions_header('/synthetic/group', **self.arguments)

    def test_malformed_actions_profile_metadata_is_rejected_before_render(self):
        for malformed in (None, [], 'foreign'):
            metadata = copy.deepcopy(self.metadata); metadata['engine_profile'] = malformed
            with mock.patch.object(profile, '_consumer', return_value=mock_actions_consumer(metadata)), mock.patch.object(profile, '_render_actions') as render:
                with self.subTest(profile=malformed), self.assertRaises(ValueError):
                    profile.compiled_actions_header('/synthetic/group', **self.arguments)
                render.assert_not_called()

    def test_actions_selector_full_target_and_all_independent_pins_rebind(self):
        changes = [{key: 'f' * 64} for key in ('expected_recipe', 'expected_manifest', 'expected_proof', 'expected_runtime')]
        changes += [{'actions_profile': 'pixel'}, {'actions_profile': None},
                    {'kernel_target': dict(self.arguments['kernel_target'], triple='different-triple')},
                    {'kernel_target': dict(self.arguments['kernel_target'], processor='aarch64')}]
        for change in changes:
            selected = dict(self.arguments); selected.update(change)
            with mock.patch.object(profile, '_consumer', return_value=self.consumer), self.subTest(change=change), self.assertRaises(ValueError):
                profile.compiled_actions_header('/synthetic/group', **selected)


class ActionsOutputCli(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-actions-profile-synthetic-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.group, self.build = self.root / 'group', self.root / 'build'
        self.group.mkdir(); self.build.mkdir()
        self.metadata = claimed_eligible_actions_unit_double()
        self.consumer = mock_actions_consumer(self.metadata)
        self.target = self.root / 'target.json'
        self.target.write_text(json.dumps(self.metadata['engine_profile']['target']))
        self.output = self.build / profile.ACTIONS_HEADER_DIRECTORY / profile.HEADER_NAME
        self.argv = ['--group', str(self.group), '--build-dir', str(self.build), '--kernel-target-json', str(self.target),
            '--actions-profile', 'document-actions-v1']
        for name, value in (('recipe', 'recipe_id'), ('manifest', 'binary_manifest_sha256'),
                            ('proof', 'proof_sha256'), ('runtime', 'runtime_sha256')):
            self.argv.extend(['--' + name + '-sha256', self.metadata[value]])

    def run_cli(self):
        with mock.patch.object(profile, '_consumer', return_value=self.consumer), contextlib.redirect_stdout(io.StringIO()):
            return profile.main(self.argv)

    def test_actions_output_is_atomic_idempotent_separate_and_reports_selector(self):
        stream = io.StringIO()
        with mock.patch.object(profile, '_consumer', return_value=self.consumer), contextlib.redirect_stdout(stream):
            self.assertEqual(profile.main(self.argv), 0)
        result = json.loads(stream.getvalue())
        self.assertEqual(result['actions_profile'], 'document-actions-v1')
        self.assertNotIn('document_profile', result)
        self.assertEqual(result['header'], str(self.output))
        first = self.output.read_bytes(); before = self.output.stat().st_mtime_ns
        self.assertEqual(self.run_cli(), 0)
        self.assertEqual(self.output.read_bytes(), first)
        self.assertEqual(self.output.stat().st_mtime_ns, before)
        self.assertFalse((self.build / profile.HEADER_DIRECTORY).exists())
        if os.name == 'posix':
            self.assertEqual(self.output.stat().st_mode & 0o7777, 0o644)

    def test_same_actions_selection_can_update_admitted_build_pins(self):
        self.run_cli(); first = self.output.read_bytes()
        updated = copy.deepcopy(self.metadata)
        updated['provider_build_sha256'] = updated['engine_profile']['build_sha256'] = 'a' * 64
        self.consumer.verify_actions_kernel_consumer.return_value = FakeInspection(updated)
        self.run_cli()
        self.assertNotEqual(self.output.read_bytes(), first)

    def test_failed_actions_verification_creates_no_output_and_preserves_existing(self):
        self.consumer.verify_actions_kernel_consumer.side_effect = ValueError('Actual runtime missing')
        with self.assertRaises(ValueError):
            self.run_cli()
        self.assertFalse(self.output.exists())
        self.consumer.verify_actions_kernel_consumer.side_effect = None
        self.run_cli(); first = self.output.read_bytes()
        self.consumer.verify_actions_kernel_consumer.side_effect = ValueError('Actual runtime missing')
        with self.assertRaises(ValueError):
            self.run_cli()
        self.assertEqual(self.output.read_bytes(), first)

    def test_cli_requires_exactly_one_explicit_profile_selector(self):
        for argv in (self.argv + ['--document-profile', 'pixel'],
                     [item for index, item in enumerate(self.argv) if index not in
                      (self.argv.index('--actions-profile'), self.argv.index('--actions-profile') + 1)]):
            with mock.patch.object(profile, '_consumer', return_value=self.consumer), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                profile.main(argv)
        self.consumer.verify_actions_kernel_consumer.assert_not_called()
        self.assertFalse(self.output.parent.exists())

    def test_foreign_legacy_synthetic_and_changed_selection_headers_are_preserved(self):
        self.run_cli(); first = self.output.read_bytes()
        legacy = profile._render(syntax_metadata()).replace(profile.SYNTHETIC_NOTICE, profile.GENERATED_NOTICE, 1).encode('ascii')
        for content in (b'foreign user source\n', legacy,
                        first.replace(profile.GENERATED_NOTICE.encode('ascii'), profile.SYNTHETIC_NOTICE.encode('ascii'), 1),
                        first.replace(b'profile: document-actions-v1', b'profile: pixel', 1)):
            self.output.write_bytes(content)
            with self.subTest(prefix=content[:100]), self.assertRaises(ValueError):
                self.run_cli()
            self.assertEqual(self.output.read_bytes(), content)
        with self.assertRaises(ValueError):
            profile._check_existing_selection(first, 'pixel')

    def test_rehashed_foreign_actions_cpp_payload_is_preserved(self):
        self.run_cli()
        lines = self.output.read_bytes().splitlines(keepends=True)
        lines[-1] += b'inline int foreign_injected_code = 1;\n'
        lines[2] = (profile.PAYLOAD_PREFIX + hashlib.sha256(b''.join(lines[3:])).hexdigest() + '\n').encode('ascii')
        foreign = b''.join(lines); self.output.write_bytes(foreign)
        with self.assertRaisesRegex(ValueError, 'foreign content'):
            self.run_cli()
        self.assertEqual(self.output.read_bytes(), foreign)

    def test_rehashed_unknown_or_noncanonical_actions_metadata_is_preserved(self):
        self.run_cli(); first = self.output.read_bytes()
        for altered in ({'extra': 'foreign'}, {'engine_profile': None}):
            lines = first.splitlines(keepends=True); end = 3
            while lines[end].startswith(profile.METADATA_PREFIX.encode('ascii')):
                end += 1
            metadata = json.loads(b''.join(line[len(profile.METADATA_PREFIX):-1] for line in lines[3:end]))
            metadata.update(altered)
            serialized = json.dumps(metadata, sort_keys=True, separators=(',', ':'))
            lines[3:end] = [(profile.METADATA_PREFIX + serialized[index:index + profile.METADATA_CHUNK_BYTES] + '\n').encode('ascii')
                for index in range(0, len(serialized), profile.METADATA_CHUNK_BYTES)]
            lines[2] = (profile.PAYLOAD_PREFIX + hashlib.sha256(b''.join(lines[3:])).hexdigest() + '\n').encode('ascii')
            foreign = b''.join(lines); self.output.write_bytes(foreign)
            with self.subTest(metadata=altered), self.assertRaises(ValueError):
                self.run_cli()
            self.assertEqual(self.output.read_bytes(), foreign)

    @unittest.skipUnless(hasattr(os, 'symlink'), 'Host lacks symlink fixtures')
    def test_actions_linked_output_directory_or_file_is_rejected(self):
        elsewhere = self.root / 'elsewhere'; elsewhere.mkdir()
        self.output.parent.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.run_cli()
        self.output.parent.unlink(); self.output.parent.mkdir()
        foreign = elsewhere / 'foreign.hpp'; foreign.write_bytes(b'preserve foreign')
        self.output.symlink_to(foreign)
        with self.assertRaises(ValueError):
            self.run_cli()
        self.assertEqual(foreign.read_bytes(), b'preserve foreign')

    def test_actions_output_rejects_retained_and_target_input_overlap(self):
        index = self.argv.index('--build-dir') + 1
        self.argv[index] = str(self.group)
        with self.assertRaisesRegex(ValueError, 'separate'):
            self.run_cli()
        self.argv[index] = str(self.build)
        self.run_cli(); first = self.output.read_bytes()
        self.argv[self.argv.index('--kernel-target-json') + 1] = str(self.output)
        with self.assertRaisesRegex(ValueError, 'target input'):
            self.run_cli()
        self.assertEqual(self.output.read_bytes(), first)



class ActionsParserFixtureIntegration(unittest.TestCase):
    def test_real_actions_consumer_metadata_stays_private_and_public_admission_rejects(self):
        # These owned Stage-A archives contain invented parser bytes and NOT RUN
        # reports. They can exercise full metadata parsing, never actual eligibility.
        sys.path.insert(0, str(ROOT / 'tests' / 'fixtures'))
        try:
            import appended_engine_native as fixture
        finally:
            sys.path.pop(0)
        consumer = profile._consumer()
        for target in (fixture.LINUX_X86_64, fixture.LINUX_AARCH64, fixture.WINDOWS_X86_64):
            with self.subTest(target=target), tempfile.TemporaryDirectory(prefix='native-actions-profile-parser-fixture-') as temporary:
                group = fixture.build_group(temporary, target=target, with_dependency=True,
                    actions_profile='document-actions-v1')
                pins = group['pins']
                selected = {'expected_recipe': pins['recipe'], 'expected_manifest': pins['manifest'],
                    'expected_proof': pins['proof'], 'expected_runtime': pins['runtime'],
                    'kernel_target': target, 'actions_profile': 'document-actions-v1'}
                metadata = consumer.inspect_actions_kernel_consumer(group['group'], **selected).as_dict()
                self.assertEqual(metadata['scope'], profile._actions_contract().SCOPE)
                self.assertIs(metadata['whole_group_verified'], True)
                self.assertIs(metadata['production_eligible'], False)
                self.assertFalse(metadata['native_audit']['binary_scan_verified'])
                self.assertTrue(profile._render_actions(metadata).startswith(profile.SYNTHETIC_NOTICE))
                with mock.patch.object(profile, '_render_actions') as render:
                    with self.assertRaisesRegex(consumer.NativeConsumerError, 'production-ineligible'):
                        profile.compiled_actions_header(group['group'], **selected)
                    render.assert_not_called()


if __name__ == '__main__':
    unittest.main()
