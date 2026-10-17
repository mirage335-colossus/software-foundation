"""First-native producer fixtures; no real SDK, engine, provider or DSO executes.

The optional CMake script cases use tiny artificial ELF headers and a fake
inspection program. They check producer rejection behavior, not native artifact
validity, actual readelf, link success or runtime eligibility.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'recipes/webkitwasm-native-rich4083-v1'
PRODUCER = ROOT / 'tools/appended_engine_native_prototype.py'
VERIFY = RECIPE / 'producer/verify-provider.cmake'
CACHE = RECIPE / 'producer/native-initial-cache.cmake'
CMAKE = Path('/usr/bin/cmake')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def load_producer():
    """Import repository-owned producer code, never a retained SDK module."""
    name = '_native_prototype_fixture_module'
    spec = importlib.util.spec_from_file_location(name, PRODUCER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    tools = str(ROOT / 'tools')
    with mock.patch.object(sys, 'path', [tools, *sys.path]):
        spec.loader.exec_module(module)
    return module


class TypedCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def test_exact_real_template_has_only_concrete_required_tokens(self):
        template = CACHE.read_bytes()
        tokens = set(re.findall(rb'@([A-Za-z_][A-Za-z0-9_]*)@', template))
        self.assertNotIn(b'TOKEN', tokens)
        self.assertIn(b'BIB_NATIVE_PROVIDER_METADATA_HEADER_SHA256', tokens)
        values = {name.decode('ascii'): '/private/fixture inputs/' + name.decode('ascii')
                  for name in tokens}
        result = self.producer.render_cache(template, values)
        self.assertIsInstance(result, bytes)
        self.assertNotIn(b'@', result)
        self.assertIn(b'set(PORT Foundation CACHE STRING', result)
        self.assertIn(b'set(CMAKE_CXX_STANDARD 23 CACHE STRING', result)
        self.assertIn(b'/private/fixture inputs/CMAKE_CXX_COMPILER', result)

    def test_missing_and_extra_values_fail_closed(self):
        for values in ({}, {'ROOT': '/private/root', 'EXTRA': '/private/other'}):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    self.producer.render_cache(b'set(X "@ROOT@")\n', values)

    def test_each_cmake_injection_character_is_rejected(self):
        for bad in (';', '"', '\n', '\r', '\\', '$', '@'):
            with self.subTest(character=repr(bad)):
                with self.assertRaises(ValueError):
                    self.producer.render_cache(b'set(X "@ROOT@")\n',
                                               {'ROOT': '/private/' + bad + 'injected'})

    def test_non_string_values_do_not_become_cmake(self):
        for value in (None, True, 1, [], {}):
            with self.subTest(value=value):
                with self.assertRaises((ValueError, TypeError)):
                    self.producer.render_cache(b'set(X "@ROOT@")\n', {'ROOT': value})

    def test_unrecognised_unresolved_token_is_rejected(self):
        with self.assertRaises(ValueError):
            self.producer.render_cache(b'set(X "@ROOT@ @invalid-token@")\n',
                                       {'ROOT': '/private/root'})

    def test_rendering_preserves_repeated_literal_values(self):
        self.assertEqual(self.producer.render_cache(b'@ROOT@\n@ROOT@\n', {'ROOT': '/x y'}),
                         b'/x y\n/x y\n')


LIMITS = {'prepare_seconds': 1, 'configure_seconds': 1, 'build_seconds': 1,
          'cleanup_seconds': 1, 'maximum_jobs': 2, 'maximum_output_bytes': 1048576,
          'minimum_free_bytes': 1, 'maximum_process_tree_bytes': 1048576}
HEALTHY = {'output_bytes': 10, 'free_bytes': 10485760, 'process_tree_bytes': 1024}


class FakeInspection:
    """A mocked unit seam, never an actual admitted native source group."""
    def __init__(self, marker):
        self.marker = marker
        self.marker_pin = sha(marker.read_bytes())
        self.protected_paths = (marker.parent,)
        self.phase_limits = dict(LIMITS)
        self.facts = {'fixture_only': True, 'marker_sha256': self.marker_pin}
        self.rechecks = 0

    def as_dict(self):
        return json.loads(json.dumps(self.facts))

    def recheck(self):
        self.rechecks += 1
        if sha(self.marker.read_bytes()) != self.marker_pin:
            raise ValueError('fixture input bytes changed')


class ControllerPythonTests(unittest.TestCase):
    """Interpreter-path doubles only; no retained interpreter executes."""
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-controller-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.python = self.root / 'admitted-python'
        self.python.write_bytes(b'fixture-only interpreter identity; never executed\n')
        self.inspection = SimpleNamespace(programs={'python': {
            'path': str(self.python), 'sha256': sha(self.python.read_bytes())}})

    def test_matching_interpreter_and_disabled_bytecode_bind_exact_identity(self):
        with mock.patch.object(self.producer.sys, 'executable', str(self.python)), \
                mock.patch.object(self.producer.sys, 'dont_write_bytecode', True), \
                mock.patch.object(self.producer.process_tree, 'launch',
                                  side_effect=AssertionError('controller check launched a process')):
            result = self.producer._controller_python(self.inspection)
        self.assertEqual(result['path'], str(self.python))
        self.assertEqual(result['sha256'], sha(self.python.read_bytes()))
        self.assertIs(result['bytecode_disabled'], True)

    def test_foreign_controller_is_rejected_without_a_process(self):
        foreign = self.root / 'foreign-python'
        foreign.write_bytes(b'fixture-only foreign interpreter; never executed\n')
        with mock.patch.object(self.producer.sys, 'executable', str(foreign)), \
                mock.patch.object(self.producer.sys, 'dont_write_bytecode', True), \
                mock.patch.object(self.producer.process_tree, 'launch',
                                  side_effect=AssertionError('controller check launched a process')), \
                self.assertRaisesRegex(ValueError, 'admitted host Python'):
            self.producer._controller_python(self.inspection)

    def test_bytecode_enabled_controller_is_rejected_without_a_process(self):
        with mock.patch.object(self.producer.sys, 'executable', str(self.python)), \
                mock.patch.object(self.producer.sys, 'dont_write_bytecode', False), \
                mock.patch.object(self.producer.process_tree, 'launch',
                                  side_effect=AssertionError('controller check launched a process')), \
                self.assertRaisesRegex(ValueError, 'PYTHONDONTWRITEBYTECODE=1'):
            self.producer._controller_python(self.inspection)


class PlanPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-plan-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / 'retained-fixture'
        self.inputs.mkdir()
        self.selection = self.inputs / 'selection.json'
        self.selection.write_bytes(encoded({'fixture_only': True}))
        self.selection_pin = sha(self.selection.read_bytes())
        self.inspection = FakeInspection(self.selection)
        self.output = self.root / 'new-plan'

    def inspect(self):
        return mock.patch.object(self.producer.native_inputs, 'inspect_selection',
                                 return_value=self.inspection)

    def create(self):
        return self.producer.create_plan(self.selection, self.selection_pin, self.output,
                                         repository_root=ROOT)

    def test_passive_plan_publishes_canonical_ineligible_bytes_without_a_process(self):
        with self.inspect() as inspect, mock.patch.object(self.producer.process_tree, 'launch',
                side_effect=AssertionError('plan executed a process')) as launch:
            plan = self.create()
        inspect.assert_called_once_with(self.selection, self.selection_pin, repository_root=ROOT)
        launch.assert_not_called()
        self.assertEqual(self.inspection.rechecks, 1)
        self.assertEqual((self.output / 'plan.json').read_bytes(), self.producer.encoded(plan))
        self.assertEqual(set(plan), self.producer.PLAN_FIELDS)
        for name in ('production_eligible', 'engine_execution', 'kernel_rebuild'):
            self.assertIs(plan[name], False)

    def test_missing_admission_writes_no_runnable_plan_or_output_directory(self):
        with mock.patch.object(self.producer.native_inputs, 'inspect_selection',
                               side_effect=ValueError('missing complete supplier fixture')):
            with self.assertRaisesRegex(ValueError, 'missing complete supplier'):
                self.create()
        self.assertFalse(self.output.exists())

    def test_changed_input_recheck_precedes_output_creation(self):
        self.selection.write_bytes(encoded({'fixture_only': True, 'changed': True}))
        with self.inspect(), self.assertRaisesRegex(ValueError, 'input bytes changed'):
            self.create()
        self.assertFalse(self.output.exists())

    def test_existing_output_and_foreign_files_are_preserved(self):
        self.output.mkdir()
        foreign = self.output / 'foreign'
        foreign.write_bytes(b'preserve exact prior evidence')
        with self.inspect(), self.assertRaisesRegex(ValueError, 'fresh'):
            self.create()
        self.assertEqual(foreign.read_bytes(), b'preserve exact prior evidence')

    def test_output_may_not_overlap_the_retained_fixture(self):
        self.output = self.inputs / 'new-plan'
        with self.inspect(), self.assertRaisesRegex(ValueError, 'overlap'):
            self.create()
        self.assertFalse(self.output.exists())

    def test_verification_rechecks_original_admission_without_rewriting_plan(self):
        with self.inspect():
            plan = self.create()
            path = self.output / 'plan.json'
            original = path.read_bytes()
            verified, inspection = self.producer.verify_plan(path, sha(original), repository_root=ROOT)
        self.assertEqual(verified, plan)
        self.assertIs(inspection, self.inspection)
        self.assertEqual(self.inspection.rechecks, 2)
        self.assertEqual(path.read_bytes(), original)

    def test_wrong_plan_pin_denies_before_reopening_input_admission(self):
        with self.inspect():
            self.create()
        with self.inspect() as inspect, self.assertRaisesRegex(ValueError, 'independent pin'):
            self.producer.verify_plan(self.output / 'plan.json', '1' * 64, repository_root=ROOT)
        inspect.assert_not_called()

    def test_changed_inspection_does_not_upgrade_an_earlier_plan(self):
        with self.inspect():
            self.create()
            path = self.output / 'plan.json'
            original = path.read_bytes()
            self.inspection.facts['changed_inventory'] = True
            with self.assertRaisesRegex(ValueError, 'original plan inputs changed'):
                self.producer.verify_plan(path, sha(original), repository_root=ROOT)
        self.assertEqual(path.read_bytes(), original)

    def test_reencoded_or_extended_plan_is_not_original_even_with_its_new_pin(self):
        with self.inspect():
            original_plan = self.create()
        for mode in ('compact', 'extra', 'eligible', 'boolean-version'):
            with self.subTest(mode=mode):
                plan = json.loads(json.dumps(original_plan))
                if mode == 'extra':
                    plan['unreviewed'] = True
                elif mode == 'eligible':
                    plan['production_eligible'] = True
                elif mode == 'boolean-version':
                    plan['schema_version'] = True
                raw = (json.dumps(plan).encode('ascii') if mode == 'compact' else encoded(plan))
                path = self.root / ('changed-plan-' + mode + '.json')
                path.write_bytes(raw)
                with self.inspect() as inspect, self.assertRaisesRegex(ValueError, 'original canonical'):
                    self.producer.verify_plan(path, sha(raw), repository_root=ROOT)
                inspect.assert_not_called()


class DocumentInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-json-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / 'input.json'

    def test_owned_document_pin_is_checked_against_actual_bytes(self):
        raw = encoded({'fixture_only': True, 'value': 'portable'})
        self.path.write_bytes(raw)
        self.assertEqual(self.producer.read_document(self.path, sha(raw)),
                         {'fixture_only': True, 'value': 'portable'})
        self.path.write_bytes(encoded({'fixture_only': True, 'value': 'changed'}))
        with self.assertRaisesRegex(ValueError, 'independent pin'):
            self.producer.read_document(self.path, sha(raw))

    def test_duplicate_nonfinite_and_invalid_utf8_json_are_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'{"x":"\xff"}'):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.producer.read_document(self.path)

    def test_escaped_unpaired_unicode_is_not_a_utf8_string(self):
        self.path.write_bytes(b'{"nested":[{"text":"\\ud800"}]}')
        with self.assertRaises(ValueError):
            self.producer.read_document(self.path)

    def test_symlink_and_hardlink_inputs_are_not_ordinary_documents(self):
        self.path.write_bytes(encoded({'fixture_only': True}))
        symbolic = self.root / 'symbolic.json'
        symbolic.symlink_to(self.path)
        with self.assertRaises(ValueError):
            self.producer.read_document(symbolic)
        hard = self.root / 'hard.json'
        os.link(self.path, hard)
        with self.assertRaises(ValueError):
            self.producer.read_document(hard)

    def test_document_size_bound_is_checked_before_json_decode(self):
        with self.path.open('wb') as stream:
            stream.truncate(self.producer.MAX_DOCUMENT + 1)
        with self.assertRaisesRegex(ValueError, '32 MiB'):
            self.producer.read_document(self.path)


class FakeOwner:
    """Protocol-only qualified-owner double; starts no child process."""
    def __init__(self, *, running=False, code=0, finish_error=None, cleanup_error=None):
        self.process = SimpleNamespace(pid=123456)
        self.running, self.code = running, code
        self.finish_error, self.cleanup_error = finish_error, cleanup_error
        self.closed = False
        self.terminated = []
        self.finished = False
        self.stream = None

    def poll(self):
        return None if self.running else self.code

    def finish(self):
        self.finished = True
        if self.finish_error:
            raise self.finish_error
        return self.code

    def terminate(self, *, timeout):
        self.terminated.append(timeout)
        if self.cleanup_error:
            raise self.cleanup_error
        self.running = False

    def close(self):
        if self.stream is not None and not self.stream.closed:
            raise AssertionError('owner was closed before its output stream')
        self.closed = True


class OwnedStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-owner-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.log = self.root / 'stage.log'
        self.now = 0.0

    def sleep(self, seconds):
        self.now += seconds

    def run_stage(self, owner, *, samples=None, phase='configure', clock=None):
        def launch(argv, cwd, stream, *, env):
            self.assertEqual(argv, ['/fixture-only/cmake', 'fixture-argument'])
            self.assertEqual(cwd, self.root)
            self.assertEqual(env, {'FIXTURE_ONLY': '1'})
            owner.stream = stream
            stream.write(b'fixture stage output\n')
            return owner
        with mock.patch.object(self.producer.process_tree, 'launch', side_effect=launch), \
                mock.patch.object(self.producer, '_resources', side_effect=samples,
                                  return_value=HEALTHY), \
                mock.patch.object(self.producer.time, 'monotonic', side_effect=clock or (lambda: self.now)), \
                mock.patch.object(self.producer.time, 'sleep', side_effect=self.sleep):
            return self.producer.run_owned(['/fixture-only/cmake', 'fixture-argument'], self.root,
                self.log, {'FIXTURE_ONLY': '1'}, LIMITS, phase=phase, resource_root=self.root)

    def test_completed_owner_is_joined_and_log_closed_before_receipt(self):
        owner = FakeOwner()
        receipt = self.run_stage(owner)
        self.assertEqual(receipt['returncode'], 0)
        self.assertTrue(owner.finished)
        self.assertTrue(owner.closed)
        self.assertTrue(owner.stream.closed)
        self.assertEqual(owner.terminated, [])
        self.assertTrue(receipt['process_tree_closed'])

    def test_nonzero_exit_is_not_a_completed_success(self):
        owner = FakeOwner(code=7)
        with self.assertRaisesRegex(ValueError, 'exited 7'):
            self.run_stage(owner)
        self.assertTrue(owner.closed)
        self.assertTrue(owner.stream.closed)
        self.assertEqual(owner.terminated, [LIMITS['cleanup_seconds']])

    def test_timeout_terminates_and_joins_the_owned_tree(self):
        owner = FakeOwner(running=True)
        with self.assertRaisesRegex(ValueError, 'deadline'):
            self.run_stage(owner)
        self.assertEqual(owner.terminated, [LIMITS['cleanup_seconds']])
        self.assertTrue(owner.closed)
        self.assertTrue(owner.stream.closed)

    def test_zero_first_observed_after_deadline_is_not_success(self):
        owner = FakeOwner()
        def late_poll():
            self.now = LIMITS['configure_seconds'] + 0.01
            return 0
        with mock.patch.object(owner, 'poll', side_effect=late_poll):
            with self.assertRaisesRegex(ValueError, 'wall deadline'):
                self.run_stage(owner)
        receipt = json.loads(self.log.with_suffix('.stage.json').read_text())
        self.assertEqual(receipt['status'], 'incomplete')
        self.assertEqual(receipt['returncode'], 0)
        self.assertTrue(receipt['process_tree_closed'])
        self.assertEqual(owner.terminated, [LIMITS['cleanup_seconds']])

    def test_finish_cannot_turn_late_zero_into_success(self):
        owner = FakeOwner()
        original = owner.finish
        def late_finish():
            self.now = LIMITS['configure_seconds'] + 0.01
            return original()
        with mock.patch.object(owner, 'finish', side_effect=late_finish):
            with self.assertRaisesRegex(ValueError, 'wall deadline'):
                self.run_stage(owner)
        self.assertTrue(owner.closed)
        self.assertEqual(owner.terminated, [LIMITS['cleanup_seconds']])

    def test_close_and_final_resource_sample_share_the_work_deadline(self):
        for late_stage in ('close', 'resource'):
            with self.subTest(late_stage=late_stage):
                self.now = 0.0
                self.log = self.root / (late_stage + '.log')
                owner = FakeOwner()
                original = owner.close
                def close():
                    original()
                    if late_stage == 'close':
                        self.now = LIMITS['configure_seconds'] + 0.01
                calls = 0
                def resources(*unused):
                    nonlocal calls
                    calls += 1
                    if late_stage == 'resource' and calls == 2:
                        self.now = LIMITS['configure_seconds'] + 0.01
                    return HEALTHY
                with mock.patch.object(owner, 'close', side_effect=close):
                    with self.assertRaisesRegex(ValueError, 'wall deadline'):
                        self.run_stage(owner, samples=resources)
                receipt = json.loads(self.log.with_suffix('.stage.json').read_text())
                self.assertEqual(receipt['status'], 'incomplete')
                self.assertTrue(owner.closed)
                self.assertEqual(owner.terminated, [], 'closed owner must not be terminated again')

    def test_receipt_uses_the_final_checked_elapsed_without_resampling(self):
        clock = mock.Mock(side_effect=[0.0, 0.25, 0.5, 0.75, 1.25])
        receipt = self.run_stage(FakeOwner(), clock=clock)
        self.assertEqual(receipt['status'], 'passed')
        self.assertEqual(receipt['wall_seconds'], 0.75)
        self.assertLess(receipt['wall_seconds'], LIMITS['configure_seconds'])
        self.assertEqual(clock.call_count, 4)

    def test_each_live_resource_limit_stops_the_same_owner(self):
        bad = ({**HEALTHY, 'output_bytes': LIMITS['maximum_output_bytes'] + 1},
               {**HEALTHY, 'free_bytes': 0},
               {**HEALTHY, 'process_tree_bytes': LIMITS['maximum_process_tree_bytes'] + 1})
        for index, sample in enumerate(bad):
            with self.subTest(sample=sample):
                self.log = self.root / ('stage-' + str(index) + '.log')
                owner = FakeOwner(running=True)
                with self.assertRaises(ValueError):
                    self.run_stage(owner, samples=[HEALTHY, sample])
                self.assertEqual(owner.terminated, [LIMITS['cleanup_seconds']])
                self.assertTrue(owner.closed)

    def test_resource_preflight_denies_before_process_launch(self):
        with mock.patch.object(self.producer, '_resources', return_value={**HEALTHY, 'free_bytes': 0}), \
                mock.patch.object(self.producer.process_tree, 'launch') as launch:
            with self.assertRaisesRegex(ValueError, 'disk reserve'):
                self.producer.run_owned(['/fixture-only/cmake'], self.root, self.log, {}, LIMITS,
                                        phase='configure', resource_root=self.root)
        launch.assert_not_called()
        self.assertFalse(self.log.exists())

    def test_outliving_descendant_report_is_not_ignored(self):
        owner = FakeOwner(finish_error=self.producer.process_tree.ProcessTreeError('fixture descendant outlived'))
        with self.assertRaisesRegex(self.producer.process_tree.ProcessTreeError, 'descendant outlived'):
            self.run_stage(owner)
        self.assertEqual(owner.terminated, [LIMITS['cleanup_seconds']])
        self.assertTrue(owner.closed)

    def test_uncertain_cleanup_propagates_as_ownership_error(self):
        owner = FakeOwner(code=7, cleanup_error=RuntimeError('fixture cleanup unknown'))
        with self.assertRaisesRegex(self.producer.process_tree.ProcessTreeError, 'retain output ownership'):
            self.run_stage(owner)
        self.assertTrue(owner.stream.closed)
        self.assertEqual(owner.terminated, [LIMITS['cleanup_seconds']])
        self.assertFalse(owner.closed, 'uncertain ownership must not retry close with another budget')

    def test_foreign_log_is_never_truncated(self):
        self.log.write_bytes(b'preserve prior stage log')
        owner = FakeOwner()
        with self.assertRaises(FileExistsError):
            self.run_stage(owner)
        self.assertEqual(self.log.read_bytes(), b'preserve prior stage log')
        self.assertIsNone(owner.stream)


class BuildControlFixtureTests(unittest.TestCase):
    """Mock admission/assembly/stages; validates orchestration, never native code."""
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-build-control-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        inputs = self.root / 'fixture-inputs'
        inputs.mkdir()
        self.selection = inputs / 'selection.json'
        self.selection.write_bytes(encoded({'fixture_only': True}))
        self.inspection = FakeInspection(self.selection)
        self.inspection.programs = {
            'python': {'path': '/fixture-only/python'},
            'cmake': {'path': '/fixture-only/cmake'},
        }
        self.inspection.environment = {'PATH': '/fixture-only', 'FIXTURE_ONLY': '1'}
        with mock.patch.object(self.producer.native_inputs, 'inspect_selection',
                               return_value=self.inspection):
            self.producer.create_plan(self.selection, sha(self.selection.read_bytes()),
                                      self.root / 'plan', repository_root=ROOT)
        self.plan = self.root / 'plan/plan.json'
        self.plan_pin = sha(self.plan.read_bytes())
        self.calls = []
        self.prepared = None
        self.fixture_time = 10.0

    def assemble(self, inspection, output):
        self.assertIs(inspection, self.inspection)
        retained, assembled = output / 'retained', output / 'assembled'
        (retained / 'source/native/runtime').mkdir(parents=True)
        (retained / (str(RECIPE.relative_to(ROOT)) + '/producer')).mkdir(parents=True)
        (retained / 'source/native/runtime/generate_native_actions_metadata.py').write_text(
            '# fixture only; never executed\n')
        (retained / RECIPE.relative_to(ROOT) / 'producer/native-initial-cache.cmake').write_bytes(
            CACHE.read_bytes())
        (assembled / 'source/engine').mkdir(parents=True)
        (assembled / 'source/engine/CMakeLists.txt').write_text('# fixture only; never configured\n')
        original_build = output / 'provider-build.json'
        original_build.write_bytes(encoded({'fixture_only': True}))
        facts = {'retained_root': str(retained), 'assembled_root': str(assembled),
                 'recipe_sha256': '2' * 64, 'sources_sha256': '3' * 64,
                 'provider_build_path': str(original_build),
                 'provider_build_sha256': sha(original_build.read_bytes()), 'fixture_only': True}
        tokens = {token.decode('ascii') for token in re.findall(
            rb'@([A-Za-z_][A-Za-z0-9_]*)@', CACHE.read_bytes())}
        values = {token: str(output / 'fixture-only' / token) for token in tokens}
        self.prepared = SimpleNamespace(cmake=values, as_dict=lambda: dict(facts))
        self.fixture_time += 0.25
        return self.prepared

    def stage(self, argv, cwd, log_path, environment, limits, *, phase, resource_root):
        self.calls.append((phase, list(argv)))
        Path(log_path).write_text('fixture only: no command executed\n')
        self.assertEqual(environment['FIXTURE_ONLY'], '1')
        if phase == 'metadata':
            self.assertAlmostEqual(limits['prepare_seconds'], LIMITS['prepare_seconds'] - 0.25)
            self.assertEqual({key: value for key, value in limits.items() if key != 'prepare_seconds'},
                             {key: value for key, value in LIMITS.items() if key != 'prepare_seconds'})
        else:
            self.assertEqual(limits, LIMITS)
        if phase == 'metadata':
            (resource_root / 'cmake/generated/BibNativeProviderActionsMetadata.generated.h').write_text(
                '// fixture only, not genuine native R/B metadata\n')
        elif phase == 'build':
            receipt = {'schema_version': 1,
                       'kind': 'foundation-native-engine-prototype-inspection-v1',
                       'scope': 'fixture-only-orchestration-no-artifact-inspected',
                       'private_runtime_policy_sha256': self.producer.PRIVATE_RUNTIME_POLICY_SHA256,
                       'production_eligible': False, 'engine_execution': False,
                       'kernel_rebuild': False, 'fixture_only': True}
            (resource_root / 'cmake/evidence/provider-inspection.json').write_bytes(encoded(receipt))
        return {'phase': phase, 'returncode': 0, 'process_tree_closed': True,
                'fixture_only': True}

    def execute(self, output, *, assembly=None, stage=None, controller=None, runtime_link=None):
        with mock.patch.object(self.producer.native_inputs, 'inspect_selection',
                               return_value=self.inspection), \
                mock.patch.object(self.producer, '_controller_python', side_effect=controller,
                                  return_value={'fixture_only': True, 'bytecode_disabled': True}), \
                mock.patch.object(self.producer.native_inputs, 'assemble',
                                  side_effect=assembly or self.assemble), \
                mock.patch.object(self.producer, 'run_owned', side_effect=stage or self.stage), \
                mock.patch.object(self.producer, '_write_graph',
                                  side_effect=lambda inspection, prepared, *args: dict(prepared.cmake)), \
                mock.patch.object(self.producer, 'verify_private_runtime_link',
                                  side_effect=runtime_link, return_value={'fixture_only': True}), \
                mock.patch.object(self.producer, '_resources', return_value=HEALTHY), \
                mock.patch.object(self.producer.time, 'monotonic',
                                  side_effect=lambda: self.fixture_time), \
                mock.patch.object(self.producer.process_tree, 'launch',
                                  side_effect=AssertionError('fixture escaped to a real process')):
            return self.producer.build(self.plan, self.plan_pin, output, repository_root=ROOT)

    def test_controller_rejection_precedes_output_assembly_and_all_stages(self):
        output = self.root / 'foreign-controller'
        with self.assertRaisesRegex(ValueError, 'fixture controller rejected'):
            self.execute(output, controller=ValueError('fixture controller rejected'))
        self.assertFalse(output.exists())
        self.assertIsNone(self.prepared)
        self.assertEqual(self.calls, [])

    def test_mock_graph_uses_engine_root_and_only_named_cmake_target(self):
        output = self.root / 'build'
        result = self.execute(output)
        self.assertEqual([phase for phase, _ in self.calls], ['metadata', 'configure', 'build'])
        configure = self.calls[1][1]
        self.assertEqual(configure[0], '/fixture-only/cmake')
        self.assertEqual(configure[configure.index('-S') + 1],
                         str(output / 'prepared/assembled/source/engine'))
        self.assertEqual(configure[configure.index('-B') + 1], str(output / 'cmake'))
        self.assertIn('-C', configure)
        self.assertEqual(self.calls[2][1], ['/fixture-only/cmake', '--build', str(output / 'cmake'),
                                         '--target', 'BibNativeProvider', '--parallel', '2'])
        self.assertEqual(result['status'], 'linked-candidate')
        self.assertTrue(all(stage['fixture_only'] for stage in result['stages']))
        for name in ('production_eligible', 'engine_execution', 'kernel_rebuild'):
            self.assertIs(result[name], False)

    def test_previous_inspection_without_private_policy_is_not_reused(self):
        output = self.root / 'old-inspection'
        def old_inspection(*args, **kwargs):
            result = self.stage(*args, **kwargs)
            if kwargs['phase'] == 'build':
                path = output / 'cmake/evidence/provider-inspection.json'
                value = json.loads(path.read_bytes())
                del value['private_runtime_policy_sha256']
                path.write_bytes(encoded(value))
            return result
        with self.assertRaisesRegex(ValueError, 'original native candidate byte inspection'):
            self.execute(output, stage=old_inspection)
        self.assertFalse((output / 'native-prototype-build.json').exists())

    def test_private_runtime_input_failure_prevents_candidate_publication(self):
        output = self.root / 'bad-runtime-inputs'
        with self.assertRaisesRegex(ValueError, 'fixture runtime input mismatch'):
            self.execute(output, runtime_link=ValueError('fixture runtime input mismatch'))
        self.assertFalse((output / 'native-prototype-build.json').exists())
        receipt = json.loads((output / 'native-prototype-failure.json').read_bytes())
        self.assertEqual(receipt['phase'], 'build')
        self.assertEqual(len(receipt['completed_stages']), 3)

    def test_assembly_failure_preserves_original_plan_and_phase_without_a_stage(self):
        output = self.root / 'failed-prepare'
        def failed(*args):
            raise ValueError('fixture source projection incomplete')
        with self.assertRaisesRegex(ValueError, 'projection incomplete'):
            self.execute(output, assembly=failed)
        failure = json.loads((output / 'native-prototype-failure.json').read_bytes())
        self.assertEqual(failure['phase'], 'prepare')
        self.assertEqual(failure['completed_stages'], [])
        self.assertEqual((output / 'evidence/original-plan.json').read_bytes(), self.plan.read_bytes())
        self.assertFalse((output / 'native-prototype-build.json').exists())
        self.assertEqual(self.calls, [])

    def test_each_stage_failure_keeps_only_actual_prior_completions(self):
        for failed_phase, prior in (('metadata', 0), ('configure', 1), ('build', 2)):
            with self.subTest(phase=failed_phase):
                self.calls = []
                output = self.root / ('failed-' + failed_phase)
                def failed(argv, cwd, log_path, environment, limits, *, phase, resource_root):
                    if phase == failed_phase:
                        self.calls.append((phase, list(argv)))
                        raise ValueError('fixture failed ' + phase)
                    return self.stage(argv, cwd, log_path, environment, limits,
                                      phase=phase, resource_root=resource_root)
                with self.assertRaisesRegex(ValueError, 'fixture failed ' + failed_phase):
                    self.execute(output, stage=failed)
                failure = json.loads((output / 'native-prototype-failure.json').read_bytes())
                self.assertEqual(failure['phase'], failed_phase)
                self.assertEqual(len(failure['completed_stages']), prior)
                self.assertFalse((output / 'native-prototype-build.json').exists())
                self.assertEqual(self.calls[-1][0], failed_phase)

    def test_uncertain_process_cleanup_is_not_reported_closed(self):
        output = self.root / 'uncertain'
        def uncertain(*args, **kwargs):
            raise self.producer.process_tree.ProcessTreeError('fixture ownership uncertain')
        with self.assertRaisesRegex(self.producer.process_tree.ProcessTreeError, 'ownership uncertain'):
            self.execute(output, stage=uncertain)
        failure = json.loads((output / 'native-prototype-failure.json').read_bytes())
        self.assertIs(failure['process_ownership_confirmed'], False)
        self.assertIs(failure['engine_execution'], False)

    def test_existing_build_root_precedes_assembly_and_keeps_prior_evidence(self):
        output = self.root / 'existing'
        output.mkdir()
        prior = output / 'prior'
        prior.write_bytes(b'original prior evidence')
        with self.assertRaisesRegex(ValueError, 'fresh'):
            self.execute(output)
        self.assertEqual(prior.read_bytes(), b'original prior evidence')
        self.assertEqual(self.calls, [])


class SharedCliFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def arguments(self):
        return ['plan', '--selection', '/fixture-only/selection.json',
                '--selection-sha256', '1' * 64, '--output', '/fixture-only/new-plan']

    def test_missing_inputs_are_json_status_two_without_a_process(self):
        error = self.producer.native_inputs.MissingInputs([
            {'role': 'complete-supplier', 'path': '/fixture-only/missing', 'reason': 'absent'}])
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(self.producer, 'create_plan', side_effect=error), \
                mock.patch.object(self.producer.process_tree, 'launch') as launch, \
                redirect_stdout(stdout), redirect_stderr(stderr):
            status = self.producer.cli(self.arguments())
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), '')
        value = json.loads(stderr.getvalue())
        self.assertIs(value['executable_plan'], False)
        self.assertEqual(value['missing'][0]['role'], 'complete-supplier')
        launch.assert_not_called()

    def test_source_or_owned_process_error_is_status_one(self):
        for error in (ValueError('fixture invalid'), OSError('fixture missing'),
                      self.producer.process_tree.ProcessTreeError('fixture unclosed')):
            with self.subTest(error=error):
                stdout, stderr = io.StringIO(), io.StringIO()
                with mock.patch.object(self.producer, 'create_plan', side_effect=error), \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    self.assertEqual(self.producer.cli(self.arguments()), 1)
                self.assertEqual(stdout.getvalue(), '')
                self.assertIn(str(error), stderr.getvalue())


class ImportedInterfaceFixtureTests(unittest.TestCase):
    """Production guard prefix in a tiny LANGUAGES NONE project, never WebKit."""
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-interface-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.retained = self.root / 'retained-fixture'
        verifier = self.retained / RECIPE.relative_to(ROOT) / 'producer/verify-provider.cmake'
        verifier.parent.mkdir(parents=True)
        verifier.write_bytes(VERIFY.read_bytes())
        self.runtime_helper = verifier.with_name('native-private-runtime.cmake')
        self.runtime_helper.write_bytes((RECIPE / 'producer/native-private-runtime.cmake').read_bytes())
        self.include = self.root / 'prefix/include'
        self.include.mkdir(parents=True)
        self.libraries = {}
        for index, name in enumerate(('Freetype::Freetype', 'FoundationNative::nghttp2',
                                      'WebP::sharpyuv', 'Brotli::dec', 'Brotli::common')):
            archive = self.root / ('prefix/fixture-' + str(index) + '.a')
            archive.write_bytes(b'fixture-only non-archive bytes; never linked')
            self.libraries[name] = {'archive': str(archive), 'includes': [],
                                    'definitions': [], 'links': []}
        self.libraries['Freetype::Freetype'].update({
            'includes': [str(self.include)], 'definitions': ['FIXTURE_NATIVE=1'],
            'links': ['FoundationNative::nghttp2']})
        self.original = self.retained / 'fixture-dependencies.cmake'
        self.extra = ''
        self.incoming_link = '$<LINK_ONLY:fixtureNghttp2>'
        self.raw_override = None
        self.inspection = SimpleNamespace(
            as_dict=lambda: {'dependencies': {'libraries': self.libraries}},
            programs={'inspect': {'path': '/fixture-only/not-executed-inspector', 'sha256': '1' * 64},
                      'cmake': {'path': str(CMAKE)}},
            needed_libraries=['libc.so.6'], phase_limits=dict(LIMITS))
        self.prepared = SimpleNamespace(
            cmake={'BIB_NATIVE_EMBEDDER_CMAKE': str(self.original)},
            as_dict=lambda: {'retained_root': str(self.retained)})

    def run_fixture(self):
        nghttp2 = self.libraries['FoundationNative::nghttp2']['archive']
        main = self.libraries['Freetype::Freetype']['archive']
        source = [
            'add_library(fixtureNghttp2 STATIC IMPORTED GLOBAL)\n',
            'add_library(FoundationNative::nghttp2 ALIAS fixtureNghttp2)\n',
            'set_property(TARGET fixtureNghttp2 PROPERTY IMPORTED_LOCATION "' + nghttp2 + '")\n',
            'add_library(fixtureFreetype STATIC IMPORTED GLOBAL)\n',
            'add_library(Freetype::Freetype ALIAS fixtureFreetype)\n',
            'set_property(TARGET fixtureFreetype PROPERTY IMPORTED_LOCATION "' + main + '")\n',
            'set_property(TARGET fixtureFreetype PROPERTY INTERFACE_INCLUDE_DIRECTORIES "' + str(self.include) + '")\n',
            'set_property(TARGET fixtureFreetype PROPERTY INTERFACE_COMPILE_DEFINITIONS FIXTURE_NATIVE=1)\n',
            'set_property(TARGET fixtureFreetype PROPERTY INTERFACE_LINK_LIBRARIES "' + self.incoming_link + '")\n',
        ]
        for variable, name in (('NGHTTP2_LIBRARY', 'FoundationNative::nghttp2'),
                               ('BROTLIDEC_LIBRARY', 'Brotli::dec'),
                               ('BROTLICOMMON_LIBRARY', 'Brotli::common')):
            path = self.raw_override if variable == 'NGHTTP2_LIBRARY' and self.raw_override else self.libraries[name]['archive']
            source.append('set(' + variable + ' "' + path + '")\n')
        source.append(self.extra)
        self.original.write_text(''.join(source))
        generated = self.root / 'generated-production-guard.cmake'
        # This class isolates the actual imported-interface guard prefix. The
        # private runtime hook has its own record/link-evidence discriminators.
        with mock.patch.object(self.producer, '_runtime_values', return_value={}):
            values = self.producer._write_graph(self.inspection, self.prepared, self.root,
                                                self.root, generated)
        full = generated.read_bytes()
        marker = b'add_custom_command(TARGET BibNativeProvider POST_BUILD\n'
        self.assertEqual(full.count(marker), 1)
        runtime_marker = ('include(' + self.producer._literal(str(self.runtime_helper)) + ')\n').encode('ascii')
        self.assertEqual(full.count(runtime_marker), 1)
        prefix = full.split(runtime_marker, 1)[0]
        (self.root / 'fixture-only-prefix.cmake').write_bytes(prefix)
        driver = self.root / 'fixture-source'
        driver.mkdir()
        (driver / 'CMakeLists.txt').write_text(
            'cmake_minimum_required(VERSION 3.24)\n'
            'project(ExplicitImportedInterfaceFixture LANGUAGES NONE)\n'
            'include("' + str(self.root / 'fixture-only-prefix.cmake') + '")\n'
            'get_target_property(_links fixtureFreetype INTERFACE_LINK_LIBRARIES)\n'
            'file(WRITE "' + str(self.root / 'fixture-normalized-links.txt') + '" "${_links}")\n')
        # No build is invoked. The explicitly selected make-program value avoids
        # ambient build-tool discovery; LANGUAGES NONE enables no compiler.
        argv = [str(CMAKE), '-S', str(driver), '-B', str(self.root / 'fixture-build'),
                '-G', 'Unix Makefiles', '-DCMAKE_MAKE_PROGRAM=' + str(CMAKE)]
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=10, check=False)
        return result.returncode, result.stdout.decode('utf-8', 'replace'), values

    def reject(self, message):
        code, output, _ = self.run_fixture()
        self.assertNotEqual(code, 0, output)
        self.assertIn(message, ' '.join(output.split()))

    def test_admitted_alias_and_link_only_are_normalized(self):
        code, output, values = self.run_fixture()
        self.assertEqual(code, 0, output)
        self.assertEqual((self.root / 'fixture-normalized-links.txt').read_text(),
                         'FoundationNative::nghttp2')
        self.assertEqual(values['NGHTTP2_LIBRARY'], self.libraries['FoundationNative::nghttp2']['archive'])

    def test_foreign_header_path_is_rejected(self):
        foreign = self.root / 'foreign-include'
        foreign.mkdir()
        self.extra = 'set_property(TARGET fixtureFreetype APPEND PROPERTY INTERFACE_INCLUDE_DIRECTORIES "' + str(foreign) + '")\n'
        self.reject('header path escapes')

    def test_foreign_macro_is_rejected(self):
        self.extra = 'set_property(TARGET fixtureFreetype APPEND PROPERTY INTERFACE_COMPILE_DEFINITIONS UNREVIEWED=1)\n'
        self.reject('macro differs')

    def test_foreign_static_archive_cannot_enter_through_an_absolute_link(self):
        archive = self.root / 'foreign.a'
        archive.write_bytes(b'fixture only')
        self.incoming_link = str(archive)
        self.reject('static link escapes')

    def test_unreviewed_compiler_option_is_rejected(self):
        self.extra = 'set_property(TARGET fixtureFreetype APPEND PROPERTY INTERFACE_COMPILE_OPTIONS -march=native)\n'
        self.reject('options require an explicit reviewed policy')

    def test_raw_library_must_match_its_admitted_target_archive(self):
        archive = self.root / 'foreign-raw.a'
        archive.write_bytes(b'fixture only')
        self.raw_override = str(archive)
        self.reject('Raw native dependency differs')


class PrivateRuntimeLinkEvidenceTests(unittest.TestCase):
    """Synthetic linker text joins, not SDK body or actual link qualification."""
    @classmethod
    def setUpClass(cls):
        cls.producer = load_producer()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='private-runtime-evidence-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.trace, self.map = self.root / 'link.log', self.root / 'link.map'
        basenames = ('libstdc++.a', 'libgcc.a', 'libgcc_eh.a', 'crtbeginS.o', 'crtendS.o')
        self.paths = ['/synthetic-sdk/runtime/' + name for name in basenames]
        self.values = {'BIB_NATIVE_RUNTIME_' + role + '_PATH': path
            for role, path in zip(self.producer.RUNTIME_ROLES, self.paths)}
        self.values['BIB_NATIVE_RUNTIME_SELECTION_SHA256'] = '7' * 64
        self.trace.write_text(''.join(path + '\n' for path in self.paths))
        self.map.write_text(''.join('LOAD ' + path + '\n' for path in self.paths))

    def verify(self):
        return self.producer.verify_private_runtime_link(self.values, self.trace, self.map)

    def test_exact_five_inputs_join_both_original_streams(self):
        result = self.verify()
        self.assertEqual(result['selected_paths'], sorted(self.paths))
        self.assertEqual(result['selection_sha256'], '7' * 64)
        self.assertEqual(result['evidence']['linker_input_trace']['sha256'], sha(self.trace.read_bytes()))
        self.assertEqual(result['evidence']['linker_map']['sha256'], sha(self.map.read_bytes()))
        self.assertIs(result['production_eligible'], False)
        self.assertIs(result['engine_execution'], False)

    def test_missing_role_in_either_stream_is_not_inferred(self):
        for stream in (self.trace, self.map):
            with self.subTest(stream=stream.name):
                original = stream.read_bytes()
                stream.write_text(''.join(path + '\n' for path in self.paths[:-1]))
                with self.assertRaisesRegex(ValueError, 'lacks selected role'):
                    self.verify()
                stream.write_bytes(original)

    def test_foreign_static_runtime_is_rejected_instead_of_hash_inference(self):
        for name in ('libstdc++.a', 'libsupc++.a', 'libstdc++exp.a', 'libsupc++_nonshared.a',
                     'libc++.a', 'libc++abi.a', 'libc++experimental.a', 'libunwind.a',
                     'libunwind-llvm.a', 'crtbegin.o'):
            with self.subTest(name=name):
                original = self.map.read_bytes()
                with self.map.open('a') as output:
                    output.write('LOAD /ambient/runtime/' + name + '\n')
                with self.assertRaisesRegex(ValueError, 'undeclared runtime input'):
                    self.verify()
                self.map.write_bytes(original)

    def test_shared_cpp_and_unwind_paths_are_rejected(self):
        for name in ('libstdc++.so.6', 'libgcc_s.so.1', 'libsupc++.so.1',
                     'libc++.so.1', 'libc++abi.so.1', 'libunwind.so.1'):
            with self.subTest(name=name):
                original = self.trace.read_bytes()
                with self.trace.open('a') as output:
                    output.write('/ambient/runtime/' + name + '\n')
                with self.assertRaisesRegex(ValueError, 'shared C\\+\\+/unwind'):
                    self.verify()
                self.trace.write_bytes(original)

    def test_lexically_equivalent_driver_paths_join_the_selected_file(self):
        self.trace.write_text(''.join(path.replace('/runtime/', '/temporary/../runtime/') + '\n'
                                      for path in self.paths))
        self.assertEqual(self.verify()['selected_paths'], sorted(self.paths))

    def test_reusing_one_path_for_two_roles_is_invalid(self):
        self.values['BIB_NATIVE_RUNTIME_CRTENDS_PATH'] = self.paths[0]
        with self.assertRaisesRegex(ValueError, 'five distinct'):
            self.verify()

    def test_streaming_reader_detects_mid_read_mutation(self):
        iterator = self.producer._link_lines(self.trace, self.producer.time.monotonic() + 60)
        next(iterator)
        with self.trace.open('a') as output:
            output.write('changed after original stream opened\n')
        try:
            with self.assertRaisesRegex(ValueError, 'changed while reading'):
                list(iterator)
        finally:
            iterator.close()

    def test_oversized_line_and_sparse_file_are_denied(self):
        self.trace.write_bytes(b'x' * (1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, 'oversized line'):
            self.verify()
        with self.trace.open('wb') as output:
            output.truncate(self.producer.MAX_LINK_EVIDENCE + 1)
        with self.assertRaisesRegex(ValueError, '128 MiB'):
            self.verify()

    def test_link_evidence_has_one_bounded_deadline(self):
        with mock.patch.object(self.producer.time, 'monotonic', side_effect=[0.0, 61.0]):
            with self.assertRaisesRegex(ValueError, 'wall deadline'):
                self.verify()

    def test_eof_and_final_stat_cannot_finish_after_the_stream_deadline(self):
        # Five actual lines and the EOF read complete before the bound. The
        # final physical-identity observation finishes late and must reject.
        clock = mock.Mock(side_effect=[0.0] * 6 + [61.0])
        with mock.patch.object(self.producer.time, 'monotonic', clock):
            with self.assertRaisesRegex(ValueError, 'wall deadline'):
                list(self.producer._link_lines(self.map, 60.0))
        self.assertEqual(clock.call_count, 7)


FAKE_INSPECTOR = r'''#!@PYTHON@
"""Synthetic inspector for CMake-P fixtures; never loads an artifact."""
import json
from pathlib import Path
import sys

config = json.loads(Path(__file__).with_name('fixture-inspector.json').read_text())
artifact = Path(sys.argv[-1])
if config.get('exit'):
    print('synthetic inspector failure', file=sys.stderr)
    raise SystemExit(config['exit'])
if '--dyn-syms' in sys.argv:
    print(config['symbols'])
elif '--version-info' in sys.argv:
    print(config['versions'])
else:
    print(config['dynamic'])
    if config.get('mutate_artifact'):
        raw = bytearray(artifact.read_bytes())
        raw[-1] ^= 1
        artifact.write_bytes(raw)
if config.get('mutate_tool'):
    with Path(__file__).open('a') as stream:
        stream.write('\n# intentional fixture mutation\n')
'''


class CMakeInspectionFixture:
    """Owned tiny fake files; deliberately supplies no real ELF link proof."""
    def __init__(self, directory):
        self.root = Path(directory)
        self.build = self.root / 'private-build'
        self.evidence = self.build / 'fixture-evidence'
        self.evidence.mkdir(parents=True)
        self.artifact = self.build / 'fake-provider.so'
        header = bytearray(80)
        header[:7] = b'\x7fELF\x02\x01\x01'
        header[16:20] = b'\x03\x00\x3e\x00'
        self.artifact.write_bytes(header)
        self.tool = self.root / 'fake-inspector'
        self.tool.write_text(FAKE_INSPECTOR.replace('@PYTHON@', sys.executable))
        self.tool.chmod(0o700)
        self.config = {
            'symbols': '  1: 0000000000000010 16 FUNC GLOBAL DEFAULT 1 bib_engine_get_provider_v1\n'
                       '  2: 0000000000000000 0 FUNC GLOBAL DEFAULT UND abort\n',
            'dynamic': ' 0x0000000000000001 (NEEDED) Shared library: [libc.so.6]\n'
                       ' 0x000000000000001d (RUNPATH) Library runpath: [$ORIGIN]\n',
            'versions': 'No version information found in this file.\n',
        }
        self.allowed = ['libc.so.6']
        self.inspection_kind = None
        self.tool_pin = sha(self.tool.read_bytes())

    def run(self):
        self.tool.with_name('fixture-inspector.json').write_bytes(encoded(self.config))
        arguments = {
            'ARTIFACT': self.artifact,
            'BUILD_ROOT': self.build,
            'EVIDENCE': self.evidence,
            'INSPECT_TOOL': self.tool,
            'INSPECT_SHA256': self.tool_pin,
            'ALLOWED_NEEDED_JSON': json.dumps(self.allowed, separators=(',', ':')),
            'MAXIMUM_ARTIFACT_BYTES': 1024,
            'PRIVATE_RUNTIME_POLICY_SHA256': '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc',
        }
        if self.inspection_kind is not None:
            arguments['INSPECTION_KIND'] = self.inspection_kind
        argv = [str(CMAKE), *(f'-DBIB_NATIVE_PROTOTYPE_{key}={value}'
                             for key, value in arguments.items()), '-P', str(VERIFY)]
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=10, check=False)
        return result.returncode, result.stdout.decode('utf-8', 'replace')

    def receipt(self):
        return self.evidence / 'provider-inspection.json'


class InertCMakeInspectionTests(unittest.TestCase):
    """Only CMake-P and fake Python inspector run; no native program is loaded."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-prototype-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.fixture = CMakeInspectionFixture(self.temporary.name)

    def rejected(self, *messages):
        code, output = self.fixture.run()
        self.assertNotEqual(code, 0, output)
        self.assertFalse(self.fixture.receipt().exists(), output)
        for message in messages:
            self.assertIn(message, ' '.join(output.split()))

    def test_synthetic_inspection_records_bytes_without_engine_eligibility(self):
        code, output = self.fixture.run()
        self.assertEqual(code, 0, output)
        receipt = json.loads(self.fixture.receipt().read_bytes())
        self.assertEqual(receipt['artifact_sha256'], sha(self.fixture.artifact.read_bytes()))
        self.assertEqual(receipt['artifact_bytes'], 80)
        self.assertEqual(receipt['exports'], ['bib_engine_get_provider_v1'])
        self.assertEqual(receipt['needed'], ['libc.so.6'])
        self.assertEqual(receipt['private_runtime_policy_sha256'],
                         '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc')
        version_info = self.fixture.evidence / 'provider-version-info.txt'
        self.assertEqual(receipt['version_info_sha256'], sha(version_info.read_bytes()))
        for name in ('production_eligible', 'engine_execution', 'kernel_rebuild'):
            self.assertIs(receipt[name], False)

    def test_closed_dependency_diagnostic_changes_only_export_and_receipt_scope(self):
        self.fixture.inspection_kind = 'dependencies-pic-v1'
        self.fixture.config['symbols'] = self.fixture.config['symbols'].replace(
            'bib_engine_get_provider_v1', 'foundation_native_dependency_pic_probe')
        code, output = self.fixture.run()
        self.assertEqual(code, 0, output)
        receipt = json.loads(self.fixture.receipt().read_bytes())
        self.assertEqual(receipt['exports'], ['foundation_native_dependency_pic_probe'])
        self.assertEqual(receipt['kind'], 'foundation-native-dependencies-private-pic-inspection-v1')
        self.assertEqual(receipt['scope'], 'actual-linked-native-dependencies-private-pic-byte-inspection')
        self.assertEqual(receipt['private_runtime_policy_sha256'],
                         '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc')
        self.assertEqual(receipt['version_info_sha256'], sha(
            (self.fixture.evidence / 'provider-version-info.txt').read_bytes()))
        for name in ('production_eligible', 'engine_execution', 'kernel_rebuild'):
            self.assertIs(receipt[name], False)
        original = self.fixture.config['symbols']
        for index, symbols in enumerate((
                original.replace('foundation_native_dependency_pic_probe', 'bib_engine_get_provider_v1'),
                original + ' 3: 0 0 FUNC GLOBAL DEFAULT UND unexpected@GLIBCXX_3.4.30\n')):
            with self.subTest(index=index):
                self.fixture.evidence = self.fixture.build / ('diagnostic-negative-' + str(index))
                self.fixture.evidence.mkdir()
                self.fixture.config['symbols'] = symbols
                self.rejected()

    def test_unrecognized_inspection_kind_fails_before_any_inspector(self):
        self.fixture.inspection_kind = 'arbitrary-export-name'
        self.rejected('Unknown closed native private inspection kind')
        self.assertFalse((self.fixture.evidence / 'provider-dynamic-symbols.txt').exists())
        self.assertFalse((self.fixture.evidence / 'provider-version-info.txt').exists())

    def test_fixed_runtime_probe_has_its_own_export_and_inspection_scope(self):
        self.fixture.inspection_kind = 'runtime-probe-v1'
        self.fixture.config['symbols'] = self.fixture.config['symbols'].replace(
            'bib_engine_get_provider_v1', 'bib_native_runtime_probe_v1')
        self.fixture.config['symbols'] += (
            ' 3: 0 0 FUNC GLOBAL DEFAULT UND __cxa_finalize@GLIBC_2.2.5 (2)\n')
        self.fixture.config['versions'] = (
            "Version needs section '.gnu.version_r' contains 1 entry:\n"
            '  000000: Version: 1  File: libc.so.6  Cnt: 1\n'
            '  0x0010: Name: GLIBC_2.2.5  Flags: none  Version: 2\n')
        code, output = self.fixture.run()
        self.assertEqual(code, 0, output)
        receipt = json.loads(self.fixture.receipt().read_bytes())
        self.assertEqual(receipt['exports'], ['bib_native_runtime_probe_v1'])
        self.assertEqual(receipt['kind'], 'foundation-native-private-runtime-probe-inspection-v1')
        self.assertEqual(receipt['scope'], 'actual-linked-native-private-runtime-probe-byte-inspection')
        self.assertEqual(receipt['private_runtime_policy_sha256'],
                         '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc')
        self.assertEqual(receipt['version_info_sha256'], sha(
            (self.fixture.evidence / 'provider-version-info.txt').read_bytes()))
        for name in ('production_eligible', 'engine_execution', 'kernel_rebuild'):
            self.assertIs(receipt[name], False)

    def test_runtime_probe_cannot_borrow_another_export_or_dynamic_cpp_runtime(self):
        self.fixture.inspection_kind = 'runtime-probe-v1'
        original = self.fixture.config['symbols']
        cases = (
            (original, self.fixture.config['dynamic']),
            (original.replace('bib_engine_get_provider_v1', 'foundation_native_dependency_pic_probe'),
             self.fixture.config['dynamic']),
            (original.replace('bib_engine_get_provider_v1', 'bib_native_runtime_probe_v1')
             + ' 3: 0 0 FUNC GLOBAL DEFAULT UND __cxa_throw\n', self.fixture.config['dynamic']),
            (original.replace('bib_engine_get_provider_v1', 'bib_native_runtime_probe_v1')
             + ' 3: 0 0 FUNC GLOBAL DEFAULT UND unexpected@GLIBCXX_3.4.30\n', self.fixture.config['dynamic']),
            (original.replace('bib_engine_get_provider_v1', 'bib_native_runtime_probe_v1'),
             self.fixture.config['dynamic'] + ' 2 (NEEDED) Shared library: [libunwind.so.1]\n'),
        )
        for index, (symbols, dynamic) in enumerate(cases):
            with self.subTest(index=index):
                self.fixture.evidence = self.fixture.build / ('runtime-probe-negative-' + str(index))
                self.fixture.evidence.mkdir()
                self.fixture.config.update(symbols=symbols, dynamic=dynamic)
                self.fixture.allowed = ['libc.so.6', 'libunwind.so.1']
                self.rejected()

    def test_extra_defined_export_is_not_hidden_by_required_getter(self):
        self.fixture.config['symbols'] += ' 3: 0000000000000020 4 OBJECT GLOBAL DEFAULT 2 extra_export\n'
        self.rejected('exactly the one public getter', 'extra_export')

    def test_weak_defined_export_is_also_rejected(self):
        self.fixture.config['symbols'] += ' 3: 0000000000000020 4 FUNC WEAK DEFAULT 2 weak_export\n'
        self.rejected('weak_export')

    def test_gnu_unique_definition_is_an_extra_public_export(self):
        self.fixture.config['symbols'] += ' 3: 0000000000000020 4 OBJECT UNIQUE DEFAULT 2 unique_export\n'
        self.rejected('unique_export')

    def test_getter_object_symbol_is_not_a_callable_c_abi(self):
        self.fixture.config['symbols'] = self.fixture.config['symbols'].replace(
            '16 FUNC GLOBAL', '16 OBJECT GLOBAL')
        self.rejected('ordinary GLOBAL DEFAULT FUNC')

    def test_undefined_getter_is_not_a_provider_export(self):
        self.fixture.config['symbols'] = self.fixture.config['symbols'].replace('DEFAULT 1 ', 'DEFAULT UND ')
        self.rejected('exactly the one public getter')

    def test_versioned_getter_does_not_match_the_public_abi(self):
        self.fixture.config['symbols'] = self.fixture.config['symbols'].replace(
            'bib_engine_get_provider_v1', 'bib_engine_get_provider_v1@@UNREVIEWED')
        self.rejected('exactly the one public getter')

    def test_every_wrong_elf_identity_fails_before_inspector(self):
        original = self.fixture.artifact.read_bytes()
        for offset, replacement in ((0, 0), (4, 1), (5, 2), (16, 2), (18, 0x28)):
            with self.subTest(offset=offset):
                raw = bytearray(original)
                raw[offset] = replacement
                self.fixture.artifact.write_bytes(raw)
                self.rejected('actual little-endian ELF64 x86_64 shared object')
                self.assertFalse((self.fixture.evidence / 'provider-dynamic-symbols.txt').exists())

    def test_undeclared_actual_dependency_is_rejected(self):
        self.fixture.config['dynamic'] += ' 2 (NEEDED) Shared library: [libunreviewed.so.1]\n'
        self.rejected('undeclared actual dynamic dependency', 'libunreviewed.so.1')

    def test_even_an_allowlisted_shared_cpp_or_unwind_runtime_is_rejected(self):
        for index, name in enumerate(('libstdc++.so.6', 'libgcc_s.so.1', 'libsupc++.so.1',
                                      'libc++.so.1', 'libc++abi.so.1', 'libunwind.so.1')):
            with self.subTest(name=name):
                self.fixture.evidence = self.fixture.build / ('shared-runtime-' + str(index))
                self.fixture.evidence.mkdir()
                self.fixture.allowed = ['libc.so.6', name]
                self.fixture.config['dynamic'] = ' 1 (NEEDED) Shared library: [' + name + ']\n'
                self.rejected('shared C++/unwind runtime', name)

    def test_unversioned_cpp_and_unwind_imports_are_not_external_runtime_calls(self):
        original = self.fixture.config['symbols']
        symbols = ('_Znwm', '_Unwind_Resume', '__gxx_personality_v0', '__gcc_personality_v0',
                   '__dynamic_cast', '__cxa_throw', '__register_frame_info', '__deregister_frame')
        for index, name in enumerate(symbols):
            with self.subTest(name=name):
                self.fixture.evidence = self.fixture.build / ('undefined-runtime-' + str(index))
                self.fixture.evidence.mkdir()
                self.fixture.config['symbols'] = original + ' 3: 0 0 FUNC GLOBAL DEFAULT UND ' + name + '\n'
                self.rejected('unresolved C++/unwind import', name)

    def test_versioned_cpp_runtime_import_is_rejected_for_any_symbol_spelling(self):
        self.fixture.config['symbols'] += ' 3: 0 0 FUNC GLOBAL DEFAULT UND unexpected@GLIBCXX_3.4.30\n'
        self.rejected('unresolved versioned C++/unwind import')

    def test_explicit_glibc_cpp_abi_imports_remain_inside_glibc_baseline(self):
        self.fixture.config['symbols'] += (
            ' 3: 0 0 FUNC GLOBAL DEFAULT UND __cxa_finalize@GLIBC_2.2.5 (2)\n'
            ' 4: 0 0 FUNC GLOBAL DEFAULT UND __cxa_atexit@GLIBC_2.2.5 (2)\n'
            ' 5: 0 0 FUNC GLOBAL DEFAULT UND __cxa_thread_atexit_impl@GLIBC_2.18 (3)\n')
        self.fixture.config['versions'] = (
            "Version needs section '.gnu.version_r' contains 1 entry:\n"
            '  000000: Version: 1  File: libc.so.6  Cnt: 2\n'
            '  0x0010: Name: GLIBC_2.2.5  Flags: none  Version: 2\n'
            '  0x0020: Name: GLIBC_2.18  Flags: none  Version: 3\n')
        code, output = self.fixture.run()
        self.assertEqual(code, 0, output)
        self.assertTrue(self.fixture.receipt().exists())

    def test_libc_cpp_abi_imports_require_actual_matching_version_needs(self):
        original = self.fixture.config['symbols']
        valid = ("Version needs section '.gnu.version_r' contains 1 entry:\n"
                 '  000000: Version: 1  File: libc.so.6  Cnt: 1\n'
                 '  0x0010: Name: GLIBC_2.2.5  Flags: none  Version: 2\n')
        cases = {
            'missing-needs': 'No version information found in this file.\n',
            'foreign-provider': valid.replace('libc.so.6', 'libforeign.so.1'),
            'different-version': valid.replace('GLIBC_2.2.5', 'GLIBC_2.3'),
            'different-index': valid.replace('Version: 2', 'Version: 3'),
            'duplicate-index': valid.replace('Cnt: 1', 'Cnt: 2')
                + '  0x0020: Name: GLIBC_2.3  Flags: none  Version: 2\n',
            'provider-count': valid.replace('contains 1 entry', 'contains 2 entries'),
            'auxiliary-count': valid.replace('Cnt: 1', 'Cnt: 2'),
            'definition-only': valid.replace("needs section '.gnu.version_r'", "definition section '.gnu.version_d'"),
            'malformed-needs': valid.replace('Flags: none', 'unsupported-record: none'),
            'repeated-provider': valid.replace('contains 1 entry', 'contains 2 entries')
                + '  000030: Version: 1  File: libc.so.6  Cnt: 1\n'
                + '  0x0040: Name: GLIBC_2.3  Flags: none  Version: 3\n',
        }
        for index, (name, versions) in enumerate(cases.items()):
            with self.subTest(name=name):
                self.fixture.evidence = self.fixture.build / ('version-needs-' + str(index))
                self.fixture.evidence.mkdir()
                self.fixture.config['symbols'] = original + (
                    ' 3: 0 0 FUNC GLOBAL DEFAULT UND __cxa_finalize@GLIBC_2.2.5 (2)\n')
                self.fixture.config['versions'] = versions
                self.rejected()

    def test_libc_cpp_abi_imports_need_numeric_index_and_actual_libc_needed(self):
        self.fixture.config['versions'] = (
            "Version needs section '.gnu.version_r' contains 1 entry:\n"
            '  000000: Version: 1  File: libc.so.6  Cnt: 1\n'
            '  0x0010: Name: GLIBC_2.2.5  Flags: none  Version: 2\n')
        original = self.fixture.config['symbols']
        self.fixture.config['symbols'] = original + (
            ' 3: 0 0 FUNC GLOBAL DEFAULT UND __cxa_finalize@GLIBC_2.2.5\n')
        self.rejected()
        self.fixture.evidence = self.fixture.build / 'missing-libc-needed'
        self.fixture.evidence.mkdir()
        self.fixture.config['symbols'] = original + (
            ' 3: 0 0 FUNC GLOBAL DEFAULT UND __cxa_finalize@GLIBC_2.2.5 (2)\n')
        self.fixture.config['dynamic'] = self.fixture.config['dynamic'].replace('libc.so.6', 'libm.so.6')
        self.fixture.allowed = ['libm.so.6']
        self.rejected()

    def test_glibc_cpp_abi_exceptions_require_real_version_information(self):
        self.fixture.config['symbols'] += ' 3: 0 0 FUNC GLOBAL DEFAULT UND __cxa_finalize\n'
        self.rejected('unresolved C++/unwind import')

    def test_above_baseline_and_private_glibc_imports_are_rejected(self):
        original = self.fixture.config['symbols']
        for index, name in enumerate(('memcpy@GLIBC_2.38', 'function@GLIBC_PRIVATE')):
            with self.subTest(name=name):
                self.fixture.evidence = self.fixture.build / ('glibc-version-' + str(index))
                self.fixture.evidence.mkdir()
                self.fixture.config['symbols'] = original + ' 3: 0 0 FUNC GLOBAL DEFAULT UND ' + name + '\n'
                self.rejected('GLIBC version')

    def test_runtime_search_path_cannot_escape_private_origin(self):
        self.fixture.config['dynamic'] = self.fixture.config['dynamic'].replace('$ORIGIN', '/tmp/unreviewed')
        self.rejected('search path differs')

    def test_rpath_escape_is_rejected_as_well_as_runpath(self):
        self.fixture.config['dynamic'] = self.fixture.config['dynamic'].replace('RUNPATH', 'RPATH').replace(
            '$ORIGIN', '$ORIGIN/../unreviewed')
        self.rejected('search path differs')

    def test_text_relocations_are_not_a_pic_success(self):
        self.fixture.config['dynamic'] += ' 0x16 (TEXTREL) 0x0\n'
        self.rejected('dynamic text relocations')

    def test_missing_observed_needed_entries_is_not_inferred_static_success(self):
        self.fixture.config['dynamic'] = ' 0x1d (RUNPATH) Library runpath: [$ORIGIN]\n'
        self.rejected('no observed runtime dependency entries')

    def test_allowlist_cannot_be_empty_or_escape_as_a_path(self):
        for allowed in ([], ['/tmp/libunreviewed.so']):
            with self.subTest(allowed=allowed):
                # Each rejected inspection leaves useful evidence; use a fresh
                # owned evidence directory for the second independent attempt.
                self.fixture.evidence = self.fixture.build / ('allow-' + str(len(allowed)))
                self.fixture.evidence.mkdir()
                self.fixture.allowed = allowed
                self.rejected('allowlist')

    def test_tool_pin_mismatch_precedes_execution(self):
        self.fixture.tool_pin = '1' * 64
        self.rejected('tool changed from its independent pin')
        self.assertFalse((self.fixture.evidence / 'provider-dynamic-symbols.txt').exists())

    def test_tool_mutation_during_execution_is_not_relabelled_unchanged(self):
        self.fixture.config['mutate_tool'] = True
        self.rejected('changed during actual inspection')

    def test_artifact_mutation_during_execution_is_rejected(self):
        self.fixture.config['mutate_artifact'] = True
        self.rejected('changed during actual inspection')

    def test_prior_evidence_is_preserved(self):
        prior = self.fixture.evidence / 'provider-dynamic-symbols.txt'
        prior.write_text('foreign prior evidence\n')
        self.rejected('refuses to overwrite prior evidence')
        self.assertEqual(prior.read_text(), 'foreign prior evidence\n')

    def test_evidence_outside_build_tree_is_rejected_before_execution(self):
        self.fixture.evidence = self.fixture.root / 'outside'
        self.fixture.evidence.mkdir()
        self.rejected('escapes the private CMake tree')

    def test_failed_inspector_is_recorded_without_success_receipt(self):
        self.fixture.config['exit'] = 3
        self.rejected('dynamic-symbol inspection failed')
        self.assertIn('synthetic inspector failure',
                      (self.fixture.evidence / 'provider-inspection-stderr.txt').read_text())

    def test_inspector_output_is_bounded(self):
        self.fixture.config['symbols'] = 'x' * (4194304 + 1)
        self.rejected('4 MiB per-file bound')


if __name__ == '__main__':
    unittest.main()
