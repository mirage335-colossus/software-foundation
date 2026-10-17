"""Inert Windows metadata/writer/controller fixtures; no real producer runs."""
import copy
from collections import namedtuple
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_prepare as prepare
import appended_engine_windows_handoff as handoff
import appended_engine_windows_contract as contract
import appended_engine_manifest as manifest


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


def reference(path):
    return {'path': str(path), 'sha256': pin(str(path).encode())}


def candidate_inputs():
    names = {name: ('helper' if name.endswith('.py') else 'config') for name in (
        *prepare.NATIVE_HELPERS, handoff.GENERATOR, handoff.TEMPLATE, handoff.CONFIG,
        prepare.NATIVE_INPUTS_PATH, prepare.DEPENDENCY_PATH, prepare.IDENTITY_PATH)}
    names.update({name: 'interface' for name in prepare.actions.INTERFACE_PATHS.values()})
    names['supplier/wrapper.txt'] = names['supplier/engine.txt'] = 'source'
    names['licenses/NOTICE'] = 'license'
    names['ordered-patches/000.patch'] = 'patch'
    records = {name: {'sha256': pin(name.encode()), 'role': role, 'mode': 0o644}
               for name, role in names.items()}
    records[prepare.DEPENDENCY_PATH]['role'] = 'data'
    for role, name in prepare.actions.INTERFACE_PATHS.items():
        records[name]['sha256'] = prepare.actions._pins()[role]
    records['ordered-patches/000.patch']['sha256'] = prepare.native_source.SUPPLIER_PATCH
    suppliers = {name: {'repository': 'https://example.invalid/' + name,
        'commit': ('68c618544e1f8af18ebce346281a6a49766aa194' if name == 'wrapper' else prepare.native_source.ENGINE_COMMIT),
        'archive': 'supplier/' + name + '.txt'} for name in ('wrapper', 'engine')}
    return records, suppliers


class SelectionTests(unittest.TestCase):
    def setUp(self):
        from test_appended_engine_windows_source_replay import Fixture, no_programs
        self.no_programs = no_programs
        self.temporary = tempfile.TemporaryDirectory(prefix='windows-prepare-selection-inert-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        bindings = Fixture().seal().bindings()
        for key in ('archives', 'provenance', 'original_proof'):
            for item in bindings[key].values():
                item['path'] = str(self.root / item['path'])
        for key in ('patches', 'notices'):
            for item in bindings[key]:
                item['path'] = str(self.root / item['path'])
        self.selection = {'schema_version': 1, 'kind': prepare.KIND,
            'target': copy.deepcopy(contract.TARGET), 'source_catalogue': copy.deepcopy(contract.CATALOGUE),
            'repository_root': str(self.root / 'repository'), 'bindings': bindings,
            'phase_limits': {name: min(value, 10) for name, value in prepare.LIMITS.items()},
            **{role: reference(self.root / (role + '.json')) for role in prepare.METADATA_REFS}}

    def test_closed_selection_keeps_windows_paths_inert_and_bounds_explicit(self):
        original = copy.deepcopy(self.selection)
        with self.no_programs():
            self.assertEqual(prepare.validate_selection(self.selection), original)
        self.assertEqual(self.selection, original)
        for field, value in (('target', prepare.native_source.TARGET),
                ('schema_version', True), ('unknown', 'caller admission')):
            changed = copy.deepcopy(self.selection)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare.validate_selection(changed)
        changed = copy.deepcopy(self.selection)
        changed['phase_limits']['maximum_processes'] = True
        with self.assertRaisesRegex(ValueError, 'finite bound'):
            prepare.validate_selection(changed)

    def test_missing_explicit_metadata_fails_before_catalogue_or_supplier_capture(self):
        raw = prepare.encoded(self.selection)
        path = self.root / 'selection.json'
        path.write_bytes(raw)
        with self.no_programs(), mock.patch.object(prepare._replay(), 'catalogue_metadata',
                side_effect=AssertionError('catalogue capture before missing metadata')):
            with self.assertRaises(prepare.MissingInputs) as context:
                prepare.inspect_prepare(path, pin(raw))
        self.assertEqual({item['role'] for item in context.exception.missing}, set(prepare.METADATA_REFS))
        self.assertFalse((self.root / 'output').exists())

    def test_absent_selection_is_a_named_missing_input(self):
        with self.no_programs(), self.assertRaises(prepare.MissingInputs) as context:
            prepare.inspect_prepare(self.root / 'absent-selection.json', pin(b'absent'))
        self.assertEqual(context.exception.missing[0]['role'], 'windows-source-preparation-selection')

    def test_catalogue_graph_is_opaque_text_and_reaches_named_missing_admissions(self):
        from test_appended_engine_windows_source_replay import Fixture, MetadataFixture
        catalogue = MetadataFixture()
        selected = copy.deepcopy(self.selection)
        selected['source_catalogue'] = copy.deepcopy(catalogue.catalogue)
        selected['repository_root'] = str(self.root / 'repository')
        for role, body in catalogue.raw.items():
            path = self.root / 'repository' / catalogue.catalogue[role]['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        for role in prepare.METADATA_REFS:
            body = prepare.encoded(Fixture().seal().projection) if role == 'source_projection' else b'{}\n'
            path = self.root / (role + '.json')
            path.write_bytes(body)
            selected[role] = {'path': str(path), 'sha256': pin(body)}
        path = self.root / 'complete-inert-selection.json'
        raw = prepare.encoded(selected)
        path.write_bytes(raw)
        proof = SimpleNamespace(validate_source_declarations=mock.Mock(side_effect=prepare._missing(
            'windows-dependency-source-declaration-join', 'inert-dependency-review', 'fixture blocks admission')))
        with self.no_programs(), mock.patch.object(contract, 'CATALOGUE', catalogue.catalogue), \
                mock.patch.object(prepare, 'RUNTIME_SEAM_SHA256', None), \
                mock.patch.object(prepare, 'PROCESS_TREE_SEAM_SHA256', None), \
                mock.patch.object(prepare._replay(), 'SOURCE_SEAM_SHA256', None), \
                mock.patch.object(contract, 'validate_inputs', return_value={}), \
                mock.patch.dict(sys.modules, {'appended_engine_windows_dependency_proof': proof}):
            with self.assertRaises(prepare.MissingInputs) as context:
                prepare.inspect_prepare(path, pin(raw))
        self.assertEqual({item['role'] for item in context.exception.missing}, {
            'windows-dependency-source-declaration-join', 'native-original-source-proof-data-seam',
            'posix-metadata-controller-runtime-admission', 'posix-metadata-controller-resource-adapter'})
        proof.validate_source_declarations.assert_called_once()


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.records, self.suppliers = candidate_inputs()
        self.identity = self.records[prepare.IDENTITY_PATH]['sha256']

    def compose(self, records=None):
        before = {'Source/modified' + str(index): pin(('before' + str(index)).encode()) for index in range(45)}
        before.update({'Source/added' + str(index): None for index in range(23)})
        patches = [{'path': 'ordered-patches/000.patch', 'tree': 'engine', 'preimages': before,
                    'postimages': {name: pin(('after' + name).encode()) for name in before}}]
        return prepare._metadata_documents(self.records if records is None else records,
            self.identity, self.suppliers, patches, ['licenses/NOTICE'])

    def test_genuine_windows_recipe_sources_build_normal_forms_are_candidates(self):
        result = self.compose()
        recipe, sources, build = (json.loads(result[name]) for name in ('recipe', 'sources', 'provider_build'))
        self.assertEqual(recipe['target'], contract.TARGET)
        self.assertEqual(build['target'], contract.TARGET)
        self.assertEqual(build, handoff._expected_build(recipe, result['recipe_sha256']))
        self.assertEqual(sources['recipe_id'], result['recipe_sha256'])
        self.assertEqual(build['toolchain']['identity_sha256'], self.identity)
        self.assertEqual(recipe['toolchain']['paired_sdk_sha256'], None)
        self.assertEqual(recipe['toolchain']['runtime_policy'], 'private-native')
        self.assertFalse(result['source_proof_admitted'])
        manifest.recipe_contract(recipe)
        manifest.source_contract(sources, recipe, result['recipe_sha256'])

    def test_input_bytes_identity_change_rebinds_r_s_b_without_mutating_inputs(self):
        original = copy.deepcopy(self.records)
        first = self.compose()
        changed = copy.deepcopy(self.records)
        changed['supplier/engine.txt']['sha256'] = pin(b'changed retained source')
        second = self.compose(changed)
        for role in ('recipe_sha256', 'sources_sha256', 'provider_build_sha256'):
            self.assertNotEqual(first[role], second[role])
        self.assertEqual(self.records, original)

    def test_identity_original_config_role_mode_and_presence_are_required(self):
        for change in ('omit', 'role', 'mode', 'pin'):
            values = copy.deepcopy(self.records)
            if change == 'omit': del values[prepare.IDENTITY_PATH]
            elif change == 'role': values[prepare.IDENTITY_PATH]['role'] = 'data'
            elif change == 'mode': values[prepare.IDENTITY_PATH]['mode'] = 0o755
            else: values[prepare.IDENTITY_PATH]['sha256'] = pin(b'foreign identity')
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'identity'):
                self.compose(values)

    def test_generated_outputs_and_self_identity_are_not_recipe_inputs(self):
        for name in ('recipe.json', 'sources.json', 'metadata/provider-build.json',
                     'generated/' + handoff.HEADER):
            values = copy.deepcopy(self.records)
            values[name] = {'sha256': pin(name.encode()), 'role': 'config', 'mode': 0o644}
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'may not retain'):
                self.compose(values)

    def test_bad_modes_and_portable_path_aliases_are_rejected(self):
        for name in ('NUL.txt', 'source/../file', 'source/a:stream', 'source/CON/file'):
            values = copy.deepcopy(self.records)
            values[name] = {'sha256': pin(name.encode()), 'role': 'source', 'mode': 0o644}
            with self.subTest(name=name), self.assertRaises(ValueError): self.compose(values)
        values = copy.deepcopy(self.records)
        values['supplier/engine.txt']['mode'] = True
        with self.assertRaises(ValueError): self.compose(values)

    def test_malformed_records_fail_as_validation_errors(self):
        for value in (None, [], {'sha256': 'bad', 'role': 'source', 'mode': 0o644}):
            records = copy.deepcopy(self.records)
            records['supplier/engine.txt'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.compose(records)


class PosixWriterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='windows-prepare-inert-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def output(self, name='output'):
        output = prepare._PosixOutput(self.root / name)
        self.addCleanup(output.close)
        return output

    def test_owned_new_files_normalize_modes_and_copy_independent_inodes(self):
        source = self.root / 'synthetic-input.txt'
        source.write_bytes(b'inert fixture bytes')
        output = self.output()
        first = output.save('metadata/test.json', b'{}\n')
        second = output.copy('retained/source.txt', source, pin(source.read_bytes()))
        self.assertEqual(Path(first['path']).read_bytes(), b'{}\n')
        self.assertEqual(Path(second['path']).read_bytes(), source.read_bytes())
        self.assertNotEqual(Path(second['path']).stat().st_ino, source.stat().st_ino)
        self.assertEqual(Path(second['path']).stat().st_nlink, 1)
        self.assertEqual(stat.S_IMODE(output.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((output.root / 'metadata').stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(Path(first['path']).stat().st_mode), 0o644)
        output.recheck()

    def test_existing_root_or_file_is_never_replaced(self):
        output = self.output()
        output.save('sentinel', b'original')
        with self.assertRaises((ValueError, FileExistsError)): output.save('sentinel', b'replacement')
        self.assertEqual((output.root / 'sentinel').read_bytes(), b'original')
        with self.assertRaises(FileExistsError): prepare._PosixOutput(output.root)

    def test_source_link_hardlink_wrong_pin_and_byte_bound_fail_closed(self):
        source = self.root / 'original.txt'
        source.write_bytes(b'inert fixture')
        link = self.root / 'alias.txt'
        link.symlink_to(source)
        with self.assertRaises((ValueError, OSError)): self.output('symlink-output').copy('symlink', link, pin(b'inert fixture'))
        link.unlink()
        os.link(source, link)
        with self.assertRaisesRegex(ValueError, 'singly linked'): self.output('hardlink-output').copy('hardlink', source, pin(b'inert fixture'))
        link.unlink()
        with self.assertRaisesRegex(ValueError, 'independent pin'): self.output('wrong-output').copy('wrong', source, pin(b'wrong'))
        output = self.output('byte-output')
        output.maximum_bytes = 1
        with self.assertRaisesRegex(ValueError, 'bound'): output.save('large', b'longer')

    def test_changed_owned_output_and_path_replacement_are_detected(self):
        output = self.output()
        output.save('owned', b'original')
        (output.root / 'owned').write_bytes(b'foreign change')
        with self.assertRaisesRegex(ValueError, 'changed'): output.recheck()
        output.root.rename(self.root / 'moved-output')
        output.root.mkdir()
        with self.assertRaisesRegex(ValueError, 'identity changed'): output.save('another', b'x')

    def test_output_traversal_and_symlink_parent_are_rejected(self):
        output = self.output()
        with self.assertRaises(ValueError): output.save('../outside', b'x')
        output = self.output('symlink-output')
        (output.root / 'linked').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises((ValueError, OSError)): output.save('linked/outside', b'x')
        self.assertFalse((self.root / 'outside').exists())

    def test_case_alias_and_foreign_plain_directory_are_not_acquired(self):
        output = self.output()
        output.save('Case/first', b'a')
        with self.assertRaisesRegex(ValueError, 'case-insensitive'):
            output.save('case/second', b'b')
        output = self.output('foreign-output')
        foreign = output.root / 'foreign'
        foreign.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, 'unowned'):
            output.save('foreign/child', b'x')
        self.assertEqual(stat.S_IMODE(foreign.stat().st_mode), 0o700)
        self.assertFalse((foreign / 'child').exists())

    def test_failed_copy_or_write_preserves_evidence_and_poisoned_completion(self):
        source = self.root / 'source'
        source.write_bytes(b'inert retained bytes')
        output = self.output('failed-copy')
        with self.assertRaisesRegex(ValueError, 'independent pin'):
            output.copy('failed', source, pin(b'foreign'))
        self.assertTrue((output.root / 'failed').exists())
        for operation in (output.recheck, lambda: output.save('more', b'x')):
            with self.assertRaisesRegex(ValueError, 'has failed'):
                operation()
        partial = self.output('failed-write')
        with mock.patch.object(prepare.os, 'write', side_effect=OSError('inert interrupted write')):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                partial.save('partial', b'bytes')
        with self.assertRaisesRegex(ValueError, 'has failed'):
            partial.recheck()

    def test_renamed_root_cannot_delete_the_original_owned_file(self):
        output = self.output()
        output.save('owned', b'keep original')
        moved = self.root / 'moved'
        output.root.rename(moved)
        output.root.mkdir()
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            output.remove_owned('owned')
        self.assertEqual((moved / 'owned').read_bytes(), b'keep original')


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='windows-metadata-controller-inert-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.limits = {'generator_seconds': 10, 'maximum_log_bytes': 1024, 'cleanup_seconds': 2}

    def test_arguments_select_exact_retained_generator_and_original_output_path(self):
        root, generated = self.root / 'retained', self.root / 'stable-generated'
        argv = prepare._generator_arguments(root, reference(root / 'recipe.json'),
            reference(root / 'sources.json'), reference(self.root / 'provider-build.json'),
            generated, reference(self.root / 'python'))
        self.assertEqual(argv[:5], [str(self.root / 'python'), '-I', '-S', '-B', str(root / handoff.GENERATOR)])
        self.assertEqual(argv[-2:], ['--output-root', str(generated)])
        with self.assertRaisesRegex(ValueError, 'overlap'):
            prepare._generator_arguments(root, reference(root / 'recipe.json'),
                reference(root / 'sources.json'), reference(root / 'provider-build.json'),
                generated, reference(self.root / 'python'))

    def test_runtime_is_named_missing_and_no_program_is_launched(self):
        with mock.patch.object(prepare, 'RUNTIME_SEAM_SHA256', None), \
                mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('launch')):
            with self.assertRaises(prepare.MissingInputs) as context:
                prepare._controller_runtime_admission(reference(self.root / 'runtime.json'), b'{}')
        self.assertEqual(context.exception.missing[0]['role'], 'posix-metadata-controller-runtime-admission')

    def test_released_runtime_source_identity_matches_actual_shared_api_and_foreign_pin_rejects(self):
        # Maintained Python source identity only; no retained runtime body or
        # InputSet capture is needed to release this shared implementation seam.
        self.assertEqual(prepare.CONTRACT_SHA256, pin(Path(contract.__file__).read_bytes()))
        actual = pin(Path(prepare.native_source.__file__).read_bytes())
        self.assertEqual(prepare.RUNTIME_SEAM_SHA256, actual)
        with mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('source pin launched a program')), \
                mock.patch.object(prepare.native_source, 'InputSet', side_effect=AssertionError('source pin captured a runtime')):
            self.assertIs(prepare._runtime_api(), prepare.native_source)
            with mock.patch.object(prepare, 'RUNTIME_SEAM_SHA256', pin(b'foreign shared source')):
                with self.assertRaisesRegex(ValueError, 'source identity differs'):
                    prepare._runtime_api()

    def test_resource_adapter_is_named_missing_and_no_program_is_launched(self):
        with mock.patch.object(prepare, 'PROCESS_TREE_SEAM_SHA256', None), \
                mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('launch')):
            with self.assertRaises(prepare.MissingInputs) as context:
                prepare._controller_resource_admission(reference(self.root / 'runtime.json'), b'{}')
        self.assertEqual(context.exception.missing[0]['role'], 'posix-metadata-controller-resource-adapter')

    def test_wiring_only_private_controller_callbacks_recheck_and_copy_limits(self):
        controller, resources = mock.Mock(), mock.Mock()
        controller.environment.return_value = {'INERT_CONTROLLER_FIXTURE': '1'}
        original = copy.deepcopy(self.limits)
        def run(argv, cwd, log, environment, limits):
            limits['generator_seconds'] = 1
            return {'inert_wiring_result': 'closed resource callback'}
        resources.run.side_effect = run
        argv, log = ['inert-not-executed'], self.root / 'never-created-log'
        temporary_root = self.root / 'never-created-temporary'
        with mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('program launch')):
            result = prepare._run_admitted_controller(controller, resources, argv, self.root, log,
                self.limits, temporary_root=temporary_root)
        self.assertEqual(result, {'inert_wiring_result': 'closed resource callback'})
        self.assertEqual(controller.mock_calls, [mock.call.recheck(),
            mock.call.environment(temporary_root), mock.call.recheck()])
        resources.run.assert_called_once()
        self.assertEqual(resources.run.call_args.args[:4], (argv, self.root, log, {'INERT_CONTROLLER_FIXTURE': '1'}))
        self.assertEqual(self.limits, original)
        self.assertFalse(log.exists())

    def test_mocked_parent_success_needs_owner_finish_close_and_remains_unadmitted(self):
        owner = mock.Mock()
        owner.poll.return_value = 0
        owner.finish.return_value = 0
        with mock.patch.object(prepare.process_tree, 'launch', return_value=owner):
            result = prepare._run_controller(['inert-not-executed'], self.root,
                self.root / 'log', {}, self.limits)
        owner.finish.assert_called_once()
        owner.close.assert_called_once()
        self.assertTrue(result['process_owner_closed'])
        self.assertFalse(result['controller_admitted'])
        self.assertFalse(result['resource_limits_complete'])

    def test_mocked_finish_failure_and_uncertain_cleanup_never_succeed(self):
        owner = mock.Mock()
        owner.poll.return_value = 0
        owner.finish.side_effect = prepare.process_tree.ProcessTreeError('descendants alive')
        with mock.patch.object(prepare.process_tree, 'launch', return_value=owner):
            with self.assertRaisesRegex(prepare.process_tree.ProcessTreeError, 'descendants'):
                prepare._run_controller(['inert-not-executed'], self.root, self.root / 'failed-log', {}, self.limits)
        owner.terminate.assert_called_once_with(timeout=2)
        uncertain = mock.Mock()
        uncertain.poll.return_value = 0
        uncertain.finish.side_effect = ValueError('original failure')
        uncertain.terminate.side_effect = RuntimeError('cleanup failed')
        before = len(prepare._UNCERTAIN)
        with mock.patch.object(prepare.process_tree, 'launch', return_value=uncertain):
            with self.assertRaisesRegex(prepare.process_tree.ProcessTreeError, 'uncertain'):
                prepare._run_controller(['inert-not-executed'], self.root, self.root / 'uncertain-log', {}, self.limits)
        self.assertEqual(len(prepare._UNCERTAIN), before + 1)
        prepare._UNCERTAIN.pop()

    def test_wall_bound_includes_owner_close_and_closed_log_context(self):
        owner, now = mock.Mock(), [0]
        owner.poll.return_value = 0
        owner.finish.return_value = 0
        def late_close():
            now[0] = self.limits['generator_seconds'] + 1
        owner.close.side_effect = late_close
        log = self.root / 'closed-late-log'
        with mock.patch.object(prepare.process_tree, 'launch', return_value=owner) as launch, \
                mock.patch.object(prepare.time, 'monotonic', side_effect=lambda: now[0]):
            with self.assertRaisesRegex(ValueError, 'closure exceeded'):
                prepare._run_controller(['inert-not-executed'], self.root, log, {}, self.limits)
        owner.finish.assert_called_once()
        owner.close.assert_called_once()
        owner.terminate.assert_not_called()
        self.assertTrue(launch.call_args.args[2].closed)
        with log.open('ab') as stream:
            stream.write(b'inert failure evidence\n')

    def test_public_operations_reject_caller_ready_flags_and_have_no_output(self):
        forged = {'metadata_ready': True, 'source_proof_admitted': True, 'controller_admitted': True}
        with mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('launch')):
            for operation, arguments in ((prepare.prepare_sources, (forged, self.root / 'output')),
                    (prepare.generate_metadata, (forged, forged)), (prepare.handoff_selection, (forged,))):
                with self.subTest(operation=operation.__name__), self.assertRaises(prepare.MissingInputs):
                    operation(*arguments)
        self.assertFalse((self.root / 'output').exists())

    def test_cli_validation_is_one_missing_input_is_two(self):
        selection = self.root / 'selection.json'
        selection.write_bytes(b'{}')
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(prepare.cli(['check', '--selection', str(selection), '--selection-sha256', pin(b'wrong')]), 1)
        missing = prepare._missing('native-original-source-proof-data-seam', 'shared-source', 'not released')
        with mock.patch.object(prepare, 'inspect_prepare', side_effect=missing), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(prepare.cli(['prepare', '--selection', str(selection), '--selection-sha256', pin(b'{}'), '--output', str(self.root / 'output')]), 2)
        self.assertEqual(json.loads(output.getvalue())['missing'][0]['role'], 'native-original-source-proof-data-seam')


