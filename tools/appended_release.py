#!/usr/bin/env python3
"""Prepare unqualified appended candidates from explicitly pinned retained bytes.

This versioned route is independent of legacy release/certification schemas. It
does no kernel build, installation, publication or qualification. Its recovery
operation means deterministic recomposition, never native kernel reconstruction.
"""
import argparse
import gzip
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
import tempfile
import zipfile
import zlib

import appended_container as container
import appended_policy as policy
from appended_project import load_project
import artifact
import dependency_archive as archive
import source_identity

MAX_INPUT = 512 * 1024 * 1024
MAX_JSON = 16 * 1024 * 1024
POLICY = 'foundation-appended-composition-candidate-v1'
COMPOSER_SOURCES = ('appended_release.py', 'appended_container.py', 'appended_policy.py',
                    'appended_project.py', 'appended_wasm.py', 'source_identity.py',
                    'artifact.py', 'dependency_archive.py')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')


def _keys(value, required, optional=(), label='object'):
    if (type(value) is not dict or not set(required) <= set(value)
            or set(value) - set(required) - set(optional)):
        raise ValueError('invalid ' + label + ' fields')


def _sha(value):
    if type(value) is not str or not SHA.fullmatch(value):
        raise ValueError('an exact lowercase SHA-256 is required')
    return value


def _name(value):
    if type(value) is not str or not NAME.fullmatch(value):
        raise ValueError('invalid candidate asset name')
    # Reuse the archive path policy, including Windows device-name rejection.
    container.resource_path(value)
    return value


def _json(data):
    try:
        result = json.loads(data.decode('utf-8'), object_pairs_hook=archive.object_pairs)
        container.canonical_json(result)
        return result
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('invalid bounded JSON document') from error


def _same_json(left, right):
    # Python equality aliases bool and int. Typed wire records must distinguish
    # false from 0 and true from 1, including nested inventories and ABI fields.
    return container.canonical_json(left) == container.canonical_json(right)


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as output:
        output.write(data)


def _document(path, value):
    _save(path, container.canonical_json(value))


def _files(root, exclude=()):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError('candidate contains a linked or special entry')
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if name not in exclude:
                result[name] = {'size': path.stat().st_size, 'sha256': archive.digest(path)}
    return result


def _publish_tree(staged, output, snapshots=(), *, precondition=None):
    """Reserve a fresh directory; expose its validity marker only after all files.

    mkdir and each hardlink are exclusive. Even a concurrently appearing empty
    destination is preserved. An incomplete directory has no candidate.json and
    can never verify as a candidate. No replacing directory rename is used.
    """
    output = Path(os.path.abspath(os.fspath(output)))
    container._ordinary_path(output.parent, directory=True)
    for saved in snapshots:
        container._recheck(saved)
    if precondition is not None:
        precondition()
    output.mkdir()  # Atomic no-clobber reservation, including existing symlinks.
    directories = {output: output.lstat()}

    def check_directories():
        for path, before in directories.items():
            current = path.lstat()
            if (not stat.S_ISDIR(current.st_mode) or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)):
                raise ValueError('reserved output directory identity changed')

    expected_files = _files(staged)
    expected_directories = {path.relative_to(staged).as_posix() for path in staged.rglob('*') if path.is_dir()}

    def check_published(marker=False):
        check_directories()
        expected = {name: value for name, value in expected_files.items() if marker or name != 'candidate.json'}
        actual_directories = {path.relative_to(output).as_posix() for path in output.rglob('*') if path.is_dir()}
        if _files(output) != expected or actual_directories != expected_directories:
            raise ValueError('reserved output inventory changed during publication')

    try:
        paths = sorted(staged.rglob('*'), key=lambda p: (p.relative_to(staged).as_posix() == 'candidate.json', p.as_posix()))
        for path in paths:
            check_directories()
            target = output / path.relative_to(staged)
            if path.is_dir():
                target.mkdir()
                directories[target] = target.lstat()
            else:
                if path.relative_to(staged).as_posix() == 'candidate.json':
                    for saved in snapshots:
                        container._recheck(saved)
                    check_published()
                    if precondition is not None:
                        precondition()
                os.link(path, target, follow_symlinks=False)
        check_published(marker=True)
    except BaseException as error:
        # Another writer could have inserted foreign entries or replaced an
        # inode. Never recursively remove a final pathname on an uncertain save.
        raise ValueError('publication incomplete; preserve and inspect reserved output: ' + str(output)) from error
    return output


