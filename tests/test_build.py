import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import windows_toolchain as toolchain
import unittest

spec = importlib.util.spec_from_file_location("builder", Path(__file__).resolve().parents[1] / "tools/build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildTests(unittest.TestCase):
    def test_windows_linker_file_versions_use_same_order(self):
        from unittest.mock import patch
        for actual, minimum, success in (
                ('14.44.35207', '14.44.35207.0', True),
                ('14.44.35207.0', '14.44.35207', True),
                ('14.44.35207', '14.44.35207.1', False),
                ('14.44.35206.9', '14.44.35207.0', False),
                ('14.45.1', '14.44.35207.0', True)):
            with self.subTest(actual=actual, minimum=minimum), patch.object(
                    toolchain, 'inspect_selected_linker', return_value={'version':actual}):
                if success:
                    builder.verify_windows_linker(minimum)
                else:
                    with self.assertRaises(ValueError): builder.verify_windows_linker(minimum)
        with patch.object(toolchain, 'inspect_selected_linker', side_effect=ValueError('unrecognized tool')):
            with self.assertRaises(ValueError): builder.verify_windows_linker('14.44.35207.0')

    def test_native_windows_selected_linker_file_identity(self):
        import os
        value = toolchain.inspect_selected_linker()
        self.assertEqual(value['architecture'], 'x86_64')
        self.assertTrue(Path(value['path']).samefile(Path(os.environ['VCToolsInstallDir']) / 'bin/Hostx64/x64/link.exe'))
        self.assertEqual(value['sha256'], hashlib.sha256(Path(value['path']).read_bytes()).hexdigest())
        builder.verify_windows_linker(value['version'])

    def test_retained_host_tools_are_selected_and_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tools").mkdir()
            (root / "tools/cmake").write_text("fixture")
            (root / "sdk.json").write_text(json.dumps({"host_tools": {"cmake": "tools/cmake"}}))
            self.assertEqual(builder.host_programs(root)["cmake"], str((root / "tools/cmake").resolve()))
            self.assertEqual(builder.host_programs(root)["ctest"], "ctest")
            (root / "sdk.json").write_text(json.dumps({"host_tools": {"cmake": "../outside"}}))
            with self.assertRaises(ValueError):
                builder.host_programs(root)

    def test_sdk_inventory_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            (root / "sysroot").mkdir()
            (root / "bin/cxx").write_bytes(b"compiler fixture")
            data = {"schema_version": 1, "recipe_id": "a" * 64, "target": {
                "system": "Linux", "processor": "x86_64", "triple": "x86_64-linux-gnu",
                "sysroot": "sysroot", "cxx_compiler": "bin/cxx"},
                "files": {"bin/cxx": hashlib.sha256(b"compiler fixture").hexdigest()}}
            (root / "sdk.json").write_text(json.dumps(data))
            self.assertEqual(len(builder.sdk_identity(root)), 64)
            (root / "sysroot/extra").write_text("unlisted")
            with self.assertRaises(ValueError):
                builder.sdk_identity(root)
            (root / "sysroot/extra").unlink()
            (root / "bin/cxx").write_bytes(b"modified")
            with self.assertRaises(ValueError):
                builder.sdk_identity(root)

    def test_path_and_job_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                builder.contained(Path(directory), "../elsewhere")
        self.assertGreaterEqual(builder.default_jobs(), 1)
        from unittest.mock import patch
        with patch("build_capacity.default_jobs", return_value=7):
            self.assertEqual(builder.default_jobs(), 7)
        with self.assertRaises(Exception):
            builder.positive("0")

    def test_runtime_install_script_selects_sdk_baseline_and_editor(self):
        import os
        import shutil
        import subprocess
        template = Path(builder.__file__).resolve().parents[1] / 'cmake/InstallRuntime.cmake.in'
        cmake = shutil.which('cmake')
        self.assertIsNotNone(cmake, 'CMake is required for build policy tests')
        with tempfile.TemporaryDirectory(prefix='runtime install ') as temporary:
            root = Path(temporary)
            (root / 'tools').mkdir()
            output = root / 'arguments.json'
            (root / 'tools/package_runtime.py').write_text(
                'import json,sys\nfrom pathlib import Path\nPath(' + repr(str(output)) +
                ').write_text(json.dumps(sys.argv[1:]))\n')
            script = root / 'configure.cmake'
            for sdk_root in ('', (root / 'retained SDK').as_posix()):
                with self.subTest(sdk=bool(sdk_root)):
                    script.write_text('cmake_minimum_required(VERSION 3.24)\n' +
                        'set(Python3_EXECUTABLE "' + Path(sys.executable).as_posix() + '")\n' +
                        'set(CMAKE_SOURCE_DIR "' + root.as_posix() + '")\n' +
                        'set(CMAKE_INSTALL_PREFIX "/opt/example")\n' +
                        'set(_portable_processor "x86_64")\n' +
                        'set(FOUNDATION_RUNTIME_ROOTS "' + (root/'target libraries').as_posix() + '")\n' +
                        'set(FOUNDATION_SDK_ROOT "' + sdk_root + '")\n' +
                        'configure_file("' + template.as_posix() + '" "' +
                        (root/'install.cmake').as_posix() + '" @ONLY)\n' +
                        'include("' + (root/'install.cmake').as_posix() + '")\n')
                    subprocess.run([cmake, '-P', str(script)], check=True,
                                   env=dict(os.environ, DESTDIR='/staging'))
                    args = json.loads(output.read_text())
                    expected = ['--prefix', '/staging/opt/example', '--processor', 'x86_64',
                                '--root', (root/'target libraries').as_posix()]
                    if sdk_root:
                        expected += ['--bookworm', '--elf-editor', sdk_root + '/bin/patchelf']
                    self.assertEqual(expected, args)

    def test_package_configuration_cannot_be_mislabelled(self):
        import shutil
        import subprocess
        cmake = shutil.which('cmake')
        self.assertIsNotNone(cmake, 'CMake is required for build policy tests')
        template = (Path(builder.__file__).resolve().parents[1] / 'cmake/PackagePolicy.cmake.in').read_text()
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / 'policy.cmake'
            for build_type, configurations, requested, success in (
                ('Debug', '', 'Release', False),
                ('Release', '', 'Release', True),
                ('', 'Debug;Release', 'Release', True),
                ('', 'Debug;Release', 'Debug', False)):
                body = template.replace('@FOUNDATION_SANITIZERS@', 'OFF').replace('@FOUNDATION_BUILD_GUI@', 'OFF')
                body = body.replace('@CMAKE_BUILD_TYPE@', build_type).replace('@CMAKE_CONFIGURATION_TYPES@', configurations)
                policy.write_text(body)
                result = subprocess.run([cmake, '-DCPACK_BUILD_CONFIG=' + requested, '-P', str(policy)], capture_output=True)
                self.assertEqual(result.returncode == 0, success, result.stderr)

    def test_mutation_during_packaging_invalidates_result(self):
        from unittest.mock import patch
        import sys
        sys.path.insert(0, str(Path(builder.__file__).parent))
        import source_identity
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            count = 0
            def run(command, **kwargs):
                nonlocal count
                if command[0] == 'cpack': count += 1
            def identity(*args): return {'revision': count}
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'run', side_effect=run), \
                    patch.object(builder, 'cache_identity', return_value={}), \
                    patch.object(source_identity, 'source_tree', side_effect=identity):
                with self.assertRaisesRegex(ValueError, 'source changed during the operation'):
                    builder.main(['package', 'release'])

    def test_normal_variable_compiler_is_read_from_active_cmake_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compiler = root / 'compiler with spaces'
            compiler.write_text('fixture compiler')
            (root / 'CMakeCache.txt').write_text('CMAKE_CACHE_MAJOR_VERSION:INTERNAL=3\nCMAKE_CACHE_MINOR_VERSION:INTERNAL=31\nCMAKE_CACHE_PATCH_VERSION:INTERNAL=6\n')
            record = root / 'CMakeFiles/3.31.6/CMakeCXXCompiler.cmake'
            record.parent.mkdir(parents=True)
            record.write_text('set(CMAKE_CXX_COMPILER "' + str(compiler) + '")\n')
            self.assertEqual(builder.cache_identity(root)['compiler_resolved_path'], str(compiler.resolve()))
            record.unlink()
            with self.assertRaises(OSError):
                builder.cache_identity(root)

    def test_unstamped_tree_is_not_silently_adopted(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tree = root / 'build/dev'
            tree.mkdir(parents=True)
            (tree / 'CMakeCache.txt').write_text('CMAKE_BUILD_TYPE:STRING=Release\n')
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'run') as run:
                with self.assertRaises(ValueError):
                    builder.main(['build', 'dev'])
                run.assert_not_called()

    def test_link_runtime_launcher_and_dependency_cache_edits_change_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compiler = root / 'compiler'
            compiler.write_text('fixture compiler')
            cache = root / 'CMakeCache.txt'
            base = 'CMAKE_CXX_COMPILER:FILEPATH=' + str(compiler) + '\n'
            for name in ('CMAKE_EXE_LINKER_FLAGS', 'CMAKE_SHARED_LINKER_FLAGS_RELEASE',
                         'CMAKE_MODULE_LINKER_FLAGS', 'CMAKE_STATIC_LINKER_FLAGS',
                         'CMAKE_INSTALL_RPATH', 'CMAKE_LINKER', 'CMAKE_CXX_COMPILER_LAUNCHER',
                         'CMAKE_PREFIX_PATH', 'Toolkit_DIR'):
                cache.write_text(base + name + ':STRING=original\n')
                before = builder.cache_identity(root)
                cache.write_text(base + name + ':STRING=changed\n')
                self.assertNotEqual(before, builder.cache_identity(root), name)


