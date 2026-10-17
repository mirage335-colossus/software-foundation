"""Unarmed fixed eight-command capture. CLI never installs reviewed authority."""
import argparse
import hashlib
import os
from pathlib import Path
import resource
import stat
import sys
import time
import types

BASE = Path(__file__).absolute().parent
COMMON_SHA256 = '3d7e89aa7afde5e2f2ecd047dac1dddd71e0521350979b0536e3e1a6bd2ddb43'
OBSERVER_SHA256 = 'c2fcd66af150d82b42953097110deafe90f68365b0d5bdece33c84f00ae4b770'
_COMMON = None
_OBSERVER = None


class ReviewedRole7Authority:
    """Construct only in an explicit independently reviewed Python caller."""
    __slots__ = ('source_closure_sha256', 'launch_policy_sha256')

    def __init__(self, source_closure_sha256, launch_policy_sha256):
        object.__setattr__(self, 'source_closure_sha256', source_closure_sha256)
        object.__setattr__(self, 'launch_policy_sha256', launch_policy_sha256)

    def __setattr__(self, _name, _value):
        raise AttributeError('Reviewed authority is immutable')


def common():
    global _COMMON
    if _COMMON is None:
        with open(BASE/'common.py', 'rb') as stream:
            raw = stream.read(131073)
        if COMMON_SHA256 is None or len(raw)>131072 or hashlib.sha256(raw).hexdigest()!=COMMON_SHA256:
            raise ValueError('Exact finite ROLE7 common source absent or changed')
        module=types.ModuleType('role7_capture_common'); module.__file__=str(BASE/'common.py')
        exec(compile(raw,module.__file__,'exec'),module.__dict__); _COMMON=module
    return _COMMON


def source_closure(authority, deadline):
    c=common()
    raw,record=c.read_file(BASE/'role7-source-closure.json',65536,
        c.pin(authority.source_closure_sha256),deadline=deadline)
    value=c.decode(raw)
    c.fields(value,('schema_version','kind','files'),'ROLE7 finite source closure')
    if type(value['schema_version']) is not int or value['schema_version']!=1 or value['kind']!='foundation-native-role7-source-closure-v1':
        raise ValueError('Unknown ROLE7 finite source closure')
    c.fields(value['files'],('common.py','observer.py','capture.py','process_tree.py'),'ROLE7 four sources')
    records={}
    for name,item in value['files'].items():
        c.fields(item,('path','sha256','bytes'),'ROLE7 source identity')
        expected=c.ROOT/'tools/process_tree.py' if name=='process_tree.py' else BASE/name
        if item['path']!=str(expected) or type(item['bytes']) is not int or not 1<=item['bytes']<=131072:
            raise ValueError('ROLE7 source closure differs from its fixed four paths')
        source,fact=c.read_file(expected,131072,item['sha256'],deadline=deadline)
        if len(source)!=item['bytes'] or name=='process_tree.py' and item['sha256']!=c.TREE_SHA256:
            raise ValueError('ROLE7 source closure byte count or supervisor pin differs')
        records[name]=fact
    if value['files']['common.py']['sha256']!=COMMON_SHA256:
        raise ValueError('ROLE7 common closure disagrees with fixed import')
    if value['files']['observer.py']['sha256']!=OBSERVER_SHA256:
        raise ValueError('ROLE7 observer closure disagrees with fixed import')
    return record,records


def observer(records, deadline):
    global _OBSERVER
    c=common()
    raw,_=c.read_file(BASE/'observer.py',131072,records['observer.py']['sha256'],deadline=deadline)
    module=types.ModuleType('role7_capture_observer'); module.__file__=str(BASE/'observer.py')
    exec(compile(raw,module.__file__,'exec'),module.__dict__)
    if module.COMMON_SHA256!=COMMON_SHA256:
        raise ValueError('ROLE7 observer and capture common pins differ')
    module._COMMON=c
    _OBSERVER=module
    return module


