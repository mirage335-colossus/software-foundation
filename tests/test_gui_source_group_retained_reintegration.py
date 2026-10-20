"""Small retained-archive recovery fixtures; no toolkit code is executed."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_group', ROOT / 'gui/source_group.py')
subject = importlib.util.module_from_spec(spec); spec.loader.exec_module(subject)


class RetainedReintegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'upstream'; self.source.mkdir()
        (self.source / 'api.hpp').write_bytes(b'int api();\n')
        (self.source / 'run.sh').write_bytes(b'#!/bin/sh\nexit 0\n')
        (self.source / 'run.sh').chmod(0o755)
        def git(*args):
            return subprocess.run(['git', '-C', str(self.source), *args], check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
        git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid')
        git('config', 'user.name', 'Fixture'); git('config', 'core.autocrlf', 'false')
        git('add', '.'); git('update-index', '--chmod=+x', 'run.sh'); git('commit', '-qm', 'Fixture')
        self.foundation = self.base / 'foundation'
        (self.foundation / 'third_party').mkdir(parents=True)
        (self.foundation / 'gui/patches').mkdir(parents=True)
        (self.foundation / 'gui/patches/apply.py').write_bytes(b'apply = True\n')
        (self.foundation / 'gui/patches/one.patch').write_bytes(b'first patch\n')
        self.lock = {'revision': git('rev-parse', 'HEAD'), 'source_tree': git('rev-parse', 'HEAD^{tree}'),
                     'upstream': 'https://example.invalid/gui', 'license': 'NOASSERTION',
                     'redistribution': {'approved': False, 'license_files': []},
                     'patches': ['gui/patches/one.patch: fixture'],
                     'files': {'api.hpp': subject.archive.digest(self.source / 'api.hpp')}}
        (self.foundation / 'third_party/gui-boundary.lock.json').write_bytes(subject.archive.encoded(self.lock))
        self.old = self.base / 'old-group'
        subject.export(self.source, self.old, self.foundation)

    def test_reintegration_replaces_stale_integration_and_preserves_upstream(self):
        # The retained Foundation archive is a recognized subset of current inputs.
        (self.foundation / 'gui/patches/two.patch').write_bytes(b'second patch\n')
        self.lock['patches'].append('gui/patches/two.patch: fixture')
        (self.foundation / 'third_party/gui-boundary.lock.json').write_bytes(subject.archive.encoded(self.lock))
        with self.assertRaisesRegex(ValueError, 'incomplete archive inventory'):
            subject.verify(self.old, foundation_root=self.foundation)

        result_path = self.base / 'rebuilt-group'
        receipt = subject.reintegrate(self.old, result_path, self.foundation)
        manifest = subject.verify(result_path, foundation_root=self.foundation)
        self.assertEqual(receipt['revision'], self.lock['revision'])
        self.assertEqual(manifest['files']['upstream/api.hpp']['sha256'],
                         hashlib.sha256((self.source / 'api.hpp').read_bytes()).hexdigest())
        self.assertEqual(0o755, manifest['files']['upstream/run.sh']['mode'])
        self.assertIn('foundation/gui/patches/two.patch', manifest['files'])
        self.assertEqual(1, subject.verify(self.old, foundation_root=self._old_foundation()).get('schema_version'))

    def _old_foundation(self):
        # Restore the old lock/patch view solely to prove the source archive remains usable.
        old_root = self.base / 'old-foundation'; (old_root / 'third_party').mkdir(parents=True)
        (old_root / 'gui/patches').mkdir(parents=True)
        (old_root / 'gui/patches/apply.py').write_bytes(b'apply = True\n')
        (old_root / 'gui/patches/one.patch').write_bytes(b'first patch\n')
        original = dict(self.lock, patches=['gui/patches/one.patch: fixture'])
        (old_root / 'third_party/gui-boundary.lock.json').write_bytes(subject.archive.encoded(original))
        return old_root

    def test_changed_upstream_is_rejected_without_creating_output(self):
        archive_path = self.old / 'gui-inputs.tar.gz'
        manifest_path = self.old / 'manifest.json'
        manifest = subject.archive.read_json(manifest_path)
        import io
        with tarfile.open(archive_path, 'r:gz') as source:
            records = [(member, source.extractfile(member).read()) for member in source]
        with tempfile.NamedTemporaryFile(dir=self.base, delete=False) as raw:
            temporary = Path(raw.name)
        with tarfile.open(temporary, 'w:gz') as target:
            for member, data in records:
                if member.name == 'upstream/api.hpp':
                    data = b'int wrong();\n'
                member.size = len(data)
                target.addfile(member, io.BytesIO(data))
                manifest['files'][member.name]['sha256'] = hashlib.sha256(data).hexdigest()
                manifest['files'][member.name]['size'] = len(data)
        archive_path.write_bytes(temporary.read_bytes()); temporary.unlink()
        manifest['archive_sha256'] = subject.archive.digest(archive_path)
        manifest_path.write_bytes(subject.archive.encoded(manifest))
        (self.old / 'SHA256SUMS').write_text(
            f"{subject.archive.digest(archive_path)}  gui-inputs.tar.gz\n"
            f"{subject.archive.digest(manifest_path)}  manifest.json\n")
        output = self.base / 'must-not-exist'
        with self.assertRaisesRegex(ValueError, 'complete source tree'):
            subject.reintegrate(self.old, output, self.foundation)
        self.assertFalse(output.exists())

    def test_overlapping_output_is_rejected(self):
        for output, reason in ((self.old / 'nested', 'overlap'),
                               (self.foundation / 'gui', 'must be new')):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, reason):
                subject.reintegrate(self.old, output, self.foundation)

    def test_source_replacement_after_verification_prevents_publication(self):
        output = self.base / 'must-not-publish'
        original = subject.verify
        def replace_source(*args, **kwargs):
            result = original(*args, **kwargs)
            path = self.foundation / 'gui/patches/one.patch'
            replacement = path.with_suffix('.replacement')
            replacement.write_bytes(path.read_bytes())
            replacement.replace(path)
            return result
        with mock.patch.object(subject, 'verify', side_effect=replace_source):
            with self.assertRaisesRegex(ValueError, 'integration inputs changed'):
                subject.reintegrate(self.old, output, self.foundation)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
