#!/usr/bin/env python3
"""Private archive install, pinned-predecessor upgrade and owned-file removal.

Only delivered runtimes execute through the native or installed-browser adapter.
No package manager, installer script, source build or kernel reconstruction
participates in this archive-channel check.
"""
import errno
import math
from pathlib import Path
import tarfile

import appended_container as container
import appended_release as release
import dependency_archive as archive
from process_tree import ProcessTreeError

MAX_SCENARIO = 4 * 1024 * 1024
MAX_INPUT = 512 * 1024 * 1024
PHASES = ('clean', 'previous', 'upgraded')


def _same(left, right):
    return container.canonical_json(left) == container.canonical_json(right)


def _save(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as output:
        output.write(content)


def _scenario(path, pin, subject, entry, target, backend):
    saved = container._snapshot(path, MAX_SCENARIO)
    if container.digest(saved.content) != release._sha(pin):
        raise ValueError('install scenario differs from independently pinned SHA-256')
    value = release._json(saved.content)
    release._keys(value, ('schema_version', 'kind', 'candidate_sha256', 'artifact_id', 'target',
                         'backend', 'channels', 'inputs', 'predecessor', 'phases', 'state'), label='install scenario')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'foundation-appended-install-scenario'
            or value['candidate_sha256'] != subject['candidate_sha256']
            or (value['artifact_id'], value['target'], value['backend']) != (entry['id'], target, backend)
            or value['channels'] != ['archive']):
        raise ValueError('install scenario must name this exact archive artifact and execution target')
    inputs = value['inputs']
    if type(inputs) is not dict or not 1 <= len(inputs) <= 128:
        raise ValueError('install scenario requires a bounded complete input inventory')
    snapshots, registry = {}, archive.PathInventory()
    for name, digest in inputs.items():
        name = container.resource_path(name)
        registry.add(name, False)
        release._sha(digest)
        snapshot = container._snapshot(archive.checked_file(saved.path.parent, name), MAX_INPUT)
        if container.digest(snapshot.content) != digest:
            raise ValueError('install scenario input differs from its independent pin: ' + name)
        snapshots[name] = snapshot
    release._keys(value['predecessor'], ('archive', 'candidate_sha256', 'artifact_id'), label='install predecessor')
    previous = value['predecessor']
    container.resource_path(previous['archive'])
    if previous['archive'] not in inputs:
        raise ValueError('predecessor candidate archive must belong to the pinned input inventory')
    release._sha(previous['candidate_sha256'])
    release._name(previous['artifact_id'])
    if previous['candidate_sha256'] == subject['candidate_sha256']:
        raise ValueError('reinstalling the same candidate cannot qualify an upgrade')
    release._keys(value['phases'], PHASES, label='install phases')
    for phase in PHASES:
        if entry['carrier'] == 'html':
            release._keys(value['phases'][phase], ('scenario',), label='installed browser phase')
            reference = container.resource_path(value['phases'][phase]['scenario'])
            if reference not in inputs:
                raise ValueError('each installed browser scenario must belong to the pinned input inventory')
            continue
        phase_ids = set()
        calls = value['phases'][phase]
        if type(calls) is not list or not 1 <= len(calls) <= 64:
            raise ValueError('each install phase requires nonempty bounded actual runtime calls')
        for call in calls:
            release._keys(call, ('id', 'argv', 'exit_code', 'stdout', 'stderr'), label='install call')
            release._name(call['id'])
            if (call['id'] in phase_ids or type(call['argv']) is not list or len(call['argv']) > 128
                    or any(type(arg) is not str or '\0' in arg or len(arg) > 4096 for arg in call['argv'])
                    or type(call['exit_code']) is not int or not -255 <= call['exit_code'] <= 255
                    or any(type(call[key]) is not str or len(call[key].encode()) > MAX_SCENARIO
                           for key in ('stdout', 'stderr'))):
                raise ValueError('invalid, duplicate or excessive install runtime call')
            phase_ids.add(call['id'])
    release._keys(value['state'], ('before', 'after'), label='install application state')
    stateless = value['state']['before'] == {} and value['state']['after'] == {}
    for phase, inventory in value['state'].items():
        if (type(inventory) is not dict or len(inventory) > 4096
                or not inventory and not stateless):
            raise ValueError('state maps must both be empty or both be bounded nonempty exact inventories')
        registry = archive.PathInventory()
        for name, digest in inventory.items():
            container.resource_path(name)
            registry.add(name, False)
            release._sha(digest)
    if entry['carrier'] == 'html' and not stateless:
        raise ValueError('persistent browser state is unsupported by the initial archive install adapter')
    return saved, snapshots, value