class Inputs:
    def __init__(self, base, retained):
        self.base, self.retained = base, retained
        self.snapshots = []

    def read(self, reference, *, source=False, limit=MAX_INPUT):
        _keys(reference, ('path', 'sha256'), ('tree_sha256',) if source else (), 'pinned input')
        if source:
            _sha(reference.get('tree_sha256'))
        relative = container.resource_path(reference['path'])
        saved = container._snapshot(self.base / relative, limit)
        pin = _sha(reference['sha256'])
        if container.digest(saved.content) != pin:
            raise ValueError('retained input differs from SHA-256: ' + relative)
        self.snapshots.append(saved)
        name = 'inputs/' + pin
        destination = self.retained / pin
        if not destination.exists():
            _save(destination, saved.content)
        elif destination.read_bytes() != saved.content:
            raise ValueError('retained content address collision')
        result = {'path': name, 'sha256': pin}
        if source:
            result['tree_sha256'] = reference['tree_sha256']
        return result, destination, saved.content


def _source(path, reference, workspace, label):
    # Apply this operation's smaller recovery bound before the general source
    # verifier (which permits SDK-sized 32 GiB source groups).
    with tarfile.open(path, 'r:*') as source:
        entries = archive.archive_entries(source, MAX_INPUT, archive.PORTABLE_PATHS)
        for member, name in entries:
            value = name.as_posix()
            if not (member.isfile() and value == 'source.json') and source_identity.ignored_source_path(value):
                raise ValueError('source archive includes excluded/generated/private inputs')
    described = source_identity.verify_source_archive(path)
    if described['tree_sha256'] != reference['tree_sha256']:
        raise ValueError('complete source identity differs: ' + label)
    if any(source_identity.ignored_source_path(name) for name in described['files']):
        raise ValueError('source archive includes excluded/generated/private inputs')
    root = workspace / label
    # The existing complete archive validator rejects links, special files,
    # traversal and aliases before extraction into this private fresh location.
    archive.extract(path, root, max_bytes=MAX_INPUT)
    if source_identity.source_tree(root) != described:
        raise ValueError('restored source bytes or modes differ: ' + label)
    return root, described


def _members(path):
    """Use the package safety checker, then preserve exact file data and modes."""
    described = artifact.describe(path)
    files, directories = {}, {}
    registry = archive.PathInventory()
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as bundle:
            for member in bundle.infolist():
                name = member.filename[:-1] if member.is_dir() else member.filename
                registry.add(name, member.is_dir())
                mode = member.external_attr >> 16
                if member.is_dir():
                    directories[name] = stat.S_IMODE(mode) if member.create_system == 3 else 0o755
                else:
                    files[name] = (bundle.read(member), stat.S_IMODE(mode) if member.create_system == 3 else 0o644)
    else:
        with tarfile.open(path, 'r:*') as bundle:
            for member in bundle:
                name = member.name.rstrip('/') if member.isdir() else member.name
                registry.add(name, member.isdir())
                if member.isdir():
                    directories[name] = member.mode
                else:
                    with bundle.extractfile(member) as stream:
                        files[name] = (stream.read(), member.mode)
    return described, files, directories


def _write_archive(path, files, directories):
    # Deterministic tar.gz is the only initial output container. Input may be a
    # ZIP or tar archive. Every retained member byte/mode survives repackaging.
    with path.open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w', format=tarfile.PAX_FORMAT) as bundle:
            for name in sorted(set(files) | set(directories)):
                member = tarfile.TarInfo(name)
                member.mtime = 0
                if name in directories:
                    member.type = tarfile.DIRTYPE
                    member.mode = directories[name]
                    bundle.addfile(member)
                else:
                    data, member.mode = files[name]
                    member.size = len(data)
                    bundle.addfile(member, io.BytesIO(data))


def _mode_inventory(files):
    return {name: mode for name, (_, mode) in sorted(files.items())}


