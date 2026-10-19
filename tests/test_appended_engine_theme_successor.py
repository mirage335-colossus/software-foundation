"""Synthetic pure Theme lane fixtures; no SDK, compiler or engine execution.

The original-command and625-byte Theme fixtures are inert pinned source metadata.
All roots, authorities, process reports and depfiles below are fabricated boundaries.
"""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from unittest import mock
import appended_engine_document_maintenance as maintenance
import appended_engine_successful_donor as donor
import appended_engine_theme_successor as theme

PIN = '1'*64
FIXTURES = Path(__file__).parent/'fixtures/native_theme'
ORIGINAL = json.loads((FIXTURES/'original-command.json').read_text())
THEME_BYTES = (FIXTURES/'RenderThemeEmscripten.cpp').read_bytes()

def source_ref():
    return dict(root='sources', path=theme.SOURCE, sha256=theme.SOURCE_SHA256)

def base_fixture():
    direct = list(donor.NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS) + ['Direct%02d.cpp'%n for n in range(29)]
    engine = ['Engine%02d.cpp'%n for n in range(16)]
    profile = dict(document_profile="editor",direct_objects=direct,engine_objects=engine,source_bindings={},derived_commands={},exceptions=[],owner_postimages={},python_entrypoints=["python.py"])
    objects = [dict(id=n,source=dict(root='sources',path='source/'+n,sha256=PIN),arguments=[],dependencies=[],unified_members=[],exceptions=False) for n in direct+engine]
    proof = dict(objects=objects,replacements=[{}]*16,archives=[dict(name=n,members=[{}]*count) for n,count in donor.ARCHIVE_COUNTS.items()],
        metadata={}, baseline=dict(command_records=dict(root='reuse',path='ledger.json',sha256=PIN),original_bindings=ORIGINAL['bindings']),
        host_tools=dict(python=dict(path='/usr/bin/python3.13')),emscripten_config=dict(LLVM_ROOT='upstream/bin'),sdk_tools=dict(emxx=dict(path='upstream/emscripten/em++')),private_cache=dict(root='cache',files=[]))
    roots={name:Path('/synthetic/current')/name for name in ('sources','sdk','reuse')}
    return maintenance.Inspection(dict(document_profile='editor',sdk_manifest_sha256=theme.PAIRED_SDK_SHA256,reuse_proof_sha256=theme.BASELINE_REUSE_SHA256),{}, {},proof,roots,
        dict(sources={theme.SOURCE:theme.SOURCE_SHA256},sdk={},reuse={}),profile)

class FakeAPI:
    ROOT=Path('/synthetic/checkout')
    def __init__(self, base):
        self.base=base;self.docs={};self.raw={};self.calls=[]
    def __getattr__(self,name):
        return getattr(maintenance,name)
    def digest(self,p):return PIN
    def ref_path(self,ref,roots,inventories):
        if ref.get('path')==theme.SOURCE and ref.get('sha256')!=theme.SOURCE_SHA256:raise ValueError('source pin')
        if ref['path']!= 'ledger.json' and inventories[ref['root']].get(ref['path'])!=ref['sha256']:raise ValueError('inventory pin')
        return roots[ref['root']]/ref['path']
    def checked_read(self,p,*args,**kwargs):
        if str(p).endswith(theme.SOURCE):return THEME_BYTES
        return self.raw[str(p)]
    def checked_document(self,p,*args):
        if str(p).endswith('ledger.json'):return dict(commands={theme.ORIGINAL_COMMAND:ORIGINAL['command']})
        return self.docs[str(p)]
    def _completed_reference(self,ref):return deepcopy(self.docs[ref['path']])
    def _completed_fact(self,fact,*args,**kwargs):return self.raw[fact['path']]
    def _header_identity(self,inspected):return dict(overlay={'version':0,'roots':[]})
    def _arguments(self,*args,**kwargs):return []
    def _object_provenance(self,obj,commands,inspected):
        with mock.patch.object(maintenance,'digest',return_value=PIN):
            return maintenance._object_provenance(obj,commands,inspected)