class WindowsLinkerTests(unittest.TestCase):
    def executable(self, path, machine=0x8664):
        import struct
        path.parent.mkdir(parents=True, exist_ok=True)
        content = bytearray(90); content[:2] = b'MZ'; struct.pack_into('<I', content, 60, 64)
        content[64:68] = b'PE\0\0'; struct.pack_into('<H', content, 68, machine)
        struct.pack_into('<H', content, 86, 2); struct.pack_into('<H', content, 88, 0x20b)
        path.write_bytes(content)
        return path

    def test_selected_file_identity_and_mutation_are_checked_without_execution(self):
        from unittest.mock import patch
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); expected = self.executable(root / 'toolset/bin/Hostx64/x64/link.exe')
            info = {'version':'14.44.35207.0','identities':[{'company':'Microsoft Corporation','original_filename':'LINK.EXE'}]}
            with patch.object(toolchain.platform, 'system', return_value='Windows'), \
                 patch.dict(toolchain.os.environ, {'VCToolsInstallDir':str(root/'toolset')}), \
                 patch.object(toolchain.shutil, 'which', return_value=str(expected)), \
                 patch.object(toolchain, 'file_version', return_value=info) as resource:
                value = toolchain.inspect_selected_linker()
                self.assertEqual(value['version'],info['version']);self.assertEqual(value['path'],str(expected.resolve()))
                self.assertEqual(value['sha256'],hashlib.sha256(expected.read_bytes()).hexdigest())
                other = self.executable(root/'other/link.exe')
                with patch.object(toolchain.shutil,'which',return_value=str(other)):
                    with self.assertRaisesRegex(ValueError,'PATH linker differs'):toolchain.inspect_selected_linker()
                for key,value in [('company','Other supplier'),('original_filename','other.exe')]:
                    changed = copy.deepcopy(info);changed['identities'][0][key]=value;resource.return_value=changed
                    with self.assertRaisesRegex(ValueError,'not the Microsoft linker'):toolchain.inspect_selected_linker()
                resource.return_value=dict(info,version='1.2.3.4')
                with self.assertRaisesRegex(ValueError,'not a supported'):toolchain.inspect_selected_linker()
                resource.return_value=info
                def mutate(path):
                    path.write_bytes(path.read_bytes()+b'changed');return info
                resource.side_effect=mutate
                with self.assertRaisesRegex(ValueError,'changed during'):toolchain.inspect_selected_linker()
                resource.side_effect=None;self.executable(expected,machine=0x14c)
                with self.assertRaisesRegex(ValueError,'native x64'):toolchain.inspect_selected_linker()
                expected.write_bytes(b'not a PE file')
                with self.assertRaisesRegex(ValueError,'not a PE'):toolchain.inspect_selected_linker()

    def test_win32_version_resource_reader_and_missing_or_outside_fields(self):
        import ctypes
        from ctypes import wintypes
        import struct
        from unittest.mock import Mock, patch
        fixed = [0xfeef04bd,0x10000,(14<<16)|44,(35207<<16),0,0,0,0,0,1,0,0,0]
        rows={'\\':struct.pack('<13I',*fixed),'\\VarFileInfo\\Translation':struct.pack('<HH',0x409,0x4b0),
              '\\StringFileInfo\\040904b0\\CompanyName':'Microsoft Corporation\0'.encode('utf-16-le'),
              '\\StringFileInfo\\040904b0\\OriginalFilename':'LINK.EXE\0'.encode('utf-16-le')}
        # Native ctypes pointer contracts are exercised using an inert buffer;
        # only DLL loading and the actual three API functions are substituted.
        offsets={};position=0
        for key,data in rows.items(): offsets[key]=position;position+=len(data)
        api=Mock();api.GetFileVersionInfoSizeW.return_value=512
        def fill(path,unused,size,block):
            for key,data in rows.items():ctypes.memmove(ctypes.addressof(block)+offsets[key],data,len(data))
            return 1
        def query(block,key,address,count):
            ctypes.cast(address,ctypes.POINTER(ctypes.c_void_p)).contents.value=ctypes.addressof(block)+offsets[key]
            ctypes.cast(count,ctypes.POINTER(wintypes.UINT)).contents.value=len(rows[key])//(2 if key.startswith('\\StringFileInfo') else 1)
            return 1
        api.GetFileVersionInfoW.side_effect=fill;api.VerQueryValueW.side_effect=query
        with patch.object(toolchain.platform,'system',return_value='Windows'), \
             patch.object(toolchain.ctypes,'WinDLL',return_value=api,create=True) as loader:
            value=toolchain.file_version(Path('selected-linker.exe'))
            self.assertEqual(value,{'version':'14.44.35207.0','identities':[{'company':'Microsoft Corporation','original_filename':'LINK.EXE'}]})
            loader.assert_called_with('version.dll',use_last_error=True,winmode=0x800)
            api.VerQueryValueW.side_effect=lambda *args:0
            with self.assertRaisesRegex(ValueError,'missing selected linker version field'):toolchain.file_version(Path('selected-linker.exe'))
            def outside(block,key,address,count):
                ctypes.cast(address,ctypes.POINTER(ctypes.c_void_p)).contents.value=ctypes.addressof(block)+1024
                ctypes.cast(count,ctypes.POINTER(wintypes.UINT)).contents.value=52
                return 1
            api.VerQueryValueW.side_effect=outside
            with self.assertRaisesRegex(ValueError,'exceeds its resource'):toolchain.file_version(Path('selected-linker.exe'))
            api.GetFileVersionInfoSizeW.return_value=0
            with self.assertRaisesRegex(ValueError,'missing or oversized'):toolchain.file_version(Path('selected-linker.exe'))
