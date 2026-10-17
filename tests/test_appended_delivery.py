"""Offline appended delivery: fake transport, immutable subjects, no producers."""
import copy
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_delivery as delivery
import appended_release as composition
import dependency_archive as archive
import test_appended_release as fixtures
from test_github_release import FakeGitHub
import test_appended_qualification as qualification_fixtures


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReleaseTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.prepared = self.fixture.prepare()
        self.candidate = self.root / 'candidate'
        self.pin = self.prepared['candidate_sha256']
        self.remote = FakeGitHub()
        self.application_commit = 'a' * 40
        self.packager_commit = 'b' * 40
        self.identity = delivery.delivery_identity(self.candidate, self.pin, 'example/project', 'app-v2',
            self.application_commit, self.packager_commit, 'publication-2')

    def publish(self, **changes):
        return delivery.publish_candidate('example/project', 'app-v2', self.candidate, self.pin,
            self.application_commit, self.packager_commit, 'publication-2', transport=self.remote, **changes)

    def policy(self):
        rules = qualification_fixtures.QualificationTests().new_policy()
        rules['profiles']['web'] = rules['profiles'].pop('synthetic')
        path = self.root / 'policy.json'; path.write_bytes(archive.encoded(rules))
        return path

    def promote(self, **changes):
        return delivery.promote('example/project', 'app-v2', self.candidate, self.identity, self.policy(),
            'web', 'qualification-1', 1, 'c' * 64, transport=self.remote, **changes)

    def test_identity_preserves_old_kernel_and_separate_downstream_commits(self):
        value = self.identity
        self.assertEqual(value['kind'], 'foundation-appended-delivery')
        self.assertEqual(value['application_source_commit'], self.application_commit)
        self.assertEqual(value['packager_commit'], self.packager_commit)
        self.assertEqual(value['tag_commit'], self.packager_commit)
        self.assertFalse(value['experiment'])
        original = value['kernels'][0]
        self.assertEqual(original['provenance'], self.fixture.descriptor['provenance'])
        selection = delivery._load(self.candidate / 'selection.json')['kernels'][0]
        for name in ('id', 'descriptor', 'original_source', 'recovery', 'evidence'):
            self.assertEqual(original[name], selection[name])
        candidate = composition.verify_candidate(self.candidate, self.pin)
        self.assertEqual(candidate['qualification'], 'incomplete')
        self.assertFalse(candidate['publication_eligible'])
        self.assertEqual(set(value['files']), set(candidate['files']) | {'candidate.json'})
        self.assertEqual(len({row['asset'].casefold() for row in value['files'].values()}), len(value['files']))

    def test_plan_only_reads_complete_subject_without_transport_or_processes(self):
        with self.fixture.forbid_processes():
            result = self.publish()
        self.assertFalse(result['execute'])
        self.assertEqual(result['delivery'], self.identity)
        self.assertFalse(self.remote.calls)

    def test_cli_defaults_to_exact_offline_plan(self):
        with self.fixture.forbid_processes(), patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(delivery.main(['publish-candidate', '--input', str(self.candidate),
                '--candidate-sha256', self.pin, '--repository', 'example/project', '--tag', 'app-v2',
                '--application-source-commit', self.application_commit, '--packager-commit', self.packager_commit,
                '--publication-id', 'publication-2']), 0)
        result = delivery.github.parse(output.getvalue())
        self.assertFalse(result['execute'])
        self.assertEqual(result['delivery'], self.identity)

    def test_delivery_json_allows_finite_timings_and_rejects_ambiguous_values(self):
        path = self.root / 'observations.json'; path.write_text('{"seconds": 0.01}')
        self.assertEqual(delivery._load(path), {'seconds': 0.01})
        for raw in ('{"seconds": NaN}', '{"seconds": 1e999}', '{"id": 1, "id": 2}'):
            path.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                delivery._load(path)

    def test_asset_mapping_distinguishes_equal_basenames(self):
        self.assertNotEqual(delivery._asset('inputs/one/descriptor.json'),
                            delivery._asset('inputs/two/descriptor.json'))

    def test_frozen_delivery_preserves_json_types(self):
        changed = copy.deepcopy(self.identity); changed['schema_version'] = True
        with self.assertRaisesRegex(ValueError, 'typed composition subject'):
            delivery.validate_delivery(changed, self.candidate)

    def test_incomplete_or_tampered_subject_fails_before_any_remote_read(self):
        (self.candidate / 'selection.json').write_text('{}')
        with self.assertRaises(ValueError):
            self.publish(execute=True)
        self.assertFalse(self.remote.calls)

    def test_invented_ready_fields_never_turn_candidate_into_qualification(self):
        path = self.candidate / 'candidate.json'
        candidate = delivery._load(path)
        candidate.update(qualification='passed', publication_eligible=True)
        path.write_bytes(archive.encoded(candidate))
        with self.assertRaises(ValueError):
            delivery.delivery_identity(self.candidate, archive.digest(path), 'example/project', 'app-v2',
                self.application_commit, self.packager_commit, 'publication-2')

    def test_forged_upstream_or_downstream_identity_fails_full_validation(self):
        for field, value in (('application_source_commit', 'c' * 40), ('kernels', []),
                             ('composition_sha256', 'd' * 64), ('tag_commit', self.application_commit)):
            modified = copy.deepcopy(self.identity); modified[field] = value
            # Source/packager commits are caller declarations. Changing source
            # commit requires a new full delivery identity with the same subject;
            # all other retained fields must still reproduce exactly.
            if field == 'application_source_commit':
                modified['application_source'] = {'sha256': '0' * 64}
            with self.subTest(field=field), self.assertRaises(ValueError):
                delivery.validate_delivery(modified, self.candidate)

    def test_publish_reads_back_every_asset_then_publishes_only_prerelease(self):
        with self.fixture.forbid_processes():
            result = self.publish(execute=True)
        self.assertTrue(result['execute'])
        row = self.remote.releases[0]
        self.assertFalse(row['draft']); self.assertTrue(row['prerelease'])
        self.assertIsNone(self.remote.latest)
        self.assertEqual(self.remote.refs, {'app-v2': self.packager_commit})
        expected = {item['asset'] for item in self.identity['files'].values()} | {delivery.DESCRIPTOR}
        self.assertEqual({item['name'] for item in row['assets']}, expected)
        transition = next(index for index, call in enumerate(self.remote.calls) if call[0] == 'PATCH')
        before = self.remote.calls[:transition]
        self.assertEqual(sum(call[0] == 'download' for call in before), len(expected))
        for call in self.remote.calls:
            if call[0] in ('POST', 'PATCH') and '/releases' in call[1]:
                self.assertEqual(call[2]['make_latest'], 'false')
        self.assertFalse(delivery._load(self.candidate / 'candidate.json')['publication_eligible'])

    def test_existing_tag_is_preserved_without_mutation(self):
        self.remote.refs['app-v2'] = 'e' * 40
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.publish(execute=True)
        self.assertFalse(self.remote.mutations)
        self.assertEqual(self.remote.refs['app-v2'], 'e' * 40)

    def test_partial_upload_is_uncertain_and_never_implicitly_replayed(self):
        self.remote.fail_upload = next(iter(self.identity['files'].values()))['asset']
        with self.assertRaises(ValueError) as raised:
            self.publish(execute=True)
        self.assertTrue(raised.exception.uncertain)
        self.assertTrue(self.remote.releases[0]['draft'])
        self.assertFalse(any(call[0] == 'PATCH' for call in self.remote.calls))
        before = copy.deepcopy(self.remote.releases)
        self.remote.calls.clear()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.publish(execute=True)
        self.assertEqual(self.remote.releases, before)
        self.assertFalse(self.remote.mutations)

    def test_changed_readback_bytes_keep_draft_unpublished(self):
        original = self.remote.download
        def corrupt(asset_id, path):
            original(asset_id, path)
            Path(path).write_bytes(Path(path).read_bytes() + b'corrupt')
        self.remote.download = corrupt
        with self.assertRaisesRegex(ValueError, 'downloaded asset bytes differ'):
            self.publish(execute=True)
        self.assertTrue(self.remote.releases[0]['draft'])
        self.assertFalse(any(call[0] == 'PATCH' for call in self.remote.calls))

    def test_remote_extra_assets_or_partial_certificate_attempt_block_verification(self):
        self.publish(execute=True)
        for name in ('unexpected.json', 'appended-certification-run1-attempt-1.json'):
            path = self.root / name; path.write_text('{}')
            self.remote.upload('app-v2', path)
            with self.subTest(name=name), self.assertRaises(ValueError):
                delivery.verified_remote(delivery.github.Remote('example/project', self.remote),
                                         self.identity, self.candidate)
            row = self.remote.releases[0]
            row['assets'] = [asset for asset in row['assets'] if asset['name'] != name]

    def test_qualifying_status_without_external_complete_certificate_cannot_promote(self):
        self.publish(execute=True); self.remote.calls.clear()
        with self.assertRaisesRegex(ValueError, 'certificate attempt is absent'):
            self.promote(execute=True)
        self.assertFalse(self.remote.mutations)
        self.assertTrue(self.remote.releases[0]['prerelease'])
        self.assertIsNone(self.remote.latest)

    def test_promotion_plan_is_offline_and_experiments_fail_before_transport(self):
        self.assertFalse(self.promote()['execute'])
        self.assertFalse(self.remote.calls)
        experiment = delivery.delivery_identity(self.candidate, self.pin, 'example/project', 'app-v2',
            self.application_commit, self.packager_commit, 'publication-2', True)
        with self.assertRaisesRegex(ValueError, 'ordinary downstream'):
            delivery.promote('example/project', 'app-v2', self.candidate, experiment, self.policy(), 'web',
                             'qualification-1', 1, 'c' * 64, execute=True, transport=self.remote)
        self.assertFalse(self.remote.calls)

    def test_invalid_current_policy_cannot_produce_a_promotion_plan(self):
        path = self.root / 'invalid-policy.json'; path.write_text('{}')
        with self.assertRaises(ValueError):
            delivery.promote('example/project', 'app-v2', self.candidate, self.identity, path,
                'web', 'qualification-1', 1, 'c' * 64, transport=self.remote)
        self.assertFalse(self.remote.calls)

    def test_certificate_envelope_for_other_delivery_is_rejected_before_proof_acceptance(self):
        self.publish(execute=True)
        stem = 'appended-certification-qualification-1-attempt-1'
        envelope = {'schema_version': 1, 'kind': 'foundation-appended-certificate-attempt',
            'delivery_sha256': '0' * 64, 'run_id': 'qualification-1', 'attempt': 1, 'profile': 'web',
            'bundle': stem + '.tar.gz', 'bundle_sha256': '1' * 64, 'certificate_sha256': 'c' * 64,
            'subject': {}, 'status': 'passed', 'eligible_for_publication': True,
            'eligible_for_promotion': True, 'experiment': False}
        path = self.root / (stem + '.json'); path.write_bytes(archive.encoded(envelope))
        bundle = self.root / (stem + '.tar.gz'); bundle.write_bytes(b'not accepted')
        self.remote.upload('app-v2', bundle); self.remote.upload('app-v2', path)
        self.remote.calls.clear()
        with self.assertRaisesRegex(ValueError, 'another delivery'):
            self.promote(execute=True)
        self.assertFalse(self.remote.mutations)


