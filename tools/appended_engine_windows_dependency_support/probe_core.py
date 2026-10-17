"""Private pure probe-object witness candidate; never native admission.

All bytes are bounded caller-supplied metadata or inert fixtures. No filesystem,
process, compiler, old controller/proof, SDK or publication import occurs here.
An original sealed owned-compile constructor is still unfinished source.
"""
import copy
import hashlib
import json
import re
import struct

SOURCE_SHA256 = 'd71938060a67c63c3557d1c45c98fe9039462a31e122d47cc0a4dc859e95b4ca'
KIND = 'foundation-native-engine-windows-static-probe-object-witness-v1'
PLAN_KIND = 'foundation-native-engine-windows-static-probe-object-plan-v1'
MISSING_CONSTRUCTOR = 'windows-static-probe-original-compile-owned-witness-constructor'
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
MAX_DOCUMENT = 4 * 1024 * 1024
MAX_OBJECT_BYTES = 4 * 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 65536
MAX_SECTIONS = 64
MAX_SYMBOLS = 4096
MAX_RELOCATIONS = 65536
MAX_STRING_BYTES = 1024 * 1024
MAX_JSON_NODES = 100000
PROGRAMS = {'compiler': 'clang-cl.exe', 'linker': 'lld-link.exe',
    'archiver': 'llvm-lib.exe', 'resource_compiler': 'llvm-rc.exe',
    'manifest_tool': 'llvm-mt.exe', 'cmake': 'cmake.exe', 'ninja': 'ninja.exe',
    'python': 'python.exe', 'perl': 'perl.exe', 'ruby': 'ruby.exe', 'gperf': 'gperf.exe'}
FALSE_FACTS = ('production_eligible', 'engine_execution', 'native_runtime_qualified', 'kernel_rebuild')
IDENTITY_FIELDS = ('schema_version', 'kind', 'target', 'policy', 'inventories', 'programs',
    'builtins', 'crt_libraries', 'include_directories', 'library_directories', 'system_root')
DECLARATION_FIELDS = ('id', 'stage', 'program', 'argv', 'cwd', 'environment')
WITNESS_FIELDS = ('schema_version', 'kind', 'target', 'scope', 'dependency_receipt',
    'toolchain_identity_sha256', 'source', 'command', 'object', 'inspection', 'postflight', 'facts')


class MissingSource(ValueError):
    pass


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Closed ' + label + ' fields required')
    return value


