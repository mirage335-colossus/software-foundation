"""Closed retained52 producer boundaries. No compiler or SDK program executes."""
from copy import deepcopy
import contextlib
import importlib.util
import io
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended_engine_document_maintenance as api
import appended_engine_retained_successor as successor
import test_appended_engine_input_method_successor as previous

PIN = 'a' * 64
ARCHIVES = ['JavaScriptCore', 'PAL', 'Skia', 'WTF', 'WebCore']


def fixture():
    base, authority = previous.fixture()
    base.profile['direct_objects'][3] = successor.GUARD
    for proof in (base.proof, authority['plan']['reuse']):
        proof['kind'] = api.REUSE_KIND
        proof['metadata'] = dict(prelink_plan=deepcopy(successor.PREDECESSOR_PRELINK))
        proof['objects'][3]['id'] = successor.GUARD
        row = proof['objects'][3]
        source = dict(root='sources', path=successor.SOURCE, sha256=successor.BEFORE_SHA256)
        row['source'] = deepcopy(source)
        row['compile_context']['source'] = deepcopy(source)
        row['provenance'] = dict(source_replacement=dict(after=deepcopy(source)))
        proof['header_identity'] = deepcopy(successor.HEADER_IDENTITY)
        for obj in proof['objects']:
            obj['compile_context']['generated_metadata'] = [proof['metadata'][k] for k in sorted(proof['metadata'])]
    base.proof['metadata']['prelink_plan']['sha256'] = 'c' * 64
    for obj in base.proof['objects']:
        obj['compile_context']['generated_metadata'] = [base.proof['metadata'][k] for k in sorted(base.proof['metadata'])]
    row = base.proof['objects'][3]
    row['source']['sha256'] = row['compile_context']['source']['sha256'] = successor.AFTER_SHA256
    row['provenance']['source_replacement']['after']['sha256'] = successor.AFTER_SHA256
    authority['plan']['selection'] = deepcopy(base.selection)
    authority['bindings'].update(base.roots)
    authority['plan']['selection']['projection_sha256'] = PIN
    base.selection['projection_sha256'] = 'b' * 64
    base.proof['header_identity'] = previous.ref(successor.HEADER_IDENTITY_SOURCE)
    authority['freeze'] = dict(files={str(base.roots['sources'] / successor.HEADER_IDENTITY['path']):
        dict(path=str(base.roots['sources'] / successor.HEADER_IDENTITY['path']),
            sha256=successor.HEADER_IDENTITY['sha256'])})
    base.inventories['sources'][successor.SOURCE] = successor.AFTER_SHA256
    return base, authority