def prepare_release(selection_path, output, *, expected_candidate_sha256=None, before_publish=None):
    """Freeze one package into all explicit kernel archive/runtime mappings."""
    saved_selection = container._snapshot(selection_path, MAX_JSON)
    selection = _json(saved_selection.content)
    _keys(selection, ('schema_version', 'kind', 'application', 'source', 'payload', 'kernels'), label='selection')
    if type(selection['schema_version']) is not int or selection['schema_version'] != 1 or selection['kind'] != 'foundation-appended-selection':
        raise ValueError('unsupported appended selection schema')
    container._application(selection['application'])
    if type(selection['kernels']) is not list or not 1 <= len(selection['kernels']) <= 32:
        raise ValueError('selection needs a bounded nonempty kernel mapping')
    output = Path(os.path.abspath(os.fspath(output)))
    container._ordinary_path(output.parent, directory=True)
    if output.exists() or output.is_symlink():
        raise ValueError('candidate output must be new')
    with tempfile.TemporaryDirectory(prefix='.appended-release-', dir=output.parent) as temporary:
        workspace = Path(temporary)
        staged = workspace / 'candidate'
        (staged / 'inputs').mkdir(parents=True)
        (staged / 'artifacts').mkdir()
        inputs = Inputs(saved_selection.path.parent, staged / 'inputs')
        composer_snapshots = [container._snapshot(Path(__file__).resolve().parent / name, MAX_JSON)
                              for name in COMPOSER_SOURCES]
        composer = {saved.path.name: container.digest(saved.content) for saved in composer_snapshots}
        for saved in composer_snapshots:
            recipe = staged / 'inputs' / container.digest(saved.content)
            if not recipe.exists():
                _save(recipe, saved.content)
        source_ref, source_path, _ = inputs.read(selection['source'], source=True)
        current, source = _source(source_path, source_ref, workspace, 'downstream-source')
        project = load_project(current)
        if project.data['application'] != selection['application']:
            raise ValueError('selected application differs from restored downstream project configuration')
        payload_ref, payload = None, None
        if selection['payload'] is not None:
            payload_ref, _, payload_bytes = inputs.read(selection['payload'])
            transported = container.parse_artifact(payload_bytes)
            if transported.carrier != 'package' or transported.package is None:
                raise ValueError('payload must be one standalone verified application package')
            payload = transported.package
            if payload.index['application'] != selection['application']:
                raise ValueError('payload application differs from selected downstream identity')
            bound_source = payload.index['identities'].get('source_tree')
            if bound_source is not None and bound_source != source['tree_sha256']:
                raise ValueError('payload source identity differs from downstream source')
        mode = payload.mode if payload is not None else 'neither'
        if project.mode != mode:
            raise ValueError('selected payload mode differs from restored downstream project configuration')
        frozen = {'schema_version': 1, 'kind': selection['kind'], 'application': selection['application'],
                  'source': source_ref, 'payload': payload_ref, 'kernels': []}
        products, identifiers, outputs = [], set(), set()
        for entry in selection['kernels']:
            _keys(entry, ('id', 'archive', 'inventory', 'descriptor', 'runtime_member', 'output',
                          'original_source', 'recovery', 'evidence'), label='kernel selection')
            identity, filename = _name(entry['id']), _name(entry['output'])
            if identity in identifiers or filename.casefold() in outputs or not filename.endswith('.tar.gz'):
                raise ValueError('duplicate kernel/output or unsupported output archive suffix')
            identifiers.add(identity)
            outputs.add(filename.casefold())
            for kind in ('recovery', 'evidence'):
                if type(entry[kind]) is not list or len(entry[kind]) > 128:
                    raise ValueError('invalid retained ' + kind + ' group')
            if not entry['recovery']:
                raise ValueError('explicit kernel reconstruction/recovery inputs are required')
            retained = {'id': identity, 'runtime_member': container.resource_path(entry['runtime_member']),
                        'output': filename}
            paths, data = {}, {}
            for kind in ('archive', 'inventory', 'descriptor', 'original_source'):
                retained[kind], paths[kind], data[kind] = inputs.read(entry[kind], source=kind == 'original_source',
                                                                    limit=MAX_JSON if kind in ('descriptor', 'inventory') else MAX_INPUT)
            for kind in ('recovery', 'evidence'):
                retained[kind] = [inputs.read(item)[0] for item in entry[kind]]
            descriptor = container.validate_descriptor(container.parse_json(data['descriptor'], 'kernel descriptor'))
            if project.kernel_profile != 'auto' and descriptor['profile'] != project.kernel_profile:
                raise ValueError('retained kernel profile differs from explicit downstream project configuration')
            policy.validate_kernel_inputs(descriptor.get('kernel_inputs'))
            original, original_source = _source(paths['original_source'], retained['original_source'], workspace,
                                                'original-source-' + identity)
            for root in (original, current):
                eligibility = policy.retained_eligibility(root, descriptor['kernel_inputs'])
                if not eligibility['eligible']:
                    raise ValueError('kernel maintenance required for ' + identity + ': ' + eligibility['reason']
                                     + '; differences=' + json.dumps(eligibility['differences'], sort_keys=True))
            described, members, directories = _members(paths['archive'])
            expected = _json(data['inventory'])
            _keys(expected, ('schema_version', 'archive', 'sha256', 'files'), ('modes',), 'archive inventory')
            if (type(expected['schema_version']) is not int or expected['schema_version'] != 1
                    or expected['sha256'] != retained['archive']['sha256']
                    or not _same_json(expected['files'], described['files'])):
                raise ValueError('complete retained archive inventory mismatch')
            if 'modes' in expected and not _same_json(expected['modes'], _mode_inventory(members)):
                raise ValueError('retained archive mode inventory mismatch')
            runtime = retained['runtime_member']
            if runtime not in members:
                raise ValueError('selected finalized runtime member is absent')
            before, file_mode = members[runtime]
            existing = container.parse_artifact(before, descriptor)
            after = container.compose_bytes(before, descriptor, payload, expected_mode=mode)
            members[runtime] = (after, file_mode)
            destination = staged / 'artifacts' / filename
            _write_archive(destination, members, directories)
            result, observed, observed_directories = _members(destination)
            if observed != members or observed_directories != directories:
                raise ValueError('composed archive changed retained runtime member bytes or modes')
            frozen['kernels'].append(retained)
            products.append({'id': identity, 'archive': 'artifacts/' + filename,
                             'sha256': archive.digest(destination), 'files': result['files'],
                             'modes': _mode_inventory(observed), 'runtime_member': runtime,
                             'kernel_descriptor_sha256': retained['descriptor']['sha256'],
                             'original_source_tree_sha256': original_source['tree_sha256'],
                             'kernel_prefix_sha256': container.digest(existing.prefix),
                             'kernel_prefix_length': len(existing.prefix), 'carrier': descriptor['carrier'],
                             'profile': descriptor['profile'], 'abi': descriptor['abi'],
                             'capabilities': descriptor['capabilities'], 'services': descriptor['services'],
                             'directories': observed_directories,
                             'runtime_sha256': container.digest(after), 'runtime_size': len(after)})
        # Input paths have been replaced by content addresses; relocation does
        # not change configuration identity or deterministic recovery output.
        _document(staged / 'selection.json', frozen)
        composition = {'schema_version': 1, 'kind': 'foundation-appended-composition', 'policy': POLICY,
                       'application': selection['application'], 'source': source_ref,
                       'composer_sources': composer,
                       'recomposition_environment': {'python_implementation': sys.implementation.name,
                                                     'python_version': list(sys.version_info[:3]),
                                                     'zlib_compile_version': zlib.ZLIB_VERSION,
                                                     'zlib_runtime_version': zlib.ZLIB_RUNTIME_VERSION,
                                                     'archive': 'tar-pax-gzip-mtime0-level9'},
                       'selection_sha256': archive.digest(staged / 'selection.json'),
                       'payload': {'transport_sha256': payload_ref['sha256'] if payload_ref else None,
                                   'package_sha256': payload.package_sha256 if payload else None,
                                   'payload_id': payload.payload_id if payload else None, 'mode': mode}, 'artifacts': products,
                       'qualification': {'status': 'incomplete', 'publication_eligible': False,
                                         'kernel_evidence': 'retained-original-references-only',
                                         'native_reconstruction': 'unverified',
                                         'pending': ['original-kernel-evidence-policy', 'runtime-application',
                                                     'browser-if-enabled', 'install-upgrade', 'recovery-qualification']}}
        _document(staged / 'composition.json', composition)
        _document(staged / 'recovery.json', {'schema_version': 1, 'kind': 'foundation-appended-recomposition',
                                           'scope': 'retained-kernel-recomposition-only',
                                           'selection': 'selection.json',
                                           'selection_sha256': archive.digest(staged / 'selection.json'),
                                           'composition_sha256': archive.digest(staged / 'composition.json')})
        candidate = {'schema_version': 1, 'kind': 'foundation-appended-candidate', 'policy': POLICY,
                     'qualification': 'incomplete', 'publication_eligible': False,
                     'files': _files(staged)}
        _document(staged / 'candidate.json', candidate)
        candidate_sha = archive.digest(staged / 'candidate.json')
        if expected_candidate_sha256 is not None and candidate_sha != expected_candidate_sha256:
            raise ValueError('recomposition did not reproduce the frozen candidate inventory')
        verify_candidate(staged, candidate_sha)
        snapshots = [saved_selection, *inputs.snapshots, *composer_snapshots]
        if before_publish is None:
            _publish_tree(staged, output, snapshots)
        else:
            _publish_tree(staged, output, snapshots, precondition=before_publish)
    return {'candidate_sha256': candidate_sha, 'composition_sha256': container.digest(container.canonical_json(composition)),
            'qualification': 'incomplete', 'publication_eligible': False, 'artifacts': len(products)}


