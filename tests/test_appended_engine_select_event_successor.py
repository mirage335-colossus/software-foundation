"""Focused metadata boundary checks for select event successor admission."""
from copy import deepcopy
import contextlib
import io
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
REPO = next(path for path in (HERE, *HERE.parents)
    if (path / 'tools/appended_engine_document_maintenance.py').is_file())
sys.path[:0] = [str(HERE / 'postimages/tools'), str(REPO / 'tools')]
import appended_engine_document_maintenance as api
import appended_engine_select_event_successor as picker
import appended_engine_theme_successor as theme

api.ROOT = REPO
PIN = 'a' * 64


def ref(name, pin=PIN):
    return dict(root='sources', path=name, sha256=pin)


def fixture():
    direct = [picker.SHIM, 'BibCopiedDocumentBinding.cpp', picker.MAIN] + ['Direct%d.cpp'%i for i in range(32)]
    engine = [picker.OWNER] + ['Engine%d.cpp'%i for i in range(15)]
    def obj(name):
        source = ref(picker.OWNER_SOURCE, picker.OWNER_SHA256) if name == picker.OWNER else ref('source/' + name)
        members = [ref('sibling%d.cpp'%i) for i in range(8)] if name == picker.OWNER else []
        if members: members[1] = ref(picker.LEAF_SOURCE,picker.LEAF_BEFORE_SHA256)
        return dict(id=name, source=source, dependencies=[], arguments=[], exceptions=False, unified_members=members,
            provenance=dict(kind='original-command-v1', command_sha256=PIN),
            compile_context=dict(source=deepcopy(source), headers=deepcopy(members), arguments=[], macros=[],
                generated_metadata=[], sdk_manifest_sha256=theme.PAIRED_SDK_SHA256))
    prior = [obj(n) for n in direct + engine]
    prior.insert(35, obj(picker.THEME))
    before = dict(objects=prior, metadata={}, header_identity=dict(root='reuse',path='metadata/document-v2/header-identity.json',sha256=PIN))
    proposed = deepcopy(before)
    proposed['header_identity']=ref(picker.HEADER_IDENTITY_SOURCE)
    proposed['objects'] = [o for o in proposed['objects'] if o['id'] != picker.THEME]
    owner = next(o for o in proposed['objects'] if o['id'] == picker.OWNER)
    owner['unified_members'][1]['sha256'] = picker.LEAF_AFTER_SHA256
    owner['compile_context']['headers'][1]['sha256'] = picker.LEAF_AFTER_SHA256
    profile = dict(direct_objects=direct, engine_objects=engine, source_bindings={}, derived_commands={})
    roots = {n: Path('/synthetic')/n for n in ('sources','sdk','reuse')}
    base = api.Inspection(dict(document_profile='editor',sdk_manifest_sha256=theme.PAIRED_SDK_SHA256),{},
        {},proposed,roots,dict(sources={theme.SOURCE:theme.SOURCE_SHA256,picker.HEADER_IDENTITY_SOURCE:PIN},sdk={},reuse={}),profile)
    authority = dict(plan=dict(reuse=before,selection=base.selection),bindings=dict(sdk=roots['sdk']))
    return base, authority


