#!/usr/bin/env python3
"""Qualify frozen retained compositions without producing or resealing kernels.

Integrity and recomposition are candidate-wide byte checks. Fixed adapters run
retained runtime scenarios, guest recovery, private archive installation and
browser interactions. No scenario selects an arbitrary command or kernel build.
"""
import argparse
from contextlib import contextmanager
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import appended_container as container
import appended_release as release
import dependency_archive as archive
from process_tree import launch, ProcessTreeError

_spec = importlib.util.spec_from_file_location('appended_check_coverage', TOOLS / 'coverage.py')
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)

ASSERTIONS = {
    'composition-integrity': ['frozen-subject', 'selected-artifact', 'retained-prefix',
                              'payload-mode', 'archive-inventory', 'input-unchanged'],
    'offline-recompose': ['frozen-subject', 'selected-artifact', 'exact-recomposition',
                          'retained-inputs-only', 'input-unchanged'],
    'retained-runtime': ['frozen-subject', 'selected-artifact', 'actual-host',
                         'extracted-inventory', 'actual-retained-runtime', 'runtime-scenario',
                         'process-tree-joined', 'runtime-unchanged', 'input-unchanged'],
    'guest-source': ['guest-source', 'guest-sdk', 'guest-compile', 'guest-tests', 'no-kernel-build'],
    'install-upgrade': ['clean-install', 'upgrade', 'remove', 'preserved-application-state'],
    'browser': ['actual-browser', 'application-scenario', 'retained-runtime'],
}
ADAPTERS = {'guest-source': 'appended_guest_check', 'install-upgrade': 'appended_install_check',
            'browser': 'appended_browser_check'}
COMMON_TOOL_SOURCES = (
    'tools/appended_release_check.py', 'tools/appended_qualification.py',
    'tools/appended_release.py', 'tools/appended_container.py', 'tools/appended_project.py',
    'tools/appended_policy.py', 'tools/appended_wasm.py', 'tools/source_identity.py',
    'tools/artifact.py', 'tools/dependency_archive.py', 'tools/process_tree.py',
    'tools/coverage.py', 'tools/certify_release.py', 'tools/release.py',
    'tools/dependency_store.py', 'tools/rust_sdk.py', 'tools/sdk_environment.py',
    'tools/sdk_manifest.py', 'tools/verify_abi.py',
)
SCOPE_TOOL_SOURCES = {
    'guest-source': ('tools/appended_guest_check.py', 'tools/appended_compile.py'),
    'install-upgrade': ('tools/appended_install_check.py',),
    'browser': ('tools/appended_browser_check.py', 'gui/tests/browser_test.py'),
}
MAX_SCENARIO = 4 * 1024 * 1024
MAX_CAPTURE = 16 * 1024 * 1024
# This fixed helper separates captures inside the existing process-tree owner.
# It accepts no shell text and records the native return code independently of
# its own successful completion. -I -S excludes Python startup injection.
CAPTURE_HELPER = '''import json, subprocess, sys
argv = json.loads(sys.argv[1])
with open(sys.argv[2], "xb") as out, open(sys.argv[3], "xb") as err:
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out,
                               stderr=err, close_fds=True)
    code = process.wait()
with open(sys.argv[4], "x", encoding="utf-8") as result:
    json.dump({"argv": argv, "exit_code": code}, result, sort_keys=True)
'''


def tool_source_catalog(scopes):
    """The reviewed tool closure whose bytes a new execution plan freezes."""
    scopes = set(scopes)
    if not scopes or not scopes <= set(ASSERTIONS):
        raise ValueError('unsupported composition source catalog scope')
    result = set(COMMON_TOOL_SOURCES)
    for scope in scopes:
        result.update(SCOPE_TOOL_SOURCES.get(scope, ()))
    return tuple(sorted(result))


def _new_json(path, value):
    c.write_new(path, value)


