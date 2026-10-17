"""Private finite D3 stage controller. No native activation is released.

The fixed factory is source-gated, not replaceable by a caller registration.
Inert contexts and capabilities have separate exact types and registries.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import threading
import types


REQUEST_KIND = 'foundation-windows-dependency-probe-production-selection-v2'
RESULT_KIND = 'foundation-windows-dependency-with-probe-object-v2'
PHASES = {'configure': ('configure', 'configure_seconds'),
    'build-tool': ('build', 'build_seconds'),
    'generate': ('build', 'configure_seconds'), 'build': ('build', 'build_seconds'),
    'install': ('install', 'install_seconds'), 'probe': ('probe', 'probe_seconds')}
PURE_W1_SHA256 = 'ba66eaa2d88912ab4ae5277cc56f0616384a9c38241f8c1ad374b38a40f0747f'
SOURCE_GAPS = (
    'windows-dependency-v2-reviewed-supplier-registry',
    'windows-dependency-v2-cap-enabled-publication-source',
    'windows-dependency-v2-original-program-observation-authority',
    'windows-dependency-v2-original-managed-runtime-authority',
    'windows-dependency-v2-produced-program-runtime-authority',
    'windows-dependency-v2-generated-input-bindings',
)
# These are reviewed source bindings, never request fields or status switches.
# None means no production activation and no output mutation is possible.
_CAP_PUBLICATION_SHA256 = None
_SUPPLIER_FACTORY_SHA256 = None
_H2_ISSUER_SHA256 = None
_W2_SHA256 = '647186156cfb0289da9e95fa13d9f99cc70264ac7a05e62410585b20c7246717'
_H2D2_PROOF_SHA256 = 'a032b4f632e3770bd6b1daeef28a95759717483aabe8a549f27b8710ea21d55a'
_NATIVE_INSPECTION_SHA256 = '9b91a9a47598e37650c1d6f54ab64402b028452baf58ddfe9a321cad88c071e6'
_NATIVE_FACTORIES = {}
_NATIVE_CONTEXTS = {}
_NATIVE_PRODUCTS = {}
_NATIVE_PROBES = {}
_NATIVE_RESULTS = {}
_FIXTURE_CONTEXTS = {}
_FIXTURE_PRODUCTS = {}
_FIXTURE_PROBES = {}
_RETAINED_UNCERTAIN = []
_W = None
_SOURCE_MODULES = {}
_SOURCE_LOCK = threading.RLock()
_SOURCE_BLOCKERS = []
_CORE_NAME = '_foundation_windows_h2d3_controller_core_v1'
_ENTRY_NAME = 'appended_engine_windows_dependencies'
_ENTRY_OWNER = globals().get('_dependency_entry_owner')
# Filled only with complete reviewed maintained child postimages.
_SUPPORT_SOURCES = {
    'selection': ('selection.py', '9e67b3c513d14172423ce832d182268f3e9b4a12cc4f1aff76462fa1344d2df7', 8590, '_foundation_windows_dependency_selection_v1'),
    'current_inputs': ('current_inputs.py', 'c6eb35a56697ae18640361ad8629be45fbf5f610314480cdd0b36c8e0b6fe166', 33393, '_foundation_windows_dependency_current_inputs_v1'),
    'generated_inputs': ('generated_inputs.py', 'b18fd8a4efc53e089f13d5377246abc61077a23d09e92ecd254908fef5091791', 27794, '_foundation_windows_dependency_generated_inputs_v1'),
    'supplier_factory_contract': ('supplier_factory_contract.py', '215780ea5181ea39631918ce20b22cd2df2ce0ac2898104bc6d9765c3b37edbb', 8195, '_foundation_windows_supplier_factory_contract_v1'),
    'supplier_factory_contract_base': ('supplier_factory_contract_base.py', 'd0afcc6c1e4ae8c64dd2e37d4b363b754ea2e821b8ddf8c8e9047a8a749b25a3', 23221, '_foundation_windows_dependency_supplier_factory_contract_base_v1'),
    'supplier_registry': ('supplier_registry.py', 'ef0af49aaea9ccfcd6ce52d46cf4ff877e6fa9a99e5eb048684b65c7c870f26f', 12470, '_foundation_windows_dependency_supplier_registry_v1'),
    'producer': ('producer.py', 'ffac314be752137b5a20f9af03ed26b431c83337f5626099757ce3bcf629820a', 39167, '_foundation_windows_dependency_producer_v1'),
    'retained_dependency': ('retained_dependency.py', '4621bd52b5c71a2161564d67aab0ab215cc60f06be150f355a6b960d87233009', 31288, '_foundation_windows_dependency_retained_dependency_v1'),
    'source_inputs': ('source_inputs.py', '0f2963b679bac9085f1dd0d1277ff96b9f72fe11c909f42d0a724bc419a0112a', 17434, '_foundation_windows_dependency_source_inputs_v1'),
    'library_interfaces': ('library_interfaces.py', '382beb825fa73e17ce7a89287094a54f99342e2da294c2ad8aab2d136942e516', 66393, '_foundation_windows_dependency_library_interfaces_v1'),
    'dependency_publication': ('dependency_publication.py', '61da86d0a2615058c17215c590cf654cc74ca061b017a545823ca1825b4204cd', 33092, '_foundation_windows_dependency_dependency_publication_v1'),
}
MAX_RUNTIME_DLLS = 128
MAX_RUNTIME_DLL_BYTES = 64 * 1024**2
MAX_RUNTIME_BYTES = 256 * 1024**2
RUNTIME_KIND = 'foundation-windows-produced-native-runtime-v1'


class MissingSource(ValueError):
    def __init__(self, names):
        self.missing = tuple(names)
        super().__init__(', '.join(self.missing))


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _self():
    module = sys.modules.get(__name__)
    if __name__ != _CORE_NAME or type(module) is not types.ModuleType or vars(module) is not globals():
        raise ValueError('Actual verified controller bootstrap required')
    return module


def _dependency_entry():
    """Return only this Core's original successfully loaded facade owner."""
    core = _self()
    owner = _ENTRY_OWNER
    if (type(owner) is not types.ModuleType or owner.__name__ != _ENTRY_NAME
            or globals().get('_dependency_entry_owner') is not owner
            or sys.modules.get(_ENTRY_NAME) is not owner):
        raise ValueError('Actual dependency entry owner required')
    cache = vars(owner).get('_SOURCE_CACHE')
    row = cache.get(_CORE_NAME) if type(cache) is dict else None
    if (type(row) is not dict or row.get('module') is not core
            or row.get('path') != str(Path(__file__).resolve())
            or type(row.get('pin')) is not str or len(row['pin']) != 64):
        raise ValueError('Complete original dependency entry/Core association required')
    return owner


def _require_source_child(name, module):
    with _SOURCE_LOCK:
        entry = _SOURCE_MODULES.get(name)
        if (entry is None or entry.get('state') not in ('executing', 'loaded')
                or entry['module'] is not module or sys.modules.get(name) is not module
                or vars(module).get('_support_source_owner') is not _self()):
            raise ValueError('Original verified controller child required')
        return _self()