class ProofTransitionTests(unittest.TestCase):
    def effective(self, base, authority):
        with mock.patch.object(api, '_current_context'), mock.patch.object(api, 'ref_path'), \
             mock.patch.object(api, 'checked_read', return_value=b'x'*picker.LEAF_AFTER_BYTES):
            return picker.effective_inspection(base, authority, api)

    def test_reviewed_leaf_only_delta_keeps52_and_unchanged_theme(self):
        base, authority = fixture()
        effective = self.effective(base,authority)
        self.assertEqual(52,len(effective.proof['objects']))
        self.assertEqual(picker.THEME,effective.proof['objects'][35]['id'])
        self.assertNotIn(picker.THEME,base.profile['direct_objects'])
        self.assertEqual(authority['plan']['reuse']['objects'][35],effective.proof['objects'][35])

    def test_undeclared_object_source_and_compiler_changes_refused(self):
        for part in ('source','arguments','dependencies'):
            base, authority = fixture()
            obj=base.proof['objects'][1]
            if part=='source': obj[part]['sha256']='b'*64
            else: obj[part]=[ref('injected.h')] if part=='dependencies' else ['-DCHANGED']
            with self.subTest(part=part),self.assertRaisesRegex(ValueError,'proof changes'):
                self.effective(base,authority)

    def test_wrong_leaf_wrapper_sibling_and_context_refused(self):
        for part in ('leaf','wrapper','sibling','order','context'):
            base, authority=fixture()
            obj=next(o for o in base.proof['objects'] if o['id']==picker.OWNER)
            if part=='leaf': obj['unified_members'][1]['sha256']='b'*64
            elif part=='wrapper': obj['source']['sha256']='b'*64
            elif part=='sibling': obj['unified_members'][2]['sha256']='b'*64
            elif part=='order': obj['unified_members'].reverse()
            else: obj['compile_context']['headers']=[]
            with self.subTest(part=part),self.assertRaises(ValueError):self.effective(base,authority)
        base, authority=fixture()
        base.proof['metadata']['document_contract']=ref('contract.json')
        with self.assertRaisesRegex(ValueError,'metadata role'):self.effective(base,authority)

    def test_context_namespace_allows_only_reviewed_leaf(self):
        oldkey='{sources}/'+picker.LEAF_SOURCE
        old=dict(directories=[],namespace={oldkey:picker.LEAF_BEFORE_SHA256,'{sources}/private.h':PIN},
            physical_headers_sha256=PIN,vfs={})
        current=deepcopy(old);current['namespace'][oldkey]=picker.LEAF_AFTER_SHA256
        picker.context_transition(old,current,api)
        for key in ('{sources}/private.h','{sources}/Other.cpp'):
            bad=deepcopy(current);bad['namespace'][key]='b'*64
            with self.subTest(key=key),self.assertRaises(ValueError):
                picker.context_transition(old,bad,api)

    def test_relocated_header_preserves_every_old_reuse_inventory_byte(self):
        base, authority=fixture()
        original=dict(files={'metadata/document-v2/header-identity.json':PIN,'build/header.h':PIN},directories=['metadata'],modes={})
        authority['plan']['reuse']['inventory']=deepcopy(original)
        base.proof['inventory']=deepcopy(original)
        self.effective(base,authority)
        base.proof['inventory']['files']['build/header.h']='b'*64
        with self.assertRaisesRegex(ValueError,'proof changes'):self.effective(base,authority)
        base, authority=fixture();base.proof['header_identity']['path']='provenance/foreign.json'
        with self.assertRaisesRegex(ValueError,'metadata relocation'):self.effective(base,authority)


class DependencyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.roots=api._completed_binding({n:'/synthetic/'+n for n in ('sources','sdk','reuse','build')})
        self.source=ref('source/Unit.cpp')
        self.target=str(self.roots['build']/'objects/Unit.cpp.o')
        self.row=dict(id='Unit.cpp',original_argv=['/compiler','-MD','-MT',self.target,'-MF',self.target+'.d',
            '-o',self.target,'-c',str(self.roots['sources']/self.source['path'])],original_cwd='/synthetic/build/cmake/build')
        self.inspection=SimpleNamespace(proof=dict(objects=[dict(id='Unit.cpp',source=self.source,arguments=[])],
            private_cache=dict(root='cache',files=['cache/sysroot/include/seed.h'])),
            roots={k:v for k,v in self.roots.items() if k!='build'},
            inventories=dict(sources={'source/Unit.cpp':PIN},sdk={'cache/sysroot/include/seed.h':PIN},reuse={}))
        self.freeze=dict(files={str(self.roots['sources']/self.source['path']):dict(path=str(self.roots['sources']/self.source['path']),sha256=PIN)})

    def admit(self, paths, *, generated=False):
        raw=(self.target+': '+' '.join(paths)+'\n').encode()
        def indexed(value,roots,inventories):
            if inventories[value['root']].get(value['path'])!=value['sha256']: raise ValueError('inventory mismatch')
            return roots[value['root']]/value['path']
        with mock.patch.object(api,'_completed_arguments',return_value=[]),mock.patch.object(api,'ref_path',side_effect=indexed):
            return picker.dependency_refs(raw,self.row,self.roots,self.freeze,self.inspection,api,generated=generated)

    def test_actual_dependency_keys_cannot_omit_source_or_escape_compiler(self):
        source=str(self.roots['sources']/self.source['path'])
        self.assertEqual([self.source],self.admit([source]))
        for paths in ([source,'/unknown/foreign.h'],['/unknown/foreign.h']):
            with self.subTest(paths=paths),self.assertRaises(ValueError):self.admit(paths)
        self.row['dependency_keys']=[]
        with self.assertRaisesRegex(ValueError,'dependency keys'):self.admit([source])

    def test_generated_input_requires_exact_shim_owner(self):
        source=str(self.roots['sources']/self.source['path'])
        generated=str(self.roots['build']/'document-generated/BibCopiedDocumentMetadata.generated.h')
        with self.assertRaisesRegex(ValueError,'generated metadata'):self.admit([source,generated])
        with self.assertRaisesRegex(ValueError,'fresh Shim'):self.admit([source,generated],generated=True)


