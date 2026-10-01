"""Release transport fixtures use no network or Actions artifact storage."""
import copy
import hashlib
import io
import json
import os
import stat
from types import SimpleNamespace
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import ci_transport as t


class FakeGitHub:
    def __init__(self):
        self.repo = dict(id=7, full_name='example/project')
        self.run = dict(id=12, run_attempt=2, head_sha='a' * 40, event='workflow_dispatch',
                        path='.github/workflows/sdk-maintenance.yml',
                        repository=self.repo.copy(), head_repository=self.repo.copy())
        self.jobs = [dict(id=30, run_id=12, run_attempt=2, head_sha='a' * 40,
                         name='produce (linux-aarch64)', runner_id=90, runner_name='Runner 1',
                         status='in_progress', conclusion=None)]
        self.refs = {}; self.releases = []; self.data = {}; self.next_asset = 100
        self.calls = []; self.lose_upload = False; self.on_download = None

    def json(self, endpoint, *, method='GET', body=None, missing=False):
        self.calls.append((method, endpoint))
        base = 'repos/example/project'; assert endpoint.startswith(base)
        path = endpoint[len(base):]
        if not path: return copy.deepcopy(self.repo)
        if path == '/actions/runs/12/attempts/2': return copy.deepcopy(self.run)
        if path.startswith('/actions/runs/12/attempts/2/jobs?'):
            page = int(path.rsplit('page=', 1)[1]); rows = self.jobs[(page - 1) * 100:page * 100]
            return dict(total_count=len(self.jobs), jobs=copy.deepcopy(rows))
        if path.startswith('/actions/jobs/'):
            return copy.deepcopy(next(j for j in self.jobs if j['id'] == int(path.rsplit('/', 1)[1])))
        if path.startswith('/git/ref/tags/'):
            value = self.refs.get(path.split('/tags/', 1)[1])
            if value is None and missing: return None
            if value is None: raise t.delivery.DeliveryError('missing tag')
            return dict(object=dict(type='commit', sha=value))
        if path == '/git/refs' and method == 'POST':
            name = body['ref'].split('refs/tags/', 1)[1]
            if name in self.refs: raise t.delivery.DeliveryError('already exists')
            self.refs[name] = body['sha']; return {}
        if path == '/releases' and method == 'POST':
            if any(row['tag_name'] == body['tag_name'] for row in self.releases):
                raise t.delivery.DeliveryError('release already exists')
            self.releases.append(dict(body, id=9, assets=[])); return copy.deepcopy(self.releases[-1])
        raise AssertionError((endpoint, method, body))

    def pages(self, endpoint):
        self.calls.append(('pages', endpoint))
        if endpoint.endswith('/releases?per_page=100'): return copy.deepcopy(self.releases)
        assert '/releases/9/assets?' in endpoint
        return copy.deepcopy(self.releases[0]['assets'])

    def upload(self, tag, path):
        self.calls.append(('upload', path.name))
        row = self.releases[0]; assert row['tag_name'] == tag
        assert all(a['name'] != path.name for a in row['assets'])
        raw = path.read_bytes(); aid = self.next_asset; self.next_asset += 1
        row['assets'].append(dict(id=aid, name=path.name, size=len(raw), digest='sha256:' + t.delivery.sha(raw), state='uploaded'))
        self.data[aid] = raw
        if self.lose_upload:
            self.lose_upload = False
            raise t.delivery.DeliveryError('response lost after write', True)

    def download(self, aid, path):
        self.calls.append(('download', aid)); path.write_bytes(self.data[aid])
        if self.on_download:
            callback, self.on_download = self.on_download, None; callback()

    def complete(self, conclusion='success'):
        self.jobs[0].update(status='completed', conclusion=conclusion)

    def replace(self, name, content):
        row = next(a for a in self.releases[0]['assets'] if a['name'] == name)
        row.update(size=len(content), digest='sha256:' + t.delivery.sha(content))
        self.data[row['id']] = content


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='transport fixture '); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.source = self.root / 'source'; self.source.mkdir()
        (self.source / 'folder').mkdir(); (self.source / 'folder/file with spaces').write_bytes(b'abc' * 100)
        (self.source / 'empty').write_bytes(b''); (self.source / 'tool').write_bytes(b'#!/bin/sh\nexit 0\n')
        (self.source / 'tool').chmod(0o755)
        self.remote = FakeGitHub()
        self.context = dict(repository='example/project', run_id=12, attempt=2, source_commit='a' * 40,
                            workflow='sdk-maintenance.yml', name='sdk-group-linux-aarch64')

    def publish(self, **kwargs):
        options = dict(self.context, root=self.source, paths=['folder', 'empty', 'tool'],
                       job_id=30, transport=self.remote, chunk_bytes=4096)
        options.update(kwargs); return t.publish_bundle(**options)

    def fetch(self, **kwargs):
        options = dict(self.context, output=self.root / 'restored', transport=self.remote)
        options.update(kwargs); return t.fetch_bundle(**options)

    def manifest(self):
        row = next(a for a in self.remote.releases[0]['assets'] if a['name'].startswith('bundle-'))
        return row, json.loads(self.remote.data[row['id']])

    def mutate_manifest(self, action):
        row, value = self.manifest(); action(value)
        self.remote.replace(row['name'], t.archive.encoded(value))

    def test_roundtrip_binds_context_and_preserves_bytes_and_modes(self):
        pointer = self.publish(metadata={'recipe': 'b' * 64})
        self.remote.complete(); receipt = self.fetch(manifest_id=pointer['manifest']['id'],
                                                    manifest_sha256=pointer['manifest']['sha256'])
        self.assertEqual(receipt['pointer'], pointer)
        self.assertEqual(receipt['manifest']['metadata'], {'recipe': 'b' * 64})
        for name in ('folder/file with spaces', 'empty', 'tool'):
            self.assertEqual((self.source / name).read_bytes(), (self.root / 'restored' / name).read_bytes())
        if os.name != 'nt': self.assertEqual(0o755, (self.root / 'restored/tool').stat().st_mode & 0o777)
        self.assertTrue(self.remote.releases[0]['draft']); self.assertTrue(self.remote.releases[0]['prerelease'])
        self.assertEqual('false', self.remote.releases[0]['make_latest'])
        self.assertFalse(any('/actions/artifacts' in str(c) for c in self.remote.calls))

    def test_manifest_uploaded_last_and_identical_retry_performs_no_upload(self):
        first = self.publish(); uploads = [c for c in self.remote.calls if c[0] == 'upload']
        self.assertTrue(uploads[-1][1].startswith('bundle-')); self.assertGreater(len(uploads), 2)
        self.assertEqual(first, self.publish())
        self.assertEqual(uploads, [c for c in self.remote.calls if c[0] == 'upload'])

    def test_partial_response_loss_retains_bytes_and_exact_retry_reconciles(self):
        self.remote.lose_upload = True
        with self.assertRaises(t.delivery.DeliveryError): self.publish()
        self.assertEqual(1, len(self.remote.releases[0]['assets']))
        self.assertFalse(any(x['name'].startswith('bundle-') for x in self.remote.releases[0]['assets']))
        self.publish(); self.remote.complete(); self.fetch()

    def test_changed_bytes_cannot_overwrite_completed_or_partial_bundle(self):
        self.publish(); previous = copy.deepcopy(self.remote.data)
        (self.source / 'empty').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'prior bundle assets'): self.publish()
        self.assertEqual(previous, self.remote.data)

    def test_partial_bundle_is_never_fetchable(self):
        self.remote.lose_upload = True
        with self.assertRaises(t.delivery.DeliveryError): self.publish()
        self.remote.complete()
        with self.assertRaisesRegex(ValueError, 'manifest'): self.fetch()
        self.assertFalse((self.root / 'restored').exists())

    def test_failed_or_running_job_requires_explicit_completed_failure_policy(self):
        self.publish(metadata={'status': 'passed'})
        with self.assertRaisesRegex(ValueError, 'completion'): self.fetch(allow_failed=True)
        self.remote.complete('failure')
        with self.assertRaisesRegex(ValueError, 'completion'): self.fetch()
        result = self.fetch(allow_failed=True)
        self.assertEqual('failure', result['producer']['conclusion'])

    def test_cancelled_job_never_becomes_retained_pass(self):
        self.publish(); self.remote.complete('cancelled')
        with self.assertRaisesRegex(ValueError, 'completion'): self.fetch(allow_failed=True)

    def test_repository_source_attempt_workflow_and_fork_mismatch_fail_before_write(self):
        changes = [('head_sha', 'b' * 40), ('run_attempt', 1), ('path', '.github/workflows/other.yml'),
                   ('head_repository', dict(id=8, full_name='example/project')), ('event', 'pull_request')]
        for key, value in changes:
            with self.subTest(key=key):
                prior = self.remote.run[key]; self.remote.run[key] = value
                with self.assertRaisesRegex(ValueError, 'producer repository'): self.publish()
                self.remote.run[key] = prior
        self.assertFalse(self.remote.releases)

    def test_reusable_caller_workflow_and_unique_runner_resolution(self):
        self.remote.run['path'] = '.github/workflows/_release-latest.yml'
        self.remote.jobs[0]['name'] = 'SDK / produce (linux-aarch64)'
        self.publish(workflow='_release-latest.yml', job_id=None, runner_name='Runner 1')
        self.remote.complete()
        self.fetch(workflow='_release-latest.yml', job_name='SDK / produce (linux-aarch64)')

    def test_canonical_target_name_with_underscore_roundtrips(self):
        name = 'sdk-group-windows-x86_64-2'
        pointer = self.publish(name=name); self.remote.complete()
        self.assertEqual(pointer, self.fetch(name=name)['pointer'])

    def test_ambiguous_runner_and_wrong_explicit_job_fail(self):
        self.remote.jobs.append(dict(self.remote.jobs[0], id=31))
        with self.assertRaisesRegex(ValueError, 'ambiguous'): self.publish(job_id=None, runner_name='Runner 1')
        with self.assertRaisesRegex(ValueError, 'job identity'): self.publish(job_name='other')

    def test_job_inventory_paginates_completely(self):
        self.remote.jobs = [dict(self.remote.jobs[0], id=1000 + i, runner_name='Other ' + str(i)) for i in range(100)] + self.remote.jobs
        self.publish(job_id=None, runner_name='Runner 1')
        self.assertTrue(any('page=2' in str(c) for c in self.remote.calls))

    def test_existing_tag_or_public_release_conflict_is_not_repaired(self):
        self.remote.refs['ci-12-attempt-2'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'tag source'): self.publish()
        self.remote.refs.clear(); self.publish(); self.remote.releases[0]['draft'] = False
        with self.assertRaisesRegex(ValueError, 'lifecycle'): self.publish()

    def test_pinned_manifest_and_exact_job_are_required_when_supplied(self):
        pointer = self.publish(); self.remote.complete()
        for options in ({'manifest_id': pointer['manifest']['id'], 'manifest_sha256': '0' * 64},
                        {'manifest_id': pointer['manifest']['id']}, {'job_id': 31}, {'job_name': 'other'}):
            with self.subTest(options=options), self.assertRaises(ValueError): self.fetch(**options)

    def test_asset_corruption_id_replacement_and_remote_changes_reject(self):
        self.publish(); self.remote.complete(); row = self.remote.releases[0]['assets'][0]
        old = self.remote.data[row['id']]; self.remote.data[row['id']] = b'corrupt'
        with self.assertRaisesRegex(ValueError, 'downloaded asset'): self.fetch()
        self.remote.data[row['id']] = old
        self.remote.on_download = lambda: self.remote.jobs[0].update(name='changed')
        with self.assertRaisesRegex(ValueError, 'producer identity'): self.fetch()
        self.assertFalse((self.root / 'restored').exists())

    def test_changed_chunk_identity_and_extra_owned_chunk_reject(self):
        self.publish(); self.remote.complete(); row = self.remote.releases[0]['assets'][0]
        row['id'] += 10000
        with self.assertRaisesRegex(ValueError, 'complete declared'): self.fetch()
        row['id'] -= 10000
        extra = dict(row, id=9999, name=t._prefix(self.context['name']) + 'unexpected')
        self.remote.releases[0]['assets'].append(extra)
        with self.assertRaisesRegex(ValueError, 'complete declared'): self.fetch()

    def test_parallel_other_bundle_does_not_invalidate_this_inventory(self):
        self.publish()
        self.remote.releases[0]['assets'].append(dict(id=9999, name=t._prefix('other') + 'uploading', state='starter'))
        self.remote.complete(); self.fetch()

    def test_two_jobs_reconcile_concurrent_store_creation_and_keep_separate_bundles(self):
        self.remote.jobs.append(dict(self.remote.jobs[0], id=31, runner_id=91,
                                     runner_name='Runner 2', name='proof'))
        original = self.remote.json; interleaved = []; entered = False
        def interleave(endpoint, **kwargs):
            nonlocal entered
            if endpoint.endswith('/git/refs') and kwargs.get('method') == 'POST' and not entered:
                entered = True
                # Both publishers observed no tag/release; job 31 wins both creates.
                interleaved.append(self.publish(name='proof', job_id=31, paths=['tool']))
            return original(endpoint, **kwargs)
        with patch.object(self.remote, 'json', side_effect=interleave):
            first = self.publish()
        self.assertEqual(1, len(self.remote.refs)); self.assertEqual(1, len(self.remote.releases))
        self.assertEqual(first['release_id'], interleaved[0]['release_id'])
        self.assertNotEqual(first['manifest']['id'], interleaved[0]['manifest']['id'])
        self.assertEqual(2, len([c for c in self.remote.calls if c == ('POST', 'repos/example/project/git/refs')]))
        self.assertEqual(2, len([c for c in self.remote.calls if c == ('POST', 'repos/example/project/releases')]))
        for job in self.remote.jobs: job.update(status='completed', conclusion='success')
        one = self.fetch(); two = self.fetch(name='proof', job_id=31, output=self.root / 'proof')
        self.assertEqual(30, one['producer']['id']); self.assertEqual(31, two['producer']['id'])
        self.assertEqual(['tool'], list(two['manifest']['files']))
        self.assertEqual((self.root / 'restored/tool').read_bytes(), (self.root / 'proof/tool').read_bytes())

    def test_manifest_context_types_and_metadata_bounds_are_strict(self):
        self.publish(); self.remote.complete(); row, base = self.manifest()
        edits = [lambda v:v.update(attempt=True), lambda v:v.update(repository_id=True),
                 lambda v:v.update(release_id=True), lambda v:v['producer'].update(id=True),
                 lambda v:v['producer'].update(runner_id=True),
                 lambda v:v.update(metadata={'oversized': 'x' * 65536})]
        for edit in edits:
            with self.subTest(edit=edit):
                value = copy.deepcopy(base); edit(value)
                self.remote.replace(row['name'], t.archive.encoded(value))
                with self.assertRaisesRegex(ValueError, 'provenance'): self.fetch()

    def test_unsafe_input_paths_and_missing_files_fail_before_remote_write(self):
        for value in ('../tool', '/tool', 'folder/../tool', 'folder\\tool', 'C:tool', 'CON', 'folder//tool'):
            with self.subTest(value=value), self.assertRaises(ValueError): self.publish(paths=[value])
        with self.assertRaises(FileNotFoundError): self.publish(paths=['missing'])
        with self.assertRaisesRegex(ValueError, 'empty'): self.publish(paths=['missing'], allow_missing=True)
        self.assertFalse(self.remote.releases)

    def test_missing_diagnostic_path_and_overlapping_selection_are_explicit(self):
        self.publish(paths=['missing', 'folder', 'folder/file with spaces'], allow_missing=True)
        self.remote.complete(); result = self.fetch()
        self.assertEqual(['folder/file with spaces'], list(result['manifest']['files']))

    def test_links_and_nonregular_inputs_reject(self):
        original = Path.lstat
        for mode, attributes in ((stat.S_IFLNK | 0o777, 0), (stat.S_IFIFO | 0o644, 0),
                                 (stat.S_IFREG | 0o4755, 0), (stat.S_IFREG | 0o644, 0x400)):
            with self.subTest(mode=mode, attributes=attributes):
                def observed(path, *args, **kwargs):
                    if path == self.source / 'tool':
                        return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                    return original(path, *args, **kwargs)
                with patch.object(Path, 'lstat', observed), self.assertRaisesRegex(ValueError, 'ordinary'):
                    self.publish()
        self.assertFalse(self.remote.releases)

    def test_manifest_rejects_path_aliases_traversal_mode_and_file_parent(self):
        self.publish(); self.remote.complete(); row, base = self.manifest()
        edits = [lambda v:v['files'].update({'../bad': next(iter(v['files'].values()))}),
                 lambda v:v['files'].update({'Folder/new': next(iter(v['files'].values()))}),
                 lambda v:v['files'].update({'folder': next(iter(v['files'].values()))}),
                 lambda v:v['files']['tool'].update(mode=0o4755),
                 lambda v:v.update(unknown=True)]
        for edit in edits:
            with self.subTest(edit=edit):
                value = copy.deepcopy(base); edit(value); self.remote.replace(row['name'], t.archive.encoded(value))
                with self.assertRaises(ValueError): self.fetch()

    def test_tar_links_duplicate_missing_and_unexpected_files_reject(self):
        files = {'file': dict(size=1, mode=0o644, sha256=hashlib.sha256(b'x').hexdigest())}
        for mode in ('link', 'duplicate', 'missing', 'extra', 'bad-bytes'):
            with self.subTest(mode=mode):
                path = self.root / (mode + '.tar')
                with tarfile.open(path, 'w') as stream:
                    if mode == 'link':
                        info = tarfile.TarInfo('file'); info.type = tarfile.SYMTYPE; info.linkname = '../elsewhere'; stream.addfile(info)
                    elif mode != 'missing':
                        for name in (['file', 'file'] if mode == 'duplicate' else ['file', 'extra'] if mode == 'extra' else ['file']):
                            info = tarfile.TarInfo(name); info.size = 1; info.mode = 0o644
                            stream.addfile(info, io.BytesIO(b'y' if mode == 'bad-bytes' else b'x'))
                output = self.root / mode; output.mkdir()
                with self.assertRaises(ValueError): t._extract(path, output, files)

    def test_input_mutation_prevents_commit_marker(self):
        original = self.remote.upload
        def upload(tag, path):
            original(tag, path); (self.source / 'empty').write_bytes(b'changed')
        with patch.object(self.remote, 'upload', side_effect=upload):
            with self.assertRaisesRegex(ValueError, 'input changed'): self.publish()
        self.assertFalse(any(a['name'].startswith('bundle-') for a in self.remote.releases[0]['assets']))

    def test_existing_destination_is_never_replaced(self):
        self.publish(); self.remote.complete(); output = self.root / 'restored'; output.mkdir(); (output / 'owned').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'must be new'): self.fetch()
        self.assertEqual('keep', (output / 'owned').read_text())

    def test_large_payload_uses_release_chunks_and_reconstructs_exact_bytes(self):
        data = bytes(range(256)) * 8193
        (self.source / 'large.bin').write_bytes(data)
        self.publish(paths=['large.bin'], chunk_bytes=65536)
        self.remote.complete(); result = self.fetch()
        self.assertEqual(data, (self.root / 'restored/large.bin').read_bytes())
        self.assertGreater(len(result['manifest']['archive']['parts']), 30)
        self.assertTrue(all(p['size'] <= 65536 for p in result['manifest']['archive']['parts']))
        self.assertFalse(any('actions/artifacts' in str(c) or 'upload-artifact' in str(c) for c in self.remote.calls))

    def test_lost_manifest_response_reconciles_without_overwrite(self):
        original = self.remote.upload
        def upload(tag, path):
            if path.name.startswith('bundle-'): self.remote.lose_upload = True
            original(tag, path)
        with patch.object(self.remote, 'upload', side_effect=upload):
            with self.assertRaises(t.delivery.DeliveryError): self.publish()
        uploads = len([c for c in self.remote.calls if c[0] == 'upload'])
        self.publish()
        self.assertEqual(uploads, len([c for c in self.remote.calls if c[0] == 'upload']))
        self.remote.complete(); self.fetch()

    def test_created_draft_visibility_is_reconciled_with_reads_only(self):
        original = self.remote.pages; hidden = 3
        def delayed(endpoint):
            nonlocal hidden
            if endpoint.endswith('/releases?per_page=100') and self.remote.releases and hidden:
                hidden -= 1
                return []
            return original(endpoint)
        with patch.object(self.remote, 'pages', side_effect=delayed), patch.object(t.time, 'sleep') as sleep:
            self.publish()
        self.assertEqual(0, hidden); self.assertEqual(3, sleep.call_count)
        self.assertEqual(1, len([c for c in self.remote.calls if c == ('POST', 'repos/example/project/releases')]))
        self.remote.complete(); self.fetch()

    def test_unobserved_created_draft_fails_without_repeating_mutation(self):
        original = self.remote.pages
        def hidden(endpoint):
            if endpoint.endswith('/releases?per_page=100'): return []
            return original(endpoint)
        with patch.object(self.remote, 'pages', side_effect=hidden), patch.object(t.time, 'sleep'), \
                self.assertRaisesRegex(ValueError, 'not visible'):
            self.publish()
        self.assertEqual(1, len(self.remote.releases))
        self.assertEqual(1, len([c for c in self.remote.calls if c == ('POST', 'repos/example/project/releases')]))
        self.assertFalse(self.remote.releases[0]['assets'])

    def test_manifest_identity_replacement_after_upload_is_rejected(self):
        original = t._put
        def replaced(*args, **kwargs):
            row = original(*args, **kwargs)
            if row['name'].startswith('bundle-'):
                remote_row = next(a for a in self.remote.releases[0]['assets'] if a['id'] == row['id'])
                old_id = remote_row['id']; remote_row['id'] += 10000
                self.remote.data[remote_row['id']] = self.remote.data[old_id]
            return row
        with patch.object(t, '_put', side_effect=replaced), self.assertRaisesRegex(ValueError, 'after commit marker'):
            self.publish()

    def test_transport_tag_change_after_manifest_upload_is_rejected(self):
        original = self.remote.upload
        def changed(tag, path):
            original(tag, path)
            if path.name.startswith('bundle-'): self.remote.refs[tag] = 'b' * 40
        with patch.object(self.remote, 'upload', side_effect=changed), self.assertRaisesRegex(ValueError, 'lifecycle'):
            self.publish()

    def test_chunk_count_limit_is_checked_before_any_remote_mutation(self):
        with self.assertRaisesRegex(ValueError, 'too many bounded chunks'): self.publish(chunk_bytes=1)
        self.assertFalse(self.remote.releases)
        self.assertFalse(self.remote.refs)

    def test_small_chunk_reconstruction_preserves_complete_archive_hash(self):
        self.publish(chunk_bytes=1024); self.remote.complete(); result = self.fetch()
        parts = result['manifest']['archive']['parts']; self.assertGreater(len(parts), 2)
        self.assertEqual(list(range(len(parts))), [int(p['name'][len(t._prefix(self.context['name'])):][:4]) for p in parts])


if __name__ == '__main__': unittest.main()