def _support_module(fixed_role):
    roles = ('controller', 'selection', 'current_inputs', 'generated_inputs',
        'supplier_factory_contract', 'supplier_factory_contract_base', 'supplier_registry',
        'producer', 'retained_dependency', 'source_inputs', 'library_interfaces',
        'dependency_publication')
    if type(fixed_role) is not str or fixed_role not in roles:
        raise ValueError('Closed maintained support role required')
    if fixed_role == 'controller':
        return _self()
    row = _SUPPORT_SOURCES.get(fixed_role)
    if row is None:
        raise MissingSource(('windows-dependency-maintained-' + fixed_role.replace('_', '-') + '-source-binding',))
    filename, pin, size, name = row
    path = Path(__file__).resolve().with_name(filename)
    module = _load_verified_source(path, pin, name, maximum=max(size, 1))
    if path.stat().st_size != size:
        raise ValueError('Maintained support source size differs')
    return module


def _load_verified_source(path, pin, name, maximum=256 * 1024):
    """One cache and atomic reservation; execute only the captured pinned bytes."""
    path = Path(path).resolve()
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if not raw or len(raw) > maximum or _hash(raw) != pin:
        raise ValueError('Reviewed module source changed')
    with _SOURCE_LOCK:
        previous = _SOURCE_MODULES.get(name)
        if previous is not None:
            if (previous['path'] != str(path) or previous['pin'] != pin
                    or sys.modules.get(name) is not previous['module']
                    or previous.get('state') != 'loaded'):
                raise ValueError('Verified module cache is changed, incomplete or failed')
            return previous['module']
        module = types.ModuleType(name)
        module.__file__ = str(path)
        module._support_source_owner = _self()
        occupied = sys.modules.setdefault(name, module)
        if occupied is not module:
            raise ValueError('Unknown occupied verified module name')
        entry = {'path': str(path), 'pin': pin, 'module': module, 'state': 'executing'}
        _SOURCE_MODULES[name] = entry
        try:
            if sys.modules.get(name) is not module:
                raise ValueError('Reserved source module slot changed before execution')
            exec(compile(raw, str(path), 'exec'), vars(module))
            if sys.modules.get(name) is not module:
                raise ValueError('Reserved source module slot changed during execution')
            entry['state'] = 'loaded'
        except BaseException as error:
            entry['state'] = 'failed'
            entry['failure'] = type(error).__name__ + ': ' + str(error)
            _SOURCE_BLOCKERS.append(entry)
            # Retain our failed reservation. Never replace/delete a foreign slot.
            raise
        return module


def _pure():
    global _W
    if _W is None:
        path = Path(__file__).resolve().with_name('probe_core.py')
        # Each controller instance owns its pure helper cache. Native original
        # authority is shared only through its separately fixed owner accessor.
        name = '_d2_common_w_' + PURE_W1_SHA256[:16] + '_' + __name__.replace('.', '_')
        _W = _load_verified_source(path, PURE_W1_SHA256, name, 128 * 1024)
    return _W


def _equal(actual, expected, label):
    if _pure().encoded(actual) != _pure().encoded(expected):
        raise ValueError(label + ' differs')


def _reference(value):
    _pure()._ref(value)
    return copy.deepcopy(value)


def _inventory_encoded(value):
    """The bounded inventory domain retains the contract's canonical bytes."""
    if (type(value) is not dict or type(value.get('files')) is not dict
            or len(value['files']) > 65536 or type(value.get('directories')) is not list
            or len(value['directories']) > 65536):
        raise ValueError('Finite complete actual output inventory required')
    raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
        allow_nan=False) + '\n').encode('ascii')
    if len(raw) > 32 * 1024**2:
        raise ValueError('Complete output inventory metadata exceeds byte bound')
    return raw


def _request(value):
    w = _pure()
    w._fields(value, ('schema_version', 'kind', 'target', 'dependency_selection',
        'input_qualification', 'version_selection', 'maintained_source'), 'D2 production request')
    _equal(value['schema_version'], 2, 'request schema')
    _equal(value['kind'], REQUEST_KIND, 'request kind')
    _equal(value['target'], w.TARGET, 'request target')
    paths = set()
    for key in ('dependency_selection', 'input_qualification', 'version_selection', 'maintained_source'):
        item = _reference(value[key])
        if item['path'].casefold() in paths:
            raise ValueError('Request reference aliases are forbidden')
        paths.add(item['path'].casefold())
    _equal(value['maintained_source']['sha256'], w.SOURCE_SHA256, 'fixed probe source')
    if not value['maintained_source']['path'].endswith(
            '/recipes/webkitwasm-native-deps-windows-x86_64-v1/static-closure-probe.cpp'):
        raise ValueError('Fixed maintained probe path required')
    return copy.deepcopy(value)


class IssuedDependencyV2:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Only the complete native D2 factory issues results')


class _Factory:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Only the fixed source-bound factory issues registration')


class _NativeProduct:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Only an earlier actual closed producer issues a program')


class _FixtureProduct:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Use the inert fixture harness')


class _NativeProbe:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Only the same actual closed compile issues its object')


class _FixtureProbe:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Use the inert fixture compile')


def require_dependency_v2(value):
    if type(value) is not IssuedDependencyV2 or value not in _NATIVE_RESULTS:
        raise ValueError('Original complete D2 native-issued result required')
    return json.loads(_NATIVE_RESULTS[value])


def produce_dependency_v2(request_ref):
    """No selected body or output is touched while source methods are absent."""
    _reference(request_ref)
    if os.name != 'nt':
        raise ValueError('Native Windows is required')
    # The real factory must bind one original deadline before reading selection,
    # run the standalone H2 observations first, then create a fresh D Workspace.
    # No request/status/dictionary can manufacture its registered capability.
    raise MissingSource(SOURCE_GAPS)


def _phase_limits(limits, operation, overall_deadline, now):
    if operation not in PHASES:
        raise ValueError('Unregistered D2 operation')
    phase, key = PHASES[operation]
    seconds = limits.get(key)
    if type(seconds) is not int or not 1 <= seconds <= 86400:
        raise ValueError('Finite strict-integer stage duration required')
    if (type(overall_deadline) not in (int, float) or type(now) not in (int, float)
            or not math.isfinite(overall_deadline) or not math.isfinite(now)):
        raise ValueError('Finite original deadline required')
    remaining = int((overall_deadline - now) * 1000)
    if remaining < 1:
        raise ValueError('Original operation deadline exhausted')
    result = {'wall_milliseconds': min(seconds * 1000, remaining)}
    for name, ceiling in (('maximum_processes', 64), ('maximum_output_bytes', 1024**4),
                          ('maximum_log_bytes', 128 * 1024**2)):
        value = limits.get(name)
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError('Finite strict-integer ' + name + ' required')
        result[name] = value
    return phase, result


