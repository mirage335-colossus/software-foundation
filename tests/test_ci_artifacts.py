"""Bounded Actions evidence must never replace complete validation or fallback."""
import copy
import gzip
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ci_artifacts as artifacts
import ci_transport
import dependency_archive as archive


class EvidenceArtifacts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'; self.source.mkdir()
        (self.source / 'nested').mkdir()
        (self.source / 'nested/test.log').write_text('complete evidence\n' * 100)
        (self.source / 'result.json').write_text('{"passed":true}\n')
        self.context = dict(repository='example/project', run_id=123, attempt=2,
                            source_commit='a' * 40, workflow='certify.yml')
        self.name = 'evidence-batch-linux-source-aabbcc-2'
        self.downloads = self.root / 'downloaded'; self.downloads.mkdir()
        self.env = mock.patch.dict(os.environ, {
            'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'example/project', 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2',
            'GITHUB_SHA': 'a' * 40, 'GITHUB_WORKFLOW_REF': 'example/project/.github/workflows/certify.yml@refs/heads/main',
            artifacts.ROOT_ENV: str(self.downloads)})
        self.env.start(); self.addCleanup(self.env.stop)

    def prepare(self, name=None, **kwargs):
        return artifacts.prepare(**self.context, name=name or self.name, root=self.source,
            paths=['nested', 'result.json'], output=self.root / ('stage-' + str(len(list(self.root.iterdir())))),
            slot=kwargs.pop('slot', 0), job_key='check', runner_name='Hosted Runner 7', **kwargs)

    def stage(self, **kwargs):
        result = self.prepare(**kwargs)
        self.assertEqual(result['transport'], 'actions')
        target = self.downloads / result['artifact_name']
        shutil.copytree(result['path'], target)
        return target

    def fetch(self, **kwargs):
        request = dict(name=self.name, output=self.root / 'unused', **kwargs)
        return artifacts.fetch_local(dict(self.context, name=self.name), request, self.root / 'result')

    def edit_manifest(self, target, callback):
        path = target / 'manifest.json'; value = json.loads(path.read_bytes())
        callback(value); path.write_bytes(archive.encoded(value))

    def replace_archive(self, target, headers):
        stream = io.BytesIO()
        with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|') as output:
                for header, data in headers:
                    output.addfile(header, io.BytesIO(data) if data is not None else None)
        path = target / 'payload.tar.gz'; path.write_bytes(stream.getvalue())
        self.edit_manifest(target, lambda value: value.update(archive=dict(size=path.stat().st_size, sha256=archive.digest(path))))

    def test_deterministic_complete_roundtrip_without_remote_operations(self):
        first = self.stage(metadata={'scope': 'source'})
        second = self.prepare(metadata={'scope': 'source'})
        for name in ('manifest.json', 'payload.tar.gz'):
            self.assertEqual((first / name).read_bytes(), (Path(second['path']) / name).read_bytes())
        with mock.patch.object(ci_transport.delivery, 'Remote', side_effect=AssertionError('unexpected API')):
            result = self.fetch()
        self.assertEqual(result['pointer']['transport'], 'actions')
        self.assertEqual(result['producer'], dict(kind='workflow-needs', trust_basis=artifacts.TRUST_BASIS, job_key='check',
                                                     runner_name='Hosted Runner 7', conclusion='success'))
        self.assertEqual(result['manifest']['metadata'], {'scope': 'source'})
        for name in ('nested/test.log', 'result.json'):
            self.assertEqual((self.root / 'result' / name).read_bytes(), (self.source / name).read_bytes())

    def test_names_have_finite_storage_bound_and_overflow_uses_release(self):
        self.assertEqual(artifacts.MAX_ARTIFACTS, 79)
        self.assertEqual(artifacts.MAX_RUN_BYTES, 370 * artifacts.MIB)
        self.assertLess(artifacts.MAX_RUN_BYTES, 384 * artifacts.MIB)
        for target in artifacts.TARGETS:
            for scope in artifacts.SCOPES:
                name = 'source-' + target + '-' + scope + '-2'
                self.assertIsNotNone(artifacts.slot_for(name, 2))
        for slot in range(48): self.assertEqual(artifacts.slot_for(self.name, 2, slot), 'evidence-' + str(slot).zfill(2))
        for slot in (-1, 48, None, True): self.assertIsNone(artifacts.slot_for(self.name, 2, slot))
        self.assertEqual(self.prepare(slot=48, allow_release_fallback=True)['transport'], 'release')
        self.assertEqual(self.prepare(name='sdk-group-linux-x86_64-2', allow_release_fallback=True)['transport'], 'release')
        self.assertEqual(self.prepare(name='evidence-batch-linux-source-aabbcc-1', allow_release_fallback=True)['transport'], 'release')

    def test_complete_oversize_payload_falls_back_without_truncating_input(self):
        data = os.urandom(artifacts.MAX_BUNDLE_BYTES)
        (self.source / 'nested/test.log').write_bytes(data)
        result = self.prepare(allow_release_fallback=True)
        self.assertEqual(result['transport'], 'release')
        self.assertIn('byte budget', result['reason'])
        self.assertEqual((self.source / 'nested/test.log').read_bytes(), data)
        self.assertFalse(any(self.root.glob('stage-*')))

    def test_expanded_file_and_manifest_budgets_choose_release(self):
        for limit, value in (('MAX_EXPANDED_BYTES', 1), ('MAX_FILES', 1), ('MAX_MANIFEST_BYTES', 1)):
            with self.subTest(limit=limit), mock.patch.object(artifacts, limit, value):
                self.assertEqual(self.prepare(allow_release_fallback=True)['transport'], 'release')
        self.assertTrue((self.source / 'result.json').is_file())

    def test_absent_artifact_fails_without_explicit_release_opt_in(self):
        with self.assertRaisesRegex(ValueError, 'required native artifact'): self.fetch()
        self.stage(name='certificate-2')
        with self.assertRaisesRegex(ValueError, 'required native artifact'): self.fetch()
        with mock.patch.dict(os.environ, {artifacts.FALLBACK_ENV: 'true'}): self.assertIsNone(self.fetch())
        with mock.patch.dict(os.environ, {artifacts.ROOT_ENV: ''}): self.assertIsNone(self.fetch())
        with mock.patch.dict(os.environ, {artifacts.ROOT_ENV: '', artifacts.REQUIRED_ENV: 'true'}):
            with self.assertRaisesRegex(ValueError, 'directory is missing'): self.fetch()

    def test_run_source_workflow_and_attempt_are_not_interchangeable(self):
        target = self.stage()
        original = (target / 'manifest.json').read_bytes()
        for field, value in (('run_id', 124), ('attempt', 3), ('source_commit', 'b' * 40),
                             ('repository', 'other/project'), ('workflow', 'candidate.yml')):
            with self.subTest(field=field):
                (target / 'manifest.json').write_bytes(original)
                self.edit_manifest(target, lambda row: row.update({field: value}))
                with self.assertRaisesRegex(ValueError, 'provenance'): self.fetch()
                self.assertFalse((self.root / 'result').exists())
        with mock.patch.dict(os.environ, {'GITHUB_RUN_ATTEMPT': '3'}):
            with self.assertRaisesRegex(ValueError, 'exact current run'): self.fetch()

    def test_archive_corruption_is_error_never_release_fallback(self):
        target = self.stage(); path = target / 'payload.tar.gz'
        path.write_bytes(path.read_bytes()[:-1] + b'x')
        with self.assertRaisesRegex(ValueError, 'archive bytes'): self.fetch()
        self.assertFalse((self.root / 'result').exists())

    def test_file_hash_is_checked_independently_of_archive_hash(self):
        target = self.stage()
        self.edit_manifest(target, lambda value: value['files']['result.json'].update(sha256='0' * 64))
        with self.assertRaisesRegex(ValueError, 'member bytes'): self.fetch()
        self.assertFalse((self.root / 'result').exists())

    def test_missing_extra_or_nonregular_downloads_are_errors(self):
        target = self.stage(); original = (target / 'manifest.json').read_bytes()
        (target / 'extra').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'only its manifest'): self.fetch()
        (target / 'extra').unlink(); (target / 'manifest.json').unlink()
        with self.assertRaisesRegex(ValueError, 'only its manifest'): self.fetch()
        (target / 'manifest.json').write_bytes(original)
        (target / 'payload.tar.gz').unlink(); (target / 'payload.tar.gz').mkdir()
        with self.assertRaisesRegex(ValueError, 'ordinary'): self.fetch()

    def test_manifest_schema_slots_and_file_inventory_are_strict(self):
        target = self.stage(); original = (target / 'manifest.json').read_bytes()
        mutations = [lambda x: x.update(extra='unknown'), lambda x: x.update(slot='evidence-49'),
                     lambda x: x.update(schema_version=True), lambda x: x['files'].update({'../escape': x['files']['result.json']}),
                     lambda x: x['files']['result.json'].update(size=True), lambda x: x.update(producer={'runner_name': 'x'})]
        for change in mutations:
            (target / 'manifest.json').write_bytes(original); self.edit_manifest(target, change)
            with self.assertRaises(ValueError): self.fetch()
            self.assertFalse((self.root / 'result').exists())

    def test_archive_links_traversal_duplicates_and_missing_members_fail(self):
        target = self.stage()
        for kind in ('link', 'traversal', 'duplicate', 'missing'):
            with self.subTest(kind=kind):
                info = tarfile.TarInfo('result.json'); info.mode = 0o644
                data = (self.source / 'result.json').read_bytes(); info.size = len(data)
                headers = [(info, data)]
                if kind == 'link': info.type = tarfile.SYMTYPE; info.linkname = '../escaped'; info.size = 0; headers = [(info, None)]
                if kind == 'traversal': info.name = '../escaped'
                if kind == 'duplicate': headers.append((copy.copy(info), data))
                self.replace_archive(target, headers)
                with self.assertRaises(ValueError): self.fetch()
                self.assertFalse((self.root / 'result').exists())
                self.assertFalse((self.root / 'escaped').exists())

    def test_rejects_destination_collision_and_release_asset_pins(self):
        self.stage()
        for pins in ({'manifest_id': 1}, {'manifest_sha256': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'release asset pins'): self.fetch(**pins)
        (self.root / 'result').mkdir(); (self.root / 'result/keep').write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'must be new'): self.fetch()
        self.assertEqual((self.root / 'result/keep').read_text(), 'preserve')

    def test_native_trust_is_explicit_and_never_satisfies_rest_pins(self):
        self.stage()
        for pin in (dict(job_name='Qualify Linux'), dict(job_id=99)):
            with self.assertRaisesRegex(ValueError, 'REST producer pins'): self.fetch(**pin)
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}):
            with self.assertRaisesRegex(ValueError, 'executing Actions'): self.fetch()

    def test_failed_evidence_requires_explicit_consumer_and_preserves_outcome(self):
        self.stage(outcome='failure')
        with self.assertRaisesRegex(ValueError, 'failed native producer'): self.fetch()
        result = self.fetch(allow_failed=True)
        self.assertEqual(result['producer']['conclusion'], 'failure')
        self.assertNotIn('id', result['producer'])
        self.assertNotIn('status', result['producer'])

    def test_cli_uses_executing_context_without_any_rest_provenance_calls(self):
        lifecycle = mock.Mock()
        lifecycle.bundle_inputs.return_value = (self.source, ['nested', 'result.json'])
        output = self.root / 'step-output'; output.touch()
        variables = dict(BUNDLE_NAME=self.name, BUNDLE_PATHS='ignored-by-fixture', ARTIFACT_SLOT='0',
                         RUNNER_TEMP=str(self.root), RUNNER_NAME='Hosted Runner 7', GITHUB_OUTPUT=str(output),
                         GITHUB_SERVER_URL='https://github.com', GITHUB_JOB='check', ARTIFACT_PRODUCER_STATUS='success')
        with mock.patch.dict(os.environ, variables), mock.patch.object(artifacts, '_lifecycle', return_value=lifecycle), \
                mock.patch.object(artifacts.delivery, 'Remote', side_effect=AssertionError('unexpected REST')), \
                mock.patch.object(ci_transport, '_producer', side_effect=AssertionError('unexpected jobs query')), \
                mock.patch('builtins.print'):
            artifacts.main(['prepare'])
        manifest = json.loads((self.root / ('foundation-evidence-stage-' + self.name) / 'manifest.json').read_bytes())
        self.assertEqual(manifest['producer'], dict(job_key='check', outcome='success', runner_name='Hosted Runner 7'))
        self.assertEqual(manifest['trust_basis'], artifacts.TRUST_BASIS)
        self.assertIn('transport=actions', output.read_text())

    def test_realistic_certificate_above_old_limit_stays_native(self):
        (self.source / 'nested/test.log').write_bytes(os.urandom(9 * artifacts.MIB))
        result = self.prepare(name='certificate-2')
        self.assertEqual(result['transport'], 'actions')
        self.assertGreater(result['bytes'], 9 * artifacts.MIB)
        self.assertLess(result['bytes'], 16 * artifacts.MIB)

    def test_sdk_archives_are_excluded_and_oversize_does_not_silently_relay(self):
        (self.source / 'nested/sdk-example-binary.tar.gz').write_bytes(b'sdk bytes')
        with self.assertRaisesRegex(ValueError, 'SDK payloads'): self.prepare(name='candidate-2')
        result = self.prepare(name='candidate-2', allow_release_fallback=True)
        self.assertEqual(result['transport'], 'release')
        (self.source / 'nested/sdk-example-binary.tar.gz').unlink()
        with mock.patch.object(artifacts, 'MAX_EXPANDED_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'explicit opt-in'): self.prepare()

    def test_v1_native_manifest_cannot_claim_simplified_provenance(self):
        target = self.stage()
        self.edit_manifest(target, lambda value: value.update(schema_version=1))
        with self.assertRaisesRegex(ValueError, 'provenance'): self.fetch()

    def test_fallback_invokes_complete_existing_release_publication(self):
        lifecycle = mock.Mock()
        with mock.patch.object(artifacts, '_lifecycle', return_value=lifecycle):
            with self.assertRaisesRegex(ValueError, 'not enabled'): artifacts.main(['fallback'])
            with mock.patch.dict(os.environ, {artifacts.FALLBACK_ENV: 'true'}): artifacts.main(['fallback'])
        lifecycle.store_bundle.assert_called_once_with()

    @unittest.skipIf(os.name == 'nt', 'symlink creation needs native Windows privilege qualification')
    def test_symlink_inputs_and_download_parents_are_rejected(self):
        (self.source / 'nested/link').symlink_to(self.source / 'result.json')
        with self.assertRaisesRegex(ValueError, 'ordinary'): self.prepare()
        (self.source / 'nested/link').unlink(); self.stage()
        alias = self.root / 'alias'; alias.symlink_to(self.downloads, target_is_directory=True)
        with mock.patch.dict(os.environ, {artifacts.ROOT_ENV: str(alias)}):
            with self.assertRaisesRegex(ValueError, 'ordinary directories'): self.fetch()


if __name__ == '__main__':
    unittest.main()
