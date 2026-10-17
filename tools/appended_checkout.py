#!/usr/bin/env python3
"""Pack current checkout payloads against pinned local kernels; never build them.

This separate request/staging schema feeds unchanged appended_release candidates.
It performs filesystem/JSON/archive/Wasm validation only, with no Git, compiler,
SDK discovery, engine, network, publication or qualification operation.
"""
import argparse
import copy
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile

import appended_container as container
from appended_ci import select_kernel
import appended_release as release
import appended_wasm as wasm
from appended_project import load_project
import dependency_archive as archive
import source_identity

POLICY = 'foundation-appended-checkout-filesystem-v1'
MAX_FILES = 131072
MAX_ENTRIES = MAX_FILES * 2
MAX_BYTES = release.MAX_INPUT
_RECEIPT_FIELDS = ('schema_version', 'profile', 'language', 'sources', 'bindings',
                   'sdk_descriptor_sha256', 'sdk_inventory_sha256', 'compiler_helper_sha256',
                   'validator_sha256', 'host', 'commands', 'module', 'audit')


def _inside(path, root):
    return path == root or root in path.parents


def _pruned(name):
    parts = Path(name).parts
    return (parts[0] in ('build', '.agent-work', '.git') or '__pycache__' in parts
            or source_identity.private_environment_path(name))


def _scan(root, *, source):
    """Reject special entries before a pure source selector can omit them."""
    registry, files, directories = archive.PathInventory(), {}, {'': container._identity(root.lstat())}
    count = 0
    for directory, children, names in os.walk(root, topdown=True, followlinks=False,
                                               onerror=container._walk_error):
        parent = Path(directory).relative_to(root)
        children[:] = [name for name in children
                       if not (source and _pruned((parent / name).as_posix()))]
        for name in sorted(children + names):
            relative = (parent / name).as_posix()
            if source and Path(relative).parts[0].casefold() == '.git' and Path(relative).parts[0] != '.git':
                raise ValueError('source contains a case-insensitive Git metadata alias')
            if not source and ('.git' in (part.casefold() for part in Path(relative).parts)
                               or source_identity.private_environment_path(relative)):
                raise ValueError('retained group contains private checkout/environment entry: ' + relative)
            if source and source_identity.ignored_source_path(relative):
                # File-only exclusions must not prune a same-named directory.
                if name not in children:
                    continue
            path = root / relative
            state = path.lstat()
            if not (stat.S_ISREG(state.st_mode) or stat.S_ISDIR(state.st_mode)):
                raise ValueError('checkout/group contains linked or special input: ' + relative)
            registry.add(relative, stat.S_ISDIR(state.st_mode))
            count += 1
            if count > MAX_ENTRIES:
                raise ValueError('checkout/group entry inventory exceeds limit')
            if stat.S_ISDIR(state.st_mode):
                directories[relative] = container._identity(state)
            else:
                files[relative] = container._identity(state)
    if len(files) > MAX_FILES or sum(row[2] for row in files.values()) > MAX_BYTES:
        raise ValueError('checkout/group source inventory exceeds limit')
    if source and set(files) != set(source_identity.source_files_without_git(root)):
        raise ValueError('pure filesystem source selection changed during inventory')
    return files, directories


def _capture(root, destination, *, source):
    before = _scan(root, source=source)
    destination.mkdir()
    saved, total = {}, 0
    for name in sorted(before[1]):
        if name:
            (destination / name).mkdir(parents=True, exist_ok=True)
    for name in sorted(before[0]):
        snapshot = container._snapshot(root / name, MAX_BYTES - total)
        if snapshot.identity != before[0][name]:
            raise ValueError('input changed during checkout/group capture: ' + name)
        total += len(snapshot.content)
        release._save(destination / name, snapshot.content)
        (destination / name).chmod(snapshot.mode)
        saved[name] = snapshot
    for name in sorted(before[1], reverse=True):
        (destination / name).chmod(0o755 if source else stat.S_IMODE(before[1][name][-1]))
    if _scan(root, source=source) != before:
        raise ValueError('checkout/group inventory changed during capture')
    return before, saved


