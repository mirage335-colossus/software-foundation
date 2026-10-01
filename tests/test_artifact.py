import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("artifact", Path(__file__).resolve().parents[1] / "tools/artifact.py")
artifact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifact)


class ArtifactTests(unittest.TestCase):
    def test_rejects_escaping_paths_and_duplicates(self):
        for name in ("../outside", "/absolute", "C:/drive", "back\\slash"):
            with self.assertRaises(ValueError):
                artifact.member_path(name)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            with zipfile.ZipFile(path, "w") as bundle:
                bundle.writestr("file", "first")
                bundle.writestr("./file", "second")
            with self.assertRaises(ValueError):
                artifact.inspect_archive(path)

    def test_rejects_links_and_detects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.tar"
            with tarfile.open(path, "w") as bundle:
                link = tarfile.TarInfo("link")
                link.type = tarfile.SYMTYPE
                link.linkname = "../../other"
                bundle.addfile(link)
            with self.assertRaises(ValueError):
                artifact.inspect_archive(path)
            path = Path(directory) / "good.tar"
            with tarfile.open(path, "w") as bundle:
                item = tarfile.TarInfo("prefix/file")
                item.size = 5
                bundle.addfile(item, io.BytesIO(b"hello"))
            self.assertEqual(artifact.describe(path)["files"]["prefix/file"]["size"], 5)

    def test_rejects_privileged_mode_and_modified_archive(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "package.tar"
            def make(data, mode=0o644):
                with tarfile.open(path, "w") as bundle:
                    item = tarfile.TarInfo("prefix/file")
                    item.size = len(data)
                    item.mode = mode
                    bundle.addfile(item, io.BytesIO(data))
            make(b"first", 0o4755)
            with self.assertRaises(ValueError):
                artifact.describe(path)
            make(b"first")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(artifact.describe(path)))
            make(b"other")
            with self.assertRaises(ValueError):
                artifact.verify(path, manifest)