class ProbeSupplementTests(unittest.TestCase):
    def setUp(self):
        self.base=base_fixture();self.api=FakeAPI(self.base);self.root=Path('/synthetic/probe')
        self.command=theme.derive_probe(self.base,source_ref(),self.root,self.api)
        self.probe_ref=dict(path='/synthetic/probe/receipt.json',sha256=PIN)
        self.supp_ref=dict(path='/synthetic/supplement.json',sha256=PIN)
        raw=(self.command['target']+': '+str(self.base.roots['sources']/theme.SOURCE)+'\n').encode()
        self.fact=dict(path=self.command['depfile'],sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),mode=420,identity=[1,2,33188,1,len(raw),3,4])
        self.api.raw[self.fact['path']]=raw
        self.probe=dict(schema_version=1,kind=theme.PROBE_KIND,command=self.command,
            execution=dict(caller_exit=0,closed=True,writers_joined=True,inputs_unchanged=True,qualified_report=dict(schema_version=1,primary_returncode=0,descendants_outlived=False,reaped=1,error=None,terminated=False)),depfile=self.fact)
        self.supp=dict(schema_version=1,kind=theme.SUPPLEMENT_KIND,baseline_plan_sha256=theme.PINS['plan'],source=source_ref(),probe=self.probe_ref)
        class Capture:
            def __str__(inner):return str(self.root/'private/sdk-python')
            def write_text(inner,text,encoding):inner.raw=text.encode(encoding)
            def chmod(inner,mode):inner.mode=mode
        capture=Capture();maintenance.python_launcher('/usr/bin/python3.13',[self.base.roots['sdk']/'python.py'],capture)
        blobs=dict(vfs=maintenance.encoded(self.api._header_identity(self.base)['overlay']),
            configuration=("LLVM_ROOT = "+repr(str(self.base.roots['sdk']/'upstream/bin'))+"\nCACHE = "+repr(str(self.root/'private/cache'))+"\nFROZEN_CACHE = True\n").encode(),launcher=capture.raw)
        private={}
        for key,expected in self.command['private'].items():
            raw=blobs[key];private[key]=dict(expected,bytes=len(raw),identity=[1,9,0o100000|expected['mode'],1,len(raw),3,4]);self.api.raw[expected['path']]=raw
        self.probe['private']=private
        self.api.docs[self.probe_ref['path']]=self.probe;self.api.docs[self.supp_ref['path']]=self.supp
    def admit(self):return theme.admit_supplement(self.supp_ref,self.base,self.api)
    def test_pre_probe_derivation_uses_original_policy_without_context_or_writes(self):
        self.assertNotIn(theme.ORIGINAL_COMMAND, self.base.proof.get('contexts',{}))
        self.assertIn('-fsyntax-only',self.command['argv']);self.assertIn('-fno-exceptions',self.command['argv'])
        self.assertNotIn('-fexceptions',self.command['arguments'])
        self.assertEqual(theme.ORIGINAL_COMMAND,self.command['original_command_sha256'])
        self.assertEqual(str(self.root),self.command['cwd'])
    def test_exact_source_and_disjoint_output_fail_closed(self):
        for change in (dict(source_ref(),sha256=PIN),dict(source_ref(),path='foreign.cpp')):
            with self.subTest(change=change),self.assertRaises(ValueError):theme.derive_probe(self.base,change,self.root,self.api)
        with self.assertRaises(ValueError):theme.derive_probe(self.base,source_ref(),self.base.roots['sdk']/'out',self.api)
    def test_probe_receipt_closure_and_effective52_preserve_baseline(self):
        before=deepcopy(self.base.proof); admitted=self.admit()
        effective=theme.effective_inspection(self.base,admitted,self.api)
        self.assertEqual(before,self.base.proof)
        self.assertEqual((52,36,16),(len(effective.proof['objects']),len(effective.profile['direct_objects']),len(effective.profile['engine_objects'])))
        self.assertEqual(theme.THEME,effective.proof['objects'][35]['id'])
        self.assertFalse(effective.proof['objects'][35]['exceptions'])
        self.assertEqual(self.base.proof['replacements'],effective.proof['replacements'])
    def test_failed_incomplete_or_terminated_probe_is_not_admitted(self):
        for key,bad in (('caller_exit',1),('caller_exit',False),('closed',False),('writers_joined',False),('inputs_unchanged',False)):
            saved=deepcopy(self.probe['execution']);self.probe['execution'][key]=bad
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):self.admit()
            self.probe['execution']=saved
        self.probe['execution']['qualified_report']['terminated']=True
        with self.assertRaises(ValueError):self.admit()
    def test_changed_probe_private_context_or_retained_baseline_pin_is_rejected(self):
        for key in ('vfs','configuration','launcher'):
            saved=self.probe['private'][key]['sha256'];self.probe['private'][key]['sha256']=PIN
            with self.subTest(key=key),self.assertRaises(ValueError):self.admit()
            self.probe['private'][key]['sha256']=saved
        bad=maintenance.Inspection(dict(self.base.selection,reuse_proof_sha256=PIN),self.base.recipe,self.base.projection,self.base.proof,self.base.roots,self.base.inventories,self.base.profile)
        with self.assertRaises(ValueError):theme.derive_probe(bad,source_ref(),self.root,self.api)
    def test_changed_command_source_macro_overlay_or_baseline_is_rejected(self):
        for key,value in (('argv',self.command['argv']+['-DFORGED']),('original_command_sha256',PIN),('header_overlay_sha256',PIN),('sdk_manifest_sha256','2'*64)):
            saved=self.probe['command'];self.probe['command']=dict(saved,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):self.admit()
            self.probe['command']=saved
        self.supp['baseline_plan_sha256']=PIN
        with self.assertRaises(ValueError):self.admit()
    def test_depfile_target_missing_source_foreign_path_and_size_are_rejected(self):
        for raw in (b'wrong: /synthetic/current/sources/a.cpp\n',(self.command['target']+': /outside/unknown.h\n').encode(),(self.command['target']+':\n').encode()):
            self.api.raw[self.fact['path']]=raw
            with self.subTest(raw=raw),self.assertRaises(ValueError):self.admit()
        self.fact['bytes']=0
        with self.assertRaises(ValueError):self.admit()
    def test_crosslane_kind_unknown_fields_and_noninteger_schema_reject(self):
        for key,value in (('kind',donor.NATIVE_CONTROL_KEYPRESS_REPAIR_DONOR_KIND),('schema_version',True),('extra',None)):
            saved=deepcopy(self.supp);self.supp[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.admit()
            self.supp.clear();self.supp.update(saved)
    def test_actual_compile_closure_matches_sealed_probe_and_rejects_extra(self):
        admitted=self.admit();effective=theme.effective_inspection(self.base,admitted,self.api)
        output=Path('/synthetic/build');target=output/('objects/'+theme.THEME+'.o')
        raw=(str(target)+': '+str(self.base.roots['sources']/theme.SOURCE)+'\n').encode()
        self.api.raw[str(target)+'.d']=raw
        plan=dict(theme_supplement=self.supp_ref)
        with mock.patch.object(self.api,'profile',return_value=self.base.profile):theme.validate_compile_depfile(plan,effective,output,self.api)
        self.api.raw[str(target)+'.d']=raw.rstrip()+b' /outside/injected.h\n'
        with mock.patch.object(self.api,'profile',return_value=self.base.profile),self.assertRaises(ValueError):theme.validate_compile_depfile(plan,effective,output,self.api)

    def test_private_cache_list_uses_inventoried_seed_and_actual_bytes(self):
        # Production reuse proofs list seed filenames; hashes belong to the SDK inventory.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);cached=root/'private/cache/sysroot/include/header.h'
            cached.parent.mkdir(parents=True);cached.write_bytes(b'frozen header\n')
            logical='cache/sysroot/include/header.h';pin=hashlib.sha256(cached.read_bytes()).hexdigest()
            self.base.proof['private_cache']['files']=[logical]
            self.base.inventories['sdk'][logical]=pin
            command=dict(self.command,cwd=str(root))
            raw=(command['target']+': '+str(self.base.roots['sources']/theme.SOURCE)+' '+str(cached)+'\n').encode()
            original=self.api.checked_read
            def checked(path,*args,**kwargs):
                if path==cached:return maintenance.checked_read(path,*args,**kwargs)
                return original(path,*args,**kwargs)
            with mock.patch.object(self.api,'checked_read',side_effect=checked):
                refs=theme._dependency_refs(raw,command,self.base,self.api)
                self.assertIn(dict(root='sdk',path=logical,sha256=pin),refs)
                self.base.proof['private_cache']['files']=[]
                with self.assertRaisesRegex(ValueError,'unseeded'):theme._dependency_refs(raw,command,self.base,self.api)
                self.base.proof['private_cache']['files']=[logical];cached.write_bytes(b'changed header\n')
                with self.assertRaises(ValueError):theme._dependency_refs(raw,command,self.base,self.api)

class NamespaceMapTests(unittest.TestCase):
    def test_exact174_and_missing_shim_or_duplicate_selected_reject(self):
        names=base_fixture().profile['direct_objects']+[theme.THEME]+base_fixture().profile['engine_objects']
        self.assertEqual(174,len(theme.artifact_names(names,list(donor.ARCHIVE_COUNTS))))
        for bad in (names[:-1],names[:-1]+[names[0]],[n for n in names if n!=theme.SHIM]+['Other.cpp']):
            with self.assertRaises(ValueError):theme.artifact_names(bad,list(donor.ARCHIVE_COUNTS))
    def test_final_map_requires_fresh_singleton_override_and_unextracted_old_member(self):
        root=Path('/synthetic/output');owner=str(root/('objects/'+theme.THEME+'.o'))+':'
        lines=[owner+'(_ZN7WebCore11RenderTheme9singletonEv)',owner+'(_ZNK7WebCore21RenderThemeEmscripten23popsMenuBySpaceOrReturnEv)']
        self.assertFalse(theme.final_map(('\n'.join(lines)).encode(),root)['old_archive_member_extracted'])
        for bad in (lines[:1],lines[1:],lines+['libWebCore.a(RenderThemeEmscripten.cpp.o):old'],[x.replace(owner,'foreign.o:') for x in lines]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):theme.final_map(('\n'.join(bad)).encode(),root)

class EntryTests(unittest.TestCase):
    @staticmethod
    def cli():
        return ['plan',*sum((["--"+k.replace('_','-'), 'editor' if k=='document_profile' else PIN if k.endswith('sha256') else '/inert/'+k] for k in maintenance.SELECTION_FIELDS),[]),'--output','/inert/output']
    def test_cli_forwards_only_explicit_paired_theme_arguments(self):
        args=self.cli()+['--successful-donor','/inert/donor','--successful-donor-sha256',PIN,'--successful-donor-native-theme-repair','--theme-supplement','/inert/theme','--theme-supplement-sha256',PIN]
        with mock.patch.object(maintenance,'make_plan',return_value={}) as planner,mock.patch('sys.stdout',new_callable=io.StringIO):maintenance.main(args)
        self.assertEqual(dict(successful_donor=dict(path='/inert/donor',sha256=PIN),successful_donor_native_theme_repair=True,theme_supplement=dict(path='/inert/theme',sha256=PIN)),planner.call_args.kwargs)
    def test_api_rejects_unpaired_crosslane_and_nonboolean_before_inspection(self):
        good=dict(successful_donor={},successful_donor_native_theme_repair=True,theme_supplement={})
        invalid=[dict(good,successful_donor_native_theme_repair=v) for v in (1,0,None,'true')]
        invalid += [dict(good,**{k:True}) for k in ('successful_donor_guard_repair','successful_donor_composition_repair','successful_donor_native_capability_repair','successful_donor_native_control_keypress_repair')]
        invalid += [dict(good,successful_donor_guard_repair=0),dict(good,successful_donor_composition_repair=None),dict(good,completed_work={}),dict(good,theme_supplement=None),dict(theme_supplement={})]
        with mock.patch.object(maintenance,'inspect_inputs') as inspector:
            for kwargs in invalid:
                with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):maintenance.make_plan(dict(document_profile='editor'),Path('/inert/output'),**kwargs)
            inspector.assert_not_called()
    def test_new_plan_roundtrip_reconstructs_effective_graph_and_rejects_restamp(self):
        base=base_fixture();admitted=dict(reference=dict(path='/inert/donor',sha256=PIN),objects=[],original_bindings={},metadata_directories=[])
        supplement=dict(reference=dict(path='/inert/theme',sha256=PIN),probe=dict(path='/inert/probe',sha256=PIN),command=dict(cwd='/inert/probe-output'))
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(maintenance.engine_sdk,'new_destination',side_effect=lambda output,roots=():output),mock.patch.object(maintenance,'inspect_inputs',return_value=base),mock.patch.object(theme,'_helper_admitted'),mock.patch.object(theme,'admit_supplement',return_value=supplement),mock.patch.object(theme,'admit_donor',return_value=admitted),mock.patch.object(theme,'effective_inspection',return_value=base),mock.patch.object(maintenance,'_completed_input_directories',return_value=()),mock.patch.object(maintenance,'digest',return_value=PIN):
            result=maintenance.make_plan(base.selection,Path(tmp)/'plan',successful_donor=admitted['reference'],successful_donor_native_theme_repair=True,theme_supplement=supplement['reference'])
            plan,_=maintenance.verify_plan(Path(result['plan']),hashlib.sha256(Path(result['plan']).read_bytes()).hexdigest())
            self.assertEqual(theme.PLAN_KIND,plan['kind']);self.assertIn(theme.HELPER,plan['producer_inputs'])
            plan['reuse']=dict(plan['reuse'],objects=[])
            with self.assertRaises(ValueError):theme.verify_plan(plan,maintenance)


