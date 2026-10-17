"""Execute composed native images through the built kernel prerequisite."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from test_appended_kernel import container, kernel, module_fixture

NATIVE_KERNEL = None


class NativeKernelTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'source.cpp').write_text('// producer fixture input\n')
        self.raw = self.root / ('raw.exe' if os.name == 'nt' else 'raw')
        shutil.copyfile(NATIVE_KERNEL, self.raw)
        self.raw.chmod(0o755)
        self.kernel = self.root / ('sealed.exe' if os.name == 'nt' else 'sealed')
        self.descriptor = kernel.seal(self.raw, self.kernel, self.root / 'kernel.json', self.source,
                                      {'qualification': 'unqualified-test-fixture'})

    def launch(self, executable, *arguments):
        return subprocess.run([str(executable), *arguments], capture_output=True, text=True, timeout=20)

    def compose(self, module=None, *, requires=None, descriptor=None, name='application'):
        module = module_fixture() if module is None else module
        package = container.build_package({'binary/application.wasm': module},
            {'id': 'org.foundation.fixture', 'name': 'Fixture application', 'version': '1.0.0'},
            binary_entry='binary/application.wasm', binary_profile='foundation-guest-v1', requires=requires)
        data = container.compose_bytes(self.kernel.read_bytes(), descriptor or self.descriptor, package)
        composed = self.root / (name + ('.exe' if os.name == 'nt' else ''))
        composed.write_bytes(data)
        composed.chmod(0o755)
        return composed, package

    def test_pristine_absence_and_external_expectation(self):
        ordinary = self.launch(self.kernel)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertIn('no appended application', ordinary.stdout)
        inspection = self.launch(self.kernel, '--inspect')
        self.assertEqual(inspection.returncode, 0, inspection.stderr)
        self.assertEqual(json.loads(inspection.stdout)['mode'], 'neither')
        expected = self.launch(self.kernel, '--expect-mode', 'binary')
        self.assertNotEqual(expected.returncode, 0)
        self.assertIn('expected appended mode binary, found neither', expected.stderr)

    def test_actual_module_initialization_dispatch_and_exact_prefix(self):
        composed, package = self.compose()
        prefix = self.kernel.read_bytes()
        self.assertEqual(composed.read_bytes()[:len(prefix)], prefix)
        executed = self.launch(composed, '--expect-mode', 'binary', '--dispatch-hex', '01020304')
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertIn('Fixture application', executed.stdout)
        self.assertIn('binary\tinitialized', executed.stdout)
        self.assertIn('service_calls\t0', executed.stdout)
        inspected = self.launch(composed, '--inspect')
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout), package.index)

    def test_failed_guest_initialization_is_not_reported_as_success(self):
        composed, _ = self.compose(module_fixture(initialization_status=2))
        failed = self.launch(composed)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('initialization failed', failed.stderr)
        self.assertNotIn('binary\tinitialized', failed.stdout)

    def test_corruption_trailer_loss_and_extra_bytes_do_not_fall_back(self):
        composed, _ = self.compose()
        data = composed.read_bytes()
        cases = [data[:-192], data[:-1], data + b'junk', data[:-193] + bytes([data[-193] ^ 1]) + data[-192:]]
        for number, changed in enumerate(cases):
            with self.subTest(case=number):
                destination = self.root / ('broken-' + str(number) + ('.exe' if os.name == 'nt' else ''))
                destination.write_bytes(changed)
                destination.chmod(0o755)
                result = self.launch(destination, '--inspect')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('no appended application', result.stdout)

    def test_invalid_dispatch_and_unsealed_producer_are_explicit_errors(self):
        self.assertIn('unsealed', self.launch(self.raw).stderr)
        for arguments in (('--dispatch-hex', '0'), ('--dispatch-hex', 'gg'), ('--expect-mode', 'bogus')):
            with self.subTest(arguments=arguments):
                self.assertNotEqual(self.launch(self.kernel, *arguments).returncode, 0)

    def test_provider_options_reject_invalid_or_conflicting_arguments_before_load(self):
        # The unsealed input proves argument errors precede self loading and any
        # guest invocation, rather than accidentally passing on missing payloads.
        cases = (
            (('--provider',), 'invalid arguments'),
            (('--provider', ''), 'needs a contract name'),
            (('--provider', '--inspect'), 'contract name'),
            (('--provider', '--help'), 'contract name'),
            (('--provider', '--provider'), 'contract name'),
            (('--provider-operation', '1'), 'require --provider'),
            (('--provider-payload-hex', ''), 'require --provider'),
            (('--provider', 'org.example.increment', '--provider-operation'), 'invalid arguments'),
            (('--provider', 'org.example.increment', '--provider-payload-hex'), 'invalid arguments'),
            (('--provider', 'org.example.increment', '--provider-operation', '0'), 'positive uint32'),
            (('--provider', 'org.example.increment', '--provider-operation', '-1'), 'positive uint32'),
            (('--provider', 'org.example.increment', '--provider-operation', '1.5'), 'positive uint32'),
            (('--provider', 'org.example.increment', '--provider-operation', '4294967296'), 'positive uint32'),
            (('--provider', 'org.example.increment', '--provider-payload-hex', '0'), 'hexadecimal'),
            (('--provider', 'org.example.increment', '--provider-payload-hex', 'gg'), 'hexadecimal'),
            (('--provider', 'org.example.increment', '--inspect'), 'cannot be combined'),
            (('--provider', 'org.example.increment', '--help'), 'cannot be combined'),
            (('--provider', 'org.example.increment', '--dispatch', ''), 'separate invocations'),
            (('--dispatch-hex', '', '--provider', 'org.example.increment'), 'separate invocations'),
            (('--provider', 'org.example.increment', '--provider', 'org.example.increment'), 'invalid arguments'),
            (('--provider', 'org.example.increment', '--provider-operation', '1', '--provider-operation', '2'), 'invalid arguments'),
            (('--provider', 'org.example.increment', '--provider-payload-hex', '', '--provider-payload-hex', ''), 'invalid arguments'),
        )
        for arguments, message in cases:
            with self.subTest(arguments=arguments):
                result = self.launch(self.raw, *arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn('unsealed', result.stderr)
                self.assertNotIn('binary\tinitialized', result.stdout)

    def test_provider_calls_require_payload_and_actual_registered_contract(self):
        absent = self.launch(self.kernel, '--provider', 'org.example.increment',
                             '--provider-operation', '4294967295', '--provider-payload-hex', '')
        self.assertNotEqual(absent.returncode, 0)
        self.assertIn('there is no appended binary application to call', absent.stderr)
        composed, _ = self.compose()
        unavailable = self.launch(composed, '--provider', 'org.example.absent')
        self.assertNotEqual(unavailable.returncode, 0)
        self.assertIn('application provider is unavailable: org.example.absent', unavailable.stderr)
        self.assertIn('binary\tinitialized', unavailable.stdout)
        self.assertNotIn('provider\torg.example.absent\t', unavailable.stdout)

    def test_provider_service_and_capability_precede_guest_initialization(self):
        requirements = {'abi': {'major': 1, 'minor': 0},
                        'services': ['foundation.providers'], 'capabilities': ['foundation.providers.v1']}
        descriptor = dict(self.descriptor,
                          services=sorted(set(self.descriptor['services']) | {'foundation.providers'}),
                          capabilities=sorted(set(self.descriptor['capabilities']) | {'foundation.providers.v1'}))
        composed, package = self.compose(requires=requirements, descriptor=descriptor)
        result = self.launch(composed, '--expect-mode', 'binary')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('binary\tinitialized', result.stdout)
        self.assertIn('service_calls\t0', result.stdout)
        inspected = self.launch(composed, '--inspect')
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout), package.index)
        self.assertNotIn('binary\tinitialized', inspected.stdout)

    def test_unavailable_requirements_fail_before_guest_initialization_but_inspect_remains_read_only(self):
        for label, requirement, declaration, message in (
                ('service', {'services': ['org.example.absent']},
                 {'services': ['foundation.kernel', 'org.example.absent']},
                 'required application service is unavailable: org.example.absent'),
                ('capability', {'capabilities': ['org.example.absent.v1']},
                 {'capabilities': ['org.example.absent.v1']},
                 'required kernel capability is unavailable: org.example.absent.v1'),
                ('abi', {'abi': {'major': 1, 'minor': 1}}, {'abi': {'major': 1, 'minor': 1}},
                 'unsupported application ABI version')):
            with self.subTest(requirement=label):
                requires = {'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []}
                requires.update(requirement)
                # Assert actual runtime checks independently of the external
                # composer's normal compatibility gate, as for unsupported web.
                descriptor = dict(self.descriptor, **declaration)
                composed, package = self.compose(module_fixture(initialization_status=2), requires=requires,
                                                 descriptor=descriptor, name='requires-' + label)
                rejected = self.launch(composed)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn(message, rejected.stderr)
                self.assertNotIn('initialization failed', rejected.stderr)
                self.assertNotIn('binary\tinitialized', rejected.stdout)
                inspected = self.launch(composed, '--inspect')
                self.assertEqual(inspected.returncode, 0, inspected.stderr)
                self.assertEqual(json.loads(inspected.stdout), package.index)
                self.assertNotIn('binary\tinitialized', inspected.stdout)

    def check_explicit_provider_module(self, module_path):
        saved = container._snapshot(module_path, container.MAX_FILE)
        requirements = {'abi': {'major': 1, 'minor': 0}, 'services': ['foundation.providers'],
                        'capabilities': ['foundation.providers.v1']}
        descriptor = dict(self.descriptor,
                          services=sorted(set(self.descriptor['services']) | {'foundation.providers'}),
                          capabilities=sorted(set(self.descriptor['capabilities']) | {'foundation.providers.v1'}))
        composed, package = self.compose(saved.content, requires=requirements, descriptor=descriptor)
        original = composed.read_bytes()
        self.assertEqual(original[:len(self.kernel.read_bytes())], self.kernel.read_bytes())
        inspected = self.launch(composed, '--inspect')
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout), package.index)
        self.assertNotIn('binary\tinitialized', inspected.stdout)
        # Each process owns a fresh initialized instance, so count is one in
        # either successful invocation. The first call checks operation default1.
        for arguments, expected in (
                (('--provider-payload-hex', '29000000'), '2a00000001000000'),
                (('--provider-operation', '1', '--provider-payload-hex', 'FF000000'), '0001000001000000')):
            with self.subTest(module=str(module_path), arguments=arguments):
                result = self.launch(composed, '--provider', 'org.example.increment', *arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('provider\torg.example.increment\t0\t' + expected + '\n', result.stdout)
                self.assertIn('binary\tinitialized', result.stdout)
                self.assertIn('service_calls\t0', result.stdout)
        # Explicit guest errors must remain errors, including the uint32 upper
        # operation boundary and omitted payload's deliberately empty bytes.
        for arguments, status in ((('--provider-operation', '4294967295', '--provider-payload-hex', '29000000'), 9),
                                  ((), 1)):
            with self.subTest(module=str(module_path), arguments=arguments):
                result = self.launch(composed, '--provider', 'org.example.increment', *arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('provider\torg.example.increment\t' + str(status) + '\t\n', result.stdout)
                self.assertIn('application provider call failed', result.stderr)
        self.assertEqual(composed.read_bytes(), original)
        container._recheck(saved)

    def test_unsupported_web_payload_is_not_executed_as_outer_document(self):
        for both in (False, True):
            with self.subTest(both=both):
                files = {'web/index.html': b'<!doctype html><html><body>engine required</body></html>'}
                if both:
                    files['binary/application.wasm'] = module_fixture()
                package = container.build_package(files,
                    {'id': 'org.foundation.webfixture', 'name': 'Web fixture', 'version': '1.0.0'},
                    web_entry='web/index.html',
                    binary_entry='binary/application.wasm' if both else None,
                    binary_profile='foundation-guest-v1' if both else None)
                # Deliberately construct a syntactically valid unsupported
                # suffix: normal composition rejects this binary-only profile.
                descriptor = dict(self.descriptor, profile='both')
                artifact = container.compose_bytes(self.kernel.read_bytes(), descriptor, package)
                destination = self.root / ('unsupported-' + str(both) + ('.exe' if os.name == 'nt' else ''))
                destination.write_bytes(artifact)
                destination.chmod(0o755)
                result = self.launch(destination)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('rich web engine capability is unavailable', result.stderr)
                self.assertNotIn('binary\tinitialized', result.stdout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--provider-module', type=Path, action='append', default=[],
                        help='explicit real SDK increment fixture; repeat for separately counted native executions')
    args, remaining = parser.parse_known_args()
    NATIVE_KERNEL = args.kernel.resolve(strict=True)
    for number, path in enumerate(args.provider_module):
        module_path = path.resolve(strict=True)
        def explicit_provider_test(self, module_path=module_path):
            self.check_explicit_provider_module(module_path)
        setattr(NativeKernelTests, 'test_explicit_provider_module_' + str(number), explicit_provider_test)
    if args.provider_module:
        print('Explicit real-provider CLI fixture scope: ' + str(len(args.provider_module)) + ' module(s)', file=sys.stderr)
    unittest.main(argv=[sys.argv[0], *remaining])