def verify_candidate(directory, candidate_sha256):
    directory = container._ordinary_path(directory, directory=True)
    saved = container._snapshot(directory / 'candidate.json', MAX_JSON)
    if container.digest(saved.content) != _sha(candidate_sha256):
        raise ValueError('candidate inventory differs from independently pinned SHA-256')
    document = _json(saved.content)
    _keys(document, ('schema_version', 'kind', 'policy', 'qualification', 'publication_eligible', 'files'), label='candidate')
    if (type(document['schema_version']) is not int or document['schema_version'] != 1
            or document['kind'] != 'foundation-appended-candidate' or document['policy'] != POLICY
            or document['qualification'] != 'incomplete' or document['publication_eligible'] is not False
            or not _same_json(document['files'], _files(directory, ('candidate.json',)))):
        raise ValueError('candidate complete inventory or conservative qualification status is invalid')
    for name in ('selection.json', 'composition.json', 'recovery.json'):
        if name not in document['files']:
            raise ValueError('candidate is missing frozen recomposition metadata')
    recovery = _json(container._snapshot(directory / 'recovery.json', MAX_JSON).content)
    _keys(recovery, ('schema_version', 'kind', 'scope', 'selection', 'selection_sha256', 'composition_sha256'),
          label='recovery metadata')
    if (type(recovery['schema_version']) is not int or recovery['schema_version'] != 1
            or recovery.get('kind') != 'foundation-appended-recomposition'
            or recovery.get('scope') != 'retained-kernel-recomposition-only'
            or recovery.get('selection') != 'selection.json'
            or recovery.get('selection_sha256') != document['files']['selection.json']['sha256']
            or recovery.get('composition_sha256') != document['files']['composition.json']['sha256']):
        raise ValueError('candidate recovery bindings differ')
    return document