def _int(value, label, low=0, high=2**31 - 1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Bounded exact integer required: ' + label)
    return value


def _pin(value):
    if (type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None or
            value == '0' * 64):
        raise ValueError('Nonzero canonical SHA256 required')
    return value


def _bytes(raw, maximum, label, minimum=1):
    if type(raw) is not bytes or not minimum <= len(raw) <= maximum:
        raise ValueError('Bounded original bytes required: ' + label)
    return raw


def _path(value):
    if (type(value) is not str or not 4 <= len(value) <= 4096 or
            not value.isascii() or re.match(r'^[A-Z]:/[^/]', value) is None or
            any(ord(c) < 32 or ord(c) >= 127 for c in value) or
            any(c in value for c in '\\;"$@~<>|?*') or value.endswith('/')):
        raise ValueError('Canonical local Windows path required')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
    reserved.update('COM' + str(i) for i in range(1, 10))
    reserved.update('LPT' + str(i) for i in range(1, 10))
    for part in value[3:].split('/'):
        if (not part or part in ('.', '..') or ':' in part or part.endswith(('.', ' ')) or
                part.split('.')[0].upper() in reserved):
            raise ValueError('Aliased or reserved Windows path')
    return value


def _ref(value):
    _fields(value, ('path', 'sha256'), 'reference')
    _path(value['path']); _pin(value['sha256'])
    return value


def _release(value):
    if type(value) is not str or len(value) > 128 or re.fullmatch(
            r'(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){1,3}', value) is None:
        raise ValueError('Canonical numeric release required')
    return tuple(_int(int(part), 'version component') for part in value.split('.'))


def _equal(actual, expected, label):
    if encoded(actual) != encoded(expected):
        raise ValueError('Mismatched ' + label)


def _tree(value, depth=0, budget=None):
    if budget is None:
        budget = [MAX_JSON_NODES, MAX_DOCUMENT]
    budget[0] -= 1
    budget[1] -= 8 + depth * 2
    if depth > 32 or budget[0] < 0 or budget[1] < 0:
        raise ValueError('JSON pre-serialization graph bound')
    if type(value) is str:
        if len(value) > 4096 or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError('Bounded JSON text required')
        budget[1] -= len(value) * 12 + 2
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError('JSON string key required')
            _tree(key, depth + 1, budget)
            _tree(item, depth + 1, budget)
    elif type(value) is list:
        for item in value:
            _tree(item, depth + 1, budget)
    elif type(value) is int:
        _int(value, 'JSON number', -(2**63), 2**63 - 1)
        budget[1] -= 24
    elif value is not None and type(value) is not bool:
        raise ValueError('Unsupported JSON scalar')
    if budget[1] < 0:
        raise ValueError('JSON pre-serialization byte bound')


def encoded(value):
    _tree(value)
    raw = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                      allow_nan=False) + '\n').encode('ascii')
    _bytes(raw, MAX_DOCUMENT, 'canonical JSON')
    return raw


def _document(raw, pin):
    _bytes(raw, MAX_DOCUMENT, 'document')
    _pin(pin)
    if _hash(raw) != pin:
        raise ValueError('Original document pin differs')
    depth, quoted, escaped, scalar, tokens = 0, False, False, False, 0
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted, scalar = True, False
            tokens += 1
        elif byte in (91, 123):
            depth += 1
            scalar = False
            tokens += 1
            if depth > 32:
                raise ValueError('JSON depth before allocation')
        elif byte in (93, 125):
            depth -= 1
            scalar = False
            if depth < 0:
                raise ValueError('Unbalanced JSON')
        elif byte in (9, 10, 13, 32, 44, 58):
            scalar = False
        elif not scalar:
            scalar = True
            tokens += 1
        if tokens > MAX_JSON_NODES:
            raise ValueError('JSON node budget before allocation')
    if depth or quoted:
        raise ValueError('Incomplete JSON')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    def integer(text):
        if len(text.lstrip('-')) > 19:
            raise ValueError('JSON integer length')
        return _int(int(text), 'JSON integer', -(2**63), 2**63 - 1)
    def reject(text):
        raise ValueError('Noninteger/nonfinite JSON')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_int=integer, parse_float=reject, parse_constant=reject)
        if encoded(value) != raw:
            raise ValueError('Original canonical document required')
        return value
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original JSON') from error


