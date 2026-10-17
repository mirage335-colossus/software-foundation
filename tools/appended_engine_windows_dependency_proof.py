"""Pure Windows dependency declarations and original-receipt consistency checks.

Nothing in this module reads retained inputs, launches programs, or admits native
observations. In particular, ``actual_facts`` is a comparison input, not evidence
that its caller performed inventory/tool/CRT admission. Native admission belongs
to the controller; its explicit entry point is imported only when called.

Identity and receipt bytes use the project's sorted, indented ASCII JSON plus
one LF. The receipt's prefix subject excludes provenance, preventing a receipt /
provenance / full-inventory hash cycle. Receipt command observations describe the
existing no-breakaway Windows Job owner. ``process_count`` is the sampled peak
active count and ``process_limit`` its monitoring threshold, not a kernel process
cap. No memory-limit or release/runtime qualification is asserted.

The initial H/D schemas conservatively restrict Windows path declarations to
ASCII. Generic text remains Unicode. Python case folding is not a qualified
Windows filesystem name-identity algorithm; Unicode paths need a future native
identity policy before admission, rather than an approximate alias comparison.
"""

import copy
import hashlib
import json
import re
import unicodedata


MAX_DOCUMENT = 4 * 1024 * 1024
MAX_TEXT = 4096
MAX_COMMANDS = 512
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
IDENTITY_KIND = 'foundation-native-engine-windows-toolchain-identity-v1'
RECEIPT_KIND = 'foundation-native-engine-windows-dependencies-build-v1'
SCOPE = 'unqualified-dependency-candidate'
POLICY = {'build_type': 'Release', 'crt': 'static-mt',
          'cpu_baseline': 'x86_64-sse2',
          'os_floor_declaration': 'windows-10-1809-unqualified',
          'engine_cxx_standard': 23, 'lto': False}
INVENTORIES = ('llvm', 'msvc_stl', 'windows_sdk', 'host_generators')
PROGRAM_NAMES = {'compiler': 'clang-cl.exe', 'linker': 'lld-link.exe',
    'archiver': 'llvm-lib.exe', 'resource_compiler': 'llvm-rc.exe',
    'manifest_tool': 'llvm-mt.exe', 'cmake': 'cmake.exe', 'ninja': 'ninja.exe',
    'python': 'python.exe', 'perl': 'perl.exe', 'ruby': 'ruby.exe', 'gperf': 'gperf.exe'}
LLVM_PROGRAMS = frozenset(('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool'))
CRT_LIBRARIES = ('libcmt', 'libcpmt', 'libvcruntime', 'libucrt', 'oldnames')
SOURCES = ('icu', 'zlib', 'brotli', 'png', 'jpeg', 'webp', 'harfbuzz',
           'xml2', 'sqlite', 'openssl', 'nghttp2', 'psl', 'curl')
LIBRARY_SUPPLIERS = {'ICU::data': 'icu', 'ICU::i18n': 'icu', 'ICU::uc': 'icu',
    'ZLIB::ZLIB': 'zlib', 'Brotli::dec': 'brotli', 'Brotli::common': 'brotli',
    'PNG::PNG': 'png', 'JPEG::JPEG': 'jpeg', 'WebP::libwebp': 'webp',
    'WebP::demux': 'webp', 'WebP::sharpyuv': 'webp',
    'HarfBuzz::HarfBuzz': 'harfbuzz', 'HarfBuzz::ICU': 'harfbuzz',
    'LibXml2::LibXml2': 'xml2', 'SQLite3::SQLite3': 'sqlite',
    'OpenSSL::SSL': 'openssl', 'OpenSSL::Crypto': 'openssl',
    'FoundationNative::nghttp2': 'nghttp2', 'LibPSL::LibPSL': 'psl', 'CURL::libcurl': 'curl'}
SYSTEM_LINKS = frozenset(('advapi32', 'bcrypt', 'crypt32', 'iphlpapi', 'normaliz',
    'ole32', 'secur32', 'shell32', 'shlwapi', 'user32', 'version', 'winmm', 'ws2_32'))
FALSE_FACTS = ('production_eligible', 'engine_execution',
               'native_runtime_qualified', 'kernel_rebuild')
IDENTITY_FIELDS = ('schema_version', 'kind', 'target', 'policy', 'inventories',
    'programs', 'builtins', 'crt_libraries', 'include_directories',
    'library_directories', 'system_root')