def require_os_origins(value, policy, fixed):
    c=common()
    if value is None:
        raise c.MissingInputs('diagnostic-original-os-authority','Reviewed original OS consumer result absent')
    c.fields(value,('manifest','original_record','files'),'Reviewed original OS consumer result')
    for name,expected in (('manifest',policy['os_manifest_sha256']),('original_record',policy['os_original_record_sha256'])):
        ref=c.fields(value[name],('path','sha256','bytes','kind'),'Original OS captured metadata')
        c.absolute(ref['path']); c.pin(ref['sha256'])
        if ref['sha256']!=expected or type(ref['bytes']) is not int or ref['bytes']<=0 or type(ref['kind']) is not str:
            raise ValueError('Original OS authority differs from independently reviewed policy')
    facts=value['files']
    if type(facts) is not dict or not 1<=len(facts)<=4096:
        raise ValueError('Finite original OS normalized files required')
    for item in facts.values():
        c.fields(item,('logical_path','resolved_path','sha256','bytes','mode','original_member','alias'),'Original normalized OS file')
        c.absolute(item['logical_path']); c.absolute(item['resolved_path']); c.pin(item['sha256'])
        if type(item['bytes']) is not int or item['bytes']<0 or type(item['mode']) is not int:
            raise ValueError('Original normalized OS file size/mode malformed')
    for path in fixed['os_provider_paths'].values():
        matches=[item for item in facts.values() if item['resolved_path']==path]
        if len(matches)!=1:
            raise c.MissingInputs('diagnostic-original-os-provider', 'Declared libc/loader has no exact unique original fact: '+path)
    alias=policy['ninja_shell_alias']
    if alias is None:
        raise c.UnsupportedReadiness('ninja: original logical /bin/sh alias proof is absent')
    if sum(item==alias for item in facts.values())!=1:
        raise c.UnsupportedReadiness('ninja: complete shell alias fact differs from approved original OS result')
    # Preserve the approved alias list verbatim. Never normpath its intermediate steps.
    return facts


def command_argv(fixed, role):
    prefix=[fixed['programs']['python']['path'],'-I','-B',str(BASE/'observer.py')]
    return prefix+(['--observe-host'] if role=='host' else
        ['--observe-subject',role,'--program',fixed['programs'][role]['path']])


def command_worker(role):
    c=common()
    # The worker cannot accept arbitrary argv, scripts, environment or descriptors.
    # A direct internal CLI worker still needs an independent fixed input pin
    # before any source-evaluated schedule or observed executable body.
    c.load_fixed_input()
    raw,_=c.read_file(BASE/'observer.py',131072,c.pin(OBSERVER_SHA256))
    module=types.ModuleType('role7_worker_schedules'); module.__file__=str(BASE/'observer.py')
    exec(compile(raw,module.__file__,'exec'),module.__dict__)
    if module.COMMON_SHA256!=COMMON_SHA256:
        raise ValueError('ROLE7 worker source import pin differs')
    context=c.load_context(module.schedules(),role); cwd=context['cwd']
    c.program_file(context['fixed']['programs']['python'],context['deadline'])
    descriptors=[]
    try:
        for name in ('observer.stdout','observer.stderr'):
            descriptor=os.open(cwd/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            os.fchmod(descriptor,0o644); descriptors.append(descriptor)
        os.sched_setaffinity(0,{context['policy']['cpu']})
        resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2))
        resource.setrlimit(resource.RLIMIT_CPU,(10,12))
        os.dup2(descriptors[0],1); os.dup2(descriptors[1],2)
        for fd in descriptors:
            os.close(fd)
        descriptors=[]; c.check(context['deadline'])
        argv=command_argv(context['fixed'],role)
        os.execve(argv[0],argv,context['policy']['environment'])
        raise RuntimeError('Fixed observer execve unexpectedly returned')
    finally:
        for fd in descriptors:
            os.close(fd)


