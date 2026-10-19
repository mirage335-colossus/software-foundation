"""Input-method selective producer metadata boundaries; no SDK program executes."""
from copy import deepcopy
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_document_maintenance as api
import appended_engine_input_method_successor as successor
import appended_engine_select_event_successor as selected

PIN = 'a' * 64
ARCHIVES = ['JavaScriptCore', 'PAL', 'Skia', 'WTF', 'WebCore']


def ref(name, pin=PIN):
    return dict(root='sources', path=name, sha256=pin)


def fixture():
    direct = [successor.SHIM, 'BibCopiedDocumentBinding.cpp', successor.MAIN] + ['Direct%d.cpp' % i for i in range(32)]
    engine = [successor.OWNER] + ['Engine%d.cpp' % i for i in range(15)]
    def obj(name):
        source = ref('source/' + name)
        return dict(id=name, source=source, dependencies=[], arguments=[], exceptions=False,
            unified_members=[], compile_context=dict(source=deepcopy(source), headers=[],
                arguments=[], macros=[], generated_metadata=[], sdk_manifest_sha256=PIN))
    old = dict(objects=[obj(n) for n in direct + engine], metadata={},
        header_identity=ref(selected.HEADER_IDENTITY_SOURCE))
    old['objects'].insert(35, obj(successor.THEME))
    proposed = deepcopy(old)
    proposed['header_identity'] = ref(successor.HEADER_IDENTITY_SOURCE)
    proposed['objects'] = [o for o in proposed['objects'] if o['id'] != successor.THEME]
    roots = {name: Path('/synthetic') / name for name in ('sources', 'sdk', 'reuse')}
    profile = dict(direct_objects=direct, engine_objects=engine, source_bindings={}, derived_commands={})
    base = api.Inspection(dict(document_profile='editor', sdk_manifest_sha256=PIN), {}, {}, proposed,
        roots, dict(sources={successor.HEADER_SOURCE: successor.HEADER_AFTER_SHA256,
            successor.HEADER_IDENTITY_SOURCE: PIN}, sdk={}, reuse={}), profile)
    authority = dict(plan=dict(reuse=old, selection=base.selection), bindings=dict(sdk=roots['sdk']))
    return base, authority


