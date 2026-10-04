"""Namespace adapter/inventory checks; actual acceptance is recorded separately."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import offline_namespace as namespace
import offline_acceptance as acceptance


@unittest.skipUnless(sys.platform.startswith('linux'), 'User/mount/PID/network namespaces require Linux')
class OfflineNamespace(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.rootfs = self.root / 'rootfs'
        for name in ('etc', 'work', 'output', 'inputs/group', 'proc', 'dev', 'sys', 'tmp', 'usr/bin'):
            (self.rootfs / name).mkdir(parents=True, exist_ok=True)
        (self.rootfs / 'etc/os-release').write_text('ID=debian\nVERSION_ID="12"\n')
        (self.rootfs / 'usr/bin/setpriv').write_text('diagnostic fixture, not an executable rootfs\n')
        self.receipt = self.root / 'receipt.json'
        self.files = self.root / 'files.json'
        self.save_receipt()

    def save_receipt(self):
        files = namespace.rootfs_files(self.rootfs)
        self.files.write_text(json.dumps(files, sort_keys=True, separators=(',', ':')))
        self.receipt.write_text(json.dumps({'schema_version': 1, 'rootfs': str(self.rootfs),
            'architecture': acceptance.processor(), 'os_release': (self.rootfs / 'etc/os-release').read_text(),
            'packages': [{'name': 'fixture', 'version': '1', 'architecture': 'fixture'}],
            'inventory': self.files.name, 'inventory_sha256': namespace.inventory_digest(files)}))
        self.boundary = {'kind': 'namespace', 'rootfs': str(self.rootfs), 'manifest': str(self.receipt),
                         'manifest_sha256': namespace.file_hash(self.receipt)}

    def test_pinned_complete_rootfs_detects_byte_mode_link_and_entry_changes(self):
        namespace.verify_rootfs(self.boundary)
        path = self.rootfs / 'usr/bin/setpriv'
        before = path.read_bytes(); mode = path.stat().st_mode
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            namespace.verify_rootfs(self.boundary)
        path.write_bytes(before); path.chmod(mode)
        path.chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            namespace.verify_rootfs(self.boundary)
        path.chmod(mode)
        (self.rootfs / 'extra').symlink_to('/host/input')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            namespace.verify_rootfs(self.boundary)

    def test_inventory_and_manifest_cannot_be_substituted(self):
        self.files.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            namespace.verify_rootfs(self.boundary)
        self.save_receipt()
        self.receipt.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'pinned identity'):
            namespace.verify_rootfs(self.boundary)
        self.save_receipt()
        metadata = json.loads(self.receipt.read_text()); metadata['inventory'] = '../elsewhere'
        self.receipt.write_text(json.dumps(metadata)); self.boundary['manifest_sha256'] = namespace.file_hash(self.receipt)
        with self.assertRaisesRegex(ValueError, 'contained manifest sibling'):
            namespace.verify_rootfs(self.boundary)

    def test_wrong_os_or_missing_mount_point_fails_before_namespace_setup(self):
        (self.rootfs / 'etc/os-release').write_text('ID=debian\nVERSION_ID=13\n')
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, 'Bookworm'):
            namespace.verify_rootfs(self.boundary)
        (self.rootfs / 'etc/os-release').write_text('ID=debian\nVERSION_ID=12\n')
        (self.rootfs / 'inputs/group').rmdir(); self.save_receipt()
        with self.assertRaisesRegex(ValueError, 'mount point'):
            namespace.verify_rootfs(self.boundary)

    def test_launch_requests_all_namespaces_without_host_home_or_credentials(self):
        source, output, group = [self.root / name for name in ('source', 'output', 'group')]
        with patch.object(namespace.os, 'getuid', return_value=1000), patch.object(namespace.os, 'getgid', return_value=1000), \
                patch.object(namespace.shutil, 'which', return_value=sys.executable):
            command = namespace.command(self.boundary, source, output, group)
        self.assertEqual(command[0], str(Path(sys.executable).resolve(strict=True)))
        for argument in ('--user', '--map-root-user', '--mount', '--net', '--pid', '--fork'):
            self.assertIn(argument, command)
        self.assertIn(str(source / 'tools/offline_namespace.py'), command)
        self.assertNotIn(str(Path.home()), command)
        self.assertNotIn('GH_TOKEN', command)
        with patch.object(namespace.os, 'getuid', return_value=0), self.assertRaisesRegex(ValueError, 'ordinary'):
            namespace.command(self.boundary, source, output, group)

    def test_host_path_cannot_replace_namespace_setup_programs_or_leak_credentials(self):
        fake = self.root / 'fake-bin'; fake.mkdir()
        for name in ('unshare', 'mount', 'chroot', 'ip'):
            path = fake / name; path.write_text('#!/bin/sh\nexit 0\n'); path.chmod(0o755)
        with patch.dict(os.environ, {'PATH': str(fake), 'GH_TOKEN': 'private', 'LD_PRELOAD': '/host/injection'}):
            for name in ('unshare', 'mount', 'chroot', 'ip'):
                selected = namespace.setup_program(name)
                self.assertNotIn(str(fake), selected)
                self.assertTrue(Path(selected).is_absolute())
            environment = namespace.setup_environment()
        self.assertNotIn('GH_TOKEN', environment)
        self.assertNotIn('LD_PRELOAD', environment)
        self.assertEqual(environment['PATH'], namespace.SETUP_PATH)

    def test_special_rootfs_entries_fail_closed(self):
        os.mkfifo(self.rootfs / 'fifo')
        with self.assertRaisesRegex(ValueError, 'special entry'):
            namespace.rootfs_files(self.rootfs)


if __name__ == '__main__':
    unittest.main()
