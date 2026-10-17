"""Private maintained dispatch fixtures: inert data, never an actual capture."""
import ast
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).absolute().parents[1]
METADATA = ROOT
FIXTURE_SHA256 = '50c7f0534ebb1b60d10731a4c8b4758e0c5f07fdb86abd70ade07861e5b7d6e2'
OLD_TEST_SHA256 = '39ad1e7d97630f9aa2ddc16f70a0096108d97cafee80ec91fb5a1a409a2ff783'


def digest(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def fixed_module(name, path, pin=None):
    raw = path.read_bytes()
    if pin is not None and digest(raw) != pin: raise ValueError('Exact fixture source changed')
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


class Model:
    """Reuse the frozen bridge fixture producer; no live capture token is consumed."""
    def __init__(self, case):
        self.case = case
        self.fixture = case.fixture_module.Fixture(case)
        f = self.fixture; self.io = f.io; self.api = case.api; self.role7 = case.role7
        # This is an inert already-captured owner normalization fixture, not
        # actual SDK/host inventory admission or original proof execution.
        def repository_file(owner, path, sha, role, *, repository_root, source_paths, maximum=32*1024**2):
            path = Path(path)
            if path.relative_to(repository_root).as_posix() not in source_paths: raise ValueError('Unadmitted fixed source path')
            return owner.file(path, sha, role, maximum=maximum)
        self.io.repository_file = types.MethodType(repository_file, self.io)
        def document(owner, ref, base, role):
            path, sha = self.api._ref(ref, base); owner.file(path, sha, role)
            return self.api.strict_json(owner.bytes(path))
        self.io.document = types.MethodType(document, self.io)
        self.inventory_calls = []
        def inventory(owner, record, base, role):
            self.inventory_calls.append((record, role))
            root = record['root']; old = owner._roots[root]
            if self.api._diagnostic_reference(record['inventory'], base) != self.api._diagnostic_reference(old[0]['inventory'], old[1]):
                raise ValueError('Fixture cannot invent a complete inventory')
            document(owner, record['inventory'], base, 'inventory')
            return dict(record, **old[3])
        self.io.inventory = types.MethodType(inventory, self.io)
        self.io.allowed.add(str(ROOT/'tools/appended_engine_native_role7.py'))
        self.io.allowed.add(str(ROOT/self.api.DIAGNOSTIC_HOST_POLICY))
        self.io.allowed.update(str(ROOT/'tools/role7'/name) for name in self.role7.SOURCE_PINS)
        tree = ROOT/'tools/process_tree.py'
        original_tree = self.role7.common.ROOT/'tools/process_tree.py'
        self.io.put(original_tree, tree.read_bytes())
        # The selected role versions and cmake/ninja aliases are genuine-shaped
        # inert fixture data. No selected program bytes can be executed.
        for role,version in (('perl','5.40.0'),('cmake','3.31.0'),('ninja','1.12.1')):
            f.programs[role]['version'] = version
            stdout = f.capture_root/(role+'/stdout.json')
            raw = json.loads(self.io.memory[str(stdout)]); raw['program'] = f.programs[role]
            updated = self.io.put(stdout, raw)
            command_path = f.capture_root/(role+'/command.json'); command = json.loads(self.io.memory[str(command_path)])
            command['stdout']['sha256'] = updated['sha256']
            updated = self.io.put(command_path, command); f.launch['commands']['subjects'][role]['sha256'] = updated['sha256']
        f.plan['toolchain']['tools']['cmake'] = f.programs['cmake']
        f.plan['toolchain']['tools']['ninja'] = f.programs['ninja']
        self.source_base = Path(f.c.BASE)
        closure = dict(schema_version=1, kind='foundation-native-role7-source-closure-v1', files={})
        for name in ('common.py', 'observer.py', 'capture.py'):
            path = self.source_base/name; raw = path.read_bytes()
            closure['files'][name] = dict(path=str(path), sha256=digest(raw), bytes=len(raw))
        raw = tree.read_bytes(); closure['files']['process_tree.py'] = dict(path=str(original_tree), sha256=digest(raw), bytes=len(raw))
        self.closure = closure; self.closure_ref = self.io.put(self.source_base/'role7-source-closure.json', closure)
        self.input_ref = self.io.put(self.source_base/'role7-input.json', f.fixed)
        policy_path = self.source_base/'role7-launch-policy.json'; self.policy = json.loads(self.io.memory[str(policy_path)])
        self.policy['input_sha256'] = self.input_ref['sha256']; self.policy_ref = self.io.put(policy_path, self.policy)
        f.launch.update(source_closure_sha256=self.closure_ref['sha256'], launch_policy_sha256=self.policy_ref['sha256'], fixed_input=self.input_ref)
        for module in (f.c, self.role7.common):
            case.stack.enter_context(patch.object(module, 'FIXED_INPUT_SHA256', self.input_ref['sha256']))
            case.stack.enter_context(patch.object(module, 'FIXED_POLICY_SHA256', self.policy_ref['sha256']))
        self.candidate = f.data_documents()
        self.observed_path = METADATA/self.candidate['observations']['path']; self.wrapper_path = METADATA/self.candidate['provenance']['path']
        self.observed = json.loads(self.io.memory[str(self.observed_path)]); self.wrapper = json.loads(self.io.memory[str(self.wrapper_path)])
        host = f.plan['host']; toolchain = f.plan['toolchain']; self.toolchain = toolchain
        self.host_document = dict(schema_version=1, kind=self.api.DIAGNOSTIC_HOST_KIND, programs=f.programs,
            module_inventories={name:dict(root=value['root'], inventory=value['inventory']) for name,value in host['module_inventories'].items()},
            interpreter_bindings=host['interpreter_bindings'], diagnostic_host=self.candidate['observations'], source_provenance=self.candidate['provenance'])
        toolchain['kind'] = 'foundation-native-engine-prototype-sdk-toolchain-v1'
        toolchain['sdk_binding']['host_document'] = self.host_document
        self.original = f.original_result
        self.original_mock = case.stack.enter_context(patch.object(self.api, '_diagnostic_original', return_value=self.original))
        self.original_authority = self.api._DiagnosticOriginalAuthority(self.api._DIAGNOSTIC_AUTHORITY_VERSION, '1'*64, '2'*64)
        case.stack.enter_context(patch.object(self.api, '_DIAGNOSTIC_ORIGINAL_AUTHORITY', self.original_authority))
        case.stack.enter_context(patch.object(self.api, '_DIAGNOSTIC_AUTHORED_SOURCES', ((self.api._DIAGNOSTIC_SOURCE_AUTHORITY_VERSION,'observer',self.role7.SOURCE_PINS['observer.py']),)))
        self.set_authority()
        # A passive parse must not invoke either collector implementation or /proc.
        for module, name in ((self.role7.capture,'run_eight'),(self.role7.common,'proc_read'),(f.c,'proc_read')):
            case.stack.enter_context(patch.object(module,name,side_effect=AssertionError('Passive admission attempted live observation')))
        self.io.calls.clear(); self.inventory_calls.clear()

    def set_authority(self):
        self.authority = self.api._DiagnosticRole7Authority(self.closure_ref['sha256'], self.policy_ref['sha256'], *self.fixture.ospins)
        self.case.stack.enter_context(patch.object(self.api,'_DIAGNOSTIC_ROLE7_AUTHORITY',self.authority))

    def reseal_launch(self):
        ref = self.io.put(self.fixture.capture_root/'role7_launch.json', self.fixture.launch)
        self.wrapper['role7_launch']['sha256'] = ref['sha256']; self.reseal_wrapper()

    def reseal_wrapper(self):
        self.host_document['source_provenance']['sha256'] = self.io.put(self.wrapper_path, self.wrapper)['sha256']

    def reseal_observed(self):
        self.host_document['diagnostic_host']['sha256'] = self.io.put(self.observed_path, self.observed)['sha256']

    def parse(self):
        return self.api.parse_host_tools(self.host_document, METADATA, self.io, self.toolchain, repository_root=ROOT)


class MaintainedRole7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack(); cls.addClassCleanup(cls.stack.close)
        cls.stack.enter_context(patch.object(sys,'path',[str(ROOT/'tools'),*sys.path]))
        cls.api = fixed_module('fixed_role7_postimage_inputs',ROOT/'tools/appended_engine_native_inputs.py')
        cls.legacy = fixed_module('fixed_role7_predecessor_fixtures',ROOT/'tests/test_appended_engine_native_inputs.py',OLD_TEST_SHA256)
        import appended_engine_native_role7 as role7
        cls.role7 = role7
        cls.bindings = types.SimpleNamespace(modules=dict(data=cls.api,common=role7.common,observer=role7.observer,capture=role7.capture,os=role7.os_origins,policy_raw=(ROOT/cls.api.DIAGNOSTIC_HOST_POLICY).read_bytes()))
        cls.fixture_module = fixed_module('portable_inert_role7_data_model',ROOT/'tests/fixtures/appended_engine_native_role7/inert_model.py',FIXTURE_SHA256)

    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.actual=[]
        def forbidden(*args,**kwargs): self.actual.append('operation'); raise AssertionError('No actual child/program/network operation')
        for obj,name in ((subprocess,'Popen'),(os,'fork'),(os,'execve'),(os,'system')):
            self.stack.enter_context(patch.object(obj,name,side_effect=forbidden))
        self.temp = tempfile.TemporaryDirectory(dir=ROOT); self.addCleanup(self.temp.cleanup); self.work=Path(self.temp.name)

    def tearDown(self): self.assertEqual(self.actual,[])
    def model(self): return Model(self)

    def test_old166_source_and_all_method_bodies_remain_exact(self):
        old = ROOT/'tests/test_appended_engine_native_inputs.py'
        self.assertEqual(digest(old.read_bytes()),OLD_TEST_SHA256)
        tree=ast.parse(old.read_bytes()); methods=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
        self.assertEqual(len(methods),166)

    def test_existing_public_and_preflight_signatures_remain_exact(self):
        before=json.loads((ROOT/'tests/fixtures/appended_engine_native_role7/predecessor-signatures.json').read_bytes())
        after=ast.parse((ROOT/'tools/appended_engine_native_inputs.py').read_bytes())
        for name,signature in before.items():
            new=next(node for node in after.body if isinstance(node,ast.FunctionDef) and node.name==name)
            self.assertEqual(signature,ast.dump(new.args,include_attributes=False))

    def test_default_original_authority_precedes_every_submitted_graph(self):
        m=self.model()
        with patch.object(self.api,'_DIAGNOSTIC_ORIGINAL_AUTHORITY',None),self.assertRaises(self.api.MissingInputs): m.parse()
        self.assertEqual(m.io.calls,[]); self.assertEqual(m.inventory_calls,[]);m.original_mock.assert_not_called()

    def test_v2_authority_absent_or_dictionary_precedes_role7_graph(self):
        m=self.model()
        for value in (None,{'source_closure_sha256':m.closure_ref['sha256']}):
            m.io.calls.clear()
            with patch.object(self.api,'_DIAGNOSTIC_ROLE7_AUTHORITY',value),self.assertRaises(self.api.MissingInputs) as raised:m.parse()
            self.assertEqual(raised.exception.roles,('diagnostic-role7-original-authority',))
            self.assertEqual([role for _,role in m.io.calls],['diagnostic-provenance-wrapper'])
        m.original_mock.assert_not_called();self.assertEqual(m.inventory_calls,[])

    def test_partial_reviewed_carrier_names_the_original_missing_os_pins(self):
        m=self.model();value=self.api._DiagnosticRole7Authority(m.authority.source_closure_sha256,m.authority.launch_policy_sha256,None,None)
        with patch.object(self.api,'_DIAGNOSTIC_ROLE7_AUTHORITY',value),self.assertRaises(self.api.MissingInputs) as raised:m.parse()
        self.assertEqual(raised.exception.roles,('diagnostic-role7-os_manifest_sha256','diagnostic-role7-os_original_record_sha256'))
        m.original_mock.assert_not_called();self.assertEqual(m.inventory_calls,[])

    def test_default_fixed_input_pin_still_refuses_before_original_body_graph(self):
        m=self.model()
        with patch.object(self.role7.common,'FIXED_INPUT_SHA256',None),self.assertRaises(self.api.MissingInputs) as raised:m.parse()
        self.assertEqual(raised.exception.roles,('diagnostic-role7-fixed-input-authority',));m.original_mock.assert_not_called()
        self.assertFalse(any('role7-launch' in role or 'os-origin' in role for _,role in m.io.calls))

    def test_passive_v2_host_parse_uses_retained_launch_without_live_capture(self):
        m=self.model();m.fixture.bundle=None
        result=m.parse();self.assertEqual(set(result['diagnostic']['runtime']['loaded_by_subject']),set(self.role7.common.ROLES))
        self.assertEqual(result['diagnostic']['policy_sha256'],self.api.DIAGNOSTIC_HOST_POLICY_SHA256)
        self.assertEqual(m.original_mock.call_count,1);self.assertIs(m.original_mock.call_args.args[3],m.original_authority)
        self.assertNotIn('BridgeCapture',repr(m.original_mock.call_args));self.assertFalse(result['diagnostic']['policy']['production_eligible'])

    def test_immutable_preflight_reuse_refuses_another_owner(self):
        m=self.model();pre=self.api._diagnostic_host_preflight(m.host_document,METADATA,m.io,m.toolchain,repository_root=ROOT)
        with self.assertRaisesRegex(ValueError,'exact original capture owner'):
            self.api._diagnostic_preflight_records(pre,m.host_document,METADATA,self.fixture_module.Inputs(),m.toolchain,m.original_authority,repository_root=ROOT)

    def test_launch_ownership_and_qualification_flags_are_original_closed_data(self):
        m=self.model();m.fixture.launch['production_eligible']=True;m.reseal_launch()
        with self.assertRaisesRegex(ValueError,'ineligible'):m.parse()
        m.original_mock.assert_not_called()

    def test_original_source_closure_requires_all_four_exact_members(self):
        m=self.model();del m.closure['files']['capture.py']
        m.closure_ref=m.io.put(m.source_base/'role7-source-closure.json',m.closure);m.set_authority()
        m.fixture.launch['source_closure_sha256']=m.closure_ref['sha256'];m.reseal_launch()
        with self.assertRaisesRegex(ValueError,'four ROLE7 sources'):m.parse()

    def test_original_source_closure_cannot_redirect_imports_or_supervisor(self):
        m=self.model();m.closure['files']['process_tree.py']['path']=str(ROOT/'tools/other.py')
        m.closure_ref=m.io.put(m.source_base/'role7-source-closure.json',m.closure);m.set_authority()
        m.fixture.launch['source_closure_sha256']=m.closure_ref['sha256'];m.reseal_launch()
        with self.assertRaisesRegex(ValueError,'exact approved source/path'):m.parse()

    def test_wrong_independent_os_approval_does_not_admit_submitted_manifest(self):
        m=self.model();bad=self.api._DiagnosticRole7Authority(m.authority.source_closure_sha256,m.authority.launch_policy_sha256,'f'*64,m.authority.os_original_record_sha256)
        with patch.object(self.api,'_DIAGNOSTIC_ROLE7_AUTHORITY',bad),self.assertRaises(ValueError):m.parse()
        m.original_mock.assert_not_called()
        missing=[dict(role='diagnostic-original-os-record',path='inert-missing',reason='Original data absent')]
        with patch.object(self.role7.os_origins,'consume_original_os_manifest',side_effect=self.role7.os_origins.MissingInputs(missing)),self.assertRaises(self.api.MissingInputs) as raised:m.parse()
        self.assertEqual(raised.exception.missing,tuple(missing));m.original_mock.assert_not_called()

    def test_unknown_original_os_member_is_named_missing_data(self):
        m=self.model();name=m.fixture.c.provider_id(m.fixture.osp['libc']);m.observed['runtime']['providers'][name]['origin']['id']='missing'
        m.wrapper['operating_system_providers'][name]['origin']['id']='missing';m.reseal_wrapper();m.reseal_observed()
        with self.assertRaises(self.api.MissingInputs) as raised:m.parse()
        self.assertEqual(raised.exception.roles,('diagnostic-original-os-member',))

    def test_rebased_command_preserves_original_cwd_and_all_command_fields(self):
        m=self.model();path=m.fixture.capture_root/'host/command.json';value=json.loads(m.io.memory[str(path)]);value['cwd']=str(m.fixture.capture_root/'other')
        ref=m.io.put(path,value);m.fixture.launch['commands']['host']['sha256']=ref['sha256'];m.reseal_launch()
        with self.assertRaisesRegex(ValueError,'changed original cwd'):m.parse()

    def test_identical_raw_bytes_at_another_target_are_not_original_stream(self):
        m=self.model();ref=m.observed['commands']['host']['stdout'];target=METADATA/ref['path'];other=m.fixture.root/'copied-stdout.json'
        clone=m.io.put(other,m.io.memory[str(target)]);ref.update(path=other.relative_to(METADATA).as_posix(),sha256=clone['sha256']);m.reseal_observed()
        with self.assertRaisesRegex(ValueError,'original target/hash'):m.parse()

    def test_original_map_inode_and_ordinary_identity_are_still_joined(self):
        m=self.model();path=m.fixture.capture_root/'python/readiness.json';ready=json.loads(m.io.memory[str(path)])
        selected=next(iter(ready['loaded_file_identities']));ready['loaded_file_identities'][selected]['map_inode']=0
        ref=m.io.put(path,ready);m.fixture.launch['readiness']['subjects']['python']['sha256']=ref['sha256'];m.reseal_launch()
        with self.assertRaisesRegex(ValueError,'map and ordinary physical identity'):m.parse()

    def test_role7_source_authority_is_not_installed_by_candidate_json(self):
        m=self.model();m.wrapper['source_authority']={'observer_sha256':self.role7.SOURCE_PINS['observer.py']};m.reseal_wrapper()
        with self.assertRaises(ValueError):m.parse()

    def test_original_subject_coverage_is_exact_seven_not_a_success_flag(self):
        m=self.model();del m.fixture.launch['readiness']['subjects']['gperf'];m.reseal_launch()
        with self.assertRaisesRegex(ValueError,'seven ROLE7'):m.parse()

    def test_candidate_os_release_must_be_original_fixed_input_copy(self):
        m=self.model();ref=m.observed['host']['os_release'];other=m.fixture.root/'same-os-release';target=METADATA/ref['path']
        copy=m.io.put(other,m.io.memory[str(target)]);ref.update(path=other.relative_to(METADATA).as_posix(),sha256=copy['sha256']);m.reseal_observed()
        with self.assertRaisesRegex(ValueError,'original fixed input pin'):m.parse()

    def source_fixture(self):
        constructor = tempfile.TemporaryDirectory
        def owned_temporary(*args,**kwargs):
            kwargs.setdefault('dir',ROOT)
            return constructor(*args,**kwargs)
        with patch.object(tempfile,'TemporaryDirectory',owned_temporary):
            value = self.legacy.native_current_source_fixture(self)
        f = value[0]
        for name in self.api.ROLE7_PRODUCERS:
            f.file(name,(ROOT/name).read_bytes())
        return value

    def test_native20_profile_changes_only_complete_producer_source_closure(self):
        path=Path(self.api.PROFILE)
        raw=(ROOT/'tests/fixtures/appended_engine_native_role7/predecessor-profile.json').read_bytes()
        self.assertEqual(digest(raw),'00be2a588df84c4180d1111a75b10cbe794dd0fb77438b19d62b70df7227f0f6')
        before=json.loads(raw);after=json.loads((ROOT/path).read_bytes())
        for role in ('source_map','provenance'):
            self.assertEqual(after[role]['path'],before[role]['path'])
            self.assertEqual(after[role]['sha256'],digest((ROOT/after[role]['path']).read_bytes()))
            before[role]['sha256']=after[role]['sha256']
        self.assertEqual(after['producer_inputs'],list(self.api.PRODUCERS))
        self.assertEqual(set(after['producer_inputs'])-set(before['producer_inputs']),set(self.api.ROLE7_PRODUCERS))
        self.assertEqual(len(after['producer_inputs']),20);self.assertEqual(len(self.api.ROLE7_PRODUCERS),6)
        after['producer_inputs']=before['producer_inputs'];self.assertEqual(after,before)

    def test_original_supervisor_reuses_real_existing_producer_authority(self):
        root=self.work/'original-supervisor';(root/'tools').mkdir(parents=True)
        path=root/'tools/process_tree.py';raw=b'# inert supervisor body; never imported\n'
        path.write_bytes(raw);path.chmod(0o664)
        owner=self.api.InputSet()
        self.api._producer_bytes(owner,path,'native-producer-source',root)
        with patch.object(self.role7.common,'ROOT',root):
            self.role7._original_source(self.api,owner,path,digest(raw),len(raw),root)
            with self.assertRaisesRegex(ValueError,'source closure bytes differ'):
                self.role7._original_source(self.api,owner,path,'1'*64,len(raw),root)
        self.assertEqual(owner._repository_sources[str(path)],(root,self.api.PRODUCERS))
        record=next(row for row in owner.records if row['path']==str(path))
        self.assertEqual(record['physical_mode'],0o664)
        self.assertEqual(record['mode'],0o644)
        with self.assertRaises(ValueError):owner.file(path,digest(raw),'strict-retained-asset')
        owner.recheck()

    def test_operational_supervisor_route_accepts_exact_reviewed_source_extent(self):
        pin='521fa923a4396afeda67b05efabb0c21f1161895fbe72f172d4d7dfc69c1496f'
        raw=(ROOT/'tools/process_tree.py').read_bytes()
        self.assertEqual(len(raw),70487);self.assertEqual(digest(raw),pin)
        self.assertEqual(self.role7.common.TREE_SHA256,pin)
        # Only the source-loader boundary is doubled; no owner or child starts.
        inert=b'#'+b' '*(len(raw)-2)+b'\n';calls=[]
        def read(path,maximum,expected):
            self.assertEqual(path,self.role7.common.ROOT/'tools/process_tree.py')
            self.assertGreaterEqual(maximum,len(raw));self.assertEqual(expected,pin)
            calls.append(path);return inert,{}
        with patch.object(self.role7.common,'read_file',side_effect=read):
            self.role7.common.load_tree()
        self.assertEqual(calls,[self.role7.common.ROOT/'tools/process_tree.py'])

    def test_real_source_capture_and_R_copy_retain_all_six_exact_control_bodies(self):
        f,profile_pin,map_pin,_=self.source_fixture();inputs=self.api.InputSet();retained={}
        original=self.api._retain_current_source
        def capture_record(table,name,path,role,owner):
            original(table,name,path,role,owner)
            if name in self.api.ROLE7_PRODUCERS:retained[name]=dict(table[name])
        with patch.object(self.api,'_retain_current_source',side_effect=capture_record):
            current=self.api.capture_current_sources(profile_pin,map_pin,repository_root=f.root,inputs=inputs)
        self.assertEqual(set(retained),set(self.api.ROLE7_PRODUCERS))
        self.assertFalse(current.as_dict()['complete_original_source_admission'])
        output=self.work/'retained';output.mkdir(mode=0o755)
        for name,item in retained.items():
            self.assertEqual(item['sha256'],digest((ROOT/name).read_bytes()))
            self.assertEqual(inputs._repository_sources[item['path']],(f.root,self.api.PRODUCERS))
            self.api._copy_new(output,name,Path(item['path']),item,inputs)
            self.assertEqual((output/name).read_bytes(),(ROOT/name).read_bytes())
        inputs.recheck()

    def test_missing_role7_producer_has_named_maintenance_need_without_fallback(self):
        f,profile_pin,map_pin,_=self.source_fixture();(f.root/'tools/role7/capture.py').unlink()
        with self.assertRaises(self.api.MissingInputs) as raised:
            self.api.capture_current_sources(profile_pin,map_pin,repository_root=f.root,inputs=self.api.InputSet())
        self.assertEqual(raised.exception.roles,('native-producer-source',))

    def test_mutated_retained_role7_source_is_rejected_by_actual_owner_recheck(self):
        f,profile_pin,map_pin,_=self.source_fixture();inputs=self.api.InputSet()
        self.api.capture_current_sources(profile_pin,map_pin,repository_root=f.root,inputs=inputs)
        path=f.root/'tools/appended_engine_native_role7.py';body=path.read_bytes();path.write_bytes(b'#'+body[1:])
        with self.assertRaises(ValueError):inputs.recheck()

    def test_dependency_source_authority_keeps23_and_joins_six_under_native20(self):
        deps=fixed_module('fixed_role7_dependency_postimage',ROOT/'tools/appended_engine_native_dependencies.py')
        self.assertEqual(len(deps.PRODUCER_SOURCES),23)
        self.assertEqual(deps.PRIVATE_SHARED_SOURCES[:3],(
            'recipes/webkitwasm-native-rich4083-v1/producer/private-cpp-runtime-policy-v1.json',
            'recipes/webkitwasm-native-rich4083-v1/producer/native-private-runtime.cmake',
            'recipes/webkitwasm-native-rich4083-v1/producer/verify-provider.cmake'))
        self.assertEqual(deps.PRIVATE_SHARED_SOURCES[-1],'tools/appended_engine_native_prototype.py')
        root=self.work/'producer-closure';root.mkdir(mode=0o755)
        for name in deps.PRODUCER_SOURCES+deps.PRIVATE_SHARED_SOURCES:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((ROOT/name).read_bytes() if name in self.api.ROLE7_PRODUCERS else b'INERT unexecuted producer control\n');path.chmod(0o644)
        owner=self.api.InputSet();deps._producer_inputs(owner,root)
        for name in deps.PRODUCER_SOURCES:
            self.assertEqual(owner._repository_sources[str(root/name)],(root,deps.PRODUCER_SOURCES))
        for name in self.api.ROLE7_PRODUCERS:
            self.assertEqual(owner._repository_sources[str(root/name)],(root,self.api.PRODUCERS))
            record=next(item for item in owner.records if item['path']==str(root/name))
            self.assertEqual(record['sha256'],digest((ROOT/name).read_bytes()))
        owner.recheck()


if __name__=='__main__': unittest.main()
