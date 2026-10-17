"""Finite ROLE7 mechanics. Missing independent pins refuse before body reads."""
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import signal
import stat
import sys
import time
import types
from datetime import datetime, timezone

BASE = Path(__file__).absolute().parent
ROOT = Path('/home/user/___quick/p/_cur/dataPump/_lessonsLearned/software-foundation')
FIXED_INPUT_SHA256 = None
FIXED_POLICY_SHA256 = None
TREE_SHA256 = '521fa923a4396afeda67b05efabb0c21f1161895fbe72f172d4d7dfc69c1496f'
ROLES = ('python', 'perl', 'ruby', 'gperf', 'cmake', 'ninja', 'sh')
INTERPRETERS = ('python', 'perl', 'ruby')
READINESS_BARRIERS = dict(python='report-and-owned-stdin-read',perl='report-and-owned-stdin-read',
    ruby='report-and-owned-stdin-read',gperf='owned-stdin-read',
    cmake='pure-script-ready-release-loop',ninja='owned-rule-shell-read',sh='builtin-owned-stdin-read')
ENV_FIELDS = ('PATH', 'LANG', 'LC_ALL', 'TZ', 'SOURCE_DATE_EPOCH', 'PYTHONPATH', 'PERL5LIB', 'RUBYLIB')
BOUNDS = dict(work_seconds=115, cleanup_seconds=5, stage_seconds=10,
    maximum_process_bytes=512 * 1024**2, maximum_stream_bytes=1024**2,
    maximum_output_bytes=8 * 1024**2, maximum_paths=4096, maximum_os_release_bytes=65536,
    maximum_subject_processes=3, maximum_total_descendants=32, maximum_live_descendants=6)
ACTIVE = []
PENDING_SIGNAL = None


class MissingInputs(ValueError):
    def __init__(self, role, reason):
        self.missing = [dict(role=role, path='', reason=reason)]
        super().__init__(reason)


class UnsupportedReadiness(ValueError):
    pass


class IdentityChanged(ValueError):
    pass


class OwnershipUncertain(RuntimeError):
    def __init__(self, owner, log, original):
        self.owner, self.log, self.original = owner, log, original
        super().__init__('ROLE7 owned lifetime uncertain: ' + str(original))


def canonical_raw(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(',', ':')) + '\n').encode('utf8')


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(label + ' requires exact closed fields')
    return value


def pin(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value) or value == '0' * 64:
        raise ValueError('Independent nonzero SHA256 required')
    return value


def absolute(value):
    if type(value) is not str or not re.fullmatch(r'/[A-Za-z0-9_./+-]+', value):
        raise ValueError('Literal ordinary absolute path required')
    if posixpath.normpath(value) != value or str(Path(value)) != value:
        raise ValueError('Normalized absolute path required')
    return Path(value)


def check(deadline, *, cleanup=False):
    if PENDING_SIGNAL is not None and not cleanup:
        raise InterruptedError('ROLE7 guarded signal pending: ' + str(PENDING_SIGNAL))
    if time.monotonic() >= deadline:
        raise TimeoutError('Original ROLE7 work deadline expired')