def _recheck_tree(root, before, saved, *, source):
    if _scan(root, source=source) != before:
        raise ValueError('checkout/group inventory changed before publication')
    for snapshot in saved.values():
        container._recheck(snapshot)
    if _scan(root, source=source) != before:
        raise ValueError('checkout/group inventory changed before publication')


def _pin(reference, base, snapshots, *, source=False, limit=release.MAX_JSON):
    release._keys(reference, ('path', 'sha256'), ('tree_sha256',) if source else (), 'pinned input')
    name = container.resource_path(reference['path'])
    release._sha(reference['sha256'])
    if source:
        release._sha(reference.get('tree_sha256'))
    saved = container._snapshot(base / name, limit)
    if container.digest(saved.content) != reference['sha256']:
        raise ValueError('input differs from independent SHA-256: ' + name)
    snapshots.append(saved)
    return saved


def _source_modes(project, saved, extra):
    if not source_identity.WINDOWS or not (project / 'source.json').exists():
        return {name for name, item in saved.items() if item.mode & 0o111}, 'filesystem-stat'
    authority = container._snapshot(project / 'source.json', release.MAX_JSON)
    data = release._json(authority.content)
    release._keys(data, ('schema_version', 'tree_sha256', 'files', 'executables'), label='source mode authority')
    if type(data['schema_version']) is not int or data['schema_version'] != 1 or type(data['files']) is not dict:
        raise ValueError('invalid source mode authority')
    if set(data['files']) != set(saved):
        raise ValueError('source mode authority complete file inventory differs')
    for name, digest in data['files'].items():
        archive.relative(name)
        release._sha(digest)
    executables = data['executables']
    if (type(executables) is not list or any(type(name) is not str or name not in saved for name in executables)
            or executables != sorted(set(executables))):
        raise ValueError('invalid source executable mode authority')
    expected = container.digest(archive.encoded({'files': data['files'], 'executables': executables}))
    if release._sha(data['tree_sha256']) != expected:
        raise ValueError('source mode authority tree identity differs')
    extra.append(authority)
    return set(executables), 'validated-source-json-executables'


def _tree_rows(root):
    files, _ = _scan(root, source=False)
    return {name: {'sha256': archive.digest(root / name), 'executable': bool(row[-1] & 0o111)}
            for name, row in sorted(files.items())}


def _bindings(root, language):
    result = {'guest.c': archive.digest(root / 'sdk/appended/guest.c')}
    for prefix in ('include', 'rust') if language == 'rust' else ('include',):
        path = root / 'sdk/appended' / prefix
        for name, entry in _tree_rows(path).items():
            result[prefix + '/' + name] = entry['sha256']
    for name in ('abi.h', 'provider_abi.h'):
        relative = 'include/foundation/appended/' + name
        result[relative] = archive.digest(root / relative)
    if language == 'rust' and not (root / 'sdk/appended/rust/src/lib.rs').is_file():
        raise ValueError('current Rust guest binding root is missing')
    return dict(sorted(result.items()))