def test_reference(name):return dict(root="sources",path=name,sha256=PIN)

class GraphTests(unittest.TestCase):
    def test_graph_routes_exact_two_compiles_50_imports_and_no_repack(self):
        import appended_engine_successful_donor as donor
        fresh = theme.FRESH
        direct = list(fresh) + ['Direct%02d.cpp' % i for i in range(34)]
        engine = ['Engine%02d.cpp' % i for i in range(16)]
        selected = direct + engine
        archives = list(donor.ARCHIVE_COUNTS)
        with tempfile.TemporaryDirectory(prefix='inert-native-control-keypress-graph-') as temporary:
            root = Path(temporary).resolve(); (root / 'cmake').mkdir()
            metadata = {name: test_reference(name) for name in ('generator', 'template', 'prelink_plan', *maintenance.metadata_interface_paths('editor'))}
            proof = {'host_tools': {'python': {'path': '/inert/python'}},
                'sdk_tools': {name: {'path': name} for name in ('emxx', 'emranlib')}, 'metadata': metadata,
                'objects': [{'id': name, 'arguments': [], 'source': test_reference(name), 'dependencies': [], 'unified_members': []} for name in selected],
                'replacements': [], 'archives': [{'name': name, 'members': []} for name in archives],
                'link': {'dependencies': [], 'archives': archives, 'flags': [], 'data': [], 'pre_js': test_reference('pre.js'), 'host_library': test_reference('host.js')}}
            imported = [name for name in selected if name not in fresh]
            work = {'objects': [{'id': name, 'object': {'path': '/inert/' + name + '.o'}, 'depfile': {'path': '/inert/' + name + '.o.d'}} for name in imported],
                    'archives': [{'name': name, 'archive': {'path': '/inert/lib' + name + '.a'}, 'report': {'path': '/inert/archive-' + name + '.json'}} for name in archives]}
            plan = {'kind': maintenance.NATIVE_THEME_REPAIR_PLAN_KIND, 'successful_donor': work}
            inspected = SimpleNamespace(proof=proof, roots={'sources': root / 'sources', 'sdk': root / 'sdk'}, inventories={},
                selection={'document_profile': 'editor'}, profile={'direct_objects': direct})
            with mock.patch.object(maintenance, '_tool', return_value=Path('/inert/python')), \
                 mock.patch.object(maintenance, 'ref_path', side_effect=lambda ref, roots, inv: root / ref['path']), \
                 mock.patch.object(maintenance, '_arguments', return_value=[]), \
                 mock.patch.object(maintenance, '_header_identity', return_value=None):
                _, fragment, commands = maintenance._graph(inspected, plan, root / 'plan.json', PIN, root)
            self.assertEqual(list(fresh), list(commands['objects']))
            self.assertLess(commands['link'].index(str(root/'objects'/ (theme.THEME+'.o'))), commands['link'].index(str(root/'archives/libWebCore.a')))
            self.assertIn(maintenance.THEME_SUCCESSOR_HELPER, fragment.read_text())
            self.assertEqual(imported, list(commands['imports']))
            self.assertEqual((52, 50, 2, 5), (len(selected), len(commands['imports']), len(commands['objects']), len(commands['archive_imports'])))
            self.assertTrue(all(cmd[-3] == 'import' for cmd in commands['imports'].values()))
            self.assertIn(maintenance.SUCCESSFUL_HELPER, fragment.read_text())
            self.assertEqual(1, sum(token.endswith('foundation-retained-engine.mjs') for token in commands['link']))


