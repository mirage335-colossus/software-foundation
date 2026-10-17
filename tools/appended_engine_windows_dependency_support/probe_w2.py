"""Private H2/D2 probe-object consistency, never native admission.

Only fixed hash-pinned pure source dependencies are loaded lazily. No selected
program, SDK, supplier, archive or product body is acquired. Supplied bytes and
independent expected declarations cannot create a native constructor authority.
"""

from collections import Counter
import copy
import hashlib
from pathlib import Path
import types


KIND = 'foundation-native-engine-windows-static-probe-object-witness-v2'
PLAN_KIND = 'foundation-native-engine-windows-static-probe-object-plan-v2'
MISSING_CONSTRUCTOR = 'windows-static-probe-v2-original-compile-owned-witness-constructor'
SOURCE_SHA256 = 'd71938060a67c63c3557d1c45c98fe9039462a31e122d47cc0a4dc859e95b4ca'
# Exact immutable W1 bounds, exposed without loading its source at module import.
MAX_SOURCE_BYTES = 65536
MAX_OBJECT_BYTES = 4 * 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024
MAX_DOCUMENT = 4 * 1024 * 1024
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
DECLARATION_FIELDS = ('id', 'stage', 'program', 'argv', 'cwd', 'environment')
WITNESS_FIELDS = ('schema_version', 'kind', 'target', 'scope', 'dependency_receipt',
    'toolchain_identity_sha256', 'source', 'command', 'object', 'inspection', 'postflight', 'facts')
_H2 = None
_W1 = None


class MissingSource(ValueError):
    pass


def _source_module(source, size, pin, name):
    with source.open('rb') as stream:
        raw = stream.read(size + 1)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('Frozen pure source differs: ' + name)
    module = types.ModuleType(name)
    module.__file__ = str(source)
    exec(compile(raw, str(source), 'exec'), vars(module))
    return module


def _h2():
    global _H2
    if _H2 is None:
        source = Path(__file__).resolve().parent / 'proof_h2.py'
        _H2 = _source_module(source, 19877,
            'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9',
            '_private_w2_frozen_h2d2')
    return _H2


def _w1():
    global _W1
    if _W1 is None:
        source = (Path(__file__).resolve().parent /
                  'probe_core.py')
        module = _source_module(source, 27776,
            'ba66eaa2d88912ab4ae5277cc56f0616384a9c38241f8c1ad374b38a40f0747f',
            '_private_w2_frozen_w1_low_level')
        if (MAX_SOURCE_BYTES, MAX_OBJECT_BYTES, MAX_LOG_BYTES, MAX_DOCUMENT) != (
                module.MAX_SOURCE_BYTES, module.MAX_OBJECT_BYTES, module.MAX_LOG_BYTES, module.MAX_DOCUMENT):
            raise ValueError('Exposed W2 bounds differ from frozen W1 source')
        _W1 = module
    return _W1


def encoded(value):
    return _w1().encoded(value)


def inspect_object(raw):
    """Reuse the frozen bounded regular-AMD64-COFF byte inspector."""
    return _w1().inspect_object(raw)


def output_subject(selected_plan, object_raw, log_raw):
    return _w1().output_subject(selected_plan, object_raw, log_raw)


def _overlaps(first, second):
    first, second = first.casefold(), second.casefold()
    return first == second or first.startswith(second + '/') or second.startswith(first + '/')


