import importlib.util
from pathlib import Path
import shutil
import hashlib
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("appended_wasm3", ROOT / "tools" / "appended_wasm3.py")
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)


class RetainedInterpreterTests(unittest.TestCase):
    def test_current_source_identity(self):
        identity = W.verify_source()
        self.assertEqual(identity["commit"], W.COMMIT)
        self.assertEqual(identity["patches"], [{"file": W.PATCH_FILE, "sha256": W.PATCH_SHA256}])

    def test_undeclared_patch_and_rehashed_patch_changes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "supplier"
            shutil.copytree(W.SOURCE, source)
            manifest = json.loads((source / "manifest.json").read_text())
            original = list(manifest["patches"])
            manifest["patches"] = []
            (source / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "unexpected wasm3 supplier identity"):
                W.verify_source(source)
            manifest["patches"] = original
            target = source / W.PATCH_FILE
            target.write_bytes(target.read_bytes() + b"\n")
            manifest["files"][W.PATCH_FILE] = hashlib.sha256(target.read_bytes()).hexdigest()
            (source / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "changed retained wasm3 patch"):
                W.verify_source(source)

    def test_changed_missing_and_unlisted_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "supplier"
            shutil.copytree(W.SOURCE, source)
            target = source / "source" / "m3_env.c"
            original = target.read_bytes()
            target.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "changed wasm3 input"):
                W.verify_source(source)
            target.write_bytes(original)
            (source / "unexpected").write_bytes(b"input")
            with self.assertRaisesRegex(ValueError, "unlisted or missing"):
                W.verify_source(source)
            (source / "unexpected").unlink()
            target.unlink()
            with self.assertRaisesRegex(ValueError, "unlisted or missing"):
                W.verify_source(source)

    def test_symlink_and_checksum_changes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "supplier"
            shutil.copytree(W.SOURCE, source)
            target = source / "XXHASH-LICENSE"
            target.unlink()
            try:
                target.symlink_to(W.SOURCE / "XXHASH-LICENSE")
            except (OSError, NotImplementedError):
                self.skipTest("host cannot create the symlink fixture")
            with self.assertRaisesRegex(ValueError, "symlink"):
                W.verify_source(source)
            target.unlink()
            shutil.copyfile(W.SOURCE / "XXHASH-LICENSE", target)
            (source / "SHA256SUMS").write_text("", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "checksum list"):
                W.verify_source(source)

    def test_rehashed_local_patch_is_not_unmodified_supplier_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "supplier"
            shutil.copytree(W.SOURCE, source)
            target = source / "source" / "m3_env.c"
            target.write_bytes(target.read_bytes() + b"\n")
            manifest = json.loads((source / "manifest.json").read_text())
            manifest["files"]["source/m3_env.c"] = hashlib.sha256(target.read_bytes()).hexdigest()
            (source / "manifest.json").write_text(json.dumps(manifest))
            (source / "SHA256SUMS").write_text("".join(
                digest + "  " + name + "\n" for name, digest in sorted(manifest["files"].items())))
            with self.assertRaisesRegex(ValueError, "source subset differs"):
                W.verify_source(source)


if __name__ == "__main__":
    unittest.main()
