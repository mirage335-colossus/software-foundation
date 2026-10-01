from pathlib import Path
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dependency_archive import extract
from source_identity import archive_source, source_tree, verify_source_archive
import source_identity as source_module
import json
from unittest.mock import patch


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
        (extra / 'setup.sh').write_text('#!/bin/sh\nexit 0\n')
        (extra / 'setup.sh').chmod(0o755)
        data = archive_source(self.source, self.root / 'source.tar.gz', extra)
        extract(self.root / 'source.tar.gz', self.root / 'restored')
        self.assertEqual(data, source_tree(self.root / 'restored'))
        self.assertEqual(data, source_tree(self.root / 'restored', self.root / 'restored/third_party/retained/gui'))
        self.assertIn('third_party/retained/gui/generic.hpp', data['files'])
        with patch.object(source_module, 'WINDOWS', True):
            self.assertEqual(data, source_tree(self.root / 'restored', self.root / 'restored/third_party/retained/gui'))

    def test_archive_cannot_become_its_own_source_input(self):
        with self.assertRaisesRegex(ValueError, 'outside source inputs'):
            archive_source(self.source, self.source / 'source.tar.gz')

    def test_failed_archive_staging_does_not_publish_partial_output(self):
        destination = self.root / 'source.tar.gz'
        with patch.object(source_module.tarfile.TarFile, 'addfile', side_effect=OSError('injected archive failure')):
            with self.assertRaises(OSError): archive_source(self.source, destination)
        self.assertFalse(destination.exists())

    def test_windows_retained_modes_survive_non_executable_storage(self):
        data = source_tree(self.source)
        data['executables'] = ['build.sh']
        # Produce authoritative metadata with the same logical modes on every host.
        paths = source_module.snapshot_paths(self.source)
        data = source_module.describe_paths(paths, {'build.sh'})
        (self.source / 'source.json').write_text(json.dumps(data), encoding='utf-8')
        (self.source / 'build.sh').chmod(0o644)
        with patch.object(source_module, 'WINDOWS', True):
            self.assertEqual(data, source_tree(self.source))
            archive_source(self.source, self.root / 'portable.tar.gz')
            self.assertEqual(data, verify_source_archive(self.root / 'portable.tar.gz'))
            (self.source / 'main.cpp').write_text('changed')
            self.assertNotEqual(data, source_tree(self.source))

    def test_windows_index_modes_are_preserved_and_conflicts_rejected(self):
        (self.source / '.git').mkdir()
        paths = {'build.sh': self.source / 'build.sh'}
        with patch.object(source_module, 'WINDOWS', True), patch.object(source_module.subprocess, 'check_output', return_value=b'100755 abc 0\tbuild.sh\0'):
            self.assertEqual({'build.sh'}, source_module.portable_executables(self.source, paths))
        with patch.object(source_module, 'WINDOWS', True), patch.object(source_module.subprocess, 'check_output', return_value=b'100755 abc 2\tbuild.sh\0'):
            with self.assertRaisesRegex(ValueError, 'unmerged'):
                source_module.portable_executables(self.source, paths)

    def test_nested_git_checkout_uses_own_index_before_parent_archive(self):
        (self.source / '.git').mkdir()
        (self.root / 'source.json').write_text(json.dumps({'files': {}, 'executables': []}))
        paths = {'build.sh': self.source / 'build.sh'}
        with patch.object(source_module, 'WINDOWS', True), patch.object(source_module.subprocess, 'check_output', return_value=b'100755 abc 0\tbuild.sh\0'):
            self.assertEqual({'build.sh'}, source_module.portable_executables(self.source, paths))
        for row in (b'120000 abc 0\tbuild.sh\0', b'100755 abc 0\tbuild.sh\0' * 2):
            with patch.object(source_module, 'WINDOWS', True), patch.object(source_module.subprocess, 'check_output', return_value=row):
                with self.assertRaisesRegex(ValueError, 'unsupported or duplicate'):
                    source_module.portable_executables(self.source, paths)

    def test_unlisted_restored_source_rejected(self):
        archive_source(self.source, self.root / 'source.tar.gz')
        extract(self.root / 'source.tar.gz', self.root / 'restored')
        (self.root / 'restored/unlisted.cpp').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            source_tree(self.root / 'restored')


if __name__ == '__main__': unittest.main()