def _runtime_layout(program_ref, source_policy, *, producer_root):
    w = _pure()
    program_ref = _reference(program_ref)
    w._path(producer_root)
    if not program_ref['path'].startswith(producer_root + '/'):
        raise ValueError('Produced program escapes its fixed registered root')
    w._fields(source_policy, ('libraries',), 'produced runtime Source policy')
    declared = source_policy['libraries']
    if type(declared) is not dict or len(declared) > MAX_RUNTIME_DLLS:
        raise ValueError('Finite fixed produced runtime DLL map required')
    directory, result, paths = program_ref['path'].rsplit('/', 1)[0], {}, set()
    for name, relative in declared.items():
        if (type(name) is not str or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,127}\.dll', name) is None
                or name in _native_inspection().SYSTEM_IMPORTS or type(relative) is not str or not relative
                or len(relative) > 2048 or relative.startswith('/') or ':' in relative or '\\' in relative):
            raise ValueError('Exact portable non-system Source DLL mapping required')
        path = producer_root + '/' + relative
        w._path(path)
        if path.rsplit('/', 1) != [directory, name] or path.casefold() in paths:
            raise ValueError('Produced DLL must have its exact import basename beside the executable')
        paths.add(path.casefold())
        result[name] = path
    return result


def _runtime_document(program_ref, source_policy, program_raw, libraries,
                      system_identity, *, producer_root):
    """Pure bounded Source runtime projection; supplied metadata is no authority.

    Only the fixed beside-executable DLL layout is implemented. Native callers
    supply genuine held current bytes; retained callers independently reopen the
    exact original bodies. The document has no D/G2/output-snapshot backedge.
    """
    w, inspector = _pure(), _native_inspection()
    program_ref = _reference(program_ref)
    layout = _runtime_layout(program_ref, source_policy, producer_root=producer_root)
    if (type(program_raw) is not bytes or not 64 <= len(program_raw) <= MAX_RUNTIME_BYTES
            or _hash(program_raw) != program_ref['sha256']):
        raise ValueError('Exact bounded produced program bytes required')
    declared = source_policy['libraries']
    if type(libraries) is not dict or set(libraries) != set(declared):
        raise ValueError('Exact complete original produced DLL bodies required')
    w._fields(system_identity, ('root', 'windows_version'), 'produced runtime OS identity')
    w._path(system_identity['root'])
    version = system_identity['windows_version']
    if type(version) is not list or len(version) != 3:
        raise ValueError('Exact actual OS version triple required')
    for component in version:
        w._int(component, 'produced runtime OS version', 0, 2**31 - 1)
    system_names = inspector.SYSTEM_IMPORTS
    references, total = {}, len(program_raw)
    for name, path in layout.items():
        body = libraries[name]
        w._fields(body, ('reference', 'raw'), 'original produced DLL body')
        reference = _reference(body['reference'])
        _equal(reference['path'], path, 'fixed original produced DLL path')
        raw = body['raw']
        if type(raw) is not bytes or not 64 <= len(raw) <= MAX_RUNTIME_DLL_BYTES:
            raise ValueError('Bounded original produced DLL bytes required')
        total += len(raw)
        if total > MAX_RUNTIME_BYTES or _hash(raw) != reference['sha256']:
            raise ValueError('Produced runtime aggregate bytes or original DLL pin differs')
        references[name] = reference
    program_inspection = inspector.inspect_tool_image(program_raw)
    if (program_inspection['format'] != 'pe32plus' or program_inspection['machine'] != 'x86_64'
            or program_inspection['dll'] is not False):
        raise ValueError('Produced runtime program must be a native x64 executable')
    inspections = {}
    for name, body in libraries.items():
        inspection = inspector.inspect_tool_image(body['raw'])
        if (inspection['format'] != 'pe32plus' or inspection['machine'] != 'x86_64'
                or inspection['dll'] is not True):
            raise ValueError('Produced runtime child must be a native x64 DLL')
        inspections[name] = inspection
    reached, system, pending = set(), set(), list(program_inspection['needed'])
    while pending:
        name = pending.pop()
        if name in system_names:
            system.add(name)
        elif name not in declared:
            raise ValueError('Unknown produced runtime import; fallback DLL search is unsupported')
        elif name not in reached:
            reached.add(name)
            pending.extend(inspections[name]['needed'])
    if reached != set(declared):
        raise ValueError('Unused Source-declared produced runtime DLL is forbidden')
    value = {'schema_version': 1, 'kind': RUNTIME_KIND,
        'program': copy.deepcopy(program_ref), 'source_policy': copy.deepcopy(source_policy),
        'libraries': copy.deepcopy(references),
        'inspection_subjects': {'program': _hash(w.encoded(program_inspection)),
            'libraries': {name: _hash(w.encoded(row)) for name, row in inspections.items()}},
        'system': {'root': system_identity['root'], 'windows_version': copy.deepcopy(version),
            'imports': sorted(system)}}
    w.encoded(value)
    return value


def _runtime_factory(context):
    if type(context) is not _NativeContext or context not in _NATIVE_CONTEXTS:
        raise ValueError('Actual native produced-runtime context required')
    context._check()
    state = _NATIVE_CONTEXTS[context]
    policy, lease = _support_module('producer')._factory(state['factory'])
    if (policy['context'] is not context or policy['source_mode'] != 'fresh-owned'
            or state['workspace'] is not context.workspace or state['held'] is not context.held
            or lease['held'] is not context.held or state['input_token'] is not policy['input_token']
            or state['source_token'] is not policy['source_token']):
        raise ValueError('Same original fresh produced-runtime factory owners required')
    _equal(context.registration, policy['registration'], 'fixed produced-runtime registration')
    _equal(context.commands, policy['commands'], 'fixed produced-runtime commands')
    _equal(context.identity, policy['identity'], 'fixed produced-runtime H2 identity')
    if (type(policy['produced_runtime_policies']) is not dict
            or set(policy['produced_runtime_policies']) != set(context.registration['produced_tools'])):
        raise ValueError('Exact independently fixed produced-runtime policies required')
    return state, policy, lease


def _runtime_producing_stage_ids(context):
    """Source-derived stage IDs for the fixed G2 snapshot/flush integration."""
    unused_state, policy, unused_lease = _runtime_factory(context)
    selected = {row['producing_command_id'] for row in policy['registration']['produced_tools'].values()}
    return [command['id'] for command in policy['commands'] if command['id'] in selected]


def _runtime_system(lease):
    actual = lease['a']._Native().runtime_identity()
    _equal(actual, lease['subject']['runtime_identity'], 'actual produced-runtime OS/runtime')
    return {'root': actual['system_root'], 'windows_version': copy.deepcopy(actual['windows_version'])}