def plan(identity_raw, identity_pin, maintained_source_path, workspace_root, limits):
    """Build the fixed compile declaration directly from the actual H2 roles."""
    h2, low = _h2(), _w1()
    identity = h2.validate_toolchain_identity(identity_raw, identity_pin)
    h1 = h2.legacy()
    h1.windows_path(maintained_source_path, 'maintained probe source')
    h1.windows_path(workspace_root, 'owned probe workspace')
    selected_limits = low._limits(limits)
    if _overlaps(maintained_source_path, workspace_root):
        raise ValueError('Owned source copy must be separate from maintained input')
    protected = [item['root'] for item in identity['inventories'].values()]
    protected += [item['path'] for item in identity['programs'].values()]
    protected.append(identity['system_root'])
    if any(_overlaps(workspace_root, item) for item in protected):
        raise ValueError('Owned workspace overlaps a protected H2 input')
    parents = sorted({item['path'].rsplit('/', 1)[0] for item in identity['programs'].values()})
    if len({item.casefold() for item in parents}) != len(parents):
        raise ValueError('Aliased H2 PATH roots')
    compiled = workspace_root + '/probe/static-closure-probe.cpp'
    object_path = workspace_root + '/probe/static-closure-probe.obj'
    log_path = workspace_root + '/logs/probe-compile.log'
    compiler = copy.deepcopy(identity['programs']['compiler'])
    command = {'id': 'closure-probe-compile', 'stage': 'probe-compile', 'program': compiler,
        'argv': [compiler['path'], '/c', '/TP', '/MT', '/Od', '/Zl', '/X', '/Y-', '/WX',
            '-Werror=unknown-argument', '/clang:--no-default-config',
            '/clang:--target=x86_64-pc-windows-msvc', '/Fo' + object_path, compiled],
        'cwd': workspace_root, 'environment': {'SystemRoot': identity['system_root'],
            'PATH': ';'.join(parents), 'TEMP': workspace_root + '/tmp', 'TMP': workspace_root + '/tmp'}}
    return {'schema_version': 2, 'kind': PLAN_KIND, 'toolchain_identity_sha256': identity_pin,
        'source': {'maintained': {'path': maintained_source_path, 'sha256': SOURCE_SHA256},
                   'compiled': {'path': compiled, 'sha256': SOURCE_SHA256}},
        'command': command, 'object_path': object_path, 'log_path': log_path,
        'limits': selected_limits}


def _link(dependency, identity, object_path):
    """Join the actual W object to the complete finite direct-link declaration."""
    h2, low = _h2(), _w1()
    h1 = h2.legacy()
    command = dependency['commands'][-1]
    tag = {'kind': 'original', 'role': 'linker',
           'declaration': identity['programs']['linker']}
    low._equal(command['program'], tag, 'D2 original selected linker tag')
    resolved = command['resolved_program']
    low._equal(resolved['kind'], 'original', 'D2 resolved original linker')
    low._equal(resolved['role'], 'linker', 'D2 resolved linker role')
    low._equal(resolved['program'], identity['programs']['linker'], 'D2 resolved selected linker')
    low._equal(command['stage'], 'probe', 'D2 final probe stage')
    low._equal(command['supplier'], '__closure__', 'D2 final closure supplier')
    low._equal(command['response_files'], [], 'D2 direct link operands')
    low._equal(dependency['probe']['command_id'], command['id'], 'D2 final probe id')
    targets = dependency['probe']['library_targets']
    whole = ['/WHOLEARCHIVE:' + dependency['libraries'][target]['path'] for target in targets]
    tail = dependency['probe']['link_inputs'][20:]
    required = list(identity['crt_libraries'].values()) + [identity['builtins']]
    for reference in required:
        if tail.count(reference) != 1:
            raise ValueError('D2 link tail requires each exact H2 CRT and builtins once')
    for reference in tail:
        if reference in required:
            continue
        path = reference['path']
        if (not path.endswith('.lib') or
                not h1._inside(path, identity['inventories']['windows_sdk']['root']) or
                path.rsplit('/', 1)[0] not in identity['library_directories']):
            raise ValueError('D2 extra link input must be an independently selected SDK library')
    args = command['argv']
    wanted = [identity['programs']['linker']['path'], object_path,
        '/NODEFAULTLIB', '/OPT:NOREF', '/OPT:NOICF', '/MACHINE:X64',
        '/OUT:' + dependency['probe']['output']['path']] + whole + [item['path'] for item in tail]
    if args[0] != wanted[0] or Counter(args) != Counter(wanted):
        raise ValueError('D2 link requires exactly the finite selected inputs, flags and actual W object')
    if [item for item in args if item.startswith('/WHOLEARCHIVE:')] != whole:
        raise ValueError('D2 whole-archive operands must retain canonical twenty-library order')