def _junit(path, names, *, failed=None, skipped=()):
    suite = ET.Element('testsuite', name='appended-retained-composition',
                       tests=str(len(names)), failures=str(int(failed is not None)),
                       skipped=str(len(skipped)), errors='0')
    for name in names:
        case = ET.SubElement(suite, 'testcase', name=name,
                             classname='appended-retained-composition')
        if failed is not None and name == failed[0]:
            ET.SubElement(case, 'failure', message=failed[1]).text = failed[1]
        elif name in skipped:
            ET.SubElement(case, 'skipped', message='operation did not complete')
    with path.open('xb') as stream:
        stream.write(ET.tostring(suite, encoding='utf-8', xml_declaration=True))


def _context():
    keys = {'plan': 'FOUNDATION_PLAN_ID', 'check': 'FOUNDATION_CHECK_ID',
            'run_id': 'FOUNDATION_RUN_ID', 'attempt': 'FOUNDATION_RUN_ATTEMPT',
            'qualification_policy_sha256': 'FOUNDATION_COMPOSITION_POLICY_SHA256',
            'profile': 'FOUNDATION_COMPOSITION_PROFILE'}
    result = {key: os.environ.get(value) for key, value in keys.items()}
    if any(value is not None for value in result.values()):
        if not all(isinstance(value, str) and value for value in result.values()):
            raise ValueError('complete frozen composition execution context is required')
        for key in ('plan', 'qualification_policy_sha256'):
            release._sha(result[key])
        for key in ('check', 'run_id', 'profile'):
            if not c.NAME.fullmatch(result[key]):
                raise ValueError('invalid composition execution context')
        if not result['attempt'].isdecimal() or int(result['attempt']) < 1:
            raise ValueError('invalid composition execution attempt')
        result['attempt'] = int(result['attempt'])
    result['composition_check_id'] = result['check']
    return result


def _checker_sources(scope, context):
    required = set(tool_source_catalog([scope] if type(scope) is str else scope))
    encoded = os.environ.get('FOUNDATION_COMPOSITION_TOOL_SOURCES')
    expected = release._json(encoded.encode('utf-8')) if encoded is not None else None
    if expected is not None:
        if (context['plan'] is None or type(expected) is not dict or not required <= set(expected)
                or not set(expected) <= set(tool_source_catalog(ASSERTIONS))):
            raise ValueError('frozen checker source closure differs from reviewed built-in tools')
        for name, pin in expected.items():
            container.resource_path(name)
            release._sha(pin)
    names = sorted(expected if expected is not None else required)
    snapshots = {name: container._snapshot(TOOLS.parent / name, release.MAX_JSON) for name in names}
    observed = {name: container.digest(saved.content) for name, saved in snapshots.items()}
    if expected is not None and not release._same_json(expected, observed):
        raise ValueError('actual checker source differs from before-run frozen tool pin')
    return snapshots, observed


def _retain_checker_sources(evidence, snapshots):
    root = evidence / 'checker-sources'
    root.mkdir()
    for name, saved in snapshots.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(saved.content)


@contextmanager
def _byte_operation():
    """A recomposition attempt must not create processes or contact a network."""
    state = {'active': True, 'blocked': []}

    def audit(event, _arguments):
        if state['active'] and (event == 'subprocess.Popen' or event.startswith('socket.')
                or event in ('os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.exec', 'pty.spawn')):
            state['blocked'].append(event)
            raise ValueError('retained recomposition forbids process/network operation: ' + event)

    # Audit hooks cannot be removed. The bounded hook becomes inert immediately
    # after this synchronous byte operation and never governs later runtime calls.
    sys.addaudithook(audit)
    try:
        yield state
        if state['blocked']:
            raise ValueError('recomposition attempted a forbidden operation')
    finally:
        state['active'] = False


def _subject(directory, pin):
    return release.verify_composition_subject(directory, pin)


def _uncertain(error):
    return isinstance(error, ProcessTreeError) or 'retain output ownership' in str(error)


