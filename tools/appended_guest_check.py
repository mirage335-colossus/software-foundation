#!/usr/bin/env python3
"""Recover one guest from pinned source/SDK inputs and execute its exact bytes.

This adapter has no build-system or download fallback. It compiles one portable
guest, requires exact delivered-module reproduction, and delegates actual tests
to the fixed retained-runtime or browser adapter against the unchanged candidate.
"""
from contextlib import contextmanager
import hashlib
import ntpath
from pathlib import Path
import tarfile
import threading
import xml.etree.ElementTree as ET

import appended_compile as compiler
import appended_container as container
import appended_project as project
import appended_release as release
import appended_wasm
import dependency_archive as archive
from process_tree import ProcessTreeError

MAX_INPUT = 512 * 1024 * 1024
MAX_INPUTS = 1024 * 1024 * 1024
MAX_SDK_BYTES = 1024 * 1024 * 1024
MAX_SDK_ENTRIES = 100000
MAX_JSON = 4 * 1024 * 1024
ASSERTIONS = ['guest-source', 'guest-sdk', 'guest-compile', 'guest-tests', 'no-kernel-build']
RECEIPT_FIELDS = ('schema_version', 'profile', 'language', 'sources', 'bindings',
                  'sdk_descriptor_sha256', 'sdk_inventory_sha256', 'compiler_helper_sha256',
                  'validator_sha256', 'host', 'commands', 'module', 'audit')
_COMPILE_LOCK = threading.RLock()


def _same(left, right):
    return container.canonical_json(left) == container.canonical_json(right)


def _save(path, data):
    with path.open('xb') as stream:
        stream.write(data)


def _scenario(context):
    saved = container._snapshot(context['scenario'], MAX_JSON)
    if container.digest(saved.content) != release._sha(context['scenario_sha256']):
        raise ValueError('guest scenario differs from its independently pinned bytes')
    value = release._json(saved.content)
    release._keys(value, ('schema_version', 'kind', 'candidate_sha256', 'language', 'entries',
                         'memory_pages', 'max_memory_pages', 'reproduction', 'inputs', 'sdk',
                         'compile_receipt', 'test'), label='guest-source scenario')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-appended-guest-source-scenario'
            or value['candidate_sha256'] != context['subject']['candidate_sha256']
            or value['language'] not in ('c', 'c++', 'rust') or value['reproduction'] != 'byte-exact'
            or type(value['entries']) is not list or not 1 <= len(value['entries']) <= 64
            or any(type(entry) is not str for entry in value['entries'])
            or len(set(value['entries'])) != len(value['entries'])
            or type(value['memory_pages']) is not int or type(value['max_memory_pages']) is not int
            or not 2 <= value['memory_pages'] <= value['max_memory_pages'] <= 256):
        raise ValueError('guest scenario requires this exact candidate and a bounded byte-exact compilation')
    for name in value['entries']:
        container.resource_path(name)
    if value['language'] == 'rust' and len(value['entries']) != 1:
        raise ValueError('Rust guest recovery needs one explicit crate root')
    release._keys(value['sdk'], ('archive', 'descriptor', 'descriptor_sha256'), label='guest SDK input')
    release._sha(value['sdk']['descriptor_sha256'])
    container.resource_path(value['sdk']['descriptor'])
    release._keys(value['test'], ('adapter', 'artifact_id', 'scenario'), label='guest test selection')
    if value['test']['adapter'] not in ('retained-runtime', 'browser'):
        raise ValueError('guest tests require an implemented fixed runtime adapter')
    release._name(value['test']['artifact_id'])
    inputs = value['inputs']
    if type(inputs) is not dict or not 1 <= len(inputs) <= 128:
        raise ValueError('guest recovery needs a bounded complete pinned input map')
    registry = archive.PathInventory()
    for name, pin in inputs.items():
        container.resource_path(name)
        registry.add(name, False)
        release._sha(pin)
    for name in (value['sdk']['archive'], value['compile_receipt'], value['test']['scenario']):
        container.resource_path(name)
        if name not in inputs:
            raise ValueError('guest scenario input reference is not independently pinned')
    snapshots, total = {}, 0
    for name, pin in inputs.items():
        snapshot = container._snapshot(saved.path.parent / name, MAX_INPUT)
        total += len(snapshot.content)
        if total > MAX_INPUTS or container.digest(snapshot.content) != pin:
            raise ValueError('guest input group exceeds limits or differs from its pinned inventory')
        snapshots[name] = snapshot
    return saved, value, snapshots