COMMAND_FIELDS = ('id', 'supplier', 'stage', 'program', 'argv', 'cwd',
                  'environment', 'initial_cache', 'response_files', 'log_policy')
INSPECTION_FIELDS = ('archive_sha256', 'format', 'machine', 'member_count',
    'import_objects', 'foreign_objects', 'dynamic_crt_directives',
    'debug_crt_directives', 'lto_objects')


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Unsupported ' + label + ' fields')
    return value


def _text(value, label, maximum=MAX_TEXT):
    if (type(value) is not str or not value or len(value) > maximum or
            unicodedata.normalize('NFC', value) != value or any(
            ord(c) < 32 or 127 <= ord(c) <= 159 or
            0xD800 <= ord(c) <= 0xDFFF or 0xFDD0 <= ord(c) <= 0xFDEF or
            ord(c) & 0xFFFF in (0xFFFE, 0xFFFF) for c in value)):
        raise ValueError('Invalid Unicode/text: ' + label)
    return value


def _integer(value, label, minimum=0, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid integer: ' + label)
    return value


def _pin(value, label):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None or value == '0' * 64:
        raise ValueError('Independent nonzero SHA256 required: ' + label)
    return value


def _json_tree(value, depth=0, budget=None):
    if budget is None:
        budget = [100000, MAX_DOCUMENT]
    budget[0] -= 1
    # Charge escaped ASCII size before constructing the complete JSON string.
    # Include conservative indentation/separator overhead for each visited node.
    budget[1] -= 4 + depth * 2
    if depth > 32 or budget[0] < 0:
        raise ValueError('JSON nesting/count bound exceeded')
    if type(value) is str:
        _text(value, 'JSON string')
        budget[1] -= 2 + sum(2 if c in '\\"' else 1 if ord(c) < 128 else
                             6 if ord(c) <= 0xFFFF else 12 for c in value)
    elif type(value) is dict:
        for key, item in value.items():
            _text(key, 'JSON key')
            budget[1] -= 6 + depth * 2 + sum(2 if c in '\\"' else 1 if ord(c) < 128 else
                                           6 if ord(c) <= 0xFFFF else 12 for c in key)
            _json_tree(item, depth + 1, budget)
    elif type(value) is list:
        for item in value:
            _json_tree(item, depth + 1, budget)
    elif type(value) is int:
        _integer(value, 'JSON integer', -(2**63), 2**63 - 1)
        budget[1] -= len(str(value))
    elif value is not None and type(value) is not bool:
        raise ValueError('Unsupported JSON scalar')
    else:
        budget[1] -= 5
    if budget[1] < 0:
        raise ValueError('JSON document exceeds pre-serialization byte bound')


def encoded(value):
    """Return bounded canonical bytes; floats and noncanonical Unicode fail."""
    _json_tree(value)
    raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                      allow_nan=False) + '\n').encode('ascii')
    if len(raw) > MAX_DOCUMENT:
        raise ValueError('JSON document exceeds byte bound')
    return raw


def parse_document(raw):
    """Parse only original canonical bytes, rejecting duplicate keys and NaN."""
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_DOCUMENT:
        raise ValueError('Invalid JSON byte bound/type')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite JSON: ' + value)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=invalid)
        if encoded(value) != raw:
            raise ValueError('Original canonical JSON bytes required')
        return value
    except (UnicodeError, RecursionError, OverflowError, json.JSONDecodeError) as error:
        raise ValueError('Invalid JSON encoding/nesting') from error


def _equal(actual, wanted, label):
    # Python's True == 1 must never admit a schema/policy/target number.
    if encoded(actual) != encoded(wanted):
        raise ValueError('Mismatched ' + label)


def windows_path(value, label='Windows path'):
    """Validate an ASCII canonical local Windows path for the initial H/D schema."""
    _text(value, label)
    if (not value.isascii() or re.match(r'^[A-Z]:/[^/]', value) is None or '\\' in value or
            any(c in value for c in ';"$@~') or value.endswith('/')):
        raise ValueError('Explicit canonical local Windows path required: ' + label)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                *('COM' + str(i) for i in range(1, 10)),
                *('LPT' + str(i) for i in range(1, 10)),
                *('COM' + c for c in '¹²³'), *('LPT' + c for c in '¹²³')}
    for part in value[3:].split('/'):
        if (not part or part in ('.', '..') or part.endswith((' ', '.')) or
                any(c in part for c in ':<>|?*') or
                part.split('.')[0].rstrip(' .').upper() in reserved):
            raise ValueError('Aliased/nonportable Windows path: ' + label)
    return value