class F6CompilerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.base=base_fixture();self.api=FakeAPI(self.base)
        self.bindings=dict(self.base.roots,build=Path('/synthetic/f6-build'))
        self.records={};self.freeze=dict(files={});self.commands=dict(objects={});self.rows=[];ledger=[]
        def fact(path,raw):
            p=str(path);self.api.raw[p]=raw
            return dict(path=p,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),mode=420,identity=[1,len(self.api.raw),33188,1,len(raw),7,8])
        self.fact=fact
        for obj in self.base.proof['objects'][:6]:
            name=obj['id'];source=self.bindings['sources']/obj['source']['path'];sf=fact(source,('source '+name).encode())
            obj['source']['sha256']=sf['sha256'];self.base.inventories['sources'][obj['source']['path']]=sf['sha256'];self.freeze['files'][str(source)]=sf
            target=str(self.bindings['build']/('objects/'+name+'.o'))
            pf=fact(target,('object '+name).encode());inputs=[str(source)]
            if name==theme.SHIM:inputs.append(str(self.bindings['build']/'document-generated/BibCopiedDocumentMetadata.generated.h'))
            df=fact(target+'.d',(target+': '+' '.join(inputs)+'\n').encode())
            self.records['objects/'+name+'.o']=pf;self.records['objects/'+name+'.o.d']=df
            argv=['/synthetic/sdk/em++','-MD','-MT',target,'-MF',target+'.d','-o',target,'-c',str(source)]
            self.commands['objects'][name]=argv
            nr=['0','1','7',target,'synthetic-hash'];ledger.append('\t'.join(nr))
            self.rows.append(dict(id=name,ninja_record=nr,ninja_command='synthetic command',command_script=None))
        self.value=dict(f6_compiled=self.rows,f6_ninja_log=fact(self.bindings['build']/'cmake/build/.ninja_log',('# ninja log v6\n'+'\n'.join(ledger)+'\n').encode()))
    def run_admission(self):
        with mock.patch.object(self.api,'_completed_arguments',return_value=[]),mock.patch.object(self.api,'_completed_ninja_command',return_value='synthetic-hash'):
            return theme._f6_compiled_rows(self.value,self.base,self.bindings,self.freeze,self.records,self.commands,self.api)
    def test_all_six_actual_interface_depfiles_only_five_import_and_no_generated_import(self):
        imported,refs=self.run_admission()
        self.assertEqual(5,len(imported));self.assertNotIn(theme.SHIM,[r['id'] for r in imported]);self.assertEqual(6,len(refs))
        self.assertTrue(all(r['original_argv']==self.commands['objects'][r['id']] for r in imported))
    def test_compiler_target_source_ninja_and_frozen_input_fail_closed(self):
        original=deepcopy(self.commands);name=self.rows[0]['id']
        for marker in ('-o','-MT','-MF','-c'):
            self.commands=deepcopy(original);a=self.commands['objects'][name];a[a.index(marker)+1]='/synthetic/foreign'
            with self.subTest(marker=marker),self.assertRaises(ValueError):self.run_admission()
        self.commands=original;self.rows[0]['ninja_record'][1]='0';self.rows[0]['ninja_record'][0]='2'
        with self.assertRaises(ValueError):self.run_admission()
    def test_missing_context_or_forged_generated_owner_is_rejected(self):
        key=next(iter(self.freeze['files']));saved=self.freeze['files'].pop(key)
        with self.assertRaises(ValueError):self.run_admission()
        self.freeze['files'][key]=saved
        name=next(r['id'] for r in self.rows if r['id']!=theme.SHIM)
        target=str(self.bindings['build']/('objects/'+name+'.o'))
        p=self.records['objects/'+name+'.o.d']['path'];self.api.raw[p]=self.api.raw[p].rstrip()+(' '+str(self.bindings['build']/'document-generated/BibCopiedDocumentMetadata.generated.h')+'\n').encode()
        with self.assertRaises(ValueError):self.run_admission()
    def test_donor_crosslane_missing_pin_or_fields_rejected_before_products(self):
        ref=dict(path='/synthetic/theme-donor.json',sha256=PIN)
        self.api.docs[ref['path']]=dict(schema_version=1,kind=donor.NATIVE_CONTROL_KEYPRESS_REPAIR_DONOR_KIND)
        with self.assertRaises(ValueError):theme.admit_donor(ref,self.base,self.api)
        with self.assertRaises(ValueError):theme.reference(dict(path=ref['path'],sha256=PIN),self.api,theme.PINS['root_acceptance'])

