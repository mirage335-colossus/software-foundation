"""Provider wire identities and real compiler/interpreter cross-language checks.

The execution cases require explicit retained compiler descriptors and a runner
built by the authorized kernel-maintenance check. No compiler is mocked or found
on PATH; absent prerequisites are reported as skipped, never as execution passes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/appended/provider_fixtures'


def hex_array(text, marker):
    body = text.split(marker, 1)[1]
    body = body[body.index('{') + 1:body.index('}')]
    return bytes(int(value, 16) for value in re.findall(r'0x([0-9a-fA-F]{2})', body))


class ProviderBindingTests(unittest.TestCase):
    def test_service_schema_pins_exact_authoritative_bytes(self):
        expected = hashlib.sha256((ROOT / 'abi/appended/providers/v1.json').read_bytes()).hexdigest()
        header = (ROOT / 'include/foundation/appended/provider_abi.h').read_text()
        self.assertEqual(re.search(r'SCHEMA_SHA256_HEX "([0-9a-f]+)"', header).group(1), expected)
        raw = header.replace('\\\n', '')
        body = re.search(r'#define FOUNDATION_PROVIDER_SCHEMA_BYTES ([^\n]+)', raw).group(1)
        self.assertEqual(bytes(int(value.strip(), 0) for value in body.split(',')), bytes.fromhex(expected))
        rust = (ROOT / 'sdk/appended/rust/src/providers.rs').read_text()
        # The Rust binding publishes the same exact schema digest, not a second
        # independent protocol version or a hash of reformatted JSON.
        self.assertIn(expected, rust)
        rust_schema = re.search(r'pub const SCHEMA: \[u8; 32\] = \[([^]]+)\]', rust, re.S).group(1)
        self.assertEqual(bytes(int(value, 16) for value in re.findall(r'0x([0-9a-fA-F]{2})', rust_schema)), bytes.fromhex(expected))
        for name in ('MAJOR', 'MINOR', 'REGISTER', 'RESPOND', 'DISCOVER', 'EVENT_CALL',
                     'MAX_PROVIDERS', 'MAX_PAYLOAD_BYTES', 'MAX_RETAINED_CALLS', 'MAX_RETAINED_BYTES', 'MAX_NAME_BYTES'):
            native_value = re.search(r'^#define FOUNDATION_PROVIDER_' + name + r' ([0-9]+)u$', header, re.M).group(1)
            rust_value = re.search(r'^pub const ' + name + r': u32 = ([0-9]+);$', rust, re.M).group(1)
            self.assertEqual(native_value, rust_value, name)
        schema = json.loads((ROOT / 'abi/appended/providers/v1.json').read_bytes())
        self.assertEqual(schema['operations']['2']['request'][-1], [4, 'payload', 'bytes', True])

    def test_real_fixtures_pin_one_exact_application_contract(self):
        contract = (FIXTURES / 'contract.txt').read_bytes()
        self.assertTrue(contract.endswith(b'\n'))
        expected = hashlib.sha256(contract).digest()
        for language, entry in [('c', 'provider.c'), ('cpp', 'provider.cpp')]:
            source = (FIXTURES / language / entry).read_text()
            with self.subTest(language=language):
                self.assertEqual(hex_array(source, 'schema[32] ='), expected)
                self.assertIn('org.example.increment', source)
        source = (FIXTURES / 'rust/src/lib.rs').read_text()
        body = re.search(r'(?:SCHEMA|schema): \[u8; 32\] = \[([^]]+)\]', source, re.S)
        self.assertIsNotNone(body)
        self.assertEqual(bytes(int(value, 16) for value in re.findall(r'0x([0-9a-fA-F]{2})', body.group(1))), expected)
        self.assertIn('org.example.increment', source)


class RealProviderExecutionTests(unittest.TestCase):
    def execute_fixture(self, language, directory, entry, sdk_variable):
        sdk = os.environ.get(sdk_variable)
        runner = os.environ.get('FOUNDATION_APPENDED_PROVIDER_TEST_RUNNER')
        if not sdk or not runner:
            self.skipTest(sdk_variable + ' and FOUNDATION_APPENDED_PROVIDER_TEST_RUNNER are required for real execution')
        sdk, runner = Path(sdk).resolve(strict=True), Path(runner).resolve(strict=True)
        with tempfile.TemporaryDirectory(prefix='foundation-provider-') as temporary:
            retained = os.environ.get('FOUNDATION_APPENDED_PROVIDER_TEST_OUTPUT')
            destination = Path(retained).resolve(strict=True) if retained else Path(temporary)
            stem = {'c': 'provider-c', 'c++': 'provider-cpp', 'rust': 'provider-rust'}[language]
            output = destination / (stem + '.wasm')
            receipt = destination / (stem + '.compile.json')
            entry_point = [sys.executable, str(ROOT / 'tools/build.py')] if os.name == 'nt' else [str(ROOT / 'build.sh')]
            command = [*entry_point, 'appended', 'compile',
                       '--source', str(FIXTURES / directory), '--language', language,
                       '--entry', entry, '--sdk', str(sdk), '--output', str(output),
                       '--receipt', str(receipt)]
            compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            data = json.loads(receipt.read_text())
            self.assertEqual(data['module']['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(data['language'], language)
            self.assertIn('include/foundation/appended/providers.h', data['bindings'])
            self.assertIn('include/foundation/appended/provider_abi.h', data['bindings'])
            self.assertFalse(any('cmake' in part.lower() for command in data['commands'] for part in command))
            execution = subprocess.run([str(runner), '--external', str(output)], cwd=ROOT,
                                       capture_output=True, text=True, timeout=30)
            if retained:
                (destination / (stem + '.execution.json')).write_text(json.dumps({
                    'module_sha256': data['module']['sha256'],
                    'runner': str(runner), 'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
                    'returncode': execution.returncode, 'stdout': execution.stdout, 'stderr': execution.stderr,
                }, indent=2) + '\n')
            self.assertEqual(execution.returncode, 0, execution.stdout + execution.stderr)

    def test_c_provider_executes_and_replays_without_repeating_work(self):
        self.execute_fixture('c', 'c', 'provider.c', 'FOUNDATION_APPENDED_C_GUEST_SDK')

    def test_cpp_provider_executes_and_replays_without_repeating_work(self):
        self.execute_fixture('c++', 'cpp', 'provider.cpp', 'FOUNDATION_APPENDED_C_GUEST_SDK')

    def test_rust_provider_executes_and_replays_without_repeating_work(self):
        self.execute_fixture('rust', 'rust', 'src/lib.rs', 'FOUNDATION_APPENDED_RUST_GUEST_SDK')


if __name__ == '__main__':
    unittest.main()
