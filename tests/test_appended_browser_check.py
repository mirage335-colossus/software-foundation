"""Offline policy fixtures for the retained-browser qualification adapter.

The HTML shell and executable are structural input vectors, never applications
launched by this suite. Only the physical browser boundary is replaced. Actual
candidate verification, extraction, pinning and evidence checks remain enabled.
These cases establish no Firefox, Chromium, rendering or release qualification.
"""
from contextlib import ExitStack, contextmanager
import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended_browser_check as browser
import appended_container as container
import appended_policy as policy
import appended_project as project
import appended_release as release
import appended_release_check as common
import artifact
import dependency_archive as archive
import source_identity
from test_appended_wasm import module


def document(path, value):
    path.write_bytes(container.canonical_json(value))


def pinned(path, **extra):
    return {'path': path.name, 'sha256': archive.digest(path), **extra}


def chromium_offline_fixture():
    online = {role: {'response': True, 'requests': 1} for role in ('root', 'frame', 'worker')}
    offline = {role: {'response': False, 'requests': 0} for role in ('root', 'frame', 'worker')}
    return {'enabled': True, 'positive_control': 'owned-loopback-root-frame-worker',
        'before': {'online': online, 'offline': copy.deepcopy(offline),
            'online_conditions': {'offline': False, 'latency': 0, 'download_throughput': 1048576, 'upload_throughput': 1048576},
            'conditions': {'offline': True, 'latency': 0, 'download_throughput': 0, 'upload_throughput': 0},
            'listener_control': True},
        'after': {'offline': offline,
            'conditions': {'offline': True, 'latency': 0, 'download_throughput': 0, 'upload_throughput': 0},
            'listener_control': True}, 'listener_joined': True}