def _selected(subject, identity):
    products = subject['composition']['artifacts']
    if not products:
        raise ValueError('composition must select an actual artifact')
    if identity is None:
        return products
    matches = [entry for entry in products if entry['id'] == identity]
    if len(matches) != 1:
        raise ValueError('select exactly one frozen artifact identity')
    return matches


def _host_target(entry, data, target, backend):
    if backend not in ('core', 'terminal'):
        raise ValueError('console runtime scenarios require core or terminal; GUI/browser needs its actual adapter')
    carrier = entry['carrier']
    if carrier == 'elf':
        endian = '<' if data[5] == 1 else '>'
        machine = struct.unpack_from(endian + 'H', data, 18)[0]
        architecture = {62: 'x86_64', 183: 'aarch64'}.get(machine)
        binary_target = 'linux-' + architecture if architecture else None
    elif carrier == 'pe':
        raise ValueError('Windows retained runtime needs its qualified permission/execution adapter')
    else:
        raise ValueError('HTML runtimes require the actual browser adapter')
    host = c.host_identity()
    machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(host['machine'].lower(), host['machine'].lower())
    if target != binary_target or target != host['system'].lower() + '-' + machine:
        raise ValueError('retained runtime must execute on its actual native target')
    return host


def _tree(directory):
    """Hash every extracted member and preserve permission/directory evidence."""
    files, directories = {}, {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('extracted runtime tree contains a link')
        mode = stat.S_IMODE(path.lstat().st_mode)
        name = path.relative_to(directory).as_posix()
        if path.is_dir():
            directories[name] = mode
        elif path.is_file():
            files[name] = {'size': path.stat().st_size, 'sha256': archive.digest(path), 'mode': mode}
        else:
            raise ValueError('extracted runtime tree contains a special file')
    return {'files': files, 'directories': directories}


def _extract(directory, entry, destination):
    # _members validates the complete archive and portable path/alias/link policy
    # before returning data. Extract manually because general legacy extraction
    # intentionally normalizes modes and cannot prove exact retained permissions.
    _, files, directories = release._members(directory / entry['archive'])
    destination.mkdir()
    for name in sorted(set(directories) | set(files)):
        path = destination / name
        if name in directories:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            data, mode = files[name]
            with path.open('xb') as stream:
                stream.write(data)
            path.chmod(mode)
    # Set restrictive directory permissions only after writing descendants.
    for name in sorted(directories, key=lambda name: len(Path(name).parts), reverse=True):
        (destination / name).chmod(directories[name])
    observed = _tree(destination)
    expected_files = {name: dict(value, mode=entry['modes'][name]) for name, value in entry['files'].items()}
    if observed['files'] != expected_files or any(observed['directories'].get(name) != mode
                                                 for name, mode in directories.items()):
        raise ValueError('extracted archive inventory or modes differ from frozen artifact')
    allowed_directories = set(directories)
    for name in set(files) | set(directories):
        allowed_directories.update(parent.as_posix() for parent in Path(name).parents if parent != Path('.'))
    if set(observed['directories']) != allowed_directories:
        raise ValueError('extracted archive directory inventory differs')
    return observed


def positive_application_call(argv, exit_code, backend):
    """Recognize the shipped CLI's app-entering calls without parsing payloads."""
    if (type(exit_code) is not int or exit_code != 0 or type(argv) is not list or not argv
            or any(type(argument) is not str for argument in argv)):
        return False
    if backend == 'terminal':
        return argv in (['--self-check'], ['--smoke-test'])
    if backend != 'core':
        return False
    values = {'--expect-mode', '--dispatch', '--dispatch-hex', '--provider',
              '--provider-operation', '--provider-payload-hex'}
    seen, index = set(), 0
    while index < len(argv):
        option = argv[index]
        key = '--dispatch' if option == '--dispatch-hex' else option
        if option not in values or key in seen or index + 1 >= len(argv):
            return False
        value = argv[index + 1]
        if option == '--expect-mode' and value not in ('neither', 'web', 'binary', 'both'):
            return False
        if option == '--provider' and (not value or value.startswith('-')):
            return False
        if option == '--provider-operation':
            decimal = value.lstrip('0') or '0'
            if (not value or any(character not in '0123456789' for character in value)
                    or len(decimal) > 10 or not 1 <= int(decimal) <= 0xffffffff):
                return False
        if option in ('--dispatch-hex', '--provider-payload-hex') and (len(value) % 2 or
                any(character not in '0123456789abcdefABCDEF' for character in value)):
            return False
        seen.add(key)
        # The next token is data, even when a dispatch payload spells --help.
        index += 2
    if {'--dispatch', '--provider'} <= seen:
        return False
    if ('--provider-operation' in seen or '--provider-payload-hex' in seen) and '--provider' not in seen:
        return False
    return '--dispatch' in seen or '--provider' in seen


def _scenario(path, pin, subject, entry, target, backend):
    if path is None or pin is None:
        raise ValueError('retained runtime needs an independently pinned nonempty scenario')
    saved = container._snapshot(path, MAX_SCENARIO)
    if container.digest(saved.content) != release._sha(pin):
        raise ValueError('runtime scenario differs from independently pinned SHA-256')
    value = release._json(saved.content)
    release._keys(value, ('schema_version', 'kind', 'candidate_sha256', 'artifact_id', 'target', 'backend', 'calls'),
                  label='runtime scenario')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-appended-runtime-scenario'
            or value['candidate_sha256'] != subject['candidate_sha256']
            or (value['artifact_id'], value['target'], value['backend']) != (entry['id'], target, backend)
            or type(value['calls']) is not list or not 1 <= len(value['calls']) <= 64):
        raise ValueError('runtime scenario does not name this exact frozen artifact and execution')
    seen = set()
    for call in value['calls']:
        release._keys(call, ('id', 'argv', 'exit_code', 'stdout', 'stderr'), label='runtime call')
        if (type(call['id']) is not str or not c.NAME.fullmatch(call['id']) or call['id'] in seen
                or type(call['argv']) is not list or len(call['argv']) > 128
                or any(type(arg) is not str or '\0' in arg or len(arg) > 4096 for arg in call['argv'])
                or type(call['exit_code']) is not int or not -255 <= call['exit_code'] <= 255
                or any(type(call[key]) is not str or len(call[key].encode('utf-8')) > MAX_SCENARIO
                       for key in ('stdout', 'stderr'))):
            raise ValueError('invalid, duplicate or excessive runtime call')
        seen.add(call['id'])
    if subject['composition']['payload']['mode'] == 'binary':
        if not any(positive_application_call(call['argv'], call['exit_code'], backend) for call in value['calls']):
            raise ValueError('binary runtime scenario needs a positive application call, not only inspection or rejection')
    return saved, value