class BoundaryTests(unittest.TestCase):
    def effective(self, base, authority):
        raw = deepcopy(authority['plan']['reuse'])
        raw['objects'] = [o for o in raw['objects'] if o['id'] != successor.THEME]
        pin = hashlib.sha256((json.dumps(raw,sort_keys=True,indent=2)+'\n').encode()).hexdigest()
        old_header = dict(projection_sha256=PIN,classes=[],postimages=[])
        new_header = dict(old_header,projection_sha256='b'*64)
        with mock.patch.object(api, '_current_context'), mock.patch.object(api, 'checked_read',
                return_value=b'x' * successor.AFTER_BYTES), mock.patch.object(successor,'RAW_PREDECESSOR_SHA256',pin), \
                mock.patch.object(api,'ref_path',return_value=Path('/current/header.json')), \
                mock.patch.object(api,'checked_document',return_value=new_header), \
                mock.patch.object(api,'_completed_fact',return_value=json.dumps(old_header).encode()):
            return successor.effective_inspection(base, authority, api)

    def test_only_registered_reviewed_transition_and_fixed_fresh_set(self):
        spec = successor.layout()
        self.assertEqual([successor.SHIM, successor.GUARD], spec['fresh'])
        self.assertNotIn(successor.MAIN, spec['fresh'])
        self.assertEqual((previous.successor.SHIM, previous.successor.MAIN), previous.successor.FRESH)
        for name in ('arbitrary', '', None, True):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unknown transition'):
                successor.layout(name)
        with mock.patch.object(successor, 'AFTER_SHA256', None), self.assertRaisesRegex(ValueError, 'unarmed'):
            successor.layout()

    def test_effective52_allows_only_guard_and_preserves_header283(self):
        base, authority = fixture()
        inspected = self.effective(base, authority)
        self.assertEqual(52, len(inspected.proof['objects']))
        self.assertEqual(successor.THEME, inspected.proof['objects'][35]['id'])
        self.assertEqual(successor.HEADER_IDENTITY_SOURCE, inspected.proof['header_identity']['path'])
        for part in ('source', 'arguments', 'dependencies', 'unified_members', 'exceptions'):
            base, authority = fixture()
            row = next(o for o in base.proof['objects'] if o['id'] == successor.MAIN)
            if part == 'source': row[part]['sha256'] = 'b' * 64
            elif part == 'arguments': row[part].append('-DOTHER')
            elif part == 'exceptions': row[part] = True
            else: row[part].append(previous.ref('foreign.h'))
            with self.subTest(part=part), self.assertRaisesRegex(ValueError, 'proof changes'):
                self.effective(base, authority)

    def test_guard_options_headers_and_source_coordinate_cannot_change(self):
        for part in ('arguments', 'dependencies', 'source', 'header_identity'):
            base, authority = fixture()
            row = next(o for o in base.proof['objects'] if o['id'] == successor.GUARD)
            if part == 'arguments': row[part].append('-DOTHER')
            elif part == 'dependencies': row[part].append(previous.ref('new.h'))
            elif part == 'source': row[part]['path'] = 'elsewhere.cpp'
            else: base.proof[part]['path'] = 'foreign-header.json'
            with self.subTest(part=part), self.assertRaises(ValueError): self.effective(base, authority)

    def test_context_requires_one_tu_delta_and_identical_headers_vfs_names(self):
        key = '{sources}/' + successor.SOURCE
        before = dict(directories=[], namespace={key: successor.BEFORE_SHA256, '{sources}/main.cpp': PIN},
            physical_headers_sha256=PIN, vfs={})
        after = deepcopy(before); after['namespace'][key] = successor.AFTER_SHA256
        successor.context_transition(before, after, api)
        for field in ('directories', 'namespace', 'physical_headers_sha256', 'vfs'):
            bad = deepcopy(after)
            if field == 'directories': bad[field].append('{sources}/new')
            elif field == 'namespace': bad[field]['{sources}/main.cpp'] = 'b' * 64
            elif field == 'vfs': bad[field]['new'] = 'mapping'
            else: bad[field] = 'b' * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                successor.context_transition(before, bad, api)

    def test174_namespace_reassigns_guard_and_main_without_archive_repack(self):
        base, authority = fixture()
        selected = [o['id'] for o in authority['plan']['reuse']['objects']]
        names = successor.artifact_names(selected, ARCHIVES)
        self.assertEqual(174, len(names))
        self.assertIn('objects/ProviderGuard.cpp.o.d', names)
        self.assertNotIn('evidence/import-ProviderGuard.cpp.json', names)
        self.assertIn('evidence/import-main.cpp.original.d', names)
        self.assertIn('evidence/import-' + successor.OWNER + '.json', names)
        for remove in (successor.MAIN, successor.OWNER, successor.GUARD):
            bad = list(selected); bad[bad.index(remove)] = 'foreign.cpp'
            with self.subTest(remove=remove), self.assertRaises(ValueError): successor.artifact_names(bad, ARCHIVES)

    def test_metadata_proof_is_explicit_acyclic_and_preserves_header_identity(self):
        root = Path('/sources'); selection = dict(document_profile='editor', reuse_proof_sha256=PIN)
        successor.validate_proof_location(selection, root / successor.PROOF_SOURCE, root, {successor.PROOF_SOURCE: PIN})
        successor.validate_metadata_overlay(dict(header_identity=previous.ref(successor.HEADER_IDENTITY_SOURCE)))
        with self.assertRaises(ValueError):
            successor.validate_proof_location(selection, root / previous.successor.PROOF_SOURCE, root,
                {previous.successor.PROOF_SOURCE: PIN})
        for name in ('sources.json', 'recipe.json', successor.PROOF_SOURCE):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'hash cycle'):
                successor.validate_metadata_overlay(dict(header_identity=previous.ref(successor.HEADER_IDENTITY_SOURCE),
                    metadata=dict(other=previous.ref(name))))

    def test_raw51_inverse_is_exact_and_rejects_unrelated_or_stale_metadata(self):
        base, authority = fixture()
        old = deepcopy(authority['plan']['reuse'])
        old['objects'] = [o for o in old['objects'] if o['id'] != successor.THEME]
        pin = hashlib.sha256((json.dumps(old,sort_keys=True,indent=2)+'\n').encode()).hexdigest()
        with mock.patch.object(successor,'RAW_PREDECESSOR_SHA256',pin):
            self.assertEqual(old,successor.predecessor_proof(base.proof))
            # Guard source edits need not change metadata-generator prelink bytes.
            unchanged_prelink = deepcopy(base.proof)
            unchanged_prelink['metadata']['prelink_plan'] = deepcopy(successor.PREDECESSOR_PRELINK)
            for row in unchanged_prelink['objects']:
                row['compile_context']['generated_metadata'] = [unchanged_prelink['metadata'][k] for k in sorted(unchanged_prelink['metadata'])]
            self.assertEqual(old, successor.predecessor_proof(unchanged_prelink))
            for change in ({'path': 'foreign.json'}, {'unexpected': True}):
                bad_prelink = deepcopy(unchanged_prelink)
                bad_prelink['metadata']['prelink_plan'].update(change)
                for row in bad_prelink['objects']:
                    row['compile_context']['generated_metadata'] = [bad_prelink['metadata'][k] for k in sorted(bad_prelink['metadata'])]
                with self.subTest(prelink=change), self.assertRaises(ValueError):
                    successor.predecessor_proof(bad_prelink)
            for field in ('header','order','metadata','unrelated','provenance'):
                bad=deepcopy(base.proof)
                if field=='header':bad['header_identity']['path']='foreign-header.json'
                elif field=='order':bad['objects'][0],bad['objects'][1]=bad['objects'][1],bad['objects'][0]
                elif field=='metadata':bad['objects'][0]['compile_context']['generated_metadata']=[]
                elif field=='provenance':bad['objects'][3]['provenance']['source_replacement']['after']['sha256']=successor.BEFORE_SHA256
                else:bad['objects'][0]['exceptions']=True
                with self.subTest(field=field),self.assertRaises(ValueError):successor.predecessor_proof(bad)

    def test_header_identity_allows_only_projection_pin_with_all_physical_facts_exact(self):
        old=dict(schema_version=1,projection_sha256=PIN,evidence={'old':'facts'},classes=[{'original':'class'}],postimages=[{'header':'283'}])
        current=dict(old,projection_sha256='b'*64)
        successor.header_identity_transition(old,current,PIN,'b'*64)
        for field in ('evidence','classes','postimages'):
            bad=deepcopy(current);bad[field]=[]
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'physical header identity'):
                successor.header_identity_transition(old,bad,PIN,'b'*64)

    def test_closed_roles_refuse_wrong_ancestor_before_any_path_following(self):
        for name in successor.PINS:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'pin differs'), \
                    mock.patch.object(api, '_completed_reference') as opened:
                successor.reference(dict(path='/untrusted/' + name, sha256='f' * 64), api, successor.PINS[name])
            opened.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'oversized'; path.write_bytes(b'')
            with mock.patch.object(api, 'ordinary', return_value=SimpleNamespace(
                    stat=lambda: SimpleNamespace(st_size=192*1048576+1))), \
                    mock.patch.object(api, 'checked_read') as read, self.assertRaisesRegex(ValueError, '192 MiB'):
                successor.freeze_reference(dict(path=str(path), sha256=successor.PINS['input_freeze']), api)
            read.assert_not_called()