def _binary(project, reference, base, retained, snapshots):
    remedy = '; compile only the guest separately with its pinned SDK; no kernel build is attempted'
    if reference is None:
        raise ValueError('current binary module and independently pinned compile receipt are required' + remedy)
    release._keys(reference, ('module', 'proof'), label='checkout binary')
    module = _pin(reference['module'], base, snapshots, limit=wasm.MAX_MODULE_BYTES)
    proof = _pin(reference['proof'], base, snapshots)
    data = release._json(proof.content)
    release._keys(data, _RECEIPT_FIELDS, label='actual guest compile receipt')
    if (type(data['schema_version']) is not int or data['schema_version'] != 1
            or data['profile'] != wasm.PROFILE or data['language'] not in ('c', 'c++', 'rust')):
        raise ValueError('unsupported current guest compile receipt' + remedy)
    release._keys(data['module'], ('sha256', 'bytes'), label='receipt module')
    if (release._sha(data['module']['sha256']) != container.digest(module.content)
            or type(data['module']['bytes']) is not int or data['module']['bytes'] != len(module.content)):
        raise ValueError('current module differs from compile receipt' + remedy)
    if not release._same_json(data['sources'], _tree_rows(project.root / project.binary.source)):
        raise ValueError('current binary source inputs differ from compile receipt' + remedy)
    if not release._same_json(data['bindings'], _bindings(project.root, data['language'])):
        raise ValueError('current guest binding inputs differ from compile receipt' + remedy)
    for field, name in (('compiler_helper_sha256', 'appended_compile.py'), ('validator_sha256', 'appended_wasm.py')):
        if release._sha(data[field]) != archive.digest(project.root / 'tools' / name):
            raise ValueError('current guest compile/validator input differs from receipt' + remedy)
    for field in ('sdk_descriptor_sha256', 'sdk_inventory_sha256'):
        release._sha(data[field])
    release._keys(data['host'], ('system', 'machine'), label='compile host')
    if any(type(item) is not str or not item or len(item) > 256 for item in data['host'].values()):
        raise ValueError('invalid original compile host')
    if (type(data['commands']) is not list or not 1 <= len(data['commands']) <= 128
            or any(type(command) is not list or not 1 <= len(command) <= 512
                   or any(type(arg) is not str or not arg or len(arg) > 8192 or '\0' in arg for arg in command)
                   for command in data['commands'])):
        raise ValueError('invalid original compile command evidence')
    if not release._same_json(data['audit'], wasm.validate_module(module.content)):
        raise ValueError('current module audit differs from compile receipt' + remedy)
    module_path = retained / 'module.wasm'
    release._save(module_path, module.content)
    release._save(retained / 'compile-receipt.json', proof.content)
    return module_path, {'module_sha256': container.digest(module.content),
                         'compile_receipt_sha256': container.digest(proof.content),
                         'sdk_validation': 'original-pinned-receipt-only; no SDK read or execution'}


def _selection(data):
    # Reuse the existing pure, complete old-schema validator. Choosing the
    # first explicit ID here validates every row; this route retains all rows.
    if (type(data) is not dict or type(data.get('kernels')) is not list
            or not 1 <= len(data['kernels']) <= 32 or type(data['kernels'][0]) is not dict):
        raise ValueError('selection needs a bounded nonempty kernel mapping')
    select_kernel(data, data['kernels'][0].get('id'))


def _output_inventory(root, *, marker=True):
    return {name: {**entry, 'mode': stat.S_IMODE((root / name).lstat().st_mode)}
            for name, entry in release._files(root).items() if marker or name != 'checkout.json'}


def _source_archive_no_git(path):
    # The unchanged release restorer eventually calls source_identity on these
    # roots. Reject aliases that would become .git on a case-insensitive host.
    with tarfile.open(path, 'r:*') as bundle:
        for _, name in archive.archive_entries(bundle, MAX_BYTES, archive.PORTABLE_PATHS):
            if name.parts[0].casefold() == '.git':
                raise ValueError('retained source archive contains Git metadata or a case-insensitive alias')


def _directory_mode(path, identity, mode):
    """Never chmod through a replaced final pathname or a symlink."""
    state = path.lstat()
    if not stat.S_ISDIR(state.st_mode) or (state.st_dev, state.st_ino) != identity:
        raise ValueError('reserved checkout directory identity changed')
    if stat.S_IMODE(state.st_mode) == mode:
        return
    if not hasattr(os, 'fchmod') or not hasattr(os, 'O_NOFOLLOW'):
        raise ValueError('safe owned-directory mode restoration is unavailable on this filesystem host')
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_DIRECTORY', 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or (opened.st_dev, opened.st_ino) != identity:
            raise ValueError('reserved checkout directory identity changed')
        os.fchmod(descriptor, mode)
    finally:
        os.close(descriptor)
    after = path.lstat()
    if not stat.S_ISDIR(after.st_mode) or (after.st_dev, after.st_ino) != identity:
        raise ValueError('reserved checkout directory identity changed')