def _environment(work):
    result = {'PATH': os.defpath, 'HOME': str(work / 'home'), 'LC_ALL': 'C', 'LANG': 'C',
              'TMPDIR': str(work / 'temporary'), 'TMP': str(work / 'temporary'), 'TEMP': str(work / 'temporary')}
    for name in ('SystemRoot', 'SYSTEMROOT', 'WINDIR'):
        if name in os.environ:
            result[name] = os.environ[name]
    for name in ('home', 'temporary'):
        (work / name).mkdir()
    return result


def _execute_runtime(argv, cwd, call_directory, environment, timeout):
    """Only physical execution boundary; all byte gates remain outside it."""
    paths = {name: call_directory / filename for name, filename in
             (('stdout', 'stdout.bin'), ('stderr', 'stderr.bin'), ('native', 'native.json'), ('supervisor', 'supervisor.log'))}
    command = [sys.executable, '-I', '-S', '-c', CAPTURE_HELPER, json.dumps(argv),
               str(paths['stdout']), str(paths['stderr']), str(paths['native'])]
    started, owner = time.monotonic(), None
    try:
        with paths['supervisor'].open('xb') as stream:
            owner = launch(command, cwd, stream, env=environment)
            while owner.poll() is None:
                if (time.monotonic() - started > timeout
                        or sum(path.stat().st_size for path in paths.values() if path.is_file()) > MAX_CAPTURE):
                    owner.terminate()
                    raise ValueError('retained runtime exceeded its time/output limit')
                time.sleep(0.02)
            code = owner.wait()
            owner.finish()
            if code != 0:
                raise ValueError('retained runtime capture helper failed; inspect supervisor.log')
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                raise ProcessTreeError('retained runtime cleanup uncertain; retain output ownership: ' + str(error)) from error
    if (time.monotonic() - started > timeout
            or sum(path.stat().st_size for path in paths.values() if path.is_file()) > MAX_CAPTURE):
        raise ValueError('retained runtime exceeded its time/output limit')
    native = c.load(paths['native'])
    if (set(native) != {'argv', 'exit_code'} or native['argv'] != argv or type(native['exit_code']) is not int):
        raise ValueError('runtime capture did not record the exact executed argv and exit code')
    return {'argv': argv, 'exit_code': native['exit_code'], 'stdout': paths['stdout'].read_bytes(),
            'stderr': paths['stderr'].read_bytes(), 'seconds': time.monotonic() - started,
            'process_tree_joined': True}


