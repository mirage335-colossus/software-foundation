"""Unarmed ROLE7 host/subject observer. No submitted script, argv or authority."""
import argparse
import hashlib
import os
from pathlib import Path
import resource
import shlex
import stat
import sys
import time
import types

BASE = Path(__file__).absolute().parent
COMMON_SHA256 = '3d7e89aa7afde5e2f2ecd047dac1dddd71e0521350979b0536e3e1a6bd2ddb43'
_COMMON = None
_LAST_CONTEXT = None


def common():
    global _COMMON
    if _COMMON is None:
        with open(BASE/'common.py','rb') as stream:
            raw=stream.read(131073)
        if COMMON_SHA256 is None or len(raw)>131072 or hashlib.sha256(raw).hexdigest() != COMMON_SHA256:
            raise ValueError('Independently frozen ROLE7 common source absent or changed')
        module = types.ModuleType('role7_observer_common'); module.__file__ = str(BASE / 'common.py')
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
        _COMMON = module
    return _COMMON


PYTHON = r"""import sys
if not sys.dont_write_bytecode or sys.pycache_prefix != @CACHE@:
    raise RuntimeError('exact empty startup cache prefix and -B required')
sys.path[:] = @PATHS@
import _frozen_importlib_external as source_loader
def source_only(self, fullname):
    name = self.get_filename(fullname)
    if not name.endswith('.py'):
        raise RuntimeError('source-only Python loader required')
    return self.source_to_code(self.get_data(name), name)
source_loader.SourceFileLoader.get_code = source_only
def no_sourceless(self, fullname):
    raise RuntimeError('sourceless bytecode loader refused')
source_loader.SourcelessFileLoader.get_code = no_sourceless
import json, hashlib, pathlib, os
paths = set()
for mod in list(sys.modules.values()):
    spec = getattr(mod, '__spec__', None)
    if spec is not None and spec.origin in ('built-in', 'frozen'):
        continue
    name = getattr(mod, '__file__', None)
    if name:
        if name.endswith(('.pyc', '.pyo')):
            raise RuntimeError('bytecode cache ambiguity')
        name = os.path.realpath(name)
        if not os.path.isfile(name):
            raise RuntimeError('unresolved loaded Python module')
        paths.add(name)
print(json.dumps(dict(role='python', search_paths=sys.path, loaded_module_paths=sorted(paths)), sort_keys=True), flush=True)
if os.read(0, 1) != b'R':
    raise RuntimeError('fixed release required')
"""
PERL = r"""BEGIN { @INC = (@PATHS@); }
use English; use FindBin; use JSON::PP; use Cwd ();
my @paths;
for my $value (values %INC) {
    die "unresolved Perl module" if ref($value) || !defined($value);
    die "Perl bytecode cache ambiguity" if $value =~ /[.]pmc$/ || -f ($value . 'c');
    my $path = Cwd::abs_path($value);
    die "unresolved Perl module" unless defined($path) && -f $path;
    push @paths, $path;
}
my %seen; @paths = sort grep { !$seen{$_}++ } @paths;
$| = 1;
print JSON::PP->new->canonical(1)->utf8(1)->encode({role=>'perl',search_paths=>\@INC,loaded_module_paths=>\@paths}), "\n";
my $token; die "fixed release required" unless sysread(STDIN,$token,1)==1 && $token eq 'R';
"""
RUBY = r"""$LOAD_PATH.replace(@PATHS@)
require 'json'; require 'fileutils'
builtins = %w[enumerator.so thread.rb fiber.so rational.so complex.so ruby2_keywords.rb]
paths = $LOADED_FEATURES.filter_map do |name|
  raise 'Ruby bytecode cache ambiguity' if name.end_with?('.rbc')
  candidates = name.start_with?('/') ? [name] : $LOAD_PATH.map { |root| File.join(root,name) }.select { |path| File.file?(path) }
  if candidates.empty? && builtins.include?(name)
    next
  end
  resolved = candidates.map { |path| File.realpath(path) }.uniq
  raise 'unresolved/ambiguous Ruby module' unless resolved.length == 1 && File.file?(resolved[0])
  resolved[0]
end.uniq.sort
STDOUT.write(JSON.generate({role:'ruby',search_paths:$LOAD_PATH,loaded_module_paths:paths})+"\n"); STDOUT.flush
raise 'fixed release required' unless STDIN.read(1)=='R'
"""
CMAKE = 'file(WRITE "@READY@" "ROLE7_READY\\n")\nwhile(NOT EXISTS "@RELEASE@")\nendwhile()\n'
SHELL = 'printf "ROLE7_READY:%s\\n" "$$" > "@READY@"\nIFS= read -r token @INPUT@\ncase "$token" in ROLE7_RELEASE) exit 0;; *) exit 73;; esac\n'
NINJA = 'rule role7_barrier\n  command = @SH@ @SCRIPT@\nbuild role7_done: role7_barrier\ndefault role7_done\n'
GPERF_INPUT = b'%%\nrole7_keyword\n'


