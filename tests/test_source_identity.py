from pathlib import Path
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dependency_archive import extract
from source_identity import archive_source, source_tree, verify_source_archive


class SourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'main.cpp').write_text('int main(){return 0;}\n')
        (self.source / 'build.sh').write_text('#!/bin/sh\nexit 0\n')
        (self.source / 'build.sh').chmod(0o755)

    def tearDown(self): self.temp.cleanup()

    def test_archive_matches_tree_and_restored_tree(self):
        data = archive_source(self.source, self.root / 'source.tar.gz')
        self.assertEqual(data, source_tree(self.source))
        self.assertEqual(data, verify_source_archive(self.root / 'source.tar.gz'))
        extract(self.root / 'source.tar.gz', self.root / 'restored')
        self.assertEqual(data, source_tree(self.root / 'restored'))

    def test_source_bytes_change_identity(self):
        before = source_tree(self.source)
        (self.source / 'main.cpp').write_text('int main(){return 1;}\n')
        self.assertNotEqual(before['tree_sha256'], source_tree(self.source)['tree_sha256'])

    @unittest.skipIf(os.name == 'nt', 'POSIX executable bit')
    def test_executable_mode_changes_identity(self):
        before = source_tree(self.source)
        (self.source / 'build.sh').chmod(0o644)
        self.assertNotEqual(before['tree_sha256'], source_tree(self.source)['tree_sha256'])

    def test_generated_outputs_excluded(self):
        before = source_tree(self.source)
        (self.source / 'build').mkdir()
        (self.source / 'build/output').write_text('generated')
        self.assertEqual(before, source_tree(self.source))

    def test_supplement_retained_and_not_double_counted(self):
        extra = self.root / 'gui'
        extra.mkdir()
        (extra / 'generic.hpp').write_text('// supplier source\n')
        data = archive_source(self.source, self.root / 'source.tar.gz', extra)
        extract(self.root / 'source.tar.gz', self.root / 'restored')
        self.assertEqual(data, source_tree(self.root / 'restored'))
        self.assertEqual(data, source_tree(self.root / 'restored', self.root / 'restored/third_party/retained/gui'))
        self.assertIn('third_party/retained/gui/generic.hpp', data['files'])

    def test_archive_cannot_become_its_own_source_input(self):
        with self.assertRaisesRegex(ValueError, 'outside source inputs'):
            archive_source(self.source, self.source / 'source.tar.gz')

    def test_unlisted_restored_source_rejected(self):
        archive_source(self.source, self.root / 'source.tar.gz')
        extract(self.root / 'source.tar.gz', self.root / 'restored')
        (self.root / 'restored/unlisted.cpp').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            source_tree(self.root / 'restored')


if __name__ == '__main__': unittest.main()