@unittest.skipUnless(sys.platform.startswith('linux'), 'initial physical adapter is Linux Firefox only')
class BrowserCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='appended browser unit fixtures ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        inputs = self.root / 'inputs'
        inputs.mkdir()
        source = self.root / 'source'
        (source / 'src').mkdir(parents=True)
        (source / 'src/kernel.cpp').write_text('retained browser kernel source fixture\n')
        (source / 'src-bin-appended').mkdir()
        (source / 'src-bin-appended/application.c').write_text('portable source fixture; not compiled\n')
        self.application = {'id': 'org.example.browser-check', 'name': 'Retained browser fixture', 'version': '1.0.0'}
        configuration = project.default_document()
        configuration['application'] = self.application
        configuration['appended']['binary']['enabled'] = True
        configuration['startup']['primary'] = 'binary'
        document(source / project.CONFIG_NAME, configuration)
        source_archive = inputs / 'source.tar.gz'
        identity = source_identity.archive_source(source, source_archive)
        self.prefix = (b'<!doctype html><html><head><meta charset="utf-8"></head><body>'
                       b'<main id="application"></main><p id="status">Structural fixture</p>' + container.HTML_MARKER)
        self.descriptor = descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'html',
                      'profile': 'binary', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
                      'services': ['foundation.view'], 'capabilities': ['foundation.view.v1'],
                      'executable': {'length': len(self.prefix), 'sha256': container.digest(self.prefix)},
                      'boundary_offset': None, 'kernel_inputs': policy.kernel_source_tree(source),
                      'provenance': {'producer': 'structural-unit-fixture', 'qualification': 'unqualified-development'}}
        descriptor_path = inputs / 'kernel.json'
        document(descriptor_path, descriptor)
        self.members = {'bin/retained-browser.html': (self.prefix, 0o644),
                        'share/unchanged.bin': (b'unchanged retained dependency\x00\xff', 0o640)}
        directories = {'bin': 0o755, 'share': 0o750, 'empty': 0o700}
        base = inputs / 'base.tar.gz'
        release._write_archive(base, self.members, directories)
        inventory_path = inputs / 'base.inventory.json'
        inventory = artifact.describe(base)
        inventory['modes'] = release._mode_inventory(self.members)
        document(inventory_path, inventory)
        package = container.build_package({'binary/application.wasm': module()}, self.application,
            binary_entry='binary/application.wasm', binary_profile='foundation-guest-v1',
            requires={'abi': {'major': 1, 'minor': 0}, 'services': ['foundation.view'],
                      'capabilities': ['foundation.view.v1']},
            identities={'source_tree': identity['tree_sha256']})
        payload = inputs / 'application.sfapp'
        payload.write_bytes(container.encode_package(package))
        recovery = inputs / 'recovery-inputs'
        recovery.write_bytes(b'explicit retained recovery fixture; not reconstruction evidence')
        selection = {'schema_version': 1, 'kind': 'foundation-appended-selection', 'application': self.application,
                     'source': pinned(source_archive, tree_sha256=identity['tree_sha256']),
                     'payload': pinned(payload), 'kernels': [{'id': 'retained-browser', 'archive': pinned(base),
                     'inventory': pinned(inventory_path), 'descriptor': pinned(descriptor_path),
                     'runtime_member': 'bin/retained-browser.html', 'output': 'retained-browser.tar.gz',
                     'original_source': pinned(source_archive, tree_sha256=identity['tree_sha256']),
                     'recovery': [pinned(recovery)], 'evidence': []}]}
        selected = inputs / 'selection.json'
        document(selected, selection)
        self.candidate = self.root / 'candidate'
        with self.forbid_processes():
            result = release.prepare_release(selected, self.candidate)
            self.subject = release.verify_composition_subject(self.candidate, result['candidate_sha256'])
        self.pin = result['candidate_sha256']
        self.product = self.subject['composition']['artifacts'][0]
        self.executable = self.root / 'firefox structural executable'
        self.executable.write_bytes(b'unit-test browser identity, never executed\n')
        self.executable.chmod(0o755)
        self.scenario = self.root / 'scenario.json'
        self.scenario_data = {'schema_version': 1, 'kind': 'foundation-appended-browser-scenario',
            'candidate_sha256': self.pin, 'artifact_id': self.product['id'], 'target': 'web-wasm32', 'backend': 'web',
            'browser': {'engine': 'firefox', 'executable': str(self.executable), 'sha256': archive.digest(self.executable)},
            'viewport': {'width': 900, 'height': 760}, 'title': self.application['name'],
            'steps': [{'id': 'edit-operand', 'action': 'edit', 'widget': {'id': 'operand', 'generation': '1'}, 'value': '7'},
                      {'id': 'activate-result', 'action': 'activate', 'widget': {'id': 'calculate', 'generation': '1'}},
                      {'id': 'observe-result', 'action': 'assert-text', 'widget': {'id': 'result', 'generation': '1'}, 'value': '42'}]}
        document(self.scenario, self.scenario_data)
        self.execution_context = {'plan': 'a' * 64, 'check': 'browser-check', 'composition_check_id': 'browser-check',
            'run_id': 'unit-browser-fixture', 'attempt': 2, 'qualification_policy_sha256': 'b' * 64, 'profile': 'binary'}
        self.sequence = 0

    def observation(self, runtime, scenario, evidence, work, timeout, environment):
        self.assertEqual(runtime.name, 'retained-browser.html')
        self.assertEqual(runtime.parent.name, 'bin')
        if hasattr(self, 'installed_prefix'):
            self.assertEqual(runtime, self.installed_prefix / self.product['runtime_member'])
        else:
            self.assertIn('relocated browser archive with spaces', str(runtime))
        self.assertEqual(archive.digest(runtime), self.product['runtime_sha256'])
        self.assertEqual(runtime.stat().st_mode & 0o777, 0o644)
        parsed = container.parse_artifact(runtime.read_bytes(), self.descriptor, expected_mode='binary')
        self.assertEqual(parsed.prefix, self.prefix)
        self.assertEqual(parsed.package.file_bytes('binary/application.wasm'), module())
        self.assertEqual((runtime.parents[1] / 'share/unchanged.bin').read_bytes(), self.members['share/unchanged.bin'][0])
        self.assertEqual(scenario['candidate_sha256'], self.pin)
        self.assertEqual(scenario['artifact_id'], self.product['id'])
        self.assertEqual(timeout, 20)
        self.assertIn(' ', str(work))
        self.assertNotIn('LD_LIBRARY_PATH', environment)
        # A complete one-pixel PNG requires no image package or renderer.
        def chunk(kind, value):
            return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))
        capture = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
                   chunk(b'IDAT', zlib.compress(b'\0\0\0\0')) + chunk(b'IEND', b''))
        with (evidence / 'capture.png').open('xb') as stream:
            stream.write(capture)
        return {'engine': 'firefox',
            'capabilities': {'browserName': 'firefox', 'browserVersion': '153.5.0',
                             'moz:buildID': '20261006170429', 'moz:processID': 4242},
            'actual_image': {'pid': 4242, 'path': str(self.executable), 'sha256': archive.digest(self.executable),
                             'owned_ancestry': [4242, 4243]},
            'offline': {'enabled': True, 'positive_control': 'NS_ERROR_OFFLINE'},
            'quit': {'acknowledged': True, 'normal_exit': True}, 'process_tree_joined': True,
            'direct_file_uri': runtime.resolve().as_uri(), 'runtime_sha256': archive.digest(runtime),
            'executed_tests': [step['id'] for step in scenario['steps']],
            'observations': [{'id': step['id'], 'action': step['action'], 'widget': copy.deepcopy(step['widget']),
                              'passed': True} for step in scenario['steps']],
            'application_result_changed': True, 'capture_sha256': container.digest(capture),
            'frame_policy': [{'sandbox': 'allow-scripts', 'srcdoc': True}]}

    def forbid_processes(self):
        stack = ExitStack()
        for name in ('run', 'Popen', 'call', 'check_call', 'check_output'):
            stack.enter_context(patch.object(subprocess, name, side_effect=AssertionError('unexpected process: ' + name)))
        return stack

    def context(self):
        self.sequence += 1
        evidence = self.root / ('evidence-' + str(self.sequence))
        work = self.root / ('work with spaces ' + str(self.sequence))
        evidence.mkdir()
        work.mkdir()
        return {'directory': self.candidate, 'subject': copy.deepcopy(self.subject), 'artifact': copy.deepcopy(self.product),
            'target': 'web-wasm32', 'backend': 'web', 'evidence': evidence, 'work': work,
            'scenario': self.scenario, 'scenario_sha256': archive.digest(self.scenario), 'timeout': 20, 'passed': [],
            'execution_context': copy.deepcopy(self.execution_context),
            'helpers': {'extract': common._extract, 'tree': common._tree, 'environment': common._environment,
                        'new_json': common._new_json, 'junit': common._junit, 'uncertain': common._uncertain}}

    def reject(self, *, scenario=None, context=None):
        if scenario is not None:
            document(self.scenario, scenario)
        context = context or self.context()
        with self.forbid_processes(), patch.object(browser, '_execute_browser') as execute, self.assertRaises(ValueError):
            browser.run(context)
        execute.assert_not_called()
        self.assertEqual(context['passed'], [])

    def test_scenario_binds_exact_candidate_artifact_target_and_data_only_steps(self):
        changes = [lambda value: value.update(schema_version=True),
            lambda value: value.update(kind='other-browser-scenario'),
            lambda value: value.update(candidate_sha256='0' * 64),
            lambda value: value.update(artifact_id='other-artifact'),
            lambda value: value.update(target='linux-x86_64'),
            lambda value: value.update(backend='terminal'),
            lambda value: value.update(script='window.application = "mock result"'),
            lambda value: value['browser'].update(argv=['--browser-workaround']),
            lambda value: value['steps'][0].update(selector='input'),
            lambda value: value['steps'][0].update(action='execute-script'),
            lambda value: value['steps'][0]['widget'].update(generation='0'),
            lambda value: value['steps'][0]['widget'].update(generation='01'),
            lambda value: value['steps'][0]['widget'].update(generation=str(1 << 64)),
            lambda value: value['steps'][0]['widget'].update(generation=1),
            lambda value: value['steps'][0].update(value=7),
            lambda value: value['steps'][1].update(value='not allowed for activation'),
            lambda value: value['steps'][2].update(id=value['steps'][0]['id']),
            lambda value: value['steps'][0].pop('value')]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                value = copy.deepcopy(self.scenario_data)
                change(value)
                self.reject(scenario=value)

    def test_rich_both_scenario_requires_versioned_identity_fields(self):
        identities = {
            'profile': 'both', 'source_tree_sha256': '1' * 64,
            'source_observed_at_package_sha256': '2' * 64, 'kernel_inputs_sha256': '3' * 64,
            'kernel_descriptor_sha256': '4' * 64, 'kernel_prefix_sha256': '5' * 64,
            'kernel_prefix_length': 4096, 'kernel_receipt_sha256': '6' * 64,
            'engine_recipe_sha256': '7' * 64, 'engine_manifest_sha256': '8' * 64,
            'engine_proof_sha256': '9' * 64, 'engine_runtime_sha256': 'a' * 64,
            'payload_transport_sha256': 'b' * 64, 'payload_package_sha256': 'c' * 64,
            'payload_id': 'fixture-payload-id'}
        rich_artifact = dict(self.product, profile='both')
        scenario = dict(self.scenario_data, schema_version=2,
                        kind='foundation-rich-both-browser-scenario', rich_identities=identities,
                        rich_inspection_sources={name: archive.digest(ROOT / name) for name in browser.RICH_INSPECTION_SOURCES})
        document(self.scenario, scenario)
        _, selected, _ = browser._scenario(self.scenario, archive.digest(self.scenario), self.subject,
                                            rich_artifact, 'web-wasm32', 'web')
        self.assertEqual(selected['rich_identities'], identities)
        for key in ('kernel_receipt_sha256', 'engine_runtime_sha256', 'payload_package_sha256'):
            broken = copy.deepcopy(scenario)
            broken['rich_identities'][key] = 'not-a-sha256'
            document(self.scenario, broken)
            with self.assertRaises(ValueError):
                browser._scenario(self.scenario, archive.digest(self.scenario), self.subject,
                                  rich_artifact, 'web-wasm32', 'web')

    def test_rich_both_admission_refuses_binary_partial_candidate(self):
        with self.assertRaisesRegex(ValueError, 'requires an HTML BOTH kernel and BOTH payload'):
            browser._rich_both_identity(self.candidate, self.subject, self.product)

    def test_binary_scenario_cannot_claim_rich_identity_fields(self):
        value = copy.deepcopy(self.scenario_data)
        value['rich_identities'] = {'profile': 'both'}
        self.reject(scenario=value)

    def test_rich_input_completes_focus_before_keyboard_and_reports_dom_only(self):
        for engine in ('firefox', 'chromium'):
            physical = Mock()
            physical.evaluate.return_value = {'x': 12.5, 'y': 20}
            physical.path.side_effect = lambda value: value
            step = {'action': 'edit', 'widget': {'id': 'amount', 'generation': '2'}, 'value': '44'}
            dispatched = browser._trusted_action(physical, engine, step)
            self.assertGreater(dispatched, 0)
            calls = physical.request.call_args_list if engine == 'chromium' else physical.command.call_args_list
            self.assertEqual(len(calls), 2)
            requests = [call.args[-1]['actions'] for call in calls]
            self.assertEqual([group[0]['type'] for group in requests], ['pointer', 'key'])
            self.assertEqual(requests[0][0]['actions'][-1], {'type': 'pointerUp', 'button': 0})
            self.assertEqual([item['value'] for item in requests[1][0]['actions'][-4:]], ['4', '4', '4', '4'])
        clocks = browser._rich_clocks(10, 20, 1020)
        self.assertTrue(browser._valid_rich_clocks(clocks))
        self.assertEqual(set(clocks['pending_measurements']), set(browser.RICH_PENDING))
        self.assertNotIn('first_visible_ack_ns', clocks)
        self.assertNotIn('warm_reload_samples', clocks)
        clocks['changed_dom_observed_ns'] = 19
        self.assertFalse(browser._valid_rich_clocks(clocks))

    def test_real_public_document_editor_both_parsers_keep_fixtures_ineligible(self):
        from test_package_appended_engine_document_wasm import DocumentBrowserProducerTests, EditorBrowserProducerTests
        from package_appended_engine_wasm import inspect_prefix as rendering_parser
        for fixture_type in (DocumentBrowserProducerTests, EditorBrowserProducerTests):
            fixture = fixture_type()
            try:
                fixture.setUp()
                prefix, envelope, facts = fixture.assemble(profile='both')
                # This was the actual policy mismatch: the old rendering-only
                # inspector rejects legitimate document/editor envelopes.
                with self.assertRaises(ValueError):
                    rendering_parser(prefix)
                actual, observed = browser._inspect_rich_prefix(prefix, envelope['kind'])
                self.assertEqual(actual, envelope)
                self.assertFalse(observed['production_eligible'])
                self.assertEqual(observed['kernel_receipt']['scope'], 'parser-fixture-only')
            finally:
                fixture.doCleanups()

    def test_rich_interpreter_sources_are_exact_and_independently_pinned(self):
        import ast
        todo = ['package_appended_engine_document_wasm', 'package_appended_engine_wasm']
        closure = set()
        while todo:
            name = todo.pop()
            if name in closure:
                continue
            closure.add(name)
            for node in ast.walk(ast.parse((ROOT / 'tools' / (name + '.py')).read_text())):
                imports = ([item.name.split('.')[0] for item in node.names] if isinstance(node, ast.Import)
                    else [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
                todo.extend(item for item in imports if (ROOT / 'tools' / (item + '.py')).is_file() and item not in closure)
        self.assertEqual(set(browser.RICH_INSPECTION_SOURCES), {'tools/' + name + '.py' for name in closure})
        pins = {name: archive.digest(ROOT / name) for name in browser.RICH_INSPECTION_SOURCES}
        self.assertEqual(len(browser._rich_sources(pins)), len(pins))
        pins['tools/package_appended_engine_document_wasm.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'differs from frozen scenario'):
            browser._rich_sources(pins)
        with self.assertRaisesRegex(ValueError, 'unsupported public rich retained-prefix role'):
            browser._inspect_rich_prefix(b'not a prefix', 'unknown')

    def test_empty_unbounded_or_noninteractive_scenarios_never_launch(self):
        for steps in ([], self.scenario_data['steps'][:1], self.scenario_data['steps'] * 22,
                      [self.scenario_data['steps'][2], dict(self.scenario_data['steps'][2], id='another-assertion')],
                      self.scenario_data['steps'][:2], [self.scenario_data['steps'][2], self.scenario_data['steps'][0]]):
            with self.subTest(count=len(steps), actions=[step['action'] for step in steps]):
                self.reject(scenario=dict(self.scenario_data, steps=steps))

    def test_wrong_engine_and_incomplete_execution_context_fail_before_boundary(self):
        for engine in ('chromium', 'unknown'):
            value = copy.deepcopy(self.scenario_data)
            value['browser']['engine'] = engine
            self.reject(scenario=value)
        document(self.scenario, self.scenario_data)
        for missing in self.execution_context:
            with self.subTest(missing=missing):
                context = self.context()
                context['execution_context'].pop(missing)
                self.reject(context=context)
        for key, value in (('attempt', 0), ('attempt', True), ('composition_check_id', 'another-check')):
            with self.subTest(key=key, value=value):
                context = self.context()
                context['execution_context'][key] = value
                self.reject(context=context)

    def test_independent_scenario_and_executable_pins_cannot_be_relabelled(self):
        context = self.context()
        context['scenario_sha256'] = '0' * 64
        self.reject(context=context)
        value = copy.deepcopy(self.scenario_data)
        value['browser']['sha256'] = '0' * 64
        self.reject(scenario=value)
        value = copy.deepcopy(self.scenario_data)
        value['browser']['executable'] = self.executable.name
        self.reject(scenario=value)

    def test_context_cannot_substitute_another_selected_product_or_subject(self):
        changes = [lambda value: value.update(target='linux-x86_64'),
                   lambda value: value.update(backend='terminal'),
                   lambda value: value['artifact'].update(runtime_sha256='0' * 64),
                   lambda value: value['artifact'].update(runtime_member='share/unchanged.bin'),
                   lambda value: value['subject'].update(candidate_sha256='0' * 64)]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                context = self.context()
                change(context)
                self.reject(context=context)

    def test_viewport_value_timeout_and_repeated_edit_limits_fail_before_admission(self):
        changes = [lambda value: value['viewport'].update(width=0),
                   lambda value: value['viewport'].update(height=True),
                   lambda value: value['viewport'].update(width=4097),
                   lambda value: value['steps'][0].update(value='x' * (64 * 1024 + 1)),
                   lambda value: value['steps'][0].update(value='embedded\0nul'),
                   lambda value: value['steps'].insert(1, dict(value['steps'][0], id='repeat-edit', value='8'))]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                value = copy.deepcopy(self.scenario_data)
                change(value)
                self.reject(scenario=value)
        document(self.scenario, self.scenario_data)
        for timeout in (0, True, float('nan'), float('inf')):
            with self.subTest(timeout=timeout):
                context = self.context()
                context['timeout'] = timeout
                self.reject(context=context)

    def test_supplied_checker_source_pins_must_match_the_observed_helper_closure(self):
        context = self.context()
        context['checker_sources'] = {name: archive.digest(ROOT / name) for name in browser.CHECKER_SOURCES}
        context['checker_sources']['gui/tests/browser_test.py'] = '0' * 64
        self.reject(context=context)

    def test_pinned_optional_inputs_are_portable_paths_and_exact_bytes(self):
        input_path = self.root / 'scenario-input.bin'
        input_path.write_bytes(b'pinned scenario support data')
        for inputs in ({'../outside': archive.digest(input_path)},
                       {'/absolute': archive.digest(input_path)},
                       {'scenario-input.bin': '0' * 64}):
            with self.subTest(inputs=inputs):
                self.reject(scenario=dict(self.scenario_data, inputs=inputs))

    def test_success_uses_exact_extracted_artifact_and_emits_only_executed_step_junit(self):
        context = self.context()
        with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=self.observation) as execute:
            details = browser.run(context)
        execute.assert_called_once()
        names = [step['id'] for step in self.scenario_data['steps']]
        self.assertEqual(context['passed'], common.ASSERTIONS['browser'])
        self.assertEqual(details['scenario_sha256'], archive.digest(self.scenario))
        self.assertEqual(details['executed_tests'], names)
        self.assertEqual(details['junit'], 'browser/scenario.junit.xml')
        self.assertEqual(details['browser']['runtime_sha256'], self.product['runtime_sha256'])
        self.assertEqual(details['browser']['executable']['sha256'], archive.digest(self.executable))
        self.assertEqual(details['browser']['actual_image']['sha256'], archive.digest(self.executable))
        evidence = context['evidence'] / 'browser'
        suite = ET.parse(evidence / 'scenario.junit.xml').getroot()
        self.assertEqual([case.get('name') for case in suite.iter('testcase')], names)
        self.assertFalse(list(suite.iter('failure')) + list(suite.iter('skipped')))
        common.c.junit(evidence / 'scenario.junit.xml', names)
        self.assertEqual(json.loads((evidence / 'before.json').read_bytes()),
                         json.loads((evidence / 'after.json').read_bytes()))
        self.assertEqual(json.loads((evidence / 'observation.json').read_bytes()), details['browser'])
        for name in browser.CHECKER_SOURCES:
            self.assertEqual(details['checker_sources'][name], archive.digest(ROOT / name))

    def test_full_u64_widget_generation_and_pinned_support_input_remain_exact(self):
        value = copy.deepcopy(self.scenario_data)
        for step in value['steps']:
            step['widget']['generation'] = str((1 << 64) - 1)
        support = self.root / 'support input.bin'
        support.write_bytes(b'explicit support input')
        value['inputs'] = {support.name: archive.digest(support)}
        document(self.scenario, value)
        context = self.context()
        with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=self.observation):
            details = browser.run(context)
        self.assertEqual([step['widget']['generation'] for step in details['browser']['observations']],
                         [str((1 << 64) - 1)] * len(value['steps']))

    def test_failed_offline_identity_or_shutdown_evidence_cannot_pass(self):
        changes = [lambda value: value.update(engine='chromium'),
            lambda value: value['capabilities'].update(browserName='chromium'),
            lambda value: value['capabilities'].update({'moz:buildID': ''}),
            lambda value: value['actual_image'].update(pid=9999),
            lambda value: value['actual_image'].update(path='relative-browser'),
            lambda value: value['offline'].update(enabled=False),
            lambda value: value['offline'].update(positive_control='not observed'),
            lambda value: value['quit'].update(acknowledged=False),
            lambda value: value['quit'].update(normal_exit=False),
            lambda value: value.update(direct_file_uri='file:///another-runtime.html'),
            lambda value: value.update(runtime_sha256='0' * 64),
            lambda value: value.update(capture_sha256='0' * 64),
            lambda value: value.update(frame_policy=[{'sandbox': 'allow-scripts allow-same-origin', 'srcdoc': True}])]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                context = self.context()
                def changed(*args):
                    value = self.observation(*args)
                    change(value)
                    return value
                with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=changed), \
                        self.assertRaises(ValueError):
                    browser.run(context)
                self.assertNotEqual(context['passed'], common.ASSERTIONS['browser'])
                self.assertFalse((context['evidence'] / 'browser/observation.json').exists())

    def test_incomplete_changed_or_fabricated_step_observations_are_rejected(self):
        changes = [lambda value: value.update(executed_tests=value['executed_tests'][:-1]),
            lambda value: value.update(executed_tests=value['executed_tests'] + ['invented-step']),
            lambda value: value['executed_tests'].reverse(),
            lambda value: value.update(application_result_changed=False),
            lambda value: value.update(observations=value['observations'][:-1]),
            lambda value: value['observations'][0].update(passed=False),
            lambda value: value['observations'][0]['widget'].update(id='unrelated-widget')]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                context = self.context()
                def changed(*args):
                    value = self.observation(*args)
                    change(value)
                    return value
                with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=changed), \
                        self.assertRaises(ValueError):
                    browser.run(context)
                self.assertNotIn('retained-runtime', context['passed'])

    def test_changed_runtime_and_unchanged_dependency_are_rechecked_after_browser_exit(self):
        for name in ('bin/retained-browser.html', 'share/unchanged.bin'):
            with self.subTest(name=name):
                context = self.context()
                def mutate(runtime, *args):
                    value = self.observation(runtime, *args)
                    (runtime.parents[1] / name).write_bytes(b'changed while browser was running')
                    return value
                with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=mutate), \
                        self.assertRaisesRegex(ValueError, 'runtime|inventory|unchanged'):
                    browser.run(context)
                self.assertNotIn('retained-runtime', context['passed'])

    def test_scenario_executable_and_support_input_mutation_cannot_be_hidden(self):
        support = self.root / 'support.bin'
        for name in ('scenario', 'executable', 'support'):
            with self.subTest(name=name):
                support.write_bytes(b'unchanged support input')
                self.executable.write_bytes(b'unit-test browser identity, never executed\n')
                value = copy.deepcopy(self.scenario_data)
                value['inputs'] = {support.name: archive.digest(support)}
                document(self.scenario, value)
                context = self.context()
                def mutate(*args):
                    result = self.observation(*args)
                    {'scenario': self.scenario, 'executable': self.executable, 'support': support}[name].write_bytes(b'changed')
                    return result
                with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=mutate), \
                        self.assertRaises(ValueError):
                    browser.run(context)
                self.assertNotIn('retained-runtime', context['passed'])

    def test_same_bytes_scenario_replacement_still_invalidates_physical_snapshot(self):
        context = self.context()
        def replace(*args):
            value = self.observation(*args)
            replacement = self.root / 'replacement.json'
            replacement.write_bytes(self.scenario.read_bytes())
            replacement.replace(self.scenario)
            return value
        with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=replace), \
                self.assertRaises(ValueError):
            browser.run(context)
        self.assertNotIn('retained-runtime', context['passed'])

    def test_uncertain_cleanup_does_not_finalize_passing_or_failed_step_evidence(self):
        context = self.context()
        with self.forbid_processes(), patch.object(browser, '_execute_browser',
                side_effect=common.ProcessTreeError('retain output ownership: browser descendants remain')), \
                self.assertRaises(common.ProcessTreeError):
            browser.run(context)
        self.assertEqual(context['passed'], [])
        for name in ('scenario.junit.xml', 'observation.json', 'after.json'):
            self.assertFalse((context['evidence'] / 'browser' / name).exists())

    def test_missing_or_false_join_is_uncertain_before_other_observation_validation(self):
        for observed in (None, {}, {'process_tree_joined': False}):
            with self.subTest(observed=observed):
                context = self.context()
                with self.forbid_processes(), patch.object(browser, '_execute_browser', return_value=observed), \
                        self.assertRaises(common.ProcessTreeError):
                    browser.run(context)
                self.assertEqual(context['passed'], [])
                for name in ('scenario.junit.xml', 'observation.json', 'after.json'):
                    self.assertFalse((context['evidence'] / 'browser' / name).exists())

    def dispatcher(self, scope):
        evidence = self.root / ('dispatcher-' + scope)
        environment = {'FOUNDATION_PLAN_ID': self.execution_context['plan'],
            'FOUNDATION_CHECK_ID': self.execution_context['check'], 'FOUNDATION_RUN_ID': self.execution_context['run_id'],
            'FOUNDATION_RUN_ATTEMPT': str(self.execution_context['attempt']),
            'FOUNDATION_COMPOSITION_POLICY_SHA256': self.execution_context['qualification_policy_sha256'],
            'FOUNDATION_COMPOSITION_PROFILE': self.execution_context['profile'],
            'FOUNDATION_COMPOSITION_TOOL_SOURCES': container.canonical_json({name: archive.digest(ROOT / name)
                for name in common.tool_source_catalog([scope, 'browser'])}).decode('utf-8')}
        with self.forbid_processes(), patch.dict(os.environ, environment), \
                patch.object(browser, '_execute_browser', side_effect=self.observation):
            receipt = common.check(self.candidate, self.pin, 'web-wasm32', 'web', scope, evidence,
                artifact_id=self.product['id'], scenario=self.scenario, scenario_sha256=archive.digest(self.scenario), timeout=20)
        return receipt, evidence

    def check_browser_host(self, receipt, evidence):
        check = {'id': 'actual-browser', 'target': 'web-wasm32', 'environment': 'firefox',
                 'qualification': 'qualification.json'}
        report = {'host': common.c.host_identity(), 'status': 'passed'}
        common.c.check_host({'checks': [check]}, check['id'], report, evidence)
        with self.assertRaisesRegex(ValueError, 'browser evidence'):
            common.c.check_host({'checks': [dict(check, environment='chromium')]}, check['id'], report, evidence)
        self.assertEqual(receipt['details']['browser']['browser_version'], '153.5.0')
        self.assertEqual(receipt['details']['browser']['status'], 'passed')

    def test_dispatcher_receipt_carries_execution_bindings_nested_junit_and_all_evidence_pins(self):
        receipt, evidence = self.dispatcher('browser')
        self.assertEqual(receipt['status'], 'passed')
        self.assertEqual(receipt['assertions'], common.ASSERTIONS['browser'])
        for key, value in self.execution_context.items():
            self.assertEqual(receipt['details'][key], value)
        self.assertEqual(receipt['details']['junit'], 'browser/scenario.junit.xml')
        self.assertEqual(receipt['details']['artifact_id'], self.product['id'])
        self.assertEqual(receipt['details']['runtime_sha256'], self.product['runtime_sha256'])
        self.assertIn('browser/capture.png', receipt['evidence'])
        self.assertIn('browser/scenario.junit.xml', receipt['evidence'])
        for name, expected in receipt['evidence'].items():
            self.assertEqual(archive.digest(evidence / name), expected)
        common.c.junit(evidence / 'qualification.junit.xml', common.ASSERTIONS['browser'])
        self.check_browser_host(receipt, evidence)

    def test_retained_runtime_html_uses_browser_adapter_and_certifiable_host_evidence(self):
        receipt, evidence = self.dispatcher('retained-runtime')
        self.assertEqual(receipt['status'], 'passed')
        self.assertEqual(receipt['assertions'], common.ASSERTIONS['retained-runtime'])
        self.assertEqual(receipt['details']['runtime']['executed_tests'],
                         [step['id'] for step in self.scenario_data['steps']])
        self.assertEqual(receipt['details']['runtime']['browser'], receipt['details']['browser'])
        self.assertEqual(set(receipt['details']['checker_sources']),
                         set(common.tool_source_catalog(['retained-runtime', 'browser'])))
        common.c.junit(evidence / 'qualification.junit.xml', common.ASSERTIONS['retained-runtime'])
        self.check_browser_host(receipt, evidence)

    def test_installed_prefix_executes_in_place_and_preserves_complete_foreign_inventory(self):
        context = self.context()
        prefix = context['work'] / 'installed prefix with spaces'
        common._extract(self.candidate, self.product, prefix)
        foreign = prefix / 'foreign-sentinel';foreign.write_bytes(b'foreign installed state\0')
        foreign.chmod(0o600)
        before = foreign.stat()
        context.update(installed_prefix=prefix, installed_inventory=common._tree(prefix))
        self.installed_prefix = prefix
        with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=self.observation), \
                patch.dict(context['helpers'], extract=lambda *args: self.fail('installed runtime was relocated')):
            details = browser.run(context)
        self.assertEqual(details['browser']['direct_file_uri'], (prefix / self.product['runtime_member']).as_uri())
        self.assertEqual(context['passed'], common.ASSERTIONS['browser'])
        self.assertEqual(common._tree(prefix), context['installed_inventory'])
        self.assertEqual((foreign.stat().st_dev, foreign.stat().st_ino, foreign.stat().st_mode),
                         (before.st_dev, before.st_ino, before.st_mode))

    def test_installed_prefix_mismatch_and_foreign_identity_replacement_cannot_pass(self):
        context = self.context()
        prefix = context['work'] / 'installed prefix with spaces'
        common._extract(self.candidate, self.product, prefix)
        context.update(installed_prefix=prefix, installed_inventory=common._tree(prefix))
        (prefix / self.product['runtime_member']).chmod(0o600)
        self.reject(context=context)
        (prefix / self.product['runtime_member']).chmod(0o644)
        foreign = prefix / 'foreign';foreign.write_bytes(b'unchanged bytes')
        context = self.context()
        context.update(installed_prefix=prefix, installed_inventory=common._tree(prefix))
        self.installed_prefix = prefix
        def replace(runtime, *args):
            value = self.observation(runtime, *args)
            replacement = prefix / 'replacement';replacement.write_bytes(foreign.read_bytes())
            replacement.chmod(foreign.stat().st_mode & 0o777);replacement.replace(foreign)
            return value
        with self.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=replace), \
                self.assertRaisesRegex(ValueError, 'runtime|inventory'):
            browser.run(context)
        self.assertNotIn('retained-runtime', context['passed'])