def _identity(raw, pin):
    value = _fields(_document(raw, pin), IDENTITY_FIELDS, 'H')
    _equal(value['schema_version'], 1, 'H schema')
    _equal(value['kind'], 'foundation-native-engine-windows-toolchain-identity-v1', 'H kind')
    _equal(value['target'], TARGET, 'H target')
    _fields(value['programs'], PROGRAMS, 'H programs')
    _fields(value['inventories'], ('llvm', 'msvc_stl', 'windows_sdk', 'host_generators'), 'H inventories')
    for role, inventory in value['inventories'].items():
        _fields(inventory, ('root', 'version', 'subject_sha256'), role + ' inventory')
        _path(inventory['root']); _pin(inventory['subject_sha256'])
        if type(inventory['version']) is not str or not 1 <= len(inventory['version']) <= 128:
            raise ValueError('Bounded inventory release declaration required')
    seen = set()
    for role, basename in PROGRAMS.items():
        item = _fields(value['programs'][role], ('path', 'sha256', 'version'), 'H program')
        _ref({key: item[key] for key in ('path', 'sha256')}); _release(item['version'])
        if item['path'].rsplit('/', 1)[-1] != basename or item['path'].casefold() in seen:
            raise ValueError('Exact distinct H program role required')
        seen.add(item['path'].casefold())
    llvm = value['inventories']['llvm']
    _fields(llvm, ('root', 'version', 'subject_sha256'), 'LLVM inventory')
    _path(llvm['root']); _pin(llvm['subject_sha256'])
    release = _release(llvm['version'])
    if len(release) != 3 or release < (19, 1, 7):
        raise ValueError('H LLVM floor')
    for role in ('compiler', 'linker'):
        program = value['programs'][role]
        if (program['version'] != llvm['version'] or
                not program['path'].startswith(llvm['root'] + '/')):
            raise ValueError('H compiler/linker release or LLVM root differs')
    _path(value['system_root'])
    # This extracts only the selected H context. Full H native semantics and
    # inventory/tool-version authority remain the unchanged caller's obligation.
    return value


def _limits(value):
    _fields(value, ('wall_milliseconds', 'maximum_processes',
                    'maximum_output_bytes', 'maximum_log_bytes'), 'limits')
    for key in value:
        _int(value[key], key, 1, 24 * 3600 * 1000 if key == 'wall_milliseconds' else
             65536 if key == 'maximum_processes' else MAX_OBJECT_BYTES + MAX_LOG_BYTES + MAX_SOURCE_BYTES)
    if value['maximum_log_bytes'] > MAX_LOG_BYTES:
        raise ValueError('Log limit exceeds private source cap')
    return copy.deepcopy(value)


def plan(identity_raw, identity_pin, maintained_source_path, workspace_root, limits):
    identity = _identity(identity_raw, identity_pin)
    _path(maintained_source_path); _path(workspace_root)
    selected_limits = _limits(limits)
    compiled = workspace_root + '/probe/static-closure-probe.cpp'
    object_path = workspace_root + '/probe/static-closure-probe.obj'
    log_path = workspace_root + '/logs/probe-compile.log'
    if (maintained_source_path.casefold() == workspace_root.casefold() or
            maintained_source_path.casefold().startswith(workspace_root.casefold() + '/') or
            workspace_root.casefold().startswith(maintained_source_path.casefold() + '/')):
        raise ValueError('Owned source copy must be separate from maintained input')
    protected = [item['root'] for item in identity['inventories'].values()]
    protected += [item['path'] for item in identity['programs'].values()]
    protected.append(identity['system_root'])
    output = workspace_root.casefold()
    if any(output == item.casefold() or output.startswith(item.casefold() + '/') or
           item.casefold().startswith(output + '/') for item in protected):
        raise ValueError('Owned workspace overlaps a protected H input')
    parents = sorted({item['path'].rsplit('/', 1)[0] for item in identity['programs'].values()})
    if len({item.casefold() for item in parents}) != len(parents):
        raise ValueError('Aliased H PATH roots')
    compiler = copy.deepcopy(identity['programs']['compiler'])
    command = {'id': 'closure-probe-compile', 'stage': 'probe-compile', 'program': compiler,
        'argv': [compiler['path'], '/c', '/TP', '/MT', '/Od', '/Zl', '/X', '/Y-', '/WX',
            '-Werror=unknown-argument', '/clang:--no-default-config',
            '/clang:--target=x86_64-pc-windows-msvc', '/Fo' + object_path, compiled],
        'cwd': workspace_root, 'environment': {'SystemRoot': identity['system_root'],
            'PATH': ';'.join(parents), 'TEMP': workspace_root + '/tmp', 'TMP': workspace_root + '/tmp'}}
    return {'schema_version': 1, 'kind': PLAN_KIND, 'toolchain_identity_sha256': identity_pin,
        'source': {'maintained': {'path': maintained_source_path, 'sha256': SOURCE_SHA256},
                   'compiled': {'path': compiled, 'sha256': SOURCE_SHA256}},
        'command': command, 'object_path': object_path, 'log_path': log_path, 'limits': selected_limits}