def validate_witness(raw_witness, witness_pin, *, identity_raw, identity_pin, dependency_raw,
        dependency_pin, dependency_path, expected, maintained_source_raw, compiled_source_raw,
        object_raw, log_raw, maintained_source_path, workspace_root, limits):
    """Validate supplied declarations/bytes; no passed flag or native authority."""
    h2, low = _h2(), _w1()
    selected_plan = plan(identity_raw, identity_pin, maintained_source_path, workspace_root, limits)
    identity = h2.validate_toolchain_identity(identity_raw, identity_pin)
    value = low._fields(low._document(raw_witness, witness_pin), WITNESS_FIELDS, 'W2')
    for key, wanted in (('schema_version', 2), ('kind', KIND), ('target', TARGET),
                        ('scope', 'unqualified-static-probe-object')):
        low._equal(value[key], wanted, 'W2 ' + key)
    h2.legacy().windows_path(dependency_path, 'D2 receipt path')
    low._equal(value['dependency_receipt'], {'path': dependency_path, 'sha256': dependency_pin}, 'original D2 ref')
    low._equal(value['toolchain_identity_sha256'], identity_pin, 'W2/H2 pin')
    low._equal(value['source'], selected_plan['source'], 'maintained/compiled source declaration')
    for raw in (maintained_source_raw, compiled_source_raw):
        low._bytes(raw, low.MAX_SOURCE_BYTES, 'original probe source')
        if low._hash(raw) != SOURCE_SHA256:
            raise ValueError('Original maintained or copied probe source pin differs')
    inspection = inspect_object(object_raw)
    low._equal(value['inspection'], inspection, 'independent actual COFF inspection')
    object_ref = {'path': selected_plan['object_path'], 'sha256': inspection['object_sha256']}
    low._equal(value['object'], object_ref, 'actual object ref')
    low._bytes(log_raw, low.MAX_LOG_BYTES, 'original complete compile log', 0)
    if len(log_raw) > selected_plan['limits']['maximum_log_bytes']:
        raise ValueError('Compile log exceeds selected limit')
    command = low._fields(value['command'], DECLARATION_FIELDS +
        ('logs', 'output_subject_sha256', 'job'), 'W2 compile command')
    low._equal({key: command[key] for key in DECLARATION_FIELDS}, selected_plan['command'],
               'independent fixed H2 compile declaration')
    log = {'path': selected_plan['log_path'], 'sha256': low._hash(log_raw),
           'bytes': len(log_raw), 'mode': 0o644}
    low._equal(command['logs'], {'combined': log}, 'actual combined closed log bytes')
    low._equal(command['output_subject_sha256'], output_subject(selected_plan, object_raw, log_raw),
               'actual compile subject')
    low._job(command['job'], selected_plan['command'], selected_plan['limits'],
             len(compiled_source_raw) + len(object_raw) + len(log_raw))
    low._equal(value['postflight'], {'source_sha256': SOURCE_SHA256,
        'toolchain_identity_sha256': identity_pin, 'object_sha256': inspection['object_sha256']}, 'W2 postflight')
    low._equal(value['facts'], {name: False for name in low.FALSE_FACTS}, 'W2 false facts')
    dependency = h2.validate_dependency_receipt(dependency_raw, dependency_pin, expected, identity)
    _link(dependency, identity, object_ref['path'])
    dependency_logs = [item['logs']['combined'] for item in dependency['commands']]
    produced = [row['program'] for item in dependency['commands']
                for row in item['produced_outputs'].values()]
    paths = h2._identity_paths(identity)
    for reference in list(value['source'].values()) + [object_ref, log,
            value['dependency_receipt'], dependency['probe']['output']] + \
            dependency['probe']['link_inputs'] + dependency_logs + produced:
        paths.add(reference['path'], 'file', reference['sha256'])
    forbidden = {item['path'].casefold() for item in value['source'].values()}
    forbidden.update((selected_plan['log_path'].casefold(), dependency_path.casefold()))
    forbidden.update(item['path'].casefold() for item in identity['programs'].values())
    forbidden.add(dependency['probe']['output']['path'].casefold())
    forbidden.update(item['path'].casefold() for item in dependency['probe']['link_inputs'])
    forbidden.update(item['path'].casefold() for item in dependency_logs + produced)
    if object_ref['path'].casefold() in forbidden:
        raise ValueError('Probe object aliases an independent input/output')
    return {'native_admitted': False, 'object': copy.deepcopy(object_ref),
        'inspection': inspection, 'source_sha256': SOURCE_SHA256,
        'toolchain_identity_sha256': identity_pin, 'dependency_receipt_sha256': dependency_pin,
        'witness_sha256': witness_pin, 'missing_source': [MISSING_CONSTRUCTOR]}


def require_native_constructor():
    raise MissingSource(MISSING_CONSTRUCTOR)