class DonorInterfaceTests(unittest.TestCase):
    """Real admission/depfile APIs over a bounded closed52 in-memory store."""
    def setUp(self):
        self.base, seed = fixture()
        self.bindings = {**self.base.roots, 'build': Path('/synthetic/build')}
        self.owner_bindings = dict(self.bindings, sources=Path('/synthetic/select-event/sources'),
            build=Path('/synthetic/select-event/build'))
        self.old = deepcopy(self.base)
        self.old.proof.clear(); self.old.proof.update(deepcopy(seed['plan']['reuse']))
        self.old.proof.update(host_tools={},private_cache=dict(root='cache',files=[]))
        self.old.inventories['sources'][successor.SOURCE]=successor.BEFORE_SHA256
        self.records={};self.raw={};self.rows=[];self.commands=dict(objects={});self.freeze=dict(files={})
        def fact(path,raw):
            value=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),mode=420,
                identity=[1,len(self.raw)+1,33188,1,len(raw),100,100]);self.raw[str(path)]=raw;return value
        self.fact=fact
        header=str(self.bindings['sources']/previous.successor.HEADER_SOURCE)
        self.freeze['files'][header]=dict(path=header,sha256=previous.successor.HEADER_AFTER_SHA256)
        self.old.inventories['sources'][previous.successor.HEADER_SOURCE]=previous.successor.HEADER_AFTER_SHA256
        for obj in self.old.proof['objects']:
            name=obj['id'];origin=self.owner_bindings if name==successor.OWNER else self.bindings
            target=str(origin['build']/('objects/'+name+'.o'))
            source=str(origin['sources']/obj['source']['path'])
            argv=['/compiler','-MD','-MT',target,'-MF',target+'.d','-o',target,'-c',source]
            dep=(target+': '+source+(' '+header if name==successor.MAIN else '')+
                (' '+str(self.bindings['build']/'document-generated/BibCopiedDocumentMetadata.generated.h') if name==successor.SHIM else '')+'\n').encode()
            self.freeze['files'][source]=dict(path=source,sha256=obj['source']['sha256'])
            self.old.inventories['sources'][obj['source']['path']]=obj['source']['sha256']
            product=fact('/synthetic/build/objects/'+name+'.o',('object '+name).encode())
            self.records['objects/'+name+'.o']=product
            row=dict(id=name,original_argv=argv,original_cwd=str(origin['build']/'cmake/build'),
                ninja_record=['0','1','100',target,'token'],ninja_command='synthetic',command_script=None,
                command_sha256=PIN,object=product)
            if name in (successor.SHIM,successor.MAIN):
                self.commands['objects'][name]=argv
                self.records['objects/'+name+'.o.d']=fact(target+'.d',dep)
                if name==successor.MAIN:self.main={k:row[k] for k in ('id','ninja_record','ninja_command','command_script')}
            else:
                row['object']=fact('/synthetic/original/'+name+'.o',self.raw[product['path']])
                row['depfile']=fact('/synthetic/original/'+name+'.d',dep)
                row['donor_provenance']=dict(kind=previous.successor.PROVENANCE_KIND,
                    compile_origin='select-event-compiled' if name==successor.OWNER else 'select-event-imported',
                    compile_bindings={k:str(v) for k,v in origin.items()},
                    predecessor=dict(kind='exact-retained-SelectEvent-Theme-F6-P5-history',id=name))
                self.rows.append(row)
                receipt=dict(object=row['object'],original_depfile=row['depfile'],donor_provenance=row['donor_provenance'],
                    compiler_invoked=False,hardlinked=False,destination=product['path'],sha256=product['sha256'],bytes=product['bytes'])
                self.records['evidence/import-'+name+'.json']=fact('/synthetic/build/evidence/import-'+name+'.json',api.encoded(receipt))
                self.records['evidence/import-'+name+'.original.d']=fact('/synthetic/build/evidence/import-'+name+'.original.d',dep)
        self.base.inventories['sources'].update(self.old.inventories['sources'])
        self.base.inventories['sources'][successor.SOURCE]=successor.AFTER_SHA256
        archives=[]
        for name in ARCHIVES:
            original=fact('/synthetic/original/lib'+name+'.a',name.encode())
            report=fact('/synthetic/original/'+name+'.json',b'{}')
            archives.append(dict(name=name,archive=original,report=report))
            self.records['archives/lib'+name+'.a']=fact('/synthetic/build/archives/lib'+name+'.a',name.encode())
            self.records['evidence/archive-'+name+'.json']=fact('/synthetic/build/evidence/archive-'+name+'.json',b'{}')
        ninja=fact('/synthetic/build/cmake/build/.ninja_log',b'# ninja log v6\n'+('\t'.join(self.main['ninja_record'])+'\n').encode())
        old=dict(reuse=seed['plan']['reuse'],successful_donor=dict(objects=self.rows,archives=archives,
            original_bindings={k:str(v) for k,v in self.bindings.items()},dependency_sidecar={},metadata_directories=[]))
        self.authority=dict(plan=old,records=self.records,commands=self.commands,bindings=self.bindings,
            freeze=self.freeze,actual_vfs={},descriptor=dict(main_compiled=self.main,input_method_ninja_log=ninja,
                root_acceptance=dict(path='/synthetic/root',sha256=PIN)))
        self.effective=deepcopy(self.base)
        self.effective.proof['objects'].insert(35,deepcopy(seed['plan']['reuse']['objects'][35]))

    def admit(self):
        def indexed(ref,roots,inventories):
            if inventories[ref['root']].get(ref['path'])!=ref['sha256']:
                raise ValueError('current dependency pin differs')
            return roots[ref['root']]/ref['path']
        def context(inspection,*args):
            return dict(directories=[],namespace={'{sources}/'+successor.SOURCE:
                successor.BEFORE_SHA256 if inspection is self.old else successor.AFTER_SHA256},
                physical_headers_sha256=PIN,vfs={})
        with mock.patch.object(successor,'accepted_authority',return_value=self.authority), \
                mock.patch.object(successor,'effective_inspection',return_value=self.effective), \
                mock.patch.object(successor,'_old_inspection',return_value=self.old), \
                mock.patch.object(api,'_header_identity',return_value=dict(overlay={})), \
                mock.patch.object(api,'_completed_normalize_vfs',return_value={}), \
                mock.patch.object(api,'_completed_header_context',side_effect=context), \
                mock.patch.object(api,'_completed_ninja_command',return_value='token'), \
                mock.patch.object(api,'_completed_arguments',return_value=[]), \
                mock.patch.object(api,'_completed_fact',side_effect=lambda f:self.raw[f['path']]), \
                mock.patch.object(api,'ref_path',side_effect=indexed):
            return successor.admit_donor(dict(path='/synthetic/donor',sha256=PIN),self.base,api)[0]

    def test_imported_main_and_unified_keep_distinct_actual_compiler_roots_and_history(self):
        result=self.admit()
        self.assertEqual((50,5),(len(result['objects']),len(result['archives'])))
        self.assertFalse(set(successor.FRESH)&{r['id'] for r in result['objects']})
        main=next(r for r in result['objects'] if r['id']==successor.MAIN)
        owner=next(r for r in result['objects'] if r['id']==successor.OWNER)
        self.assertEqual('input-method-compiled',main['donor_provenance']['compile_origin'])
        self.assertEqual(str(self.bindings['build']),main['donor_provenance']['compile_bindings']['build'])
        self.assertIsNone(main['donor_provenance']['predecessor'])
        self.assertEqual(str(self.owner_bindings['build']),owner['donor_provenance']['compile_bindings']['build'])
        self.assertEqual('select-event-compiled',owner['donor_provenance']['predecessor']['compile_origin'])

    def test_changed_copy_receipt_and_unadmitted_header_consumer_are_refused(self):
        row=next(r for r in self.rows if r['id']==successor.THEME);name=row['id']
        original=self.raw[row['depfile']['path']]
        altered=original.rstrip()+(' '+str(self.bindings['sources']/previous.successor.HEADER_SOURCE)+'\n').encode()
        self.raw[row['depfile']['path']]=altered
        self.raw[self.records['evidence/import-'+name+'.original.d']['path']]=altered
        with self.assertRaisesRegex(ValueError,'sole actual compiler owner'):self.admit()
        self.raw[row['depfile']['path']]=original
        self.raw[self.records['evidence/import-'+name+'.original.d']['path']]=original
        fact=self.records['evidence/import-'+name+'.json'];receipt=json.loads(self.raw[fact['path']])
        receipt['compiler_invoked']=True;self.raw[fact['path']]=api.encoded(receipt)
        with self.assertRaisesRegex(ValueError,'independent-copy receipt'):self.admit()