def _state(state_root, expected, helpers):
    container._ordinary_path(state_root, directory=True)
    observed = helpers['tree'](state_root)
    if ({name: identity['sha256'] for name, identity in observed['files'].items()} != expected
            or not expected and observed['directories']):
        raise ValueError('application state does not match the exact pinned scenario inventory')
    return observed


def _check_inputs(saved_scenario, snapshots):
    container._recheck(saved_scenario)
    for saved in snapshots.values():
        container._recheck(saved)


def _browser_scenarios(saved, snapshots, scenario, current, entry, previous, old, target, backend, evidence):
    """Preflight all nested bindings and retain their complete pinned inputs."""
    from appended_browser_check import _scenario as browser_scenario
    registry = archive.PathInventory()
    for name in snapshots:
        registry.add(name, False)
    for phase in PHASES:
        reference = scenario['phases'][phase]['scenario']
        nested = snapshots[reference]
        subject, product = (previous, old) if phase == 'previous' else (current, entry)
        _, _, inputs = browser_scenario(nested.path, scenario['inputs'][reference], subject, product, target, backend)
        for item in inputs:
            try:
                name = item.path.relative_to(saved.path.parent).as_posix()
            except ValueError as error:
                raise ValueError('nested browser inputs must remain under the install scenario parent') from error
            if name in snapshots:
                if snapshots[name].content != item.content:
                    raise ValueError('conflicting independently pinned nested browser input')
                continue
            registry.add(name, False)
            snapshots[name] = item
            _save(evidence / 'inputs' / name, item.content)


def _browser_phase(name, directory, subject, entry, prefix, state_root, evidence, work,
                   outer_context, scenario, snapshots, helpers, inputs_unchanged):
    """Run the fixed browser verifier against the actual managed install tree."""
    from appended_browser_check import _validate_offline
    if 'browser' not in helpers or not callable(helpers['browser']):
        raise ValueError('HTML installation requires the trusted installed browser adapter')
    roots = {}
    for path in (prefix, state_root):
        state = container._ordinary_path(path, directory=True).lstat()
        roots[path] = (state.st_dev, state.st_ino)
    before = helpers['tree'](prefix)
    _state(state_root, {}, helpers)
    inputs_unchanged()
    phase_evidence = evidence / name; phase_evidence.mkdir()
    phase_work = work / ('browser ' + name + ' phase with spaces'); phase_work.mkdir()
    helpers['new_json'](phase_evidence / 'before.json', before)
    reference = scenario['phases'][name]['scenario']
    nested = snapshots[reference]
    nested_pin = container.digest(nested.content)
    child = dict(outer_context)
    child.update(directory=directory, subject=subject, artifact=entry, evidence=phase_evidence, work=phase_work,
                 scenario=nested.path, scenario_sha256=nested_pin, passed=[],
                 installed_prefix=prefix, installed_inventory=before)
    result = helpers['browser'](child)
    if (type(result) is not dict or type(result.get('browser')) is not dict
            or result['browser'].get('process_tree_joined') is not True):
        raise ProcessTreeError('installed browser completion uncertain; retain output ownership')
    for path, expected_identity in roots.items():
        state = container._ordinary_path(path, directory=True).lstat()
        if (state.st_dev, state.st_ino) != expected_identity:
            raise ValueError('installed browser replaced the managed prefix or designated state root')
    browser = result['browser']
    if (child['passed'] != ['actual-browser', 'application-scenario', 'retained-runtime']
            or result.get('scenario_sha256') != nested_pin or not result.get('executed_tests')
            or browser.get('direct_file_uri') != (prefix / entry['runtime_member']).resolve().as_uri()
            or browser.get('runtime_sha256') != entry['runtime_sha256']
            or browser.get('application_result_changed') is not True
            or _validate_offline(browser.get('engine'), browser.get('offline')) is not True
            or not _same(browser.get('quit'), {'acknowledged': True, 'normal_exit': True})):
        raise ValueError('installed browser did not complete its actual bound application scenario')
    after = helpers['tree'](prefix)
    helpers['new_json'](phase_evidence / 'after.json', after)
    if not _same(after, before):
        raise ValueError('installed browser changed the managed application or preserved foreign inventory')
    _state(state_root, {}, helpers)
    inputs_unchanged()
    junit = container.resource_path(result.get('junit'))
    archive.checked_file(phase_evidence, junit)
    return dict(result, junit='install/' + name + '/' + junit)