class CertificateDeliveryTests(unittest.TestCase):
    """Real certifier over inert fixture receipts, never actual qualification."""
    def setUp(self):
        self.fixture = qualification_fixtures.QualificationTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.candidate, self.pin = self.fixture.candidate, self.fixture.pin
        self.policy = self.root / 'current-policy.json'
        self.plan = self.root / 'composition-plan.json'
        self.certificate = self.root / 'composition-certificate.json'
        self.frozen = self.fixture.freeze()
        self.reports = self.fixture.reports(self.frozen)
        self.document = self.fixture.certify(self.frozen, self.reports)
        self.write_documents()
        self.identity = delivery.delivery_identity(self.candidate, self.pin, 'example/project', 'app-v2',
                                                   'a' * 40, 'b' * 40, 'publication-2')
        self.remote = FakeGitHub()

    def write_documents(self):
        qualification_fixtures.document(self.policy, self.fixture.policy)
        qualification_fixtures.document(self.plan, self.frozen)
        qualification_fixtures.document(self.certificate, self.document)

    def publish(self):
        return delivery.publish_candidate('example/project', 'app-v2', self.candidate, self.pin,
            'a' * 40, 'b' * 40, 'publication-2', execute=True, transport=self.remote)

    def attach(self, **changes):
        return delivery.attach_certificate('example/project', 'app-v2', self.candidate, self.identity,
            self.certificate, self.plan, self.policy, 'synthetic', self.reports, 1,
            evidence_root=self.root, transport=self.remote, **changes)

    def promote(self, **changes):
        return delivery.promote('example/project', 'app-v2', self.candidate, self.identity, self.policy,
            'synthetic', 'synthetic-run', 1, archive.digest(self.certificate), transport=self.remote, **changes)

    def test_complete_external_attempt_reproduces_and_promotes_exact_remote_subject(self):
        original = composition._files(self.candidate)
        planned = self.attach()
        self.assertFalse(planned['execute']); self.assertFalse(self.remote.calls)
        self.publish()
        previous = copy.deepcopy(self.remote.releases[0]['assets'])
        attached = self.attach(execute=True)
        self.assertTrue(attached['execute']); self.assertIsNone(self.remote.latest)
        self.assertEqual(self.remote.releases[0]['assets'][:len(previous)], previous)
        self.assertTrue(self.promote(execute=True)['latest'])
        self.assertEqual(self.remote.latest, self.remote.releases[0]['id'])
        self.assertFalse(self.remote.releases[0]['prerelease'])
        self.assertEqual(composition._files(self.candidate), original)
        self.assertEqual(self.document['kernel_evidence'], self.fixture.certify(self.frozen, self.reports)['kernel_evidence'])
        self.assertFalse(delivery._load(self.candidate / 'candidate.json')['publication_eligible'])

    def test_bundle_keeps_frozen_scenario_input_outside_report_evidence(self):
        scenario = self.root / 'scenarios' / 'runtime.json'
        qualification_fixtures.document(scenario, {'fixture': 'retained scenario'})
        row = next(row for row in self.fixture.policy['profiles']['synthetic']['checks'] if row['id'] == 'runtime')
        row['scenario'] = qualification_fixtures.pinned(scenario, self.root)
        self.frozen = self.fixture.freeze()
        self.reports = self.fixture.reports(self.frozen, 'scenario-reports')
        report = next(path for path in self.reports if delivery._load(path)['check'] == 'runtime')
        receipt = delivery._load(report.parent / 'qualification.json')
        receipt['details']['scenario_sha256'] = row['scenario']['sha256']
        qualification_fixtures.document(report.parent / 'qualification.json', receipt)
        self.fixture.refresh_report(report)
        self.document = self.fixture.certify(self.frozen, self.reports)
        self.write_documents()
        output = self.root / 'scenario-bundle'; output.mkdir()
        envelope, path, bundle = delivery.bundle_certificate(self.candidate, self.identity, self.certificate,
            self.plan, self.policy, 'synthetic', self.reports, 1, output, evidence_root=self.root)
        self.assertEqual((output / 'contents/evidence/scenarios/runtime.json').read_bytes(), scenario.read_bytes())
        self.assertEqual(envelope['certificate_sha256'], archive.digest(self.certificate))

    def test_bundle_outputs_never_overwrite_existing_attempt_files(self):
        stem = 'appended-certification-synthetic-run-attempt-1'
        for suffix in ('.json', '.tar.gz'):
            output = self.root / ('existing-' + suffix.removeprefix('.')); output.mkdir()
            existing = output / (stem + suffix); existing.write_bytes(b'foreign original bytes')
            with self.subTest(suffix=suffix), self.assertRaises(FileExistsError):
                delivery.bundle_certificate(self.candidate, self.identity, self.certificate, self.plan,
                    self.policy, 'synthetic', self.reports, 1, output, evidence_root=self.root)
            self.assertEqual(existing.read_bytes(), b'foreign original bytes')

    def test_certificate_output_cannot_mutate_immutable_subject(self):
        before = composition._files(self.candidate)
        with self.assertRaisesRegex(ValueError, 'outside the immutable composition subject'):
            delivery.bundle_certificate(self.candidate, self.identity, self.certificate, self.plan,
                self.policy, 'synthetic', self.reports, 1, self.candidate, evidence_root=self.root)
        self.assertEqual(composition._files(self.candidate), before)

    def test_changed_proof_or_policy_blocks_attachment_before_remote_reads(self):
        self.fixture.proof_path.write_bytes(self.fixture.proof_path.read_bytes() + b'changed')
        with self.assertRaises(ValueError):
            self.attach(execute=True)
        self.assertFalse(self.remote.calls)

    def test_saved_certificate_preserves_json_types_before_any_remote_read(self):
        for key, value in (('schema_version', True), ('eligible_for_publication', 1),
                           ('experiment', 0), ('attempt', True)):
            changed = copy.deepcopy(self.document); changed[key] = value
            qualification_fixtures.document(self.certificate, changed)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.attach(execute=True)
            self.assertFalse(self.remote.calls)

    def test_remote_certificate_envelope_preserves_json_boolean_types(self):
        self.publish(); attached = self.attach(execute=True)
        envelope_name = 'appended-certification-synthetic-run-attempt-1.json'
        changed = copy.deepcopy(attached['certificate']); changed['eligible_for_promotion'] = 1
        self.remote.replace_asset(envelope_name, archive.encoded(changed))
        self.remote.calls.clear()
        with self.assertRaisesRegex(ValueError, 'envelope differs'):
            self.promote(execute=True)
        self.assertFalse(self.remote.mutations)
        self.assertIsNone(self.remote.latest)

    def test_attempt_is_append_only_and_partial_upload_needs_reconciliation(self):
        self.publish()
        self.remote.fail_upload = 'appended-certification-synthetic-run-attempt-1.tar.gz'
        with self.assertRaises(ValueError) as raised:
            self.attach(execute=True)
        self.assertTrue(raised.exception.uncertain)
        before = copy.deepcopy(self.remote.releases)
        self.remote.fail_upload = None; self.remote.calls.clear()
        with self.assertRaisesRegex(ValueError, 'partial composition certificate'):
            self.attach(execute=True)
        self.assertEqual(self.remote.releases, before)
        self.assertFalse(self.remote.mutations)

    def test_second_attachment_cannot_overwrite_completed_attempt(self):
        self.publish(); self.attach(execute=True)
        before = copy.deepcopy(self.remote.releases); self.remote.calls.clear()
        with self.assertRaisesRegex(ValueError, 'attempt exists'):
            self.attach(execute=True)
        self.assertFalse(self.remote.mutations)
        self.assertEqual(self.remote.releases, before)

    def test_changed_remote_bundle_is_rejected_against_local_uploaded_bytes(self):
        self.publish()
        original = self.remote.upload
        def changed_upload(tag, path):
            original(tag, path)
            if Path(path).name == 'appended-certification-synthetic-run-attempt-1.json':
                self.remote.replace_asset('appended-certification-synthetic-run-attempt-1.tar.gz', b'changed upload')
        self.remote.upload = changed_upload
        with self.assertRaisesRegex(ValueError, 'remote asset differs'):
            self.attach(execute=True)
        self.assertTrue(self.remote.releases[0]['prerelease'])
        self.assertIsNone(self.remote.latest)

    def test_changed_current_policy_prevents_promotion(self):
        self.publish(); self.attach(execute=True)
        rules = copy.deepcopy(self.fixture.policy)
        rules['profiles']['synthetic']['description'] += ' revised'
        qualification_fixtures.document(self.policy, rules)
        self.remote.calls.clear()
        with self.assertRaisesRegex(ValueError, 'current composition policy differs'):
            self.promote(execute=True)
        self.assertFalse(self.remote.mutations)
        self.assertIsNone(self.remote.latest)

    def test_missing_retained_nested_evidence_cannot_be_hidden_by_new_bundle_hash(self):
        self.publish(); attached = self.attach(execute=True)
        envelope_name = 'appended-certification-synthetic-run-attempt-1.json'
        bundle_name = 'appended-certification-synthetic-run-attempt-1.tar.gz'
        envelope_row = next(row for row in self.remote.releases[0]['assets'] if row['name'] == envelope_name)
        bundle_row = next(row for row in self.remote.releases[0]['assets'] if row['name'] == bundle_name)
        root = self.root / 'tampered-bundle'; root.mkdir()
        bundled = root / 'original.tar.gz'; bundled.write_bytes(self.remote.data[bundle_row['id']])
        tree = archive.extract(bundled, root / 'contents')
        (tree / 'evidence/fresh-evidence/runtime/console.log').unlink()
        metadata = delivery._load(tree / 'bundle.json')
        metadata['files'] = archive.file_inventory(tree, exclude=('bundle.json',))
        qualification_fixtures.document(tree / 'bundle.json', metadata)
        changed = root / 'changed.tar.gz'; archive.archive_tree(tree, changed)
        self.remote.replace_asset(bundle_name, changed.read_bytes())
        envelope = copy.deepcopy(attached['certificate']); envelope['bundle_sha256'] = archive.digest(changed)
        self.remote.replace_asset(envelope_name, archive.encoded(envelope))
        self.remote.calls.clear()
        with self.assertRaises((ValueError, OSError)):
            self.promote(execute=True)
        self.assertFalse(self.remote.mutations)
        self.assertIsNone(self.remote.latest)

    def test_latest_postcheck_failure_retains_uncertain_remote_outcome(self):
        self.publish(); self.attach(execute=True)
        original = self.remote.json
        def no_latest(endpoint, **kwargs):
            if endpoint.endswith('/releases/latest') and self.remote.latest is not None:
                value = copy.deepcopy(self.remote.releases[0]); value['id'] += 100
                return value
            return original(endpoint, **kwargs)
        self.remote.json = no_latest
        with self.assertRaisesRegex(ValueError, 'Latest does not identify') as raised:
            self.promote(execute=True)
        self.assertTrue(raised.exception.uncertain)


if __name__ == '__main__':
    unittest.main()