def verify_composition_subject(directory, candidate_sha256):
    """Deeply verify a frozen v1 candidate without executing or rebuilding it.

    An independently pinned inventory proves the selected tree's identity; this
    additional pass proves the typed relationships between source, retained
    kernels, payload and every produced member. It grants no runtime qualification.
    """
    directory = container._ordinary_path(directory, directory=True)

    def identities():
        return {str(path.relative_to(directory)): container._identity(path.lstat())
                for path in [directory, *sorted(directory.rglob('*'))]}

    before = identities()
    candidate = verify_candidate(directory, candidate_sha256)
    selection_bytes = container._snapshot(directory / 'selection.json', MAX_JSON).content
    composition_bytes = container._snapshot(directory / 'composition.json', MAX_JSON).content
    selection = container.parse_json(selection_bytes, 'frozen appended selection')
    composition = container.parse_json(composition_bytes, 'composition record')
    _keys(selection, ('schema_version', 'kind', 'application', 'source', 'payload', 'kernels'), label='selection')
    _keys(composition, ('schema_version', 'kind', 'policy', 'application', 'source', 'composer_sources',
                        'recomposition_environment', 'selection_sha256', 'payload', 'artifacts', 'qualification'),
          label='composition')
    if (type(selection['schema_version']) is not int or selection['schema_version'] != 1
            or selection['kind'] != 'foundation-appended-selection'
            or type(composition['schema_version']) is not int or composition['schema_version'] != 1
            or composition['kind'] != 'foundation-appended-composition' or composition['policy'] != POLICY
            or composition['application'] != selection['application'] or composition['source'] != selection['source']
            or composition['selection_sha256'] != container.digest(selection_bytes)):
        raise ValueError('composition and frozen selection identities differ')
    container._application(selection['application'])
    expected_qualification = {'status': 'incomplete', 'publication_eligible': False,
        'kernel_evidence': 'retained-original-references-only', 'native_reconstruction': 'unverified',
        'pending': ['original-kernel-evidence-policy', 'runtime-application', 'browser-if-enabled',
                    'install-upgrade', 'recovery-qualification']}
    if not _same_json(composition['qualification'], expected_qualification):
        raise ValueError('immutable composition qualification declaration differs')
    environment = composition['recomposition_environment']
    _keys(environment, ('python_implementation', 'python_version', 'zlib_compile_version', 'zlib_runtime_version', 'archive'),
          label='recomposition environment')
    if (any(type(environment[key]) is not str or not environment[key] for key in
            ('python_implementation', 'zlib_compile_version', 'zlib_runtime_version'))
            or type(environment['python_version']) is not list or len(environment['python_version']) != 3
            or any(type(value) is not int or value < 0 for value in environment['python_version'])
            or environment['archive'] != 'tar-pax-gzip-mtime0-level9'):
        raise ValueError('invalid recorded recomposition environment')
    consumed = {'selection.json', 'composition.json', 'recovery.json'}

    def retained(reference, *, source=False, limit=MAX_INPUT):
        _keys(reference, ('path', 'sha256'), ('tree_sha256',) if source else (), 'retained reference')
        pin = _sha(reference['sha256'])
        if source:
            _sha(reference.get('tree_sha256'))
        name = container.resource_path(reference['path'])
        if name != 'inputs/' + pin or candidate['files'].get(name, {}).get('sha256') != pin:
            raise ValueError('retained reference differs from its content address')
        saved = container._snapshot(directory / name, limit)
        if container.digest(saved.content) != pin:
            raise ValueError('retained reference hash differs')
        consumed.add(name)
        return saved.path, saved.content

    composers = composition['composer_sources']
    if type(composers) is not dict or set(composers) != set(COMPOSER_SOURCES):
        raise ValueError('incomplete composition tool source inventory')
    for name, pin in composers.items():
        retained({'path': 'inputs/' + _sha(pin), 'sha256': pin}, limit=MAX_JSON)
    kernels, products = selection['kernels'], composition['artifacts']
    if (type(kernels) is not list or not 1 <= len(kernels) <= 32
            or type(products) is not list or len(products) != len(kernels)):
        raise ValueError('composition artifact inventory differs from selected kernels')
    with tempfile.TemporaryDirectory(prefix='appended-subject-') as temporary:
        workspace = Path(temporary)
        source_path, _ = retained(selection['source'], source=True)
        current, source = _source(source_path, selection['source'], workspace, 'downstream-source')
        project = load_project(current)
        if project.data['application'] != selection['application']:
            raise ValueError('composition application differs from restored project')
        payload = None
        if selection['payload'] is not None:
            _, payload_bytes = retained(selection['payload'])
            transported = container.parse_artifact(payload_bytes)
            if transported.carrier != 'package' or transported.package is None:
                raise ValueError('composition payload is not one standalone package')
            payload = transported.package
            if payload.index['application'] != selection['application']:
                raise ValueError('composition payload application differs')
            if payload.index['identities'].get('source_tree', source['tree_sha256']) != source['tree_sha256']:
                raise ValueError('composition payload source identity differs')
        mode = payload.mode if payload else 'neither'
        if project.mode != mode:
            raise ValueError('composition payload mode differs from restored project')
        expected_payload = {'transport_sha256': selection['payload']['sha256'] if payload else None,
                            'package_sha256': payload.package_sha256 if payload else None,
                            'payload_id': payload.payload_id if payload else None, 'mode': mode}
        if composition['payload'] != expected_payload:
            raise ValueError('composition payload hashes or presence differ')
        names, outputs = set(), set()
        for selected, product in zip(kernels, products):
            _keys(selected, ('id', 'runtime_member', 'output', 'archive', 'inventory', 'descriptor',
                             'original_source', 'recovery', 'evidence'), label='selected kernel')
            identity, output = _name(selected['id']), _name(selected['output'])
            if identity in names or output.casefold() in outputs or not output.endswith('.tar.gz'):
                raise ValueError('duplicate or invalid composition artifact identity')
            names.add(identity)
            outputs.add(output.casefold())
            paths, values = {}, {}
            for kind in ('archive', 'inventory', 'descriptor', 'original_source'):
                paths[kind], values[kind] = retained(selected[kind], source=kind == 'original_source',
                    limit=MAX_JSON if kind in ('inventory', 'descriptor') else MAX_INPUT)
            for kind in ('recovery', 'evidence'):
                if type(selected[kind]) is not list or len(selected[kind]) > 128 or kind == 'recovery' and not selected[kind]:
                    raise ValueError('invalid retained ' + kind + ' inventory')
                for reference in selected[kind]:
                    retained(reference)
            descriptor = container.validate_descriptor(container.parse_json(values['descriptor'], 'retained descriptor'))
            if project.kernel_profile != 'auto' and descriptor['profile'] != project.kernel_profile:
                raise ValueError('retained profile differs from explicit project profile')
            policy.validate_kernel_inputs(descriptor.get('kernel_inputs'))
            original, original_source = _source(paths['original_source'], selected['original_source'], workspace,
                                                'original-source-' + identity)
            for tree in (original, current):
                if not policy.retained_eligibility(tree, descriptor['kernel_inputs'])['eligible']:
                    raise ValueError('kernel source projection differs from the retained descriptor')
            described, members, directories = _members(paths['archive'])
            expected_inventory = _json(values['inventory'])
            _keys(expected_inventory, ('schema_version', 'archive', 'sha256', 'files'), ('modes',), 'original archive inventory')
            if (type(expected_inventory['schema_version']) is not int or expected_inventory['schema_version'] != 1
                    or expected_inventory['sha256'] != selected['archive']['sha256']
                    or not _same_json(expected_inventory['files'], described['files'])
                    or 'modes' in expected_inventory and not _same_json(expected_inventory['modes'], _mode_inventory(members))):
                raise ValueError('retained archive inventory differs')
            runtime = container.resource_path(selected['runtime_member'])
            if runtime not in members:
                raise ValueError('selected retained runtime member is absent')
            old_runtime, mode_bits = members[runtime]
            existing = container.parse_artifact(old_runtime, descriptor)
            expected_members = dict(members)
            new_runtime = container.compose_bytes(old_runtime, descriptor, payload, expected_mode=mode)
            expected_members[runtime] = (new_runtime, mode_bits)
            output_name = 'artifacts/' + output
            if output_name not in candidate['files']:
                raise ValueError('composed archive is absent from complete candidate')
            consumed.add(output_name)
            observed_description, observed_members, observed_directories = _members(directory / output_name)
            if observed_members != expected_members or observed_directories != directories:
                raise ValueError('composed archive changed retained runtime closure, member bytes or modes')
            expected_product = {'id': identity, 'archive': output_name,
                'sha256': archive.digest(directory / output_name), 'files': observed_description['files'],
                'modes': _mode_inventory(observed_members), 'runtime_member': runtime,
                'kernel_descriptor_sha256': selected['descriptor']['sha256'],
                'original_source_tree_sha256': original_source['tree_sha256'],
                'kernel_prefix_sha256': container.digest(existing.prefix), 'kernel_prefix_length': len(existing.prefix),
                'carrier': descriptor['carrier'], 'profile': descriptor['profile'], 'abi': descriptor['abi'],
                'capabilities': descriptor['capabilities'], 'services': descriptor['services'],
                'directories': observed_directories, 'runtime_sha256': container.digest(new_runtime),
                'runtime_size': len(new_runtime)}
            if not _same_json(product, expected_product):
                raise ValueError('composition artifact metadata differs from verified member bytes')
    if consumed != set(candidate['files']):
        raise ValueError('unexplained or omitted candidate composition inputs')
    if verify_candidate(directory, candidate_sha256) != candidate or identities() != before:
        raise ValueError('candidate changed during semantic subject verification')
    return {'candidate_sha256': candidate_sha256, 'composition_sha256': container.digest(composition_bytes),
            'selection_sha256': container.digest(selection_bytes), 'candidate': candidate,
            'selection': selection, 'composition': composition}