class ReceiptTests(unittest.TestCase):
    def test_real174_receipt_keeps_two_fresh_and50_import_provenances(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);base=base_fixture();selected=base.profile['direct_objects']+[theme.THEME]+base.profile['engine_objects']
            archives=list(donor.ARCHIVE_COUNTS);expected=theme.artifact_names(selected,archives)
            for name in expected:
                f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b'inert')
            work=dict(reference=dict(path='/synthetic/donor',sha256=PIN),objects=[],archives=[])
            results=[]
            for name in selected:
                target=root/('objects/'+name+'.o');sha=maintenance.digest(target)
                results.append(dict(id=name,sha256=sha,bytes=5))
                if name in theme.FRESH:continue
                fact=dict(path='/synthetic/old/'+name+'.o',sha256=sha,bytes=5,mode=420,identity=[99,1,33188,1,5,1,1])
                df=dict(fact,path='/synthetic/old/'+name+'.o.d')
                row=dict(id=name,object=fact,depfile=df,command_sha256=PIN,original_argv=['synthetic'],original_cwd='/synthetic',ninja_record=[],ninja_command='synthetic',command_script=None,donor_provenance=dict(kind='foundation-document-v2-native-theme-object-provenance-v1'))
                work['objects'].append(row)
                receipt=dict(kind='foundation-document-v2-object-import-v1',id=name,production_eligible=False,origin='imported',compiler_invoked=False,hardlinked=False,sha256=sha,bytes=5,object=fact,original_depfile=df,original_command_sha256=PIN,original_argv=row['original_argv'],original_cwd=row['original_cwd'],ninja_record=[],ninja_command='synthetic',command_script=None,donor_provenance=row['donor_provenance'])
                (root/('evidence/import-'+name+'.json')).write_bytes(maintenance.encoded(receipt))
            for name in archives:
                target=root/('archives/lib'+name+'.a');sha=maintenance.digest(target)
                fact=dict(path='/synthetic/old/lib'+name+'.a',sha256=sha,bytes=5,mode=420,identity=[99,1,33188,1,5,1,1]);report=dict(fact,path='/synthetic/old/archive-'+name+'.json')
                work['archives'].append(dict(name=name,archive=fact,report=report))
                receipt=dict(kind='foundation-document-v2-archive-import-v1',name=name,origin='imported',archive=fact,original_report=report,destination=str(target),hardlinked=False,archive_program_invoked=False,production_eligible=False,sha256=sha,bytes=5)
                (root/('evidence/import-archive-'+name+'.json')).write_bytes(maintenance.encoded(receipt))
            owner=str(root/('objects/'+theme.THEME+'.o'))+':'
            (root/'evidence/engine-link.map').write_text(owner+'(_ZN7WebCore11RenderTheme9singletonEv)\n'+owner+'(_ZNK7WebCore21RenderThemeEmscripten23popsMenuBySpaceOrReturnEv)\n')
            plan=dict(kind=theme.PLAN_KIND,successful_donor=work,theme_supplement=dict(path='/synthetic/theme',sha256=PIN),reuse=dict(objects=[dict(id=n) for n in selected]))
            inspected=SimpleNamespace(proof=dict(objects=[dict(id=n) for n in selected],archives=[dict(name=n) for n in archives]))
            commands=dict(objects={n:[] for n in theme.FRESH},imports={n:[] for n in selected if n not in theme.FRESH},archive_imports={n:[] for n in archives})
            result=dict(objects=deepcopy(results))
            with mock.patch.object(theme,'validate_compile_depfile'):
                theme.build_receipt(result,plan,inspected,root,commands,maintenance)
            self.assertEqual((52,2,50,5,0,174),(result['accounting']['selected'],result['accounting']['compiled'],result['accounting']['imported'],result['accounting']['archive_imported'],result['accounting']['archive_repacked'],result['expected_artifact_records']))
            row=work['objects'][0];f=root/('evidence/import-'+row['id']+'.json');bad=json.loads(f.read_text());bad['compiler_invoked']=True;f.write_bytes(maintenance.encoded(bad))
            with mock.patch.object(theme,'validate_compile_depfile'),self.assertRaises(ValueError):theme.build_receipt(dict(objects=deepcopy(results)),plan,inspected,root,commands,maintenance)


