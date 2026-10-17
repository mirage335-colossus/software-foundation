"""Private pure H2/D2 declarations; never native or independent-factory authority.

Only the fixed frozen H1 pure source is read lazily. No native module, selected
program, SDK, archive, product or supplier body is read/imported/executed. A D2
expected dictionary is consistency input, not proof of independent registration.
The native controller must obtain it from its fixed opaque source-owned factory.
Generated script/data inputs are outside the PE-only produced-program protocol;
unreviewed supplier routes using them remain named factory MissingInputs.
"""

import copy
import hashlib
from pathlib import Path
import re
import types


IDENTITY_KIND = 'foundation-native-engine-windows-toolchain-identity-v2'
RECEIPT_KIND = 'foundation-native-engine-windows-dependencies-build-v2'
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
POLICY = {'build_type': 'Release', 'crt': 'static-mt', 'cpu_baseline': 'x86_64-sse2',
          'os_floor_declaration': 'windows-10-1809-unqualified',
          'engine_cxx_standard': 23, 'lto': False}
PROGRAM_NAMES = {'compiler': 'clang-cl.exe', 'linker': 'lld-link.exe',
    'archiver': 'llvm-lib.exe', 'resource_compiler': 'llvm-rc.exe',
    'manifest_tool': 'llvm-mt.exe', 'cmake': 'cmake.exe', 'ninja': 'ninja.exe',
    'python': 'python.exe', 'perl': 'perl.exe', 'ruby': 'ruby.exe', 'gperf': 'gperf.exe',
    'nmake': 'nmake.exe', 'msbuild': 'MSBuild.exe'}
IDENTITY_FIELDS = ('schema_version', 'kind', 'target', 'policy', 'inventories',
    'programs', 'builtins', 'crt_libraries', 'include_directories',
    'library_directories', 'system_root')
STAGES = ('configure', 'build-tool', 'generate', 'build', 'install', 'probe')
_BASE = None


def legacy():
    """Load exactly frozen 6d H1 helpers; no source-path or loader callback input."""
    global _BASE
    if _BASE is None:
        source = Path(__file__).resolve().parent.parent / 'appended_engine_windows_dependency_proof.py'
        with source.open('rb') as stream:
            raw = stream.read(35436)
        if (len(raw) != 35435 or hashlib.sha256(raw).hexdigest() !=
                '6d30769578be43268cf9a6226054db79d0e16956e52085fb0f1c4618505b5747'):
            raise ValueError('Frozen H1 pure helper source differs')
        module = types.ModuleType('_private_h2d2_frozen_h1')
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _BASE = module
    return _BASE


def encoded(value):
    return legacy().encoded(value)


def _identity_paths(value):
    h1 = legacy()
    paths = h1._Paths()
    for item in value['inventories'].values(): paths.add(item['root'], 'directory')
    for item in value['programs'].values(): paths.add(item['path'], 'file', item['sha256'])
    for item in (value['builtins'], *value['crt_libraries'].values()):
        paths.add(item['path'], 'file', item['sha256'])
    for name in ('include_directories', 'library_directories'):
        for directory in value[name]: paths.add(directory, 'directory')
    paths.add(value['system_root'], 'directory')
    return paths


def toolchain_identity(declared_facts):
    """Construct declared H2 only; the complete host bundle is not admitted here."""
    h1 = legacy()
    h1.encoded(declared_facts)
    value = h1._fields(declared_facts, IDENTITY_FIELDS, 'H2 toolchain identity')
    h1._equal(value['schema_version'], 2, 'H2 schema')
    h1._equal(value['kind'], IDENTITY_KIND, 'H2 kind')
    h1._fields(value['programs'], PROGRAM_NAMES, 'exact thirteen H2 programs')
    # Preserve every H1 field/role rule through its unchanged implementation.
    original = copy.deepcopy(value)
    original.update(schema_version=1, kind=h1.IDENTITY_KIND)
    original['programs'] = {role: original['programs'][role] for role in h1.PROGRAM_NAMES}
    h1.toolchain_identity(original)
    for role in ('nmake', 'msbuild'):
        item = h1._reference(value['programs'][role], 'H2 ' + role, program=True)
        if (not h1._inside(item['path'], value['inventories']['host_generators']['root']) or
                item['path'].rsplit('/', 1)[-1] != PROGRAM_NAMES[role]):
            raise ValueError('H2 frontend must belong to the complete host inventory: ' + role)
    _identity_paths(value)
    return copy.deepcopy(value)


def validate_toolchain_identity(raw, expected_pin, actual_facts=None):
    """Validate canonical H2/pin and optional reconstruction, never its authority."""
    h1 = legacy()
    h1._pin(expected_pin, 'H2 identity')
    value = toolchain_identity(h1.parse_document(raw))
    if hashlib.sha256(raw).hexdigest() != expected_pin:
        raise ValueError('H2 identity SHA256 mismatch')
    if actual_facts is not None:
        h1._equal(value, toolchain_identity(actual_facts), 'actual H2 reconstruction')
    return value