class BoundaryTests(unittest.TestCase):
    def effective(self, base, authority):
        with mock.patch.object(api, '_current_context'), mock.patch.object(api, 'ref_path'), \
             mock.patch.object(api, 'checked_read', return_value=b'x' * successor.HEADER_AFTER_BYTES):
            return successor.effective_inspection(base, authority, api)

    def test_header_only_transition_preserves52_graph_and_accepted_leaf(self):
        base, authority = fixture()
        result = self.effective(base, authority)
        self.assertEqual(52, len(result.proof['objects']))
        self.assertEqual(successor.THEME, result.proof['objects'][35]['id'])
        self.assertEqual(authority['plan']['reuse']['objects'], result.proof['objects'])
        self.assertEqual((successor.SHIM, successor.MAIN), successor.FRESH)
        self.assertEqual(174, len(successor.artifact_names([o['id'] for o in result.proof['objects']], ARCHIVES)))
        self.assertIn('evidence/import-' + successor.OWNER + '.original.d',
            successor.artifact_names([o['id'] for o in result.proof['objects']], ARCHIVES))
        names=[o['id'] for o in result.proof['objects']]
        names[names.index(successor.OWNER)]='foreign-owner.cpp'
        with self.assertRaises(ValueError):successor.artifact_names(names,ARCHIVES)

    def test_changed_source_compiler_unified_or_dependency_is_not_header_authority(self):
        for part in ('source', 'arguments', 'dependencies', 'unified_members'):
            base, authority = fixture()
            obj = next(o for o in base.proof['objects'] if o['id'] == successor.OWNER)
            if part == 'source': obj[part]['sha256'] = 'b' * 64
            else: obj[part] = ['-DCHANGED'] if part == 'arguments' else [ref('foreign.h')]
            with self.subTest(part=part), self.assertRaisesRegex(ValueError, 'proof changes'):
                self.effective(base, authority)

    def test_context_allows_exactly_reviewed_header_and_no_other_namespace_or_vfs_delta(self):
        key = '{sources}/' + successor.HEADER_SOURCE
        before = dict(directories=[], namespace={key: successor.HEADER_BEFORE_SHA256, '{sources}/main.cpp': PIN},
            physical_headers_sha256=PIN, vfs={})
        after = deepcopy(before); after['namespace'][key] = successor.HEADER_AFTER_SHA256
        successor.context_transition(before, after, api)
        for field in ('namespace', 'directories', 'physical_headers_sha256', 'vfs'):
            bad = deepcopy(after)
            if field == 'namespace': bad[field]['{sources}/main.cpp'] = 'b' * 64
            elif field == 'directories': bad[field] = ['{sdk}/foreign']
            elif field == 'vfs': bad[field] = {'foreign': 'mapping'}
            else: bad[field] = 'b' * 64
            with self.subTest(field=field), self.assertRaises(ValueError): successor.context_transition(before, bad, api)
        with mock.patch.object(successor, 'HEADER_AFTER_SHA256', None), self.assertRaises(ValueError):
            successor.context_transition(before, after, api)

    def test_complete_actual_depfile_census_requires_main_as_sole_header_owner(self):
        base, authority = fixture()
        names = [o['id'] for o in authority['plan']['reuse']['objects']]
        closures = {name: [] for name in names}
        closures[successor.MAIN] = [ref(successor.HEADER_SOURCE, successor.HEADER_BEFORE_SHA256)]
        successor.validate_dependency_owners(closures)
        for name in (successor.SHIM, successor.OWNER, successor.THEME):
            bad = deepcopy(closures); bad[name].append(ref(successor.HEADER_SOURCE))
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'sole actual compiler owner'):
                successor.validate_dependency_owners(bad)
        del closures[names[-1]]
        with self.assertRaisesRegex(ValueError, 'all52'): successor.validate_dependency_owners(closures)

    def test_fresh_main_readback_requires_postimage_header(self):
        good = [ref(successor.HEADER_SOURCE, successor.HEADER_AFTER_SHA256)]
        successor.validate_fresh_members(successor.MAIN, good, None)
        for bad in ([], [ref(successor.HEADER_SOURCE, successor.HEADER_BEFORE_SHA256)]):
            with self.assertRaisesRegex(ValueError, 'fresh main depfile'): successor.validate_fresh_members(successor.MAIN, bad, None)

    def test_metadata_overlay_has_distinct_paths_and_rejects_cycles(self):
        root = Path('/sources')
        selection = dict(document_profile='editor', reuse_proof_sha256=PIN)
        successor.validate_proof_location(selection, root / successor.PROOF_SOURCE, root, {successor.PROOF_SOURCE: PIN})
        successor.validate_metadata_overlay(dict(header_identity=ref(successor.HEADER_IDENTITY_SOURCE)))
        with self.assertRaises(ValueError):
            successor.validate_proof_location(selection, root / selected.PROOF_SOURCE, root, {selected.PROOF_SOURCE: PIN})
        for name in (successor.PROOF_SOURCE, 'sources.json', 'recipe.json'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'hash cycle'):
                successor.validate_metadata_overlay(dict(header_identity=ref(successor.HEADER_IDENTITY_SOURCE), metadata=dict(other=ref(name))))