def inspect_object(raw):
    """Inspect bounded standard COFF metadata; never load or run section bytes."""
    _bytes(raw, MAX_OBJECT_BYTES, 'COFF object', 20)
    if raw.startswith((b'BC\xc0\xde', b'\xde\xc0\x17\x0b', b'!<arch>\n', b'MZ')):
        raise ValueError('Bitcode/archive/image is not a standard COFF object')
    machine, sections, stamp, symbols_at, symbols, optional, flags = struct.unpack_from('<HHIIIHH', raw)
    if machine != 0x8664 or not 1 <= sections <= MAX_SECTIONS or optional != 0 or flags & 0x2002:
        raise ValueError('Native AMD64 standard COFF object required, not import/bigobj/image')
    if symbols > MAX_SYMBOLS:
        raise ValueError('COFF symbol count before table allocation')
    header_end = 20 + sections * 40
    if header_end > len(raw):
        raise ValueError('Truncated section table')
    ranges = [(0, header_end, 'headers')]
    def span(start, size, label):
        if type(start) is not int or type(size) is not int or start < header_end or size < 0 or start > len(raw) - size:
            raise ValueError('Truncated/impossible COFF ' + label)
        if size:
            ranges.append((start, start + size, label))
    strings = b''
    if symbols_at:
        symbol_bytes = symbols * 18
        span(symbols_at, symbol_bytes, 'symbols')
        string_at = symbols_at + symbol_bytes
        if string_at > len(raw) - 4:
            raise ValueError('Truncated COFF string table length')
        string_size = struct.unpack_from('<I', raw, string_at)[0]
        if not 4 <= string_size <= MAX_STRING_BYTES:
            raise ValueError('COFF string-table bound')
        span(string_at, string_size, 'strings')
        strings = raw[string_at:string_at + string_size]
    elif symbols:
        raise ValueError('Missing COFF symbol table')
    def string(offset):
        if not 4 <= offset < len(strings):
            raise ValueError('Invalid COFF string offset')
        end = strings.find(b'\0', offset)
        if end < 0 or end - offset > 4096:
            raise ValueError('Unterminated/oversize COFF name')
        return ascii_name(strings[offset:end])
    def ascii_name(data):
        if not data or any(byte < 32 or byte > 126 for byte in data):
            raise ValueError('ASCII COFF name required')
        return data.decode('ascii')
    def name(data, section=False):
        if section and data.startswith(b'/'):
            offset = data.rstrip(b'\0')[1:]
            if not offset.isdigit() or len(offset) > 10:
                raise ValueError('Invalid long section name')
            return string(int(offset))
        if not section and data[:4] == b'\0' * 4:
            return string(struct.unpack_from('<I', data, 4)[0])
        return ascii_name(data.split(b'\0', 1)[0])
    descriptors, relocations = [], 0
    for index in range(sections):
        row = struct.unpack_from('<8sIIIIIIHHI', raw, 20 + index * 40)
        section_name = name(row[0], section=True)
        if section_name.casefold().startswith(('.lto', '.gnu.lto', '.llvmbc', '.llvmcmd', '.llvm.lto')):
            raise ValueError('LTO/bitcode section is not admitted')
        allowed = ('.text', '.data', '.bss', '.xdata', '.pdata', '.drectve', '.debug$S', '.debug$T', '.llvm_addrsig')
        if section_name not in allowed and not section_name.startswith(('.text$', '.data$', '.rdata$')) and section_name != '.rdata':
            raise ValueError('Unreviewed standard COFF section')
        size, data_at, reloc_at, lines_at, reloc_count, line_count, characteristics = row[3:]
        if line_count or lines_at or characteristics & 0x01000000:
            raise ValueError('Unreviewed line/overflow-relocation table')
        relocations += reloc_count
        if relocations > MAX_RELOCATIONS:
            raise ValueError('COFF relocation count before table allocation')
        if data_at:
            span(data_at, size, 'section data')
        elif size and not characteristics & 0x80:
            raise ValueError('Missing initialized section data')
        if reloc_count:
            span(reloc_at, reloc_count * 10, 'relocations')
        elif reloc_at:
            raise ValueError('Unexpected empty relocation pointer')
        descriptors.append((section_name, size, data_at, reloc_at, reloc_count, row[2]))
    ordered = sorted(ranges)
    if any(first[1] > second[0] for first, second in zip(ordered, ordered[1:])):
        raise ValueError('Overlapping COFF tables or data')
    index, primary_symbols = 0, set()
    while index < symbols:
        primary_symbols.add(index)
        at = symbols_at + index * 18
        name(raw[at:at + 8])
        value, section, kind, storage, auxiliary = struct.unpack_from('<IhHBB', raw, at + 8)
        if section > sections or section < -2 or index + auxiliary >= symbols:
            raise ValueError('Invalid COFF symbol/auxiliary range')
        index += 1 + auxiliary
    # Source-specific subset from the official PE/COFF x64 relocation table.
    # CLR token and span/pair forms need separate semantics and remain rejected.
    widths = {0: 0, 1: 8, 2: 4, 3: 4, 4: 4, 5: 4, 6: 4, 7: 4,
              8: 4, 9: 4, 10: 2, 11: 4, 12: 1}
    for section_name, size, data_at, reloc_at, reloc_count, virtual_address in descriptors:
        for index in range(reloc_count):
            address, symbol, relocation = struct.unpack_from('<IIH', raw, reloc_at + index * 10)
            width = widths.get(relocation)
            offset = address - virtual_address
            if (symbol not in primary_symbols or width is None or
                    offset < 0 or offset > size - width):
                raise ValueError('Invalid COFF relocation symbol/type/field extent')
        if section_name == '.drectve' and size:
            try:
                directives = raw[data_at:data_at + size].rstrip(b'\0').decode('ascii').split()
            except UnicodeError as error:
                raise ValueError('Non-ASCII COFF directives') from error
            for token in directives:
                if (not token.lower().startswith('/export:') or
                        token[len('/export:'):] != 'foundation_native_dependency_link_probe'):
                    raise ValueError('Unreviewed COFF linker directive')
    return {'object_sha256': _hash(raw), 'format': 'coff-object', 'machine': 'x86_64',
            'section_count': sections, 'symbol_count': symbols, 'optional_header_bytes': optional}


