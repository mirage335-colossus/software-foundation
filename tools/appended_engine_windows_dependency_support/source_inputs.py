"""Fixed thirteen-archive projection, held source trees and owned source copies.

The actual B instance comes only from the same genuine issuer's Origin getter.
Only its four bounded structural stream helpers are used.  Engine, handoff and
157-file replay authorities are not used.  Importing this module performs no I/O.
"""
import copy
import hashlib
import math
from pathlib import Path, PurePosixPath
import sys
import time
import types

MAX_FILES = 65536
MAX_ARCHIVE = 4 * 1024**3
MAX_EXPANDED = 32 * 1024**3
MAX_MEMBER = 256 * 1024**2
_SOURCES = {}


class HeldSupplierSources:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Only the complete actual supplier-source factory issues tokens')


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _inputs():
    return _owner()._support_module('current_inputs')


def _base():
    return _owner()._support_module('supplier_factory_contract_base')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _seal(state):
    encode = _base()._source_encoded
    return {'mode': state['mode'],
        'projections': {name: _sha(encode(row)) for name, row in state['projections'].items()},
        'bindings': _sha(encode(state['bindings'])),
        'protected_paths': _sha(encode(state['protected_paths']))}


def _issue(inputs, projections, bindings, protected, mode):
    _inputs()._lease_for_controller(inputs)['held'].check()
    token = object.__new__(HeldSupplierSources)
    state = {'inputs': inputs, 'projections': projections, 'bindings': bindings,
        'protected_paths': protected, 'materialized': False, 'revoked': False, 'mode': mode}
    state['seal'] = _seal(state)
    _SOURCES[token] = state
    return token


def _relative(name):
    return _base()._relative(name)


def _metadata_equal(left, right):
    if _base()._source_encoded(left) != _base()._source_encoded(right):
        raise ValueError('Complete original supplier projections differ')


def projection(value, supplier, component):
    """Pure finite supplier declaration; this does not admit any input bytes."""
    b, h = _base(), _base()._proof().legacy()
    b._source_preflight(value)
    b._fields(value, ('schema_version', 'kind', 'target', 'supplier', 'identity',
        'source_root', 'files', 'directories', 'notices', 'transformations'), 'supplier projection')
    for actual, expected in ((value['schema_version'], 1),
            (value['kind'], 'foundation-native-engine-windows-dependency-source-replay-v1'),
            (value['target'], b._proof().TARGET), (value['supplier'], supplier),
            (value['identity'], component), (value['transformations'], [])):
        b._equal(actual, expected, 'original unmodified supplier declaration')
    b._path(value['source_root'])
    files, directories = value['files'], value['directories']
    if (type(files) is not dict or not 1 <= len(files) <= MAX_FILES
            or type(directories) is not list or len(directories) > MAX_FILES
            or directories != sorted(set(directories))):
        raise ValueError('Finite complete supplier source tree required')
    kinds, total = {}, 0
    for name in directories:
        _relative(name)
        if name.casefold() in kinds:
            raise ValueError('Source directory aliases')
        kinds[name.casefold()] = (name, 'directory')
    for name, row in files.items():
        _relative(name)
        b._fields(row, ('sha256', 'bytes'), 'source file')
        h._pin(row['sha256'], 'source member')
        h._integer(row['bytes'], 'source member bytes', 0, MAX_MEMBER)
        total += row['bytes']
        if name.casefold() in kinds or total > MAX_EXPANDED:
            raise ValueError('Source file aliases or expanded byte bound')
        kinds[name.casefold()] = (name, 'file')
    for name, kind in kinds.values():
        for parent in PurePosixPath(name).parents:
            if str(parent) != '.' and kinds.get(str(parent).casefold()) != (str(parent), 'directory'):
                raise ValueError('Complete source parent directories required')
    notices = value['notices']
    if (type(notices) is not list or not 1 <= len(notices) <= 256
            or notices != sorted(set(notices)) or any(name not in files for name in notices)):
        raise ValueError('Exact original source notice members required')
    subject = {'root': value['source_root'], 'files': files, 'directories': directories}
    return {'source_subject_sha256': _sha(b._source_encoded(subject)),
        'notice_subject_sha256': _sha(b._source_encoded({name: files[name] for name in notices}))}


