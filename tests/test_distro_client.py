"""Authenticated client selection, rollback, and retained-generation behavior."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

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