class FullDonorTests(F6CompilerEvidenceTests):
    def setUp(self):
        super().setUp();base=self.base;api=self.api;names=[o['id'] for o in base.proof['objects']];fresh=set(donor.NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS)
        for obj in base.proof['objects']:
            base.inventories['sources'][obj['source']['path']] = obj['source']['sha256']
        self.refs={k:dict(path='/synthetic/authority/'+k+'.json',sha256=v) for k,v in theme.PINS.items()}
        f6ref=dict(path='/synthetic/authority/f6-donor.json',sha256=PIN)
        self.value.update(schema_version=1,kind=theme.DONOR_KIND,document_profile='editor',f6_donor=f6ref,bindings={k:str(v) for k,v in self.bindings.items()},f6_private=dict(vfs=dict(sha256=PIN),configuration=dict(sha256=PIN),launcher=dict(sha256=PIN)),**self.refs)
        selected_archives=[a['name'] for a in base.proof['archives']]
        accounting=dict(selected=51,compiled=6,imported=45,archive_imported=5,archive_repacked=0,compiled_ids=[n for n in names if n in fresh],imported_ids=[n for n in names if n not in fresh],imported_archive_names=selected_archives)
        old_selection=dict(base.selection,sources=str(base.roots['sources']),sdk=str(base.roots['sdk']),reuse_root=str(base.roots['reuse']))
        self.old=dict(kind=maintenance.NATIVE_CONTROL_KEYPRESS_REPAIR_PLAN_KIND,production_eligible=False,reuse=deepcopy(base.proof),profile_sha256=PIN,successful_donor=dict(reference=f6ref),selection=old_selection,projection={})
        for name,doc in (('sources.json',dict(files={k:v for k,v in base.inventories['sources'].items() if k != theme.SOURCE})),('recipe.json',{})):
            raw=maintenance.encoded(doc);fact=self.fact(base.roots['sources']/name,raw);self.freeze['files'][str(base.roots['sources']/name)]=fact
            self.old['selection']['sources_sha256' if name=='sources.json' else 'recipe_sha256']=fact['sha256']
        self.freeze['roots']={k:str(v) for k,v in self.bindings.items() if k!='build'}
        legacy_objects=[]
        for name in names:
            if name in fresh:continue
            raw=('import '+name).encode();original=self.fact('/synthetic/legacy/'+name+'.o',raw);dep=self.fact('/synthetic/legacy/'+name+'.d',b'legacy dep')
            row=dict(id=name,object=original,depfile=dep,dependency_keys=[],donor_provenance=dict(p5='synthetic'))
            legacy_objects.append(row)
            obj=self.fact(self.bindings['build']/('objects/'+name+'.o'),raw);self.records['objects/'+name+'.o']=obj
            receipt=dict(object=original,original_depfile=dep,compiler_invoked=False,hardlinked=False,donor_provenance=row['donor_provenance'],destination=obj['path'],sha256=obj['sha256'],bytes=obj['bytes'])
            self.records['evidence/import-'+name+'.json']=self.fact(self.bindings['build']/('evidence/import-'+name+'.json'),maintenance.encoded(receipt))
            self.records['evidence/import-'+name+'.original.d']=self.fact(self.bindings['build']/('evidence/import-'+name+'.original.d'),b'legacy dep')
        legacy_archives=[]
        for name in selected_archives:
            raw=('archive '+name).encode();old_archive=self.fact('/synthetic/legacy/lib'+name+'.a',raw)
            report_raw=maintenance.encoded(dict(name=name,sha256=old_archive['sha256'],members=[]));old_report=self.fact('/synthetic/legacy/archive-'+name+'.json',report_raw)
            legacy_archives.append(dict(name=name,archive=old_archive,report=old_report))
            self.records['archives/lib'+name+'.a']=self.fact(self.bindings['build']/('archives/lib'+name+'.a'),raw)
            self.records['evidence/archive-'+name+'.json']=self.fact(self.bindings['build']/('evidence/archive-'+name+'.json'),report_raw)
        for name in donor.native_control_keypress_artifact_names(names,selected_archives):
            if name not in self.records:self.records[name]=self.fact(self.bindings['build']/name,b'inert')
        api.docs['/synthetic/legacy/sidecar']=dict(dependencies={})
        self.legacy=dict(objects=legacy_objects,archives=legacy_archives,original_bindings=ORIGINAL['bindings'],dependency_sidecar=dict(path='/synthetic/legacy/sidecar',sha256=PIN),additional_input_directories=[],metadata_directories=['/synthetic/legacy'])
        report=dict(schema_version=1,primary_returncode=0,descendants_outlived=False,reaped=1,error=None,terminated=False)
        self.root=dict(kind='root-closed-successful-donor-native-control-keypress-repair-candidate-accepted-v1',actual_session=40718,caller_observed_exit=0,status='passed',closed=True,writers_joined=True,inputs_unchanged=True,all_artifact_physical_identities_root_rechecked=True,verified_artifact_records=167,production_eligible=False,qualified_report=report,records=dict(closed=self.refs['closed_result'],commands=self.refs['commands'],maintenance_build=self.refs['maintenance_build'],plan=self.refs['plan'],donor_descriptor=f6ref))
        result=dict(closed=True,verified=True,writers_joined=True,runtime_not_run=True,status='passed',returncode=0,supervisor_report=report,input_identity_namespace_postflight='passed',static_byte_readback='passed',actual_objects=51,actual_archive_reports=5,opaque_unchanged_members=2060,successful_donor=dict(accounting=accounting),maintenance_build_sha256=self.refs['maintenance_build']['sha256'],artifact_records=self.records)
        build=dict(kind=maintenance.NATIVE_CONTROL_KEYPRESS_REPAIR_BUILD_KIND,status='passed',accounting=accounting,commands=dict(path='evidence/commands.json',sha256=self.refs['commands']['sha256']),private_configuration=dict(config_sha256=PIN,launcher_sha256=PIN))
        self.refs['maintenance_build']['path']=str(self.bindings['build']/'maintenance-build.json');self.refs['commands']['path']=str(self.bindings['build']/'evidence/commands.json')
        packet=dict(output=str(self.bindings['build']),selection=self.old['selection'],plan_sha256=self.refs['plan']['sha256'],freeze=self.refs['input_freeze']['path'],freeze_sha256=self.refs['input_freeze']['sha256'])
        self.commands['imports']={n:[] for n in names if n not in fresh}
        docs=dict(root_acceptance=self.root,closed_result=result,plan=self.old,maintenance_build=build,commands=self.commands,build_packet=packet,input_freeze=self.freeze)
        for key,doc in docs.items():api.docs[self.refs[key]['path']]=doc
        self.donor_ref=dict(path='/synthetic/authority/theme-donor.json',sha256=PIN);api.docs[self.donor_ref['path']]=self.value
    def admit_full(self):
        def legacy_admission(ref, inspection, api):
            self.assertIsNot(inspection,self.base)
            self.assertNotIn(theme.SOURCE,inspection.inventories['sources'])
            return dict(self.legacy, object_dependencies={row['id']:[next(obj['source'] for obj in self.base.proof['objects'] if obj['id']==row['id'])] for row in self.legacy['objects']})
        helper=SimpleNamespace(NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS=donor.NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS,_fact_shape=donor._fact_shape,_p5_flat_fact=lambda fact,api:fact,native_control_keypress_dependency_admission=legacy_admission,native_control_keypress_artifact_names=donor.native_control_keypress_artifact_names)
        def synthetic_context(i,*args):
            return dict(directories=[],namespace=({} if i is not self.base else {'{sources}/'+theme.SOURCE:theme.SOURCE_SHA256}),physical_headers_sha256=PIN,vfs={})
        with mock.patch.object(self.api,'_completed_header_context',side_effect=synthetic_context),mock.patch.object(self.api,'_successful_module',return_value=helper),mock.patch.object(self.api,'_completed_binding',side_effect=lambda d:{k:Path(v) for k,v in d.items()}),mock.patch.object(self.api,'_completed_private_context',return_value={}),mock.patch.object(self.api,'_completed_normalize_vfs',return_value={}),mock.patch.object(self.api,'_completed_arguments',return_value=[]),mock.patch.object(self.api,'_completed_ninja_command',return_value='synthetic-hash'):
            return theme.admit_donor(self.donor_ref,self.base,self.api)
    def test_full_real_new_donor_interface_admits50_with_five_f6_histories(self):
        admitted=self.admit_full()
        self.assertEqual(50,len(admitted['objects']));self.assertEqual(5,sum(r['donor_provenance']['compile_origin']=='f6-compiled' for r in admitted['objects']))
        self.assertEqual(5,len(admitted['archives']));self.assertNotIn(theme.SHIM,[r['id'] for r in admitted['objects']])
    def test_original_root_failure_and_changed_legacy51_proof_reject(self):
        self.root['closed']=False
        with self.assertRaises(ValueError):self.admit_full()
        self.root['closed']=True;self.old['reuse']['objects'][0]['arguments']=['-DFORGED']
        with self.assertRaises(ValueError):self.admit_full()


