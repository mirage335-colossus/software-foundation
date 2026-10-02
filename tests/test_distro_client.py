"""Authenticated client selection, rollback, and retained-generation behavior."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import distro_client as client
import test_distribution_release as fixtures


def config(location):
    return dict(schema_version=1, repository='example/project', target='linux-x86_64',
        trusted_fingerprint='A'*40, policy_sha256='b'*64, location=str(location),
        selection={'tag':'distro-1.2.3-x86_64-r1-s7','manifest_sha256':'c'*64})


def marker(target='linux-x86_64'):
    checks = ['apt-bookworm','apt-trixie','apt-ubuntu']+(['arch','gentoo'] if target.endswith('x86_64') else [])
    return dict(schema_version=1,target=target,source_commit='a'*40,run_id=1,attempt=1,checks={name:'b'*64 for name in checks})


def asset_row(identity, name, data, tag='distro-1.2.3-x86_64-r1-s7'):
    return dict(id=identity, name=name, state='uploaded', size=len(data), digest='sha256:' + hashlib.sha256(data).hexdigest(),
                browser_download_url='https://github.com/example/project/releases/download/' + tag + '/' + name)


def asset_response(data, url='https://release-assets.githubusercontent.com/fixture/object?signature=exact'):
    result = io.BytesIO(data); result.url = url
    return result


class PublicDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.transport = client.PublicGitHub('example/project')
        self.tag = 'distro-1.2.3-x86_64-r1-s7'
        self.releases = 'repos/example/project/releases?per_page=100'
        self.assets = 'repos/example/project/releases/1/assets?per_page=100'

    def bind(self, rows):
        with patch.object(self.transport, 'json', side_effect=[[dict(id=1, tag_name=self.tag)], rows]):
            self.transport.pages(self.releases); self.transport.pages(self.assets)

    def test_seventy_asset_downloads_use_public_urls_without_asset_rest_requests(self):
        rows = [asset_row(index + 1, 'asset-' + str(index), str(index).encode()) for index in range(70)]
        bodies = {row['browser_download_url']: str(index).encode() for index, row in enumerate(rows)}
        with patch.object(self.transport, 'json', side_effect=[[dict(id=1, tag_name=self.tag)], rows]) as metadata, \
                patch.object(self.transport, 'request', side_effect=AssertionError('no per-asset REST request')), \
                patch.object(client, 'build_opener') as build:
            build.return_value.open.side_effect = lambda request, **options: asset_response(bodies[request.full_url])
            self.transport.pages(self.releases); self.transport.pages(self.assets)
            for row in rows: self.transport.download(row['id'], self.root / row['name'])
        self.assertEqual(metadata.call_count, 2); self.assertEqual(build.return_value.open.call_count, 70)
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir()},
                         {row['name']: bodies[row['browser_download_url']] for row in rows})

    def test_incomplete_asset_pagination_never_authorizes_download(self):
        rows = [asset_row(index + 1, 'asset-' + str(index), b'x') for index in range(100)]
        with patch.object(self.transport, 'json', side_effect=[[dict(id=1, tag_name=self.tag)], rows, OSError('page two failed')]):
            self.transport.pages(self.releases)
            with self.assertRaises(OSError): self.transport.pages(self.assets)
        with patch.object(client, 'build_opener') as build, self.assertRaisesRegex(ValueError, 'complete public asset inventory'):
            self.transport.download(1, self.root / 'payload')
        build.assert_not_called(); self.assertEqual(self.transport.assets, {})

    def test_asset_binding_rejects_foreign_url_unbound_release_and_rebinding(self):
        row = asset_row(1, 'payload', b'exact')
        with self.assertRaisesRegex(ValueError, 'observed public release'):
            self.transport.remember(self.assets, [row])
        self.bind([row])
        for changed in (dict(row, browser_download_url=row['browser_download_url'].replace('/example/project/', '/foreign/project/')),
                        dict(row, browser_download_url=row['browser_download_url'].replace(self.tag, 'foreign-tag')),
                        dict(row, browser_download_url=row['browser_download_url'] + '?replacement=1'),
                        dict(row, name='../escape'), dict(row, size=client.release.MAX_ASSET+1),
                        dict(row, digest='sha256:' + 'a'*64)):
            with self.subTest(changed=changed), self.assertRaises(ValueError): self.transport.remember(self.assets, [changed])
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.transport.remember(self.releases, [dict(id=1, tag_name='different')])
        self.assertEqual(self.transport.assets[1]['sha256'], hashlib.sha256(b'exact').hexdigest())

    def test_truncated_excessive_or_changed_payload_never_publishes_destination(self):
        self.bind([asset_row(1, 'payload', b'exact')]); destination = self.root / 'payload'
        for data in (b'exac', b'exact!', b'wrong'):
            with self.subTest(data=data), patch.object(client, 'build_opener') as build:
                build.return_value.open.return_value = asset_response(data)
                with self.assertRaises(ValueError): self.transport.download(1, destination)
                self.assertFalse(destination.exists()); self.assertEqual(list(self.root.iterdir()), [])
        destination.write_bytes(b'preserve')
        with patch.object(client, 'build_opener') as build, self.assertRaisesRegex(ValueError, 'must be new'):
            self.transport.download(1, destination)
        build.assert_not_called(); self.assertEqual(destination.read_bytes(), b'preserve')

    def test_slow_trickle_has_whole_transfer_deadline_and_no_partial_destination(self):
        self.bind([asset_row(1, 'payload', b'exact')]); destination = self.root / 'payload'
        response = asset_response(b'exact'); response.read1 = Mock(side_effect=[b'e', b'x', b'a', b'c', b't', b''])
        with patch.object(client, 'build_opener') as build, patch.object(client, 'MAX_DOWNLOAD_SECONDS', 3), \
                patch.object(client.time, 'monotonic', side_effect=[0, 1, 2, 3]):
            build.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, 'deadline'): self.transport.download(1, destination)
        self.assertEqual(response.read1.call_count, 1)
        self.assertFalse(destination.exists()); self.assertEqual(list(self.root.iterdir()), [])

    def test_redirects_reject_downgrade_foreign_hosts_credentials_ports_and_other_release(self):
        initial = asset_row(1, 'payload', b'x')['browser_download_url']; handler = client.ReleaseRedirects(initial)
        request = client.Request(initial)
        for url in ('http://release-assets.githubusercontent.com/object', 'https://example.invalid/object',
                    'https://release-assets.githubusercontent.com.evil.invalid/object',
                    'https://user@release-assets.githubusercontent.com/object', 'https://release-assets.githubusercontent.com:443/object',
                    initial.replace(self.tag, 'foreign-tag'), initial + '#fragment'):
            with self.subTest(url=url), self.assertRaises(ValueError): handler.redirect_request(request, None, 302, 'Found', {}, url)
        allowed = 'https://release-assets.githubusercontent.com/object?signature=exact'
        self.assertEqual(handler.redirect_request(request, None, 302, 'Found', {}, allowed).full_url, allowed)

    def test_redirect_chain_is_bounded_before_unlimited_network_requests(self):
        from email.message import Message
        initial = asset_row(1, 'payload', b'x')['browser_download_url']; handler = client.ReleaseRedirects(initial)
        calls = []
        def redirect(request, **options):
            calls.append(request.full_url); request.timeout = 1
            headers = Message(); headers['Location'] = 'https://release-assets.githubusercontent.com/object?hop=' + str(len(calls))
            return handler.http_error_302(request, io.BytesIO(b''), 302, 'Found', headers)
        handler.parent = Mock(open=Mock(side_effect=redirect))
        with self.assertRaises(client.HTTPError): redirect(client.Request(initial))
        self.assertLessEqual(len(calls), 7)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.value=config(self.root/'state')

    def test_only_explicit_missing_404_is_absence(self):
        transport = client.PublicGitHub('example/project')
        for status, missing in ((404,True),(404,False),(403,True),(500,True)):
            error = client.HTTPError('https://api.github.com/repos/example/project/releases/latest',status,'fixture',{},None)
            with self.subTest(status=status,missing=missing), patch.object(transport,'request',side_effect=error):
                if status == 404 and missing:
                    self.assertIsNone(transport.json('repos/example/project/releases/latest',missing=missing))
                else:
                    with self.assertRaises(client.HTTPError):transport.json('repos/example/project/releases/latest',missing=missing)

    def test_generation_sync_flushes_nested_payload_before_directories(self):
        import os,stat
        root=self.root/'generation';(root/'nested').mkdir(parents=True)
        (root/'nested/payload').write_bytes(b'complete');events=[]
        def sync(fd):events.append('directory' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file')
        with patch.object(client.os,'fsync',side_effect=sync):client.sync_tree(root)
        self.assertEqual(['file','directory','directory'],events)
        (root/'link').symlink_to(root/'nested/payload')
        with self.assertRaisesRegex(ValueError,'non-regular'):client.sync_tree(root)

    def test_configuration_rejects_ambiguous_or_linked_destinations(self):
        self.assertEqual(self.value,client.configuration(self.value))
        for key,value in [('schema_version',True),('target','linux-unknown'),('policy_sha256','x'),('location','/'),('selection',{'track':'latest'})]:
            with self.subTest(key=key), self.assertRaises(ValueError):client.configuration(dict(self.value,**{key:value}))
        (self.root/'alias').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):client.configuration(dict(self.value,location=str(self.root/'alias/state')))

    def test_only_qualified_target_is_automatically_selected(self):
        value=dict(self.value,selection={'track':'qualified'})
        def row(sequence,**kwargs):
            return dict(tag_name=f'distro-1.2.3-x86_64-r1-s{sequence}',draft=False,prerelease=False,
                body=json.dumps(dict(kind='signed-distribution',manifest_sha256='c'*64,native_qualification=marker())),**kwargs)
        from unittest.mock import Mock
        remote=Mock();remote.pages.return_value=[row(7),dict(row(8),prerelease=True),dict(row(9),draft=True)]
        self.assertEqual('distro-1.2.3-x86_64-r1-s7',client.select(value,remote)['tag'])
        remote.pages.return_value=[row(7),row(7)]
        with self.assertRaisesRegex(ValueError,'ambiguous'):client.select(value,remote)
        remote.pages.return_value=[dict(row(7),body=json.dumps(dict(kind='signed-distribution',manifest_sha256='c'*64,native_qualification={})))]
        with self.assertRaises(ValueError):client.select(value,remote)

    def test_native_configs_require_signatures_and_regular_update_adapter(self):
        for kind in ('apt','arch','gentoo'):
            text=client.native_config(self.value,kind,'/trusted/tools/distro_client.py','/etc/foundation.json')
            self.assertIn('/current/',text)
            self.assertNotIn('SigLevel = Never',text)
        self.assertIn('Signed-By:',client.native_config(self.value,'apt','/tool','/cfg'))
        self.assertIn('auto-sync = yes',client.native_config(self.value,'gentoo','/tool','/cfg'))
        compile(client.PORTAGE_ADAPTER,'adapter','exec')

    def test_rollback_and_package_replacement_are_rejected(self):
        spec={'version':'1.2.3','package_release':1}
        previous={'request':dict(repository='example/project',target='linux-x86_64',trusted_fingerprint='A'*40,sequence=7),
                  'backends':['core'],'specifications':{'core':spec}}
        client.advance(previous,copy.deepcopy(previous))
        for changed in (dict(previous,request=dict(previous['request'],sequence=6)),
                        dict(previous,backends=[]),
                        dict(previous,request=dict(previous['request'],sequence=8),specifications={'core':dict(spec,version='1.2.2')}),
                        dict(previous,request=dict(previous['request'],sequence=8),specifications={'core':dict(spec,extra='replacement')})):
            with self.assertRaises(ValueError):client.advance(previous,changed)


@unittest.skipUnless(sys.platform.startswith('linux') and all(shutil.which(x) for x in ('cc','dpkg-deb','gpg','gpgv','gpgconf','git')),
                     'actual Linux ELF and signing prerequisites required')
class SignedClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=fixtures.SignedDistributionTests
        cls.fixture.setUpClass();cls.addClassCleanup(cls.fixture.doClassCleanups)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=self.fixture.root);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.f=self.fixture
        self.value=dict(config(self.root/'state'),target=self.f.req['target'],trusted_fingerprint=self.f.trusted,
            policy_sha256=client.release.archive.digest(self.f.policy),selection={'tag':self.f.frozen['tag'],
                'manifest_sha256':client.release.archive.digest(self.f.prepared/'distribution.json')})

    def test_prepared_verified_generation_refresh_is_idempotent_and_preserves_old_state_on_tampering(self):
        first=client.refresh(self.value,self.f.policy,prepared=self.f.prepared)
        self.assertTrue(first['changed']);current=client.current(self.root/'state')
        self.assertFalse(client.refresh(self.value,self.f.policy,prepared=self.f.prepared)['changed'])
        changed=self.root/'changed';shutil.copytree(self.f.prepared,changed)
        (changed/'Packages').write_bytes(b'tampered')
        with self.assertRaises(ValueError):client.refresh(self.value,self.f.policy,prepared=changed)
        self.assertEqual(current,client.current(self.root/'state'))
        (current/'channels/native/gentoo/foreign').write_bytes(b'foreign')
        (current/'channels/native/gentoo/foreign').chmod(0o644)
        with self.assertRaisesRegex(ValueError,'derived channel changed'):client.refresh(self.value,self.f.policy,prepared=self.f.prepared)
        self.assertEqual(current,client.current(self.root/'state'))

    def test_public_asset_refresh_replays_signed_inventory_and_preserves_active_generation_on_bad_bytes(self):
        tag = self.f.frozen['tag']; bodies = {}; rows = []
        for identity, path in enumerate(sorted(self.f.prepared.iterdir()), 1):
            row = asset_row(identity, path.name, path.read_bytes(), tag)
            rows.append(row); bodies[row['browser_download_url']] = path.read_bytes()
        info = dict(id=1, tag_name=tag, name=tag, draft=False, prerelease=True)
        def metadata(endpoint, **options):
            if '/releases/1/assets?' in endpoint: return rows
            if '/releases?' in endpoint: return [info]
            if '/git/ref/tags/' in endpoint: return {'object': {'type': 'commit', 'sha': self.f.req['packager_commit']}}
            if endpoint.endswith('/releases/latest'): return None
            self.fail('unexpected REST request: ' + endpoint)
        transport = client.PublicGitHub('example/project')
        with patch.object(transport, 'json', side_effect=metadata), patch.object(client, 'build_opener') as build:
            build.return_value.open.side_effect = lambda request, **options: asset_response(bodies[request.full_url])
            self.assertTrue(client.refresh(self.value, self.f.policy, transport=transport)['changed'])
            current = client.current(self.root/'state')
            manifest_url = next(url for url in bodies if url.endswith('/distribution.json'))
            bodies[manifest_url] += b'changed'
            with self.assertRaises(ValueError): client.refresh(self.value, self.f.policy, transport=transport)
            self.assertEqual(current, client.current(self.root/'state'))
            self.assertEqual(client.release.verify(current/'assets', self.f.policy, self.f.trusted), self.f.frozen)

    def test_payload_sync_failure_cannot_publish_generation_or_pointer(self):
        with patch.object(client,'sync_tree',side_effect=OSError('durability fixture')):
            with self.assertRaisesRegex(OSError,'durability fixture'):
                client.refresh(self.value,self.f.policy,prepared=self.f.prepared)
        self.assertIsNone(client.current(self.root/'state'))
        self.assertEqual([],list((self.root/'state/generations').iterdir()))

    def test_pointer_failure_leaves_complete_inactive_generation_for_exact_retry(self):
        with patch.object(client.os,'replace',side_effect=OSError('activation fixture')):
            with self.assertRaisesRegex(OSError,'activation fixture'):
                client.refresh(self.value,self.f.policy,prepared=self.f.prepared)
        self.assertIsNone(client.current(self.root/'state'))
        generations=list((self.root/'state/generations').iterdir());self.assertEqual(len(generations),1)
        self.assertTrue((generations[0]/'assets/distribution.json').is_file());self.assertTrue((generations[0]/'channels/apt/Packages').is_file())
        self.assertTrue(client.refresh(self.value,self.f.policy,prepared=self.f.prepared)['changed'])
        self.assertEqual(generations[0],client.current(self.root/'state'))

    def test_unsigned_previous_identity_and_changed_policy_cannot_be_used(self):
        client.refresh(self.value,self.f.policy,prepared=self.f.prepared)
        current=client.current(self.root/'state')
        manifest=current/'assets/distribution.json';manifest.write_bytes(manifest.read_bytes()+b' ')
        with self.assertRaises((ValueError,client.subprocess.SubprocessError)):client.refresh(self.value,self.f.policy,prepared=self.f.prepared)
        with self.assertRaisesRegex(ValueError,'policy'):client.refresh(dict(self.value,policy_sha256='0'*64),self.f.policy,prepared=self.f.prepared)


if __name__=='__main__':unittest.main()