def recover(directory, candidate_sha256, output):
    directory = container._ordinary_path(directory, directory=True)
    output = Path(os.path.abspath(os.fspath(output)))
    if output == directory or directory in output.parents:
        raise ValueError('recovery output must be outside the pinned original candidate')
    verified = verify_candidate(directory, candidate_sha256)

    def entry_identities():
        return {str(path.relative_to(directory)): container._identity(path.lstat())
                for path in [directory, *sorted(directory.rglob('*'))]}

    frozen = entry_identities()

    def revalidate_original():
        # Include unreferenced evidence/metadata and directory entries, not only
        # the selected input blobs. Both exact bytes and physical identities must
        # still match before reservation and again before the validity marker.
        if verify_candidate(directory, candidate_sha256) != verified or entry_identities() != frozen:
            raise ValueError('original candidate changed during recomposition')

    return prepare_release(directory / 'selection.json', output, expected_candidate_sha256=candidate_sha256,
                           before_publish=revalidate_original)


def fetch_inputs(repository, tag, release_id, source_commit, asset_name, asset_sha256, selection_sha256, output,
                 *, remote=None):
    """Authenticated read-only acquisition of one immutable pinned input group.

    The caller supplies source coordinates explicitly. GH_TOKEN belongs only to
    this acquisition stage; no downstream publication identity is inferred.
    """
    from github_release import Remote
    remote = remote or Remote(repository)
    if remote.repository != repository:
        raise ValueError('source repository differs from explicit acquisition repository')
    _name(asset_name)
    _sha(asset_sha256)
    _sha(selection_sha256)
    if type(release_id) is not int or release_id <= 0:
        raise ValueError('source release requires an exact positive release ID')
    if type(source_commit) is not str or not re.fullmatch(r'[0-9a-f]{40}', source_commit):
        raise ValueError('source release requires an exact commit identity')
    output = Path(os.path.abspath(os.fspath(output)))
    container._ordinary_path(output.parent, directory=True)
    if output.exists() or output.is_symlink():
        raise ValueError('retained acquisition output must be new')
    info = remote.by_id(release_id, tag)
    if info['draft'] or remote.reference(tag) != source_commit:
        raise ValueError('source release must be published at the pinned direct commit tag')
    # Keep Remote.private unset so its existing authenticated API download path
    # is used even when the source repository itself is public.
    assets = remote.assets(info)
    if asset_name not in assets:
        raise ValueError('pinned retained input-group asset is absent')
    row = assets[asset_name]
    if (type(row['id']) is not int or row['id'] <= 0 or row['name'] != asset_name
            or type(row['size']) is not int or not 0 < row['size'] <= MAX_INPUT
            or row['digest'] != 'sha256:' + asset_sha256):
        raise ValueError('retained input-group asset differs from pin or exceeds limit')
    origin = {'kind': 'local'}
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        fields = {'repository': 'GITHUB_REPOSITORY', 'workflow_ref': 'GITHUB_WORKFLOW_REF',
                  'workflow_sha': 'GITHUB_WORKFLOW_SHA', 'run_id': 'GITHUB_RUN_ID',
                  'run_attempt': 'GITHUB_RUN_ATTEMPT', 'job': 'GITHUB_JOB',
                  'runner_environment': 'RUNNER_ENVIRONMENT'}
        origin = {'kind': 'github-actions', **{key: os.environ.get(name, '') for key, name in fields.items()}}
        if (any(not value for key, value in origin.items())
                or not re.fullmatch(r'[0-9a-f]{40}', origin['workflow_sha'])
                or any(not re.fullmatch(r'[1-9][0-9]*', origin[key]) for key in ('run_id', 'run_attempt'))
                or origin['runner_environment'] not in ('github-hosted', 'self-hosted')):
            raise ValueError('incomplete actual GitHub Actions acquisition origin')
    with tempfile.TemporaryDirectory(prefix='.appended-fetch-', dir=output.parent) as temporary:
        workspace = Path(temporary)
        downloaded = workspace / asset_name
        remote.download(row, downloaded, asset_sha256)
        # Whole archive SHA is checked before any extraction. Existing portable
        # path/link/alias validation runs before creating extracted members.
        if archive.digest(downloaded) != asset_sha256:
            raise ValueError('downloaded retained group differs from pinned bytes')
        group = workspace / 'group'
        archive.extract(downloaded, group, max_bytes=MAX_INPUT)
        selection = container._snapshot(group / 'selection.json', MAX_JSON)
        if container.digest(selection.content) != selection_sha256:
            raise ValueError('downloaded selection differs from independently pinned SHA-256')
        group_files = _files(group)
        def group_entries():
            result = {}
            for path in [group, *sorted(group.rglob('*'))]:
                state = path.lstat()
                # Exclusive publication hardlinks these exact files. Their
                # ctime/link count changes legitimately, unlike inode, mode,
                # mtime, size or the complete hash inventory checked below.
                result[path.relative_to(group).as_posix()] = (state.st_dev, state.st_ino, state.st_size,
                                                            state.st_mtime_ns, state.st_mode)
            return result

        group_identities = group_entries()

        def unchanged_group():
            if group_entries() != group_identities or not _same_json(_files(group), group_files):
                raise ValueError('retained acquisition group changed before publication')

        remote.unchanged(tag, info, assets, expected_ref=source_commit)
        _publish_tree(group, output, precondition=unchanged_group)
        unchanged_group()
    # Save this returned document alongside the frozen candidate. It records
    # observed acquisition coordinates separately from the immutable input group;
    # it is neither kernel qualification nor an independent attestation.
    return {'schema_version': 1, 'kind': 'foundation-appended-acquisition',
            'source_repository': repository, 'source_tag': tag, 'release_id': release_id,
            'source_commit': source_commit, 'asset_name': asset_name, 'asset_id': row['id'],
            'asset_size': row['size'], 'asset_sha256': asset_sha256,
            'selection_sha256': selection_sha256, 'group_files': group_files, 'origin': origin}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    prepare = actions.add_parser('prepare-release')
    prepare.add_argument('--selection', type=Path, required=True)
    prepare.add_argument('--output', type=Path, required=True)
    for action in ('verify-candidate', 'verify-composition', 'recover'):
        child = actions.add_parser(action)
        child.add_argument('--input', type=Path, required=True)
        child.add_argument('--candidate-sha256', required=True)
        if action == 'recover':
            child.add_argument('--output', type=Path, required=True)
    fetch = actions.add_parser('fetch-inputs')
    fetch.add_argument('--source-repository', required=True)
    fetch.add_argument('--source-tag', required=True)
    fetch.add_argument('--source-release-id', type=int, required=True)
    fetch.add_argument('--source-commit', required=True)
    fetch.add_argument('--asset', required=True)
    fetch.add_argument('--asset-sha256', required=True)
    fetch.add_argument('--selection-sha256', required=True)
    fetch.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare-release':
            result = prepare_release(args.selection, args.output)
        elif args.action == 'verify-candidate':
            result = verify_candidate(args.input, args.candidate_sha256)
        elif args.action == 'verify-composition':
            result = verify_composition_subject(args.input, args.candidate_sha256)
        elif args.action == 'recover':
            result = recover(args.input, args.candidate_sha256, args.output)
        else:
            result = fetch_inputs(args.source_repository, args.source_tag, args.source_release_id, args.source_commit,
                                  args.asset, args.asset_sha256, args.selection_sha256, args.output)
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(2, 'appended release: ' + str(error) + '\n')
    print(container.canonical_json(result).decode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