def output_subject(selected_plan, object_raw, log_raw):
    _bytes(object_raw, MAX_OBJECT_BYTES, 'object')
    _bytes(log_raw, MAX_LOG_BYTES, 'closed log', 0)
    value = {'source': selected_plan['source']['compiled'],
        'object': {'path': selected_plan['object_path'], 'sha256': _hash(object_raw)},
        'log': {'path': selected_plan['log_path'], 'sha256': _hash(log_raw),
                'bytes': len(log_raw), 'mode': 0o644}}
    return _hash(encoded(value))


def _job(value, declaration, limits, minimum_output):
    names = ('owner', 'launch_intent_sha256', 'image', 'launch_suspended',
        'assigned_before_resume', 'breakaway_allowed', 'kill_on_close', 'exit_code',
        'elapsed_milliseconds', 'wall_limit_milliseconds', 'process_count', 'process_limit',
        'peak_output_bytes', 'output_limit_bytes', 'active_processes_at_join',
        'streams_closed', 'join_completed', 'owner_closed')
    _fields(value, names, 'W Job declaration')
    _equal(value['owner'], 'windows-job-v1', 'Job owner')
    _equal(value['launch_intent_sha256'], _hash(encoded(declaration)), 'original literal compile intent')
    _equal(value['image'], {key: declaration['program'][key] for key in ('path', 'sha256')}, 'Job image')
    for key in ('launch_suspended', 'assigned_before_resume', 'kill_on_close',
                'streams_closed', 'join_completed', 'owner_closed'):
        _equal(value[key], True, 'closed Job ' + key)
    _equal(value['breakaway_allowed'], False, 'no-breakaway')
    for key in ('exit_code', 'active_processes_at_join'):
        _equal(value[key], 0, key)
    for key, limit, selected, minimum in (
            ('elapsed_milliseconds', 'wall_limit_milliseconds', 'wall_milliseconds', 0),
            ('process_count', 'process_limit', 'maximum_processes', 1),
            ('peak_output_bytes', 'output_limit_bytes', 'maximum_output_bytes', minimum_output)):
        _int(value[key], key, minimum, limits[selected])
        _equal(value[limit], limits[selected], 'selected Job limit')
        if key == 'elapsed_milliseconds' and value[key] >= limits[selected]:
            raise ValueError('Compile deadline exhausted')
    # process_count remains a sampled declaration, not a pre-resume process cap.


