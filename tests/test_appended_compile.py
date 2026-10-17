"""Retained guest compiler inputs, portable profile and publication contracts."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import appended_compile


class GuestCompileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='foundation guest with spaces ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'main.c').write_text('#include <foundation/appended/guest.h>\n', encoding='utf-8')
        self.toolroot = self.root / 'tools'
        self.toolroot.mkdir()
        for name in ('clang', 'clang++', 'wasm-ld'):
            path = self.toolroot / name
            path.write_bytes(name.encode())
            path.chmod(0o755)
        self.sdk = self.root / 'sdk.json'
        self.data = {'schema_version': 1, 'profile': appended_compile.PROFILE, 'root': 'tools',
                     'tools': {'clang': 'clang', 'clangxx': 'clang++', 'wasm_ld': 'wasm-ld'},
                     'inventory': appended_compile._tree(self.toolroot)}
        self.save_sdk()
        self.output, self.receipt = self.root / 'module.wasm', self.root / 'module.json'
        self.calls = []

    def save_sdk(self):
        self.sdk.write_text(json.dumps(self.data), encoding='utf-8')

    def fake_run(self, argv, work, environment):
        self.calls.append(argv)
        if Path(argv[0]).name == 'rustc':
            Path(argv[argv.index('-o') + 1]).write_bytes(b'archive fixture')
            dep = next(part.removeprefix('--emit=link,dep-info=') for part in argv
                       if part.startswith('--emit=link,dep-info='))
            source = argv[argv.index('-o') - 1].replace(' ', '\\ ')
            Path(dep).write_text('output: ' + source + '\n')
        elif '-c' in argv:
            source = Path(argv[argv.index('-c') + 1])
            destination = Path(argv[argv.index('-o') + 1])
            destination.write_bytes(b'object')
            dependencies = str(source).replace(' ', '\\ ')
            Path(argv[argv.index('-MF') + 1]).write_text('output: ' + dependencies + '\n', encoding='utf-8')
        else:
            Path(argv[argv.index('-o') + 1]).write_bytes(b'\x00asm\x01\x00\x00\x00')

    def compile(self, **kwargs):
        with patch.dict(os.environ, {}, clear=True), patch.object(appended_compile, '_run', side_effect=self.fake_run), \
             patch.object(appended_compile.appended_wasm, 'validate_module', return_value={'profile': appended_compile.PROFILE}) as audit:
            result = appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt, **kwargs)
            audit.assert_called_once_with(self.output.read_bytes())
            return result

    def archived_bindings(self):
        archived = self.root / 'archived-project'
        shutil.copytree(appended_compile.ROOT / 'sdk/appended', archived / 'sdk/appended')
        headers = archived / 'include/foundation/appended'
        headers.mkdir(parents=True)
        for name in ('abi.h', 'provider_abi.h'):
            shutil.copyfile(appended_compile.ROOT / 'include/foundation/appended' / name, headers / name)
        return archived

    def rust_sdk(self):
        (self.source / 'main.rs').write_text('#![no_std]\n')
        rustc = self.toolroot / 'rustc'
        rustc.write_bytes(b'retained rust compiler fixture')
        rustc.chmod(0o755)
        target = self.toolroot / 'rust/lib/rustlib/wasm32v1-none/lib'
        target.mkdir(parents=True)
        for name in ('libcore-fixture.rlib', 'libcompiler_builtins-fixture.rlib'):
            (target / name).write_bytes(b'target library fixture')
        self.data['tools']['rustc'] = 'rustc'
        self.data['rust_sysroot'] = 'rust'
        self.data['inventory'] = appended_compile._tree(self.toolroot)
        self.save_sdk()

    def test_compiler_environment_omits_ambient_paths_and_fixes_time_and_locale(self):
        ambient = {'PATH': '/ambient/bin', 'HOME': '/ambient/home', 'TMPDIR': '/ambient/tmpdir',
                   'TMP': '/ambient/tmp', 'TEMP': '/ambient/temp', 'SOURCE_DATE_EPOCH': '1234567890',
                   'TZ': 'Pacific/Honolulu', 'LANG': 'different', 'LC_ALL': 'different',
                   'COMSPEC': 'ambient-shell', 'PATHEXT': '.ambient', 'USER': 'ambient-user',
                   'SystemRoot': 'retained-windows-root', 'WINDIR': 'retained-windows-root'}
        with patch.dict(os.environ, ambient, clear=True):
            environment = appended_compile._environment()
            host_environment = {key: value for key, value in os.environ.items()
                                if key in {'SystemRoot', 'SYSTEMROOT', 'WINDIR'}} if os.name == 'nt' else {}
        expected = {'PATH': '', 'HOME': '', 'LANG': 'C', 'LC_ALL': 'C',
                    'SOURCE_DATE_EPOCH': '0', 'TZ': 'UTC'}
        expected.update(host_environment)
        self.assertEqual(environment, expected)

    def test_c_and_cpp_snapshots_use_epoch_dates_and_remap_private_and_sdk_paths(self):
        archived = self.archived_bindings()
        cpp = self.source / 'main.cpp'
        cpp.write_text('#include <foundation/appended/guest.hpp>\n')
        original_dates = {}
        for base in (self.source, archived):
            for path in base.rglob('*'):
                if path.is_file():
                    os.utime(path, ns=(1234567890000000000, 1234567890000000000))
                    original_dates[path] = path.stat().st_mtime_ns
        original = self.fake_run
        for language, entry in (('c', 'main.c'), ('c++', 'main.cpp')):
            with self.subTest(language=language):
                output, receipt = self.root / (language + '.wasm'), self.root / (language + '.json')
                observed = []
                def run(argv, work, environment):
                    observed.append(work)
                    for base in (work / 'source', work / 'bindings'):
                        for path in base.rglob('*'):
                            if path.is_file():
                                self.assertEqual(path.stat().st_mtime_ns, 0, path)
                    if '-c' in argv:
                        for original_path, logical in ((work, '/foundation/guest/work'),
                                                       (self.toolroot, '/foundation/guest/sdk')):
                            for option in ('-ffile-prefix-map', '-fmacro-prefix-map', '-fdebug-prefix-map'):
                                self.assertIn(option + '=' + str(original_path) + '=' + logical, argv)
                    self.assertEqual(environment['SOURCE_DATE_EPOCH'], '0')
                    self.assertEqual(environment['TZ'], 'UTC')
                    self.assertEqual(environment['HOME'], '')
                    original(argv, work, environment)
                with patch.object(appended_compile, '_run', side_effect=run), \
                        patch.dict(os.environ, {}, clear=True), \
                        patch.object(appended_compile.appended_wasm, 'validate_module', return_value={}):
                    result = appended_compile.compile_guest(self.source, language, self.sdk, output,
                                                           receipt, entries=[entry], bindings_root=archived)
                self.assertTrue(observed)
                self.assertTrue(any('-ffile-prefix-map=$WORK=/foundation/guest/work' in argv
                                    for argv in result['commands']))
                self.assertFalse(any(str(observed[0]) in part for argv in result['commands'] for part in argv))
        self.assertTrue(all(path.stat().st_mtime_ns == before for path, before in original_dates.items()))

    def test_unsupported_deterministic_compiler_flag_fails_without_retry_or_publication(self):
        diagnostic = 'guest compiler failed (1):\nunknown argument: -ffile-prefix-map'
        with patch.object(appended_compile, '_run', side_effect=ValueError(diagnostic)) as run, \
                patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'unknown argument'):
            appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt)
        run.assert_called_once()
        self.assertTrue(any(part.startswith('-ffile-prefix-map=') for part in run.call_args.args[0]))
        self.assertFalse(self.output.exists())
        self.assertFalse(self.receipt.exists())
        self.assertFalse(list(self.root.glob('.foundation-guest-*')))

    def test_unrepresentable_prefix_mapping_fails_before_invoking_compilers(self):
        destination = self.root / 'output=directory'
        destination.mkdir()
        with patch.object(appended_compile, '_run') as run, patch.dict(os.environ, {}, clear=True), \
                self.assertRaisesRegex(ValueError, 'prefix maps require workspace and SDK paths without'):
            appended_compile.compile_guest(self.source, 'c', self.sdk, destination / 'module.wasm',
                                           destination / 'module.json')
        run.assert_not_called()
        self.assertEqual(list(destination.iterdir()), [])

    def test_compiles_only_guest_objects_and_binds_full_inputs_and_audit(self):
        result = self.compile()
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(result['module']['sha256'], hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertEqual(result, json.loads(self.receipt.read_text()))
        self.assertIn('include/foundation/appended/abi.h', result['bindings'])
        self.assertIn('main.c', result['sources'])
        self.assertIn('sdk_inventory_sha256', result)
        self.assertTrue(all('--target=wasm32-unknown-unknown' in argv for argv in self.calls[:-1]))
        self.assertTrue(all('-nostdinc' in argv for argv in self.calls[:-1]))
        self.assertIn('--compress-relocations', self.calls[-1])
        self.assertNotIn('-DFOUNDATION_GUEST_REQUIRE_HOOKS', self.calls[0])
        self.assertFalse(any('cmake' in part.lower() for argv in self.calls for part in argv))
        self.assertTrue(any('$WORK' in part for argv in result['commands'] for part in argv))
        self.assertFalse(list(self.root.glob('.foundation-guest-*')))

    def test_archived_bindings_are_snapshotted_and_bound_with_current_trusted_helpers(self):
        archived = self.archived_bindings()
        runtime = archived / 'sdk/appended/guest.c'
        runtime.write_bytes(runtime.read_bytes() + b'\n/* archived runtime */\n')
        abi = archived / 'include/foundation/appended/abi.h'
        abi.write_bytes(abi.read_bytes() + b'\n/* archived ABI */\n')
        helpers = archived / 'tools'
        helpers.mkdir()
        for name in ('appended_compile.py', 'appended_wasm.py'):
            (helpers / name).write_text('raise RuntimeError("untrusted archived helper")\n')
        original = self.fake_run
        def run(argv, work, environment):
            self.assertEqual((work / 'bindings/guest.c').read_bytes(), runtime.read_bytes())
            self.assertEqual((work / 'bindings/include/foundation/appended/abi.h').read_bytes(), abi.read_bytes())
            original(argv, work, environment)
        with patch.object(self, 'fake_run', side_effect=run):
            result = self.compile(bindings_root=archived)
        self.assertEqual(result['bindings']['guest.c'], appended_compile._digest(runtime))
        self.assertEqual(result['bindings']['include/foundation/appended/abi.h'], appended_compile._digest(abi))
        self.assertEqual(result['compiler_helper_sha256'], appended_compile._digest(Path(appended_compile.__file__)))
        self.assertEqual(result['validator_sha256'], appended_compile._digest(Path(appended_compile.appended_wasm.__file__)))

    def test_invalid_missing_or_linked_archived_bindings_fail_before_compilation(self):
        archived = self.archived_bindings()
        alias = self.root / 'archived-link'
        alias.symlink_to(archived, target_is_directory=True)
        include = archived / 'sdk/appended/include'
        include.rename(archived / 'saved-include')
        cases = (self.root / 'absent-bindings', self.source / 'main.c', alias, archived)
        with patch.object(appended_compile, '_run') as run:
            for root in cases:
                with self.subTest(root=root), self.assertRaises(ValueError):
                    appended_compile.compile_guest(self.source, 'c', self.sdk, self.output,
                                                   self.receipt, bindings_root=root)
            include.symlink_to(archived / 'saved-include', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'linked input or output'):
                appended_compile.compile_guest(self.source, 'c', self.sdk, self.output,
                                               self.receipt, bindings_root=archived)
            include.unlink()
            (archived / 'saved-include').rename(include)
            (archived / 'include/foundation/appended/provider_abi.h').unlink()
            with self.assertRaises(FileNotFoundError):
                appended_compile.compile_guest(self.source, 'c', self.sdk, self.output,
                                               self.receipt, bindings_root=archived)
        run.assert_not_called()

    def test_changed_archived_bindings_during_compilation_invalidate_the_result(self):
        archived = self.archived_bindings()
        def run(argv, work, environment):
            self.fake_run(argv, work, environment)
            (archived / 'sdk/appended/include/added.h').write_text('/* new binding */\n')
        with patch.object(appended_compile, '_run', side_effect=run), patch.dict(os.environ, {}, clear=True), \
                patch.object(appended_compile.appended_wasm, 'validate_module', return_value={}):
            with self.assertRaisesRegex(ValueError, 'changed during compilation'):
                appended_compile.compile_guest(self.source, 'c', self.sdk, self.output,
                                               self.receipt, bindings_root=archived)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.receipt.exists())
        self.assertFalse(list(self.root.glob('.foundation-guest-*')))

    def test_changed_binding_snapshot_is_rejected_before_tool_invocation(self):
        archived = self.archived_bindings()
        original = appended_compile.shutil.copyfile
        def copy(source, destination, *args, **kwargs):
            result = original(source, destination, *args, **kwargs)
            if Path(destination).name == 'guest.c':
                Path(destination).write_bytes(b'changed snapshot')
            return result
        with patch.object(appended_compile.shutil, 'copyfile', side_effect=copy), \
                patch.object(appended_compile, '_run') as run, patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'bindings changed during snapshot'):
                appended_compile.compile_guest(self.source, 'c', self.sdk, self.output,
                                               self.receipt, bindings_root=archived)
        run.assert_not_called()

    def test_compile_cli_forwards_explicit_bindings_and_preserves_positional_defaults(self):
        with patch.object(appended_compile, 'compile_guest', return_value={'module': {'sha256': 'digest'}}) as compile_guest, \
                patch('builtins.print'):
            self.assertEqual(appended_compile.main(['compile', '--source', 'source', '--language', 'c',
                                                   '--sdk', 'sdk.json', '--output', 'module.wasm',
                                                   '--receipt', 'module.json', '--bindings-root', 'archive']), 0)
        compile_guest.assert_called_once_with('source', 'c', 'sdk.json', 'module.wasm',
                                             'module.json', None, 4, 16, bindings_root='archive')

    def test_uncertain_compiler_cleanup_preserves_workspace_without_publishing(self):
        workspaces = []
        def run(argv, work, environment):
            workspaces.append(work)
            (work / 'writer-output').write_bytes(b'owned output')
            raise appended_compile.process_tree.ProcessTreeError('unconfirmed writers; retain output ownership')
        with patch.object(appended_compile, '_run', side_effect=run), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(appended_compile.process_tree.ProcessTreeError,
                                        'retained compiler workspace: ') as raised:
                appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt)
        self.assertIn(str(workspaces[0]), str(raised.exception))
        self.assertEqual((workspaces[0] / 'writer-output').read_bytes(), b'owned output')
        self.assertFalse(self.output.exists())
        self.assertFalse(self.receipt.exists())

    def test_ordinary_compiler_failure_cleans_workspace_without_publishing(self):
        with patch.object(appended_compile, '_run', side_effect=ValueError('compiler failed')), \
                patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'compiler failed'):
            appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt)
        self.assertFalse(list(self.root.glob('.foundation-guest-*')))
        self.assertFalse(self.output.exists())
        self.assertFalse(self.receipt.exists())

    def test_workspace_preserves_wrapped_cleanup_uncertainty(self):
        owned = []
        with self.assertRaisesRegex(appended_compile.process_tree.ProcessTreeError,
                                    'retained compiler workspace: ') as raised:
            with appended_compile._workspace(self.root) as work:
                owned.append(work)
                try:
                    raise appended_compile.process_tree.ProcessTreeError('writer ownership unconfirmed')
                except appended_compile.process_tree.ProcessTreeError as error:
                    raise RuntimeError('outer compiler failure') from error
        self.assertIn(str(owned[0]), str(raised.exception))
        self.assertTrue(owned[0].is_dir())

    def test_run_retains_owner_and_open_log_when_close_is_unconfirmed(self):
        for failure, finish_failure in ((subprocess.TimeoutExpired(['compiler'], 5), None),
                                        (RuntimeError('cleanup failed'), ValueError('compiler failed'))):
            with self.subTest(failure=type(failure).__name__, finish_failure=finish_failure):
                owner = Mock()
                owner.poll.return_value, owner.finish.return_value = 0, 0
                owner.finish.side_effect = finish_failure
                owner.close.side_effect = failure
                retained = []
                with patch.object(appended_compile.process_tree, 'launch', return_value=owner) as launch, \
                        patch.object(appended_compile, '_UNCONFIRMED_RUNS', retained):
                    with self.assertRaisesRegex(appended_compile.process_tree.ProcessTreeError,
                                                'cleanup uncertain; retain output ownership'):
                        appended_compile._run(['compiler'], self.root, {})
                self.assertEqual(len(retained), 1)
                self.assertIs(retained[0][0], owner)
                stream = retained[0][1]
                self.assertIs(launch.call_args.kwargs['stream'], stream)
                self.assertFalse(stream.closed)
                self.assertTrue(Path(stream.name).is_file())
                # The fixture has no child process; retire only our mocked owner.
                stream.close()
                Path(stream.name).unlink()

    def test_run_preserves_open_log_after_uncertain_launch(self):
        streams, retained = [], []
        def launch(argv, **kwargs):
            streams.append(kwargs['stream'])
            raise appended_compile.process_tree.ProcessTreeError('launch writer cleanup is uncertain')
        with patch.object(appended_compile.process_tree, 'launch', side_effect=launch), \
                patch.object(appended_compile, '_UNCONFIRMED_RUNS', retained):
            with self.assertRaisesRegex(appended_compile.process_tree.ProcessTreeError, 'launch writer cleanup'):
                appended_compile._run(['compiler'], self.root, {})
        self.assertEqual(retained, [(None, streams[0])])
        self.assertFalse(streams[0].closed)
        self.assertTrue(Path(streams[0].name).is_file())
        streams[0].close()
        Path(streams[0].name).unlink()

    def test_run_closes_log_after_ordinary_launch_failure(self):
        streams = []
        def launch(argv, **kwargs):
            streams.append(kwargs['stream'])
            raise OSError('compiler could not be launched')
        with patch.object(appended_compile.process_tree, 'launch', side_effect=launch):
            with self.assertRaisesRegex(OSError, 'could not be launched'):
                appended_compile._run(['compiler'], self.root, {})
        self.assertTrue(streams[0].closed)
        self.assertFalse(Path(streams[0].name).exists())

    def test_run_closes_logs_after_confirmed_success_and_ordinary_failure(self):
        for code in (0, 7):
            with self.subTest(code=code):
                owner = Mock()
                owner.poll.return_value, owner.finish.return_value = code, code
                streams = []
                def launch(argv, **kwargs):
                    stream = kwargs['stream']
                    streams.append(stream)
                    stream.write(b'compiler output\n')
                    stream.flush()
                    return owner
                with patch.object(appended_compile.process_tree, 'launch', side_effect=launch):
                    if code:
                        with self.assertRaisesRegex(ValueError, r'guest compiler failed \(7\):\ncompiler output'):
                            appended_compile._run(['compiler'], self.root, {})
                    else:
                        self.assertEqual(appended_compile._run(['compiler'], self.root, {}), 'compiler output\n')
                owner.close.assert_called_once_with()
                self.assertTrue(streams[0].closed)
                self.assertFalse(Path(streams[0].name).exists())

    def test_rust_archive_requires_real_hooks_and_selects_only_needed_members(self):
        self.rust_sdk()
        def run(argv, work, environment):
            if Path(argv[0]).name == 'rustc':
                for original, logical in ((work, '/foundation/guest/work'),
                                          (self.toolroot, '/foundation/guest/sdk')):
                    self.assertIn('--remap-path-prefix=' + str(original) + '=' + logical, argv)
                self.assertEqual(environment['HOME'], '')
                self.assertFalse({'TMP', 'TEMP', 'TMPDIR'} & set(environment))
                for base in (work / 'source', work / 'bindings'):
                    self.assertTrue(all(path.stat().st_mtime_ns == 0 for path in base.rglob('*') if path.is_file()))
            self.fake_run(argv, work, environment)
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(appended_compile, '_run', side_effect=run), \
                patch.object(appended_compile.appended_wasm, 'validate_module', return_value={}):
            appended_compile.compile_guest(self.source, 'rust', self.sdk, self.output,
                                          self.receipt, entries=['main.rs'])
        self.assertIn('-DFOUNDATION_GUEST_REQUIRE_HOOKS', self.calls[0])
        self.assertTrue(any(part.endswith('/application.a') for part in self.calls[-1]))
        self.assertNotIn('--whole-archive', self.calls[-1])
        self.assertNotIn('--no-whole-archive', self.calls[-1])
        self.assertEqual(sum('--target=wasm32v1-none' in call for call in self.calls), 2)

    def test_missing_sdk_and_changed_or_unlisted_tool_inputs_fail_before_invocation(self):
        with patch.object(appended_compile, '_run') as run:
            with self.assertRaises(FileNotFoundError):
                appended_compile.compile_guest(self.source, 'c', self.root / 'absent.json', self.output, self.receipt)
            (self.toolroot / 'sibling.cfg').write_text('undeclared tool configuration', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'inventory mismatch'):
                appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt)
            run.assert_not_called()

    def test_binary_source_policy_rejects_forbidden_files_and_references(self):
        for name, content in (('extra.js', b'0'), ('manifest.json', b'{"dependency":"wasm-bindgen"}'),
                              ('helper.c', b'/* load application.mjs */'), ('package.json', b'{}')):
            with self.subTest(name=name), patch.object(appended_compile, '_run') as run:
                bad = self.source / name
                bad.write_bytes(content)
                with self.assertRaisesRegex(ValueError, 'unsupported binary source'):
                    appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt)
                run.assert_not_called()
                bad.unlink()

    def test_rust_requires_separate_explicit_retained_tools_and_target(self):
        with self.assertRaisesRegex(ValueError, 'pinned guest compiler'):
            appended_compile.load_sdk(self.sdk, 'rust')
        self.data['tools']['rustc'] = 'clang'
        self.save_sdk()
        with self.assertRaisesRegex(ValueError, 'missing retained Rust wasm32v1-none sysroot'):
            appended_compile.load_sdk(self.sdk, 'rust')

    def test_existing_outputs_are_preserved_without_tool_invocation(self):
        self.output.write_bytes(b'prior module')
        with patch.object(appended_compile, '_run') as run, self.assertRaisesRegex(ValueError, 'absent paths'):
            appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt)
        run.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'prior module')

    def test_undeclared_header_is_rejected_and_no_output_is_published(self):
        def run(argv, work, environment):
            self.fake_run(argv, work, environment)
            if '-c' in argv:
                Path(argv[argv.index('-MF') + 1]).write_text('output: /etc/hosts\n')
        with patch.dict(os.environ, {}, clear=True), patch.object(appended_compile, '_run', side_effect=run):
            with self.assertRaisesRegex(ValueError, 'undeclared dependency'):
                appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.receipt.exists())

    def test_changed_source_during_compile_invalidates_result(self):
        def run(argv, work, environment):
            self.fake_run(argv, work, environment)
            (self.source / 'main.c').write_text('changed', encoding='utf-8')
        with patch.object(appended_compile, '_run', side_effect=run), patch.dict(os.environ, {}, clear=True), \
             patch.object(appended_compile.appended_wasm, 'validate_module', return_value={}):
            with self.assertRaisesRegex(ValueError, 'changed during compilation'):
                appended_compile.compile_guest(self.source, 'c', self.sdk, self.output, self.receipt)
        self.assertFalse(self.output.exists())

    def test_sdk_duplicate_keys_and_symlinks_fail_closed(self):
        self.sdk.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            appended_compile.load_sdk(self.sdk, 'c')
        self.save_sdk()
        (self.toolroot / 'link').symlink_to(self.toolroot / 'clang')
        with self.assertRaisesRegex(ValueError, 'regular file'):
            appended_compile.load_sdk(self.sdk, 'c')

    def test_rust_application_sources_keep_target_details_behind_sdk(self):
        root = Path(__file__).resolve().parents[1]
        sources = sorted((root / 'src-bin-appended/rust/src').rglob('*.rs'))
        self.assertTrue(sources)
        target_details = re.compile(r'\b(?:core|std)\s*::\s*arch\b|\btarget_\w+\b|\bwasm(?:32|64)\b')
        for source in sources:
            with self.subTest(source=source.relative_to(root).as_posix()):
                self.assertIsNone(target_details.search(source.read_text()),
                                  'application target details belong in the guest SDK')

    def test_rust_constants_are_generated_from_current_authoritative_header_values(self):
        root = Path(__file__).resolve().parents[1]
        header = (root / 'include/foundation/appended/abi.h').read_text()
        rust = (root / 'sdk/appended/rust/src/abi.rs').read_text()
        expected = {}
        for name, literal in re.findall(r'^#define FOUNDATION_APPENDED_(\w+) (0x[0-9a-fA-F]+|[0-9]+)u?$', header, re.M):
            expected[name] = int(literal, 0)
        actual = {name: int(literal.replace('_', ''), 0) for name, literal in
                  re.findall(r'^pub const (\w+): u(?:16|32|64) = (0x[0-9a-fA-F_]+|[0-9_]+);$', rust, re.M)}
        self.assertTrue(expected)
        for name, number in expected.items():
            self.assertEqual(actual.get(name), number, name)
        header = header.replace('\\\n', '')
        schema_hex = re.search(r'BOOTSTRAP_SCHEMA_SHA256_HEX "([0-9a-f]+)"', header).group(1)
        schema_bytes = re.search(r'BOOTSTRAP_SCHEMA_BYTES ([^\n]+)', header).group(1)
        expected_bytes = bytes(int(p.strip(), 0) for p in schema_bytes.split(','))
        actual_bytes = re.search(r'BOOTSTRAP_SCHEMA_BYTES: \[u8; 32\] = \[([^]]+)\]', rust, re.S).group(1)
        self.assertEqual(bytes(int(p.strip(), 0) for p in actual_bytes.split(',') if p.strip()), expected_bytes)
        self.assertEqual(expected_bytes.hex(), schema_hex)
        self.assertEqual(hashlib.sha256((root / 'abi/appended/v1/bootstrap.json').read_bytes()).hexdigest(), schema_hex)

    def test_dependency_reader_accepts_multirule_rust_files_and_rejects_external_rule(self):
        dep = self.root / 'rust.d'
        escaped = str(self.source / 'main.c').replace(' ', '\\ ')
        dep.write_text('result.rlib: ' + escaped + '\n\nresult.d: ' + escaped + '\n' + escaped + ':\n')
        appended_compile._dependencies(dep, self.root)
        dep.write_text(dep.read_text() + 'other: /etc/hosts\n')
        with self.assertRaisesRegex(ValueError, 'undeclared dependency'):
            appended_compile._dependencies(dep, self.root)

    def test_publication_failure_preserves_concurrent_replacement_inode(self):
        def publish(path, data):
            if path == self.receipt:
                self.output.unlink()
                self.output.write_bytes(b'concurrent replacement')
                raise FileExistsError('receipt appeared')
            return original(path, data)
        original = appended_compile._publish
        with patch.object(appended_compile, '_publish', side_effect=publish), self.assertRaises(FileExistsError):
            self.compile()
        self.assertEqual(self.output.read_bytes(), b'concurrent replacement')

    def test_output_parent_symlink_is_rejected(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with patch.object(appended_compile, '_run') as run, self.assertRaisesRegex(ValueError, 'linked input or output'):
            appended_compile.compile_guest(self.source, 'c', self.sdk, alias / 'module.wasm', self.receipt)
        run.assert_not_called()

    def test_view_binding_identity_matches_authoritative_value_contract(self):
        root = Path(__file__).resolve().parents[1]
        schema_bytes = (root / 'abi/appended/view/v1.json').read_bytes()
        schema = json.loads(schema_bytes)
        header = (root / 'sdk/appended/include/foundation/appended/view.h').read_text().replace('\\\n', '')
        digest = re.search(r'VIEW_SCHEMA_SHA256 "([0-9a-f]+)"', header).group(1)
        self.assertEqual(digest, hashlib.sha256(schema_bytes).hexdigest())
        literal = re.search(r'VIEW_SCHEMA_BYTES\s+([^\n]+)', header).group(1)
        self.assertEqual(bytes(int(item.strip(), 0) for item in literal.split(',')).hex(), digest)
        self.assertEqual(schema['name'], 'foundation.view')
        self.assertEqual(schema['operations']['1']['name'], 'replace')
        self.assertEqual(schema['operations']['2']['name'], 'host_service')
        for name, number in (('group', 1), ('label', 2), ('button', 3), ('text', 6)):
            self.assertIn(str(number) + name, schema['records']['widget']['3'])
            self.assertIn('FOUNDATION_GUEST_VIEW_' + name.upper() + ' ' + str(number) + 'u', header)


if __name__ == '__main__':
    unittest.main()
