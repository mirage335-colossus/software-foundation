"""Pure fixed supplier declaration contract; no input or native authority.

Only maintained pinned source metadata/templates are read. The actual producer
owns original source admission, native H2 reconstruction and fixed registration.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import types

MODULE_NAME = '_foundation_windows_supplier_factory_contract_v1'
_ROOT = Path(__file__).resolve().parents[2]
_GAP = Path(__file__).resolve().parent
_PROFILE = '14b73b412dab26015fdec17027e29526cfc35f1b9f377a675333257b75860ada'
_TEMPLATE = '5461a349b2f16b1cb4fadb87b8714d86eca790206ae8b44d93ef9403f50256a7'
_PROOF = 'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9'
_CONTEXT = ('supplier', 'identity', 'source_layout', 'source_recipe_bindings',
    'workspace_root', 'source_root', 'project_root', 'binary_root', 'prefix_root',
    'toolchain_file', 'cache_file', 'environment')
_COMMAND = ('id', 'supplier', 'stage', 'program', 'argv', 'cwd', 'environment',
    'initial_cache', 'response_files', 'log_policy')
_STAGES = ('configure', 'build-tool', 'generate', 'build', 'install', 'probe')
_P = None


class MissingInputs(ValueError):
    def __init__(self, gaps):
        if (type(gaps) not in (list, tuple) or not 1 <= len(gaps) <= 128
                or any(type(item) is not str or not re.fullmatch(
                    r'[a-z][a-z0-9-]{0,191}', item) for item in gaps)
                or len(set(gaps)) != len(gaps)):
            raise ValueError('Finite distinct named missing inputs required')
        self.gaps = tuple(gaps)
        super().__init__(', '.join(self.gaps))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _source(path, pin, maximum):
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if not raw or len(raw) > maximum or _sha(raw) != pin:
        raise ValueError('Maintained supplier contract source changed')
    return raw


def _proof():
    global _P
    if _P is None:
        path = _GAP / 'proof_h2.py'
        raw = _source(path, _PROOF, 65536)
        module = types.ModuleType('_supplier_factory_pure_h2')
        module.__file__ = str(path)
        exec(compile(raw, str(path), 'exec'), vars(module))
        _P = module
    return _P


def _fields(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('Closed ' + label + ' required')


def _equal(left, right, label):
    if _proof().encoded(left) != _proof().encoded(right):
        raise ValueError(label + ' differs')


def _source_preflight(value):
    # Bound structure and escaped ASCII allocation BEFORE asking json to encode.
    pending, nodes, estimate = [(value, 0)], 0, 0
    maximum = 32 * 1024**2
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > 1000000 or depth > 64:
            raise ValueError('Supplier metadata structure exceeds bound')
        if type(item) is str:
            estimate += 2
            for char in item:
                number = ord(char)
                estimate += (2 if char in '\\"' else 6 if number < 32 or 127 <= number <= 65535
                    else 12 if number > 65535 else 1)
                if estimate > maximum:
                    raise ValueError('Supplier metadata escaped bytes exceed bound')
        elif type(item) in (dict, list):
            if len(item) > 65536:
                raise ValueError('Supplier metadata container exceeds bound')
            estimate += 2 + 2 * depth + len(item) * (2 * depth + 8)
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise ValueError('Supplier metadata keys must be strings')
                for key, child in item.items():
                    pending.append((key, depth + 1))
                    pending.append((child, depth + 1))
            else:
                pending.extend((child, depth + 1) for child in item)
            if len(pending) + nodes > 1000000:
                raise ValueError('Supplier metadata pending structure exceeds bound')
        elif item is None or type(item) is bool:
            estimate += 5
        elif type(item) is int and item.bit_length() <= 64:
            estimate += 21
        else:
            raise ValueError('Supplier metadata scalar is outside closed domain')
        if estimate > maximum:
            raise ValueError('Supplier metadata estimated bytes exceed bound')


def _source_encoded(value):
    # Source projections use the inventory domain, not the H2/D2 document cap.
    _source_preflight(value)
    raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
        allow_nan=False) + '\n').encode('ascii')
    if len(raw) > 32 * 1024**2:
        raise ValueError('Supplier metadata exceeds bounded inventory domain')
    return raw


def _integer(value, label, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Bounded ' + label + ' required')


def _path(value):
    return _proof().legacy().windows_path(value)


def _relative(value):
    if (type(value) is not str or not value or len(value) > 2048
            or value.startswith('/') or '\\' in value or ':' in value):
        raise ValueError('Portable relative path required')
    _path('C:/relative/' + value)
    return value


def _ref(value):
    _fields(value, ('path', 'sha256'), 'recipe reference')
    _path(value['path'])
    _proof().legacy()._pin(value['sha256'], 'recipe reference')
    return copy.deepcopy(value)


def _inside(path, root):
    return path.casefold().startswith(root.casefold() + '/')


def _profile():
    path = _ROOT / 'recipes/webkitwasm-native-deps-windows-x86_64-v1/profile.json'
    return json.loads(_source(path, _PROFILE, 65536))


def _merge_reference(refs, value):
    _ref(value)
    key = value['path'].casefold()
    previous = refs.get(key)
    if previous is not None and previous != value:
        raise ValueError('Recipe references conflict in Windows spelling or pin')
    refs[key] = copy.deepcopy(value)


def _file_layout(names):
    seen = set()
    for name in names:
        key = name.casefold()
        if key in seen:
            raise ValueError('File outputs alias')
        seen.add(key)
    for name in seen:
        parts = name.split('/')
        if any('/'.join(parts[:i]) in seen for i in range(1, len(parts))):
            raise ValueError('File output is another output parent')


def _check_context(value):
    _fields(value, _CONTEXT, 'factory context')
    actual = factory_context(value['supplier'], identity=value['identity'],
        source_layout=value['source_layout'], build_root=value['workspace_root'],
        prefix_root=value['prefix_root'], source_recipe_bindings=value['source_recipe_bindings'])
    if _source_encoded(value) != _source_encoded(actual):
        raise ValueError('Derived factory context differs')
    return actual


def _render(context):
    path = _ROOT / 'recipes/webkitwasm-native-deps-windows-x86_64-v1/initial-cache.cmake.in'
    text = _source(path, _TEMPLATE, 65536).decode('ascii')
    roles = {'COMPILER': 'compiler', 'LINKER': 'linker', 'ARCHIVER': 'archiver',
        'RESOURCE_COMPILER': 'resource_compiler', 'MANIFEST_TOOL': 'manifest_tool', 'NINJA': 'ninja'}
    for key, role in roles.items():
        selected = context['identity']['programs'][role]['path']
        if any(char in selected for char in '$;"\\\r\n'):
            raise ValueError('Selected path cannot be represented by fixed CMake renderer')
        token = '@FOUNDATION_WINDOWS_' + key + '@'
        if token not in text:
            raise ValueError('Maintained program placeholder absent')
        text = text.replace(token, selected)
    if '@FOUNDATION_' in text:
        raise ValueError('Unresolved maintained CMake placeholder')
    # External compatibility default, not an assertion about actual emitted CRT.
    text += '\nset(CMAKE_POLICY_DEFAULT_CMP0091 NEW CACHE STRING "Use runtime abstraction for older vendor projects")\n'
    cache = context['cache_file']
    if any(char in cache for char in '$;"\\\r\n'):
        raise ValueError('Cache path cannot be represented by fixed CMake renderer')
    toolchain = '# Source-owned Windows toolchain; selected cache is pinned separately.\ninclude("' + cache + '")\n'
    prefix = 'recipes/' + context['supplier'] + '/'
    files = [{'output': prefix + 'initial-cache.cmake', 'content': text},
        {'output': prefix + 'toolchain.cmake', 'content': toolchain}]
    refs = {row['output'].rsplit('/', 1)[-1]: {'path': context['workspace_root'] + '/' + row['output'],
        'sha256': _sha(row['content'].encode('ascii'))} for row in files}
    return {'rendered_files': files, 'references': refs}


def factory_context(supplier, *, identity, source_layout, build_root, prefix_root,
                    source_recipe_bindings):
    profile = _profile()
    if type(supplier) is not str or supplier not in profile['components']:
        raise ValueError('Exact fixed supplier required')
    identity = _proof().toolchain_identity(identity)
    _path(build_root)
    _path(prefix_root)
    if prefix_root != build_root + '/prefix':
        raise ValueError('Exact Workspace prefix required')
    for root in [row['root'] for row in identity['inventories'].values()] + [identity['system_root']]:
        if (root.casefold() == build_root.casefold() or _inside(root, build_root)
                or _inside(build_root, root)):
            raise ValueError('Workspace overlaps original tool/runtime root')
    _fields(source_layout, ('root', 'files', 'directories'), 'source projection')
    if source_layout['root'] != build_root + '/sources/' + supplier:
        raise ValueError('Exact source projection root required')
    files, directories = source_layout['files'], source_layout['directories']
    if type(files) is not dict or not 1 <= len(files) <= 65536:
        raise ValueError('Finite nonempty original source projection required')
    if type(directories) is not list or len(directories) > 65536 or directories != sorted(set(directories)):
        raise ValueError('Sorted unique source directories required')
    seen, total = {}, 0
    for directory in directories:
        _relative(directory)
        if directory.casefold() in seen:
            raise ValueError('Source projection paths alias')
        seen[directory.casefold()] = 'directory'
    for member, row in files.items():
        _relative(member)
        _fields(row, ('sha256', 'bytes'), 'source file')
        _proof().legacy()._pin(row['sha256'], 'source file')
        _integer(row['bytes'], 'source file bytes', 512 * 1024**2)
        total += row['bytes']
        if total > 32 * 1024**3 or member.casefold() in seen:
            raise ValueError('Source projection bound or alias')
        seen[member.casefold()] = 'file'
    for name in seen:
        parents = name.split('/')[:-1]
        if any(seen.get('/'.join(parents[:i])) != 'directory' for i in range(1, len(parents) + 1)):
            raise ValueError('Complete source parent directories required')
    _source_preflight(source_layout)
    _fields(source_recipe_bindings, ('source', 'recipes'), 'source recipe bindings')
    _equal(source_recipe_bindings['source'], profile['components'][supplier], 'fixed supplier archive identity')
    recipes = source_recipe_bindings['recipes']
    if type(recipes) is not dict or len(recipes) > 32:
        raise ValueError('Finite selected recipe map required')
    aliases, recipe_refs = set(), {}
    for name, ref in recipes.items():
        _relative(name)
        _ref(ref)
        if name.casefold() in aliases:
            raise ValueError('Selected recipe names alias')
        aliases.add(name.casefold())
        _merge_reference(recipe_refs, ref)
    parents = sorted({row['path'].rsplit('/', 1)[0] for row in identity['programs'].values()}, key=str.casefold)
    environment = {'SystemRoot': identity['system_root'], 'PATH': ';'.join(parents),
        'TEMP': build_root + '/tmp', 'TMP': build_root + '/tmp',
        'INCLUDE': ';'.join(identity['include_directories']), 'LIB': ';'.join(identity['library_directories'])}
    result = {'supplier': supplier, 'identity': identity, 'source_layout': copy.deepcopy(source_layout),
        'source_recipe_bindings': copy.deepcopy(source_recipe_bindings), 'workspace_root': build_root,
        'source_root': source_layout['root'], 'project_root': build_root + '/recipes/' + supplier,
        'binary_root': build_root + '/build/' + supplier, 'prefix_root': prefix_root,
        'toolchain_file': build_root + '/recipes/' + supplier + '/toolchain.cmake',
        'cache_file': build_root + '/recipes/' + supplier + '/initial-cache.cmake', 'environment': environment}
    for key in ('source_root', 'project_root', 'binary_root', 'toolchain_file', 'cache_file'):
        _path(result[key])
    generic = {'toolchain.cmake', 'initial-cache.cmake'}
    if generic.intersection(recipes):
        if not generic.issubset(recipes):
            raise ValueError('Both common CMake recipe references required')
        for name, ref in _render(result)['references'].items():
            _equal(recipes[name], ref, 'source-rendered common CMake ' + name)
    return result


def original_program(context, role):
    context = _check_context(context)
    return _original_program(context, role)


def _original_program(context, role):
    if type(role) is not str or role not in context['identity']['programs']:
        raise ValueError('Original H2 role required')
    return {'kind': 'original', 'role': role,
        'declaration': copy.deepcopy(context['identity']['programs'][role])}


def render_cmake_inputs(context):
    return _render(_check_context(context))


def rendered_reference(context, output, content):
    context = _check_context(context)
    return _rendered_reference(context, output, content)


def _rendered_reference(context, output, content):
    _relative(output)
    if not output.startswith('recipes/' + context['supplier'] + '/'):
        raise ValueError('Supplier-owned rendered output required')
    if (type(content) is not str or not content or not content.isascii()
            or '\r' in content or '\x00' in content or len(content) > 65536):
        raise ValueError('Bounded nonempty ASCII LF render required')
    path = context['workspace_root'] + '/' + output
    _path(path)
    return {'path': path, 'sha256': _sha(content.encode('ascii'))}


def validate_factory_result(context, result):
    context = _check_context(context)
    supplier, workspace = context['supplier'], context['workspace_root']
    _fields(result, ('commands', 'registration', 'source_files', 'rendered_files',
        'generated_inputs', 'install_artifacts'), 'supplier result')
    commands = result['commands']
    if type(commands) is not list or not 1 <= len(commands) <= 128:
        raise ValueError('Finite complete supplier commands required')
    _fields(result['registration'], ('stages', 'produced_tools'), 'supplier registration')
    rows, indices = {}, {}
    for index, command in enumerate(commands):
        _fields(command, _COMMAND, 'supplier command')
        identifier = command['id']
        if (type(identifier) is not str or re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', identifier) is None
                or identifier in rows or command['supplier'] != supplier or command['stage'] not in _STAGES):
            raise ValueError('Unique exact supplier stage required')
        rows[identifier], indices[identifier] = command, index
    _equal(result['registration']['stages'], [{key: row[key] for key in ('id', 'supplier', 'stage')}
        for row in commands], 'complete supplier stage registration')
    tools = result['registration']['produced_tools']
    if type(tools) is not dict or len(tools) > 64:
        raise ValueError('Finite produced tool registration required')
    toolpaths = set()
    for role, row in tools.items():
        if (supplier != 'icu' or type(role) is not str or role in context['identity']['programs']
                or re.fullmatch(r'[a-z][a-z0-9_-]{0,95}', role) is None):
            raise ValueError('Fixed ICU produced role required')
        _fields(row, ('producing_command_id', 'output', 'root'), 'produced registration')
        _relative(row['output'])
        _path(row['root'])
        producer = rows.get(row['producing_command_id'])
        path = row['root'] + '/' + row['output']
        _path(path)
        if (not _inside(row['root'], workspace) or not row['output'].endswith('.exe')
                or producer is None or producer['stage'] != 'build-tool' or path.casefold() in toolpaths):
            raise ValueError('Owned closed producer executable required')
        toolpaths.add(path.casefold())
    renders = result['rendered_files']
    if type(renders) is not list or len(renders) > 32:
        raise ValueError('Finite rendered files required')
    rendernames, refs, rendered_bytes = [], {}, 0
    for row in renders:
        _fields(row, ('output', 'content'), 'rendered file')
        ref = _rendered_reference(context, row['output'], row['content'])
        rendernames.append(row['output'])
        _merge_reference(refs, ref)
        rendered_bytes += len(row['content'])
    if rendernames != sorted(set(rendernames)) or len({name.casefold() for name in rendernames}) != len(rendernames) or rendered_bytes > 1024**2:
        raise ValueError('Sorted unique bounded renders required')
    _file_layout(rendernames)
    common = _render(context)
    for row in common['rendered_files']:
        if row['output'] in rendernames:
            actual = renders[rendernames.index(row['output'])]
            if _source_encoded(actual) != _source_encoded(row):
                raise ValueError('Fixed common CMake render differs')
    for row in context['source_recipe_bindings']['recipes'].values():
        _merge_reference(refs, row)
    selected = result['source_files']
    if type(selected) is not list or not 1 <= len(selected) <= 65536:
        raise ValueError('Finite selected original source files required')
    names = []
    for row in selected:
        _fields(row, ('member', 'sha256', 'bytes'), 'selected source file')
        _relative(row['member'])
        _equal({key: row[key] for key in ('sha256', 'bytes')},
            context['source_layout']['files'].get(row['member']), 'selected original source file')
        names.append(row['member'])
        path = context['source_root'] + '/' + row['member']
        _merge_reference(refs, {'path': path, 'sha256': row['sha256']})
    if names != sorted(set(names)):
        raise ValueError('Sorted unique selected sources required')
    _file_layout([row['path'] for row in refs.values()])
    argv_bytes = 0
    for command in commands:
        program = command['program']
        if type(program) is not dict:
            raise ValueError('Tagged program required')
        if program.get('kind') == 'original':
            _equal(program, _original_program(context, program.get('role')), 'exact original role tag')
            executable = program['declaration']['path']
        elif program.get('kind') == 'produced':
            _fields(program, ('kind', 'role', 'producing_command_id', 'output'), 'produced tag')
            row = tools.get(program['role'])
            if row is None or any(program[key] != row[key] for key in ('producing_command_id', 'output')):
                raise ValueError('Registered produced tag required')
            if indices[row['producing_command_id']] >= indices[command['id']]:
                raise ValueError('Strictly earlier produced executable required')
            executable = row['root'] + '/' + row['output']
        else:
            raise ValueError('Supported original or produced tag required')
        argv = command['argv']
        if (type(argv) is not list or not 1 <= len(argv) <= 512 or argv[0] != executable
                or any(type(arg) is not str or not arg or len(arg) > 8192
                    or any(ord(char) < 32 or ord(char) > 126 for char in arg) for arg in argv)):
            raise ValueError('Finite literal executable argv required')
        argv_bytes += sum(map(len, argv))
        if argv_bytes > 1024**2:
            raise ValueError('Aggregate literal argv bytes exceed bound')
        _path(command['cwd'])
        if command['cwd'] != workspace and not _inside(command['cwd'], workspace):
            raise ValueError('Owned command cwd required')
        _equal(command['environment'], context['environment'], 'fixed H2 environment')
        if command['log_policy'] != 'stdout-stderr-combined':
            raise ValueError('Combined original log required')
        response = command['response_files']
        if type(response) is not list or len(response) > 64:
            raise ValueError('Finite response file references required')
        for ref in ([command['initial_cache']] if command['initial_cache'] is not None else []) + response:
            _ref(ref)
            _equal(refs.get(ref['path'].casefold()), ref, 'selected source/render recipe reference')
    generated = result['generated_inputs']
    if type(generated) is not list or len(generated) > 4096:
        raise ValueError('Finite generated input declarations required')
    seen = set()
    for row in generated:
        _fields(row, ('consumer_command_id', 'producing_command_id', 'output'), 'generated input')
        _relative(row['output'])
        producer, consumer = row['producing_command_id'], row['consumer_command_id']
        if producer not in rows or consumer not in rows or indices[producer] >= indices[consumer]:
            raise ValueError('Strictly earlier generated input producer required')
        key = (consumer, row['output'].casefold())
        if key in seen:
            raise ValueError('Generated input declarations alias')
        seen.add(key)
        if workspace + '/' + row['output'] not in rows[consumer]['argv']:
            raise ValueError('Generated file must be a literal consumer operand')
    artifacts = result['install_artifacts']
    _fields(artifacts, ('libraries', 'headers'), 'install artifacts')
    expected = {key for key, row in _profile()['libraries'].items() if row['supplier'] == supplier}
    if type(artifacts['libraries']) is not dict or set(artifacts['libraries']) != expected:
        raise ValueError('Exact fixed supplier library targets required')
    paths = set()
    for path in artifacts['libraries'].values():
        _relative(path)
        if not path.endswith('.lib') or path.casefold() in paths:
            raise ValueError('Unique literal static library paths required')
        paths.add(path.casefold())
    headers = artifacts['headers']
    if type(headers) is not list or len(headers) > 65536 or headers != sorted(set(headers)):
        raise ValueError('Sorted unique installed header paths required')
    for path in headers:
        _relative(path)
        if path.casefold() in paths:
            raise ValueError('Installed artifact paths alias')
        paths.add(path.casefold())
    _file_layout([*artifacts['libraries'].values(), *headers])
    _source_encoded(result)
    return copy.deepcopy(result)