def _sdk_bundle(path, output):
    # Bound entry count before the shared extractor materializes its inventory.
    total, count, registry = 0, 0, archive.PathInventory()
    with tarfile.open(path, 'r:*') as bundle:
        for member in bundle:
            count += 1
            total += member.size
            name = member.name.rstrip('/') if member.isdir() else member.name
            registry.add(name, member.isdir())
            if (count > MAX_SDK_ENTRIES or member.size < 0 or total > MAX_SDK_BYTES
                    or not (member.isfile() or member.isdir()) or member.mode & 0o7000):
                raise ValueError('guest SDK bundle exceeds limits or contains linked/special/privileged entries')
    archive.extract(path, output, max_bytes=MAX_SDK_BYTES)


def _bindings(root, language):
    files = compiler._binding_sources(root, language)
    return {name: compiler._digest(path) for name, path in sorted(files.items())}


def _commands(commands, sdk, host):
    if (type(commands) is not list or not commands or len(commands) > 128
            or any(type(argv) is not list or not argv or
                   any(type(part) is not str or '\0' in part for part in argv) for argv in commands)):
        raise ValueError('guest compile receipt needs exact ordered command arrays')
    def separators(value):
        return value.replace('\\', '/') if host['system'] == 'Windows' else value
    first = separators(commands[0][0])
    suffix = '/' + sdk['tools']['clang']
    if not first.endswith(suffix):
        raise ValueError('original guest compile does not start with its inventoried C runtime compiler')
    root = first[:-len(suffix)]
    if not root or not (Path(root).is_absolute() or ntpath.isabs(root)):
        raise ValueError('guest compiler command needs an explicit absolute SDK root')
    known = {root + '/' + name: name for name in sdk['tools'].values()}
    normalized = []
    for original in commands:
        argv = list(original)
        executable = separators(argv[0])
        if executable not in known:
            raise ValueError('guest command selects a tool outside the one pinned SDK')
        argv[0] = '$SDK/' + known[executable]
        for index, part in enumerate(argv[1:], 1):
            if '$WORK' in part:
                argv[index] = separators(part)
            for option in ('-ffile-prefix-map=', '-fmacro-prefix-map=', '-fdebug-prefix-map=',
                           '--remap-path-prefix='):
                if not part.startswith(option):
                    continue
                mapping = separators(part[len(option):])
                if mapping == root + '=/foundation/guest/sdk':
                    argv[index] = option + '$SDK=/foundation/guest/sdk'
                elif mapping == '$WORK=/foundation/guest/work':
                    argv[index] = option + mapping
                else:
                    raise ValueError('deterministic guest-module recompile needed: unsupported prefix mapping in retained guest recipe')
        if '--sysroot' in argv:
            index = argv.index('--sysroot') + 1
            if (index >= len(argv) or 'rust_sysroot' not in sdk
                    or separators(argv[index]) != root + '/' + sdk['rust_sysroot']):
                raise ValueError('guest Rust command selects an unpinned sysroot')
            argv[index] = '$SDK/' + sdk['rust_sysroot']
        normalized.append(argv)
    return normalized


def _receipt(value, *, language, sources, bindings, sdk_pin, sdk_inventory_pin, module, audit,
             helper_pin, validator_pin, sdk):
    release._keys(value, RECEIPT_FIELDS, label='guest compile receipt')
    expected = {'schema_version': 1, 'profile': compiler.PROFILE, 'language': language,
                'sources': sources, 'bindings': bindings, 'sdk_descriptor_sha256': sdk_pin,
                'sdk_inventory_sha256': sdk_inventory_pin,
                'module': {'sha256': container.digest(module), 'bytes': len(module)}, 'audit': audit,
                'compiler_helper_sha256': helper_pin, 'validator_sha256': validator_pin}
    if any(not _same(value[key], item) for key, item in expected.items()):
        raise ValueError('guest compile receipt differs from actual recovered source, bindings, SDK or module')
    release._keys(value['host'], ('system', 'machine'), label='guest compiler host')
    if any(type(value['host'][key]) is not str or not value['host'][key] for key in ('system', 'machine')):
        raise ValueError('guest compile receipt has no actual compiler host identity')
    return _commands(value['commands'], sdk, value['host'])


