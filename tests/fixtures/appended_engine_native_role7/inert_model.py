"""Portable inert ROLE7 data model; no execution, admission or original authority."""
import hashlib,json,os,stat
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).absolute().parents[3]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def raw(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()

class Inputs:
    """Explicit fixture owner. Never reads outside fixed sources/owned inert files."""
    def __init__(self):
        self.memory={}; self.allowed=set(); self.calls=[]; self.records={}; self._roots={}; self._sdk_roots={}
    def put(self,path,value):
        path=Path(path); body=value if type(value) is bytes else raw(value); self.memory[str(path)]=body
        return dict(path=str(path),sha256=sha(body))
    def check_deadline(self): pass
    def bytes(self,path,maximum=32*1024**2):
        path=Path(path)
        if str(path) in self.memory: body=self.memory[str(path)]
        elif str(path) in self.allowed:
            body=path.read_bytes()
        else: raise AssertionError('Unexpected fixture body read: '+str(path))
        if len(body)>maximum: raise ValueError('Fixture bounded input overflow')
        return body
    def file(self,path,digest,role,maximum=32*1024**2):
        path=Path(path); self.calls.append((str(path),role)); body=self.bytes(path,maximum)
        if sha(body)!=digest: raise ValueError('Changed original fixture bytes')
        mode=0o644 if str(path) in self.memory else stat.S_IMODE(path.lstat().st_mode)
        item=dict(path=str(path),sha256=digest,bytes=len(body),mode=mode,roles=[role])
        previous=self.records.get(str(path))
        if previous: item['roles']=sorted(set(previous['roles']+[role]))
        self.records[str(path)]=item
        return item


class Fixture:
    def __init__(self,case,external_gperf=False):
        self.case=case; self.io=Inputs(); self.b=case.bindings; self.d=self.b.modules['data']; self.c=self.b.modules['common']
        case.stack.enter_context(patch.object(self.c,'proc_read',side_effect=AssertionError('No actual proc sampling in inert bridge fixtures')))
        self.base=BASE; self.root=case.work; self.sdk=self.root/'sdk'; self.sdk.mkdir(); self.osroot=self.root/'os'; self.osroot.mkdir()
        self.files={}; self.modes={}; self.dirs=set()
        def leaf(name,body=b'inert fixture data',mode=0o644):
            path=self.sdk/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(body); path.chmod(mode)
            self.io.allowed.add(str(path)); self.files[name]=sha(body); self.modes[name]=mode
            for parent in path.parents:
                if parent==self.sdk: break
                rel=parent.relative_to(self.sdk).as_posix(); self.dirs.add(rel); self.modes[rel]=0o755
            return path
        self.programs={role:dict(path=str(leaf('bin/'+role,('inert-'+role).encode(),0o755)),sha256=sha(('inert-'+role).encode()),version='3.12.4') for role in case.role7.common.ROLES}
        required={'python':['json/__init__.py','hashlib.py','pathlib.py'],'perl':['English.pm','FindBin.pm','JSON/PP.pm'],'ruby':['json.rb','fileutils.rb']}
        self.search={}; self.module_paths={}
        for role,names in required.items():
            self.search[role]=[str(self.sdk/role)]
            self.module_paths[role]=[]
            for index,name in enumerate(names):
                path=leaf(role+'/'+name,('inert-module-'+role+name).encode())
                if index==0: self.module_paths[role].append(str(path))
        self.policy=json.loads(self.b.modules['policy_raw']); self.osp={}; os_entries={}; members={}; placements={}
        for role in ('libc','loader'):
            path=self.osroot/(role+'.so'); body=('inert-os-'+role).encode(); path.write_bytes(body); path.chmod(0o644); self.io.allowed.add(str(path))
            self.osp[role]=str(path); member='lib/'+role+'.so'; name=self.c.provider_id(str(path))
            members[member]=dict(source='fixture-original',sha256=sha(body),bytes=len(body),mode=0o644); placements[str(path)]=member
            os_entries[name]=dict(logical_path=str(path),resolved_path=str(path),sha256=sha(body),bytes=len(body),mode=0o644,original_member=member)
            leaf('retained-os/'+role+'.so',body)
        sh=self.programs['sh']; body=self.io.bytes(sh['path']); members['bin/sh']=dict(source='fixture-original',sha256=sh['sha256'],bytes=len(body),mode=0o755)
        placements[sh['path']]='bin/sh'; os_entries['shell']=dict(logical_path='/bin/sh',resolved_path=sh['path'],sha256=sh['sha256'],bytes=len(body),mode=0o755,original_member='bin/sh')
        original=dict(schema_version=1,kind='foundation-native-diagnostic-original-os-record-v1',scope='original-host-os-selected-members-only',
            sources={'fixture-original':dict(kind='source-build-output',identity='INERT UNIT FIXTURE, NOT REAL ORIGIN',original_evidence_sha256='9'*64)},
            members=members,placements=placements,aliases={'/bin/sh':dict(type='symlink',target=sh['path'])})
        orig_path=self.root/'os-original.json'; orig=self.io.put(orig_path,original)
        manifest=dict(schema_version=1,kind='foundation-native-diagnostic-os-origin-manifest-v1',scope='original-host-os-selected-members-only',
            original_record=dict(path=orig_path.name,sha256=orig['sha256']),files=os_entries)
        manifest_path=self.root/'os-manifest.json'; manifest_ref=self.io.put(manifest_path,manifest)
        self.osref=dict(path=manifest_path.name,sha256=manifest_ref['sha256']); self.osbase=self.root
        self.ospins=(manifest_ref['sha256'],orig['sha256'])
        osfacts=self.b.modules['os'].consume_original_os_manifest(self.osref,self.osbase,self.io,
            approved_manifest_sha256=self.ospins[0],approved_original_record_sha256=self.ospins[1])
        if external_gperf:
            path=self.root/'external/gperf'; path.parent.mkdir(); path.write_bytes(b'inert-gperf'); path.chmod(0o755); self.io.allowed.add(str(path))
            self.programs['gperf']['path']=str(path)
        tools={}
        for name in self.d.TOOL_NAMES:
            path=leaf('tools/'+name,('inert-tool-'+name).encode(),0o755); tools[name]=dict(path=str(path),sha256=self.files['tools/'+name],version='1.0')
        osrelease=raw(self.policy['execution_host']['distribution'])  # Replaced with original-style bytes below.
        dist=self.policy['execution_host']['distribution']; osrelease=('ID='+dist['id']+'\nVERSION_ID='+dist['version_id']+'\nVERSION_CODENAME='+dist['codename']+'\n').encode()
        self.fixed=dict(schema_version=1,kind='foundation-native-role7-fixed-input-v1',programs=self.programs,interpreter_paths=self.search,
            os_release=dict(path=str(self.root/'os-release'),sha256=sha(osrelease)),os_provider_paths=self.osp)
        input_path=Path(self.c.BASE)/'role7-input.json'; input_ref=self.io.put(input_path,self.fixed)
        self.capture_root=self.root/'capture'; self.env=dict(PATH=':'.join(sorted({str(Path(item['path']).parent) for item in [*tools.values(),*self.programs.values()]})),
            LANG='C.UTF-8',LC_ALL='C.UTF-8',TZ='UTC',SOURCE_DATE_EPOCH='1',PYTHONPATH=':'.join(self.search['python']),PERL5LIB=':'.join(self.search['perl']),RUBYLIB=':'.join(self.search['ruby']))
        rpolicy=dict(schema_version=1,kind='foundation-native-role7-launch-policy-v1',input_sha256=input_ref['sha256'],workspace_root=str(self.capture_root),
            environment=self.env,bounds=self.c.BOUNDS,schedules=self.b.modules['observer'].schedules(),ninja_shell_alias=osfacts['files']['shell'],
            os_manifest_sha256=self.ospins[0],os_original_record_sha256=self.ospins[1],cpu=0)
        policy_ref=self.io.put(Path(self.c.BASE)/'role7-launch-policy.json',rpolicy)
        case.stack.enter_context(patch.object(self.c,'FIXED_INPUT_SHA256',input_ref['sha256']))
        case.stack.enter_context(patch.object(self.c,'FIXED_POLICY_SHA256',policy_ref['sha256']))
        self.roleauth=self.b.modules['capture'].ReviewedRole7Authority('c'*64,policy_ref['sha256'])
        sdk_binding=dict(root=str(self.sdk),sdk_manifest_sha256='a'*64,policy=dict(source_date_epoch='1',cpu=self.policy['cpu'],runtime=dict(c_library_baseline='2.36')),
            files=self.files,directories=sorted(self.dirs),modes=self.modes)
        self.sdk_inventory=dict(root=str(self.sdk),inventory=dict(path='unused-sdk-inventory.json',sha256='a'*64),files=self.files,directories=sorted(self.dirs),modes=self.modes)
        self.io._sdk_roots[str(self.sdk)]=({},self.base,'fixture-sdk',sdk_binding)
        srcroot=Path(self.b.modules['observer'].__file__).parent
        source_files={name:sha((srcroot/name).read_bytes()) for name in case.role7.SOURCE_PINS}; source_modes={name:0o644 for name in source_files}
        source_doc=dict(files=source_files,directories=[],modes=source_modes); source_ref=self.doc('source-inventory.json',source_doc)
        self.host_inventories={'source':dict(root=str(srcroot),inventory=source_ref,**source_doc)}
        self.io._roots[str(srcroot)]=(dict(root=str(srcroot),inventory=source_ref),self.base,'fixture-source',source_doc)
        if external_gperf:
            path=Path(self.programs['gperf']['path']); inventory=dict(files={'gperf':self.programs['gperf']['sha256']},directories=[],modes={'gperf':0o755})
            ref=self.doc('gperf-inventory.json',inventory); self.host_inventories['gperf']=dict(root=str(path.parent),inventory=ref,**inventory)
            self.io._roots[str(path.parent)]=(dict(root=str(path.parent),inventory=ref),self.base,'fixture-external',inventory)
        runtimes={}; interpreter_refs={}
        for role in required:
            facts=dict(schema_version=1,kind='foundation-native-host-interpreter-runtime-v1',program_sha256=self.programs[role]['sha256'],search_paths=self.search[role],runtime_inventories=['sdk'])
            interpreter_refs[role]=self.doc(role+'-facts.json',facts); runtimes[role]=facts
        host=dict(programs=self.programs,module_inventories=self.host_inventories,interpreter_runtimes=runtimes,interpreter_bindings=interpreter_refs)
        toolchain=dict(tools=tools,inventories={'sdk':self.sdk_inventory},sdk_binding=sdk_binding)
        subjects=dict(programs=self.programs,inventory_documents=dict(sdk=dict(root=str(self.sdk),manifest_sha256='a'*64),
            extensions={'host-'+name:dict(root=value['root'],inventory=value['inventory']) for name,value in self.host_inventories.items()}),interpreter_facts=interpreter_refs)
        observer_path=Path(self.b.modules['observer'].__file__); observer_retained=dict(path=str(observer_path),sha256=case.role7.SOURCE_PINS['observer.py'],bytes=observer_path.stat().st_size,inventory='host-source')
        derived=dict(observer=dict(kind='source-copy',retained=observer_retained,source=dict(path=observer_path.relative_to(self.base).as_posix(),sha256=case.role7.SOURCE_PINS['observer.py'])))
        self.providers={}; self.modules={role:{} for role in required}
        for role,program in self.programs.items():
            if not external_gperf or role!='gperf': self.providers[self.c.provider_id(program['path'])]=self.provider(Path(program['path']),Path(program['path']),dict(kind='sdk',path=Path(program['path']).relative_to(self.sdk).as_posix()))
        for role,path in self.osp.items():
            self.providers[self.c.provider_id(path)]=self.provider(Path(path),self.sdk/('retained-os/'+role+'.so'),dict(kind='os-original',id=self.c.provider_id(path)))
        for role,paths in self.module_paths.items():
            self.modules[role]['module-'+role]=self.provider(Path(paths[0]),Path(paths[0]),dict(kind='sdk',path=Path(paths[0]).relative_to(self.sdk).as_posix()))
        self.plan=dict(host=host,toolchain=toolchain,subjects=subjects,providers=self.providers,modules=self.modules,derived_files=derived)
        ownership=dict(closed=True,descendants_closed=True,logs_closed=True); stamp='2026-10-17T00:00:00+00:00'
        self.launch=dict(schema_version=1,kind='foundation-native-diagnostic-role7-launch-v1',scope='original-eight-command-role7-observation-only',
            source_closure_sha256='c'*64,launch_policy_sha256=policy_ref['sha256'],fixed_input=input_ref,
            commands=dict(host=None,subjects={}),readiness=dict(host=None,subjects={}),ownership=ownership,
            production_eligible=False,native_engine_execution=False,kernel_rebuild=False)
        self.originals={}
        for role in ('host',*case.role7.common.ROLES):
            provider_paths=sorted([*self.osp.values(),self.programs['python' if role=='host' else role]['path']])
            modules=self.module_paths.get(role,[]) if role!='host' else []
            raw_value=dict(schema_version=1,kind='foundation-native-diagnostic-host-raw-v1',host=self.policy['execution_host'],
                libc_provider=self.c.provider_id(self.osp['libc']),loader_provider=self.c.provider_id(self.osp['loader'])) if role=='host' else dict(
                schema_version=1,kind='foundation-native-diagnostic-subject-raw-v1',role=role,program=self.programs[role],search_paths=self.search.get(role,[]),loaded_module_paths=modules,loaded_provider_paths=provider_paths)
            stdout=self.at_capture(role+'/stdout.json',raw_value); stderr=self.at_capture(role+'/stderr.txt',b'')
            command=dict(argv=self.b.modules['capture'].command_argv(self.fixed,role),environment=self.env,cwd=str(self.capture_root/role),returncode=0,
                stdout=stdout,stderr=stderr,started_utc=stamp,finished_utc=stamp,ownership=ownership)
            command_ref=self.at_capture(role+'/command.json',command)
            identities={}
            for path in provider_paths+modules:
                physical=self.c.opened_identity(path); mapped=path in provider_paths
                identities[path]=dict(map_device=[os.major(physical[0]),os.minor(physical[0])] if mapped else None,map_inode=physical[1] if mapped else None,file_identity=physical)
            supervision=dict(schema_version=1,primary_returncode=0,descendants_outlived=False,terminated=False,error=None,reaped=1)
            readiness=dict(schema_version=1,kind='foundation-native-role7-readiness-v1',role=role,barrier='self-host-snapshot' if role=='host' else self.c.READINESS_BARRIERS[role],
                primary_pid=100,start_time='101',subject_pids=[100],search_paths=self.search.get(role,[]),loaded_module_paths=modules,loaded_provider_paths=provider_paths,loaded_file_identities=identities,
                subject_settlement=None if role=='host' else dict(returncode=0,supervision=supervision,started_utc=stamp,finished_utc=stamp,ownership=ownership))
            ready_ref=self.at_capture(role+'/readiness.json',readiness)
            for kind,ref in (('commands',command_ref),('readiness',ready_ref)):
                if role=='host': self.launch[kind]['host']=ref
                else: self.launch[kind]['subjects'][role]=ref
        self.at_capture('host/os-release.raw',osrelease)
        self.io.put(self.capture_root/'role7_launch.json',self.launch)
        proof_path=self.root/'original-launch.json'; self.original_ref=dict(path=proof_path.relative_to(self.base).as_posix(),sha256='8'*64)
        self.original_result=dict(launch=dict(path=str(proof_path),sha256='8'*64),proof=dict(path=str(self.root/'proof.json'),sha256='7'*64,bytes=1,kind='foundation-native-fixed-trixie-original-proof-v1'),
            packages={name:dict(name=name,source_package=name,version='fixture',architecture='amd64',members={},link_origins={}) for name in ('gperf','ruby3.3','libruby3.3')},external_inventories=[])
    def doc(self,name,value):
        path=self.root/name; ref=self.io.put(path,value); return dict(path=path.relative_to(self.base).as_posix(),sha256=ref['sha256'])
    def at_capture(self,name,value):
        path=self.capture_root/name; ref=self.io.put(path,value); self.originals[str(path)]=self.io.memory[str(path)]
        return dict(path=name,sha256=ref['sha256'])
    def provider(self,resolved,retained,origin):
        body=self.io.bytes(retained)
        return dict(logical_path=str(resolved),resolved_path=str(resolved),retained=dict(path=str(retained),sha256=sha(body),bytes=len(body),inventory='sdk'),origin=origin)


    def data_documents(self):
        ref=self.io.put(self.capture_root/'role7_launch.json',self.launch)
        commands={};loaded={}
        for role in ('host',*self.c.ROLES):
            path=self.capture_root/(role+'/command.json');command=json.loads(self.io.memory[str(path)])
            raw_value=json.loads(self.io.memory[str(self.capture_root/command['stdout']['path'])])
            for stream in ('stdout','stderr'):
                command[stream]['path']=(self.capture_root/command[stream]['path']).relative_to(self.base).as_posix()
            commands[role]=command
            if role!='host':
                loaded[role]=dict(providers=sorted(name for name,value in self.providers.items() if value['resolved_path'] in raw_value['loaded_provider_paths']),modules=sorted(name for name,value in self.modules.get(role,{}).items() if value['resolved_path'] in raw_value['loaded_module_paths']))
        observations=dict(schema_version=1,kind='foundation-native-diagnostic-build-host-observations-v1',scope='native-engine-diagnostic-build-host-only',policy_id=self.policy['policy_id'],observed_utc=commands['host']['finished_utc'],
            subjects=self.plan['subjects'],host=dict(self.policy['execution_host'],os_release=dict(path=(self.capture_root/'host/os-release.raw').relative_to(self.base).as_posix(),sha256=self.fixed['os_release']['sha256'])),
            runtime=dict(providers=self.providers,modules=self.modules,loaded_by_subject=loaded),commands=dict(host=commands['host'],subjects={role:commands[role] for role in self.c.ROLES}),ownership=self.launch['ownership'],production_eligible=False,native_engine_execution=False,kernel_rebuild=False)
        wrapper=dict(schema_version=1,kind='foundation-retained-diagnostic-host-original-proof-provenance-v2',scope='native-engine-diagnostic-build-host-only',original_proof=self.original_ref,derived_files=self.plan['derived_files'],operating_system_providers={self.c.provider_id(path):self.providers[self.c.provider_id(path)] for path in self.osp.values()},
            os_original=dict(path=(self.root/'os-manifest.json').relative_to(self.base).as_posix(),sha256=self.ospins[0]),role7_launch=dict(path=(self.capture_root/'role7_launch.json').relative_to(self.base).as_posix(),sha256=ref['sha256']))
        refs={}
        for name,value in (('observations',observations),('provenance',wrapper)):
            path=self.base/('inert-role7-'+name+'.json');ref=self.io.put(path,value);refs[name]=dict(path=path.name,sha256=ref['sha256'])
        return refs