def _runtime(directory, subject, entry, target, backend, evidence, work, scenario_path, scenario_pin, timeout, passed):
    archive_path = directory / entry['archive']
    _, members, _ = release._members(archive_path)
    _host_target(entry, members[entry['runtime_member']][0], target, backend)
    passed.append('actual-host')
    saved, scenario = _scenario(scenario_path, scenario_pin, subject, entry, target, backend)
    runtime_evidence = evidence / 'runtime'
    runtime_evidence.mkdir()
    with (runtime_evidence / 'scenario.json').open('xb') as stream:
        stream.write(saved.content)
    relocated = work / 'relocated final archive with spaces'
    before = _extract(directory, entry, relocated)
    runtime = relocated / entry['runtime_member']
    if archive.digest(runtime) != entry['runtime_sha256'] or not runtime.stat().st_mode & 0o111:
        raise ValueError('selected retained runtime bytes or executable mode differ')
    passed.append('extracted-inventory')
    _new_json(runtime_evidence / 'before.json', before)
    environment = _environment(work)
    execution_cwd = work / 'application working directory with spaces'
    execution_cwd.mkdir()
    observations, completed_calls = [], []
    call_names = [call['id'] for call in scenario['calls']]
    failure, cleanup_uncertain = None, False
    try:
        for call in scenario['calls']:
            call_directory = runtime_evidence / call['id']
            call_directory.mkdir()
            argv = [str(runtime), *call['argv']]
            call_before = _tree(relocated)
            _new_json(call_directory / 'before.json', call_before)
            if call_before != before or archive.digest(runtime) != entry['runtime_sha256']:
                raise ValueError('retained runtime or extracted dependency inventory changed before call ' + call['id'])
            observed = _execute_runtime(argv, execution_cwd, call_directory, environment, timeout)
            if observed.get('process_tree_joined') is not True:
                raise ProcessTreeError('retained runtime process completion uncertain; retain output ownership')
            if observed.get('argv') != argv:
                raise ValueError('exact retained runtime execution is required')
            call_after = _tree(relocated)
            _new_json(call_directory / 'after.json', call_after)
            record = {key: observed[key] for key in ('argv', 'exit_code', 'seconds', 'process_tree_joined')}
            record.update(id=call['id'], stdout_sha256=container.digest(observed['stdout']),
                          stderr_sha256=container.digest(observed['stderr']),
                          runtime_before_sha256=call_before['files'][entry['runtime_member']]['sha256'],
                          runtime_after_sha256=call_after['files'].get(entry['runtime_member'], {}).get('sha256'))
            observations.append(record)
            _new_json(call_directory / 'observation.json', record)
            if call_after != before or record['runtime_after_sha256'] != entry['runtime_sha256']:
                raise ValueError('retained runtime or extracted dependency inventory changed during call ' + call['id'])
            if (observed['exit_code'] != call['exit_code']
                    or observed['stdout'] != call['stdout'].encode('utf-8')
                    or observed['stderr'] != call['stderr'].encode('utf-8')):
                raise ValueError('retained runtime output/exit mismatch for scenario call ' + call['id'])
            completed_calls.append(call['id'])
    except BaseException as error:
        failure = (call['id'], str(error))
        cleanup_uncertain = _uncertain(error)
        raise
    finally:
        if not cleanup_uncertain:
            skipped = [name for name in call_names if name not in completed_calls and
                       (failure is None or name != failure[0])]
            _junit(runtime_evidence / 'calls.junit.xml', call_names, failed=failure, skipped=skipped)
    passed.extend(('actual-retained-runtime', 'runtime-scenario', 'process-tree-joined'))
    after = _tree(relocated)
    _new_json(runtime_evidence / 'after.json', after)
    if after != before or archive.digest(runtime) != entry['runtime_sha256']:
        raise ValueError('retained runtime or extracted dependency inventory changed during execution')
    container._recheck(saved)
    passed.append('runtime-unchanged')
    return {'scenario_sha256': scenario_pin, 'runtime_before_sha256': entry['runtime_sha256'],
            'runtime_after_sha256': archive.digest(runtime), 'calls': observations,
            'working_directory_contains_spaces': ' ' in str(execution_cwd),
            'relocation_contains_spaces': ' ' in str(relocated)}