@contextmanager
def _execution(context, tools, destination, sdk_root, sdk_inventory):
    """Capture the fixed compiler's real tool boundary, including complete logs."""
    observed = []
    original = compiler._run
    selected = {value for key, value in tools.items() if key != 'rust_sysroot'}
    execute = context['helpers']['execute']
    private = None

    def run(argv, cwd, environment):
        nonlocal private
        cwd = Path(cwd)
        observed_inputs = {'source': compiler._tree(cwd / 'source', source=True),
                           'bindings': compiler._tree(cwd / 'bindings')}
        if private is None:
            private = (cwd, observed_inputs)
        if (cwd != private[0] or not _same(observed_inputs, private[1])
                or not _same(compiler._tree(sdk_root), sdk_inventory)):
            raise ValueError('guest compiler SDK or private source/bindings changed before a tool call')
        if not argv or argv[0] not in selected:
            raise ValueError('guest compile attempted a tool outside the verified SDK')
        if argv[0] == tools['wasm_ld']:
            if '--no-entry' not in argv or '--export-memory' not in argv or '-c' in argv:
                raise ValueError('guest link command is not the portable module link')
        elif argv[0] == tools.get('rustc'):
            if '--target=wasm32v1-none' not in argv or '-Cpanic=abort' not in argv:
                raise ValueError('guest Rust compilation selected an unsupported target')
        elif not {'--target=wasm32-unknown-unknown', '-ffreestanding', '-nostdinc', '-c'} <= set(argv):
            raise ValueError('guest compilation selected a native or unspecified target')
        call = destination / ('command-' + str(len(observed)).zfill(3))
        call.mkdir()
        context['helpers']['new_json'](call / 'inputs-before.json', observed_inputs)
        result = execute(list(argv), cwd, call, environment, min(120, context['timeout']))
        if result.get('process_tree_joined') is not True:
            raise ProcessTreeError('guest compiler process completion uncertain; retain output ownership')
        if result.get('argv') != list(argv) or type(result.get('exit_code')) is not int:
            raise ValueError('guest compiler execution did not bind exact argv and joined processes')
        record = {key: result[key] for key in ('argv', 'exit_code', 'seconds', 'process_tree_joined')}
        record.update(stdout_sha256=container.digest(result['stdout']), stderr_sha256=container.digest(result['stderr']),
                      receipt_argv=[part.replace(str(cwd), '$WORK') for part in argv])
        context['helpers']['new_json'](call / 'execution.json', record)
        observed.append(record)
        after_inputs = {'source': compiler._tree(cwd / 'source', source=True),
                        'bindings': compiler._tree(cwd / 'bindings')}
        context['helpers']['new_json'](call / 'inputs-after.json', after_inputs)
        if not _same(after_inputs, private[1]) or not _same(compiler._tree(sdk_root), sdk_inventory):
            raise ValueError('guest compiler SDK or private source/bindings changed during a tool call')
        if len(result['stdout']) + len(result['stderr']) > 1024 * 1024:
            raise ValueError('guest compiler exceeded its output limit')
        if result['exit_code'] != 0:
            raise ValueError('guest compiler failed; inspect retained guest/compiler captures')
        return (result['stdout'] + result['stderr']).decode('utf-8', errors='replace')

    with _COMPILE_LOCK:
        compiler._run = run
        try:
            yield observed
        finally:
            compiler._run = original


