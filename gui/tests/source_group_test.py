#!/usr/bin/env python3
"""Offline group identity, failure isolation and complete-source tests."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('source_group', ROOT / 'gui/source_group.py')
subject = importlib.util.module_from_spec(spec); spec.loader.exec_module(subject)


class SourceGroupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'; self.source.mkdir()
        self.foundation = self.root / 'foundation'
        (self.foundation / 'third_party').mkdir(parents=True)
        (self.foundation / 'gui/patches').mkdir(parents=True)
        (self.foundation / 'gui/patches/apply.py').write_text('apply = True\n')
        (self.foundation / 'gui/patches/host.patch').write_text('reviewed patch\n')
        (self.source / 'api.hpp').write_text('int result();\n')
        (self.source / 'retained.txt').write_text('Complete retained source\n')
        (self.source / 'run.sh').write_text('#!/bin/sh\nexit 0\n'); (self.source / 'run.sh').chmod(0o755)
        def git(*args):
            return subprocess.run(['git', '-C', str(self.source), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
        git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'Fixture')
        git('add', '.'); git('commit', '-qm', 'Fixture input')
        self.lock = {'revision': git('rev-parse', 'HEAD'), 'source_tree': git('rev-parse', 'HEAD^{tree}'),
                     'upstream': 'https://example.invalid/gui', 'license': 'NOASSERTION',
                     'redistribution': {'approved': False, 'license_files': []},
                     'patches': ['gui/patches/host.patch: fixture'],
                     'files': {'api.hpp': subject.archive.digest(self.source / 'api.hpp')}}
        (self.foundation / 'third_party/gui-boundary.lock.json').write_text(json.dumps(self.lock))
        self.group = self.root / 'group'
        subject.export(self.source, self.group, self.foundation)

    def rewrite(self, change, change_manifest=False):
        manifest = subject.archive.read_json(self.group / 'manifest.json')
        with tarfile.open(self.group / 'gui-inputs.tar.gz') as archive:
            entries = [(member, archive.extractfile(member).read()) for member in archive]
        entries = change(entries)
        with tarfile.open(self.group / 'gui-inputs.tar.gz', 'w:gz') as archive:
            for member, data in entries:
                member.size = len(data); archive.addfile(member, io.BytesIO(data))
                if change_manifest:
                    manifest['files'][member.name] = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'mode': member.mode}
        manifest['archive_sha256'] = subject.archive.digest(self.group / 'gui-inputs.tar.gz')
        (self.group / 'manifest.json').write_bytes(subject.archive.encoded(manifest))
        (self.group / 'SHA256SUMS').write_text(''.join(f'{subject.archive.digest(self.group / name)}  {name}\n' for name in ['gui-inputs.tar.gz', 'manifest.json']))

    def verify(self):
        return subject.verify(self.group, foundation_root=self.foundation)

    def test_export_deterministic_restore_and_repeat(self):
        other = self.root / 'other'; subject.export(self.source, other, self.foundation)
        self.assertEqual(subject.archive.file_inventory(self.group), subject.archive.file_inventory(other))
        output = self.root / 'restored'; result = subject.restore(self.group, output, self.foundation)
        self.assertEqual(str(output / 'upstream'), result['source'])
        self.assertEqual(result, subject.restore(self.group, output, self.foundation))
        self.assertEqual(self.source.joinpath('retained.txt').read_bytes(), output.joinpath('upstream/retained.txt').read_bytes())
        self.assertTrue(output.joinpath('upstream/run.sh').stat().st_mode & 0o111)

    def test_terms_block_redistribution_only(self):
        self.assertFalse(self.verify()['redistributable'])
        with self.assertRaisesRegex(ValueError, 'terms'):
            subject.verify(self.group, True, self.foundation)

    def test_mutated_existing_restore_preserved(self):
        output = self.root / 'restored'; subject.restore(self.group, output, self.foundation)
        target = output / 'upstream/api.hpp'; target.write_text('local work')
        with self.assertRaises(ValueError): subject.restore(self.group, output, self.foundation)
        self.assertEqual('local work', target.read_text())

    def test_foreign_directory_and_input_rejected(self):
        output = self.root / 'restored'; subject.restore(self.group, output, self.foundation)
        (output / 'foreign').mkdir()
        with self.assertRaises(ValueError): subject.restore(self.group, output, self.foundation)
        (self.group / 'unexpected').write_text('extra')
        with self.assertRaises(ValueError): self.verify()

    def test_integration_change_rejected(self):
        (self.foundation / 'gui/patches/host.patch').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'integration'): self.verify()

    def test_unconsumed_source_tamper_rejected_by_complete_tree(self):
        self.rewrite(lambda entries: [(member, b'tampered' if member.name == 'upstream/retained.txt' else data) for member, data in entries], True)
        with self.assertRaisesRegex(ValueError, 'complete source tree'): self.verify()

    def test_duplicate_archive_entry_rejected_before_output(self):
        self.rewrite(lambda entries: entries + [entries[0]])
        output = self.root / 'output'
        with self.assertRaises(ValueError): subject.restore(self.group, output, self.foundation)
        self.assertFalse(output.exists())

    def test_unsafe_archive_path_rejected(self):
        def change(entries):
            entries[0][0].name = '../outside'; return entries
        self.rewrite(change, True)
        with self.assertRaises(ValueError): self.verify()
        self.assertFalse((self.root / 'outside').exists())

    def test_link_and_checksum_tamper_rejected(self):
        path = self.group / 'SHA256SUMS'; content = path.read_text(); path.unlink(); path.symlink_to(self.source / 'retained.txt')
        with self.assertRaises(ValueError): self.verify()
        path.unlink(); path.write_text(content + 'invalid\n')
        with self.assertRaises(ValueError): self.verify()

    def test_bounded_inventory_and_case_collision(self):
        value = {'sha256': 'a' * 64, 'size': 1, 'mode': 0o644}
        for entries in ({'a/x': value, 'A/y': value}, {'x': value, 'x/y': value}, {'CON': value}, {'x': dict(value, size=subject.MAX_FILE + 1)}):
            with self.assertRaises(ValueError): subject.validate_entries(entries)

    def test_windows_logical_modes_do_not_depend_on_chmod(self):
        path = self.source / 'run.sh'; path.chmod(0o644)
        with patch.object(subject, 'WINDOWS', True):
            self.assertEqual(0o755, subject.metadata(path, 0o755)['mode'])
        with patch.object(subject, 'WINDOWS', False):
            self.assertEqual(0o644, subject.metadata(path, 0o755)['mode'])

    def test_missing_archive_member_and_truncated_input_rejected(self):
        self.rewrite(lambda entries: entries[1:])
        with self.assertRaises(ValueError): self.verify()
        target = self.group / 'gui-inputs.tar.gz'; target.write_bytes(target.read_bytes()[:20])
        with self.assertRaises(ValueError): self.verify()

    def test_dirty_checkout_rejected(self):
        (self.source / 'retained.txt').write_text('changed')
        with self.assertRaises(ValueError): subject.export(self.source, self.root / 'dirty', self.foundation)


if __name__ == '__main__':
    unittest.main()