def _inside(path, root):
    return path.startswith(root + '/')


class _Paths:
    """Case-spelling and file/directory conflicts include implicit parents."""
    def __init__(self):
        self.entries = {}

    def add(self, path, kind, pin=None):
        windows_path(path)
        parts = path.split('/')
        for i in range(2, len(parts) + 1):
            name = '/'.join(parts[:i])
            selected_kind = kind if i == len(parts) else 'directory'
            selected_pin = pin if i == len(parts) else None
            old = self.entries.get(name.casefold())
            record = (name, selected_kind, selected_pin)
            if old is not None and old != record:
                raise ValueError('Conflicting Windows path spelling/kind/pin: ' + name)
            self.entries[name.casefold()] = record
        return path


def _reference(value, label, paths=None, program=False):
    _fields(value, ('path', 'sha256', 'version') if program else ('path', 'sha256'), label)
    windows_path(value['path'], label)
    _pin(value['sha256'], label)
    if program:
        _version(value['version'], label)
    if paths is not None:
        paths.add(value['path'], 'file', value['sha256'])
    return value


def _version(value, label):
    _text(value, label, 128)
    if re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){1,3}', value) is None:
        raise ValueError('Exact numeric release required: ' + label)
    return tuple(int(x) for x in value.split('.'))


def _array(value, label, maximum, minimum=0):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise ValueError('Invalid list bound/type: ' + label)
    return value


def _unique_strings(value, label, maximum, minimum=0):
    _array(value, label, maximum, minimum)
    for item in value:
        _text(item, label)
    if len(set(value)) != len(value):
        raise ValueError('Duplicate ' + label)
    return value


def toolchain_identity(declared_facts):
    """Construct H from declared facts only; perform no native SDK admission.

    ``declared_facts`` is the complete closed H object (including kind/schema).
    The returned object is an owned copy; no digest or output back-reference is
    added. Inventory subjects exclude provenance and are independent of D.
    """
    encoded(declared_facts)
    value = _fields(declared_facts, IDENTITY_FIELDS, 'toolchain identity')
    _equal(value['schema_version'], 1, 'toolchain schema')
    _equal(value['kind'], IDENTITY_KIND, 'toolchain kind')
    _equal(value['target'], TARGET, 'toolchain target')
    _equal(value['policy'], POLICY, 'toolchain policy')
    _fields(value['inventories'], INVENTORIES, 'toolchain inventories')
    paths = _Paths()
    roots = []
    for role in INVENTORIES:
        item = _fields(value['inventories'][role], ('root', 'version', 'subject_sha256'), role)
        root = windows_path(item['root'], role + ' root')
        _pin(item['subject_sha256'], role + ' subject')
        _text(item['version'], role + ' version', 128)
        if any(root.casefold() == other.casefold() or
               _inside(root.casefold(), other.casefold()) or
               _inside(other.casefold(), root.casefold()) for other in roots):
            raise ValueError('Inventory roots must be unique and disjoint')
        roots.append(root)
        paths.add(root, 'directory')
    llvm = value['inventories']['llvm']
    release = _version(llvm['version'], 'LLVM version')
    if len(release) != 3 or release < (19, 1, 7):
        raise ValueError('LLVM exact release must be at least 19.1.7')
    if re.fullmatch(r'14\.[0-9]+\.[0-9]+', value['inventories']['msvc_stl']['version']) is None:
        raise ValueError('Exact MSVC 14.x.y toolset required')
    if re.fullmatch(r'10\.0\.[0-9]+\.[0-9]+', value['inventories']['windows_sdk']['version']) is None:
        raise ValueError('Exact Windows SDK 10.0.x.y required')
    _fields(value['programs'], PROGRAM_NAMES, 'toolchain programs')
    selected_paths = set()
    for role, basename in PROGRAM_NAMES.items():
        item = _reference(value['programs'][role], role, paths, program=True)
        owner = 'llvm' if role in LLVM_PROGRAMS else 'host_generators'
        if (not _inside(item['path'], value['inventories'][owner]['root']) or
                item['path'].rsplit('/', 1)[-1] != basename or
                item['path'].casefold() in selected_paths):
            raise ValueError('Wrong or aliased program role: ' + role)
        selected_paths.add(item['path'].casefold())
        if role in LLVM_PROGRAMS and item['version'] != llvm['version']:
            raise ValueError('LLVM programs must share the same exact release')
    item = _reference(value['builtins'], 'LLVM builtins', paths)
    if (not _inside(item['path'], llvm['root']) or
            item['path'].rsplit('/', 1)[-1] != 'clang_rt.builtins-x86_64.lib'):
        raise ValueError('Explicit LLVM x64 builtins library required')
    _fields(value['crt_libraries'], CRT_LIBRARIES, 'static CRT libraries')
    for role in CRT_LIBRARIES:
        item = _reference(value['crt_libraries'][role], role, paths)
        owner = 'windows_sdk' if role == 'libucrt' else 'msvc_stl'
        if (not _inside(item['path'], value['inventories'][owner]['root']) or
                item['path'].rsplit('/', 1)[-1] != role + '.lib'):
            raise ValueError('Wrong static CRT role/owner: ' + role)
    for name in ('include_directories', 'library_directories'):
        for path in _unique_strings(value[name], name, 128, 1):
            paths.add(path, 'directory')
            if not any(_inside(path, value['inventories'][role]['root'])
                       for role in ('llvm', 'msvc_stl', 'windows_sdk')):
                raise ValueError('Search directory outside toolchain subjects')
    # SystemRoot is the independently selected native OS root, not an SDK root.
    paths.add(value['system_root'], 'directory')
    if any(value['system_root'].casefold() == root.casefold() or
           _inside(value['system_root'].casefold(), root.casefold()) or
           _inside(root.casefold(), value['system_root'].casefold()) for root in roots):
        raise ValueError('SystemRoot must be separate from retained inventories')
    return copy.deepcopy(value)