def schedules():
    templates = dict(python=PYTHON, perl=PERL, ruby=RUBY, gperf=GPERF_INPUT.decode(),
        cmake=CMAKE, ninja=NINJA + SHELL, sh=SHELL)
    barriers = common().READINESS_BARRIERS
    return {role:dict(template_sha256=hashlib.sha256(text.encode()).hexdigest(),
        barrier=barriers[role], expected_exit=0, maximum_subject_processes=3 if role=='ninja' else 1)
        for role,text in templates.items()}


def ninja_alias(context):
    c = common(); value = context['policy']['ninja_shell_alias']
    if value is None:
        raise c.UnsupportedReadiness('ninja: original logical /bin/sh alias proof is absent')
    c.fields(value, ('logical_path','resolved_path','sha256','bytes','mode','original_member','alias'), 'Ninja original shell alias')
    sh = context['fixed']['programs']['sh']
    if (value['logical_path'] != '/bin/sh' or value['resolved_path'] != sh['path']
            or value['sha256'] != sh['sha256'] or value['mode'] != 0o755
            or type(value['bytes']) is not int or value['bytes'] <= 0
            or type(value['alias']) is not list or not 1 <= len(value['alias']) <= 16):
        raise c.UnsupportedReadiness('ninja: original shell alias does not bind admitted sh')
    for step in value['alias']:
        c.fields(step, ('path','type','literal_target','next_path'), 'Ninja original alias step')
    return value


def prepare(role, context):
    c=common(); fixed=context['fixed']; cwd=context['cwd']
    target=fixed['programs'][role]['path']
    paths=fixed['interpreter_paths'].get(role, [])
    if role=='python':
        cache=c.empty_cache(cwd/'startup-pycache',create=True,deadline=context['deadline'])
        c.write_new(cwd/'startup-cache.json',cache,deadline=context['deadline'])
        script=PYTHON.replace('@PATHS@',repr(paths)).replace('@CACHE@',repr(cache['path']))
        return [target,'-I','-B','-X','pycache_prefix='+cache['path'],'-S','-c',script]
    if role=='perl':
        return [target,'-e',PERL.replace('@PATHS@',','.join("'" + item + "'" for item in paths))]
    if role=='ruby':
        return [target,'--disable-gems','-e',RUBY.replace('@PATHS@',c.canonical_raw(paths).decode().strip())]
    if role=='gperf':
        return [target]
    if role=='cmake':
        text=CMAKE.replace('@READY@',str(cwd/'ready')).replace('@RELEASE@',str(cwd/'release'))
        c.write_new(cwd/'barrier.cmake',text.encode(),deadline=context['deadline'])
        return [target,'-P',str(cwd/'barrier.cmake')]
    if role in ('sh','ninja'):
        if role=='ninja':
            ninja_alias(context)
        text=SHELL.replace('@READY@',str(cwd/'ready')).replace('@INPUT@',
            '< "'+str(cwd/'barrier.fifo')+'"' if role=='ninja' else '')
        c.write_new(cwd/'barrier.sh',text.encode(),deadline=context['deadline'])
        if role=='sh':
            return [target,str(cwd/'barrier.sh')]
        text=NINJA.replace('@SH@',fixed['programs']['sh']['path']).replace('@SCRIPT@',str(cwd/'barrier.sh'))
        c.write_new(cwd/'build.ninja',text.encode(),deadline=context['deadline'])
        return [target,'-j1','-f',str(cwd/'build.ninja')]
    raise ValueError('Unknown fixed subject')


