"""Focused metadata boundary checks for native showPicker successor admission."""
from copy import deepcopy
import contextlib
import io
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
import appended_engine_showpicker_successor as picker
import appended_engine_theme_successor as theme

api.ROOT = REPO
PIN = 'a' * 64


def ref(name, pin=PIN):
    return dict(root='sources', path=name, sha256=pin)


def fixture():
    direct = [picker.SHIM, 'BibCopiedDocumentBinding.cpp', picker.MAIN] + ['Direct%d.cpp'%i for i in range(32)]
    engine = ['Engine%d.cpp'%i for i in range(16)]
    def obj(name):
        source = ref(picker.MAIN_SOURCE, picker.MAIN_BEFORE_SHA256) if name == picker.MAIN else ref('source/' + name)
        return dict(id=name, source=source, dependencies=[], arguments=[], exceptions=False, unified_members=[],
            provenance=dict(kind='original-command-v1', command_sha256=PIN),
            compile_context=dict(source=deepcopy(source), headers=[], arguments=[], macros=[],
                generated_metadata=[], sdk_manifest_sha256=theme.PAIRED_SDK_SHA256))
    prior = [obj(n) for n in direct + engine]
    theme_obj = obj(picker.THEME)
    prior.insert(35, theme_obj)
    before = dict(objects=prior, metadata={}, header_identity=ref('provenance/header.json'))
    proposed = deepcopy(before)
    proposed['objects'] = [o for o in proposed['objects'] if o['id'] != picker.THEME]
    main = next(o for o in proposed['objects'] if o['id'] == picker.MAIN)
    main['source']['sha256'] = picker.MAIN_AFTER_SHA256
    main['compile_context']['source']['sha256'] = picker.MAIN_AFTER_SHA256
    profile = dict(direct_objects=direct, engine_objects=engine, source_bindings={}, derived_commands={})
    roots = {n: Path('/synthetic')/n for n in ('sources','sdk','reuse')}
    base = api.Inspection(dict(document_profile='editor',sdk_manifest_sha256=theme.PAIRED_SDK_SHA256),{},
        {},proposed,roots,dict(sources={theme.SOURCE:theme.SOURCE_SHA256},sdk={},reuse={}),profile)
    authority = dict(plan=dict(reuse=before,selection=base.selection),bindings=dict(sdk=roots['sdk']))
    return base, authority