def validate_raw(role, value, fixed):
    c=common()
    if role=='host':
        c.fields(value,('schema_version','kind','host','libc_provider','loader_provider'),'Original host raw')
        if value['kind']!='foundation-native-diagnostic-host-raw-v1':
            raise ValueError('Unexpected original host kind')
        c.fields(value['host'],('system','processor','distribution','libc'),'Original host')
        c.fields(value['host']['distribution'],('id','version_id','codename'),'Original distribution')
        c.fields(value['host']['libc'],('family','version'),'Original libc')
        if (value['libc_provider']!=c.provider_id(fixed['os_provider_paths']['libc'])
                or value['loader_provider']!=c.provider_id(fixed['os_provider_paths']['loader'])):
            raise ValueError('Host raw provider IDs differ from exact fixed original paths')
    else:
        c.fields(value,('schema_version','kind','role','program','search_paths','loaded_module_paths','loaded_provider_paths'),'Original subject raw')
        if (value['kind']!='foundation-native-diagnostic-subject-raw-v1' or value['role']!=role
                or value['program']!=fixed['programs'][role]):
            raise ValueError('Original subject kind/role/program differs')
        expected=fixed['interpreter_paths'].get(role,[])
        if value['search_paths']!=expected:
            raise ValueError('Original subject interpreter search paths differ')
        for name in ('loaded_module_paths','loaded_provider_paths'):
            paths=value[name]
            if type(paths) is not list or paths!=sorted(set(paths)) or len(paths)>4096:
                raise ValueError('Original subject loaded paths must be finite/sorted/unique')
            for path in paths:
                c.absolute(path)
        if role not in c.INTERPRETERS and value['loaded_module_paths']:
            raise ValueError('Non-interpreter cannot report interpreter modules')
    if type(value['schema_version']) is not int or value['schema_version']!=1:
        raise ValueError('Original raw schema version differs')
    return value


def validate_readiness(role, value, fixed, schedules):
    c=common()
    c.fields(value,('schema_version','kind','role','barrier','primary_pid','start_time','subject_pids',
        'search_paths','loaded_module_paths','loaded_provider_paths','subject_settlement',
        'loaded_file_identities'),'Original maintained readiness')
    if (type(value['schema_version']) is not int or value['schema_version']!=1
            or value['kind']!='foundation-native-role7-readiness-v1' or value['role']!=role
            or type(value['primary_pid']) is not int or value['primary_pid']<=0
            or type(value['start_time']) is not str or not value['start_time'].isdigit()):
        raise ValueError('Malformed original maintained readiness')
    pids=value['subject_pids']; maximum=3 if role=='ninja' else 1
    if (type(pids) is not list or pids!=sorted(set(pids)) or not 1<=len(pids)<=maximum
            or value['primary_pid'] not in pids or any(type(pid) is not int or pid<=0 for pid in pids)):
        raise ValueError('Readiness subject PID coverage differs')
    for name in ('search_paths','loaded_module_paths','loaded_provider_paths'):
        paths=value[name]
        if type(paths) is not list or paths!=sorted(set(paths)) or len(paths)>4096:
            raise ValueError('Readiness paths must be finite/sorted/unique')
        for path in paths:
            c.absolute(path)
    identities=value['loaded_file_identities']
    required=set(value['loaded_module_paths'])|set(value['loaded_provider_paths'])
    if type(identities) is not dict or set(identities)!=required or len(identities)>8192:
        raise ValueError('Readiness ordinary identities must cover exactly the reported footprint')
    for path,record in identities.items():
        c.fields(record,('map_device','map_inode','file_identity'),'Observed ordinary file identity')
        physical=record['file_identity']
        if (type(physical) is not list or len(physical)!=7 or any(type(item) is not int for item in physical)
                or physical[0]<0 or physical[1]<=0 or not stat.S_ISREG(physical[2])
                or physical[3]!=1 or physical[4]<0):
            raise ValueError('Readiness requires exact ordinary physical facts')
        device,inode=record['map_device'],record['map_inode']
        if device is None and inode is None:
            if path in value['loaded_provider_paths']:
                raise ValueError('Mapped provider cannot omit original map device/inode')
        elif (type(device) is not list or len(device)!=2 or any(type(item) is not int or item<0 for item in device)
                or type(inode) is not int or inode!=physical[1]
                or device!=[os.major(physical[0]),os.minor(physical[0])]):
            raise ValueError('Readiness original map and ordinary physical identity differ')
    program=fixed['programs']['python' if role=='host' else role]['path']
    if program not in identities or identities[program]['map_device'] is None:
        raise ValueError('Readiness mapped primary executable identity absent')
    if role=='host':
        if value['barrier']!='self-host-snapshot' or value['subject_settlement'] is not None:
            raise ValueError('Host readiness must be a self snapshot')
    else:
        if value['barrier']!=schedules[role]['barrier']:
            raise ValueError('Original readiness barrier differs from fixed schedule')
        settled=value['subject_settlement']
        c.fields(settled,('returncode','supervision','started_utc','finished_utc','ownership'),'Original inner settlement')
        if settled['returncode']!=0 or not c.supervision_report(settled['supervision'],settled['returncode']):
            raise ValueError('Inner subject settlement is not strictly closed natural zero')
        c.fields(settled['ownership'],('closed','descendants_closed','logs_closed'),'Inner subject ownership')
        if any(flag is not True for flag in settled['ownership'].values()):
            raise ValueError('Inner subject ownership remains open')
    return value