def _phase(name, calls, entry, prefix, state_root, environment, evidence, timeout, helpers, inputs_unchanged):
    phase_root = evidence / name; phase_root.mkdir()
    calls_root = phase_root / 'calls'; calls_root.mkdir()
    owned_roots = {}
    for path in (prefix, state_root):
        state = container._ordinary_path(path, directory=True).lstat()
        owned_roots[path] = (state.st_dev, state.st_ino)
    def ordinary_roots():
        for path, expected_identity in owned_roots.items():
            state = container._ordinary_path(path, directory=True).lstat()
            if (state.st_dev, state.st_ino) != expected_identity:
                raise ValueError('private installed prefix or application state root was replaced')
    expected = helpers['tree'](prefix)
    runtime = prefix / entry['runtime_member']
    if archive.digest(runtime) != entry['runtime_sha256'] or not runtime.stat().st_mode & 0o111:
        raise ValueError('installed selected runtime bytes or executable mode differ')
    helpers['new_json'](phase_root / 'before.json', expected)
    results, completed = [], []
    failed, uncertain = None, False
    try:
        for call in calls:
            inputs_unchanged()
            ordinary_roots()
            call_root = calls_root / call['id']; call_root.mkdir()
            before = helpers['tree'](prefix)
            if not _same(before, expected):
                raise ValueError('installed inventory changed before install scenario call')
            helpers['new_json'](call_root / 'before.json', before)
            argv = [str(runtime), *(argument.replace('{state}', str(state_root)).replace('{prefix}', str(prefix))
                                   for argument in call['argv'])]
            observed = helpers['execute'](argv, state_root, call_root, environment, timeout)
            if type(observed) is not dict or observed.get('process_tree_joined') is not True:
                raise ProcessTreeError('install runtime completion uncertain; retain output ownership')
            ordinary_roots()
            after = helpers['tree'](prefix)
            helpers['new_json'](call_root / 'after.json', after)
            if (observed.get('argv') != argv
                    or type(observed.get('exit_code')) is not int
                    or type(observed.get('seconds')) not in (int, float)
                    or not math.isfinite(observed['seconds']) or observed['seconds'] < 0
                    or type(observed.get('stdout')) is not bytes or type(observed.get('stderr')) is not bytes):
                raise ValueError('install scenario requires exact runtime observations and joined process trees')
            for key in ('stdout', 'stderr'):
                if container._snapshot(call_root / (key + '.bin'), MAX_SCENARIO).content != observed[key]:
                    raise ValueError('install runtime observation differs from its retained raw capture')
            native = release._json(container._snapshot(call_root / 'native.json', MAX_SCENARIO).content)
            if not _same(native, {'argv': argv, 'exit_code': observed['exit_code']}):
                raise ValueError('install runtime native capture differs from the executed runtime')
            record = {key: observed[key] for key in ('argv', 'exit_code', 'seconds', 'process_tree_joined')}
            record.update(id=call['id'], stdout_sha256=container.digest(observed['stdout']),
                          stderr_sha256=container.digest(observed['stderr']))
            helpers['new_json'](call_root / 'observation.json', record)
            results.append(record)
            if not _same(after, expected):
                raise ValueError('installed inventory changed during install scenario call')
            inputs_unchanged()
            if (observed['exit_code'] != call['exit_code'] or observed['stdout'] != call['stdout'].encode()
                    or observed['stderr'] != call['stderr'].encode()):
                raise ValueError('install runtime output or exit mismatch for call ' + call['id'])
            completed.append(call['id'])
    except BaseException as error:
        failed = (call['id'], str(error))
        uncertain = helpers['uncertain'](error)
        raise
    finally:
        if not uncertain:
            skipped = [call['id'] for call in calls if call['id'] not in completed
                       and (failed is None or call['id'] != failed[0])]
            helpers['junit'](phase_root / 'calls.junit.xml', [call['id'] for call in calls], failed=failed, skipped=skipped)
    final = helpers['tree'](prefix)
    if not _same(final, expected):
        raise ValueError('installed archive changed after completed install scenario phase')
    helpers['new_json'](phase_root / 'after.json', final)
    return results