def worker(role):
    c=common(); context=c.load_context(schedules(),role); cwd=context['cwd']
    program=context['fixed']['programs'][role]
    c.program_file(program,context['deadline'])
    argv=prepare(role,context)
    c.write_new(cwd/'subject.pid',(str(os.getpid())+'\n').encode(),deadline=context['deadline'])
    descriptors=[]
    try:
        for name in ('subject.stdout','subject.stderr'):
            descriptor=os.open(cwd/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            os.fchmod(descriptor,0o644); descriptors.append(descriptor)
        fd=os.open(cwd/'stdin.fifo',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        descriptors.append(fd)
        if not stat.S_ISFIFO(os.fstat(fd).st_mode):
            raise ValueError('Owned stdin FIFO required')
        os.set_blocking(fd,True)
        os.sched_setaffinity(0,{context['policy']['cpu']})
        resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2))
        resource.setrlimit(resource.RLIMIT_CPU,(10,12))
        os.dup2(fd,0); os.dup2(descriptors[0],1); os.dup2(descriptors[1],2)
        for descriptor in descriptors:
            os.close(descriptor)
        descriptors=[]
        c.check(context['deadline'])
        os.execve(argv[0],argv,context['policy']['environment'])
        raise RuntimeError('execve returned')
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def marker(path, maximum=4096):
    c=common()
    try:
        raw,_=c.read_file(path,maximum)
    except FileNotFoundError:
        return None
    except c.IdentityChanged:
        return None  # A bounded marker may still be undergoing its first write.
    return raw if raw.endswith(b'\n') else None


def blocked_read(pid, fifo):
    c=common()
    text=c.proc_read('/proc/'+str(pid)+'/syscall',4096).split()
    if len(text)<2 or text[0]!='0' or int(text[1],0)!=0:
        return False
    state=os.stat('/proc/'+str(pid)+'/fd/0')
    actual=fifo.lstat()
    return stat.S_ISFIFO(state.st_mode) and (state.st_dev,state.st_ino)==(actual.st_dev,actual.st_ino)


def held_snapshot(context, role, owner):
    c=common(); cwd=context['cwd']; fixed=context['fixed']
    while True:
        c.check(context['deadline'])
        if owner.poll() is not None:
            raise c.UnsupportedReadiness(role+': process exited before maintained readiness')
        raw=marker(cwd/'subject.pid')
        if raw is None or not raw.strip().isdigit():
            time.sleep(0.01); continue
        pid=int(raw.strip()); before=c.pid_state(pid)[0]
        if os.readlink('/proc/'+str(pid)+'/exe')!=fixed['programs'][role]['path']:
            time.sleep(0.01); continue
        if c.identity(os.stat('/proc/'+str(pid)+'/exe'))!=context['program_before']['identity']:
            raise c.UnsupportedReadiness('Actual executable identity differs from admitted prelaunch program')
        pids=c.descendants(pid,3 if role=='ninja' else 1)
        modules=[]; search=[]; held=False
        if role in c.INTERPRETERS:
            report=marker(cwd/'subject.stdout',1024**2)
            if report:
                value=c.decode(report)
                c.fields(value,('role','search_paths','loaded_module_paths'),'Interpreter readiness')
                if value['role']!=role or value['search_paths']!=fixed['interpreter_paths'][role]:
                    raise c.UnsupportedReadiness('Actual interpreter search paths differ')
                search=value['search_paths']; modules=value['loaded_module_paths']
                if type(modules) is not list or modules!=sorted(set(modules)) or len(modules)>4096:
                    raise c.UnsupportedReadiness('Actual interpreter module bound/order differs')
                for path in modules:
                    c.regular(path)
                held=blocked_read(pid,cwd/'stdin.fifo')
        elif role=='gperf':
            held=blocked_read(pid,cwd/'stdin.fifo')
        elif role=='cmake':
            held=marker(cwd/'ready')==b'ROLE7_READY\n' and not (cwd/'release').exists()
        else:
            ready=marker(cwd/'ready')
            if ready and ready.startswith(b'ROLE7_READY:') and ready[12:].strip().isdigit():
                barrier=int(ready[12:].strip())
                if barrier not in pids:
                    raise c.UnsupportedReadiness('Shell barrier PID is not an owned subject')
                expected=fixed['programs']['sh']['path']
                for child in pids:
                    if child!=pid and os.readlink('/proc/'+str(child)+'/exe')!=expected:
                        raise c.UnsupportedReadiness('Unexpected Ninja descendant image')
                held=blocked_read(barrier,cwd/('barrier.fifo' if role=='ninja' else 'stdin.fifo'))
        if not held:
            c.sample_resources(owner.process.pid,Path(context['policy']['workspace_root']),context['deadline'])
            time.sleep(0.01); continue
        def footprint():
            records={}
            for child in pids:
                for path,record in c.mapped_records(child).items():
                    if path in records and records[path]!=record:
                        raise c.UnsupportedReadiness('Conflicting child mapped file identities')
                    records[path]=record
            providers=sorted(records)
            primary=records.get(fixed['programs'][role]['path'])
            if primary is None or primary['file_identity']!=context['program_before']['identity']:
                raise c.UnsupportedReadiness('Mapped primary differs from admitted prelaunch executable')
            for path in modules:
                actual=c.opened_identity(path)
                if path in records:
                    if records[path]['file_identity']!=actual:
                        raise c.UnsupportedReadiness('Module and map ordinary identities differ')
                else:
                    records[path]=dict(map_device=None,map_inode=None,file_identity=actual)
            return providers,{path:records[path] for path in sorted(records)}
        providers,identities=footprint(); again,second=footprint()
        if (providers!=again or identities!=second or c.descendants(pid,3 if role=='ninja' else 1)!=pids
                or c.pid_state(pid)[0]!=before):
            raise c.UnsupportedReadiness('Subject mappings/lifetime changed at held barrier')
        if len(providers)>4096:
            raise c.UnsupportedReadiness('Provider union exceeds bound')
        if role=='python':
            raw=marker(cwd/'startup-cache.json')
            if raw is None or c.decode(raw)!=c.empty_cache(cwd/'startup-pycache',deadline=context['deadline']):
                raise c.UnsupportedReadiness('Python startup cache prefix identity/emptiness changed')
        return dict(schema_version=1,kind='foundation-native-role7-readiness-v1',role=role,
            barrier=schedules()[role]['barrier'],primary_pid=pid,start_time=before,
            subject_pids=pids,search_paths=search,loaded_module_paths=modules,loaded_provider_paths=providers,
            loaded_file_identities=identities)