def identity(s):
    return [s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def regular(path):
    path = absolute(str(path))
    for part in reversed((path, *path.parents)):
        state = part.lstat()
        if part == path:
            if not stat.S_ISREG(state.st_mode) or state.st_nlink != 1:
                raise ValueError('Independent regular file required')
        elif not stat.S_ISDIR(state.st_mode):
            raise ValueError('Ordinary ancestors required')
    return path


def read_file(path, maximum, expected=None, *, deadline=None):
    path = regular(path); before = path.lstat()
    if before.st_size > maximum:
        raise ValueError('ROLE7 bounded file exceeds limit')
    raw = bytearray()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise IdentityChanged('ROLE7 identity changed before reading')
        while True:
            if deadline is not None:
                check(deadline)
            block = stream.read(min(65536, maximum + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
            if len(raw) > maximum:
                raise ValueError('ROLE7 bounded read overflow')
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise IdentityChanged('ROLE7 identity changed during read')
    digest = hashlib.sha256(raw).hexdigest()
    if identity(path.lstat()) != identity(before) or len(raw) != before.st_size:
        raise IdentityChanged('ROLE7 exact original identity mismatch')
    if expected is not None and digest != pin(expected):
        raise ValueError('ROLE7 exact original byte mismatch')
    if deadline is not None:
        check(deadline)
    return bytes(raw), dict(path=str(path), sha256=digest, bytes=len(raw), identity=identity(before))


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate ROLE7 JSON field')
            value[key] = item
        return value
    value = json.loads(raw.decode('utf8'), object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    canonical_raw(value)
    return value


def write_new(path, value, *, maximum=1024**2, deadline=None):
    if deadline is not None:
        check(deadline)
    raw = value if type(value) is bytes else canonical_raw(value)
    if len(raw) > maximum:
        raise ValueError('ROLE7 output overflow; no truncation')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        os.fchmod(stream.fileno(), 0o644)
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if deadline is not None:
        check(deadline)
    return dict(path=Path(path).name, sha256=hashlib.sha256(raw).hexdigest())


def validate_fixed_input(value):
    fields(value, ('schema_version', 'kind', 'programs', 'interpreter_paths',
        'os_release', 'os_provider_paths'), 'ROLE7 fixed input')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != 'foundation-native-role7-fixed-input-v1':
        raise ValueError('Unknown ROLE7 fixed input')
    fields(value['programs'], ROLES, 'ROLE7 programs')
    for item in value['programs'].values():
        fields(item, ('path', 'sha256', 'version'), 'Original program')
        absolute(item['path']); pin(item['sha256'])
        if type(item['version']) is not str or not re.fullmatch(r'[A-Za-z0-9._+-]{1,128}', item['version']):
            raise ValueError('Original hash-bound version required')
    fields(value['interpreter_paths'], INTERPRETERS, 'Interpreter search paths')
    for paths in value['interpreter_paths'].values():
        if type(paths) is not list or not 1 <= len(paths) <= 256 or paths != sorted(set(paths)):
            raise ValueError('Sorted finite interpreter paths required')
        for path in paths:
            absolute(path)
    fields(value['os_release'], ('path', 'sha256'), 'Original os-release')
    absolute(value['os_release']['path']); pin(value['os_release']['sha256'])
    fields(value['os_provider_paths'], ('libc', 'loader'), 'Original OS providers')
    for path in value['os_provider_paths'].values():
        absolute(path)
    if len(set(value['os_provider_paths'].values())) != 2:
        raise ValueError('Distinct libc and loader required')
    return value


def load_fixed_input():
    if FIXED_INPUT_SHA256 is None or FIXED_POLICY_SHA256 is None:
        raise MissingInputs('diagnostic-role7-fixed-input-authority',
            'Independently reviewed fixed input/policy source pins are absent')
    raw, record = read_file(BASE / 'role7-input.json', 65536, pin(FIXED_INPUT_SHA256))
    return validate_fixed_input(decode(raw)), record


def validate_policy(value, fixed, schedules):
    fields(value, ('schema_version', 'kind', 'input_sha256', 'workspace_root', 'environment',
        'bounds', 'schedules', 'ninja_shell_alias', 'os_manifest_sha256',
        'os_original_record_sha256', 'cpu'), 'ROLE7 launch policy')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-native-role7-launch-policy-v1'
            or value['input_sha256'] != FIXED_INPUT_SHA256
            or canonical_raw(value['bounds']) != canonical_raw(BOUNDS)
            or canonical_raw(value['schedules']) != canonical_raw(schedules)
            or type(value['cpu']) is not int or value['cpu'] < 0):
        raise ValueError('Exact ROLE7 schedule/bounds/input differs')
    absolute(value['workspace_root']); pin(value['os_manifest_sha256']); pin(value['os_original_record_sha256'])
    env = fields(value['environment'], ENV_FIELDS, 'Exact diagnostic environment')
    if any(type(item) is not str for item in env.values()):
        raise ValueError('String environment required')
    paths = env['PATH'].split(':')
    if paths != sorted(set(paths)) or not paths:
        raise ValueError('Sorted explicit PATH required')
    for path in paths:
        absolute(path)
    if not {str(Path(item['path']).parent) for item in fixed['programs'].values()} <= set(paths):
        raise ValueError('PATH omits an admitted program parent')
    if (env['LANG'] != 'C.UTF-8' or env['LC_ALL'] != 'C.UTF-8' or env['TZ'] != 'UTC'
            or not re.fullmatch('[0-9]{1,12}', env['SOURCE_DATE_EPOCH'])):
        raise ValueError('Exact locale/time environment required')
    for role, name in (('python', 'PYTHONPATH'), ('perl', 'PERL5LIB'), ('ruby', 'RUBYLIB')):
        if env[name] != ':'.join(fixed['interpreter_paths'][role]):
            raise ValueError('Interpreter environment differs from admitted paths')
    return value


def load_context(schedules, role):
    deadline = time.monotonic() + (115 if role == 'capture' else 10)
    fixed, input_record = load_fixed_input()
    raw, policy_record = read_file(BASE / 'role7-launch-policy.json', 65536, pin(FIXED_POLICY_SHA256))
    policy = validate_policy(decode(raw), fixed, schedules)
    if role not in (*ROLES, 'host', 'capture'):
        raise ValueError('Unknown fixed role')
    cwd = absolute(str(Path.cwd()))
    expected = absolute(policy['workspace_root'])
    if role != 'capture':
        expected /= role
    if cwd != expected:
        raise ValueError('ROLE7 cwd differs from reviewed workspace')
    validate_controller(fixed, deadline)
    return dict(fixed=fixed, input=input_record, policy=policy, policy_record=policy_record,
        cwd=cwd, deadline=deadline)


def validate_controller(fixed, deadline):
    if not sys.platform.startswith('linux') or os.uname().machine != 'x86_64' or not sys.dont_write_bytecode:
        raise UnsupportedReadiness('Fixed Linux/x86_64 bytecode-disabled controller required')
    controller = fixed['programs']['python']
    if str(Path(sys.executable).resolve()) != controller['path']:
        raise ValueError('Actual supervisor Python differs from admitted Python')
    return program_file(controller, deadline)[1]


def program_file(item, deadline):
    raw, record = read_file(item['path'], 128 * 1024**2, item['sha256'], deadline=deadline)
    if stat.S_IMODE(record['identity'][2]) != 0o755:
        raise ValueError('Original executable must be an ordinary 0755 file')
    return raw, record


def recheck_context(context):
    read_file(context['input']['path'], 65536, context['input']['sha256'], deadline=context['deadline'])
    read_file(context['policy_record']['path'], 65536, context['policy_record']['sha256'], deadline=context['deadline'])


def provider_id(path):
    return 'provider-' + hashlib.sha256(str(absolute(path)).encode('utf8')).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def load_tree():
    path = ROOT / 'tools/process_tree.py'
    raw, _ = read_file(path, 131072, TREE_SHA256)
    module = types.ModuleType('role7_fixed_process_tree'); module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def proc_read(path, maximum):
    with open(path, 'rb', buffering=0) as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise UnsupportedReadiness('Bounded /proc record overflow')
    return raw.decode('utf8')


def pid_state(pid):
    parts = proc_read('/proc/' + str(pid) + '/stat', 65536).rsplit(')', 1)[1].split()
    if len(parts) < 20:
        raise UnsupportedReadiness('Malformed original PID state')
    return parts[19], parts[0]


def descendants(root, maximum=64, *, allow_vanished=False):
    pending, found = [root], []
    while pending:
        pid = pending.pop()
        if pid in found:
            raise UnsupportedReadiness('Ambiguous observed process tree')
        found.append(pid)
        if len(found) > maximum:
            raise UnsupportedReadiness('Observed process count exceeds fixed schedule')
        try:
            text = proc_read('/proc/' + str(pid) + '/task/' + str(pid) + '/children', 65536)
        except FileNotFoundError:
            if allow_vanished:
                continue
            raise
        for name in text.split():
            if not name.isdecimal() or int(name) <= 0:
                raise UnsupportedReadiness('Malformed original child PID')
            pending.append(int(name))
    return sorted(found)


def opened_identity(path):
    path=regular(path); before=identity(path.lstat())
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        actual=identity(os.fstat(descriptor))
        if actual!=before or identity(path.lstat())!=actual:
            raise IdentityChanged('Opened observed file identity changed')
        return actual
    finally:
        os.close(descriptor)


def empty_cache(path, *, create=False, deadline=None):
    if deadline is not None:
        check(deadline)
    path=absolute(str(path))
    if create:
        path.mkdir(mode=0o755)  # Fresh only; never adopt an existing cache.
    before=path.lstat()
    if not stat.S_ISDIR(before.st_mode) or stat.S_IMODE(before.st_mode)!=0o755:
        raise ValueError('Owned empty startup cache must be an ordinary0755 directory')
    descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        if identity(os.fstat(descriptor))!=identity(before):
            raise IdentityChanged('Startup cache changed before inspection')
        with os.scandir(path) as entries:
            if next(entries,None) is not None:
                raise ValueError('Owned startup cache is not empty')
        if identity(os.fstat(descriptor))!=identity(before) or identity(path.lstat())!=identity(before):
            raise IdentityChanged('Startup cache changed during inspection')
    finally:
        os.close(descriptor)
    if deadline is not None:
        check(deadline)
    return dict(path=str(path),identity=identity(before))


def mapped_records(pid):
    before = pid_state(pid)[0]
    records = {}
    for line in proc_read('/proc/' + str(pid) + '/maps', 1024**2).splitlines():
        pieces = line.split(None, 5)
        if len(pieces)<5:
            raise UnsupportedReadiness('Malformed original maps line')
        if len(pieces) < 6 or not pieces[5].startswith('/'):
            continue
        name = pieces[5]
        if name.endswith(' (deleted)'):
            raise UnsupportedReadiness('Deleted mapping cannot establish a provider')
        path = absolute(name)
        if (not re.fullmatch('[0-9a-fA-F]{1,8}:[0-9a-fA-F]{1,8}',pieces[3])
                or not re.fullmatch('[0-9]{1,20}',pieces[4]) or not 1<=int(pieces[4])<2**64):
            raise UnsupportedReadiness('Malformed mapped device/inode')
        device=[int(item,16) for item in pieces[3].split(':')]; inode=int(pieces[4])
        physical=opened_identity(path)
        if [os.major(physical[0]),os.minor(physical[0])]!=device or physical[1]!=inode:
            raise UnsupportedReadiness('Mapped device/inode differs from opened ordinary path')
        record=dict(map_device=device,map_inode=inode,file_identity=physical)
        if str(path) in records and records[str(path)]!=record:
            raise UnsupportedReadiness('Conflicting mapped identity for one ordinary path')
        records[str(path)]=record
        if len(records) > 4096:
            raise UnsupportedReadiness('Mapped provider bound exceeded')
    if pid_state(pid)[0] != before:
        raise UnsupportedReadiness('PID lifetime changed during maps read')
    return {path:records[path] for path in sorted(records)}


def mapped_paths(pid):
    return list(mapped_records(pid))


def sample_resources(root, workspace, deadline):
    check(deadline); rss = 0
    pids = descendants(root, BOUNDS['maximum_live_descendants'], allow_vanished=True)
    for pid in sorted(set(pids + [os.getpid()])):
        try:
            text = proc_read('/proc/' + str(pid) + '/status', 65536)
        except FileNotFoundError:
            continue
        matches = re.findall(r'^VmRSS:\s+([0-9]+)\s+kB$', text, re.M)
        if len(matches)!=1:
            try:
                if not matches and pid_state(pid)[1]=='Z':
                    continue
            except FileNotFoundError:
                continue
            raise UnsupportedReadiness('Sampled live RSS record missing or malformed')
        rss += int(matches[0]) * 1024
    total, pending, count = 0, [workspace], 0
    while pending:
        check(deadline); path = pending.pop(); state = path.lstat(); count += 1
        if count > 256:
            raise ValueError('ROLE7 output shape overflow')
        if stat.S_ISDIR(state.st_mode):
            with os.scandir(path) as entries:
                children = []
                for entry in entries:
                    if len(children) >= 256:
                        raise ValueError('ROLE7 output child overflow')
                    children.append(Path(entry.path))
                pending.extend(children)
        elif stat.S_ISREG(state.st_mode) and state.st_nlink == 1:
            total += state.st_size
        elif stat.S_ISFIFO(state.st_mode) and path.name in ('stdin.fifo', 'barrier.fifo'):
            pass
        else:
            raise ValueError('Unexpected ROLE7 output object')
    if rss > BOUNDS['maximum_process_bytes'] or total > BOUNDS['maximum_output_bytes']:
        raise ValueError('ROLE7 sampled RSS/output exceeded')
    check(deadline)
    return rss, total


def supervision_report(report, code, *, cleanup=False):
    return (type(code) is int and type(report) is dict
        and set(report) == {'schema_version', 'primary_returncode', 'descendants_outlived',
            'terminated', 'error', 'reaped'}
        and type(report['schema_version']) is int and report['schema_version'] == 1
        and type(report['primary_returncode']) is int and report['primary_returncode'] == code
        and report['descendants_outlived'] is False and report['error'] is None
        and type(report['terminated']) is bool and (cleanup or report['terminated'] is False)
        and type(report['reaped']) is int and report['reaped'] >= 1)


def guarded_signal(signum, _frame):
    global PENDING_SIGNAL
    if PENDING_SIGNAL is None:
        PENDING_SIGNAL = signum  # First reason only; never throw across opaque launch.


def owned(argv, cwd, log_path, environment, deadline, workspace, during=None):
    """Internal fixed factories only. No CLI accepts argv or descriptors."""
    owner = log = None
    attempted = settlement_started = log_closure_started = uncertain = False
    handlers = {}
    retained = dict(owner=None, log=None, phase='before-launch')
    ACTIVE.append(retained)
    started = utc()
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            handlers[signum] = signal.signal(signum, guarded_signal)
        tree = load_tree(); log = open(log_path, 'xb'); retained['log'] = log
        os.fchmod(log.fileno(),0o644)
        check(deadline); attempted = True
        retained['phase'] = 'opaque-launch'
        owner = tree.launch(argv, cwd, log, env=environment); retained['owner'] = owner
        retained['phase'] = 'owned'; check(deadline)
        if during is not None:
            during(owner)
        while owner.poll() is None:
            sample_resources(owner.process.pid, workspace, deadline); time.sleep(0.02)
        settlement_started = True
        code = owner.finish()
        if not supervision_report(owner.process.report, code):
            raise ValueError('Exact natural ROLE7 supervisor report required before close')
        owner.close()
        if owner.closed is not True:
            raise ValueError('ROLE7 owner did not report actual closed state')
        log_closure_started = True
        log.flush(); os.fsync(log.fileno()); log.close(); check(deadline)
        sample_resources(os.getpid(), workspace, deadline); check(deadline)
        retained['phase'] = 'closed'
        if code != 0:
            raise ValueError('Fixed ROLE7 command failed: ' + str(code))
        return dict(returncode=code, started_utc=started, finished_utc=utc(),
            supervision=dict(owner.process.report),
            ownership=dict(closed=True, descendants_closed=True, logs_closed=True))
    except BaseException as original:
        uncertain = owner is None and attempted
        if owner is not None and not owner.closed and settlement_started:
            # finish/close is opaque. Do not attempt a second settlement.
            uncertain = True
        elif owner is not None and not owner.closed:
            settlement_started = True
            stop = min(deadline + 5, time.monotonic() + 5)
            try:
                check(stop, cleanup=True)
                owner.terminate(timeout=max(0.001, stop - time.monotonic()))
                check(stop, cleanup=True)
                code = owner.process.returncode
                if not supervision_report(owner.process.report, code, cleanup=True):
                    raise ValueError('Exact cleanup ROLE7 supervisor report required before close')
                owner.close(); check(stop, cleanup=True)
                if owner.closed is not True:
                    raise ValueError('ROLE7 cleanup owner did not close')
            except BaseException:
                uncertain = True
        if not uncertain and log is not None and not log.closed and log_closure_started:
            uncertain = True
        if not uncertain and log is not None and not log.closed:
            try:
                log_closure_started = True
                log.flush(); os.fsync(log.fileno()); log.close()
            except BaseException:
                uncertain = True
        if uncertain:
            retained['phase'] = 'uncertain'
            error = OwnershipUncertain(owner, log, original); ACTIVE.append((owner, log, error))
            raise error from original
        retained['phase'] = 'failed-closed'
        raise
    finally:
        if not uncertain:
            for signum, previous in handlers.items():
                signal.signal(signum, previous)


def park(error):
    ACTIVE.append(error)
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, lambda *_: None)
    except BaseException:
        pass
    while True:
        park_step()


def park_step():
    try:
        time.sleep(30)
    except BaseException:
        pass