def capture_one(role, context, schedules):
    c=common(); root=context['cwd']; cwd=root/role
    cwd.mkdir(mode=0o755)
    stage_deadline=min(context['deadline'],time.monotonic()+c.BOUNDS['stage_seconds'])
    py=context['fixed']['programs']['python']['path']
    settled=c.owned([py,'-I','-B',str(BASE/'capture.py'),'--command-worker',role],
        cwd,cwd/'observer-owner.log',context['policy']['environment'],stage_deadline,root)
    stdout,raw_record=c.read_file(cwd/'observer.stdout',1024**2,deadline=context['deadline'])
    _,error_record=c.read_file(cwd/'observer.stderr',1024**2,deadline=context['deadline'])
    value=validate_raw(role,c.decode(stdout),context['fixed'])
    ready,ready_record=c.read_file(cwd/'readiness.json',1024**2,deadline=context['deadline'])
    readiness=validate_readiness(role,c.decode(ready),context['fixed'],schedules)
    if role!='host' and any(readiness[key]!=value[key] for key in ('search_paths','loaded_module_paths','loaded_provider_paths')):
        raise ValueError('Actual raw loaded paths differ from original maintained readiness')
    ref=lambda fact: dict(path=str(Path(fact['path']).relative_to(root)),sha256=fact['sha256'])
    command=dict(argv=command_argv(context['fixed'],role),environment=context['policy']['environment'],
        cwd=str(cwd),returncode=settled['returncode'],stdout=ref(raw_record),stderr=ref(error_record),
        started_utc=settled['started_utc'],finished_utc=settled['finished_utc'],ownership=settled['ownership'])
    command_ref=c.write_new(cwd/'command.json',command,deadline=context['deadline'])
    command_ref['path']=role+'/'+command_ref['path']
    return dict(command=command_ref,readiness=ref(ready_record),raw=value,inner_reaped=
        0 if role=='host' else readiness['subject_settlement']['supervision']['reaped'],outer_reaped=settled['supervision']['reaped'])