class EntrypointTests(unittest.TestCase):
    def test_bad_descriptor_kind_and_authority_pin_stop_before_private_context(self):
        descriptor=dict(schema_version=1,kind='unsupported',document_profile='editor',
            showpicker_ninja_log={},showpicker_private={},main_compiled={},
            **{name:dict(path='/metadata/'+name,sha256=pin) for name,pin in picker.PINS.items()})
        with mock.patch.object(api,'_completed_reference',return_value=descriptor), \
             mock.patch.object(api,'_completed_private_context') as private:
            with self.assertRaisesRegex(ValueError,'descriptor kind'):
                picker.accepted_authority(dict(path='/metadata/donor',sha256=PIN),api)
            private.assert_not_called()
        with self.assertRaisesRegex(ValueError,'authority pin'):
            picker.reference(dict(path='/metadata/root',sha256=PIN),api,picker.PINS['root_acceptance'])

    def test_only_explicit_exclusive_boolean_repair_switch_dispatches(self):
        with mock.patch.object(picker,'make_plan',return_value={'ok':True}) as plan:
            result=api.make_plan({'document_profile':'editor'},Path('/synthetic/out'),
                successful_donor={},successful_donor_select_event_repair=True)
            self.assertEqual({'ok':True},result)
            plan.assert_called_once()
        for value in (0,1,None,'true'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                api.make_plan({},Path('/synthetic/out'),successful_donor_select_event_repair=value)
        for lane in ('successful_donor_guard_repair','successful_donor_composition_repair',
                'successful_donor_native_capability_repair','successful_donor_native_control_keypress_repair',
                'successful_donor_native_theme_repair','successful_donor_native_showpicker_repair'):
            with self.subTest(lane=lane),self.assertRaises(ValueError):
                api.make_plan({'document_profile':'editor'},Path('/synthetic/out'),successful_donor={},
                    successful_donor_select_event_repair=True,**{lane:True})

    def test_cli_forwards_new_explicit_lane_and_refuses_mixed_lane(self):
        args=['plan']
        for name in api.SELECTION_FIELDS:
            args.extend(['--'+name.replace('_','-'),'editor' if name=='document_profile' else PIN])
        args.extend(['--output','/synthetic/out','--successful-donor','/synthetic/donor',
            '--successful-donor-sha256',PIN,'--successful-donor-select-event-repair'])
        with mock.patch.object(api,'make_plan',return_value={}) as plan,contextlib.redirect_stdout(io.StringIO()):
            api.main(args)
        self.assertEqual(dict(path='/synthetic/donor',sha256=PIN),plan.call_args.kwargs['successful_donor'])
        self.assertIs(plan.call_args.kwargs['successful_donor_select_event_repair'],True)
        with mock.patch.object(api,'make_plan') as plan,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            api.main(args+['--successful-donor-native-theme-repair'])
        plan.assert_not_called()

    def test_parallel_build_and_unknown_internal_kind_fail_before_tools(self):
        with mock.patch.object(api,'ordinary',side_effect=lambda p,*a,**k:Path(p)), \
             mock.patch.object(api,'verify_plan',return_value=(dict(kind=picker.PLAN_KIND),None)), \
             mock.patch.object(api,'_supervise') as launch:
            with self.assertRaisesRegex(ValueError,'one compiler job'):
                api.build(Path('/synthetic/plan'),PIN,Path('/synthetic/out'),jobs=2)
            launch.assert_not_called()
        with mock.patch.object(api,'checked_document',return_value=dict(kind='unknown',production_eligible=False)):
            with self.assertRaisesRegex(ValueError,'Invalid internal'):
                api._step(SimpleNamespace(plan='synthetic',plan_sha256=PIN))

    def test_internal_repack_refused_for_new_supported_kind(self):
        plan=dict(kind=picker.PLAN_KIND,production_eligible=False,reuse={},selection=dict(sources='/in/sources',sdk='/in/sdk',reuse_root='/in/reuse'))
        owner=dict(schema_version=1,plan_sha256=PIN,output='/out',producer_sha256=PIN)
        with mock.patch.object(api,'checked_document',side_effect=[plan,owner]), \
             mock.patch.object(api,'ordinary',side_effect=lambda p,*a,**kw:Path(p)),mock.patch.object(api,'digest',return_value=PIN):
            with self.assertRaisesRegex(ValueError,'zero repacks'):
                api._step(SimpleNamespace(plan='/plans/plan.json',plan_sha256=PIN,build_root='/out',action='repack'))


class GraphTests(unittest.TestCase):
    def test_synthetic_graph_two_fresh_50imports_fivecopies_theme_before_archive(self):
        direct=[picker.SHIM,picker.MAIN,picker.THEME]+['Direct%d.cpp'%i for i in range(33)]
        engine=[picker.OWNER]+['Engine%d.cpp'%i for i in range(15)]
        selected=direct+engine
        archives=['JavaScriptCore','PAL','Skia','WTF','WebCore']
        with tempfile.TemporaryDirectory(prefix='showpicker-graph-') as tmp:
            root=Path(tmp).resolve();(root/'cmake').mkdir()
            metadata={name:ref(name) for name in ('generator','template','prelink_plan',*api.metadata_interface_paths('editor'))}
            proof=dict(host_tools=dict(python=dict(path='/inert/python')),sdk_tools={n:dict(path=n) for n in ('emxx','emranlib')},
                metadata=metadata,objects=[dict(id=n,arguments=[],source=ref(n),dependencies=[],unified_members=[]) for n in selected],
                replacements=[],archives=[dict(name=n,members=[]) for n in archives],
                link=dict(dependencies=[],archives=archives,flags=[],data=[],pre_js=ref('pre.js'),host_library=ref('host.js')))
            imported=[n for n in selected if n not in picker.FRESH]
            work=dict(objects=[dict(id=n,object=dict(path='/inert/'+n+'.o'),depfile=dict(path='/inert/'+n+'.o.d')) for n in imported],
                archives=[dict(name=n,archive=dict(path='/inert/lib'+n+'.a'),report=dict(path='/inert/'+n+'.json')) for n in archives])
            inspected=SimpleNamespace(proof=proof,roots=dict(sources=root/'sources',sdk=root/'sdk'),
                inventories={},selection=dict(document_profile='editor'),profile=dict(direct_objects=direct))
            with mock.patch.object(api,'_tool',return_value=Path('/inert/python')), \
                 mock.patch.object(api,'ref_path',side_effect=lambda r,roots,i:root/r['path']), \
                 mock.patch.object(api,'_arguments',return_value=[]),mock.patch.object(api,'_header_identity',return_value=None):
                _,fragment,commands=api._graph(inspected,dict(kind=picker.PLAN_KIND,successful_donor=work),root/'plan',PIN,root)
            self.assertEqual((2,50,5),(len(commands['objects']),len(commands['imports']),len(commands['archive_imports'])))
            self.assertEqual(list(picker.FRESH),list(commands['objects']))
            self.assertLess(commands['link'].index(str(root/'objects'/ (picker.THEME+'.o'))),
                commands['link'].index(str(root/'archives/libWebCore.a')))
            self.assertIn(api.SELECT_EVENT_SUCCESSOR_HELPER,fragment.read_text())
            self.assertLess(commands['link'].index(str(root/'objects'/(picker.OWNER+'.o'))),
                commands['link'].index(str(root/'archives/libWebCore.a')))
            self.assertIn(picker.MAIN,commands['imports'])
            self.assertNotIn(picker.OWNER,commands['imports'])
            self.assertEqual(174,len(picker.artifact_names(selected,archives)))


class DonorInterfaceTests(unittest.TestCase):
    """Real admission interface with an inert closed52 metadata/object graph."""
    def setUp(self):
        self.base, authority=fixture()
        self.bindings={**self.base.roots,'build':Path('/synthetic/build')}
        self.records={};self.raw={};self.rows=[];self.commands=dict(objects={})
        self.freeze=dict(files={})
        self.old_inspection=deepcopy(self.base)
        self.old_inspection.proof.clear();self.old_inspection.proof.update(deepcopy(authority['plan']['reuse']))
        self.old_inspection.proof.update(host_tools={},private_cache=dict(root='cache',files=[]))
        for obj in self.old_inspection.proof['objects']:
            self.old_inspection.inventories['sources'][obj['source']['path']]=obj['source']['sha256']
        self.old_inspection.inventories['sources'][picker.LEAF_SOURCE]=picker.LEAF_BEFORE_SHA256
        self.base.inventories['sources'].clear();self.base.inventories['sources'].update(self.old_inspection.inventories['sources'])
        self.base.inventories['sources'][picker.LEAF_SOURCE]=picker.LEAF_AFTER_SHA256
        def fact(path,raw):
            value=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),mode=420,
                identity=[1,len(self.raw)+1,33188,1,len(raw),100,100]);self.raw[str(path)]=raw;return value
        self.fact=fact
        for obj in self.old_inspection.proof['objects']:
            name=obj['id'];target=str(self.bindings['build']/('objects/'+name+'.o'))
            source=str(self.bindings['sources']/obj['source']['path'])
            argv=['/compiler','-MD','-MT',target,'-MF',target+'.d','-o',target,'-c',source]
            dep=(target+': '+source+(' '+str(self.bindings['build']/'document-generated/BibCopiedDocumentMetadata.generated.h') if name==picker.SHIM else '')+'\n').encode()
            frozen=dict(path=source,sha256=obj['source']['sha256']);self.freeze['files'][source]=frozen
            product=fact(target,('object '+name).encode());self.records['objects/'+name+'.o']=product
            row=dict(id=name,original_argv=argv,original_cwd='/synthetic/build/cmake/build',
                ninja_record=['0','1','100',target,'token'],ninja_command='synthetic',command_script=None,
                command_sha256=PIN,object=product)
            if name in (picker.SHIM,picker.MAIN):
                self.commands['objects'][name]=argv
                self.records['objects/'+name+'.o.d']=fact(target+'.d',dep)
                if name==picker.MAIN:self.main={k:row[k] for k in ('id','ninja_record','ninja_command','command_script')}
            else:
                original=fact('/synthetic/original/'+name+'.o',self.raw[target]);row['object']=original
                row['depfile']=fact('/synthetic/original/'+name+'.d',dep)
                row['donor_provenance']=dict(kind=api._showpicker_module().PROVENANCE_KIND,
                    compile_origin='theme-imported',compile_bindings={k:str(v) for k,v in self.bindings.items()},
                    predecessor=dict(kind='retained-Theme-F6-P5-history',id=name))
                self.rows.append(row)
                receipt=dict(object=original,original_depfile=row['depfile'],donor_provenance=row['donor_provenance'],
                    compiler_invoked=False,hardlinked=False,destination=target,sha256=product['sha256'],bytes=product['bytes'])
                self.records['evidence/import-'+name+'.json']=fact('/synthetic/build/evidence/import-'+name+'.json',api.encoded(receipt))
                self.records['evidence/import-'+name+'.original.d']=fact('/synthetic/build/evidence/import-'+name+'.original.d',dep)
        self.archives=[]
        for name in ('JavaScriptCore','PAL','Skia','WTF','WebCore'):
            archive=fact('/synthetic/original/lib'+name+'.a',name.encode());report=fact('/synthetic/original/'+name+'.json',b'{}')
            self.archives.append(dict(name=name,archive=archive,report=report))
            self.records['archives/lib'+name+'.a']=fact('/synthetic/build/archives/lib'+name+'.a',name.encode())
            self.records['evidence/archive-'+name+'.json']=fact('/synthetic/build/evidence/archive-'+name+'.json',b'{}')
        ninja=b'# ninja log v6\n'+('\t'.join(self.main['ninja_record'])+'\n').encode()
        self.ninja=fact('/synthetic/build/cmake/build/.ninja_log',ninja)
        old=dict(reuse=authority['plan']['reuse'],successful_donor=dict(objects=self.rows,archives=self.archives,
            original_bindings={k:str(v) for k,v in self.bindings.items()},dependency_sidecar={},metadata_directories=[]))
        self.authority=dict(plan=old,records=self.records,commands=self.commands,bindings=self.bindings,
            freeze=self.freeze,actual_vfs={},descriptor=dict(main_compiled=self.main,showpicker_ninja_log=self.ninja,
            root_acceptance=dict(path='/synthetic/root',sha256=PIN)))
        self.effective=deepcopy(self.base);self.effective.proof['objects'].insert(35,deepcopy(authority['plan']['reuse']['objects'][35]))

    def admit(self):
        def indexed(ref,roots,inventories):
            if inventories[ref['root']].get(ref['path'])!=ref['sha256']:raise ValueError('current dependency pin differs')
            return roots[ref['root']]/ref['path']
        def context(inspection,*args):
            return dict(directories=[],namespace={'{sources}/'+picker.LEAF_SOURCE:
                picker.LEAF_BEFORE_SHA256 if inspection is self.old_inspection else picker.LEAF_AFTER_SHA256},
                physical_headers_sha256=PIN,vfs={})
        with mock.patch.object(picker,'accepted_authority',return_value=self.authority), \
             mock.patch.object(picker,'effective_inspection',return_value=self.effective), \
             mock.patch.object(picker,'_old_inspection',return_value=self.old_inspection), \
             mock.patch.object(api,'_header_identity',return_value=dict(overlay={})), \
             mock.patch.object(api,'_completed_normalize_vfs',return_value={}), \
             mock.patch.object(api,'_completed_header_context',side_effect=context), \
             mock.patch.object(api,'_completed_ninja_command',return_value='token'), \
             mock.patch.object(api,'_completed_arguments',return_value=[]), \
             mock.patch.object(api,'_completed_fact',side_effect=lambda f:self.raw[f['path']]), \
             mock.patch.object(api,'ref_path',side_effect=indexed):
            return picker.admit_donor(dict(path='/synthetic/donor',sha256=PIN),self.base,api)[0]

    def test_complete50_import_interface_preserves_main_compile_and_nested_history(self):
        result=self.admit()
        self.assertEqual((50,5),(len(result['objects']),len(result['archives'])))
        self.assertNotIn(picker.OWNER,[r['id'] for r in result['objects']])
        main=next(r for r in result['objects'] if r['id']==picker.MAIN)
        self.assertEqual('showpicker-compiled',main['donor_provenance']['compile_origin'])
        inherited=next(r for r in result['objects'] if r['id']==picker.THEME)
        self.assertEqual('showpicker-imported',inherited['donor_provenance']['compile_origin'])
        self.assertEqual('retained-Theme-F6-P5-history',inherited['donor_provenance']['predecessor']['predecessor']['kind'])

    def test_leaf_in_any_other_imported_actual_depfile_refuses_current_reuse(self):
        row=self.rows[0];name=row['id'];key=str(self.bindings['sources']/picker.LEAF_SOURCE)
        self.freeze['files'][key]=dict(path=key,sha256=picker.LEAF_BEFORE_SHA256)
        raw=self.raw[row['depfile']['path']].rstrip()+(' '+key+'\n').encode()
        self.raw[row['depfile']['path']]=raw
        self.raw[self.records['evidence/import-'+name+'.original.d']['path']]=raw
        with self.assertRaisesRegex(ValueError,'current dependency pin differs'):self.admit()

    def test_mutated_copy_receipt_and_ninja_record_refuse(self):
        row=self.rows[0];fact=self.records['evidence/import-'+row['id']+'.json'];old=self.raw[fact['path']]
        value=json.loads(old);value['compiler_invoked']=True;self.raw[fact['path']]=api.encoded(value)
        with self.assertRaisesRegex(ValueError,'copy receipt'):self.admit()
        self.raw[fact['path']]=old;self.main['ninja_record'][0]='2'
        with self.assertRaisesRegex(ValueError,'Ninja authority'):self.admit()