def _runtime_context(context):
    """Execute a nested recovered-guest test using the same exact runtime gate."""
    result = _runtime(context['directory'], context['subject'], context['artifact'],
                      context['target'], context['backend'], context['evidence'], context['work'],
                      context['scenario'], context['scenario_sha256'], context['timeout'], context['passed'])
    return dict(result, executed_tests=[call['id'] for call in result['calls']],
                junit='runtime/calls.junit.xml')


def _adapter(scope, context):
    # Module names are maintained code, never a scenario or command-line input.
    try:
        module = importlib.import_module(ADAPTERS[scope])
    except ModuleNotFoundError as error:
        if error.name == ADAPTERS[scope]:
            raise ValueError('requested composition adapter is unavailable: ' + scope) from error
        raise
    result = module.run(context)
    if type(result) is not dict:
        raise ValueError('composition adapter must return typed observation details')
    return result


def _browser_context(context):
    """Execute the fixed browser instrument, including installed HTML phases."""
    result = _adapter('browser', context)
    if context['passed'] != ASSERTIONS['browser']:
        raise ValueError('browser instrument did not complete its exact executed assertion inventory')
    if not release._same_json(result.get('checker_sources'), context['checker_sources']):
        raise ValueError('browser instrument changed the frozen checker source closure')
    return result