def join_retained(files, subjects, *, readiness=None):
    """Passive join of a reviewed caller's combined genuine SDK/OS normalized FILEs."""
    c=common()
    if type(files) is not dict or len(files)>16384:
        raise ValueError('Finite exact original retained FILE map required')
    c.fields(subjects,c.ROLES,'Seven original subject records')
    if readiness is None:
        raise c.MissingInputs('diagnostic-observed-file-identities','Original held-readiness identity records absent')
    c.fields(readiness,c.ROLES,'Seven original readiness records')
    fixed=dict(programs={role:value['program'] for role,value in subjects.items()})
    for role,value in readiness.items():
        validate_readiness(role,value,fixed,{role:dict(barrier=barrier) for role,barrier in c.READINESS_BARRIERS.items()})
        if any(value[key]!=subjects[role][key] for key in ('search_paths','loaded_module_paths','loaded_provider_paths')):
            raise ValueError('Retained join subject/readiness footprint differs')
    by_path={}
    for fact in files.values():
        c.fields(fact,('logical_path','resolved_path','sha256','bytes','mode','original_member','alias'),'Original normalized retained FILE')
        path=str(c.absolute(fact['resolved_path'])); c.pin(fact['sha256'])
        if path in by_path:
            raise ValueError('Competing original resolved FILE facts')
        by_path[path]=fact
    programs={}; providers={}; modules={role:{} for role in c.INTERPRETERS}; loaded={}
    def selected(path,role):
        if path not in by_path:
            raise c.MissingInputs('diagnostic-original-retained-file','Observed path lacks a genuine exact original FILE: '+path)
        fact=by_path[path]; physical=readiness[role]['loaded_file_identities'][path]['file_identity']
        if c.opened_identity(path)!=physical:
            raise ValueError('Observed ordinary identity changed before retained join')
        if fact['bytes']!=physical[4] or fact['mode']!=stat.S_IMODE(physical[2]):
            raise ValueError('Original retained file size/mode differs from observed ordinary footprint')
        return fact
    for role,value in subjects.items():
        program=selected(value['program']['path'],role)
        if program['sha256']!=value['program']['sha256'] or program['mode']!=0o755:
            raise ValueError('Observed program differs from its original retained executable')
        programs[role]=program; pids=[]; mids=[]
        for path in value['loaded_provider_paths']:
            name=c.provider_id(path); providers[name]=selected(path,role); pids.append(name)
        for path in value['loaded_module_paths']:
            if role not in c.INTERPRETERS:
                raise ValueError('Non-interpreter reports modules')
            name='module-'+role+'-'+hashlib.sha256(path.encode('utf8')).hexdigest()
            modules[role][name]=selected(path,role); mids.append(name)
        loaded[role]=dict(providers=sorted(pids),modules=sorted(mids))
    return dict(programs=programs,providers=providers,modules=modules,loaded_by_subject=loaded)


