import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("builder", Path(__file__).resolve().parents[1] / "tools/build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildTests(unittest.TestCase):
    def test_windows_linker_banner_and_file_version_use_same_order(self):
        from unittest.mock import patch
        for actual, minimum, success in (
                ('14.44.35207', '14.44.35207.0', True),
                ('14.44.35207.0', '14.44.35207', True),
                ('14.44.35207', '14.44.35207.1', False),
                ('14.44.35206.9', '14.44.35207.0', False),
                ('14.45.1', '14.44.35207.0', True)):
            with self.subTest(actual=actual, minimum=minimum), patch.object(
                    builder.subprocess, 'check_output', return_value='Linker Version ' + actual):
                if success:
                    builder.verify_windows_linker(minimum)
                else:
                    with self.assertRaises(ValueError): builder.verify_windows_linker(minimum)
        with patch.object(builder.subprocess, 'check_output', return_value='unrecognized tool'):
            with self.assertRaises(ValueError): builder.verify_windows_linker('14.44.35207.0')

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
        self.assertLessEqual(builder.default_jobs(), 4)
        with self.assertRaises(Exception):
            builder.positive("0")

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
