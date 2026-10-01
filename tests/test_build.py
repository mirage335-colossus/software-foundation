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
    def test_sdk_inventory_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            (root / "sysroot").mkdir()
            (root / "bin/cxx").write_bytes(b"compiler fixture")
            data = {"schema_version": 1, "recipe_id": "test-only", "target": {
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