def observe_subject(role, program):
    global _LAST_CONTEXT
    c=common(); context=c.load_context(schedules(),role); cwd=context['cwd']
    _LAST_CONTEXT=context
    item=context['fixed']['programs'][role]
    if program!=item['path']:
        raise ValueError('Subject program differs from fixed original input')
    if role=='ninja':
        ninja_alias(context)
    _,before=c.program_file(item,context['deadline'])
    context['program_before']=before
    fds=[]
    snapshot=None
    def during(owner):
        nonlocal snapshot
        snapshot=held_snapshot(context,role,owner)
        if role=='cmake':
            c.write_new(cwd/'release',b'R',deadline=context['deadline'])
        else:
            token=GPERF_INPUT if role=='gperf' else b'ROLE7_RELEASE\n' if role in ('sh','ninja') else b'R'
            if os.write(fds[-1] if role=='ninja' else fds[0],token)!=len(token):
                raise ValueError('Fixed FIFO release was not written completely')
        if role=='gperf':
            os.close(fds.pop(0))  # Deliberate EOF only after the held snapshot.
    try:
        for name in ('stdin.fifo','barrier.fifo') if role=='ninja' else ('stdin.fifo',):
            os.mkfifo(cwd/name,0o600); fds.append(os.open(cwd/name,os.O_RDWR|os.O_NONBLOCK|os.O_NOFOLLOW))
        py=context['fixed']['programs']['python']['path']
        settled=c.owned([py,'-I','-B',str(BASE/'observer.py'),'--subject-worker',role],
            cwd,cwd/'subject-owner.log',context['policy']['environment'],context['deadline'],
            Path(context['policy']['workspace_root']),during)
    except c.OwnershipUncertain:
        c.ACTIVE.append((context,fds))
        raise
    except BaseException:
        for fd in fds:
            os.close(fd)
        raise
    for fd in fds:
        os.close(fd)
    _,after=c.program_file(item,context['deadline'])
    if before!=after:
        raise ValueError('Subject binary identity changed')
    if role=='python':
        raw=marker(cwd/'startup-cache.json')
        if raw is None or c.decode(raw)!=c.empty_cache(cwd/'startup-pycache',deadline=context['deadline']):
            raise c.UnsupportedReadiness('Python startup cache changed after target settlement')
    snapshot['subject_settlement']=settled
    c.recheck_context(context)
    c.write_new(cwd/'readiness.json',snapshot,deadline=context['deadline'])
    return dict(schema_version=1,kind='foundation-native-diagnostic-subject-raw-v1',
        role=role,program=item,search_paths=snapshot['search_paths'],
        loaded_module_paths=snapshot['loaded_module_paths'],loaded_provider_paths=snapshot['loaded_provider_paths'])