class MetadataOverlayTests(unittest.TestCase):
    def inspect(self,*,selected=True,path=picker.PROOF_SOURCE):
        roots={k:Path('/metadata-fixture')/k for k in ('sources','sdk','reuse')}
        selection={k:PIN for k in api.SELECTION_FIELDS}
        selection.update(document_profile='editor',profile='fixture-profile',sources=str(roots['sources']),
            sdk=str(roots['sdk']),reuse_root=str(roots['reuse']),projection=str(roots['sources']/'projection.json'),
            reuse_proof=str(roots['sources']/path))
        target=dict(system='Emscripten',processor='wasm32',pointer_bits=32,triple='wasm32-emscripten')
        recipe=dict(target=target,options=dict(script_enabled=True,rendering='cpu',thread_model='single'),
            provider=dict(binding='copied-owner-bridge',abi_major=1,abi_minor=1,
                header='include/foundation/appended/engine_provider.h',header_sha256=api.document_contract.BASE_HEADER_SHA256),
            toolchain=dict(paired_sdk_sha256=PIN))
        files={'projection.json':PIN,picker.PROOF_SOURCE:PIN,picker.HEADER_IDENTITY_SOURCE:PIN}
        proof={name:{} for name in ('baseline','inventory','host_tools','sdk_tools','python_launch','metadata',
            'private_cache','emscripten_config','header_identity')}
        proof.update(schema_version=1,kind=api.REUSE_KIND,profile='fixture-profile',document_profile='editor',
            target=target,paired_sdk_sha256=PIN,objects=[],archives=[],replacements=[],link={},recovery_limits=[],
            header_identity=ref(picker.HEADER_IDENTITY_SOURCE),inventory=dict(files={}))
        docs={str(roots['sources']/'recipe.json'):recipe,str(roots['sources']/'projection.json'):{},
            str(roots['sdk']/'sdk.json'):dict(target=target,files={}),str(roots['sources']/path):proof}
        with mock.patch.object(api,'profile',return_value=dict(name='fixture-profile')), \
             mock.patch.object(api,'ordinary',side_effect=lambda p,*a,**k:Path(p)), \
             mock.patch.object(api,'checked_document',side_effect=lambda p,*a,**k:docs[str(p)]), \
             mock.patch.object(api,'checked_read',return_value=b''),mock.patch.object(api,'digest',return_value=PIN), \
             mock.patch.object(api,'required_helpers',return_value=()), \
             mock.patch.object(api,'_validate_metadata_interfaces'),mock.patch.object(api,'_validate_projection'), \
             mock.patch.object(api.manifest,'verify_sources',return_value=(dict(files=files),PIN,recipe)), \
             mock.patch.object(api,'verify_sdk',return_value=PIN),mock.patch.object(api,'inventory') as inventory, \
             mock.patch.object(api,'_validate_proof'):
            result=api.inspect_inputs(selection,**({'_select_event_repair':True} if selected else {}))
            inventory.assert_called_once_with(roots['reuse'],proof['inventory'],'reuse-proof.json')
            return result

    def test_fixed_inventoried_overlay_admitted_only_by_new_lane(self):
        self.assertEqual('sources',self.inspect().proof['header_identity']['root'])
        with self.assertRaisesRegex(ValueError,'baseline root reuse-proof'):self.inspect(selected=False)
        with self.assertRaisesRegex(ValueError,'inventoried source metadata overlay'):self.inspect(path='provenance/foreign.json')

    def test_metadata_graph_refuses_self_and_manifest_hash_cycles(self):
        proof=dict(header_identity=ref(picker.HEADER_IDENTITY_SOURCE))
        picker.validate_metadata_overlay(proof)
        for path in (picker.PROOF_SOURCE,'sources.json','recipe.json'):
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'hash cycle'):
                picker.validate_metadata_overlay(dict(proof,metadata=dict(injected=ref(path))))
        with self.assertRaisesRegex(ValueError,'declared source metadata relocation'):
            picker.validate_metadata_overlay(dict(header_identity=ref('foreign.json')))

    def test_wrong_inventory_pin_or_profile_cannot_select_overlay(self):
        source=Path('/metadata-fixture/sources');selection=dict(document_profile='editor',reuse_proof_sha256=PIN)
        for files,profile in (({},'editor'),({picker.PROOF_SOURCE:'b'*64},'editor'),({picker.PROOF_SOURCE:PIN},'pixel')):
            with self.subTest(profile=profile,files=files),self.assertRaises(ValueError):
                picker.validate_proof_location(dict(selection,document_profile=profile),source/picker.PROOF_SOURCE,source,files)