class InterfaceTests(unittest.TestCase):
    def test_api_routes_explicit_lane_and_refuses_every_mixed_lane(self):
        with mock.patch.object(successor, 'make_plan', return_value={}) as plan:
            api.make_plan(dict(document_profile='editor'), Path('/out'), successful_donor={}, successful_donor_input_method_repair=True)
            self.assertEqual(api, plan.call_args.args[-1])
        lanes = ('guard', 'composition', 'native_capability', 'native_control_keypress', 'native_theme', 'native_showpicker', 'select_event')
        for lane in lanes:
            with self.subTest(lane=lane), self.assertRaisesRegex(ValueError, 'exclusive'):
                api.make_plan(dict(document_profile='editor'), Path('/out'), successful_donor={},
                    successful_donor_input_method_repair=True, **{'successful_donor_' + lane + '_repair': True})
        with self.assertRaisesRegex(ValueError, 'strict boolean'):
            api.make_plan({}, Path('/out'), successful_donor_input_method_repair=1)

    def test_real_cli_forwards_and_rejects_mixed_lane_before_io(self):
        args = ['plan']
        for name in api.SELECTION_FIELDS:
            args += ['--' + name.replace('_', '-'), 'editor' if name == 'document_profile' else PIN]
        args += ['--output', '/out', '--successful-donor', '/donor', '--successful-donor-sha256', PIN,
            '--successful-donor-input-method-repair']
        with mock.patch.object(api, 'make_plan', return_value={}) as plan, contextlib.redirect_stdout(io.StringIO()): api.main(args)
        self.assertIs(plan.call_args.kwargs['successful_donor_input_method_repair'], True)
        with mock.patch.object(api, 'make_plan') as plan, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            api.main(args + ['--successful-donor-select-event-repair'])
        plan.assert_not_called()

    def test_verifier_dispatch_and_one_job_guard_before_programs(self):
        value = dict(kind=successor.PLAN_KIND)
        with mock.patch.object(api, 'checked_document', return_value=value), mock.patch.object(successor, 'verify_plan', return_value='routed') as verify:
            self.assertEqual('routed', api.verify_plan(Path('/plan'), PIN))
            verify.assert_called_once_with(value, api)
        with mock.patch.object(api, 'ordinary', side_effect=lambda p,*a,**k: Path(p)), \
             mock.patch.object(api, 'verify_plan', return_value=(value, None)), mock.patch.object(api, '_supervise') as launch:
            with self.assertRaisesRegex(ValueError, 'one compiler job'): api.build(Path('/plan'), PIN, Path('/out'), jobs=2)
            launch.assert_not_called()

    def test_internal_repack_is_rejected_for_new_kind(self):
        value = dict(kind=successor.PLAN_KIND, production_eligible=False, reuse={},
            selection=dict(sources='/in/sources', sdk='/in/sdk', reuse_root='/in/reuse'))
        owner = dict(schema_version=1, plan_sha256=PIN, output='/out', producer_sha256=PIN)
        with mock.patch.object(api, 'checked_document', side_effect=[value, owner]), \
             mock.patch.object(api, 'ordinary', side_effect=lambda p,*a,**k: Path(p)), mock.patch.object(api, 'digest', return_value=PIN):
            with self.assertRaisesRegex(ValueError, 'zero repacks'):
                api._step(SimpleNamespace(plan='/plans/plan.json', plan_sha256=PIN, build_root='/out', action='repack'))

    def test_real_graph_fresh_main_shim_imported_unified_direct_once_and_five_copies(self):
        base, authority = fixture()
        proof = deepcopy(authority['plan']['reuse'])
        proof.update(host_tools=dict(python=dict(path='/inert/python')), sdk_tools={n: dict(path=n) for n in ('emxx','emranlib')},
            replacements=[dict(archive='WebCore',ordinal=0,object_id=successor.OWNER)],
            archives=[dict(name=n,members=[]) for n in ARCHIVES],
            link=dict(dependencies=[],archives=ARCHIVES,flags=[],data=[],pre_js=ref('pre.js'),host_library=ref('host.js')))
        proof['metadata'] = {n:ref(n) for n in ('generator','template','prelink_plan',*api.metadata_interface_paths('editor'))}
        direct = base.profile['direct_objects'] + [successor.THEME]
        with tempfile.TemporaryDirectory(prefix='input-method-graph-') as tmp:
            root=Path(tmp).resolve();(root/'cmake').mkdir()
            imported=[o['id'] for o in proof['objects'] if o['id'] not in successor.FRESH]
            work=dict(objects=[dict(id=n,object=dict(path='/inert/'+n+'.o'),depfile=dict(path='/inert/'+n+'.d')) for n in imported],
                archives=[dict(name=n,archive=dict(path='/inert/lib'+n+'.a'),report=dict(path='/inert/'+n+'.json')) for n in ARCHIVES])
            inspected=SimpleNamespace(proof=proof, roots=dict(sources=root/'sources',sdk=root/'sdk'), inventories={},
                selection=dict(document_profile='editor'),profile=dict(direct_objects=direct))
            with mock.patch.object(api,'_tool',return_value=Path('/inert/python')), \
                 mock.patch.object(api,'ref_path',side_effect=lambda r,*a:root/r['path']), \
                 mock.patch.object(api,'_arguments',return_value=[]),mock.patch.object(api,'_header_identity',return_value=None):
                _,fragment,commands=api._graph(inspected,dict(kind=successor.PLAN_KIND,successful_donor=work),root/'plan',PIN,root)
            self.assertEqual(set(successor.FRESH),set(commands['objects']))
            self.assertEqual((50,5),(len(commands['imports']),len(commands['archive_imports'])))
            self.assertIn(successor.OWNER,commands['imports']);self.assertNotIn(successor.MAIN,commands['imports'])
            target=str(root/('objects/'+successor.OWNER+'.o'))
            self.assertEqual(1,commands['link'].count(target))
            self.assertLess(commands['link'].index(target),commands['link'].index(str(root/'archives/libWebCore.a')))
            self.assertIn(successor.HELPER,fragment.read_text())


    def test_import_boundary_preserves_compiler_provenance_and_uses_independent_copies(self):
        with tempfile.TemporaryDirectory(prefix='input-method-import-') as tmp:
            root=Path(tmp).resolve();original=root/'original';output=root/'output'
            original.mkdir();output.mkdir();(output/'objects').mkdir();(output/'evidence').mkdir()
            def fact(name,raw):
                path=original/name;path.write_bytes(raw);state=path.stat()
                return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),mode=state.st_mode&0o777,
                    identity=api._identity7(state))
            provenance=dict(kind=successor.PROVENANCE_KIND,compile_origin='select-event-compiled',compile_bindings=dict(build='/old/build'))
            row=dict(id=successor.OWNER,object=fact('owner.o',b'actual retained object bytes'),depfile=fact('owner.d',b'owner: source.cpp\n'),
                command_sha256=PIN,original_argv=['/inert/compiler'],original_cwd='/old/build',ninja_record=['0','1','2','owner','token'],
                ninja_command='inert retained command',command_script=None,donor_provenance=provenance)
            with mock.patch.object(api,'_completed_input_directories',return_value=[original]):
                result=api._copy_completed_object(dict(kind=successor.PLAN_KIND,successful_donor=dict(objects=[row])),successor.OWNER,output)
            target=output/('objects/'+successor.OWNER+'.o')
            self.assertEqual(b'actual retained object bytes',target.read_bytes())
            self.assertNotEqual(target.stat().st_ino,Path(row['object']['path']).stat().st_ino)
            self.assertFalse(result['compiler_invoked']);self.assertFalse(result['hardlinked'])
            self.assertEqual(provenance,result['donor_provenance'])

    def test_inspection_uses_new_inventoried_overlay_without_admitting_it_to_old_lane(self):
        roots={k:Path('/metadata-fixture')/k for k in ('sources','sdk','reuse')}
        selection={k:PIN for k in api.SELECTION_FIELDS}
        selection.update(document_profile='editor',profile='fixture-profile',sources=str(roots['sources']),sdk=str(roots['sdk']),
            reuse_root=str(roots['reuse']),projection=str(roots['sources']/'projection.json'),reuse_proof=str(roots['sources']/successor.PROOF_SOURCE))
        target=dict(system='Emscripten',processor='wasm32',pointer_bits=32,triple='wasm32-emscripten')
        recipe=dict(target=target,options=dict(script_enabled=True,rendering='cpu',thread_model='single'),
            provider=dict(binding='copied-owner-bridge',abi_major=1,abi_minor=1,header='include/foundation/appended/engine_provider.h',
                header_sha256=api.document_contract.BASE_HEADER_SHA256),toolchain=dict(paired_sdk_sha256=PIN))
        files={'projection.json':PIN,successor.PROOF_SOURCE:PIN,successor.HEADER_IDENTITY_SOURCE:PIN}
        proof={n:{} for n in ('baseline','host_tools','sdk_tools','python_launch','metadata','private_cache','emscripten_config')}
        proof.update(schema_version=1,kind=api.REUSE_KIND,profile='fixture-profile',document_profile='editor',target=target,paired_sdk_sha256=PIN,
            objects=[],archives=[],replacements=[],link={},recovery_limits=[],header_identity=ref(successor.HEADER_IDENTITY_SOURCE),inventory=dict(files={}))
        docs={str(roots['sources']/'recipe.json'):recipe,str(roots['sources']/'projection.json'):{},
            str(roots['sdk']/'sdk.json'):dict(target=target,files={}),str(roots['sources']/successor.PROOF_SOURCE):proof}
        with mock.patch.object(api,'profile',return_value=dict(name='fixture-profile')),mock.patch.object(api,'ordinary',side_effect=lambda p,*a,**k:Path(p)), \
             mock.patch.object(api,'checked_document',side_effect=lambda p,*a,**k:docs[str(p)]),mock.patch.object(api,'checked_read',return_value=b''), \
             mock.patch.object(api,'digest',return_value=PIN),mock.patch.object(api,'required_helpers',return_value=()), \
             mock.patch.object(api,'_validate_metadata_interfaces'),mock.patch.object(api,'_validate_projection'), \
             mock.patch.object(api.manifest,'verify_sources',return_value=(dict(files=files),PIN,recipe)),mock.patch.object(api,'verify_sdk',return_value=PIN), \
             mock.patch.object(api,'inventory'),mock.patch.object(api,'_validate_proof'):
            self.assertEqual(proof,api.inspect_inputs(selection,_input_method_repair=True).proof)
            with self.assertRaisesRegex(ValueError,'baseline root reuse-proof'):api.inspect_inputs(selection)
            with self.assertRaises(ValueError):api.inspect_inputs(selection,_input_method_repair=True,_select_event_repair=True)


