"""Rich profile routing fixtures; no fixture is eligible retained-engine evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build


class ReachedJobSelection(Exception):
    pass


def options(root, *, native=False, profile='web', document='pixel'):
    return ['build', '--core-provider', 'cpp', '--kernel-maintenance', '--appended-profile', profile,
            '--gui-source', str(root / 'gui'), '--gui-backends', 'terminal' if native else 'wasm',
            '--sdk', str(root / 'sdk'), '--engine-group', str(root / 'engine'),
            '--engine-native-document-profile' if native else '--engine-document-profile', document,
            *[argument for name, pin in (('recipe', 'a'), ('manifest', 'b'), ('proof', 'c'), ('runtime', 'd'))
              for argument in ('--engine-' + name + '-sha256', pin * 64)]]


def inert_inputs(root, *, system='Emscripten', processor='wasm32', triple='wasm32-emscripten'):
    for name in ('sdk', 'engine', 'gui'):
        (root / name).mkdir()
    (root / 'sdk/sdk.json').write_text(json.dumps({'recipe_id': 'e' * 64, 'target': {
        'system': system, 'processor': processor, 'triple': triple}}))
    return hashlib.sha256((root / 'sdk/sdk.json').read_bytes()).hexdigest()


class RichEntryTests(unittest.TestCase):
    def test_selectors_require_explicit_rich_maintenance_before_tools(self):
        for selector in ('--engine-document-profile', '--engine-native-document-profile'):
            for base in ([], ['--kernel-maintenance'], ['--kernel-maintenance', '--appended-profile', 'binary']):
                with self.subTest(selector=selector, base=base), patch.object(build, 'job_limits') as jobs, \
                        patch.object(build, 'host_programs') as programs, patch.object(build, 'run') as run, \
                        patch.object(build, 'sdk_identity') as sdk, patch.object(sys, 'stderr', new_callable=io.StringIO):
                    with self.assertRaises(SystemExit):
                        build.main(['build', '--core-provider', 'cpp', *base, selector, 'pixel'])
                    for sentinel in (jobs, programs, run, sdk):
                        sentinel.assert_not_called()

    def test_native_physical_is_not_a_supported_selection(self):
        with patch.object(build, 'execute') as execute, patch.object(sys, 'stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                build.main(['build', '--engine-native-document-profile', 'physical'])
            execute.assert_not_called()

    def test_contract_selections_are_mutually_exclusive(self):
        root = Path('/unused')
        combinations = [options(root) + ['--engine-physical-input'],
                        options(root) + ['--engine-native-document-profile', 'pixel'],
                        options(root, native=True) + ['--engine-physical-input']]
        for arguments in combinations:
            with self.subTest(arguments=arguments), patch.object(build, 'sdk_identity') as sdk, \
                    patch.object(build, 'run') as run, patch.object(sys, 'stderr', new_callable=io.StringIO) as errors:
                with self.assertRaises(SystemExit):
                    build.main(arguments)
                self.assertIn('only one', errors.getvalue())
                sdk.assert_not_called()
                run.assert_not_called()

    def test_browser_document_consumer_receives_selected_profile(self):
        import appended_engine_document_consumer as consumer
        for profile in ('web', 'both'):
            for document in ('pixel', 'physical'):
                with self.subTest(profile=profile, document=document), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    pin = inert_inputs(root)
                    inspection = Mock()
                    inspection.as_dict.return_value = {'group_files': {'synthetic': 'f' * 64}}
                    with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                            patch.object(build, 'sdk_identity', return_value=pin), \
                            patch.object(consumer, 'verify_kernel_consumer', return_value=inspection) as verify, \
                            patch.object(build, 'job_limits', side_effect=ReachedJobSelection), patch.object(build, 'run') as run:
                        with self.assertRaises(ReachedJobSelection):
                            build.main(options(root, profile=profile, document=document))
                        self.assertEqual(verify.call_args.kwargs['document_profile'], document)
                        self.assertEqual(verify.call_args.kwargs['paired_sdk'], pin)
                        self.assertEqual(verify.call_args.kwargs['kernel_target']['pointer_bits'], 32)
                        run.assert_not_called()

    def test_native_consumer_receives_exact_target_without_browser_sdk_argument(self):
        import appended_engine_native_consumer as consumer
        for profile in ('web', 'both'):
            for processor, triple in (('x86_64', 'x86_64-linux-gnu'), ('aarch64', 'aarch64-linux-gnu')):
                with self.subTest(profile=profile, processor=processor), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    pin = inert_inputs(root, system='Linux', processor=processor, triple=triple)
                    inspection = Mock()
                    inspection.as_dict.return_value = {'group_files': {'synthetic': 'f' * 64}}
                    with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                            patch.object(build, 'sdk_identity', return_value=pin), \
                            patch.object(consumer, 'verify_kernel_consumer', return_value=inspection) as verify, \
                            patch.object(build, 'job_limits', side_effect=ReachedJobSelection), patch.object(build, 'run') as run:
                        with self.assertRaises(ReachedJobSelection):
                            build.main(options(root, native=True, profile=profile))
                        self.assertEqual(verify.call_args.kwargs, {
                            'expected_recipe': 'a' * 64, 'expected_manifest': 'b' * 64,
                            'expected_proof': 'c' * 64, 'expected_runtime': 'd' * 64,
                            'kernel_target': {'system': 'Linux', 'processor': processor, 'triple': triple, 'pointer_bits': 64},
                            'document_profile': 'pixel'})
                        run.assert_not_called()

    def test_ineligible_groups_never_reach_programs_or_configuration(self):
        for native in (False, True):
            with self.subTest(native=native), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root, **({'system': 'Linux', 'processor': 'x86_64',
                    'triple': 'x86_64-linux-gnu'} if native else {}))
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), patch.object(build, 'job_limits') as jobs, \
                        patch.object(build, 'host_programs') as programs, patch.object(build, 'run') as run, \
                        patch.object(build.subprocess, 'check_output') as output:
                    with self.assertRaises(ValueError):
                        build.main(options(root, native=native))
                    for sentinel in (jobs, programs, run, output):
                        sentinel.assert_not_called()
                    self.assertFalse((root / 'build').exists())

    def test_native_rejects_browser_sdk_and_unadmitted_architectures(self):
        for system, processor, triple in (('Emscripten', 'wasm32', 'wasm32-emscripten'),
                ('Linux', 'riscv64', 'riscv64-linux-gnu'), ('Windows', 'aarch64', 'aarch64-windows')):
            with self.subTest(system=system, processor=processor), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root, system=system, processor=processor, triple=triple)
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), patch.object(build, 'engine_consumer_identity') as consumer, \
                        patch.object(build, 'job_limits') as jobs, patch.object(sys, 'stderr', new_callable=io.StringIO):
                    with self.assertRaises(SystemExit):
                        build.main(options(root, native=True))
                    consumer.assert_not_called()
                    jobs.assert_not_called()

    def test_native_selection_requires_sdk_and_native_terminal(self):
        arguments = options(Path('/unused'), native=True)
        variations = []
        for flag, value in (('--gui-backends', 'wasm'), ('--gui-backends', 'framebuffer')):
            modified = list(arguments)
            modified[modified.index(flag) + 1] = value
            variations.append(modified)
        modified = list(arguments)
        index = modified.index('--sdk')
        del modified[index:index + 2]
        variations.append(modified)
        for modified in variations:
            with self.subTest(arguments=modified), patch.object(build, 'sdk_identity') as sdk, \
                    patch.object(build, 'job_limits') as jobs, patch.object(sys, 'stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build.main(modified)
                sdk.assert_not_called()
                jobs.assert_not_called()

    def test_selection_is_part_of_wrapper_identity(self):
        import appended_engine_document_consumer as document_consumer
        import appended_engine_native_consumer as native_consumer
        inspection = Mock()
        inspection.as_dict.return_value = {'synthetic': 'identical'}
        args = argparse.Namespace(engine_group=Path('/unused'), engine_physical_input=False,
            engine_document_profile='pixel', engine_native_document_profile=None,
            **{'engine_' + name + '_sha256': 'a' * 64 for name in ('recipe', 'manifest', 'proof', 'runtime')})
        with patch.object(document_consumer, 'verify_kernel_consumer', return_value=inspection), \
                patch.object(native_consumer, 'verify_kernel_consumer', return_value=inspection):
            pixel = build.engine_consumer_identity(args, 'b' * 64, {'fixture': 'target'})
            args.engine_document_profile = 'physical'
            physical = build.engine_consumer_identity(args, 'b' * 64, {'fixture': 'target'})
            args.engine_document_profile = None
            args.engine_native_document_profile = 'pixel'
            native = build.engine_consumer_identity(args, 'b' * 64, {'fixture': 'target'})
        self.assertEqual(pixel['document_profile'], 'pixel')
        self.assertEqual(physical['document_profile'], 'physical')
        self.assertEqual(native['native_document_profile'], 'pixel')
        self.assertNotEqual(pixel, physical)
        self.assertNotEqual(pixel, native)

    def test_wrapper_forwards_explicit_selection_and_rechecks_before_build(self):
        import sdk_wasm
        import source_identity
        for native in (False, True):
            for profile in ('web', 'both'):
                with self.subTest(native=native, profile=profile), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    pin = inert_inputs(root, **({'system': 'Linux', 'processor': 'x86_64',
                        'triple': 'x86_64-linux-gnu'} if native else {}))
                    node = root / 'sdk/node/bin/node'
                    node.parent.mkdir(parents=True)
                    node.write_text('unexecuted runtime fixture')
                    identity = {'root': str(root / 'engine'),
                        'pins': {name: letter * 64 for name, letter in
                                 (('recipe', 'a'), ('manifest', 'b'), ('proof', 'c'), ('runtime', 'd'))},
                        'consumer': {'group_files': {'synthetic': 'f' * 64}},
                        'native_document_profile' if native else 'document_profile': 'pixel'}
                    with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                            patch.object(build, 'sdk_identity', return_value=pin), \
                            patch.object(build, 'engine_consumer_identity', return_value=identity), \
                            patch.object(build, 'host_programs', return_value={name: name for name in ('cmake', 'ctest', 'cpack', 'ninja')}), \
                            patch.object(sdk_wasm, 'environment', return_value={}), \
                            patch.object(source_identity, 'source_tree', return_value={}), \
                            patch.object(build, 'recheck_engine_input', side_effect=[None, None, ValueError('changed group')]), \
                            patch.object(build, 'run') as run:
                        with self.assertRaisesRegex(ValueError, 'changed group'):
                            build.main(options(root, native=native, profile=profile))
                        run.assert_called_once()
                        configure = run.call_args.args[0]
                        self.assertIn('-DFOUNDATION_APPENDED_PROFILE=' + profile, configure)
                        self.assertIn('-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=' + ('' if native else 'pixel'), configure)
                        self.assertIn('-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=' + ('pixel' if native else ''), configure)
                        self.assertIn('-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=OFF', configure)

    def cmake_source(self):
        source = (ROOT / 'CMakeLists.txt').read_text()
        options = source.split('# Appended profile options.\n', 1)[1].split('# End appended profile options.', 1)[0]
        admission = source.split('# Appended retained-input admission.\n', 1)[1].split('# End appended retained-input admission.', 1)[0]
        return options, admission

    def test_cmake_cached_booleans_do_not_admit_invalid_selections(self):
        options_source, admission = self.cmake_source()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.24)\nproject(Routing LANGUAGES NONE)\n' +
                options_source + admission + '\nfile(WRITE "${CMAKE_CURRENT_BINARY_DIR}/entered" "unexpected")\n')
            for index, flags in enumerate((
                    ['-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=physical'],
                    ['-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=pixel'],
                    ['-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=pixel'],
                    ['-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=pixel',
                     '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=pixel'])):
                tree = root / ('build' + str(index))
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *flags,
                    '-DFOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED=ON',
                    '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED=ON',
                    '-DFOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED=ON'], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((tree / 'entered').exists())
                self.assertFalse((tree / 'appended-engine-kernel-target.json').exists())

    def cmake_fixture(self, root, *, native):
        """Mock admission programs only; no generated fact is production evidence."""
        sdk = root / 'sdk'
        sdk.mkdir()
        (sdk / 'compiler').write_text('inert compiler path, never executed')
        (sdk / 'sysroot').mkdir()
        target = {'system': 'Linux' if native else 'Emscripten',
                  'processor': 'x86_64' if native else 'wasm32',
                  'triple': 'x86_64-linux-gnu' if native else 'wasm32-emscripten',
                  'cxx_compiler': 'compiler', 'sysroot': 'sysroot'}
        (sdk / 'sdk.json').write_text(json.dumps({'target': target}))
        digest = hashlib.sha256((sdk / 'sdk.json').read_bytes()).hexdigest()
        toolchain = root / 'cmake/toolchains/sdk.cmake'
        toolchain.parent.mkdir(parents=True)
        toolchain.write_text('# synthetic toolchain path, no tools executed\n')
        scripts = root / 'tools'
        scripts.mkdir()
        (scripts / 'sdk_verify.py').write_text('print(' + repr(digest) + ')\n')
        recorder = ('import json,pathlib,sys\n'
            'target=pathlib.Path(sys.argv[sys.argv.index("--kernel-target-json")+1])\n'
            'label=pathlib.Path(__file__).stem\n'
            '(target.parent/(label+".arguments")).write_text(json.dumps(sys.argv[1:]))\n'
            'print(json.dumps({"fixture":"synthetic routing only","adapter":label}))\n')
        for name in ('appended_engine_document_profile', 'appended_engine_native_profile',
                     'appended_engine_kernel_sdk'):
            (scripts / (name + '.py')).write_text(recorder)
        options_source, admission = self.cmake_source()
        (root / 'CMakeLists.txt').write_text(
            'cmake_minimum_required(VERSION 3.24)\nproject(Routing LANGUAGES NONE)\n'
            'set(Python3_EXECUTABLE "' + Path(sys.executable).as_posix() + '")\n'
            'set(CMAKE_SYSTEM_NAME ' + target['system'] + ')\n'
            'set(CMAKE_SYSTEM_PROCESSOR ' + target['processor'] + ')\n'
            'set(CMAKE_SIZEOF_VOID_P ' + ('8' if native else '4') + ')\n'
            'set(CMAKE_TOOLCHAIN_FILE "' + toolchain.as_posix() + '")\n'
            'set(CMAKE_CXX_COMPILER "' + (sdk / 'compiler').as_posix() + '")\n'
            'set(CMAKE_SYSROOT "' + (sdk / 'sysroot').as_posix() + '")\n'
            'set(FOUNDATION_BUILD_GUI ON)\n'
            'set(FOUNDATION_GUI_SOURCE "' + (root / 'gui').as_posix() + '")\n'
            'set(FOUNDATION_SDK_ROOT "' + sdk.as_posix() + '")\n' + options_source + admission +
            '\nfile(WRITE "${CMAKE_CURRENT_BINARY_DIR}/verified" '
            '"${FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED};${FOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED};${FOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED}")\n')
        return ['-DFOUNDATION_APPENDED_KERNEL_MAINTENANCE=ON',
                '-DFOUNDATION_APPENDED_ENGINE_GROUP=' + str(root / 'empty-ineligible-engine'),
                *['-DFOUNDATION_APPENDED_ENGINE_' + pin + '_SHA256=' + 'a' * 64
                  for pin in ('RECIPE', 'MANIFEST', 'PROOF', 'RUNTIME')]]

    def test_cmake_dispatches_exact_separate_generators_and_target_facts(self):
        for native in (False, True):
            with self.subTest(native=native), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                base = self.cmake_fixture(root, native=native)
                for profile in ('web', 'both'):
                    documents = ('pixel',) if native else ('pixel', 'physical')
                    for document in documents:
                        tree = root / (profile + '-' + document)
                        variable = 'NATIVE_DOCUMENT_PROFILE' if native else 'DOCUMENT_PROFILE'
                        result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                            '-DFOUNDATION_APPENDED_PROFILE=' + profile,
                            '-DFOUNDATION_APPENDED_ENGINE_' + variable + '=' + document],
                            capture_output=True, text=True, timeout=15)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertEqual((tree / 'verified').read_text(), 'TRUE;FALSE;TRUE' if native else 'TRUE;TRUE;FALSE')
                        name = 'appended_engine_native_profile' if native else 'appended_engine_document_profile'
                        arguments = json.loads((tree / (name + '.arguments')).read_text())
                        self.assertEqual(arguments[arguments.index('--document-profile') + 1], document)
                        self.assertEqual('--paired-sdk-sha256' in arguments, not native)
                        self.assertEqual('--build-dir' in arguments, native)
                        self.assertEqual('--build-root' in arguments, not native)
                        self.assertFalse((tree / ('appended_engine_document_profile' if native else 'appended_engine_native_profile')
                                          ).with_suffix('.arguments').exists())
                        target = json.loads((tree / 'appended-engine-kernel-target.json').read_text())
                        self.assertEqual(set(target), {'system', 'processor', 'triple', 'pointer_bits'})
                        self.assertEqual(target['pointer_bits'], 64 if native else 32)
                        self.assertEqual((tree / 'appended_engine_kernel_sdk.arguments').exists(), native)

    def test_cmake_document_selection_change_requires_fresh_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = self.cmake_fixture(root, native=False)
            tree = root / 'build'
            for document, success in (('pixel', True), ('pixel', True), ('physical', False)):
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                    '-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=' + document],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                if not success:
                    self.assertIn('Retained engine identity changed', result.stdout + result.stderr)

    def test_cmake_native_target_and_pointer_mismatches_stop_before_generation(self):
        for replacement in ('set(CMAKE_SYSTEM_PROCESSOR aarch64)', 'set(CMAKE_SYSTEM_PROCESSOR riscv64)',
                            'set(CMAKE_SIZEOF_VOID_P 4)'):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                base = self.cmake_fixture(root, native=True)
                project = root / 'CMakeLists.txt'
                source = project.read_text()
                original = 'set(CMAKE_SIZEOF_VOID_P 8)' if 'VOID_P' in replacement else 'set(CMAKE_SYSTEM_PROCESSOR x86_64)'
                self.assertIn(original, source)
                project.write_text(source.replace(original, replacement))
                tree = root / 'build'
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                    '-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=pixel'],
                    capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((tree / 'appended-engine-kernel-target.json').exists())
                self.assertFalse((tree / 'appended_engine_native_profile.arguments').exists())
                self.assertFalse((tree / 'verified').exists())

    def test_direct_cmake_actual_native_generator_rejects_empty_ineligible_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = self.cmake_fixture(root, native=True)
            (root / 'empty-ineligible-engine').mkdir()
            (root / 'tools/appended_engine_native_profile.py').write_text(
                'import runpy,sys\nsys.path.insert(0,' + repr(str(ROOT / 'tools')) + ')\n'
                'runpy.run_path(' + repr(str(ROOT / 'tools/appended_engine_native_profile.py')) + ',run_name="__main__")\n')
            tree = root / 'build'
            result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                '-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=pixel',
                '-DFOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED=ON',
                '-DFOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED=ON'],
                capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('appended engine native profile:', result.stdout + result.stderr)
            self.assertFalse((tree / 'verified').exists())
            self.assertFalse((tree / 'appended-engine-native-profile').exists())

class EditorRichEntryTests(unittest.TestCase):
    """Editor2035 projections only; synthetic admission never establishes eligibility."""

    cmake_source = RichEntryTests.cmake_source

    def cmake_editor_fixture(self, root, *, identical_metadata=False):
        # Reuse the old fixture without changing its three-boolean output or
        # any legacy test body. Editor state is recorded in a separate file.
        base = RichEntryTests.cmake_fixture(self, root, native=False)
        recorder = ('import json,pathlib,sys\n'
            'target=pathlib.Path(sys.argv[sys.argv.index("--kernel-target-json")+1])\n'
            'label=pathlib.Path(__file__).stem\n'
            '(target.parent/(label+".arguments")).write_text(json.dumps(sys.argv[1:]))\n'
            'with (target.parent/(label+".invocations")).open("a") as stream: stream.write("called\\n")\n' +
            ('print(json.dumps({"fixture":"identical synthetic admission"}))\n' if identical_metadata else
             'print(json.dumps({"fixture":"synthetic editor routing only","adapter":label}))\n'))
        (root / 'tools/appended_engine_editor_profile.py').write_text(recorder)
        if identical_metadata:
            (root / 'tools/appended_engine_document_profile.py').write_text(recorder)
        project = root / 'CMakeLists.txt'
        project.write_text(project.read_text() +
            '\nfile(WRITE "${CMAKE_CURRENT_BINARY_DIR}/editor-verified" '
            '"${FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED};'
            '${FOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED};'
            '${FOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED};'
            '${FOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED};'
            '${FOUNDATION_APPENDED_ENGINE_EDITOR_DIRECTORY}")\n')
        return base

    def editor_namespace(self):
        return argparse.Namespace(engine_group=Path('/unused'), engine_physical_input=False,
            engine_document_profile='editor', engine_native_document_profile=None,
            **{'engine_' + name + '_sha256': letter * 64 for name, letter in
               (('recipe', 'a'), ('manifest', 'b'), ('proof', 'c'), ('runtime', 'd'))})

    def test_editor_requires_explicit_rich_maintenance_before_discovery(self):
        for base in ([], ['--kernel-maintenance'], ['--appended-profile', 'web'],
                     ['--kernel-maintenance', '--appended-profile', 'binary']):
            with self.subTest(base=base), patch.object(build, 'job_limits') as jobs, \
                    patch.object(build, 'host_programs') as programs, patch.object(build, 'run') as run, \
                    patch.object(build, 'sdk_identity') as sdk, patch.object(sys, 'stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build.main(['build', '--core-provider', 'cpp', *base, '--engine-document-profile', 'editor'])
                for sentinel in (jobs, programs, run, sdk):
                    sentinel.assert_not_called()

    def test_editor_rejects_mixed_profiles_missing_pins_and_nonbrowser_backends_early(self):
        original = options(Path('/unused'), document='editor')
        variations = [original + ['--engine-physical-input'],
                      original + ['--engine-native-document-profile', 'pixel']]
        for name in ('recipe', 'manifest', 'proof', 'runtime'):
            flag = '--engine-' + name + '-sha256'
            for value in (None, 'A' * 64, '0' * 63):
                arguments = list(original)
                index = arguments.index(flag)
                if value is None:
                    del arguments[index:index + 2]
                else:
                    arguments[index + 1] = value
                variations.append(arguments)
        for backend in ('terminal', 'hosted-web', 'wasm,terminal'):
            arguments = list(original)
            arguments[arguments.index('--gui-backends') + 1] = backend
            variations.append(arguments)
        for arguments in variations:
            with self.subTest(arguments=arguments), patch.object(build, 'sdk_identity') as sdk, \
                    patch.object(build, 'job_limits') as jobs, patch.object(build, 'host_programs') as programs, \
                    patch.object(build, 'run') as run, patch.object(sys, 'stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build.main(arguments)
                for sentinel in (sdk, jobs, programs, run):
                    sentinel.assert_not_called()
        with patch.object(build, 'execute') as execute, patch.object(sys, 'stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                build.main(options(Path('/unused'), native=True, document='editor'))
            execute.assert_not_called()

    def test_editor_consumer_receives_exact_four_pins_sdk_target_and_explicit_selector(self):
        import appended_engine_editor_consumer as consumer
        import appended_engine_document_consumer as old_document
        import appended_engine_native_consumer as native
        for profile in ('web', 'both'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root)
                inspection = Mock()
                inspection.as_dict.return_value = {'group_files': {'synthetic': 'f' * 64}}
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), \
                        patch.object(consumer, 'verify_kernel_consumer', return_value=inspection) as verify, \
                        patch.object(old_document, 'verify_kernel_consumer') as old_verify, \
                        patch.object(native, 'verify_kernel_consumer') as native_verify, \
                        patch.object(build, 'job_limits', side_effect=ReachedJobSelection), patch.object(build, 'run') as run:
                    with self.assertRaises(ReachedJobSelection):
                        build.main(options(root, profile=profile, document='editor'))
                    verify.assert_called_once_with(root / 'engine', expected_recipe='a' * 64,
                        expected_manifest='b' * 64, expected_proof='c' * 64, expected_runtime='d' * 64,
                        kernel_target={'system': 'Emscripten', 'processor': 'wasm32',
                                       'triple': 'wasm32-emscripten', 'pointer_bits': 32},
                        paired_sdk=pin, editor_profile='editor')
                    old_verify.assert_not_called()
                    native_verify.assert_not_called()
                    run.assert_not_called()

    def test_editor_actual_ineligible_group_never_reaches_programs_or_configuration(self):
        for profile in ('web', 'both'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root)
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), patch.object(build, 'job_limits') as jobs, \
                        patch.object(build, 'host_programs') as programs, patch.object(build, 'run') as run, \
                        patch.object(build.subprocess, 'check_output') as output:
                    with self.assertRaises(ValueError):
                        build.main(options(root, profile=profile, document='editor'))
                    for sentinel in (jobs, programs, run, output):
                        sentinel.assert_not_called()
                    self.assertFalse((root / 'build').exists())

    def test_editor_requires_exact_browser_sdk_target_before_consumer_or_discovery(self):
        for system, processor, triple in (('Linux', 'x86_64', 'x86_64-linux-gnu'),
                ('Emscripten', 'wasm64', 'wasm64-emscripten'), ('Emscripten', 'wasm32', 'different-triple')):
            with self.subTest(system=system, processor=processor), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root, system=system, processor=processor, triple=triple)
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), patch.object(build, 'engine_consumer_identity') as consumer, \
                        patch.object(build, 'job_limits') as jobs, patch.object(build, 'host_programs') as programs, \
                        patch.object(build, 'run') as run, patch.object(sys, 'stderr', new_callable=io.StringIO):
                    with self.assertRaises(SystemExit):
                        build.main(options(root, document='editor'))
                    for sentinel in (consumer, jobs, programs, run):
                        sentinel.assert_not_called()

    def test_editor_selector_changes_wrapper_identity_even_with_identical_consumer_metadata(self):
        import appended_engine_editor_consumer as editor
        import appended_engine_document_consumer as document
        inspection = Mock()
        inspection.as_dict.return_value = {'synthetic': 'identical'}
        args = self.editor_namespace()
        target = {'system': 'Emscripten', 'processor': 'wasm32', 'triple': 'wasm32-emscripten', 'pointer_bits': 32}
        with patch.object(editor, 'verify_kernel_consumer', return_value=inspection) as editor_verify, \
                patch.object(document, 'verify_kernel_consumer', return_value=inspection) as document_verify:
            selected = build.engine_consumer_identity(args, 'e' * 64, target)
            args.engine_document_profile = 'physical'
            physical = build.engine_consumer_identity(args, 'e' * 64, target)
            args.engine_document_profile = 'editor'
            again = build.engine_consumer_identity(args, 'e' * 64, target)
        self.assertEqual(selected['document_profile'], 'editor')
        self.assertEqual(selected['paired_sdk_sha256'], 'e' * 64)
        self.assertEqual(selected['kernel_target'], target)
        self.assertNotEqual(selected, physical)
        self.assertEqual(selected, again)
        self.assertEqual(editor_verify.call_count, 2, 'equal identities still require fresh consumer inspection')
        document_verify.assert_called_once()

    def test_cached_wrapper_editor_admission_never_skips_fresh_consumer(self):
        import appended_engine_editor_consumer as consumer
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pin = inert_inputs(root)
            tree = root / 'existing-build'
            tree.mkdir()
            (tree / 'wrapper-identity.json').write_text(json.dumps({'appended_profile': 'web', 'appended_engine': {
                'document_profile': 'editor', 'consumer_verified': True, 'editor_consumer_verified': True}}))
            with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                    patch.object(build, 'sdk_identity', return_value=pin), \
                    patch.object(consumer, 'verify_kernel_consumer', side_effect=ValueError('fresh editor rejection')) as verify, \
                    patch.object(build, 'job_limits') as jobs, patch.object(build, 'host_programs') as programs, patch.object(build, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'fresh editor rejection'):
                    build.main(options(root, document='editor') + ['--build-dir', str(tree)])
                verify.assert_called_once()
                for sentinel in (jobs, programs, run):
                    sentinel.assert_not_called()

    def test_editor_wrapper_forwards_unified_selector_and_rechecks_before_any_compile(self):
        import sdk_wasm
        import source_identity
        for profile in ('web', 'both'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root)
                node = root / 'sdk/node/bin/node'
                node.parent.mkdir(parents=True)
                node.write_text('inert never executed runtime path')
                identity = {'root': str(root / 'engine'),
                    'pins': {name: letter * 64 for name, letter in
                             (('recipe', 'a'), ('manifest', 'b'), ('proof', 'c'), ('runtime', 'd'))},
                    'consumer': {'group_files': {'synthetic': 'f' * 64}}, 'document_profile': 'editor'}
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), \
                        patch.object(build, 'engine_consumer_identity', return_value=identity), \
                        patch.object(build, 'host_programs', return_value={name: name for name in ('cmake', 'ctest', 'cpack', 'ninja')}), \
                        patch.object(sdk_wasm, 'environment', return_value={}), \
                        patch.object(source_identity, 'source_tree', return_value={}), \
                        patch.object(build, 'recheck_engine_input', side_effect=[None, None, ValueError('editor bytes changed')]) as recheck, \
                        patch.object(build, 'run') as run:
                    with self.assertRaisesRegex(ValueError, 'editor bytes changed'):
                        build.main(options(root, profile=profile, document='editor'))
                    run.assert_called_once()
                    self.assertEqual(recheck.call_count, 3)
                    configure = run.call_args.args[0]
                    self.assertIn('-DFOUNDATION_APPENDED_PROFILE=' + profile, configure)
                    self.assertIn('-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=editor', configure)
                    self.assertIn('-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=', configure)
                    self.assertIn('-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=OFF', configure)
                    for name, letter in (('RECIPE', 'a'), ('MANIFEST', 'b'), ('PROOF', 'c'), ('RUNTIME', 'd')):
                        self.assertIn('-DFOUNDATION_APPENDED_ENGINE_' + name + '_SHA256=' + letter * 64, configure)

    def test_cmake_editor_dispatches_exact_generator_target_four_booleans_and_private_directory(self):
        for profile in ('web', 'both'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                base = self.cmake_editor_fixture(root)
                sdk_pin = hashlib.sha256((root / 'sdk/sdk.json').read_bytes()).hexdigest()
                tree = root / 'build'
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                    '-DFOUNDATION_APPENDED_PROFILE=' + profile, '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=editor',
                    '-DFOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED=ON',
                    '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED=ON',
                    '-DFOUNDATION_APPENDED_ENGINE_EDITOR_DIRECTORY=' + str(root / 'forged-directory')],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((tree / 'verified').read_text(), 'TRUE;FALSE;FALSE')
                self.assertEqual((tree / 'editor-verified').read_text(),
                    'TRUE;FALSE;FALSE;TRUE;' + (tree / 'appended-engine-editor-profile').as_posix())
                arguments = json.loads((tree / 'appended_engine_editor_profile.arguments').read_text())
                self.assertEqual(arguments, ['--build-root', str(tree), '--editor-profile', 'editor',
                    '--group', str(root / 'empty-ineligible-engine'),
                    *[value for name in ('recipe', 'manifest', 'proof', 'runtime')
                      for value in ('--' + name + '-sha256', 'a' * 64)],
                    '--kernel-target-json', str(tree / 'appended-engine-kernel-target.json'), '--paired-sdk-sha256', sdk_pin])
                target = json.loads((tree / 'appended-engine-kernel-target.json').read_text())
                self.assertEqual(target, {'system': 'Emscripten', 'processor': 'wasm32',
                                          'triple': 'wasm32-emscripten', 'pointer_bits': 32})
                for name in ('appended_engine_document_profile', 'appended_engine_native_profile', 'appended_engine_kernel_sdk'):
                    self.assertFalse((tree / (name + '.arguments')).exists())

    def test_cmake_editor_cache_flags_neither_select_nor_admit_editor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.cmake_editor_fixture(root)
            tree = root / 'build'
            result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree),
                *['-DFOUNDATION_APPENDED_ENGINE_' + name + '_CONSUMER_VERIFIED=ON'
                  for name in ('DOCUMENT', 'NATIVE', 'EDITOR')],
                '-DFOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED=ON',
                '-DFOUNDATION_APPENDED_ENGINE_EDITOR_DIRECTORY=' + str(root / 'forged-directory')],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((tree / 'editor-verified').read_text(), 'FALSE;FALSE;FALSE;FALSE;')
            self.assertFalse((tree / 'appended-engine-kernel-target.json').exists())
            self.assertFalse((tree / 'appended_engine_editor_profile.arguments').exists())

    def test_cmake_editor_invalid_or_unmaintained_selection_fails_before_target_or_generator(self):
        variations = [[], ['-DFOUNDATION_APPENDED_PROFILE=binary'],
            ['-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_KERNEL_MAINTENANCE=OFF'],
            ['-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=ON'],
            ['-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=pixel'],
            ['-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=editor2035']]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = self.cmake_editor_fixture(root)
            for index, flags in enumerate(variations):
                tree = root / ('build-' + str(index))
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                    '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=editor', *flags,
                    '-DFOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED=ON',
                    '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED=ON',
                    '-DFOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED=ON',
                    '-DFOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED=ON'],
                    capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((tree / 'appended-engine-kernel-target.json').exists())
                self.assertFalse((tree / 'appended_engine_editor_profile.arguments').exists())
                self.assertFalse((tree / 'editor-verified').exists())

    def test_cmake_editor_sdk_target_and_pointer_mismatch_stop_before_generation(self):
        for original, replacement in (('set(CMAKE_SYSTEM_PROCESSOR wasm32)', 'set(CMAKE_SYSTEM_PROCESSOR x86_64)'),
                ('set(CMAKE_SIZEOF_VOID_P 4)', 'set(CMAKE_SIZEOF_VOID_P 8)'),
                ('set(CMAKE_SYSTEM_NAME Emscripten)', 'set(CMAKE_SYSTEM_NAME Linux)')):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                base = self.cmake_editor_fixture(root)
                project = root / 'CMakeLists.txt'
                self.assertIn(original, project.read_text())
                project.write_text(project.read_text().replace(original, replacement))
                tree = root / 'build'
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                    '-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=editor'],
                    capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((tree / 'appended-engine-kernel-target.json').exists())
                self.assertFalse((tree / 'appended_engine_editor_profile.arguments').exists())
                self.assertFalse((tree / 'editor-verified').exists())

    def test_cmake_editor_same_selection_reverifies_and_failing_generator_cannot_use_cached_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = self.cmake_editor_fixture(root)
            tree = root / 'build'
            command = ['cmake', '-S', str(root), '-B', str(tree), *base,
                '-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=editor',
                '-DFOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED=ON',
                '-DFOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED=ON']
            for attempt in (1, 2):
                result = subprocess.run(command, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((tree / 'appended_engine_editor_profile.invocations').read_text().splitlines(), ['called'] * attempt)
            (root / 'tools/appended_engine_editor_profile.py').write_text('raise SystemExit("fresh editor generator rejection")\n')
            for name in ('verified', 'editor-verified'):
                (tree / name).unlink()
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('fresh editor generator rejection', result.stdout + result.stderr)
            self.assertFalse((tree / 'editor-verified').exists())
            self.assertFalse((tree / 'verified').exists())

    def test_cmake_editor_selection_change_requires_fresh_tree_even_with_identical_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = self.cmake_editor_fixture(root, identical_metadata=True)
            tree = root / 'build'
            for document, success in (('pixel', True), ('editor', False)):
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                    '-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=' + document],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                if not success:
                    self.assertIn('Retained engine identity changed', result.stdout + result.stderr)
            self.assertTrue((tree / 'appended_engine_editor_profile.arguments').exists(),
                            'fresh admission precedes identity comparison even for changed selection')

    def test_direct_cmake_actual_editor_generator_rejects_ineligible_group_despite_cached_booleans(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = self.cmake_editor_fixture(root)
            (root / 'empty-ineligible-engine').mkdir()
            (root / 'tools/appended_engine_editor_profile.py').write_text(
                'import runpy,sys\nsys.path.insert(0,' + repr(str(ROOT / 'tools')) + ')\n'
                'runpy.run_path(' + repr(str(ROOT / 'tools/appended_engine_editor_profile.py')) + ',run_name="__main__")\n')
            tree = root / 'build'
            result = subprocess.run(['cmake', '-S', str(root), '-B', str(tree), *base,
                '-DFOUNDATION_APPENDED_PROFILE=web', '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=editor',
                '-DFOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED=ON',
                '-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED=ON',
                '-DFOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED=ON'],
                capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('appended engine editor profile:', result.stdout + result.stderr)
            self.assertFalse((tree / 'editor-verified').exists())
            self.assertFalse((tree / 'verified').exists())
            self.assertFalse((tree / 'appended-engine-editor-profile').exists())


class NativeActionsEntryTests(unittest.TestCase):
    """Native4083 entry routing only; inert inputs never establish eligibility."""

    def actions_options(self, root, *, profile='web', backend='terminal'):
        arguments = options(root, native=True, profile=profile)
        arguments[arguments.index('--engine-native-document-profile')] = '--engine-native-actions-profile'
        arguments[arguments.index('--engine-native-actions-profile') + 1] = 'document-actions-v1'
        arguments[arguments.index('--gui-backends') + 1] = backend
        return arguments

    def test_actions_require_explicit_maintenance_exclusive_contracts_and_all_pins_early(self):
        original = self.actions_options(Path('/unused'))
        variations = []
        for flag in ('--kernel-maintenance', '--appended-profile'):
            changed = list(original)
            index = changed.index(flag)
            del changed[index:index + (2 if flag == '--appended-profile' else 1)]
            variations.append(changed)
        changed = list(original)
        changed[changed.index('--appended-profile') + 1] = 'binary'
        variations.append(changed)
        for extra in (['--engine-native-document-profile', 'pixel'],
                      ['--engine-document-profile', 'pixel'],
                      ['--engine-document-profile', 'physical'],
                      ['--engine-document-profile', 'editor'], ['--engine-physical-input']):
            variations.append(original + extra)
        for name in ('recipe', 'manifest', 'proof', 'runtime'):
            flag = '--engine-' + name + '-sha256'
            for value in (None, 'A' * 64, '0' * 63):
                changed = list(original)
                index = changed.index(flag)
                if value is None:
                    del changed[index:index + 2]
                else:
                    changed[index + 1] = value
                variations.append(changed)
        changed = list(original)
        changed[changed.index('--engine-native-actions-profile') + 1] = 'pixel'
        variations.append(changed)
        for arguments in variations:
            with self.subTest(arguments=arguments), patch.object(build, 'sdk_identity') as sdk, \
                    patch.object(build, 'engine_consumer_identity') as consumer, \
                    patch.object(build, 'job_limits') as jobs, patch.object(build, 'host_programs') as programs, \
                    patch.object(build, 'run') as run, patch.object(sys, 'stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build.main(arguments)
                for sentinel in (sdk, consumer, jobs, programs, run):
                    sentinel.assert_not_called()

    def test_actions_native_backend_matrix_calls_only_new_api_with_exact_pins_and_target(self):
        import appended_engine_native_consumer as consumer
        import appended_engine_document_consumer as document
        for profile in ('web', 'both'):
            for backend in ('terminal', 'sdl', 'fltk', 'rev', 'framebuffer'):
                for suffix in ('', ',hosted-web'):
                    with self.subTest(profile=profile, backend=backend + suffix), tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary)
                        pin = inert_inputs(root, system='Linux', processor='x86_64', triple='x86_64-linux-gnu')
                        inspection = Mock()
                        inspection.as_dict.return_value = {'group_files': {'synthetic': 'f' * 64}}
                        with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                                patch.object(build, 'sdk_identity', return_value=pin), \
                                patch.object(consumer, 'verify_actions_kernel_consumer', return_value=inspection) as verify, \
                                patch.object(consumer, 'verify_kernel_consumer') as pixel, \
                                patch.object(document, 'verify_kernel_consumer') as browser, \
                                patch.object(build, 'job_limits', side_effect=ReachedJobSelection), \
                                patch.object(build, 'host_programs') as programs, patch.object(build, 'run') as run:
                            with self.assertRaises(ReachedJobSelection):
                                build.main(self.actions_options(root, profile=profile, backend=backend + suffix))
                            verify.assert_called_once_with(root / 'engine', expected_recipe='a' * 64,
                                expected_manifest='b' * 64, expected_proof='c' * 64, expected_runtime='d' * 64,
                                kernel_target={'system': 'Linux', 'processor': 'x86_64',
                                    'triple': 'x86_64-linux-gnu', 'pointer_bits': 64},
                                actions_profile='document-actions-v1')
                            pixel.assert_not_called()
                            browser.assert_not_called()
                            programs.assert_not_called()
                            run.assert_not_called()

    def test_actions_reject_incompatible_backends_and_native_input_routes_before_discovery(self):
        original = self.actions_options(Path('/unused'))
        variations = []
        for backend in ('wasm', 'hosted-web', 'wasm,terminal'):
            changed = list(original)
            changed[changed.index('--gui-backends') + 1] = backend
            variations.append(changed)
        variations.append(original + ['--host-tests'])
        for flag in ('--sdk', '--gui-source'):
            changed = list(original)
            index = changed.index(flag)
            del changed[index:index + 2]
            variations.append(changed)
        variations.extend((original + ['--windows-dependencies', '/unused/windows'],
                           original + ['--dependency-prefix', '/unused/prefix'],
                           original + ['--wasm-package', '/unused/wasm', '--wasm-package-sha256', 'a' * 64]))
        for arguments in variations:
            with self.subTest(arguments=arguments), patch.object(build, 'sdk_identity') as sdk, \
                    patch.object(build, 'engine_consumer_identity') as consumer, \
                    patch.object(build, 'job_limits') as jobs, patch.object(build, 'host_programs') as programs, \
                    patch.object(build, 'run') as run, patch.object(sys, 'stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build.main(arguments)
                for sentinel in (sdk, consumer, jobs, programs, run):
                    sentinel.assert_not_called()

    def test_actions_native_targets_and_windows_export_route_reach_new_consumer_exactly(self):
        import appended_engine_native_consumer as consumer
        for system, processor, triple in (('Linux', 'x86_64', 'x86_64-linux-gnu'),
                ('Linux', 'aarch64', 'aarch64-linux-gnu'), ('Windows', 'x86_64', 'x86_64-windows')):
            with self.subTest(system=system, processor=processor), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root, system=system, processor=processor, triple=triple)
                arguments = self.actions_options(root)
                platform_os = Mock(wraps=build.os)
                if system == 'Windows':
                    arguments[arguments.index('--sdk')] = '--windows-dependencies'
                    arguments.append('--portable')
                    platform_os.name = 'nt'
                else:
                    platform_os.name = build.os.name
                inspection = Mock()
                inspection.as_dict.return_value = {'group_files': {'synthetic': 'f' * 64}}
                with patch.object(build, 'ROOT', root), patch.object(build, 'os', platform_os), \
                        patch.object(build, 'require_clean'), patch.object(build, 'sdk_identity', return_value=pin), \
                        patch.object(consumer, 'verify_actions_kernel_consumer', return_value=inspection) as verify, \
                        patch.object(build, 'job_limits', side_effect=ReachedJobSelection), \
                        patch.object(build, 'host_programs') as programs, patch.object(build, 'run') as run:
                    with self.assertRaises(ReachedJobSelection):
                        build.main(arguments)
                    verify.assert_called_once_with(root / 'engine', expected_recipe='a' * 64,
                        expected_manifest='b' * 64, expected_proof='c' * 64, expected_runtime='d' * 64,
                        kernel_target={'system': system, 'processor': processor, 'triple': triple, 'pointer_bits': 64},
                        actions_profile='document-actions-v1')
                    programs.assert_not_called()
                    run.assert_not_called()

    def test_actions_wrong_sdk_targets_fail_before_consumer_or_programs(self):
        for system, processor, triple in (('Emscripten', 'wasm32', 'wasm32-emscripten'),
                ('Linux', 'riscv64', 'riscv64-linux-gnu'), ('Windows', 'aarch64', 'aarch64-windows'),
                ('Windows', 'x86_64', 'x86_64-windows')):
            with self.subTest(system=system, processor=processor), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root, system=system, processor=processor, triple=triple)
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), \
                        patch.object(build, 'engine_consumer_identity') as consumer, \
                        patch.object(build, 'job_limits') as jobs, patch.object(build, 'host_programs') as programs, \
                        patch.object(build, 'run') as run, patch.object(sys, 'stderr', new_callable=io.StringIO):
                    with self.assertRaises(SystemExit):
                        build.main(self.actions_options(root))
                    for sentinel in (consumer, jobs, programs, run):
                        sentinel.assert_not_called()

    def test_actions_actual_empty_group_fails_before_any_program_or_configuration(self):
        for profile in ('web', 'both'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root, system='Linux', processor='x86_64', triple='x86_64-linux-gnu')
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), patch.object(build, 'job_limits') as jobs, \
                        patch.object(build, 'host_programs') as programs, patch.object(build, 'run') as run, \
                        patch.object(build.subprocess, 'check_output') as output:
                    with self.assertRaises(ValueError):
                        build.main(self.actions_options(root, profile=profile))
                    for sentinel in (jobs, programs, run, output):
                        sentinel.assert_not_called()
                    self.assertFalse((root / 'build').exists())

    def test_actions_identity_is_distinct_with_equal_metadata_and_legacy_api_is_unchanged(self):
        import appended_engine_native_consumer as consumer
        inspection = Mock()
        inspection.as_dict.return_value = {'synthetic': 'identical'}
        args = argparse.Namespace(engine_group=Path('/unused'), engine_physical_input=False,
            engine_document_profile=None, engine_native_document_profile='pixel', engine_native_actions_profile=None,
            **{'engine_' + name + '_sha256': letter * 64 for name, letter in
                (('recipe', 'a'), ('manifest', 'b'), ('proof', 'c'), ('runtime', 'd'))})
        target = {'system': 'Linux', 'processor': 'x86_64', 'triple': 'x86_64-linux-gnu', 'pointer_bits': 64}
        with patch.object(consumer, 'verify_kernel_consumer', return_value=inspection) as pixel, \
                patch.object(consumer, 'verify_actions_kernel_consumer', return_value=inspection) as actions:
            old = build.engine_consumer_identity(args, 'e' * 64, target)
            args.engine_native_document_profile = None
            args.engine_native_actions_profile = 'document-actions-v1'
            selected = build.engine_consumer_identity(args, 'e' * 64, target)
            again = build.engine_consumer_identity(args, 'e' * 64, target)
        self.assertEqual(old['native_document_profile'], 'pixel')
        self.assertNotIn('native_actions_profile', old)
        self.assertEqual(selected['native_actions_profile'], 'document-actions-v1')
        self.assertNotIn('native_document_profile', selected)
        self.assertNotEqual(old, selected)
        self.assertEqual(selected, again)
        self.assertEqual(pixel.call_count, 1)
        self.assertEqual(actions.call_count, 2, 'equal metadata still requires fresh actions verification')
        self.assertEqual(pixel.call_args.kwargs['document_profile'], 'pixel')
        self.assertEqual(actions.call_args.kwargs['actions_profile'], 'document-actions-v1')
        self.assertNotIn('paired_sdk', actions.call_args.kwargs)

    def test_actions_cached_admission_does_not_skip_fresh_new_consumer(self):
        import appended_engine_native_consumer as consumer
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pin = inert_inputs(root, system='Linux', processor='x86_64', triple='x86_64-linux-gnu')
            tree = root / 'existing-build'
            tree.mkdir()
            (tree / 'wrapper-identity.json').write_text(json.dumps({'appended_profile': 'web', 'appended_engine': {
                'native_actions_profile': 'document-actions-v1', 'consumer_verified': True}}))
            with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                    patch.object(build, 'sdk_identity', return_value=pin), \
                    patch.object(consumer, 'verify_actions_kernel_consumer', side_effect=ValueError('fresh actions rejection')) as verify, \
                    patch.object(build, 'job_limits') as jobs, patch.object(build, 'host_programs') as programs, \
                    patch.object(build, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'fresh actions rejection'):
                    build.main(self.actions_options(root) + ['--build-dir', str(tree)])
                verify.assert_called_once()
                for sentinel in (jobs, programs, run):
                    sentinel.assert_not_called()

    def test_actions_wrapper_forwards_only_new_selector_and_rechecks_before_compile(self):
        import source_identity
        for profile in ('web', 'both'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                pin = inert_inputs(root, system='Linux', processor='x86_64', triple='x86_64-linux-gnu')
                identity = {'root': str(root / 'engine'),
                    'pins': {name: letter * 64 for name, letter in
                        (('recipe', 'a'), ('manifest', 'b'), ('proof', 'c'), ('runtime', 'd'))},
                    'consumer': {'group_files': {'synthetic': 'f' * 64}}, 'native_actions_profile': 'document-actions-v1'}
                with patch.object(build, 'ROOT', root), patch.object(build, 'require_clean'), \
                        patch.object(build, 'sdk_identity', return_value=pin), \
                        patch.object(build, 'engine_consumer_identity', return_value=identity), \
                        patch.object(build, 'host_programs', return_value={name: name for name in ('cmake', 'ctest', 'cpack', 'ninja')}), \
                        patch.object(source_identity, 'source_tree', return_value={}), \
                        patch.object(build, 'recheck_engine_input', side_effect=[None, None, ValueError('actions group changed')]) as recheck, \
                        patch.object(build, 'run') as run:
                    with self.assertRaisesRegex(ValueError, 'actions group changed'):
                        build.main(self.actions_options(root, profile=profile))
                    self.assertEqual(recheck.call_count, 3)
                    run.assert_called_once()
                    configure = run.call_args.args[0]
                    self.assertIn('-DFOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE=document-actions-v1', configure)
                    self.assertIn('-DFOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE=', configure)
                    self.assertIn('-DFOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=', configure)
                    self.assertIn('-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=OFF', configure)
                    self.assertIn('-DFOUNDATION_APPENDED_ENGINE_NATIVE_DEPENDENCY_GROUP=', configure)
                    for name, letter in (('RECIPE', 'a'), ('MANIFEST', 'b'), ('PROOF', 'c'), ('RUNTIME', 'd')):
                        self.assertIn('-DFOUNDATION_APPENDED_ENGINE_' + name + '_SHA256=' + letter * 64, configure)

    def test_actions_addition_does_not_admit_legacy_pixel_without_terminal(self):
        for backend in ('sdl', 'fltk', 'rev', 'framebuffer', 'sdl,hosted-web'):
            arguments = options(Path('/unused'), native=True)
            arguments[arguments.index('--gui-backends') + 1] = backend
            with self.subTest(backend=backend), patch.object(build, 'sdk_identity') as sdk, \
                    patch.object(build, 'job_limits') as jobs, patch.object(build, 'run') as run, \
                    patch.object(sys, 'stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build.main(arguments)
                for sentinel in (sdk, jobs, run):
                    sentinel.assert_not_called()


if __name__ == '__main__':
    unittest.main()