def validate_toolchain_identity(raw, expected_pin, actual_facts=None):
    """Validate original H bytes/pin, optionally comparing independently built facts.

    Supplying ``actual_facts`` does not establish their provenance or admission.
    The native controller must construct them after actual bounded admission.
    """
    _pin(expected_pin, 'toolchain identity')
    value = toolchain_identity(parse_document(raw))
    if hashlib.sha256(raw).hexdigest() != expected_pin:
        raise ValueError('Toolchain identity SHA256 mismatch')
    if actual_facts is not None:
        _equal(value, toolchain_identity(actual_facts), 'actual toolchain reconstruction')
    return value


def _sources(value, paths):
    _fields(value, SOURCES, 'thirteen original sources')
    original_files = set()
    for supplier, item in value.items():
        _fields(item, ('version', 'archive', 'replay', 'source_subject_sha256',
                       'notice_subject_sha256'), supplier + ' source')
        _text(item['version'], supplier + ' version', 128)
        archive = _fields(item['archive'], ('path', 'sha256', 'bytes', 'format', 'strip_prefix'),
                          supplier + ' archive')
        _reference({k: archive[k] for k in ('path', 'sha256')}, supplier + ' archive', paths)
        _integer(archive['bytes'], supplier + ' archive bytes', 1, 2**32)
        if archive['format'] not in ('tar-gzip', 'tar-xz', 'zip'):
            raise ValueError('Unsupported original archive format')
        prefix = _text(archive['strip_prefix'], 'archive strip prefix', 512)
        if (prefix in ('.', '..') or '/' in prefix or '\\' in prefix or
                re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*', prefix) is None):
            raise ValueError('Invalid archive strip prefix')
        _reference(item['replay'], supplier + ' original replay', paths)
        for selected in (archive['path'], item['replay']['path']):
            if selected.casefold() in original_files:
                raise ValueError('Aliased original supplier archive/replay')
            original_files.add(selected.casefold())
        _pin(item['source_subject_sha256'], supplier + ' source subject')
        _pin(item['notice_subject_sha256'], supplier + ' notice subject')


def _bindings(value, paths):
    _fields(value, ('selection', 'plan', 'producer', 'toolchain_identity_sha256',
                    'sources', 'controller'), 'receipt bindings')
    for name in ('selection', 'plan'):
        _reference(value[name], name, paths)
    producer = _fields(value['producer'], ('controller', 'recipe', 'source_review',
                                          'helpers', 'templates'), 'producer identities')
    for name in ('controller', 'recipe', 'source_review'):
        _reference(producer[name], 'producer ' + name, paths)
    for name in ('helpers', 'templates'):
        _array(producer[name], name, 64, 1)
        seen = set()
        for item in producer[name]:
            _reference(item, name, paths)
            if item['path'].casefold() in seen:
                raise ValueError('Duplicate producer reference')
            seen.add(item['path'].casefold())
    _pin(value['toolchain_identity_sha256'], 'original toolchain H')
    _sources(value['sources'], paths)
    controller = _fields(value['controller'], ('program', 'runtime_subject_sha256',
                                              'machine', 'pointer_bits'), 'actual controller')
    _reference(controller['program'], 'controller interpreter', paths, program=True)
    if controller['program']['path'].rsplit('/', 1)[-1] != 'python.exe':
        raise ValueError('Selected native controller Python required')
    _pin(controller['runtime_subject_sha256'], 'controller runtime subject')
    _equal(controller['machine'], 'AMD64', 'controller machine')
    _equal(controller['pointer_bits'], 64, 'controller pointer bits')


def _safe_argument(value):
    _text(value, 'literal argv')
    if value.casefold().startswith('/clang:'):
        _safe_argument(value[7:])
    literal = value.replace('"', '').replace("'", '')
    upper = literal.upper()
    for assignment in re.finditer(
            r'CMAKE_INTERPROCEDURAL_OPTIMIZATION[^=]*=(.*)', upper):
        # CMake accepts arbitrary non-false values as enabled, including numeric
        # values other than 1. Capture the entire assignment key: custom config
        # and cache-type punctuation must not bypass the false-value policy.
        if assignment.group(1) not in ('OFF', 'NO', 'FALSE', '0', 'IGNORE', 'NOTFOUND'):
            raise ValueError('Forbidden truthy CMake IPO assignment')
    baseline_flags = {'-m64', '-msse2', '-mno-avx', '-mno-avx2', '-mno-avx512f',
                      '-mno-fma', '-mno-f16c', '-mno-rdrnd', '-mno-rdseed', '-mno-adx'}
    for flag in re.finditer(r'(?:^|[= ;:])(-m[^ ;]*)', literal):
        if flag.group(1) not in baseline_flags:
            raise ValueError('Unreviewed CPU feature/baseline argument')
    for flag in re.finditer(r'(?:^|[= ;:])(/ARCH:[^ ;]*)', upper):
        if flag.group(1) != '/ARCH:SSE2':
            raise ValueError('Unreviewed Windows architecture argument')
    if re.search(r'(?:^|[= ;:])-TARGET-(?:CPU|FEATURE)(?:$|[= ;])', upper):
        raise ValueError('Unreviewed explicit compiler CPU/feature route')
    if (re.search(r'(?:^|[= ;])(?:/MD[D]?|/MTD|/GL|/LTCG)(?:$|[= :;])', upper) or
            re.search(r'(?:^|[= ;:])-FLTO(?:=[^ ]*)?', upper) or
            '/ARCH:AVX' in upper or 'MULTITHREADEDDEBUG' in upper or
            'MULTITHREADEDDLL' in upper):
        raise ValueError('Forbidden dynamic/debug CRT, CPU-floor or LTO argument')


def _command(value, paths):
    _fields(value, COMMAND_FIELDS, 'literal command')
    if re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', _text(value['id'], 'command id')) is None:
        raise ValueError('Invalid command id')
    if value['stage'] not in ('configure', 'build', 'install', 'probe'):
        raise ValueError('Unsupported command stage')
    if value['supplier'] not in SOURCES and not (
            value['supplier'] == '__closure__' and value['stage'] == 'probe'):
        raise ValueError('Unknown command supplier')
    if value['stage'] == 'probe' and value['supplier'] != '__closure__':
        raise ValueError('Probe must bind the complete closure')
    _reference(value['program'], 'command program', paths, program=True)
    if value['program']['path'].rsplit('/', 1)[-1] not in PROGRAM_NAMES.values():
        raise ValueError('Undeclared command program role')
    _array(value['argv'], 'literal argv', 512, 1)
    for argument in value['argv']:
        _safe_argument(argument)
    if value['argv'][0] != value['program']['path']:
        raise ValueError('Command executable/argv mismatch')
    paths.add(value['cwd'], 'directory')
    environment = value['environment']
    if type(environment) is not dict or not 1 <= len(environment) <= 128:
        raise ValueError('Explicit complete command environment required')
    seen = set()
    for name, item in environment.items():
        if (re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,95}', name) is None or
                name.casefold() in seen or name.upper() in
                ('CL', '_CL_', 'LINK', '_LINK_', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS')):
            raise ValueError('Ambient or aliased command environment')
        seen.add(name.casefold())
        _safe_argument(item)
        if name.upper() == 'PATH':
            for directory in item.split(';'):
                paths.add(directory, 'directory')
        elif name.upper() == 'SYSTEMROOT':
            paths.add(item, 'directory')
    if not {'path', 'systemroot'} <= seen:
        raise ValueError('Explicit PATH and SystemRoot required')
    if value['initial_cache'] is not None:
        _reference(value['initial_cache'], 'generated initial cache', paths)
    _array(value['response_files'], 'response files', 64)
    responses = []
    for item in value['response_files']:
        _reference(item, 'response file content pin', paths)
        responses.append(item['path'])
    if len(set(responses)) != len(responses) or [item[1:] for item in value['argv'] if item.startswith('@')] != responses:
        raise ValueError('Exact ordered response-file argv/content pins required')
    _equal(value['log_policy'], 'stdout-stderr-combined', 'command log policy')


def _job(value, declaration):
    names = ('owner', 'launch_intent_sha256', 'image', 'launch_suspended',
        'assigned_before_resume', 'breakaway_allowed', 'kill_on_close', 'exit_code',
        'elapsed_milliseconds', 'wall_limit_milliseconds', 'process_count',
        'process_limit', 'peak_output_bytes', 'output_limit_bytes',
        'active_processes_at_join', 'streams_closed', 'join_completed', 'owner_closed')
    _fields(value, names, 'original Windows Job observation')
    _equal(value['owner'], 'windows-job-v1', 'Windows owner')
    _pin(value['launch_intent_sha256'], 'launch intent')
    _equal(value['launch_intent_sha256'], hashlib.sha256(encoded(declaration)).hexdigest(),
           'literal command launch intent')
    _reference(value['image'], 'launched image')
    _equal(value['image'], {k: declaration['program'][k] for k in ('path', 'sha256')},
           'launched tool image')
    for name in ('launch_suspended', 'assigned_before_resume', 'kill_on_close',
                 'streams_closed', 'join_completed', 'owner_closed'):
        _equal(value[name], True, 'closed Job ' + name)
    _equal(value['breakaway_allowed'], False, 'no-breakaway Job')
    for name in ('exit_code', 'active_processes_at_join'):
        _equal(value[name], 0, 'successful joined Job ' + name)
    for observed, limit, low, high in (
            ('elapsed_milliseconds', 'wall_limit_milliseconds', 0, 24 * 3600 * 1000),
            ('process_count', 'process_limit', 1, 65536),
            ('peak_output_bytes', 'output_limit_bytes', 0, 2**40)):
        _integer(value[observed], observed, low, high)
        _integer(value[limit], limit, max(1, low), high)
        if (value[observed] > value[limit] or
                observed == 'elapsed_milliseconds' and value[observed] == value[limit]):
            raise ValueError('Exceeded observed Job bound: ' + observed)


def _prefix(value, paths):
    _fields(value, ('root', 'inventory_subject_sha256', 'header_data_subject_sha256',
                    'notice_subject_sha256'), 'provenance-excluded prefix')
    paths.add(value['root'], 'directory')
    for name in ('inventory_subject_sha256', 'header_data_subject_sha256', 'notice_subject_sha256'):
        _pin(value[name], 'prefix ' + name)


def _libraries(value, bindings, prefix, paths, observations):
    _fields(value, LIBRARY_SUPPLIERS, 'exact twenty-library map')
    build_instances = {}
    library_paths = set()
    for target, item in value.items():
        names = ('path', 'sha256', 'includes', 'definitions', 'links', 'supplier',
                 'source_subject_sha256', 'build_instance')
        _fields(item, names + (('inspection',) if observations else ()), target)
        _reference({k: item[k] for k in ('path', 'sha256')}, target, paths)
        if item['path'].casefold() in library_paths:
            raise ValueError('Aliased twenty-library output')
        library_paths.add(item['path'].casefold())
        if not _inside(item['path'], prefix['root']) or not item['path'].endswith('.lib'):
            raise ValueError('Static library outside dependency prefix')
        supplier = LIBRARY_SUPPLIERS[target]
        _equal(item['supplier'], supplier, 'library supplier')
        _equal(item['source_subject_sha256'], bindings['sources'][supplier]['source_subject_sha256'],
               'library original source')
        _text(item['build_instance'], 'supplier build instance', 128)
        old = build_instances.setdefault(supplier, item['build_instance'])
        if old != item['build_instance']:
            raise ValueError('Supplier targets require same original build instance')
        for directory in _unique_strings(item['includes'], target + ' includes', 64, 1):
            paths.add(directory, 'directory')
            if not _inside(directory, prefix['root']):
                raise ValueError('Library include escapes prefix')
        for definition in _unique_strings(item['definitions'], target + ' definitions', 128):
            if re.fullmatch(r'[A-Z][A-Z0-9_]*(?:=[A-Za-z0-9_]+)?', definition) is None:
                raise ValueError('Nonliteral library definition')
        for link in _unique_strings(item['links'], target + ' ordered links', 64):
            if link not in LIBRARY_SUPPLIERS and link not in SYSTEM_LINKS:
                raise ValueError('Unknown native/system library link')
        if target == 'WebP::libwebp' and 'WebP::sharpyuv' not in item['links']:
            raise ValueError('WebP requires same-source sharpyuv link')
        if target == 'WebP::demux' and 'WebP::libwebp' not in item['links']:
            raise ValueError('WebP demux requires actual libwebp closure')
        if observations:
            inspection = _fields(item['inspection'], INSPECTION_FIELDS, target + ' inspection')
            _equal(inspection['archive_sha256'], item['sha256'], 'inspected archive pin')
            _equal(inspection['format'], 'coff-static', 'static archive format')
            _equal(inspection['machine'], 'AMD64', 'archive machine')
            _integer(inspection['member_count'], 'archive member count', 1, 1000000)
            for name in INSPECTION_FIELDS[4:]:
                _equal(inspection[name], 0, 'forbidden archive ' + name)


def _probe(value, commands, libraries, paths):
    _fields(value, ('command_id', 'library_targets', 'link_inputs', 'output'), 'closure probe')
    ids = {item['id']: item for item in commands}
    _text(value['command_id'], 'probe command id', 96)
    if value['command_id'] not in ids or ids[value['command_id']]['stage'] != 'probe':
        raise ValueError('Closure probe must bind an original probe command')
    if value['library_targets'] != sorted(LIBRARY_SUPPLIERS):
        raise ValueError('Probe requires exact complete twenty-library closure')
    _array(value['link_inputs'], 'probe link inputs', 64, 20)
    for item in value['link_inputs']:
        _reference(item, 'probe link input', paths)
    selected = [item['path'] for item in value['link_inputs']]
    if len(set(selected)) != len(selected):
        raise ValueError('Duplicate probe link input')
    expected = [{k: libraries[target][k] for k in ('path', 'sha256')}
                for target in sorted(LIBRARY_SUPPLIERS)]
    if value['link_inputs'][:20] != expected:
        raise ValueError('Probe link inputs must start with exact ordered dependency closure')
    _reference(value['output'], 'probe output', paths)
    if not value['output']['path'].endswith('.exe'):
        raise ValueError('Native static closure probe executable required')


def validate_receipt(value, expected):
    """Check original receipt semantics against independent source declarations.

    This returns owned receipt facts and makes **no native/body admission**.
    ``expected`` has exactly bindings, commands, prefix, libraries, probe. Its
    commands omit logs/output_subject_sha256/job; libraries omit inspection.
    Every other original declaration must match exactly, including order.
    Callers must obtain expected declarations from independently pinned inputs.
    """
    encoded(value)
    encoded(expected)
    _fields(expected, ('bindings', 'commands', 'prefix', 'libraries', 'probe'), 'receipt expectations')
    _fields(value, ('schema_version', 'kind', 'target', 'scope', 'bindings', 'commands',
                    'prefix', 'libraries', 'postflight', 'probe', 'facts'), 'original dependency receipt')
    _equal(value['schema_version'], 1, 'receipt schema')
    _equal(value['kind'], RECEIPT_KIND, 'receipt kind')
    _equal(value['target'], TARGET, 'receipt target')
    _equal(value['scope'], SCOPE, 'receipt scope')
    paths = _Paths()
    _bindings(expected['bindings'], paths)
    _prefix(expected['prefix'], paths)
    _array(expected['commands'], 'expected commands', MAX_COMMANDS, 1)
    ids, stages = set(), {name: [] for name in SOURCES}
    for command in expected['commands']:
        _command(command, paths)
        if command['id'] in ids:
            raise ValueError('Duplicate original command id')
        ids.add(command['id'])
        if command['supplier'] in stages:
            stages[command['supplier']].append(command['stage'])
    if any(stage != ['configure', 'build', 'install'] for stage in stages.values()):
        raise ValueError('Each supplier requires ordered configure/build/install stages')
    if [x['stage'] for x in expected['commands']].count('probe') != 1 or expected['commands'][-1]['stage'] != 'probe':
        raise ValueError('Exactly one final closure probe required')
    _libraries(expected['libraries'], expected['bindings'], expected['prefix'], paths, False)
    _probe(expected['probe'], expected['commands'], expected['libraries'], paths)
    for name in ('bindings', 'prefix', 'probe'):
        _equal(value[name], expected[name], 'original ' + name)
    _array(value['commands'], 'original commands', MAX_COMMANDS, 1)
    if len(value['commands']) != len(expected['commands']):
        raise ValueError('Incomplete original command stages')
    for actual, declaration in zip(value['commands'], expected['commands']):
        _fields(actual, COMMAND_FIELDS + ('logs', 'output_subject_sha256', 'job'), 'original command observation')
        _equal({k: actual[k] for k in COMMAND_FIELDS}, declaration, 'original literal command')
        _fields(actual['logs'], ('combined',), 'closed combined command log')
        _reference(actual['logs']['combined'], 'original combined log')
        log_path = actual['logs']['combined']['path']
        if log_path.casefold() in paths.entries:
            raise ValueError('Original command log aliases another input/output')
        _reference(actual['logs']['combined'], 'original combined log', paths)
        _pin(actual['output_subject_sha256'], 'original command outputs')
        _job(actual['job'], declaration)
    _libraries(value['libraries'], value['bindings'], value['prefix'], paths, True)
    _equal({target: {key: item for key, item in record.items() if key != 'inspection'}
            for target, record in value['libraries'].items()}, expected['libraries'], 'original library map')
    _fields(value['postflight'], ('toolchain_identity_sha256', 'sources'), 'frozen input postflight')
    _equal(value['postflight']['toolchain_identity_sha256'],
           value['bindings']['toolchain_identity_sha256'], 'unchanged toolchain postflight')
    _equal(value['postflight']['sources'], {name: value['bindings']['sources'][name]['source_subject_sha256']
                                          for name in SOURCES}, 'unchanged source postflight')
    _fields(value['facts'], FALSE_FACTS, 'unqualified dependency facts')
    for name in FALSE_FACTS:
        _equal(value['facts'][name], False, 'unqualified ' + name)
    return copy.deepcopy(value)


def admit_dependency_producer(receipt_ref, native_inputs, inventories, identity):
    """Delegate bounded native admission to its explicit controller entry point.

    The controller must enforce native Windows, reviewed recipe authority and
    admitted retained bodies. The pure validator above is never that authority.
    No native/prototype code is imported until this explicit operation is called.
    """
    from appended_engine_windows_dependencies import admit_dependency_producer as admit
    return admit(receipt_ref, native_inputs, inventories, identity)


def validate_source_declarations(identity_raw, identity_pin, receipt_raw,
                                 receipt_pin, native_inputs):
    """Delegate source-only expectation derivation to the pinned recipe controller.

    The controller derives expectations independently of D; it must fail closed
    while reviewed supplier commands are absent. This is not native admission.
    """
    from appended_engine_windows_dependencies import validate_source_declarations as validate
    return validate(identity_raw, identity_pin, receipt_raw, receipt_pin, native_inputs)