class InternalActionTests(unittest.TestCase):
    def test_internal_theme_plan_imports_and_refuses_archive_programs(self):
        output = Path('/inert/fresh-output')
        plan = {'kind': maintenance.NATIVE_THEME_REPAIR_PLAN_KIND, 'production_eligible': False, 'reuse': {},
            'selection': {'sources': '/inert/sources', 'sdk': '/inert/sdk', 'reuse_root': '/inert/reuse'}}
        owner = {'schema_version': 1, 'plan_sha256': PIN, 'output': str(output), 'producer_sha256': PIN}
        args = SimpleNamespace(plan=Path('/inert/plans/plan.json'), plan_sha256=PIN, build_root=output,
            action='import', object='Imported.cpp', archive='WebCore')
        with mock.patch.object(maintenance, 'checked_document', side_effect=lambda p, *pins: plan if p == args.plan else owner), \
             mock.patch.object(maintenance, 'ordinary', side_effect=lambda p, *a, **kw: Path(p)), \
             mock.patch.object(maintenance, 'digest', return_value=PIN), \
             mock.patch.object(maintenance, '_copy_completed_object', return_value='object') as obj, \
             mock.patch.object(maintenance, '_copy_successful_archive', return_value='archive') as archive, \
             mock.patch.object(maintenance.os, 'execv') as execute:
            self.assertEqual('object', maintenance._step(args)); obj.assert_called_once_with(plan, 'Imported.cpp', output)
            args.action = 'import-archive'
            self.assertEqual('archive', maintenance._step(args)); archive.assert_called_once_with(plan, 'WebCore', output)
            for action in ('archive', 'repack'):
                args.action = action
                with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'zero repacks'): maintenance._step(args)
            execute.assert_not_called()

    def test_theme_build_refuses_parallel_jobs_before_any_output_or_tool(self):
        with mock.patch.object(maintenance,'ordinary',side_effect=lambda p,*a,**k:Path(p)),mock.patch.object(maintenance,'verify_plan',return_value=(dict(kind=theme.PLAN_KIND),None)),mock.patch.object(maintenance,'_supervise') as launch:
            with self.assertRaisesRegex(ValueError,'one compiler job'):maintenance.build(Path('/inert/plan'),PIN,Path('/inert/output'),jobs=2)
            launch.assert_not_called()