def _archive_projection(stream, component, kernel, deadline):
    """One frozen stream and bounded structural decode; no alternate parser."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError('Initial source admission lifetime exhausted')
    limits = {'seconds': min(60, math.ceil(remaining)), 'maximum_archive_bytes': MAX_ARCHIVE,
        'maximum_expanded_bytes': MAX_EXPANDED, 'maximum_members': 2 * MAX_FILES,
        'maximum_member_bytes': MAX_MEMBER, 'maximum_patch_bytes': 1024**2}
    budget = kernel._Budget(limits)
    budget.deadline = min(budget.deadline, deadline)
    bounded = kernel._BoundedStream(stream, component['bytes'], budget)
    files, directories, seen, root_seen = {}, set(), set(), False
    prefix = component['strip_prefix']
    for name, kind, mode, size, link, member in kernel._archive_entries(bounded, component['format'], budget):
        if time.monotonic() >= deadline:
            raise ValueError('Original archive decoding deadline exhausted')
        budget.member(size)  # Before any member allocation/read.
        if kind not in ('file', 'directory'):
            raise ValueError('Only ordinary supplier archive files/directories are admitted')
        directory = kind == 'directory'
        if directory and size:
            raise ValueError('Supplier archive directories must have empty payloads')
        if directory and name in (prefix, prefix + '/'):
            if root_seen:
                raise ValueError('Duplicate supplier archive strip root')
            root_seen = True
            continue
        if directory and name.endswith('/'):
            name = name[:-1]
        if not name.startswith(prefix + '/'):
            raise ValueError('Archive member outside exact retained strip prefix')
        relative = _relative(name[len(prefix) + 1:])
        if relative.casefold() in seen:
            raise ValueError('Duplicate or aliased supplier archive member')
        seen.add(relative.casefold())
        for parent in PurePosixPath(relative).parents:
            if str(parent) != '.':
                directories.add(str(parent))
        if directory:
            directories.add(relative)
        else:
            if len(files) >= MAX_FILES:
                raise ValueError('Supplier regular-file count exceeds bound')
            pin, unused = kernel._read_member(member, size, False, budget)
            files[relative] = {'sha256': pin, 'bytes': size}
    if time.monotonic() >= deadline:
        raise ValueError('Original archive decoding deadline exhausted')
    if not files or len(directories) > MAX_FILES:
        raise ValueError('Empty or overbound original source archive')
    return {'files': files, 'directories': sorted(directories)}


def admit_sources(current_inputs):
    """Own H-before-D original13 archive/tree admission through genuine leases."""
    inputs, b = _inputs(), _base()
    lease = inputs._lease_for_controller(current_inputs)
    held, selection = lease['held'], lease['selection']
    kernel = lease['issuer'].originals_module()._capture_source_provider()
    components = b._profile()['components']
    roots = [selection['output'], lease['identity']['system_root'],
        *[row['root'] for row in lease['identity']['inventories'].values()]]
    projections, bindings, protected = {}, {}, []
    for supplier in b._proof().legacy().SOURCES:
        selected, component = selection['sources'][supplier], components[supplier]
        raw = held.read_ref(selected['replay'], inputs.MAX_INVENTORY)
        value = inputs._document(raw, selected['replay'], inputs.MAX_INVENTORY)
        facts = projection(value, supplier, component)
        root = value['source_root']
        if any(root.casefold() == other.casefold() or root.casefold().startswith(other.casefold() + '/')
                or other.casefold().startswith(root.casefold() + '/') for other in roots):
            raise ValueError('Supplier retained roots overlap original inputs/output')
        roots.append(root)
        if not 1 <= component['bytes'] <= MAX_ARCHIVE:
            raise ValueError('Fixed original source archive exceeds supported size')
        archive_ref = selected['archive']
        if archive_ref['sha256'] != component['sha256']:
            raise ValueError('Selected archive differs from the fixed supplier identity')
        parent, leaf = archive_ref['path'].rsplit('/', 1)
        owner = held._open(parent)
        archive_deadline = min(lease['deadline'], time.monotonic() + 60)
        stream = owner.open_archive(leaf, expected={'sha256': component['sha256'],
            'bytes': component['bytes'], 'mode': 0o644})
        try:
            digest, count = hashlib.sha256(), 0
            while True:
                held._time()
                if time.monotonic() >= archive_deadline:
                    raise ValueError('Original compressed archive hashing deadline exhausted')
                chunk = stream.read(1024**2)
                if not chunk:
                    break
                count += len(chunk)
                if count > component['bytes']:
                    raise ValueError('Original compressed archive exceeded exact EOF')
                digest.update(chunk)
            if count != component['bytes'] or digest.hexdigest() != component['sha256']:
                raise ValueError('Original compressed supplier archive pin differs')
            stream.seek(0)
            actual = _archive_projection(stream, component, kernel, archive_deadline)
        finally:
            stream.close()  # Actual owner keeps the original immutable capture.
        _metadata_equal(actual, {name: value[name] for name in ('files', 'directories')})
        held.hold_tree({'root': root, **actual})
        projections[supplier] = copy.deepcopy(value)
        bindings[supplier] = {'version': component['version'], 'archive': {
            'path': archive_ref['path'], **{name: component[name] for name in
                ('sha256', 'bytes', 'format', 'strip_prefix')}},
            'replay': copy.deepcopy(selected['replay']), **facts}
        protected += [root, archive_ref['path'], selected['replay']['path']]
    if lease['originals'] is not None:
        refs = [row[key] for row in selection['sources'].values() for key in ('archive', 'replay')]
        lease['issuer'].originals_module().require_original_membership(lease['originals'], refs)
    held.check()
    return _issue(current_inputs, projections, bindings, protected, 'fresh-owned')


def admit_source_declarations(current_inputs):
    """Hold original retained projection metadata for read-only reconstruction.

    Archive pins and original source subjects remain exact fixed declarations.
    No archive or supplier tree body is opened, and this private mode can never
    materialize sources or obtain a native execution Workspace.
    """
    inputs = _inputs()
    lease = inputs._lease_for_controller(current_inputs)
    if lease['originals'] is None:
        raise ValueError('Read-only source metadata requires genuine retained D Origin')
    profile = _base()._profile()
    projections, bindings, protected = {}, {}, []
    selected = lease['selection']['sources']
    origin = lease['issuer'].originals_module()
    origin.require_original_membership(lease['originals'],
        [row['replay'] for row in selected.values()])
    for supplier, component in profile['components'].items():
        item = selected[supplier]
        raw = lease['held'].read_ref(item['replay'], inputs.MAX_INVENTORY)
        value = inputs._document(raw, item['replay'], inputs.MAX_INVENTORY)
        facts = projection(value, supplier, component)
        if item['archive']['sha256'] != component['sha256']:
            raise ValueError('Retained archive declaration differs from fixed supplier pin')
        projections[supplier] = copy.deepcopy(value)
        bindings[supplier] = {'version': component['version'], 'archive': {
            'path': item['archive']['path'], **{name: component[name] for name in
                ('sha256', 'bytes', 'format', 'strip_prefix')}},
            'replay': copy.deepcopy(item['replay']), **facts}
        protected.append(item['replay']['path'])
    return _issue(current_inputs, projections, bindings, protected, 'retained-read-only')


def _state(value):
    if type(value) is not HeldSupplierSources or value not in _SOURCES:
        raise ValueError('Genuine complete original supplier sources required')
    state = _SOURCES[value]
    if state['revoked'] or state.get('mode') not in ('fresh-owned', 'retained-read-only'):
        raise ValueError('Supplier source capability is revoked')
    if _seal(state) != state.get('seal'):
        raise ValueError('Original supplier source declarations changed')
    lease = _inputs()._lease_for_controller(state['inputs'])
    return state, lease


def require_sources(value):
    state, lease = _state(value)
    return copy.deepcopy({name: state[name] for name in
        ('projections', 'bindings', 'protected_paths', 'materialized', 'mode')})


def materialize_sources(value, context):
    """Copy original files only after the same real initial probe compilation."""
    state, lease = _state(value)
    c = _owner()
    if type(context) is not c._NativeContext or context not in c._NATIVE_CONTEXTS:
        raise ValueError('Actual native source-bound controller required')
    if (state['mode'] != 'fresh-owned' or context.held is not lease['held'] or context.workspace is not
            c._NATIVE_CONTEXTS[context]['workspace'] or context.next_index or context.observations
            or type(context.probe) is not c._NativeProbe or context.probe not in c._NATIVE_PROBES
            or state['materialized']):
        raise ValueError('One source materialization after the original initial compile required')
    context._check()
    workspace = context.workspace
    probe = c._NATIVE_PROBES[context.probe]
    operation = probe['operation']
    if (probe['context'] is not context or probe['workspace'] is not workspace
            or not any(item is operation['joined'] for item in workspace.joined)
            or not any(item is operation['log'] for item in workspace.logs)
            or operation['log']._workspace is not workspace
            or operation['log']._state != 'sealed'):
        raise ValueError('Same actual closed initial compile/log association required')
    if operation['joined'].as_dict() != operation['joined_facts']:
        raise ValueError('Original initial compile JoinedStage changed')
    if (operation['joined_facts'].get('returncode') != 0
            or operation['joined_facts'].get('process_tree_closed') is not True):
        raise ValueError('Actual successful closed initial compile required')
    # Reopen the exact compiled object before any source tree is published.
    context._capture({'path': probe['plan']['object_path'],
        'sha256': probe['inspection']['object_sha256']}, len(probe['object']['raw']),
        identity=probe['object']['physical'])
    try:
        workspace.mkdir_new('sources')
        for supplier, value in state['projections'].items():
            prefix = 'sources/' + supplier
            workspace.mkdir_new(prefix)
            for directory in sorted(value['directories'], key=lambda name: (name.count('/'), name)):
                workspace.mkdir_new(prefix + '/' + directory)
            tree = lease['held'].trees[value['source_root'].casefold()]['tree']
            for name, row in value['files'].items():
                context._check()
                stream = tree.open_file(name)
                try:
                    raw = stream.read(row['bytes'] + 1)
                    if len(raw) != row['bytes'] or _sha(raw) != row['sha256']:
                        raise ValueError('Held original source changed before owned copy')
                finally:
                    stream.close()
                actual = workspace.publish_bytes_new(prefix + '/' + name, raw)
                if actual['sha256'] != row['sha256'] or actual['bytes'] != row['bytes']:
                    raise ValueError('Actual owned source copy differs')
            # Keep the exact owned original source files and all names locked
            # through supplier stages; generated outputs belong in build roots.
            lease['held'].hold_tree({'root': workspace.output + '/' + prefix,
                'files': value['files'], 'directories': value['directories']})
        state['materialized'] = True
        context._check()
    except BaseException as error:
        state['revoked'] = True
        context._revoke(error)
        raise