class _InertRuntimeCapture:
    """Tiny lower capture views; never reads a real retained runtime or source."""
    def __init__(self, fixture):
        self.fixture, self.deadline = fixture, None
        self.file_calls, self.inventory_calls, self.document_calls = [], [], []
        self.rechecks = 0
        self.protected_paths = {fixture.root}

    def file(self, path, digest, label, maximum=None):
        self.file_calls.append((Path(path), digest, label, maximum))
        return {'path': str(path), 'sha256': digest}

    def bytes(self, path):
        if Path(path) != self.fixture.path:
            raise AssertionError('unexpected lower captured body')
        return self.fixture.captured_raw

    def inventory(self, record, base, label):
        self.inventory_calls.append((copy.deepcopy(record), Path(base), label))
        return copy.deepcopy(self.fixture.inventory)

    def document(self, reference, base, label):
        self.document_calls.append((copy.deepcopy(reference), Path(base), label))
        return copy.deepcopy(self.fixture.facts)

    def recheck(self):
        self.rechecks += 1
        if self.fixture.capture_failure:
            raise ValueError('inert runtime capture changed')


class _InertRuntimeFixture:
    """Explicit mocked lower admission, not actual retained-runtime evidence."""
    def __init__(self, root):
        self.root = root / 'runtime'
        self.root.mkdir()
        (self.root / 'lib').mkdir(mode=0o755)
        self.python = self.root / 'python'
        self.python.write_bytes(b'inert interpreter identity, never executed\n')
        self.python.chmod(0o755)
        self.path = root / 'controller-runtime.json'
        self.wrapper = {'schema_version': 1, 'kind': 'foundation-posix-metadata-python-runtime-v1',
            'python': {'path': str(self.python), 'sha256': pin(self.python.read_bytes()), 'version': '3.12.1'},
            'inventories': {'python': {'root': str(self.root),
                'inventory': {'path': str(root / 'runtime-inventory.json'), 'sha256': pin(b'inert inventory')}}},
            'runtime_facts': {'path': str(root / 'runtime-facts.json'), 'sha256': pin(b'inert facts')},
            'supervisor': {'path': str(Path(prepare.process_tree.__file__).resolve()),
                'sha256': pin(b'inert supervisor source capture')}}
        self.raw = prepare.encoded(self.wrapper)
        self.path.write_bytes(self.raw)
        self.reference = {'path': str(self.path), 'sha256': pin(self.raw)}
        self.captured_raw, self.capture_failure = self.raw, False
        self.facts = {'schema_version': 1, 'kind': 'foundation-native-host-interpreter-runtime-v1',
            'program_sha256': self.wrapper['python']['sha256'], 'search_paths': [str(self.root)],
            'runtime_inventories': ['python']}
        self.inventory = {'root': str(self.root), 'inventory': {},
            'files': {'python': self.wrapper['python']['sha256']}, 'directories': ['lib'],
            'modes': {'python': 0o755, 'lib': 0o755}}
        self.capture = _InertRuntimeCapture(self)
        self.api = SimpleNamespace(InputSet=lambda: self.capture,
            _program=mock.Mock(side_effect=lambda program, *args: copy.deepcopy(program)),
            _version=mock.Mock(), _interpreter_runtime_facts=mock.Mock(
                side_effect=lambda facts, *args, **kwargs: copy.deepcopy(facts)))
        self.observation = {'path': str(self.python), 'version': (3, 12, 1),
            'implementation': 'cpython', 'prefix': str(self.root), 'base_prefix': str(self.root)}


