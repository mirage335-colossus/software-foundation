import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dependency_archive import extract, file_inventory
from dependency_store import copy_group, fetch, names, put, verify_group
from test_sdk import fixture


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.recipe, _, _, self.group = fixture(self.root)

    def tearDown(self): self.temp.cleanup()

    def test_put_reuse_fetch_no_network(self):
        base = self.root / 'base'
        self.assertFalse(put(base, self.group, self.recipe)['reused'])
        self.assertTrue(put(base, self.group, self.recipe)['reused'])
        fetch(base, self.recipe, self.root / 'fetched')
        self.assertEqual(file_inventory(self.group), file_inventory(self.root / 'fetched'))

    def test_missing_base_never_prepares(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            fetch(self.root / 'absent', self.recipe, self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_incomplete_group_rejected(self):
        (self.group / names(self.recipe)[1]).unlink()
        with self.assertRaisesRegex(ValueError, 'exactly'):
            verify_group(self.group, self.recipe)

    def test_changed_archive_rejected(self):
        (self.group / names(self.recipe)[0]).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            put(self.root / 'base', self.group, self.recipe)

    def test_unexpected_asset_rejected(self):
        (self.group / 'extra').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'exactly'):
            verify_group(self.group, self.recipe)

    def test_duplicate_checksum_rejected(self):
        path = self.group / names(self.recipe)[2]
        path.write_text(path.read_text() + path.read_text().splitlines()[0] + '\n')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            verify_group(self.group, self.recipe)

    def test_unsafe_archive_entries_leave_no_output(self):
        for index, (name, kind) in enumerate((('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE), ('link', tarfile.SYMTYPE), ('file', tarfile.FIFOTYPE))):
            archive = self.root / ('bad-' + str(index) + '.tar')
            with tarfile.open(archive, 'w') as stream:
                info = tarfile.TarInfo(name)
                info.type = kind
                info.linkname = 'outside'
                stream.addfile(info, io.BytesIO())
            output = self.root / ('bad-output-' + str(index))
            with self.assertRaises(ValueError): extract(archive, output)
            self.assertFalse(output.exists())

    def test_file_parent_collision_is_rejected_before_writing(self):
        archive = self.root / 'collision.tar'
        with tarfile.open(archive, 'w') as stream:
            for name in ('parent', 'parent/child'):
                info = tarfile.TarInfo(name)
                stream.addfile(info, io.BytesIO())
        with self.assertRaisesRegex(ValueError, 'parent'):
            extract(archive, self.root / 'collision')
        self.assertFalse((self.root / 'collision').exists())


if __name__ == '__main__': unittest.main()