def _test(context, value, snapshots):
    selected = value['test']
    matches = [entry for entry in context['subject']['composition']['artifacts']
               if entry['id'] == selected['artifact_id']]
    if len(matches) != 1:
        raise ValueError('guest tests need one exact candidate runtime artifact')
    snapshot = snapshots[selected['scenario']]
    nested = release._json(snapshot.content)
    if (type(nested) is not dict or nested.get('candidate_sha256') != value['candidate_sha256']
            or nested.get('artifact_id') != selected['artifact_id']
            or type(nested.get('target')) is not str or type(nested.get('backend')) is not str):
        raise ValueError('guest test scenario names a different candidate or runtime')
    child_evidence, child_work = context['evidence'] / 'guest/tests', context['work'] / 'guest tests'
    child_evidence.mkdir()
    child_work.mkdir()
    child = dict(context, artifact=matches[0], target=nested['target'], backend=nested['backend'],
                 evidence=child_evidence, work=child_work, scenario=snapshot.path,
                 scenario_sha256=value['inputs'][selected['scenario']], passed=[])
    if selected['adapter'] == 'retained-runtime':
        calls = nested.get('calls')
        application_call = context['helpers']['application_call']
        if type(calls) is not list or not any(type(call) is dict and
                application_call(call.get('argv'), call.get('exit_code'), child['backend']) for call in calls):
            raise ValueError('guest tests need a positive application call, not only inspection/help')
        result = context['helpers']['runtime'](child)
    else:
        if matches[0]['carrier'] != 'html':
            raise ValueError('guest browser tests need the exact HTML runtime artifact')
        import appended_browser_check
        result = appended_browser_check.run(child)
    tests, name = result.get('executed_tests'), result.get('junit')
    if (type(tests) is not list or not tests or len(set(tests)) != len(tests)
            or any(type(test) is not str or not release.NAME.fullmatch(test) for test in tests)
            or type(name) is not str):
        raise ValueError('guest tests did not return a nonempty actual JUnit execution inventory')
    path = child_evidence / container.resource_path(name)
    saved = container._snapshot(path, MAX_JSON)
    root = ET.fromstring(saved.content)
    cases = root.findall('.//testcase')
    if (sorted(case.get('name') for case in cases) != sorted(tests)
            or any(case.get('status', 'run') not in ('run', 'passed') for case in cases)
            or any(case.find(tag) is not None for case in cases for tag in ('failure', 'error', 'skipped'))):
        raise ValueError('guest runtime test outcomes are failed, skipped or incomplete')
    _save(context['evidence'] / 'guest.junit.xml', saved.content)
    return result, tests


