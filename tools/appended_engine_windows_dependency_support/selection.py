"""Closed private selection2 and existing native-input publication declarations.

Pure metadata only: constructing these dictionaries never admits original/native
facts. The native factory independently holds bytes and requires issuer tokens.
"""
import copy
import hashlib
import math
from pathlib import Path
import types
import sys

SELECTION_KIND = 'foundation-native-engine-windows-dependencies-selection-v2'
LIMITS = {'overall_seconds': (1, 86400), 'configure_seconds': (1, 3600),
    'build_seconds': (1, 28800), 'install_seconds': (1, 3600),
    'probe_seconds': (1, 3600), 'cleanup_seconds': (1, 60), 'maximum_jobs': (1, 4),
    'maximum_processes': (1, 64), 'maximum_output_bytes': (1024, 1024**4),
    'maximum_log_bytes': (1024, 128 * 1024**2)}
PUBLICATION_SOURCES = ('tools/appended_engine_windows_publication.py',
    'tests/diagnostics/windows_engine_publication.py', 'tools/process_tree.py',
    'tools/appended_engine_windows_contract.py')
_P = _C = None


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _module(path, pin, maximum, name):
    return _owner()._load_verified_source(path, pin, name, maximum)


def _proof():
    global _P
    if _P is None:
        _P = _module(Path(__file__).resolve().with_name('proof_h2.py'),
            'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9',
            65536, '_selection_exact_pure_h2')
    return _P


def _contract():
    global _C
    if _C is None:
        _C = _module(Path(__file__).resolve().parent.parent / 'appended_engine_windows_contract.py',
            'ef065be8c502211ea748dbfc1732b6ca02b9210ee78ed74901f2b6ca6869d5d8',
            65536, '_selection_exact_pure_windows_inputs')
    return _C


def _profile(value):
    h = _proof().legacy()
    h._fields(value, ('qualification', 'source_identity', 'runtime_identity'), 'publication profile')
    h._reference(value['qualification'], 'publication qualification')
    h._fields(value['source_identity'], PUBLICATION_SOURCES, 'publication source identity')
    for name, pin in value['source_identity'].items():
        h._pin(pin, name)
    runtime = value['runtime_identity']
    h._fields(runtime, ('python_path', 'python_sha256', 'python_version', 'system', 'machine',
        'pointer_bits', 'windows_version', 'system_root'), 'actual runtime declaration')
    for key in ('python_path', 'system_root'):
        h.windows_path(runtime[key])
    h._pin(runtime['python_sha256'], 'current Python')
    h._version(runtime['python_version'], 'current Python')
    for key, expected in (('system', 'Windows'), ('machine', 'x86_64'), ('pointer_bits', 64)):
        h._equal(runtime[key], expected, 'runtime ' + key)
    versions = runtime['windows_version']
    if type(versions) is not list or len(versions) != 3:
        raise ValueError('Windows runtime version triple required')
    for item in versions:
        h._integer(item, 'Windows runtime version', 0, 2**31 - 1)
    return copy.deepcopy(value)


def validate_limits(value):
    h = _proof().legacy()
    h._fields(value, LIMITS, 'selection2 finite limits')
    return {name: h._integer(value[name], name, *bounds) for name, bounds in LIMITS.items()}