def run_eight(*, authority=None, os_manifest=None):
    c=common()
    if type(authority) is not ReviewedRole7Authority:
        raise c.MissingInputs('diagnostic-role7-reviewed-launch-authority','Explicit independently reviewed caller authority absent')
    c.pin(authority.source_closure_sha256); c.pin(authority.launch_policy_sha256)
    if c.FIXED_POLICY_SHA256 is None or authority.launch_policy_sha256!=c.FIXED_POLICY_SHA256:
        raise c.MissingInputs('diagnostic-role7-launch-policy-authority','Exact independently pinned policy authority absent')
    deadline=time.monotonic()+c.BOUNDS['work_seconds']
    closure,sources=source_closure(authority,deadline)
    obs=observer(sources,deadline)
    fixed,input_record=c.load_fixed_input()
    raw,policy_record=c.read_file(BASE/'role7-launch-policy.json',65536,authority.launch_policy_sha256,deadline=deadline)
    policy=c.validate_policy(c.decode(raw),fixed,obs.schedules())
    os_files=require_os_origins(os_manifest,policy,fixed)
    obs.ninja_alias(dict(fixed=fixed,policy=policy))
    c.validate_controller(fixed,deadline)
    root=c.absolute(policy['workspace_root'])
    c.check(deadline)
    if root.exists() or root.is_symlink():
        raise ValueError('ROLE7 capture output must be fresh')
    for path in root.parents:
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise ValueError('ROLE7 output ancestors must be ordinary directories')
    if policy['cpu'] not in os.sched_getaffinity(0):
        raise ValueError('Reviewed one-CPU choice unavailable')
    before={role:c.program_file(item,deadline)[1] for role,item in fixed['programs'].items()}
    provider_before={}
    for path in fixed['os_provider_paths'].values():
        fact=next(item for item in os_files.values() if item['resolved_path']==path)
        _,actual=c.read_file(path,128*1024**2,fact['sha256'],deadline=deadline)
        if actual['bytes']!=fact['bytes'] or stat.S_IMODE(actual['identity'][2])!=fact['mode']:
            raise ValueError('Declared libc/loader original size/mode differs from observed bytes')
        provider_before[path]=(fact,actual)
    root.mkdir(mode=0o755)
    context=dict(fixed=fixed,input=input_record,policy=policy,policy_record=policy_record,cwd=root,deadline=deadline)
    results={}
    try:
        for role in ('host',*c.ROLES):
            c.check(deadline)
            results[role]=capture_one(role,context,obs.schedules())
            # Fixed launch model 16+14+2 plus actual reports. No transient-child completeness claim.
            reaped=sum(item['outer_reaped']+item['inner_reaped'] for item in results.values())
            supervisors=len(results)+sum(role!='host' for role in results)
            if reaped+supervisors>c.BOUNDS['maximum_total_descendants']:
                raise ValueError('Original supervisor reaping exceeds the fixed ROLE7 child budget')
        for role,item in fixed['programs'].items():
            if c.program_file(item,deadline)[1]!=before[role]:
                raise ValueError('Original program identity changed across eight commands')
        for path,(fact,before_provider) in provider_before.items():
            if c.read_file(path,128*1024**2,fact['sha256'],deadline=deadline)[1]!=before_provider:
                raise ValueError('Declared libc/loader original bytes changed across eight commands')
        c.recheck_context(context)
        again,after=source_closure(authority,deadline)
        if again!=closure or after!=sources:
            raise ValueError('ROLE7 frozen sources changed during capture')
        refs=lambda key: dict(host=results['host'][key],subjects={role:results[role][key] for role in c.ROLES})
        result=dict(schema_version=1,kind='foundation-native-diagnostic-role7-launch-v1',
            scope='original-eight-command-role7-observation-only',source_closure_sha256=authority.source_closure_sha256,
            launch_policy_sha256=authority.launch_policy_sha256,fixed_input=dict(path=input_record['path'],sha256=input_record['sha256']),
            commands=refs('command'),readiness=refs('readiness'),ownership=dict(closed=True,descendants_closed=True,logs_closed=True),
            production_eligible=False,native_engine_execution=False,kernel_rebuild=False)
        c.sample_resources(os.getpid(),root,deadline)
        c.write_new(root/'role7_launch.json',result,deadline=deadline)
        c.sample_resources(os.getpid(),root,deadline)
        c.check(deadline)
        return result
    except c.OwnershipUncertain:
        c.ACTIVE.append((context,results,authority,os_manifest))
        raise
    except BaseException as error:
        # A partial capture is never promoted. Preserve prior facts and the first failure.
        try:
            c.write_new(root/'failure.json',dict(schema_version=1,kind='foundation-native-role7-failure-v1',
                completed_roles=list(results),first_failure=str(error)[:2048],complete=False),deadline=deadline)
        except BaseException:
            pass
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--command-worker',choices=('host','python','perl','ruby','gperf','cmake','ninja','sh'))
    args=parser.parse_args(argv); c=common()
    try:
        if args.command_worker is None:
            run_eight()  # No CLI authority source or JSON-to-authority conversion.
        else:
            command_worker(args.command_worker)
        raise RuntimeError('Fixed capture worker unexpectedly returned')
    except c.OwnershipUncertain as error:
        c.park(error)
        raise RuntimeError('Uncertain retained park returned')


if __name__=='__main__':
    raise SystemExit(main())