def _closed_runtime_operation(context, operation):
    state, unused_policy, lease = _runtime_factory(context)
    joined, log = operation['joined'], operation['log']
    if (type(joined) is not lease['a'].JoinedStage or type(log) is not lease['a'].OwnedLog
            or not any(item is joined for item in context.workspace.joined)
            or not any(item is log for item in context.workspace.logs)
            or log._workspace is not context.workspace or log._state != 'sealed'):
        raise ValueError('Original actual closed produced-program operation/log required')
    facts = joined.as_dict()
    _equal(facts, operation['joined_facts'], 'original closed produced-program operation')
    _equal(facts.get('tagged_command'), operation['declaration'], 'original produced-program declaration')
    if (facts.get('returncode') != 0 or facts.get('process_tree_closed') is not True
            or facts.get('closure') != 'actual-bound-job-finish-and-close'):
        raise ValueError('Actual successful known-closed producer required')
    return state, lease


def _runtime_dll_membership(context, program, source_policy, *, producer_root):
    """Reject local shadows and extra DLLs instead of assuming loader search."""
    directory = program['path'].rsplit('/', 1)[0]
    expected = set(_runtime_layout(program, source_policy, producer_root=producer_root).values())
    snapshot, actual = context.workspace.inspect_outputs(), set()
    for relative, row in snapshot['files'].items():
        path = context.workspace.output + '/' + relative
        parent, leaf = path.rsplit('/', 1)
        if parent == directory and leaf.casefold().endswith('.dll'):
            if row.get('kind') != 'file' or leaf.casefold() in _native_inspection().SYSTEM_IMPORTS:
                raise ValueError('Local produced-runtime OS DLL shadow is forbidden')
            actual.add(path)
    if actual != expected:
        raise ValueError('Complete beside-executable DLL membership must equal the fixed Source map')
    return snapshot


def _native_product_runtime(context, role, capture, inspection, *, operation, observation):
    state, policy, lease = _runtime_factory(context)
    _closed_runtime_operation(context, operation)
    if not any(row is capture for row in context.captures):
        raise ValueError('Original actual produced-program capture required')
    if type(role) is not str or re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', role) is None:
        raise ValueError('Exact registered produced-runtime role required')
    recipe = context.registration['produced_tools'][role]
    _equal(recipe['producing_command_id'], operation['declaration']['id'], 'same actual produced-runtime command')
    _equal(operation['declaration'], context.commands[context.next_index], 'fixed actual produced-runtime stage')
    _equal(observation['logs']['combined'], operation['row'], 'same actual closed producer log')
    _pure()._pin(observation['output_subject_sha256'])
    fixed = policy['produced_runtime_policies'].get(role)
    if fixed is None:
        raise MissingSource(('windows-dependency-produced-' + role + '-runtime-source-policy',))
    _pure()._fields(fixed, ('libraries',), 'fixed produced runtime Source policy')
    declared = fixed['libraries']
    if type(declared) is not dict or len(declared) > MAX_RUNTIME_DLLS:
        raise ValueError('Finite fixed produced runtime DLL count required')
    documents = state.setdefault('runtime_documents', {})
    if type(documents) is not dict or role in documents or len(documents) >= 128:
        raise ValueError('One bounded runtime document per original produced role required')
    program = {'path': recipe['root'] + '/' + recipe['output'], 'sha256': _hash(capture['raw'])}
    _reference(program)
    _equal(_inspect_native_image(capture['raw']), inspection, 'actual produced program inspection')
    snapshot = _runtime_dll_membership(context, program, fixed, producer_root=recipe['root'])
    _equal(_hash(_inventory_encoded(snapshot)), observation['output_subject_sha256'],
        'runtime bodies belong to the original closed producer snapshot')
    original_program = snapshot['files'].get(program['path'][len(context.workspace.output) + 1:])
    if (type(original_program) is not dict or original_program.get('kind') != 'file'
            or original_program['sha256'] != program['sha256']
            or original_program['bytes'] != len(capture['raw'])):
        raise ValueError('Original produced-program capture differs from the actual output snapshot')
    selected, total = {}, len(capture['raw'])
    # Check all sizes and names before opening any additional whole body.
    for name, relative in declared.items():
        path = recipe['root'] + '/' + relative
        _pure()._path(path)
        if not path.startswith(context.workspace.output + '/'):
            raise ValueError('Produced runtime DLL escapes original Workspace')
        row = snapshot['files'].get(path[len(context.workspace.output) + 1:])
        if type(row) is not dict or row.get('kind') != 'file':
            raise ValueError('Original produced runtime DLL output absent')
        size = _pure()._int(row['bytes'], 'produced runtime DLL bytes', 64, MAX_RUNTIME_DLL_BYTES)
        total += size
        if total > MAX_RUNTIME_BYTES:
            raise ValueError('Actual produced runtime aggregate byte bound exceeded')
        selected[name] = {'reference': {'path': path, 'sha256': row['sha256']}, 'bytes': size}
    libraries, captures = {}, {}
    for name, row in selected.items():
        captures[name] = context._capture(row['reference'], row['bytes'])
        libraries[name] = {'reference': copy.deepcopy(row['reference']), 'raw': captures[name]['raw']}
    value = _runtime_document(program, fixed, capture['raw'], libraries,
        _runtime_system(lease), producer_root=recipe['root'])
    raw = _pure().encoded(value)
    reference = {'path': context.workspace.output + '/metadata/produced-runtime/' + role + '.json',
        'sha256': _hash(raw), 'bytes': len(raw)}
    _reference({key: reference[key] for key in ('path', 'sha256')})
    documents[role] = {'state': 'pending', 'raw': raw, 'reference': reference,
        'program': copy.deepcopy(program), 'program_capture': capture,
        'libraries': libraries, 'library_captures': captures, 'operation': operation,
        'index': context.next_index, 'source_policy': copy.deepcopy(fixed),
        'producer_root': recipe['root'], 'snapshot_subject': observation['output_subject_sha256'],
        'document_capture': None}
    context._check()
    return reference['sha256']


def _runtime_stage_snapshot(context, record):
    generated = _support_module('generated_inputs')
    matches = [token for token, state in generated._NATIVE.items()
        if type(token) is generated._NativeLifecycle and state['context'] is context
        and state['next_index'] == context.next_index and not state['revoked']]
    if len(matches) != 1:
        raise ValueError('Same actual generated lifecycle must precede runtime document publication')
    state, unused_files, unused_kind = generated._state(matches[0])
    path = context.workspace.output + '/metadata/stage-output/' + record['operation']['declaration']['id'] + '.json'
    raw = state['snapshots'].get(path)
    if type(raw) is not bytes or _hash(raw) != record['snapshot_subject']:
        raise ValueError('Original pre-runtime-document producer snapshot required')
    return context._capture({'path': path, 'sha256': _hash(raw)}, len(raw))