def run(context):
    """Execute the fixed guest-source adapter inside its caller-owned workspace."""
    if (context['artifact'] is not None or (context['target'], context['backend']) != ('portable-wasm32', 'guest')):
        raise ValueError('guest source recovery is one candidate-wide portable-module operation')
    saved, value, snapshots = _scenario(context)
    evidence = context['evidence'] / 'guest'
    evidence.mkdir()
    new_json = context['helpers']['new_json']
    _save(evidence / 'scenario.json', saved.content)
    new_json(evidence / 'inputs.json', value['inputs'])
    source_ref = context['subject']['composition']['source']
    restored, source_identity = release._source(context['directory'] / source_ref['path'], source_ref,
                                               context['work'], 'restored guest source')
    selected_project = project.load_project(restored)
    if not selected_project.binary.enabled:
        raise ValueError('guest source recovery requires the configured binary source component')
    source = restored / container.resource_path(selected_project.binary.source)
    sources = compiler._tree(source, source=True)
    bindings = _bindings(restored, value['language'])
    original_helper = compiler._digest(restored / 'tools/appended_compile.py')
    original_validator = compiler._digest(restored / 'tools/appended_wasm.py')
    new_json(evidence / 'source.json', {'source': source_identity, 'source_root': selected_project.binary.source,
                                      'sources': sources, 'bindings': bindings})
    context['passed'].append('guest-source')
    bundle = context['work'] / 'retained guest SDK'
    _sdk_bundle(snapshots[value['sdk']['archive']].path, bundle)
    descriptor_path = bundle / value['sdk']['descriptor']
    descriptor = container._snapshot(descriptor_path, MAX_JSON)
    if container.digest(descriptor.content) != value['sdk']['descriptor_sha256']:
        raise ValueError('bundled guest SDK descriptor differs from independent pin')
    sdk_document = release._json(descriptor.content)
    root_name = sdk_document.get('root') if type(sdk_document) is dict else None
    if (type(sdk_document) is not dict or type(sdk_document.get('schema_version')) is not int
            or sdk_document['schema_version'] != 1 or sdk_document.get('profile') != compiler.PROFILE):
        raise ValueError('bundled guest SDK needs its strict versioned profile descriptor')
    if type(root_name) is not str or Path(root_name).is_absolute() or ntpath.isabs(root_name):
        raise ValueError('bundled guest SDK root must be relative and contained in its restored bundle')
    container.resource_path(root_name)
    sdk_root, sdk, tools, sdk_pin = compiler.load_sdk(descriptor_path, value['language'])
    if not sdk_root.is_relative_to(bundle) or sdk_root == bundle:
        raise ValueError('guest SDK tools escape the retained bundle')
    sdk_inventory_pin = hashlib.sha256(compiler._canonical(sdk['inventory'])).hexdigest()
    _save(evidence / 'sdk.json', descriptor.content)
    new_json(evidence / 'sdk-inventory.json', sdk['inventory'])
    context['passed'].append('guest-sdk')
    payload_ref = context['subject']['selection']['payload']
    if payload_ref is None:
        raise ValueError('guest source recovery requires a delivered binary module')
    payload = container.parse_artifact((context['directory'] / payload_ref['path']).read_bytes()).package
    if payload is None or not payload.index['components']['binary']['present']:
        raise ValueError('guest source recovery requires a delivered binary module')
    delivered = payload.file_bytes('binary/application.wasm')
    audit = appended_wasm.validate_module(delivered)
    if audit['memory'] != {'minimum_pages': value['memory_pages'], 'maximum_pages': value['max_memory_pages']}:
        raise ValueError('guest scenario memory limits differ from the delivered module')
    original = release._json(snapshots[value['compile_receipt']].content)
    original_commands = _receipt(original, language=value['language'], sources=sources, bindings=bindings,
        sdk_pin=sdk_pin, sdk_inventory_pin=sdk_inventory_pin, module=delivered, audit=audit,
        helper_pin=original_helper, validator_pin=original_validator, sdk=sdk)
    _save(evidence / 'original-compile.json', snapshots[value['compile_receipt']].content)
    for snapshot in (saved, descriptor, *snapshots.values()):
        container._recheck(snapshot)
    compiler_logs = evidence / 'compiler'
    compiler_logs.mkdir()
    module_path, receipt_path = evidence / 'module.wasm', evidence / 'compile.json'
    current_helper = compiler._digest(Path(compiler.__file__).resolve())
    current_validator = compiler._digest(Path(appended_wasm.__file__).resolve())
    with _execution(context, tools, compiler_logs, sdk_root, sdk['inventory']) as commands:
        fresh = compiler.compile_guest(source, value['language'], descriptor_path, module_path, receipt_path,
                                        value['entries'], value['memory_pages'], value['max_memory_pages'],
                                        bindings_root=restored)
    rebuilt = container._snapshot(module_path, appended_wasm.MAX_MODULE_BYTES)
    fresh_saved = container._snapshot(receipt_path, MAX_JSON)
    fresh_receipt = release._json(fresh_saved.content)
    fresh_audit = appended_wasm.validate_module(rebuilt.content)
    if rebuilt.content != delivered:
        raise ValueError('deterministic guest-module recompile needed: recovery did not reproduce the exact delivered module')
    if not _same(fresh, fresh_receipt):
        raise ValueError('guest recovery returned an inconsistent fresh compile receipt')
    fresh_commands = _receipt(fresh_receipt, language=value['language'], sources=sources, bindings=bindings,
        sdk_pin=sdk_pin, sdk_inventory_pin=sdk_inventory_pin, module=rebuilt.content, audit=fresh_audit,
        helper_pin=current_helper, validator_pin=current_validator, sdk=sdk)
    observed_commands = _commands([record['receipt_argv'] for record in commands], sdk, fresh_receipt['host'])
    if not _same(original_commands, fresh_commands) or not _same(observed_commands, fresh_commands):
        raise ValueError('deterministic guest-module recompile needed: recovery commands differ from the exact retained guest build recipe')
    new_json(evidence / 'audit.json', fresh_audit)
    context['passed'].append('guest-compile')
    runtime, tests = _test(context, value, snapshots)
    context['passed'].append('guest-tests')
    for snapshot in (saved, descriptor, rebuilt, fresh_saved, *snapshots.values()):
        container._recheck(snapshot)
    if (compiler._tree(source, source=True) != sources or _bindings(restored, value['language']) != bindings
            or compiler._tree(sdk_root) != sdk['inventory']):
        raise ValueError('guest recovery inputs changed during compilation or test execution')
    context['passed'].append('no-kernel-build')
    return {'scenario_sha256': context['scenario_sha256'], 'reproduction': 'byte-exact',
            'source_tree_sha256': source_identity['tree_sha256'], 'language': value['language'],
            'entries': value['entries'], 'sdk_archive_sha256': value['inputs'][value['sdk']['archive']],
            'sdk_descriptor_sha256': sdk_pin, 'sdk_inventory_sha256': sdk_inventory_pin,
            'delivered_module_sha256': container.digest(delivered), 'rebuilt_module_sha256': container.digest(rebuilt.content),
            'compiler_commands': commands, 'executed_tests': tests, 'tool_reports': [],
            'guest_runtime': runtime, 'kernel_build_invocations': 0}