def _publish(staged, output, recheck):
    """Exclusive tree publication; checkout.json is the last validity marker."""
    expected = _output_inventory(staged)
    directory_modes = {p.relative_to(staged).as_posix(): stat.S_IMODE(p.lstat().st_mode)
                       for p in staged.rglob('*') if p.is_dir()}
    recheck()
    output.mkdir()
    identities = {output: (output.lstat().st_dev, output.lstat().st_ino)}

    def directories_unchanged():
        for path, identity in identities.items():
            state = path.lstat()
            if not stat.S_ISDIR(state.st_mode) or (state.st_dev, state.st_ino) != identity:
                raise ValueError('reserved checkout directory identity changed')

    def inventory(marker):
        directories_unchanged()
        observed = {p.relative_to(output).as_posix(): stat.S_IMODE(p.lstat().st_mode)
                    for p in output.rglob('*') if p.is_dir() and not p.is_symlink()}
        wanted = expected if marker else {name: row for name, row in expected.items() if name != 'checkout.json'}
        if observed != directory_modes or _output_inventory(output, marker=marker) != wanted:
            raise ValueError('reserved checkout inventory changed during publication')

    try:
        for name in sorted(directory_modes, key=lambda item: (item.count('/'), item)):
            directories_unchanged()
            path = output / name
            path.mkdir()
            identities[path] = (path.lstat().st_dev, path.lstat().st_ino)
        for name in sorted(expected):
            if name == 'checkout.json':
                continue
            directories_unchanged()
            os.link(staged / name, output / name, follow_symlinks=False)
        for name in sorted(directory_modes, reverse=True):
            _directory_mode(output / name, identities[output / name], directory_modes[name])
        recheck()
        inventory(False)
        if (output / 'checkout.json').exists() or (output / 'checkout.json').is_symlink():
            raise ValueError('checkout validity marker appeared before publication')
        os.link(staged / 'checkout.json', output / 'checkout.json', follow_symlinks=False)
        inventory(True)
    except BaseException as error:
        raise ValueError('checkout publication incomplete; preserve and inspect reserved output: ' + str(output)) from error


