"""Actual signed local channel fixtures and mocked immutable remote lifecycle."""
import copy
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import distribution_release as d
import test_github_release as fixtures


def request():
    return dict(schema_version=1, repository='example/project', application_tag='v1', inventory_sha256='a' * 64,
        profile='fixture', certificate_run='qualification-run', certificate_attempt=1, certificate_sha256='b' * 64,
        target='linux-x86_64', version='1.2.3', package_release=1, sequence=7, valid_days=30,
        trusted_fingerprint='A' * 40, license_files=['share/doc/Foundation/LICENSE'],
        runtime_dependencies={'arch': ['glibc>=2.36'], 'gentoo': ['>=sys-libs/glibc-2.36']}, packager_commit='a' * 40)


def git_fixture(root, algorithm='sha1'):
    root.mkdir(); (root / 'a').mkdir()
    (root / 'a/z').write_bytes(b'checkout source\n'); (root / 'a.c').write_bytes(b'lexical tree order\n')
    (root / 'script').write_bytes(b'#!/bin/sh\nexit 0\n'); (root / 'script').chmod(0o755)
    args = ['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgSign=false']
    subprocess.run([*args, 'init', '--quiet', '--object-format=' + algorithm], check=True, capture_output=True)
    subprocess.run([*args, 'add', '.'], check=True, capture_output=True)
    subprocess.run([*args, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '--quiet', '-m', 'Fixture'], check=True, capture_output=True)
    return subprocess.run([*args, 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()


class InitializationTests(unittest.TestCase):
    def setUp(self):
        self.transport=fixtures.FakeGitHub()
        self.remote=d.delivery.Remote('example/project',self.transport)
        self.tag='distro-fixture';self.commit='a'*40;self.body='exact body'
        self.sleep=patch.object(d.delivery.time,'sleep');self.sleep.start();self.addCleanup(self.sleep.stop)

    def initialize(self):
        return d.initialize_channel(self.remote,self.tag,self.commit,self.body)

    def release_posts(self):
        return [c for c in self.transport.calls if c[:2]==('POST','repos/example/project/releases')]

    def test_orphan_matching_tag_never_authorizes_creation(self):
        self.transport.refs[self.tag]=self.commit
        with self.assertRaisesRegex(ValueError,'not visible'):self.initialize()
        self.assertEqual([],self.release_posts());self.assertFalse(self.transport.releases)

    def test_successful_creation_waits_for_exact_visible_id(self):
        original=self.transport.pages;remaining=3
        def delayed(endpoint):
            nonlocal remaining
            if endpoint.endswith('/releases?per_page=100') and remaining:
                remaining-=1;return []
            return original(endpoint)
        with patch.object(self.transport,'pages',side_effect=delayed):result=self.initialize()
        self.assertEqual(1,result['id']);self.assertEqual(1,len(self.release_posts()))

    def test_uncertain_ref_response_grants_no_creation(self):
        original=self.transport.json
        def lost(endpoint,**kwargs):
            result=original(endpoint,**kwargs)
            if endpoint.endswith('/git/refs') and kwargs.get('method')=='POST':
                raise d.delivery.DeliveryError('uncertain reference creation',True)
            return result
        with patch.object(self.transport,'json',side_effect=lost),self.assertRaisesRegex(ValueError,'not visible'):
            self.initialize()
        self.assertEqual(self.commit,self.transport.refs[self.tag]);self.assertEqual([],self.release_posts())

    def test_lost_creation_response_reconciles_without_second_post(self):
        original=self.transport.json
        def lost(endpoint,**kwargs):
            result=original(endpoint,**kwargs)
            if endpoint.endswith('/releases') and kwargs.get('method')=='POST':
                raise d.delivery.DeliveryError('uncertain draft creation',True)
            return result
        with patch.object(self.transport,'json',side_effect=lost):result=self.initialize()
        self.assertEqual(1,result['id']);self.assertEqual(1,len(self.release_posts()))

    def test_two_initializers_only_atomic_ref_winner_creates_draft(self):
        original=self.remote.change;entered=False;winner=[]
        def race(endpoint,**kwargs):
            nonlocal entered
            if endpoint=='/git/refs' and not entered:
                entered=True;winner.append(self.initialize())
                raise d.delivery.DeliveryError('reference already exists')
            return original(endpoint,**kwargs)
        with patch.object(self.remote,'change',side_effect=race):result=self.initialize()
        self.assertEqual(winner[0]['id'],result['id']);self.assertEqual(1,len(self.release_posts()))

    def test_changed_response_id_or_duplicate_draft_is_rejected(self):
        original=self.transport.json
        def changed(endpoint,**kwargs):
            result=original(endpoint,**kwargs)
            if endpoint.endswith('/releases') and kwargs.get('method')=='POST':result['id']+=100
            return result
        with patch.object(self.transport,'json',side_effect=changed),self.assertRaisesRegex(ValueError,'ID differs'):
            self.initialize()
        self.transport.releases.append(dict(self.transport.releases[0],id=99))
        with self.assertRaisesRegex(ValueError,'duplicate release tags'):self.initialize()
        self.assertFalse(any(c[0]=='upload' for c in self.transport.calls))


class RequestTests(unittest.TestCase):
    def test_workflow_retains_complete_large_notice_inventory(self):
        value = request()
        value['license_files'] = ['share/doc/Foundation/dependencies/' + str(i) + '/COPYING.txt' for i in range(400)]
        raw = json.dumps(value, separators=(',', ':'))
        self.assertGreater(len(raw.encode('utf-8')), 16 * 1024)
        self.assertEqual(value, d.workflow_request(raw))

    def test_workflow_request_exact_byte_bound_precedes_parsing(self):
        raw = json.dumps(request(), separators=(',', ':'))
        bounded = raw + ' ' * (d.MAX_WORKFLOW_REQUEST_BYTES - len(raw.encode('utf-8')))
        self.assertEqual(request(), d.workflow_request(bounded))
        for excessive in (bounded + ' ', 'é' * (d.MAX_WORKFLOW_REQUEST_BYTES // 2 + 1), None):
            with self.subTest(value_type=type(excessive)), patch.object(d.delivery, 'parse', side_effect=AssertionError('must reject before parse')):
                with self.assertRaisesRegex(ValueError, 'input bound'):
                    d.workflow_request(excessive)
        utf8_boundary = 'é' * (d.MAX_WORKFLOW_REQUEST_BYTES // 2)
        with patch.object(d.delivery, 'parse', return_value=request()) as parse:
            self.assertEqual(request(), d.workflow_request(utf8_boundary))
            parse.assert_called_once_with(utf8_boundary)

    def test_workflow_request_preserves_json_and_semantic_validation(self):
        raw = json.dumps(request())
        for invalid in (raw[:-1] + ',"sequence":8}', '{}', json.dumps(dict(request(), sequence=True))):
            with self.subTest(raw=invalid), self.assertRaises(ValueError):
                d.workflow_request(invalid)

    def test_plan_has_no_remote_or_signing_side_effect(self):
        with patch.object(d.delivery, 'Remote', side_effect=AssertionError('no network')):
            result = d.plan(request())
        self.assertFalse(result['execute']); self.assertEqual('distro-1.2.3-x86_64-r1-s7', result['tag'])

    def test_exact_request_rejects_injection_unknown_fields_and_unsupported_targets(self):
        for changes in ({'target': 'windows-x86_64'}, {'version': '1.0;exit'}, {'sequence': True},
                        {'certificate_attempt': 0}, {'extra': 1}, {'repository': 'bad/repo/extra'},
                        {'license_files': ['../file']}, {'runtime_dependencies': {'arch': ['$(x)'], 'gentoo': ['glibc']}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): d.plan(dict(request(), **changes))

    def test_private_key_inside_checkout_or_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); key = root / 'key'; key.write_bytes(b'private')
            with self.assertRaisesRegex(ValueError, 'outside'): d._key_outside(key, root)


@unittest.skipUnless(sys.platform.startswith('linux') and all(shutil.which(x) for x in ('cc', 'dpkg-deb', 'gpg', 'gpgv', 'gpgconf', 'git')),
                     'Linux ELF, Debian package and real signing tools required')
class SignedDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = fixtures.DeliveryTests(); cls.f.setUp(); cls.root = cls.f.root
        cls.addClassCleanup(cls.f.doCleanups)
        # Use a genuine native executable in one real installation root.
        cls.arch = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine().lower(), platform.machine().lower())
        if cls.arch not in ('x86_64', 'aarch64'): raise RuntimeError('unsupported Linux qualification architecture')
        app = cls.root / 'application'; (app / 'share/doc/Foundation').mkdir(parents=True)
        (app / 'share/doc/Foundation/LICENSE').write_bytes(b'Fixture redistribution terms\n')
        c = cls.root / 'main.c'; c.write_text('int main(void) { return 0; }\n')
        subprocess.run(['cc', str(c), '-o', str(app / 'bin/foundation-cli')], check=True)
        wrapper = cls.root / 'wrapper'; wrapper.mkdir(); shutil.copytree(app, wrapper / 'prefix')
        package = cls.root / 'application.tar.gz'; package.unlink(); d.archive.archive_tree(wrapper, package)
        d.archive.write_json(cls.root / 'application.tar.gz.json', d.release.artifact.describe(package))
        cls.f.fixture.spec['artifacts'][0]['sha256'] = d.archive.digest(package)
        d.archive.write_json(cls.f.fixture.spec_path, cls.f.fixture.spec)
        shutil.rmtree(cls.f.directory); d.release.assemble(cls.f.fixture.spec_path, cls.f.fixture.base, cls.f.directory)
        cls.f.delivery = d.delivery.publish_candidate(**cls.f.args)['delivery']; cls.f.publish()
        cls.cert = cls.f.cert(); d.delivery.attach_certificate(**cls.cert, execute=True, transport=cls.f.remote)
        home = cls.root / 'keyhome'; home.mkdir(mode=0o700)
        try:
            d.distro.run('gpg', '--batch', '--homedir', home, '--pinentry-mode', 'loopback', '--passphrase', '',
                        '--quick-generate-key', 'Fixture <fixture@example.invalid>', 'ed25519', 'sign', '1d')
            public = cls.root / 'public.gpg'; public.write_bytes(d.distro.run('gpg', '--batch', '--homedir', home, '--export'))
            cls.trusted = d.apt.fingerprint(public); cls.private = cls.root / 'private.asc'
            cls.private.write_bytes(d.distro.run('gpg', '--batch', '--homedir', home, '--armor', '--export-secret-keys', cls.trusted))
        finally: d.distro.run('gpgconf', '--homedir', home, '--kill', 'all')
        cls.req = dict(request(), trusted_fingerprint=cls.trusted, target='linux-' + cls.arch,
                       inventory_sha256=cls.f.delivery['inventory_sha256'], certificate_sha256=d.archive.digest(cls.cert['certificate']))
        cls.policy = cls.cert['policy']; cls.packaging = cls.root / 'packaging-source.tar.gz'
        cls.checkout = cls.root / 'packaging-checkout'
        cls.req['packager_commit'] = git_fixture(cls.checkout)
        d.source_identity.archive_source(cls.checkout, cls.packaging)
        cls.prepared = cls.root / 'distribution'
        cls.frozen = d.prepare(cls.req, cls.f.directory, cls.f.delivery, cls.policy, cls.packaging, cls.prepared,
                               cls.private, transport=cls.f.remote, packaging_checkout=cls.checkout)
        cls.remote_state = copy.deepcopy(cls.f.remote)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.root); self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name); self.remote = copy.deepcopy(self.remote_state)

    def test_real_signatures_packages_and_source_closure_verify(self):
        value = d.verify(self.prepared, self.policy, self.trusted)
        self.assertEqual(value, self.frozen); self.assertEqual(['core'], value['backends'])
        self.assertTrue((self.prepared / 'Packages').is_file()); self.assertTrue((self.prepared / 'software-foundation.db').is_file())
        self.assertEqual(set(value['retained']), {'application/' + name for name in self.f.delivery['files']} |
            {'delivery.json', 'policy.json', 'packaging-source.tar.gz', 'certification-qualification-run-attempt-1.json', 'certification-qualification-run-attempt-1.tar.gz'})
        for name in value['retained'].values(): self.assertIn(d.archive.digest(self.prepared / name), name)
        with (self.prepared / 'Packages').open() as stream:
            filename = next(line.removeprefix('Filename: ').strip() for line in stream if line.startswith('Filename: '))
        self.assertTrue((self.prepared / filename).is_file())
        self.assertNotIn(self.private.read_bytes(), b''.join(p.read_bytes() for p in self.prepared.iterdir()))

    def test_complete_retained_delivery_requires_terms_even_for_selected_core_target(self):
        manifest = copy.deepcopy(d.release.verify_release(self.f.directory))
        manifest['artifacts'].append(dict(manifest['artifacts'][0], target='windows-x86_64', backends=['fltk']))
        with patch.object(d.release, 'verify_release', return_value=manifest), \
                patch.object(d.distro, 'require_gui_terms', side_effect=ValueError('unresolved terms')) as terms:
            with self.assertRaisesRegex(ValueError, 'terms'):
                d.prepare(self.req, self.f.directory, self.f.delivery, self.policy, self.packaging,
                          self.work / 'terms', self.private, transport=self.remote, packaging_checkout=self.checkout)
        terms.assert_called_once()
        self.assertFalse((self.work / 'terms').exists())

    def test_packaging_commit_proof_rejects_different_bytes_modes_and_commit_object(self):
        proof = self.frozen['packaging_source_proof']
        self.assertEqual(proof, d.verify_source_commit(self.packaging, proof, self.req['packager_commit']))
        changed = copy.deepcopy(proof); changed['commit_object'] = d.base64.b64encode(b'tree ' + b'0' * 40 + b'\n').decode()
        with self.assertRaisesRegex(ValueError, 'Git commit'): d.verify_source_commit(self.packaging, changed, self.req['packager_commit'])
        raw = d.base64.b64decode(proof['commit_object'])
        duplicate = raw.split(b'\n', 1)[0] + b'\n' + raw
        changed = dict(proof, commit_object=d.base64.b64encode(duplicate).decode(),
                       commit=d._git_object('commit', duplicate, 'sha1').hex())
        with self.assertRaisesRegex(ValueError, 'Git commit'): d.verify_source_commit(self.packaging, changed, changed['commit'])
        for mode in ('bytes', 'executable'):
            root = self.work / mode
            shutil.copytree(self.checkout, root)
            if mode == 'bytes': (root / 'a/z').write_bytes(b'substituted source\n')
            else: (root / 'script').chmod(0o644)
            bundled = self.work / (mode + '.tar.gz'); d.source_identity.archive_source(root, bundled)
            with self.assertRaisesRegex(ValueError, 'Git commit'): d.verify_source_commit(bundled, proof, self.req['packager_commit'])
            with self.assertRaisesRegex(ValueError, 'clean'): d.source_commit_proof(root, bundled, self.req['packager_commit'])

    def test_sha256_repository_commit_proof_is_verified_without_checkout(self):
        root = self.work / 'sha256'; commit = git_fixture(root, 'sha256')
        bundled = self.work / 'sha256-source.tar.gz'; d.source_identity.archive_source(root, bundled)
        proof = d.source_commit_proof(root, bundled, commit); shutil.rmtree(root)
        self.assertEqual(proof, d.verify_source_commit(bundled, proof, commit))

    def test_publish_is_plan_by_default(self):
        before = len(self.remote.mutations)
        self.assertFalse(d.publish(self.prepared, self.policy, self.trusted, transport=self.remote)['execute'])
        self.assertEqual(before, len(self.remote.mutations))

    def test_publish_readback_fetch_and_identical_retry_preserve_application_and_latest(self):
        application = copy.deepcopy(self.remote.releases[0]); self.remote.latest = application['id']
        result = d.publish(self.prepared, self.policy, self.trusted, execute=True, transport=self.remote)
        self.assertTrue(result['execute']); self.assertEqual(application, self.remote.releases[0]); self.assertEqual(application['id'], self.remote.latest)
        restored = self.work / 'restored'
        self.assertEqual(self.frozen, d.fetch('example/project', d.tag_for(self.req), d.archive.digest(self.prepared / 'distribution.json'),
                         restored, self.policy, self.trusted, transport=self.remote))
        uploads = len([x for x in self.remote.calls if x[0] == 'upload'])
        d.publish(self.prepared, self.policy, self.trusted, execute=True, transport=self.remote)
        self.assertEqual(uploads, len([x for x in self.remote.calls if x[0] == 'upload']))

    def test_native_acceptance_checks_payload_then_preserves_qualified_retry(self):
        import distro_check
        d.publish(self.prepared,self.policy,self.trusted,execute=True,transport=self.remote)
        channel=self.remote.releases[-1]
        selected=dict(tag=d.tag_for(self.req),manifest_sha256=d.archive.digest(self.prepared/'distribution.json'),target=self.req['target'])
        env=dict(GITHUB_REPOSITORY='example/project',GITHUB_SHA=self.req['packager_commit'],GITHUB_RUN_ID='901',GITHUB_RUN_ATTEMPT='1',TRUSTED_FINGERPRINT=self.trusted)
        channels=distro_check.extract_channels(self.prepared,self.work/'expected')
        records=[]
        for row in distro_check.matrix(selected['target'])['include']:
            expected=distro_check.expected_payload(channels,self.frozen,'core',row['kind'])
            records.append(dict(schema_version=1,status='passed',id=row['id'],kind=row['kind'],image=row['image'],image_id='sha256:'+'a'*64,
                target=selected['target'],tag=selected['tag'],manifest_sha256=selected['manifest_sha256'],
                checks=['signature','published-download','install','repeated-update','exact-payload','self-check','remove'],
                source_commit=env['GITHUB_SHA'],run_id='901',attempt='1',commands=[['fixture-only']],
                backends=[dict(backend='core',files=len(expected),payload_sha256=d.distro.digest(d.distro.encoded(expected)))]))
        checkout=self.work/'client';(checkout/'docs').mkdir(parents=True);shutil.copyfile(self.policy,checkout/'docs/release-policy.json')
        original=d.delivery.Remote
        with patch.object(d,'ROOT',checkout),patch.object(d.delivery,'Remote',side_effect=lambda repository,transport=None:original(repository,self.remote)):
            bad=copy.deepcopy(records);bad[0]['backends'][0]['payload_sha256']='b'*64
            with self.assertRaisesRegex(ValueError,'exact signed channel'):
                distro_check.accept(selected,bad,env,self.work/'bad-evidence')
            self.assertTrue(channel['prerelease'])
            distro_check.accept(selected,records,env,self.work/'accepted')
            self.assertFalse(channel['prerelease'])
            saved=copy.deepcopy(channel)
            distro_check.accept(selected,records,env,self.work/'accepted-retry')
            self.assertEqual(saved,channel)
        d.publish(self.prepared,self.policy,self.trusted,execute=True,transport=self.remote)
        self.assertEqual(saved,channel)
        marker=json.loads(channel['body']);marker['native_qualification']['target']='linux-aarch64' if self.req['target']=='linux-x86_64' else 'linux-x86_64'
        channel['body']=json.dumps(marker)
        with self.assertRaises(ValueError):
            d.fetch('example/project',selected['tag'],selected['manifest_sha256'],self.work/'wrong-target',self.policy,self.trusted,transport=self.remote)

    def test_partial_upload_failure_retains_draft_and_exact_retry_reconciles(self):
        self.remote.fail_upload = 'Packages'
        with self.assertRaises(d.delivery.DeliveryError): d.publish(self.prepared, self.policy, self.trusted, execute=True, transport=self.remote)
        channel = self.remote.releases[-1]; self.assertTrue(channel['draft']); self.assertTrue(channel['assets'])
        self.remote.fail_upload = None
        d.publish(self.prepared, self.policy, self.trusted, execute=True, transport=self.remote)
        self.assertFalse(self.remote.releases[-1]['draft'])

    def test_changed_remote_asset_is_never_overwritten(self):
        d.publish(self.prepared, self.policy, self.trusted, execute=True, transport=self.remote)
        self.remote.replace_asset('Packages', b'changed'); before = len(self.remote.mutations)
        with self.assertRaises(ValueError): d.publish(self.prepared, self.policy, self.trusted, execute=True, transport=self.remote)
        self.assertEqual(before, len(self.remote.mutations))

    def test_signed_manifest_and_unsigned_flat_payload_tampering_fail(self):
        for name in ('distribution.json', 'Packages', 'software-foundation.db', 'channels.tar.gz'):
            with self.subTest(name=name):
                stage = self.work / name.replace('.', '-'); shutil.copytree(self.prepared, stage)
                with (stage / name).open('ab') as stream: stream.write(b'changed')
                with self.assertRaises((ValueError, subprocess.SubprocessError)): d.verify(stage, self.policy, self.trusted)

    def test_other_policy_certificate_and_trust_cannot_authorize_publication(self):
        other = self.work / 'policy.json'; other.write_bytes(self.policy.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'policy'): d.verify(self.prepared, other, self.trusted)
        with self.assertRaisesRegex(ValueError, 'policy'): d.verify(self.prepared, self.policy, 'F' * 40)
        changed = dict(self.req, certificate_sha256='0' * 64)
        with self.assertRaises(ValueError): d.prepare(changed, self.f.directory, self.f.delivery, self.policy, self.packaging,
            self.work / 'bad', self.private, transport=self.remote, packaging_checkout=self.checkout)
        self.assertFalse((self.work / 'bad').exists())

    def resign(self, directory, value):
        d.archive.write_json(directory / 'distribution.json', value)
        with d.distro.signing(self.private, self.trusted) as (_, sign):
            (directory / 'distribution.json.sig').write_bytes(sign((directory / 'distribution.json').read_bytes()))

    def test_valid_outer_signature_cannot_relabel_certified_package_version(self):
        stage = self.work / 'relabeled'; shutil.copytree(self.prepared, stage)
        value = copy.deepcopy(self.frozen); value['request']['version'] = '9.0.0'
        value['tag'] = d.tag_for(value['request'])
        self.resign(stage, value)
        with self.assertRaisesRegex(ValueError, 'URL|certified|version'): d.verify(stage, self.policy, self.trusted)

    def test_valid_outer_signature_cannot_replace_flat_channel_bytes(self):
        stage = self.work / 'changed'; shutil.copytree(self.prepared, stage)
        (stage / 'Packages').write_bytes(b'changed flat metadata\n')
        value = copy.deepcopy(self.frozen); value['files']['Packages'] = d.asset_info(stage / 'Packages')
        self.resign(stage, value)
        with self.assertRaisesRegex(ValueError, 'flat channel'): d.verify(stage, self.policy, self.trusted)

    def test_application_change_during_upload_preserves_private_failure(self):
        original = self.remote.upload; replaced = False
        def upload(tag, path):
            nonlocal replaced
            original(tag, path)
            if not replaced:
                replaced = True; self.remote.replace_asset('delivery.json')
        with patch.object(self.remote, 'upload', side_effect=upload), self.assertRaises(ValueError):
            d.publish(self.prepared, self.policy, self.trusted, execute=True, transport=self.remote)
        self.assertTrue(self.remote.releases[-1]['draft'])

    def test_fetch_rejects_replaced_asset_identity_without_exposing_output(self):
        d.publish(self.prepared, self.policy, self.trusted, execute=True, transport=self.remote)
        self.remote.change_download = lambda: self.remote.replace_asset('Packages')
        output = self.work / 'changed'
        with self.assertRaises(ValueError):
            d.fetch('example/project', d.tag_for(self.req), d.archive.digest(self.prepared / 'distribution.json'),
                    output, self.policy, self.trusted, transport=self.remote)
        self.assertFalse(output.exists())

    def test_asset_limit_preflight_prevents_a_remote_partial_channel(self):
        with patch.object(d, 'MAX_ASSET', 1), self.assertRaisesRegex(ValueError, 'limits'):
            d.prepare(self.req, self.f.directory, self.f.delivery, self.policy, self.packaging,
                      self.work / 'oversized', self.private, transport=self.remote, packaging_checkout=self.checkout)
        self.assertFalse((self.work / 'oversized').exists())


if __name__ == '__main__': unittest.main()
