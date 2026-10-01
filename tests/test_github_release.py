"""Offline lifecycle scenarios: no live GitHub authentication or remote writes."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('github_delivery',ROOT/'tools/github_release.py')
G=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(G)
import test_release as release_fixtures


class FakeGitHub:
    def __init__(self):
        self.releases=[];self.refs={};self.data={};self.next_id=1;self.next_asset=100
        self.latest=None;self.calls=[];self.fail_upload=None;self.change_download=None

    @property
    def mutations(self):
        return [x for x in self.calls if x[0] in ('POST','PATCH','upload')]

    def json(self,endpoint,method='GET',body=None,missing=False):
        self.calls.append((method,endpoint,copy.deepcopy(body)))
        prefix='repos/example/project'
        if endpoint==prefix:return {'full_name':'example/project'}
        path=endpoint[len(prefix):]
        if path.startswith('/git/ref/tags/'):
            value=self.refs.get(path.removeprefix('/git/ref/tags/'))
            if value is None:
                if missing:return None
                raise G.DeliveryError('missing tag')
            return {'object':{'type':'commit','sha':value}}
        if path=='/git/refs' and method=='POST':
            tag=body['ref'].removeprefix('refs/tags/')
            if tag in self.refs:raise G.DeliveryError('tag exists')
            self.refs[tag]=body['sha'];return {'object':{'type':'commit','sha':body['sha']}}
        if path=='/releases/latest':
            found=next((r for r in self.releases if r['id']==self.latest),None)
            if found:return copy.deepcopy(found)
            if missing:return None
            raise G.DeliveryError('Latest missing')
        if path=='/releases' and method=='POST':
            row=dict(body,id=self.next_id,assets=[]);self.next_id+=1;self.releases.append(row)
            return copy.deepcopy(row)
        if path.startswith('/releases/') and method=='PATCH':
            rid=int(path.rsplit('/',1)[1]);row=next(r for r in self.releases if r['id']==rid)
            row.update(body)
            if body.get('make_latest')=='true':self.latest=rid
            return copy.deepcopy(row)
        raise AssertionError((method,endpoint,body))

    def pages(self,endpoint):
        self.calls.append(('pages',endpoint))
        if endpoint.endswith('/releases?per_page=100'):return copy.deepcopy(self.releases)
        rid=int(endpoint.split('/releases/')[1].split('/')[0])
        return copy.deepcopy(next(r for r in self.releases if r['id']==rid)['assets'])

    def upload(self,tag,path):
        self.calls.append(('upload',tag,Path(path).name))
        row=next(r for r in self.releases if r['tag_name']==tag)
        if any(a['name']==Path(path).name for a in row['assets']):raise G.DeliveryError('asset exists')
        value=Path(path).read_bytes();asset={'id':self.next_asset,'name':Path(path).name,'state':'uploaded',
                                        'size':len(value),'digest':'sha256:'+G.sha(value)}
        self.next_asset+=1;self.data[asset['id']]=value;row['assets'].append(asset)
        if self.fail_upload==asset['name']:raise G.DeliveryError('injected response loss after upload')

    def download(self,asset_id,path):
        self.calls.append(('download',asset_id))
        Path(path).write_bytes(self.data[asset_id])
        if self.change_download:
            callback=self.change_download;self.change_download=None;callback()

    def replace_asset(self,name,value=None):
        row=next(r for r in self.releases if any(a['name']==name for a in r['assets']))
        asset=next(a for a in row['assets'] if a['name']==name)
        value=self.data[asset['id']] if value is None else value
        asset.update(id=self.next_asset,size=len(value),digest='sha256:'+G.sha(value));self.next_asset+=1
        self.data[asset['id']]=value


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=release_fixtures.ReleaseTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root=self.fixture.root;self.remote=FakeGitHub()
        self.target=platform.system().lower()+'-'+{'amd64':'x86_64','arm64':'aarch64'}.get(platform.machine().lower(),platform.machine().lower())
        info=self.root/'application/build-info.txt';info.write_text(info.read_text().replace('linux-x86_64',self.target))
        package=self.root/'application.tar.gz';package.unlink();G.archive.archive_tree(self.root/'application',package)
        G.archive.write_json(self.root/'application.tar.gz.json',G.release.artifact.describe(package))
        self.fixture.spec['artifacts'][0].update(sha256=G.archive.digest(package),target=self.target)
        self.fixture.spec['required_scopes']=['source','archive','recovery']
        G.archive.write_json(self.fixture.spec_path,self.fixture.spec)
        self.directory=self.root/'release';G.release.assemble(self.fixture.spec_path,self.fixture.base,self.directory)
        self.args=dict(repository='example/project',tag='v1',directory=str(self.directory),source_commit='a'*40,
                       packager_commit='a'*40,publication_id='publish-1')
        self.delivery=G.publish_candidate(**self.args)['delivery']

    def publish(self,**changes):
        return G.publish_candidate(**dict(self.args,**changes),execute=True,transport=self.remote)

    def base(self,**changes):
        return G.publish_base('example/project',self.fixture.recipe,self.root/'group','a'*40,
                              transport=self.remote,**changes)

    def cert(self,attempt=1,failed=False,experiment=False):
        c=G.coverage;dest=self.root/('cert-'+str(attempt));dest.mkdir()
        rows=[dict(target=self.target,backend='core',environment='fixture',scope=scope)
              for scope in ('source','archive','recovery')]
        policy={'schema_version':1,'profiles':{'fixture':{'description':'offline lifecycle fixture',
                'targets':{self.target:['core']},'checks':rows}}}
        subject={'source_sha256':self.delivery['source_sha256'],'inventory_sha256':self.delivery['inventory_sha256'],
                 'configuration_sha256':c.digest({'policy':policy,'profile':'fixture'})}
        runner=dest/'fixture.py'
        runner.write_text("import json,sys,hashlib\nfrom pathlib import Path\np=Path(sys.argv[1]);r=json.loads(sys.argv[2])\nif r['scope'] in ('source','recovery'):\n q=p/'source.junit.xml';q.write_text('<testsuite><testcase name=\"fixture\"/></testsuite>');r['evidence']={'source.junit.xml':hashlib.sha256(q.read_bytes()).hexdigest()};r['details']={'executed_tests':['fixture']}\n(p/'qualification.json').write_text(json.dumps(r))\n")
        checks=[]
        for row in rows:
            receipt=dict(schema_version=1,source_sha256=subject['source_sha256'],inventory_sha256=subject['inventory_sha256'],
                host=c.host_identity(),status='passed',details={},assertions=['offline-fixture'],evidence={},
                **{key:row[key] for key in ('target','backend','scope')})
            argv=['{python}','{root}/fixture.py','{evidence}',json.dumps(receipt)]
            if failed and row['scope']=='archive':argv=['{python}','-c','raise SystemExit(7)']
            checks.append(dict(row,id=row['scope'],required=True,argv=argv,qualification='qualification.json',
                               timeout_seconds=5,warning_seconds=4,expected_tests=[]))
        plan=c.freeze({'schema_version':1,'mode':'release','subject':subject,'inputs':{'fixture.py':c.sha(runner)},'checks':checks})
        reports=[]
        for check in checks:
            c.run_case(plan,check['id'],dest,dest/check['id'],'qualification-run',attempt)
            reports.append(dest/check['id']/'result.json')
        # Non-plan ordering must survive deterministic packaging and revalidation.
        reports.reverse()
        certificate=G.certification.certify(self.directory,G.release.verify_release(self.directory),plan,reports,policy,'fixture',experiment)
        paths={}
        for key,value in [('certificate',certificate),('check_plan',plan),('policy',policy)]:
            paths[key]=dest/(key+'.json');c.write_new(paths[key],value)
        return dict(repository='example/project',tag='v1',directory=str(self.directory),delivery=self.delivery,
                    profile='fixture',reports=reports,attempt=attempt,**paths)

    def promotion(self,cert,**changes):
        values={key:cert[key] for key in ('repository','tag','directory','delivery','policy','profile','attempt')}
        values.update(run_id='qualification-run',certificate_sha256=G.archive.digest(cert['certificate']))
        values.update(changes)
        return G.promote(**values,transport=self.remote)

    def test_mutations_are_offline_plans_by_default(self):
        self.assertFalse(G.publish_candidate(**self.args,transport=self.remote)['execute'])
        self.assertFalse(self.base()['execute'])
        cert=self.cert()
        self.assertFalse(G.attach_certificate(**cert,transport=self.remote)['execute'])
        self.assertFalse(self.promotion(cert)['execute'])
        self.assertEqual(self.remote.calls,[])

    def test_candidate_publishes_only_after_complete_byte_verification(self):
        result=self.publish()
        self.assertTrue(result['execute']);self.assertFalse(self.remote.releases[0]['draft'])
        self.assertIsNone(self.remote.latest)
        uploads=[x for x in self.remote.calls if x[0]=='upload']
        self.assertEqual(len(uploads),len(self.delivery['files'])+1)
        last_patch=max(i for i,x in enumerate(self.remote.calls) if x[0]=='PATCH')
        self.assertTrue(any(x[0]=='download' for x in self.remote.calls[:last_patch]))

    def test_existing_tag_draft_and_duplicate_tags_never_overwrite(self):
        self.publish();before=copy.deepcopy(self.remote.releases);count=len(self.remote.mutations)
        with self.assertRaisesRegex(ValueError,'already exists'):self.publish()
        self.assertEqual(self.remote.releases,before);self.assertEqual(len(self.remote.mutations),count)
        duplicate=copy.deepcopy(before[0]);duplicate['id']=999;self.remote.releases.append(duplicate)
        with self.assertRaisesRegex(ValueError,'duplicate release tags'):self.publish()

    def test_existing_orphan_tag_is_not_silently_adopted(self):
        self.remote.refs['v1']='a'*40
        with self.assertRaisesRegex(ValueError,'already exists'):self.publish()
        self.assertFalse(self.remote.mutations)

    def test_unknown_upload_outcome_preserves_draft_and_blocks_retry(self):
        self.remote.fail_upload='application.tar.gz'
        with self.assertRaises(G.DeliveryError) as caught:self.publish()
        self.assertTrue(caught.exception.uncertain);self.assertTrue(self.remote.releases[0]['draft'])
        self.assertFalse(any(x[0]=='PATCH' for x in self.remote.mutations))
        with self.assertRaisesRegex(ValueError,'already exists'):self.publish()

    def test_replaced_same_byte_asset_invalidates_observation(self):
        self.publish();self.remote.change_download=lambda:self.remote.replace_asset('application.tar.gz')
        with self.assertRaisesRegex(ValueError,'identities changed'):
            G.verified_remote(G.Remote('example/project',self.remote),self.delivery,self.directory)

    def test_tag_change_during_download_invalidates_observation(self):
        self.publish();self.remote.change_download=lambda:self.remote.refs.update(v1='b'*40)
        with self.assertRaisesRegex(ValueError,'tag identity changed'):
            G.verified_remote(G.Remote('example/project',self.remote),self.delivery,self.directory)

    def test_incomplete_or_duplicate_remote_assets_never_finalize(self):
        original=self.remote.upload
        def incomplete(tag,path):
            original(tag,path)
            if Path(path).name=='delivery.json':self.remote.releases[0]['assets'][0]['state']='starter'
        self.remote.upload=incomplete
        with self.assertRaises(G.DeliveryError) as caught:self.publish()
        self.assertTrue(caught.exception.uncertain);self.assertTrue(self.remote.releases[0]['draft'])
        self.assertFalse(any(x[0]=='PATCH' for x in self.remote.mutations))
        self.remote.releases[0]['assets'][0]['state']='uploaded'
        duplicate=copy.deepcopy(self.remote.releases[0]['assets'][0]);duplicate['id']=999
        self.remote.releases[0]['assets'].append(duplicate)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            G.Remote('example/project',self.remote).assets(self.remote.releases[0])

    def test_missing_local_dependency_member_prevents_any_mutation(self):
        member=next(name for name in self.delivery['files'] if name.startswith('dependencies/'))
        (self.directory/member).unlink()
        with self.assertRaises(ValueError):self.publish()
        self.assertFalse(self.remote.calls)

    def test_base_fetch_missing_is_failure_without_fallback(self):
        with self.assertRaisesRegex(ValueError,'absent'):
            G.fetch_base('example/project',self.fixture.recipe,self.root/'fetched',transport=self.remote)
        self.assertFalse((self.root/'fetched').exists());self.assertFalse(self.remote.mutations)

    def test_base_publish_fetch_and_exact_reuse(self):
        self.base(execute=True)
        self.assertTrue(self.remote.releases[0]['prerelease']);self.assertIsNone(self.remote.latest)
        uploads=[x[2] for x in self.remote.calls if x[0]=='upload']
        self.assertEqual(uploads,list(G.store.names(self.fixture.recipe)))
        result=G.fetch_base('example/project',self.fixture.recipe,self.root/'fetched',transport=self.remote)
        self.assertEqual(result['files'],G.store.verify_group(self.root/'group',self.fixture.recipe))
        count=len(self.remote.mutations);self.assertTrue(self.base(execute=True)['reused'])
        self.assertEqual(len(self.remote.mutations),count)

    def test_base_release_replacement_during_upload_is_uncertain(self):
        original=self.remote.upload
        def changed_release(tag,path):
            original(tag,path)
            if Path(path).name==G.store.names(self.fixture.recipe)[-1]:
                self.remote.releases[0]['id']=999
        self.remote.upload=changed_release
        with self.assertRaisesRegex(G.DeliveryError,'base release identity changed') as caught:
            self.base(execute=True)
        self.assertTrue(caught.exception.uncertain)
        self.assertFalse(any(x[0]=='PATCH' for x in self.remote.mutations))

    def test_partial_or_conflicting_base_is_not_replaced(self):
        self.base(execute=True);row=self.remote.releases[0];row['assets'].pop();count=len(self.remote.mutations)
        with self.assertRaisesRegex(ValueError,'partial existing'):self.base(execute=True)
        self.assertEqual(len(self.remote.mutations),count)

    def test_changed_base_asset_is_rejected_even_with_valid_server_digest(self):
        self.base(execute=True);name=G.store.names(self.fixture.recipe)[0];self.remote.replace_asset(name,b'changed')
        count=len(self.remote.mutations)
        with self.assertRaisesRegex(ValueError,'differs'):self.base(execute=True)
        self.assertEqual(len(self.remote.mutations),count)

    def test_complete_certificate_attachment_and_exact_promotion(self):
        self.publish();cert=self.cert();before=copy.deepcopy(self.remote.releases[0]['assets'])
        attached=G.attach_certificate(**cert,execute=True,transport=self.remote)
        self.assertIsNone(self.remote.latest)
        self.assertEqual(self.remote.releases[0]['assets'][:len(before)],before)
        result=self.promotion(cert,execute=True)
        self.assertTrue(result['latest']);self.assertEqual(self.remote.latest,result['release_id'])
        self.assertEqual(set(attached['files']),{'certification-qualification-run-attempt-1.json','certification-qualification-run-attempt-1.tar.gz'})

    def test_failed_later_attempt_keeps_older_reports_and_binary_bytes(self):
        self.publish();cert=self.cert();G.attach_certificate(**cert,execute=True,transport=self.remote)
        old=copy.deepcopy(self.remote.releases[0]['assets']);later=self.cert(2,failed=True)
        G.attach_certificate(**later,execute=True,transport=self.remote)
        self.assertEqual(self.remote.releases[0]['assets'][:len(old)],old)
        with self.assertRaisesRegex(ValueError,'does not qualify'):self.promotion(later,execute=True)
        self.assertIsNone(self.remote.latest)

    def test_duplicate_attempt_and_stale_certificate_are_rejected(self):
        self.publish();cert=self.cert();G.attach_certificate(**cert,execute=True,transport=self.remote)
        count=len(self.remote.mutations)
        with self.assertRaisesRegex(ValueError,'already exists'):G.attach_certificate(**cert,execute=True,transport=self.remote)
        with self.assertRaisesRegex(ValueError,'stale'):self.promotion(cert,certificate_sha256='0'*64,execute=True)
        self.assertEqual(len(self.remote.mutations),count)

    def test_partial_certificate_attempt_blocks_promotion_and_later_attachment(self):
        self.publish();cert=self.cert();stem='certification-qualification-run-attempt-1.tar.gz'
        self.remote.fail_upload=stem
        with self.assertRaises(G.DeliveryError) as caught:
            G.attach_certificate(**cert,execute=True,transport=self.remote)
        self.assertTrue(caught.exception.uncertain);count=len(self.remote.mutations)
        with self.assertRaisesRegex(ValueError,'partial certificate'):
            self.promotion(cert,execute=True)
        later=self.cert(2)
        with self.assertRaisesRegex(ValueError,'partial certificate'):
            G.attach_certificate(**later,execute=True,transport=self.remote)
        self.assertEqual(len(self.remote.mutations),count);self.assertIsNone(self.remote.latest)

    def test_changed_policy_or_local_evidence_cannot_reuse_certificate(self):
        self.publish();cert=self.cert();G.attach_certificate(**cert,execute=True,transport=self.remote)
        rules=G.coverage.load(cert['policy']);rules['profiles']['fixture']['description']='Changed support contract'
        Path(cert['policy']).write_bytes(G.archive.encoded(rules));count=len(self.remote.mutations)
        with self.assertRaisesRegex(ValueError,'current promotion policy differs'):
            self.promotion(cert,execute=True)
        self.assertEqual(len(self.remote.mutations),count)
        later=self.cert(2)
        (later['reports'][0].parent/'console.log').write_text('different execution output')
        with self.assertRaises(ValueError):G.attach_certificate(**later,execute=True,transport=self.remote)
        self.assertEqual(len(self.remote.mutations),count)

    def test_changed_binary_or_tag_cannot_be_promoted(self):
        self.publish();cert=self.cert();G.attach_certificate(**cert,execute=True,transport=self.remote)
        self.remote.replace_asset('application.tar.gz',b'different');count=len(self.remote.mutations)
        with self.assertRaises(ValueError):self.promotion(cert,execute=True)
        self.assertEqual(len(self.remote.mutations),count);self.assertIsNone(self.remote.latest)

    def test_experiment_never_becomes_latest_or_relabels_packager(self):
        with self.assertRaisesRegex(ValueError,'requires an experiment'):
            G.publish_candidate(**dict(self.args,packager_commit='b'*40))
        result=self.publish(packager_commit='b'*40,experiment=True)
        self.assertEqual(self.remote.releases[0]['name'],'experiment');self.assertTrue(self.remote.releases[0]['prerelease'])
        self.delivery=result['delivery'];cert=self.cert(experiment=True)
        with self.assertRaisesRegex(ValueError,'ordinary'):self.promotion(cert,execute=True)
        self.assertIsNone(self.remote.latest)

    def test_final_pointer_failure_is_uncertain_and_never_rolls_back(self):
        self.publish();cert=self.cert();G.attach_certificate(**cert,execute=True,transport=self.remote)
        original=self.remote.json
        def change_pointer(endpoint,**kwargs):
            result=original(endpoint,**kwargs)
            if kwargs.get('body',{}).get('make_latest')=='true':self.remote.latest=None
            return result
        self.remote.json=change_pointer
        with self.assertRaises(G.DeliveryError) as caught:self.promotion(cert,execute=True)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(len(self.remote.releases),1)

    def test_changed_asset_after_promotion_reports_uncertainty(self):
        self.publish();cert=self.cert();G.attach_certificate(**cert,execute=True,transport=self.remote)
        original=self.remote.json
        def change_asset(endpoint,**kwargs):
            result=original(endpoint,**kwargs)
            if kwargs.get('body',{}).get('make_latest')=='true':self.remote.replace_asset('application.tar.gz')
            return result
        self.remote.json=change_asset
        with self.assertRaises(G.DeliveryError) as caught:self.promotion(cert,execute=True)
        self.assertTrue(caught.exception.uncertain)

    def test_cli_plans_without_transport_and_requires_separate_execution_option(self):
        request=self.root/'request.json';request.write_text(json.dumps(self.args))
        with mock.patch.object(G,'GitHub',side_effect=AssertionError('unexpected transport')):
            with mock.patch('sys.stdout',new_callable=io.StringIO) as output:
                self.assertEqual(G.main(['publish-candidate','--input',str(request)]),0)
            self.assertFalse(json.loads(output.getvalue())['execute'])
        request.write_text(json.dumps(dict(self.args,execute=True)))
        with self.assertRaisesRegex(ValueError,'separate explicit CLI option'):
            G.main(['publish-candidate','--input',str(request)])

    def test_lost_execution_receipt_is_uncertain(self):
        request=self.root/'request.json';request.write_text(json.dumps(self.args))
        with mock.patch.object(G,'GitHub',return_value=self.remote),mock.patch('builtins.print',side_effect=BrokenPipeError):
            with self.assertRaises(G.DeliveryError) as caught:
                G.main(['publish-candidate','--input',str(request),'--execute'])
        self.assertTrue(caught.exception.uncertain)
        self.assertFalse(self.remote.releases[0]['draft']);self.assertIsNone(self.remote.latest)


class TransportTests(unittest.TestCase):
    def test_invalid_location_and_untrusted_duplicate_fields_fail(self):
        for repository in ('--help','owner/repo/extra','../repo','owner/repo\n'):
            with self.assertRaises(ValueError):G.location(repository)
        for tag in ('../v1','--target=x','v 1','a/b'):
            with self.assertRaises(ValueError):G.location('example/project',tag)
        with self.assertRaises(ValueError):G.parse('{"id":1,"id":2}')

    def test_paginated_inventory_is_complete_and_never_uses_embedded_assets(self):
        transport=G.GitHub('example/project')
        with mock.patch.object(transport,'_run',return_value=subprocess.CompletedProcess([],0,b'[[{"id":1}],[],[{"id":2}]]',b'')) as call:
            self.assertEqual(transport.pages('repos/example/project/releases?per_page=100'),[{'id':1},{'id':2}])
            self.assertIn('--paginate',call.call_args.args[0]);self.assertIn('--slurp',call.call_args.args[0])
        with mock.patch.object(transport,'_run',return_value=subprocess.CompletedProcess([],0,b'{"assets":[]}',b'')):
            with self.assertRaises(ValueError):transport.pages('endpoint')

    def test_transport_never_uses_shell_or_clobber_and_never_prints_credentials(self):
        transport=G.GitHub('example/project')
        with mock.patch.object(G.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'',b'private token value')) as call:
            with self.assertRaises(G.DeliveryError) as caught:transport.upload('v1',Path('/owned/file.zip'))
        argv=call.call_args.args[0]
        self.assertEqual(argv,['gh','release','upload','v1','--repo','github.com/example/project','/owned/file.zip'])
        self.assertNotIn('clobber',' '.join(argv));self.assertNotIn('private token',str(caught.exception))
        self.assertNotIn('shell',call.call_args.kwargs)

    def test_access_failure_is_never_a_cache_miss(self):
        transport=G.GitHub('example/project')
        for raw in (b'HTTP/2 403 Forbidden\n\n{}',b'HTTP/2 500 Server Error\n\n{}',b'unknown'):
            with mock.patch.object(transport,'_run',return_value=subprocess.CompletedProcess([],1,raw,b'secret')):
                with self.assertRaises(ValueError):transport.json('endpoint',missing=True)


if __name__=='__main__':unittest.main()