def _dependency(raw, pin, identity, identity_pin, object_path):
    value = _fields(_document(raw, pin), ('schema_version', 'kind', 'target', 'scope', 'bindings',
        'commands', 'prefix', 'libraries', 'postflight', 'probe', 'facts'), 'D v1 envelope')
    _equal(value['schema_version'], 1, 'D schema')
    _equal(value['kind'], 'foundation-native-engine-windows-dependencies-build-v1', 'D kind')
    _equal(value['target'], TARGET, 'D target')
    _equal(value['scope'], 'unqualified-dependency-candidate', 'D scope')
    _equal(value['facts'], {name: False for name in FALSE_FACTS}, 'D false claims')
    if type(value['bindings']) is not dict or type(value['postflight']) is not dict:
        raise ValueError('Original D/H bindings required')
    _equal(value['bindings'].get('toolchain_identity_sha256'), identity_pin, 'D/H binding')
    _equal(value['postflight'].get('toolchain_identity_sha256'), identity_pin, 'D/H postflight')
    commands = value['commands']
    if type(commands) is not list or not 1 <= len(commands) <= 512:
        raise ValueError('Bounded original D command list required')
    command = commands[-1]
    fields = ('id', 'supplier', 'stage', 'program', 'argv', 'cwd', 'environment', 'initial_cache',
              'response_files', 'log_policy', 'logs', 'output_subject_sha256', 'job')
    _fields(command, fields, 'D original link command')
    _equal(command['program'], identity['programs']['linker'], 'D selected linker')
    _equal(command['stage'], 'probe', 'D probe stage')
    _equal(command['supplier'], '__closure__', 'D closure supplier')
    _equal(command['response_files'], [], 'D direct arguments')
    _fields(value['probe'], ('command_id', 'library_targets', 'link_inputs', 'output'), 'D probe')
    _equal(value['probe']['command_id'], command['id'], 'D probe command id')
    arguments = command['argv']
    if (type(arguments) is not list or not 2 <= len(arguments) <= 512 or
            any(type(item) is not str or len(item) > 4096 for item in arguments) or
            arguments[0] != identity['programs']['linker']['path'] or
            arguments.count(object_path) != 1 or
            any(item.startswith('@') for item in arguments) or
            any(item.lower().endswith('.obj') and item != object_path for item in arguments[1:])):
        raise ValueError('Exactly one actual W object must join the direct D link operand')
    # The existing unchanged proof/native controller remains responsible for all
    # thirteen suppliers, twenty WHOLEARCHIVE libraries and full D/H semantics.
    return value