class ProofTransitionTests(unittest.TestCase):
    def effective(self, base, authority):
        with mock.patch.object(api, '_current_context'), mock.patch.object(api, 'ref_path'):
            return picker.effective_inspection(base, authority, api)

    def test_reviewed_main_only_delta_keeps52_and_unchanged_theme(self):
        base, authority = fixture()
        effective = self.effective(base,authority)
        self.assertEqual(52,len(effective.proof['objects']))
        self.assertEqual(picker.THEME,effective.proof['objects'][35]['id'])
        self.assertNotIn(picker.THEME,base.profile['direct_objects'])
        self.assertEqual(authority['plan']['reuse']['objects'][35],effective.proof['objects'][35])

    def test_unarmed_binding_refuses_before_inspection_or_output(self):
        with mock.patch.object(picker,'MAIN_AFTER_SHA256',None), mock.patch.object(api,'inspect_inputs') as inspect:
            with self.assertRaisesRegex(ValueError,'unarmed'):
                picker.make_plan({},Path('/synthetic/output'),{},api)
            inspect.assert_not_called()

    def test_undeclared_object_source_and_compiler_changes_refused(self):
        for part in ('source','arguments','dependencies'):
            base, authority = fixture()
            obj=base.proof['objects'][1]
            if part=='source': obj[part]['sha256']='b'*64
            else: obj[part]=[ref('injected.h')] if part=='dependencies' else ['-DCHANGED']
            with self.subTest(part=part),self.assertRaisesRegex(ValueError,'proof changes'):
                self.effective(base,authority)

    def test_wrong_main_pin_and_metadata_contract_refused(self):
        base, authority=fixture()
        base.proof['objects'][2]['source']['sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'main logical'):
            self.effective(base,authority)
        base, authority=fixture()
        base.proof['metadata']['document_contract']=ref('contract.json')
        with self.assertRaisesRegex(ValueError,'metadata role'):
            self.effective(base,authority)

    def test_context_namespace_allows_only_reviewed_main(self):
        oldkey='{sources}/'+picker.MAIN_SOURCE
        old=dict(directories=[],namespace={oldkey:picker.MAIN_BEFORE_SHA256,'{sources}/private.h':PIN},
            physical_headers_sha256=PIN,vfs={})
        current=deepcopy(old);current['namespace'][oldkey]=picker.MAIN_AFTER_SHA256
        picker.context_transition(old,current,api)
        for key in ('{sources}/private.h','{sources}/Other.cpp'):
            bad=deepcopy(current);bad['namespace'][key]='b'*64
            with self.subTest(key=key),self.assertRaises(ValueError):
                picker.context_transition(old,bad,api)

    def test_reuse_projection_wrapper_delta_keeps_other_inventory_exact(self):
        base, authority=fixture()
        path='metadata/document-v2/header-identity.json'
        oldref=dict(root='reuse',path=path,sha256=PIN)
        newref=dict(oldref,sha256='b'*64)
        authority['plan']['reuse'].update(header_identity=oldref,
            inventory=dict(files={path:PIN,'build/header.h':PIN},directories=['metadata'],modes={path:420}))
        base.proof.update(header_identity=newref,
            inventory=dict(files={path:'b'*64,'build/header.h':PIN},directories=['metadata'],modes={path:420}))
        self.effective(base,authority)
        base.proof['inventory']['files']['build/header.h']='c'*64
        with self.assertRaisesRegex(ValueError,'proof changes'):
            self.effective(base,authority)


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
            theme_ninja_log={},theme_private={},theme_compiled={},
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
                successful_donor={},successful_donor_native_showpicker_repair=True)
            self.assertEqual({'ok':True},result)
            plan.assert_called_once()
        for value in (0,1,None,'true'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                api.make_plan({},Path('/synthetic/out'),successful_donor_native_showpicker_repair=value)
        for lane in ('successful_donor_guard_repair','successful_donor_composition_repair',
                'successful_donor_native_capability_repair','successful_donor_native_control_keypress_repair',
                'successful_donor_native_theme_repair'):
            with self.subTest(lane=lane),self.assertRaises(ValueError):
                api.make_plan({'document_profile':'editor'},Path('/synthetic/out'),successful_donor={},
                    successful_donor_native_showpicker_repair=True,**{lane:True})

    def test_cli_forwards_new_explicit_lane_and_refuses_mixed_lane(self):
        args=['plan']
        for name in api.SELECTION_FIELDS:
            args.extend(['--'+name.replace('_','-'),'editor' if name=='document_profile' else PIN])
        args.extend(['--output','/synthetic/out','--successful-donor','/synthetic/donor',
            '--successful-donor-sha256',PIN,'--successful-donor-native-showpicker-repair'])
        with mock.patch.object(api,'make_plan',return_value={}) as plan,contextlib.redirect_stdout(io.StringIO()):
            api.main(args)
        self.assertEqual(dict(path='/synthetic/donor',sha256=PIN),plan.call_args.kwargs['successful_donor'])
        self.assertIs(plan.call_args.kwargs['successful_donor_native_showpicker_repair'],True)
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
        direct=list(picker.FRESH)+[picker.THEME]+['Direct%d.cpp'%i for i in range(33)]
        engine=['Engine%d.cpp'%i for i in range(16)]
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
            self.assertIn(api.SHOWPICKER_SUCCESSOR_HELPER,fragment.read_text())
            self.assertEqual(174,len(picker.artifact_names(selected,archives)))


if __name__=='__main__':
    unittest.main()