def observe_host():
    global _LAST_CONTEXT
    c=common(); context=c.load_context(schedules(),'host'); fixed=context['fixed']
    _LAST_CONTEXT=context
    _,before=c.program_file(fixed['programs']['python'],context['deadline'])
    raw,_=c.read_file(fixed['os_release']['path'],65536,fixed['os_release']['sha256'],deadline=context['deadline'])
    values={}
    for line in raw.decode('utf8').splitlines():
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError('Malformed os-release')
        name,text=line.split('=',1); parsed=shlex.split(text)
        if len(parsed)>1 or name in values:
            raise ValueError('Ambiguous os-release')
        values[name]=parsed[0] if parsed else ''
    distribution=dict(id=values['ID'],version_id=values['VERSION_ID'],codename=values['VERSION_CODENAME'])
    family,version=os.confstr('CS_GNU_LIBC_VERSION').split()
    if family!='glibc':
        raise c.UnsupportedReadiness('Actual glibc observation unavailable')
    identities=c.mapped_records(os.getpid()); paths=list(identities)
    primary=identities.get(fixed['programs']['python']['path'])
    if (primary is None or primary['file_identity']!=before['identity']
            or c.identity(os.stat('/proc/'+str(os.getpid())+'/exe'))!=before['identity']):
        raise c.UnsupportedReadiness('Host snapshot Python mapping differs from ordinary observed executable')
    if not set(fixed['os_provider_paths'].values())<=set(paths):
        raise c.UnsupportedReadiness('Actual libc/loader do not match fixed original provider paths')
    c.write_new(context['cwd']/'os-release.raw',raw,maximum=65536,deadline=context['deadline'])
    c.write_new(context['cwd']/'readiness.json',dict(schema_version=1,
        kind='foundation-native-role7-readiness-v1',role='host',barrier='self-host-snapshot',
        primary_pid=os.getpid(),start_time=c.pid_state(os.getpid())[0],subject_pids=[os.getpid()],
        search_paths=[],loaded_module_paths=[],loaded_provider_paths=paths,subject_settlement=None,
        loaded_file_identities=identities),
        deadline=context['deadline'])
    _,after=c.program_file(fixed['programs']['python'],context['deadline'])
    if before!=after:
        raise ValueError('Host controller identity changed')
    c.recheck_context(context)
    return dict(schema_version=1,kind='foundation-native-diagnostic-host-raw-v1',
        host=dict(system=os.uname().sysname,processor=os.uname().machine,distribution=distribution,
            libc=dict(family=family,version=version)),
        libc_provider=c.provider_id(fixed['os_provider_paths']['libc']),
        loader_provider=c.provider_id(fixed['os_provider_paths']['loader']))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--observe-host',action='store_true')
    choice.add_argument('--observe-subject',choices=('python','perl','ruby','gperf','cmake','ninja','sh'))
    choice.add_argument('--subject-worker',choices=('python','perl','ruby','gperf','cmake','ninja','sh'),help=argparse.SUPPRESS)
    parser.add_argument('--program')
    args=parser.parse_args(argv); c=common()
    if bool(args.program)!=bool(args.observe_subject):
        raise ValueError('Only subject observations require the fixed program')
    try:
        if args.subject_worker:
            worker(args.subject_worker)
            raise RuntimeError('Subject worker unexpectedly returned')
        value=observe_host() if args.observe_host else observe_subject(args.observe_subject,args.program)
        sys.stdout.buffer.write(c.canonical_raw(value)); sys.stdout.flush()
        c.check(_LAST_CONTEXT['deadline'])
        return 0
    except c.OwnershipUncertain as error:
        c.park(error)
        raise RuntimeError('Uncertain park returned')


if __name__=='__main__':
    raise SystemExit(main())
