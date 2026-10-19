"""Source checks and an explicitly selected bounded rich4083 Guard/Once probe.

The opt-in CLI compiles only pure helpers and fake callbacks, never WebCore or a
provider DSO. Every compiler and runtime process is supervised, and evidence is
retained at the caller's fresh private output directory on success or failure.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path('recipes/webkitwasm-native-rich4083-v1/source')
RECIPE = NATIVE.parent
FIXTURE = Path('tests/appended_engine_native_actions_bootstrap_test.cpp')
SCHEDULER = Path('tests/fixtures/appended_native_bootstrap/FixtureScheduler.hpp')
GUARDS = {
    'rich': (NATIVE / 'foundation/third_party/appended-engine/src/ProviderGuard.cpp',
             '3aebfcc5b4e838846f23a5c9c61a62acc51fecc73541fd58deaa9c157308b0ff',
             'e19476baf039231cd4053b915f52f91fce0e25dd16c56083f5cd299fb9ac47a7'),
}
ONCE_SHA256 = '3848f57570997b6885642cf507094c99f7a1823f6932a77659b45cdf316a34ef'
COMMON_SOURCES = (
    ('preflight', NATIVE / 'provider-binding/binding/BibEngineProviderPreflight.cpp'),
    ('resource-url', NATIVE / 'wrapper/src/embedder/resource_url.cpp'),
    ('actions-codec', NATIVE / 'document-provider/portable/NativeDocumentActionsV1Codec.cpp'),
    ('document-codec', NATIVE / 'document-provider/portable/NativeDocumentV2Codec.cpp'),
    ('document-types', NATIVE / 'document-provider/portable/NativeDocumentV2Types.cpp'),
    ('foundation-forms', NATIVE / 'foundation/src/appended/document_forms.cpp'),
    ('foundation-abi', NATIVE / 'foundation/src/appended/abi.cpp'),
)
FROZEN_HELPERS = tuple((Path('tools') / name, RECIPE / 'helpers/tools' / name) for name in (
    'dependency_archive.py', 'appended_engine_manifest.py', 'appended_engine_sdk.py',
    'appended_engine_document_contract.py', 'appended_engine_editor_contract.py',
    'appended_engine_native_actions_contract.py'))
CANONICAL_JOINS = (
    (Path('third_party/appended-engine/src/ProviderGuard.cpp'),
        NATIVE / 'foundation/third_party/appended-engine/src/ProviderGuard.cpp'),
    (Path('third_party/appended-engine/include/EnginePrivate.hpp'),
        NATIVE / 'foundation/third_party/appended-engine/include/EnginePrivate.hpp'),
) + tuple((Path('third_party/appended-engine/portable') / name,
            NATIVE / 'document-provider/portable' / name) for name in (
    'NativeDocumentActionsV1Codec.cpp', 'NativeDocumentActionsV1Codec.hpp',
    'NativeDocumentV2Codec.cpp', 'NativeDocumentV2Codec.hpp',
    'NativeDocumentV2Types.cpp', 'NativeDocumentV2Types.hpp')) + tuple(
    (Path(name), NATIVE / 'foundation' / name) for name in (
    'include/foundation/appended/document_forms.hpp', 'include/foundation/appended/abi.h',
    'include/foundation/appended/registry.hpp', 'src/appended/document_forms.cpp', 'src/appended/abi.cpp',
    'abi/appended/engine_editor_protocol.h', 'include/foundation/appended/engine_provider.h',
    'include/foundation/appended/engine_provider_document_v2.h',
    'include/foundation/appended/engine_provider_document_actions_v1.h')) + (
    (Path('gui/shared/engine_editor_pins.hpp'), NATIVE / 'document-provider/portable/engine_editor_pins.hpp'),
)
RECHECK = b'''            // START can commit between the fast owner check and acquisition.
            // Recheck the published owner under the gate before retained state.
            if (locked && require_owner
                && value.phase.load(std::memory_order_acquire) != BIB_ENGINE_START_NOT_RETAINED
                && value.owner != std::this_thread::get_id()) {
                value.busy.clear(std::memory_order_release);
                locked = false;
                status = BIB_ENGINE_WRONG_THREAD;
            }
'''
POINT = b'            locked = !value.busy.test_and_set(std::memory_order_acquire);\n'
HOOK = b'            if (require_owner) bib_native_fixture_gate_pause_v1();\n'
CASES = (
    'null-output', 'wrong-major', 'short-capacity', 'minor0',
    'rejected-then-accepted', 'higher-max-minor', 'repeated-owner-getter',
    'ready-foreign-getter', 'concurrent-binding', 'binding-before-owner-written',
    'same-thread-recursive-getter', 'known-unsupported', 'known-invalid',
    'known-limit', 'uncertain-throw', 'uncertain-after-bind',
    'wrong-thread-start-then-owner', 'malformed-start-then-owner', 'repeated-start',
    'foreign-start-after-ready', 'initial-phase-gate-race',
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_joins(base):
    if len(CANONICAL_JOINS) != 18:
        raise ValueError('reviewed eighteen-source canonical join closure changed')
    records = []
    for canonical, rich in CANONICAL_JOINS:
        canonical_raw, rich_raw = (base / canonical).read_bytes(), (base / rich).read_bytes()
        if canonical_raw != rich_raw:
            raise ValueError('canonical source differs from compiled rich source: ' + str(canonical))
        records.append({'canonical': canonical.as_posix(), 'compiled_rich_source': rich.as_posix(),
                        'sha256': digest(rich_raw), 'bytes': len(rich_raw)})
    return records


def instrument(raw, *, old=False):
    if raw.count(POINT) != 1 or raw.count(RECHECK) != 1 or HOOK in raw:
        raise ValueError('Guard scheduling/recheck preimage changed')
    selected = raw.replace(RECHECK, b'') if old else raw
    result = selected.replace(POINT, HOOK + POINT)
    if result.replace(HOOK, b'') != selected:
        raise ValueError('fixture instrumentation changed production bytes')
    return result


def inputs():
    # Compile only the rich source family. Canonical duplicate paths are frozen
    # as byte-identity proof inputs and excluded from compiler admission below.
    common = [FIXTURE, SCHEDULER, Path(__file__).relative_to(ROOT), Path('tools/process_tree.py'),
              NATIVE / 'native/BibNativeProviderOnce.hpp',
              NATIVE / 'native/BibNativeProviderBootstrap.hpp',
              NATIVE / 'document-provider/runtime/BibCopiedDocumentCatalog.hpp',
              NATIVE / 'provider-binding/binding/BibEngineProviderPreflight.h',
              NATIVE / 'wrapper/src/embedder/resource_url.hpp',
              NATIVE / 'document-provider/portable/appended_engine_input_profile.hpp',
              NATIVE / 'document-provider/portable/engine_editor_protocol.h',
              NATIVE / 'document-provider/portable/engine_editor_pins.hpp',
              NATIVE / 'foundation/abi/appended/engine_editor_protocol.h',
              NATIVE / 'foundation/third_party/appended-engine/include/LegacyHostAdapters.hpp',
              NATIVE / 'foundation/third_party/appended-engine/include/EnginePrivate.hpp']
    common += [path for _, path in COMMON_SOURCES]
    common += [NATIVE / 'document-provider/portable' / name for name in (
        'NativeDocumentActionsV1Codec.hpp', 'NativeDocumentV2Codec.hpp', 'NativeDocumentV2Types.hpp')]
    common += [NATIVE / 'foundation/include/foundation/appended' / name for name in (
        'engine_provider.h', 'engine_provider_document_v2.h', 'engine_provider_document_actions_v1.h',
        'document_forms.hpp', 'registry.hpp', 'abi.h')]
    common += [NATIVE / 'foundation/third_party/appended-engine/include/legacy' / name for name in (
        'BibAppResourceHost.h', 'BibFoundationServiceHost.h')]
    common += [Path('tests/test_appended_engine_native_actions_metadata.py'),
               Path('recipes/webkitwasm-native-rich4083-v1/runtime/generate_native_actions_metadata.py'),
               Path('recipes/webkitwasm-native-rich4083-v1/runtime/native-provider-actions-metadata.h.in'),
               Path('recipes/webkitwasm-native-rich4083-v1/prelink-config.json')]
    common += [origin for _, origin in FROZEN_HELPERS]
    common += [NATIVE / 'foundation/abi/engine/document-v2' / name for name in (
        'contract.json', 'catalog.json', 'schema-definition.json', 'action-ack.json')]
    common += [NATIVE / 'foundation/abi/engine/document-actions-v1' / name for name in (
        'contract.json', 'catalog.json', 'binary-schema.json', 'action-ack.json')]
    common += [NATIVE / 'foundation/abi/appended/editor-v1' / name for name in (
        'contract.json', 'catalog.json', 'binary-schema.json')]
    common += [NATIVE / 'foundation/abi/engine/physical-v1/catalog.json']
    common += [path for pair in CANONICAL_JOINS for path in pair]
    return sorted(set(common + [record[0] for record in GUARDS.values()]))


def run_probe(output):
    sys.dont_write_bytecode = True
    started = time.monotonic()
    deadline = started + 84  # Six seconds reserved for cleanup within the 90s grant.
    if sys.platform != 'linux' or os.name != 'posix' or os.uname().machine != 'x86_64':
        raise ValueError('this focused compiler probe is admitted only on Linux x86_64')
    output = output.absolute()
    output.mkdir(mode=0o700)  # Refuse preexisting evidence/output directories.
    original = {}
    commands = []
    records_lock = threading.Lock()
    cancelled = threading.Event()
    snapshot = output / 'source'
    snapshot.mkdir()
    result = {'scope': 'fake-native-rich4083-actual-guard-once-only', 'production_eligible': False,
              'engine_compiled': False, 'provider_dso_built': False,
              'maximum_compile_jobs': 2, 'whole_budget_seconds': 90, 'commands': commands,
              'fixture_cxx_standard': 20, 'synthetic_recipe_cxx_standard': 23,
              'child_environment': {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}}
    def record_json(name, value):
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    try:
        for relative in inputs():
            source = ROOT / relative
            info = source.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('project fixture input is not an independent regular file: ' + str(relative))
            raw = source.read_bytes()
            original[relative.as_posix()] = {'sha256': digest(raw), 'bytes': len(raw),
                                            'device': info.st_dev, 'inode': info.st_ino}
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        # These logical tools aliases come only from the pinned recipe copies.
        # Mutable ROOT/tools modules never enter this synthetic helper closure.
        helper_origins = []
        for logical, origin in FROZEN_HELPERS:
            destination = snapshot / logical
            raw = (snapshot / origin).read_bytes()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(raw)
            helper_origins.append({'snapshot_logical_path': logical.as_posix(),
                'origin': origin.as_posix(), 'sha256': digest(raw), 'bytes': len(raw)})
        result['frozen_helper_origins'] = helper_origins
        record_json('SNAPSHOT-HELPER-ORIGINS.json', helper_origins)
        result['canonical_source_joins_before'] = canonical_joins(ROOT)
        if canonical_joins(snapshot) != result['canonical_source_joins_before']:
            raise ValueError('canonical proof snapshot differs from actual source joins')
        record_json('CANONICAL-SOURCE-JOINS.json', result['canonical_source_joins_before'])
        compiler = Path('/usr/bin/g++-14')
        resolved = compiler.resolve(strict=True)
        info = resolved.stat()
        result['compiler'] = {'path': str(compiler), 'resolved': str(resolved),
                              'sha256': digest(resolved.read_bytes()), 'device': info.st_dev,
                              'inode': info.st_ino, 'bytes': info.st_size}
        if digest((snapshot / NATIVE / 'native/BibNativeProviderOnce.hpp').read_bytes()) != ONCE_SHA256:
            raise ValueError('reviewed NativeProviderOnce bytes changed')
        record_json('INPUT-FREEZE.json', original)
        spec = importlib.util.spec_from_file_location('native_probe_process_tree', snapshot / 'tools/process_tree.py')
        process_tree = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(process_tree)
        def command(name, argv, maximum=20):
            if cancelled.is_set() or deadline <= time.monotonic():
                raise TimeoutError('whole fixture launch deadline exhausted')
            item = {'name': name, 'argv': [str(x) for x in argv], 'launch_intent_monotonic': time.monotonic()}
            with records_lock:
                commands.append(item)
                record_json('COMMANDS.json', commands)
            with (output / (name + '.log')).open('wb') as stream:
                owner = process_tree.launch(item['argv'], snapshot, stream, env=result['child_environment'])
                try:
                    with records_lock:
                        item['supervisor_pid'] = owner.process.pid
                        item['launched_monotonic'] = time.monotonic()
                        record_json('COMMANDS.json', commands)
                    command_deadline = min(deadline, time.monotonic() + maximum)
                    while True:
                        remaining = command_deadline - time.monotonic()
                        if cancelled.is_set() or remaining <= 0:
                            raise TimeoutError('fixture command cancelled or deadline exhausted')
                        try:
                            code = owner.wait(timeout=min(0.25, remaining))
                            break
                        except subprocess.TimeoutExpired:
                            pass
                    owner.finish()
                except BaseException as error:
                    cancelled.set()
                    owner.terminate(timeout=max(0.01, min(5, started + 89 - time.monotonic())))
                    with records_lock:
                        item['failure'] = type(error).__name__ + ': ' + str(error)
                    raise
                finally:
                    owner.close()
                    with records_lock:
                        item.update(finished_monotonic=time.monotonic(), writers_closed=True)
                        record_json('COMMANDS.json', commands)
            with records_lock:
                item.update(returncode=code, finished_monotonic=time.monotonic(), writers_closed=True)
                record_json('COMMANDS.json', commands)
            return code
        variants = output / 'variants'
        variants.mkdir()
        for family, (path, expected, old_expected) in GUARDS.items():
            raw = (snapshot / path).read_bytes()
            if digest(raw) != expected or digest(raw.replace(RECHECK, b'')) != old_expected:
                raise ValueError('reviewed Guard postimage/counterfactual changed: ' + family)
            for old in (False, True):
                label = family + ('-old' if old else '-fixed')
                (variants / (label + '.cpp')).write_bytes(instrument(raw, old=old))
        common_includes = [snapshot / NATIVE / suffix for suffix in (
            'native', 'document-provider/runtime', 'document-provider/portable',
            'provider-binding/binding', 'wrapper/src/embedder')]
        def flags():
            base = snapshot / NATIVE / 'foundation'
            includes = common_includes + [base / 'include', base / 'third_party/appended-engine/include',
                                         base / 'abi/appended']
            return ['-std=c++20', '-O0', '-fexceptions', '-pthread', '-Wall', '-Wextra',
                    '-DBIB_ENGINE_PROVIDER_NEUTRAL=1', '-DBIB_ENGINE_PROVIDER_NATIVE=1',
                    '-DBIB_ENGINE_PROVIDER_DOCUMENT_V2=1', '-DBIB_ENGINE_PROVIDER_EDITOR_V1=1',
                    '-DBIB_ENGINE_PROVIDER_DOCUMENT_ACTIONS_V1=1',
                    '-DBIB_NATIVE_PROVIDER_BINDING_HEADER="BibNativeProviderBootstrap.hpp"'] + [
                        '-I' + str(path) for path in includes]
        jobs = []
        objects = {}
        for family in GUARDS:
            for old in (False, True):
                label = family + ('-old' if old else '-fixed')
                source = variants / (label + '.cpp')
                obj = output / (label + '.o')
                objects[label] = obj
                jobs.append((label, [compiler] + flags() + ['-include', snapshot / SCHEDULER,
                    '-MMD', '-MF', output / (label + '.d'), '-c', source, '-o', obj]))
            jobs.append((family + '-fixture', [compiler] + flags() + ['-MMD', '-MF',
                output / (family + '-fixture.d'), '-c', snapshot / FIXTURE, '-o', output / (family + '-fixture.o')]))
        for name, path in COMMON_SOURCES:
            jobs.append((name, [compiler] + flags() + ['-MMD', '-MF', output / (name + '.d'),
                        '-c', snapshot / path, '-o', output / (name + '.o')]))
        if len(jobs) != 10:
            raise ValueError('the reviewed ten-helper-TU closure changed')
        def compile_one(job):
            code = command(*job)
            if code:
                cancelled.set()
                raise RuntimeError('pure helper compilation failed: ' + job[0])
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(compile_one, job) for job in jobs]
            try:
                for future in futures:
                    future.result()
            except BaseException:
                cancelled.set()
                for future in futures:
                    future.cancel()
                # Each active worker owns and joins its own process tree. Never
                # concurrently invoke ProcessTree lifecycle methods from here.
                for future in futures:
                    try:
                        future.result()
                    except BaseException:
                        pass
                raise
        # -MMD enumerates project headers only. No unsnapshotted project read may
        # be silently added to the compiler closure.
        canonical_proofs = {canonical for canonical, _ in CANONICAL_JOINS}
        admitted = {str(snapshot / path) for path in inputs() if path not in canonical_proofs}
        admitted |= {str(path) for path in variants.iterdir()}
        for depfile in output.glob('*.d'):
            words = depfile.read_text().replace('\\\n', ' ').split()[1:]
            if any(word not in admitted for word in words):
                raise ValueError('compiler read a project input outside the frozen closure: ' + depfile.name)
        for label, obj in objects.items():
            family = label.split('-')[0]
            code = command(label + '-link', [compiler, '-pthread', obj, output / (family + '-fixture.o'),
                           *[output / (name + '.o') for name, _ in COMMON_SOURCES], '-o', output / label])
            if code:
                raise RuntimeError('pure helper fixture link failed: ' + label)
        # Synthetic sealed R/B fixtures exercise the exact generated header's
        # native64 layouts and constexpr joins without claiming native inputs.
        metadata_spec = importlib.util.spec_from_file_location('native_actions_probe_metadata_fixture',
            snapshot / 'tests/test_appended_engine_native_actions_metadata.py')
        metadata_fixture = importlib.util.module_from_spec(metadata_spec)
        metadata_spec.loader.exec_module(metadata_fixture)
        pure_targets = []
        header = None
        for label, system, processor in (('linux-x64', 'Linux', 'x86_64'),
                ('linux-arm64', 'Linux', 'aarch64'), ('windows-x64', 'Windows', 'x86_64')):
            if deadline <= time.monotonic():
                raise TimeoutError('whole fixture deadline exhausted before pure metadata generation')
            generated = metadata_fixture.Fixture(output / ('synthetic-metadata-' + label),
                processor=processor, system=system)
            metadata_result = generated.generate()
            if (metadata_result['production_eligible'] or metadata_result['engine_execution']
                    or len(metadata_result['engine_profile']) != 40):
                raise ValueError('synthetic rich metadata incorrectly claimed eligibility or lost its profile')
            pure_targets.append(metadata_result)
            if label == 'linux-x64':
                header = generated.output / generated.module.HEADER
        result['synthetic_metadata_pure_generations'] = pure_targets
        if header is None:
            raise ValueError('Linux x64 generated header was not selected explicitly')
        header_source = output / 'metadata-layout.cpp'
        header_source.write_text('#include "' + str(header) + '"\n')
        metadata_depfile = output / 'metadata-layout.d'
        if command('generated-header-layout', [compiler] + flags() + ['-MMD', '-MF', metadata_depfile,
                   '-MT', 'metadata-layout', '-fsyntax-only', header_source], 10):
            raise RuntimeError('generated native metadata header layout/constexpr checks failed')
        metadata_admitted = admitted | {str(header), str(header_source)}
        dependencies = metadata_depfile.read_text().replace('\\\n', ' ').split()[1:]
        if any(word not in metadata_admitted for word in dependencies):
            raise ValueError('generated header compiler read outside the frozen closure')
        result['synthetic_metadata_header_compile_passed'] = True
        for case in CASES:
            if command('rich-' + case, [output / 'rich-fixed', case], 5):
                raise RuntimeError('actual rich4083 Guard/Once case failed: ' + case)
        for family in GUARDS:
            name = family + '-old-counterfactual'
            code = command(name, [output / (family + '-old'), 'initial-phase-gate-race'], 5)
            log = (output / (name + '.log')).read_text()
            if code != 1 or 'foreign advance crossed START owner commitment' not in log:
                raise RuntimeError('old Gate counterfactual did not discriminate: ' + family)
        result.update(passed=True, main_cases_passed=len(CASES), rich_gate_confirmation_passed=True,
                      expected_counterfactual_failures=1)
    except BaseException as error:
        result.update(passed=False, failure=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        changed = []
        recheck_errors = {}
        for path, item in original.items():
            try:
                state = (ROOT / path).lstat()
                if (not stat.S_ISREG(state.st_mode) or state.st_nlink != 1
                        or (state.st_dev, state.st_ino, state.st_size) !=
                            (item['device'], item['inode'], item['bytes'])
                        or digest((ROOT / path).read_bytes()) != item['sha256']):
                    changed.append(path)
            except OSError as error:
                changed.append(path)
                recheck_errors[path] = type(error).__name__ + ': ' + str(error)
        result.update(source_bytes_changed=changed)
        if recheck_errors:
            result['source_recheck_errors'] = recheck_errors
        try:
            result['canonical_source_joins_after'] = canonical_joins(ROOT)
            if ('canonical_source_joins_before' in result
                    and result['canonical_source_joins_after'] != result['canonical_source_joins_before']):
                changed.append('canonical-to-rich source joins changed')
        except (OSError, ValueError) as error:
            changed.append('canonical-to-rich source joins failed')
            result['canonical_source_join_error'] = type(error).__name__ + ': ' + str(error)
        if 'compiler' in result:
            try:
                state = resolved.stat()
                result['compiler_bytes_unchanged'] = (
                    (state.st_dev, state.st_ino, state.st_size) ==
                        (result['compiler']['device'], result['compiler']['inode'], result['compiler']['bytes'])
                    and digest(resolved.read_bytes()) == result['compiler']['sha256'])
            except OSError as error:
                result['compiler_bytes_unchanged'] = False
                result['compiler_recheck_error'] = type(error).__name__ + ': ' + str(error)
            if not result['compiler_bytes_unchanged']:
                changed.append('/usr/bin/g++-14 resolved compiler')
        result['elapsed_seconds'] = time.monotonic() - started
        if result['elapsed_seconds'] > 90:
            result.update(passed=False, failure='whole 90-second fixture budget exhausted')
        if changed:
            result.update(passed=False, failure='fixture inputs changed during the bounded run')
        record_json('RESULT.json', result)
    if not result['passed']:
        raise RuntimeError(result['failure'])
    return result


class NativeActionsBootstrapSourceTests(unittest.TestCase):
    def test_guard_instrumentation_is_exact_and_reversible(self):
        for path, fixed, old in GUARDS.values():
            raw = (ROOT / path).read_bytes()
            self.assertEqual(digest(raw), fixed)
            self.assertEqual(digest(instrument(raw).replace(HOOK, b'')), fixed)
            self.assertEqual(digest(instrument(raw, old=True).replace(HOOK, b'')), old)

    def test_editor_guard_successor_keeps_native_predecessors_and_profile_joins(self):
        logical = 'source/foundation/third_party/appended-engine/src/ProviderGuard.cpp'
        tracked = 'recipes/webkitwasm-native-rich4083-v1/' + logical
        expected = '3aebfcc5b4e838846f23a5c9c61a62acc51fecc73541fd58deaa9c157308b0ff'
        previous = 'ae2a27c9f62ca92636ef7253501fdfcb0ebed788473af174c98c0c698b855651'
        provenance_raw = (ROOT / RECIPE / 'provenance.json').read_bytes()
        imports_raw = (ROOT / RECIPE / 'source-imports.json').read_bytes()
        provenance = json.loads(provenance_raw)
        imports = json.loads(imports_raw)
        record = provenance['runtime_files'][logical]
        self.assertEqual(record['after_sha256'], expected)
        self.assertEqual(record['after_bytes'], 74981)
        self.assertEqual(record['bytes'], 73277)
        original = '909ceac8b7bf311993f680cdf104d2ae6111bede8b0507fcc0e094bcc573d5ae'
        self.assertEqual(record['sha256'], original)
        self.assertEqual(record['preimage_sha256'], original)
        successor = record['successor']
        self.assertEqual({key: successor[key] for key in ('kind', 'correction', 'sha256', 'source_path', 'source_only')}, {
            'kind': 'reviewed-editor-C8-preflight-repair',
            'correction': 'inert-C8-before-Host-TURN-with-in-turn-revalidation',
            'sha256': expected, 'source_path': tracked, 'source_only': True})
        prior = successor['supersedes']
        self.assertEqual((prior['sha256'], prior['tracked_path']), (previous, tracked))
        self.assertEqual(prior['origin'], {
            'action': 'native-getter-hook-only-gate-fix-already-present',
            'after_sha256': previous, 'bytes': 73277, 'mode': 420,
            'origin': 'frozen-native-actions-capsule',
            'origin_path': '.agent-work/appended-implementation-20261016/tui-native-actions/versions/0001-document-actions-v1/source/foundation/third_party/appended-engine/src/ProviderGuard.cpp',
            'preimage_sha256': original, 'selection': 'native-adaptation',
            'sha256': original, 'source': logical})
        item = imports['inputs'][logical]
        self.assertEqual((item['tracked_path'], item['sha256'], item['bytes']), (tracked, expected, 74981))
        self.assertEqual(item['origin']['record'], record)
        self.assertEqual(digest((ROOT / tracked).read_bytes()), expected)
        self.assertEqual(imports['provenance']['sha256'], digest(provenance_raw))
        self.assertEqual(imports['inputs']['provenance.json']['sha256'], digest(provenance_raw))
        self.assertEqual(imports['inputs']['provenance.json']['bytes'], len(provenance_raw))
        for name in ('native-prototype-profile.json', 'windows-producer-profile.json'):
            profile = json.loads((ROOT / RECIPE / name).read_bytes())
            self.assertEqual(profile['source_map']['sha256'], digest(imports_raw))
            self.assertEqual(profile['provenance']['sha256'], digest(provenance_raw))
            self.assertEqual((profile['source_files'], profile['engine_files'], profile['direct_translation_units']), (158 if profile['kind'] in ('foundation-native-engine-prototype-composition-undo-profile-v1', 'foundation-native-engine-windows-producer-composition-undo-profile-v1', 'foundation-native-engine-prototype-native-popup-capability-profile-v1', 'foundation-native-engine-windows-producer-native-popup-capability-profile-v1') else 157, 48, 32))

    def test_closure_is_only_rich_and_expected_once(self):
        self.assertEqual(set(GUARDS), {'rich'})
        self.assertEqual(len(COMMON_SOURCES), 7)
        self.assertEqual(digest((ROOT / NATIVE / 'native/BibNativeProviderOnce.hpp').read_bytes()), ONCE_SHA256)
        self.assertEqual(len(canonical_joins(ROOT)), 18)
        canonical_proofs = {canonical for canonical, _ in CANONICAL_JOINS}
        self.assertIn(Path('third_party/appended-engine/src/ProviderGuard.cpp'), canonical_proofs)
        self.assertIn(Path('third_party/appended-engine/include/EnginePrivate.hpp'), canonical_proofs)
        self.assertTrue(canonical_proofs <= set(inputs()))
        self.assertFalse(canonical_proofs & {path for _, path in COMMON_SOURCES})
        self.assertEqual(len(FROZEN_HELPERS), 6)
        for logical, origin in FROZEN_HELPERS:
            self.assertNotIn(logical, inputs())
            self.assertIn(origin, inputs())
        for path in inputs():
            self.assertTrue((ROOT / path).is_file(), str(path))
        source = (ROOT / FIXTURE).read_text()
        self.assertIn('bind_engine_document_actions_private(engine,document,editor,actions)', source)
        self.assertIn('P::document_physical_profile,0,worker', source)
        self.assertIn('sizeof(BibEngineLimitsV1),1048576,236,1048576', source)

    def test_named_cases_are_finite_and_implemented(self):
        source = (ROOT / FIXTURE).read_text()
        self.assertEqual(len(CASES), 21)
        self.assertEqual(len(set(CASES)), len(CASES))
        for case in CASES:
            self.assertIn('"' + case + '"', source)


if __name__ == '__main__':
    if '--bounded-output' in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--bounded-output', type=Path, required=True)
        args = parser.parse_args()
        print(json.dumps(run_probe(args.bounded_output), sort_keys=True))
    else:
        unittest.main()