class InterfaceTests(unittest.TestCase):
    def test_real174_receipt_keeps_two_compiles_and_fifty_original_provenances(self):
        with tempfile.TemporaryDirectory(prefix='retained-receipt-') as tmp:
            root=Path(tmp);base,authority=fixture()
            selected=[o['id'] for o in authority['plan']['reuse']['objects']]
            for name in successor.artifact_names(selected,ARCHIVES):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'inert')
            work=dict(reference=dict(path='/inert/donor',sha256=PIN),objects=[],archives=[])
            results=[]
            for name in selected:
                target=root/('objects/'+name+'.o');pin=api.digest(target)
                results.append(dict(id=name,sha256=pin,bytes=5))
                if name in successor.FRESH:continue
                obj=dict(path='/inert/original/'+name+'.o',sha256=pin,bytes=5,mode=420,identity=[99,1,33188,1,5,1,1])
                dep=dict(obj,path='/inert/original/'+name+'.o.d')
                row=dict(id=name,object=obj,depfile=dep,command_sha256=PIN,original_argv=['inert'],original_cwd='/inert',
                    ninja_record=[],ninja_command='inert',command_script=None,donor_provenance=dict(kind=successor.PROVENANCE_KIND))
                work['objects'].append(row)
                receipt=dict(kind='foundation-document-v2-object-import-v1',id=name,production_eligible=False,origin='imported',
                    compiler_invoked=False,hardlinked=False,sha256=pin,bytes=5,object=obj,original_depfile=dep,
                    original_command_sha256=PIN,original_argv=row['original_argv'],original_cwd=row['original_cwd'],
                    ninja_record=[],ninja_command='inert',command_script=None,donor_provenance=row['donor_provenance'])
                (root/('evidence/import-'+name+'.json')).write_bytes(api.encoded(receipt))
            for name in ARCHIVES:
                target=root/('archives/lib'+name+'.a');pin=api.digest(target)
                obj=dict(path='/inert/original/lib'+name+'.a',sha256=pin,bytes=5,mode=420,identity=[99,1,33188,1,5,1,1])
                report=dict(obj,path='/inert/original/archive-'+name+'.json')
                work['archives'].append(dict(name=name,archive=obj,report=report))
                receipt=dict(kind='foundation-document-v2-archive-import-v1',name=name,origin='imported',archive=obj,
                    original_report=report,destination=str(target),hardlinked=False,archive_program_invoked=False,
                    production_eligible=False,sha256=pin,bytes=5)
                (root/('evidence/import-archive-'+name+'.json')).write_bytes(api.encoded(receipt))
            symbols={successor.THEME:('_ZN7WebCore11RenderTheme9singletonEv',
                '_ZNK7WebCore21RenderThemeEmscripten23popsMenuBySpaceOrReturnEv'),
                successor.OWNER:('_ZN7WebCore17HTMLSelectElement20optionSelectedByUserEibb',
                '_ZN7WebCore17HTMLSelectElement19updateSelectedStateEibb')}
            (root/'evidence/engine-link.map').write_text(''.join(str(root/('objects/'+name+'.o'))+':('+symbol+')\n'
                for name,items in symbols.items() for symbol in items))
            plan=dict(kind=successor.PLAN_KIND,retained_transition=successor.layout(),successful_donor=work,
                reuse=dict(objects=[dict(id=n) for n in selected]))
            inspected=SimpleNamespace(proof=dict(objects=[dict(id=n) for n in selected],archives=[dict(name=n) for n in ARCHIVES]),
                roots=dict(sources=Path('/inert/sources'),sdk=Path('/inert/sdk'),reuse=Path('/inert/reuse')))
            commands=dict(objects={n:[] for n in successor.FRESH},imports={n:[] for n in selected if n not in successor.FRESH},
                archive_imports={n:[] for n in ARCHIVES})
            result=dict(objects=deepcopy(results))
            refs=[dict(root='sources',path=successor.SOURCE,sha256=successor.AFTER_SHA256)]
            with mock.patch.object(previous.successor,'dependency_refs',return_value=refs):
                successor.build_receipt(result,plan,inspected,root,commands,api)
            self.assertEqual(successor.BUILD_KIND,result['kind'])
            self.assertEqual((52,2,50,5,0,174),tuple(result['accounting'][k] for k in
                ('selected','compiled','imported','archive_imported','archive_repacked'))+(result['expected_artifact_records'],))
            self.assertEqual(successor.layout(),result['retained_transition'])
            row=work['objects'][0];path=root/('evidence/import-'+row['id']+'.json')
            bad=json.loads(path.read_bytes());bad['donor_provenance']={'kind':'restamped'};path.write_bytes(api.encoded(bad))
            with mock.patch.object(previous.successor,'dependency_refs',return_value=refs),self.assertRaisesRegex(ValueError,'compiler history'):
                successor.build_receipt(dict(objects=deepcopy(results)),plan,inspected,root,commands,api)

    def test_explicit_api_selector_routes_only_one_editor_transition(self):
        with mock.patch.object(successor, 'make_plan', return_value={}) as plan:
            api.make_plan(dict(document_profile='editor'), Path('/out'), successful_donor={},
                retained_transition=successor.TRANSITION)
            self.assertEqual((successor.TRANSITION, api), plan.call_args.args[-2:])
        for lane in ('guard', 'composition', 'native_capability', 'native_control_keypress',
                'native_theme', 'native_showpicker', 'select_event', 'input_method'):
            with self.subTest(lane=lane), self.assertRaisesRegex(ValueError, 'exclusive'):
                api.make_plan(dict(document_profile='editor'), Path('/out'), successful_donor={},
                    retained_transition=successor.TRANSITION, **{'successful_donor_' + lane + '_repair': True})
        with self.assertRaisesRegex(ValueError, 'unknown transition'):
            api.make_plan({}, Path('/out'), retained_transition=True)

    def test_cli_forwards_closed_selector_and_rejects_mixed_or_unknown_before_io(self):
        args = ['plan']
        for name in api.SELECTION_FIELDS:
            args += ['--' + name.replace('_', '-'), 'editor' if name == 'document_profile' else PIN]
        args += ['--output', '/out', '--successful-donor', '/donor', '--successful-donor-sha256', PIN,
            '--successful-donor-retained-transition', successor.TRANSITION]
        with mock.patch.object(api, 'make_plan', return_value={}) as plan, contextlib.redirect_stdout(io.StringIO()):
            api.main(args)
        self.assertEqual(successor.TRANSITION, plan.call_args.kwargs['retained_transition'])
        for suffix in (['--successful-donor-input-method-repair'], ['--successful-donor-retained-transition', 'other']):
            with self.subTest(suffix=suffix), mock.patch.object(api, 'make_plan') as plan, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): api.main(args + suffix)
            plan.assert_not_called()

    def test_verifier_and_job_barrier_use_distinct_kind(self):
        value = dict(kind=successor.PLAN_KIND)
        with mock.patch.object(api, 'checked_document', return_value=value), \
                mock.patch.object(successor, 'verify_plan', return_value='routed') as verify:
            self.assertEqual('routed', api.verify_plan(Path('/plan'), PIN))
            verify.assert_called_once_with(value, api)
        with mock.patch.object(api, 'ordinary', side_effect=lambda p,*a,**k: Path(p)), \
                mock.patch.object(api, 'verify_plan', return_value=(value, None)), mock.patch.object(api, '_supervise') as run:
            with self.assertRaisesRegex(ValueError, 'one compiler job'):
                api.build(Path('/plan'), PIN, Path('/out'), jobs=2)
            run.assert_not_called()

    def test_layout_cannot_be_restamped_with_arbitrary_fresh_ids(self):
        plan = dict(kind=successor.PLAN_KIND, retained_transition=successor.layout())
        self.assertEqual(successor.layout(), api._retained_layout(plan))
        plan['retained_transition']['fresh'] = [successor.SHIM, successor.MAIN]
        with self.assertRaisesRegex(ValueError, 'layout differs'): api._retained_layout(plan)

    def test_graph_emits_two_fresh50_copies_five_archives_and_direct_owner_once(self):
        base, authority = fixture(); proof = deepcopy(authority['plan']['reuse'])
        proof.update(host_tools=dict(python=dict(path='/inert/python')), sdk_tools={n:dict(path=n) for n in ('emxx','emranlib')},
            replacements=[dict(archive='WebCore',ordinal=0,object_id=successor.OWNER)],
            archives=[dict(name=n,members=[]) for n in ARCHIVES], link=dict(dependencies=[],archives=ARCHIVES,flags=[],data=[],
                pre_js=previous.ref('pre.js'),host_library=previous.ref('host.js')))
        proof['metadata'] = {n:previous.ref(n) for n in ('generator','template','prelink_plan',*api.metadata_interface_paths('editor'))}
        with tempfile.TemporaryDirectory(prefix='retained-graph-') as tmp:
            root = Path(tmp).resolve(); (root/'cmake').mkdir()
            imported = [o['id'] for o in proof['objects'] if o['id'] not in successor.FRESH]
            work = dict(objects=[dict(id=n,object=dict(path='/inert/'+n+'.o'),depfile=dict(path='/inert/'+n+'.d')) for n in imported],
                archives=[dict(name=n,archive=dict(path='/inert/lib'+n+'.a'),report=dict(path='/inert/'+n+'.json')) for n in ARCHIVES])
            inspected = SimpleNamespace(proof=proof, roots=dict(sources=root/'sources',sdk=root/'sdk'), inventories={},
                selection=dict(document_profile='editor'),profile=dict(direct_objects=base.profile['direct_objects']+[successor.THEME]))
            plan = dict(kind=successor.PLAN_KIND, retained_transition=successor.layout(), successful_donor=work)
            with mock.patch.object(api,'_tool',return_value=Path('/inert/python')), \
                    mock.patch.object(api,'ref_path',side_effect=lambda r,*a:root/r['path']), \
                    mock.patch.object(api,'_arguments',return_value=[]),mock.patch.object(api,'_header_identity',return_value=None):
                _,fragment,commands=api._graph(inspected,plan,root/'plan',PIN,root)
            self.assertEqual(set(successor.FRESH),set(commands['objects']))
            self.assertEqual((50,5),(len(commands['imports']),len(commands['archive_imports'])))
            self.assertTrue({successor.MAIN,successor.OWNER} <= set(commands['imports']))
            target=str(root/('objects/'+successor.OWNER+'.o'))
            self.assertEqual(1,commands['link'].count(target))
            self.assertLess(commands['link'].index(target),commands['link'].index(str(root/'archives/libWebCore.a')))
            self.assertIn(successor.HELPER,fragment.read_text())

    def test_internal_archive_operations_fail_closed_for_retained_layout(self):
        value = dict(kind=successor.PLAN_KIND, production_eligible=False, reuse={},
            retained_transition=successor.layout(), selection=dict(sources='/in/sources',sdk='/in/sdk',reuse_root='/in/reuse'))
        owner = dict(schema_version=1,plan_sha256=PIN,output='/out',producer_sha256=PIN)
        for action in ('repack','archive'):
            with self.subTest(action=action), mock.patch.object(api,'checked_document',side_effect=[value,owner]), \
                    mock.patch.object(api,'ordinary',side_effect=lambda p,*a,**k:Path(p)),mock.patch.object(api,'digest',return_value=PIN):
                with self.assertRaisesRegex(ValueError,'zero repacks'):
                    api._step(SimpleNamespace(plan='/plans/plan.json',plan_sha256=PIN,build_root='/out',action=action))

    def test_assembler_exposes_explicit_helper_selection(self):
        spec=importlib.util.spec_from_file_location('retained_assembly_test',ROOT/'recipes/webkitwasm-document-v2/assemble_sources.py')
        assembly=importlib.util.module_from_spec(spec);sys.modules[spec.name]=assembly;spec.loader.exec_module(assembly)
        self.assertIn('appended_engine_retained_successor',assembly.HelperBundle.NAMES)
        with self.assertRaisesRegex(ValueError,'explicit editor'):
            assembly._maintained(ROOT,'pixel',include_retained_successor_helper=True)
        with self.assertRaisesRegex(ValueError,'explicit editor'):
            assembly.prepare('/none',PIN,PIN,document_profile='editor',include_retained_successor_helper=1)
        with self.assertRaisesRegex(ValueError,'strict booleans'):
            assembly.prepare('/none',PIN,PIN,document_profile='editor',include_retained_successor_helper=True,
                include_input_method_successor_helper=1)
        options={name:True for name in ('include_successful_donor_helper','include_theme_successor_helper',
            'include_showpicker_successor_helper','include_select_event_successor_helper','include_input_method_successor_helper')}
        old,_,_=assembly._maintained(ROOT,'editor',**options)
        current,_,_=assembly._maintained(ROOT,'editor',include_retained_successor_helper=True)
        self.assertEqual(set(old)|{successor.HELPER},set(current))
        self.assertEqual({name:current[name] for name in old},old)
        self.assertEqual((assembly.snapshot(ROOT/successor.HELPER),'helper'),current[successor.HELPER])
        args=['plan','--baseline-sources','/none','--baseline-recipe-sha256',PIN,'--baseline-sources-sha256',PIN,
            '--document-profile','editor','--include-retained-successor-helper']
        with mock.patch.object(assembly,'prepare',return_value=dict(document_profile='editor',source_files=1,source_bytes=1)) as prepare, \
                contextlib.redirect_stdout(io.StringIO()):self.assertEqual(0,assembly.main(args))
        self.assertIs(prepare.call_args.kwargs['include_retained_successor_helper'],True)


if __name__ == '__main__':
    unittest.main()