def _relative_output(root, relative):
    h1 = legacy()
    h1.windows_path(root, 'registered produced output root')
    h1._text(relative, 'portable produced output')
    if (relative.startswith('/') or ':' in relative or
            any(not part or part in ('.', '..') for part in relative.split('/')) or
            not relative.endswith('.exe')):
        raise ValueError('Canonical relative produced PE executable required')
    return h1.windows_path(root + '/' + relative, 'registered produced executable')


def _original_evidence(value, identity, paths):
    h1 = legacy()
    h1._fields(value, PROGRAM_NAMES, 'thirteen original H2 program evidence rows')
    seen = set()
    for role, item in value.items():
        h1._fields(item, ('observation', 'inventory_subject_sha256', 'runtime_subject_sha256'),
                   'original H2 program evidence')
        h1._reference(item['observation'], 'original version observation', paths)
        selected = item['observation']['path'].casefold()
        if selected in seen: raise ValueError('Original role observations alias')
        seen.add(selected)
        owner = 'llvm' if role in h1.LLVM_PROGRAMS else 'host_generators'
        h1._equal(item['inventory_subject_sha256'],
                  identity['inventories'][owner]['subject_sha256'], 'original owning inventory')
        h1._pin(item['runtime_subject_sha256'], 'independently reconstructed original runtime')


def _registration(value, commands, identity, paths):
    h1 = legacy()
    h1._fields(value, ('stages', 'produced_tools'), 'independent finite registration')
    h1._array(value['stages'], 'registered stages', h1.MAX_COMMANDS, 1)
    h1._equal(value['stages'], [{key: item[key] for key in ('id', 'supplier', 'stage')}
                              for item in commands], 'registered exact stage sequence')
    rows = {}
    suppliers = set()
    for item in value['stages']:
        h1._fields(item, ('id', 'supplier', 'stage'), 'registered stage')
        h1._text(item['id'], 'registered command id', 96)
        if re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', item['id']) is None or item['id'] in rows:
            raise ValueError('Duplicate/invalid registered command id')
        if item['stage'] not in STAGES:
            raise ValueError('Unsupported registered stage')
        if item['supplier'] not in h1.SOURCES and not (
                item['supplier'] == '__closure__' and item['stage'] == 'probe'):
            raise ValueError('Unknown registered supplier')
        rows[item['id']] = item
        if item['supplier'] in h1.SOURCES: suppliers.add(item['supplier'])
    if (suppliers != set(h1.SOURCES) or
            sum(item['stage'] == 'probe' for item in rows.values()) != 1 or
            value['stages'][-1]['stage'] != 'probe' or
            value['stages'][-1]['supplier'] != '__closure__'):
        raise ValueError('Exact thirteen suppliers and one final closure probe required')
    tools = value['produced_tools']
    if type(tools) is not dict or len(tools) > 64:
        raise ValueError('Finite registered produced-role subset required')
    output_paths, producer_keys = set(), set()
    for role, item in tools.items():
        h1._text(role, 'registered produced role', 96)
        if re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', role) is None or role in PROGRAM_NAMES:
            raise ValueError('Unknown/aliased original versus produced role')
        h1._fields(item, ('producing_command_id', 'output', 'root'), 'registered produced tool')
        producer = item['producing_command_id']
        h1._text(producer, 'registered producing command', 96)
        if producer not in rows or rows[producer]['supplier'] != 'icu' or rows[producer]['stage'] != 'build-tool':
            raise ValueError('Produced ICU tool requires its registered build-tool stage')
        absolute = _relative_output(item['root'], item['output'])
        producer_key = (producer, item['output'].casefold())
        if producer_key in producer_keys:
            raise ValueError('Registered producer-relative output keys alias')
        producer_keys.add(producer_key)
        for original in (*[row['root'] for row in identity['inventories'].values()], identity['system_root']):
            if (absolute.casefold() == original.casefold() or
                    h1._inside(absolute.casefold(), original.casefold()) or
                    h1._inside(original.casefold(), item['root'].casefold())):
                raise ValueError('Produced output overlaps original tool/runtime roots')
        if absolute.casefold() in output_paths:
            raise ValueError('Registered produced outputs alias')
        output_paths.add(absolute.casefold())
        paths.add(item['root'], 'directory')
        paths.add(absolute, 'file')
    return rows