class RealNamespaceExtensionTests(unittest.TestCase):
    def test_real_namespace_allows_only_exact_reviewed_tu(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);roots={k:root/k for k in ('sources','sdk','reuse')}
            for value in roots.values():value.mkdir()
            (roots['sources']/'source/engine/Source/WebCore').mkdir(parents=True)
            (roots['sdk']/'upstream/lib/clang/24/include').mkdir(parents=True)
            (roots['sdk']/'cache/sysroot/include').mkdir(parents=True)
            prefix='source/engine/Source/WebCore/'
            prior={prefix+'Header.h':PIN,prefix+'Old.cpp':PIN}
            base=base_fixture()
            def inspect(files):
                return maintenance.Inspection(base.selection,{}, {},base.proof,roots,dict(sources=files,sdk={},reuse={}),base.profile)
            obj=[dict(arguments=['-I{sources}/source/engine/Source/WebCore'])]
            with mock.patch.object(maintenance,'_header_identity',return_value=dict(original_files={},overlay={})),mock.patch.object(maintenance,'_completed_normalize_vfs',return_value={}):
                old=maintenance._completed_header_context(inspect(prior),[],obj)
                current=maintenance._completed_header_context(inspect(dict(prior,**{theme.SOURCE:theme.SOURCE_SHA256})),[],obj)
                theme.context_extension(old,current,maintenance)
                for key,pin in ((prefix+'Extra.cpp',PIN),(prefix+'Extra.h',PIN),(prefix+'Header.h','2'*64)):
                    changed=dict(prior,**{theme.SOURCE:theme.SOURCE_SHA256,key:pin})
                    actual=maintenance._completed_header_context(inspect(changed),[],obj)
                    with self.subTest(key=key),self.assertRaises(ValueError):theme.context_extension(old,actual,maintenance)

if __name__ == "__main__":unittest.main()