@unittest.skipUnless(sys.platform.startswith('linux'), 'native-image adapter selects Linux')
class ChromiumAdapterTests(unittest.TestCase):
    def setUp(self):
        self.fixture = BrowserCheckTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.executable = self.fixture.root, self.fixture.executable
        self.executable.write_bytes(b'\x7fELF' + b'B' * 60)
        self.driver = self.root / 'native structural driver'
        self.driver.write_bytes(b'\x7fELF' + b'D' * 60);self.driver.chmod(0o755)
        self.scenario = copy.deepcopy(self.fixture.scenario_data)
        self.scenario['browser'] = {'engine': 'chromium', 'executable': str(self.executable),
            'sha256': archive.digest(self.executable),
            'driver': {'executable': str(self.driver), 'sha256': archive.digest(self.driver)}}
        document(self.fixture.scenario, self.scenario)

    def observation(self, *args):
        result = self.fixture.observation(*args)
        result.update(engine='chromium',
            capabilities={'browserName': 'chrome', 'browserVersion': '130.0.1.2', 'goog:processID': 4242,
                          'chrome': {'chromedriverVersion': '130.0.1.7 (fixture)'}},
            actual_image={'pid': 4242, 'start_time': '123', 'path': str(self.executable),
                          'sha256': archive.digest(self.executable), 'owned_ancestry': [4242, 4243, 4244]},
            actual_driver={'pid': 4243, 'start_time': '124', 'path': str(self.driver),
                          'sha256': archive.digest(self.driver), 'owned_ancestry': [4243, 4244]},
            offline=chromium_offline_fixture())
        return result

    def test_chromium_exact_candidate_scenario_pins_and_changed_result(self):
        context = self.fixture.context()
        with self.fixture.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=self.observation):
            result = browser.run(context)
        self.assertEqual(context['passed'], common.ASSERTIONS['browser'])
        self.assertEqual(result['browser']['engine'], 'chromium')
        self.assertEqual(result['browser']['driver'], {'path': str(self.driver), 'sha256': archive.digest(self.driver)})
        self.assertTrue(browser._validate_offline('chromium', result['browser']['offline']))

    def test_driver_selection_is_explicit_native_distinct_and_independently_pinned(self):
        changes = [lambda value: value['browser'].pop('driver'),
            lambda value: value['browser']['driver'].update(executable=self.driver.name),
            lambda value: value['browser']['driver'].update(sha256='0' * 64),
            lambda value: value['browser']['driver'].update(argv=['--unsafe']),
            lambda value: value['browser'].update(driver={'executable': str(self.executable), 'sha256': archive.digest(self.executable)}),
            lambda value: value['browser'].update(engine='firefox')]
        for index, change in enumerate(changes):
            value = copy.deepcopy(self.scenario);change(value)
            with self.subTest(index=index):
                self.fixture.reject(scenario=value)
        document(self.fixture.scenario, self.scenario)
        for invalid in ('script', 'mode', 'hardlink'):
            with self.subTest(invalid=invalid):
                if invalid == 'script':
                    self.driver.write_bytes(b'#!/bin/sh\nexit 0\n')
                elif invalid == 'mode':
                    self.driver.write_bytes(b'\x7fELF' + b'D' * 60);self.driver.chmod(0o644)
                else:
                    self.driver.unlink();os.link(self.executable, self.driver)
                value = copy.deepcopy(self.scenario)
                value['browser']['driver']['sha256'] = archive.digest(self.driver)
                self.fixture.reject(scenario=value)

    def test_incomplete_native_driver_offline_and_shutdown_observations_cannot_pass(self):
        changes = [lambda value: value['capabilities'].pop('goog:processID'),
            lambda value: value['capabilities'].update({'goog:processID': True}),
            lambda value: value['capabilities']['chrome'].update(chromedriverVersion='129.0.1.7'),
            lambda value: value['actual_driver'].update(start_time=''),
            lambda value: value['actual_driver'].update(path=str(self.executable)),
            lambda value: value['actual_driver'].update(sha256='0' * 64),
            lambda value: value['actual_image'].update(owned_ancestry=[4242, 4244]),
            lambda value: value['offline']['before']['online']['worker'].update(response=False),
            lambda value: value['offline']['before']['online']['frame'].update(requests=0),
            lambda value: value['offline']['before']['offline']['worker'].update(requests=1),
            lambda value: value['offline']['after']['offline'].pop('worker'),
            lambda value: value['offline']['after']['conditions'].update(offline=False),
            lambda value: value['offline']['after'].update(listener_control=False),
            lambda value: value['offline'].update(listener_joined=False),
            lambda value: value['quit'].update(normal_exit=False)]
        for index, change in enumerate(changes):
            context = self.fixture.context()
            def changed(*args):
                result = self.observation(*args);change(result);return result
            with self.subTest(index=index), self.fixture.forbid_processes(), \
                    patch.object(browser, '_execute_browser', side_effect=changed), self.assertRaises(ValueError):
                browser.run(context)
            self.assertNotEqual(context['passed'], common.ASSERTIONS['browser'])

    def test_selected_driver_mutation_stops_retained_runtime_evidence(self):
        context = self.fixture.context()
        def changed(*args):
            result = self.observation(*args);self.driver.write_bytes(b'changed native image');return result
        with self.fixture.forbid_processes(), patch.object(browser, '_execute_browser', side_effect=changed), self.assertRaises(ValueError):
            browser.run(context)
        self.assertNotIn('retained-runtime', context['passed'])

    def test_native_image_identity_requires_driver_ancestry_and_stable_processes(self):
        identities = {4242: ('123', 4243), 4243: ('124', 4244), 4244: ('125', 1)}
        selected = SimpleNamespace(capabilities={'goog:processID': 4242}, process=SimpleNamespace(pid=4244))
        def image(path):
            return str(self.executable if str(path).split('/')[2] == '4242' else self.driver)
        with patch.object(browser, '_proc_identity', side_effect=identities.__getitem__), \
                patch.object(browser.os, 'readlink', side_effect=image):
            snapshots, actual, driver = browser._chromium_images(selected, self.scenario)
        self.assertEqual(len(snapshots), 4)
        self.assertEqual(actual['owned_ancestry'], [4242, 4243, 4244])
        self.assertEqual(driver['owned_ancestry'], [4243, 4244])
        identities[4243] = ('124', 1)
        with patch.object(browser, '_proc_identity', side_effect=identities.__getitem__), self.assertRaises(ValueError):
            browser._chromium_images(selected, self.scenario)

    def test_canary_phase_requires_real_online_response_and_independent_zero_offline_requests(self):
        resource = Mock()
        resource.resource.side_effect = lambda phase, role: ('/' + phase + '/' + role, 'http://127.0.0.1:1/' + role, role)
        for online, response, count, success in ((True, True, 1, True), (True, False, 1, False),
                (False, False, 0, True), (False, False, 1, False), (False, True, 0, False)):
            agent = Mock();agent.evaluate.return_value = {'response': response};resource.count.return_value = count
            with self.subTest(online=online, response=response, count=count):
                if success:
                    result = browser._canary_phase(agent, resource, 'online' if online else 'before', online)
                    self.assertEqual(set(result), {'root', 'frame', 'worker'})
                    self.assertEqual(agent.evaluate.call_count, 3)
                    self.assertEqual(agent.evaluate.call_args_list[-1].args[0], browser.CANARY_WORKER)
                else:
                    with self.assertRaises(ValueError):
                        browser._canary_phase(agent, resource, 'online' if online else 'before', online)

    def test_listener_cleanup_uncertainty_is_sticky_and_late_requests_fail(self):
        for operation in ('shutdown', 'join', 'server_close', 'alive'):
            resource = object.__new__(browser._CanaryResources)
            resource.closed = False;resource.cleanup_error = None;resource.server = Mock();resource.thread = Mock()
            resource.thread.is_alive.return_value = operation == 'alive'
            if operation != 'alive':
                getattr(resource.thread if operation == 'join' else resource.server, operation).side_effect = OSError('uncertain')
            with self.subTest(operation=operation), self.assertRaises(common.ProcessTreeError) as first:
                resource.close()
            with self.assertRaises(common.ProcessTreeError) as second:
                resource.close()
            self.assertIs(first.exception, second.exception)
        resource = object.__new__(browser._CanaryResources);resource.lock = threading.Lock()
        resource.counts = {'/x/online/root': 1, '/x/before/root': 0, '/x/after/host': 1}
        resource.complete();resource.counts['/x/before/root'] = 1
        with self.assertRaises(ValueError):
            resource.complete()

    def test_normal_browser_driver_shutdown_never_terminates_and_requires_all_descendants_gone(self):
        agent = Mock();agent.process.pid = 4244;agent.owner.wait.return_value = 0
        agent.cdp.return_value = {};agent.request.return_value = None
        image = {'pid': 4242, 'start_time': '123'};driver = {'pid': 4243, 'start_time': '124'}
        def identity(pid):
            if pid == 4242:
                raise FileNotFoundError()
            return ('124', 4244)
        with patch.object(browser, '_owned_children', return_value={4243}), \
                patch.object(browser, '_proc_identity', side_effect=identity):
            result = browser._chromium_quit(agent, image, driver, browser.time.monotonic() + 10)
        self.assertEqual(result, {'acknowledged': True, 'normal_exit': True})
        agent.owner.terminate.assert_not_called();agent.owner.finish.assert_called_once();agent.owner.close.assert_called_once()
        agent.cdp.assert_called_once_with('Browser.close', {});agent.request.assert_called_once_with('GET', '/shutdown')
        agent = Mock();agent.cdp.return_value = {}
        with self.assertRaises(TimeoutError):
            browser._chromium_quit(agent, image, driver, 0)
        agent.request.assert_not_called();agent.owner.finish.assert_not_called()

    def test_descendant_inventory_includes_children_of_nonleader_tasks(self):
        tree = self.root / 'owned process tree fixture'
        for pid, threads in ((4244, {4244: '', 4344: '4243'}), (4243, {4243: '', 4343: '4242'}),
                             (4242, {4242: ''})):
            for tid, children in threads.items():
                directory = tree / str(pid) / 'task' / str(tid);directory.mkdir(parents=True)
                (directory / 'children').write_text(children)
        original = Path
        def process_path(*parts):
            return original(tree, *parts[1:]) if parts and parts[0] == '/proc' else original(*parts)
        with patch.object(browser, 'Path', side_effect=process_path):
            self.assertEqual(browser._owned_children(4244), {4242, 4243})

    def test_quit_waits_for_natural_children_and_rejects_driver_exit_or_missing_acknowledgement(self):
        image = {'pid': 4242, 'start_time': '123'};driver = {'pid': 4243, 'start_time': '124'}
        def identity(pid):
            if pid == 4242:
                raise FileNotFoundError()
            return ('124', 4244)
        agent = Mock();agent.process.pid = 4244;agent.owner.poll.return_value = None
        agent.owner.wait.return_value = 0;agent.cdp.return_value = {};agent.request.return_value = None
        with patch.object(browser, '_owned_children', side_effect=[{4242, 4243, 4245}, {4243}]) as children, \
                patch.object(browser, '_proc_identity', side_effect=identity), patch.object(browser.time, 'sleep'):
            browser._chromium_quit(agent, image, driver, browser.time.monotonic() + 10)
        self.assertEqual(children.call_count, 2);agent.owner.terminate.assert_not_called()
        agent = Mock();agent.cdp.return_value = {};agent.owner.poll.return_value = 1
        with patch.object(browser, '_owned_children', return_value={4242, 4243}), \
                self.assertRaisesRegex(ValueError, 'driver exited'):
            browser._chromium_quit(agent, image, driver, browser.time.monotonic() + 10)
        agent.request.assert_not_called()
        agent = Mock();agent.cdp.return_value = None
        with self.assertRaisesRegex(ValueError, 'acknowledge'):
            browser._chromium_quit(agent, image, driver, browser.time.monotonic() + 10)
        agent.request.assert_not_called();agent.owner.finish.assert_not_called()

    def test_offline_validator_is_engine_specific_complete_and_type_exact(self):
        self.assertTrue(browser._validate_offline('chromium', chromium_offline_fixture()))
        self.assertFalse(browser._validate_offline('firefox', chromium_offline_fixture()))
        self.assertFalse(browser._validate_offline('unknown', chromium_offline_fixture()))
        value = chromium_offline_fixture();value['before']['offline']['worker']['requests'] = False
        self.assertFalse(browser._validate_offline('chromium', value))

    def test_fixed_transport_executes_controls_then_untouched_file_and_natural_quit(self):
        """Fake only native/HTTP boundaries; execute the actual adapter sequence."""
        owner = Mock();owner.process.pid = 4244;owner.wait.return_value = 0
        events, conditions = [], {}
        capabilities = {'browserName': 'chrome', 'browserVersion': '130.0.1.2', 'goog:processID': 4242,
                        'chrome': {'chromedriverVersion': '130.0.1.7 (fixture)'}}
        image = {'pid': 4242, 'start_time': '123', 'path': str(self.executable),
                 'sha256': archive.digest(self.executable), 'owned_ancestry': [4242, 4243, 4244]}
        driver = {'pid': 4243, 'start_time': '124', 'path': str(self.driver),
                  'sha256': archive.digest(self.driver), 'owned_ancestry': [4243, 4244]}
        fixture = self

        class Base:
            def __init__(self, executable, selected_driver, directory, arguments):
                fixture.assertEqual((executable, selected_driver), (str(fixture.executable), str(fixture.driver)))
                fixture.assertNotIn('--no-sandbox', arguments)
                self.base = 'http://127.0.0.1:1';self.session = None
                self._launch([selected_driver, '--port=1', '--allowed-ips=127.0.0.1'], directory, 'chromedriver.log')
                value = self.request('POST', '/session', {'capabilities': {'alwaysMatch': {}}})
                self.session, self.capabilities = value['sessionId'], value['capabilities']

            def path(self, suffix):
                return '/session/unit' + suffix

            def command(self, name, arguments):
                events.append((name, arguments))
                if name == 'WebDriver:Navigate':
                    return self.request('POST', self.path('/url'), arguments)
                if name == 'WebDriver:TakeScreenshot':
                    return {'value': browser.base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()}
                if name == 'WebDriver:SwitchToFrame':
                    return None
                raise AssertionError('unexpected fixed command: ' + name)

            def root(self):
                self.frame()

            def frame(self, index=None):
                self.command('WebDriver:SwitchToFrame', {'id': index})

            def close(self):
                if not self.closed:
                    owner.terminate();owner.close();self.log.close();self.closed = True

        @contextmanager
        def workspace(evidence):
            path = evidence / 'private browser fixture';path.mkdir();yield path

        helper = SimpleNamespace(ChromiumBrowser=Base, browser_workspace=workspace,
            BrowserCleanupError=type('FixtureBrowserCleanupError', (RuntimeError,), {}),
            process_tree=SimpleNamespace(launch=Mock(return_value=owner)))

        class Resources:
            def __init__(self, deadline):
                self.deadline = deadline;self.calls = []

            def resource(self, phase, role):
                self.calls.append((phase, role))
                return phase + '/' + role, 'http://127.0.0.1:1/' + phase + '/' + role, role

            def count(self, path):
                return int(path.startswith('online/'))

            def control(self, phase):
                events.append(('listener-control', phase));return True

            def close(self):
                events.append(('listener-joined', True))

            def complete(self):
                fixture.assertEqual(len(self.calls), 9)

        class Response:
            def __init__(self, value):
                self.content = json.dumps({'value': value}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                fixture.assertLessEqual(len(self.content), limit);return self.content

        def opened(request, timeout):
            data = None if request.data is None else json.loads(request.data)
            path = request.full_url.removeprefix('http://127.0.0.1:1')
            events.append((request.method, path, data))
            if path == '/session':
                fixture.assertEqual(data['capabilities']['alwaysMatch']['goog:loggingPrefs'], {'browser': 'ALL'})
                return Response({'sessionId': 'unit', 'capabilities': capabilities})
            if path.endswith('/chromium/network_conditions'):
                if data is not None:
                    conditions.clear();conditions.update(data['network_conditions'])
                return Response(dict(conditions))
            if path.endswith('/execute/async'):
                fixture.assertIn(data['script'], (browser.CANARY_FETCH, browser.CANARY_WORKER))
                return Response({'response': '/online/' in data['args'][0]})
            if path.endswith('/execute/sync'):
                script = data['script']
                if script == browser.READ:
                    return Response('42' if any(item[0] == 'activated' for item in events) else '0')
                if script == browser.ACTION:
                    if data['args'][2] == 'activate':
                        events.append(('activated', True))
                    return Response(True)
                if '#status' in script:
                    return Response(fixture.scenario['title'])
                if "querySelectorAll('iframe')" in script:
                    return Response([{'sandbox': 'allow-scripts', 'srcdoc': True}])
                return Response(True)
            if path.endswith('/goog/cdp/execute'):
                fixture.assertEqual(data, {'cmd': 'Browser.close', 'params': {}});return Response({})
            return Response(None)

        work, evidence = self.root / 'transport work', self.root / 'transport evidence'
        work.mkdir();evidence.mkdir()
        runtime = self.root / 'untouched application.html';runtime.write_text('retained opaque application fixture')
        def process_identity(pid):
            if pid == 4242:
                raise FileNotFoundError()
            return ('124', 4244)
        with self.fixture.forbid_processes(), patch.object(browser, '_load_browser_helper', return_value=helper), \
                patch.object(browser, '_chromium_images', return_value=([], image, driver)), \
                patch.object(browser, '_CanaryResources', Resources), \
                patch.object(browser.urllib.request, 'build_opener', return_value=SimpleNamespace(open=opened)), \
                patch.object(browser, '_owned_children', return_value={4243}), \
                patch.object(browser, '_proc_identity', side_effect=process_identity):
            result = browser._execute_chromium(runtime, self.scenario, evidence, work, 20, {'HOME': str(work)})
        self.assertTrue(browser._validate_offline('chromium', result['offline']))
        self.assertEqual(result['direct_file_uri'], runtime.resolve().as_uri())
        self.assertEqual(runtime.read_text(), 'retained opaque application fixture')
        self.assertEqual(result['executed_tests'], [step['id'] for step in self.scenario['steps']])
        owner.terminate.assert_not_called();owner.finish.assert_called_once();owner.close.assert_called_once()
        self.assertLess(events.index(('listener-joined', True)), next(index for index, item in enumerate(events)
            if item[0] == 'POST' and item[1].endswith('/goog/cdp/execute')))
        self.assertEqual(helper.process_tree.launch.call_args.kwargs['env'], {'HOME': str(work)})


if __name__ == '__main__':
    unittest.main()