def _remove(prefix, owned, helpers, *, foreign=None, foreign_directories=None):
    """Remove verified owned members individually; never recursively delete data."""
    container._ordinary_path(prefix, directory=True)
    before = helpers['tree'](prefix)
    expected_files = dict(owned['files'])
    expected_directories = dict(owned['directories'])
    expected_directories.update(foreign_directories or {})
    if foreign is not None:
        name, identity = foreign
        expected_files[name] = identity
    if not _same(before, {'files': expected_files, 'directories': expected_directories}):
        raise ValueError('managed archive changed before owned-file removal')
    for name, expected in sorted(owned['files'].items()):
        path = archive.checked_file(prefix, name)
        saved = container._snapshot(path, MAX_INPUT)
        if (container.digest(saved.content) != expected['sha256'] or len(saved.content) != expected['size']
                or saved.mode != expected['mode']):
            raise ValueError('owned installed file changed before removal')
        container._recheck(saved)
        path.unlink()
    for name in sorted(owned['directories'], key=lambda item: (len(Path(item).parts), item), reverse=True):
        path = container._ordinary_path(prefix / name, directory=True)
        try:
            path.rmdir()
        except OSError as error:
            if error.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                raise
    after = helpers['tree'](prefix)
    remaining = {} if foreign is None else {foreign[0]: foreign[1]}
    if not _same(after['files'], remaining):
        raise ValueError('owned removal changed foreign data or retained owned files')
    if foreign is None and after['directories']:
        raise ValueError('owned directory inventory remains after removal')
    if foreign is not None:
        expected_directories = {parent.as_posix(): expected_directories[parent.as_posix()]
                                for parent in Path(foreign[0]).parents if parent != Path('.')}
        if not _same(after['directories'], expected_directories):
            raise ValueError('owned removal changed foreign directory ownership or modes')
    return before, after


def _foreign_record(prefix, name, helpers):
    saved = container._snapshot(prefix / name, MAX_INPUT)
    tree = helpers['tree'](prefix)
    return {'path': name, 'sha256': container.digest(saved.content), 'size': len(saved.content),
            'mode': saved.mode, 'device': saved.identity[0], 'inode': saved.identity[1],
            'directories': {parent.as_posix(): tree['directories'][parent.as_posix()]
                            for parent in Path(name).parents if parent != Path('.')}}


def _foreign(prefix, owned, entry, helpers):
    """Create data owned by the qualification fixture, outside archive ownership."""
    parent = Path(entry['runtime_member']).parent
    added = {}
    if parent == Path('.'):
        if owned['directories']:
            parent = Path(min(owned['directories'], key=lambda name: (len(Path(name).parts), name)))
        else:
            parent = Path('foreign application data')
            index = 0
            while (prefix / parent).exists():
                index += 1
                parent = Path('foreign application data ' + str(index))
            (prefix / parent).mkdir(mode=0o700)
            added[parent.as_posix()] = (prefix / parent).stat().st_mode & 0o777
    name = (parent / 'foreign uninstall sentinel').as_posix()
    index = 0
    while (prefix / name).exists():
        index += 1
        name = (parent / ('foreign uninstall sentinel ' + str(index))).as_posix()
    sentinel = prefix / name
    _save(sentinel, b'foreign application-adjacent data must survive upgrade and owned removal\n')
    sentinel.chmod(0o600)
    return _foreign_record(prefix, name, helpers), added


