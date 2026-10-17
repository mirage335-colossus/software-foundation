#!/usr/bin/env python3
"""Static admission tests using synthetic bytes; no native image is loaded.

The complete Stage-A groups built here are deliberately production-ineligible.
Header labels and unexecuted reports cannot establish actual engine behavior.
"""
import copy
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests' / 'fixtures'))

import appended_engine_document_contract as document
import appended_engine_native_consumer as consumer
import appended_engine_native as fixture
from dependency_archive import encoded


class NativeConsumerTests(unittest.TestCase):
    def build(self, **kwargs):
        temporary = tempfile.TemporaryDirectory(prefix='native-consumer-parser-')
        self.addCleanup(temporary.cleanup)
        return fixture.build_group(temporary.name, **kwargs)

    def arguments(self, built, **changes):
        arguments = {'expected_' + key: value for key, value in built['pins'].items()}
        arguments.update(kernel_target=built['target'], document_profile='pixel')
        arguments.update(changes)
        return arguments

    def inspect(self, built, **changes):
        return consumer.inspect_kernel_consumer(built['group'], **self.arguments(built, **changes))

    def embedded(self, built, **changes):
        arguments = {name: built[name] for name in ('evidence', 'assets', 'notices', 'pins')}
        arguments.update(kernel_target=built['target'], document_profile='pixel')
        arguments.update(changes)
        return consumer.inspect_embedded_consumer(**arguments)

    def refuses(self, mutate, pattern=None, **kwargs):
        built = self.build(mutate=mutate, **kwargs)
        context = self.assertRaises(consumer.NativeConsumerError) if pattern is None else self.assertRaisesRegex(consumer.NativeConsumerError, pattern)
        with context:
            self.inspect(built)

    def test_full_target_and_native_contract_helpers_own_their_inputs(self):
        for target, pair in ((fixture.LINUX_X86_64, (1, 1)), (fixture.LINUX_AARCH64, (1, 2)),
                             (fixture.WINDOWS_X86_64, (2, 1))):
            original = copy.deepcopy(target)
            selected = consumer.native_target(original)
            original['triple'] = 'changed-after-selection'
            self.assertEqual(selected, target)
            contract = consumer.provider_contract(kernel_target=target, document_profile='pixel')
            self.assertEqual(contract['target'], {'system': pair[0], 'processor': pair[1], 'pointer_bits': 64})
            profile = consumer.expected_engine_profile(kernel_target=target, document_profile='pixel',
                build_sha256='1' * 64, source_recipe_sha256='2' * 64)
            self.assertEqual(profile['binding'], 'private-native')
            self.assertEqual(profile['target'], target)
            self.assertEqual(profile['provider_abi_minor'], 1)
            self.assertEqual(profile['base_header_sha256'], document.BASE_HEADER_SHA256)
            self.assertEqual(profile['contract_sha256'], document.CONTRACT_SHA256)
            self.assertNotEqual(profile['base_header_sha256'], profile['contract_sha256'])

    def test_target_schema_rejects_ambiguous_or_unsupported_values(self):
        base = fixture.LINUX_X86_64
        invalid = [None, 'Linux', {**base, 'unknown': 1}, {**base, 'pointer_bits': True},
            {**base, 'pointer_bits': 32}, {**base, 'processor': 'wasm32'},
            {**base, 'system': 'Windows', 'processor': 'aarch64'},
            {key: value for key, value in base.items() if key != 'triple'}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(consumer.NativeConsumerError):
                consumer.native_target(value)

    def test_selectors_are_exact_and_physical_is_explicitly_unavailable(self):
        for selector in ('physical', 'physical2003', 'native', '', True):
            with self.subTest(selector=selector), self.assertRaises(consumer.NativeConsumerError):
                consumer.expected_configuration(document_profile=selector)
        built = self.build()
        with self.assertRaisesRegex(consumer.NativeConsumerError, 'physical2003'):
            self.inspect(built, document_profile='physical')

    def test_header_only_groups_inspect_on_each_supported_target_but_never_verify(self):
        for target in (fixture.LINUX_X86_64, fixture.LINUX_AARCH64, fixture.WINDOWS_X86_64):
            with self.subTest(target=target):
                built = self.build(target=target)
                result = self.inspect(built)
                metadata = result.as_dict()
                self.assertTrue(metadata['whole_group_verified'])
                self.assertFalse(metadata['production_eligible'])
                self.assertEqual(metadata['engine_profile']['target'], target)
                self.assertEqual(metadata['runtime_evidence']['scope'], 'parser-fixture-only')
                self.assertEqual(metadata['runtime_evidence']['status'], 'incomplete')
                self.assertTrue(all(check['status'] == 'not-run' for check in metadata['runtime_evidence']['checks'].values()))
                self.assertFalse(metadata['native_audit']['binary_scan_verified'])
                self.assertEqual(metadata['native_audit']['scope'], 'synthetic-header-only-no-binary-contract-proof')
                paths = [item['path'] for item in metadata['inventory']]
                self.assertEqual(paths, sorted(paths))
                self.assertIn('engine-sdk.json', paths)
                self.assertTrue(any(item['kind'] == 'directory' for item in metadata['inventory']))
                self.assertEqual(set(result.assets), set(built['assets']))
                with self.assertRaisesRegex(consumer.NativeConsumerError, 'production-ineligible'):
                    consumer.verify_kernel_consumer(built['group'], **self.arguments(built))

    def test_embedded_inspection_owns_immutable_bytes_and_has_no_whole_group_eligibility(self):
        built = self.build()
        result = self.embedded(built)
        self.assertFalse(result.metadata['whole_group_verified'])
        self.assertFalse(result.metadata['production_eligible'])
        self.assertIsNone(result.metadata['group_files'])
        entry = result.metadata['provider_entry']
        original = result.assets[entry]
        built['assets'][entry] = b'caller replaced bytes'
        built['evidence']['interfaces'].clear()
        built['pins'].clear()
        self.assertEqual(result.assets[entry], original)
        self.assertEqual(len(result.evidence['interfaces']), 5)
        copied = result.as_dict()
        copied['engine_profile']['target']['triple'] = 'caller mutation'
        self.assertEqual(result.metadata['engine_profile']['target']['triple'], fixture.LINUX_X86_64['triple'])
        for destination, key in ((result.metadata, 'production_eligible'), (result.assets, entry),
                                 (result.evidence['reports'], 'new')):
            with self.subTest(key=key), self.assertRaises(TypeError):
                destination[key] = b'not mutable'

    def test_all_four_independent_pins_are_required_and_checked(self):
        built = self.build()
        for key in ('recipe', 'manifest', 'proof', 'runtime'):
            with self.subTest(pin=key), self.assertRaises(consumer.NativeConsumerError):
                self.inspect(built, **{'expected_' + key: '3' * 64})
        for pins in ({**built['pins'], 'extra': '4' * 64}, {key: value for key, value in built['pins'].items() if key != 'runtime'}):
            with self.assertRaises(consumer.NativeConsumerError):
                self.embedded(built, pins=pins)

    def test_full_target_triple_is_part_of_consumer_selection(self):
        built = self.build()
        alternate = {**built['target'], 'triple': 'x86_64-pc-linux-gnu'}
        consumer.native_target(alternate)
        with self.assertRaisesRegex(consumer.NativeConsumerError, 'full target'):
            self.inspect(built, kernel_target=alternate)

    def test_new_proof_build_profile_runtime_and_nested_objects_are_closed(self):
        locations = (
            lambda s: s['proof'], lambda s: s['build'], lambda s: s['profile'],
            lambda s: s['runtime'], lambda s: s['runtime']['environment'],
            lambda s: s['runtime']['bootstrap'], lambda s: s['runtime']['provider_observation'],
            lambda s: s['proof']['native_facts'], lambda s: s['proof']['native_facts']['private_runtime'],
            lambda s: s['proof']['native_facts']['runtime_floor'],
            lambda s: next(iter(s['proof']['native_facts']['binaries'].values())),
            lambda s: next(iter(s['proof']['assets'].values())),
        )
        for number, location in enumerate(locations):
            with self.subTest(location=number):
                self.refuses(lambda state: location(state).__setitem__('browser_worker', 'ineligible'))

    def test_provider_build_and_profile_cannot_reuse_browser_binding_or_abi_minor_zero(self):
        changes = (
            lambda s: s['build'].__setitem__('binding', 'webkitwasm-copied259-v1'),
            lambda s: s['build']['configuration'].__setitem__('thread_model', 'worker'),
            lambda s: s['build']['configuration'].__setitem__('factory', 'engine.mjs'),
            lambda s: s['profile'].__setitem__('provider_abi_minor', 0),
            lambda s: s['profile'].__setitem__('maximum_starts', 2),
            lambda s: s['build'].__setitem__('contract_header_sha256', document.BASE_HEADER_SHA256),
        )
        for number, mutate in enumerate(changes):
            with self.subTest(change=number):
                self.refuses(mutate)

    def test_canonical_interface_aliases_are_refused_even_for_identical_bytes(self):
        for role in document.INTERFACE_PATHS:
            def alias(state, selected=role):
                reference = state['proof']['interfaces'][selected]
                previous = reference['path']
                reference['path'] = 'aliases/' + Path(previous).name
                state['interfaces'][reference['path']] = state['interfaces'].pop(previous)
                if selected == 'base_header':
                    state['binary']['provider']['header'] = reference['path']
                    state['recipe']['provider']['header'] = reference['path']
                    raw = state['source_bytes'][previous]
                    state['source_bytes'][reference['path']] = raw
                    state['recipe']['inputs'][reference['path']] = {'role': 'interface', 'sha256': fixture.sha(raw), 'mode': 0o644}
                    state['source_manifest']['files'][reference['path']] = fixture.sha(raw)
                    state['source_manifest']['modes'][reference['path']] = 0o644
                    state['source_manifest']['directories'].append('aliases')
                    state['source_manifest']['directories'].sort()
                    state['source_manifest']['modes']['aliases'] = 0o755
            with self.subTest(role=role):
                self.refuses(alias, 'noncanonical')

    def test_every_interface_requires_its_independent_source_interface_role(self):
        for role, path in document.INTERFACE_PATHS.items():
            with self.subTest(role=role):
                mutate = lambda state, selected=path: state['recipe']['inputs'][selected].__setitem__('role', 'source')
                if role == 'base_header':
                    with self.assertRaisesRegex(ValueError, 'provider header differs from source input'):
                        self.build(mutate=mutate)
                else:
                    self.refuses(mutate, 'original source recipe')

    def test_canonical_binary_interface_cannot_replace_missing_original_source(self):
        path = document.INTERFACE_PATHS['extension_header']
        def missing(state):
            state['source_bytes'].pop(path)
            state['source_manifest']['files'].pop(path)
            state['source_manifest']['modes'].pop(path)
            state['recipe']['inputs'].pop(path)
        self.refuses(missing, 'original source recipe')

    def test_interface_digest_and_actual_bytes_are_independently_bound(self):
        path = document.INTERFACE_PATHS['action_ack_schema']
        self.refuses(lambda state: state['interfaces'].__setitem__(path, state['interfaces'][path] + b'\n'))
        self.refuses(lambda state: state['proof']['interfaces']['action_ack_schema'].__setitem__('sha256', '5' * 64))

    def test_native_asset_roles_and_provider_entry_are_not_inferred_from_names(self):
        def role(state, value):
            state['proof']['assets'][state['binary']['provider']['entry']]['role'] = value
        for value in ('wasm', 'factory', 'data', 'dependency'):
            with self.subTest(role=value):
                self.refuses(lambda state: role(state, value))

    def test_windows_requires_explicit_import_library_role(self):
        self.refuses(lambda state: state['proof']['assets']['lib/fixture-engine.lib'].__setitem__('role', 'data'),
            'import library', target=fixture.WINDOWS_X86_64)
        self.refuses(lambda state: state['proof']['assets']['share/parser-fixture.dat'].__setitem__('role', 'import-library'),
            'Windows .lib')

    def test_actual_asset_bytes_must_match_declared_size_digest_and_ownership(self):
        built = self.build()
        entry = self.inspect(built).metadata['provider_entry']
        for value in (built['assets'][entry] + b'x', bytearray(built['assets'][entry]), memoryview(built['assets'][entry])):
            changed = dict(built['assets']); changed[entry] = value
            with self.subTest(value_type=type(value).__name__), self.assertRaises(consumer.NativeConsumerError):
                self.embedded(built, assets=changed)
        self.refuses(lambda state: next(iter(state['proof']['assets'].values())).__setitem__('bytes', 1))

    def test_header_machine_and_dll_shape_are_checked_after_resealing_asset_hashes(self):
        for target in (fixture.LINUX_X86_64, fixture.WINDOWS_X86_64):
            def changed(state):
                entry = state['binary']['provider']['entry']
                raw = bytearray(state['assets'][entry])
                if target['system'] == 'Linux':struct.pack_into('<H', raw, 18, 183)
                else:struct.pack_into('<H', raw, 128 + 22, 0x22)
                state['assets'][entry] = bytes(raw)
                state['proof']['assets'][entry]['sha256'] = fixture.sha(bytes(raw))
            with self.subTest(target=target):
                self.refuses(changed, 'machine|DLL', target=target)

    def test_extra_embedded_asset_notice_report_or_interface_has_no_unassigned_escape(self):
        built = self.build()
        for name in ('assets', 'notices'):
            values = {**built[name], 'extra/unassigned.bin': b'unassigned'}
            with self.subTest(name=name), self.assertRaises(consumer.NativeConsumerError):
                self.embedded(built, **{name: values})
        for name in ('reports', 'interfaces'):
            evidence = copy.deepcopy(built['evidence'])
            evidence[name]['extra/unassigned.bin'] = b'unassigned'
            with self.subTest(name=name), self.assertRaises(consumer.NativeConsumerError):
                self.embedded(built, evidence=evidence)

    def test_complete_group_checksums_and_members_remain_stage_a_gates(self):
        built = self.build()
        archive = next(built['group'].glob('*.tar.gz'))
        with archive.open('ab') as stream:
            stream.write(b'changed after retained checksum')
        with self.assertRaises(consumer.NativeConsumerError):
            self.inspect(built)

    def test_paths_are_portable_case_unambiguous_and_cannot_traverse(self):
        built = self.build()
        for path in ('../escape', '/absolute', 'data\\file', 'C:/drive'):
            changed = {**built['assets'], path: b'ineligible'}
            with self.subTest(path=path), self.assertRaises(consumer.NativeConsumerError):
                self.embedded(built, assets=changed)
        def collision(state):
            path = 'SHARE/parser-fixture.dat'
            raw = b'case collision'
            state['assets'][path] = raw
            state['proof']['assets'][path] = {'role': 'data', 'sha256': fixture.sha(raw), 'bytes': len(raw), 'mode': 0o644}
            state['binary']['provider']['assets'].append(path)
            state['binary']['provider']['assets'].sort()
        with self.assertRaises((ValueError, consumer.NativeConsumerError)):
            self.inspect(self.build(mutate=collision))

    def test_private_retained_dependency_is_explicit_and_source_only_inspectable(self):
        for target in (fixture.LINUX_X86_64, fixture.WINDOWS_X86_64):
            with self.subTest(target=target):
                result = self.inspect(self.build(target=target, with_dependency=True))
                self.assertFalse(result.metadata['production_eligible'])
                self.assertEqual(len(result.metadata['native_facts']['dependencies']), 1)
                self.assertEqual(result.metadata['native_facts']['dependencies'][0]['kind'], 'retained')

    def test_dependency_graph_rejects_missing_edges_ambient_search_and_unowned_system_names(self):
        self.refuses(lambda state: state['proof']['native_facts']['dependencies'].clear(), with_dependency=True)
        self.refuses(lambda state: state['proof']['native_facts']['private_runtime'].__setitem__('ambient_search', True))
        self.refuses(lambda state: state['proof']['native_facts']['private_runtime'].__setitem__('unique_dependencies', False))
        def unowned(state):
            facts = state['proof']['native_facts']
            next(iter(facts['binaries'].values()))['needed'] = ['unowned-ambient.so']
            facts['dependencies'] = [{'library': 'unowned-ambient.so', 'kind': 'system', 'path': None, 'sha256': None}]
        self.refuses(unowned, 'system policy')
        self.refuses(lambda state: next(iter(state['proof']['native_facts']['binaries'].values())).__setitem__('runpath', ['/usr/local/lib']), 'RUNPATH')

    def test_external_symbol_versions_cannot_exceed_declared_or_bookworm_floor(self):
        def imported(state, version):
            facts = state['proof']['native_facts']
            item = next(iter(facts['binaries'].values()))
            item['needed'] = ['libc.so.6']
            item['imports'] = [{'library': 'libc.so.6', 'symbol': 'puts', 'version': version}]
            facts['dependencies'] = [{'library': 'libc.so.6', 'kind': 'system', 'path': None, 'sha256': None}]
        for version in ('GLIBC_2.37', 'GLIBC_PRIVATE', 'GLIBCXX_3.4.30'):
            with self.subTest(version=version):
                self.refuses(lambda state: imported(state, version), 'symbol version|version namespace')
        self.refuses(lambda state: state['proof']['native_facts']['runtime_floor'].__setitem__('GLIBC', '2.37'), 'Debian 12')

    def test_provider_limits_require_exact_shape_integer_types_and_shared_bounds(self):
        defaults = fixture.default_limits()
        self.assertEqual(consumer.validate_provider_limits(defaults), defaults)
        changes = ({'reserved': 1}, {'size': 40}, {'maximum_query_bytes': True},
            {'maximum_retired_documents': 9}, {'maximum_reply_bytes': 1048575},
            {'maximum_resource_response_bytes': 100, 'maximum_retained_resource_bytes': 99},
            {'wasm_pages': 64})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(consumer.NativeConsumerError):
                consumer.validate_provider_limits({**defaults, **change})
        self.refuses(lambda state: state['runtime']['provider_observation']['provider_limits'].__setitem__('maximum_query_bytes', 32768), 'observation')

    def test_original_getter_table_environment_and_bootstrap_are_bound(self):
        changes = (
            lambda s: s['runtime']['provider_observation'].__setitem__('maximum_minor', 0),
            lambda s: s['runtime']['provider_observation'].__setitem__('status', 1),
            lambda s: s['runtime']['bootstrap'].__setitem__('maximum_minor', 0),
            lambda s: s['runtime']['bootstrap']['checks'].__setitem__('one_process_start', True),
            lambda s: s['runtime']['environment'].__setitem__('loader_flags', ['RTLD_GLOBAL', 'RTLD_NOW']),
            lambda s: s['runtime']['checks'].__setitem__('unrecognized-native-check', {'status': 'not-run', 'evidence': []}),
        )
        for number, mutate in enumerate(changes):
            with self.subTest(change=number):
                self.refuses(mutate)

    def test_passed_check_requires_original_report_and_report_references_cannot_alias_assets(self):
        self.refuses(lambda state: state['runtime']['checks']['native-service-result-and-ack'].__setitem__('status', 'passed'), 'requires original')
        def alias(state):
            path = state['binary']['provider']['entry']
            state['proof']['native_facts']['evidence'] = [{'path': path, 'sha256': fixture.sha(state['assets'][path])}]
        self.refuses(alias, 'report role')
        def duplicate(state):
            reference = state['proof']['native_facts']['evidence'][0]
            state['proof']['native_facts']['evidence'].append(dict(reference))
        self.refuses(duplicate, 'duplicate')

    def test_fixture_builder_cannot_claim_actual_runtime_and_header_only_relabel_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='native-fixture-refusal-') as directory:
            with self.assertRaisesRegex(ValueError, 'cannot claim actual'):
                fixture.build_group(directory, scope='retained-native-provider-runtime')
        self.refuses(lambda state: state['runtime'].__setitem__('scope', 'retained-native-provider-runtime'), 'ELF|section|program|table')

    def audit_refusal_inputs(self, *, windows=False, retained=False, unversioned=False):
        """Only invalid direct-helper audit inputs, never a retained runtime group.

        These artificial assertions are intentionally not exposed by the fixture
        builder and are never sent to inspect/verify or used as runtime facts.
        Every caller must introduce a named refusal before invoking the helper.
        """
        target = fixture.WINDOWS_X86_64 if windows else fixture.LINUX_X86_64
        built = self.build(target=target, with_dependency=retained)
        proof = copy.deepcopy(built['documents']['proof'])
        runtime = copy.deepcopy(built['documents']['runtime'])
        facts = proof['native_facts']
        requester = built['documents']['binary']['provider']['entry']
        if retained:
            dependency = facts['dependencies'][0]
            library = dependency['library']
            symbol = 'fixture_function'
            facts['binaries'][dependency['path']]['exports'] = [symbol]
        else:
            library = 'KERNEL32.dll' if windows else 'libc.so.6'
            symbol = 'Sleep' if windows else 'puts'
            dependency = {'library': library, 'kind': 'system', 'path': None, 'sha256': None}
            facts['dependencies'] = [dependency]
        binary = facts['binaries'][requester]
        binary['needed'] = [library]
        binary['imports'] = [{'library': None if unversioned else library, 'symbol': symbol, 'version': None}]
        root = 'C:/parser-fixture/runtime' if windows else '/parser-fixture/runtime'
        resolved = (root + '/' + dependency['path'] if retained else
                    'C:/Windows/System32/KERNEL32.dll' if windows else '/lib/x86_64-linux-gnu/libc.so.6')
        identity = {**dependency, 'resolved_path': resolved,
                    'resolved_sha256': dependency['sha256'] if retained else '6' * 64}
        audit = {'schema_version': 1, 'kind': 'foundation-native-dso-audit-v1',
            'scope': 'actual-native-binary-audit', 'executed': True, 'target': copy.deepcopy(target),
            'assets_sha256': fixture.sha(encoded(proof['assets'])),
            **{name + '_sha256': fixture.sha(encoded(facts[name])) for name in ('binaries', 'dependencies', 'runtime_floor', 'private_runtime')},
            'environment': copy.deepcopy(runtime['environment']), 'runtime_root': root,
            'tools': [{'name': 'synthetic-refusal-test-only', 'version': 'unexecuted', 'sha256': '7' * 64}],
            'outputs': [{'path': 'reports/artificial-refusal.txt', 'sha256': fixture.sha(b'Never executed; negative helper input only.')}],
            'library_resolutions': [{'requester': requester, **identity}],
            'import_resolutions': [{'requester': requester, 'symbol': symbol, 'version': None, **identity}]}
        reports = {'reports/artificial-refusal.txt': b'Never executed; negative helper input only.'}
        return facts, proof, runtime, reports, target, audit

    def refuse_audit(self, inputs, pattern):
        facts, proof, runtime, reports, target, audit = inputs
        path = 'reports/artificial-refusal.json'
        reports[path] = encoded(audit)
        facts['evidence'] = [{'path': path, 'sha256': fixture.sha(reports[path])}]
        with self.assertRaisesRegex(consumer.NativeConsumerError, pattern):
            consumer._audit_closure(facts, proof, runtime, reports, target)

    def test_actual_audit_cannot_replace_dependency_paths_with_different_system_libraries(self):
        for windows, wrong in ((False, '/lib/x86_64-linux-gnu/libm.so.6'),
                               (True, 'C:/Windows/System32/user32.dll')):
            inputs = self.audit_refusal_inputs(windows=windows)
            inputs[-1]['library_resolutions'][0]['resolved_path'] = wrong
            with self.subTest(windows=windows):
                self.refuse_audit(inputs, 'system ELF dependency|system DLL name')

    def test_actual_audit_allows_only_explicit_api_set_host_aliases(self):
        inputs = self.audit_refusal_inputs(windows=True)
        facts, proof, _, _, _, audit = inputs
        requested = 'api-ms-win-crt-runtime-l1-1-0.dll'
        facts['dependencies'][0]['library'] = requested
        provider = next(iter(facts['binaries'].values()))
        provider['needed'] = [requested]
        provider['imports'][0]['library'] = requested
        audit['binaries_sha256'] = fixture.sha(encoded(facts['binaries']))
        audit['dependencies_sha256'] = fixture.sha(encoded(facts['dependencies']))
        audit['assets_sha256'] = fixture.sha(encoded(proof['assets']))
        for item in audit['library_resolutions'] + audit['import_resolutions']:
            item['library'] = requested
            item['resolved_path'] = 'C:/Windows/System32/kernelbase.dll'
        self.refuse_audit(inputs, 'system DLL name')

    def test_actual_audit_needs_every_scanned_import_even_when_elf_library_is_unversioned(self):
        inputs = self.audit_refusal_inputs(unversioned=True)
        inputs[-1]['import_resolutions'].clear()
        self.refuse_audit(inputs, 'symbol resolutions are incomplete')

    def test_actual_audit_rejects_conflicting_loaded_identity_between_needed_and_import(self):
        inputs = self.audit_refusal_inputs()
        inputs[-1]['import_resolutions'][0]['resolved_sha256'] = '8' * 64
        self.refuse_audit(inputs, 'conflicting loaded paths/digests')

    def test_actual_audit_retained_symbol_supplier_must_export_name_and_ordinals_are_not_admitted(self):
        inputs = self.audit_refusal_inputs(retained=True)
        facts, _, _, _, _, audit = inputs
        supplier = facts['dependencies'][0]['path']
        facts['binaries'][supplier]['exports'] = []
        audit['binaries_sha256'] = fixture.sha(encoded(facts['binaries']))
        self.refuse_audit(inputs, 'does not actually export')
        inputs = self.audit_refusal_inputs(windows=True, retained=True)
        facts, _, _, _, _, audit = inputs
        requester = audit['import_resolutions'][0]['requester']
        facts['binaries'][requester]['imports'][0]['symbol'] = '#7'
        audit['import_resolutions'][0]['symbol'] = '#7'
        audit['binaries_sha256'] = fixture.sha(encoded(facts['binaries']))
        self.refuse_audit(inputs, 'ordinal DLL imports')

    def test_actual_private_search_refuses_earlier_extant_inventory_candidate(self):
        built = self.build(with_dependency=True)
        proof = copy.deepcopy(built['documents']['proof'])
        facts = proof['native_facts']
        entry = built['documents']['binary']['provider']['entry']
        library = facts['dependencies'][0]['library']
        facts['binaries'][entry]['runpath'] = ['$ORIGIN/decoy', '$ORIGIN']
        scanned_by_bytes = {}
        assets = dict(built['assets'])
        # Distinct synthetic header bytes let a strict-scan test double isolate
        # lookup order. No admitted group/result or binary-proof claim is made.
        for index, (path, value) in enumerate(facts['binaries'].items()):
            assets[path] += bytes([index])
            scanned_by_bytes[assets[path]] = value
        inventory = set(assets) | {'lib/decoy/' + library}
        with mock.patch.object(consumer, 'scan_native_binary', side_effect=lambda raw: copy.deepcopy(scanned_by_bytes[raw])):
            with self.assertRaisesRegex(consumer.NativeConsumerError, 'not reachable'):
                consumer._native_facts(proof, assets, built['target'], actual=True, inventory_paths=inventory)

    def test_limits_bound_members_assets_reports_and_owned_byte_types(self):
        for change in ({'max_assets': 1}, {'max_members': 1}, {'max_native_member_bytes': 63},
                       {'max_reports_total_bytes': 1}, {'max_notice_bytes': 1}, {'max_data_member_bytes': 1}):
            built = self.build()
            with self.subTest(change=change), self.assertRaises(consumer.NativeConsumerError):
                self.inspect(built, limits=consumer.NativeConsumerLimits(**change))
        for value in (True, 0, -1):
            with self.assertRaises(consumer.NativeConsumerError):
                consumer.NativeConsumerLimits(max_assets=value)
        built = self.build()
        with self.assertRaises(consumer.NativeConsumerError):
            self.inspect(built, limits={'max_assets': 1})
        for name in ('recipe', 'proof', 'runtime'):
            evidence = copy.deepcopy(built['evidence'])
            evidence[name] = bytearray(evidence[name])
            with self.subTest(name=name), self.assertRaises(consumer.NativeConsumerError):
                self.embedded(built, evidence=evidence)


    def actions_arguments(self, built, **changes):
        arguments = {'expected_' + key: value for key, value in built['pins'].items()}
        arguments.update(kernel_target=built['target'], actions_profile='document-actions-v1')
        arguments.update(changes)
        return arguments

    def inspect_actions(self, built, **changes):
        return consumer.inspect_actions_kernel_consumer(built['group'], **self.actions_arguments(built, **changes))

    def test_actions_supported_targets_inspect_but_synthetic_groups_never_qualify(self):
        import appended_engine_native_actions_contract as actions
        for target in (fixture.LINUX_X86_64, fixture.LINUX_AARCH64, fixture.WINDOWS_X86_64):
            with self.subTest(target=target):
                built = self.build(target=target, actions_profile=actions.SELECTOR)
                result = self.inspect_actions(built)
                metadata = result.as_dict()
                self.assertEqual(metadata['scope'], actions.SCOPE)
                self.assertTrue(metadata['whole_group_verified'])
                self.assertFalse(metadata['production_eligible'])
                self.assertEqual(metadata['engine_profile']['kind'], actions.PROFILE_KIND)
                self.assertEqual(metadata['engine_profile']['target'], target)
                self.assertEqual(metadata['engine_profile']['profile_kind'], 4)
                self.assertEqual(metadata['engine_profile']['capabilities'], '4083')
                self.assertEqual(len(metadata['interfaces']), 16)
                self.assertEqual(len(metadata['runtime_evidence']['checks']), 35)
                self.assertEqual(len(metadata['provider_contract']['queries']), 2)
                self.assertEqual([item['operation'] for item in metadata['provider_contract']['commands']], [1,3,5,6,7,8,9,10,11])
                self.assertEqual(metadata['provider_limits'], dict(actions.PROVIDER_LIMITS))
                with self.assertRaisesRegex(consumer.NativeConsumerError, 'production-ineligible'):
                    consumer.verify_actions_kernel_consumer(built['group'], **self.actions_arguments(built))
                embedded = consumer.inspect_embedded_actions_consumer(**{name:built[name] for name in ('evidence','assets','notices','pins')},
                    kernel_target=built['target'], actions_profile=actions.SELECTOR)
                self.assertEqual(embedded.metadata['scope'], actions.EMBEDDED_SCOPE)
                self.assertFalse(embedded.metadata['whole_group_verified'])
                self.assertFalse(embedded.metadata['production_eligible'])

    def test_actions_and_pixel_admission_are_bidirectionally_closed(self):
        for is_actions in (False, True):
            built = self.build(**({'actions_profile':'document-actions-v1'} if is_actions else {}))
            with self.subTest(actions=is_actions), self.assertRaises(consumer.NativeConsumerError):
                self.inspect(built) if is_actions else self.inspect_actions(built)
        for selector in ('pixel','actions','4083',4,True,None):
            with self.subTest(selector=selector), self.assertRaises(consumer.NativeConsumerError):
                consumer.expected_actions_configuration(actions_profile=selector)
        with self.assertRaises(consumer.NativeConsumerError):
            consumer.expected_configuration(document_profile='document-actions-v1')
        built = self.build()
        with self.assertRaises(consumer.NativeConsumerError):
            consumer.inspect_kernel_consumer(built['group'], **self.arguments(built), actions_profile='document-actions-v1')

    def test_actions_new_and_inherited_schema_fields_pin_and_kind_are_exact(self):
        import appended_engine_native_actions_contract as actions
        mutations = [lambda s:s['profile'].update(profile_kind=3),
            lambda s:s['profile'].update(capabilities='2035'),
            lambda s:s['profile'].update(actions_profile='foundation-engine-copied2035-ndv2-editor-v1'),
            lambda s:s['profile'].update(document_profile=document.PROFILE_NAMES['pixel']),
            lambda s:s['profile'].update(surface_protocol_version=1),
            lambda s:s['build'].update(kind=consumer.BUILD_KIND),
            lambda s:s['proof'].update(kind=consumer.PROOF_KIND),
            lambda s:s['runtime'].update(kind=consumer.RUNTIME_KIND),
            lambda s:s['build']['configuration'].update(kind='native-dso-private-runtime-v1')]
        for key in actions.PROFILE_FIELDS:
            if key.endswith('sha256') and key not in ('build_sha256','source_recipe_sha256'):
                mutations.append(lambda s,key=key:s['profile'].__setitem__(key,'3'*64))
        for mutate in mutations:
            built = self.build(actions_profile=actions.SELECTOR, mutate=mutate)
            with self.subTest(mutate=mutate), self.assertRaises(consumer.NativeConsumerError):
                self.inspect_actions(built)

    def test_actions_catalog_and_all_fixed_native_limits_are_bound(self):
        import appended_engine_native_actions_contract as actions
        mutations = [lambda s:s['build']['provider_contract']['commands'].pop(),
            lambda s:s['build']['provider_contract']['queries'].pop(),
            lambda s:s['build']['provider_contract']['commands'][-1].update(operation=7),
            lambda s:s['build']['provider_contract']['commands'][-2].update(schema_sha256=document.DOCUMENT_SCHEMA_SHA256)]
        for key,value in actions.PROVIDER_LIMITS.items():
            mutations.append(lambda s,key=key,value=value:s['build']['provider_limits'].__setitem__(key,value+1))
            mutations.append(lambda s,key=key,value=value:s['build']['provider_limits'].__setitem__(key,True))
        for mutate in mutations:
            built = self.build(actions_profile=actions.SELECTOR, mutate=mutate)
            with self.subTest(mutate=mutate), self.assertRaises(consumer.NativeConsumerError):
                self.inspect_actions(built)

    def test_actions_all_original_interface_roles_and_source_bindings_are_required(self):
        import appended_engine_native_actions_contract as actions
        for role,path in actions.INTERFACE_PATHS.items():
            for index,mutate in enumerate((
                lambda s,role=role:s['proof']['interfaces'][role].update(sha256='4'*64),
                lambda s,role=role:s['proof']['interfaces'][role].update(path='other/'+role),
                lambda s,path=path:s['recipe']['inputs'][path].update(role='source'))):
                if role == 'base_header' and index == 2:
                    # The existing Stage-A provider contract rejects its own
                    # header's wrong source role before consumer inspection.
                    with self.subTest(role=role), self.assertRaisesRegex(ValueError, 'provider header'):
                        self.build(actions_profile=actions.SELECTOR, mutate=mutate)
                    continue
                built = self.build(actions_profile=actions.SELECTOR, mutate=mutate)
                with self.subTest(role=role), self.assertRaises(consumer.NativeConsumerError):
                    self.inspect_actions(built)

    def test_actions_independent_pins_full_target_and_runtime_gates_remain_required(self):
        built = self.build(actions_profile='document-actions-v1')
        for key in ('recipe','manifest','proof','runtime'):
            with self.subTest(pin=key), self.assertRaises(consumer.NativeConsumerError):
                self.inspect_actions(built, **{'expected_'+key:'5'*64})
        with self.assertRaisesRegex(consumer.NativeConsumerError, 'full target'):
            self.inspect_actions(built, kernel_target={**built['target'],'triple':'x86_64-pc-linux-gnu'})
        # Header-only native assets cannot claim actual runtime merely by a
        # relabeled scope/status/check map. Existing static DSO audit still runs.
        def claim(s):
            s['runtime']['scope']='retained-native-provider-runtime';s['runtime']['status']='passed'
            for item in s['runtime']['checks'].values():item['status']='passed';item['evidence']=s['proof']['native_facts']['evidence']
            for key in s['runtime']['bootstrap']['checks']:s['runtime']['bootstrap']['checks'][key]='passed'
            for key in ('loader_resolution','conflicting_preload'):s['proof']['native_facts']['private_runtime'][key]='passed'
        claimed=self.build(actions_profile='document-actions-v1',mutate=claim)
        with self.assertRaises(consumer.NativeConsumerError):
            consumer.verify_actions_kernel_consumer(claimed['group'], **self.actions_arguments(claimed))

    def test_actions_cli_is_explicit_and_mutually_exclusive(self):
        import contextlib,io,json
        built=self.build(actions_profile='document-actions-v1')
        target=built['group'].parent/'target.json';target.write_bytes(encoded(built['target']))
        args=['inspect','--group',str(built['group']),'--kernel-target-json',str(target),'--actions-profile','document-actions-v1']
        for name,pin in built['pins'].items():args += ['--'+name+'-sha256',pin]
        output=io.StringIO()
        with contextlib.redirect_stdout(output):self.assertEqual(consumer.main(args),0)
        self.assertEqual(json.loads(output.getvalue())['engine_profile']['profile_kind'],4)
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            consumer.main(args+['--document-profile','pixel'])



if __name__ == '__main__':
    unittest.main()