class DonorInterfaceTests(unittest.TestCase):
    """The real admission/parser interface over an inert closed52 graph."""
    def setUp(self):
        self.base, original = fixture()
        self.bindings={**self.base.roots,'build':Path('/synthetic/build')}
        self.records={};self.raw={};self.rows=[];self.commands=dict(objects={});self.freeze=dict(files={})
        self.old=deepcopy(self.base);self.old.proof.clear();self.old.proof.update(deepcopy(original['plan']['reuse']))
        self.old.proof.update(host_tools={},private_cache=dict(root='cache',files=[]))
        self.old.inventories['sources'][successor.HEADER_SOURCE]=successor.HEADER_BEFORE_SHA256
        for obj in self.old.proof['objects']:
            self.old.inventories['sources'][obj['source']['path']]=obj['source']['sha256']
        self.base.inventories['sources'].update(self.old.inventories['sources'])
        self.base.inventories['sources'][successor.HEADER_SOURCE]=successor.HEADER_AFTER_SHA256
        def fact(path,raw):
            value=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),mode=420,
                identity=[1,len(self.raw)+1,33188,1,len(raw),100,100]);self.raw[str(path)]=raw;return value
        self.fact=fact
        header=str(self.bindings['sources']/successor.HEADER_SOURCE)
        self.freeze['files'][header]=dict(path=header,sha256=successor.HEADER_BEFORE_SHA256)
        for obj in self.old.proof['objects']:
            name=obj['id'];target=str(self.bindings['build']/('objects/'+name+'.o'));source=str(self.bindings['sources']/obj['source']['path'])
            argv=['/compiler','-MD','-MT',target,'-MF',target+'.d','-o',target,'-c',source]
            dep=(target+': '+source+(' '+header if name==successor.MAIN else '')+
                (' '+str(self.bindings['build']/'document-generated/BibCopiedDocumentMetadata.generated.h') if name==successor.SHIM else '')+'\n').encode()
            self.freeze['files'][source]=dict(path=source,sha256=obj['source']['sha256'])
            product=fact(target,('object '+name).encode());self.records['objects/'+name+'.o']=product
            row=dict(id=name,original_argv=argv,original_cwd='/synthetic/build/cmake/build',ninja_record=['0','1','100',target,'token'],
                ninja_command='synthetic',command_script=None,command_sha256=PIN,object=product)
            if name in (successor.SHIM,successor.OWNER):
                self.commands['objects'][name]=argv;self.records['objects/'+name+'.o.d']=fact(target+'.d',dep)
                if name==successor.OWNER:self.owner={k:row[k] for k in ('id','ninja_record','ninja_command','command_script')}
            else:
                row['object']=fact('/synthetic/original/'+name+'.o',self.raw[target]);row['depfile']=fact('/synthetic/original/'+name+'.d',dep)
                row['donor_provenance']=dict(kind=selected.PROVENANCE_KIND,compile_origin='showpicker-imported',
                    compile_bindings={k:str(v) for k,v in self.bindings.items()},predecessor=dict(kind='retained-Theme-F6-P5-history',id=name))
                self.rows.append(row)
                receipt=dict(object=row['object'],original_depfile=row['depfile'],donor_provenance=row['donor_provenance'],
                    compiler_invoked=False,hardlinked=False,destination=target,sha256=product['sha256'],bytes=product['bytes'])
                self.records['evidence/import-'+name+'.json']=fact('/synthetic/build/evidence/import-'+name+'.json',api.encoded(receipt))
                self.records['evidence/import-'+name+'.original.d']=fact('/synthetic/build/evidence/import-'+name+'.original.d',dep)
        archives=[]
        for name in ARCHIVES:
            archive=fact('/synthetic/original/lib'+name+'.a',name.encode());report=fact('/synthetic/original/'+name+'.json',b'{}')
            archives.append(dict(name=name,archive=archive,report=report))
            self.records['archives/lib'+name+'.a']=fact('/synthetic/build/archives/lib'+name+'.a',name.encode())
            self.records['evidence/archive-'+name+'.json']=fact('/synthetic/build/evidence/archive-'+name+'.json',b'{}')
        ninja=fact('/synthetic/build/cmake/build/.ninja_log',b'# ninja log v6\n'+('\t'.join(self.owner['ninja_record'])+'\n').encode())
        old=dict(reuse=original['plan']['reuse'],successful_donor=dict(objects=self.rows,archives=archives,
            original_bindings={k:str(v) for k,v in self.bindings.items()},dependency_sidecar={},metadata_directories=[]))
        self.authority=dict(plan=old,records=self.records,commands=self.commands,bindings=self.bindings,freeze=self.freeze,actual_vfs={},
            descriptor=dict(owner_compiled=self.owner,select_event_ninja_log=ninja,root_acceptance=dict(path='/synthetic/root',sha256=PIN)))
        self.effective=deepcopy(self.base);self.effective.proof['objects'].insert(35,deepcopy(original['plan']['reuse']['objects'][35]))

    def admit(self):
        def indexed(r,roots,inventories):
            if inventories[r['root']].get(r['path'])!=r['sha256']:raise ValueError('current dependency pin differs')
            return roots[r['root']]/r['path']
        def context(inspection,*args):
            return dict(directories=[],namespace={'{sources}/'+successor.HEADER_SOURCE:
                successor.HEADER_BEFORE_SHA256 if inspection is self.old else successor.HEADER_AFTER_SHA256},physical_headers_sha256=PIN,vfs={})
        with mock.patch.object(successor,'accepted_authority',return_value=self.authority), \
             mock.patch.object(successor,'effective_inspection',return_value=self.effective),mock.patch.object(successor,'_old_inspection',return_value=self.old), \
             mock.patch.object(api,'_header_identity',return_value=dict(overlay={})),mock.patch.object(api,'_completed_normalize_vfs',return_value={}), \
             mock.patch.object(api,'_completed_header_context',side_effect=context),mock.patch.object(api,'_completed_ninja_command',return_value='token'), \
             mock.patch.object(api,'_completed_arguments',return_value=[]),mock.patch.object(api,'_completed_fact',side_effect=lambda f:self.raw[f['path']]), \
             mock.patch.object(api,'ref_path',side_effect=indexed):
            return successor.admit_donor(dict(path='/synthetic/donor',sha256=PIN),self.base,api)[0]

    def test_50imports_include_accepted_unified_with_own_compiler_root_and_history(self):
        result=self.admit();self.assertEqual((50,5),(len(result['objects']),len(result['archives'])))
        self.assertNotIn(successor.MAIN,[r['id'] for r in result['objects']])
        owner=next(r for r in result['objects'] if r['id']==successor.OWNER)
        self.assertEqual('select-event-compiled',owner['donor_provenance']['compile_origin'])
        self.assertEqual(str(self.bindings['build']),owner['donor_provenance']['compile_bindings']['build'])
        inherited=next(r for r in result['objects'] if r['id']==successor.THEME)
        self.assertEqual('retained-Theme-F6-P5-history',inherited['donor_provenance']['predecessor']['predecessor']['kind'])

    def test_other_imported_header_consumer_and_changed_receipt_are_refused(self):
        row=next(r for r in self.rows if r['id']!=successor.MAIN);name=row['id'];original=self.raw[row['depfile']['path']]
        raw=original.rstrip()+(' '+str(self.bindings['sources']/successor.HEADER_SOURCE)+'\n').encode()
        self.raw[row['depfile']['path']]=raw;self.raw[self.records['evidence/import-'+name+'.original.d']['path']]=raw
        with self.assertRaisesRegex(ValueError,'sole actual compiler owner'):self.admit()
        self.raw[row['depfile']['path']]=original;self.raw[self.records['evidence/import-'+name+'.original.d']['path']]=original
        fact=self.records['evidence/import-'+name+'.json'];value=json.loads(self.raw[fact['path']]);value['compiler_invoked']=True;self.raw[fact['path']]=api.encoded(value)
        with self.assertRaisesRegex(ValueError,'copy receipt'):self.admit()


class AssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('input_method_source_assembly',ROOT/'recipes/webkitwasm-document-v2/assemble_sources.py')
        cls.assembly=importlib.util.module_from_spec(spec);sys.modules[spec.name]=cls.assembly;spec.loader.exec_module(cls.assembly)

    def options(self):
        return {name:True for name in ('include_successful_donor_helper','include_theme_successor_helper',
            'include_showpicker_successor_helper','include_select_event_successor_helper','include_input_method_successor_helper')}

    def test_maintained_selection_adds_only_exact_input_method_helper(self):
        options=self.options();options.pop('include_input_method_successor_helper')
        prior,_,_=self.assembly._maintained(ROOT,'editor',**options)
        current,_,_=self.assembly._maintained(ROOT,'editor',**self.options())
        self.assertEqual(set(prior)|{successor.HELPER},set(current))
        self.assertEqual((self.assembly.snapshot(ROOT/successor.HELPER),'helper'),current[successor.HELPER])
        self.assertEqual({name:current[name] for name in prior},prior)

    def test_optin_requires_all_predecessors_before_io_and_cli_forwards(self):
        a=self.assembly
        for name in self.options():
            options=self.options();options[name]=False if name!='include_input_method_successor_helper' else 1
            with self.subTest(name=name),mock.patch.object(a,'ordinary',side_effect=AssertionError('unexpected IO')),self.assertRaises(ValueError):
                a.prepare(Path('/baseline'),PIN,PIN,document_profile='editor',**options)
        args=['plan','--baseline-sources','/baseline','--baseline-recipe-sha256',PIN,'--baseline-sources-sha256',PIN,'--document-profile','editor']
        for name in self.options():args.append('--'+name.replace('_','-'))
        with mock.patch.object(a,'prepare',return_value=dict(document_profile='editor',source_files=1,source_bytes=1)) as prepare,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0,a.main(args))
        self.assertIs(prepare.call_args.kwargs['include_input_method_successor_helper'],True)


if __name__=='__main__':unittest.main()