def _flush_runtime_documents(context):
    """Fixed G2 hook after its initial producer snapshot; never a callback slot."""
    state, policy, lease = _runtime_factory(context)
    result = []
    for role, record in sorted(state.get('runtime_documents', {}).items()):
        if record['state'] != 'pending':
            continue
        if record['index'] != context.next_index - 1:
            raise ValueError('Produced runtime document must flush at its own completed G2 stage')
        _closed_runtime_operation(context, record['operation'])
        _runtime_stage_snapshot(context, record)
        _equal(record['source_policy'], policy['produced_runtime_policies'][role], 'fixed original runtime Source policy')
        value = _runtime_document(record['program'], record['source_policy'],
            record['program_capture']['raw'], record['libraries'], _runtime_system(lease),
            producer_root=record['producer_root'])
        if _pure().encoded(value) != record['raw'] or _hash(record['raw']) != record['reference']['sha256']:
            raise ValueError('Original queued runtime document differs')
        for directory in ('metadata', 'metadata/produced-runtime'):
            if directory not in context.workspace.directories:
                context.workspace.mkdir_new(directory)
        relative = record['reference']['path'][len(context.workspace.output) + 1:]
        published = context.workspace.publish_bytes_new(relative, record['raw'])
        _equal({key: published[key] for key in ('sha256', 'bytes')},
            {key: record['reference'][key] for key in ('sha256', 'bytes')}, 'actual owned runtime document')
        record['document_capture'] = context._capture(
            {key: record['reference'][key] for key in ('path', 'sha256')}, len(record['raw']))
        record['state'] = 'held'
        result.append(copy.deepcopy(record['reference']))
        context._check()
    return result


def _runtime_document_references(context):
    """Enumerate only actual held documents for fixed publication bookkeeping."""
    state, policy, unused_lease = _runtime_factory(context)
    if (context.next_index != len(context.commands)
            or set(state.get('runtime_documents', {})) != set(policy['produced_runtime_policies'])):
        raise ValueError('Complete original produced-runtime scope required before publication')
    result = []
    for role, record in sorted(state.get('runtime_documents', {}).items()):
        if record['state'] != 'held' or record['document_capture'] is None:
            raise ValueError('Every produced runtime document must be held before publication')
        result.append(copy.deepcopy(record['reference']))
    return result


def _require_product_runtime(context, role, product, program_capture):
    state, policy, lease = _runtime_factory(context)
    record = state.get('runtime_documents', {}).get(role)
    if type(record) is not dict or record['state'] != 'held' or record['document_capture'] is None:
        raise ValueError('Actual sealed held produced-runtime document required before launch')
    _closed_runtime_operation(context, record['operation'])
    _equal(record['program'], product['output']['program'], 'same original produced-runtime program')
    _equal(record['source_policy'], policy['produced_runtime_policies'][role], 'same fixed runtime Source policy')
    _equal(record['reference']['sha256'], product['output']['runtime_subject_sha256'], 'actual produced-runtime subject')
    if program_capture['physical'] != record['program_capture']['physical']:
        raise ValueError('Original produced-runtime program physical identity changed')
    _runtime_dll_membership(context, record['program'], record['source_policy'],
        producer_root=record['producer_root'])
    libraries = {}
    for name, original in record['library_captures'].items():
        ref = record['libraries'][name]['reference']
        current = context._capture(ref, len(original['raw']), identity=original['physical'])
        libraries[name] = {'reference': copy.deepcopy(ref), 'raw': current['raw']}
    value = _runtime_document(record['program'], record['source_policy'], program_capture['raw'], libraries,
        _runtime_system(lease), producer_root=record['producer_root'])
    _equal(value['inspection_subjects']['program'], product['output']['inspection_subject_sha256'],
        'same original produced-runtime executable inspection')
    raw = _pure().encoded(value)
    document = context._capture({key: record['reference'][key] for key in ('path', 'sha256')},
        record['reference']['bytes'], identity=record['document_capture']['physical'])
    if raw != record['raw'] or document['raw'] != raw:
        raise ValueError('Actual held produced-runtime document or current runtime bytes changed')


def _native_inspection():
    if _NATIVE_INSPECTION_SHA256 is None:
        raise MissingSource(('windows-dependency-v2-produced-program-image-source-binding',))
    path = Path(__file__).resolve().with_name('native_inspection.py')
    return _load_verified_source(path, _NATIVE_INSPECTION_SHA256,
        '_d2_actual_native_inspection_' + _NATIVE_INSPECTION_SHA256[:16])


def _proof_module():
    path = Path(__file__).resolve().with_name('proof_d3.py')
    return _load_verified_source(path, _H2D2_PROOF_SHA256,
        '_d3_fixed_proof_' + _H2D2_PROOF_SHA256[:16])


def _witness_module():
    path = Path(__file__).resolve().with_name('probe_d3.py')
    return _load_verified_source(path, _W2_SHA256,
        '_d3_fixed_witness_' + _W2_SHA256[:16])


def _inspect_native_image(raw):
    return _native_inspection().inspect_tool_image(raw)