def _migrate_foreign(prefix, staged, old_owned, current_owned, before, old_extra, helpers):
    """Move foreign data only after the complete new ownership collision check."""
    name = before['path']
    identity = {key: before[key] for key in ('size', 'sha256', 'mode')}
    expected_old = {'files': dict(old_owned['files'], **{name: identity}),
                    'directories': dict(old_owned['directories'], **old_extra)}
    if (not _same(helpers['tree'](prefix), expected_old)
            or not _same(helpers['tree'](staged), current_owned)
            or not _same(_foreign_record(prefix, name, helpers), before)):
        raise ValueError('predecessor foreign data or staged application changed before upgrade')
    if name in current_owned['files'] or name in current_owned['directories']:
        raise ValueError('incompatible archive upgrade: current owned member collides with foreign data')
    extra = {}
    for parent, mode in before['directories'].items():
        if parent in current_owned['files']:
            raise ValueError('incompatible archive upgrade: current owned file collides with foreign parent')
        if parent in current_owned['directories']:
            if current_owned['directories'][parent] != mode:
                raise ValueError('incompatible archive upgrade: foreign parent directory mode changed')
        else:
            extra[parent] = mode
    # No source pathname has changed before every collision is known. All
    # processes are joined; both trees are private and contain verified bytes.
    for parent in sorted(extra, key=lambda value: (len(Path(value).parts), value)):
        (staged / parent).mkdir()
    (prefix / name).rename(staged / name)
    for parent in sorted(extra, key=lambda value: (len(Path(value).parts), value), reverse=True):
        (staged / parent).chmod(extra[parent])
    for parent in sorted(old_extra, key=lambda value: (len(Path(value).parts), value), reverse=True):
        container._ordinary_path(prefix / parent, directory=True).rmdir()
    expected_current = {'files': dict(current_owned['files'], **{name: identity}),
                        'directories': dict(current_owned['directories'], **extra)}
    if (not _same(helpers['tree'](prefix), old_owned)
            or not _same(helpers['tree'](staged), expected_current)
            or not _same(_foreign_record(staged, name, helpers), before)):
        raise ValueError('archive upgrade failed to preserve exact foreign file identity and parent modes')
    return expected_current, extra


