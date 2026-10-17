"""Opt-in actual Windows publication scenarios. Never part of ordinary discovery.

Root registration must provide FOUNDATION_WINDOWS_PUBLICATION_ROOT as a fresh
canonical path on an owned local NTFS volume. Original observations are written
there and bound on stdout. This suite uses only Python child fixtures; it never
discovers an SDK, compiler, generator, provider, network service or application.
"""
import hashlib
import os
from pathlib import Path, PureWindowsPath
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_publication as publication
import process_tree

_BASE = None
_CASES = {}
_OWNERS = []


def setUpModule():
    global _BASE
    publication._native_host()
    if not sys.dont_write_bytecode:
        raise ValueError('Native publication diagnostic must start with -B')
    selected = os.environ.get('FOUNDATION_WINDOWS_PUBLICATION_ROOT')
    if not selected:
        raise ValueError('Select a fresh owned FOUNDATION_WINDOWS_PUBLICATION_ROOT')
    publication.contract.windows_path(selected, 'native diagnostic root')
    _BASE = publication._diagnostic_workspace(selected, limits={'maximum_output_bytes': 4 * 1024 * 1024})


def tearDownModule():
    if _BASE is None:
        return
    if any(not owner.closed for owner in _OWNERS):
        raise process_tree.ProcessTreeError('Diagnostic command owner remains open; retain all evidence')
    subjects = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in publication.SOURCE_FILES}
    if subjects['tools/appended_engine_windows_contract.py'] != publication.CONTRACT_SHA256:
        raise ValueError('Native diagnostic contract source differs')
    value = {'schema_version': 1, 'kind': 'foundation-windows-publication-observations-v1',
        'scope': publication.SCOPE, 'policy': publication.POLICY, 'source_identity': subjects,
        'runtime_identity': _BASE.native.runtime_identity(), 'filesystem': _BASE.filesystem,
        'cases': _CASES}
    raw = publication.encoded(value)
    row = _BASE.publish_bytes_new('observations.json', raw)
    print('WINDOWS_PUBLICATION_OBSERVATIONS_SHA256=' + row['sha256'], flush=True)
    print('WINDOWS_PUBLICATION_OBSERVATIONS_PATH=' + _BASE.output + '/observations.json', flush=True)
    _BASE.close_joined()