class _ControllerWiringTestCase(unittest.TestCase):
    """Actual private issuance with explicit inert lower capture/observation seams."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='windows-controller-runtime-wiring-inert-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = _InertRuntimeFixture(self.root)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(prepare, '_runtime_api', return_value=self.fixture.api))
        self.observe = self.stack.enter_context(mock.patch.object(prepare, '_observe_current_python',
            side_effect=lambda: copy.deepcopy(self.fixture.observation)))
        self.stack.enter_context(mock.patch.object(prepare, '_require_clean_controller_environment'))
        self.launch = self.stack.enter_context(mock.patch.object(prepare.process_tree, 'launch',
            side_effect=AssertionError('runtime fixture must never execute a program')))

    def admit(self, **keywords):
        runtime = prepare._controller_runtime_admission(self.fixture.reference, self.fixture.raw, **keywords)
        self.addCleanup(runtime.close)
        return runtime


class ControllerRuntimeWiringOnlyTests(_ControllerWiringTestCase):
    def test_wiring_only_factory_captures_original_bytes_and_returns_defensive_runtime_views(self):
        runtime = self.admit()
        expected = {key: self.fixture.wrapper['python'][key] for key in ('path', 'sha256')}
        selected = runtime.python_reference()
        self.assertEqual(selected, expected)
        selected['sha256'] = pin(b'caller changed returned runtime reference')
        self.assertEqual(runtime.python_reference(), expected)
        self.assertEqual(self.fixture.capture.file_calls[0][:3],
            (self.fixture.path, self.fixture.reference['sha256'], 'metadata-controller-wrapper'))
        self.assertEqual(self.fixture.capture.inventory_calls[0][2], 'metadata-python-python')
        self.fixture.api._program.assert_called_once()
        self.fixture.api._version.assert_called_once_with('3.12.1', (3, 9, 0), 'Python')
        self.fixture.api._interpreter_runtime_facts.assert_called_once()
        self.assertIs(self.fixture.api._interpreter_runtime_facts.call_args.kwargs['external'], True)
        runtime.recheck()
        self.assertGreaterEqual(self.observe.call_count, 2)
        self.assertGreaterEqual(self.fixture.capture.rechecks, 1)
        self.launch.assert_not_called()

    def test_wiring_only_environment_is_closed_and_returned_values_cannot_change_it(self):
        runtime = self.admit()
        workspace = self.root / 'private-temporary'
        workspace.mkdir(mode=0o700)
        with mock.patch.dict(os.environ, {'UNRELATED_AMBIENT_VARIABLE': 'must not inherit',
                'HOME': '/caller-home', 'PYTHONPATH': '/caller-python', 'PYTHONSTARTUP': '/caller-startup'}):
            first = runtime.environment(workspace)
            second = runtime.environment(workspace)
        self.assertEqual(first, second)
        for name in ('UNRELATED_AMBIENT_VARIABLE', 'HOME', 'PYTHONPATH', 'PYTHONSTARTUP',
                     'LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT'):
            self.assertNotIn(name, first)
        first['UNRELATED_AMBIENT_VARIABLE'] = 'caller mutation'
        self.assertNotIn('UNRELATED_AMBIENT_VARIABLE', runtime.environment(workspace))
        self.launch.assert_not_called()

    def test_wiring_only_wrapper_raw_must_equal_original_captured_bytes(self):
        self.fixture.captured_raw = self.fixture.raw + b' '
        with self.assertRaisesRegex(ValueError, 'capture|original|bytes|changed|differ'):
            self.admit()
        self.fixture.api._program.assert_not_called()
        self.launch.assert_not_called()

    def test_wiring_only_current_observation_mismatch_rejects_before_runtime_issuance(self):
        for field, value in (('path', str(self.root / 'foreign-python')),
                ('version', (3, 12, 2)),
                ('prefix', str(self.root / 'outside-prefix')), ('base_prefix', str(self.root / 'outside-base'))):
            with self.subTest(field=field):
                old = self.fixture.observation[field]
                self.fixture.observation[field] = value
                try:
                    with self.assertRaises(ValueError):
                        self.admit()
                finally:
                    self.fixture.observation[field] = old
        self.launch.assert_not_called()

    def test_wiring_only_recheck_reobserves_current_program_and_original_capture(self):
        runtime = self.admit()
        self.fixture.observation['path'] = str(self.root / 'replaced-current-python')
        with self.assertRaises(ValueError):
            runtime.recheck()
        self.launch.assert_not_called()
        runtime.close()
        with self.assertRaises(prepare.MissingInputs):
            runtime.python_reference()

    def test_wiring_only_static_isolated_layout_requires_original_captured_search_directories(self):
        runtime = self.admit()
        self.assertIsNone(prepare._isolated_startup_admission(prepare._runtime(runtime)))
        for path in (self.fixture.python, self.root / 'unknown-search-root'):
            with self.subTest(path=path):
                self.fixture.facts['search_paths'] = [str(path)]
                changed = self.admit()
                before = len(prepare._RESOURCES)
                with mock.patch.object(prepare, '_process_api', return_value=prepare.process_tree):
                    with self.assertRaisesRegex(ValueError, 'captured directories'):
                        prepare._controller_resource_admission(self.fixture.reference, self.fixture.raw,
                            controller=changed)
                self.assertEqual(len(prepare._RESOURCES), before)
        self.launch.assert_not_called()

    def test_wiring_only_current_implementation_is_frozen_across_runtime_lifetime(self):
        runtime = self.admit()
        self.fixture.observation['implementation'] = 'changed-after-original-observation'
        with self.assertRaisesRegex(ValueError, 'changed'):
            runtime.recheck()
        self.launch.assert_not_called()

    def test_wiring_only_original_runtime_mutation_cannot_be_rechecked_as_ready(self):
        runtime = self.admit()
        self.fixture.capture_failure = True
        with self.assertRaisesRegex(ValueError, 'capture changed'):
            runtime.recheck()
        self.launch.assert_not_called()
        runtime.close()
        with self.assertRaises(prepare.MissingInputs):
            runtime.environment(self.root)

    def test_wiring_only_outer_deadline_is_not_extended_by_runtime_recheck(self):
        now = [0]
        with mock.patch.object(prepare.time, 'monotonic', side_effect=lambda: now[0]):
            runtime = self.admit(deadline=2)
            now[0] = 3
            with self.assertRaisesRegex(ValueError, 'deadline|wall|budget'):
                runtime.recheck()
        self.launch.assert_not_called()


class InspectionAdmissionCleanupWiringOnlyTests(_ControllerWiringTestCase):
    """Public inspection cleanup with actual issued inert lower admission handles."""
    def setUp(self):
        super().setUp()
        self.runtime_handles, self.resource_handles = [], []
        self.addCleanup(self.cleanup_admissions)
        selected = {'repository_root': str(self.root / 'repository'),
            'phase_limits': {'prepare_seconds': 10},
            **{role: reference(self.root / (role + '.json')) for role in prepare.METADATA_REFS}}
        selected['metadata_controller_runtime'] = copy.deepcopy(self.fixture.reference)
        self.selection = prepare.encoded(selected)
        self.stack.enter_context(mock.patch.object(prepare, 'validate_selection', return_value=selected))
        def metadata(reference, role, **keywords):
            if role == 'windows-source-preparation-selection':
                return self.selection, None
            if role == 'metadata_controller_runtime':
                return self.fixture.raw, copy.deepcopy(self.fixture.wrapper)
            if role in prepare.METADATA_REFS or role.startswith('current-source-'):
                return b'{}\n', {}
            raise AssertionError('unexpected inspection metadata capture')
        self.stack.enter_context(mock.patch.object(prepare, '_metadata', side_effect=metadata))
        contract_body = b'inert source-contract observation'
        self.stack.enter_context(mock.patch.object(prepare, 'CONTRACT_SHA256', pin(contract_body)))
        def source_contract(path, **keywords):
            if Path(path) != Path(contract.__file__).absolute():
                raise AssertionError('inspection fixture attempted an unexpected physical body capture')
            return contract_body
        self.stack.enter_context(mock.patch.object(handoff, '_read', side_effect=source_contract))
        self.stack.enter_context(mock.patch.object(contract, 'validate_inputs'))
        replay = SimpleNamespace(validate_projection_metadata=mock.Mock(),
            catalogue_metadata=mock.Mock(return_value={}), require_original_proof_seam=mock.Mock())
        self.stack.enter_context(mock.patch.object(prepare, '_replay', return_value=replay))
        proof = SimpleNamespace(validate_source_declarations=mock.Mock())
        self.stack.enter_context(mock.patch.dict(sys.modules,
            {'appended_engine_windows_dependency_proof': proof}))
        self.stack.enter_context(mock.patch.object(prepare, '_process_api', return_value=prepare.process_tree))
        actual_runtime, actual_resources = prepare._controller_runtime_admission, prepare._controller_resource_admission
        def runtime(*arguments, **keywords):
            handle = actual_runtime(*arguments, **keywords)
            self.runtime_handles.append(handle)
            return handle
        def resources(*arguments, **keywords):
            handle = actual_resources(*arguments, **keywords)
            self.resource_handles.append(handle)
            return handle
        self.stack.enter_context(mock.patch.object(prepare, '_controller_runtime_admission', side_effect=runtime))
        self.stack.enter_context(mock.patch.object(prepare, '_controller_resource_admission', side_effect=resources))
        self.output = self.stack.enter_context(mock.patch.object(prepare, '_PosixOutput',
            side_effect=AssertionError('inspection admission failure created output')))

    def cleanup_admissions(self):
        # These fixtures never bind or launch a writer. Remove their injected
        # uncertainty only after the temporary close-failure patch has ended.
        for resource in reversed(self.resource_handles):
            resource.close()
        for runtime in reversed(self.runtime_handles):
            runtime.close()
        prepare._UNCERTAIN[:] = [item for item in prepare._UNCERTAIN if not (
            type(item) is tuple and len(item) == 2 and
            any(item[0] is resource for resource in self.resource_handles) and
            any(item[1] is runtime for runtime in self.runtime_handles))]

    def inspect(self):
        return prepare.inspect_prepare(self.root / 'not-read-selection.json', pin(self.selection))

    def assert_revoked_without_writers(self):
        for runtime in self.runtime_handles:
            with self.assertRaises(prepare.MissingInputs):
                runtime.python_reference()
        for resource in self.resource_handles:
            with self.assertRaises(prepare.MissingInputs):
                prepare._resource(resource)
        self.output.assert_not_called()
        self.launch.assert_not_called()

    def test_wiring_only_resource_admission_error_revokes_already_issued_runtime(self):
        before = len(prepare._UNCERTAIN)
        with mock.patch.object(prepare, '_controller_resource_admission',
                side_effect=ValueError('inert resource admission rejected')):
            with self.assertRaisesRegex(ValueError, 'inert resource admission rejected'):
                self.inspect()
        self.assertEqual(len(self.runtime_handles), 1)
        self.assertEqual(self.resource_handles, [])
        self.assert_revoked_without_writers()
        self.assertEqual(len(prepare._UNCERTAIN), before)

    def test_wiring_only_owner_constructor_error_revokes_both_actual_admissions(self):
        before = len(prepare._UNCERTAIN)
        with mock.patch.object(prepare, '_PreparationOwner',
                side_effect=ValueError('inert owner construction rejected')):
            with self.assertRaisesRegex(ValueError, 'inert owner construction rejected'):
                self.inspect()
        self.assertEqual(len(self.runtime_handles), 1)
        self.assertEqual(len(self.resource_handles), 1)
        self.assert_revoked_without_writers()
        self.assertEqual(len(prepare._UNCERTAIN), before)

    def test_wiring_only_uncertain_admission_close_retains_actual_pair_and_dependent_runtime(self):
        before, runtime_closes = len(prepare._UNCERTAIN), []
        actual_close = prepare._ControllerRuntime.close
        def runtime_close(runtime):
            runtime_closes.append(runtime)
            actual_close(runtime)
        with mock.patch.object(prepare, '_PreparationOwner',
                side_effect=ValueError('inert owner construction rejected')), \
                mock.patch.object(prepare._MetadataResources, 'close',
                    side_effect=RuntimeError('inert resource close uncertain')), \
                mock.patch.object(prepare._ControllerRuntime, 'close', new=runtime_close):
            with self.assertRaisesRegex(prepare.process_tree.ProcessTreeError, 'cleanup uncertain') as context:
                self.inspect()
        self.assertIsInstance(context.exception.__cause__, RuntimeError)
        self.assertEqual(runtime_closes, [])
        self.assertEqual(len(self.runtime_handles), 1)
        self.assertEqual(len(self.resource_handles), 1)
        runtime, resource = self.runtime_handles[0], self.resource_handles[0]
        self.assertEqual(len(prepare._UNCERTAIN), before + 1)
        retained = prepare._UNCERTAIN[-1]
        self.assertIs(retained[0], resource)
        self.assertIs(retained[1], runtime)
        self.assertIs(prepare._resource(resource).runtime, runtime)
        self.assertTrue(runtime.python_reference())
        self.output.assert_not_called()
        self.launch.assert_not_called()


_SupervisorStartup = namedtuple('SupervisorStartup', ('pid', 'parent_pid', 'executable',
    'executable_realpath', 'version_info', 'implementation', 'prefix', 'base_prefix',
    'exec_prefix', 'base_exec_prefix', 'sys_path', 'platlibdir', 'flags', 'helper_path',
    'dont_write_bytecode'))


def inert_startup(fixture):
    """Implementation-owned lower observation mock, never caller admission data."""
    prefix = fixture.observation['prefix']
    return _SupervisorStartup(os.getpid() + 1000, os.getpid(), str(fixture.python),
        str(fixture.python.resolve()), (3, 12, 1), 'cpython', prefix, prefix,
        prefix, prefix, tuple(fixture.facts['search_paths']), 'lib',
        tuple((name, 1) for name in ('isolated', 'ignore_environment', 'no_user_site',
            'no_site', 'dont_write_bytecode')), fixture.wrapper['supervisor']['path'], True)


class SupervisorStartupWiringOnlyTests(_ControllerWiringTestCase):
    """Actual B validator over immutable implementation-owned lower observations."""
    def startup(self):
        runtime = self.admit()
        return prepare._runtime(runtime), inert_startup(self.fixture)

    def test_wiring_only_actual_validator_accepts_original_layout_without_minting_authority(self):
        runtime, observation = self.startup()
        self.assertIsNone(prepare._validate_supervisor_startup(runtime, observation))
        self.launch.assert_not_called()
        self.assertEqual(observation.sys_path, tuple(self.fixture.facts['search_paths']))

    def test_wiring_only_program_current_identity_flags_and_helper_mismatch_reject(self):
        runtime, observation = self.startup()
        bad = (('executable', str(self.root / 'foreign-python')),
            ('executable_realpath', str(self.root / 'foreign-python-realpath')),
            ('version_info', (3, 12, 2)), ('version_info', (True, 12, 1)),
            ('version_info', [3, 12, 1]), ('implementation', 'foreign-implementation'),
            ('helper_path', str(self.root / 'foreign-supervisor.py')), ('pid', True),
            ('pid', 0), ('parent_pid', os.getpid() + 1), ('parent_pid', True))
        for field, value in bad:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                prepare._validate_supervisor_startup(runtime, observation._replace(**{field: value}))
        self.launch.assert_not_called()

    def test_wiring_only_all_isolated_prefixes_require_original_captured_directories(self):
        runtime, observation = self.startup()
        for field in ('prefix', 'base_prefix', 'exec_prefix', 'base_exec_prefix'):
            for value in (str(self.root / 'outside-runtime'), str(self.fixture.python)):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    prepare._validate_supervisor_startup(runtime, observation._replace(**{field: value}))
        self.launch.assert_not_called()

    def test_wiring_only_isolation_flags_are_exact_immutable_int_pairs_and_true_bytecode_policy(self):
        runtime, observation = self.startup()
        flags = observation.flags
        bad_flags = (list(flags), tuple(list(pair) for pair in flags), flags[:-1],
            tuple(reversed(flags)), ((flags[0][0], True), *flags[1:]),
            (*flags, ('unknown_flag', 1)))
        for value in bad_flags:
            with self.subTest(flags=value), self.assertRaises(ValueError):
                prepare._validate_supervisor_startup(runtime, observation._replace(flags=value))
        for value in (False, 1, 'true'):
            with self.subTest(dont_write_bytecode=value), self.assertRaises(ValueError):
                prepare._validate_supervisor_startup(runtime, observation._replace(dont_write_bytecode=value))
        self.launch.assert_not_called()

    def test_wiring_only_search_paths_reject_mutability_aliases_duplicates_files_and_unknown_roots(self):
        runtime, observation = self.startup()
        original = observation.sys_path[0]
        bad = ((), [original], (original, original), ('relative-search',),
            (str(self.root / 'foreign-search'),), (str(self.fixture.root / 'unknown'),),
            (str(self.fixture.python),), (original + '/',))
        for value in bad:
            with self.subTest(paths=value), self.assertRaises(ValueError):
                prepare._validate_supervisor_startup(runtime, observation._replace(sys_path=value))
        for value in ('lib/nested', '../lib', 'NUL', ''):
            with self.subTest(platlibdir=value), self.assertRaises(ValueError):
                prepare._validate_supervisor_startup(runtime, observation._replace(platlibdir=value))
        self.launch.assert_not_called()

    def test_wiring_only_actual_search_directories_must_equal_complete_original_facts(self):
        self.fixture.facts['search_paths'] = sorted((str(self.fixture.root), str(self.fixture.root / 'lib')))
        runtime, observation = self.startup()
        self.assertIsNone(prepare._validate_supervisor_startup(runtime, observation))
        with self.assertRaisesRegex(ValueError, 'differ from original'):
            prepare._validate_supervisor_startup(runtime,
                observation._replace(sys_path=(str(self.fixture.root),)))
        self.launch.assert_not_called()

    def test_wiring_only_standard_zip_candidate_uses_original_pinned_or_proven_absent_inventory(self):
        for retained in (False, True):
            with self.subTest(retained=retained):
                if retained:
                    self.fixture.inventory['files']['lib/python312.zip'] = pin(b'inert retained zip identity')
                    self.fixture.inventory['modes']['lib/python312.zip'] = 0o644
                runtime, observation = self.startup()
                path = str(self.fixture.root / 'lib/python312.zip')
                observation = observation._replace(sys_path=(path, *observation.sys_path))
                with mock.patch.object(prepare.os, 'stat', side_effect=AssertionError('startup must use captured inventory')):
                    self.assertIsNone(prepare._validate_supervisor_startup(runtime, observation))
        self.launch.assert_not_called()

    def test_wiring_only_unadmitted_zip_parent_foreign_name_and_layout_do_not_supply_search_authority(self):
        runtime, observation = self.startup()
        bad = (self.fixture.root / 'lib/python311.zip', self.fixture.root / 'unknown/python312.zip',
            self.fixture.root / 'python312.zip', self.root / 'lib/python312.zip')
        for path in bad:
            with self.subTest(path=path), self.assertRaises(ValueError):
                prepare._validate_supervisor_startup(runtime,
                    observation._replace(sys_path=(str(path), *observation.sys_path)))
        self.fixture.inventory['directories'] = []
        changed, observation = self.startup()
        with self.assertRaises(ValueError):
            prepare._validate_supervisor_startup(changed,
                observation._replace(sys_path=(str(self.fixture.root / 'lib/python312.zip'), *observation.sys_path)))
        self.launch.assert_not_called()


_ObservedProcessSample = namedtuple('ObservedProcessSample', ('records', 'complete', 'unknown_coverage'))


class ControllerResourcesWiringOnlyTests(_ControllerWiringTestCase):
    """Actual issued/bound owners; every process and startup observation is mocked."""
    def setUp(self):
        super().setUp()
        self.events, self.bound_values = [], []
        self.new_process()
        self.launch_hook = lambda stream: None
        def launch(*arguments, **keywords):
            self.events.append('launch')
            self.process_state['stream'] = arguments[2]
            return self.process
        self.launch.side_effect = launch
        self.stack.enter_context(mock.patch.object(prepare, '_process_api', return_value=prepare.process_tree))
        self.real_startup_validator = prepare._validate_supervisor_startup
        self.startup_validator = self.stack.enter_context(mock.patch.object(prepare,
            '_validate_supervisor_startup', side_effect=lambda *args: self.events.append('validate')))
        self.real_workspace_owner = prepare._workspace_owner
        self.workspace_owner = self.stack.enter_context(mock.patch.object(prepare, '_workspace_owner'))
        self.limits = {'prepare_seconds': 100, 'generator_seconds': 10, 'cleanup_seconds': 2,
            'maximum_processes': 2, 'maximum_output_bytes': 4096, 'maximum_log_bytes': 1024}

    def new_process(self):
        self.process = mock.Mock()
        self.process.poll.return_value = 0
        self.process_state = {'finished': False, 'released': False}
        self.startup_observation = inert_startup(self.fixture)
        def observe(**kwargs):
            self.events.append('observe')
            return self.startup_observation
        def release(observation):
            if observation is not self.startup_observation or self.process_state['released']:
                raise prepare.process_tree.ProcessTreeError('inert foreign or reused startup observation')
            self.events.append('release')
            self.process_state['released'] = True
            self.launch_hook(self.process_state['stream'])
        def poll():
            if not self.process_state['released']:
                raise AssertionError('target polled before startup GO')
            return self.process.poll.return_value
        self.process.observe_supervisor_startup.side_effect = observe
        self.process.release_supervisor_startup.side_effect = release
        self.process.poll.side_effect = poll
        self.process.finish.side_effect = self.finish_process
        def sample(**kwargs):
            self.events.append('sample')
            completed = self.process_state['finished']
            return _ObservedProcessSample((), completed, not completed)
        self.process.sample_processes.side_effect = sample
        self.process.close.side_effect = lambda: self.events.append('close')
        self.process.terminate.side_effect = lambda **kwargs: self.events.append('terminate')

    def finish_process(self, code=0):
        if not self.process_state['released']:
            raise AssertionError('target finished before startup GO')
        self.events.append('finish')
        self.process_state['finished'] = True
        return code

    def bind(self, *, limits=None):
        if self.bound_values:
            self.new_process()
        output = prepare._PosixOutput(self.root / ('output-' + str(len(self.bound_values))))
        self.addCleanup(output.close)
        selected = {role: output.save(name, b'{}') for role, name in (
            ('recipe', 'retained/recipe.json'), ('sources', 'retained/sources.json'),
            ('provider_build', 'metadata/provider-build.json'))}
        generated = output.private_directory('generated')
        temporary = output.private_directory('temporary')
        log = output.reserve_log('controller/generator.log')
        preparation = SimpleNamespace(retained_root=output.root / 'retained', references=selected)
        self.workspace_owner.return_value = preparation
        runtime = self.admit()
        resources = prepare._controller_resource_admission(self.fixture.reference, self.fixture.raw,
            controller=runtime)
        self.addCleanup(resources.close)
        limits = copy.deepcopy(self.limits if limits is None else limits)
        argv = prepare._generator_arguments(preparation.retained_root, selected['recipe'],
            selected['sources'], selected['provider_build'], generated, runtime.python_reference())
        bound = resources.for_workspace(output, generated_root=generated, temporary_root=temporary,
            protected_paths=(), argv=argv, limits=limits, deadline=prepare.time.monotonic() + 20)
        value = SimpleNamespace(output=output, runtime=runtime, resources=resources, bound=bound,
            generated=generated, temporary=temporary, log=log, preparation=preparation,
            argv=argv, limits=limits)
        self.bound_values.append(value)
        # Mocked process owners cannot be real writers. Clear only this fixture's
        # retained uncertainty after asserting it, before ordinary owner cleanup.
        self.addCleanup(self.cleanup_inert_uncertainty, bound)
        return value

    def cleanup_inert_uncertainty(self, token):
        owner = prepare._BOUND_RUNS.get(token)
        if owner is not None and owner in prepare._UNCERTAIN:
            if owner.stream is not None:
                owner.stream.close()
                owner.stream = None
            prepare._UNCERTAIN.remove(owner)
            owner.phase = 'failed'

    def write_header(self, value, raw):
        directory = value.generated if hasattr(value, 'generated') else value.generated_root
        path = directory / handoff.HEADER
        path.write_bytes(raw)
        path.chmod(0o644)

    def run_bound(self, value, **changes):
        arguments = {'argv': value.argv, 'cwd': value.preparation.retained_root, 'log': value.log,
            'environment': value.runtime.environment(value.temporary), 'limits': value.limits}
        arguments.update(changes)
        return value.bound.run(**arguments)

    def test_wiring_only_pending_owner_releases_original_observation_not_validator_returned_copy(self):
        value = self.bind()
        original = self.startup_observation
        copied = copy.deepcopy(original)
        self.assertIsNot(copied, original)
        def validate(runtime, observation):
            self.assertIs(observation, original)
            self.real_startup_validator(runtime, observation)
            return copied
        target = mock.Mock()
        self.launch_hook = target
        with mock.patch.object(prepare, '_validate_supervisor_startup', side_effect=validate):
            self.run_bound(value)
        self.process.observe_supervisor_startup.assert_called_once_with(
            deadline=prepare._BOUND_RUNS[value.bound].deadline)
        self.process.release_supervisor_startup.assert_called_once()
        self.assertIs(self.process.release_supervisor_startup.call_args.args[0], original)
        self.assertIsNot(self.process.release_supervisor_startup.call_args.args[0], copied)
        target.assert_called_once()
        self.assertTrue(self.process_state['released'])

    def test_wiring_only_bad_actual_startup_observation_blocks_go_and_closes_pending_owner(self):
        wrong = (('executable', str(self.root / 'foreign-python')), ('version_info', (3, 12, 2)),
            ('prefix', str(self.root / 'foreign-prefix')), ('sys_path', (str(self.root / 'foreign-search'),)),
            ('flags', ()), ('helper_path', str(self.root / 'foreign-supervisor.py')))
        for field, item in wrong:
            with self.subTest(field=field):
                value = self.bind()
                foreign = self.startup_observation._replace(**{field: item})
                self.process.observe_supervisor_startup.side_effect = lambda **kwargs: foreign
                target = mock.Mock()
                self.launch_hook = target
                with mock.patch.object(prepare, '_validate_supervisor_startup',
                        side_effect=self.real_startup_validator):
                    with self.assertRaises(ValueError):
                        self.run_bound(value)
                target.assert_not_called()
                self.process.release_supervisor_startup.assert_not_called()
                self.process.poll.assert_not_called()
                self.process.finish.assert_not_called()
                self.process.sample_processes.assert_not_called()
                self.process.terminate.assert_called_once_with(timeout=2)
                self.process.close.assert_called_once()
                self.assertFalse(self.process_state['released'])
                self.assertTrue(self.launch.call_args.args[2].closed)

    def test_wiring_only_observe_validate_or_foreign_go_refusal_joins_the_same_pending_owner(self):
        for stage in ('observe', 'validate', 'release'):
            with self.subTest(stage=stage):
                value = self.bind()
                target = mock.Mock()
                self.launch_hook = target
                self.startup_validator.reset_mock()
                self.startup_validator.side_effect = lambda *args: self.events.append('validate')
                if stage == 'observe':
                    self.process.observe_supervisor_startup.side_effect = prepare.process_tree.ProcessTreeError('inert observe failure')
                elif stage == 'validate':
                    self.startup_validator.side_effect = ValueError('inert validate failure')
                else:
                    self.process.release_supervisor_startup.side_effect = prepare.process_tree.ProcessTreeError('inert foreign observation refusal')
                with self.assertRaises((ValueError, prepare.process_tree.ProcessTreeError)):
                    self.run_bound(value)
                target.assert_not_called()
                if stage != 'release':
                    self.process.release_supervisor_startup.assert_not_called()
                if stage == 'observe':
                    self.startup_validator.assert_not_called()
                self.process.poll.assert_not_called()
                self.process.finish.assert_not_called()
                self.process.terminate.assert_called_once_with(timeout=2)
                self.process.close.assert_called_once()
                self.assertFalse(self.process_state['released'])
                self.assertTrue(self.launch.call_args.args[2].closed)

    def test_wiring_only_pending_owner_uncertain_cleanup_retains_original_stream_and_all_owners(self):
        value = self.bind()
        target = mock.Mock()
        self.launch_hook = target
        self.startup_validator.side_effect = ValueError('inert startup validation failure')
        self.process.terminate.side_effect = RuntimeError('inert pending cleanup uncertain')
        before = len(prepare._UNCERTAIN)
        with self.assertRaisesRegex(prepare.process_tree.ProcessTreeError, 'uncertain'):
            self.run_bound(value)
        target.assert_not_called()
        self.process.release_supervisor_startup.assert_not_called()
        self.process.poll.assert_not_called()
        self.process.finish.assert_not_called()
        self.process.terminate.assert_called_once_with(timeout=2)
        self.process.close.assert_not_called()
        owner = prepare._BOUND_RUNS[value.bound]
        self.assertEqual(len(prepare._UNCERTAIN), before + 1)
        self.assertIs(prepare._UNCERTAIN[-1], owner)
        self.assertIs(owner.owner, self.process)
        self.assertIs(owner.stream, self.launch.call_args.args[2])
        self.assertIs(owner.output, value.output)
        self.assertFalse(owner.stream.closed)
        for operation in (value.resources.close, value.runtime.close):
            with self.subTest(operation=operation), self.assertRaises(prepare.process_tree.ProcessTreeError):
                operation()

    def test_wiring_only_workspace_is_checked_before_go_without_pending_process_sampling(self):
        value = self.bind()
        target = mock.Mock()
        self.launch_hook = target
        def observe(**kwargs):
            (value.generated / 'unowned-before-go').write_bytes(b'inert unexpected bytes')
            return self.startup_observation
        self.process.observe_supervisor_startup.side_effect = observe
        with self.assertRaises(ValueError):
            self.run_bound(value)
        target.assert_not_called()
        self.process.release_supervisor_startup.assert_not_called()
        self.process.sample_processes.assert_not_called()
        self.process.poll.assert_not_called()
        self.process.finish.assert_not_called()
        self.process.terminate.assert_called_once_with(timeout=2)
        self.process.close.assert_called_once()

    def test_wiring_only_original_bound_deadline_still_applies_after_startup_before_go(self):
        now = [0]
        target = mock.Mock()
        with mock.patch.object(prepare.time, 'monotonic', side_effect=lambda: now[0]):
            value = self.bind()
            self.launch_hook = target
            def observe(**kwargs):
                now[0] = 11
                return self.startup_observation
            self.process.observe_supervisor_startup.side_effect = observe
            with self.assertRaisesRegex(ValueError, 'wall threshold'):
                self.run_bound(value)
        target.assert_not_called()
        self.process.release_supervisor_startup.assert_not_called()
        self.process.poll.assert_not_called()
        self.process.finish.assert_not_called()
        self.process.terminate.assert_called_once_with(timeout=2)
        self.process.close.assert_called_once()

    def preparation_owner(self):
        # Actual private owner/stage methods, with source capture and semantic
        # metadata join explicitly mocked. This cannot establish source proof.
        if self.bound_values:
            self.new_process()
        output = prepare._PosixOutput(self.root / ('preparation-' + str(len(self.bound_values))))
        self.addCleanup(output.close)
        references = {role: output.save(name, b'{}') for role, name in (
            ('recipe', 'retained/recipe.json'), ('sources', 'retained/sources.json'),
            ('provider_build', 'metadata/provider-build.json'))}
        runtime = self.admit()
        resources = prepare._controller_resource_admission(self.fixture.reference, self.fixture.raw,
            controller=runtime)
        self.addCleanup(resources.close)
        owner = prepare._PreparationOwner({'phase_limits': dict(self.limits)}, {}, {}, runtime, resources,
            deadline=prepare.time.monotonic() + 20)
        self.addCleanup(owner.close)
        owner.output, owner.references = output, references
        owner.retained_root, owner.assembled_root = output.root / 'retained', output.root / 'assembled'
        owner.capture = SimpleNamespace(_inputs={}, check=mock.Mock(), close=mock.Mock())
        prepare._OUTPUTS[output] = owner
        owner.phase = 'sources_ready'
        checked, sources = prepare._issue('checked', owner), prepare._issue('sources', owner)
        self.bound_values.append(owner)
        def output_bytes(stream):
            stream.write(b'{}\n')
            stream.flush()
            self.write_header(owner, b'inert generated header\n')
        self.launch_hook = output_bytes
        return owner, checked, sources

    def test_wiring_only_actual_preparation_keeps_runtime_resources_through_postflight_then_closes(self):
        owner, checked, sources = self.preparation_owner()
        observations = []
        def postflight():
            self.assertTrue(owner.controller.python_reference())
            self.assertIs(prepare._resource(owner.resources).runtime, owner.controller)
            self.assertFalse(owner.output.closed)
            owner.capture.close.assert_not_called()
            observations.append('postflight-live')
        with mock.patch.object(prepare, '_workspace_owner', side_effect=self.real_workspace_owner), \
                mock.patch.object(prepare, '_check_generated_metadata', return_value={'wiring_only': True}), \
                mock.patch.object(owner, 'scan_sources', side_effect=postflight):
            metadata = prepare.generate_metadata(checked, sources)
        self.assertEqual(observations, ['postflight-live'])
        self.assertEqual(owner.phase, 'metadata_ready')
        self.assertIn(metadata, prepare._PREPARATIONS)
        owner.close()
        self.assertTrue(owner.closed)
        self.assertTrue(owner.output.closed)
        owner.capture.close.assert_called_once()
        self.assertEqual(owner.tickets, set())
        for token in (checked, sources, metadata):
            self.assertNotIn(token, prepare._PREPARATIONS)
        with self.assertRaises(prepare.MissingInputs):
            owner.controller.python_reference()
        with self.assertRaises(prepare.MissingInputs):
            prepare._resource(owner.resources)

    def test_wiring_only_preparation_final_runtime_recheck_failure_still_closes_and_revokes(self):
        owner, checked, sources = self.preparation_owner()
        original_close = prepare._MetadataResources.close
        def close_then_change_runtime(resources):
            original_close(resources)
            if resources is owner.resources:
                self.fixture.capture_failure = True
        before = len(prepare._UNCERTAIN)
        try:
            with mock.patch.object(prepare._MetadataResources, 'close', new=close_then_change_runtime):
                with self.assertRaisesRegex(ValueError, 'capture changed'):
                    owner.close()
        finally:
            self.fixture.capture_failure = False
        self.assertTrue(owner.closed)
        self.assertTrue(owner.failed)
        self.assertTrue(owner.output.closed)
        owner.capture.close.assert_called_once()
        self.assertEqual(owner.tickets, set())
        self.assertNotIn(checked, prepare._PREPARATIONS)
        self.assertNotIn(sources, prepare._PREPARATIONS)
        self.assertEqual(len(prepare._UNCERTAIN), before)
        with self.assertRaises(prepare.MissingInputs):
            owner.controller.python_reference()
        with self.assertRaises(prepare.MissingInputs):
            prepare._resource(owner.resources)

    def test_wiring_only_preparation_runtime_overlap_and_parent_alias_reject_before_mkdir(self):
        runtime = self.admit()
        resources = prepare._controller_resource_admission(self.fixture.reference, self.fixture.raw,
            controller=runtime)
        self.addCleanup(resources.close)
        owner = prepare._PreparationOwner({'phase_limits': dict(self.limits)}, {}, {}, runtime, resources,
            deadline=prepare.time.monotonic() + 20)
        self.addCleanup(owner.close)
        owner.capture = SimpleNamespace(_inputs={}, check=mock.Mock(), close=mock.Mock())
        alias = self.root / 'runtime-alias'
        alias.symlink_to(self.fixture.root, target_is_directory=True)
        for destination in (self.fixture.root / 'forbidden-output', self.root):
            with self.subTest(destination=destination), \
                    mock.patch.object(prepare, '_PosixOutput', side_effect=AssertionError('mkdir before runtime overlap check')) as output:
                with self.assertRaises(ValueError):
                    owner.start(destination)
                output.assert_not_called()
        physical_parent = self.root / 'physical-parent'
        physical_parent.mkdir()
        original_stat, runtime_state = prepare.os.stat, self.fixture.root.stat()
        def stat_alias(path, *arguments, **keywords):
            if isinstance(path, (str, os.PathLike)) and Path(path) == physical_parent:
                return runtime_state
            return original_stat(path, *arguments, **keywords)
        with mock.patch.object(prepare.os, 'stat', side_effect=stat_alias), \
                mock.patch.object(prepare, '_PosixOutput', side_effect=AssertionError('mkdir before physical runtime overlap check')) as output:
            with self.assertRaisesRegex(ValueError, 'parent aliases'):
                owner.start(physical_parent / 'forbidden-output')
            output.assert_not_called()
        # Actual qualified output anchors reject a symbolic parent before mkdir.
        with mock.patch.object(prepare.os, 'mkdir', side_effect=AssertionError('mkdir through symbolic runtime alias')) as mkdir:
            with self.assertRaises(ValueError):
                owner.start(alias / 'forbidden-output')
            mkdir.assert_not_called()
        self.assertFalse((self.fixture.root / 'forbidden-output').exists())

    def test_wiring_only_actual_preparation_postflight_failure_poisoning_revokes_every_ticket(self):
        owner, checked, sources = self.preparation_owner()
        def postflight():
            self.assertTrue(owner.controller.python_reference())
            self.assertIs(prepare._resource(owner.resources).runtime, owner.controller)
            owner.capture.close.assert_not_called()
            raise ValueError('inert postflight failure')
        with mock.patch.object(prepare, '_workspace_owner', side_effect=self.real_workspace_owner), \
                mock.patch.object(prepare, '_check_generated_metadata', return_value={'wiring_only': True}), \
                mock.patch.object(owner, 'scan_sources', side_effect=postflight):
            with self.assertRaisesRegex(ValueError, 'inert postflight failure'):
                prepare.generate_metadata(checked, sources)
        self.assertTrue(owner.failed)
        self.assertTrue(owner.closed)
        self.assertTrue(owner.output.closed)
        owner.capture.close.assert_called_once()
        self.assertEqual(owner.tickets, set())
        self.assertNotIn(checked, prepare._PREPARATIONS)
        self.assertNotIn(sources, prepare._PREPARATIONS)
        self.assertFalse((owner.output.root / 'ready.json').exists())
        with self.assertRaises(prepare.MissingInputs):
            owner.controller.python_reference()
        with self.assertRaises(prepare.MissingInputs):
            prepare._resource(owner.resources)

    def test_wiring_only_sole_launch_live_sample_join_close_and_whole_log_receipt(self):
        value = self.bind()
        def output(stream):
            stream.write(b'original log\n')
            stream.flush()
            self.write_header(value, b'inert original header\n')
        self.launch_hook = output
        def final_close():
            self.events.append('close')
            self.launch.call_args.args[2].write(b'final close bytes\n')
        self.process.close.side_effect = final_close
        result = self.run_bound(value)
        self.assertEqual(self.events, ['launch', 'observe', 'validate', 'release', 'finish', 'sample', 'close'])
        self.launch.assert_called_once()
        self.assertIs(self.launch.call_args.kwargs['isolated_python_supervisor'], True)
        self.assertEqual(self.launch.call_args.args[:2], (value.argv, value.preparation.retained_root))
        self.process.observe_supervisor_startup.assert_called_once_with(
            deadline=prepare._BOUND_RUNS[value.bound].deadline)
        self.process.release_supervisor_startup.assert_called_once()
        self.assertIs(self.process.release_supervisor_startup.call_args.args[0], self.startup_observation)
        self.assertTrue(self.launch.call_args.args[2].closed)
        self.process.finish.assert_called_once()
        self.process.close.assert_called_once()
        self.process.terminate.assert_not_called()
        self.process.sample_processes.assert_called_once_with(maximum_processes=2,
            deadline=prepare._BOUND_RUNS[value.bound].deadline)
        self.assertTrue(result['process_owner_closed'])
        self.assertIs(result['hard_quota_claim'], False)
        self.assertIs(result['process_limit_enforced'], False)
        self.assertEqual(result['maximum_observed_processes'], 0)
        self.assertIs(result['live_process_census_complete'], False)
        self.assertIs(result['unknown_live_coverage'], True)
        self.assertIs(result['final_process_closure_observed'], True)
        self.assertEqual(value.bound.adopt_closed_log(value.output, 'controller/generator.log', 1024),
            b'original log\nfinal close bytes\n')
        with self.assertRaises(ValueError):
            self.run_bound(value)
        self.launch.assert_called_once()

    def test_wiring_only_closed_log_receipt_requires_actual_bound_owner_and_original_path_identity(self):
        for substitution in ('before-run', 'output-owner', 'log-name', 'same-bytes-replacement'):
            with self.subTest(substitution=substitution):
                value = self.bind()
                if substitution == 'before-run':
                    with self.assertRaises(ValueError):
                        value.bound.adopt_closed_log(value.output, 'controller/generator.log', 1024)
                    self.launch.assert_not_called()
                    continue
                self.launch_hook = lambda stream: (stream.write(b'original log'), stream.flush())
                self.run_bound(value)
                if substitution == 'output-owner':
                    with self.assertRaises(ValueError):
                        value.bound.adopt_closed_log(object.__new__(prepare._PosixOutput),
                            'controller/generator.log', 1024)
                elif substitution == 'log-name':
                    with self.assertRaises(ValueError):
                        value.bound.adopt_closed_log(value.output, 'controller/foreign.log', 1024)
                else:
                    replacement = self.root / 'replacement-log'
                    replacement.write_bytes(value.log.read_bytes())
                    replacement.chmod(0o644)
                    os.replace(replacement, value.log)
                    with self.assertRaisesRegex(ValueError, 'identity|original|changed|differ'):
                        value.bound.adopt_closed_log(value.output, 'controller/generator.log', 1024)

    def test_wiring_only_resource_original_inputs_and_actual_runtime_handle_are_mandatory(self):
        value = self.bind()
        for controller in ({'controller_admitted': True}, object.__new__(prepare._ControllerRuntime)):
            with self.subTest(controller=controller), self.assertRaises(prepare.MissingInputs):
                prepare._controller_resource_admission(self.fixture.reference, self.fixture.raw,
                    controller=controller)
        changed = dict(self.fixture.reference, sha256=pin(b'foreign resource wrapper'))
        with self.assertRaisesRegex(ValueError, 'original inputs differ'):
            prepare._controller_resource_admission(changed, self.fixture.raw, controller=value.runtime)
        self.launch.assert_not_called()

    def test_wiring_only_workspace_requires_actual_registered_preparation_association(self):
        value = self.bind()
        with mock.patch.object(prepare, '_workspace_owner', side_effect=self.real_workspace_owner):
            for output in (value.output, object.__new__(prepare._PosixOutput)):
                with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'registered preparation'):
                    value.resources.for_workspace(output, generated_root=value.generated,
                        temporary_root=value.temporary, protected_paths=(), argv=value.argv,
                        limits=value.limits, deadline=prepare.time.monotonic() + 10)
        self.launch.assert_not_called()

    def test_wiring_only_binding_rejects_foreign_roots_and_protected_overlap(self):
        value = self.bind()
        for change in ({'generated_root': self.root / 'foreign'},
                {'temporary_root': value.generated}, {'protected_paths': (value.output.root / 'retained',)},
                {'argv': value.argv + ['caller-switch']}):
            arguments = {'generated_root': value.generated, 'temporary_root': value.temporary,
                'protected_paths': (), 'argv': value.argv, 'limits': value.limits,
                'deadline': prepare.time.monotonic() + 10}
            arguments.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                value.resources.for_workspace(value.output, **arguments)
        self.launch.assert_not_called()

    def test_wiring_only_bound_argv_limits_environment_cwd_and_log_cannot_be_substituted(self):
        value = self.bind()
        for change in ({'argv': value.argv + ['caller-switch']},
                {'limits': dict(value.limits, maximum_processes=3)},
                {'environment': {'CALLER_READY': '1'}}, {'cwd': self.root},
                {'log': value.output.root / 'unreserved.log'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_bound(value, **change)
        self.launch.assert_not_called()

    def test_wiring_only_sample_threshold_equality_passes_and_excess_stops_live_owner(self):
        value = self.bind()
        self.process.poll.side_effect = [None, 0]
        self.process.sample_processes.side_effect = [
            _ObservedProcessSample(((10, 100, 1, 10), (11, 101, 10, 100)), False, True),
            _ObservedProcessSample((), True, False)]
        with mock.patch.object(prepare.time, 'sleep'):
            result = self.run_bound(value)
        self.assertEqual(result['maximum_observed_processes'], 2)
        self.assertIs(result['live_process_census_complete'], False)
        self.assertIs(result['unknown_live_coverage'], True)
        self.assertIs(result['final_process_closure_observed'], True)
        self.process.terminate.assert_not_called()
        excess = self.bind()
        self.process.reset_mock()
        self.process.poll.return_value = None
        self.process.sample_processes.side_effect = lambda **kwargs: _ObservedProcessSample((
            (10, 100, 1, 10), (11, 101, 10, 100), (12, 102, 10, 100)), False, True)
        with self.assertRaisesRegex(ValueError, 'observation|threshold'):
            self.run_bound(excess)
        self.process.terminate.assert_called_once_with(timeout=2)
        self.process.close.assert_called_once()
        self.process.finish.assert_not_called()

    def test_wiring_only_malformed_or_self_contradictory_observations_stop_the_live_owner(self):
        invalid = ((), _ObservedProcessSample((), True, True),
            _ObservedProcessSample(((10, 100, 1, 10), (10, 101, 1, 10)), False, True),
            _ObservedProcessSample(((True, 100, 1, 10),), False, True),
            _ObservedProcessSample(((10, 0, 1, 10),), False, True))
        for snapshot in invalid:
            with self.subTest(snapshot=snapshot):
                value = self.bind()
                self.process.poll.return_value = None
                self.process.sample_processes.side_effect = None
                self.process.sample_processes.return_value = snapshot
                with self.assertRaises((ValueError, AttributeError)):
                    self.run_bound(value)
                self.process.terminate.assert_called_once_with(timeout=2)
                self.process.close.assert_called_once()
                self.process.finish.assert_not_called()

    def test_wiring_only_joined_primary_still_requires_terminal_complete_closure_observation(self):
        value = self.bind()
        self.process.sample_processes.side_effect = None
        self.process.sample_processes.return_value = _ObservedProcessSample((), False, True)
        with self.assertRaisesRegex(prepare.process_tree.ProcessTreeError, 'closure observation'):
            self.run_bound(value)
        self.process.finish.assert_called_once()
        self.process.close.assert_called_once()
        self.process.terminate.assert_not_called()
        self.assertFalse((value.output.root / 'ready.json').exists())

    def test_wiring_only_whole_log_threshold_includes_bytes_written_during_close(self):
        value = self.bind(limits=dict(self.limits, maximum_log_bytes=3))
        def close():
            self.events.append('close')
            self.launch.call_args.args[2].write(b'four')
        self.process.close.side_effect = close
        with self.assertRaisesRegex(ValueError, 'log|threshold'):
            self.run_bound(value)
        self.process.finish.assert_called_once()
        self.process.close.assert_called_once()
        self.process.terminate.assert_not_called()
        self.assertTrue(self.launch.call_args.args[2].closed)

    def test_wiring_only_log_output_and_entry_threshold_equality_is_accepted(self):
        value = self.bind(limits=dict(self.limits, maximum_log_bytes=3, maximum_output_bytes=12))
        initial_entries = len(list(value.output.root.rglob('*')))
        def output(stream):
            stream.write(b'log')
            stream.flush()
            self.write_header(value, b'out')
        self.launch_hook = output
        # Exactly the original entries plus the exclusive log and fixed header.
        with mock.patch.object(prepare, 'MAX_OUTPUT_FILES', initial_entries + 2):
            self.run_bound(value)
        self.process.terminate.assert_not_called()
        self.assertEqual(value.bound.adopt_closed_log(value.output, 'controller/generator.log', 3), b'log')

    def test_wiring_only_entry_excess_stops_the_same_live_owner(self):
        value = self.bind()
        initial_entries = len(list(value.output.root.rglob('*')))
        self.launch_hook = lambda stream: self.write_header(value, b'out')
        self.process.poll.return_value = None
        with mock.patch.object(prepare, 'MAX_OUTPUT_FILES', initial_entries + 1):
            with self.assertRaisesRegex(ValueError, 'entry|threshold'):
                self.run_bound(value)
        self.process.terminate.assert_called_once_with(timeout=2)
        self.process.close.assert_called_once()
        self.process.finish.assert_not_called()

    def test_wiring_only_log_and_workspace_byte_excess_stop_the_same_live_owner(self):
        for channel in ('log', 'workspace'):
            with self.subTest(channel=channel):
                limits = dict(self.limits, maximum_log_bytes=3) if channel == 'log' else dict(
                    self.limits, maximum_output_bytes=9)
                value = self.bind(limits=limits)
                def output(stream):
                    if channel == 'log':
                        stream.write(b'four')
                        stream.flush()
                    else:
                        self.write_header(value, b'four')
                self.launch_hook = output
                self.process.reset_mock()
                self.process.poll.return_value = None
                with self.assertRaisesRegex(ValueError, 'log|output|threshold'):
                    self.run_bound(value)
                self.process.terminate.assert_called_once_with(timeout=2)
                self.process.close.assert_called_once()
                self.process.finish.assert_not_called()

    def test_wiring_only_unknown_special_or_changed_protected_output_fails_without_ready(self):
        for channel in ('unknown', 'symlink', 'protected'):
            with self.subTest(channel=channel):
                value = self.bind()
                def output(stream):
                    if channel == 'unknown':
                        (value.generated / 'foreign.hpp').write_bytes(b'unknown')
                    elif channel == 'symlink':
                        (value.generated / 'link').symlink_to(self.fixture.python)
                    else:
                        (value.output.root / 'retained/recipe.json').write_bytes(b'changed')
                self.launch_hook = output
                self.process.reset_mock()
                self.process.poll.return_value = None
                with self.assertRaises(ValueError):
                    self.run_bound(value)
                self.process.terminate.assert_called_once_with(timeout=2)
                self.process.close.assert_called_once()
                self.assertFalse((value.output.root / 'ready.json').exists())

    def test_wiring_only_nonzero_and_unjoined_descendant_failure_preserve_sole_completion(self):
        value = self.bind()
        self.process.finish.side_effect = lambda: self.finish_process(13)
        with self.assertRaisesRegex(ValueError, 'exited 13'):
            self.run_bound(value)
        self.process.close.assert_called_once()
        self.process.terminate.assert_not_called()
        descendant = self.bind()
        self.process.reset_mock()
        self.process.finish.side_effect = prepare.process_tree.ProcessTreeError('inert live descendant')
        with self.assertRaisesRegex(prepare.process_tree.ProcessTreeError, 'live descendant'):
            self.run_bound(descendant)
        self.process.terminate.assert_called_once_with(timeout=2)
        self.process.close.assert_called_once()

    def test_wiring_only_nonzero_joined_primary_preserves_failure_without_successful_terminal_sample(self):
        value = self.bind()
        self.process.finish.side_effect = lambda: self.finish_process(7)
        self.process.sample_processes.side_effect = AssertionError('nonzero exit requested successful terminal sample')
        before = len(prepare._UNCERTAIN)
        with mock.patch.object(value.output, 'adopt_closed_log',
                side_effect=AssertionError('failed primary log was adopted')) as adopt:
            with self.assertRaisesRegex(ValueError, 'exited 7'):
                self.run_bound(value)
            with self.assertRaises(ValueError):
                value.bound.adopt_closed_log(value.output, 'controller/generator.log', 1024)
            adopt.assert_not_called()
        self.process.finish.assert_called_once()
        self.process.sample_processes.assert_not_called()
        self.process.close.assert_called_once()
        self.process.terminate.assert_not_called()
        self.assertEqual(prepare._BOUND_RUNS[value.bound].phase, 'failed')
        self.assertTrue(self.launch.call_args.args[2].closed)
        self.assertEqual(len(prepare._UNCERTAIN), before)

    def test_wiring_only_uncertain_close_retains_original_stream_runtime_and_workspace(self):
        value = self.bind()
        before = len(prepare._UNCERTAIN)
        self.process.close.side_effect = RuntimeError('inert close uncertain')
        with self.assertRaisesRegex(prepare.process_tree.ProcessTreeError, 'uncertain'):
            self.run_bound(value)
        retained = prepare._BOUND_RUNS[value.bound]
        self.assertEqual(len(prepare._UNCERTAIN), before + 1)
        self.assertIs(prepare._UNCERTAIN[-1], retained)
        self.assertIs(retained.output, value.output)
        self.assertIs(retained.owner, self.process)
        self.assertIs(retained.stream, self.launch.call_args.args[2])
        self.assertFalse(retained.stream.closed)
        self.process.close.assert_called_once()
        self.process.terminate.assert_not_called()
        for operation in (value.resources.close, value.runtime.close):
            with self.subTest(operation=operation), self.assertRaises(prepare.process_tree.ProcessTreeError):
                operation()
        self.assertFalse((value.output.root / 'ready.json').exists())

    def test_wiring_only_postjoin_runtime_mutation_and_fsync_failure_never_reclose_owner(self):
        for failure in ('runtime', 'current', 'fsync'):
            with self.subTest(failure=failure):
                value = self.bind()
                self.process.reset_mock()
                if failure == 'runtime':
                    self.process.close.side_effect = lambda: setattr(self.fixture, 'capture_failure', True)
                    context = ExitStack()
                elif failure == 'current':
                    self.process.close.side_effect = lambda: self.fixture.observation.__setitem__(
                        'path', str(self.root / 'changed-postjoin-current-python'))
                    context = ExitStack()
                else:
                    context = mock.patch.object(prepare.os, 'fsync', side_effect=OSError('inert fsync failure'))
                try:
                    with context, self.assertRaises((ValueError, OSError)):
                        self.run_bound(value)
                    self.process.finish.assert_called_once()
                    self.process.close.assert_called_once()
                    self.process.terminate.assert_not_called()
                    self.assertTrue(self.launch.call_args.args[2].closed)
                    self.assertFalse((value.output.root / 'ready.json').exists())
                finally:
                    self.fixture.capture_failure = False
                    self.fixture.observation['path'] = str(self.fixture.python)
                    self.process.close.side_effect = lambda: self.events.append('close')

    def test_wiring_only_first_log_close_failure_is_uncertain_without_retry(self):
        value = self.bind()
        original_fdopen = prepare.os.fdopen
        class Stream:
            def __init__(self, stream):
                self.stream, self.close_calls = stream, 0
            @property
            def closed(self):
                return self.stream.closed
            def fileno(self):
                return self.stream.fileno()
            def write(self, raw):
                return self.stream.write(raw)
            def flush(self):
                return self.stream.flush()
            def close(self):
                self.close_calls += 1
                if self.close_calls == 1:
                    raise OSError('inert first log close failure')
                self.stream.close()
        def open_stream(*arguments, **keywords):
            return Stream(original_fdopen(*arguments, **keywords))
        before = len(prepare._UNCERTAIN)
        with mock.patch.object(prepare.os, 'fdopen', side_effect=open_stream):
            with self.assertRaisesRegex(prepare.process_tree.ProcessTreeError, 'uncertain'):
                self.run_bound(value)
        stream = self.launch.call_args.args[2]
        self.assertEqual(stream.close_calls, 1)
        self.assertFalse(stream.closed)
        self.assertEqual(len(prepare._UNCERTAIN), before + 1)
        self.assertIs(prepare._UNCERTAIN[-1], prepare._BOUND_RUNS[value.bound])
        self.process.finish.assert_called_once()
        self.process.close.assert_called_once()
        self.process.terminate.assert_not_called()

    def test_wiring_only_wall_threshold_includes_owner_close_without_second_termination(self):
        now = [0]
        with mock.patch.object(prepare.time, 'monotonic', side_effect=lambda: now[0]):
            value = self.bind()
            self.process.close.side_effect = lambda: now.__setitem__(0, 11)
            with self.assertRaisesRegex(ValueError, 'wall threshold'):
                self.run_bound(value)
        self.process.finish.assert_called_once()
        self.process.close.assert_called_once()
        self.process.terminate.assert_not_called()
        self.assertTrue(self.launch.call_args.args[2].closed)


class ControllerCapabilityRejectionTests(unittest.TestCase):
    """Public data and unregistered objects never acquire controller ownership."""
    def test_private_controller_handle_constructors_cannot_issue_authority(self):
        for name in ('_ControllerRuntime', '_MetadataResources', '_BoundMetadataRun'):
            with self.subTest(handle=name), self.assertRaises((TypeError, ValueError, prepare.MissingInputs)):
                getattr(prepare, name)()

    def test_unregistered_runtime_cannot_supply_program_environment_or_recheck(self):
        forged = object.__new__(prepare._ControllerRuntime)
        with tempfile.TemporaryDirectory(prefix='windows-runtime-forged-inert-') as temporary:
            root = Path(temporary)
            with mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('forged runtime launch')):
                for operation in (forged.python_reference, forged.protected_paths,
                        lambda: forged.environment(root), forged.recheck):
                    with self.subTest(operation=operation), self.assertRaises(prepare.MissingInputs):
                        operation()
            self.assertEqual(list(root.iterdir()), [])

    def test_unregistered_resource_and_run_handles_cannot_bind_or_launch(self):
        resources = object.__new__(prepare._MetadataResources)
        bound = object.__new__(prepare._BoundMetadataRun)
        with tempfile.TemporaryDirectory(prefix='windows-resources-forged-inert-') as temporary:
            root = Path(temporary)
            argv, limits = ['inert-never-executed'], {'generator_seconds': 1}
            with mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('forged resources launch')):
                with self.assertRaises(prepare.MissingInputs):
                    resources.for_workspace(object(), generated_root=root / 'generated',
                        temporary_root=root / 'temporary', protected_paths=(), argv=argv,
                        limits=limits, deadline=1)
                with self.assertRaises((ValueError, prepare.MissingInputs)):
                    bound.run(argv, root, root / 'log', {}, limits)
                with self.assertRaises((ValueError, prepare.MissingInputs)):
                    bound.adopt_closed_log(object(), 'log', 1)
            self.assertEqual(list(root.iterdir()), [])


class PreparationRegistryRejectionTests(unittest.TestCase):
    def test_direct_ticket_construction_cannot_supply_preparation_authority(self):
        with self.assertRaises((TypeError, ValueError, prepare.MissingInputs)):
            prepare._PreparationTicket()

    def test_unregistered_ticket_object_is_rejected_before_output_or_launch(self):
        from test_appended_engine_windows_source_replay import no_programs
        forged = object.__new__(prepare._PreparationTicket)
        with tempfile.TemporaryDirectory(prefix='windows-ticket-rejection-inert-') as temporary:
            output = Path(temporary) / 'output'
            with no_programs(), mock.patch.object(prepare.process_tree, 'launch',
                    side_effect=AssertionError('unregistered ticket launched a program')):
                for operation, arguments in ((prepare._checked, (forged,)),
                        (prepare.prepare_sources, (forged, output)),
                        (prepare.generate_metadata, (forged, {})),
                        (prepare.handoff_selection, (forged,))):
                    with self.subTest(operation=operation.__name__), self.assertRaises(prepare.MissingInputs):
                        operation(*arguments)
            self.assertFalse(output.exists())


class GeneratedMetadataWiringOnlyTests(unittest.TestCase):
    """The existing generated-output join is mocked; no generator is executed."""
    def test_exact_header_path_reaches_join_and_result_remains_unadmitted(self):
        with tempfile.TemporaryDirectory(prefix='windows-generated-wiring-inert-') as temporary:
            header = Path(temporary) / 'generated' / handoff.HEADER
            raw = {role: b'inert generated metadata\n' for role in handoff.REFS}
            raw['metadata_receipt'] = prepare.encoded({'header': str(header)})
            retained_read = mock.Mock(side_effect=AssertionError('mocked join must not read retained bodies'))
            facts, retained, assembled = {'inert': 'metadata'}, {'inert': 'retained'}, {'inert': 'assembled'}
            with mock.patch.object(handoff, '_joined', return_value=(facts, retained, assembled)) as joined, \
                    mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('generator launch')):
                result = prepare._check_generated_metadata(raw, retained_read, header)
            joined.assert_called_once_with(raw, retained_read)
            self.assertEqual(result['metadata'], facts)
            self.assertEqual(result['retained_inventory'], retained)
            self.assertEqual(result['assembled_inventory'], assembled)
            self.assertIs(result['source_proof_admitted'], False)
            self.assertIs(result['controller_admitted'], False)

    def test_wrong_original_header_path_stops_before_generated_output_join(self):
        with tempfile.TemporaryDirectory(prefix='windows-generated-path-inert-') as temporary:
            header = Path(temporary) / 'generated' / handoff.HEADER
            raw = {role: b'inert generated metadata\n' for role in handoff.REFS}
            raw['metadata_receipt'] = prepare.encoded({'header': str(header.with_name('foreign.hpp'))})
            with mock.patch.object(handoff, '_joined', side_effect=AssertionError('join after path mismatch')):
                with self.assertRaisesRegex(ValueError, 'header path differs'):
                    prepare._check_generated_metadata(raw, mock.Mock(), header)


class _WiringOnlyPreparationOwner:
    """Mock private stage callbacks; no capture, source proof or controller runs."""
    def __init__(self, root):
        self.root = root
        self.phase, self.tickets, self.events = 'checked', set(), []
        self.failed = self.closed = False
        self.failpoint = None
        self.retained_root, self.assembled_root = root / 'retained', root / 'assembled'
        paths = {'recipe': 'retained/recipe.json', 'sources': 'retained/sources.json',
            'provider_build': 'metadata/provider-build.json',
            'assembled_inventory': 'metadata/assembled-inventory.json',
            'native_inputs': 'retained/' + prepare.NATIVE_INPUTS_PATH,
            'metadata_header': 'generated/' + handoff.HEADER,
            'metadata_receipt': 'metadata/metadata-receipt.json'}
        self.references = {role: reference(root / name) for role, name in paths.items()}

    def _event(self, name):
        self.events.append((name, self.phase))
        if self.failpoint == name:
            raise ValueError('inert wiring failure: ' + name)

    def check(self):
        if self.closed or self.failed:
            raise ValueError('inert wiring owner is closed or failed')
        self._event('check')

    def start(self, root):
        if Path(root) != self.root:
            raise ValueError('inert wiring root differs')
        self._event('start')

    def prepare(self):
        self._event('prepare')

    def generate(self):
        self._event('generate')

    def scan_sources(self):
        self._event('scan_sources')

    def scan_generated(self):
        self._event('scan_generated')

    def summary(self):
        self._event('summary')
        return {'wiring_only': True, 'phase': self.phase, 'source_proof_admitted': False,
                **{name: False for name in prepare.FALSE_FACTS}}

    def replay_selection(self):
        self._event('replay_selection')
        return {'wiring_only': True, 'root': str(self.root)}

    def close(self):
        if not self.closed:
            self._event('close')
            self.closed = True
            for ticket in tuple(self.tickets):
                prepare._PREPARATIONS.pop(ticket, None)
            self.tickets.clear()

    def fail(self):
        self.failed = True
        self.events.append(('fail', self.phase))
        self.close()


class PublicPreparationWiringOnlyTests(unittest.TestCase):
    """Privately issued mock-owner tickets exercise routing, never admission."""
    def setUp(self):
        from test_appended_engine_windows_source_replay import no_programs
        self.no_programs = no_programs
        self.temporary = tempfile.TemporaryDirectory(prefix='windows-public-wiring-inert-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def owner(self, name='output'):
        owner = _WiringOnlyPreparationOwner(self.root / name)
        self.addCleanup(owner.close)
        # This is explicit private test setup, not the production inspection path.
        return owner, prepare._issue('checked', owner)

    def test_wiring_only_public_chain_consumes_phases_and_returns_exact_handoff_references(self):
        owner, checked = self.owner()
        with self.no_programs(), mock.patch.object(prepare.process_tree, 'launch', side_effect=AssertionError('program launch')):
            sources = prepare.prepare_sources(checked, owner.root)
            self.assertEqual(owner.phase, 'sources_ready')
            metadata = prepare.generate_metadata(checked, sources)
            self.assertEqual(owner.phase, 'metadata_ready')
            selected = prepare.handoff_selection(metadata)
            self.assertEqual(owner.phase, 'closed')
            self.assertTrue(owner.closed)
            for operation, arguments in ((prepare.prepare_sources, (checked, owner.root)),
                    (prepare.generate_metadata, (checked, sources)), (prepare.handoff_selection, (metadata,))):
                with self.subTest(operation=operation.__name__), self.assertRaises(prepare.MissingInputs):
                    operation(*arguments)
        self.assertEqual(set(selected), {'schema_version', 'kind', 'target', 'source_catalogue',
                                        'retained_root', 'assembled_root', *handoff.REFS})
        self.assertEqual(selected['kind'], handoff.SELECTION_KIND)
        self.assertEqual(selected['target'], contract.TARGET)
        self.assertEqual(selected['source_catalogue'], contract.CATALOGUE)
        self.assertEqual(selected['retained_root'], str(owner.retained_root))
        self.assertEqual(selected['assembled_root'], str(owner.assembled_root))
        self.assertEqual({role: selected[role] for role in handoff.REFS}, owner.references)
        selected['recipe']['sha256'] = pin(b'changed returned data')
        self.assertNotEqual(selected['recipe'], owner.references['recipe'])
        self.assertIn(('prepare', 'materializing'), owner.events)
        self.assertIn(('generate', 'generating'), owner.events)
        self.assertIn(('scan_generated', 'metadata_ready'), owner.events)
        self.assertFalse(owner.root.exists())

    def test_wiring_only_cross_owner_and_reused_source_ticket_cannot_advance_a_stage(self):
        first, first_checked = self.owner('first')
        second, second_checked = self.owner('second')
        with self.no_programs():
            first_sources = prepare.prepare_sources(first_checked, first.root)
            second_sources = prepare.prepare_sources(second_checked, second.root)
            with self.assertRaisesRegex(ValueError, 'another inspection'):
                prepare.generate_metadata(first_checked, second_sources)
            with self.assertRaises(ValueError):
                prepare.prepare_sources(first_checked, first.root)
            with self.assertRaises(prepare.MissingInputs):
                prepare.prepare_sources(first_sources, first.root)
        self.assertEqual(first.phase, 'sources_ready')
        self.assertEqual(second.phase, 'sources_ready')
        self.assertFalse(any(name == 'generate' for name, phase in first.events + second.events))
        self.assertFalse(first.root.exists())
        self.assertFalse(second.root.exists())

    def test_wiring_only_phase_failures_poison_owner_and_revoke_all_issued_tickets(self):
        for failpoint in ('start', 'prepare', 'generate', 'scan_sources', 'scan_generated'):
            with self.subTest(failpoint=failpoint), self.no_programs():
                owner, checked = self.owner(failpoint)
                if failpoint in ('start', 'prepare'):
                    owner.failpoint = failpoint
                    operation = lambda: prepare.prepare_sources(checked, owner.root)
                else:
                    sources = prepare.prepare_sources(checked, owner.root)
                    if failpoint == 'generate':
                        owner.failpoint = failpoint
                        operation = lambda: prepare.generate_metadata(checked, sources)
                    else:
                        metadata = prepare.generate_metadata(checked, sources)
                        owner.failpoint = failpoint
                        operation = lambda: prepare.handoff_selection(metadata)
                with self.assertRaisesRegex(ValueError, 'inert wiring failure: ' + failpoint):
                    operation()
                self.assertTrue(owner.failed)
                self.assertTrue(owner.closed)
                self.assertEqual(owner.tickets, set())
                with self.assertRaises(prepare.MissingInputs):
                    prepare.prepare_sources(checked, owner.root)
                self.assertFalse(owner.root.exists())

    def test_wiring_only_prephase_check_failure_poisoning_revokes_every_owned_ticket(self):
        for phase in ('checked', 'sources_ready', 'metadata_ready'):
            with self.subTest(phase=phase), self.no_programs():
                owner, checked = self.owner('prephase-' + phase)
                if phase == 'checked':
                    operation = lambda: prepare.prepare_sources(checked, owner.root)
                else:
                    sources = prepare.prepare_sources(checked, owner.root)
                    if phase == 'sources_ready':
                        operation = lambda: prepare.generate_metadata(checked, sources)
                    else:
                        metadata = prepare.generate_metadata(checked, sources)
                        operation = lambda: prepare.handoff_selection(metadata)
                issued = tuple(owner.tickets)
                previous_events = len(owner.events)
                owner.failpoint = 'check'
                with self.assertRaisesRegex(ValueError, 'inert wiring failure: check'):
                    operation()
                self.assertTrue(owner.failed)
                self.assertTrue(owner.closed)
                self.assertEqual(owner.phase, phase)
                self.assertEqual(owner.events[previous_events:], [('check', phase), ('fail', phase), ('close', phase)])
                self.assertEqual(owner.tickets, set())
                self.assertTrue(all(ticket not in prepare._PREPARATIONS for ticket in issued))
                owner.failpoint = None
                with self.assertRaises(prepare.MissingInputs):
                    operation()
                self.assertFalse(owner.root.exists())

    def test_wiring_only_cli_check_serializes_plain_summary_and_closes_owner(self):
        owner, ticket = self.owner()
        selection, selected_pin = self.root / 'not-read-selection.json', pin(b'inert selection')
        with self.no_programs(), mock.patch.object(prepare, 'inspect_prepare', return_value=ticket) as inspection, \
                redirect_stdout(io.StringIO()) as output:
            code = prepare.cli(['check', '--selection', str(selection), '--selection-sha256', selected_pin])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), {'wiring_only': True, 'phase': 'checked',
            'source_proof_admitted': False, **{name: False for name in prepare.FALSE_FACTS}})
        inspection.assert_called_once_with(str(selection), selected_pin)
        self.assertTrue(owner.closed)
        self.assertFalse(owner.root.exists())

    def test_wiring_only_cli_prepare_serializes_replay_and_handoff_after_stage_chain(self):
        owner, ticket = self.owner()
        selection, selected_pin = self.root / 'not-read-selection.json', pin(b'inert selection')
        with self.no_programs(), mock.patch.object(prepare, 'inspect_prepare', return_value=ticket), \
                redirect_stdout(io.StringIO()) as output:
            code = prepare.cli(['prepare', '--selection', str(selection), '--selection-sha256', selected_pin,
                                '--output', str(owner.root)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result['wiring_only'])
        self.assertEqual(result['phase'], 'metadata_ready')
        self.assertIs(result['source_proof_admitted'], False)
        self.assertTrue(all(result[name] is False for name in prepare.FALSE_FACTS))
        self.assertEqual(result['source_replay_selection'], {'wiring_only': True, 'root': str(owner.root)})
        self.assertEqual({role: result['handoff_selection'][role] for role in handoff.REFS}, owner.references)
        self.assertEqual(owner.phase, 'closed')
        self.assertTrue(owner.closed)
        self.assertFalse(owner.root.exists())


class MaterializationTests(unittest.TestCase):
    def setUp(self):
        from test_appended_engine_windows_source_replay import Fixture, no_programs
        self.Fixture, self.no_programs = Fixture, no_programs
        self.temporary = tempfile.TemporaryDirectory(prefix='windows-source-materializer-inert-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_synthetic_supplier_patch_overlay_materializes_three_formats_as_unchecked(self):
        for archive_format in ('tar-gzip', 'tar-xz', 'zip'):
            fixture = self.Fixture(archive_format)
            fixture.patch()
            fixture.overlay()
            fixture.seal()
            output = prepare._PosixOutput(self.root / archive_format)
            try:
                with self.subTest(format=archive_format), self.no_programs():
                    result = prepare._materialize_candidate(fixture.projection, fixture.streams,
                        fixture.patches, fixture.overlays, fixture.overlay_facts, fixture.limits, output)
                    self.assertEqual((output.root / 'assembled/source/engine/Source/a.txt').read_bytes(), b'final overlay\n')
                    self.assertFalse(result['original_proof_admitted'])
                    self.assertFalse(result['preparation_complete'])
                    self.assertFalse((output.root / 'ready.json').exists())
            finally:
                output.close()

    def test_wiring_only_checked_extraction_uses_derived_target_without_another_replay_or_hash_pass(self):
        fixture = self.Fixture()
        fixture.add('engine', 'Source/alias.txt', kind='symlink', link='a.txt',
                    expected=b'before\n', target_mode=0o644)
        fixture.projection['projection']['normalizations']['engine']['Source/alias.txt'] = 'Source/a.txt'
        fixture.seal()
        expected = {key: value for key, value in fixture.run().items() if key in ('files', 'directories', 'modes')}
        projection = copy.deepcopy(fixture.projection)
        # Explicit lower wiring fixture, not a shared checked object. The public
        # owner gets this view only from its actual shared source authority.
        projection['_files'] = {name: {**item, 'regular_member':
            projection['projection']['normalizations'][item['archive']].get(item['member'], item['member'])}
            for name, item in projection['projection']['files'].items()}
        projection['projection']['normalizations']['engine'].clear()
        output = prepare._PosixOutput(self.root / 'checked-extract-wiring')
        replay = prepare._replay()
        try:
            with self.no_programs(), mock.patch.object(replay, 'replay_projection',
                    side_effect=AssertionError('duplicate replay')), mock.patch.object(replay, '_stream_pin',
                    side_effect=AssertionError('duplicate whole archive hash')):
                result = prepare._materialize_candidate_data(projection, fixture.streams, [], {}, {},
                    fixture.limits, output, checked_inventory=expected)
            source = output.root / 'assembled/source/engine/Source/a.txt'
            alias = source.with_name('alias.txt')
            self.assertEqual(alias.read_bytes(), b'before\n')
            self.assertNotEqual(alias.stat().st_ino, source.stat().st_ino)
            self.assertEqual({key: result[key] for key in expected}, expected)
            self.assertFalse(result['original_proof_admitted'])
            self.assertFalse(result['preparation_complete'])
        finally:
            output.close()

    def test_deleted_owned_path_can_be_recreated_by_final_exact_overlay(self):
        fixture = self.Fixture()
        raw = b'--- a/Source/a.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-before\n'
        fixture.patches = [raw]
        fixture.projection['patches'] = [{'path': 'patches/delete.patch', 'sha256': pin(raw), 'tree': 'engine',
            'preimages': {'Source/a.txt': pin(b'before\n')}, 'postimages': {'Source/a.txt': None}}]
        fixture.overlay(body=b'new ordinary overlay\n', mode=0o755)
        fixture.seal()
        output = prepare._PosixOutput(self.root / 'delete-overlay')
        try:
            with self.no_programs():
                prepare._materialize_candidate(fixture.projection, fixture.streams, fixture.patches,
                    fixture.overlays, fixture.overlay_facts, fixture.limits, output)
            path = output.root / 'assembled/source/engine/Source/a.txt'
            self.assertEqual(path.read_bytes(), b'new ordinary overlay\n')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)
            self.assertEqual(path.stat().st_nlink, 1)
        finally:
            output.close()

    def test_normalized_link_becomes_independent_file_and_deleted_parent_is_retained(self):
        fixture = self.Fixture()
        fixture.add('engine', 'Source/alias.txt', kind='symlink', link='a.txt',
                    expected=b'before\n', target_mode=0o644)
        fixture.projection['projection']['normalizations']['engine']['Source/alias.txt'] = 'Source/a.txt'
        fixture.add('engine', 'EmptyAfterPatch/only.txt', b'delete\n')
        raw = b'--- a/EmptyAfterPatch/only.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-delete\n'
        fixture.patches = [raw]
        fixture.projection['patches'] = [{'path': 'patches/delete.patch', 'sha256': pin(raw), 'tree': 'engine',
            'preimages': {'EmptyAfterPatch/only.txt': pin(b'delete\n')},
            'postimages': {'EmptyAfterPatch/only.txt': None}}]
        fixture.seal()
        output = prepare._PosixOutput(self.root / 'normalized-and-empty')
        try:
            with self.no_programs():
                result = prepare._materialize_candidate(fixture.projection, fixture.streams, fixture.patches,
                    fixture.overlays, fixture.overlay_facts, fixture.limits, output)
            source = output.root / 'assembled/source/engine/Source/a.txt'
            alias = source.with_name('alias.txt')
            self.assertEqual(alias.read_bytes(), source.read_bytes())
            self.assertNotEqual(alias.stat().st_ino, source.stat().st_ino)
            self.assertFalse(alias.is_symlink())
            empty = output.root / 'assembled/source/engine/EmptyAfterPatch'
            self.assertTrue(empty.is_dir())
            self.assertEqual(list(empty.iterdir()), [])
            self.assertEqual(result['modes']['source/engine/EmptyAfterPatch'], 0o755)
        finally:
            output.close()

    def test_caller_mutation_between_replay_and_write_cannot_change_supplier_patch(self):
        fixture = self.Fixture()
        original = fixture.patch()
        fixture.overlay()
        fixture.seal()
        replay = prepare._replay()
        replay_function = replay.replay_projection
        patch_function = prepare.native_source.apply_unified_patch
        def mutate_after_replay(*arguments, **keywords):
            result = replay_function(*arguments, **keywords)
            foreign = b'--- a/Source/a.txt\n+++ b/Source/a.txt\n@@ -1 +1 @@\n-before\n+foreign\n'
            fixture.patches[0] = foreign
            fixture.projection['patches'][0]['sha256'] = pin(foreign)
            fixture.projection['patches'][0]['postimages']['Source/a.txt'] = pin(b'foreign\n')
            return result
        output = prepare._PosixOutput(self.root / 'immutable-metadata')
        try:
            with self.no_programs(), mock.patch.object(replay, 'replay_projection', side_effect=mutate_after_replay), \
                    mock.patch.object(prepare.native_source, 'apply_unified_patch', wraps=patch_function) as patches:
                prepare._materialize_candidate(fixture.projection, fixture.streams, fixture.patches,
                    fixture.overlays, fixture.overlay_facts, fixture.limits, output)
            self.assertEqual([call.args[1] for call in patches.call_args_list], [original, original])
        finally:
            output.close()

    def test_wall_bound_still_applies_after_final_overlay_before_scan(self):
        fixture = self.Fixture()
        fixture.overlay()
        fixture.seal()
        output = prepare._PosixOutput(self.root / 'late-overlay')
        now = [0]
        save = output.save
        def late_save(*arguments, **keywords):
            result = save(*arguments, **keywords)
            if arguments[1] == b'final overlay\n':
                now[0] = fixture.limits['seconds'] + 1
            return result
        try:
            with self.no_programs(), mock.patch.object(prepare.time, 'monotonic', side_effect=lambda: now[0]), \
                    mock.patch.object(output, 'save', side_effect=late_save), \
                    mock.patch.object(handoff, '_scan', side_effect=AssertionError('scan after wall bound')):
                with self.assertRaisesRegex(ValueError, 'wall budget'):
                    prepare._materialize_candidate(fixture.projection, fixture.streams, fixture.patches,
                        fixture.overlays, fixture.overlay_facts, fixture.limits, output)
            for operation in (output.recheck, lambda: output.save('resume', b'forbidden')):
                with self.assertRaisesRegex(ValueError, 'has failed'):
                    operation()
        finally:
            output.close()

    def test_late_archive_pin_failure_after_save_poisoned_the_entire_operation(self):
        fixture = self.Fixture().seal()
        output = prepare._PosixOutput(self.root / 'late-pin')
        replay = prepare._replay()
        stream_pin = replay._stream_pin
        def late_pin(*arguments, **keywords):
            stream_pin(*arguments, **keywords)
            if output.files:
                raise ValueError('inert late archive pin failure')
        try:
            with self.no_programs(), mock.patch.object(replay, '_stream_pin', side_effect=late_pin):
                with self.assertRaisesRegex(ValueError, 'late archive pin'):
                    prepare._materialize_candidate(fixture.projection, fixture.streams, fixture.patches,
                        fixture.overlays, fixture.overlay_facts, fixture.limits, output)
            self.assertTrue(output.files)
            for operation in (output.recheck, lambda: output.save('resume', b'forbidden')):
                with self.assertRaisesRegex(ValueError, 'has failed'):
                    operation()
        finally:
            output.close()

    def test_complete_inventory_failure_preserves_files_but_prohibits_completion(self):
        fixture = self.Fixture().seal()
        output = prepare._PosixOutput(self.root / 'failed-complete-scan')
        try:
            with self.no_programs(), mock.patch.object(handoff, '_scan', side_effect=ValueError('inert final inventory differs')):
                with self.assertRaisesRegex(ValueError, 'final inventory differs'):
                    prepare._materialize_candidate(fixture.projection, fixture.streams, fixture.patches,
                        fixture.overlays, fixture.overlay_facts, fixture.limits, output)
            self.assertTrue(output.files)
            for operation in (output.recheck, lambda: output.save('resume', b'forbidden')):
                with self.assertRaisesRegex(ValueError, 'has failed'):
                    operation()
        finally:
            output.close()


if __name__ == '__main__':
    unittest.main()
