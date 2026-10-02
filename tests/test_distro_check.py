"""Native qualification cannot substitute another target, scope, attempt or payload."""
import copy
import json
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

    def test_native_installation_refuses_regular_host(self):
        from unittest.mock import patch
        with patch.dict(check.os.environ,{'FOUNDATION_DISPOSABLE_CHECK':'0'}),self.assertRaisesRegex(ValueError,'disposable'):
            check.native(None,None,None,'apt',None)

if __name__=='__main__':unittest.main()