def run(context):
    directory, subject, entry = Path(context['directory']), context['subject'], context['artifact']
    helpers = context['helpers']
    target, backend = context['target'], context['backend']
    if (type(context['timeout']) not in (int, float) or not math.isfinite(context['timeout'])
            or not 0 < context['timeout'] <= 300):
        raise ValueError('install runtime timeout must be positive and at most 300 seconds')
    html = entry['carrier'] == 'html'
    if html:
        if (entry['profile'] != 'binary' or subject['composition']['payload']['mode'] != 'binary'
                or (target, backend) != ('web-wasm32', 'web')):
            raise ValueError('HTML installation requires the exact binary GUI web-wasm32/web product')
    elif entry['carrier'] != 'elf' or backend not in ('core', 'terminal'):
        raise ValueError('archive install adapter requires native ELF core/terminal or a stateless binary HTML product')
    if not _same(release.verify_composition_subject(directory, subject['candidate_sha256']), subject):
        raise ValueError('install adapter received a different frozen composition subject')
    matches = [item for item in subject['composition']['artifacts'] if item['id'] == entry['id']]
    if len(matches) != 1 or not _same(matches[0], entry):
        raise ValueError('install adapter artifact differs from the exact frozen product')
    saved, snapshots, scenario = _scenario(context['scenario'], context['scenario_sha256'], subject,
                                           entry, target, backend)
    stateless = not scenario['state']['before'] and not scenario['state']['after']
    current_members = release._members(directory / entry['archive'])[1]
    if not html:
        helpers['host_target'](entry, current_members[entry['runtime_member']][0], target, backend)
    work = container._ordinary_path(context['work'], directory=True) / 'install'; work.mkdir()
    evidence = container._ordinary_path(context['evidence'], directory=True) / 'install'; evidence.mkdir()
    _save(evidence / 'scenario.json', saved.content)
    for name, snapshot in snapshots.items():
        _save(evidence / 'inputs' / name, snapshot.content)
    previous_ref = scenario['predecessor']
    previous_archive = snapshots[previous_ref['archive']].path
    try:
        previous_directory = archive.extract(previous_archive, work / 'previous candidate', max_bytes=MAX_INPUT)
    except tarfile.TarError as error:
        raise ValueError('predecessor input is not a safe complete candidate archive') from error
    previous = release.verify_composition_subject(previous_directory, previous_ref['candidate_sha256'])
    previous_entries = [item for item in previous['composition']['artifacts'] if item['id'] == previous_ref['artifact_id']]
    if len(previous_entries) != 1:
        raise ValueError('predecessor must select one exact frozen artifact')
    old = previous_entries[0]
    if (previous['composition']['application']['id'] != subject['composition']['application']['id']
            or previous['composition']['application']['version'] == subject['composition']['application']['version']
            or old['carrier'] != entry['carrier']
            or old['runtime_sha256'] == entry['runtime_sha256']
            and previous['composition']['payload']['payload_id'] == subject['composition']['payload']['payload_id']):
        raise ValueError('upgrade requires a distinct prior application release and runtime or payload')
    old_members = release._members(previous_directory / old['archive'])[1]
    if html:
        if old['profile'] != 'binary' or previous['composition']['payload']['mode'] != 'binary':
            raise ValueError('HTML predecessor must retain its binary-defined browser application')
        _browser_scenarios(saved, snapshots, scenario, subject, entry, previous, old, target, backend, evidence)
    else:
        helpers['host_target'](old, old_members[old['runtime_member']][0], target, backend)
    unchanged = lambda: _check_inputs(saved, snapshots)
    unchanged()
    phases = {}
    def execute_phase(name, selected_directory, selected_subject, selected_entry, prefix, state_root, environment):
        if html:
            return _browser_phase(name, selected_directory, selected_subject, selected_entry, prefix, state_root,
                                  evidence, work, context, scenario, snapshots, helpers, unchanged)
        return _phase(name, scenario['phases'][name], selected_entry, prefix, state_root,
                      environment, evidence, context['timeout'], helpers, unchanged)
    for phase in ('clean', 'upgrade'):
        root = work / phase; root.mkdir()
        environment_root = root / 'environment'; environment_root.mkdir()
        environment = helpers['environment'](environment_root)
        state_root = Path(environment['HOME']) / 'application state'; state_root.mkdir()
        prefix = root / 'application prefix with spaces'
        if phase == 'clean':
            clean_owned = helpers['extract'](directory, entry, prefix)
            phases['clean'] = execute_phase('clean', directory, subject, entry, prefix, state_root, environment)
            if stateless:
                helpers['new_json'](evidence / 'clean-state.json', _state(state_root, {}, helpers))
            helpers['new_json'](evidence / 'clean-installed.json', clean_owned)
            context['passed'].append('clean-install')
            continue
        old_owned = helpers['extract'](previous_directory, old, prefix)
        helpers['new_json'](evidence / 'previous-installed.json', old_owned)
        phases['previous'] = execute_phase('previous', previous_directory, previous, old, prefix, state_root, environment)
        state_before = _state(state_root, scenario['state']['before'], helpers)
        helpers['new_json'](evidence / 'state-before-upgrade.json', state_before)
        foreign_before, previous_foreign_directories = _foreign(prefix, old_owned, old, helpers)
        helpers['new_json'](evidence / 'foreign-before-upgrade.json', foreign_before)
        staged = root / 'staged current application'
        current_owned = helpers['extract'](directory, entry, staged)
        unchanged()
        expected_upgraded, foreign_directories = _migrate_foreign(prefix, staged, old_owned, current_owned,
            foreign_before, previous_foreign_directories, helpers)
        backup = root / 'previous owned application'
        prefix.rename(backup)
        staged.rename(prefix)
        upgraded = helpers['tree'](prefix)
        if not _same(upgraded, expected_upgraded) or not _same(_state(state_root, scenario['state']['before'], helpers), state_before):
            raise ValueError('archive replacement changed application state or delivered inventory')
        helpers['new_json'](evidence / 'upgraded-installed.json', upgraded)
        foreign_name = foreign_before['path']
        foreign_after = _foreign_record(prefix, foreign_name, helpers)
        if not _same(foreign_after, foreign_before):
            raise ValueError('archive replacement changed exact foreign file identity or parent modes')
        helpers['new_json'](evidence / 'foreign-after-upgrade.json', foreign_after)
        foreign_snapshot = container._snapshot(prefix / foreign_name, MAX_INPUT)
        foreign_identity = {key: foreign_after[key] for key in ('size', 'sha256', 'mode')}
        _remove(backup, old_owned, helpers)
        backup.rmdir()
        phases['upgraded'] = execute_phase('upgraded', directory, subject, entry, prefix, state_root, environment)
        # Byte inventories alone cannot identify a same-content replacement.
        # Establish foreign ownership preservation before claiming the upgrade
        # or deleting any newly installed owned member.
        container._recheck(foreign_snapshot)
        if not _same(_foreign_record(prefix, foreign_name, helpers), foreign_before):
            raise ValueError('upgraded runtime changed preserved foreign ownership or parent modes')
        state_after = _state(state_root, scenario['state']['after'], helpers)
        helpers['new_json'](evidence / 'state-after-upgrade.json', state_after)
        context['passed'].append('upgrade')
        before_remove, after_remove = _remove(prefix, current_owned, helpers,
                                              foreign=(foreign_name, foreign_identity),
                                              foreign_directories=foreign_directories)
        helpers['new_json'](evidence / 'before-remove.json', before_remove)
        helpers['new_json'](evidence / 'after-remove.json', after_remove)
        context['passed'].append('remove')
        container._recheck(foreign_snapshot)
        if not _same(_state(state_root, scenario['state']['after'], helpers), state_after):
            raise ValueError('owned archive removal changed preserved application state')
        helpers['new_json'](evidence / 'state-after-remove.json', helpers['tree'](state_root))
        context['passed'].append('preserved-application-state')
    unchanged()
    if (not _same(release.verify_composition_subject(directory, subject['candidate_sha256']), subject)
            or not _same(release.verify_composition_subject(previous_directory, previous_ref['candidate_sha256']), previous)):
        raise ValueError('current or predecessor candidate changed during archive installation checks')
    current_identity = {'candidate_sha256': subject['candidate_sha256'], 'artifact_id': entry['id'],
                        'archive_sha256': entry['sha256'], 'runtime_sha256': entry['runtime_sha256'],
                        'version': subject['composition']['application']['version']}
    predecessor_identity = {'candidate_sha256': previous_ref['candidate_sha256'], 'artifact_id': old['id'],
                            'archive_sha256': old['sha256'], 'runtime_sha256': old['runtime_sha256'],
                            'version': previous['composition']['application']['version'],
                            'input_archive_sha256': scenario['inputs'][previous_ref['archive']]}
    return {'channels': ['archive'], 'scenario_sha256': context['scenario_sha256'],
            'state_claim': 'stateless' if stateless else 'persistent',
            'installation': {'current': current_identity, 'predecessor': predecessor_identity,
                             'phases': phases, 'state_before': state_before, 'state_after': state_after,
                             'state_migration': not stateless and not _same(scenario['state']['before'], scenario['state']['after']),
                             'preserved_after_remove': True, 'foreign_sentinel_preserved': foreign_name,
                             'host_installation': False, 'native_reconstruction': False,
                             'working_prefix_contains_spaces': True}}