class MapTests(unittest.TestCase):
    def test_direct_fresh_owner_is_required_and_archive_owner_forbidden(self):
        root=Path('/candidate')
        marker=str(root/('objects/'+picker.OWNER+'.o'))+':'
        symbols=('_ZN7WebCore17HTMLSelectElement20optionSelectedByUserEibb',
            '_ZN7WebCore17HTMLSelectElement19updateSelectedStateEibb')
        raw='\n'.join(marker+'('+s+')' for s in symbols).encode()
        with mock.patch.object(theme,'final_map',return_value={}):
            self.assertEqual(marker,picker.final_map(raw,root,api)['select_owner'])
            for bad in (b'',raw.replace(marker.encode(),b'foreign.o:'),
                raw+b'libWebCore.a('+picker.OWNER.encode()+b'.o)'):
                with self.subTest(bad=bad[:30]),self.assertRaises(ValueError):picker.final_map(bad,root,api)

    def test_actual_fresh_depfile_must_contain_reviewed_unified_leaf(self):
        # The generic dependency parser is tested above; unified completeness is a distinct owner boundary.
        refs=[ref('source/one.cpp')]
        with self.assertRaisesRegex(ValueError,'unified member'):
            picker.validate_fresh_members(picker.OWNER,refs,SimpleNamespace(proof=dict(objects=[
                dict(id=picker.OWNER,unified_members=[ref(picker.LEAF_SOURCE,picker.LEAF_AFTER_SHA256)])])))


if __name__=='__main__':
    unittest.main()