class _Context:
    """Shared finite logic; only exact registered native type has authority."""

    def _registry(self):
        if type(self) is _NativeContext:
            return _NATIVE_CONTEXTS, _NATIVE_PRODUCTS, _NativeProduct
        if type(self) is _FixtureContext:
            return _FIXTURE_CONTEXTS, _FIXTURE_PRODUCTS, _FixtureProduct
        raise ValueError('Exact controller context required')

    def _check(self):
        contexts, _, _ = self._registry()
        state = contexts.get(self)
        if state is None or state['workspace'] is not self.workspace or state['held'] is not self.held:
            raise ValueError('Original controller factory association required')
        if self.revoked or self.closed or self.clock() >= self.deadline:
            raise ValueError('Controller is revoked, closed or expired')
        self.workspace.check_anchors()
        self.held.check()
        for capture in self.captures:
            capture['owner'].check()

    def _revoke(self, reason):
        self.revoked = True
        _, products, _ = self._registry()
        for token, record in list(products.items()):
            if record['context'] is self:
                del products[token]
        probes = _NATIVE_PROBES if type(self) is _NativeContext else _FIXTURE_PROBES
        for token, record in list(probes.items()):
            if record['context'] is self:
                del probes[token]
        _RETAINED_UNCERTAIN.append((self, str(reason)))

    def _original(self, tag):
        _pure()._fields(tag, ('kind', 'role', 'declaration'), 'original program tag')
        if tag['kind'] != 'original' or tag['role'] not in self.identity['programs']:
            raise ValueError('Registered original H2 role required')
        role = tag['role']
        program = self.identity['programs'][role]
        _equal(tag['declaration'], program, 'original H2 declaration')
        evidence = self.original_evidence[role]
        _pure()._fields(evidence, ('observation', 'inventory_subject_sha256',
            'runtime_subject_sha256'), 'original program evidence')
        _reference(evidence['observation'])
        for key in ('inventory_subject_sha256', 'runtime_subject_sha256'):
            _pure()._pin(evidence[key])
        # Production context receives these only from genuine opaque H2 issuer
        # reconstruction. This read preserves current original bytes, not version
        # semantics; fixture contexts cannot issue production capabilities.
        raw = self.held.read_ref({key: program[key] for key in ('path', 'sha256')}, 256 * 1024**2)
        if type(raw) is not bytes or _hash(raw) != program['sha256']:
            raise ValueError('Actual selected original executable changed')
        return {'kind': 'original', 'role': role, 'program': copy.deepcopy(program),
            **copy.deepcopy(evidence)}

    def _product(self, tag):
        _pure()._fields(tag, ('kind', 'role', 'producing_command_id', 'output'), 'produced program tag')
        if tag['kind'] != 'produced' or tag['role'] not in self.registration['produced_tools']:
            raise ValueError('Fixed registered produced role required')
        recipe = self.registration['produced_tools'][tag['role']]
        for name in ('producing_command_id', 'output'):
            _equal(tag[name], recipe[name], 'registered produced ' + name)
        token = self.products.get(tag['role'])
        _, registry, kind = self._registry()
        if type(token) is not kind or token not in registry:
            raise ValueError('Original earlier produced-program capability required')
        row = registry[token]
        if row['context'] is not self or row['workspace'] is not self.workspace:
            raise ValueError('Produced executable belongs to another Workspace')
        if row['index'] >= self.next_index or row['command']['id'] != tag['producing_command_id']:
            raise ValueError('Producer must be a strictly earlier completed step')
        if (not any(item is row['joined'] for item in self.workspace.joined)
                or not any(item is row['log'] for item in self.workspace.logs)
                or row['log']._workspace is not self.workspace or row['log']._state != 'sealed'):
            raise ValueError('Actual closed producer/log association changed')
        _equal(row['joined'].as_dict(), row['joined_facts'], 'original producer JoinedStage')
        if row['joined_facts'].get('returncode') != 0 or row['joined_facts'].get('process_tree_closed') is not True:
            raise ValueError('Actual successful closed producer required')
        item = row['output']
        expected_path = recipe['root'] + '/' + tag['output']
        _equal(item['program']['path'], expected_path, 'exact registered produced path')
        # A new input owner/read avoids a stale cached body at every launch.
        program_capture = self._capture(item['program'], row['bytes'], identity=row['physical'])
        if type(self) is _NativeContext:
            _require_product_runtime(self, tag['role'], row, program_capture)
        return {'kind': 'produced', 'role': tag['role'],
            'producing_command_id': tag['producing_command_id'], 'output': tag['output'],
            **copy.deepcopy(item), 'output_subject_sha256': row['output_subject_sha256']}

    def resolve(self, declaration):
        self._check()
        if self.next_index >= len(self.commands):
            raise ValueError('Fixed registered sequence is complete')
        _equal(declaration, self.commands[self.next_index], 'fixed next command')
        environment = declaration['environment']
        tag = declaration['program']
        nmake = type(tag) is dict and tag.get('kind') == 'original' and tag.get('role') == 'nmake'
        mandatory = {'SystemRoot', 'PATH', 'TEMP', 'TMP'}
        allowed = mandatory | {'INCLUDE', 'LIB'} | ({'COMSPEC'} if nmake else set())
        if (type(environment) is not dict or not mandatory <= set(environment)
                or not set(environment) <= allowed):
            raise ValueError('Finite admitted D3 environment required')
        if nmake:
            runtime = self.nmake_runtime
            if type(self) is _NativeContext:
                _equal(runtime, _NATIVE_CONTEXTS[self]['nmake_runtime'], 'original NMake runtime authority')
            selected = runtime['command_processor']
            _pure()._fields(selected, ('path', 'sha256', 'bytes'), 'NMake original command processor')
            _equal(selected['path'], self.identity['system_root'] + '/System32/cmd.exe', 'exact admitted command processor')
            _equal(environment.get('COMSPEC'), selected['path'], 'exact derived NMake COMSPEC')
            _reference({key: selected[key] for key in ('path', 'sha256')})
            _pure()._int(selected['bytes'], 'NMake command processor bytes', 1, 64 * 1024**2)
            actual = self.held.read_ref({key: selected[key] for key in ('path', 'sha256')}, 64 * 1024**2)
            if type(actual) is not bytes or len(actual) != selected['bytes'] or _hash(actual) != selected['sha256']:
                raise ValueError('Actual original NMake command processor changed')
        _equal(environment['SystemRoot'], self.identity['system_root'], 'exact original SystemRoot')
        allowed = sorted({row['path'].rsplit('/', 1)[0]
            for row in self.identity['programs'].values()}, key=str.casefold)
        path = environment['PATH'].split(';') if type(environment['PATH']) is str else []
        if not path or len(path) != len(set(item.casefold() for item in path)) or any(item not in allowed for item in path):
            raise ValueError('PATH must use unique exact admitted H2 program parents')
        for name in ('TEMP', 'TMP'):
            _equal(environment[name], self.workspace.output + '/tmp', 'controlled ' + name)
        for name, key in (('INCLUDE', 'include_directories'), ('LIB', 'library_directories')):
            if name in environment:
                _equal(environment[name], ';'.join(self.identity[key]), 'admitted ' + name)
        tag = declaration['program']
        if type(tag) is not dict or tag.get('kind') not in ('original', 'produced'):
            raise ValueError('Closed D2 program tag required')
        resolved = self._original(tag) if tag['kind'] == 'original' else self._product(tag)
        execution = copy.deepcopy(declaration)
        execution['program'] = copy.deepcopy(resolved['program'])
        if not execution['argv'] or execution['argv'][0] != execution['program']['path']:
            raise ValueError('Exact resolved executable must be argv[0]')
        return resolved, execution

    def _capture(self, reference, size, *, identity=None, minimum=1):
        _reference(reference)
        if type(size) is not int or not minimum <= size <= 256 * 1024**2:
            raise ValueError('Finite produced executable size required')
        root = self.workspace.output
        prefix = root + '/'
        if not reference['path'].startswith(prefix):
            raise ValueError('Produced file must be in the same actual Workspace')
        relative = reference['path'][len(prefix):]
        owner = self.held.open_output(root)
        capture = {'owner': owner}
        self.captures.append(capture)  # preserve the owner before uncertain read
        raw = owner.read(relative, expected={'sha256': reference['sha256'],
            'bytes': size, 'mode': 0o644}, maximum=256 * 1024**2)
        physical = owner._files.get(relative, {}).get('identity')
        if physical is None or identity is not None and physical != identity:
            raise ValueError('Original produced file physical identity changed')
        if type(raw) is not bytes or len(raw) != size or _hash(raw) != reference['sha256']:
            raise ValueError('Actual produced executable bytes changed')
        capture.update(raw=raw, physical=copy.deepcopy(physical))
        owner.check()
        return capture

    def _retain_outputs(self, operation, observation):
        produced = {}
        snapshot = self.workspace.inspect_outputs()
        for role, recipe in self.registration['produced_tools'].items():
            if recipe['producing_command_id'] != operation['declaration']['id']:
                continue
            path = recipe['root'] + '/' + recipe['output']
            prefix = self.workspace.output + '/'
            if not path.startswith(prefix):
                raise ValueError('Registered producer output escapes actual Workspace')
            row = snapshot['files'].get(path[len(prefix):])
            if type(row) is not dict or row.get('kind') != 'file':
                raise ValueError('Actual registered producer output is absent')
            reference = {'path': path, 'sha256': row['sha256']}
            capture = self._capture(reference, row['bytes'])
            if type(self) is _NativeContext:
                inspection = _inspect_native_image(capture['raw'])
                runtime = _native_product_runtime(self, role, capture, inspection,
                    operation=operation, observation=observation)
            else:
                inspection = self.fixture_images[path]
                runtime = self.fixture_runtimes[path]
            if inspection.get('format') != 'pe32plus' or inspection.get('machine') != 'x86_64' or inspection.get('dll') is not False:
                raise ValueError('Produced program must be an actual x64 PE executable')
            _pure()._pin(runtime)
            item = {'role': role, 'program': reference,
                'inspection_subject_sha256': _hash(_pure().encoded(inspection)),
                'runtime_subject_sha256': runtime}
            _, registry, kind = self._registry()
            token = object.__new__(kind)
            registry[token] = {'context': self, 'workspace': self.workspace,
                'index': self.next_index, 'command': copy.deepcopy(operation['declaration']),
                'joined': operation['joined'], 'joined_facts': copy.deepcopy(operation['joined_facts']),
                'log': operation['log'], 'output': {key: copy.deepcopy(item[key]) for key in
                    ('program', 'inspection_subject_sha256', 'runtime_subject_sha256')},
                'output_subject_sha256': observation['output_subject_sha256'],
                'bytes': row['bytes'], 'physical': capture['physical']}
            self.products[role] = token
            produced[recipe['output']] = item
        return produced

    def step(self):
        """Execute exactly one independently registered next stage."""
        try:
            self._check()
            if self.next_index >= len(self.commands):
                raise ValueError('Fixed registered sequence is complete')
            declaration = self.commands[self.next_index]
            resolved, execution = self.resolve(declaration)
            if declaration['stage'] == 'probe' and declaration['supplier'] == '__closure__':
                self._check_probe_link(execution)
            phase, limits = _phase_limits(self.limits, declaration['stage'], self.deadline, self.clock())
            operation = _run_owned(self, declaration, execution, phase, limits)
            snapshot = self.workspace.inspect_outputs()
            # This is the inventory domain, not the 4MiB H/D JSON domain.
            subject = _hash(_inventory_encoded(snapshot))
            observation = copy.deepcopy(declaration)
            observation.update(resolved_program=resolved, logs={'combined': operation['row']},
                output_subject_sha256=subject, job=operation['job'])
            observation['produced_outputs'] = self._retain_outputs(operation, observation)
            self.observations.append(observation)
            self.next_index += 1
            self._check()
            return copy.deepcopy(observation)
        except BaseException as error:
            self._revoke(error)
            raise

    def compile_probe(self, witness, *, identity_raw, identity_pin,
                      maintained_source_path, limits):
        """Fixed header-free compile first; witness is a pinned pure W2 module.

        The native factory supplies the exact source-bound module, never a caller
        callback. A fixture may use a distinct synthetic module and registry.
        """
        try:
            self._check()
            if self.probe is not None or self.next_index or self.observations:
                raise ValueError('Exactly one initial probe compile is allowed')
            before = self.workspace.inspect_outputs()
            if before['files'] or before['directories'] or before['bytes']:
                raise ValueError('Probe compile must precede all supplier outputs')
            if type(self) is _NativeContext:
                state = _NATIVE_CONTEXTS[self]
                if witness is not state['witness'] or _W2_SHA256 is None:
                    raise ValueError('Exact source-bound W2 module required')
                if identity_raw != state['identity_raw'] or identity_pin != state['identity_pin']:
                    raise ValueError('Exact independently admitted native H2 bytes required')
            limits = copy.deepcopy(limits)
            remaining = int((self.deadline - self.clock()) * 1000)
            if remaining < 1:
                raise ValueError('Original operation lifetime exhausted before compile')
            limits['wall_milliseconds'] = min(limits['wall_milliseconds'], remaining)
            plan = witness.plan(identity_raw, identity_pin, maintained_source_path,
                self.workspace.output, limits)
            source = self.held.read_ref(plan['source']['maintained'], witness.MAX_SOURCE_BYTES)
            if type(source) is not bytes or _hash(source) != witness.SOURCE_SHA256:
                raise ValueError('Fixed original maintained source changed')
            self._original({'kind': 'original', 'role': 'compiler',
                'declaration': self.identity['programs']['compiler']})
            for directory in ('probe', 'logs', 'tmp'):
                self.workspace.mkdir_new(directory)
            copied = self.workspace.publish_bytes_new('probe/static-closure-probe.cpp', source)
            copy_ref = {'path': self.workspace.output + '/' + copied['path'], 'sha256': copied['sha256']}
            _equal(copy_ref, plan['source']['compiled'], 'actual owned source copy')
            copied_capture = self._capture(copy_ref, len(source))
            operation = _run_owned(self, plan['command'], plan['command'], 'probe',
                plan['limits'], operation='probe-compile',
                log_relative=plan['log_path'][len(self.workspace.output) + 1:],
                source_intent={'source': copy.deepcopy(plan['source']), 'object_path': plan['object_path']})
            output = self.workspace.inspect_outputs()
            relative = plan['object_path'][len(self.workspace.output) + 1:]
            row = output['files'].get(relative)
            if type(row) is not dict or not 1 <= row.get('bytes', 0) <= witness.MAX_OBJECT_BYTES:
                raise ValueError('Actual bounded compiled object is absent')
            capture = self._capture({'path': plan['object_path'], 'sha256': row['sha256']}, row['bytes'])
            inspection = witness.inspect_object(capture['raw'])
            kind = _NativeProbe if type(self) is _NativeContext else _FixtureProbe
            registry = _NATIVE_PROBES if type(self) is _NativeContext else _FIXTURE_PROBES
            token = object.__new__(kind)
            registry[token] = {'context': self, 'workspace': self.workspace, 'plan': plan,
                'operation': operation, 'object': capture, 'source': copied_capture,
                'source_raw': source, 'inspection': inspection,
                'identity_raw': identity_raw, 'identity_pin': identity_pin}
            self.probe = token
            self._check()
            return token
        except BaseException as error:
            self._revoke(error)
            raise

    def _check_probe_link(self, execution):
        kind = _NativeProbe if type(self) is _NativeContext else _FixtureProbe
        registry = _NATIVE_PROBES if type(self) is _NativeContext else _FIXTURE_PROBES
        if type(self.probe) is not kind or self.probe not in registry:
            raise ValueError('Same actual initial compile capability required')
        row = registry[self.probe]
        if row['context'] is not self or row['workspace'] is not self.workspace:
            raise ValueError('Compiled object belongs to another actual Workspace')
        operation = row['operation']
        if (not any(item is operation['joined'] for item in self.workspace.joined)
                or not any(item is operation['log'] for item in self.workspace.logs)
                or operation['log']._workspace is not self.workspace
                or operation['log']._state != 'sealed'):
            raise ValueError('Original closed compile owner/log association required')
        _equal(operation['joined'].as_dict(), operation['joined_facts'], 'actual original compile token')
        _equal(execution['program'], self.identity['programs']['linker'], 'exact original H2 linker')
        obj = row['plan']['object_path']
        if execution['response_files'] or execution['argv'].count(obj) != 1:
            raise ValueError('Exactly one direct original compiled object operand required')
        if any(arg.casefold().endswith('.obj') and arg != obj for arg in execution['argv'][1:]):
            raise ValueError('Unreviewed sibling object is forbidden')
        self._capture({'path': obj, 'sha256': row['inspection']['object_sha256']},
            len(row['object']['raw']), identity=row['object']['physical'])
        return row


