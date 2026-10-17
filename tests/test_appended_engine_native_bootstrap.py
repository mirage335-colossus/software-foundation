"""Pixel Source3 checks and an explicitly selected bounded Guard/Once probe.

The opt-in CLI compiles only pure helpers and fake callbacks, never WebCore or a
provider DSO. Every compiler and runtime process is supervised, and evidence is
retained at the caller's fresh private output directory on success or failure.
The canonical/editor family is the frozen historical740 test version. The new
rich actions probe checks the current canonical Guard independently.
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
NATIVE = Path('recipes/webkitwasm-native-v1/source')
FIXTURE = Path('tests/appended_engine_native_bootstrap_test.cpp')
SCHEDULER = Path('tests/fixtures/appended_native_bootstrap/FixtureScheduler.hpp')
HISTORICAL = Path('tests/fixtures/appended_engine_native_bootstrap_legacy740')
HISTORICAL_PROOF = '4a4fc8e631b0e3a92387f4b52ae944037d952cf7c5f359237f6f0f9ad34fa3bf'
GUARDS = {
    'pixel': (NATIVE / 'foundation/third_party/appended-engine/src/ProviderGuard.cpp',
              '61b516cc59eab6b80ec329191a1de5d34b24fbf23c7152ea4a228dc2d23faa11',
              '3b4ed6b5c56696a80a61d4da6bfb5304a85e2ce6cea3f47feff845ebe394136c'),
    'canonical': (HISTORICAL / 'third_party/appended-engine/src/ProviderGuard.cpp',
                  '74084a0d77e7c32a493f42be2e6538a0151039ba92cba8bb5cdfc37a48831b90',
                  '87b510433d4db2286b3fb7585e9394230392f7b67183c340430cd6d68fb19a19'),
}
RECHECK = b'''            // START may have committed after the fast owner check and before
            // this acquisition. Read owner only after published commitment,
            // and recheck under the gate before any retained-state operation.
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


def instrument(raw, *, old=False):
    if raw.count(POINT) != 1 or raw.count(RECHECK) != 1 or HOOK in raw:
        raise ValueError('Guard scheduling/recheck preimage changed')
    selected = raw.replace(RECHECK, b'') if old else raw
    result = selected.replace(POINT, HOOK + POINT)
    if result.replace(HOOK, b'') != selected:
        raise ValueError('fixture instrumentation changed production bytes')
    return result


def inputs():
    common = [FIXTURE, SCHEDULER, Path(__file__).relative_to(ROOT), Path('tools/process_tree.py'),
              NATIVE / 'native/BibNativeProviderOnce.hpp',
              NATIVE / 'native/BibNativeProviderBootstrap.hpp',
              NATIVE / 'document-provider/runtime/BibCopiedDocumentCatalog.hpp',
              NATIVE / 'provider-binding/binding/BibEngineProviderPreflight.h',
              NATIVE / 'provider-binding/binding/BibEngineProviderPreflight.cpp',
              NATIVE / 'wrapper/src/embedder/resource_url.hpp',
              NATIVE / 'wrapper/src/embedder/resource_url.cpp',
              HISTORICAL / 'abi/appended/engine_editor_protocol.h',
              HISTORICAL / 'gui/shared/engine_editor_pins.hpp', HISTORICAL / 'SOURCE-PROOF.json']
    common += [Path('tests/test_appended_engine_native_metadata.py'),
               Path('recipes/webkitwasm-native-v1/runtime/generate_native_metadata.py'),
               Path('recipes/webkitwasm-native-v1/runtime/native-provider-metadata.h.in'),
               Path('recipes/webkitwasm-native-v1/prelink-config.json')]
    common += [Path('tools') / name for name in ('dependency_archive.py', 'appended_engine_manifest.py',
               'appended_engine_sdk.py', 'appended_engine_document_contract.py')]
    common += [NATIVE / 'foundation/abi/engine/document-v2' / name for name in (
        'contract.json', 'catalog.json', 'schema-definition.json', 'action-ack.json')]
    common += [NATIVE / 'foundation/third_party/appended-engine/include/LegacyHostAdapters.hpp']
    common += [NATIVE / 'foundation/third_party/appended-engine/include/legacy' / name for name in (
        'BibAppResourceHost.h', 'BibFoundationServiceHost.h')]
    for base in (HISTORICAL, NATIVE / 'foundation'):
        common += [base / 'third_party/appended-engine/include/EnginePrivate.hpp',
                   base / 'include/foundation/appended/engine_provider.h',
                   base / 'include/foundation/appended/engine_provider_document_v2.h']
    return sorted(set(common + [record[0] for record in GUARDS.values()]))


def run_probe(output):
    sys.dont_write_bytecode = True
    started = time.monotonic()
    deadline = started + 84  # Six seconds reserved for cleanup within the 90s grant.
    if sys.platform != 'linux' or os.name != 'posix':
        raise ValueError('this focused compiler probe is admitted only on Linux')
    output = output.absolute()
    output.mkdir(mode=0o700)  # Refuse preexisting evidence/output directories.
    original = {}
    commands = []
    records_lock = threading.Lock()
    cancelled = threading.Event()
    snapshot = output / 'source'
    snapshot.mkdir()
    result = {'scope': 'fake-native-actual-guard-once-only', 'production_eligible': False,
              'engine_compiled': False, 'provider_dso_built': False,
              'maximum_compile_jobs': 2, 'whole_budget_seconds': 90, 'commands': commands,
              'child_environment': {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
              'canonical_family_scope': 'frozen-historical-editor740-test-only'}
    def record_json(name, value):
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    try:
        historical_raw = (ROOT / HISTORICAL / 'SOURCE-PROOF.json').read_bytes()
        if digest(historical_raw) != HISTORICAL_PROOF:
            raise ValueError('historical source proof differs from its independent pin')
        for name, item in json.loads(historical_raw)['files'].items():
            if digest((ROOT / HISTORICAL / name).read_bytes()) != item['sha256']:
                raise ValueError('historical Guard/header source changed: ' + name)
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
        compiler = Path('/usr/bin/g++-14')
        resolved = compiler.resolve(strict=True)
        info = resolved.stat()
        result['compiler'] = {'path': str(compiler), 'resolved': str(resolved),
                              'sha256': digest(resolved.read_bytes()), 'device': info.st_dev,
                              'inode': info.st_ino, 'bytes': info.st_size}
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
            'native', 'document-provider/runtime', 'provider-binding/binding', 'wrapper/src/embedder')]
        def flags(family):
            base = snapshot / (NATIVE / 'foundation' if family == 'pixel' else HISTORICAL)
            includes = common_includes + [base / 'include', base / 'third_party/appended-engine/include',
                                         base / 'abi/appended', base / 'gui/shared']
            return ['-std=c++20', '-O0', '-fexceptions', '-pthread', '-Wall', '-Wextra',
                    '-DBIB_ENGINE_PROVIDER_NATIVE=1',
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
                jobs.append((label, [compiler] + flags(family) + ['-include', snapshot / SCHEDULER,
                    '-MMD', '-MF', output / (label + '.d'), '-c', source, '-o', obj]))
            jobs.append((family + '-fixture', [compiler] + flags(family) + ['-MMD', '-MF',
                output / (family + '-fixture.d'), '-c', snapshot / FIXTURE, '-o', output / (family + '-fixture.o')]))
        for name, path in [('preflight', NATIVE / 'provider-binding/binding/BibEngineProviderPreflight.cpp'),
                           ('resource-url', NATIVE / 'wrapper/src/embedder/resource_url.cpp')]:
            jobs.append((name, [compiler] + flags('pixel') + ['-MMD', '-MF', output / (name + '.d'),
                        '-c', snapshot / path, '-o', output / (name + '.o')]))
        def compile_one(job):
            code = command(*job)
            if code:
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
        admitted = {str(snapshot / path) for path in inputs()} | {str(path) for path in variants.iterdir()}
        for depfile in output.glob('*.d'):
            words = depfile.read_text().replace('\\\n', ' ').split()[1:]
            if any(word not in admitted for word in words):
                raise ValueError('compiler read a project input outside the frozen closure: ' + depfile.name)
        for label, obj in objects.items():
            family = label.split('-')[0]
            code = command(label + '-link', [compiler, '-pthread', obj, output / (family + '-fixture.o'),
                           output / 'preflight.o', output / 'resource-url.o', '-o', output / label])
            if code:
                raise RuntimeError('pure helper fixture link failed: ' + label)
        # Synthetic sealed R/B fixtures exercise the exact generated header's
        # native64 layouts and constexpr joins without claiming native inputs.
        metadata_spec = importlib.util.spec_from_file_location('native_probe_metadata_fixture',
            snapshot / 'tests/test_appended_engine_native_metadata.py')
        metadata_fixture = importlib.util.module_from_spec(metadata_spec)
        metadata_spec.loader.exec_module(metadata_fixture)
        generated = metadata_fixture.Fixture(output / 'synthetic-metadata')
        metadata_result = generated.generate()
        if metadata_result['production_eligible']:
            raise ValueError('synthetic metadata incorrectly claimed runtime eligibility')
        header = generated.output / generated.module.HEADER
        header_source = output / 'metadata-layout.cpp'
        header_source.write_text('#include "' + str(header) + '"\n')
        metadata_depfile = output / 'metadata-layout.d'
        if command('generated-header-layout', [compiler] + flags('pixel') + ['-MMD', '-MF', metadata_depfile,
                   '-MT', 'metadata-layout', '-fsyntax-only', header_source], 10):
            raise RuntimeError('generated native metadata header layout/constexpr checks failed')
        metadata_admitted = admitted | {str(header), str(header_source)}
        dependencies = metadata_depfile.read_text().replace('\\\n', ' ').split()[1:]
        if any(word not in metadata_admitted for word in dependencies):
            raise ValueError('generated header compiler read outside the frozen closure')
        result['synthetic_metadata_header_compile_passed'] = True
        for case in CASES:
            if command('pixel-' + case, [output / 'pixel-fixed', case], 5):
                raise RuntimeError('actual pixel Guard/Once case failed: ' + case)
        if command('canonical-gate-race', [output / 'canonical-fixed', 'initial-phase-gate-race'], 5):
            raise RuntimeError('canonical fixed Gate race failed')
        for family in GUARDS:
            name = family + '-old-counterfactual'
            code = command(name, [output / (family + '-old'), 'initial-phase-gate-race'], 5)
            log = (output / (name + '.log')).read_text()
            if code != 1 or 'foreign advance crossed START owner commitment' not in log:
                raise RuntimeError('old Gate counterfactual did not discriminate: ' + family)
        result.update(passed=True, main_cases_passed=len(CASES), canonical_gate_confirmation_passed=True,
                      expected_counterfactual_failures=2)
    except BaseException as error:
        result.update(passed=False, failure=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        changed = [path for path, item in original.items()
                   if digest((ROOT / path).read_bytes()) != item['sha256']]
        result.update(source_bytes_changed=changed)
        if 'compiler' in result:
            result['compiler_bytes_unchanged'] = digest(resolved.read_bytes()) == result['compiler']['sha256']
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


class NativeBootstrapSourceTests(unittest.TestCase):
    def test_historical_source_proof_is_exact(self):
        raw = (ROOT / HISTORICAL / 'SOURCE-PROOF.json').read_bytes()
        self.assertEqual(digest(raw), HISTORICAL_PROOF)
        records = json.loads(raw)['files']
        self.assertEqual(len(records), 6)
        for name, item in records.items():
            self.assertEqual(digest((ROOT / HISTORICAL / name).read_bytes()), item['sha256'])

    def test_guard_instrumentation_is_exact_and_reversible(self):
        for path, fixed, old in GUARDS.values():
            raw = (ROOT / path).read_bytes()
            self.assertEqual(digest(raw), fixed)
            self.assertEqual(digest(instrument(raw).replace(HOOK, b'')), fixed)
            self.assertEqual(digest(instrument(raw, old=True).replace(HOOK, b'')), old)

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
