"""Pinned guest recovery wiring with only physical compiler/runtime calls faked.

All source, archive, SDK, receipt, native-container and Wasm profile checks run.
No compiler, native structural fixture, download or build system is executed.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_compile as compiler
import appended_container as container
import appended_guest_check as guest
import appended_policy as policy
import appended_project as project
import appended_release as release
import appended_release_check as retained
import appended_wasm
import artifact
import dependency_archive as archive
import source_identity
from test_appended_wasm import fixtures, module


def document(path, value):
    path.write_bytes(container.canonical_json(value))


def pinned(path, **extra):
    return {'path': path.name, 'sha256': archive.digest(path), **extra}


def native_prefix():
    value = bytearray(4096)
    value[:16] = b'\x7fELF\x02\x01\x01' + bytes(9)
    struct.pack_into('<HHIQQQIHHHHHH', value, 16, 2, 62, 1, 256, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into('<IIQQQQQQ', value, 64, 1, 5, 0, 0x400000, 0, 4096, 4096, 4096)
    value[256:272] = container.STAMP_MAGIC + struct.pack('<Q', len(value))
    return bytes(value)


@unittest.skipUnless(os.name == 'posix', 'POSIX retained SDK/native permission fixture')
class GuestCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='guest recovery fixture ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.source = self.root / 'source'
        self.binary_source = self.source / 'src-bin-appended'
        self.binary_source.mkdir(parents=True)
        (self.binary_source / 'main.c').write_text('#include <foundation/appended/guest.h>\n')
        shutil.copytree(ROOT / 'sdk/appended', self.source / 'sdk/appended')
        headers = self.source / 'include/foundation/appended'
        headers.mkdir(parents=True)
        for name in ('abi.h', 'provider_abi.h'):
            shutil.copyfile(ROOT / 'include/foundation/appended' / name, headers / name)
        (self.source / 'tools').mkdir()
        for name in ('appended_compile.py', 'appended_wasm.py'):
            shutil.copyfile(ROOT / 'tools' / name, self.source / 'tools' / name)
        configuration = project.default_document()
        configuration['application'] = {'id': 'org.example.guest', 'name': 'Guest recovery fixture', 'version': '1.0.0'}
        configuration['appended']['binary']['enabled'] = True
        configuration['startup']['primary'] = 'binary'
        document(self.source / project.CONFIG_NAME, configuration)
        self.application = configuration['application']
        self.sdk_source = self.root / 'sdk source'
        tools = self.sdk_source / 'tools'
        tools.mkdir(parents=True)
        for name in ('clang', 'clang++', 'wasm-ld'):
            path = tools / name
            path.write_bytes(('inventoried non-executed ' + name).encode())
            path.chmod(0o755)
        self.sdk = {'schema_version': 1, 'profile': compiler.PROFILE, 'root': 'tools',
                    'tools': {'clang': 'clang', 'clangxx': 'clang++', 'wasm_ld': 'wasm-ld'},
                    'inventory': compiler._tree(tools)}
        self.sdk_path = self.sdk_source / 'sdk.json'
        document(self.sdk_path, self.sdk)
        sections, _, _, _ = fixtures()
        sections[5] = b'\x01\x01\x04\x10'
        self.module = module(sections)
        appended_wasm.validate_module(self.module)
        original_output = self.root / 'original.wasm'
        self.original_receipt_path = self.inputs / 'original-compile.json'
        with patch.dict(os.environ, {}, clear=True), patch.object(compiler, '_run', side_effect=self.compile_fixture):
            self.original = compiler.compile_guest(self.binary_source, 'c', self.sdk_path,
                original_output, self.original_receipt_path, ['main.c'], 4, 16, bindings_root=self.source)
        self.sdk_archive = self.inputs / 'guest-sdk.tar.gz'
        archive.archive_tree(self.sdk_source, self.sdk_archive)
        source_archive = self.inputs / 'source.tar.gz'
        self.source_identity = source_identity.archive_source(self.source, source_archive)
        prefix = native_prefix()
        self.descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'elf',
                           'profile': 'binary', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
                           'capabilities': [], 'services': [],
                           'executable': {'length': len(prefix), 'sha256': container.digest(prefix)},
                           'boundary_offset': 256, 'provenance': {'scope': 'non-executable structural fixture'},
                           'kernel_inputs': policy.kernel_source_tree(self.source)}
        descriptor_path = self.inputs / 'kernel.json'
        document(descriptor_path, self.descriptor)
        base = self.inputs / 'kernel.tar.gz'
        release._write_archive(base, {'bin/runtime': (prefix, 0o755)}, {'bin': 0o755})
        inventory = self.inputs / 'kernel.inventory.json'
        document(inventory, artifact.describe(base))
        package = container.build_package({'binary/application.wasm': self.module}, self.application,
            binary_entry='binary/application.wasm', binary_profile=compiler.PROFILE,
            identities={'source_tree': self.source_identity['tree_sha256']})
        payload = self.inputs / 'application.sfapp'
        payload.write_bytes(container.encode_package(package))
        recovery = self.inputs / 'recovery'
        recovery.write_bytes(b'explicit retained original recovery group')
        selected = {'schema_version': 1, 'kind': 'foundation-appended-selection', 'application': self.application,
                    'source': pinned(source_archive, tree_sha256=self.source_identity['tree_sha256']),
                    'payload': pinned(payload), 'kernels': [{'id': 'linux-guest-console', 'archive': pinned(base),
                    'inventory': pinned(inventory), 'descriptor': pinned(descriptor_path),
                    'runtime_member': 'bin/runtime', 'output': 'guest-linux.tar.gz',
                    'original_source': pinned(source_archive, tree_sha256=self.source_identity['tree_sha256']),
                    'recovery': [pinned(recovery)], 'evidence': []}]}
        selection_path = self.inputs / 'selection.json'
        document(selection_path, selected)
        self.candidate = self.root / 'candidate'
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('unexpected process')):
            result = release.prepare_release(selection_path, self.candidate)
            self.subject = release.verify_composition_subject(self.candidate, result['candidate_sha256'])
        self.runtime_scenario = self.inputs / 'runtime.json'
        self.runtime_argv = ['--expect-mode', 'binary', '--dispatch-hex', '01020304']
        document(self.runtime_scenario, {'schema_version': 1, 'kind': 'foundation-appended-runtime-scenario',
            'candidate_sha256': result['candidate_sha256'], 'artifact_id': 'linux-guest-console',
            'target': 'linux-x86_64', 'backend': 'core', 'calls': [{'id': 'positive-dispatch',
            'argv': self.runtime_argv, 'exit_code': 0,
            'stdout': 'actual guest scenario passed\n', 'stderr': ''}]})
        self.scenario_path = self.inputs / 'guest.json'
        self.scenario = {'schema_version': 1, 'kind': 'foundation-appended-guest-source-scenario',
            'candidate_sha256': result['candidate_sha256'], 'language': 'c', 'entries': ['main.c'],
            'memory_pages': 4, 'max_memory_pages': 16, 'reproduction': 'byte-exact',
            'inputs': {path.name: archive.digest(path) for path in
                       (self.sdk_archive, self.original_receipt_path, self.runtime_scenario)},
            'sdk': {'archive': self.sdk_archive.name, 'descriptor': 'sdk.json',
                    'descriptor_sha256': archive.digest(self.sdk_path)},
            'compile_receipt': self.original_receipt_path.name,
            'test': {'adapter': 'retained-runtime', 'artifact_id': 'linux-guest-console', 'scenario': self.runtime_scenario.name}}
        self.calls = []
        self.save_scenario()

    def save_scenario(self):
        document(self.scenario_path, self.scenario)

    def compile_fixture(self, argv, work, environment):
        output = Path(argv[argv.index('-o') + 1])
        if '-c' in argv:
            source = argv[argv.index('-c') + 1]
            output.write_bytes(b'portable object fixture')
            Path(argv[argv.index('-MF') + 1]).write_text('out: ' + source.replace(' ', '\\ ') + '\n')
        else:
            output.write_bytes(self.module)
        return ''

    def execute(self, argv, cwd, destination, environment, timeout):
        self.calls.append(list(argv))
        if Path(argv[0]).name in ('clang', 'clang++', 'wasm-ld'):
            self.assertIn('retained guest SDK', argv[0])
            self.assertEqual(environment['PATH'], '')
            self.compile_fixture(argv, cwd, environment)
            stdout = b'physical compiler fixture\n'
        else:
            self.assertEqual(Path(argv[0]).name, 'runtime')
            data = Path(argv[0]).read_bytes()
            artifact_input = container.parse_artifact(data, self.descriptor)
            self.assertEqual(artifact_input.package.file_bytes('binary/application.wasm'), self.module)
            self.assertEqual(argv[1:], self.runtime_argv)
            stdout = b'actual guest scenario passed\n'
        for name, data in (('stdout.bin', stdout), ('stderr.bin', b''), ('supervisor.log', b'owned fixture capture\n')):
            (destination / name).write_bytes(data)
        document(destination / 'native.json', {'argv': argv, 'exit_code': 0})
        return {'argv': argv, 'exit_code': 0, 'stdout': stdout, 'stderr': b'',
                'seconds': 0.001, 'process_tree_joined': True}

    def nested_runtime(self, child):
        with patch.object(retained, '_execute_runtime', side_effect=child['helpers']['execute']), \
                patch.object(retained.c, 'host_identity', return_value={'system': 'Linux', 'machine': 'x86_64'}):
            result = retained._runtime(child['directory'], child['subject'], child['artifact'],
                child['target'], child['backend'], child['evidence'], child['work'], child['scenario'],
                child['scenario_sha256'], child['timeout'], child['passed'])
        result['executed_tests'] = [item['id'] for item in result['calls']]
        result['junit'] = 'runtime/calls.junit.xml'
        return result

    def context(self, name='check'):
        evidence, work = self.root / (name + '-evidence'), self.root / (name + '-work')
        evidence.mkdir()
        work.mkdir()
        return {'directory': self.candidate, 'subject': self.subject, 'artifact': None,
            'target': 'portable-wasm32', 'backend': 'guest', 'evidence': evidence, 'work': work,
            'scenario': self.scenario_path, 'scenario_sha256': archive.digest(self.scenario_path),
            'timeout': 10, 'passed': [], 'helpers': {'new_json': retained._new_json, 'junit': retained._junit,
            'extract': retained._extract, 'tree': retained._tree, 'execute': self.execute,
            'environment': retained._environment, 'uncertain': retained._uncertain, 'runtime': self.nested_runtime,
            'application_call': retained.positive_application_call}}

    def run_guest(self, name='check'):
        context = self.context(name)
        with patch.dict(os.environ, {}, clear=True), patch.object(subprocess, 'Popen', side_effect=AssertionError('unexpected process')):
            result = guest.run(context)
        return context, result

    def replace_original(self, transform):
        value = copy.deepcopy(self.original)
        transform(value)
        document(self.original_receipt_path, value)
        self.scenario['inputs'][self.original_receipt_path.name] = archive.digest(self.original_receipt_path)
        self.save_scenario()

    def test_recovers_guest_once_with_actual_byte_gates_and_nested_frozen_runtime(self):
        with patch.object(compiler, 'compile_guest', wraps=compiler.compile_guest) as compile_once:
            context, result = self.run_guest()
        self.assertEqual(compile_once.call_count, 1)
        self.assertEqual(compile_once.call_args.kwargs['bindings_root'], context['work'] / 'restored guest source')
        self.assertEqual(context['passed'], guest.ASSERTIONS)
        self.assertEqual(result['reproduction'], 'byte-exact')
        self.assertEqual(result['delivered_module_sha256'], hashlib.sha256(self.module).hexdigest())
        self.assertEqual(result['delivered_module_sha256'], result['rebuilt_module_sha256'])
        self.assertEqual(result['executed_tests'], ['positive-dispatch'])
        self.assertEqual(result['kernel_build_invocations'], 0)
        self.assertEqual(len(result['compiler_commands']), 3)
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(all('--target=wasm32-unknown-unknown' in call for call in self.calls[:2]))
        self.assertIn('--no-entry', self.calls[2])
        self.assertFalse(any('cmake' in part.lower() for call in self.calls for part in call))
        evidence = context['evidence']
        retained.c.junit(evidence / 'guest.junit.xml', ['positive-dispatch'])
        self.assertEqual((evidence / 'guest/module.wasm').read_bytes(), self.module)
        self.assertEqual(json.loads((evidence / 'guest/audit.json').read_bytes()), appended_wasm.validate_module(self.module))
        self.assertTrue((evidence / 'guest/compiler/command-000/stdout.bin').is_file())
        self.assertTrue((evidence / 'guest/tests/runtime/positive-dispatch/stdout.bin').is_file())

    def test_original_receipt_wrong_inputs_types_module_or_audit_fail_before_tools(self):
        changes = {'schema-bool': lambda v: v.update(schema_version=True),
                   'source-mode': lambda v: v['sources']['main.c'].update(executable=0),
                   'binding': lambda v: v['bindings'].update({'guest.c': '0' * 64}),
                   'sdk': lambda v: v.update(sdk_inventory_sha256='0' * 64),
                   'module': lambda v: v['module'].update(bytes=len(self.module) + 1),
                   'audit': lambda v: v['audit']['memory'].update(minimum_pages=True),
                   'helper': lambda v: v.update(compiler_helper_sha256='0' * 64)}
        for name, change in changes.items():
            with self.subTest(name=name):
                self.replace_original(change)
                with self.assertRaisesRegex(ValueError, 'compile receipt differs'):
                    self.run_guest(name)
                self.assertEqual(self.calls, [])

    def test_original_order_flags_entries_or_mixed_sdk_roots_cannot_reproduce_recipe(self):
        changes = {'flag': lambda v: v['commands'][0].append('-DUNDECLARED'),
                   'order': lambda v: v['commands'].reverse(),
                   'root': lambda v: v['commands'][1].__setitem__(0, '/other/root/clang'),
                   'posix-backslash': lambda v: v['commands'][1].__setitem__(v['commands'][1].index('-c') + 1, '$WORK\\source\\main.c'),
                   'entry': lambda v: v['commands'][1].__setitem__(v['commands'][1].index('-c') + 1, '$WORK/source/other.c')}
        for name, change in changes.items():
            with self.subTest(name=name):
                self.replace_original(change)
                with self.assertRaisesRegex(ValueError, 'command|compiler|recipe'):
                    self.run_guest(name)

    def test_original_recipe_without_deterministic_maps_requires_guest_only_recompile(self):
        def legacy(value):
            for argv in value['commands']:
                argv[:] = [part for part in argv if not part.startswith(
                    ('-ffile-prefix-map=', '-fmacro-prefix-map=', '-fdebug-prefix-map=', '--remap-path-prefix='))]
        self.replace_original(legacy)
        with self.assertRaisesRegex(ValueError, 'deterministic guest-module recompile needed'):
            self.run_guest()

    def test_wrong_rebuilt_module_fails_real_validation(self):
        execute = self.execute
        def changed(argv, *args):
            result = execute(argv, *args)
            if Path(argv[0]).name == 'wasm-ld':
                Path(argv[argv.index('-o') + 1]).write_bytes(b'not a supported module')
            return result
        context = self.context()
        context['helpers']['execute'] = changed
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(appended_wasm.WasmError):
            guest.run(context)
        self.assertFalse((context['evidence'] / 'guest.junit.xml').exists())

    def test_fresh_receipt_is_independently_checked_against_module_and_actual_inputs(self):
        compile_guest = compiler.compile_guest
        def forged(*args, **kwargs):
            result = compile_guest(*args, **kwargs)
            result['module']['bytes'] = True
            document(Path(args[4]), result)
            return result
        context = self.context()
        with patch.object(compiler, 'compile_guest', side_effect=forged), patch.dict(os.environ, {}, clear=True), \
                self.assertRaisesRegex(ValueError, 'compile receipt differs'):
            guest.run(context)
        self.assertEqual(len(self.calls), 3)
        self.assertFalse((context['evidence'] / 'guest.junit.xml').exists())

    def test_nested_failed_or_skipped_guest_cases_do_not_become_passing_junit(self):
        runtime = self.nested_runtime
        def skipped(child):
            result = runtime(child)
            path = child['evidence'] / result['junit']
            path.write_text('<testsuite><testcase name="positive-dispatch" status="notrun"/></testsuite>')
            return result
        context = self.context()
        context['helpers']['runtime'] = skipped
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'failed, skipped or incomplete'):
            guest.run(context)
        self.assertFalse((context['evidence'] / 'guest.junit.xml').exists())

    def test_inspection_only_guest_tests_never_claim_application_execution(self):
        nested = json.loads(self.runtime_scenario.read_bytes())
        nested['calls'][0]['argv'] = ['--inspect']
        document(self.runtime_scenario, nested)
        self.scenario['inputs'][self.runtime_scenario.name] = archive.digest(self.runtime_scenario)
        self.save_scenario()
        with self.assertRaisesRegex(ValueError, 'positive application call'):
            self.run_guest()
        self.assertEqual(len(self.calls), 3)

    def test_shared_application_parser_preserves_payload_tokens_and_option_order(self):
        for name, argv in (('literal-help', ['--dispatch', '--help']),
                           ('literal-inspect', ['--dispatch', '--inspect']),
                           ('reordered', ['--dispatch-hex', '01020304', '--expect-mode', 'binary'])):
            with self.subTest(name=name):
                self.runtime_argv = argv
                nested = json.loads(self.runtime_scenario.read_bytes())
                nested['calls'][0]['argv'] = argv
                document(self.runtime_scenario, nested)
                self.scenario['inputs'][self.runtime_scenario.name] = archive.digest(self.runtime_scenario)
                self.save_scenario()
                context = self.context(name)
                application_call = Mock(wraps=retained.positive_application_call)
                context['helpers']['application_call'] = application_call
                with patch.dict(os.environ, {}, clear=True), \
                        patch.object(subprocess, 'Popen', side_effect=AssertionError('unexpected process')):
                    result = guest.run(context)
                application_call.assert_called_once_with(argv, 0, 'core')
                self.assertEqual(result['executed_tests'], ['positive-dispatch'])
                self.assertEqual(context['passed'], guest.ASSERTIONS)

    def test_intermediate_sdk_or_private_source_mutation_cannot_hide_in_later_calls(self):
        for name in ('sdk-tool', 'private-source'):
            with self.subTest(name=name):
                self.calls = []
                context = self.context(name)
                execute = self.execute
                def mutate(argv, cwd, *args):
                    result = execute(argv, cwd, *args)
                    if len(self.calls) == 1:
                        path = Path(argv[0]).parent / 'wasm-ld' if name == 'sdk-tool' else cwd / 'source/main.c'
                        path.write_bytes(b'changed after first tool call')
                    else:
                        # On the old adapter this later call could hide the
                        # intermediate bytes before its single final recheck.
                        if name == 'sdk-tool':
                            (Path(argv[0]).parent / 'wasm-ld').write_bytes(b'inventoried non-executed wasm-ld')
                        else:
                            (cwd / 'source/main.c').write_bytes((self.binary_source / 'main.c').read_bytes())
                    return result
                context['helpers']['execute'] = mutate
                with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'changed during a tool call'):
                    guest.run(context)
                self.assertEqual(len(self.calls), 1)
                self.assertFalse((context['evidence'] / 'guest.junit.xml').exists())

    def test_scenario_requires_all_pins_exact_reproduction_and_valid_memory(self):
        original = copy.deepcopy(self.scenario)
        for name in ('missing-pin', 'candidate', 'reproduction', 'memory', 'traversal'):
            with self.subTest(name=name):
                self.scenario = copy.deepcopy(original)
                if name == 'missing-pin':
                    self.scenario['inputs'].pop(self.sdk_archive.name)
                elif name == 'candidate':
                    self.scenario['candidate_sha256'] = '0' * 64
                elif name == 'reproduction':
                    self.scenario['reproduction'] = 'not-claimed'
                elif name == 'memory':
                    self.scenario['memory_pages'] = True
                else:
                    self.scenario['sdk']['descriptor'] = '../outside.json'
                self.save_scenario()
                with self.assertRaises(ValueError):
                    self.run_guest(name)
                self.assertEqual(self.calls, [])

    def test_sdk_bundle_absolute_root_and_extra_tool_files_fail_before_tools(self):
        for name in ('absolute', 'unlisted'):
            with self.subTest(name=name):
                data = copy.deepcopy(self.sdk)
                if name == 'absolute':
                    data['root'] = str(self.sdk_source / 'tools')
                else:
                    (self.sdk_source / 'tools/unlisted').write_text('undeclared input')
                document(self.sdk_path, data)
                self.sdk_archive.unlink()
                archive.archive_tree(self.sdk_source, self.sdk_archive)
                self.scenario['inputs'][self.sdk_archive.name] = archive.digest(self.sdk_archive)
                self.scenario['sdk']['descriptor_sha256'] = archive.digest(self.sdk_path)
                self.save_scenario()
                with self.assertRaisesRegex(ValueError, 'relative|inventory'):
                    self.run_guest(name)
                self.assertEqual(self.calls, [])

    def test_sdk_expansion_bound_and_changed_pinned_inputs_fail_closed(self):
        with patch.object(guest, 'MAX_SDK_BYTES', 8), self.assertRaisesRegex(ValueError, 'exceeds limits'):
            self.run_guest('bound')
        self.original_receipt_path.write_bytes(b'changed pinned receipt')
        with self.assertRaisesRegex(ValueError, 'pinned inventory'):
            self.run_guest('changed')
        self.assertEqual(self.calls, [])

    def test_unjoined_compiler_does_not_produce_guest_test_outcomes(self):
        context = self.context()
        def uncertain(*args):
            raise retained.ProcessTreeError('fixture join uncertainty; retain output ownership')
        context['helpers']['execute'] = uncertain
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(retained.ProcessTreeError, 'retain output ownership'):
            guest.run(context)
        retained_scratch = list((context['evidence'] / 'guest').glob('.foundation-guest-*'))
        self.assertEqual(len(retained_scratch), 1)
        self.assertFalse((context['evidence'] / 'guest.junit.xml').exists())
        self.assertNotIn('guest-compile', context['passed'])

    def test_returned_unconfirmed_compiler_join_preserves_its_scratch(self):
        context = self.context()
        execute = self.execute
        def not_joined(*args):
            result = execute(*args)
            result['process_tree_joined'] = False
            return result
        context['helpers']['execute'] = not_joined
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(retained.ProcessTreeError, 'retain output ownership'):
            guest.run(context)
        self.assertEqual(len(list((context['evidence'] / 'guest').glob('.foundation-guest-*'))), 1)
        self.assertFalse((context['evidence'] / 'guest.junit.xml').exists())


class CommandMappingTests(unittest.TestCase):
    def setUp(self):
        self.sdk = {'tools': {'clang': 'bin/clang', 'wasm_ld': 'bin/wasm-ld', 'rustc': 'rust/bin/rustc'},
                    'rust_sysroot': 'rust'}
        self.host = {'system': 'Linux', 'machine': 'x86_64'}

    def commands(self, root):
        return [[root + '/bin/clang', *[option + root + '=/foundation/guest/sdk'
                  for option in ('-ffile-prefix-map=', '-fmacro-prefix-map=', '-fdebug-prefix-map=')],
                 '-ffile-prefix-map=$WORK=/foundation/guest/work', '-c', '$WORK/source/main.c'],
                [root + '/rust/bin/rustc', '--remap-path-prefix=' + root + '=/foundation/guest/sdk',
                 '--remap-path-prefix=$WORK=/foundation/guest/work', '--sysroot', root + '/rust',
                 '$WORK/source/lib.rs']]

    def test_only_exact_sdk_mapping_operands_relocate_with_the_pinned_tools(self):
        original = guest._commands(self.commands('/original/sdk'), self.sdk, self.host)
        restored = guest._commands(self.commands('/restored SDK/tools'), self.sdk, self.host)
        self.assertEqual(original, restored)
        self.assertEqual(original[0][1], '-ffile-prefix-map=$SDK=/foundation/guest/sdk')
        self.assertEqual(original[1][1], '--remap-path-prefix=$SDK=/foundation/guest/sdk')
        self.assertEqual(original[0][-1], '$WORK/source/main.c')

    def test_wrong_sdk_root_or_logical_destination_is_never_normalized(self):
        for name, replacement in (('root', '/different/sdk=/foundation/guest/sdk'),
                                   ('destination', '/original/sdk=/different/logical'),
                                   ('work', '$WORK=/different/logical')):
            with self.subTest(name=name):
                commands = self.commands('/original/sdk')
                commands[0][1] = '-ffile-prefix-map=' + replacement
                with self.assertRaisesRegex(ValueError, 'unsupported prefix mapping'):
                    guest._commands(commands, self.sdk, self.host)

    def test_posix_literal_backslashes_remain_distinct_in_mapping_operands(self):
        commands = self.commands('/original/sdk')
        commands[0][1] = '-ffile-prefix-map=\\original\\sdk=/foundation/guest/sdk'
        with self.assertRaisesRegex(ValueError, 'unsupported prefix mapping'):
            guest._commands(commands, self.sdk, self.host)


if __name__ == '__main__':
    unittest.main()