def validate_selection(value):
    h = _proof().legacy()
    h._fields(value, ('schema_version', 'kind', 'target', 'toolchain_identity',
        'inventories', 'sources', 'output', 'publication', 'limits'), 'selection2')
    h._equal(value['schema_version'], 2, 'selection2 schema')
    h._equal(value['kind'], SELECTION_KIND, 'selection2 kind')
    h._equal(value['target'], _proof().TARGET, 'selection2 target')
    paths = h._Paths()
    h._reference(value['toolchain_identity'], 'original H2', paths)
    h._fields(value['inventories'], h.INVENTORIES, 'complete original four inventories')
    for role, reference in value['inventories'].items():
        h._reference(reference, role, paths)
    h._fields(value['sources'], h.SOURCES, 'thirteen original source selections')
    selected = set()
    for supplier, row in value['sources'].items():
        h._fields(row, ('archive', 'replay'), 'source ' + supplier)
        for key, reference in row.items():
            h._reference(reference, supplier + ' ' + key, paths)
            if reference['path'].casefold() in selected:
                raise ValueError('Original source archive/projection refs must be distinct')
            selected.add(reference['path'].casefold())
    paths.add(value['output'], 'directory')
    profile = _profile(value['publication'])
    h._reference(profile['qualification'], 'publication qualification', paths)
    validate_limits(value['limits'])
    for spelling, kind, pin in paths.entries.values():
        if kind == 'file' and (spelling.casefold().startswith(value['output'].casefold() + '/')
                or value['output'].casefold().startswith(spelling.casefold() + '/')):
            raise ValueError('Dependency output overlaps an original selected input')
    return copy.deepcopy(value)


def operation_deadline(original_start, original_deadline, limits):
    """Requested duration always starts at original command entry, never now."""
    limits = validate_limits(limits)
    for value in (original_start, original_deadline):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Finite original entry/deadline required')
    if not 0 < original_deadline - original_start <= 86400:
        raise ValueError('Original operation ceiling must be finite and positive')
    return min(original_deadline, original_start + limits['overall_seconds'])


def input_limits(deadline, now):
    for value in (deadline, now):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Finite original deadline required')
    remaining = deadline - now
    if not 0 < remaining <= 86400:
        raise ValueError('Original input operation lifetime exhausted/unsupported')
    return {'seconds': math.ceil(remaining), 'maximum_archive_bytes': 8 * 1024**3,
        'maximum_expanded_bytes': 32 * 1024**3, 'maximum_members': 1000000,
        'maximum_member_bytes': 256 * 1024**2, 'maximum_patch_bytes': 32 * 1024**2}


def native_input_declaration(identity, inventory_refs, prefix, prefix_inventory, libraries):
    """Construct the existing manifest from independently supplied checked facts.

    This helper validates declarations only. Actual callers must own native H2,
    inventories, library/archive inspections and completed publication evidence.
    Product assets are an independent SDK-consumer inventory, absent here.
    """
    identity = _proof().toolchain_identity(identity)
    h = _proof().legacy()
    h._fields(inventory_refs, h.INVENTORIES, 'four original inventory refs')
    for role, ref in inventory_refs.items():
        h._reference(ref, role)
    h._reference(prefix_inventory, 'fresh prefix inventory')
    h.windows_path(prefix)
    h._fields(libraries, h.LIBRARY_SUPPLIERS, 'exact independent Windows20 declaration')
    selected = {}
    for target, row in libraries.items():
        if type(row) is not dict or not {'path', 'sha256', 'includes', 'definitions', 'links'} <= set(row):
            raise ValueError('Complete original checked library declaration required')
        selected[target] = {name: copy.deepcopy(row[name]) for name in
            ('path', 'sha256', 'includes', 'definitions', 'links')}
    reference = lambda row: {key: row[key] for key in ('path', 'sha256')}
    value = {'schema_version': 1, 'kind': 'foundation-native-engine-windows-inputs',
        'target': 'windows-x86_64', 'build_type': 'Release', 'crt': 'static-mt',
        'cpu_baseline': 'x86_64-sse2', 'os_floor_declaration': 'windows-10-1809-unqualified',
        'engine_cxx_standard': 23, 'dependency_prefix': prefix,
        'toolchain': {'compiler': reference(identity['programs']['compiler']),
            'linker': reference(identity['programs']['linker']), 'builtins': reference(identity['builtins']),
            'compiler_version': identity['inventories']['llvm']['version'],
            **{role: {'root': identity['inventories'][role]['root'], 'inventory': copy.deepcopy(inventory_refs[role])}
                for role in ('msvc_stl', 'windows_sdk')}},
        'dependency_inventory': copy.deepcopy(prefix_inventory), 'woff2': 'OFF', 'libraries': selected}
    return _contract().validate_inputs(value)