def _command(value, registration, identity, paths, indices, index):
    h1 = legacy()
    h1._fields(value, h1.COMMAND_FIELDS, 'D2 literal command')
    selected = value['program']
    if type(selected) is not dict or type(selected.get('kind')) is not str:
        raise ValueError('Closed tagged D2 program required')
    if selected['kind'] == 'original':
        h1._fields(selected, ('kind', 'role', 'declaration'), 'original D2 program')
        h1._text(selected['role'], 'original program role', 96)
        if selected['role'] not in PROGRAM_NAMES: raise ValueError('Unknown H2 original role')
        h1._equal(selected['declaration'], identity['programs'][selected['role']], 'H2 original declaration')
        program_path = selected['declaration']['path']
    elif selected['kind'] == 'produced':
        h1._fields(selected, ('kind', 'role', 'producing_command_id', 'output'), 'produced D2 program')
        h1._text(selected['role'], 'produced role', 96)
        if selected['role'] not in registration['produced_tools']:
            raise ValueError('Unregistered produced program role')
        item = registration['produced_tools'][selected['role']]
        h1._equal(selected['producing_command_id'], item['producing_command_id'], 'registered producer')
        h1._equal(selected['output'], item['output'], 'registered producer output')
        if indices[item['producing_command_id']] >= index or value['supplier'] != 'icu':
            raise ValueError('Produced ICU program must join a strictly earlier producer')
        program_path = _relative_output(item['root'], item['output'])
    else:
        raise ValueError('Unsupported D2 program origin')
    h1._array(value['argv'], 'literal argv', 512, 1)
    for argument in value['argv']: h1._safe_argument(argument)
    if value['argv'][0] != program_path:
        raise ValueError('D2 executable/argv mismatch')
    paths.add(value['cwd'], 'directory')
    environment = value['environment']
    if type(environment) is not dict or not 1 <= len(environment) <= 128:
        raise ValueError('Explicit complete D2 environment required')
    seen = set()
    for name, item in environment.items():
        if (re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,95}', name) is None or
                name.casefold() in seen or name.upper() in
                ('CL', '_CL_', 'LINK', '_LINK_', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS')):
            raise ValueError('Ambient or aliased D2 command environment')
        seen.add(name.casefold()); h1._safe_argument(item)
        if name.upper() == 'PATH':
            for directory in item.split(';'): paths.add(directory, 'directory')
        elif name.upper() == 'SYSTEMROOT':
            paths.add(item, 'directory')
            h1._equal(item, identity['system_root'], 'selected H2 SystemRoot')
    if not {'path', 'systemroot'} <= seen:
        raise ValueError('Explicit PATH and SystemRoot required')
    if value['initial_cache'] is not None:
        h1._reference(value['initial_cache'], 'initial cache', paths)
    h1._array(value['response_files'], 'response files', 64)
    responses = []
    for item in value['response_files']:
        h1._reference(item, 'response content', paths); responses.append(item['path'])
    if len(set(responses)) != len(responses) or [arg[1:] for arg in value['argv'] if arg.startswith('@')] != responses:
        raise ValueError('Exact ordered response-file argv/content pins required')
    h1._equal(value['log_policy'], 'stdout-stderr-combined', 'D2 log policy')


def _produced_outputs(value, command_id, registration):
    h1 = legacy()
    expected = {item['output']: (role, item) for role, item in registration['produced_tools'].items()
                if item['producing_command_id'] == command_id}
    h1._fields(value, expected, 'exact registered produced outputs')
    for relative, item in value.items():
        role, registered = expected[relative]
        h1._fields(item, ('role', 'program', 'inspection_subject_sha256', 'runtime_subject_sha256'),
                   'original closed produced PE evidence')
        h1._equal(item['role'], role, 'produced output role')
        h1._reference(item['program'], 'produced program')
        h1._equal(item['program']['path'], _relative_output(registered['root'], relative),
                  'produced program path')
        h1._pin(item['inspection_subject_sha256'], 'actual PE inspection subject')
        h1._pin(item['runtime_subject_sha256'], 'actual produced runtime subject')


def _resolved(actual, declaration, expected, identity, closed):
    h1 = legacy()
    tag = declaration['program']
    role = tag['role']
    if tag['kind'] == 'original':
        wanted = {'kind': 'original', 'role': role, 'program': identity['programs'][role],
                  **expected['original_program_evidence'][role]}
    else:
        producer = closed.get(tag['producing_command_id'])
        if producer is None:
            raise ValueError('Produced executable lacks an earlier closed producing command')
        output = producer['produced_outputs'][tag['output']]
        wanted = {'kind': 'produced', 'role': role,
            'producing_command_id': tag['producing_command_id'], 'output': tag['output'],
            **{key: output[key] for key in ('program', 'inspection_subject_sha256', 'runtime_subject_sha256')},
            'output_subject_sha256': producer['output_subject_sha256']}
    h1._equal(actual, wanted, 'resolved D2 original/produced program')
    return actual['program']


def validate_receipt(value, expected, identity):
    """Pure D2 consistency only; expected registration is not factory authority."""
    h1 = legacy()
    h1.encoded(value); h1.encoded(expected)
    identity = toolchain_identity(identity)
    h1._fields(expected, ('bindings', 'commands', 'prefix', 'libraries', 'probe',
                         'registration', 'original_program_evidence'), 'D2 independent expectations')
    h1._fields(value, ('schema_version', 'kind', 'target', 'scope', 'bindings', 'commands',
                     'prefix', 'libraries', 'postflight', 'probe', 'facts'), 'D2 receipt')
    for key, wanted in (('schema_version', 2), ('kind', RECEIPT_KIND), ('target', TARGET), ('scope', h1.SCOPE)):
        h1._equal(value[key], wanted, 'D2 ' + key)
    paths = _identity_paths(identity)
    h1._bindings(expected['bindings'], paths)
    h1._equal(expected['bindings']['toolchain_identity_sha256'],
              hashlib.sha256(encoded(identity)).hexdigest(), 'independent H2 digest')
    h1._prefix(expected['prefix'], paths)
    _original_evidence(expected['original_program_evidence'], identity, paths)
    h1._array(expected['commands'], 'expected D2 commands', h1.MAX_COMMANDS, 1)
    for command in expected['commands']: h1._fields(command, h1.COMMAND_FIELDS, 'D2 expected command')
    _registration(expected['registration'], expected['commands'], identity, paths)
    indices = {item['id']: index for index, item in enumerate(expected['commands'])}
    for index, command in enumerate(expected['commands']):
        _command(command, expected['registration'], identity, paths, indices, index)
    h1._libraries(expected['libraries'], expected['bindings'], expected['prefix'], paths, False)
    h1._probe(expected['probe'], expected['commands'], expected['libraries'], paths)
    for key in ('bindings', 'prefix', 'probe'): h1._equal(value[key], expected[key], 'original D2 ' + key)
    h1._array(value['commands'], 'actual D2 commands', h1.MAX_COMMANDS, 1)
    if len(value['commands']) != len(expected['commands']): raise ValueError('Incomplete D2 stages')
    closed = {}
    for actual, declaration in zip(value['commands'], expected['commands']):
        h1._fields(actual, h1.COMMAND_FIELDS + ('logs', 'output_subject_sha256', 'job',
                       'resolved_program', 'produced_outputs'), 'D2 command observations')
        h1._equal({key: actual[key] for key in h1.COMMAND_FIELDS}, declaration, 'registered D2 literal command')
        h1._fields(actual['logs'], ('combined',), 'original D2 combined log')
        h1._reference(actual['logs']['combined'], 'original D2 log')
        if actual['logs']['combined']['path'].casefold() in paths.entries:
            raise ValueError('D2 log aliases another original input/output')
        h1._reference(actual['logs']['combined'], 'original D2 log', paths)
        h1._pin(actual['output_subject_sha256'], 'closed D2 output subject')
        program = _resolved(actual['resolved_program'], declaration, expected, identity, closed)
        h1._equal(program['path'], declaration['argv'][0], 'resolved D2 execution path')
        execution = {**declaration, 'program': program}
        h1._job(actual['job'], execution)
        _produced_outputs(actual['produced_outputs'], declaration['id'], expected['registration'])
        closed[declaration['id']] = actual
    h1._libraries(value['libraries'], value['bindings'], value['prefix'], paths, True)
    h1._equal({target: {key: item for key, item in record.items() if key != 'inspection'}
               for target, record in value['libraries'].items()}, expected['libraries'], 'D2 library map')
    h1._fields(value['postflight'], ('toolchain_identity_sha256', 'sources'), 'D2 frozen postflight')
    h1._equal(value['postflight']['toolchain_identity_sha256'],
              expected['bindings']['toolchain_identity_sha256'], 'unchanged H2 postflight')
    h1._equal(value['postflight']['sources'], {name: expected['bindings']['sources'][name]['source_subject_sha256']
                                             for name in h1.SOURCES}, 'unchanged D2 sources')
    h1._fields(value['facts'], h1.FALSE_FACTS, 'unqualified D2 facts')
    for key in h1.FALSE_FACTS: h1._equal(value['facts'][key], False, 'unqualified D2 ' + key)
    return copy.deepcopy(value)


def dependency_receipt(declared_facts, expected, identity):
    return validate_receipt(declared_facts, expected, identity)


def validate_dependency_receipt(raw, expected_pin, expected, identity):
    h1 = legacy()
    h1._pin(expected_pin, 'D2 receipt')
    value = h1.parse_document(raw)
    if hashlib.sha256(raw).hexdigest() != expected_pin: raise ValueError('D2 receipt SHA256 mismatch')
    return validate_receipt(value, expected, identity)