def prepare_checkout(project_root, request_path, output, *, before_publish=None):
    """Create one new staging group and its unchanged, unqualified candidate."""
    project_root = container._ordinary_path(project_root, directory=True)
    request_saved = container._snapshot(request_path, release.MAX_JSON)
    request = release._json(request_saved.content)
    release._keys(request, ('schema_version', 'kind', 'selection', 'binary'), ('requires',), 'checkout request')
    if (type(request['schema_version']) is not int or request['schema_version'] != 1
            or request['kind'] != 'foundation-appended-checkout-request'):
        raise ValueError('unsupported checkout request schema')
    if 'requires' in request:
        container._requirements(request['requires'])
    snapshots = [request_saved]
    old_saved = _pin(request['selection'], request_saved.path.parent, snapshots)
    old = release._json(old_saved.content)
    _selection(old)
    group = old_saved.path.parent
    if _inside(project_root, group):
        raise ValueError('acquired retained group must not contain the current checkout')
    if _inside(group, project_root) and (not _pruned(group.relative_to(project_root).as_posix())
            or group.relative_to(project_root).parts[0] == '.git'):
        raise ValueError('acquired retained group must be outside selected checkout source inputs')
    output = Path(os.path.abspath(os.fspath(output)))
    container._ordinary_path(output.parent, directory=True)
    if output.exists() or output.is_symlink():
        raise ValueError('checkout output must be new')
    if _inside(output, group) or _inside(group, output):
        raise ValueError('checkout output must be outside acquired retained inputs')
    if _inside(output, project_root) and not _pruned(output.relative_to(project_root).as_posix()):
        raise ValueError('checkout output must be outside selected source inputs or under an ignored source root')
    if _inside(output.parent, project_root) and (output.parent == project_root
            or not _pruned(output.parent.relative_to(project_root).as_posix())):
        raise ValueError('checkout staging parent must be outside selected source inputs or inside an existing ignored root')
    with tempfile.TemporaryDirectory(prefix='.appended-checkout-', dir=output.parent) as temporary:
        workspace = Path(temporary)
        staged = workspace / 'checkout'
        staged.mkdir()
        source_root = workspace / 'current-source'
        source_before, source_saved = _capture(project_root, source_root, source=True)
        # Resolve only the pinned strict-selection reference closure. A selected
        # JSON file never authorizes reading unrelated siblings in its parent.
        inputs = release.Inputs(group, workspace / 'validated-inputs')
        retained = staged / 'retained'
        retained.mkdir()
        release._save(retained / old_saved.path.name, old_saved.content)
        (retained / old_saved.path.name).chmod(old_saved.mode)
        mirrors = {old_saved.path.name: old_saved}
        closure_bytes = len(old_saved.content)
        consumption_bytes = closure_bytes
        if closure_bytes > MAX_BYTES or len(mirrors) > MAX_FILES:
            raise ValueError('retained selection reference closure exceeds aggregate limit')
        mirror_paths = archive.PathInventory()
        mirror_paths.add(old_saved.path.name, False)
        source_archives = set()

        def reference(value, *, source=False):
            nonlocal closure_bytes, consumption_bytes
            # Every reference shape/pin was checked by select_kernel above.
            # Repeated paths share one independently validated snapshot rather
            # than multiplying retained input bytes and memory per reference.
            name = value['path']
            if name in mirrors:
                saved = mirrors[name]
                if len(saved.content) > MAX_BYTES - consumption_bytes:
                    raise ValueError('retained reference composition consumption exceeds aggregate byte limit')
                if container.digest(saved.content) != value['sha256']:
                    raise ValueError('repeated retained reference differs from SHA-256: ' + name)
            else:
                if len(mirrors) >= MAX_FILES:
                    raise ValueError('retained selection reference closure exceeds aggregate file limit')
                mirror_paths.add(name, False)
                _, _, content = inputs.read(value, source=source,
                                             limit=min(release.MAX_INPUT, MAX_BYTES - closure_bytes,
                                                       MAX_BYTES - consumption_bytes))
                saved = inputs.snapshots[-1]
                closure_bytes += len(content)
                release._save(retained / name, content)
                (retained / name).chmod(saved.mode)
                mirrors[name] = saved
            # Bound declared retained consumption in the unchanged composer as
            # well as unique capture. This is not a process RSS bound: source,
            # snapshots and composition buffers may coexist.
            consumption_bytes += len(saved.content)
            if source and value['sha256'] not in source_archives:
                _source_archive_no_git(retained / name)
                source_archives.add(value['sha256'])
            return {**value, 'path': 'retained/' + name}

        modes, mode_authority = _source_modes(project_root, source_saved, snapshots)
        for name in source_saved:
            (source_root / name).chmod(0o755 if name in modes else 0o644)
        described = source_identity.describe_paths({name: source_root / name for name in source_saved}, modes)
        release._save(source_root / 'source.json', archive.encoded(described))
        # On a case-insensitive host an ordinary-looking .GIT entry can alias
        # .git. Fail closed before any source_identity branch could launch Git.
        if (source_root / '.git').exists() or (source_root / '.git').is_symlink():
            raise ValueError('captured source contains Git metadata or a case-insensitive alias')
        source_archive = staged / 'current-source.tar.gz'
        if source_identity.archive_source(source_root, source_archive) != described:
            raise ValueError('current complete source archive identity differs')
        project = load_project(source_root)
        insulation = release.policy.audit(source_root,
            binary_roots=(project.binary.source, 'sdk/appended') if project.binary.enabled else ('sdk/appended',),
            web_roots=(project.web.source,) if project.web.enabled else ())
        if not insulation['ok']:
            raise ValueError('selected appended source insulation failed: '
                             + container.canonical_json(insulation['violations']).decode().strip())
        binary_record, module = None, None
        if project.binary.enabled:
            module, binary_record = _binary(project, request['binary'], request_saved.path.parent,
                                             staged / 'binary-proof', snapshots)
        elif request['binary'] is not None:
            raise ValueError('disabled binary component must have null module proof')
        payload = None
        if project.mode != 'neither':
            if project.web.enabled and not project.configured:
                raise ValueError('Rich startup requires an explicit configured primary')
            payload_path = staged / 'application.sfapp'
            identities = {'source_tree': described['tree_sha256']}
            if project.configured:
                identities['project-config'] = container.digest(project._source_bytes)
            if binary_record:
                identities['compile-receipt'] = binary_record['compile_receipt_sha256']
            container._pack(source_root / project.web.source if project.web.enabled else None,
                            module, payload_path, application=project.data['application'],
                            web_entry=project.web.entry or 'index.html', binary_profile=wasm.PROFILE,
                            requires=request.get('requires'), identities=identities, startup=project.web.enabled,
                            _startup_primary=project.startup_primary)
            payload = {'path': payload_path.name, 'sha256': archive.digest(payload_path)}
        elif 'requires' in request:
            container._requirements(request['requires'])
        selection = {'schema_version': 1, 'kind': 'foundation-appended-selection',
                     'application': project.data['application'],
                     'source': {'path': source_archive.name, 'sha256': archive.digest(source_archive),
                                'tree_sha256': described['tree_sha256']}, 'payload': payload, 'kernels': []}
        # Preserve exact selected bytes and modes, not unreferenced parent data.
        reference(old['source'], source=True)
        if old['payload'] is not None:
            reference(old['payload'])
        eligibility = []
        for row in old['kernels']:
            current = copy.deepcopy(row)
            for key in ('archive', 'inventory', 'descriptor', 'original_source'):
                current[key] = reference(row[key], source=key == 'original_source')
            for key in ('recovery', 'evidence'):
                current[key] = [reference(ref) for ref in row[key]]
            selection['kernels'].append(current)
            descriptor = container.validate_descriptor(release._json(mirrors[row['descriptor']['path']].content))
            eligibility.append({'id': row['id'], 'descriptor_sha256': row['descriptor']['sha256'],
                                'original_source': copy.deepcopy(row['original_source']),
                                'current': release.policy.retained_eligibility(source_root, descriptor.get('kernel_inputs'))})
        release._document(staged / 'selection.json', selection)
        release._save(staged / 'request.json', request_saved.content)
        candidate = release.prepare_release(staged / 'selection.json', staged / 'candidate')
        source_policy = {'policy': POLICY, 'selection': 'source_identity.source_files_without_git',
                         'exclusions': 'source_identity.ignored_source_path; Git ignore rules not consulted',
                         'mode_authority': mode_authority, 'tree_sha256': described['tree_sha256'],
                         'files': len(described['files']), 'bytes': sum(len(item.content) for item in source_saved.values())}
        result = {**candidate, 'candidate_directory': 'candidate',
                  'selection_sha256': archive.digest(staged / 'selection.json'),
                  'source_tree_sha256': described['tree_sha256'], 'source_policy': source_policy}
        receipt = {'schema_version': 1, 'kind': 'foundation-appended-checkout',
                   'policy': POLICY, 'request_sha256': container.digest(request_saved.content),
                   'retained_selection_sha256': container.digest(old_saved.content),
                   'retained_inputs': {'policy': 'exact-pinned-selection-reference-closure-v1',
                                       'paths': sorted(mirrors), 'unreferenced_parent_entries': 'not enumerated or read'},
                   'source_policy': source_policy, 'binary': binary_record, 'insulation': insulation,
                   'kernel_eligibility': eligibility, 'candidate': result,
                   'qualification': 'incomplete', 'publication_eligible': False,
                   'files': _output_inventory(staged)}
        release._document(staged / 'checkout.json', receipt)

        def unchanged():
            if before_publish is not None:
                before_publish()
            for saved in snapshots:
                container._recheck(saved)
            for saved in inputs.snapshots:
                container._recheck(saved)
            _recheck_tree(project_root, source_before, source_saved, source=True)

        _publish(staged, output, unchanged)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    print(container.canonical_json(prepare_checkout(args.project_root, args.request, args.output)).decode(), end='')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('appended checkout: ' + str(error), file=sys.stderr)
        sys.exit(1)
