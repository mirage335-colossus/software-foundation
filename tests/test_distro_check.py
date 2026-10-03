"""Native qualification cannot substitute another target, scope, attempt or payload."""
import copy
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import distro_check as check

class NativeCheckTests(unittest.TestCase):
    def setUp(self):
        self.selected=dict(tag='distro-1.2.3-x86_64-r1-s1',manifest_sha256='a'*64,target='linux-x86_64')
        self.env={'GITHUB_SHA':'b'*40,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'}
        self.records=[dict(schema_version=1,status='passed',id=row['id'],kind=row['kind'],image=row['image'],image_id='sha256:'+'d'*64,
            target=row['target'],tag=self.selected['tag'],manifest_sha256='a'*64,
            checks=['signature','published-download','install','repeated-update','exact-payload','self-check','remove'],
            source_commit='b'*40,run_id='123',attempt='1',backends=[dict(backend='core',files=1,payload_sha256='c'*64)],commands=[['true']])
            for row in check.matrix('linux-x86_64')['include']]

    def test_native_matrix_and_complete_execution_binding(self):
        self.assertEqual(5,len(self.records));self.assertEqual(3,len(check.matrix('linux-aarch64')['include']))
        self.assertEqual(self.selected,check.selection(json.dumps(self.selected)))
        marker=check.qualification(self.selected,self.records,self.env)
        self.assertEqual(5,len(marker['checks']));check.release.native_marker(marker)
        for records in (self.records[:-1],self.records+[self.records[0]],list(reversed(self.records))):
            if records==list(reversed(self.records)):
                self.assertEqual(marker,check.qualification(self.selected,records,self.env));continue
            with self.assertRaises(ValueError):check.qualification(self.selected,records,self.env)
        for key,value in [('status','skipped'),('target','linux-aarch64'),('attempt','2'),('manifest_sha256','c'*64),('checks',[])]:
            altered=copy.deepcopy(self.records);altered[0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check.qualification(self.selected,altered,self.env)

    def test_gentoo_accepts_each_selected_exact_license_without_broadening_scope(self):
        backends = sorted(check.release.distro.BACKENDS)
        config = check.gentoo_license_config(backends)
        accepted = dict(line.split() for line in config.splitlines())
        self.assertEqual(len(backends), len(config.splitlines()))
        self.assertNotIn('*', config)
        # Portage LicenseManager matches license tokens by exact membership;
        # Foundation-Bundled-* does not accept any of these actual license names.
        for backend in backends:
            package = 'app-misc/software-foundation-'+backend+'-bin'
            license_name = 'Foundation-Bundled-'+backend
            self.assertEqual(license_name, accepted[package])
            self.assertNotIn(license_name, {'Foundation-Bundled-*'})
        self.assertEqual(
            'app-misc/software-foundation-core-bin Foundation-Bundled-core\n'
            'app-misc/software-foundation-hosted-web-bin Foundation-Bundled-hosted-web\n',
            check.gentoo_license_config(['core', 'hosted-web']))
        self.assertEqual('', check.gentoo_license_config([]))

    def test_gentoo_runtime_preflight_configures_only_its_required_provider(self):
        value = {'specifications': {
            'core': {'runtime_dependencies': {'gentoo': ['>=sys-libs/glibc-2.36']}},
            'rev': {'runtime_dependencies': {'gentoo': ['>=sys-libs/glibc-2.36', 'media-libs/mesa[X,opengl]']}}}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); directory = root/'etc/portage/package.use'
            directory.mkdir(parents=True)
            unrelated = directory/'site-settings'; unrelated.write_text('app-misc/other feature\n')
            calls = []
            def resolve(*args):
                # Host flags must be present before strict binary resolution.
                self.assertEqual('media-libs/libglvnd X\n', (directory/'software-foundation').read_text())
                calls.append(args)
            check.prepare_gentoo_runtime(value, root, resolve)
            self.assertEqual([('emerge', '--pretend', '--getbinpkgonly', '--usepkgonly',
                '--binpkg-respect-use=y', '--oneshot', '--with-bdeps=n',
                '>=sys-libs/glibc-2.36', 'media-libs/mesa[X,opengl]')], calls)
            self.assertEqual('app-misc/other feature\n', unrelated.read_text())
            del value['specifications']['rev']
            check.prepare_gentoo_runtime(value, root, lambda *args: calls.append(args))
            self.assertEqual('', (directory/'software-foundation').read_text())
            self.assertNotIn('media-libs/mesa[X,opengl]', calls[-1])
            self.assertEqual('app-misc/other feature\n', unrelated.read_text())
            def missing_binary(*args):
                raise subprocess.CalledProcessError(1, args)
            with self.assertRaises(subprocess.CalledProcessError):
                check.prepare_gentoo_runtime(value, root, missing_binary)

    def test_installed_file_bytes_modes_and_extra_files_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);private=root/'opt/software-foundation/core';private.mkdir(parents=True)
            path=private/'data';path.write_bytes(b'complete');path.chmod(0o644)
            expected={'opt/software-foundation/core/data':dict(sha256=check.release.distro.digest(b'complete'),size=8,mode=0o644)}
            self.assertEqual(1,check.verify_installed(root,expected,'core'))
            path.chmod(0o755)
            with self.assertRaises(ValueError):check.verify_installed(root,expected,'core')
            path.chmod(0o644);(private/'foreign').write_text('foreign')
            with self.assertRaisesRegex(ValueError,'foreign'):check.verify_installed(root,expected,'core')

    def test_payload_receipt_requires_exact_authenticated_inventory(self):
        from unittest.mock import patch
        payload={'opt/software-foundation/core/bin/foundation-cli':dict(sha256='1'*64,size=7,mode=0o755)}
        record=copy.deepcopy(self.records[0])
        record['backends']=[dict(backend='core',files=1,payload_sha256=check.release.distro.digest(check.release.distro.encoded(payload)))]
        with patch.object(check,'expected_payload',return_value=payload):
            check.validate_payload_evidence(None,{'backends':['core']},record)
            for key,value in [('files',2),('payload_sha256','c'*64)]:
                altered=copy.deepcopy(record);altered['backends'][0][key]=value
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exact signed channel'):
                    check.validate_payload_evidence(None,{'backends':['core']},altered)

    def test_container_executes_inspected_image_and_cleans_after_timeout(self):
        import subprocess
        from unittest.mock import patch
        calls=[];identity='sha256:'+'e'*64
        def execute(argv,stream,**kwargs):
            calls.append(list(argv))
            if argv[:2]==['docker','start']:raise subprocess.TimeoutExpired(argv,1)
        def cleanup(name,token):calls.append(['cleanup',name,token])
        def run(argv,**kwargs):calls.append(list(argv))
        from contextlib import contextmanager
        @contextmanager
        def display(directory):
            calls.append(['display-start'])
            try:yield {'DISPLAY':':17','XAUTHORITY':'/owned/authority'}
            finally:calls.append(['display-joined'])
        with tempfile.TemporaryDirectory() as temp:
            env=dict(CHANNEL=json.dumps(self.selected),CHECK_IMAGE='debian:bookworm',CHECK_KIND='apt')
            with patch.object(check,'private_display',side_effect=display),patch.object(check.subprocess,'run',side_effect=run),patch.object(check.subprocess,'check_output',return_value=json.dumps([{'Id':identity}])),patch.object(check,'supervised',side_effect=execute),patch.object(check,'remove_owned_container',side_effect=cleanup):
                with self.assertRaises(subprocess.TimeoutExpired):check.container(temp,'apt-bookworm',env)
        created=next(c for c in calls if c[:2]==['docker','create'])
        self.assertIn(identity,created);self.assertNotIn('debian:bookworm',created)
        self.assertIn('DISPLAY=:17',created)
        self.assertIn('type=bind,source=/owned/authority,target=/run/foundation-Xauthority,readonly',created)
        self.assertEqual(['display-joined'],calls[-1])
        cleanup_indices=[i for i,c in enumerate(calls) if c[0]=='cleanup']
        self.assertEqual(2,len(cleanup_indices));self.assertLess(max(cleanup_indices),next(i for i,c in enumerate(calls) if c[:2]==['sudo','chown']))
        self.assertEqual(calls[cleanup_indices[0]][2],calls[cleanup_indices[1]][2])

    def test_container_cleanup_refuses_foreign_ownership(self):
        from unittest.mock import patch
        answers=['123abc',json.dumps([{'Name':'/owned','Config':{'Labels':{'foundation.native-check':'foreign'}}}])]
        with patch.object(check.subprocess,'check_output',side_effect=answers),patch.object(check.subprocess,'run') as mutate:
            with self.assertRaisesRegex(ValueError,'ownership changed'):check.remove_owned_container('owned','expected')
            mutate.assert_not_called()

    def test_version_upgrade_requires_newer_package_for_every_existing_backend(self):
        old = dict(request=dict(repository='example/project',target='linux-x86_64',trusted_fingerprint='a'*40,sequence=1),
            backends=['core'],specifications={'core':dict(version='1.2.3',package_release=1)})
        new = copy.deepcopy(old); new['request']['sequence'] = 2
        with self.assertRaisesRegex(ValueError,'newer package'):
            check.require_version_upgrade(old,new)
        new['specifications']['core']['package_release'] = 2
        check.require_version_upgrade(old,new)
        with self.assertRaises(ValueError):check.require_version_upgrade(new,old)

    def test_arch_install_rejects_stale_native_revision_with_unchanged_payload(self):
        names = ['software-foundation-core-bin', 'software-foundation-terminal-bin']
        query = Path('/owned/arch-versions.txt')
        calls = []
        installed = {'version': '1.2.3-1'}
        def run(*argv, capture=None):
            calls.append((argv, capture))
            if argv[:2] == ('pacman', '-Q'):
                return ''.join(name+' '+installed['version']+'\n' for name in reversed(names)).encode()
        # Successful install/update commands and identical payload are insufficient.
        with self.assertRaisesRegex(ValueError, 'versions differ'):
            check.install_arch(names, '1.2.3-2', run, query)
        self.assertFalse(any(args[:2] == ('pacman', '-Qkk') for args, _ in calls))
        installed['version'] = '1.2.3-2'; calls.clear()
        self.assertEqual(dict.fromkeys(names, '1.2.3-2'), check.install_arch(names, '1.2.3-2', run, query))
        self.assertEqual((('pacman', '-Q', *names), query), calls[2])
        self.assertEqual([(('pacman', '-Qkk', name), None) for name in names], calls[3:])
        for raw in (b'', b'foreign 1.2.3-2\n',
                    ((names[0]+' 1.2.3-2\n')*2).encode(),
                    (names[0]+' 1.2.3-2 extra\n'+names[1]+' 1.2.3-2\n').encode()):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'versions differ'):
                check.install_arch(names, '1.2.3-2', lambda *args, **kw: raw, query)

    def test_acceptance_binds_exact_upgrade_predecessor_tag_and_digest(self):
        prior = dict(self.selected, tag='distro-1.2.2-x86_64-r1-s1', manifest_sha256='e'*64)
        env = dict(self.env, PREVIOUS=json.dumps(prior))
        records = copy.deepcopy(self.records)
        with self.assertRaisesRegex(ValueError, 'scope'):
            check.qualification(self.selected, records, env)
        for record in records:
            record.update(upgrade_from=prior['tag'], upgrade_manifest_sha256=prior['manifest_sha256'])
        check.qualification(self.selected, records, env)
        with self.assertRaisesRegex(ValueError, 'scope'):
            check.qualification(self.selected, records, self.env)
        for key, value in (('upgrade_from', self.selected['tag']), ('upgrade_manifest_sha256', 'f'*64)):
            altered = copy.deepcopy(records); altered[0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'scope'):
                check.qualification(self.selected, altered, env)
        for bad in (dict(prior, target='linux-aarch64'), self.selected):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'predecessor'):
                check.qualification(self.selected, records, dict(env, PREVIOUS=json.dumps(bad)))

    def test_arch_keyring_setup_keeps_explicit_native_home_and_trust(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            key=Path(temp)/'public.gpg';key.write_bytes(b'public fixture')
            with patch.object(check,'require_disposable') as guard, patch.object(Path,'mkdir'), \
                    patch.object(check,'keyring_session',return_value={'status':'passed'}) as session:
                check.prepare_arch_keyring(key,'a'*40)
            guard.assert_called_once_with()
            home=Path('/etc/pacman.d/gnupg')
            self.assertEqual(session.call_args.args,(home,[
                ['pacman-key','--gpgdir',home,'--init'],
                ['pacman-key','--gpgdir',home,'--add',key.resolve()],
                ['pacman-key','--gpgdir',home,'--lsign-key','A'*40]]))
        with patch.object(check,'prepare_arch_keyring',return_value={}) as prepare, patch('builtins.print'):
            check.main(['arch-keyring','--directory','/owned','--trusted-fingerprint','a'*40])
        prepare.assert_called_once_with(Path('/owned/archive-keyring.gpg'),'a'*40)

    def test_keyring_command_failure_stops_work_but_still_shuts_down_and_joins(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp).resolve();failure=subprocess.CalledProcessError(7,['first'])
            with patch.object(check,'keyring_subreaper'), patch.object(check.subprocess,'run',side_effect=[failure,None]) as run, \
                    patch.object(check,'reap_keyring_children',return_value=[]) as join:
                with self.assertRaises(subprocess.CalledProcessError) as caught:
                    check.keyring_session(home,[['first'],['must-not-run']])
                self.assertIs(caught.exception,failure)
            self.assertEqual([c.args[0] for c in run.call_args_list],
                [['first'],['gpgconf','--homedir',str(home),'--kill','all']])
            join.assert_called_once()

    def test_keyring_cleanup_failure_is_sticky_and_preserves_original(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            failure=subprocess.CalledProcessError(7,['first'])
            for cleanup,joined in ((subprocess.CalledProcessError(3,['shutdown']),[]),
                                   (None,check.process_tree.ProcessTreeError('join timed out')),
                                   (None,[{'pid':123,'returncode':1}])):
                with self.subTest(cleanup=cleanup,joined=joined), patch.object(check,'keyring_subreaper'), \
                        patch.object(check.subprocess,'run',side_effect=[failure,cleanup]), \
                        patch.object(check,'reap_keyring_children',side_effect=joined if isinstance(joined,Exception) else None,
                                     return_value=joined) as join:
                    with self.assertRaisesRegex(check.process_tree.ProcessTreeError,'keyring cleanup failed') as caught:
                        check.keyring_session(Path(temp),[['first']])
                    self.assertIs(caught.exception.__cause__,failure)
                    join.assert_called_once()

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux child wait semantics required')
    def test_keyring_join_waits_for_delayed_exit_and_requires_echild(self):
        from unittest.mock import patch
        with patch.object(check.os,'waitpid',side_effect=[(0,0),(123,0),ChildProcessError()]) as wait, \
                patch.object(check.time,'sleep') as sleep:
            self.assertEqual(check.reap_keyring_children(1),[{'pid':123,'returncode':0}])
            self.assertEqual(wait.call_count,3);sleep.assert_called_once()
        with patch.object(check.os,'waitpid',return_value=(0,0)), patch.object(check.time,'sleep') as sleep:
            with self.assertRaisesRegex(check.process_tree.ProcessTreeError,'did not exit'):
                check.reap_keyring_children(0)
            sleep.assert_not_called()
        with patch.object(check.os,'waitpid',side_effect=OSError('cannot inspect children')):
            with self.assertRaises(OSError):check.reap_keyring_children(1)
        with patch.object(check.process_tree,'_direct_children',return_value=[123]),patch.object(check.ctypes,'CDLL') as api:
            with self.assertRaisesRegex(check.process_tree.ProcessTreeError,'fresh Linux child'):
                check.keyring_subreaper()
            api.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith('linux') and all(shutil.which(x) for x in
        ('gpg','gpgconf','gpg-agent','gpg-connect-agent')), 'Linux and GnuPG lifecycle tools required')
    def test_real_keyring_worker_joins_its_daemon_and_preserves_unrelated_home(self):
        script = """import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import distro_check as check
home=Path(sys.argv[2])
commands=[['gpg','--batch','--homedir',str(home),'--pinentry-mode','loopback','--passphrase','',
           '--quick-generate-key','Fixture <fixture@example.invalid>','ed25519','sign','1d']]
if sys.argv[3]=='unmanaged':
 import subprocess
 subprocess.run(commands[0],check=True)
else:
 print(check.keyring_session(home,commands,timeout=20,cleanup_timeout=10))
"""
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);foreign=root/'foreign';foreign.mkdir(mode=0o700)
            def agent_pid():
                result=subprocess.run(['gpg-connect-agent','--homedir',str(foreign),'--no-autostart','GETINFO pid','/bye'],
                    capture_output=True,text=True,timeout=5)
                if result.returncode:return None
                rows=[line[2:] for line in result.stdout.splitlines() if line.startswith('D ')]
                return int(rows[0]) if len(rows)==1 and rows[0].isdecimal() else None
            stop=root/'stop-foreign'
            foreign_script = """import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import distro_check as check
wait = "import sys,time; from pathlib import Path; p=Path(sys.argv[1]); deadline=time.monotonic()+45\\nwhile not p.exists() and time.monotonic()<deadline: time.sleep(.01)\\nassert p.exists(), 'foreign owner stop deadline'"
check.keyring_session(Path(sys.argv[2]),[
 ['gpg-connect-agent','--homedir',sys.argv[2],'/bye'],
 [sys.executable,'-B','-c',wait,sys.argv[3]]],timeout=50,cleanup_timeout=10)
"""
            with (root/'foreign.log').open('wb') as log:
                foreign_owner=check.process_tree.launch([sys.executable,'-B','-c',foreign_script,
                    str(ROOT/'tools'),str(foreign),str(stop)],ROOT,log)
                try:
                    deadline=time.monotonic()+5;before=None
                    while before is None and time.monotonic()<deadline:
                        before=agent_pid()
                        if before is None:time.sleep(.01)
                    self.assertIsNotNone(before)
                    for mode in ('unmanaged','managed'):
                        home=root/mode;home.mkdir(mode=0o700)
                        with (root/(mode+'.log')).open('wb') as output:
                            owner=check.process_tree.launch([sys.executable,'-B','-c',script,str(ROOT/'tools'),str(home),mode],ROOT,output)
                            try:
                                self.assertEqual(owner.wait(timeout=40),0)
                                if mode=='unmanaged':
                                    with self.assertRaisesRegex(check.process_tree.ProcessTreeError,'descendants outlived'):owner.finish()
                                else:owner.finish()
                            finally:owner.close()
                        self.assertIsNone(foreign_owner.poll())
                        self.assertEqual(agent_pid(),before)
                finally:
                    try:
                        stop.write_text('stop')
                        self.assertEqual(foreign_owner.wait(timeout=15),0);foreign_owner.finish()
                    finally:foreign_owner.close()
            renamed=root/'managed-closed';(root/'managed').rename(renamed);shutil.rmtree(renamed)

    def test_native_installation_refuses_regular_host(self):
        from unittest.mock import patch
        with patch.dict(check.os.environ,{'FOUNDATION_DISPOSABLE_CHECK':'0'}),self.assertRaisesRegex(ValueError,'disposable'):
            check.native(None,None,None,'apt',None)

if __name__=='__main__':unittest.main()