class NativePublication(unittest.TestCase):
    def work(self):
        name = self._testMethodName
        return publication._diagnostic_workspace(_BASE.output + '/' + name,
            limits={'maximum_output_bytes': 1024 * 1024, 'maximum_log_bytes': 65536})

    def record(self, value):
        _CASES[self._testMethodName] = {'operation': self._testMethodName, 'observed': value}

    def test_complete_atomic_no_replace(self):
        work = self.work()
        raw = b'{"complete":true}\n'; observed = []
        write, rename = work.native.write, work.native.rename_new
        def pending_write(handle, data):
            self.assertNotIn('body.json', work.native.names(work.directories['']))
            observed.append('final-absent-before-pending-write')
            return write(handle, data)
        def publish(handle, parent, name):
            self.assertNotIn(name, work.native.names(parent))
            rename(handle, parent, name)
            reader = work.native.open_child(parent, name)
            try: self.assertEqual(work.native.read(reader, len(raw)), raw)
            finally: work.native.close(reader)
            observed.append('independent-name-read-complete-after-rename')
        with mock.patch.object(work.native, 'write', side_effect=pending_write), mock.patch.object(work.native, 'rename_new', side_effect=publish):
            row = work.publish_bytes_new('body.json', raw)
        before = work.inspect_outputs()
        with self.assertRaises(FileExistsError): work.publish_bytes_new('body.json', b'bad')
        self.assertEqual(work.inspect_outputs(), before)
        work.close_joined()
        self.record({'published': row, 'readback': before, 'visibility_sequence': observed, 'collision_preserved': True})

    def test_existing_directory_and_case_collision(self):
        work = self.work(); work.mkdir_new('existing')
        with self.assertRaises(FileExistsError): work.mkdir_new('EXISTING')
        with self.assertRaises(FileExistsError): publication._diagnostic_workspace(work.output)
        state = work.inspect_outputs(); self.assertEqual(state['directories'], ['existing'])
        work.close_joined(); self.record({'readback': state, 'existing_empty_directory_preserved': True})

    def test_ancestor_handles_prevent_rename(self):
        work = self.work()
        with self.assertRaises(OSError): os.rename(work.output, work.output + '-moved')
        work.check_anchors()
        state = work.native.state(work.directories[''])
        self.assertEqual(state['path'], work.output)
        work.close_joined(); self.record({'anchored_root': state, 'rename_refused': True})

    def test_reparse_and_hardlink_rejected(self):
        work = self.work(); row = work.publish_bytes_new('plain.txt', b'owned')
        os.link(work.output + '/plain.txt', work.output + '/hard.txt')
        with self.assertRaises(publication.PublicationError): work.inspect_outputs()
        # A missing privilege is a diagnostic failure, never an internal skip.
        os.symlink('plain.txt', work.output + '/symbolic.txt')
        native = work.native
        handle = None
        try:
            with self.assertRaises((publication.PublicationError, OSError)):
                handle = native.open_child(work.directories[''], 'symbolic.txt', metadata_only=True)
                native.state(handle)
        finally:
            if handle is not None: native.close(handle)
        work.close_joined(); self.record({'original': row, 'hardlink_rejected': True, 'reparse_rejected': True})

    def test_complete_output_inventory(self):
        work = self.work(); work.mkdir_new('directory')
        row = work.publish_bytes_new('directory/data', b'precise bytes')
        first = work.inspect_outputs()
        expected = dict(first['files'], **{name: {'path': name, 'kind': 'directory'} for name in first['directories']})
        self.assertEqual(work.inspect_outputs(expected), first)
        self.assertEqual(first['files']['directory/data']['sha256'], row['sha256'])
        work.close_joined(); self.record({'complete_inventory': first})

    def test_owned_pending_cleanup(self):
        work = self.work()
        with mock.patch.object(work.native, 'flush', side_effect=OSError('injected pre-publication flush failure')):
            with self.assertRaises(OSError): work.publish_bytes_new('body', b'pending')
        pending = work._retained_pending[0][0]
        work.remove_owned_pending(pending)
        self.assertEqual(work.inspect_outputs()['files'], {})
        work.close_joined(); self.record({'exact_owned_pending_removed': pending, 'final_absent': True})

    def test_parent_exit_with_writer_rejected(self):
        work = self.work(); log = work.open_log_new('child.log'); work.mark_running(log)
        child = 'import sys,time; print("child",flush=True); time.sleep(30)'
        script = ('import subprocess,sys; subprocess.Popen([sys.executable,"-I","-B","-c",' +
            repr(child) + '],stdout=sys.stdout,stderr=sys.stderr)')
        owner = work.launch(log, [sys.executable, '-I', '-B', '-c', script], work.output,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        _OWNERS.append(owner)
        try:
            self.assertEqual(owner.wait(timeout=10), 0)
            with self.assertRaises(process_tree.ProcessTreeError): work.mark_joined(log, {'phase': 'probe'})
            self.assertTrue(work.uncertain)
        finally:
            # Explicit fixture recovery of the known Job; never release on parent exit.
            owner.terminate(timeout=5); owner.close()
        self.assertTrue(owner.closed)
        log.stream.close()
        self.record({'parent_exit': 0, 'parent_only_success_rejected': True,
            'job_closed_after_explicit_fixture_recovery': owner.closed, 'workspace_retained': work.uncertain})

    def test_joined_owner_seals_log(self):
        work = self.work(); log = work.open_log_new('joined.log'); work.mark_running(log)
        owner = work.launch(log, [sys.executable, '-I', '-B', '-c', 'print("native owned stdout")'],
            work.output, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        _OWNERS.append(owner)
        self.assertEqual(owner.wait(timeout=10), 0)
        joined = work.mark_joined(log, {'phase': 'probe', 'returncode': 0})
        row = work.seal_log(log); self.assertTrue(owner.closed); self.assertTrue(log.stream.closed)
        work.close_joined(); self.record({'stage': joined.as_dict(), 'closed_log': row})

    def test_flush_failure_stops_publication(self):
        work = self.work()
        with mock.patch.object(work.native, 'flush', side_effect=OSError('injected file FlushFileBuffers error')):
            with self.assertRaises(OSError): work.publish_bytes_new('body', b'complete')
        names = work.native.names(work.directories[''])
        self.assertNotIn('body', names)
        pending = work._retained_pending[0][0]
        work.remove_owned_pending(pending); work.close_joined()
        self.record({'final_absent_after_flush_failure': True, 'original_pending_names': names})

    def test_uncertain_rename_retains_evidence(self):
        work = self.work(); original = work.native.rename_new
        def after_commit(handle, parent, name):
            original(handle, parent, name)
            raise OSError('injected post-rename reporting failure')
        with mock.patch.object(work.native, 'rename_new', side_effect=after_commit):
            with self.assertRaises(OSError): work.publish_bytes_new('body', b'complete')
        self.assertTrue(work.uncertain)
        pending, handle, identity = work._retained_pending[0]
        state = work.native.state(handle)
        self.assertEqual(state['path'], work.output + '/body'); self.assertEqual(state['identity'], identity)
        self.assertEqual(work.native.read(handle, 64), b'complete')
        self.record({'committed_identity': state, 'old_pending_name': pending,
            'automatic_cleanup_refused': work.uncertain, 'ownership_retained': not work.closed})


if __name__ == '__main__':
    # Root normally runs this registered module through the complete case runner.
    unittest.main()