def validate_witness(raw_witness, witness_pin, *, identity_raw, identity_pin, dependency_raw,
        dependency_pin, dependency_path, maintained_source_raw, compiled_source_raw,
        object_raw, log_raw, maintained_source_path, workspace_root, limits):
    selected_plan = plan(identity_raw, identity_pin, maintained_source_path, workspace_root, limits)
    identity = _identity(identity_raw, identity_pin)
    value = _fields(_document(raw_witness, witness_pin), WITNESS_FIELDS, 'W')
    _equal(value['schema_version'], 1, 'W schema')
    _equal(value['kind'], KIND, 'W kind')
    _equal(value['target'], TARGET, 'W target')
    _equal(value['scope'], 'unqualified-static-probe-object', 'W scope')
    _path(dependency_path)
    _equal(value['dependency_receipt'], {'path': dependency_path, 'sha256': dependency_pin}, 'original D ref')
    _equal(value['toolchain_identity_sha256'], identity_pin, 'W/H pin')
    _equal(value['source'], selected_plan['source'], 'maintained/compiled source declaration')
    for raw in (maintained_source_raw, compiled_source_raw):
        _bytes(raw, MAX_SOURCE_BYTES, 'original probe source')
        if _hash(raw) != SOURCE_SHA256:
            raise ValueError('Original maintained or copied probe source pin differs')
    inspection = inspect_object(object_raw)
    _equal(value['inspection'], inspection, 'independent actual COFF inspection')
    object_ref = {'path': selected_plan['object_path'], 'sha256': inspection['object_sha256']}
    _equal(value['object'], object_ref, 'actual object ref')
    _bytes(log_raw, MAX_LOG_BYTES, 'original complete compile log', 0)
    if len(log_raw) > selected_plan['limits']['maximum_log_bytes']:
        raise ValueError('Compile log exceeds selected limit')
    command = _fields(value['command'], DECLARATION_FIELDS + ('logs', 'output_subject_sha256', 'job'), 'W compile command')
    _equal({key: command[key] for key in DECLARATION_FIELDS}, selected_plan['command'], 'independent fixed compile declaration')
    log = {'path': selected_plan['log_path'], 'sha256': _hash(log_raw), 'bytes': len(log_raw), 'mode': 0o644}
    _equal(command['logs'], {'combined': log}, 'actual combined closed log bytes')
    _equal(command['output_subject_sha256'], output_subject(selected_plan, object_raw, log_raw), 'actual compile subject')
    minimum_output = len(compiled_source_raw) + len(object_raw) + len(log_raw)
    _job(command['job'], selected_plan['command'], selected_plan['limits'], minimum_output)
    _equal(value['postflight'], {'source_sha256': SOURCE_SHA256,
        'toolchain_identity_sha256': identity_pin, 'object_sha256': inspection['object_sha256']}, 'W postflight')
    _equal(value['facts'], {name: False for name in FALSE_FACTS}, 'W false facts')
    dependency = _dependency(dependency_raw, dependency_pin, identity, identity_pin, object_ref['path'])
    forbidden = {item['path'].casefold() for item in value['source'].values()}
    forbidden.update((selected_plan['log_path'].casefold(), dependency_path.casefold()))
    forbidden.update(item['path'].casefold() for item in identity['programs'].values())
    probe_output = _ref(dependency['probe']['output'])['path']
    forbidden.add(probe_output.casefold())
    for item in dependency['probe']['link_inputs']:
        forbidden.add(_ref(item)['path'].casefold())
    if object_ref['path'].casefold() in forbidden:
        raise ValueError('Probe object aliases an independent input/output')
    return {'native_admitted': False, 'object': copy.deepcopy(object_ref),
        'inspection': inspection, 'source_sha256': SOURCE_SHA256,
        'toolchain_identity_sha256': identity_pin, 'dependency_receipt_sha256': dependency_pin,
        'witness_sha256': witness_pin, 'missing_source': [MISSING_CONSTRUCTOR]}


def require_native_constructor():
    raise MissingSource(MISSING_CONSTRUCTOR)