def check(directory, candidate_sha256, target, backend, scope, evidence, *, artifact_id=None,
          scenario=None, scenario_sha256=None, timeout=60, junit_name='qualification.junit.xml'):
    if scope not in ASSERTIONS:
        raise ValueError('no self-verifying adapter for requested composition scope: ' + scope)
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError('runtime timeout must be positive and at most 300 seconds')
    directory = container._ordinary_path(directory, directory=True)
    evidence = Path(os.path.abspath(os.fspath(evidence)))
    if evidence == directory or directory in evidence.parents:
        raise ValueError('qualification evidence must be outside the immutable candidate')
    if scope in ('composition-integrity', 'offline-recompose'):
        if artifact_id is not None or (target, backend) != ('composition', 'none') or scenario is not None or scenario_sha256 is not None:
            raise ValueError('global byte checks require composition/none and no artifact or runtime scenario')
    elif scope == 'guest-source':
        if artifact_id is not None or (target, backend) != ('portable-wasm32', 'guest') or scenario is None or scenario_sha256 is None:
            raise ValueError('guest recovery requires portable-wasm32/guest, no artifact, and a pinned scenario')
    elif artifact_id is None:
        raise ValueError('artifact qualification requires an exact selected artifact')
    context = _context()
    code_snapshots, checker_sources = _checker_sources(scope, context)
    subject = _subject(directory, candidate_sha256)
    selected = _selected(subject, artifact_id)
    if artifact_id is not None and selected[0]['carrier'] == 'html' and scope in ('retained-runtime', 'install-upgrade'):
        for saved in code_snapshots.values():
            container._recheck(saved)
        code_snapshots, checker_sources = _checker_sources((scope, 'browser'), context)
    evidence.mkdir(parents=True, exist_ok=True)
    container._ordinary_path(evidence, directory=True)
    if len(c.relative(junit_name).parts) != 1 or not junit_name.endswith('.xml'):
        raise ValueError('primary qualification JUnit must be a new XML basename')
    junit_path = c.local(evidence, junit_name)
    reserved = ('qualification.json', 'subject.json', 'failure.json', 'runtime', 'guest', 'install', 'browser',
                'recomposition.json', 'retained-work.json', 'guest.junit.xml', 'checker-sources')
    if any((evidence / name).exists() for name in reserved) or junit_path.exists():
        raise ValueError('qualification outputs must be new for this attempt')
    passed = [] if scope in ADAPTERS else ['frozen-subject', 'selected-artifact']
    details = {**context, 'candidate_sha256': subject['candidate_sha256'],
               'composition_sha256': subject['composition_sha256'], 'selection_sha256': subject['selection_sha256'],
               'source_tree_sha256': subject['composition']['source']['tree_sha256'],
               'checker_sources': checker_sources,
               'artifacts': [{'id': item['id'], 'archive': item['archive'], 'archive_sha256': item['sha256'],
                              'runtime_member': item['runtime_member'], 'runtime_sha256': item['runtime_sha256'],
                              'kernel_prefix_sha256': item['kernel_prefix_sha256']} for item in selected]}
    if artifact_id is not None:
        details.update(artifact_id=artifact_id, archive_sha256=selected[0]['sha256'],
                       runtime_member=selected[0]['runtime_member'], runtime_sha256=selected[0]['runtime_sha256'],
                       scenario_sha256=scenario_sha256)
    elif scenario is not None:
        details['scenario_sha256'] = scenario_sha256
    _retain_checker_sources(evidence, code_snapshots)
    _new_json(evidence / 'subject.json', details)
    work = Path(tempfile.mkdtemp(prefix='foundation appended qualification '))
    context_data = {'directory': directory, 'subject': subject,
        'artifact': selected[0] if artifact_id is not None else None,
        'target': target, 'backend': backend, 'evidence': evidence, 'work': work,
        'scenario': Path(scenario) if scenario is not None else None,
        'scenario_sha256': scenario_sha256, 'timeout': timeout, 'passed': passed,
        'execution_context': context, 'checker_sources': checker_sources,
        'helpers': {'extract': _extract, 'tree': _tree, 'execute': _execute_runtime,
            'environment': _environment, 'new_json': _new_json, 'junit': _junit,
            'uncertain': _uncertain, 'host_target': _host_target, 'runtime': _runtime_context,
            'browser': _browser_context, 'application_call': positive_application_call}}
    cleanup_safe = True
    failure = None
    try:
        if scope == 'composition-integrity':
            # The deep verifier compared original/final complete member bytes,
            # all modes/directories, exact prefix, payload mode and native closure.
            passed.extend(('retained-prefix', 'payload-mode', 'archive-inventory'))
            details['mode'] = subject['composition']['payload']['mode']
        elif scope == 'offline-recompose':
            recovered = work / 'offline recomposed candidate'
            with _byte_operation():
                result = release.recover(directory, candidate_sha256, recovered)
            observed = _subject(recovered, candidate_sha256)
            if (result['candidate_sha256'] != candidate_sha256 or observed != subject
                    or release._files(recovered) != release._files(directory)):
                raise ValueError('offline recomposition differs from exact frozen candidate')
            passed.extend(('exact-recomposition', 'retained-inputs-only'))
            details['recomposition'] = {'candidate_sha256': result['candidate_sha256'],
                                        'processes_permitted': False, 'network_permitted': False,
                                        'native_reconstruction': False}
            _new_json(evidence / 'recomposition.json', details['recomposition'])
        elif scope == 'retained-runtime':
            if selected[0]['carrier'] == 'html':
                observed = _browser_context(dict(context_data, passed=[]))
                passed.extend(('actual-host', 'extracted-inventory', 'actual-retained-runtime',
                               'runtime-scenario', 'process-tree-joined', 'runtime-unchanged'))
                details['runtime'] = observed
                details['browser'] = observed['browser']
            else:
                details['runtime'] = _runtime(directory, subject, selected[0], target, backend, evidence, work,
                                               scenario, scenario_sha256, timeout, passed)
        else:
            observed = _adapter(scope, context_data)
            if any(key in details and not release._same_json(value, details[key]) for key, value in observed.items()):
                raise ValueError('composition adapter attempted to change immutable execution bindings')
            details.update(observed)
        if _subject(directory, candidate_sha256) != subject:
            raise ValueError('frozen composition changed during qualification')
        for name, saved in code_snapshots.items():
            container._recheck(saved)
            if archive.digest(evidence / 'checker-sources' / name) != checker_sources[name]:
                raise ValueError('retained checker source changed during qualification')
        if scope not in ADAPTERS:
            passed.append('input-unchanged')
        if passed != ASSERTIONS[scope]:
            raise ValueError('internal executed assertion inventory differs from fixed adapter contract')
    except BaseException as error:
        failure = error
        if _uncertain(error):
            cleanup_safe = False
            _new_json(evidence / 'retained-work.json', {'status': 'incomplete', 'workspace': str(work),
                                                      'reason': str(error)})
        raise
    finally:
        if cleanup_safe:
            shutil.rmtree(work)
        if failure is not None and cleanup_safe:
            remaining = [name for name in ASSERTIONS[scope] if name not in passed]
            failed = remaining[0] if remaining else ASSERTIONS[scope][-1]
            _junit(junit_path, ASSERTIONS[scope], failed=(failed, str(failure)), skipped=remaining[1:])
            _new_json(evidence / 'failure.json', {'status': 'failed', 'error': str(failure), 'details': details,
                                                'completed_assertions': passed})
    _junit(junit_path, ASSERTIONS[scope])
    evidence_map = {}
    for path in sorted(evidence.rglob('*')):
        if path.is_symlink():
            raise ValueError('qualification evidence contains a link')
        if path.is_file() and path.name not in ('console.log', 'result.json', 'qualification.json'):
            evidence_map[path.relative_to(evidence).as_posix()] = archive.digest(path)
    receipt = {'schema_version': 1, 'source_sha256': subject['composition']['source']['sha256'],
               'inventory_sha256': candidate_sha256, 'target': target, 'backend': backend, 'scope': scope,
               'host': c.host_identity(), 'status': 'passed', 'details': details,
               'assertions': ASSERTIONS[scope], 'evidence': evidence_map}
    _new_json(evidence / 'qualification.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scope')
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--candidate-sha256', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backend', required=True)
    parser.add_argument('--artifact')
    parser.add_argument('--scenario', type=Path)
    parser.add_argument('--scenario-sha256')
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--junit', default='qualification.junit.xml')
    args = parser.parse_args(argv)
    try:
        result = check(args.release, args.candidate_sha256, args.target, args.backend, args.scope, args.evidence,
                       artifact_id=args.artifact, scenario=args.scenario, scenario_sha256=args.scenario_sha256,
                       timeout=args.timeout, junit_name=args.junit)
    except (OSError, ValueError, ProcessTreeError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({'status': result['status'], 'scope': args.scope, 'candidate_sha256': args.candidate_sha256}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