class _NativeContext(_Context):
    def __new__(cls, *args, **kwargs):
        raise ValueError('Use the fixed actual native factory')


class _FixtureContext(_Context):
    def __new__(cls, *args, **kwargs):
        raise ValueError('Use the separate inert context factory')


def _run_owned(context, declaration, execution, phase, limits, *, operation=None,
               log_relative=None, source_intent=None):
    context._check()
    workspace = context.workspace
    relative = log_relative or 'logs/' + declaration['id'] + '.log'
    log = workspace.open_log_new(relative)
    workspace.mark_running(log)
    intent = {'phase': phase, 'operation': operation or declaration['stage'],
        'execution_command': copy.deepcopy(execution)}
    if source_intent is None:
        intent['tagged_command'] = copy.deepcopy(declaration)
    else:
        intent.update(copy.deepcopy(source_intent))
    started, owner, joined = context.clock(), None, None
    join_attempted = seal_attempted = sealed = False
    peak_count, peak_output = 1, 0

    def sample():
        nonlocal peak_count, peak_output
        context._check()
        usage = workspace.usage(log=log)
        for name in ('bytes', 'log_bytes'):
            _pure()._int(usage[name], 'actual ' + name, 0, 2**63 - 1)
        peak_output = max(peak_output, usage['bytes'])
        if peak_output > limits['maximum_output_bytes'] or usage['log_bytes'] > limits['maximum_log_bytes']:
            raise ValueError('Actual output/log bound exceeded')
        if owner is not None:
            count = owner.job.active()
            _pure()._int(count, 'actual live Job count', 0, 2**31 - 1)
            peak_count = max(peak_count, count)
            if peak_count > limits['maximum_processes']:
                raise ValueError('Sampled Job process bound exceeded')
        if int((context.clock() - started) * 1000) >= limits['wall_milliseconds']:
            raise ValueError('Original stage deadline exhausted')

    try:
        sample()
        owner = workspace.launch(log, execution['argv'], execution['cwd'],
            env=execution['environment'], maximum_active_processes=limits['maximum_processes'])
        if owner.job is None:
            raise ValueError('Actual bound native Job required')
        while owner.poll() is None:
            sample()
            context.pause(0.01)
        sample()  # live final sample before sole actual A finish/close
        join_attempted = True
        joined = workspace.mark_joined(log, intent)
        facts = joined.as_dict()
        for key, value in intent.items():
            _equal(facts.get(key), value, 'actual joined ' + key)
        if (not any(item is joined for item in workspace.joined)
                or not any(item is log for item in workspace.logs)
                or log._workspace is not workspace or facts.get('returncode') != 0
                or facts.get('process_tree_closed') is not True
                or facts.get('closure') != 'actual-bound-job-finish-and-close'):
            raise ValueError('Original successful closed A stage required')
        seal_attempted = True
        row = workspace.seal_log(log)
        if log._state != 'sealed':
            raise ValueError('Original actual stage log must be sealed')
        sealed = True
        _equal(row['path'], relative, 'owned stage log path')
        log_capture = context._capture({'path': workspace.output + '/' + relative, 'sha256': row['sha256']},
            row['bytes'], identity=log.identity, minimum=0)
        final = workspace.inspect_outputs()
        peak_output = max(peak_output, _pure()._int(final['bytes'], 'final output bytes', 0, 2**63 - 1))
        elapsed = int((context.clock() - started) * 1000)
        if peak_output > limits['maximum_output_bytes'] or elapsed >= limits['wall_milliseconds']:
            raise ValueError('Final output/stage deadline bound exceeded')
        job = {'owner': 'windows-job-v1', 'launch_intent_sha256': _hash(_pure().encoded(execution)),
            'image': {key: execution['program'][key] for key in ('path', 'sha256')},
            'launch_suspended': True, 'assigned_before_resume': True,
            'breakaway_allowed': False, 'kill_on_close': True, 'exit_code': facts['returncode'],
            'elapsed_milliseconds': elapsed, 'wall_limit_milliseconds': limits['wall_milliseconds'],
            'process_count': peak_count, 'process_limit': limits['maximum_processes'],
            'peak_output_bytes': peak_output, 'output_limit_bytes': limits['maximum_output_bytes'],
            'active_processes_at_join': 0, 'streams_closed': True, 'join_completed': True, 'owner_closed': True}
        return {'declaration': copy.deepcopy(declaration), 'joined': joined,
            'joined_facts': copy.deepcopy(facts), 'log': log,
            'log_capture': log_capture,
            'row': {'path': workspace.output + '/' + relative, 'sha256': row['sha256'], 'bytes': row['bytes']},
            'job': job}
    except BaseException as error:
        context._revoke(error)
        if (join_attempted and joined is None) or (seal_attempted and not sealed):
            workspace.retain_uncertain(owner, log, str(error))
            raise
        try:
            if joined is None and owner is not None:
                owner.terminate(timeout=5)
                join_attempted = True
                joined = workspace.mark_joined(log, intent)
            if joined is not None:
                workspace.mark_failed_joined(joined, str(error))
                if not sealed:
                    workspace.seal_log(log)
            else:
                workspace.retain_uncertain(owner, log, str(error))
        except BaseException as cleanup:
            workspace.retain_uncertain(owner, log, str(error) + '; cleanup: ' + str(cleanup))
        raise


def _fixture_context(workspace, held, *, identity, commands, registration,
                     original_evidence, limits, deadline, clock, pause,
                     images=None, runtimes=None):
    """Synthetic mechanism fixture only; never a native production factory."""
    context = object.__new__(_FixtureContext)
    context.workspace, context.held = workspace, held
    context.identity = copy.deepcopy(identity)
    context.commands, context.registration = copy.deepcopy(commands), copy.deepcopy(registration)
    context.original_evidence = copy.deepcopy(original_evidence)
    context.limits, context.deadline = copy.deepcopy(limits), deadline
    context.clock, context.pause = clock, pause
    context.fixture_images, context.fixture_runtimes = copy.deepcopy(images or {}), copy.deepcopy(runtimes or {})
    context.captures, context.observations, context.products = [], [], {}
    context.next_index, context.revoked, context.closed, context.probe = 0, False, False, None
    _FIXTURE_CONTEXTS[context] = {'workspace': workspace, 'held': held}
    return context
